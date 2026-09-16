"""OpenAI Responses API wrapper with bounded transport retries."""

from __future__ import annotations

import math
import hashlib
import json
import os
import random
import time
from copy import copy, deepcopy
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
from .usage_accounting import MemoryDispatchAccounting, current_accounting_binding

_AUTH_TEST_ACCOUNTING = MemoryDispatchAccounting()
_TRANSLATION_MODELS = frozenset({"gpt-5.2", "gpt-5.6-terra", "gpt-5.6-sol"})


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
        model: str = OPENAI_MODEL,
        max_transport_retries: int = 4,
        base_backoff_seconds: float = 1.0,
        backoff_cap_seconds: float = 12.0,
        pre_call_jitter_seconds: float = 0.8,
        request_timeout_seconds: float = 180.0,
        logger: Callable[[str], None] | None = None,
        sdk_client: Any | None = None,
    ) -> None:
        # Explicit selection is per client; ordinary callers retain their default.
        # Reject aliases/typos rather than silently choosing a different model.
        if not isinstance(model, str) or model not in _TRANSLATION_MODELS:
            raise ValueError("An explicitly supported translation model is required.")
        self._model = model
        if sdk_client is None:
            resolved_api_key, credential_source = resolve_openai_key_with_source(api_key)
            if not resolved_api_key:
                raise ValueError("OpenAI API key is not configured.")
            self._client = OpenAI(api_key=resolved_api_key, max_retries=0)
            self._credential_source = credential_source
        else:
            # Injected transports are already configured. Never consult ambient
            # credentials while constructing an isolated caller or its workers.
            with_options = getattr(sdk_client, "with_options", None)
            self._client = with_options(max_retries=0) if callable(with_options) else sdk_client
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
        """The requested translation model, independent of returned snapshots."""
        return self._model

    def clone(self, *, logger: Callable[[str], None] | None = None) -> OpenAIResponsesClient:
        """Keep the exact configured transport and retry policy in worker clients."""
        cloned = copy(self)
        if logger is not None:
            cloned._logger = logger
        return cloned

    def local_credential_preflight(self) -> TranslationAuthTestResult:
        """Check local configuration only; the first work request proves auth."""
        return TranslationAuthTestResult(
            ok=True,
            status="ok",
            message="OpenAI credentials are configured locally; provider authorization is not yet tested.",
            credential_source=self._credential_source,
        )

    def run_translation_auth_test(self, *, timeout_seconds: float = 20.0) -> TranslationAuthTestResult:
        return _run_translation_auth_test_request(
            client=self._client,
            credential_source=self._credential_source,
            timeout_seconds=timeout_seconds,
            accountant=self._dispatch_accounting,
        )

    def prepare_page_request(
        self, *, instructions: str, prompt_text: str, effort: str,
        image_data_url: str | None = None, image_detail: str = "low",
        response_format: dict[str, Any] | None = None, max_output_tokens: int | None = None,
        timeout_seconds: float | None = None, cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, Any]:
        """Pure preparation of the exact bounded request; never dispatch/approve it."""
        request = _build_page_request(instructions=instructions, prompt_text=prompt_text,
            effort=effort, image_data_url=image_data_url, image_detail=image_detail,
            response_format=response_format, max_output_tokens=max_output_tokens, model=self.model)
        active = _active_accountant(self._dispatch_accounting)
        _, limits = _dispatch_limits(active, provider="openai", purpose=None, model=request["model"])
        return _apply_openai_dispatch_limits(request, active, limits)

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
        page_request = _build_page_request(instructions=instructions, prompt_text=prompt_text,
            effort=effort, image_data_url=image_data_url, image_detail=image_detail,
            response_format=response_format, max_output_tokens=max_output_tokens, model=self.model)

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
            refused, incomplete_reason, actual_model = False, None, self.model
            try:
                if self._pre_call_jitter_seconds > 0:
                    jitter_seconds = min(random.uniform(0.0, self._pre_call_jitter_seconds), remaining_budget)
                    if jitter_seconds > 0.0:
                        _sleep(jitter_seconds)
                remaining_budget = _check_deadline()
                dispatched = True
                response = _accounted_openai_create(
                    client=self._client, accountant=self._dispatch_accounting,
                    attempt=attempt + 1,
                    before_dispatch=_check_deadline,
                    timeout=max(0.1, remaining_budget),
                    **page_request,
                )
                usage = _extract_usage(response)
                response_id = _field(response, "id")
                actual_model = _field(response, "model") or self.model
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
                if dispatched and not recorded and not getattr(exc, "_legalpdf_not_dispatched", False):
                    error_response = _error_response(exc)
                    usage = _extract_usage(error_response) if error_response is not None else {}
                    response_id = _field(error_response, "id")
                    actual_model = _field(error_response, "model") or self.model
                    attempt_usage.append({"attempt": attempt + 1, "usage": dict(usage), "response_id": response_id,
                                          "model": actual_model, "effort": effort, "status": "transport_failed"})
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
                if not _active_accountant(self._dispatch_accounting).can_retry:
                    raise _failure(type(exc).__name__, "Provider completion is uncertain; the hard-budget hold prevents another attempt.", status_code) from exc
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
        attempt_usage: list[dict[str, Any]] = []
        usage: dict[str, Any] = {}
        response_id: str | None = None
        actual_model = self.model
        overall_timeout_seconds = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(self._request_timeout_seconds)
        )
        overall_timeout_seconds = max(0.1, overall_timeout_seconds)
        started_at = time.perf_counter()

        def _remaining_budget_seconds() -> float:
            return max(0.0, overall_timeout_seconds - (time.perf_counter() - started_at))

        def _before_dispatch() -> float:
            remaining = _remaining_budget_seconds()
            if remaining <= 0.0:
                raise _budget_exhausted_error(
                    transport_retries_count=transport_retries_count,
                    last_backoff_seconds=last_backoff_seconds,
                    total_backoff_seconds=total_backoff_seconds,
                    rate_limit_hit=rate_limit_hit, budget_seconds=overall_timeout_seconds,
                    attempt_usage=attempt_usage, model=self.model, effort=effort,
                )
            return remaining

        # max_transport_retries is "retries after the first call"; always attempt at least once.
        for attempt in range(self._max_transport_retries + 1):
            response = None
            dispatched = False
            remaining_budget = _remaining_budget_seconds()
            if remaining_budget <= 0.0:
                raise _budget_exhausted_error(
                    transport_retries_count=transport_retries_count,
                    last_backoff_seconds=last_backoff_seconds,
                    total_backoff_seconds=total_backoff_seconds,
                    rate_limit_hit=rate_limit_hit,
                    budget_seconds=overall_timeout_seconds,
                    attempt_usage=attempt_usage, model=self.model, effort=effort,
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
                            attempt_usage=attempt_usage, model=self.model, effort=effort,
                        )
                dispatched = True
                response = _accounted_openai_create(
                    client=self._client, accountant=self._dispatch_accounting,
                    attempt=attempt + 1,
                    before_dispatch=_before_dispatch,
                    model=self.model,
                    instructions=instructions,
                    input=user_input,
                    reasoning={"effort": effort},
                    store=OPENAI_STORE,
                    timeout=max(0.1, remaining_budget),
                )
                usage = _extract_usage(response)
                response_id = _field(response, "id")
                actual_model = _field(response, "model") or self.model
                output = _extract_output_text(response)
                attempt_usage.append({"attempt": attempt + 1, "usage": dict(usage), "response_id": response_id,
                                      "model": actual_model, "effort": effort, "status": "completed"})
                return ApiCallResult(
                    raw_output=output,
                    usage=usage,
                    response_id=response_id,
                    transport_retries_count=transport_retries_count,
                    last_backoff_seconds=last_backoff_seconds,
                    total_backoff_seconds=total_backoff_seconds,
                    rate_limit_hit=rate_limit_hit,
                    model=actual_model, effort=effort, attempt_usage=deepcopy(attempt_usage),
                )
            except Exception as exc:  # noqa: BLE001
                if dispatched and not getattr(exc, "_legalpdf_not_dispatched", False):
                    evidence = response if response is not None else _error_response(exc)
                    usage = _extract_usage(evidence)
                    response_id = _field(evidence, "id")
                    actual_model = _field(evidence, "model") or self.model
                    attempt_usage.append({"attempt": attempt + 1, "usage": dict(usage), "response_id": response_id,
                                          "model": actual_model, "effort": effort, "status": "transport_failed"})
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
                        usage=usage, response_id=response_id, model=actual_model, effort=effort,
                        attempt_usage=deepcopy(attempt_usage),
                    ) from exc
                if not _active_accountant(self._dispatch_accounting).can_retry:
                    raise ApiCallError(
                        message="Provider completion is uncertain; the hard-budget hold prevents another attempt.",
                        status_code=status_code, exception_class=type(exc).__name__,
                        transport_retries_count=transport_retries_count,
                        last_backoff_seconds=last_backoff_seconds,
                        total_backoff_seconds=total_backoff_seconds, rate_limit_hit=rate_limit_hit,
                        usage=usage, response_id=response_id, model=actual_model, effort=effort,
                        attempt_usage=deepcopy(attempt_usage),
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
                        attempt_usage=attempt_usage, model=self.model, effort=effort,
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
    attempt_usage: list[dict[str, Any]] | None = None,
    model: str = "",
    effort: str = "",
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
        attempt_usage=deepcopy(attempt_usage or []),
        model=model, effort=effort,
    )


