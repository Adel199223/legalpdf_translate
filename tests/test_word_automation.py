from __future__ import annotations

from pathlib import Path
import json
import re
import subprocess

import fitz
import pytest
from docx import Document

import legalpdf_translate.word_automation as word_automation


class _FakePopen:
    def __init__(
        self,
        *,
        returncode: int = 0,
        stdout: str = "OK",
        stderr: str = "",
        pid: int = 4242,
        timeout_exc: subprocess.TimeoutExpired | None = None,
        trailing_outputs: list[tuple[str, str]] | None = None,
    ) -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr
        self.pid = pid
        self._timeout_exc = timeout_exc
        self._trailing_outputs = list(trailing_outputs or [])
        self._communicate_calls = 0
        self._running = True
        self.kill_calls = 0

    def communicate(self, timeout: float | None = None):
        self._communicate_calls += 1
        if self._timeout_exc is not None and self._communicate_calls == 1:
            raise self._timeout_exc
        self._running = False
        if self._communicate_calls > 1 and self._trailing_outputs:
            return self._trailing_outputs.pop(0)
        return (self._stdout, self._stderr)

    def poll(self):
        return None if self._running else self.returncode

    def kill(self) -> None:
        self.kill_calls += 1
        self._running = False
        self.returncode = -9


def _write_docx(path: Path) -> None:
    document = Document()
    document.add_paragraph("Synthetic requerimento de honorários.")
    document.save(path)


def _write_pdf(path: Path, text: str = "Synthetic honorarios PDF") -> None:
    with fitz.open() as document:
        document.new_page().insert_text((72, 72), text)
        document.save(path)


def _script_path(script: str, variable: str) -> Path | None:
    match = re.search(rf"^\${variable} = '(.*)'$", script, re.MULTILINE)
    return Path(match.group(1).replace("''", "'")) if match else None


def _record_pdf_helper(
    monkeypatch,
    *,
    state_overrides: dict | None = None,
    create_pdf: bool = True,
    process: _FakePopen | None = None,
) -> list[dict]:
    """Model the -File helper protocol without launching PowerShell or Word."""
    calls: list[dict] = []
    process = process or _FakePopen()

    def _launch(command, **kwargs):
        assert "-File" in command
        assert "-Command" not in command
        script_file = Path(command[command.index("-File") + 1])
        assert script_file.read_bytes().startswith(b"\xef\xbb\xbf")
        script = script_file.read_text(encoding="utf-8-sig")
        state_path = _script_path(script, "statePath")
        assert state_path is not None
        state = {
            "status": "succeeded",
            "phase": "complete",
            "cleanup_status": "confirmed",
            "helper_pid": process.pid,
            "helper_start_ticks": "123",
            "ownership": "proven",
        }
        state.update(state_overrides or {})
        state_path.write_text(json.dumps(state), encoding="utf-8")
        source = _script_path(script, "target")
        target = _script_path(script, "pdfPath")
        if target is not None and create_pdf:
            _write_pdf(target)
        calls.append({"command": command, "kwargs": kwargs, "source": source, "target": target})
        return process

    monkeypatch.setattr(word_automation.subprocess, "Popen", _launch)
    return calls


def test_build_open_powershell_command_uses_exact_resolved_path(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "arabic doc's.docx"
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )

    command = word_automation._build_powershell_command(docx_path, align_right_and_save=False)

    assert command is not None
    assert "-Sta" in command
    script = command[-1]
    assert str(docx_path.resolve()).replace("'", "''") in script
    assert "Documents.Open($target)" in script
    assert "ParagraphFormat.Alignment = 2" not in script


def test_build_align_save_powershell_command_sets_alignment_and_save(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "arabic.docx"
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )

    command = word_automation._build_powershell_command(docx_path, align_right_and_save=True)

    assert command is not None
    assert "-Sta" in command
    script = command[-1]
    assert "$doc.Range().ParagraphFormat.Alignment = 2" in script
    assert "$doc.Save()" in script


