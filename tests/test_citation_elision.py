"""Fictional citation elision cases; no retained private document text or calls."""
from collections import Counter
from types import SimpleNamespace

import pytest

from legalpdf_translate import new_translation_blocks as blocks
from legalpdf_translate.translation_structure import BlockCoverageError
from legalpdf_translate.types import TargetLang


def check(source, target, language=TargetLang.FR):
    return blocks.validate_block(
        {"id": "p0001_b0001", "text": source}, target, language, None, set())


def test_public_validator_accepts_expanded_french_article_after_subdivisions():
    # This standalone reproducer imports only symbols available before the fix.
    # The retained failure's grammar is reproduced with unrelated fictional IDs.
    check("artigo 24.º, n.º 1, alínea c) e 35.º, n.º 2, n.º 3, alínea c) e d).",
          "article 24.º, n.º 1, alinéa c) et de l’article 35.º, n.º 2, n.º 3, alinéa c) et d).")


@pytest.mark.parametrize("source,target", [
    ("artigo 24.º, n.º 1, alínea c) e 35.º, n.º 2.",
     "article 24.º, n.º 1, alinéa c) et article 35.º, n.º 2."),
    ("article 24.º, no. 1, et 35.º, no. 2.",
     "article 24.º, no. 1, et article 35.º, no. 2."),
    ("articles 24, 35 and 46.", "article 24, article 35 and article 46."),
    ("artigos 24.º e 35.º do Código.", "articles 24.º et 35.º du Code."),
    ("Article 24-A and 35-B.", "Article 24-A and Article 35-B."),
])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("language", [TargetLang.EN, TargetLang.FR])
def test_explicit_and_elided_heads_are_equivalent_both_directions(source, target, reverse, language):
    if reverse:
        source, target = target, source
    check(source, target, language)
    assert blocks._citation_heads(source) == blocks._citation_heads(target)


@pytest.mark.parametrize("text,expected", [
    ("Artigo 24.º, n.º 1 e 2.", {"24": 1}),
    ("Artigo 24.º, n.º 1, n.º 2 e 3.", {"24": 1}),
    ("Artigo 24.º, alíneas c) e d).", {"24": 1}),
    ("Article 24, paragraphs 1 and 2.", {"24": 1}),
    ("Article 24, paragraphes 1 et 2.", {"24": 1}),
    ("Article 24, subparagraphs c) and d).", {"24": 1}),
    ("Article 24, points c) et d).", {"24": 1}),
    ("Artigo 24.º, n.º 1, alíneas c) e d) e 35.º, n.º 2.", {"24": 1, "35": 1}),
    ("Article 24, paragraph 1 and 35.º.", {"24": 1, "35": 1}),
    ("Article 24, § 1 and 35-A.", {"24": 1, "35-A": 1}),
])
def test_subdivision_lists_keep_their_own_numbers(text, expected):
    assert blocks._citation_heads(text) == Counter(expected)


@pytest.mark.parametrize("text", [
    "Article 24 and 10 days.",
    "Artigo 24.º e 10 dias.",
    "Article 24 et 10 jours.",
    "Article 24 and 10 May 2030.",
    "Article 24 and 10/05/2030.",
    "Article 24 and 10.05.2030.",
    "Article 24 and 10-05-2030.",
    "Article 24 and 35A.",
    "Article 24 and 35.foo.",
    "Article 24 and 35/ABC.",
    "Article 24 and 35,000 units.",
    "Article 24 and 35.50 units.",
    "Article 24 and reference 35.",
    "Article 24, paragraph 1 and 2, with reference 35.",
    "Article 24, subparagraph c) and d), see 35.º.",
    "Article 24 applies with reference to 35.º.",
    "Article 24. And 35.º.",
    "Article 24; and 35.º.",
    "Article 24: and 35.º.",
    "Article 24\nand 35.º.",
    "Article 24 and\n35.º.",
    "Article 24\r\nand 35.º.",
    "Article 24\tand\v35.º.",
    "Article 24 e\f35.º.",
])
def test_dates_deadlines_prose_identifiers_and_line_boundaries_are_not_heads(text):
    assert blocks._citation_heads(text) == Counter({"24": 1})


