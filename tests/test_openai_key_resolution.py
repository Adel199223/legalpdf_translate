from __future__ import annotations

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
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    client = OpenAIResponsesClient()
    assert isinstance(client._client, _DummyOpenAI)  # type: ignore[attr-defined]
    assert client._client.api_key == "stored-key"  # type: ignore[attr-defined]


def test_missing_openai_key_blocks_client_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(openai_client, "get_openai_key", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenAI API key is not configured"):
        OpenAIResponsesClient()
