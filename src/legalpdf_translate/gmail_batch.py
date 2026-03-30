"""Windows Gmail fetch helpers and batch session state via gog CLI."""

from __future__ import annotations

import json
import tempfile
from datetime import UTC, datetime
from dataclasses import dataclass, field
from pathlib import Path
from shutil import copy2
from typing import Any, Callable, Mapping, Sequence
from uuid import uuid4

from legalpdf_translate.docx_writer import resolve_noncolliding_output_path
from legalpdf_translate.gmail_draft import (
    _extract_gmail_accounts,
    _is_windows,
    _run_capture,
    _run_gog_json,
    resolve_gog_path,
)
from legalpdf_translate.gmail_intake import InboundMailContext
from legalpdf_translate.source_document import is_supported_source_file


@dataclass(frozen=True, slots=True)
class GmailAttachmentCandidate:
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int
    source_message_id: str


@dataclass(frozen=True, slots=True)
class GmailAttachmentSelection:
    candidate: GmailAttachmentCandidate
    start_page: int = 1
    page_count: int | None = None


@dataclass(frozen=True, slots=True)
class FetchedGmailMessage:
    message_id: str
    thread_id: str
    subject: str
    from_header: str
    account_email: str
    attachments: tuple[GmailAttachmentCandidate, ...]

    @classmethod
    def from_payload(
        cls,
        payload: object,
        *,
        fallback_subject: str,
        account_email: str,
    ) -> FetchedGmailMessage:
        if not isinstance(payload, dict):
            raise ValueError("Gmail message payload must be a JSON object.")
        message_id = str(payload.get("id", "") or "").strip()
        thread_id = str(payload.get("threadId", "") or "").strip()
        message_payload = payload.get("payload")
        if not message_id:
            raise ValueError("Gmail message payload is missing id.")
        if not thread_id:
            raise ValueError("Gmail message payload is missing threadId.")
        if not isinstance(message_payload, dict):
            raise ValueError("Gmail message payload is missing payload metadata.")
        subject = _header_value(message_payload, "Subject") or fallback_subject.strip()
        from_header = _header_value(message_payload, "From")
        attachments = tuple(_collect_supported_attachments(message_payload, source_message_id=message_id))
        return cls(
            message_id=message_id,
            thread_id=thread_id,
            subject=subject,
            from_header=from_header,
            account_email=account_email.strip(),
            attachments=attachments,
        )


@dataclass(frozen=True, slots=True)
class DownloadedGmailAttachment:
    candidate: GmailAttachmentCandidate
    saved_path: Path
    start_page: int = 1
    page_count: int = 1


GmailBatchConsistencySignature = tuple[str, str, str, str]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _is_pdf_attachment(candidate: GmailAttachmentCandidate) -> bool:
    filename = candidate.filename.strip().lower()
    mime_type = candidate.mime_type.strip().lower()
    return mime_type == "application/pdf" or filename.endswith(".pdf")


def _selection_page_count(
    *,
    selection: GmailAttachmentSelection,
    attachment: GmailAttachmentCandidate,
    preview_page_counts: Mapping[str, int],
) -> int | None:
    if isinstance(selection.page_count, int) and int(selection.page_count) > 0:
        return int(selection.page_count)
    cached_page_count = preview_page_counts.get(attachment.attachment_id)
    if isinstance(cached_page_count, int) and int(cached_page_count) > 0:
        return int(cached_page_count)
    if not _is_pdf_attachment(attachment):
        return 1
    return None


@dataclass(frozen=True, slots=True)
class GmailBatchConfirmedItem:
    downloaded_attachment: DownloadedGmailAttachment
    # Stored as the immutable staged copy used for Gmail draft attachments.
    translated_docx_path: Path
    run_dir: Path
    translated_word_count: int
    joblog_row_id: int
    run_id: str
    case_number: str
    case_entity: str
    case_city: str
    court_email: str

    @property
    def consistency_signature(self) -> GmailBatchConsistencySignature:
        return gmail_batch_consistency_signature(
            case_number=self.case_number,
            case_entity=self.case_entity,
            case_city=self.case_city,
            court_email=self.court_email,
        )


@dataclass(slots=True)
class GmailMessageLoadResult:
    ok: bool
    classification: str
    status_message: str
    intake_context: InboundMailContext
    gog_path: Path | None = None
    account_email: str | None = None
    accounts: tuple[str, ...] = ()
    message: FetchedGmailMessage | None = None
    stdout: str = ""
    stderr: str = ""


