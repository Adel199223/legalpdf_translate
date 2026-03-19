"""Windows Word automation helpers used by the Qt app."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from shutil import which
import subprocess
import time


@dataclass(frozen=True, slots=True)
class WordAutomationResult:
    ok: bool
    action: str
    message: str
    stdout: str = ""
    stderr: str = ""
    command: tuple[str, ...] = ()
    failure_code: str = ""
    details: str = ""
    elapsed_ms: int = 0


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


def _normalize_process_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


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
        "-Sta",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    )


def _build_pdf_export_powershell_script(docx_path: Path, pdf_path: Path) -> str:
    resolved_docx = str(docx_path.expanduser().resolve())
    resolved_pdf = str(pdf_path.expanduser().resolve())
    quoted_docx = _quote_powershell_single(resolved_docx)
    quoted_pdf = _quote_powershell_single(resolved_pdf)
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "function Invoke-WithRetry {",
            "    param(",
            "        [scriptblock]$Action,",
            "        [int]$Attempts = 5,",
            "        [int]$DelayMs = 300",
            "    )",
            "    for ($attempt = 1; $attempt -le $Attempts; $attempt++) {",
            "        try {",
            "            return & $Action",
            "        } catch {",
            "            if ($attempt -ge $Attempts) {",
            "                throw",
            "            }",
            "            Start-Sleep -Milliseconds $DelayMs",
            "        }",
            "    }",
            "}",
            f"$target = [System.IO.Path]::GetFullPath('{quoted_docx}')",
            f"$pdfPath = [System.IO.Path]::GetFullPath('{quoted_pdf}')",
            "$word = $null",
            "$doc = $null",
            "$openedDoc = $false",
            "try {",
            "    $word = Invoke-WithRetry { New-Object -ComObject Word.Application }",
            "    $word.Visible = $false",
            "    Invoke-WithRetry { $null = $word.Documents.Count }",
            "    $doc = Invoke-WithRetry { $word.Documents.Open($target, $false, $true) }",
            "    $openedDoc = $true",
            "    $doc.Activate()",
            "    $wdExportFormatPDF = 17",
            "    Invoke-WithRetry { $doc.ExportAsFixedFormat($pdfPath, $wdExportFormatPDF) }",
            "    Write-Output 'OK'",
            "} finally {",
            "    if ($null -ne $doc -and $openedDoc) {",
            "        try {",
            "            Invoke-WithRetry { $doc.Close([ref]$false) }",
            "        } catch {",
            "        }",
            "    }",
            "    if ($null -ne $word) {",
            "        try {",
            "            Invoke-WithRetry { $word.Quit() }",
            "        } catch {",
            "        }",
            "    }",
            "}",
        ]
    )


def _build_pdf_export_powershell_command(docx_path: Path, pdf_path: Path) -> tuple[str, ...] | None:
    powershell = _resolve_powershell_path()
    if powershell is None:
        return None
    script = _build_pdf_export_powershell_script(docx_path, pdf_path)
    return (
        powershell,
        "-Sta",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
    )


def _build_pdf_preflight_powershell_script() -> str:
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            "$word = $null",
            "try {",
            "    $word = New-Object -ComObject Word.Application",
            "    $word.Visible = $false",
            "    $null = $word.Documents.Count",
            "    Write-Output 'OK'",
            "} finally {",
            "    if ($null -ne $word) {",
            "        try {",
            "            $word.Quit()",
            "        } catch {",
            "        }",
            "    }",
            "}",
        ]
    )


def _build_pdf_preflight_powershell_command() -> tuple[str, ...] | None:
    powershell = _resolve_powershell_path()
    if powershell is None:
        return None
    return (
        powershell,
        "-Sta",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        _build_pdf_preflight_powershell_script(),
    )


def _classify_pdf_failure(raw_message: str, *, action: str) -> str:
    lowered = raw_message.casefold()
    if "timed out" in lowered:
        return "timeout"
    if "powershell" in lowered and "unavailable" in lowered:
        return "powershell_missing"
    if (
        "class not registered" in lowered
        or "invalid class string" in lowered
        or "cannot create activex component" in lowered
        or "no com class identified" in lowered
    ):
        return "word_unavailable"
    if (
        "server execution failed" in lowered
        or "co_e_server_exec_failure" in lowered
        or "0x80080005" in lowered
        or "retrieving the com class factory" in lowered
    ):
        return "com_launch_failed"
    if action == "export_pdf":
        return "export_failed"
    return "unknown"


def _pdf_failure_message(failure_code: str) -> str:
    return {
        "powershell_missing": "PowerShell is unavailable for Word PDF export.",
        "word_unavailable": "Microsoft Word is unavailable for PDF export on this computer.",
        "com_launch_failed": "Microsoft Word could not be started for PDF export.",
        "timeout": "Word PDF export timed out.",
        "export_failed": "Microsoft Word could not export the PDF.",
        "unknown": "Word PDF export failed.",
    }.get(failure_code, "Word PDF export failed.")


def _build_pdf_failure_details(
    *,
    failure_code: str,
    elapsed_ms: int,
    raw_message: str,
    stdout: str,
    stderr: str,
    command: tuple[str, ...],
) -> str:
    lines = [
        f"Failure code: {failure_code or 'unknown'}",
        f"Elapsed: {elapsed_ms} ms",
    ]
    if command:
        lines.append(f"Host command: {command[0]}")
    if raw_message:
        lines.extend(["", "Raw diagnostic:", raw_message])
    if stderr and stderr != raw_message:
        lines.extend(["", "stderr:", stderr])
    if stdout and stdout != raw_message:
        lines.extend(["", "stdout:", stdout])
    return "\n".join(lines).strip()


def _build_pdf_failure_result(
    *,
    action: str,
    raw_message: str,
    stdout: str = "",
    stderr: str = "",
    command: tuple[str, ...] = (),
    elapsed_ms: int = 0,
    failure_code: str | None = None,
) -> WordAutomationResult:
    resolved_code = failure_code or _classify_pdf_failure(raw_message, action=action)
    return WordAutomationResult(
        ok=False,
        action=action,
        message=_pdf_failure_message(resolved_code),
        stdout=stdout,
        stderr=stderr,
        command=command,
        failure_code=resolved_code,
        details=_build_pdf_failure_details(
            failure_code=resolved_code,
            elapsed_ms=elapsed_ms,
            raw_message=raw_message,
            stdout=stdout,
            stderr=stderr,
            command=command,
        ),
        elapsed_ms=elapsed_ms,
    )


def _run_command(
    *,
    action: str,
    command: tuple[str, ...],
    success_message: str,
    timeout_seconds: float = 20,
) -> WordAutomationResult:
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        stdout = _normalize_process_text(getattr(exc, "stdout", ""))
        stderr = _normalize_process_text(getattr(exc, "stderr", ""))
        raw_message = stderr or stdout or str(exc)
        if action in {"export_pdf", "pdf_preflight"}:
            return _build_pdf_failure_result(
                action=action,
                raw_message=raw_message,
                stdout=stdout,
                stderr=stderr,
                command=command,
                elapsed_ms=elapsed_ms,
                failure_code="timeout",
            )
        return WordAutomationResult(
            ok=False,
            action=action,
            message=str(exc),
            stdout=stdout,
            stderr=stderr,
            command=command,
            elapsed_ms=elapsed_ms,
        )
    except Exception as exc:  # noqa: BLE001
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        raw_message = str(exc)
        if action in {"export_pdf", "pdf_preflight"}:
            return _build_pdf_failure_result(
                action=action,
                raw_message=raw_message,
                command=command,
                elapsed_ms=elapsed_ms,
            )
        return WordAutomationResult(
            ok=False,
            action=action,
            message=raw_message,
            command=command,
            elapsed_ms=elapsed_ms,
        )
    elapsed_ms = int((time.perf_counter() - started_at) * 1000)
    stdout = _normalize_process_text(completed.stdout)
    stderr = _normalize_process_text(completed.stderr)
    if completed.returncode != 0:
        raw_message = stderr or stdout or "Word automation failed."
        if action in {"export_pdf", "pdf_preflight"}:
            return _build_pdf_failure_result(
                action=action,
                raw_message=raw_message,
                stdout=stdout,
                stderr=stderr,
                command=command,
                elapsed_ms=elapsed_ms,
            )
        return WordAutomationResult(
            ok=False,
            action=action,
            message=raw_message,
            stdout=stdout,
            stderr=stderr,
            command=command,
            elapsed_ms=elapsed_ms,
        )
    return WordAutomationResult(
        ok=True,
        action=action,
        message=success_message,
        stdout=stdout,
        stderr=stderr,
        command=command,
        elapsed_ms=elapsed_ms,
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
    success_message = "Word document opened." if not align_right_and_save else "Word document aligned right and saved."
    return _run_command(
        action=action,
        command=command,
        success_message=success_message,
    )


def open_docx_in_word(docx_path: Path) -> WordAutomationResult:
    return _run_word_action(docx_path, align_right_and_save=False)


def align_right_and_save_docx_in_word(docx_path: Path) -> WordAutomationResult:
    return _run_word_action(docx_path, align_right_and_save=True)


def export_docx_to_pdf_in_word(
    docx_path: Path,
    pdf_path: Path,
    *,
    timeout_seconds: float = 45.0,
) -> WordAutomationResult:
    action = "export_pdf"
    resolved_docx = docx_path.expanduser().resolve()
    resolved_pdf = pdf_path.expanduser().resolve()
    if not _is_windows_host():
        return WordAutomationResult(
            ok=False,
            action=action,
            message="Word automation is available only on Windows.",
        )
    if not resolved_docx.exists():
        return WordAutomationResult(
            ok=False,
            action=action,
            message=f"DOCX not found: {resolved_docx}",
        )
    resolved_pdf.parent.mkdir(parents=True, exist_ok=True)
    command = _build_pdf_export_powershell_command(resolved_docx, resolved_pdf)
    if command is None:
        return _build_pdf_failure_result(
            action=action,
            raw_message="PowerShell is unavailable for Word automation.",
            failure_code="powershell_missing",
        )
    result = _run_command(
        action=action,
        command=command,
        success_message="Word document exported to PDF.",
        timeout_seconds=float(timeout_seconds),
    )
    if result.ok and not resolved_pdf.exists():
        return _build_pdf_failure_result(
            action=action,
            raw_message="Word returned success, but no PDF file was created.",
            stdout=result.stdout,
            stderr=result.stderr,
            command=result.command,
            elapsed_ms=result.elapsed_ms,
            failure_code="export_failed",
        )
    return result


def probe_word_pdf_export_support(*, timeout_seconds: float = 8.0) -> WordAutomationResult:
    action = "pdf_preflight"
    if not _is_windows_host():
        return WordAutomationResult(
            ok=False,
            action=action,
            message="Word automation is available only on Windows.",
            failure_code="unknown",
            details="Word automation is available only on Windows.",
        )
    command = _build_pdf_preflight_powershell_command()
    if command is None:
        return _build_pdf_failure_result(
            action=action,
            raw_message="PowerShell is unavailable for Word automation.",
            failure_code="powershell_missing",
        )
    return _run_command(
        action=action,
        command=command,
        success_message="Word PDF export preflight passed.",
        timeout_seconds=timeout_seconds,
    )
