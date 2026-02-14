"""Run diagnostics event collection and Markdown report rendering."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__

_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._\-]{8,}\b"),
    re.compile(r"(?i)\b(authorization)\s*:\s*[^\s,;]+"),
    re.compile(r"(?i)\b(x-api-key|api[-_ ]?key)\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{8,}['\"]?"),
)

_FORBIDDEN_EVENT_KEYS = {
    "prompt_text",
    "raw_output",
    "request_body",
    "request_payload",
    "authorization",
    "api_key",
    "openai_api_key",
    "ocr_api_key",
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def sanitize_text(value: str) -> str:
    cleaned = value
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[REDACTED]", cleaned)
    return cleaned


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, nested in value.items():
            key_text = str(key)
            if key_text.strip().lower() in _FORBIDDEN_EVENT_KEYS:
                continue
            output[key_text] = sanitize_value(nested)
        return output
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_value(item) for item in value]
    return value


class RunEventCollector:
    """Collect structured run events in memory and JSONL on disk."""

    def __init__(self, *, run_dir: Path, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self._run_dir = run_dir
        self._events_path = run_dir / "run_events.jsonl"
        self._events: list[dict[str, Any]] = []
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def events_path(self) -> Path:
        return self._events_path

    def add_event(
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
        if not self._enabled:
            return
        payload: dict[str, Any] = {
            "timestamp": _utc_now(),
            "event_type": event_type,
            "stage": stage,
            "page_index": page_index,
            "duration_ms": round(float(duration_ms), 3) if duration_ms is not None else None,
            "counters": sanitize_value(counters or {}),
            "decisions": sanitize_value(decisions or {}),
            "warning": sanitize_text(warning) if warning else None,
            "error": sanitize_text(error) if error else None,
            "details": sanitize_value(details or {}),
        }
        with self._lock:
            self._events.append(payload)
            try:
                self._events_path.parent.mkdir(parents=True, exist_ok=True)
                with self._events_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(payload, ensure_ascii=False))
                    fh.write("\n")
            except Exception:
                # Do not fail translation due to diagnostics persistence failures.
                pass

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._events]


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def load_events_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in lines:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _truncate(value: str, *, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    if max_chars <= 3:
        return value[:max_chars]
    return value[: max_chars - 3] + "..."


def _extract_translated_snippets(run_dir: Path, *, per_page_max_chars: int) -> list[dict[str, Any]]:
    pages_dir = run_dir / "pages"
    snippets: list[dict[str, Any]] = []
    if not pages_dir.exists() or not pages_dir.is_dir():
        return snippets
    for page_file in sorted(pages_dir.glob("page_*.txt")):
        page_suffix = page_file.stem.replace("page_", "")
        try:
            page_number = int(page_suffix)
        except ValueError:
            continue
        try:
            text = page_file.read_text(encoding="utf-8")
        except OSError:
            continue
        sanitized = sanitize_text(text).replace("\r\n", "\n").strip()
        snippet = _truncate(sanitized, max_chars=per_page_max_chars)
        snippets.append(
            {
                "page_number": page_number,
                "chars": len(snippet),
                "snippet": snippet,
            }
        )
    return snippets


def _safe_file_name(path_text: str | None) -> str:
    if not path_text:
        return ""
    return Path(path_text).name


def _safe_file_size(path_text: str | None) -> int | None:
    if not path_text:
        return None
    try:
        target = Path(path_text)
        if not target.exists() or not target.is_file():
            return None
        return int(target.stat().st_size)
    except OSError:
        return None


def _resolve_commit_hash() -> str | None:
    env_value = (
        os.getenv("LEGALPDF_COMMIT_HASH", "").strip()
        or os.getenv("GIT_COMMIT", "").strip()
    )
    repo_root = Path(__file__).resolve().parents[2]
    try:
        raw = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            stderr=subprocess.DEVNULL,
            timeout=1.5,
            text=True,
        ).strip()
        if raw:
            return raw
    except Exception:
        pass
    return env_value or None


def _sorted_pages_from_run_state(run_state_payload: dict[str, Any]) -> list[tuple[int, dict[str, Any]]]:
    pages_obj = run_state_payload.get("pages")
    if not isinstance(pages_obj, dict):
        return []
    rows: list[tuple[int, dict[str, Any]]] = []
    for key, value in pages_obj.items():
        try:
            page_number = int(str(key))
        except ValueError:
            continue
        if isinstance(value, dict):
            rows.append((page_number, value))
    rows.sort(key=lambda row: row[0])
    return rows


def _slice_events_for_run(events: list[dict[str, Any]], *, run_id: str) -> list[dict[str, Any]]:
    if not events or run_id.strip() == "":
        return events
    start_index: int | None = None
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        if str(event.get("event_type", "") or "") != "run_started":
            continue
        details = event.get("details")
        if not isinstance(details, dict):
            continue
        if str(details.get("run_id", "") or "") == run_id:
            start_index = index
            break
    if start_index is None:
        return events
    end_index = len(events)
    for index in range(start_index + 1, len(events)):
        event = events[index]
        if not isinstance(event, dict):
            continue
        if str(event.get("event_type", "") or "") == "run_started":
            end_index = index
            break
    return events[start_index:end_index]


def _build_timeline_lines(events: list[dict[str, Any]], *, limit: int | None = None) -> list[str]:
    rows = list(events)
    rows.sort(key=lambda item: str(item.get("timestamp", "")))
    if limit is not None and limit > 0:
        rows = rows[:limit]
    lines: list[str] = []
    for item in rows:
        stamp = str(item.get("timestamp", "") or "-")
        event_type = str(item.get("event_type", "") or "event")
        stage = str(item.get("stage", "") or "-")
        page_index = item.get("page_index")
        duration_ms = item.get("duration_ms")
        summary_parts = [f"{stamp} | {event_type} | stage={stage}"]
        if isinstance(page_index, int):
            summary_parts.append(f"page={page_index}")
        if isinstance(duration_ms, (int, float)):
            summary_parts.append(f"duration_ms={float(duration_ms):.3f}")
        error = item.get("error")
        warning = item.get("warning")
        if isinstance(warning, str) and warning.strip():
            summary_parts.append(f"warning={sanitize_text(warning.strip())}")
        if isinstance(error, str) and error.strip():
            summary_parts.append(f"error={sanitize_text(error.strip())}")
        lines.append("- " + " | ".join(summary_parts))
    if not lines:
        lines.append("- (no timeline events recorded)")
    return lines


def _ocr_summary_line(pipeline_obj: dict[str, Any]) -> str:
    ocr_mode = str(pipeline_obj.get("ocr_mode", "") or "").strip().lower()
    ocr_requested = bool(pipeline_obj.get("ocr_requested", False))
    ocr_used = bool(pipeline_obj.get("ocr_used", False))
    ocr_provider_configured = bool(pipeline_obj.get("ocr_provider_configured", False))
    ocr_preflight_checked = bool(pipeline_obj.get("ocr_preflight_checked", False))
    ocr_requested_pages = int(pipeline_obj.get("ocr_requested_pages", 0) or 0)
    ocr_used_pages = int(pipeline_obj.get("ocr_used_pages", 0) or 0)
    ocr_required_pages = int(pipeline_obj.get("ocr_required_pages", 0) or 0)
    ocr_helpful_pages = int(pipeline_obj.get("ocr_helpful_pages", 0) or 0)
    ocr_required_unavailable_pages = int(pipeline_obj.get("ocr_required_unavailable_pages", 0) or 0)

    if ocr_mode == "off":
        return "- OCR disabled (mode=off)."
    if ocr_used:
        if ocr_required_unavailable_pages > 0:
            return (
                f"- WARNING: OCR required but unavailable on `{ocr_required_unavailable_pages}` page(s); "
                "direct-text fallback was used for those pages."
            )
        return (
            f"- OCR used on `{ocr_used_pages}` page(s) "
            f"(requested pages: `{ocr_requested_pages}`, required pages: `{ocr_required_pages}`, "
            f"helpful pages: `{ocr_helpful_pages}`, provider configured: `{ocr_provider_configured}`)."
        )
    if ocr_required_unavailable_pages > 0:
        return (
            f"- WARNING: OCR required on `{ocr_required_unavailable_pages}` page(s) but OCR could not run; "
            "direct-text fallback was used."
        )
    if ocr_requested:
        return "- OCR was requested but not used after fallback decisions."
    if ocr_helpful_pages > 0 and not ocr_provider_configured:
        return (
            f"- OCR not used; `{ocr_helpful_pages}` page(s) were marked as helpful for OCR, "
            "but local OCR was unavailable so direct text was kept."
        )
    if not ocr_preflight_checked:
        return "- OCR not used; OCR not requested by routing."
    if not ocr_provider_configured:
        return "- OCR not used; OCR provider not configured (not needed)."
    return "- OCR not used; direct text route was sufficient."


def _image_mode_optimization_hint(
    *,
    target_language: str,
    image_mode: str,
    pages: list[tuple[int, dict[str, Any]]],
) -> str:
    if image_mode.strip().lower() != "always":
        return ""
    if target_language.strip().upper() not in {"EN", "FR"}:
        return ""
    if not pages:
        return ""
    for _, page in pages:
        source_route = str(page.get("source_route", "") or "").strip().lower()
        try:
            extracted_chars = int(page.get("extracted_text_chars", -1) or -1)
        except Exception:
            return ""
        # EN/FR auto-image attaches only on extraction failure or near-empty text.
        if source_route != "direct_text" or extracted_chars < 20:
            return ""
    return (
        "image_mode=always attached images on all pages while EN/FR auto-image "
        "heuristics would skip image attachments for this run; consider image_mode=auto."
    )


def build_run_report_payload(
    *,
    run_dir: Path,
    admin_mode: bool,
    include_sanitized_snippets: bool,
) -> dict[str, Any]:
    run_state = load_json_file(run_dir / "run_state.json")
    run_summary = load_json_file(run_dir / "run_summary.json")
    run_id = str(run_state.get("run_started_at") or run_summary.get("run_id") or run_dir.name)
    all_events = load_events_jsonl(run_dir / "run_events.jsonl")
    events = _slice_events_for_run(all_events, run_id=run_id)

    pages = _sorted_pages_from_run_state(run_state)
    per_page: list[dict[str, Any]] = []
    api_calls_total = 0
    transport_retries_total = 0
    backoff_wait_seconds_total = 0.0
    rate_limit_hits = 0
    page_failures: list[int] = []
    ocr_requested_pages = 0
    ocr_used_pages = 0
    ocr_required_pages = 0
    ocr_helpful_pages = 0
    ocr_required_unavailable_pages = 0
    pt_language_leak_failures = 0
    pt_language_leak_retries = 0

    for page_number, page in pages:
        status = str(page.get("status", "") or "").strip().lower()
        if status == "failed":
            page_failures.append(page_number)
        api_calls = int(page.get("api_calls_count", 0) or 0)
        retries = int(page.get("transport_retries_count", 0) or 0)
        backoff_seconds = float(page.get("backoff_wait_seconds_total", 0.0) or 0.0)
        rate_limited = bool(page.get("rate_limit_hit", False))
        api_calls_total += api_calls
        transport_retries_total += retries
        backoff_wait_seconds_total += backoff_seconds
        if rate_limited:
            rate_limit_hits += 1
        ocr_request_reason = str(page.get("ocr_request_reason", "not_requested") or "not_requested").strip().lower()
        ocr_requested = bool(page.get("ocr_requested", False))
        ocr_used = bool(page.get("ocr_used", False)) or str(page.get("source_route", "")).strip().lower() == "ocr"
        if ocr_requested:
            ocr_requested_pages += 1
        if ocr_used:
            ocr_used_pages += 1
        if ocr_request_reason == "required":
            ocr_required_pages += 1
            ocr_failed_reason = str(page.get("ocr_failed_reason", "") or "").strip().lower()
            if (not ocr_used) and (
                "unavailable" in ocr_failed_reason
                or "not_configured" in ocr_failed_reason
                or not bool(page.get("ocr_provider_configured", False))
            ):
                ocr_required_unavailable_pages += 1
        elif ocr_request_reason == "helpful":
            ocr_helpful_pages += 1
        retry_reason_text = str(page.get("retry_reason", "") or "").strip().lower()
        error_text = str(page.get("error", "") or "").strip().lower()
        if retry_reason_text == "pt_language_leak":
            pt_language_leak_retries += 1
            if status == "failed" and error_text == "compliance_failure":
                pt_language_leak_failures += 1
        raw_signals = page.get("extraction_quality_signals", [])
        extraction_signals = raw_signals if isinstance(raw_signals, list) else []
        row = {
            "page_number": page_number,
            "status": status,
            "source_route": str(page.get("source_route", "") or ""),
            "source_route_reason": str(page.get("source_route_reason", "") or ""),
            "image_used": bool(page.get("image_used", False)),
            "image_decision_reason": str(page.get("image_decision_reason", "") or ""),
            "ocr_requested": ocr_requested,
            "ocr_request_reason": ocr_request_reason,
            "ocr_used": ocr_used,
            "ocr_provider_configured": bool(page.get("ocr_provider_configured", False)),
            "ocr_engine_used": str(page.get("ocr_engine_used", "") or ""),
            "ocr_failed_reason": str(page.get("ocr_failed_reason", "") or ""),
            "extraction_quality_signals": extraction_signals,
            "wall_seconds": float(page.get("wall_seconds", 0.0) or 0.0),
            "extract_seconds": float(page.get("extract_seconds", 0.0) or 0.0),
            "ocr_seconds": float(page.get("ocr_seconds", 0.0) or 0.0),
            "translate_seconds": float(page.get("translate_seconds", 0.0) or 0.0),
            "api_calls_count": api_calls,
            "transport_retries_count": retries,
            "backoff_wait_seconds_total": round(backoff_seconds, 3),
            "rate_limit_hit": rate_limited,
            "input_tokens": int(page.get("input_tokens", 0) or 0),
            "output_tokens": int(page.get("output_tokens", 0) or 0),
            "reasoning_tokens": int(page.get("reasoning_tokens", 0) or 0),
            "total_tokens": int(page.get("total_tokens", 0) or 0),
            "estimated_cost": page.get("estimated_cost"),
            "exception_class": str(page.get("exception_class", "") or ""),
            "error": str(page.get("error", "") or ""),
            "retry_reason": str(page.get("retry_reason", "") or ""),
        }
        per_page.append(sanitize_value(row))

    totals_obj = run_summary.get("totals")
    counts_obj = run_summary.get("counts")
    if not isinstance(totals_obj, dict):
        totals_obj = {}
    if not isinstance(counts_obj, dict):
        counts_obj = {}

    lang = str(run_state.get("lang") or run_summary.get("lang") or "")
    pdf_path = str(run_state.get("pdf_path") or run_summary.get("pdf_path") or "")
    final_docx = str(run_state.get("final_docx_path_abs") or "")
    output_folder = str(run_state.get("frozen_outdir_abs") or "")
    settings_obj = run_state.get("settings")
    if not isinstance(settings_obj, dict):
        settings_obj = {}
    summary_pipeline_obj = run_summary.get("pipeline")
    if not isinstance(summary_pipeline_obj, dict):
        summary_pipeline_obj = {}
    settings_image_mode = str(settings_obj.get("image_mode", run_summary.get("image_mode", "")) or "")
    image_mode_optimization_hint = _image_mode_optimization_hint(
        target_language=lang,
        image_mode=settings_image_mode,
        pages=pages,
    )
    resume_value = bool(settings_obj.get("resume", False))
    for event in events:
        if not isinstance(event, dict):
            continue
        if str(event.get("event_type", "") or "") != "run_started":
            continue
        details_obj = event.get("details")
        if not isinstance(details_obj, dict):
            continue
        if "resume" in details_obj:
            resume_value = bool(details_obj.get("resume"))
        break

    ocr_mode_value = str(settings_obj.get("ocr_mode", summary_pipeline_obj.get("ocr_mode", "")) or "").strip().lower()
    if ocr_mode_value == "always":
        fallback_ocr_requested = True
    elif ocr_mode_value == "off":
        fallback_ocr_requested = False
    else:
        fallback_ocr_requested = ocr_requested_pages > 0
    if isinstance(summary_pipeline_obj.get("ocr_requested"), bool):
        ocr_requested_value = bool(summary_pipeline_obj.get("ocr_requested"))
    else:
        ocr_requested_value = fallback_ocr_requested

    if isinstance(summary_pipeline_obj.get("ocr_used"), bool):
        ocr_used_value = bool(summary_pipeline_obj.get("ocr_used"))
    else:
        ocr_used_value = ocr_used_pages > 0

    ocr_provider_configured_event: bool | None = None
    ocr_preflight_checked_event = False
    for event in events:
        if not isinstance(event, dict):
            continue
        event_type = str(event.get("event_type", "") or "")
        if event_type == "ocr_preflight_checked":
            ocr_preflight_checked_event = True
            decisions_obj = event.get("decisions")
            if isinstance(decisions_obj, dict) and isinstance(decisions_obj.get("configured"), bool):
                if bool(decisions_obj.get("configured")):
                    ocr_provider_configured_event = True
                    break
                if ocr_provider_configured_event is None:
                    ocr_provider_configured_event = False
            continue
        if event_type == "ocr_engine_ready":
            ocr_provider_configured_event = True
            break
        if event_type in {
            "ocr_required_but_unavailable",
            "ocr_helpful_but_unavailable",
            "ocr_engine_unavailable",
            "ocr_engine_not_configured",
        }:
            ocr_provider_configured_event = False

    if isinstance(summary_pipeline_obj.get("ocr_preflight_checked"), bool):
        ocr_preflight_checked_value = bool(summary_pipeline_obj.get("ocr_preflight_checked"))
    elif ocr_preflight_checked_event:
        ocr_preflight_checked_value = True
    else:
        ocr_preflight_checked_value = (ocr_requested_pages > 0) or (ocr_required_pages > 0) or (ocr_helpful_pages > 0)

    if isinstance(summary_pipeline_obj.get("ocr_provider_configured"), bool):
        ocr_provider_configured_value = bool(summary_pipeline_obj.get("ocr_provider_configured"))
    elif not ocr_preflight_checked_value:
        ocr_provider_configured_value = False
    elif ocr_provider_configured_event is not None:
        ocr_provider_configured_value = bool(ocr_provider_configured_event)
    elif ocr_mode_value == "off":
        ocr_provider_configured_value = False
    else:
        ocr_provider_configured_value = any(bool(row.get("ocr_provider_configured", False)) for row in per_page)

    if isinstance(summary_pipeline_obj.get("ocr_requested_pages"), int):
        ocr_requested_pages_value = int(summary_pipeline_obj.get("ocr_requested_pages") or 0)
    else:
        ocr_requested_pages_value = int(ocr_requested_pages)
    if isinstance(summary_pipeline_obj.get("ocr_used_pages"), int):
        ocr_used_pages_value = int(summary_pipeline_obj.get("ocr_used_pages") or 0)
    else:
        ocr_used_pages_value = int(ocr_used_pages)
    if isinstance(summary_pipeline_obj.get("ocr_required_pages"), int):
        ocr_required_pages_value = int(summary_pipeline_obj.get("ocr_required_pages") or 0)
    else:
        ocr_required_pages_value = int(ocr_required_pages)
    if isinstance(summary_pipeline_obj.get("ocr_helpful_pages"), int):
        ocr_helpful_pages_value = int(summary_pipeline_obj.get("ocr_helpful_pages") or 0)
    else:
        ocr_helpful_pages_value = int(ocr_helpful_pages)
    if isinstance(summary_pipeline_obj.get("ocr_required_unavailable_pages"), int):
        ocr_required_unavailable_pages_value = int(summary_pipeline_obj.get("ocr_required_unavailable_pages") or 0)
    else:
        ocr_required_unavailable_pages_value = int(ocr_required_unavailable_pages)

    payload: dict[str, Any] = {
        "schema_version": "admin_run_report_v1" if admin_mode else "basic_run_report_v1",
        "admin_mode": bool(admin_mode),
        "generated_at": _utc_now(),
        "run": {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "status": str(run_state.get("run_status") or ""),
            "halt_reason": str(run_state.get("halt_reason") or ""),
            "completed_at": str(run_state.get("finished_at") or ""),
            "app_version": __version__,
            "commit_hash": _resolve_commit_hash(),
            "platform": platform.platform(),
            "python_version": sys.version.split()[0],
        },
        "input": {
            "file_name": _safe_file_name(pdf_path),
            "file_size_bytes": _safe_file_size(pdf_path),
            "detected_page_count": int(run_state.get("total_pages", 0) or 0),
            "target_language": lang,
            "page_range": {
                "start_page": int(run_state.get("selection_start_page", 0) or 0),
                "end_page": int(run_state.get("selection_end_page", 0) or 0),
                "max_pages_effective": int(run_state.get("max_pages_effective", 0) or 0),
                "resume": resume_value,
            },
        },
        "pipeline": {
            "image_mode": settings_image_mode,
            "ocr_mode": str(settings_obj.get("ocr_mode", summary_pipeline_obj.get("ocr_mode", "")) or ""),
            "ocr_engine": str(settings_obj.get("ocr_engine", summary_pipeline_obj.get("ocr_engine", "")) or ""),
            "ocr_requested": bool(ocr_requested_value),
            "ocr_used": bool(ocr_used_value),
            "ocr_provider_configured": bool(ocr_provider_configured_value),
            "ocr_requested_pages": int(ocr_requested_pages_value),
            "ocr_used_pages": int(ocr_used_pages_value),
            "ocr_required_pages": int(ocr_required_pages_value),
            "ocr_helpful_pages": int(ocr_helpful_pages_value),
            "ocr_required_unavailable_pages": int(ocr_required_unavailable_pages_value),
            "ocr_preflight_checked": bool(ocr_preflight_checked_value),
            "pt_language_leak_failures": int(pt_language_leak_failures),
            "pt_language_leak_retries": int(pt_language_leak_retries),
            "image_mode_optimization_hint": image_mode_optimization_hint,
        },
        "totals": {
            "wall_seconds": float(totals_obj.get("total_wall_seconds", 0.0) or 0.0),
            "input_tokens": int(totals_obj.get("total_input_tokens", 0) or 0),
            "output_tokens": int(totals_obj.get("total_output_tokens", 0) or 0),
            "reasoning_tokens": int(totals_obj.get("total_reasoning_tokens", 0) or 0),
            "total_tokens": int(totals_obj.get("total_tokens", 0) or 0),
            "estimated_cost": totals_obj.get("total_cost_estimate_if_available"),
            "api_calls_total": api_calls_total,
            "transport_retries_total": transport_retries_total,
            "backoff_wait_seconds_total": round(backoff_wait_seconds_total, 3),
            "rate_limit_hits": rate_limit_hits,
        },
        "output": {
            "output_folder": output_folder or (str(Path(final_docx).parent) if final_docx else ""),
            "output_docx_name": _safe_file_name(final_docx),
            "intermediates_kept": bool(settings_obj.get("keep_intermediates", True)),
            "run_summary_path": str(run_dir / "run_summary.json"),
            "events_path": str(run_dir / "run_events.jsonl"),
        },
        "warnings_errors": {
            "failed_pages": page_failures,
            "failed_pages_count": int(counts_obj.get("pages_failed", len(page_failures)) or len(page_failures)),
        },
    }

    if admin_mode:
        payload["timeline_events"] = sanitize_value(events)
        payload["per_page_rollups"] = per_page
        if include_sanitized_snippets:
            payload["translated_snippets"] = _extract_translated_snippets(
                run_dir,
                per_page_max_chars=200,
            )

    return sanitize_value(payload)


def build_run_report_markdown(
    *,
    run_dir: Path,
    admin_mode: bool,
    include_sanitized_snippets: bool,
) -> str:
    payload = build_run_report_payload(
        run_dir=run_dir,
        admin_mode=admin_mode,
        include_sanitized_snippets=include_sanitized_snippets and admin_mode,
    )

    run_obj = payload.get("run", {})
    input_obj = payload.get("input", {})
    totals_obj = payload.get("totals", {})
    output_obj = payload.get("output", {})
    warnings_obj = payload.get("warnings_errors", {})
    pipeline_obj = payload.get("pipeline", {})
    timeline_obj = payload.get("timeline_events", [])
    if not isinstance(run_obj, dict):
        run_obj = {}
    if not isinstance(input_obj, dict):
        input_obj = {}
    if not isinstance(totals_obj, dict):
        totals_obj = {}
    if not isinstance(output_obj, dict):
        output_obj = {}
    if not isinstance(warnings_obj, dict):
        warnings_obj = {}
    if not isinstance(pipeline_obj, dict):
        pipeline_obj = {}
    if not isinstance(timeline_obj, list):
        timeline_obj = []

    lines: list[str] = []
    lines.append("# Run Report")
    lines.append("")
    lines.append("## Summary")
    lines.append(
        f"- Run `{run_obj.get('run_id', '-')}` status `{run_obj.get('status', '-')}` "
        f"for `{input_obj.get('file_name', '-')}` -> `{output_obj.get('output_docx_name', '-')}`."
    )
    lines.append(
        f"- Total wall time `{totals_obj.get('wall_seconds', 0.0)}`s, "
        f"tokens `{totals_obj.get('total_tokens', 0)}`, estimated cost `{totals_obj.get('estimated_cost')}`."
    )
    lines.append(
        f"- API calls `{totals_obj.get('api_calls_total', 0)}`, retries `{totals_obj.get('transport_retries_total', 0)}`, "
        f"rate-limit hits `{totals_obj.get('rate_limit_hits', 0)}`."
    )
    lines.append(
        f"- Failed pages `{warnings_obj.get('failed_pages_count', 0)}` "
        f"({warnings_obj.get('failed_pages', [])})."
    )
    lines.append(_ocr_summary_line(pipeline_obj))
    pt_language_leak_failures = int(pipeline_obj.get("pt_language_leak_failures", 0) or 0)
    pt_language_leak_retries = int(pipeline_obj.get("pt_language_leak_retries", 0) or 0)
    if pt_language_leak_retries > 0 or pt_language_leak_failures > 0:
        lines.append(
            "- Portuguese residual-language guardrail: "
            f"retries `{pt_language_leak_retries}`, failures `{pt_language_leak_failures}`."
        )
    optimization_hint = str(pipeline_obj.get("image_mode_optimization_hint", "") or "").strip()
    if optimization_hint:
        lines.append(f"- Optimization hint: {optimization_hint}")
    lines.append("")
    lines.append("## Timeline")
    lines.extend(_build_timeline_lines(timeline_obj))

    if admin_mode:
        per_page = payload.get("per_page_rollups")
        if isinstance(per_page, list):
            lines.append("")
            lines.append("## Per-Page Rollups")
            if per_page:
                for item in per_page:
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        "- "
                        f"Page {item.get('page_number')}: "
                        f"status={item.get('status')} "
                        f"route={item.get('source_route')} "
                        f"ocr_requested={item.get('ocr_requested')} "
                        f"ocr_request_reason={item.get('ocr_request_reason')} "
                        f"ocr_used={item.get('ocr_used')} "
                        f"image={item.get('image_used')} "
                        f"retry_reason={item.get('retry_reason')} "
                        f"tokens={item.get('total_tokens')} "
                        f"wall_s={item.get('wall_seconds')}"
                    )
            else:
                lines.append("- (no page rollups available)")

        snippets = payload.get("translated_snippets")
        if isinstance(snippets, list):
            lines.append("")
            lines.append("## Sanitized Snippets (Translated Output, Max 200 chars/page)")
            if snippets:
                for item in snippets:
                    if not isinstance(item, dict):
                        continue
                    page_no = item.get("page_number")
                    snippet = str(item.get("snippet", "") or "")
                    lines.append(f"- Page {page_no}: `{snippet}`")
            else:
                lines.append("- (no snippets available)")

    lines.append("")
    lines.append("## JSON")
    lines.append("```json")
    lines.append(json.dumps(payload, ensure_ascii=False, indent=2))
    lines.append("```")
    return "\n".join(lines)
