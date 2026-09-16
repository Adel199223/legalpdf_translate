"""Validate a bounded acceptance successor without resetting prior allowances.

This opt-in scope supplements existing physical approval and ledger enforcement.
It does not mint authority, release a hold, rewrite an intent or infer a lineage
for arbitrary newly named cases. Historical runtime evidence remains a trusted,
cooperative-runtime assertion, not a hostile-process attestation.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import stat

from .acceptance_budget import AcceptanceBudgetError, stable_acceptance_run_identity
from .acceptance_provenance import _verified_file, request_fingerprint as wire_fingerprint
from .budget_reservations import fingerprint, locked, money
from .structured_artifacts import _decode
from .translation_structure import request_fingerprint as page_fingerprint

SUCCESSOR_SCOPE_VERSION = "acceptance_successor_scope_v1"
_SOURCE_KEYS = ("source_sha256", "context_hash", "language", "model", "selection")


def _read(entry, label):
    return _decode(_verified_file(entry, label))


def _require(condition, code):
    if not condition:
        raise AcceptanceBudgetError(code)


def validate_successor_scope(budget, scope_file: dict) -> dict:
    """Check frozen residual bounds and immutable predecessor evidence read-only.

The scope is a member of the approved config manifest. Its execution projection
excludes that enclosing manifest's hash to avoid a circular self-hash; physical
approval binds the completed manifest and full execution identity separately.
Existing reservation checks continue enforcing all caps on every actual call.
"""
    try:
        manifest = _read(budget.amendment["provenance"]["config_manifest"], "config_manifest")
        _require(scope_file in manifest["files"], "successor_scope_not_approved")
        scope = _read(scope_file, "successor_scope")
        _require(set(scope) == {"version", "campaign_id", "ledger_identity", "root_case_id",
            "root_run_identity", "predecessor_cases", "predecessor_reservations_fingerprint",
            "successor_case", "successor_run_identity", "execution_projection", "eligible_pages",
            "excluded_pages", "consumed_intent_pages", "no_contact_dispositions"}, "successor_scope_invalid")
        _require(scope["version"] == SUCCESSOR_SCOPE_VERSION and scope["campaign_id"] == budget.campaign_id,
                 "successor_campaign_changed")
        _require(scope["ledger_identity"] == budget._campaign_binding(), "successor_ledger_changed")
        _require(scope["successor_case"] == budget.case, "successor_case_changed")
        _require(scope["successor_run_identity"] == stable_acceptance_run_identity(budget.run_identity),
                 "successor_run_changed")
        _require(scope["execution_projection"] == {k: v for k, v in budget.execution_identity.items()
            if k != "config_manifest_sha256"}, "successor_execution_changed")
        original = scope["root_run_identity"]
        current = scope["successor_run_identity"]
        _require(all(original[k] == current[k] for k in _SOURCE_KEYS), "successor_source_selection_changed")
        full_pages = list(range(current["selection"][0], current["selection"][1] + 1))
        new_id = budget.case["case_id"]
        predecessors = scope["predecessor_cases"]
        root_id = scope["root_case_id"]
        _require(isinstance(predecessors, dict) and root_id in predecessors and new_id not in predecessors,
                 "successor_predecessors_invalid")
        root = predecessors[root_id]
        _require(root["stable_run_identity_hash"] == fingerprint(original), "successor_root_run_changed")
        with locked(budget.lock_path):
            state = budget._load_ledger_unlocked()
        _require(not state.get("blocked_reason") and all(r["status"] == "finalized"
            for r in state["reservations"].values()), "successor_unresolved_dispatch")
        campaign = state["acceptance_campaigns"][budget.campaign_id]
        registered = {k: v for k, v in campaign["cases"].items() if k != new_id}
        _require(registered == predecessors, "successor_predecessor_binding_changed")
        rows = {k: r for k, r in state["reservations"].items()
            if r.get("execution", {}).get("campaign_id") == budget.campaign_id
            and r["execution"].get("case_id") != new_id}
        _require(all(r["execution"]["case_id"] in predecessors for r in rows.values()),
                 "successor_predecessor_case_missing")
        _require(fingerprint(rows) == scope["predecessor_reservations_fingerprint"],
                 "successor_predecessor_charges_changed")
        original_calls = root["case_max_calls"]
        prior_cost = sum((money(r["actual_usd"]) for r in rows.values()), Decimal(0))
        _require(type(original_calls) is int and budget.case["max_calls"] == original_calls - len(rows),
                 "successor_call_allowance_reset")
        _require(money(budget.case["ceiling_usd"]) == money(root["case_ceiling_usd"]) - prior_cost,
                 "successor_cost_allowance_reset")
        prior_pages = sorted({r["execution"]["page_number"] for r in rows.values()})
        _require(all(type(n) is int and n in full_pages for n in prior_pages), "successor_prior_page_invalid")
        _require(scope["excluded_pages"] == prior_pages, "successor_paid_page_not_excluded")
        _require(scope["eligible_pages"] == [n for n in full_pages if n not in prior_pages],
                 "successor_eligible_pages_changed")
        _require(set(budget.dispatch_limits) == {"openai:translation"}, "successor_primary_only")
        limit = budget.dispatch_limits["openai:translation"]
        _require(set(limit["allowed_pages"]).issubset(scope["eligible_pages"])
            and limit["max_calls_per_page"] == 1 and limit["max_attempts"] == 1,
            "successor_dispatch_scope_changed")
        consumed = scope["consumed_intent_pages"]
        _require(isinstance(consumed, list) and consumed == sorted(set(consumed))
            and all(type(n) is int and n in scope["eligible_pages"] for n in consumed),
            "successor_consumed_intents_invalid")
        dispositions = scope["no_contact_dispositions"]
        _require(isinstance(dispositions, list) and [d["page_number"] for d in dispositions] == consumed,
                 "successor_no_contact_disposition_missing")
        for disposition in dispositions:
            _verify_no_contact(disposition, manifest["files"], state, budget.campaign_id, new_id, original, root_id)
        return deepcopy(scope)
    except AcceptanceBudgetError:
        raise
    except (KeyError, TypeError, ValueError, OSError, AttributeError):
        raise AcceptanceBudgetError("successor_scope_invalid") from None


def _verify_no_contact(disposition, approved_files, state, campaign_id, new_id, original, root_id):
    _require(set(disposition) == {"page_number", "operation_sha256", "request_sha256", "result_file",
        "operation_file", "operation_intent_file", "page_intent_file", "prepared_requests_file",
        "provider_intent_path", "assurance"},
        "successor_no_contact_disposition_invalid")
    _require(disposition["assurance"] == "trusted_runtime_no_contact_observed",
             "successor_no_contact_assurance_invalid")
    for name in ("operation_file", "result_file", "operation_intent_file", "page_intent_file", "prepared_requests_file"):
        _require(disposition[name] in approved_files, "successor_disposition_file_not_approved")
    result = _read(disposition["result_file"], "prior_operation_result")
    prior_operation = _read(disposition["operation_file"], "prior_operation")
    operation = _read(disposition["operation_intent_file"], "prior_operation_intent")
    page_intent = _read(disposition["page_intent_file"], "prior_page_intent")
    _require(disposition["operation_file"]["sha256"] == disposition["operation_sha256"]
        and prior_operation.get("request_sha256") == disposition["request_sha256"]
        and prior_operation.get("pages") == [disposition["page_number"]]
        and stable_acceptance_run_identity(prior_operation["run_identity"]) == original
        and result.get("operation_sha256") == disposition["operation_sha256"]
        and operation.get("operation_sha256") == disposition["operation_sha256"]
        and operation.get("consumed") is True and operation.get("no_automatic_replay") is True,
        "successor_prior_operation_changed")
    _require(type(result.get("sdk_calls_entered")) is int and result["sdk_calls_entered"] == 0
        and type(result.get("exit_code")) is int and result["exit_code"] != 0
        and result.get("phase") == "workflow", "successor_prior_contact_uncertain")
    identity = page_intent["identity"]
    full_pages = list(range(original["selection"][0], original["selection"][1] + 1))
    expected_campaign = fingerprint({"campaign_id": campaign_id, "case_id": root_id,
        "source_sha256": original["source_sha256"], "full_case_pages": full_pages})
    _require(identity["page_number"] == disposition["page_number"]
        and identity["full_case_pages"] == full_pages and identity["campaign"] == expected_campaign
        and identity["protocol"] == original["protocol_identity"]
        and type(page_intent.get("version")) is int and page_intent["version"] == 1
        and page_intent["sha256"] == fingerprint({k: v for k, v in page_intent.items() if k != "sha256"}),
        "successor_prior_intent_changed")
    prepared_entry = disposition["prepared_requests_file"]
    _require(prepared_entry in prior_operation["read_files"], "successor_prior_request_file_changed")
    prepared = _read(prepared_entry, "prior_prepared_requests")
    selected = [p for p in prepared["pages"] if p["page_number"] == disposition["page_number"]]
    _require(len(selected) == 1, "successor_prior_request_missing")
    selected = selected[0]
    descriptor = selected["logical_descriptor"]
    request = descriptor["request"]
    _require(descriptor["page_number"] == disposition["page_number"]
        and descriptor["purpose"] == "translation" and descriptor["attempt"] == 1
        and descriptor["model"] == original["model"]
        and page_intent["payload"]["request"] == request
        and selected["final_request_sha256"] == disposition["request_sha256"]
        and wire_fingerprint(selected["final_request"]) == disposition["request_sha256"],
        "successor_prior_request_changed")
    prompt, end = json.JSONDecoder().raw_decode(request["prompt_text"])
    prompt = _decode(request["prompt_text"][:end].encode("utf-8"))
    _require(prompt["page"] == disposition["page_number"]
        and identity["page_fingerprint"] == page_fingerprint(source_blocks=prompt["blocks"],
            prompt_text=request["prompt_text"], translation_identity=fingerprint({
                "run": identity["protocol"], "model": original["model"], "effort": request["effort"]})),
        "successor_prior_page_fingerprint_changed")
    # Paths here attribute evidence to one operation. Reject lexical traversal
    # and any reparse ancestor, not just an eventual file's digest mismatch.
    def owned_path(raw):
        path = Path(raw)
        _require(path.is_absolute() and ".." not in path.parts, "successor_prior_intent_path_changed")
        for part in (path, *path.parents):
            if part.exists() or part.is_symlink():
                info = part.lstat()
                _require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                         "successor_prior_intent_path_changed")
        return path.resolve()
    provider_path = owned_path(disposition["provider_intent_path"])
    operation_path = owned_path(disposition["operation_intent_file"]["path"])
    _require(provider_path == operation_path.parent / "provider.intent.json"
        and not provider_path.exists() and not provider_path.is_symlink(), "successor_provider_intent_exists")
    page_path = owned_path(disposition["page_intent_file"]["path"])
    _require(page_path.name == f"page_{disposition['page_number']:04d}.primary.intent.json"
        and page_path.parent.name == "acceptance_private"
        and page_path.parent.parent.parent == operation_path.parent / "outputs",
        "successor_prior_intent_path_changed")
    response_path = page_path.with_name(page_path.name.replace(".intent.json", ".response.json"))
    _require(not response_path.exists() and not response_path.is_symlink(), "successor_prior_response_exists")
    _require(not any(not (r.get("execution", {}).get("campaign_id") == campaign_id
        and r["execution"].get("case_id") == new_id)
        and (r.get("execution", {}).get("request_hash") == disposition["request_sha256"]
        or r.get("execution", {}).get("campaign_id") == campaign_id
        and r["execution"].get("page_number") == disposition["page_number"])
        for r in state["reservations"].values()), "successor_prior_reservation_exists")
