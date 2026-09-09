"""Privacy-safe startup observations, exercised with no native Word execution.

The shared harness removes the complete production native declaration and
replaces every process, window, and COM entry point before running PowerShell.
Only the synthetic getters below vary; diagnostic fields must not grant any
authority to bind, change settings, open documents, or clean up an instance.
"""

from __future__ import annotations

import importlib
import json
import os
from pathlib import Path

import pytest

from legalpdf_translate import word_pdf_control
from tests import test_word_pdf_script as fake_helper


WINDOWS_FAKE = pytest.mark.skipif(
    os.name != "nt", reason="PowerShell fake-runtime harness is Windows-only"
)


def _replace_once(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, "Shared fake-runtime contract changed"
    return text.replace(old, new, 1)


def _observe_startup(
    monkeypatch: pytest.MonkeyPatch,
    *,
    name_body: str | None = None,
    executable_body: str | None = None,
) -> None:
    """Add bounded fake read/acquisition events, without logging getter values."""
    runtime = fake_helper._FAKE_RUNTIME
    runtime = _replace_once(
        runtime,
        'public string ProcessName { get { return Id == 789 ? (Runtime.Scenario == "wrong_name" ? "OTHER" : "WINWORD") : "powershell"; } }',
        "public object ProcessName { get {\n"
        '            Runtime.Record("read_name", null);\n'
        + (name_body or 'return Id == 789 ? (Runtime.Scenario == "wrong_name" ? "OTHER" : "WINWORD") : "powershell";')
        + "\n        } }",
    )
    runtime = _replace_once(
        runtime,
        "public class FakeModule { public string FileName { get {\n"
        '        if (Runtime.Scenario == "identity_read_failure") throw new Exception("PRIVATE_DOCUMENT_TEXT C:/private/case.docx");\n'
        '        return Runtime.Scenario == "wrong_executable" ? "C:/unrelated/WINWORD.EXE" : Runtime.Executable;\n'
        "    } } }",
        "public class FakeModule { public object FileName { get {\n"
        '        Runtime.Record("read_executable", null);\n'
        + (
            executable_body
            or 'if (Runtime.Scenario == "identity_read_failure") throw new Exception("PRIVATE_DOCUMENT_TEXT C:/private/case.docx");\n'
            '        return Runtime.Scenario == "wrong_executable" ? "C:/unrelated/WINWORD.EXE" : Runtime.Executable;'
        )
        + "\n    } } }",
    )
    runtime = _replace_once(
        runtime,
        "public static IntPtr[] FindDocumentWindows(int pid) { return new IntPtr[] { new IntPtr(123) }; }",
        "public static IntPtr[] FindDocumentWindows(int pid) {\n"
        '            WordPdfTest.Runtime.Record("find_window", null);\n'
        "            return new IntPtr[] { new IntPtr(123) };\n"
        "        }",
    )
    runtime = _replace_once(
        runtime,
        "public static object GetNativeWordWindow(IntPtr hwnd, int expectedPid) {",
        "public static object GetNativeWordWindow(IntPtr hwnd, int expectedPid) {\n"
        '            WordPdfTest.Runtime.Record("bind_window", null);',
    )
    monkeypatch.setattr(fake_helper, "_FAKE_RUNTIME", runtime)


def _assert_metadata(state: dict) -> None:
    assert state["schema_version"] == 1  # Existing journal schema stays readable.
    assert state["startup_diagnostics_version"] == 2
    assert state["startup_launch_method"] == "create_process_hidden_v1"
    assert state["startup_expected_process_name"] == "WINWORD"
    assert state["startup_process_name_source"] == "retained_launch_handle"
    assert all(value is None or type(value) is bool for value in state["startup_identity_checks"].values())


def _assert_rejected(result, state: dict, events: list[str], reason: str) -> None:
    _assert_metadata(state)
    assert result.returncode == 1, state
    assert state["failure_code"] == "ownership_unproven"
    assert state["primary_failure_phase"] == "launch_word"
    assert state["startup_identity_reason"] == reason
    assert state["ownership"] == "rejected"
    assert state["process_identity_verified"] is False
    assert state["word_identity_verified"] is False
    assert state["document_owned"] is False
    assert state["bootstrap_owned"] is False
    assert state["cleanup_status"] == "ambiguous"
    assert events.count("launch") == 1
    assert not {
        "find_window", "bind_window", "hwnd", "visible", "security", "open",
        "export", "close", "close_bootstrap", "quit", "wait_exit", "release",
    }.intersection(events)


@WINDOWS_FAKE
@pytest.mark.parametrize("name", ["WINWORD", "winword", "WiNwOrD"])
def test_valid_process_name_preserves_exact_case_and_existing_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    _observe_startup(monkeypatch, name_body=f"return {json.dumps(name)};")
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success")

    _assert_metadata(state)
    assert result.returncode == 0, (state, result.stderr)
    assert state["startup_process_name_status"] == "captured"
    assert state["startup_process_name"] == name
    assert state["startup_executable_status"] == "compared"
    assert all(value is True for value in state["startup_identity_checks"].values())
    assert state["ownership"] == "proven"
    assert state["cleanup_status"] == "confirmed"
    for event in ("launch", "find_window", "bind_window", "open", "export", "close", "quit"):
        assert events.count(event) == 1
    assert "close_bootstrap" not in events
    # Further reads are existing fresh ownership guards, not diagnostics.
    assert events[:3] == ["launch", "read_name", "read_executable"]


@WINDOWS_FAKE
@pytest.mark.parametrize("name", ["OTHER", "WINWORD.EXE", "A", "a._-9", "A" * 64])
def test_safe_unexpected_name_is_retained_without_authorizing_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    _observe_startup(monkeypatch, name_body=f"return {json.dumps(name)};")
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success")

    _assert_rejected(result, state, events, "failed_name_matches")
    assert state["startup_process_name_status"] == "captured"
    assert state["startup_process_name"] == name
    assert state["startup_executable_status"] == "not_observed"
    assert state["startup_identity_checks"]["name_matches"] is False
    assert state["startup_identity_checks"]["start_not_before_launch"] is None
    assert state["startup_identity_checks"]["executable_matches"] is None
    assert events == ["launch", "read_name"]


@WINDOWS_FAKE
@pytest.mark.parametrize(
    "name",
    [
        "A" * 65,
        "C:\\private\\case.docx",
        "C:/private/case.docx",
        "PRIVATE_DOCUMENT_TEXT C:/private/case.docx",
        "WINWORD\n",
        "WINWORD\r\n",
        "WINWORD\t",
        "OTHER\x00",
        "WINWÖRD",
        "OTHER\u202e",
        ".WINWORD",
        "-WINWORD",
    ],
)
def test_unsafe_name_is_redacted_but_never_substituted_into_identity_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    _observe_startup(monkeypatch, name_body=f"return {json.dumps(name, ensure_ascii=True)};")
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success")

    _assert_rejected(result, state, events, "failed_name_matches")
    assert state["startup_process_name_status"] == "redacted"
    assert state["startup_process_name"] is None
    assert state["startup_executable_status"] == "not_observed"
    assert state["startup_identity_checks"]["name_matches"] is False
    assert events == ["launch", "read_name"]
    serialized = json.dumps(state, ensure_ascii=False)
    assert name not in serialized
    assert name not in result.stdout + result.stderr


@WINDOWS_FAKE
@pytest.mark.parametrize("name_body", [
    "return null;", 'return "";', 'return " \\t";', "return 17;", "return true;",
    "return new object();", 'return new string[] { "WINWORD", "OTHER" };',
])
def test_invalid_name_is_not_coerced_or_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name_body: str
) -> None:
    _observe_startup(monkeypatch, name_body=name_body)
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success")

    _assert_rejected(result, state, events, "identity_read_failed")
    assert state["startup_process_name_status"] == "invalid"
    assert state["startup_process_name"] is None
    assert state["startup_executable_status"] == "not_observed"
    assert state["startup_identity_checks"]["name_matches"] is None
    assert events == ["launch", "read_name"]


