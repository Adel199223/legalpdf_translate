"""Core page-by-page translation workflow shared by CLI and GUI."""

from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from .arabic_pre_tokenize import pretokenize_arabic_source
from .checkpoint import (
    RunPaths,
    build_run_paths,
    clear_run_dirs,
    ensure_run_dirs,
    list_completed_pages,
    load_run_state,
    mark_page_done,
    mark_page_failed,
    new_run_state,
    record_final_docx_path,
    resume_incompatibility_reason,
    save_run_state_atomic,
    sha256_of_bytes,
    sha256_of_file,
    sha256_of_text,
)
from .config import load_environment
from .docx_writer import assemble_docx
from .image_io import render_page_image_data_url
from .ocr_engine import OCREngine, OcrResult, build_ocr_engine, ocr_engine_config_from_run_config
from .ocr_helpers import ocr_pdf_page_text
from .openai_client import OpenAIResponsesClient
from .output_normalize import normalize_output_text
from .output_paths import require_writable_output_dir
from .page_selection import resolve_page_selection
from .pdf_text_order import extract_ordered_page_text, get_page_count
from .prompt_builder import build_page_prompt, build_retry_prompt
from .resources_loader import load_system_instructions
from .types import OcrMode, PageStatus, ReasoningEffort, RunConfig, RunState, RunSummary, TargetLang
from .validators import parse_code_block_output, validate_ar, validate_enfr


@dataclass(slots=True)
class _Evaluation:
    ok: bool
    normalized_text: str | None
    defect_reason: str | None


