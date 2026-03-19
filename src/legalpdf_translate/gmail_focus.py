"""Windows foreground-attention helpers for Gmail intake."""

from __future__ import annotations

import ctypes
import json
import os
import re
import socket
import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_BRIDGE_RUNTIME_FILENAME = "gmail_intake_bridge_runtime.json"
_WINDOWS_NETSTAT_LISTEN_RE = re.compile(
    r"^\s*TCP\s+127\.0\.0\.1:(?P<port>\d+)\s+\S+\s+LISTENING\s+(?P<pid>\d+)\s*$",
    re.IGNORECASE,
)
_AF_INET = 2
_TCP_TABLE_OWNER_PID_LISTENER = 3
_NO_ERROR = 0
_ERROR_INSUFFICIENT_BUFFER = 122
_SW_RESTORE = 9
_FLASHW_TRAY = 0x00000002
_FLASHW_TIMERNOFG = 0x0000000C


@dataclass(frozen=True, slots=True)
class WindowAttentionResult:
    requested: bool
    restored: bool
    focused: bool
    flashed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class BridgeFocusResult:
    ok: bool
    focused: bool
    flashed: bool
    reason: str


@dataclass(frozen=True, slots=True)
class BridgeOwnerValidationResult:
    ok: bool
    pid: int | None
    hwnd: int | None
    reason: str
    owner_kind: str | None = None
    runtime_mode: str | None = None
    workspace_id: str | None = None
    browser_url: str | None = None


class _FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hwnd", ctypes.c_void_p),
        ("dwFlags", ctypes.c_uint),
        ("uCount", ctypes.c_uint),
        ("dwTimeout", ctypes.c_uint),
    ]


class _MIB_TCPROW_OWNER_PID(ctypes.Structure):
    _fields_ = [
        ("dwState", ctypes.c_ulong),
        ("dwLocalAddr", ctypes.c_ulong),
        ("dwLocalPort", ctypes.c_ulong),
        ("dwRemoteAddr", ctypes.c_ulong),
        ("dwRemotePort", ctypes.c_ulong),
        ("dwOwningPid", ctypes.c_ulong),
    ]


def _is_windows() -> bool:
    return os.name == "nt"


def bridge_runtime_metadata_path(base_dir: Path) -> Path:
    return base_dir / _BRIDGE_RUNTIME_FILENAME


def write_bridge_runtime_metadata(
    *,
    base_dir: Path,
    port: int,
    pid: int,
    window_title: str,
    build_identity: dict[str, object] | None,
    running: bool,
    owner_kind: str = "qt_app",
    runtime_mode: str | None = None,
    workspace_id: str | None = None,
    browser_url: str | None = None,
) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = bridge_runtime_metadata_path(base_dir)
    payload = {
        "host": "127.0.0.1",
        "port": int(port),
        "pid": int(pid),
        "window_title": str(window_title or "").strip(),
        "build_identity": build_identity if isinstance(build_identity, dict) else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "running": bool(running),
        "owner_kind": str(owner_kind or "qt_app").strip() or "qt_app",
        "runtime_mode": str(runtime_mode or "").strip() or None,
        "workspace_id": str(workspace_id or "").strip() or None,
        "browser_url": str(browser_url or "").strip() or None,
    }
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp_path.replace(path)
    return path


def load_bridge_runtime_metadata(base_dir: Path) -> dict[str, object] | None:
    path = bridge_runtime_metadata_path(base_dir)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def clear_bridge_runtime_metadata(base_dir: Path) -> None:
    path = bridge_runtime_metadata_path(base_dir)
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _window_hwnd(window: object) -> int | None:
    win_id = getattr(window, "winId", None)
    if not callable(win_id):
        return None
    try:
        raw = win_id()
    except Exception:  # noqa: BLE001
        return None
    try:
        hwnd = int(raw)
    except (TypeError, ValueError):
        return None
    return hwnd if hwnd > 0 else None


def _show_window(hwnd: int, command: int) -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    return bool(user32.ShowWindow(ctypes.c_void_p(hwnd), command))


def _set_foreground_window(hwnd: int) -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    return bool(user32.SetForegroundWindow(ctypes.c_void_p(hwnd)))


def _get_foreground_window() -> int | None:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    hwnd = int(user32.GetForegroundWindow())
    return hwnd if hwnd > 0 else None