@dataclass(slots=True)
class GmailAttachmentDownloadRequest:
    gog_path: Path
    account_email: str
    message_id: str
    attachment_id: str
    output_dir: Path
    filename: str


@dataclass(slots=True)
class GmailAttachmentDownloadResult:
    ok: bool
    message: str
    stdout: str
    stderr: str
    saved_path: Path | None = None
    payload: dict[str, Any] | None = None


@dataclass(slots=True)
class GmailBatchSession:
    intake_context: InboundMailContext
    message: FetchedGmailMessage
    gog_path: Path
    account_email: str
    downloaded_attachments: tuple[DownloadedGmailAttachment, ...]
    download_dir: Path
    selected_target_lang: str = ""
    effective_output_dir: Path | None = None
    session_id: str = field(default_factory=lambda: f"gmail_batch_{uuid4().hex[:12]}")
    started_at: str = field(default_factory=_utc_now)
    status: str = "prepared"
    halt_reason: str = ""
    session_report_dir: Path | None = None
    session_report_path: Path | None = None
    confirmed_items: list[GmailBatchConfirmedItem] = field(default_factory=list)
    consistency_signature: GmailBatchConsistencySignature | None = None
    honorarios_requested: bool = False
    requested_honorarios_path: Path | None = None
    requested_honorarios_pdf_path: Path | None = None
    actual_honorarios_path: Path | None = None
    actual_honorarios_pdf_path: Path | None = None
    honorarios_auto_renamed: bool = False
    draft_preflight_result: str = ""
    draft_created: bool = False
    draft_failure_reason: str = ""
    final_attachment_basenames: tuple[str, ...] = ()
    pdf_export: dict[str, Any] = field(default_factory=dict)
    finalization_state: str = ""
    finalization_preflight: dict[str, Any] = field(default_factory=dict)
    _temp_dir: tempfile.TemporaryDirectory[str] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def cleanup(self) -> None:
        temp_dir = self._temp_dir
        self._temp_dir = None
        if temp_dir is not None:
            temp_dir.cleanup()


@dataclass(slots=True)
class GmailInterpretationSession:
    intake_context: InboundMailContext
    message: FetchedGmailMessage
    gog_path: Path
    account_email: str
    downloaded_attachment: DownloadedGmailAttachment
    download_dir: Path
    effective_output_dir: Path | None = None
    session_id: str = field(default_factory=lambda: f"gmail_interpretation_{uuid4().hex[:12]}")
    started_at: str = field(default_factory=_utc_now)
    status: str = "prepared"
    halt_reason: str = ""
    session_report_dir: Path | None = None
    session_report_path: Path | None = None
    honorarios_requested: bool = False
    requested_honorarios_path: Path | None = None
    requested_honorarios_pdf_path: Path | None = None
    actual_honorarios_path: Path | None = None
    actual_honorarios_pdf_path: Path | None = None
    honorarios_auto_renamed: bool = False
    draft_created: bool = False
    draft_failure_reason: str = ""
    final_attachment_basenames: tuple[str, ...] = ()
    metadata_extraction: dict[str, Any] = field(default_factory=dict)
    pdf_export: dict[str, Any] = field(default_factory=dict)
    _temp_dir: tempfile.TemporaryDirectory[str] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def cleanup(self) -> None:
        temp_dir = self._temp_dir
        self._temp_dir = None
        if temp_dir is not None:
            temp_dir.cleanup()


def gmail_batch_consistency_signature(
    *,
    case_number: str,
    case_entity: str,
    case_city: str,
    court_email: str,
) -> GmailBatchConsistencySignature:
    return (
        case_number.strip(),
        case_entity.strip(),
        case_city.strip(),
        court_email.strip(),
    )


def prepare_gmail_batch_session_report_path(
    *,
    output_dir: Path,
    session_id: str,
) -> tuple[Path, Path]:
    report_dir = output_dir.expanduser().resolve() / "_gmail_batch_sessions" / session_id
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir, report_dir / "gmail_batch_session.json"


def prepare_gmail_interpretation_session_report_path(
    *,
    output_dir: Path,
    session_id: str,
) -> tuple[Path, Path]:
    report_dir = output_dir.expanduser().resolve() / "_gmail_interpretation_sessions" / session_id
    report_dir.mkdir(parents=True, exist_ok=True)
    return report_dir, report_dir / "gmail_interpretation_session.json"


