from copy import deepcopy
import json

import pytest

from legalpdf_translate.ordinary_layout_contracts import (PROPOSAL_VERSION, LayoutSuggestionPolicy, OrdinaryLayoutError,
    normalize_proposals, page_ids, proposal_schema)
from legalpdf_translate.saved_docx_layout import inspect_docx, validate_decisions
from tests.test_ordinary_layout_service import make_case


def proposal(view, page=1):
    rows = []
    for choice in view["decisions"]["paragraphs"]:
        if {r["page_number"] for r in choice["regions"]} != {page}:
            continue
        row = deepcopy(choice)
        row.pop("regions"); row.pop("unmapped_reason")
        row["bbox"] = [0, 0, 1, 1]
        rows.append(row)
    rows[0].update(role="heading", heading_level=1, heading_size_pt=12, bold=True)
    return {"version": PROPOSAL_VERSION, "page_number": page, "paragraphs": rows,
            "bands": [{"kind": "columns", "widths_pct": [60, 40], "gutter_pt": 18,
                "cells": [{"groups": [{"paragraph_ids": [rows[0]["paragraph_id"]], "panel": True}]},
                          {"groups": [{"paragraph_ids": [rows[1]["paragraph_id"]], "panel": False}]}]}]}


@pytest.mark.parametrize("lang", ["EN", "FR", "AR"])
def test_proposal_cannot_claim_review_or_change_text(tmp_path, monkeypatch, lang):
    case = make_case(tmp_path, monkeypatch, lang)
    view = case.view["review"]
    normalized = normalize_proposals(inspect_docx(case.job.reviewed_docx, lang), view, [proposal(view)])
    assert normalized["bands"][0]["widths_pct"] == [60, 40]
    assert normalized["review"]["document_reviewed"] is False
    assert normalized["review"]["pages_reviewed"] == []
    assert "text" not in json.dumps(proposal_schema(1, page_ids(view, 1)))


@pytest.mark.parametrize("mutation", ["text", "unknown", "duplicate", "order", "box", "role", "bad_span", "review"])
def test_rejects_injected_text_identity_geometry_or_attestation(tmp_path, monkeypatch, mutation):
    case = make_case(tmp_path, monkeypatch)
    view = case.view["review"]; value = proposal(view)
    if mutation == "text": value["paragraphs"][0]["text"] = "Replace words"
    elif mutation == "unknown": value["paragraphs"][0]["paragraph_id"] = "p999999"
    elif mutation == "duplicate": value["paragraphs"][1]["paragraph_id"] = "p000001"
    elif mutation == "order": value["bands"][0]["cells"].reverse()
    elif mutation == "box": value["paragraphs"][0]["bbox"] = [-1, 0, 1, 1]
    elif mutation == "role": value["paragraphs"][0]["role"] = "invented"
    elif mutation == "bad_span": value["paragraphs"][0]["emphasis"] = [{"start": 1, "end": 3, "bold": True, "italic": False, "underline": False}]
    elif mutation == "review": value["document_reviewed"] = True
    with pytest.raises(OrdinaryLayoutError):
        normalize_proposals(inspect_docx(case.job.reviewed_docx, "EN"), view, [value])


def test_unknown_source_mapping_is_not_guessed(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch, mapping=False)
    with pytest.raises(OrdinaryLayoutError, match="page_mapping_required"):
        page_ids(case.view["review"], 1)


