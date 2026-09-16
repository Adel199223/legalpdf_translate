"""Each fake provider dispatch is journaled before it can run."""

from concurrent.futures import ThreadPoolExecutor
import json
from types import SimpleNamespace

import pytest

import legalpdf_translate.ocr_engine as ocr
import legalpdf_translate.openai_client as transport
from legalpdf_translate.openai_client import ApiCallError, OpenAIResponsesClient
from legalpdf_translate.usage_accounting import accounting_context


class Recorder:
    def __init__(self, *, hard=False, limits=None):
        self.hard_budget = hard
        self.can_retry = True
        self.limits = limits or {}
        if hard:
            self.limits = {"billing_scope": "fixture", "currency": "USD",
                "allowed_base_urls": ["https://api.openai.com/v1"], **self.limits}
        self.events = []
        self.completed = []

    def request_limits(self, provider, purpose, requested_model):
        self.selection = (provider, purpose, requested_model)
        return dict(self.limits)

    def begin(self, **kwargs):
        self.events.append(("begin", kwargs))
        return SimpleNamespace(call_id=f"call-{len(self.events)}")

    def finish(self, ticket, **kwargs):
        self.events.append(("finish", kwargs))
        self.completed.append(kwargs)
        if self.hard_budget and not kwargs.get("usage"):
            self.can_retry = False
        return kwargs


def response(**overrides):
    return SimpleNamespace(**{
        "id": "synthetic-id", "model": "gpt-5.2", "status": "completed", "output": [],
        "service_tier": "default",
        "output_text": "translated", "usage": {
            "input_tokens": 20, "output_tokens": 8, "total_tokens": 28,
            "input_tokens_details": {"cached_tokens": 4},
            "output_tokens_details": {"reasoning_tokens": 3},
        }, **overrides,
    })


def client(create, **kwargs):
    return OpenAIResponsesClient(sdk_client=SimpleNamespace(base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create)),
                                 pre_call_jitter_seconds=0, **kwargs)


def call(instance, *, structured=False, **kwargs):
    if structured:
        kwargs["response_format"] = {"type": "json_schema", "strict": True, "name": "test", "schema": {}}
    return instance.create_page_response(instructions="synthetic instruction", prompt_text="synthetic source",
                                         effort="high", **kwargs)


@pytest.mark.parametrize("structured", [False, True])
def test_translation_dispatch_has_begin_finish_and_complete_response_evidence(structured):
    journal = Recorder()
    requests = []
    def create(**kwargs):
        assert journal.events[-1][0] == "begin"
        requests.append(kwargs)
        return response()
    with accounting_context(journal, purpose="correction", page_number=6):
        result = call(client(create), structured=structured)
    assert [event for event, _ in journal.events] == ["begin", "finish"]
    begin = journal.events[0][1]
    assert journal.selection == ("openai", "correction", "gpt-5.2")
    assert len(begin["request_hash"]) == 64
    assert "synthetic source" not in str(begin)
    assert result.attempt_usage[0]["usage"]["cached_input_tokens"] == 4
    assert journal.completed[0]["usage"]["reasoning_tokens"] == 3
    assert journal.completed[0]["actual_model"] == "gpt-5.2"
    assert "max_output_tokens" not in requests[0]


def test_ordinary_retry_ceiling_and_backoff_are_preserved_with_each_attempt_recorded(monkeypatch):
    journal, sleeps, calls = Recorder(), [], []
    def create(**kwargs):
        calls.append(kwargs)
        raise transport.APIConnectionError(request=None)
    monkeypatch.setattr(transport.time, "sleep", sleeps.append)
    monkeypatch.setattr(transport.random, "uniform", lambda *_: 0)
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(create, max_transport_retries=2))
    assert len(calls) == 3 and sleeps == [1, 2]
    assert [item[1]["attempt"] for item in journal.events if item[0] == "begin"] == [1, 2, 3]
    assert len(caught.value.attempt_usage) == 3
    assert all(item["usage"] == {} for item in journal.completed)


