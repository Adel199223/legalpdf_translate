from __future__ import annotations

import json
from pathlib import Path

from legalpdf_translate import gmail_window_trace as trace_module


def test_summarize_window_trace_samples_flags_duplicate_and_blank_edge_windows(tmp_path: Path) -> None:
    trace_dir = tmp_path / "window_traces" / "launch-1"
    samples_path = trace_dir / "samples.jsonl"
    samples = [
        {
            "sample_index": 0,
            "windows": [
                {
                    "hwnd": 101,
                    "title": "LegalPDF Translate Browser App",
                    "class_name": "Chrome_WidgetWin_1",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 1280, "height": 900},
                    "process_image_path": r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                },
                {
                    "hwnd": 102,
                    "title": "",
                    "class_name": "Chrome_WidgetWin_1",
                    "visible": False,
                    "minimized": True,
                    "cloaked": True,
                    "rect": {"width": 20, "height": 20},
                    "process_image_path": r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                },
                {
                    "hwnd": 999,
                    "title": "Windows Terminal",
                    "class_name": "CASCADIA_HOSTING_WINDOW_CLASS",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 1280, "height": 900},
                    "process_image_path": r"C:\Program Files\WindowsApps\wt.exe",
                },
                {
                    "hwnd": 998,
                    "title": "Codex",
                    "class_name": "Chrome_WidgetWin_1",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 1280, "height": 900},
                    "process_image_path": r"C:\Program Files\WindowsApps\OpenAI.Codex\Codex.exe",
                },
            ],
        },
        {
            "sample_index": 1,
            "windows": [
                {
                    "hwnd": 101,
                    "title": "LegalPDF Translate Browser App",
                    "class_name": "Chrome_WidgetWin_1",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 1280, "height": 900},
                    "process_image_path": r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                },
                {
                    "hwnd": 103,
                    "title": "LegalPDF Translate Browser App",
                    "class_name": "Chrome_WidgetWin_1",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 900, "height": 700},
                    "process_image_path": r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                },
            ],
        },
    ]

    summary = trace_module.summarize_window_trace_samples(
        samples,
        launch_session_id="launch-1",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
        trace_dir=trace_dir,
        samples_path=samples_path,
    )

    assert summary["launch_session_id"] == "launch-1"
    assert summary["max_edge_window_count"] == 2
    assert summary["max_legalpdf_surface_count"] == 2
    assert summary["max_visible_edge_surface_count"] == 2
    assert summary["max_visible_legalpdf_surface_count"] == 2
    assert summary["blank_or_cloaked_browser_window_count"] == 1
    assert summary["hidden_or_cloaked_edge_utility_count"] == 1
    assert summary["new_top_level_edge_window_count"] == 1
    assert summary["new_top_level_edge_hwnd_ids"] == [103]
    assert summary["edge_title_transition_count"] == 0
    assert summary["new_tab_to_legalpdf_transition_count"] == 0
    assert summary["title_transition_events"] == []
    assert summary["flags"] == {
        "multiple_edge_windows_detected": True,
        "blank_or_cloaked_browser_windows_detected": True,
        "repeated_window_churn_detected": True,
        "multiple_legalpdf_surfaces_detected": True,
        "multiple_visible_edge_surfaces_detected": True,
        "multiple_visible_legalpdf_surfaces_detected": True,
        "hidden_or_cloaked_edge_utilities_detected": True,
        "new_top_level_edge_windows_detected": True,
        "new_tab_to_legalpdf_transition_detected": False,
        "console_helper_windows_detected": False,
        "multiple_visible_console_helper_windows_detected": False,
        "repeated_console_helper_window_churn_detected": False,
        "new_top_level_console_helper_windows_detected": False,
    }


