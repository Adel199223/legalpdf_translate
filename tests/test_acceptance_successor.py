"""Successor lineage fixtures are fictional; no real ledger/operations are read."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from dataclasses import replace

import pytest

from legalpdf_translate.acceptance_budget import AcceptanceBudgetError, LegacyAcceptanceBudget, stable_acceptance_run_identity
from legalpdf_translate.acceptance_successor import validate_successor_scope, SUCCESSOR_SCOPE_VERSION
from legalpdf_translate.acceptance_provenance import request_fingerprint, canonical_run_config
from legalpdf_translate.budget_reservations import fingerprint
from legalpdf_translate.translation_structure import request_fingerprint as page_fingerprint
from tests.test_acceptance_continuation import offline
from tests.test_acceptance_campaign_integration import _campaign, _approve, _forbid_source_acquisition
from tests.test_acceptance_budget_adapter import _provenance
from tests.test_structured_acceptance_run import invoke
from tooling.structured_acceptance_prepare import prepare_reviewed_requests


def write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def fixture(tmp_path):
    original = {"source_sha256": "d" * 64, "context_hash": "c" * 64, "language": "AR", "model": "gpt-5.2",
        "selection": [1, 2], "protocol": "legal_blocks_v2",
        "protocol_identity": {"protocol": "legal_blocks_v2", "fingerprint": "a" * 64}}
    current = deepcopy(original)
    current["protocol_identity"]["fingerprint"] = "b" * 64
    predecessors = {"root-case": {"stable_run_identity_hash": fingerprint(original),
        "case_max_calls": 2, "case_ceiling_usd": "2"}}
    rows = {"paid-2": {"status": "finalized", "actual_usd": "0.02",
        "execution": {"campaign_id": "campaign", "case_id": "root-case", "page_number": 2, "request_hash": "paid"}}}
    state = {"reservations": rows, "blocked_reason": None,
        "acceptance_campaigns": {"campaign": {"cases": deepcopy(predecessors)}}}
    budget = SimpleNamespace(campaign_id="campaign", case={"case_id": "successor", "max_calls": 1, "ceiling_usd": "1.98"},
        run_identity=current, execution_identity={"code_manifest_sha256": "code", "config_manifest_sha256": "config"},
        dispatch_limits={"openai:translation": {"allowed_pages": [1], "max_calls_per_page": 1, "max_attempts": 1}},
        _campaign_binding=lambda: {"original_ledger": True}, _load_ledger_unlocked=lambda: deepcopy(state),
        lock_path=tmp_path / "ledger.lock")
    scope = {"version": SUCCESSOR_SCOPE_VERSION, "campaign_id": budget.campaign_id,
        "ledger_identity": budget._campaign_binding(), "root_case_id": "root-case", "root_run_identity": original,
        "predecessor_cases": predecessors, "predecessor_reservations_fingerprint": fingerprint(rows),
        "successor_case": deepcopy(budget.case), "successor_run_identity": deepcopy(current),
        "execution_projection": {"code_manifest_sha256": "code"}, "eligible_pages": [1], "excluded_pages": [2],
        "consumed_intent_pages": [], "no_contact_dispositions": []}
    files = []
    return SimpleNamespace(root=tmp_path, budget=budget, scope=scope, state=state, files=files)


def commit(case):
    entry = write(case.root / "successor.json", case.scope)
    manifest = write(case.root / "manifest.json", {"files": [entry, *case.files]})
    case.budget.amendment = {"provenance": {"config_manifest": manifest}}
    return entry


def no_contact(case):
    root = case.root / "old-operation"
    prompt = json.dumps({"page": 1, "total_pages": 2, "blocks": [{"id": "p0001_b0001", "text": "Fictional source."}]})
    logical = {"prompt_text": prompt, "effort": "high", "instructions": "Fictional test."}
    final = {"input": prompt, "model": "gpt-5.2", "store": False}
    final_hash = request_fingerprint(final)
    prepared = write(root / "prepared.json", {"pages": [{"page_number": 1, "final_request": final,
        "final_request_sha256": final_hash, "logical_descriptor": {"request": logical,
            "page_number": 1, "model": "gpt-5.2", "purpose": "translation", "attempt": 1}}]})
    operation = write(root / "authority" / "operation.json", {"request_sha256": final_hash,
        "run_identity": case.scope["root_run_identity"], "pages": [1], "read_files": [prepared]})
    result = write(root / "result.json", {"operation_sha256": operation["sha256"],
        "sdk_calls_entered": 0, "exit_code": 2, "phase": "workflow"})
    consumed = write(root / "operation.intent.json", {"operation_sha256": operation["sha256"],
        "consumed": True, "no_automatic_replay": True})
    identity = {"page_number": 1, "full_case_pages": [1, 2],
        "campaign": fingerprint({"campaign_id": "campaign", "case_id": "root-case",
            "source_sha256": case.scope["root_run_identity"]["source_sha256"], "full_case_pages": [1, 2]}),
        "protocol": case.scope["root_run_identity"]["protocol_identity"],
        "page_fingerprint": page_fingerprint(source_blocks=json.loads(prompt)["blocks"], prompt_text=prompt,
            translation_identity=fingerprint({"run": case.scope["root_run_identity"]["protocol_identity"],
                "model": "gpt-5.2", "effort": "high"}))}
    envelope = {"version": 1, "identity": identity, "payload": {"request": logical, "approval_sha256": "a" * 64}}
    envelope["sha256"] = fingerprint(envelope)
    intent = write(root / "outputs" / "source_AR_run" / "acceptance_private" / "page_0001.primary.intent.json", envelope)
    disposition = {"page_number": 1, "operation_sha256": operation["sha256"], "request_sha256": final_hash,
        "operation_file": operation, "result_file": result, "operation_intent_file": consumed,
        "page_intent_file": intent, "prepared_requests_file": prepared,
        "provider_intent_path": str(root / "provider.intent.json"), "assurance": "trusted_runtime_no_contact_observed"}
    case.files.extend([operation, result, consumed, intent, prepared])
    case.scope.update(consumed_intent_pages=[1], no_contact_dispositions=[disposition])
    return disposition


def change_file(case, entry, transform):
    original = dict(entry)
    payload = json.loads(Path(entry["path"]).read_bytes())
    transform(payload)
    replacement = write(Path(entry["path"]), payload)
    for item in case.files:
        if item == original:
            item.update(replacement)
    entry.update(replacement)


def test_valid_residual_scope_and_no_contact_are_read_only(tmp_path):
    case = fixture(tmp_path)
    no_contact(case)
    entry = commit(case)
    before = deepcopy(case.state)
    assert validate_successor_scope(case.budget, entry) == case.scope
    assert case.state == before


@pytest.mark.parametrize("change", ["calls", "cost", "paid_page", "source", "model", "language", "selection", "history",
    "registry", "held", "excluded", "missing_disposition", "execution", "amendment_member"])
def test_invalid_lineage_never_grants_successor_scope(tmp_path, change):
    case = fixture(tmp_path)
    if change == "calls": case.budget.case["max_calls"] = case.scope["successor_case"]["max_calls"] = 2
    elif change == "cost": case.budget.case["ceiling_usd"] = case.scope["successor_case"]["ceiling_usd"] = "2"
    elif change == "paid_page": case.budget.dispatch_limits["openai:translation"]["allowed_pages"] = [1, 2]
    elif change in {"source", "model", "language", "selection"}:
        key = "source_sha256" if change == "source" else change
        value = [1, 3] if change == "selection" else "changed"
        case.budget.run_identity[key] = case.scope["successor_run_identity"][key] = value
    elif change == "history": case.state["reservations"]["paid-2"]["actual_usd"] = "0.03"
    elif change == "registry": case.state["acceptance_campaigns"]["campaign"]["cases"]["extra"] = {}
    elif change == "held": case.state["reservations"]["paid-2"]["status"] = "uncertain"
    elif change == "excluded": case.scope["excluded_pages"] = []
    elif change == "missing_disposition": case.scope["consumed_intent_pages"] = [1]
    elif change == "execution": case.scope["execution_projection"] = {}
    entry = commit(case)
    if change == "amendment_member": entry = write(case.root / "not-approved.json", case.scope)
    with pytest.raises(AcceptanceBudgetError):
        validate_successor_scope(case.budget, entry)


@pytest.mark.parametrize("change", ["sdk", "boolean_sdk", "success", "provider", "response", "request", "page_hash",
    "request_file", "traversal", "other_operation", "reservation"])
def test_no_contact_requires_exact_request_and_resolved_operation_evidence(tmp_path, change):
    case = fixture(tmp_path)
    disposition = no_contact(case)
    if change in {"sdk", "boolean_sdk", "success"}:
        key, value = ("exit_code", 0) if change == "success" else ("sdk_calls_entered", False if change == "boolean_sdk" else 1)
        change_file(case, disposition["result_file"], lambda p: p.update({key: value}))
    elif change == "provider": Path(disposition["provider_intent_path"]).write_text("{}")
    elif change == "response": Path(disposition["page_intent_file"]["path"].replace(".intent.json", ".response.json")).write_text("{}")
    elif change in {"request", "page_hash"}:
        def mutate(p):
            if change == "request": p["payload"]["request"]["prompt_text"] += " different"
            else: p["identity"]["page_fingerprint"] = "e" * 64
            p.pop("sha256")
            p["sha256"] = fingerprint(p)
        change_file(case, disposition["page_intent_file"], mutate)
    elif change == "request_file":
        change_file(case, disposition["prepared_requests_file"], lambda p: p.update(extra=True))
    elif change in {"traversal", "other_operation"}:
        entry = disposition["page_intent_file"]
        old = dict(entry)
        new_path = case.root / "elsewhere" / "outputs" / "run" / "acceptance_private" / Path(entry["path"]).name
        replacement = write(new_path, json.loads(Path(entry["path"]).read_bytes()))
        if change == "traversal":
            replacement["path"] = str(case.root / "old-operation" / ".." / new_path.relative_to(case.root))
        for item in case.files:
            if item == old: item.update(replacement)
        entry.update(replacement)
    else:
        case.state["reservations"]["outside-campaign"] = {"status": "finalized", "actual_usd": "0",
            "execution": {"campaign_id": "another", "case_id": "other", "page_number": 1,
                "request_hash": disposition["request_sha256"]}}
    with pytest.raises(AcceptanceBudgetError):
        validate_successor_scope(case.budget, commit(case))


def test_actual_successor_uses_residual_case_and_resumes_without_repaying(tmp_path, monkeypatch):
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=2, reviewed=True)
    case.sdk.max_retries = 0
    old = invoke(case, _approve(case, (2,)))
    assert old.completed_pages == 1 and len(case.sdk.requests) == 1
    original_rows = json.loads(case.ledger.read_bytes())["reservations"]
    state = json.loads(case.ledger.read_bytes())
    root_id, original = case.amendment["case"]["case_id"], stable_acceptance_run_identity(case.identity)
    predecessors = state["acceptance_campaigns"][case.amendment["campaign_id"]]["cases"]
    prior = {k: v for k, v in original_rows.items() if v.get("execution", {}).get("campaign_id") == case.amendment["campaign_id"]}
    case.config = replace(case.config, output_dir=tmp_path / "successor-output")
    case.config.output_dir.mkdir()
    limits = {"requested_service_tier": "default", "max_input_tokens": 50000, "max_output_tokens": 24000}
    prep = prepare_reviewed_requests(config=case.config, preferences={}, campaign_id=case.amendment["campaign_id"],
        case_id="successor", eligible_pages=(1,), source_review_json=Path(case.review_entry["path"]).read_text(),
        reviewed_source_evidence=case.reviewed_case.evidence, source_review_guard=lambda: None,
        dispatch_limits=limits, directory=tmp_path / "new-prepared")
    case.identity = prep["run_identity"]
    case.hashes = {1: prep["requests"][1]["request_sha256"]}
    case.authority = tmp_path / "new-authority"
    case.authority.mkdir()
    provenance, case.execution = _provenance(case.authority, source=case.config.pdf_path,
        runtime_config=canonical_run_config(case.config), preferences={})
    case.amendment.update(provenance=provenance, execution_identity=case.execution,
        stable_run_identity=stable_acceptance_run_identity(case.identity), case={"case_id": "successor",
        "max_calls": predecessors[root_id]["case_max_calls"] - 1,
        "ceiling_usd": str(Decimal(predecessors[root_id]["case_ceiling_usd"]) - sum(Decimal(r["actual_usd"]) for r in prior.values()))})
    case.amendment["dispatch_limits"]["openai:translation"].update(limits, ceiling_usd="0.5")
    # Bind the ledger identity exactly as the production adapter does, without
    # requiring the enclosing scope/config-manifest hash to refer to itself.
    projection = {k: v for k, v in case.execution.items() if k != "config_manifest_sha256"}
    scope = {"version": SUCCESSOR_SCOPE_VERSION, "campaign_id": case.amendment["campaign_id"],
        "ledger_identity": state["acceptance_campaigns"][case.amendment["campaign_id"]]["identity"],
        "root_case_id": root_id, "root_run_identity": original, "predecessor_cases": predecessors,
        "predecessor_reservations_fingerprint": fingerprint(prior), "successor_case": case.amendment["case"],
        "successor_run_identity": stable_acceptance_run_identity(case.identity), "execution_projection": projection,
        "eligible_pages": [1], "excluded_pages": [2], "consumed_intent_pages": [], "no_contact_dispositions": []}
    entry = write(case.authority / "successor.json", scope)
    manifest_path = Path(provenance["config_manifest"]["path"])
    manifest = json.loads(manifest_path.read_bytes())
    manifest["files"].extend([entry, case.review_entry, *case.evidence_entries])
    provenance["config_manifest"] = write(manifest_path, manifest)
    case.execution["config_manifest_sha256"] = provenance["config_manifest"]["sha256"]
    approval = _approve(case, (1,))
    first = invoke(case, approval, successor_scope_file=entry)
    assert first.completed_pages == 1 and first.error == "acceptance_phase_complete", first.error
    assert len(case.sdk.requests) == 2
    saved = case.ledger.read_bytes()
    again = invoke(case, approval, resume=True, successor_scope_file=entry)
    assert again.error == "acceptance_phase_complete" and len(case.sdk.requests) == 2
    assert case.ledger.read_bytes() == saved
    assert all(json.loads(saved)["reservations"][k] == row for k, row in original_rows.items())
