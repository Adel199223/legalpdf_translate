"""Generated presentation cannot reorder or omit immutable paragraph text."""
from copy import deepcopy
import json

import pytest

from legalpdf_translate.ordinary_layout_contracts import (
    BAND_NORMALIZATION_V1, BAND_NORMALIZATION_V2, PROPOSAL_VERSION_V3, OrdinaryLayoutError,
    normalize_proposals, page_ids, proposal_source_evidence)
from legalpdf_translate.saved_docx_layout import inspect_docx, validate_decisions
from tests.test_ordinary_layout_service import make_case


def proposal(case, page=1):
    view = case.view["review"]
    ids = page_ids(view, page)
    rows = []
    for choice in view["decisions"]["paragraphs"]:
        if choice["paragraph_id"] not in ids: continue
        row = deepcopy(choice)
        row.pop("regions"); row.pop("unmapped_reason")
        row.update(bbox=[.3, .9, .7, .98], role="source_folio")
        rows.append(row)
    return {"version": PROPOSAL_VERSION_V3, "page_number": page, "paragraphs": rows,
        "bands": [{"kind": "flow", "groups": [{"paragraph_ids": list(reversed(ids)), "panel": False}]}],
        "paragraph_partitions": [], "source_coverage_findings": [],
        "source_layout_evidence": [{"kind": "source_footer", "paragraph_ids": list(reversed(ids)), "bbox": [.3, .9, .7, 1]}]}


def test_complete_contiguous_plain_flow_restores_text_order_and_discards_reversed_hint(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch, pages=2)
    view, raw = case.view["review"], case.job.reviewed_docx
    snapshot = inspect_docx(raw, "EN")
    value = proposal(case, page=2)
    before = deepcopy(value)
    decisions = normalize_proposals(snapshot, view, [value], band_normalization_version=BAND_NORMALIZATION_V2)
    assert [pid for band in decisions["bands"] for group in band.get("groups", []) for pid in group["paragraph_ids"]] == [row["id"] for row in snapshot["paragraphs"]]
    validate_decisions(snapshot, view["pages"], decisions)
    evidence = proposal_source_evidence(snapshot, view, value, band_normalization_version=BAND_NORMALIZATION_V2)
    assert evidence["layout"] == []
    assert evidence["metadata_band_normalization"]["version"] == BAND_NORMALIZATION_V2
    assert evidence["metadata_band_normalization"]["rejected_bands"][0]["reason"] == "generated_plain_flow_restored_to_text_order"
    assert evidence["normalization"]["rejected_hints"][0]["reason"] == "reordered_source_footer_hint_kept_in_flow"
    assert evidence["source_coverage_verified"] is False
    assert value == before and case.job.reviewed_docx == raw


def test_only_contiguous_flow_interval_changes_beside_existing_columns(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch, pages=2)
    view = case.view["review"]
    for choice in view["decisions"]["paragraphs"]:
        for region in choice["regions"]: region["page_number"] = 1
    value = proposal(case)
    ids = page_ids(view, 1)
    columns = {"kind": "columns", "widths_pct": [50, 50], "gutter_pt": 12, "cells": [
        {"groups": [{"paragraph_ids": [ids[0]], "panel": False}]},
        {"groups": [{"paragraph_ids": [ids[1]], "panel": False}]}]}
    value["bands"] = [columns, {"kind": "flow", "groups": [{"paragraph_ids": [ids[3], ids[2]], "panel": False}]}]
    value["source_layout_evidence"][0]["paragraph_ids"] = [ids[3], ids[2]]
    snapshot = inspect_docx(case.job.reviewed_docx, "EN")
    decisions = normalize_proposals(snapshot, view, [value], band_normalization_version=BAND_NORMALIZATION_V2)
    assert decisions["bands"][0] == columns
    assert decisions["bands"][1]["groups"][0]["paragraph_ids"] == ids[2:]
    # An interleaved flow interval must not borrow IDs across a column band.
    value["bands"][0]["cells"][0]["groups"][0]["paragraph_ids"] = [ids[0]]
    value["bands"][0]["cells"][1]["groups"][0]["paragraph_ids"] = [ids[2]]
    value["bands"][1]["groups"][0]["paragraph_ids"] = [ids[3], ids[1]]
    with pytest.raises(OrdinaryLayoutError, match="proposal_coverage"):
        normalize_proposals(snapshot, view, [value], band_normalization_version=BAND_NORMALIZATION_V2)