def _window_title(hwnd: int) -> str:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    length = int(user32.GetWindowTextLengthW(ctypes.c_void_p(hwnd)))
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    copied = int(user32.GetWindowTextW(ctypes.c_void_p(hwnd), buffer, length + 1))
    if copied <= 0:
        return ""
    return str(buffer.value[:copied]).strip()


def _flash_window(hwnd: int) -> bool:
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    info = _FLASHWINFO(
        cbSize=ctypes.sizeof(_FLASHWINFO),
        hwnd=ctypes.c_void_p(hwnd),
        dwFlags=_FLASHW_TRAY | _FLASHW_TIMERNOFG,
        uCount=3,
        dwTimeout=0,
    )
    return bool(user32.FlashWindowEx(ctypes.byref(info)))


def _call_if_present(window: object, method_name: str) -> None:
    method = getattr(window, method_name, None)
    if not callable(method):
        return
    try:
        method()
    except Exception:  # noqa: BLE001
        return


def _request_hwnd_attention(hwnd: int, *, restored: bool) -> WindowAttentionResult:
    try:
        if _show_window(hwnd, _SW_RESTORE):
            restored = True
    except Exception:  # noqa: BLE001
        return WindowAttentionResult(
            requested=True,
            restored=restored,
            focused=False,
            flashed=False,
            reason="show_window_failed",
        )

    try:
        if _set_foreground_window(hwnd):
            foreground_hwnd = _get_foreground_window()
            return WindowAttentionResult(
                requested=True,
                restored=restored,
                focused=foreground_hwnd == hwnd or foreground_hwnd is None,
                flashed=False,
                reason="foreground_set",
            )
    except Exception:  # noqa: BLE001
        return WindowAttentionResult(
            requested=True,
            restored=restored,
            focused=False,
            flashed=False,
            reason="set_foreground_failed",
        )

    foreground_hwnd = None
    try:
        foreground_hwnd = _get_foreground_window()
    except Exception:  # noqa: BLE001
        foreground_hwnd = None
    if foreground_hwnd == hwnd:
        return WindowAttentionResult(
            requested=True,
            restored=restored,
            focused=True,
            flashed=False,
            reason="already_foreground",
        )

    flashed = False
    try:
        flashed = _flash_window(hwnd)
    except Exception:  # noqa: BLE001
        flashed = False
    return WindowAttentionResult(
        requested=True,
        restored=restored,
        focused=False,
        flashed=flashed,
        reason="foreground_blocked" if flashed else "foreground_request_failed",
    )


