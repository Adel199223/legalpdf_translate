from __future__ import annotations

import sys
import types
from pathlib import Path


class _FakeQt:
    class HighDpiScaleFactorRoundingPolicy:
        PassThrough = object()


class _FakeQFont:
    def __init__(self, family: str, size: int) -> None:
        self.family = family
        self.size = size


class _FakeQIcon:
    def __init__(self, path: str) -> None:
        self.path = path


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
        self.window_icon: _FakeQIcon | None = None
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

    def setProperty(self, _name: str, _value: object) -> None:
        return None

    def setWindowIcon(self, icon: _FakeQIcon) -> None:
        self.window_icon = icon

    def exec(self) -> int:
        self.exec_called = True
        return 0


class _FakeWindow:
    instances: list["_FakeWindow"] = []

    def __init__(self, *_args, **_kwargs) -> None:
        self.shown = False
        self.window_icon: _FakeQIcon | None = None
        _FakeWindow.instances.append(self)

    def show(self) -> None:
        self.shown = True

    def setWindowIcon(self, icon: _FakeQIcon) -> None:
        self.window_icon = icon


class _FakeWindowController:
    last_instance: "_FakeWindowController | None" = None

    def __init__(self, *, app, build_identity, window_icon) -> None:
        self.app = app
        self.build_identity = build_identity
        self.window_icon = window_icon
        self.create_calls: list[tuple[bool, bool]] = []
        _FakeWindowController.last_instance = self

    def create_workspace(self, *, show: bool = True, focus: bool = True) -> _FakeWindow:
        self.create_calls.append((show, focus))
        window = _FakeWindow()
        if self.window_icon is not None:
            window.setWindowIcon(self.window_icon)
        if show:
            window.show()
        return window


def test_qt_app_run_smoke(monkeypatch) -> None:
    qtcore_mod = types.ModuleType("PySide6.QtCore")
    qtcore_mod.Qt = _FakeQt
    qtgui_mod = types.ModuleType("PySide6.QtGui")
    qtgui_mod.QFont = _FakeQFont
    qtgui_mod.QIcon = _FakeQIcon
    qtwidgets_mod = types.ModuleType("PySide6.QtWidgets")
    qtwidgets_mod.QApplication = _FakeQApplication
    pyside_mod = types.ModuleType("PySide6")

    styles_mod = types.ModuleType("legalpdf_translate.qt_gui.styles")
    applied_themes: list[str] = []

    def _fake_apply_app_appearance(app, *, theme: str) -> str:
        applied_themes.append(theme)
        app.setStyleSheet(f"fake-style:{theme}")
        return app.stylesheet

    styles_mod.apply_app_appearance = _fake_apply_app_appearance
    controller_mod = types.ModuleType("legalpdf_translate.qt_gui.window_controller")
    controller_mod.WorkspaceWindowController = _FakeWindowController
    settings_mod = types.ModuleType("legalpdf_translate.user_settings")
    settings_mod.load_gui_settings = lambda: {"ui_theme": "dark_simple"}

    monkeypatch.setitem(sys.modules, "PySide6", pyside_mod)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore_mod)
    monkeypatch.setitem(sys.modules, "PySide6.QtGui", qtgui_mod)
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qtwidgets_mod)
    monkeypatch.setitem(sys.modules, "legalpdf_translate.qt_gui.styles", styles_mod)
    monkeypatch.setitem(sys.modules, "legalpdf_translate.qt_gui.window_controller", controller_mod)
    monkeypatch.setitem(sys.modules, "legalpdf_translate.user_settings", settings_mod)

    from legalpdf_translate import qt_app

    qt_app.run(["python"])

    app = _FakeQApplication.last_instance
    assert app is not None
    assert app.exec_called is True
    assert app.stylesheet == "fake-style:dark_simple"
    assert applied_themes == ["dark_simple"]
    assert app.window_icon is not None
    assert app.window_icon.path.replace("\\", "/").endswith("resources/icons/LegalPDFTranslate.png")
    controller = _FakeWindowController.last_instance
    assert controller is not None
    assert controller.app is app
    assert controller.create_calls == [(True, False)]
    assert _FakeWindow.instances
    assert _FakeWindow.instances[-1].shown is True
    assert _FakeWindow.instances[-1].window_icon is not None
    assert _FakeWindow.instances[-1].window_icon.path == app.window_icon.path


def test_qt_main_smoke(monkeypatch) -> None:
    called = {"run": False}

    def _fake_run() -> int:
        called["run"] = True
        return 0

    qt_app_mod = types.ModuleType("legalpdf_translate.qt_app")
    qt_app_mod.run = _fake_run
    monkeypatch.setitem(sys.modules, "legalpdf_translate.qt_app", qt_app_mod)

    from legalpdf_translate import qt_main

    qt_main.main()
    assert called["run"] is True


def test_qt_app_module_main_guard_invokes_run() -> None:
    source = Path("src/legalpdf_translate/qt_app.py").read_text(encoding="utf-8")
    assert 'if __name__ == "__main__":' in source
    assert "raise SystemExit(run())" in source


def test_build_stylesheet_supports_runtime_theme_variants() -> None:
    from legalpdf_translate.qt_gui.styles import build_stylesheet, normalize_ui_theme, theme_effect_colors

    futuristic = build_stylesheet("dark_futuristic")
    simple = build_stylesheet("dark_simple")
    futuristic_effects = theme_effect_colors("dark_futuristic")
    simple_effects = theme_effect_colors("dark_simple")

    assert normalize_ui_theme("unknown") == "dark_futuristic"
    assert futuristic != simple
    assert "QFrame#DashboardFrame" in futuristic
    assert "QDialog, QMessageBox" in simple
    assert '"Segoe UI Variable", "Segoe UI", "Corbel", "Calibri", "DejaVu Sans", "Arial"' in futuristic
    assert '"Candara", "Segoe UI Variable", "Segoe UI Semibold", "Corbel", "Segoe UI", "DejaVu Sans", "Arial"' in futuristic
    assert '"Segoe UI Variable", "Candara", "Segoe UI Semibold", "Corbel", "Segoe UI", "DejaVu Sans", "Arial"' in futuristic
    assert 'QComboBox[sharedChromeCombo="true"][embeddedField="true"][hovered="true"]' in futuristic
    assert 'QFrame#FieldChrome[sharedChromeDate="true"][hovered="true"]' in futuristic
    assert "QFrame#CalendarPopup" in futuristic
    assert "QPushButton#PrimaryButton:default" in futuristic
    assert "QWidget#DialogActionBar QPushButton#PrimaryButton" in futuristic
    assert "Bahnschrift" not in futuristic
    assert "Aptos" not in futuristic
    assert "letter-spacing: 0.82px;" in futuristic
    assert futuristic_effects["title_glow"].getRgb() != simple_effects["title_glow"].getRgb()
    assert futuristic_effects["footer_glow"].getRgb() != simple_effects["footer_glow"].getRgb()
