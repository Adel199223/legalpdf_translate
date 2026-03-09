"""Qt input widgets that ignore accidental wheel changes."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QSpinBox


class NoWheelComboBox(QComboBox):
    """Ignore wheel changes unless the popup list is intentionally open."""

    def _should_ignore_wheel(self) -> bool:
        view = self.view()
        return not (view is not None and view.isVisible())

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