def test_hard_unknown_outcome_holds_and_stops_before_retry_backoff(monkeypatch):
    journal = Recorder(hard=True, limits={"max_input_tokens": 2000, "max_output_tokens": 40})
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        raise transport.APIConnectionError(request=None)
    monkeypatch.setattr(transport.time, "sleep", lambda _: pytest.fail("uncertain hard attempt must not sleep/retry"))
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(create, max_transport_retries=4))
    assert len(calls) == 1 and calls[0]["max_output_tokens"] == 40
    assert len(caught.value.attempt_usage) == 1
    assert "hard-budget hold" in str(caught.value)


@pytest.mark.parametrize("options,kind", [
    ({"output": [{"type": "refusal"}]}, "RefusalResponseError"),
    ({"status": "incomplete"}, "IncompleteResponseError"),
    ({"output_text": ""}, "EmptyResponseError"),
])
def test_rejected_structured_response_still_settles_its_usage(options, kind):
    journal = Recorder()
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(lambda **_: response(**options)), structured=True)
    assert caught.value.exception_class == kind
    assert len(journal.completed) == 1
    assert journal.completed[0]["usage"]["total_tokens"] == 28


def test_sdk_error_body_usage_and_actual_model_survive_failure():
    class Failed(Exception):
        status_code = 400
        body = {"id": "failed-id", "model": "actual-model", "usage": {"input_tokens": 11, "output_tokens": 2}}
    journal = Recorder()
    def create(**kwargs):
        raise Failed("sensitive provider detail")
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(create), structured=True)
    assert journal.completed[0]["actual_model"] == "actual-model"
    assert journal.completed[0]["response_id"] == "failed-id"
    assert caught.value.usage["output_tokens"] == 2
    assert caught.value.response_id == "failed-id"
    assert "sensitive" not in str(journal.events)


@pytest.mark.parametrize("usage", [
    {"input_tokens": 20, "output_tokens": 3, "cached_input_tokens": 7, "cache_write_tokens": 2},
    {"input_tokens": 20, "output_tokens": 3, "input_tokens_details": {"cached_tokens": 7, "cache_write_tokens": 2}},
])
def test_response_cache_read_and_write_breakdowns_reach_journal(usage):
    journal = Recorder()
    with accounting_context(journal):
        result = call(client(lambda **_: response(usage=usage)))
    assert result.usage["cached_input_tokens"] == 7
    assert result.usage["cache_write_tokens"] == 2
    assert journal.completed[0]["usage"]["cache_write_tokens"] == 2


def test_journal_finish_failure_preserves_paid_response_usage_and_never_retries():
    class StorageFailed(Recorder):
        def finish(self, ticket, **kwargs):
            raise RuntimeError("journal storage failed")
    journal, calls = StorageFailed(), []
    def create(**kwargs):
        calls.append(kwargs)
        return response(output_text="private translated text")
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(create), structured=True)
    assert len(calls) == 1
    assert caught.value.usage["total_tokens"] == 28
    assert caught.value.response_id == "synthetic-id"
    assert "private translated text" not in str(caught.value)


def test_post_response_cancellation_preserves_accounted_charge():
    journal, state = Recorder(), {"cancel": False}
    def create(**kwargs):
        state["cancel"] = True
        return response()
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(create), structured=True, cancel_check=lambda: state["cancel"])
    assert caught.value.exception_class == "CancelledError"
    assert len(journal.completed) == 1 and journal.completed[0]["usage"]["output_tokens"] == 8


def test_cancel_during_reservation_prevents_sdk_and_reconciles_no_dispatch():
    state = {"cancel": False}
    class CancellingRecorder(Recorder):
        def begin(self, **kwargs):
            ticket = super().begin(**kwargs)
            state["cancel"] = True
            return ticket
    journal = CancellingRecorder()
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(lambda **_: pytest.fail("cancelled reservation reached SDK")), structured=True,
             cancel_check=lambda: state["cancel"])
    assert caught.value.exception_class == "CancelledError" and caught.value.attempt_usage == []
    assert journal.completed[0]["outcome"] == "not_dispatched"
    assert journal.completed[0]["usage"]["total_tokens"] == 0


