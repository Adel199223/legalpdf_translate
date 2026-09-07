from copy import deepcopy
import json

import pytest

from legalpdf_translate.document_spacing import DOCUMENT_SPACING_VERSION, infer_page_spacing
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256


def pair(rows=None):
    rows = rows or [
        {"text": "First source paragraph.", "bbox": [50, 120, 500, 150]},
        {"text": "Second source paragraph.", "bbox": [50, 160, 500, 190]},
    ]
    page = PageStructure(1, "a" * 64, [StructureBlock(f"p0001_b{i:04d}", **row) for i, row in enumerate(rows, 1)],
                         source_file_sha256="f" * 64)
    page.source_sha256 = page.source_text_sha256 = text_sha256(page.text)
    source = page.to_dict()
    target = deepcopy(source)
    for row in target["blocks"]:
        row["text"] = "Translated paragraph."
    target["translation_sha256"] = text_sha256("\n".join(row["text"] for row in target["blocks"]))
    return source, target


def infer(source, target, **kwargs):
    return infer_page_spacing(source_page=source, translated_page=target, **kwargs)


def change_both(source, target, index, **values):
    for page in (source, target):
        page["blocks"][index].update(values)


def test_gap_is_source_geometry_not_target_length_or_line_height():
    source, target = pair()
    before = deepcopy((source, target))
    result = infer(source, target)
    assert result["version"] == DOCUMENT_SPACING_VERSION
    assert result["status"] == "source_bound"
    assert result["line_height_evidence"] == "unavailable"
    assert result["overrides"]["p0001_b0002"] == {
        "previous_block_id": "p0001_b0001", "source_gap_pt": 10.0, "desired_gap_pt": 10.0,
        "basis": "source_same_flow_gap", "clamped": False,
    }
    assert (source, target) == before
    target["blocks"][0]["text"] = ("نص عربي طويل\n" * 50).rstrip()
    target["translation_sha256"] = text_sha256("\n".join(row["text"] for row in target["blocks"]))
    assert infer(source, target)["overrides"] == result["overrides"]
    assert "line_spacing" not in json.dumps(result)
    assert "First source paragraph" not in json.dumps(result)


@pytest.mark.parametrize("gap,expected", [(0, 0), (1.76, 2), (8.82, 9), (33.53, 18)])
def test_body_gap_rounding_and_bounded_clamp(gap, expected):
    source, target = pair()
    change_both(source, target, 1, bbox=[50, 150 + gap, 500, 190 + gap])
    override = infer(source, target)["overrides"]["p0001_b0002"]
    assert override["desired_gap_pt"] == expected
    assert override["clamped"] is (gap > 18)


@pytest.mark.parametrize("role", ["header", "address", "footer"])
def test_furniture_groups_remain_tight(role):
    source, target = pair()
    change_both(source, target, 0, role=role)
    change_both(source, target, 1, role=role)
    assert infer(source, target)["overrides"]["p0001_b0002"]["desired_gap_pt"] == 3


def test_header_to_body_gap_is_bounded_separately():
    source, target = pair()
    change_both(source, target, 0, role="header")
    change_both(source, target, 1, bbox=[50, 178.82, 500, 205])
    override = infer(source, target)["overrides"]["p0001_b0002"]
    assert override["desired_gap_pt"] == 24
    assert override["basis"] == "source_header_body_gap"


def test_header_address_transition_keeps_measured_gap_not_internal_address_compression():
    source, target = pair()
    change_both(source, target, 0, role="header")
    change_both(source, target, 1, role="address")
    assert infer(source, target)["overrides"]["p0001_b0002"]["desired_gap_pt"] == 10


