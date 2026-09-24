from types import SimpleNamespace

import httpx
import pytest

import legalpdf_translate.openai_client as module
from legalpdf_translate.openai_client import ApiCallError, OpenAIResponsesClient


def client_for(monkeypatch, create, **options):
    def factory(*, api_key, max_retries):
        assert api_key == "synthetic-key" and max_retries == 0
        return SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(module, "OpenAI", factory)
    return OpenAIResponsesClient(api_key="synthetic-key", pre_call_jitter_seconds=0, **options)


def response(**options):
    return SimpleNamespace(**{ "id": "synthetic-response", "status": "completed", "model": "gpt-5.2",
        "output_text": '{"blocks":[]}', "output": [],
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                  "input_tokens_details": {"cached_tokens": 4}, "output_tokens_details": {"reasoning_tokens": 3}}, **options})


def call(client, **options):
    options.setdefault("response_format", {"type": "json_schema", "strict": True, "name": "test", "schema": {}})
    return client.create_page_response(instructions="synthetic", prompt_text="source", effort="high", **options)


def test_optional_strict_format_and_output_bound_keep_current_model(monkeypatch):
    calls = []
    client = client_for(monkeypatch, lambda **kw: calls.append(kw) or response())
    form = {"type": "json_schema", "name": "legal_blocks_v2", "strict": True, "schema": {"type": "object"}}
    result = call(client, response_format=form, max_output_tokens=1234)
    assert calls[0]["text"] == {"format": form}
    assert calls[0]["max_output_tokens"] == 1234
    assert calls[0]["model"] == module.OPENAI_MODEL == "gpt-5.2"
    assert result.response_status == "completed" and result.model == "gpt-5.2" and result.effort == "high"
    assert result.usage["cached_input_tokens"] == 4
    assert result.usage["output_tokens"] == 5 and result.usage["reasoning_tokens"] == 3
    assert len(result.attempt_usage) == 1


@pytest.mark.parametrize("options,kind", [
    ({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}, "IncompleteResponseError"),
    ({"status": "failed"}, "IncompleteResponseError"),
    ({"output": [{"type": "message", "content": [{"type": "refusal", "refusal": "private refusal"}]}]}, "RefusalResponseError"),
    ({"output_text": "", "output": []}, "EmptyResponseError"),
])
def test_failed_response_retains_usage_and_never_retries_or_exposes_content(monkeypatch, options, kind):
    calls = []
    client = client_for(monkeypatch, lambda **kw: calls.append(kw) or response(**options))
    with pytest.raises(ApiCallError) as error:
        call(client)
    assert len(calls) == 1
    assert error.value.exception_class == kind
    assert error.value.usage["total_tokens"] == 15
    assert error.value.response_id == "synthetic-response"
    assert len(error.value.attempt_usage) == 1
    assert "private refusal" not in str(error.value)


def test_structured_missing_status_is_not_accepted_but_legacy_fake_remains_compatible(monkeypatch):
    bare = SimpleNamespace(output_text="legacy", usage={}, id="fake")
    client = client_for(monkeypatch, lambda **kw: bare)
    assert call(client, response_format=None).raw_output == "legacy"
    with pytest.raises(ApiCallError):
        call(client, response_format={"type": "json_schema", "strict": True, "name": "test", "schema": {}})


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "20"])
def test_invalid_output_bound_fails_before_dispatch(monkeypatch, limit):
    calls = []
    client = client_for(monkeypatch, lambda **kw: calls.append(kw) or response())
    with pytest.raises(ValueError):
        call(client, max_output_tokens=limit)
    assert calls == []


def test_cancel_before_dispatch_has_no_attempt_usage(monkeypatch):
    calls = []
    client = client_for(monkeypatch, lambda **kw: calls.append(kw) or response())
    with pytest.raises(ApiCallError) as error:
        call(client, cancel_check=lambda: True)
    assert error.value.exception_class == "CancelledError"
    assert error.value.attempt_usage == [] and calls == []


