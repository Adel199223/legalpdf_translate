from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser


DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000
DEFAULT_PORT = 8877
DEFAULT_MODE = "live"
DEFAULT_WORKSPACE = "workspace-1"
DEFAULT_UI = "qt"
DEFAULT_VIEW = "new-job"
READY_TIMEOUT_SECONDS = 35.0
READY_POLL_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 2.0
SCRIPT_PATH = Path(__file__).resolve()
REPO_ROOT = SCRIPT_PATH.parents[1]
SRC_ROOT = REPO_ROOT / "src"
SHADOW_HOST = "127.0.0.1"
APP_DATA_DIR_NAME = "LegalPDFTranslate"
GMAIL_WORKSPACE_ID = "gmail-intake"
if SRC_ROOT.exists():
    src_text = str(SRC_ROOT)
    if src_text not in sys.path:
        sys.path.insert(0, src_text)

try:
    from legalpdf_translate.gmail_window_trace import (  # type: ignore
        update_launch_session_state as _trace_update_launch_session_state,
    )
except Exception:  # pragma: no cover - degraded launcher fallback
    _trace_update_launch_session_state = None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Launch the local browser app in detached mode.")
    parser.add_argument("--mode", choices=("live", "shadow"), default=DEFAULT_MODE)
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--ui", choices=("qt", "legacy"), default=DEFAULT_UI)
    parser.add_argument(
        "--launch-session-id",
        default="",
        help="Correlated launch session identifier for Gmail cold-start diagnostics.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Start or reuse the browser app server without opening a browser tab.",
    )
    return parser


def _python_candidates(repo_root: Path) -> list[Path]:
    return [
        repo_root / ".venv311" / "Scripts" / "python.exe",
        repo_root / ".venv" / "Scripts" / "python.exe",
        repo_root / ".venv311" / "Scripts" / "pythonw.exe",
        repo_root / ".venv" / "Scripts" / "pythonw.exe",
        _absolute_path_noresolve(Path(sys.executable)),
    ]


def _absolute_path_noresolve(path: Path) -> Path:
    # Preserve Windows venv launcher identity. Path.resolve() can collapse
    # a venv python[w].exe back to the base interpreter, which would make the
    # detached browser app relaunch under the wrong runtime.
    return Path(os.path.abspath(str(path.expanduser())))


def _python_runtime(repo_root: Path) -> Path:
    for candidate in _python_candidates(repo_root):
        if candidate.exists():
            return _absolute_path_noresolve(candidate)
    raise SystemExit(
        "No Python runtime found for the browser app launcher. "
        "Expected .venv311/Scripts/pythonw.exe, python.exe, or the current interpreter."
    )


def _launcher_env(repo_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    pythonpath = str((repo_root / "src").resolve())
    existing = str(env.get("PYTHONPATH", "") or "").strip()
    env["PYTHONPATH"] = pythonpath if existing == "" else os.pathsep.join([pythonpath, existing])
    return env


def _default_view(*, workspace: str, ui: str) -> str:
    if str(ui) == "legacy":
        return "dashboard"
    return "gmail-intake" if str(workspace).strip() == "gmail-intake" else DEFAULT_VIEW


def _browser_url(*, port: int, mode: str, workspace: str, ui: str = DEFAULT_UI) -> str:
    params: dict[str, str] = {
        "mode": str(mode),
        "workspace": str(workspace),
    }
    if str(ui) == "legacy":
        params["ui"] = "legacy"
    query = urllib.parse.urlencode(params)
    return f"http://{SHADOW_HOST}:{int(port)}/?{query}#{_default_view(workspace=str(workspace), ui=str(ui))}"


def _probe_browser_url(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            status = int(getattr(response, "status", 0))
            return 200 <= status < 500
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        return False


def _wait_until_ready(url: str, *, timeout_seconds: float = READY_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + max(timeout_seconds, 0.0)
    while time.monotonic() < deadline:
        if _probe_browser_url(url):
            return True
        time.sleep(READY_POLL_SECONDS)
    return False


def _normalize_token(value: object) -> str:
    return str(value or "").strip()


def _is_gmail_workspace(workspace: object) -> bool:
    return _normalize_token(workspace) == GMAIL_WORKSPACE_ID


def _legalpdf_app_data_dir() -> Path:
    appdata = _normalize_token(os.environ.get("APPDATA"))
    if appdata != "":
        return Path(appdata).expanduser().resolve() / APP_DATA_DIR_NAME
    return (Path.home() / ".legalpdf_translate" / APP_DATA_DIR_NAME).expanduser().resolve()


def _update_launch_session(launch_session_id: str, **fields: object) -> None:
    if _trace_update_launch_session_state is None:
        return
    session_id = _normalize_token(launch_session_id)
    if session_id == "":
        return
    try:
        _trace_update_launch_session_state(
            _legalpdf_app_data_dir(),
            launch_session_id=session_id,
            **fields,
        )
    except Exception:
        return


def _open_browser(url: str, *, workspace: str = DEFAULT_WORKSPACE, launch_session_id: str = "") -> bool:
    if _is_gmail_workspace(workspace):
        _update_launch_session(
            _normalize_token(launch_session_id),
            browser_launch_status="server_only",
            browser_launch_reason="extension_browser_surface_owner",
            launched_browser_pid=0,
            launched_browser_path="",
            launched_browser_user_data_dir="",
            launched_browser_profile="",
            launched_browser_command="",
        )
        return False
    startfile = getattr(os, "startfile", None)
    if callable(startfile):
        try:
            startfile(url)
            return True
        except OSError:
            pass
    try:
        return bool(webbrowser.open(url, new=1))
    except webbrowser.Error:
        return False


def _spawn_server(*, repo_root: Path, runtime: Path, port: int) -> int:
    log_dir = repo_root / "tmp"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / f"browser_app_{int(port)}.spawned.out.log"
    stderr_path = log_dir / f"browser_app_{int(port)}.spawned.err.log"
    with stdout_path.open("ab", buffering=0) as stdout_handle, stderr_path.open(
        "ab", buffering=0
    ) as stderr_handle:
        proc = subprocess.Popen(
            [
                str(runtime),
                "-m",
                "legalpdf_translate.shadow_web.server",
                "--port",
                str(int(port)),
            ],
            cwd=str(repo_root),
            env=_launcher_env(repo_root),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            close_fds=True,
        )
    return int(proc.pid)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = REPO_ROOT
    runtime = _python_runtime(repo_root)
    target_url = _browser_url(
        port=int(args.port),
        mode=str(args.mode),
        workspace=str(args.workspace),
        ui=str(args.ui),
    )

    if not _probe_browser_url(target_url):
        pid = _spawn_server(repo_root=repo_root, runtime=runtime, port=int(args.port))
        if not _wait_until_ready(target_url):
            raise SystemExit(
                f"Browser app did not become ready on {target_url}. "
                f"Check tmp/browser_app_{int(args.port)}.spawned.err.log for details."
            )
        print(pid)
    else:
        print("already-running")

    if not bool(args.no_open):
        opened = _open_browser(
            target_url,
            workspace=str(args.workspace),
            launch_session_id=str(args.launch_session_id or ""),
        )
        if not opened:
            print(f"Browser app is running at: {target_url}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