def build_gmail_batch_session_payload(session: GmailBatchSession) -> dict[str, Any]:
    run_items = [
        {
            "attachment_filename": item.downloaded_attachment.candidate.filename,
            "run_id": item.run_id,
            "run_dir": str(item.run_dir.expanduser().resolve()),
            "joblog_row_id": int(item.joblog_row_id),
            "translated_docx_basename": item.translated_docx_path.name,
        }
        for item in session.confirmed_items
    ]
    finalization: dict[str, Any] = {
        "honorarios_requested": bool(session.honorarios_requested),
        "requested_save_path": (
            str(session.requested_honorarios_path.expanduser().resolve())
            if isinstance(session.requested_honorarios_path, Path)
            else ""
        ),
        "requested_pdf_save_path": (
            str(session.requested_honorarios_pdf_path.expanduser().resolve())
            if isinstance(session.requested_honorarios_pdf_path, Path)
            else ""
        ),
        "actual_saved_path": (
            str(session.actual_honorarios_path.expanduser().resolve())
            if isinstance(session.actual_honorarios_path, Path)
            else ""
        ),
        "actual_pdf_saved_path": (
            str(session.actual_honorarios_pdf_path.expanduser().resolve())
            if isinstance(session.actual_honorarios_pdf_path, Path)
            else ""
        ),
        "auto_renamed": bool(session.honorarios_auto_renamed),
        "draft_preflight_result": session.draft_preflight_result.strip(),
        "draft_created": bool(session.draft_created),
        "draft_failure_reason": session.draft_failure_reason.strip(),
        "final_attachment_basenames": list(session.final_attachment_basenames),
        "finalization_state": session.finalization_state.strip(),
        "finalization_preflight": dict(session.finalization_preflight),
    }
    return {
        "session_id": session.session_id,
        "started_at": session.started_at,
        "status": session.status,
        "halt_reason": session.halt_reason,
        "effective_output_dir": (
            str(session.effective_output_dir.expanduser().resolve())
            if isinstance(session.effective_output_dir, Path)
            else ""
        ),
        "intake_context": {
            "message_id": session.intake_context.message_id,
            "thread_id": session.intake_context.thread_id,
            "subject": session.intake_context.subject,
            "account_email": session.intake_context.account_email or "",
            "selected_target_lang": session.selected_target_lang.strip(),
            "selected_attachment_filenames": [
                attachment.candidate.filename for attachment in session.downloaded_attachments
            ],
            "selected_attachments": [
                {
                    "filename": attachment.candidate.filename,
                    "start_page": int(attachment.start_page),
                    "page_count": int(attachment.page_count),
                }
                for attachment in session.downloaded_attachments
            ],
        },
        "runs": run_items,
        "pdf_export": dict(session.pdf_export),
        "finalization": finalization,
    }


def build_gmail_interpretation_session_payload(session: GmailInterpretationSession) -> dict[str, Any]:
    finalization: dict[str, Any] = {
        "honorarios_requested": bool(session.honorarios_requested),
        "requested_save_path": (
            str(session.requested_honorarios_path.expanduser().resolve())
            if isinstance(session.requested_honorarios_path, Path)
            else ""
        ),
        "requested_pdf_save_path": (
            str(session.requested_honorarios_pdf_path.expanduser().resolve())
            if isinstance(session.requested_honorarios_pdf_path, Path)
            else ""
        ),
        "actual_saved_path": (
            str(session.actual_honorarios_path.expanduser().resolve())
            if isinstance(session.actual_honorarios_path, Path)
            else ""
        ),
        "actual_pdf_saved_path": (
            str(session.actual_honorarios_pdf_path.expanduser().resolve())
            if isinstance(session.actual_honorarios_pdf_path, Path)
            else ""
        ),
        "auto_renamed": bool(session.honorarios_auto_renamed),
        "draft_created": bool(session.draft_created),
        "draft_failure_reason": session.draft_failure_reason.strip(),
        "final_attachment_basenames": list(session.final_attachment_basenames),
    }
    return {
        "session_id": session.session_id,
        "started_at": session.started_at,
        "status": session.status,
        "halt_reason": session.halt_reason,
        "effective_output_dir": (
            str(session.effective_output_dir.expanduser().resolve())
            if isinstance(session.effective_output_dir, Path)
            else ""
        ),
        "intake_context": {
            "message_id": session.intake_context.message_id,
            "thread_id": session.intake_context.thread_id,
            "subject": session.intake_context.subject,
            "account_email": session.intake_context.account_email or "",
            "selected_attachment_filename": session.downloaded_attachment.candidate.filename,
            "selected_attachment": {
                "filename": session.downloaded_attachment.candidate.filename,
                "start_page": int(session.downloaded_attachment.start_page),
                "page_count": int(session.downloaded_attachment.page_count),
            },
        },
        "downloaded_notice": {
            "filename": session.downloaded_attachment.candidate.filename,
            "saved_path": str(session.downloaded_attachment.saved_path.expanduser().resolve()),
        },
        "metadata_extraction": dict(session.metadata_extraction),
        "pdf_export": dict(session.pdf_export),
        "finalization": finalization,
    }


