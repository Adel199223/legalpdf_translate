"""Genuine reviewed source -> completed job -> explicit formatting bridge.

Only OCR/SDK, worker scheduling and unrelated result enrichment are synthetic.
No committed page, source acceptance, formatting revision or DOCX is injected.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import threading

import pytest

from legalpdf_translate import browser_formatting_review as module, translation_service as jobs_module
from legalpdf_translate.browser_formatting_review import BrowserFormattingReviewManager, BrowserFormattingReviewError
from legalpdf_translate.browser_source_review import BrowserSourceReviewError
from legalpdf_translate.run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
from legalpdf_translate.ordinary_formatting_review_service import (
    FormattingFragment, FormattingParagraph, FormattingTable, FormattingPageDecision,
    FormattingDocumentDecision, FormattingDocumentGroup,
)
from tests.test_browser_source_review import bridge_case, submit as source_submit, capture_jobs, capture_lazy_client
from tests.test_ordinary_source_review_service import local_only


def formatting_case(tmp_path, monkeypatch):
    c = bridge_case(tmp_path, monkeypatch)
    source = source_submit(c)
    queued = capture_jobs(monkeypatch)
    c.clients, c.calls = capture_lazy_client(monkeypatch)
    monkeypatch.setattr(jobs_module, "_translation_result_payload", lambda **kw: {"artifacts": {
        "run_dir": str(kw["summary"].run_dir), "output_docx": str(kw["summary"].output_docx)}})
    job = c.bridge.start_translate(**c.owner, review_id=c.view["review_id"],
        revision_id=source["revision_id"], operation_nonce="a" * 32)
    queued.pop(0)()
    c.job = c.jobs.get_job(job["job_id"])
    assert c.job["status"] == "completed", c.job["diagnostics"]
    c.scope = {**c.owner, "job_id": job["job_id"], "settings_path": c.settings}
    c.run_dir = Path(c.job["artifacts"]["run_dir"])
    c.manager = BrowserFormattingReviewManager(c.jobs)
    return c


def layout_decision(page, *, table=False, gap=None):
    """Explicit fictional choices retain complete independent line partitions."""
    fragments = []
    for parent in page["parents"]:
        source = parent["source_text"].splitlines(keepends=True)
        target = parent["target_text"].splitlines(keepends=True)
        assert len(source) == len(target)
        left = right = 0
        for src, dst in zip(source, target):
            n = len(fragments)
            box = (10 + n * 100, 10, 90 + n * 100, 30) if table else (10, 10 + n * 40, 190, 30 + n * 40)
            fragments.append(FormattingFragment(parent["parent_number"], (left, left + len(src)),
                (right, right + len(dst)), box, "body", "left", False, False,
                "Fictional operator compared both complete line selections and source box."))
            left += len(src)
            right += len(dst)
    if table:
        assert len(fragments) == 2
        body = (FormattingTable((50, 50), (((1,), (2,)),), gap),)
    else:
        body = tuple(FormattingParagraph(n) for n in range(1, len(fragments) + 1))
    return FormattingPageDecision(tuple(fragments), (), body, (), None, True, True,
        "Fictional operator", "Complete source and target comparison.")


def document_decision(count=1):
    return FormattingDocumentDecision((FormattingDocumentGroup(1, count),), True, False, True,
        "Fictional operator", "All pages and boundaries reviewed explicitly.")


def reviewed(c, *, table=False, gap=None):
    view = c.manager.prepare(**c.scope, page_matched_derivative=True)
    for page in view["pages"]:
        view = c.manager.save_page(**c.scope, review_id=view["review_id"], expected_generation=view["generation"],
            page_number=page["page_number"], decision=layout_decision(page, table=table, gap=gap))
    view = c.manager.save_document(**c.scope, review_id=view["review_id"], expected_generation=view["generation"],
        decision=document_decision(len(view["pages"])))
    return c.manager.submit(**c.scope, review_id=view["review_id"], expected_generation=view["generation"],
        reviewer="Fictional final operator", accept_formatting=True)


def originals(c):
    paths = [p for p in c.run_dir.rglob("*") if p.is_file()]
    paths += [c.settings, Path(c.job["artifacts"]["output_docx"])]
    return {p: p.read_bytes() for p in paths}


def unchanged(before):
    assert {p: p.read_bytes() for p in before} == before


def request(c, view, nonce="b" * 32):
    return {**c.scope, "review_id": view["review_id"], "revision_id": view["revision_id"], "operation_nonce": nonce}


def test_real_job_derivative_build_download_and_restart_preserve_originals(tmp_path, monkeypatch):
    c = formatting_case(tmp_path, monkeypatch)
    before = originals(c)
    assert c.job["actions"]["formatting_review"]
    declined = c.manager.prepare(**c.scope, page_matched_derivative=False)
    assert declined["status"] == "declined" and "reviewed_profile_requires_page_breaks" in declined["notice_codes"]
    view = reviewed(c, table=True, gap=(12,))
    result = c.manager.rebuild(**request(c, view))
    assert result["status"] == "built" and result["page_matched_derivative"] is True
    assert result["formatting_derivative"]["original_page_breaks"] is False
    artifact = result["artifacts"][0]
    assert result["rebuild_operations"] == [{"operation_nonce": "b" * 32, "revision_id": view["revision_id"],
        "status": "built", "artifact_id": artifact["artifact_id"]}]
    restored = BrowserFormattingReviewManager(c.jobs)
    monkeypatch.setattr(module.OrdinaryFormattingReviewService, "rebuild", lambda *_: pytest.fail("Completed nonce must never rebuild"))
    assert restored.rebuild(**request(c, view)) == result
    read = restored.read(**c.scope, review_id=view["review_id"])
    assert read["artifacts"] == [artifact] and read["revision_id"] == view["revision_id"]
    for kind in module.KINDS:
        raw = restored.artifact(**c.scope, review_id=view["review_id"], artifact_id=artifact["artifact_id"], artifact_kind=kind)
        if kind == "output_docx":
            assert raw.startswith(b"PK")
        elif kind == "source_map":
            assert json.loads(raw)["pages"][0]["tables"][0]["column_gaps_px"] == [12]
        else:
            assert json.loads(raw)["provider_dispatch_count"] == 0
    job = c.jobs.get_job(c.job["job_id"])
    assert job["artifacts"]["output_docx"] == c.job["artifacts"]["output_docx"]
    assert job["artifacts"]["reviewed_formatting"] == [artifact]
    job["artifacts"]["reviewed_formatting"].clear()
    assert c.jobs.get_job(c.job["job_id"])["artifacts"]["reviewed_formatting"] == [artifact]
    assert c.jobs._jobs[c.job["job_id"]]._config.page_breaks is False
    unchanged(before)
    assert len(c.clients) == len(c.calls) == 1
    assert str(tmp_path) not in json.dumps(read) and "draft_id" not in read


@pytest.mark.parametrize("choice", [None, 0, 1, "true"])
def test_choice_is_strict_boolean_before_any_draft(tmp_path, monkeypatch, choice):
    c = formatting_case(tmp_path, monkeypatch)
    with pytest.raises(BrowserFormattingReviewError, match="invalid_derivative_choice"):
        c.manager.prepare(**c.scope, page_matched_derivative=choice)
    assert not (c.run_dir / "browser_formatting_reviews").exists()


@pytest.mark.parametrize("changed", ["mode", "workspace", "job", "settings", "status", "context", "config"])
def test_exact_trusted_job_owner_required_on_every_read(tmp_path, monkeypatch, changed):
    c = formatting_case(tmp_path, monkeypatch)
    view = c.manager.prepare(**c.scope, page_matched_derivative=True)
    scope = dict(c.scope)
    job = c.jobs._jobs[c.job["job_id"]]
    if changed == "mode": scope["runtime_mode"] = "live"
    if changed == "workspace": scope["workspace_id"] = "workspace-2"
    if changed == "job": scope["job_id"] = "tx-" + "0" * 12
    if changed == "settings":
        scope["settings_path"] = tmp_path / "other.json"
        scope["settings_path"].write_text("{}", encoding="utf-8")
    if changed == "status": job.status = "running"
    if changed == "context": job._reviewed_source_loader = lambda: None
    if changed == "config": job._config = replace(job._config, page_breaks=True)
    with pytest.raises(BrowserFormattingReviewError):
        c.manager.read(**scope, review_id=view["review_id"])


def test_accessor_rechecks_config_after_reloading_context(tmp_path, monkeypatch):
    c = formatting_case(tmp_path, monkeypatch)
    job = c.jobs._jobs[c.job["job_id"]]
    original = job._reviewed_source_loader
    def changed():
        fresh = original()
        job._config = replace(job._config, page_breaks=True)
        return fresh
    job._reviewed_source_loader = changed
    with pytest.raises(ValueError, match="formatting_job_unavailable"):
        c.jobs.trusted_formatting_job(**c.scope)


def test_stale_generation_unaccepted_revision_and_tampered_choice_reject(tmp_path, monkeypatch):
    c = formatting_case(tmp_path, monkeypatch)
    view = c.manager.prepare(**c.scope, page_matched_derivative=True)
    decision = layout_decision(view["pages"][0])
    c.manager.save_page(**c.scope, review_id=view["review_id"], expected_generation=1, page_number=1, decision=decision)
    with pytest.raises(BrowserFormattingReviewError):
        c.manager.save_page(**c.scope, review_id=view["review_id"], expected_generation=1, page_number=1, decision=decision)
    with pytest.raises(BrowserFormattingReviewError, match="revision_unavailable"):
        c.manager.inspect(**c.scope, review_id=view["review_id"], revision_id="0" * 32)
    path = c.run_dir / "browser_formatting_reviews" / view["review_id"] / "owner.json"
    owner = json.loads(path.read_bytes()); owner["page_matched_derivative"] = 1
    path.write_text(json.dumps(owner), encoding="utf-8")
    with pytest.raises(BrowserFormattingReviewError, match="owner_changed"):
        c.manager.read(**c.scope, review_id=view["review_id"])


@pytest.mark.parametrize("stage", ["before_build", "after_build", "after_result", "after_registration"])
def test_lost_rebuild_response_never_replays_unknown_publication(tmp_path, monkeypatch, stage):
    c = formatting_case(tmp_path, monkeypatch)
    view = reviewed(c)
    real_build, real_write = module.OrdinaryFormattingReviewService.rebuild, module._write
    real_register = c.jobs.register_reviewed_formatting_artifact
    calls = []
    def build(service, revision):
        calls.append(revision)
        if stage == "before_build": raise RuntimeError("Private diagnostic must not escape")
        result = real_build(service, revision)
        if stage == "after_build": raise RuntimeError("Private diagnostic must not escape")
        return result
    def write(path, value):
        raw = real_write(path, value)
        if stage == "after_result" and path.name == "result.json": raise RuntimeError("lost response")
        return raw
    def register(**kwargs):
        result = real_register(**kwargs)
        if stage == "after_registration": raise RuntimeError("lost response")
        return result
    monkeypatch.setattr(module.OrdinaryFormattingReviewService, "rebuild", build)
    monkeypatch.setattr(module, "_write", write)
    monkeypatch.setattr(c.jobs, "register_reviewed_formatting_artifact", register)
    with pytest.raises(BrowserFormattingReviewError, match="operation_failed"):
        c.manager.rebuild(**request(c, view))
    monkeypatch.setattr(c.jobs, "register_reviewed_formatting_artifact", real_register)
    monkeypatch.setattr(module, "_write", real_write)
    restored = BrowserFormattingReviewManager(c.jobs)
    repeated = restored.rebuild(**request(c, view))
    assert len(calls) == 1
    assert repeated["status"] == ("pending" if stage in {"before_build", "after_build"} else "built")
    if repeated["status"] == "pending":
        with pytest.raises(BrowserFormattingReviewError, match="operation_outcome_unknown"):
            restored.rebuild(**request(c, view, "c" * 32))
    else:
        assert restored.read(**c.scope, review_id=view["review_id"])["artifacts"] == repeated["artifacts"]


def test_concurrent_nonce_is_one_attempt_and_other_thread_fails_closed(tmp_path, monkeypatch):
    c = formatting_case(tmp_path, monkeypatch)
    view = reviewed(c)
    entered, release = threading.Event(), threading.Event()
    original = module.OrdinaryFormattingReviewService.rebuild
    calls = []
    def build(service, revision):
        calls.append(revision); entered.set()
        assert release.wait(10)
        return original(service, revision)
    monkeypatch.setattr(module.OrdinaryFormattingReviewService, "rebuild", build)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(c.manager.rebuild, **request(c, view))
        assert entered.wait(10)
        try:
            with pytest.raises(BrowserFormattingReviewError, match="run_busy"):
                BrowserFormattingReviewManager(c.jobs).rebuild(**request(c, view))
        finally:
            release.set()
        assert first.result()["status"] == "built"
    assert len(calls) == 1


def test_real_retained_loader_contention_is_typed_and_source_bridge_remains_content_free(tmp_path, monkeypatch):
    c = formatting_case(tmp_path, monkeypatch)
    before = originals(c)
    # The real completed job's retained loader acquires this same slot. A
    # different thread must fail before any new formatting draft or dispatch.
    with run_workspace_slot(c.run_dir), ThreadPoolExecutor(max_workers=1) as pool:
        lookup = pool.submit(c.jobs.trusted_formatting_job, **c.scope)
        with pytest.raises(RunWorkspaceBusy):
            lookup.result()
        prepare = pool.submit(c.manager.prepare, **c.scope, page_matched_derivative=True)
        with pytest.raises(BrowserFormattingReviewError) as busy:
            prepare.result()
        assert str(busy.value) == "browser_formatting_review_run_busy"
        image = pool.submit(c.bridge.image, **c.owner, review_id=c.view["review_id"], page_number=1)
        with pytest.raises(BrowserSourceReviewError) as source_error:
            image.result()
        assert str(source_error.value) == "browser_source_review_image_unavailable"
    unchanged(before)
    assert not (c.run_dir / "browser_formatting_reviews").exists()
    assert len(c.clients) == len(c.calls) == 1
    # Releasing the real slot leaves the original reviewed context usable.
    assert c.jobs.trusted_formatting_job(**c.scope).source_context.reviewer_kind == "operator_review"

    def unrelated_failure():
        raise RuntimeError("Fictional private loader detail")
    monkeypatch.setattr(c.jobs._jobs[c.job["job_id"]], "_reviewed_source_loader", unrelated_failure)
    with pytest.raises(ValueError) as unavailable:
        c.jobs.trusted_formatting_job(**c.scope)
    assert type(unavailable.value) is ValueError
    assert str(unavailable.value) == "formatting_job_unavailable"
    with pytest.raises(BrowserFormattingReviewError) as generic:
        c.manager.prepare(**c.scope, page_matched_derivative=True)
    assert str(generic.value) == "browser_formatting_review_operation_failed"
    assert not (c.run_dir / "browser_formatting_reviews").exists()
    assert len(c.clients) == len(c.calls) == 1


@pytest.mark.parametrize("kind", module.KINDS)
def test_download_revalidates_exact_artifact_bytes(tmp_path, monkeypatch, kind):
    c = formatting_case(tmp_path, monkeypatch)
    view = reviewed(c); built = c.manager.rebuild(**request(c, view))
    operation = c.run_dir / "browser_formatting_reviews" / view["review_id"] / "operations" / ("b" * 32)
    record = json.loads((operation / "result.json").read_bytes())["record"]
    path = Path(record["files"][kind]["path"])
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(BrowserFormattingReviewError):
        c.manager.artifact(**c.scope, review_id=view["review_id"], artifact_id=built["artifact"]["artifact_id"], artifact_kind=kind)


def test_generation_bool_and_changed_nonce_revision_are_not_equal(tmp_path, monkeypatch):
    c = formatting_case(tmp_path, monkeypatch); view = reviewed(c)
    built = c.manager.rebuild(**request(c, view))
    with pytest.raises(BrowserFormattingReviewError):
        c.manager.rebuild(**{**request(c, view), "revision_id": "0" * 32})
    path = c.run_dir / "browser_formatting_reviews" / view["review_id"] / "operations" / ("b" * 32) / "intent.json"
    intent = json.loads(path.read_bytes()); intent["generation"] = True
    path.write_text(json.dumps(intent), encoding="utf-8")
    with pytest.raises(BrowserFormattingReviewError, match="operation_changed"):
        c.manager.read(**c.scope, review_id=view["review_id"])


def test_artifact_reader_rejects_hardlinks_and_symbolic_links(tmp_path):
    original = tmp_path / "original.bin"
    original.write_bytes(b"owned bytes")
    hardlink = tmp_path / "hardlink.bin"
    os.link(original, hardlink)
    for path in (original, hardlink):
        with pytest.raises(ValueError, match="formatting_job_artifact_unavailable"):
            jobs_module.read_reviewed_formatting_file(path)
    independent = tmp_path / "independent.bin"
    independent.write_bytes(b"other owned bytes")
    symbolic = tmp_path / "symbolic.bin"
    try:
        symbolic.symlink_to(independent)
    except OSError:
        return  # Windows may deny symlink creation; hardlink negatives still ran.
    with pytest.raises(ValueError, match="formatting_job_artifact_unavailable"):
        jobs_module.read_reviewed_formatting_file(symbolic)


def test_persistent_review_cannot_restore_without_its_trusted_job(tmp_path, monkeypatch):
    c = formatting_case(tmp_path, monkeypatch)
    view = reviewed(c)
    restored = BrowserFormattingReviewManager(jobs_module.TranslationJobManager())
    with pytest.raises(BrowserFormattingReviewError):
        restored.read(**c.scope, review_id=view["review_id"])
