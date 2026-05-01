"""Local-only one-shot Windows window tracing for cold Gmail launches."""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import time
from typing import Any
from uuid import uuid4

from .user_settings import APP_FOLDER_NAME


DEFAULT_TRACE_DURATION_SECONDS = 15.0
DEFAULT_TRACE_SAMPLE_INTERVAL_MS = 200
_WINDOW_TRACE_SUBDIR = Path("diagnostics") / "window_traces"
_WINDOW_TRACE_ARM_FILENAME = "_next_cold_start_window_trace.json"
_WINDOW_TRACE_SESSION_STATE_FILENAME = "_latest_launch_session.json"
_GW_OWNER = 4
_GWL_STYLE = -16
_GWL_EXSTYLE = -20
_DWMWA_CLOAKED = 14
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _is_windows() -> bool:
    return os.name == "nt"


def default_runtime_state_root() -> Path:
    appdata = str(os.environ.get("APPDATA", "") or "").strip()
    if appdata:
        return Path(appdata).expanduser().resolve() / APP_FOLDER_NAME
    return (Path.home() / ".legalpdf_translate" / APP_FOLDER_NAME).expanduser().resolve()


def _looks_like_repo_worktree(path: Path) -> bool:
    candidate = path.expanduser().resolve()
    return (
        (candidate / "src" / "legalpdf_translate" / "gmail_focus_host.py").exists()
        and (candidate / "tooling" / "launch_browser_app_live_detached.py").exists()
    )


def resolve_runtime_state_root(base_dir: Path | None = None) -> Path:
    if base_dir is None:
        return default_runtime_state_root()
    resolved = base_dir.expanduser().resolve()
    # Launch-session state is machine runtime state, not repo-local diagnostics.
    # If a repo root leaks into this API, snap back to the canonical app-data root.
    if _looks_like_repo_worktree(resolved):
        return default_runtime_state_root()
    return resolved


def window_trace_root(base_dir: Path) -> Path:
    return resolve_runtime_state_root(base_dir) / _WINDOW_TRACE_SUBDIR


def window_trace_arm_path(base_dir: Path) -> Path:
    return window_trace_root(base_dir) / _WINDOW_TRACE_ARM_FILENAME


def launch_session_state_path(base_dir: Path) -> Path:
    return window_trace_root(base_dir) / _WINDOW_TRACE_SESSION_STATE_FILENAME


def launch_session_trace_dir(base_dir: Path, launch_session_id: str) -> Path:
    cleaned = str(launch_session_id or "").strip()
    if cleaned == "":
        raise ValueError("launch_session_id is required.")
    return window_trace_root(base_dir) / cleaned


def build_launch_session_id() -> str:
    return f"{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:12]}"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temp_path = resolved.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(resolved)
    return resolved


def _read_json(path: Path) -> dict[str, Any] | None:
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        return None
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def arm_next_cold_start_window_trace(
    *,
    base_dir: Path,
    duration_seconds: float = DEFAULT_TRACE_DURATION_SECONDS,
    sample_interval_ms: int = DEFAULT_TRACE_SAMPLE_INTERVAL_MS,
) -> dict[str, Any]:
    duration = max(1.0, float(duration_seconds or DEFAULT_TRACE_DURATION_SECONDS))
    interval_ms = max(50, int(sample_interval_ms or DEFAULT_TRACE_SAMPLE_INTERVAL_MS))
    root = window_trace_root(base_dir)
    arm_payload = {
        "armed": True,
        "armed_at": _utc_now_iso(),
        "duration_seconds": duration,
        "sample_interval_ms": interval_ms,
        "arm_path": str(window_trace_arm_path(base_dir)),
        "trace_root": str(root),
    }
    _write_json(window_trace_arm_path(base_dir), arm_payload)
    latest_state = read_launch_session_state(base_dir)
    return {
        "armed": True,
        "reason": "next_cold_start_window_trace_armed",
        "duration_seconds": duration,
        "sample_interval_ms": interval_ms,
        "arm_path": str(window_trace_arm_path(base_dir)),
        "trace_root": str(root),
        "latest_launch_session": latest_state,
    }


