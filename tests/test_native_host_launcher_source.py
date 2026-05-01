from __future__ import annotations

from pathlib import Path


def _launcher_source() -> str:
    return Path("tooling/native_host_launcher/LegalPDFGmailFocusHostLauncher.cs").read_text(
        encoding="utf-8"
    )


def test_native_host_launcher_reads_single_framed_message() -> None:
    text = _launcher_source()

    assert "ReadSingleNativeMessageAsync" in text
    assert "WriteSingleNativeMessageToChildAsync" in text
    assert "await source.CopyToAsync(process.StandardInput.BaseStream)" not in text
    assert "sendNativeMessage() response" in text


def test_native_host_launcher_keeps_console_python_first_for_native_messaging_stdio() -> None:
    text = _launcher_source()

    python_index = text.index('Path.Combine(repoRoot, ".venv311", "Scripts", "python.exe")')
    pythonw_index = text.index('Path.Combine(repoRoot, ".venv311", "Scripts", "pythonw.exe")')

    assert python_index < pythonw_index
