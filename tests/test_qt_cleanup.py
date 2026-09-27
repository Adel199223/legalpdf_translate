from __future__ import annotations

import os

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from shiboken6 import isValid

from tests.conftest import _cleanup_qt_widgets


def test_cleanup_destroys_retained_widget_and_child_before_return() -> None:
    app = QApplication.instance() or QApplication([])
    parent = QWidget()
    child = QLabel("Retained child", parent)
    destroyed: list[str] = []
    parent.destroyed.connect(lambda: destroyed.append("parent"))
    child.destroyed.connect(lambda: destroyed.append("child"))

    _cleanup_qt_widgets()

    assert sorted(destroyed) == ["child", "parent"]
    assert not isValid(parent)
    assert not isValid(child)
    assert isValid(app)


def test_cleanup_drains_deletion_scheduled_by_residual_events() -> None:
    app = QApplication.instance() or QApplication([])
    parent = QObject()
    child = QObject(parent)
    destroyed: list[str] = []
    parent.destroyed.connect(lambda: destroyed.append("parent"))
    child.destroyed.connect(lambda: destroyed.append("child"))
    QTimer.singleShot(0, parent.deleteLater)

    _cleanup_qt_widgets()

    assert sorted(destroyed) == ["child", "parent"]
    assert not isValid(parent)
    assert not isValid(child)
    assert isValid(app)