def consume_armed_window_trace(base_dir: Path) -> dict[str, Any] | None:
    arm_path = window_trace_arm_path(base_dir)
    payload = _read_json(arm_path)
    try:
        arm_path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass
    if payload is None:
        return None
    try:
        duration_seconds = max(1.0, float(payload.get("duration_seconds", DEFAULT_TRACE_DURATION_SECONDS) or DEFAULT_TRACE_DURATION_SECONDS))
    except (TypeError, ValueError):
        duration_seconds = DEFAULT_TRACE_DURATION_SECONDS
    try:
        sample_interval_ms = max(50, int(payload.get("sample_interval_ms", DEFAULT_TRACE_SAMPLE_INTERVAL_MS) or DEFAULT_TRACE_SAMPLE_INTERVAL_MS))
    except (TypeError, ValueError):
        sample_interval_ms = DEFAULT_TRACE_SAMPLE_INTERVAL_MS
    return {
        "armed": True,
        "armed_at": str(payload.get("armed_at", "") or "").strip() or _utc_now_iso(),
        "duration_seconds": duration_seconds,
        "sample_interval_ms": sample_interval_ms,
        "arm_path": str(arm_path),
        "trace_root": str(window_trace_root(base_dir)),
    }


def read_launch_session_state(base_dir: Path) -> dict[str, Any] | None:
    return _read_json(launch_session_state_path(base_dir))


def write_launch_session_state(base_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload or {})
    normalized["updated_at"] = _utc_now_iso()
    _write_json(launch_session_state_path(base_dir), normalized)
    return normalized


def update_launch_session_state(
    base_dir: Path,
    *,
    launch_session_id: str,
    **fields: object,
) -> dict[str, Any]:
    existing = read_launch_session_state(base_dir) or {}
    if str(existing.get("launch_session_id", "") or "").strip() != str(launch_session_id or "").strip():
        existing = {
            "launch_session_id": str(launch_session_id or "").strip(),
        }
    existing.update(fields)
    return write_launch_session_state(base_dir, existing)


def latest_window_trace_status(base_dir: Path) -> dict[str, Any]:
    runtime_state_root = resolve_runtime_state_root(base_dir)
    state = read_launch_session_state(base_dir) or {}
    summary_path = Path(str(state.get("trace_summary_path", "") or "").strip()) if state.get("trace_summary_path") else None
    summary_payload: dict[str, Any] | None = None
    if summary_path:
        summary_payload = _read_json(summary_path)
    return {
        "runtime_state_root": str(runtime_state_root),
        "launch_session_id": str(state.get("launch_session_id", "") or "").strip(),
        "handoff_session_id": str(state.get("handoff_session_id", "") or "").strip(),
        "status": str(state.get("status", "") or "").strip(),
        "trace_status": str(state.get("trace_status", "") or "").strip(),
        "trace_requested": bool(state.get("trace_requested")),
        "trace_dir": str(state.get("trace_dir", "") or "").strip(),
        "trace_samples_path": str(state.get("trace_samples_path", "") or "").strip(),
        "trace_summary_path": str(state.get("trace_summary_path", "") or "").strip(),
        "browser_url": str(state.get("browser_url", "") or "").strip(),
        "workspace_id": str(state.get("workspace_id", "") or "").strip(),
        "runtime_mode": str(state.get("runtime_mode", "") or "").strip(),
        "browser_open_owned_by": str(state.get("browser_open_owned_by", "") or "").strip(),
        "launch_phase": str(state.get("launch_phase", "") or "").strip(),
        "native_host_path_kind": str(state.get("native_host_path_kind", "") or "").strip(),
        "click_phase": str(state.get("click_phase", "") or "").strip(),
        "click_failure_reason": str(state.get("click_failure_reason", "") or "").strip(),
        "source_gmail_url": str(state.get("source_gmail_url", "") or "").strip(),
        "tab_resolution_strategy": str(state.get("tab_resolution_strategy", "") or "").strip(),
        "workspace_surface_confirmed": bool(state.get("workspace_surface_confirmed")),
        "client_hydration_status": str(state.get("client_hydration_status", "") or "").strip(),
        "extension_surface_outcome": str(state.get("extension_surface_outcome", "") or "").strip(),
        "extension_surface_reason": str(state.get("extension_surface_reason", "") or "").strip(),
        "extension_surface_tab_id": _safe_int(state.get("extension_surface_tab_id", 0)),
        "surface_candidate_source": str(state.get("surface_candidate_source", "") or "").strip(),
        "surface_candidate_valid": bool(state.get("surface_candidate_valid")),
        "surface_invalidation_reason": str(state.get("surface_invalidation_reason", "") or "").strip(),
        "fresh_tab_created_after_invalidation": bool(state.get("fresh_tab_created_after_invalidation")),
        "bridge_context_posted": bool(state.get("bridge_context_posted")),
        "surface_visibility_status": str(state.get("surface_visibility_status", "") or "").strip(),
        "runtime_state_root_compatible": bool(state.get("runtime_state_root_compatible")),
        "expected_runtime_state_root": str(state.get("expected_runtime_state_root", "") or "").strip(),
        "observed_runtime_state_root": str(state.get("observed_runtime_state_root", "") or "").strip(),
        "browser_launch_status": str(state.get("browser_launch_status", "") or "").strip(),
        "browser_launch_reason": str(state.get("browser_launch_reason", "") or "").strip(),
        "launched_browser_pid": _safe_int(state.get("launched_browser_pid", 0)),
        "launched_browser_path": str(state.get("launched_browser_path", "") or "").strip(),
        "launched_browser_user_data_dir": str(state.get("launched_browser_user_data_dir", "") or "").strip(),
        "launched_browser_profile": str(state.get("launched_browser_profile", "") or "").strip(),
        "launched_browser_command": str(state.get("launched_browser_command", "") or "").strip(),
        "launch_runtime_path": str(state.get("launch_runtime_path", "") or "").strip(),
        "updated_at": str(state.get("updated_at", "") or "").strip(),
        "trace_summary": summary_payload or {},
    }


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _is_edge_window(window: dict[str, Any]) -> bool:
    process_image_path = _safe_text(window.get("process_image_path")).replace("/", "\\").casefold()
    class_name = _safe_text(window.get("class_name")).casefold()
    title = _safe_text(window.get("title")).casefold()
    legalpdf_title = (
        "legalpdf translate browser app" in title
        or "127.0.0.1:8877" in title
        or "gmail-intake" in title
    )
    if process_image_path.endswith("\\msedge.exe"):
        return True
    if process_image_path != "":
        return legalpdf_title
    if class_name.startswith("chrome_widgetwin") and legalpdf_title:
        return True
    return legalpdf_title


