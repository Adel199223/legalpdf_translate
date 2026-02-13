from __future__ import annotations

from legalpdf_translate.glossary_builder import (
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