def test_summarize_window_trace_samples_detects_new_tab_to_legalpdf_transition(tmp_path: Path) -> None:
    trace_dir = tmp_path / "window_traces" / "launch-2"
    samples_path = trace_dir / "samples.jsonl"
    samples = [
        {
            "sample_index": 0,
            "relative_ms": 0,
            "windows": [
                {
                    "hwnd": 501,
                    "title": "New tab - Personal - Microsoft Edge",
                    "class_name": "Chrome_WidgetWin_1",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 1280, "height": 900},
                    "process_image_path": r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                },
            ],
        },
        {
            "sample_index": 1,
            "relative_ms": 5000,
            "windows": [
                {
                    "hwnd": 501,
                    "title": "LegalPDF Translate Browser App and 1 more page - Personal - Microsoft Edge",
                    "class_name": "Chrome_WidgetWin_1",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 1280, "height": 900},
                    "process_image_path": r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                },
            ],
        },
    ]

    summary = trace_module.summarize_window_trace_samples(
        samples,
        launch_session_id="launch-2",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
        trace_dir=trace_dir,
        samples_path=samples_path,
        launched_browser_metadata={
            "browser_launch_status": "server_only",
            "browser_launch_reason": "extension_browser_surface_owner",
        },
    )

    assert summary["new_top_level_edge_window_count"] == 0
    assert summary["edge_title_transition_count"] == 1
    assert summary["new_tab_to_legalpdf_transition_count"] == 1
    assert summary["title_transition_events"] == [
        {
            "hwnd": 501,
            "from_title": "New tab - Personal - Microsoft Edge",
            "to_title": "LegalPDF Translate Browser App and 1 more page - Personal - Microsoft Edge",
            "sample_index": 1,
            "relative_ms": 5000,
        }
    ]
    assert summary["flags"]["new_tab_to_legalpdf_transition_detected"] is True
    assert summary["browser_launch_status"] == "server_only"
    assert summary["browser_launch_reason"] == "extension_browser_surface_owner"


def test_summarize_window_trace_samples_detects_console_helper_window_churn(tmp_path: Path) -> None:
    trace_dir = tmp_path / "window_traces" / "launch-3"
    samples_path = trace_dir / "samples.jsonl"
    samples = [
        {
            "sample_index": 0,
            "relative_ms": 0,
            "windows": [
                {
                    "hwnd": 701,
                    "title": "Python",
                    "class_name": "ConsoleWindowClass",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 840, "height": 600},
                    "process_image_path": r"C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe",
                },
            ],
        },
        {
            "sample_index": 1,
            "relative_ms": 200,
            "windows": [
                {
                    "hwnd": 701,
                    "title": "Python",
                    "class_name": "ConsoleWindowClass",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 840, "height": 600},
                    "process_image_path": r"C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe",
                },
                {
                    "hwnd": 702,
                    "title": "Console Host",
                    "class_name": "ConsoleWindowClass",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "rect": {"width": 840, "height": 600},
                    "process_image_path": r"C:\Windows\System32\conhost.exe",
                },
            ],
        },
    ]

    summary = trace_module.summarize_window_trace_samples(
        samples,
        launch_session_id="launch-3",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
        trace_dir=trace_dir,
        samples_path=samples_path,
        launched_browser_metadata={
            "launch_runtime_path": r"C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe",
            "native_host_path_kind": "cmd",
        },
    )

    assert summary["max_console_helper_window_count"] == 2
    assert summary["max_visible_console_helper_window_count"] == 2
    assert summary["console_helper_churn_events"] == 1
    assert summary["new_top_level_console_helper_window_count"] == 1
    assert summary["new_top_level_console_helper_hwnd_ids"] == [702]
    assert summary["unique_console_helper_window_count"] == 2
    assert summary["unique_visible_console_helper_window_count"] == 2
    assert summary["launch_runtime_path"] == r"C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe"
    assert summary["native_host_path_kind"] == "cmd"
    assert summary["flags"]["console_helper_windows_detected"] is True
    assert summary["flags"]["multiple_visible_console_helper_windows_detected"] is True
    assert summary["flags"]["new_top_level_console_helper_windows_detected"] is True


def test_pseudoconsole_window_counts_as_visible_console_helper(tmp_path: Path) -> None:
    trace_dir = tmp_path / "window_traces" / "launch-4"
    samples_path = trace_dir / "samples.jsonl"
    samples = [
        {
            "sample_index": 0,
            "relative_ms": 0,
            "windows": [
                {
                    "hwnd": 801,
                    "title": "",
                    "class_name": "PseudoConsoleWindow",
                    "visible": True,
                    "minimized": False,
                    "cloaked": False,
                    "owner_hwnd": 800,
                    "rect": {"width": 0, "height": 0},
                    "process_image_path": r"C:\Windows\System32\cmd.exe",
                },
            ],
        },
    ]

    summary = trace_module.summarize_window_trace_samples(
        samples,
        launch_session_id="launch-4",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
        trace_dir=trace_dir,
        samples_path=samples_path,
    )

    assert summary["max_console_helper_window_count"] == 1
    assert summary["max_visible_console_helper_window_count"] == 1
    assert summary["flags"]["console_helper_windows_detected"] is True


