"""OpenAI Responses API wrapper with bounded transport retries."""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from typing import Any, Callable

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from .config import OPENAI_MODEL, OPENAI_STORE


@dataclass(slots=True)
class ApiCallResult:
    raw_output: str
    usage: dict[str, Any]
    response_id: str | None


class OpenAIResponsesClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        max_transport_retries: int = 4,
        base_backoff_seconds: float = 1.0,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        resolved_api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not resolved_api_key:
            raise ValueError("OPENAI_API_KEY is not set.")
        self._client = OpenAI(api_key=resolved_api_key)
        self._max_transport_retries = max_transport_retries
        self._base_backoff_seconds = base_backoff_seconds
        self._logger = logger

    def create_page_response(
        self,
        *,
        instructions: str,
        prompt_text: str,
        effort: str,
        image_data_url: str | None = None,
    ) -> ApiCallResult:
        content: list[dict[str, Any]] = [{"type": "input_text", "text": prompt_text}]
        if image_data_url:
            content.append(
                {
                    "type": "input_image",
                    "image_url": image_data_url,
                    "detail": "high",
                }
            )
        user_input = [{"role": "user", "content": content}]

        last_error: Exception | None = None
        for attempt in range(self._max_transport_retries):
            try:
                response = self._client.responses.create(
                    model=OPENAI_MODEL,
                    instructions=instructions,
                    input=user_input,
                    reasoning={"effort": effort},
                    store=OPENAI_STORE,
                )
                return ApiCallResult(
                    raw_output=_extract_output_text(response),
                    usage=_extract_usage(response),
                    response_id=getattr(response, "id", None),
                )
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if not _is_retryable(exc) or attempt >= self._max_transport_retries - 1:
                    raise
                sleep_seconds = self._base_backoff_seconds * (2**attempt) + random.uniform(0.0, 0.4)
                if self._logger:
                    self._logger(
                        f"Transient API error ({type(exc).__name__}), retrying in {sleep_seconds:.2f}s."
                    )
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
