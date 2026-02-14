from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.types import ImageMode, OcrEnginePolicy, OcrMode, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


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


class _SequenceClient:
    def __init__(self, outputs: list[str]) -> None:
        self._outputs = list(outputs)

    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        _ = kwargs
        if not self._outputs:
            raise RuntimeError("No more fake responses configured.")
        raw_output = self._outputs.pop(0)
        return ApiCallResult(
            raw_output=raw_output,
            usage={"input_tokens": 10, "output_tokens": 4, "reasoning_tokens": 1, "total_tokens": 15},
            response_id="resp-test",
        )


def _config(pdf: Path, outdir: Path) -> RunConfig:
    return RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.AR,
        effort=ReasoningEffort.HIGH,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        ocr_mode=OcrMode.OFF,
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


def _source_text() -> str:
    return "\n".join(
        [
            "Nome: Adel Belghali",
            "Morada: Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira",
            "IBAN: PT50003506490000832760029",
        ]
    )


def _source_text_with_month_date() -> str:
    return "\n".join(
        [
            "Nome: Adel Belghali",
            "Morada: Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira",
            "Beja, 10 de fevereiro de 2026",
            "IBAN: PT50003506490000832760029",
        ]
    )


def test_ar_expected_tokens_autofix_unwrapped_literals(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(_source_text()))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    raw_output = (
        "```\n"
        "الاسم: Adel Belghali\n"
        "العنوان: Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira\n"
        "آيبان: PT50003506490000832760029\n"
        "```"
    )
    summary = TranslationWorkflow(client=_SequenceClient([raw_output])).run(_config(pdf, outdir))

    assert summary.success is True
    page_text = (summary.run_dir / "pages" / "page_0001.txt").read_text(encoding="utf-8")
    assert "\u2066[[Adel Belghali]]\u2069" in page_text
    assert "\u2066[[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\u2069" in page_text
    assert "\u2066[[PT50003506490000832760029]]\u2069" in page_text

    events = _event_rows(summary.run_dir / "run_events.jsonl")
    event_types = [str(item.get("event_type", "")) for item in events]
    assert "ar_locked_token_autofix_applied" in event_types
    assert "ar_locked_token_violation" not in event_types


def test_ar_expected_tokens_with_extra_wrapped_token_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(_source_text()))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    raw_output = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "العنوان: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "المرجع: [[84/26.1PBBJA]]\n"
        "```"
    )
    summary = TranslationWorkflow(client=_SequenceClient([raw_output])).run(_config(pdf, outdir))

    assert summary.success is True

    events = _event_rows(summary.run_dir / "run_events.jsonl")
    event_types = [str(item.get("event_type", "")) for item in events]
    assert "ar_locked_token_extra_tokens" in event_types
    assert "ar_locked_token_violation" not in event_types


def test_ar_expected_token_mismatch_fails_after_retry(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(_source_text()))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    altered = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "العنوان: [[Rua Luís de Camões no 9, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "```"
    )
    summary = TranslationWorkflow(client=_SequenceClient([altered, altered])).run(_config(pdf, outdir))

    assert summary.success is False
    assert summary.error == "compliance_failure"

    events = _event_rows(summary.run_dir / "run_events.jsonl")
    violations = [item for item in events if str(item.get("event_type", "")) == "ar_locked_token_violation"]
    assert violations
    counters = violations[-1].get("counters", {})
    assert isinstance(counters, dict)
    assert int(counters.get("missing_count", 0) or 0) >= 1
    assert int(counters.get("altered_count", 0) or 0) >= 1


def test_ar_month_date_conversion_is_not_a_token_lock_violation(tmp_path: Path, monkeypatch) -> None:
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
        lambda _pdf, _idx: _ordered_text_result(_source_text_with_month_date()),
    )
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    raw_output = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "العنوان: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "بيجا، [[10]] فبراير [[2026]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "```"
    )
    summary = TranslationWorkflow(client=_SequenceClient([raw_output])).run(_config(pdf, outdir))

    assert summary.success is True
    page_text = (summary.run_dir / "pages" / "page_0001.txt").read_text(encoding="utf-8")
    assert "فبراير" in page_text
    assert "de fevereiro" not in page_text

    events = _event_rows(summary.run_dir / "run_events.jsonl")
    event_types = [str(item.get("event_type", "")) for item in events]
    assert "ar_locked_token_violation" not in event_types
