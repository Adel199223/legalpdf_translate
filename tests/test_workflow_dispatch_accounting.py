"""Real workflow/coordinator/transport journaling with an entirely fake SDK."""
from dataclasses import replace
from datetime import date
import json
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from legalpdf_translate import workflow as module
from legalpdf_translate.checkpoint import load_run_state, save_run_state_atomic
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.types import BudgetExceedPolicy
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_new_run_preflight import TARGET, config_for


class FakeSDK:
    def __init__(self, *, correction=False, missing_usage=False):
        self.base_url = "https://api.openai.com/v1/"
        self.requests = []
        self.correction = correction
        self.missing_usage = missing_usage
        self.responses = SimpleNamespace(create=self.create)

    def create(self, **request):
        self.requests.append(request)
        prompt = request["input"][0]["content"][0]["text"]
        if "text" in request:
            source, _ = json.JSONDecoder().raw_decode(prompt)
            rows = [{"id": row["id"], "text": TARGET} for row in source["blocks"]]
            if self.correction and len(self.requests) == 1:
                rows = []
            output = json.dumps({"blocks": rows})
        else:
            output = "```text\n" + TARGET + "\n```"
        return SimpleNamespace(id=f"response-{len(self.requests)}", model="gpt-5.2", status="completed",
            service_tier="default",
            output_text=output, output=[], usage=None if self.missing_usage else {
                "input_tokens": 100, "output_tokens": 60,
                "input_tokens_details": {"cached_tokens": 20},
                "output_tokens_details": {"reasoning_tokens": 30}, "total_tokens": 160})


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    import legalpdf_translate.accounting_policy as policy_module
    class VerifiedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 9, 10)
    monkeypatch.setattr(policy_module, "date", VerifiedDate)
    monkeypatch.setattr(module, "load_environment", lambda: None)
    monkeypatch.setattr(module, "load_gui_settings", lambda: pytest.fail("Ambient settings"))
    monkeypatch.setattr(module, "run_translation_auth_test", lambda: pytest.fail("Billable auth probe"))
    monkeypatch.setattr(module, "resolve_openai_key_with_source", lambda: pytest.fail("Ambient report credentials"))


def client_for(sdk):
    return OpenAIResponsesClient(sdk_client=sdk, max_transport_retries=0, pre_call_jitter_seconds=0)


@pytest.mark.parametrize("protocol", ["legacy_text_v1", "legal_blocks_v2"])
def test_durable_calls_survive_resume_and_no_auth_probe(tmp_path, protocol):
    config = config_for(tmp_path)
    sdk = FakeSDK()
    workflow = TranslationWorkflow(client=client_for(sdk), gui_settings={}, translation_protocol=protocol)
    result = workflow.run(config)
    assert result.success, result.error
    state = load_run_state(workflow._last_paths.run_state_path)
    identifier = state.dispatch_accounting["id"]
    journal_path = result.run_dir / "accounting" / identifier / "dispatch_accounting.json"
    before = journal_path.read_bytes()
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert summary["dispatch_accounting"]["call_count"] == 1
    assert summary["dispatch_accounting"]["cost_usd"] == pytest.approx(0.0009835)
    assert summary["cost_estimation_status"] == "measured_all_calls"
    assert all("service_tier" not in request for request in sdk.requests)
    if protocol == "legacy_text_v1":
        assert all("max_output_tokens" not in request for request in sdk.requests)
    else:
        assert all(request["max_output_tokens"] < 128000 for request in sdk.requests)
    assert len(sdk.requests) == 1
    resumed = TranslationWorkflow(client=client_for(sdk), gui_settings={}).run(replace(config, resume=True))
    assert resumed.success, resumed.error
    assert len(sdk.requests) == 1
    assert journal_path.read_bytes() == before


def test_structured_correction_is_a_separate_durable_purpose(tmp_path):
    sdk = FakeSDK(correction=True)
    result = TranslationWorkflow(client=client_for(sdk), gui_settings={},
        translation_protocol="legal_blocks_v2").run(config_for(tmp_path))
    assert result.success, result.error
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))["dispatch_accounting"]
    assert summary["call_count"] == 2
    assert summary["by_purpose"]["translation"]["provider_dispatch_count"] == 1
    assert summary["by_purpose"]["correction"]["provider_dispatch_count"] == 1


