from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "src" / "legalpdf_translate" / "shadow_web" / "static"
DEFAULT_NODE_TIMEOUT_SECONDS = 20


def _node_executable() -> str:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is required for browser module probe coverage.")
    return node


def _prepare_browser_esm_workspace() -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
    temp_dir = tempfile.TemporaryDirectory(prefix="legalpdf-browser-esm-")
    workspace_root = Path(temp_dir.name)
    static_root = workspace_root / "static"
    shutil.copytree(STATIC_DIR, static_root)
    (workspace_root / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
    return temp_dir, workspace_root, static_root


def _run_node_probe(script: str, *, cwd: Path, timeout_seconds: int) -> str:
    node = _node_executable()
    try:
        completed = subprocess.run(
            [node, "--input-type=module", "-"],
            input=script,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_seconds,
            cwd=cwd,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout or ""
        stderr = error.stderr or ""
        pytest.fail(
            f"Node probe timed out after {timeout_seconds}s.\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}",
            pytrace=False,
        )
    if completed.returncode != 0:
        pytest.fail(
            f"Node probe failed with exit code {completed.returncode}.\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}",
            pytrace=False,
        )
    return completed.stdout


def run_browser_esm_json_probe(
    script_template: str,
    module_placeholders: dict[str, str],
    *,
    timeout_seconds: int = DEFAULT_NODE_TIMEOUT_SECONDS,
) -> object:
    temp_dir, workspace_root, static_root = _prepare_browser_esm_workspace()
    try:
        script = script_template
        for placeholder, relative_path in module_placeholders.items():
            module_url = (static_root / relative_path).resolve().as_uri()
            script = script.replace(placeholder, json.dumps(module_url))
        stdout = _run_node_probe(script, cwd=workspace_root, timeout_seconds=timeout_seconds)
    finally:
        temp_dir.cleanup()
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as error:
        pytest.fail(
            f"Node probe did not emit valid JSON: {error}\nSTDOUT:\n{stdout}",
            pytrace=False,
        )
