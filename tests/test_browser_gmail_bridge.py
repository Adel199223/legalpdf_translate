from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import legalpdf_translate.browser_gmail_bridge as browser_bridge_module
from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.gmail_focus import load_bridge_runtime_metadata
from legalpdf_translate.shadow_runtime import BrowserDataPaths
from legalpdf_translate.gmail_browser_service import GmailBrowserSessionManager


class _FakeBridge:
    instances: list["_FakeBridge"] = []

    def __init__(self, *, port: int, token: str, on_context, host: str = "127.0.0.1") -> None:
        self.host = host
        self.port = int(port)
        self.token = str(token)
        self._on_context = on_context
        self.started = False
        self.stopped = False
        _FakeBridge.instances.append(self)

    @property
    def is_running(self) -> bool:
        return self.started and not self.stopped

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True


def _identity() -> RuntimeBuildIdentity:
    return RuntimeBuildIdentity(
        worktree_path="C:/Users/FA507/.codex/legalpdf_translate_beginner_first_ux",
        branch="codex/beginner-first-primary-flow-ux",
        head_sha="5c9842e",
        labels=("shadow-web",),
        is_canonical=False,
        is_lineage_valid=True,
        canonical_worktree_path="C:/Users/FA507/.codex/legalpdf_translate",
        canonical_branch="main",
        approved_base_branch="main",
        approved_base_head_floor="506dee6",
        canonical_head_floor="506dee6",
        reasons=("noncanonical",),
    )


def _live_data_paths(root: Path) -> BrowserDataPaths:
    return BrowserDataPaths(
        mode="live",
        label="Live App Data",
        app_data_dir=root,
        settings_path=root / "settings.json",
        job_log_db_path=root / "job_log.sqlite3",
        outputs_dir=root / "outputs",
        live_data=True,
        banner_text="LIVE APP DATA",
    )


def test_browser_live_gmail_bridge_manager_starts_and_clears_runtime_metadata(monkeypatch, tmp_path: Path) -> None:
    _FakeBridge.instances = []
    live_root = tmp_path / "live"
    live_root.mkdir(parents=True, exist_ok=True)
    (live_root / "settings.json").write_text(
        json.dumps(
            {
                "gmail_intake_bridge_enabled": True,
                "gmail_intake_bridge_token": "shared-token",
                "gmail_intake_port": 9011,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(browser_bridge_module, "detect_browser_data_paths", lambda **kwargs: _live_data_paths(live_root))
    monkeypatch.setattr(browser_bridge_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(
        browser_bridge_module,
        "ensure_edge_native_host_registered",
        lambda **kwargs: SimpleNamespace(ok=True, reason="registered"),
    )
    monkeypatch.setattr(
        browser_bridge_module,
        "validate_bridge_owner",
        lambda **kwargs: SimpleNamespace(
            ok=False,
            pid=None,
            hwnd=None,
            reason="runtime_metadata_missing",
            owner_kind="none",
            browser_url=None,
            workspace_id=None,
            runtime_mode=None,
        ),
    )

    manager = browser_bridge_module.BrowserLiveGmailBridgeManager(
        repo_root=tmp_path,
        build_identity=_identity(),
        server_port=8877,
        gmail_sessions=GmailBrowserSessionManager(),
    )

    result = manager.sync()

    assert result.status == "ready"
    assert result.owner_kind == "browser_app"
    assert result.started is True
    assert len(_FakeBridge.instances) == 1
    payload = load_bridge_runtime_metadata(live_root)
    assert payload is not None
    assert payload["owner_kind"] == "browser_app"
    assert payload["workspace_id"] == "gmail-intake"
    assert payload["runtime_mode"] == "live"
    assert payload["browser_url"] == "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake"

    manager.stop()

    assert _FakeBridge.instances[0].stopped is True
    assert load_bridge_runtime_metadata(live_root) is None


def test_browser_live_gmail_bridge_manager_backs_off_for_existing_qt_owner(monkeypatch, tmp_path: Path) -> None:
    _FakeBridge.instances = []
    live_root = tmp_path / "live"
    live_root.mkdir(parents=True, exist_ok=True)
    (live_root / "settings.json").write_text(
        json.dumps(
            {
                "gmail_intake_bridge_enabled": True,
                "gmail_intake_bridge_token": "shared-token",
                "gmail_intake_port": 9011,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(browser_bridge_module, "detect_browser_data_paths", lambda **kwargs: _live_data_paths(live_root))
    monkeypatch.setattr(browser_bridge_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(
        browser_bridge_module,
        "ensure_edge_native_host_registered",
        lambda **kwargs: SimpleNamespace(ok=True, reason="registered"),
    )
    monkeypatch.setattr(
        browser_bridge_module,
        "validate_bridge_owner",
        lambda **kwargs: SimpleNamespace(
            ok=True,
            pid=6543,
            hwnd=101,
            reason="bridge_owner_ready",
            owner_kind="qt_app",
            browser_url=None,
            workspace_id=None,
            runtime_mode=None,
        ),
    )

    manager = browser_bridge_module.BrowserLiveGmailBridgeManager(
        repo_root=tmp_path,
        build_identity=_identity(),
        server_port=8877,
        gmail_sessions=GmailBrowserSessionManager(),
    )

    result = manager.sync()

    assert result.status == "backing_off"
    assert result.owner_kind == "qt_app"
    assert _FakeBridge.instances == []
    assert load_bridge_runtime_metadata(live_root) is None


def test_browser_live_gmail_bridge_manager_disables_noncanonical_live_port(monkeypatch, tmp_path: Path) -> None:
    _FakeBridge.instances = []
    live_root = tmp_path / "live"
    live_root.mkdir(parents=True, exist_ok=True)
    (live_root / "settings.json").write_text(
        json.dumps(
            {
                "gmail_intake_bridge_enabled": True,
                "gmail_intake_bridge_token": "shared-token",
                "gmail_intake_port": 9011,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(browser_bridge_module, "detect_browser_data_paths", lambda **kwargs: _live_data_paths(live_root))
    monkeypatch.setattr(browser_bridge_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(
        browser_bridge_module,
        "ensure_edge_native_host_registered",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("registration should be skipped on noncanonical live ports")
        ),
    )

    manager = browser_bridge_module.BrowserLiveGmailBridgeManager(
        repo_root=tmp_path,
        build_identity=_identity(),
        server_port=8888,
        gmail_sessions=GmailBrowserSessionManager(),
    )

    result = manager.sync()

    assert result.status == "disabled"
    assert result.reason == "noncanonical_live_bridge_port"
    assert result.browser_url == "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake"
    assert result.registration_ok is False
    assert result.registration_reason == "skipped_noncanonical_live_bridge_port"
    assert _FakeBridge.instances == []
    assert load_bridge_runtime_metadata(live_root) is None
