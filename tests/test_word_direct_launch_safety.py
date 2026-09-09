"""Offline ownership regressions around direct Word launch.

The shared harness removes every native definition and launch before executing
PowerShell. These extra observations make process/window acquisition visible,
not merely the later document mutations. No real Word process is created.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests import test_word_pdf_script as fake_helper


pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only"
)


def _replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, "Shared fake-runtime contract changed"
    return text.replace(old, new, 1)


def _observe_acquisition(monkeypatch: pytest.MonkeyPatch, *, user_pid: int | None = None) -> None:
    runtime = fake_helper._FAKE_RUNTIME
    runtime = _replace_once(
        runtime,
        'public static string Scenario = "success";',
        'public static string Scenario = "success";\n'
        "        public static int RefreshCount;",
    )
    runtime = _replace_once(
        runtime,
        "public static FakeProcess GetProcessById(int pid) { return new FakeProcess { Id = pid }; }",
        'public static FakeProcess GetProcessById(int pid) {\n'
        '            Runtime.Record("lookup_process_" + pid, null);\n'
        '            if (pid != 789) throw new Exception("Unowned process lookup");\n'
        "            return new FakeProcess { Id = pid };\n"
        "        }",
    )
    runtime = _replace_once(
        runtime,
        "public void Refresh() { }",
        "public void Refresh() {\n"
        "            Runtime.RefreshCount++;\n"
        '            if (Runtime.RefreshCount == 2) {\n'
        '                if (Runtime.Scenario == "reuse_before_binding") Runtime.Reused = true;\n'
        '                if (Runtime.Scenario == "exit_before_binding") Runtime.WordExited = true;\n'
        '                if (Runtime.Scenario == "pid_change_before_binding") Id = 790;\n'
        "            }\n"
        "        }",
    )
    runtime = _replace_once(
        runtime,
        "public static IntPtr[] FindDocumentWindows(int pid) { return new IntPtr[] { new IntPtr(123) }; }",
        "public static IntPtr[] FindDocumentWindows(int pid) {\n"
        '            WordPdfTest.Runtime.Record("find_window_" + pid, null);\n'
        '            if (pid != 789) throw new Exception("Unowned window lookup");\n'
        "            return new IntPtr[] { new IntPtr(123) };\n"
        "        }",
    )
    runtime = _replace_once(
        runtime,
        "public static object GetNativeWordWindow(IntPtr hwnd, int expectedPid) {",
        "public static object GetNativeWordWindow(IntPtr hwnd, int expectedPid) {\n"
        '            WordPdfTest.Runtime.Record("bind_window_" + expectedPid, null);',
    )
    monkeypatch.setattr(fake_helper, "_FAKE_RUNTIME", runtime)

    if user_pid is not None:
        original_builder = fake_helper.build_pdf_script

        def with_existing_user_process(*args, **kwargs):
            script = original_builder(*args, **kwargs)
            return _replace_once(
                script,
                "@(Get-Process -Name WINWORD -ErrorAction SilentlyContinue |\n"
                "        ForEach-Object { $_.Id })",
                f"@({user_pid})",
            )

        monkeypatch.setattr(fake_helper, "build_pdf_script", with_existing_user_process)


def _assert_no_binding_or_mutation(events: list[str]) -> None:
    assert not any(event.startswith(("find_window_", "bind_window_")) for event in events)
    assert not {"visible", "security", "open", "export", "close", "quit"}.intersection(events)


@pytest.mark.parametrize("export", [False, True])
def test_direct_owned_start_coexists_with_unrelated_user_word(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, export: bool
) -> None:
    _observe_acquisition(monkeypatch, user_pid=321)
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success", export=export)

    assert result.returncode == 0, (state, result.stderr)
    assert state["ownership"] == "proven"
    assert state["cleanup_status"] == "confirmed"
    assert state["word_pid"] == 789
    assert state["startup_identity_checks"]["new_pid"] is True
    assert events.count("launch") == 1
    assert events.count("find_window_789") == 1
    assert events.count("bind_window_789") == 1
    assert events.count("quit") == 1
    assert events.count("open") == int(export)
    assert events.count("close") == int(export)
    assert events.count("export") == int(export)
    # Startup ownership uses the returned object, not a process-name/PID search.
    # GetProcessById is allowed only after scoped Quit to confirm owned exit.
    lookups = [event for event in events if event.startswith("lookup_process_")]
    assert lookups == ["lookup_process_789"]
    assert events.index("quit") < events.index("lookup_process_789")
    assert not any("321" in event for event in events)


@pytest.mark.parametrize(
    ("scenario", "reason"),
    [
        ("missing_launcher", "failed_process_returned"),
        ("exited_launcher", "failed_running"),
        ("wrong_session", "failed_session_matches"),
        ("wrong_name", "failed_name_matches"),
        ("old_start", "failed_start_not_before_launch"),
        ("wrong_executable", "failed_executable_matches"),
        ("identity_read_failure", "identity_read_failed"),
    ],
)
def test_rejected_direct_return_never_reaches_window_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, reason: str
) -> None:
    # A different user's Word may already exist. Even though the fake native
    # window provider could return a Word object, rejected launch cannot use it.
    _observe_acquisition(monkeypatch, user_pid=321)
    result, state, events = fake_helper._run_fake_helper(tmp_path, scenario)

    assert result.returncode == 1, state
    assert state["failure_code"] == "ownership_unproven"
    assert state["startup_identity_reason"] == reason
    assert state["process_identity_verified"] is False
    assert state["word_identity_verified"] is False
    assert state["document_owned"] is False
    assert state["cleanup_status"] == "ambiguous"
    assert events == ["launch"]
    _assert_no_binding_or_mutation(events)


@pytest.mark.parametrize(
    ("scenario", "cleanup"),
    [
        ("reuse_before_binding", "confirmed"),
        ("exit_before_binding", "confirmed"),
        ("pid_change_before_binding", "ambiguous"),
    ],
)
def test_identity_change_after_launch_proof_stops_before_window_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, cleanup: str
) -> None:
    _observe_acquisition(monkeypatch, user_pid=321)
    result, state, events = fake_helper._run_fake_helper(tmp_path, scenario)

    assert result.returncode == 1, state
    assert state["startup_identity_reason"] == "verified"
    assert state["process_identity_verified"] is True
    assert state["primary_failure_phase"] == "find_word_window"
    assert state["failure_code"] == "ownership_unproven"
    assert state["word_identity_verified"] is False
    assert state["document_owned"] is False
    assert state["cleanup_status"] == cleanup
    assert state["word_pid"] == 789
    assert events.count("launch") == 1
    assert not any("790" in event or "321" in event for event in events)
    _assert_no_binding_or_mutation(events)
