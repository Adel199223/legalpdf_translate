from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json

from PIL import Image, ImageDraw
import pytest

from legalpdf_translate.document_layout import attach_page_layout, derive_page_layout, validate_page_layout
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256


def source(rows=None):
    rows = rows or [
        ((35, 35, 185, 55), "header"),
        ((335, 38, 555, 58), "heading"),
        ((35, 85, 190, 110), "address"),
        ((335, 90, 550, 120), "address"),
        ((35, 205, 205, 225), "heading"),
        ((35, 240, 215, 270), "paragraph"),
        ((35, 285, 210, 310), "paragraph"),
        ((290, 210, 560, 240), "heading"),
        ((290, 260, 560, 300), "paragraph"),
        ((290, 340, 560, 380), "paragraph"),
    ]
    blocks = [StructureBlock(f"p0001_b{i:04d}", f"Synthetic paragraph {i}", role=role, bbox=box, alignment="left")
              for i, (box, role) in enumerate(rows, 1)]
    return PageStructure(1, text_sha256("\n".join(b.text for b in blocks)), blocks, width_pt=600, height_pt=800,
                         source_file_sha256="1" * 64)


def image(*, fill="#d9d9d9", rectangle=True, transparency=False, horizontal_rule=False):
    im = Image.new("RGBA" if transparency else "RGB", (600, 800), "white")
    draw = ImageDraw.Draw(im)
    if rectangle:
        color = (217, 217, 217, 0) if transparency else fill
        draw.rectangle((25, 190, 235, 325), fill=color)
        # Source text creates holes but must not destroy rectangular evidence.
        for y in (210, 248, 291):
            draw.rectangle((36, y, 160, y + 3), fill="black")
        if horizontal_rule:
            draw.line((25, 231, 235, 231), fill="black", width=1)
    output = io.BytesIO()
    im.save(output, format="PNG")
    return output.getvalue()


def panels(layout):
    return [panel for band in layout["bands"] for region in band["regions"] for panel in region["panels"]]


def regions(layout):
    return [region for band in layout["bands"] for region in band["regions"]]


def test_geometry_finds_partial_width_notice_without_midpoint_assumption():
    s = source()
    layout = derive_page_layout(s, image())
    assert layout["status"] == "regions" and not layout["review_required"]
    assert len(layout["bands"]) == 1
    left, right = regions(layout)
    assert left["block_ids"] == [s.blocks[i].id for i in (0, 2, 4, 5, 6)]
    assert right["block_ids"] == [s.blocks[i].id for i in (1, 3, 7, 8, 9)]
    assert left["column_start"] == 0 and right["column_start"] == 1
    assert layout["bands"][0]["column_edges_pt"][1] < s.width_pt / 2
    assert set(left["block_ids"] + right["block_ids"]) == {b.id for b in s.blocks}


@pytest.mark.parametrize("horizontal_rule", [False, True])
def test_pixel_proof_groups_multiparagraph_shaded_panel(horizontal_rule):
    s, data = source(), image(horizontal_rule=horizontal_rule)
    layout = derive_page_layout(s, data)
    assert len(panels(layout)) == 1
    panel = panels(layout)[0]
    assert panel["block_ids"] == [b.id for b in s.blocks[4:7]]
    assert panel["shading"]["fill"] == "D9D9D9"
    assert panel["shading"]["image_sha256"] == hashlib.sha256(data).hexdigest()
    assert panel["shading"]["evidence"] == "pixel_rectangle"
    assert panel["shading"]["sample_fraction"] >= .55
    assert validate_page_layout(layout, s) == layout


def test_no_image_never_invents_shading_but_keeps_supported_columns():
    layout = derive_page_layout(source())
    assert layout["status"] == "regions" and layout["review_required"]
    assert layout["warnings"] == ["panel_style_not_evaluated"]
    assert not panels(layout)


@pytest.mark.parametrize("data", [b"invalid", b"", None])
def test_unavailable_image_keeps_geometry_and_reports_unassessed_style(data):
    layout = derive_page_layout(source(), data)
    assert layout["status"] == "regions" and layout["review_required"] and not panels(layout)


@pytest.mark.parametrize("kwargs", [{"rectangle": False}, {"fill": "white"}, {"transparency": True}])
def test_pixels_without_visible_gray_rectangle_do_not_create_panel(kwargs):
    assert not panels(derive_page_layout(source(), image(**kwargs)))


def test_gray_ellipse_is_not_misrepresented_as_rectangular_panel():
    im = Image.new("RGB", (600, 800), "white")
    ImageDraw.Draw(im).ellipse((25, 190, 235, 325), fill="#d9d9d9")
    output = io.BytesIO()
    im.save(output, format="PNG")
    assert not panels(derive_page_layout(source(), output.getvalue()))


def test_layout_attachment_changes_only_metadata_and_is_detached():
    s = source()
    before = deepcopy(s.to_dict())
    attached = attach_page_layout(s, image())
    assert s.to_dict() == before
    actual = attached.to_dict()
    actual["metadata"].pop("layout")
    assert actual == before
    attached.metadata["other"] = []
    assert "other" not in s.metadata


def test_target_text_reuses_exact_source_geometry_without_retranslation_identity():
    s = source()
    layout = derive_page_layout(s, image())
    target = deepcopy(s.to_dict())
    for block in target["blocks"]:
        block["text"] = "ترجمة عربية " + block["id"]
    target["translation_sha256"] = "2" * 64
    target["metadata"]["layout"] = {"untrusted": "prior metadata is excluded"}
    assert validate_page_layout(layout, target) == layout


@pytest.mark.parametrize("field,value", [("bbox", [40, 35, 185, 55]), ("role", "paragraph"),
    ("alignment", "right"), ("uncertain", True)])
