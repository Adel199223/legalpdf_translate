"""Google Gemini Interactions API wrapper with bounded transport retries."""

from __future__ import annotations

import hashlib
import json
import math
import os
import random
import re
import time
from copy import copy, deepcopy
from typing import Any, Callable

import httpx
from google import genai
from google.genai import errors as genai_errors

from .config import (
    GEMINI_MODEL,
    GEMINI_SEMANTIC_REVIEW_MODEL,
    GEMINI_STORE,
)
from .openai_client import (
    ApiCallError,
    ApiCallResult,
    OpenAICredentialSourceInfo,
    TranslationAuthTestResult,
    _active_accountant,
    _compute_sleep_seconds,
    _dispatch_limits,
    _field,
    _retry_after_seconds,
    _status_code_from_exception,
    _validate_dispatch_input_bound,
    _validated_page_images,
)
from .secrets_store import get_gemini_key, get_ocr_key
from .usage_accounting import MemoryDispatchAccounting, normalize_usage

_AUTH_TEST_ACCOUNTING = MemoryDispatchAccounting()
_GEMINI_MODELS = frozenset(
    {
        "gemini-4-neon",
        "gemini-4-hydrogen",
        "gemini-4-carbon",
        "gemini-4-argon",
        "gemini-3.5-flash-lite",
    }
)
_GEMINI_THINKING_LEVELS = frozenset({"low", "medium", "high", "xhigh"})
_GEMINI_DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com"
_DATA_URL_PATTERN = re.compile(
    r"data:(image/[A-Za-z0-9][A-Za-z0-9.+-]*);base64,([A-Za-z0-9+/]+={0,2})"
)


def normalize_gemini_thinking_level(value: object, *, default: str = "xhigh") -> str:
    cleaned = str(value or "").strip().lower()
    if cleaned in _GEMINI_THINKING_LEVELS:
        return cleaned
    return default if default in _GEMINI_THINKING_LEVELS else "high"


def resolve_gemini_key_with_source(
    api_key: str | None = None,
    *,
    allow_ocr_fallback: bool = False,
) -> tuple[str | None, OpenAICredentialSourceInfo | None]:
    resolved_api_key = (api_key or "").strip() or None
    if resolved_api_key:
        return resolved_api_key, OpenAICredentialSourceInfo(kind="inline", name="")
    try:
        stored_key = get_gemini_key()
    except RuntimeError:
        stored_key = None
    if stored_key:
        return stored_key, OpenAICredentialSourceInfo(kind="stored", name="gemini_api_key")
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        env_key = os.getenv(env_name, "").strip()
        if env_key:
            return env_key, OpenAICredentialSourceInfo(kind="env", name=env_name)
    if allow_ocr_fallback:
        try:
            stored_ocr_key = get_ocr_key()
        except RuntimeError:
            stored_ocr_key = None
        if stored_ocr_key:
            return stored_ocr_key, OpenAICredentialSourceInfo(kind="stored", name="ocr_api_key_fallback")
    return None, None


def is_gemini_auth_failure(
    *,
    exception_class: str,
    status_code: int | None,
    message: str = "",
) -> bool:
    if status_code in (401, 403):
        return True
    lowered = f"{exception_class} {message}".lower()
    return (
        "api_key_invalid" in lowered
        or "api key not valid" in lowered
        or "permission_denied" in lowered
        or "unauthenticated" in lowered
    )


def _extract_gemini_base_url(client: Any) -> str:
    explicit = getattr(client, "base_url", None)
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().rstrip("/")
    api_client = getattr(client, "_api_client", None)
    http_options = getattr(api_client, "_http_options", None) if api_client is not None else None
    raw = getattr(http_options, "base_url", None) if http_options is not None else None
    if isinstance(raw, str) and raw.strip():
        return raw.strip().rstrip("/")
    return _GEMINI_DEFAULT_BASE_URL


def _trusted_gemini_billing_scope(client: Any, limits: dict[str, Any]) -> str | None:
    scope = limits.get("billing_scope")
    allowed = limits.get("allowed_base_urls")
    actual = _extract_gemini_base_url(client)
    if not isinstance(scope, str) or not isinstance(allowed, (list, tuple)):
        return None
    return scope if actual in [str(value).rstrip("/") for value in allowed] else None


