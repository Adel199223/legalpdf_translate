"""Worker objects for running workflow tasks in Qt threads."""

from __future__ import annotations

import re
import threading

from PySide6.QtCore import QObject, Signal, Slot

from ..openai_client import OpenAIResponsesClient
from ..types import RunConfig
from ..workflow import TranslationWorkflow

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