def write_gmail_batch_session_report(session: GmailBatchSession) -> Path | None:
    report_path = session.session_report_path
    if report_path is None:
        return None
    payload = build_gmail_batch_session_payload(session)
    tmp_path = report_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(report_path)
    return report_path


def write_gmail_interpretation_session_report(session: GmailInterpretationSession) -> Path | None:
    report_path = session.session_report_path
    if report_path is None:
        return None
    payload = build_gmail_interpretation_session_payload(session)
    tmp_path = report_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(report_path)
    return report_path


def stage_gmail_batch_translated_docx(
    *,
    session: GmailBatchSession,
    translated_docx_path: Path,
) -> Path:
    source = translated_docx_path.expanduser().resolve()
    if not source.exists():
        raise ValueError(f"Translated DOCX not found for Gmail batch staging: {source}")
    draft_dir = session.download_dir.expanduser().resolve() / "_draft_attachments"
    draft_dir.mkdir(parents=True, exist_ok=True)
    staged = resolve_noncolliding_output_path(draft_dir / source.name)
    copy2(source, staged)
    return staged


def load_gmail_message_from_intake(
    *,
    intake_context: InboundMailContext,
    configured_gog_path: str = "",
    configured_account_email: str = "",
) -> GmailMessageLoadResult:
    if not _is_windows():
        return GmailMessageLoadResult(
            ok=False,
            classification="unavailable",
            status_message=(
                "Windows-only feature. Gmail intake fetch is unavailable in this environment."
            ),
            intake_context=intake_context,
        )
    gog_path = resolve_gog_path(configured_gog_path=configured_gog_path)
    if gog_path is None:
        return GmailMessageLoadResult(
            ok=False,
            classification="unavailable",
            status_message=(
                "Windows gog.exe not found. Install gog on Windows or set the Gmail gog path in Settings."
            ),
            intake_context=intake_context,
        )
    clients_result = _run_gog_json(gog_path, ["auth", "credentials", "list", "--json", "--no-input"])
    if clients_result is None:
        return GmailMessageLoadResult(
            ok=False,
            classification="unavailable",
            status_message=(
                "Unable to read gog OAuth credentials. Configure Google OAuth first with "
                "`gog auth credentials set <client_secret.json>`."
            ),
            intake_context=intake_context,
            gog_path=gog_path,
        )
    clients = clients_result.get("clients", [])
    if not isinstance(clients, list) or not clients:
        return GmailMessageLoadResult(
            ok=False,
            classification="unavailable",
            status_message=(
                "No Google OAuth client credentials are configured for gog. Run "
                "`gog auth credentials set <client_secret.json>` first."
            ),
            intake_context=intake_context,
            gog_path=gog_path,
        )
    accounts_result = _run_gog_json(gog_path, ["auth", "list", "--json", "--no-input"])
    if accounts_result is None:
        return GmailMessageLoadResult(
            ok=False,
            classification="unavailable",
            status_message=(
                "Unable to read gog authenticated accounts. Run "
                "`gog auth add <your@gmail.com> --services gmail` first."
            ),
            intake_context=intake_context,
            gog_path=gog_path,
        )
    accounts = tuple(_extract_gmail_accounts(accounts_result))
    if not accounts:
        return GmailMessageLoadResult(
            ok=False,
            classification="unavailable",
            status_message=(
                "No Gmail account is authenticated in gog. Run "
                "`gog auth add <your@gmail.com> --services gmail` first."
            ),
            intake_context=intake_context,
            gog_path=gog_path,
        )
    account_email, error_message = _resolve_account_email(
        configured_account_email=configured_account_email,
        intake_account_email=intake_context.account_email or "",
        available_accounts=accounts,
    )
    if account_email is None:
        return GmailMessageLoadResult(
            ok=False,
            classification="unavailable",
            status_message=error_message,
            intake_context=intake_context,
            gog_path=gog_path,
            accounts=accounts,
        )

    cmd = [
        str(gog_path),
        "gmail",
        "get",
        intake_context.message_id,
        "--format",
        "full",
        "--json",
        "--no-input",
        "--account",
        account_email,
    ]
    completed = _run_capture(cmd)
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        return GmailMessageLoadResult(
            ok=False,
            classification="failed",
            status_message=stderr or stdout or "Failed to fetch Gmail message via gog.",
            intake_context=intake_context,
            gog_path=gog_path,
            account_email=account_email,
            accounts=accounts,
            stdout=stdout,
            stderr=stderr,
        )
    try:
        raw_payload = json.loads(stdout) if stdout else {}
    except json.JSONDecodeError:
        return GmailMessageLoadResult(
            ok=False,
            classification="failed",
            status_message="gog returned invalid JSON for the Gmail message fetch.",
            intake_context=intake_context,
            gog_path=gog_path,
            account_email=account_email,
            accounts=accounts,
            stdout=stdout,
            stderr=stderr,
        )
    try:
        payload = _extract_message_payload_from_gog_response(raw_payload)
        message = FetchedGmailMessage.from_payload(
            payload,
            fallback_subject=intake_context.subject,
            account_email=account_email,
        )
    except ValueError as exc:
        return GmailMessageLoadResult(
            ok=False,
            classification="failed",
            status_message=str(exc),
            intake_context=intake_context,
            gog_path=gog_path,
            account_email=account_email,
            accounts=accounts,
            stdout=stdout,
            stderr=stderr,
        )
    if message.message_id != intake_context.message_id:
        return GmailMessageLoadResult(
            ok=False,
            classification="failed",
            status_message=(
                "Gmail returned a different message ID than the intake request. "
                "The open message could not be confirmed exactly."
            ),
            intake_context=intake_context,
            gog_path=gog_path,
            account_email=account_email,
            accounts=accounts,
            stdout=stdout,
            stderr=stderr,
        )
    if message.thread_id != intake_context.thread_id:
        return GmailMessageLoadResult(
            ok=False,
            classification="failed",
            status_message=(
                "Gmail returned a different thread ID than the intake request. "
                "The open thread could not be confirmed exactly."
            ),
            intake_context=intake_context,
            gog_path=gog_path,
            account_email=account_email,
            accounts=accounts,
            stdout=stdout,
            stderr=stderr,
        )
    return GmailMessageLoadResult(
        ok=True,
        classification="ready",
        status_message=(
            f"Gmail intake fetch is ready for {account_email}. "
            f"Found {len(message.attachments)} supported attachment(s) in the exact message."
        ),
        intake_context=intake_context,
        gog_path=gog_path,
        account_email=account_email,
        accounts=accounts,
        message=message,
        stdout=stdout,
        stderr=stderr,
    )


