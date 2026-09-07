from __future__ import annotations

import pytest
import os
import subprocess
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


@pytest.fixture(autouse=True)
def _block_external_file_launches():
    """A fake document must never reach a real Windows file association.

    Tests exercising launch behavior must replace this guard with their own
    recording stub. pytest.fail is deliberately not an Exception: production
    fallback handlers must not swallow an accidental external application open.
    """
    def blocked_startfile(*args, **kwargs):
        pytest.fail("External file launch blocked in tests; explicitly mock os.startfile.", pytrace=False)

    # Do not share the test's monkeypatch fixture: Qt module mocks must be
    # restored before widget cleanup, while this launch guard remains active.
    with pytest.MonkeyPatch.context() as launch_guard:
        launch_guard.setattr(os, "startfile", blocked_startfile, raising=False)
        yield


@pytest.fixture(autouse=True)
def _block_native_word_execution():
    """Keep native Word launch/cleanup blocked until an explicit recording mock.

    A module-local proxy avoids changing subprocess behavior for other tests.
    Its separate patch context survives restoration of test-specific Qt mocks
    and stays in place through widget cleanup, just like the startfile guard.
    """
    import legalpdf_translate.word_automation as word_automation

    def blocked_native_word(*args, **kwargs):
        pytest.fail(
            "Native Word execution blocked in tests; explicitly mock Word subprocess execution or readiness.",
            pytrace=False,
        )

    class GuardedWordSubprocess:
        Popen = staticmethod(blocked_native_word)
        run = staticmethod(blocked_native_word)
        call = staticmethod(blocked_native_word)
        check_call = staticmethod(blocked_native_word)
        check_output = staticmethod(blocked_native_word)

        def __getattr__(self, name):
            return getattr(subprocess, name)

    with pytest.MonkeyPatch.context() as word_guard:
        word_guard.setattr(word_automation, "subprocess", GuardedWordSubprocess())
        yield


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
def _cleanup_qt_widgets_after_test(_block_external_file_launches, _block_native_word_execution) -> None:
    _cleanup_qt_widgets()
    yield
    _cleanup_qt_widgets()
