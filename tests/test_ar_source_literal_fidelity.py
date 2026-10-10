import pytest

from legalpdf_translate.arabic_pre_tokenize import pretokenize_arabic_source, extract_locked_tokens, is_portuguese_month_date_token
from legalpdf_translate.ar_literal_fidelity import regroup_source_numeric_tokens, visible_text
from legalpdf_translate.workflow_components.evaluation import evaluate_output
from legalpdf_translate.types import TargetLang


def token(value):
    return "\u2066[[" + value + "]]\u2069"


@pytest.mark.parametrize("source", ["[Aviso de 15 de Junho de 2026].", "[15 de Junho de 2026", "15 de Junho de 2026]"])
def test_outer_source_brackets_remain_visible_outside_date_token(source):
    wrapped = pretokenize_arabic_source(source)
    assert extract_locked_tokens(wrapped) == ["15 de Junho de 2026"]
    assert all(is_portuguese_month_date_token(t) for t in extract_locked_tokens(wrapped))
    assert visible_text(wrapped) == source
    assert pretokenize_arabic_source(wrapped) == wrapped


@pytest.mark.parametrize("source,literal", [("102/500=0,204€", "102/500=0,204€"), ("1 / 3", "1 / 3")])
def test_source_bound_grouping_preserves_visible_text(source, literal):
    protected = pretokenize_arabic_source(source)
    result = regroup_source_numeric_tokens(token(literal), protected)
    assert visible_text(result) == literal
    assert len(extract_locked_tokens(result)) >= 2
    evaluation = evaluate_output("```\nنص " + token(literal) + "\n```", TargetLang.AR, expected_ar_tokens=extract_locked_tokens(protected), ar_source_text=protected)
    assert evaluation.ok


@pytest.mark.parametrize("source,literal", [(None,"1 / 3"),("1 / 3 et 1 / 3","1 / 3"),("1 / 3","1 / 4"),("123 / 3","1 / 3"),("1 mot 3","1 mot 3"),("AB1 / 3","AB1 / 3")])
def test_unsupported_numeric_grouping_is_unchanged(source,literal):
    protected = pretokenize_arabic_source(source) if source else None
    original = token(literal)
    assert regroup_source_numeric_tokens(original, protected) == original


@pytest.mark.parametrize("replacement", ["", "سليم", "سبعة عشر"])
def test_correction_cannot_delete_transliterate_or_spell_additional_primary_literal(replacement):
    primary = "نص " + token("Required") + " " + token("Selim Example") + " " + token("17")
    corrected = "نص " + token("Required") + " " + (token("17") if replacement != "سبعة عشر" else replacement)
    if replacement == "سليم": corrected += " سليم"
    result = evaluate_output("```\n"+corrected+"\n```", TargetLang.AR, expected_ar_tokens=["Required"], primary_normalized_text=primary)
    assert not result.ok and result.ar_violation_kind == "correction_literal_fidelity_loss"


def test_required_occurrence_cannot_mask_lost_identical_extra_occurrence():
    primary = "نص " + token("Extra") + " " + token("Extra")
    result = evaluate_output("```\nنص "+token("Extra")+"\n```",TargetLang.AR,expected_ar_tokens=["Extra"],primary_normalized_text=primary)
    assert not result.ok and result.ar_violation_kind == "correction_literal_fidelity_loss"


def test_preserved_additional_grouping_passes_but_missing_required_stays_strict():
    primary = "نص " + token("1 / 3") + " " + token("Selim Example")
    corrected = "نص " + token("1") + " / " + token("3") + " " + token("Selim Example")
    result = evaluate_output("```\n"+corrected+"\n```",TargetLang.AR,expected_ar_tokens=["1","3"],ar_source_text=pretokenize_arabic_source("1 / 3"),primary_normalized_text=primary)
    assert result.ok
    missing = evaluate_output("```\nنص "+token("Extra")+"\n```",TargetLang.AR,expected_ar_tokens=["Required"])
    assert not missing.ok and missing.ar_violation_kind == "expected_token_mismatch"


def test_arabic_adjacent_additional_token_cannot_disappear():
    primary = "ب" + token("Nadia")
    result = evaluate_output("```\nنص\n```", TargetLang.AR, primary_normalized_text=primary)
    assert not result.ok and result.ar_violation_kind == "correction_literal_fidelity_loss"


@pytest.mark.parametrize("malformed", ["[[1 / 3]]", "\u2066[[1 / 3]]", "[[1 / 3]]\u2069", "[" + token("1 / 3")])
def test_regroup_does_not_repair_unqualified_wrappers(malformed):
    assert regroup_source_numeric_tokens(malformed, pretokenize_arabic_source("1 / 3")) == malformed


@pytest.mark.parametrize("source,prior,required,ok", [
    ("Morada: Rua Example no 6, 7960-011 Town", "Rua Example no 9, 7960-011 Town", "Rua Example no 6, 7960-011 Town", True),
    (None, "Rua Example no 9, 7960-011 Town", "Rua Example no 6, 7960-011 Town", False),
    ("Morada: Rua Example no 6, 7960-011 Town", "Rua Other no 9, 7960-011 Town", "Rua Example no 6, 7960-011 Town", False),
    ("Morada: Rua Example no 6, 7960-011 Town", "Rua Example no 9, 7961-011 Town", "Rua Example no 6, 7960-011 Town", False),
])
def test_required_address_numeric_repair_is_source_field_bound(source, prior, required, ok):
    from legalpdf_translate.ar_literal_fidelity import correction_preserves_additional_literals
    assert correction_preserves_additional_literals(token(prior), token(required), [required], source) is ok


@pytest.mark.parametrize("source,duplicate", [
    ("Morada: Rua Example no 6, 7960-011 Town\nAddress: Rua Example no 6, 7960-011 Town", False),
    ("Morada: Rua Example no 6, 7960-011 Town\nOther source: Rua Example no 9, 7960-011 Town", False),
    ("Morada: Rua Example no 6, 7960-011 Town", True),
])
def test_source_present_or_duplicated_address_is_not_exempt(source, duplicate):
    from legalpdf_translate.ar_literal_fidelity import correction_preserves_additional_literals
    wrong = token("Rua Example no 9, 7960-011 Town")
    primary = wrong + (" " + wrong if duplicate else "")
    required = "Rua Example no 6, 7960-011 Town"
    assert not correction_preserves_additional_literals(primary, token(required), [required], source)


def test_regroup_count_counts_each_changed_source_numeric_group():
    from legalpdf_translate.output_normalize import regroup_source_bound_ar_numeric_tokens
    source = pretokenize_arabic_source("102/500=0,204€; 1 / 3")
    original = token("102/500=0,204€") + "; " + token("1 / 3")
    result, count = regroup_source_bound_ar_numeric_tokens(original, source_text=source, expected_tokens=extract_locked_tokens(source))
    assert count == 2
    assert visible_text(result) == visible_text(original)
    unchanged, count = regroup_source_bound_ar_numeric_tokens(result, source_text=source, expected_tokens=extract_locked_tokens(source))
    assert unchanged == result and count == 0
