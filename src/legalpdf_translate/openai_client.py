"""OpenAI Responses API wrapper with bounded transport retries."""

from __future__ import annotations

import math
import os
import random
import time
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

from .config import OPENAI_MODEL, OPENAI_STORE
from .secrets_store import get_ocr_key, get_openai_key


@dataclass(slots=True)
class ApiCallResult:
    raw_output: str
    usage: dict[str, Any]
    response_id: str | None
    transport_retries_count: int = 0
    last_backoff_seconds: float = 0.0
    total_backoff_seconds: float = 0.0
    rate_limit_hit: bool = False
    response_status: str = "completed"
    refused: bool = False
    incomplete_reason: str | None = None
    model: str = ""
    effort: str = ""
    attempt_usage: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class ApiCallError(RuntimeError):
    message: str
    status_code: int | None
    exception_class: str
    transport_retries_count: int
    last_backoff_seconds: float
    total_backoff_seconds: float
    rate_limit_hit: bool
    usage: dict[str, Any] = field(default_factory=dict)
    response_id: str | None = None
    response_status: str = ""
    refused: bool = False
    incomplete_reason: str | None = None
    model: str = ""
    effort: str = ""
    attempt_usage: list[dict[str, Any]] = field(default_factory=list)

    def __str__(self) -> str:
        return self.message


@dataclass(slots=True, frozen=True)
class OpenAICredentialSourceInfo:
    kind: str
    name: str = ""

    def to_payload(self) -> dict[str, str]:
        return {
            "kind": self.kind,
            "name": self.name,
        }


@dataclass(slots=True, frozen=True)
class TranslationAuthTestResult:
    ok: bool
    status: str
    message: str
    credential_source: OpenAICredentialSourceInfo | None
    status_code: int | None = None
    exception_class: str = ""
    latency_ms: int | None = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "message": self.message,
            "credential_source": (
                self.credential_source.to_payload() if self.credential_source is not None else {"kind": "missing", "name": ""}
            ),
            "status_code": self.status_code,
            "exception_class": self.exception_class,
            "latency_ms": self.latency_ms,
        }


def resolve_openai_key_with_source(
    api_key: str | None = None,
) -> tuple[str | None, OpenAICredentialSourceInfo | None]:
    resolved_api_key = (api_key or "").strip() or None
    if resolved_api_key:
        return resolved_api_key, OpenAICredentialSourceInfo(kind="inline", name="")
    try:
        stored_key = get_openai_key()
    except RuntimeError:
        stored_key = None
    if stored_key:
        return stored_key, OpenAICredentialSourceInfo(kind="stored", name="")
    try:
        stored_ocr_key = get_ocr_key()
    except RuntimeError:
        stored_ocr_key = None
    if stored_ocr_key:
        return stored_ocr_key, OpenAICredentialSourceInfo(kind="stored", name="ocr_api_key_fallback")
    env_key = os.getenv("OPENAI_API_KEY", "").strip()
    if env_key:
        return env_key, OpenAICredentialSourceInfo(kind="env", name="OPENAI_API_KEY")
    return None, None


def is_openai_auth_failure(*, exception_class: str, status_code: int | None) -> bool:
    lowered = str(exception_class or "").strip()
    return lowered == "AuthenticationError" or status_code in (401, 403)


def run_translation_auth_test(
    *,
    api_key: str | None = None,
    timeout_seconds: float = 20.0,
) -> TranslationAuthTestResult:
    resolved_api_key, credential_source = resolve_openai_key_with_source(api_key)
    if not resolved_api_key:
        return TranslationAuthTestResult(
            ok=False,
            status="missing",
            message="OpenAI translation credentials are not configured.",
            credential_source=None,
        )

    client = OpenAI(api_key=resolved_api_key, max_retries=0)
    return _run_translation_auth_test_request(
        client=client,
        credential_source=credential_source,
        timeout_seconds=timeout_seconds,
    )


class OpenAIResponsesClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        max_transport_retries: int = 4,
        base_backoff_seconds: float = 1.0,
        backoff_cap_seconds: float = 12.0,
        pre_call_jitter_seconds: float = 0.8,
        request_timeout_seconds: float = 180.0,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        resolved_api_key, credential_source = resolve_openai_key_with_source(api_key)
        if not resolved_api_key:
            raise ValueError("OpenAI API key is not configured.")
        self._client = OpenAI(api_key=resolved_api_key, max_retries=0)
        self._credential_source = credential_source
        self._max_transport_retries = max(0, int(max_transport_retries))
        self._base_backoff_seconds = base_backoff_seconds
        self._backoff_cap_seconds = max(1.0, backoff_cap_seconds)
        self._pre_call_jitter_seconds = max(0.0, pre_call_jitter_seconds)
        self._request_timeout_seconds = max(5.0, request_timeout_seconds)
        self._logger = logger

    def run_translation_auth_test(self, *, timeout_seconds: float = 20.0) -> TranslationAuthTestResult:
        return _run_translation_auth_test_request(
            client=self._client,
            credential_source=self._credential_source,
            timeout_seconds=timeout_seconds,
        )

    def create_page_response(
        self,
        *,
        instructions: str,
        prompt_text: str,
        effort: str,
        image_data_url: str | None = None,
        image_detail: str = "low",
        timeout_seconds: float | None = None,
        response_format: dict[str, Any] | None = None,
        max_output_tokens: int | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> ApiCallResult:
        # Existing callers, including their request shape and retry policy, stay legacy.
        if response_format is None and max_output_tokens is None and cancel_check is None:
            return self._create_legacy_page_response(
                instructions=instructions, prompt_text=prompt_text, effort=effort,
                image_data_url=image_data_url, image_detail=image_detail, timeout_seconds=timeout_seconds,
            )
        if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens <= 0):
            raise ValueError("max_output_tokens must be a positive integer.")
        if cancel_check is not None and not callable(cancel_check):
            raise ValueError("cancel_check must be callable.")
        if response_format is not None and (
            not isinstance(response_format, dict) or response_format.get("type") != "json_schema"
            or response_format.get("strict") is not True or not isinstance(response_format.get("schema"), dict)
            or not isinstance(response_format.get("name"), str) or not response_format["name"]
        ):
            raise ValueError("A strict named JSON-schema response format is required.")
        request_options: dict[str, Any] = {}
        if response_format is not None:
            request_options["text"] = {"format": deepcopy(response_format)}
        if max_output_tokens is not None:
            request_options["max_output_tokens"] = max_output_tokens
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt_text}]
        if image_data_url:
            content.append(
                {
                    "type": "input_image",
                    "image_url": image_data_url,
                    "detail": image_detail,
                }
            )
        user_input = [{"role": "user", "content": content}]

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
        actual_model = OPENAI_MODEL
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
                message=message, status_code=status_code, exception_class=kind,
                transport_retries_count=transport_retries_count, last_backoff_seconds=last_backoff_seconds,
                total_backoff_seconds=total_backoff_seconds, rate_limit_hit=rate_limit_hit,
                usage=dict(usage), response_id=response_id, response_status=response_status,
                refused=refused, incomplete_reason=incomplete_reason, model=actual_model, effort=effort,
                attempt_usage=deepcopy(attempt_usage),
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

        # max_transport_retries is "retries after the first call"; always attempt at least once.
        attempt_limit = self._max_transport_retries + 1
        for attempt in range(attempt_limit):
            remaining_budget = _check_deadline()
            dispatched = False
            recorded = False
            usage, response_id, response_status = {}, None, ""
            refused, incomplete_reason, actual_model = False, None, OPENAI_MODEL
            try:
                if self._pre_call_jitter_seconds > 0:
                    jitter_seconds = min(random.uniform(0.0, self._pre_call_jitter_seconds), remaining_budget)
                    if jitter_seconds > 0.0:
                        _sleep(jitter_seconds)
                remaining_budget = _check_deadline()
                dispatched = True
                response = self._client.responses.create(
                    model=OPENAI_MODEL,
                    instructions=instructions,
                    input=user_input,
                    reasoning={"effort": effort},
                    store=OPENAI_STORE,
                    timeout=max(0.1, remaining_budget),
                    **request_options,
                )
                usage = _extract_usage(response)
                response_id = _field(response, "id")
                actual_model = _field(response, "model") or OPENAI_MODEL
                response_status = _field(response, "status") or ("" if response_format is not None else "completed")
                reason = _field(_field(response, "incomplete_details"), "reason")
                # Preserve only documented content-free status detail, not an arbitrary provider string.
                incomplete_reason = reason if reason in {"max_output_tokens", "content_filter", "steered"} else ("unknown" if reason else None)
                refused = _has_refusal(response)
                attempt_usage.append({
                    "attempt": attempt + 1, "usage": dict(usage), "response_id": response_id,
                    "model": actual_model, "effort": effort, "status": response_status,
                    "refused": refused, "incomplete_reason": incomplete_reason,
                })
                recorded = True
                if refused:
                    raise _failure("RefusalResponseError", "The provider refused this response; it was not accepted.")
                if response_status != "completed" or _has_incomplete_message(response):
                    raise _failure("IncompleteResponseError", "The provider response did not complete; partial text was not accepted.")
                try:
                    output = _extract_output_text(response)
                except RuntimeError:
                    raise _failure("EmptyResponseError", "The provider response contained no usable text.") from None
                if not output.strip():
                    raise _failure("EmptyResponseError", "The provider response contained no usable text.")
                _check_cancel()
                return ApiCallResult(
                    raw_output=output,
                    usage=usage,
                    response_id=response_id,
                    transport_retries_count=transport_retries_count,
                    last_backoff_seconds=last_backoff_seconds,
                    total_backoff_seconds=total_backoff_seconds,
                    rate_limit_hit=rate_limit_hit,
                    response_status=response_status, refused=refused, incomplete_reason=incomplete_reason,
                    model=actual_model, effort=effort, attempt_usage=deepcopy(attempt_usage),
                )
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, ApiCallError):
                    raise
                if dispatched and not recorded:
                    error_response = getattr(exc, "response", None)
                    usage = _extract_usage(error_response) if error_response is not None else {}
                    attempt_usage.append({"attempt": attempt + 1, "usage": dict(usage), "response_id": None,
                                          "model": OPENAI_MODEL, "effort": effort, "status": "transport_failed"})
                last_error = exc
                status_code = _status_code_from_exception(exc)
                if status_code == 429 or isinstance(exc, RateLimitError):
                    rate_limit_hit = True
                if not _is_retryable(exc) or attempt >= attempt_limit - 1:
                    message = (f"{type(exc).__name__}: structured request failed."
                               if response_format is not None else f"{type(exc).__name__}: {exc}")
                    raise _failure(type(exc).__name__, message, status_code) from exc
                # A structured timeout/connection/5xx failure can be billed even
                # without a response. It must not silently authorize another call.
                if response_format is not None and status_code != 429:
                    raise _failure(type(exc).__name__, "Structured response transport failed with uncertain completion; no retry dispatched.", status_code) from exc
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
                        f"Transient API error ({type(exc).__name__}), retrying in {bounded_sleep:.2f}s "
                        f"within remaining budget {remaining_budget:.2f}s."
                    )
                transport_retries_count += 1
                last_backoff_seconds = bounded_sleep
                total_backoff_seconds += bounded_sleep
                _sleep(bounded_sleep)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unreachable transport retry state.")

    def _create_legacy_page_response(
        self,
        *,
        instructions: str,
        prompt_text: str,
        effort: str,
        image_data_url: str | None = None,
        image_detail: str = "low",
        timeout_seconds: float | None = None,
    ) -> ApiCallResult:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt_text}]
        if image_data_url:
            content.append(
                {
                    "type": "input_image",
                    "image_url": image_data_url,
                    "detail": image_detail,
                }
            )
        user_input = [{"role": "user", "content": content}]

        last_error: Exception | None = None
        transport_retries_count = 0
        last_backoff_seconds = 0.0
        total_backoff_seconds = 0.0
        rate_limit_hit = False
        overall_timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(self._request_timeout_seconds)
        )
        overall_timeout_seconds = max(0.1, overall_timeout_seconds)
        started_at = time.perf_counter()

        def _remaining_budget_seconds() -> float:
            return max(0.0, overall_timeout_seconds - (time.perf_counter() - started_at))

        # max_transport_retries is "retries after the first call"; always attempt at least once.
        for attempt in range(self._max_transport_retries + 1):
            remaining_budget = _remaining_budget_seconds()
            if remaining_budget <= 0.0:
                raise _budget_exhausted_error(
                    transport_retries_count=transport_retries_count,
                    last_backoff_seconds=last_backoff_seconds,
                    total_backoff_seconds=total_backoff_seconds,
                    rate_limit_hit=rate_limit_hit,
                    budget_seconds=overall_timeout_seconds,
                )
            try:
                if self._pre_call_jitter_seconds > 0:
                    jitter_seconds = min(random.uniform(0.0, self._pre_call_jitter_seconds), remaining_budget)
                    if jitter_seconds > 0.0:
                        time.sleep(jitter_seconds)
                    remaining_budget = _remaining_budget_seconds()
                    if remaining_budget <= 0.0:
                        raise _budget_exhausted_error(
                            transport_retries_count=transport_retries_count,
                            last_backoff_seconds=last_backoff_seconds,
                            total_backoff_seconds=total_backoff_seconds,
                            rate_limit_hit=rate_limit_hit,
                            budget_seconds=overall_timeout_seconds,
                        )
                response = self._client.responses.create(
                    model=OPENAI_MODEL,
                    instructions=instructions,
                    input=user_input,
                    reasoning={"effort": effort},
                    store=OPENAI_STORE,
                    timeout=max(0.1, remaining_budget),
                )
                return ApiCallResult(
                    raw_output=_extract_output_text(response),
                    usage=_extract_usage(response),
                    response_id=getattr(response, "id", None),
                    transport_retries_count=transport_retries_count,
                    last_backoff_seconds=last_backoff_seconds,
                    total_backoff_seconds=total_backoff_seconds,
                    rate_limit_hit=rate_limit_hit,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                status_code = _status_code_from_exception(exc)
                if status_code == 429 or isinstance(exc, RateLimitError):
                    rate_limit_hit = True
                if not _is_retryable(exc) or attempt >= self._max_transport_retries:
                    raise ApiCallError(
                        message=f"{type(exc).__name__}: {exc}",
                        status_code=status_code,
                        exception_class=type(exc).__name__,
                        transport_retries_count=transport_retries_count,
                        last_backoff_seconds=last_backoff_seconds,
                        total_backoff_seconds=total_backoff_seconds,
                        rate_limit_hit=rate_limit_hit,
                    ) from exc
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
                    raise _budget_exhausted_error(
                        transport_retries_count=transport_retries_count,
                        last_backoff_seconds=last_backoff_seconds,
                        total_backoff_seconds=total_backoff_seconds,
                        rate_limit_hit=rate_limit_hit,
                        budget_seconds=overall_timeout_seconds,
                    ) from exc
                if self._logger:
                    self._logger(
                        f"Transient API error ({type(exc).__name__}), retrying in {bounded_sleep:.2f}s "
                        f"within remaining budget {remaining_budget:.2f}s."
                    )
                transport_retries_count += 1
                last_backoff_seconds = bounded_sleep
                total_backoff_seconds += bounded_sleep
                time.sleep(bounded_sleep)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unreachable transport retry state.")


def _budget_exhausted_error(
    *,
    transport_retries_count: int,
    last_backoff_seconds: float,
    total_backoff_seconds: float,
    rate_limit_hit: bool,
    budget_seconds: float,
) -> ApiCallError:
    return ApiCallError(
        message=(
            "APITimeoutError: request budget exhausted before a successful response "
            f"(budget_seconds={budget_seconds:.3f})"
        ),
        status_code=None,
        exception_class="APITimeoutError",
        transport_retries_count=transport_retries_count,
        last_backoff_seconds=last_backoff_seconds,
        total_backoff_seconds=total_backoff_seconds,
        rate_limit_hit=rate_limit_hit,
    )


def _run_translation_auth_test_request(
    *,
    client: OpenAI,
    credential_source: OpenAICredentialSourceInfo | None,
    timeout_seconds: float,
) -> TranslationAuthTestResult:
    started = time.perf_counter()
    try:
        client.responses.create(
            model=OPENAI_MODEL,
            input=[{"role": "user", "content": [{"type": "input_text", "text": "Reply exactly with OK."}]}],
            max_output_tokens=16,
            store=False,
            timeout=max(5.0, float(timeout_seconds)),
        )
    except Exception as exc:  # noqa: BLE001
        status_code = _status_code_from_exception(exc)
        exception_class = type(exc).__name__
        if is_openai_auth_failure(exception_class=exception_class, status_code=status_code):
            return TranslationAuthTestResult(
                ok=False,
                status="unauthorized",
                message="OpenAI authentication failed.",
                credential_source=credential_source,
                status_code=status_code,
                exception_class=exception_class,
            )
        return TranslationAuthTestResult(
            ok=False,
            status="error",
            message=f"Translation auth test failed: {exception_class}.",
            credential_source=credential_source,
            status_code=status_code,
            exception_class=exception_class,
        )

    latency_ms = int((time.perf_counter() - started) * 1000)
    return TranslationAuthTestResult(
        ok=True,
        status="ok",
        message="OpenAI translation auth test passed.",
        credential_source=credential_source,
        latency_ms=latency_ms,
    )


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, AuthenticationError):
        return False
    if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        return status_code in (429, 500, 502, 503, 504)
    status = getattr(exc, "status_code", None)
    return status in (429, 500, 502, 503, 504)


