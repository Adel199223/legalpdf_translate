from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

import legalpdf_translate.word_automation as word_automation


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

    command = word_automation._build_pdf_export_powershell_command(docx_path, pdf_path)

    assert command is not None
    script = command[-1]
    assert str(docx_path.resolve()).replace("'", "''") in script
    assert str(pdf_path.resolve()).replace("'", "''") in script
    assert "$doc.ExportAsFixedFormat($pdfPath, $wdExportFormatPDF)" in script
    assert "$doc.Close([ref]$false)" in script
    assert "$word.Quit()" in script


def test_build_pdf_preflight_powershell_command_starts_and_quits_word(monkeypatch) -> None:
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )

    command = word_automation._build_pdf_preflight_powershell_command()

    assert command is not None
    script = command[-1]
    assert "New-Object -ComObject Word.Application" in script
    assert "$word.Quit()" in script


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
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
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
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="OK", stderr=""),
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
        "run",
        lambda *args, **kwargs: (pdf_path.write_bytes(b"%PDF-1.7"), SimpleNamespace(returncode=0, stdout="OK", stderr=""))[1],
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
        "run",
        lambda *args, **kwargs: SimpleNamespace(
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


def test_probe_word_pdf_export_support_classifies_timeout(monkeypatch) -> None:
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(
        word_automation,
        "_resolve_powershell_path",
        lambda: r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    )

    def _raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(
            cmd=args[0],
            timeout=kwargs.get("timeout", 8),
            stderr="Word.Application launch timed out",
        )

    monkeypatch.setattr(word_automation.subprocess, "run", _raise_timeout)

    result = word_automation.probe_word_pdf_export_support()

    assert result.ok is False
    assert result.failure_code == "timeout"
    assert result.message == "Word PDF export timed out."
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
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="OK", stderr=""),
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
