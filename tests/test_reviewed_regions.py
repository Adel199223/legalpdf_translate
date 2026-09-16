"""Synthetic, text-free region declarations; no document or provider runtime."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json

import pytest

from legalpdf_translate.reviewed_regions import (
    RegionFragmentInput, ReviewedRegionsError, validate_reviewed_regions,
)


def fid(number, page=1):
    return f"p{page:04d}_f{number:04d}"


def fragment(number, role, box, page=1):
    return RegionFragmentInput(fid(number, page), role, tuple(box))


def table(cells, *, widths=None, number=1, page=1):
    return {"kind": "table", "table_id": f"p{page:04d}_t{number:04d}",
            "column_widths": widths or [100 // len(cells)] * len(cells),
            "rows": [{"cells": [{"fragment_ids": ids} for ids in cells]}]}


def packet():
    fragments = [
        fragment(1, "header", (50, 10, 950, 40)),
        fragment(2, "body", (50, 100, 400, 120)),
        fragment(3, "body", (500, 100, 950, 120)),
        fragment(4, "body", (50, 130, 400, 150)),
        fragment(5, "body", (500, 130, 950, 150)),
        fragment(6, "signature", (500, 300, 950, 330)),
        fragment(7, "footer", (50, 900, 700, 940)),
        fragment(8, "folio", (800, 910, 950, 940)),
    ]
    layout = {"version": "reviewed_region_layout_v1", "header": [fid(1)],
              "body": [table([[fid(2), fid(4)], [fid(3), fid(5)]], widths=[40, 60]),
                       {"kind": "paragraph", "fragment_id": fid(6)}],
              "footer": [fid(7), fid(8)]}
    return layout, fragments


def validate(layout, fragments, *, page=1, size=(1000, 1000)):
    return validate_reviewed_regions(layout, fragments=fragments,
                                     page_number=page, image_size_px=size)


def assert_rejected(layout, fragments, **kwargs):
    with pytest.raises(ReviewedRegionsError) as error:
        validate(layout, fragments, **kwargs)
    assert str(error.value).startswith("region_")
    assert str(error.value).isascii()
    assert " " not in str(error.value)


def test_canonical_immutable_descriptor_preserves_declared_columns_and_input():
    layout, fragments = packet()
    before = deepcopy((layout, fragments))
    result = validate(layout, fragments)
    assert type(result) is bytes
    assert result == json.dumps(layout, sort_keys=True, separators=(",", ":")).encode()
    assert json.loads(result) == layout
    assert (layout, fragments) == before
    assert validate(dict(reversed(list(layout.items()))), tuple(fragments)) == result
    with pytest.raises(FrozenInstanceError):
        fragments[0].role = "body"


def test_interleaved_source_ids_keep_sequential_order_inside_each_column():
    layout, fragments = packet()
    result = json.loads(validate(layout, fragments))
    cells = result["body"][0]["rows"][0]["cells"]
    assert [cell["fragment_ids"] for cell in cells] == [[fid(2), fid(4)], [fid(3), fid(5)]]


def test_empty_structural_cells_are_preserved_without_invented_fragment_ids():
    layout, fragments = packet()
    layout["body"][0] = table([[fid(2), fid(4)], [], [fid(3), fid(5)]], widths=[35, 10, 55])
    assert json.loads(validate(layout, fragments))["body"][0]["rows"][0]["cells"][1] == {"fragment_ids": []}


def test_header_can_be_first_row_of_first_body_table_at_page_top():
    layout, fragments = packet()
    fragments[0] = replace(fragments[0], bbox_px=(50, 10, 400, 40))
    layout["header"] = []
    layout["body"][0]["rows"][0]["cells"][0]["fragment_ids"].insert(0, fid(1))
    assert validate(layout, fragments)


def test_touching_box_edges_are_disjoint_and_valid():
    layout, fragments = packet()
    fragments[2] = replace(fragments[2], bbox_px=(400, 100, 950, 120))
    fragments[4] = replace(fragments[4], bbox_px=(400, 120, 950, 150))
    assert validate(layout, fragments)


def test_nondefault_page_identity_is_retained_not_renumbered():
    layout, fragments = packet()
    layout = json.loads(json.dumps(layout).replace("p0001_", "p0017_"))
    fragments = [replace(row, rendering_id=row.rendering_id.replace("p0001_", "p0017_")) for row in fragments]
    assert json.loads(validate(layout, fragments, page=17))["body"][0]["table_id"] == "p0017_t0001"


@pytest.mark.parametrize("mutation", [
    lambda layout: layout.update(text="PRIVATE_TEXT_MUST_NOT_ESCAPE"),
    lambda layout: layout.pop("footer"),
    lambda layout: layout.update(version="reviewed_region_layout_v2"),
    lambda layout: layout.update(header=tuple(layout["header"])),
    lambda layout: layout.update(body={}),
    lambda layout: layout.update(footer=None),
    lambda layout: layout["body"][1].update(style="bold"),
    lambda layout: layout["body"][1].update(kind="textbox"),
    lambda layout: layout["body"][1].pop("fragment_id"),
    lambda layout: layout["body"][0].update(text="PRIVATE_TEXT_MUST_NOT_ESCAPE"),
    lambda layout: layout["body"][0]["rows"][0].update(height=10),
    lambda layout: layout["body"][0]["rows"][0]["cells"][0].update(span=2),
    lambda layout: layout["body"][0]["rows"][0]["cells"][0].update(fragment_ids="p0001_f0002"),
])
def test_unknown_missing_or_wrong_typed_schema_fields_rejected(mutation):
    layout, fragments = packet()
    mutation(layout)
    assert_rejected(layout, fragments)


@pytest.mark.parametrize("widths", [[], [100, 0], [50, 49], [50, 51], [True, 99],
    [50.0, 50], ["50", 50], [-1, 101], [20, 20, 20, 20, 20], [100]])
def test_widths_are_rectangular_positive_integer_percentages(widths):
    layout, fragments = packet()
    layout["body"][0]["column_widths"] = widths
    assert_rejected(layout, fragments)


@pytest.mark.parametrize("mutation", [
    lambda layout: layout["body"][0].update(rows=[]),
    lambda layout: layout["body"][0].update(rows={}),
    lambda layout: layout["body"][0]["rows"][0].update(cells=[]),
    lambda layout: layout["body"][0]["rows"][0]["cells"].pop(),
    lambda layout: layout["body"][0]["rows"][0].update(cells=[{"fragment_ids": []}, {"fragment_ids": []}]),
    lambda layout: layout["body"][0].update(rows=layout["body"][0]["rows"] * 101),
])
def test_empty_oversized_or_ragged_table_rejected(mutation):
    layout, fragments = packet()
    mutation(layout)
    assert_rejected(layout, fragments)


@pytest.mark.parametrize("mutation", [
    lambda layout: layout["header"].append(fid(1)),
    lambda layout: layout["body"][0]["rows"][0]["cells"][0]["fragment_ids"].append(fid(3)),
    lambda layout: layout["footer"].pop(),
    lambda layout: layout["body"][1].update(fragment_id=fid(99)),
    lambda layout: layout["body"][1].update(fragment_id=7),
    lambda layout: layout["body"][0].update(table_id="p0002_t0001"),
    lambda layout: layout["body"][0].update(table_id="p0001_t0002"),
    lambda layout: layout["body"][0].update(table_id="p1_t1"),
])
def test_missing_duplicate_foreign_or_unbound_owners_rejected(mutation):
    layout, fragments = packet()
    mutation(layout)
    assert_rejected(layout, fragments)


@pytest.mark.parametrize("index,role", [(0, "body"), (1, "footer"), (1, "folio"),
    (5, "header"), (5, "footer"), (6, "body"), (7, "signature"), (3, "unknown")])
def test_roles_cannot_be_relabelled_into_wrong_containers(index, role):
    layout, fragments = packet()
    fragments[index] = replace(fragments[index], role=role)
    assert_rejected(layout, fragments)


def test_header_is_rejected_in_later_table_or_later_row_or_below_top_quarter():
    layout, fragments = packet()
    fragments[5] = replace(fragments[5], role="header", bbox_px=(50, 200, 950, 230))
    layout["body"][1] = table([[fid(6)]], widths=[100], number=2)
    assert_rejected(layout, fragments)
    layout, fragments = packet()
    fragments[5] = replace(fragments[5], role="header", bbox_px=(50, 200, 950, 230))
    layout["body"].pop()
    layout["body"][0]["rows"].append({"cells": [{"fragment_ids": [fid(6)]}, {"fragment_ids": []}]})
    assert_rejected(layout, fragments)
    layout, fragments = packet()
    fragments[5] = replace(fragments[5], role="header")
    layout["body"] = [table([[fid(2), fid(4)], [fid(3), fid(5), fid(6)]], widths=[40, 60])]
    assert_rejected(layout, fragments)


@pytest.mark.parametrize("index,box", [(3, (50, 110, 400, 150)),
    (2, (350, 100, 950, 120)), (5, (500, 140, 950, 330)),
    (0, (50, 10, 950, 110)), (6, (50, 320, 700, 940)),
    (7, (600, 910, 950, 940)), (7, (50, 890, 950, 899))])
def test_cell_column_block_furniture_overlap_or_reordering_rejected(index, box):
    layout, fragments = packet()
    fragments[index] = replace(fragments[index], bbox_px=box)
    assert_rejected(layout, fragments)


def test_column_union_overlap_rejected_even_when_individual_ink_boxes_do_not_overlap():
    layout, fragments = packet()
    fragments[3] = replace(fragments[3], bbox_px=(50, 130, 700, 150))
    fragments[2] = replace(fragments[2], bbox_px=(500, 100, 950, 120))
    fragments[4] = replace(fragments[4], bbox_px=(800, 130, 950, 150))
    assert_rejected(layout, fragments)


def test_cell_source_order_is_checked_separately_from_vertical_box_order():
    layout, fragments = packet()
    fragments[1], fragments[3] = (replace(fragments[1], bbox_px=fragments[3].bbox_px),
                                replace(fragments[3], bbox_px=fragments[1].bbox_px))
    layout["body"][0]["rows"][0]["cells"][0]["fragment_ids"].reverse()
    assert_rejected(layout, fragments)


def test_reversed_columns_and_rows_rejected():
    layout, fragments = packet()
    layout["body"][0]["rows"][0]["cells"].reverse()
    assert_rejected(layout, fragments)
    layout, fragments = packet()
    layout["body"][0]["rows"] = [
        {"cells": [{"fragment_ids": [fid(4)]}, {"fragment_ids": [fid(5)]}]},
        {"cells": [{"fragment_ids": [fid(2)]}, {"fragment_ids": [fid(3)]}]},
    ]
    assert_rejected(layout, fragments)


def test_body_block_source_order_cannot_be_replaced_by_ordered_box_assertions():
    layout, fragments = vertical_packet(2)
    fragments[0], fragments[1] = (replace(fragments[0], bbox_px=fragments[1].bbox_px),
                                replace(fragments[1], bbox_px=fragments[0].bbox_px))
    layout["body"].reverse()
    assert_rejected(layout, fragments)


def test_table_row_source_ranges_cannot_interleave_even_with_ordered_boxes():
    layout, fragments = packet()
    for first, second in ((1, 3), (2, 4)):
        fragments[first], fragments[second] = (
            replace(fragments[first], bbox_px=fragments[second].bbox_px),
            replace(fragments[second], bbox_px=fragments[first].bbox_px))
    layout["body"][0]["rows"] = [
        {"cells": [{"fragment_ids": [fid(4)]}, {"fragment_ids": [fid(5)]}]},
        {"cells": [{"fragment_ids": [fid(2)]}, {"fragment_ids": [fid(3)]}]},
    ]
    assert_rejected(layout, fragments)


def test_header_cannot_enter_first_table_after_a_body_paragraph():
    fragments = [fragment(1, "body", (50, 10, 950, 20)),
                 fragment(2, "header", (50, 30, 400, 40)),
                 fragment(3, "body", (500, 30, 950, 40))]
    layout = {"version": "reviewed_region_layout_v1", "header": [], "footer": [],
              "body": [{"kind": "paragraph", "fragment_id": fid(1)},
                       table([[fid(2)], [fid(3)]], widths=[50, 50])]}
    assert_rejected(layout, fragments)


@pytest.mark.parametrize("first_role,second_role", [("body", "header"),
    ("footer", "header"), ("footer", "body")])
def test_global_container_order_cannot_reverse_immutable_fragment_order(first_role, second_role):
    boxes = {"header": (50, 10, 950, 40), "body": (50, 100, 950, 200),
             "footer": (50, 900, 950, 940)}
    fragments = [fragment(1, first_role, boxes[first_role]),
                 fragment(2, second_role, boxes[second_role])]
    layout = {"version": "reviewed_region_layout_v1", "header": [], "body": [], "footer": []}
    for number, role in enumerate((first_role, second_role), 1):
        if role == "body":
            layout["body"].append({"kind": "paragraph", "fragment_id": fid(number)})
        else:
            layout[role].append(fid(number))
    assert_rejected(layout, fragments)


@pytest.mark.parametrize("box", [(True, 1, 10, 20), (float("nan"), 1, 10, 20),
    (1, float("inf"), 10, 20), (-1, 1, 10, 20), (10, 1, 10, 20),
    (1, 20, 10, 1), (1, 1, 1001, 20), (1, 1, 10, 1001), (1, 2, 3), [1, 2, 3, 4]])
def test_fragment_box_contract_is_finite_positive_and_in_frame(box):
    layout, fragments = packet()
    fragments[0] = replace(fragments[0], bbox_px=box)
    assert_rejected(layout, fragments)


@pytest.mark.parametrize("page,size", [(True, (1000, 1000)), (0, (1000, 1000)),
    (1000000, (1000, 1000)), (1, (0, 1000)), (1, (1000.0, 1000)),
    (1, (True, 1000)), (1, [1000, 1000]), (1, (10000, 10000))])
def test_invalid_or_oversized_page_frame_rejected(page, size):
    layout, fragments = packet()
    assert_rejected(layout, fragments, page=page, size=size)


@pytest.mark.parametrize("case", ["empty", "wrong_type", "dict_fragment", "duplicate", "wrong_page", "wrong_id"])
def test_input_fragment_identity_contract_rejected(case):
    layout, fragments = packet()
    if case == "empty":
        fragments = []
    elif case == "wrong_type":
        fragments = iter(fragments)
    elif case == "dict_fragment":
        fragments[0] = {"rendering_id": fid(1), "role": "header", "bbox_px": (50, 10, 950, 40)}
    elif case == "duplicate":
        fragments[1] = replace(fragments[1], rendering_id=fid(1))
    elif case == "wrong_page":
        fragments[0] = replace(fragments[0], rendering_id=fid(1, 2))
    else:
        fragments[0] = replace(fragments[0], rendering_id="PRIVATE_TEXT_MUST_NOT_ESCAPE")
    assert_rejected(layout, fragments)


def vertical_packet(count, *, tables=False):
    fragments = [fragment(number, "body", (1, number * 2, 99, number * 2 + 1))
                 for number in range(1, count + 1)]
    body = ([table([[fid(number)]], widths=[100], number=number) for number in range(1, count + 1)]
            if tables else [{"kind": "paragraph", "fragment_id": fid(number)} for number in range(1, count + 1)])
    return {"version": "reviewed_region_layout_v1", "header": [], "body": body, "footer": []}, fragments


def test_fragment_and_table_count_upper_bounds():
    layout, fragments = vertical_packet(5000)
    assert validate(layout, fragments, size=(100, 10001))
    layout, fragments = vertical_packet(5001)
    assert_rejected(layout, fragments, size=(100, 10003))
    layout, fragments = vertical_packet(100, tables=True)
    assert validate(layout, fragments)
    layout, fragments = vertical_packet(101, tables=True)
    assert_rejected(layout, fragments)


def test_one_hundred_rows_and_four_columns_with_empty_cells_are_supported():
    layout, fragments = vertical_packet(100)
    layout["body"] = [{"kind": "table", "table_id": "p0001_t0001", "column_widths": [25, 25, 25, 25],
                       "rows": [{"cells": [{"fragment_ids": [fid(number)]}, {"fragment_ids": []},
                                           {"fragment_ids": []}, {"fragment_ids": []}]}
                                for number in range(1, 101)]}]
    assert validate(layout, fragments)