def test_missing_journal_blocks_resume_before_provider(tmp_path):
    config = config_for(tmp_path)
    sdk = FakeSDK()
    workflow = TranslationWorkflow(client=client_for(sdk), gui_settings={})
    assert workflow.run(config).success
    state = load_run_state(workflow._last_paths.run_state_path)
    # Point at nonexistent evidence without deleting the existing journal.
    state.dispatch_accounting["id"] = "f" * 32
    save_run_state_atomic(workflow._last_paths.run_state_path, state)
    with pytest.raises(ValueError, match="journal is missing"):
        workflow.run(replace(config, resume=True))
    assert len(sdk.requests) == 1


def test_legacy_new_run_preserves_previous_journal(tmp_path):
    config = config_for(tmp_path)
    sdk = FakeSDK()
    workflow = TranslationWorkflow(client=client_for(sdk), gui_settings={})
    result = workflow.run(config)
    previous = {p: p.read_bytes() for p in (result.run_dir / "accounting").rglob("*.json")}
    assert workflow.run(config).success
    assert all(p.read_bytes() == content for p, content in previous.items())
    assert len(list((result.run_dir / "accounting").glob("*/dispatch_accounting.json"))) == 2


def test_old_completed_checkpoint_stays_historically_incomplete(tmp_path):
    config = config_for(tmp_path)
    sdk = FakeSDK()
    workflow = TranslationWorkflow(client=client_for(sdk), gui_settings={})
    assert workflow.run(config).success
    old_accounting = workflow._last_paths.run_dir / "accounting"
    old_accounting.rename(old_accounting.with_name("fixture-modern-evidence"))
    state = load_run_state(workflow._last_paths.run_state_path)
    state.dispatch_accounting = {}
    save_run_state_atomic(workflow._last_paths.run_state_path, state)
    result = workflow.run(replace(config, resume=True))
    assert result.success
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))["dispatch_accounting"]
    assert summary["historical_incomplete"] is True
    assert summary["coverage_status"] != "complete"
    assert summary["cost_usd"] is None
    assert len(sdk.requests) == 1


def test_product_block_without_verified_bounds_stops_before_sdk(tmp_path):
    config = replace(config_for(tmp_path), budget_cap_usd=10, budget_on_exceed=BudgetExceedPolicy.BLOCK)
    sdk = FakeSDK()
    result = TranslationWorkflow(client=client_for(sdk), gui_settings={}).run(config)
    assert not result.success
    assert not sdk.requests


def test_worker_context_accounts_each_page_once(tmp_path):
    config = config_for(tmp_path)
    source = tmp_path / "two.pdf"
    with fitz.open(config.pdf_path) as original, fitz.open() as document:
        document.insert_pdf(original)
        document.insert_pdf(original)
        document.save(source)
    sdk = FakeSDK()
    result = TranslationWorkflow(client=client_for(sdk), gui_settings={}).run(
        replace(config, pdf_path=source, workers=2))
    assert result.success, result.error
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))["dispatch_accounting"]
    assert summary["call_count"] == 2
    assert len(sdk.requests) == 2


def priced_factory(budgets):
    from legalpdf_translate.budget_reservations import ReservationBudget
    from legalpdf_translate.cost_guardrails import PricingSnapshot
    from legalpdf_translate.usage_accounting import DispatchAccounting

    prices = PricingSnapshot.from_mapping({
        "snapshot_id": "offline-workflow-fixture", "verified_at": "2026-09-10",
        "source": "synthetic test rates, not production pricing",
        "models": {"openai:gpt-5.2|default|fixture|USD": {
            "input_per_1m": 2, "output_per_1m": 8, "cached_input_per_1m": 1,
            "service_tier": "default", "billing_scope": "fixture", "currency": "USD"}},
    })

    def factory(*, run_dir, run_identity, historical_incomplete):
        budget = ReservationBudget(run_dir / "budget.json", cap_usd="1", identity=run_identity,
            create=not (run_dir / "dispatch_accounting.json").exists())
        budgets.append(budget)
        limits = {"requested_model": "gpt-5.2", "max_input_tokens": 50000,
                  "max_output_tokens": 256, "requested_service_tier": "default",
                  "billing_scope": "fixture", "currency": "USD",
                  "allowed_base_urls": ["https://api.openai.com/v1"]}
        return DispatchAccounting(run_dir, run_identity=run_identity, pricing_snapshot=prices,
            budget_context=budget, historical_incomplete=historical_incomplete,
            dispatch_limits={"openai:translation": limits, "openai:correction": limits})

    return factory