@pytest.mark.parametrize("change,reason", [
    ({"bbox": [50, 140, 500, 190]}, "overlapping_geometry"),
    ({"bbox": [505, 160, 580, 190]}, "different_horizontal_flow"),
    ({"bbox": [50, 600, 500, 630]}, "oversized_source_gap"),
    ({"bbox": None}, "geometry_unavailable"),
    ({"bbox": [-1, 160, 500, 190]}, "geometry_unavailable"),
    ({"bbox": [50, 160, 50, 190]}, "geometry_unavailable"),
    ({"uncertain": True}, "uncertain_block"),
    ({"document_start": True}, "document_boundary"),
    ({"continuation_of": "p0001_b0001"}, "continuation_boundary"),
    ({"role": "footer"}, "footer_reservation_not_paragraph_spacing"),
])
def test_unsafe_adjacency_does_not_invent_spacing(change, reason):
    source, target = pair()
    change_both(source, target, 1, **change)
    result = infer(source, target)
    assert result["overrides"] == {}
    assert result["skipped"] == [{"block_id": "p0001_b0002", "code": reason}]


def test_table_cells_and_parallel_columns_are_not_body_spacing():
    source, target = pair()
    change_both(source, target, 1, role="table_cell", table_id="p0001_t1", row=0, col=0)
    assert infer(source, target)["skipped"][0]["code"] == "table_boundary"
    source, target = pair([
        {"text": "Left.", "bbox": [50, 100, 200, 140]},
        {"text": "Right.", "bbox": [330, 100, 500, 140]},
        {"text": "Later right.", "bbox": [330, 150, 500, 180]},
    ])
    result = infer(source, target)
    assert not result["overrides"]
    assert {row["code"] for row in result["skipped"]} == {"parallel_columns"}


def test_excluded_or_region_rows_break_adjacency_not_bridge_it():
    source, target = pair([
        {"text": "Body.", "bbox": [50, 100, 500, 120]},
        {"text": "Furniture.", "role": "header", "bbox": [50, 130, 500, 140]},
        {"text": "Next body.", "bbox": [50, 150, 500, 170]},
    ])
    assert not infer(source, target, excluded_block_ids={"p0001_b0002"})["overrides"]
    target["metadata"]["layout"] = {"status": "regions", "bands": [{"regions": [{"block_ids": ["p0001_b0002"]}]}]}
    assert not infer(source, target)["overrides"]


@pytest.mark.parametrize("key", ["continuation_from_previous", "continuation_to_next"])
def test_page_continuation_edges_are_skipped(key):
    source, target = pair()
    target[key] = True
    assert infer(source, target)["skipped"][0]["code"] == "continuation_boundary"


