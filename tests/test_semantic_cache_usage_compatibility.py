"""Documented TTL dimensions; exact historical policy and fictional native replay."""
from copy import deepcopy
from decimal import Decimal
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate.accounting_policy import ordinary_accounting_policy, with_semantic_review_policy
from legalpdf_translate.openai_client import ApiCallError
from legalpdf_translate.semantic_review_billing import (
    POLICY, FRESH_POLICY, strict_limits, usage_evidence, validate_retained_responses,
)
from legalpdf_translate.usage_accounting import DispatchAccounting, DispatchAccountingError, _state_fingerprint
from tests.test_semantic_review_native_billing import native, call, IDENTITY, ROLE

FIXTURE = json.loads((Path(__file__).parent / "fixtures/semantic_billing_prechange_v1.json").read_bytes())


def test_genuine_prechange_evidence_and_catalog_only_change_fresh_marker():
    for shape in ("legacy", "new"):
        assert usage_evidence(FIXTURE[f"{shape}_usage"], max_output_tokens=32000) == FIXTURE[f"{shape}_evidence"]
        assert usage_evidence(FIXTURE[f"{shape}_usage"], max_output_tokens=32000, policy=POLICY) == FIXTURE[f"{shape}_evidence"]
    old = deepcopy(FIXTURE["accounting_arguments"])
    fresh = with_semantic_review_policy(ordinary_accounting_policy(), ROLE).accounting_arguments()
    old["dispatch_limits"]["openai:semantic_audit:gpt-6-astra"]["semantic_review_billing_policy"] = FRESH_POLICY
    assert fresh == old  # No price, model, capacity, source or primary policy change.
    assert not strict_limits({}) and not strict_limits({"semantic_review_billing_policy": "unknown"})


@pytest.mark.parametrize("shape", ["legacy", "new"])
def test_fresh_admits_legacy_and_documented_default_with_exact_raw_hash(shape):
    result = usage_evidence(FIXTURE[f"{shape}_usage"], max_output_tokens=32000, policy=FRESH_POLICY)
    assert result["status"] == "available" and result["policy"] == FRESH_POLICY
    assert result["raw_usage"] == FIXTURE[f"{shape}_usage"]
    assert result["raw_usage_sha256"] == FIXTURE[f"{shape}_evidence"]["raw_usage_sha256"]


def malformed_usage(defect):
    usage = deepcopy(FIXTURE["new_usage"])
    details = usage["input_tokens_details"]
    ttl = details["cache_write_tokens_details"]
    if defect == "partial_30m": ttl.pop("ttl_30m_tokens")
    elif defect == "partial_12h": ttl.pop("ttl_12h_tokens")
    elif defect == "extra": ttl["ttl_future_tokens"] = 0
    elif defect == "null": details["cache_write_tokens_details"] = None
    elif defect == "scalar": details["cache_write_tokens_details"] = 30
    elif defect == "bool_30m": ttl["ttl_30m_tokens"] = True
    elif defect == "bool_12h": ttl["ttl_12h_tokens"] = False
    elif defect == "float": ttl["ttl_30m_tokens"] = 30.0
    elif defect == "negative": ttl["ttl_12h_tokens"] = -1
    elif defect == "string": ttl["ttl_30m_tokens"] = "30"
    elif defect == "sum": ttl["ttl_30m_tokens"] = 29
    elif defect == "12h": ttl.update(ttl_30m_tokens=20, ttl_12h_tokens=10)
    elif defect == "flat_conflict": usage["cache_write_tokens"] = 29
    elif defect == "missing_aggregate": details.pop("cache_write_tokens")
    elif defect == "aggregate_null": details["cache_write_tokens"] = None
    elif defect == "outer_extra": details["unknown_tokens"] = 0
    else: raise AssertionError(defect)
    return usage


DEFECTS = ["partial_30m", "partial_12h", "extra", "null", "scalar", "bool_30m", "bool_12h", "float",
           "negative", "string", "sum", "12h", "flat_conflict", "missing_aggregate", "aggregate_null", "outer_extra"]


