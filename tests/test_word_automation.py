from __future__ import annotations

from pathlib import Path
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


def test_open_docx_in_word_is_unsupported_off_windows(tmp_path: Path, monkeypatch) -> None:
    docx_path = tmp_path / "arabic.docx"
    docx_path.write_bytes(b"docx")

    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: False)

    result = word_automation.open_docx_in_word(docx_path)

    assert result.ok is False
    assert result.message == "Word automation is available only on Windows."
