"""Real stdlib atomic-writer path, fictional ledgers and no provider contact."""
import json
import os
from pathlib import Path
import sys

import pytest

from legalpdf_translate.budget_reservations import atomic_json
from tooling.acceptance_runtime_boundary import AcceptanceRuntimeBoundary
from tooling.run_isolated_acceptance_tests import OfflineBoundaryDenied


@pytest.fixture
def boundary(tmp_path):
    outside = tmp_path / "fictional-ledger"
    outside.mkdir()
    ledger = outside / "budget-ledger.json"
    ledger.write_text('{"original": true}', encoding="utf-8")
    owned = tmp_path / "new-operation"
    owned.mkdir()
    return AcceptanceRuntimeBoundary(read_roots=(), read_files=(), write_root=owned, ledger=ledger)


def test_real_atomic_writer_accepts_only_owned_temp_to_ledger_replacement(boundary):
    # Hooks cannot be removed; turn this local synthetic check off in finally.
    # Its closure is passive for every later test, including any cleanup.
    active = [True]
    events = []
    def hook(event, args):
        if active[0]:
            if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
                events.append((str(args[0]), args[1]))
            boundary.check(event, args)
    sys.addaudithook(hook)
    try:
        atomic_json(boundary.ledger, {"original": True, "synthetic_append": 1})
    finally:
        active[0] = False
    assert json.loads(boundary.ledger.read_bytes())["synthetic_append"] == 1
    assert (str(boundary.ledger.parent), "w") in events
    assert len(boundary.owned_temps) == 1 and not boundary.denials
    assert not next(iter(boundary.owned_temps)).exists()


@pytest.mark.parametrize("event", ["os.remove", "os.rmdir", "os.chmod", "os.truncate"])
def test_ledger_and_parent_cannot_be_deleted_or_mutated_directly(boundary, event):
    for path in (boundary.ledger, boundary.ledger.parent, boundary.ledger_lock):
        with pytest.raises(OfflineBoundaryDenied):
            boundary.check(event, (str(path),))


def test_direct_ledger_and_arbitrary_sibling_writes_are_denied(boundary):
    for path in (boundary.ledger, boundary.ledger.parent / "unrelated.json"):
        with pytest.raises(OfflineBoundaryDenied):
            boundary.check("open", (str(path), "w", os.O_CREAT | os.O_TRUNC | os.O_WRONLY))


def test_existing_temp_is_not_adopted_and_only_exclusive_creation_is_owned(boundary):
    existing = boundary.ledger.parent / ".accounting-existing.tmp"
    existing.write_text("user owned", encoding="utf-8")
    for flags in (os.O_CREAT | os.O_EXCL | os.O_WRONLY, os.O_CREAT | os.O_WRONLY):
        with pytest.raises(OfflineBoundaryDenied):
            boundary.check("open", (str(existing), "w", flags))
    assert not boundary.owned_temps


def test_only_owned_temp_can_replace_exact_ledger(boundary):
    temp = boundary.ledger.parent / ".accounting-new.tmp"
    boundary.check("open", (str(temp), "w", os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    boundary.check("os.rename", (str(temp), str(boundary.ledger), -1, -1))
    for source, dest in ((boundary.ledger, temp), (temp, boundary.ledger.parent / "other.json"),
                         (boundary.ledger.parent / ".accounting-unowned.tmp", boundary.ledger)):
        with pytest.raises(OfflineBoundaryDenied):
            boundary.check("os.rename", (str(source), str(dest), -1, -1))


def test_parent_open_exception_does_not_apply_to_other_paths_or_modes(boundary):
    for path, mode, flags in ((boundary.ledger.parent, "r", os.O_RDONLY),
                              (boundary.ledger.parent.parent, "w", os.O_CREAT | os.O_TRUNC)):
        with pytest.raises(OfflineBoundaryDenied):
            boundary.check("open", (str(path), mode, flags))


def test_network_connections_require_explicit_provider_dns_result(boundary):
    boundary.check("socket.getaddrinfo", ("api.openai.com", 443))
    for host, port in (("other.invalid", 443), ("api.openai.com", 80)):
        with pytest.raises(OfflineBoundaryDenied):
            boundary.check("socket.getaddrinfo", (host, port))
    with pytest.raises(OfflineBoundaryDenied):
        boundary.check("socket.connect", (None, ("192.0.2.1", 443)))
    boundary.allowed_connections.add(("192.0.2.1", 443))
    boundary.check("socket.connect", (None, ("192.0.2.1", 443)))
    with pytest.raises(OfflineBoundaryDenied):
        boundary.check("socket.connect", (None, ("192.0.2.1", 80)))
