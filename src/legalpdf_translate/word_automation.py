"""Windows Word automation helpers used by the Qt app."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from shutil import which
import subprocess


@dataclass(frozen=True, slots=True)
class WordAutomationResult:
    ok: bool
    action: str
    message: str
    stdout: str = ""
    stderr: str = ""
    command: tuple[str, ...] = ()


def _is_windows_host() -> bool:
    return os.name == "nt"


def _resolve_powershell_path() -> str | None:
    if not _is_windows_host():
        return None
    system_root = os.environ.get("SystemRoot", r"C:\Windows").strip() or r"C:\Windows"
    preferred = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if preferred.exists():
        return str(preferred)
    discovered = which("powershell.exe") or which("powershell")
    if discovered:
        return discovered
    return None


def _quote_powershell_single(value: str) -> str:
    return value.replace("'", "''")


def _build_word_powershell_script(docx_path: Path, *, align_right_and_save: bool) -> str:
    resolved = str(docx_path.expanduser().resolve())
    quoted = _quote_powershell_single(resolved)
    action_block = ""
    if align_right_and_save:
        action_block = "\n".join(
            [
                "$doc.Range().ParagraphFormat.Alignment = 2",
                "$doc.Save()",
            ]
        )
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$target = [System.IO.Path]::GetFullPath('{quoted}')",
            "$word = $null",
            "try {",
            "    $word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')",
            "} catch {",
            "}",
            "if ($null -eq $word) {",
            "    $word = New-Object -ComObject Word.Application",
            "}",
            "$word.Visible = $true",
            "$doc = $null",
            "foreach ($candidate in @($word.Documents)) {",
            "    if ([string]::Equals($candidate.FullName, $target, [System.StringComparison]::OrdinalIgnoreCase)) {",
            "        $doc = $candidate",
            "        break",
            "    }",
            "}",
            "if ($null -eq $doc) {",
            "    $doc = $word.Documents.Open($target)",
            "}",
            "$doc.Activate()",
            "$word.Activate()",
            action_block,
            "Write-Output 'OK'",
        ]
    )


def _build_powershell_command(docx_path: Path, *, align_right_and_save: bool) -> tuple[str, ...] | None:
    powershell = _resolve_powershell_path()
    if powershell is None:
        return None
    script = _build_word_powershell_script(docx_path, align_right_and_save=align_right_and_save)
    return (
        powershell,
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    )


def _run_word_action(docx_path: Path, *, align_right_and_save: bool) -> WordAutomationResult:
    action = "align_right_and_save" if align_right_and_save else "open"
    resolved = docx_path.expanduser().resolve()
    if not _is_windows_host():
        return WordAutomationResult(
            ok=False,
            action=action,
            message="Word automation is available only on Windows.",
        )
    if not resolved.exists():
        return WordAutomationResult(
            ok=False,
            action=action,
            message=f"DOCX not found: {resolved}",
        )
    command = _build_powershell_command(resolved, align_right_and_save=align_right_and_save)
    if command is None:
        return WordAutomationResult(
            ok=False,
            action=action,
            message="PowerShell is unavailable for Word automation.",
        )
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=20,
            creationflags=creationflags,
        )
    except Exception as exc:  # noqa: BLE001
        return WordAutomationResult(
            ok=False,
            action=action,
            message=str(exc),
            command=command,
        )
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if completed.returncode != 0:
        return WordAutomationResult(
            ok=False,
            action=action,
            message=stderr or stdout or "Word automation failed.",
            stdout=stdout,
            stderr=stderr,
            command=command,
        )
    success_message = "Word document opened." if not align_right_and_save else "Word document aligned right and saved."
    return WordAutomationResult(
        ok=True,
        action=action,
        message=success_message,
        stdout=stdout,
        stderr=stderr,
        command=command,
    )


def open_docx_in_word(docx_path: Path) -> WordAutomationResult:
    return _run_word_action(docx_path, align_right_and_save=False)


def align_right_and_save_docx_in_word(docx_path: Path) -> WordAutomationResult:
    return _run_word_action(docx_path, align_right_and_save=True)
