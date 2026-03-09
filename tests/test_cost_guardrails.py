from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.types import (
    BudgetExceedPolicy,
    EffortPolicy,
    ImageMode,
    PageStatus,
    ReasoningEffort,
    RunConfig,
    TargetLang,
)
from legalpdf_translate.workflow import TranslationWorkflow, _PageOutcome


def _base_config(
    pdf: Path,
    outdir: Path,
    *,
    budget_cap_usd: float | None,
    budget_on_exceed: BudgetExceedPolicy,
) -> RunConfig:
    return RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.HIGH,
        effort_policy=EffortPolicy.ADAPTIVE,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
        budget_cap_usd=budget_cap_usd,
        budget_on_exceed=budget_on_exceed,
    )


def _patch_common_runtime(monkeypatch: pytest.MonkeyPatch, *, extracted_text: str) -> None:
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)
    monkeypatch.setattr(workflow_module, "load_system_instructions", lambda _lang: "SYS")
    monkeypatch.setattr(
        workflow_module,
        "extract_ordered_page_text",
        lambda _pdf, _idx: SimpleNamespace(
            text=extracted_text,
            newline_to_char_ratio=0.0,
            block_count=1,
            header_blocks_count=0,
            footer_blocks_count=0,
            barcode_blocks_count=0,
            body_blocks_count=1,
            two_column_detected=False,
            extraction_failed=False,
            fragmented=False,
        ),
    )

    def _assemble_docx(
        _pages_dir: Path,
        output_path: Path,
        **_kwargs,  # noqa: ANN003
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"docx")
        return output_path

    monkeypatch.setattr(workflow_module, "assemble_docx", _assemble_docx)


def _patch_done_page(monkeypatch: pytest.MonkeyPatch, calls: dict[str, int]) -> None:
    def _done_page(  # type: ignore[no-untyped-def]
        self,
        *,
        client,
        config,
        paths,
        instructions,
        context_text,
        page_number,
        total_pages,
        ocr_engine,
    ):
        _ = self, client, config, instructions, context_text, total_pages, ocr_engine
        calls["count"] += 1
        page_path = paths.pages_dir / f"page_{page_number:04d}.txt"
        page_path.write_text("Translated content", encoding="utf-8")
        return _PageOutcome(
            status=PageStatus.DONE,
            image_used=False,
            retry_used=False,
            usage={},
            error=None,
            page_metadata={
                "started_at_iso": "2026-03-05T00:00:00+00:00",
                "ended_at_iso": "2026-03-05T00:00:01+00:00",
                "wall_seconds": 0.5,
                "attempt1_effort": "high",
                "attempt2_effort": "",
                "input_tokens": 120,
                "output_tokens": 60,
                "reasoning_tokens": 10,
                "total_tokens": 190,
                "api_calls_count": 1,
                "transport_retries_count": 0,
                "backoff_wait_seconds_total": 0.0,
                "source_route": "direct_text",
            },
        )

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _done_page)


def test_budget_cap_exceeded_warn_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    _patch_common_runtime(monkeypatch, extracted_text=("A" * 4000))
    calls = {"count": 0}
    _patch_done_page(monkeypatch, calls)

    summary = TranslationWorkflow(client=object()).run(
        _base_config(
            pdf,
            outdir,
            budget_cap_usd=0.0,
            budget_on_exceed=BudgetExceedPolicy.WARN,
        )
    )

    assert summary.success is True
    assert calls["count"] == 1
    assert summary.run_summary_path is not None
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["budget_decision"] == "warn"
    assert payload["budget_decision_reason"] == "estimate_exceeds_budget_cap"
    assert payload["cost_estimation_status"] == "available"
    assert isinstance(payload["budget_pre_run"]["estimated_cost_usd"], float)


def test_budget_cap_exceeded_block_stops_before_processing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    _patch_common_runtime(monkeypatch, extracted_text=("A" * 4000))
    calls = {"count": 0}
    _patch_done_page(monkeypatch, calls)

    summary = TranslationWorkflow(client=object()).run(
        _base_config(
            pdf,
            outdir,
            budget_cap_usd=0.0,
            budget_on_exceed=BudgetExceedPolicy.BLOCK,
        )
    )

    assert summary.success is False
    assert summary.exit_code == 1
    assert summary.error == "budget_cap_exceeded"
    assert summary.completed_pages == 0
    assert calls["count"] == 0
    state_payload = json.loads((summary.run_dir / "run_state.json").read_text(encoding="utf-8"))
    assert state_payload["run_status"] == "budget_blocked"
    assert state_payload["halt_reason"] == "budget_cap_exceeded"
    assert summary.run_summary_path is not None
    run_summary = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert run_summary["budget_decision"] == "block"
    assert run_summary["budget_decision_reason"] == "estimate_exceeds_budget_cap"


def test_budget_estimate_unavailable_returns_na_and_continues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
        lambda _pdf, _idx: (_ for _ in ()).throw(RuntimeError("sample read failed")),
    )

    def _assemble_docx(
        _pages_dir: Path,
        output_path: Path,
        **_kwargs,  # noqa: ANN003
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"docx")
        return output_path

    monkeypatch.setattr(workflow_module, "assemble_docx", _assemble_docx)

    calls = {"count": 0}
    _patch_done_page(monkeypatch, calls)

    summary = TranslationWorkflow(client=object()).run(
        _base_config(
            pdf,
            outdir,
            budget_cap_usd=1.0,
            budget_on_exceed=BudgetExceedPolicy.WARN,
        )
    )

    assert summary.success is True
    assert calls["count"] == 1
    assert summary.run_summary_path is not None
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["budget_decision"] == "n/a"
    assert payload["budget_decision_reason"] == "estimate_unavailable_with_budget_cap"
    assert payload["cost_estimation_status"] == "unavailable"


def test_no_budget_cap_returns_allow_when_estimate_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    _patch_common_runtime(monkeypatch, extracted_text=("A" * 4000))
    calls = {"count": 0}
    _patch_done_page(monkeypatch, calls)

    summary = TranslationWorkflow(client=object()).run(
        _base_config(
            pdf,
            outdir,
            budget_cap_usd=None,
            budget_on_exceed=BudgetExceedPolicy.WARN,
        )
    )

    assert summary.success is True
    assert calls["count"] == 1
    assert summary.run_summary_path is not None
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["budget_decision"] == "allow"
    assert payload["budget_decision_reason"] == "no_budget_cap_configured"
    assert payload["cost_estimation_status"] == "available"
