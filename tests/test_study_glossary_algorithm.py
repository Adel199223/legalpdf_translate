from __future__ import annotations

from legalpdf_translate.study_glossary import (
    StudyCandidate,
    StudyGlossaryEntry,
    apply_subsumption_suppression,
    assign_coverage_tiers,
    build_ngram_index,
    compute_non_overlapping_tier_assignment,
    count_non_overlapping_matches,
    create_candidate_stats,
    finalize_study_candidates,
    filter_candidates_by_thresholds,
    merge_study_entries,
    mine_study_candidates,
    normalize_study_entries,
    select_min_cover_set,
    sort_candidates_for_selection,
    tokenize_pt,
    update_candidate_stats_from_page,
)


def test_mine_candidates_excludes_identifier_like_terms() -> None:
    corpus = [
        {
            "doc_id": "doc-a",
            "page_number": 1,
            "text": "\n".join(
                [
                    "SENTENÇA.",
                    "O Ministério Público apresentou acusação.",
                    "O Ministério Público apresentou acusação.",
                    "IBAN PT50002700000000000000000",
                    "Processo 84/26.1PBBJA",
                    "Data 12/01/2025",
                ]
            ),
        },
        {
            "doc_id": "doc-a",
            "page_number": 2,
            "text": "O Ministério Público apresentou acusação.",
        },
    ]

    candidates = mine_study_candidates(corpus, mode="full_text")
    terms = {item.term_pt for item in candidates}

    assert "ministério público" in terms
    assert "84 26 pbbja" not in terms
    assert "12 01 2025" not in terms


def test_select_min_cover_set_reaches_target_with_smallest_prefix() -> None:
    candidates = [
        StudyCandidate("a", tf=50, df_pages=3, score=50.0, confidence=0.9, sample_snippets=[], category="other", df_docs=2),
        StudyCandidate("b", tf=30, df_pages=2, score=30.0, confidence=0.8, sample_snippets=[], category="other", df_docs=2),
        StudyCandidate("c", tf=20, df_pages=1, score=20.0, confidence=0.7, sample_snippets=[], category="other", df_docs=1),
    ]

    selected = select_min_cover_set(candidates, coverage_target=0.80)

    assert [item.term_pt for item in selected] == ["a", "b"]
    assert sum(item.tf for item in selected) / sum(item.tf for item in candidates) >= 0.80


