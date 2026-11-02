"""Fictional fresh V12 operations; every native provider transport is mocked."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_reproposal as proof
from legalpdf_translate.ordinary_layout_contracts import OrdinaryLayoutError, decode, encode, digest
from tests import test_ordinary_layout_reproposal as legacy


@pytest.fixture(autouse=True)
def no_live_provider(monkeypatch):
    legacy.isolate_provider(monkeypatch)
    # These capacity/ledger oracles belong to concrete saved V12, not a moving renderer.
    monkeypatch.setattr(auto, "frozen_automatic_layout_policy", auto._per_page_reproposal_v12_policy)


def invalid_footer(proposal):
    # Footer eligibility requires plain flow; the shared fixture starts with a panel.
    for band in proposal["bands"]:
        for group in band["groups"]:
            group["panel"] = False
    proposal["source_layout_evidence"] = [{"kind": "source_footer",
        "paragraph_ids": [proposal["paragraphs"][0]["paragraph_id"]], "bbox": [.1, .2, .8, .3]}]


def invalid_band_coverage(proposal):
    pid = proposal["paragraphs"][0]["paragraph_id"]
    # Each repeated reference is schema-valid, but their flattened coverage is not.
    proposal["bands"] = [{"kind": "columns", "widths_pct": [50, 50], "gutter_pt": 0,
        "cells": [{"groups": [{"paragraph_ids": [pid], "panel": False}]} for _ in range(2)]}]


def mixed_damage(page, ordinal, proposal, *_):
    if ordinal == 0 and page == 2:
        legacy.invalid_decision(proposal)
    if ordinal == 0 and page == 3:
        invalid_band_coverage(proposal)


@pytest.fixture(scope="module")
def two_repaired_pages(tmp_path_factory):
    patch = pytest.MonkeyPatch()
    legacy.isolate_provider(patch)
    case = legacy.normal_start(tmp_path_factory.mktemp("per_page_success"), patch,
        damage=mixed_damage, saved_policy=auto._per_page_reproposal_v12_policy())
    yield case
    patch.undo()


def test_normal_start_two_distinct_replacements_strict_candidate_and_accounting(two_repaired_pages):
    case = two_repaired_pages
    assert auto.frozen_automatic_layout_policy() == auto._per_page_reproposal_v12_policy()
    assert [p for p, _ in case.calls] == [1, 2, 2, 3, 3], case.job["result"]["automatic_layout"]
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    witness, kwargs = legacy.witness_context(case)
    proposals, summary = proof.verify_witness(witness, **kwargs)
    assert len(proposals) == 3 and summary["provider_dispatch_count"] == 5
    assert witness["version"] == proof.VERSION_V2
    assert "repair_slot.json" not in witness["records"]
    assert {n for n in witness["records"] if n.endswith("repair_slot.json")} == {
        "page-0002/repair_slot.json", "page-0003/repair_slot.json"}
    begins = witness["journal"]["events"][::2]
    assert len({e["call_id"] for e in begins}) == 5
    assert all(e["attempt"] == 1 for e in begins)
    assert case.job["result"]["automatic_layout"]["layout_costs"]["complete"]
    for page in (2, 3):
        folder = case.operation / "attempts" / f"page-{page:04d}"
        assert decode((folder / "selection.json").read_bytes())["ordinal"] == 1
        assert (case.operation / f"page-{page:04d}.response.json").read_bytes() == (folder / "attempt-01.response.json").read_bytes()
        assert (folder / "attempt-00.response.json").read_bytes() != (folder / "attempt-01.response.json").read_bytes()
    assert not (case.operation / "attempts/page-0001/repair_slot.json").exists()
    assert decode(witness["records"]["page-0002/attempt-00.validation.json"])["error_code"] == "ordinary_layout_invalid_proposal_decisions"
    assert decode(witness["records"]["page-0003/attempt-00.validation.json"])["error_code"] == "ordinary_layout_proposal_coverage"


@pytest.mark.parametrize("repair_pages", [(), (3,), (1, 2, 3)])
def test_zero_last_and_all_pages_repaired_are_bounded(tmp_path, monkeypatch, repair_pages):
    def damage(page, ordinal, proposal, *_):
        if page in repair_pages and ordinal == 0:
            legacy.invalid_decision(proposal)
    case = legacy.normal_start(tmp_path, monkeypatch, damage=damage)
    expected = [p for p in (1, 2, 3) for _ in range(2 if p in repair_pages else 1)]
    assert [p for p, _ in case.calls] == expected
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    witness, kwargs = legacy.witness_context(case)
    assert proof.verify_witness(witness, **kwargs)[1]["provider_dispatch_count"] == len(expected)
    assert len([p for p in witness["records"] if p.endswith("repair_slot.json")]) == len(repair_pages)


def test_v11_still_stops_on_second_distinct_invalid_page(tmp_path, monkeypatch):
    case = legacy.normal_start(tmp_path, monkeypatch, damage=mixed_damage,
        saved_policy=auto._bounded_page_reproposal_v11_policy())
    assert [p for p, _ in case.calls] == [1, 2, 2, 3]
    assert case.job["result"]["automatic_layout"]["status"] == "raw_fallback"
    assert (case.operation / "attempts/repair_slot.json").is_file()
    assert not (case.operation / "attempts/page-0003/attempt-01.intent.json").exists()
    assert not (case.operation / "page-0003.response.json").exists()


def test_single_page_footer_repair_has_two_calls_and_unchanged_footer_guidance(tmp_path, monkeypatch):
    def damage(page, ordinal, proposal, *_):
        if ordinal == 0:
            invalid_footer(proposal)
    case = legacy.normal_start(tmp_path, monkeypatch, damage=damage, page_count=1)
    assert [page for page, _ in case.calls] == [1, 1]
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    witness, kwargs = legacy.witness_context(case)
    assert proof.verify_witness(witness, **kwargs)[1]["provider_dispatch_count"] == 2
    first, replacement = case.calls[0][1], case.calls[1][1]
    assert replacement["instructions"] == first["instructions"] + proof.INSTRUCTIONS + proof.FOOTER_CONSTRAINT_INSTRUCTIONS
    intent = decode(witness["records"]["page-0001/attempt-01.intent.json"])
    feedback = decode(intent["request"]["prompt_text"])["proposal_repair"]
    assert feedback["version"] == proof.POLICY_V2
    assert feedback["error_code"] == "ordinary_layout_invalid_source_footer_evidence"


def test_invalid_replacement_stops_without_third_attempt_or_later_page(tmp_path, monkeypatch):
    def damage(page, ordinal, proposal, *_):
        if page == 2:
            legacy.invalid_decision(proposal)
    case = legacy.normal_start(tmp_path, monkeypatch, damage=damage)
    assert [p for p, _ in case.calls] == [1, 2, 2]
    assert case.job["result"]["automatic_layout"]["status"] == "raw_fallback"
    assert not (case.operation / "attempts/page-0002/attempt-02.intent.json").exists()
    assert not (case.operation / "attempts/page-0003").exists()
    assert case.job["actions"]["recover_layout"] is False
    before = len(case.calls)
    with pytest.raises(OrdinaryLayoutError, match="unsupported_policy"):
        auto.run_automatic_layout(case.manager, case.app.state.ordinary_layouts._accounting,
            case.job["job_id"], auto.manual_automatic_layout_policy(), recovery_old_policy=auto._per_page_reproposal_v12_policy())
    assert len(case.calls) == before


@pytest.mark.parametrize("fault", ["root_slot", "slot_swapped", "slot_missing", "slot_on_valid", "slot_intent",
    "slot_version", "third_attempt", "missing_zero_witness", "mixed_version", "native_duplicate", "select_failed"])
def test_slot_version_and_native_forgery_reject(two_repaired_pages, fault):
    from legalpdf_translate.usage_accounting import _state_fingerprint
    witness, kwargs = legacy.witness_context(two_repaired_pages)
    records = witness["records"]
    name = "page-0002/repair_slot.json"
    if fault == "root_slot":
        records["repair_slot.json"] = records.pop(name)
    elif fault == "slot_swapped":
        records[name], records["page-0003/repair_slot.json"] = records["page-0003/repair_slot.json"], records[name]
    elif fault == "slot_missing": records.pop(name)
    elif fault == "slot_on_valid": records["page-0001/repair_slot.json"] = records[name]
    elif fault in {"slot_intent", "slot_version"}:
        value = decode(records[name])
        value["repair_intent_sha256" if fault == "slot_intent" else "version"] = "wrong"
        records[name] = encode(value).decode()
    elif fault == "third_attempt": records["page-0002/attempt-02.intent.json"] = records["page-0002/attempt-01.intent.json"]
    elif fault == "missing_zero_witness": records.pop("page-0001/attempt-00.intent.json")
    elif fault == "mixed_version": witness["version"] = proof.VERSION
    elif fault == "native_duplicate":
        witness["journal"]["events"].extend(deepcopy(witness["journal"]["events"][-2:]))
        witness["journal"]["fingerprint"] = _state_fingerprint(witness["journal"])
    else:
        value = decode(records["page-0002/selection.json"])
        value["ordinal"] = 0
        records["page-0002/selection.json"] = encode(value).decode()
    with pytest.raises((OrdinaryLayoutError, ValueError)):
        proof.verify_witness(witness, **kwargs)


@pytest.mark.parametrize("fault", ["local_reconstruct", "missing_repair_intent", "missing_repair_raw", "wrong_alias", "missing_next_page"])
def test_recovery_never_resends_and_only_reconstructs_settled_local_records(two_repaired_pages, tmp_path, fault):
    case = two_repaired_pages
    operation = tmp_path / "operation"
    shutil.copytree(case.operation, operation)
    witness, kwargs = legacy.witness_context(case)
    if fault == "local_reconstruct":
        for relative in ["page-0003.response.json", "attempts/page-0003/attempt-01.validation.json", "attempts/page-0003/selection.json"]:
            (operation / relative).unlink()
        restored, _, _ = proof.operation_witness(operation, **kwargs, restore_aliases=True, seal=True)
        assert restored == witness
    else:
        target = {"missing_repair_intent": "attempts/page-0003/attempt-01.intent.json",
                  "missing_repair_raw": "attempts/page-0003/attempt-01.response.json",
                  "missing_next_page": "attempts/page-0003/attempt-00.intent.json"}.get(fault)
        if target: (operation / target).unlink()
        else: (operation / "page-0003.response.json").write_bytes(b"{}")
        with pytest.raises((OrdinaryLayoutError, FileNotFoundError)):
            proof.operation_witness(operation, **kwargs, restore_aliases=True, seal=True)
    assert len(case.calls) == 5


@pytest.mark.parametrize("restart", [False, True], ids=["same_manager", "new_manager"])
def test_saved_v11_actual_binding_resume_and_rebuild_remain_same_under_v12(tmp_path, monkeypatch, restart):
    from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
    case = legacy.normal_start(tmp_path, monkeypatch,
        damage=lambda p, n, proposal, *_: legacy.invalid_decision(proposal) if p == 2 and n == 0 else None,
        saved_policy=auto._bounded_page_reproposal_v11_policy())
    assert auto.frozen_automatic_layout_policy() == auto._per_page_reproposal_v12_policy()
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"
    before = {p: p.read_bytes() for p in case.operation.rglob("*") if p.is_file() and p.suffix != ".lock"}
    def forbidden(*args, **kwargs): pytest.fail("Saved operation attempted a provider or new accounting capacity")
    manager = OrdinaryLayoutManager(case.manager.service.root.parents[2], mode="shadow", workspace_id="fictional",
        job_resolver=case.manager.job_resolver, provider_factory=forbidden, accounting_factory=forbidden,
        suggestion_policy=forbidden) if restart else case.manager
    result = auto.run_automatic_layout(manager, case.app.state.ordinary_layouts._accounting,
        case.job["job_id"], auto._bounded_page_reproposal_v11_policy())
    assert result["reused_durable_candidate"] and len(case.calls) == 4
    rebuilt = auto.run_completed_unreviewed_rebuild(manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert rebuilt["reused_durable_candidate"] and rebuilt["sha256"] == result["sha256"]
    assert all(p.read_bytes() == raw for p, raw in before.items())


def test_v12_completed_rebuild_reuses_exact_policy_and_spend(two_repaired_pages):
    case = two_repaired_pages
    result = auto.run_completed_unreviewed_rebuild(case.manager, case.app.state.ordinary_layouts._accounting, case.job["job_id"])
    assert result["reused_durable_candidate"] and len(case.calls) == 5
    assert result["sha256"] == case.job["result"]["automatic_layout"]["sha256"]


def test_initial_requests_old_descriptor_and_versioned_capacity_are_distinct():
    _, view, _, old = legacy.synthetic()
    new = proof.expected_policy(1, proof.POLICY_V2)
    assert proof.page_request(view, 1, old) == proof.page_request(view, 1, new)
    assert proof.descriptor()["global_extra_calls"] == 1
    assert proof.descriptor()["ledger_version"] == proof.VERSION
    assert "global_extra_calls" not in proof.descriptor(proof.POLICY_V2)
    assert proof.descriptor(proof.POLICY_V2)["ledger_version"] == proof.VERSION_V2
    assert proof.expected_policy(3)["max_operation_cost_usd"] == "4.592"
    assert Decimal(proof.expected_policy(3, proof.POLICY_V2)["max_operation_cost_usd"]) == Decimal("6.888")
    assert auto._source_folio_direction_version(auto._bounded_page_reproposal_v11_policy().split(":", 1)[1]) == "numeric_run_ltr_v4"
    assert not auto.supports_manual_layout_recovery(auto._per_page_reproposal_v12_policy())
    assert auto.manual_automatic_layout_policy() == auto._protected_folio_bridges_v10_policy()


@pytest.mark.parametrize("count", [1, 3, 100])
def test_record_count_bound_is_selected_page_count_and_v1_stays_610(tmp_path, count):
    base = {"version": proof.VERSION_V2, "policy": {proof.KEY: proof.POLICY_V2},
            "identity": {"selected_pages": list(range(1, count + 1))}}
    assert proof.record_limit(base) == 10 * count
    assert proof.record_limit({"version": proof.VERSION, "policy": {proof.KEY: proof.POLICY}}) == 610
    folder = tmp_path / "operation/attempts"
    folder.mkdir(parents=True)
    (folder / "manifest.json").write_bytes(encode(base))
    journal = folder.parent / "accounting/dispatch_accounting.json"
    journal.parent.mkdir()
    journal.write_bytes(b"{}")
    for i in range(10 * count): (folder / f"record-{i}.json").write_bytes(b"{}")
    assert len(proof._load(folder.parent)["records"]) == 10 * count
    (folder / "extra.json").write_bytes(b"{}")
    with pytest.raises(OrdinaryLayoutError, match="ledger_changed"):
        proof._load(folder.parent)


@pytest.mark.parametrize("count", [0, 101, True, 1.0])
def test_new_policy_refuses_invalid_selected_page_counts(count):
    with pytest.raises(OrdinaryLayoutError, match="context_changed"):
        proof.expected_policy(count, proof.POLICY_V2)


@pytest.mark.parametrize("value", ["unknown", None, {}, []])
def test_unknown_capability_never_acquires_allowance(value):
    with pytest.raises(OrdinaryLayoutError, match="policy_changed"):
        proof.descriptor(value)


@pytest.mark.parametrize("repair_policy,version", [(proof.POLICY, proof.VERSION), (proof.POLICY_V2, proof.VERSION_V2)])
def test_aggregate_ledger_eight_mib_limit_stays_fail_closed(tmp_path, repair_policy, version):
    folder = tmp_path / "operation/attempts"
    folder.mkdir(parents=True)
    base = {"version": version, "policy": {proof.KEY: repair_policy}, "identity": {"selected_pages": [1]}}
    (folder / "manifest.json").write_bytes(encode(base))
    for i in range(2): (folder / f"large-{i}.json").write_bytes(b" " * (4 * 1024 * 1024))
    with pytest.raises(OrdinaryLayoutError, match="ledger_changed"):
        proof._load(folder.parent)


@pytest.mark.parametrize("kind", ["connection", "incomplete", "refusal", "unknown_usage", "cancel", "stale", "reserved_capacity"])
def test_v12_keeps_transport_unknown_cancel_stale_and_hardcap_stops(tmp_path, monkeypatch, kind):
    # The inherited test exercises its actual mocked normal Start and all assertions
    # under this module's fresh V12 default, without the old module's V11 fixture.
    legacy.test_transport_cancel_staleness_and_unavailable_capacity_never_buy_replacement(tmp_path, monkeypatch, kind)


def test_v12_both_between_call_deadline_guards_use_saved_2n_envelope(tmp_path, monkeypatch):
    from legalpdf_translate import ordinary_layout_manager as module
    calls = iter([0])
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: next(calls, 6 * 480 + 31)))
    case = legacy.normal_start(tmp_path, monkeypatch)
    assert case.calls == [] and case.job["result"]["automatic_layout"]["status"] == "raw_fallback"


def test_v12_accepts_between_call_time_above_old_n_plus_one_limit(tmp_path, monkeypatch):
    from legalpdf_translate import ordinary_layout_manager as module
    calls = iter([0])
    monkeypatch.setattr(module, "time", SimpleNamespace(monotonic=lambda: next(calls, 5 * 480)))
    case = legacy.normal_start(tmp_path, monkeypatch)
    assert [page for page, _ in case.calls] == [1, 2, 3]
    assert case.job["result"]["automatic_layout"]["status"] == "automatic_unreviewed"


@pytest.mark.parametrize("inner", ["downgrade", "absent", "null"])
def test_v12_trusted_outer_policy_downgrade_requires_its_mandatory_witness(two_repaired_pages, inner):
    legacy.test_trusted_v11_policy_always_requires_matching_inner_policy_and_witness(two_repaired_pages, inner)


def test_v12_actual_saved_reader_build_and_standalone_reject_downgrade(two_repaired_pages):
    legacy.test_actual_saved_reader_public_build_and_standalone_checks_reject_nested_policy_downgrade(two_repaired_pages)
