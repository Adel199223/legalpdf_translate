"""Optional institutional-footer conflicts preserve all protected content."""
from copy import deepcopy

import pytest

from legalpdf_translate.ordinary_layout_contracts import (
    OrdinaryLayoutError, OPTIONAL_HINT_NORMALIZATION_V1, OPTIONAL_HINT_NORMALIZATION_V2,
    OPTIONAL_HINT_NORMALIZATION_V3, proposal_source_evidence, source_evidence_review_fields)
from tests.test_ordinary_source_evidence import fixture


def institutional_footer():
    snapshot, view, proposal = fixture()
    texts = ["Fictional body", "Fictional court address", "Page 3 of 3", "Fictional contact"]
    roles = ["body", "institution", "source_folio", "institution"]
    snapshot["paragraphs"] = [{"id": f"p{n:06}", "tokens": [{"kind": "t", "text": text}]}
        for n, text in enumerate(texts, 1)]
    view["paragraphs"] = [{"id": row["id"], "text": text} for row, text in zip(snapshot["paragraphs"], texts)]
    ids = [row["id"] for row in snapshot["paragraphs"]]
    view["decisions"]["paragraphs"] = [{"paragraph_id": pid, "regions": [{"page_number": 1, "bbox_px": [1, 1, 20, 20]}]} for pid in ids]
    proposal["paragraphs"] = [{"paragraph_id": pid, "role": role} for pid, role in zip(ids, roles)]
    proposal["bands"] = [{"kind": "flow", "groups": [{"paragraph_ids": ids, "panel": False}]}]
    proposal["source_layout_evidence"] = [{"kind": "source_footer", "paragraph_ids": ids[-3:], "bbox": [.06, .952, .94, .998]}]
    return snapshot, view, proposal


def test_safe_institutional_footer_hint_is_quarantined_without_changing_inputs():
    values = institutional_footer()
    original = deepcopy(values)
    result = proposal_source_evidence(*values)
    assert values == original
    assert result["layout"] == []
    assert result["source_coverage_verified"] is False
    assert result["normalization"] == {
        "version": OPTIONAL_HINT_NORMALIZATION_V3,
        "canonical_proposal_sha256": result["normalization"]["canonical_proposal_sha256"],
        "rejected_hints": [{"index": 0, "kind": "source_footer", "paragraph_ids": ["p000002", "p000003", "p000004"],
            "reason": "source_footer_institution_kept_in_flow"}], "review_required": True}
    assert source_evidence_review_fields([result])["source_layout_review_required"] is True


@pytest.mark.parametrize("version", [OPTIONAL_HINT_NORMALIZATION_V1, OPTIONAL_HINT_NORMALIZATION_V2])
def test_historical_versions_do_not_quarantine_institutional_footer(version):
    with pytest.raises(OrdinaryLayoutError, match="invalid_source_footer_evidence"):
        proposal_source_evidence(*institutional_footer(), normalization_version=version)


@pytest.mark.parametrize("role", ["signature", "heading", "reference", "recipient", "list"])
def test_other_protected_footer_roles_still_fail(role):
    snapshot, view, proposal = institutional_footer()
    proposal["paragraphs"][-1]["role"] = role
    with pytest.raises(OrdinaryLayoutError, match="invalid_source_footer_evidence"):
        proposal_source_evidence(snapshot, view, proposal)


@pytest.mark.parametrize("unsafe", ["unknown", "duplicate", "reverse", "gap", "nonterminal", "box", "blank", "field", "numbering", "numbering_xml", "tab", "interior_break", "partition", "panel"])
def test_institutional_quarantine_runs_after_all_hard_safety_guards(unsafe):
    snapshot, view, proposal = institutional_footer()
    evidence = proposal["source_layout_evidence"][0]
    raw = snapshot["paragraphs"][-1]
    if unsafe == "unknown": evidence["paragraph_ids"][-1] = "unknown"
    elif unsafe == "duplicate": evidence["paragraph_ids"].append(evidence["paragraph_ids"][-1])
    elif unsafe == "reverse": evidence["paragraph_ids"].reverse()
    elif unsafe == "gap": evidence["paragraph_ids"].pop(1)
    elif unsafe == "nonterminal": evidence["paragraph_ids"].pop()
    elif unsafe == "box": evidence["bbox"][1] = .5
    elif unsafe == "blank": raw["tokens"][0]["text"] = " "
    elif unsafe == "field": raw["has_field"] = True
    elif unsafe == "numbering": raw["has_numbering"] = True
    elif unsafe == "numbering_xml": raw["ppr_xml"] = "<w:numPr/>"
    elif unsafe == "tab": raw["tokens"].append({"kind": "tab", "text": "\t"})
    elif unsafe == "interior_break": raw["tokens"].insert(0, {"kind": "page_break", "text": ""})
    elif unsafe == "partition": proposal["paragraph_partitions"] = [{"paragraph_id": raw["id"]}]
    elif unsafe == "panel": proposal["bands"][0]["groups"][0]["panel"] = True
    with pytest.raises(OrdinaryLayoutError): proposal_source_evidence(snapshot, view, proposal)


def test_current_policy_is_v3_and_both_old_metadata_folio_recipes_stay_pinned():
    from legalpdf_translate.ordinary_auto_layout import (
        frozen_automatic_layout_policy, _optional_hint_policy,
        _metadata_normalization_policies, _source_normalization_version)
    current = frozen_automatic_layout_policy()
    assert current == _optional_hint_policy(OPTIONAL_HINT_NORMALIZATION_V3,
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_labeled_folio_v2")
    assert _source_normalization_version(current.split(":", 1)[1]) == OPTIONAL_HINT_NORMALIZATION_V3
    for folio in ["terminal_labeled_folio_v1", "terminal_labeled_folio_v2"]:
        old = _optional_hint_policy(OPTIONAL_HINT_NORMALIZATION_V2,
            emphasis_normalization=True, metadata_normalization=True, primary_folio_version=folio)
        assert old != current and old in _metadata_normalization_policies()
        assert _source_normalization_version(old.split(":", 1)[1]) == OPTIONAL_HINT_NORMALIZATION_V2
    old = _optional_hint_policy(OPTIONAL_HINT_NORMALIZATION_V1)
    assert _source_normalization_version(old.split(":", 1)[1]) == OPTIONAL_HINT_NORMALIZATION_V1
