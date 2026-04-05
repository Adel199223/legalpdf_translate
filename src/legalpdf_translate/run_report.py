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


def _parse_optional_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    return None


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
            "extracted_text_chars": int(page.get("extracted_text_chars", 0) or 0),
            "extracted_text_lines": int(page.get("extracted_text_lines", 0) or 0),
            "prompt_build_ms": float(page.get("prompt_build_ms", 0.0) or 0.0),
            "attempt1_effort": str(page.get("attempt1_effort", "") or ""),
            "attempt2_effort": str(page.get("attempt2_effort", "") or ""),
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
    ocr_source_profile_value = str(summary_pipeline_obj.get("ocr_source_profile", "") or "").strip()
    ocr_local_pass_strategy_value = str(summary_pipeline_obj.get("ocr_local_pass_strategy", "") or "").strip()
    ocr_api_fallback_policy_value = str(summary_pipeline_obj.get("ocr_api_fallback_policy", "") or "").strip()
    ocr_quality_score_avg_value = summary_pipeline_obj.get("ocr_quality_score_avg")
    ocr_track_enfr_pages_value = int(summary_pipeline_obj.get("ocr_track_enfr_pages", 0) or 0)
    ocr_track_ar_pages_value = int(summary_pipeline_obj.get("ocr_track_ar_pages", 0) or 0)
    ocr_track_weighting_value = summary_pipeline_obj.get("ocr_track_weighting")
    if not isinstance(ocr_track_weighting_value, dict):
        ocr_track_weighting_value = {"enfr": 0.60, "ar": 0.40}
    ocr_track_quality_packet_value = summary_pipeline_obj.get("ocr_track_quality_packet")
    if not isinstance(ocr_track_quality_packet_value, dict):
        ocr_track_quality_packet_value = {}
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
    budget_pre_obj = run_summary.get("budget_pre_run")
    if not isinstance(budget_pre_obj, dict):
        budget_pre_obj = {}
    budget_post_obj = run_summary.get("budget_post_run")
    if not isinstance(budget_post_obj, dict):
        budget_post_obj = {}
    budget_obj: dict[str, Any] = {
        "cost_estimation_status": str(run_summary.get("cost_estimation_status", "") or ""),
        "cost_profile_id": str(run_summary.get("cost_profile_id", "") or ""),
        "budget_cap_usd": run_summary.get("budget_cap_usd"),
        "budget_decision": str(run_summary.get("budget_decision", "") or ""),
        "budget_decision_reason": str(run_summary.get("budget_decision_reason", "") or ""),
        "budget_pre_run": budget_pre_obj,
        "budget_post_run": budget_post_obj,
    }
    quality_obj: dict[str, Any] = {
        "quality_risk_score": run_summary.get("quality_risk_score"),
        "review_queue_count": int(run_summary.get("review_queue_count", 0) or 0),
        "advisor_recommendation_applied": _parse_optional_bool(run_summary.get("advisor_recommendation_applied")),
        "advisor_recommendation": (
            run_summary.get("advisor_recommendation")
            if isinstance(run_summary.get("advisor_recommendation"), dict)
            else {}
        ),
    }
    gmail_batch_context_obj = run_summary.get("gmail_batch_context")
    if not isinstance(gmail_batch_context_obj, dict):
        gmail_batch_context_obj = {}

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
            "ocr_source_profile": ocr_source_profile_value,
            "ocr_local_pass_strategy": ocr_local_pass_strategy_value,
            "ocr_api_fallback_policy": ocr_api_fallback_policy_value,
            "ocr_quality_score_avg": ocr_quality_score_avg_value,
            "ocr_track_enfr_pages": int(ocr_track_enfr_pages_value),
            "ocr_track_ar_pages": int(ocr_track_ar_pages_value),
            "ocr_track_weighting": ocr_track_weighting_value,
            "ocr_track_quality_packet": ocr_track_quality_packet_value,
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
        "budget": budget_obj,
        "quality": quality_obj,
    }
    if gmail_batch_context_obj:
        payload["gmail_batch_context"] = {
            "source": str(gmail_batch_context_obj.get("source", "") or ""),
            "session_id": str(gmail_batch_context_obj.get("session_id", "") or ""),
            "message_id": str(gmail_batch_context_obj.get("message_id", "") or ""),
            "thread_id": str(gmail_batch_context_obj.get("thread_id", "") or ""),
            "selected_attachment_filename": str(
                gmail_batch_context_obj.get("selected_attachment_filename", "") or ""
            ),
            "selected_attachment_count": int(
                gmail_batch_context_obj.get("selected_attachment_count", 0) or 0
            ),
            "selected_target_lang": str(
                gmail_batch_context_obj.get("selected_target_lang", "") or ""
            ),
            "selected_start_page": int(
                gmail_batch_context_obj.get("selected_start_page", 0) or 0
            ),
            "gmail_batch_session_report_path": str(
                gmail_batch_context_obj.get("gmail_batch_session_report_path", "") or ""
            ),
        }

    if admin_mode:
        payload["timeline_events"] = sanitize_value(events)
        payload["per_page_rollups"] = per_page
        if include_sanitized_snippets:
            payload["translated_snippets"] = _extract_translated_snippets(
                run_dir,
                per_page_max_chars=200,
            )

    # Glossary diagnostics (from events emitted by glossary_diagnostics module)
    glossary_diag: dict[str, Any] = {}
    for ev in events:
        et = str(ev.get("event_type", ""))
        if et == "page_coverage_summary":
            glossary_diag["coverage_proof"] = ev.get("details", {})
        elif et == "pkg_pareto_summary":
            glossary_diag["pkg_pareto"] = ev.get("details", {})
        elif et == "token_pareto_summary":
            glossary_diag["token_pareto"] = ev.get("details", {})
        elif et == "cg_load_summary":
            glossary_diag["cg_load"] = ev.get("counters", {})
        elif et == "cg_ambiguous_pareto_summary":
            glossary_diag["cg_ambiguous_pareto"] = ev.get("details", {})
        elif et == "cg_drift_candidates":
            glossary_diag["cg_drift"] = ev.get("details", {})
        elif et == "lemma_normalization_summary":
            glossary_diag["lemma_summary"] = ev.get("details", {})
        elif et == "suggestion_selection_summary":
            glossary_diag["suggestion_selection"] = ev.get("details", {})
    cg_per_page = [
        {**ev.get("counters", {}), "page_index": ev.get("page_index")}
        for ev in events
        if str(ev.get("event_type", "")) == "cg_apply_page"
    ]
    if cg_per_page:
        glossary_diag["cg_per_page_matches"] = cg_per_page
    if glossary_diag:
        payload["glossary_diagnostics"] = glossary_diag

    # Translation diagnostics (from events emitted by translation_diagnostics module)
    translation_diag: dict[str, Any] = {}
    prompt_compiled_pages: list[dict[str, Any]] = []
    validation_pages: list[dict[str, Any]] = []
    for ev in events:
        et = str(ev.get("event_type", ""))
        if et == "run_config_summary":
            translation_diag["run_config"] = ev.get("details", {})
        elif et == "prompt_compiled":
            prompt_compiled_pages.append(
                {"page_index": ev.get("page_index"), **ev.get("counters", {}), **ev.get("decisions", {})}
            )
        elif et == "translation_validation_summary":
            validation_pages.append(
                {"page_index": ev.get("page_index"), **ev.get("counters", {}), **ev.get("decisions", {})}
            )
        elif et == "cost_estimate_summary":
            translation_diag["cost_estimate"] = {
                **ev.get("counters", {}),
                **ev.get("details", {}),
            }
        elif et == "docx_write_summary":
            translation_diag["docx_write"] = {
                "duration_ms": ev.get("duration_ms"),
                **ev.get("counters", {}),
            }
    if prompt_compiled_pages:
        translation_diag["prompt_compiled_pages"] = prompt_compiled_pages
    if validation_pages:
        translation_diag["validation_pages"] = validation_pages
    if translation_diag:
        payload["translation_diagnostics"] = translation_diag

    return sanitize_value(payload)


