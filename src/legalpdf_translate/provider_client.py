"""Unified translation provider dispatch across Gemini and OpenAI."""

from __future__ import annotations

from typing import Any, Callable

from .config import DEFAULT_TRANSLATION_PROVIDER, GEMINI_MODEL, OPENAI_MODEL
from .gemini_client import (
    GeminiInteractionsClient,
    is_gemini_auth_failure,
    resolve_gemini_key_with_source,
    run_gemini_auth_test,
)
from .openai_client import (
    OpenAIResponsesClient,
    OpenAICredentialSourceInfo,
    TranslationAuthTestResult,
    is_openai_auth_failure,
    resolve_openai_key_with_source,
    run_translation_auth_test,
)
from .types import TranslationApiProvider

TranslationClient = OpenAIResponsesClient | GeminiInteractionsClient


def normalize_translation_provider(
    value: object,
    default: TranslationApiProvider = TranslationApiProvider(DEFAULT_TRANSLATION_PROVIDER),
) -> TranslationApiProvider:
    if isinstance(value, TranslationApiProvider):
        return value
    cleaned = str(value or "").strip().lower()
    if cleaned == TranslationApiProvider.GEMINI.value:
        return TranslationApiProvider.GEMINI
    if cleaned == TranslationApiProvider.OPENAI.value:
        return TranslationApiProvider.OPENAI
    return default


def default_translation_model(provider: TranslationApiProvider | str) -> str:
    resolved = normalize_translation_provider(provider)
    return GEMINI_MODEL if resolved == TranslationApiProvider.GEMINI else OPENAI_MODEL


def provider_display_name(provider: TranslationApiProvider | str) -> str:
    resolved = normalize_translation_provider(provider)
    return "Gemini" if resolved == TranslationApiProvider.GEMINI else "OpenAI"


def is_translation_client(client: Any) -> bool:
    return isinstance(client, (OpenAIResponsesClient, GeminiInteractionsClient))


def client_provider(client: Any) -> str:
    if isinstance(client, GeminiInteractionsClient):
        return TranslationApiProvider.GEMINI.value
    if isinstance(client, OpenAIResponsesClient):
        return TranslationApiProvider.OPENAI.value
    explicit = str(getattr(client, "provider", "") or "").strip().lower()
    if explicit in {"gemini", "openai"}:
        return explicit
    model = str(getattr(client, "model", "") or "").strip().lower()
    if model.startswith("gemini-"):
        return TranslationApiProvider.GEMINI.value
    return TranslationApiProvider.OPENAI.value


def create_translation_client(
    *,
    provider: TranslationApiProvider | str | None = None,
    model: str | None = None,
    api_key: str | None = None,
    max_transport_retries: int = 4,
    backoff_cap_seconds: float = 12.0,
    request_timeout_seconds: float = 180.0,
    logger: Callable[[str], None] | None = None,
) -> TranslationClient:
    resolved_provider = normalize_translation_provider(provider)
    resolved_model = (model or "").strip() or default_translation_model(resolved_provider)
    if resolved_provider == TranslationApiProvider.GEMINI:
        return GeminiInteractionsClient(
            api_key=api_key,
            model=resolved_model,
            max_transport_retries=max_transport_retries,
            backoff_cap_seconds=backoff_cap_seconds,
            request_timeout_seconds=request_timeout_seconds,
            logger=logger,
        )
    return OpenAIResponsesClient(
        api_key=api_key,
        model=resolved_model,
        max_transport_retries=max_transport_retries,
        backoff_cap_seconds=backoff_cap_seconds,
        request_timeout_seconds=request_timeout_seconds,
        logger=logger,
    )


def resolve_translation_key_with_source(
    provider: TranslationApiProvider | str | None = None,
    api_key: str | None = None,
    *,
    allow_gemini_ocr_fallback: bool = False,
) -> tuple[str | None, OpenAICredentialSourceInfo | None]:
    resolved_provider = normalize_translation_provider(provider)
    if resolved_provider == TranslationApiProvider.GEMINI:
        return resolve_gemini_key_with_source(api_key, allow_ocr_fallback=allow_gemini_ocr_fallback)
    return resolve_openai_key_with_source(api_key)


def run_provider_auth_test(
    provider: TranslationApiProvider | str | None = None,
    *,
    api_key: str | None = None,
    model: str | None = None,
    timeout_seconds: float = 20.0,
) -> TranslationAuthTestResult:
    resolved_provider = normalize_translation_provider(provider)
    if resolved_provider == TranslationApiProvider.GEMINI:
        return run_gemini_auth_test(
            api_key=api_key,
            model=(model or "").strip() or GEMINI_MODEL,
            timeout_seconds=timeout_seconds,
        )
    return run_translation_auth_test(
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )


def is_provider_auth_failure(
    provider: TranslationApiProvider | str | None = None,
    *,
    exception_class: str,
    status_code: int | None,
    message: str = "",
) -> bool:
    if is_openai_auth_failure(exception_class=exception_class, status_code=status_code):
        return True
    if provider is None or normalize_translation_provider(provider) == TranslationApiProvider.GEMINI:
        return is_gemini_auth_failure(
            exception_class=exception_class,
            status_code=status_code,
            message=message,
        )
    return False
