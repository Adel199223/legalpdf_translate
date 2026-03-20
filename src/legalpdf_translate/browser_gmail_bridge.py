"""Browser-server ownership of the live Gmail intake bridge."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from .build_identity import RuntimeBuildIdentity
from .gmail_browser_service import GmailBrowserSessionManager
from .gmail_focus import (
    clear_bridge_runtime_metadata,
    load_bridge_runtime_metadata,
    validate_bridge_owner,
    write_bridge_runtime_metadata,
)
from .gmail_focus_host import ensure_edge_native_host_registered
from .gmail_intake import InboundMailContext, LocalGmailIntakeBridge
from .shadow_runtime import (
    RUNTIME_MODE_LIVE,
    SHADOW_DEFAULT_PORT,
    SHADOW_HOST,
    BrowserDataPaths,
    detect_browser_data_paths,
)
from .user_settings import load_gui_settings_from_path

LIVE_GMAIL_WORKSPACE_ID = "gmail-intake"


def build_browser_gmail_workspace_url(
    *,
    server_port: int = SHADOW_DEFAULT_PORT,
    workspace_id: str = LIVE_GMAIL_WORKSPACE_ID,
) -> str:
    return f"http://{SHADOW_HOST}:{int(server_port)}/?mode=live&workspace={workspace_id}#gmail-intake"


@dataclass(frozen=True, slots=True)
class BrowserLiveBridgeSyncResult:
    status: str
    reason: str
    bridge_enabled: bool
    bridge_port: int | None
    owner_kind: str
    browser_url: str
    workspace_id: str
    started: bool
    registration_ok: bool
    registration_reason: str


class BrowserLiveGmailBridgeManager:
    """Own the live Gmail intake bridge for the browser server when possible."""

    def __init__(
        self,
        *,
        repo_root: Path,
        build_identity: RuntimeBuildIdentity,
        server_port: int,
        gmail_sessions: GmailBrowserSessionManager,
    ) -> None:
        self._data_paths = detect_browser_data_paths(
            mode=RUNTIME_MODE_LIVE,
            repo=repo_root,
            identity=build_identity,
        )
        self._server_port = int(server_port)
        self._gmail_sessions = gmail_sessions
        self._bridge: LocalGmailIntakeBridge | None = None
        self._last_result = BrowserLiveBridgeSyncResult(
            status="idle",
            reason="not_synced",
            bridge_enabled=False,
            bridge_port=None,
            owner_kind="none",
            browser_url=build_browser_gmail_workspace_url(server_port=self._server_port),
            workspace_id=LIVE_GMAIL_WORKSPACE_ID,
            started=False,
            registration_ok=False,
            registration_reason="not_attempted",
        )

    @property
    def data_paths(self) -> BrowserDataPaths:
        return self._data_paths

    @property
    def browser_url(self) -> str:
        return build_browser_gmail_workspace_url(server_port=self._server_port)

    @property
    def workspace_id(self) -> str:
        return LIVE_GMAIL_WORKSPACE_ID

    @property
    def last_result(self) -> BrowserLiveBridgeSyncResult:
        return self._last_result

    def _settings(self) -> tuple[bool, int, str]:
        values = load_gui_settings_from_path(self._data_paths.settings_path)
        enabled = bool(values.get("gmail_intake_bridge_enabled", False))
        token = str(values.get("gmail_intake_bridge_token", "") or "").strip()
        try:
            port = int(values.get("gmail_intake_port", 8765))
        except (TypeError, ValueError):
            port = 8765
        port = max(1, min(65535, port))
        return enabled, port, token

    def _clear_metadata_if_owned(self) -> None:
        payload = load_bridge_runtime_metadata(self._data_paths.app_data_dir)
        if not isinstance(payload, dict):
            return
        try:
            payload_pid = int(payload.get("pid", 0))
        except (TypeError, ValueError):
            payload_pid = 0
        if payload_pid != os.getpid():
            return
        if str(payload.get("owner_kind", "") or "").strip() != "browser_app":
            return
        clear_bridge_runtime_metadata(self._data_paths.app_data_dir)

    def _write_browser_metadata(self, bridge: LocalGmailIntakeBridge) -> None:
        write_bridge_runtime_metadata(
            base_dir=self._data_paths.app_data_dir,
            port=bridge.port,
            pid=os.getpid(),
            window_title="LegalPDF Translate Browser App",
            build_identity=None,
            running=True,
            owner_kind="browser_app",
            runtime_mode=RUNTIME_MODE_LIVE,
            workspace_id=self.workspace_id,
            browser_url=self.browser_url,
        )

    def _stop_current_bridge(self) -> None:
        bridge = self._bridge
        self._bridge = None
        if bridge is None:
            self._clear_metadata_if_owned()
            return
        bridge.stop()
        self._clear_metadata_if_owned()

    def stop(self) -> None:
        self._stop_current_bridge()
        self._last_result = BrowserLiveBridgeSyncResult(
            status="stopped",
            reason="bridge_stopped",
            bridge_enabled=False,
            bridge_port=None,
            owner_kind="none",
            browser_url=self.browser_url,
            workspace_id=self.workspace_id,
            started=False,
            registration_ok=self._last_result.registration_ok,
            registration_reason=self._last_result.registration_reason,
        )

    def _registration_state(self) -> tuple[bool, str]:
        result = ensure_edge_native_host_registered(base_dir=self._data_paths.app_data_dir)
        return bool(result.ok), str(result.reason or "").strip()

    def _handle_inbound_context(self, context: InboundMailContext) -> None:
        self._gmail_sessions.accept_bridge_intake(
            runtime_mode=RUNTIME_MODE_LIVE,
            workspace_id=self.workspace_id,
            settings_path=self._data_paths.settings_path,
            context=context,
        )

    def sync(self) -> BrowserLiveBridgeSyncResult:
        enabled, port, token = self._settings()
        current = self._bridge
        current_matches = (
            current is not None
            and current.host == SHADOW_HOST
            and current.port == port
            and current.token == token
            and current.is_running
        )
        if current_matches:
            registration_ok, registration_reason = self._registration_state()
            self._write_browser_metadata(current)
            self._last_result = BrowserLiveBridgeSyncResult(
                status="ready",
                reason="browser_bridge_owner_ready",
                bridge_enabled=True,
                bridge_port=port,
                owner_kind="browser_app",
                browser_url=self.browser_url,
                workspace_id=self.workspace_id,
                started=False,
                registration_ok=registration_ok,
                registration_reason=registration_reason,
            )
            return self._last_result

        if current is not None:
            self._stop_current_bridge()

        registration_ok, registration_reason = self._registration_state()

        if not enabled:
            self._last_result = BrowserLiveBridgeSyncResult(
                status="disabled",
                reason="bridge_disabled",
                bridge_enabled=False,
                bridge_port=port,
                owner_kind="none",
                browser_url=self.browser_url,
                workspace_id=self.workspace_id,
                started=False,
                registration_ok=registration_ok,
                registration_reason=registration_reason,
            )
            return self._last_result

        if token == "":
            self._last_result = BrowserLiveBridgeSyncResult(
                status="disabled",
                reason="bridge_token_missing",
                bridge_enabled=True,
                bridge_port=port,
                owner_kind="none",
                browser_url=self.browser_url,
                workspace_id=self.workspace_id,
                started=False,
                registration_ok=registration_ok,
                registration_reason=registration_reason,
            )
            return self._last_result

        validation = validate_bridge_owner(
            bridge_port=port,
            base_dir=self._data_paths.app_data_dir,
        )
        if validation.ok and validation.pid != os.getpid():
            self._last_result = BrowserLiveBridgeSyncResult(
                status="backing_off",
                reason=validation.reason,
                bridge_enabled=True,
                bridge_port=port,
                owner_kind=validation.owner_kind or "qt_app",
                browser_url=validation.browser_url or self.browser_url,
                workspace_id=validation.workspace_id or self.workspace_id,
                started=False,
                registration_ok=registration_ok,
                registration_reason=registration_reason,
            )
            return self._last_result

        bridge = LocalGmailIntakeBridge(
            port=port,
            token=token,
            on_context=self._handle_inbound_context,
        )
        try:
            bridge.start()
        except Exception as exc:  # noqa: BLE001
            self._last_result = BrowserLiveBridgeSyncResult(
                status="failed",
                reason=f"bridge_start_failed:{exc}",
                bridge_enabled=True,
                bridge_port=port,
                owner_kind="external" if validation.reason in {"bridge_port_owner_mismatch", "bridge_port_owner_unknown"} else "none",
                browser_url=self.browser_url,
                workspace_id=self.workspace_id,
                started=False,
                registration_ok=registration_ok,
                registration_reason=registration_reason,
            )
            return self._last_result

        self._bridge = bridge
        self._write_browser_metadata(bridge)
        self._last_result = BrowserLiveBridgeSyncResult(
            status="ready",
            reason="browser_bridge_owner_ready",
            bridge_enabled=True,
            bridge_port=port,
            owner_kind="browser_app",
            browser_url=self.browser_url,
            workspace_id=self.workspace_id,
            started=True,
            registration_ok=registration_ok,
            registration_reason=registration_reason,
        )
        return self._last_result