def _is_console_helper_window(
    window: dict[str, Any],
    *,
    launch_metadata: dict[str, Any] | None = None,
) -> bool:
    process_image_path = _safe_text(window.get("process_image_path")).replace("/", "\\").casefold()
    class_name = _safe_text(window.get("class_name")).casefold()
    launch_runtime_path = _safe_text((launch_metadata or {}).get("launch_runtime_path")).replace("/", "\\").casefold()
    if launch_runtime_path != "" and process_image_path == launch_runtime_path:
        return True
    if class_name == "consolewindowclass":
        return True
    return process_image_path.endswith(
        (
            "\\conhost.exe",
            "\\powershell.exe",
            "\\pwsh.exe",
            "\\cmd.exe",
            "\\python.exe",
        )
    )


def _is_legalpdf_surface(window: dict[str, Any]) -> bool:
    if not _is_edge_window(window):
        return False
    title = _safe_text(window.get("title")).casefold()
    return (
        "legalpdf translate browser app" in title
        or "127.0.0.1:8877" in title
        or "gmail-intake" in title
    )


def _is_blank_or_cloaked_browser_window(window: dict[str, Any]) -> bool:
    if not _is_edge_window(window):
        return False
    title = _safe_text(window.get("title"))
    rect = window.get("rect") if isinstance(window.get("rect"), dict) else {}
    width = int(rect.get("width", 0) or 0)
    height = int(rect.get("height", 0) or 0)
    return title == "" or bool(window.get("cloaked")) or width <= 40 or height <= 40


def _window_rect_size(window: dict[str, Any]) -> tuple[int, int]:
    rect = window.get("rect") if isinstance(window.get("rect"), dict) else {}
    width = int(rect.get("width", 0) or 0)
    height = int(rect.get("height", 0) or 0)
    return width, height


