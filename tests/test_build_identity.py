from __future__ import annotations

import subprocess
from pathlib import Path

from legalpdf_translate import build_identity


def test_resolve_wsl_executable_falls_back_to_system32(monkeypatch, tmp_path: Path) -> None:
    system_root = tmp_path / "Windows"
    wsl_exe = system_root / "System32" / "wsl.exe"
    wsl_exe.parent.mkdir(parents=True)
    wsl_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(build_identity.shutil, "which", lambda _name: None)
    monkeypatch.setenv("SystemRoot", str(system_root))

    assert build_identity._resolve_wsl_executable() == str(wsl_exe)


def test_run_git_proc_uses_system32_wsl_when_which_is_missing(
    monkeypatch, tmp_path: Path
) -> None:
    system_root = tmp_path / "Windows"
    wsl_exe = system_root / "System32" / "wsl.exe"
    wsl_exe.parent.mkdir(parents=True)
    wsl_exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(build_identity.shutil, "which", lambda _name: None)
    monkeypatch.setenv("SystemRoot", str(system_root))

    calls: list[list[str]] = []

    def fake_run(
        args: list[str],
        *,
        text: bool,
        capture_output: bool,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                args=args,
                returncode=128,
                stdout="",
                stderr="fatal: not a git repository: /mnt/c/Users/FA507/.codex/legalpdf_translate/.git/worktrees/legalpdf_translate_gmail_intake\n",
            )
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="feat/gmail-intake-batch-reply\n",
            stderr="",
        )

    monkeypatch.setattr(build_identity.subprocess, "run", fake_run)

    repo = Path(r"C:\Users\FA507\.codex\legalpdf_translate_gmail_intake")
    result = build_identity._run_git_proc(repo, "symbolic-ref", "--short", "-q", "HEAD")

    assert result.returncode == 0
    assert result.stdout == "feat/gmail-intake-batch-reply\n"
    assert calls[0] == [
        "git",
        "-C",
        str(repo),
        "symbolic-ref",
        "--short",
        "-q",
        "HEAD",
    ]
    assert calls[1] == [
        str(wsl_exe),
        "--exec",
        "git",
        "-C",
        "/mnt/c/Users/FA507/.codex/legalpdf_translate_gmail_intake",
        "symbolic-ref",
        "--short",
        "-q",
        "HEAD",
    ]
