from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from legalpdf_translate.acceptance_budget import (
    AcceptanceBudgetError,
    LegacyAcceptanceBudget,
    stable_acceptance_run_identity,
)
from legalpdf_translate.budget_reservations import atomic_json, fingerprint
from legalpdf_translate.cost_guardrails import PricingSnapshot
from tooling.structured_acceptance_preflight import preflight
from tests.test_acceptance_budget_adapter import _write_fixture, _proof, _request, REQUEST_HASH, DISPATCH_SCOPE
from legalpdf_translate.acceptance_provenance import request_fingerprint


def _write_amendment(path: Path, amendment: dict) -> str:
    amendment.pop("fingerprint", None)
    amendment["fingerprint"] = fingerprint(amendment)
    atomic_json(path, amendment)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _open_budget(
    ledger_path: Path,
    amendment_path: Path,
    amendment_sha256: str,
    run_identity: dict,
    execution_identity: dict,
    pricing_snapshot,
) -> LegacyAcceptanceBudget:
    return LegacyAcceptanceBudget(
        ledger_path,
        amendment_path=amendment_path,
        expected_amendment_sha256=amendment_sha256,
        run_identity=run_identity,
        execution_identity=execution_identity,
        pricing_snapshot=pricing_snapshot,
    )


def _dispatch_metadata(
    budget: LegacyAcceptanceBudget,
    *,
    page_number: int,
    request_hash: str,
    attempt: int = 1,
) -> dict:
    limit = budget.dispatch_limits["openai:translation"]
    if request_hash == request_fingerprint(_request(page_number)):
        _proof(budget, page_number)
    return {
        "provider": "openai",
        "requested_model": "model-a",
        "effort": "high",
        "purpose": "translation",
        "page_number": page_number,
        "request_hash": request_hash,
        "attempt": attempt,
        **DISPATCH_SCOPE,
        "bounds": {
            "max_input_tokens": limit["max_input_tokens"],
            "max_output_tokens": limit["max_output_tokens"],
            "input_bytes": 100,
            "image_count": 0,
        },
    }


def test_external_digest_rejects_self_refingerprinted_amendment_edit(tmp_path: Path) -> None:
    ledger, amendment_path, approved_sha, identity, execution, snapshot, _ = (
        _write_fixture(tmp_path)
    )
    before = ledger.read_bytes()
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    amendment["approved_by"] = "edited-after-approval"
    _write_amendment(amendment_path, amendment)

    with pytest.raises(AcceptanceBudgetError, match="externally approved SHA-256"):
        _open_budget(
            ledger,
            amendment_path,
            approved_sha,
            identity,
            execution,
            snapshot,
        )
    assert ledger.read_bytes() == before


def test_campaign_cap_persists_across_distinct_case_amendments(tmp_path: Path) -> None:
    ledger, amendment_path, _, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    first = json.loads(amendment_path.read_text(encoding="utf-8"))
    first["case"]["ceiling_usd"] = "0.06"
    first["dispatch_limits"]["openai:translation"]["ceiling_usd"] = "0.06"
    first_sha = _write_amendment(amendment_path, first)
    first_budget = _open_budget(
        ledger,
        amendment_path,
        first_sha,
        identity,
        execution,
        snapshot,
    )
    first_budget.reserve(
        "campaign-case-one",
        "0.06",
        _dispatch_metadata(first_budget, page_number=1, request_hash=REQUEST_HASH),
    )
    first_budget.finalize(
        "campaign-case-one",
        "0.06",
        {"outcome": "succeeded", "usage_status": "available"},
    )

    ledger_state = json.loads(ledger.read_text(encoding="utf-8"))
    second = deepcopy(first)
    second["case"] = {"case_id": "ar-case-two", "max_calls": 1, "ceiling_usd": "0.05"}
    second_limit = second["dispatch_limits"]["openai:translation"]
    second_limit["ceiling_usd"] = "0.05"
    second_limit["allowed_request_hashes"] = [REQUEST_HASH]
    second["prior_amendments"] = ledger_state["acceptance_campaigns"][second["campaign_id"]]["amendments"]
    second["prior_reservations_fingerprint"] = fingerprint({key: row for key, row in ledger_state["reservations"].items()
        if row.get("execution", {}).get("campaign_id") == second["campaign_id"]})
    second_path = tmp_path / "acceptance-amendment-case-two.json"
    second_sha = _write_amendment(second_path, second)
    second_budget = _open_budget(
        ledger,
        second_path,
        second_sha,
        identity,
        execution,
        snapshot,
    )

    with pytest.raises(AcceptanceBudgetError, match="campaign ceiling"):
        second_budget.reserve(
            "campaign-case-two",
            "0.05",
            _dispatch_metadata(second_budget, page_number=1, request_hash=REQUEST_HASH),
        )


