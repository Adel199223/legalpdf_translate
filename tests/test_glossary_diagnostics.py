"""Tests for glossary diagnostics (PKG Pareto + CG match analysis)."""

from __future__ import annotations

from pathlib import Path

from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.glossary_diagnostics import (
    AmbiguousCandidate,
    GlossaryDiagnosticsAccumulator,
    PageCoverageRecord,
    classify_ambiguity_heuristics,
    emit_diagnostics_events,
)
from legalpdf_translate.run_report import RunEventCollector

# ---------------------------------------------------------------------------
# Synthetic 3-page fixture
# ---------------------------------------------------------------------------

_PAGE_1_TEXT = "\n".join([
    "SENTENÇA.",
    "I – RELATÓRIO.",
    "O Ministério Público apresentou acusação contra o arguido.",
    "O arguido foi notificado por carta registada.",
    "Audiência de julgamento realizada em 15/01/2025.",
    "Art. 256.º n.º 1 alínea a) do Código Penal.",
])

_PAGE_2_TEXT = "\n".join([
    "II – SANEAMENTO.",
    "O Ministério Público apresentou a contestação escrita.",
    "Factos Provados:",
    "O arguido utilizou documento falso.",
    "Presunção de inocência aplicável.",
    "Art. 256.º n.º 1 alínea a) do Código Penal.",
])

_PAGE_3_TEXT = "\n".join([
    "III – FUNDAMENTAÇÃO.",
    "O Ministério Público requereu a absolvição.",
    "In dubio pro reo.",
    "O arguido foi absolvido.",
    "Sem custas.",
    "Notifique.",
])

_ALL_PAGES = [_PAGE_1_TEXT, _PAGE_2_TEXT, _PAGE_3_TEXT]

_CG_ENTRIES = [
    GlossaryEntry("Ministério Público", "Public Prosecutor's Office", "exact", "PT", 2),
    GlossaryEntry("arguido", "defendant", "exact", "PT", 2),
    GlossaryEntry("acusação", "indictment", "exact", "PT", 2),
    GlossaryEntry("absolvição", "acquittal", "exact", "PT", 2),
    GlossaryEntry("alínea", "subparagraph", "exact", "PT", 4),
    GlossaryEntry("n.º", "No.", "exact", "PT", 4),
]


def _make_accumulator(pages: list[str] = _ALL_PAGES, cg_entries: list[GlossaryEntry] = _CG_ENTRIES) -> GlossaryDiagnosticsAccumulator:
    acc = GlossaryDiagnosticsAccumulator(total_pages=len(pages))
    acc.set_cg_entries(list(cg_entries))
    for idx, text in enumerate(pages, start=1):
        token_count = acc.record_page_pkg_stats(
            page_index=idx, source_text=text, doc_id="test-doc",
        )
        match_count = acc.record_page_cg_matches(
            page_index=idx, active_entries=list(cg_entries), source_text=text,
        )
        acc.record_page_coverage(PageCoverageRecord(
            page_index=idx,
            total_pages=len(pages),
            source_route="direct_text",
            char_count=len(text),
            segment_count=len([line for line in text.splitlines() if line.strip()]),
            pkg_token_count=token_count,
            cg_entries_active=len(cg_entries),
            cg_matches_count=match_count,
            cg_matched_keys=[],
        ))
    return acc


# ---------------------------------------------------------------------------
# Coverage proof
# ---------------------------------------------------------------------------


def test_coverage_proof_correct_x_over_y() -> None:
    acc = _make_accumulator()
    proof = acc.finalize_coverage_proof()
    assert proof["processed_pages"] == 3
    assert proof["total_pages"] == 3
    assert proof["assertion"] == "Processed pages: 3/3"
    assert len(proof["per_page"]) == 3


def test_coverage_proof_partial() -> None:
    acc = GlossaryDiagnosticsAccumulator(total_pages=5)
    for idx in (1, 3):
        acc.record_page_coverage(PageCoverageRecord(
            page_index=idx, total_pages=5, source_route="direct_text",
            char_count=100, segment_count=5, pkg_token_count=20,
            cg_entries_active=0, cg_matches_count=0, cg_matched_keys=[],
        ))
    proof = acc.finalize_coverage_proof()
    assert proof["processed_pages"] == 2
    assert proof["total_pages"] == 5
    assert "2/5" in proof["assertion"]


