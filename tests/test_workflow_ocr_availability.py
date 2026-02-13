from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.types import ImageMode, OcrEnginePolicy, OcrMode, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


class _FakeClient:
    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        _ = kwargs
        return ApiCallResult(
            raw_output="```\nTranslated output\n```",
            usage={"input_tokens": 10, "output_tokens": 4, "reasoning_tokens": 1, "total_tokens": 15},
            response_id="resp-test",
        )


def _ordered_text_result(text: str) -> SimpleNamespace:
    ratio = float(text.count("\n")) / float(max(1, len(text)))
    return SimpleNamespace(
        text=text,
        newline_to_char_ratio=ratio,
        block_count=1,
        header_blocks_count=0,
        footer_blocks_count=0,
        barcode_blocks_count=0,
        body_blocks_count=1,
        two_column_detected=False,
        extraction_failed=False,
        fragmented=False,
    )


def _config(pdf: Path, outdir: Path) -> RunConfig:
    return RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.AUTO,
        ocr_engine=OcrEnginePolicy.LOCAL_THEN_API,
        diagnostics_admin_mode=True,
    )


def _event_rows(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def test_auto_mode_does_not_warn_when_ocr_not_needed(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(
        workflow_module,
        "extract_ordered_page_text",
        lambda _pdf, _idx: _ordered_text_result("This page has enough extracted text to avoid OCR in auto mode."),
    )
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    def _raise_missing(_cfg):  # type: ignore[no-untyped-def]
        raise RuntimeError("missing")

    monkeypatch.setattr(workflow_module, "build_ocr_engine", _raise_missing)

    logs: list[str] = []
    summary = TranslationWorkflow(client=_FakeClient(), log_callback=logs.append).run(_config(pdf, outdir))

    assert summary.success is True
    assert summary.run_summary_path is not None
    summary_payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert summary_payload["pipeline"]["ocr_requested"] is False
    assert summary_payload["pipeline"]["ocr_used"] is False
    assert summary_payload["pipeline"]["ocr_provider_configured"] is False

    events = _event_rows(summary.run_dir / "run_events.jsonl")
    event_types = {str(item.get("event_type", "")) for item in events}
    assert "ocr_engine_unavailable" not in event_types
    assert not any("OCR provider not configured for OCR-requested pages" in line for line in logs)


def test_auto_mode_warns_only_when_ocr_needed_and_unavailable(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(""))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    def _raise_missing(_cfg):  # type: ignore[no-untyped-def]
        raise RuntimeError("missing")

    monkeypatch.setattr(workflow_module, "build_ocr_engine", _raise_missing)

    logs: list[str] = []
    summary = TranslationWorkflow(client=_FakeClient(), log_callback=logs.append).run(_config(pdf, outdir))

    assert summary.success is True
    assert summary.run_summary_path is not None
    summary_payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert summary_payload["pipeline"]["ocr_requested"] is True
    assert summary_payload["pipeline"]["ocr_used"] is False
    assert summary_payload["pipeline"]["ocr_provider_configured"] is False
    assert summary_payload["pipeline"]["ocr_requested_pages"] == 1
    assert summary_payload["pipeline"]["ocr_used_pages"] == 0

    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert run_state["pages"]["1"]["source_route_reason"] == "ocr_requested_engine_unavailable"

    events = _event_rows(summary.run_dir / "run_events.jsonl")
    unavailable_events = [item for item in events if item.get("event_type") == "ocr_engine_unavailable"]
    assert len(unavailable_events) == 1
    assert "OCR provider not configured for OCR-requested pages" in str(unavailable_events[0].get("warning", ""))
    assert any("OCR provider not configured for OCR-requested pages" in line for line in logs)
