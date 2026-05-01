"""Shared top-level Qt sizing and collapsible-section helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, QTimer, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QFrame, QLayout, QSizePolicy, QToolButton, QVBoxLayout, QWidget


@dataclass(frozen=True)
class WindowSizingPreset:
    width_fraction: float
    height_fraction: float
    max_width: int | None = None
    max_height: int | None = None
    margin: int = 24


WINDOW_SIZING_PRESETS: dict[str, WindowSizingPreset] = {
    "shell": WindowSizingPreset(width_fraction=0.94, height_fraction=0.93, max_width=2200, max_height=1440, margin=20),
    "form": WindowSizingPreset(width_fraction=0.82, height_fraction=0.88, max_width=1280, max_height=1080),
    "table": WindowSizingPreset(width_fraction=0.9, height_fraction=0.84, max_width=1700, max_height=1200),
    "preview": WindowSizingPreset(width_fraction=0.92, height_fraction=0.9, max_width=1680, max_height=1280),
}


def available_screen_geometry(widget: QWidget) -> QRect:
    screen = widget.screen()
    if screen is None and widget.windowHandle() is not None:
        screen = widget.windowHandle().screen()
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        return QRect(0, 0, 1440, 900)
    return screen.availableGeometry()


def bounded_top_level_size(
    widget: QWidget,
    *,
    role: str,
    preferred_size: QSize | None = None,
    expand_to_role_target: bool = False,
) -> QSize:
    preset = WINDOW_SIZING_PRESETS.get(role, WINDOW_SIZING_PRESETS["form"])
    available = available_screen_geometry(widget)
    max_by_screen = QSize(
        max(240, available.width() - (preset.margin * 2)),
        max(220, available.height() - (preset.margin * 2)),
    )
    role_target = QSize(
        max(240, int(available.width() * preset.width_fraction)),
        max(220, int(available.height() * preset.height_fraction)),
    )
    width_cap = min(
        max_by_screen.width(),
        preset.max_width if preset.max_width is not None else max_by_screen.width(),
        role_target.width(),
    )
    height_cap = min(
        max_by_screen.height(),
        preset.max_height if preset.max_height is not None else max_by_screen.height(),
        role_target.height(),
    )
    if preferred_size is None or not preferred_size.isValid():
        preferred_size = widget.sizeHint()
    if preferred_size is None or not preferred_size.isValid():
        preferred_size = QSize(width_cap, height_cap)
    baseline = QSize(width_cap, height_cap) if expand_to_role_target else preferred_size
    return QSize(
        min(width_cap, max(min(240, width_cap), int(baseline.width()))),
        min(height_cap, max(min(220, height_cap), int(baseline.height()))),
    )


def _clamped_top_left(available: QRect, size: QSize, current_pos: QPoint | None = None) -> QPoint:
    max_x = available.x() + max(0, available.width() - size.width())
    max_y = available.y() + max(0, available.height() - size.height())
    if current_pos is None:
        return QPoint(
            available.x() + max(0, (available.width() - size.width()) // 2),
            available.y() + max(0, (available.height() - size.height()) // 2),
        )
    return QPoint(
        min(max(current_pos.x(), available.x()), max_x),
        min(max(current_pos.y(), available.y()), max_y),
    )


class ResponsiveWindowController(QObject):
    """Screen-bounded initial sizing plus deferred resize callbacks."""

    def __init__(
        self,
        window: QWidget,
        *,
        role: str,
        preferred_size: QSize | None = None,
        expand_to_role_target: bool = False,
        resize_callback: Callable[[], None] | None = None,
        resize_interval_ms: int = 36,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._role = role
        self._preferred_size = preferred_size
        self._expand_to_role_target = bool(expand_to_role_target)
        self._resize_callback = resize_callback
        self._base_minimum_size = window.minimumSize()
        self._initial_geometry_applied = False
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(max(0, int(resize_interval_ms)))
        self._resize_timer.timeout.connect(self.flush_resize_callback)
        if isinstance(window, QDialog):
            window.setSizeGripEnabled(True)
        window.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: object) -> bool:
        if watched is self._window and isinstance(event, QEvent):
            if event.type() == QEvent.Type.Show and not self._initial_geometry_applied:
                self.apply_initial_geometry()
            elif event.type() == QEvent.Type.Resize and self._resize_callback is not None:
                self._resize_timer.start()
            elif event.type() == QEvent.Type.ScreenChangeInternal:
                self.clamp_to_screen()
        return False

    def _apply_dynamic_minimum_size(self, bounded_size: QSize) -> None:
        self._window.setMinimumSize(
            min(self._base_minimum_size.width(), bounded_size.width()),
            min(self._base_minimum_size.height(), bounded_size.height()),
        )

    def apply_initial_geometry(self) -> None:
        target_size = bounded_top_level_size(
            self._window,
            role=self._role,
            preferred_size=self._preferred_size,
            expand_to_role_target=self._expand_to_role_target,
        )
        self._apply_dynamic_minimum_size(target_size)
        self._window.resize(target_size)
        available = available_screen_geometry(self._window)
        self._window.move(_clamped_top_left(available, target_size))
        self._initial_geometry_applied = True
        self.flush_resize_callback()

    def clamp_to_screen(self) -> None:
        current_size = self._window.size()
        bounded_size = bounded_top_level_size(
            self._window,
            role=self._role,
            preferred_size=current_size,
            expand_to_role_target=False,
        )
        self._apply_dynamic_minimum_size(bounded_size)
        if bounded_size != current_size:
            self._window.resize(bounded_size)
        available = available_screen_geometry(self._window)
        self._window.move(_clamped_top_left(available, bounded_size, self._window.pos()))
        self.flush_resize_callback()

    def flush_resize_callback(self) -> None:
        if self._resize_timer.isActive():
            self._resize_timer.stop()
        if self._resize_callback is not None:
            self._resize_callback()


class CollapsibleSection(QFrame):
    """A compact collapsible section with a styled toggle button."""

    def __init__(self, title: str, *, expanded: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._expanded = bool(expanded)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.toggle_button = QToolButton(self, objectName="SectionToggleButton")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setText(title)
        self.toggle_button.toggled.connect(self.set_expanded)
        root.addWidget(self.toggle_button)

        self.content_frame = QFrame(self)
        self.content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        root.addWidget(self.content_frame)

        self.set_expanded(self._expanded)

    def set_content_layout(self, layout: QLayout) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.setParent(None)
            if child_layout is not None:
                while child_layout.count():
                    child_layout.takeAt(0)
        self.content_layout.addLayout(layout)

    def set_content_widget(self, widget: QWidget) -> None:
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            prior_widget = item.widget()
            if prior_widget is not None:
                prior_widget.setParent(None)
        self.content_layout.addWidget(widget)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = bool(expanded)
        self.toggle_button.blockSignals(True)
        self.toggle_button.setChecked(self._expanded)
        self.toggle_button.blockSignals(False)
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if self._expanded else Qt.ArrowType.RightArrow
        )
        self.content_frame.setVisible(self._expanded)

    def is_expanded(self) -> bool:
        return self._expanded