def _is_visible_edge_surface(window: dict[str, Any]) -> bool:
    if not _is_edge_window(window):
        return False
    if not bool(window.get("visible")):
        return False
    if bool(window.get("minimized")) or bool(window.get("cloaked")):
        return False
    title = _safe_text(window.get("title"))
    width, height = _window_rect_size(window)
    return title != "" and width >= 320 and height >= 240


def _is_hidden_or_cloaked_edge_utility(window: dict[str, Any]) -> bool:
    return _is_edge_window(window) and not _is_visible_edge_surface(window)


def _is_visible_console_helper_window(
    window: dict[str, Any],
    *,
    launch_metadata: dict[str, Any] | None = None,
) -> bool:
    if not _is_console_helper_window(window, launch_metadata=launch_metadata):
        return False
    if not bool(window.get("visible")):
        return False
    if bool(window.get("minimized")) or bool(window.get("cloaked")):
        return False
    if _safe_text(window.get("class_name")).casefold() == "pseudoconsolewindow":
        # Pseudo consoles can present as transient transparent surfaces even
        # when Win32 reports a zero-sized rect.
        return True
    width, height = _window_rect_size(window)
    return width >= 120 and height >= 80


def summarize_window_trace_samples(
    samples: list[dict[str, Any]],
    *,
    launch_session_id: str,
    browser_url: str = "",
    trace_dir: Path | None = None,
    samples_path: Path | None = None,
    launched_browser_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    launch_metadata = dict(launched_browser_metadata or {})
    max_edge_window_count = 0
    max_legalpdf_surface_count = 0
    max_visible_edge_surface_count = 0
    max_visible_legalpdf_surface_count = 0
    max_console_helper_window_count = 0
    max_visible_console_helper_window_count = 0
    blank_or_cloaked_count = 0
    hidden_or_cloaked_edge_utility_count = 0
    unique_edge_hwnds: set[int] = set()
    unique_legalpdf_hwnds: set[int] = set()
    unique_visible_edge_hwnds: set[int] = set()
    unique_visible_legalpdf_hwnds: set[int] = set()
    unique_console_helper_hwnds: set[int] = set()
    unique_visible_console_helper_hwnds: set[int] = set()
    new_top_level_edge_hwnds: set[int] = set()
    new_top_level_console_helper_hwnds: set[int] = set()
    edge_churn_events = 0
    console_helper_churn_events = 0
    edge_title_transition_count = 0
    new_tab_to_legalpdf_transition_count = 0
    previous_edge_hwnds: set[int] | None = None
    previous_console_helper_hwnds: set[int] | None = None
    baseline_edge_hwnds: set[int] | None = None
    baseline_console_helper_hwnds: set[int] | None = None
    seen_edge_hwnds: set[int] = set()
    seen_console_helper_hwnds: set[int] = set()
    last_titles_by_hwnd: dict[int, str] = {}
    title_transition_events: list[dict[str, Any]] = []

    for sample in samples:
        windows = [item for item in sample.get("windows", []) if isinstance(item, dict)]
        edge_windows = [item for item in windows if _is_edge_window(item)]
        legalpdf_windows = [item for item in edge_windows if _is_legalpdf_surface(item)]
        visible_edge_windows = [item for item in edge_windows if _is_visible_edge_surface(item)]
        visible_legalpdf_windows = [item for item in visible_edge_windows if _is_legalpdf_surface(item)]
        console_helper_windows = [item for item in windows if _is_console_helper_window(item, launch_metadata=launch_metadata)]
        visible_console_helper_windows = [
            item for item in console_helper_windows if _is_visible_console_helper_window(item, launch_metadata=launch_metadata)
        ]
        max_edge_window_count = max(max_edge_window_count, len(edge_windows))
        max_legalpdf_surface_count = max(max_legalpdf_surface_count, len(legalpdf_windows))
        max_visible_edge_surface_count = max(max_visible_edge_surface_count, len(visible_edge_windows))
        max_visible_legalpdf_surface_count = max(max_visible_legalpdf_surface_count, len(visible_legalpdf_windows))
        max_console_helper_window_count = max(max_console_helper_window_count, len(console_helper_windows))
        max_visible_console_helper_window_count = max(
            max_visible_console_helper_window_count,
            len(visible_console_helper_windows),
        )
        blank_or_cloaked_count += sum(1 for item in edge_windows if _is_blank_or_cloaked_browser_window(item))
        hidden_or_cloaked_edge_utility_count += sum(1 for item in edge_windows if _is_hidden_or_cloaked_edge_utility(item))

        current_edge_hwnds = {
            int(item.get("hwnd", 0) or 0)
            for item in edge_windows
            if int(item.get("hwnd", 0) or 0) > 0
        }
        current_legalpdf_hwnds = {
            int(item.get("hwnd", 0) or 0)
            for item in legalpdf_windows
            if int(item.get("hwnd", 0) or 0) > 0
        }
        current_visible_edge_hwnds = {
            int(item.get("hwnd", 0) or 0)
            for item in visible_edge_windows
            if int(item.get("hwnd", 0) or 0) > 0
        }
        current_visible_legalpdf_hwnds = {
            int(item.get("hwnd", 0) or 0)
            for item in visible_legalpdf_windows
            if int(item.get("hwnd", 0) or 0) > 0
        }
        current_console_helper_hwnds = {
            int(item.get("hwnd", 0) or 0)
            for item in console_helper_windows
            if int(item.get("hwnd", 0) or 0) > 0
        }
        current_visible_console_helper_hwnds = {
            int(item.get("hwnd", 0) or 0)
            for item in visible_console_helper_windows
            if int(item.get("hwnd", 0) or 0) > 0
        }
        unique_edge_hwnds.update(current_edge_hwnds)
        unique_legalpdf_hwnds.update(current_legalpdf_hwnds)
        unique_visible_edge_hwnds.update(current_visible_edge_hwnds)
        unique_visible_legalpdf_hwnds.update(current_visible_legalpdf_hwnds)
        unique_console_helper_hwnds.update(current_console_helper_hwnds)
        unique_visible_console_helper_hwnds.update(current_visible_console_helper_hwnds)
        if baseline_edge_hwnds is None:
            baseline_edge_hwnds = set(current_edge_hwnds)
            seen_edge_hwnds.update(current_edge_hwnds)
        else:
            newly_created_hwnds = {
                hwnd for hwnd in current_edge_hwnds
                if hwnd not in seen_edge_hwnds and hwnd not in baseline_edge_hwnds
            }
            new_top_level_edge_hwnds.update(newly_created_hwnds)
            seen_edge_hwnds.update(current_edge_hwnds)
        if baseline_console_helper_hwnds is None:
            baseline_console_helper_hwnds = set(current_console_helper_hwnds)
            seen_console_helper_hwnds.update(current_console_helper_hwnds)
        else:
            newly_created_console_helper_hwnds = {
                hwnd for hwnd in current_console_helper_hwnds
                if hwnd not in seen_console_helper_hwnds and hwnd not in baseline_console_helper_hwnds
            }
            new_top_level_console_helper_hwnds.update(newly_created_console_helper_hwnds)
            seen_console_helper_hwnds.update(current_console_helper_hwnds)
        if previous_edge_hwnds is not None:
            edge_churn_events += len(current_edge_hwnds - previous_edge_hwnds)
            edge_churn_events += len(previous_edge_hwnds - current_edge_hwnds)
        if previous_console_helper_hwnds is not None:
            console_helper_churn_events += len(current_console_helper_hwnds - previous_console_helper_hwnds)
            console_helper_churn_events += len(previous_console_helper_hwnds - current_console_helper_hwnds)
        previous_edge_hwnds = current_edge_hwnds
        previous_console_helper_hwnds = current_console_helper_hwnds
        for item in edge_windows:
            hwnd = int(item.get("hwnd", 0) or 0)
            if hwnd <= 0:
                continue
            current_title = _safe_text(item.get("title"))
            previous_title = last_titles_by_hwnd.get(hwnd)
            if previous_title is not None and previous_title != current_title:
                edge_title_transition_count += 1
                if "new tab" in previous_title.casefold() and _is_legalpdf_surface(item):
                    new_tab_to_legalpdf_transition_count += 1
                if len(title_transition_events) < 25:
                    title_transition_events.append(
                        {
                            "hwnd": hwnd,
                            "from_title": previous_title,
                            "to_title": current_title,
                            "sample_index": int(sample.get("sample_index", 0) or 0),
                            "relative_ms": int(sample.get("relative_ms", 0) or 0),
                        }
                    )
            last_titles_by_hwnd[hwnd] = current_title

    flags = {
        "multiple_edge_windows_detected": max_edge_window_count > 1,
        "blank_or_cloaked_browser_windows_detected": blank_or_cloaked_count > 0,
        "repeated_window_churn_detected": edge_churn_events >= 2,
        "multiple_legalpdf_surfaces_detected": max_legalpdf_surface_count > 1,
        "multiple_visible_edge_surfaces_detected": max_visible_edge_surface_count > 1,
        "multiple_visible_legalpdf_surfaces_detected": max_visible_legalpdf_surface_count > 1,
        "hidden_or_cloaked_edge_utilities_detected": hidden_or_cloaked_edge_utility_count > 0,
        "new_top_level_edge_windows_detected": len(new_top_level_edge_hwnds) > 0,
        "new_tab_to_legalpdf_transition_detected": new_tab_to_legalpdf_transition_count > 0,
        "console_helper_windows_detected": max_console_helper_window_count > 0,
        "multiple_visible_console_helper_windows_detected": max_visible_console_helper_window_count > 1,
        "repeated_console_helper_window_churn_detected": console_helper_churn_events >= 2,
        "new_top_level_console_helper_windows_detected": len(new_top_level_console_helper_hwnds) > 0,
    }

    summary = {
        "launch_session_id": str(launch_session_id or "").strip(),
        "browser_url": str(browser_url or "").strip(),
        "captured_at": _utc_now_iso(),
        "sample_count": len(samples),
        "max_edge_window_count": max_edge_window_count,
        "max_legalpdf_surface_count": max_legalpdf_surface_count,
        "max_visible_edge_surface_count": max_visible_edge_surface_count,
        "max_visible_legalpdf_surface_count": max_visible_legalpdf_surface_count,
        "max_console_helper_window_count": max_console_helper_window_count,
        "max_visible_console_helper_window_count": max_visible_console_helper_window_count,
        "blank_or_cloaked_browser_window_count": blank_or_cloaked_count,
        "hidden_or_cloaked_edge_utility_count": hidden_or_cloaked_edge_utility_count,
        "edge_churn_events": edge_churn_events,
        "console_helper_churn_events": console_helper_churn_events,
        "new_top_level_edge_window_count": len(new_top_level_edge_hwnds),
        "new_top_level_edge_hwnd_ids": sorted(new_top_level_edge_hwnds),
        "new_top_level_console_helper_window_count": len(new_top_level_console_helper_hwnds),
        "new_top_level_console_helper_hwnd_ids": sorted(new_top_level_console_helper_hwnds),
        "edge_title_transition_count": edge_title_transition_count,
        "new_tab_to_legalpdf_transition_count": new_tab_to_legalpdf_transition_count,
        "title_transition_events": title_transition_events,
        "unique_edge_window_count": len(unique_edge_hwnds),
        "unique_legalpdf_surface_count": len(unique_legalpdf_hwnds),
        "unique_visible_edge_surface_count": len(unique_visible_edge_hwnds),
        "unique_visible_legalpdf_surface_count": len(unique_visible_legalpdf_hwnds),
        "unique_console_helper_window_count": len(unique_console_helper_hwnds),
        "unique_visible_console_helper_window_count": len(unique_visible_console_helper_hwnds),
        "flags": flags,
        "trace_dir": str(trace_dir) if trace_dir is not None else "",
        "samples_path": str(samples_path) if samples_path is not None else "",
    }
    if isinstance(launched_browser_metadata, dict):
        summary.update(
            {
                "launched_browser_pid": _safe_int(launched_browser_metadata.get("launched_browser_pid", 0)),
                "launched_browser_path": str(launched_browser_metadata.get("launched_browser_path", "") or "").strip(),
                "launched_browser_user_data_dir": str(launched_browser_metadata.get("launched_browser_user_data_dir", "") or "").strip(),
                "launched_browser_profile": str(launched_browser_metadata.get("launched_browser_profile", "") or "").strip(),
                "launched_browser_command": str(launched_browser_metadata.get("launched_browser_command", "") or "").strip(),
                "browser_launch_status": str(launched_browser_metadata.get("browser_launch_status", "") or "").strip(),
                "browser_launch_reason": str(launched_browser_metadata.get("browser_launch_reason", "") or "").strip(),
                "launch_runtime_path": str(launched_browser_metadata.get("launch_runtime_path", "") or "").strip(),
                "launch_phase": str(launched_browser_metadata.get("launch_phase", "") or "").strip(),
                "native_host_path_kind": str(launched_browser_metadata.get("native_host_path_kind", "") or "").strip(),
            }
        )
    return summary


def _enum_top_level_windows() -> list[int]:
    if not _is_windows():
        return []
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    hwnds: list[int] = []

    @enum_proc_type
    def _callback(hwnd, _lparam):
        hwnd_value = int(hwnd)
        if hwnd_value > 0:
            hwnds.append(hwnd_value)
        return True

    user32.EnumWindows(_callback, 0)
    return hwnds


def _window_text(hwnd: int) -> str:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    length = int(user32.GetWindowTextLengthW(wintypes.HWND(hwnd)))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    copied = int(user32.GetWindowTextW(wintypes.HWND(hwnd), buffer, length + 1))
    if copied <= 0:
        return ""
    return str(buffer.value[:copied]).strip()


def _window_class_name(hwnd: int) -> str:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    buffer = ctypes.create_unicode_buffer(256)
    copied = int(user32.GetClassNameW(wintypes.HWND(hwnd), buffer, len(buffer)))
    if copied <= 0:
        return ""
    return str(buffer.value[:copied]).strip()


def _window_rect(hwnd: int) -> dict[str, int]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    rect = _RECT()
    if not bool(user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(rect))):
        return {
            "left": 0,
            "top": 0,
            "right": 0,
            "bottom": 0,
            "width": 0,
            "height": 0,
        }
    return {
        "left": int(rect.left),
        "top": int(rect.top),
        "right": int(rect.right),
        "bottom": int(rect.bottom),
        "width": max(0, int(rect.right - rect.left)),
        "height": max(0, int(rect.bottom - rect.top)),
    }


