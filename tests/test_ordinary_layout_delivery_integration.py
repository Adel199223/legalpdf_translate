"""Fictional owned artifacts and journals; no provider, Word or mail operations."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import threading
from decimal import Decimal
from datetime import date

import pytest

from legalpdf_translate.ordinary_layout_integration import delivery_job_snapshot, open_layout_artifact, verify_open_review_copy
from legalpdf_translate.ordinary_layout_accounting import OrdinaryLayoutAccounting, layout_accounting_policy
from legalpdf_translate.ordinary_layout_contracts import OrdinaryLayoutError
from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.usage_accounting import DispatchAccounting, _ceiling_for
from tests.test_ordinary_layout_service import make_case, built, select, nonce, docx_bytes, pdf_bytes
from tests.test_translation_completion_metrics import completion_job, completion_seed


def snapshot(case, tmp_path):
    path = tmp_path / "ordinary.docx"
    path.write_bytes(case.job.reviewed_docx)
    job = completion_job(path)
    job.update(job_id=case.job.job_id, runtime_mode="shadow", workspace_id="fixture")
    job["result"]["save_seed"].update(run_id=case.job.run_id, target_lang=case.job.target_lang)
    job["result"]["run_dir"] = str(tmp_path)
    job["artifacts"] = {"output_docx": str(path), "run_dir": str(tmp_path)}
    return job


@pytest.mark.parametrize("lang", ["EN", "FR", "AR"])
def test_owned_selected_snapshot_preserves_original_seed_and_freezes(tmp_path, monkeypatch, lang):
    case = make_case(tmp_path, monkeypatch, lang)
    job = snapshot(case, tmp_path)
    original = deepcopy(job)
    artifact = built(case)
    state = select(case, artifact)
    with pytest.raises(OrdinaryLayoutError, match="precondition_required"):
        delivery_job_snapshot(case.manager, job, mutation=True)
    with pytest.raises(OrdinaryLayoutError, match="delivery_stale"):
        delivery_job_snapshot(case.manager, job, mutation=True, baseline_id=state["baseline_id"], expected_delivery_generation=3)
    selected, delivery = delivery_job_snapshot(case.manager, job, mutation=True, baseline_id=state["baseline_id"],
        expected_delivery_generation=1, freeze_nonce=nonce())
    assert delivery.frozen and selected["delivery"]["sha256"] == hashlib.sha256(delivery.path.read_bytes()).hexdigest()
    assert selected["result"]["save_seed"]["output_docx"] == str(delivery.path)
    assert job == original and selected["result"]["save_seed"]["word_count"] == delivery.word_count
    case.state["job"] = replace(case.job, reviewed_docx=docx_bytes(lang, " later external change"))
    assert delivery_job_snapshot(case.manager, job)[1].sha256 == delivery.sha256
    delivery.path.write_bytes(b"tampered")
    with pytest.raises(OrdinaryLayoutError):
        delivery_job_snapshot(case.manager, job)


def test_prepared_without_selection_never_falls_back(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    with pytest.raises(OrdinaryLayoutError):
        delivery_job_snapshot(case.manager, snapshot(case, tmp_path))


def test_explicit_open_verifies_copy_without_changing_selected_artifact(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    artifact = built(case)
    calls = []
    from legalpdf_translate.word_automation import WordAutomationResult
    monkeypatch.setattr("legalpdf_translate.word_automation.open_docx_in_word",
        lambda path: calls.append(path) or WordAutomationResult(True, "open", "Fictional document opened"))
    data = {"baseline_id": case.view["baseline_id"], "artifact_id": artifact["artifact_id"], "expected_generation": artifact["generation"]}
    result = open_layout_artifact(case.manager, case.job.job_id, data)
    assert result["open_result"]["ok"] and len(calls) == 1
    calls[0].write_bytes(b"user changed review copy")
    with pytest.raises(OrdinaryLayoutError, match="review_copy_changed"):
        open_layout_artifact(case.manager, case.job.job_id, data)
    assert len(calls) == 1 and case.manager.state(case.job.job_id)["delivery"] is None
    case.manager.output_review_guard = lambda *args: verify_open_review_copy(case.manager, *args)
    with pytest.raises(OrdinaryLayoutError, match="review_copy_changed"):
        case.manager.accept_output(case.job.job_id, artifact["artifact_id"], artifact["generation"], nonce(), True,
            expected_baseline_id=case.view["baseline_id"])


def accounting_case(tmp_path, monkeypatch, hard=False):
    case = make_case(tmp_path, monkeypatch)
    budget = ReservationBudget(tmp_path / "shared.json", cap_usd="2", identity={"fictional": True}) if hard else None
    accountant = DispatchAccounting(tmp_path / "translation_accounting", run_identity={"run": case.job.run_id},
        budget_context=budget, **layout_accounting_policy().accounting_arguments())
    monkeypatch.setattr(accountant, "summary", lambda: {"cost_usd": .4, "coverage_status": "complete"})
    record = SimpleNamespace(status="completed", _completed_accountant=accountant, result_payload={"run_dir": str(tmp_path)})
    jobs = SimpleNamespace(_lock=threading.RLock(), _jobs={case.job.job_id: record})
    return case, OrdinaryLayoutAccounting(jobs), accountant, budget


def test_explicit_budget_includes_prior_cost_and_shares_every_child(tmp_path, monkeypatch):
    case, support, original, _ = accounting_case(tmp_path, monkeypatch)
    quote = support.state(case.job)
    assert quote["authorization_available"] and quote["minimum_cap_usd"] == "1.212"
    assert not (tmp_path / "ordinary_layout_budget").exists()
    authorization = nonce()
    result = support.authorize(case.job, authorization, "2")
    assert result["authorization_nonce"] == authorization and result["remaining_usd"] == "1.6"
    assert original.budget_context is None
    assert support.authorize(case.job, authorization, "2") == result
    with pytest.raises(OrdinaryLayoutError, match="already_authorized"):
        support.authorize(case.job, nonce(), "20")
    policy = support.policy(case.job)
    one = support.accountant(case.job, nonce(), tmp_path / "one", policy)
    two = support.accountant(case.job, nonce(), tmp_path / "two", policy)
    assert one.budget_context is two.budget_context
    bound = _ceiling_for(pricing_snapshot=one.pricing_snapshot, provider="openai", model=policy.model,
        bounds=one.request_limits("openai", "layout_suggestion", policy.model), hard=True)
    assert bound == Decimal("0.812")
    one.budget_context.reserve("pending", bound, {"fictional": True})
    with pytest.raises(ValueError, match="Insufficient budget"):
        two.budget_context.reserve("next", bound, {"fictional": True})


def test_existing_hard_cap_cannot_be_replaced_and_unknown_cost_blocks(tmp_path, monkeypatch):
    case, support, original, budget = accounting_case(tmp_path, monkeypatch, hard=True)
    assert support.state(case.job)["shared_existing_cap"]
    with pytest.raises(OrdinaryLayoutError, match="already_configured"):
        support.authorize(case.job, nonce(), "200")
    assert support.accountant(case.job, nonce(), tmp_path / "child", support.policy(case.job)).budget_context is budget
    monkeypatch.setattr(original, "summary", lambda: {"cost_usd": None})
    assert not support.state(case.job)["authorization_available"]
    with pytest.raises(OrdinaryLayoutError, match="accounting_incomplete"):
        support.policy(case.job)


def test_verified_pricing_reference_expires_against_actual_future_date():
    policy = layout_accounting_policy()
    assert policy.accounting_arguments(today=date(2026, 10, 9))["pricing_snapshot"] is not None
    assert policy.accounting_arguments(today=date(2026, 11, 10))["pricing_snapshot"] is None
    assert policy.accounting_arguments(today=date(2026, 10, 8))["pricing_snapshot"] is None


def test_job_bound_save_cannot_update_another_historical_run(tmp_path, monkeypatch):
    from legalpdf_translate import translation_service as service
    monkeypatch.setattr(service, "build_translation_capability_flags", lambda **_: {})
    output = tmp_path / "fictional.docx"; output.write_bytes(docx_bytes())
    seed = completion_seed(output)
    seed.update(run_id="older-run", target_lang="EN")
    args = {"settings_path": tmp_path / "settings.json", "job_log_db_path": tmp_path / "jobs.sqlite"}
    first = service.save_translation_row(**args, form_values=seed, seed_payload=seed)
    before = service.list_translation_history(db_path=args["job_log_db_path"])
    with pytest.raises(ValueError, match="does not belong"):
        service.save_translation_row(**args, form_values=seed, seed_payload={**seed, "run_id": "new-run"},
            row_id=first["saved_result"]["row_id"], word_count_docx=output, owned_run_id="new-run")
    assert service.list_translation_history(db_path=args["job_log_db_path"]) == before


def test_production_policy_enforces_image_bound_default_tier_and_shared_settlement(tmp_path, monkeypatch):
    from legalpdf_translate.openai_client import OpenAIResponsesClient
    from legalpdf_translate.usage_accounting import accounting_context
    case, support, _, _ = accounting_case(tmp_path, monkeypatch)
    support.authorize(case.job, nonce(), "2")
    policy = support.policy(case.job)
    accountant = support.accountant(case.job, nonce(), tmp_path / "image_call", policy)
    calls = []
    def create(**request):
        calls.append(request)
        assert request["service_tier"] == "default" and request["max_output_tokens"] == 8000
        assert accountant.budget_context.status()["held_usd"] == "0.812000000"
        return SimpleNamespace(id="fictional-image-response", model="gpt-5.2-2025-12-11", service_tier="default",
            status="completed", output=[], output_text="{}", usage={"input_tokens": 100, "output_tokens": 10,
                "total_tokens": 110, "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}})
    client = OpenAIResponsesClient(model=policy.model, max_transport_retries=0, pre_call_jitter_seconds=0,
        sdk_client=SimpleNamespace(base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create)))
    with accounting_context(accountant, purpose="layout_suggestion", page_number=1):
        client.create_page_response(instructions="Fictional layout", prompt_text="Fictional paragraph",
            effort="high", image_data_url="data:image/png;base64,AA==", image_detail="high", max_output_tokens=8000)
    assert len(calls) == 1 and accountant.summary()["cost_usd"] == pytest.approx(.000315)
    assert Decimal(accountant.budget_context.status()["known_spend_usd"]) == Decimal("0.400315")


def test_completed_job_snapshots_before_external_edits_and_preserves_page_map(tmp_path):
    from legalpdf_translate.translation_service import TranslationJobManager, _ManagedTranslationJob, _serialize_run_config
    from legalpdf_translate.types import RunConfig, TargetLang
    source = tmp_path / "source.pdf"; source.write_bytes(pdf_bytes())
    output = tmp_path / "output.docx"; output.write_bytes(docx_bytes())
    original = output.read_bytes()
    output.with_suffix(".source_map.json").write_text(json.dumps({"docx_sha256": hashlib.sha256(original).hexdigest(),
        "pages": [{"source_page_number": 1, "blocks": [{"location": {"kind": "body_paragraph", "paragraph_index": i}} for i in range(2)]}]}))
    config = RunConfig(pdf_path=source, output_dir=tmp_path, target_lang=TargetLang.EN, end_page=1)
    jobs = TranslationJobManager()
    record = _ManagedTranslationJob("tx-123456abcdef", "translate", "shadow", "fixture", "now", "now", "running", "",
        _serialize_run_config(config), {}, {}, _config=config)
    jobs._jobs[record.job_id] = record
    seed = completion_seed(output); seed.update(run_id="run-fictional", target_lang="EN")
    jobs._mark_finished(job_id=record.job_id, status="completed", status_text="done",
        result={"run_dir": str(tmp_path), "save_seed": seed}, artifacts={"output_docx": str(output)})
    output.write_bytes(docx_bytes(suffix=" edited"))
    trusted = jobs.trusted_ordinary_layout_job(record.job_id, runtime_mode="shadow", workspace_id="fixture")
    assert trusted.original_docx == original and trusted.reviewed_docx == output.read_bytes()
    assert trusted.page_groups == {}  # Changed wording cannot silently inherit source associations.
    assert jobs.get_job(record.job_id)["result"]["save_seed"] == seed
    source.write_bytes(b"changed")
    with pytest.raises(OrdinaryLayoutError, match="original_changed"):
        jobs.trusted_ordinary_layout_job(record.job_id, runtime_mode="shadow", workspace_id="fixture")


@pytest.mark.parametrize("flag", ["draft_created", "status", "finalization_state"])
def test_already_finalized_guard_has_no_native_or_mail_side_effect(tmp_path, monkeypatch, flag):
    from tests.test_gmail_browser_service import _translation_batch_session
    from legalpdf_translate.gmail_browser_service import GmailBrowserSessionManager
    session = _translation_batch_session(tmp_path)
    setattr(session, flag, True if flag == "draft_created" else "draft_ready")
    manager = GmailBrowserSessionManager()
    manager._workspace(runtime_mode="shadow", workspace_id="fixture").batch_session = session
    monkeypatch.setattr(manager, "preflight_batch_finalization", lambda **_: pytest.fail("Native preflight must not run"))
    with pytest.raises(ValueError, match="already has its final draft"):
        manager.finalize_batch(runtime_mode="shadow", workspace_id="fixture", settings_path=tmp_path / "settings.json",
            output_filename=None, profile_id=None)


def test_changed_staged_hash_rejected_before_finalization_preflight(tmp_path, monkeypatch):
    from tests.test_gmail_browser_service import _translation_batch_session
    from legalpdf_translate.gmail_browser_service import GmailBrowserSessionManager
    session = _translation_batch_session(tmp_path)
    session.confirmed_items[0] = replace(session.confirmed_items[0], delivery_sha256="0" * 64)
    manager = GmailBrowserSessionManager()
    manager._workspace(runtime_mode="shadow", workspace_id="fixture").batch_session = session
    monkeypatch.setattr(manager, "preflight_batch_finalization", lambda **_: pytest.fail("No preflight after hash mismatch"))
    with pytest.raises(ValueError, match="attachment changed"):
        manager.finalize_batch(runtime_mode="shadow", workspace_id="fixture", settings_path=tmp_path / "settings.json",
            output_filename=None, profile_id=None)


def test_real_routes_selected_bytes_save_reuse_and_gmail_freeze(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from legalpdf_translate.shadow_web import app as browser
    from legalpdf_translate import translation_service, gmail_browser_service
    from legalpdf_translate.gmail_batch import GmailBatchSession, DownloadedGmailAttachment
    from tests.test_gmail_browser_service import _load_result
    case = make_case(tmp_path, monkeypatch)
    artifact = built(case)
    select(case, artifact)
    job = snapshot(case, tmp_path)
    source = tmp_path / "source.pdf"; source.write_bytes(case.job.source_pdf)
    job["config"] = {"source_path": str(source), "start_page": 1}
    jobs = SimpleNamespace(get_job=lambda identity: deepcopy(job) if identity == job["job_id"] else None)
    gmail = gmail_browser_service.GmailBrowserSessionManager()
    loaded = _load_result(message_id="fictional-message", thread_id="fictional-thread", subject="Fictional",
        account_email="fictional@example.test", attachment_ids=("fictional-attachment",))
    downloaded = DownloadedGmailAttachment(loaded.message.attachments[0], source, 1, 1)
    session = GmailBatchSession(intake_context=loaded.intake_context, message=loaded.message, gog_path=loaded.gog_path,
        account_email=loaded.account_email, downloaded_attachments=(downloaded,), download_dir=tmp_path,
        selected_target_lang="EN", effective_output_dir=tmp_path)
    gmail._workspace(runtime_mode="shadow", workspace_id="fixture").batch_session = session
    services = replace(browser.offline_browser_app_services(state_root=tmp_path / "browser"),
        translation_jobs_factory=lambda: jobs, gmail_sessions_factory=lambda: gmail,
        ordinary_layout_factory=lambda *args, **kwargs: case.manager)
    monkeypatch.setattr(translation_service, "build_translation_capability_flags", lambda **_: {})
    monkeypatch.setattr(browser, "build_translation_capability_flags", lambda **_: {})
    monkeypatch.setattr(gmail_browser_service, "build_gmail_browser_capability_flags", lambda **_: {})
    app = browser.create_shadow_app(repo_root=tmp_path / "repo", services=services, enable_live_gmail_bridge=False)
    scope = "?mode=shadow&workspace=fixture"
    with TestClient(app) as client:
        status = client.get(f"/api/translation/jobs/{job['job_id']}" + scope)
        assert status.status_code == 200
        view = status.json()["normalized_payload"]["job"]
        assert view["delivery"]["generation"] == 1
        download = client.get(f"/api/translation/jobs/{job['job_id']}/artifact/output_docx" + scope)
        assert hashlib.sha256(download.content).hexdigest() == view["delivery"]["sha256"]
        form = {**job["result"]["save_seed"], "target_lang": "EN", "expected_total_mode": "auto", "rate_per_word": ".027"}
        request = {"job_id": job["job_id"], "form_values": form, "baseline_id": case.view["baseline_id"],
            "expected_delivery_generation": 1}
        rejected = client.post("/api/translation/save-row" + scope, json={**request, "expected_delivery_generation": 2})
        assert rejected.status_code != 200
        saved = client.post("/api/translation/save-row" + scope, json=request)
        assert saved.status_code == 200, saved.text
        row = saved.json()["saved_result"]["row_id"]
        confirmed = client.post("/api/gmail/batch/confirm-current" + scope, json={**request, "row_id": row})
        assert confirmed.status_code == 200, confirmed.text
        item = session.confirmed_items[0]
        assert item.joblog_row_id == row and item.delivery_generation == 1
        assert item.delivery_sha256 == hashlib.sha256(download.content).hexdigest()
        assert item.staged_translated_docx_path.read_bytes() == download.content
        assert case.manager.state(case.job.job_id)["frozen"]
        assert job["result"]["save_seed"]["output_docx"] != str(item.translated_docx_path)
