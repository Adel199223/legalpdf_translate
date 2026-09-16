"""Prepare offline, approve fixed evidence, then run/resume with a fake SDK only."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from legalpdf_translate import workflow as module
from legalpdf_translate.acceptance_budget import stable_acceptance_run_identity
from legalpdf_translate.budget_reservations import atomic_json, fingerprint
from legalpdf_translate.cost_guardrails import PricingSnapshot
from legalpdf_translate.usage_accounting import DispatchAccounting
from legalpdf_translate.workflow import TranslationWorkflow
from tests.test_new_run_preflight import config_for
from tests.test_workflow_dispatch_accounting import FakeSDK, client_for
from tooling.structured_acceptance_preflight import build_acceptance_accounting
from tests.test_acceptance_budget_adapter import _provenance
from legalpdf_translate.acceptance_provenance import canonical_run_config


def test_offline_preparation_then_fixed_approval_handles_generated_run_id(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        pytest.fail("Ambient credentials/settings or automatic provider probe")

    monkeypatch.setattr(module, "load_environment", forbidden)
    monkeypatch.setattr(module, "load_gui_settings", forbidden)
    monkeypatch.setattr(module, "run_translation_auth_test", forbidden)
    monkeypatch.setattr(module, "resolve_openai_key_with_source", forbidden)
    config = config_for(tmp_path)
    sdk = FakeSDK()
    prepared = {}

    request_limits = {"requested_model": "gpt-5.2", "max_input_tokens": 50000,
                      "max_output_tokens": 256, "requested_service_tier": "default",
                      "billing_scope": "fixture-standard", "currency": "USD",
                      "allowed_actual_service_tiers": ["default"],
                      "allowed_base_urls": ["https://api.openai.com/v1"], "route": "responses.create"}

    def capture_before_dispatch(**arguments):
        prepared.update(arguments)
        class CaptureOnly(DispatchAccounting):
            def begin(self, **request):
                prepared["request"] = request
                raise RuntimeError("Offline preparation stops before any SDK dispatch")
        return CaptureOnly(**arguments, dispatch_limits={"openai:translation": request_limits})

    common = dict(client=client_for(sdk), gui_settings={}, environment_loader=lambda: None,
                  ocr_engine_factory=forbidden, translation_protocol="legal_blocks_v2")
    (tmp_path / "preparation-only").mkdir()
    # Preparation owns separate scratch outputs; it must not occupy the eventual
    # output folder. It builds the real bounded request, but stops at begin().
    preparation_result = TranslationWorkflow(**common, accounting_factory=capture_before_dispatch).run(
        replace(config, output_dir=tmp_path / "preparation-only"))
    assert not preparation_result.success
    assert not sdk.requests
    assert prepared["request"]["requested_model"] == "gpt-5.2"

    # Everything below is synthetic test authority, prepared outside the dispatch
    # factory. Production Stage 3 requires the user's separate exact approval.
    historic_rows = {"historic": {"purpose": "translation", "candidate_id": "fixture",
        "reserved_usd": "3", "actual_usd": "2.36852785", "status": "finalized"}}
    ledger_path = tmp_path / "original-fixture-ledger.json"
    ledger = {"schema_version": 1, "benchmark_id": "offline-existing-campaign",
        "manifest_path": "fixture-manifest.json", "manifest_fingerprint": "a" * 64,
        "cap_usd": "10", "created_at": "2026-09-06T00:00:00+00:00",
        "updated_at": "2026-09-06T00:00:00+00:00", "blocked_reason": None,
        "reservations": historic_rows}
    ledger["fingerprint"] = fingerprint(ledger)
    atomic_json(ledger_path, ledger)
    static = {key: value for key, value in ledger.items()
              if key not in {"reservations", "updated_at", "fingerprint", "blocked_reason"}}
    prices = PricingSnapshot.from_mapping({
        "snapshot_id": "workflow-acceptance-fixture", "verified_at": "2026-09-10",
        "source": "offline test rates; not production pricing",
        "models": {"openai:gpt-5.2|default|fixture-standard|USD": {"input_per_1m": 2, "output_per_1m": 8,
            "cached_input_per_1m": 1, "service_tier": "default", "billing_scope": "fixture-standard", "currency": "USD"}},
    })
    provenance, execution_identity = _provenance(tmp_path, source=config.pdf_path,
        runtime_config=canonical_run_config(TranslationWorkflow(**common)._normalize_config(config)), preferences={})
    amendment = {"schema_version": 2, "approval_status": "approved", "prior_amendments": [],
        "prior_reservations_fingerprint": fingerprint({}), "provenance": provenance,
        "ledger": {"benchmark_id": ledger["benchmark_id"], "resolved_path": str(ledger_path.resolve()),
            "manifest_fingerprint": ledger["manifest_fingerprint"], "cap_usd": "10",
            "initial_sha256": hashlib.sha256(ledger_path.read_bytes()).hexdigest(),
            "base_reservations_fingerprint": fingerprint(historic_rows),
            "base_static_fingerprint": fingerprint(static)},
        "campaign_id": "synthetic-workflow-campaign", "campaign_cap_usd": "0.2",
        "case": {"case_id": "synthetic-one-page", "max_calls": 1, "ceiling_usd": "0.2"},
        "stable_run_identity": stable_acceptance_run_identity(prepared["run_identity"]),
        "execution_identity": execution_identity, "pricing_snapshot": prices.metadata(),
        "protocol": "legal_blocks_v2", "approved_at": "2026-09-10T12:00:00+00:00",
        "approved_by": "synthetic-test-only", "approval_reference": "separate-offline-fixture-approval",
        "dispatch_limits": {"openai:translation": {
            **request_limits,
            "limit_id": "synthetic-primary", "requested_model": "gpt-5.2", "required_effort": "high",
            "max_calls": 1, "max_calls_per_page": 1, "max_attempts": 1, "allowed_pages": [1],
            "allowed_request_hashes": [prepared["request"]["request_hash"]],
            "max_input_tokens": 50000, "max_output_tokens": 256, "ceiling_usd": "0.2"}}}
    amendment["fingerprint"] = fingerprint(amendment)
    amendment_path = tmp_path / "approved-fixture-amendment.json"
    atomic_json(amendment_path, amendment)
    approved_sha256 = hashlib.sha256(amendment_path.read_bytes()).hexdigest()
    identities = []

    def fixed_approved_factory(**arguments):
        identities.append(arguments["run_identity"])
        return build_acceptance_accounting(**arguments, ledger_path=ledger_path,
            amendment_path=amendment_path, expected_amendment_sha256=approved_sha256,
            execution_identity=execution_identity, pricing_snapshot=prices)

    workflow = TranslationWorkflow(**common, accounting_factory=fixed_approved_factory)
    result = workflow.run(config)
    assert result.success, result.error
    assert len(sdk.requests) == 1
    assert identities[0]["accounting_id"] != prepared["run_identity"]["accounting_id"]
    assert stable_acceptance_run_identity(identities[0]) == amendment["stable_run_identity"]
    summary = json.loads(result.run_summary_path.read_text(encoding="utf-8"))
    assert summary["dispatch_accounting"]["coverage_status"] == "complete"
    assert summary["dispatch_accounting"]["cost_usd"] == pytest.approx(0.00066)
    settled = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert settled["reservations"]["historic"] == historic_rows["historic"]
    assert len(settled["reservations"]) == 2
    before = ledger_path.read_bytes()
    resumed = TranslationWorkflow(**common, accounting_factory=fixed_approved_factory).run(
        replace(config, resume=True))
    assert resumed.success, resumed.error
    assert len(sdk.requests) == 1
    assert ledger_path.read_bytes() == before
    assert hashlib.sha256(amendment_path.read_bytes()).hexdigest() == approved_sha256
