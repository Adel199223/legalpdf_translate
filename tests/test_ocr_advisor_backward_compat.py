from __future__ import annotations

import json
from pathlib import Path

from legalpdf_translate.run_report import build_run_report_markdown


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_run_report_remains_compatible_without_advisor_keys(tmp_path: Path) -> None:
    run_dir = tmp_path / "legacy_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("Translated page", encoding="utf-8")

    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260305_120000",
            "run_status": "completed",
            "halt_reason": "",
            "finished_at": "2026-03-05T12:00:59+00:00",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "total_pages": 1,
            "max_pages_effective": 1,
            "selection_start_page": 1,
            "selection_end_page": 1,
            "settings": {
                "image_mode": "auto",
                "ocr_mode": "auto",
                "ocr_engine": "local_then_api",
                "keep_intermediates": True,
                "resume": False,
            },
            "pages": {
                "1": {
                    "status": "done",
                    "source_route": "direct_text",
                    "source_route_reason": "direct_text_usable",
                    "image_used": False,
                    "ocr_requested": False,
                    "ocr_used": False,
                    "ocr_provider_configured": True,
                    "ocr_engine_used": "none",
                    "ocr_failed_reason": "ocr_not_requested",
                    "wall_seconds": 0.7,
                    "extract_seconds": 0.2,
                    "ocr_seconds": 0.0,
                    "translate_seconds": 0.4,
                    "api_calls_count": 1,
                    "transport_retries_count": 0,
                    "backoff_wait_seconds_total": 0.0,
                    "rate_limit_hit": False,
                    "input_tokens": 48,
                    "output_tokens": 20,
                    "reasoning_tokens": 3,
                    "total_tokens": 71,
                    "estimated_cost": 0.0008,
                    "exception_class": "",
                    "error": "",
                    "retry_reason": "",
                }
            },
        },
    )
    _write_json(
        run_dir / "run_summary.json",
        {
            "run_id": "20260305_120000",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "image_mode": "auto",
            "pipeline": {
                "image_mode": "auto",
                "ocr_mode": "auto",
                "ocr_engine": "local_then_api",
                "ocr_requested": False,
                "ocr_used": False,
                "ocr_provider_configured": True,
                "ocr_requested_pages": 0,
                "ocr_used_pages": 0,
                "ocr_required_pages": 0,
                "ocr_helpful_pages": 0,
                "ocr_preflight_checked": True,
            },
            "totals": {
                "total_wall_seconds": 0.7,
                "total_cost_estimate_if_available": 0.0008,
                "total_input_tokens": 48,
                "total_output_tokens": 20,
                "total_reasoning_tokens": 3,
                "total_tokens": 71,
            },
            "counts": {
                "pages_with_images": 0,
                "pages_with_retries": 0,
                "pages_failed": 0,
                "rate_limit_hits": 0,
                "transport_retries_total": 0,
            },
        },
    )
    (run_dir / "run_events.jsonl").write_text("", encoding="utf-8")

    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )

    assert "## Summary" in markdown
    assert "OCR advisor recommends" not in markdown
    assert "OCR advisor recommendation applied" not in markdown
