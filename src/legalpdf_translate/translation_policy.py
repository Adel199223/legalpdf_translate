"""Internal fresh-run policy and read-only rollout checks.

Saved checkpoints own their protocol. This default remains legacy until the
separate real-document acceptance and activation stages have passed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path

DEFAULT_TRANSLATION_PROTOCOL = "legacy_text_v1"
SUPPORTED_TRANSLATION_PROTOCOLS = frozenset({"legacy_text_v1", "legal_blocks_v2"})


def resolve_translation_protocol(
    explicit: str | None = None, *, environment: Mapping[str, str] | None = None
) -> str:
    values = os.environ if environment is None else environment
    selected = explicit if explicit is not None else values.get(
        "LEGALPDF_TRANSLATION_PROTOCOL", DEFAULT_TRANSLATION_PROTOCOL
    )
    if selected not in SUPPORTED_TRANSLATION_PROTOCOLS:
        raise ValueError("Unsupported internal translation protocol.")
    return selected


def require_inactive_queues(checkpoint_paths: Iterable[Path]) -> None:
    """Reject rollout/rollback while any inspected queue has unfinished work.

    The operator must supply all known queue checkpoints. This function neither
    changes the queue schema nor claims to discover every queue on the machine.
    """
    for path in checkpoint_paths:
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            jobs = state["jobs"]
            if not isinstance(jobs, list):
                raise ValueError
            for job in jobs:
                if not isinstance(job, dict) or job.get("status") not in {"done", "failed", "skipped"}:
                    raise ValueError
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise ValueError("Protocol rollout requires verified inactive queues with no pending jobs.") from exc
