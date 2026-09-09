"""Run folder layout, hashing, checkpoint persistence, and resume compatibility."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import CONTEXT_EMPTY_HASH_MARKER, RUN_STATE_VERSION
from .output_paths import OutputPaths, build_output_paths
from .types import (
    ApiKeySource,
    EffortPolicy,
    ImageMode,
    OcrEnginePolicy,
    OcrMode,
    PageStatus,
    ReasoningEffort,
    RunConfig,
    RunState,
    TargetLang,
)

RunPaths = OutputPaths


def build_run_paths(
    output_dir: Path,
    pdf_path: Path,
    lang: TargetLang,
    *,
    run_started_at: str | None = None,
    gmail_batch_context: dict[str, Any] | None = None,
) -> RunPaths:
    return build_output_paths(
        output_dir=output_dir,
        pdf_path=pdf_path,
        lang=lang,
        run_started_at=run_started_at,
        gmail_batch_context=gmail_batch_context,
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
        "effort_policy": config.effort_policy.value,
        "allow_xhigh_escalation": bool(config.allow_xhigh_escalation),
        "image_mode": config.image_mode.value,
        "ocr_mode": config.ocr_mode.value,
        "ocr_engine": config.ocr_engine.value,
        "ocr_api_base_url": (config.ocr_api_base_url or "").strip(),
        "ocr_api_model": (config.ocr_api_model or "").strip(),
        "glossary_file_path": str(config.glossary_file.expanduser().resolve()) if config.glossary_file else "",
        "page_breaks": config.page_breaks,
        "keep_intermediates": config.keep_intermediates,
        "strip_bidi_controls": bool(config.strip_bidi_controls),
        "start_page": config.start_page,
        "end_page": config.end_page,
        "max_pages": config.max_pages,
        "workers": config.workers,
    }


def _default_page_record(*, status: str = PageStatus.PENDING.value) -> dict[str, Any]:
    return {
        "status": status,
        "image_used": False,
        "retry_used": False,
        "usage": {},
        "error": None,
        "started_at_iso": "",
        "ended_at_iso": "",
        "wall_seconds": 0.0,
        "attempt1_effort": "",
        "attempt2_effort": "",
        "image_mode": "",
        "image_detail": "",
        "image_bytes": 0,
        "image_width_px": 0,
        "image_height_px": 0,
        "image_format": "",
        "image_compress_steps": 0,
        "extracted_text_chars": 0,
        "extracted_text_lines": 0,
        "extract_seconds": 0.0,
        "ocr_seconds": 0.0,
        "translate_seconds": 0.0,
        "attempt1_seconds": 0.0,
        "attempt2_seconds": 0.0,
        "api_calls_count": 0,
        "backoff_wait_seconds_total": 0.0,
        "source_route": "",
        "source_route_reason": "",
        "image_decision_reason": "",
        "ocr_requested": False,
        "ocr_used": False,
        "ocr_provider_configured": False,
        "ocr_engine_used": "",
        "ocr_failed_reason": "",
        "estimated_cost": None,
        "newline_to_char_ratio": 0.0,
        "ordered_blocks_count": 0,
        "header_blocks_count": 0,
        "footer_blocks_count": 0,
        "barcode_blocks_count": 0,
        "body_blocks_count": 0,
        "two_column_detected": False,
        "compliance_defect_outside_text": False,
        "parser_failed": False,
        "validator_failed": False,
        "retry_reason": "",
        "openai_request_id": "",
        "status_code": None,
        "exception_class": "",
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "transport_retries_count": 0,
        "last_backoff_seconds": 0.0,
        "rate_limit_hit": False,
    }


def _coerce_page_record(raw: Any) -> dict[str, Any]:
    record = _default_page_record()
    if isinstance(raw, dict):
        record.update(raw)
    return record


def new_run_state(
    *,
    config: RunConfig,
    paths: RunPaths,
    pdf_fingerprint: str,
    context_hash: str,
    total_pages: int,
    selected_pages: list[int],
    protocol_identity: dict[str, Any] | None = None,
) -> RunState:
    from .structured_artifacts import normalize_protocol_identity

    identity = normalize_protocol_identity(protocol_identity)
    if not selected_pages:
        raise ValueError("selected_pages cannot be empty.")

    selection_start_page = selected_pages[0]
    selection_end_page = selected_pages[-1]
    selection_page_count = len(selected_pages)

    now = _utc_now()
    selection_count = len(selected_pages)
    pages = {
        str(page_num): _default_page_record(status=PageStatus.PENDING.value)
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
        run_status="running",
        halt_reason=None,
        final_docx_path_abs=None,
        run_started_at=paths.run_started_at,
        finished_at=None,
        pages=pages,
        last_completed_page=0,
        done_count=0,
        failed_count=0,
        pending_count=selection_count,
        failure_context={},
        protocol_identity=identity,
    )


def load_run_state(path: Path) -> RunState | None:
    if not path.exists():
        return None
    try:
        def unique_keys(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate checkpoint key.")
                result[key] = value
            return result

        data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
        return None

    if not isinstance(data, dict):
        return None
    required_keys = {
        "version",
        "pdf_path",
        "pdf_fingerprint",
        "lang",
        "total_pages",
        "max_pages_effective",
        "settings",
        "context_hash",
        "created_at",
        "updated_at",
        "pages",
    }
    if any(key not in data for key in required_keys):
        return None

    try:
        final_docx_raw = data.get("final_docx_path_abs")
        final_docx: str | None
        if final_docx_raw in (None, ""):
            final_docx = None
        else:
            final_docx = str(final_docx_raw)

        run_status_raw = data.get("run_status")
        if isinstance(run_status_raw, str) and run_status_raw.strip():
            run_status = run_status_raw.strip()
        else:
            run_status = "running"
        finished_at_raw = data.get("finished_at")
        finished_at: str | None
        if finished_at_raw in (None, ""):
            finished_at = None
        else:
            finished_at = str(finished_at_raw)
        halt_reason_raw = data.get("halt_reason")
        if halt_reason_raw in (None, ""):
            halt_reason = None
        else:
            halt_reason = str(halt_reason_raw)

        pages_raw_obj = data["pages"]
        if not isinstance(pages_raw_obj, dict):
            return None
        pages: dict[str, dict[str, Any]] = {}
        for key, value in pages_raw_obj.items():
            pages[str(key)] = _coerce_page_record(value)
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
        done_count = 0
        failed_count = 0
        for page_data in pages.values():
            status = str(page_data.get("status", "")).strip().lower()
            if status == PageStatus.DONE.value:
                done_count += 1
            elif status == PageStatus.FAILED.value:
                failed_count += 1
        pending_count = max(0, fallback_selection_count - done_count - failed_count)

        settings_obj = data["settings"]
        if not isinstance(settings_obj, dict):
            return None
        failure_context_obj = data.get("failure_context", {})
        failure_context = dict(failure_context_obj) if isinstance(failure_context_obj, dict) else {}
        from .structured_artifacts import normalize_protocol_identity

        protocol_raw = data.get("protocol_identity", {})
        if not isinstance(protocol_raw, dict):
            return None
        protocol_identity = normalize_protocol_identity(protocol_raw)

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
            settings=dict(settings_obj),
            context_hash=str(data["context_hash"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            frozen_outdir_abs=str(data.get("frozen_outdir_abs", path.parent.parent.resolve())),
            run_dir_abs=str(data.get("run_dir_abs", path.parent.resolve())),
            run_status=run_status,
            halt_reason=halt_reason,
            final_docx_path_abs=final_docx,
            run_started_at=str(data.get("run_started_at", "")),
            finished_at=finished_at,
            pages=pages,
            last_completed_page=int(data.get("last_completed_page", 0)),
            done_count=int(data.get("done_count", done_count)),
            failed_count=int(data.get("failed_count", failed_count)),
            pending_count=int(data.get("pending_count", pending_count)),
            failure_context=failure_context,
            protocol_identity=protocol_identity,
        )
    except (TypeError, ValueError, KeyError):
        return None


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
    protocol_identity: dict[str, Any] | None = None,
) -> str | None:
    from .structured_artifacts import StructuredArtifactError, normalize_protocol_identity

    # This must run before the caller writes logs, creates directories or makes
    # any provider/authentication request. A saved legacy run stays legacy.
    try:
        identity = normalize_protocol_identity(state.protocol_identity)
        expected_identity = normalize_protocol_identity(protocol_identity)
    except StructuredArtifactError:
        return "translation protocol identity is invalid."
    if identity != expected_identity:
        return "translation protocol identity mismatch."
    if state.version != RUN_STATE_VERSION:
        return f"state version mismatch: checkpoint={state.version}, expected={RUN_STATE_VERSION}"
    if state.pdf_fingerprint != pdf_fingerprint:
        return "PDF fingerprint mismatch."
    if state.lang != config.target_lang.value:
        return f"target language mismatch: checkpoint={state.lang}, expected={config.target_lang.value}"
    if state.context_hash != context_hash:
        return "context mismatch."
    expected_settings = settings_fingerprint(config)
    checkpoint_settings = dict(state.settings)
    if "strip_bidi_controls" not in checkpoint_settings:
        checkpoint_settings["strip_bidi_controls"] = True
    if "glossary_file_path" not in checkpoint_settings:
        checkpoint_settings["glossary_file_path"] = ""
    if identity:
        # Structured translation identity separately binds all request inputs.
        # These local assembly/scheduling choices do not invalidate paid text.
        # Retention stays significant: a resume must not silently purge evidence.
        for key in ("page_breaks", "strip_bidi_controls", "workers"):
            expected_settings.pop(key, None)
            checkpoint_settings.pop(key, None)
    if checkpoint_settings != expected_settings:
        return (
            "settings mismatch: checkpoint="
            f"{checkpoint_settings}, expected={expected_settings}"
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
    try:
        _verified_structured_pages(state, paths, protocol_identity=expected_identity)
    except StructuredArtifactError as exc:
        return f"structured checkpoint evidence requires explicit recovery: {exc}"
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
    protocol_identity: dict[str, Any] | None = None,
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
            protocol_identity=protocol_identity,
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
    metadata: dict[str, Any] | None = None,
    structured_commit: dict[str, Any] | None = None,
) -> None:
    from .structured_artifacts import StructuredArtifactError, normalize_protocol_identity, validate_structured_page

    identity = normalize_protocol_identity(state.protocol_identity)
    verified_commit = None
    if identity:
        if (type(page_number) is not int or not isinstance(structured_commit, dict)
                or not state.run_dir_abs or str(page_number) not in state.pages):
            raise StructuredArtifactError("structured_done_requires_committed_evidence")
        verified_commit = validate_structured_page(Path(state.run_dir_abs) / "pages", page_number,
            protocol_identity=identity, expected_commit=structured_commit)
        if verified_commit["source_file_sha256"] != state.pdf_fingerprint:
            raise StructuredArtifactError("structured_done_source_mismatch")
        receipt = verified_commit.get("page_result")
        if receipt is not None and (receipt["usage"] != (usage or {})
                or receipt["image_used"] is not image_used or receipt["retry_used"] is not retry_used):
            raise StructuredArtifactError("structured_done_outcome_mismatch")
    elif structured_commit is not None or (metadata or {}).get("structured_commit"):
        raise StructuredArtifactError("legacy_done_cannot_adopt_structured_evidence")
    page_key = str(page_number)
    page_data = _default_page_record(status=PageStatus.DONE.value)
    page_data.update(_coerce_page_record(state.pages.get(page_key)))
    if metadata:
        page_data.update(metadata)
    if verified_commit is not None:
        page_data["structured_commit"] = verified_commit
        page_data["structured_evidence_state"] = "retained"
    page_data.update(
        {
            "status": PageStatus.DONE.value,
            "image_used": image_used,
            "retry_used": retry_used,
            "usage": usage or {},
            "error": None,
        }
    )
    state.pages[page_key] = page_data
    state.last_completed_page = max(state.last_completed_page, page_number)
    _refresh_counts(state)


def _verified_structured_pages(state: RunState, paths: RunPaths, *,
                               protocol_identity: dict[str, Any] | None) -> dict[int, dict]:
    """Read-only complete-run check, including orphan commits and stray files.

    Manual TXT edits remain available to the writer's explicit local fallback,
    but cannot satisfy structured resume. Incomplete evidence is never removed
    or repurchased automatically. No file or in-memory checkpoint is changed.
    """
    from .structured_artifacts import StructuredArtifactError, normalize_protocol_identity, validate_structured_page

    identity = normalize_protocol_identity(state.protocol_identity)
    if identity != normalize_protocol_identity(protocol_identity):
        raise StructuredArtifactError("translation_protocol_identity_mismatch")
    if not identity:
        if any(record.get("structured_commit") or record.get("structured_evidence_state")
               for record in state.pages.values()):
            raise StructuredArtifactError("mixed_legacy_structured_evidence")
        return {}
    if not state.run_dir_abs or Path(state.run_dir_abs).resolve() != paths.run_dir.resolve():
        raise StructuredArtifactError("structured_run_path_mismatch")
    verified = {}
    allowed_names = set()
    for key, page in state.pages.items():
        try:
            number = int(key)
        except (TypeError, ValueError) as exc:
            raise StructuredArtifactError("invalid_structured_checkpoint_page") from exc
        if str(number) != key or number < 1:
            raise StructuredArtifactError("invalid_structured_checkpoint_page")
        if page.get("structured_evidence_state") == "purged":
            raise StructuredArtifactError("structured_evidence_deliberately_purged")
        names = [f"page_{number:04d}{suffix}" for suffix in
                 (".txt", ".source_structure.json", ".structure.json", ".commit.json")]
        allowed_names.update(names)
        present = [((paths.pages_dir / name).exists() or (paths.pages_dir / name).is_symlink()) for name in names]
        done = page.get("status") == PageStatus.DONE.value
        if not done and not any(present):
            if page.get("structured_commit") or page.get("structured_evidence_state"):
                raise StructuredArtifactError("missing_structured_checkpoint_evidence")
            continue
        if not all(present):
            raise StructuredArtifactError("incomplete_structured_page_bundle")
        expected = page.get("structured_commit")
        if done and (not isinstance(expected, dict) or page.get("structured_evidence_state") != "retained"):
            raise StructuredArtifactError("structured_completion_proof_unavailable")
        commit = validate_structured_page(paths.pages_dir, number, protocol_identity=identity,
                                          expected_commit=expected)
        if commit["source_file_sha256"] != state.pdf_fingerprint:
            raise StructuredArtifactError("structured_source_identity_mismatch")
        if not done and commit.get("page_result") is None:
            raise StructuredArtifactError("orphan_commit_result_unavailable")
        verified[number] = commit
    if paths.pages_dir.exists():
        for path in paths.pages_dir.iterdir():
            if (path.name.startswith("page_") and path.name.endswith(
                    (".txt", ".source_structure.json", ".structure.json", ".commit.json"))
                    and path.name not in allowed_names):
                raise StructuredArtifactError("unselected_structured_page_artifact")
    return verified


def recover_structured_commits(state: RunState, paths: RunPaths, *,
                               protocol_identity: dict[str, Any] | None = None) -> list[int]:
    """Recover only complete commit-before-DONE crashes, without any provider.

    Validate every page before changing even the in-memory state. The caller
    owns its run lock and atomically saves the returned recovered state before
    normal processing. Disk artifacts are never edited or deleted here.
    """
    verified = _verified_structured_pages(state, paths, protocol_identity=protocol_identity)
    recovered = []
    replacements = {}
    for number, commit in verified.items():
        prior = state.pages[str(number)]
        if prior.get("status") == PageStatus.DONE.value:
            continue
        result = commit["page_result"]
        record = deepcopy(prior)
        record.update(deepcopy(result["metadata"]))
        record.update(status=PageStatus.DONE.value, error=None,
                      usage=deepcopy(result["usage"]), image_used=result["image_used"],
                      retry_used=result["retry_used"], structured_commit=deepcopy(commit),
                      structured_evidence_state="retained", recovered_commit_before_done=True)
        replacements[str(number)] = record
        recovered.append(number)
    state.pages.update(replacements)
    if recovered:
        state.last_completed_page = max(state.last_completed_page, *recovered)
        _refresh_counts(state)
    return sorted(recovered)


def mark_structured_evidence_purged(state: RunState, page_numbers: list[int]) -> None:
    """Record retention opt-out only; callers own cleanup after final assembly."""
    from .structured_artifacts import StructuredArtifactError, normalize_protocol_identity, validate_commit_record

    identity = normalize_protocol_identity(state.protocol_identity)
    if not identity or len(set(page_numbers)) != len(page_numbers):
        raise StructuredArtifactError("invalid_structured_purge_selection")
    for number in page_numbers:
        page = state.pages.get(str(number), {})
        if type(number) is not int or page.get("status") != PageStatus.DONE.value:
            raise StructuredArtifactError("only_completed_structured_evidence_can_be_purged")
        validate_commit_record(page.get("structured_commit"), page_number=number, protocol_identity=identity)
    for number in page_numbers:
        state.pages[str(number)]["structured_evidence_state"] = "purged"


def mark_page_failed(
    state: RunState,
    page_number: int,
    *,
    image_used: bool,
    retry_used: bool,
    usage: dict[str, Any] | None,
    error: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    page_key = str(page_number)
    page_data = _default_page_record(status=PageStatus.FAILED.value)
    page_data.update(_coerce_page_record(state.pages.get(page_key)))
    if metadata:
        page_data.update(metadata)
    page_data.update(
        {
            "status": PageStatus.FAILED.value,
            "image_used": image_used,
            "retry_used": retry_used,
            "usage": usage or {},
            "error": error,
        }
    )
    state.pages[page_key] = page_data
    _refresh_counts(state)


def _refresh_counts(state: RunState) -> None:
    done_count = 0
    failed_count = 0
    for page_data in state.pages.values():
        status = str(page_data.get("status", "")).strip().lower()
        if status == PageStatus.DONE.value:
            done_count += 1
        elif status == PageStatus.FAILED.value:
            failed_count += 1
    total = len(state.pages)
    state.done_count = done_count
    state.failed_count = failed_count
    state.pending_count = max(0, total - done_count - failed_count)


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


def parse_effort_policy(value: str) -> EffortPolicy:
    lowered = value.strip().lower()
    if lowered == EffortPolicy.ADAPTIVE.value:
        return EffortPolicy.ADAPTIVE
    if lowered == EffortPolicy.FIXED_HIGH.value:
        return EffortPolicy.FIXED_HIGH
    if lowered == EffortPolicy.FIXED_XHIGH.value:
        return EffortPolicy.FIXED_XHIGH
    raise ValueError("Effort policy must be adaptive, fixed_high, or fixed_xhigh.")


def parse_image_mode(value: str) -> ImageMode:
    lowered = value.strip().lower()
    if lowered == ImageMode.OFF.value:
        return ImageMode.OFF
    if lowered == ImageMode.AUTO.value:
        return ImageMode.AUTO
    if lowered == ImageMode.ALWAYS.value:
        return ImageMode.ALWAYS
    raise ValueError("Image mode must be off, auto, or always.")


def parse_ocr_mode(value: str) -> OcrMode:
    lowered = value.strip().lower()
    if lowered == OcrMode.OFF.value:
        return OcrMode.OFF
    if lowered == OcrMode.AUTO.value:
        return OcrMode.AUTO
    if lowered == OcrMode.ALWAYS.value:
        return OcrMode.ALWAYS
    raise ValueError("OCR mode must be off, auto, or always.")


def parse_ocr_engine_policy(value: str) -> OcrEnginePolicy:
    lowered = value.strip().lower()
    if lowered == OcrEnginePolicy.LOCAL.value:
        return OcrEnginePolicy.LOCAL
    if lowered == OcrEnginePolicy.LOCAL_THEN_API.value:
        return OcrEnginePolicy.LOCAL_THEN_API
    if lowered == OcrEnginePolicy.API.value:
        return OcrEnginePolicy.API
    raise ValueError("OCR engine must be local, local_then_api, or api.")


def parse_api_key_source(value: str) -> ApiKeySource:
    lowered = value.strip().lower()
    if lowered == ApiKeySource.ENV.value:
        return ApiKeySource.ENV
    if lowered == ApiKeySource.CREDMAN.value:
        return ApiKeySource.CREDMAN
    if lowered == ApiKeySource.INLINE.value:
        return ApiKeySource.INLINE
    raise ValueError("API key source must be env, credman, or inline.")
