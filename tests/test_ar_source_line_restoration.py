"""Fictional source-bound postal line restoration through the real evaluator."""
import pytest
import re

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens, pretokenize_arabic_source
from legalpdf_translate.ar_literal_fidelity import correction_preserves_additional_literals, visible_text
from legalpdf_translate.ar_source_fields import source_address_line_blocks
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow_components.evaluation import evaluate_output


STREET = "Rua da Árvore, 7"
LOCALITY = "Várzea"
POSTAL = "1234 Vila Nova"
BLOCK = "\n".join((STREET, LOCALITY, POSTAL))
FLAT = BLOCK.replace("\n", " ")


def token(value):
    return "\u2066[[" + value + "]]\u2069"


def restored(block=BLOCK):
    # Retained response shape: street/house, locality, postcode/locality tokens.
    # Use fictional values while preserving the real required numeric contract.
    def wrap_line(line):
        return " ".join(token(part) for part in re.split(r"(?<=,) (?=[0-9])|(?<=[0-9]) (?=[A-Z])", line))
    return "\n".join(wrap_line(line) for line in block.split("\n"))


def evaluate(corrected, *, source=BLOCK, primary=None):
    protected_source = pretokenize_arabic_source(source)
    return evaluate_output("```\nنص " + corrected + "\n```", TargetLang.AR,
        expected_ar_tokens=extract_locked_tokens(protected_source), ar_source_text=protected_source,
        primary_normalized_text="نص " + (token(FLAT) if primary is None else primary))


@pytest.mark.parametrize("block", [BLOCK, BLOCK.replace("1234", "1234-567"),
    STREET + "\n1234-567 Vila Nova", STREET + "\n" + POSTAL,
    BLOCK.replace("Rua da", "Rua  da")])
def test_real_pretokenization_and_required_tokens_allow_only_exact_source_restoration(block):
    source = pretokenize_arabic_source(block)
    assert visible_text(source) == block
    assert extract_locked_tokens(source)
    corrected = restored(block)
    if "1234-567" in block and len(block.split("\n")) == 3:
        # Anchored full-postcode input already requires its complete street.
        corrected = token(STREET) + "\n" + token(LOCALITY) + "\n" + token("1234-567 Vila Nova")
    result = evaluate(corrected, source=block, primary=token(block.replace("\n", " ")))
    assert result.ok, result
    assert visible_text(result.normalized_text) == "نص " + block


@pytest.mark.parametrize("boundary", ["\n", "\r", "\r\n"])
def test_direct_guard_preserves_the_exact_source_cr_lf_witness(boundary):
    block = BLOCK.replace("\n", boundary)
    corrected = boundary.join(token(line) for line in block.split(boundary))
    assert correction_preserves_additional_literals(token(FLAT), corrected, [], pretokenize_arabic_source(block))
    if boundary != "\n":
        assert not correction_preserves_additional_literals(token(FLAT), restored(), [], block)


@pytest.mark.parametrize("source", [None, "", FLAT, BLOCK + "\n\n" + BLOCK,
    BLOCK + "\n\n" + BLOCK.replace("\n", "\r\n"),
    BLOCK + "\n\n" + FLAT,
    "\n".join((STREET, POSTAL, LOCALITY)), "\n".join((LOCALITY, STREET, POSTAL)),
    STREET + "\ntexto corrido\n" + POSTAL, STREET + "\n\n" + POSTAL])
def test_absent_ambiguous_or_differently_associated_source_never_proves_restoration(source):
    assert not correction_preserves_additional_literals(token(FLAT), restored(), [], source)


@pytest.mark.parametrize("changed", [
    BLOCK.replace(", 7", ", 17"), BLOCK.replace("Árvore", "Arvore"),
    BLOCK.replace("Árvore", "árvore"), BLOCK.replace(",", "،"),
    BLOCK.replace("Rua da", "Rua  da"), BLOCK.replace("Rua da", "Rua\tda"),
    BLOCK.replace("Vila Nova", "Vila  Nova"), BLOCK.replace("1234", "1235"),
    BLOCK.replace("\n", "\n\n"), BLOCK.replace("\n", "\u2028"),
    BLOCK.replace("\n", "\n "), BLOCK.replace("\n", "\n", 1).replace("Várzea\n", "Várzea "),
    BLOCK.replace("Rua da", "Rua\nda"), "\n".join((STREET, POSTAL, LOCALITY)),
])
def test_content_inline_whitespace_and_unwitnessed_boundaries_stay_rejected(changed):
    assert not correction_preserves_additional_literals(token(FLAT), restored(changed), [], BLOCK)


@pytest.mark.parametrize("primary", [token(FLAT.replace(" ", "  ", 1)),
    token(FLAT.replace("Várzea ", "Várzea  ")), token(FLAT.replace("Várzea ", "Várzea\t"))])
def test_primary_must_flatten_each_source_boundary_to_exactly_one_ascii_space(primary):
    assert not correction_preserves_additional_literals(primary, restored(), [], BLOCK)


def test_newlines_cannot_flatten_in_the_reverse_direction():
    assert not correction_preserves_additional_literals(restored(), token(FLAT), [], BLOCK)


