"""OpenAI Responses API wrapper with bounded transport retries."""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from .config import OPENAI_MODEL, OPENAI_STORE
from .secrets_store import get_openai_key


@dataclass(slots=True)
class ApiCallResult:
    raw_output: str
    usage: dict[str, Any]
    response_id: str | None
    transport_retries_count: int = 0
    last_backoff_seconds: float = 0.0
    rate_limit_hit: bool = False


@dataclass(slots=True)
class ApiCallError(RuntimeError):
    message: str
    status_code: int | None
    exception_class: str
    transport_retries_count: int
    last_backoff_seconds: float
    rate_limit_hit: bool

    def __str__(self) -> str:
        return self.message


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
        resolved_api_key = (api_key or "").strip() or None
        if not resolved_api_key:
            try:
                resolved_api_key = get_openai_key()
            except RuntimeError:
                resolved_api_key = None
        if not resolved_api_key:
            env_key = os.getenv("OPENAI_API_KEY", "").strip()
            resolved_api_key = env_key or None
        if not resolved_api_key:
            raise ValueError("OpenAI API key is not configured.")
        self._client = OpenAI(api_key=resolved_api_key)
        self._max_transport_retries = max_transport_retries
        self._base_backoff_seconds = base_backoff_seconds
        self._backoff_cap_seconds = max(1.0, backoff_cap_seconds)
        self._pre_call_jitter_seconds = max(0.0, pre_call_jitter_seconds)
        self._request_timeout_seconds = max(5.0, request_timeout_seconds)
        self._logger = logger

    def create_page_response(
        self,
        *,
        instructions: str,
        prompt_text: str,
        effort: str,
        image_data_url: str | None = None,
        image_detail: str = "high",
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
        rate_limit_hit = False
        for attempt in range(self._max_transport_retries):
            try:
                if self._pre_call_jitter_seconds > 0:
                    time.sleep(random.uniform(0.0, self._pre_call_jitter_seconds))
                response = self._client.responses.create(
                    model=OPENAI_MODEL,
                    instructions=instructions,
                    input=user_input,
                    reasoning={"effort": effort},
                    store=OPENAI_STORE,
                    timeout=max(5.0, timeout_seconds) if timeout_seconds is not None else self._request_timeout_seconds,
                )
                return ApiCallResult(
                    raw_output=_extract_output_text(response),
                    usage=_extract_usage(response),
                    response_id=getattr(response, "id", None),
                    transport_retries_count=transport_retries_count,
                    last_backoff_seconds=last_backoff_seconds,
                    rate_limit_hit=rate_limit_hit,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                status_code = _status_code_from_exception(exc)
                if status_code == 429 or isinstance(exc, RateLimitError):
                    rate_limit_hit = True
                if not _is_retryable(exc) or attempt >= self._max_transport_retries - 1:
                    raise ApiCallError(
                        message=f"{type(exc).__name__}: {exc}",
                        status_code=status_code,
                        exception_class=type(exc).__name__,
                        transport_retries_count=transport_retries_count,
                        last_backoff_seconds=last_backoff_seconds,
                        rate_limit_hit=rate_limit_hit,
                    ) from exc
                retry_after = _retry_after_seconds(exc)
                if retry_after is not None:
                    sleep_seconds = min(self._backoff_cap_seconds, retry_after + random.uniform(0.0, 0.25))
                else:
                    sleep_seconds = min(
                        self._backoff_cap_seconds,
                        self._base_backoff_seconds * (2**attempt) + random.uniform(0.0, 0.4),
                    )
                if self._logger:
                    self._logger(
                        f"Transient API error ({type(exc).__name__}), retrying in {sleep_seconds:.2f}s."
                    )
                transport_retries_count += 1
                last_backoff_seconds = sleep_seconds
                time.sleep(sleep_seconds)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Unreachable transport retry state.")


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (RateLimitError, APITimeoutError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        status_code = getattr(exc, "status_code", None)
        return status_code in (429, 500, 502, 503, 504)
    status = getattr(exc, "status_code", None)
    return status in (429, 500, 502, 503, 504)


def _extract_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text != "":
        return output_text

    chunks: list[str] = []
    for output_item in getattr(response, "output", []) or []:
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
    usage_obj = getattr(response, "usage", None)
    if usage_obj is None:
        return {}
    usage: dict[str, Any] = {}
    for key in ("input_tokens", "output_tokens", "total_tokens", "reasoning_tokens"):
        value = getattr(usage_obj, key, None)
        if value is None and isinstance(usage_obj, dict):
            value = usage_obj.get(key)
        if value is not None:
            usage[key] = value
    return usage


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
