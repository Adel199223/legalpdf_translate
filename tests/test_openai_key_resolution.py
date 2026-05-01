from __future__ import annotations

from types import SimpleNamespace

import pytest

import legalpdf_translate.openai_client as openai_client
from legalpdf_translate.openai_client import OpenAIResponsesClient


class _DummyResponses:
    def create(self, **kwargs: object) -> object:
        raise RuntimeError("not used in this test")


class _DummyOpenAI:
    def __init__(self, *, api_key: str, **_: object) -> None:
        self.api_key = api_key
        self.responses = _DummyResponses()


def test_stored_openai_key_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "OpenAI", _DummyOpenAI)
    monkeypatch.setattr(openai_client, "get_openai_key", lambda: "stored-key")
    monkeypatch.setattr(openai_client, "get_ocr_key", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    client = OpenAIResponsesClient()
    assert isinstance(client._client, _DummyOpenAI)  # type: ignore[attr-defined]
    assert client._client.api_key == "stored-key"  # type: ignore[attr-defined]
    assert client._credential_source is not None  # type: ignore[attr-defined]
    assert client._credential_source.to_payload() == {"kind": "stored", "name": ""}  # type: ignore[attr-defined]


def test_resolve_openai_key_reports_env_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "get_openai_key", lambda: None)
    monkeypatch.setattr(openai_client, "get_ocr_key", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    resolved_key, source = openai_client.resolve_openai_key_with_source()

    assert resolved_key == "env-key"
    assert source is not None
    assert source.to_payload() == {"kind": "env", "name": "OPENAI_API_KEY"}


def test_resolve_openai_key_reports_missing_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "get_openai_key", lambda: None)
    monkeypatch.setattr(openai_client, "get_ocr_key", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    resolved_key, source = openai_client.resolve_openai_key_with_source()

    assert resolved_key is None
    assert source is None


def test_missing_openai_key_blocks_client_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "get_openai_key", lambda: None)
    monkeypatch.setattr(openai_client, "get_ocr_key", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenAI API key is not configured"):
        OpenAIResponsesClient()


def test_resolve_openai_key_uses_stored_ocr_fallback_before_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "get_openai_key", lambda: None)
    monkeypatch.setattr(openai_client, "get_ocr_key", lambda: "stored-ocr-key")
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")

    resolved_key, source = openai_client.resolve_openai_key_with_source()

    assert resolved_key == "stored-ocr-key"
    assert source is not None
    assert source.to_payload() == {"kind": "stored", "name": "ocr_api_key_fallback"}


def test_run_translation_auth_test_uses_openai_minimum_output_tokens(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _FakeResponses:
        def create(self, **kwargs: object) -> object:
            captured.update(kwargs)
            return SimpleNamespace(output_text="OK")

    class _FakeOpenAI:
        def __init__(self, *, api_key: str, **_: object) -> None:
            captured["api_key"] = api_key
            self.responses = _FakeResponses()

    monkeypatch.setattr(openai_client, "OpenAI", _FakeOpenAI)

    result = openai_client.run_translation_auth_test(api_key="inline-key")

    assert result.ok is True
    assert captured["api_key"] == "inline-key"
    assert captured["max_output_tokens"] == 16
