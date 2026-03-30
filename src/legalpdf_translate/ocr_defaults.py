"""Lightweight OCR provider defaults shared across startup-sensitive modules."""

from __future__ import annotations

from .types import OcrApiProvider

OPENAI_OCR_DEFAULT_ENV = "OPENAI_API_KEY"
OPENAI_OCR_LEGACY_ENV = "DEEPSEEK_API_KEY"
GEMINI_OCR_DEFAULT_ENV = "GEMINI_API_KEY"


def default_ocr_api_env_name(provider: OcrApiProvider) -> str:
    if provider == OcrApiProvider.GEMINI:
        return GEMINI_OCR_DEFAULT_ENV
    return OPENAI_OCR_DEFAULT_ENV
