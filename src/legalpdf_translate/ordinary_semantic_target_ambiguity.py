"""Opt-in initial target-only ambiguity diagnosis; never final acceptance."""
from copy import deepcopy
import base64
import re

from . import ordinary_semantic_review as review
from . import ordinary_semantic_unit_refs as refs

KEY = "semantic_target_ambiguity_policy"
POLICY = "initial_target_ambiguity_repair_v1"
STATUS = "target_ambiguity"
_BASE_KEYS = {"stage", "protocol", "pdf_sha256", "configured_image_mode", "source_image_policy", "source_pages",
    "source_units", "source_inventory", "literal_protocol", "candidate_pages", "target_units",
    "semantic_source_review_policy", "semantic_unit_reference_policy", "semantic_page_coverage_policy"}
INSTRUCTIONS = """
INITIAL TARGET-AMBIGUITY DIAGNOSTIC PROFILE:
The additional claim status target_ambiguity is a failed diagnostic, never acceptance.
Use it only when the complete original source, its context and the supplied source image
make the source commitment clear, the validated inventory states that commitment without
unresolved source meaning, and the cited candidate text leaves a material aspect of that
same commitment ambiguous. A source-grounded wording clarification must be possible
without choosing between genuinely uncertain source readings or adding a source fact.
Examples of aspects are actor/recipient, agency, scope, polarity/modality, temporal state
and conditions; do not invent an unspecified participant or resolve an unspecified fact.
Cite nonempty target_unit_ids with the existing exact claim ownership rules. Mere style
preferences or an equivalent alternative phrasing are equivalent, not target_ambiguity.
Use missing or contradiction for those actual defects. Keep unresolved for unclear,
unreadable or genuinely uncertain source meaning, insufficient evidence, or any uncertainty
that cannot be specifically attributed to the candidate's wording. Report bad or missing
inventory propositions in inventory_errors rather than forcing agreement with inventory.
All existing complete claim/target coverage, boundary and unsupported-addition checks
remain required. Do not propose replacement text, choose a preferred verdict, or repair
the candidate. Only an entirely equivalent result can pass this verification.
"""


def check_policy(policy):
    if policy is not None and (type(policy) is not str or policy != POLICY):
        review._fail("repair_target_ambiguity_policy")


def descriptor():
    return {"policy": POLICY, "instruction_sha256": review.audit._sha(INSTRUCTIONS),
        "request_profile": "initial_verification_claim_status_v1",
        "eligibility_semantics": "whole_resolved_inventory_text_owned_image_backed_target_only_v1"}


def _format(payload):
    source = {unit["unit_id"]: unit for unit in payload["source_units"]}
    target = {unit["unit_id"]: unit for unit in payload["target_units"]}
    result = refs.response_format("verification", source, inventory=payload["source_inventory"], target=target)
    result["schema"]["properties"]["claim_results"]["items"]["properties"]["status"]["enum"].append(STATUS)
    refs._check_schema(result["schema"])
    return result


def adapt_request(request, *, semantic_source_review_policy="source_commitment_visual_v7"):
    """Caller invokes this only for the unused ordinary attempt00 verifier."""
    from . import ordinary_semantic_source_review as source_policy
    if (type(semantic_source_review_policy) is not str
            or semantic_source_review_policy not in (source_policy.POLICY_V7, source_policy.POLICY_V8, source_policy.POLICY_V9)):
        review._fail("repair_target_ambiguity_profile")
    payload = review._parse(request["prompt_text"])
    if (set(payload) != _BASE_KEYS or payload.get("stage") != "verification" or payload.get("protocol") != refs.PROTOCOL
            or payload.get("semantic_unit_reference_policy") != refs.POLICY or KEY in payload
            or review.audit._json(payload.get("semantic_source_review_policy")) != review.audit._json(source_policy.descriptor(semantic_source_review_policy))):
        review._fail("repair_target_ambiguity_profile")
    if semantic_source_review_policy in (source_policy.POLICY_V8, source_policy.POLICY_V9):
        instructions = (review._VERIFICATION + refs._ATOMIC + refs._VERIFY
            + source_policy._suffixes(semantic_source_review_policy)["verification"])
        if request.get("instructions") != instructions:
            review._fail("repair_target_ambiguity_profile")
    result = deepcopy(request)
    expected = _format(payload)
    legacy = deepcopy(expected)
    legacy["schema"]["properties"]["claim_results"]["items"]["properties"]["status"]["enum"].remove(STATUS)
    if review.audit._json(request["response_format"]) != review.audit._json(legacy):
        review._fail("repair_target_ambiguity_profile")
    payload[KEY] = descriptor()
    result.update(prompt_text=review._prompt_json(payload), instructions=request["instructions"] + INSTRUCTIONS,
                  response_format=expected)
    return result


