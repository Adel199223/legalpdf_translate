"""Run folder layout, hashing, checkpoint persistence, and resume compatibility."""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import CONTEXT_EMPTY_HASH_MARKER, RUN_STATE_VERSION
from .output_paths import OutputPaths, build_output_paths
from .types import ImageMode, PageStatus, ReasoningEffort, RunConfig, RunState, TargetLang

RunPaths = OutputPaths


def build_run_paths(
    output_dir: Path,
    pdf_path: Path,
    lang: TargetLang,
    *,
    run_started_at: str | None = None,
) -> RunPaths:
    return build_output_paths(
        output_dir=output_dir,
        pdf_path=pdf_path,
        lang=lang,
        run_started_at=run_started_at,
    )


def ensure_run_dirs(paths: RunPaths) -> None:
    paths.run_dir.mkdir(parents=True, exist_ok=True)
    paths.pages_dir.mkdir(parents=True, exist_ok=True)
    paths.images_dir.mkdir(parents=True, exist_ok=True)


def clear_run_dirs(paths: RunPaths) -> None:
    if paths.pages_dir.exists():
        shutil.rmtree(paths.pages_dir)
    if paths.images_dir.exists():
        shutil.rmtree(paths.images_dir)
    if paths.run_state_path.exists():
        paths.run_state_path.unlink()
    ensure_run_dirs(paths)


def sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_of_text(value: str | None) -> str:
    if not value:
        return CONTEXT_EMPTY_HASH_MARKER
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_of_bytes(value: bytes | None) -> str:
    if not value:
        return CONTEXT_EMPTY_HASH_MARKER
    return hashlib.sha256(value).hexdigest()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def settings_fingerprint(config: RunConfig) -> dict[str, Any]:
    return {
        "effort": config.effort.value,
        "image_mode": config.image_mode.value,
        "page_breaks": config.page_breaks,
        "keep_intermediates": config.keep_intermediates,
        "start_page": config.start_page,
        "end_page": config.end_page,
        "max_pages": config.max_pages,
    }


def new_run_state(
    *,
    config: RunConfig,
    paths: RunPaths,
    pdf_fingerprint: str,
    context_hash: str,
    total_pages: int,
    selected_pages: list[int],
) -> RunState:
    if not selected_pages:
        raise ValueError("selected_pages cannot be empty.")

    selection_start_page = selected_pages[0]
    selection_end_page = selected_pages[-1]
    selection_page_count = len(selected_pages)

    now = _utc_now()
    pages = {
        str(page_num): {
            "status": PageStatus.PENDING.value,
            "image_used": False,
            "retry_used": False,
            "usage": {},
            "error": None,
        }
        for page_num in selected_pages
    }
    return RunState(
        version=RUN_STATE_VERSION,
        pdf_path=str(config.pdf_path),
        pdf_fingerprint=pdf_fingerprint,
        lang=config.target_lang.value,
        total_pages=total_pages,
        max_pages_effective=selection_page_count,
        selection_start_page=selection_start_page,
        selection_end_page=selection_end_page,
        selection_page_count=selection_page_count,
        settings=settings_fingerprint(config),
        context_hash=context_hash,
        created_at=now,
        updated_at=now,
        frozen_outdir_abs=str(paths.frozen_outdir),
        run_dir_abs=str(paths.run_dir),
        final_docx_path_abs=None,
        run_started_at=paths.run_started_at,
        pages=pages,
        last_completed_page=0,
    )


def load_run_state(path: Path) -> RunState | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    final_docx_raw = data.get("final_docx_path_abs")
    final_docx: str | None
    if final_docx_raw in (None, ""):
        final_docx = None
    else:
        final_docx = str(final_docx_raw)

    pages = dict(data["pages"])
    page_numbers: list[int] = []
    for key in pages.keys():
        try:
            page_numbers.append(int(key))
        except ValueError:
            continue
    page_numbers = sorted(page_numbers)
    fallback_selection_start = page_numbers[0] if page_numbers else 1
    fallback_selection_end = page_numbers[-1] if page_numbers else int(data.get("max_pages_effective", 0))
    fallback_selection_count = len(page_numbers)

    return RunState(
        version=int(data["version"]),
        pdf_path=str(data["pdf_path"]),
        pdf_fingerprint=str(data["pdf_fingerprint"]),
        lang=str(data["lang"]),
        total_pages=int(data["total_pages"]),
        max_pages_effective=int(data["max_pages_effective"]),
        selection_start_page=int(data.get("selection_start_page", fallback_selection_start)),
        selection_end_page=int(data.get("selection_end_page", fallback_selection_end)),
        selection_page_count=int(data.get("selection_page_count", fallback_selection_count)),
        settings=dict(data["settings"]),
        context_hash=str(data["context_hash"]),
        created_at=str(data["created_at"]),
        updated_at=str(data["updated_at"]),
        frozen_outdir_abs=str(data.get("frozen_outdir_abs", path.parent.parent.resolve())),
        run_dir_abs=str(data.get("run_dir_abs", path.parent.resolve())),
        final_docx_path_abs=final_docx,
        run_started_at=str(data.get("run_started_at", "")),
        pages=pages,
        last_completed_page=int(data.get("last_completed_page", 0)),
    )