def test_deadline_during_reservation_prevents_legacy_sdk_dispatch(monkeypatch):
    clock = {"now": 0.0}
    class DelayedRecorder(Recorder):
        def begin(self, **kwargs):
            ticket = super().begin(**kwargs)
            clock["now"] = 10.0
            return ticket
    journal = DelayedRecorder()
    monkeypatch.setattr(transport.time, "perf_counter", lambda: clock["now"])
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(lambda **_: pytest.fail("expired reservation reached SDK")), timeout_seconds=5)
    assert caught.value.attempt_usage == []
    assert journal.completed[0]["outcome"] == "not_dispatched"


@pytest.mark.parametrize("image", [False, True])
def test_hard_unverified_input_bound_blocks_before_journal_and_provider(image):
    limits = {"max_input_tokens": 2000 if image else 1, "max_output_tokens": 40}
    journal = Recorder(hard=True, limits=limits)
    with accounting_context(journal), pytest.raises(ApiCallError) as caught:
        call(client(lambda **_: pytest.fail("blocked request reached provider")),
             image_data_url="data:synthetic" if image else None)
    assert journal.events == [] and caught.value.attempt_usage == []


def test_local_preflight_is_free_and_explicit_auth_test_is_accounted():
    journal = Recorder()
    instance = client(lambda **_: response())
    with accounting_context(journal):
        assert instance.local_credential_preflight().ok
        assert journal.events == []
        assert instance.run_translation_auth_test().ok
    assert journal.events[0][1]["purpose"] == "auth"
    assert len(journal.completed) == 1


def test_contexts_do_not_cross_parallel_worker_clones():
    instance = client(lambda **_: response())
    journals = [Recorder(), Recorder()]
    def run(index):
        with accounting_context(journals[index], purpose=f"purpose{index}", page_number=index + 1):
            call(instance.clone())
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, range(2)))
    assert [item.selection[1] for item in journals] == ["purpose0", "purpose1"]
    assert all(len(item.completed) == 1 for item in journals)


def test_openai_ocr_and_explicit_provider_test_share_accounting_boundary(monkeypatch):
    journal = Recorder()
    def create(**kwargs):
        assert journal.events[-1][0] == "begin"
        return response(output_text="OK", model="gpt-4o-mini")
    def factory(**kwargs):
        assert kwargs["max_retries"] == 0
        return SimpleNamespace(responses=SimpleNamespace(create=create))
    monkeypatch.setattr(ocr, "OpenAI", factory)
    engine = ocr.ApiOcrEngine(api_key="synthetic", model="gpt-4o-mini")
    with accounting_context(journal, purpose="translation", page_number=2):
        assert engine.ocr_image(b"synthetic-image").text == "OK"
        ocr.test_ocr_provider_connection(ocr.OcrEngineConfig(), api_key="synthetic")
    assert [event[1]["purpose"] for event in journal.events if event[0] == "begin"] == ["ocr", "auth"]
    assert all(record["actual_model"] == "gpt-4o-mini" for record in journal.completed)


def test_gemini_ocr_records_raw_usage_and_actual_model(monkeypatch):
    journal = Recorder()
    usage = {"promptTokenCount": 20, "candidatesTokenCount": 5, "thoughtsTokenCount": 3, "totalTokenCount": 28}
    def post(**kwargs):
        assert journal.events[-1][0] == "begin"
        return {"candidates": [{"content": {"parts": [{"text": "OCR text"}]}}],
                "usageMetadata": usage, "modelVersion": "gemini-actual", "responseId": "gemini-id"}
    monkeypatch.setattr(ocr, "_gemini_post_json", post)
    with accounting_context(journal, purpose="translation"):
        result = ocr.GeminiApiOcrEngine(api_key="synthetic", model="gemini-requested").ocr_image(b"image")
    assert result.text == "OCR text"
    assert journal.events[0][1]["purpose"] == "ocr"
    assert journal.completed[0]["usage"] == usage
    assert journal.completed[0]["actual_model"] == "gemini-actual"