def test_cancel_during_retry_backoff_preserves_unknown_attempt_and_no_redispatch(monkeypatch):
    state = {"cancel": False}
    calls = []
    def create(**kw):
        calls.append(kw)
        raise module.APIConnectionError(request=None)
    def sleep(_seconds):
        state["cancel"] = True
    monkeypatch.setattr(module.time, "sleep", sleep)
    client = client_for(monkeypatch, create)
    with pytest.raises(ApiCallError) as error:
        call(client, response_format=None, cancel_check=lambda: state["cancel"])
    assert len(calls) == 1 and error.value.exception_class == "CancelledError"
    assert len(error.value.attempt_usage) == 1
    assert error.value.attempt_usage[0]["usage"] == {}


def test_structured_uncertain_billing_never_uses_remaining_transport_retries(monkeypatch):
    calls = []
    def create(**kw):
        calls.append(kw)
        raise module.APIConnectionError(request=None)
    client = client_for(monkeypatch, create)
    with pytest.raises(ApiCallError) as error:
        call(client, response_format={"type": "json_schema", "strict": True, "name": "test", "schema": {}})
    assert len(calls) == 1 and error.value.attempt_usage[0]["status"] == "transport_failed"


@pytest.mark.parametrize("cause_class", [
    httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.CloseError, httpx.ProxyError,
    httpx.RemoteProtocolError, httpx.LocalProtocolError, httpx.UnsupportedProtocol,
    httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout,
])
def test_transport_diagnostic_keeps_only_allowlisted_cause_class(monkeypatch, cause_class):
    secret = "private message https://private.invalid/token SECRET"
    def create(**kwargs):
        try:
            raise cause_class(secret)
        except cause_class as cause:
            raise module.APIConnectionError(message=secret, request=None) from cause
    client = client_for(monkeypatch, create)
    with pytest.raises(ApiCallError) as error:
        call(client)
    assert module.transport_failure_diagnostic(error.value) == (
        f"APIConnectionError: transport cause class=httpx.{cause_class.__name__}")
    assert secret not in str(error.value)
    assert error.value.usage == {} and error.value.response_id is None


@pytest.mark.parametrize("kind", ["missing", "unknown", "cycle", "deep", "implicit", "subclass"])
def test_transport_diagnostic_does_not_guess_or_expose_unknown_causes(kind):
    error = ApiCallError("private wrapper message", None, "APITimeoutError", 0, 0.0, 0.0, False)
    private_type = type("PrivateSecretException", (RuntimeError,), {})
    if kind == "unknown":
        error.__cause__ = private_type("private cause message")
    elif kind == "cycle":
        error.__cause__ = private_type("private cycle")
        error.__cause__.__cause__ = error
    elif kind == "deep":
        current = error
        for _ in range(8):
            current.__cause__ = RuntimeError("private deep chain")
            current = current.__cause__
        current.__cause__ = httpx.ReadTimeout("private tail")
    elif kind == "implicit":
        error.__context__ = httpx.ReadTimeout("private unrelated context")
    elif kind == "subclass":
        error.__cause__ = type("PrivateReadError", (httpx.ReadError,), {})("private subclass")
    assert module.transport_failure_diagnostic(error) == "APITimeoutError: transport cause unavailable"


def test_nontransport_error_has_no_transport_diagnostic():
    error = ApiCallError("private message", None, "PrivateSecretException", 0, 0.0, 0.0, False)
    error.__cause__ = httpx.ReadError("private context")
    assert module.transport_failure_diagnostic(error) is None


def test_cancel_after_completed_response_preserves_billed_usage(monkeypatch):
    state = {"cancel": False}
    def create(**kw):
        state["cancel"] = True
        return response()
    client = client_for(monkeypatch, create)
    with pytest.raises(ApiCallError) as error:
        call(client, cancel_check=lambda: state["cancel"])
    assert error.value.exception_class == "CancelledError"
    assert error.value.usage["total_tokens"] == 15
    assert error.value.attempt_usage[0]["status"] == "completed"


def test_dict_response_and_incomplete_message_are_handled(monkeypatch):
    result = vars(response())
    client = client_for(monkeypatch, lambda **kw: result)
    assert call(client).usage["cached_input_tokens"] == 4
    result["output"] = [{"type": "message", "status": "incomplete", "content": []}]
    with pytest.raises(ApiCallError) as error:
        call(client)
    assert error.value.exception_class == "IncompleteResponseError"