@WINDOWS_FAKE
def test_name_getter_failure_remains_unknown_without_private_error_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _observe_startup(
        monkeypatch,
        name_body='throw new Exception("PRIVATE_DOCUMENT_TEXT C:/private/case.docx");',
    )
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success")

    _assert_rejected(result, state, events, "identity_read_failed")
    # PowerShell's managed property adapter presents this throwing getter as a
    # null observation. This is not evidence distinguishing null from a throw.
    assert state["startup_process_name_status"] == "invalid"
    assert state["startup_process_name"] is None
    assert state["startup_executable_status"] == "not_observed"
    assert state["startup_identity_checks"]["name_matches"] is None
    assert events == ["launch", "read_name"]


@WINDOWS_FAKE
@pytest.mark.parametrize("name", ["WINWORD\x00", "WINWORD\u202e"])
def test_redaction_does_not_replace_existing_name_or_later_identity_predicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    # The pre-existing PowerShell case-insensitive comparison ignores these
    # characters. Redaction is deliberately not a new identity allow/deny rule;
    # the independent exact executable guard must still reject before binding.
    _observe_startup(monkeypatch, name_body=f"return {json.dumps(name)};")
    result, state, events = fake_helper._run_fake_helper(tmp_path, "wrong_executable")

    _assert_rejected(result, state, events, "failed_executable_matches")
    assert state["startup_process_name_status"] == "redacted"
    assert state["startup_process_name"] is None
    assert state["startup_identity_checks"]["name_matches"] is True
    assert state["startup_identity_checks"]["start_not_before_launch"] is True
    assert state["startup_identity_checks"]["executable_matches"] is False
    assert state["startup_executable_status"] == "compared"
    assert events == ["launch", "read_name", "read_executable"]


