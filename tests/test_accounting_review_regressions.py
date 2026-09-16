"""Offline regressions for the independent Stage 2 accounting review."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.cost_guardrails import CostRates, PricingSnapshot
from legalpdf_translate.usage_accounting import DispatchAccounting, DispatchAccountingError


@pytest.fixture
def hard_accountant(tmp_path: Path):
    identity = {"source_sha256": "7" * 64}
    rates = {}
    for model, input_rate, output_rate in (("model-a", 2, 8), ("alias-a", 10, 20)):
        rates[f"openai:{model}"] = CostRates(
            input_per_1m=input_rate,
            output_per_1m=output_rate,
            reasoning_per_1m=output_rate,
            source="offline review fixture",
            explanation="Synthetic prices; not production pricing evidence",
            verified_at="2026-09-10",
            pricing_version="review-fixture-v1",
            pricing_model=model,
            provider="openai",
            service_tier="default",
            billing_scope="offline_fixture",
        )
    snapshot = PricingSnapshot(
        snapshot_id="review-fixture-v1",
        verified_at="2026-09-10",
        source="offline review fixture",
        models=rates,
    )
    budget = ReservationBudget(tmp_path / "budget.json", cap_usd="1", identity=identity)
    accountant = DispatchAccounting(
        tmp_path / "accounting",
        run_identity=identity,
        pricing_snapshot=snapshot,
        budget_context=budget,
        dispatch_limits={
            "openai:translation": {
                "requested_model": "model-a",
                "allowed_actual_models": ["alias-a"],
                "max_input_tokens": 1000,
                "max_output_tokens": 1000,
                "image_bound_verified": True,
                "max_image_input_tokens": 500,
                "max_image_count": 1,
                "requested_service_tier": "auto",
                "allowed_actual_service_tiers": ["default"],
                "billing_scope": "offline_fixture",
                "currency": "USD",
            }
        },
    )
    return accountant, budget


def _bounds(accountant):
    return {
        **dict(accountant.request_limits("openai", "translation", "model-a")),
        "input_bytes": 100,
        "image_count": 0,
    }


def _begin(accountant, *, character="a", bounds=None):
    return accountant.begin(
        provider="openai",
        requested_model="model-a",
        purpose="translation",
        request_hash=character * 64,
        bounds=_bounds(accountant) if bounds is None else bounds,
        billing_scope="offline_fixture",
    )


def _finish(accountant, ticket, **overrides):
    return accountant.finish(
        ticket,
        **{
            "outcome": "succeeded",
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            "response_id": "review-response",
            "actual_model": "model-a",
            "actual_service_tier": "default",
            **overrides,
        },
    )


def _assert_latched_before_reserve(accountant, budget, monkeypatch):
    before = budget.status()

    def forbidden_reserve(*_args, **_kwargs):
        pytest.fail("A latched accountant must not create another reservation")

    monkeypatch.setattr(budget, "reserve", forbidden_reserve)
    assert accountant.can_retry is False
    with pytest.raises(DispatchAccountingError, match="not safe"):
        _begin(accountant, character="f")
    assert budget.status() == before


@pytest.mark.parametrize("phase", ["begin", "finish"])
@pytest.mark.parametrize("operation", ["_load_unlocked", "_save_unlocked"])
def test_journal_persistence_failure_latches_before_any_later_reservation(
    hard_accountant, monkeypatch, phase, operation,
):
    accountant, budget = hard_accountant
    ticket = _begin(accountant) if phase == "finish" else None
    original = getattr(accountant, operation)

    def fail_persistence(*_args, **_kwargs):
        raise OSError("synthetic journal persistence failure")

    monkeypatch.setattr(accountant, operation, fail_persistence)
    with pytest.raises(OSError, match="synthetic journal"):
        if phase == "begin":
            _begin(accountant)
        else:
            _finish(accountant, ticket)
    monkeypatch.setattr(accountant, operation, original)
    assert budget.status()["attempts"] == 1
    if phase == "begin" or operation == "_load_unlocked":
        assert Decimal(budget.status()["held_usd"]) > 0
    _assert_latched_before_reserve(accountant, budget, monkeypatch)


def test_duplicate_provider_response_keeps_second_full_hold_and_latches(
    hard_accountant, monkeypatch,
):
    accountant, budget = hard_accountant
    first = _begin(accountant)
    one_hold = Decimal(budget.status()["held_usd"])
    second = _begin(accountant, character="b")
    assert Decimal(budget.status()["held_usd"]) == one_hold * 2
    _finish(accountant, first)
    with pytest.raises(DispatchAccountingError, match="already bound"):
        _finish(accountant, second)
    assert Decimal(budget.status()["held_usd"]) == one_hold
    assert accountant.summary()["in_flight_count"] == 1
    assert accountant.summary()["coverage_status"] == "incomplete"
    assert accountant.summary()["cost_usd"] is None
    _assert_latched_before_reserve(accountant, budget, monkeypatch)


def test_invalid_canonical_usage_stays_invalid_in_summary_and_after_reopen(hard_accountant):
    accountant, budget = hard_accountant
    ticket = _begin(accountant)
    held = budget.status()["held_usd"]
    result = _finish(
        accountant,
        ticket,
        usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
               "reasoning_tokens": "invalid-synthetic-value"},
    )
    assert result["usage"]["usage_status"] == "invalid"
    assert result["usage"]["reasoning_tokens"] is None
    summary = accountant.summary()
    assert summary["invalid_usage_count"] == 1
    assert summary["missing_usage_count"] == 0
    assert summary["unknown_cost_count"] == 1
    assert summary["coverage_status"] == "incomplete"
    assert summary["cost_usd"] is None
    assert all(value == 0 for value in summary["totals"].values())
    assert budget.status()["held_usd"] == held
    reopened = DispatchAccounting(
        accountant.run_dir,
        run_identity=accountant.run_identity,
        pricing_snapshot=accountant.pricing_snapshot,
        budget_context=budget,
        dispatch_limits=accountant.dispatch_limits,
    )
    assert reopened.summary() == summary


def test_known_cost_above_reserved_ceiling_cannot_claim_complete_coverage(
    hard_accountant, monkeypatch,
):
    accountant, budget = hard_accountant
    ticket = _begin(accountant)
    held = budget.status()["held_usd"]
    result = _finish(
        accountant,
        ticket,
        usage={"input_tokens": 10000, "output_tokens": 10000, "total_tokens": 20000},
    )
    assert result["cost_status"] == "available"
    assert result["budget_status"] == "uncertain"
    assert result["budget_blocked_reason"] == "reservation_ceiling_exceeded"
    summary = accountant.summary()
    assert summary["known_cost_usd"] == 0.1
    assert summary["unknown_cost_count"] == 0
    assert summary["budget_incomplete_count"] == 1
    assert summary["by_purpose"]["translation"]["budget_incomplete_count"] == 1
    assert summary["coverage_status"] == "incomplete"
    assert summary["cost_usd"] is None
    assert budget.status()["held_usd"] == held
    _assert_latched_before_reserve(accountant, budget, monkeypatch)


@pytest.mark.parametrize("key,replacement", [
    ("allowed_actual_models", None),
    ("allowed_actual_models", []),
    ("allowed_actual_models", ["model-a"]),
    ("max_image_count", None),
    ("max_image_count", 2),
    ("max_image_count", 0),
])
def test_hard_bounds_cannot_omit_or_change_frozen_alias_and_image_limits(
    hard_accountant, monkeypatch, key, replacement,
):
    accountant, budget = hard_accountant
    bounds = _bounds(accountant)
    if replacement is None:
        bounds.pop(key)
    else:
        bounds[key] = replacement

    def forbidden_reserve(*_args, **_kwargs):
        pytest.fail("Altered hard bounds must fail before creating a reservation")

    monkeypatch.setattr(budget, "reserve", forbidden_reserve)
    with pytest.raises(DispatchAccountingError, match=f"configured {key}"):
        _begin(accountant, bounds=bounds)
    assert budget.status()["attempts"] == 0
    assert accountant.summary()["attempt_count"] == 0
