"""Synthetic delimiter/ownership contracts; no private source or renderer."""
from copy import deepcopy
from dataclasses import replace

import pytest

from legalpdf_translate.reviewed_cell_boundaries import (
    MAX_PIPE_BOUNDARIES, MAX_SCOPE_DEPTH, MAX_TEXT_BYTES,
    ReviewedCellBoundariesError, pipe_cell_boundaries, validated_inline_cell_pairs,
)
from legalpdf_translate.reviewed_regions import RegionFragmentInput


def fid(number):
    return f"p0001_f{number:04d}"


def packet():
    fragments = tuple(RegionFragmentInput(fid(number), "body", box) for number, box in enumerate([
        (10, 100, 280, 130), (320, 100, 610, 130), (660, 100, 990, 130),
    ], 1))
    layout = {"version": "reviewed_region_layout_v1", "header": [], "footer": [],
              "body": [{"kind": "table", "table_id": "p0001_t0001",
                        "column_widths": [30, 35, 35],
                        "rows": [{"cells": [{"fragment_ids": [f.rendering_id]} for f in fragments]}]}]}
    return layout, fragments


def pairs(layout, fragments):
    return validated_inline_cell_pairs(layout, fragments=fragments, page_number=1,
                                       image_size_px=(1000, 1400))


@pytest.mark.parametrize("text", [
    "Processo: 123 | Referência: 456 | Data: 23/06/2026",
    "الملف: 123 | المرجع: 456 | التاريخ: 23/06/2026",
    "Nom: João Guerreiro | Heure: 09:30 | Dossier: 123",
    "Name: [[João Guerreiro]] | Time: [[09:30]] | Reference: 123",
])
def test_three_cells_preserve_every_literal_separator_and_character(text):
    boundaries = sorted(pipe_cell_boundaries(text))
    assert len(boundaries) == 2
    ends = [0, *boundaries, len(text)]
    fragments = [text[start:end] for start, end in zip(ends, ends[1:])]
    assert "".join(fragments) == text
    assert all(fragment.endswith(" | ") for fragment in fragments[:-1])
    assert sum(fragment.count("|") for fragment in fragments) == 2


def test_source_and_target_offsets_are_independent():
    source = "Nome: João Guerreiro | Hora: 09:30 | Ref: 123"
    target = "الاسم: [[João Guerreiro]] | الساعة: [[09:30]] | المرجع: 123"
    assert pipe_cell_boundaries(source) != pipe_cell_boundaries(target)
    assert {source[index] for index in pipe_cell_boundaries(source)} == {"H", "R"}
    assert {target[index] for index in pipe_cell_boundaries(target)} == {"ا"}


def test_all_ascii_horizontal_separator_space_belongs_to_preceding_cell():
    text = "Name\t | \t  Time"
    assert pipe_cell_boundaries(text) == frozenset({text.index("Time")})
    assert text[:next(iter(pipe_cell_boundaries(text)))].endswith("| \t  ")


@pytest.mark.parametrize("text", [
    "", "João Guerreiro", "09:30", "القانون", "A\nB", "A\r\nB",
    "A| B", "A |B", "A|B", "A ｜ B", "A ¦ B", "A\u00a0| B", "A |\u00a0B",
    " | B", "A | ", "A | | B", "A\n | B", "A | \nB", "A | \r\nB",
    "A | \u0301B", "A | \u064eب", "A | \u200dب", "A | \u200cب",
    "A | \ufe0fB", "A | \U0001f3fbB", "A | \u200eB", "A | \u061cب",
    "A\u200d | B", "A | \x00B",
    "[[Name | Time]]", "\u2066Name | Time\u2069", "\u202aName | Time\u202c",
])
def test_unsafe_or_non_pipe_cuts_are_not_offered(text):
    assert pipe_cell_boundaries(text) == frozenset()


def test_complete_scope_inside_cell_does_not_hide_later_safe_boundary():
    text = "[[Name | Time]] | Reference"
    assert pipe_cell_boundaries(text) == frozenset({text.index("Reference")})


def test_scope_inside_right_cell_starts_only_at_whole_placeholder():
    text = "Name | [[João Guerreiro]]"
    assert pipe_cell_boundaries(text) == frozenset({text.index("[[")})