def _extract_message_payload_from_gog_response(raw_payload: object) -> object:
    if isinstance(raw_payload, dict):
        nested_message = raw_payload.get("message")
        if isinstance(nested_message, dict):
            return nested_message
        return raw_payload
    if isinstance(raw_payload, list):
        raise ValueError(
            "gog returned an attachment list instead of Gmail message metadata. "
            "Retry without --results-only or update the Gmail fetch integration."
        )
    raise ValueError(
        f"Gmail message payload must be a JSON object. Received JSON {type(raw_payload).__name__}."
    )


def download_gmail_attachment_via_gog(
    request: GmailAttachmentDownloadRequest,
) -> GmailAttachmentDownloadResult:
    output_dir = request.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(request.gog_path.expanduser().resolve()),
        "gmail",
        "attachment",
        request.message_id,
        request.attachment_id,
        "--json",
        "--no-input",
        "--account",
        request.account_email.strip(),
        "--out",
        str(output_dir),
        "--name",
        request.filename,
    ]
    completed = _run_capture(cmd)
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    payload: dict[str, Any] | None = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
    if completed.returncode != 0:
        return GmailAttachmentDownloadResult(
            ok=False,
            message=stderr or stdout or "Failed to download Gmail attachment via gog.",
            stdout=stdout,
            stderr=stderr,
            payload=payload,
        )
    saved_path = _resolve_downloaded_path(output_dir=output_dir, filename=request.filename, payload=payload)
    if saved_path is None or not saved_path.exists():
        return GmailAttachmentDownloadResult(
            ok=False,
            message="Attachment download completed, but the saved file path could not be confirmed.",
            stdout=stdout,
            stderr=stderr,
            payload=payload,
        )
    return GmailAttachmentDownloadResult(
        ok=True,
        message="Attachment downloaded successfully.",
        stdout=stdout,
        stderr=stderr,
        saved_path=saved_path,
        payload=payload,
    )


