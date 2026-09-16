"""Cooperative audit policy for an explicitly scoped acceptance operation.

Interpreter, startup and installed native dependencies remain trusted. This is
not hostile-code confinement and does not change a historical private guard.
"""
from __future__ import annotations

import os
from pathlib import Path

from tooling.run_isolated_acceptance_tests import OfflineBoundary


class AcceptanceRuntimeBoundary(OfflineBoundary):
    def __init__(self, *, read_roots, read_files, write_root, ledger):
        super().__init__(read_roots=read_roots, write_root=write_root)
        self.ledger = Path(ledger).resolve()
        self.ledger_lock = self.ledger.with_suffix(self.ledger.suffix + ".lock")
        self.read_files = {Path(path).resolve() for path in read_files} | {self.ledger}
        self.owned_temps: set[Path] = set()
        self.allowed_connections: set[tuple[str, int]] = set()
        self.last_event = None

    def _path(self, value, *, write=False, allow_null=False):
        if isinstance(value, (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(value)).resolve()
            if path in self.owned_temps or not write and path in self.read_files:
                return
        super()._path(value, write=write, allow_null=allow_null)

    def check(self, event, args):
        self.last_event = event
        if event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
            mode = args[1] if len(args) > 1 else None
            if path == self.ledger_lock and not flags & os.O_TRUNC:
                return
            # CPython NamedTemporaryFile uses io.open(dir, 'w', opener=...);
            # only its opener creates the actual exclusive child. A normal
            # OS file-open cannot truncate an existing directory. We trust
            # this stdlib behavior; no arbitrary directory/file is allowed.
            if (path == self.ledger.parent and path.is_dir() and mode == "w"
                    and flags & os.O_CREAT and flags & os.O_TRUNC):
                return
            if (path.parent == self.ledger.parent and path.name.startswith(".accounting-")
                    and path.suffix == ".tmp" and flags & os.O_EXCL and flags & os.O_CREAT
                    and not path.exists()):
                self.owned_temps.add(path)
        if event == "os.rename":
            self._no_dir_fd(args[2:])
            if Path(args[0]).resolve() in self.owned_temps and Path(args[1]).resolve() == self.ledger:
                return
        if event == "os.mkdir" and Path(args[0]).resolve() == self.ledger.parent and self.ledger.parent.is_dir():
            self._no_dir_fd(args[2:])
            return
        if event == "socket.getaddrinfo":
            host = args[0].decode() if isinstance(args[0], bytes) else args[0]
            if host == "api.openai.com" and args[1] == 443:
                return
        if event == "socket.connect" and args[1][:2] in self.allowed_connections:
            return
        super().check(event, args)
