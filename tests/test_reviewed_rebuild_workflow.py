"""Ordinary workflow rebuild uses explicit reviews and retained paid evidence."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.checkpoint import (build_run_paths, load_run_state, new_run_state,
                                          save_run_state_atomic)
from legalpdf_translate.run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
from tests.test_run_docx_formatting import setup, encode


def forbidden(*args, **kwargs):
    pytest.fail("Offline rebuild must not invoke provider, extraction, OCR, auth or native rendering")


@pytest.fixture
def case(tmp_path, monkeypatch):
    result = setup(tmp_path)
    paths = build_run_paths(result.config.output_dir, result.config.pdf_path, result.config.target_lang)
    result.run_dir.rename(paths.run_dir)
    result.run_dir, result.pages_dir, result.paths = paths.run_dir, paths.pages_dir, paths
    original = result.state
    state = new_run_state(config=result.config, paths=paths, pdf_fingerprint=original.pdf_fingerprint,
                         context_hash="NO_CONTEXT", total_pages=1, selected_pages=[1])
    state.pages = deepcopy(original.pages)
    state.protocol_identity = deepcopy(original.protocol_identity)
    state.dispatch_accounting = {"retained_test_accounting": {"spent_usd": "0.0123", "calls": 1}}
    state.settings["historical_model"] = "retained-model"
    state.run_status, state.finished_at = "completed", "2026-09-15T00:00:00+00:00"
    state.done_count, state.pending_count, state.last_completed_page = 1, 0, 1
    result.state = state
    save_run_state_atomic(paths.run_state_path, state)
    result.summary = {"model": "retained-model", "totals": {"cost_usd": "0.0123"},
        "usage_records": [{"input_tokens": 17}], "quality_risk_score": 0.4,
        "review_queue": [{"page_number": 1, "score": 0.4, "reasons": ["semantic_issue"],
            "recommended_action": "rerun_page", "retained": True}], "review_queue_count": 1}
    (paths.run_dir / "run_summary.json").write_bytes(encode(result.summary))
    result.messages = []
    result.workflow = workflow_module.TranslationWorkflow(gui_settings={}, log_callback=result.messages.append)
    for name in ("OpenAIResponsesClient", "extract_ordered_page_text", "build_ocr_engine",
                 "run_translation_auth_test", "resolve_openai_key_with_source", "load_environment"):
        monkeypatch.setattr(workflow_module, name, forbidden)
    import legalpdf_translate.layout_integration as layout
    monkeypatch.setattr(layout, "_render_source", forbidden)
    return result


def submit(case):
    return case.workflow.submit_docx_formatting_review(case.config, reviewer_kind=case.reviewer,
        source_review=case.source_review, source_evidence=case.source_evidence,
        source_review_evidence=case.source_decision_evidence, formatting_manifest=encode(case.manifest),
        review_evidence=b"Separate synthetic formatting decision.")


def retained(case):
    return {path.name: path.read_bytes() for path in case.pages_dir.iterdir()}


def assert_accounting_unchanged(case, before):
    current = load_run_state(case.paths.run_state_path)
    assert current.dispatch_accounting == before.dispatch_accounting
    assert current.protocol_identity == before.protocol_identity and current.settings == before.settings
    assert current.pages["1"]["original_usage"] == before.pages["1"]["original_usage"]
    assert current.pages["1"]["structured_commit"] == before.pages["1"]["structured_commit"]
    summary = json.loads((case.run_dir / "run_summary.json").read_bytes())
    for key in ("model", "totals", "usage_records", "quality_risk_score"):
        assert summary[key] == case.summary[key]
    assert summary["review_queue"][0]["score"] == 0.4
    assert summary["review_queue"][0]["recommended_action"] == "rerun_page"


def test_reviewed_rebuild_uses_explicit_run_revision_and_actual_source_map_checker(case, monkeypatch):
    revision = submit(case)
    before, checkpoint = retained(case), load_run_state(case.paths.run_state_path)
    monkeypatch.setattr(workflow_module, "assemble_docx", forbidden)
    monkeypatch.setattr(case.workflow, "_prepare_docx_layout", forbidden)
    output = case.workflow.rebuild_docx(case.config, formatting_revision_id=revision)
    mapping = json.loads(output.with_suffix(".source_map.json").read_bytes())
    assert mapping["version"] == "reviewed_region_source_map_v1"
    assert retained(case) == before
    restored = load_run_state(case.paths.run_state_path)
    assert restored.pages["1"]["layout_review_required"] is True
    assert "layout_mapping_unavailable" not in restored.pages["1"]["layout_review_reasons"]
    assert output.with_suffix(".formatting_assembly.json").is_file()
    assert_accounting_unchanged(case, checkpoint)


@pytest.mark.parametrize("kind", ["revision", "source", "commit"])
def test_integrity_failure_never_falls_back_or_updates_checkpoint(case, monkeypatch, kind):
    revision = submit(case)
    path = {"revision": case.run_dir / "formatting_reviews" / revision / "formatting.json",
            "source": case.pages_dir / "page_0001.source_structure.json",
            "commit": case.pages_dir / "page_0001.commit.json"}[kind]
    path.write_bytes(path.read_bytes() + b" changed")
    before = case.paths.run_state_path.read_bytes()
    monkeypatch.setattr(workflow_module, "assemble_docx", forbidden)
    with pytest.raises(ValueError):
        case.workflow.rebuild_docx(case.config, formatting_revision_id=revision)
    assert case.paths.run_state_path.read_bytes() == before
    assert not list(case.config.output_dir.glob("*.docx"))


def test_edited_txt_declines_mapping_then_uses_normal_writer_and_keeps_accounting(case):
    revision = submit(case)
    checkpoint = load_run_state(case.paths.run_state_path)
    originals = retained(case)
    text = case.pages_dir / "page_0001.txt"
    text.write_bytes(b"Complete user-edited fictional text.")
    output = case.workflow.rebuild_docx(case.config, formatting_revision_id=revision)
    mapping = json.loads(output.with_suffix(".source_map.json").read_bytes())
    assert mapping["version"] == 1
    assert any("reviewed_profile_stale_edited_target" in message for message in case.messages)
    state = load_run_state(case.paths.run_state_path)
    assert {"reviewed_profile_stale_review", "reviewed_profile_stale_edited_target"} <= set(
        state.pages["1"]["layout_review_reasons"])
    summary = json.loads((case.run_dir / "run_summary.json").read_bytes())
    assert "reviewed_profile_stale_review" in summary["review_queue"][0]["reasons"]
    for name, raw in originals.items():
        if name != text.name:
            assert (case.pages_dir / name).read_bytes() == raw
    assert_accounting_unchanged(case, checkpoint)


def test_no_revision_keeps_normal_rebuild_path_and_does_not_auto_select_latest(case, monkeypatch):
    submit(case)
    import legalpdf_translate.run_docx_formatting as adapter
    monkeypatch.setattr(adapter, "prepare_run_docx_formatting", forbidden)
    output = case.workflow.rebuild_docx(case.config)
    assert json.loads(output.with_suffix(".source_map.json").read_bytes())["version"] == 1
    assert not output.with_suffix(".formatting_assembly.json").exists()
    assert not any("Reviewed formatting was declined" in message for message in case.messages)


def test_saved_unsupported_preference_is_preserved_and_decline_stays_visible(case):
    revision = submit(case)
    case.config.page_breaks = False
    output = case.workflow.rebuild_docx(case.config, formatting_revision_id=revision)
    assert json.loads(output.with_suffix(".source_map.json").read_bytes())["version"] == 1
    assert case.config.page_breaks is False
    state = load_run_state(case.paths.run_state_path)
    assert "reviewed_profile_requires_page_breaks" in state.pages["1"]["layout_review_reasons"]


@pytest.mark.parametrize("operation", ["draft", "submit", "rebuild"])
def test_reviewed_operations_reject_checkpoint_marked_running(case, operation):
    revision = submit(case)
    state = load_run_state(case.paths.run_state_path)
    state.run_status, state.finished_at = "running", None
    save_run_state_atomic(case.paths.run_state_path, state)
    before = case.paths.run_state_path.read_bytes()
    with pytest.raises(ValueError, match="marked running"):
        if operation == "draft":
            case.workflow.begin_docx_formatting_review(case.config, reviewer_kind="operator_review")
        elif operation == "submit":
            submit(case)
        else:
            case.workflow.rebuild_docx(case.config, formatting_revision_id=revision)
    assert case.paths.run_state_path.read_bytes() == before


@pytest.mark.parametrize("operation", ["run", "rebuild", "reviewed_rebuild", "draft", "submit"])
def test_all_public_workflow_entry_points_share_same_run_lock(case, monkeypatch, operation):
    revision = submit(case)
    monkeypatch.setattr(case.workflow, "_run_locked", forbidden)
    def invoke():
        if operation == "run":
            return case.workflow.run(case.config)
        if operation == "rebuild":
            return case.workflow.rebuild_docx(case.config)
        if operation == "reviewed_rebuild":
            return case.workflow.rebuild_docx(case.config, formatting_revision_id=revision)
        if operation == "draft":
            return case.workflow.begin_docx_formatting_review(case.config, reviewer_kind="operator_review")
        return submit(case)
    with run_workspace_slot(case.run_dir):
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(RunWorkspaceBusy):
                pool.submit(invoke).result(timeout=5)


def test_normal_run_owns_lock_before_body_and_allows_same_thread_partial_export(case, monkeypatch):
    expected = case.config.output_dir / "synthetic_partial.docx"
    monkeypatch.setattr(case.workflow, "_export_partial_docx_locked", lambda: expected)
    def body(config):
        with ThreadPoolExecutor(max_workers=1) as pool:
            def contender():
                with run_workspace_slot(case.run_dir):
                    pytest.fail("Normal run must hold the same lock")
            with pytest.raises(RunWorkspaceBusy):
                pool.submit(contender).result(timeout=5)
        case.workflow._last_config, case.workflow._last_paths, case.workflow._last_state = config, case.paths, case.state
        return case.workflow.export_partial_docx()
    monkeypatch.setattr(case.workflow, "_run_locked", body)
    assert case.workflow.run(case.config) == expected


def test_successful_locked_acquisition_preserves_reviewer_and_does_not_write_draft(case):
    before = retained(case)
    draft = case.workflow.begin_docx_formatting_review(case.config, reviewer_kind="operator_review")
    assert draft["status"] == "draft" and draft["formatting_manifest"]["reviewer_kind"] == "operator_review"
    assert retained(case) == before and not (case.run_dir / "formatting_reviews").exists()


def test_redirected_checkpoint_locks_retained_owner_and_keeps_actual_paths(case, monkeypatch):
    base_root, base_checkpoint = case.run_dir, case.paths.run_state_path
    owner = base_root.parent / "retained_owner"
    base_root.rename(owner)
    base_root.mkdir()
    case.run_dir, case.pages_dir = owner, owner / "pages"
    case.paths = replace(case.paths, run_dir=owner, pages_dir=case.pages_dir,
                         images_dir=owner / "images", run_state_path=owner / "run_state.json")
    state = load_run_state(case.paths.run_state_path)
    state.run_dir_abs = str(owner)
    save_run_state_atomic(case.paths.run_state_path, state)
    save_run_state_atomic(base_checkpoint, state)
    revision = submit(case)
    with run_workspace_slot(owner):
        with ThreadPoolExecutor(max_workers=1) as pool:
            with pytest.raises(RunWorkspaceBusy):
                pool.submit(case.workflow.rebuild_docx, case.config,
                            formatting_revision_id=revision).result(timeout=5)
    output = case.workflow.rebuild_docx(case.config, formatting_revision_id=revision)
    assert output.is_file()
    assert case.workflow._last_paths.run_dir == owner
    assert case.workflow._last_paths.pages_dir == case.pages_dir
    assert case.workflow._last_paths.run_state_path == case.paths.run_state_path
    assert load_run_state(case.paths.run_state_path).final_docx_path_abs == str(output)


@pytest.mark.parametrize("revision", ["../outside", "", "f" * 32])
def test_invalid_or_missing_explicit_revision_does_not_silently_select_another(case, monkeypatch, revision):
    submit(case)
    monkeypatch.setattr(workflow_module, "assemble_docx", forbidden)
    with pytest.raises(ValueError):
        case.workflow.rebuild_docx(case.config, formatting_revision_id=revision)
    assert not list(case.config.output_dir.glob("*.docx"))
