from __future__ import annotations

import json
from pathlib import Path

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.pdf_text_order import OrderedPageText
from legalpdf_translate.types import ImageMode, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


def test_analyze_only_no_api_calls(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    config = RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.AUTO,
        start_page=1,
        end_page=2,
        max_pages=2,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
    )

    class _ForbiddenClient:
        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            raise AssertionError("OpenAIResponsesClient must not be instantiated in analyze-only mode.")

    monkeypatch.setattr(workflow_module, "OpenAIResponsesClient", _ForbiddenClient)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 2)
    monkeypatch.setattr(
        workflow_module,
        "extract_ordered_page_text",
        lambda _pdf, _idx: OrderedPageText(
            text="short text",
            extraction_failed=False,
            newline_to_char_ratio=0.03,
            fragmented=False,
            block_count=4,
            header_blocks_count=1,
            footer_blocks_count=0,
            barcode_blocks_count=0,
            body_blocks_count=3,
            two_column_detected=False,
        ),
    )

    summary = TranslationWorkflow().analyze(config)

    assert summary.selected_pages_count == 2
    assert summary.pages_would_attach_images == 2
    assert summary.analyze_report_path.exists()

    payload = json.loads(summary.analyze_report_path.read_text(encoding="utf-8"))
    assert payload["selected_pages_count"] == 2
    assert len(payload["pages"]) == 2
    assert payload["recommended_ocr_mode"] in {"off", "auto", "always"}
    assert payload["recommended_image_mode"] in {"off", "auto", "always"}
    assert isinstance(payload["recommendation_reasons"], list)
    assert isinstance(payload["confidence"], float)
    assert payload["advisor_track"] == "enfr"
    for row in payload["pages"]:
        assert "page_number" in row
        assert "would_attach_image" in row