class TranslationWorkflow:
    def __init__(
        self,
        *,
        client: OpenAIResponsesClient | None = None,
        log_callback: Callable[[str], None] | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> None:
        self._provided_client = client
        self._log_callback = log_callback
        self._progress_callback = progress_callback
        self._cancel_event = threading.Event()

        self._last_config: RunConfig | None = None
        self._last_paths: RunPaths | None = None
        self._last_state: RunState | None = None

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self, config: RunConfig) -> RunSummary:
        self._cancel_event.clear()
        self._last_config = None
        self._last_paths = None
        self._last_state = None

        config = self._normalize_config(config)
        self._validate_config(config)
        self._last_config = config

        load_environment()
        if not config.keep_intermediates:
            self._log(
                "keep_intermediates is OFF: pages/images will be deleted after successful export; "
                "resume/rebuild will not be available."
            )
        context_text, context_hash = self._resolve_context(config)

        total_pages = get_page_count(config.pdf_path)
        selected_pages = resolve_page_selection(
            total_pages,
            config.start_page,
            config.end_page,
            config.max_pages,
        )
        if not selected_pages:
            raise ValueError("No pages selected for translation.")
        selection_start_page = selected_pages[0]
        selection_end_page = selected_pages[-1]
        selection_page_count = len(selected_pages)
        max_pages_effective = selection_page_count

        pdf_fingerprint = sha256_of_file(config.pdf_path)
        paths, existing_state = self._resolve_paths_for_run(config)
        ensure_run_dirs(paths)
        self._last_paths = paths

        run_state = self._load_or_initialize_run_state(
            config=config,
            paths=paths,
            existing_state=existing_state,
            pdf_fingerprint=pdf_fingerprint,
            context_hash=context_hash,
            total_pages=total_pages,
            selected_pages=selected_pages,
            selection_start_page=selection_start_page,
            selection_end_page=selection_end_page,
            selection_page_count=selection_page_count,
            max_pages_effective=max_pages_effective,
        )
        run_state.run_status = "running"
        run_state.final_docx_path_abs = None
        run_state.finished_at = None
        save_run_state_atomic(paths.run_state_path, run_state)
        self._last_state = run_state

        client = self._provided_client
        instructions = load_system_instructions(config.target_lang)
        ocr_engine: OCREngine | None = None
        if config.ocr_mode != OcrMode.OFF:
            try:
                ocr_engine = build_ocr_engine(ocr_engine_config_from_run_config(config))
            except Exception:
                if config.ocr_engine.value == "api" or config.ocr_mode == OcrMode.ALWAYS:
                    raise
                ocr_engine = None
                self._log("OCR engine unavailable; continuing without OCR for this run.")

        failed_page: int | None = None
        compliance_failure = False
        for selected_index, page_number in enumerate(selected_pages, start=1):
            self._log(f"Processing {selected_index}/{selection_page_count} (PDF page {page_number})")
            if self._cancel_event.is_set():
                self._log("Cancellation requested; stopping before next page.")
                break
            page_state = run_state.pages.get(str(page_number))
            if config.resume and page_state and page_state.get("status") == PageStatus.DONE.value:
                self._log(f"page={page_number} image_used=False retry_used=False status=skipped")
                self._progress(selected_index, selection_page_count, "skipped (already done)")
                continue

            self._progress(selected_index, selection_page_count, "processing")
            try:
                if client is None:
                    client = OpenAIResponsesClient(logger=self._log)
                page_result = self._process_page(
                    client=client,
                    config=config,
                    paths=paths,
                    instructions=instructions,
                    context_text=context_text,
                    page_number=page_number,
                    total_pages=total_pages,
                    ocr_engine=ocr_engine,
                )
            except Exception as exc:  # noqa: BLE001
                self._log(f"Runtime failure on page {page_number}: {exc}")
                page_result = _PageOutcome(
                    status=PageStatus.FAILED,
                    image_used=False,
                    retry_used=False,
                    usage={},
                    error="runtime_failure",
                )
            if page_result.status == PageStatus.DONE:
                self._log(
                    f"page={page_number} image_used={page_result.image_used} "
                    f"retry_used={page_result.retry_used} status=done"
                )
                mark_page_done(
                    run_state,
                    page_number,
                    image_used=page_result.image_used,
                    retry_used=page_result.retry_used,
                    usage=page_result.usage,
                )
                save_run_state_atomic(paths.run_state_path, run_state)
                self._progress(selected_index, selection_page_count, "done")
                continue

            failed_page = page_number
            compliance_failure = page_result.error == "compliance_failure"
            self._log(
                f"page={page_number} image_used={page_result.image_used} "
                f"retry_used={page_result.retry_used} status=failed"
            )
            mark_page_failed(
                run_state,
                page_number,
                image_used=page_result.image_used,
                retry_used=page_result.retry_used,
                usage=page_result.usage,
                error=page_result.error or "unknown_failure",
            )
            save_run_state_atomic(paths.run_state_path, run_state)
            self._progress(selected_index, selection_page_count, "failed")
            break

        self._last_state = run_state
        completed_pages = len(list_completed_pages(run_state))

        if failed_page is None and not self._cancel_event.is_set():
            try:
                output_docx = assemble_docx(
                    paths.pages_dir,
                    paths.final_docx_path,
                    lang=config.target_lang,
                    page_breaks=config.page_breaks,
                )
            except Exception as exc:  # noqa: BLE001
                run_state.run_status = "docx_write_failed"
                run_state.finished_at = self._utc_now()
                run_state.final_docx_path_abs = None
                save_run_state_atomic(paths.run_state_path, run_state)
                self._log(f"DOCX save failed at {paths.final_docx_path}: {exc}")
                return RunSummary(
                    success=False,
                    exit_code=2,
                    output_docx=None,
                    partial_docx=None,
                    run_dir=paths.run_dir,
                    completed_pages=completed_pages,
                    failed_page=None,
                    error="docx_write_failed",
                    attempted_output_docx=paths.final_docx_path,
                )

            record_final_docx_path(run_state, output_docx)
            run_state.run_status = "completed"
            run_state.finished_at = self._utc_now()
            save_run_state_atomic(paths.run_state_path, run_state)
            if not config.keep_intermediates:
                self._cleanup_intermediates(paths)
            return RunSummary(
                success=True,
                exit_code=0,
                output_docx=output_docx,
                partial_docx=None,
                run_dir=paths.run_dir,
                completed_pages=completed_pages,
                failed_page=None,
                error=None,
                attempted_output_docx=output_docx,
            )

        partial_docx = None
        if completed_pages > 0:
            partial_docx = self.export_partial_docx()

        if self._cancel_event.is_set():
            run_state.run_status = "cancelled"
            run_state.finished_at = self._utc_now()
            save_run_state_atomic(paths.run_state_path, run_state)
            return RunSummary(
                success=False,
                exit_code=2,
                output_docx=None,
                partial_docx=partial_docx,
                run_dir=paths.run_dir,
                completed_pages=completed_pages,
                failed_page=failed_page,
                error="cancelled",
            )

        run_state.run_status = "compliance_failure" if compliance_failure else "runtime_failure"
        run_state.finished_at = self._utc_now()
        save_run_state_atomic(paths.run_state_path, run_state)
        return RunSummary(
            success=False,
            exit_code=3 if compliance_failure else 2,
            output_docx=None,
            partial_docx=partial_docx,
            run_dir=paths.run_dir,
            completed_pages=completed_pages,
            failed_page=failed_page,
            error="compliance_failure" if compliance_failure else "runtime_failure",
        )

    def rebuild_docx(self, config: RunConfig) -> Path:
        config = self._normalize_config(config)
        self._validate_config(config)

        base_paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
        run_state = load_run_state(base_paths.run_state_path)

        effective_outdir = base_paths.frozen_outdir
        run_started_at = base_paths.run_started_at
        run_dir = base_paths.run_dir
        pages_dir = base_paths.pages_dir
        run_state_path = base_paths.run_state_path

        if run_state is not None:
            if run_state.frozen_outdir_abs:
                effective_outdir = require_writable_output_dir(Path(run_state.frozen_outdir_abs))
            if run_state.run_started_at:
                run_started_at = run_state.run_started_at
            if run_state.run_dir_abs:
                run_dir = Path(run_state.run_dir_abs).expanduser().resolve()
                pages_dir = run_dir / "pages"
                run_state_path = run_dir / "run_state.json"

        final_paths = build_run_paths(
            output_dir=effective_outdir,
            pdf_path=config.pdf_path,
            lang=config.target_lang,
            run_started_at=run_started_at,
        )

        page_files = sorted(pages_dir.glob("page_*.txt"))
        if not page_files:
            raise ValueError(f"No completed page files found for rebuild: {pages_dir}")

        output_docx = assemble_docx(
            pages_dir,
            final_paths.final_docx_path,
            lang=config.target_lang,
            page_breaks=config.page_breaks,
        )

        if run_state is not None:
            run_state.frozen_outdir_abs = str(effective_outdir)
            run_state.run_dir_abs = str(run_dir)
            run_state.run_started_at = run_started_at
            record_final_docx_path(run_state, output_docx)
            run_state.run_status = "completed"
            run_state.finished_at = self._utc_now()
            save_run_state_atomic(run_state_path, run_state)

        self._last_config = config
        self._last_paths = final_paths
        self._last_state = run_state
        return output_docx

    def export_partial_docx(self) -> Path | None:
        if self._last_config is None or self._last_paths is None or self._last_state is None:
            return None
        completed = list_completed_pages(self._last_state)
        if not completed:
            return None
        return assemble_docx(
            self._last_paths.pages_dir,
            self._last_paths.partial_docx_path,
            lang=self._last_config.target_lang,
            page_breaks=self._last_config.page_breaks,
        )

    def _process_page(
        self,
        *,
        client: OpenAIResponsesClient,
        config: RunConfig,
        paths: RunPaths,
        instructions: str,
        context_text: str | None,
        page_number: int,
        total_pages: int,
        ocr_engine: OCREngine | None,
    ) -> "_PageOutcome":
        ordered = extract_ordered_page_text(config.pdf_path, page_number - 1)
        extracted_text = ordered.text
        extracted_usable = self._is_usable_source_text(extracted_text)

        ocr_result = OcrResult(
            text="",
            engine="none",
            failed_reason="ocr_not_requested",
            chars=0,
        )
        ocr_attempted = False
        should_ocr = False
        if config.ocr_mode == OcrMode.ALWAYS:
            should_ocr = True
        elif config.ocr_mode == OcrMode.AUTO:
            should_ocr = not extracted_usable
        if should_ocr and ocr_engine is not None:
            ocr_attempted = True
            ocr_result = ocr_pdf_page_text(
                config.pdf_path,
                page_number,
                mode=OcrMode.ALWAYS,
                engine=ocr_engine,
                prefer_header=False,
                lang_hint=config.target_lang.value,
            )

        source_text = ocr_result.text if ocr_result.chars > 0 else extracted_text
        if config.target_lang == TargetLang.AR:
            source_text = pretokenize_arabic_source(source_text)

        source_usable = self._is_usable_source_text(source_text)
        image_used = False
        if not source_usable:
            if config.ocr_mode == OcrMode.OFF or (ocr_attempted and ocr_result.chars <= 0):
                image_used = True
        image_data_url = None
        if image_used:
            image_path = paths.images_dir / f"page_{page_number:04d}.jpg" if config.keep_intermediates else None
            image_data_url, _ = render_page_image_data_url(
                config.pdf_path,
                page_number - 1,
                save_path=image_path,
            )
        ocr_reason = ocr_result.failed_reason or "none"
        self._log(
            f"page={page_number} ocr_used={ocr_result.engine} ocr_chars={ocr_result.chars} "
            f"ocr_failed_reason={ocr_reason}"
        )

        prompt_text = build_page_prompt(
            lang=config.target_lang,
            page_number=page_number,
            total_pages=total_pages,
            source_text=source_text,
            context_text=context_text,
        )

        usage_payload: dict[str, object] = {
            "ocr": {
                "engine": ocr_result.engine,
                "chars": ocr_result.chars,
                "failed_reason": ocr_result.failed_reason,
            }
        }
        initial = client.create_page_response(
            instructions=instructions,
            prompt_text=prompt_text,
            effort=config.effort.value,
            image_data_url=image_data_url,
        )
        usage_payload["attempt_1"] = initial.usage
        initial_eval = self._evaluate_output(initial.raw_output, config.target_lang)
        if initial_eval.ok and initial_eval.normalized_text is not None:
            output_path = paths.pages_dir / f"page_{page_number:04d}.txt"
            output_path.write_text(initial_eval.normalized_text, encoding="utf-8")
            return _PageOutcome(
                status=PageStatus.DONE,
                image_used=image_used,
                retry_used=False,
                usage=usage_payload,
                error=None,
            )

        retry_prompt = build_retry_prompt(config.target_lang, initial.raw_output)
        retry = client.create_page_response(
            instructions=instructions,
            prompt_text=retry_prompt,
            effort=ReasoningEffort.MEDIUM.value,
            image_data_url=None,
        )
        usage_payload["attempt_2"] = retry.usage
        retry_eval = self._evaluate_output(retry.raw_output, config.target_lang)
        if retry_eval.ok and retry_eval.normalized_text is not None:
            output_path = paths.pages_dir / f"page_{page_number:04d}.txt"
            output_path.write_text(retry_eval.normalized_text, encoding="utf-8")
            return _PageOutcome(
                status=PageStatus.DONE,
                image_used=image_used,
                retry_used=True,
                usage=usage_payload,
                error=None,
            )

        defect_reason = retry_eval.defect_reason or initial_eval.defect_reason or "compliance_failure"
        self._log(f"Compliance failure on page {page_number}: {defect_reason}")
        return _PageOutcome(
            status=PageStatus.FAILED,
            image_used=image_used,
            retry_used=True,
            usage=usage_payload,
            error="compliance_failure",
        )

    def _evaluate_output(self, raw_output: str, lang: TargetLang) -> _Evaluation:
        parsed = parse_code_block_output(raw_output)
        if parsed.block_count == 0:
            return _Evaluation(ok=False, normalized_text=None, defect_reason="No code block in model output.")
        if parsed.block_count > 1:
            return _Evaluation(ok=False, normalized_text=None, defect_reason="More than one code block in model output.")
        if parsed.inner_content is None:
            return _Evaluation(ok=False, normalized_text=None, defect_reason="Missing inner code block content.")

        normalized = normalize_output_text(parsed.inner_content, lang=lang)
        if lang in (TargetLang.EN, TargetLang.FR):
            validation = validate_enfr(normalized)
        else:
            validation = validate_ar(normalized)
        if not validation.ok:
            return _Evaluation(ok=False, normalized_text=normalized, defect_reason=validation.reason)
        if parsed.outside_has_non_whitespace:
            return _Evaluation(
                ok=False,
                normalized_text=normalized,
                defect_reason="Non-whitespace text found outside code block.",
            )
        return _Evaluation(ok=True, normalized_text=normalized, defect_reason=None)

    def _resolve_paths_for_run(self, config: RunConfig) -> tuple[RunPaths, RunState | None]:
        paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
        existing = load_run_state(paths.run_state_path)
        if not config.resume or existing is None:
            return paths, existing

        if existing.frozen_outdir_abs:
            state_outdir = Path(existing.frozen_outdir_abs).expanduser().resolve()
            if state_outdir != paths.frozen_outdir:
                raise ValueError(
                    "Checkpoint output folder does not match the selected output folder. "
                    "Use New Run (resume disabled)."
                )
        run_started_at = existing.run_started_at or paths.run_started_at
        resolved_paths = build_run_paths(
            output_dir=config.output_dir,
            pdf_path=config.pdf_path,
            lang=config.target_lang,
            run_started_at=run_started_at,
        )
        return resolved_paths, existing

    def _load_or_initialize_run_state(
        self,
        *,
        config: RunConfig,
        paths: RunPaths,
        existing_state: RunState | None,
        pdf_fingerprint: str,
        context_hash: str,
        total_pages: int,
        selected_pages: list[int],
        selection_start_page: int,
        selection_end_page: int,
        selection_page_count: int,
        max_pages_effective: int,
    ) -> RunState:
        existing = existing_state
        if existing is None:
            existing = load_run_state(paths.run_state_path)

        if config.resume and existing is not None:
            if existing.frozen_outdir_abs:
                frozen_from_state = Path(existing.frozen_outdir_abs).expanduser().resolve()
                if frozen_from_state != paths.frozen_outdir:
                    raise ValueError(
                        "Checkpoint output folder mismatch. Start a new run with resume disabled."
                    )
            if existing.run_dir_abs:
                run_dir_from_state = Path(existing.run_dir_abs).expanduser().resolve()
                if run_dir_from_state != paths.run_dir:
                    raise ValueError(
                        "Checkpoint run directory mismatch. Start a new run with resume disabled."
                    )

            mismatch_reason = resume_incompatibility_reason(
                existing,
                config=config,
                paths=paths,
                pdf_fingerprint=pdf_fingerprint,
                context_hash=context_hash,
                selection_start_page=selection_start_page,
                selection_end_page=selection_end_page,
                selection_page_count=selection_page_count,
                max_pages_effective=max_pages_effective,
            )
            if mismatch_reason is None:
                existing.frozen_outdir_abs = str(paths.frozen_outdir)
                existing.run_dir_abs = str(paths.run_dir)
                existing.run_started_at = paths.run_started_at
                save_run_state_atomic(paths.run_state_path, existing)
                self._log("Compatible checkpoint found. Resuming from completed pages.")
                return existing
            raise ValueError(
                "Checkpoint is incompatible with current run settings: "
                f"{mismatch_reason}. Disable resume or use New Run."
            )

        clear_run_dirs(paths)
        state = new_run_state(
            config=config,
            paths=paths,
            pdf_fingerprint=pdf_fingerprint,
            context_hash=context_hash,
            total_pages=total_pages,
            selected_pages=selected_pages,
        )
        save_run_state_atomic(paths.run_state_path, state)
        return state

    def _normalize_config(self, config: RunConfig) -> RunConfig:
        outdir_abs = require_writable_output_dir(config.output_dir)
        context_file_abs = config.context_file.expanduser().resolve() if config.context_file else None
        return RunConfig(
            pdf_path=config.pdf_path.expanduser().resolve(),
            output_dir=outdir_abs,
            target_lang=config.target_lang,
            effort=config.effort,
            image_mode=config.image_mode,
            start_page=config.start_page,
            end_page=config.end_page,
            max_pages=config.max_pages,
            resume=config.resume,
            page_breaks=config.page_breaks,
            keep_intermediates=config.keep_intermediates,
            ocr_mode=config.ocr_mode,
            ocr_engine=config.ocr_engine,
            ocr_api_base_url=(config.ocr_api_base_url or "").strip() or None,
            ocr_api_model=(config.ocr_api_model or "").strip() or None,
            ocr_api_key_env_name=(config.ocr_api_key_env_name or "").strip() or "DEEPSEEK_API_KEY",
            context_file=context_file_abs,
            context_text=config.context_text,
        )

    def _is_usable_source_text(self, value: str) -> bool:
        cleaned = value.strip()
        if not cleaned:
            return False
        if len(cleaned) < 24:
            return False
        alpha_num = sum(1 for ch in cleaned if ch.isalnum())
        if alpha_num < max(12, int(len(cleaned) * 0.2)):
            return False
        lines = [line for line in cleaned.splitlines() if line.strip()]
        if lines and len(lines) >= 10:
            short_ratio = sum(1 for line in lines if len(line.strip()) <= 2) / len(lines)
            if short_ratio > 0.75:
                return False
        return True

    def _validate_config(self, config: RunConfig) -> None:
        if not config.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {config.pdf_path}")
        if config.target_lang not in (TargetLang.EN, TargetLang.FR, TargetLang.AR):
            raise ValueError("Invalid target language.")
        if config.start_page <= 0:
            raise ValueError("start_page must be >= 1.")
        if config.end_page is not None and config.end_page <= 0:
            raise ValueError("end_page must be >= 1 when provided.")
        if config.end_page is not None and config.start_page > config.end_page:
            raise ValueError("start_page must be <= end_page.")
        if config.max_pages is not None and config.max_pages <= 0:
            raise ValueError("max_pages must be a positive integer when provided.")
        if config.context_file and not config.context_file.exists():
            raise FileNotFoundError(f"Context file not found: {config.context_file}")

    def _resolve_context(self, config: RunConfig) -> tuple[str | None, str]:
        if config.context_file:
            raw = config.context_file.read_bytes()
            return raw.decode("utf-8"), sha256_of_bytes(raw)
        if config.context_text:
            return config.context_text, sha256_of_text(config.context_text)
        return None, sha256_of_text(None)

    def _cleanup_intermediates(self, paths: RunPaths) -> None:
        shutil.rmtree(paths.pages_dir, ignore_errors=True)
        shutil.rmtree(paths.images_dir, ignore_errors=True)

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _progress(self, current_page: int, total_pages: int, status: str) -> None:
        if self._progress_callback:
            self._progress_callback(current_page, total_pages, status)

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class _PageOutcome:
    status: PageStatus
    image_used: bool
    retry_used: bool
    usage: dict[str, object]
    error: str | None