@pytest.mark.parametrize("source,target", [
    ("Artigos 24.º e 35.º. Referência 46.",
     "Article 24.º et article 46.º. Référence 35."),
    ("Artigos 24.º e 35.º.", "Article 24.º. Référence 35.º."),
    ("Artigo 24.º. Referência 35.º.", "Articles 24.º et 35.º."),
    ("Artigos 24.º e 24.º.", "Article 24.º. Référence 24.º."),
    ("Article 24-A and 35-B.", "Article 24-A and article 35-C."),
    ("Article 24, paragraph 1 and 2.", "Article 24, paragraph 1 and article 2."),
    ("Article 24 and 10 days.", "Article 24 and article 10 days."),
])
def test_same_numeric_multiset_does_not_allow_citation_reference_or_suffix_swaps(source, target):
    assert Counter(blocks._NUMBER.findall(source)) == Counter(blocks._NUMBER.findall(target))
    with pytest.raises(BlockCoverageError, match="^block_citation_association_defect$"):
        check(source, target)


def test_duplicate_elided_heads_keep_exact_multiplicity():
    source = "Artigos 24.º e 24.º. Artigo 35.º."
    target = "Article 24.º et article 24.º. Article 35.º."
    check(source, target)
    assert blocks._citation_heads(source) == Counter({"24": 2, "35": 1})


def test_no_space_comma_list_parser_does_not_override_numeric_token_guard():
    source = "articles 24,35 and 46."
    target = "article 24, article 35 and article 46."
    assert blocks._citation_heads(source) == blocks._citation_heads(target) == Counter({"24": 1, "35": 1, "46": 1})
    # The unchanged number grammar treats 24,35 as one token. Parser equivalence
    # alone cannot authorize changing numeric tokenization in a translation.
    assert Counter(blocks._NUMBER.findall(source)) != Counter(blocks._NUMBER.findall(target))
    with pytest.raises(BlockCoverageError, match="^block_numeric_association_defect$"):
        check(source, target)


@pytest.mark.parametrize("target", [
    "Article 24.º et article 36.º.",
    "Article 24.º.",
    "Article 24.º et article 35.º. Référence 46.",
])
def test_numeric_guard_still_rejects_changed_missing_and_added_numbers(target):
    with pytest.raises(BlockCoverageError, match="^block_numeric_association_defect$"):
        check("Artigos 24.º e 35.º.", target)


@pytest.mark.parametrize("head", ["المادة", "المادتان", "المادتين", "المواد"])
def test_arabic_plain_article_lists_keep_explicit_and_elided_equivalence(head):
    elided = f"{head} 24 و35."
    expanded = "المادة 24 والمادة 35."
    assert blocks._citation_heads(elided) == blocks._citation_heads(expanded) == Counter({"24": 1, "35": 1})
    check("Artigos 24 e 35.", expanded, TargetLang.AR)


def test_arabic_unrecognised_subdivision_words_do_not_borrow_article_head():
    # A numeric paragraph using this label is still outside the supported grammar.
    text = "المادة 24، الفقرة 1 و35."
    assert blocks._citation_heads(text) == Counter({"24": 1})


@pytest.mark.parametrize("head", ["للمادة", "للمادتين", "للمواد", "وللمادة", "فللمادة"])
def test_contracted_arabic_heads_keep_explicit_citation_identity(head):
    target = f"وفقا {head} 27.º من القانون."
    assert blocks._citation_heads(target) == Counter({"27": 1})
    check("Artigo 27.º do Código.", target, TargetLang.AR)


@pytest.mark.parametrize("comma", [",", "،"])
@pytest.mark.parametrize("label,values", [("رقم", "2"), ("الأرقام", "2 و3")])
def test_arabic_number_and_letter_subdivisions_allow_only_marked_next_article(comma, label, values):
    target = f"المادة 27.º{comma} {label} {values}{comma} الفقرة c و42.º{comma} رقم 4 من القانون."
    assert blocks._citation_heads(target) == Counter({"27": 1, "42": 1})


