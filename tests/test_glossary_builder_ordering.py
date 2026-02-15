"""Deterministic ordering tests for glossary builder suggestion ranking.

Verifies that finalize_builder_suggestions returns suggestions sorted by:
  1. Descending _score (TF-weighted with DF/header boosts)
  2. Descending occurrences_corpus (TF tie-break)
  3. Descending df_docs
  4. Descending df_pages
  5. Ascending casefold(source_term) (alphabetical tie-break)
"""
from __future__ import annotations

from legalpdf_translate.glossary_builder import (
    build_lemma_grouped_stats,
    create_builder_stats,
    finalize_builder_suggestions,
    update_builder_stats_from_page,
)


def _make_stats(
    terms: dict[str, dict],
) -> dict:
    """Build a stats dict from a compact spec.

    terms maps term -> {"tf": int, "pages": list[str], "docs": list[str],
                         "doc_tf": dict[str, int], "header_hits": int}
    """
    stats = create_builder_stats()
    for term, spec in terms.items():
        stats["term_tf"][term] = spec["tf"]
        stats["term_pages"][term] = set(spec.get("pages", []))
        stats["term_docs"][term] = set(spec.get("docs", []))
        stats["term_doc_tf"][term] = spec.get("doc_tf", {})
        stats["term_header_hits"][term] = spec.get("header_hits", 0)
    return stats


