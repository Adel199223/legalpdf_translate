from __future__ import annotations

import hashlib
import json
from pathlib import Path
from decimal import Decimal
import shutil

import pytest

from legalpdf_translate.acceptance_budget import (
    AcceptanceBudgetError,
    LegacyAcceptanceBudget,
    stable_acceptance_run_identity,
)
from legalpdf_translate.budget_reservations import atomic_json, fingerprint
from legalpdf_translate.cost_guardrails import CostRates, PricingSnapshot
from legalpdf_translate.usage_accounting import DispatchAccounting
from legalpdf_translate.acceptance_provenance import request_fingerprint
import legalpdf_translate.acceptance_provenance as provenance_module


def _request(page: int = 1) -> dict:
    return {"model": "model-a", "input": f"synthetic page {page}", "reasoning": {"effort": "high"},
        "max_output_tokens": 1000, "store": False, "service_tier": "default"}


REQUEST_HASH = request_fingerprint(_request())
DISPATCH_SCOPE = {"route": "responses.create", "requested_service_tier": "default",
    "billing_scope": "fixture-standard", "currency": "USD", "base_url": "https://api.openai.com/v1"}


def _proof(budget, page: int = 1, *, purpose: str = "translation") -> None:
    if not budget.runtime_context_bound:
        budget.bind_runtime_context(config={"synthetic": True}, preferences={"unchanged": True})
    budget.verify_dispatch(request=_request(page), provider="openai", purpose=purpose,
        page_number=page, attempt=1, **DISPATCH_SCOPE)


