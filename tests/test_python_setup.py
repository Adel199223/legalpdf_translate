from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows setup script")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "setup_python311_env.ps1"


@pytest.fixture
def setup_sandbox(tmp_path: Path):
    repo = tmp_path / "checkout with spaces"
    (repo / "scripts").mkdir(parents=True)
    shutil.copyfile(SCRIPT, repo / "scripts" / SCRIPT.name)
    (repo / ".python-version").write_text("3.11.9\n", encoding="utf-8")
    (repo / "uv.lock").write_text("test lock\n", encoding="utf-8")
    tools = tmp_path / "fake tools"
    tools.mkdir()
    state = tmp_path / "state.json"
    log = tmp_path / "calls.jsonl"
    fake = tools / "fake_uv.py"
    fake.write_text('''import json, os, pathlib, sys
state = json.loads(pathlib.Path(os.environ["UV_SETUP_TEST_STATE"]).read_text())
args = sys.argv[1:]
with open(state["log"], "a", encoding="utf-8") as stream:
    stream.write(json.dumps({"args": args, "target": os.environ.get("UV_PROJECT_ENVIRONMENT")}) + "\\n")
stage = args[0]
if stage == "sync":
    target = pathlib.Path(os.environ["UV_PROJECT_ENVIRONMENT"])
    (target / "Scripts").mkdir(parents=True, exist_ok=True)
    (target / "Scripts" / "python.exe").write_text("fake interpreter")
    (target / "pyvenv.cfg").write_text("fake venv")
if state.get("failure") == stage:
    sys.exit(35)
if stage == "python":
    print(state["python"])
if stage == "run" and "import sys; print(sys.version.split()[0])" in args:
    print(state.get("existing_version", "3.11.9"))
''', encoding="utf-8")
    (tools / "uv.cmd").write_text(
        f'@echo off\n"{sys.executable}" "{fake}" %*\nexit /b %errorlevel%\n', encoding="utf-8"
    )
    state.write_text(json.dumps({"log": str(log), "python": sys.executable}), encoding="utf-8")

    def run(*args: str, failure: str | None = None, existing_version: str = "3.11.9"):
        config = json.loads(state.read_text(encoding="utf-8"))
        config["failure"] = failure
        config["existing_version"] = existing_version
        state.write_text(json.dumps(config), encoding="utf-8")
        env = os.environ.copy()
        env["PATH"] = str(tools) + os.pathsep + env["PATH"]
        env["UV_SETUP_TEST_STATE"] = str(state)
        env["UV_PROJECT_ENVIRONMENT"] = "caller-environment"
        quote = lambda value: "'" + str(value).replace("'", "''") + "'"
        command = (
            "$setupFailed=$false; try { & " + quote(repo / "scripts" / SCRIPT.name)
            + " " + " ".join(quote(arg) for arg in args)
            + " } catch { Write-Output $_.Exception.Message; $setupFailed=$true }; "
            + "Write-Output ('RESTORED_ENV=' + $env:UV_PROJECT_ENVIRONMENT); "
            + "Write-Output ('RESTORED_CWD=' + (Get-Location).Path); "
            + "if ($setupFailed) { exit 1 }"
        )
        # Switches must remain tokens; positional argument values are quoted.
        for switch in ("-Recreate", "-VenvName"):
            command = command.replace(quote(switch), switch)
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=tmp_path, env=env, text=True, capture_output=True, timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []
        return result, calls

    return repo, run


def _existing_environment(repo: Path) -> Path:
    env = repo / ".venv311"
    env.mkdir()
    (env / "pyvenv.cfg").write_text("original config", encoding="utf-8")
    (env / "keep.txt").write_text("original environment", encoding="utf-8")
    (env / "Scripts").mkdir()
    (env / "Scripts" / "python.exe").write_text("original interpreter", encoding="utf-8")
    return env


def test_success_uses_locked_versions_and_restores_caller_state(setup_sandbox):
    repo, run = setup_sandbox
    result, calls = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert [call["args"][0] for call in calls] == ["python", "lock", "sync", "pip", "run"]
    sync = calls[2]
    assert sync["target"] == str(repo / ".venv311")
    assert "--locked" in sync["args"] and "--inexact" in sync["args"]
    assert "RESTORED_ENV=caller-environment" in result.stdout
    assert f"RESTORED_CWD={repo.parent}" in result.stdout
    assert "Done. Activate" in result.stdout