def prepare_gmail_batch_session(
    *,
    intake_context: InboundMailContext,
    message: FetchedGmailMessage,
    gog_path: Path,
    account_email: str,
    selected_attachments: Sequence[GmailAttachmentSelection],
    selected_target_lang: str,
    effective_output_dir: Path,
    cached_preview_paths: Mapping[str, Path] | None = None,
    cached_preview_page_counts: Mapping[str, int] | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> GmailBatchSession:
    def _log(message: str) -> None:
        if callable(log_callback):
            log_callback(message)

    selected = tuple(selected_attachments)
    if not selected:
        raise ValueError("Select at least one Gmail attachment before continuing.")
    allowed_ids = {attachment.attachment_id for attachment in message.attachments}
    for selection in selected:
        attachment = selection.candidate
        if attachment.attachment_id not in allowed_ids:
            raise ValueError(
                f"The Gmail attachment '{attachment.filename}' is not available in the fetched message."
            )
        if int(selection.start_page) <= 0:
            raise ValueError(
                f"Start page must be >= 1 for Gmail attachment '{attachment.filename}'."
            )

    temp_dir = tempfile.TemporaryDirectory(prefix="legalpdf_gmail_batch_")
    download_dir = Path(temp_dir.name).expanduser().resolve()
    preview_paths = dict(cached_preview_paths or {})
    preview_page_counts = dict(cached_preview_page_counts or {})
    downloads: list[DownloadedGmailAttachment] = []
    used_names: set[str] = set()
    try:
        for selection in selected:
            downloads.append(
                _prepare_downloaded_attachment(
                    selection=selection,
                    gog_path=gog_path,
                    account_email=account_email,
                    download_dir=download_dir,
                    used_names=used_names,
                    preview_paths=preview_paths,
                    preview_page_counts=preview_page_counts,
                    log_callback=_log,
                )
            )
    except Exception:
        temp_dir.cleanup()
        raise

    session_id = f"gmail_batch_{uuid4().hex[:12]}"
    report_dir, report_path = prepare_gmail_batch_session_report_path(
        output_dir=effective_output_dir,
        session_id=session_id,
    )
    session = GmailBatchSession(
        intake_context=intake_context,
        message=message,
        gog_path=gog_path.expanduser().resolve(),
        account_email=account_email.strip(),
        downloaded_attachments=tuple(downloads),
        download_dir=download_dir,
        selected_target_lang=selected_target_lang.strip().upper(),
        effective_output_dir=effective_output_dir.expanduser().resolve(),
        session_id=session_id,
        session_report_dir=report_dir,
        session_report_path=report_path,
        _temp_dir=temp_dir,
    )
    write_gmail_batch_session_report(session)
    return session


def prepare_gmail_interpretation_session(
    *,
    intake_context: InboundMailContext,
    message: FetchedGmailMessage,
    gog_path: Path,
    account_email: str,
    selected_attachment: GmailAttachmentSelection,
    effective_output_dir: Path,
    cached_preview_paths: Mapping[str, Path] | None = None,
    cached_preview_page_counts: Mapping[str, int] | None = None,
    log_callback: Callable[[str], None] | None = None,
) -> GmailInterpretationSession:
    def _log(message_text: str) -> None:
        if callable(log_callback):
            log_callback(message_text)

    attachment = selected_attachment.candidate
    allowed_ids = {candidate.attachment_id for candidate in message.attachments}
    if attachment.attachment_id not in allowed_ids:
        raise ValueError(
            f"The Gmail attachment '{attachment.filename}' is not available in the fetched message."
        )

    temp_dir = tempfile.TemporaryDirectory(prefix="legalpdf_gmail_interpretation_")
    download_dir = Path(temp_dir.name).expanduser().resolve()
    try:
        downloaded_attachment = _prepare_downloaded_attachment(
            selection=selected_attachment,
            gog_path=gog_path,
            account_email=account_email,
            download_dir=download_dir,
            used_names=set(),
            preview_paths=dict(cached_preview_paths or {}),
            preview_page_counts=dict(cached_preview_page_counts or {}),
            log_callback=_log,
        )
    except Exception:
        temp_dir.cleanup()
        raise

    session_id = f"gmail_interpretation_{uuid4().hex[:12]}"
    report_dir, report_path = prepare_gmail_interpretation_session_report_path(
        output_dir=effective_output_dir,
        session_id=session_id,
    )
    session = GmailInterpretationSession(
        intake_context=intake_context,
        message=message,
        gog_path=gog_path.expanduser().resolve(),
        account_email=account_email.strip(),
        downloaded_attachment=downloaded_attachment,
        download_dir=download_dir,
        effective_output_dir=effective_output_dir.expanduser().resolve(),
        session_id=session_id,
        session_report_dir=report_dir,
        session_report_path=report_path,
        _temp_dir=temp_dir,
    )
    write_gmail_interpretation_session_report(session)
    return session


def _resolve_account_email(
    *,
    configured_account_email: str,
    intake_account_email: str,
    available_accounts: Sequence[str],
) -> tuple[str | None, str]:
    configured = configured_account_email.strip()
    intake = intake_account_email.strip()
    accounts = tuple(str(account).strip() for account in available_accounts if str(account).strip())
    if configured:
        if configured in accounts:
            return configured, ""
        return (
            None,
            f"The configured Gmail account '{configured}' is not available in gog. "
            "Use Settings to pick an authenticated Gmail account.",
        )
    if intake and intake in accounts:
        return intake, ""
    if len(accounts) == 1:
        return accounts[0], ""
    if intake and intake not in accounts:
        return (
            None,
            f"The intake account '{intake}' is not authenticated in gog. "
            "Set the Gmail account in Settings or authenticate that Gmail account first.",
        )
    return (
        None,
        "Multiple Gmail accounts are authenticated in gog. Set the Gmail account in Settings "
        "before continuing with Gmail intake.",
    )


def _prepare_downloaded_attachment(
    *,
    selection: GmailAttachmentSelection,
    gog_path: Path,
    account_email: str,
    download_dir: Path,
    used_names: set[str],
    preview_paths: Mapping[str, Path],
    preview_page_counts: Mapping[str, int],
    log_callback: Callable[[str], None] | None = None,
) -> DownloadedGmailAttachment:
    def _log(message_text: str) -> None:
        if callable(log_callback):
            log_callback(message_text)

    attachment = selection.candidate
    requested_name = _unique_download_name(attachment.filename, used_names)
    saved_path: Path | None = None
    reused_preview_cache = False
    cached_path = preview_paths.get(attachment.attachment_id)
    known_cached_page_count = preview_page_counts.get(attachment.attachment_id)
    if isinstance(cached_path, Path):
        candidate_path = cached_path.expanduser().resolve()
        if candidate_path.exists():
            staged_path = download_dir / requested_name
            try:
                copy2(candidate_path, staged_path)
                saved_path = staged_path.expanduser().resolve()
                _log(
                    "Gmail intake: reusing preview cache for "
                    f"{attachment.filename} -> {saved_path}"
                )
                reused_preview_cache = True
            except OSError as exc:
                _log(
                    "Gmail intake: preview cache copy failed for "
                    f"{attachment.filename}; downloading fresh copy instead ({exc})."
                )
                saved_path = None
        else:
            _log(
                "Gmail intake: preview cache missing for "
                f"{attachment.filename}; downloading fresh copy instead."
            )
    if saved_path is None:
        result = download_gmail_attachment_via_gog(
            GmailAttachmentDownloadRequest(
                gog_path=gog_path,
                account_email=account_email,
                message_id=attachment.source_message_id,
                attachment_id=attachment.attachment_id,
                output_dir=download_dir,
                filename=requested_name,
            )
        )
        if not result.ok or result.saved_path is None:
            raise ValueError(f"Failed to download '{attachment.filename}': {result.message}")
        saved_path = result.saved_path.expanduser().resolve()
        _log(
            "Gmail intake: downloaded fresh Gmail copy for "
            f"{attachment.filename} -> {saved_path}"
        )
    try:
        page_count = _selection_page_count(
            selection=selection,
            attachment=attachment,
            preview_page_counts=preview_page_counts,
        )
    except Exception:
        page_count = None
    if page_count is None or page_count <= 0:
        if _is_pdf_attachment(attachment):
            raise ValueError(
                "Page count is unavailable for Gmail attachment "
                f"'{attachment.filename}'. Load the PDF in the browser preview first so the browser can stage its page metadata."
            )
        page_count = 1
    if reused_preview_cache and isinstance(known_cached_page_count, int) and known_cached_page_count > 0:
        if int(known_cached_page_count) != page_count:
            _log(
                "Gmail intake: preview cache page-count mismatch for "
                f"{attachment.filename} (cached={int(known_cached_page_count)}, actual={page_count})."
            )
    if int(selection.start_page) > page_count:
        raise ValueError(
            f"Start page {int(selection.start_page)} exceeds page count {page_count} "
            f"for Gmail attachment '{attachment.filename}'."
        )
    return DownloadedGmailAttachment(
        candidate=attachment,
        saved_path=saved_path,
        start_page=int(selection.start_page),
        page_count=page_count,
    )


def _header_value(part: object, header_name: str) -> str:
    if not isinstance(part, dict):
        return ""
    raw_headers = part.get("headers", [])
    if not isinstance(raw_headers, list):
        return ""
    target = header_name.strip().lower()
    for item in raw_headers:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "") or "").strip().lower()
        if name != target:
            continue
        return str(item.get("value", "") or "").strip()
    return ""


