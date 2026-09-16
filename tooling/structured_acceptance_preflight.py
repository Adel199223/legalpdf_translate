"""Offline-only assembly and preflight for structured acceptance accounting.

This tool cannot construct a provider client or dispatch a request.  It validates
caller-supplied, private identities and exposes a factory that later explicitly
authorized code can bind to the normal dispatch accounting seam.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _REPOSITORY_ROOT / "src"
sys.path[:] = [item for item in sys.path if item != str(_SOURCE_ROOT)]
sys.path.insert(0, str(_SOURCE_ROOT))

import legalpdf_translate as _legalpdf_package

if not Path(_legalpdf_package.__file__).resolve().is_relative_to(_SOURCE_ROOT.resolve()):
    raise RuntimeError("Acceptance preflight imported LegalPDF from another worktree.")

from legalpdf_translate.acceptance_budget import LegacyAcceptanceBudget
from legalpdf_translate.cost_guardrails import PricingSnapshot
from legalpdf_translate.usage_accounting import DispatchAccounting


def load_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} is unreadable.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object.")
    return value


def build_acceptance_accounting(
    *,
    run_dir: Path,
    ledger_path: Path,
    amendment_path: Path,
    expected_amendment_sha256: str,
    run_identity: Mapping[str, Any],
    execution_identity: Mapping[str, Any],
    pricing_snapshot: PricingSnapshot | Mapping[str, Any],
    historical_incomplete: bool = False,
) -> DispatchAccounting:
    """Build accounting only; the returned object has no provider transport."""

    snapshot = (
        pricing_snapshot
        if isinstance(pricing_snapshot, PricingSnapshot)
        else PricingSnapshot.from_mapping(pricing_snapshot)
    )
    budget = LegacyAcceptanceBudget(
        ledger_path,
        amendment_path=amendment_path,
        expected_amendment_sha256=expected_amendment_sha256,
        run_identity=run_identity,
        execution_identity=execution_identity,
        pricing_snapshot=snapshot,
    )
    if not budget.dispatch_enabled:
        raise ValueError("Legacy acceptance approval is inspection-only; v2 physical approval is required.")
    return DispatchAccounting(
        run_dir,
        run_identity=run_identity,
        pricing_snapshot=snapshot,
        budget_context=budget,
        dispatch_limits=budget.dispatch_limits,
        historical_incomplete=historical_incomplete,
    )


def preflight(
    *,
    ledger_path: Path,
    amendment_path: Path,
    expected_amendment_sha256: str,
    run_identity: Mapping[str, Any],
    execution_identity: Mapping[str, Any],
    pricing_snapshot: PricingSnapshot | Mapping[str, Any],
) -> dict[str, Any]:
    """Validate immutable spend authority without creating a run or dispatch."""

    snapshot = (
        pricing_snapshot
        if isinstance(pricing_snapshot, PricingSnapshot)
        else PricingSnapshot.from_mapping(pricing_snapshot)
    )
    budget = LegacyAcceptanceBudget(
        ledger_path,
        amendment_path=amendment_path,
        expected_amendment_sha256=expected_amendment_sha256,
        run_identity=run_identity,
        execution_identity=execution_identity,
        pricing_snapshot=snapshot,
    )
    status = budget.status()
    amendment_bytes = Path(amendment_path).read_bytes()
    return {
        "dispatch_enabled": False,
        "preflight_status": "blocked" if status["blocked_reason"] or not budget.dispatch_enabled else "ready",
        "benchmark_id": status["benchmark_id"],
        "cap_usd": status["cap_usd"],
        "campaign_cap_usd": status["campaign_cap_usd"],
        "known_spend_usd": status["known_spend_usd"],
        "held_usd": status["held_usd"],
        "remaining_usd": status["remaining_usd"],
        "attempts": status["attempts"],
        "blocked_reason": status["blocked_reason"] or (None if budget.dispatch_enabled else "legacy_approval_read_only"),
        "amendment_fingerprint": status["amendment_fingerprint"],
        "amendment_sha256": hashlib.sha256(amendment_bytes).hexdigest(),
        "approval_schema_version": budget.amendment["schema_version"],
        "physical_provenance_verified": budget.dispatch_enabled,
        "runtime_context_bound": budget.runtime_context_bound,
        "pricing_snapshot": snapshot.metadata(),
        "case": dict(budget.case),
        "dispatch_limit_ids": sorted(
            str(limit.get("limit_id") or key)
            for key, limit in budget.dispatch_limits.items()
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate structured-translation acceptance spend authority offline."
    )
    parser.add_argument("--ledger", required=True, type=Path)
    parser.add_argument("--amendment", required=True, type=Path)
    parser.add_argument("--expected-amendment-sha256", required=True)
    parser.add_argument("--run-identity", required=True, type=Path)
    parser.add_argument("--execution-identity", required=True, type=Path)
    parser.add_argument("--pricing-snapshot", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = preflight(
            ledger_path=args.ledger,
            amendment_path=args.amendment,
            expected_amendment_sha256=args.expected_amendment_sha256,
            run_identity=load_json_mapping(args.run_identity, "run identity"),
            execution_identity=load_json_mapping(
                args.execution_identity,
                "execution identity",
            ),
            pricing_snapshot=load_json_mapping(args.pricing_snapshot, "pricing snapshot"),
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "dispatch_enabled": False,
                    "preflight_status": "failed",
                    "error": type(exc).__name__,
                },
                sort_keys=True,
            )
        )
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0 if result["preflight_status"] == "ready" else 2


if __name__ == "__main__":
    sys.exit(main())
