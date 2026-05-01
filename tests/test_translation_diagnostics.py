"""Tests for translation diagnostics (quality checks, cost estimation, report rendering)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legalpdf_translate.output_normalize import LRI, PDI
from legalpdf_translate.translation_diagnostics import (
    check_bidi_safety,
    check_citation_preservation,
    check_numeric_preservation,
    check_structure,
    check_target_language,
    compute_prompt_metrics,
    estimate_cost,
    run_all_quality_checks,
    system_instructions_hash,
)

# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------


def test_estimate_cost_known_model() -> None:
    cost, expl = estimate_cost(
        model="gpt-4o",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        reasoning_tokens=0,
    )
    assert cost is not None
    assert cost > 0
    assert "gpt-4o" in expl


def test_estimate_cost_unknown_model() -> None:
    cost, expl = estimate_cost(
        model="unknown-model-xyz",
        input_tokens=100,
        output_tokens=100,
        reasoning_tokens=0,
    )
    assert cost is None
    assert "not in built-in" in expl


def test_estimate_cost_env_rates() -> None:
    cost, expl = estimate_cost(
        model="anything",
        input_tokens=2_000_000,
        output_tokens=1_000_000,
        reasoning_tokens=500_000,
        env_input_rate=3.0,
        env_output_rate=12.0,
        env_reasoning_rate=12.0,
    )
    # 2M * 3/1M + 1M * 12/1M + 0.5M * 12/1M = 6 + 12 + 6 = 24
    assert cost is not None
    assert abs(cost - 24.0) < 0.001
    assert "env rates" in expl


# ---------------------------------------------------------------------------
# Prompt metrics
# ---------------------------------------------------------------------------


def test_compute_prompt_metrics_basic() -> None:
    prompt = "Translate this text. <<<BEGIN GLOSSARY>>>arguido=defendant<<<END GLOSSARY>>> Some content."
    metrics = compute_prompt_metrics(
        prompt_text=prompt,
        system_instructions="You are a translator.",
        glossary_source_text="line one\nline two\n\nline three",
    )
    assert metrics["prompt_chars"] == len(prompt)
    assert metrics["system_chars"] == len("You are a translator.")
    assert metrics["glossary_chars"] > 0
    assert metrics["segment_count"] == 3  # 3 non-empty lines


def test_system_instructions_hash_deterministic() -> None:
    h1 = system_instructions_hash("test instructions")
    h2 = system_instructions_hash("test instructions")
    assert h1 == h2
    assert len(h1) == 12


# ---------------------------------------------------------------------------
# Quality checks: numeric preservation
# ---------------------------------------------------------------------------


def test_numeric_preservation_all_present() -> None:
    source = "Art. 256 n.º 1 alínea a) valor de 1.500,00 EUR."
    output = "Art. 256 No. 1 subparagraph a) amount of 1.500,00 EUR."
    result = check_numeric_preservation(source, output)
    assert result["missing_count"] == 0
    assert result["extra_count"] == 0


def test_numeric_preservation_missing_number() -> None:
    source = "Artigo 123 e artigo 456."
    output = "Article 123."
    result = check_numeric_preservation(source, output)
    assert result["missing_count"] > 0
    assert 456 in [int(n) for n in result["missing_sample"]] or "456" in result["missing_sample"]


# ---------------------------------------------------------------------------
# Quality checks: citation preservation
# ---------------------------------------------------------------------------


def test_citation_preservation_balanced() -> None:
    source = "Art. 256.º n.º 1 alínea a) do Código Penal."
    output = "Art. 256 No. 1 subparagraph a) of the Penal Code."
    result = check_citation_preservation(source, output)
    # Exact deltas depend on regex, but parens should be similar
    assert isinstance(result["citation_delta"], int)
    assert isinstance(result["parens_delta"], int)
    assert result["citation_marker_delta_abs"] == abs(result["citation_delta"])
    assert result["parenthesis_delta_abs"] == abs(result["parens_delta"])
    assert result["source_citation_marker_count"] == result["source_citations"]
    assert result["output_citation_marker_count"] == result["output_citations"]


# ---------------------------------------------------------------------------
# Quality checks: structure
# ---------------------------------------------------------------------------


def test_structure_no_collapse() -> None:
    source = "Para 1.\nPara 2.\nPara 3.\nPara 4."
    output = "Para 1.\nPara 2.\nPara 3.\nPara 4."
    result = check_structure(source, output)
    assert result["collapse_warning"] is False
    assert result["paragraph_delta"] == 0


def test_structure_collapse_detected() -> None:
    source = "P1.\nP2.\nP3.\nP4.\nP5.\nP6.\nP7.\nP8.\nP9.\nP10."
    output = "All paragraphs merged into one."
    result = check_structure(source, output)
    assert result["collapse_warning"] is True


# ---------------------------------------------------------------------------
# Quality checks: bidi safety
# ---------------------------------------------------------------------------


def test_bidi_clean_text() -> None:
    result = check_bidi_safety("Normal English text with no bidi marks.")
    assert result["bidi_control_count"] == 0
    assert result["bidi_warning"] is False


def test_bidi_warning_many_controls() -> None:
    text = "text" + "\u200f" * 25 + "more"
    result = check_bidi_safety(text)
    assert result["bidi_control_count"] == 25
    assert result["bidi_warning"] is True


# ---------------------------------------------------------------------------
# Quality checks: target language
# ---------------------------------------------------------------------------


def test_target_language_en_detection() -> None:
    output = "The defendant was acquitted of all charges by the court."
    result = check_target_language(output, "EN")
    assert result["language_ok"] is True


def test_target_language_ar_not_portuguese() -> None:
    output = "\u0627\u0644\u0645\u062a\u0647\u0645 \u062a\u0645\u062a \u062a\u0628\u0631\u0626\u062a\u0647"
    result = check_target_language(output, "AR")
    # For AR, language_ok means detected != PT
    assert result["language_ok"] is True


def test_target_language_ar_ignores_portuguese_inside_protected_tokens() -> None:
    output = f"النص العربي {LRI}[[Tribunal Judicial da Comarca de Beja]]{PDI}"
    result = check_target_language(output, "AR")
    assert result["language_ok"] is True
    assert result["detected_lang"] == "AUTO"


def test_target_language_ar_rejects_portuguese_after_token_strip() -> None:
    output = "ãõç"
    result = check_target_language(output, "AR")
    assert result["language_ok"] is False
    assert result["detected_lang"] == "PT"


# ---------------------------------------------------------------------------
# Combined quality checks
# ---------------------------------------------------------------------------


def test_run_all_quality_checks_returns_expected_keys() -> None:
    source = "O arguido foi condenado. Art. 256.º n.º 1."
    output = "The defendant was convicted. Art. 256 No. 1."
    result = run_all_quality_checks(
        source_text=source,
        output_text=output,
        target_lang="EN",
    )
    expected_keys = {
        "language_ok", "detected_lang",
        "numeric_mismatches_count", "numeric_missing_sample",
        "citation_mismatches_count",
        "citation_marker_delta_abs", "parenthesis_delta_abs",
        "source_citation_marker_count", "output_citation_marker_count",
        "source_parenthesis_marker_count", "output_parenthesis_marker_count",
        "structure_warnings_count", "source_paragraphs", "output_paragraphs",
        "bidi_warnings_count", "bidi_control_count", "replacement_char_count",
    }
    assert expected_keys.issubset(set(result.keys()))
    assert result["citation_mismatches_count"] == (
        result["citation_marker_delta_abs"] + result["parenthesis_delta_abs"]
    )


def test_run_all_quality_checks_includes_extraction_integrity_context() -> None:
    result = run_all_quality_checks(
        source_text="A última remuneração registada ascende a",
        output_text="La dernière rémunération enregistrée s'élève à",
        target_lang="FR",
        integrity_context={
            "extraction_integrity_suspect": True,
            "extraction_integrity_reasons": ["dangling_amount_clause", "vector_gap_cluster"],
            "vector_gap_count": 38,
            "visual_recovery_strategy": "image_grounding_fallback",
            "visual_recovery_used": True,
            "visual_recovery_failed": False,
        },
    )

    assert result["extraction_integrity_warnings_count"] == 1
    assert result["extraction_integrity_reasons"] == ["dangling_amount_clause", "vector_gap_cluster"]
    assert result["vector_gap_count"] == 38
    assert result["visual_recovery_strategy"] == "image_grounding_fallback"
    assert result["visual_recovery_used"] is True
    assert result["visual_recovery_failed"] is False


# ---------------------------------------------------------------------------
# Event emission + report rendering
# ---------------------------------------------------------------------------


def _create_run_artifacts_with_translation_events(run_dir: Path) -> None:
    """Write minimal run artifacts plus translation diagnostic events."""
    run_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(exist_ok=True)

    state: dict[str, Any] = {
        "version": 1,
        "total_pages": 2,
        "max_pages_effective": 2,
        "selection_start_page": 1,
        "selection_end_page": 2,
        "selection_page_count": 2,
        "run_status": "completed",
        "run_dir_abs": str(run_dir),
        "halt_reason": None,
        "finished_at": "2026-01-15T10:30:00+00:00",
        "pages": {
            "1": {
                "status": "done",
                "input_tokens": 500,
                "output_tokens": 200,
                "reasoning_tokens": 50,
                "total_tokens": 750,
                "wall_seconds": 2.5,
            },
            "2": {
                "status": "done",
                "input_tokens": 600,
                "output_tokens": 250,
                "reasoning_tokens": 60,
                "total_tokens": 910,
                "wall_seconds": 3.1,
            },
        },
        "done_count": 2,
        "failed_count": 0,
        "pending_count": 0,
    }
    (run_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    summary: dict[str, Any] = {
        "run_id": "test-translation-diag",
        "pdf_path": "example.pdf",
        "lang": "EN",
        "selected_pages_count": 2,
        "totals": {
            "total_wall_seconds": 5.6,
            "total_input_tokens": 1100,
            "total_output_tokens": 450,
            "total_reasoning_tokens": 110,
            "total_tokens": 1660,
        },
        "counts": {
            "pages_images": 0,
            "pages_retries": 0,
            "pages_failed": 0,
        },
        "pipeline": {},
        "settings": {},
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    # Write translation diagnostics events directly to events JSONL
    from legalpdf_translate.run_report import RunEventCollector

    collector = RunEventCollector(run_dir=run_dir, enabled=True)

    from legalpdf_translate.translation_diagnostics import (
        emit_cost_estimate_event,
        emit_docx_write_event,
        emit_prompt_compiled_event,
        emit_run_config_event,
        emit_validation_summary_event,
    )

    emit_run_config_event(
        collector,
        model="gpt-5.2",
        system_instructions_hash="abc123def456",
        image_mode="auto",
        ocr_mode="auto",
        strip_bidi_controls=True,
        effort_policy="default",
        glossary_entries_count=6,
        glossary_tiers="[1, 2]",
        target_lang="EN",
    )

    for page_idx in (1, 2):
        emit_prompt_compiled_event(
            collector,
            page_index=page_idx,
            metrics={
                "prompt_tokens_est": 320 + page_idx * 10,
                "system_tokens_est": 150,
                "glossary_tokens_est": 80,
                "segment_count": 5 + page_idx,
                "prompt_bloat_warning": False,
            },
        )

        emit_validation_summary_event(
            collector,
            page_index=page_idx,
            checks={
                "language_ok": True,
                "detected_lang": "EN",
                "numeric_mismatches_count": 0,
                "numeric_missing_sample": [],
                "citation_mismatches_count": page_idx - 1,
                "citation_marker_delta_abs": page_idx - 1,
                "parenthesis_delta_abs": 0,
                "source_citation_marker_count": 1,
                "output_citation_marker_count": page_idx,
                "source_parenthesis_marker_count": 2,
                "output_parenthesis_marker_count": 2,
                "structure_warnings_count": 0,
                "bidi_warnings_count": 0,
                "bidi_control_count": 0,
                "replacement_char_count": 0,
            },
        )

    emit_docx_write_event(collector, write_ms=45.2, page_count=2)
    emit_cost_estimate_event(
        collector,
        model="gpt-5.2",
        input_tokens=1100,
        output_tokens=450,
        reasoning_tokens=110,
        estimated_cost=0.006480,
        cost_explanation="built-in table for gpt-5.2",
    )


def test_report_contains_run_configuration(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _create_run_artifacts_with_translation_events(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "### A. Run Configuration" in report
    assert "gpt-5.2" in report
    assert "abc123def456" in report


def test_report_contains_prompt_chunking_table(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _create_run_artifacts_with_translation_events(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "### C. Prompt + Chunking Diagnostics" in report
    assert "Prompt Tokens (est)" in report
    assert "Segments" in report


def test_report_contains_quality_checks_table(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _create_run_artifacts_with_translation_events(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "### D. Translation Quality Checks" in report
    assert "Lang OK" in report
    assert "Numeric" in report


def test_report_contains_cost_estimation(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _create_run_artifacts_with_translation_events(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "### F. Cost Estimation" in report
    assert "$0.006480" in report
    assert "built-in table" in report


def test_report_contains_output_construction(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _create_run_artifacts_with_translation_events(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "### E. Output Construction" in report
    assert "45.2" in report


def test_payload_contains_translation_diagnostics(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _create_run_artifacts_with_translation_events(run_dir)

    from legalpdf_translate.run_report import build_run_report_payload

    payload = build_run_report_payload(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    td = payload.get("translation_diagnostics")
    assert td is not None
    assert "run_config" in td
    assert "prompt_compiled_pages" in td
    assert "validation_pages" in td
    assert "cost_estimate" in td
    assert "docx_write" in td
    assert len(td["prompt_compiled_pages"]) == 2
    assert len(td["validation_pages"]) == 2