def save_run_state_atomic(path: Path, state: RunState) -> None:
    state.updated_at = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def resume_incompatibility_reason(
    state: RunState,
    *,
    config: RunConfig,
    paths: RunPaths,
    pdf_fingerprint: str,
    context_hash: str,
    selection_start_page: int,
    selection_end_page: int,
    selection_page_count: int,
    max_pages_effective: int,
) -> str | None:
    if state.version != RUN_STATE_VERSION:
        return f"state version mismatch: checkpoint={state.version}, expected={RUN_STATE_VERSION}"
    if state.pdf_fingerprint != pdf_fingerprint:
        return "PDF fingerprint mismatch."
    if state.lang != config.target_lang.value:
        return f"target language mismatch: checkpoint={state.lang}, expected={config.target_lang.value}"
    if state.context_hash != context_hash:
        return "context mismatch."
    expected_settings = settings_fingerprint(config)
    if state.settings != expected_settings:
        return (
            "settings mismatch: checkpoint="
            f"{state.settings}, expected={expected_settings}"
        )

    if state.selection_start_page != selection_start_page:
        return (
            "selection start page mismatch: checkpoint="
            f"{state.selection_start_page}, expected={selection_start_page}"
        )
    if state.selection_end_page != selection_end_page:
        return (
            "selection end page mismatch: checkpoint="
            f"{state.selection_end_page}, expected={selection_end_page}"
        )
    if state.selection_page_count != selection_page_count:
        return (
            "selection page count mismatch: checkpoint="
            f"{state.selection_page_count}, expected={selection_page_count}"
        )
    if state.max_pages_effective != max_pages_effective:
        return (
            "max_pages_effective mismatch: checkpoint="
            f"{state.max_pages_effective}, expected={max_pages_effective}"
        )

    if state.frozen_outdir_abs:
        if Path(state.frozen_outdir_abs).expanduser().resolve() != paths.frozen_outdir:
            return "output folder mismatch."
    if state.run_dir_abs:
        if Path(state.run_dir_abs).expanduser().resolve() != paths.run_dir:
            return "run directory mismatch."
    if state.run_started_at and state.run_started_at != paths.run_started_at:
        return (
            "run timestamp mismatch: checkpoint="
            f"{state.run_started_at}, expected={paths.run_started_at}"
        )
    return None


def is_resume_compatible(
    state: RunState,
    *,
    config: RunConfig,
    paths: RunPaths,
    pdf_fingerprint: str,
    context_hash: str,
    selection_start_page: int,
    selection_end_page: int,
    selection_page_count: int,
    max_pages_effective: int,
) -> bool:
    return (
        resume_incompatibility_reason(
            state,
            config=config,
            paths=paths,
            pdf_fingerprint=pdf_fingerprint,
            context_hash=context_hash,
            selection_start_page=selection_start_page,
            selection_end_page=selection_end_page,
            selection_page_count=selection_page_count,
            max_pages_effective=max_pages_effective,
        )
        is None
    )


def record_final_docx_path(state: RunState, final_docx_path: Path) -> None:
    state.final_docx_path_abs = str(final_docx_path.expanduser().resolve())


def mark_page_done(
    state: RunState,
    page_number: int,
    *,
    image_used: bool,
    retry_used: bool,
    usage: dict[str, Any] | None,
) -> None:
    page_key = str(page_number)
    state.pages[page_key] = {
        "status": PageStatus.DONE.value,
        "image_used": image_used,
        "retry_used": retry_used,
        "usage": usage or {},
        "error": None,
    }
    state.last_completed_page = max(state.last_completed_page, page_number)


def mark_page_failed(
    state: RunState,
    page_number: int,
    *,
    image_used: bool,
    retry_used: bool,
    usage: dict[str, Any] | None,
    error: str,
) -> None:
    state.pages[str(page_number)] = {
        "status": PageStatus.FAILED.value,
        "image_used": image_used,
        "retry_used": retry_used,
        "usage": usage or {},
        "error": error,
    }


def list_completed_pages(state: RunState) -> list[int]:
    pages: list[int] = []
    for key, value in state.pages.items():
        if value.get("status") == PageStatus.DONE.value:
            pages.append(int(key))
    return sorted(pages)


def bool_from_text(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in ("1", "true", "yes", "y", "on"):
        return True
    if lowered in ("0", "false", "no", "n", "off"):
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def parse_effort(value: str) -> ReasoningEffort:
    lowered = value.strip().lower()
    if lowered == ReasoningEffort.HIGH.value:
        return ReasoningEffort.HIGH
    if lowered == ReasoningEffort.XHIGH.value:
        return ReasoningEffort.XHIGH
    raise ValueError("Effort must be high or xhigh.")


def parse_image_mode(value: str) -> ImageMode:
    lowered = value.strip().lower()
    if lowered == ImageMode.OFF.value:
        return ImageMode.OFF
    if lowered == ImageMode.AUTO.value:
        return ImageMode.AUTO
    if lowered == ImageMode.ALWAYS.value:
        return ImageMode.ALWAYS
    raise ValueError("Image mode must be off, auto, or always.")
