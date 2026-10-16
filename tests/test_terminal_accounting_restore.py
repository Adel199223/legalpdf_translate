"""Pinned restart accounting; fictional inputs and no external services."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from legalpdf_translate import terminal_recovery as recovery
from legalpdf_translate.checkpoint import load_run_state, save_run_state_atomic
from legalpdf_translate.gmail_batch import GmailBatchSession, DownloadedGmailAttachment
from legalpdf_translate.gmail_browser_service import (GmailBrowserSessionManager,
    _serialize_batch_session, _serialize_load_result)
from legalpdf_translate.ordinary_layout_accounting import OrdinaryLayoutAccounting
from legalpdf_translate.ordinary_layout_integration import delivery_job_snapshot
from legalpdf_translate.translation_service import TranslationJobManager
from legalpdf_translate.usage_accounting import DispatchAccounting, accounting_context, _state_fingerprint
from tests.test_gmail_browser_service import _load_result
from tests.test_terminal_recovery import fixture, write
from tests.test_usage_accounting_core import _snapshot, _usage


def gmail_fixture(source, output):
    loaded = _load_result(message_id="fictional-message", thread_id="fictional-thread",
        subject="Fictional", account_email="fictional@example.test", attachment_ids=("fictional-attachment",))
    session = GmailBatchSession(intake_context=loaded.intake_context, message=loaded.message,
        gog_path=loaded.gog_path, account_email=loaded.account_email,
        downloaded_attachments=(DownloadedGmailAttachment(loaded.message.attachments[0], source),),
        download_dir=source.parent, selected_target_lang="EN", effective_output_dir=output)
    context = {"source": "gmail_intake", "session_id": session.session_id,
        "message_id": loaded.message.message_id, "thread_id": loaded.message.thread_id,
        "attachment_id": loaded.message.attachments[0].attachment_id}
    return loaded, session, context


def restart_into_app(tmp_path, app, jobs, job_id, loaded, session):
    """Capture real terminal state, then import into fresh registries and app."""
    from legalpdf_translate.shadow_web import app as browser
    context = app.state.shadow_context
    services = context.services
    manager = app.state.ordinary_layouts.manager_for_context(context, "shadow", "fictional")
    root = manager.service.root.parents[2]
    settings = services.detect_data_paths(mode="shadow", repo=context.repo_root,
        identity=context.build_identity).settings_path
    if not settings.exists():
        settings.parent.mkdir(parents=True, exist_ok=True)
        write(settings, {})
    raw_path, overlay_path, gmail_path = [tmp_path / name for name in ("raw.json", "overlay.json", "gmail.json")]
    write(raw_path, {"active_jobs": [jobs.get_job(job_id)], "runtime": {"build_sha": "a" * 40,
        "runtime_mode": "shadow", "workspace_id": "fictional", "settings_path": str(settings)}})
    write(overlay_path, delivery_job_snapshot(manager, jobs.get_job(job_id))[0])
    write(gmail_path, {"active_session": _serialize_batch_session(session, current_index=0),
        "load_result": _serialize_load_result(loaded), "review_event_id": 1,
        "message_signature": "fictional-signature", "current_handoff_context": {},
        "pending_status": "", "pending_intake_context": {}, "pending_review_open": False})
    target = {"mode": "shadow", "workspace_id": "fictional", "settings_path": str(settings),
        "layout_root": str(root), "raw_job_paths": [str(raw_path)], "job_ids": [job_id],
        "overlay_paths": [str(overlay_path)], "gmail_bootstrap_path": str(gmail_path),
        "gmail_current_path": str(gmail_path)}
    spec, capsule = tmp_path / "capture.json", tmp_path / "capsule.json"
    write(spec, {"version": recovery.VERSION, "base_sha": "a" * 40, "targets": [target]})
    pin = recovery.create_capsule(spec, capsule)
    manifest = json.loads(capsule.read_bytes())
    before = {Path(name): Path(name).read_bytes() for name in manifest["files"]}
    restored_jobs, restored_gmail = TranslationJobManager(), GmailBrowserSessionManager()
    def no_provider(*args, **kwargs):
        client = services.ordinary_layout_provider_factory(*args, **kwargs)
        client._client.responses.create = lambda **_: pytest.fail("Restarted retained recovery must not dispatch any provider request")
        return client
    new_services = replace(services, translation_jobs_factory=lambda: restored_jobs,
        gmail_sessions_factory=lambda: restored_gmail, ordinary_layout_provider_factory=no_provider)
    new_app = browser.create_shadow_app(repo_root=context.repo_root, services=new_services,
        enable_live_gmail_bridge=False)
    # Match server startup: attach app-owned runners to empty registries before
    # importing durable terminal jobs into those same registries.
    recovery.import_capsule(capsule, pin, translation_jobs=restored_jobs, gmail_sessions=restored_gmail,
        expected_targets=[{key: target[key] for key in ("mode", "workspace_id", "settings_path", "layout_root")}])
    assert all(path.read_bytes() == value for path, value in before.items())
    restored = restored_jobs._jobs[job_id]._completed_accountant
    assert isinstance(restored, DispatchAccounting) and restored.can_retry
    assert restored.summary()["coverage_status"] == "complete"
    new_manager = new_app.state.ordinary_layouts.manager_for_context(new_app.state.shadow_context,
        "shadow", "fictional")
    trusted = new_manager._job(job_id)
    budget = new_app.state.ordinary_layouts._accounting.state(trusted)
    assert budget["authorized"] is True, budget
    assert all(path.read_bytes() == value for path, value in before.items())
    return new_app, restored_jobs


def accounting_case(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch, correction=True)
    state = load_run_state(case[7].run_state_path)
    state.dispatch_accounting = {"id": "a" * 32, "historical_incomplete": False}
    save_run_state_atomic(case[7].run_state_path, state)
    identity = {"accounting_id": "a" * 32, "source_sha256": state.pdf_fingerprint,
        "context_hash": state.context_hash, "language": state.lang, "protocol": "legacy_text_v1",
        "model": "model-a", "protocol_identity": {},
        "selection": [state.selection_start_page, state.selection_end_page], "run_started_at": state.run_started_at}
    accountant = DispatchAccounting(case[7].run_dir / "accounting" / ("a" * 32),
        run_identity=identity, pricing_snapshot=_snapshot(),
        dispatch_limits={"openai:translation": {"requested_model": "model-a", "max_output_tokens": 200}})
    with accounting_context(accountant, purpose="translation", page_number=1):
        ticket = accountant.begin(provider="openai", requested_model="model-a", effort="high",
            request_hash="b" * 64, bounds={"max_output_tokens": 100}, billing_scope="offline_fixture")
    accountant.finish(ticket, outcome="succeeded", usage=_usage(), response_id="fictional-response",
        actual_model="model-a", actual_service_tier="default")
    return case, accountant


def import_case(tmp_path, case):
    capsule = tmp_path / "capsule.json"
    pin = recovery.create_capsule(case[0], capsule)
    jobs = TranslationJobManager()
    recovery.import_capsule(capsule, pin, translation_jobs=jobs,
        gmail_sessions=GmailBrowserSessionManager(), expected_targets=case[1])
    return jobs, capsule, pin


def test_capsule_restores_saved_rates_limits_and_cumulative_cost_without_repricing(tmp_path, monkeypatch):
    case, original = accounting_case(tmp_path, monkeypatch)
    before = original.journal_path.read_bytes()
    # The older seed is intentionally different: resumed cumulative accounting
    # cannot be compared with an immutable predecessor's earlier cost.
    jobs, _, _ = import_case(tmp_path, case)
    restored = jobs._jobs["tx-fictional"]._completed_accountant
    assert restored.summary() == original.summary()
    assert restored.dispatch_limits == original.dispatch_limits
    assert restored.pricing_snapshot.to_mapping() == original.pricing_snapshot.to_mapping()
    assert restored.can_retry and restored.hard_budget is False
    assert original.journal_path.read_bytes() == before
    assert jobs.get_job("tx-fictional")["result"]["save_seed"]["api_cost"] == .25


@pytest.mark.parametrize("mutation", ["unknown", "inflight", "historical", "hard", "missing_catalog"])
def test_incomplete_or_hard_accounting_cannot_authorize_layout_after_restart(tmp_path, monkeypatch, mutation):
    case, original = accounting_case(tmp_path, monkeypatch)
    data = json.loads(original.journal_path.read_bytes())
    if mutation == "unknown":
        data["events"][-1]["cost_usd"] = None
        data["events"][-1]["cost_status"] = "pricing_unavailable"
    if mutation == "inflight": data["events"].pop()
    if mutation == "historical":
        data["historical_incomplete"] = True
        state = load_run_state(case[7].run_state_path)
        state.dispatch_accounting["historical_incomplete"] = True
        save_run_state_atomic(case[7].run_state_path, state)
    if mutation == "hard": data["budget_context"] = {"hard": True, "identity_hash": "c" * 64}
    if mutation == "missing_catalog": data.pop("pricing_catalog")
    data["fingerprint"] = _state_fingerprint(data)
    write(original.journal_path, data)
    before = original.journal_path.read_bytes()
    jobs, _, _ = import_case(tmp_path, case)
    accountant = jobs._jobs["tx-fictional"]._completed_accountant
    if mutation in {"hard", "missing_catalog"}: assert accountant is None
    else: assert accountant.summary()["cost_usd"] is None
    trusted = jobs.trusted_ordinary_layout_job("tx-fictional", runtime_mode="shadow", workspace_id="fixture")
    state = OrdinaryLayoutAccounting(jobs).state(trusted)
    assert state["authorized"] is False and state["authorization_available"] is False
    assert original.journal_path.read_bytes() == before


@pytest.mark.parametrize("mutation", ["source", "context", "language", "selection", "start", "protocol",
    "requested_model", "missing", "malformed", "fingerprint"])
def test_invalid_accounting_evidence_rejects_capsule_atomically(tmp_path, monkeypatch, mutation):
    case, original = accounting_case(tmp_path, monkeypatch)
    data = json.loads(original.journal_path.read_bytes())
    key = {"source": "source_sha256", "context": "context_hash", "language": "language",
        "selection": "selection", "start": "run_started_at", "protocol": "protocol"}.get(mutation)
    if key:
        data["run_identity"][key] = [2, 2] if key == "selection" else "different"
    if mutation == "requested_model": data["events"][0]["requested_model"] = "different"
    if mutation == "malformed": data["events"] = "invalid"
    data["fingerprint"] = _state_fingerprint(data)
    if mutation == "fingerprint": data["fingerprint"] = "f" * 64
    write(original.journal_path, data)
    if mutation == "missing": original.journal_path.unlink()
    with pytest.raises(recovery.RecoveryError):
        import_case(tmp_path, case)


def test_changed_pinned_journal_rejects_import_without_registry_changes(tmp_path, monkeypatch):
    case, original = accounting_case(tmp_path, monkeypatch)
    capsule = tmp_path / "capsule.json"
    pin = recovery.create_capsule(case[0], capsule)
    original.journal_path.write_bytes(original.journal_path.read_bytes() + b" ")
    jobs, gmail = TranslationJobManager(), GmailBrowserSessionManager()
    with pytest.raises(recovery.RecoveryError):
        recovery.import_capsule(capsule, pin, translation_jobs=jobs,
            gmail_sessions=gmail, expected_targets=case[1])
    assert not jobs._jobs and not gmail._workspaces


@pytest.mark.parametrize("mutation", ["nondict_event", "unknown_event", "duplicate_begin", "duplicate_finish",
    "orphan_finish", "unknown_outcome", "missing_usage", "invalid_usage", "missing_token", "wrong_token_type",
    "negative_token", "inconsistent_total", "unknown_cost_status", "limits_container", "limits_value", "limits_pairs", "historical_flag",
    "missing_purpose", "missing_provider", "missing_requested_model", "missing_request_hash", "invalid_attempt",
    "invalid_page", "invalid_bounds", "nonzero_not_dispatched", "numeric_provider", "duplicate_response"])
def test_malformed_retained_accounting_rejects_atomically(tmp_path, monkeypatch, mutation):
    case, original = accounting_case(tmp_path, monkeypatch)
    capsule = tmp_path / "malformed_capsule.json"
    recovery.create_capsule(case[0], capsule)
    data = json.loads(original.journal_path.read_bytes())
    event = data["events"][-1]
    if mutation == "nondict_event": data["events"].append(None)
    if mutation == "unknown_event": data["events"].append({"event": "other", "call_id": "other"})
    if mutation == "duplicate_begin": data["events"].append(dict(data["events"][0]))
    if mutation == "duplicate_finish": data["events"].append(dict(event))
    if mutation == "orphan_finish": event["call_id"] = "orphan"
    if mutation == "unknown_outcome": event["outcome"] = "other"
    if mutation == "missing_usage": event["usage"]["usage_status"] = "missing"
    if mutation == "invalid_usage": event["usage"]["usage_status"] = "invalid"
    if mutation == "missing_token": event["usage"].pop("input_tokens")
    if mutation == "wrong_token_type": event["usage"]["input_tokens"] = "100"
    if mutation == "negative_token": event["usage"]["input_tokens"] = -1
    if mutation == "inconsistent_total": event["usage"]["total_tokens"] = 1
    if mutation == "unknown_cost_status": event["cost_status"] = "missing_usage"
    if mutation.startswith("missing_") and mutation.removeprefix("missing_") in {
            "purpose", "provider", "requested_model", "request_hash"}:
        data["events"][0].pop(mutation.removeprefix("missing_"))
    if mutation == "invalid_attempt": data["events"][0]["attempt"] = 0
    if mutation == "invalid_page": data["events"][0]["page_number"] = -1
    if mutation == "invalid_bounds": data["events"][0]["bounds"] = []
    if mutation == "nonzero_not_dispatched": event["outcome"] = "not_dispatched"
    if mutation == "numeric_provider": data["events"][0]["provider"] = 1
    if mutation == "duplicate_response":
        duplicate_begin, duplicate_finish = dict(data["events"][0]), dict(event)
        duplicate_begin["call_id"] = duplicate_finish["call_id"] = "other-call"
        data["events"].extend((duplicate_begin, duplicate_finish))
    if mutation == "limits_container": data["dispatch_limits"] = []
    if mutation == "limits_value": data["dispatch_limits"] = {"openai:translation": 1}
    if mutation == "limits_pairs": data["dispatch_limits"] = {"openai:translation": [["requested_model", "model-a"]]}
    if mutation == "historical_flag":
        state = load_run_state(case[7].run_state_path)
        state.dispatch_accounting["historical_incomplete"] = "false"
        save_run_state_atomic(case[7].run_state_path, state)
    data["fingerprint"] = _state_fingerprint(data)
    write(original.journal_path, data)
    # Capture normally validates before export. Deliberately repin these
    # fictional malformed bytes to exercise import's independent validation.
    manifest = recovery.decode(capsule.read_bytes())
    for name in manifest["files"]:
        value = Path(name).read_bytes()
        manifest["files"][name] = {"sha256": hashlib.sha256(value).hexdigest(), "bytes": len(value)}
    raw = recovery.encode(manifest)
    capsule.write_bytes(raw)
    pin = hashlib.sha256(raw).hexdigest()
    before = original.journal_path.read_bytes()
    jobs, gmail = TranslationJobManager(), GmailBrowserSessionManager()
    with pytest.raises(recovery.RecoveryError):
        recovery.import_capsule(capsule, pin, translation_jobs=jobs,
            gmail_sessions=gmail, expected_targets=case[1])
    assert not jobs._jobs and not gmail._workspaces
    assert original.journal_path.read_bytes() == before
