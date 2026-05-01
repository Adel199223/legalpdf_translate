"""Shared beginner-first declutter primitives for Qt surfaces."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


def _repolish(widget: QWidget) -> None:
    style = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)
    widget.update()


def build_compact_add_button(
    *,
    tooltip: str,
    accessible_name: str | None = None,
    parent: QWidget | None = None,
) -> QToolButton:
    """Create a compact add button that fits dense field rows."""

    button = QToolButton(parent)
    button.setObjectName("CompactAddButton")
    button.setText("+")
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    button.setAutoRaise(False)
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    button.setFixedSize(30, 30)
    tooltip_text = tooltip.strip()
    button.setToolTip(tooltip_text)
    button.setStatusTip(tooltip_text)
    resolved_name = (accessible_name or tooltip_text or "Add").strip()
    button.setAccessibleName(resolved_name)
    button.setAccessibleDescription(tooltip_text or resolved_name)
    return button


def build_inline_info_button(
    *,
    tooltip: str,
    accessible_name: str | None = None,
    whats_this: str | None = None,
    parent: QWidget | None = None,
) -> QToolButton:
    """Create a compact info affordance for secondary hover/focus help."""

    button = QToolButton(parent)
    button.setObjectName("InlineInfoButton")
    button.setText("i")
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    button.setAutoRaise(False)
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    button.setFixedSize(24, 24)
    tooltip_text = tooltip.strip()
    button.setToolTip(tooltip_text)
    button.setStatusTip(tooltip_text)
    if whats_this is not None:
        button.setWhatsThis(str(whats_this).strip())
    resolved_name = (accessible_name or tooltip_text or "More information").strip()
    button.setAccessibleName(resolved_name)
    button.setAccessibleDescription(tooltip_text or resolved_name)
    return button


class DeclutterSection(QFrame):
    """A dialog-friendly collapsible section with summary and trailing actions."""

    def __init__(
        self,
        title: str,
        *,
        expanded: bool = True,
        summary_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DeclutterSection")
        self._expanded = bool(expanded)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        self.header_frame = QFrame(self)
        self.header_frame.setObjectName("DeclutterSectionHeader")
        self.header_frame.setProperty("attention", False)
        header = QHBoxLayout(self.header_frame)
        header.setContentsMargins(12, 8, 12, 8)
        header.setSpacing(8)

        self.toggle_button = QToolButton(self.header_frame)
        self.toggle_button.setObjectName("DeclutterSectionToggle")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toggle_button.setText(title)
        self.toggle_button.setAccessibleName(title.strip() or "Section")
        self.toggle_button.toggled.connect(self.set_expanded)
        header.addWidget(self.toggle_button, 1)

        self.summary_label = QLabel(self.header_frame)
        self.summary_label.setObjectName("DeclutterSectionSummary")
        self.summary_label.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        self.summary_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self.summary_label, 0)

        self.trailing_frame = QWidget(self.header_frame)
        trailing = QHBoxLayout(self.trailing_frame)
        trailing.setContentsMargins(0, 0, 0, 0)
        trailing.setSpacing(6)
        self.trailing_layout = trailing
        header.addWidget(self.trailing_frame, 0)

        root.addWidget(self.header_frame)

        self.content_frame = QFrame(self)
        self.content_frame.setObjectName("DeclutterSectionContent")
        self.content_frame.setProperty("attention", False)
        self.content_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(10)
        root.addWidget(self.content_frame)

        self.set_summary_text(summary_text)
        self.set_expanded(self._expanded)

    def set_title(self, title: str) -> None:
        text = title.strip()
        self.toggle_button.setText(text)
        self.toggle_button.setAccessibleName(text or "Section")

    def set_summary_text(self, text: str) -> None:
        summary = text.strip()
        self.summary_label.setText(summary)
        self.summary_label.setHidden(summary == "")

    def add_header_widget(self, widget: QWidget) -> None:
        self.trailing_layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignVCenter)

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

    def set_attention_state(self, active: bool) -> None:
        attention = bool(active)
        self.header_frame.setProperty("attention", attention)
        self.content_frame.setProperty("attention", attention)
        _repolish(self.header_frame)
        _repolish(self.content_frame)

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
