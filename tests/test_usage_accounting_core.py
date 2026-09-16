from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
from pathlib import Path

import pytest

from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.cost_guardrails import (
    CostRates,
    PricingSnapshot,
    estimate_cost_decimal,
)
from legalpdf_translate.usage_accounting import (
    DispatchAccounting,
    DispatchAccountingError,
    accounting_context,
    normalize_usage,
)


def _snapshot(*, output_rate: float = 8.0) -> PricingSnapshot:
    return PricingSnapshot(
        snapshot_id="offline-fixture-v1",
        verified_at="2026-09-10",
        source="checked-in test fixture",
        models={
            "openai:model-a": CostRates(
                input_per_1m=2.0,
                output_per_1m=output_rate,
                reasoning_per_1m=output_rate,
                cached_input_per_1m=1.0,
                cache_write_per_1m=3.0,
                source="fixture",
                explanation="fixture",
                verified_at="2026-09-10",
                pricing_version="offline-fixture-v1",
                pricing_model="model-a",
                provider="openai",
                service_tier="default",
                billing_scope="offline_fixture",
            )
        },
    )


def _usage() -> dict[str, int]:
    return {
        "input_tokens": 100,
        "output_tokens": 50,
        "total_tokens": 150,
        "reasoning_tokens": 30,
        "cached_input_tokens": 20,
        "cache_write_tokens": 10,
    }


def test_inclusive_output_and_cache_breakdowns_are_not_double_priced() -> None:
    rates = next(iter(_snapshot().models.values()))
    assert estimate_cost_decimal(
        input_tokens=100,
        output_tokens=50,
        reasoning_tokens=30,
        cached_input_tokens=20,
        cache_write_tokens=10,
        rates=rates,
    ) == Decimal("0.000590000")


def test_usage_normalization_is_strict_and_adapts_gemini_totals() -> None:
    assert normalize_usage(_usage())["usage_status"] == "available"
    invalid = normalize_usage({**_usage(), "reasoning_tokens": 51})
    assert invalid["usage_status"] == "invalid"
    gemini = normalize_usage(
        {
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
            "thoughtsTokenCount": 3,
            "totalTokenCount": 18,
        },
        provider="gemini",
    )
    assert gemini == {
        "input_tokens": 10,
        "output_tokens": 8,
        "total_tokens": 18,
        "reasoning_tokens": 3,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "usage_status": "available",
        "total_tokens_source": "provider",
        "reasoning_included_in_output": True,
    }


def test_durable_journal_records_context_cost_and_reopens_exactly(tmp_path: Path) -> None:
    accountant = DispatchAccounting(
        tmp_path,
        run_identity={"source_sha256": "1" * 64, "protocol": "legal_blocks_v2"},
        pricing_snapshot=_snapshot(),
    )
    with accounting_context(accountant, purpose="translation", page_number=2):
        ticket = accountant.begin(
            provider="openai",
            requested_model="model-a",
            effort="high",
            request_hash="a" * 64,
            bounds={"max_output_tokens": 100},
            billing_scope="offline_fixture",
        )
    accountant.finish(
        ticket,
        outcome="succeeded",
        usage=_usage(),
        response_id="response-1",
        actual_model="model-a",
        actual_service_tier="default",
    )
    summary = accountant.summary()
    assert summary["coverage_status"] == "complete"
    assert summary["cost_usd"] == 0.00059
    assert summary["by_purpose"]["translation"]["provider_dispatch_count"] == 1
    assert summary["pricing_snapshot"]["rates_sha256"]
    reopened = DispatchAccounting(
        tmp_path,
        run_identity={"source_sha256": "1" * 64, "protocol": "legal_blocks_v2"},
        pricing_snapshot=_snapshot(),
    )
    assert reopened.summary() == summary


def test_same_snapshot_label_refresh_resumes_original_frozen_catalog(tmp_path: Path) -> None:
    DispatchAccounting(
        tmp_path,
        run_identity={"source_sha256": "1" * 64},
        pricing_snapshot=_snapshot(),
    )
    reopened = DispatchAccounting(
        tmp_path,
        run_identity={"source_sha256": "1" * 64},
        pricing_snapshot=_snapshot(output_rate=9.0),
    )
    assert reopened.pricing_snapshot.metadata() == _snapshot().metadata()


def test_duplicate_response_id_is_serialized_and_counted_once(tmp_path: Path) -> None:
    accountant = DispatchAccounting(
        tmp_path,
        run_identity={"source_sha256": "2" * 64},
        pricing_snapshot=_snapshot(),
    )
    tickets = [
        accountant.begin(
            provider="openai",
            requested_model="model-a",
            request_hash=character * 64,
        )
        for character in ("a", "b")
    ]

    def finish(ticket):
        return accountant.finish(
            ticket,
            outcome="succeeded",
            usage=_usage(),
            response_id="same-response",
            actual_model="model-a",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(finish, ticket) for ticket in tickets]
    outcomes = []
    for future in futures:
        try:
            future.result()
            outcomes.append("ok")
        except DispatchAccountingError:
            outcomes.append("blocked")
    assert sorted(outcomes) == ["blocked", "ok"]
    assert accountant.summary()["in_flight_count"] == 1
    assert accountant.summary()["cost_usd"] is None


