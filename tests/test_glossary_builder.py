from __future__ import annotations

from legalpdf_translate.glossary_builder import (
    compute_selection_metadata,
    create_builder_stats,
    finalize_builder_suggestions,
    mine_glossary_builder_suggestions,
    update_builder_stats_from_page,
)


def test_builder_filters_identifier_like_terms_and_keeps_repeated_legal_terms() -> None:
    rows = [
        {
            "doc_id": "doc-a",
            "page_number": 1,
            "text": "\n".join(
                [
                    "Ministério Público apresentou acusação.",
                    "Ministério Público apresentou acusação.",
                    "Ministério Público apresentou acusação.",
                    "IBAN PT50002700000000000000000",
                    "Processo 84/26.1PBBJA",
                    "Data 12/01/2025",
                ]
            ),
        },
        {
            "doc_id": "doc-b",
            "page_number": 1,
            "text": "Ministério Público apresentou acusação.",
        },
        {
            "doc_id": "doc-c",
            "page_number": 1,
            "text": "Ministério Público apresentou acusação.",
        },
    ]

    suggestions = mine_glossary_builder_suggestions(rows, target_lang="AR")
    terms = {item.source_term for item in suggestions}

    assert "ministério público" in terms
    assert "pt50002700000000000000000" not in terms
    assert "84 26 pbbja" not in terms
    assert "12 01 2025" not in terms


def test_builder_thresholds_require_repetition_and_are_deterministic() -> None:
    stats = create_builder_stats()
    update_builder_stats_from_page(
        doc_id="doc-a",
        page_number=1,
        text="acusação acusação acusação autos autos",
        stats=stats,
        mode="full_text",
    )
    update_builder_stats_from_page(
        doc_id="doc-b",
        page_number=1,
        text="acusação acusação autos",
        stats=stats,
        mode="full_text",
    )
    update_builder_stats_from_page(
        doc_id="doc-c",
        page_number=1,
        text="acusação autos",
        stats=stats,
        mode="full_text",
    )

    first = finalize_builder_suggestions(stats, target_lang="AR")
    second = finalize_builder_suggestions(stats, target_lang="AR")

    assert [(row.source_term, row.occurrences_corpus, row.df_docs) for row in first] == [
        (row.source_term, row.occurrences_corpus, row.df_docs) for row in second
    ]
    assert any(row.source_term == "acusação" for row in first)


def test_compute_selection_metadata_keys_and_counts() -> None:
    """compute_selection_metadata returns correct keys and counts matching
    finalize_builder_suggestions thresholds."""
    stats = create_builder_stats()
    # doc-a: "acusação" x5 in one doc → passes doc_max ≥ 5
    update_builder_stats_from_page(
        doc_id="doc-a",
        page_number=1,
        text="acusação acusação acusação acusação acusação",
        stats=stats,
        mode="full_text",
    )
    # "arguido" across 3 docs, 1 occurrence each → passes corpus tf ≥ 3 AND df ≥ 2
    for doc_id in ("doc-a", "doc-b", "doc-c"):
        update_builder_stats_from_page(
            doc_id=doc_id,
            page_number=1,
            text="arguido",
            stats=stats,
            mode="full_text",
        )

    suggestions = finalize_builder_suggestions(stats, target_lang="EN")
    meta = compute_selection_metadata(stats, final_count=len(suggestions))

    # All expected keys are present
    expected_keys = {
        "candidates_extracted_total",
        "filter_doc_max_threshold",
        "filter_corpus_tf_threshold",
        "filter_corpus_df_threshold",
        "passed_doc_max_filter",
        "passed_corpus_filter",
        "max_suggestions_cap",
        "final_suggestions_count",
        "lemma_grouping_affected_selection",
        "lemma_selection_changed",
    }
    assert set(meta.keys()) == expected_keys

    # Counts are sensible
    assert meta["candidates_extracted_total"] > 0
    assert meta["final_suggestions_count"] == len(suggestions)
    assert meta["passed_doc_max_filter"] >= 1  # "acusação" passes doc_max ≥ 5
    assert meta["passed_corpus_filter"] >= 1  # "arguido" passes corpus filter
    assert meta["max_suggestions_cap"] is None
    assert meta["lemma_grouping_affected_selection"] is False

    # Thresholds match defaults
    assert meta["filter_doc_max_threshold"] == 5
    assert meta["filter_corpus_tf_threshold"] == 3
    assert meta["filter_corpus_df_threshold"] == 2
