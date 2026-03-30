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
        def __init__(self, api_key: str, max_retries: int = 99) -> None:
            _ = api_key
            assert max_retries == 0
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
        def __init__(self, api_key: str, max_retries: int = 99) -> None:
            _ = api_key
            assert max_retries == 0
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


def test_timeout_budget_is_spent_across_transport_retries(monkeypatch) -> None:
    calls = {"count": 0}
    fake_clock = {"now": 100.0}

    def _perf_counter() -> float:
        return fake_clock["now"]

    def _sleep(seconds: float) -> None:
        fake_clock["now"] += seconds

    def _create_response(**kwargs):  # noqa: ANN003
        _ = kwargs
        calls["count"] += 1
        raise openai_client.APIConnectionError(request=None)

    class _FakeOpenAI:
        def __init__(self, api_key: str, max_retries: int = 99) -> None:
            _ = api_key
            assert max_retries == 0
            self.responses = SimpleNamespace(create=_create_response)

    monkeypatch.setattr(openai_client, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(openai_client.time, "perf_counter", _perf_counter)
    monkeypatch.setattr(openai_client.time, "sleep", _sleep)
    monkeypatch.setattr(openai_client.random, "uniform", lambda _a, _b: 0.0)

    client = OpenAIResponsesClient(
        api_key="test-key",
        max_transport_retries=4,
        base_backoff_seconds=1.0,
        backoff_cap_seconds=12.0,
        pre_call_jitter_seconds=0.0,
        request_timeout_seconds=180.0,
    )

    with pytest.raises(ApiCallError) as exc_info:
        client.create_page_response(
            instructions="instr",
            prompt_text="prompt",
            effort="high",
            timeout_seconds=1.5,
        )

    assert calls["count"] == 2
    assert exc_info.value.exception_class == "APITimeoutError"
    assert exc_info.value.transport_retries_count == 2


def test_translation_auth_test_reports_missing_credentials(monkeypatch) -> None:
    monkeypatch.setattr(openai_client, "get_openai_key", lambda: None)
    monkeypatch.setattr(openai_client, "get_ocr_key", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = openai_client.run_translation_auth_test()

    assert result.ok is False
    assert result.status == "missing"
    assert result.credential_source is None


def test_translation_auth_test_reports_unauthorized(monkeypatch) -> None:
    class AuthenticationError(Exception):
        def __init__(self, message: str) -> None:
            super().__init__(message)
            self.status_code = 401

    def _create_response(**kwargs):  # noqa: ANN003
        _ = kwargs
        raise AuthenticationError("bad key")

    class _FakeOpenAI:
        def __init__(self, api_key: str, max_retries: int = 99) -> None:
            _ = api_key
            assert max_retries == 0
            self.responses = SimpleNamespace(create=_create_response)

    monkeypatch.setattr(openai_client, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(openai_client, "get_openai_key", lambda: "stored-key")
    monkeypatch.setattr(openai_client, "get_ocr_key", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = openai_client.run_translation_auth_test()

    assert result.ok is False
    assert result.status == "unauthorized"
    assert result.status_code == 401
    assert result.exception_class == "AuthenticationError"
    assert result.credential_source is not None
    assert result.credential_source.to_payload() == {"kind": "stored", "name": ""}


def test_translation_auth_test_reports_success(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def _create_response(**kwargs):  # noqa: ANN003
        calls.append(dict(kwargs))
        return SimpleNamespace(id="resp-ok")

    class _FakeOpenAI:
        def __init__(self, api_key: str, max_retries: int = 99) -> None:
            assert api_key == "inline-key"
            assert max_retries == 0
            self.responses = SimpleNamespace(create=_create_response)

    monkeypatch.setattr(openai_client, "OpenAI", _FakeOpenAI)

    result = openai_client.run_translation_auth_test(api_key="inline-key", timeout_seconds=7.0)

    assert result.ok is True
    assert result.status == "ok"
    assert result.credential_source is not None
    assert result.credential_source.to_payload() == {"kind": "inline", "name": ""}
    assert result.latency_ms is not None
    assert calls[0]["timeout"] == 7.0
