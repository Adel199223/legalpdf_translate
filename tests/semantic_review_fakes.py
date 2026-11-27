"""Structural fake responses for the three review schemas; no semantic oracle."""


VERSIONS = {
    "source_inventory": "ordinary_source_inventory_v1",
    "correction": "ordinary_source_correction_v1",
    "verification": "ordinary_source_verification_v1",
}
UNIT_REF_VERSIONS = {
    "source_inventory": "ordinary_source_inventory_unit_refs_v1",
    "correction": "ordinary_source_correction_unit_refs_v1",
    "verification": "ordinary_source_verification_unit_refs_v1",
}
ALL_FORMAT_NAMES = set(VERSIONS.values()) | set(UNIT_REF_VERSIONS.values())


def _canonical_response(payload, *, corrected_by_page=None):
    stage = payload["stage"]
    if stage == "source_inventory":
        claims, coverage = [], []
        for index, unit in enumerate(payload["source_units"], 1):
            key = f"claim_{index}"
            claims.append({"claim_id": key, "source_unit_ids": [unit["unit_id"]],
                "source_evidence": [{"kind": "text", **{k: unit[k] for k in ("page", "start", "end")},
                    "quote": unit["text"]}], "proposition": unit["text"],
                "axes": {"actor_recipient": "fictional parties", "polarity_modality": "assertion",
                    "temporal_state": "completed", "participant_number": "one", "conditions": ""},
                "unresolved": False})
            coverage.append({"unit_id": unit["unit_id"], "claim_ids": [key]})
        for page in payload["source_pages"]:
            if not any(c["source_evidence"][0]["page"] == page["page"] for c in claims):
                claims.append({"claim_id": f"image_{page['page']}", "source_unit_ids": [],
                    "source_evidence": [{"kind": "image", "page": page["page"], "bbox": [.1, .1, .9, .9]}],
                    "proposition": "A fictional visible notice.",
                    "axes": {"actor_recipient": "fictional parties", "polarity_modality": "assertion",
                        "temporal_state": "completed", "participant_number": "one", "conditions": ""},
                    "unresolved": False})
        return {"version": VERSIONS[stage], "claims": claims, "unit_coverage": coverage,
            "boundaries": [{"left_page": a["page"], "right_page": b["page"], "relation": "separate",
                "claim_ids": [c["claim_id"] for c in claims
                              if c["source_evidence"][0]["page"] in {a["page"], b["page"]}]}
                for a, b in zip(payload["source_pages"], payload["source_pages"][1:])],
            "page_visual_coverage": [{"page": p["page"], "status":
                "reviewed" if p["image_position"] is not None else "text_only"} for p in payload["source_pages"]]}
    if stage == "correction":
        corrections = corrected_by_page or {}
        return {"version": VERSIONS[stage], "pages": [{"page_number": p["page"],
            "status": "corrected" if p["page"] in corrections else "no_change",
            "corrected_text": corrections.get(p["page"], ""),
            "reason_codes": ["actor_recipient"] if p["page"] in corrections else []}
            for p in payload["primary_pages"]],
            "claim_coverage": [{"claim_id": c["claim_id"], "status": "preserved"}
                               for c in payload["source_inventory"]["claims"]]}
    if stage == "verification":
        results, inverse = [], {u["unit_id"]: [] for u in payload["target_units"]}
        source_pages = {unit["unit_id"]: unit["page"] for unit in payload["source_units"]}
        for claim in payload["source_inventory"]["claims"]:
            pages = ({source_pages[key] for key in claim["source_unit_ids"]} if claim["source_unit_ids"] else
                {span["page"] for span in claim["source_evidence"] if span["kind"] == "image"})
            spans = []
            for unit in payload["target_units"]:
                if unit["page"] in pages:
                    spans.append({**{k: unit[k] for k in ("page", "start", "end")}, "quote": unit["text"]})
                    inverse[unit["unit_id"]].append(claim["claim_id"])
            results.append({"claim_id": claim["claim_id"], "status": "equivalent", "target_spans": spans})
        return {"version": VERSIONS[stage], "claim_results": results,
            "target_unit_coverage": [{"unit_id": key, "claim_ids": claims} for key, claims in inverse.items()],
            "boundary_results": [{"left_page": b["left_page"], "right_page": b["right_page"],
                                  "status": "equivalent"} for b in payload["source_inventory"]["boundaries"]],
            "inventory_errors": [], "unsupported_additions": []}
    raise AssertionError("Unexpected fictional review stage")


def review_response(payload, *, corrected_by_page=None, unit_references=False):
    """Generate structural coverage from caller units, never a semantic oracle."""
    value = _canonical_response(payload, corrected_by_page=corrected_by_page)
    if not unit_references:
        return value
    stage = payload["stage"]
    value["version"] = UNIT_REF_VERSIONS[stage]
    if stage == "source_inventory":
        value.pop("unit_coverage")
        for claim in value["claims"]:
            evidence = claim.pop("source_evidence")
            claim["context_unit_ids"] = []
            claim["source_image_evidence"] = [item for item in evidence if item["kind"] == "image"]
    elif stage == "verification":
        ids = {(u["page"], u["start"], u["end"], u["text"]): u["unit_id"] for u in payload["target_units"]}
        value.pop("target_unit_coverage")
        for result in value["claim_results"]:
            result["target_unit_ids"] = [ids[(s["page"], s["start"], s["end"], s["quote"])]
                for s in result.pop("target_spans")]
    return value
