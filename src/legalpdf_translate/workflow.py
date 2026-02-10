"""Core page-by-page translation workflow shared by CLI and GUI."""

from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .arabic_pre_tokenize import pretokenize_arabic_source
from .checkpoint import (
    RunPaths,
    build_run_paths,
    clear_run_dirs,
    ensure_run_dirs,
    is_resume_compatible,
    list_completed_pages,
    load_run_state,
    mark_page_done,
    mark_page_failed,
    new_run_state,
    save_run_state_atomic,
    sha256_of_bytes,
    sha256_of_file,
    sha256_of_text,
)
from .config import load_environment
from .docx_writer import assemble_docx, build_output_docx_path
from .image_io import render_page_image_data_url, should_include_image
from .openai_client import OpenAIResponsesClient
from .pdf_text_order import extract_ordered_page_text, get_page_count
from .prompt_builder import build_page_prompt, build_retry_prompt
from .resources_loader import load_system_instructions
from .types import PageStatus, ReasoningEffort, RunConfig, RunState, RunSummary, TargetLang
from .validators import parse_code_block_output, validate_ar, validate_enfr
from .output_normalize import normalize_output_text


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
        self._last_config = config
        self._last_paths = None
        self._last_state = None

        load_environment()
        self._validate_config(config)
        config.output_dir.mkdir(parents=True, exist_ok=True)
        if not config.keep_intermediates:
            self._log(
                "keep_intermediates is OFF: run artifacts will be deleted after successful export; "
                "resume/audit will not be available."
            )
        context_text, context_hash = self._resolve_context(config)

        total_pages = get_page_count(config.pdf_path)
        max_pages_effective = total_pages if config.max_pages is None else min(config.max_pages, total_pages)
        if max_pages_effective <= 0:
            raise ValueError("No pages selected for translation.")

        pdf_fingerprint = sha256_of_file(config.pdf_path)
        paths = build_run_paths(config.output_dir, config.pdf_path, config.target_lang)
        ensure_run_dirs(paths)
        self._last_paths = paths

        run_state = self._load_or_initialize_run_state(
            config=config,
            paths=paths,
            pdf_fingerprint=pdf_fingerprint,
            context_hash=context_hash,
            total_pages=total_pages,
            max_pages_effective=max_pages_effective,
        )
        self._last_state = run_state

        client = self._provided_client
        instructions = load_system_instructions(config.target_lang)

        failed_page: int | None = None
        compliance_failure = False
        for page_number in range(1, max_pages_effective + 1):
            if self._cancel_event.is_set():
                self._log("Cancellation requested; stopping before next page.")
                break
            page_state = run_state.pages.get(str(page_number))
            if config.resume and page_state and page_state.get("status") == PageStatus.DONE.value:
                self._log(f"page={page_number} image_used=False retry_used=False status=skipped")
                self._progress(page_number, max_pages_effective, "skipped (already done)")
                continue

            self._progress(page_number, max_pages_effective, "processing")
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
                self._progress(page_number, max_pages_effective, "done")
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
            self._progress(page_number, max_pages_effective, "failed")
            break

        self._last_state = run_state
        completed_pages = len(list_completed_pages(run_state))

        if failed_page is None and not self._cancel_event.is_set():
            output_docx = build_output_docx_path(config.output_dir, config.pdf_path.stem, config.target_lang)
            assemble_docx(
                paths.pages_dir,
                output_docx,
                lang=config.target_lang,
                page_breaks=config.page_breaks,
            )
            if not config.keep_intermediates:
                shutil.rmtree(paths.run_dir, ignore_errors=True)
            return RunSummary(
                success=True,
                exit_code=0,
                output_docx=output_docx,
                partial_docx=None,
                run_dir=paths.run_dir,
                completed_pages=completed_pages,
                failed_page=None,
                error=None,
            )

        partial_docx = None
        if completed_pages > 0:
            partial_docx = self.export_partial_docx()

        if self._cancel_event.is_set():
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

    def export_partial_docx(self) -> Path | None:
        if self._last_config is None or self._last_paths is None or self._last_state is None:
            return None
        completed = list_completed_pages(self._last_state)
        if not completed:
            return None
        output_docx = build_output_docx_path(
            self._last_config.output_dir,
            self._last_config.pdf_path.stem,
            self._last_config.target_lang,
            partial=True,
        )
        return assemble_docx(
            self._last_paths.pages_dir,
            output_docx,
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
    ) -> "_PageOutcome":
        ordered = extract_ordered_page_text(config.pdf_path, page_number - 1)
        source_text = ordered.text
        if config.target_lang == TargetLang.AR:
            source_text = pretokenize_arabic_source(source_text)

        image_used = should_include_image(
            config.image_mode,
            ordered_text=ordered.text,
            extraction_failed=ordered.extraction_failed,
            fragmented=ordered.fragmented,
        )
        image_data_url = None
        if image_used:
            image_path = paths.images_dir / f"page_{page_number:04d}.jpg" if config.keep_intermediates else None
            image_data_url, _ = render_page_image_data_url(
                config.pdf_path,
                page_number - 1,
                save_path=image_path,
            )

        prompt_text = build_page_prompt(
            lang=config.target_lang,
            page_number=page_number,
            total_pages=total_pages,
            source_text=source_text,
            context_text=context_text,
        )

        usage_payload: dict[str, object] = {}
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

    def _load_or_initialize_run_state(
        self,
        *,
        config: RunConfig,
        paths: RunPaths,
        pdf_fingerprint: str,
        context_hash: str,
        total_pages: int,
        max_pages_effective: int,
    ) -> RunState:
        existing = load_run_state(paths.run_state_path)
        if config.resume and existing is not None and is_resume_compatible(
            existing,
            config=config,
            pdf_fingerprint=pdf_fingerprint,
            context_hash=context_hash,
        ):
            self._log("Compatible checkpoint found. Resuming from completed pages.")
            return existing

        clear_run_dirs(paths)
        state = new_run_state(
            config=config,
            pdf_fingerprint=pdf_fingerprint,
            context_hash=context_hash,
            total_pages=total_pages,
            max_pages_effective=max_pages_effective,
        )
        save_run_state_atomic(paths.run_state_path, state)
        return state

    def _validate_config(self, config: RunConfig) -> None:
        if not config.pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {config.pdf_path}")
        if config.target_lang not in (TargetLang.EN, TargetLang.FR, TargetLang.AR):
            raise ValueError("Invalid target language.")
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

    def _log(self, message: str) -> None:
        if self._log_callback:
            self._log_callback(message)

    def _progress(self, current_page: int, total_pages: int, status: str) -> None:
        if self._progress_callback:
            self._progress_callback(current_page, total_pages, status)


@dataclass(slots=True)
class _PageOutcome:
    status: PageStatus
    image_used: bool
    retry_used: bool
    usage: dict[str, object]
    error: str | None
