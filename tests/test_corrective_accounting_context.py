"""Fake-only proofs of scoped billing, conservative holds and frozen resume context."""
from __future__ import annotations

from decimal import Decimal
import json

import pytest

from legalpdf_translate.budget_reservations import ReservationBudget, fingerprint
from legalpdf_translate.cost_guardrails import PricingSnapshot
from legalpdf_translate.usage_accounting import DispatchAccounting, DispatchAccountingError, accounting_context


def snapshot(*, version="offline_v1", output=10, tiers=("default", "priority"), scoped=True):
    models = {}
    for model, multiplier in (("model-a", 1), ("alias-a", 3)):
        for tier in tiers:
            premium = 2 if tier == "priority" else 1
            billing = {"service_tier": tier, "billing_scope": "offline_fixture", "currency": "USD"} if scoped else {}
            key = f"openai:{model}|{tier}|offline_fixture|USD" if scoped else f"openai:{model}"
            models[key] = {
                "input_per_1m": 2 * multiplier * premium,
                "cached_input_per_1m": multiplier * premium,
                "output_per_1m": output * multiplier * premium,
                **billing,
            }
    return PricingSnapshot.from_mapping({"snapshot_id": version, "verified_at": "2026-09-10",
        "source": "Synthetic offline fixture; not production rates", "models": models})


def limits(**overrides):
    return {"requested_model": "model-a", "requested_service_tier": "auto",
        "allowed_actual_models": ["alias-a"], "allowed_actual_service_tiers": ["default", "priority"],
        "billing_scope": "offline_fixture", "currency": "USD",
        "max_input_tokens": 1000, "max_output_tokens": 1000, **overrides}


def accountant(tmp_path, *, hard=False, prices=None, declared=None):
    identity = {"run": "synthetic"}
    budget = ReservationBudget(tmp_path / "budget.json", cap_usd="1", identity=identity) if hard else None
    result = DispatchAccounting(tmp_path / "run", run_identity=identity,
        pricing_snapshot=prices or snapshot(), budget_context=budget,
        dispatch_limits={"openai:translation": declared if declared is not None else limits()})
    return result, budget


def begin(accounting, **kwargs):
    declared = accounting.request_limits("openai", "translation", "model-a")
    return accounting.begin(provider="openai", requested_model="model-a", purpose="translation",
        requested_service_tier=declared.get("requested_service_tier"), billing_scope=declared.get("billing_scope"),
        currency=declared.get("currency", "USD"), bounds=dict(declared), request_hash="a" * 64,
        route="responses.create", **kwargs)


def finish(accounting, ticket, **kwargs):
    return accounting.finish(ticket, **{"outcome": "succeeded", "actual_model": "model-a",
        "actual_service_tier": "default", "response_id": "fake-response",
        "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150,
            "input_tokens_details": {"cached_tokens": 20},
            "output_tokens_details": {"reasoning_tokens": 30}}, **kwargs})


def rewrite_journal(accounting, mutate):
    state = json.loads(accounting.journal_path.read_text(encoding="utf-8"))
    mutate(state)
    state.pop("fingerprint", None)
    state["fingerprint"] = fingerprint(state)
    accounting.journal_path.write_text(json.dumps(state), encoding="utf-8")


def test_pricing_catalog_roundtrip_and_explicit_identity():
    prices = snapshot()
    assert PricingSnapshot.from_mapping(prices.to_mapping()).metadata() == prices.metadata()
    assert prices.resolve("openai", "model-a", service_tier="default", billing_scope="offline_fixture").rates.output_per_1m == 10
    assert prices.resolve("openai", "model-a", service_tier="priority", billing_scope="offline_fixture").rates.output_per_1m == 20
    assert prices.resolve("openai", "model-a", service_tier="default", billing_scope="another_scope").rates is None
    assert prices.resolve("openai", "model-a", service_tier="default", billing_scope="offline_fixture", currency="EUR").rates is None
    assert snapshot(scoped=False).resolve("openai", "model-a", service_tier="default", billing_scope="offline_fixture").rates is None


@pytest.mark.parametrize("tier,expected", [("default", "0.00068"), ("priority", "0.00136")])
def test_actual_tier_controls_cost_and_never_double_adds_reasoning(tmp_path, tier, expected):
    accounting, _ = accountant(tmp_path)
    event = finish(accounting, begin(accounting), actual_service_tier=tier)
    assert Decimal(event["cost_usd"]) == Decimal(expected)
    assert accounting.summary()["coverage_status"] == "complete"
    state = json.loads(accounting.journal_path.read_text(encoding="utf-8"))
    assert state["events"][0]["requested_service_tier"] == "auto"
    assert state["events"][1]["actual_service_tier"] == tier
    assert state["events"][1]["actual_billing_scope"] == "offline_fixture"


def test_auto_reserves_worst_case_across_alias_and_tier_then_settles_downgrade(tmp_path):
    accounting, budget = accountant(tmp_path, hard=True)
    ticket = begin(accounting)
    assert Decimal(budget.status()["held_usd"]) == Decimal("0.072")
    event = finish(accounting, ticket, actual_model="alias-a", actual_service_tier="default")
    assert event["budget_status"] == "finalized"
    assert Decimal(budget.status()["known_spend_usd"]) == Decimal("0.00204")
    assert Decimal(budget.status()["held_usd"]) == 0


