from __future__ import annotations

import pathlib
import subprocess
import sys


DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000


def main() -> int:
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    runtime = repo_root.parent / "legalpdf_translate" / ".venv311" / "Scripts" / "pythonw.exe"
    log_dir = repo_root / "tmp"
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = log_dir / "browser_app_8877.spawned.out.log"
    stderr_path = log_dir / "browser_app_8877.spawned.err.log"

    with stdout_path.open("ab", buffering=0) as stdout_handle, stderr_path.open("ab", buffering=0) as stderr_handle:
        proc = subprocess.Popen(
            [str(runtime), "-m", "legalpdf_translate.shadow_web.server", "--port", "8877"],
            cwd=str(repo_root),
            stdin=subprocess.DEVNULL,
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            close_fds=True,
        )
    print(proc.pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