@pytest.mark.parametrize("protocol,correction,expected_calls", [
    ("legacy_text_v1", False, 1), ("legal_blocks_v2", False, 1),
    ("legal_blocks_v2", True, 2),
])
def test_priced_workflow_settles_complete_all_calls_and_resume_reuses_evidence(
    tmp_path, protocol, correction, expected_calls,
):
    config = config_for(tmp_path)
    sdk = FakeSDK(correction=correction)
    budgets = []
    factory = priced_factory(budgets)
    workflow = TranslationWorkflow(client=client_for(sdk), gui_settings={},
        translation_protocol=protocol, accounting_factory=factory)
    result = workflow.run(config)
    assert result.success, result.error
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    accounting = summary["dispatch_accounting"]
    assert accounting["coverage_status"] == "complete"
    assert accounting["provider_dispatch_count"] == expected_calls
    # Output usage includes reasoning; cached input is billed once at the cache rate.
    assert accounting["cost_usd"] == pytest.approx(0.00066 * expected_calls)
    assert summary["cost_estimation_status"] == "measured_all_calls"
    assert summary["budget_post_run"]["input_tokens"] == 100 * expected_calls
    assert summary["budget_post_run"]["output_tokens"] == 60 * expected_calls
    assert summary["budget_post_run"]["total_tokens"] == 160 * expected_calls
    assert summary["budget_post_run"]["pricing_source"] == "verified_snapshot"
    assert summary["budget_post_run"]["pricing_snapshot"]["snapshot_id"] == "offline-workflow-fixture"
    assert float(budgets[-1].status()["known_spend_usd"]) == pytest.approx(0.00066 * expected_calls)
    assert float(budgets[-1].status()["held_usd"]) == 0
    assert all(request["max_output_tokens"] == 256 for request in sdk.requests)
    evidence = {path: path.read_bytes() for path in (result.run_dir / "accounting").rglob("*.json")}
    resumed = TranslationWorkflow(client=client_for(sdk), gui_settings={},
        accounting_factory=factory).run(replace(config, resume=True))
    assert resumed.success, resumed.error
    assert len(sdk.requests) == expected_calls
    assert all(path.read_bytes() == before for path, before in evidence.items())


def test_missing_usage_never_becomes_free_in_priced_workflow(tmp_path):
    sdk = FakeSDK(missing_usage=True)
    budgets = []
    result = TranslationWorkflow(client=client_for(sdk), gui_settings={},
        translation_protocol="legal_blocks_v2", accounting_factory=priced_factory(budgets)).run(
            config_for(tmp_path))
    assert result.success, result.error
    accounting = json.loads(result.run_summary_path.read_text(encoding="utf-8"))["dispatch_accounting"]
    assert accounting["coverage_status"] != "complete"
    assert accounting["cost_usd"] is None
    assert budgets[-1].status()["blocked"] is True
    assert float(budgets[-1].status()["held_usd"]) > 0
    assert len(sdk.requests) == 1


@pytest.mark.parametrize("damage", ["unreadable_checkpoint", "missing_checkpoint", "missing_completed_text",
                                   "missing_accounting_reference"])
def test_accounted_legacy_resume_never_restarts_after_evidence_damage(tmp_path, monkeypatch, damage):
    config = config_for(tmp_path)
    sdk = FakeSDK()
    workflow = TranslationWorkflow(client=client_for(sdk), gui_settings={})
    result = workflow.run(config)
    assert result.success
    evidence = {path: path.read_bytes() for path in (result.run_dir / "accounting").rglob("*.json")}
    checkpoint = workflow._last_paths.run_state_path
    if damage == "unreadable_checkpoint":
        checkpoint.write_text("not valid JSON", encoding="utf-8")
    elif damage == "missing_checkpoint":
        checkpoint.rename(checkpoint.with_suffix(".retained.json"))
    elif damage == "missing_accounting_reference":
        state = load_run_state(checkpoint)
        state.dispatch_accounting = {}
        save_run_state_atomic(checkpoint, state)
    else:
        page = result.run_dir / "pages" / "page_0001.txt"
        page.rename(page.with_suffix(".retained.txt"))
    monkeypatch.setattr(module, "clear_run_dirs", lambda *_: pytest.fail("Resume cleared evidence"))
    with pytest.raises(ValueError, match="recover"):
        workflow.run(replace(config, resume=True))
    assert len(sdk.requests) == 1
    after = {path: path.read_bytes() for path in (result.run_dir / "accounting").rglob("*.json")}
    assert after == evidence


