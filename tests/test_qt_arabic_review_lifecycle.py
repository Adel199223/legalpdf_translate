from __future__ import annotations

import os

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from legalpdf_translate.qt_gui import dialogs
from legalpdf_translate.word_automation import WordAutomationResult


@pytest.fixture
def review_context(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "fictional.docx"
    path.write_bytes(b"fictional review input; never opened natively")
    opened = []
    polled = []

    def open_mock(docx_path):
        opened.append(docx_path)
        return WordAutomationResult(ok=True, action="open", message="Mocked open")

    monkeypatch.setattr(dialogs, "open_docx_in_word", open_mock)
    monkeypatch.setattr(
        dialogs.QtArabicDocxReviewDialog, "_poll_for_save", lambda self: polled.append(self)
    )
    return app, path, opened, polled


@pytest.mark.parametrize("completion", ["accept", "reject"])
def test_completion_before_first_event_cancels_startup(review_context, completion):
    app, path, opened, polled = review_context
    dialog = dialogs.QtArabicDocxReviewDialog(
        parent=None, docx_path=path, is_gmail_batch=False
    )

    getattr(dialog, completion)()
    app.processEvents()
    app.processEvents()

    assert opened == []
    assert polled == []
    assert not dialog._startup_timer.isActive()
    assert not dialog._poll_timer.isActive()


def test_deletion_before_first_event_cancels_startup(review_context):
    app, path, opened, polled = review_context
    dialog = dialogs.QtArabicDocxReviewDialog(
        parent=None, docx_path=path, is_gmail_batch=False
    )
    startup_timer = dialog._startup_timer
    poll_timer = dialog._poll_timer

    dialog.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    app.processEvents()

    assert not isValid(dialog)
    assert not isValid(startup_timer)
    assert not isValid(poll_timer)
    assert opened == []
    assert polled == []


def test_normal_start_opens_once_and_polls_until_completion(review_context):
    app, path, opened, polled = review_context
    dialog = dialogs.QtArabicDocxReviewDialog(
        parent=None, docx_path=path, is_gmail_batch=False
    )
    assert opened == []

    app.processEvents()
    app.processEvents()

    assert opened == [path.resolve()]
    assert not dialog._startup_timer.isActive()
    assert dialog._poll_timer.isActive()
    dialog._poll_timer.setInterval(0)
    app.processEvents()
    assert polled

    dialog.accept()
    poll_count = len(polled)
    app.processEvents()
    app.processEvents()

    assert opened == [path.resolve()]
    assert len(polled) == poll_count
    assert not dialog._startup_timer.isActive()
    assert not dialog._poll_timer.isActive()