@pytest.mark.parametrize("text", [
    "\u2066[[ABC-123]]\u2069 | مرجع | \u2066[[23-06-2026]]\u2069",
    "Name: \u2066[[João Guerreiro]]\u2069 | \u2066[[09:30]]\u2069 appointment",
])
def test_complete_literal_isolates_remain_inside_their_independent_cells(text):
    expected = frozenset(index + 3 for index in range(len(text)) if text.startswith(" | ", index))
    assert pipe_cell_boundaries(text) == expected
    ends = [0, *sorted(expected), len(text)]
    cells = [text[start:end] for start, end in zip(ends, ends[1:])]
    assert "".join(cells) == text
    assert all(cell.count("\u2066") == cell.count("\u2069") for cell in cells)


@pytest.mark.parametrize("literal", [
    "\u2066Name\u2069", "\u2067[[Name]]\u2069", "\u2068[[Name]]\u2069",
    "\u202a[[Name]]\u202c", "\u2066[[]]\u2069", "\u2066[[ ]]\u2069",
    "\u2066[[Name\nSurname]]\u2069", "\u2066[[A\u200eB]]\u2069",
    "\u2066[[A\u200dB]]\u2069", "\u2066[[A | B]]\u2069",
])
@pytest.mark.parametrize("side", ["left", "right"])
def test_unadmitted_isolate_shapes_do_not_supply_field_edges(literal, side):
    text = literal + " | Field" if side == "left" else "Field | " + literal
    assert pipe_cell_boundaries(text) == frozenset()


@pytest.mark.parametrize("prefix", ["\u0301", "\u064e", "\u200c", "\u200d", "\ufe0f", "\U0001f3fb"])
def test_literal_isolate_cannot_hide_unsafe_right_grapheme_edge(prefix):
    assert pipe_cell_boundaries("Field | \u2066[[" + prefix + "Name]]\u2069") == frozenset()


def test_combining_mark_stays_with_preceding_arabic_word():
    text = "اسمُ | مرجع"
    assert pipe_cell_boundaries(text) == frozenset({text.index("مرجع")})


@pytest.mark.parametrize("text,code", [
    ("[[Name", "cell_unclosed_text_scope"),
    ("Name]]", "cell_unmatched_placeholder"),
    ("[[Name [[Time]]]]", "cell_nested_placeholder"),
    ("\u2066Name", "cell_unclosed_text_scope"),
    ("Name\u2069", "cell_unbalanced_bidi_scope"),
    ("\u2066\u202aName\u2069\u202c", "cell_unbalanced_bidi_scope"),
    ("A | B [[", "cell_unclosed_text_scope"),
    ("A | B \u202c", "cell_unbalanced_bidi_scope"),
    ("A\rB", "cell_unsupported_line_separator"),
    ("A\u0085B", "cell_unsupported_line_separator"),
    ("A\u2028B", "cell_unsupported_line_separator"),
    ("A\u2029B", "cell_unsupported_line_separator"),
    ("\ud800", "cell_invalid_unicode"),
])
def test_malformed_text_has_only_exact_content_free_error(text, code):
    with pytest.raises(ReviewedCellBoundariesError) as caught:
        pipe_cell_boundaries(text)
    assert str(caught.value) == code


@pytest.mark.parametrize("text", [None, b"A | B", 1, True, [], {}])
def test_non_text_rejected_without_coercion(text):
    with pytest.raises(ReviewedCellBoundariesError, match="^cell_invalid_text$"):
        pipe_cell_boundaries(text)


def test_text_byte_and_character_bounds(monkeypatch):
    import legalpdf_translate.reviewed_cell_boundaries as module
    assert MAX_TEXT_BYTES == 4 * 1024 * 1024
    monkeypatch.setattr(module, "MAX_TEXT_BYTES", 8)
    with pytest.raises(ReviewedCellBoundariesError, match="^cell_invalid_text$"):
        pipe_cell_boundaries("a" * 9)
    with pytest.raises(ReviewedCellBoundariesError, match="^cell_text_too_large$"):
        pipe_cell_boundaries("ب" * 5)


def test_scope_and_boundary_counts_are_bounded(monkeypatch):
    import legalpdf_translate.reviewed_cell_boundaries as module
    assert MAX_SCOPE_DEPTH == 128 and MAX_PIPE_BOUNDARIES == 5000
    monkeypatch.setattr(module, "MAX_SCOPE_DEPTH", 2)
    with pytest.raises(ReviewedCellBoundariesError, match="^cell_scope_depth_exceeded$"):
        pipe_cell_boundaries("\u2066" * 3 + "A" + "\u2069" * 3)
    monkeypatch.setattr(module, "MAX_PIPE_BOUNDARIES", 2)
    with pytest.raises(ReviewedCellBoundariesError, match="^cell_too_many_boundaries$"):
        pipe_cell_boundaries("A | B | C | D")