def test_arm_and_consume_window_trace_round_trip(tmp_path: Path) -> None:
    armed = trace_module.arm_next_cold_start_window_trace(base_dir=tmp_path, duration_seconds=12, sample_interval_ms=250)

    assert armed["armed"] is True
    assert Path(armed["arm_path"]).exists()

    consumed = trace_module.consume_armed_window_trace(tmp_path)

    assert consumed is not None
    assert consumed["duration_seconds"] == 12.0
    assert consumed["sample_interval_ms"] == 250
    assert not Path(armed["arm_path"]).exists()


def test_latest_window_trace_status_reads_saved_summary(tmp_path: Path) -> None:
    session_id = "launch-42"
    trace_dir = trace_module.launch_session_trace_dir(tmp_path, session_id)
    trace_dir.mkdir(parents=True)
    summary_path = trace_dir / "summary.json"
    summary_path.write_text(json.dumps({"flags": {"multiple_edge_windows_detected": True}}), encoding="utf-8")
    trace_module.write_launch_session_state(
        tmp_path,
        {
            "launch_session_id": session_id,
            "status": "launch_ready",
            "trace_status": "completed",
            "trace_requested": True,
            "trace_dir": str(trace_dir),
            "trace_summary_path": str(summary_path),
        },
    )

    status = trace_module.latest_window_trace_status(tmp_path)

    assert status["launch_session_id"] == session_id
    assert status["trace_status"] == "completed"
    assert status["trace_summary"] == {"flags": {"multiple_edge_windows_detected": True}}


def test_latest_window_trace_status_surfaces_launched_browser_metadata(tmp_path: Path) -> None:
    session_id = "launch-77"
    trace_module.write_launch_session_state(
        tmp_path,
        {
            "launch_session_id": session_id,
            "status": "launch_ready",
            "browser_launch_status": "launch_spawned",
            "browser_launch_reason": "explicit_edge_launch_spawned",
            "launched_browser_pid": 4242,
            "launched_browser_path": r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            "launched_browser_user_data_dir": r"C:\Users\FA507\AppData\Local\Microsoft\Edge\User Data",
            "launched_browser_profile": "Profile 2",
            "launched_browser_command": r"msedge.exe --profile-directory=Profile 2 http://127.0.0.1:8877/",
            "launch_runtime_path": r"C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\pythonw.exe",
            "native_host_path_kind": "exe",
            "launch_phase": "server_boot_ready",
            "tab_resolution_strategy": "created_exact_tab",
            "handoff_session_id": "handoff-77",
            "workspace_surface_confirmed": True,
            "client_hydration_status": "warming",
            "surface_candidate_source": "fresh_exact_tab",
            "surface_candidate_valid": True,
            "surface_invalidation_reason": "launch_session_mismatch",
            "fresh_tab_created_after_invalidation": True,
            "bridge_context_posted": True,
            "surface_visibility_status": "visible",
            "extension_surface_outcome": "warming",
            "extension_surface_reason": "workspace_pending_with_confirmed_surface",
            "extension_surface_tab_id": 91,
        },
    )

    status = trace_module.latest_window_trace_status(tmp_path)

    assert status["browser_launch_status"] == "launch_spawned"
    assert status["browser_launch_reason"] == "explicit_edge_launch_spawned"
    assert status["launched_browser_pid"] == 4242
    assert status["launched_browser_profile"] == "Profile 2"
    assert status["launch_runtime_path"] == r"C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\pythonw.exe"
    assert status["native_host_path_kind"] == "exe"
    assert status["launch_phase"] == "server_boot_ready"
    assert status["tab_resolution_strategy"] == "created_exact_tab"
    assert status["handoff_session_id"] == "handoff-77"
    assert status["workspace_surface_confirmed"] is True
    assert status["client_hydration_status"] == "warming"
    assert status["surface_candidate_source"] == "fresh_exact_tab"
    assert status["surface_candidate_valid"] is True
    assert status["surface_invalidation_reason"] == "launch_session_mismatch"
    assert status["fresh_tab_created_after_invalidation"] is True
    assert status["bridge_context_posted"] is True
    assert status["surface_visibility_status"] == "visible"
    assert status["extension_surface_outcome"] == "warming"
    assert status["extension_surface_reason"] == "workspace_pending_with_confirmed_surface"
    assert status["extension_surface_tab_id"] == 91