def test_source_geometry_or_role_drift_invalidates_layout(field, value):
    s = source()
    layout = derive_page_layout(s, image())
    payload = s.to_dict()
    payload["blocks"][0][field] = value
    with pytest.raises(ValueError):
        validate_page_layout(layout, payload)


def test_full_width_header_is_a_spanning_band_then_two_columns():
    rows = [((35, 10, 565, 25), "heading"), *[(b.bbox, b.role) for b in source().blocks]]
    s = source(rows)
    layout = derive_page_layout(s, image(rectangle=False))
    assert layout["status"] == "regions"
    assert len(layout["bands"]) == 2
    assert layout["bands"][0]["regions"][0]["column_span"] == 2
    assert layout["bands"][0]["regions"][0]["block_ids"] == [s.blocks[0].id]


def test_overlapping_spanning_block_requires_flow_review():
    rows = [((35, 45, 565, 100), "heading"), *[(b.bbox, b.role) for b in source().blocks]]
    layout = derive_page_layout(source(rows))
    assert layout["status"] == "needs_review" and layout["bands"] == []


def test_single_column_and_semantic_tables_remain_normal_flow():
    s = source([((35, 35, 560, 55), "heading"), ((35, 70, 560, 110), "paragraph")])
    assert derive_page_layout(s)["status"] == "flow"
    s = source([((35, 35, 200, 55), "table_cell"), ((220, 35, 560, 55), "table_cell"),
                ((35, 70, 200, 110), "table_cell"), ((220, 70, 560, 110), "table_cell")])
    for index, block in enumerate(s.blocks):
        block.table_id, block.row, block.col = "p0001_t0001", index // 2, index % 2
    before = s.to_dict()
    assert derive_page_layout(s)["status"] == "flow"
    assert s.to_dict() == before


def test_semantic_table_inside_column_is_not_split_into_layout_cells():
    s = source()
    for index in (4, 5):
        s.blocks[index].role = "table_cell"
        s.blocks[index].table_id, s.blocks[index].row, s.blocks[index].col = "p0001_t0001", index - 4, 0
    layout = derive_page_layout(s, image(rectangle=False))
    assert layout["status"] == "regions"
    assert all(s.blocks[i].id in regions(layout)[0]["block_ids"] for i in (4, 5))
    assert not panels(layout)


def test_missing_or_uncertain_geometry_requires_review():
    for field, value in (("bbox", None), ("uncertain", True)):
        s = source()
        setattr(s.blocks[0], field, value)
        layout = derive_page_layout(s)
        assert layout["status"] == "needs_review" and layout["review_required"] and not layout["bands"]


def test_internal_document_boundary_not_hidden_in_region():
    s = source()
    s.blocks[0].document_start = True
    assert derive_page_layout(s)["status"] == "regions"
    s.blocks[4].document_start = True
    assert derive_page_layout(s)["status"] == "needs_review"


def test_geometry_work_limit_is_fail_closed():
    s = source([((35, i + 1, 200, i + 1.5), "paragraph") for i in range(201)])
    layout = derive_page_layout(s)
    assert layout["status"] == "needs_review" and "layout_geometry_limit" in layout["warnings"]


def test_three_columns_are_not_silently_flattened_into_two_regions():
    s = source([((x, y, x + 120, y + 30), "paragraph")
                for y in (30, 90, 160) for x in (30, 220, 410)])
    layout = derive_page_layout(s, image(rectangle=False))
    assert layout["status"] == "needs_review"
    assert layout["warnings"] == ["additional_column_geometry"]
    assert layout["bands"] == []


@pytest.mark.parametrize("mutation", [
    lambda x: x.update(version=2), lambda x: x.update(page_number=True), lambda x: x.update(status=[]),
    lambda x: x.update(geometry_sha256="0" * 64), lambda x: x.update(unexpected=True),
    lambda x: x["bands"][0].update(column_edges_pt=[35, 35, 560]),
    lambda x: x["bands"][0]["regions"][0].update(column_span=True),
    lambda x: x["bands"][0]["regions"][0].update(alignment=[]),
    lambda x: x["bands"][0]["regions"][0]["block_ids"].pop(),
    lambda x: x["bands"][0]["regions"][0]["block_ids"].append("p0001_b0001"),
    lambda x: x["bands"][0]["regions"][0]["block_ids"].reverse(),
    lambda x: x["bands"][0]["regions"][0].update(bbox=[35, 35, 100, 380]),
    lambda x: x["bands"].append(deepcopy(x["bands"][0])),
    lambda x: x["bands"][0]["regions"][1].update(column_start=0),
    lambda x: x["bands"][0]["regions"][0]["panels"][0].update(block_ids=["p0001_b0005", "p0001_b0007"]),
    lambda x: x["bands"][0]["regions"][0]["panels"][0]["shading"].update(image_sha256="unknown"),
    lambda x: x["bands"][0]["regions"][0]["panels"][0]["shading"].update(sample_fraction=float("nan")),
    lambda x: x["bands"][0]["regions"][0]["panels"][0]["shading"].update(bbox_px=[0, 0, 1, 1]),
])
def test_invalid_layout_rejected_without_changing_source(mutation):
    s = source()
    before = s.to_dict()
    layout = derive_page_layout(s, image())
    mutation(layout)
    with pytest.raises(ValueError):
        validate_page_layout(layout, s)
    assert s.to_dict() == before


def test_explicit_review_fallback_preserves_source_binding():
    s = source()
    layout = derive_page_layout(s)
    layout.update(status="needs_review", review_required=True, bands=[], warnings=["unsupported_region_geometry"])
    assert validate_page_layout(layout, s)["bands"] == []
