"""Bounded source-page images use the existing accounted Responses transport."""

import base64
import json
from types import SimpleNamespace

import httpx
import pytest

import legalpdf_translate.openai_client as module
from legalpdf_translate.openai_client import ApiCallError, OpenAIResponsesClient
from legalpdf_translate.usage_accounting import MemoryDispatchAccounting, accounting_context
from tooling.acceptance_openai_sdk import AcceptanceOpenAI


IMAGES = tuple(
    "data:image/png;base64," + base64.b64encode(f"synthetic-page-{i}".encode()).decode()
    for i in range(12)
)
BASE = {"instructions": "synthetic instructions", "prompt_text": "synthetic source", "effort": "high"}
FORMAT = {"type": "json_schema", "strict": True, "name": "synthetic", "schema": {}}


def response(**changes):
    return SimpleNamespace(**{
        "id": "synthetic-response", "status": "completed", "model": "gpt-5.2",
        "output_text": '{"ok":true}', "output": [],
        "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25}, **changes,
    })


def client(create):
    return OpenAIResponsesClient(
        sdk_client=SimpleNamespace(
            base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create),
        ), pre_call_jitter_seconds=0,
    )


@pytest.mark.parametrize("container,count", [(list, 1), (tuple, 3), (list, 12)])
@pytest.mark.parametrize("detail", ["low", "high", "auto", "original"])
def test_prepare_and_dispatch_preserve_all_ordered_images_and_detail(container, count, detail):
    calls = []
    instance = client(lambda **kw: calls.append(kw) or response())
    options = {**BASE, "image_data_urls": container(IMAGES[:count]), "image_detail": detail,
               "response_format": FORMAT, "max_output_tokens": 400}
    prepared = instance.prepare_page_request(**options)
    assert calls == [] and instance._dispatch_accounting.summary()["call_count"] == 0
    result = instance.create_page_response(**options)
    assert result.response_status == "completed" and len(calls) == 1
    assert {k: v for k, v in calls[0].items() if k != "timeout"} == prepared
    assert prepared["input"][0]["content"] == [
        {"type": "input_text", "text": BASE["prompt_text"]},
        *({"type": "input_image", "image_url": url, "detail": detail} for url in IMAGES[:count]),
    ]
    begin = instance._dispatch_accounting._events[0]
    request_hash, bounds = module._request_accounting_details(prepared)
    assert begin["bounds"]["image_count"] == count
    assert begin["bounds"]["input_bytes"] == bounds["input_bytes"]
    assert begin["request_hash"] == request_hash
    assert IMAGES[0] not in json.dumps(instance._dispatch_accounting._events)
    # Every image's position/content participates in the prepared request identity.
    if count > 1:
        reversed_request = instance.prepare_page_request(**{**options, "image_data_urls": list(reversed(IMAGES[:count]))})
        assert module._request_accounting_details(reversed_request)[0] != request_hash


@pytest.mark.parametrize("images", [
    [], (), list(IMAGES) + [IMAGES[0]], IMAGES[0], b"image", {IMAGES[0]},
    {"image": IMAGES[0]}, iter(IMAGES), [None], [1], [b"data:image/png;base64,YQ=="],
    [""], ["https://example.invalid/page.png"], ["file:///page.png"],
    ["data:text/plain;base64,YQ=="], ["data:image/png,YQ=="],
    ["data:image/png;base64,"], ["data:image/png;base64,A"],
    ["data:image/png;base64,YQ="], ["data:image/png;base64,YQ==\n"],
    ["data:image/png;base64,@@=="], ["data:image/;base64,YQ=="],
])
def test_bad_plural_input_fails_before_preparation_accounting_or_dispatch(images):
    calls = []
    instance = client(lambda **kw: calls.append(kw) or response())
    for method in (instance.prepare_page_request, instance.create_page_response, module._build_page_request):
        with pytest.raises(ValueError):
            method(**BASE, image_data_urls=images)
    assert calls == [] and instance._dispatch_accounting._events == []


@pytest.mark.parametrize("single", ["", "data:legacy", IMAGES[0]])
def test_single_and_plural_input_are_mutually_exclusive_even_for_empty_single(single):
    instance = client(lambda **_: pytest.fail("mixed inputs reached SDK"))
    for method in (instance.prepare_page_request, instance.create_page_response, module._build_page_request):
        with pytest.raises(ValueError, match="cannot be combined"):
            method(**BASE, image_data_url=single, image_data_urls=[IMAGES[0]])
    assert instance._dispatch_accounting._events == []


@pytest.mark.parametrize("single", [None, "", "data:legacy-not-validated"])
def test_omitted_and_none_plural_option_preserve_legacy_payload_and_missing_status(single):
    calls = []
    instance = client(lambda **kw: calls.append(kw) or SimpleNamespace(output_text="legacy", usage={}, id="fake"))
    for options in ({}, {"image_data_urls": None}):
        assert instance.create_page_response(**BASE, image_data_url=single, **options).raw_output == "legacy"
        prepared = instance.prepare_page_request(**BASE, image_data_url=single, **options)
        assert {k: v for k, v in calls[-1].items() if k != "timeout"} == prepared
        assert set(calls[-1]) == {"model", "instructions", "input", "reasoning", "store", "timeout"}
    assert {k: v for k, v in calls[0].items() if k != "timeout"} == {
        k: v for k, v in calls[1].items() if k != "timeout"
    }