def test_build_pdf_export_powershell_script_uses_docx_and_pdf_paths(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "honorarios doc's.docx"
    pdf_path = tmp_path / "honorarios out.pdf"
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    monkeypatch.setattr(
        word_automation,
        "_resolve_winword_path",
        lambda: r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    )

    script = word_automation._build_pdf_export_powershell_script(docx_path, pdf_path)
    assert str(docx_path.resolve()).replace("'", "''") in script
    assert str(pdf_path.resolve()).replace("'", "''") in script
    assert "$doc.ExportAsFixedFormat(" in script
    assert "$pdfPath, 17, $false" in script
    assert "$doc.Close(0)" in script
    assert "$word.Quit(0)" in script
    assert "Invoke-Com 'export_pdf'" in script
    assert "LEGALPDF_WORD_HELPER_PID:" in script
    assert "GetActiveObject" not in script
    assert "New-Object -ComObject" not in script
    assert "Start-Process" not in script
    assert "$word.Hwnd" not in script
    assert "$bootstrapWindow.Hwnd" in script
    assert "AccessibleObjectFromWindow" in script
    assert "$startInfo.Arguments = '/w'" in script
    assert r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE" in script
    assert "Assert-StartedProcess 'cleanup_quit_identity'" in script
    assert "Invoke-Com 'close_bootstrap_document'" not in script
    assert script.index("Assert-StartedProcess 'cleanup_quit_identity'") < script.index("Invoke-Com 'quit_word'")
    assert script.index("Assert-BootstrapUnchanged 'cleanup_bootstrap'") < script.index("Invoke-Com 'quit_word'")
    assert "if ($remainingCount -ne 1) { Fail-Safe 'cleanup_ambiguous' }" in script
    assert "Assert-StagedDocument 'cleanup_document_identity'" in script
    assert "$doc.Activate" not in script


def test_build_pdf_preflight_powershell_script_requires_owned_instance(monkeypatch) -> None:
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    monkeypatch.setattr(
        word_automation,
        "_resolve_winword_path",
        lambda: r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE",
    )

    script = word_automation._build_pdf_preflight_powershell_script()
    assert "$mode = 'preflight'" in script
    assert "New-Object -ComObject" not in script
    assert "[Diagnostics.Process]::Start($startInfo)" in script
    assert "$startInfo.Arguments = '/w'" in script
    assert "$startInfo.UseShellExecute = $true" in script
    assert "[Diagnostics.ProcessWindowStyle]::Hidden" in script
    assert r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE" in script
    assert "AccessibleObjectFromWindow" in script
    assert "$bootstrapWindow.Hwnd" in script
    assert "$word.Hwnd" not in script
    assert "$word.Quit(0)" in script
    assert "Set-Phase 'launch_word'" in script
    assert "GetActiveObject" not in script
    assert "$state.ownership -eq 'proven'" in script
    assert "Assert-StartedProcess 'cleanup_quit_identity'" in script


def test_open_docx_in_word_reports_subprocess_failure(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "arabic.docx"
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    monkeypatch.setattr(
        word_automation.subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(returncode=1, stdout="", stderr="boom"),
    )

    result = word_automation.open_docx_in_word(docx_path)

    assert result.ok is False
    assert result.action == "open"
    assert result.message == "boom"
    assert result.command[0].endswith("powershell.exe")


def test_align_right_and_save_docx_in_word_reports_success(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "arabic.docx"
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    monkeypatch.setattr(
        word_automation.subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(returncode=0, stdout="OK", stderr=""),
    )

    result = word_automation.align_right_and_save_docx_in_word(docx_path)

    assert result.ok is True
    assert result.action == "align_right_and_save"
    assert result.message == "Word document aligned right and saved."


def test_export_docx_to_pdf_in_word_reports_success(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "honorarios.docx"
    pdf_path = tmp_path / "honorarios.pdf"
    _write_docx(docx_path)
    source_bytes = docx_path.read_bytes()

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    calls = _record_pdf_helper(monkeypatch)

    result = word_automation.export_docx_to_pdf_in_word(docx_path, pdf_path)

    assert result.ok is True
    assert result.action == "export_pdf"
    assert result.message == "Word document exported to PDF."
    assert result.command[0].endswith("powershell.exe")
    assert result.cleanup_succeeded is True
    assert len(calls) == 1
    assert "-Sta" in calls[0]["command"]
    assert calls[0]["source"] != docx_path
    assert calls[0]["target"] != pdf_path
    assert calls[0]["kwargs"]["stdout"] == subprocess.DEVNULL
    assert calls[0]["kwargs"]["stderr"] == subprocess.PIPE
    assert result.stdout == result.stderr == ""
    with fitz.open(pdf_path) as document:
        assert document.page_count == 1
        assert "Synthetic honorarios PDF" in document[0].get_text()
    assert docx_path.read_bytes() == source_bytes


def test_probe_word_pdf_export_support_classifies_com_launch_failure(monkeypatch) -> None:
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    _record_pdf_helper(
        monkeypatch,
        state_overrides={"status": "failed", "phase": "launch_word", "primary_hresult": "0x80080005",
                         "failure_code": "com_launch_failed", "cleanup_status": "ambiguous"},
        process=_FakePopen(returncode=1),
    )

    result = word_automation.probe_word_pdf_export_support()

    assert result.ok is False
    assert result.action == "pdf_preflight"
    assert result.failure_code == "com_launch_failed"
    assert result.message == "Microsoft Word could not be started for PDF export."
    assert "0x80080005" in result.details
    assert "Failure code: com_launch_failed" in result.details


def test_probe_word_pdf_export_support_does_not_expose_raw_powershell_com_failure(monkeypatch) -> None:
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    _record_pdf_helper(
        monkeypatch,
        state_overrides={"status": "failed", "phase": "launch_word", "primary_hresult": "0x80080005",
                         "failure_code": "com_launch_failed", "cleanup_status": "ambiguous"},
        process=_FakePopen(
            returncode=1,
            stdout="synthetic-private-document-content",
            stderr=(
                "New-Object : Retrieving the COM class factory for component with CLSID "
                "{000209FF-0000-0000-C000-000000000046} failed due to the following error: "
                "80080005 Server execution failed (Exception from HRESULT: 0x80080005 "
                "(CO_E_SERVER_EXEC_FAILURE)).\n"
                "    + CategoryInfo          : ResourceUnavailable: (:) [New-Object], COMException\n"
                "    + FullyQualifiedErrorId : NoCOMClassIdentified,Microsoft.PowerShell.Commands.NewObjectCommand"
                "\nC:\\private-synthetic-document.docx"
            ),
        ),
    )

    result = word_automation.probe_word_pdf_export_support()

    assert result.ok is False
    assert result.failure_code == "com_launch_failed"
    assert result.message == "Microsoft Word could not be started for PDF export."
    assert "0x80080005" in result.details
    assert "private-synthetic" not in str(result)
    assert "synthetic-private" not in str(result)
    assert "New-Object" not in result.details
    assert result.stdout == result.stderr == ""


def test_probe_word_pdf_export_support_classifies_timeout(monkeypatch) -> None:
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    timeout = subprocess.TimeoutExpired(
        cmd=["powershell.exe"],
        timeout=8,
        output=f"{word_automation._WORD_HELPER_PID_PREFIX}3131\n{word_automation._WORD_PHASE_PREFIX}launch_word",
        stderr="Word.Application launch timed out",
    )
    process = _FakePopen(timeout_exc=timeout, pid=3131)
    calls = _record_pdf_helper(
        monkeypatch,
        state_overrides={"status": "running", "phase": "launch_word", "cleanup_status": "not_started"},
        process=process,
    )
    monkeypatch.setattr(
        word_automation,
        "_terminate_windows_process_tree",
        lambda pid: pytest.fail("PDF timeout must not kill a process tree"),
    )
    monkeypatch.setattr("legalpdf_translate.word_pdf_control._identity_gone", lambda *args: False)
    # Simulate unresolved Word activation independently of this host's current
    # processes. A Word-free machine legitimately permits a later safe retry.
    monkeypatch.setattr("legalpdf_translate.word_pdf_control._no_word_processes", lambda: False)

    result = word_automation.probe_word_pdf_export_support()

    assert result.ok is False
    assert result.failure_code == "timeout"
    assert result.message == "Word PDF export timed out."
    assert result.failure_phase == "launch_word"
    assert result.helper_pid == 3131
    assert result.cleanup_attempted is True
    assert result.cleanup_succeeded is False
    assert process.kill_calls == 1
    assert "Cleanup attempted: yes" in result.details
    assert "Owned helper stopped: yes" in result.details
    assert "Word.Application launch timed out" not in result.details
    retry = word_automation.probe_word_pdf_export_support()
    assert retry.ok is False
    assert retry.failure_code == "cleanup_unconfirmed"
    assert len(calls) == 1


def test_export_docx_to_pdf_in_word_reports_missing_output_file_as_export_failure(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "honorarios.docx"
    pdf_path = tmp_path / "honorarios.pdf"
    _write_docx(docx_path)

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    _record_pdf_helper(monkeypatch, create_pdf=False)

    result = word_automation.export_docx_to_pdf_in_word(docx_path, pdf_path)

    assert result.ok is False
    assert result.failure_code == "verification_failed"
    assert result.failure_phase == "verify_artifacts"
    assert "original DOCX and any previous PDF were preserved" in result.details
    assert not pdf_path.exists()


@pytest.mark.parametrize("fresh_pdf_written", [False, True])
def test_failed_pdf_export_preserves_previous_output_and_invalidates_readiness(
    tmp_path: Path, monkeypatch, fresh_pdf_written: bool,
) -> None:
    docx_path = tmp_path / "honorários d'Água.docx"
    pdf_path = docx_path.with_suffix(".pdf")
    _write_docx(docx_path)
    _write_pdf(pdf_path, "Previous reviewed PDF")
    original_docx = docx_path.read_bytes()
    original_pdf = pdf_path.read_bytes()
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(word_automation, "_resolve_powershell_path", lambda: "powershell.exe")
    calls = _record_pdf_helper(
        monkeypatch,
        create_pdf=fresh_pdf_written,
        state_overrides={"cleanup_status": "ambiguous"} if fresh_pdf_written else None,
    )
    word_automation._WORD_READINESS_CACHE["synthetic-cached-ready"] = (0, {"ok": True})

    result = word_automation.export_docx_to_pdf_in_word(docx_path, pdf_path)

    assert result.ok is False
    assert result.failure_code == ("cleanup_unconfirmed" if fresh_pdf_written else "verification_failed")
    assert len(calls) == 1
    assert docx_path.read_bytes() == original_docx
    assert pdf_path.read_bytes() == original_pdf
    assert "synthetic-cached-ready" not in word_automation._WORD_READINESS_CACHE


def test_open_docx_in_word_is_unsupported_off_windows(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "arabic.docx"
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: False)

    result = word_automation.open_docx_in_word(docx_path)

    assert result.ok is False
    assert result.message == "Word automation is available only on Windows."


def test_export_docx_to_pdf_in_word_is_unsupported_off_windows(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "honorarios.docx"
    pdf_path = tmp_path / "honorarios.pdf"
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: False)

    result = word_automation.export_docx_to_pdf_in_word(docx_path, pdf_path)

    assert result.ok is False
    assert result.action == "export_pdf"
    assert result.message == "Word automation is available only on Windows."


def test_run_word_pdf_export_canary_verifies_pdf_pages_and_expected_text(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        word_automation,
        "export_docx_to_pdf_in_word",
        lambda docx_path, pdf_path, **kwargs: (
            _write_pdf(pdf_path, "Word PDF export canary"),
            word_automation.WordAutomationResult(ok=True, action="export_pdf", message="ok", elapsed_ms=25, helper_pid=8181),
        )[1],
    )

    result = word_automation.run_word_pdf_export_canary(temp_root=tmp_path)

    assert result.ok is True
    assert result.action == "pdf_export_canary"
    assert result.message == "Word PDF export canary passed."
    assert result.helper_pid == 8181
    assert "PDF pages and expected canary text verified" in result.details


@pytest.mark.parametrize("header_only", [False, True])
def test_run_word_pdf_export_canary_rejects_missing_evidence(tmp_path: Path, monkeypatch, header_only: bool) -> None:
    def _fake_export(docx_path: Path, pdf_path: Path, **kwargs):
        if header_only:
            pdf_path.write_bytes(b"%PDF-1.7\n")
        else:
            _write_pdf(pdf_path, "Unrelated document without canary text")
        return word_automation.WordAutomationResult(ok=True, action="export_pdf", message="ok")

    monkeypatch.setattr(word_automation, "export_docx_to_pdf_in_word", _fake_export)

    result = word_automation.run_word_pdf_export_canary(temp_root=tmp_path)

    assert result.ok is False
    assert result.action == "pdf_export_canary"
    assert result.failure_code == "verification_failed"
    assert result.failure_phase == "verify_pdf_content"


def test_successful_export_canary_preserves_confirmed_cleanup_metadata(tmp_path: Path, monkeypatch) -> None:
    def _fake_export(docx_path: Path, pdf_path: Path, **kwargs):
        _write_pdf(pdf_path, "Word PDF export canary")
        return word_automation.WordAutomationResult(
            ok=True,
            action="export_pdf",
            message="Word document exported to PDF.",
            details="Phase: complete\nWord cleanup: confirmed",
            elapsed_ms=25,
            helper_pid=8181,
            cleanup_attempted=True,
            cleanup_succeeded=True,
            cleanup_details="Owned Word instance exit confirmed.",
        )

    monkeypatch.setattr(word_automation, "export_docx_to_pdf_in_word", _fake_export)
    result = word_automation.run_word_pdf_export_canary(temp_root=tmp_path)

    assert result.ok is True
    assert result.action == "pdf_export_canary"
    assert result.cleanup_attempted is True
    assert result.cleanup_succeeded is True
    assert result.cleanup_details == "Owned Word instance exit confirmed."
    assert "Word cleanup: confirmed" in result.details
    assert "PDF pages and expected canary text verified." in result.details
    serialized = word_automation.serialize_word_automation_result(result)
    assert serialized["cleanup_attempted"] is True
    assert serialized["cleanup_succeeded"] is True
    assert serialized["cleanup_details"] == result.cleanup_details


def test_run_word_pdf_export_canary_tolerates_cleanup_retry(tmp_path: Path, monkeypatch) -> None:
    cleanup_calls = {"count": 0}

    def _fake_export(docx_path: Path, pdf_path: Path, **kwargs):
        _write_pdf(pdf_path, "Word PDF export canary")
        return word_automation.WordAutomationResult(
            ok=True,
            action="export_pdf",
            message="ok",
            elapsed_ms=12,
        )

    def _fake_rmtree(_path: Path) -> None:
        cleanup_calls["count"] += 1
        if cleanup_calls["count"] == 1:
            raise PermissionError("locked")

    monkeypatch.setattr(word_automation, "export_docx_to_pdf_in_word", _fake_export)
    monkeypatch.setattr(word_automation.shutil, "rmtree", _fake_rmtree)
    monkeypatch.setattr(word_automation.time, "sleep", lambda _seconds: None)

    result = word_automation.run_word_pdf_export_canary(temp_root=tmp_path)

    assert result.ok is True
    assert cleanup_calls["count"] == 2


def test_assess_word_pdf_export_readiness_reports_launch_vs_canary(monkeypatch) -> None:
    calls = {"launch": 0, "canary": 0}
    monkeypatch.setattr(
        word_automation,
        "probe_word_pdf_export_support",
        lambda **kwargs: calls.__setitem__("launch", calls["launch"] + 1)
        or word_automation.WordAutomationResult(ok=True, action="pdf_preflight", message="Launch ready"),
    )
    monkeypatch.setattr(
        word_automation,
        "run_word_pdf_export_canary",
        lambda **kwargs: calls.__setitem__("canary", calls["canary"] + 1)
        or word_automation.WordAutomationResult(ok=False, action="pdf_export_canary", message="Export timed out", failure_code="timeout", failure_phase="export_pdf"),
    )

    payload = word_automation.assess_word_pdf_export_readiness(cache_scope="test-scope", force_refresh=True)

    assert payload["ok"] is False
    assert payload["finalization_ready"] is False
    assert payload["launch_preflight"]["ok"] is True
    assert payload["export_canary"]["ok"] is False
    assert payload["failure_code"] == "timeout"
    assert payload["failure_phase"] == "export_pdf"
    assert calls == {"launch": 1, "canary": 1}


def test_assess_word_pdf_export_readiness_uses_cache(monkeypatch) -> None:
    calls = {"launch": 0, "canary": 0}
    monkeypatch.setattr(
        word_automation,
        "probe_word_pdf_export_support",
        lambda **kwargs: calls.__setitem__("launch", calls["launch"] + 1)
        or word_automation.WordAutomationResult(ok=True, action="pdf_preflight", message="Launch ready"),
    )
    monkeypatch.setattr(
        word_automation,
        "run_word_pdf_export_canary",
        lambda **kwargs: calls.__setitem__("canary", calls["canary"] + 1)
        or word_automation.WordAutomationResult(ok=True, action="pdf_export_canary", message="Canary ready"),
    )

    first = word_automation.assess_word_pdf_export_readiness(cache_scope="cache-scope", force_refresh=True)
    second = word_automation.assess_word_pdf_export_readiness(cache_scope="cache-scope")

    assert first["finalization_ready"] is True
    assert second["used_cache"] is True
    assert calls == {"launch": 1, "canary": 1}


def test_clear_word_pdf_export_readiness_cache_supports_prefix_invalidation() -> None:
    word_automation.clear_word_pdf_export_readiness_cache()
    word_automation._WORD_READINESS_CACHE.update(  # noqa: SLF001
        {
            "provider_state::a": (1.0, {"ok": True}),
            "gmail_batch_finalization::a::session": (1.0, {"ok": True}),
            "provider_state::b": (1.0, {"ok": False}),
        }
    )

    removed = word_automation.clear_word_pdf_export_readiness_cache(scope_prefix="provider_state::a")

    assert removed == 1
    assert "provider_state::a" not in word_automation._WORD_READINESS_CACHE  # noqa: SLF001
    assert "gmail_batch_finalization::a::session" in word_automation._WORD_READINESS_CACHE  # noqa: SLF001
    assert "provider_state::b" in word_automation._WORD_READINESS_CACHE  # noqa: SLF001

    word_automation.clear_word_pdf_export_readiness_cache()
