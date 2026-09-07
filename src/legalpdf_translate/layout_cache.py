"""Opt-in local layout JSON cache; no extraction, OCR, usage or provider code."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any

_KEY = re.compile(r"[0-9a-f]{64}\Z")
_MAX_BYTES = 16_000_000
_WRITE_LOCK = threading.Lock()


def _encoded(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


class LayoutCache:
    """Disabled reads and writes touch no cache directory; callers own consent."""

    def __init__(self, root: Path, *, enabled: bool = False):
        self.root = Path(root)
        self.enabled = bool(enabled)

    def _path(self, key: str) -> Path:
        if not isinstance(key, str) or not _KEY.fullmatch(key):
            raise ValueError("Invalid layout cache key")
        return self.root / f"{key}.json"

    def get(self, key: str) -> dict | None:
        if not self.enabled:
            return None
        path = self._path(key)
        try:
            if path.stat().st_size > _MAX_BYTES:
                return None
            record = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("version") != 1 or record.get("key") != key:
                return None
            payload = record.get("payload")
            if (not isinstance(payload, dict) or set(payload) != {"layout"}
                    or not isinstance(payload["layout"], dict)
                    or record.get("payload_sha256") != hashlib.sha256(_encoded(payload)).hexdigest()):
                return None
            return payload
        except (OSError, ValueError, TypeError, OverflowError):
            return None

    def set(self, key: str, payload: dict) -> None:
        if not self.enabled:
            return
        path = self._path(key)
        if not isinstance(payload, dict) or set(payload) != {"layout"} or not isinstance(payload["layout"], dict):
            raise ValueError("Only layout evidence belongs in this cache")
        encoded = _encoded({"version": 1, "key": key, "payload": payload,
                            "payload_sha256": hashlib.sha256(_encoded(payload)).hexdigest()})
        if len(encoded) > _MAX_BYTES:
            raise ValueError("Layout cache record exceeds the local bound")
        self.root.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".layout-", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            # Windows replace can reject simultaneous writers to one pathname.
            # Serialize this process; other-process contention is an optional
            # cache miss, never grounds to retry extraction or a provider call.
            with _WRITE_LOCK:
                try:
                    os.replace(temporary, path)
                except PermissionError:
                    pass
        finally:
            Path(temporary).unlink(missing_ok=True)
