"""Fictional reproductions; no retained court text or inferred model responses."""
import pytest

from legalpdf_translate.arabic_pre_tokenize import pretokenize_arabic_source, extract_locked_tokens
from legalpdf_translate.ar_literal_fidelity import correction_preserves_additional_literals, visible_text
from legalpdf_translate.ar_source_fields import canonicalize_source_address_literals
from legalpdf_translate.workflow_components.evaluation import evaluate_output
from legalpdf_translate.types import TargetLang


def token(value):
    return "\u2066[[" + value + "]]\u2069"


OLD_SOURCE = "Rua das Flores\n[[1234-567]] Vila Nova"
FIELD = "1234-567 Vila Nova"


def evaluate(body, source=OLD_SOURCE, required=None, primary=None):
    return evaluate_output("```\nنص " + body + "\n```", TargetLang.AR,
        expected_ar_tokens=required if required is not None else ["1234-567"],
        ar_source_text=source, primary_normalized_text=primary)


def test_source_postal_locality_is_one_exact_token_without_a_street_anchor():
    source = "عنوان\n1234-567 Vila Nova\nTexto traduzível."
    result = pretokenize_arabic_source(source)
    assert extract_locked_tokens(result) == [FIELD]
    assert visible_text(result) == source
    assert pretokenize_arabic_source(result) == result


@pytest.mark.parametrize("body", [token(FIELD), token("1234-567") + " " + token("Vila Nova"), FIELD])
def test_saved_source_wrapper_shapes_have_exact_source_equivalence(body):
    result = evaluate(body)
    assert result.ok
    assert extract_locked_tokens(result.normalized_text) == [FIELD]
    assert visible_text(result.normalized_text) == "نص " + visible_text(body)


def test_wrapper_only_correction_is_not_additional_literal_loss():
    primary = "نص " + token(FIELD) + " " + token("Unrelated Example")
    corrected = token("1234-567") + " " + token("Vila Nova") + " " + token("Unrelated Example")
    assert evaluate(corrected, primary=primary).ok
    assert not evaluate(token("1234-567") + " " + token("Vila Nova"), primary=primary).ok


@pytest.mark.parametrize("body", [
    token("1234-568 Vila Nova"), token("1234-567 Vila Velha"), token("1234-567"),
    token(FIELD) + " " + token(FIELD), token(FIELD + " Annex"), token("X" + FIELD),
    token(FIELD + "\u0301"), token(FIELD.replace(" ", "  ")),
    token(FIELD.replace("Vila", "Vilà")),
    token(FIELD) + "-" + token("Annex"), token("Prefix") + "/" + token(FIELD),
])
def test_changed_missing_duplicate_prefix_or_widened_fields_stay_rejected(body):
    assert not evaluate(body).ok


def test_duplicated_source_fields_require_both_exact_occurrences():
    source = OLD_SOURCE + "\n\n" + OLD_SOURCE
    assert evaluate(token(FIELD) + "\n" + token(FIELD), source, ["1234-567"] * 2).ok
    assert not evaluate(token(FIELD), source, ["1234-567"] * 2).ok
    assert not evaluate(token(FIELD) + "\n" + token(FIELD) + "\n" + token(FIELD), source, ["1234-567"] * 2).ok


def test_distinct_postal_fields_cannot_be_reassociated():
    source = "[[1234-567]] Vila Nova\n[[2345-678]] Vila Velha"
    assert not evaluate(token("2345-678 Vila Velha") + "\n" + token(FIELD), source,
                        ["1234-567", "2345-678"]).ok


def test_malformed_or_crossing_wrappers_do_not_prove_equivalence():
    for body in ("[[[" + FIELD + "]]]", token(FIELD + "; Appendix"),
                 "\u2066[[" + FIELD + "]]", "[[" + FIELD + "]]\u2069"):
        result = canonicalize_source_address_literals(body, OLD_SOURCE, ["1234-567"])
        assert result[3]
        assert result[0] == body


def test_no_source_proof_retains_strict_missing_token_check():
    assert not evaluate(token(FIELD), source=None).ok
    assert not evaluate(token(FIELD), source="[[1234-567]] This sentence explains the case.").ok


def test_complete_labeled_address_split_group_equivalence():
    field = "Rua das Flores 12, 1234-567 Vila Nova"
    source = "Morada: " + token(field)
    split = token("Rua das Flores") + " " + token("12") + ", " + token(FIELD)
    result = evaluate(split, source, [field])
    assert result.ok
    assert extract_locked_tokens(result.normalized_text) == [field]
    assert correction_preserves_additional_literals(token(field), split, [field], source)


@pytest.mark.parametrize("boundary", ["\n\n", "\f", "\u2029", "\nTexto explicativo\n"])
def test_street_proof_does_not_cross_hard_blank_or_body_boundaries(boundary):
    source = "Rua das Flores" + boundary + "1234-567 Vila Nova"
    assert "Rua das Flores" not in extract_locked_tokens(pretokenize_arabic_source(source))


def test_unknown_identical_extra_occurrences_cannot_be_dropped():
    primary = token(FIELD) + " " + token("Extra") + " " + token("Extra")
    corrected = token("1234-567") + " " + token("Vila Nova") + " " + token("Extra")
    assert not evaluate(corrected, primary=primary).ok


def test_canonicalization_is_idempotent_with_saved_expectations():
    first, required, changed, error = canonicalize_source_address_literals(
        token("1234-567") + " " + token("Vila Nova"), OLD_SOURCE, ["1234-567"])
    assert not error and changed == 1 and required == [FIELD]
    second, _, count, error = canonicalize_source_address_literals(first, OLD_SOURCE, ["1234-567"])
    assert second == first and count == 0 and not error


@pytest.mark.parametrize("short,long", [
    (FIELD, "Rua das Flores 12, " + FIELD),
    ("Rua das Flores", "Rua das Flores 12"),
])
def test_nested_field_text_has_disjoint_occurrence_ownership(short, long):
    source = "Morada: " + token(long) + "\nMorada: " + token(short)
    if short == FIELD:
        source = "Morada: " + token(long) + "\n" + token(short)
    expected = [long, short]
    complete = token(long) + "\n" + token(short)
    assert evaluate(complete, source, expected).ok
    assert evaluate(long + "\n" + short, source, expected).ok
    assert not evaluate(long, source, expected).ok
    assert not evaluate(token(long), source, expected).ok
    assert not evaluate(complete + "\n" + token(short), source, expected).ok
    assert not evaluate(token(short) + "\n" + token(long), source, expected).ok
    assert correction_preserves_additional_literals(complete, long + "\n" + short, expected, source)
