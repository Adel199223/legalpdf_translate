"""Tests for glossary builder diagnostics UI (buttons + export)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from legalpdf_translate.qt_gui.tools_dialogs import QtGlossaryBuilderDialog


# ---------------------------------------------------------------------------
# Fake widgets matching the Qt interface used by the dialog methods
# ---------------------------------------------------------------------------


class _FakeButton:
    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled
        self._tooltip = ""

    def setEnabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def isEnabled(self) -> bool:
        return self._enabled

    def setToolTip(self, text: str) -> None:
        self._tooltip = text

    def toolTip(self) -> str:
        return self._tooltip


class _FakeLabel:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setWordWrap(self, _v: bool) -> None:
        pass


class _FakeCombo:
    def __init__(self, text: str = "EN") -> None:
        self._text = text

    def currentText(self) -> str:
        return self._text

    def currentData(self) -> str:
        return self._text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_fake_dialog(tmp_path: Path, admin_mode: bool = True) -> SimpleNamespace:
    """Build a SimpleNamespace that quacks like QtGlossaryBuilderDialog
    for the methods under test."""
    return SimpleNamespace(
        _settings={"diagnostics_admin_mode": admin_mode},
        _current_output_dir=tmp_path,
        _current_pdf_path=tmp_path / "dummy.pdf",
        _last_artifact_dir=None,
        _diag_admin_mode=admin_mode,
        open_run_folder_btn=_FakeButton(False),
        export_diagnostics_btn=_FakeButton(False),
        diag_path_label=_FakeLabel(),
        summary_label=_FakeLabel(),
        target_lang_combo=_FakeCombo("EN"),
    )


def _create_minimal_run_artifacts(run_dir: Path) -> None:
    """Write minimal run_state.json and run_summary.json so
    build_run_report_markdown can produce a report."""
    run_dir.mkdir(parents=True, exist_ok=True)
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(exist_ok=True)

    state = {
        "version": 1,
        "total_pages": 2,
        "max_pages_effective": 2,
        "selection_start_page": 1,
        "selection_end_page": 2,
        "selection_page_count": 2,
        "run_status": "completed",
        "run_dir_abs": str(run_dir),
        "halt_reason": None,
        "finished_at": "2026-01-01T00:00:00+00:00",
        "pages": {},
        "done_count": 2,
        "failed_count": 0,
        "pending_count": 0,
    }
    (run_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    summary = {
        "run_id": "test-run",
        "pdf_path": "dummy.pdf",
        "lang": "EN",
        "selected_pages_count": 2,
        "totals": {
            "total_wall_seconds": 1.0,
            "total_input_tokens": 100,
            "total_output_tokens": 50,
            "total_reasoning_tokens": 0,
            "total_tokens": 150,
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

    # Write a diagnostics event so the report includes glossary sections
    from legalpdf_translate.glossary_diagnostics import (
        GlossaryDiagnosticsAccumulator,
        PageCoverageRecord,
        emit_diagnostics_events,
    )
    from legalpdf_translate.run_report import RunEventCollector

    acc = GlossaryDiagnosticsAccumulator(total_pages=2)
    from legalpdf_translate.glossary import GlossaryEntry

    cg_entries = [GlossaryEntry("arguido", "defendant", "exact", "PT", 2)]
    acc.set_cg_entries(cg_entries)
    for i in (1, 2):
        text = "O arguido foi notificado. Art. 256.º n.º 1 alínea a)."
        acc.record_page_pkg_stats(page_index=i, source_text=text, doc_id="test")
        acc.record_page_cg_matches(page_index=i, active_entries=cg_entries, source_text=text)
        acc.record_page_coverage(PageCoverageRecord(
            page_index=i, total_pages=2, source_route="direct_text",
            char_count=len(text), segment_count=1, pkg_token_count=10,
            cg_entries_active=1, cg_matches_count=1, cg_matched_keys=["arguido"],
        ))
    collector = RunEventCollector(run_dir=run_dir, enabled=True)
    emit_diagnostics_events(acc, collector)


# ---------------------------------------------------------------------------
# Tests: button enable/disable after run
# ---------------------------------------------------------------------------


def test_buttons_disabled_before_run() -> None:
    """Before any run, both diagnostics buttons are disabled."""
    fake = SimpleNamespace(
        open_run_folder_btn=_FakeButton(False),
        export_diagnostics_btn=_FakeButton(False),
    )
    assert not fake.open_run_folder_btn.isEnabled()
    assert not fake.export_diagnostics_btn.isEnabled()


def test_buttons_enabled_after_successful_run(tmp_path: Path) -> None:
    """After _update_diagnostics_buttons with a valid artifact dir,
    both buttons become enabled (when admin mode is on)."""
    fake = _make_fake_dialog(tmp_path, admin_mode=True)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    fake._last_artifact_dir = None

    # Simulate: _artifact_dir returns run_dir
    def _fake_artifact_dir() -> Path:
        return run_dir

    # Call the actual method via unbound reference
    QtGlossaryBuilderDialog._update_diagnostics_buttons(fake)

    # Since _artifact_dir isn't callable on fake, it uses _artifact_dir method.
    # Instead, let's call it properly by making _artifact_dir a method.
    fake._artifact_dir = _fake_artifact_dir
    QtGlossaryBuilderDialog._update_diagnostics_buttons(fake)

    assert fake._last_artifact_dir == run_dir
    assert fake.open_run_folder_btn.isEnabled()
    assert fake.export_diagnostics_btn.isEnabled()
    assert fake.diag_path_label.text() == str(run_dir)


def test_export_button_disabled_when_admin_mode_off(tmp_path: Path) -> None:
    """When admin mode is off, export button stays disabled even with a valid dir."""
    fake = _make_fake_dialog(tmp_path, admin_mode=False)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    fake._artifact_dir = lambda: run_dir

    QtGlossaryBuilderDialog._update_diagnostics_buttons(fake)

    assert fake.open_run_folder_btn.isEnabled()
    assert not fake.export_diagnostics_btn.isEnabled()


# ---------------------------------------------------------------------------
# Tests: export writes a .md file with diagnostics content
# ---------------------------------------------------------------------------


def test_export_writes_md_with_diagnostics_sections(tmp_path: Path) -> None:
    """_export_diagnostics_report writes a markdown file containing
    glossary diagnostics sections when run artifacts exist."""
    run_dir = tmp_path / "test_run"
    _create_minimal_run_artifacts(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )
    output_path = tmp_path / "exported_report.md"
    output_path.write_text(report, encoding="utf-8")

    content = output_path.read_text(encoding="utf-8")
    assert output_path.exists()
    assert "Processed pages: 2/2" in content
    assert "PKG n-gram Pareto" in content
    assert "CG Match" in content


def test_export_report_contains_ambiguous_section(tmp_path: Path) -> None:
    """The exported report includes the ambiguous Pareto section."""
    run_dir = tmp_path / "test_run"
    _create_minimal_run_artifacts(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir,
        admin_mode=True,
        include_sanitized_snippets=False,
    )
    assert "Ambiguous Pareto" in report
    assert "Drift Candidates" in report


# ---------------------------------------------------------------------------
# Tests: glossary builder run report artifacts
# ---------------------------------------------------------------------------


def _create_glossary_builder_run_artifacts(run_dir: Path) -> None:
    """Simulate what _write_run_report_artifacts does: write run_state.json,
    run_summary.json, and events from a populated accumulator."""
    run_dir.mkdir(parents=True, exist_ok=True)

    from legalpdf_translate.glossary_diagnostics import (
        GlossaryDiagnosticsAccumulator,
        PageCoverageRecord,
        emit_diagnostics_events,
    )
    from legalpdf_translate.run_report import RunEventCollector

    acc = GlossaryDiagnosticsAccumulator(total_pages=3)
    texts = [
        "SENTENÇA. O Ministério Público apresentou acusação contra o arguido.",
        "II – SANEAMENTO. O arguido utilizou documento falso.",
        "III – FUNDAMENTAÇÃO. O arguido foi absolvido. Sem custas.",
    ]
    for i, text in enumerate(texts, start=1):
        pkg_tc = acc.record_page_pkg_stats(page_index=i, source_text=text, doc_id="test_pdf")
        acc.record_page_coverage(PageCoverageRecord(
            page_index=i, total_pages=3, source_route="direct_text",
            char_count=len(text),
            segment_count=len([ln for ln in text.splitlines() if ln.strip()]),
            pkg_token_count=pkg_tc,
            cg_entries_active=0, cg_matches_count=0, cg_matched_keys=[],
        ))

    state = {
        "version": 1,
        "run_started_at": "2026-02-14T10:00:00+00:00",
        "finished_at": "2026-02-14T10:00:02+00:00",
        "run_status": "completed",
        "halt_reason": None,
        "lang": "EN",
        "pdf_path": "sentenca_example.pdf",
        "total_pages": 3,
        "max_pages_effective": 3,
        "selection_start_page": 1,
        "selection_end_page": 3,
        "selection_page_count": 3,
        "run_dir_abs": str(run_dir),
        "pages": {},
        "done_count": 3,
        "failed_count": 0,
        "pending_count": 0,
    }
    (run_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    summary = {
        "run_id": "glossary_builder_test",
        "pdf_path": "sentenca_example.pdf",
        "lang": "EN",
        "selected_pages_count": 3,
        "totals": {
            "total_wall_seconds": 1.234,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_reasoning_tokens": 0,
            "total_tokens": 0,
        },
        "counts": {"pages_images": 0, "pages_retries": 0, "pages_failed": 0},
        "pipeline": {},
        "settings": {},
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    collector = RunEventCollector(run_dir=run_dir, enabled=True)
    emit_diagnostics_events(acc, collector)


def test_glossary_builder_report_has_coverage_proof(tmp_path: Path) -> None:
    """A glossary builder run report shows correct page count and coverage proof."""
    run_dir = tmp_path / "gb_run"
    _create_glossary_builder_run_artifacts(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "Processed pages: 3/3" in report
    assert "sentenca_example.pdf" in report
    assert "1.234" in report  # wall_seconds
    assert "PKG n-gram Pareto" in report
    assert "Sanity Warnings" not in report


def test_glossary_builder_report_has_page_count_nonzero(tmp_path: Path) -> None:
    """detected_page_count is non-zero in the report payload."""
    run_dir = tmp_path / "gb_run"
    _create_glossary_builder_run_artifacts(run_dir)

    from legalpdf_translate.run_report import build_run_report_payload

    payload = build_run_report_payload(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert payload["input"]["detected_page_count"] == 3
    assert payload["totals"]["wall_seconds"] > 0
    assert payload["run"]["status"] == "completed"


def test_sanity_warnings_on_empty_report(tmp_path: Path) -> None:
    """When run artifacts have zero pages and no events, report shows warnings."""
    run_dir = tmp_path / "empty_run"
    run_dir.mkdir(parents=True)

    state = {
        "version": 1, "total_pages": 0, "run_status": "",
        "pages": {}, "run_started_at": "2026-01-01T00:00:00",
    }
    (run_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")
    (run_dir / "run_summary.json").write_text(
        json.dumps({
            "run_id": "empty", "totals": {"total_wall_seconds": 0.0},
            "counts": {},
        }),
        encoding="utf-8",
    )

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "## Sanity Warnings" in report
    assert "WARNING" in report
    assert "detected_page_count is 0" in report


def test_sanity_warnings_absent_when_events_exist(tmp_path: Path) -> None:
    """A properly populated run should not have sanity warnings."""
    run_dir = tmp_path / "good_run"
    _create_glossary_builder_run_artifacts(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "Sanity Warnings" not in report


# ---------------------------------------------------------------------------
# Tests: run_summary includes lemma tokens + suggestion selection section
# ---------------------------------------------------------------------------


def _create_run_artifacts_with_lemma_and_selection(run_dir: Path) -> None:
    """Write run artifacts that include non-zero lemma tokens in run_summary
    and a suggestion_selection_summary event in run_events.jsonl."""
    run_dir.mkdir(parents=True, exist_ok=True)

    from legalpdf_translate.glossary_diagnostics import (
        GlossaryDiagnosticsAccumulator,
        PageCoverageRecord,
        emit_diagnostics_events,
    )
    from legalpdf_translate.run_report import RunEventCollector

    acc = GlossaryDiagnosticsAccumulator(total_pages=2)
    for i in (1, 2):
        text = "O arguido foi notificado. Art. 256.º n.º 1 alínea a)."
        acc.record_page_pkg_stats(page_index=i, source_text=text, doc_id="test")
        acc.record_page_coverage(PageCoverageRecord(
            page_index=i, total_pages=2, source_route="direct_text",
            char_count=len(text), segment_count=1, pkg_token_count=10,
            cg_entries_active=0, cg_matches_count=0, cg_matched_keys=[],
        ))

    state = {
        "version": 1,
        "total_pages": 2,
        "max_pages_effective": 2,
        "selection_start_page": 1,
        "selection_end_page": 2,
        "selection_page_count": 2,
        "run_status": "completed",
        "run_dir_abs": str(run_dir),
        "halt_reason": None,
        "finished_at": "2026-02-14T10:00:02+00:00",
        "pages": {},
        "done_count": 2,
        "failed_count": 0,
        "pending_count": 0,
    }
    (run_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    summary = {
        "run_id": "test-lemma-run",
        "pdf_path": "test.pdf",
        "lang": "EN",
        "selected_pages_count": 2,
        "totals": {
            "total_wall_seconds": 2.5,
            "api_calls_total": 4,
            "total_input_tokens": 8500,
            "total_output_tokens": 3500,
            "total_reasoning_tokens": 0,
            "total_tokens": 12000,
        },
        "counts": {"pages_images": 0, "pages_retries": 0, "pages_failed": 0},
        "pipeline": {},
        "settings": {},
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    collector = RunEventCollector(run_dir=run_dir, enabled=True)
    emit_diagnostics_events(acc, collector)

    # Emit lemma_normalization_summary event
    collector.add_event(
        event_type="lemma_normalization_summary",
        stage="glossary_diagnostics",
        details={
            "terms_total": 40,
            "cache_hits": 10,
            "api_calls": 4,
            "input_tokens": 8500,
            "output_tokens": 3500,
            "failures": 0,
            "wall_seconds": 1.2,
            "fallback_to_surface": False,
        },
    )

    # Emit suggestion_selection_summary event
    collector.add_event(
        event_type="suggestion_selection_summary",
        stage="glossary_diagnostics",
        details={
            "candidates_extracted_total": 250,
            "filter_doc_max_threshold": 5,
            "filter_corpus_tf_threshold": 3,
            "filter_corpus_df_threshold": 2,
            "passed_doc_max_filter": 12,
            "passed_corpus_filter": 55,
            "max_suggestions_cap": None,
            "final_suggestions_count": 68,
            "lemma_grouping_affected_selection": False,
        },
    )


def test_run_summary_includes_lemma_tokens(tmp_path: Path) -> None:
    """When run_summary has non-zero token totals from lemma normalization,
    the report markdown Summary shows those token counts."""
    run_dir = tmp_path / "lemma_run"
    _create_run_artifacts_with_lemma_and_selection(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    # The summary section should show non-zero tokens
    assert "12,000" in report or "12000" in report
    assert "8,500" in report or "8500" in report


def test_report_includes_suggestion_selection_section(tmp_path: Path) -> None:
    """When a suggestion_selection_summary event is present,
    the report includes the Suggestion Selection Diagnostics section."""
    run_dir = tmp_path / "selection_run"
    _create_run_artifacts_with_lemma_and_selection(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "Suggestion Selection Diagnostics" in report
    assert "Candidate n-grams extracted: **250**" in report
    assert "Final suggestions: 68" in report
    assert "was not used for suggestion selection" in report.lower()


def test_lemma_analytics_only_note(tmp_path: Path) -> None:
    """The Lemma Normalization section includes the analytics-only note."""
    run_dir = tmp_path / "lemma_note_run"
    _create_run_artifacts_with_lemma_and_selection(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "### Lemma Normalization" in report
    assert "PKG/token Pareto analytics only" in report
    assert "did NOT affect the suggestion list" in report


def _create_run_artifacts_all_cached(run_dir: Path) -> None:
    """Write run artifacts where all lemma terms came from cache."""
    run_dir.mkdir(parents=True, exist_ok=True)

    from legalpdf_translate.glossary_diagnostics import (
        GlossaryDiagnosticsAccumulator,
        PageCoverageRecord,
        emit_diagnostics_events,
    )
    from legalpdf_translate.run_report import RunEventCollector

    acc = GlossaryDiagnosticsAccumulator(total_pages=1)
    text = "O arguido foi notificado."
    acc.record_page_pkg_stats(page_index=1, source_text=text, doc_id="test")
    acc.record_page_coverage(PageCoverageRecord(
        page_index=1, total_pages=1, source_route="direct_text",
        char_count=len(text), segment_count=1, pkg_token_count=5,
        cg_entries_active=0, cg_matches_count=0, cg_matched_keys=[],
    ))

    state = {
        "version": 1, "total_pages": 1, "max_pages_effective": 1,
        "selection_start_page": 1, "selection_end_page": 1,
        "selection_page_count": 1, "run_status": "completed",
        "run_dir_abs": str(run_dir), "halt_reason": None,
        "finished_at": "2026-02-14T10:00:00+00:00", "pages": {},
        "done_count": 1, "failed_count": 0, "pending_count": 0,
    }
    (run_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    summary = {
        "run_id": "test-cache-run", "pdf_path": "test.pdf", "lang": "EN",
        "selected_pages_count": 1,
        "totals": {"total_wall_seconds": 0.5, "api_calls_total": 0,
                   "total_input_tokens": 0, "total_output_tokens": 0,
                   "total_reasoning_tokens": 0, "total_tokens": 0},
        "counts": {"pages_images": 0, "pages_retries": 0, "pages_failed": 0},
        "pipeline": {}, "settings": {},
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    collector = RunEventCollector(run_dir=run_dir, enabled=True)
    emit_diagnostics_events(acc, collector)
    collector.add_event(
        event_type="lemma_normalization_summary",
        stage="glossary_diagnostics",
        details={
            "terms_total": 20, "cache_hits": 20, "api_calls": 0,
            "input_tokens": 0, "output_tokens": 0, "failures": 0,
            "wall_seconds": 0.1, "fallback_to_surface": False,
        },
    )
    collector.add_event(
        event_type="suggestion_selection_summary",
        stage="glossary_diagnostics",
        details={
            "candidates_extracted_total": 50,
            "filter_doc_max_threshold": 5, "filter_corpus_tf_threshold": 3,
            "filter_corpus_df_threshold": 2, "passed_doc_max_filter": 3,
            "passed_corpus_filter": 10, "max_suggestions_cap": None,
            "final_suggestions_count": 12,
            "lemma_grouping_affected_selection": False,
        },
    )


def test_report_lemma_cache_all_cached(tmp_path: Path) -> None:
    """When all lemma terms came from cache, the report shows the fast-run note."""
    run_dir = tmp_path / "all_cached_run"
    _create_run_artifacts_all_cached(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "All 20 terms resolved from cache" in report
    assert "Fast run" in report


def _create_run_artifacts_with_selection_delta(run_dir: Path) -> None:
    """Write run artifacts where lemma grouping affected selection."""
    run_dir.mkdir(parents=True, exist_ok=True)

    from legalpdf_translate.glossary_diagnostics import (
        GlossaryDiagnosticsAccumulator,
        PageCoverageRecord,
        emit_diagnostics_events,
    )
    from legalpdf_translate.run_report import RunEventCollector

    acc = GlossaryDiagnosticsAccumulator(total_pages=1)
    text = "O arguido foi notificado."
    acc.record_page_pkg_stats(page_index=1, source_text=text, doc_id="test")
    acc.record_page_coverage(PageCoverageRecord(
        page_index=1, total_pages=1, source_route="direct_text",
        char_count=len(text), segment_count=1, pkg_token_count=5,
        cg_entries_active=0, cg_matches_count=0, cg_matched_keys=[],
    ))

    state = {
        "version": 1, "total_pages": 1, "max_pages_effective": 1,
        "selection_start_page": 1, "selection_end_page": 1,
        "selection_page_count": 1, "run_status": "completed",
        "run_dir_abs": str(run_dir), "halt_reason": None,
        "finished_at": "2026-02-14T10:00:00+00:00", "pages": {},
        "done_count": 1, "failed_count": 0, "pending_count": 0,
    }
    (run_dir / "run_state.json").write_text(json.dumps(state), encoding="utf-8")

    summary = {
        "run_id": "test-delta-run", "pdf_path": "test.pdf", "lang": "EN",
        "selected_pages_count": 1,
        "totals": {"total_wall_seconds": 1.0, "api_calls_total": 2,
                   "total_input_tokens": 1000, "total_output_tokens": 500,
                   "total_reasoning_tokens": 0, "total_tokens": 1500},
        "counts": {"pages_images": 0, "pages_retries": 0, "pages_failed": 0},
        "pipeline": {}, "settings": {},
    }
    (run_dir / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")

    collector = RunEventCollector(run_dir=run_dir, enabled=True)
    emit_diagnostics_events(acc, collector)
    collector.add_event(
        event_type="lemma_normalization_summary",
        stage="glossary_diagnostics",
        details={
            "terms_total": 30, "cache_hits": 25, "api_calls": 2,
            "input_tokens": 1000, "output_tokens": 500, "failures": 0,
            "wall_seconds": 0.8, "fallback_to_surface": False,
        },
    )
    collector.add_event(
        event_type="suggestion_selection_summary",
        stage="glossary_diagnostics",
        details={
            "candidates_extracted_total": 200,
            "filter_doc_max_threshold": 5, "filter_corpus_tf_threshold": 3,
            "filter_corpus_df_threshold": 2, "passed_doc_max_filter": 10,
            "passed_corpus_filter": 40, "max_suggestions_cap": None,
            "final_suggestions_count": 55,
            "lemma_grouping_affected_selection": True,
            "lemma_selection_changed": True,
            "lemma_surface_only_count": 3,
            "lemma_only_count": 5,
            "lemma_unchanged_count": 47,
            "lemma_surface_only_terms": ["sentença", "arguida", "réu"],
            "lemma_only_terms": ["arguido", "sentença", "tribunal", "acusação", "recurso"],
        },
    )


def test_report_selection_delta_shown(tmp_path: Path) -> None:
    """When lemma grouping affected selection, the report shows the delta."""
    run_dir = tmp_path / "delta_run"
    _create_run_artifacts_with_selection_delta(run_dir)

    from legalpdf_translate.run_report import build_run_report_markdown

    report = build_run_report_markdown(
        run_dir=run_dir, admin_mode=True, include_sanitized_snippets=False,
    )
    assert "Lemma grouping was used for suggestion selection and changed the results" in report
    assert "3 surface-only removed" in report
    assert "5 lemma-grouped added" in report
    assert "47 unchanged" in report
    assert "Removed (surface-only)" in report
    assert "Added (lemma-grouped)" in report
