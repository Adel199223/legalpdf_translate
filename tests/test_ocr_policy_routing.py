from __future__ import annotations

import pytest

from legalpdf_translate.ocr_engine import ApiOcrEngine, LocalThenApiEngine, OcrEngineConfig, build_ocr_engine
from legalpdf_translate.types import ApiKeySource, OcrEnginePolicy


def test_api_policy_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.API,
        api_model="gpt-4o-mini",
        api_key_source=ApiKeySource.ENV,
        api_key_env="DEEPSEEK_API_KEY",
    )
    with pytest.raises(ValueError, match="OCR engine is set to API"):
        build_ocr_engine(config)


def test_api_policy_with_env_key_builds_api_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.API,
        api_model="gpt-4o-mini",
        api_key_source=ApiKeySource.ENV,
        api_key_env="DEEPSEEK_API_KEY",
    )
    engine = build_ocr_engine(config)
    assert isinstance(engine, ApiOcrEngine)


def test_local_then_api_without_key_disables_api_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL_THEN_API,
        api_model="gpt-4o-mini",
        api_key_source=ApiKeySource.ENV,
        api_key_env="DEEPSEEK_API_KEY",
    )
    engine = build_ocr_engine(config)
    assert isinstance(engine, LocalThenApiEngine)
    assert engine.api_engine is None


def test_local_then_api_with_key_enables_api_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL_THEN_API,
        api_model="gpt-4o-mini",
        api_key_source=ApiKeySource.ENV,
        api_key_env="DEEPSEEK_API_KEY",
    )
    engine = build_ocr_engine(config)
    assert isinstance(engine, LocalThenApiEngine)
    assert engine.api_engine is not None
