from __future__ import annotations

from pathlib import Path

import legalpdf_translate.gmail_focus as gmail_focus


class _FakeWindow:
    def __init__(self, *, minimized: bool, hwnd: int = 101) -> None:
        self._minimized = minimized
        self._hwnd = hwnd
        self.calls: list[str] = []

    def isMinimized(self) -> bool:
        return self._minimized

    def showNormal(self) -> None:
        self.calls.append("showNormal")
        self._minimized = False

    def show(self) -> None:
        self.calls.append("show")

    def raise_(self) -> None:
        self.calls.append("raise")

    def activateWindow(self) -> None:
        self.calls.append("activate")

    def winId(self) -> int:
        return self._hwnd


def test_request_window_attention_is_noop_off_windows(monkeypatch) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: False)
    window = _FakeWindow(minimized=True)

    result = gmail_focus.request_window_attention(window)

    assert result == gmail_focus.WindowAttentionResult(
        requested=False,
        restored=False,
        focused=False,
        flashed=False,
        reason="unsupported_platform",
    )
    assert window.calls == []


def test_request_window_attention_restores_and_focuses_window(monkeypatch) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    monkeypatch.setattr(gmail_focus, "_show_window", lambda hwnd, command: hwnd == 101 and command == 9)
    monkeypatch.setattr(gmail_focus, "_set_foreground_window", lambda hwnd: hwnd == 101)
    monkeypatch.setattr(gmail_focus, "_get_foreground_window", lambda: 101)

    window = _FakeWindow(minimized=True)
    result = gmail_focus.request_window_attention(window)

    assert result == gmail_focus.WindowAttentionResult(
        requested=True,
        restored=True,
        focused=True,
        flashed=False,
        reason="foreground_set",
    )
    assert window.calls == ["showNormal", "raise", "activate"]


def test_request_window_attention_flashes_when_foreground_is_blocked(monkeypatch) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    monkeypatch.setattr(gmail_focus, "_show_window", lambda _hwnd, _command: False)
    monkeypatch.setattr(gmail_focus, "_set_foreground_window", lambda _hwnd: False)
    monkeypatch.setattr(gmail_focus, "_get_foreground_window", lambda: 404)
    monkeypatch.setattr(gmail_focus, "_flash_window", lambda hwnd: hwnd == 101)

    window = _FakeWindow(minimized=False)
    result = gmail_focus.request_window_attention(window)

    assert result == gmail_focus.WindowAttentionResult(
        requested=True,
        restored=False,
        focused=False,
        flashed=True,
        reason="foreground_blocked",
    )
    assert window.calls == ["show", "raise", "activate"]


def test_bridge_runtime_metadata_round_trips_and_clears(tmp_path: Path) -> None:
    path = gmail_focus.write_bridge_runtime_metadata(
        base_dir=tmp_path,
        port=9011,
        pid=4321,
        window_title="LegalPDF Translate",
        build_identity={"branch": "feat/ai-docs-bootstrap", "head_sha": "80a7312"},
        running=True,
    )

    payload = gmail_focus.load_bridge_runtime_metadata(tmp_path)

    assert path == tmp_path / "gmail_intake_bridge_runtime.json"
    assert payload is not None
    assert payload["port"] == 9011
    assert payload["pid"] == 4321
    assert payload["window_title"] == "LegalPDF Translate"
    assert payload["running"] is True
    assert payload["build_identity"] == {"branch": "feat/ai-docs-bootstrap", "head_sha": "80a7312"}
    assert "updated_at" in payload

    gmail_focus.clear_bridge_runtime_metadata(tmp_path)

    assert gmail_focus.load_bridge_runtime_metadata(tmp_path) is None


def test_parse_listener_pid_from_netstat_matches_localhost_listener() -> None:
    output = """
  Proto  Local Address          Foreign Address        State           PID
  TCP    127.0.0.1:9011         0.0.0.0:0              LISTENING       4321
  TCP    127.0.0.1:9012         0.0.0.0:0              LISTENING       5000
"""

    assert gmail_focus.parse_listener_pid_from_netstat(output, 9011) == 4321
    assert gmail_focus.parse_listener_pid_from_netstat(output, 9015) is None


