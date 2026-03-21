"""Edge native-messaging host for Gmail intake foreground activation."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

from legalpdf_translate.build_identity import normalize_path_identity, try_load_canonical_build_config
from legalpdf_translate.gmail_focus import focus_bridge_owner, validate_bridge_owner
from legalpdf_translate.shadow_runtime import SHADOW_DEFAULT_PORT
from legalpdf_translate.user_settings import app_data_dir, load_gui_settings


EDGE_NATIVE_HOST_NAME = "com.legalpdf.gmail_focus"
EDGE_EXTENSION_ID = "afckgbhjkmojchdlinolkepffchlgpin"
EDGE_EXTENSION_ORIGIN = f"chrome-extension://{EDGE_EXTENSION_ID}/"
_MAX_NATIVE_MESSAGE_BYTES = 1024 * 1024
_EDGE_NATIVE_HOST_REGISTRY_SUBKEY = rf"Software\Microsoft\Edge\NativeMessagingHosts\{EDGE_NATIVE_HOST_NAME}"
_EDGE_NATIVE_HOST_EXE = "LegalPDFGmailFocusHost.exe"
_AUTO_LAUNCH_WAIT_SECONDS = 15.0
_AUTO_LAUNCH_POLL_INTERVAL_SECONDS = 0.25
_AUTO_LAUNCH_LABELS = ("gmail-intake", "auto-launch")
_AUTO_LAUNCHABLE_BRIDGE_REASONS = {"runtime_metadata_missing", "bridge_not_running", "bridge_owner_stale"}
_WSL_MNT_RE = re.compile(r"^/mnt/([A-Za-z])/(.*)$")
_BROWSER_GMAIL_WORKSPACE_ID = "gmail-intake"


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


def _looks_like_repo_worktree(path: Path) -> bool:
    candidate = path.expanduser().resolve()
    return (
        (candidate / "tooling" / "launch_qt_build.py").exists()
        and (candidate / "src" / "legalpdf_translate" / "qt_app.py").exists()
    )


def _python_executable_for_worktree(worktree: Path) -> Path | None:
    resolved_worktree = worktree.expanduser().resolve()
    roots: list[Path] = [resolved_worktree]
    config = try_load_canonical_build_config(resolved_worktree)
    if config is not None:
        canonical_root = _coerce_repo_path(config.canonical_worktree_path).resolve()
        if canonical_root not in roots:
            roots.append(canonical_root)
    candidates: list[Path] = []
    for root in roots:
        candidates.extend(
            [
                root / ".venv311" / "Scripts" / "python.exe",
                root / ".venv" / "Scripts" / "python.exe",
            ]
        )
    for candidate in candidates:
        resolved = candidate.expanduser().resolve()
        if resolved.exists():
            return resolved
    return None


def _resolve_repo_worktree_for_auto_launch(*, runtime_path: Path | None = None) -> Path | None:
    if runtime_path is None:
        if getattr(sys, "frozen", False):
            runtime_path = Path(sys.executable).resolve()
        else:
            runtime_path = _repo_root()
    start = runtime_path.expanduser().resolve()
    search_root = start if start.is_dir() else start.parent
    for candidate in (search_root, *search_root.parents):
        if _looks_like_repo_worktree(candidate):
            return candidate
    return None


def _browser_gmail_workspace_url(*, port: int = SHADOW_DEFAULT_PORT) -> str:
    return f"http://127.0.0.1:{int(port)}/?mode=live&workspace={_BROWSER_GMAIL_WORKSPACE_ID}#gmail-intake"


def _resolve_qt_auto_launch_target(*, runtime_path: Path | None = None) -> AutoLaunchTarget:
    worktree = _resolve_repo_worktree_for_auto_launch(runtime_path=runtime_path)
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

    python_executable = _python_executable_for_worktree(worktree)
    if python_executable is None:
        return AutoLaunchTarget(
            ready=False,
            worktree_path=str(worktree),
            python_executable=None,
            launcher_script=str(launcher_script),
            reason="launch_python_missing",
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
    worktree = _resolve_repo_worktree_for_auto_launch(runtime_path=runtime_path)
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

    python_executable = _python_executable_for_worktree(worktree)
    if python_executable is None:
        return AutoLaunchTarget(
            ready=False,
            worktree_path=str(worktree),
            python_executable=None,
            launcher_script=None,
            reason="launch_python_missing",
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
            "-m",
            "legalpdf_translate.shadow_web.server",
            "--port",
            str(SHADOW_DEFAULT_PORT),
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
    elif fallback_browser_url:
        response["browser_url"] = fallback_browser_url


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
            creationflags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
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
        if validation.reason in {"bridge_port_owner_mismatch", "invalid_bridge_port", "unsupported_platform"}:
            return validation.reason
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
            normalized = normalize_path_identity(path_text)
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


def resolve_edge_native_host_executable(*, repo_root: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / _EDGE_NATIVE_HOST_EXE)
    root = repo_root or _repo_root()
    candidates.append(root / "dist" / "legalpdf_translate" / _EDGE_NATIVE_HOST_EXE)

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


def ensure_edge_native_host_registered(
    *,
    base_dir: Path | None = None,
    host_executable_path: Path | None = None,
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

    resolved_host_exe = (
        host_executable_path.expanduser().resolve()
        if host_executable_path is not None
        else resolve_edge_native_host_executable()
    )
    if resolved_host_exe is None or not resolved_host_exe.exists():
        return NativeHostRegistrationResult(
            ok=False,
            changed=False,
            manifest_path=None,
            executable_path=str(resolved_host_exe) if resolved_host_exe is not None else None,
            reason="host_executable_missing",
        )

    manifest_dir = (base_dir or app_data_dir()).expanduser().resolve()
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
) -> dict[str, object]:
    settings = _read_gmail_bridge_settings(settings_loader=settings_loader)
    base_dir = (base_dir or app_data_dir())
    auto_launch_target = _resolve_auto_launch_target()
    response: dict[str, object] = {
        "ok": False,
        "focused": False,
        "flashed": False,
        "bridgeTokenPresent": bool(settings["bridgeTokenPresent"]),
        "launched": False,
        "autoLaunchReady": auto_launch_target.ready,
        "launchTargetReason": auto_launch_target.reason,
        "ui_owner": "none",
    }
    if auto_launch_target.worktree_path:
        response["launchTarget"] = auto_launch_target.worktree_path
    if auto_launch_target.ui_owner == "browser_app" and auto_launch_target.browser_url:
        response["browser_url"] = auto_launch_target.browser_url
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
        base_dir=base_dir,
    )
    response["reason"] = validation.reason
    _apply_validation_context(
        response,
        validation=validation,
        fallback_browser_url=auto_launch_target.browser_url,
    )

    if not validation.ok and request_focus and validation.reason in _AUTO_LAUNCHABLE_BRIDGE_REASONS:
        launch_reason = _launch_repo_worktree(auto_launch_target)
        if launch_reason != "launch_started":
            response["reason"] = launch_reason
            return response
        response["launched"] = True
        wait_reason = _wait_for_bridge_owner_after_launch(
            bridge_port=bridge_port,
            base_dir=base_dir,
        )
        if wait_reason != "launch_ready":
            response["reason"] = wait_reason
            return response
        validation = validate_bridge_owner(
            bridge_port=bridge_port,
            base_dir=base_dir,
        )
        response["reason"] = validation.reason
        _apply_validation_context(
            response,
            validation=validation,
            fallback_browser_url=auto_launch_target.browser_url,
        )

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
            base_dir=base_dir,
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
    parser.add_argument("--edge-extension-report", action="store_true")
    parser.add_argument("--edge-extension-report-file", type=str, default="")
    parser.add_argument("--host-executable", type=str, default="")
    args, _unknown = parser.parse_known_args(argv)
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
    if args.edge_extension_report:
        report_text = json.dumps(build_edge_extension_report(), ensure_ascii=False)
        if args.edge_extension_report_file.strip():
            Path(args.edge_extension_report_file).expanduser().write_text(report_text, encoding="utf-8")
        else:
            print(report_text)
        return 0
    return run()


def main() -> None:
    raise SystemExit(cli(sys.argv[1:]))


if __name__ == "__main__":
    main()