def test_higher_tf_ranks_first_when_df_equal() -> None:
    """Term with more corpus occurrences ranks higher when DF is equal."""
    stats = _make_stats({
        "acusação": {
            "tf": 20, "pages": ["d1#1", "d2#1"], "docs": ["d1", "d2"],
            "doc_tf": {"d1": 12, "d2": 8},
        },
        "arguido": {
            "tf": 8, "pages": ["d1#1", "d2#1"], "docs": ["d1", "d2"],
            "doc_tf": {"d1": 5, "d2": 3},
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    terms = [s.source_term for s in suggestions]
    assert terms.index("acusação") < terms.index("arguido")


def test_higher_df_docs_ranks_first_when_tf_close() -> None:
    """Term appearing in more documents ranks higher even with similar TF."""
    stats = _make_stats({
        "tribunal": {
            "tf": 6, "pages": ["d1#1", "d2#1", "d3#1"],
            "docs": ["d1", "d2", "d3"],
            "doc_tf": {"d1": 2, "d2": 2, "d3": 2},
        },
        "sentença": {
            "tf": 7, "pages": ["d1#1", "d1#2"],
            "docs": ["d1"],
            "doc_tf": {"d1": 7},
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    terms = [s.source_term for s in suggestions]
    # tribunal has df_docs=3, sentença has df_docs=1
    # tribunal also gets project scope (df_docs>=2) which gives header_boost=1.15 in sort
    assert terms.index("tribunal") < terms.index("sentença")


def test_alphabetical_tiebreak_when_scores_identical() -> None:
    """When score and all numeric fields match, alphabetical order wins."""
    stats = _make_stats({
        "beta termo": {
            "tf": 10, "pages": ["d1#1", "d2#1"], "docs": ["d1", "d2"],
            "doc_tf": {"d1": 5, "d2": 5},
        },
        "alfa termo": {
            "tf": 10, "pages": ["d1#1", "d2#1"], "docs": ["d1", "d2"],
            "doc_tf": {"d1": 5, "d2": 5},
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    terms = [s.source_term for s in suggestions]
    assert terms == ["alfa termo", "beta termo"]


def test_header_boost_promotes_term() -> None:
    """Term with actual header hits ranks higher than one without, even with same TF/DF."""
    stats = _make_stats({
        "normal term": {
            "tf": 10, "pages": ["d1#1", "d2#1"], "docs": ["d1", "d2"],
            "doc_tf": {"d1": 5, "d2": 5}, "header_hits": 0,
        },
        "header term": {
            "tf": 10, "pages": ["d1#1", "d2#1"], "docs": ["d1", "d2"],
            "doc_tf": {"d1": 5, "d2": 5}, "header_hits": 3,
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    terms = [s.source_term for s in suggestions]
    # "header term" has header_hits=3 → 1.15x boost in _score
    # "normal term" has header_hits=0 → no boost
    assert terms[0] == "header term"
    assert suggestions[0].header_hits == 3
    assert suggestions[1].header_hits == 0


def test_header_hits_stored_on_suggestion() -> None:
    """GlossaryBuilderSuggestion.header_hits reflects actual header hit count."""
    stats = _make_stats({
        "contrato": {
            "tf": 8, "pages": ["d1#1"], "docs": ["d1"],
            "doc_tf": {"d1": 8}, "header_hits": 5,
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    assert len(suggestions) == 1
    assert suggestions[0].header_hits == 5


def test_sort_uses_header_hits_not_scope_as_proxy() -> None:
    """Sort key uses real header_hits, not recommended_scope as proxy.

    Regression test: previously the sort passed
    ``1 if item.recommended_scope == "project" else 0`` as header_hits,
    giving all multi-doc terms a 1.15x boost regardless of actual header hits.
    """
    stats = _make_stats({
        # project-scoped (df_docs=2) but NO header hits
        "projeto termo": {
            "tf": 10, "pages": ["d1#1", "d2#1"], "docs": ["d1", "d2"],
            "doc_tf": {"d1": 5, "d2": 5}, "header_hits": 0,
        },
        # personal-scoped (df_docs=1) but HAS header hits
        "cabeçalho termo": {
            "tf": 10, "pages": ["d1#1", "d1#2", "d1#3", "d1#4", "d1#5"],
            "docs": ["d1"],
            "doc_tf": {"d1": 10}, "header_hits": 4,
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    terms = [s.source_term for s in suggestions]
    # "cabeçalho termo" should rank higher because header_hits=4 gives 1.15x boost,
    # while "projeto termo" has header_hits=0 and gets no boost despite being project-scoped
    assert terms[0] == "cabeçalho termo"


def test_ordering_is_deterministic_across_runs() -> None:
    """Running finalize twice on the same stats produces identical order."""
    stats = create_builder_stats()
    for doc_id in ("d1", "d2", "d3"):
        update_builder_stats_from_page(
            doc_id=doc_id,
            page_number=1,
            text="ministério público arguido sentença tribunal acusação " * 3,
            stats=stats,
            mode="full_text",
        )
    first = finalize_builder_suggestions(stats, target_lang="EN")
    second = finalize_builder_suggestions(stats, target_lang="EN")
    assert [s.source_term for s in first] == [s.source_term for s in second]
    assert [s.occurrences_corpus for s in first] == [s.occurrences_corpus for s in second]
    assert [s.confidence for s in first] == [s.confidence for s in second]


def test_below_threshold_terms_excluded() -> None:
    """Terms that don't meet either threshold path are excluded."""
    stats = _make_stats({
        "raro": {
            "tf": 2, "pages": ["d1#1"], "docs": ["d1"],
            "doc_tf": {"d1": 2},
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    assert len(suggestions) == 0


def test_doc_max_path_passes_single_doc_term() -> None:
    """A term with high TF in one doc passes via doc_max >= min_tf_per_doc."""
    stats = _make_stats({
        "contrato": {
            "tf": 8, "pages": ["d1#1"], "docs": ["d1"],
            "doc_tf": {"d1": 8},
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    assert len(suggestions) == 1
    assert suggestions[0].source_term == "contrato"
    assert suggestions[0].recommended_scope == "personal"


def test_corpus_path_passes_multi_doc_term() -> None:
    """A term with tf>=3 and df_docs>=2 passes via corpus path."""
    stats = _make_stats({
        "sentença": {
            "tf": 3, "pages": ["d1#1", "d2#1"], "docs": ["d1", "d2"],
            "doc_tf": {"d1": 2, "d2": 1},
        },
    })
    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    assert len(suggestions) == 1
    assert suggestions[0].source_term == "sentença"
    assert suggestions[0].recommended_scope == "project"


def test_lemma_grouping_merges_and_reranks() -> None:
    """Lemma grouping merges inflections and can change ranking order."""
    stats = create_builder_stats()
    # "acusação" x3 in doc-a, "acusações" x3 in doc-b → merged TF=6 under lemma
    update_builder_stats_from_page(
        doc_id="doc-a", page_number=1,
        text="acusação acusação acusação",
        stats=stats, mode="full_text",
    )
    update_builder_stats_from_page(
        doc_id="doc-b", page_number=1,
        text="acusações acusações acusações",
        stats=stats, mode="full_text",
    )
    # "tribunal" x4 in doc-a only → TF=4, df_docs=1
    update_builder_stats_from_page(
        doc_id="doc-a", page_number=2,
        text="tribunal tribunal tribunal tribunal",
        stats=stats, mode="full_text",
    )

    # Surface: "acusação" (tf=3, 1 doc), "acusações" (tf=3, 1 doc) — neither passes corpus path
    #          "tribunal" (tf=4, 1 doc) — doesn't pass doc_max=5 either
    surface = finalize_builder_suggestions(stats, target_lang="EN")

    # Lemma: merge "acusação"+"acusações" → representative "acusação" (tf=6, 2 docs)
    lemma_mapping = {"acusação": "acusação", "acusações": "acusação"}
    grouped = build_lemma_grouped_stats(stats, lemma_mapping)
    lemma = finalize_builder_suggestions(grouped, target_lang="EN")

    # Surface might not have "acusação" (depends on thresholds), lemma should
    lemma_terms = {s.source_term for s in lemma}
    assert "acusação" in lemma_terms
    # Merged term has higher TF and multi-doc spread
    acusacao = next(s for s in lemma if s.source_term == "acusação")
    assert acusacao.occurrences_corpus == 6
    assert acusacao.df_docs == 2
