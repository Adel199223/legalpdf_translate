"""Core page-by-page translation workflow shared by CLI and GUI."""

from __future__ import annotations

import json
import math
import os
import random
import shutil
import threading
import time
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

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
from .config import IMAGE_MAX_DATA_URL_BYTES_AR, IMAGE_MAX_DATA_URL_BYTES_ENFR
from .docx_writer import assemble_docx
from .image_io import render_page_image_data_url, should_include_image
from .ocr_engine import OCREngine, OcrResult, build_ocr_engine, ocr_engine_config_from_run_config
from .ocr_helpers import ocr_pdf_page_text
from .openai_client import ApiCallError, OpenAIResponsesClient
from .output_normalize import normalize_output_text
from .output_paths import require_writable_output_dir
from .page_selection import resolve_page_selection
from .pdf_text_order import extract_ordered_page_text, get_page_count
from .prompt_builder import build_page_prompt, build_retry_prompt
from .run_report import RunEventCollector
from .resources_loader import load_system_instructions
from .types import AnalyzeSummary, ImageMode, OcrMode, PageStatus, ReasoningEffort, RunConfig, RunState, RunSummary, TargetLang
from .validators import parse_code_block_output, validate_ar, validate_enfr


@dataclass(slots=True)
class _Evaluation:
    ok: bool
    normalized_text: str | None
    defect_reason: str | None
    parser_failed: bool = False
    validator_failed: bool = False
    outside_text: bool = False
    block_count: int = 0


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
        self._event_collector: RunEventCollector | None = None
        self._run_stage_timings_ms: dict[str, float] = {}
        self._diagnostics_admin_mode = False
        self._ocr_provider_configured = False
        self._ocr_unavailable_warned = False
        self._ocr_unavailable_lock = threading.Lock()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self, config: RunConfig) -> RunSummary:
        run_started_perf = time.perf_counter()
        self._cancel_event.clear()
        self._last_config = None
        self._last_paths = None
        self._last_state = None
        self._event_collector = None
        self._run_stage_timings_ms = {}
        self._ocr_provider_configured = False
        self._ocr_unavailable_warned = False

        config = self._normalize_config(config)
        self._validate_config(config)
        self._last_config = config
        self._diagnostics_admin_mode = bool(config.diagnostics_admin_mode)

        started = time.perf_counter()
        load_environment()
        self._run_stage_timings_ms["load_environment"] = round((time.perf_counter() - started) * 1000.0, 3)
        if not config.keep_intermediates:
            self._log(
                "keep_intermediates is OFF: pages/images will be deleted after successful export; "
                "resume/rebuild will not be available."
            )
        context_text, context_hash = self._resolve_context(config)

        started = time.perf_counter()
        total_pages = get_page_count(config.pdf_path)
        self._run_stage_timings_ms["get_page_count"] = round((time.perf_counter() - started) * 1000.0, 3)
        started = time.perf_counter()
        selected_pages = resolve_page_selection(
            total_pages,
            config.start_page,
            config.end_page,
            config.max_pages,
        )
        self._run_stage_timings_ms["resolve_page_selection"] = round((time.perf_counter() - started) * 1000.0, 3)
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
        self._event_collector = RunEventCollector(run_dir=paths.run_dir, enabled=self._diagnostics_admin_mode)
        self._record_event(
            event_type="run_started",
            stage="run",
            details={
                "run_id": paths.run_started_at,
                "pdf_name": config.pdf_path.name,
                "target_lang": config.target_lang.value,
                "selection_start_page": selection_start_page,
                "selection_end_page": selection_end_page,
                "selection_page_count": selection_page_count,
                "max_pages_effective": max_pages_effective,
                "resume": bool(config.resume),
                "image_mode": config.image_mode.value,
                "ocr_mode": config.ocr_mode.value,
                "ocr_engine": config.ocr_engine.value,
                "keep_intermediates": bool(config.keep_intermediates),
                "strip_bidi_controls": bool(config.strip_bidi_controls),
            },
        )

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
        self._record_event(
            event_type="run_state_ready",
            stage="checkpoint",
            details={
                "run_state_path": str(paths.run_state_path),
                "done_count": int(run_state.done_count),
                "failed_count": int(run_state.failed_count),
                "pending_count": int(run_state.pending_count),
            },
        )

        instructions = load_system_instructions(config.target_lang)
        ocr_engine: OCREngine | None = None
        if config.ocr_mode != OcrMode.OFF:
            try:
                ocr_engine = build_ocr_engine(ocr_engine_config_from_run_config(config))
                self._ocr_provider_configured = True
                self._record_event(
                    event_type="ocr_engine_ready",
                    stage="ocr",
                    decisions={"engine_policy": config.ocr_engine.value},
                )
            except Exception:
                if config.ocr_engine.value == "api" or config.ocr_mode == OcrMode.ALWAYS:
                    raise
                ocr_engine = None
                self._ocr_provider_configured = False
                self._record_event(
                    event_type="ocr_engine_not_configured",
                    stage="ocr",
                    decisions={"engine_policy": config.ocr_engine.value},
                    details={
                        "note": "OCR provider not configured; OCR will only be used if explicitly requested by routing.",
                    },
                )

        state_lock = threading.Lock()
        failed_page: int | None = None
        compliance_failure = False
        halt_reason: str | None = None

        thread_local = threading.local()
        provided_client = self._provided_client

        def _get_thread_client() -> OpenAIResponsesClient | Any:
            cached = getattr(thread_local, "client", None)
            if isinstance(cached, OpenAIResponsesClient):
                return cached
            if provided_client is not None and not isinstance(provided_client, OpenAIResponsesClient):
                return provided_client
            if isinstance(provided_client, OpenAIResponsesClient):
                client_instance = OpenAIResponsesClient(
                    max_transport_retries=provided_client._max_transport_retries,
                    base_backoff_seconds=provided_client._base_backoff_seconds,
                    backoff_cap_seconds=provided_client._backoff_cap_seconds,
                    pre_call_jitter_seconds=provided_client._pre_call_jitter_seconds,
                    request_timeout_seconds=provided_client._request_timeout_seconds,
                    logger=self._log,
                )
            else:
                client_instance = OpenAIResponsesClient(logger=self._log)
            thread_local.client = client_instance
            return client_instance

        pending_pages: list[int] = []
        for page_number in selected_pages:
            page_state = run_state.pages.get(str(page_number))
            if config.resume and page_state and page_state.get("status") == PageStatus.DONE.value:
                self._log(f"page={page_number} image_used=False retry_used=False status=skipped")
                self._record_event(
                    event_type="page_skipped_resume",
                    stage="page",
                    page_index=page_number,
                    decisions={"reason": "already_done"},
                )
                continue
            pending_pages.append(page_number)

        if run_state.done_count > 0:
            self._progress(run_state.done_count, selection_page_count, f"Resumed {run_state.done_count} page(s)")

        if pending_pages:
            worker_count = max(1, min(6, config.workers, len(pending_pages)))

            def _run_page_task(page_number: int) -> _PageOutcome | None:
                if self._cancel_event.is_set():
                    return None
                local_client = _get_thread_client()
                self._log(f"Processing PDF page {page_number}")
                self._record_event(
                    event_type="page_started",
                    stage="page",
                    page_index=page_number,
                )
                try:
                    return self._process_page(
                        client=local_client,
                        config=config,
                        paths=paths,
                        instructions=instructions,
                        context_text=context_text,
                        page_number=page_number,
                        total_pages=total_pages,
                        ocr_engine=ocr_engine,
                    )
                except Exception as exc:  # noqa: BLE001
                    exception_class = type(exc).__name__
                    status_code = getattr(exc, "status_code", None)
                    if isinstance(status_code, int):
                        self._log(
                            f"Runtime failure on page {page_number}: "
                            f"exception_class={exception_class} status_code={status_code}"
                        )
                    else:
                        self._log(
                            f"Runtime failure on page {page_number}: exception_class={exception_class}"
                        )
                    self._record_event(
                        event_type="page_runtime_exception",
                        stage="page",
                        page_index=page_number,
                        error=f"exception_class={exception_class}",
                        details={"status_code": status_code if isinstance(status_code, int) else None},
                    )
                    return _PageOutcome(
                        status=PageStatus.FAILED,
                        image_used=False,
                        retry_used=False,
                        usage={},
                        error="runtime_failure",
                    )

            futures: dict[Future[_PageOutcome | None], int] = {}
            next_page_idx = 0
            stop_submitting = False
            submitted_count = 0

            def _submit_next(executor: ThreadPoolExecutor) -> bool:
                nonlocal next_page_idx, submitted_count
                if stop_submitting or self._cancel_event.is_set():
                    return False
                if next_page_idx >= len(pending_pages):
                    return False
                page_number = pending_pages[next_page_idx]
                next_page_idx += 1
                if worker_count > 1 and submitted_count > 0:
                    time.sleep(random.uniform(0.0, 0.12))
                future = executor.submit(_run_page_task, page_number)
                futures[future] = page_number
                submitted_count += 1
                return True

            with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="lpt-page") as executor:
                for _ in range(worker_count):
                    if not _submit_next(executor):
                        break

                while futures:
                    if self._cancel_event.is_set():
                        stop_submitting = True
                        for future in list(futures.keys()):
                            if future.cancel():
                                futures.pop(future, None)
                        if not futures:
                            break

                    done_set, _ = wait(set(futures.keys()), return_when=FIRST_COMPLETED)
                    for future in done_set:
                        page_number = futures.pop(future, None)
                        if page_number is None:
                            continue
                        if future.cancelled():
                            continue

                        outcome = future.result()
                        if outcome is None:
                            continue

                        if outcome.status == PageStatus.DONE:
                            self._log(
                                f"page={page_number} image_used={outcome.image_used} "
                                f"retry_used={outcome.retry_used} status=done"
                            )
                            with state_lock:
                                mark_page_done(
                                    run_state,
                                    page_number,
                                    image_used=outcome.image_used,
                                    retry_used=outcome.retry_used,
                                    usage=outcome.usage,
                                    metadata=outcome.page_metadata,
                                )
                                save_run_state_atomic(paths.run_state_path, run_state)
                                done_count = run_state.done_count
                            self._record_event(
                                event_type="page_done",
                                stage="page",
                                page_index=page_number,
                                duration_ms=float((outcome.page_metadata or {}).get("wall_seconds", 0.0) or 0.0)
                                * 1000.0,
                                counters={
                                    "api_calls_count": int((outcome.page_metadata or {}).get("api_calls_count", 0) or 0),
                                    "input_tokens": int((outcome.page_metadata or {}).get("input_tokens", 0) or 0),
                                    "output_tokens": int((outcome.page_metadata or {}).get("output_tokens", 0) or 0),
                                    "reasoning_tokens": int(
                                        (outcome.page_metadata or {}).get("reasoning_tokens", 0) or 0
                                    ),
                                    "total_tokens": int((outcome.page_metadata or {}).get("total_tokens", 0) or 0),
                                    "transport_retries_count": int(
                                        (outcome.page_metadata or {}).get("transport_retries_count", 0) or 0
                                    ),
                                    "backoff_wait_seconds_total": float(
                                        (outcome.page_metadata or {}).get("backoff_wait_seconds_total", 0.0) or 0.0
                                    ),
                                },
                                decisions={
                                    "source_route": str((outcome.page_metadata or {}).get("source_route", "") or ""),
                                    "image_used": bool(outcome.image_used),
                                    "retry_used": bool(outcome.retry_used),
                                },
                            )
                            if self._diagnostics_admin_mode and outcome.page_metadata:
                                self._log(
                                    "page="
                                    f"{page_number} route={outcome.page_metadata.get('source_route', '')} "
                                    f"extract_s={outcome.page_metadata.get('extract_seconds', 0.0)} "
                                    f"ocr_s={outcome.page_metadata.get('ocr_seconds', 0.0)} "
                                    f"translate_s={outcome.page_metadata.get('translate_seconds', 0.0)} "
                                    f"api_calls={outcome.page_metadata.get('api_calls_count', 0)} "
                                    f"tokens={outcome.page_metadata.get('total_tokens', 0)} "
                                    f"cost={outcome.page_metadata.get('estimated_cost', None)}"
                                )
                            self._progress(done_count, selection_page_count, f"Page {page_number} finished")
                        else:
                            self._log(
                                f"page={page_number} image_used={outcome.image_used} "
                                f"retry_used={outcome.retry_used} status=failed"
                            )
                            with state_lock:
                                mark_page_failed(
                                    run_state,
                                    page_number,
                                    image_used=outcome.image_used,
                                    retry_used=outcome.retry_used,
                                    usage=outcome.usage,
                                    error=outcome.error or "unknown_failure",
                                    metadata=outcome.page_metadata,
                                )
                                if failed_page is None:
                                    run_state.halt_reason = (
                                        f"Hard failure at page {page_number}: {outcome.error or 'unknown_failure'}"
                                    )
                                save_run_state_atomic(paths.run_state_path, run_state)
                                done_count = run_state.done_count
                            if failed_page is None:
                                failed_page = page_number
                                compliance_failure = outcome.error == "compliance_failure"
                                halt_reason = (
                                    f"Hard failure at page {page_number}: {outcome.error or 'unknown_failure'}"
                                )
                                stop_submitting = True
                            self._record_event(
                                event_type="page_failed",
                                stage="page",
                                page_index=page_number,
                                duration_ms=float((outcome.page_metadata or {}).get("wall_seconds", 0.0) or 0.0)
                                * 1000.0,
                                error=outcome.error or "unknown_failure",
                                counters={
                                    "api_calls_count": int((outcome.page_metadata or {}).get("api_calls_count", 0) or 0),
                                    "transport_retries_count": int(
                                        (outcome.page_metadata or {}).get("transport_retries_count", 0) or 0
                                    ),
                                    "backoff_wait_seconds_total": float(
                                        (outcome.page_metadata or {}).get("backoff_wait_seconds_total", 0.0) or 0.0
                                    ),
                                    "total_tokens": int((outcome.page_metadata or {}).get("total_tokens", 0) or 0),
                                },
                                decisions={
                                    "source_route": str((outcome.page_metadata or {}).get("source_route", "") or ""),
                                    "image_used": bool(outcome.image_used),
                                    "retry_used": bool(outcome.retry_used),
                                },
                            )
                            self._progress(done_count, selection_page_count, f"Page {page_number} failed")

                    if not stop_submitting and not self._cancel_event.is_set():
                        while len(futures) < worker_count:
                            if not _submit_next(executor):
                                break

        self._last_state = run_state
        completed_pages = run_state.done_count

        if failed_page is None and not self._cancel_event.is_set() and run_state.failed_count == 0:
            try:
                docx_started = time.perf_counter()
                output_docx = assemble_docx(
                    paths.pages_dir,
                    paths.final_docx_path,
                    lang=config.target_lang,
                    page_breaks=config.page_breaks,
                    strip_bidi_controls=config.strip_bidi_controls,
                )
                self._run_stage_timings_ms["docx_rebuild"] = round((time.perf_counter() - docx_started) * 1000.0, 3)
            except Exception as exc:  # noqa: BLE001
                self._run_stage_timings_ms["docx_rebuild"] = round((time.perf_counter() - docx_started) * 1000.0, 3)
                self._run_stage_timings_ms["run_total"] = round((time.perf_counter() - run_started_perf) * 1000.0, 3)
                with state_lock:
                    run_state.run_status = "docx_write_failed"
                    run_state.finished_at = self._utc_now()
                    run_state.final_docx_path_abs = None
                    run_state.halt_reason = "docx_write_failed"
                    save_run_state_atomic(paths.run_state_path, run_state)
                run_summary_path = self._write_run_summary(
                    config=config,
                    paths=paths,
                    run_state=run_state,
                )
                self._log(f"DOCX save failed at {paths.final_docx_path}: {exc}")
                self._record_event(
                    event_type="run_failed",
                    stage="run",
                    error="docx_write_failed",
                    details={"attempted_output_docx": str(paths.final_docx_path)},
                )
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
                    run_summary_path=run_summary_path,
                )

            with state_lock:
                record_final_docx_path(run_state, output_docx)
                run_state.run_status = "completed"
                run_state.finished_at = self._utc_now()
                run_state.halt_reason = None
                save_run_state_atomic(paths.run_state_path, run_state)
            self._run_stage_timings_ms["run_total"] = round((time.perf_counter() - run_started_perf) * 1000.0, 3)
            run_summary_path = self._write_run_summary(
                config=config,
                paths=paths,
                run_state=run_state,
            )
            self._record_event(
                event_type="run_completed",
                stage="run",
                details={
                    "output_docx": str(output_docx),
                    "completed_pages": int(completed_pages),
                },
            )
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
                run_summary_path=run_summary_path,
            )

        partial_docx = None
        if completed_pages > 0:
            partial_docx = self.export_partial_docx()

        if self._cancel_event.is_set():
            self._run_stage_timings_ms["run_total"] = round((time.perf_counter() - run_started_perf) * 1000.0, 3)
            with state_lock:
                run_state.run_status = "cancelled"
                run_state.finished_at = self._utc_now()
                if run_state.halt_reason is None:
                    run_state.halt_reason = "cancelled_by_user"
                save_run_state_atomic(paths.run_state_path, run_state)
            run_summary_path = self._write_run_summary(
                config=config,
                paths=paths,
                run_state=run_state,
            )
            self._record_event(
                event_type="run_cancelled",
                stage="run",
                details={"completed_pages": int(completed_pages)},
            )
            return RunSummary(
                success=False,
                exit_code=2,
                output_docx=None,
                partial_docx=partial_docx,
                run_dir=paths.run_dir,
                completed_pages=completed_pages,
                failed_page=failed_page,
                error="cancelled",
                run_summary_path=run_summary_path,
            )

        with state_lock:
            run_state.run_status = "compliance_failure" if compliance_failure else "runtime_failure"
            run_state.finished_at = self._utc_now()
            run_state.halt_reason = halt_reason or run_state.halt_reason or "hard_failure"
            save_run_state_atomic(paths.run_state_path, run_state)
        self._run_stage_timings_ms["run_total"] = round((time.perf_counter() - run_started_perf) * 1000.0, 3)
        run_summary_path = self._write_run_summary(
            config=config,
            paths=paths,
            run_state=run_state,
        )
        self._record_event(
            event_type="run_failed",
            stage="run",
            error="compliance_failure" if compliance_failure else "runtime_failure",
            details={
                "failed_page": failed_page,
                "completed_pages": int(completed_pages),
            },
        )
        return RunSummary(
            success=False,
            exit_code=3 if compliance_failure else 2,
            output_docx=None,
            partial_docx=partial_docx,
            run_dir=paths.run_dir,
            completed_pages=completed_pages,
            failed_page=failed_page,
            error="compliance_failure" if compliance_failure else "runtime_failure",
            run_summary_path=run_summary_path,
        )

    def analyze(self, config: RunConfig) -> AnalyzeSummary:
        config = self._normalize_config(config)
        self._validate_config(config)

        total_pages = get_page_count(config.pdf_path)
        selected_pages = resolve_page_selection(
            total_pages,
            config.start_page,
            config.end_page,
            config.max_pages,
        )
        if not selected_pages:
            raise ValueError("No pages selected for analysis.")

        paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
        ensure_run_dirs(paths)
        self._last_config = config
        self._last_paths = paths

        rows: list[dict[str, object]] = []
        pages_would_attach_images = 0
        for page_number in selected_pages:
            ordered = extract_ordered_page_text(config.pdf_path, page_number - 1)
            extracted_text = ordered.text
            would_attach_image = should_include_image(
                config.image_mode,
                extracted_text,
                ordered.extraction_failed,
                ordered.fragmented,
                lang=config.target_lang,
            )
            if would_attach_image:
                pages_would_attach_images += 1
            rows.append(
                {
                    "page_number": page_number,
                    "extracted_text_chars": len(extracted_text),
                    "newline_to_char_ratio": float(ordered.newline_to_char_ratio),
                    "blocks_count": int(ordered.block_count),
                    "two_column_detected": bool(ordered.two_column_detected),
                    "would_attach_image": would_attach_image,
                    "reason": self._analyze_image_reason(
                        lang=config.target_lang,
                        mode=config.image_mode.value,
                        extraction_failed=ordered.extraction_failed,
                        ordered_text=extracted_text,
                        fragmented=ordered.fragmented,
                        would_attach_image=would_attach_image,
                    ),
                }
            )

        payload = {
            "run_id": paths.run_started_at,
            "pdf_path": str(config.pdf_path),
            "lang": config.target_lang.value,
            "image_mode": config.image_mode.value,
            "selected_pages_count": len(selected_pages),
            "pages_would_attach_images": pages_would_attach_images,
            "pages": rows,
        }
        analyze_report_path = paths.run_dir / "analyze_report.json"
        tmp_path = analyze_report_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(analyze_report_path)
        return AnalyzeSummary(
            run_dir=paths.run_dir,
            analyze_report_path=analyze_report_path,
            selected_pages_count=len(selected_pages),
            pages_would_attach_images=pages_would_attach_images,
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
            strip_bidi_controls=config.strip_bidi_controls,
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
            strip_bidi_controls=self._last_config.strip_bidi_controls,
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
        started_monotonic = time.perf_counter()
        started_at_iso = self._utc_now()
        extract_started = time.perf_counter()
        ordered = extract_ordered_page_text(config.pdf_path, page_number - 1)
        extract_seconds = time.perf_counter() - extract_started
        extracted_text = ordered.text
        extracted_usable = self._is_usable_source_text(extracted_text)
        extracted_lines = len([line for line in extracted_text.splitlines() if line.strip()])

        page_metadata: dict[str, object] = {
            "started_at_iso": started_at_iso,
            "ended_at_iso": "",
            "wall_seconds": 0.0,
            "attempt1_effort": "",
            "attempt2_effort": "",
            "image_mode": config.image_mode.value,
            "image_detail": "",
            "image_bytes": 0,
            "image_width_px": 0,
            "image_height_px": 0,
            "image_format": "",
            "image_compress_steps": 0,
            "extracted_text_chars": len(extracted_text),
            "extracted_text_lines": extracted_lines,
            "extract_seconds": round(extract_seconds, 3),
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
            "newline_to_char_ratio": float(ordered.newline_to_char_ratio),
            "ordered_blocks_count": int(ordered.block_count),
            "header_blocks_count": int(ordered.header_blocks_count),
            "footer_blocks_count": int(ordered.footer_blocks_count),
            "barcode_blocks_count": int(ordered.barcode_blocks_count),
            "body_blocks_count": int(ordered.body_blocks_count),
            "two_column_detected": bool(ordered.two_column_detected),
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
        api_calls_count = 0

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
            ocr_started = time.perf_counter()
            ocr_result = ocr_pdf_page_text(
                config.pdf_path,
                page_number,
                mode=OcrMode.ALWAYS,
                engine=ocr_engine,
                prefer_header=False,
                lang_hint=config.target_lang.value,
            )
            page_metadata["ocr_seconds"] = round(time.perf_counter() - ocr_started, 3)

        source_text = ocr_result.text if ocr_result.chars > 0 else extracted_text
        source_route = "ocr" if ocr_result.chars > 0 else "direct_text"
        source_route_reason = "direct_text_default"
        if ocr_result.chars > 0:
            source_route_reason = "ocr_success"
        elif should_ocr and ocr_attempted:
            source_route_reason = f"ocr_fallback:{ocr_result.failed_reason or 'empty_result'}"
        elif should_ocr and ocr_engine is None:
            source_route_reason = "ocr_requested_engine_unavailable"
            ocr_result.failed_reason = "ocr_engine_unavailable"
        elif config.ocr_mode == OcrMode.AUTO and extracted_usable:
            source_route_reason = "direct_text_usable"
        page_metadata["source_route"] = source_route
        page_metadata["source_route_reason"] = source_route_reason
        page_metadata["ocr_requested"] = bool(should_ocr)
        page_metadata["ocr_used"] = bool(ocr_result.chars > 0)
        page_metadata["ocr_provider_configured"] = bool(ocr_engine is not None)
        page_metadata["ocr_engine_used"] = ocr_result.engine
        page_metadata["ocr_failed_reason"] = ocr_result.failed_reason or ""

        if should_ocr and ocr_engine is None:
            warning_message = (
                "OCR provider not configured for OCR-requested pages; "
                "continuing with direct text route where possible."
            )
            should_warn = False
            with self._ocr_unavailable_lock:
                if not self._ocr_unavailable_warned:
                    self._ocr_unavailable_warned = True
                    should_warn = True
            if should_warn:
                self._log(warning_message)
                self._record_event(
                    event_type="ocr_engine_unavailable",
                    stage="ocr",
                    page_index=page_number,
                    warning=warning_message,
                    decisions={
                        "ocr_mode": config.ocr_mode.value,
                        "ocr_engine_policy": config.ocr_engine.value,
                        "source_route_reason": source_route_reason,
                    },
                )

        self._record_event(
            event_type="page_source_route",
            stage="extract",
            page_index=page_number,
            duration_ms=extract_seconds * 1000.0,
            decisions={
                "route": source_route,
                "reason": source_route_reason,
                "ocr_engine": ocr_result.engine,
                "ocr_chars": int(ocr_result.chars),
            },
        )

        if config.target_lang == TargetLang.AR:
            source_text = pretokenize_arabic_source(source_text)

        image_used = should_include_image(
            config.image_mode,
            extracted_text,
            ordered.extraction_failed,
            ordered.fragmented,
            lang=config.target_lang,
        )
        image_decision_reason = self._analyze_image_reason(
            lang=config.target_lang,
            mode=config.image_mode.value,
            extraction_failed=ordered.extraction_failed,
            ordered_text=extracted_text,
            fragmented=ordered.fragmented,
            would_attach_image=image_used,
        )
        page_metadata["image_decision_reason"] = image_decision_reason
        short_or_failed = ordered.extraction_failed or len(extracted_text.strip()) < 20
        image_detail = "low"
        if short_or_failed and config.image_mode in (ImageMode.AUTO, ImageMode.ALWAYS):
            image_detail = "high"

        image_data_url = None
        rendered_image = None
        if image_used:
            image_path = paths.images_dir / f"page_{page_number:04d}.jpg" if config.keep_intermediates else None
            image_cap_bytes = self._image_cap_for_lang(config.target_lang)
            rendered_image = render_page_image_data_url(
                config.pdf_path,
                page_number - 1,
                save_path=image_path,
                max_data_url_bytes=image_cap_bytes,
            )
            image_data_url = rendered_image.data_url
            page_metadata["image_detail"] = image_detail
            page_metadata["image_format"] = rendered_image.image_format
            page_metadata["image_bytes"] = int(rendered_image.encoded_bytes)
            page_metadata["image_width_px"] = int(rendered_image.width_px)
            page_metadata["image_height_px"] = int(rendered_image.height_px)
            page_metadata["image_compress_steps"] = int(rendered_image.compress_steps)
        else:
            page_metadata["image_detail"] = ""
        self._record_event(
            event_type="page_image_decision",
            stage="image",
            page_index=page_number,
            decisions={
                "image_mode": config.image_mode.value,
                "image_used": bool(image_used),
                "reason": image_decision_reason,
                "image_detail": image_detail if image_used else "",
            },
        )

        attempt1_effort = self._resolve_attempt1_effort(
            config=config,
            image_used=image_used,
            ordered_text_chars=len(extracted_text.strip()),
        )
        page_metadata["attempt1_effort"] = attempt1_effort.value

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
        def _finalize_page_metadata() -> None:
            page_metadata["api_calls_count"] = int(api_calls_count)
            page_metadata["translate_seconds"] = round(
                float(page_metadata.get("attempt1_seconds", 0.0) or 0.0)
                + float(page_metadata.get("attempt2_seconds", 0.0) or 0.0),
                3,
            )
            page_metadata["estimated_cost"] = self._estimate_cost_if_available(
                total_input_tokens=int(page_metadata.get("input_tokens", 0) or 0),
                total_output_tokens=int(page_metadata.get("output_tokens", 0) or 0),
                total_reasoning_tokens=int(page_metadata.get("reasoning_tokens", 0) or 0),
            )
            page_metadata["ended_at_iso"] = self._utc_now()
            page_metadata["wall_seconds"] = round(time.perf_counter() - started_monotonic, 3)

        attempt1_started = time.perf_counter()
        try:
            initial = client.create_page_response(
                instructions=instructions,
                prompt_text=prompt_text,
                effort=attempt1_effort.value,
                image_data_url=image_data_url,
                image_detail=str(page_metadata["image_detail"] or "low"),
            )
            page_metadata["attempt1_seconds"] = round(time.perf_counter() - attempt1_started, 3)
            api_calls_count += 1
        except ApiCallError as exc:
            page_metadata["attempt1_seconds"] = round(time.perf_counter() - attempt1_started, 3)
            api_calls_count += 1
            page_metadata["status_code"] = exc.status_code
            page_metadata["exception_class"] = exc.exception_class
            page_metadata["transport_retries_count"] = int(exc.transport_retries_count)
            page_metadata["last_backoff_seconds"] = float(exc.last_backoff_seconds)
            page_metadata["backoff_wait_seconds_total"] = float(exc.total_backoff_seconds)
            page_metadata["rate_limit_hit"] = bool(exc.rate_limit_hit)
            self._record_event(
                event_type="api_call_failed",
                stage="translate",
                page_index=page_number,
                duration_ms=float(page_metadata["attempt1_seconds"]) * 1000.0,
                counters={
                    "attempt": 1,
                    "transport_retries_count": int(exc.transport_retries_count),
                    "backoff_wait_seconds_total": float(exc.total_backoff_seconds),
                    "rate_limit_hit": bool(exc.rate_limit_hit),
                },
                error=exc.exception_class,
            )
            _finalize_page_metadata()
            return _PageOutcome(
                status=PageStatus.FAILED,
                image_used=image_used,
                retry_used=False,
                usage=usage_payload,
                error="runtime_failure",
                page_metadata=page_metadata,
            )
        usage_payload["attempt_1"] = initial.usage
        page_metadata["openai_request_id"] = initial.response_id or ""
        page_metadata["transport_retries_count"] = int(initial.transport_retries_count)
        page_metadata["last_backoff_seconds"] = float(initial.last_backoff_seconds)
        page_metadata["backoff_wait_seconds_total"] = float(initial.total_backoff_seconds)
        page_metadata["rate_limit_hit"] = bool(initial.rate_limit_hit)
        self._accumulate_usage_totals(page_metadata, initial.usage)
        self._record_event(
            event_type="api_call_done",
            stage="translate",
            page_index=page_number,
            duration_ms=float(page_metadata["attempt1_seconds"]) * 1000.0,
            counters={
                "attempt": 1,
                "input_tokens": int(initial.usage.get("input_tokens", 0) or 0),
                "output_tokens": int(initial.usage.get("output_tokens", 0) or 0),
                "reasoning_tokens": int(initial.usage.get("reasoning_tokens", 0) or 0),
                "total_tokens": int(initial.usage.get("total_tokens", 0) or 0),
                "transport_retries_count": int(initial.transport_retries_count),
                "backoff_wait_seconds_total": float(initial.total_backoff_seconds),
                "rate_limit_hit": bool(initial.rate_limit_hit),
            },
        )
        initial_eval = self._evaluate_output(initial.raw_output, config.target_lang)
        page_metadata["parser_failed"] = bool(initial_eval.parser_failed)
        page_metadata["validator_failed"] = bool(initial_eval.validator_failed)
        page_metadata["compliance_defect_outside_text"] = bool(initial_eval.outside_text)
        if initial_eval.ok and initial_eval.normalized_text is not None:
            output_path = paths.pages_dir / f"page_{page_number:04d}.txt"
            output_path.write_text(initial_eval.normalized_text, encoding="utf-8")
            _finalize_page_metadata()
            return _PageOutcome(
                status=PageStatus.DONE,
                image_used=image_used,
                retry_used=False,
                usage=usage_payload,
                error=None,
                page_metadata=page_metadata,
            )

        retry_reason = self._retry_reason_from_evaluation(
            initial_eval,
            lang=config.target_lang,
            fallback_reason=initial_eval.defect_reason,
        )
        page_metadata["retry_reason"] = retry_reason
        retry_prompt = build_retry_prompt(config.target_lang, initial.raw_output)
        retry_effort = self._resolve_retry_effort(config=config)
        page_metadata["attempt2_effort"] = retry_effort.value
        attempt2_started = time.perf_counter()
        try:
            retry = client.create_page_response(
                instructions=instructions,
                prompt_text=retry_prompt,
                effort=retry_effort.value,
                image_data_url=None,
            )
            page_metadata["attempt2_seconds"] = round(time.perf_counter() - attempt2_started, 3)
            api_calls_count += 1
        except ApiCallError as exc:
            page_metadata["attempt2_seconds"] = round(time.perf_counter() - attempt2_started, 3)
            api_calls_count += 1
            page_metadata["status_code"] = exc.status_code
            page_metadata["exception_class"] = exc.exception_class
            page_metadata["transport_retries_count"] = int(page_metadata["transport_retries_count"]) + int(
                exc.transport_retries_count
            )
            page_metadata["last_backoff_seconds"] = float(exc.last_backoff_seconds)
            page_metadata["backoff_wait_seconds_total"] = float(page_metadata["backoff_wait_seconds_total"]) + float(
                exc.total_backoff_seconds
            )
            page_metadata["rate_limit_hit"] = bool(page_metadata["rate_limit_hit"]) or bool(exc.rate_limit_hit)
            self._record_event(
                event_type="api_call_failed",
                stage="translate",
                page_index=page_number,
                duration_ms=float(page_metadata["attempt2_seconds"]) * 1000.0,
                counters={
                    "attempt": 2,
                    "transport_retries_count": int(exc.transport_retries_count),
                    "backoff_wait_seconds_total": float(exc.total_backoff_seconds),
                    "rate_limit_hit": bool(exc.rate_limit_hit),
                },
                error=exc.exception_class,
            )
            _finalize_page_metadata()
            return _PageOutcome(
                status=PageStatus.FAILED,
                image_used=image_used,
                retry_used=True,
                usage=usage_payload,
                error="runtime_failure",
                page_metadata=page_metadata,
            )
        usage_payload["attempt_2"] = retry.usage
        if not page_metadata["openai_request_id"]:
            page_metadata["openai_request_id"] = retry.response_id or ""
        page_metadata["transport_retries_count"] = int(page_metadata["transport_retries_count"]) + int(
            retry.transport_retries_count
        )
        page_metadata["last_backoff_seconds"] = float(retry.last_backoff_seconds)
        page_metadata["backoff_wait_seconds_total"] = float(page_metadata["backoff_wait_seconds_total"]) + float(
            retry.total_backoff_seconds
        )
        page_metadata["rate_limit_hit"] = bool(page_metadata["rate_limit_hit"]) or bool(retry.rate_limit_hit)
        self._accumulate_usage_totals(page_metadata, retry.usage)
        self._record_event(
            event_type="api_call_done",
            stage="translate",
            page_index=page_number,
            duration_ms=float(page_metadata["attempt2_seconds"]) * 1000.0,
            counters={
                "attempt": 2,
                "input_tokens": int(retry.usage.get("input_tokens", 0) or 0),
                "output_tokens": int(retry.usage.get("output_tokens", 0) or 0),
                "reasoning_tokens": int(retry.usage.get("reasoning_tokens", 0) or 0),
                "total_tokens": int(retry.usage.get("total_tokens", 0) or 0),
                "transport_retries_count": int(retry.transport_retries_count),
                "backoff_wait_seconds_total": float(retry.total_backoff_seconds),
                "rate_limit_hit": bool(retry.rate_limit_hit),
            },
        )
        retry_eval = self._evaluate_output(retry.raw_output, config.target_lang)
        page_metadata["parser_failed"] = bool(page_metadata["parser_failed"]) or bool(retry_eval.parser_failed)
        page_metadata["validator_failed"] = bool(page_metadata["validator_failed"]) or bool(retry_eval.validator_failed)
        page_metadata["compliance_defect_outside_text"] = bool(page_metadata["compliance_defect_outside_text"]) or bool(
            retry_eval.outside_text
        )
        if retry_eval.ok and retry_eval.normalized_text is not None:
            output_path = paths.pages_dir / f"page_{page_number:04d}.txt"
            output_path.write_text(retry_eval.normalized_text, encoding="utf-8")
            _finalize_page_metadata()
            return _PageOutcome(
                status=PageStatus.DONE,
                image_used=image_used,
                retry_used=True,
                usage=usage_payload,
                error=None,
                page_metadata=page_metadata,
            )

        defect_reason = retry_eval.defect_reason or initial_eval.defect_reason or "compliance_failure"
        page_metadata["retry_reason"] = self._retry_reason_from_evaluation(
            retry_eval,
            lang=config.target_lang,
            fallback_reason=defect_reason,
        )
        _finalize_page_metadata()
        self._log(f"Compliance failure on page {page_number}: {defect_reason}")
        return _PageOutcome(
            status=PageStatus.FAILED,
            image_used=image_used,
            retry_used=True,
            usage=usage_payload,
            error="compliance_failure",
            page_metadata=page_metadata,
        )

    def _evaluate_output(self, raw_output: str, lang: TargetLang) -> _Evaluation:
        parsed = parse_code_block_output(raw_output)
        if parsed.block_count == 0:
            return _Evaluation(
                ok=False,
                normalized_text=None,
                defect_reason="No code block in model output.",
                parser_failed=True,
                validator_failed=False,
                outside_text=False,
                block_count=0,
            )
        if parsed.block_count > 1:
            return _Evaluation(
                ok=False,
                normalized_text=None,
                defect_reason="More than one code block in model output.",
                parser_failed=True,
                validator_failed=False,
                outside_text=False,
                block_count=parsed.block_count,
            )
        if parsed.inner_content is None:
            return _Evaluation(
                ok=False,
                normalized_text=None,
                defect_reason="Missing inner code block content.",
                parser_failed=True,
                validator_failed=False,
                outside_text=False,
                block_count=1,
            )

        normalized = normalize_output_text(parsed.inner_content, lang=lang)
        if lang in (TargetLang.EN, TargetLang.FR):
            validation = validate_enfr(normalized)
        else:
            validation = validate_ar(normalized)
        if not validation.ok:
            return _Evaluation(
                ok=False,
                normalized_text=normalized,
                defect_reason=validation.reason,
                parser_failed=False,
                validator_failed=True,
                outside_text=False,
                block_count=1,
            )
        if parsed.outside_has_non_whitespace:
            return _Evaluation(
                ok=False,
                normalized_text=normalized,
                defect_reason="Non-whitespace text found outside code block.",
                parser_failed=False,
                validator_failed=False,
                outside_text=True,
                block_count=1,
            )
        return _Evaluation(
            ok=True,
            normalized_text=normalized,
            defect_reason=None,
            parser_failed=False,
            validator_failed=False,
            outside_text=False,
            block_count=1,
        )

    def _accumulate_usage_totals(self, page_metadata: dict[str, object], usage: dict[str, Any]) -> None:
        for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
            current = int(page_metadata.get(key, 0) or 0)
            try:
                increment = int(usage.get(key, 0) or 0)
            except Exception:
                increment = 0
            page_metadata[key] = current + max(0, increment)

    def _retry_reason_from_evaluation(
        self,
        evaluation: _Evaluation,
        *,
        lang: TargetLang,
        fallback_reason: str | None,
    ) -> str:
        if evaluation.outside_text:
            return "outside_text"
        if evaluation.block_count == 0:
            return "no_code_block"
        if evaluation.block_count > 1:
            return "multi_code_block"
        reason = (fallback_reason or "").strip().lower()
        if "blank line" in reason:
            return "blank_lines"
        if lang == TargetLang.AR:
            if "latin" in reason or "digit" in reason or "token" in reason or "wrapped" in reason:
                return "ar_token_violation"
        return "other"

    def _write_run_summary(
        self,
        *,
        config: RunConfig,
        paths: RunPaths,
        run_state: RunState,
    ) -> Path:
        summary_path = paths.run_dir / "run_summary.json"
        payload = self._build_run_summary_payload(config=config, paths=paths, run_state=run_state)
        tmp_path = summary_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(summary_path)
        return summary_path

    def _build_run_summary_payload(
        self,
        *,
        config: RunConfig,
        paths: RunPaths,
        run_state: RunState,
    ) -> dict[str, Any]:
        page_rows: list[tuple[int, dict[str, Any]]] = []
        for key, page in run_state.pages.items():
            try:
                page_number = int(key)
            except ValueError:
                continue
            if isinstance(page, dict):
                page_rows.append((page_number, page))
        page_rows.sort(key=lambda item: item[0])

        total_wall_seconds = sum(float(page.get("wall_seconds", 0.0) or 0.0) for _, page in page_rows)
        total_input_tokens = sum(int(page.get("input_tokens", 0) or 0) for _, page in page_rows)
        total_output_tokens = sum(int(page.get("output_tokens", 0) or 0) for _, page in page_rows)
        total_reasoning_tokens = sum(int(page.get("reasoning_tokens", 0) or 0) for _, page in page_rows)
        total_tokens = sum(int(page.get("total_tokens", 0) or 0) for _, page in page_rows)

        pages_with_images = sum(1 for _, page in page_rows if bool(page.get("image_used", False)))
        pages_with_retries = sum(1 for _, page in page_rows if bool(page.get("retry_used", False)))
        pages_failed = sum(
            1 for _, page in page_rows if str(page.get("status", "")).strip().lower() == PageStatus.FAILED.value
        )
        rate_limit_hits = sum(1 for _, page in page_rows if bool(page.get("rate_limit_hit", False)))
        transport_retries_total = sum(int(page.get("transport_retries_count", 0) or 0) for _, page in page_rows)
        ocr_requested_pages = sum(1 for _, page in page_rows if bool(page.get("ocr_requested", False)))
        ocr_used_pages = sum(
            1
            for _, page in page_rows
            if bool(page.get("ocr_used", False)) or str(page.get("source_route", "")).strip().lower() == "ocr"
        )
        ocr_requested = config.ocr_mode == OcrMode.ALWAYS or ocr_requested_pages > 0
        if config.ocr_mode == OcrMode.OFF:
            ocr_requested = False
        ocr_used = ocr_used_pages > 0
        ocr_provider_configured = bool(self._ocr_provider_configured) if config.ocr_mode != OcrMode.OFF else False

        slowest = sorted(page_rows, key=lambda item: float(item[1].get("wall_seconds", 0.0) or 0.0), reverse=True)[:10]
        top_reasoning = sorted(
            page_rows,
            key=lambda item: int(item[1].get("reasoning_tokens", 0) or 0),
            reverse=True,
        )[:10]

        def _row(page_number: int, page: dict[str, Any]) -> dict[str, Any]:
            return {
                "page_number": page_number,
                "wall_seconds": float(page.get("wall_seconds", 0.0) or 0.0),
                "reasoning_tokens": int(page.get("reasoning_tokens", 0) or 0),
                "image_bytes": int(page.get("image_bytes", 0) or 0),
                "retry_used": bool(page.get("retry_used", False)),
            }

        selected_pages_count = int(run_state.selection_page_count or len(page_rows))
        avg_image_bytes = 0.0
        if pages_with_images > 0:
            avg_image_bytes = (
                sum(int(page.get("image_bytes", 0) or 0) for _, page in page_rows if bool(page.get("image_used", False)))
                / float(pages_with_images)
            )

        effort_policy = self._resolve_effort_policy_label(config)
        suspected_cause, evidence = self._classify_suspected_cause(
            selected_pages_count=selected_pages_count,
            pages_with_images=pages_with_images,
            avg_image_bytes=avg_image_bytes,
            total_reasoning_tokens=total_reasoning_tokens,
            total_tokens=total_tokens,
            effort_policy=effort_policy,
            pages_with_retries=pages_with_retries,
            rate_limit_hits=rate_limit_hits,
            transport_retries_total=transport_retries_total,
        )

        total_cost_estimate = self._estimate_cost_if_available(
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_reasoning_tokens=total_reasoning_tokens,
        )

        payload: dict[str, Any] = {
            "run_id": run_state.run_started_at or paths.run_started_at,
            "pdf_path": str(config.pdf_path),
            "lang": config.target_lang.value,
            "selected_pages_count": selected_pages_count,
            "effort_policy": effort_policy,
            "image_mode": config.image_mode.value,
            "pipeline": {
                "image_mode": config.image_mode.value,
                "ocr_mode": config.ocr_mode.value,
                "ocr_engine": config.ocr_engine.value,
                "ocr_requested": bool(ocr_requested),
                "ocr_used": bool(ocr_used),
                "ocr_provider_configured": bool(ocr_provider_configured),
                "ocr_requested_pages": int(ocr_requested_pages),
                "ocr_used_pages": int(ocr_used_pages),
            },
            "totals": {
                "total_wall_seconds": round(total_wall_seconds, 3),
                "total_cost_estimate_if_available": total_cost_estimate,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_reasoning_tokens": total_reasoning_tokens,
                "total_tokens": total_tokens,
            },
            "counts": {
                "pages_with_images": pages_with_images,
                "pages_with_retries": pages_with_retries,
                "pages_failed": pages_failed,
                "rate_limit_hits": rate_limit_hits,
                "transport_retries_total": transport_retries_total,
            },
            "top_slowest_pages": [_row(page_number, page) for page_number, page in slowest],
            "top_reasoning_pages": [_row(page_number, page) for page_number, page in top_reasoning],
            "suspected_cause": suspected_cause,
            "evidence": evidence,
        }
        if self._diagnostics_admin_mode:
            api_calls_total = sum(int(page.get("api_calls_count", 0) or 0) for _, page in page_rows)
            backoff_wait_seconds_total = sum(
                float(page.get("backoff_wait_seconds_total", 0.0) or 0.0) for _, page in page_rows
            )
            extract_seconds_total = sum(float(page.get("extract_seconds", 0.0) or 0.0) for _, page in page_rows)
            ocr_seconds_total = sum(float(page.get("ocr_seconds", 0.0) or 0.0) for _, page in page_rows)
            translate_seconds_total = sum(float(page.get("translate_seconds", 0.0) or 0.0) for _, page in page_rows)
            page_rollups = [
                {
                    "page_number": page_number,
                    "status": str(page.get("status", "") or ""),
                    "source_route": str(page.get("source_route", "") or ""),
                    "source_route_reason": str(page.get("source_route_reason", "") or ""),
                    "image_used": bool(page.get("image_used", False)),
                    "image_decision_reason": str(page.get("image_decision_reason", "") or ""),
                    "ocr_requested": bool(page.get("ocr_requested", False)),
                    "ocr_used": bool(page.get("ocr_used", False)),
                    "ocr_provider_configured": bool(page.get("ocr_provider_configured", False)),
                    "ocr_engine_used": str(page.get("ocr_engine_used", "") or ""),
                    "ocr_failed_reason": str(page.get("ocr_failed_reason", "") or ""),
                    "wall_seconds": float(page.get("wall_seconds", 0.0) or 0.0),
                    "extract_seconds": float(page.get("extract_seconds", 0.0) or 0.0),
                    "ocr_seconds": float(page.get("ocr_seconds", 0.0) or 0.0),
                    "translate_seconds": float(page.get("translate_seconds", 0.0) or 0.0),
                    "api_calls_count": int(page.get("api_calls_count", 0) or 0),
                    "transport_retries_count": int(page.get("transport_retries_count", 0) or 0),
                    "backoff_wait_seconds_total": float(page.get("backoff_wait_seconds_total", 0.0) or 0.0),
                    "rate_limit_hit": bool(page.get("rate_limit_hit", False)),
                    "input_tokens": int(page.get("input_tokens", 0) or 0),
                    "output_tokens": int(page.get("output_tokens", 0) or 0),
                    "reasoning_tokens": int(page.get("reasoning_tokens", 0) or 0),
                    "total_tokens": int(page.get("total_tokens", 0) or 0),
                    "estimated_cost": page.get("estimated_cost"),
                    "exception_class": str(page.get("exception_class", "") or ""),
                    "error": str(page.get("error", "") or ""),
                    "retry_reason": str(page.get("retry_reason", "") or ""),
                }
                for page_number, page in page_rows
            ]
            payload["diagnostics"] = {
                "schema_version": "admin_diagnostics_v1",
                "stage_timings_ms": dict(self._run_stage_timings_ms),
                "api_calls_total": api_calls_total,
                "backoff_wait_seconds_total": round(backoff_wait_seconds_total, 3),
                "extract_seconds_total": round(extract_seconds_total, 3),
                "ocr_seconds_total": round(ocr_seconds_total, 3),
                "translate_seconds_total": round(translate_seconds_total, 3),
                "events_path": str(paths.run_dir / "run_events.jsonl"),
                "page_rollups": page_rollups,
            }
        currency = os.getenv("LEGALPDF_COST_CURRENCY", "").strip()
        if currency:
            payload["cost_currency"] = currency.upper()
        return payload

    def _resolve_effort_policy_label(self, config: RunConfig) -> str:
        policy = getattr(config, "effort_policy", None)
        if policy is not None:
            value = getattr(policy, "value", None)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
            if isinstance(policy, str) and policy.strip():
                return policy.strip().lower()
        return "fixed_xhigh" if config.effort == ReasoningEffort.XHIGH else "fixed_high"

    def _resolve_attempt1_effort(
        self,
        *,
        config: RunConfig,
        image_used: bool,
        ordered_text_chars: int,
    ) -> ReasoningEffort:
        policy = self._resolve_effort_policy_label(config)
        if policy == "fixed_high":
            return ReasoningEffort.HIGH
        if policy == "fixed_xhigh":
            return ReasoningEffort.XHIGH

        # Adaptive policy.
        if config.target_lang in (TargetLang.EN, TargetLang.FR):
            if (
                config.allow_xhigh_escalation
                and image_used
                and ordered_text_chars < 20
            ):
                return ReasoningEffort.XHIGH
            return ReasoningEffort.HIGH

        # AR adaptive keeps user's selected baseline but can escalate to xhigh per-page.
        base = config.effort if config.effort in (ReasoningEffort.HIGH, ReasoningEffort.XHIGH) else ReasoningEffort.HIGH
        if (
            config.allow_xhigh_escalation
            and image_used
            and ordered_text_chars < 20
        ):
            return ReasoningEffort.XHIGH
        return base

    def _resolve_retry_effort(self, *, config: RunConfig) -> ReasoningEffort:
        policy = self._resolve_effort_policy_label(config)
        if policy == "adaptive" and config.target_lang in (TargetLang.EN, TargetLang.FR):
            return ReasoningEffort.HIGH
        return ReasoningEffort.MEDIUM

    def _classify_suspected_cause(
        self,
        *,
        selected_pages_count: int,
        pages_with_images: int,
        avg_image_bytes: float,
        total_reasoning_tokens: int,
        total_tokens: int,
        effort_policy: str,
        pages_with_retries: int,
        rate_limit_hits: int,
        transport_retries_total: int,
    ) -> tuple[str, list[str]]:
        evidence: list[str] = []
        selected = max(1, selected_pages_count)
        images_ratio = pages_with_images / float(selected)
        retries_ratio = pages_with_retries / float(selected)
        reasoning_ratio = total_reasoning_tokens / float(max(1, total_tokens))
        transport_threshold = max(3, int(math.ceil(0.5 * selected)))

        if images_ratio >= 0.30 and avg_image_bytes >= 1_048_576:
            evidence.append(
                f"images_ratio={images_ratio:.3f}>=0.300 and avg_image_bytes={int(avg_image_bytes)}>=1048576"
            )
            return "image_auto_triggering", evidence
        if reasoning_ratio >= 0.60 and effort_policy == "fixed_xhigh":
            evidence.append(
                f"reasoning_ratio={reasoning_ratio:.3f}>=0.600 and effort_policy=fixed_xhigh"
            )
            return "xhigh_reasoning_tokens", evidence
        if retries_ratio >= 0.20:
            evidence.append(f"retries_ratio={retries_ratio:.3f}>=0.200")
            return "compliance_retries", evidence
        if rate_limit_hits > 0 or transport_retries_total >= transport_threshold:
            evidence.append(
                f"rate_limit_hits={rate_limit_hits}, transport_retries_total={transport_retries_total}, threshold={transport_threshold}"
            )
            return "rate_limiting", evidence
        evidence.append("no primary threshold fired")
        return "mixed_or_unknown", evidence

    def _estimate_cost_if_available(
        self,
        *,
        total_input_tokens: int,
        total_output_tokens: int,
        total_reasoning_tokens: int,
    ) -> float | None:
        input_rate = self._env_float("LEGALPDF_COST_INPUT_PER_1M")
        output_rate = self._env_float("LEGALPDF_COST_OUTPUT_PER_1M")
        reasoning_rate = self._env_float("LEGALPDF_COST_REASONING_PER_1M")
        if input_rate is None or output_rate is None or reasoning_rate is None:
            return None
        estimate = (
            (total_input_tokens / 1_000_000.0) * input_rate
            + (total_output_tokens / 1_000_000.0) * output_rate
            + (total_reasoning_tokens / 1_000_000.0) * reasoning_rate
        )
        return round(estimate, 6)

    def _env_float(self, key: str) -> float | None:
        raw = os.getenv(key, "").strip()
        if raw == "":
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    def _image_cap_for_lang(self, lang: TargetLang) -> int:
        if lang == TargetLang.AR:
            return IMAGE_MAX_DATA_URL_BYTES_AR
        return IMAGE_MAX_DATA_URL_BYTES_ENFR

    def _analyze_image_reason(
        self,
        *,
        lang: TargetLang,
        mode: str,
        extraction_failed: bool,
        ordered_text: str,
        fragmented: bool,
        would_attach_image: bool,
    ) -> str:
        if mode == "off":
            return "image_mode_off"
        if mode == "always":
            return "image_mode_always"
        if lang in (TargetLang.EN, TargetLang.FR):
            if extraction_failed:
                return "extraction_failed"
            if len(ordered_text.strip()) < 20:
                return "ordered_text_chars_lt_20"
            return "not_needed"
        if extraction_failed:
            return "extraction_failed"
        if ordered_text.strip() == "":
            return "empty_text"
        if len(ordered_text) < 40:
            return "short_text"
        ratio = ordered_text.count("\n") / max(len(ordered_text), 1)
        if ratio > 0.12 and len(ordered_text) < 1500:
            return "newline_ratio_fragmented"
        if fragmented:
            return "fragmented_blocks"
        return "not_needed" if not would_attach_image else "heuristic_triggered"

    def _resolve_paths_for_run(self, config: RunConfig) -> tuple[RunPaths, RunState | None]:
        paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
        existing = load_run_state(paths.run_state_path)
        if config.resume and existing is None and paths.run_state_path.exists():
            self._log("Existing run_state.json is unreadable; starting a new run state.")
            self._record_event(
                event_type="checkpoint_unreadable",
                stage="checkpoint",
                warning="Existing run_state.json is unreadable; starting a new run state.",
            )
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
        self._record_event(
            event_type="checkpoint_detected",
            stage="checkpoint",
            details={"run_started_at": run_started_at},
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
                self._record_event(
                    event_type="checkpoint_resume_compatible",
                    stage="checkpoint",
                    details={
                        "done_count": int(existing.done_count),
                        "failed_count": int(existing.failed_count),
                        "pending_count": int(existing.pending_count),
                    },
                )
                return existing
            self._record_event(
                event_type="checkpoint_resume_incompatible",
                stage="checkpoint",
                error=mismatch_reason,
            )
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
            effort_policy=config.effort_policy,
            allow_xhigh_escalation=config.allow_xhigh_escalation,
            image_mode=config.image_mode,
            start_page=config.start_page,
            end_page=config.end_page,
            max_pages=config.max_pages,
            workers=max(1, min(6, int(config.workers))),
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
            diagnostics_admin_mode=bool(config.diagnostics_admin_mode),
            diagnostics_include_sanitized_snippets=bool(config.diagnostics_include_sanitized_snippets),
            strip_bidi_controls=bool(config.strip_bidi_controls),
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
        if config.workers < 1 or config.workers > 6:
            raise ValueError("workers must be between 1 and 6.")
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

    def _record_event(
        self,
        *,
        event_type: str,
        stage: str,
        page_index: int | None = None,
        duration_ms: float | None = None,
        counters: dict[str, Any] | None = None,
        decisions: dict[str, Any] | None = None,
        warning: str | None = None,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        collector = self._event_collector
        if collector is None:
            return
        collector.add_event(
            event_type=event_type,
            stage=stage,
            page_index=page_index,
            duration_ms=duration_ms,
            counters=counters,
            decisions=decisions,
            warning=warning,
            error=error,
            details=details,
        )

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
    page_metadata: dict[str, object] | None = None