def _extract_output_text(response: Any) -> str:
    output_text = _field(response, "output_text")
    if isinstance(output_text, str) and output_text != "":
        return output_text

    chunks: list[str] = []
    for output_item in _field(response, "output", []) or []:
        content = getattr(output_item, "content", None)
        if content is None and isinstance(output_item, dict):
            content = output_item.get("content", [])
        for entry in content or []:
            entry_type = getattr(entry, "type", None)
            if entry_type is None and isinstance(entry, dict):
                entry_type = entry.get("type")
            if entry_type not in ("output_text", "text"):
                continue
            text = getattr(entry, "text", None)
            if text is None and isinstance(entry, dict):
                text = entry.get("text")
            if isinstance(text, str):
                chunks.append(text)
    joined = "\n".join(chunks).strip()
    if joined:
        return joined
    raise RuntimeError("Responses API returned no textual output.")


def _extract_usage(response: Any) -> dict[str, Any]:
    usage_obj = _field(response, "usage")
    if usage_obj is None:
        return {}
    usage: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens", "reasoning_tokens"):
        value = getattr(usage_obj, key, None)
        if value is None and isinstance(usage_obj, dict):
            value = usage_obj.get(key)
        if key == "reasoning_tokens" and value is None:
            details_obj = getattr(usage_obj, "output_tokens_details", None)
            if details_obj is None and isinstance(usage_obj, dict):
                details_obj = usage_obj.get("output_tokens_details")
            value = getattr(details_obj, "reasoning_tokens", None)
            if value is None and isinstance(details_obj, dict):
                value = details_obj.get("reasoning_tokens")
        if value is not None:
            usage[key] = value
    input_details = _field(usage_obj, "input_tokens_details")
    cached = _field(input_details, "cached_tokens")
    if cached is not None:
        usage["cached_input_tokens"] = cached
    return usage