def _window_long_ptr(hwnd: int, index: int) -> int:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    getter = getattr(user32, "GetWindowLongPtrW", None)
    if getter is not None:
        getter.restype = ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
        return int(getter(wintypes.HWND(hwnd), index))
    legacy = user32.GetWindowLongW
    legacy.restype = ctypes.c_long
    return int(legacy(wintypes.HWND(hwnd), index))


def _window_owner(hwnd: int) -> int | None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    owner = int(user32.GetWindow(wintypes.HWND(hwnd), _GW_OWNER))
    return owner if owner > 0 else None


def _window_pid_and_thread(hwnd: int) -> tuple[int | None, int | None]:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    pid = wintypes.DWORD(0)
    thread_id = int(user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid)))
    pid_value = int(pid.value)
    return (pid_value if pid_value > 0 else None, thread_id if thread_id > 0 else None)


def _window_visible(hwnd: int) -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    return bool(user32.IsWindowVisible(wintypes.HWND(hwnd)))


def _window_minimized(hwnd: int) -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    return bool(user32.IsIconic(wintypes.HWND(hwnd)))


def _window_cloaked(hwnd: int) -> bool:
    try:
        dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
    except OSError:
        return False
    cloaked = wintypes.DWORD(0)
    result = int(
        dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            _DWMWA_CLOAKED,
            ctypes.byref(cloaked),
            ctypes.sizeof(cloaked),
        )
    )
    return result == 0 and int(cloaked.value) != 0


