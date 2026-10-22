"""Fictional source-owned wrapper decomposition; no literal/value repair."""
import pytest
from legalpdf_translate.ar_literal_fidelity import (
    decompose_source_literal_components_with_stats as decompose, visible_text,
    LITERAL_WRAPPER_POLICY,
)
from legalpdf_translate.output_normalize import LRI, PDI
from legalpdf_translate.workflow_components.evaluation import evaluate_output
from legalpdf_translate.types import TargetLang

SOURCE = "Rua da Aurora [[8]]\nVale Claro\n[[4321]] Cidade Nova"
LITERAL = "Rua da Aurora 8, Vale Claro, 4321 Cidade Nova"
EXPECTED = ["8", "4321"]
def token(value):
    return LRI + "[[" + value + "]]" + PDI
PRIMARY = "العنوان: " + token(LITERAL) + "\n" + token("R")
def evaluate(text=PRIMARY, **kwargs):
    return evaluate_output("```\n" + text + "\n```", TargetLang.AR,
        ar_source_text=SOURCE, expected_ar_tokens=EXPECTED, **kwargs)

def test_initial_full_validation_is_lossless_and_opt_in():
    baseline = evaluate()
    assert not baseline.ok and baseline.ar_violation_kind == "expected_token_mismatch"
    selected = evaluate(literal_wrapper_policy=LITERAL_WRAPPER_POLICY)
    assert selected.ok
    assert visible_text(selected.normalized_text) == visible_text(baseline.normalized_text)
    assert SOURCE == "Rua da Aurora [[8]]\nVale Claro\n[[4321]] Cidade Nova"
    assert EXPECTED == ["8", "4321"]
    assert evaluate(literal_wrapper_policy=None) == baseline

@pytest.mark.parametrize("join", [" ", ", ", "، "])
@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"])
def test_complete_rows_and_exact_component_coordinates(join, newline):
    source = SOURCE.replace("\n", newline)
    text = token(join.join(visible_text(source).splitlines()))
    result, count = decompose(text, source, EXPECTED)
    assert count == 1 and visible_text(result) == visible_text(text)
    assert token("8") in result and token("4321") in result
    assert token(join + "Vale Claro" + join) in result
    assert result.replace(LRI, "").replace(PDI, "").count("[[") == 5


def test_initial_only_even_if_policy_is_accidentally_passed_on_retry():
    original = evaluate().normalized_text
    retry = evaluate(primary_normalized_text=original, literal_wrapper_policy=LITERAL_WRAPPER_POLICY)
    assert not retry.ok and retry.ar_violation_kind == "expected_token_mismatch"
    selected = evaluate(literal_wrapper_policy=LITERAL_WRAPPER_POLICY).normalized_text
    corrected = selected.replace(token("R"), "")
    for policy in (None, LITERAL_WRAPPER_POLICY):
        rejected = evaluate(corrected, primary_normalized_text=selected, literal_wrapper_policy=policy)
        assert not rejected.ok and rejected.ar_violation_kind == "correction_literal_fidelity_loss"

@pytest.mark.parametrize("source,literal,expected", [
    ("Nome: [[8]] Silva\nCódigo: [[4321]]", "8 Silva 4321", EXPECTED),
    (SOURCE, LITERAL.replace("Aurora", "Auroras"), EXPECTED),
    (SOURCE, LITERAL.replace(" 8,", " 9,"), EXPECTED),
    (SOURCE, LITERAL.replace("4321", "4322"), EXPECTED),
    (SOURCE, LITERAL.replace("Vale Claro, ", ""), EXPECTED),
    (SOURCE, LITERAL + " Outra Cidade", EXPECTED),
    (SOURCE, LITERAL.replace(", Vale", "; Vale"), EXPECTED),
    (SOURCE, LITERAL.replace("Aurora", "aurora"), EXPECTED),
    (SOURCE, LITERAL, ["8", "4321", "8"]),
    (SOURCE + "\n[[8]]", LITERAL, EXPECTED),
    (SOURCE + "\n8", LITERAL, EXPECTED),
    (SOURCE + "\n" + SOURCE, LITERAL, EXPECTED),
    (SOURCE.replace("[[8]]", "8"), LITERAL, EXPECTED),
    (SOURCE.replace("[[4321]]", "[[432]]1"), LITERAL, ["8", "432"]),
    (SOURCE.replace("\n", "\u2028"), LITERAL, EXPECTED),
    (SOURCE.replace("Vale", "Va\u2066le\u2069"), LITERAL, EXPECTED),
    (SOURCE.replace("Vale", "Va\u200fle"), LITERAL, EXPECTED),
])
def test_unproven_or_ambiguous_allocations_are_noops(source, literal, expected):
    original = token(literal)
    assert decompose(original, source, expected) == (original, 0)