@pytest.mark.parametrize("defect", DEFECTS)
def test_fresh_malformed_ttl_stays_unknown(defect):
    assert usage_evidence(malformed_usage(defect), max_output_tokens=32000, policy=FRESH_POLICY)["status"] != "available"


@pytest.mark.parametrize("flat_only", [False, True])
def test_zero_ttl_and_flat_aggregate_are_explicitly_valid(flat_only):
    usage = deepcopy(FIXTURE["new_usage"])
    details = usage["input_tokens_details"]
    details.update(cache_write_tokens=0, cache_write_tokens_details={"ttl_30m_tokens": 0, "ttl_12h_tokens": 0})
    if flat_only: usage["cache_write_tokens"] = details.pop("cache_write_tokens")
    assert usage_evidence(usage, max_output_tokens=32000, policy=FRESH_POLICY)["status"] == "available"


@pytest.mark.parametrize("version", [POLICY, FRESH_POLICY])
@pytest.mark.parametrize("shape", ["legacy", "new"])
def test_native_frozen_policy_controls_raw_bill_and_read_only_process_restore(tmp_path, version, shape):
    settings = deepcopy(FIXTURE["accounting_arguments"])
    settings["dispatch_limits"]["openai:semantic_audit:gpt-6-astra"]["semantic_review_billing_policy"] = version
    def mutate(data):
        data["usage"] = deepcopy(FIXTURE[f"{shape}_usage"])
        return data
    client, accountant, requests, bodies = native(tmp_path, mutate, settings=settings)
    rejected = version == POLICY and shape == "new"
    if rejected:
        with pytest.raises(ApiCallError): call(client, accountant)
    else:
        call(client, accountant)
    state = json.loads(accountant.journal_path.read_bytes())
    finish = state["events"][-1]
    evidence = finish["semantic_review_billing_evidence"]
    assert evidence["policy"] == version
    assert (accountant.run_dir / evidence["response"]["path"]).read_bytes() == bodies[0]
    if rejected:
        assert evidence == {**FIXTURE["new_evidence"], "response": evidence["response"]}
        assert finish["cost_usd"] is None and finish["cost_status"] == "unsupported_usage_dimensions"
    else:
        assert Decimal(finish["cost_usd"]) == Decimal("0.001395")
    validate_retained_responses(accountant.run_dir, state["events"])
    before = accountant.journal_path.read_bytes()
    fresh = with_semantic_review_policy(ordinary_accounting_policy(), ROLE).accounting_arguments()
    restored = DispatchAccounting(accountant.run_dir, run_identity=IDENTITY, **fresh)
    assert restored.request_limits("openai", "semantic_audit", "gpt-6-astra")["semantic_review_billing_policy"] == version
    assert accountant.journal_path.read_bytes() == before
    if rejected:
        assert not restored.can_retry
        with pytest.raises(ApiCallError): call(client, restored)
    assert len(requests) == 1 and accountant.journal_path.read_bytes() == before


@pytest.mark.parametrize("defect", DEFECTS + ["duplicate_ttl", "duplicate_details"])
def test_native_unknown_ttl_retains_wire_and_durable_hold(tmp_path, defect):
    def mutate(data):
        data["usage"] = deepcopy(FIXTURE["new_usage"]) if defect.startswith("duplicate") else malformed_usage(defect)
        if defect == "duplicate_ttl":
            return json.dumps(data).replace('"ttl_12h_tokens": 0', '"ttl_12h_tokens": 1, "ttl_12h_tokens": 0').encode()
        if defect == "duplicate_details":
            return json.dumps(data).replace('"cache_write_tokens_details": {', '"cache_write_tokens_details": {}, "cache_write_tokens_details": {').encode()
        return data
    client, accountant, requests, bodies = native(tmp_path, mutate)
    with pytest.raises(ApiCallError): call(client, accountant)
    state = json.loads(accountant.journal_path.read_bytes())
    finish = state["events"][-1]
    assert finish["cost_usd"] is None and accountant.summary()["unknown_cost_count"] == 1
    if defect.startswith("duplicate"): assert finish["cost_status"] == "duplicate_json_keys"
    if defect == "12h": assert finish["cost_status"] == "unsupported_cache_write_ttl"
    proof = finish["semantic_review_billing_evidence"]["response"]
    assert (accountant.run_dir / proof["path"]).read_bytes() == bodies[0]
    before = accountant.journal_path.read_bytes()
    restored = DispatchAccounting(accountant.run_dir, run_identity=IDENTITY, **ordinary_accounting_policy().accounting_arguments())
    assert not restored.can_retry
    with pytest.raises(ApiCallError): call(client, restored)
    assert len(requests) == 1 and accountant.journal_path.read_bytes() == before