def test_old_running_checkpoint_cannot_claim_historically_complete_cost(tmp_path):
    config = config_for(tmp_path)
    sdk = FakeSDK()
    workflow = TranslationWorkflow(client=client_for(sdk), gui_settings={})
    assert workflow.run(config).success
    old_accounting = workflow._last_paths.run_dir / "accounting"
    old_accounting.rename(old_accounting.with_name("fixture-modern-evidence"))
    state = load_run_state(workflow._last_paths.run_state_path)
    state.dispatch_accounting = {}
    state.pages["1"] = {"status": "running"}
    state.run_status = "running"
    state.finished_at = None
    save_run_state_atomic(workflow._last_paths.run_state_path, state)
    result = TranslationWorkflow(client=client_for(sdk), gui_settings={},
        accounting_factory=priced_factory([])).run(replace(config, resume=True))
    assert result.success, result.error
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert summary["dispatch_accounting"]["historical_incomplete"] is True
    assert summary["cost_estimation_status"] != "measured_all_calls"
    assert summary["dispatch_accounting"]["cost_usd"] is None


def test_injected_accounting_cannot_bypass_product_block_cap(tmp_path):
    from legalpdf_translate.usage_accounting import DispatchAccounting
    config = replace(config_for(tmp_path), budget_cap_usd=1, budget_on_exceed=BudgetExceedPolicy.BLOCK)
    sdk = FakeSDK()
    with pytest.raises(ValueError, match="BLOCK budget"):
        TranslationWorkflow(client=client_for(sdk), gui_settings={},
            accounting_factory=lambda **kwargs: DispatchAccounting(**kwargs)).run(config)
    assert not sdk.requests


def diagnostic_cost_event(result):
    events = [json.loads(line) for line in (result.run_dir / "run_events.jsonl").read_text(encoding="utf-8").splitlines()]
    return [event for event in events if event["event_type"] == "cost_estimate_summary"][-1]


def test_diagnostic_cost_matches_two_call_measured_summary(tmp_path):
    config = replace(config_for(tmp_path), diagnostics_admin_mode=True)
    source = tmp_path / "two-pages.pdf"
    with fitz.open(config.pdf_path) as original, fitz.open() as document:
        document.insert_pdf(original)
        document.insert_pdf(original)
        document.save(source)

    class UsageSDK(FakeSDK):
        def create(self, **request):
            result = super().create(**request)
            inp, out, reasoning = [(1072, 1151, 569), (596, 669, 489)][len(self.requests) - 1]
            result.usage = {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out,
                "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": reasoning}}
            return result

    result = TranslationWorkflow(client=client_for(UsageSDK()), gui_settings={},
        translation_protocol="legal_blocks_v2").run(replace(config, pdf_path=source))
    assert result.success, result.error
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    event = diagnostic_cost_event(result)
    assert event["details"]["estimated_cost"] == pytest.approx(0.028399)
    assert event["details"]["estimated_cost"] == summary["dispatch_accounting"]["cost_usd"]
    assert event["details"]["cost_estimation_status"] == "measured_all_calls"
    assert event["details"]["pricing_snapshot"] == summary["dispatch_accounting"]["pricing_snapshot"]
    assert event["counters"] == summary["dispatch_accounting"]["totals"]


