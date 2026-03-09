"""Controller for app-level Qt workspace windows and shared reservations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from PySide6.QtCore import QObject, Signal

from legalpdf_translate.build_identity import RuntimeBuildIdentity, normalize_path_identity
from legalpdf_translate.gmail_focus import clear_bridge_runtime_metadata
from legalpdf_translate.gmail_intake import InboundMailContext, LocalGmailIntakeBridge
from legalpdf_translate.user_settings import app_data_dir, load_gui_settings

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    from legalpdf_translate.qt_gui.app_window import QtMainWindow


@dataclass(frozen=True, slots=True)
class RunTargetReservation:
    token: str
    target_paths: tuple[Path, ...]
    workspace_index: int | None


@dataclass(frozen=True, slots=True)
class RunTargetConflict:
    target_path: Path
    owner_window: object
    owner_workspace_index: int | None
    owner_title: str


@dataclass(frozen=True, slots=True)
class RunTargetReservationResult:
    reservation: RunTargetReservation | None = None
    conflict: RunTargetConflict | None = None


@dataclass(slots=True)
class _ReservedTargetEntry:
    owner_key: int
    owner_window: object
    token: str
    path: Path


class _ControllerSignals(QObject):
    gmail_intake_received = Signal(object)


class WorkspaceWindowController:
    """Own top-level workspaces and shared app-level reservations."""

    def __init__(
        self,
        *,
        app: QApplication,
        build_identity: RuntimeBuildIdentity | None,
        window_icon: QIcon | None = None,
    ) -> None:
        self._app = app
        self._build_identity = build_identity
        self._window_icon = window_icon
        self._windows: dict[int, QtMainWindow] = {}
        self._workspace_indices: dict[int, int] = {}
        self._next_workspace_index = 1
        self._last_active_window_key: int | None = None
        self._reserved_targets: dict[str, _ReservedTargetEntry] = {}
        self._gmail_intake_bridge: LocalGmailIntakeBridge | None = None
        self._gmail_bridge_bootstrapped = False
        self._signals = _ControllerSignals()
        self._signals.gmail_intake_received.connect(self._route_gmail_intake_on_main_thread)
        about_to_quit = getattr(app, "aboutToQuit", None)
        if about_to_quit is not None and hasattr(about_to_quit, "connect"):
            about_to_quit.connect(self.stop_gmail_intake_bridge)

    def windows(self) -> tuple[QtMainWindow, ...]:
        return tuple(self._windows.values())

    def create_workspace(
        self,
        *,
        show: bool = True,
        focus: bool = True,
    ) -> QtMainWindow:
        from legalpdf_translate.qt_gui.app_window import QtMainWindow

        workspace_index = self._next_workspace_index
        self._next_workspace_index += 1
        window = QtMainWindow(
            build_identity=self._build_identity,
            controller=self,
            workspace_index=workspace_index,
        )
        if self._window_icon is not None:
            window.setWindowIcon(self._window_icon)

        key = id(window)
        self._windows[key] = window
        self._workspace_indices[key] = workspace_index
        destroyed = getattr(window, "destroyed", None)
        if destroyed is not None and hasattr(destroyed, "connect"):
            destroyed.connect(lambda _obj=None, key=key: self._on_window_destroyed(key))
        if show:
            window.show()
        if focus:
            self.focus_window(window)
        else:
            refresh_title = getattr(window, "refresh_workspace_title", None)
            if callable(refresh_title):
                refresh_title()
        if not self._gmail_bridge_bootstrapped:
            self._gmail_bridge_bootstrapped = True
            self.sync_gmail_intake_bridge(anchor_window=window)
        return window

    def workspace_index_for(self, window: object) -> int | None:
        return self._workspace_indices.get(id(window))

    def note_window_activated(self, window: object) -> None:
        key = id(window)
        if key not in self._windows:
            return
        self._last_active_window_key = key

    def last_active_window(self) -> QtMainWindow | None:
        if self._last_active_window_key is not None:
            candidate = self._windows.get(self._last_active_window_key)
            if candidate is not None:
                return candidate
        return next(iter(self._windows.values()), None)

    def gmail_intake_bridge(self) -> LocalGmailIntakeBridge | None:
        return self._gmail_intake_bridge

    def focus_window(self, window: object) -> None:
        target = self._windows.get(id(window))
        if target is None:
            return
        if hasattr(target, "isMinimized") and target.isMinimized():
            target.showNormal()
        else:
            target.show()
        if hasattr(target, "raise_"):
            target.raise_()
        if hasattr(target, "activateWindow"):
            target.activateWindow()
        self.note_window_activated(target)

    def reserve_run_targets(
        self,
        owner_window: object,
        target_paths: list[Path] | tuple[Path, ...],
    ) -> RunTargetReservationResult:
        owner_key = id(owner_window)
        workspace_index = self.workspace_index_for(owner_window)
        normalized_targets: list[tuple[str, Path]] = []
        seen: set[str] = set()
        for raw_path in target_paths:
            path = raw_path.expanduser().resolve()
            key = normalize_path_identity(path)
            if key in seen:
                continue
            seen.add(key)
            existing = self._reserved_targets.get(key)
            if existing is not None and existing.owner_key != owner_key:
                owner_title_getter = getattr(existing.owner_window, "windowTitle", None)
                owner_title = str(owner_title_getter() or "").strip() if callable(owner_title_getter) else ""
                return RunTargetReservationResult(
                    conflict=RunTargetConflict(
                        target_path=existing.path,
                        owner_window=existing.owner_window,
                        owner_workspace_index=self.workspace_index_for(existing.owner_window),
                        owner_title=owner_title,
                    )
                )
            normalized_targets.append((key, path))
        token = uuid4().hex
        for key, path in normalized_targets:
            self._reserved_targets[key] = _ReservedTargetEntry(
                owner_key=owner_key,
                owner_window=owner_window,
                token=token,
                path=path,
            )
        return RunTargetReservationResult(
            reservation=RunTargetReservation(
                token=token,
                target_paths=tuple(path for _key, path in normalized_targets),
                workspace_index=workspace_index,
            )
        )

    def release_run_targets(
        self,
        owner_window: object,
        reservation: RunTargetReservation | None,
    ) -> None:
        if reservation is None:
            return
        owner_key = id(owner_window)
        for path in reservation.target_paths:
            key = normalize_path_identity(path)
            existing = self._reserved_targets.get(key)
            if existing is None:
                continue
            if existing.owner_key != owner_key or existing.token != reservation.token:
                continue
            self._reserved_targets.pop(key, None)

    def release_all_for_window(self, owner_window: object) -> None:
        owner_key = id(owner_window)
        stale_keys = [key for key, entry in self._reserved_targets.items() if entry.owner_key == owner_key]
        for key in stale_keys:
            self._reserved_targets.pop(key, None)

    @staticmethod
    def _gmail_intake_settings(settings: dict[str, object] | None = None) -> tuple[bool, int, str]:
        values = load_gui_settings() if settings is None else dict(settings)
        enabled = bool(values.get("gmail_intake_bridge_enabled", False))
        token = str(values.get("gmail_intake_bridge_token", "") or "").strip()
        try:
            port = int(values.get("gmail_intake_port", 8765))
        except (TypeError, ValueError):
            port = 8765
        port = max(1, min(65535, port))
        return enabled, port, token

    def _append_log(self, window: object | None, message: str) -> None:
        if window is None:
            return
        append_log = getattr(window, "_append_log", None)
        if callable(append_log):
            append_log(message)

    def _set_bridge_status(self, window: object | None, status_text: str) -> None:
        if window is None:
            return
        status_label = getattr(window, "status_label", None)
        if status_label is not None and hasattr(status_label, "setText"):
            status_label.setText(status_text)
        header_status_label = getattr(window, "header_status_label", None)
        if header_status_label is not None and hasattr(header_status_label, "setText"):
            header_status_label.setText(status_text)
        dashboard_snapshot = getattr(window, "_dashboard_snapshot", None)
        if dashboard_snapshot is not None and hasattr(dashboard_snapshot, "current_task"):
            dashboard_snapshot.current_task = status_text

    def _anchor_window(self, preferred: object | None = None) -> object | None:
        if preferred is not None:
            return preferred
        return self.last_active_window()

    def apply_shared_settings(
        self,
        *,
        source_window: object | None,
        persist: bool,
        values: dict[str, object],
    ) -> None:
        if persist:
            reloaded_settings = load_gui_settings()
            shared_settings = {
                key: reloaded_settings[key]
                for key in values.keys()
                if key in reloaded_settings
            }
        else:
            shared_settings = dict(values)
        for window in self.windows():
            refresh_shared_settings = getattr(window, "reload_shared_settings", None)
            if callable(refresh_shared_settings):
                refresh_shared_settings(shared_settings)
        self.sync_gmail_intake_bridge(
            settings=shared_settings,
            anchor_window=source_window,
        )

    def stop_gmail_intake_bridge(self) -> None:
        bridge = self._gmail_intake_bridge
        self._gmail_intake_bridge = None
        if bridge is None:
            clear_bridge_runtime_metadata(app_data_dir())
            return
        bridge.stop()
        clear_bridge_runtime_metadata(app_data_dir())

    def sync_gmail_intake_bridge(
        self,
        *,
        settings: dict[str, object] | None = None,
        anchor_window: object | None = None,
    ) -> None:
        from PySide6.QtWidgets import QMessageBox

        from legalpdf_translate.qt_gui.app_window import (
            _ensure_gmail_native_focus_host_registration,
            _refresh_gmail_bridge_runtime_metadata,
        )

        enabled, port, token = self._gmail_intake_settings(settings)
        current = self._gmail_intake_bridge
        anchor = self._anchor_window(anchor_window)
        current_matches = (
            current is not None
            and current.host == "127.0.0.1"
            and current.port == port
            and current.token == token
            and current.is_running
        )
        if enabled and token != "" and current_matches:
            if anchor is not None:
                _refresh_gmail_bridge_runtime_metadata(
                    anchor,
                    bridge=current,
                    build_identity=self._build_identity,
                )
            return

        if current is not None:
            current_port = current.port
            self.stop_gmail_intake_bridge()
            self._append_log(anchor, f"Gmail intake bridge stopped on 127.0.0.1:{current_port}.")

        if not enabled:
            return
        if token == "":
            self._append_log(anchor, "Gmail intake bridge is enabled but token is blank; bridge not started.")
            return

        bridge = LocalGmailIntakeBridge(
            port=port,
            token=token,
            on_context=self._handle_gmail_intake_from_bridge,
        )
        try:
            bridge.start()
        except Exception as exc:  # noqa: BLE001
            status_text = "Gmail intake bridge unavailable"
            details_text = (
                "Gmail intake bridge could not start on "
                f"127.0.0.1:{port}.\n\n"
                "Another process may already be using this port.\n\n"
                f"Details: {exc}"
            )
            self._set_bridge_status(anchor, status_text)
            self._append_log(anchor, f"Gmail intake bridge failed to start on 127.0.0.1:{port}: {exc}")
            if anchor is not None:
                QMessageBox.warning(anchor, status_text, details_text)
            return

        self._gmail_intake_bridge = bridge
        if anchor is not None:
            _refresh_gmail_bridge_runtime_metadata(
                anchor,
                bridge=bridge,
                build_identity=self._build_identity,
            )
            _ensure_gmail_native_focus_host_registration(
                anchor,
                append_log=getattr(anchor, "_append_log", None),
            )
        self._append_log(anchor, f"Gmail intake bridge listening on {bridge.url}.")

    def _handle_gmail_intake_from_bridge(self, context: InboundMailContext) -> None:
        self._signals.gmail_intake_received.emit(context)

    def _route_gmail_intake_on_main_thread(self, context_obj: object) -> None:
        if not isinstance(context_obj, InboundMailContext):
            return
        target = self.last_active_window()
        reusable = False
        if target is not None:
            is_workspace_reusable = getattr(target, "is_workspace_reusable_for_gmail", None)
            if callable(is_workspace_reusable):
                reusable = bool(is_workspace_reusable())
        if target is None or not reusable:
            target = self.create_workspace(show=True, focus=True)
        accept_gmail_intake = getattr(target, "accept_gmail_intake", None)
        if callable(accept_gmail_intake):
            accept_gmail_intake(context_obj)

    def _on_window_destroyed(self, key: int) -> None:
        window = self._windows.pop(key, None)
        self._workspace_indices.pop(key, None)
        if window is not None:
            self.release_all_for_window(window)
        if self._last_active_window_key == key:
            self._last_active_window_key = None
        if not self._windows:
            self.stop_gmail_intake_bridge()