# ---------------------------------------------------------------------------
# PKG Pareto
# ---------------------------------------------------------------------------


def test_pkg_pareto_section_exists_and_deterministic() -> None:
    acc = _make_accumulator()
    result1 = acc.finalize_pkg_pareto()
    result2 = acc.finalize_pkg_pareto()

    assert result1["total_tokens"] > 0
    assert result1["unique_terms"] > 0
    assert len(result1["suggested_pkg_candidates"]) > 0
    assert len(result1["core80_terms"]) > 0
    assert result1["top_20_pct_coverage"] > 0.0

    # Determinism
    assert result1["suggested_pkg_candidates"] == result2["suggested_pkg_candidates"]
    assert result1["core80_terms"] == result2["core80_terms"]


def test_pkg_pareto_empty_text() -> None:
    acc = GlossaryDiagnosticsAccumulator(total_pages=1)
    acc.record_page_pkg_stats(page_index=1, source_text="", doc_id="empty")
    result = acc.finalize_pkg_pareto()
    assert result["total_tokens"] == 0
    assert result["unique_terms"] == 0
    assert result["suggested_pkg_candidates"] == []


# ---------------------------------------------------------------------------
# CG matches
# ---------------------------------------------------------------------------


def test_cg_section_includes_active_entries_and_match_totals() -> None:
    acc = _make_accumulator()
    summary = acc.finalize_cg_summary()
    assert summary["entries_loaded"] == len(_CG_ENTRIES)
    assert summary["total_match_count"] > 0
    assert summary["unique_matched_entries"] > 0
    assert len(summary["per_page_matches"]) == 3

    # "Ministério Público" appears on all 3 pages
    all_matched = set()
    for page_rec in summary["per_page_matches"]:
        all_matched.update(page_rec["matched_entries"])
    assert "Ministério Público" in all_matched
    assert "arguido" in all_matched


def test_cg_never_matched_entries() -> None:
    extra_entry = GlossaryEntry("xyzzy_not_found", "translation", "exact", "PT", 2)
    entries = list(_CG_ENTRIES) + [extra_entry]
    acc = _make_accumulator(cg_entries=entries)
    summary = acc.finalize_cg_summary()
    assert "xyzzy_not_found" in summary["never_matched_entries"]


def test_cg_alias_matching_counts_canonical_citation_entries() -> None:
    entries = [
        GlossaryEntry("p. e p. pelos artigos", "x", "contains", "PT", 4),
        GlossaryEntry("alínea", "x", "exact", "PT", 4),
        GlossaryEntry("n.º", "x", "exact", "PT", 4),
    ]
    acc = GlossaryDiagnosticsAccumulator(total_pages=1)
    acc.set_cg_entries(entries)
    acc.record_page_cg_matches(
        page_index=1,
        active_entries=entries,
        source_text="crime p. e p. pelos arts. 153.º, n° 1, al. a) do Código Penal.",
    )

    summary = acc.finalize_cg_summary()
    assert summary["per_page_matches"][0]["matched_entries"] == ["alínea", "n.º", "p. e p. pelos artigos"]
    assert summary["never_matched_entries"] == []


# ---------------------------------------------------------------------------
# Ambiguous Pareto
# ---------------------------------------------------------------------------


def test_ambiguous_pareto_section_exists_even_if_empty() -> None:
    acc = GlossaryDiagnosticsAccumulator(total_pages=1)
    acc.set_cg_entries([])
    acc.record_page_pkg_stats(page_index=1, source_text="simple text", doc_id="d")
    summary = acc.finalize_cg_summary()
    assert "ambiguous_candidates" in summary
    assert isinstance(summary["ambiguous_candidates"], list)
    assert "ambiguous_pareto_core80" in summary


def test_ambiguous_pareto_includes_cg_entries() -> None:
    acc = _make_accumulator()
    summary = acc.finalize_cg_summary()
    # CG entries that matched should appear as ambiguous (heuristic A)
    ambig_terms = {c["source_text"] for c in summary["ambiguous_candidates"]}
    assert "arguido" in ambig_terms or "Ministério Público" in ambig_terms


# ---------------------------------------------------------------------------
# Heuristic unit tests
# ---------------------------------------------------------------------------


def test_ambiguity_heuristic_cg_entry() -> None:
    tags = classify_ambiguity_heuristics(
        "arguido",
        cg_source_texts={"arguido"},
    )
    assert "cg_entry" in tags