def test_historical_usage_keeps_newly_priced_run_incomplete(tmp_path: Path) -> None:
    accountant = DispatchAccounting(
        tmp_path,
        run_identity={"source_sha256": "3" * 64},
        pricing_snapshot=_snapshot(),
        historical_incomplete=True,
    )
    ticket = accountant.begin(
        provider="openai",
        requested_model="model-a",
        request_hash="c" * 64,
        billing_scope="offline_fixture",
    )
    accountant.finish(
        ticket,
        outcome="succeeded",
        usage=_usage(),
        response_id="response-3",
        actual_model="model-a",
        actual_service_tier="default",
    )
    summary = accountant.summary()
    assert summary["known_cost_usd"] == 0.00059
    assert summary["cost_usd"] is None
    assert summary["historical_incomplete"] is True


def test_hard_ceiling_covers_more_expensive_allowed_actual_model(tmp_path: Path) -> None:
    snapshot = PricingSnapshot(
        snapshot_id="alias-fixture",
        verified_at="2026-09-10",
        source="test",
        models={
            "openai:request-model": CostRates(
                1, 2, 2, "fixture", "requested",
                verified_at="2026-09-10",
                pricing_version="alias-fixture",
                pricing_model="request-model",
                provider="openai",
                service_tier="default",
                billing_scope="offline_fixture",
            ),
            "openai:actual-model": CostRates(
                10, 20, 20, "fixture", "actual",
                verified_at="2026-09-10",
                pricing_version="alias-fixture",
                pricing_model="actual-model",
                provider="openai",
                service_tier="default",
                billing_scope="offline_fixture",
            ),
        },
    )
    identity = {"source_sha256": "4" * 64}
    budget = ReservationBudget(
        tmp_path / "budget.json",
        cap_usd="1",
        identity=identity,
    )
    limits = {
        "openai:translation": {
            "requested_model": "request-model",
            "allowed_actual_models": ["actual-model"],
            "max_input_tokens": 1000,
            "max_output_tokens": 1000,
            "requested_service_tier": "auto",
            "allowed_actual_service_tiers": ["default"],
            "billing_scope": "offline_fixture",
            "currency": "USD",
        }
    }
    accountant = DispatchAccounting(
        tmp_path / "accounting",
        run_identity=identity,
        pricing_snapshot=snapshot,
        budget_context=budget,
        dispatch_limits=limits,
    )
    returned = accountant.request_limits("openai", "translation", "request-model")
    ticket = accountant.begin(
        provider="openai",
        requested_model="request-model",
        purpose="translation",
        request_hash="d" * 64,
        bounds={**dict(returned), "input_bytes": 50, "image_count": 0},
        billing_scope="offline_fixture",
    )
    assert Decimal(budget.status()["held_usd"]) == Decimal("0.030000000")
    accountant.finish(
        ticket,
        outcome="succeeded",
        usage={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
        response_id="alias-response",
        actual_model="actual-model",
        actual_service_tier="default",
    )
    assert accountant.summary()["coverage_status"] == "complete"
    assert Decimal(budget.status()["known_spend_usd"]) == Decimal("0.000030000")


def test_not_dispatched_is_proved_zero_and_does_not_count_as_provider_call(tmp_path: Path) -> None:
    accountant = DispatchAccounting(
        tmp_path,
        run_identity={"source_sha256": "5" * 64},
        pricing_snapshot=_snapshot(),
    )
    ticket = accountant.begin(
        provider="openai",
        requested_model="model-a",
        request_hash="e" * 64,
    )
    accountant.finish(ticket, outcome="not_dispatched")
    summary = accountant.summary()
    assert summary["cost_usd"] == 0.0
    assert summary["not_dispatched_count"] == 1
    assert summary["provider_dispatch_count"] == 0


def test_journal_contains_no_request_content(tmp_path: Path) -> None:
    accountant = DispatchAccounting(
        tmp_path,
        run_identity={"source_sha256": "6" * 64},
    )
    with pytest.raises(DispatchAccountingError, match="forbidden"):
        accountant.begin(
            provider="openai",
            requested_model="model-a",
            request_hash="f" * 64,
            bounds={"prompt": "PRIVATE SOURCE"},
        )
    assert "PRIVATE SOURCE" not in (tmp_path / "dispatch_accounting.json").read_text(
        encoding="utf-8"
    )
