from __future__ import annotations

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _isolate_test_appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    appdata_root = tmp_path / "appdata"
    appdata_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(appdata_root))


def _cleanup_qt_widgets() -> None:
    try:
        from PySide6.QtWidgets import QApplication
    except Exception:  # pragma: no cover
        return
    app = QApplication.instance()
    if app is None:
        return
    seen: set[int] = set()
    candidates = []
    popup = QApplication.activePopupWidget()
    modal = QApplication.activeModalWidget()
    for widget in (popup, modal, *app.topLevelWidgets()):
        if widget is None:
            continue
        widget_id = id(widget)
        if widget_id in seen:
            continue
        seen.add(widget_id)
        candidates.append(widget)
    for widget in candidates:
        try:
            if hasattr(widget, "_busy"):
                setattr(widget, "_busy", False)
            if hasattr(widget, "_running"):
                setattr(widget, "_running", False)
            widget.close()
        except RuntimeError:
            continue
        try:
            widget.deleteLater()
        except RuntimeError:
            continue
    app.processEvents()
    app.processEvents()


@pytest.fixture(autouse=True)
def _cleanup_qt_widgets_after_test() -> None:
    _cleanup_qt_widgets()
    yield
    _cleanup_qt_widgets()
