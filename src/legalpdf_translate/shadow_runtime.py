"""Runtime/state helpers for the local browser-hosted shadow harness."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .build_identity import RuntimeBuildIdentity, detect_runtime_build_identity, normalize_path_identity
from .gmail_focus import detect_listener_pid
from .joblog_db import JOB_LOG_DB_FILENAME
from .user_settings import (
    APP_FOLDER_NAME,
    SETTINGS_FILENAME,
    app_data_dir_from_settings_path,
    load_gui_settings_from_path,
    settings_path as live_settings_path,
)

SHADOW_HOST = "127.0.0.1"
SHADOW_DEFAULT_PORT = 8877
SHADOW_APP_FOLDER_NAME = f"{APP_FOLDER_NAME}Shadow"
SHADOW_RUNTIME_METADATA_FILENAME = "shadow_runtime.json"
RUNTIME_MODE_SHADOW = "shadow"
RUNTIME_MODE_LIVE = "live"
RUNTIME_MODE_CHOICES = (RUNTIME_MODE_SHADOW, RUNTIME_MODE_LIVE)
_SHADOW_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9._-]+")
_AUTOMATION_FAILURE_SEMANTICS = {
    "unavailable": "host/toolchain cannot execute automation preflight or flow",
    "failed": "automation executed but flow assertions failed",
}
_DARTDEV_AOT_MARKERS = (
    "Unable to find AOT snapshot for dartdev",
    "Could not find a command named",
)


@dataclass(frozen=True, slots=True)
class ShadowRuntimePaths:
    app_data_dir: Path
    settings_path: Path
    job_log_db_path: Path
    outputs_dir: Path
    uploads_dir: Path
    runtime_metadata_path: Path


@dataclass(frozen=True, slots=True)
class ShadowListenerOwnership:
    host: str
    port: int
    status: str
    pid: int | None
    reason: str


@dataclass(frozen=True, slots=True)
class BrowserDataPaths:
    mode: str
    label: str
    app_data_dir: Path
    settings_path: Path
    job_log_db_path: Path
    outputs_dir: Path
    live_data: bool
    banner_text: str


def _default_appdata_root() -> Path:
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        return Path(appdata).expanduser().resolve()
    return (Path.home() / ".legalpdf_translate").expanduser().resolve()


def _safe_token(value: str, *, fallback: str) -> str:
    cleaned = _SHADOW_SAFE_TOKEN_RE.sub("-", str(value or "").strip()).strip("._-")
    return cleaned or fallback


def normalize_runtime_mode(value: object) -> str:
    candidate = str(value or "").strip().lower()
    if candidate == RUNTIME_MODE_LIVE:
        return RUNTIME_MODE_LIVE
    return RUNTIME_MODE_SHADOW


def normalize_workspace_id(value: object, *, fallback: str = "workspace-1") -> str:
    cleaned = _safe_token(str(value or ""), fallback=fallback)
    return cleaned or fallback


def shadow_build_key(identity: RuntimeBuildIdentity | None = None, *, repo: Path | None = None) -> str:
    resolved_identity = identity or detect_runtime_build_identity(repo=repo, labels=("shadow-web",))
    repo_identity = normalize_path_identity(resolved_identity.worktree_path)
    repo_hash = hashlib.sha1(repo_identity.encode("utf-8")).hexdigest()[:8]
    branch = _safe_token(resolved_identity.branch, fallback="head")
    return f"{branch}-{repo_hash}"


def shadow_app_data_dir(
    *,
    repo: Path | None = None,
    identity: RuntimeBuildIdentity | None = None,
    appdata_root: Path | None = None,
) -> Path:
    base_root = (appdata_root or _default_appdata_root()).expanduser().resolve()
    key = shadow_build_key(identity, repo=repo)
    return base_root / SHADOW_APP_FOLDER_NAME / key


def detect_shadow_runtime_paths(
    *,
    repo: Path | None = None,
    identity: RuntimeBuildIdentity | None = None,
    appdata_root: Path | None = None,
) -> ShadowRuntimePaths:
    app_data = shadow_app_data_dir(repo=repo, identity=identity, appdata_root=appdata_root)
    return ShadowRuntimePaths(
        app_data_dir=app_data,
        settings_path=app_data / SETTINGS_FILENAME,
        job_log_db_path=app_data / JOB_LOG_DB_FILENAME,
        outputs_dir=app_data / "outputs",
        uploads_dir=app_data / "uploads",
        runtime_metadata_path=app_data / SHADOW_RUNTIME_METADATA_FILENAME,
    )


def _outputs_dir_for_settings_path(settings_path: Path, *, fallback_name: str) -> Path:
    gui_settings = load_gui_settings_from_path(settings_path)
    preferred = str(gui_settings.get("default_outdir", "") or "").strip()
    if preferred:
        return Path(preferred).expanduser().resolve()
    return app_data_dir_from_settings_path(settings_path) / fallback_name


def detect_browser_data_paths(
    *,
    mode: str,
    repo: Path | None = None,
    identity: RuntimeBuildIdentity | None = None,
    appdata_root: Path | None = None,
) -> BrowserDataPaths:
    normalized_mode = normalize_runtime_mode(mode)
    if normalized_mode == RUNTIME_MODE_LIVE:
        settings_file = live_settings_path().expanduser().resolve()
        app_data = app_data_dir_from_settings_path(settings_file)
        return BrowserDataPaths(
            mode=RUNTIME_MODE_LIVE,
            label="Live App Data",
            app_data_dir=app_data,
            settings_path=settings_file,
            job_log_db_path=settings_file.with_name(JOB_LOG_DB_FILENAME),
            outputs_dir=_outputs_dir_for_settings_path(settings_file, fallback_name="browser_outputs"),
            live_data=True,
            banner_text="LIVE APP DATA: this browser workspace is using your real settings, Gmail bridge, and job log.",
        )

    shadow_paths = detect_shadow_runtime_paths(repo=repo, identity=identity, appdata_root=appdata_root)
    return BrowserDataPaths(
        mode=RUNTIME_MODE_SHADOW,
        label="Isolated Test Data",
        app_data_dir=shadow_paths.app_data_dir,
        settings_path=shadow_paths.settings_path,
        job_log_db_path=shadow_paths.job_log_db_path,
        outputs_dir=shadow_paths.outputs_dir,
        live_data=False,
        banner_text="",
    )


def classify_shadow_listener(
    *,
    port: int = SHADOW_DEFAULT_PORT,
    expected_pid: int | None = None,
) -> ShadowListenerOwnership:
    owner_pid = detect_listener_pid(port)
    if owner_pid is None:
        return ShadowListenerOwnership(
            host=SHADOW_HOST,
            port=int(port),
            status="available",
            pid=None,
            reason="no_listener",
        )
    if expected_pid is not None and int(owner_pid) == int(expected_pid):
        return ShadowListenerOwnership(
            host=SHADOW_HOST,
            port=int(port),
            status="owned_by_self",
            pid=int(owner_pid),
            reason="listener_owned_by_current_process",
        )
    return ShadowListenerOwnership(
        host=SHADOW_HOST,
        port=int(port),
        status="unavailable",
        pid=int(owner_pid),
        reason="listener_owned_by_other_process",
    )


def load_shadow_runtime_metadata(path: Path) -> dict[str, Any] | None:
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


def write_shadow_runtime_metadata(path: Path, payload: dict[str, Any]) -> Path:
    resolved = path.expanduser().resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temp_path = resolved.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(resolved)
    return resolved


def clear_shadow_runtime_metadata(path: Path) -> None:
    resolved = path.expanduser().resolve()
    try:
        resolved.unlink()
    except FileNotFoundError:
        return


def _automation_preflight_error_payload(
    *,
    error: str,
    command: list[str] | tuple[str, ...] | None = None,
    raw_output: str = "",
    launcher_failure: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "automation_host_selected": "local",
        "preferred_host_status": "unavailable",
        "fallback_host_status": "n/a",
        "failure_semantics": dict(_AUTOMATION_FAILURE_SEMANTICS),
        "toolchain": {
            "playwright_available": False,
        },
        "error": str(error or "automation preflight failed").strip(),
    }
    if command:
        payload["command"] = list(command)
    if raw_output.strip():
        payload["raw_output"] = raw_output.strip()
    if launcher_failure.strip():
        payload["launcher_failure"] = launcher_failure.strip()
    return payload


def _resolve_dart_bin() -> str | None:
    override = str(os.environ.get("LEGALPDF_DART_BIN", "") or "").strip()
    if override:
        override_path = Path(override).expanduser()
        if override_path.exists():
            return str(override_path.resolve())
        discovered_override = shutil.which(override)
        if discovered_override:
            return discovered_override
    discovered = shutil.which("dart")
    if discovered:
        return discovered
    return None


def _run_automation_preflight_command(
    *,
    command: list[str],
    repo_root: Path,
) -> tuple[subprocess.CompletedProcess[str] | None, dict[str, Any] | None]:
    try:
        completed = subprocess.run(
            command,
            cwd=repo_root,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return None, _automation_preflight_error_payload(
            error=f"automation preflight launch failed: {exc}",
            command=command,
        )
    return completed, None


def _parse_automation_preflight_payload(
    *,
    completed: subprocess.CompletedProcess[str],
    command: list[str],
) -> dict[str, Any] | None:
    stdout = str(completed.stdout or "").strip()
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        raise ValueError("automation preflight returned invalid JSON") from None
    if not isinstance(payload, dict):
        raise TypeError("automation preflight returned a non-object payload")
    payload.setdefault("automation_host_selected", "local")
    payload.setdefault("failure_semantics", dict(_AUTOMATION_FAILURE_SEMANTICS))
    payload.setdefault("toolchain", {})
    payload["command"] = list(command)
    return payload


def _looks_like_dartdev_launcher_failure(*parts: str) -> bool:
    combined = "\n".join(str(part or "") for part in parts).strip()
    if not combined:
        return False
    return any(marker.casefold() in combined.casefold() for marker in _DARTDEV_AOT_MARKERS)


def run_browser_automation_preflight(*, repo: Path | None = None) -> dict[str, Any]:
    repo_root = (repo or Path(__file__).resolve().parents[2]).expanduser().resolve()
    dart_bin = _resolve_dart_bin()
    if dart_bin is None:
        return _automation_preflight_error_payload(
            error="automation preflight launch failed: Dart is unavailable.",
        )

    direct_command = [dart_bin, "tooling/automation_preflight.dart"]
    direct_completed, direct_error = _run_automation_preflight_command(
        command=direct_command,
        repo_root=repo_root,
    )
    if direct_error is not None:
        return direct_error
    assert direct_completed is not None
    try:
        direct_payload = _parse_automation_preflight_payload(
            completed=direct_completed,
            command=direct_command,
        )
    except (TypeError, ValueError) as exc:
        return _automation_preflight_error_payload(
            error=str(exc),
            command=direct_command,
            raw_output=str(direct_completed.stdout or "").strip(),
        )
    if direct_payload is not None:
        direct_payload.setdefault("launcher_mode", "direct")
        return direct_payload

    fallback_command = [dart_bin, "run", "tooling/automation_preflight.dart"]
    fallback_completed, fallback_error = _run_automation_preflight_command(
        command=fallback_command,
        repo_root=repo_root,
    )
    if fallback_error is not None:
        return _automation_preflight_error_payload(
            error=str(fallback_error.get("error") or "automation preflight failed"),
            command=direct_command,
            launcher_failure=str(fallback_error.get("error") or ""),
        )
    assert fallback_completed is not None
    fallback_stdout = str(fallback_completed.stdout or "").strip()
    fallback_stderr = str(fallback_completed.stderr or "").strip()
    if _looks_like_dartdev_launcher_failure(fallback_stdout, fallback_stderr):
        retry_completed, retry_error = _run_automation_preflight_command(
            command=direct_command,
            repo_root=repo_root,
        )
        if retry_error is None and retry_completed is not None:
            try:
                retry_payload = _parse_automation_preflight_payload(
                    completed=retry_completed,
                    command=direct_command,
                )
            except (TypeError, ValueError) as exc:
                return _automation_preflight_error_payload(
                    error=str(exc),
                    command=direct_command,
                    raw_output=str(retry_completed.stdout or "").strip(),
                    launcher_failure=fallback_stderr or fallback_stdout,
                )
            if retry_payload is not None:
                retry_payload["launcher_mode"] = "direct"
                retry_payload["launcher_failure"] = fallback_stderr or fallback_stdout
                return retry_payload
        return _automation_preflight_error_payload(
            error="automation preflight launcher failed, but direct Dart script execution is the supported fallback.",
            command=direct_command,
            raw_output=str(retry_completed.stdout or "").strip() if retry_completed is not None else "",
            launcher_failure=fallback_stderr or fallback_stdout,
        )

    try:
        fallback_payload = _parse_automation_preflight_payload(
            completed=fallback_completed,
            command=fallback_command,
        )
    except (TypeError, ValueError) as exc:
        return _automation_preflight_error_payload(
            error=str(exc),
            command=fallback_command,
            raw_output=fallback_stdout,
        )
    if fallback_payload is not None:
        fallback_payload.setdefault("launcher_mode", "run")
        return fallback_payload

    return _automation_preflight_error_payload(
        error=str(fallback_stderr or fallback_stdout or "automation preflight failed").strip(),
        command=direct_command,
        launcher_failure=fallback_stderr or fallback_stdout,
    )


def runtime_build_identity_payload(identity: RuntimeBuildIdentity) -> dict[str, Any]:
    return asdict(identity)


def build_shadow_runtime_metadata(
    *,
    repo: Path | None = None,
    identity: RuntimeBuildIdentity | None = None,
    port: int = SHADOW_DEFAULT_PORT,
    listener: ShadowListenerOwnership | None = None,
    automation_preflight: dict[str, Any] | None = None,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_identity = identity or detect_runtime_build_identity(repo=repo, labels=("shadow-web",))
    resolved_listener = listener or classify_shadow_listener(port=port)
    return {
        "host": SHADOW_HOST,
        "port": int(port),
        "pid": int(os.getpid()),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "build_identity": runtime_build_identity_payload(resolved_identity),
        "listener_ownership": asdict(resolved_listener),
        "automation_preflight": automation_preflight or run_browser_automation_preflight(repo=repo),
        "capabilities": capabilities or {},
    }
