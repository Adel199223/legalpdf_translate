"""Windows Word automation helpers used by the Qt app."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import os
from pathlib import Path
from shutil import which
import subprocess
from tempfile import TemporaryDirectory
import time

from docx import Document

_WORD_PHASE_PREFIX = "LEGALPDF_WORD_PHASE:"
_WORD_HELPER_PID_PREFIX = "LEGALPDF_WORD_HELPER_PID:"
_WORD_HELPER_OWNER_PREFIX = "LEGALPDF_WORD_HELPER_OWNER:"
_WORD_HELPER_OWNER = "app_owned"
_WORD_READINESS_CACHE_TTL_SECONDS = 60.0
_WORD_READINESS_CACHE: dict[str, tuple[float, dict[str, object]]] = {}


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
    failure_phase: str = ""
    helper_pid: int = 0
    cleanup_attempted: bool = False
    cleanup_succeeded: bool = False
    cleanup_details: str = ""


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


def _resolve_winword_path() -> str | None:
    if not _is_windows_host():
        return None
    candidates: list[Path] = []
    for env_name in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        root = str(os.environ.get(env_name, "") or "").strip()
        if root == "":
            continue
        base = Path(root)
        candidates.extend(
            [
                base / "Microsoft Office" / "root" / "Office16" / "WINWORD.EXE",
                base / "Microsoft Office" / "Office16" / "WINWORD.EXE",
                base / "Microsoft Office" / "root" / "Office15" / "WINWORD.EXE",
                base / "Microsoft Office" / "Office15" / "WINWORD.EXE",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    discovered = which("WINWORD.EXE") or which("winword.exe") or which("winword")
    if discovered:
        return discovered
    return None


def _quote_powershell_single(value: str) -> str:
    return value.replace("'", "''")


def _word_phase_marker(phase: str) -> str:
    return f"Write-Output '{_WORD_PHASE_PREFIX}{_quote_powershell_single(phase)}'"


def _word_helper_header() -> list[str]:
    return [
        f"Write-Output '{_WORD_HELPER_OWNER_PREFIX}{_WORD_HELPER_OWNER}'",
        f'Write-Output ("{_WORD_HELPER_PID_PREFIX}" + $PID)',
    ]


def _normalize_process_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    return str(value).strip()


def _strip_word_helper_markers(value: str) -> str:
    lines = []
    for raw_line in str(value or "").splitlines():
        line = raw_line.strip()
        if (
            line.startswith(_WORD_PHASE_PREFIX)
            or line.startswith(_WORD_HELPER_PID_PREFIX)
            or line.startswith(_WORD_HELPER_OWNER_PREFIX)
        ):
            continue
        lines.append(raw_line)
    return "\n".join(lines).strip()


def _extract_last_word_phase(*texts: str) -> str:
    last_phase = ""
    for text in texts:
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if line.startswith(_WORD_PHASE_PREFIX):
                last_phase = line[len(_WORD_PHASE_PREFIX) :].strip()
    return last_phase


def _extract_word_helper_pid(*texts: str) -> int:
    for text in texts:
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line.startswith(_WORD_HELPER_PID_PREFIX):
                continue
            raw_value = line[len(_WORD_HELPER_PID_PREFIX) :].strip()
            try:
                return int(raw_value)
            except (TypeError, ValueError):
                continue
    return 0


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
            *_word_helper_header(),
            f"$target = [System.IO.Path]::GetFullPath('{quoted}')",
            "$word = $null",
            _word_phase_marker("get_active_word"),
            "try {",
            "    $word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')",
            "} catch {",
            "}",
            "if ($null -eq $word) {",
            f"    {_word_phase_marker('launch_word')}",
            "    $word = New-Object -ComObject Word.Application",
            "}",
            "$word.Visible = $true",
            "$doc = $null",
            _word_phase_marker("scan_documents"),
            "foreach ($candidate in @($word.Documents)) {",
            "    if ([string]::Equals($candidate.FullName, $target, [System.StringComparison]::OrdinalIgnoreCase)) {",
            "        $doc = $candidate",
            "        break",
            "    }",
            "}",
            "if ($null -eq $doc) {",
            f"    {_word_phase_marker('open_document')}",
            "    $doc = $word.Documents.Open($target)",
            "}",
            _word_phase_marker("activate_document"),
            "$doc.Activate()",
            "$word.Activate()",
            action_block,
            _word_phase_marker("complete"),
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
    winword_path = _resolve_winword_path()
    quoted_winword = _quote_powershell_single(winword_path) if winword_path else ""
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            *_word_helper_header(),
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
            f"$wordAutomationPath = '{quoted_winword}'",
            "$bootstrapProcess = $null",
            f"$target = [System.IO.Path]::GetFullPath('{quoted_docx}')",
            f"$pdfPath = [System.IO.Path]::GetFullPath('{quoted_pdf}')",
            "$word = $null",
            "$doc = $null",
            "$openedDoc = $false",
            "$ownsWordInstance = $false",
            "try {",
            f"    {_word_phase_marker('get_active_word')}",
            "    try {",
            "        $word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')",
            "    } catch {",
            "    }",
            "    if ($null -eq $word) {",
            "        if (-not [string]::IsNullOrWhiteSpace($wordAutomationPath)) {",
            f"            {_word_phase_marker('bootstrap_automation')}",
            "            $bootstrapProcess = Start-Process -FilePath $wordAutomationPath -ArgumentList '/automation' -PassThru",
            "            Start-Sleep -Milliseconds 1500",
            "        }",
            f"        {_word_phase_marker('launch_word')}",
            "        $word = Invoke-WithRetry { New-Object -ComObject Word.Application }",
            "        $ownsWordInstance = $true",
            "    }",
            "    $word.Visible = $false",
            _word_phase_marker("documents_count"),
            "    Invoke-WithRetry { $null = $word.Documents.Count }",
            _word_phase_marker("open_document"),
            "    $doc = Invoke-WithRetry { $word.Documents.Open($target, $false, $true) }",
            "    $openedDoc = $true",
            _word_phase_marker("activate_document"),
            "    $doc.Activate()",
            "    $wdExportFormatPDF = 17",
            _word_phase_marker("export_pdf"),
            "    Invoke-WithRetry { $doc.ExportAsFixedFormat($pdfPath, $wdExportFormatPDF) }",
            _word_phase_marker("export_complete"),
            "    Write-Output 'OK'",
            "} finally {",
            "    if ($null -ne $doc -and $openedDoc) {",
                "        try {",
            f"            {_word_phase_marker('close_document')}",
            "            Invoke-WithRetry { $doc.Close([ref]$false) }",
            "        } catch {",
            "        }",
            "    }",
            "    if ($null -ne $word -and $ownsWordInstance) {",
            "        try {",
            f"            {_word_phase_marker('quit_word')}",
            "            Invoke-WithRetry { $word.Quit() }",
            "        } catch {",
            "        }",
            "    }",
            "    if ($null -ne $bootstrapProcess) {",
            "        try {",
            "            $bootstrapProcess.Refresh()",
            "            if (-not $bootstrapProcess.HasExited) {",
            f"                {_word_phase_marker('stop_bootstrap_process')}",
            "                Stop-Process -Id $bootstrapProcess.Id -Force",
            "            }",
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
    winword_path = _resolve_winword_path()
    quoted_winword = _quote_powershell_single(winword_path) if winword_path else ""
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            *_word_helper_header(),
            f"$wordAutomationPath = '{quoted_winword}'",
            "$bootstrapProcess = $null",
            "$word = $null",
            "$ownsWordInstance = $false",
            "try {",
            f"    {_word_phase_marker('get_active_word')}",
            "    try {",
            "        $word = [Runtime.InteropServices.Marshal]::GetActiveObject('Word.Application')",
            "    } catch {",
            "    }",
            "    if ($null -eq $word) {",
            "        if (-not [string]::IsNullOrWhiteSpace($wordAutomationPath)) {",
            f"            {_word_phase_marker('bootstrap_automation')}",
            "            $bootstrapProcess = Start-Process -FilePath $wordAutomationPath -ArgumentList '/automation' -PassThru",
            "            Start-Sleep -Milliseconds 1500",
            "        }",
            f"        {_word_phase_marker('launch_word')}",
            "        $word = New-Object -ComObject Word.Application",
            "        $ownsWordInstance = $true",
            "    }",
            "    $word.Visible = $false",
            _word_phase_marker("documents_count"),
            "    $null = $word.Documents.Count",
            _word_phase_marker("complete"),
            "    Write-Output 'OK'",
            "} finally {",
            "    if ($null -ne $word -and $ownsWordInstance) {",
            "        try {",
            f"            {_word_phase_marker('quit_word')}",
            "            $word.Quit()",
            "        } catch {",
            "        }",
            "    }",
            "    if ($null -ne $bootstrapProcess) {",
            "        try {",
            "            $bootstrapProcess.Refresh()",
            "            if (-not $bootstrapProcess.HasExited) {",
            f"                {_word_phase_marker('stop_bootstrap_process')}",
            "                Stop-Process -Id $bootstrapProcess.Id -Force",
            "            }",
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
    if (
        "powershell is unavailable" in lowered
        or "powershell unavailable" in lowered
        or "powershell.exe is unavailable" in lowered
    ):
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
        "verification_failed": "Word PDF export verification failed.",
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
    failure_phase: str = "",
    helper_pid: int = 0,
    cleanup_attempted: bool = False,
    cleanup_succeeded: bool = False,
    cleanup_details: str = "",
) -> str:
    lines = [
        f"Failure code: {failure_code or 'unknown'}",
        f"Elapsed: {elapsed_ms} ms",
    ]
    if failure_phase:
        lines.append(f"Failure phase: {failure_phase}")
    if helper_pid > 0:
        lines.append(f"Helper PID: {helper_pid}")
    if cleanup_attempted:
        lines.append(f"Cleanup attempted: {'yes' if cleanup_succeeded else 'no'}")
    if cleanup_details:
        lines.extend(["", "Cleanup:", cleanup_details])
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
    failure_phase: str = "",
    helper_pid: int = 0,
    cleanup_attempted: bool = False,
    cleanup_succeeded: bool = False,
    cleanup_details: str = "",
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
            failure_phase=failure_phase,
            helper_pid=helper_pid,
            cleanup_attempted=cleanup_attempted,
            cleanup_succeeded=cleanup_succeeded,
            cleanup_details=cleanup_details,
        ),
        elapsed_ms=elapsed_ms,
        failure_phase=failure_phase,
        helper_pid=helper_pid,
        cleanup_attempted=cleanup_attempted,
        cleanup_succeeded=cleanup_succeeded,
        cleanup_details=cleanup_details,
    )


def _resolve_taskkill_path() -> str | None:
    if not _is_windows_host():
        return None
    system_root = os.environ.get("SystemRoot", r"C:\Windows").strip() or r"C:\Windows"
    preferred = Path(system_root) / "System32" / "taskkill.exe"
    if preferred.exists():
        return str(preferred)
    discovered = which("taskkill.exe") or which("taskkill")
    if discovered:
        return discovered
    return None


def _terminate_windows_process_tree(pid: int) -> tuple[bool, str]:
    if not _is_windows_host() or int(pid) <= 0:
        return False, "Process-tree cleanup is only available on Windows."
    taskkill = _resolve_taskkill_path()
    if taskkill is None:
        return False, "taskkill.exe is unavailable."
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        completed = subprocess.run(
            [taskkill, "/PID", str(int(pid)), "/T", "/F"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            creationflags=creationflags,
        )
    except subprocess.TimeoutExpired as exc:
        return False, f"taskkill timed out after {exc.timeout} seconds."
    stdout = _normalize_process_text(completed.stdout)
    stderr = _normalize_process_text(completed.stderr)
    lowered = f"{stdout}\n{stderr}".casefold()
    success = completed.returncode == 0 or "not found" in lowered or "no running instance" in lowered
    details = stderr or stdout or "taskkill returned no output."
    return success, details


def serialize_word_automation_result(result: WordAutomationResult) -> dict[str, object]:
    return {
        "ok": bool(result.ok),
        "action": str(result.action or "").strip(),
        "message": str(result.message or "").strip(),
        "stdout": str(result.stdout or "").strip(),
        "stderr": str(result.stderr or "").strip(),
        "command": list(result.command),
        "failure_code": str(result.failure_code or "").strip(),
        "details": str(result.details or "").strip(),
        "elapsed_ms": int(result.elapsed_ms),
        "failure_phase": str(result.failure_phase or "").strip(),
        "helper_pid": int(result.helper_pid or 0),
        "cleanup_attempted": bool(result.cleanup_attempted),
        "cleanup_succeeded": bool(result.cleanup_succeeded),
        "cleanup_details": str(result.cleanup_details or "").strip(),
    }


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
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
        )
        stdout_raw, stderr_raw = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        stdout_raw = _normalize_process_text(getattr(exc, "stdout", ""))
        stderr_raw = _normalize_process_text(getattr(exc, "stderr", ""))
        helper_pid = _extract_word_helper_pid(stdout_raw, stderr_raw) or int(getattr(process, "pid", 0) or 0)
        failure_phase = _extract_last_word_phase(stdout_raw, stderr_raw)
        cleanup_attempted = False
        cleanup_succeeded = False
        cleanup_details = ""
        if action in {"export_pdf", "pdf_preflight"} and helper_pid > 0 and _is_windows_host():
            cleanup_attempted = True
            cleanup_succeeded, cleanup_details = _terminate_windows_process_tree(helper_pid)
        if getattr(process, "poll", lambda: None)() is None:
            try:
                process.kill()
            except Exception:  # noqa: BLE001
                pass
        try:
            extra_stdout, extra_stderr = process.communicate(timeout=2)
            stdout_raw = "\n".join(filter(None, [stdout_raw, _normalize_process_text(extra_stdout)])).strip()
            stderr_raw = "\n".join(filter(None, [stderr_raw, _normalize_process_text(extra_stderr)])).strip()
        except Exception:  # noqa: BLE001
            pass
        stdout = _strip_word_helper_markers(stdout_raw)
        stderr = _strip_word_helper_markers(stderr_raw)
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
                failure_phase=failure_phase,
                helper_pid=helper_pid,
                cleanup_attempted=cleanup_attempted,
                cleanup_succeeded=cleanup_succeeded,
                cleanup_details=cleanup_details,
            )
        return WordAutomationResult(
            ok=False,
            action=action,
            message=str(exc),
            stdout=stdout,
            stderr=stderr,
            command=command,
            elapsed_ms=elapsed_ms,
            failure_phase=failure_phase,
            helper_pid=helper_pid,
            cleanup_attempted=cleanup_attempted,
            cleanup_succeeded=cleanup_succeeded,
            cleanup_details=cleanup_details,
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
    stdout_raw = _normalize_process_text(stdout_raw)
    stderr_raw = _normalize_process_text(stderr_raw)
    stdout = _strip_word_helper_markers(stdout_raw)
    stderr = _strip_word_helper_markers(stderr_raw)
    helper_pid = _extract_word_helper_pid(stdout_raw, stderr_raw) or int(getattr(process, "pid", 0) or 0)
    failure_phase = _extract_last_word_phase(stdout_raw, stderr_raw)
    if process.returncode != 0:
        raw_message = stderr or stdout or "Word automation failed."
        if action in {"export_pdf", "pdf_preflight"}:
            return _build_pdf_failure_result(
                action=action,
                raw_message=raw_message,
                stdout=stdout,
                stderr=stderr,
                command=command,
                elapsed_ms=elapsed_ms,
                failure_phase=failure_phase,
                helper_pid=helper_pid,
            )
        return WordAutomationResult(
            ok=False,
            action=action,
            message=raw_message,
            stdout=stdout,
            stderr=stderr,
            command=command,
            elapsed_ms=elapsed_ms,
            failure_phase=failure_phase,
            helper_pid=helper_pid,
        )
    return WordAutomationResult(
        ok=True,
        action=action,
        message=success_message,
        stdout=stdout,
        stderr=stderr,
        command=command,
        elapsed_ms=elapsed_ms,
        failure_phase=failure_phase,
        helper_pid=helper_pid,
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


def probe_word_pdf_export_support(*, timeout_seconds: float = 12.0) -> WordAutomationResult:
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


def _write_word_export_canary_docx(docx_path: Path) -> None:
    document = Document()
    document.add_heading("LegalPDF Translate", level=1)
    document.add_paragraph("Word PDF export canary")
    document.add_paragraph("This temporary document verifies Gmail finalization PDF readiness.")
    document.save(docx_path)


def run_word_pdf_export_canary(*, timeout_seconds: float = 45.0, temp_root: Path | None = None) -> WordAutomationResult:
    action = "pdf_export_canary"
    root = temp_root.expanduser().resolve() if isinstance(temp_root, Path) else None
    with TemporaryDirectory(prefix="legalpdf_word_export_canary_", dir=str(root) if root else None) as temp_dir:
        working_dir = Path(temp_dir).expanduser().resolve()
        docx_path = working_dir / "honorarios_canary.docx"
        pdf_path = working_dir / "honorarios_canary.pdf"
        _write_word_export_canary_docx(docx_path)
        export_result = export_docx_to_pdf_in_word(docx_path, pdf_path, timeout_seconds=timeout_seconds)
        if not export_result.ok:
            return WordAutomationResult(
                ok=False,
                action=action,
                message=export_result.message,
                stdout=export_result.stdout,
                stderr=export_result.stderr,
                command=export_result.command,
                failure_code=export_result.failure_code,
                details=export_result.details,
                elapsed_ms=export_result.elapsed_ms,
                failure_phase=export_result.failure_phase,
                helper_pid=export_result.helper_pid,
                cleanup_attempted=export_result.cleanup_attempted,
                cleanup_succeeded=export_result.cleanup_succeeded,
                cleanup_details=export_result.cleanup_details,
            )
        header = pdf_path.read_bytes()[:5] if pdf_path.exists() else b""
        if header != b"%PDF-":
            return _build_pdf_failure_result(
                action=action,
                raw_message=f"Expected PDF header %PDF- but found {header!r}.",
                command=export_result.command,
                elapsed_ms=export_result.elapsed_ms,
                failure_code="verification_failed",
                failure_phase="verify_pdf_header",
                helper_pid=export_result.helper_pid,
            )
        return WordAutomationResult(
            ok=True,
            action=action,
            message="Word PDF export canary passed.",
            stdout=export_result.stdout,
            stderr=export_result.stderr,
            command=export_result.command,
            details="PDF header verified as %PDF-.",
            elapsed_ms=export_result.elapsed_ms,
            helper_pid=export_result.helper_pid,
        )


def assess_word_pdf_export_readiness(
    *,
    cache_scope: object | None = None,
    launch_timeout_seconds: float = 12.0,
    export_timeout_seconds: float = 45.0,
    force_refresh: bool = False,
    cache_ttl_seconds: float = _WORD_READINESS_CACHE_TTL_SECONDS,
    temp_root: Path | None = None,
) -> dict[str, object]:
    scope = str(cache_scope or "global").strip() or "global"
    now = time.time()
    cached_entry = _WORD_READINESS_CACHE.get(scope)
    if not force_refresh and cached_entry and (now - cached_entry[0]) < float(cache_ttl_seconds):
        payload = dict(cached_entry[1])
        payload["used_cache"] = True
        return payload

    launch_preflight = probe_word_pdf_export_support(timeout_seconds=float(launch_timeout_seconds))
    if launch_preflight.ok:
        export_canary = run_word_pdf_export_canary(
            timeout_seconds=float(export_timeout_seconds),
            temp_root=temp_root,
        )
    else:
        export_canary = WordAutomationResult(
            ok=False,
            action="pdf_export_canary",
            message="Word export canary was skipped because launch preflight failed.",
            failure_code=launch_preflight.failure_code or "launch_preflight_failed",
            details=launch_preflight.details,
            elapsed_ms=launch_preflight.elapsed_ms,
            failure_phase=launch_preflight.failure_phase,
            helper_pid=launch_preflight.helper_pid,
            cleanup_attempted=launch_preflight.cleanup_attempted,
            cleanup_succeeded=launch_preflight.cleanup_succeeded,
            cleanup_details=launch_preflight.cleanup_details,
        )

    finalization_ready = bool(launch_preflight.ok and export_canary.ok)
    effective = export_canary if launch_preflight.ok else launch_preflight
    payload = {
        "ok": finalization_ready,
        "finalization_ready": finalization_ready,
        "failure_code": str(effective.failure_code or "").strip(),
        "message": str(effective.message or "").strip(),
        "details": str(effective.details or "").strip(),
        "elapsed_ms": int(effective.elapsed_ms),
        "failure_phase": str(effective.failure_phase or "").strip(),
        "launch_preflight": serialize_word_automation_result(launch_preflight),
        "export_canary": serialize_word_automation_result(export_canary),
        "preflight": serialize_word_automation_result(launch_preflight),
        "last_checked_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "cache_ttl_seconds": int(max(1.0, float(cache_ttl_seconds))),
        "used_cache": False,
    }
    _WORD_READINESS_CACHE[scope] = (now, dict(payload))
    return payload


def clear_word_pdf_export_readiness_cache(*, scope_prefix: object | None = None) -> int:
    prefix = str(scope_prefix or "").strip()
    if prefix == "":
        removed = len(_WORD_READINESS_CACHE)
        _WORD_READINESS_CACHE.clear()
        return removed
    removed = 0
    for scope in list(_WORD_READINESS_CACHE):
        if not scope.startswith(prefix):
            continue
        removed += 1
        _WORD_READINESS_CACHE.pop(scope, None)
    return removed
