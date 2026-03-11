"""Worker objects for running workflow tasks in Qt threads."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import fitz
from PySide6.QtCore import QObject, Signal, Slot

from legalpdf_translate.gmail_batch import (
    GmailAttachmentDownloadRequest,
    GmailAttachmentCandidate,
    GmailAttachmentSelection,
    GmailInterpretationSession,
    GmailBatchSession,
    GmailMessageLoadResult,
    FetchedGmailMessage,
    download_gmail_attachment_via_gog,
    load_gmail_message_from_intake,
    prepare_gmail_batch_session,
    prepare_gmail_interpretation_session,
)
from legalpdf_translate.gmail_intake import InboundMailContext
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.queue_runner import (
    QueueRunCancelled,
    queue_result_from_run_summary,
    run_queue_manifest,
)
from legalpdf_translate.source_document import (
    get_source_page_count,
    is_pdf_source,
    render_source_page_image_data_url,
)
from legalpdf_translate.types import RunConfig
from legalpdf_translate.workflow import TranslationWorkflow

_PAGE_LOG_RE = re.compile(
    r"page=(?P<page>\d+)\s+image_used=(?P<image>True|False)\s+retry_used=(?P<retry>True|False)\s+status=(?P<status>[a-z_]+)"
)
_PAGE_STATUS_RE = re.compile(r"Page\s+(?P<page>\d+)\s+(?P<status>finished|failed)", re.IGNORECASE)
_PREVIEW_RENDER_START_DPI = 110
_PREVIEW_RENDER_MAX_DPI = 144
_PREVIEW_RENDER_MAX_BYTES = 900_000


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
                    raise QueueRunCancelled("queue_cancelled_by_user")
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


class GmailMessageLoadWorker(QObject):
    """Fetch the exact Gmail message and supported attachments without blocking Qt."""

    log = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        *,
        context: InboundMailContext,
        configured_gog_path: str,
        configured_account_email: str,
    ) -> None:
        super().__init__()
        self._context = context
        self._configured_gog_path = configured_gog_path
        self._configured_account_email = configured_account_email

    @Slot()
    def run(self) -> None:
        try:
            self.log.emit("Gmail intake: checking gog access for the exact message.")
            result = load_gmail_message_from_intake(
                intake_context=self._context,
                configured_gog_path=self._configured_gog_path,
                configured_account_email=self._configured_account_email,
            )
            self.log.emit(result.status_message)
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class GmailBatchPrepareWorker(QObject):
    """Download the selected Gmail attachments into a batch temp folder."""

    log = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        *,
        context: InboundMailContext,
        message: FetchedGmailMessage,
        gog_path: Path,
        account_email: str,
        selected_attachments: tuple[GmailAttachmentSelection, ...],
        selected_target_lang: str,
        effective_output_dir: Path,
        cached_preview_paths: dict[str, Path] | None = None,
        cached_preview_page_counts: dict[str, int] | None = None,
    ) -> None:
        super().__init__()
        self._context = context
        self._message = message
        self._gog_path = gog_path
        self._account_email = account_email
        self._selected_attachments = selected_attachments
        self._selected_target_lang = selected_target_lang
        self._effective_output_dir = effective_output_dir
        self._cached_preview_paths = cached_preview_paths or {}
        self._cached_preview_page_counts = cached_preview_page_counts or {}

    @Slot()
    def run(self) -> None:
        try:
            self.log.emit(
                "Gmail intake: preparing "
                f"{len(self._selected_attachments)} attachment(s) into a batch temp folder."
            )
            session = prepare_gmail_batch_session(
                intake_context=self._context,
                message=self._message,
                gog_path=self._gog_path,
                account_email=self._account_email,
                selected_attachments=self._selected_attachments,
                selected_target_lang=self._selected_target_lang,
                effective_output_dir=self._effective_output_dir,
                cached_preview_paths=self._cached_preview_paths,
                cached_preview_page_counts=self._cached_preview_page_counts,
                log_callback=self.log.emit,
            )
            for downloaded in session.downloaded_attachments:
                if downloaded.saved_path.exists():
                    self.log.emit(
                        "Gmail intake: prepared "
                        f"{downloaded.candidate.filename} -> {downloaded.saved_path} "
                        f"(start_page={downloaded.start_page}, page_count={downloaded.page_count})"
                    )
            self.finished.emit(session)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class GmailInterpretationPrepareWorker(QObject):
    """Download one Gmail notice attachment for interpretation finalization."""

    log = Signal(str)
    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        *,
        context: InboundMailContext,
        message: FetchedGmailMessage,
        gog_path: Path,
        account_email: str,
        selected_attachment: GmailAttachmentSelection,
        effective_output_dir: Path,
        cached_preview_paths: dict[str, Path] | None = None,
        cached_preview_page_counts: dict[str, int] | None = None,
    ) -> None:
        super().__init__()
        self._context = context
        self._message = message
        self._gog_path = gog_path
        self._account_email = account_email
        self._selected_attachment = selected_attachment
        self._effective_output_dir = effective_output_dir
        self._cached_preview_paths = cached_preview_paths or {}
        self._cached_preview_page_counts = cached_preview_page_counts or {}

    @Slot()
    def run(self) -> None:
        try:
            self.log.emit(
                "Gmail intake: preparing one interpretation notice attachment into a temp folder."
            )
            session = prepare_gmail_interpretation_session(
                intake_context=self._context,
                message=self._message,
                gog_path=self._gog_path,
                account_email=self._account_email,
                selected_attachment=self._selected_attachment,
                effective_output_dir=self._effective_output_dir,
                cached_preview_paths=self._cached_preview_paths,
                cached_preview_page_counts=self._cached_preview_page_counts,
                log_callback=self.log.emit,
            )
            if session.downloaded_attachment.saved_path.exists():
                self.log.emit(
                    "Gmail intake: prepared interpretation notice "
                    f"{session.downloaded_attachment.candidate.filename} -> "
                    f"{session.downloaded_attachment.saved_path} "
                    f"(page_count={session.downloaded_attachment.page_count})"
                )
            self.finished.emit(session)
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


@dataclass(slots=True)
class GmailAttachmentPreviewBootstrapResult:
    attachment: GmailAttachmentCandidate
    local_path: Path
    page_count: int
    page_sizes: tuple[tuple[float, float], ...] = ()


@dataclass(slots=True)
class GmailAttachmentPreviewPageResult:
    attachment: GmailAttachmentCandidate
    local_path: Path
    page_count: int
    page_number: int
    image_bytes: bytes
    image_format: str
    width_px: int
    height_px: int


def _gmail_preview_filename(attachment: GmailAttachmentCandidate) -> str:
    source_name = Path(attachment.filename).name or "attachment"
    stem = Path(source_name).stem or "attachment"
    suffix = Path(source_name).suffix
    token = attachment.attachment_id.strip()[:8] or "preview"
    return f"{stem}_{token}{suffix}"


def _preview_page_sizes(local_path: Path) -> tuple[tuple[float, float], ...]:
    if not is_pdf_source(local_path):
        return ()
    sizes: list[tuple[float, float]] = []
    with fitz.open(local_path) as doc:
        for page_index in range(doc.page_count):
            rect = doc.load_page(page_index).rect
            sizes.append((max(1.0, float(rect.width)), max(1.0, float(rect.height))))
    return tuple(sizes)


class GmailAttachmentPreviewBootstrapWorker(QObject):
    """Download a Gmail attachment preview target and resolve its page count."""

    finished = Signal(object)
    error = Signal(str)

    def __init__(
        self,
        *,
        gog_path: Path,
        account_email: str,
        attachment: GmailAttachmentCandidate,
        preview_dir: Path,
        local_path: Path | None = None,
    ) -> None:
        super().__init__()
        self._gog_path = gog_path
        self._account_email = account_email
        self._attachment = attachment
        self._preview_dir = preview_dir
        self._local_path = local_path

    @Slot()
    def run(self) -> None:
        try:
            local_path = self._local_path.expanduser().resolve() if isinstance(self._local_path, Path) else None
            if local_path is None or not local_path.exists():
                self._preview_dir.mkdir(parents=True, exist_ok=True)
                download = download_gmail_attachment_via_gog(
                    GmailAttachmentDownloadRequest(
                        gog_path=self._gog_path,
                        account_email=self._account_email,
                        message_id=self._attachment.source_message_id,
                        attachment_id=self._attachment.attachment_id,
                        output_dir=self._preview_dir,
                        filename=_gmail_preview_filename(self._attachment),
                    )
                )
                if not download.ok or download.saved_path is None:
                    raise ValueError(
                        f"Failed to download '{self._attachment.filename}' for preview: {download.message}"
                    )
                local_path = download.saved_path.expanduser().resolve()

            page_count = int(get_source_page_count(local_path))
            if page_count <= 0:
                raise ValueError(f"Unable to determine page count for preview: {local_path}")
            self.finished.emit(
                GmailAttachmentPreviewBootstrapResult(
                    attachment=self._attachment,
                    local_path=local_path,
                    page_count=page_count,
                    page_sizes=_preview_page_sizes(local_path),
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.error.emit(str(exc))


class GmailAttachmentPreviewPageWorker(QObject):
    """Render one preview page from a locally cached Gmail attachment."""

    finished = Signal(object)
    error = Signal(int, str)

    def __init__(
        self,
        *,
        attachment: GmailAttachmentCandidate,
        local_path: Path,
        page_count: int,
        requested_page: int,
    ) -> None:
        super().__init__()
        self._attachment = attachment
        self._local_path = local_path
        self._page_count = page_count
        self._requested_page = requested_page

    @Slot()
    def run(self) -> None:
        page_number = min(max(1, int(self._requested_page)), max(1, int(self._page_count)))
        try:
            local_path = self._local_path.expanduser().resolve()
            if not local_path.exists():
                raise ValueError(f"Preview file is missing: {local_path}")
            rendered = render_source_page_image_data_url(
                local_path,
                page_number - 1,
                start_dpi=_PREVIEW_RENDER_START_DPI,
                max_dpi=_PREVIEW_RENDER_MAX_DPI,
                max_data_url_bytes=_PREVIEW_RENDER_MAX_BYTES,
            )
            self.finished.emit(
                GmailAttachmentPreviewPageResult(
                    attachment=self._attachment,
                    local_path=local_path,
                    page_count=max(1, int(self._page_count)),
                    page_number=page_number,
                    image_bytes=rendered.image_bytes,
                    image_format=rendered.image_format,
                    width_px=rendered.width_px,
                    height_px=rendered.height_px,
                )
            )
        except Exception as exc:  # noqa: BLE001
            self.error.emit(page_number, str(exc))