@pytest.mark.parametrize("version", [None, BAND_NORMALIZATION_V1])
def test_historical_normalization_does_not_gain_new_flow_repair(tmp_path, monkeypatch, version):
    case = make_case(tmp_path, monkeypatch)
    with pytest.raises(OrdinaryLayoutError, match="proposal_coverage"):
        normalize_proposals(inspect_docx(case.job.reviewed_docx, "EN"), case.view["review"], [proposal(case)],
                            band_normalization_version=version)


def test_unspecified_helpers_and_retained_import_keep_v1_until_explicit_successor_opt_in(tmp_path, monkeypatch):
    from tests.test_ordinary_layout_manager import enable_paid
    from tests.test_ordinary_layout_service import nonce
    from legalpdf_translate.ordinary_layout_service import _read

    case = make_case(tmp_path, monkeypatch)
    paid = enable_paid(case)
    value, view = proposal(case), case.view["review"]
    snapshot = inspect_docx(case.job.reviewed_docx, "EN")
    with pytest.raises(OrdinaryLayoutError, match="proposal_coverage"):
        normalize_proposals(snapshot, view, [value])
    with pytest.raises(OrdinaryLayoutError, match="invalid_source_layout_evidence"):
        proposal_source_evidence(snapshot, view, value)
    retained = {1: {"raw": json.dumps(value).encode("utf-8"), "origin": {"fictional": "prior_immutable_raw"}}}
    with pytest.raises(OrdinaryLayoutError, match="proposal_coverage"):
        case.manager.suggest(case.job.job_id, case.view["generation"], nonce(), [1],
            expected_baseline_id=case.view["baseline_id"], retained_proposals=retained)
    assert not paid.calls and not paid.accountants
    operation_nonce = nonce()
    result = case.manager.suggest(case.job.job_id, case.view["generation"], operation_nonce, [1],
        expected_baseline_id=case.view["baseline_id"], retained_proposals=retained,
        band_normalization_version=BAND_NORMALIZATION_V2)
    assert result["status"] == "applied_unreviewed" and not paid.calls
    directory = case.manager.service.folder(case.job.job_id) / "baselines" / case.view["baseline_id"] / "suggestions" / operation_nonce
    assert _read(directory / "intent.json")["request"]["policy"]["band_normalization_version"] == BAND_NORMALIZATION_V2
    assert _read(directory / "proposal_initial_view.json")["band_normalization_version"] == BAND_NORMALIZATION_V2
    before = (directory / "page-0001.response.json").read_bytes()
    assert case.manager.suggest(case.job.job_id, case.view["generation"], operation_nonce, [1],
        expected_baseline_id=case.view["baseline_id"]) == result
    assert (directory / "page-0001.response.json").read_bytes() == before and not paid.calls


def test_existing_failed_paid_result_never_reinterpreted_by_new_explicit_recipe(tmp_path, monkeypatch):
    from tests import test_ordinary_layout_manager as fixture
    from tests.test_ordinary_layout_service import nonce
    from legalpdf_translate.ordinary_layout_service import _read

    case = make_case(tmp_path, monkeypatch)
    value = proposal(case)
    monkeypatch.setattr(fixture, "proposal", lambda _: deepcopy(value))
    paid = fixture.enable_paid(case)
    old_nonce = nonce()
    old_result = case.manager.suggest(case.job.job_id, case.view["generation"], old_nonce, [1],
        expected_baseline_id=case.view["baseline_id"])
    assert old_result["status"] == "failed" and old_result["error_code"] == "ordinary_layout_proposal_coverage"
    old_folder = case.manager.service.folder(case.job.job_id) / "baselines" / case.view["baseline_id"] / "suggestions" / old_nonce
    before = {path.name: path.read_bytes() for path in old_folder.iterdir() if path.is_file()}
    assert "band_normalization_version" not in _read(old_folder / "intent.json")["request"]["policy"]
    assert case.manager.suggest(case.job.job_id, case.view["generation"], old_nonce, [1],
        expected_baseline_id=case.view["baseline_id"], band_normalization_version=BAND_NORMALIZATION_V2) == old_result
    assert len(paid.calls) == 1
    new_result = case.manager.suggest(case.job.job_id, case.view["generation"], nonce(), [1],
        expected_baseline_id=case.view["baseline_id"], band_normalization_version=BAND_NORMALIZATION_V2)
    assert new_result["status"] == "applied_unreviewed" and len(paid.calls) == 2
    assert before == {path.name: path.read_bytes() for path in old_folder.iterdir() if path.is_file()}


