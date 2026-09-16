"""Actual prepared request, workflow identity and fake-SDK model/effort parity."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from legalpdf_translate.acceptance_budget import stable_acceptance_run_identity
from legalpdf_translate.acceptance_provenance import canonical_run_config, request_fingerprint
from legalpdf_translate.cost_guardrails import PricingSnapshot
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.types import ReasoningEffort, EffortPolicy
from tests.test_acceptance_budget_adapter import _provenance
from tests.test_acceptance_campaign_integration import _approve
from tests.test_acceptance_continuation import offline
from tests.test_structured_acceptance_prepare import arguments, LIMITS
from tests.test_structured_acceptance_run import invoke
from tooling.structured_acceptance_prepare import prepare_reviewed_requests, PreparationOnly


def selected_case(tmp_path, monkeypatch, model, effort):
    case, args = arguments(tmp_path, monkeypatch, pages=1)
    old_identity = deepcopy(case.identity)
    if effort == "xhigh":
        case.config = replace(case.config, effort=ReasoningEffort.XHIGH, effort_policy=EffortPolicy.FIXED_XHIGH)
    args.update(config=case.config, model=model, required_effort=effort,
        case_id=f"new-{model}-{effort}", dispatch_limits={**LIMITS, "requested_model": model, "required_effort": effort})
    prepared = prepare_reviewed_requests(**args)
    case.identity = prepared["run_identity"]
    case.hashes = {1: prepared["requests"][1]["request_sha256"]}
    case.client = OpenAIResponsesClient(sdk_client=case.sdk, model=model,
        max_transport_retries=0, pre_call_jitter_seconds=0)
    case.sdk.max_retries = 0
    create = case.sdk.responses.create
    def selected_response(**request):
        response = create(**request)
        response.model = model
        return response
    case.sdk.responses.create = selected_response
    rates = next(iter(case.prices.models.values()))
    case.prices = PricingSnapshot(snapshot_id="selected-model-synthetic", verified_at="2026-09-10",
        source="Synthetic rates only, not current API pricing", models={
            f"openai:{model}|default|fixture-standard|USD": replace(rates,
                pricing_model=model, pricing_version="selected-model-synthetic")})
    provenance, case.execution = _provenance(case.authority, source=case.config.pdf_path,
        runtime_config=canonical_run_config(case.config), preferences={})
    path = Path(provenance["config_manifest"]["path"])
    manifest = json.loads(path.read_bytes())
    manifest["files"].extend([case.review_entry, *case.evidence_entries])
    path.write_text(json.dumps(manifest), encoding="utf-8")
    provenance["config_manifest"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    case.execution["config_manifest_sha256"] = provenance["config_manifest"]["sha256"]
    case.amendment.update(provenance=provenance, execution_identity=case.execution,
        stable_run_identity=stable_acceptance_run_identity(case.identity), pricing_snapshot=case.prices.metadata())
    case.amendment["case"]["case_id"] = args["case_id"]
    case.amendment["dispatch_limits"]["openai:translation"].update(args["dispatch_limits"], ceiling_usd="1.5")
    return case, prepared, old_identity


@pytest.mark.parametrize("model", ["gpt-5.2", "gpt-5.6-terra", "gpt-5.6-sol"])
@pytest.mark.parametrize("effort", ["high", "xhigh"])
def test_explicit_model_effort_preparation_dispatch_identity_and_resume(tmp_path, monkeypatch, model, effort):
    case, prepared, old_identity = selected_case(tmp_path, monkeypatch, model, effort)
    expected = prepared["requests"][1]["request"]
    assert expected["model"] == case.identity["model"] == model
    assert expected["reasoning"]["effort"] == effort
    assert prepared["requests"][1]["descriptor"]["model"] == model
    approval = _approve(case, (1,))
    result = invoke(case, approval)
    assert result.success, result.error
    assert len(case.sdk.requests) == 1
    sent = {k: v for k, v in case.sdk.requests[0].items() if k != "timeout"}
    assert sent == expected and request_fingerprint(sent) == prepared["requests"][1]["request_sha256"]
    state = json.loads((result.run_dir / "run_state.json").read_bytes())
    assert state["protocol_identity"] == prepared["run_identity"]["protocol_identity"]
    accounting = json.loads((result.run_dir / "accounting" / state["dispatch_accounting"]["id"] / "dispatch_accounting.json").read_bytes())
    assert accounting["run_identity"]["model"] == model
    ledger = case.ledger.read_bytes()
    assert invoke(case, approval, resume=True).success
    assert len(case.sdk.requests) == 1 and case.ledger.read_bytes() == ledger


@pytest.mark.parametrize("initial_model, changed_model, changed_effort", [
    ("gpt-5.2", "gpt-5.6-terra", "high"),
    ("gpt-5.6-terra", "gpt-5.6-sol", "high"),
    ("gpt-5.6-terra", "gpt-5.6-terra", "xhigh"),
    ("gpt-5.6-sol", "gpt-5.6-sol", "xhigh"),
])
def test_protocol_identity_changes_for_only_model_or_effort(tmp_path, monkeypatch,
        initial_model, changed_model, changed_effort):
    case, args = arguments(tmp_path, monkeypatch, pages=1)
    args.update(model=initial_model, required_effort="high")
    initial = prepare_reviewed_requests(**args)
    # Only the disposable preparation directory changes, never the RunConfig
    # output path, campaign/case, source, preferences, or selected page set.
    changed_args = {**args, "directory": tmp_path / "changed-prepare",
        "model": changed_model, "required_effort": changed_effort}
    if changed_effort == "xhigh":
        changed_args["config"] = replace(case.config, effort=ReasoningEffort.XHIGH,
            effort_policy=EffortPolicy.FIXED_XHIGH)
    changed = prepare_reviewed_requests(**changed_args)
    assert initial["campaign_identity"] == changed["campaign_identity"]
    assert initial["preferences_sha256"] == changed["preferences_sha256"]
    for key in ("source_sha256", "context_hash", "language", "protocol", "selection"):
        assert initial["run_identity"][key] == changed["run_identity"][key]
    assert initial["run_identity"]["protocol_identity"] != changed["run_identity"]["protocol_identity"]
    before = deepcopy(initial["requests"][1]["request"])
    before["model"] = changed_model
    before["reasoning"]["effort"] = changed_effort
    assert before == changed["requests"][1]["request"]
    assert initial["requests"][1]["request_sha256"] != changed["requests"][1]["request_sha256"]
    assert not case.sdk.requests


@pytest.mark.parametrize("drift", ["client_model", "identity_model", "config_effort"])
def test_model_or_effort_drift_rejected_before_sdk_entry(tmp_path, monkeypatch, drift):
    case, prepared, _ = selected_case(tmp_path, monkeypatch, "gpt-5.6-terra", "high")
    approval = _approve(case, (1,))
    before = case.ledger.read_bytes()
    if drift == "client_model":
        case.client = OpenAIResponsesClient(sdk_client=case.sdk, model="gpt-5.6-sol", max_transport_retries=0)
    elif drift == "identity_model":
        case.identity["model"] = "gpt-5.2"
    else:
        case.config = replace(case.config, effort=ReasoningEffort.XHIGH, effort_policy=EffortPolicy.FIXED_XHIGH)
    with pytest.raises(ValueError):
        invoke(case, approval)
    assert not case.sdk.requests and case.ledger.read_bytes() == before


def test_preparation_limits_cannot_silently_change_selected_model_or_effort(tmp_path, monkeypatch):
    case, args = arguments(tmp_path, monkeypatch)
    args.update(model="gpt-5.6-terra", dispatch_limits={**LIMITS, "requested_model": "gpt-5.2"})
    with pytest.raises(ValueError, match="model_or_effort"):
        prepare_reviewed_requests(**args)
    assert not case.sdk.requests and not args["directory"].exists()
    args.update(dispatch_limits={**LIMITS, "required_effort": "xhigh"})
    with pytest.raises(ValueError, match="model_or_effort"):
        prepare_reviewed_requests(**args)
    assert not case.sdk.requests and not args["directory"].exists()


def test_preparation_accountant_is_model_specific_and_default_stays_legacy():
    assert PreparationOnly(LIMITS).request_limits("openai", "translation", "gpt-5.2") == LIMITS
    terra = PreparationOnly(LIMITS, model="gpt-5.6-terra")
    assert terra.request_limits("openai", "translation", "gpt-5.6-terra") == LIMITS
    with pytest.raises(ValueError, match="route_changed"):
        terra.request_limits("openai", "translation", "gpt-5.2")
