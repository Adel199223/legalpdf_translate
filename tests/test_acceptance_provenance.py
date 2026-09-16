"""Synthetic physical evidence and externally supplied approvals; no transports."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pytest

from legalpdf_translate.acceptance_budget import AcceptanceBudgetError, LegacyAcceptanceBudget
from legalpdf_translate.acceptance_provenance import AcceptanceProvenanceError, request_fingerprint
from legalpdf_translate.budget_reservations import atomic_json, fingerprint
from legalpdf_translate.usage_accounting import DispatchAccounting
from tests.test_acceptance_budget_adapter import _write_fixture, _request, _proof, DISPATCH_SCOPE, REQUEST_HASH


def _save(path, payload):
    payload.pop("fingerprint", None)
    payload["fingerprint"] = fingerprint(payload)
    atomic_json(path, payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _budget(fixture, amendment_path=None, digest=None):
    ledger, path, sha, identity, execution, prices, _ = fixture
    return LegacyAcceptanceBudget(ledger, amendment_path=amendment_path or path,
        expected_amendment_sha256=digest or sha, run_identity=identity,
        execution_identity=execution, pricing_snapshot=prices)


def _details(budget, purpose="translation", request=None):
    request = request or _request()
    return {"provider": "openai", "purpose": purpose, "requested_model": "model-a",
        "effort": "high", "page_number": 1, "attempt": 1,
        "request_hash": request_fingerprint(request), **DISPATCH_SCOPE,
        "bounds": {**dict(budget.dispatch_limits[f"openai:{purpose}"]), "input_bytes": 100, "image_count": 0}}


def _verify(budget, request=None, purpose="translation"):
    if not budget.runtime_context_bound:
        budget.bind_runtime_context(config={"synthetic": True}, preferences={"unchanged": True})
    budget.verify_dispatch(request=request or _request(), provider="openai", purpose=purpose,
        page_number=1, attempt=1, **DISPATCH_SCOPE)


@pytest.mark.parametrize("label", ["source", "preferences", "code_manifest", "config_manifest", "code_member", "config_member"])
def test_physical_byte_drift_after_construction_blocks_without_ledger_write(tmp_path, label):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    provenance = budget.amendment["provenance"]
    if label.endswith("_member"):
        manifest = json.loads(Path(provenance[label.replace("_member", "_manifest")]["path"]).read_bytes())
        target = Path(manifest["files"][0]["path"])
    else:
        target = Path(provenance[label]["path"])
    target.write_bytes(target.read_bytes() + b" changed")
    before = fixture[0].read_bytes()
    with pytest.raises((AcceptanceBudgetError, AcceptanceProvenanceError)):
        _verify(budget)
    assert fixture[0].read_bytes() == before


@pytest.mark.parametrize("change", ["model", "effort", "tier", "output", "input", "route", "endpoint", "page", "purpose", "attempt", "scope"])
def test_final_request_or_route_drift_has_no_dispatch_authority(tmp_path, change):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    request = _request()
    arguments = dict(request=request, provider="openai", purpose="translation", page_number=1, attempt=1, **DISPATCH_SCOPE)
    if change == "model": request["model"] = "different"
    elif change == "effort": request["reasoning"]["effort"] = "medium"
    elif change == "tier": request["service_tier"] = "priority"
    elif change == "output": request["max_output_tokens"] = 999
    elif change == "input": request["input"] += " changed"
    elif change == "route": arguments["route"] = "chat.completions.create"
    elif change == "endpoint": arguments["base_url"] = "https://unapproved.invalid/v1"
    elif change == "page": arguments["page_number"] = 2
    elif change == "purpose": arguments["purpose"] = "ocr"
    elif change == "attempt": arguments["attempt"] = 2
    elif change == "scope": arguments["billing_scope"] = "different"
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError): budget.verify_dispatch(**arguments)
    assert fixture[0].read_bytes() == before


def test_reservation_requires_one_use_proof_and_recheck_owns_exact_request(tmp_path):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    with pytest.raises(AcceptanceBudgetError, match="one-use"):
        budget.reserve("no-proof", "0.02", _details(budget))
    _verify(budget)
    budget.reserve("owned", "0.02", _details(budget))
    budget.recheck_dispatch("owned", request=_request(), provider="openai", purpose="translation",
        page_number=1, attempt=1, **DISPATCH_SCOPE)
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError, match="changed before"):
        budget.recheck_dispatch("owned", request={**_request(), "input": "changed"},
            provider="openai", purpose="translation", page_number=1, attempt=1, **DISPATCH_SCOPE)
    assert fixture[0].read_bytes() == before
    assert Decimal(budget.status()["held_usd"]) == Decimal("0.02")


def _next_amendment(fixture, *, purpose="correction"):
    ledger, original, _, _, _, _, _ = fixture
    amendment = json.loads(original.read_bytes())
    state = json.loads(ledger.read_bytes())
    amendment["prior_amendments"] = state["acceptance_campaigns"][amendment["campaign_id"]]["amendments"]
    amendment["prior_reservations_fingerprint"] = fingerprint({key: row for key, row in state["reservations"].items()
        if row.get("execution", {}).get("campaign_id") == amendment["campaign_id"]})
    limit = amendment["dispatch_limits"].pop("openai:translation")
    request = {**_request(), "input": "separately approved synthetic correction"}
    limit["allowed_request_hashes"] = [request_fingerprint(request)]
    if purpose == "correction":
        pending = {"version": 1, "identity": {"synthetic": True}, "payload": {"request": request}}
        pending["sha256"] = fingerprint(pending)
        pending_path = original.parent / "synthetic-correction.pending.json"
        atomic_json(pending_path, pending)
        limit["approved_calls"] = [{"page_number": 1, "attempt": 1,
            "request_hash": request_fingerprint(request), "pending_correction_sha256": pending["sha256"]}]
        limit["pending_correction_files"] = {pending["sha256"]: {"path": str(pending_path.resolve()),
            "sha256": hashlib.sha256(pending_path.read_bytes()).hexdigest()}}
    amendment["dispatch_limits"][f"openai:{purpose}"] = limit
    return amendment, request


def _multi_call_fixture(tmp_path):
    fixture = list(_write_fixture(tmp_path))
    amendment = json.loads(fixture[1].read_bytes())
    amendment["case"]["max_calls"] = 2
    fixture[2] = _save(fixture[1], amendment)
    return fixture


def test_new_correction_amendment_resumes_same_journal_without_rebuying_primary(tmp_path):
    fixture = _multi_call_fixture(tmp_path)
    first = _budget(fixture)
    accounting = DispatchAccounting(tmp_path / "run", run_identity=fixture[3],
        pricing_snapshot=fixture[5], budget_context=first, dispatch_limits=first.dispatch_limits)
    _verify(first)
    ticket = accounting.begin(**_details(first))
    accounting.finish(ticket, outcome="succeeded", actual_model="model-a", actual_service_tier="default",
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}, response_id="primary")
    before_rows = deepcopy(json.loads(fixture[0].read_bytes())["reservations"])
    amendment, request = _next_amendment(fixture)
    correction_path = tmp_path / "externally-approved-correction.json"
    digest = _save(correction_path, amendment)
    second = _budget(fixture, correction_path, digest)
    assert second.binding_identity == first.binding_identity
    assert second.continuation_identity == first.continuation_identity
    resumed = DispatchAccounting(tmp_path / "run", run_identity=fixture[3],
        pricing_snapshot=fixture[5], budget_context=second, dispatch_limits=second.dispatch_limits)
    _verify(second, request, "correction")
    correction = resumed.begin(**_details(second, "correction", request))
    resumed.finish(correction, outcome="succeeded", actual_model="model-a", actual_service_tier="default",
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}, response_id="correction")
    assert resumed.summary()["provider_dispatch_count"] == 2
    state = json.loads(fixture[0].read_bytes())
    for key, row in before_rows.items(): assert state["reservations"][key] == row
    assert len(state["acceptance_campaigns"][first.campaign_id]["amendments"]) == 2
    assert state["reservations"][ticket.call_id]["execution"]["authorization_sha256"] == fixture[2]
    assert state["reservations"][correction.call_id]["execution"]["authorization_sha256"] == digest
    with pytest.raises(AcceptanceBudgetError, match="superseded"):
        first.status()


@pytest.mark.parametrize("mutation", ["cap", "case_cap", "max_calls", "prior_charges", "duplicate", "revoked"])
def test_amendment_cannot_reset_caps_history_or_approval(tmp_path, mutation):
    fixture = _multi_call_fixture(tmp_path)
    first = _budget(fixture)
    _verify(first)
    first.reserve("primary", "0.02", _details(first))
    first.finalize("primary", "0.001", {"outcome": "succeeded"})
    amendment, _ = _next_amendment(fixture)
    if mutation == "cap": amendment["campaign_cap_usd"] = "0.2"
    elif mutation == "case_cap": amendment["case"]["ceiling_usd"] = "0.09"
    elif mutation == "max_calls": amendment["case"]["max_calls"] = 3
    elif mutation == "prior_charges": amendment["prior_reservations_fingerprint"] = fingerprint({})
    elif mutation == "duplicate": amendment["prior_amendments"] *= 2
    elif mutation == "revoked": amendment["approval_status"] = "revoked"
    path = tmp_path / "mismatched-amendment.json"
    digest = _save(path, amendment)
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError): _budget(fixture, path, digest)
    assert fixture[0].read_bytes() == before


def test_uncertain_primary_is_not_released_by_new_correction_approval(tmp_path):
    fixture = _multi_call_fixture(tmp_path)
    first = _budget(fixture)
    _verify(first)
    first.reserve("primary", "0.02", _details(first))
    first.finalize("primary", None, {"outcome": "timeout"})
    amendment, request = _next_amendment(fixture)
    path = tmp_path / "correction-does-not-release.json"
    second = _budget(fixture, path, _save(path, amendment))
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError): _verify(second, request, "correction")
    assert fixture[0].read_bytes() == before
    assert Decimal(second.status()["held_usd"]) == Decimal("0.02")


def test_legacy_amendment_inspection_does_not_enable_dispatch(tmp_path):
    fixture = list(_write_fixture(tmp_path))
    amendment = json.loads(fixture[1].read_bytes())
    # Legacy pricing metadata can still be inspected but cannot create authority.
    amendment["schema_version"] = 1
    raw_prices = fixture[5].to_mapping()
    row = next(iter(raw_prices["models"].values()))
    for key in ("service_tier", "billing_scope", "currency"): row.pop(key, None)
    raw_prices["models"] = {"openai:model-a": row}
    from legalpdf_translate.cost_guardrails import PricingSnapshot
    fixture[5] = PricingSnapshot.from_mapping(raw_prices)
    amendment["pricing_snapshot"] = fixture[5].metadata()
    fixture[2] = _save(fixture[1], amendment)
    legacy = _budget(fixture)
    before = fixture[0].read_bytes()
    assert not legacy.dispatch_enabled
    with pytest.raises(AcceptanceBudgetError, match="read-only"):
        legacy.reserve("legacy-no-proof", "0.02", _details(legacy))
    assert fixture[0].read_bytes() == before


def test_competing_append_amendments_cannot_both_reserve_or_expand_allowance(tmp_path):
    fixture = _multi_call_fixture(tmp_path)
    first = _budget(fixture)
    _verify(first)
    first.reserve("primary", "0.02", _details(first))
    first.finalize("primary", "0.001", {"outcome": "succeeded"})
    amendment, request = _next_amendment(fixture)
    candidates = []
    for index in range(2):
        candidate = deepcopy(amendment)
        candidate["approval_reference"] = f"independent-fixture-approval-{index}"
        path = tmp_path / f"competing-{index}.json"
        candidates.append(_budget(fixture, path, _save(path, candidate)))
    for budget in candidates: _verify(budget, request, "correction")

    def reserve(index):
        try:
            candidates[index].reserve(f"competing-{index}", "0.02", _details(candidates[index], "correction", request))
            return True
        except AcceptanceBudgetError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(reserve, range(2)))
    assert sorted(outcomes) == [False, True]
    state = json.loads(fixture[0].read_bytes())
    assert state["cap_usd"] == "10"
    assert len(state["reservations"]) == 3  # Original historical, primary, one correction.
    assert len(state["acceptance_campaigns"][first.campaign_id]["amendments"]) == 2


@pytest.mark.parametrize("target", ["amendment", "pending", "limits"])
def test_postapproval_drift_cannot_consume_preverified_dispatch(tmp_path, target):
    fixture = _multi_call_fixture(tmp_path)
    first = _budget(fixture)
    _verify(first)
    first.reserve("primary", "0.02", _details(first))
    first.finalize("primary", "0.001", {"outcome": "succeeded"})
    amendment, request = _next_amendment(fixture)
    path = tmp_path / "approved-correction.json"
    second = _budget(fixture, path, _save(path, amendment))
    _verify(second, request, "correction")
    before = fixture[0].read_bytes()
    if target == "amendment":
        changed = json.loads(path.read_bytes())
        changed["approval_status"] = "revoked"
        _save(path, changed)
    elif target == "pending":
        entry = next(iter(second.dispatch_limits["openai:correction"]["pending_correction_files"].values()))
        Path(entry["path"]).write_bytes(b"changed private synthetic pending evidence")
    else:
        second.dispatch_limits["openai:correction"]["allowed_base_urls"].append("https://drift.invalid")
    with pytest.raises((AcceptanceBudgetError, AcceptanceProvenanceError)):
        second.reserve("changed", "0.02", _details(second, "correction", request))
    assert fixture[0].read_bytes() == before


def test_pending_permission_query_requires_exact_envelope_identity(tmp_path):
    fixture = _multi_call_fixture(tmp_path)
    first = _budget(fixture)
    _verify(first)
    first.reserve("primary", "0.02", _details(first))
    first.finalize("primary", "0.001", {"outcome": "succeeded"})
    amendment, request = _next_amendment(fixture)
    path = tmp_path / "approved-correction.json"
    second = _budget(fixture, path, _save(path, amendment))
    second.bind_runtime_context(config={"synthetic": True}, preferences={"unchanged": True})
    arguments = {key: value for key, value in _details(second, "correction", request).items() if key != "bounds"}
    pending = second.dispatch_limits["openai:correction"]["approved_calls"][0]["pending_correction_sha256"]
    before = fixture[0].read_bytes()
    assert second.permits_dispatch(**arguments, pending_correction_sha256=pending)
    assert not second.permits_dispatch(**arguments, pending_correction_sha256="f" * 64)
    assert fixture[0].read_bytes() == before


def test_finalized_primary_charge_tamper_cannot_be_hidden_by_rehashing_ledger(tmp_path):
    fixture = _multi_call_fixture(tmp_path)
    first = _budget(fixture)
    _verify(first)
    first.reserve("primary", "0.02", _details(first))
    first.finalize("primary", "0.001", {"outcome": "succeeded"})
    amendment, _ = _next_amendment(fixture)
    path = tmp_path / "approved-before-tamper.json"
    digest = _save(path, amendment)
    state = json.loads(fixture[0].read_bytes())
    state["reservations"]["primary"]["actual_usd"] = "0"
    _save(fixture[0], state)
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError, match="charged campaign history"):
        _budget(fixture, path, digest)
    assert fixture[0].read_bytes() == before


def test_manual_block_after_reservation_stops_immediate_presend_recheck(tmp_path):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    _verify(budget)
    budget.reserve("owned", "0.02", _details(budget))
    state = json.loads(fixture[0].read_bytes())
    state["blocked_reason"] = "manual_reconciliation_required"
    _save(fixture[0], state)
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError, match="became blocked"):
        budget.recheck_dispatch("owned", request=_request(), provider="openai", purpose="translation",
            page_number=1, attempt=1, **DISPATCH_SCOPE)
    assert fixture[0].read_bytes() == before
    assert Decimal(budget.status()["held_usd"]) == Decimal("0.02")


@pytest.mark.parametrize("mutation", ["missing_member", "dummy_only", "other_package"])
def test_manifest_cannot_substitute_a_declared_code_subset_for_executing_package(tmp_path, mutation):
    fixture = list(_write_fixture(tmp_path))
    amendment = json.loads(fixture[1].read_bytes())
    entry = amendment["provenance"]["code_manifest"]
    manifest = json.loads(Path(entry["path"]).read_bytes())
    if mutation == "missing_member":
        manifest["files"].pop()
    elif mutation == "dummy_only":
        manifest["files"] = manifest["files"][:1]
    else:
        other = tmp_path / "alternate" / "legalpdf_translate" / "other.py"
        other.parent.mkdir(parents=True)
        other.write_bytes(b"synthetic alternate package")
        manifest["files"].append({"path": str(other.resolve()), "sha256": hashlib.sha256(other.read_bytes()).hexdigest()})
    atomic_json(Path(entry["path"]), manifest)
    entry["sha256"] = hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest()
    fixture[4]["code_manifest_sha256"] = entry["sha256"]
    amendment["execution_identity"] = fixture[4]
    fixture[2] = _save(fixture[1], amendment)
    with pytest.raises(AcceptanceProvenanceError, match="package"):
        _budget(fixture)


def test_dispatch_without_actual_effective_context_is_not_authorized(tmp_path):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError, match="external acceptance approval"):
        budget.verify_dispatch(request=_request(), provider="openai", purpose="translation",
            page_number=1, attempt=1, **DISPATCH_SCOPE)
    assert not budget.runtime_context_bound
    assert fixture[0].read_bytes() == before


@pytest.mark.parametrize("target", ["config", "preferences"])
def test_effective_context_must_match_both_initially_and_after_inmemory_drift(tmp_path, target):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    config, preferences = {"synthetic": True}, {"unchanged": True}
    changed = {"synthetic": False} if target == "config" else {"unchanged": False}
    with pytest.raises(AcceptanceProvenanceError, match="differ.*from approval"):
        budget.bind_runtime_context(config=changed if target == "config" else config,
            preferences=changed if target == "preferences" else preferences)
    budget.bind_runtime_context(config=lambda: config, preferences=lambda: preferences)
    if target == "config": config["synthetic"] = False
    else: preferences["unchanged"] = False
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError): _verify(budget)
    assert fixture[0].read_bytes() == before


def test_context_drift_after_reservation_is_rechecked_before_send(tmp_path):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    config, preferences = {"synthetic": True}, {"unchanged": True}
    budget.bind_runtime_context(config=lambda: config, preferences=lambda: preferences)
    _verify(budget)
    budget.reserve("owned", "0.02", _details(budget))
    config["synthetic"] = False
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceProvenanceError, match="runtime configuration"):
        budget.recheck_dispatch("owned", request=_request(), provider="openai", purpose="translation",
            page_number=1, attempt=1, **DISPATCH_SCOPE)
    assert fixture[0].read_bytes() == before


def test_rewriting_externally_supplied_digest_cannot_hide_revocation(tmp_path):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    _verify(budget)
    amendment = json.loads(fixture[1].read_bytes())
    amendment["approval_status"] = "revoked"
    budget.expected_amendment_sha256 = _save(fixture[1], amendment)
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError, match="Immutable external"):
        budget.reserve("revoked", "0.02", _details(budget))
    assert fixture[0].read_bytes() == before


def test_preflight_requires_requested_tier_price_even_when_only_downgrade_allowed(tmp_path):
    fixture = list(_write_fixture(tmp_path))
    amendment = json.loads(fixture[1].read_bytes())
    amendment["dispatch_limits"]["openai:translation"]["requested_service_tier"] = "priority"
    fixture[2] = _save(fixture[1], amendment)
    with pytest.raises(AcceptanceBudgetError, match="no verified price"):
        _budget(fixture)


def test_canonical_config_excludes_only_resume_and_preserves_enum_path_values(tmp_path):
    from dataclasses import dataclass, replace
    from enum import Enum
    from legalpdf_translate.acceptance_provenance import canonical_run_config
    class Mode(str, Enum):
        OFF = "off"
    @dataclass
    class Config:
        path: Path
        mode: Mode = Mode.OFF
        resume: bool = False
        model: str = "unchanged-model"
    config = Config(tmp_path / "source.pdf")
    result = canonical_run_config(config)
    assert result == {"path": str(config.path), "mode": "off", "model": "unchanged-model"}
    assert canonical_run_config(replace(config, resume=True)) == result
    assert canonical_run_config(replace(config, model="different")) != result


@pytest.mark.parametrize("target", ["path", "amendment_path", "cap_usd", "campaign_cap_usd", "amendment_fingerprint", "hard"])
def test_external_authority_controls_are_frozen_after_independent_approval(tmp_path, target):
    fixture = _write_fixture(tmp_path)
    budget = _budget(fixture)
    _verify(budget)
    if target in {"path", "amendment_path"}:
        setattr(budget, target, tmp_path / "different.json")
    elif target in {"cap_usd", "campaign_cap_usd"}:
        setattr(budget, target, Decimal("999"))
    elif target == "amendment_fingerprint":
        budget.amendment_fingerprint = "f" * 64
    else:
        budget.hard = False
    before = fixture[0].read_bytes()
    with pytest.raises(AcceptanceBudgetError, match="Immutable external"):
        budget.reserve("mutated-control", "0.02", _details(budget))
    assert fixture[0].read_bytes() == before
