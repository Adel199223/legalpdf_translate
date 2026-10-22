"""Fictional complete-row evidence; v2 never edits a visible source value."""
from dataclasses import asdict, replace
import json
from pathlib import Path

import pytest

from legalpdf_translate.ar_literal_fidelity import (
    decompose_source_literal_components_with_stats as decompose,
    correction_preserves_additional_literals as preserves, visible_text,
)
from legalpdf_translate.ar_source_fields import source_required_prefixed_address_line_blocks as blocks
from legalpdf_translate.output_normalize import LRI, PDI
from legalpdf_translate.prompt_builder import build_ar_token_retry_prompt
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow_components.evaluation import evaluate_output

V1, V2 = "lossless_source_components_v1", "lossless_source_components_v2"
FIRST, POSTAL = "Casa da Aurora - Rua das Flores 18", "4567-123 Vila Serena"
EXPECTED = [FIRST, POSTAL]
SOURCE = "[[" + FIRST + "]]\n[[" + POSTAL + "]]"


def token(value):
    return LRI + "[[" + value + "]]" + PDI


def evaluate(body, source=SOURCE, expected=EXPECTED, primary=None, policy=V2):
    return evaluate_output("```\n" + body + "\n```", TargetLang.AR,
        ar_source_text=source, expected_ar_tokens=expected,
        primary_normalized_text=primary, literal_wrapper_policy=policy)


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"])
@pytest.mark.parametrize("dash", ["-", "–", "—"])
def test_complete_owned_rows_split_without_visible_change_and_restore_exact_newline(newline, dash):
    first = FIRST.replace(" - ", " " + dash + " ")
    source = "[[" + first + "]]" + newline + "[[" + POSTAL + "]]"
    expected = [first, POSTAL]
    primary = "العنوان: " + token(first + " " + POSTAL) + "\n" + token("R")
    initial = evaluate(primary, source, expected)
    assert initial.ok and visible_text(initial.normalized_text) == visible_text(primary)
    assert token(" ") in initial.normalized_text and token("R") in initial.normalized_text
    assert decompose(initial.normalized_text, source, expected, literal_wrapper_policy=V2) == (initial.normalized_text, 0)
    old = evaluate(primary, source, expected, policy=V1)
    corrected = "العنوان: " + token(first) + newline + token(POSTAL) + "\n" + token("R")
    retry = evaluate(corrected, source, expected, old.normalized_text)
    assert preserves(old.normalized_text, corrected, expected, source, literal_wrapper_policy=V2)
    if newline == "\n":
        assert retry.ok
        assert visible_text(retry.normalized_text) == visible_text(corrected)
    else:
        # Existing output normalization emits LF. Do not expand the exact
        # source-line proof into arbitrary CR/LF equivalence on correction.
        assert not retry.ok
    assert not evaluate(corrected, source, expected, old.normalized_text, policy=V1).ok


def test_retry_never_decomposes_even_when_v2_is_supplied():
    primary = token(FIRST + " " + POSTAL)
    baseline = evaluate(primary, policy=V1).normalized_text
    retry = evaluate(primary, primary=baseline)
    assert not retry.ok and retry.ar_violation_kind == "expected_token_mismatch"
    assert retry.normalized_text == baseline


@pytest.mark.parametrize("mutation", [
    lambda s: s.replace("Casa da Aurora", "casa da Aurora"),
    lambda s: s.replace("Casa da Aurora", "Deve Pagar"),
    lambda s: s.replace("Casa da Aurora", "Um Dois Tres Quatro Cinco Seis Sete"),
    lambda s: s.replace("Casa da Aurora", "A" * 81),
    lambda s: s.replace(" - ", "-"),
    lambda s: s.replace(" - ", ": "),
    lambda s: s.replace("Flores", "Flores|"),
    lambda s: s.replace("Flores", "Flores?"),
    lambda s: s.replace("Flores", "Flores;"),
    lambda s: s.replace("Flores", "Rua das Flores"),
    lambda s: s.replace("Aurora", "Au\u202erora"),
    lambda s: s.replace("Aurora", "Au\x00rora"),
    lambda s: s.replace("\n", "\u2028"),
    lambda s: LRI + s,
    lambda s: s + PDI,
    lambda s: s.replace("\n", "\n" + LRI),
    lambda s: s.replace("[[", "[[[", 1),
    lambda s: s.replace("]]", "]]]", 1),
    lambda s: s.replace("[[", "", 1).replace("]]", "", 1),
    lambda s: s.replace("\n", "\n\n"),
    lambda s: s.replace("[[4567-123", "4567-123"),
])
def test_unproven_source_pair_abstains(mutation):
    source = mutation(SOURCE)
    expected = [visible_text(line) for line in source.splitlines()]
    assert blocks(source, expected) == []


@pytest.mark.parametrize("source,expected,target", [
    (SOURCE + "\n" + SOURCE, EXPECTED, token(FIRST + " " + POSTAL)),
    (SOURCE, EXPECTED + [FIRST], token(FIRST + " " + POSTAL)),
    (SOURCE + "\n[[" + FIRST + "]]", EXPECTED, token(FIRST + " " + POSTAL)),
    (SOURCE, ["18", POSTAL], token(FIRST + " " + POSTAL)),
    (SOURCE, [FIRST, "4567", "123"], token(FIRST + " " + POSTAL)),
    (SOURCE, EXPECTED, token(FIRST + " " + POSTAL) * 2),
    (SOURCE, EXPECTED, token(FIRST + " " + POSTAL) + token(FIRST)),
    (SOURCE, EXPECTED, token(POSTAL + " " + FIRST)),
    (SOURCE, EXPECTED, token(FIRST.replace("18", "19") + " " + POSTAL)),
    (SOURCE, EXPECTED, token(FIRST + " " + POSTAL.replace("4567", "4568"))),
    (SOURCE, EXPECTED, token(FIRST + " " + POSTAL + " Extra")),
    (SOURCE, EXPECTED, token(FIRST + "; " + POSTAL)),
])
def test_ambiguous_partial_changed_or_reused_allocation_is_noop(source, expected, target):
    assert decompose(target, source, expected, literal_wrapper_policy=V2) == (target, 0)


