from __future__ import annotations

from pathlib import Path
import subprocess

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
        self._running = False
        self.returncode = -9


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


def test_build_pdf_export_powershell_command_uses_docx_and_pdf_paths(tmp_path: Path, monkeypatch) -> None:
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

    command = word_automation._build_pdf_export_powershell_command(docx_path, pdf_path)

    assert command is not None
    assert "-Sta" in command
    script = command[-1]
    assert str(docx_path.resolve()).replace("'", "''") in script
    assert str(pdf_path.resolve()).replace("'", "''") in script
    assert "$doc.ExportAsFixedFormat($pdfPath, $wdExportFormatPDF)" in script
    assert "$doc.Close([ref]$false)" in script
    assert "$word.Quit()" in script
    assert "LEGALPDF_WORD_PHASE:export_pdf" in script
    assert "LEGALPDF_WORD_HELPER_PID:" in script
    assert "GetActiveObject('Word.Application')" in script
    assert "Start-Process -FilePath $wordAutomationPath -ArgumentList '/automation' -PassThru" in script
    assert "$ownsWordInstance = $true" in script
    assert "$null -ne $word -and $ownsWordInstance" in script


def test_build_pdf_preflight_powershell_command_starts_and_quits_word(monkeypatch) -> None:
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

    command = word_automation._build_pdf_preflight_powershell_command()

    assert command is not None
    assert "-Sta" in command
    script = command[-1]
    assert "New-Object -ComObject Word.Application" in script
    assert "$word.Quit()" in script
    assert "LEGALPDF_WORD_PHASE:launch_word" in script
    assert "LEGALPDF_WORD_PHASE:get_active_word" in script
    assert "LEGALPDF_WORD_PHASE:bootstrap_automation" in script
    assert "Start-Process -FilePath $wordAutomationPath -ArgumentList '/automation' -PassThru" in script
    assert "$null -ne $word -and $ownsWordInstance" in script


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
        lambda *args, **kwargs: (pdf_path.write_bytes(b"%PDF-1.7"), _FakePopen(returncode=0, stdout="OK", stderr=""))[1],
    )

    result = word_automation.export_docx_to_pdf_in_word(docx_path, pdf_path)

    assert result.ok is True
    assert result.action == "export_pdf"
    assert result.message == "Word document exported to PDF."
    assert result.command[0].endswith("powershell.exe")


def test_probe_word_pdf_export_support_classifies_com_launch_failure(monkeypatch) -> None:
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    monkeypatch.setattr(
        word_automation.subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            returncode=1,
            stdout="",
            stderr=(
                "New-Object : Retrieving the COM class factory for component with CLSID "
                "{000209FF-0000-0000-C000-000000000046} failed due to the following error: "
                "80080005 Server execution failed (Exception from HRESULT: 0x80080005 "
                "(CO_E_SERVER_EXEC_FAILURE))."
            ),
        ),
    )

    result = word_automation.probe_word_pdf_export_support()

    assert result.ok is False
    assert result.action == "pdf_preflight"
    assert result.failure_code == "com_launch_failed"
    assert result.message == "Microsoft Word could not be started for PDF export."
    assert "0x80080005" in result.details
    assert "Failure code: com_launch_failed" in result.details


def test_probe_word_pdf_export_support_classifies_real_powershell_com_failure(monkeypatch) -> None:
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )
    monkeypatch.setattr(
        word_automation.subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            returncode=1,
            stdout="",
            stderr=(
                "New-Object : Retrieving the COM class factory for component with CLSID "
                "{000209FF-0000-0000-C000-000000000046} failed due to the following error: "
                "80080005 Server execution failed (Exception from HRESULT: 0x80080005 "
                "(CO_E_SERVER_EXEC_FAILURE)).\n"
                "    + CategoryInfo          : ResourceUnavailable: (:) [New-Object], COMException\n"
                "    + FullyQualifiedErrorId : NoCOMClassIdentified,Microsoft.PowerShell.Commands.NewObjectCommand"
            ),
        ),
    )

    result = word_automation.probe_word_pdf_export_support()

    assert result.ok is False
    assert result.failure_code == "com_launch_failed"
    assert result.message == "Microsoft Word could not be started for PDF export."


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
    monkeypatch.setattr(
        word_automation.subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(timeout_exc=timeout, pid=3131),
    )
    monkeypatch.setattr(
        word_automation,
        "_terminate_windows_process_tree",
        lambda pid: (pid == 3131, "taskkill ok"),
    )

    result = word_automation.probe_word_pdf_export_support()

    assert result.ok is False
    assert result.failure_code == "timeout"
    assert result.message == "Word PDF export timed out."
    assert result.failure_phase == "launch_word"
    assert result.helper_pid == 3131
    assert result.cleanup_attempted is True
    assert result.cleanup_succeeded is True
    assert "Cleanup attempted: yes" in result.details
    assert "Word.Application launch timed out" in result.details


def test_export_docx_to_pdf_in_word_reports_missing_output_file_as_export_failure(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "honorarios.docx"
    pdf_path = tmp_path / "honorarios.pdf"
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

    result = word_automation.export_docx_to_pdf_in_word(docx_path, pdf_path)

    assert result.ok is False
    assert result.failure_code == "export_failed"
    assert result.message == "Microsoft Word could not export the PDF."
    assert "no PDF file was created" in result.details


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


def test_run_word_pdf_export_canary_verifies_pdf_header(tmp_path: Path, monkeypatch) -> None:
    pdf_bytes = b"%PDF-1.7\n"

    monkeypatch.setattr(
        word_automation,
        "export_docx_to_pdf_in_word",
        lambda docx_path, pdf_path, **kwargs: (
            pdf_path.write_bytes(pdf_bytes),
            word_automation.WordAutomationResult(ok=True, action="export_pdf", message="ok", elapsed_ms=25, helper_pid=8181),
        )[1],
    )

    result = word_automation.run_word_pdf_export_canary(temp_root=tmp_path)

    assert result.ok is True
    assert result.action == "pdf_export_canary"
    assert result.message == "Word PDF export canary passed."
    assert result.helper_pid == 8181
    assert "PDF header verified" in result.details


def test_run_word_pdf_export_canary_tolerates_cleanup_retry(tmp_path: Path, monkeypatch) -> None:
    cleanup_calls = {"count": 0}

    def _fake_export(docx_path: Path, pdf_path: Path, **kwargs):
        pdf_path.write_bytes(b"%PDF-1.7\n")
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
