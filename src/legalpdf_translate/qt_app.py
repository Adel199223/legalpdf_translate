"""Primary Qt application module for LegalPDF Translate."""

from __future__ import annotations

import os
import sys


def run(argv: list[str] | None = None) -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont, QIcon
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            "PySide6 is not installed. Install dependencies with `pip install -e .`."
        ) from exc

    from legalpdf_translate.qt_gui.app_window import QtMainWindow
    from legalpdf_translate.qt_gui.styles import build_stylesheet
    from legalpdf_translate.resources_loader import resource_path

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName("LegalPDF Translate")
    app.setOrganizationName("LegalPDFTranslate")
    app.setFont(QFont("Segoe UI", 12))
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())
    icon_path = resource_path("resources/icons/LegalPDFTranslate.png")
    app_icon = QIcon(str(icon_path))
    app.setWindowIcon(app_icon)

    window = QtMainWindow()
    window.setWindowIcon(app_icon)
    window.show()
    return app.exec()


def main() -> None:
    run()


if __name__ == "__main__":
    raise SystemExit(run())
