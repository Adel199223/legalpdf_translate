"""Fictional source enclosures and exact source-row restoration, fresh v3 only."""
from itertools import product

import pytest

from legalpdf_translate import ar_literal_fidelity as f
from legalpdf_translate.ar_source_fields import _view
from legalpdf_translate.output_normalize import LRI, PDI
from legalpdf_translate.prompt_builder import build_ar_token_retry_prompt
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow_components.evaluation import evaluate_output

V3 = "lossless_source_components_v3"
OLD = [None, "lossless_source_components_v1", "lossless_source_components_v2"]
SOURCE = "Rua da Aurora [[8]]\nVale Claro\n[[4321]] Cidade Nova"
FUSED = "Rua da Aurora 8, Vale Claro, 4321 Cidade Nova"
REQUIRED = ["7", "8", "4321"]


def token(value):
    return LRI + "[[" + value + "]]" + PDI


def enclosure_case(source_enclosure=None, target_enclosure=None):
    source_enclosure = "[" + token("7") + "]" if source_enclosure is None else source_enclosure
    target_enclosure = "[" + token("7") + "]" if target_enclosure is None else target_enclosure
    return source_enclosure + "\n" + SOURCE, "نص " + target_enclosure + "\nالعنوان " + token(FUSED)


def test_source_qualified_square_enclosure_recovers_only_local_raw_coordinates():
    source, primary = enclosure_case()
    shared_before = _view(primary)
    result, count = f.decompose_source_literal_components_with_stats(primary, source, REQUIRED, literal_wrapper_policy=V3)
    assert count == 1 and f.visible_text(result) == f.visible_text(primary)
    assert "[" + token("7") + "]" in result
    assert token("8") in result and token("4321") in result
    assert _view(primary) == shared_before  # Global parser behavior stays unchanged.
    assert f.decompose_source_literal_components_with_stats(result, source, REQUIRED, literal_wrapper_policy=V3) == (result, 0)
    for old in OLD:
        assert f.decompose_source_literal_components_with_stats(primary, source, REQUIRED, literal_wrapper_policy=old) == (primary, 0)


@pytest.mark.parametrize("source_enclosure,target_enclosure", [
    (token("7"), "[" + token("7") + "]"),
    ("(" + token("7") + ")", "[" + token("7") + "]"),
    ("[" + token("7") + "]\n[" + token("7") + "]", "[" + token("7") + "]"),
    ("[" + token("7") + "]\n[7]", "[" + token("7") + "]"),
    ("[[" + token("7") + "]]", "[" + token("7") + "]"),
    ("([" + token("7") + "])", "[" + token("7") + "]"),
    (None, "[[" + token("7") + "]]"),
    (None, "([" + token("7") + "])"),
    (None, "[ [" + token("7") + "] ]"),
    ("[ note [" + token("7") + "] ]", None),
    (None, "[" + LRI + "[[7]]" + "]"),
    (None, "[" + "[[7]]" + PDI + "]"),
    (None, LRI + "[" + token("7") + "]" + PDI),
    (None, "[" + token("7") + "] [" + token("7") + "]"),
    ("\u202e[" + token("7") + "]", None),
    (None, "\u200f[" + token("7") + "]"),
])
def test_unwitnessed_nested_half_ambient_duplicate_or_unsafe_enclosure_is_noop(source_enclosure, target_enclosure):
    source, primary = enclosure_case(source_enclosure, target_enclosure)
    assert f.decompose_source_literal_components_with_stats(primary, source, REQUIRED, literal_wrapper_policy=V3) == (primary, 0)


@pytest.mark.parametrize("side", ["source", "target"])
def test_enclosure_does_not_relax_numeric_occurrence_uniqueness(side):
    source, primary = enclosure_case()
    if side == "source":
        source += "\n8"
    else:
        primary += "\n" + token("8")
    assert f.decompose_source_literal_components_with_stats(primary, source, REQUIRED, literal_wrapper_policy=V3) == (primary, 0)


def test_repeated_non_enclosed_reference_does_not_own_the_unique_printed_enclosure():
    source, primary = enclosure_case()
    source += "\n" + token("7") + "\n" + token("7")
    primary += "\n" + token("7") + "\n" + token("7")
    result, count = f.decompose_source_literal_components_with_stats(primary, source, REQUIRED, literal_wrapper_policy=V3)
    assert count == 1 and f.visible_text(result) == f.visible_text(primary)
    assert result.count(token("7")) == 3


def test_identical_correction_keeps_existing_tab_source_support_when_no_new_proof_is_needed():
    source = "Referencia:\t[[7123]]"
    raw = "```\nمرجع " + token("7123") + "\n```"
    primary = evaluate_output(raw, TargetLang.AR, expected_ar_tokens=["7123"],
        ar_source_text=source, literal_wrapper_policy=V3)
    correction = evaluate_output(raw, TargetLang.AR, expected_ar_tokens=["7123"],
        ar_source_text=source, primary_normalized_text=primary.normalized_text, literal_wrapper_policy=V3)
    assert primary.ok and correction.ok


ROWS = ("Rua das Acácias, 17", "Vale Sereno", "6543 Cidade Clara")