def test_plural_without_format_still_uses_bounded_response_checks():
    instance = client(lambda **_: response(status="incomplete"))
    with pytest.raises(ApiCallError) as caught:
        instance.create_page_response(**BASE, image_data_urls=list(IMAGES[:2]))
    assert caught.value.exception_class == "IncompleteResponseError"
    assert caught.value.usage["total_tokens"] == 25


@pytest.mark.parametrize("changes,kind", [
    ({"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}, "IncompleteResponseError"),
    ({"output": [{"type": "refusal", "refusal": "private refusal"}]}, "RefusalResponseError"),
])
def test_plural_structured_response_failures_keep_billed_usage_and_do_not_retry(changes, kind):
    calls = []
    instance = client(lambda **kw: calls.append(kw) or response(**changes))
    with pytest.raises(ApiCallError) as caught:
        instance.create_page_response(**BASE, image_data_urls=IMAGES[:3], response_format=FORMAT)
    assert len(calls) == 1 and caught.value.exception_class == kind
    assert caught.value.usage["total_tokens"] == 25
    assert instance._dispatch_accounting.summary()["call_count"] == 1
    assert "private refusal" not in str(caught.value)


def test_plural_structured_uncertain_transport_preserves_no_retry_policy(monkeypatch):
    calls = []
    def create(**kw):
        calls.append(kw)
        raise module.APIConnectionError(request=None)
    monkeypatch.setattr(module.time, "sleep", lambda _: pytest.fail("uncertain structured request retried"))
    instance = client(create)
    with pytest.raises(ApiCallError) as caught:
        instance.create_page_response(**BASE, image_data_urls=IMAGES[:3], response_format=FORMAT)
    assert len(calls) == 1 and caught.value.attempt_usage[0]["status"] == "transport_failed"


def test_cancelled_settled_output_is_private_and_preserved_without_another_dispatch():
    state, calls = {"cancelled": False}, []
    private_text = '{"private_synthetic_document":"retained"}'

    def create(**kwargs):
        calls.append(kwargs)
        state["cancelled"] = True
        return response(output_text=private_text)

    instance = client(create)
    with pytest.raises(ApiCallError) as caught:
        instance.create_page_response(**BASE, image_data_urls=IMAGES[:2],
            response_format=FORMAT, cancel_check=lambda: state["cancelled"])
    assert len(calls) == 1
    assert caught.value.exception_class == "CancelledError"
    assert caught.value.raw_output == private_text
    assert caught.value.response_status == "completed"
    assert caught.value.usage["total_tokens"] == 25
    assert private_text not in str(caught.value)
    assert private_text not in repr(caught.value)
    assert instance._dispatch_accounting.summary()["call_count"] == 1


def test_pretransport_cancellation_has_no_retained_output_or_dispatch():
    instance = client(lambda **_: pytest.fail("cancelled before dispatch"))
    with pytest.raises(ApiCallError) as caught:
        instance.create_page_response(**BASE, image_data_urls=IMAGES[:2],
            response_format=FORMAT, cancel_check=lambda: True)
    assert caught.value.raw_output is None
    assert instance._dispatch_accounting.summary()["call_count"] == 0


@pytest.mark.parametrize("maximum_images,allowed", [(2, False), (3, True)])
def test_hard_budget_image_count_covers_all_images_before_reservation(maximum_images, allowed):
    class BoundedAccounting(MemoryDispatchAccounting):
        hard_budget = True
        def request_limits(self, provider, purpose, requested_model):
            return {"max_input_tokens": 5000, "max_output_tokens": 400,
                    "max_image_count": maximum_images, "max_image_input_tokens": 300,
                    "image_bound_verified": True, "billing_scope": "synthetic",
                    "allowed_base_urls": ["https://api.openai.com/v1"]}
    journal, calls = BoundedAccounting(), []
    instance = client(lambda **kw: calls.append(kw) or response())
    with accounting_context(journal):
        if allowed:
            instance.create_page_response(**BASE, image_data_urls=IMAGES[:3], response_format=FORMAT)
        else:
            with pytest.raises(ApiCallError) as caught:
                instance.create_page_response(**BASE, image_data_urls=IMAGES[:3], response_format=FORMAT)
            assert caught.value.attempt_usage == []
    assert len(calls) == int(allowed)
    if allowed:
        assert journal._events[0]["bounds"]["image_count"] == 3
        assert len(journal._events) == 2
    else:
        assert journal._events == []


def test_locked_sdk_serializes_plural_images_through_existing_wrapper_without_network():
    calls = []
    def handle(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert [p["image_url"] for p in payload["input"][0]["content"][1:]] == list(IMAGES[:3])
        assert payload["text"] == {"format": FORMAT}
        return httpx.Response(200, json={
            "id": "resp_synthetic", "object": "response", "created_at": 1,
            "status": "completed", "model": "gpt-5.2", "output": [
                {"id": "msg_synthetic", "type": "message", "status": "completed", "role": "assistant",
                 "content": [{"type": "output_text", "text": '{"ok":true}', "annotations": []}]},
            ], "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
        })
    with httpx.Client(transport=httpx.MockTransport(handle), trust_env=False) as transport:
        sdk = AcceptanceOpenAI(api_key="synthetic-offline", http_client=transport, max_retries=0)
        instance = OpenAIResponsesClient(sdk_client=sdk, max_transport_retries=0, pre_call_jitter_seconds=0)
        result = instance.create_page_response(**BASE, image_data_urls=IMAGES[:3], response_format=FORMAT)
    assert result.raw_output == '{"ok":true}' and len(calls) == 1