def test_detect_listener_pid_prefers_tcp_table_lookup(monkeypatch) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    monkeypatch.setattr(gmail_focus, "_detect_listener_pid_from_tcp_table", lambda port: 4321 if port == 9011 else None)
    monkeypatch.setattr(gmail_focus, "_detect_listener_pid_from_netstat", lambda _port: 9999)

    assert gmail_focus.detect_listener_pid(9011) == 4321


def test_detect_listener_pid_falls_back_to_netstat_after_retries(monkeypatch) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    tcp_attempts = {"count": 0}
    netstat_attempts = {"count": 0}

    def fake_tcp_table(_port: int) -> int | None:
        tcp_attempts["count"] += 1
        return None

    def fake_netstat(_port: int) -> int | None:
        netstat_attempts["count"] += 1
        return 4321 if netstat_attempts["count"] == 2 else None

    monkeypatch.setattr(gmail_focus, "_detect_listener_pid_from_tcp_table", fake_tcp_table)
    monkeypatch.setattr(gmail_focus, "_detect_listener_pid_from_netstat", fake_netstat)
    monkeypatch.setattr(gmail_focus.time, "sleep", lambda _seconds: None)

    assert gmail_focus.detect_listener_pid(9011) == 4321
    assert tcp_attempts["count"] == 2
    assert netstat_attempts["count"] == 2


def test_detect_listener_pid_trusts_listener_probe_without_extra_liveness_gate(monkeypatch) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    monkeypatch.setattr(gmail_focus, "_detect_listener_pid_from_tcp_table", lambda _port: 4321)
    monkeypatch.setattr(gmail_focus, "_detect_listener_pid_from_netstat", lambda _port: None)
    monkeypatch.setattr(gmail_focus, "_pid_is_running", lambda pid: False if pid == 4321 else True)
    monkeypatch.setattr(gmail_focus.time, "sleep", lambda _seconds: None)

    assert gmail_focus.detect_listener_pid(9011) == 4321


def test_pid_is_running_handles_windows_invalid_handle_systemerror(monkeypatch) -> None:
    def fake_kill(_pid: int, _signal: int) -> None:
        raise SystemError("<built-in function kill> returned a result with an exception set")

    monkeypatch.setattr(gmail_focus.os, "kill", fake_kill)

    assert gmail_focus._pid_is_running(4321) is False


def test_focus_bridge_owner_rejects_missing_runtime_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)

    result = gmail_focus.focus_bridge_owner(bridge_port=9011, base_dir=tmp_path)

    assert result == gmail_focus.BridgeFocusResult(
        ok=False,
        focused=False,
        flashed=False,
        reason="runtime_metadata_missing",
    )


