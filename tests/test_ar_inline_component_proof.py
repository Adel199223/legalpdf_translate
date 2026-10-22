"""Sanitized source-bound Arabic number-label connector regressions."""
import pytest

from legalpdf_translate.ar_literal_fidelity import visible_text
from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.ar_source_fields import _inline_address_fields
from legalpdf_translate.workflow_components.evaluation import evaluate_output
from legalpdf_translate.types import TargetLang


def token(value):
    return "\u2066[[" + value + "]]\u2069"


SOURCE = "Apuraram que na Rua de Cedro, no nº [[42]] é que residiam."
STREET = "Rua de Cedro"
FIELD = STREET + ", no nº 42"


def evaluate(body, source=SOURCE, expected=None, primary=None, **options):
    return evaluate_output("```\nنص " + body + "\n```", TargetLang.AR,
        expected_ar_tokens=["42"] if expected is None else expected,
        ar_source_text=source, primary_normalized_text=primary, **options)


@pytest.mark.parametrize("source_field_policy", [None, "baseline_label_value_v1"])
@pytest.mark.parametrize("literal_wrapper_policy", [None, "lossless_source_components_v2"])
@pytest.mark.parametrize("connector", ["، رقم ", " رقم ", ", رقم ", "، بالرقم ", " بالرقم ", ", بالرقم ", "\tبالرقم\t", " \t،\tبالرقم \t"])
def test_exact_separate_components_allow_only_translated_number_label(connector, source_field_policy, literal_wrapper_policy):
    body = token(STREET) + connector + token("42")
    options = {"source_field_policy": source_field_policy, "literal_wrapper_policy": literal_wrapper_policy}
    result = evaluate(body, **options)
    assert result.ok
    assert visible_text(result.normalized_text) == "نص " + STREET + connector + "42"
    assert result.normalized_text == "نص " + body
    correction = evaluate(body, primary=result.normalized_text, **options)
    assert correction.ok and correction.normalized_text == result.normalized_text


@pytest.mark.parametrize("source_field_policy", [None, "baseline_label_value_v1"])
@pytest.mark.parametrize("label", ["رقم", "بالرقم"])
@pytest.mark.parametrize("body", [
    token("Rua de Cedra") + "، رقم " + token("42"),
    token(STREET) + "، رقم " + token("43"),
    token(STREET) + "، رقم " + token("142"),
    token(STREET) + "، رقم " + token("42A"),
    token(STREET) + "، رقم " + token("42") + "-1",
    token(STREET) + "، رقم " + token("42") + ",5",
    token(STREET) + "، رقم " + token("42") + " " + token("42"),
    token(STREET) + "، رقم " + token("42") + " " + token(STREET),
    token("42") + "، رقم " + token(STREET),
    token(STREET), token("42"),
    token(STREET) + "، ليس رقم " + token("42"),
    token(STREET) + "، رقم\n" + token("42"),
    token(STREET) + "، رقم " + token("Other") + " " + token("42"),
    token(STREET + "، رقم 42"),
    token("Prefix " + STREET) + "، رقم " + token("42"),
    token(STREET) + "، رقم " + token("42 Suffix"),
])
def test_component_proof_rejects_loss_mutation_duplication_or_crossing(body, label, source_field_policy):
    body = body.replace("رقم", label)
    assert not evaluate(body, source_field_policy=source_field_policy).ok


def test_component_proof_preserves_two_address_association_and_source_order():
    other = "Rua da Fonte"
    source = SOURCE + "\nNa Rua da Fonte, nº [[7]], para informar."
    first = token(STREET) + "، رقم " + token("42")
    second = token(other) + "، رقم " + token("7")
    assert evaluate(first + " و " + second, source, ["42", "7"]).ok
    assert not evaluate(second + " و " + first, source, ["42", "7"]).ok
    assert not evaluate(token(STREET) + "، رقم " + token("7") + " و " + token(other) + "، رقم " + token("42"), source, ["42", "7"]).ok


def test_previously_whole_primary_literal_cannot_lose_its_text_to_translated_connector():
    body = token(STREET) + "، رقم " + token("42")
    assert not evaluate(body, primary="نص " + token(FIELD)).ok


def test_original_unrelated_primary_literals_remain_required():
    body = token(STREET) + "، رقم " + token("42")
    assert not evaluate(body, primary="نص " + body + " " + token("Other Protected")).ok


def test_full_labeled_address_cannot_use_separate_component_exception():
    source = "Morada: Rua de Cedro, no nº [[42]]"
    assert not evaluate(token(STREET) + "، رقم " + token("42"), source, extract_locked_tokens(source)).ok


def test_locality_extension_is_not_inferred_from_translated_connector():
    source = "Na Rua de Cedro, no nº [[42]], em Vila Clara, para informar."
    assert not evaluate(token(STREET) + "، رقم " + token("42") + " " + token("Vila Clara"), source).ok


