"""Fictional pinned recovery only; never provider, native Word or Gmail I/O."""
from copy import deepcopy
from pathlib import Path
import hashlib
import json
import shutil

import pytest

from legalpdf_translate import terminal_recovery as recovery
from legalpdf_translate.checkpoint import (build_run_paths, new_run_state, save_run_state_atomic,
    sha256_of_text)
from legalpdf_translate.gmail_batch import GmailBatchSession, DownloadedGmailAttachment
from legalpdf_translate.gmail_browser_service import (GmailBrowserSessionManager,
    _serialize_batch_session, _serialize_load_result)
from legalpdf_translate.ordinary_layout_integration import delivery_job_snapshot
from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
from legalpdf_translate.run_workspace_lock import run_workspace_slot
from legalpdf_translate.translation_service import TranslationJobManager, _ManagedTranslationJob, _serialize_run_config
from legalpdf_translate.types import RunConfig, TargetLang
from tests.test_gmail_browser_service import _load_result
from tests.test_ordinary_layout_service import docx_bytes, pdf_bytes, fake_prepare, nonce
from tests.test_ordinary_text_correction import action


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def fixture(tmp_path, monkeypatch, *, correction=False, owned_temp=False):
    download_dir = tmp_path
    if owned_temp:
        temp_root = tmp_path / "system-temp"; temp_root.mkdir()
        monkeypatch.setattr(recovery.tempfile, "gettempdir", lambda: str(temp_root))
        download_dir = temp_root / "legalpdf_gmail_batch_fictional"; download_dir.mkdir()
    source = download_dir / "fictional.pdf"; source.write_bytes(pdf_bytes())
    output = tmp_path / "outputs"; output.mkdir()
    layout = tmp_path / "app"; layout.mkdir()
    settings = layout / "settings.json"; write(settings, {})
    loaded = _load_result(message_id="fictional-message", thread_id="fictional-thread",
        subject="Fictional", account_email="fictional@example.test", attachment_ids=("fictional-attachment",))
    session = GmailBatchSession(intake_context=loaded.intake_context, message=loaded.message,
        gog_path=loaded.gog_path, account_email=loaded.account_email,
        downloaded_attachments=(DownloadedGmailAttachment(loaded.message.attachments[0], source),),
        download_dir=download_dir, selected_target_lang="EN", effective_output_dir=output)
    config = RunConfig(source, output, TargetLang.EN, gmail_batch_context={"source": "gmail_intake",
        "session_id": session.session_id, "message_id": loaded.message.message_id,
        "thread_id": loaded.message.thread_id, "attachment_id": loaded.message.attachments[0].attachment_id})
    paths = build_run_paths(output, source, TargetLang.EN)
    paths.run_dir.mkdir(); paths.pages_dir.mkdir()
    with run_workspace_slot(paths.run_dir):
        pass
    state = new_run_state(config=config, paths=paths, pdf_fingerprint=hashlib.sha256(source.read_bytes()).hexdigest(),
        context_hash=sha256_of_text(None), total_pages=1, selected_pages=[1])
    state.run_status = "completed" if correction else "failed"
    state.pages["1"]["status"] = "done" if correction else "failed"
    state.done_count = 1 if correction else 0; state.failed_count = 0 if correction else 1; state.pending_count = 0
    if correction:
        (paths.pages_dir / "page_0001.txt").write_text("Fictional court\nPreserve all words.", encoding="utf-8")
    save_run_state_atomic(paths.run_state_path, state)
    raw_docx = paths.run_dir / "fictional.docx"; raw_docx.write_bytes(docx_bytes())
    seed = {"run_id": paths.run_dir.name, "target_lang": "EN", "output_docx": str(raw_docx),
        "api_cost": .25, "estimated_api_cost": .25, "word_count": 7}
    job = _ManagedTranslationJob("tx-fictional", "translate", "shadow", "fixture", "created", "updated",
        state.run_status, "Fictional", _serialize_run_config(config), {}, {}, result_payload={
            "run_dir": str(paths.run_dir), "source_sha256": state.pdf_fingerprint, "save_seed": seed},
        artifacts_payload={"run_dir": str(paths.run_dir), "output_docx": str(raw_docx)}, _config=config)
    jobs = TranslationJobManager(); jobs._jobs[job.job_id] = job
    if correction:
        jobs._capture_ordinary_baseline(job)
        monkeypatch.setattr("legalpdf_translate.saved_docx_layout_service._prepare_import", fake_prepare)
        manager = OrdinaryLayoutManager(layout, mode="shadow", workspace_id="fixture",
            job_resolver=lambda _: jobs.trusted_ordinary_layout_job(job.job_id, runtime_mode="shadow", workspace_id="fixture"))
        manager.prepare(job.job_id, nonce())
        trusted = manager._job(job.job_id)
        service = manager.service
        view = service.text_correction_state(trusted)
        draft = service.draft_text_correction(trusted, nonce(), view["parent"],
            [action(view["paragraphs"][0]["paragraph_id"], "Explicit fictional correction")])
        service.approve_text_correction(trusted, draft["draft_id"], nonce(), True, True, "")
        overlay, _ = delivery_job_snapshot(manager, jobs.get_job(job.job_id))
    else:
        overlay = jobs.get_job(job.job_id)
    raw_path = tmp_path / "raw.json"; write(raw_path, {"active_jobs": [jobs.get_job(job.job_id)],
        "runtime": {"build_sha": "a" * 40, "runtime_mode": "shadow", "workspace_id": "fixture", "settings_path": str(settings)}})
    overlay_path = tmp_path / "overlay.json"; write(overlay_path, overlay)
    gmail_path = tmp_path / "gmail.json"
    write(gmail_path, {"active_session": _serialize_batch_session(session, current_index=0),
        "load_result": _serialize_load_result(loaded), "review_event_id": 1,
        "message_signature": "fictional-signature", "current_handoff_context": {},
        "pending_status": "", "pending_intake_context": {}, "pending_review_open": False})
    target = {"mode": "shadow", "workspace_id": "fixture", "settings_path": str(settings),
        "layout_root": str(layout), "raw_job_paths": [str(raw_path)], "job_ids": [job.job_id],
        "overlay_paths": [str(overlay_path)], "gmail_bootstrap_path": str(gmail_path), "gmail_current_path": str(gmail_path)}
    spec_path = tmp_path / "capture.json"
    write(spec_path, {"version": recovery.VERSION, "base_sha": "a" * 40, "targets": [target]})
    targets = [{key: target[key] for key in ("mode", "workspace_id", "settings_path", "layout_root")}]
    return spec_path, targets, jobs, session, raw_path, overlay_path, source, paths