def test_crash_hold_makes_read_only_preflight_blocked(tmp_path: Path) -> None:
    ledger, amendment_path, amendment_sha, identity, execution, snapshot, _ = (
        _write_fixture(tmp_path)
    )
    budget = _open_budget(
        ledger,
        amendment_path,
        amendment_sha,
        identity,
        execution,
        snapshot,
    )
    budget.reserve(
        "crashed-dispatch",
        "0.02",
        _dispatch_metadata(budget, page_number=1, request_hash=REQUEST_HASH),
    )
    before_preflight = ledger.read_bytes()

    result = preflight(
        ledger_path=ledger,
        amendment_path=amendment_path,
        expected_amendment_sha256=amendment_sha,
        run_identity=identity,
        execution_identity=execution,
        pricing_snapshot=snapshot,
    )

    assert result["dispatch_enabled"] is False
    assert result["preflight_status"] == "blocked"
    assert result["blocked_reason"] == "unresolved_dispatch"
    assert Decimal(result["held_usd"]) == Decimal("0.02")
    assert result["remaining_usd"] == "0"
    assert ledger.read_bytes() == before_preflight


def test_approved_request_hashes_cannot_be_cross_paired_with_pages(tmp_path: Path) -> None:
    ledger, amendment_path, _, identity, execution, snapshot, _ = _write_fixture(tmp_path)
    identity["selection"] = [1, 2]
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    amendment["stable_run_identity"] = stable_acceptance_run_identity(identity)
    amendment["case"]["max_calls"] = 2
    limit = amendment["dispatch_limits"]["openai:translation"]
    limit.update(
        allowed_pages=[1, 2],
        allowed_request_hashes=[REQUEST_HASH, request_fingerprint(_request(2))],
        approved_calls=[
            {"page_number": 1, "attempt": 1, "request_hash": REQUEST_HASH},
            {"page_number": 2, "attempt": 1, "request_hash": request_fingerprint(_request(2))},
        ],
        max_calls=2,
        max_calls_per_page=1,
        max_attempts=1,
    )
    amendment_sha = _write_amendment(amendment_path, amendment)
    budget = _open_budget(
        ledger,
        amendment_path,
        amendment_sha,
        identity,
        execution,
        snapshot,
    )
    before = ledger.read_bytes()

    with pytest.raises(AcceptanceBudgetError, match="approved call tuple"):
        budget.reserve(
            "cross-paired",
            "0.02",
            _dispatch_metadata(budget, page_number=1, request_hash=request_fingerprint(_request(2))),
        )
    assert ledger.read_bytes() == before

    budget.reserve(
        "approved-page-one",
        "0.02",
        _dispatch_metadata(budget, page_number=1, request_hash=REQUEST_HASH),
    )
    budget.finalize(
        "approved-page-one",
        "0.001",
        {"outcome": "succeeded", "usage_status": "available"},
    )
    with pytest.raises(AcceptanceBudgetError, match="approved call tuple"):
        budget.reserve(
            "wrong-page-two-hash",
            "0.02",
            _dispatch_metadata(budget, page_number=2, request_hash="e" * 64),
        )
    budget.reserve(
        "approved-page-two",
        "0.02",
        _dispatch_metadata(budget, page_number=2, request_hash=request_fingerprint(_request(2))),
    )


def test_direct_cli_without_pythonpath_is_read_only_and_dispatch_disabled(
    tmp_path: Path,
) -> None:
    ledger, amendment, amendment_sha, identity, execution, snapshot, _ = _write_fixture(
        tmp_path
    )
    repository = Path(__file__).resolve().parents[1]
    script = repository / "tooling" / "structured_acceptance_preflight.py"
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() not in {"PYTHONPATH", "PYTHONHOME"}
    }
    environment["PYTHONNOUSERSITE"] = "1"
    before = ledger.read_bytes()

    no_arguments = subprocess.run(
        [sys.executable, str(script)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert no_arguments.returncode == 2
    assert ledger.read_bytes() == before

    pricing_payload = {
        "snapshot_id": "acceptance-fixture-v1",
        "verified_at": "2026-09-10",
        "source": "offline test fixture",
        "models": {
            "openai:model-a|default|fixture-standard|USD": {
                "input_per_1m": 2,
                "output_per_1m": 8,
                "reasoning_per_1m": 8,
                "cached_input_per_1m": 1,
                "cache_write_per_1m": 3,
                "source": "fixture",
                "explanation": "fixture",
                "verified_at": "2026-09-10",
                "pricing_version": "acceptance-fixture-v1",
                "pricing_model": "model-a",
                "provider": "openai",
                "service_tier": "default", "billing_scope": "fixture-standard", "currency": "USD",
            }
        },
    }
    assert PricingSnapshot.from_mapping(pricing_payload).metadata() == snapshot.metadata()
    identity_path = tmp_path / "run-identity.json"
    execution_path = tmp_path / "execution-identity.json"
    pricing_path = tmp_path / "pricing-snapshot.json"
    for path, value in (
        (identity_path, identity),
        (execution_path, execution),
        (pricing_path, pricing_payload),
    ):
        path.write_text(json.dumps(value), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--ledger",
            str(ledger),
            "--amendment",
            str(amendment),
            "--expected-amendment-sha256",
            amendment_sha,
            "--run-identity",
            str(identity_path),
            "--execution-identity",
            str(execution_path),
            "--pricing-snapshot",
            str(pricing_path),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads(completed.stdout)
    assert result["preflight_status"] == "ready"
    assert result["dispatch_enabled"] is False
    assert ledger.read_bytes() == before
