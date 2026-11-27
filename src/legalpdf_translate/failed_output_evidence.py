"""Opt-in private failed-response evidence; never emitted to application logs.

Only run-owned intermediate evidence is written. Each body is capped at 32 KiB
UTF-8, each literal delta at 32 hashed rows, each file at 512 KiB, and each page
attempt at eight retained failures across Resume. Existing evidence is never
replaced. These are packaging deltas, not proof of changed semantic content.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from .arabic_pre_tokenize import extract_locked_tokens

_BODY_BYTES = 32 * 1024
_FILE_BYTES = 512 * 1024
_SLOTS = 8


def _body(text):
    encoded = (text or "").encode("utf-8")
    return {"text": encoded[:_BODY_BYTES].decode("utf-8", errors="ignore"),
            "sha256": hashlib.sha256(encoded).hexdigest(), "bytes": len(encoded),
            "truncated": len(encoded) > _BODY_BYTES}


def _delta(before, after):
    missing, added = Counter(before) - Counter(after), Counter(after) - Counter(before)
    def rows(values):
        return [{"sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
                 "bytes": len(value.encode("utf-8")), "count": count}
                for value, count in sorted(values.items())[:32]]
    return {"missing_occurrences": sum(missing.values()), "added_occurrences": sum(added.values()),
            "missing_hashed_samples": rows(missing), "added_hashed_samples": rows(added),
            "samples_truncated": len(missing) > 32 or len(added) > 32}


def retain_failed_output(run_dir: Path, *, keep_intermediates: bool, page: int,
                         attempt: int, raw_output: str, evaluation,
                         expected_tokens=None, primary_normalized_text=None):
    """Best-effort diagnostic only; do not alter evaluation or Resume state."""
    if not keep_intermediates or evaluation.ok or type(page) is not int or page < 1 or attempt not in {1, 2}:
        return None
    normalized = evaluation.normalized_text or ""
    observed = extract_locked_tokens(normalized)
    kind = evaluation.ar_violation_kind or ""
    payload = {"version": 1, "page": page, "attempt": attempt,
               "violation_kind": kind if re.fullmatch(r"[a-z_]{0,80}", kind) else "",
               "raw_output": _body(raw_output), "normalized_output": _body(normalized),
               "expected_token_packaging_delta": _delta(expected_tokens or [], observed)}
    if primary_normalized_text is not None:
        payload["primary_token_packaging_delta"] = _delta(extract_locked_tokens(primary_normalized_text), observed)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    if len(encoded) > _FILE_BYTES:
        return None
    try:
        root = Path(run_dir).resolve(strict=True)
        directory = root / "failed_output_evidence"
        directory.mkdir(exist_ok=True)
        if directory.is_symlink() or not directory.resolve(strict=True).is_relative_to(root):
            return None
        for slot in range(1, _SLOTS + 1):
            path = directory / f"page_{page:04d}_attempt_{attempt}_failure_{slot:02d}.json"
            try:
                with path.open("xb") as stream:
                    stream.write(encoded)
                return path
            except FileExistsError:
                continue
    except OSError:
        return None
    return None