def restore(tmp_path, monkeypatch, **kwargs):
    case = fixture(tmp_path, monkeypatch, **kwargs)
    capsule = tmp_path / "capsule.json"
    pin = recovery.create_capsule(case[0], capsule)
    jobs, gmail = TranslationJobManager(), GmailBrowserSessionManager()
    result = recovery.import_capsule(capsule, pin, translation_jobs=jobs, gmail_sessions=gmail, expected_targets=case[1])
    return case, capsule, pin, jobs, gmail, result


def test_failed_job_and_session_restore_without_replay_and_idempotent(tmp_path, monkeypatch):
    case, capsule, pin, jobs, gmail, result = restore(tmp_path, monkeypatch)
    assert result == {"status": "imported", "jobs": 1, "workspaces": 1}
    assert jobs.get_job("tx-fictional") == case[2].get_job("tx-fictional")
    restored = gmail._workspaces[("shadow", "fixture")]
    assert restored.batch_session.session_id == case[3].session_id
    assert restored.batch_session.downloaded_attachments[0].saved_path == case[6]
    assert restored.current_batch_index == 0 and not restored.batch_session.confirmed_items
    assert jobs._jobs["tx-fictional"]._workflow is None
    assert not jobs._reservations and not jobs._workflow_accounting
    assert recovery.import_capsule(capsule, pin, translation_jobs=jobs, gmail_sessions=gmail,
        expected_targets=case[1])["status"] == "already_imported"


def test_selected_correction_history_and_review_pending_survive(tmp_path, monkeypatch):
    case, capsule, pin, jobs, gmail, _ = restore(tmp_path, monkeypatch, correction=True)
    target = case[1][0]
    manager = OrdinaryLayoutManager(Path(target["layout_root"]), mode="shadow", workspace_id="fixture",
        job_resolver=lambda _: jobs.trusted_ordinary_layout_job("tx-fictional", runtime_mode="shadow", workspace_id="fixture"))
    selected, artifact = delivery_job_snapshot(manager, jobs.get_job("tx-fictional"))
    expected = json.loads(case[5].read_text(encoding="utf-8"))
    assert selected["delivery"] == expected["delivery"]
    assert selected["text_correction"] == expected["text_correction"]
    assert selected["text_correction"]["output_review_required"]
    assert artifact.kind == "text_corrected" and not artifact.frozen
    assert jobs.get_job("tx-fictional")["result"]["save_seed"]["api_cost"] == .25
    assert recovery.validate_capsule(capsule, pin)["jobs"] == 1