@WINDOWS_FAKE
@pytest.mark.parametrize(("scenario", "reason"), [
    ("missing_launcher", "failed_process_returned"),
    ("exited_launcher", "failed_running"),
    ("preexisting", "failed_new_pid"),
    ("wrong_session", "failed_session_matches"),
])
def test_earlier_failed_guard_does_not_read_name_or_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, scenario: str, reason: str
) -> None:
    _observe_startup(monkeypatch)
    result, state, events = fake_helper._run_fake_helper(tmp_path, scenario)

    _assert_rejected(result, state, events, reason)
    assert state["startup_process_name_status"] == "not_observed"
    assert state["startup_process_name"] is None
    assert state["startup_executable_status"] == "not_observed"
    assert state["startup_identity_checks"]["name_matches"] is None
    assert state["startup_identity_checks"]["executable_matches"] is None
    assert events == ["launch"]


@WINDOWS_FAKE
def test_failed_start_time_does_not_read_executable_after_captured_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _observe_startup(monkeypatch)
    result, state, events = fake_helper._run_fake_helper(tmp_path, "old_start")

    _assert_rejected(result, state, events, "failed_start_not_before_launch")
    assert state["startup_process_name_status"] == "captured"
    assert state["startup_process_name"] == "WINWORD"
    assert state["startup_executable_status"] == "not_observed"
    assert state["startup_identity_checks"]["executable_matches"] is None
    assert events == ["launch", "read_name"]


@WINDOWS_FAKE
def test_executable_getter_failure_has_no_raw_path_or_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _observe_startup(monkeypatch)
    result, state, events = fake_helper._run_fake_helper(tmp_path, "identity_read_failure")

    _assert_rejected(result, state, events, "identity_read_failed")
    assert state["startup_process_name"] == "WINWORD"
    # As with ProcessName, this managed getter exception is adapted to null.
    assert state["startup_executable_status"] == "invalid"
    assert state["startup_identity_checks"]["executable_matches"] is None
    assert events == ["launch", "read_name", "read_executable"]


@WINDOWS_FAKE
@pytest.mark.parametrize(
    ("expression", "status_field", "event", "expected_events"),
    [
        ("$wordProcess.ProcessName", "startup_process_name_status", "read_name", ["launch", "read_name"]),
        ("$wordProcess.MainModule.FileName", "startup_executable_status", "read_executable", ["launch", "read_name", "read_executable"]),
    ],
)
def test_propagated_observation_error_preserves_read_failed_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expression: str,
    status_field: str,
    event: str,
    expected_events: list[str],
) -> None:
    _observe_startup(monkeypatch)
    original_builder = fake_helper.build_pdf_script

    def with_propagated_observation_error(*args, **kwargs):
        # Inject an evaluation error (not the managed property-adapter case)
        # after the diagnostic read marker and inside the existing guard.
        script = original_builder(*args, **kwargs)
        return _replace_once(
            script,
            f"$observed = {expression}",
            "$observed = & { "
            f"[WordPdfTest.Runtime]::Record('{event}', $null); "
            "throw [InvalidOperationException]::new('PRIVATE_DOCUMENT_TEXT') }",
        )

    monkeypatch.setattr(fake_helper, "build_pdf_script", with_propagated_observation_error)
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success")

    _assert_rejected(result, state, events, "identity_read_failed")
    assert state[status_field] == "read_failed"
    assert events == expected_events