def test_filter_candidates_by_thresholds_applies_doc_and_dispersion_rules() -> None:
    candidates = [
        StudyCandidate("high-tf", tf=6, df_pages=1, score=1.0, confidence=0.5, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("cross-doc", tf=3, df_pages=2, score=1.0, confidence=0.5, sample_snippets=[], category="other", df_docs=2),
        StudyCandidate("discard", tf=2, df_pages=1, score=1.0, confidence=0.5, sample_snippets=[], category="other", df_docs=1),
    ]

    filtered = filter_candidates_by_thresholds(candidates)
    assert [item.term_pt for item in filtered] == ["high-tf", "cross-doc"]


def test_normalize_study_entries_expands_translations_for_new_langs() -> None:
    normalized = normalize_study_entries(
        [
            {
                "term_pt": "acusação",
                "translations_by_lang": {"AR": "الاتهام"},
                "tf": 5,
                "df_pages": 2,
            }
        ],
        ["EN", "FR", "AR", "ES"],
    )

    assert len(normalized) == 1
    assert normalized[0].translations_by_lang == {"EN": "", "FR": "", "AR": "الاتهام", "ES": ""}


def test_merge_study_entries_preserves_manual_translations_and_status() -> None:
    existing = [
        StudyGlossaryEntry(
            term_pt="acusação",
            translations_by_lang={"EN": "indictment", "FR": "", "AR": ""},
            tf=2,
            df_pages=1,
            df_docs=1,
            sample_snippets=[],
            category="procedure",
            status="known",
            next_review_date="2026-02-14",
        )
    ]
    incoming = [
        StudyGlossaryEntry(
            term_pt="acusação",
            translations_by_lang={"EN": "", "FR": "acte d’accusation", "AR": "الاتهام"},
            tf=9,
            df_pages=4,
            df_docs=3,
            sample_snippets=["acusação apresentada"],
            category="procedure",
            status="new",
            next_review_date=None,
        )
    ]

    merged = merge_study_entries(existing, incoming, supported_langs=["EN", "FR", "AR"])

    assert len(merged) == 1
    assert merged[0].translations_by_lang["EN"] == "indictment"
    assert merged[0].translations_by_lang["FR"] == "acte d’accusation"
    assert merged[0].translations_by_lang["AR"] == "الاتهام"
    assert merged[0].status == "known"
    assert merged[0].tf == 9
    assert merged[0].df_pages == 4
    assert merged[0].df_docs == 3


def test_sort_candidates_for_selection_uses_deterministic_tie_breakers() -> None:
    rows = [
        StudyCandidate("zeta", tf=4, df_pages=2, score=10.0, confidence=0.6, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("alpha", tf=4, df_pages=3, score=10.0, confidence=0.6, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("beta", tf=5, df_pages=1, score=10.0, confidence=0.6, sample_snippets=[], category="other", df_docs=1),
    ]

    ordered = sort_candidates_for_selection(rows)

    assert [item.term_pt for item in ordered] == ["beta", "alpha", "zeta"]


def test_streaming_stats_finalize_computes_df_docs_and_tiers() -> None:
    stats = create_candidate_stats()
    update_candidate_stats_from_page(
        doc_id="doc-a",
        page_number=1,
        text="Ministério Público apresentou acusação.\nMinistério Público apresentou acusação.",
        mode="full_text",
        include_snippets=True,
        snippet_max_chars=80,
        stats=stats,
    )
    update_candidate_stats_from_page(
        doc_id="doc-b",
        page_number=1,
        text="Ministério Público apresentou acusação.",
        mode="full_text",
        include_snippets=True,
        snippet_max_chars=80,
        stats=stats,
    )

    candidates = finalize_study_candidates(stats)
    by_term = {item.term_pt: item for item in candidates}
    assert "ministério público" in by_term
    assert by_term["ministério público"].df_docs == 2
    assert by_term["ministério público"].coverage_tier in {"core80", "next15", "long_tail"}


def test_assign_coverage_tiers_is_stable_across_runs() -> None:
    ordered = [
        StudyCandidate("a", tf=40, df_pages=4, score=40.0, confidence=0.9, sample_snippets=[], category="other", df_docs=2),
        StudyCandidate("b", tf=30, df_pages=3, score=30.0, confidence=0.8, sample_snippets=[], category="other", df_docs=2),
        StudyCandidate("c", tf=20, df_pages=2, score=20.0, confidence=0.7, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("d", tf=10, df_pages=1, score=10.0, confidence=0.6, sample_snippets=[], category="other", df_docs=1),
    ]
    first = assign_coverage_tiers(ordered)
    second = assign_coverage_tiers(ordered)

    assert [(item.term_pt, item.coverage_tier) for item in first] == [
        ("a", "core80"),
        ("b", "core80"),
        ("c", "core80"),
        ("d", "next15"),
    ]
    assert [(item.term_pt, item.coverage_tier) for item in first] == [
        (item.term_pt, item.coverage_tier) for item in second
    ]


def test_non_overlapping_coverage_uses_longest_match_first() -> None:
    pages_tokens = [tokenize_pt("ministério público ministério público")]
    candidates = [
        StudyCandidate("ministério público", tf=4, df_pages=1, score=10.0, confidence=0.9, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("ministério", tf=4, df_pages=1, score=9.0, confidence=0.8, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("público", tf=4, df_pages=1, score=8.0, confidence=0.8, sample_snippets=[], category="other", df_docs=1),
    ]
    ranked = sort_candidates_for_selection(candidates)
    ranked_keys = [item.term_pt.casefold() for item in ranked]
    ngram_index = build_ngram_index(ranked, ranked_term_keys=ranked_keys)

    counts, total = count_non_overlapping_matches(pages_tokens, set(ranked_keys), ngram_index)

    assert total == 2
    assert counts["ministério público"] == 2
    assert counts.get("ministério", 0) == 0
    assert counts.get("público", 0) == 0

    tiered = compute_non_overlapping_tier_assignment(ranked, pages_tokens, coverage_target=0.80)
    core_rows = [item.term_pt for item in tiered if item.coverage_tier == "core80"]
    assert core_rows == ["ministério público"]

    selected = select_min_cover_set(ranked, coverage_target=0.80, pages_tokens=pages_tokens)
    assert [item.term_pt for item in selected] == ["ministério público"]


def test_subsumption_suppression_demotes_shorter_term_noise() -> None:
    pages_tokens = [tokenize_pt("ministério público acusação ministério público autos")]
    candidates = [
        StudyCandidate("ministério", tf=2, df_pages=1, score=12.0, confidence=0.8, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("ministério público", tf=2, df_pages=1, score=11.0, confidence=0.8, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("acusação", tf=1, df_pages=1, score=10.0, confidence=0.8, sample_snippets=[], category="other", df_docs=1),
        StudyCandidate("autos", tf=1, df_pages=1, score=9.0, confidence=0.8, sample_snippets=[], category="other", df_docs=1),
    ]

    tiered = compute_non_overlapping_tier_assignment(candidates, pages_tokens, coverage_target=0.80)
    suppressed = apply_subsumption_suppression(tiered, pages_tokens, threshold=0.80)
    by_term = {item.term_pt: item for item in suppressed}

    assert by_term["ministério"].coverage_tier == "long_tail"
    assert by_term["ministério público"].coverage_tier in {"core80", "next15"}
