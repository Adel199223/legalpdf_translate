"""Pure, source-bound inter-block gap recommendations for editable Word output.

Bounding boxes establish approximate *inter-block* whitespace, not baseline or
line-height metrics. This helper never infers leading from text/newline counts,
alters text, crosses a page, or dictates Word pagination/header reservations.
The writer owns readable line-spacing defaults and rendered acceptance.
"""
from __future__ import annotations

from collections.abc import Collection
import hashlib
import json
import re
from typing import Any

from .document_structure import validate_page_structure


DOCUMENT_SPACING_VERSION = "source_block_spacing_v2"
MAX_SPACING_BLOCKS = 512
_BODY = frozenset({"paragraph", "list_item", "heading", "reference", "signature"})
_TIGHT = frozenset({"header", "address", "footer"})
_GEOMETRY_KEYS = ("id", "role", "bbox", "table_id", "row", "col", "alignment", "uncertain", "document_start")
_ASTERISK_SEPARATOR = re.compile(r"[ \t]*\*(?:[ \t]*\*){0,7}[ \t]*")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _result(status: str = "unavailable", warning: str | None = None) -> dict[str, Any]:
    return {"version": DOCUMENT_SPACING_VERSION, "status": status, "overrides": {}, "skipped": [],
            "warnings": [warning] if warning else [], "line_height_evidence": "unavailable"}


def _bound_pages(source_page: dict, translated_page: dict):
    source = validate_page_structure(source_page).to_dict()
    target = validate_page_structure(translated_page).to_dict()
    if (not source["source_file_sha256"] or source["uncertain"] or target["uncertain"]
            or len(source["blocks"]) > MAX_SPACING_BLOCKS
            or source["source_sha256"] != source["source_text_sha256"]
            or source["source_sha256"] != _hash("\n".join(row["text"] for row in source["blocks"]))
            or target["translation_sha256"] != _hash("\n".join(row["text"] for row in target["blocks"]))):
        return None
    page_keys = ("page_number", "width_pt", "height_pt", "source_file_sha256", "source_sha256",
                 "source_text_sha256", "uncertain", "document_start")
    if any(source[key] != target[key] for key in page_keys) or len(source["blocks"]) != len(target["blocks"]):
        return None
    if any(any(a[key] != b[key] for key in _GEOMETRY_KEYS) for a, b in zip(source["blocks"], target["blocks"])):
        return None
    if any(a["text"].strip() and not b["text"].strip() for a, b in zip(source["blocks"], target["blocks"])):
        return None
    return source, target


def _box(block: dict, page: dict):
    box = block["bbox"]
    if (box is None or not 0 <= box[0] < box[2] <= page["width_pt"]
            or not 0 <= box[1] < box[3] <= page["height_pt"]
            or box[3] - box[1] > page["height_pt"] * .7):
        return None
    return box


def _region_ids(page: dict) -> set[str]:
    layout = page.get("metadata", {}).get("layout")
    if layout is None:
        return set()
    if not isinstance(layout, dict) or layout.get("status") not in {"regions", "flow"} or layout.get("review_required", False):
        raise ValueError("Source spacing requires certain layout metadata")
    if layout["status"] == "flow":
        if layout.get("bands"):
            raise ValueError("Flow layout cannot contain regions")
        return set()
    bands = layout["bands"]
    known = {row["id"] for row in page["blocks"]}
    if not isinstance(bands, list) or not 1 <= len(bands) <= 32:
        raise ValueError("Invalid spacing exclusion bands")
    identities = set()
    for band in bands:
        regions = band["regions"]
        if not isinstance(regions, list) or not 1 <= len(regions) <= 64:
            raise ValueError("Invalid spacing exclusion regions")
        for region in regions:
            members = region["block_ids"]
            if (not isinstance(members, list) or not 1 <= len(members) <= MAX_SPACING_BLOCKS
                    or any(not isinstance(identity, str) or identity not in known for identity in members)):
                raise ValueError("Invalid spacing exclusion identities")
            identities.update(members)
    return identities


def _has_parallel_columns(blocks: list[dict], boxes: dict, excluded: set[str]) -> bool:
    candidates = [row for row in blocks if row["id"] not in excluded and boxes[row["id"]]
                  and row["role"] != "table_cell" and row["text"].strip()]
    candidates.sort(key=lambda row: boxes[row["id"]][1])
    for index, row in enumerate(candidates):
        a = boxes[row["id"]]
        for other in candidates[index + 1:]:
            b = boxes[other["id"]]
            if b[1] >= a[3]:
                break
            overlap = min(a[3], b[3]) - b[1]
            if overlap > min(a[3] - a[1], b[3] - b[1]) * .25 and (b[0] - a[2] >= 6 or a[0] - b[2] >= 6):
                return True
    return False


def _same_flow(a: dict, b: dict, first: list, second: list, width: float) -> bool:
    overlap = min(first[2], second[2]) - max(first[0], second[0])
    minimum_width = min(first[2] - first[0], second[2] - second[0])
    if overlap < minimum_width * .6:
        return False
    edge_tolerance = min(24.0, width * .04)
    if abs(first[0] - second[0]) <= edge_tolerance or abs(first[2] - second[2]) <= edge_tolerance:
        return True
    # A centered heading/separator can share a full-width flow. This is not
    # permission to infer gaps between separate physical columns or regions.
    centered = a["alignment"] == "center" or b["alignment"] == "center"
    return centered and abs((first[0] + first[2]) - (second[0] + second[2])) / 2 <= edge_tolerance


