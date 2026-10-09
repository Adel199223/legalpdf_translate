"""Explicit ordinary layout recovery keeps translation and failed billing immutable."""
from __future__ import annotations

from decimal import Decimal
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import workflow as workflow_module
from legalpdf_translate import ordinary_layout_accounting as layout_accounting_module
from legalpdf_translate.accounting_policy import OrdinaryAccountingPolicy
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.ordinary_layout_accounting import OrdinaryLayoutAccounting, verified_page_ceiling
from legalpdf_translate.ordinary_layout_contracts import LayoutSuggestionPolicy
from legalpdf_translate.ordinary_layout_service import _read
from legalpdf_translate.usage_accounting import _state_fingerprint, _ceiling_for
from tests.test_ordinary_auto_layout_workflow import _app, _proposal, _source, _start, _wait


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "run_translation_auth_test",
        lambda *a, **k: pytest.fail("Unexpected authentication call"))
    monkeypatch.setattr(workflow_module, "resolve_openai_key_with_source",
        lambda *a, **k: pytest.fail("Unexpected ambient credentials"))


def _success_layout_provider(app, requests, *, hold_first: tuple[Event, Event] | None = None):
    def provider(job, policy):
        def create(**request):
            requests.append(request)
            if hold_first is not None and len(requests) == 2:
                entered, release = hold_first
                entered.set()
                if not release.wait(20):
                    raise TimeoutError("Fictional recovery page was not released")
            manager = app.state.ordinary_layouts.manager_for_context(
                app.state.shadow_context, job.mode, job.workspace_id)
            review = manager.service.state(job.job_id)["review"]
            page = job.selected_pages[len(requests) - 2]
            return SimpleNamespace(id=f"fictional-recovery-{page}", model=policy.model,
                status="completed", service_tier="default", output=[],
                output_text=json.dumps(_proposal(review, page)),
                usage={"input_tokens": 80, "output_tokens": 60, "total_tokens": 140,
                    "input_tokens_details": {"cached_tokens": 0},
                    "output_tokens_details": {"reasoning_tokens": 0}})
        return OpenAIResponsesClient(model=policy.model,
            sdk_client=SimpleNamespace(base_url="https://api.openai.com/v1/",
                responses=SimpleNamespace(create=create)),
            max_transport_retries=0, pre_call_jitter_seconds=0)
    return provider


def test_explicit_historical_eight_thousand_token_policy_keeps_its_own_accounting_bound(tmp_path):
    accounting = OrdinaryLayoutAccounting(jobs=object())
    budget = ReservationBudget(tmp_path / "budget.json", cap_usd="10", identity={"case": "old-layout"})
    accounting._source = lambda job: (object(), tmp_path, Decimal("0"))
    accounting._budget = lambda job, meter, folder: budget
    job = SimpleNamespace(job_id="old-layout", run_id="same-run", binding={"source_sha256": "a" * 64})
    for max_tokens, expected in ((8000, Decimal("0.812")), (32000, Decimal("1.148"))):
        policy = LayoutSuggestionPolicy("gpt-5.2", str(expected), str(expected),
            max_output_tokens=max_tokens, timeout_seconds=240.0 if max_tokens == 8000 else 480.0)
        meter = accounting.accountant(job, f"{max_tokens:032x}", tmp_path / str(max_tokens), policy)
        limit = meter.request_limits("openai", "layout_suggestion", policy.model)
        assert limit["max_output_tokens"] == max_tokens
        assert _ceiling_for(pricing_snapshot=meter.pricing_snapshot, provider="openai",
            model=policy.model, bounds=limit, hard=True) == expected


