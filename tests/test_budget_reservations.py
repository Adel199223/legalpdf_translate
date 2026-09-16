from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json

import pytest

from legalpdf_translate.budget_reservations import BudgetError, ReservationBudget


def ledger(tmp_path, cap="1"):
    return ReservationBudget(tmp_path / "budget.json", cap_usd=cap, identity={"run": "fixture"})


def test_reserve_is_durable_before_reconcile_and_duplicates_fail(tmp_path):
    budget = ledger(tmp_path)
    budget.reserve("first", "0.6", {"purpose": "translation"})
    assert budget.status()["held_usd"] == "0.6"
    with pytest.raises(BudgetError, match="Duplicate"):
        budget.reserve("first", "0.1", {})
    budget.finalize("first", "0.2", {"response_id": "fixture"})
    assert Decimal(budget.status()["remaining_usd"]) == Decimal("0.8")
    with pytest.raises(BudgetError, match="unfinalized"):
        budget.finalize("first", "0", {})


def test_parallel_reservations_cannot_overcommit(tmp_path):
    budget = ledger(tmp_path)
    def reserve(index):
        try:
            budget.reserve(f"call-{index}", "0.3", {})
            return True
        except BudgetError:
            return False
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(reserve, range(12)))
    assert sum(results) == 3
    assert Decimal(budget.status()["held_usd"]) == Decimal("0.9")


@pytest.mark.parametrize("actual", [None, "0.6000000000001", "12"])
def test_unknown_or_overage_retains_full_hold_and_blocks(tmp_path, actual):
    budget = ledger(tmp_path)
    budget.reserve("first", "0.6", {})
    budget.finalize("first", actual, {})
    assert budget.blocked
    assert Decimal(budget.status()["held_usd"]) == Decimal("0.6")
    assert Decimal(budget.status()["remaining_usd"]) == 0
    with pytest.raises(BudgetError, match="Uncertain"):
        budget.reserve("next", "0.1", {})
    with pytest.raises(BudgetError, match="unfinalized"):
        budget.finalize("first", "0", {})


def test_reopen_after_crash_cannot_release_or_reuse_inflight_reservation(tmp_path):
    first = ledger(tmp_path)
    first.reserve("dispatched", "0.7", {})
    recovered = ledger(tmp_path)
    assert recovered.blocked
    assert Decimal(recovered.status()["held_usd"]) == Decimal("0.7")
    with pytest.raises(BudgetError):
        recovered.reserve("retry", "0.1", {})
    with pytest.raises(BudgetError):
        recovered.finalize("dispatched", "0", {})


def test_finalized_history_is_kept_on_reopen_and_cap_is_immutable(tmp_path):
    first = ledger(tmp_path)
    first.reserve("first", "0.7", {})
    first.finalize("first", "0.4", {})
    before = first.path.read_bytes()
    reopened = ledger(tmp_path)
    assert reopened.path.read_bytes() == before
    assert Decimal(reopened.status()["known_spend_usd"]) == Decimal("0.4")
    with pytest.raises(BudgetError, match="integrity"):
        ledger(tmp_path, "2")
    assert reopened.path.read_bytes() == before


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-0.1", True, None])
def test_invalid_money_never_authorizes_a_call(tmp_path, value):
    budget = ledger(tmp_path)
    with pytest.raises(BudgetError):
        budget.reserve("first", value, {})
    assert budget.status()["attempts"] == 0


def test_corrupt_ledger_cannot_be_recreated(tmp_path):
    budget = ledger(tmp_path)
    state = json.loads(budget.path.read_text(encoding="utf-8"))
    state["cap_usd"] = "100"
    budget.path.write_text(json.dumps(state), encoding="utf-8")
    before = budget.path.read_bytes()
    with pytest.raises(BudgetError, match="integrity"):
        ledger(tmp_path)
    assert budget.path.read_bytes() == before


def test_missing_existing_ledger_and_zero_cap_fail_closed(tmp_path):
    with pytest.raises(BudgetError, match="Existing"):
        ReservationBudget(tmp_path / "missing.json", cap_usd="1", identity={}, create=False)
    budget = ledger(tmp_path, "0")
    with pytest.raises(BudgetError, match="Insufficient"):
        budget.reserve("first", "0.001", {})
