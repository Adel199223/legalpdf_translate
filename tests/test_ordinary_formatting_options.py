"""Explicit derivative settings and source-bound gutters through ordinary runs."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from legalpdf_translate.checkpoint import load_run_state, settings_fingerprint
from legalpdf_translate.formatting_support import formatting_fingerprint
from legalpdf_translate.ordinary_formatting_review_service import (
    OrdinaryFormattingReviewService, FormattingReviewServiceError,
    FormattingDocumentDecision, FormattingDocumentGroup, FormattingTable,
    _page_decision_dict, _typed_page,
)
from legalpdf_translate.run_docx_formatting import OPERATOR_REVIEW_PROFILE, prepare_run_docx_formatting
from legalpdf_translate.run_workspace_lock import run_workspace_slot
from legalpdf_translate.types import TargetLang
from tests.test_ordinary_formatting_review_service import (
    public_case, page_decision, completed_draft, submit, originals,
)
from tests.test_ordinary_source_review_service import local_only


@pytest.mark.parametrize("lang", [TargetLang.EN, TargetLang.FR, TargetLang.AR])
@pytest.mark.parametrize("saved_page_breaks", [False, True])
def test_explicit_page_matched_derivative_preserves_original_run_and_reloads_exact_choice(
        tmp_path, monkeypatch, lang, saved_page_breaks):
    case = public_case(tmp_path, monkeypatch, lang=lang, count=2, page_breaks=saved_page_breaks)
    before = originals(case)
    original_settings = deepcopy(settings_fingerprint(case.config))
    case.service = OrdinaryFormattingReviewService(case.config, case.context, page_matched_derivative=True)
    draft = completed_draft(case)
    choice = draft["formatting_derivative"]
    assert choice == {"version": "explicit_source_page_matched_derivative_v1",
        "original_page_breaks": saved_page_breaks, "page_breaks": True,
        "original_formatting_fingerprint": formatting_fingerprint(case.config),
        "formatting_fingerprint": formatting_fingerprint(replace(case.config, page_breaks=True))}
    result = submit(case, draft)
    revision = result["revision_id"]
    assert result["formatting_derivative"] == choice
    ordinary = OrdinaryFormattingReviewService(case.config, case.context)
    with pytest.raises(FormattingReviewServiceError, match="draft_owner_changed"):
        ordinary.read(draft["draft_id"])
    with pytest.raises(FormattingReviewServiceError, match="revision_owner_changed"):
        ordinary.rebuild(revision)
    restored = OrdinaryFormattingReviewService(case.config, case.context, page_matched_derivative=True)
    assert restored.read(draft["draft_id"])["revision_id"] == revision
    output = restored.rebuild(revision)
    assert output["status"] == "built" and output["formatting_derivative"] == choice
    mapping = json.loads(output["source_map"].read_bytes())
    assert mapping["source_page_count"] == 2 and mapping["rendered_page_count"] is None
    assert mapping["typography"]["size_pt"] == (11 if lang == TargetLang.AR else 10.5)
    folder = case.run_dir / "formatting_reviews" / revision
    evidence = json.loads((folder / "review_evidence.bin").read_bytes())
    assert evidence["formatting_derivative"] == choice
    with run_workspace_slot(case.run_dir):
        state = load_run_state(case.run_dir / "run_state.json")
        effective = prepare_run_docx_formatting(case.run_dir, replace(case.config, page_breaks=True), state,
            revision_id=revision, review_profile=OPERATOR_REVIEW_PROFILE)
        assert effective.status == "ready"
        if not saved_page_breaks:
            unchanged = prepare_run_docx_formatting(case.run_dir, case.config, state,
                revision_id=revision, review_profile=OPERATOR_REVIEW_PROFILE)
            assert unchanged.status == "declined"
            assert "reviewed_profile_requires_page_breaks" in unchanged.notice_codes
    assert case.config.page_breaks is saved_page_breaks
    assert settings_fingerprint(case.config) == original_settings and originals(case) == before
    assert len(case.calls) == len(case.local_calls) == 2


@pytest.mark.parametrize("choice", [None, 0, 1, "true", [], {}])
def test_derivative_requires_a_real_boolean(tmp_path, monkeypatch, choice):
    case = public_case(tmp_path, monkeypatch)
    with pytest.raises(FormattingReviewServiceError, match="invalid_derivative_choice"):
        OrdinaryFormattingReviewService(case.config, case.context, page_matched_derivative=choice)


def test_derivative_does_not_enable_bidi_stripping_or_mutate_unsupported_preferences(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch, page_breaks=False, strip_bidi_controls=False)
    before = originals(case)
    selected = OrdinaryFormattingReviewService(case.config, case.context, page_matched_derivative=True)
    result = selected.prepare()
    assert result == {"status": "declined", "notice_codes": ["reviewed_profile_requires_bidi_stripping"]}
    assert not case.config.page_breaks and not case.config.strip_bidi_controls
    assert originals(case) == before and len(case.calls) == 1


def test_derivative_cannot_rebind_original_checkpoint_settings(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch, page_breaks=False)
    before = originals(case)
    forged_original = replace(case.config, page_breaks=True)
    selected = OrdinaryFormattingReviewService(forged_original, case.context, page_matched_derivative=True)
    with pytest.raises(FormattingReviewServiceError, match="saved_owner_changed"):
        selected.prepare()
    assert originals(case) == before


@pytest.mark.parametrize("record_name,error", [("parents", "draft_owner_changed"),
    ("intent", "submission_intent_changed"), ("receipt", "revision_owner_changed")])
@pytest.mark.parametrize("field,value", [("page_breaks", 1), ("original_page_breaks", 0)])
def test_persisted_derivative_booleans_cannot_be_replaced_by_equal_integers(
        tmp_path, monkeypatch, record_name, error, field, value):
    case = public_case(tmp_path, monkeypatch, page_breaks=False)
    case.service = OrdinaryFormattingReviewService(case.config, case.context, page_matched_derivative=True)
    draft = completed_draft(case)
    revision = submit(case, draft)["revision_id"]
    root = case.run_dir / "visual_formatting_reviews"
    path = (root / "revisions" / (revision + ".json") if record_name == "receipt"
        else root / "drafts" / draft["draft_id"] / ("parents.json" if record_name == "parents" else "submit_intent.json"))
    value_before = json.loads(path.read_bytes())
    value_before["owner"]["formatting_derivative"][field] = value
    path.write_text(json.dumps(value_before), encoding="utf-8")
    before = originals(case)
    restored = OrdinaryFormattingReviewService(case.config, case.context, page_matched_derivative=True)
    # Match the owner error, not a later checksum failure; the intent mutation
    # needs no generation-chain edit and previously compared equal in Python.
    with pytest.raises(FormattingReviewServiceError, match=error):
        if record_name == "parents":
            restored.read(draft["draft_id"])
        else:
            restored.rebuild(revision)
    assert originals(case) == before and len(case.calls) == 1


def _save_table(case, gap):
    draft = case.service.prepare()
    decision = page_decision(draft["pages"][0], table=True)
    table = replace(decision.body[0], column_gaps_px=gap)
    decision = replace(decision, body=(table,))
    return case.service.save_page(draft["draft_id"], expected_generation=draft["generation"],
        page_number=1, decision=decision)


@pytest.mark.parametrize("lang", [TargetLang.EN, TargetLang.FR, TargetLang.AR])
def test_explicit_gutter_survives_saved_decisions_and_reaches_real_docx_map(tmp_path, monkeypatch, lang):
    case = public_case(tmp_path, monkeypatch, lang=lang)
    before = originals(case)
    draft = _save_table(case, (12,))
    decision = draft["pages"][0]["decision"]
    assert decision["body"][0]["column_gaps_px"] == (12,)
    # Reading JSON from a fresh service preserves exact typed decisions.
    restored = OrdinaryFormattingReviewService(case.config, case.context)
    reloaded = restored.read(draft["draft_id"])
    assert reloaded["pages"][0]["decision"]["body"][0]["column_gaps_px"] == [12]
    case.service = restored
    draft = restored.save_document(draft["draft_id"], expected_generation=draft["generation"],
        decision=FormattingDocumentDecision((FormattingDocumentGroup(1, 1),), True, False, True,
            "Fictional operator", "Explicit source-supported table gutter reviewed."))
    revision = submit(case, draft)["revision_id"]
    output = restored.rebuild(revision)
    mapping = json.loads(output["source_map"].read_bytes())
    assert mapping["table_policy"] == "explicit_ltr_fixed_percent_columns_reviewed_gutters_v2"
    table = mapping["pages"][0]["tables"][0]
    assert table["column_gaps_px"] == [12]
    assert table["column_gaps_twips"] == [714]
    assert table["cell_margins_twips"] == [{"left": 0, "right": 357}, {"left": 357, "right": 0}]
    assert originals(case) == before and len(case.calls) == len(case.local_calls) == 1


@pytest.mark.parametrize("gap", [(), (True,), (-1,), (21,), (float("nan"),),
    (float("inf"),), ("12",), (12, 12), (10**1000,), "12"])
def test_malformed_or_source_unsupported_gutter_cannot_save_a_page(tmp_path, monkeypatch, gap):
    case = public_case(tmp_path, monkeypatch)
    before = originals(case)
    with pytest.raises(FormattingReviewServiceError):
        _save_table(case, gap)
    assert originals(case) == before and not (case.run_dir / "formatting_reviews").exists()


def test_default_table_decision_retains_v1_schema_and_output(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    draft = case.service.prepare()
    decision = page_decision(draft["pages"][0], table=True)
    raw = _page_decision_dict(decision)
    assert "column_gaps_px" not in raw["body"][0]
    assert _typed_page(json.loads(json.dumps(raw))) == decision
    draft = completed_draft(case, table=True)
    revision = submit(case, draft)["revision_id"]
    output = case.service.rebuild(revision)
    mapping = json.loads(output["source_map"].read_bytes())
    assert mapping["table_policy"] == "explicit_ltr_fixed_percent_columns_zero_cell_margins_v1"
    assert "column_gaps_px" not in mapping["pages"][0]["tables"][0]
    assert "formatting_derivative" not in draft


def test_mixed_explicit_and_unspecified_table_gaps_require_a_complete_choice(tmp_path, monkeypatch):
    case = public_case(tmp_path, monkeypatch)
    draft = case.service.prepare()
    decision = page_decision(draft["pages"][0])
    decision = replace(decision, body=(FormattingTable((100,), (((1,),),), ()),
                                      FormattingTable((100,), (((2,),),))))
    with pytest.raises(FormattingReviewServiceError, match="explicit_table_gaps_required"):
        case.service.save_page(draft["draft_id"], expected_generation=draft["generation"],
            page_number=1, decision=decision)