def _field(value: Any, name: str, default: Any = None) -> Any:
    return value.get(name, default) if isinstance(value, dict) else getattr(value, name, default)


def _has_refusal(response: Any) -> bool:
    if _field(response, "refusal"):
        return True
    for item in _field(response, "output", []) or []:
        if _field(item, "type") == "refusal":
            return True
        for part in _field(item, "content", []) or []:
            if _field(part, "type") == "refusal":
                return True
    return False


def _has_incomplete_message(response: Any) -> bool:
    return any(_field(item, "type") == "message" and _field(item, "status") not in (None, "completed")
               for item in _field(response, "output", []) or [])


def _retry_after_seconds(exc: Exception) -> float | None:
    headers: Any = None
    response = getattr(exc, "response", None)
    if response is not None:
        headers = getattr(response, "headers", None)
    if headers is None:
        headers = getattr(exc, "headers", None)
    if headers is None:
        return None
    value: str | None = None
    if isinstance(headers, dict):
        for key in ("retry-after", "Retry-After"):
            if key in headers:
                raw = headers.get(key)
                value = str(raw).strip() if raw is not None else None
                break
    else:
        getter = getattr(headers, "get", None)
        if callable(getter):
            raw = getter("retry-after") or getter("Retry-After")
            if raw is not None:
                value = str(raw).strip()
    if not value:
        return None
    try:
        delay = float(value)
        return max(0.0, delay)
    except ValueError:
        pass
    try:
        parsed_dt = parsedate_to_datetime(value)
        now = datetime.now(parsed_dt.tzinfo) if parsed_dt.tzinfo else datetime.utcnow()
        delay = (parsed_dt - now).total_seconds()
        return max(0.0, delay)
    except Exception:
        return None


def _compute_sleep_seconds(
    *,
    attempt: int,
    retry_after: float | None,
    backoff_cap_seconds: float,
    base_backoff_seconds: float,
) -> float:
    if retry_after is not None:
        return min(backoff_cap_seconds, retry_after + random.uniform(0.0, 0.25))
    return min(
        backoff_cap_seconds,
        base_backoff_seconds * (2**attempt) + random.uniform(0.0, 0.4),
    )


def _status_code_from_exception(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status
    response = getattr(exc, "response", None)
    if response is not None:
        response_status = getattr(response, "status_code", None)
        if isinstance(response_status, int):
            return response_status
    return None
