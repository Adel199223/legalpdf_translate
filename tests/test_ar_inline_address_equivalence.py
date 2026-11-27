"""Sanitized inline-address grouping and adversarial source-ownership cases."""
import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens, pretokenize_arabic_source
from legalpdf_translate.ar_literal_fidelity import visible_text
from legalpdf_translate.ar_source_fields import canonicalize_source_address_literals
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow_components.evaluation import evaluate_output


def token(value):
    return "\u2066[[" + value + "]]\u2069"


FIELD = "Rua de Cedro, no nº 42"
SOURCE = "Apuraram que na Rua de Cedro, no nº [[42]] é que residiam."


def evaluate(body, *, source=SOURCE, required=None, primary=None):
    return evaluate_output("```\nنص " + body + "\n```", TargetLang.AR,
        expected_ar_tokens=required if required is not None else ["42"],
        ar_source_text=source, primary_normalized_text=primary)


@pytest.mark.parametrize("body", [token(FIELD), token("Rua de Cedro, no nº") + " " + token("42"),
                                  token("Rua de Cedro") + ", no nº " + token("42")])
def test_inline_source_address_wrapper_shapes_are_exactly_equivalent(body):
    result = evaluate(body)
    assert result.ok
    assert visible_text(result.normalized_text) == "نص " + FIELD
    assert extract_locked_tokens(result.normalized_text) == [FIELD]
    correction = evaluate(body, primary="نص " + token(FIELD))
    assert correction.ok


def test_inline_source_proof_does_not_change_saved_or_fresh_pretokenization():
    plain = SOURCE.replace("[[42]]", "42")
    assert pretokenize_arabic_source(plain) == SOURCE
    assert pretokenize_arabic_source(SOURCE) == SOURCE


@pytest.mark.parametrize("body", [
    token("Rua de Cedro, no nº 43"), token("Rua de Cedro, no nº"), token("42"),
    token("Rua de Cedra, no nº 42"), token("Rua de Cedro, no nº 42A"),
    token("Rua de Cedro, no nº 142"), token("Rua de Cedro, no nº 42-1"),
    token("Rua de Cedro, no nº 42,5"), token("Rua de Cedro, no nº ٤٢"),
    token("Rua de Cedro, no nº") + " " + token("42") + " " + token("42"),
    token(FIELD) + " " + token(FIELD), token(FIELD.replace(" ", "  ")),
    token(FIELD.replace("Cedro", "Cédro")), token(FIELD + "\u0301"),
    token("42") + " " + token("Rua de Cedro, no nº"),
    token(FIELD + ", Appendix"), token("Prefix " + FIELD),
    token(FIELD) + "/" + token("Annex"), token("Prefix") + "-" + token(FIELD),
])
def test_inline_address_loss_mutation_duplication_reordering_or_crossing_is_rejected(body):
    assert not evaluate(body, primary="نص " + token(FIELD)).ok


def test_two_inline_addresses_preserve_counts_order_and_unrelated_literals():
    other = "Rua Nova do Vale, nº 8, em Vila Clara"
    source = SOURCE + "\nAntes da Rua Nova do Vale, nº [[8]], em Vila Clara, para informar."
    body = token(FIELD) + " " + token(other) + " " + token("Unrelated Example")
    result = evaluate(body, source=source, required=["42", "8"])
    assert result.ok
    split = token("Rua de Cedro, no nº") + " " + token("42") + " " + token(other) + " " + token("Unrelated Example")
    assert evaluate(split, source=source, required=["42", "8"], primary="نص " + body).ok
    assert not evaluate(token(other) + " " + token(FIELD), source=source, required=["42", "8"]).ok
    assert not evaluate(token(FIELD), source=source, required=["42", "8"]).ok
    assert not evaluate(token(FIELD) + " " + token(other), source=source, required=["42", "8"], primary="نص " + body).ok


def test_repeated_inline_address_requires_exact_source_multiplicity():
    source = SOURCE + "\n" + SOURCE
    assert evaluate(token(FIELD) + " " + token(FIELD), source=source, required=["42", "42"]).ok
    assert not evaluate(token(FIELD), source=source, required=["42", "42"]).ok
    assert not evaluate(" ".join([token(FIELD)] * 3), source=source, required=["42", "42"]).ok


def test_inline_constituent_must_preserve_separate_source_occurrence():
    source = "Referência [[42]].\n" + SOURCE
    body = token("42") + " " + token(FIELD)
    assert evaluate(body, source=source, required=["42", "42"]).ok
    assert not evaluate(token(FIELD), source=source, required=["42", "42"]).ok
    assert not evaluate(token("42") + " " + body, source=source, required=["42", "42"]).ok


def test_nested_street_word_does_not_duplicate_inline_field_ownership():
    field = "Rua da Avenida Cedro, nº 42"
    source = "Na Rua da Avenida Cedro, nº [[42]], seguiu."
    assert evaluate(token(field), source=source).ok
    assert not evaluate(token("Avenida Cedro, nº 42"), source=source).ok


@pytest.mark.parametrize("source", [None, "Número [[42]] sem endereço.",
    "Rua de Cedro, no nº [[43]] é que residiam.",
    "Texto Rua de Cedro, no nº [[42]]-1 nesta rua.",
    "Texto Rua de Cedro, no nº [[42]],5 nesta rua.",
    "Texto Rua de Cedro\n\nno nº [[42]] nesta rua.",
    "Texto Rua de Cedro\fno nº [[42]] nesta rua.",
    "Texto Rua deve pagar, nº [[42]] nesta rua.",
])
def test_inline_equivalence_requires_bounded_exact_source_proof(source):
    assert not evaluate(token(FIELD), source=source).ok


def test_inline_candidates_do_not_shorten_existing_whole_field_ownership():
    whole = FIELD + ", 1234-567 Vila Clara"
    source = "Morada: " + token(whole)
    result = evaluate(token(whole), source=source, required=[whole])
    assert result.ok
    assert extract_locked_tokens(result.normalized_text) == [whole]


@pytest.mark.parametrize("body", ["[[[" + FIELD + "]]]", "\u2066[[" + FIELD + "]]",
                                  "[[" + FIELD + "]]\u2069"])
def test_inline_source_equivalence_does_not_repair_malformed_wrappers(body):
    assert canonicalize_source_address_literals(body, SOURCE, ["42"])[3]