@pytest.mark.parametrize("copies", [1, 3])
def test_repeated_source_address_requires_exact_component_multiplicity(copies):
    source = SOURCE + "\n" + SOURCE
    body = " و ".join([token(STREET) + "، رقم " + token("42")] * copies)
    assert not evaluate(body, source, ["42", "42"]).ok


def test_repeated_and_mixed_exact_address_representations_are_valid():
    source = SOURCE + "\n" + SOURCE
    separate = token(STREET) + "، رقم " + token("42")
    assert evaluate(separate + " و " + separate, source, ["42", "42"]).ok
    assert evaluate(token(FIELD) + " و " + separate, source, ["42", "42"]).ok


def test_separate_house_token_outside_address_keeps_its_own_multiplicity():
    source = "Referência [[42]].\n" + SOURCE
    separate = token(STREET) + "، رقم " + token("42")
    assert evaluate(token("42") + " " + separate, source, ["42", "42"]).ok
    assert not evaluate(separate, source, ["42", "42"]).ok
    assert not evaluate(token("42") + " " + token("42") + " " + separate, source, ["42", "42"]).ok


@pytest.mark.parametrize("source", [
    "Na Rua de Cedra, no nº [[42]], seguiu.",
    "Na Rua de Cedro, no nº [[43]], seguiu.",
    "Na [[Rua de Cedro, no nº 42]], seguiu.",
])
def test_component_proof_requires_exact_independent_source_parts(source):
    assert not evaluate(token(STREET) + "، رقم " + token("42"), source, extract_locked_tokens(source)).ok



def test_cross_line_source_is_not_claimed_as_inline_component_proof():
    assert not _inline_address_fields("Na Rua de Cedro\nno nº 42, seguiu.", [])


@pytest.mark.parametrize("source_field_policy", [None, "baseline_label_value_v1"])
@pytest.mark.parametrize("connector", [" برقم ", "، ليس بالرقم ", "، بالرقم غير ",
    "، بالرقم\n", "\nبالرقم ", "، بالرقم", "، رقم/بالرقم ", "، ذو الرقم "])
def test_closed_label_alternative_rejects_other_words_negation_and_newlines(source_field_policy, connector):
    body = token(STREET) + connector + token("42")
    assert not evaluate(body, source_field_policy=source_field_policy,
        literal_wrapper_policy="lossless_source_components_v2").ok


@pytest.mark.parametrize("source_field_policy", [None, "baseline_label_value_v1"])
def test_prefixed_label_preserves_association_order_and_exact_multiplicity(source_field_policy):
    options = {"source_field_policy": source_field_policy, "literal_wrapper_policy": "lossless_source_components_v2"}
    first = token(STREET) + "، بالرقم " + token("42")
    other = "Rua da Fonte"
    second = token(other) + "، بالرقم " + token("7")
    source = SOURCE + "\nNa Rua da Fonte, nº [[7]], para informar."
    assert evaluate(first + " و " + second, source, ["42", "7"], **options).ok
    assert not evaluate(second + " و " + first, source, ["42", "7"], **options).ok
    swapped = token(STREET) + "، بالرقم " + token("7") + " و " + token(other) + "، بالرقم " + token("42")
    assert not evaluate(swapped, source, ["42", "7"], **options).ok
    repeated = SOURCE + "\n" + SOURCE
    assert evaluate(first + " و " + first, repeated, ["42", "42"], **options).ok
    assert evaluate(token(FIELD) + " و " + first, repeated, ["42", "42"], **options).ok
    for copies in [1, 3]:
        assert not evaluate(" و ".join([first] * copies), repeated, ["42", "42"], **options).ok
    external = "Referência [[42]].\n" + SOURCE
    assert evaluate(token("42") + " " + first, external, ["42", "42"], **options).ok
    assert not evaluate(first, external, ["42", "42"], **options).ok
    assert not evaluate(token("42") + " " + token("42") + " " + first, external, ["42", "42"], **options).ok


@pytest.mark.parametrize("source_field_policy", [None, "baseline_label_value_v1"])
def test_prefixed_label_never_bypasses_whole_field_primary_or_source_ownership_guards(source_field_policy):
    body = token(STREET) + "، بالرقم " + token("42")
    options = {"source_field_policy": source_field_policy, "literal_wrapper_policy": "lossless_source_components_v2"}
    assert not evaluate(body, primary="نص " + token(FIELD), **options).ok
    assert not evaluate(body, primary="نص " + body + " " + token("Other Protected"), **options).ok
    for source in ["Morada: " + SOURCE.split("na ", 1)[1],
        "Na [[Rua de Cedro, no nº 42]], seguiu.",
        "Na Rua de Cedra, no nº [[42]], seguiu.",
        "Na Rua de Cedro, no nº [[43]], seguiu."]:
        assert not evaluate(body, source, extract_locked_tokens(source), **options).ok
    source = "Na Rua de Cedro, no nº [[42]], em Vila Clara, para informar."
    assert not evaluate(body + " " + token("Vila Clara"), source, **options).ok
