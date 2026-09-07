"""Formatting-only assembly/rebuild notices preserve saved translation history."""
from copy import deepcopy
import json

from docx import Document
import pytest

from legalpdf_translate.checkpoint import (build_run_paths, ensure_run_dirs, load_run_state,
    mark_page_done, new_run_state, save_run_state_atomic)
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.formatting_support import save_translated_structure, write_json_atomic
from legalpdf_translate.layout_integration import collect_docx_layout_review, merge_layout_review_queue
from legalpdf_translate.types import RunConfig, TargetLang
import legalpdf_translate.layout_integration as integration
import legalpdf_translate.workflow as workflow_module


def forbidden(*args, **kwargs):
    pytest.fail("Formatting must not invoke translation, extraction, OCR or credentials")


@pytest.fixture
def case(tmp_path, monkeypatch):
    for name in ("OpenAIResponsesClient", "extract_ordered_page_text", "build_ocr_engine",
                 "run_translation_auth_test", "resolve_openai_key_with_source", "load_environment"):
        monkeypatch.setattr(workflow_module, name, forbidden)
    monkeypatch.setattr(integration, "_render_source", forbidden)
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"Synthetic original; no native or API render")
    config = RunConfig(pdf, tmp_path / "out", TargetLang.FR, page_breaks=False, keep_intermediates=False)
    paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
    ensure_run_dirs(paths)
    (paths.pages_dir / "page_0001.txt").write_text("Texte traduit intégral.", encoding="utf-8")
    state = new_run_state(config=config, paths=paths, pdf_fingerprint=integration._file_hash(pdf),
                         context_hash="NO_CONTEXT", total_pages=2, selected_pages=[1, 2])
    mark_page_done(state, 1, image_used=True, retry_used=True,
                   usage={"input_tokens": 41, "output_tokens": 23, "reasoning_tokens": 11})
    state.pages["1"]["existing_findings"] = [{"code": "semantic_issue"}]
    save_run_state_atomic(paths.run_state_path, state)
    summary = {"model": "historical-model", "totals": {"cost_usd": 0.002, "input_tokens": 41},
               "quality_risk_score": .8, "usage_records": [{"call": "paid-before-rebuild"}],
               "review_queue_count": 1, "review_queue": [{"page_number": 1, "score": .8,
               "recommended_action": "rerun_page", "reasons": ["semantic_issue"], "custom": "retained"}]}
    write_json_atomic(paths.run_dir / "run_summary.json", summary)
    return config, paths, state, summary


def test_legacy_rebuild_adds_manual_layout_notice_without_fabricating_structure(case):
    config, paths, state, summary = case
    original = (paths.pages_dir / "page_0001.txt").read_bytes()
    workflow = workflow_module.TranslationWorkflow()
    output = workflow.rebuild_docx(config)
    assert output.is_file()
    doc = Document(output)
    assert doc.styles["Normal"].font.name == "Times New Roman"
    assert doc.styles["Normal"].font.size.pt == 10.5
    assert (paths.pages_dir / "page_0001.txt").read_bytes() == original
    assert not list(paths.pages_dir.glob("*.structure.json"))
    assert not list(paths.pages_dir.glob("*.layout.json"))
    assert not (config.output_dir / ".legalpdf_layout_cache").exists()
    after = json.loads((paths.run_dir / "run_summary.json").read_text(encoding="utf-8"))
    for key in ("model", "totals", "quality_risk_score", "usage_records"):
        assert after[key] == summary[key]
    row = after["review_queue"][0]
    assert row["recommended_action"] == "rerun_page" and row["custom"] == "retained"
    assert row["reasons"] == ["semantic_issue", "source_block_layout_unavailable"]
    restored = load_run_state(paths.run_state_path)
    assert restored.pages["1"]["usage"] == state.pages["1"]["usage"]
    assert restored.pages["1"]["existing_findings"] == state.pages["1"]["existing_findings"]
    assert restored.pages["1"]["layout_review_required"] is True
    assert not restored.pages["2"].get("layout_review_required")
    workflow.rebuild_docx(config)
    assert json.loads((paths.run_dir / "run_summary.json").read_text(encoding="utf-8")) == after


def test_rebuild_preserves_all_bound_source_target_and_fingerprint_files(case):
    config, paths, state, summary = case
    blocks = [StructureBlock("p0001_b0001", "Texto português integral.")]
    source = PageStructure(1, text_sha256(blocks[0].text), blocks,
                           source_file_sha256=integration._file_hash(config.pdf_path),
                           source_text_sha256=text_sha256(blocks[0].text))
    write_json_atomic(paths.pages_dir / "page_0001.source_structure.json", source.to_dict())
    text = (paths.pages_dir / "page_0001.txt").read_text(encoding="utf-8")
    save_translated_structure(path=paths.pages_dir / "page_0001.structure.json", source_structure=source,
                              translated_blocks=[{"id": blocks[0].id, "text": text}], translated_text=text,
                              translation_fingerprint="never-invalidated-by-spacing")
    identity = paths.run_dir / "run_fingerprints.json"
    identity.write_text('{"translation":"historical","review":"historical"}', encoding="utf-8")
    originals = {path: path.read_bytes() for path in paths.pages_dir.iterdir()}
    original_identity = identity.read_bytes()
    workflow_module.TranslationWorkflow().rebuild_docx(config)
    assert all(path.read_bytes() == data for path, data in originals.items())
    assert identity.read_bytes() == original_identity
    assert (paths.pages_dir / "page_0001.layout.json").exists()


