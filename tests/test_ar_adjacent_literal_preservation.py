"""Exact wrapper regrouping must retain independent protected occurrences."""
import pytest

from legalpdf_translate.ar_literal_fidelity import correction_preserves_additional_literals
from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow_components.evaluation import evaluate_output


def token(value):
    return "\u2066[[" + value + "]]\u2069"


STREET = "Rua da Árvore, 5"
POSTAL = "1234-567 Vila Nova"
COMBINED = token(STREET) + "\n" + token(POSTAL)
SPLIT = token("Rua da Árvore") + ", " + token("5") + "\n" + token("1234-567") + " " + token("Vila Nova")


@pytest.mark.parametrize("primary,corrected", [(COMBINED, SPLIT), (SPLIT, COMBINED)])
def test_exact_street_house_and_postal_locality_split_merge(primary, corrected):
    assert correction_preserves_additional_literals(primary, corrected, [])
    result = evaluate_output("```\nنص " + corrected + " " + token("Required") + "\n```",
        TargetLang.AR, expected_ar_tokens=["Required"], primary_normalized_text="نص " + primary)
    assert result.ok, result


@pytest.mark.parametrize("corrected", [
    token("Rua da Árvore") + ", " + token("15"),
    token("Rua da Árvore") + "، " + token("5"),
    token("Rua da Arvore") + ", " + token("5"),
    token("Rua da árvore") + ", " + token("5"),
    token("Rua da Árvore") + ",  " + token("5"),
    token("Rua da Árvore") + " palavra " + token("5"),
    token("Rua da Árvore") + " كلمة " + token("5"),
    token("Rua da Árvore") + ", 5",
    token("Rua da Árvore"),
    STREET,
])
def test_changed_or_unprotected_visible_content_is_not_equivalent(corrected):
    assert not correction_preserves_additional_literals(token(STREET), corrected, [])


def test_one_split_group_cannot_mask_repeated_or_nested_literal_loss():
    split = token("Rua da Árvore") + ", " + token("5")
    assert not correction_preserves_additional_literals(token(STREET) + " " + token(STREET), split, [])
    assert not correction_preserves_additional_literals(token(STREET) + " " + token("5"), split, ["5"])
    assert not correction_preserves_additional_literals(token("A B") + " " + token("B C"),
        token("A") + " " + token("B") + " " + token("C"), [])


def test_disjoint_allocation_can_choose_between_equal_groupings():
    primary = token("A B") + " / " + token("A") + " " + token("B")
    corrected = token("A") + " " + token("B") + " / " + token("A B")
    assert correction_preserves_additional_literals(primary, corrected, [])
    assert not correction_preserves_additional_literals(primary, token("A B"), [])


@pytest.mark.parametrize("malformed", [
    "[[[Rua da Árvore, 5]]]", "\u2066[[Rua da Árvore, 5]]",
    "[[Rua da Árvore, 5]]\u2069", "[[Rua da Árvore]], [[5]",
])
def test_malformed_wrappers_never_prove_regrouping(malformed):
    assert not correction_preserves_additional_literals(token(STREET), malformed, [])
    assert not correction_preserves_additional_literals(malformed, token(STREET), [])


def test_split_matching_does_not_change_required_literal_validation():
    result = evaluate_output("```\nنص " + SPLIT + "\n```", TargetLang.AR,
        expected_ar_tokens=["Missing"], primary_normalized_text="نص " + COMBINED)
    assert not result.ok and result.ar_violation_kind == "expected_token_mismatch"


@pytest.mark.parametrize("bound", ["_MAX_GROUP_WORK", "_MAX_GROUP_STATES"])
def test_ambiguous_proof_resource_exhaustion_fails_closed(monkeypatch, bound):
    from legalpdf_translate import ar_literal_fidelity
    monkeypatch.setattr(ar_literal_fidelity, bound, 1)
    assert not correction_preserves_additional_literals(COMBINED, SPLIT, [])
    assert correction_preserves_additional_literals(COMBINED, COMBINED, [])