def test_gemini_failure_usage_is_preserved_without_provider_content(monkeypatch):
    journal = Recorder()
    def post(**kwargs):
        raise ocr.GeminiRequestError("gemini HTTP 500", status_code=500, body={
            "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 1},
            "modelVersion": "gemini-actual", "responseId": "failed-gemini", "error": "private detail"})
    monkeypatch.setattr(ocr, "_gemini_post_json", post)
    with accounting_context(journal):
        result = ocr.GeminiApiOcrEngine(api_key="synthetic", model="gemini-requested").ocr_image(b"image")
    assert result.failed_reason == "api OCR request failed: gemini HTTP 500"
    assert journal.completed[0]["usage"]["promptTokenCount"] == 9
    assert "private detail" not in str(journal.events)


def durable_accountant(tmp_path, *, hard=True):
    from legalpdf_translate.budget_reservations import ReservationBudget
    from legalpdf_translate.cost_guardrails import PricingSnapshot
    from legalpdf_translate.usage_accounting import DispatchAccounting
    prices = PricingSnapshot.from_mapping({
        "snapshot_id": "synthetic-test", "verified_at": "2026-09-10", "source": "offline fixture",
        "models": {"openai:gpt-5.2|default|fixture|USD": {"input_per_1m": 2, "output_per_1m": 8,
            "cached_input_per_1m": 1, "service_tier": "default", "billing_scope": "fixture", "currency": "USD"}},
    })
    budget = ReservationBudget(tmp_path / "budget.json", cap_usd="1", identity={"case": "synthetic"}) if hard else None
    accountant = DispatchAccounting(tmp_path / "journal", run_identity={"case": "synthetic"},
        pricing_snapshot=prices, budget_context=budget,
        dispatch_limits={"openai:translation": {
            "requested_model": "gpt-5.2", "max_input_tokens": 2000, "max_output_tokens": 40,
            "requested_service_tier": "default", "billing_scope": "fixture", "currency": "USD",
            "allowed_base_urls": ["https://api.openai.com/v1"]}})
    return accountant, budget


def test_real_journal_and_reservation_exist_before_sdk_then_settle_once(tmp_path):
    accountant, budget = durable_accountant(tmp_path)
    def create(**kwargs):
        journal = json.loads(accountant.journal_path.read_text(encoding="utf-8"))
        assert len(journal["events"]) == 1 and journal["events"][0]["event"] == "begin"
        assert float(budget.status()["held_usd"]) > 0
        assert kwargs["max_output_tokens"] == 40
        return response()
    with accounting_context(accountant, purpose="translation", page_number=3):
        call(client(create))
    summary = accountant.summary()
    assert summary["coverage_status"] == "complete"
    assert summary["call_count"] == 1
    assert float(budget.status()["held_usd"]) == 0
    assert float(budget.status()["known_spend_usd"]) > 0


def test_real_hard_reservation_retains_full_hold_after_timeout(tmp_path, monkeypatch):
    accountant, budget = durable_accountant(tmp_path)
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        raise transport.APITimeoutError(request=None)
    monkeypatch.setattr(transport.time, "sleep", lambda _: pytest.fail("uncertain hold retried"))
    with accounting_context(accountant), pytest.raises(ApiCallError):
        call(client(create))
    assert len(calls) == 1
    assert budget.status()["blocked"] is True
    assert float(budget.status()["held_usd"]) > 0
    assert accountant.summary()["coverage_status"] != "complete"


def test_standalone_clone_keeps_usage_history_in_fallback_accountant():
    instance = client(lambda **_: response())
    call(instance.clone())
    assert instance._dispatch_accounting.summary()["call_count"] == 1