def _run_translation_auth_test_request(
    *,
    client: OpenAI,
    credential_source: OpenAICredentialSourceInfo | None,
    timeout_seconds: float,
    accountant: Any | None = None,
) -> TranslationAuthTestResult:
    started = time.perf_counter()
    try:
        _accounted_openai_create(
            client=client, accountant=accountant or _AUTH_TEST_ACCOUNTING, purpose="auth",
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


def _build_page_request(*, instructions: str, prompt_text: str, effort: str,
                        image_data_url: str | None = None, image_detail: str = "low",
                        response_format: dict[str, Any] | None = None,
                        max_output_tokens: int | None = None,
                        model: str = OPENAI_MODEL) -> dict[str, Any]:
    if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens <= 0):
        raise ValueError("max_output_tokens must be a positive integer.")
    if response_format is not None and (
        not isinstance(response_format, dict) or response_format.get("type") != "json_schema"
        or response_format.get("strict") is not True or not isinstance(response_format.get("schema"), dict)
        or not isinstance(response_format.get("name"), str) or not response_format["name"]
    ):
        raise ValueError("A strict named JSON-schema response format is required.")
    content = [{"type": "input_text", "text": prompt_text}]
    if image_data_url:
        content.append({"type": "input_image", "image_url": image_data_url, "detail": image_detail})
    request = {"model": model, "instructions": instructions,
               "input": [{"role": "user", "content": content}],
               "reasoning": {"effort": effort}, "store": OPENAI_STORE}
    if response_format is not None:
        request["text"] = {"format": deepcopy(response_format)}
    if max_output_tokens is not None:
        request["max_output_tokens"] = max_output_tokens
    return request