def test_ambiguity_heuristic_legal_citation() -> None:
    tags = classify_ambiguity_heuristics(
        "Art. 256.º n.º 1 alínea a)",
        cg_source_texts=set(),
    )
    assert "legal_citation" in tags


def test_ambiguity_heuristic_abbreviation() -> None:
    tags = classify_ambiguity_heuristics(
        "IBAN",
        cg_source_texts=set(),
    )
    assert "abbreviation" in tags


def test_ambiguity_heuristic_mixed_script() -> None:
    tags = classify_ambiguity_heuristics(
        "\u0645\u062d\u0643\u0645\u0629 Court",
        cg_source_texts=set(),
    )
    assert "mixed_script" in tags


def test_ambiguity_heuristic_varied_translation() -> None:
    tags = classify_ambiguity_heuristics(
        "arguido",
        cg_source_texts=set(),
        target_renderings=["defendant", "accused"],
    )
    assert "varied_translation" in tags


def test_ambiguity_no_heuristics() -> None:
    tags = classify_ambiguity_heuristics(
        "simples",
        cg_source_texts=set(),
    )
    assert tags == []


# ---------------------------------------------------------------------------
# Event emission
# ---------------------------------------------------------------------------


def test_events_emitted_to_collector(tmp_path: Path) -> None:
    collector = RunEventCollector(run_dir=tmp_path, enabled=True)
    acc = _make_accumulator(pages=_ALL_PAGES[:2], cg_entries=_CG_ENTRIES)
    emit_diagnostics_events(acc, collector)
    events = collector.snapshot()
    event_types = {e["event_type"] for e in events}
    assert "page_coverage_summary" in event_types
    assert "pkg_pareto_summary" in event_types
    assert "token_pareto_summary" in event_types
    assert "pkg_token_stats_page" in event_types
    assert "cg_load_summary" in event_types
    assert "cg_apply_page" in event_types
    assert "cg_ambiguous_pareto_summary" in event_types
    assert "cg_drift_candidates" in event_types


def test_events_emitted_count(tmp_path: Path) -> None:
    collector = RunEventCollector(run_dir=tmp_path, enabled=True)
    acc = _make_accumulator(pages=_ALL_PAGES, cg_entries=_CG_ENTRIES)
    emit_diagnostics_events(acc, collector)
    events = collector.snapshot()
    # 1 page_coverage_summary + 3 pkg_token_stats_page + 1 pkg_pareto_summary
    # + 1 token_pareto_summary + 1 cg_load_summary + 3 cg_apply_page
    # + 1 cg_ambiguous_pareto_summary + 1 cg_drift_candidates = 12
    assert len(events) == 12


def test_events_none_collector() -> None:
    """emit_diagnostics_events should not crash with None collector."""
    acc = _make_accumulator()
    emit_diagnostics_events(acc, None)  # should not raise


# ---------------------------------------------------------------------------
# Content Token Pareto
# ---------------------------------------------------------------------------


def test_token_pareto_filters_stopwords() -> None:
    """Token Pareto excludes Portuguese stopwords."""
    acc = _make_accumulator()
    result = acc.finalize_token_pareto()
    candidates = result.get("suggested_content_candidates", [])
    candidate_terms = {c["term"].casefold() for c in candidates}
    # Common PT stopwords should not appear
    for sw in ("que", "para", "com", "uma"):
        assert sw not in candidate_terms


def test_token_pareto_unigrams_only() -> None:
    """Token Pareto only includes unigrams (no spaces in terms)."""
    acc = _make_accumulator()
    result = acc.finalize_token_pareto()
    candidates = result.get("suggested_content_candidates", [])
    for item in candidates:
        assert " " not in item["term"], f"Multi-word term found: {item['term']}"


def test_token_pareto_with_lemma_grouping() -> None:
    """Token Pareto uses lemma mapping when set."""
    acc = _make_accumulator()
    acc.set_lemma_mapping({"arguido": "arguido", "arguidos": "arguido"})
    result = acc.finalize_token_pareto()
    assert result.get("lemma_mode") is True
    # When lemma mode is on, candidates may have surface_forms lists
    candidates = result.get("suggested_content_candidates", [])
    if candidates:
        # At least one candidate should exist
        assert isinstance(candidates[0], dict)
        assert "term" in candidates[0]
