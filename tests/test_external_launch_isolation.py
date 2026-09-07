"""Pure safety regressions: unit fixtures cannot launch associated desktop apps."""
import os
import subprocess

import pytest

import legalpdf_translate.word_automation as word_automation


def test_unmocked_file_association_launch_is_blocked_even_by_exception_fallback():
    with pytest.raises(pytest.fail.Exception, match="External file launch blocked"):
        try:
            os.startfile("synthetic-invalid-arabic.docx")
        except Exception:
            pytest.fail("The isolation guard must escape production fallback handlers.")


def test_file_association_behavior_can_be_explicitly_mocked(monkeypatch):
    calls = []
    monkeypatch.setattr(os, "startfile", calls.append)
    os.startfile("synthetic-invalid-arabic.docx")
    assert calls == ["synthetic-invalid-arabic.docx"]


@pytest.mark.parametrize("action", ["probe", "export", "cleanup"])
def test_unmocked_native_word_and_cleanup_are_blocked(action, tmp_path, monkeypatch):
    monkeypatch.setattr(word_automation, "_is_windows_host", lambda: True)
    monkeypatch.setattr(word_automation, "_resolve_powershell_path", lambda: "powershell.exe")
    monkeypatch.setattr(word_automation, "_resolve_winword_path", lambda: None)
    monkeypatch.setattr(word_automation, "_resolve_taskkill_path", lambda: "taskkill.exe")
    docx = tmp_path / "synthetic-invalid.docx"
    docx.write_bytes(b"not a real document")

    with pytest.raises(pytest.fail.Exception, match="Native Word execution blocked"):
        try:
            if action == "probe":
                word_automation.probe_word_pdf_export_support()
            elif action == "export":
                word_automation.export_docx_to_pdf_in_word(docx, tmp_path / "out.pdf")
            else:
                word_automation._terminate_windows_process_tree(4242)
        except Exception:
            pytest.fail("The Word guard must escape production fallback handlers.")


def test_native_word_guard_is_module_local_and_allows_explicit_recording_mock(monkeypatch):
    assert word_automation.subprocess is not subprocess
    assert word_automation.subprocess.PIPE == subprocess.PIPE
    assert word_automation.subprocess.TimeoutExpired is subprocess.TimeoutExpired
    calls = []
    monkeypatch.setattr(word_automation.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)))
    word_automation.subprocess.Popen(["synthetic-word-helper"])
    assert calls == [((["synthetic-word-helper"],), {})]


def test_native_word_guard_survives_nested_test_mock_restoration(monkeypatch):
    with monkeypatch.context() as test_patch:
        test_patch.setattr(word_automation.subprocess, "run", lambda *args, **kwargs: "recorded")
        assert word_automation.subprocess.run(["synthetic-cleanup"]) == "recorded"
    with pytest.raises(pytest.fail.Exception, match="Native Word execution blocked"):
        word_automation.subprocess.run(["synthetic-cleanup"])