@pytest.mark.parametrize("change", [
    lambda s: s.replace(token("R"), ""),
    lambda s: s.replace("Flores", "Flor"),
    lambda s: s.replace("4567", "4568"),
    lambda s: s.replace(POSTAL, "4567-123 Outra Vila"),
])
def test_v2_still_rejects_actual_visible_literal_loss(change):
    primary = token(FIRST + " " + POSTAL) + "\n" + token("R")
    prior = evaluate(primary, policy=V1).normalized_text
    corrected = token(FIRST) + "\n" + token(POSTAL) + "\n" + token("R")
    result = evaluate(change(corrected), primary=prior)
    assert not result.ok


def test_source_newline_permission_does_not_delete_inserted_punctuation():
    primary = token(FIRST + ", " + POSTAL)
    corrected = token(FIRST) + "\n" + token(POSTAL)
    assert not preserves(primary, corrected, EXPECTED, SOURCE, literal_wrapper_policy=V2)
    corrected = token(FIRST.replace(" - ", " ")) + "\n" + token(POSTAL)
    assert not preserves(token(FIRST + " " + POSTAL), corrected, EXPECTED, SOURCE, literal_wrapper_policy=V2)


def test_pair_cannot_borrow_postal_row_from_another_address_or_reorder_blocks():
    other = FIRST.replace("Aurora", "Estrela").replace("18", "29")
    post = POSTAL.replace("4567", "5678")
    source = SOURCE + "\n[[" + other + "]]\n[[" + post + "]]"
    expected = EXPECTED + [other, post]
    wrong = token(FIRST + " " + post) + "\n" + token(other + " " + POSTAL)
    assert decompose(wrong, source, expected, literal_wrapper_policy=V2) == (wrong, 0)
    reversed_pair = token(other + " " + post) + "\n" + token(FIRST + " " + POSTAL)
    assert decompose(reversed_pair, source, expected, literal_wrapper_policy=V2) == (reversed_pair, 0)


def test_genuine_prechange_none_and_v1_evaluation_prompt_bytes_unchanged():
    fixture = json.loads((Path(__file__).parent / "fixtures/primary_literal_packaging_v2_prechange.json").read_bytes())
    for case in fixture["cases"]:
        source, expected = fixture["source"], fixture["expected"]
        initial = evaluate(fixture["primary"], source, expected, policy=case["policy"])
        retry = evaluate(fixture["corrected"], source, expected, initial.normalized_text, policy=case["policy"])
        assert asdict(initial) == case["initial"] and asdict(retry) == case["retry"]
        assert build_ar_token_retry_prompt(fixture["primary"], expected,
            source_text=source, literal_wrapper_policy=case["policy"]) == case["prompt"]
    assert build_ar_token_retry_prompt("prior", EXPECTED, source_text=SOURCE, literal_wrapper_policy=V1) == build_ar_token_retry_prompt("prior", EXPECTED, source_text=SOURCE, literal_wrapper_policy=V2)


def test_resource_limit_and_malformed_inventory_abstain(monkeypatch):
    assert blocks(SOURCE, EXPECTED * 257) == []
    for expected in (None, [], [False], ["x" * 257]):
        assert blocks(SOURCE, expected) == []
    import legalpdf_translate.ar_source_fields as module
    monkeypatch.setattr(module, "_LIMIT", 20)
    assert blocks(SOURCE, EXPECTED) == []


@pytest.mark.parametrize("source", [
    LRI + "\n" + SOURCE,
    LRI + "\n" + SOURCE + "\n" + PDI,
    LRI + "\n" + token(FIRST) + "\n" + token(POSTAL) + "\n" + PDI,
    "\u202e\n" + SOURCE,
    SOURCE + "\n\u200f",
    LRI + LRI + "Unrelated" + PDI + PDI + "\n" + SOURCE,
])
def test_unowned_nested_or_unbalanced_controls_never_create_witness(source):
    assert blocks(source, EXPECTED) == []
    corrected = token(FIRST) + "\n" + token(POSTAL)
    assert not preserves(token(FIRST + " " + POSTAL), corrected, EXPECTED, source, literal_wrapper_policy=V2)


@pytest.mark.parametrize("unrelated", [
    LRI + "Unrelated" + PDI,
    "[" + LRI + "[[Unrelated]]" + PDI + "]",
    token("Unrelated"),
])
def test_safe_balanced_unrelated_directional_runs_do_not_own_postal_rows(unrelated):
    assert len(blocks(unrelated + "\n" + SOURCE, EXPECTED)) == 1


def test_street_marker_is_a_whole_lexical_marker_not_suffix_of_doctor_title():
    first = FIRST.replace("Rua das Flores", "Rua Dr. Flores")
    source = "[[" + first + "]]\n[[" + POSTAL + "]]"
    assert len(blocks(source, [first, POSTAL])) == 1
    assert evaluate(token(first + " " + POSTAL), source, [first, POSTAL]).ok
    first = first.replace("Dr.", "R.")
    assert blocks("[[" + first + "]]\n[[" + POSTAL + "]]", [first, POSTAL]) == []