def joined(rows=ROWS, joins=(", ", ", ")):
    return "".join(row + (joins[i] if i < len(joins) else "") for i, row in enumerate(rows))


def restored(rows=ROWS, newline="\n"):
    return newline.join(token(row) for row in rows)


def preserves(before, after, source="\n".join(ROWS), policy=V3):
    return f.correction_preserves_additional_literals(before, after, [], source, literal_wrapper_policy=policy)


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"])
@pytest.mark.parametrize("joins", list(product((" ", ", ", "، "), repeat=2)))
def test_each_supported_per_row_join_restores_only_the_complete_exact_source_block(newline, joins):
    assert preserves(token(joined(joins=joins)), restored(newline=newline), newline.join(ROWS))


@pytest.mark.parametrize("after", [
    restored().replace("Acácias,", "Acácias"),
    restored().replace("Acácias,", "Acácias،"),
    restored().replace(" 17", " 18"),
    restored().replace("6543", "6544"),
    restored().replace("Vale Sereno", "Vale  Sereno"),
    restored().replace("Vale Sereno", "vale Sereno"),
    restored().replace(token(ROWS[1]) + "\n", ""),
    restored().replace("\n", "\n\n"),
    restored() + "\n" + restored(),
    restored() + "\n" + token(joined(joins=(" ", " "))),
])
def test_restoration_rejects_within_row_edits_missing_rows_and_duplicate_variants(after):
    assert not preserves(token(joined()), after)


@pytest.mark.parametrize("before", [
    token(joined().replace(", Vale", ",  Vale")),
    token(joined().replace(", Vale", "; Vale")),
    token(joined()) + "\n" + token(joined(joins=(" ", " "))),
    token(joined()) + "\n" + token("17"),
    token(joined()) + "\n" + token("R"),
])
def test_ambiguous_prior_or_unrelated_lost_literals_cannot_share_an_address_group(before):
    assert not preserves(before, restored())


@pytest.mark.parametrize("source", [None, "", joined(), "\n".join(ROWS) * 2,
    "\n".join(ROWS) + "\n" + joined(joins=(" ", " ")),
    "\u202e" + "\n".join(ROWS),
    LRI + "\n".join(ROWS) + PDI,
])
def test_source_witness_must_be_unique_exact_and_safe(source):
    assert not preserves(token(joined()), restored(), source)


def test_two_distinct_blocks_need_disjoint_whole_tokens_and_source_order():
    other = ("Avenida da Luz, 29", "Vale Novo", "7654 Outra Cidade")
    source = "\n".join(ROWS) + "\n\n" + "\n".join(other)
    before = token(joined()) + "\n" + token(joined(other))
    after = restored() + "\n" + restored(other)
    assert preserves(before, after, source)
    assert not preserves(before, restored(other) + "\n" + restored(), source)
    assert not preserves(token(joined(other)) + "\n" + token(joined()), after, source)


def test_unchanged_other_join_variant_still_reserves_its_source_order_and_multiplicity():
    other = ("Avenida da Luz, 29", "Vale Novo", "7654 Outra Cidade")
    source = "\n".join(ROWS) + "\n\n" + "\n".join(other)
    unchanged = token(joined(other, ("، ", "، ")))
    before = token(joined()) + "\n" + unchanged
    assert preserves(before, restored() + "\n" + unchanged, source)
    assert not preserves(before, unchanged + "\n" + restored(), source)
    assert not preserves(before, unchanged + "\n" + restored() + "\n" + unchanged, source)
    alternate_newlines = source + "\n\n" + "\r\n".join(other)
    assert not preserves(before, restored() + "\n" + unchanged, alternate_newlines)


def test_repeated_primary_additional_literal_requires_distinct_corrected_occurrences():
    assert not preserves(token(joined()) + " " + token("R") + " " + token("R"), restored() + " " + token("R"))


@pytest.mark.parametrize("policy", OLD)
def test_saved_policies_keep_comma_restoration_rejected_and_prompt_bytes_unchanged(policy):
    assert not preserves(token(joined()), restored(), policy=policy)
    if policy is not None:
        assert build_ar_token_retry_prompt("prior", [], literal_wrapper_policy=policy) == build_ar_token_retry_prompt("prior", [], literal_wrapper_policy=V3)


def test_required_inventory_loss_still_fails_full_evaluation():
    result = evaluate_output("```\nنص " + restored() + "\n```", TargetLang.AR,
        expected_ar_tokens=["9999"], ar_source_text="\n".join(ROWS),
        primary_normalized_text="نص " + token(joined()), literal_wrapper_policy=V3)
    assert not result.ok and result.ar_violation_kind == "expected_token_mismatch"


def test_resource_limits_stop_both_new_proofs(monkeypatch):
    source, primary = enclosure_case()
    monkeypatch.setattr(f, "_MAX_COMPONENT_WORK", 1)
    assert f.decompose_source_literal_components_with_stats(primary, source, REQUIRED, literal_wrapper_policy=V3) == (primary, 0)
    monkeypatch.setattr(f, "_MAX_SOURCE_LINE_WORK", 1)
    assert not preserves(token(joined()), restored())