def test_nonheading_size_is_disallowed_by_schema_and_writer_without_silent_repair(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    view = case.view["review"]
    snapshot = inspect_docx(case.job.reviewed_docx, "EN")
    schema = proposal_schema(1, page_ids(view, 1))["schema"]
    branches = schema["properties"]["paragraphs"]["items"]["anyOf"]
    heading, other = (branch["properties"] for branch in branches)
    assert heading["role"]["enum"] == ["heading"]
    assert other["heading_level"] == {"type": "integer", "enum": [0]}
    assert other["heading_size_pt"] == {"type": "null"}
    assert set(other["role"]["enum"]) == {
        "institution", "reference", "recipient", "body", "list", "signature", "source_folio"}
    for role in other["role"]["enum"]:
        value = proposal(view)
        value["paragraphs"][0].update(role=role, heading_level=0, heading_size_pt=14)
        retained = deepcopy(value)
        with pytest.raises(OrdinaryLayoutError, match="invalid_proposal_decisions"):
            normalize_proposals(snapshot, view, [value])
        assert value == retained
        value["paragraphs"][0]["heading_size_pt"] = None
        normalized = normalize_proposals(snapshot, view, [value])
        assert normalized["paragraphs"][0]["role"] == role
        assert normalized["paragraphs"][0]["heading_size_pt"] is None
        assert normalized["review"]["document_reviewed"] is False
        assert normalized["review"]["pages_reviewed"] == []


def test_schema_heading_values_match_writer_and_exclude_invalid_combinations(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    view = case.view["review"]
    snapshot = inspect_docx(case.job.reviewed_docx, "EN")
    heading = proposal_schema(1, page_ids(view, 1))["schema"]["properties"]["paragraphs"]["items"]["anyOf"][0]["properties"]
    assert heading["heading_level"] == {"type": "integer", "enum": [1, 2, 3]}
    assert heading["heading_size_pt"] == {"type": ["number", "null"], "minimum": 1, "maximum": 24}
    for level in heading["heading_level"]["enum"]:
        for size in (None, 1, 11.5, 24):
            value = proposal(view)
            value["paragraphs"][0].update(heading_level=level, heading_size_pt=size)
            normalized = normalize_proposals(snapshot, view, [value])
            assert normalized["paragraphs"][0]["heading_level"] == level
            assert normalized["paragraphs"][0]["heading_size_pt"] == size
    for level, size in ((0, None), (4, None), (1, 0), (1, 24.1)):
        value = proposal(view)
        value["paragraphs"][0].update(heading_level=level, heading_size_pt=size)
        with pytest.raises(OrdinaryLayoutError, match="invalid_proposal_decisions"):
            normalize_proposals(snapshot, view, [value])


def test_schema_exposes_bounded_spacing_regions_columns_and_strict_nested_branches():
    schema = proposal_schema(1, ["p000001", "p000002"])["schema"]
    assert schema["type"] == "object" and "anyOf" not in schema
    paragraphs = schema["properties"]["paragraphs"]
    assert paragraphs["minItems"] == paragraphs["maxItems"] == 2
    for branch in paragraphs["items"]["anyOf"]:
        assert branch["additionalProperties"] is False
        assert set(branch["required"]) == set(branch["properties"])
        props = branch["properties"]
        assert props["space_before_pt"] == props["space_after_pt"] == {
            "type": ["number", "null"], "minimum": 0, "maximum": 72}
        assert props["bbox"] == {"type": ["array", "null"],
            "items": {"type": "number", "minimum": 0, "maximum": 1}, "minItems": 4, "maxItems": 4}
    columns = schema["properties"]["bands"]["items"]["anyOf"][1]["properties"]
    assert columns["widths_pct"] == {"type": "array",
        "items": {"type": "number", "minimum": 10, "maximum": 90}, "minItems": 2, "maxItems": 3}
    assert columns["cells"]["minItems"] == 2 and columns["cells"]["maxItems"] == 3
    assert columns["gutter_pt"] == {"type": "number", "minimum": 0, "maximum": 36}


@pytest.mark.parametrize("mutation", ["spacing", "gutter", "width", "width_total", "cell_count"])
def test_writer_still_rejects_invalid_layout_bounds_and_cross_field_constraints(tmp_path, monkeypatch, mutation):
    case = make_case(tmp_path, monkeypatch)
    view = case.view["review"]
    value = proposal(view)
    if mutation == "spacing": value["paragraphs"][0]["space_before_pt"] = 72.1
    elif mutation == "gutter": value["bands"][0]["gutter_pt"] = 36.1
    elif mutation == "width": value["bands"][0]["widths_pct"] = [9, 91]
    elif mutation == "width_total": value["bands"][0]["widths_pct"] = [50, 40]
    elif mutation == "cell_count": value["bands"][0]["widths_pct"] = [40, 30, 30]
    with pytest.raises(OrdinaryLayoutError, match="invalid_proposal_decisions"):
        normalize_proposals(inspect_docx(case.job.reviewed_docx, "EN"), view, [value])


def test_layout_policy_has_finite_eight_minute_default_and_retains_old_explicit_bound():
    policy = LayoutSuggestionPolicy("gpt-5.2", "1.148", "3.444")
    assert policy.public() == {"model": "gpt-5.2", "max_page_cost_usd": "1.148",
        "max_operation_cost_usd": "3.444", "max_output_tokens": 32000,
        "timeout_seconds": 480.0, "effort": "high"}
    old = LayoutSuggestionPolicy("gpt-5.2", ".812", "2.436", max_output_tokens=8000,
        timeout_seconds=240.0)
    assert old.public()["max_output_tokens"] == 8000
    assert old.public()["timeout_seconds"] == 240.0
    assert LayoutSuggestionPolicy("gpt-5.2", ".812", "2.436", timeout_seconds=90).public()["timeout_seconds"] == 90


@pytest.mark.parametrize("timeout", [4.99, 480.01, float("inf"), float("nan"), True, "480"])
def test_layout_policy_rejects_unbounded_or_invalid_timeout(timeout):
    with pytest.raises(OrdinaryLayoutError, match="paid_policy_unavailable"):
        LayoutSuggestionPolicy("gpt-5.2", ".812", "2.436", timeout_seconds=timeout).public()


@pytest.mark.parametrize("lang", ["EN", "FR", "AR"])
def test_bounded_degenerate_boxes_leave_styles_unreviewed_and_explicitly_unmapped(tmp_path, monkeypatch, lang):
    case = make_case(tmp_path, monkeypatch, lang)
    view = deepcopy(case.view["review"])
    view["decisions"]["review"].update(document_reviewed=True, pages_reviewed=[1],
                                      reviewer="Fictional operator", note="Earlier source review.")
    snapshot = inspect_docx(case.job.reviewed_docx, lang)
    boxes = ([0.07, 1, 0.75, 1], [0.5, 0.1, 0.5, 0.8],
             [0.9, 0.1, 0.2, 0.8], [0.1, 0.9, 0.8, 0.2], [1, 1, 0, 0])
    for box in boxes:
        value = proposal(view)
        value["paragraphs"][0]["bbox"] = box
        retained = deepcopy(value)
        normalized = normalize_proposals(snapshot, view, [value])
        row = normalized["paragraphs"][0]
        assert row["regions"] == []
        assert row["unmapped_reason"] == (
            "Suggested source box is empty or reversed; operator source association is required.")
        assert {k: v for k, v in row.items() if k not in {"regions", "unmapped_reason"}} == {
            k: v for k, v in retained["paragraphs"][0].items() if k != "bbox"}
        assert normalized["bands"] == retained["bands"]
        assert value == retained
        assert normalized["review"] == {"reviewer_kind": "operator_review", "reviewer": "", "note": "",
                                        "pages_reviewed": [], "document_reviewed": False}
        with pytest.raises(ValueError, match="incomplete_source_review"):
            validate_decisions(snapshot, view["pages"], normalized, require_review=True)


def test_malformed_nonfinite_and_out_of_bounds_boxes_still_reject(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    view = case.view["review"]
    snapshot = inspect_docx(case.job.reviewed_docx, "EN")
    boxes = ([], [0, 0, 1], [0, 0, 1, 1, 1], (0, 0, 1, 1), "0,0,1,1", {},
             [False, 0, 1, 1], [0, "0", 1, 1], [float("nan"), 0, 1, 1],
             [0, 0, float("inf"), 1], [0, float("-inf"), 1, 1],
             [-0.01, 0, 1, 1], [0, 0, 1.01, 1], [-0.01, 1, 0.75, 1])
    for box in boxes:
        value = proposal(view)
        value["paragraphs"][0]["bbox"] = box
        with pytest.raises(OrdinaryLayoutError, match="invalid_proposal_box"):
            normalize_proposals(snapshot, view, [value])


def test_valid_and_uncertain_box_meanings_are_unchanged(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    view = case.view["review"]
    snapshot = inspect_docx(case.job.reviewed_docx, "EN")
    frame = view["pages"][0]
    value = proposal(view)
    value["paragraphs"][0]["bbox"] = [0.1, 0.2, 0.8, 0.9]
    normalized = normalize_proposals(snapshot, view, [value])
    assert normalized["paragraphs"][0]["regions"] == [{"page_number": 1, "bbox_px": [
        0.1 * frame["width_px"], 0.2 * frame["height_px"],
        0.8 * frame["width_px"], 0.9 * frame["height_px"]]}]
    assert normalized["paragraphs"][0]["unmapped_reason"] == ""
    value["paragraphs"][0]["bbox"] = None
    normalized = normalize_proposals(snapshot, view, [value])
    assert normalized["paragraphs"][0]["regions"] == []
    assert normalized["paragraphs"][0]["unmapped_reason"] == "Source association requires operator review."
