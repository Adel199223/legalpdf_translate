from __future__ import annotations

from types import SimpleNamespace

import pytest

import legalpdf_translate.openai_client as openai_client
from legalpdf_translate.openai_client import ApiCallError, OpenAIResponsesClient


def test_zero_retries_still_attempts_once_success(monkeypatch) -> None:
    calls = {"count": 0}

    def _create_response(**kwargs):  # noqa: ANN003
        _ = kwargs
        calls["count"] += 1
        return SimpleNamespace(
            output_text="```ok```",
            usage={"input_tokens": 10, "output_tokens": 4, "total_tokens": 14, "reasoning_tokens": 2},
            id="resp_1",
        )

    class _FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            _ = api_key
            self.responses = SimpleNamespace(create=_create_response)

    monkeypatch.setattr(openai_client, "OpenAI", _FakeOpenAI)

    client = OpenAIResponsesClient(api_key="test-key", max_transport_retries=0, pre_call_jitter_seconds=0.0)
    result = client.create_page_response(
        instructions="instr",
        prompt_text="prompt",
        effort="high",
    )

    assert calls["count"] == 1
    assert result.raw_output == "```ok```"
    assert result.transport_retries_count == 0


def test_zero_retries_failure_raises_apicallerror(monkeypatch) -> None:
    calls = {"count": 0}

    def _create_response(**kwargs):  # noqa: ANN003
        _ = kwargs
        calls["count"] += 1
        raise RuntimeError("boom")

    class _FakeOpenAI:
        def __init__(self, api_key: str) -> None:
            _ = api_key
            self.responses = SimpleNamespace(create=_create_response)

    monkeypatch.setattr(openai_client, "OpenAI", _FakeOpenAI)

    client = OpenAIResponsesClient(api_key="test-key", max_transport_retries=0, pre_call_jitter_seconds=0.0)

    with pytest.raises(ApiCallError) as exc_info:
        client.create_page_response(
            instructions="instr",
            prompt_text="prompt",
            effort="high",
        )

    assert calls["count"] == 1
    assert exc_info.value.transport_retries_count == 0
    assert "RuntimeError" in str(exc_info.value)
