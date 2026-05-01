"""Edge native-messaging host for Gmail intake foreground activation."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import struct
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, BinaryIO

from legalpdf_translate.build_identity import (
    detect_runtime_build_identity,
    try_load_canonical_build_config,
)
from legalpdf_translate.gmail_focus import focus_bridge_owner, validate_bridge_owner
from legalpdf_translate.gmail_window_trace import (
    build_launch_session_id,
    consume_armed_window_trace,
    latest_window_trace_status,
    resolve_runtime_state_root,
    update_launch_session_state,
)


EDGE_NATIVE_HOST_NAME = "com.legalpdf.gmail_focus"
EDGE_EXTENSION_ID = "afckgbhjkmojchdlinolkepffchlgpin"
EDGE_EXTENSION_ORIGIN = f"chrome-extension://{EDGE_EXTENSION_ID}/"
_MAX_NATIVE_MESSAGE_BYTES = 1024 * 1024
_EDGE_NATIVE_HOST_REGISTRY_SUBKEY = rf"Software\Microsoft\Edge\NativeMessagingHosts\{EDGE_NATIVE_HOST_NAME}"
EDGE_NATIVE_HOST_REGISTRY_KEY_PATH = rf"HKCU\{_EDGE_NATIVE_HOST_REGISTRY_SUBKEY}"
_EDGE_NATIVE_HOST_EXE = "LegalPDFGmailFocusHost.exe"
_EDGE_NATIVE_HOST_WRAPPER = "LegalPDFGmailFocusHost.cmd"
_AUTO_LAUNCH_WAIT_SECONDS = 35.0
_AUTO_LAUNCH_POLL_INTERVAL_SECONDS = 0.25
_AUTO_LAUNCH_LOCK_SECONDS = _AUTO_LAUNCH_WAIT_SECONDS + 5.0
_AUTO_LAUNCH_LABELS = ("gmail-intake", "auto-launch")
_AUTO_LAUNCHABLE_BRIDGE_REASONS = {"runtime_metadata_missing", "bridge_not_running", "bridge_owner_stale"}
_AUTO_LAUNCH_IN_PROGRESS_REASON = "launch_in_progress"
_BROWSER_SERVER_READY_REASON = "browser_server_ready"
_AUTO_LAUNCH_LOCK_FILENAME = "gmail_browser_launch.lock.json"
_BROWSER_OPEN_OWNER_EXTENSION = "extension"
_BROWSER_OPEN_OWNER_SERVER_BOOT = "server_boot"
_BROWSER_OPEN_OWNER_NATIVE_HOST = "native_host"
_BROWSER_OPEN_OWNER_RUNTIME = "runtime"
_WSL_MNT_RE = re.compile(r"^/mnt/([A-Za-z])/(.*)$")
_BROWSER_GMAIL_WORKSPACE_ID = "gmail-intake"
_SELF_TEST_TIMEOUT_SECONDS = 15.0
_APP_FOLDER_NAME = "LegalPDFTranslate"
_SETTINGS_FILENAME = "settings.json"
SHADOW_DEFAULT_PORT = 8877
_EDGE_NATIVE_HOST_LAUNCHER_SOURCE = Path("tooling") / "native_host_launcher" / "LegalPDFGmailFocusHostLauncher.cs"
_EDGE_NATIVE_HOST_BUILD_DIR = Path("dist") / "legalpdf_translate"


@dataclass(frozen=True, slots=True)
class NativeHostRegistrationResult:
    ok: bool
    changed: bool
    manifest_path: str | None
    executable_path: str | None
    reason: str


@dataclass(frozen=True, slots=True)
class EdgeUnpackedExtensionRecord:
    profile_name: str
    extension_id: str
    path: str
    disable_reasons: tuple[int, ...]
    enabled: bool


@dataclass(frozen=True, slots=True)
class AutoLaunchTarget:
    ready: bool
    worktree_path: str | None
    python_executable: str | None
    launcher_script: str | None
    reason: str
    ui_owner: str = "qt_app"
    browser_url: str | None = None
    launch_args: tuple[str, ...] = ()


def _is_windows() -> bool:
    return os.name == "nt"


def _is_truthy_env(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def settings_path() -> Path:
    appdata = str(os.environ.get("APPDATA", "") or "").strip()
    if appdata:
        root = Path(appdata).expanduser().resolve()
    else:
        root = (Path.home() / ".legalpdf_translate").expanduser().resolve()
    return root / _APP_FOLDER_NAME / _SETTINGS_FILENAME


def app_data_dir() -> Path:
    return settings_path().parent


def load_settings_from_path(path: Path) -> dict[str, object]:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        return {}
    try:
        payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def load_gui_settings() -> dict[str, object]:
    return load_settings_from_path(settings_path())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _coerce_repo_path(path_text: str | Path) -> Path:
    text = str(path_text).strip()
    match = _WSL_MNT_RE.match(text)
    if match:
        drive = match.group(1).upper()
        tail = match.group(2).replace("/", "\\")
        return Path(f"{drive}:\\{tail}")
    return Path(text).expanduser()


def _absolute_path_noresolve(path: Path) -> Path:
    # Preserve Windows venv launcher identities. Path.resolve() can collapse
    # a venv python.exe back to the base interpreter, which breaks runtime
    # selection and wrapper generation for cold-start launch paths.
    return Path(os.path.abspath(str(path.expanduser())))


def _looks_like_repo_worktree(path: Path) -> bool:
    candidate = path.expanduser().resolve()
    return (
        (candidate / "tooling" / "launch_qt_build.py").exists()
        and (candidate / "src" / "legalpdf_translate" / "qt_app.py").exists()
    )


def _python_executable_for_worktree(worktree: Path) -> Path | None:
    python_executable, _reason = _validated_python_executable_for_worktree(worktree)
    return python_executable


def _python_runtime_variants(candidate: Path, *, prefer_windowless: bool) -> tuple[Path, ...]:
    resolved = _absolute_path_noresolve(candidate)
    lowered_name = resolved.name.casefold()
    if lowered_name not in {"python.exe", "pythonw.exe"}:
        return (resolved,)
    python_console = resolved.with_name("python.exe")
    python_windowless = resolved.with_name("pythonw.exe")
    ordered = (
        (python_windowless, python_console)
        if prefer_windowless
        else (python_console, python_windowless)
    )
    seen: set[Path] = set()
    variants: list[Path] = []
    for item in ordered:
        normalized = _absolute_path_noresolve(item)
        if normalized in seen:
            continue
        seen.add(normalized)
        variants.append(normalized)
    return tuple(variants)


def _candidate_python_executables_for_worktree(
    worktree: Path,
    *,
    preferred_python_executable: Path | None = None,
    ui_owner: str = "qt_app",
) -> tuple[Path, ...]:
    resolved_worktree = worktree.expanduser().resolve()
    roots: list[Path] = [resolved_worktree]
    config = try_load_canonical_build_config(resolved_worktree)
    if config is not None:
        canonical_root = _coerce_repo_path(config.canonical_worktree_path).resolve()
        if canonical_root not in roots:
            roots.append(canonical_root)
    candidates: list[Path] = []
    # Browser/server helpers are launched with CREATE_NO_WINDOW, so python.exe
    # gives reliable stdio/startup without flashing a console window. pythonw.exe
    # remains a fallback only; it can silently fail to bind the localhost server
    # in this native-host launch path.
    prefer_windowless = False

    def _append(candidate: Path | None) -> None:
        if candidate is None:
            return
        for resolved in _python_runtime_variants(candidate, prefer_windowless=prefer_windowless):
            if resolved in candidates:
                continue
            candidates.append(resolved)

    _append(preferred_python_executable)
    if not getattr(sys, "frozen", False):
        _append(Path(sys.executable))
    for root in roots:
        _append(root / ".venv311" / "Scripts" / "python.exe")
        _append(root / ".venv" / "Scripts" / "python.exe")
    return tuple(candidates)


def _build_runtime_probe_env(repo_root: Path) -> dict[str, str]:
    resolved_repo = repo_root.expanduser().resolve()
    resolved_src = (resolved_repo / "src").resolve()
    env = os.environ.copy()
    existing_pythonpath = str(env.get("PYTHONPATH", "") or "").strip()
    env["PYTHONPATH"] = (
        f"{resolved_src}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(resolved_src)
    )
    return env


def _fresh_extension_handoff_state() -> dict[str, object]:
    return {
        "click_phase": "",
        "click_failure_reason": "",
        "source_gmail_url": "",
        "tab_resolution_strategy": "",
        "workspace_surface_confirmed": False,
        "client_hydration_status": "",
        "extension_surface_outcome": "",
        "extension_surface_reason": "",
        "extension_surface_tab_id": 0,
        "surface_candidate_source": "",
        "surface_candidate_valid": False,
        "surface_invalidation_reason": "",
        "fresh_tab_created_after_invalidation": False,
        "bridge_context_posted": False,
        "surface_visibility_status": "",
        "runtime_state_root_compatible": True,
        "expected_runtime_state_root": "",
        "observed_runtime_state_root": "",
    }


def _run_python_runtime_probe(
    python_executable: Path,
    *,
    repo_root: Path,
    args: list[str],
) -> bool:
    run_kwargs: dict[str, object] = {
        "cwd": str(repo_root),
        "env": _build_runtime_probe_env(repo_root),
        "capture_output": True,
        "text": True,
        "timeout": _SELF_TEST_TIMEOUT_SECONDS,
        "check": False,
    }
    if _is_windows():
        run_kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        completed = subprocess.run(
            [str(python_executable), *args],
            **run_kwargs,
        )
    except Exception:
        return False
    return completed.returncode == 0


def _windows_no_window_creationflags() -> int:
    if not _is_windows():
        return 0
    return int(getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _python_runtime_supports_native_host(python_executable: Path, *, repo_root: Path) -> bool:
    return _run_python_runtime_probe(
        python_executable,
        repo_root=repo_root,
        args=["-m", "legalpdf_translate.gmail_focus_host", "--self-test"],
    )


def _python_runtime_supports_browser_runtime(python_executable: Path, *, repo_root: Path) -> bool:
    return _run_python_runtime_probe(
        python_executable,
        repo_root=repo_root,
        args=["-m", "legalpdf_translate.shadow_web.server", "--help"],
    )


def _looks_like_pytest_or_temp_runtime_path(path: Path) -> bool:
    absolute_path = _absolute_path_noresolve(path)
    try:
        resolved_path = path.expanduser().resolve()
    except Exception:  # noqa: BLE001
        resolved_path = absolute_path

    def _has_pytest_markers(candidate: Path) -> bool:
        lowered_parts = [part.lower() for part in candidate.parts]
        return any(
            part.startswith("pytest-")
            or part.startswith("pytest_of")
            or part.startswith("pytest-of-")
            for part in lowered_parts
        )

    if _has_pytest_markers(absolute_path) or _has_pytest_markers(resolved_path):
        return True

    temp_root = Path(tempfile.gettempdir()).expanduser().resolve()
    for candidate in (absolute_path, resolved_path):
        try:
            candidate.relative_to(temp_root)
        except Exception:  # noqa: BLE001
            continue
        return True
    return False


def _validated_python_executable_for_worktree(
    worktree: Path,
    *,
    preferred_python_executable: Path | None = None,
    ui_owner: str = "qt_app",
) -> tuple[Path | None, str]:
    repo_root = worktree.expanduser().resolve()
    saw_candidate = False
    candidates = _candidate_python_executables_for_worktree(
        repo_root,
        preferred_python_executable=preferred_python_executable,
        ui_owner=ui_owner,
    )
    for candidate in candidates:
        resolved = _absolute_path_noresolve(candidate)
        if not resolved.exists():
            continue
        if _looks_like_pytest_or_temp_runtime_path(resolved):
            continue
        saw_candidate = True
        if not _python_runtime_supports_native_host(resolved, repo_root=repo_root):
            continue
        if not _python_runtime_supports_browser_runtime(resolved, repo_root=repo_root):
            continue
        return resolved, "launch_target_ready"
    if saw_candidate:
        return None, "launch_runtime_broken"
    return None, "launch_python_missing"


def _self_test_payload() -> dict[str, object]:
    repo_root = _preferred_repo_worktree_for_auto_launch(runtime_path=Path(sys.executable))
    return {
        "ok": True,
        "reason": "native_host_self_test_ok",
        "python_executable": str(_absolute_path_noresolve(Path(sys.executable))),
        "repo_root": str(repo_root) if repo_root is not None else "",
    }


def _resolve_repo_worktree_for_auto_launch(*, runtime_path: Path | None = None) -> Path | None:
    if runtime_path is None:
        if getattr(sys, "frozen", False):
            runtime_path = Path(sys.executable).resolve()
        else:
            runtime_path = _repo_root()
    start = _absolute_path_noresolve(runtime_path)
    search_root = start if start.is_dir() else start.parent
    for candidate in (search_root, *search_root.parents):
        if _looks_like_repo_worktree(candidate):
            return candidate
    return None


def _preferred_repo_worktree_for_auto_launch(*, runtime_path: Path | None = None) -> Path | None:
    worktree = _resolve_repo_worktree_for_auto_launch(runtime_path=runtime_path)
    if worktree is None:
        return None
    config = try_load_canonical_build_config(worktree)
    if config is None:
        return worktree
    canonical_root = _coerce_repo_path(config.canonical_worktree_path).resolve()
    if canonical_root != worktree and _looks_like_repo_worktree(canonical_root):
        return canonical_root
    return worktree


def _runtime_build_identity_for_registration(
    *,
    runtime_path: Path | None = None,
) -> RuntimeBuildIdentity | None:
    worktree = _resolve_repo_worktree_for_auto_launch(runtime_path=runtime_path)
    if worktree is None:
        return None
    try:
        return detect_runtime_build_identity(repo=worktree, labels=("shadow-web",))
    except Exception:  # noqa: BLE001
        return None


def _browser_gmail_workspace_url(*, port: int = SHADOW_DEFAULT_PORT) -> str:
    return f"http://127.0.0.1:{int(port)}/?mode=live&workspace={_BROWSER_GMAIL_WORKSPACE_ID}#gmail-intake"


def _browser_workspace_url(
    *,
    runtime_mode: str = "live",
    workspace_id: str = _BROWSER_GMAIL_WORKSPACE_ID,
    fragment: str = "gmail-intake",
    port: int = SHADOW_DEFAULT_PORT,
) -> str:
    cleaned_mode = str(runtime_mode or "live").strip() or "live"
    cleaned_workspace = str(workspace_id or _BROWSER_GMAIL_WORKSPACE_ID).strip() or _BROWSER_GMAIL_WORKSPACE_ID
    cleaned_fragment = str(fragment or "gmail-intake").strip() or "gmail-intake"
    return f"http://127.0.0.1:{int(port)}/?mode={cleaned_mode}&workspace={cleaned_workspace}#{cleaned_fragment}"


def _browser_shell_ready_url(
    *,
    runtime_mode: str = "live",
    workspace_id: str = _BROWSER_GMAIL_WORKSPACE_ID,
    port: int = SHADOW_DEFAULT_PORT,
) -> str:
    cleaned_mode = str(runtime_mode or "live").strip() or "live"
    cleaned_workspace = str(workspace_id or _BROWSER_GMAIL_WORKSPACE_ID).strip() or _BROWSER_GMAIL_WORKSPACE_ID
    return (
        f"http://127.0.0.1:{int(port)}/api/bootstrap/shell/ready"
        f"?mode={cleaned_mode}&workspace={cleaned_workspace}"
    )


def _browser_runtime_identity_from_url(browser_url: str) -> tuple[str, str, int]:
    target_url = str(browser_url or "").strip()
    if target_url == "":
        return ("live", _BROWSER_GMAIL_WORKSPACE_ID, SHADOW_DEFAULT_PORT)
    try:
        parsed = urllib.parse.urlsplit(target_url)
    except Exception:  # noqa: BLE001
        return ("live", _BROWSER_GMAIL_WORKSPACE_ID, SHADOW_DEFAULT_PORT)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
    runtime_mode = str((query.get("mode") or ["live"])[0] or "").strip() or "live"
    workspace_id = str((query.get("workspace") or [_BROWSER_GMAIL_WORKSPACE_ID])[0] or "").strip() or _BROWSER_GMAIL_WORKSPACE_ID
    port = int(parsed.port or SHADOW_DEFAULT_PORT)
    return (runtime_mode, workspace_id, port)


def _probe_browser_shell_ready(browser_url: str) -> bool:
    runtime_mode, workspace_id, port = _browser_runtime_identity_from_url(browser_url)
    shell_ready_url = _browser_shell_ready_url(
        runtime_mode=runtime_mode,
        workspace_id=workspace_id,
        port=port,
    )
    try:
        with urllib.request.urlopen(shell_ready_url, timeout=2.0) as response:
            status = int(getattr(response, "status", 0))
            return 200 <= status < 300
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _resolve_qt_auto_launch_target(*, runtime_path: Path | None = None) -> AutoLaunchTarget:
    worktree = _preferred_repo_worktree_for_auto_launch(runtime_path=runtime_path)
    if worktree is None:
        return AutoLaunchTarget(
            ready=False,
            worktree_path=None,
            python_executable=None,
            launcher_script=None,
            reason="launch_target_missing",
            ui_owner="qt_app",
        )

    launcher_script = (worktree / "tooling" / "launch_qt_build.py").expanduser().resolve()
    if not launcher_script.exists():
        return AutoLaunchTarget(
            ready=False,
            worktree_path=str(worktree),
            python_executable=None,
            launcher_script=None,
            reason="launch_helper_missing",
            ui_owner="qt_app",
        )

    python_executable, runtime_reason = _validated_python_executable_for_worktree(
        worktree,
        preferred_python_executable=runtime_path if runtime_path and runtime_path.is_file() else None,
        ui_owner="qt_app",
    )
    if python_executable is None:
        return AutoLaunchTarget(
            ready=False,
            worktree_path=str(worktree),
            python_executable=None,
            launcher_script=str(launcher_script),
            reason=runtime_reason,
            ui_owner="qt_app",
        )

    return AutoLaunchTarget(
        ready=True,
        worktree_path=str(worktree),
        python_executable=str(python_executable),
        launcher_script=str(launcher_script),
        reason="launch_target_ready",
        ui_owner="qt_app",
    )


def _resolve_browser_auto_launch_target(*, runtime_path: Path | None = None) -> AutoLaunchTarget:
    worktree = _preferred_repo_worktree_for_auto_launch(runtime_path=runtime_path)
    if worktree is None:
        return AutoLaunchTarget(
            ready=False,
            worktree_path=None,
            python_executable=None,
            launcher_script=None,
            reason="launch_target_missing",
            ui_owner="browser_app",
            browser_url=_browser_gmail_workspace_url(),
        )

    launcher_script = (worktree / "tooling" / "launch_browser_app_live_detached.py").expanduser().resolve()
    if not launcher_script.exists():
        return AutoLaunchTarget(
            ready=False,
            worktree_path=str(worktree),
            python_executable=None,
            launcher_script=None,
            reason="launch_helper_missing",
            ui_owner="browser_app",
            browser_url=_browser_gmail_workspace_url(),
        )

    python_executable, runtime_reason = _validated_python_executable_for_worktree(
        worktree,
        preferred_python_executable=runtime_path if runtime_path and runtime_path.is_file() else None,
        ui_owner="browser_app",
    )
    if python_executable is None:
        return AutoLaunchTarget(
            ready=False,
            worktree_path=str(worktree),
            python_executable=None,
            launcher_script=None,
            reason=runtime_reason,
            ui_owner="browser_app",
            browser_url=_browser_gmail_workspace_url(),
        )

    return AutoLaunchTarget(
        ready=True,
        worktree_path=str(worktree),
        python_executable=str(python_executable),
        launcher_script=None,
        reason="launch_target_ready",
        ui_owner="browser_app",
        browser_url=_browser_gmail_workspace_url(),
        launch_args=(
            str(launcher_script),
            "--mode",
            "live",
            "--workspace",
            _BROWSER_GMAIL_WORKSPACE_ID,
            "--no-open",
        ),
    )


def _resolve_auto_launch_target(*, runtime_path: Path | None = None) -> AutoLaunchTarget:
    browser_target = _resolve_browser_auto_launch_target(runtime_path=runtime_path)
    if browser_target.ready:
        return browser_target
    qt_target = _resolve_qt_auto_launch_target(runtime_path=runtime_path)
    if qt_target.ready:
        return qt_target
    return browser_target


def _apply_validation_context(
    response: dict[str, object],
    *,
    validation: Any,
    fallback_browser_url: str | None = None,
) -> None:
    owner_kind = str(getattr(validation, "owner_kind", "") or "").strip() or "none"
    if owner_kind == "none" and bool(getattr(validation, "ok", False)):
        owner_kind = "qt_app"
    response["ui_owner"] = owner_kind
    if owner_kind == "browser_app":
        response["browser_url"] = str(
            getattr(validation, "browser_url", "") or fallback_browser_url or ""
        ).strip()
        response["workspace_id"] = str(
            getattr(validation, "workspace_id", "") or _BROWSER_GMAIL_WORKSPACE_ID
        ).strip() or _BROWSER_GMAIL_WORKSPACE_ID
        response["runtime_mode"] = str(getattr(validation, "runtime_mode", "") or "live").strip() or "live"
        response["browser_open_owned_by"] = _BROWSER_OPEN_OWNER_EXTENSION
    elif fallback_browser_url:
        response["browser_url"] = fallback_browser_url


def _apply_browser_launch_ready_context(
    response: dict[str, object],
    *,
    browser_url: str,
    launch_session_id: str,
    handoff_session_id: str = "",
    browser_open_owned_by: str,
    launch_lock_ttl_ms: int | None = None,
    reason: str = _BROWSER_SERVER_READY_REASON,
) -> None:
    response["ok"] = True
    response["reason"] = str(reason or _BROWSER_SERVER_READY_REASON).strip() or _BROWSER_SERVER_READY_REASON
    response["ui_owner"] = "browser_app"
    response["browser_url"] = str(browser_url or _browser_gmail_workspace_url()).strip()
    response["browser_open_owned_by"] = str(browser_open_owned_by or _BROWSER_OPEN_OWNER_EXTENSION).strip() or _BROWSER_OPEN_OWNER_EXTENSION
    response["workspace_id"] = _BROWSER_GMAIL_WORKSPACE_ID
    response["runtime_mode"] = "live"
    response["launch_phase"] = "server_boot_ready" if response["browser_open_owned_by"] == _BROWSER_OPEN_OWNER_EXTENSION else "server_boot"
    if str(launch_session_id or "").strip():
        response["launch_session_id"] = str(launch_session_id).strip()
    if str(handoff_session_id or "").strip():
        response["handoff_session_id"] = str(handoff_session_id).strip()
    if isinstance(launch_lock_ttl_ms, int) and launch_lock_ttl_ms > 0:
        response["launch_lock_ttl_ms"] = int(launch_lock_ttl_ms)


def _browser_auto_launch_lock_path(base_dir: Path) -> Path:
    return base_dir / "native_messaging" / _AUTO_LAUNCH_LOCK_FILENAME


def _clear_browser_auto_launch_lock(base_dir: Path) -> None:
    lock_path = _browser_auto_launch_lock_path(base_dir).expanduser().resolve()
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _coerce_int(value: object) -> int | None:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _pid_is_running(pid: int | None) -> bool:
    parsed = _coerce_int(pid)
    if parsed is None:
        return False
    try:
        os.kill(parsed, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, SystemError):
        return False
    return True


def _read_browser_auto_launch_lock(base_dir: Path) -> dict[str, object] | None:
    lock_path = _browser_auto_launch_lock_path(base_dir).expanduser().resolve()
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        _clear_browser_auto_launch_lock(base_dir)
        return None
    if not isinstance(payload, dict):
        _clear_browser_auto_launch_lock(base_dir)
        return None
    expires_at = float(payload.get("expires_at_epoch_seconds", 0) or 0)
    remaining_ms = max(0, int((expires_at - time.time()) * 1000))
    if remaining_ms <= 0:
        _clear_browser_auto_launch_lock(base_dir)
        return None
    payload["remaining_ms"] = remaining_ms
    return payload


def _write_browser_auto_launch_lock(
    base_dir: Path,
    target: AutoLaunchTarget,
    *,
    launch_session_id: str,
    browser_open_owned_by: str = _BROWSER_OPEN_OWNER_SERVER_BOOT,
    ttl_seconds: float = _AUTO_LAUNCH_LOCK_SECONDS,
) -> dict[str, object]:
    lock_path = _browser_auto_launch_lock_path(base_dir).expanduser().resolve()
    expires_at = time.time() + max(1.0, float(ttl_seconds or _AUTO_LAUNCH_LOCK_SECONDS))
    payload: dict[str, object] = {
        "created_at_epoch_seconds": time.time(),
        "expires_at_epoch_seconds": expires_at,
        "launch_session_id": str(launch_session_id or "").strip(),
        "ui_owner": target.ui_owner,
        "browser_url": str(target.browser_url or "").strip(),
        "workspace_id": _BROWSER_GMAIL_WORKSPACE_ID,
        "runtime_mode": "live",
        "browser_open_owned_by": str(browser_open_owned_by or _BROWSER_OPEN_OWNER_SERVER_BOOT).strip() or _BROWSER_OPEN_OWNER_SERVER_BOOT,
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = lock_path.with_suffix(".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp_path.replace(lock_path)
    payload["remaining_ms"] = max(0, int((expires_at - time.time()) * 1000))
    return payload


def _apply_browser_auto_launch_lock_context(
    response: dict[str, object],
    *,
    lock_payload: dict[str, object],
    fallback_browser_url: str | None = None,
) -> None:
    response["launch_in_progress"] = True
    response["launch_lock_ttl_ms"] = max(0, int(lock_payload.get("remaining_ms", 0) or 0))
    launch_session_id = str(lock_payload.get("launch_session_id", "") or "").strip()
    if launch_session_id != "":
        response["launch_session_id"] = launch_session_id
    response["ui_owner"] = str(lock_payload.get("ui_owner", "") or "browser_app").strip() or "browser_app"
    response["browser_url"] = str(
        lock_payload.get("browser_url", "") or fallback_browser_url or ""
    ).strip()
    response["workspace_id"] = str(
        lock_payload.get("workspace_id", "") or _BROWSER_GMAIL_WORKSPACE_ID
    ).strip() or _BROWSER_GMAIL_WORKSPACE_ID
    response["runtime_mode"] = str(lock_payload.get("runtime_mode", "") or "live").strip() or "live"
    response["browser_open_owned_by"] = str(
        lock_payload.get("browser_open_owned_by", "") or _BROWSER_OPEN_OWNER_SERVER_BOOT
    ).strip() or _BROWSER_OPEN_OWNER_SERVER_BOOT


def _terminate_process_tree(pid: int | None) -> bool:
    parsed = _coerce_int(pid)
    if parsed is None:
        return True
    if not _pid_is_running(parsed):
        return True
    if _is_windows():
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(parsed), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except Exception:
            return False
        return completed.returncode == 0 or not _pid_is_running(parsed)
    try:
        os.kill(parsed, 15)
    except ProcessLookupError:
        return True
    except OSError:
        return False
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if not _pid_is_running(parsed):
            return True
        time.sleep(0.1)
    return not _pid_is_running(parsed)


def _resolve_canonical_browser_restart_target(
    *,
    runtime_path: Path | None = None,
) -> tuple[AutoLaunchTarget | None, dict[str, object]]:
    target = _resolve_browser_auto_launch_target(runtime_path=runtime_path)
    if not target.ready:
        return None, {
            "ok": False,
            "reason": str(target.reason or "launch_target_missing").strip() or "launch_target_missing",
            "launch_target": str(target.worktree_path or "").strip(),
            "browser_url": str(target.browser_url or _browser_gmail_workspace_url()).strip(),
        }
    if not target.worktree_path or not target.python_executable:
        return None, {
            "ok": False,
            "reason": "canonical_target_missing_runtime",
            "launch_target": str(target.worktree_path or "").strip(),
            "browser_url": str(target.browser_url or _browser_gmail_workspace_url()).strip(),
        }
    try:
        identity = detect_runtime_build_identity(
            repo=Path(target.worktree_path).expanduser().resolve(),
            labels=("shadow-web",),
        )
    except Exception as exc:  # noqa: BLE001
        return None, {
            "ok": False,
            "reason": "canonical_target_identity_failed",
            "error": str(exc) or "Failed to inspect canonical target build identity.",
            "launch_target": str(target.worktree_path or "").strip(),
            "browser_url": str(target.browser_url or _browser_gmail_workspace_url()).strip(),
        }
    if not identity.is_canonical:
        return None, {
            "ok": False,
            "reason": "canonical_target_not_ready",
            "launch_target": str(target.worktree_path or "").strip(),
            "browser_url": str(target.browser_url or _browser_gmail_workspace_url()).strip(),
            "build_identity": asdict(identity),
        }
    return target, {
        "ok": True,
        "reason": "canonical_target_ready",
        "launch_target": str(target.worktree_path).strip(),
        "target_python": str(target.python_executable).strip(),
        "browser_url": str(target.browser_url or _browser_gmail_workspace_url()).strip(),
        "build_identity": asdict(identity),
    }


def _spawn_detached_helper(
    command: list[str],
    *,
    cwd: str | None = None,
) -> bool:
    try:
        creationflags = 0
        creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        creationflags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
        creationflags |= _windows_no_window_creationflags()
        subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
    except Exception:
        return False
    return True


def _start_window_trace_capture(
    *,
    base_dir: Path,
    launch_session_id: str,
    target: AutoLaunchTarget,
    trace_request: dict[str, object] | None,
) -> str:
    if not trace_request:
        return "not_requested"
    if not target.worktree_path or not target.python_executable:
        return "trace_runtime_unavailable"
    command = [
        str(target.python_executable),
        "-m",
        "legalpdf_translate.gmail_window_trace",
        "--base-dir",
        str(base_dir),
        "--launch-session-id",
        str(launch_session_id or "").strip(),
        "--browser-url",
        str(target.browser_url or "").strip(),
        "--duration-seconds",
        str(float(trace_request.get("duration_seconds", _AUTO_LAUNCH_WAIT_SECONDS) or _AUTO_LAUNCH_WAIT_SECONDS)),
        "--sample-interval-ms",
        str(int(trace_request.get("sample_interval_ms", 200) or 200)),
    ]
    if not _spawn_detached_helper(command, cwd=str(target.worktree_path)):
        return "trace_spawn_failed"
    return "trace_started"


def restart_canonical_browser_runtime(
    *,
    current_listener_pid: int | None = None,
    runtime_mode: str = "live",
    workspace_id: str = _BROWSER_GMAIL_WORKSPACE_ID,
    runtime_path: Path | None = None,
) -> dict[str, object]:
    target, target_payload = _resolve_canonical_browser_restart_target(runtime_path=runtime_path)
    cleaned_runtime_mode = str(runtime_mode or "live").strip() or "live"
    cleaned_workspace_id = str(workspace_id or _BROWSER_GMAIL_WORKSPACE_ID).strip() or _BROWSER_GMAIL_WORKSPACE_ID
    browser_url = _browser_workspace_url(
        runtime_mode=cleaned_runtime_mode,
        workspace_id=cleaned_workspace_id,
        fragment="gmail-intake",
    )
    shell_ready_url = _browser_shell_ready_url(
        runtime_mode=cleaned_runtime_mode,
        workspace_id=cleaned_workspace_id,
    )
    if target is None:
        payload = dict(target_payload)
        payload.setdefault("browser_url", browser_url)
        payload.setdefault("shell_ready_url", shell_ready_url)
        payload["runtime_mode"] = cleaned_runtime_mode
        payload["workspace_id"] = cleaned_workspace_id
        return payload
    helper_command = [
        str(_absolute_path_noresolve(Path(sys.executable))),
        "-m",
        "legalpdf_translate.gmail_focus_host",
        "--restart-browser-runtime-canonical",
        "--target-worktree",
        str(target.worktree_path),
        "--target-python",
        str(target.python_executable),
        "--current-listener-pid",
        str(_coerce_int(current_listener_pid) or 0),
        "--runtime-mode",
        cleaned_runtime_mode,
        "--workspace-id",
        cleaned_workspace_id,
    ]
    if not _spawn_detached_helper(helper_command, cwd=str(target.worktree_path or "")):
        return {
            "ok": False,
            "reason": "canonical_restart_spawn_failed",
            "browser_url": browser_url,
            "shell_ready_url": shell_ready_url,
            "runtime_mode": cleaned_runtime_mode,
            "workspace_id": cleaned_workspace_id,
            "launch_target": str(target.worktree_path or "").strip(),
            "target_python": str(target.python_executable or "").strip(),
            "build_identity": target_payload.get("build_identity"),
        }
    return {
        "ok": True,
        "reason": "canonical_restart_started",
        "browser_url": browser_url,
        "shell_ready_url": shell_ready_url,
        "runtime_mode": cleaned_runtime_mode,
        "workspace_id": cleaned_workspace_id,
        "launch_target": str(target.worktree_path or "").strip(),
        "target_python": str(target.python_executable or "").strip(),
        "build_identity": target_payload.get("build_identity"),
    }


def _run_restart_browser_runtime_canonical(
    *,
    target_worktree: str,
    target_python: str,
    current_listener_pid: int | None,
    runtime_mode: str,
    workspace_id: str,
) -> dict[str, object]:
    time.sleep(0.75)
    if not _terminate_process_tree(current_listener_pid):
        return {
            "ok": False,
            "reason": "canonical_restart_terminate_failed",
            "current_listener_pid": _coerce_int(current_listener_pid),
        }
    target = AutoLaunchTarget(
        ready=True,
        worktree_path=str(target_worktree or "").strip(),
        python_executable=str(target_python or "").strip(),
        launcher_script=None,
        reason="launch_target_ready",
        ui_owner="browser_app",
        browser_url=_browser_workspace_url(
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            fragment="gmail-intake",
        ),
        launch_args=(
            "-m",
            "legalpdf_translate.shadow_web.server",
            "--port",
            str(SHADOW_DEFAULT_PORT),
        ),
    )
    launch_reason = _launch_repo_worktree(target)
    return {
        "ok": launch_reason == "launch_started",
        "reason": launch_reason,
        "launch_target": target.worktree_path,
        "browser_url": target.browser_url,
    }


def _launch_repo_worktree(target: AutoLaunchTarget) -> str:
    if not target.ready or not target.worktree_path or not target.python_executable:
        return target.reason or "launch_target_missing"
    if target.launch_args:
        command = [
            target.python_executable,
            *target.launch_args,
        ]
        try:
            creationflags = 0
            creationflags |= int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
            creationflags |= int(getattr(subprocess, "DETACHED_PROCESS", 0))
            creationflags |= _windows_no_window_creationflags()
            subprocess.Popen(
                command,
                cwd=target.worktree_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except Exception:
            return "launch_command_failed"
        return "launch_started"
    else:
        if not target.launcher_script:
            return target.reason or "launch_target_missing"
        command = [
            target.python_executable,
            target.launcher_script,
            "--worktree",
            target.worktree_path,
            "--allow-noncanonical",
            "--labels",
            ",".join(_AUTO_LAUNCH_LABELS),
        ]
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                cwd=target.worktree_path,
                timeout=20,
            )
        except Exception:
            return "launch_command_failed"
        return "launch_started"


def _wait_for_bridge_owner_after_launch(*, bridge_port: int, base_dir: Path) -> str:
    deadline = time.monotonic() + _AUTO_LAUNCH_WAIT_SECONDS
    while time.monotonic() < deadline:
        validation = validate_bridge_owner(
            bridge_port=bridge_port,
            base_dir=base_dir,
        )
        if validation.ok:
            return "launch_ready"
        if validation.reason in {"invalid_bridge_port", "unsupported_platform"}:
            return validation.reason
        time.sleep(_AUTO_LAUNCH_POLL_INTERVAL_SECONDS)
    return "launch_timeout"


def _wait_for_auto_launch_ready_after_launch(
    *,
    bridge_port: int,
    base_dir: Path,
    target: AutoLaunchTarget,
) -> str:
    deadline = time.monotonic() + _AUTO_LAUNCH_WAIT_SECONDS
    browser_url = str(target.browser_url or "").strip()
    while time.monotonic() < deadline:
        validation = validate_bridge_owner(
            bridge_port=bridge_port,
            base_dir=base_dir,
        )
        if validation.ok:
            return "launch_ready"
        if validation.reason in {"invalid_bridge_port", "unsupported_platform"}:
            return validation.reason
        if target.ui_owner == "browser_app" and browser_url and _probe_browser_shell_ready(browser_url):
            return _BROWSER_SERVER_READY_REASON
        time.sleep(_AUTO_LAUNCH_POLL_INTERVAL_SECONDS)
    return "launch_timeout"


def _edge_user_data_dir() -> Path | None:
    local_appdata = str(os.environ.get("LOCALAPPDATA", "") or "").strip()
    if local_appdata == "":
        return None
    return Path(local_appdata) / "Microsoft" / "Edge" / "User Data"


def _coerce_disable_reasons(value: object) -> tuple[int, ...]:
    if not isinstance(value, list):
        return ()
    output: list[int] = []
    for item in value:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        output.append(parsed)
    return tuple(output)


def discover_edge_unpacked_gmail_extensions(
    *,
    edge_user_data_dir: Path | None = None,
) -> tuple[EdgeUnpackedExtensionRecord, ...]:
    root = edge_user_data_dir or _edge_user_data_dir()
    if root is None or not root.exists():
        return ()

    records: list[EdgeUnpackedExtensionRecord] = []
    try:
        profiles = sorted(path for path in root.iterdir() if path.is_dir())
    except OSError:
        return ()

    for profile_dir in profiles:
        secure_preferences = profile_dir / "Secure Preferences"
        if not secure_preferences.exists():
            continue
        try:
            payload = json.loads(secure_preferences.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        settings = payload.get("extensions", {}).get("settings", {})
        if not isinstance(settings, dict):
            continue
        for extension_id, entry in settings.items():
            if not isinstance(entry, dict):
                continue
            if int(entry.get("location", -1)) != 4:
                continue
            path_text = str(entry.get("path", "") or "").strip()
            if path_text == "":
                continue
            normalized = _normalize_edge_extension_path(path_text)
            if not normalized.endswith("/extensions/gmail_intake"):
                continue
            cleaned_extension_id = str(extension_id).strip()
            disable_reasons = _coerce_disable_reasons(entry.get("disable_reasons"))
            records.append(
                EdgeUnpackedExtensionRecord(
                    profile_name=profile_dir.name,
                    extension_id=cleaned_extension_id,
                    path=path_text,
                    disable_reasons=disable_reasons,
                    enabled=len(disable_reasons) == 0,
                )
            )
    return tuple(
        sorted(
            (record for record in records if record.extension_id),
            key=lambda item: (item.profile_name.casefold(), item.extension_id.casefold()),
        )
    )


def _normalize_edge_extension_path(path_text: str) -> str:
    cleaned = str(path_text or "").strip().replace("\\", "/")
    if cleaned.startswith("//?/"):
        cleaned = cleaned[4:]
    return cleaned.rstrip("/").lower()


def discover_edge_unpacked_gmail_extension_ids(*, edge_user_data_dir: Path | None = None) -> tuple[str, ...]:
    ids = {record.extension_id for record in discover_edge_unpacked_gmail_extensions(edge_user_data_dir=edge_user_data_dir)}
    return tuple(sorted(item for item in ids if item))


def edge_native_host_allowed_origins(*, edge_user_data_dir: Path | None = None) -> tuple[str, ...]:
    origins = {EDGE_EXTENSION_ORIGIN}
    for extension_id in discover_edge_unpacked_gmail_extension_ids(edge_user_data_dir=edge_user_data_dir):
        origins.add(f"chrome-extension://{extension_id}/")
    return tuple(sorted(origins))


def build_edge_extension_report(*, edge_user_data_dir: Path | None = None) -> dict[str, object]:
    records = discover_edge_unpacked_gmail_extensions(edge_user_data_dir=edge_user_data_dir)
    active_ids = [record.extension_id for record in records if record.enabled]
    stale_ids = [record.extension_id for record in records if not record.enabled]
    paths = sorted({record.path for record in records if record.path})
    return {
        "edge_user_data_dir": str((edge_user_data_dir or _edge_user_data_dir() or Path("")).expanduser()),
        "stable_extension_id": EDGE_EXTENSION_ID,
        "stable_extension_origin": EDGE_EXTENSION_ORIGIN,
        "active_extension_ids": active_ids,
        "stale_extension_ids": stale_ids,
        "paths": paths,
        "records": [
            {
                "profile_name": record.profile_name,
                "extension_id": record.extension_id,
                "path": record.path,
                "disable_reasons": list(record.disable_reasons),
                "enabled": record.enabled,
            }
            for record in records
        ],
    }


def build_edge_native_host_manifest(
    host_executable_path: Path,
    *,
    edge_user_data_dir: Path | None = None,
) -> dict[str, object]:
    return {
        "name": EDGE_NATIVE_HOST_NAME,
        "description": "LegalPDF Translate foreground activation host",
        "path": str(host_executable_path.expanduser().resolve()),
        "type": "stdio",
        "allowed_origins": list(edge_native_host_allowed_origins(edge_user_data_dir=edge_user_data_dir)),
    }


def edge_native_host_manifest_path(base_dir: Path) -> Path:
    return base_dir / "native_messaging" / f"{EDGE_NATIVE_HOST_NAME}.edge.json"


def _edge_native_host_wrapper_path(base_dir: Path) -> Path:
    return base_dir / "native_messaging" / _EDGE_NATIVE_HOST_WRAPPER


def _native_host_path_kind(path: Path | str | None) -> str:
    if path is None:
        return ""
    suffix = Path(str(path)).suffix.casefold()
    if suffix == ".exe":
        return "exe"
    if suffix == ".cmd":
        return "cmd"
    return suffix.lstrip(".")


def _read_registered_native_host_path(
    *,
    base_dir: Path | None = None,
    read_registry_value=None,
) -> Path | None:
    active_read_registry_value = read_registry_value or _read_edge_native_host_registry_value
    manifest_dir = (base_dir or app_data_dir()).expanduser().resolve()
    registered_manifest_text = str(active_read_registry_value() or "").strip()
    if registered_manifest_text == "":
        return None
    try:
        registered_manifest_path = Path(registered_manifest_text).expanduser().resolve()
    except Exception:  # noqa: BLE001
        return None
    manifest_payload = _read_edge_native_host_manifest_payload(registered_manifest_path)
    if not isinstance(manifest_payload, dict):
        return None
    registered_host_text = str(manifest_payload.get("path", "") or "").strip()
    if registered_host_text == "":
        return None
    try:
        return Path(registered_host_text).expanduser().resolve()
    except Exception:  # noqa: BLE001
        return None


def _registered_native_host_path_kind(
    *,
    base_dir: Path | None = None,
    read_registry_value=None,
) -> str:
    return _native_host_path_kind(_read_registered_native_host_path(base_dir=base_dir, read_registry_value=read_registry_value))


def _edge_native_host_launcher_source_path(*, repo_root: Path | None = None) -> Path:
    root = (repo_root or _repo_root()).expanduser().resolve()
    return root / _EDGE_NATIVE_HOST_LAUNCHER_SOURCE


def _edge_native_host_output_path(*, repo_root: Path | None = None) -> Path:
    root = (repo_root or _repo_root()).expanduser().resolve()
    return root / _EDGE_NATIVE_HOST_BUILD_DIR / _EDGE_NATIVE_HOST_EXE


def _resolve_windows_csharp_compiler() -> Path | None:
    if not _is_windows():
        return None
    windir = Path(str(os.environ.get("WINDIR", r"C:\Windows")) or r"C:\Windows")
    candidates = (
        windir / "Microsoft.NET" / "Framework64" / "v4.0.30319" / "csc.exe",
        windir / "Microsoft.NET" / "Framework" / "v4.0.30319" / "csc.exe",
    )
    for candidate in candidates:
        resolved = _absolute_path_noresolve(candidate)
        if resolved.exists():
            return resolved
    return None


def build_edge_native_host_executable(
    *,
    repo_root: Path | None = None,
    force: bool = False,
) -> tuple[Path | None, str]:
    root = (repo_root or _repo_root()).expanduser().resolve()
    source_path = _edge_native_host_launcher_source_path(repo_root=root)
    if not source_path.exists():
        return None, "native_host_launcher_source_missing"
    compiler_path = _resolve_windows_csharp_compiler()
    if compiler_path is None:
        return None, "native_host_launcher_compiler_missing"
    output_path = _edge_native_host_output_path(repo_root=root)
    if output_path.exists() and not force:
        try:
            if output_path.stat().st_mtime >= source_path.stat().st_mtime:
                return output_path, "native_host_launcher_ready"
        except OSError:
            pass

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output_path = output_path.with_suffix(".tmp.exe")
    run_kwargs: dict[str, object] = {
        "capture_output": True,
        "text": True,
        "timeout": 60,
        "check": False,
        "cwd": str(root),
    }
    if _is_windows():
        run_kwargs["creationflags"] = _windows_no_window_creationflags()
    completed = subprocess.run(
        [
            str(compiler_path),
            "/nologo",
            "/optimize+",
            "/target:winexe",
            f"/out:{temp_output_path}",
            str(source_path),
        ],
        **run_kwargs,
    )
    if completed.returncode != 0 or not temp_output_path.exists():
        try:
            temp_output_path.unlink()
        except OSError:
            pass
        return None, "native_host_launcher_build_failed"
    temp_output_path.replace(output_path)
    return output_path, "native_host_launcher_built"


def _native_host_launcher_buildable(*, repo_root: Path | None = None) -> bool:
    root = (repo_root or _repo_root()).expanduser().resolve()
    return _edge_native_host_launcher_source_path(repo_root=root).exists() and _resolve_windows_csharp_compiler() is not None


def _build_checkout_edge_native_host_wrapper(*, repo_root: Path, python_executable: Path) -> str:
    resolved_repo = repo_root.expanduser().resolve()
    resolved_python = _absolute_path_noresolve(python_executable)
    resolved_src = (resolved_repo / "src").resolve()
    return (
        "@echo off\r\n"
        "setlocal\r\n"
        f'set "PYTHONPATH={resolved_src};%PYTHONPATH%"\r\n'
        f'cd /d "{resolved_repo}"\r\n'
        f'"{resolved_python}" -m legalpdf_translate.gmail_focus_host %*\r\n'
    )


def _ensure_checkout_edge_native_host_wrapper(
    *,
    base_dir: Path,
    runtime_path: Path | None = None,
    preferred_python_executable: Path | None = None,
) -> tuple[Path | None, str, bool]:
    worktree = _preferred_repo_worktree_for_auto_launch(runtime_path=runtime_path)
    if worktree is None:
        return None, "launch_target_missing", False
    python_executable, runtime_reason = _validated_python_executable_for_worktree(
        worktree,
        preferred_python_executable=preferred_python_executable,
        ui_owner="qt_app",
    )
    if python_executable is None:
        return None, runtime_reason, False

    wrapper_path = _edge_native_host_wrapper_path(base_dir).expanduser().resolve()
    wrapper_text = _build_checkout_edge_native_host_wrapper(
        repo_root=worktree,
        python_executable=python_executable,
    )
    changed = False
    existing_wrapper_text = None
    try:
        existing_wrapper_text = wrapper_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing_wrapper_text = None
    except OSError:
        existing_wrapper_text = None
    if existing_wrapper_text != wrapper_text:
        wrapper_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = wrapper_path.with_suffix(".tmp")
        temp_path.write_text(wrapper_text, encoding="utf-8")
        temp_path.replace(wrapper_path)
        changed = True
    return wrapper_path, "launch_target_ready", changed


def _host_executable_supports_self_test(host_executable_path: Path) -> bool:
    run_kwargs: dict[str, object] = {
        "capture_output": True,
        "text": True,
        "timeout": _SELF_TEST_TIMEOUT_SECONDS,
        "check": False,
    }
    if _is_windows():
        run_kwargs["creationflags"] = _windows_no_window_creationflags()
    try:
        completed = subprocess.run(
            [str(host_executable_path), "--self-test"],
            **run_kwargs,
        )
    except Exception:
        return False
    return completed.returncode == 0


def resolve_edge_native_host_executable(*, repo_root: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / _EDGE_NATIVE_HOST_EXE)
    root = repo_root or _repo_root()
    candidates.append(_edge_native_host_output_path(repo_root=root))

    seen: set[str] = set()
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if resolved.exists():
            return resolved
    return None


def _read_edge_native_host_registry_value() -> str | None:
    if not _is_windows():
        return None
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _EDGE_NATIVE_HOST_REGISTRY_SUBKEY) as key:
            value, _value_type = winreg.QueryValueEx(key, None)
    except OSError:
        return None
    return str(value or "").strip() or None


def _write_edge_native_host_registry_value(manifest_path: str) -> None:
    if not _is_windows():
        raise RuntimeError("unsupported_platform")
    try:
        import winreg
    except ImportError as exc:
        raise RuntimeError("winreg_unavailable") from exc
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _EDGE_NATIVE_HOST_REGISTRY_SUBKEY) as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, str(manifest_path))


def _read_edge_native_host_manifest_payload(manifest_path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _parse_wrapper_python_target(wrapper_path: Path) -> str | None:
    try:
        wrapper_text = wrapper_path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(
        r'^\s*"([^"]+)"\s+-m\s+legalpdf_translate\.gmail_focus_host(?:\s|$)',
        wrapper_text,
        re.IGNORECASE | re.MULTILINE,
    )
    if match is None:
        return None
    return str(_absolute_path_noresolve(Path(match.group(1))))


def _run_edge_native_host_self_test(host_path: Path) -> dict[str, object]:
    run_kwargs: dict[str, object] = {
        "capture_output": True,
        "text": True,
        "timeout": _SELF_TEST_TIMEOUT_SECONDS,
        "check": False,
    }
    if _is_windows():
        run_kwargs["creationflags"] = _windows_no_window_creationflags()
    try:
        completed = subprocess.run(
            [str(host_path), "--self-test"],
            **run_kwargs,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": "launch_failed",
            "reason": "native_host_self_test_launch_failed",
            "payload": {
                "message": str(exc) or "Native host self-test could not start.",
            },
        }
    stdout_text = str(completed.stdout or "").strip()
    stderr_text = str(completed.stderr or "").strip()
    payload: dict[str, object] | None = None
    if stdout_text:
        try:
            parsed = json.loads(stdout_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
    if completed.returncode == 0 and (payload is None or bool(payload.get("ok", True))):
        return {
            "ok": True,
            "status": "ok",
            "reason": str(payload.get("reason", "native_host_self_test_ok")) if isinstance(payload, dict) else "native_host_self_test_ok",
            "payload": payload or {
                "stdout": stdout_text,
            },
        }
    failure_payload: dict[str, object] = payload or {}
    if stdout_text and "stdout" not in failure_payload:
        failure_payload["stdout"] = stdout_text
    if stderr_text and "stderr" not in failure_payload:
        failure_payload["stderr"] = stderr_text
    failure_payload["returncode"] = int(completed.returncode)
    return {
        "ok": False,
        "status": "failed",
        "reason": str(failure_payload.get("reason", "native_host_self_test_failed")),
        "payload": failure_payload,
    }


def inspect_edge_native_host(
    *,
    base_dir: Path | None = None,
    preferred_python_executable: Path | None = None,
    runtime_path: Path | None = None,
    run_self_test: bool = True,
    read_registry_value=_read_edge_native_host_registry_value,
) -> dict[str, object]:
    manifest_dir = (base_dir or app_data_dir()).expanduser().resolve()
    expected_manifest_path = edge_native_host_manifest_path(manifest_dir).expanduser().resolve()
    wrapper_path = _edge_native_host_wrapper_path(manifest_dir).expanduser().resolve()
    registered_manifest_text = str(read_registry_value() or "").strip()
    registered_manifest_path = (
        Path(registered_manifest_text).expanduser().resolve()
        if registered_manifest_text
        else None
    )
    manifest_exists = bool(registered_manifest_path and registered_manifest_path.exists())
    manifest_matches_expected = bool(registered_manifest_path and registered_manifest_path == expected_manifest_path)
    manifest_payload = (
        _read_edge_native_host_manifest_payload(registered_manifest_path)
        if manifest_exists and registered_manifest_path is not None
        else None
    )
    registered_host_text = str(manifest_payload.get("path", "") or "").strip() if isinstance(manifest_payload, dict) else ""
    registered_host_path = Path(registered_host_text).expanduser().resolve() if registered_host_text else None
    host_exists = bool(registered_host_path and registered_host_path.exists())
    registered_host_path_kind = _native_host_path_kind(registered_host_path)
    wrapper_exists = wrapper_path.exists()
    wrapper_target_python = _parse_wrapper_python_target(wrapper_path) if wrapper_exists else None
    current_runtime = _absolute_path_noresolve(runtime_path or Path(sys.executable))
    current_runtime_python = str(current_runtime) if current_runtime else ""
    self_test_result: dict[str, object] = {
        "ok": False,
        "status": "not_run",
        "reason": "native_host_self_test_not_run",
        "payload": {},
    }
    if not run_self_test:
        self_test_result = {
            "ok": False,
            "status": "skipped",
            "reason": "native_host_self_test_skipped",
            "payload": {},
        }
    elif host_exists and registered_host_path is not None:
        self_test_result = _run_edge_native_host_self_test(registered_host_path)
    elif registered_host_path is not None:
        self_test_result = {
            "ok": False,
            "status": "missing_host",
            "reason": "native_host_executable_missing",
            "payload": {},
        }

    repair_supported = _is_windows()
    repairable = False
    repair_reason = "unsupported_platform"
    repair_target_kind = ""
    repair_target_python = ""
    packaged_host = None
    current_runtime_identity = _runtime_build_identity_for_registration(runtime_path=runtime_path)
    current_worktree = _preferred_repo_worktree_for_auto_launch(runtime_path=runtime_path)
    if repair_supported and current_runtime_identity is not None and not current_runtime_identity.is_canonical:
        repair_reason = "canonical_restart_required"
    elif repair_supported:
        packaged_host = resolve_edge_native_host_executable(repo_root=current_worktree)
        if packaged_host is not None and _host_executable_supports_self_test(packaged_host):
            repairable = True
            repair_reason = "packaged_host_ready"
            repair_target_kind = "packaged_host"
            repair_target_python = str(packaged_host.expanduser().resolve())
        elif _native_host_launcher_buildable(repo_root=current_worktree or _repo_root()):
            repairable = True
            repair_reason = "native_host_launcher_build_ready"
            repair_target_kind = "packaged_host"
            repair_target_python = str(_edge_native_host_output_path(repo_root=current_worktree or _repo_root()))

    ready = False
    reason = "native_host_unregistered"
    message = "Edge native host is not registered yet."
    if not repair_supported:
        reason = "unsupported_platform"
        message = "Edge native host diagnostics are only available on Windows."
    elif not registered_manifest_path:
        reason = "native_host_unregistered"
        message = "Edge native host is not registered yet."
    elif not manifest_exists:
        reason = "native_host_manifest_missing"
        message = "The registered Edge native host manifest is missing."
    elif manifest_payload is None:
        reason = "native_host_manifest_invalid"
        message = "The registered Edge native host manifest could not be read."
    elif registered_host_path is None:
        reason = "native_host_manifest_missing_path"
        message = "The registered Edge native host manifest does not point to a host executable."
    elif not host_exists:
        reason = "native_host_executable_missing"
        message = "The registered Edge native host executable is missing."
    elif not manifest_matches_expected:
        reason = "native_host_manifest_drift"
        message = "Edge is registered to a different native-host manifest than this browser app expects."
    elif run_self_test and not bool(self_test_result.get("ok")):
        reason = str(self_test_result.get("reason", "native_host_self_test_failed") or "native_host_self_test_failed")
        message = "The registered Edge native host failed its self-test."
    else:
        ready = True
        reason = "native_host_ready"
        message = (
            "Edge native host is registered and passed self-test."
            if run_self_test
            else "Edge native host is registered and structurally ready."
        )

    return {
        "configured": bool(registered_manifest_path),
        "ready": ready,
        "reason": reason,
        "message": message,
        "registry_key_path": EDGE_NATIVE_HOST_REGISTRY_KEY_PATH,
        "registered_manifest_path": str(registered_manifest_path) if registered_manifest_path is not None else "",
        "expected_manifest_path": str(expected_manifest_path),
        "manifest_exists": manifest_exists,
        "manifest_matches_expected": manifest_matches_expected,
        "registered_host_path": str(registered_host_path) if registered_host_path is not None else "",
        "registered_host_path_kind": registered_host_path_kind,
        "host_exists": host_exists,
        "wrapper_path": str(wrapper_path),
        "wrapper_path_kind": _native_host_path_kind(wrapper_path),
        "wrapper_exists": wrapper_exists,
        "wrapper_target_python": wrapper_target_python or "",
        "self_test_ok": bool(self_test_result.get("ok")),
        "self_test_status": str(self_test_result.get("status", "not_run") or "not_run"),
        "self_test_reason": str(self_test_result.get("reason", "") or ""),
        "self_test_payload": dict(self_test_result.get("payload", {}) or {}),
        "repair_supported": repair_supported,
        "repairable": repairable,
        "repair_reason": repair_reason,
        "repair_target_kind": repair_target_kind,
        "repair_target_python": repair_target_python,
        "repair_recommended": bool(not ready and repairable),
        "current_runtime_python": current_runtime_python,
        "current_runtime_is_canonical": bool(current_runtime_identity.is_canonical) if current_runtime_identity is not None else None,
    }


def _looks_like_pytest_temp_base_dir(base_dir: Path) -> bool:
    try:
        resolved_base = base_dir.expanduser().resolve()
        temp_root = Path(tempfile.gettempdir()).expanduser().resolve()
        resolved_base.relative_to(temp_root)
    except Exception:  # noqa: BLE001
        return False
    lowered_parts = [part.lower() for part in resolved_base.parts]
    return any(
        part.startswith("pytest-")
        or part.startswith("pytest_of")
        or part.startswith("pytest-of-")
        for part in lowered_parts
    )


def maybe_ensure_edge_native_host_registered(
    *,
    base_dir: Path | None = None,
    host_executable_path: Path | None = None,
    preferred_python_executable: Path | None = None,
    runtime_path: Path | None = None,
    read_registry_value=_read_edge_native_host_registry_value,
    write_registry_value=_write_edge_native_host_registry_value,
) -> NativeHostRegistrationResult:
    manifest_dir = (base_dir or app_data_dir()).expanduser().resolve()
    if _is_truthy_env(os.environ.get("LEGALPDF_SKIP_EDGE_NATIVE_HOST_AUTO_REGISTRATION")):
        return NativeHostRegistrationResult(
            ok=False,
            changed=False,
            manifest_path=None,
            executable_path=None,
            reason="skipped_by_env",
        )
    if str(os.environ.get("PYTEST_CURRENT_TEST", "") or "").strip():
        return NativeHostRegistrationResult(
            ok=False,
            changed=False,
            manifest_path=None,
            executable_path=None,
            reason="skipped_pytest_runtime",
        )
    if _looks_like_pytest_temp_base_dir(manifest_dir):
        return NativeHostRegistrationResult(
            ok=False,
            changed=False,
            manifest_path=None,
            executable_path=None,
            reason="skipped_pytest_temp_base_dir",
        )
    return ensure_edge_native_host_registered(
        base_dir=manifest_dir,
        host_executable_path=host_executable_path,
        preferred_python_executable=preferred_python_executable,
        runtime_path=runtime_path,
        read_registry_value=read_registry_value,
        write_registry_value=write_registry_value,
    )


def ensure_edge_native_host_registered(
    *,
    base_dir: Path | None = None,
    host_executable_path: Path | None = None,
    preferred_python_executable: Path | None = None,
    runtime_path: Path | None = None,
    read_registry_value=_read_edge_native_host_registry_value,
    write_registry_value=_write_edge_native_host_registry_value,
) -> NativeHostRegistrationResult:
    if not _is_windows():
        return NativeHostRegistrationResult(
            ok=False,
            changed=False,
            manifest_path=None,
            executable_path=None,
            reason="unsupported_platform",
        )

    current_runtime_identity = _runtime_build_identity_for_registration(runtime_path=runtime_path)
    if current_runtime_identity is not None and not current_runtime_identity.is_canonical:
        return NativeHostRegistrationResult(
            ok=False,
            changed=False,
            manifest_path=None,
            executable_path=None,
            reason="canonical_restart_required",
        )

    manifest_dir = (base_dir or app_data_dir()).expanduser().resolve()
    resolution_reason = "host_executable_missing"
    if host_executable_path is not None:
        resolved_host_exe = host_executable_path.expanduser().resolve()
    else:
        resolved_host_exe = None
        current_worktree = _preferred_repo_worktree_for_auto_launch(runtime_path=runtime_path)
        packaged_host = resolve_edge_native_host_executable(
            repo_root=current_worktree
        )
        if packaged_host is not None and _host_executable_supports_self_test(packaged_host):
            resolved_host_exe = packaged_host
        if resolved_host_exe is None:
            resolved_host_exe, resolution_reason = build_edge_native_host_executable(
                repo_root=current_worktree or _repo_root(),
            )
    if resolved_host_exe is None or not resolved_host_exe.exists():
        return NativeHostRegistrationResult(
            ok=False,
            changed=False,
            manifest_path=None,
            executable_path=str(resolved_host_exe) if resolved_host_exe is not None else None,
            reason=resolution_reason,
        )
    if not _host_executable_supports_self_test(resolved_host_exe):
        return NativeHostRegistrationResult(
            ok=False,
            changed=False,
            manifest_path=None,
            executable_path=str(resolved_host_exe),
            reason="native_host_self_test_failed",
        )

    manifest_path = edge_native_host_manifest_path(manifest_dir).expanduser().resolve()
    manifest_payload = build_edge_native_host_manifest(resolved_host_exe)
    manifest_text = json.dumps(manifest_payload, ensure_ascii=False, indent=2) + "\n"
    changed = False

    existing_manifest_text = None
    try:
        existing_manifest_text = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing_manifest_text = None
    except OSError:
        existing_manifest_text = None
    if existing_manifest_text != manifest_text:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = manifest_path.with_suffix(".tmp")
        temp_path.write_text(manifest_text, encoding="utf-8")
        temp_path.replace(manifest_path)
        changed = True

    manifest_value = str(manifest_path)
    registered_value = str(read_registry_value() or "").strip() or None
    if registered_value != manifest_value:
        write_registry_value(manifest_value)
        changed = True

    return NativeHostRegistrationResult(
        ok=True,
        changed=changed,
        manifest_path=manifest_value,
        executable_path=str(resolved_host_exe),
        reason="registered" if changed else "already_registered",
    )


def read_native_message(stream: BinaryIO) -> dict[str, object]:
    raw_length = stream.read(4)
    if raw_length == b"":
        raise EOFError("Native host stdin closed.")
    if len(raw_length) != 4:
        raise ValueError("Native message length header is incomplete.")
    message_length = struct.unpack("<I", raw_length)[0]
    if message_length <= 0 or message_length > _MAX_NATIVE_MESSAGE_BYTES:
        raise ValueError("Native message length is invalid.")
    payload_bytes = stream.read(message_length)
    if len(payload_bytes) != message_length:
        raise ValueError("Native message body is incomplete.")
    payload = json.loads(payload_bytes.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Native message must be a JSON object.")
    return payload


def write_native_message(stream: BinaryIO, payload: dict[str, object]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    stream.write(struct.pack("<I", len(body)))
    stream.write(body)
    stream.flush()


def _normalize_bool(value: object, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _read_gmail_bridge_settings(*, settings_loader=None) -> dict[str, object]:
    active_settings_loader = settings_loader or load_gui_settings
    try:
        payload = active_settings_loader()
    except Exception:  # noqa: BLE001
        payload = {}
    if not isinstance(payload, dict):
        payload = {}

    enabled = bool(payload.get("gmail_intake_bridge_enabled", False))
    token = str(payload.get("gmail_intake_bridge_token", "") or "").strip()
    try:
        bridge_port = int(payload.get("gmail_intake_port", 0))
    except (TypeError, ValueError):
        bridge_port = 0
    return {
        "enabled": enabled,
        "bridgeToken": token,
        "bridgeTokenPresent": token != "",
        "bridgePort": bridge_port if 1 <= bridge_port <= 65535 else None,
    }


def prepare_gmail_intake(
    *,
    base_dir: Path | None = None,
    request_focus: bool = True,
    include_token: bool = True,
    settings_loader=None,
    handoff_session_requested: bool = False,
) -> dict[str, object]:
    settings = _read_gmail_bridge_settings(settings_loader=settings_loader)
    runtime_state_root = resolve_runtime_state_root(base_dir or app_data_dir())
    auto_launch_target = _resolve_auto_launch_target()
    latest_trace_state = latest_window_trace_status(runtime_state_root)
    native_host_path_kind = _registered_native_host_path_kind(base_dir=runtime_state_root)
    response: dict[str, object] = {
        "ok": False,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": bool(settings["bridgeTokenPresent"]),
        "launched": False,
        "autoLaunchReady": auto_launch_target.ready,
        "launchTargetReason": auto_launch_target.reason,
        "ui_owner": "none",
        "runtime_state_root": str(runtime_state_root),
    }
    if str(latest_trace_state.get("launch_session_id", "") or "").strip():
        response["launch_session_id"] = str(latest_trace_state.get("launch_session_id", "") or "").strip()
    handoff_session_id = build_launch_session_id() if handoff_session_requested else ""
    if handoff_session_id:
        response["handoff_session_id"] = handoff_session_id
    if auto_launch_target.worktree_path:
        response["launchTarget"] = auto_launch_target.worktree_path
    if auto_launch_target.ui_owner == "browser_app" and auto_launch_target.browser_url:
        response["browser_url"] = auto_launch_target.browser_url
        response["browser_open_owned_by"] = _BROWSER_OPEN_OWNER_EXTENSION
    if native_host_path_kind:
        response["native_host_path_kind"] = native_host_path_kind
    bridge_port = settings.get("bridgePort")
    if isinstance(bridge_port, int):
        response["bridgePort"] = bridge_port

    if not bool(settings["enabled"]):
        response["reason"] = "bridge_disabled"
        return response
    if not bool(settings["bridgeTokenPresent"]):
        response["reason"] = "bridge_token_missing"
        return response
    if not isinstance(bridge_port, int):
        response["reason"] = "invalid_bridge_port"
        return response

    validation = validate_bridge_owner(
        bridge_port=bridge_port,
        base_dir=runtime_state_root,
    )
    response["reason"] = validation.reason
    _apply_validation_context(
        response,
        validation=validation,
        fallback_browser_url=auto_launch_target.browser_url,
    )

    active_launch_lock = (
        _read_browser_auto_launch_lock(runtime_state_root)
        if auto_launch_target.ui_owner == "browser_app"
        else None
    )
    if validation.ok:
        if active_launch_lock is not None:
            _clear_browser_auto_launch_lock(runtime_state_root)
        if (
            handoff_session_id
            and str(getattr(validation, "owner_kind", "") or "").strip() == "browser_app"
        ):
            current_launch_session_id = str(response.get("launch_session_id", "") or "").strip() or build_launch_session_id()
            response["launch_session_id"] = current_launch_session_id
            update_launch_session_state(
                runtime_state_root,
                launch_session_id=current_launch_session_id,
                **_fresh_extension_handoff_state(),
                handoff_session_id=handoff_session_id,
                status="launch_ready",
                reason=str(validation.reason or "").strip(),
                browser_url=str(getattr(validation, "browser_url", "") or auto_launch_target.browser_url or "").strip(),
                workspace_id=str(getattr(validation, "workspace_id", "") or _BROWSER_GMAIL_WORKSPACE_ID).strip() or _BROWSER_GMAIL_WORKSPACE_ID,
                runtime_mode=str(getattr(validation, "runtime_mode", "") or "live").strip() or "live",
                browser_open_owned_by=str(response.get("browser_open_owned_by", "") or _BROWSER_OPEN_OWNER_EXTENSION).strip() or _BROWSER_OPEN_OWNER_EXTENSION,
                launch_runtime_path=str(auto_launch_target.python_executable or "").strip(),
                launch_phase=(
                    "browser_surface_ready"
                    if str(response.get("browser_open_owned_by", "") or "").strip() == _BROWSER_OPEN_OWNER_EXTENSION
                    else "server_boot"
                ),
                native_host_path_kind=native_host_path_kind,
            )
    elif active_launch_lock is not None and validation.reason in _AUTO_LAUNCHABLE_BRIDGE_REASONS:
        response["reason"] = _AUTO_LAUNCH_IN_PROGRESS_REASON
        _apply_browser_auto_launch_lock_context(
            response,
            lock_payload=active_launch_lock,
            fallback_browser_url=auto_launch_target.browser_url,
        )
        return response
    elif active_launch_lock is not None:
        _clear_browser_auto_launch_lock(runtime_state_root)

    if not validation.ok and request_focus and validation.reason in _AUTO_LAUNCHABLE_BRIDGE_REASONS:
        launch_lock_payload: dict[str, object] | None = None
        launch_session_id = build_launch_session_id()
        trace_request = consume_armed_window_trace(runtime_state_root) if auto_launch_target.ui_owner == "browser_app" else None
        launch_session_state = update_launch_session_state(
            runtime_state_root,
            launch_session_id=launch_session_id,
            **_fresh_extension_handoff_state(),
            handoff_session_id=handoff_session_id,
            status="launch_started",
            browser_url=str(auto_launch_target.browser_url or "").strip(),
            workspace_id=_BROWSER_GMAIL_WORKSPACE_ID,
            runtime_mode="live",
            browser_open_owned_by=_BROWSER_OPEN_OWNER_SERVER_BOOT,
            launch_runtime_path=str(auto_launch_target.python_executable or "").strip()
            if auto_launch_target.ready and auto_launch_target.python_executable
            else "",
            native_host_path_kind=native_host_path_kind,
            trace_requested=bool(trace_request),
            trace_status="pending" if trace_request else "",
            trace_dir="",
            trace_samples_path="",
            trace_summary_path="",
            reason="launch_started",
        )
        response["launch_session_id"] = launch_session_id
        if auto_launch_target.ui_owner == "browser_app":
            launch_lock_payload = _write_browser_auto_launch_lock(
                runtime_state_root,
                auto_launch_target,
                launch_session_id=launch_session_id,
            )
        trace_reason = _start_window_trace_capture(
            base_dir=runtime_state_root,
            launch_session_id=launch_session_id,
            target=auto_launch_target,
            trace_request=trace_request,
        )
        if trace_request:
            launch_session_state = update_launch_session_state(
                runtime_state_root,
                launch_session_id=launch_session_id,
                trace_status=trace_reason,
                trace_dir=launch_session_state.get("trace_dir", ""),
                trace_samples_path=launch_session_state.get("trace_samples_path", ""),
                trace_summary_path=launch_session_state.get("trace_summary_path", ""),
            )
        launch_target = auto_launch_target
        if auto_launch_target.ui_owner == "browser_app":
            launch_target = replace(
                auto_launch_target,
                launch_args=(
                    *auto_launch_target.launch_args,
                    "--launch-session-id",
                    launch_session_id,
                ),
            )
        launch_reason = _launch_repo_worktree(launch_target)
        if launch_reason != "launch_started":
            if auto_launch_target.ui_owner == "browser_app":
                _clear_browser_auto_launch_lock(runtime_state_root)
            update_launch_session_state(
                runtime_state_root,
                launch_session_id=launch_session_id,
                status=launch_reason,
                reason=launch_reason,
            )
            response["reason"] = launch_reason
            return response
        response["launched"] = True
        wait_reason = _wait_for_auto_launch_ready_after_launch(
            bridge_port=bridge_port,
            base_dir=runtime_state_root,
            target=auto_launch_target,
        )
        if wait_reason == _BROWSER_SERVER_READY_REASON and auto_launch_target.ui_owner == "browser_app":
            if launch_lock_payload is not None:
                launch_lock_payload = _write_browser_auto_launch_lock(
                    runtime_state_root,
                    auto_launch_target,
                    launch_session_id=launch_session_id,
                    browser_open_owned_by=_BROWSER_OPEN_OWNER_EXTENSION,
                )
            update_launch_session_state(
                runtime_state_root,
                launch_session_id=launch_session_id,
                status=_BROWSER_SERVER_READY_REASON,
                reason=_BROWSER_SERVER_READY_REASON,
                browser_open_owned_by=_BROWSER_OPEN_OWNER_EXTENSION,
                launch_phase="server_boot_ready",
                native_host_path_kind=native_host_path_kind,
            )
            _apply_browser_launch_ready_context(
                response,
                browser_url=str(auto_launch_target.browser_url or "").strip(),
                launch_session_id=launch_session_id,
                handoff_session_id=handoff_session_id,
                browser_open_owned_by=_BROWSER_OPEN_OWNER_EXTENSION,
                launch_lock_ttl_ms=(
                    int(launch_lock_payload.get("remaining_ms", 0) or 0)
                    if isinstance(launch_lock_payload, dict)
                    else None
                ),
                reason=_BROWSER_SERVER_READY_REASON,
            )
            if include_token:
                response["bridgeToken"] = str(settings["bridgeToken"])
            return response
        if wait_reason != "launch_ready":
            update_launch_session_state(
                runtime_state_root,
                launch_session_id=launch_session_id,
                handoff_session_id=handoff_session_id,
                status=(
                    _AUTO_LAUNCH_IN_PROGRESS_REASON
                    if auto_launch_target.ui_owner == "browser_app" and wait_reason == "launch_timeout"
                    else wait_reason
                ),
                reason=wait_reason,
                native_host_path_kind=native_host_path_kind,
            )
            if auto_launch_target.ui_owner == "browser_app" and launch_lock_payload is not None and wait_reason == "launch_timeout":
                _apply_browser_auto_launch_lock_context(
                    response,
                    lock_payload=launch_lock_payload,
                    fallback_browser_url=auto_launch_target.browser_url,
                )
                response["reason"] = _AUTO_LAUNCH_IN_PROGRESS_REASON
                return response
            if auto_launch_target.ui_owner == "browser_app":
                _clear_browser_auto_launch_lock(runtime_state_root)
            response["reason"] = wait_reason
            return response
        if auto_launch_target.ui_owner == "browser_app":
            _clear_browser_auto_launch_lock(runtime_state_root)
        validation = validate_bridge_owner(
            bridge_port=bridge_port,
            base_dir=runtime_state_root,
        )
        response["reason"] = validation.reason
        _apply_validation_context(
            response,
            validation=validation,
            fallback_browser_url=auto_launch_target.browser_url,
        )
        update_launch_session_state(
            runtime_state_root,
            launch_session_id=launch_session_id,
            handoff_session_id=handoff_session_id,
            status="launch_ready" if validation.ok else str(validation.reason or "launch_failed").strip() or "launch_failed",
            reason=str(validation.reason or "").strip(),
            browser_open_owned_by=(
                str(response.get("browser_open_owned_by", "") or "").strip()
                or (
                    _BROWSER_OPEN_OWNER_EXTENSION
                    if str(getattr(validation, "owner_kind", "") or "").strip() == "browser_app" and bool(validation.ok)
                    else _BROWSER_OPEN_OWNER_SERVER_BOOT
                )
            ),
            launch_phase=(
                "browser_surface_ready"
                if str(response.get("browser_open_owned_by", "") or "").strip() == _BROWSER_OPEN_OWNER_EXTENSION
                else "server_boot"
            ),
            native_host_path_kind=native_host_path_kind,
        )
        if not validation.ok and launch_lock_payload is not None:
            _clear_browser_auto_launch_lock(runtime_state_root)

    if not validation.ok:
        return response

    if str(getattr(validation, "owner_kind", "") or "").strip() == "browser_app":
        response["ok"] = True
        if include_token:
            response["bridgeToken"] = str(settings["bridgeToken"])
        return response

    if request_focus:
        focus_result = focus_bridge_owner(
            bridge_port=bridge_port,
            base_dir=runtime_state_root,
        )
        response["focused"] = focus_result.focused
        response["flashed"] = focus_result.flashed
        response["reason"] = focus_result.reason
        if not focus_result.ok:
            return response

    response["ok"] = True
    if include_token:
        response["bridgeToken"] = str(settings["bridgeToken"])
    return response


def handle_native_message(
    payload: object,
    *,
    base_dir: Path | None = None,
) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"ok": False, "focused": False, "flashed": False, "reason": "invalid_payload"}
    action = payload.get("action")
    if action == "prepare_gmail_intake":
        return prepare_gmail_intake(
            base_dir=(base_dir or app_data_dir()),
            request_focus=_normalize_bool(payload.get("requestFocus"), default=True),
            include_token=_normalize_bool(payload.get("includeToken"), default=True),
            handoff_session_requested=True,
        )
    if action != "focus_app":
        return {"ok": False, "focused": False, "flashed": False, "reason": "unsupported_action"}
    try:
        bridge_port = int(payload.get("bridgePort", 0))
    except (TypeError, ValueError):
        return {"ok": False, "focused": False, "flashed": False, "reason": "invalid_bridge_port"}
    result = focus_bridge_owner(
        bridge_port=bridge_port,
        base_dir=(base_dir or app_data_dir()),
    )
    return {
        "ok": result.ok,
        "focused": result.focused,
        "flashed": result.flashed,
        "reason": result.reason,
    }


def run() -> int:
    try:
        request = read_native_message(sys.stdin.buffer)
        response = handle_native_message(request)
    except EOFError:
        return 0
    except Exception as exc:  # noqa: BLE001
        response = {
            "ok": False,
            "focused": False,
            "flashed": False,
            "reason": str(exc) or "native_host_error",
        }
    write_native_message(sys.stdout.buffer, response)
    return 0


def cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--register", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--edge-extension-report", action="store_true")
    parser.add_argument("--edge-extension-report-file", type=str, default="")
    parser.add_argument("--host-executable", type=str, default="")
    parser.add_argument("--build-native-host-launcher", action="store_true")
    parser.add_argument("--restart-browser-runtime-canonical", action="store_true")
    parser.add_argument("--target-worktree", type=str, default="")
    parser.add_argument("--target-python", type=str, default="")
    parser.add_argument("--current-listener-pid", type=int, default=0)
    parser.add_argument("--runtime-mode", type=str, default="live")
    parser.add_argument("--workspace-id", type=str, default=_BROWSER_GMAIL_WORKSPACE_ID)
    args, _unknown = parser.parse_known_args(argv)
    if args.self_test:
        print(json.dumps(_self_test_payload(), ensure_ascii=False))
        return 0
    if args.register:
        host_executable = Path(args.host_executable).expanduser() if args.host_executable.strip() else None
        result = ensure_edge_native_host_registered(host_executable_path=host_executable)
        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "changed": result.changed,
                    "manifest_path": result.manifest_path,
                    "executable_path": result.executable_path,
                    "reason": result.reason,
                }
            )
        )
        return 0 if result.ok else 1
    if args.build_native_host_launcher:
        built_path, reason = build_edge_native_host_executable(repo_root=_preferred_repo_worktree_for_auto_launch())
        print(
            json.dumps(
                {
                    "ok": built_path is not None,
                    "path": str(built_path) if built_path is not None else "",
                    "reason": reason,
                }
            )
        )
        return 0 if built_path is not None else 1
    if args.edge_extension_report:
        report_text = json.dumps(build_edge_extension_report(), ensure_ascii=False)
        if args.edge_extension_report_file.strip():
            Path(args.edge_extension_report_file).expanduser().write_text(report_text, encoding="utf-8")
        else:
            print(report_text)
        return 0
    if args.restart_browser_runtime_canonical:
        payload = _run_restart_browser_runtime_canonical(
            target_worktree=args.target_worktree,
            target_python=args.target_python,
            current_listener_pid=args.current_listener_pid,
            runtime_mode=args.runtime_mode,
            workspace_id=args.workspace_id,
        )
        print(json.dumps(payload, ensure_ascii=False))
        return 0 if bool(payload.get("ok")) else 1
    return run()


def main() -> None:
    raise SystemExit(cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
