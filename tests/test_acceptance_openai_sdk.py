"""Actual SDK with synthetic HTTP responses; no provider or private data."""
import json
import platform

import httpx
from openai import APIStatusError, OpenAI
import pytest

from legalpdf_translate import openai_client as client_module
from legalpdf_translate.openai_client import OpenAIResponsesClient
from tooling.acceptance_openai_sdk import AcceptanceOpenAI


REQUEST = dict(model="gpt-5.2", input="Synthetic request.", reasoning={"effort": "high"},
               max_output_tokens=64, store=False, service_tier="default")


def forbid(*args, **kwargs):
    raise AssertionError("Host metadata or ambient credential lookup is forbidden.")


@pytest.fixture(autouse=True)
def forbid_metadata_and_ambient_credentials(monkeypatch):
    calls = []
    def record_forbidden(*args, **kwargs):
        calls.append(True)
        forbid()
    for name in ("system", "platform", "machine", "uname", "win32_ver"):
        monkeypatch.setattr(platform, name, record_forbidden)
    monkeypatch.setattr(client_module, "resolve_openai_key_with_source", record_forbidden)
    yield
    # The SDK catches metadata exceptions and falls back to Unknown. Merely
    # raising would let a missing override appear to pass these tests.
    assert not calls, 'No host/credential probe may occur even if SDK catches it.'


def response(request):
    return httpx.Response(200, json={
        "id": "resp_synthetic", "object": "response", "created_at": 1,
        "status": "completed", "model": "gpt-5.2", "service_tier": "default",
        "output": [{"id": "msg_synthetic", "type": "message", "status": "completed",
                    "role": "assistant", "content": [{"type": "output_text", "text": "Synthetic output.", "annotations": []}]}],
        "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5,
                  "input_tokens_details": {"cached_tokens": 0},
                  "output_tokens_details": {"reasoning_tokens": 1}},
    })


def configured(transport):
    return AcceptanceOpenAI(api_key="synthetic-offline-key", base_url="https://api.openai.com/v1",
                            http_client=transport, timeout=2, max_retries=0)


def test_real_sdk_preserves_request_and_response_without_host_probe():
    calls = []
    def handle(request):
        calls.append(request)
        assert json.loads(request.content) == REQUEST
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["X-Stainless-OS"] == "Unknown"
        assert request.headers["X-Stainless-Arch"] == "unknown"
        return response(request)
    original = OpenAI.platform_headers
    with httpx.Client(transport=httpx.MockTransport(handle), trust_env=False) as transport:
        sdk = configured(transport)
        result = sdk.responses.create(**REQUEST)
        assert result.output_text == "Synthetic output."
        assert result.usage.input_tokens == 2 and result.usage.output_tokens == 3
        assert sdk.max_retries == 0 and len(calls) == 1
        assert OpenAI.platform_headers is original
        clone = sdk.with_options(max_retries=0)
        assert type(clone) is AcceptanceOpenAI
        assert clone.platform_headers() == sdk.platform_headers()
        assert client_module.OpenAI is OpenAI  # Ordinary application unchanged.


@pytest.mark.parametrize('status', [401, 429, 500])
def test_real_sdk_errors_remain_errors_with_no_retry(status):
    calls = []
    def handle(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "Synthetic failure.", "type": "synthetic"}})
    with httpx.Client(transport=httpx.MockTransport(handle), trust_env=False) as transport:
        with pytest.raises(APIStatusError) as caught:
            configured(transport).responses.create(**REQUEST)
    assert caught.value.status_code == status and len(calls) == 1


def test_actual_app_wrapper_and_clone_use_configured_sdk_without_metadata_or_key_lookup():
    calls = []
    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload['model'] == 'gpt-5.2'
        assert payload['reasoning'] == {'effort': 'high'}
        assert payload['store'] is False
        return response(request)
    with httpx.Client(transport=httpx.MockTransport(handle), trust_env=False) as transport:
        sdk = configured(transport)
        wrapper = OpenAIResponsesClient(sdk_client=sdk, max_transport_retries=0,
            pre_call_jitter_seconds=0, request_timeout_seconds=2)
        clone = wrapper.clone()
        assert isinstance(clone._client, AcceptanceOpenAI)
        assert clone._max_transport_retries == clone._client.max_retries == 0
        result = clone.create_page_response(instructions='Synthetic instructions.',
            prompt_text='Synthetic request.', effort='high', max_output_tokens=64,
            image_data_url=None, image_detail='low', timeout_seconds=2)
        assert result.raw_output == 'Synthetic output.'
        assert result.response_status == 'completed' and len(calls) == 1
        assert result.usage['input_tokens'] == 2 and result.usage['output_tokens'] == 3


def test_metadata_dictionary_is_not_shared_between_callers():
    with httpx.Client(transport=httpx.MockTransport(response), trust_env=False) as transport:
        sdk = configured(transport)
        headers = sdk.platform_headers()
        headers['X-Stainless-OS'] = 'changed-by-caller'
        assert sdk.platform_headers()['X-Stainless-OS'] == 'Unknown'
