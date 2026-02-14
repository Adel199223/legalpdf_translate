"""Tests for lemma-grouped selection: build_lemma_grouped_stats, compute_selection_delta, metadata."""
from __future__ import annotations

from legalpdf_translate.glossary_builder import (
    GlossaryBuilderSuggestion,
    SelectionDelta,
    build_lemma_grouped_stats,
    compute_selection_delta,
    compute_selection_metadata,
    create_builder_stats,
    finalize_builder_suggestions,
    update_builder_stats_from_page,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stats_with_terms(
    term_entries: list[dict],
) -> dict:
    """Build stats from a list of dicts with keys: term, tf, pages, docs, doc_tf, header_hits."""
    stats = create_builder_stats()
    for entry in term_entries:
        term = entry["term"]
        stats["term_tf"][term] = entry.get("tf", 1)
        stats["term_pages"][term] = set(entry.get("pages", []))
        stats["term_docs"][term] = set(entry.get("docs", []))
        stats["term_doc_tf"][term] = dict(entry.get("doc_tf", {}))
        stats["term_header_hits"][term] = entry.get("header_hits", 0)
    return stats


def _suggestion_term_set(suggestions: list[GlossaryBuilderSuggestion]) -> set[str]:
    return {s.source_term for s in suggestions}


# ---------------------------------------------------------------------------
# 1. test_build_lemma_grouped_stats_merges_inflections
# ---------------------------------------------------------------------------

def test_build_lemma_grouped_stats_merges_inflections() -> None:
    """Three surface forms ('arguido', 'arguidos', 'arguida') map to lemma 'arguido'.
    Grouped stats should have one entry keyed by highest-TF surface."""
    stats = _make_stats_with_terms([
        {"term": "arguido", "tf": 10, "pages": {"p1", "p2"}, "docs": {"d1"}, "doc_tf": {"d1": 10}},
        {"term": "arguidos", "tf": 5, "pages": {"p2", "p3"}, "docs": {"d1", "d2"}, "doc_tf": {"d1": 3, "d2": 2}},
        {"term": "arguida", "tf": 2, "pages": {"p1"}, "docs": {"d1"}, "doc_tf": {"d1": 2}},
    ])
    mapping = {"arguido": "arguido", "arguidos": "arguido", "arguida": "arguido"}

    grouped = build_lemma_grouped_stats(stats, mapping)

    assert len(grouped["term_tf"]) == 1
    # Representative should be "arguido" (highest TF = 10)
    assert "arguido" in grouped["term_tf"]
    assert grouped["term_tf"]["arguido"] == 17  # 10 + 5 + 2
    assert grouped["term_pages"]["arguido"] == {"p1", "p2", "p3"}
    assert grouped["term_docs"]["arguido"] == {"d1", "d2"}
    assert grouped["term_header_hits"]["arguido"] == 0


# ---------------------------------------------------------------------------
# 2. test_build_lemma_grouped_stats_preserves_unmatched
# ---------------------------------------------------------------------------

def test_build_lemma_grouped_stats_preserves_unmatched() -> None:
    """Terms not in mapping appear as-is (identity mapping via casefold)."""
    stats = _make_stats_with_terms([
        {"term": "tribunal", "tf": 8, "pages": {"p1"}, "docs": {"d1"}, "doc_tf": {"d1": 8}},
        {"term": "arguido", "tf": 4, "pages": {"p1"}, "docs": {"d1"}, "doc_tf": {"d1": 4}},
    ])
    # Mapping only has "arguido"
    mapping = {"arguido": "arguido"}

    grouped = build_lemma_grouped_stats(stats, mapping)

    assert len(grouped["term_tf"]) == 2
    assert "tribunal" in grouped["term_tf"]
    assert "arguido" in grouped["term_tf"]
    assert grouped["term_tf"]["tribunal"] == 8
    assert grouped["term_tf"]["arguido"] == 4


# ---------------------------------------------------------------------------
# 3. test_build_lemma_grouped_stats_merges_doc_tf
# ---------------------------------------------------------------------------

def test_build_lemma_grouped_stats_merges_doc_tf() -> None:
    """Per-doc counts sum correctly across surface variants."""
    stats = _make_stats_with_terms([
        {"term": "arguido", "tf": 6, "pages": {"p1"}, "docs": {"d1", "d2"},
         "doc_tf": {"d1": 4, "d2": 2}},
        {"term": "arguidos", "tf": 3, "pages": {"p2"}, "docs": {"d1"},
         "doc_tf": {"d1": 3}},
    ])
    mapping = {"arguido": "arguido", "arguidos": "arguido"}

    grouped = build_lemma_grouped_stats(stats, mapping)

    doc_tf = grouped["term_doc_tf"]["arguido"]
    assert doc_tf["d1"] == 7  # 4 + 3
    assert doc_tf["d2"] == 2


# ---------------------------------------------------------------------------
# 4. test_selection_delta_detects_added_terms
# ---------------------------------------------------------------------------

def test_selection_delta_detects_added_terms() -> None:
    """Term below threshold individually, passes when grouped by lemma.

    Surface: "arguido" tf=3 (doc_tf d1=3), "arguidos" tf=2 (doc_tf d2=2)
    Neither passes doc_max>=5 alone, neither passes corpus filter alone
    (tf>=3 AND df_docs>=2 → arguido has df=1, arguidos has df=1).

    Grouped: representative "arguido" tf=5, doc_tf d1=3+d2=2 → doc_max=3 (doesn't pass).
    But corpus: tf=5>=3 AND df_docs=2>=2 → passes corpus filter.
    """
    stats = _make_stats_with_terms([
        {"term": "arguido", "tf": 3, "pages": {"p1"}, "docs": {"d1"},
         "doc_tf": {"d1": 3}},
        {"term": "arguidos", "tf": 2, "pages": {"p2"}, "docs": {"d2"},
         "doc_tf": {"d2": 2}},
    ])
    mapping = {"arguido": "arguido", "arguidos": "arguido"}

    surface_suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    grouped_stats = build_lemma_grouped_stats(stats, mapping)
    lemma_suggestions = finalize_builder_suggestions(grouped_stats, target_lang="EN")

    # Surface: neither term passes threshold
    assert "arguido" not in _suggestion_term_set(surface_suggestions)
    assert "arguidos" not in _suggestion_term_set(surface_suggestions)

    # Lemma: grouped "arguido" now passes corpus filter (tf=5, df_docs=2)
    assert "arguido" in _suggestion_term_set(lemma_suggestions)

    delta = compute_selection_delta(surface_suggestions, lemma_suggestions)
    assert delta.affected is True
    assert "arguido" in delta.lemma_only_terms


# ---------------------------------------------------------------------------
# 5. test_selection_delta_detects_removed_terms
# ---------------------------------------------------------------------------

def test_selection_delta_detects_removed_terms() -> None:
    """A surface term that passes individually may be replaced by a different
    representative after lemma grouping.

    "sentença" tf=6 doc_max=6 (passes on its own)
    "sentenças" tf=8 doc_max=8 (passes on its own)
    Mapping: both → lemma "sentença"
    Grouped: representative = "sentenças" (highest TF=8), grouped tf=14
    Surface set has both; lemma set has only "sentenças".
    Delta: surface_only = ["sentença"], lemma_only = [].
    """
    stats = _make_stats_with_terms([
        {"term": "sentença", "tf": 6, "pages": {"p1", "p2"}, "docs": {"d1"},
         "doc_tf": {"d1": 6}},
        {"term": "sentenças", "tf": 8, "pages": {"p1", "p2", "p3"}, "docs": {"d1", "d2"},
         "doc_tf": {"d1": 5, "d2": 3}},
    ])
    mapping = {"sentença": "sentença", "sentenças": "sentença"}

    surface_suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    grouped_stats = build_lemma_grouped_stats(stats, mapping)
    lemma_suggestions = finalize_builder_suggestions(grouped_stats, target_lang="EN")

    # Both pass on surface
    assert "sentença" in _suggestion_term_set(surface_suggestions)
    assert "sentenças" in _suggestion_term_set(surface_suggestions)

    # After grouping, only "sentenças" (highest TF) remains
    assert "sentenças" in _suggestion_term_set(lemma_suggestions)
    assert "sentença" not in _suggestion_term_set(lemma_suggestions)

    delta = compute_selection_delta(surface_suggestions, lemma_suggestions)
    assert delta.affected is True
    assert "sentença" in delta.surface_only_terms
    assert len(delta.lemma_only_terms) == 0


# ---------------------------------------------------------------------------
# 6. test_selection_delta_empty_when_no_mapping
# ---------------------------------------------------------------------------

def test_selection_delta_empty_when_no_mapping() -> None:
    """Empty mapping → identity mapping → no change in selection."""
    stats = _make_stats_with_terms([
        {"term": "tribunal", "tf": 10, "pages": {"p1", "p2"}, "docs": {"d1"},
         "doc_tf": {"d1": 10}},
    ])
    mapping: dict[str, str] = {}

    surface_suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    grouped_stats = build_lemma_grouped_stats(stats, mapping)
    lemma_suggestions = finalize_builder_suggestions(grouped_stats, target_lang="EN")

    delta = compute_selection_delta(surface_suggestions, lemma_suggestions)
    assert delta.affected is False
    assert delta.surface_only_terms == []
    assert delta.lemma_only_terms == []


# ---------------------------------------------------------------------------
# 7. test_compute_selection_metadata_with_delta
# ---------------------------------------------------------------------------

def test_compute_selection_metadata_with_delta() -> None:
    """When selection_delta is provided, metadata includes delta keys."""
    stats = create_builder_stats()
    stats["term_tf"]["x"] = 1

    delta = SelectionDelta(
        surface_only_terms=["a", "b"],
        lemma_only_terms=["c"],
        unchanged_count=5,
        surface_count=7,
        lemma_count=6,
        affected=True,
    )
    meta = compute_selection_metadata(stats, final_count=6, selection_delta=delta)

    assert meta["lemma_grouping_affected_selection"] is True
    assert meta["lemma_selection_changed"] is True
    assert meta["surface_selection_count"] == 7
    assert meta["lemma_selection_count"] == 6
    assert meta["lemma_surface_only_count"] == 2
    assert meta["lemma_only_count"] == 1
    assert meta["lemma_unchanged_count"] == 5
    assert meta["lemma_surface_only_terms"] == ["a", "b"]
    assert meta["lemma_only_terms"] == ["c"]


# ---------------------------------------------------------------------------
# 8. test_compute_selection_metadata_without_delta_unchanged
# ---------------------------------------------------------------------------

def test_compute_selection_metadata_without_delta_unchanged() -> None:
    """Backward-compatible: no delta keys when delta=None."""
    stats = create_builder_stats()
    stats["term_tf"]["x"] = 1

    meta = compute_selection_metadata(stats, final_count=0)

    assert meta["lemma_grouping_affected_selection"] is False
    assert meta["lemma_selection_changed"] is False
    assert "lemma_surface_only_count" not in meta
    assert "lemma_only_count" not in meta
    assert "lemma_unchanged_count" not in meta


# ---------------------------------------------------------------------------
# 8b. test_compute_selection_metadata_lemma_used_same_results
# ---------------------------------------------------------------------------

def test_compute_selection_metadata_lemma_used_same_results() -> None:
    """When lemma was used but sets are identical, flag says 'used' but 'not changed'."""
    stats = create_builder_stats()
    stats["term_tf"]["x"] = 1

    delta = SelectionDelta(
        surface_only_terms=[],
        lemma_only_terms=[],
        unchanged_count=5,
        surface_count=5,
        lemma_count=5,
        affected=False,
    )
    meta = compute_selection_metadata(stats, final_count=5, selection_delta=delta)

    assert meta["lemma_grouping_affected_selection"] is True   # lemma WAS used
    assert meta["lemma_selection_changed"] is False             # but results same
    assert meta["surface_selection_count"] == 5
    assert meta["lemma_selection_count"] == 5
    assert meta["lemma_surface_only_count"] == 0
    assert meta["lemma_only_count"] == 0
    assert meta["lemma_unchanged_count"] == 5


# ---------------------------------------------------------------------------
# 9. test_finalize_on_grouped_stats_produces_valid_suggestions
# ---------------------------------------------------------------------------

def test_finalize_on_grouped_stats_produces_valid_suggestions() -> None:
    """Grouped stats work with existing finalize function and produce
    valid GlossaryBuilderSuggestion objects."""
    stats = _make_stats_with_terms([
        {"term": "arguido", "tf": 4, "pages": {"p1", "p2"}, "docs": {"d1", "d2"},
         "doc_tf": {"d1": 2, "d2": 2}},
        {"term": "arguidos", "tf": 3, "pages": {"p1", "p3"}, "docs": {"d1", "d3"},
         "doc_tf": {"d1": 1, "d3": 2}},
    ])
    mapping = {"arguido": "arguido", "arguidos": "arguido"}

    grouped = build_lemma_grouped_stats(stats, mapping)
    suggestions = finalize_builder_suggestions(grouped, target_lang="EN")

    # Should produce valid suggestions
    for s in suggestions:
        assert isinstance(s, GlossaryBuilderSuggestion)
        assert isinstance(s.source_term, str)
        assert s.target_lang == "EN"
        assert s.occurrences_corpus > 0


# ---------------------------------------------------------------------------
# 10. test_end_to_end_lemma_selection_flow
# ---------------------------------------------------------------------------

def test_end_to_end_lemma_selection_flow() -> None:
    """Full pipeline: multi-page stats → group → finalize → delta → metadata.

    Uses update_builder_stats_from_page to build realistic stats.
    """
    stats = create_builder_stats()

    # Doc A, 3 pages — uses "arguido" and "arguidos"
    for pg in range(1, 4):
        update_builder_stats_from_page(
            doc_id="doc-a",
            page_number=pg,
            text="O arguido apresentou defesa. O arguido foi ouvido.",
            stats=stats,
        )

    # Doc B, 2 pages — uses "arguidos" heavily
    for pg in range(1, 3):
        update_builder_stats_from_page(
            doc_id="doc-b",
            page_number=pg,
            text="Os arguidos foram identificados. Os arguidos foram notificados. Os arguidos declararam.",
            stats=stats,
        )

    # Mapping: both surface forms → lemma "arguido"
    mapping = {"arguido": "arguido", "arguidos": "arguido"}

    surface_suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    grouped_stats = build_lemma_grouped_stats(stats, mapping)
    lemma_suggestions = finalize_builder_suggestions(grouped_stats, target_lang="EN")
    delta = compute_selection_delta(surface_suggestions, lemma_suggestions)
    metadata = compute_selection_metadata(
        stats, final_count=len(lemma_suggestions), selection_delta=delta,
    )

    # Verify metadata shape
    assert isinstance(metadata, dict)
    assert "lemma_grouping_affected_selection" in metadata
    assert isinstance(metadata["final_suggestions_count"], int)

    # Verify delta is consistent
    assert isinstance(delta, SelectionDelta)
    assert delta.surface_count == len(surface_suggestions)
    assert delta.lemma_count == len(lemma_suggestions)
    assert delta.unchanged_count + len(delta.surface_only_terms) == delta.surface_count
    assert delta.unchanged_count + len(delta.lemma_only_terms) == delta.lemma_count
