"""Qt input widgets that ignore accidental wheel changes."""

from __future__ import annotations

from PySide6.QtCore import QDate, QEvent, QLocale, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import (
    QCalendarWidget,
    QComboBox,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QStyledItemDelegate,
    QTableView,
    QToolButton,
    QWidget,
)


POPUP_LABEL_ROLE = int(Qt.ItemDataRole.UserRole) + 1
CALENDAR_WEEKEND_COLOR = "#FF4D64"


def _repolish(widget: QWidget) -> None:
    style = widget.style()
    if style is None:
        widget.update()
        return
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


class _PopupLabelDelegate(QStyledItemDelegate):
    """Render popup-only labels without changing the closed combo text."""

    def initStyleOption(self, option, index) -> None:  # type: ignore[override]
        super().initStyleOption(option, index)
        option.displayAlignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        popup_label = index.data(POPUP_LABEL_ROLE)
        if isinstance(popup_label, str) and popup_label.strip():
            option.text = popup_label.strip()


class NoWheelComboBox(QComboBox):
    """Ignore wheel changes unless the popup list is intentionally open."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state_mirrors: list[QWidget] = []
        self._popup_click_targets: set[int] = set()
        self._armed_popup_target_id: int | None = None
        self.setProperty("sharedChromeCombo", True)
        popup_view = self.view()
        popup_view.setItemDelegate(_PopupLabelDelegate(popup_view))
        popup_view.setTextElideMode(Qt.TextElideMode.ElideNone)
        self._set_state_property("hovered", False)
        self._set_state_property("focused", False)
        self._set_state_property("popupOpen", False)

    def _should_ignore_wheel(self) -> bool:
        view = self.view()
        return not (view is not None and view.isVisible())

    def register_state_mirror(self, widget: QWidget, *, popup_on_click: bool = False) -> None:
        if widget in self._state_mirrors:
            return
        self._state_mirrors.append(widget)
        widget.setProperty("sharedChromeCombo", True)
        widget.setProperty("hovered", bool(self.property("hovered")))
        widget.setProperty("focused", bool(self.property("focused")))
        widget.setProperty("popupOpen", bool(self.property("popupOpen")))
        widget.installEventFilter(self)
        if popup_on_click:
            self._popup_click_targets.add(id(widget))
        _repolish(widget)

    def setPopupLabel(self, index: int, label: str) -> None:
        self.setItemData(index, label, POPUP_LABEL_ROLE)

    def popupLabel(self, index: int) -> str:
        popup_label = self.itemData(index, POPUP_LABEL_ROLE)
        if isinstance(popup_label, str) and popup_label.strip():
            return popup_label.strip()
        return self.itemText(index).strip()

    def popupContentWidth(self) -> int:
        metrics = self.view().fontMetrics()
        widest = 0
        for index in range(self.count()):
            widest = max(widest, metrics.horizontalAdvance(self.popupLabel(index)))
        return max(self.width(), widest + 54)

    def _set_state_property(self, name: str, value: bool) -> None:
        normalized = bool(value)
        current_value = self.property(name)
        if current_value is None or bool(current_value) != normalized:
            self.setProperty(name, normalized)
            _repolish(self)
        for widget in self._state_mirrors:
            widget_value = widget.property(name)
            if widget_value is None or bool(widget_value) != normalized:
                widget.setProperty(name, normalized)
                _repolish(widget)

    def showPopup(self) -> None:  # type: ignore[override]
        super().showPopup()
        popup_width = self.popupContentWidth()
        popup_view = self.view()
        popup_view.setMinimumWidth(popup_width)
        popup_window = popup_view.window()
        popup_window.setMinimumWidth(popup_width)
        popup_window.resize(max(popup_window.width(), popup_width), popup_window.height())
        self._set_state_property("popupOpen", True)

    def hidePopup(self) -> None:  # type: ignore[override]
        super().hidePopup()
        self._set_state_property("popupOpen", False)

    def enterEvent(self, event) -> None:  # type: ignore[override]
        self._set_state_property("hovered", True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[override]
        self._set_state_property("hovered", False)
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:  # type: ignore[override]
        self._set_state_property("focused", True)
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # type: ignore[override]
        self._set_state_property("focused", False)
        super().focusOutEvent(event)

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched in self._state_mirrors and event is not None:
            event_type = event.type()
            if event_type == QEvent.Type.Enter:
                self._set_state_property("hovered", True)
            elif event_type == QEvent.Type.Leave:
                self._set_state_property("hovered", False)
            elif event_type == QEvent.Type.MouseButtonPress and id(watched) in self._popup_click_targets:
                if self.isEnabled() and getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton:
                    self._armed_popup_target_id = id(watched)
                    self.setFocus(Qt.FocusReason.MouseFocusReason)
                return True
            elif event_type == QEvent.Type.MouseButtonRelease and id(watched) in self._popup_click_targets:
                if (
                    self.isEnabled()
                    and self._armed_popup_target_id == id(watched)
                    and getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton
                ):
                    self.showPopup()
                self._armed_popup_target_id = None
                return True
            elif event_type == QEvent.Type.MouseButtonDblClick and id(watched) in self._popup_click_targets:
                return True
        return super().eventFilter(watched, event)

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        if self._should_ignore_wheel():
            event.ignore()
            return
        super().wheelEvent(event)


class NoWheelSpinBox(QSpinBox):
    """Ignore wheel changes entirely so values only change intentionally."""

    def _should_ignore_wheel(self) -> bool:
        return True

    def wheelEvent(self, event) -> None:  # type: ignore[override]
        event.ignore()


class _CalendarPopupFrame(QFrame):
    closed = Signal()

    def hideEvent(self, event) -> None:  # type: ignore[override]
        self.closed.emit()
        super().hideEvent(event)


class _StyledCalendarWidget(QCalendarWidget):
    """Shared calendar widget with Monday-first weeks and readable weekend styling."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._styled_weekend_days: set[int] = set()
        self._weekend_format = QTextCharFormat()
        self._weekend_format.setForeground(QColor(CALENDAR_WEEKEND_COLOR))
        self.setObjectName("CalendarPopupWidget")
        self.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.setHorizontalHeaderFormat(QCalendarWidget.HorizontalHeaderFormat.ShortDayNames)
        self.setFirstDayOfWeek(Qt.DayOfWeek.Monday)
        self.currentPageChanged.connect(self._refresh_visible_weekend_formats)
        self._refresh_header_metrics()
        self._refresh_visible_weekend_formats()

    def _weekday_labels(self) -> list[str]:
        locale = self.locale()
        start_day = self.firstDayOfWeek().value
        labels: list[str] = []
        for offset in range(7):
            day_number = ((start_day - 1 + offset) % 7) + 1
            label = locale.dayName(day_number, QLocale.FormatType.ShortFormat).strip()
            if not label:
                label = locale.standaloneDayName(day_number, QLocale.FormatType.ShortFormat).strip()
            labels.append(label or "Wed")
        return labels

    def _refresh_header_metrics(self) -> None:
        day_metrics = self.fontMetrics()
        min_cell_width = max(
            44,
            max(day_metrics.horizontalAdvance(label) for label in self._weekday_labels()) + 18,
        )
        min_calendar_width = max(self.minimumWidth(), (min_cell_width * 7) + 28)
        self.setMinimumWidth(min_calendar_width)
        calendar_view = self.findChild(QTableView, "qt_calendar_calendarview")
        if calendar_view is None:
            return
        header = calendar_view.horizontalHeader()
        header.setMinimumSectionSize(min_cell_width)
        header.setDefaultSectionSize(min_cell_width)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def _visible_grid_start_date(self) -> QDate:
        first_of_month = QDate(self.yearShown(), self.monthShown(), 1)
        offset = (first_of_month.dayOfWeek() - self.firstDayOfWeek().value + 7) % 7
        return first_of_month.addDays(-offset)

    def _refresh_visible_weekend_formats(self) -> None:
        for julian_day in self._styled_weekend_days:
            self.setDateTextFormat(QDate.fromJulianDay(julian_day), QTextCharFormat())
        self._styled_weekend_days.clear()
        visible_start = self._visible_grid_start_date()
        for offset in range(42):
            visible_date = visible_start.addDays(offset)
            if visible_date.dayOfWeek() in {6, 7}:
                self.setDateTextFormat(visible_date, self._weekend_format)
                self._styled_weekend_days.add(visible_date.toJulianDay())

    def showEvent(self, event) -> None:  # type: ignore[override]
        self._refresh_header_metrics()
        self._refresh_visible_weekend_formats()
        super().showEvent(event)


