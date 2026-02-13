from __future__ import annotations

import json
from pathlib import Path

from legalpdf_translate.run_report import build_run_report_markdown


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_run_dir(tmp_path: Path) -> Path:
    run_dir = tmp_path / "sample_EN_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("A" * 240, encoding="utf-8")
    (pages_dir / "page_0002.txt").write_text("B short line", encoding="utf-8")

    run_state = {
        "run_started_at": "20260213_010203",
        "run_status": "runtime_failure",
        "halt_reason": "hard_failure",
        "finished_at": "2026-02-13T01:03:10+00:00",
        "pdf_path": str(tmp_path / "input.pdf"),
        "lang": "EN",
        "total_pages": 2,
        "max_pages_effective": 2,
        "selection_start_page": 1,
        "selection_end_page": 2,
        "settings": {
            "image_mode": "auto",
            "ocr_mode": "auto",
            "ocr_engine": "local_then_api",
            "keep_intermediates": True,
            "resume": True,
        },
        "pages": {
            "1": {
                "status": "done",
                "source_route": "direct_text",
                "source_route_reason": "direct_text_usable",
                "image_used": False,
                "image_decision_reason": "not_needed",
                "ocr_engine_used": "none",
                "ocr_failed_reason": "ocr_not_requested",
                "wall_seconds": 1.2,
                "extract_seconds": 0.2,
                "ocr_seconds": 0.0,
                "translate_seconds": 0.9,
                "api_calls_count": 1,
                "transport_retries_count": 0,
                "backoff_wait_seconds_total": 0.0,
                "rate_limit_hit": False,
                "input_tokens": 100,
                "output_tokens": 40,
                "reasoning_tokens": 5,
                "total_tokens": 145,
                "estimated_cost": 0.001,
                "exception_class": "",
                "error": "",
                "retry_reason": "",
            },
            "2": {
                "status": "failed",
                "source_route": "ocr",
                "source_route_reason": "ocr_success",
                "image_used": True,
                "image_decision_reason": "ordered_text_chars_lt_20",
                "ocr_engine_used": "local",
                "ocr_failed_reason": "",
                "wall_seconds": 2.4,
                "extract_seconds": 0.2,
                "ocr_seconds": 0.3,
                "translate_seconds": 1.6,
                "api_calls_count": 2,
                "transport_retries_count": 2,
                "backoff_wait_seconds_total": 1.4,
                "rate_limit_hit": True,
                "input_tokens": 120,
                "output_tokens": 50,
                "reasoning_tokens": 8,
                "total_tokens": 178,
                "estimated_cost": 0.002,
                "exception_class": "RateLimitError",
                "error": "runtime_failure",
                "retry_reason": "outside_text",
            },
        },
    }
    _write_json(run_dir / "run_state.json", run_state)

    run_summary = {
        "run_id": "20260213_010203",
        "pdf_path": str(tmp_path / "input.pdf"),
        "lang": "EN",
        "image_mode": "auto",
        "totals": {
            "total_wall_seconds": 3.6,
            "total_cost_estimate_if_available": 0.003,
            "total_input_tokens": 220,
            "total_output_tokens": 90,
            "total_reasoning_tokens": 13,
            "total_tokens": 323,
        },
        "counts": {
            "pages_with_images": 1,
            "pages_with_retries": 1,
            "pages_failed": 1,
            "rate_limit_hits": 1,
            "transport_retries_total": 2,
        },
    }
    _write_json(run_dir / "run_summary.json", run_summary)

    events = [
        {
            "timestamp": "2026-02-13T01:02:00+00:00",
            "event_type": "run_started",
            "stage": "run",
            "page_index": None,
            "duration_ms": None,
            "counters": {},
            "decisions": {},
            "warning": None,
            "error": None,
            "details": {},
        },
        {
            "timestamp": "2026-02-13T01:02:07+00:00",
            "event_type": "api_call_failed",
            "stage": "translate",
            "page_index": 2,
            "duration_ms": 500.0,
            "counters": {"attempt": 1},
            "decisions": {},
            "warning": None,
            "error": "Authorization: Bearer sk-SECRETKEY12345",
            "details": {},
        },
    ]
    (run_dir / "run_events.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n",
        encoding="utf-8",
    )
    return run_dir


def test_admin_run_report_contains_sections_schema_and_redaction(tmp_path: Path) -> None:
    run_dir = _seed_run_dir(tmp_path)
    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=True,
    )

    assert "## Summary" in markdown
    assert "## Timeline" in markdown
    assert "## JSON" in markdown
    assert '"schema_version": "admin_run_report_v1"' in markdown
    assert "## Per-Page Rollups" in markdown
    assert "## Sanitized Snippets" in markdown
    assert "sk-SECRETKEY12345" not in markdown
    assert "Bearer sk-SECRETKEY12345" not in markdown
    assert "[REDACTED]" in markdown
    assert "Page 1: `" in markdown
    # Snippet is hard-capped at 200 chars per page.
    assert ("A" * 205) not in markdown


def test_basic_run_report_omits_admin_verbose_sections(tmp_path: Path) -> None:
    run_dir = _seed_run_dir(tmp_path)
    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=False,
        include_sanitized_snippets=True,
    )
    assert '"schema_version": "basic_run_report_v1"' in markdown
    assert "## Per-Page Rollups" not in markdown
    assert "## Sanitized Snippets" not in markdown