def test_public_arabic_validator_accepts_contraction_and_subdivision_chain_together():
    source = "artigo 27.º, n.º 2, alínea c) e 42.º, n.º 3."
    target = "وفقا للمادة 27.º، رقم 2، الفقرة c) و42.º، رقم 3."
    assert blocks._citation_heads(source) == blocks._citation_heads(target)
    check(source, target, TargetLang.AR)


@pytest.mark.parametrize("text", [
    "كلمةللمادة 27.º.", "لللمادة 27.º.", "للمادية 27.º.",
    "للمادة\n27.º.", "للمواد\u2028 27.º.",
])
def test_contracted_arabic_heads_require_supported_word_and_horizontal_boundary(text):
    assert blocks._citation_heads(text) == Counter()


@pytest.mark.parametrize("tail", [
    "، رقم 2 و42.", "، رقم 2، الفقرة c و42.",
    "، رقم 2 و42 يوما.", "، رقم 2 و42.50 قيمة.",
    "، رقم 2 و42/ABC.", "، رقم 2 و12/05/2030.",
    "، رقم 2؛ و42.º.", "، رقم 2. و42.º.",
    "، رقم 2، الفقرة c، مرجع 42.º.", "، رقم 2، الفقرة word و42.º.",
    "، رقم 2، الفقرة 3 و42.º.", "، رقم 2، الفقرة c\nو42.º.",
    "، رقم\n2 و42.º.", "، رقم 2، الفقرة\u2028c و42.º.",
])
def test_arabic_subdivisions_do_not_promote_values_cross_boundaries_or_read_prose(tail):
    assert blocks._citation_heads("المادة 27.º" + tail) == Counter({"27": 1})


def test_arabic_subdivision_exact_counts_still_reject_reference_reassignment():
    source = "artigo 27.º, n.º 2, alínea c) e 42.º."
    target = "المادة 27.º، رقم 2، الفقرة c). مرجع 42.º."
    assert Counter(blocks._NUMBER.findall(source)) == Counter(blocks._NUMBER.findall(target))
    with pytest.raises(BlockCoverageError, match="^block_citation_association_defect$"):
        check(source, target, TargetLang.AR)


def test_arabic_subdivision_keeps_tail_caps_and_literal_guard():
    assert blocks._citation_heads("المادة 27.º، رقم " + " " * 512 + "2 و42.º.") == Counter({"27": 1})
    heads = blocks._citation_heads("المادة 27.º" + "، رقم 2" * 100 + " و42.º.")
    assert heads == Counter({"27": 1})
    with pytest.raises(BlockCoverageError, match="^block_language_or_token_defect$"):
        check("artigo 27.º.", "وفقا للمادة 27.º. untranslated", TargetLang.AR)


@pytest.mark.parametrize("delimiter", [",", "،", ";", "؛"])
def test_arabic_closing_punctuation_keeps_each_repeated_article_pair(delimiter):
    source = "Artigos 24º e 35º do Código. Nos termos dos artigos 24º e 35º, suspende-se o processo."
    target = ("المادتين 24º و35º من القانون. "
              f"بموجب المادتين 24º و35º{delimiter} يُقرر تعليق الإجراءات.")
    assert blocks._citation_heads(source) == blocks._citation_heads(target) == Counter({"24": 2, "35": 2})
    check(source, target, TargetLang.AR)


@pytest.mark.parametrize("target", [
    "المواد 24، 35 و46.", "المواد 24،35، و46؛", "المواد 24 و35، و46، وفق القانون.",
])
def test_arabic_comma_joins_explicitly_coordinated_article_numbers(target):
    assert blocks._citation_heads(target) == Counter({"24": 1, "35": 1, "46": 1})
    check("Artigos 24, 35 e 46.", target, TargetLang.AR)