def _provenance(tmp_path: Path, *, source: Path | None = None,
                runtime_config: dict | None = None, preferences: dict | None = None) -> tuple[dict, dict]:
    def artifact(path, value):
        path.write_bytes(value)
        return {"path": str(path.resolve()), "sha256": hashlib.sha256(value).hexdigest()}
    source_entry = artifact(tmp_path / "synthetic-source.bin", b"synthetic source") if source is None else {
        "path": str(source.resolve()), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}
    package_root = Path(provenance_module.__file__).resolve().parent
    synthetic_code = artifact(tmp_path / "synthetic-code.py", b"SYNTHETIC = True\n")
    code_files = [synthetic_code, *[{"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for path in sorted(package_root.rglob("*.py"))]]
    config = artifact(tmp_path / "synthetic-config.json", b'{"offline": true}')
    provenance = {"source": source_entry,
        "code_manifest": artifact(tmp_path / "code-manifest.json", json.dumps({"files": code_files}).encode()),
        "config_manifest": artifact(tmp_path / "config-manifest.json", json.dumps({"files": [config],
            "runtime_config_sha256": fingerprint(runtime_config if runtime_config is not None else {"synthetic": True})}).encode()),
        "preferences": artifact(tmp_path / "synthetic-preferences.json", json.dumps(
            preferences if preferences is not None else {"unchanged": True}).encode())}
    identity = {f"{key}_sha256": provenance[key]["sha256"] for key in ("code_manifest", "config_manifest", "preferences")}
    return provenance, identity


def _snapshot() -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_id="acceptance-fixture-v1",
        verified_at="2026-09-10",
        source="offline test fixture",
        models={
            "openai:model-a|default|fixture-standard|USD": CostRates(
                2,
                8,
                8,
                "fixture",
                "fixture",
                cached_input_per_1m=1,
                cache_write_per_1m=3,
                verified_at="2026-09-10",
                pricing_version="acceptance-fixture-v1",
                pricing_model="model-a",
                provider="openai",
                service_tier="default", billing_scope="fixture-standard", currency="USD",
            )
        },
    )


def _write_fixture(tmp_path: Path):
    ledger_path = tmp_path / "budget-ledger.json"
    reservations = {
        "historical-1": {
            "purpose": "translation",
            "candidate_id": "baseline",
            "reserved_usd": "3",
            "actual_usd": "2.36852785",
            "status": "finalized",
            "created_at": "2026-09-06T00:00:00+00:00",
            "finalized_at": "2026-09-06T00:01:00+00:00",
        }
    }
    state = {
        "schema_version": 1,
        "benchmark_id": "translation_quality_2026_09_06",
        "manifest_path": "private-manifest.json",
        "manifest_fingerprint": "a" * 64,
        "cap_usd": "10",
        "created_at": "2026-09-06T00:00:00+00:00",
        "reservations": reservations,
        "blocked_reason": None,
        "updated_at": "2026-09-06T00:01:00+00:00",
    }
    state["fingerprint"] = fingerprint(state)
    atomic_json(ledger_path, state)
    initial_bytes = ledger_path.read_bytes()
    static = {
        key: value
        for key, value in state.items()
        if key not in {"reservations", "updated_at", "fingerprint", "blocked_reason"}
    }
    provenance, execution_identity = _provenance(tmp_path)
    run_identity = {
        "accounting_id": "generated-one",
        "run_started_at": "generated-time",
        "source_sha256": provenance["source"]["sha256"],
        "context_hash": "NO_CONTEXT",
        "language": "AR",
        "protocol": "legal_blocks_v2",
        "model": "model-a",
        "protocol_identity": {"protocol": "legal_blocks_v2", "fingerprint": "d" * 64},
        "selection": [1, 1],
    }
    snapshot = _snapshot()
    amendment = {
        "schema_version": 2,
        "approval_status": "approved", "prior_amendments": [],
        "prior_reservations_fingerprint": fingerprint({}), "provenance": provenance,
        "ledger": {
            "benchmark_id": state["benchmark_id"],
            "manifest_fingerprint": state["manifest_fingerprint"],
            "cap_usd": "10",
            "resolved_path": str(ledger_path.resolve()),
            "initial_sha256": hashlib.sha256(initial_bytes).hexdigest(),
            "base_reservations_fingerprint": fingerprint(reservations),
            "base_static_fingerprint": fingerprint(static),
        },
        "campaign_cap_usd": "0.10",
        "campaign_id": "structured-activation-test",
        "case": {"case_id": "ar-case", "max_calls": 1, "ceiling_usd": "0.10"},
        "stable_run_identity": stable_acceptance_run_identity(run_identity),
        "execution_identity": execution_identity,
        "pricing_snapshot": snapshot.metadata(),
        "protocol": "legal_blocks_v2",
        "approved_at": "2026-09-10T12:00:00+00:00",
        "approved_by": "offline-test",
        "approval_reference": "NEXT_STAGE_3-test-only",
        "dispatch_limits": {
            "openai:translation": {
                "limit_id": "pilot-page-1",
                "requested_model": "model-a",
                "max_input_tokens": 1000,
                "max_output_tokens": 1000,
                "ceiling_usd": "0.02",
                "allowed_pages": [1],
                "allowed_request_hashes": [REQUEST_HASH],
                **{key: value for key, value in DISPATCH_SCOPE.items() if key != "base_url"},
                "allowed_actual_service_tiers": ["default"],
                "allowed_base_urls": [DISPATCH_SCOPE["base_url"]],
                "required_effort": "high",
                "max_calls": 1,
                "max_calls_per_page": 1,
                "max_attempts": 1,
            }
        },
    }
    amendment["fingerprint"] = fingerprint(amendment)
    amendment_path = tmp_path / "acceptance-amendment.json"
    atomic_json(amendment_path, amendment)
    amendment_sha256 = hashlib.sha256(amendment_path.read_bytes()).hexdigest()
    return (
        ledger_path,
        amendment_path,
        amendment_sha256,
        run_identity,
        execution_identity,
        snapshot,
        reservations,
    )


def test_adapter_never_initializes_a_missing_acceptance_ledger(tmp_path: Path) -> None:
    _, amendment_path, amendment_sha, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    missing = tmp_path / "missing-ledger.json"
    with pytest.raises(AcceptanceBudgetError, match="no allowance was created"):
        LegacyAcceptanceBudget(
            missing,
            amendment_path=amendment_path,
            expected_amendment_sha256=amendment_sha,
            run_identity=identity,
            execution_identity=execution,
            pricing_snapshot=snapshot,
        )
    assert not missing.exists()


def test_adapter_appends_to_same_ledger_and_preserves_historical_rows(tmp_path: Path) -> None:
    ledger_path, amendment_path, amendment_sha, identity, execution, snapshot, historical = _write_fixture(tmp_path)
    budget = LegacyAcceptanceBudget(
        ledger_path,
        amendment_path=amendment_path,
        expected_amendment_sha256=amendment_sha,
        run_identity=identity,
        execution_identity=execution,
        pricing_snapshot=snapshot,
    )
    accountant = DispatchAccounting(
        tmp_path / "accounting",
        run_identity=identity,
        pricing_snapshot=snapshot,
        budget_context=budget,
        dispatch_limits=budget.dispatch_limits,
    )
    limits = accountant.request_limits("openai", "translation", "model-a")
    _proof(budget)
    ticket = accountant.begin(
        provider="openai",
        requested_model="model-a",
        effort="high",
        purpose="translation",
        page_number=1,
        request_hash=REQUEST_HASH,
        **DISPATCH_SCOPE,
        bounds={**dict(limits), "input_bytes": 100, "image_count": 0},
    )
    held = budget.status()
    assert Decimal(held["held_usd"]) == Decimal("0.02")
    accountant.finish(
        ticket,
        outcome="succeeded",
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        response_id="acceptance-response-1",
        actual_model="model-a",
        actual_service_tier="default",
    )
    state = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert state["cap_usd"] == "10"
    assert state["reservations"]["historical-1"] == historical["historical-1"]
    assert len(state["reservations"]) == 2
    assert accountant.summary()["coverage_status"] == "complete"
    reopened = LegacyAcceptanceBudget(
        ledger_path,
        amendment_path=amendment_path,
        expected_amendment_sha256=amendment_sha,
        run_identity=identity,
        execution_identity=execution,
        pricing_snapshot=snapshot,
    )
    assert reopened.status()["known_spend_usd"] == "2.369127850000"


def test_unknown_usage_keeps_full_hold_and_blocks_future_dispatch(tmp_path: Path) -> None:
    ledger_path, amendment_path, amendment_sha, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    budget = LegacyAcceptanceBudget(
        ledger_path,
        amendment_path=amendment_path,
        expected_amendment_sha256=amendment_sha,
        run_identity=identity,
        execution_identity=execution,
        pricing_snapshot=snapshot,
    )
    accountant = DispatchAccounting(
        tmp_path / "accounting",
        run_identity=identity,
        pricing_snapshot=snapshot,
        budget_context=budget,
        dispatch_limits=budget.dispatch_limits,
    )
    limits = accountant.request_limits("openai", "translation", "model-a")
    _proof(budget)
    ticket = accountant.begin(
        provider="openai",
        requested_model="model-a",
        effort="high",
        purpose="translation",
        page_number=1,
        request_hash=REQUEST_HASH,
        **DISPATCH_SCOPE,
        bounds={**dict(limits), "input_bytes": 100, "image_count": 0},
    )
    accountant.finish(ticket, outcome="timeout", error_code="TimeoutError")
    status = budget.status()
    assert Decimal(status["held_usd"]) == Decimal("0.02")
    assert status["remaining_usd"] == "0"
    assert status["blocked_reason"] == "missing_usage"
    assert accountant.can_retry is False
    with pytest.raises(Exception):
        accountant.begin(
            provider="openai",
            requested_model="model-a",
            effort="high",
            purpose="translation",
            page_number=1,
            request_hash="e" * 64,
            bounds={**dict(limits), "input_bytes": 100, "image_count": 0},
        )


def test_pinned_historical_row_tamper_fails_closed(tmp_path: Path) -> None:
    ledger_path, amendment_path, amendment_sha, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    state = json.loads(ledger_path.read_text(encoding="utf-8"))
    state["reservations"]["historical-1"]["actual_usd"] = "1"
    state["fingerprint"] = fingerprint(
        {key: value for key, value in state.items() if key != "fingerprint"}
    )
    atomic_json(ledger_path, state)
    with pytest.raises(AcceptanceBudgetError, match="pinned base"):
        LegacyAcceptanceBudget(
            ledger_path,
            amendment_path=amendment_path,
            expected_amendment_sha256=amendment_sha,
            run_identity=identity,
            execution_identity=execution,
            pricing_snapshot=snapshot,
        )


def test_amendment_cannot_silently_change_run_or_pricing_identity(tmp_path: Path) -> None:
    ledger_path, amendment_path, amendment_sha, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    with pytest.raises(AcceptanceBudgetError, match="Stable protocol"):
        LegacyAcceptanceBudget(
            ledger_path,
            amendment_path=amendment_path,
            expected_amendment_sha256=amendment_sha,
            run_identity={**identity, "protocol": "legacy_text_v1"},
            execution_identity=execution,
            pricing_snapshot=snapshot,
        )
    altered = _snapshot()
    altered = PricingSnapshot(
        snapshot_id=altered.snapshot_id,
        verified_at=altered.verified_at,
        source=altered.source,
        models={
            "openai:model-a": CostRates(
                2,
                9,
                9,
                "fixture",
                "changed",
                verified_at="2026-09-10",
                pricing_version="acceptance-fixture-v1",
                pricing_model="model-a",
                provider="openai",
            )
        },
    )
    with pytest.raises(AcceptanceBudgetError, match="pricing identity"):
        LegacyAcceptanceBudget(
            ledger_path,
            amendment_path=amendment_path,
            expected_amendment_sha256=amendment_sha,
            run_identity=identity,
            execution_identity=execution,
            pricing_snapshot=altered,
        )


def test_byte_identical_ledger_copy_is_not_a_second_allowance(tmp_path: Path) -> None:
    ledger_path, amendment_path, amendment_sha, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    copied = tmp_path / "copied-budget-ledger.json"
    shutil.copyfile(ledger_path, copied)
    with pytest.raises(AcceptanceBudgetError, match="different ledger path"):
        LegacyAcceptanceBudget(
            copied,
            amendment_path=amendment_path,
            expected_amendment_sha256=amendment_sha,
            run_identity=identity,
            execution_identity=execution,
            pricing_snapshot=snapshot,
        )


def test_amendment_enforces_effort_attempt_and_total_call_limits(tmp_path: Path) -> None:
    ledger_path, amendment_path, amendment_sha, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    budget = LegacyAcceptanceBudget(
        ledger_path,
        amendment_path=amendment_path,
        expected_amendment_sha256=amendment_sha,
        run_identity=identity,
        execution_identity=execution,
        pricing_snapshot=snapshot,
    )
    bounds = {
        **dict(budget.dispatch_limits["openai:translation"]),
        "input_bytes": 100,
        "image_count": 0,
    }

    def metadata(*, effort: str = "high", attempt: int = 1) -> dict:
        return {
            "provider": "openai",
            "requested_model": "model-a",
            "effort": effort,
            "purpose": "translation",
            "page_number": 1,
            "request_hash": REQUEST_HASH,
            **DISPATCH_SCOPE,
            "bounds": bounds,
            "attempt": attempt,
        }

    with pytest.raises(AcceptanceBudgetError, match="effort"):
        budget.reserve("wrong-effort", "0.02", metadata(effort="medium"))
    with pytest.raises(AcceptanceBudgetError, match="attempt"):
        budget.reserve("wrong-attempt", "0.02", metadata(attempt=2))
    _proof(budget)
    budget.reserve("allowed-once", "0.02", metadata())
    budget.finalize(
        "allowed-once",
        "0.001",
        {"outcome": "succeeded", "usage_status": "available"},
    )
    with pytest.raises(AcceptanceBudgetError, match="case call limit"):
        _proof(budget)
        budget.reserve("second-call", "0.02", metadata())


def test_generic_preflight_is_read_only_and_cannot_dispatch(tmp_path: Path) -> None:
    from tooling.structured_acceptance_preflight import preflight

    ledger_path, amendment_path, amendment_sha, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    before = ledger_path.read_bytes()
    result = preflight(
        ledger_path=ledger_path,
        amendment_path=amendment_path,
        expected_amendment_sha256=amendment_sha,
        run_identity=identity,
        execution_identity=execution,
        pricing_snapshot=snapshot,
    )
    assert result["preflight_status"] == "ready"
    assert result["dispatch_enabled"] is False
    assert result["case"]["max_calls"] == 1
    assert result["dispatch_limit_ids"] == ["pilot-page-1"]
    assert ledger_path.read_bytes() == before