def test_only_complete_validated_same_row_body_cells_supply_pairs():
    layout, fragments = packet()
    before = deepcopy((layout, fragments))
    assert pairs(layout, fragments) == frozenset({(fid(1), fid(2)), (fid(1), fid(3)), (fid(2), fid(3))})
    assert (layout, fragments) == before


def test_source_order_is_independent_of_physical_column_order():
    layout, fragments = packet()
    first, second, third = fragments
    fragments = (replace(first, bbox_px=third.bbox_px), second, replace(third, bbox_px=first.bbox_px))
    layout["body"][0]["rows"][0]["cells"].reverse()
    assert pairs(layout, fragments) == frozenset({(fid(1), fid(2)), (fid(1), fid(3)), (fid(2), fid(3))})


@pytest.mark.parametrize("role", ["signature", "header"])
def test_signature_and_permitted_top_header_cannot_acquire_inline_authority(role):
    layout, fragments = packet()
    fragments = (replace(fragments[0], role=role), *fragments[1:])
    assert pairs(layout, fragments) == frozenset({(fid(2), fid(3))})


def test_empty_cell_has_no_authority():
    layout, fragments = packet()
    layout["body"][0]["rows"][0]["cells"][1]["fragment_ids"] = []
    fragments = (fragments[0], replace(fragments[2], rendering_id=fid(2)))
    layout["body"][0]["rows"][0]["cells"][2]["fragment_ids"] = [fid(2)]
    assert pairs(layout, fragments) == frozenset({(fid(1), fid(2))})


def test_multiple_fragments_in_one_cell_cannot_acquire_inline_authority():
    layout, fragments = packet()
    fragments = (fragments[0], replace(fragments[1], bbox_px=(10, 150, 280, 180)),
                 replace(fragments[2], bbox_px=(660, 100, 990, 180)))
    cells = layout["body"][0]["rows"][0]["cells"]
    cells[0]["fragment_ids"] = [fid(1), fid(2)]
    cells[1]["fragment_ids"] = []
    assert pairs(layout, fragments) == frozenset()


@pytest.mark.parametrize("kind", ["paragraph", "cross_row", "cross_table"])
def test_non_cell_and_different_row_or_table_pairs_are_excluded(kind):
    layout, fragments = packet()
    fragments = tuple(replace(f, bbox_px=(10, 100 + index * 100, 900, 130 + index * 100))
                      for index, f in enumerate(fragments))
    if kind == "paragraph":
        layout["body"] = [{"kind": "paragraph", "fragment_id": f.rendering_id} for f in fragments]
    elif kind == "cross_row":
        layout["body"][0].update(column_widths=[100], rows=[
            {"cells": [{"fragment_ids": [f.rendering_id]}]} for f in fragments])
    else:
        layout["body"] = [{"kind": "table", "table_id": f"p0001_t{index:04d}", "column_widths": [100],
                           "rows": [{"cells": [{"fragment_ids": [f.rendering_id]}]}]}
                          for index, f in enumerate(fragments, 1)]
    assert pairs(layout, fragments) == frozenset()


@pytest.mark.parametrize("change", [
    lambda layout: layout["body"][0]["rows"][0]["cells"][1].update(fragment_ids=[fid(1)]),
    lambda layout: layout["body"][0]["rows"][0]["cells"][1].update(fragment_ids=[]),
    lambda layout: layout["body"][0]["rows"][0]["cells"].reverse(),
    lambda layout: layout["body"][0].update(column_widths=[50, 50]),
    lambda layout: layout.update(version="unreviewed"),
    lambda layout: layout.update(extra="private synthetic sentinel"),
])
def test_malformed_or_incomplete_region_layout_never_supplies_partial_pairs(change):
    layout, fragments = packet()
    change(layout)
    with pytest.raises(ReviewedCellBoundariesError) as caught:
        pairs(layout, fragments)
    assert str(caught.value) == "cell_invalid_region_layout"


@pytest.mark.parametrize("kwargs", [
    {"page_number": 2}, {"page_number": True}, {"image_size_px": (0, 1400)},
    {"image_size_px": [1000, 1400]}, {"fragments": []}, {"fragments": {}},
])
def test_malformed_region_inputs_use_helper_error(kwargs):
    layout, fragments = packet()
    inputs = dict(fragments=fragments, page_number=1, image_size_px=(1000, 1400))
    inputs.update(kwargs)
    with pytest.raises(ReviewedCellBoundariesError, match="^cell_invalid_region_layout$"):
        validated_inline_cell_pairs(layout, **inputs)
