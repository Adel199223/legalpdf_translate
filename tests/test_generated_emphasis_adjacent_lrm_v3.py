"""Fictional whole-run optional hints; no source text or live services."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path

import pytest
from docx import Document
from fastapi.testclient import TestClient

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate.saved_docx_layout import inspect_docx, _emphasis, SavedDocxLayoutError
from tests.test_ordinary_generated_emphasis import span

MARK = "\u200e"
REASON = "adjacent_complete_lrm_owner_emphasis_omitted"


def case(side="following", *, owner="ZX-104"):
    parts = ([MARK + owner + MARK] if side in {"preceding", "both"} else [])
    start = sum(map(len, parts))
    parts.append("Fictional label: ")
    end = sum(map(len, parts))
    if side in {"following", "both"}:
        parts.append(MARK + owner + MARK)
    document = Document()
    paragraph = document.add_paragraph()
    for part in parts:
        paragraph.add_run(part)
    stream = BytesIO()
    document.save(stream)
    row = inspect_docx(stream.getvalue(), "AR")["paragraphs"][0]
    return row, [span(start, end)]


@pytest.mark.parametrize("side", ["preceding", "following", "both"])
def test_v3_omits_only_whole_clean_run_with_each_adjacent_owner_proven(side):
    row, hints = case(side)
    before = deepcopy((row, hints))
    rejected = []
    assert c._generated_emphasis(row, hints, normalization_version=c.EMPHASIS_NORMALIZATION_V3,
        rejected=rejected) == []
    assert rejected == [{"span": hints[0], "reason": REASON}]
    assert (row, hints) == before
    for version in (None, c.EMPHASIS_NORMALIZATION_V1, c.EMPHASIS_NORMALIZATION_V2):
        with pytest.raises(c.OrdinaryLayoutError):
            c._generated_emphasis(row, hints, normalization_version=version)
    with pytest.raises(SavedDocxLayoutError):
        _emphasis(row, hints)


@pytest.mark.parametrize("damage", [
    "partial_selected", "missing_selected", "duplicate_selected", "crossing_selected",
    "missing_owner", "duplicate_owner", "crossing_owner", "split_owner",
    "padded_left", "padded_right", "empty_owner", "interior_control", "other_mark",
    "bare_mark", "bad_other_edge", "field", "break", "nontext", "later_interior",
    "later_overlap", "later_malformed",
])
def test_new_omission_never_hides_ambiguous_ownership_or_fatal_span_guards(damage):
    if damage in {"padded_left", "padded_right", "empty_owner", "interior_control"}:
        owner = {"padded_left": " ZX-104", "padded_right": "ZX-104 ",
                 "empty_owner": "", "interior_control": "ZX\u200d104"}[damage]
        row, hints = case(owner=owner)
    else:
        row, hints = case("both" if damage == "bad_other_edge" else "following")
    selected = next(run for run in row["runs"] if run["start"] == hints[0]["start"])
    owner = row["runs"][-1]
    if damage == "partial_selected": hints[0]["start"] += 1
    elif damage == "missing_selected": row["runs"].remove(selected)
    elif damage == "duplicate_selected": row["runs"].append(deepcopy(selected))
    elif damage == "crossing_selected": row["runs"].append({**selected, "end": selected["end"] + 1})
    elif damage == "missing_owner": row["runs"].remove(owner)
    elif damage == "duplicate_owner": row["runs"].append(deepcopy(owner))
    elif damage == "crossing_owner": row["runs"].append({**owner, "start": owner["start"] + 1})
    elif damage == "split_owner":
        row["runs"].remove(owner)
        row["runs"].extend([{**owner, "end": owner["start"] + 2}, {**owner, "start": owner["start"] + 2}])
    elif damage == "other_mark": row["text"] = row["text"].replace(MARK, "\u200f")
    elif damage == "bare_mark": row["text"] = row["text"][:-1] + "x"
    elif damage == "bad_other_edge": row["text"] = "\u200f" + row["text"][1:]
    elif damage == "field": row["has_field"] = True
    elif damage == "break": row["has_page_break"] = True
    elif damage == "nontext": row["tokens"].append({"kind": "tab", "text": "\t", "start": len(row["text"]), "end": len(row["text"]) + 1})
    elif damage == "later_interior": hints.append(span(owner["start"] + 1, owner["end"] - 1))
    elif damage == "later_overlap": hints.append(span(1, 3))
    elif damage == "later_malformed": hints.append(span(True, 3))
    with pytest.raises(c.OrdinaryLayoutError):
        c._generated_emphasis(row, hints, normalization_version=c.EMPHASIS_NORMALIZATION_V3)


def test_unrelated_complete_lrm_run_does_not_borrow_or_invalidate_local_proof():
    row, hints = case()
    # The additional complete owner is separated from the participating pair.
    end = len(row["text"])
    suffix = " context " + MARK + "OTHER-9" + MARK
    row["text"] += suffix
    row["runs"].extend([{**row["runs"][0], "start": end, "end": end + 9},
                        {**row["runs"][1], "start": end + 9, "end": len(row["text"])}])
    row["tokens"].append({"kind": "t", "text": suffix, "start": end, "end": len(row["text"])})
    assert c._generated_emphasis(row, hints, normalization_version=c.EMPHASIS_NORMALIZATION_V3) == []


def test_v3_keeps_v2_complete_owner_omission_and_safe_styles_exact():
    from tests.test_ordinary_generated_emphasis import lrm_row
    row, start, end = lrm_row()
    for version in (c.EMPHASIS_NORMALIZATION_V2, c.EMPHASIS_NORMALIZATION_V3):
        rejected = []
        assert c._generated_emphasis(row, [span(start, end)], normalization_version=version, rejected=rejected) == []
        assert rejected == [{"span": span(start, end), "reason": "complete_lrm_owner_emphasis_omitted"}]


def test_omission_evidence_preserves_exact_hint_hash_and_review_warning():
    from tests.test_ordinary_source_evidence import fixture
    snapshot, view, proposal = fixture()
    row, hints = case()
    row["id"] = "p000001"
    snapshot["paragraphs"] = [row]
    view["paragraphs"][0]["text"] = row["text"]
    proposal["paragraphs"][0]["emphasis"] = hints
    original = deepcopy((snapshot, view, proposal))
    evidence = c.proposal_source_evidence(snapshot, view, proposal,
        emphasis_normalization_version=c.EMPHASIS_NORMALIZATION_V3)
    assert evidence["optional_emphasis_normalization"] == {
        "version": c.EMPHASIS_NORMALIZATION_V3,
        "canonical_proposal_sha256": c.digest(c.encode(proposal)),
        "rejected_spans": [{"paragraph_id": "p000001", "span": hints[0], "reason": REASON}],
        "review_required": True}
    assert c.source_evidence_review_fields([evidence])["source_layout_rejected_hints"] == [{
        "page_number": 1, "kind": "optional_emphasis", "paragraph_ids": ["p000001"],
        "paragraph_id": "p000001", "span": hints[0], "reason": REASON}]
    assert (snapshot, view, proposal) == original


def test_fresh_v9_changes_only_emphasis_and_preserves_concrete_v8_selectors():
    old, new = auto._in_body_terminal_closing_v8_policy(), auto._adjacent_lrm_emphasis_v9_policy()
    assert new == auto._adjacent_lrm_emphasis_v9_policy() and new != old
    for policy in (old, new):
        fp = policy.split(":")[1]
        assert auto._band_normalization_version(fp) == c.BAND_NORMALIZATION_V8
        assert auto._terminal_source_layout_versions(fp)["source_closing_group_version"] == "bounded_terminal_signature_context_v3"
        assert auto._clock_direction_version(fp) == "clock_h_colon_ltr_v1"
        assert auto._source_folio_inline_direction_version(fp) == "source_bound_folio_separator_ltr_v1"
        assert policy in auto._metadata_normalization_policies() and policy in auto._source_folio_policies()
    assert auto._emphasis_normalization_version(old.split(":")[1]) == c.EMPHASIS_NORMALIZATION_V2
    assert auto._emphasis_normalization_version(new.split(":")[1]) == c.EMPHASIS_NORMALIZATION_V3


@pytest.mark.parametrize("reader", ["evidence", "recovery"])
@pytest.mark.parametrize("damage", ["initial_missing", "initial_wrong", "ledger_changed"])
def test_fresh_v3_marker_and_source_evidence_are_immutable_in_both_saved_readers(tmp_path, monkeypatch, reader, damage):
    from tests import test_ordinary_layout_manager as provider
    from tests.test_ordinary_layout_service import make_case, nonce
    from legalpdf_translate.ordinary_layout_service import _read
    case = make_case(tmp_path, monkeypatch)
    original = provider.proposal
    def proposal(view):
        value = original(view)
        value.update(version=c.PROPOSAL_VERSION_V3, paragraph_partitions=[], source_coverage_findings=[], source_layout_evidence=[])
        return value
    monkeypatch.setattr(provider, "proposal", proposal)
    paid = provider.enable_paid(case)
    policy = auto._adjacent_lrm_emphasis_v9_policy()
    assert policy == auto._adjacent_lrm_emphasis_v9_policy()
    operation_nonce = nonce()
    result = case.manager.suggest(case.job.job_id, case.view["generation"], operation_nonce, [1],
        expected_baseline_id=case.view["baseline_id"], band_normalization_version=c.BAND_NORMALIZATION_V8,
        emphasis_normalization_version=c.EMPHASIS_NORMALIZATION_V3)
    assert result["status"] == "applied_unreviewed"
    operation = case.manager.service.root / case.job.job_id / "baselines" / case.view["baseline_id"] / "suggestions" / operation_nonce
    initial = operation / "proposal_initial_view.json"
    assert _read(initial)["emphasis_normalization_version"] == c.EMPHASIS_NORMALIZATION_V3
    assert _read(operation / "intent.json")["request"]["policy"]["emphasis_normalization_version"] == c.EMPHASIS_NORMALIZATION_V3
    kwargs = (case.manager, case.job.job_id, case.view["baseline_id"], case.view["review"]["review_id"], operation_nonce, (1,), policy)
    first = auto._proposal_evidence(*kwargs)
    assert auto._proposal_evidence(*kwargs) == first and len(paid.calls) == 1
    path = operation / "source_evidence.json" if damage == "ledger_changed" else initial
    value = _read(path)
    if damage == "initial_missing": value.pop("emphasis_normalization_version")
    elif damage == "initial_wrong": value["emphasis_normalization_version"] = c.EMPHASIS_NORMALIZATION_V2
    else: value["pages"][0]["source_coverage_verified"] = True
    path.write_bytes(c.encode({"payload": value, "sha256": c.digest(c.encode(value))}))
    pointer = {"origin_job_id": case.job.job_id, "baseline_id": case.view["baseline_id"],
               "review_id": case.view["review"]["review_id"], "operation_nonce": operation_nonce,
               "initial_generation": case.view["generation"]}
    with pytest.raises(c.OrdinaryLayoutError, match="source_evidence_response_changed"):
        if reader == "evidence": auto._proposal_evidence(*kwargs)
        else:
            (operation / "result.json").unlink()
            auto._recover_settled_result(case.manager, pointer, [1], policy_fingerprint=policy.split(":")[1])
    assert len(paid.calls) == 1


@pytest.mark.parametrize("restart", [False, True], ids=["saved_v8_resume", "saved_v8_restart_resume"])
def test_saved_v8_actual_resume_and_restart_remain_v8_under_fresh_v9(tmp_path, monkeypatch, restart):
    # Explicit historical V9 default for this saved-V8 oracle.
    monkeypatch.setattr(auto, "frozen_automatic_layout_policy", auto._adjacent_lrm_emphasis_v9_policy)
    from tests import test_ordinary_auto_layout_workflow as flow
    from tests.test_terminal_accounting_restore import gmail_fixture, restart_into_app
    from legalpdf_translate.ordinary_layout_service import _read
    original = flow._proposal
    def proposal(*args, **kwargs):
        value = original(*args, **kwargs)
        value.update(version=c.PROPOSAL_VERSION_V3, paragraph_partitions=[], source_coverage_findings=[], source_layout_evidence=[])
        return value
    monkeypatch.setattr(flow, "_proposal", proposal)
    source, output = tmp_path / "fictional.pdf", tmp_path / "output"
    output.mkdir()
    flow._source(source, ("digital",))
    app, jobs, sdk, requests = flow._app(tmp_path, monkeypatch, ("Fictional body text.",), (1,))
    loaded, session, gmail = gmail_fixture(source, output)
    form = {"source_path": str(source), "output_dir": str(output), "target_lang": "EN",
            "start_page": 1, "end_page": 1, "image_mode": "off", "ocr_mode": "off", "workers": 1,
            "gmail_batch_context": gmail}
    with TestClient(app) as client:
        with monkeypatch.context() as prior:
            prior.setattr(auto, "frozen_automatic_layout_policy", auto._in_body_terminal_closing_v8_policy)
            response = client.post("/api/translation/jobs/translate", json={"mode": "shadow", "workspace_id": "fictional", "form_values": form})
            assert response.status_code == 200
            job_id = response.json()["normalized_payload"]["job"]["job_id"]
            initial = flow._wait(jobs, job_id)
        assert initial["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
        assert auto.frozen_automatic_layout_policy() == auto._adjacent_lrm_emphasis_v9_policy()
        run = Path(initial["result"]["run_dir"])
        pointer = json.loads((run / "ordinary_auto_layout/operation.json").read_bytes())
        manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context, "shadow", "fictional")
        operation = manager.service.root / job_id / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
        saved = {p: p.read_bytes() for p in operation.rglob("*") if p.is_file() and p.suffix != ".lock"}
        assert _read(operation / "proposal_initial_view.json")["emphasis_normalization_version"] == c.EMPHASIS_NORMALIZATION_V2
        if restart:
            app, jobs = restart_into_app(tmp_path, app, jobs, job_id, loaded, session)
            client = TestClient(app)
        response = client.post("/api/translation/jobs/translate", json={"mode": "shadow", "workspace_id": "fictional", "form_values": {**form, "resume": True}})
        assert response.status_code == 200
        resumed_id = response.json()["normalized_payload"]["job"]["job_id"]
        resumed = flow._wait(jobs, resumed_id)
        assert resumed["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
        assert len(sdk.requests) == len(requests) == 1
        assert all(p.read_bytes() == raw for p, raw in saved.items())

