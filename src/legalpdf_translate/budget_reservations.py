"""Crash-safe reservations for an explicitly configured product-run hard cap.

Acceptance uses its original ledger adapter; this module never discovers or
creates an acceptance allowance. Uncertain dispatches cannot release money.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Iterator, Mapping
import uuid


class BudgetError(ValueError):
    """No dispatch may follow a budget validation or persistence failure."""


def money(value: Any) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise BudgetError("A finite nonnegative monetary value is required.")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise BudgetError("A finite nonnegative monetary value is required.") from exc
    if not number.is_finite() or number < 0:
        raise BudgetError("A finite nonnegative monetary value is required.")
    return number


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                prefix=".accounting-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            descriptor = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


@contextmanager
def locked(path: Path) -> Iterator[None]:
    """Thread and OS process exclusion; the permanent lock file is never removed."""
    key = os.path.normcase(str(path.resolve()))
    with _LOCKS_GUARD:
        local = _LOCKS.setdefault(key, threading.RLock())
    with local:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a+b") as handle:
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            except OSError as exc:
                raise BudgetError("Budget is in use; no dispatch was authorized.") from exc
            try:
                yield
            finally:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class ReservationBudget:
    hard = True

    def __init__(self, path: Path, *, cap_usd: Any, identity: Mapping[str, Any], create: bool = True):
        self.path = Path(path).resolve()
        self.lock_path = self.path.with_suffix(self.path.suffix + ".lock")
        self.cap_usd = money(cap_usd)
        self.identity = json.loads(json.dumps(dict(identity), allow_nan=False))
        self._owner = uuid.uuid4().hex
        with locked(self.lock_path):
            if self.path.exists():
                self._load()
            elif not create:
                raise BudgetError("Existing budget ledger is required.")
            else:
                self._save({"version": 1, "cap_usd": str(self.cap_usd), "identity": self.identity,
                    "reservations": {}, "blocked_reason": None})

    def _save(self, state):
        payload = deepcopy(state)
        payload.pop("fingerprint", None)
        payload["fingerprint"] = fingerprint(payload)
        atomic_json(self.path, payload)

    def _load(self):
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            digest = state.pop("fingerprint")
            if (digest != fingerprint(state) or state["version"] != 1
                    or state["identity"] != self.identity or money(state["cap_usd"]) != self.cap_usd
                    or not isinstance(state["reservations"], dict)):
                raise ValueError
            for identifier, row in state["reservations"].items():
                if not isinstance(identifier, str) or not identifier or not isinstance(row, dict):
                    raise ValueError
                ceiling = money(row["reserved_usd"])
                if row["status"] not in {"reserved", "uncertain", "finalized"}:
                    raise ValueError
                if row["status"] == "finalized":
                    if money(row["actual_usd"]) > ceiling:
                        raise ValueError
                elif row["actual_usd"] is not None:
                    raise ValueError
            if self._committed(state) > self.cap_usd:
                raise ValueError
            return state
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise BudgetError("Budget identity, cap or integrity changed; preserve the ledger.") from exc

    @staticmethod
    def _committed(state):
        return sum((money(row["actual_usd"] if row["status"] == "finalized" else row["reserved_usd"])
            for row in state["reservations"].values()), Decimal(0))

    def _blocked(self, state):
        return bool(state.get("blocked_reason")) or any(
            row["status"] == "uncertain" or (row["status"] == "reserved" and row.get("owner") != self._owner)
            for row in state["reservations"].values())

    @property
    def blocked(self):
        with locked(self.lock_path):
            return self._blocked(self._load())

    @property
    def has_uncertain(self):
        return self.blocked

    def status(self):
        with locked(self.lock_path):
            state = self._load()
            known = sum((money(row["actual_usd"]) for row in state["reservations"].values()
                if row["status"] == "finalized"), Decimal(0))
            held = self._committed(state) - known
            blocked = self._blocked(state)
            return {"cap_usd": str(self.cap_usd), "known_spend_usd": str(known), "held_usd": str(held),
                "remaining_usd": str(Decimal(0) if blocked else self.cap_usd-known-held),
                "attempts": len(state["reservations"]), "blocked": blocked,
                "blocked_reason": state.get("blocked_reason") or ("unresolved_dispatch" if blocked else None)}

    def reserve(self, reservation_id: str, ceiling_usd: Any, metadata: Mapping[str, Any]):
        ceiling = money(ceiling_usd)
        if not isinstance(reservation_id, str) or not reservation_id or len(reservation_id) > 200:
            raise BudgetError("A bounded unique reservation identity is required.")
        details = json.loads(json.dumps(dict(metadata), allow_nan=False))
        with locked(self.lock_path):
            state = self._load()
            if self._blocked(state):
                raise BudgetError("Uncertain billing blocks further dispatches.")
            if reservation_id in state["reservations"]:
                raise BudgetError("Duplicate reservation cannot authorize another dispatch.")
            if self._committed(state) + ceiling > self.cap_usd:
                raise BudgetError("Insufficient budget for the worst-case dispatch.")
            row = {"reserved_usd": str(ceiling), "actual_usd": None, "status": "reserved",
                "owner": self._owner, "created_at": datetime.now(UTC).isoformat(), "metadata": details}
            state["reservations"][reservation_id] = row
            self._save(state)
            return {"reservation_id": reservation_id, **deepcopy(row)}

    def finalize(self, reservation_id: str, actual_usd: Any, metadata: Mapping[str, Any], block_reason=None):
        actual = None if actual_usd is None else money(actual_usd)
        details = json.loads(json.dumps(dict(metadata), allow_nan=False))
        with locked(self.lock_path):
            state = self._load()
            row = state["reservations"].get(reservation_id)
            if row is None or row["status"] != "reserved" or row.get("owner") != self._owner:
                raise BudgetError("Only this execution's unfinalized reservation can be reconciled.")
            row["evidence"] = details
            if actual is not None and actual > money(row["reserved_usd"]):
                row["observed_overage_usd"] = str(actual)
                block_reason = "reservation_ceiling_exceeded"
            if block_reason or actual is None:
                row["status"] = "uncertain"
                state["blocked_reason"] = block_reason or "unknown_provider_cost"
            else:
                row.update(status="finalized", actual_usd=str(actual), finalized_at=datetime.now(UTC).isoformat())
            self._save(state)
            return {"reservation_id": reservation_id, **deepcopy(row), "blocked_reason": state["blocked_reason"]}