def _visible_window_hwnds_for_pid(pid: int) -> list[int]:
    if not _is_windows():
        return []
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    enum_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    hwnds: list[int] = []

    @enum_proc_type
    def _callback(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        owner = int(user32.GetWindow(hwnd, 4))  # GW_OWNER
        if owner != 0:
            return True
        process_id = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
        if int(process_id.value) != pid:
            return True
        hwnds.append(int(hwnd))
        return True

    user32.EnumWindows(_callback, 0)
    return hwnds


def _legacy_bridge_owner_validation(*, bridge_port: int, fallback_reason: str) -> BridgeOwnerValidationResult:
    owner_pid = detect_listener_pid(bridge_port)
    if owner_pid is None:
        return BridgeOwnerValidationResult(
            ok=False,
            pid=None,
            hwnd=None,
            reason=fallback_reason,
            owner_kind="none",
        )

    hwnds = _visible_window_hwnds_for_pid(owner_pid)
    if not hwnds:
        return BridgeOwnerValidationResult(
            ok=False,
            pid=owner_pid,
            hwnd=None,
            reason=fallback_reason,
            owner_kind="external",
        )

    preferred_hwnd = None
    for hwnd in hwnds:
        title = _window_title(hwnd)
        if "legalpdf translate" in title.casefold():
            preferred_hwnd = hwnd
            break
    if preferred_hwnd is None:
        return BridgeOwnerValidationResult(
            ok=False,
            pid=owner_pid,
            hwnd=None,
            reason=fallback_reason,
            owner_kind="external",
        )

    return BridgeOwnerValidationResult(
        ok=True,
        pid=owner_pid,
        hwnd=preferred_hwnd,
        reason="legacy_bridge_owner_ready",
        owner_kind="qt_app",
    )


def parse_listener_pid_from_netstat(output: str, port: int) -> int | None:
    for raw_line in str(output or "").splitlines():
        match = _WINDOWS_NETSTAT_LISTEN_RE.match(raw_line)
        if match is None:
            continue
        if int(match.group("port")) != int(port):
            continue
        return int(match.group("pid"))
    return None


def _port_from_mib_dword(raw_port: int) -> int:
    return int(socket.ntohs(int(raw_port) & 0xFFFF))


def _detect_listener_pid_from_tcp_table(port: int) -> int | None:
    if not _is_windows():
        return None
    try:
        iphlpapi = ctypes.WinDLL("iphlpapi", use_last_error=True)
    except Exception:  # noqa: BLE001
        return None

    size = ctypes.c_ulong(0)
    try:
        result = iphlpapi.GetExtendedTcpTable(
            None,
            ctypes.byref(size),
            False,
            _AF_INET,
            _TCP_TABLE_OWNER_PID_LISTENER,
            0,
        )
    except Exception:  # noqa: BLE001
        return None
    if result not in (_NO_ERROR, _ERROR_INSUFFICIENT_BUFFER) or size.value <= 0:
        return None

    buffer = ctypes.create_string_buffer(size.value)
    try:
        result = iphlpapi.GetExtendedTcpTable(
            ctypes.byref(buffer),
            ctypes.byref(size),
            False,
            _AF_INET,
            _TCP_TABLE_OWNER_PID_LISTENER,
            0,
        )
    except Exception:  # noqa: BLE001
        return None
    if result != _NO_ERROR:
        return None

    payload = ctypes.string_at(buffer, size.value)
    if len(payload) < ctypes.sizeof(ctypes.c_ulong):
        return None
    entry_count = int(ctypes.c_ulong.from_buffer_copy(payload).value)
    row_size = ctypes.sizeof(_MIB_TCPROW_OWNER_PID)
    offset = ctypes.sizeof(ctypes.c_ulong)
    for _index in range(entry_count):
        if offset + row_size > len(payload):
            break
        row = _MIB_TCPROW_OWNER_PID.from_buffer_copy(payload, offset)
        offset += row_size
        if _port_from_mib_dword(row.dwLocalPort) != int(port):
            continue
        owning_pid = int(row.dwOwningPid)
        return owning_pid if owning_pid > 0 else None
    return None


def _detect_listener_pid_from_netstat(port: int) -> int | None:
    if not _is_windows():
        return None
    system_root = os.environ.get("SystemRoot", "").strip()
    netstat_candidates = [
        shutil.which("netstat.exe"),
        shutil.which("netstat"),
        str(Path(system_root) / "System32" / "netstat.exe") if system_root else "",
    ]
    netstat = next((candidate for candidate in netstat_candidates if candidate and Path(candidate).exists()), None)
    if netstat is None:
        return None
    try:
        completed = subprocess.run(
            [netstat, "-ano", "-p", "tcp"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except Exception:  # noqa: BLE001
        return None
    if completed.returncode != 0:
        return None
    return parse_listener_pid_from_netstat(completed.stdout, port)


def _pid_is_running(pid: int | None) -> bool:
    try:
        parsed = int(pid or 0)
    except (TypeError, ValueError):
        return False
    if parsed <= 0:
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


def detect_listener_pid(port: int) -> int | None:
    if not _is_windows():
        return None
    for attempt in range(3):
        owner_pid = _detect_listener_pid_from_tcp_table(port)
        if owner_pid is not None:
            return owner_pid
        owner_pid = _detect_listener_pid_from_netstat(port)
        if owner_pid is not None:
            return owner_pid
        if attempt < 2:
            time.sleep(0.1)
    return None


def validate_bridge_owner(*, bridge_port: int, base_dir: Path) -> BridgeOwnerValidationResult:
    if not _is_windows():
        return BridgeOwnerValidationResult(
            ok=False,
            pid=None,
            hwnd=None,
            reason="unsupported_platform",
            owner_kind="none",
        )
    if int(bridge_port) <= 0 or int(bridge_port) > 65535:
        return BridgeOwnerValidationResult(
            ok=False,
            pid=None,
            hwnd=None,
            reason="invalid_bridge_port",
            owner_kind="none",
        )

    payload = load_bridge_runtime_metadata(base_dir)
    if payload is None:
        return _legacy_bridge_owner_validation(
            bridge_port=bridge_port,
            fallback_reason="runtime_metadata_missing",
        )

    try:
        metadata_port = int(payload.get("port", 0))
        metadata_pid = int(payload.get("pid", 0))
    except (TypeError, ValueError):
        return _legacy_bridge_owner_validation(
            bridge_port=bridge_port,
            fallback_reason="runtime_metadata_invalid",
        )
    if metadata_port != int(bridge_port):
        return _legacy_bridge_owner_validation(
            bridge_port=bridge_port,
            fallback_reason="bridge_port_mismatch",
        )
    if not bool(payload.get("running", False)):
        return _legacy_bridge_owner_validation(
            bridge_port=bridge_port,
            fallback_reason="bridge_not_running",
        )
    if metadata_pid <= 0:
        return _legacy_bridge_owner_validation(
            bridge_port=bridge_port,
            fallback_reason="runtime_metadata_invalid",
        )
    owner_pid = detect_listener_pid(bridge_port)
    if owner_pid is None:
        if not _pid_is_running(metadata_pid):
            return _legacy_bridge_owner_validation(
                bridge_port=bridge_port,
                fallback_reason="bridge_owner_stale",
            )
        return BridgeOwnerValidationResult(
            ok=False,
            pid=metadata_pid,
            hwnd=None,
            reason="bridge_port_owner_unknown",
            owner_kind="external",
        )
    if owner_pid != metadata_pid:
        return _legacy_bridge_owner_validation(
            bridge_port=bridge_port,
            fallback_reason="bridge_port_owner_mismatch",
        )

    owner_kind = str(payload.get("owner_kind", "") or "").strip() or "qt_app"
    runtime_mode = str(payload.get("runtime_mode", "") or "").strip() or None
    workspace_id = str(payload.get("workspace_id", "") or "").strip() or None
    browser_url = str(payload.get("browser_url", "") or "").strip() or None

    if owner_kind == "browser_app":
        return BridgeOwnerValidationResult(
            ok=True,
            pid=metadata_pid,
            hwnd=None,
            reason="bridge_owner_ready",
            owner_kind="browser_app",
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            browser_url=browser_url,
        )

    hwnds = _visible_window_hwnds_for_pid(metadata_pid)
    if not hwnds:
        return BridgeOwnerValidationResult(
            ok=False,
            pid=metadata_pid,
            hwnd=None,
            reason="window_not_found",
            owner_kind=owner_kind,
            runtime_mode=runtime_mode,
            workspace_id=workspace_id,
            browser_url=browser_url,
        )

    return BridgeOwnerValidationResult(
        ok=True,
        pid=metadata_pid,
        hwnd=hwnds[0],
        reason="bridge_owner_ready",
        owner_kind=owner_kind,
        runtime_mode=runtime_mode,
        workspace_id=workspace_id,
        browser_url=browser_url,
    )


def focus_bridge_owner(*, bridge_port: int, base_dir: Path) -> BridgeFocusResult:
    validation = validate_bridge_owner(bridge_port=bridge_port, base_dir=base_dir)
    if validation.ok and validation.owner_kind == "browser_app":
        return BridgeFocusResult(
            ok=True,
            focused=False,
            flashed=False,
            reason="browser_tab_focus_delegated",
        )
    if not validation.ok or validation.hwnd is None:
        return BridgeFocusResult(ok=False, focused=False, flashed=False, reason=validation.reason)

    result = _request_hwnd_attention(validation.hwnd, restored=False)
    return BridgeFocusResult(
        ok=result.focused or result.flashed,
        focused=result.focused,
        flashed=result.flashed,
        reason=result.reason,
    )


def request_window_attention(window: object) -> WindowAttentionResult:
    if not _is_windows():
        return WindowAttentionResult(
            requested=False,
            restored=False,
            focused=False,
            flashed=False,
            reason="unsupported_platform",
        )

    restored = False
    is_minimized = False
    minimized_getter = getattr(window, "isMinimized", None)
    if callable(minimized_getter):
        try:
            is_minimized = bool(minimized_getter())
        except Exception:  # noqa: BLE001
            is_minimized = False

    if is_minimized:
        _call_if_present(window, "showNormal")
        restored = True
    else:
        _call_if_present(window, "show")

    _call_if_present(window, "raise_")
    _call_if_present(window, "activateWindow")

    hwnd = _window_hwnd(window)
    if hwnd is None:
        return WindowAttentionResult(
            requested=False,
            restored=restored,
            focused=False,
            flashed=False,
            reason="window_handle_unavailable",
        )
    return _request_hwnd_attention(hwnd, restored=restored)