def _parse_data_url_image(url: str) -> dict[str, Any]:
    match = _DATA_URL_PATTERN.fullmatch(url)
    if match is None:
        raise ValueError("Each image must be a nonempty base64 image data URL.")
    return {
        "type": "image",
        "mime_type": match.group(1),
        "data": match.group(2),
    }


def _build_gemini_page_request(
    *,
    instructions: str,
    prompt_text: str,
    effort: str,
    image_data_url: str | None = None,
    image_detail: str = "low",
    image_data_urls: list[str] | tuple[str, ...] | None = None,
    response_format: dict[str, Any] | None = None,
    max_output_tokens: int | None = None,
    model: str = GEMINI_MODEL,
) -> dict[str, Any]:
    del image_detail  # Interactions ImageContent uses resolution/default; preserve signature parity.
    if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens <= 0):
        raise ValueError("max_output_tokens must be a positive integer.")
    if response_format is not None and (
        not isinstance(response_format, dict)
        or response_format.get("type") != "json_schema"
        or response_format.get("strict") is not True
        or not isinstance(response_format.get("schema"), dict)
        or not isinstance(response_format.get("name"), str)
        or not response_format["name"]
    ):
        raise ValueError("A strict named JSON-schema response format is required.")
    images = _validated_page_images(image_data_url, image_data_urls)
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt_text}]
    if images is not None:
        content.extend(_parse_data_url_image(url) for url in images)
    elif image_data_url:
        _validated_page_images(None, [image_data_url])
        content.append(_parse_data_url_image(image_data_url))

    thinking_level = normalize_gemini_thinking_level(effort, default="high")
    generation_config: dict[str, Any] = {"thinking_level": thinking_level}
    if max_output_tokens is not None:
        generation_config["max_output_tokens"] = max_output_tokens

    request: dict[str, Any] = {
        "model": model,
        "input": content,
        "generation_config": generation_config,
        "store": GEMINI_STORE,
    }
    if instructions and instructions.strip():
        request["system_instruction"] = instructions
    if response_format is not None:
        request["response_format"] = {
            "type": "text",
            "mime_type": "application/json",
            "schema": deepcopy(response_format["schema"]),
        }
    return request


def _apply_gemini_dispatch_limits(
    request: dict[str, Any],
    accountant: Any,
    limits: dict[str, Any],
) -> dict[str, Any]:
    request = deepcopy(request)
    maximum = limits.get("max_output_tokens")
    if maximum is not None and (accountant.hard_budget or not limits.get("apply_output_bound_only_when_hard")):
        if type(maximum) is not int or maximum <= 0:
            raise ValueError("Dispatch output token bound must be a positive integer.")
        gen_cfg = request.setdefault("generation_config", {})
        current = gen_cfg.get("max_output_tokens", maximum)
        gen_cfg["max_output_tokens"] = min(maximum, current)
    return request


