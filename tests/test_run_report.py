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
                "ocr_requested": False,
                "ocr_used": False,
                "ocr_provider_configured": True,
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
                "ocr_requested": True,
                "ocr_used": True,
                "ocr_provider_configured": True,
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
        "pipeline": {
            "image_mode": "auto",
            "ocr_mode": "auto",
            "ocr_engine": "local_then_api",
            "ocr_requested": True,
            "ocr_used": True,
            "ocr_provider_configured": True,
            "ocr_requested_pages": 1,
            "ocr_used_pages": 1,
            "ocr_required_pages": 1,
            "ocr_helpful_pages": 0,
            "ocr_preflight_checked": True,
        },
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
    assert '"ocr_requested": true' in markdown
    assert '"ocr_used": true' in markdown
    assert '"ocr_provider_configured": true' in markdown
    assert '"pt_language_leak_failures": 0' in markdown
    assert '"pt_language_leak_retries": 0' in markdown
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


def test_run_report_clarifies_ocr_not_needed_when_provider_missing(tmp_path: Path) -> None:
    run_dir = tmp_path / "text_only_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("Simple translated text", encoding="utf-8")

    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260213_020304",
            "run_status": "completed",
            "halt_reason": "",
            "finished_at": "2026-02-13T02:03:59+00:00",
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
                    "image_decision_reason": "not_needed",
                    "ocr_requested": False,
                    "ocr_used": False,
                    "ocr_provider_configured": False,
                    "ocr_engine_used": "none",
                    "ocr_failed_reason": "ocr_not_requested",
                    "wall_seconds": 0.8,
                    "extract_seconds": 0.2,
                    "ocr_seconds": 0.0,
                    "translate_seconds": 0.5,
                    "api_calls_count": 1,
                    "transport_retries_count": 0,
                    "backoff_wait_seconds_total": 0.0,
                    "rate_limit_hit": False,
                    "input_tokens": 50,
                    "output_tokens": 20,
                    "reasoning_tokens": 2,
                    "total_tokens": 72,
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
            "run_id": "20260213_020304",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "image_mode": "auto",
            "pipeline": {
                "image_mode": "auto",
                "ocr_mode": "auto",
                "ocr_engine": "local_then_api",
                "ocr_requested": False,
                "ocr_used": False,
                "ocr_provider_configured": False,
                "ocr_requested_pages": 0,
                "ocr_used_pages": 0,
                "ocr_required_pages": 0,
                "ocr_helpful_pages": 0,
                "ocr_preflight_checked": False,
            },
            "totals": {
                "total_wall_seconds": 0.8,
                "total_cost_estimate_if_available": 0.0008,
                "total_input_tokens": 50,
                "total_output_tokens": 20,
                "total_reasoning_tokens": 2,
                "total_tokens": 72,
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

    assert "OCR not used; OCR not requested by routing." in markdown
    assert "WARNING: OCR required" not in markdown
    assert '"ocr_requested": false' in markdown
    assert '"ocr_used": false' in markdown
    assert '"ocr_provider_configured": false' in markdown
    assert '"ocr_required_pages": 0' in markdown
    assert '"ocr_helpful_pages": 0' in markdown
    assert '"ocr_preflight_checked": false' in markdown


def test_run_report_warns_when_ocr_required_but_unavailable(tmp_path: Path) -> None:
    run_dir = tmp_path / "required_unavailable_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("Fallback direct text", encoding="utf-8")

    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260213_030405",
            "run_status": "completed",
            "halt_reason": "",
            "finished_at": "2026-02-13T03:05:59+00:00",
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
                    "source_route_reason": "ocr_requested_engine_unavailable",
                    "image_used": False,
                    "image_decision_reason": "not_needed",
                    "ocr_requested": True,
                    "ocr_request_reason": "required",
                    "ocr_used": False,
                    "ocr_provider_configured": False,
                    "ocr_engine_used": "none",
                    "ocr_failed_reason": "required_unavailable",
                    "extraction_quality_signals": [],
                    "wall_seconds": 0.9,
                    "extract_seconds": 0.2,
                    "ocr_seconds": 0.0,
                    "translate_seconds": 0.6,
                    "api_calls_count": 1,
                    "transport_retries_count": 0,
                    "backoff_wait_seconds_total": 0.0,
                    "rate_limit_hit": False,
                    "input_tokens": 60,
                    "output_tokens": 25,
                    "reasoning_tokens": 3,
                    "total_tokens": 88,
                    "estimated_cost": 0.0009,
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
            "run_id": "20260213_030405",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "image_mode": "auto",
            "pipeline": {
                "image_mode": "auto",
                "ocr_mode": "auto",
                "ocr_engine": "local_then_api",
                "ocr_requested": True,
                "ocr_used": False,
                "ocr_provider_configured": False,
                "ocr_requested_pages": 1,
                "ocr_used_pages": 0,
                "ocr_required_pages": 1,
                "ocr_helpful_pages": 0,
                "ocr_preflight_checked": True,
            },
            "totals": {
                "total_wall_seconds": 0.9,
                "total_cost_estimate_if_available": 0.0009,
                "total_input_tokens": 60,
                "total_output_tokens": 25,
                "total_reasoning_tokens": 3,
                "total_tokens": 88,
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
    (run_dir / "run_events.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-02-13T03:05:01+00:00",
                "event_type": "ocr_required_but_unavailable",
                "stage": "ocr",
                "page_index": 1,
                "warning": "OCR required but unavailable",
                "decisions": {"request_reason": "required"},
                "details": {},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )

    assert "WARNING: OCR required on `1` page(s) but OCR could not run" in markdown
    assert '"ocr_required_pages": 1' in markdown
    assert '"ocr_helpful_pages": 0' in markdown
    assert '"ocr_preflight_checked": true' in markdown


def test_run_report_treats_helpful_unavailable_as_info_only(tmp_path: Path) -> None:
    run_dir = tmp_path / "helpful_unavailable_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("Fallback direct text", encoding="utf-8")

    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260213_040506",
            "run_status": "completed",
            "halt_reason": "",
            "finished_at": "2026-02-13T04:06:59+00:00",
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
                    "source_route_reason": "ocr_helpful_unavailable",
                    "image_used": False,
                    "image_decision_reason": "not_needed",
                    "ocr_requested": False,
                    "ocr_request_reason": "helpful",
                    "ocr_used": False,
                    "ocr_provider_configured": False,
                    "ocr_engine_used": "none",
                    "ocr_failed_reason": "helpful_unavailable",
                    "extraction_quality_signals": ["fragmented_lines", "repetition_dominance"],
                    "wall_seconds": 1.0,
                    "extract_seconds": 0.2,
                    "ocr_seconds": 0.0,
                    "translate_seconds": 0.7,
                    "api_calls_count": 1,
                    "transport_retries_count": 0,
                    "backoff_wait_seconds_total": 0.0,
                    "rate_limit_hit": False,
                    "input_tokens": 65,
                    "output_tokens": 26,
                    "reasoning_tokens": 3,
                    "total_tokens": 94,
                    "estimated_cost": 0.001,
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
            "run_id": "20260213_040506",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "image_mode": "auto",
            "pipeline": {
                "image_mode": "auto",
                "ocr_mode": "auto",
                "ocr_engine": "local_then_api",
                "ocr_requested": False,
                "ocr_used": False,
                "ocr_provider_configured": False,
                "ocr_requested_pages": 0,
                "ocr_used_pages": 0,
                "ocr_required_pages": 0,
                "ocr_helpful_pages": 1,
                "ocr_preflight_checked": True,
            },
            "totals": {
                "total_wall_seconds": 1.0,
                "total_cost_estimate_if_available": 0.001,
                "total_input_tokens": 65,
                "total_output_tokens": 26,
                "total_reasoning_tokens": 3,
                "total_tokens": 94,
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
    (run_dir / "run_events.jsonl").write_text(
        json.dumps(
            {
                "timestamp": "2026-02-13T04:06:01+00:00",
                "event_type": "ocr_helpful_but_unavailable",
                "stage": "ocr",
                "page_index": 1,
                "warning": None,
                "decisions": {"request_reason": "helpful"},
                "details": {"note": "helpful"},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )

    assert "WARNING: OCR required" not in markdown
    assert "were marked as helpful for OCR" in markdown
    assert '"ocr_required_pages": 0' in markdown
    assert '"ocr_helpful_pages": 1' in markdown
    assert '"ocr_preflight_checked": true' in markdown


def test_run_report_timeline_scopes_to_current_run_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "timeline_scope_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("OK", encoding="utf-8")

    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260213_222412",
            "run_status": "completed",
            "halt_reason": "",
            "finished_at": "2026-02-13T22:25:05+00:00",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "AR",
            "total_pages": 1,
            "max_pages_effective": 1,
            "selection_start_page": 1,
            "selection_end_page": 1,
            "settings": {
                "image_mode": "always",
                "ocr_mode": "off",
                "ocr_engine": "api",
                "keep_intermediates": True,
                "resume": False,
            },
            "pages": {
                "1": {
                    "status": "done",
                    "source_route": "direct_text",
                    "source_route_reason": "direct_text_ocr_off",
                    "image_used": True,
                    "image_decision_reason": "image_mode_always",
                    "ocr_requested": False,
                    "ocr_request_reason": "not_requested",
                    "ocr_used": False,
                    "ocr_provider_configured": False,
                    "ocr_engine_used": "none",
                    "ocr_failed_reason": "ocr_not_requested",
                    "extraction_quality_signals": [],
                    "wall_seconds": 1.0,
                    "extract_seconds": 0.1,
                    "ocr_seconds": 0.0,
                    "translate_seconds": 0.8,
                    "api_calls_count": 1,
                    "transport_retries_count": 0,
                    "backoff_wait_seconds_total": 0.0,
                    "rate_limit_hit": False,
                    "input_tokens": 100,
                    "output_tokens": 40,
                    "reasoning_tokens": 10,
                    "total_tokens": 150,
                    "estimated_cost": 0.001,
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
            "run_id": "20260213_222412",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "AR",
            "image_mode": "always",
            "pipeline": {
                "image_mode": "always",
                "ocr_mode": "off",
                "ocr_engine": "api",
                "ocr_requested": False,
                "ocr_used": False,
                "ocr_provider_configured": False,
                "ocr_requested_pages": 0,
                "ocr_used_pages": 0,
                "ocr_required_pages": 0,
                "ocr_helpful_pages": 0,
                "ocr_preflight_checked": False,
            },
            "totals": {
                "total_wall_seconds": 1.0,
                "total_cost_estimate_if_available": 0.001,
                "total_input_tokens": 100,
                "total_output_tokens": 40,
                "total_reasoning_tokens": 10,
                "total_tokens": 150,
            },
            "counts": {
                "pages_with_images": 1,
                "pages_with_retries": 0,
                "pages_failed": 0,
                "rate_limit_hits": 0,
                "transport_retries_total": 0,
            },
        },
    )

    events = [
        {
            "timestamp": "2026-02-13T21:00:00+00:00",
            "event_type": "run_started",
            "stage": "run",
            "page_index": None,
            "duration_ms": None,
            "counters": {},
            "decisions": {},
            "warning": None,
            "error": None,
            "details": {"run_id": "20260213_210000"},
        },
        {
            "timestamp": "2026-02-13T21:00:10+00:00",
            "event_type": "old_event",
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
            "timestamp": "2026-02-13T22:24:12+00:00",
            "event_type": "run_started",
            "stage": "run",
            "page_index": None,
            "duration_ms": None,
            "counters": {},
            "decisions": {},
            "warning": None,
            "error": None,
            "details": {"run_id": "20260213_222412"},
        },
        {
            "timestamp": "2026-02-13T22:24:58+00:00",
            "event_type": "current_event",
            "stage": "translate",
            "page_index": 1,
            "duration_ms": 100.0,
            "counters": {},
            "decisions": {},
            "warning": None,
            "error": None,
            "details": {},
        },
    ]
    (run_dir / "run_events.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in events) + "\n",
        encoding="utf-8",
    )

    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )

    assert "current_event" in markdown
    assert "old_event" not in markdown
    assert '"event_type": "current_event"' in markdown
    assert '"event_type": "old_event"' not in markdown


def test_run_report_adds_pt_leak_counters_and_image_mode_optimization_hint(tmp_path: Path) -> None:
    run_dir = tmp_path / "pt_leak_hint_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("Fallback text", encoding="utf-8")
    (pages_dir / "page_0002.txt").write_text("Translated text", encoding="utf-8")

    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260214_101500",
            "run_status": "runtime_failure",
            "halt_reason": "hard_failure",
            "finished_at": "2026-02-14T10:16:59+00:00",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "FR",
            "total_pages": 2,
            "max_pages_effective": 2,
            "selection_start_page": 1,
            "selection_end_page": 2,
            "settings": {
                "image_mode": "always",
                "ocr_mode": "off",
                "ocr_engine": "api",
                "keep_intermediates": False,
                "resume": False,
            },
            "pages": {
                "1": {
                    "status": "failed",
                    "source_route": "direct_text",
                    "source_route_reason": "direct_text_ocr_off",
                    "extracted_text_chars": 500,
                    "image_used": True,
                    "image_decision_reason": "image_mode_always",
                    "ocr_requested": False,
                    "ocr_request_reason": "not_requested",
                    "ocr_used": False,
                    "ocr_provider_configured": False,
                    "ocr_engine_used": "none",
                    "ocr_failed_reason": "ocr_not_requested",
                    "wall_seconds": 1.5,
                    "extract_seconds": 0.1,
                    "ocr_seconds": 0.0,
                    "translate_seconds": 1.3,
                    "api_calls_count": 2,
                    "transport_retries_count": 0,
                    "backoff_wait_seconds_total": 0.0,
                    "rate_limit_hit": False,
                    "input_tokens": 100,
                    "output_tokens": 60,
                    "reasoning_tokens": 20,
                    "total_tokens": 180,
                    "estimated_cost": None,
                    "exception_class": "",
                    "error": "compliance_failure",
                    "retry_reason": "pt_language_leak",
                },
                "2": {
                    "status": "done",
                    "source_route": "direct_text",
                    "source_route_reason": "direct_text_ocr_off",
                    "extracted_text_chars": 420,
                    "image_used": True,
                    "image_decision_reason": "image_mode_always",
                    "ocr_requested": False,
                    "ocr_request_reason": "not_requested",
                    "ocr_used": False,
                    "ocr_provider_configured": False,
                    "ocr_engine_used": "none",
                    "ocr_failed_reason": "ocr_not_requested",
                    "wall_seconds": 1.0,
                    "extract_seconds": 0.1,
                    "ocr_seconds": 0.0,
                    "translate_seconds": 0.8,
                    "api_calls_count": 1,
                    "transport_retries_count": 0,
                    "backoff_wait_seconds_total": 0.0,
                    "rate_limit_hit": False,
                    "input_tokens": 90,
                    "output_tokens": 40,
                    "reasoning_tokens": 10,
                    "total_tokens": 140,
                    "estimated_cost": None,
                    "exception_class": "",
                    "error": "",
                    "retry_reason": "",
                },
            },
        },
    )
    _write_json(
        run_dir / "run_summary.json",
        {
            "run_id": "20260214_101500",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "FR",
            "image_mode": "always",
            "pipeline": {
                "image_mode": "always",
                "ocr_mode": "off",
                "ocr_engine": "api",
                "ocr_requested": False,
                "ocr_used": False,
                "ocr_provider_configured": False,
                "ocr_requested_pages": 0,
                "ocr_used_pages": 0,
                "ocr_required_pages": 0,
                "ocr_helpful_pages": 0,
                "ocr_preflight_checked": False,
            },
            "totals": {
                "total_wall_seconds": 2.5,
                "total_cost_estimate_if_available": None,
                "total_input_tokens": 190,
                "total_output_tokens": 100,
                "total_reasoning_tokens": 30,
                "total_tokens": 320,
            },
            "counts": {
                "pages_with_images": 2,
                "pages_with_retries": 1,
                "pages_failed": 1,
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

    assert '"pt_language_leak_failures": 1' in markdown
    assert '"pt_language_leak_retries": 1' in markdown
    assert '"image_mode_optimization_hint": "image_mode=always attached images on all pages while EN/FR auto-image heuristics would skip image attachments for this run; consider image_mode=auto."' in markdown
    assert "Optimization hint: image_mode=always attached images on all pages" in markdown


def test_run_report_renders_budget_guardrail_section_when_present(tmp_path: Path) -> None:
    run_dir = _seed_run_dir(tmp_path)
    summary_path = run_dir / "run_summary.json"
    run_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    run_summary.update(
        {
            "cost_estimation_status": "available",
            "cost_profile_id": "default_local",
            "budget_cap_usd": 0.01,
            "budget_decision": "warn",
            "budget_decision_reason": "estimate_exceeds_budget_cap",
            "budget_pre_run": {
                "estimated_cost_usd": 0.023,
                "estimation_status": "available",
            },
            "budget_post_run": {
                "estimated_cost_usd": 0.003,
                "estimation_status": "available",
            },
        }
    )
    _write_json(summary_path, run_summary)

    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )

    assert "Budget guardrail decision `warn`" in markdown
    assert "Budget decision reason: `estimate_exceeds_budget_cap`." in markdown


def test_run_report_legacy_summary_without_budget_keys_remains_compatible(tmp_path: Path) -> None:
    run_dir = _seed_run_dir(tmp_path)
    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )

    assert "## Summary" in markdown
    assert "Budget guardrail decision" not in markdown


def test_run_report_renders_quality_risk_summary_when_present(tmp_path: Path) -> None:
    run_dir = _seed_run_dir(tmp_path)
    summary_path = run_dir / "run_summary.json"
    run_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    run_summary.update(
        {
            "quality_risk_score": 0.4721,
            "review_queue_count": 3,
        }
    )
    _write_json(summary_path, run_summary)

    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )

    assert "Quality risk score `0.4721` with `3` flagged review page(s)." in markdown


def test_run_report_renders_ocr_observability_summary_when_present(tmp_path: Path) -> None:
    run_dir = _seed_run_dir(tmp_path)
    summary_path = run_dir / "run_summary.json"
    run_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    pipeline = dict(run_summary.get("pipeline", {}))
    pipeline.update(
        {
            "ocr_source_profile": "pt_latin_default",
            "ocr_local_pass_strategy": "single_pass_baseline",
            "ocr_api_fallback_policy": "required_only_for_paid_fallback",
            "ocr_quality_score_avg": 0.8123,
            "ocr_track_quality_packet": {
                "enfr_avg": 0.81,
                "ar_avg": 0.66,
                "weighted_score": 0.75,
            },
        }
    )
    run_summary["pipeline"] = pipeline
    _write_json(summary_path, run_summary)

    markdown = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )

    assert "OCR observability: profile `pt_latin_default`" in markdown
    assert "OCR track quality packet: EN/FR avg `0.81`, AR avg `0.66`, weighted `0.75`" in markdown
    assert '"ocr_local_pass_strategy": "single_pass_baseline"' in markdown
    assert '"ocr_api_fallback_policy": "required_only_for_paid_fallback"' in markdown
