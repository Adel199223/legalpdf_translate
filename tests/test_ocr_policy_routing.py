from __future__ import annotations

import pytest

import legalpdf_translate.ocr_engine as ocr_engine
from legalpdf_translate.ocr_engine import ApiOcrEngine, LocalThenApiEngine, OcrEngineConfig, build_ocr_engine
from legalpdf_translate.types import OcrEnginePolicy


def test_api_policy_missing_key_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(ocr_engine, "get_ocr_key", lambda: None)
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.API,
        api_model="gpt-4o-mini",
        api_key_env_name="DEEPSEEK_API_KEY",
    )
    with pytest.raises(ValueError, match="OCR API key is not configured"):
        build_ocr_engine(config)


def test_api_policy_with_env_key_builds_api_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_engine, "get_ocr_key", lambda: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.API,
        api_model="gpt-4o-mini",
        api_key_env_name="DEEPSEEK_API_KEY",
    )
    engine = build_ocr_engine(config)
    assert isinstance(engine, ApiOcrEngine)


def test_local_then_api_without_key_disables_api_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_engine, "get_ocr_key", lambda: None)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL_THEN_API,
        api_model="gpt-4o-mini",
        api_key_env_name="DEEPSEEK_API_KEY",
    )
    engine = build_ocr_engine(config)
    assert isinstance(engine, LocalThenApiEngine)
    assert engine.api_engine is None


def test_local_then_api_with_key_enables_api_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_engine, "get_ocr_key", lambda: None)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL_THEN_API,
        api_model="gpt-4o-mini",
        api_key_env_name="DEEPSEEK_API_KEY",
    )
    engine = build_ocr_engine(config)
    assert isinstance(engine, LocalThenApiEngine)
    assert engine.api_engine is not None


def test_stored_ocr_key_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
    monkeypatch.setattr(ocr_engine, "get_ocr_key", lambda: "stored-key")
    config = OcrEngineConfig(api_key_env_name="DEEPSEEK_API_KEY")
    resolved = ocr_engine._resolve_api_key(config)
    assert resolved == "stored-key"
