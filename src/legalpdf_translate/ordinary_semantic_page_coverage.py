"""Fresh-only complete selected-page correction request contract.

The legacy instruction/schema constants and deterministic validators are unchanged.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json

POLICY = "complete_selected_pages_v1"
KEY = "semantic_page_coverage_policy"
OLD_SENTENCE = ("Return exactly one page in source\n"
                "order and one claim_coverage entry per inventory claim; unresolved blocks publication.")
NEW_SENTENCE = ("Return exactly one pages entry for EVERY selected source page, including no-change pages, "
                "in the exact selected source-page order. The pages array must contain ALL selected pages "
                "exactly once, with their original page_number identities; never return only corrected pages "
                "or a single page from a multi-page selection. Return one claim_coverage entry per inventory "
                "claim; unresolved blocks publication.")


def check_policy(policy, unit_reference_policy):
    if (type(policy) is not str or policy != POLICY
            or unit_reference_policy != "caller_unit_refs_v1"):
        raise ValueError("Invalid complete-page policy.")


def _constraints(page_numbers):
    if (not 1 <= len(page_numbers) <= 12 or any(type(n) is not int or n < 1 for n in page_numbers)
            or list(page_numbers) != sorted(set(page_numbers))):
        raise ValueError("Invalid complete-page selection.")
    return {"minItems": len(page_numbers), "maxItems": len(page_numbers),
            "page_number": {"type": "integer", "enum": list(page_numbers)}}


def descriptor(page_numbers):
    return {"policy": POLICY,
            "replaced_instruction_sha256": hashlib.sha256(OLD_SENTENCE.encode()).hexdigest(),
            "replacement_instruction_sha256": hashlib.sha256(NEW_SENTENCE.encode()).hexdigest(),
            "correction_pages_constraints": _constraints(page_numbers)}


def adapt_request(request, stage, page_numbers, *, encode_payload):
    """Only correction instructions/schema change; every request binds the policy."""
    payload = json.loads(request["prompt_text"])
    if (stage not in ("source_inventory", "correction", "verification")
            or payload.get("stage") != stage
            or payload.get("semantic_unit_reference_policy") != "caller_unit_refs_v1"
            or [p["page"] for p in payload["source_pages"]] != list(page_numbers)
            or KEY in payload):
        raise ValueError("Invalid complete-page request.")
    policy = descriptor(page_numbers)
    payload[KEY] = policy
    result = {**request, "prompt_text": encode_payload(payload)}
    if stage == "correction":
        if request["instructions"].count(OLD_SENTENCE) != 1:
            raise ValueError("Unexpected legacy complete-page instruction.")
        result["instructions"] = request["instructions"].replace(OLD_SENTENCE, NEW_SENTENCE)
        form = deepcopy(request["response_format"])
        pages = form["schema"]["properties"]["pages"]
        if (pages.get("type") != "array"
                or pages["items"]["properties"]["page_number"] != {"type": "integer"}
                or "minItems" in pages or "maxItems" in pages):
            raise ValueError("Unexpected legacy complete-page schema.")
        constraints = policy["correction_pages_constraints"]
        pages.update({key: constraints[key] for key in ("minItems", "maxItems")})
        pages["items"]["properties"]["page_number"] = deepcopy(constraints["page_number"])
        result["response_format"] = form
    return result