def test_journal_evidence_cannot_change_saved_policy(tmp_path):
    client, accountant, _, _ = native(tmp_path)
    call(client, accountant)
    state = json.loads(accountant.journal_path.read_bytes())
    state["events"][-1]["semantic_review_billing_evidence"]["policy"] = POLICY
    state["fingerprint"] = _state_fingerprint(state)
    accountant.journal_path.write_text(json.dumps(state), encoding="utf-8")
    before = accountant.journal_path.read_bytes()
    with pytest.raises(DispatchAccountingError):
        DispatchAccounting(accountant.run_dir, run_identity=IDENTITY, **ordinary_accounting_policy().accounting_arguments())
    assert accountant.journal_path.read_bytes() == before


def test_billing_version_does_not_change_provider_request(tmp_path):
    requests = []
    for version in (POLICY, FRESH_POLICY):
        settings = deepcopy(FIXTURE["accounting_arguments"])
        settings["dispatch_limits"]["openai:semantic_audit:gpt-6-astra"]["semantic_review_billing_policy"] = version
        client, accountant, sent, _ = native(tmp_path / version, settings=settings)
        call(client, accountant)
        requests.append(sent)
    assert requests[0] == requests[1]


@pytest.mark.parametrize("extended_ttl", [False, True])
def test_documented_wire_shape_workflow_resume_and_rebuild(tmp_path, extended_ttl):
    from tests.test_semantic_review_model_integration import setup, immutable
    from legalpdf_translate.workflow import TranslationWorkflow
    def mutate(body, data):
        if body["model"] == "gpt-6-astra":
            details = data["usage"]["input_tokens_details"]
            details["cache_write_tokens_details"] = {
                "ttl_30m_tokens": 0 if extended_ttl else 20,
                "ttl_12h_tokens": 20 if extended_ttl else 0,
            }
        return data
    config, http, flow = setup(tmp_path, mutate=mutate)
    result = flow.run(config)
    assert result.success is not extended_ttl, result.error
    expected_calls = 2 if extended_ttl else 4
    assert len(http.requests) == expected_calls
    journal = json.loads(flow._dispatch_accounting.journal_path.read_bytes())
    strict_finishes = [e for e in journal["events"] if e.get("semantic_review_billing_evidence")]
    for finish in strict_finishes:
        assert finish["semantic_review_billing_evidence"]["policy"] == FRESH_POLICY
        proof = finish["semantic_review_billing_evidence"]["response"]
        assert (flow._dispatch_accounting.run_dir / proof["path"]).read_bytes() in http.bodies
    before = immutable(result.run_dir)
    resumed = flow.run(replace(config, resume=True))
    assert resumed.success is not extended_ttl, resumed.error
    if not extended_ttl:
        assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    else:
        assert not (result.run_dir / "semantic_audit/attempt_00/correction").exists()
        assert not (result.run_dir / "semantic_audit/manifest.json").exists()
        assert strict_finishes[-1]["cost_status"] == "unsupported_cache_write_ttl"
    assert len(http.requests) == expected_calls and immutable(result.run_dir) == before