def test_old_current_paid_evidence_replays_its_exact_v1_recipe_after_fresh_policy_change(tmp_path, monkeypatch):
    from tests import test_ordinary_layout_manager as fixture
    from tests.test_ordinary_layout_service import nonce
    from legalpdf_translate.ordinary_auto_layout import _optional_hint_policy, _proposal_evidence

    case = make_case(tmp_path, monkeypatch)
    value = proposal(case)
    value["bands"][0]["groups"][0]["paragraph_ids"].reverse()
    value["source_layout_evidence"] = []
    monkeypatch.setattr(fixture, "proposal", lambda _: deepcopy(value))
    paid = fixture.enable_paid(case)
    operation_nonce = nonce()
    result = case.manager.suggest(case.job.job_id, case.view["generation"], operation_nonce, [1],
        expected_baseline_id=case.view["baseline_id"])
    assert result["status"] == "applied_unreviewed"
    old = _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3", emphasis_normalization=True,
        metadata_normalization=True, primary_folio_version="terminal_labeled_folio_v2", source_folio_proof=True)
    directory = case.manager.service.folder(case.job.job_id) / "baselines" / case.view["baseline_id"] / "suggestions" / operation_nonce
    before = {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}
    first = _proposal_evidence(case.manager, case.job.job_id, case.view["baseline_id"], case.view["review"]["review_id"],
                               operation_nonce, (1,), old)
    second = _proposal_evidence(case.manager, case.job.job_id, case.view["baseline_id"], case.view["review"]["review_id"],
                                operation_nonce, (1,), old)
    assert first == second and first["local_source_folio_proof_version"] == "ordinary_source_folio_span_proof_v1"
    assert first["policy_fingerprint"] == old.split(":", 1)[1]
    assert len(paid.calls) == 1
    assert before == {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}


@pytest.mark.parametrize("mutation", ["missing", "extra", "duplicate", "panel", "partition", "field", "page_break", "unknown_key"])
def test_unsafe_or_incomplete_generated_flow_remains_rejected(tmp_path, monkeypatch, mutation):
    case = make_case(tmp_path, monkeypatch)
    view = case.view["review"]
    snapshot = inspect_docx(case.job.reviewed_docx, "EN")
    value = proposal(case)
    group = value["bands"][0]["groups"][0]
    if mutation == "missing": group["paragraph_ids"].pop()
    if mutation == "extra": group["paragraph_ids"].append("p999999")
    if mutation == "duplicate": group["paragraph_ids"][1] = group["paragraph_ids"][0]
    if mutation == "panel": group["panel"] = True
    if mutation == "partition": value["paragraph_partitions"] = [{"paragraph_id": group["paragraph_ids"][0], "split_before": ["all words."]}]
    if mutation == "field": snapshot["paragraphs"][0]["has_field"] = True
    if mutation == "page_break": snapshot["paragraphs"][0]["has_page_break"] = True
    if mutation == "unknown_key": group["invented"] = True
    with pytest.raises(OrdinaryLayoutError):
        normalize_proposals(snapshot, view, [value], band_normalization_version=BAND_NORMALIZATION_V2)


def test_fresh_policy_versions_new_behavior_without_reinterpreting_prior_policy():
    from legalpdf_translate.ordinary_auto_layout import (
        frozen_automatic_layout_policy, _source_bound_v4_policy, _optional_hint_policy, _band_normalization_version,
        _source_normalization_version, _source_folio_policies, _body_columns_v3_policy, _clock_direction_policy, _heading_columns_v4_policy)
    old = _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3", emphasis_normalization=True,
        metadata_normalization=True, primary_folio_version="terminal_labeled_folio_v2", source_folio_proof=True)
    current = _heading_columns_v4_policy()
    assert current != old
    assert _band_normalization_version(_source_bound_v4_policy().split(":", 1)[1]) == BAND_NORMALIZATION_V2
    assert _band_normalization_version(_body_columns_v3_policy().split(":", 1)[1]) == "ordinary_metadata_band_normalization_v3"
    assert _band_normalization_version(_clock_direction_policy().split(":", 1)[1]) == "ordinary_metadata_band_normalization_v3"
    assert _band_normalization_version(current.split(":", 1)[1]) == "ordinary_metadata_band_normalization_v4"
    assert _band_normalization_version(old.split(":", 1)[1]) == BAND_NORMALIZATION_V1
    assert _source_normalization_version(old.split(":", 1)[1]) == "ordinary_optional_layout_hint_normalization_v3"
    assert old in _source_folio_policies()