def test_structured_permanent_error_has_no_raw_provider_content(monkeypatch):
    def create(**kw):
        raise RuntimeError("private document content")
    client = client_for(monkeypatch, create)
    with pytest.raises(ApiCallError) as error:
        call(client, response_format={"type": "json_schema", "strict": True, "name": "test", "schema": {}})
    assert "private document" not in str(error.value)


@pytest.mark.parametrize("timeout", [float("nan"), float("inf"), 0, -1])
def test_bad_deadline_rejected_without_attempt(monkeypatch, timeout):
    calls = []
    client = client_for(monkeypatch, lambda **kw: calls.append(kw) or response())
    with pytest.raises(ValueError):
        call(client, timeout_seconds=timeout)
    assert calls == []


def test_omitted_or_none_options_preserve_exact_legacy_request(monkeypatch):
    calls = []
    client = client_for(monkeypatch, lambda **kw: calls.append(kw) or response())
    for options in ({}, {"response_format": None, "max_output_tokens": None, "cancel_check": None}):
        client.create_page_response(instructions="base", prompt_text="page", effort="medium",
                                    image_data_url="data:synthetic", **options)
    for request in calls:
        assert set(request) == {"model", "instructions", "input", "reasoning", "store", "timeout"}
        assert request["model"] == module.OPENAI_MODEL
        assert request["reasoning"] == {"effort": "medium"}
        assert request["input"] == [{"role": "user", "content": [
            {"type": "input_text", "text": "page"},
            {"type": "input_image", "image_url": "data:synthetic", "detail": "low"},
        ]}]


def test_request_format_is_copied_and_medium_effort_not_overridden(monkeypatch):
    form = {"type": "json_schema", "strict": True, "name": "test", "schema": {}}
    def create(**kw):
        assert kw["reasoning"] == {"effort": "medium"}
        assert kw["max_output_tokens"] == 24000
        kw["text"]["format"]["schema"]["mutated"] = True
        return response()
    client = client_for(monkeypatch, create)
    result = client.create_page_response(instructions="i", prompt_text="p", effort="medium",
                                        response_format=form, max_output_tokens=24000)
    assert form["schema"] == {}
    assert result.effort == "medium"


def test_invalid_schema_and_cancel_callback_never_dispatch(monkeypatch):
    calls = []
    client = client_for(monkeypatch, lambda **kw: calls.append(kw) or response())
    for form in ({}, {"type": "text"}, {"type": "json_schema", "strict": False, "name": "test", "schema": {}}):
        with pytest.raises(ValueError):
            call(client, response_format=form)
    with pytest.raises(ValueError):
        call(client, cancel_check=True)
    assert calls == []


def test_cancellation_in_structured_429_backoff_prevents_second_call(monkeypatch):
    class Throttled(Exception):
        status_code = 429
    state, calls = {"cancel": False}, []
    def create(**kw):
        calls.append(kw)
        raise Throttled()
    monkeypatch.setattr(module.time, "sleep", lambda _s: state.update(cancel=True))
    client = client_for(monkeypatch, create)
    with pytest.raises(ApiCallError) as caught:
        call(client, cancel_check=lambda: state["cancel"])
    assert len(calls) == 1
    assert caught.value.exception_class == "CancelledError"
    assert caught.value.rate_limit_hit is True
    assert len(caught.value.attempt_usage) == 1


def test_usage_survives_downstream_strict_parser_failure(monkeypatch):
    from legalpdf_translate.translation_structure import BlockCoverageError, parse_structured_translation
    client = client_for(monkeypatch, lambda **kw: response())
    result = call(client)
    with pytest.raises(BlockCoverageError):
        parse_structured_translation(result.raw_output, [{"id": "p0001_b0001", "text": "Source"}])
    assert result.usage == {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
                            "reasoning_tokens": 3, "cached_input_tokens": 4}
    assert result.attempt_usage[0]["usage"] == result.usage
