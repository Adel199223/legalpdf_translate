"""Run separately under the reviewed, environment-scrubbed OS-lock test launcher.

This single-purpose synthetic test intentionally starts two bounded Python
children. It does not belong in an offline harness that forbids subprocesses.
Children import only the lock module; there is no app/provider/native activity.
"""
from pathlib import Path
import subprocess
import sys

import legalpdf_translate.run_workspace_lock as locking
from legalpdf_translate.run_workspace_lock import run_workspace_slot


_CHILD = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from legalpdf_translate.run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
try:
    with run_workspace_slot(Path(sys.argv[2])):
        print('acquired', flush=True)
except RunWorkspaceBusy:
    print('busy', flush=True)
    raise SystemExit(73)
"""


def test_separate_python_process_contends_on_actual_os_lock(tmp_path):
    source_root = str(Path(locking.__file__).resolve().parents[1])
    command = [sys.executable, "-I", "-B", "-c", _CHILD, source_root, str(tmp_path)]
    with run_workspace_slot(tmp_path):
        busy = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        assert busy.returncode == 73 and busy.stdout.strip() == "busy" and busy.stderr == ""
    available = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    assert available.returncode == 0 and available.stdout.strip() == "acquired" and available.stderr == ""