def test_validate_bridge_owner_recovers_from_legacy_listener_without_runtime_metadata(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    monkeypatch.setattr(gmail_focus, "detect_listener_pid", lambda _port: 4321)
    monkeypatch.setattr(gmail_focus, "_visible_window_hwnds_for_pid", lambda pid: [101] if pid == 4321 else [])
    monkeypatch.setattr(gmail_focus, "_window_title", lambda hwnd: "LegalPDF Translate [feat/gmail-intake]" if hwnd == 101 else "")

    result = gmail_focus.validate_bridge_owner(bridge_port=9011, base_dir=tmp_path)

    assert result == gmail_focus.BridgeOwnerValidationResult(
        ok=True,
        pid=4321,
        hwnd=101,
        reason="legacy_bridge_owner_ready",
        owner_kind="qt_app",
    )


def test_focus_bridge_owner_rejects_port_owner_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    gmail_focus.write_bridge_runtime_metadata(
        base_dir=tmp_path,
        port=9011,
        pid=4321,
        window_title="LegalPDF Translate",
        build_identity=None,
        running=True,
    )
    monkeypatch.setattr(gmail_focus, "detect_listener_pid", lambda _port: 5555)

    result = gmail_focus.focus_bridge_owner(bridge_port=9011, base_dir=tmp_path)

    assert result == gmail_focus.BridgeFocusResult(
        ok=False,
        focused=False,
        flashed=False,
        reason="bridge_port_owner_mismatch",
    )


def test_focus_bridge_owner_focuses_visible_window_for_matching_pid(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    gmail_focus.write_bridge_runtime_metadata(
        base_dir=tmp_path,
        port=9011,
        pid=4321,
        window_title="LegalPDF Translate",
        build_identity=None,
        running=True,
    )
    monkeypatch.setattr(gmail_focus, "detect_listener_pid", lambda _port: 4321)
    monkeypatch.setattr(gmail_focus, "_visible_window_hwnds_for_pid", lambda pid: [101] if pid == 4321 else [])
    monkeypatch.setattr(
        gmail_focus,
        "_request_hwnd_attention",
        lambda hwnd, *, restored: gmail_focus.WindowAttentionResult(
            requested=True,
            restored=restored,
            focused=False,
            flashed=True,
            reason="foreground_blocked",
        )
        if hwnd == 101
        else gmail_focus.WindowAttentionResult(
            requested=True,
            restored=restored,
            focused=False,
            flashed=False,
            reason="foreground_request_failed",
        ),
    )

    result = gmail_focus.focus_bridge_owner(bridge_port=9011, base_dir=tmp_path)

    assert result == gmail_focus.BridgeFocusResult(
        ok=True,
        focused=False,
        flashed=True,
        reason="foreground_blocked",
    )


def test_validate_bridge_owner_accepts_browser_owned_runtime_without_window(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    gmail_focus.write_bridge_runtime_metadata(
        base_dir=tmp_path,
        port=9011,
        pid=4321,
        window_title="LegalPDF Translate Browser App",
        build_identity=None,
        running=True,
        owner_kind="browser_app",
        runtime_mode="live",
        workspace_id="gmail-intake",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job",
    )
    monkeypatch.setattr(gmail_focus, "detect_listener_pid", lambda _port: 4321)
    monkeypatch.setattr(gmail_focus, "_visible_window_hwnds_for_pid", lambda _pid: [])

    result = gmail_focus.validate_bridge_owner(bridge_port=9011, base_dir=tmp_path)

    assert result == gmail_focus.BridgeOwnerValidationResult(
        ok=True,
        pid=4321,
        hwnd=None,
        reason="bridge_owner_ready",
        owner_kind="browser_app",
        runtime_mode="live",
        workspace_id="gmail-intake",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job",
    )


def test_validate_bridge_owner_treats_dead_runtime_metadata_pid_as_stale(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    gmail_focus.write_bridge_runtime_metadata(
        base_dir=tmp_path,
        port=9011,
        pid=4321,
        window_title="LegalPDF Translate Browser App",
        build_identity=None,
        running=True,
        owner_kind="browser_app",
        runtime_mode="live",
        workspace_id="gmail-intake",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job",
    )
    monkeypatch.setattr(gmail_focus, "_pid_is_running", lambda pid: False if pid == 4321 else True)
    monkeypatch.setattr(gmail_focus, "detect_listener_pid", lambda _port: None)

    result = gmail_focus.validate_bridge_owner(bridge_port=9011, base_dir=tmp_path)

    assert result == gmail_focus.BridgeOwnerValidationResult(
        ok=False,
        pid=None,
        hwnd=None,
        reason="bridge_owner_stale",
        owner_kind="none",
    )


def test_focus_bridge_owner_treats_browser_owned_bridge_as_delegated(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(gmail_focus, "_is_windows", lambda: True)
    gmail_focus.write_bridge_runtime_metadata(
        base_dir=tmp_path,
        port=9011,
        pid=4321,
        window_title="LegalPDF Translate Browser App",
        build_identity=None,
        running=True,
        owner_kind="browser_app",
        runtime_mode="live",
        workspace_id="gmail-intake",
        browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job",
    )
    monkeypatch.setattr(gmail_focus, "detect_listener_pid", lambda _port: 4321)
    monkeypatch.setattr(gmail_focus, "_visible_window_hwnds_for_pid", lambda _pid: [])

    result = gmail_focus.focus_bridge_owner(bridge_port=9011, base_dir=tmp_path)

    assert result == gmail_focus.BridgeFocusResult(
        ok=True,
        focused=False,
        flashed=False,
        reason="browser_tab_focus_delegated",
    )