@WINDOWS_FAKE
@pytest.mark.parametrize("executable_body", ["return null;", 'return "";', 'return " ";', "return 17;"])
def test_invalid_executable_observation_is_not_coerced_or_logged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, executable_body: str
) -> None:
    _observe_startup(monkeypatch, executable_body=executable_body)
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success")

    _assert_rejected(result, state, events, "identity_read_failed")
    assert state["startup_process_name_status"] == "captured"
    assert state["startup_executable_status"] == "invalid"
    assert state["startup_identity_checks"]["executable_matches"] is None
    assert events == ["launch", "read_name", "read_executable"]


@WINDOWS_FAKE
def test_valid_but_mismatched_executable_records_only_comparison(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_path = "C:/SYNTHETIC_PRIVATE_EXECUTABLE/WINWORD.EXE"
    _observe_startup(monkeypatch, executable_body=f"return {json.dumps(private_path)};")
    result, state, events = fake_helper._run_fake_helper(tmp_path, "success")

    _assert_rejected(result, state, events, "failed_executable_matches")
    assert state["startup_process_name_status"] == "captured"
    assert state["startup_executable_status"] == "compared"
    assert state["startup_identity_checks"]["executable_matches"] is False
    assert events == ["launch", "read_name", "read_executable"]
    assert "SYNTHETIC_PRIVATE_EXECUTABLE" not in json.dumps(state) + result.stdout + result.stderr


def test_startup_diagnostics_read_existing_getters_once_without_extra_acquisition(tmp_path: Path) -> None:
    script = fake_helper._script(tmp_path)
    launch_check = script.split("function Test-LaunchIdentity {", 1)[1].split("function Assert-OwnedProcess", 1)[0]
    assert launch_check.count("$wordProcess.ProcessName") == 1
    assert launch_check.count("$wordProcess.MainModule.FileName") == 1
    assert "\\A[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\\z" in launch_check
    for forbidden in ("GetProcessById", "Get-Process", "FindDocumentWindows", "GetNativeWordWindow", "StartHidden", "Save()", ".Quit("):
        assert forbidden not in launch_check
    assert script.count("[LegalPdfWord.DirectProcess]::StartHidden($wordExecutable)") == 1
    assert "ParentProcessId" not in script
    assert "Win32_Process" not in script


@pytest.mark.parametrize("module_name", [
    "word_automation", "word_pdf_control", "word_pdf_script", "word_process_start",
])
def test_startup_diagnostic_test_imports_are_from_current_worktree(module_name: str) -> None:
    expected_source = Path(__file__).resolve().parents[1] / "src" / "legalpdf_translate"
    module = importlib.import_module(f"legalpdf_translate.{module_name}")
    assert Path(module.__file__).resolve() == expected_source / f"{module_name}.py"


@pytest.mark.parametrize("diagnostic_fields", [
    {},
    {"startup_diagnostics_version": 1, "startup_identity_reason": "failed_name_matches"},
    {
        "startup_diagnostics_version": 2,
        "startup_identity_reason": "verified",
        "startup_process_name_status": "captured",
        "startup_process_name": "WINWORD",
        "startup_executable_status": "compared",
    },
])
def test_legacy_and_new_journal_diagnostics_never_supply_recovery_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, diagnostic_fields: dict
) -> None:
    state = {
        "schema_version": 1,
        "status": "failed",
        "cleanup_status": "ambiguous",
        "helper_pid": 456,
        "helper_start_ticks": "123",
        "word_pid": 789,
        "word_start_ticks": "456",
        "process_identity_verified": False,
        "word_identity_verified": False,
        **diagnostic_fields,
    }
    journal = tmp_path / "synthetic-legacy-state.json"
    journal.write_text(json.dumps(state), encoding="utf-8")
    before = journal.read_bytes()
    observations = []
    monkeypatch.setattr(word_pdf_control, "_identity_gone", lambda pid, ticks: observations.append((pid, ticks)) or True)
    monkeypatch.setattr(word_pdf_control, "_stable_word_free", lambda: False)

    loaded = word_pdf_control.read_state(journal)
    assert loaded == state
    assert word_pdf_control._previous_operation_finished(loaded) is False
    assert observations == [(456, "123")]
    assert journal.read_bytes() == before
