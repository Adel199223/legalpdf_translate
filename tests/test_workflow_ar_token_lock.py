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
        self.calls: list[dict[str, object]] = []

    def create_page_response(self, **kwargs) -> ApiCallResult:  # noqa: ANN003
        self.calls.append(dict(kwargs))
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


def _source_text_with_bracketed_reference() -> str:
    return "21/25.0FBPTM [36231063]"


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

    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert run_state["pages"]["1"]["retry_prompt_type"] == "ar_token_correction"
    run_summary = json.loads((summary.run_dir / "run_summary.json").read_text(encoding="utf-8"))
    failure_context = run_summary["failure_context"]
    assert failure_context["validator_defect_reason"] == "Expected locked token mismatch."
    assert failure_context["ar_violation_kind"] == "expected_token_mismatch"
    token_details = failure_context["ar_token_details"]
    assert token_details["missing_token_samples"]
    assert token_details["unexpected_token_samples"]


def test_ar_expected_token_mismatch_can_recover_on_retry(tmp_path: Path, monkeypatch) -> None:
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
    corrected = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "العنوان: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "```"
    )
    client = _SequenceClient([altered, corrected])
    summary = TranslationWorkflow(client=client).run(_config(pdf, outdir))

    assert summary.success is True
    assert len(client.calls) == 2
    retry_prompt = str(client.calls[1].get("prompt_text", ""))
    assert "<<<BEGIN LOCKED TOKENS>>>" in retry_prompt
    assert "[[Adel Belghali]]" in retry_prompt
    assert "[[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]" in retry_prompt
    assert "<<<BEGIN TOKEN MISMATCH SUMMARY>>>" in retry_prompt
    assert "Expected locked token mismatch." in retry_prompt
    assert "<<<BEGIN SOURCE PAGE>>>" in retry_prompt
    assert "Nome: [[Adel Belghali]]" in retry_prompt
    assert "All non-token text must be Arabic." in retry_prompt
    assert client.calls[1]["effort"] == ReasoningEffort.HIGH.value

    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert run_state["pages"]["1"]["retry_prompt_type"] == "ar_token_correction"


def test_ar_token_retry_effort_preserves_xhigh_floor(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    config = _config(pdf, outdir)
    config.effort = ReasoningEffort.XHIGH

    workflow = TranslationWorkflow(client=_SequenceClient([]))
    resolved = workflow._resolve_retry_effort(  # noqa: SLF001
        config=config,
        retry_reason="ar_token_violation",
        attempt1_effort=ReasoningEffort.XHIGH,
    )

    assert resolved == ReasoningEffort.XHIGH


def test_ar_expected_token_near_match_can_recover_after_retry(tmp_path: Path, monkeypatch) -> None:
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
    near_match = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "العنوان: [[Rua Luis de Camoes no 6, 7960-011 Marmelar, Pedrogao, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "```"
    )
    summary = TranslationWorkflow(client=_SequenceClient([altered, near_match])).run(_config(pdf, outdir))

    assert summary.success is True
    page_text = (summary.run_dir / "pages" / "page_0001.txt").read_text(encoding="utf-8")
    assert "\u2066[[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\u2069" in page_text


def test_ar_safe_identifier_span_outside_tokens_can_autowrap(tmp_path: Path, monkeypatch) -> None:
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
        "آيبان: PT50003506490000832760029\n"
        "```"
    )
    summary = TranslationWorkflow(client=_SequenceClient([raw_output])).run(_config(pdf, outdir))

    assert summary.success is True
    page_text = (summary.run_dir / "pages" / "page_0001.txt").read_text(encoding="utf-8")
    assert "\u2066[[PT50003506490000832760029]]\u2069" in page_text


def test_ar_outside_token_violation_uses_wrap_retry_prompt(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(_source_text()))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    leaking = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "المرجع: Tribunal Judicial da Comarca de Beja\n"
        "العنوان: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "```"
    )
    corrected = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "المرجع: [[Tribunal Judicial da Comarca de Beja]]\n"
        "العنوان: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "```"
    )
    client = _SequenceClient([leaking, corrected])
    summary = TranslationWorkflow(client=client).run(_config(pdf, outdir))

    assert summary.success is True
    assert len(client.calls) == 2
    retry_prompt = str(client.calls[1].get("prompt_text", ""))
    assert "CURRENT DEFECT TO FIX: Latin letters or digits still appear outside [[...]] tokens." in retry_prompt

    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert run_state["pages"]["1"]["retry_prompt_type"] == "ar_wrap_correction"