def _request_accounting_details(request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    stable = {key: value for key, value in request.items() if key != "timeout"}
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    input_items = stable.get("input")
    image_count = 0
    if isinstance(input_items, list):
        image_count = sum(
            1 for part in input_items if isinstance(part, dict) and part.get("type") == "image"
        )
    text_request = deepcopy(stable)
    if isinstance(text_request.get("input"), list):
        for part in text_request["input"]:
            if isinstance(part, dict) and part.get("type") == "image":
                part.pop("data", None)
    input_bytes = len(json.dumps(text_request, sort_keys=True, ensure_ascii=False).encode("utf-8")) + 64
    bounds: dict[str, Any] = {"input_bytes": input_bytes, "image_count": image_count}
    gen_cfg = request.get("generation_config")
    if isinstance(gen_cfg, dict) and gen_cfg.get("max_output_tokens") is not None:
        bounds["max_output_tokens"] = gen_cfg["max_output_tokens"]
    return hashlib.sha256(encoded).hexdigest(), bounds


def _extract_gemini_output_text(response: Any) -> str:
    output_text = _field(response, "output_text")
    if isinstance(output_text, str) and output_text != "":
        return output_text
    steps = _field(response, "steps")
    if isinstance(steps, list):
        parts: list[str] = []
        collecting = False
        for step in reversed(steps):
            step_type = _field(step, "type")
            if step_type == "user_input":
                break
            if step_type == "thought":
                continue
            if step_type != "model_output":
                if collecting:
                    break
                continue
            content = _field(step, "content")
            if not isinstance(content, list):
                continue
            should_stop = False
            for item in reversed(content):
                if _field(item, "type") == "text":
                    collecting = True
                    text = _field(item, "text")
                    if isinstance(text, str):
                        parts.append(text)
                elif collecting:
                    should_stop = True
                    break
            if should_stop:
                break
        joined = "".join(reversed(parts)).strip()
        if joined:
            return joined
    raise RuntimeError("Gemini Interactions API returned no textual output.")


def _extract_gemini_usage(response: Any) -> dict[str, Any]:
    usage_obj = _field(response, "usage")
    if usage_obj is None:
        return {}
    normalized = normalize_usage(usage_obj, provider="gemini")
    result: dict[str, Any] = {}
    for key in (
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "reasoning_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
    ):
        val = normalized.get(key)
        if val is not None:
            result[key] = val
    return result


def _gemini_has_refusal(response: Any) -> bool:
    if _field(response, "refusal"):
        return True
    errors = _field(response, "errors")
    if isinstance(errors, list):
        for err in errors:
            code = str(_field(err, "code", "") or "").lower()
            if code in {"safety", "prohibited_content", "blocklist", "image_safety", "content_blocked"}:
                return True
    return False


def _gemini_incomplete_reason(response: Any) -> str | None:
    status = str(_field(response, "status", "") or "").lower()
    if status in {"requires_continuation", "incomplete"}:
        return "max_output_tokens"
    if status in {"failed", "cancelled"}:
        errors = _field(response, "errors")
        if isinstance(errors, list) and errors:
            code = str(_field(errors[0], "code", "") or "").lower()
            if "safety" in code or "content" in code:
                return "content_filter"
        return "unknown"
    return None


def _is_gemini_retryable(exc: Exception) -> bool:
    status = _status_code_from_exception(exc)
    if status in (401, 403):
        return False
    if status in (429, 500, 502, 503, 504):
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError, TimeoutError)):
        return True
    if isinstance(exc, genai_errors.ServerError):
        return True
    return False


def _error_response(exc: BaseException) -> Any:
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        return body
    if isinstance(body, str) and body.strip():
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return parsed
        except ValueError:
            pass
    response = getattr(exc, "response", None) or getattr(exc, "raw_response", None)
    if response is not None and _field(response, "usage") is not None:
        return response
    return None


def _finish_gemini_attempt(
    accountant: Any,
    ticket: Any,
    *,
    response: Any,
    outcome: str,
    error_code: str | None = None,
    billing_scope: str | None = None,
    currency: str = "USD",
    strict_semantic: bool = False,
    semantic_response_evidence: Any = None,
) -> Any:
    usage = _field(response, "usage") if strict_semantic else _extract_gemini_usage(response)
    response_id = _field(response, "id")
    actual_model = _field(response, "model")
    actual_tier = _field(response, "service_tier") or "default"
    try:
        return accountant.finish(
            ticket,
            outcome=outcome,
            usage=usage,
            response_id=response_id,
            actual_model=actual_model,
            error_code=error_code,
            actual_service_tier=actual_tier,
            actual_billing_scope=billing_scope,
            currency=currency,
            **({"semantic_response_evidence": semantic_response_evidence} if strict_semantic else {}),
        )
    except Exception as exc:  # noqa: BLE001
        exc.body = {  # type: ignore[attr-defined]
            "usage": usage,
            "id": response_id,
            "model": actual_model,
            "service_tier": actual_tier,
        }
        raise


def _raw_response_bytes(raw_response: Any) -> bytes:
    content = getattr(raw_response, "content", None)
    if isinstance(content, bytes):
        return content
    read_fn = getattr(raw_response, "read", None)
    if callable(read_fn):
        data = read_fn()
        if isinstance(data, bytes):
            return data
    http_resp = getattr(raw_response, "http_response", None)
    if http_resp is not None and isinstance(getattr(http_resp, "content", None), bytes):
        return http_resp.content
    return b""


