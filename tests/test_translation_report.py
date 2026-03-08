"""Tests for enhanced translation admin run report rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legalpdf_translate.run_report import build_run_report_markdown


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_page(
    page_number: int,
    *,
    status: str = "done",
    route: str = "direct_text",
    route_reason: str = "direct_text_usable",
    wall_seconds: float = 1.0,
    extract_seconds: float = 0.1,
    translate_seconds: float = 0.8,
    api_calls_count: int = 1,
    input_tokens: int = 100,
    output_tokens: int = 40,
    reasoning_tokens: int = 5,
    estimated_cost: float | None = 0.001,
    retry_reason: str = "",
    error: str = "",
    image_used: bool = False,
    ocr_used: bool = False,
    extracted_text_chars: int = 400,
    extracted_text_lines: int = 20,
    attempt1_effort: str = "high",
) -> dict[str, Any]:
    total = input_tokens + output_tokens + reasoning_tokens
    return {
        "status": status,
        "source_route": route,
        "source_route_reason": route_reason,
        "image_used": image_used,
        "image_decision_reason": "not_needed",
        "ocr_requested": ocr_used,
        "ocr_request_reason": "required" if ocr_used else "not_requested",
        "ocr_used": ocr_used,
        "ocr_provider_configured": True,
        "ocr_engine_used": "local" if ocr_used else "none",
        "ocr_failed_reason": "",
        "wall_seconds": wall_seconds,
        "extract_seconds": extract_seconds,
        "ocr_seconds": 0.0,
        "translate_seconds": translate_seconds,
        "api_calls_count": api_calls_count,
        "transport_retries_count": 0,
        "backoff_wait_seconds_total": 0.0,
        "rate_limit_hit": False,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total,
        "estimated_cost": estimated_cost,
        "exception_class": "",
        "error": error,
        "retry_reason": retry_reason,
        "extracted_text_chars": extracted_text_chars,
        "extracted_text_lines": extracted_text_lines,
        "attempt1_effort": attempt1_effort,
        "attempt2_effort": "",
        "prompt_build_ms": 2.5,
    }


def _seed_run(
    tmp_path: Path,
    *,
    pages: dict[str, dict[str, Any]],
    events: list[dict[str, Any]],
    total_tokens: int = 323,
    api_calls_total: int = 2,
    wall_seconds: float = 3.0,
    run_status: str = "completed",
) -> Path:
    run_dir = tmp_path / "test_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for pn in pages:
        (pages_dir / f"page_{int(pn):04d}.txt").write_text(f"Text for page {pn}", encoding="utf-8")

    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260214_120000",
            "run_status": run_status,
            "halt_reason": "",
            "finished_at": "2026-02-14T12:01:00+00:00",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "total_pages": len(pages),
            "max_pages_effective": len(pages),
            "selection_start_page": 1,
            "selection_end_page": len(pages),
            "settings": {"image_mode": "auto", "ocr_mode": "auto", "resume": False},
            "pages": pages,
        },
    )
    _write_json(
        run_dir / "run_summary.json",
        {
            "run_id": "20260214_120000",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "image_mode": "auto",
            "pipeline": {},
            "totals": {
                "total_wall_seconds": wall_seconds,
                "api_calls_total": api_calls_total,
                "total_tokens": total_tokens,
                "total_input_tokens": 200,
                "total_output_tokens": 80,
                "total_reasoning_tokens": 10,
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
    all_events: list[dict[str, Any]] = [
        {
            "timestamp": "2026-02-14T12:00:00+00:00",
            "event_type": "run_started",
            "stage": "run",
            "page_index": None,
            "duration_ms": None,
            "counters": {},
            "decisions": {},
            "warning": None,
            "error": None,
            "details": {"run_id": "20260214_120000"},
        },
        *events,
    ]
    (run_dir / "run_events.jsonl").write_text(
        "\n".join(json.dumps(e, ensure_ascii=False) for e in all_events) + "\n",
        encoding="utf-8",
    )
    return run_dir


def _run_config_event(**overrides: Any) -> dict[str, Any]:
    details = {
        "model": "gpt-5.2",
        "system_instructions_hash": "abc123def456",
        "image_mode": "auto",
        "ocr_mode": "auto",
        "strip_bidi_controls": True,
        "effort_policy": "fixed_high",
        "glossary_entries_count": 5,
        "glossary_tiers": "[1, 2]",
        "target_lang": "EN",
        "effort_resolved": "fixed_high",
        "page_breaks": True,
        "workers": 2,
        "resume": False,
        **overrides,
    }
    return {
        "timestamp": "2026-02-14T12:00:01+00:00",
        "event_type": "run_config_summary",
        "stage": "run",
        "page_index": None,
        "duration_ms": None,
        "counters": {},
        "decisions": {},
        "warning": None,
        "error": None,
        "details": details,
    }


def _validation_event(
    page_index: int,
    *,
    numeric_mismatches: int = 0,
    numeric_missing_sample: list[str] | None = None,
    language_ok: bool = True,
    detected_lang: str = "EN",
    source_paragraphs: int = 10,
    output_paragraphs: int = 10,
    citation_mismatches: int = 0,
    structure_warnings: int = 0,
    bidi_warnings: int = 0,
) -> dict[str, Any]:
    return {
        "timestamp": "2026-02-14T12:00:30+00:00",
        "event_type": "translation_validation_summary",
        "stage": "translate",
        "page_index": page_index,
        "duration_ms": None,
        "counters": {
            "numeric_mismatches_count": numeric_mismatches,
            "numeric_missing_sample": numeric_missing_sample or [],
            "citation_mismatches_count": citation_mismatches,
            "structure_warnings_count": structure_warnings,
            "source_paragraphs": source_paragraphs,
            "output_paragraphs": output_paragraphs,
            "bidi_warnings_count": bidi_warnings,
            "bidi_control_count": 0,
            "replacement_char_count": 0,
        },
        "decisions": {"language_ok": language_ok, "detected_lang": detected_lang},
        "warning": None,
        "error": None,
        "details": {},
    }


def _cost_event(
    *,
    model: str = "gpt-5.2",
    input_tokens: int = 200,
    output_tokens: int = 80,
    reasoning_tokens: int = 10,
    estimated_cost: float | None = 0.001234,
    cost_explanation: str = "built-in table for gpt-5.2",
) -> dict[str, Any]:
    return {
        "timestamp": "2026-02-14T12:00:50+00:00",
        "event_type": "cost_estimate_summary",
        "stage": "run",
        "page_index": None,
        "duration_ms": None,
        "counters": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": input_tokens + output_tokens + reasoning_tokens,
        },
        "decisions": {},
        "warning": None,
        "error": None,
        "details": {
            "model": model,
            "estimated_cost": estimated_cost,
            "cost_explanation": cost_explanation,
        },
    }


def _docx_event(
    *,
    write_ms: float = 50.0,
    page_count: int = 3,
    paragraph_count: int = 45,
    run_count: int = 45,
) -> dict[str, Any]:
    return {
        "timestamp": "2026-02-14T12:00:55+00:00",
        "event_type": "docx_write_summary",
        "stage": "assemble",
        "page_index": None,
        "duration_ms": write_ms,
        "counters": {
            "page_count": page_count,
            "paragraph_count": paragraph_count,
            "run_count": run_count,
        },
        "decisions": {},
        "warning": None,
        "error": None,
        "details": {},
    }


# ---------------------------------------------------------------------------
# Tests — existing (updated headings)
# ---------------------------------------------------------------------------


def test_coverage_proof_table_with_assertion(tmp_path: Path) -> None:
    pages = {
        "1": _make_page(1),
        "2": _make_page(2),
        "3": _make_page(3),
    }
    events = [_run_config_event(), _validation_event(1), _validation_event(2), _validation_event(3)]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "### B. Coverage Proof" in md
    assert "**Processed pages: 3/3**" in md
    # Table headers present
    assert "| Page | Status | Route | Why |" in md
    # Table rows for each page
    assert "| 1 | done |" in md
    assert "| 2 | done |" in md
    assert "| 3 | done |" in md


def test_coverage_proof_shows_failed_and_retry_lists(tmp_path: Path) -> None:
    pages = {
        "1": _make_page(1),
        "2": _make_page(2, status="failed", error="compliance_failure"),
        "3": _make_page(3, retry_reason="pt_language_leak"),
    }
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "Pages failed: [2]" in md
    assert "Pages with retries: [3]" in md


def test_sanity_warnings_for_broken_inputs(tmp_path: Path) -> None:
    pages = {"1": _make_page(1, api_calls_count=1)}
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events, api_calls_total=3, total_tokens=0)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "## Sanity Warnings" in md
    assert "total_tokens is 0" in md


def test_sanity_warnings_absent_for_valid_runs(tmp_path: Path) -> None:
    pages = {"1": _make_page(1), "2": _make_page(2)}
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events, api_calls_total=2, total_tokens=323)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "## Sanity Warnings" not in md


def test_quality_checks_section_renders(tmp_path: Path) -> None:
    pages = {"1": _make_page(1), "2": _make_page(2)}
    events = [
        _run_config_event(),
        _validation_event(1, numeric_mismatches=2, numeric_missing_sample=["1.234", "56"]),
        _validation_event(2),
    ]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "### D. Translation Quality Checks" in md
    assert "| 1 | yes | EN |" in md
    assert "#### Numeric Mismatch Samples" in md
    assert "Page 1: missing [" in md
    assert "1.234" in md


def test_cost_estimate_known_model(tmp_path: Path) -> None:
    pages = {"1": _make_page(1)}
    events = [_run_config_event(), _cost_event(model="gpt-5.2", estimated_cost=0.001234)]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "### F. Cost Estimation" in md
    assert "Estimated cost: **$" in md


def test_cost_estimate_unknown_model(tmp_path: Path) -> None:
    pages = {"1": _make_page(1)}
    events = [
        _run_config_event(),
        _cost_event(model="unknown-model-7", estimated_cost=None, cost_explanation="model 'unknown-model-7' not in built-in price table"),
    ]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "unavailable" in md


def test_docx_stats_in_output_construction(tmp_path: Path) -> None:
    pages = {"1": _make_page(1)}
    events = [_run_config_event(), _docx_event(paragraph_count=45, run_count=50)]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "### E. Output Construction" in md
    assert "Paragraphs: **45**" in md
    assert "Runs: **50**" in md


def test_run_config_shows_effort_resolved(tmp_path: Path) -> None:
    pages = {"1": _make_page(1)}
    events = [_run_config_event(effort_resolved="fixed_xhigh", workers=3)]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "### A. Run Configuration" in md
    assert "Effort resolved (attempt 1 default): `fixed_xhigh`" in md
    assert "Workers: `3`" in md


def test_per_page_cost_breakdown(tmp_path: Path) -> None:
    pages = {
        "1": _make_page(1, estimated_cost=0.000500),
        "2": _make_page(2, estimated_cost=0.000700),
    }
    events = [_run_config_event(), _cost_event(estimated_cost=0.001200)]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "#### Per-Page Cost Breakdown" in md
    assert "$0.000500" in md
    assert "$0.000700" in md


def test_legacy_per_page_rollups_hidden_when_diagnostics_present(tmp_path: Path) -> None:
    """When translation diagnostics are present, legacy Per-Page Rollups section is hidden."""
    pages = {"1": _make_page(1)}
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    # Coverage Proof replaces legacy Per-Page Rollups
    assert "### B. Coverage Proof" in md
    assert "## Per-Page Rollups" not in md


# ---------------------------------------------------------------------------
# Tests — new
# ---------------------------------------------------------------------------


def test_translation_diagnostics_wrapper_heading(tmp_path: Path) -> None:
    """Wrapper heading '## Translation Diagnostics' appears before sub-sections."""
    pages = {"1": _make_page(1)}
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "## Translation Diagnostics" in md
    # Wrapper must appear before any ### sub-section
    td_pos = md.index("## Translation Diagnostics")
    first_sub = md.index("### A. Run Configuration")
    assert td_pos < first_sub


def test_coverage_proof_includes_route_reason(tmp_path: Path) -> None:
    """Coverage table 'Why' column shows source_route_reason."""
    pages = {
        "1": _make_page(1, route_reason="direct_text_usable"),
        "2": _make_page(2, route_reason="ocr_fallback_triggered"),
    }
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "direct_text_usable" in md
    assert "ocr_fallback_triggered" in md


def test_sanity_warning_completed_but_empty_timeline(tmp_path: Path) -> None:
    """Sanity warning fires when run_status=completed but no events in JSONL."""
    pages = {"1": _make_page(1)}
    run_dir = tmp_path / "test_run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    (pages_dir / "page_0001.txt").write_text("Text for page 1", encoding="utf-8")

    _write_json(
        run_dir / "run_state.json",
        {
            "run_started_at": "20260214_120000",
            "run_status": "completed",
            "halt_reason": "",
            "finished_at": "2026-02-14T12:01:00+00:00",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "total_pages": 1,
            "max_pages_effective": 1,
            "selection_start_page": 1,
            "selection_end_page": 1,
            "settings": {"image_mode": "auto", "ocr_mode": "auto", "resume": False},
            "pages": pages,
        },
    )
    _write_json(
        run_dir / "run_summary.json",
        {
            "run_id": "20260214_120000",
            "pdf_path": str(tmp_path / "input.pdf"),
            "lang": "EN",
            "image_mode": "auto",
            "pipeline": {},
            "totals": {
                "total_wall_seconds": 1.0,
                "api_calls_total": 1,
                "total_tokens": 100,
                "total_input_tokens": 50,
                "total_output_tokens": 30,
                "total_reasoning_tokens": 5,
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
    # Empty events JSONL — no events at all
    (run_dir / "run_events.jsonl").write_text("", encoding="utf-8")

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "## Sanity Warnings" in md
    assert "Run status is 'completed' but timeline is empty" in md


def test_sanity_warning_incomplete_pages(tmp_path: Path) -> None:
    """Sanity warning fires when some pages failed (done < total)."""
    pages = {
        "1": _make_page(1),
        "2": _make_page(2, status="failed", error="some_error"),
        "3": _make_page(3),
    }
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "## Sanity Warnings" in md
    assert "Only 2/3 pages completed successfully" in md


def test_numeric_samples_capped_at_three(tmp_path: Path) -> None:
    """Only first 3 numeric mismatch samples appear in rendered markdown."""
    pages = {"1": _make_page(1)}
    events = [
        _run_config_event(),
        _validation_event(
            1,
            numeric_mismatches=5,
            numeric_missing_sample=["11", "22", "33", "44", "55"],
        ),
    ]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    # First 3 should appear
    assert "11" in md
    assert "22" in md
    assert "33" in md
    # 4th and 5th should NOT appear in the samples line
    # Find the sample line and check it doesn't contain '44' or '55'
    for line in md.splitlines():
        if "Page 1: missing [" in line:
            assert "44" not in line
            assert "55" not in line
            break
    else:
        raise AssertionError("Numeric mismatch sample line not found")


def test_snippets_only_on_quality_warnings(tmp_path: Path) -> None:
    """Snippets appear only for pages with quality warnings; legacy section suppressed."""
    pages = {
        "1": _make_page(1),  # clean — no warnings
        "2": _make_page(2),  # will have numeric mismatch warning
    }
    events = [
        _run_config_event(),
        _validation_event(1),  # no warnings
        _validation_event(2, numeric_mismatches=3, numeric_missing_sample=["99"]),
    ]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=True)

    # Flagged Page Snippets sub-section should appear for page 2
    assert "#### Flagged Page Snippets" in md
    assert "Page 2" in md
    # Page 1 snippet should NOT appear in the flagged section
    flagged_section_start = md.index("#### Flagged Page Snippets")
    flagged_section = md[flagged_section_start:]
    # The flagged section goes until the next section
    next_section = flagged_section.find("\n### ")
    if next_section > 0:
        flagged_section = flagged_section[:next_section]
    assert "Page 1" not in flagged_section
    # Legacy Sanitized Snippets should be suppressed
    assert "## Sanitized Snippets" not in md


def test_output_construction_shows_text_only_note(tmp_path: Path) -> None:
    """Output Construction section includes text-only pipeline note."""
    pages = {"1": _make_page(1)}
    events = [_run_config_event(), _docx_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "### E. Output Construction" in md
    assert "text-only pipeline" in md


def test_chunking_note_present(tmp_path: Path) -> None:
    """Prompt + Chunking section contains 1-chunk-per-page note."""
    pages = {"1": _make_page(1)}
    # Need a prompt_compiled event for section C to render
    prompt_event: dict[str, Any] = {
        "timestamp": "2026-02-14T12:00:10+00:00",
        "event_type": "prompt_compiled",
        "stage": "translate",
        "page_index": 1,
        "duration_ms": None,
        "counters": {
            "prompt_tokens_est": 500,
            "system_tokens_est": 200,
            "glossary_tokens_est": 100,
            "segment_count": 15,
        },
        "decisions": {"prompt_bloat_warning": False},
        "warning": None,
        "error": None,
        "details": {},
    }
    events = [_run_config_event(), prompt_event]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "### C. Prompt + Chunking Diagnostics" in md
    assert "1 chunk per page" in md


def test_report_sanity_summary_in_payload(tmp_path: Path) -> None:
    """JSON payload contains report_sanity_summary with expected fields."""
    pages = {"1": _make_page(1), "2": _make_page(2)}
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    # Extract JSON block from markdown
    json_start = md.index("```json\n") + len("```json\n")
    json_end = md.index("\n```", json_start)
    payload = json.loads(md[json_start:json_end])

    assert "report_sanity_summary" in payload
    summary = payload["report_sanity_summary"]
    assert "processed_pages" in summary
    assert "total_pages" in summary
    assert "timeline_event_count" in summary
    assert "sanity_warnings" in summary
    assert isinstance(summary["sanity_warnings"], list)
    assert summary["total_pages"] == 2  # from detected_page_count
    assert summary["processed_pages"] == 2


def test_translation_report_renders_gmail_batch_context_section(tmp_path: Path) -> None:
    pages = {"1": _make_page(1)}
    events = [_run_config_event()]
    run_dir = _seed_run(tmp_path, pages=pages, events=events)

    summary_path = run_dir / "run_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["gmail_batch_context"] = {
        "source": "gmail_intake",
        "session_id": "gmail_batch_abc123",
        "message_id": "msg-100",
        "thread_id": "thread-200",
        "selected_attachment_filename": "21-25.pdf",
        "selected_attachment_count": 1,
        "selected_target_lang": "AR",
        "gmail_batch_session_report_path": r"C:\Users\FA507\Downloads\gmail_batch_session.json",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    md = build_run_report_markdown(run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False)

    assert "## Gmail Intake / Batch Context" in md
    assert "msg-100" in md
    assert "thread-200" in md
    assert "selected attachment: `21-25.pdf`".lower() in md.lower()