def test_ar_failure_artifacts_capture_violation_kind_and_samples(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(_source_text()))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    leaking = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "المرجع: Tribunal Judicial da Comarca de Beja\n"
        "العنوان: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "```"
    )
    summary = TranslationWorkflow(client=_SequenceClient([leaking, leaking])).run(_config(pdf, outdir))

    assert summary.success is False
    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    page = run_state["pages"]["1"]
    assert page["ar_violation_kind"] == "latin_or_digits_outside_wrapped_tokens"
    assert page["validator_defect_reason"] == "Latin letters or digits found outside wrapped tokens."
    assert page["ar_violation_samples"] == ["المرجع: Tribunal Judicial da Comarca de Beja"]

    run_summary = json.loads((summary.run_dir / "run_summary.json").read_text(encoding="utf-8"))
    failure_context = run_summary["failure_context"]
    assert failure_context["ar_violation_kind"] == "latin_or_digits_outside_wrapped_tokens"
    assert failure_context["validator_defect_reason"] == "Latin letters or digits found outside wrapped tokens."
    assert failure_context["ar_violation_samples"] == ["المرجع: Tribunal Judicial da Comarca de Beja"]


def test_ar_language_leakage_inside_protected_tokens_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
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
        "المرجع: [[Tribunal Judicial da Comarca de Beja]]\n"
        "```"
    )
    summary = TranslationWorkflow(client=_SequenceClient([raw_output])).run(_config(pdf, outdir))

    assert summary.success is True


def test_ar_language_leakage_outside_protected_tokens_uses_language_retry(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(workflow_module, "extract_ordered_page_text", lambda _pdf, _idx: _ordered_text_result(_source_text()))
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    leaking = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "العنوان: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "ãõç\n"
        "```"
    )
    corrected = (
        "```\n"
        "الاسم: [[Adel Belghali]]\n"
        "العنوان: [[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\n"
        "آيبان: [[PT50003506490000832760029]]\n"
        "```"
    )
    client = _SequenceClient([leaking, corrected])
    summary = TranslationWorkflow(client=client).run(_config(pdf, outdir))

    assert summary.success is True
    assert len(client.calls) == 2
    retry_prompt = str(client.calls[1].get("prompt_text", ""))
    assert "LANGUAGE CORRECTION ONLY" in retry_prompt
    assert "Portuguese is allowed only inside verbatim protected [[...]] tokens." in retry_prompt

    run_state = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert run_state["pages"]["1"]["retry_prompt_type"] == "language_correction"


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


def test_ar_bracketed_reference_retry_prompt_uses_clean_token_inventory(tmp_path: Path, monkeypatch) -> None:
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
        lambda _pdf, _idx: _ordered_text_result(_source_text_with_bracketed_reference()),
    )
    monkeypatch.setattr(workflow_module, "should_include_image", lambda *args, **kwargs: False)

    leaking = (
        "```\n"
        "الملف: [[21/25.0FBPTM]] [\u2066[[36231063]]\u2069]\n"
        "المرجع: Tribunal Judicial da Comarca de Beja\n"
        "```"
    )
    corrected = (
        "```\n"
        "الملف: [[21/25.0FBPTM]] [\u2066[[36231063]]\u2069]\n"
        "المرجع: [[Tribunal Judicial da Comarca de Beja]]\n"
        "```"
    )
    client = _SequenceClient([leaking, corrected])
    summary = TranslationWorkflow(client=client).run(_config(pdf, outdir))

    assert summary.success is True
    assert len(client.calls) == 2
    retry_prompt = str(client.calls[1].get("prompt_text", ""))
    assert "[[36231063]]" in retry_prompt
    assert "[[[36231063]]]" not in retry_prompt
