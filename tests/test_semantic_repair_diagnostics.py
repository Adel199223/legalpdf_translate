"""Complete fresh diagnostics and conservative no-op projections; no provider."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_unit_refs as refs
from tests.test_ordinary_semantic_review import pack, recipe, PDF
from tests.test_ordinary_semantic_unit_refs import response
from tests.test_source_precision_policy_v5 import OPTIONS

OPTIONS = {**OPTIONS, "semantic_source_review_policy": "source_commitment_visual_v5"}


def diagnostic_case(*, count=2):
    pages = pack(count=count)
    settings = recipe()
    units = review.source_units(pages)
    request = repair._request("source_inventory", pages, settings, PDF, units, OPTIONS)
    raw = json.dumps(response("source_inventory", json.loads(request["prompt_text"])))
    canonical, _ = refs.hydrate(raw, "source_inventory", request, units)
    inventory = review.validate_source_inventory(review.audit._json(canonical), pages, units)
    candidate = {page.page_number: page.primary_text for page in pages}
    request = repair._request("verification", pages, settings, PDF, units, OPTIONS,
        inventory=inventory, candidate=candidate)
    data = response("verification", json.loads(request["prompt_text"]))
    return pages, units, inventory, candidate, request, data


def parse(case):
    pages, units, inventory, candidate, request, data = case
    return repair.diagnose(json.dumps(data), request, pages, units, inventory, candidate)


def test_missing_empty_refs_is_diagnostic_only_and_historical_hydration_stays_strict():
    case = diagnostic_case(count=1)
    data = case[-1]
    data["claim_results"][0].update(status="missing", target_unit_ids=[])
    data["unsupported_additions"] = [{"target_unit_ids": ["T001"], "reason": "A candidate-only assertion requires source reinspection."}]
    diagnostic = parse(case)
    assert diagnostic["eligible"] and diagnostic["findings"][0]["target_unit_ids"] == []
    with pytest.raises(review.SemanticAuditError):
        refs.hydrate(json.dumps(data), "verification", case[-2], case[1])


@pytest.mark.parametrize("defect", ["tail_shape", "tail_status", "tail_id", "duplicate", "missing_claim", "wrong_owner",
    "empty_equivalent", "empty_contradiction", "unknown_target", "duplicate_target", "bad_inventory_source",
    "bad_inventory_reason", "bad_addition_target", "bad_addition_tail", "boundary_shape", "boundary_status",
    "missing_boundary", "unknown_field", "target_gap" ])
def test_every_diagnostic_tail_validates_before_eligibility(defect):
    case = diagnostic_case()
    data = case[-1]
    # This early genuine semantic finding must not hide a malformed later row.
    data["inventory_errors"] = [{"source_unit_ids": ["S001"], "reason": "A source qualifier needs reinspection."}]
    if defect == "tail_shape": data["claim_results"][-1]["unexpected"] = True
    elif defect == "tail_status": data["claim_results"][-1]["status"] = "pass"
    elif defect == "tail_id": data["claim_results"][-1]["claim_id"] = "unknown"
    elif defect == "duplicate": data["claim_results"].append(deepcopy(data["claim_results"][0]))
    elif defect == "missing_claim": data["claim_results"].pop()
    elif defect == "wrong_owner": data["claim_results"][-1]["target_unit_ids"] = ["T001"]
    elif defect == "empty_equivalent": data["claim_results"][-1]["target_unit_ids"] = []
    elif defect == "empty_contradiction": data["claim_results"][-1].update(status="contradiction", target_unit_ids=[])
    elif defect == "unknown_target": data["claim_results"][-1]["target_unit_ids"] = ["T999"]
    elif defect == "duplicate_target": data["claim_results"][-1]["target_unit_ids"] *= 2
    elif defect == "bad_inventory_source": data["inventory_errors"].append({"source_unit_ids": ["S999"], "reason": "Unknown source."})
    elif defect == "bad_inventory_reason": data["inventory_errors"][-1]["reason"] = ""
    elif defect == "bad_addition_target": data["unsupported_additions"] = [{"target_unit_ids": ["T999"], "reason": "Unknown target."}]
    elif defect == "bad_addition_tail": data["unsupported_additions"] = [{"target_unit_ids": ["T001"], "reason": "A finding."}, {}]
    elif defect == "boundary_shape": data["boundary_results"][-1]["extra"] = True
    elif defect == "boundary_status": data["boundary_results"][-1]["status"] = "missing"
    elif defect == "missing_boundary": data["boundary_results"] = []
    elif defect == "unknown_field": data["unsupported"] = []
    elif defect == "target_gap": data["claim_results"][-1].update(status="missing", target_unit_ids=[])
    with pytest.raises(review.SemanticAuditError):
        parse(case)


@pytest.mark.parametrize("field,status", [("claim_results", "unresolved"), ("boundary_results", "unresolved"), ("boundary_results", "contradiction")])
def test_unresolved_or_failed_boundary_never_licenses_repair(field, status):
    case = diagnostic_case()
    case[-1][field][-1]["status"] = status
    diagnostic = parse(case)
    assert diagnostic["hard_stop"] and not diagnostic["eligible"]


def test_inventory_noop_ignores_renumber_reorder_and_inverse_bookkeeping():
    inventory = diagnostic_case()[2]
    changed = deepcopy(inventory)
    lookup = {row["claim_id"]: f"renamed_{index}" for index, row in enumerate(changed["claims"], 1)}
    for row in changed["claims"]: row["claim_id"] = lookup[row["claim_id"]]
    changed["claims"].reverse()
    for row in changed["boundaries"]: row["claim_ids"] = [lookup[key] for key in reversed(row["claim_ids"])]
    for row in changed["unit_coverage"]: row["claim_ids"] = [lookup[key] for key in row["claim_ids"]]
    changed["unit_coverage"].reverse()
    changed["page_visual_coverage"].reverse()
    assert repair.inventory_projection(inventory) == repair.inventory_projection(changed)
    assert not repair.substantive_change(inventory, changed, {1: "نص عربي."}, {1: "\nنص عربي.\n\n"})


def test_valid_meaningful_context_citation_fix_remains_substantive():
    pages = (replace(pack()[0], source_text="A repeated source.\nA repeated source.",
                     original_source_text="A repeated source.\nA repeated source."),)
    units = review.source_units(pages)
    request = repair._request("source_inventory", pages, recipe(), PDF, units, OPTIONS)
    raw = json.dumps(response("source_inventory", json.loads(request["prompt_text"])))
    inventory, _ = refs.hydrate(raw, "source_inventory", request, units)
    review.validate_source_inventory(review.audit._json(inventory), pages, units)
    changed = deepcopy(inventory)
    changed["claims"][0]["source_evidence"].append(deepcopy(changed["claims"][1]["source_evidence"][0]))
    review.validate_source_inventory(review.audit._json(changed), pages, units)
    assert repair.substantive_change(inventory, changed, {1: "نص عربي."}, {1: "نص عربي."})


def test_inventory_projection_keeps_multiplicity_and_material_axes():
    inventory = diagnostic_case()[2]
    changed = deepcopy(inventory)
    changed["claims"][0]["axes"]["conditions"] = "Only while present."
    assert repair.inventory_projection(inventory) != repair.inventory_projection(changed)
    changed = deepcopy(inventory)
    changed["claims"].append({**deepcopy(changed["claims"][0]), "claim_id": "another"})
    assert repair.inventory_projection(inventory) != repair.inventory_projection(changed)


def test_comparison_never_normalizes_literal_interior_punctuation_or_diacritics():
    inventory = diagnostic_case()[2]
    for old, new in [("نص \u2066[[A B]]\u2069", "نص \u2066[[A  B]]\u2069"),
                     ("نص،", "نص."), ("نَص", "نص")]:
        assert repair.substantive_change(inventory, inventory, {1: old}, {1: new})


def test_ascii_presentation_only_candidate_and_inventory_edits_do_not_buy_a_verifier():
    inventory = diagnostic_case()[2]
    changed = deepcopy(inventory)
    changed["claims"][0]["proposition"] = changed["claims"][0]["proposition"].replace(" ", "  \t")
    changed["claims"][0]["axes"]["actor_recipient"] = changed["claims"][0]["axes"]["actor_recipient"].replace(" ", "  ")
    assert not repair.substantive_change(inventory, changed, {1: "نص عربي."}, {1: "\nنص  \tعربي.\n"})
    assert repair._presentation("word boundary") != repair._presentation("wordboundary")
    assert repair._presentation("نص \u2066[[A B]]\u2069") != repair._presentation("نص \u2066[[A  B]]\u2069")