@pytest.mark.parametrize("text", [
    token(LITERAL) + token("8"), token(LITERAL) + " 8", token(LITERAL) * 2,
    "[[" + LITERAL + "]]", LRI + "[[" + LITERAL + "]]",
    "[[[" + LITERAL + "]]]", token(LITERAL) + LRI,
    PDI + token(LITERAL), token(LITERAL.replace("Vale", "Va\u202ele")),
    token(LITERAL.replace("Vale", "Va\x00le")),
])
def test_target_reuse_malformed_wrappers_and_controls_are_noops(text):
    assert decompose(text, SOURCE, EXPECTED) == (text, 0)


def test_balanced_unrelated_source_isolate_is_allowed_but_orphan_is_not():
    source = LRI + "Original" + PDI + "\n" + SOURCE
    assert decompose(token(LITERAL), source, EXPECTED)[1] == 1
    for bad in (LRI + "Original\n" + SOURCE, PDI + SOURCE):
        assert decompose(token(LITERAL), bad, EXPECTED) == (token(LITERAL), 0)


def test_multiple_distinct_blocks_keep_source_order():
    source2 = SOURCE.replace("Aurora", "Nascente").replace("[[8]]", "[[9]]").replace("[[4321]]", "[[5432]]")
    literal2 = LITERAL.replace("Aurora", "Nascente").replace(" 8,", " 9,").replace("4321", "5432")
    source = SOURCE + "\n\n" + source2
    expected = EXPECTED + ["9", "5432"]
    ordered = token(LITERAL) + "\n" + token(literal2)
    result, count = decompose(ordered, source, expected)
    assert count == 2 and visible_text(result) == visible_text(ordered)
    reversed_text = token(literal2) + "\n" + token(LITERAL)
    assert decompose(reversed_text, source, expected) == (reversed_text, 0)

@pytest.mark.parametrize("bound,value", [
    ("_MAX_COMPONENT_CHARS", 10), ("_MAX_COMPONENT_WORK", 10),
    ("_MAX_COMPONENT_TOKENS", 1), ("_MAX_COMPONENT_BLOCKS", 0),
])
def test_resource_proof_overflow_is_noop(monkeypatch, bound, value):
    import legalpdf_translate.ar_literal_fidelity as module
    monkeypatch.setattr(module, bound, value)
    assert decompose(PRIMARY, SOURCE, EXPECTED) == (PRIMARY, 0)

@pytest.mark.parametrize("expected", [None, [], [""], [5], ["x" * 257], ["x"] * 513])
def test_invalid_expected_inventory_is_noop(expected):
    assert decompose(PRIMARY, SOURCE, expected) == (PRIMARY, 0)


def test_unknown_policy_is_explicit_error():
    with pytest.raises(ValueError, match="Unknown literal wrapper policy"):
        evaluate(literal_wrapper_policy="unrecognized")



def test_idempotence_preserves_protected_residual_spaces_and_punctuation():
    split, count = decompose(PRIMARY, SOURCE, EXPECTED)
    assert count == 1
    assert token("Rua da Aurora ") in split
    assert token(", Vale Claro, ") in split
    assert token(" Cidade Nova") in split
    assert decompose(split, SOURCE, EXPECTED) == (split, 0)
    assert evaluate(split, literal_wrapper_policy=LITERAL_WRAPPER_POLICY).ok

@pytest.mark.parametrize("source,target", [
    (SOURCE + "\nID-8/END", PRIMARY),
    (SOURCE, PRIMARY + "\n" + token("ID-8/END")),
    (SOURCE.replace("[[8]]", "ID-[[8]]/END"), PRIMARY.replace(" 8,", " ID-8/END,")),
    (SOURCE.replace("[[8]]", "[[8]]0"), PRIMARY.replace(" 8,", " 80,")),
    (SOURCE, PRIMARY.replace("4321", "X4321")),
])
def test_identifiers_and_lexical_substrings_cannot_supply_components(source, target):
    # A separate identifier does not own a house-number occurrence; any literal
    # selected must retain an exact complete source block with whole components.
    result, count = decompose(target, source, EXPECTED)
    if source.endswith("ID-8/END") or target.endswith(token("ID-8/END")):
        assert count == 1 and visible_text(result) == visible_text(target)
        if target.endswith(token("ID-8/END")):
            assert result.endswith(token("ID-8/END"))
    else:
        assert (result, count) == (target, 0)


def test_duplicate_component_values_inside_address_are_not_reallocated():
    source = SOURCE.replace("Aurora", "Aurora [[8]]")
    target = PRIMARY.replace("Aurora", "Aurora 8")
    assert decompose(target, source, ["8", "8", "4321"]) == (target, 0)


def test_borrowed_source_identifier_constituent_is_not_a_whole_component():
    source = SOURCE.replace("[[8]]", "ID-[[8]]/END")
    assert decompose(PRIMARY, source, EXPECTED) == (PRIMARY, 0)


def test_partial_source_token_crossing_row_is_not_allocated():
    source = SOURCE.replace("[[8]]\nVale", "[[8\nVale]]")
    assert decompose(PRIMARY, source, EXPECTED) == (PRIMARY, 0)