def _accounted_gemini_interaction_create(
    *,
    client: Any,
    accountant: Any,
    purpose: str | None = None,
    attempt: int = 1,
    before_dispatch: Callable[[], float] | None = None,
    **request: Any,
) -> Any:
    try:
        active = _active_accountant(accountant)
        purpose, limits = _dispatch_limits(active, provider="gemini", purpose=purpose, model=request["model"])
        request = _apply_gemini_dispatch_limits(request, active, limits)
        billing_scope = _trusted_gemini_billing_scope(client, limits)
        currency = limits.get("currency", "USD")
        from .semantic_review_billing import GEMINI_MODEL as semantic_model, strict_limits

        strict_semantic = request["model"] == semantic_model and purpose == "semantic_audit" and strict_limits(limits)
        if strict_semantic:
            from .usage_accounting import DispatchAccounting
            from .semantic_review_model_policy import validate_policy, KEY

            if (
                not isinstance(active, DispatchAccounting)
                or billing_scope != "gemini_developer_api"
                or currency != "USD"
            ):
                raise ValueError("Dedicated Gemini semantic review requires its native billing policy.")
            validate_policy(active.run_identity.get(KEY))
            if active.hard_budget:
                raise ValueError("Dedicated semantic review has no verified strict BLOCK reservation envelope.")
            raw_create = getattr(getattr(client.interactions, "with_raw_response", None), "create", None)
            if not callable(raw_create):
                raise ValueError("Dedicated semantic review requires raw SDK response evidence.")
            snapshot = active.pricing_snapshot
            if (
                snapshot is None
                or snapshot.resolve(
                    "gemini",
                    semantic_model,
                    service_tier="default",
                    billing_scope=billing_scope,
                    currency=currency,
                ).status
                != "available"
            ):
                raise ValueError("Dedicated semantic review requires its immutable native price catalog.")
        if active.hard_budget and billing_scope is None:
            raise ValueError("Hard-budget dispatch requires a verified billing endpoint and scope.")
        request_hash, observed = _request_accounting_details(request)
        _validate_dispatch_input_bound(active, limits, observed)
        bounds = {**limits, **observed}
        verifier = getattr(active, "verify_dispatch", None)
        base_url = _extract_gemini_base_url(client)
        effort_label = (request.get("generation_config") or {}).get("thinking_level", "")
        verification = dict(
            request=request,
            route="interactions.create",
            provider="gemini",
            purpose=purpose,
            attempt=attempt,
            requested_service_tier="default",
            base_url=base_url,
            billing_scope=billing_scope,
            currency=currency,
        )
        if callable(verifier):
            verifier(**verification)
        ticket = active.begin(
            provider="gemini",
            requested_model=request["model"],
            effort=effort_label,
            purpose=purpose,
            request_hash=request_hash,
            bounds=bounds,
            attempt=attempt,
            requested_service_tier="default",
            billing_scope=billing_scope,
            currency=currency,
            route="interactions.create",
            base_url=base_url,
        )
    except Exception as exc:
        exc._legalpdf_not_dispatched = True  # type: ignore[attr-defined]
        raise

    if before_dispatch is not None:
        try:
            request["timeout"] = max(0.1, before_dispatch())
        except BaseException as exc:
            active.finish(
                ticket,
                outcome="not_dispatched",
                usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                response_id=None,
                actual_model=request["model"],
                error_code=type(exc).__name__,
            )
            exc._legalpdf_not_dispatched = True  # type: ignore[attr-defined]
            raise

    try:
        rechecker = getattr(active, "recheck_dispatch", None)
        try:
            if (
                _extract_gemini_base_url(client) != verification["base_url"]
                or _trusted_gemini_billing_scope(client, limits) != billing_scope
            ):
                raise ValueError("Provider endpoint changed after reservation.")
            if callable(rechecker):
                rechecker(reservation_id=getattr(ticket, "reservation_id", None), **verification)
        except BaseException as exc:
            active.finish(
                ticket,
                outcome="not_dispatched",
                usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                actual_model=request["model"],
                response_id=None,
                error_code=type(exc).__name__,
            )
            exc._legalpdf_not_dispatched = True  # type: ignore[attr-defined]
            raise

        if strict_semantic:
            raw_response = raw_create(**request)
            response, semantic_response_proof = active.retain_semantic_response(
                ticket,
                _raw_response_bytes(raw_response),
            )
        else:
            response = client.interactions.create(**request)
    except BaseException as exc:
        if getattr(exc, "_legalpdf_not_dispatched", False):
            raise
        evidence = _error_response(exc)
        strict_arguments: dict[str, Any] = {}
        if strict_semantic:
            raw = _raw_response_bytes(getattr(exc, "raw_response", None) or getattr(exc, "response", None))
            if not raw and isinstance(getattr(exc, "body", None), str):
                raw = exc.body.encode("utf-8", errors="ignore")
            evidence, semantic_response_proof = active.retain_semantic_response(ticket, raw)
            strict_arguments = {
                "strict_semantic": True,
                "semantic_response_evidence": semantic_response_proof,
            }
            exc.body = evidence  # type: ignore[attr-defined]
        is_timeout = isinstance(exc, (httpx.TimeoutException, TimeoutError))
        finish = _finish_gemini_attempt(
            active,
            ticket,
            response=evidence,
            outcome="timeout" if is_timeout else "failed",
            error_code=type(exc).__name__,
            billing_scope=billing_scope,
            currency=currency,
            **strict_arguments,
        )
        if strict_semantic and (not isinstance(finish, dict) or finish.get("cost_usd") is None):
            raise _semantic_billing_failure(evidence, request) from exc
        raise

    finish = _finish_gemini_attempt(
        active,
        ticket,
        response=response,
        outcome="refused" if _gemini_has_refusal(response) else "succeeded",
        billing_scope=billing_scope,
        currency=currency,
        **(
            {
                "strict_semantic": True,
                "semantic_response_evidence": semantic_response_proof,
            }
            if strict_semantic
            else {}
        ),
    )
    if strict_semantic and (not isinstance(finish, dict) or finish.get("cost_usd") is None):
        raise _semantic_billing_failure(response, request)
    return response