def _process_image_path(pid: int | None) -> str:
    if not _is_windows() or pid is None or pid <= 0:
        return ""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(int(size.value))
        ok = kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size))
        if not ok:
            return ""
        return str(buffer.value[: int(size.value)]).strip()
    finally:
        kernel32.CloseHandle(handle)


def capture_window_snapshot(hwnd: int) -> dict[str, Any]:
    pid, thread_id = _window_pid_and_thread(hwnd)
    return {
        "hwnd": int(hwnd),
        "pid": pid,
        "thread_id": thread_id,
        "title": _window_text(hwnd),
        "class_name": _window_class_name(hwnd),
        "visible": _window_visible(hwnd),
        "minimized": _window_minimized(hwnd),
        "owner_hwnd": _window_owner(hwnd),
        "rect": _window_rect(hwnd),
        "cloaked": _window_cloaked(hwnd),
        "style": _window_long_ptr(hwnd, _GWL_STYLE),
        "exstyle": _window_long_ptr(hwnd, _GWL_EXSTYLE),
        "process_image_path": _process_image_path(pid),
    }


def capture_window_trace(
    *,
    base_dir: Path,
    launch_session_id: str,
    browser_url: str = "",
    duration_seconds: float = DEFAULT_TRACE_DURATION_SECONDS,
    sample_interval_ms: int = DEFAULT_TRACE_SAMPLE_INTERVAL_MS,
) -> dict[str, Any]:
    trace_dir = launch_session_trace_dir(base_dir, launch_session_id).expanduser().resolve()
    trace_dir.mkdir(parents=True, exist_ok=True)
    samples_path = trace_dir / "samples.jsonl"
    summary_path = trace_dir / "summary.json"

    if not _is_windows():
        summary = {
            "launch_session_id": str(launch_session_id or "").strip(),
            "browser_url": str(browser_url or "").strip(),
            "captured_at": _utc_now_iso(),
            "reason": "unsupported_platform",
            "sample_count": 0,
            "flags": {},
            "trace_dir": str(trace_dir),
            "samples_path": str(samples_path),
        }
        _write_json(summary_path, summary)
        update_launch_session_state(
            base_dir,
            launch_session_id=launch_session_id,
            trace_status="unsupported_platform",
            trace_dir=str(trace_dir),
            trace_samples_path=str(samples_path),
            trace_summary_path=str(summary_path),
        )
        return summary

    samples: list[dict[str, Any]] = []
    start = time.monotonic()
    deadline = start + max(1.0, float(duration_seconds or DEFAULT_TRACE_DURATION_SECONDS))
    interval_seconds = max(0.05, int(sample_interval_ms or DEFAULT_TRACE_SAMPLE_INTERVAL_MS) / 1000.0)

    with samples_path.open("w", encoding="utf-8") as handle:
        sample_index = 0
        while True:
            captured_at = _utc_now_iso()
            now = time.monotonic()
            sample = {
                "launch_session_id": str(launch_session_id or "").strip(),
                "sample_index": sample_index,
                "captured_at": captured_at,
                "relative_ms": int((now - start) * 1000),
                "windows": [capture_window_snapshot(hwnd) for hwnd in _enum_top_level_windows()],
            }
            handle.write(json.dumps(sample, ensure_ascii=False) + "\n")
            handle.flush()
            samples.append(sample)
            sample_index += 1
            if now >= deadline:
                break
            time.sleep(interval_seconds)

    launch_metadata = read_launch_session_state(base_dir) or {}
    if str(launch_metadata.get("launch_session_id", "") or "").strip() != str(launch_session_id or "").strip():
        launch_metadata = {}

    summary = summarize_window_trace_samples(
        samples,
        launch_session_id=launch_session_id,
        browser_url=browser_url,
        trace_dir=trace_dir,
        samples_path=samples_path,
        launched_browser_metadata=launch_metadata,
    )
    _write_json(summary_path, summary)
    update_launch_session_state(
        base_dir,
        launch_session_id=launch_session_id,
        trace_status="completed",
        trace_dir=str(trace_dir),
        trace_samples_path=str(samples_path),
        trace_summary_path=str(summary_path),
        trace_flags=summary.get("flags", {}),
    )
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Capture a one-shot local window trace for Gmail cold launch diagnostics.")
    parser.add_argument("--base-dir", required=True, help="App data directory for LegalPDF Translate.")
    parser.add_argument("--launch-session-id", required=True, help="Correlated launch session identifier.")
    parser.add_argument("--browser-url", default="", help="Browser URL for the launch session.")
    parser.add_argument("--duration-seconds", type=float, default=DEFAULT_TRACE_DURATION_SECONDS)
    parser.add_argument("--sample-interval-ms", type=int, default=DEFAULT_TRACE_SAMPLE_INTERVAL_MS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    capture_window_trace(
        base_dir=Path(args.base_dir),
        launch_session_id=str(args.launch_session_id or "").strip(),
        browser_url=str(args.browser_url or "").strip(),
        duration_seconds=float(args.duration_seconds or DEFAULT_TRACE_DURATION_SECONDS),
        sample_interval_ms=int(args.sample_interval_ms or DEFAULT_TRACE_SAMPLE_INTERVAL_MS),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
