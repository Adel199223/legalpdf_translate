"""Worker objects for running workflow tasks in Qt threads."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal, Slot

from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.queue_runner import (
    queue_result_from_run_summary,
    run_queue_manifest,
)
from legalpdf_translate.types import RunConfig
from legalpdf_translate.workflow import TranslationWorkflow

_PAGE_LOG_RE = re.compile(
    r"page=(?P<page>\d+)\s+image_used=(?P<image>True|False)\s+retry_used=(?P<retry>True|False)\s+status=(?P<status>[a-z_]+)"
)
_PAGE_STATUS_RE = re.compile(r"Page\s+(?P<page>\d+)\s+(?P<status>finished|failed)", re.IGNORECASE)


class TranslationRunWorker(QObject):
    """Run a translation workflow without blocking the GUI thread."""

    log = Signal(str)
    progress = Signal(int, int, int, str, bool, bool)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        *,
        config: RunConfig,
        max_transport_retries: int,
        backoff_cap_seconds: float,
    ) -> None:
        super().__init__()
        self._config = config
        self._max_transport_retries = max_transport_retries
        self._backoff_cap_seconds = backoff_cap_seconds
        self._workflow: TranslationWorkflow | None = None
        self._page_flags: dict[int, tuple[bool, bool]] = {}
        self._flags_lock = threading.Lock()

    @property
    def workflow(self) -> TranslationWorkflow | None:
        return self._workflow

    @Slot()
    def run(self) -> None:
        def _log_callback(message: str) -> None:
            self.log.emit(message)
            match = _PAGE_LOG_RE.search(message)
            if not match:
                return
            page = int(match.group("page"))
            image_used = match.group("image") == "True"
            retry_used = match.group("retry") == "True"
            with self._flags_lock:
                self._page_flags[page] = (image_used, retry_used)

        def _progress_callback(selected_index: int, selected_total: int, status: str) -> None:
            real_page = 0
            image_used = False
            retry_used = False
            match = _PAGE_STATUS_RE.search(status)
            if match:
                real_page = int(match.group("page"))
                with self._flags_lock:
                    flags = self._page_flags.get(real_page)
                if flags is not None:
                    image_used, retry_used = flags
            self.progress.emit(selected_index, selected_total, real_page, status, image_used, retry_used)

        try:
            client = OpenAIResponsesClient(
                max_transport_retries=self._max_transport_retries,
                backoff_cap_seconds=self._backoff_cap_seconds,
                logger=_log_callback,
            )
            workflow = TranslationWorkflow(
                client=client,
                log_callback=_log_callback,
                progress_callback=_progress_callback,
            )
            self._workflow = workflow
            summary = workflow.run(self._config)
            self.finished.emit(summary)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))

    @Slot()
    def cancel(self) -> None:
        workflow = self._workflow
        if workflow is not None:
            workflow.cancel()
            self.log.emit("Cancellation requested.")


class RebuildDocxWorker(QObject):
    """Rebuild DOCX from saved pages without blocking the GUI thread."""

    log = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, *, config: RunConfig) -> None:
        super().__init__()
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            workflow = TranslationWorkflow(log_callback=self.log.emit)
            rebuilt = workflow.rebuild_docx(self._config)
            self.finished.emit(rebuilt)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class AnalyzeWorker(QObject):
    """Run analyze-only workflow path without API calls."""

    log = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, *, config: RunConfig) -> None:
        super().__init__()
        self._config = config

    @Slot()
    def run(self) -> None:
        try:
            workflow = TranslationWorkflow(log_callback=self.log.emit)
            summary = workflow.analyze(self._config)
            self.finished.emit(summary)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class QueueRunWorker(QObject):
    """Run queue-manifest jobs sequentially without blocking the GUI thread."""

    log = Signal(str)
    queue_status = Signal(object)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        *,
        manifest_path: Path,
        rerun_failed_only: bool,
        build_config: Callable[[dict[str, Any]], RunConfig],
        max_transport_retries: int,
        backoff_cap_seconds: float,
    ) -> None:
        super().__init__()
        self._manifest_path = manifest_path.expanduser().resolve()
        self._rerun_failed_only = bool(rerun_failed_only)
        self._build_config = build_config
        self._max_transport_retries = max_transport_retries
        self._backoff_cap_seconds = backoff_cap_seconds
        self._cancel_requested = False
        self._current_workflow: TranslationWorkflow | None = None

    @Slot()
    def run(self) -> None:
        try:
            def _run_job(job_payload: dict[str, Any]):
                if self._cancel_requested:
                    raise RuntimeError("queue_cancelled_by_user")
                config = self._build_config(job_payload)
                client = OpenAIResponsesClient(
                    max_transport_retries=self._max_transport_retries,
                    backoff_cap_seconds=self._backoff_cap_seconds,
                    logger=self.log.emit,
                )
                workflow = TranslationWorkflow(
                    client=client,
                    log_callback=self.log.emit,
                )
                self._current_workflow = workflow
                return queue_result_from_run_summary(workflow.run(config))

            summary = run_queue_manifest(
                manifest_path=self._manifest_path,
                run_job=_run_job,
                rerun_failed_only=self._rerun_failed_only,
                log_callback=self.log.emit,
                status_callback=lambda row: self.queue_status.emit(dict(row)),
            )
            self.finished.emit(summary)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))
        finally:
            self._current_workflow = None

    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True
        workflow = self._current_workflow
        if workflow is not None:
            workflow.cancel()
        self.log.emit("Queue cancellation requested.")
