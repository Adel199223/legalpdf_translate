from __future__ import annotations

import json
from pathlib import Path

import legalpdf_translate.workflow as workflow_module
from legalpdf_translate.types import EffortPolicy, ImageMode, PageStatus, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow, _PageOutcome


def _base_config(pdf: Path, outdir: Path) -> RunConfig:
    return RunConfig(
        pdf_path=pdf,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.XHIGH,
        effort_policy=EffortPolicy.ADAPTIVE,
        allow_xhigh_escalation=False,
        image_mode=ImageMode.OFF,
        max_pages=1,
        workers=1,
        resume=False,
        page_breaks=True,
        keep_intermediates=True,
    )


def _collect_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, nested in value.items():
            keys.add(str(key))
            keys.update(_collect_keys(nested))
    elif isinstance(value, list):
        for item in value:
            keys.update(_collect_keys(item))
    return keys


def test_adaptive_effort_never_xhigh_by_default(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()
    config = _base_config(pdf, outdir)

    workflow = TranslationWorkflow(client=object())
    resolved = workflow._resolve_attempt1_effort(  # type: ignore[attr-defined]
        config=config,
        image_used=True,
        ordered_text_chars=0,
    )
    assert resolved == ReasoningEffort.HIGH


def test_run_summary_written_on_failure(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)

    def _fail_page(  # type: ignore[no-untyped-def]
        self, *, client, config, paths, instructions, context_text, page_number, total_pages, ocr_engine
    ):
        return _PageOutcome(
            status=PageStatus.FAILED,
            image_used=False,
            retry_used=False,
            usage={},
            error="runtime_failure",
            page_metadata={
                "started_at_iso": "2026-01-01T00:00:00+00:00",
                "ended_at_iso": "2026-01-01T00:00:01+00:00",
                "wall_seconds": 1.0,
                "attempt1_effort": "high",
            },
        )

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _fail_page)

    summary = TranslationWorkflow(client=object()).run(_base_config(pdf, outdir))

    assert summary.success is False
    assert summary.run_summary_path is not None
    assert summary.run_summary_path.exists()
    payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))
    assert payload["counts"]["pages_failed"] == 1
    assert "cost_estimation_status" in payload
    assert "cost_profile_id" in payload
    assert "budget_cap_usd" in payload
    assert "budget_decision" in payload
    assert "budget_decision_reason" in payload
    assert "budget_pre_run" in payload
    assert "budget_post_run" in payload
    assert "quality_risk_score" in payload
    assert "review_queue_count" in payload
    assert "review_queue" in payload
    assert "advisor_recommendation_applied" in payload
    assert "advisor_recommendation" in payload


def test_telemetry_no_content_fields(tmp_path: Path, monkeypatch) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    outdir = tmp_path / "out"
    outdir.mkdir()

    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(workflow_module, "get_page_count", lambda _pdf: 1)

    def _fail_page(  # type: ignore[no-untyped-def]
        self, *, client, config, paths, instructions, context_text, page_number, total_pages, ocr_engine
    ):
        return _PageOutcome(
            status=PageStatus.FAILED,
            image_used=False,
            retry_used=True,
            usage={"attempt_1": {"input_tokens": 10, "output_tokens": 5, "reasoning_tokens": 3, "total_tokens": 18}},
            error="runtime_failure",
            page_metadata={
                "started_at_iso": "2026-01-01T00:00:00+00:00",
                "ended_at_iso": "2026-01-01T00:00:01+00:00",
                "wall_seconds": 1.0,
                "attempt1_effort": "high",
                "attempt2_effort": "high",
                "retry_reason": "outside_text",
                "status_code": 429,
                "exception_class": "RateLimitError",
                "transport_retries_count": 2,
                "rate_limit_hit": True,
            },
        )

    monkeypatch.setattr(TranslationWorkflow, "_process_page", _fail_page)

    summary = TranslationWorkflow(client=object()).run(_base_config(pdf, outdir))
    assert summary.run_summary_path is not None

    run_state_path = summary.run_dir / "run_state.json"
    state_payload = json.loads(run_state_path.read_text(encoding="utf-8"))
    summary_payload = json.loads(summary.run_summary_path.read_text(encoding="utf-8"))

    forbidden_keys = {
        "source_text",
        "ordered_text",
        "extracted_text",
        "translated_text",
        "output_text",
        "prompt_text",
        "raw_output",
        "image_data_url",
        "image_base64",
        "page_text",
    }

    state_keys = _collect_keys(state_payload)
    summary_keys = _collect_keys(summary_payload)
    assert forbidden_keys.isdisjoint(state_keys)
    assert forbidden_keys.isdisjoint(summary_keys)