@pytest.mark.parametrize("stage", ["python", "lock", "sync", "pip", "run"])
def test_native_failure_stops_before_later_commands(setup_sandbox, stage):
    _, run = setup_sandbox
    result, calls = run(failure=stage)
    assert result.returncode != 0
    assert calls[-1]["args"][0] == stage
    assert "failed (exit 35)" in result.stdout
    assert "Done. Activate" not in result.stdout
    assert "RESTORED_ENV=caller-environment" in result.stdout


@pytest.mark.parametrize("name", ["..", "../outside", ".venv311/../src", "src", "C:\\outside"])
def test_invalid_environment_target_is_rejected_before_any_command(setup_sandbox, name):
    repo, run = setup_sandbox
    result, calls = run("-VenvName", name, "-Recreate")
    assert result.returncode != 0
    assert calls == []
    assert not (repo / ".venv311").exists()


def test_recreate_preserves_backup_on_success(setup_sandbox):
    repo, run = setup_sandbox
    original = _existing_environment(repo)
    result, _ = run("-Recreate")
    assert result.returncode == 0, result.stdout + result.stderr
    backups = list(repo.glob(".venv311.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "keep.txt").read_text() == "original environment"
    assert not (original / "keep.txt").exists()


@pytest.mark.parametrize("stage", ["sync", "pip", "run"])
def test_failed_recreation_restores_original_and_preserves_failed_candidate(setup_sandbox, stage):
    repo, run = setup_sandbox
    original = _existing_environment(repo)
    result, _ = run("-Recreate", failure=stage)
    assert result.returncode != 0
    assert (original / "keep.txt").read_text() == "original environment"
    assert (original / "pyvenv.cfg").read_text() == "original config"
    assert len(list(repo.glob(".venv311.failed-*"))) == 1
    assert not list(repo.glob(".venv311.backup-*"))


def test_lock_failure_does_not_move_existing_environment(setup_sandbox):
    repo, run = setup_sandbox
    original = _existing_environment(repo)
    result, _ = run("-Recreate", failure="lock")
    assert result.returncode != 0
    assert (original / "keep.txt").is_file()
    assert not list(repo.glob(".venv311.backup-*"))


def test_existing_unrelated_directory_is_not_recreated(setup_sandbox):
    repo, run = setup_sandbox
    target = repo / ".venv311"
    target.mkdir()
    (target / "important.txt").write_text("keep", encoding="utf-8")
    result, calls = run("-Recreate")
    assert result.returncode != 0
    assert calls == []
    assert (target / "important.txt").read_text() == "keep"


def test_existing_environment_and_extras_are_preserved_without_recreate(setup_sandbox):
    repo, run = setup_sandbox
    original = _existing_environment(repo)
    result, calls = run()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (original / "keep.txt").read_text() == "original environment"
    assert "--inexact" in next(call["args"] for call in calls if call["args"][0] == "sync")
    assert not list(repo.glob(".venv311.backup-*"))


def test_wrong_existing_python_is_not_automatically_replaced(setup_sandbox):
    repo, run = setup_sandbox
    original = _existing_environment(repo)
    result, calls = run(existing_version="3.12.10")
    assert result.returncode != 0
    assert "Use -Recreate" in result.stdout
    assert not any(call["args"][0] == "sync" for call in calls)
    assert (original / "keep.txt").is_file()


@pytest.mark.parametrize("missing", [".python-version", "uv.lock"])
def test_missing_tracked_inputs_fail_before_any_command(setup_sandbox, missing):
    repo, run = setup_sandbox
    (repo / missing).unlink()
    result, calls = run()
    assert result.returncode != 0
    assert calls == []


def test_linked_environment_is_rejected_before_recreate(setup_sandbox):
    repo, run = setup_sandbox
    outside = repo.parent / "outside environment"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link = repo / ".venv311"
    result = subprocess.run(
        ["cmd.exe", "/c", "mklink", "/J", str(link), str(outside)],
        text=True, capture_output=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    result, calls = run("-Recreate")
    assert result.returncode != 0
    assert calls == []
    assert (outside / "keep.txt").read_text() == "keep"