def _apply_openai_dispatch_limits(request: dict[str, Any], accountant: Any,
                                  limits: dict[str, Any]) -> dict[str, Any]:
    request = deepcopy(request)
    maximum = limits.get("max_output_tokens")
    if maximum is not None and (accountant.hard_budget or not limits.get("apply_output_bound_only_when_hard")):
        if type(maximum) is not int or maximum <= 0:
            raise ValueError("Dispatch output token bound must be a positive integer.")
        request["max_output_tokens"] = min(maximum, request.get("max_output_tokens", maximum))
    tier = limits.get("requested_service_tier")
    if tier is not None and tier != "auto":
        if request.get("service_tier", tier) != tier:
            raise ValueError("Request service tier conflicts with its approved policy.")
        request["service_tier"] = tier
    return request


def _trusted_billing_scope(client: Any, limits: dict[str, Any]) -> str | None:
    scope = limits.get("billing_scope")
    allowed = limits.get("allowed_base_urls")
    actual = str(getattr(client, "base_url", "")).rstrip("/")
    if not isinstance(scope, str) or not isinstance(allowed, (list, tuple)):
        return None
    return scope if actual in [str(value).rstrip("/") for value in allowed] else None


def _request_accounting_details(request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Retain request identity and size limits, never request content."""
    stable = {key: value for key, value in request.items() if key != "timeout"}
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    image_count = sum(
        1 for message in request.get("input", []) if isinstance(message, dict)
        for part in message.get("content", []) if isinstance(part, dict) and part.get("type") == "input_image"
    )
    text_request = deepcopy(stable)
    for message in text_request.get("input", []):
        if isinstance(message, dict):
            for part in message.get("content", []):
                if isinstance(part, dict) and part.get("type") == "input_image":
                    part.pop("image_url", None)
    # A UTF-8 byte upper bound avoids assuming a tokenizer version. Framing
    # allowance is deliberately explicit and is included in the reserved bound.
    input_bytes = len(json.dumps(text_request, sort_keys=True, ensure_ascii=False).encode("utf-8")) + 64
    bounds = {"input_bytes": input_bytes, "image_count": image_count}
    if request.get("max_output_tokens") is not None:
        bounds["max_output_tokens"] = request["max_output_tokens"]
    return hashlib.sha256(encoded).hexdigest(), bounds


def _active_accountant(fallback: Any) -> Any:
    binding = current_accounting_binding()
    return binding.accountant if binding is not None else fallback


def _dispatch_limits(accountant: Any, *, provider: str, purpose: str | None, model: str) -> tuple[str, dict[str, Any]]:
    binding = current_accounting_binding()
    resolved_purpose = purpose or (binding.purpose if binding is not None else None) or "translation"
    limits = dict(accountant.request_limits(provider, resolved_purpose, model))
    return resolved_purpose, limits


def _validate_dispatch_input_bound(accountant: Any, limits: dict[str, Any], observed: dict[str, Any]) -> None:
    if not accountant.hard_budget:
        return
    maximum = limits.get("max_input_tokens")
    if type(maximum) is not int or maximum <= 0:
        raise ValueError("Hard-budget dispatch requires a positive input token bound.")
    input_bound = observed["input_bytes"]
    if observed["image_count"]:
        image_bound = limits.get("max_image_input_tokens")
        maximum_images = limits.get("max_image_count")
        if (limits.get("image_bound_verified") is not True or type(image_bound) is not int or image_bound <= 0
                or type(maximum_images) is not int or maximum_images < observed["image_count"]):
            raise ValueError("Hard-budget image dispatch requires a verified image token upper bound.")
        input_bound += image_bound
    if input_bound > maximum:
        raise ValueError("Request exceeds its reserved input token upper bound.")


def _error_response(exc: BaseException) -> Any:
    """SDK status errors expose parsed API evidence in body, not HTTP headers."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        return body
    response = getattr(exc, "response", None)
    if response is not None and _field(response, "usage") is not None:
        return response
    return None


def _finish_openai_attempt(accountant: Any, ticket: Any, *, response: Any, outcome: str,
                           error_code: str | None = None, billing_scope: str | None = None,
                           currency: str = "USD") -> None:
    usage = _extract_usage(response)
    response_id, actual_model = _field(response, "id"), _field(response, "model")
    try:
        accountant.finish(ticket, outcome=outcome, usage=usage, response_id=response_id,
                          actual_model=actual_model, error_code=error_code,
                          actual_service_tier=_field(response, "service_tier"),
                          actual_billing_scope=billing_scope, currency=currency)
    except Exception as exc:
        # Accounting storage failure must not discard the response's billed
        # usage from the app error. Retain only content-free response evidence.
        exc.body = {"usage": usage, "id": response_id, "model": actual_model,
                    "service_tier": _field(response, "service_tier")}  # type: ignore[attr-defined]
        raise


def _accounted_openai_create(
    *, client: Any, accountant: Any, purpose: str | None = None, attempt: int = 1,
    before_dispatch: Callable[[], float] | None = None,
    **request: Any,
) -> Any:
    """One begin/finish pair surrounds exactly one SDK transport attempt."""
    try:
        active = _active_accountant(accountant)
        purpose, limits = _dispatch_limits(active, provider="openai", purpose=purpose, model=request["model"])
        request = _apply_openai_dispatch_limits(request, active, limits)
        billing_scope = _trusted_billing_scope(client, limits)
        currency = limits.get("currency", "USD")
        if active.hard_budget and billing_scope is None:
            raise ValueError("Hard-budget dispatch requires a verified billing endpoint and scope.")
        request_hash, observed = _request_accounting_details(request)
        _validate_dispatch_input_bound(active, limits, observed)
        bounds = {**limits, **observed}
        verifier = getattr(active, "verify_dispatch", None)
        verification = dict(request=request, route="responses.create", provider="openai",
            purpose=purpose, attempt=attempt, requested_service_tier=request.get("service_tier", "auto"),
            base_url=str(getattr(client, "base_url", "")).rstrip("/"),
            billing_scope=billing_scope, currency=currency)
        if callable(verifier):
            verifier(**verification)
        ticket = active.begin(
            provider="openai", requested_model=request["model"],
            effort=request.get("reasoning", {}).get("effort", ""), purpose=purpose,
            request_hash=request_hash, bounds=bounds, attempt=attempt,
            requested_service_tier=request.get("service_tier", "auto"),
            billing_scope=billing_scope, currency=currency, route="responses.create",
            base_url=verification["base_url"],
        )
    except Exception as exc:
        exc._legalpdf_not_dispatched = True  # type: ignore[attr-defined]
        raise
    if before_dispatch is not None:
        try:
            request["timeout"] = max(0.1, before_dispatch())
        except BaseException as exc:
            active.finish(ticket, outcome="not_dispatched",
                          usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                          response_id=None, actual_model=request["model"], error_code=type(exc).__name__)
            exc._legalpdf_not_dispatched = True  # type: ignore[attr-defined]
            raise
    try:
        # Recheck physical provenance after the deadline/cancellation callback;
        # no user-controlled hook may alter approved bytes between check and send.
        rechecker = getattr(active, "recheck_dispatch", None)
        try:
            if (str(getattr(client, "base_url", "")).rstrip("/") != verification["base_url"]
                    or _trusted_billing_scope(client, limits) != billing_scope):
                raise ValueError("Provider endpoint changed after reservation.")
            if callable(rechecker):
                rechecker(reservation_id=getattr(ticket, "reservation_id", None), **verification)
        except BaseException as exc:
            active.finish(ticket, outcome="not_dispatched",
                usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                actual_model=request["model"], response_id=None, error_code=type(exc).__name__)
            exc._legalpdf_not_dispatched = True  # type: ignore[attr-defined]
            raise
        response = client.responses.create(**request)
    except BaseException as exc:
        if getattr(exc, "_legalpdf_not_dispatched", False):
            raise
        evidence = _error_response(exc)
        _finish_openai_attempt(active, ticket, response=evidence,
            outcome="timeout" if isinstance(exc, APITimeoutError) else "failed", error_code=type(exc).__name__,
            billing_scope=billing_scope, currency=currency)
        raise
    _finish_openai_attempt(active, ticket, response=response,
                          outcome="refused" if _has_refusal(response) else "succeeded",
                          billing_scope=billing_scope, currency=currency)
    return response


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
    for key in ("input_tokens", "output_tokens", "total_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_tokens"):
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
    if cached is not None and "cached_input_tokens" not in usage:
        usage["cached_input_tokens"] = cached
    cache_write = _field(input_details, "cache_write_tokens")
    if cache_write is not None and "cache_write_tokens" not in usage:
        usage["cache_write_tokens"] = cache_write
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