def _collect_supported_attachments(
    message_payload: object,
    *,
    source_message_id: str,
) -> list[GmailAttachmentCandidate]:
    if not isinstance(message_payload, dict):
        return []
    candidates: list[GmailAttachmentCandidate] = []
    seen: set[tuple[str, str]] = set()

    def _walk(part: object) -> None:
        if not isinstance(part, dict):
            return
        filename = str(part.get("filename", "") or "").strip()
        mime_type = str(part.get("mimeType", "") or "").strip() or "application/octet-stream"
        body = part.get("body")
        attachment_id = (
            str(body.get("attachmentId", "") or "").strip()
            if isinstance(body, dict)
            else ""
        )
        size_bytes = _coerce_size_bytes(body.get("size") if isinstance(body, dict) else 0)
        disposition = _header_value(part, "Content-Disposition").strip().lower()
        if (
            filename
            and attachment_id
            and is_supported_source_file(Path(filename))
            and "inline" not in disposition
        ):
            key = (attachment_id, filename.casefold())
            if key not in seen:
                seen.add(key)
                candidates.append(
                    GmailAttachmentCandidate(
                        attachment_id=attachment_id,
                        filename=filename,
                        mime_type=mime_type,
                        size_bytes=size_bytes,
                        source_message_id=source_message_id,
                    )
                )
        child_parts = part.get("parts", [])
        if isinstance(child_parts, list):
            for child in child_parts:
                _walk(child)

    _walk(message_payload)
    return candidates


def _coerce_size_bytes(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            try:
                return max(0, int(cleaned))
            except ValueError:
                return 0
    return 0


def _unique_download_name(filename: str, used_names: set[str]) -> str:
    original = filename.strip() or "attachment"
    candidate = original
    path = Path(original)
    stem = path.stem or "attachment"
    suffix = path.suffix
    index = 2
    while candidate.casefold() in used_names:
        candidate = f"{stem} ({index}){suffix}"
        index += 1
    used_names.add(candidate.casefold())
    return candidate


def _resolve_downloaded_path(
    *,
    output_dir: Path,
    filename: str,
    payload: dict[str, Any] | None,
) -> Path | None:
    expected = (output_dir / filename).expanduser().resolve()
    if expected.exists():
        return expected
    if payload is None:
        return None
    for key in ("path", "savedPath", "saved_path", "outputPath", "output_path"):
        raw = payload.get(key)
        if not isinstance(raw, str):
            continue
        candidate = Path(raw).expanduser().resolve()
        if candidate.exists():
            return candidate
    return None
