"""Conservative source proof for compact list reflow, never sentence joining.

The writer must first bind these full source pages to the saved translations.
This local proof changes neither translation inputs nor continuation flags.
"""
from __future__ import annotations

import re
from typing import Any

from .formatting_support import _contact_furniture, _furniture_geometry, _same_furniture, digest_text

_MARKER = re.compile(r"^\s*(?:(?P<number>[0-9]{1,4})(?P<number_end>[.)])|"
                     r"(?P<letter>[A-Za-z])(?P<letter_end>[.)])|(?P<bullet>[-•]))(?=\s)")


def _edges(page: dict) -> tuple[list[dict], list[dict], list[dict]]:
    blocks = page["blocks"]
    start, end = 0, len(blocks)
    while start < end and blocks[start]["role"] in {"header", "address"}:
        start += 1
    while end > start and blocks[end - 1]["role"] in {"footer", "address"}:
        end -= 1
    return blocks[:start], blocks[start:end], blocks[end:]


def potential_list_furniture_boundary(previous: dict, current: dict) -> bool:
    """A hint for review reporting only; never permission to move a paragraph."""
    _, left, trailing = _edges(previous)
    leading, right, _ = _edges(current)
    return bool(left and right and trailing and leading and right[0]["role"] == "list_item"
                and (left[-1]["role"] == "list_item" or
                     (left[-1]["role"] == "paragraph" and left[-1]["text"].rstrip().endswith(":"))))


def _marker(block: dict) -> tuple[str, str, int | str] | None:
    match = _MARKER.match(block["text"])
    if not match:
        return None
    if match["number"]:
        return "number", match["number_end"], int(match["number"])
    if match["letter"]:
        return "letter", match["letter_end"], ord(match["letter"])
    return "bullet", match["bullet"], match["bullet"]


def _next_marker(first: tuple, second: tuple) -> bool:
    return first[:2] == second[:2] and (first[0] == "bullet" or second[2] == first[2] + 1)


def confirmed_list_furniture_reflow(previous: dict, current: dict) -> dict[str, Any] | None:
    """Move a leading list group before exact, source-evidenced page furniture.

    List items remain separate, even when the preceding item ends mid-sentence.
    A heading/reference/signature/table or a numbering reset never proves a list
    continuation. All furniture occurrences, including translation variants,
    remain editable body text after the group.
    """
    if (previous["page_number"] + 1 != current["page_number"] or current.get("document_start")
            or previous.get("uncertain") or current.get("uncertain")
            or not previous.get("source_file_sha256")
            or previous["source_file_sha256"] != current.get("source_file_sha256")
            or any(abs(previous[key] - current[key]) > 1 for key in ("width_pt", "height_pt"))
            or any(block.get("document_start") for block in current["blocks"])
            or any(block.get("document_start") for block in previous["blocks"][1:])
            or not potential_list_furniture_boundary(previous, current)):
        return None
    ids = [block["id"] for page in (previous, current) for block in page["blocks"]]
    if len(ids) != len(set(ids)):
        return None
    _, left, trailing = _edges(previous)
    leading, right, current_footer = _edges(current)
    tail, head = left[-1], right[0]
    group = []
    for block in right:
        if block["role"] != "list_item":
            break
        group.append(block)
    if (not group or len(group) > 64 or any(not block["text"].strip() or block.get("uncertain")
            or block.get("table_id") or not block.get("bbox") for block in [tail, *group])
            or tail["bbox"][3] < previous["height_pt"] * 0.72
            or head["bbox"][1] > current["height_pt"] * 0.32):
        return None
    markers = [_marker(block) for block in group]
    if any(marker is None for marker in markers) or any(not _next_marker(a, b) for a, b in zip(markers, markers[1:])):
        return None
    if tail["role"] == "list_item":
        preceding = _marker(tail)
        if preceding is None or not _next_marker(preceding, markers[0]):
            return None
        kind = "continued_list"
    else:
        if len(tail["text"].strip()) < 20 or not tail["text"].rstrip().endswith(":"):
            return None
        first = markers[0]
        if (first[0] == "number" and first[2] != 1) or (first[0] == "letter" and first[2] not in {ord("a"), ord("A")}):
            return None
        kind = "introduced_list"
    # Only complete repeated top furniture and short bottom contact lines are
    # movable; role names alone cannot authorize moving a legal footer.
    witnesses = [block for block in previous["blocks"]
                 if block["role"] in {"header", "address"} and _furniture_geometry(block, previous, top=True)]
    if (not 1 <= len(leading) <= 4 or not 1 <= len(trailing) <= 4
            or any(not block["text"].strip() or not _furniture_geometry(block, current, top=True) for block in leading)
            or any(not block["text"].strip() or not _furniture_geometry(block, previous, top=False) for block in trailing)
            or any(not block["text"].strip() or not _furniture_geometry(block, current, top=False) for block in current_footer)
            or not _same_furniture(witnesses, leading, previous, current)
            or not _contact_furniture(trailing) or not _contact_furniture(current_footer)
            or not _same_furniture(trailing, current_footer, previous, current)):
        return None
    pairs = [*zip(witnesses, leading), *zip(trailing, current_footer)]
    return {"version": 1, "kind": kind, "previous_page": previous["page_number"],
            "current_page": current["page_number"], "source_file_sha256": previous["source_file_sha256"],
            "previous_source_sha256": previous["source_sha256"], "current_source_sha256": current["source_sha256"],
            "previous_tail_id": tail["id"], "current_list_ids": [block["id"] for block in group],
            "previous_trailing_ids": [block["id"] for block in trailing],
            "current_leading_ids": [block["id"] for block in leading],
            "furniture_pairs": [{"previous_id": a["id"], "current_id": b["id"],
                                 "source_text_sha256": digest_text(a["text"].strip())} for a, b in pairs]}
