"""Synthetic-only coverage for explicit translation model selection."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

import legalpdf_translate.openai_client as module
from legalpdf_translate.openai_client import ApiCallError, OpenAIResponsesClient


MODELS = ("gpt-5.2", "gpt-5.6-terra", "gpt-5.6-sol")
REQUEST = {"instructions": "synthetic instructions", "prompt_text": "synthetic source", "effort": "high"}
FORMAT = {"type": "json_schema", "name": "synthetic", "strict": True, "schema": {"type": "object"}}


def _forbidden(*args, **kwargs):
    raise AssertionError("Real provider construction or ambient credential access is forbidden.")


@pytest.fixture(autouse=True)
def _block_ambient_provider_and_credentials(monkeypatch):
    monkeypatch.setattr(module, "OpenAI", _forbidden)
    monkeypatch.setattr(module, "resolve_openai_key_with_source", _forbidden)


def _response(**overrides):
    return {"id": "synthetic-response", "status": "completed", "output_text": "synthetic output",
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}, **overrides}


def _client(*, response=None, error=None, **options):
    calls = []

    def create(**request):
        calls.append(deepcopy(request))
        if error is not None:
            raise error
        return _response() if response is None else response

    sdk = SimpleNamespace(responses=SimpleNamespace(create=create))
    client = OpenAIResponsesClient(sdk_client=sdk, pre_call_jitter_seconds=0,
                                   max_transport_retries=0, **options)
    return client, calls


@pytest.mark.parametrize("structured", [False, True])
def test_omitted_model_keeps_ordinary_translation_default(structured):
    client, calls = _client()
    extra = {"response_format": FORMAT} if structured else {}
    prepared = client.prepare_page_request(**REQUEST, **extra)
    result = client.create_page_response(**REQUEST, **extra)
    assert client.model == prepared["model"] == calls[0]["model"] == module.OPENAI_MODEL == "gpt-5.2"
    assert result.model == "gpt-5.2"


@pytest.mark.parametrize("selected", MODELS)
@pytest.mark.parametrize("structured", [False, True])
def test_prepared_and_actual_translation_request_match_selected_model(selected, structured):
    client, calls = _client(model=selected)
    extra = {"response_format": FORMAT, "max_output_tokens": 512} if structured else {}
    prepared = client.prepare_page_request(**REQUEST, **extra)
    assert calls == []
    result = client.create_page_response(**REQUEST, **extra)
    assert len(calls) == 1
    actual = {key: value for key, value in calls[0].items() if key != "timeout"}
    assert actual == prepared
    assert actual["model"] == result.model == selected
    assert actual["reasoning"] == {"effort": "high"}
    assert result.attempt_usage[0]["model"] == selected
    assert result.attempt_usage[0]["effort"] == "high"


@pytest.mark.parametrize("selected", MODELS)
def test_model_selection_survives_clone_without_reconfiguration(selected):
    calls, options = [], []
    configured = SimpleNamespace(responses=SimpleNamespace(create=lambda **kw: calls.append(kw) or _response()))
    sdk = SimpleNamespace(with_options=lambda **kw: options.append(kw) or configured)
    client = OpenAIResponsesClient(sdk_client=sdk, model=selected, max_transport_retries=2,
                                   pre_call_jitter_seconds=0, request_timeout_seconds=42)
    worker_logger = lambda _message: None
    worker = client.clone(logger=worker_logger)
    assert options == [{"max_retries": 0}]
    assert worker is not client and worker._client is client._client is configured
    assert worker.model == client.model == selected
    assert worker._max_transport_retries == 2 and worker._request_timeout_seconds == 42
    assert worker._logger is worker_logger and client._logger is None
    assert worker.local_credential_preflight().ok
    worker.create_page_response(**REQUEST, response_format=FORMAT)
    assert calls[0]["model"] == selected
    with pytest.raises(AttributeError):
        worker.model = "gpt-5.2"


@pytest.mark.parametrize("invalid", [None, "", " ", "gpt-5.6", "terra", "GPT-5.6-TERRA",
                                    "gpt-5.6-terra ", "gpt-5.6-terra\n", "other-model", [], {}, 5, True])
def test_invalid_or_ambiguous_selection_rejected_before_sdk_or_credentials(invalid):
    with pytest.raises(ValueError, match="supported translation model"):
        OpenAIResponsesClient(model=invalid)
    sdk = SimpleNamespace(with_options=_forbidden)
    with pytest.raises(ValueError, match="supported translation model"):
        OpenAIResponsesClient(model=invalid, sdk_client=sdk)


@pytest.mark.parametrize("returned", [None, "", "gpt-5.6-terra-2026-09-01"])
@pytest.mark.parametrize("structured", [False, True])
def test_actual_returned_model_is_preserved_otherwise_selected_model_is_fallback(returned, structured):
    client, _calls = _client(model="gpt-5.6-terra", response=_response(model=returned))
    extra = {"response_format": FORMAT} if structured else {}
    result = client.create_page_response(**REQUEST, **extra)
    assert result.model == (returned or "gpt-5.6-terra")
    assert result.attempt_usage[0]["model"] == result.model
    assert client.model == "gpt-5.6-terra"


@pytest.mark.parametrize("structured", [False, True])
@pytest.mark.parametrize("returned", [None, "gpt-5.6-terra-2026-09-01"])
def test_failed_transport_preserves_returned_model_or_selected_fallback(structured, returned):
    error = RuntimeError("synthetic transport failure")
    error.body = {"id": "synthetic-failure", "usage": {"input_tokens": 1}, "model": returned}
    client, calls = _client(model="gpt-5.6-terra", error=error)
    extra = {"response_format": FORMAT} if structured else {}
    with pytest.raises(ApiCallError) as captured:
        client.create_page_response(**REQUEST, **extra)
    assert len(calls) == 1
    assert captured.value.model == (returned or "gpt-5.6-terra")
    assert captured.value.attempt_usage[0]["model"] == captured.value.model
    assert captured.value.effort == "high"


def test_cancel_before_dispatch_reports_selected_model_without_attempt():
    client, calls = _client(model="gpt-5.6-terra")
    with pytest.raises(ApiCallError) as captured:
        client.create_page_response(**REQUEST, response_format=FORMAT, cancel_check=lambda: True)
    assert captured.value.model == "gpt-5.6-terra" and captured.value.effort == "high"
    assert captured.value.attempt_usage == [] and calls == []


def test_legacy_expired_deadline_reports_selected_model_without_attempt(monkeypatch):
    client, calls = _client(model="gpt-5.6-terra")
    times = iter((0.0, 1.0))
    monkeypatch.setattr(module.time, "perf_counter", lambda: next(times))
    with pytest.raises(ApiCallError) as captured:
        client.create_page_response(**REQUEST, timeout_seconds=0.1)
    assert captured.value.model == "gpt-5.6-terra" and captured.value.effort == "high"
    assert captured.value.exception_class == "APITimeoutError"
    assert captured.value.attempt_usage == [] and calls == []


def test_explicit_translation_selection_does_not_change_auth_probe_routing():
    client, calls = _client(model="gpt-5.6-terra")
    assert client.run_translation_auth_test().ok
    assert len(calls) == 1 and calls[0]["model"] == "gpt-5.2"
    assert calls[0]["max_output_tokens"] == 16 and calls[0]["store"] is False
    assert client.model == "gpt-5.6-terra"


def test_accounting_limits_and_reservation_use_selected_model():
    client, calls = _client(model="gpt-5.6-terra")
    limited_models, reservations = [], []

    class RecordingAccounting(module.MemoryDispatchAccounting):
        def request_limits(self, provider, purpose, model):
            limited_models.append((provider, purpose, model))
            return {"max_output_tokens": 256, "requested_service_tier": "default"}

        def begin(self, **kwargs):
            reservations.append(deepcopy(kwargs))
            return super().begin(**kwargs)

    client._dispatch_accounting = RecordingAccounting()
    prepared = client.prepare_page_request(**REQUEST, response_format=FORMAT, max_output_tokens=512)
    client.create_page_response(**REQUEST, response_format=FORMAT, max_output_tokens=512)
    assert limited_models == [("openai", "translation", "gpt-5.6-terra")] * 2
    assert len(reservations) == 1 and reservations[0]["requested_model"] == "gpt-5.6-terra"
    assert reservations[0]["effort"] == "high"
    assert reservations[0]["request_hash"] == module._request_accounting_details(prepared)[0]
    assert calls[0]["max_output_tokens"] == 256 and calls[0]["service_tier"] == "default"
    assert {key: value for key, value in calls[0].items() if key != "timeout"} == prepared
