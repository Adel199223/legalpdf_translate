from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import os
from types import SimpleNamespace

import pytest

from legalpdf_translate import budget_reservations as reservations
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


@pytest.mark.skipif(os.name != "nt", reason="Windows destination sharing")
@pytest.mark.parametrize("release", [True, False])
def test_open_journal_retries_only_its_fsynced_temporary(tmp_path, monkeypatch, release):
    path = tmp_path / "dispatch_accounting.json"
    old, new = {"calls": ["start"]}, {"calls": ["start", "finish"]}
    reservations.atomic_json(path, old)
    before = path.read_bytes()
    replace, fsync = os.replace, os.fsync
    attempts, flushed = [], []
    with path.open("rb") as reader:
        def observed_replace(src, dest):
            attempts.append((src, dest, src.read_bytes()))
            try:
                return replace(src, dest)
            except PermissionError as exc:
                assert exc.winerror in (5, 32, 33)
                assert path.read_bytes() == before
                if release:
                    reader.close()
                raise
        def observed_fsync(fd):
            flushed.append(fd)
            return fsync(fd)
        monkeypatch.setattr(reservations.os, "replace", observed_replace)
        monkeypatch.setattr(reservations.os, "fsync", observed_fsync)
        if release:
            reservations.atomic_json(path, new)
            assert json.loads(path.read_bytes()) == new
            assert len(attempts) == 2
        else:
            with pytest.raises(PermissionError):
                reservations.atomic_json(path, new)
            assert path.read_bytes() == before
            assert len(attempts) == 7
    assert len(set(attempts)) == 1 and len(flushed) == 1
    assert not list(tmp_path.glob(".accounting-*.tmp"))


@pytest.mark.parametrize("platform,code,attempts", [
    ("nt", 5, 2), ("nt", 32, 2), ("nt", 33, 2),
    ("nt", 2, 1), ("nt", 112, 1), ("nt", None, 1), ("posix", 32, 1),
])
def test_other_errors_and_platforms_do_not_retry_replace(tmp_path, monkeypatch, platform, code, attempts):
    path = tmp_path / "budget.json"
    reservations.atomic_json(path, {"before": True})
    before = path.read_bytes()
    seen = []
    def replace(src, dest):
        seen.append((src, dest))
        if len(seen) == 1:
            error = PermissionError("injected final publish failure")
            error.winerror = code
            raise error
        os.replace(src, dest)
    monkeypatch.setattr(reservations, "os", SimpleNamespace(name=platform, fsync=os.fsync, replace=replace))
    if attempts == 1:
        with pytest.raises(PermissionError):
            reservations.atomic_json(path, {"after": True})
        assert path.read_bytes() == before
    else:
        reservations.atomic_json(path, {"after": True})
        assert json.loads(path.read_bytes()) == {"after": True}
    assert len(seen) == attempts and len(set(seen)) == 1
    assert not list(tmp_path.glob(".accounting-*.tmp"))


@pytest.mark.parametrize("failure", ["serialization", "fsync"])
def test_failed_staging_does_not_publish_or_retry(tmp_path, monkeypatch, failure):
    path = tmp_path / "budget.json"
    reservations.atomic_json(path, {"before": True})
    before = path.read_bytes()
    def no_publish(*_args):
        pytest.fail("a staged failure must never reach replace")
    monkeypatch.setattr(reservations.os, "replace", no_publish)
    payload = {"after": True}
    if failure == "serialization":
        payload["nonfinite"] = float("nan")
        error = ValueError
    else:
        def fail_fsync(_fd):
            exc = OSError("simulated flush failure")
            exc.winerror = 32
            raise exc
        monkeypatch.setattr(reservations.os, "fsync", fail_fsync)
        error = OSError
    with pytest.raises(error):
        reservations.atomic_json(path, payload)
    assert path.read_bytes() == before and not list(tmp_path.glob(".accounting-*.tmp"))