def test_explicit_priority_can_settle_only_explicitly_allowed_default_downgrade(tmp_path):
    accounting, budget = accountant(tmp_path, hard=True,
        declared=limits(requested_service_tier="priority", allowed_actual_service_tiers=["default"]))
    event = finish(accounting, begin(accounting), actual_service_tier="default")
    assert event["cost_status"] == "available"
    assert budget.status()["blocked"] is False


@pytest.mark.parametrize("updates", [
    {"allowed_actual_service_tiers": []}, {"allowed_actual_service_tiers": ["auto"]},
    {"allowed_actual_service_tiers": ["unpriced_tier"]}, {"billing_scope": None},
    {"billing_scope": "another_scope"}, {"currency": "EUR"},
    {"allowed_actual_models": ["unverified_alias"]},
])
def test_unverified_hard_identity_fails_before_any_hold(tmp_path, updates):
    accounting, budget = accountant(tmp_path, hard=True, declared=limits(**updates))
    with pytest.raises(DispatchAccountingError):
        begin(accounting)
    assert budget.status()["attempts"] == 0


@pytest.mark.parametrize("updates,reason", [
    ({"actual_service_tier": None}, "missing_actual_service_tier"),
    ({"actual_service_tier": "auto"}, "missing_actual_service_tier"),
    ({"actual_service_tier": "unapproved"}, "actual_service_tier_mismatch"),
    ({"actual_billing_scope": "another_scope"}, "billing_scope_mismatch"),
    ({"currency": "EUR"}, "currency_mismatch"),
    ({"actual_model": "another_model"}, "actual_model_mismatch"),
    ({"usage": None, "outcome": "timeout"}, "missing_usage"),
])
def test_missing_or_mismatched_identity_keeps_entire_hold(tmp_path, updates, reason):
    accounting, budget = accountant(tmp_path, hard=True)
    ticket = begin(accounting)
    held = budget.status()["held_usd"]
    event = finish(accounting, ticket, **updates)
    assert event["cost_status"] == reason
    assert event["cost_usd"] is None
    assert accounting.summary()["coverage_status"] == "incomplete"
    assert budget.status()["held_usd"] == held
    assert budget.status()["blocked"] is True
    assert accounting.can_retry is False


def test_legacy_unscoped_rates_never_complete_new_response_cost(tmp_path):
    accounting, _ = accountant(tmp_path, prices=snapshot(scoped=False))
    event = finish(accounting, begin(accounting))
    assert event["cost_status"] == "pricing_unavailable"
    assert accounting.can_retry is True  # WARN/no-cap stays nonblocking.


def test_old_unpriced_run_stays_unpriced_after_global_catalog_refresh(tmp_path):
    original = DispatchAccounting(tmp_path, run_identity={"run": "old"})
    before = original.journal_path.read_bytes()
    resumed = DispatchAccounting(tmp_path, run_identity={"run": "old"}, pricing_snapshot=snapshot(),
        dispatch_limits={"openai:translation": limits()})
    assert resumed.pricing_snapshot is None
    assert not resumed.dispatch_limits
    assert resumed.journal_path.read_bytes() == before
    ticket = resumed.begin(provider="openai", requested_model="model-a", request_hash="a" * 64)
    assert finish(resumed, ticket)["cost_status"] == "pricing_snapshot_unavailable"


def test_priced_run_freezes_full_catalog_bounds_and_settled_totals_after_refresh(tmp_path):
    original, _ = accountant(tmp_path)
    finish(original, begin(original))
    before = original.journal_path.read_bytes()
    previous = original.summary()
    resumed = DispatchAccounting(original.run_dir, run_identity=original.run_identity,
        pricing_snapshot=snapshot(version="today", output=1000),
        dispatch_limits={"openai:translation": limits(max_output_tokens=10)})
    assert resumed.pricing_snapshot.metadata() == original.pricing_snapshot.metadata()
    assert resumed.request_limits("openai", "translation", "model-a")["max_output_tokens"] == 1000
    assert resumed.summary() == previous
    assert resumed.journal_path.read_bytes() == before
    finish(resumed, begin(resumed), response_id="second-fake")
    assert resumed.summary()["cost_usd"] == 0.00136


def test_metadata_only_priced_journal_preserves_history_and_requires_exact_archive(tmp_path):
    original, _ = accountant(tmp_path)
    finish(original, begin(original))
    rewrite_journal(original, lambda state: state.pop("pricing_catalog"))
    old_bytes = original.journal_path.read_bytes()
    resumed = DispatchAccounting(original.run_dir, run_identity=original.run_identity,
        pricing_snapshot=snapshot(version="today", output=1000))
    assert resumed.summary()["cost_usd"] == 0.00068
    with pytest.raises(DispatchAccountingError, match="exact archive"):
        begin(resumed)
    assert resumed.journal_path.read_bytes() == old_bytes
    restored = DispatchAccounting(original.run_dir, run_identity=original.run_identity,
        pricing_snapshot=snapshot(version="today", output=1000), pricing_archives=[snapshot()])
    assert restored.pricing_snapshot.metadata() == snapshot().metadata()
    finish(restored, begin(restored), response_id="archived-price-response")
    assert restored.summary()["cost_usd"] == 0.00136


