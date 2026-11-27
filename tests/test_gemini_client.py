"""Offline tests for GeminiInteractionsClient, provider factory, and Gemini usage normalization."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legalpdf_translate import gemini_client, provider_client
from legalpdf_translate.accounting_policy import gemini_accounting_policy, with_semantic_review_policy
from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.config import DEFAULT_TRANSLATION_PROVIDER, GEMINI_MODEL
from legalpdf_translate.openai_client import ApiCallError
from legalpdf_translate.semantic_review_model_policy import fresh_semantic_review_model_policy
from legalpdf_translate.types import TranslationApiProvider
from legalpdf_translate.usage_accounting import DispatchAccounting, accounting_context, normalize_usage


def _make_fake_interaction(
    *,
    response_id: str = "int-123",
    model: str = GEMINI_MODEL,
    status: str = "completed",
    text: str = "Translated output",
    input_tokens: int = 120,
    output_tokens: int = 40,
    thought_tokens: int = 25,
    cached_tokens: int = 10,
    service_tier: str | None = None,
    errors: list[dict[str, str]] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=response_id,
        model=model,
        status=status,
        service_tier=service_tier,
        errors=errors or [],
        output_text=text,
        steps=[
            SimpleNamespace(type="thought", content=[]),
            SimpleNamespace(
                type="model_output",
                content=[SimpleNamespace(type="text", text=text)],
            ),
        ],
        usage=SimpleNamespace(
            total_input_tokens=input_tokens,
            total_output_tokens=output_tokens,
            total_thought_tokens=thought_tokens,
            total_cached_tokens=cached_tokens,
            total_tokens=input_tokens + output_tokens + thought_tokens,
        ),
    )


def test_default_provider_and_factory_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
    assert DEFAULT_TRANSLATION_PROVIDER == "gemini"
    assert provider_client.normalize_translation_provider(None) == TranslationApiProvider.GEMINI
    assert provider_client.default_translation_model("gemini") == "gemini-4-neon"
    gem = provider_client.create_translation_client(provider="gemini")
    oai = provider_client.create_translation_client(provider="openai")
    assert isinstance(gem, gemini_client.GeminiInteractionsClient)
    assert gem.model == "gemini-4-neon"
    assert provider_client.client_provider(gem) == "gemini"
    assert provider_client.client_provider(oai) == "openai"


def test_build_gemini_page_request_uses_store_false_image_and_strict_schema() -> None:
    req = gemini_client._build_gemini_page_request(
        instructions="Translate carefully.",
        prompt_text="Source text",
        effort="xhigh",
        image_data_url="data:image/png;base64,QUJD",
        response_format={
            "type": "json_schema",
            "name": "sample_schema",
            "strict": True,
            "schema": {"type": "object", "properties": {"a": {"type": "string"}}},
        },
        max_output_tokens=4096,
    )
    assert req["model"] == "gemini-4-neon"
    assert req["store"] is False
    assert req["system_instruction"] == "Translate carefully."
    assert req["generation_config"] == {"thinking_level": "xhigh", "max_output_tokens": 4096}
    assert req["input"] == [
        {"type": "text", "text": "Source text"},
        {"type": "image", "mime_type": "image/png", "data": "QUJD"},
    ]
    req_high = gemini_client._build_gemini_page_request(
        instructions="Translate carefully.",
        prompt_text="Source text",
        effort="high",
        image_data_url="data:image/png;base64,QUJD",
        image_detail="high",
    )
    assert req_high["input"] == [
        {"type": "text", "text": "Source text"},
        {"type": "image", "mime_type": "image/png", "data": "QUJD", "resolution": "high"},
    ]
    assert req["response_format"] == {
        "type": "text",
        "mime_type": "application/json",
        "schema": {"type": "object", "properties": {"a": {"type": "string"}}},
    }


def test_normalize_gemini_usage_folds_thought_tokens_into_output() -> None:
    raw_usage = SimpleNamespace(
        total_input_tokens=1000,
        total_output_tokens=200,
        total_thought_tokens=350,
        total_cached_tokens=100,
        total_tokens=1550,
    )
    norm = normalize_usage(raw_usage, provider="gemini")
    assert norm["usage_status"] == "available"
    assert norm["input_tokens"] == 1000
    assert norm["output_tokens"] == 550
    assert norm["reasoning_tokens"] == 350
    assert norm["cached_input_tokens"] == 100
    assert norm["cache_write_tokens"] == 0
    assert norm["total_tokens"] == 1550


def test_gemini_client_create_page_response_with_dispatch_accounting(tmp_path: Path) -> None:
    seen_requests: list[dict[str, object]] = []

    class _FakeInteractions:
        def create(self, **kwargs):
            seen_requests.append(kwargs)
            return _make_fake_interaction(input_tokens=500, output_tokens=100, thought_tokens=150)

    sdk = SimpleNamespace(interactions=_FakeInteractions())
    client = gemini_client.GeminiInteractionsClient(
        sdk_client=sdk,
        pre_call_jitter_seconds=0.0,
    )
    policy = gemini_accounting_policy()
    budget = ReservationBudget(tmp_path / "budget.json", cap_usd="5.00", identity={"run": "r1"})
    accountant = DispatchAccounting(
        tmp_path / "accounting",
        run_identity={"run": "r1"},
        budget_context=budget,
        **policy.accounting_arguments(),
    )
    with accounting_context(accountant, purpose="translation", page_number=1):
        result = client.create_page_response(
            instructions="Sys",
            prompt_text="Body",
            effort="xhigh",
        )
    assert result.raw_output == "Translated output"
    assert result.model == "gemini-4-neon"
    assert result.usage["input_tokens"] == 500
    assert result.usage["output_tokens"] == 250
    assert result.usage["reasoning_tokens"] == 150
    assert seen_requests[0]["store"] is False
    assert seen_requests[0]["generation_config"]["thinking_level"] == "xhigh"
    summary = accountant.summary()
    assert summary["coverage_status"] == "complete"
    assert float(summary["cost_usd"]) > 0.0


def test_gemini_strict_semantic_review_retains_raw_bytes(tmp_path: Path) -> None:
    payload_dict = {
        "id": "int-sem-1",
        "model": "gemini-4-neon",
        "status": "completed",
        "output_text": '{"ok":true}',
        "usage": {
            "total_input_tokens": 400,
            "total_output_tokens": 50,
            "total_thought_tokens": 50,
            "total_cached_tokens": 0,
            "total_tokens": 500,
        },
    }
    raw_bytes = json.dumps(payload_dict).encode("utf-8")

    class _FakeRawResp:
        def read(self) -> bytes:
            return raw_bytes

    class _FakeInteractions:
        def __init__(self) -> None:
            self.with_raw_response = SimpleNamespace(create=lambda **kw: _FakeRawResp())

    sdk = SimpleNamespace(interactions=_FakeInteractions())
    client = gemini_client.GeminiInteractionsClient(sdk_client=sdk, pre_call_jitter_seconds=0.0)
    review_client = client.for_semantic_review(model="gemini-4-neon")
    model_policy = fresh_semantic_review_model_policy(primary_model="gemini-4-neon")
    policy = with_semantic_review_policy(gemini_accounting_policy(), model_policy)
    accountant = DispatchAccounting(
        tmp_path / "accounting",
        run_identity={"run": "sem1", "semantic_review_model_policy": model_policy},
        budget_context=None,
        **policy.accounting_arguments(),
    )
    with accounting_context(accountant, purpose="semantic_audit", page_number=1):
        res = review_client.create_page_response(instructions="Audit", prompt_text="Data", effort="xhigh")
    assert res.raw_output == '{"ok":true}'
    summary = accountant.summary()
    assert summary["coverage_status"] == "complete"
    events = json.loads((tmp_path / "accounting" / "dispatch_accounting.json").read_text(encoding="utf-8"))["events"]
    finish = [e for e in events if e["event"] == "finish"][0]
    assert finish["semantic_review_billing_evidence"]["status"] == "available"


def test_gemini_auth_failure_and_empty_output_raise_api_call_error() -> None:
    class _AuthErr(Exception):
        status_code = 403

    class _FailInteractions:
        def create(self, **kwargs):
            raise _AuthErr("API_KEY_INVALID")

    client = gemini_client.GeminiInteractionsClient(
        sdk_client=SimpleNamespace(interactions=_FailInteractions()),
        pre_call_jitter_seconds=0.0,
    )
    with pytest.raises(ApiCallError) as exc_info:
        client.create_page_response(instructions="Sys", prompt_text="Body", effort="xhigh")
    assert exc_info.value.status_code == 403
    assert gemini_client.is_gemini_auth_failure(
        exception_class=exc_info.value.exception_class,
        status_code=exc_info.value.status_code,
        message=str(exc_info.value),
    )


def test_gemini_key_resolution_ignores_other_keys_and_never_leaks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_client, "get_gemini_key", lambda: "gem-secret-token")
    monkeypatch.setattr(gemini_client, "get_ocr_key", lambda: None)
    key, src = gemini_client.resolve_gemini_key_with_source()
    assert key == "gem-secret-token"
    assert src is not None and src.kind == "stored" and src.name == "gemini_api_key"