@pytest.mark.parametrize("mutation", ["source", "checkpoint", "settings", "capture", "missing", "extra"])
def test_any_changed_or_missing_evidence_refuses_entire_import(tmp_path, monkeypatch, mutation):
    case = fixture(tmp_path, monkeypatch)
    capsule = tmp_path / "capsule.json"; pin = recovery.create_capsule(case[0], capsule)
    targets = {"source": case[6], "checkpoint": case[7].run_state_path,
        "settings": Path(case[1][0]["settings_path"]), "capture": case[4], "missing": case[6]}
    if mutation == "extra":
        (case[7].run_dir / "unexpected.txt").write_text("changed", encoding="utf-8")
    elif mutation == "missing":
        targets[mutation].unlink()
    else:
        targets[mutation].write_bytes(b"changed")
    jobs, gmail = TranslationJobManager(), GmailBrowserSessionManager()
    with pytest.raises(recovery.RecoveryError):
        recovery.import_capsule(capsule, pin, translation_jobs=jobs, gmail_sessions=gmail, expected_targets=case[1])
    assert not jobs._jobs and not gmail._workspaces


@pytest.mark.parametrize("mutation", ["active", "owner", "raw_overlay", "wrong_session", "confirmed", "config", "build"])
def test_semantic_mismatch_refuses_even_newly_pinned_capture(tmp_path, monkeypatch, mutation):
    case = fixture(tmp_path, monkeypatch)
    raw = json.loads(case[4].read_text(encoding="utf-8"))
    job = raw["active_jobs"][0]
    if mutation == "active": job["status"] = "running"
    if mutation == "owner": job["workspace_id"] = "another"
    if mutation == "raw_overlay": job["layout_costs"] = {"operations": 1}
    if mutation == "wrong_session": job["config"]["gmail_batch_context"]["session_id"] = "other-session"
    if mutation == "config": job["config"]["workers"] = 6
    if mutation == "build": raw["runtime"]["build_sha"] = "b" * 40
    write(case[4], raw)
    if mutation == "confirmed":
        spec = json.loads(case[0].read_text(encoding="utf-8")); path = Path(spec["targets"][0]["gmail_current_path"])
        value = json.loads(path.read_text(encoding="utf-8")); value["active_session"]["confirmed_items"] = [{"fake": True}]
        write(path, value)
    with pytest.raises(recovery.RecoveryError):
        recovery.create_capsule(case[0], tmp_path / "capsule.json")


def test_hash_target_and_existing_registry_refuse(tmp_path, monkeypatch):
    case, capsule, pin, jobs, gmail, _ = restore(tmp_path, monkeypatch)
    for bad_pin, targets, manager in (("0" * 64, case[1], TranslationJobManager()),
            (pin, [], TranslationJobManager()), (pin, case[1], case[2])):
        with pytest.raises(recovery.RecoveryError):
            recovery.import_capsule(capsule, bad_pin, translation_jobs=manager,
                gmail_sessions=GmailBrowserSessionManager(), expected_targets=targets)


def test_delivery_cost_overlay_cannot_be_reimported_as_raw_or_changed(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch, correction=True)
    overlay = json.loads(case[5].read_text(encoding="utf-8"))
    overlay["result"]["save_seed"]["api_cost"] += .25
    write(case[5], overlay)
    with pytest.raises(recovery.RecoveryError, match="accounting_mismatch"):
        recovery.create_capsule(case[0], tmp_path / "capsule.json")


