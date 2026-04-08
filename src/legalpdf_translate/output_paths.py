"""Deterministic output path and outdir preflight helpers."""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .types import TargetLang

RUN_STARTED_AT_FORMAT = "%Y%m%d_%H%M%S"
_RUN_STARTED_AT_RE = re.compile(r"^\d{8}_\d{6}$")
_SAFE_SCOPE_TOKEN_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True, frozen=True)
class OutputPaths:
    frozen_outdir: Path
    run_started_at: str
    run_dir: Path
    pages_dir: Path
    images_dir: Path
    run_state_path: Path
    final_docx_path: Path
    partial_docx_path: Path


def _normalize_scope_token(value: object, *, max_len: int) -> str:
    cleaned = _SAFE_SCOPE_TOKEN_RE.sub("-", str(value or "").strip().lower()).strip("-")
    if cleaned == "":
        return "scope"
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[-max_len:]


def _gmail_run_dir_name(
    *,
    pdf_path: Path,
    lang: TargetLang,
    gmail_batch_context: Mapping[str, Any] | None,
) -> str | None:
    if not isinstance(gmail_batch_context, Mapping):
        return None
    source = str(gmail_batch_context.get("source", "") or "").strip().lower()
    session_id = str(gmail_batch_context.get("session_id", "") or "").strip()
    attachment_id = str(gmail_batch_context.get("attachment_id", "") or "").strip()
    try:
        selected_start_page = int(gmail_batch_context.get("selected_start_page", 0) or 0)
    except (TypeError, ValueError):
        selected_start_page = 0
    if source not in {"", "gmail_intake"}:
        return None
    if session_id == "" or attachment_id == "" or selected_start_page <= 0:
        return None
    scope_hash = hashlib.sha1(
        "\n".join((session_id, attachment_id, str(selected_start_page), lang.value)).encode("utf-8")
    ).hexdigest()[:12]
    session_token = _normalize_scope_token(session_id, max_len=12)
    return f"{pdf_path.stem}_{lang.value}_gmail_{session_token}_p{selected_start_page}_{scope_hash}_run"


def timestamp_for_run_start(now: datetime | None = None) -> str:
    stamp = now or datetime.now()
    return stamp.strftime(RUN_STARTED_AT_FORMAT)


def normalize_run_started_at(value: str) -> str:
    cleaned = value.strip()
    if not _RUN_STARTED_AT_RE.fullmatch(cleaned):
        raise ValueError(
            f"run_started_at must match YYYYMMDD_HHMMSS, got: {value!r}"
        )
    return cleaned


def build_output_paths(
    output_dir: Path,
    pdf_path: Path,
    lang: TargetLang,
    *,
    run_started_at: str | None = None,
    gmail_batch_context: Mapping[str, Any] | None = None,
) -> OutputPaths:
    outdir_abs = output_dir.expanduser().resolve()
    started_at = (
        normalize_run_started_at(run_started_at)
        if run_started_at is not None
        else timestamp_for_run_start()
    )
    run_dir_name = _gmail_run_dir_name(
        pdf_path=pdf_path,
        lang=lang,
        gmail_batch_context=gmail_batch_context,
    ) or f"{pdf_path.stem}_{lang.value}_run"
    run_dir = outdir_abs / run_dir_name
    final_docx = outdir_abs / f"{pdf_path.stem}_{lang.value}_{started_at}.docx"
    partial_docx = outdir_abs / f"{pdf_path.stem}_{lang.value}_{started_at}_PARTIAL.docx"
    return OutputPaths(
        frozen_outdir=outdir_abs,
        run_started_at=started_at,
        run_dir=run_dir,
        pages_dir=run_dir / "pages",
        images_dir=run_dir / "images",
        run_state_path=run_dir / "run_state.json",
        final_docx_path=final_docx,
        partial_docx_path=partial_docx,
    )


def _write_probe_file(path: Path) -> None:
    with path.open("wb") as handle:
        handle.write(b"ok")
        handle.flush()
        os.fsync(handle.fileno())


def require_writable_output_dir_text(outdir_text: str) -> Path:
    if outdir_text.strip() == "":
        raise ValueError("Output folder is required.")
    return require_writable_output_dir(Path(outdir_text))


def require_writable_output_dir(output_dir: Path) -> Path:
    output_text = str(output_dir).strip()
    if output_text == "":
        raise ValueError("Output folder is required.")

    outdir_abs = output_dir.expanduser().resolve()
    if not outdir_abs.exists():
        raise ValueError(f"Output folder does not exist: {outdir_abs}")
    if not outdir_abs.is_dir():
        raise ValueError(f"Output folder is not a directory: {outdir_abs}")

    probe_path = outdir_abs / ".write_test.tmp"
    try:
        _write_probe_file(probe_path)
    except OSError as exc:
        if probe_path.exists():
            try:
                probe_path.unlink()
            except OSError:
                pass
        raise ValueError(f"Output folder is not writable: {outdir_abs}") from exc

    try:
        probe_path.unlink(missing_ok=True)
    except OSError as exc:
        raise ValueError(
            f"Output folder preflight cleanup failed: {outdir_abs}"
        ) from exc

    return outdir_abs