@pytest.mark.parametrize("resume_before_recovery", [False, True])
def test_browser_explicit_recovery_reuses_translation_and_preserves_failed_layout_cost(
    tmp_path, monkeypatch, resume_before_recovery,
):
    assert verified_page_ceiling() == Decimal("1.148")
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    output.mkdir()
    _source(source, ("digital",))
    app, jobs, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        ("English page one alpha 42",), (1,), failed_page=1, failure="incomplete")
    scope = "?mode=shadow&workspace=fictional"
    with TestClient(app) as client:
        original_id = _start(client, source, output, "EN", start=1, end=1, image_mode="off")
        first = _wait(jobs, original_id)
        assert first["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert len(translation_sdk.requests) == len(layout_requests) == 1
        run_dir = Path(first["result"]["run_dir"])
        original_intent = (run_dir / "ordinary_auto_layout" / "intent.json").read_bytes()
        pointer = json.loads((run_dir / "ordinary_auto_layout" / "operation.json").read_bytes())
        layout_service = app.state.ordinary_layouts.manager_for_context(
            app.state.shadow_context, "shadow", "fictional").service
        predecessor_op = (layout_service.root / pointer["origin_job_id"] / "baselines" /
            pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"])
        failed_result = _read(predecessor_op / "result.json")
        assert failed_result["status"] == "failed"
        assert failed_result["provider_response_status"] == "incomplete"
        assert failed_result["provider_incomplete_reason"] == "max_output_tokens"
        prior_cost = Decimal(str(_read(predecessor_op / "accounting_summary.json")["cost_usd"]))
        assert prior_cost > 0
        old_files = {p: p.read_bytes() for p in (predecessor_op / "result.json",
            predecessor_op / "accounting_summary.json",
            predecessor_op / "accounting" / "dispatch_accounting.json")}
        if resume_before_recovery:
            recovered_id = _start(client, source, output, "EN", start=1, end=1,
                image_mode="off", resume=True)
            resumed = _wait(jobs, recovered_id)
            assert resumed["result"]["automatic_layout"]["status"] == "raw_fallback"
            assert len(translation_sdk.requests) == len(layout_requests) == 1
            job_id = recovered_id
        else:
            job_id = original_id
        layout_manager = app.state.ordinary_layouts.manager_for_context(
            app.state.shadow_context, "shadow", "fictional")
        layout_manager.provider_factory = _success_layout_provider(app, layout_requests)
        started = client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope)
        assert started.status_code == 200, started.text
        result = _wait(jobs, job_id)
        assert result["result"]["automatic_layout"]["status"] == "automatic_unreviewed", result
        assert len(translation_sdk.requests) == 1 and len(layout_requests) == 2
        assert layout_requests[1]["max_output_tokens"] == 32000
        assert layout_requests[1]["timeout"] <= 480
        recovery = run_dir / "ordinary_auto_layout" / "recoveries" / "layout_capacity_v2"
        assert (recovery / "intent.json").is_file() and (recovery / "candidate.json").is_file()
        assert (run_dir / "ordinary_auto_layout" / "intent.json").read_bytes() == original_intent
        assert all(path.read_bytes() == raw for path, raw in old_files.items())
        shown_response = client.get(f"/api/translation/jobs/{job_id}" + scope)
        assert shown_response.status_code == 200, shown_response.text
        shown = shown_response.json()["normalized_payload"]["job"]
        assert shown["delivery"]["kind"] == "automatic_unreviewed"
        assert shown["ordinary_layout"]["budget"]["authorization_nonce"] == "explicit_layout_capacity_recovery_v1"
        assert Decimal(shown["ordinary_layout"]["budget"]["prior_layout_cost_usd"]) == prior_cost
        costs = shown["layout_costs"]
        assert costs["complete"] and costs["operations"] == 2
        assert Decimal(costs["predecessor_cost_usd"]) == prior_cost
        assert Decimal(costs["cost_usd"]) > prior_cost
        download = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx" + scope)
        assert download.status_code == 200
        assert sha256(download.content).hexdigest() == shown["delivery"]["sha256"]
        repeated = client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope)
        assert repeated.status_code == 200 and len(layout_requests) == 2
        save = client.post("/api/translation/save-row", json={"mode": "shadow",
            "workspace_id": "fictional", "job_id": job_id,
            "baseline_id": shown["ordinary_layout"]["baseline_id"],
            "expected_delivery_generation": shown["delivery"]["generation"],
            "form_values": {**shown["result"]["save_seed"], "rate_per_word": ".027",
                "expected_total_mode": "auto"}})
        assert save.status_code == 200, save.text
        assert all(path.read_bytes() == raw for path, raw in old_files.items())
        after_id = _start(client, source, output, "EN", start=1, end=1,
            image_mode="off", resume=True)
        after_resume = _wait(jobs, after_id)
        assert after_resume["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert len(translation_sdk.requests) == 1 and len(layout_requests) == 2
        reused = client.post(f"/api/translation/jobs/{after_id}/layout/recover" + scope)
        assert reused.status_code == 200, reused.text
        after = _wait(jobs, after_id)
        assert after["result"]["automatic_layout"]["status"] == "automatic_unreviewed", after
        assert after["result"]["automatic_layout"]["reused_durable_candidate"] is True
        assert len(translation_sdk.requests) == 1 and len(layout_requests) == 2
        after_shown = client.get(f"/api/translation/jobs/{after_id}" + scope).json()["normalized_payload"]["job"]
        after_docx = client.get(f"/api/translation/jobs/{after_id}/artifact/output_docx" + scope)
        assert after_docx.status_code == 200 and after_docx.content == download.content
        assert Decimal(after_shown["layout_costs"]["cost_usd"]) == Decimal(costs["cost_usd"])


def test_recovery_rejects_changed_predecessor_journal_without_new_dispatch(tmp_path, monkeypatch):
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    output.mkdir()
    _source(source, ("digital",))
    app, jobs, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        ("English page one alpha 42",), (1,), failed_page=1, failure="incomplete")
    scope = "?mode=shadow&workspace=fictional"
    with TestClient(app) as client:
        job_id = _start(client, source, output, "EN", start=1, end=1, image_mode="off")
        first = _wait(jobs, job_id)
        run_dir = Path(first["result"]["run_dir"])
        pointer = json.loads((run_dir / "ordinary_auto_layout" / "operation.json").read_bytes())
        service = app.state.ordinary_layouts.manager_for_context(
            app.state.shadow_context, "shadow", "fictional").service
        journal_path = (service.root / pointer["origin_job_id"] / "baselines" / pointer["baseline_id"] /
            "suggestions" / pointer["operation_nonce"] / "accounting" / "dispatch_accounting.json")
        journal = json.loads(journal_path.read_bytes())
        journal["events"].append({"event": "begin", "call_id": "new-unsettled-request",
            "provider": "openai", "purpose": "layout_suggestion", "page_number": 1})
        journal["fingerprint"] = _state_fingerprint(journal)
        journal_path.write_text(json.dumps(journal), encoding="utf-8")
        started = client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope)
        assert started.status_code == 200
        result = _wait(jobs, job_id)
        assert result["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert len(translation_sdk.requests) == len(layout_requests) == 1
        assert not (run_dir / "ordinary_auto_layout" / "recoveries" / "layout_capacity_v2" /
            "operation.json").exists()


def test_cancel_recovery_stops_before_second_page_and_reentry_does_not_dispatch(tmp_path, monkeypatch):
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    output.mkdir()
    _source(source, ("digital", "digital"))
    app, jobs, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        ("English page one alpha 42", "English page two beta 73"), (1, 2),
        failed_page=1, failure="incomplete")
    scope = "?mode=shadow&workspace=fictional"
    entered, release = Event(), Event()
    with TestClient(app) as client:
        job_id = _start(client, source, output, "EN", start=1, end=2, image_mode="off")
        initial = _wait(jobs, job_id)
        assert initial["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert len(translation_sdk.requests) == 2 and len(layout_requests) == 1
        manager = app.state.ordinary_layouts.manager_for_context(
            app.state.shadow_context, "shadow", "fictional")
        manager.provider_factory = _success_layout_provider(app, layout_requests,
            hold_first=(entered, release))
        started = client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope)
        assert started.status_code == 200
        assert entered.wait(20)
        cancelled = client.post(f"/api/translation/jobs/{job_id}/cancel" + scope)
        assert cancelled.status_code == 200
        release.set()
        terminal = _wait(jobs, job_id)
        assert terminal["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert len(layout_requests) == 2
        raw = client.get(f"/api/translation/jobs/{job_id}/artifact/output_docx" + scope)
        assert raw.status_code == 200
        again = client.post(f"/api/translation/jobs/{job_id}/layout/recover" + scope)
        assert again.status_code == 200
        _wait(jobs, job_id)
        assert len(translation_sdk.requests) == 2 and len(layout_requests) == 2


def test_old_eight_thousand_token_checkpoint_resumes_then_recovers_at_current_bound(tmp_path, monkeypatch):
    source, output = tmp_path / "source.pdf", tmp_path / "output"
    output.mkdir()
    _source(source, ("digital",))
    original_catalog = layout_accounting_module.layout_accounting_policy()
    args = original_catalog.accounting_arguments(today=date(2026, 10, 9))
    args["dispatch_limits"]["openai:layout_suggestion:gpt-5.2"]["max_output_tokens"] = 8000
    old_catalog = OrdinaryAccountingPolicy.from_mapping(
        pricing=args["pricing_snapshot"], limits=args["dispatch_limits"])
    old_catalog = OrdinaryAccountingPolicy(old_catalog._pricing_json, old_catalog._limits_json,
        date(2026, 10, 9))
    app, jobs, translation_sdk, layout_requests = _app(tmp_path, monkeypatch,
        ("English page one alpha 42",), (1,), failed_page=1, failure="incomplete")
    scope = "?mode=shadow&workspace=fictional"
    with TestClient(app) as client:
        with monkeypatch.context() as old:
            old.setattr(layout_accounting_module, "layout_accounting_policy", lambda: old_catalog)
            old.setattr(layout_accounting_module, "PAGE_CEILING", Decimal("0.812"))
            old.setattr(layout_accounting_module.OrdinaryLayoutAccounting, "policy",
                lambda self, job: LayoutSuggestionPolicy("gpt-5.2", ".812", ".812",
                    max_output_tokens=8000, timeout_seconds=240.0))
            original_id = _start(client, source, output, "EN", start=1, end=1, image_mode="off")
            failed = _wait(jobs, original_id)
            assert failed["result"]["automatic_layout"]["status"] == "raw_fallback"
            assert layout_requests[0]["max_output_tokens"] == 8000
        assert len(translation_sdk.requests) == len(layout_requests) == 1
        manager = app.state.ordinary_layouts.manager_for_context(
            app.state.shadow_context, "shadow", "fictional")
        manager.suggestion_policy = app.state.ordinary_layouts._accounting.policy
        manager.provider_factory = _success_layout_provider(app, layout_requests)
        resumed_id = _start(client, source, output, "EN", start=1, end=1,
            image_mode="off", resume=True)
        resumed = _wait(jobs, resumed_id)
        assert resumed["result"]["automatic_layout"]["status"] == "raw_fallback"
        assert len(translation_sdk.requests) == len(layout_requests) == 1
        started = client.post(f"/api/translation/jobs/{resumed_id}/layout/recover" + scope)
        assert started.status_code == 200, started.text
        recovered = _wait(jobs, resumed_id)
        assert recovered["result"]["automatic_layout"]["status"] == "automatic_unreviewed", recovered
        assert len(translation_sdk.requests) == 1 and len(layout_requests) == 2
        assert layout_requests[1]["max_output_tokens"] == 32000
        shown = client.get(f"/api/translation/jobs/{resumed_id}" + scope).json()["normalized_payload"]["job"]
        assert shown["layout_costs"]["operations"] == 2
        downloaded = client.get(f"/api/translation/jobs/{resumed_id}/artifact/output_docx" + scope)
        assert downloaded.status_code == 200 and sha256(downloaded.content).hexdigest() == shown["delivery"]["sha256"]
