"""Browser Arabic DOCX review gate state shared across translation and Gmail flows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import os
import threading
import time
from typing import Any, Mapping

from .word_automation import (
    WordAutomationResult,
    align_right_and_save_docx_in_word,
    open_docx_in_word,
)

_DEFAULT_POLL_INTERVAL_MS = 500
_DEFAULT_QUIET_PERIOD_MS = 1500


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _read_fingerprint(path: Path) -> tuple[int, int] | None:
    try:
        stat = path.expanduser().resolve().stat()
    except OSError:
        return None
    return (int(stat.st_mtime_ns), int(stat.st_size))


def _word_result_payload(result: WordAutomationResult) -> dict[str, Any]:
    return {
        "ok": bool(result.ok),
        "action": result.action,
        "message": result.message,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "command": list(result.command),
        "failure_code": result.failure_code,
        "details": result.details,
        "elapsed_ms": int(result.elapsed_ms),
        "failure_phase": result.failure_phase,
        "helper_pid": int(result.helper_pid),
        "cleanup_attempted": bool(result.cleanup_attempted),
        "cleanup_succeeded": bool(result.cleanup_succeeded),
        "cleanup_details": result.cleanup_details,
    }


def _completion_key_from_job(job: Mapping[str, Any]) -> str:
    job_id = _clean_text(job.get("job_id"))
    job_kind = _clean_text(job.get("job_kind")) or "translate"
    if not job_id:
        raise ValueError("Arabic DOCX review requires a completed browser translation job id.")
    return f"job:{job_id}:{job_kind}"


def _resolve_review_target(job: Mapping[str, Any]) -> tuple[str, Path]:
    if _clean_text(job.get("job_kind")) != "translate":
        raise ValueError("Arabic DOCX review only applies to translation jobs.")
    if _clean_text(job.get("status")) != "completed":
        raise ValueError("Arabic DOCX review only applies to completed translation jobs.")
    result = job.get("result")
    if not isinstance(result, Mapping):
        raise ValueError("Completed translation job result is unavailable for Arabic DOCX review.")
    save_seed = result.get("save_seed")
    if not isinstance(save_seed, Mapping):
        raise ValueError("Completed translation job is missing the Save-to-Job-Log seed required for Arabic review.")
    target_lang = _clean_text(save_seed.get("target_lang")).upper() or _clean_text(
        (job.get("config") or {}).get("target_lang") if isinstance(job.get("config"), Mapping) else ""
    ).upper()
    if target_lang != "AR":
        raise ValueError("Arabic DOCX review only applies to completed Arabic translation jobs.")
    output_docx_text = _clean_text(save_seed.get("output_docx"))
    if not output_docx_text:
        raise ValueError("Arabic DOCX review requires the durable translated DOCX from save_seed.output_docx.")
    docx_path = Path(output_docx_text).expanduser().resolve()
    if not docx_path.exists() or not docx_path.is_file():
        raise ValueError(f"Arabic DOCX review file was not found: {docx_path}")
    return (target_lang, docx_path)


def job_requires_arabic_review(job: Mapping[str, Any]) -> bool:
    if not isinstance(job, Mapping):
        return False
    try:
        _resolve_review_target(job)
    except ValueError:
        return False
    return True


@dataclass(slots=True)
class _ArabicReviewSession:
    runtime_mode: str
    workspace_id: str
    job_id: str
    completion_key: str
    docx_path: Path
    poll_interval_ms: int
    quiet_period_ms: int
    created_at: str
    updated_at: str
    baseline_fingerprint: tuple[int, int] | None
    last_seen_fingerprint: tuple[int, int] | None
    fingerprint_changed: bool = False
    save_detected: bool = False
    last_change_monotonic: float | None = None
    resolved: bool = False
    resolution: str = ""
    status: str = "required"
    message: str = (
        "Arabic DOCX review is required before Save-to-Job-Log or Gmail confirmation can continue. "
        "Open the durable DOCX in Word, align or edit it manually, then save."
    )
    fallback_used: bool = False
    opened_once: bool = False


class ArabicDocxReviewManager:
    """Keeps per-workspace Arabic DOCX review sessions inside the browser-app runtime."""

    def __init__(
        self,
        *,
        poll_interval_ms: int = _DEFAULT_POLL_INTERVAL_MS,
        quiet_period_ms: int = _DEFAULT_QUIET_PERIOD_MS,
    ) -> None:
        self._poll_interval_ms = max(100, int(poll_interval_ms))
        self._quiet_period_ms = max(self._poll_interval_ms, int(quiet_period_ms))
        self._lock = threading.RLock()
        self._sessions: dict[tuple[str, str, str], _ArabicReviewSession] = {}

    def _session_key(self, runtime_mode: str, workspace_id: str, completion_key: str) -> tuple[str, str, str]:
        return (
            _clean_text(runtime_mode).lower() or "live",
            _clean_text(workspace_id) or "workspace-1",
            _clean_text(completion_key),
        )

    def _resolve_or_create_session(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        job: Mapping[str, Any],
        completion_key: str | None = None,
    ) -> _ArabicReviewSession:
        resolved_completion_key = _clean_text(completion_key) or _completion_key_from_job(job)
        _target_lang, docx_path = _resolve_review_target(job)
        job_id = _clean_text(job.get("job_id"))
        key = self._session_key(runtime_mode, workspace_id, resolved_completion_key)
        with self._lock:
            existing = self._sessions.get(key)
            if existing is not None:
                existing.job_id = job_id
                existing.docx_path = docx_path
                self._refresh_session_locked(existing)
                return existing
            now_iso = _utc_now_iso()
            baseline = _read_fingerprint(docx_path)
            session = _ArabicReviewSession(
                runtime_mode=key[0],
                workspace_id=key[1],
                job_id=job_id,
                completion_key=resolved_completion_key,
                docx_path=docx_path,
                poll_interval_ms=self._poll_interval_ms,
                quiet_period_ms=self._quiet_period_ms,
                created_at=now_iso,
                updated_at=now_iso,
                baseline_fingerprint=baseline,
                last_seen_fingerprint=baseline,
            )
            self._sessions[key] = session
            self._refresh_session_locked(session)
            return session

    def _latest_workspace_session_locked(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        unresolved_only: bool = False,
    ) -> _ArabicReviewSession | None:
        runtime_key = _clean_text(runtime_mode).lower() or "live"
        workspace_key = _clean_text(workspace_id) or "workspace-1"
        matches = [
            session
            for session in self._sessions.values()
            if session.runtime_mode == runtime_key
            and session.workspace_id == workspace_key
            and (not unresolved_only or not session.resolved)
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: item.updated_at, reverse=True)
        return matches[0]

    def _resolve_session_locked(self, session: _ArabicReviewSession, *, resolution: str, message: str) -> None:
        session.resolved = True
        session.resolution = resolution
        session.status = "resolved"
        session.message = message
        session.fingerprint_changed = session.fingerprint_changed or session.save_detected
        session.updated_at = _utc_now_iso()

    def _refresh_session_locked(self, session: _ArabicReviewSession) -> None:
        if session.resolved:
            return
        current = _read_fingerprint(session.docx_path)
        if current is None:
            session.status = "missing"
            session.message = f"Arabic DOCX review file is unavailable: {session.docx_path}"
            session.updated_at = _utc_now_iso()
            return
        if session.baseline_fingerprint is None:
            session.baseline_fingerprint = current
            session.last_seen_fingerprint = current
            session.updated_at = _utc_now_iso()
            return
        if current != session.last_seen_fingerprint:
            session.last_seen_fingerprint = current
            if current != session.baseline_fingerprint or session.save_detected:
                session.fingerprint_changed = True
                session.save_detected = True
                session.last_change_monotonic = time.monotonic()
                session.status = "waiting_for_save"
                session.message = "Save detected. Waiting for Word to finish writing..."
                session.updated_at = _utc_now_iso()
                return
        if session.save_detected and session.last_change_monotonic is not None:
            elapsed_ms = (time.monotonic() - session.last_change_monotonic) * 1000.0
            if elapsed_ms >= float(session.quiet_period_ms):
                self._resolve_session_locked(
                    session,
                    resolution="saved",
                    message="Arabic DOCX save detected. Review gate resolved.",
                )

    def _payload_from_session_locked(self, session: _ArabicReviewSession) -> dict[str, Any]:
        self._refresh_session_locked(session)
        return {
            "required": True,
            "resolved": bool(session.resolved),
            "resolution": session.resolution,
            "status": session.status,
            "message": session.message,
            "docx_path": str(session.docx_path),
            "fingerprint_changed": bool(session.fingerprint_changed),
            "save_detected": bool(session.save_detected),
            "fallback_used": bool(session.fallback_used),
            "job_id": session.job_id,
            "completion_key": session.completion_key,
            "poll_interval_ms": int(session.poll_interval_ms),
            "quiet_period_ms": int(session.quiet_period_ms),
            "auto_open_pending": not session.opened_once and not session.resolved,
        }

    def idle_payload(self) -> dict[str, Any]:
        return {
            "required": False,
            "resolved": True,
            "resolution": "",
            "status": "not_required",
            "message": "",
            "docx_path": "",
            "fingerprint_changed": False,
            "save_detected": False,
            "fallback_used": False,
            "job_id": "",
            "completion_key": "",
            "poll_interval_ms": int(self._poll_interval_ms),
            "quiet_period_ms": int(self._quiet_period_ms),
            "auto_open_pending": False,
        }

    def state_for_workspace(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        job: Mapping[str, Any] | None = None,
        completion_key: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if job is not None:
                session = self._resolve_or_create_session(
                    runtime_mode=runtime_mode,
                    workspace_id=workspace_id,
                    job=job,
                    completion_key=completion_key,
                )
                return self._payload_from_session_locked(session)
            if completion_key:
                session = self._sessions.get(self._session_key(runtime_mode, workspace_id, completion_key))
            else:
                session = self._latest_workspace_session_locked(
                    runtime_mode=runtime_mode,
                    workspace_id=workspace_id,
                    unresolved_only=True,
                )
            if session is None:
                return self.idle_payload()
            return self._payload_from_session_locked(session)

    def require_resolved(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        job: Mapping[str, Any],
        completion_key: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            session = self._resolve_or_create_session(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                job=job,
                completion_key=completion_key,
            )
            payload = self._payload_from_session_locked(session)
            if payload["required"] and not payload["resolved"]:
                raise ValueError(payload["message"] or "Arabic DOCX review is still required.")
            return payload

    def open_review(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        job: Mapping[str, Any],
        completion_key: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        diagnostics: dict[str, Any] = {}
        with self._lock:
            session = self._resolve_or_create_session(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                job=job,
                completion_key=completion_key,
            )
            session.opened_once = True
            result = open_docx_in_word(session.docx_path)
            diagnostics["word_action"] = _word_result_payload(result)
            if result.ok:
                session.status = "awaiting_save"
                session.message = (
                    "DOCX opened in Word. Align or edit it manually, then save and the app will continue automatically."
                )
                session.fallback_used = False
                session.updated_at = _utc_now_iso()
                return (self._payload_from_session_locked(session), diagnostics)

            fallback_message = _clean_text(result.message) or "Word automation failed."
            if os.name == "nt" and hasattr(os, "startfile"):
                try:
                    os.startfile(str(session.docx_path))  # type: ignore[attr-defined]
                except Exception as exc:  # noqa: BLE001
                    diagnostics["fallback_error"] = str(exc)
                else:
                    session.status = "awaiting_save"
                    session.message = (
                        "Word automation failed, but the DOCX was opened with the default Windows handler. "
                        "Align or edit it manually, then save and the app will continue automatically."
                    )
                    session.fallback_used = True
                    session.updated_at = _utc_now_iso()
                    return (self._payload_from_session_locked(session), diagnostics)

            session.status = "attention"
            session.message = (
                f"{fallback_message} Use 'Continue now' after saving manually if detection misses."
            )
            session.updated_at = _utc_now_iso()
            return (self._payload_from_session_locked(session), diagnostics)

    def align_right_and_save(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        job: Mapping[str, Any],
        completion_key: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        diagnostics: dict[str, Any] = {}
        with self._lock:
            session = self._resolve_or_create_session(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                job=job,
                completion_key=completion_key,
            )
            result = align_right_and_save_docx_in_word(session.docx_path)
            diagnostics["word_action"] = _word_result_payload(result)
            if result.ok:
                session.fingerprint_changed = True
                session.save_detected = True
                self._resolve_session_locked(
                    session,
                    resolution="align_right_save",
                    message="DOCX aligned right and saved in Word. Review gate resolved.",
                )
                return (self._payload_from_session_locked(session), diagnostics)
            session.status = "attention"
            session.message = (
                f"{_clean_text(result.message) or 'Align Right + Save failed.'} "
                "Keep editing manually in Word and save, or use Continue now."
            )
            session.updated_at = _utc_now_iso()
            return (self._payload_from_session_locked(session), diagnostics)

    def continue_review(
        self,
        *,
        runtime_mode: str,
        workspace_id: str,
        job: Mapping[str, Any],
        continuation: str,
        completion_key: str | None = None,
    ) -> dict[str, Any]:
        normalized = _clean_text(continuation)
        if normalized not in {"continue_now", "continue_without_changes"}:
            raise ValueError("Arabic DOCX review continuation must be continue_now or continue_without_changes.")
        with self._lock:
            session = self._resolve_or_create_session(
                runtime_mode=runtime_mode,
                workspace_id=workspace_id,
                job=job,
                completion_key=completion_key,
            )
            message = (
                "Arabic DOCX review marked complete. Continuing now."
                if normalized == "continue_now"
                else "Arabic DOCX review marked complete without changes."
            )
            self._resolve_session_locked(session, resolution=normalized, message=message)
            return self._payload_from_session_locked(session)


__all__ = ["ArabicDocxReviewManager", "job_requires_arabic_review"]