@pytest.mark.parametrize("env_rate", ["1", "not-a-rate"])
def test_diagnostic_cost_uses_all_correction_calls_and_cached_snapshot_not_env(tmp_path, monkeypatch, env_rate):
    for key in ("INPUT", "OUTPUT", "REASONING"):
        monkeypatch.setenv(f"LEGALPDF_COST_{key}_PER_1M", env_rate)
    sdk = FakeSDK(correction=True)
    result = TranslationWorkflow(client=client_for(sdk), gui_settings={},
        translation_protocol="legal_blocks_v2", accounting_factory=priced_factory([])).run(
            replace(config_for(tmp_path), diagnostics_admin_mode=True))
    assert result.success, result.error
    accounting = json.loads(result.run_summary_path.read_text(encoding="utf-8"))["dispatch_accounting"]
    event = diagnostic_cost_event(result)
    assert accounting["call_count"] == 2
    assert event["details"]["estimated_cost"] == accounting["cost_usd"] == pytest.approx(.00132)
    assert event["counters"] == accounting["totals"]
    assert event["counters"]["cached_input_tokens"] == 40
    assert event["counters"]["output_tokens"] == 120
    assert event["counters"]["reasoning_tokens"] == 60
    assert event["details"]["pricing_snapshot"]["snapshot_id"] == "offline-workflow-fixture"


@pytest.mark.parametrize("unknown", ["usage", "model", "tier"])
def test_diagnostic_partial_accounting_keeps_total_unknown(tmp_path, unknown):
    class PartialSDK(FakeSDK):
        def create(self, **request):
            result = super().create(**request)
            if len(self.requests) == 2:
                if unknown == "usage":
                    result.usage = None
                elif unknown == "model":
                    result.model = "unpriced-test-model"
                else:
                    result.service_tier = "unpriced-test-tier"
            return result

    result = TranslationWorkflow(client=client_for(PartialSDK(correction=True)), gui_settings={},
        translation_protocol="legal_blocks_v2").run(replace(config_for(tmp_path), diagnostics_admin_mode=True))
    assert result.success, result.error
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    accounting = summary["dispatch_accounting"]
    event = diagnostic_cost_event(result)
    assert accounting["coverage_status"] == "incomplete"
    assert event["details"]["estimated_cost"] is accounting["cost_usd"] is None
    assert event["details"]["known_cost_usd"] == accounting["known_cost_usd"] == pytest.approx(.0009835)
    assert event["details"]["cost_estimation_status"] == summary["cost_estimation_status"] == "incomplete_all_calls"
    assert event["details"]["coverage_status"] == "incomplete"
    assert event["counters"] == accounting["totals"]


def test_diagnostic_historical_unknown_cost_cannot_fall_back_to_page_estimate(tmp_path):
    config = replace(config_for(tmp_path), diagnostics_admin_mode=True)
    sdk = FakeSDK()
    workflow = TranslationWorkflow(client=client_for(sdk), gui_settings={})
    assert workflow.run(config).success
    old_accounting = workflow._last_paths.run_dir / "accounting"
    old_accounting.rename(old_accounting.with_name("fixture-retained-accounting"))
    state = load_run_state(workflow._last_paths.run_state_path)
    state.dispatch_accounting = {}
    save_run_state_atomic(workflow._last_paths.run_state_path, state)
    result = workflow.run(replace(config, resume=True))
    assert result.success
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    event = diagnostic_cost_event(result)
    assert summary["dispatch_accounting"]["historical_incomplete"]
    assert event["details"]["estimated_cost"] is None
    assert event["details"]["cost_estimation_status"] == summary["cost_estimation_status"] == "not_evaluated_all_calls"
    assert event["details"]["coverage_status"] == "incomplete"
    assert len(sdk.requests) == 1


def test_diagnostic_measured_cost_survives_docx_write_failure(tmp_path, monkeypatch):
    def failed_assembly(*args, **kwargs):
        raise OSError("Fictional DOCX write failure")

    monkeypatch.setattr(module, "assemble_docx", failed_assembly)
    sdk = FakeSDK()
    result = TranslationWorkflow(client=client_for(sdk), gui_settings={}).run(
        replace(config_for(tmp_path), diagnostics_admin_mode=True))
    assert not result.success and result.error == "docx_write_failed"
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    event = diagnostic_cost_event(result)
    assert event["details"]["estimated_cost"] == summary["dispatch_accounting"]["cost_usd"] == pytest.approx(.0009835)
    assert event["details"]["cost_estimation_status"] == "measured_all_calls"
    assert len(sdk.requests) == 1