class GuardedDateEdit(QWidget):
    """Line-edit-compatible date field with an optional calendar popup."""

    textChanged = Signal(str)
    editingFinished = Signal()

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._popup: _CalendarPopupFrame | None = None
        self._calendar: _StyledCalendarWidget | None = None

        self._chrome = QFrame(self)
        self._chrome.setObjectName("FieldChrome")
        self._chrome.setProperty("sharedChromeDate", True)
        self._chrome.setProperty("hovered", False)
        self._chrome.setProperty("focused", False)
        self._chrome.setProperty("popupOpen", False)

        chrome_layout = QHBoxLayout(self._chrome)
        chrome_layout.setContentsMargins(12, 0, 10, 0)
        chrome_layout.setSpacing(8)

        self._line_edit = QLineEdit(text, self._chrome)
        self._line_edit.setProperty("embeddedField", True)
        self._line_edit.setClearButtonEnabled(False)
        self._line_edit.textChanged.connect(self.textChanged.emit)
        self._line_edit.editingFinished.connect(self.editingFinished.emit)
        self._line_edit.installEventFilter(self)
        chrome_layout.addWidget(self._line_edit, 1)

        self._button = QToolButton(self._chrome)
        self._button.setObjectName("DatePickerButton")
        self._button.setArrowType(Qt.ArrowType.DownArrow)
        self._button.setAutoRaise(False)
        self._button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._button.installEventFilter(self)
        self._button.clicked.connect(self.toggleCalendarPopup)
        chrome_layout.addWidget(self._button, 0, Qt.AlignmentFlag.AlignVCenter)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(self._chrome)
        self.setFocusProxy(self._line_edit)

    def _set_state_property(self, name: str, value: bool) -> None:
        normalized = bool(value)
        current_value = self._chrome.property(name)
        if current_value is None or bool(current_value) != normalized:
            self._chrome.setProperty(name, normalized)
            _repolish(self._chrome)

    def _sync_hover_state(self) -> None:
        self._set_state_property("hovered", self.underMouse() or self._line_edit.underMouse() or self._button.underMouse())

    def eventFilter(self, watched, event) -> bool:  # type: ignore[override]
        if watched in {self._line_edit, self._button} and event is not None:
            event_type = event.type()
            if event_type == QEvent.Type.Enter:
                self._set_state_property("hovered", True)
            elif event_type == QEvent.Type.Leave:
                self._sync_hover_state()
            elif event_type == QEvent.Type.FocusIn:
                self._set_state_property("focused", True)
            elif event_type == QEvent.Type.FocusOut:
                self._set_state_property("focused", False)
        return super().eventFilter(watched, event)

    def _ensure_popup(self) -> _CalendarPopupFrame:
        if self._popup is not None and self._calendar is not None:
            return self._popup
        popup = _CalendarPopupFrame(None, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        popup.setObjectName("CalendarPopup")
        popup_layout = QHBoxLayout(popup)
        popup_layout.setContentsMargins(10, 10, 10, 10)
        calendar = _StyledCalendarWidget(popup)
        calendar.clicked.connect(self._apply_calendar_date)
        calendar.activated.connect(self._apply_calendar_date)
        popup_layout.addWidget(calendar)
        popup.setMinimumWidth(calendar.minimumWidth() + 20)
        popup.closed.connect(lambda: self._set_state_property("popupOpen", False))
        self._popup = popup
        self._calendar = calendar
        return popup

    def _apply_calendar_date(self, date: QDate) -> None:
        if not date.isValid():
            return
        self.setCalendarDate(date)
        if self._popup is not None:
            self._popup.hide()
        self.editingFinished.emit()

    def _sync_calendar_selection(self) -> None:
        if self._calendar is None:
            return
        parsed = QDate.fromString(self.text().strip(), "yyyy-MM-dd")
        if parsed.isValid():
            self._calendar.setSelectedDate(parsed)

    def toggleCalendarPopup(self) -> None:
        popup = self._ensure_popup()
        if popup.isVisible():
            popup.hide()
            return
        self._sync_calendar_selection()
        popup.adjustSize()
        popup.resize(max(popup.width(), popup.minimumWidth()), popup.height())
        popup.move(self.mapToGlobal(QPoint(0, self.height() + 4)))
        popup.show()
        popup.raise_()
        popup.activateWindow()
        self._set_state_property("popupOpen", True)

    def text(self) -> str:
        return self._line_edit.text()

    def setText(self, value: str) -> None:
        self._line_edit.setText(value)

    def setCalendarDate(self, date: QDate) -> None:
        if date.isValid():
            self._line_edit.setText(date.toString("yyyy-MM-dd"))

    def setPlaceholderText(self, text: str) -> None:
        self._line_edit.setPlaceholderText(text)

    def setReadOnly(self, value: bool) -> None:
        self._line_edit.setReadOnly(value)
        self._button.setEnabled(not value)

    def isReadOnly(self) -> bool:
        return self._line_edit.isReadOnly()

    def setEnabled(self, enabled: bool) -> None:  # type: ignore[override]
        super().setEnabled(enabled)
        self._line_edit.setEnabled(enabled)
        self._button.setEnabled(enabled and not self._line_edit.isReadOnly())

    def lineEdit(self) -> QLineEdit:
        return self._line_edit

    def calendarWidget(self) -> QCalendarWidget:
        self._ensure_popup()
        assert self._calendar is not None
        return self._calendar
