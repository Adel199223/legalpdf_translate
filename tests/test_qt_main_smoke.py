from __future__ import annotations

import sys
import types


class _FakeQt:
    class HighDpiScaleFactorRoundingPolicy:
        PassThrough = object()


class _FakeQFont:
    def __init__(self, family: str, size: int) -> None:
        self.family = family
        self.size = size


class _FakeQApplication:
    rounding_policy: object | None = None
    last_instance: "_FakeQApplication | None" = None

    @classmethod
    def setHighDpiScaleFactorRoundingPolicy(cls, policy: object) -> None:
        cls.rounding_policy = policy

    def __init__(self, argv: list[str]) -> None:
        self.argv = list(argv)
        self.app_name = ""
        self.org_name = ""
        self.font: _FakeQFont | None = None
        self.style = ""
        self.stylesheet = ""
        self.exec_called = False
        _FakeQApplication.last_instance = self

    def setApplicationName(self, name: str) -> None:
        self.app_name = name

    def setOrganizationName(self, name: str) -> None:
        self.org_name = name

    def setFont(self, font: _FakeQFont) -> None:
        self.font = font

    def setStyle(self, style: str) -> None:
        self.style = style

    def setStyleSheet(self, stylesheet: str) -> None:
        self.stylesheet = stylesheet

    def exec(self) -> int:
        self.exec_called = True
        return 0


class _FakeWindow:
    instances: list["_FakeWindow"] = []

    def __init__(self) -> None:
        self.shown = False
        _FakeWindow.instances.append(self)

    def show(self) -> None:
        self.shown = True


def test_qt_main_smoke(monkeypatch) -> None:
    qtcore_mod = types.ModuleType("PySide6.QtCore")
    qtcore_mod.Qt = _FakeQt
    qtgui_mod = types.ModuleType("PySide6.QtGui")
    qtgui_mod.QFont = _FakeQFont
    qtwidgets_mod = types.ModuleType("PySide6.QtWidgets")
    qtwidgets_mod.QApplication = _FakeQApplication
    pyside_mod = types.ModuleType("PySide6")

    styles_mod = types.ModuleType("legalpdf_translate.qt_gui.styles")
    styles_mod.build_stylesheet = lambda: "fake-style"
    app_window_mod = types.ModuleType("legalpdf_translate.qt_gui.app_window")
    app_window_mod.QtMainWindow = _FakeWindow

    monkeypatch.setitem(sys.modules, "PySide6", pyside_mod)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore_mod)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui_mod)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets_mod)
    monkeypatch.setitem(sys.modules, "legalpdf_translate.qt_gui.styles", styles_mod)
    monkeypatch.setitem(sys.modules, "legalpdf_translate.qt_gui.app_window", app_window_mod)

    from legalpdf_translate import qt_main

    qt_main.main()

    app = _FakeQApplication.last_instance
    assert app is not None
    assert app.exec_called is True
    assert app.stylesheet == "fake-style"
    assert _FakeWindow.instances
    assert _FakeWindow.instances[-1].shown is True