@pytest.mark.parametrize("text", [
    "المادة 24؛ و35º.", "المادة 24، مرجع 35º.",
    "المادة 24، 10 أيام.", "المادة 24، 10 مايو 2030.",
    "المادة 24، 10/05/2030.", "المادة 24، 10.05.2030.",
    "المادة 24، 10-05-2030.", "المادة 24، 35A.",
    "المادة 24، 35/ABC.", "المادة 24، 35.50 قيمة.",
    "المادة 24، الفقرة 1 و35º.",
    *(f"المادة 24،{boundary}و35º." for boundary in ('\n', '\r\n', '\v', '\f', '\u2028', '\u2029')),
])
def test_arabic_punctuation_cannot_cross_clauses_prose_values_or_lines(text):
    assert blocks._citation_heads(text) == Counter({"24": 1})


def test_arabic_semicolon_closes_the_pair_without_borrowing_the_next_number():
    assert blocks._citation_heads("المادتين 24 و35؛ و46º.") == Counter({"24": 1, "35": 1})


@pytest.mark.parametrize("source,target", [
    ("Artigos 24º e 35º. Referência 46.", "المادتين 24º و46º، والمرجع 35."),
    ("Artigos 24º e 35º.", "المادة 24º؛ والمرجع 35º."),
    ("Artigo 24º. Referência 35º.", "المادتين 24º و35º، وفق القانون."),
    ("Artigos 24º e 24º.", "المادة 24º، والمرجع 24º."),
])
def test_arabic_punctuation_keeps_strict_citation_counts_with_same_numbers(source, target):
    assert Counter(blocks._NUMBER.findall(source)) == Counter(blocks._NUMBER.findall(target))
    assert blocks._citation_heads(source) != blocks._citation_heads(target)
    # A reordered literal may be rejected before the citation check; neither
    # that stronger guard nor the citation counter may be bypassed.
    with pytest.raises(BlockCoverageError):
        check(source, target, TargetLang.AR)


def test_arabic_punctuation_keeps_character_and_step_limits():
    assert blocks._citation_heads("المادة 24، " + " " * 512 + "35.") == Counter({"24": 1})
    heads = blocks._citation_heads("المادة 24" + "، 1º" * 100)
    assert heads["24"] == 1
    assert 0 < heads["1"] <= blocks._MAX_CITATION_TAIL_STEPS < 100


def test_continuation_is_bounded_without_partial_token_admission():
    assert blocks._citation_heads("Article 24 and " + " " * 512 + "35.") == Counter({"24": 1})
    assert blocks._citation_heads("Article 24 and " + " " * 495 + "35A.") == Counter({"24": 1})
    long_list = "Article 24" + " e 1º" * 100
    heads = blocks._citation_heads(long_list)
    assert heads["24"] == 1
    assert 0 < heads["1"] <= blocks._MAX_CITATION_TAIL_STEPS < 100


def test_citation_policy_changes_real_translation_identity_only_through_evaluation(monkeypatch, tmp_path):
    workflow = SimpleNamespace(_translation_model="gpt-5.6-terra", _prompt_glossaries_by_lang={},
                               _enabled_glossary_tiers_by_lang={}, _prompt_addendum_by_lang={})
    config = SimpleNamespace(target_lang=TargetLang.FR, pdf_path=tmp_path / "fictional.pdf")
    monkeypatch.setattr(blocks, "source_page_identity", lambda _path, page: {"page": page, "source": "fictional"})
    current = blocks.NewTranslationBlocks(workflow, config, [1], source_hash="fictional", context_hash="fictional")
    assert blocks.CITATION_POLICY_VERSION == "article_heads_v5_arabic_contracted_subdivisions"
    monkeypatch.setattr(blocks, "CITATION_POLICY_VERSION", "article_heads_v4_arabic_punctuation")
    previous = blocks.NewTranslationBlocks(workflow, config, [1], source_hash="fictional", context_hash="fictional")
    assert current.identity["fingerprint"] != previous.identity["fingerprint"]
    assert current.instructions == previous.instructions
    assert current.model == previous.model
    assert current.page_identities == previous.page_identities