@pytest.mark.parametrize("change", ["source_text", "source_hash", "file_hash", "target_hash", "target_text", "geometry", "role", "order", "missing", "uncertain", "page"])
def test_full_binding_is_mandatory(change):
    source, target = pair()
    if change == "source_text": source["blocks"][0]["text"] += "changed"
    elif change == "source_hash": target["source_sha256"] = "e" * 64
    elif change == "file_hash": target["source_file_sha256"] = "e" * 64
    elif change == "target_hash": target["translation_sha256"] = "e" * 64
    elif change == "target_text": target["blocks"][0]["text"] += "changed"
    elif change == "geometry": target["blocks"][0]["bbox"][0] += 1
    elif change == "role": target["blocks"][0]["role"] = "heading"
    elif change == "order": target["blocks"].reverse()
    elif change == "missing": target["blocks"].pop()
    elif change == "uncertain": source["uncertain"] = target["uncertain"] = True
    elif change == "page": target["page_number"] = 2
    result = infer(source, target)
    assert result["status"] == "unavailable" and not result["overrides"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_nonfinite_or_bool_geometry_fails_closed(value):
    source, target = pair()
    change_both(source, target, 1, bbox=[50, value, 500, 190])
    assert infer(source, target)["status"] == "unavailable"


def test_missing_inputs_and_invalid_exclusions_are_safe():
    assert infer({}, {})["status"] == "unavailable"
    source, target = pair()
    assert infer(source, target, excluded_block_ids="p0001_b0001")["status"] == "unavailable"
    assert infer(source, target, excluded_block_ids={None})["status"] == "unavailable"
    assert infer(source, target, excluded_block_ids={"p0001_b0099"})["status"] == "unavailable"


@pytest.mark.parametrize("layout", [
    {"status": "needs_review"},
    {"status": "flow", "review_required": True},
    {"status": "regions", "bands": "invalid"},
    {"status": "regions", "bands": [{"regions": [{"block_ids": "p0001_b0001"}]}]},
    {"status": "regions", "bands": [{"regions": [{"block_ids": ["p0001_b0099"]}]}]},
    {"status": "flow", "bands": [1]},
])
def test_unsupported_or_invalid_layout_is_not_spacing_authority(layout):
    source, target = pair()
    target["metadata"]["layout"] = layout
    assert infer(source, target)["status"] == "unavailable"


def test_empty_target_with_valid_hash_still_cannot_authorize_spacing():
    source, target = pair()
    target["blocks"][0]["text"] = ""
    target["translation_sha256"] = text_sha256("\n".join(row["text"] for row in target["blocks"]))
    assert infer(source, target)["status"] == "unavailable"


def test_page_block_complexity_is_bounded():
    source, target = pair([{"text": str(i), "bbox": [50, 120, 500, 150]} for i in range(513)])
    assert infer(source, target)["status"] == "unavailable"


def separator_pair(text="*", role="reference", target_text=None):
    source, target = pair([
        {"text": "First source paragraph.", "bbox": [50, 120, 500, 140]},
        {"text": text, "role": role, "bbox": [50, 165, 500, 175]},
        {"text": "Second source paragraph.", "bbox": [50, 200, 500, 220]},
    ])
    target["blocks"][1]["text"] = text if target_text is None else target_text
    target["translation_sha256"] = text_sha256("\n".join(row["text"] for row in target["blocks"]))
    return source, target


@pytest.mark.parametrize("text", ["*", "**", "* * *", " \t** ", "********"])
def test_exact_reference_separator_caps_both_adjacent_gaps_without_text_change(text):
    source, target = separator_pair(text)
    before = deepcopy((source, target))
    result = infer(source, target)
    assert result["version"] == "source_block_spacing_v2"
    assert len(result["overrides"]) == 2
    for override in result["overrides"].values():
        assert override["desired_gap_pt"] == 12
        assert override["source_gap_pt"] == 25
        assert override["basis"] == "source_decorative_separator_gap"
        assert override["clamped"] is True
    assert (source, target) == before


@pytest.mark.parametrize("text,role,target_text", [
    ("*", "list_item", "*"),
    ("*", "heading", "*"),
    ("*", "paragraph", "*"),
    ("* Source bullet", "reference", "* Source bullet"),
    ("** Legal heading **", "reference", "** Legal heading **"),
    ("*\n*", "reference", "*\n*"),
    ("*********", "reference", "*********"),
    (" " * 33 + "*", "reference", " " * 33 + "*"),
    ("*", "reference", "**"),
    ("*", "reference", " * "),
    ("*", "reference", "Translated heading."),
    ("***\u200e", "reference", "***\u200e"),
])
def test_non_decorative_or_changed_target_does_not_reduce_ordinary_cap(text, role, target_text):
    source, target = separator_pair(text, role, target_text)
    for override in infer(source, target)["overrides"].values():
        assert override["desired_gap_pt"] == 18
        assert override["basis"] == "source_same_flow_gap"


def test_separator_does_not_compress_smaller_source_gap_or_header_separation():
    source, target = separator_pair()
    change_both(source, target, 0, role="header")
    change_both(source, target, 2, bbox=[50, 184, 500, 204])
    result = infer(source, target)["overrides"]
    assert result["p0001_b0002"]["desired_gap_pt"] == 24
    assert result["p0001_b0002"]["basis"] == "source_header_body_gap"
    assert result["p0001_b0003"]["desired_gap_pt"] == 9
    assert result["p0001_b0003"]["clamped"] is False


def test_separator_cap_preserves_binding_and_adjacency_guards():
    source, target = separator_pair()
    assert not infer(source, target, excluded_block_ids={"p0001_b0002"})["overrides"]
    target["blocks"][1]["text"] = "**"
    assert infer(source, target)["status"] == "unavailable"
