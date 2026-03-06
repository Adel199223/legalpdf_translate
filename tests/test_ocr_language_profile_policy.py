from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.ocr_engine import OcrResult, _source_profile_from_hint
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


def _config(pdf: Path, outdir: Path, target_lang: TargetLang) -> RunConfig:
    return RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=target_lang,
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


def test_source_profile_defaults_to_pt_latin_for_non_ar_hints() -> None:
    assert _source_profile_from_hint(None) == "pt_latin_default"
    assert _source_profile_from_hint("PT") == "pt_latin_default"
    assert _source_profile_from_hint("EN") == "pt_latin_default"
    assert _source_profile_from_hint("FR") == "pt_latin_default"
    assert _source_profile_from_hint("pt_latin_default") == "pt_latin_default"


def test_source_profile_maps_ar_hints_to_ar_track() -> None:
    assert _source_profile_from_hint("AR") == "ar_track_default"
    assert _source_profile_from_hint("ara") == "ar_track_default"
    assert _source_profile_from_hint("ar_track_default") == "ar_track_default"


def test_workflow_uses_source_profile_hint_not_target_label(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(""))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    captured_hints: list[str | None] = []

    def _fake_ocr_pdf_page_text(_pdf, _page, mode, engine, *, prefer_header, lang_hint):  # type: ignore[no-untyped-def]
        _ = mode, engine, prefer_header
        captured_hints.append(lang_hint)
        return OcrResult(
            text="OCR text",
            engine="local",
            failed_reason=None,
            chars=8,
            quality_score=0.7,
            selected_pass="pass_a_document",
            attempts=[],
        )

    class _FakeEngine:
        def ocr_image(self, image_bytes: bytes, lang_hint: str | None = None) -> OcrResult:
            _ = image_bytes, lang_hint
            return OcrResult(text="OCR text", engine="local", failed_reason=None, chars=8)

    monkeypatch.setattr(workflow_module, "ocr_pdf_page_text", _fake_ocr_pdf_page_text)
    monkeypatch.setattr(workflow_module, "build_ocr_engine", lambda _cfg: _FakeEngine())

    TranslationWorkflow(client=_FakeClient()).run(_config(pdf, outdir, TargetLang.EN))
    TranslationWorkflow(client=_FakeClient()).run(_config(pdf, outdir, TargetLang.AR))

    assert captured_hints[0] == "pt_latin_default"
    assert captured_hints[1] == "ar_track_default"