def _render_glossary_diagnostics_markdown(lines: list[str], gd: dict[str, Any]) -> None:
    """Append glossary diagnostics sections to *lines*."""
    # -- Document Coverage Proof --
    proof = gd.get("coverage_proof")
    if isinstance(proof, dict):
        lines.append("")
        lines.append("## Document Coverage Proof")
        lines.append(f"- **{proof.get('assertion', 'Processed pages: ?/?')}**")
        per_page = proof.get("per_page")
        if isinstance(per_page, list) and per_page:
            lines.append("")
            lines.append("| Page | Route | Chars | Segments | PKG Tokens | CG Active | CG Matches |")
            lines.append("|------|-------|-------|----------|------------|-----------|------------|")
            for row in per_page:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"| {row.get('page_index', '?')}"
                    f" | {row.get('source_route', '?')}"
                    f" | {row.get('char_count', 0)}"
                    f" | {row.get('segment_count', 0)}"
                    f" | {row.get('pkg_token_count', 0)}"
                    f" | {row.get('cg_entries_active', 0)}"
                    f" | {row.get('cg_matches_count', 0)} |"
                )

    # -- PKG Pareto Analysis --
    pkg = gd.get("pkg_pareto")
    if isinstance(pkg, dict):
        lemma_mode = bool(pkg.get("lemma_mode"))
        lines.append("")
        header = "## PKG n-gram Pareto (diagnostic)"
        if lemma_mode:
            header += " \u2014 Lemma-grouped"
        lines.append(header)
        lines.append(
            "> n-gram (1\u20134) frequency distribution. "
            "For primary content analysis, see Content Token Pareto below."
        )
        lines.append(f"- Total raw tokens analyzed: **{pkg.get('total_tokens', 0)}**")
        if lemma_mode:
            lines.append(f"- Surface unique terms: **{pkg.get('surface_unique_terms', 0)}**")
            lines.append(f"- Lemma-grouped unique terms: **{pkg.get('lemma_grouped_unique_terms', 0)}**")
        else:
            lines.append(f"- Unique terms (n-grams): **{pkg.get('unique_terms', 0)}**")
        lines.append(f"- Total term occurrences: **{pkg.get('total_term_occurrences', 0)}**")
        lines.append(
            f"- Top 20% of terms cover **{round(float(pkg.get('top_20_pct_coverage', 0)) * 100, 1)}%** of occurrences"
        )
        core80 = pkg.get("core80_terms")
        if isinstance(core80, list) and core80:
            lines.append(f"- Smallest set covering ~80%: **{len(core80)} terms**")
        suggested = pkg.get("suggested_pkg_candidates")
        if isinstance(suggested, list) and suggested:
            lines.append("")
            lines.append("### Suggested PKG Candidates")
            lines.append("")
            if lemma_mode:
                lines.append("| Rank | Lemma | Surface Forms | Frequency | Pages |")
                lines.append("|------|-------|---------------|-----------|-------|")
            else:
                lines.append("| Rank | Term | Frequency | Pages |")
                lines.append("|------|------|-----------|-------|")
            for rank, item in enumerate(suggested[:30], start=1):
                if not isinstance(item, dict):
                    continue
                if lemma_mode:
                    sf_list = item.get("surface_forms", [])
                    sf_str = ", ".join(str(s) for s in sf_list) if sf_list else ""
                    lines.append(
                        f"| {rank}"
                        f" | {item.get('term', '?')}"
                        f" | {sf_str}"
                        f" | {item.get('tf', 0)}"
                        f" | {item.get('df_pages', 0)} |"
                    )
                else:
                    lines.append(
                        f"| {rank}"
                        f" | {item.get('term', '?')}"
                        f" | {item.get('tf', 0)}"
                        f" | {item.get('df_pages', 0)} |"
                    )

    # -- Content Token Pareto --
    tok_pareto = gd.get("token_pareto")
    if isinstance(tok_pareto, dict):
        tok_lemma = bool(tok_pareto.get("lemma_mode"))
        lines.append("")
        tok_header = "## Content Token Pareto"
        if tok_lemma:
            tok_header += " (Lemma-grouped)"
        lines.append(tok_header)
        lines.append(
            "> Unigram content tokens (stopword-filtered, len \u2265 3). "
            "For meaningful coverage analysis without n-gram explosion."
        )
        lines.append(f"- Content tokens analyzed: **{tok_pareto.get('total_content_tokens', 0)}**")
        lines.append(f"- Unique content tokens: **{tok_pareto.get('unique_content_tokens', 0)}**")
        tok_cov = round(float(tok_pareto.get("top_20_pct_coverage", 0)) * 100, 1)
        lines.append(f"- Top 20% cover **{tok_cov}%** of occurrences")
        tok_core80 = tok_pareto.get("core80_terms")
        if isinstance(tok_core80, list) and tok_core80:
            lines.append(f"- Core 80% set: **{len(tok_core80)} terms**")
        tok_candidates = tok_pareto.get("suggested_content_candidates")
        if isinstance(tok_candidates, list) and tok_candidates:
            lines.append("")
            lines.append("### Suggested Content Candidates")
            lines.append("")
            if tok_lemma:
                lines.append("| Rank | Term | Surface Forms | Frequency | Pages |")
                lines.append("|------|------|---------------|-----------|-------|")
            else:
                lines.append("| Rank | Term | Frequency | Pages |")
                lines.append("|------|------|-----------|-------|")
            for rank, item in enumerate(tok_candidates[:30], start=1):
                if not isinstance(item, dict):
                    continue
                if tok_lemma:
                    sf_list = item.get("surface_forms", [])
                    sf_str = ", ".join(str(s) for s in sf_list) if sf_list else ""
                    lines.append(
                        f"| {rank}"
                        f" | {item.get('term', '?')}"
                        f" | {sf_str}"
                        f" | {item.get('tf', 0)}"
                        f" | {item.get('df_pages', 0)} |"
                    )
                else:
                    lines.append(
                        f"| {rank}"
                        f" | {item.get('term', '?')}"
                        f" | {item.get('tf', 0)}"
                        f" | {item.get('df_pages', 0)} |"
                    )

    # -- Lemma Normalization Summary --
    lemma_sum = gd.get("lemma_summary")
    if isinstance(lemma_sum, dict):
        lines.append("")
        lines.append("### Lemma Normalization")
        # Check if lemma grouping affected suggestion selection
        _sel = gd.get("suggestion_selection")
        _lemma_affected = (
            isinstance(_sel, dict) and bool(_sel.get("lemma_grouping_affected_selection"))
        )
        if _lemma_affected:
            lines.append(
                "> Lemma normalization was used for both PKG/token Pareto analytics "
                "**and** suggestion selection."
            )
        else:
            lines.append(
                "> Lemma normalization is used for PKG/token Pareto analytics only. "
                "It did NOT affect the suggestion list in this run."
            )
        terms_total = int(lemma_sum.get("terms_total", 0))
        cache_hits = int(lemma_sum.get("cache_hits", 0))
        api_calls_count = int(lemma_sum.get("api_calls", 0))
        lines.append(f"- Terms processed: **{terms_total}**")
        lines.append(f"- Cache hits: **{cache_hits}**")
        lines.append(f"- API calls: **{api_calls_count}**")
        in_tok = int(lemma_sum.get("input_tokens", 0))
        out_tok = int(lemma_sum.get("output_tokens", 0))
        if in_tok or out_tok:
            lines.append(f"- Tokens: **{in_tok}** in / **{out_tok}** out")
        # Cache explanation
        if terms_total > 0 and cache_hits >= terms_total:
            lines.append(
                f"> All {terms_total} terms resolved from cache (0 API calls). "
                "Fast run \u2014 lemma cache contained all needed terms."
            )
        elif api_calls_count > 0:
            uncached = terms_total - cache_hits
            lines.append(
                f"> {uncached} term(s) required API normalization "
                f"({api_calls_count} call(s), {in_tok} input tokens)."
            )
        failures = int(lemma_sum.get("failures", 0))
        if failures:
            lines.append(f"- Batch failures: **{failures}**")
        wall = lemma_sum.get("wall_seconds")
        if wall is not None:
            lines.append(f"- Wall time: **{round(float(wall), 1)}s**")
        if lemma_sum.get("fallback_to_surface"):
            lines.append("")
            lines.append("> **Warning:** All lemma API batches failed. PKG Pareto used surface forms only.")

    # -- Suggestion Selection Diagnostics --
    sel = gd.get("suggestion_selection")
    if isinstance(sel, dict):
        lines.append("")
        lines.append("## Suggestion Selection Diagnostics")
        _cand = int(sel.get("candidates_extracted_total", 0))
        _doc_max_th = sel.get("filter_doc_max_threshold", 5)
        _corpus_tf_th = sel.get("filter_corpus_tf_threshold", 3)
        _corpus_df_th = sel.get("filter_corpus_df_threshold", 2)
        _passed_a = int(sel.get("passed_doc_max_filter", 0))
        _passed_b = int(sel.get("passed_corpus_filter", 0))
        _final = int(sel.get("final_suggestions_count", 0))
        _cap = sel.get("max_suggestions_cap")
        lines.append(f"- Candidate n-grams extracted: **{_cand}**")
        lines.append(
            f"- Filter A — single-document TF \u2265 {_doc_max_th}: **{_passed_a}** terms"
        )
        lines.append(
            f"- Filter B — corpus TF \u2265 {_corpus_tf_th} AND DF \u2265 {_corpus_df_th}: **{_passed_b}** terms"
        )
        lines.append(f"- Combined (A OR B): **{_final}** terms")
        if _cap is not None:
            lines.append(f"- Max suggestions cap: **{_cap}**")
        else:
            lines.append("- Max suggestions cap: **none** (all qualifying terms returned)")
        lines.append(f"- **Final suggestions: {_final}**")
        _lemma_used = bool(sel.get("lemma_grouping_affected_selection"))
        _lemma_changed = bool(sel.get("lemma_selection_changed"))
        if _lemma_used and _lemma_changed:
            _so_count = int(sel.get("lemma_surface_only_count", 0))
            _lo_count = int(sel.get("lemma_only_count", 0))
            _unch = int(sel.get("lemma_unchanged_count", 0))
            lines.append("")
            lines.append(
                f"> Lemma grouping was used for suggestion selection and changed the results. "
                f"Delta: {_so_count} surface-only removed, "
                f"{_lo_count} lemma-grouped added, {_unch} unchanged."
            )
            _so_terms = sel.get("lemma_surface_only_terms", [])
            if isinstance(_so_terms, list) and _so_terms:
                lines.append(f">  \u2022 Removed (surface-only): {', '.join(str(t) for t in _so_terms)}")
            _lo_terms = sel.get("lemma_only_terms", [])
            if isinstance(_lo_terms, list) and _lo_terms:
                lines.append(f">  \u2022 Added (lemma-grouped): {', '.join(str(t) for t in _lo_terms)}")
        elif _lemma_used and not _lemma_changed:
            _sc = int(sel.get("surface_selection_count", 0))
            _lc = int(sel.get("lemma_selection_count", 0))
            lines.append("")
            lines.append(
                "> Lemma grouping was used for suggestion selection "
                "but produced the same results as surface-form selection."
            )
            lines.append(f"> Surface count: {_sc}, Lemma count: {_lc} (identical sets).")
        else:
            lines.append("")
            lines.append(
                "> Lemma grouping was not used for suggestion selection in this run. "
                "The suggestion count is determined entirely by TF/DF threshold filters."
            )

    # -- CG Match Analysis --
    cg_ambig = gd.get("cg_ambiguous_pareto")
    cg_load = gd.get("cg_load")
    if isinstance(cg_ambig, dict) or isinstance(cg_load, dict):
        lines.append("")
        lines.append("## CG Match Analysis")
        if isinstance(cg_load, dict):
            lines.append(f"- Entries loaded: **{cg_load.get('entries_loaded', 0)}**")
        if isinstance(cg_ambig, dict):
            lines.append(f"- Total match count (all pages): **{cg_ambig.get('total_match_count', 0)}**")
            lines.append(f"- Unique matched entries: **{cg_ambig.get('unique_matched_entries', 0)}**")
            never = cg_ambig.get("never_matched_entries")
            if isinstance(never, list) and never:
                lines.append(f"- Never matched: {', '.join(str(n) for n in never[:20])}")

        cg_pp = gd.get("cg_per_page_matches")
        if isinstance(cg_pp, list) and cg_pp:
            lines.append("")
            lines.append("| Page | Matches | Active Entries |")
            lines.append("|------|---------|----------------|")
            for row in cg_pp:
                if not isinstance(row, dict):
                    continue
                lines.append(
                    f"| {row.get('page_index', '?')}"
                    f" | {row.get('match_count', 0)}"
                    f" | {row.get('entries_active', 0)} |"
                )

        # Ambiguous Pareto sub-section
        if isinstance(cg_ambig, dict):
            ambig_candidates = cg_ambig.get("ambiguous_candidates", [])
            lines.append("")
            lines.append("### Ambiguous Pareto")
            lines.append(
                f"- Total ambiguous frequency: **{cg_ambig.get('ambiguous_total_frequency', 0)}**"
            )
            lines.append(f"- Ambiguous candidates: **{len(ambig_candidates)}**")
            core80 = cg_ambig.get("ambiguous_pareto_core80", [])
            if isinstance(core80, list) and core80:
                lines.append(f"- Core 80% set: **{len(core80)} terms**")
                lines.append("")
                lines.append("| Term | Frequency | Pages | Heuristics | CG Covered |")
                lines.append("|------|-----------|-------|------------|------------|")
                for item in core80:
                    if not isinstance(item, dict):
                        continue
                    tags = ", ".join(item.get("heuristic_tags", []))
                    lines.append(
                        f"| {item.get('source_text', '?')}"
                        f" | {item.get('frequency', 0)}"
                        f" | {item.get('df_pages', 0)}"
                        f" | {tags}"
                        f" | {'yes' if item.get('cg_covered') else 'no'} |"
                    )

            # Drift candidates
            drift = gd.get("cg_drift", {})
            drift_list = drift.get("drift_candidates", []) if isinstance(drift, dict) else []
            lines.append("")
            lines.append("### Drift Candidates")
            if isinstance(drift_list, list) and drift_list:
                for item in drift_list:
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        f"- **{item.get('source_text', '?')}**: "
                        f"translations seen: {item.get('translations_seen', [])}"
                    )
            else:
                lines.append("- (none detected)")

            lines.append("")
            lines.append(
                "> **Reminder:** CG should stay minimal and high-impact. "
                "These are suggestions only — do not auto-add."
            )