def test_partial_cancelled_assembly_keeps_saved_text_and_reports_only_present_pages(case):
    config, paths, state, summary = case
    workflow = workflow_module.TranslationWorkflow()
    workflow._last_config, workflow._last_paths, workflow._last_state = config, paths, state
    workflow._cancel_event.set()
    assert workflow.export_partial_docx().is_file()
    assert state.pages["1"]["layout_review_required"]
    assert not state.pages["2"].get("layout_review_required")
    assert not list(paths.pages_dir.glob("*.layout.json"))


@pytest.mark.parametrize("bad", [{}, "invalid", 4])
def test_malformed_old_queue_fails_closed_without_discarding_evidence(bad):
    payload = {"review_queue": bad, "cost": "0.456", "model": "historical", "quality_risk_score": .7}
    original = deepcopy(payload)
    with pytest.raises(ValueError):
        merge_layout_review_queue(payload, {"1": {"layout_review_required": True}})
    assert payload == original


def test_absent_old_queue_gains_only_layout_notice():
    payload = {"review_queue": None, "cost": "0.456"}
    merge_layout_review_queue(payload, {"1": {"layout_review_required": True}})
    assert payload["cost"] == "0.456"
    assert payload["review_queue_count"] == 1
    assert payload["review_queue"][0]["reasons"] == ["layout_review_required"]


def test_malformed_later_row_does_not_partially_mutate_historical_queue():
    payload = {"review_queue": [{"page_number": 1, "reasons": ["semantic_issue"]},
                                {"page_number": 2, "reasons": {"historical": "finding"}}]}
    original = deepcopy(payload)
    with pytest.raises(ValueError):
        merge_layout_review_queue(payload, {"1": {"layout_review_required": True},
                                            "2": {"layout_review_required": True}})
    assert payload == original


def test_malformed_summary_file_is_preserved_with_log_notice(case):
    config, paths, state, summary = case
    path = paths.run_dir / "run_summary.json"
    path.write_text("[invalid historical record", encoding="utf-8")
    messages = []
    workflow = workflow_module.TranslationWorkflow(log_callback=messages.append)
    workflow.rebuild_docx(config)
    assert path.read_text(encoding="utf-8") == "[invalid historical record"
    assert any("Historical summary was preserved" in item for item in messages)


def test_malformed_historical_queue_keeps_exact_summary_bytes_on_rebuild(case):
    config, paths, state, summary = case
    path = paths.run_dir / "run_summary.json"
    summary["review_queue"] = {"historical_finding": "do not discard"}
    write_json_atomic(path, summary)
    before = path.read_bytes()
    workflow_module.TranslationWorkflow().rebuild_docx(config)
    assert path.read_bytes() == before


@pytest.mark.parametrize("corruption", ["docx", "translation", "duplicate", "missing", "invalid_page", "absent_map"])
def test_layout_review_rejects_unbound_map(case, corruption):
    config, paths, state, summary = case
    output = workflow_module.TranslationWorkflow().rebuild_docx(config)
    map_path = output.with_suffix(".source_map.json")
    record = json.loads(map_path.read_text(encoding="utf-8"))
    if corruption == "docx":
        record["docx_sha256"] = "0" * 64
    elif corruption == "translation":
        record["pages"][0]["translation_sha256"] = "0" * 64
    elif corruption == "duplicate":
        record["pages"].append(deepcopy(record["pages"][0]))
    elif corruption == "missing":
        record["pages"] = []
    elif corruption == "invalid_page":
        record["pages"][0]["source_page_number"] = True
    write_json_atomic(map_path, record)
    if corruption == "absent_map":
        map_path.unlink()
    assert "layout_mapping_unavailable" in collect_docx_layout_review(output, paths.pages_dir, {})[1]


def test_normal_summary_merge_keeps_original_summary_builder_results_and_sticky_flags(case, monkeypatch):
    config, paths, state, summary = case
    state.pages["1"].update(layout_review_required=True, layout_review_reasons=[
        "layout_review_required", "section_furniture_target_variant_standardized"])
    workflow = workflow_module.TranslationWorkflow()
    monkeypatch.setattr(workflow, "_build_run_summary_payload", lambda **kw: deepcopy(summary))
    path = workflow._write_run_summary(config=config, paths=paths, run_state=state)
    after = json.loads(path.read_text(encoding="utf-8"))
    for key in ("model", "totals", "usage_records", "quality_risk_score"):
        assert after[key] == summary[key]
    assert after["review_queue"][0]["reasons"] == ["semantic_issue", "layout_review_required",
                                                   "section_furniture_target_variant_standardized"]
    assert after["review_queue_count"] == 1
