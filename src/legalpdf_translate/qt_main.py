"""Qt GUI entrypoint for LegalPDF Translate."""

from __future__ import annotations

import os
import sys


def main() -> None:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QFont
        from PySide6.QtWidgets import QApplication
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(
            "PySide6 is not installed. Install dependencies with `pip install -e .`."
        ) from exc

    from legalpdf_translate.qt_gui.app_window import QtMainWindow
    from legalpdf_translate.qt_gui.styles import build_stylesheet

    os.environ.setdefault("QT_ENABLE_HIGHDPI_SCALING", "1")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("LegalPDF Translate")
    app.setOrganizationName("LegalPDFTranslate")
    app.setFont(QFont("Segoe UI", 12))
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

    window = QtMainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