def _render_translation_diagnostics_markdown(
    lines: list[str],
    td: dict[str, Any],
    *,
    per_page: list[dict[str, Any]] | None = None,
    snippets: list[dict[str, Any]] | None = None,
) -> None:
    """Append translation diagnostics sections to *lines*."""
    lines.append("")
    lines.append("## Translation Diagnostics")

    # -- A. Run Configuration --
    rc = td.get("run_config")
    if isinstance(rc, dict):
        lines.append("")
        lines.append("### A. Run Configuration")
        lines.append(f"- Model: **{rc.get('model', '?')}**")
        lines.append(f"- Target language: **{rc.get('target_lang', '?')}**")
        lines.append(f"- Image mode: `{rc.get('image_mode', '?')}`")
        lines.append(f"- OCR mode: `{rc.get('ocr_mode', '?')}`")
        lines.append(f"- Strip bidi controls: `{rc.get('strip_bidi_controls', '?')}`")
        lines.append(f"- Effort policy: `{rc.get('effort_policy', '?')}`")
        lines.append(f"- Effort resolved (attempt 1 default): `{rc.get('effort_resolved', '?')}`")
        lines.append(f"- Page breaks: `{rc.get('page_breaks', '?')}`")
        lines.append(f"- Workers: `{rc.get('workers', '?')}`")
        lines.append(f"- Keep intermediates: `{rc.get('keep_intermediates', '?')}`")
        if rc.get("resume"):
            lines.append("- Resume: `True`")
        lines.append(f"- Glossary entries: **{rc.get('glossary_entries_count', 0)}** (tiers: {rc.get('glossary_tiers', '?')})")
        lines.append(f"- System instructions hash: `{rc.get('system_instructions_hash', '?')}`")
        lines.append("- Max output tokens: *not set (API default)*")
        lines.append("- Temperature: *not set (API default)*")

    # -- B. Coverage Proof --
    if isinstance(per_page, list) and per_page:
        _total_pp = len(per_page)
        _done_pp = [p for p in per_page if isinstance(p, dict) and p.get("status") in ("done", "failed")]
        _processed = len(_done_pp)
        _failed_list = [p.get("page_number") for p in per_page if isinstance(p, dict) and p.get("status") == "failed"]
        _retry_list = [
            p.get("page_number")
            for p in per_page
            if isinstance(p, dict) and str(p.get("retry_reason", "") or "").strip()
        ]
        lines.append("")
        lines.append("### B. Coverage Proof")
        lines.append(f"- **Processed pages: {_processed}/{_total_pp}**")
        if _failed_list:
            lines.append(f"- Pages failed: {_failed_list}")
        if _retry_list:
            lines.append(f"- Pages with retries: {_retry_list}")
        lines.append("")
        lines.append(
            "| Page | Status | Route | Why | Chars | Lines | Effort | OCR | Image | API | In Tok | Out Tok"
            " | Extract ms | API ms | Total ms | Cost |"
        )
        lines.append(
            "|------|--------|-------|-----|-------|-------|--------|-----|-------|-----|--------|--------"
            "|------------|--------|----------|------|"
        )
        for _pp in per_page:
            if not isinstance(_pp, dict):
                continue
            _ocr_flag = "Y" if _pp.get("ocr_used") else "-"
            _img_flag = "Y" if _pp.get("image_used") else "-"
            _effort = str(_pp.get("attempt1_effort", "") or "")
            _cost_val = _pp.get("estimated_cost")
            _cost_str = f"${_cost_val:.6f}" if _cost_val is not None else "-"
            _extract_ms = round(float(_pp.get("extract_seconds", 0) or 0) * 1000.0)
            _api_ms = round(float(_pp.get("translate_seconds", 0) or 0) * 1000.0)
            _total_ms = round(float(_pp.get("wall_seconds", 0) or 0) * 1000.0)
            _route_reason = str(_pp.get("source_route_reason", "") or "")
            lines.append(
                f"| {_pp.get('page_number', '?')}"
                f" | {_pp.get('status', '?')}"
                f" | {_pp.get('source_route', '?')}"
                f" | {_route_reason or '-'}"
                f" | {_pp.get('extracted_text_chars', 0)}"
                f" | {_pp.get('extracted_text_lines', 0)}"
                f" | {_effort or '-'}"
                f" | {_ocr_flag}"
                f" | {_img_flag}"
                f" | {_pp.get('api_calls_count', 0)}"
                f" | {_pp.get('input_tokens', 0)}"
                f" | {_pp.get('output_tokens', 0)}"
                f" | {_extract_ms}"
                f" | {_api_ms}"
                f" | {_total_ms}"
                f" | {_cost_str} |"
            )

    # -- C. Prompt + Chunking Diagnostics --
    pcp = td.get("prompt_compiled_pages")
    if isinstance(pcp, list) and pcp:
        lines.append("")
        lines.append("### C. Prompt + Chunking Diagnostics")
        lines.append("")
        lines.append("> Pipeline processes each page as a single unit (1 chunk per page). No sub-page chunking or truncation.")
        lines.append("")
        lines.append("| Page | Prompt Tokens (est) | System Tokens (est) | Glossary Tokens (est) | Segments | Bloat? |")
        lines.append("|------|---------------------|---------------------|-----------------------|----------|--------|")
        for row in pcp:
            if not isinstance(row, dict):
                continue
            bloat = "YES" if row.get("prompt_bloat_warning") else "no"
            lines.append(
                f"| {row.get('page_index', '?')}"
                f" | {row.get('prompt_tokens_est', 0)}"
                f" | {row.get('system_tokens_est', 0)}"
                f" | {row.get('glossary_tokens_est', 0)}"
                f" | {row.get('segment_count', 0)}"
                f" | {bloat} |"
            )

    # -- D. Translation Quality Checks --
    vp = td.get("validation_pages")
    if isinstance(vp, list) and vp:
        lines.append("")
        lines.append("### D. Translation Quality Checks")
        lines.append("")
        lines.append("| Page | Lang OK | Detected | Numeric Δ | Citation Δ | Struct Warn | Bidi Warn | Src Para | Out Para |")
        lines.append("|------|---------|----------|-----------|------------|-------------|-----------|----------|----------|")
        _numeric_sample_lines: list[str] = []
        _flagged_pages: set[int | str] = set()
        for row in vp:
            if not isinstance(row, dict):
                continue
            lang_ok = "yes" if row.get("language_ok") else "NO"
            _page_idx = row.get("page_index", "?")
            lines.append(
                f"| {_page_idx}"
                f" | {lang_ok}"
                f" | {row.get('detected_lang', '?')}"
                f" | {row.get('numeric_mismatches_count', 0)}"
                f" | {row.get('citation_mismatches_count', 0)}"
                f" | {row.get('structure_warnings_count', 0)}"
                f" | {row.get('bidi_warnings_count', 0)}"
                f" | {row.get('source_paragraphs', '-')}"
                f" | {row.get('output_paragraphs', '-')} |"
            )
            _samples = row.get("numeric_missing_sample")
            if isinstance(_samples, list) and _samples:
                _numeric_sample_lines.append(
                    f"- Page {_page_idx}: missing {_samples[:3]}"
                )
            # Track flagged pages for snippet gating
            _has_warning = (
                not row.get("language_ok", True)
                or int(row.get("numeric_mismatches_count", 0) or 0) > 0
                or int(row.get("citation_mismatches_count", 0) or 0) > 0
                or int(row.get("structure_warnings_count", 0) or 0) > 0
                or int(row.get("bidi_warnings_count", 0) or 0) > 0
            )
            if _has_warning:
                _flagged_pages.add(_page_idx)
        if _numeric_sample_lines:
            lines.append("")
            lines.append("#### Numeric Mismatch Samples")
            lines.extend(_numeric_sample_lines)
        # Flagged page snippets — only for pages with quality warnings
        if snippets and _flagged_pages:
            _flagged_snippet_lines: list[str] = []
            for _snip in snippets:
                if not isinstance(_snip, dict):
                    continue
                _snip_page = _snip.get("page_number")
                if _snip_page not in _flagged_pages:
                    continue
                _snip_text = str(_snip.get("snippet", "") or "")[:120]
                if _snip_text:
                    _flagged_snippet_lines.append(
                        f"- Page {_snip_page} ({len(_snip_text)} chars): `{_snip_text}`"
                    )
            if _flagged_snippet_lines:
                lines.append("")
                lines.append("#### Flagged Page Snippets")
                lines.extend(_flagged_snippet_lines)

    # -- E. Output Construction --
    dw = td.get("docx_write")
    if isinstance(dw, dict):
        lines.append("")
        lines.append("### E. Output Construction")
        lines.append(f"- DOCX assembly: **{round(float(dw.get('duration_ms', 0)), 1)} ms** for **{dw.get('page_count', 0)}** pages")
        _para_count = dw.get("paragraph_count")
        _run_count_dw = dw.get("run_count")
        if _para_count is not None or _run_count_dw is not None:
            lines.append(
                f"- Paragraphs: **{_para_count or 0}**, Runs: **{_run_count_dw or 0}**"
            )
        lines.append("- Tables: 0, Images: 0 (text-only pipeline)")

    # -- F. Cost Estimation --
    ce = td.get("cost_estimate")
    if isinstance(ce, dict):
        lines.append("")
        lines.append("### F. Cost Estimation")
        lines.append(f"- Model: **{ce.get('model', '?')}**")
        lines.append(
            f"- Tokens: input={ce.get('input_tokens', 0)}, "
            f"output={ce.get('output_tokens', 0)}, "
            f"reasoning={ce.get('reasoning_tokens', 0)}, "
            f"total={ce.get('total_tokens', 0)}"
        )
        cost = ce.get("estimated_cost")
        if cost is not None:
            lines.append(f"- Estimated cost: **${cost:.6f}**")
        else:
            lines.append(f"- Estimated cost: *unavailable* ({ce.get('cost_explanation', 'unknown')})")
        lines.append(f"- Pricing source: {ce.get('cost_explanation', '?')}")
        # Per-page cost breakdown
        if isinstance(per_page, list) and any(
            isinstance(p, dict) and p.get("estimated_cost") is not None for p in per_page
        ):
            lines.append("")
            lines.append("#### Per-Page Cost Breakdown")
            lines.append("")
            lines.append("| Page | In Tokens | Out Tokens | Reas Tokens | Est. Cost |")
            lines.append("|------|-----------|------------|-------------|-----------|")
            for _pp_cost in per_page:
                if not isinstance(_pp_cost, dict):
                    continue
                _c = _pp_cost.get("estimated_cost")
                _c_str = f"${_c:.6f}" if _c is not None else "-"
                lines.append(
                    f"| {_pp_cost.get('page_number', '?')}"
                    f" | {_pp_cost.get('input_tokens', 0)}"
                    f" | {_pp_cost.get('output_tokens', 0)}"
                    f" | {_pp_cost.get('reasoning_tokens', 0)}"
                    f" | {_c_str} |"
                )


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
    budget_obj = payload.get("budget", {})
    quality_obj = payload.get("quality", {})
    gmail_batch_context_obj = payload.get("gmail_batch_context", {})
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
    if not isinstance(budget_obj, dict):
        budget_obj = {}
    if not isinstance(quality_obj, dict):
        quality_obj = {}
    if not isinstance(gmail_batch_context_obj, dict):
        gmail_batch_context_obj = {}
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
    run_tokens = int(totals_obj.get("total_tokens", 0) or 0)
    billed_total_tokens = 0
    budget_post_obj = budget_obj.get("budget_post_run")
    if isinstance(budget_post_obj, dict):
        billed_total_tokens = int(budget_post_obj.get("total_tokens", 0) or 0)
    token_summary = f"run tokens `{run_tokens}`"
    if billed_total_tokens > 0 and billed_total_tokens != run_tokens:
        token_summary += f", billed total `{billed_total_tokens}` (includes reasoning)"
    lines.append(
        f"- Total wall time `{totals_obj.get('wall_seconds', 0.0)}`s, "
        f"{token_summary}, estimated cost `{totals_obj.get('estimated_cost')}`."
    )
    lines.append(
        f"- API calls `{totals_obj.get('api_calls_total', 0)}`, retries `{totals_obj.get('transport_retries_total', 0)}`, "
        f"rate-limit hits `{totals_obj.get('rate_limit_hits', 0)}`."
    )
    budget_decision = str(budget_obj.get("budget_decision", "") or "")
    budget_reason = str(budget_obj.get("budget_decision_reason", "") or "")
    cost_status = str(budget_obj.get("cost_estimation_status", "") or "")
    cost_profile_id = str(budget_obj.get("cost_profile_id", "") or "")
    budget_cap = budget_obj.get("budget_cap_usd")
    budget_pre = budget_obj.get("budget_pre_run")
    if not isinstance(budget_pre, dict):
        budget_pre = {}
    budget_pre_cost = budget_pre.get("estimated_cost_usd")
    if (
        budget_decision
        or cost_status
        or cost_profile_id
        or budget_cap is not None
    ):
        lines.append(
            f"- Budget guardrail decision `{budget_decision or 'n/a'}` "
            f"(status `{cost_status or 'unknown'}`, cap `{budget_cap}`, profile `{cost_profile_id or 'default_local'}`, "
            f"pre-run estimate `{budget_pre_cost}`)."
        )
        if budget_reason:
            lines.append(f"- Budget decision reason: `{budget_reason}`.")
    quality_risk_score = quality_obj.get("quality_risk_score")
    review_queue_count = int(quality_obj.get("review_queue_count", 0) or 0)
    if quality_risk_score is not None or review_queue_count > 0:
        lines.append(
            f"- Quality risk score `{quality_risk_score}` with "
            f"`{review_queue_count}` flagged review page(s)."
        )
    advisor_applied = _parse_optional_bool(quality_obj.get("advisor_recommendation_applied"))
    advisor_obj = quality_obj.get("advisor_recommendation")
    if not isinstance(advisor_obj, dict):
        advisor_obj = {}
    advisor_ocr_mode = str(advisor_obj.get("recommended_ocr_mode", "") or "").strip()
    advisor_image_mode = str(advisor_obj.get("recommended_image_mode", "") or "").strip()
    advisor_track = str(advisor_obj.get("advisor_track", "") or "").strip()
    advisor_confidence = advisor_obj.get("confidence")
    advisor_reasons = [
        str(item)
        for item in advisor_obj.get("recommendation_reasons", [])
        if isinstance(item, str) and str(item).strip()
    ]
    if advisor_ocr_mode or advisor_image_mode or advisor_track or advisor_confidence is not None:
        lines.append(
            f"- OCR advisor recommends OCR mode `{advisor_ocr_mode or 'n/a'}`, "
            f"image mode `{advisor_image_mode or 'n/a'}`, "
            f"track `{advisor_track or 'n/a'}`, "
            f"confidence `{advisor_confidence}`."
        )
        if advisor_reasons:
            lines.append(f"- OCR advisor reasons: `{', '.join(advisor_reasons)}`.")
    if advisor_applied is not None:
        lines.append(f"- OCR advisor recommendation applied: `{advisor_applied}`.")
    lines.append(
        f"- Failed pages `{warnings_obj.get('failed_pages_count', 0)}` "
        f"({warnings_obj.get('failed_pages', [])})."
    )
    lines.append(_ocr_summary_line(pipeline_obj))
    ocr_source_profile = str(pipeline_obj.get("ocr_source_profile", "") or "").strip()
    ocr_local_pass_strategy = str(pipeline_obj.get("ocr_local_pass_strategy", "") or "").strip()
    ocr_api_fallback_policy = str(pipeline_obj.get("ocr_api_fallback_policy", "") or "").strip()
    ocr_quality_score_avg = pipeline_obj.get("ocr_quality_score_avg")
    if (
        ocr_source_profile
        or ocr_local_pass_strategy
        or ocr_api_fallback_policy
        or ocr_quality_score_avg is not None
    ):
        lines.append(
            f"- OCR observability: profile `{ocr_source_profile or 'n/a'}`, "
            f"local strategy `{ocr_local_pass_strategy or 'n/a'}`, "
            f"fallback policy `{ocr_api_fallback_policy or 'n/a'}`, "
            f"quality score avg `{ocr_quality_score_avg}`."
        )
    ocr_track_quality_packet = pipeline_obj.get("ocr_track_quality_packet")
    if isinstance(ocr_track_quality_packet, dict):
        lines.append(
            "- OCR track quality packet: "
            f"EN/FR avg `{ocr_track_quality_packet.get('enfr_avg')}`, "
            f"AR avg `{ocr_track_quality_packet.get('ar_avg')}`, "
            f"weighted `{ocr_track_quality_packet.get('weighted_score')}` "
            "(weights EN/FR=0.60, AR=0.40)."
        )
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
    if gmail_batch_context_obj:
        lines.append(
            f"- Gmail intake session `{gmail_batch_context_obj.get('session_id', '-')}` "
            f"attachment `{gmail_batch_context_obj.get('selected_attachment_filename', '-')}` "
            f"target `{gmail_batch_context_obj.get('selected_target_lang', '-')}` "
            f"start page `{gmail_batch_context_obj.get('selected_start_page', '-')}`."
        )

    # Sanity warnings — flag empty/inconsistent reports
    _sanity_warnings: list[str] = []
    _detected_pages = int(input_obj.get("detected_page_count", 0) or 0)
    _wall_secs = float(totals_obj.get("wall_seconds", 0.0) or 0.0)
    _has_glossary_diag = bool(payload.get("glossary_diagnostics"))
    _has_translation_diag = bool(payload.get("translation_diagnostics"))
    if _detected_pages == 0:
        _sanity_warnings.append(
            f"WARNING: detected_page_count is 0. "
            f"The run may not have recorded page-level state. "
            f"Run dir: {run_obj.get('run_dir', '?')}"
        )
    if not _has_glossary_diag and not _has_translation_diag and not timeline_obj:
        _sanity_warnings.append(
            "WARNING: No diagnostics events found. "
            "Diagnostics sections will be empty. "
            "Check that run_events.jsonl exists and contains events."
        )
    if _wall_secs == 0.0 and _detected_pages > 0:
        _sanity_warnings.append(
            "WARNING: wall_seconds is 0.0 despite pages being detected. "
            "Timing data may not have been recorded."
        )
    # Check per-page rollup completeness
    _per_page_data = payload.get("per_page_rollups")
    _per_page_count = len(_per_page_data) if isinstance(_per_page_data, list) else 0
    _pages_processed = int(pipeline_obj.get("pages_processed", _per_page_count) or 0)
    if _pages_processed > 0 and _per_page_count == 0:
        _sanity_warnings.append(
            "WARNING: pages_processed > 0 but no per-page rollup data found."
        )
    if _per_page_count > 0 and _per_page_count < _pages_processed:
        _sanity_warnings.append(
            f"WARNING: per-page rollups ({_per_page_count}) < pages_processed ({_pages_processed}). "
            "Some pages may not have recorded metadata."
        )
    # Check token tracking consistency
    _api_calls = int(totals_obj.get("api_calls_total", 0) or 0)
    _total_tokens = int(totals_obj.get("total_tokens", 0) or 0)
    if _api_calls > 0 and _total_tokens == 0:
        _sanity_warnings.append(
            f"WARNING: {_api_calls} API calls recorded but total_tokens is 0. "
            "Token tracking may be broken."
        )
    # Check status=completed but timeline empty
    _run_status = str(run_obj.get("status", "") or "")
    if _run_status == "completed" and not timeline_obj:
        _sanity_warnings.append(
            "WARNING: Run status is 'completed' but timeline is empty. "
            "Events may not have been recorded."
        )
    # Check processed_pages != total_pages
    _total_pages = _detected_pages  # detected_page_count from input section
    _done_pages = len([
        p for p in (_per_page_data or [])
        if isinstance(p, dict) and p.get("status") == "done"
    ])
    if _total_pages > 0 and _per_page_count > 0 and _done_pages < _total_pages:
        _sanity_warnings.append(
            f"WARNING: Only {_done_pages}/{_total_pages} pages completed successfully."
        )
    # Store sanity summary in payload for programmatic consumers
    payload["report_sanity_summary"] = {
        "detected_page_count": _detected_pages,
        "processed_pages": _done_pages,
        "total_pages": _total_pages,
        "timeline_event_count": len(timeline_obj),
        "sanity_warnings": list(_sanity_warnings),
    }
    if _sanity_warnings:
        lines.append("")
        lines.append("## Sanity Warnings")
        for _w in _sanity_warnings:
            lines.append(f"- {_w}")

    if gmail_batch_context_obj:
        lines.append("")
        lines.append("## Gmail Intake / Batch Context")
        lines.append(f"- Source: `{gmail_batch_context_obj.get('source', '') or 'gmail_intake'}`")
        lines.append(f"- Session ID: `{gmail_batch_context_obj.get('session_id', '-')}`")
        lines.append(
            f"- Message/thread: `{gmail_batch_context_obj.get('message_id', '-')}` / "
            f"`{gmail_batch_context_obj.get('thread_id', '-')}`"
        )
        lines.append(
            f"- Selected attachment: `{gmail_batch_context_obj.get('selected_attachment_filename', '-')}` "
            f"of `{gmail_batch_context_obj.get('selected_attachment_count', 0)}` selected attachment(s)."
        )
        lines.append(f"- Selected target language: `{gmail_batch_context_obj.get('selected_target_lang', '-')}`")
        lines.append(f"- Selected start page: `{gmail_batch_context_obj.get('selected_start_page', '-')}`")
        report_path = str(gmail_batch_context_obj.get("gmail_batch_session_report_path", "") or "")
        if report_path:
            lines.append(f"- Gmail batch session report: `{report_path}`")

    lines.append("")
    lines.append("## Timeline")
    lines.extend(_build_timeline_lines(timeline_obj))

    # -- Glossary Diagnostics sections --
    gd = payload.get("glossary_diagnostics")
    if isinstance(gd, dict) and gd:
        _render_glossary_diagnostics_markdown(lines, gd)

    # -- Translation Diagnostics sections --
    td = payload.get("translation_diagnostics")
    if isinstance(td, dict) and td:
        _render_translation_diagnostics_markdown(
            lines, td,
            per_page=payload.get("per_page_rollups"),
            snippets=payload.get("translated_snippets"),
        )

    if admin_mode and not (isinstance(td, dict) and td):
        # Legacy Per-Page Rollups: only when no translation diagnostics
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

    if admin_mode and not (isinstance(td, dict) and td):
        # Legacy Sanitized Snippets: only when no translation diagnostics
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
