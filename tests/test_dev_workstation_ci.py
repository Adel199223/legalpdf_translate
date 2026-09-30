"""Keep runtime-sensitive CI jobs aligned with the workstation version files."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "python-package.yml"


def _job(job_id: str) -> str:
    # These assertions intentionally cover the repository's simple job layout;
    # they do not add a YAML dependency to the locked application environment.
    match = re.search(
        rf"(?ms)^  {re.escape(job_id)}:\n(.*?)(?=^  [a-z_]+:\n|\Z)",
        WORKFLOW.read_text(encoding="utf-8"),
    )
    assert match is not None, f"Missing CI job: {job_id}"
    return match.group(1)


def _step(job: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^      - name: {re.escape(name)}\n(.*?)(?=^      - |\Z)", job
    )
    assert match is not None, f"Missing CI step: {name}"
    return match.group(0)


@pytest.mark.parametrize("filename", [".node-version", ".dart-version"])
def test_runtime_files_pin_exact_releases(filename: str):
    version = (ROOT / filename).read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), filename


@pytest.mark.parametrize("job_id", ["windows_contracts", "python_shards"])
def test_windows_test_jobs_supply_pinned_node_before_browser_probes(job_id: str):
    job = _job(job_id)
    node = _step(job, "Setup Node")
    assert "uses: actions/setup-node@v7\n" in node
    assert "node-version-file: .node-version\n" in node
    assert not re.search(r"^\s+node-version:", node, re.MULTILINE)
    assert job.index(node) < job.index("Install locked environment")
    test_step = "Targeted Core Regressions" if job_id == "windows_contracts" else "Full Tests (one exhaustive partition)"
    assert job.index(node) < job.index(test_step)


@pytest.mark.parametrize("job_id", ["windows_contracts", "docs_tooling_contracts"])
def test_docs_jobs_pass_the_dart_file_pin_to_setup_before_validation(job_id: str):
    job = _job(job_id)
    read = _step(job, "Read Dart version")
    setup = _step(job, "Setup Dart")
    assert "id: dart_version\n" in read
    assert ".dart-version" in read and "GITHUB_OUTPUT" in read
    assert "uses: dart-lang/setup-dart@v1\n" in setup
    assert "sdk: ${{ steps.dart_version.outputs.sdk }}\n" in setup
    assert job.index(read) < job.index(setup) < job.index("Validate Agent Docs")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PowerShell output contract")
def test_windows_dart_pin_read_preserves_github_output_and_emits_utf8(tmp_path: Path):
    read = _step(_job("windows_contracts"), "Read Dart version")
    assert "shell: powershell\n" in read
    command = textwrap.dedent(read.split("run: |\n", 1)[1])
    pin = (ROOT / ".dart-version").read_text(encoding="utf-8").strip()
    (tmp_path / ".dart-version").write_bytes((pin + "\r\n").encode("utf-8"))
    output = tmp_path / "step output.txt"
    output.write_text("existing=preserved\n", encoding="utf-8")
    env = os.environ.copy()
    env["GITHUB_OUTPUT"] = str(output)
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.read_text(encoding="utf-8-sig").splitlines() == [
        "existing=preserved", f"sdk={pin}"
    ]