@pytest.mark.parametrize("changed", [BLOCK.replace(", 7", ", 17"), BLOCK.replace("Árvore", "Arvore"),
    BLOCK.replace("Árvore", "árvore"), BLOCK.replace(",", "،"),
    BLOCK.replace("Rua da", "Rua  da"), BLOCK.replace("\n", "\n\n"),
    BLOCK.replace("\n", "\n "), BLOCK.replace("1234", "1235"),
    "\n".join((STREET, POSTAL, LOCALITY))])
def test_full_evaluator_keeps_changed_content_and_unwitnessed_lines_rejected(changed):
    assert not evaluate(restored(changed)).ok


def test_existing_raw_output_line_normalization_still_precedes_exact_guard_proof():
    for body in [restored().replace("\n", "\n\n"), restored().replace("\n", "\r\n")]:
        result = evaluate(body)
        assert result.ok
        assert visible_text(result.normalized_text) == "نص " + BLOCK
    # The new guard itself never folds these boundaries or other whitespace.
    assert not correction_preserves_additional_literals(token(FLAT),
        restored().replace("\n", "\n\n"), [], BLOCK)


@pytest.mark.parametrize("corrected", [restored() + " " + restored(),
    token(STREET) + "\n" + LOCALITY + "\n" + token(POSTAL),
    token("prefix " + STREET) + "\n" + token(LOCALITY) + "\n" + token(POSTAL),
    token(STREET) + "\n" + token(LOCALITY) + "\n" + token(POSTAL + " suffix")])
def test_proof_requires_unique_complete_whole_token_coverage(corrected):
    assert not correction_preserves_additional_literals(token(FLAT), corrected, [], BLOCK)


def test_repeated_and_nested_required_or_additional_occurrences_cannot_reuse_one_group():
    for extra, required in [(FLAT, []), ("7", ["7"]), (LOCALITY, []), (POSTAL, [POSTAL])]:
        assert not correction_preserves_additional_literals(token(FLAT) + " " + token(extra),
            restored(), required, pretokenize_arabic_source(BLOCK))
    assert evaluate(restored(), primary=token(FLAT) + " " + token("7")).ok is False


def test_other_required_and_additional_tokens_keep_disjoint_ownership():
    extra = token("Independent Example")
    assert evaluate(restored() + " " + extra, primary=token(FLAT) + " " + extra).ok
    assert not evaluate(restored(), primary=token(FLAT) + " " + extra).ok
    assert not evaluate(restored(), source=BLOCK + "\n9999").ok


def test_multiple_source_blocks_cannot_swap_association():
    other = "Avenida da Paz, 8\n4321 Outro Lugar"
    primary = token(FLAT) + "\n" + token(other.replace("\n", " "))
    corrected = restored() + "\n" + restored(other)
    assert correction_preserves_additional_literals(primary, corrected, [], BLOCK + "\n" + other)
    assert not correction_preserves_additional_literals(primary, restored(other) + "\n" + restored(),
        [], BLOCK + "\n" + other)
    assert not correction_preserves_additional_literals(primary, corrected, [], other + "\n" + BLOCK)


@pytest.mark.parametrize("unchanged", ["flat", "restored"])
def test_restored_candidate_cannot_swap_relative_to_an_unchanged_source_block(unchanged):
    other = "Avenida da Paz, 8\n4321 Outro Lugar"
    stable = token(other.replace("\n", " ") if unchanged == "flat" else other)
    source = pretokenize_arabic_source(BLOCK + "\n" + other)
    primary = token(FLAT) + "\n" + stable
    assert correction_preserves_additional_literals(primary, restored() + "\n" + stable, [], source)
    assert not correction_preserves_additional_literals(primary, stable + "\n" + restored(), [], source)


@pytest.mark.parametrize("malformed", ["[[[" + FLAT + "]]]", "\u2066[[" + FLAT + "]]",
    "[[" + FLAT + "]]\u2069", "[[" + FLAT, token(FLAT) + "]]"])
def test_malformed_primary_corrected_and_source_wrappers_fail_closed(malformed):
    assert not correction_preserves_additional_literals(malformed, restored(), [], BLOCK)
    assert not correction_preserves_additional_literals(token(FLAT), malformed, [], BLOCK)
    assert not correction_preserves_additional_literals(token(FLAT), restored(), [], malformed)


@pytest.mark.parametrize("bound", ["_MAX_GROUP_WORK", "_MAX_GROUP_STATES", "_MAX_SOURCE_LINE_WORK"])
def test_restoration_proof_resource_bounds_fail_closed(monkeypatch, bound):
    from legalpdf_translate import ar_literal_fidelity
    monkeypatch.setattr(ar_literal_fidelity, bound, 1)
    assert not correction_preserves_additional_literals(token(FLAT), restored(), [], BLOCK)


def test_overlong_or_non_cr_lf_source_boundaries_fail_closed():
    assert not correction_preserves_additional_literals(token(FLAT), restored(), [], "x" * 120001 + BLOCK)
    for bad in [BLOCK.replace("\n", "\u2028"), STREET + "\n" + "V" * 141 + "\n" + POSTAL]:
        assert source_address_line_blocks(bad) == []


@pytest.mark.parametrize("postal", ["12345 Vila Nova", "1234-56 Vila Nova", "1234-5678 Vila Nova",
    "1234 vila nova", "1234 deve pagar", "١٢٣٤ Vila Nova"])
def test_source_witness_requires_strict_ascii_postal_and_latin_locality(postal):
    assert source_address_line_blocks(STREET + "\n" + postal) == []
