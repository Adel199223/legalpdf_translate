"""Pure validation of explicit, text-free editable source-region declarations.

The returned canonical JSON bytes describe only the requested containers and
fragment ownership. They are not geometry measurement, source verification or
review authority. The caller must bind each fragment to the unchanged source
image, complete source/target text ranges and committed translation evidence.
No layout is inferred and no source or target content is created or rewritten.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import json
import math
import re


VERSION = "reviewed_region_layout_v1"
GUTTER_VERSION = "reviewed_region_layout_v2"
GUTTER_POLICY = "explicit_source_supported_column_gaps_v1"
MAX_FRAGMENTS = 5000
MAX_TABLES = 100
MAX_ROWS = 100
MAX_COLUMNS = 4
MAX_IMAGE_PIXELS = 40_000_000
MAX_PAGE_NUMBER = 999_999
_ROLES = frozenset({"header", "body", "signature", "footer", "folio"})
_FRAGMENT_ID = re.compile(r"p([0-9]{4,6})_f([0-9]{4,6})\Z", re.ASCII)


class ReviewedRegionsError(ValueError):
    """Content-free validation category; never include caller data."""


@dataclass(frozen=True, slots=True)
class RegionFragmentInput:
    rendering_id: str
    role: str
    bbox_px: tuple[float, float, float, float]


def _fail(code: str) -> None:
    raise ReviewedRegionsError(code)


def _keys(value: object, expected: set[str]) -> dict:
    if type(value) is not dict or set(value) != expected:
        _fail("region_invalid_schema")
    return value


def _list(value: object, *, maximum: int, nonempty: bool = False) -> list:
    if type(value) is not list or len(value) > maximum or (nonempty and not value):
        _fail("region_invalid_list")
    return value


def _box(value: object, image_size: tuple[int, int]) -> tuple[float, float, float, float]:
    if (type(value) is not tuple or len(value) != 4
            or any(type(number) not in (int, float) for number in value)):
        _fail("region_invalid_box")
    # Compare integers before converting them: enormous caller integers must
    # produce the same bounded error rather than an OverflowError from float.
    width, height = image_size
    if (not all(0 <= number <= (width if index % 2 == 0 else height)
                for index, number in enumerate(value))
            or not value[0] < value[2] or not value[1] < value[3]):
        _fail("region_invalid_box")
    result = tuple(float(number) for number in value)
    if not all(math.isfinite(number) for number in result):
        _fail("region_invalid_box")
    return result


def _union(boxes: Sequence[tuple]) -> tuple[float, float, float, float] | None:
    if not boxes:
        return None
    return (min(box[0] for box in boxes), min(box[1] for box in boxes),
            max(box[2] for box in boxes), max(box[3] for box in boxes))


def _after(previous: tuple | None, current: tuple | None) -> None:
    if previous is not None and current is not None and current[1] < previous[3]:
        _fail("region_vertical_overlap_or_order")


def validate_reviewed_regions(layout: dict, *, fragments: Sequence[RegionFragmentInput],
                              page_number: int, image_size_px: tuple[int, int]) -> bytes:
    """Return canonical immutable JSON bytes of the exact validated layout.

    Inputs are materialized lists/tuples of frozen fragment records, in their
    original consecutive rendering-ID order. Table traversal may interleave
    these IDs across columns within a row; each individual cell must retain
    increasing source ID order and vertically disjoint boxes. Rows and body
    blocks retain noninterleaving source-rank ranges. Widths are explicit positive
    integer percentages, not inferred measurements. Empty structural cells are
    retained, but there is no empty row/table, spanning cell or nested table.
    The function performs no I/O and never modifies its arguments.
    """
    if type(page_number) is not int or not 1 <= page_number <= MAX_PAGE_NUMBER:
        _fail("region_invalid_page")
    if (type(image_size_px) is not tuple or len(image_size_px) != 2
            or any(type(number) is not int or not 0 < number <= MAX_IMAGE_PIXELS
                   for number in image_size_px)
            or image_size_px[0] * image_size_px[1] > MAX_IMAGE_PIXELS):
        _fail("region_invalid_image_frame")
    if type(fragments) not in (list, tuple) or not 0 < len(fragments) <= MAX_FRAGMENTS:
        _fail("region_invalid_fragments")
    records, boxes, ranks = {}, {}, {}
    for rank, fragment in enumerate(fragments, 1):
        if type(fragment) is not RegionFragmentInput:
            _fail("region_invalid_fragment")
        identifier = fragment.rendering_id
        if (type(identifier) is not str or not _FRAGMENT_ID.fullmatch(identifier)
                or identifier != f"p{page_number:04d}_f{rank:04d}"
                or type(fragment.role) is not str or fragment.role not in _ROLES):
            _fail("region_invalid_fragment_identity")
        records[identifier] = fragment
        boxes[identifier] = _box(fragment.bbox_px, image_size_px)
        ranks[identifier] = rank

    if type(layout) is not dict or type(layout.get("version")) is not str:
        _fail("region_invalid_schema")
    gutters = layout["version"] == GUTTER_VERSION
    root = _keys(layout, {"version", "header", "body", "footer"}
                 | ({"gutter_policy"} if gutters else set()))
    if root["version"] not in {VERSION, GUTTER_VERSION}:
        _fail("region_unsupported_version")
    if gutters and root["gutter_policy"] != GUTTER_POLICY:
        _fail("region_unsupported_gutter_policy")
    seen: set[str] = set()

    def consume(value: object, roles: set[str], *, footer: bool = False,
                top_header: bool = False) -> tuple[list[str], tuple | None]:
        identifiers = _list(value, maximum=MAX_FRAGMENTS)
        owned, prior = [], []
        last_rank = 0
        for identifier in identifiers:
            if type(identifier) is not str or identifier not in records or identifier in seen:
                _fail("region_missing_or_duplicate_owner")
            row, box = records[identifier], boxes[identifier]
            if row.role not in roles:
                _fail("region_role_container_mismatch")
            if top_header and row.role == "header" and box[3] > image_size_px[1] * .25:
                _fail("region_body_header_not_at_top")
            if ranks[identifier] <= last_rank:
                _fail("region_fragment_source_order")
            last_rank = ranks[identifier]
            for old_id in prior:
                old_box = boxes[old_id]
                if box[1] >= old_box[3]:
                    continue
                # Contact furniture and a literal folio may share the bottom
                # band. This is not authority for overlapping ink, two contact
                # columns, reordered separate bands or a folio in the body.
                same_band = bool(footer and {row.role, records[old_id].role} == {"footer", "folio"}
                    and box[3] > old_box[1]
                    and (box[0] >= old_box[2] or box[2] <= old_box[0]))
                if not same_band:
                    _fail("region_vertical_overlap_or_order")
            seen.add(identifier)
            prior.append(identifier)
            owned.append(identifier)
        return owned, _union([boxes[identifier] for identifier in owned])

    header, header_box = consume(root["header"], {"header"})
    body_input = _list(root["body"], maximum=MAX_FRAGMENTS)
    body, body_boxes, table_count, previous_body_rank = [], [], 0, 0
    first_body_rank = None
    for block_index, block in enumerate(body_input):
        if type(block) is not dict:
            _fail("region_invalid_schema")
        kind = block.get("kind")
        if type(kind) is not str:
            _fail("region_unsupported_body_kind")
        if kind == "paragraph":
            _keys(block, {"kind", "fragment_id"})
            ids, block_box = consume([block["fragment_id"]], {"body", "signature"})
            block_ranks = [ranks[ids[0]]]
            canonical_block = {"kind": "paragraph", "fragment_id": ids[0]}
        elif kind == "table":
            _keys(block, {"kind", "table_id", "column_widths", "rows"}
                  | ({"column_gaps_px"} if gutters else set()))
            table_count += 1
            if (table_count > MAX_TABLES or type(block["table_id"]) is not str
                    or block["table_id"] != f"p{page_number:04d}_t{table_count:04d}"):
                _fail("region_invalid_table_identity")
            widths = _list(block["column_widths"], maximum=MAX_COLUMNS, nonempty=True)
            if any(type(width) is not int or not 0 < width <= 100 for width in widths) or sum(widths) != 100:
                _fail("region_invalid_column_widths")
            gaps = _list(block["column_gaps_px"], maximum=MAX_COLUMNS - 1) if gutters else []
            if gutters and (len(gaps) != len(widths) - 1
                    or any(type(gap) not in (int, float) or not 0 <= gap <= image_size_px[0]
                           or not math.isfinite(gap) for gap in gaps)):
                _fail("region_invalid_column_gaps")
            gap_support = [[] for _ in gaps]
            rows_input = _list(block["rows"], maximum=MAX_ROWS, nonempty=True)
            rows, row_boxes, block_ranks, previous_row_rank = [], [], [], 0
            for row_index, row in enumerate(rows_input):
                _keys(row, {"cells"})
                cells_input = _list(row["cells"], maximum=MAX_COLUMNS, nonempty=True)
                if len(cells_input) != len(widths):
                    _fail("region_nonrectangular_table")
                cells, cell_boxes, row_ranks, physical_cell_boxes = [], [], [], []
                for cell in cells_input:
                    _keys(cell, {"fragment_ids"})
                    roles = {"body", "signature"}
                    if block_index == 0 and table_count == 1 and row_index == 0:
                        roles.add("header")
                    ids, cell_box = consume(cell["fragment_ids"], roles, top_header=True)
                    physical_cell_boxes.append(cell_box)
                    row_ranks.extend(ranks[identifier] for identifier in ids)
                    cells.append({"fragment_ids": ids})
                    if cell_box is not None:
                        if cell_boxes and cell_box[0] < cell_boxes[-1][2]:
                            _fail("region_column_overlap_or_order")
                        cell_boxes.append(cell_box)
                if gutters:
                    for column, (left, right) in enumerate(zip(physical_cell_boxes, physical_cell_boxes[1:])):
                        if left is not None and right is not None:
                            gap_support[column].append(right[0] - left[2])
                row_box = _union(cell_boxes)
                if row_box is None:
                    _fail("region_empty_table_row")
                if min(row_ranks) <= previous_row_rank:
                    _fail("region_table_row_source_order")
                previous_row_rank = max(row_ranks)
                block_ranks.extend(row_ranks)
                _after(row_boxes[-1] if row_boxes else None, row_box)
                row_boxes.append(row_box)
                rows.append({"cells": cells})
            block_box = _union(row_boxes)
            canonical_block = {"kind": "table", "table_id": block["table_id"],
                               "column_widths": list(widths), "rows": rows}
            if gutters:
                for gap, observed in zip(gaps, gap_support):
                    if gap > 0 and (not observed or gap > min(observed)):
                        _fail("region_unsupported_column_gap")
                canonical_block["column_gaps_px"] = list(gaps)
        else:
            _fail("region_unsupported_body_kind")
        if min(block_ranks) <= previous_body_rank:
            _fail("region_body_source_order")
        if first_body_rank is None:
            first_body_rank = min(block_ranks)
        previous_body_rank = max(block_ranks)
        _after(body_boxes[-1] if body_boxes else None, block_box)
        body_boxes.append(block_box)
        body.append(canonical_block)
    footer, footer_box = consume(root["footer"], {"footer", "folio"}, footer=True)
    # Ordered boxes do not authorize moving immutable source text between
    # furniture and body containers. A header inside the first table already
    # belongs to that body's checked rank interval, not to this header list.
    header_last_rank = ranks[header[-1]] if header else 0
    if (first_body_rank is not None and first_body_rank <= header_last_rank
            or footer and ranks[footer[0]] <= max(header_last_rank, previous_body_rank)):
        _fail("region_container_source_order")
    body_box = _union(body_boxes)
    _after(header_box, body_box)
    _after(body_box if body_box is not None else header_box, footer_box)
    if seen != set(records):
        _fail("region_incomplete_fragment_coverage")
    canonical = {"version": root["version"], "header": header, "body": body, "footer": footer}
    if gutters:
        canonical["gutter_policy"] = GUTTER_POLICY
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")