def _exact_decorative_separator(source: dict, target: dict) -> bool:
    # Only a complete, source-classified reference separator is decorative.
    # Asterisk list markers, semantic headings, altered target punctuation and
    # multiline text never authorize this narrower formatting cap.
    text = source["text"]
    return (source["role"] == target["role"] == "reference"
            and text == target["text"] and len(text) <= 32
            and _ASTERISK_SEPARATOR.fullmatch(text) is not None)


def infer_page_spacing(*, source_page: dict, translated_page: dict,
                       excluded_block_ids: Collection[str] = ()) -> dict[str, Any]:
    """Recommend bounded total gaps for adjacent, fully bound source blocks.

    ``overrides[id].desired_gap_pt`` is a total inter-paragraph recommendation,
    not extra space to add on top of existing paragraph margins. The writer
    must account for its existing before/after spacing and Word layout. It is
    approximate source geometry, not guaranteed glyph-to-glyph equality.
    Excluded/adopted furniture and region IDs break adjacency; no bridge is
    synthesized. The language-neutral recommendations never infer line height.
    """
    try:
        bound = _bound_pages(source_page, translated_page)
        if bound is None:
            return _result(warning="source_spacing_binding_unavailable")
        source, target = bound
        if isinstance(excluded_block_ids, (str, bytes)) or len(excluded_block_ids) > MAX_SPACING_BLOCKS:
            return _result(warning="source_spacing_invalid_exclusions")
        excluded = set(excluded_block_ids)
        known = {row["id"] for row in source["blocks"]}
        if any(not isinstance(identity, str) or identity not in known for identity in excluded):
            return _result(warning="source_spacing_invalid_exclusions")
        excluded |= _region_ids(source) | _region_ids(target)
    except (ValueError, TypeError, KeyError, AttributeError):
        return _result(warning="source_spacing_binding_unavailable")
    result = _result("source_bound")
    result["page_number"] = source["page_number"]
    result["source_sha256"] = source["source_sha256"]
    result["translation_sha256"] = target["translation_sha256"]
    geometry = [{key: row[key] for key in _GEOMETRY_KEYS} for row in source["blocks"]]
    result["geometry_sha256"] = _hash(json.dumps(geometry, sort_keys=True, separators=(",", ":"), allow_nan=False))
    blocks = source["blocks"]
    decorative_ids = {row["id"] for row, translated in zip(blocks, target["blocks"])
                      if _exact_decorative_separator(row, translated)}
    boxes = {row["id"]: _box(row, source) for row in blocks}
    parallel = _has_parallel_columns(blocks, boxes, excluded)
    body_ids = [row["id"] for row in blocks if row["role"] in _BODY]
    continued = {row["id"] for page in (source, target) for row in page["blocks"] if row["continuation_of"]}
    if body_ids and (source["continuation_from_previous"] or target["continuation_from_previous"]):
        continued.add(body_ids[0])
    if body_ids and (source["continuation_to_next"] or target["continuation_to_next"]):
        continued.add(body_ids[-1])
    for previous, current in zip(blocks, blocks[1:]):
        identity = current["id"]
        first, second = boxes[previous["id"]], boxes[identity]
        reason = None
        if identity in excluded or previous["id"] in excluded:
            reason = "excluded_or_region_boundary"
        elif parallel:
            reason = "parallel_columns"
        elif previous["uncertain"] or current["uncertain"]:
            reason = "uncertain_block"
        elif previous["role"] == "table_cell" or current["role"] == "table_cell":
            reason = "table_boundary"
        elif current["document_start"]:
            reason = "document_boundary"
        elif identity in continued or previous["id"] in continued:
            reason = "continuation_boundary"
        elif not previous["text"].strip() or not current["text"].strip():
            reason = "empty_block_boundary"
        elif first is None or second is None:
            reason = "geometry_unavailable"
        elif second[1] < first[3]:
            reason = "overlapping_geometry"
        elif not _same_flow(previous, current, first, second, source["width_pt"]):
            reason = "different_horizontal_flow"
        elif second[1] - first[3] > min(72.0, source["height_pt"] * .1):
            reason = "oversized_source_gap"
        elif previous["role"] == "footer" or current["role"] == "footer":
            if previous["role"] != current["role"]:
                reason = "footer_reservation_not_paragraph_spacing"
        if reason:
            result["skipped"].append({"block_id": identity, "code": reason})
            continue
        raw_gap = second[1] - first[3]
        if previous["role"] == current["role"] and current["role"] in _TIGHT:
            cap, basis = 3.0, "tight_furniture_group"
        elif {previous["role"], current["role"]} == {"header", "address"}:
            cap, basis = 18.0, "source_group_boundary_gap"
        elif previous["role"] in {"header", "address"} and current["role"] in _BODY:
            cap, basis = 24.0, "source_header_body_gap"
        elif previous["role"] in _BODY and current["role"] in _BODY:
            if previous["id"] in decorative_ids or identity in decorative_ids:
                cap, basis = 12.0, "source_decorative_separator_gap"
            else:
                cap, basis = 18.0, "source_same_flow_gap"
        else:
            result["skipped"].append({"block_id": identity, "code": "unsupported_role_transition"})
            continue
        result["overrides"][identity] = {
            "previous_block_id": previous["id"], "source_gap_pt": round(raw_gap, 3),
            "desired_gap_pt": round(min(raw_gap, cap) * 2) / 2,
            "basis": basis, "clamped": raw_gap > cap,
        }
    return result
