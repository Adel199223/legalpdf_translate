"""Shared Gmail browser-parity services and workspace session state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha1
import json
from pathlib import Path
import re
import tempfile
import threading
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from .gmail_batch import (
    DownloadedGmailAttachment,
    FetchedGmailMessage,
    GmailAttachmentCandidate,
    GmailAttachmentDownloadRequest,
    GmailAttachmentSelection,
    GmailBatchConfirmedItem,
    GmailBatchSession,
    GmailInterpretationSession,
    GmailMessageLoadResult,
    download_gmail_attachment_via_gog,
    gmail_batch_consistency_signature,
    load_gmail_message_from_intake,
    prepare_gmail_batch_session,
    prepare_gmail_interpretation_session,
    stage_gmail_batch_translated_docx,
    write_gmail_batch_session_report,
    write_gmail_interpretation_session_report,
)
from .gmail_draft import (
    GmailDraftRequest,
    GmailDraftResult,
    GmailPrereqStatus,
    assess_gmail_draft_prereqs,
    build_gmail_batch_reply_request,
    build_interpretation_gmail_reply_request,
    create_gmail_draft_via_gog,
    validate_translated_docx_artifacts_for_gmail_draft,
)
from .gmail_intake import InboundMailContext
from .output_paths import require_writable_output_dir
from .user_settings import load_gui_settings_from_path
from .word_automation import (
    assess_word_pdf_export_readiness,
    clear_word_pdf_export_readiness_cache,
)

if TYPE_CHECKING:
    from .translation_service import TranslationJobManager

GMAIL_WORKFLOW_TRANSLATION = "translation"
GMAIL_WORKFLOW_INTERPRETATION = "interpretation"

_DEFAULT_GMAIL_OUTPUT_SUBDIR = "gmail_browser"
_EMAIL_PATTERN = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.IGNORECASE)
_REPLY_HINT_TERMS = (
    "reply",
    "resposta",
    "responder",
    "respond",
    "response",
    "remet",
    "endere",
    "address",
    "seguinte",
    "following",
    "exclusive",
    "exclusiv",
)
_PREPARE_REASON_MESSAGES = {
    "bridge_disabled": "Gmail bridge is disabled in LegalPDF Translate.",
    "bridge_token_missing": "Gmail bridge is not configured in LegalPDF Translate.",
    "invalid_bridge_port": "Gmail bridge port is invalid in LegalPDF Translate.",
    "canonical_restart_required": "Live Gmail is paused until LegalPDF Translate restarts into the canonical runtime.",
    "runtime_metadata_missing": "LegalPDF Translate is not running the Gmail bridge right now.",
    "bridge_not_running": "LegalPDF Translate is not running the Gmail bridge right now.",
    "runtime_metadata_invalid": "LegalPDF Translate has invalid Gmail bridge runtime metadata.",
    "bridge_port_mismatch": "LegalPDF Translate is listening on a different Gmail bridge port.",
    "bridge_port_owner_unknown": "LegalPDF Translate could not verify the Gmail bridge listener.",
    "bridge_port_owner_mismatch": "Another process is using the Gmail bridge port configured for LegalPDF Translate.",
    "window_not_found": "LegalPDF Translate is running without a visible main window.",
    "launch_target_missing": "LegalPDF Translate auto-launch is not available from this checkout.",
    "launch_helper_missing": "LegalPDF Translate auto-launch is not available from this checkout.",
    "launch_python_missing": "LegalPDF Translate auto-launch is not available from this checkout.",
    "launch_command_failed": "LegalPDF Translate could not be started automatically.",
    "launch_in_progress": "LegalPDF Translate is already starting the browser app for this Gmail handoff.",
    "launch_timeout": "LegalPDF Translate was started, but the Gmail bridge did not become ready in time.",
    "unsupported_platform": "Foreground activation is only supported on Windows for this extension.",
}
_TERMINAL_BATCH_FINALIZATION_STATES = frozenset({"local_artifacts_ready", "draft_failed", "draft_ready"})
_REPORTABLE_BATCH_FINALIZATION_STATES = _TERMINAL_BATCH_FINALIZATION_STATES | frozenset({"blocked_word_pdf_export"})
_RESTORED_BATCH_SESSION_MAX_AGE = timedelta(hours=24)


def _word_pdf_cache_scope_token(settings_path: Path) -> str:
    return str(settings_path.expanduser().resolve())


def _clear_word_pdf_export_cache_for_session(*, settings_path: Path, session_id: str) -> int:
    scope_token = _word_pdf_cache_scope_token(settings_path)
    removed = clear_word_pdf_export_readiness_cache(
        scope_prefix=f"gmail_batch_finalization::{scope_token}::{str(session_id or '').strip()}",
    )
    removed += clear_word_pdf_export_readiness_cache(scope_prefix=f"provider_state::{scope_token}")
    return removed


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _sanitize_email(value: object) -> str:
    cleaned = str(value or "").strip().strip("<>[](){}\"'`")
    cleaned = re.sub(r"[.,;:]+$", "", cleaned)
    if cleaned and _EMAIL_PATTERN.fullmatch(cleaned):
        return cleaned
    return ""


def _path_text(path: Path | None) -> str:
    if path is None:
        return ""
    return str(path.expanduser().resolve())


def _normalize_batch_finalization_state(value: object) -> str:
    return _clean_text(value).lower().replace(" ", "_")


def _batch_finalization_status_and_retry(
    *,
    finalization_state: object,
    draft_preflight_result: object = "",
) -> tuple[str, bool]:
    normalized_state = _normalize_batch_finalization_state(finalization_state)
    normalized_preflight = _normalize_batch_finalization_state(draft_preflight_result)
    if normalized_state == "draft_ready":
        return ("ok", False)
    if normalized_state == "local_artifacts_ready":
        return ("local_only", True)
    if normalized_state == "draft_failed":
        return ("draft_unavailable" if normalized_preflight == "failed" else "draft_failed", True)
    if normalized_state == "blocked_word_pdf_export":
        return ("blocked_word_pdf_export", False)
    return (normalized_state or "ok", False)


def _has_complete_batch_finalization_report_context(raw_context: object) -> bool:
    if not isinstance(raw_context, Mapping):
        return False
    return (
        _clean_text(raw_context.get("kind")) == "gmail_finalization_report"
        and _clean_text(raw_context.get("operation")) == "gmail_batch_finalize"
        and _clean_text(raw_context.get("status")) != ""
        and _clean_text(raw_context.get("finalization_state")) != ""
        and _clean_text(raw_context.get("build_sha")) != ""
        and _clean_text(raw_context.get("asset_version")) != ""
        and isinstance(raw_context.get("session"), Mapping)
    )


def _merge_batch_finalization_report_context(
    *,
    base_context: Mapping[str, Any],
    existing_context: object,
) -> dict[str, Any]:
    merged = dict(base_context)
    if not isinstance(existing_context, Mapping):
        return merged
    captured_at = _clean_text(existing_context.get("captured_at"))
    active_view = _clean_text(existing_context.get("active_view"))
    if captured_at:
        merged["captured_at"] = captured_at
    if active_view:
        merged["active_view"] = active_view
    raw_outcome = existing_context.get("outcome")
    if isinstance(raw_outcome, Mapping):
        outcome = dict(merged.get("outcome", {}))
        for key in ("draft", "draft_prereqs", "gmail_draft_request", "gmail_draft_result"):
            value = raw_outcome.get(key)
            if isinstance(value, Mapping) and value:
                outcome[key] = dict(value)
        merged["outcome"] = outcome
    return merged


def _resolve_workflow_kind(value: object) -> str:
    cleaned = str(value or "").strip().casefold()
    if cleaned == GMAIL_WORKFLOW_INTERPRETATION:
        return GMAIL_WORKFLOW_INTERPRETATION
    return GMAIL_WORKFLOW_TRANSLATION


def _configured_gmail_values(settings_path: Path) -> tuple[str, str]:
    gui_settings = load_gui_settings_from_path(settings_path)
    return (
        str(gui_settings.get("gmail_gog_path", "") or "").strip(),
        str(gui_settings.get("gmail_account_email", "") or "").strip(),
    )


def autofill_interpretation_from_notification_pdf(*args, **kwargs):
    from .interpretation_service import autofill_interpretation_from_notification_pdf as _impl

    return _impl(*args, **kwargs)


def export_interpretation_honorarios(*args, **kwargs):
    from .interpretation_service import export_interpretation_honorarios as _impl

    return _impl(*args, **kwargs)


def _current_profile(*args, **kwargs):
    from .interpretation_service import _current_profile as _impl

    return _impl(*args, **kwargs)


def _default_output_dir(settings_path: Path, outputs_dir: Path) -> Path:
    gui_settings = load_gui_settings_from_path(settings_path)
    for key in ("last_outdir", "default_outdir"):
        candidate = str(gui_settings.get(key, "") or "").strip()
        if candidate:
            try:
                return require_writable_output_dir(Path(candidate))
            except Exception:
                continue
    fallback = outputs_dir.expanduser().resolve() / _DEFAULT_GMAIL_OUTPUT_SUBDIR
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def extension_prepare_reason_catalog() -> list[dict[str, str]]:
    return [{"reason": key, "message": value} for key, value in sorted(_PREPARE_REASON_MESSAGES.items())]


def _load_result_stdout_payload(result: GmailMessageLoadResult) -> dict[str, Any]:
    stdout = str(result.stdout or "").strip()
    if not stdout:
        return {}
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _header_value(headers: object, *names: str) -> str:
    if not isinstance(headers, list):
        return ""
    name_set = {name.casefold() for name in names}
    for item in headers:
        if not isinstance(item, Mapping):
            continue
        header_name = str(item.get("name", "") or "").strip().casefold()
        if header_name not in name_set:
            continue
        email = _sanitize_email(item.get("value"))
        if email:
            return email
    return ""


def _extract_reply_email_from_text(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return ""
    scored_candidates: list[tuple[int, int, str]] = []
    all_emails: list[str] = []
    seen_all: set[str] = set()
    for line_index, _line in enumerate(lines):
        window = " ".join(lines[max(0, line_index - 1): min(len(lines), line_index + 2)]).casefold()
        score = sum(1 for term in _REPLY_HINT_TERMS if term in window)
        for match in _EMAIL_PATTERN.finditer(lines[line_index]):
            email = _sanitize_email(match.group(0))
            if not email:
                continue
            lowered = email.casefold()
            if lowered not in seen_all:
                all_emails.append(email)
                seen_all.add(lowered)
            if score > 0:
                scored_candidates.append((-score, line_index, email))
    if scored_candidates:
        scored_candidates.sort()
        return scored_candidates[0][2]
    if len(all_emails) == 1:
        return all_emails[0]
    return ""


def _preferred_reply_email_from_load_result(result: GmailMessageLoadResult) -> str:
    payload = _load_result_stdout_payload(result)
    header_email = _header_value(payload.get("headers"), "Reply-To")
    if header_email:
        return header_email
    message_payload = payload.get("message")
    if isinstance(message_payload, Mapping):
        nested_payload = message_payload.get("payload")
        if isinstance(nested_payload, Mapping):
            header_email = _header_value(nested_payload.get("headers"), "Reply-To")
            if header_email:
                return header_email
    body_email = _extract_reply_email_from_text(str(payload.get("body", "") or ""))
    if body_email:
        return body_email
    return ""


def _seed_payload_with_preferred_reply_email(seed_payload: object, preferred_reply_email: str) -> object:
    if not isinstance(seed_payload, Mapping):
        return seed_payload
    if not preferred_reply_email:
        return dict(seed_payload)
    patched = dict(seed_payload)
    patched["court_email"] = preferred_reply_email
    return patched


def _seed_response_with_preferred_reply_email(
    seed_response: dict[str, Any],
    preferred_reply_email: str,
) -> dict[str, Any]:
    if not preferred_reply_email:
        return seed_response
    patched = dict(seed_response)
    patched["normalized_payload"] = _seed_payload_with_preferred_reply_email(
        seed_response.get("normalized_payload"),
        preferred_reply_email,
    )
    return patched


def _serialize_attachment_candidate(attachment: GmailAttachmentCandidate) -> dict[str, Any]:
    return {
        "attachment_id": attachment.attachment_id,
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "size_bytes": int(attachment.size_bytes),
        "source_message_id": attachment.source_message_id,
    }


def _is_pdf_attachment(candidate: GmailAttachmentCandidate) -> bool:
    filename = candidate.filename.strip().lower()
    mime_type = candidate.mime_type.strip().lower()
    return mime_type == "application/pdf" or filename.endswith(".pdf")


def _serialize_downloaded_attachment(attachment: DownloadedGmailAttachment) -> dict[str, Any]:
    return {
        "attachment": _serialize_attachment_candidate(attachment.candidate),
        "saved_path": _path_text(attachment.saved_path),
        "start_page": int(attachment.start_page),
        "page_count": int(attachment.page_count),
    }


def _serialize_message(message: FetchedGmailMessage) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "thread_id": message.thread_id,
        "subject": message.subject,
        "from_header": message.from_header,
        "account_email": message.account_email,
        "attachments": [_serialize_attachment_candidate(item) for item in message.attachments],
    }


def _serialize_load_result(result: GmailMessageLoadResult) -> dict[str, Any]:
    return {
        "ok": bool(result.ok),
        "classification": result.classification,
        "status_message": result.status_message,
        "gog_path": _path_text(result.gog_path),
        "account_email": result.account_email or "",
        "accounts": list(result.accounts),
        "message": _serialize_message(result.message) if result.message is not None else None,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "intake_context": {
            "message_id": result.intake_context.message_id,
            "thread_id": result.intake_context.thread_id,
            "subject": result.intake_context.subject,
            "account_email": result.intake_context.account_email or "",
        },
    }


def _serialize_inbound_context(context: InboundMailContext | Mapping[str, Any] | None) -> dict[str, str]:
    if context is None:
        return {}
    if isinstance(context, InboundMailContext):
        return {
            "message_id": context.message_id,
            "thread_id": context.thread_id,
            "subject": context.subject,
            "account_email": context.account_email or "",
        }
    if isinstance(context, Mapping):
        return {
            "message_id": _clean_text(context.get("message_id")),
            "thread_id": _clean_text(context.get("thread_id")),
            "subject": _clean_text(context.get("subject")),
            "account_email": _clean_text(context.get("account_email")),
        }
    return {}


def _gmail_context_matches(
    left: InboundMailContext | Mapping[str, Any] | None,
    right: InboundMailContext | Mapping[str, Any] | None,
) -> bool:
    left_payload = _serialize_inbound_context(left)
    right_payload = _serialize_inbound_context(right)
    comparisons: list[bool] = []
    left_message_id = _clean_text(left_payload.get("message_id"))
    right_message_id = _clean_text(right_payload.get("message_id"))
    if left_message_id and right_message_id:
        comparisons.append(left_message_id == right_message_id)
    left_thread_id = _clean_text(left_payload.get("thread_id"))
    right_thread_id = _clean_text(right_payload.get("thread_id"))
    if left_thread_id and right_thread_id:
        comparisons.append(left_thread_id == right_thread_id)
    return bool(comparisons) and all(comparisons)


def _message_signature(result: GmailMessageLoadResult) -> str:
    message = result.message
    subject = message.subject if message is not None else result.intake_context.subject
    account_email = result.account_email or result.intake_context.account_email or ""
    attachment_ids = "|".join(
        attachment.attachment_id
        for attachment in (message.attachments if message is not None else ())
    )
    raw = "\n".join(
        (
            _clean_text(result.intake_context.message_id),
            _clean_text(result.intake_context.thread_id),
            _clean_text(subject),
            _clean_text(account_email),
            attachment_ids,
        )
    )
    if raw.strip() == "":
        return ""
    return sha1(raw.encode("utf-8")).hexdigest()


def _serialize_confirmed_item(item: GmailBatchConfirmedItem) -> dict[str, Any]:
    durable_path = _path_text(item.translated_docx_path)
    staged_path = _path_text(item.staged_translated_docx_path)
    primary_path = durable_path or staged_path
    return {
        "attachment_filename": item.downloaded_attachment.candidate.filename,
        "translated_docx_path": primary_path,
        "durable_translated_docx_path": durable_path,
        "staged_translated_docx_path": staged_path,
        "translated_docx_path_source": "durable" if durable_path else ("staged_fallback" if staged_path else ""),
        "translated_docx_path_exists": bool(primary_path and ((durable_path and item.translated_docx_path.exists()) or (staged_path and item.staged_translated_docx_path.exists()))),
        "durable_translated_docx_path_exists": bool(durable_path and item.translated_docx_path.exists()),
        "staged_translated_docx_path_exists": bool(staged_path and item.staged_translated_docx_path.exists()),
        "run_dir": _path_text(item.run_dir),
        "translated_word_count": int(item.translated_word_count),
        "joblog_row_id": int(item.joblog_row_id),
        "run_id": item.run_id,
        "case_number": item.case_number,
        "case_entity": item.case_entity,
        "case_city": item.case_city,
        "court_email": item.court_email,
        "consistency_signature": list(item.consistency_signature),
    }


def _serialize_draft_prereqs(prereqs: GmailPrereqStatus) -> dict[str, Any]:
    return {
        "status": "ready" if bool(prereqs.ready) else "failed",
        "ready": bool(prereqs.ready),
        "message": prereqs.message,
        "gog_path": _path_text(prereqs.gog_path),
        "account_email": prereqs.account_email or "",
        "accounts": list(prereqs.accounts),
    }


def _pending_draft_prereqs_payload(*, account_email: str = "") -> dict[str, Any]:
    return {
        "status": "pending",
        "ready": False,
        "message": "Draft prerequisites will load after the browser shell is ready.",
        "gog_path": "",
        "account_email": account_email or "",
        "accounts": [],
    }


def _serialize_draft_request(request: GmailDraftRequest) -> dict[str, Any]:
    return {
        "gog_path": _path_text(request.gog_path),
        "account_email": request.account_email,
        "to_email": request.to_email,
        "subject": request.subject,
        "body_preview": request.body[:4000],
        "attachments": [_path_text(path) for path in request.attachments],
        "reply_to_message_id": request.reply_to_message_id or "",
    }


def _serialize_draft_result(result: GmailDraftResult) -> dict[str, Any]:
    return {
        "ok": bool(result.ok),
        "message": result.message,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "payload": dict(result.payload or {}),
    }


def _serialize_translation_launch(
    *,
    session: GmailBatchSession,
    attachment: DownloadedGmailAttachment,
    target_lang: str,
    output_dir: Path,
) -> dict[str, Any]:
    return {
        "source_path": _path_text(attachment.saved_path),
        "source_filename": attachment.candidate.filename,
        "attachment_id": attachment.candidate.attachment_id,
        "source_type": "pdf" if _is_pdf_attachment(attachment.candidate) else "image",
        "start_page": int(attachment.start_page),
        "page_count": int(attachment.page_count),
        "output_dir": _path_text(output_dir),
        "target_lang": target_lang.strip().upper(),
        "image_mode": "auto",
        "ocr_mode": "auto",
        "ocr_engine": "local_then_api",
        "resume": False,
        "keep_intermediates": True,
        "auto_start": False,
        "workflow_source": "gmail_intake",
        "gmail_batch_context": {
            "source": "gmail_intake",
            "session_id": session.session_id,
            "message_id": session.intake_context.message_id,
            "thread_id": session.intake_context.thread_id,
            "attachment_id": attachment.candidate.attachment_id,
            "selected_attachment_filename": attachment.candidate.filename,
            "selected_attachment_count": int(len(session.downloaded_attachments)),
            "selected_target_lang": target_lang.strip().upper(),
            "selected_start_page": int(attachment.start_page),
            "gmail_batch_session_report_path": _path_text(session.session_report_path) or "",
        },
    }


def _serialize_batch_session(
    session: GmailBatchSession,
    *,
    current_index: int,
) -> dict[str, Any]:
    total = len(session.downloaded_attachments)
    current_attachment = (
        session.downloaded_attachments[current_index]
        if 0 <= current_index < total
        else None
    )
    return {
        "kind": GMAIL_WORKFLOW_TRANSLATION,
        "session_id": session.session_id,
        "status": session.status,
        "halt_reason": session.halt_reason,
        "started_at": session.started_at,
        "message": _serialize_message(session.message),
        "download_dir": _path_text(session.download_dir),
        "effective_output_dir": _path_text(session.effective_output_dir),
        "selected_target_lang": session.selected_target_lang,
        "attachments": [_serialize_downloaded_attachment(item) for item in session.downloaded_attachments],
        "confirmed_items": [_serialize_confirmed_item(item) for item in session.confirmed_items],
        "current_index": int(current_index),
        "current_item_number": int(current_index + 1) if current_attachment is not None else int(total),
        "total_items": int(total),
        "current_attachment": _serialize_downloaded_attachment(current_attachment) if current_attachment is not None else None,
        "completed": total > 0 and len(session.confirmed_items) >= total,
        "consistency_signature": list(session.consistency_signature) if session.consistency_signature else [],
        "session_report_path": _path_text(session.session_report_path),
        "final_attachment_basenames": list(session.final_attachment_basenames),
        "draft_created": bool(session.draft_created),
        "draft_preflight_result": session.draft_preflight_result,
        "draft_failure_reason": session.draft_failure_reason,
        "requested_honorarios_path": _path_text(session.requested_honorarios_path),
        "requested_honorarios_pdf_path": _path_text(session.requested_honorarios_pdf_path),
        "actual_honorarios_path": _path_text(session.actual_honorarios_path),
        "actual_honorarios_pdf_path": _path_text(session.actual_honorarios_pdf_path),
        "honorarios_auto_renamed": bool(session.honorarios_auto_renamed),
        "pdf_export": dict(session.pdf_export),
        "finalization_state": session.finalization_state,
        "finalization_preflight": dict(session.finalization_preflight),
        "finalization_report_context": dict(session.finalization_report_context),
    }


def _serialize_interpretation_session(session: GmailInterpretationSession) -> dict[str, Any]:
    return {
        "kind": GMAIL_WORKFLOW_INTERPRETATION,
        "session_id": session.session_id,
        "status": session.status,
        "halt_reason": session.halt_reason,
        "started_at": session.started_at,
        "message": _serialize_message(session.message),
        "download_dir": _path_text(session.download_dir),
        "effective_output_dir": _path_text(session.effective_output_dir),
        "attachment": _serialize_downloaded_attachment(session.downloaded_attachment),
        "session_report_path": _path_text(session.session_report_path),
        "draft_created": bool(session.draft_created),
        "draft_failure_reason": session.draft_failure_reason,
        "metadata_extraction": dict(session.metadata_extraction),
        "pdf_export": dict(session.pdf_export),
    }


def build_gmail_browser_capability_flags(*, settings_path: Path) -> dict[str, Any]:
    configured_gog_path, configured_account_email = _configured_gmail_values(settings_path)
    prereqs = assess_gmail_draft_prereqs(
        configured_gog_path=configured_gog_path,
        configured_account_email=configured_account_email,
    )
    return {
        "gmail": {
            "status": "ready" if prereqs.ready else "unavailable",
            "draft_prereqs": _serialize_draft_prereqs(prereqs),
            "supports_load_exact_message": True,
            "supports_attachment_review": True,
            "supports_translation_batch": True,
            "supports_interpretation_notice": True,
            "supports_gmail_reply_drafts": True,
        }
    }


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _build_batch_finalization_report_context(
    *,
    runtime_mode: str,
    workspace_id: str,
    build_sha: str,
    asset_version: str,
    session: GmailBatchSession,
    status: str,
    retry_available: bool,
    draft_payload: Mapping[str, Any] | None = None,
    draft_prereqs: GmailPrereqStatus | None = None,
    draft_request: GmailDraftRequest | None = None,
    draft_result: GmailDraftResult | None = None,
    actual_export: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    message = session.message
    return {
        "kind": "gmail_finalization_report",
        "captured_at": _utc_now_iso(),
        "operation": "gmail_batch_finalize",
        "status": str(status or "").strip(),
        "finalization_state": str(session.finalization_state or "").strip(),
        "retry_available": bool(retry_available),
        "runtime_mode": str(runtime_mode or "").strip(),
        "workspace_id": str(workspace_id or "").strip(),
        "active_view": "",
        "build_sha": str(build_sha or "").strip(),
        "asset_version": str(asset_version or "").strip(),
        "session": {
            "session_id": session.session_id,
            "message_id": message.message_id,
            "thread_id": message.thread_id,
            "subject": message.subject,
            "account_email": message.account_email,
            "selected_target_lang": session.selected_target_lang.strip(),
            "effective_output_dir": _path_text(session.effective_output_dir),
            "confirmed_items": [_serialize_confirmed_item(item) for item in session.confirmed_items],
            "session_report_path": _path_text(session.session_report_path),
            "final_attachment_basenames": list(session.final_attachment_basenames),
        },
        "word_pdf_export": dict(session.finalization_preflight),
        "actual_export": dict(actual_export or session.pdf_export),
        "outcome": {
            "draft": dict(draft_payload or {}),
            "draft_prereqs": _serialize_draft_prereqs(draft_prereqs) if draft_prereqs is not None else {},
            "gmail_draft_request": _serialize_draft_request(draft_request) if draft_request is not None else {},
            "gmail_draft_result": _serialize_draft_result(draft_result) if draft_result is not None else {},
            "docx_path": _path_text(session.actual_honorarios_path),
            "docx_path_exists": bool(session.actual_honorarios_path and session.actual_honorarios_path.exists()),
            "pdf_path": _path_text(session.actual_honorarios_pdf_path),
            "pdf_path_exists": bool(session.actual_honorarios_pdf_path and session.actual_honorarios_pdf_path.exists()),
            "requested_docx_path": _path_text(session.requested_honorarios_path),
            "requested_pdf_path": _path_text(session.requested_honorarios_pdf_path),
            "draft_failure_reason": session.draft_failure_reason.strip(),
            "draft_created": bool(session.draft_created),
            "honorarios_auto_renamed": bool(session.honorarios_auto_renamed),
        },
    }


def _persist_batch_finalization_report_context(
    *,
    runtime_mode: str,
    workspace_id: str,
    build_sha: str,
    asset_version: str,
    session: GmailBatchSession,
    status: str,
    retry_available: bool,
    draft_payload: Mapping[str, Any] | None = None,
    draft_prereqs: GmailPrereqStatus | None = None,
    draft_request: GmailDraftRequest | None = None,
    draft_result: GmailDraftResult | None = None,
    actual_export: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    context = _build_batch_finalization_report_context(
        runtime_mode=runtime_mode,
        workspace_id=workspace_id,
        build_sha=build_sha,
        asset_version=asset_version,
        session=session,
        status=status,
        retry_available=retry_available,
        draft_payload=draft_payload,
        draft_prereqs=draft_prereqs,
        draft_request=draft_request,
        draft_result=draft_result,
        actual_export=actual_export,
    )
    session.finalization_report_context = dict(context)
    return context


def _backfill_batch_finalization_report_context(
    *,
    runtime_mode: str,
    workspace_id: str,
    build_sha: str,
    asset_version: str,
    session: GmailBatchSession,
) -> dict[str, Any] | None:
    state = _normalize_batch_finalization_state(session.finalization_state or session.status)
    if state not in _REPORTABLE_BATCH_FINALIZATION_STATES:
        return None
    status, retry_available = _batch_finalization_status_and_retry(
        finalization_state=state,
        draft_preflight_result=session.draft_preflight_result,
    )
    canonical_context = _build_batch_finalization_report_context(
        runtime_mode=runtime_mode,
        workspace_id=workspace_id,
        build_sha=build_sha,
        asset_version=asset_version,
        session=session,
        status=status,
        retry_available=retry_available,
        actual_export=session.pdf_export,
    )
    repaired_context = _merge_batch_finalization_report_context(
        base_context=canonical_context,
        existing_context=session.finalization_report_context,
    )
    session.finalization_report_context = dict(repaired_context)
    return repaired_context


def _candidate_existing_path(path_text: object) -> str:
    cleaned = _clean_text(path_text)
    if not cleaned:
        return ""
    try:
        path = Path(cleaned).expanduser().resolve()
    except OSError:
        return cleaned
    return str(path) if path.exists() else cleaned


def _report_confirmed_item_from_sources(
    *,
    raw_item: Mapping[str, Any] | None,
    run_payload: Mapping[str, Any] | None,
    effective_output_dir_text: str = "",
) -> dict[str, Any]:
    raw_item = raw_item if isinstance(raw_item, Mapping) else {}
    run_payload = run_payload if isinstance(run_payload, Mapping) else {}

    run_dir_text = _clean_text(run_payload.get("run_dir")) or _clean_text(raw_item.get("run_dir"))
    translated_basename = _clean_text(run_payload.get("translated_docx_basename"))
    effective_output_dir_text = _clean_text(effective_output_dir_text)
    staged_path_text = (
        _clean_text(raw_item.get("staged_translated_docx_path"))
        or _clean_text(run_payload.get("staged_translated_docx_path"))
    )
    raw_primary_path = _clean_text(raw_item.get("translated_docx_path"))
    raw_durable_path = (
        _clean_text(raw_item.get("durable_translated_docx_path"))
        or _clean_text(run_payload.get("durable_translated_docx_path"))
    )

    durable_from_run = ""
    if run_dir_text and translated_basename:
        durable_from_run = str((Path(run_dir_text).expanduser().resolve() / translated_basename))
    durable_from_output_dir = ""
    if effective_output_dir_text and translated_basename:
        durable_from_output_dir = str(
            (Path(effective_output_dir_text).expanduser().resolve() / translated_basename)
        )

    inferred_staged_path = ""
    if raw_primary_path and durable_from_run:
        try:
            if Path(raw_primary_path).expanduser().resolve() != Path(durable_from_run).expanduser().resolve():
                inferred_staged_path = raw_primary_path
        except OSError:
            if raw_primary_path != durable_from_run:
                inferred_staged_path = raw_primary_path

    durable_candidates = [
        durable_from_run,
        durable_from_output_dir,
        raw_durable_path,
    ]
    if raw_primary_path and not inferred_staged_path:
        durable_candidates.append(raw_primary_path)
    durable_path = ""
    for candidate in durable_candidates:
        if not candidate:
            continue
        resolved = _candidate_existing_path(candidate)
        if resolved and Path(resolved).expanduser().resolve().exists():
            durable_path = resolved
            break
    if not durable_path:
        fallback_durable_candidates = [raw_durable_path]
        if raw_primary_path and not inferred_staged_path:
            fallback_durable_candidates.append(raw_primary_path)
        fallback_durable_candidates.extend([durable_from_output_dir, durable_from_run])
        for candidate in fallback_durable_candidates:
            resolved = _candidate_existing_path(candidate)
            if resolved:
                durable_path = resolved
                break

    staged_candidates = [staged_path_text, inferred_staged_path]
    staged_path = ""
    for candidate in staged_candidates:
        if not candidate:
            continue
        resolved = _candidate_existing_path(candidate)
        if resolved and Path(resolved).expanduser().resolve().exists():
            staged_path = resolved
            break
    if not staged_path:
        for candidate in staged_candidates:
            resolved = _candidate_existing_path(candidate)
            if resolved:
                staged_path = resolved
                break

    primary_path = durable_path or staged_path
    path_source = "durable" if durable_path else ("staged_fallback" if staged_path else "")

    primary_exists = False
    durable_exists = False
    staged_exists = False
    if primary_path:
        try:
            primary_exists = Path(primary_path).expanduser().resolve().exists()
        except OSError:
            primary_exists = False
    if durable_path:
        try:
            durable_exists = Path(durable_path).expanduser().resolve().exists()
        except OSError:
            durable_exists = False
    if staged_path:
        try:
            staged_exists = Path(staged_path).expanduser().resolve().exists()
        except OSError:
            staged_exists = False

    return {
        "attachment_filename": _clean_text(raw_item.get("attachment_filename")) or _clean_text(run_payload.get("attachment_filename")),
        "translated_docx_path": primary_path,
        "durable_translated_docx_path": durable_path,
        "staged_translated_docx_path": staged_path,
        "translated_docx_path_source": path_source,
        "translated_docx_path_exists": bool(primary_exists),
        "durable_translated_docx_path_exists": bool(durable_exists),
        "staged_translated_docx_path_exists": bool(staged_exists),
        "run_dir": run_dir_text,
        "translated_word_count": int(raw_item.get("translated_word_count") or 0),
        "joblog_row_id": int(raw_item.get("joblog_row_id") or run_payload.get("joblog_row_id") or 0),
        "run_id": _clean_text(raw_item.get("run_id")) or _clean_text(run_payload.get("run_id")),
        "case_number": _clean_text(raw_item.get("case_number")),
        "case_entity": _clean_text(raw_item.get("case_entity")),
        "case_city": _clean_text(raw_item.get("case_city")),
        "court_email": _clean_text(raw_item.get("court_email")),
        "consistency_signature": [str(item or "") for item in raw_item.get("consistency_signature", [])] if isinstance(raw_item.get("consistency_signature"), list) else [],
    }


def _restored_confirmed_items_from_session_report(report_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    run_payloads: list[Mapping[str, Any]] = [
        run for run in report_payload.get("runs", []) if isinstance(run, Mapping)
    ]
    effective_output_dir_text = _clean_text(report_payload.get("effective_output_dir"))
    run_by_attachment: dict[str, Mapping[str, Any]] = {}
    run_by_run_id: dict[str, Mapping[str, Any]] = {}
    for run_payload in run_payloads:
        attachment_filename = _clean_text(run_payload.get("attachment_filename"))
        run_id = _clean_text(run_payload.get("run_id"))
        if attachment_filename and attachment_filename not in run_by_attachment:
            run_by_attachment[attachment_filename] = run_payload
        if run_id and run_id not in run_by_run_id:
            run_by_run_id[run_id] = run_payload

    report_context = report_payload.get("finalization_report_context")
    if isinstance(report_context, Mapping):
        session_payload = report_context.get("session")
        if isinstance(session_payload, Mapping):
            confirmed_items = session_payload.get("confirmed_items")
            if isinstance(confirmed_items, list):
                restored = []
                for item in confirmed_items:
                    if not isinstance(item, Mapping):
                        continue
                    run_payload = run_by_run_id.get(_clean_text(item.get("run_id"))) or run_by_attachment.get(
                        _clean_text(item.get("attachment_filename"))
                    )
                    restored.append(
                        _report_confirmed_item_from_sources(
                            raw_item=item,
                            run_payload=run_payload,
                            effective_output_dir_text=effective_output_dir_text,
                        )
                    )
                if restored:
                    return restored
    restored: list[dict[str, Any]] = []
    for run in report_payload.get("runs", []):
        if not isinstance(run, Mapping):
            continue
        restored.append(
            _report_confirmed_item_from_sources(
                raw_item=None,
                run_payload=run,
                effective_output_dir_text=effective_output_dir_text,
            )
        )
    return restored


def _build_batch_finalization_report_context_from_session_report(
    *,
    report_payload: Mapping[str, Any],
    report_path: Path,
    runtime_mode: str,
    workspace_id: str,
    build_sha: str,
    asset_version: str,
) -> dict[str, Any] | None:
    finalization = report_payload.get("finalization")
    intake_context = report_payload.get("intake_context")
    if not isinstance(finalization, Mapping) or not isinstance(intake_context, Mapping):
        return None
    finalization_state = _normalize_batch_finalization_state(
        finalization.get("finalization_state") or report_payload.get("status")
    )
    if finalization_state not in _REPORTABLE_BATCH_FINALIZATION_STATES:
        return None
    status, retry_available = _batch_finalization_status_and_retry(
        finalization_state=finalization_state,
        draft_preflight_result=finalization.get("draft_preflight_result"),
    )
    draft_created = bool(finalization.get("draft_created"))
    draft_failure_reason = _clean_text(finalization.get("draft_failure_reason"))
    gmail_draft_result: dict[str, Any] = {}
    if draft_created or draft_failure_reason:
        gmail_draft_result = {
            "ok": draft_created,
            "message": "Gmail draft created successfully." if draft_created else draft_failure_reason,
            "stdout": "",
            "stderr": "",
            "payload": {},
        }
    return {
        "kind": "gmail_finalization_report",
        "captured_at": _utc_now_iso(),
        "operation": "gmail_batch_finalize",
        "status": status,
        "finalization_state": finalization_state,
        "retry_available": bool(retry_available),
        "runtime_mode": _clean_text(runtime_mode),
        "workspace_id": _clean_text(workspace_id),
        "active_view": "",
        "build_sha": _clean_text(build_sha),
        "asset_version": _clean_text(asset_version),
        "session": {
            "session_id": _clean_text(report_payload.get("session_id")),
            "message_id": _clean_text(intake_context.get("message_id")),
            "thread_id": _clean_text(intake_context.get("thread_id")),
            "subject": _clean_text(intake_context.get("subject")),
            "account_email": _clean_text(intake_context.get("account_email")),
            "selected_target_lang": _clean_text(intake_context.get("selected_target_lang")),
            "effective_output_dir": _clean_text(report_payload.get("effective_output_dir")),
            "confirmed_items": _restored_confirmed_items_from_session_report(report_payload),
            "session_report_path": _path_text(report_path),
            "final_attachment_basenames": list(finalization.get("final_attachment_basenames", [])),
        },
        "word_pdf_export": dict(finalization.get("finalization_preflight", {})),
        "actual_export": dict(report_payload.get("pdf_export", {})),
        "outcome": {
            "draft": {},
            "draft_prereqs": {},
            "gmail_draft_request": {},
            "gmail_draft_result": gmail_draft_result,
            "docx_path": _clean_text(finalization.get("actual_saved_path")),
            "docx_path_exists": bool(_clean_text(finalization.get("actual_saved_path")) and Path(_clean_text(finalization.get("actual_saved_path"))).expanduser().resolve().exists()),
            "pdf_path": _clean_text(finalization.get("actual_pdf_saved_path")),
            "pdf_path_exists": bool(_clean_text(finalization.get("actual_pdf_saved_path")) and Path(_clean_text(finalization.get("actual_pdf_saved_path"))).expanduser().resolve().exists()),
            "requested_docx_path": _clean_text(finalization.get("requested_save_path")),
            "requested_pdf_path": _clean_text(finalization.get("requested_pdf_save_path")),
            "draft_failure_reason": draft_failure_reason,
            "draft_created": draft_created,
            "honorarios_auto_renamed": bool(finalization.get("auto_renamed")),
        },
    }


def _repair_batch_finalization_report_context_from_session_report(
    *,
    raw_context: object,
    report_payload: Mapping[str, Any],
    report_path: Path,
    runtime_mode: str,
    workspace_id: str,
    build_sha: str,
    asset_version: str,
) -> dict[str, Any] | None:
    canonical_context = _build_batch_finalization_report_context_from_session_report(
        report_payload=report_payload,
        report_path=report_path,
        runtime_mode=runtime_mode,
        workspace_id=workspace_id,
        build_sha=build_sha,
        asset_version=asset_version,
    )
    if canonical_context is None:
        return None
    return _merge_batch_finalization_report_context(
        base_context=canonical_context,
        existing_context=raw_context,
    )


def _write_batch_session_report_payload(report_path: Path, payload: Mapping[str, Any]) -> None:
    tmp_path = report_path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(report_path)


def _restored_attachment_payloads_from_session_report(report_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    intake_context = report_payload.get("intake_context")
    if not isinstance(intake_context, Mapping):
        return []
    message_id = _clean_text(intake_context.get("message_id"))
    session_id = _clean_text(report_payload.get("session_id")) or "batch"
    attachments: list[dict[str, Any]] = []
    for index, raw_item in enumerate(intake_context.get("selected_attachments", []), start=1):
        if not isinstance(raw_item, Mapping):
            continue
        filename = _clean_text(raw_item.get("filename"))
        mime_type = "application/pdf" if filename.lower().endswith(".pdf") else ""
        attachments.append(
            {
                "attachment": {
                    "attachment_id": f"restored-{session_id}-{index}",
                    "filename": filename,
                    "mime_type": mime_type,
                    "size_bytes": 0,
                    "source_message_id": message_id,
                },
                "saved_path": "",
                "start_page": max(1, int(raw_item.get("start_page") or 1)),
                "page_count": max(1, int(raw_item.get("page_count") or 1)),
            }
        )
    return attachments


def _build_restored_batch_session_payload_from_report(
    *,
    report_payload: Mapping[str, Any],
    report_path: Path,
    report_context: Mapping[str, Any],
) -> dict[str, Any]:
    finalization = report_payload.get("finalization")
    intake_context = report_payload.get("intake_context")
    if not isinstance(finalization, Mapping) or not isinstance(intake_context, Mapping):
        raise ValueError("Restored Gmail batch session report is missing required sections.")
    attachments = _restored_attachment_payloads_from_session_report(report_payload)
    confirmed_items = _restored_confirmed_items_from_session_report(report_payload)
    total_items = max(len(attachments), len(confirmed_items))
    completed = _normalize_batch_finalization_state(finalization.get("finalization_state")) in _TERMINAL_BATCH_FINALIZATION_STATES
    current_attachment = attachments[min(len(attachments) - 1, max(total_items - 1, 0))] if attachments else None
    consistency_signature: list[str] = []
    if confirmed_items:
        first_signature = confirmed_items[0].get("consistency_signature")
        if isinstance(first_signature, list):
            consistency_signature = [str(item or "") for item in first_signature]
    return {
        "kind": GMAIL_WORKFLOW_TRANSLATION,
        "session_id": _clean_text(report_payload.get("session_id")),
        "status": _clean_text(report_payload.get("status"))
        or _normalize_batch_finalization_state(finalization.get("finalization_state")),
        "halt_reason": _clean_text(report_payload.get("halt_reason")),
        "started_at": _clean_text(report_payload.get("started_at")),
        "message": {
            "message_id": _clean_text(intake_context.get("message_id")),
            "thread_id": _clean_text(intake_context.get("thread_id")),
            "subject": _clean_text(intake_context.get("subject")),
            "from_header": "",
            "account_email": _clean_text(intake_context.get("account_email")),
            "attachments": [dict(item.get("attachment", {})) for item in attachments],
        },
        "download_dir": "",
        "effective_output_dir": _clean_text(report_payload.get("effective_output_dir")),
        "selected_target_lang": _clean_text(intake_context.get("selected_target_lang")),
        "attachments": attachments,
        "confirmed_items": confirmed_items,
        "current_index": max(total_items - 1, 0) if total_items else 0,
        "current_item_number": total_items,
        "total_items": total_items,
        "current_attachment": current_attachment,
        "completed": completed,
        "consistency_signature": consistency_signature,
        "session_report_path": _path_text(report_path),
        "final_attachment_basenames": list(finalization.get("final_attachment_basenames", [])),
        "draft_created": bool(finalization.get("draft_created")),
        "draft_preflight_result": _clean_text(finalization.get("draft_preflight_result")),
        "draft_failure_reason": _clean_text(finalization.get("draft_failure_reason")),
        "requested_honorarios_path": _clean_text(finalization.get("requested_save_path")),
        "requested_honorarios_pdf_path": _clean_text(finalization.get("requested_pdf_save_path")),
        "actual_honorarios_path": _clean_text(finalization.get("actual_saved_path")),
        "actual_honorarios_pdf_path": _clean_text(finalization.get("actual_pdf_saved_path")),
        "honorarios_auto_renamed": bool(finalization.get("auto_renamed")),
        "pdf_export": dict(report_payload.get("pdf_export", {})),
        "finalization_state": _normalize_batch_finalization_state(finalization.get("finalization_state")),
        "finalization_preflight": dict(finalization.get("finalization_preflight", {})),
        "finalization_report_context": dict(report_context),
        "restored_from_report": True,
    }


def _latest_restorable_batch_session_report_path(outputs_dir: Path) -> Path | None:
    report_root = outputs_dir.expanduser().resolve() / "_gmail_batch_sessions"
    if not report_root.exists():
        return None
    candidates: list[tuple[float, Path]] = []
    for report_path in report_root.glob("*/gmail_batch_session.json"):
        try:
            stat = report_path.stat()
        except OSError:
            continue
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        if datetime.now(UTC) - modified_at > _RESTORED_BATCH_SESSION_MAX_AGE:
            continue
        candidates.append((stat.st_mtime, report_path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _restore_batch_session_payload_from_report(
    *,
    outputs_dir: Path,
    runtime_mode: str,
    workspace_id: str,
    build_sha: str,
    asset_version: str,
) -> dict[str, Any] | None:
    report_path = _latest_restorable_batch_session_report_path(outputs_dir)
    if report_path is None:
        return None
    try:
        raw_payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw_payload, Mapping):
        return None
    finalization = raw_payload.get("finalization")
    if not isinstance(finalization, Mapping):
        return None
    finalization_state = _normalize_batch_finalization_state(
        finalization.get("finalization_state") or raw_payload.get("status")
    )
    if finalization_state not in _REPORTABLE_BATCH_FINALIZATION_STATES:
        return None
    report_context_raw = raw_payload.get("finalization_report_context")
    repaired_context = _repair_batch_finalization_report_context_from_session_report(
        raw_context=report_context_raw,
        report_payload=raw_payload,
        report_path=report_path,
        runtime_mode=runtime_mode,
        workspace_id=workspace_id,
        build_sha=build_sha,
        asset_version=asset_version,
    )
    if repaired_context is None:
        return None
    report_context = repaired_context
    if not isinstance(report_context_raw, Mapping) or dict(report_context_raw) != report_context:
        updated_payload = dict(raw_payload)
        updated_payload["finalization_report_context"] = dict(report_context)
        try:
            _write_batch_session_report_payload(report_path, updated_payload)
        except OSError:
            pass
        raw_payload = updated_payload
    try:
        return _build_restored_batch_session_payload_from_report(
            report_payload=raw_payload,
            report_path=report_path,
            report_context=report_context,
        )
    except ValueError:
        return None


@dataclass(slots=True)
class _WorkspaceState:
    loaded_result: GmailMessageLoadResult | None = None
    batch_session: GmailBatchSession | None = None
    interpretation_session: GmailInterpretationSession | None = None
    current_batch_index: int = 0
    interpretation_seed_response: dict[str, Any] | None = None
    review_event_id: int = 0
    message_signature: str = ""
    preferred_reply_email: str = ""
    pending_status: str = ""
    pending_intake_context: dict[str, str] = field(default_factory=dict, repr=False)
    pending_review_open: bool = False
    allow_report_restore: bool = True
    preview_paths: dict[str, Path] = field(default_factory=dict, repr=False)
    preview_page_counts: dict[str, int] = field(default_factory=dict, repr=False)
    _preview_temp_dir: tempfile.TemporaryDirectory[str] | None = field(default=None, repr=False)

    def cleanup(self) -> None:
        if self.batch_session is not None:
            self.batch_session.cleanup()
            self.batch_session = None
        if self.interpretation_session is not None:
            self.interpretation_session.cleanup()
            self.interpretation_session = None
        preview_dir = self._preview_temp_dir
        self._preview_temp_dir = None
        self.preview_paths = {}
        self.preview_page_counts = {}
        self.interpretation_seed_response = None
        self.preferred_reply_email = ""
        self.pending_status = ""
        self.pending_intake_context = {}
        self.pending_review_open = False
        self.current_batch_index = 0
        if preview_dir is not None:
            preview_dir.cleanup()

    def ensure_preview_dir(self) -> Path:
        if self._preview_temp_dir is None:
            self._preview_temp_dir = tempfile.TemporaryDirectory(prefix="legalpdf_browser_gmail_preview_")
        return Path(self._preview_temp_dir.name).expanduser().resolve()


class GmailBrowserSessionManager:
    """In-process Gmail browser workspace registry."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._workspaces: dict[tuple[str, str], _WorkspaceState] = {}

    def _key(self, *, runtime_mode: str, workspace_id: str) -> tuple[str, str]:
        return (str(runtime_mode or "").strip(), str(workspace_id or "").strip())

    def _workspace(self, *, runtime_mode: str, workspace_id: str) -> _WorkspaceState:
        key = self._key(runtime_mode=runtime_mode, workspace_id=workspace_id)
        with self._lock:
            return self._workspaces.setdefault(key, _WorkspaceState())

    def clear_workspace(self, *, runtime_mode: str, workspace_id: str) -> None:
        key = self._key(runtime_mode=runtime_mode, workspace_id=workspace_id)
        with self._lock:
            workspace = self._workspaces.pop(key, None)
        if workspace is not None:
            workspace.cleanup()
        with self._lock:
            self._workspaces[key] = _WorkspaceState(allow_report_restore=False)

    def current_attachment_file(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        attachment_id: str,
    ) -> Path | None:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        cached = workspace.preview_paths.get(attachment_id)
        if isinstance(cached, Path) and cached.exists():
            return cached.expanduser().resolve()
        if workspace.batch_session is not None:
            for attachment in workspace.batch_session.downloaded_attachments:
                if attachment.candidate.attachment_id == attachment_id:
                    return attachment.saved_path.expanduser().resolve()
        if workspace.interpretation_session is not None:
            attachment = workspace.interpretation_session.downloaded_attachment
            if attachment.candidate.attachment_id == attachment_id:
                return attachment.saved_path.expanduser().resolve()
        return None

    def record_browser_pdf_bundle(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        attachment_id: str,
        source_path: Path,
        page_count: int,
    ) -> None:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        attachment_key = _clean_text(attachment_id)
        if not attachment_key:
            return
        resolved_source = source_path.expanduser().resolve()
        workspace.preview_paths[attachment_key] = resolved_source
        workspace.preview_page_counts[attachment_key] = max(1, int(page_count))

    def build_bootstrap(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        outputs_dir: Path,
        build_sha: str = "",
        asset_version: str = "",
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        configured_gog_path, configured_account_email = _configured_gmail_values(settings_path)
        prereqs = assess_gmail_draft_prereqs(
            configured_gog_path=configured_gog_path,
            configured_account_email=configured_account_email,
        )
        defaults = {
            "message_context": {
                "message_id": "",
                "thread_id": "",
                "subject": "",
                "account_email": configured_account_email,
            },
            "default_output_dir": _path_text(_default_output_dir(settings_path, outputs_dir)),
            "workflow_kind": GMAIL_WORKFLOW_TRANSLATION,
            "target_lang": str(load_gui_settings_from_path(settings_path).get("last_lang", "EN") or "EN").strip().upper(),
        }
        if workspace.loaded_result is not None:
            defaults["message_context"] = dict(_serialize_load_result(workspace.loaded_result)["intake_context"])
        elif workspace.pending_intake_context:
            defaults["message_context"] = dict(workspace.pending_intake_context)
        handoff_state = "idle"
        if workspace.pending_review_open and workspace.pending_status:
            handoff_state = workspace.pending_status
        elif workspace.loaded_result is not None:
            handoff_state = "loaded"
        payload: dict[str, Any] = {
            "defaults": defaults,
            "load_result": _serialize_load_result(workspace.loaded_result) if workspace.loaded_result is not None else None,
            "active_session": None,
            "restored_completed_session": None,
            "suggested_translation_launch": None,
            "interpretation_seed": (
                _seed_payload_with_preferred_reply_email(
                    workspace.interpretation_seed_response.get("normalized_payload"),
                    workspace.preferred_reply_email,
                )
                if isinstance(workspace.interpretation_seed_response, dict)
                else None
            ),
            "draft_prereqs": _serialize_draft_prereqs(prereqs),
            "review_event_id": int(workspace.review_event_id),
            "message_signature": workspace.message_signature,
            "pending_status": workspace.pending_status,
            "pending_intake_context": dict(workspace.pending_intake_context),
            "pending_review_open": bool(workspace.pending_review_open),
            "handoff_state": handoff_state,
        }
        if workspace.batch_session is not None:
            report_context = _backfill_batch_finalization_report_context(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                build_sha=build_sha,
                asset_version=asset_version,
                session=workspace.batch_session,
            )
            if report_context is not None:
                write_gmail_batch_session_report(workspace.batch_session)
            payload["active_session"] = _serialize_batch_session(
                workspace.batch_session,
                current_index=workspace.current_batch_index,
            )
            if 0 <= workspace.current_batch_index < len(workspace.batch_session.downloaded_attachments):
                payload["suggested_translation_launch"] = _serialize_translation_launch(
                    session=workspace.batch_session,
                    attachment=workspace.batch_session.downloaded_attachments[workspace.current_batch_index],
                    target_lang=workspace.batch_session.selected_target_lang,
                    output_dir=workspace.batch_session.effective_output_dir or outputs_dir,
                )
        elif workspace.interpretation_session is not None:
            payload["active_session"] = _serialize_interpretation_session(workspace.interpretation_session)
        elif (
            workspace.allow_report_restore
            and workspace.loaded_result is None
            and workspace.interpretation_session is None
            and not workspace.pending_intake_context
            and not workspace.pending_status
        ):
            payload["restored_completed_session"] = _restore_batch_session_payload_from_report(
                outputs_dir=outputs_dir,
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                build_sha=build_sha,
                asset_version=asset_version,
            )
        return {
            "status": "ok",
            "normalized_payload": payload,
            "diagnostics": {},
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }

    def build_shell_ready(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        _configured_gog_path, configured_account_email = _configured_gmail_values(settings_path)
        handoff_state = "idle"
        if workspace.pending_review_open and workspace.pending_status:
            handoff_state = workspace.pending_status
        elif workspace.loaded_result is not None:
            handoff_state = "loaded"
        return {
            "status": "ok",
            "normalized_payload": {
                "load_result": (
                    _serialize_load_result(workspace.loaded_result)
                    if workspace.loaded_result is not None
                    else None
                ),
                "review_event_id": int(workspace.review_event_id),
                "message_signature": workspace.message_signature,
                "pending_status": workspace.pending_status,
                "pending_intake_context": dict(workspace.pending_intake_context),
                "pending_review_open": bool(workspace.pending_review_open),
                "handoff_state": handoff_state,
                "draft_prereqs": _pending_draft_prereqs_payload(
                    account_email=configured_account_email,
                ),
            },
            "diagnostics": {},
            "capability_flags": {},
        }

    def _set_pending_intake(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        context: InboundMailContext,
        status: str = "warming",
        review_open: bool = True,
    ) -> None:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        workspace.pending_status = _clean_text(status).lower() or "warming"
        workspace.pending_intake_context = _serialize_inbound_context(context)
        workspace.pending_review_open = bool(review_open)

    def _mark_pending_failure(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        context: InboundMailContext,
    ) -> None:
        self._set_pending_intake(
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            context=context,
            status="failed",
            review_open=False,
        )

    def _store_loaded_result(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        result: GmailMessageLoadResult,
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        next_event_id = max(0, int(workspace.review_event_id)) + 1
        workspace.cleanup()
        workspace.loaded_result = result
        workspace.allow_report_restore = True
        workspace.review_event_id = next_event_id
        workspace.message_signature = _message_signature(result)
        workspace.preferred_reply_email = _preferred_reply_email_from_load_result(result)
        return {
            "review_event_id": int(workspace.review_event_id),
            "message_signature": workspace.message_signature,
        }

    def load_message(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        context_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        intake_context = InboundMailContext.from_payload(dict(context_payload))
        configured_gog_path, configured_account_email = _configured_gmail_values(settings_path)
        self._set_pending_intake(
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            context=intake_context,
        )
        try:
            result = load_gmail_message_from_intake(
                intake_context=intake_context,
                configured_gog_path=configured_gog_path,
                configured_account_email=configured_account_email,
            )
        except Exception:
            self._mark_pending_failure(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                context=intake_context,
            )
            raise
        review_state = self._store_loaded_result(
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            result=result,
        )
        status = "ok" if result.ok else result.classification or "failed"
        return {
            "status": status,
            "normalized_payload": {
                "load_result": _serialize_load_result(result),
                "message": _serialize_message(result.message) if result.message is not None else None,
                **review_state,
            },
            "diagnostics": {},
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }

    def accept_bridge_intake(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        context: InboundMailContext,
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        if (
            workspace.pending_review_open
            and workspace.pending_status in {"warming", "delayed"}
            and _gmail_context_matches(workspace.pending_intake_context, context)
        ):
            return {
                "status": workspace.pending_status,
                "normalized_payload": {
                    "load_result": (
                        _serialize_load_result(workspace.loaded_result)
                        if workspace.loaded_result is not None
                        else None
                    ),
                    "message": (
                        _serialize_message(workspace.loaded_result.message)
                        if workspace.loaded_result is not None and workspace.loaded_result.message is not None
                        else None
                    ),
                    "workspace_id": workspace_id,
                    "runtime_mode": runtime_mode,
                    "review_event_id": int(workspace.review_event_id),
                    "message_signature": workspace.message_signature,
                    "pending_status": workspace.pending_status,
                    "pending_intake_context": dict(workspace.pending_intake_context),
                    "pending_review_open": bool(workspace.pending_review_open),
                    "handoff_state": "pending_reused",
                },
                "diagnostics": {
                    "bridge_ingest": True,
                    "handoff_reused": True,
                },
                "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
            }
        if (
            workspace.loaded_result is not None
            and _gmail_context_matches(workspace.loaded_result.intake_context, context)
        ):
            result = workspace.loaded_result
            return {
                "status": "ok" if result.ok else result.classification or "failed",
                "normalized_payload": {
                    "load_result": _serialize_load_result(result),
                    "message": _serialize_message(result.message) if result.message is not None else None,
                    "workspace_id": workspace_id,
                    "runtime_mode": runtime_mode,
                    "review_event_id": int(workspace.review_event_id),
                    "message_signature": workspace.message_signature,
                    "pending_status": workspace.pending_status,
                    "pending_intake_context": dict(workspace.pending_intake_context),
                    "pending_review_open": bool(workspace.pending_review_open),
                    "handoff_state": "loaded_reused",
                },
                "diagnostics": {
                    "bridge_ingest": True,
                    "handoff_reused": True,
                },
                "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
            }
        configured_gog_path, configured_account_email = _configured_gmail_values(settings_path)
        self._set_pending_intake(
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            context=context,
        )
        try:
            result = load_gmail_message_from_intake(
                intake_context=context,
                configured_gog_path=configured_gog_path,
                configured_account_email=configured_account_email,
            )
        except Exception:
            self._mark_pending_failure(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                context=context,
            )
            raise
        review_state = self._store_loaded_result(
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            result=result,
        )
        return {
            "status": "ok" if result.ok else result.classification or "failed",
            "normalized_payload": {
                "load_result": _serialize_load_result(result),
                "message": _serialize_message(result.message) if result.message is not None else None,
                "workspace_id": workspace_id,
                "runtime_mode": runtime_mode,
                "handoff_state": "new",
                **review_state,
            },
            "diagnostics": {
                "bridge_ingest": True,
            },
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }

    def preview_attachment(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        attachment_id: str,
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        load_result = workspace.loaded_result
        if load_result is None or not load_result.ok or load_result.message is None:
            raise ValueError("Load an exact Gmail message first.")
        attachment = next(
            (candidate for candidate in load_result.message.attachments if candidate.attachment_id == attachment_id),
            None,
        )
        if attachment is None:
            raise ValueError("Selected Gmail attachment is not available in the loaded message.")
        cached_path = workspace.preview_paths.get(attachment.attachment_id)
        cached_page_count = workspace.preview_page_counts.get(attachment.attachment_id)
        if isinstance(cached_path, Path) and cached_path.exists() and isinstance(cached_page_count, int):
            return {
                "status": "ok",
                "normalized_payload": {
                    "attachment": _serialize_attachment_candidate(attachment),
                    "page_count": int(cached_page_count),
                    "preview_path": _path_text(cached_path),
                },
                "diagnostics": {"reused_preview_cache": True},
                "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
            }
        preview_dir = workspace.ensure_preview_dir()
        result = download_gmail_attachment_via_gog(
            GmailAttachmentDownloadRequest(
                gog_path=load_result.gog_path or Path(""),
                account_email=load_result.account_email or "",
                message_id=load_result.message.message_id,
                attachment_id=attachment.attachment_id,
                output_dir=preview_dir,
                filename=attachment.filename,
            )
        )
        if not result.ok or result.saved_path is None:
            raise ValueError(result.message or "Failed to preview the selected Gmail attachment.")
        saved_path = result.saved_path.expanduser().resolve()
        workspace.preview_paths[attachment.attachment_id] = saved_path
        page_count = 1 if not _is_pdf_attachment(attachment) else 0
        if page_count > 0:
            workspace.preview_page_counts[attachment.attachment_id] = page_count
        return {
            "status": "ok",
            "normalized_payload": {
                "attachment": _serialize_attachment_candidate(attachment),
                "page_count": page_count if page_count > 0 else None,
                "preview_path": _path_text(saved_path),
            },
            "diagnostics": {
                "download_stdout": result.stdout,
                "download_stderr": result.stderr,
                "download_payload": result.payload or {},
            },
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }

    def prepare_session(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        outputs_dir: Path,
        workflow_kind: str,
        target_lang: str,
        output_dir_text: str,
        selections_payload: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        load_result = workspace.loaded_result
        if load_result is None or not load_result.ok or load_result.message is None:
            raise ValueError("Load an exact Gmail message before preparing attachments.")
        if load_result.gog_path is None or not _clean_text(load_result.account_email):
            raise ValueError("Gmail account resolution is unavailable for the loaded message.")
        workflow = _resolve_workflow_kind(workflow_kind)
        effective_output_dir = (
            require_writable_output_dir(Path(output_dir_text))
            if _clean_text(output_dir_text)
            else _default_output_dir(settings_path, outputs_dir)
        )
        attachments_by_id = {
            item.attachment_id: item for item in load_result.message.attachments
        }
        selections: list[GmailAttachmentSelection] = []
        for item in selections_payload:
            attachment_id = _clean_text(item.get("attachment_id"))
            attachment = attachments_by_id.get(attachment_id)
            if attachment is None:
                raise ValueError(f"Unknown Gmail attachment selection: {attachment_id or '(blank)'}.")
            start_page = int(item.get("start_page", 1) or 1)
            raw_page_count = item.get("page_count")
            page_count = None
            if raw_page_count not in (None, ""):
                try:
                    page_count = int(raw_page_count)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Page count must be an integer for Gmail attachment '{attachment.filename}'."
                    ) from None
            if workflow == GMAIL_WORKFLOW_INTERPRETATION:
                start_page = 1
            if start_page <= 0:
                raise ValueError(f"Start page must be >= 1 for Gmail attachment '{attachment.filename}'.")
            if page_count is not None and page_count <= 0:
                raise ValueError(
                    f"Page count must be >= 1 for Gmail attachment '{attachment.filename}'."
                )
            selections.append(
                GmailAttachmentSelection(
                    candidate=attachment,
                    start_page=start_page,
                    page_count=page_count,
                )
            )
        if not selections:
            raise ValueError("Select at least one Gmail attachment first.")

        if workflow == GMAIL_WORKFLOW_INTERPRETATION:
            if len(selections) != 1:
                raise ValueError("Interpretation notices require exactly one selected attachment.")
            if workspace.batch_session is not None:
                workspace.batch_session.cleanup()
                workspace.batch_session = None
            if workspace.interpretation_session is not None:
                workspace.interpretation_session.cleanup()
            session = prepare_gmail_interpretation_session(
                intake_context=load_result.intake_context,
                message=load_result.message,
                gog_path=load_result.gog_path,
                account_email=load_result.account_email or "",
                selected_attachment=selections[0],
                effective_output_dir=effective_output_dir,
                cached_preview_paths=workspace.preview_paths,
                cached_preview_page_counts=workspace.preview_page_counts,
            )
            seed_response = autofill_interpretation_from_notification_pdf(
                pdf_path=session.downloaded_attachment.saved_path,
                settings_path=settings_path,
            )
            seed_response = _seed_response_with_preferred_reply_email(
                seed_response,
                workspace.preferred_reply_email,
            )
            session.metadata_extraction = dict(seed_response.get("diagnostics", {}).get("metadata_extraction", {}))
            write_gmail_interpretation_session_report(session)
            workspace.interpretation_session = session
            workspace.current_batch_index = 0
            workspace.interpretation_seed_response = seed_response
            return {
                "status": "ok",
                "normalized_payload": {
                    "active_session": _serialize_interpretation_session(session),
                    "interpretation_seed": seed_response.get("normalized_payload"),
                },
                "diagnostics": {
                    "seed_diagnostics": seed_response.get("diagnostics", {}),
                },
                "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
            }

        if workspace.interpretation_session is not None:
            workspace.interpretation_session.cleanup()
            workspace.interpretation_session = None
        if workspace.batch_session is not None:
            workspace.batch_session.cleanup()
        session = prepare_gmail_batch_session(
            intake_context=load_result.intake_context,
            message=load_result.message,
            gog_path=load_result.gog_path,
            account_email=load_result.account_email or "",
            selected_attachments=tuple(selections),
            selected_target_lang=_clean_text(target_lang).upper() or "EN",
            effective_output_dir=effective_output_dir,
            cached_preview_paths=workspace.preview_paths,
            cached_preview_page_counts=workspace.preview_page_counts,
        )
        workspace.batch_session = session
        workspace.allow_report_restore = True
        workspace.current_batch_index = 0
        workspace.interpretation_seed_response = None
        return {
            "status": "ok",
            "normalized_payload": {
                "active_session": _serialize_batch_session(session, current_index=0),
                "suggested_translation_launch": _serialize_translation_launch(
                    session=session,
                    attachment=session.downloaded_attachments[0],
                    target_lang=session.selected_target_lang,
                    output_dir=session.effective_output_dir or effective_output_dir,
                ),
            },
            "diagnostics": {},
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }

    def confirm_current_batch_translation(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        job_log_db_path: Path,
        translation_jobs: "TranslationJobManager",
        job_id: str,
        form_values: Mapping[str, Any],
        row_id: object | None = None,
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        session = workspace.batch_session
        if session is None:
            raise ValueError("No Gmail translation batch is active in this workspace.")
        if workspace.current_batch_index >= len(session.downloaded_attachments):
            raise ValueError("All selected Gmail attachments have already been confirmed.")
        job = translation_jobs.get_job(job_id)
        if job is None:
            raise ValueError("Browser translation job was not found.")
        if str(job.get("job_kind", "") or "") != "translate":
            raise ValueError("Only completed translation jobs can be confirmed for Gmail batch attachments.")
        if str(job.get("status", "") or "") != "completed":
            raise ValueError("The selected browser translation job is not complete yet.")
        current_attachment = session.downloaded_attachments[workspace.current_batch_index]
        config = job.get("config", {}) if isinstance(job.get("config"), dict) else {}
        source_path = _clean_text(config.get("source_path"))
        if source_path and Path(source_path).expanduser().resolve() != current_attachment.saved_path.expanduser().resolve():
            raise ValueError("The selected translation job does not match the current Gmail attachment.")
        start_page = int(config.get("start_page", current_attachment.start_page) or current_attachment.start_page)
        if start_page != int(current_attachment.start_page):
            raise ValueError("The selected translation job used a different Gmail attachment start page.")
        result = job.get("result", {}) if isinstance(job.get("result"), dict) else {}
        save_seed = result.get("save_seed")
        if not isinstance(save_seed, dict):
            raise ValueError("The selected translation job does not have a Save-to-Job-Log seed yet.")
        from .translation_service import save_translation_row

        save_response = save_translation_row(
            settings_path=settings_path,
            job_log_db_path=job_log_db_path,
            form_values=dict(form_values),
            seed_payload=save_seed,
            row_id=row_id,
        )
        saved_result = dict(save_response.get("saved_result", {}))
        translated_docx_text = (
            _clean_text(saved_result.get("translated_docx_path"))
            or _clean_text(job.get("artifacts", {}).get("output_docx"))
            or _clean_text(job.get("artifacts", {}).get("partial_docx"))
        )
        if not translated_docx_text:
            raise ValueError("The translated DOCX for the confirmed Gmail attachment is unavailable.")
        translated_docx_path = Path(translated_docx_text).expanduser().resolve()
        if not translated_docx_path.exists():
            raise ValueError(f"Translated DOCX not found: {translated_docx_path}")
        staged_docx = stage_gmail_batch_translated_docx(session=session, translated_docx_path=translated_docx_path)
        run_dir_text = _clean_text(result.get("run_dir")) or _clean_text(job.get("artifacts", {}).get("run_dir"))
        run_dir = Path(run_dir_text).expanduser().resolve() if run_dir_text else translated_docx_path.parent
        confirmed_item = GmailBatchConfirmedItem(
            downloaded_attachment=current_attachment,
            translated_docx_path=translated_docx_path,
            staged_translated_docx_path=staged_docx,
            run_dir=run_dir,
            translated_word_count=int(saved_result.get("word_count", 0) or 0),
            joblog_row_id=int(saved_result.get("row_id", 0) or 0),
            run_id=_clean_text(saved_result.get("run_id")),
            case_number=_clean_text(saved_result.get("case_number")),
            case_entity=_clean_text(saved_result.get("case_entity")),
            case_city=_clean_text(saved_result.get("case_city")),
            court_email=_clean_text(saved_result.get("court_email")),
        )
        signature = confirmed_item.consistency_signature
        if session.consistency_signature is None:
            session.consistency_signature = signature
        elif session.consistency_signature != signature:
            raise ValueError("Selected attachments did not resolve to the same confirmed reply metadata.")
        session.confirmed_items.append(confirmed_item)
        workspace.current_batch_index += 1
        session.status = "confirmed"
        write_gmail_batch_session_report(session)
        next_launch = None
        if workspace.current_batch_index < len(session.downloaded_attachments):
            next_launch = _serialize_translation_launch(
                session=session,
                attachment=session.downloaded_attachments[workspace.current_batch_index],
                target_lang=session.selected_target_lang,
                output_dir=session.effective_output_dir or run_dir.parent,
            )
        return {
            "status": "ok",
            "normalized_payload": {
                "saved_result": save_response.get("saved_result", {}),
                "save_response": save_response,
                "active_session": _serialize_batch_session(session, current_index=workspace.current_batch_index),
                "confirmed_item": _serialize_confirmed_item(confirmed_item),
                "suggested_translation_launch": next_launch,
            },
            "diagnostics": {},
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }

    def finalize_batch(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        output_filename: str | None,
        profile_id: str | None,
        build_sha: str = "",
        asset_version: str = "",
    ) -> dict[str, Any]:
        preflight_response = self.preflight_batch_finalization(
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            settings_path=settings_path,
            force_refresh=False,
            build_sha=build_sha,
            asset_version=asset_version,
        )
        preflight_payload = dict(preflight_response.get("normalized_payload", {}))
        finalization_preflight = (
            dict(preflight_payload.get("finalization_preflight", {}))
            if isinstance(preflight_payload.get("finalization_preflight"), Mapping)
            else {}
        )
        if not bool(finalization_preflight.get("finalization_ready")):
            return preflight_response

        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        session = workspace.batch_session
        if session is None:
            raise ValueError("No Gmail translation batch is active in this workspace.")
        if len(session.confirmed_items) != len(session.downloaded_attachments):
            raise ValueError("Confirm every selected Gmail attachment before finalizing the batch reply.")
        from .honorarios_docx import (
            HonorariosKind,
            build_honorarios_draft,
            default_honorarios_filename,
            generate_honorarios_docx,
        )
        from .interpretation_service import (
            _current_profile,
            _profile_missing_fields,
            _run_pdf_export_with_retry,
            serialize_honorarios_draft,
        )

        _profiles, _primary_profile_id, profile = _current_profile(settings_path=settings_path, profile_id=profile_id)
        missing_profile_fields = _profile_missing_fields(profile)
        if missing_profile_fields:
            raise ValueError(
                "Selected profile is missing required fields: " + ", ".join(missing_profile_fields) + "."
            )
        signature = session.consistency_signature or gmail_batch_consistency_signature(
            case_number=session.confirmed_items[0].case_number,
            case_entity=session.confirmed_items[0].case_entity,
            case_city=session.confirmed_items[0].case_city,
            court_email=session.confirmed_items[0].court_email,
        )
        session.finalization_preflight = finalization_preflight
        session.finalization_state = "finalizing"
        session.draft_created = False
        session.draft_failure_reason = ""
        session.final_attachment_basenames = ()
        session.finalization_report_context = {}
        write_gmail_batch_session_report(session)
        draft = build_honorarios_draft(
            case_number=signature[0],
            word_count=sum(int(item.translated_word_count) for item in session.confirmed_items),
            case_entity=signature[1],
            case_city=signature[2],
            profile=profile,
        )
        effective_output_dir = (session.effective_output_dir or Path.cwd()).expanduser().resolve()
        effective_output_dir.mkdir(parents=True, exist_ok=True)
        requested_name = _clean_text(output_filename) or default_honorarios_filename(
            draft.case_number,
            kind=HonorariosKind.TRANSLATION,
        )
        requested_path = (effective_output_dir / requested_name).expanduser().resolve()
        docx_path = generate_honorarios_docx(draft, requested_path)
        pdf_export = _run_pdf_export_with_retry(docx_path=docx_path, pdf_path=docx_path.with_suffix(".pdf"))
        session.honorarios_requested = True
        session.requested_honorarios_path = requested_path
        session.requested_honorarios_pdf_path = requested_path.with_suffix(".pdf")
        session.actual_honorarios_path = docx_path
        session.pdf_export = dict(pdf_export)
        session.actual_honorarios_pdf_path = (
            Path(_clean_text(pdf_export.get("pdf_path"))).expanduser().resolve()
            if _clean_text(pdf_export.get("pdf_path"))
            else None
        )
        session.honorarios_auto_renamed = docx_path != requested_path
        if not pdf_export.get("ok"):
            _clear_word_pdf_export_cache_for_session(settings_path=settings_path, session_id=session.session_id)
            session.draft_preflight_result = "passed"
            session.finalization_state = "local_artifacts_ready"
            session.draft_created = False
            session.draft_failure_reason = _clean_text(pdf_export.get("failure_message")) or "Honorários PDF is unavailable."
            report_context = _persist_batch_finalization_report_context(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                build_sha=build_sha,
                asset_version=asset_version,
                session=session,
                status="local_only",
                retry_available=True,
                draft_payload=serialize_honorarios_draft(draft),
                actual_export=pdf_export,
            )
            write_gmail_batch_session_report(session)
            return {
                "status": "local_only",
                "normalized_payload": {
                    "docx_path": _path_text(docx_path),
                    "pdf_path": "",
                    "draft": serialize_honorarios_draft(draft),
                    "finalization_state": session.finalization_state,
                    "finalization_preflight": dict(session.finalization_preflight),
                    "finalization_report_context": report_context,
                    "retry_available": True,
                    "active_session": _serialize_batch_session(session, current_index=workspace.current_batch_index),
                },
                "diagnostics": {
                    "word_pdf_export": dict(session.finalization_preflight),
                    "pdf_export": pdf_export,
                },
                "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
            }

        configured_gog_path, configured_account_email = _configured_gmail_values(settings_path)
        prereqs = assess_gmail_draft_prereqs(
            configured_gog_path=configured_gog_path,
            configured_account_email=configured_account_email,
        )
        if not prereqs.ready:
            session.draft_preflight_result = "failed"
            session.finalization_state = "draft_failed"
            session.draft_created = False
            session.draft_failure_reason = prereqs.message
            report_context = _persist_batch_finalization_report_context(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                build_sha=build_sha,
                asset_version=asset_version,
                session=session,
                status="draft_unavailable",
                retry_available=True,
                draft_payload=serialize_honorarios_draft(draft),
                draft_prereqs=prereqs,
                actual_export=pdf_export,
            )
            write_gmail_batch_session_report(session)
            return {
                "status": "draft_unavailable",
                "normalized_payload": {
                    "docx_path": _path_text(docx_path),
                    "pdf_path": _clean_text(pdf_export.get("pdf_path")),
                    "draft": serialize_honorarios_draft(draft),
                    "draft_prereqs": _serialize_draft_prereqs(prereqs),
                    "finalization_state": session.finalization_state,
                    "finalization_preflight": dict(session.finalization_preflight),
                    "finalization_report_context": report_context,
                    "retry_available": True,
                    "active_session": _serialize_batch_session(session, current_index=workspace.current_batch_index),
                },
                "diagnostics": {
                    "word_pdf_export": dict(session.finalization_preflight),
                    "pdf_export": pdf_export,
                },
                "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
            }

        translated_docxs = validate_translated_docx_artifacts_for_gmail_draft(
            translated_docxs=[item.staged_translated_docx_path for item in session.confirmed_items],
            honorarios_pdf=Path(_clean_text(pdf_export.get("pdf_path"))).expanduser().resolve(),
        )
        request = build_gmail_batch_reply_request(
            gog_path=prereqs.gog_path or session.gog_path,
            account_email=prereqs.account_email or session.account_email,
            to_email=workspace.preferred_reply_email or signature[3],
            subject=session.message.subject,
            reply_to_message_id=session.message.message_id,
            translated_docxs=translated_docxs,
            honorarios_pdf=Path(_clean_text(pdf_export.get("pdf_path"))).expanduser().resolve(),
            profile=profile,
        )
        result = create_gmail_draft_via_gog(request)
        session.draft_preflight_result = "passed"
        session.final_attachment_basenames = tuple(path.name for path in request.attachments)
        session.draft_created = bool(result.ok)
        session.draft_failure_reason = "" if result.ok else _clean_text(result.message)
        session.finalization_state = "draft_ready" if result.ok else "draft_failed"
        session.status = "draft_ready" if result.ok else "draft_failed"
        report_context = _persist_batch_finalization_report_context(
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            build_sha=build_sha,
            asset_version=asset_version,
            session=session,
            status="ok" if result.ok else "draft_failed",
            retry_available=not bool(result.ok),
            draft_payload=serialize_honorarios_draft(draft),
            draft_prereqs=prereqs,
            draft_request=request,
            draft_result=result,
            actual_export=pdf_export,
        )
        write_gmail_batch_session_report(session)
        return {
            "status": "ok" if result.ok else "draft_failed",
            "normalized_payload": {
                "docx_path": _path_text(docx_path),
                "pdf_path": _clean_text(pdf_export.get("pdf_path")),
                "draft": serialize_honorarios_draft(draft),
                "draft_prereqs": _serialize_draft_prereqs(prereqs),
                "gmail_draft_request": _serialize_draft_request(request),
                "gmail_draft_result": _serialize_draft_result(result),
                "finalization_state": session.finalization_state,
                "finalization_preflight": dict(session.finalization_preflight),
                "finalization_report_context": report_context,
                "retry_available": not bool(result.ok),
                "active_session": _serialize_batch_session(session, current_index=workspace.current_batch_index),
            },
            "diagnostics": {
                "word_pdf_export": dict(session.finalization_preflight),
                "pdf_export": pdf_export,
            },
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }

    def preflight_batch_finalization(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        force_refresh: bool = False,
        build_sha: str = "",
        asset_version: str = "",
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        session = workspace.batch_session
        if session is None:
            raise ValueError("No Gmail translation batch is active in this workspace.")
        if len(session.confirmed_items) != len(session.downloaded_attachments):
            raise ValueError("Confirm every selected Gmail attachment before finalizing the batch reply.")
        readiness = assess_word_pdf_export_readiness(
            cache_scope=f"gmail_batch_finalization::{_word_pdf_cache_scope_token(settings_path)}::{session.session_id}",
            launch_timeout_seconds=8.0,
            export_timeout_seconds=45.0,
            force_refresh=force_refresh,
        )
        previous_state = session.finalization_state.strip()
        session.finalization_preflight = dict(readiness)
        if bool(readiness.get("finalization_ready")):
            if previous_state not in {"local_artifacts_ready", "draft_failed", "draft_ready"}:
                session.finalization_state = "ready_to_finalize"
                session.finalization_report_context = {}
        elif previous_state not in {"local_artifacts_ready", "draft_failed", "draft_ready"}:
            session.finalization_state = "blocked_word_pdf_export"
        if not bool(readiness.get("finalization_ready")):
            session.draft_preflight_result = "blocked_word_pdf_export"
            session.draft_created = False
            session.draft_failure_reason = _clean_text(readiness.get("message")) or "Word PDF export is unavailable."
            report_context = _persist_batch_finalization_report_context(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                build_sha=build_sha,
                asset_version=asset_version,
                session=session,
                status="blocked_word_pdf_export",
                retry_available=False,
                actual_export=session.pdf_export,
            )
        else:
            report_context = None
        write_gmail_batch_session_report(session)
        normalized_payload = {
            "finalization_state": session.finalization_state,
            "finalization_preflight": dict(readiness),
            "retry_available": False,
            "active_session": _serialize_batch_session(session, current_index=workspace.current_batch_index),
        }
        if report_context:
            normalized_payload["finalization_report_context"] = report_context
        return {
            "status": "ok" if bool(readiness.get("finalization_ready")) else "blocked_word_pdf_export",
            "normalized_payload": normalized_payload,
            "diagnostics": {"word_pdf_export": dict(readiness)},
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }

    def finalize_interpretation(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        settings_path: Path,
        form_values: Mapping[str, Any],
        profile_id: str | None,
        service_same_checked: bool,
        output_filename: str | None,
    ) -> dict[str, Any]:
        workspace = self._workspace(runtime_mode=runtime_mode, workspace_id=workspace_id)
        session = workspace.interpretation_session
        if session is None:
            raise ValueError("No Gmail interpretation notice is active in this workspace.")
        export_response = export_interpretation_honorarios(
            settings_path=settings_path,
            outputs_dir=session.effective_output_dir or Path.cwd(),
            form_values=form_values,
            profile_id=profile_id,
            output_filename=output_filename,
            service_same_checked=service_same_checked,
        )
        normalized_payload = dict(export_response.get("normalized_payload", {}))
        diagnostics = dict(export_response.get("diagnostics", {}))
        pdf_export = dict(diagnostics.get("pdf_export", {}))
        session.honorarios_requested = True
        session.actual_honorarios_path = Path(normalized_payload["docx_path"]).expanduser().resolve()
        session.actual_honorarios_pdf_path = (
            Path(_clean_text(normalized_payload.get("pdf_path"))).expanduser().resolve()
            if _clean_text(normalized_payload.get("pdf_path"))
            else None
        )
        session.pdf_export = pdf_export
        if export_response.get("status") != "ok":
            session.draft_created = False
            session.draft_failure_reason = _clean_text(pdf_export.get("failure_message")) or "Honorários PDF is unavailable."
            write_gmail_interpretation_session_report(session)
            return {
                "status": "local_only",
                "normalized_payload": {
                    **normalized_payload,
                    "active_session": _serialize_interpretation_session(session),
                },
                "diagnostics": diagnostics,
                "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
            }

        configured_gog_path, configured_account_email = _configured_gmail_values(settings_path)
        prereqs = assess_gmail_draft_prereqs(
            configured_gog_path=configured_gog_path,
            configured_account_email=configured_account_email,
        )
        if not prereqs.ready:
            session.draft_created = False
            session.draft_failure_reason = prereqs.message
            write_gmail_interpretation_session_report(session)
            return {
                "status": "draft_unavailable",
                "normalized_payload": {
                    **normalized_payload,
                    "draft_prereqs": _serialize_draft_prereqs(prereqs),
                    "active_session": _serialize_interpretation_session(session),
                },
                "diagnostics": diagnostics,
                "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
            }

        _profiles, _primary_profile_id, profile = _current_profile(settings_path=settings_path, profile_id=profile_id)
        resolved_reply_email = workspace.preferred_reply_email or _clean_text(form_values.get("court_email"))
        request = build_interpretation_gmail_reply_request(
            gog_path=prereqs.gog_path or session.gog_path,
            account_email=prereqs.account_email or session.account_email,
            to_email=resolved_reply_email,
            subject=session.message.subject,
            reply_to_message_id=session.message.message_id,
            honorarios_pdf=Path(_clean_text(normalized_payload.get("pdf_path"))).expanduser().resolve(),
            profile=profile,
        )
        result = create_gmail_draft_via_gog(request)
        session.draft_created = bool(result.ok)
        session.draft_failure_reason = "" if result.ok else _clean_text(result.message)
        session.final_attachment_basenames = tuple(path.name for path in request.attachments)
        session.status = "draft_ready" if result.ok else "draft_failed"
        write_gmail_interpretation_session_report(session)
        return {
            "status": "ok" if result.ok else "draft_failed",
            "normalized_payload": {
                **normalized_payload,
                "draft_prereqs": _serialize_draft_prereqs(prereqs),
                "gmail_draft_request": _serialize_draft_request(request),
                "gmail_draft_result": _serialize_draft_result(result),
                "active_session": _serialize_interpretation_session(session),
            },
            "diagnostics": diagnostics,
            "capability_flags": build_gmail_browser_capability_flags(settings_path=settings_path),
        }