def test_tampered_saved_catalog_does_not_reprice_or_dispatch(tmp_path):
    original, _ = accountant(tmp_path)
    key = next(iter(snapshot().models))
    rewrite_journal(original, lambda state: state["pricing_catalog"]["models"][key].update(output_per_1m=0))
    before = original.journal_path.read_bytes()
    with pytest.raises(DispatchAccountingError, match="catalog identity"):
        DispatchAccounting(original.run_dir, run_identity=original.run_identity, pricing_snapshot=snapshot())
    assert original.journal_path.read_bytes() == before


def test_old_model_only_cost_is_not_retroactively_certified_or_repriced(tmp_path):
    original, _ = accountant(tmp_path)
    finish(original, begin(original))
    def remove_billing_evidence(state):
        for key in ("actual_service_tier", "actual_billing_scope", "currency"):
            state["events"][1].pop(key)
    rewrite_journal(original, remove_billing_evidence)
    before = original.journal_path.read_bytes()
    resumed = DispatchAccounting(original.run_dir, run_identity=original.run_identity,
        pricing_snapshot=snapshot(version="today", output=1000))
    assert resumed.summary()["known_cost_usd"] == 0.00068
    assert resumed.summary()["cost_usd"] is None
    assert resumed.summary()["billing_identity_incomplete_count"] == 1
    assert resumed.journal_path.read_bytes() == before


def test_endpoint_journal_never_retains_userinfo_or_query_secrets(tmp_path):
    accounting, _ = accountant(tmp_path)
    begin(accounting, base_url="https://username:credential@invalid.example/v1/?token=private")
    journal = accounting.journal_path.read_text(encoding="utf-8")
    assert "credential" not in journal
    assert "token=private" not in journal
    assert json.loads(journal)["events"][0]["base_url"] is None


def test_unknown_model_warn_does_not_borrow_known_model_limits(tmp_path):
    accounting = DispatchAccounting(tmp_path, run_identity={}, pricing_snapshot=snapshot(),
        dispatch_limits={"openai:*:model-a": limits()})
    assert accounting.request_limits("openai", "ocr", "model-a")["max_output_tokens"] == 1000
    assert accounting.request_limits("openai", "ocr", "unknown-model") == {}


def test_nested_dispatch_limit_mutation_cannot_authorize_new_hold(tmp_path):
    accounting, budget = accountant(tmp_path, hard=True)
    accounting.dispatch_limits["openai:translation"]["allowed_actual_models"].append("new-alias")
    with pytest.raises(DispatchAccountingError, match="Immutable dispatch limits"):
        begin(accounting)
    assert budget.status()["attempts"] == 0


@pytest.mark.parametrize("after_reserve", [False, True])
def test_replacing_in_memory_catalog_cannot_change_saved_run_prices(tmp_path, after_reserve):
    accounting, budget = accountant(tmp_path, hard=True)
    ticket = begin(accounting) if after_reserve else None
    before = accounting.journal_path.read_bytes()
    held = budget.status()["held_usd"]
    accounting.pricing_snapshot = snapshot(version="replacement", output=1)
    with pytest.raises(DispatchAccountingError, match="Immutable pricing context"):
        if after_reserve:
            finish(accounting, ticket)
        else:
            begin(accounting)
    assert accounting.journal_path.read_bytes() == before
    assert budget.status()["held_usd"] == held
    assert budget.status()["attempts"] == int(after_reserve)


def test_replacing_budget_object_cannot_silently_redirect_the_allowance(tmp_path):
    accounting, original = accountant(tmp_path, hard=True)
    replacement = ReservationBudget(tmp_path / "different-allowance.json", cap_usd="1", identity=original.identity)
    accounting.budget_context = replacement
    with pytest.raises(DispatchAccountingError, match="Immutable budget context"):
        begin(accounting)
    assert original.status()["attempts"] == replacement.status()["attempts"] == 0


def test_acceptance_verification_forwards_exact_bound_page_without_self_approval(tmp_path):
    captured = []
    class Budget:
        hard = False
        binding_identity = {"campaign": "fixture"}
        def verify_dispatch(self, **kwargs):
            captured.append(kwargs)
    accounting = DispatchAccounting(tmp_path, run_identity={}, budget_context=Budget())
    request = {"model": "model-a", "input": "Synthetic fixture"}
    with accounting_context(accounting, purpose="translation", page_number=5):
        accounting.verify_dispatch(request=request, route="responses.create", provider="openai",
            purpose="translation", attempt=1, requested_service_tier="auto",
            billing_scope="offline_fixture", currency="USD", base_url="https://api.openai.com/v1/")
    assert captured[0]["page_number"] == 5
    assert captured[0]["request"] is request
    assert accounting.summary()["call_count"] == 0