def check_request(request, pages, units, inventory, candidate, *,
                  semantic_source_review_policy="source_commitment_visual_v7"):
    """Rebind the exact profile, source/target units, inventory and image order."""
    from . import ordinary_semantic_source_review as source_policy
    from . import ordinary_semantic_page_coverage as page_policy
    if (type(semantic_source_review_policy) is not str
            or semantic_source_review_policy not in (source_policy.POLICY_V7, source_policy.POLICY_V8, source_policy.POLICY_V9)):
        review._fail("repair_target_ambiguity_profile")
    payload = review._parse(request["prompt_text"])
    source = refs.unit_map(units, "S")
    targets = refs.unit_map(review.source_units(pages, candidate=candidate), "T")
    projected_inventory = deepcopy(inventory)
    reverse = {unit["unit_id"]: key for key, unit in source.items()}
    for claim in projected_inventory["claims"]:
        claim["source_unit_ids"] = [reverse[key] for key in claim["source_unit_ids"]]
    for row in projected_inventory["unit_coverage"]:
        row["unit_id"] = reverse[row["unit_id"]]
    positions = {page.page_number: i + 1 for i, page in enumerate(p for p in pages if p.image_data_url is not None)}
    expected = {"stage": "verification", "protocol": refs.PROTOCOL, "semantic_unit_reference_policy": refs.POLICY,
        KEY: descriptor(), "semantic_source_review_policy": source_policy.descriptor(semantic_source_review_policy),
        "semantic_page_coverage_policy": page_policy.descriptor([page.page_number for page in pages]),
        "source_image_policy": "configured_image_mode_v1",
        "source_units": [{**unit, "unit_id": key} for key, unit in source.items()],
        "target_units": [{**unit, "unit_id": key} for key, unit in targets.items()],
        "source_inventory": projected_inventory,
        "source_pages": [{"page": page.page_number, "original_source_text": review._original(page),
            "image_position": positions.get(page.page_number), "visual_coverage": page.visual_coverage} for page in pages],
        "candidate_pages": [{"page": page.page_number, "text": candidate[page.page_number]} for page in pages],
        "literal_protocol": review.literal_protocol(pages)}
    instructions = (review._VERIFICATION + refs._ATOMIC + refs._VERIFY
        + source_policy._suffixes(semantic_source_review_policy)["verification"] + INSTRUCTIONS)
    if (set(payload) != _BASE_KEYS | {KEY}
            or payload.get("configured_image_mode") not in {"off", "auto", "always"}
            or any(review.audit._json(payload.get(key)) != review.audit._json(value) for key, value in expected.items())
            or request.get("instructions") != instructions
            or tuple(request.get("image_data_urls", ())) != tuple(p.image_data_url for p in pages if p.image_data_url is not None)
            or review.audit._json(request.get("response_format")) != review.audit._json(_format(payload))):
        review._fail("repair_target_ambiguity_profile")


def _image(value):
    if type(value) is not str or len(value) > review.audit.MAX_IMAGE_BYTES * 4 // 3 + 100:
        return False
    match = re.fullmatch(r"data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=]+)", value)
    if match is None:
        return False
    try:
        decoded = base64.b64decode(match[1], validate=True)
    except ValueError:
        return False
    return 0 < len(decoded) <= review.audit.MAX_IMAGE_BYTES


def eligible(data, pages, units, inventory, candidate):
    """Extra prerequisites apply only when the diagnostic uses the new status."""
    affected = [row for row in data["claim_results"] if row["status"] == STATUS]
    if (not affected or any(row["status"] not in {"equivalent", STATUS} for row in data["claim_results"])
            or any(row["status"] != "equivalent" for row in data["boundary_results"])
            or data["inventory_errors"] or data["unsupported_additions"]):
        return False
    # Recheck every claim and boundary, including unrelated source commitments.
    review.validate_source_inventory(review.audit._json(inventory), pages, units)
    claims = {row["claim_id"]: row for row in inventory["claims"]}
    originals = {unit["unit_id"]: unit for unit in units}
    targets = refs.unit_map(review.source_units(pages, candidate=candidate), "T")
    page_map = {page.page_number: page for page in pages}
    visuals = {row["page"]: row["status"] for row in inventory["page_visual_coverage"]}
    images = {}
    for row in affected:
        claim = claims[row["claim_id"]]
        owned = claim["source_unit_ids"]
        selected = review._ids(row["target_unit_ids"], targets)
        if not owned or {targets[key]["page"] for key in selected} != review._claim_owner_pages(claim, originals):
            return False
        for key in owned:
            if not any(span["kind"] == "text" and span["quote"].strip() and review._overlaps(originals[key], span)
                       for span in claim["source_evidence"]):
                return False
        for number in review._claim_owner_pages(claim, originals):
            if number not in images:
                images[number] = _image(page_map[number].image_data_url)
            if not images[number] or visuals.get(number) != "reviewed":
                return False
    return True