def _semantic_billing_failure(response: Any, request: dict[str, Any]) -> ApiCallError:
    try:
        output = _extract_gemini_output_text(response)
    except RuntimeError:
        output = None
    return ApiCallError(
        message="Dedicated semantic review billing evidence is unsupported; no further dispatch is allowed.",
        status_code=None,
        exception_class="SemanticReviewBillingError",
        transport_retries_count=0,
        last_backoff_seconds=0.0,
        total_backoff_seconds=0.0,
        rate_limit_hit=False,
        usage=_extract_gemini_usage(response),
        response_id=_field(response, "id"),
        response_status=_field(response, "status") or "",
        refused=_gemini_has_refusal(response),
        incomplete_reason=_gemini_incomplete_reason(response),
        model=_field(response, "model") or "",
        effort=(request.get("generation_config") or {}).get("thinking_level", ""),
        raw_output=output,
    )


def _run_gemini_auth_test_request(
    *,
    client: Any,
    credential_source: OpenAICredentialSourceInfo | None,
    timeout_seconds: float,
    model: str = GEMINI_MODEL,
    accountant: Any | None = None,
) -> TranslationAuthTestResult:
    started = time.perf_counter()
    try:
        _accounted_gemini_interaction_create(
            client=client,
            accountant=accountant or _AUTH_TEST_ACCOUNTING,
            purpose="auth",
            model=model,
            input="Reply exactly with OK.",
            generation_config={"thinking_level": "low", "max_output_tokens": 16},
            store=False,
            timeout=max(5.0, float(timeout_seconds)),
        )
    except Exception as exc:  # noqa: BLE001
        status_code = _status_code_from_exception(exc)
        exception_class = type(exc).__name__
        if is_gemini_auth_failure(
            exception_class=exception_class,
            status_code=status_code,
            message=str(exc),
        ):
            return TranslationAuthTestResult(
                ok=False,
                status="unauthorized",
                message="Gemini authentication failed.",
                credential_source=credential_source,
                status_code=status_code,
                exception_class=exception_class,
            )
        return TranslationAuthTestResult(
            ok=False,
            status="error",
            message=f"Gemini translation auth test failed: {exception_class}.",
            credential_source=credential_source,
            status_code=status_code,
            exception_class=exception_class,
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    return TranslationAuthTestResult(
        ok=True,
        status="ok",
        message="Gemini translation auth test passed.",
        credential_source=credential_source,
        latency_ms=latency_ms,
    )


def run_gemini_auth_test(
    *,
    api_key: str | None = None,
    model: str = GEMINI_MODEL,
    timeout_seconds: float = 20.0,
) -> TranslationAuthTestResult:
    resolved_api_key, credential_source = resolve_gemini_key_with_source(api_key)
    if not resolved_api_key:
        return TranslationAuthTestResult(
            ok=False,
            status="missing",
            message="Gemini translation credentials are not configured.",
            credential_source=None,
        )
    client = genai.Client(
        api_key=resolved_api_key,
        http_options={"retry_options": {"attempts": 1}},
    )
    return _run_gemini_auth_test_request(
        client=client,
        credential_source=credential_source,
        timeout_seconds=timeout_seconds,
        model=model,
    )


class GeminiInteractionsClient:
    provider = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = GEMINI_MODEL,
        max_transport_retries: int = 4,
        base_backoff_seconds: float = 1.0,
        backoff_cap_seconds: float = 12.0,
        pre_call_jitter_seconds: float = 0.8,
        request_timeout_seconds: float = 180.0,
        logger: Callable[[str], None] | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        if not isinstance(model, str) or model not in _GEMINI_MODELS:
            raise ValueError("An explicitly supported Gemini translation model is required.")
        self._model = model
        if sdk_client is None:
            resolved_api_key, credential_source = resolve_gemini_key_with_source(api_key)
            if not resolved_api_key:
                raise ValueError("Gemini API key is not configured.")
            self._client = genai.Client(
                api_key=resolved_api_key,
                http_options={"retry_options": {"attempts": 1}},
            )
            self._credential_source = credential_source
        else:
            self._client = sdk_client
            self._credential_source = OpenAICredentialSourceInfo(kind="injected")
        self._max_transport_retries = max(0, int(max_transport_retries))
        self._base_backoff_seconds = base_backoff_seconds
        self._backoff_cap_seconds = max(1.0, backoff_cap_seconds)
        self._pre_call_jitter_seconds = max(0.0, pre_call_jitter_seconds)
        self._request_timeout_seconds = max(5.0, request_timeout_seconds)
        self._logger = logger
        self._dispatch_accounting = MemoryDispatchAccounting()

    @property
    def model(self) -> str:
        return self._model

    def clone(self, *, logger: Callable[[str], None] | None = None) -> GeminiInteractionsClient:
        cloned = copy(self)
        if logger is not None:
            cloned._logger = logger
        return cloned

    def for_semantic_review(self, *, model: str) -> GeminiInteractionsClient:
        if model not in _GEMINI_MODELS and model != GEMINI_SEMANTIC_REVIEW_MODEL:
            raise ValueError("An approved dedicated Gemini semantic model is required.")
        selected = self.clone()
        selected._model = model
        return selected

    def local_credential_preflight(self) -> TranslationAuthTestResult:
        return TranslationAuthTestResult(
            ok=True,
            status="ok",
            message="Gemini credentials are configured locally; provider authorization is not yet tested.",
            credential_source=self._credential_source,
        )

    def run_translation_auth_test(self, *, timeout_seconds: float = 20.0) -> TranslationAuthTestResult:
        return _run_gemini_auth_test_request(
            client=self._client,
            credential_source=self._credential_source,
            timeout_seconds=timeout_seconds,
            model=self._model,
            accountant=self._dispatch_accounting,
        )

    def prepare_page_request(
        self,
        *,
        instructions: str,
        prompt_text: str,
        effort: str,
        image_data_url: str | None = None,
        image_detail: str = "low",
        image_data_urls: list[str] | tuple[str, ...] | None = None,
        response_format: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
        timeout_seconds: float | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        del timeout_seconds, cancel_check
        request = _build_gemini_page_request(
            instructions=instructions,
            prompt_text=prompt_text,
            effort=effort,
            image_data_url=image_data_url,
            image_detail=image_detail,
            image_data_urls=image_data_urls,
            response_format=response_format,
            max_output_tokens=max_output_tokens,
            model=self.model,
        )
        active = _active_accountant(self._dispatch_accounting)
        _, limits = _dispatch_limits(active, provider="gemini", purpose=None, model=request["model"])
        return _apply_gemini_dispatch_limits(request, active, limits)

    def create_page_response(
        self,
        *,
        instructions: str,
        prompt_text: str,
        effort: str,
        image_data_url: str | None = None,
        image_detail: str = "low",
        image_data_urls: list[str] | tuple[str, ...] | None = None,
        timeout_seconds: float | None = None,
        response_format: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ApiCallResult:
        if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens <= 0):
            raise ValueError("max_output_tokens must be a positive integer.")
        if cancel_check is not None and not callable(cancel_check):
            raise ValueError("cancel_check must be callable.")
        page_request = _build_gemini_page_request(
            instructions=instructions,
            prompt_text=prompt_text,
            effort=effort,
            image_data_url=image_data_url,
            image_detail=image_detail,
            image_data_urls=image_data_urls,
            response_format=response_format,
            max_output_tokens=max_output_tokens,
            model=self.model,
        )

        last_error: Exception | None = None
        transport_retries_count = 0
        last_backoff_seconds = 0.0
        total_backoff_seconds = 0.0
        rate_limit_hit = False
        attempt_usage: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}
        response_id: str | None = None
        response_status = ""
        refused = False
        incomplete_reason: str | None = None
        actual_model = self.model
        retained_output: str | None = None
        overall_timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(self._request_timeout_seconds)
        )
        if not math.isfinite(overall_timeout_seconds) or overall_timeout_seconds <= 0:
            raise ValueError("A positive finite request deadline is required.")
        overall_timeout_seconds = max(0.1, overall_timeout_seconds)
        started_at = time.perf_counter()

        def _remaining_budget_seconds() -> float:
            return max(0.0, overall_timeout_seconds - (time.perf_counter() - started_at))

        def _failure(kind: str, message: str, status_code: int | None = None) -> ApiCallError:
            return ApiCallError(
                message=message,
                status_code=status_code,
                exception_class=kind,
                transport_retries_count=transport_retries_count,
                last_backoff_seconds=last_backoff_seconds,
                total_backoff_seconds=total_backoff_seconds,
                rate_limit_hit=rate_limit_hit,
                usage=dict(usage),
                response_id=response_id,
                response_status=response_status,
                refused=refused,
                incomplete_reason=incomplete_reason,
                model=actual_model,
                effort=effort,
                attempt_usage=deepcopy(attempt_usage),
                raw_output=retained_output,
            )

        def _check_cancel() -> None:
            if cancel_check is not None and cancel_check():
                raise _failure("CancelledError", "Translation request cancelled; no further attempt was dispatched.")

        def _check_deadline() -> float:
            _check_cancel()
            remaining = _remaining_budget_seconds()
            if remaining <= 0:
                raise _failure("APITimeoutError", "Translation request deadline exhausted.")
            return remaining

        def _sleep(seconds: float) -> None:
            if cancel_check is None:
                time.sleep(seconds)
                return
            remaining = seconds
            while remaining > 0:
                _check_cancel()
                step = min(0.1, remaining)
                time.sleep(step)
                remaining -= step
            _check_cancel()

        attempt_limit = self._max_transport_retries + 1
        for attempt in range(attempt_limit):
            remaining_budget = _check_deadline()
            dispatched = False
            recorded = False
            usage, response_id, response_status = {}, None, ""
            refused, incomplete_reason, actual_model = False, None, self.model
            retained_output = None
            try:
                if self._pre_call_jitter_seconds > 0:
                    jitter_seconds = min(random.uniform(0.0, self._pre_call_jitter_seconds), remaining_budget)
                    if jitter_seconds > 0.0:
                        _sleep(jitter_seconds)
                remaining_budget = _check_deadline()
                dispatched = True
                response = _accounted_gemini_interaction_create(
                    client=self._client,
                    accountant=self._dispatch_accounting,
                    attempt=attempt + 1,
                    before_dispatch=_check_deadline,
                    timeout=max(0.1, remaining_budget),
                    **page_request,
                )
                usage = _extract_gemini_usage(response)
                response_id = _field(response, "id")
                actual_model = _field(response, "model") or self.model
                response_status = _field(response, "status") or "completed"
                incomplete_reason = _gemini_incomplete_reason(response)
                refused = _gemini_has_refusal(response)
                attempt_usage.append(
                    {
                        "attempt": attempt + 1,
                        "usage": dict(usage),
                        "response_id": response_id,
                        "model": actual_model,
                        "effort": effort,
                        "status": response_status,
                        "refused": refused,
                        "incomplete_reason": incomplete_reason,
                    }
                )
                recorded = True
                try:
                    retained_output = _extract_gemini_output_text(response)
                except RuntimeError:
                    retained_output = None
                if refused:
                    raise _failure("RefusalResponseError", "The provider refused this response; it was not accepted.")
                if response_status != "completed":
                    raise _failure(
                        "IncompleteResponseError",
                        "The provider response did not complete; partial text was not accepted.",
                    )
                if retained_output is None or not retained_output.strip():
                    raise _failure("EmptyResponseError", "The provider response contained no usable text.")
                _check_cancel()
                return ApiCallResult(
                    raw_output=retained_output,
                    usage=usage,
                    response_id=response_id,
                    transport_retries_count=transport_retries_count,
                    last_backoff_seconds=last_backoff_seconds,
                    total_backoff_seconds=total_backoff_seconds,
                    rate_limit_hit=rate_limit_hit,
                    response_status=response_status,
                    refused=refused,
                    incomplete_reason=incomplete_reason,
                    model=actual_model,
                    effort=effort,
                    attempt_usage=deepcopy(attempt_usage),
                )
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, ApiCallError):
                    raise
                if dispatched and not recorded and not getattr(exc, "_legalpdf_not_dispatched", False):
                    error_response = _error_response(exc)
                    usage = _extract_gemini_usage(error_response) if error_response is not None else {}
                    response_id = _field(error_response, "id")
                    actual_model = _field(error_response, "model") or self.model
                    attempt_usage.append(
                        {
                            "attempt": attempt + 1,
                            "usage": dict(usage),
                            "response_id": response_id,
                            "model": actual_model,
                            "effort": effort,
                            "status": "transport_failed",
                        }
                    )
                last_error = exc
                status_code = _status_code_from_exception(exc)
                if status_code == 429:
                    rate_limit_hit = True
                if not _is_gemini_retryable(exc) or attempt >= attempt_limit - 1:
                    message = (
                        f"{type(exc).__name__}: structured request failed."
                        if response_format is not None
                        else f"{type(exc).__name__}: {exc}"
                    )
                    raise _failure(type(exc).__name__, message, status_code) from exc
                if response_format is not None and status_code != 429:
                    raise _failure(
                        type(exc).__name__,
                        "Structured response transport failed with uncertain completion; no retry dispatched.",
                        status_code,
                    ) from exc
                if not _active_accountant(self._dispatch_accounting).can_retry:
                    raise _failure(
                        type(exc).__name__,
                        "Provider completion is uncertain; the hard-budget hold prevents another attempt.",
                        status_code,
                    ) from exc
                _check_cancel()
                retry_after = _retry_after_seconds(exc)
                sleep_seconds = _compute_sleep_seconds(
                    attempt=attempt,
                    retry_after=retry_after,
                    backoff_cap_seconds=self._backoff_cap_seconds,
                    base_backoff_seconds=self._base_backoff_seconds,
                )
                remaining_budget = _remaining_budget_seconds()
                bounded_sleep = min(sleep_seconds, remaining_budget)
                if bounded_sleep <= 0.0:
                    raise _failure("APITimeoutError", "Translation request deadline exhausted.") from exc
                if self._logger:
                    self._logger(
                        f"Transient Gemini API error ({type(exc).__name__}), retrying in {bounded_sleep:.2f}s "
                        f"within remaining budget {remaining_budget:.2f}s."
                    )
                transport_retries_count += 1
                last_backoff_seconds = bounded_sleep
                total_backoff_seconds += bounded_sleep
                _sleep(bounded_sleep)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unreachable transport retry state.")
