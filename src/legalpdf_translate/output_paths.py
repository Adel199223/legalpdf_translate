"""Deterministic output path and outdir preflight helpers."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .types import TargetLang

RUN_STARTED_AT_FORMAT = "%Y%m%d_%H%M%S"
_RUN_STARTED_AT_RE = re.compile(r"^\d{8}_\d{6}$")


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
) -> OutputPaths:
    outdir_abs = output_dir.expanduser().resolve()
    started_at = (
        normalize_run_started_at(run_started_at)
        if run_started_at is not None
        else timestamp_for_run_start()
    )
    run_dir = outdir_abs / f"{pdf_path.stem}_{lang.value}_run"
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
