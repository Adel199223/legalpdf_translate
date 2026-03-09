from __future__ import annotations

import pytest

import legalpdf_translate.ocr_engine as ocr_engine
from legalpdf_translate.ocr_engine import (
    ApiOcrEngine,
    GeminiApiOcrEngine,
    LocalThenApiEngine,
    OcrEngineConfig,
    OcrResult,
    build_ocr_engine,
    test_ocr_provider_connection,
)
from legalpdf_translate.types import OcrApiProvider, OcrEnginePolicy


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


def test_local_then_api_uses_api_only_when_local_is_unusable() -> None:
    class _LocalUnusable:
        def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
            _ = image_bytes, lang_hint
            return OcrResult(
                text="",
                engine="local",
                failed_reason="local OCR result below acceptance threshold (score=0.0500, pass=pass_b_sparse)",
                chars=0,
                quality_score=0.05,
                selected_pass="pass_b_sparse",
                attempts=[],
            )

    class _ApiGood:
        def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
            _ = image_bytes, lang_hint
            return OcrResult(text="api result", engine="api", failed_reason=None, chars=10, quality_score=0.7)

    routed = LocalThenApiEngine(local_engine=_LocalUnusable(), api_engine=_ApiGood())  # type: ignore[arg-type]
    result = routed.ocr_image(b"x", lang_hint="pt_latin_default")
    assert result.engine == "api"
    assert result.chars > 0


def test_api_engine_constructs_openai_with_bounded_retry_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeOpenAI:
        def __init__(self, *, api_key: str, base_url: str | None = None, max_retries: int = 99) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            captured["max_retries"] = max_retries
            self.responses = object()

    monkeypatch.setattr(ocr_engine, "OpenAI", _FakeOpenAI)

    engine = ApiOcrEngine(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        model="gpt-test",
        timeout_seconds=240.0,
    )

    assert captured == {
        "api_key": "test-key",
        "base_url": "https://example.invalid/v1",
        "max_retries": 0,
    }
    assert engine._timeout_seconds == pytest.approx(240.0)

def test_gemini_api_policy_builds_gemini_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_engine, "get_ocr_key", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.API,
        api_provider=OcrApiProvider.GEMINI,
        api_model="gemini-3.1-flash-lite-preview",
        api_key_env_name="GEMINI_API_KEY",
    )
    engine = build_ocr_engine(config)
    assert isinstance(engine, GeminiApiOcrEngine)


def test_local_then_api_with_gemini_key_enables_gemini_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ocr_engine, "get_ocr_key", lambda: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    config = OcrEngineConfig(
        policy=OcrEnginePolicy.LOCAL_THEN_API,
        api_provider=OcrApiProvider.GEMINI,
        api_model="gemini-3-flash-preview",
        api_key_env_name="GEMINI_API_KEY",
    )
    engine = build_ocr_engine(config)
    assert isinstance(engine, LocalThenApiEngine)
    assert isinstance(engine.api_engine, GeminiApiOcrEngine)


def test_test_ocr_provider_connection_uses_gemini_ping(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def _fake_gemini_post_json(*, api_key: str, model: str, base_url: str | None, payload: dict[str, object]):
        captured["api_key"] = api_key
        captured["model"] = model
        captured["base_url"] = base_url
        captured["payload"] = payload
        return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}

    monkeypatch.setattr(ocr_engine, "_gemini_post_json", _fake_gemini_post_json)

    test_ocr_provider_connection(
        OcrEngineConfig(
            policy=OcrEnginePolicy.API,
            api_provider=OcrApiProvider.GEMINI,
            api_model="gemini-3.1-flash-lite-preview",
            api_key_env_name="GEMINI_API_KEY",
        ),
        api_key="gem-key",
    )

    assert captured["api_key"] == "gem-key"
    assert captured["model"] == "gemini-3.1-flash-lite-preview"


def test_gemini_media_resolution_uses_pdf_medium_and_image_high(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_payloads: list[dict[str, object]] = []

    def _fake_gemini_post_json(*, api_key: str, model: str, base_url: str | None, payload: dict[str, object]):
        _ = api_key, model, base_url
        captured_payloads.append(payload)
        return {"candidates": [{"content": {"parts": [{"text": "OK"}]}}]}

    monkeypatch.setattr(ocr_engine, "_gemini_post_json", _fake_gemini_post_json)
    engine = GeminiApiOcrEngine(api_key="gem-key", model="gemini-3.1-flash-lite-preview")

    engine.ocr_image(b"pdf-bytes", lang_hint="PT", source_type="pdf")
    engine.ocr_image(b"img-bytes", lang_hint="PT", source_type="image")

    assert captured_payloads[0]["generationConfig"]["mediaResolution"] == "MEDIUM"
    assert captured_payloads[1]["generationConfig"]["mediaResolution"] == "HIGH"