def test_import_does_not_change_any_retained_file_bytes(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch, correction=True)
    capsule = tmp_path / "capsule.json"; pin = recovery.create_capsule(case[0], capsule)
    before = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert recovery.validate_capsule(capsule, pin)["status"] == "imported"
    after = {str(p): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_owned_temp_backup_restores_same_missing_path_and_never_overwrites(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch, owned_temp=True)
    capsule = tmp_path / "capsule.json"; pin = recovery.create_capsule(case[0], capsule)
    original = case[6].read_bytes()
    assert recovery.restore_missing_sources(capsule, pin)["status"] == "sources_unchanged"
    shutil.rmtree(case[6].parent)
    with pytest.raises(recovery.RecoveryError):
        recovery.validate_capsule(capsule, pin)
    receipt = recovery.restore_missing_sources(capsule, pin)
    assert receipt == {"status": "sources_restored", "restored_files": 1, "source_directories": 1}
    assert case[6].read_bytes() == original
    assert recovery.validate_capsule(capsule, pin)["jobs"] == 1
    assert recovery.restore_missing_sources(capsule, pin)["restored_files"] == 0
    case[6].write_bytes(b"different original")
    with pytest.raises(recovery.RecoveryError, match="existing_source_changed"):
        recovery.restore_missing_sources(capsule, pin)
    assert case[6].read_bytes() == b"different original"


@pytest.mark.parametrize("mutation", ["backup_bytes", "backup_escape", "root_escape", "relative_escape", "non_source_missing", "extra"])
def test_source_restore_rejects_adversarial_backup_before_any_write(tmp_path, monkeypatch, mutation):
    case = fixture(tmp_path, monkeypatch, owned_temp=True)
    capsule = tmp_path / "capsule.json"; pin = recovery.create_capsule(case[0], capsule)
    value = json.loads(capsule.read_text(encoding="utf-8"))
    backup = value["source_backups"][0]
    first = next(iter(backup["files"].values()))
    shutil.rmtree(case[6].parent)
    if mutation == "backup_bytes": Path(first["backup_path"]).write_bytes(b"changed")
    if mutation == "backup_escape": first["backup_path"] = str(case[4])
    if mutation == "root_escape": backup["directory"] = str(tmp_path / "legalpdf_gmail_batch_other")
    if mutation == "relative_escape": backup["files"]["../escaped.pdf"] = backup["files"].pop("fictional.pdf")
    if mutation == "non_source_missing": case[7].run_state_path.unlink()
    if mutation == "extra":
        case[6].parent.mkdir(); (case[6].parent / "unowned.txt").write_bytes(b"unowned")
    if mutation in {"backup_escape", "root_escape", "relative_escape"}:
        raw = recovery.encode(value); capsule.write_bytes(raw); pin = hashlib.sha256(raw).hexdigest()
    with pytest.raises(recovery.RecoveryError):
        recovery.restore_missing_sources(capsule, pin)
    assert not case[6].exists()


def test_non_temp_sources_never_get_backups(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    capsule = tmp_path / "capsule.json"; pin = recovery.create_capsule(case[0], capsule)
    assert json.loads(capsule.read_text(encoding="utf-8"))["source_backups"] == []
    case[6].unlink()
    with pytest.raises(recovery.RecoveryError):
        recovery.restore_missing_sources(capsule, pin)
    assert not case[6].exists()


def test_public_abbreviated_build_identity_matches_full_pinned_base(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch)
    value = json.loads(case[4].read_text(encoding="utf-8")); value["runtime"]["build_sha"] = "a" * 7
    write(case[4], value)
    capsule = tmp_path / "capsule.json"; pin = recovery.create_capsule(case[0], capsule)
    assert recovery.validate_capsule(capsule, pin)["jobs"] == 1


def test_linked_backup_is_rejected(tmp_path, monkeypatch):
    case = fixture(tmp_path, monkeypatch, owned_temp=True)
    capsule = tmp_path / "capsule.json"; pin = recovery.create_capsule(case[0], capsule)
    value = json.loads(capsule.read_text(encoding="utf-8"))
    backup = Path(next(iter(value["source_backups"][0]["files"].values()))["backup_path"])
    target = tmp_path / "same-bytes.pdf"; target.write_bytes(backup.read_bytes()); backup.unlink()
    try:
        backup.symlink_to(target)
    except OSError:
        pytest.skip("Symlinks require privileges on this Windows test host")
    shutil.rmtree(case[6].parent)
    with pytest.raises(recovery.RecoveryError, match="linked_path"):
        recovery.restore_missing_sources(capsule, pin)
    assert not case[6].exists()


@pytest.mark.parametrize("stdout", [{"headers": [{"name": "Reply-To", "value": "reply@example.test"}]},
    {"body": "Please reply to reply@example.test"}])
def test_preferred_reply_email_restored_from_pinned_original_load(tmp_path, monkeypatch, stdout):
    case = fixture(tmp_path, monkeypatch)
    spec = json.loads(case[0].read_text(encoding="utf-8")); gmail_path = Path(spec["targets"][0]["gmail_current_path"])
    payload = json.loads(gmail_path.read_text(encoding="utf-8"))
    payload["load_result"]["stdout"] = json.dumps(stdout)
    write(gmail_path, payload)
    capsule = tmp_path / "capsule.json"; pin = recovery.create_capsule(case[0], capsule)
    jobs, gmail = TranslationJobManager(), GmailBrowserSessionManager()
    recovery.import_capsule(capsule, pin, translation_jobs=jobs, gmail_sessions=gmail, expected_targets=case[1])
    assert gmail._workspaces[("shadow", "fixture")].preferred_reply_email == "reply@example.test"
