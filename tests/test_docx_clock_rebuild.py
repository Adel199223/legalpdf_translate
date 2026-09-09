"""Saved Arabic clocks rebuild locally without touching translation evidence."""
from copy import deepcopy
import hashlib
import json
import socket
import subprocess

from docx import Document
from docx.oxml.ns import qn
import pytest

from legalpdf_translate import formatting_support, layout_integration, ocr_engine, ocr_helpers, openai_client
from legalpdf_translate import secrets_store, source_document, workflow as workflow_module
from legalpdf_translate.checkpoint import (
    build_run_paths, ensure_run_dirs, load_run_state, mark_page_done,
    new_run_state, save_run_state_atomic,
)
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.docx_writer import sanitize_bidi_controls
from legalpdf_translate.structured_artifacts import publish_structured_page, validate_structured_page
from legalpdf_translate.translation_structure import translation_fingerprint
from legalpdf_translate.types import ImageMode, OcrMode, RunConfig, TargetLang


SOURCE = "A audiência terá lugar às 09:30. João Guerreiro deve comparecer."
SPLIT_CLOCKS = ("[[09]]:[[30]]", "\u2066[[09]]\u2069:\u2066[[30]]\u2069")


@pytest.fixture
def no_external_work(monkeypatch):
    calls = []
    def forbidden(*args, **kwargs):
        calls.append("forbidden_operation")
        pytest.fail("Formatting-only clock rebuild dispatched provider/OCR/auth/extraction/native/network work")
    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {})
    for module in (workflow_module, ocr_engine, ocr_helpers, source_document, openai_client, secrets_store):
        for name in ("load_environment", "run_translation_auth_test", "resolve_openai_key_with_source",
                     "get_openai_key", "get_ocr_key", "resolve_ocr_api_key", "resolve_ocr_api_key_source",
                     "build_ocr_engine", "invoke_ocr_image", "extract_ordered_page_text", "extract_ordered_source_page_text",
                     "ocr_pdf_page_text", "ocr_pdf_page_crop_text", "ocr_image_file_text", "ocr_source_page_text",
                     "ocr_source_page_crop_text", "render_page_png", "render_image_png"):
            if hasattr(module, name):
                monkeypatch.setattr(module, name, forbidden)
    monkeypatch.setattr(workflow_module, "OpenAIResponsesClient", forbidden)
    monkeypatch.setattr(openai_client.OpenAIResponsesClient, "__init__", forbidden)
    for name in ("LocalTesseractEngine", "ApiOcrEngine", "GeminiApiOcrEngine"):
        monkeypatch.setattr(getattr(ocr_engine, name), "__init__", forbidden)
    monkeypatch.setattr(workflow_module.TranslationWorkflow, "run", forbidden)
    monkeypatch.setattr(layout_integration, "_render_source", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    return calls


def saved_run(tmp_path, *, structured, clock, strip):
    original = tmp_path / "clock-source.pdf"
    # No PDF extraction or renderer should be needed: this is a saved text run.
    original.write_bytes(SOURCE.encode("utf-8"))
    config = RunConfig(original, tmp_path / "out", TargetLang.AR,
        image_mode=ImageMode.OFF, ocr_mode=OcrMode.OFF, workers=1,
        page_breaks=False, keep_intermediates=True, strip_bidi_controls=strip)
    paths = build_run_paths(config.output_dir, original, TargetLang.AR, run_started_at="20260909_010203")
    ensure_run_dirs(paths)
    identity = {"protocol": "legal_blocks_v2", "fingerprint": "a" * 64} if structured else None
    source_hash = hashlib.sha256(original.read_bytes()).hexdigest()
    state = new_run_state(config=config, paths=paths, pdf_fingerprint=source_hash,
        context_hash="NO_CONTEXT", total_pages=1, selected_pages=[1], protocol_identity=identity)
    text = f"تُعقد الجلسة في الساعة {clock}. يجب على \u2066[[João Guerreiro]]\u2069 الحضور."
    commit = None
    if structured:
        source = PageStructure(1, text_sha256(SOURCE), [StructureBlock("p0001_b0001", SOURCE)],
            source_file_sha256=source_hash, source_text_sha256=text_sha256(SOURCE),
            provenance="text_fallback", uncertain=True)
        target = source.to_dict()
        target["blocks"][0]["text"] = text
        target["translation_sha256"] = text_sha256(text)
        commit = publish_structured_page(paths.pages_dir, source_structure=source, translated_structure=target,
            translated_text=text, protocol_identity=identity, page_fingerprint="b" * 64)
    else:
        (paths.pages_dir / "page_0001.txt").write_text(text, encoding="utf-8")
    usage = {"translation": {"input_tokens": 137, "output_tokens": 89,
                             "reasoning_tokens": 34, "reasoning_included_in_output": True},
             "ocr": {"recorded_usd": "0.0031"}}
    fidelity = {"fidelity_review_required": True, "fidelity_review_status": "not_evaluated",
                "fidelity_review_codes": ["legal_fidelity_not_evaluated"],
                "source_review_required": True, "source_coverage_status": "recognized_words_only",
                "cost_measurement_status": "not_evaluated_all_calls", "estimated_cost": None,
                "historical_review_findings": [{"code": "human_review_pending", "resolved": False}]}
    mark_page_done(state, 1, image_used=False, retry_used=False, usage=usage,
                   metadata=fidelity, structured_commit=commit)
    state.run_status = "completed"
    save_run_state_atomic(paths.run_state_path, state)
    historical = {
        "run_events.jsonl": b'{"event":"saved_translation","already_charged":true}\n',
        "usage_ledger.json": b'{ "total_usd" : "0.0049", "calls" : 1, "reasoning_included" : true }\n',
        "fidelity_review.json": json.dumps(fidelity, ensure_ascii=False, indent=3).encode("utf-8"),
        "run_fingerprints.json": b'{"translation":"historical-frozen","review":"unassessed"}\n',
    }
    for name, content in historical.items():
        (paths.run_dir / name).write_bytes(content)
    summary = {"model": "historical-model", "usage_records": usage, "fidelity": fidelity,
               "cost_estimation_status": "not_evaluated_all_calls",
               "totals": {"total_tokens": 226, "total_cost_estimate_if_available": None},
               "review_queue": [{"page_number": 1, "reasons": ["legal_fidelity_not_evaluated"],
                                 "recommended_action": "manual_review"}], "review_queue_count": 1}
    (paths.run_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return config, paths, state, historical, summary


def assert_atomic_clock(output):
    document = Document(output)
    paragraphs = [p for p in document.paragraphs if p.text.strip()]
    assert len(paragraphs) == 1
    paragraph = paragraphs[0]
    visible = sanitize_bidi_controls(paragraph.text)
    assert visible == "تُعقد الجلسة في الساعة 09:30. يجب على João Guerreiro الحضور."
    assert "[[" not in paragraph.text and "]]" not in paragraph.text
    clock_runs = [run for run in paragraph.runs if "09:30" in sanitize_bidi_controls(run.text)]
    assert len(clock_runs) == 1, "Saved split clock must become one complete LTR run"
    assert sanitize_bidi_controls(clock_runs[0].text).strip() == "09:30"
    rtl = clock_runs[0]._r.find(f"{qn('w:rPr')}/{qn('w:rtl')}")
    assert rtl is not None and rtl.get(qn("w:val")) in {"0", "false"}
    assert paragraph._p.find(f"{qn('w:pPr')}/{qn('w:bidi')}") is not None
    assert len([run for run in paragraph.runs if "João Guerreiro" in run.text]) == 1
    assert document.styles["Normal"].font.name == "Arial"
    assert document.styles["Normal"].font.size.pt == 11


@pytest.mark.parametrize("structured", [False, True], ids=["legacy", "structured"])
@pytest.mark.parametrize("clock", SPLIT_CLOCKS, ids=["split-protected", "split-protected-isolates"])
@pytest.mark.parametrize("strip", [True, False], ids=["strip-controls", "retain-controls"])
def test_saved_arabic_clock_rebuild_is_atomic_and_preserves_all_history(
    tmp_path, no_external_work, structured, clock, strip,
):
    config, paths, state, historical, summary = saved_run(tmp_path, structured=structured, clock=clock, strip=strip)
    saved_files = {path: path.read_bytes() for path in paths.pages_dir.iterdir()}
    saved_files[config.pdf_path] = config.pdf_path.read_bytes()
    saved_files.update({paths.run_dir / name: content for name, content in historical.items()})
    page_before = deepcopy(state.pages["1"])
    workflow = workflow_module.TranslationWorkflow()
    output = workflow.rebuild_docx(config)
    assert_atomic_clock(output)
    assert all(path.read_bytes() == content for path, content in saved_files.items())
    restored = load_run_state(paths.run_state_path)
    assert restored.protocol_identity == state.protocol_identity
    for name in ("usage", "fidelity_review_status", "fidelity_review_required", "fidelity_review_codes",
                 "source_review_required", "source_coverage_status", "cost_measurement_status",
                 "estimated_cost", "historical_review_findings", "structured_commit"):
        assert restored.pages["1"].get(name) == page_before.get(name)
    after_summary = json.loads((paths.run_dir / "run_summary.json").read_text("utf-8"))
    for name in ("model", "usage_records", "fidelity", "cost_estimation_status", "totals"):
        assert after_summary[name] == summary[name]
    if structured:
        validate_structured_page(paths.pages_dir, 1, protocol_identity=state.protocol_identity,
                                 expected_commit=page_before["structured_commit"])
    else:
        assert not list(paths.pages_dir.glob("*.commit.json"))
        assert not list(paths.pages_dir.glob("*.structure.json"))
    assert no_external_work == []


@pytest.mark.parametrize("structured", [False, True], ids=["legacy", "structured"])
def test_clock_profile_change_does_not_invalidate_translation_identity(
    tmp_path, monkeypatch, no_external_work, structured,
):
    config = RunConfig(tmp_path / "not-opened.pdf", tmp_path / "not-created", TargetLang.AR,
                       image_mode=ImageMode.OFF, ocr_mode=OcrMode.OFF, page_breaks=False)
    request = dict(model="retained-model", instructions="retained instructions", config=config,
                   glossary=[], tiers=[1], addendum="", context_hash="retained-context",
                   structured=structured, extraction_identity={"retained": "extraction"},
                   evaluation_identity={"retained": "evaluation"})
    assert formatting_support.LAYOUT_PROFILE_VERSION == "compact_legal_v11_atomic_clock_runs"
    current_format = formatting_support.formatting_fingerprint(config)
    current_translation = translation_fingerprint(**request)
    monkeypatch.setattr(formatting_support, "LAYOUT_PROFILE_VERSION", "compact_legal_v10_isolated_contact_footer")
    assert formatting_support.formatting_fingerprint(config) != current_format
    assert translation_fingerprint(**request) == current_translation
    assert not config.pdf_path.exists() and not config.output_dir.exists()
    assert no_external_work == []
