from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QBuffer, QDate, QEvent, QIODevice, QRect, QItemSelectionModel, Qt
from PySide6.QtGui import QCloseEvent, QColor, QImage, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QBoxLayout, QCalendarWidget, QComboBox, QDialog, QLineEdit, QToolButton, QWidget

from legalpdf_translate.gmail_batch import (
    FetchedGmailMessage,
    GmailAttachmentCandidate,
    GmailAttachmentSelection,
    GmailBatchConfirmedItem,
    GmailInterpretationSession,
    GmailBatchSession,
    GmailMessageLoadResult,
)
import legalpdf_translate.qt_gui.app_window as app_window_module
import legalpdf_translate.qt_gui.dialogs as dialogs_module
import legalpdf_translate.qt_gui.window_adaptive as window_adaptive_module
import legalpdf_translate.qt_gui.window_controller as window_controller_module
import legalpdf_translate.user_settings as user_settings
from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.docx_writer import assemble_docx
from legalpdf_translate.gmail_focus import (
    WindowAttentionResult,
    bridge_runtime_metadata_path,
    load_bridge_runtime_metadata,
)
from legalpdf_translate.gmail_intake import InboundMailContext
from legalpdf_translate.joblog_db import insert_job_run, open_job_log
from legalpdf_translate.qt_gui.app_window import QtMainWindow
from legalpdf_translate.qt_gui.dialogs import (
    GMAIL_INTAKE_WORKFLOW_INTERPRETATION,
    GmailBatchReviewPreviewCacheTransfer,
    GmailBatchReviewResult,
    JobLogSeed,
    JobLogSavedResult,
    QtArabicDocxReviewDialog,
    QtGmailAttachmentPreviewDialog,
    QtGmailBatchReviewDialog,
    QtJobLogWindow,
    QtReviewQueueDialog,
    QtSaveToJobLogDialog,
    QtSettingsDialog,
    build_blank_interpretation_seed,
    build_interpretation_seed_from_photo_screenshot,
    build_seed_from_run,
    count_words_from_docx,
    count_words_from_output_artifacts,
)
from legalpdf_translate.qt_gui.guarded_inputs import (
    CALENDAR_WEEKEND_COLOR,
    GuardedDateEdit,
    NoWheelComboBox,
    NoWheelSpinBox,
    POPUP_LABEL_ROLE,
)
from legalpdf_translate.qt_gui.window_controller import WorkspaceWindowController
from legalpdf_translate.qt_gui.worker import (
    GmailAttachmentPreviewBootstrapResult,
    GmailAttachmentPreviewPageResult,
)
from legalpdf_translate.types import TargetLang
from legalpdf_translate.types import (
    EffortPolicy,
    ImageMode,
    OcrEnginePolicy,
    OcrMode,
    RunConfig,
    RunSummary,
)
from legalpdf_translate.user_profile import default_primary_profile
from legalpdf_translate.word_automation import WordAutomationResult


class _FakeEdit:
    def __init__(self, value: str = "") -> None:
        self._value = value

    def text(self) -> str:
        return self._value

    def setText(self, value: str) -> None:
        self._value = value

    def clear(self) -> None:
        self._value = ""


class _FakeCombo:
    def __init__(self, value: str) -> None:
        self._value = value
        self.items: list[str] = []
        self.blocked = False

    def currentText(self) -> str:
        return self._value

    def setCurrentText(self, value: str) -> None:
        self._value = value

    def clear(self) -> None:
        self.items = []

    def addItems(self, values: list[str]) -> None:
        self.items.extend(values)

    def blockSignals(self, blocked: bool) -> None:
        self.blocked = blocked


class _FakeSpin:
    def __init__(self, value: int) -> None:
        self._value = value
        self.blocked = False

    def value(self) -> int:
        return self._value

    def setValue(self, value: int) -> None:
        self._value = value

    def blockSignals(self, blocked: bool) -> None:
        self.blocked = blocked


class _FakeCheck:
    def __init__(self, checked: bool) -> None:
        self._checked = checked
        self.blocked = False

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, checked: bool) -> None:
        self._checked = checked

    def blockSignals(self, blocked: bool) -> None:
        self.blocked = blocked


class _FakeEvent:
    def __init__(self) -> None:
        self.ignored = False

    def ignore(self) -> None:
        self.ignored = True


class _FakeButton:
    def __init__(self) -> None:
        self.enabled: bool | None = None
        self.checked: bool | None = None

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def setChecked(self, checked: bool) -> None:
        self.checked = checked


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class _FakeProgress:
    def __init__(self) -> None:
        self.value: int | None = None

    def setValue(self, value: int) -> None:
        self.value = value


class _FakeTextBox:
    def __init__(self) -> None:
        self.cleared = False

    def clear(self) -> None:
        self.cleared = True


class _FakeTimer:
    def __init__(self) -> None:
        self.started = False

    def start(self) -> None:
        self.started = True


def _base_gui_settings(**overrides: object) -> dict[str, object]:
    settings = dict(user_settings.DEFAULT_GUI_SETTINGS)
    settings.update(overrides)
    return settings


def _build_gmail_batch_session(tmp_path: Path, *, count: int = 2) -> GmailBatchSession:
    downloaded = []
    for index in range(count):
        source_path = tmp_path / f"attachment-{index + 1}.pdf"
        source_path.write_bytes(b"%PDF-1.4\n")
        downloaded.append(
            SimpleNamespace(
                candidate=GmailAttachmentCandidate(
                    attachment_id=f"att-{index + 1}",
                    filename=f"attachment-{index + 1}.pdf",
                    mime_type="application/pdf",
                    size_bytes=2048 + index,
                    source_message_id="msg-100",
                ),
                saved_path=source_path,
                start_page=1,
                page_count=6,
            )
        )
    return GmailBatchSession(
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=tuple(item.candidate for item in downloaded),
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        downloaded_attachments=tuple(downloaded),
        download_dir=tmp_path,
    )


def _build_gmail_batch_confirmed_item(
    session: GmailBatchSession,
    *,
    index: int,
    translated_docx_path: Path,
    translated_word_count: int,
    case_number: str = "123/26.0",
    case_entity: str = "Tribunal",
    case_city: str = "Beja",
    court_email: str = "court@example.com",
    run_id: str | None = None,
    joblog_row_id: int | None = None,
    run_dir: Path | None = None,
) -> GmailBatchConfirmedItem:
    resolved_run_dir = run_dir or (translated_docx_path.parent / f"run-{index + 1}")
    resolved_run_dir.mkdir(parents=True, exist_ok=True)
    return GmailBatchConfirmedItem(
        downloaded_attachment=session.downloaded_attachments[index],
        translated_docx_path=translated_docx_path,
        staged_translated_docx_path=translated_docx_path,
        run_dir=resolved_run_dir,
        translated_word_count=translated_word_count,
        joblog_row_id=joblog_row_id or (index + 1),
        run_id=run_id or f"run-{index + 1}",
        case_number=case_number,
        case_entity=case_entity,
        case_city=case_city,
        court_email=court_email,
    )


def _build_gmail_interpretation_session(tmp_path: Path) -> GmailInterpretationSession:
    notice_path = tmp_path / "notice.pdf"
    notice_path.write_bytes(b"%PDF-1.4\n")
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="notice.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    return GmailInterpretationSession(
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        downloaded_attachment=SimpleNamespace(
            candidate=attachment,
            saved_path=notice_path,
            start_page=1,
            page_count=4,
        ),
        download_dir=tmp_path,
        effective_output_dir=tmp_path,
    )


def _close_qt_windows(app: QApplication, windows: list[QtMainWindow]) -> None:
    for window in windows:
        window._busy = False
        window._running = False
        window.close()
        window.deleteLater()
    _close_qt_transients(app)


def _drain_qt_events(app: QApplication, *, cycles: int = 3, wait_ms: int = 0) -> None:
    for _ in range(max(1, cycles)):
        app.processEvents()
        if wait_ms > 0:
            QTest.qWait(wait_ms)


def _close_qt_transients(app: QApplication, *, keep: tuple[QWidget | None, ...] = ()) -> None:
    keep_ids = {id(widget) for widget in keep if widget is not None}
    seen: set[int] = set()
    candidates: list[QWidget] = []
    for widget in (QApplication.activePopupWidget(), QApplication.activeModalWidget(), *app.topLevelWidgets()):
        if widget is None:
            continue
        widget_id = id(widget)
        if widget_id in keep_ids or widget_id in seen:
            continue
        seen.add(widget_id)
        candidates.append(widget)
    for widget in candidates:
        try:
            widget.close()
        except RuntimeError:
            continue
        try:
            widget.deleteLater()
        except RuntimeError:
            continue
    _drain_qt_events(app, cycles=3, wait_ms=1)


def _activate_dialog_and_focus(app: QApplication, dialog: QDialog, widget: QWidget) -> None:
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    for _ in range(8):
        widget.setFocus(Qt.FocusReason.OtherFocusReason)
        _drain_qt_events(app, cycles=2, wait_ms=5)
        if QApplication.focusWidget() is widget:
            return
        dialog.raise_()
        dialog.activateWindow()
    assert QApplication.focusWidget() is widget


def _make_restore_settings_fake(defaults: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        _defaults=defaults,
        outdir_edit=_FakeEdit(""),
        lang_combo=_FakeCombo("EN"),
        effort_combo=_FakeCombo("high"),
        effort_policy_combo=_FakeCombo("adaptive"),
        images_combo=_FakeCombo("off"),
        ocr_mode_combo=_FakeCombo("auto"),
        ocr_engine_combo=_FakeCombo("local_then_api"),
        start_edit=_FakeEdit(""),
        end_edit=_FakeEdit(""),
        max_edit=_FakeEdit(""),
        workers_spin=_FakeSpin(1),
        resume_check=_FakeCheck(False),
        breaks_check=_FakeCheck(False),
        keep_check=_FakeCheck(False),
        queue_manifest_edit=_FakeEdit(""),
        queue_rerun_failed_only_check=_FakeCheck(False),
        _refresh_lang_badge=lambda: None,
        _existing_output_dir_text=QtMainWindow._existing_output_dir_text,
    )


class _FakeBridge:
    instances: list["_FakeBridge"] = []

    def __init__(
        self,
        *,
        port: int,
        token: str,
        on_context,
        host: str = "127.0.0.1",
    ) -> None:
        self.host = host
        self.port = port
        self.token = token
        self._on_context = on_context
        self.started = False
        self.stopped = False
        self.running = False
        _FakeBridge.instances.append(self)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/gmail-intake"

    @property
    def is_running(self) -> bool:
        return self.running

    def start(self) -> None:
        if self.host != "127.0.0.1":
            raise ValueError("LocalGmailIntakeBridge must bind to 127.0.0.1.")
        self.started = True
        self.running = True

    def stop(self) -> None:
        self.stopped = True
        self.running = False


class _FailingBridge(_FakeBridge):
    def start(self) -> None:
        raise OSError("Only one usage of each socket address is normally permitted")


def test_stage_two_shell_smoke() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        assert window.dashboard_frame.objectName() == "DashboardFrame"
        assert window.title_label.text() == "LegalPDF Translate"
        assert window.header_status_label.text() == "Idle"
        assert window.dashboard_nav_btn.text() == "Dashboard"
        assert window._scroll_area.objectName() == "ShellScrollArea"
        assert window.content_card.objectName() == "ContentCard"
        assert window.translate_btn.text() == "Start Translate"
        assert window.show_adv.text() == "Advanced Settings"
        assert window.advanced_help_btn.objectName() == "InlineInfoButton"
        assert window.progress_panel_title.text() == "Run Status"
        assert window.progress_help_btn.objectName() == "InlineInfoButton"
        assert window.progress_eta_label.text() == "ETA --"
        assert window.output_format_label.isHidden() is True
        assert window.more_btn.menu() is window.more_menu
        assert window.more_btn.text() == "..."
        assert window.footer_meta_label.text() == "Project v3.0 | LegalPDF"
        assert window.translate_btn.minimumHeight() == window.cancel_btn.minimumHeight() == window.more_btn.minimumHeight()
        assert window.cancel_btn.width() == 186
        assert window.more_btn.width() == 92
        assert "new_window" in window._menu_actions
        assert "review_queue" in window._menu_actions
        assert "save_joblog" in window._menu_actions
        assert "new_interpretation_honorarios" in window._menu_actions
        assert "job_log" in window._menu_actions
        assert "new_window" in window._overflow_menu_actions
        assert "new_interpretation_honorarios" in window._overflow_menu_actions
        assert window._menu_actions["new_interpretation_honorarios"].text() == "New Interpretation Honorários..."
        assert window._overflow_menu_actions["new_interpretation_honorarios"].text() == "New Interpretation Honorários..."
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_qt_main_window_uses_isolated_test_appdata(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    captured: dict[str, Path] = {}

    def _load_settings() -> dict[str, object]:
        captured["path"] = user_settings.settings_path()
        return _base_gui_settings()

    monkeypatch.setattr(app_window_module, "load_gui_settings", _load_settings)
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)

    window = QtMainWindow()
    try:
        assert captured["path"] == tmp_path / "appdata" / "LegalPDFTranslate" / "settings.json"
        assert "AppData\\Roaming\\LegalPDFTranslate" not in str(captured["path"])
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_eta_formatting() -> None:
    assert QtMainWindow._format_eta_seconds(None) == "--"
    assert QtMainWindow._format_eta_seconds(12.0) == "~12s"
    assert QtMainWindow._format_eta_seconds(125.0) == "~2m"


def test_queue_status_maps_into_dashboard_panel() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window._queue_total_jobs = 4
        window._on_queue_status({"job_id": "job-1", "status": "failed"})
        assert window.metric_pages_title_label.text() == "Jobs"
        assert window.metric_images_title_label.text() == "Skipped"
        assert window.metric_errors_title_label.text() == "Failed"
        assert window.metric_pages_value_label.text() == "1 / 4"
        assert window.metric_errors_value_label.text() == "1"
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_dashboard_card_can_expand_wider_than_stage_two_cap() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.show()
        app.processEvents()
        window._update_card_max_width(viewport_width=1664)
        app.processEvents()
        assert window.sidebar_frame.width() >= 136
        assert window.content_card.width() > 1400
        assert window.body_layout.direction() == QBoxLayout.Direction.LeftToRight
        window.resize(1800, 1000)
        app.processEvents()
        window._update_card_max_width(viewport_width=1664)
        app.processEvents()
        assert window.setup_panel.width() > window.progress_panel.width()
        assert window.setup_panel.width() < int(window.progress_panel.width() * 1.35)
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_wide_dashboard_frame_matches_centered_gemini_footprint(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    monkeypatch.setattr(
        window_adaptive_module,
        "available_screen_geometry",
        lambda _widget: QRect(0, 0, 1800, 1000),
    )

    window = QtMainWindow()
    try:
        window.show()
        app.processEvents()
        window.resize(1800, 1000)
        app.processEvents()
        window._update_card_max_width(viewport_width=1800)
        app.processEvents()

        assert window._layout_mode == "desktop_exact"
        assert window.body_layout.direction() == QBoxLayout.Direction.LeftToRight
        assert window.dashboard_frame.width() == 1200
        assert window.dashboard_frame.width() < window.content_card.width()
        assert window.dashboard_frame.x() == (window.content_card.width() - window.dashboard_frame.width()) // 2
        assert window.hero_row_layout.contentsMargins().bottom() == 14
        assert window.setup_panel.width() > window.progress_panel.width()
        assert window.setup_panel.width() < int(window.progress_panel.width() * 1.3)
        assert window.footer_card.width() < window.dashboard_frame.width()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_dashboard_reflows_for_compact_width() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.show()
        app.processEvents()
        window._update_card_max_width(viewport_width=920)
        app.processEvents()
        assert window._layout_mode == "stacked_compact"
        assert window.sidebar_frame.width() <= 74
        assert window.body_layout.direction() == QBoxLayout.Direction.TopToBottom
        assert window.footer_layout.itemAtPosition(0, 0).widget() is window.translate_btn
        assert window.footer_layout.itemAtPosition(1, 1).widget() is window.cancel_btn
        assert window.footer_layout.itemAtPosition(1, 2).widget() is window.more_btn
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_dashboard_keeps_two_column_layout_for_medium_width() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.show()
        app.processEvents()
        window._update_card_max_width(viewport_width=1360)
        app.processEvents()
        assert window._layout_mode == "desktop_compact"
        assert window.sidebar_frame.width() >= 118
        assert window.body_layout.direction() == QBoxLayout.Direction.LeftToRight
        assert window.dashboard_frame.width() == 1100
        assert window.dashboard_frame.x() == (window.content_card.width() - window.dashboard_frame.width()) // 2
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_main_window_small_screen_is_bounded_and_reserves_status_width(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    monkeypatch.setattr(
        window_adaptive_module,
        "available_screen_geometry",
        lambda _widget: QRect(0, 0, 1000, 700),
    )

    window = QtMainWindow()
    try:
        window.show()
        app.processEvents()
        assert window.width() <= 940
        assert window.height() <= 651
        window._update_card_max_width(viewport_width=920)
        app.processEvents()
        assert window.hero_status_spacer.width() == window.header_status_label.minimumWidth()
        assert window.header_status_label.minimumWidth() >= (
            window.header_status_label.fontMetrics().horizontalAdvance("Idle")
        )
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_settings_dialog_small_screen_is_bounded(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    monkeypatch.setattr(
        window_adaptive_module,
        "available_screen_geometry",
        lambda _widget: QRect(0, 0, 860, 640),
    )

    dialog = QtSettingsDialog(
        parent=None,
        settings=_base_gui_settings(),
        apply_callback=lambda _values, _persist: None,
        collect_debug_paths=lambda: [],
    )
    try:
        dialog.show()
        app.processEvents()
        assert dialog.width() <= 705
        assert dialog.height() <= 563
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_desktop_sidebar_buttons_have_room_for_full_labels() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.show()
        app.processEvents()
        window._update_card_max_width(viewport_width=1664)
        app.processEvents()

        assert window.dashboard_nav_btn.width() >= 112
        assert window.recent_jobs_nav_btn.width() >= 112
        dashboard_text_width = window.dashboard_nav_btn.fontMetrics().horizontalAdvance("Dashboard")
        recent_text_width = window.recent_jobs_nav_btn.fontMetrics().horizontalAdvance("Recent Jobs")
        assert dashboard_text_width < window.dashboard_nav_btn.width() - 14
        assert recent_text_width < window.recent_jobs_nav_btn.width() - 14
        assert window.progress_panel_title.text() == "Run Status"
        assert not window.more_menu.isVisible()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_target_language_field_shows_single_code_and_flag() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.lang_combo.setCurrentText("FR")
        window._refresh_lang_badge()
        app.processEvents()
        assert window.lang_combo.currentText() == "FR"
        assert window.lang_combo.itemData(
            window.lang_combo.currentIndex(),
            Qt.ItemDataRole.TextAlignmentRole,
        ) == int(Qt.AlignmentFlag.AlignCenter)
        assert window.flag_label.text() == ""
        pixmap = window.flag_label.pixmap()
        assert pixmap is not None and not pixmap.isNull()
        assert window.lang_caret_btn.icon().isNull() is False
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_target_language_popup_uses_full_names_and_content_width() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        assert window.lang_combo.itemData(0, POPUP_LABEL_ROLE) == "English"
        assert window.lang_combo.itemData(1, POPUP_LABEL_ROLE) == "French"
        assert window.lang_combo.itemData(2, POPUP_LABEL_ROLE) == "Arabic"
        assert window.lang_combo.currentText() == "EN"
        assert window.lang_combo.popupContentWidth() > window.lang_combo.maximumWidth()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_target_language_wrapper_click_opens_shared_popup_state() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.show()
        app.processEvents()
        QTest.mouseClick(
            window.lang_field,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
            window.lang_field.rect().center(),
        )
        app.processEvents()

        assert bool(window.lang_combo.property("popupOpen")) is True
        assert bool(window.lang_field.property("popupOpen")) is True
        assert window.lang_combo.view().minimumWidth() >= window.lang_combo.popupContentWidth()

        window.lang_combo.hidePopup()
        app.processEvents()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_main_window_start_page_defaults_to_one_even_with_saved_legacy_values(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings = _base_gui_settings(default_start_page=7, start_page=9)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)

    window = QtMainWindow()
    try:
        assert window.start_edit.text() == "1"
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_source_pdf_pages_cluster_stays_readable() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        assert window.pages_label.text() == "Pages: -"
        assert window.pages_label.minimumWidth() >= 74
        assert window.pdf_support_cluster.isHidden() is True
        assert window.pdf_pages_divider.isHidden() is True
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_source_pdf_pages_cluster_returns_when_source_is_selected(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    try:
        monkeypatch.setattr(app_window_module, "is_supported_source_file", lambda _path: True)
        monkeypatch.setattr(app_window_module, "get_page_count", lambda _path: 25)
        window.pdf_edit.setText(str(pdf_path))
        app.processEvents()
        assert window.pages_label.text() == "Pages: 25"
        assert window.pdf_support_cluster.isHidden() is False
        assert window.pdf_pages_divider.isHidden() is False
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_source_pdf_placeholder_shortens_in_compact_layouts() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.show()
        app.processEvents()
        window._update_card_max_width(viewport_width=1360)
        app.processEvents()
        assert window.pdf_edit.placeholderText() == "Select PDF or image..."
        window._update_card_max_width(viewport_width=920)
        app.processEvents()
        assert window.pdf_edit.placeholderText() == "Select source..."
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_metric_grid_keeps_retries_heading_without_row_level_cells() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        assert window.metric_retry_header_label.text() == "Retries"
        assert window.metric_grid_layout.itemAtPosition(1, 2) is None
        assert window.metric_grid_layout.itemAtPosition(2, 2) is None
        assert window.metric_pages_title_label.text() == "Pages"
        assert window.metric_errors_title_label.text() == "Errors"
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_busy_close_cancel_wait_shows_cancelling_state() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window._busy = True
        window._running = True
        window._queue_total_jobs = 1
        window._resolve_busy_close_choice = lambda: "cancel_wait"  # type: ignore[method-assign]
        event = QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted() is False
        assert window._cancel_pending is True
        assert "Cancelling... page ?" in window.status_label.text()
        assert "remaining <=" in window.status_label.text()
        assert window.header_status_label.text() == "Cancelling..."
        assert window.queue_status_label.text().startswith("Queue: cancelling page ?")
        assert window.cancel_btn.isEnabled() is False
        assert window._cancel_wait_timer.isActive() is True
    finally:
        window._busy = False
        window._running = False
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_cancel_wait_status_shows_page_elapsed_and_remaining(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    clock = {"now": 130.0}

    def _perf_counter() -> float:
        return clock["now"]

    monkeypatch.setattr("legalpdf_translate.qt_gui.app_window.time.perf_counter", _perf_counter)

    window = QtMainWindow()
    try:
        window._busy = True
        window._running = True
        window._active_request_page = 3
        window._active_request_budget_seconds = 120.0
        window._active_request_started_at = 100.0
        window._begin_cancel_wait()

        clock["now"] = 150.0
        window._refresh_cancel_wait_status()

        assert "page 3" in window.status_label.text()
        assert "waited ~20s" in window.status_label.text()
        assert "remaining <= ~1m" in window.status_label.text()
        assert "page 3" in window.queue_status_label.text()
    finally:
        window._busy = False
        window._running = False
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_ocr_heavy_risk_notes_cover_known_risky_settings(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        config = RunConfig(
            pdf_path=tmp_path / "sample.pdf",
            output_dir=tmp_path,
            target_lang=TargetLang.AR,
            image_mode=ImageMode.AUTO,
            ocr_mode=OcrMode.ALWAYS,
            ocr_engine=OcrEnginePolicy.LOCAL_THEN_API,
            effort_policy=EffortPolicy.FIXED_XHIGH,
            workers=3,
            resume=True,
            keep_intermediates=False,
        )
        notes = window._ocr_heavy_risk_notes(config)
        assert any("not 'api'" in note for note in notes)
        assert any("Image mode is 'auto'" in note for note in notes)
        assert any("fixed_xhigh" in note for note in notes)
        assert any("workers is 3" in note.lower() for note in notes)
        assert any("Resume is on" in note for note in notes)
        assert any("Keep intermediates is off" in note for note in notes)
        assert "OCR engine = api" in "\n".join(window._ocr_heavy_safe_profile_lines())
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_apply_transient_ocr_heavy_safe_profile_changes_current_form_only() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.effort_policy_combo.setCurrentText("adaptive")
        window.images_combo.setCurrentText("auto")
        window.ocr_mode_combo.setCurrentText("auto")
        window.ocr_engine_combo.setCurrentText("local_then_api")
        window.workers_spin.setValue(3)
        window.resume_check.setChecked(True)
        window.keep_check.setChecked(False)

        window._apply_transient_ocr_heavy_safe_profile()

        assert window._transient_safe_profile_active is True
        assert window.effort_policy_combo.currentText() == "fixed_high"
        assert window.images_combo.currentText() == "off"
        assert window.ocr_mode_combo.currentText() == "always"
        assert window.ocr_engine_combo.currentText() == "api"
        assert window.workers_spin.value() == 1
        assert window.resume_check.isChecked() is False
        assert window.keep_check.isChecked() is True

        window._restore_transient_safe_profile_if_needed()

        assert window._transient_safe_profile_active is False
        assert window.effort_policy_combo.currentText() == "adaptive"
        assert window.images_combo.currentText() == "auto"
        assert window.ocr_mode_combo.currentText() == "auto"
        assert window.ocr_engine_combo.currentText() == "local_then_api"
        assert window.workers_spin.value() == 3
        assert window.resume_check.isChecked() is True
        assert window.keep_check.isChecked() is False
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_save_settings_uses_backup_when_transient_safe_profile_is_active(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.save_gui_settings",
        lambda values: captured.update(values),
    )

    fake = SimpleNamespace(
        _defaults={},
        _transient_safe_profile_active=True,
        _transient_safe_profile_backup={
            "effort_policy": "adaptive",
            "image_mode": "auto",
            "ocr_mode": "auto",
            "ocr_engine": "local_then_api",
            "workers": 3,
            "resume": True,
            "keep_intermediates": False,
        },
        outdir_edit=_FakeEdit("C:/tmp/out"),
        lang_combo=_FakeCombo("FR"),
        effort_combo=_FakeCombo("high"),
        effort_policy_combo=_FakeCombo("fixed_high"),
        images_combo=_FakeCombo("off"),
        ocr_mode_combo=_FakeCombo("always"),
        ocr_engine_combo=_FakeCombo("api"),
        start_edit=_FakeEdit("3"),
        end_edit=_FakeEdit("8"),
        max_edit=_FakeEdit(""),
        workers_spin=_FakeSpin(1),
        resume_check=_FakeCheck(False),
        breaks_check=_FakeCheck(False),
        keep_check=_FakeCheck(True),
        queue_manifest_edit=_FakeEdit("C:/tmp/queue.json"),
        queue_rerun_failed_only_check=_FakeCheck(False),
    )

    QtMainWindow._save_settings(fake)

    assert captured["effort_policy"] == "adaptive"
    assert captured["image_mode"] == "auto"
    assert captured["ocr_mode"] == "auto"
    assert captured["ocr_engine"] == "local_then_api"
    assert captured["workers"] == 3
    assert captured["resume"] is True
    assert captured["keep_intermediates"] is False


def test_warn_ocr_api_only_apply_safe_profile_keeps_run_transient(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    window = QtMainWindow()
    try:
        window.pdf_edit.setText(str(pdf_path))
        window.outdir_edit.setText(str(out_dir))
        window.ocr_mode_combo.setCurrentText("auto")
        window.ocr_engine_combo.setCurrentText("local_then_api")
        window.images_combo.setCurrentText("auto")
        window.effort_policy_combo.setCurrentText("fixed_xhigh")
        window.workers_spin.setValue(3)
        window.resume_check.setChecked(True)
        window.keep_check.setChecked(False)

        monkeypatch.setattr("legalpdf_translate.qt_gui.app_window.which", lambda _name: None)
        monkeypatch.setattr(
            "legalpdf_translate.qt_gui.app_window.extract_ordered_page_text",
            lambda *_args, **_kwargs: SimpleNamespace(text="", extraction_failed=True),
        )
        monkeypatch.setattr(window, "_show_ocr_heavy_runtime_warning", lambda _config: "apply_safe")

        config = window._build_config()
        adjusted = window._warn_ocr_api_only_if_needed(config)

        assert adjusted is not None
        assert adjusted.effort_policy == EffortPolicy.FIXED_HIGH
        assert adjusted.image_mode == ImageMode.OFF
        assert adjusted.ocr_mode == OcrMode.ALWAYS
        assert adjusted.ocr_engine == OcrEnginePolicy.API
        assert adjusted.workers == 1
        assert adjusted.resume is False
        assert adjusted.keep_intermediates is True
        assert window._transient_safe_profile_active is True
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_warn_ocr_api_only_apply_safe_profile_preserves_override_inputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    pdf_path = tmp_path / "queue-input.pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")
    out_dir = tmp_path / "queue-out"
    out_dir.mkdir()

    window = QtMainWindow()
    try:
        window.ocr_mode_combo.setCurrentText("auto")
        window.ocr_engine_combo.setCurrentText("local_then_api")
        window.images_combo.setCurrentText("auto")
        window.effort_policy_combo.setCurrentText("fixed_xhigh")
        window.workers_spin.setValue(3)
        window.resume_check.setChecked(True)
        window.keep_check.setChecked(False)

        monkeypatch.setattr("legalpdf_translate.qt_gui.app_window.which", lambda _name: None)
        monkeypatch.setattr(
            "legalpdf_translate.qt_gui.app_window.extract_ordered_page_text",
            lambda *_args, **_kwargs: SimpleNamespace(text="", extraction_failed=True),
        )
        monkeypatch.setattr(window, "_show_ocr_heavy_runtime_warning", lambda _config: "apply_safe")

        critical_calls: list[str] = []
        monkeypatch.setattr(
            app_window_module.QMessageBox,
            "critical",
            lambda _self, _title, text: critical_calls.append(text),
        )

        def _rebuild_config() -> RunConfig:
            return window._build_config(
                pdf_override=str(pdf_path),
                outdir_override=str(out_dir),
                lang_override="FR",
            )

        config = _rebuild_config()
        adjusted = window._warn_ocr_api_only_if_needed(config, rebuild_config=_rebuild_config)

        assert adjusted is not None
        assert critical_calls == []
        assert adjusted.pdf_path == pdf_path.resolve()
        assert adjusted.output_dir == out_dir.resolve()
        assert adjusted.target_lang == TargetLang.FR
        assert adjusted.effort_policy == EffortPolicy.FIXED_HIGH
        assert adjusted.image_mode == ImageMode.OFF
        assert adjusted.ocr_mode == OcrMode.ALWAYS
        assert adjusted.ocr_engine == OcrEnginePolicy.API
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_warn_ocr_api_only_continue_keeps_override_config_without_rebuild(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    pdf_path = tmp_path / "override.pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")
    out_dir = tmp_path / "override-out"
    out_dir.mkdir()

    window = QtMainWindow()
    try:
        monkeypatch.setattr("legalpdf_translate.qt_gui.app_window.which", lambda _name: None)
        monkeypatch.setattr(
            "legalpdf_translate.qt_gui.app_window.extract_ordered_page_text",
            lambda *_args, **_kwargs: SimpleNamespace(text="", extraction_failed=True),
        )
        monkeypatch.setattr(window, "_show_ocr_heavy_runtime_warning", lambda _config: "continue")

        rebuild_calls: list[bool] = []

        def _rebuild_config() -> RunConfig:
            rebuild_calls.append(True)
            return window._build_config(
                pdf_override=str(pdf_path),
                outdir_override=str(out_dir),
                lang_override="AR",
            )

        config = _rebuild_config()
        rebuild_calls.clear()
        adjusted = window._warn_ocr_api_only_if_needed(config, rebuild_config=_rebuild_config)

        assert adjusted is config
        assert rebuild_calls == []
        assert adjusted.pdf_path == pdf_path.resolve()
        assert adjusted.output_dir == out_dir.resolve()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_warn_ocr_api_only_cancel_returns_none_without_override_rebuild(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    pdf_path = tmp_path / "override.pdf"
    pdf_path.write_text("placeholder", encoding="utf-8")
    out_dir = tmp_path / "override-out"
    out_dir.mkdir()

    window = QtMainWindow()
    try:
        monkeypatch.setattr("legalpdf_translate.qt_gui.app_window.which", lambda _name: None)
        monkeypatch.setattr(
            "legalpdf_translate.qt_gui.app_window.extract_ordered_page_text",
            lambda *_args, **_kwargs: SimpleNamespace(text="", extraction_failed=True),
        )
        monkeypatch.setattr(window, "_show_ocr_heavy_runtime_warning", lambda _config: "cancel")

        rebuild_calls: list[bool] = []

        def _rebuild_config() -> RunConfig:
            rebuild_calls.append(True)
            return window._build_config(
                pdf_override=str(pdf_path),
                outdir_override=str(out_dir),
                lang_override="AR",
            )

        config = _rebuild_config()
        rebuild_calls.clear()
        adjusted = window._warn_ocr_api_only_if_needed(config, rebuild_config=_rebuild_config)

        assert adjusted is None
        assert rebuild_calls == []
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_no_wheel_combo_ignores_closed_popup_wheel() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    combo = NoWheelComboBox()
    try:
        combo.addItems(["a", "b"])
        event = _FakeEvent()
        combo.wheelEvent(event)
        assert event.ignored is True
        assert combo._should_ignore_wheel() is True
    finally:
        combo.deleteLater()
        if owns_app:
            app.quit()


def test_no_wheel_combo_allows_open_popup_scroll_intentionally(monkeypatch) -> None:
    combo = NoWheelComboBox()
    try:
        monkeypatch.setattr(combo, "view", lambda: SimpleNamespace(isVisible=lambda: True))
        assert combo._should_ignore_wheel() is False
    finally:
        combo.deleteLater()


def test_no_wheel_spin_ignores_wheel() -> None:
    spin = NoWheelSpinBox()
    try:
        event = _FakeEvent()
        spin.wheelEvent(event)
        assert event.ignored is True
        assert spin._should_ignore_wheel() is True
    finally:
        spin.deleteLater()


def test_main_window_uses_guarded_run_critical_controls() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        assert isinstance(window.lang_combo, NoWheelComboBox)
        assert isinstance(window.effort_policy_combo, NoWheelComboBox)
        assert isinstance(window.effort_combo, NoWheelComboBox)
        assert isinstance(window.images_combo, NoWheelComboBox)
        assert isinstance(window.ocr_mode_combo, NoWheelComboBox)
        assert isinstance(window.ocr_engine_combo, NoWheelComboBox)
        assert isinstance(window.workers_spin, NoWheelSpinBox)
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_advanced_settings_hover_and_open_state_stays_local_to_active_combo() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.show()
        window._set_adv_visible(True)
        app.processEvents()

        QApplication.sendEvent(window.effort_policy_combo, QEvent(QEvent.Type.Enter))
        assert bool(window.effort_policy_combo.property("hovered")) is True
        assert bool(window.images_combo.property("hovered")) is False

        window.effort_policy_combo.showPopup()
        app.processEvents()
        assert bool(window.effort_policy_combo.property("popupOpen")) is True
        assert bool(window.images_combo.property("popupOpen")) is False
        window.effort_policy_combo.hidePopup()
        app.processEvents()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_settings_dialog_uses_guarded_run_critical_controls(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings_dialog = QtSettingsDialog(
        parent=None,
        settings={},
        apply_callback=lambda *_args, **_kwargs: None,
        collect_debug_paths=lambda: [],
        current_pdf_path=None,
    )
    try:
        assert isinstance(settings_dialog.ocr_provider_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_lang_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_effort_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_effort_policy_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_images_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_workers_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.ocr_mode_default_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.ocr_engine_default_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.glossary_lang_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.glossary_tier_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.study_category_filter_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.study_status_filter_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.study_coverage_filter_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.study_corpus_source_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.study_mode_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.ui_theme_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.ui_scale_combo, NoWheelComboBox)
        assert settings_dialog.ocr_provider_combo.isEditable() is False
        assert settings_dialog.default_lang_combo.isEditable() is False
        assert settings_dialog.default_effort_combo.isEditable() is False
        assert settings_dialog.default_effort_policy_combo.isEditable() is False
        assert settings_dialog.default_images_combo.isEditable() is False
        assert settings_dialog.default_workers_combo.isEditable() is False
        assert settings_dialog.ocr_mode_default_combo.isEditable() is False
        assert settings_dialog.ocr_engine_default_combo.isEditable() is False
        assert settings_dialog.glossary_lang_combo.isEditable() is False
        assert settings_dialog.glossary_tier_combo.isEditable() is False
        assert settings_dialog.study_category_filter_combo.isEditable() is False
        assert settings_dialog.study_status_filter_combo.isEditable() is False
        assert settings_dialog.study_coverage_filter_combo.isEditable() is False
        assert settings_dialog.study_corpus_source_combo.isEditable() is False
        assert settings_dialog.study_mode_combo.isEditable() is False
        assert settings_dialog.ui_theme_combo.isEditable() is False
        assert settings_dialog.ui_scale_combo.isEditable() is False
        assert isinstance(settings_dialog.study_coverage_spin, NoWheelSpinBox)
        assert isinstance(settings_dialog.study_snippet_chars_spin, NoWheelSpinBox)
        assert settings_dialog.save_btn.objectName() == "PrimaryButton"
        assert settings_dialog.openai_clear_btn.objectName() == "DangerButton"
        assert settings_dialog.ocr_clear_btn.objectName() == "DangerButton"
        assert settings_dialog.glossary_builtin_btn.objectName() == "DangerButton"
        assert settings_dialog.restore_defaults_btn.objectName() == "DangerButton"
        assert settings_dialog.glossary_remove_rows_btn.objectName() == "DangerButton"
        assert settings_dialog.study_remove_run_dir_btn.objectName() == "DangerButton"
        assert settings_dialog.study_clear_run_dirs_btn.objectName() == "DangerButton"
        assert settings_dialog.study_remove_pdf_btn.objectName() == "DangerButton"
        assert settings_dialog.study_clear_pdf_btn.objectName() == "DangerButton"
        assert settings_dialog.study_generate_btn.objectName() == "PrimaryButton"
        assert settings_dialog.study_add_selected_btn.objectName() == "PrimaryButton"
        assert settings_dialog.study_copy_to_ai_btn.objectName() == "PrimaryButton"
        assert settings_dialog.create_bundle_btn.objectName() == "PrimaryButton"
        assert isinstance(settings_dialog.gmail_intake_port_spin, NoWheelSpinBox)
    finally:
        settings_dialog.close()
        settings_dialog.deleteLater()
        if owns_app:
            app.quit()


def test_settings_dialog_generates_bridge_token_when_enabled() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings_dialog = QtSettingsDialog(
        parent=None,
        settings=_base_gui_settings(),
        apply_callback=lambda *_args, **_kwargs: None,
        collect_debug_paths=lambda: [],
        current_pdf_path=None,
    )
    try:
        settings_dialog.gmail_intake_enabled_check.setChecked(True)
        settings_dialog.gmail_intake_token_edit.clear()
        settings_dialog.gmail_intake_port_spin.setValue(9015)

        values = settings_dialog._collect_values()

        assert values["gmail_intake_bridge_enabled"] is True
        assert values["gmail_intake_port"] == 9015
        assert isinstance(values["gmail_intake_bridge_token"], str)
        assert len(str(values["gmail_intake_bridge_token"])) >= 20
        assert settings_dialog.gmail_intake_token_edit.text() == values["gmail_intake_bridge_token"]
    finally:
        settings_dialog.close()
        settings_dialog.deleteLater()
        if owns_app:
            app.quit()


def test_settings_dialog_normalizes_default_start_page_to_one() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings_dialog = QtSettingsDialog(
        parent=None,
        settings=_base_gui_settings(default_start_page=7),
        apply_callback=lambda *_args, **_kwargs: None,
        collect_debug_paths=lambda: [],
        current_pdf_path=None,
    )
    try:
        values = settings_dialog._collect_values()
        assert not hasattr(settings_dialog, "default_start_edit")
        assert values["default_start_page"] == 1
    finally:
        settings_dialog.close()
        settings_dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_intake_bridge_starts_when_enabled(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="stage-one-token",
        gmail_intake_port=9011,
    )
    registration_calls: list[object] = []
    monkeypatch.setattr(app_window_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(
        app_window_module,
        "maybe_ensure_edge_native_host_registered",
        lambda *, base_dir: registration_calls.append(base_dir) or SimpleNamespace(
            ok=True,
            changed=True,
            manifest_path="C:/Users/FA507/AppData/Roaming/LegalPDFTranslate/native_messaging/com.legalpdf.gmail_focus.edge.json",
            executable_path="C:/Users/FA507/.codex/legalpdf_translate/dist/legalpdf_translate/LegalPDFGmailFocusHost.exe",
            reason="registered",
        ),
    )
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)

    window = QtMainWindow()
    try:
        assert len(_FakeBridge.instances) == 1
        bridge = _FakeBridge.instances[0]
        assert bridge.started is True
        assert window._gmail_intake_bridge is bridge
        assert len(registration_calls) == 1
        assert "Gmail intake bridge listening on http://127.0.0.1:9011/gmail-intake." in window.log_text.toPlainText()
        assert "Edge Gmail focus helper registered for this user:" in window.log_text.toPlainText()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_intake_bridge_skips_native_host_registration_in_pytest_runtime(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="stage-one-token",
        gmail_intake_port=9011,
    )
    monkeypatch.setattr(app_window_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)

    window = QtMainWindow()
    try:
        assert len(_FakeBridge.instances) == 1
        assert "Edge Gmail focus helper auto-registration skipped: skipped_pytest_runtime." in window.log_text.toPlainText()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_intake_bridge_restarts_and_stops_with_settings_changes(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="initial-token",
        gmail_intake_port=9012,
    )
    monkeypatch.setattr(app_window_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)

    window = QtMainWindow()
    try:
        initial_bridge = _FakeBridge.instances[0]
        window.apply_settings_from_dialog(
            {
                "gmail_intake_bridge_enabled": True,
                "gmail_intake_bridge_token": "updated-token",
                "gmail_intake_port": 9013,
            },
            False,
        )
        updated_bridge = _FakeBridge.instances[-1]
        assert initial_bridge.stopped is True
        assert updated_bridge.started is True
        assert updated_bridge is not initial_bridge
        assert window._gmail_intake_bridge is updated_bridge

        window.apply_settings_from_dialog(
            {
                "gmail_intake_bridge_enabled": False,
                "gmail_intake_bridge_token": "updated-token",
                "gmail_intake_port": 9013,
            },
            False,
        )
        assert updated_bridge.stopped is True
        assert window._gmail_intake_bridge is None
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_intake_bridge_does_not_start_without_token(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="",
        gmail_intake_port=9014,
    )
    monkeypatch.setattr(app_window_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)

    window = QtMainWindow()
    try:
        assert _FakeBridge.instances == []
        assert window._gmail_intake_bridge is None
        assert "Gmail intake bridge is enabled but token is blank; bridge not started." in window.log_text.toPlainText()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_intake_bridge_start_failure_is_visible(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="stage-one-token",
        gmail_intake_port=8765,
    )
    captured: dict[str, str] = {}
    monkeypatch.setattr(app_window_module, "LocalGmailIntakeBridge", _FailingBridge)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)
    monkeypatch.setattr(
        app_window_module.QMessageBox,
        "warning",
        lambda _self, title, text: captured.update({"title": title, "text": text}),
    )

    window = QtMainWindow()
    try:
        assert window._gmail_intake_bridge is None
        assert window.status_label.text() == "Gmail intake bridge unavailable"
        assert window.header_status_label.text() == "Gmail intake bridge unavailable"
        assert window._dashboard_snapshot.current_task == "Gmail intake bridge unavailable"
        log_text = window.log_text.toPlainText()
        assert "Gmail intake bridge failed to start on 127.0.0.1:8765:" in log_text
        assert captured["title"] == "Gmail intake bridge unavailable"
        assert "127.0.0.1:8765" in captured["text"]
        assert "Another process may already be using this port." in captured["text"]
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_intake_bridge_stops_on_window_close(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="stage-one-token",
        gmail_intake_port=9016,
    )
    monkeypatch.setattr(app_window_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)

    window = QtMainWindow()
    bridge = _FakeBridge.instances[0]
    window.close()
    assert bridge.stopped is True
    window.deleteLater()
    if owns_app:
        app.quit()


def test_gmail_intake_bridge_runtime_metadata_is_written_and_cleared(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="stage-one-token",
        gmail_intake_port=9017,
    )
    monkeypatch.setattr(app_window_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)
    monkeypatch.setattr(app_window_module, "app_data_dir", lambda: tmp_path)

    window = QtMainWindow()
    metadata_path = bridge_runtime_metadata_path(tmp_path)
    try:
        payload = load_bridge_runtime_metadata(tmp_path)
        assert metadata_path.exists() is True
        assert payload is not None
        assert payload["port"] == 9017
        assert payload["pid"] > 0
        assert payload["window_title"].startswith("LegalPDF Translate")
        assert payload["running"] is True
        assert isinstance(payload["build_identity"], dict) or payload["build_identity"] is None
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()

    assert metadata_path.exists() is False


def test_workspace_controller_gmail_bridge_backs_off_when_browser_app_owns_live_bridge(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="stage-browser-token",
        gmail_intake_port=9020,
    )
    monkeypatch.setattr(window_controller_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(window_controller_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(window_controller_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        window_controller_module,
        "validate_bridge_owner",
        lambda *, bridge_port, base_dir: SimpleNamespace(
            ok=bridge_port == 9020 and base_dir == tmp_path,
            pid=5555,
            hwnd=None,
            reason="bridge_owner_ready",
            owner_kind="browser_app",
            browser_url="http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake",
            workspace_id="gmail-intake",
            runtime_mode="live",
        ),
    )
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)
    monkeypatch.setattr(app_window_module, "app_data_dir", lambda: tmp_path)

    controller = WorkspaceWindowController(app=app, build_identity=None)
    windows: list[QtMainWindow] = []
    try:
        window = controller.create_workspace(show=False, focus=False)
        windows.append(window)
        assert _FakeBridge.instances == []
        assert controller.gmail_intake_bridge() is None
        assert window._gmail_intake_bridge is None
        assert "Gmail intake bridge already owned by browser app on 127.0.0.1:9020." in window.log_text.toPlainText()
    finally:
        _close_qt_windows(app, windows)
        if owns_app:
            app.quit()


def test_workspace_controller_gmail_intake_reuses_last_active_pristine_workspace(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="stage-two-token",
        gmail_intake_port=9021,
    )
    monkeypatch.setattr(window_controller_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(window_controller_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(window_controller_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)
    monkeypatch.setattr(app_window_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        app_window_module,
        "maybe_ensure_edge_native_host_registered",
        lambda *, base_dir: SimpleNamespace(
            ok=True,
            changed=False,
            manifest_path=str(base_dir / "native.json"),
            executable_path=str(base_dir / "focus.exe"),
            reason="ready",
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "request_window_attention",
        lambda window: WindowAttentionResult(
            requested=True,
            restored=False,
            focused=True,
            flashed=False,
            reason=f"focused:{window.windowTitle()}",
        ),
    )
    accepted: list[tuple[QtMainWindow, InboundMailContext]] = []
    monkeypatch.setattr(QtMainWindow, "_start_gmail_message_load", lambda self, context: accepted.append((self, context)))

    controller = WorkspaceWindowController(app=app, build_identity=None)
    windows: list[QtMainWindow] = []
    try:
        first = controller.create_workspace(show=False, focus=False)
        second = controller.create_workspace(show=False, focus=False)
        windows.extend([first, second])
        controller.note_window_activated(second)

        context = InboundMailContext(
            message_id="msg-201",
            thread_id="thread-301",
            subject="Stage 2 intake reuse",
        )
        controller._route_gmail_intake_on_main_thread(context)

        assert len(_FakeBridge.instances) == 1
        assert first._gmail_intake_bridge is None
        assert second._gmail_intake_bridge is None
        assert controller.gmail_intake_bridge() is _FakeBridge.instances[0]
        assert len(controller.windows()) == 2
        assert accepted == [(second, context)]
        payload = load_bridge_runtime_metadata(tmp_path)
        assert payload is not None
        assert payload["window_title"] == second.windowTitle()
        assert payload["port"] == 9021
    finally:
        _close_qt_windows(app, windows)
        if owns_app:
            app.quit()


def test_workspace_controller_gmail_intake_opens_new_window_for_occupied_workspace(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="stage-two-token",
        gmail_intake_port=9022,
    )
    monkeypatch.setattr(window_controller_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(window_controller_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(window_controller_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)
    monkeypatch.setattr(app_window_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        app_window_module,
        "maybe_ensure_edge_native_host_registered",
        lambda *, base_dir: SimpleNamespace(
            ok=True,
            changed=False,
            manifest_path=str(base_dir / "native.json"),
            executable_path=str(base_dir / "focus.exe"),
            reason="ready",
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "request_window_attention",
        lambda _window: WindowAttentionResult(
            requested=True,
            restored=False,
            focused=True,
            flashed=False,
            reason="focused",
        ),
    )
    accepted: list[tuple[QtMainWindow, InboundMailContext]] = []
    monkeypatch.setattr(QtMainWindow, "_start_gmail_message_load", lambda self, context: accepted.append((self, context)))

    controller = WorkspaceWindowController(app=app, build_identity=None)
    windows: list[QtMainWindow] = []
    try:
        first = controller.create_workspace(show=False, focus=False)
        windows.append(first)
        controller.note_window_activated(first)
        first.pdf_edit.setText("C:/occupied-job.pdf")

        context = InboundMailContext(
            message_id="msg-202",
            thread_id="thread-302",
            subject="Stage 2 intake new window",
        )
        controller._route_gmail_intake_on_main_thread(context)

        routed_window = accepted[0][0]
        windows.extend(window for window in controller.windows() if window not in windows)
        assert len(controller.windows()) == 2
        assert routed_window is not first
        assert accepted == [(routed_window, context)]
        assert "Workspace 2" in routed_window.windowTitle()
    finally:
        _close_qt_windows(app, windows)
        if owns_app:
            app.quit()


def test_workspace_controller_reconfigures_gmail_bridge_without_overwriting_other_window_drafts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    _FakeBridge.instances = []
    settings_store = _base_gui_settings(
        gmail_intake_bridge_enabled=True,
        gmail_intake_bridge_token="initial-token",
        gmail_intake_port=9023,
    )
    monkeypatch.setattr(window_controller_module, "LocalGmailIntakeBridge", _FakeBridge)
    monkeypatch.setattr(window_controller_module, "load_gui_settings", lambda: dict(settings_store))
    monkeypatch.setattr(window_controller_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings_store))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda values: settings_store.update(values))
    monkeypatch.setattr(app_window_module, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        app_window_module,
        "maybe_ensure_edge_native_host_registered",
        lambda *, base_dir: SimpleNamespace(
            ok=True,
            changed=False,
            manifest_path=str(base_dir / "native.json"),
            executable_path=str(base_dir / "focus.exe"),
            reason="ready",
        ),
    )

    controller = WorkspaceWindowController(app=app, build_identity=None)
    windows: list[QtMainWindow] = []
    try:
        first = controller.create_workspace(show=False, focus=False)
        second = controller.create_workspace(show=False, focus=False)
        windows.extend([first, second])

        initial_bridge = _FakeBridge.instances[0]
        second.pdf_edit.setText("C:/draft-job.pdf")
        second.outdir_edit.setText("C:/draft-out")
        second.queue_manifest_edit.setText("C:/draft-queue.json")

        first.apply_settings_from_dialog(
            {
                "gmail_intake_bridge_enabled": True,
                "gmail_intake_bridge_token": "updated-token",
                "gmail_intake_port": 9024,
            },
            True,
        )

        updated_bridge = _FakeBridge.instances[-1]
        assert initial_bridge.stopped is True
        assert updated_bridge.started is True
        assert updated_bridge is not initial_bridge
        assert controller.gmail_intake_bridge() is updated_bridge
        assert second._gmail_intake_bridge is None
        assert second.pdf_edit.text() == "C:/draft-job.pdf"
        assert second.outdir_edit.text() == "C:/draft-out"
        assert second.queue_manifest_edit.text() == "C:/draft-queue.json"
        assert second._defaults["gmail_intake_bridge_token"] == "updated-token"
        assert second._defaults["gmail_intake_port"] == 9024
    finally:
        _close_qt_windows(app, windows)
        if owns_app:
            app.quit()


def test_gmail_intake_acceptance_updates_visible_ui_without_starting_translation(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: _base_gui_settings())
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda _values: None)
    attention_calls: list[object] = []
    monkeypatch.setattr(
        app_window_module,
        "request_window_attention",
        lambda window: attention_calls.append(window)
        or WindowAttentionResult(
            requested=True,
            restored=False,
            focused=True,
            flashed=False,
            reason="foreground_set",
        ),
    )

    window = QtMainWindow()
    try:
        calls: list[InboundMailContext] = []
        monkeypatch.setattr(window, "_start_gmail_message_load", calls.append)
        context = InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            account_email="court@example.com",
        )

        window._on_gmail_intake_received(context)

        assert window._last_gmail_intake_context == context
        assert window.header_status_label.text() == "Gmail intake accepted"
        assert window.status_label.text() == "Gmail intake accepted: Court reply needed"
        log_text = window.log_text.toPlainText()
        assert "thread_id=thread-200" in log_text
        assert "message_id=msg-100" in log_text
        assert "account_email=court@example.com" in log_text
        assert calls == [context]
        assert attention_calls == [window]
        assert window._busy is False
        assert window._running is False
        assert window._last_summary is None
        assert window._last_joblog_seed is None
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_intake_acceptance_starts_message_load_when_idle() -> None:
    calls: list[InboundMailContext] = []
    logs: list[str] = []
    fake = SimpleNamespace(
        _busy=False,
        _last_gmail_intake_context=None,
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _append_log=logs.append,
        _start_gmail_message_load=calls.append,
    )
    context = InboundMailContext(
        message_id="msg-100",
        thread_id="thread-200",
        subject="Court reply needed",
        account_email="court@example.com",
    )

    QtMainWindow._on_gmail_intake_received(fake, context)

    assert fake._last_gmail_intake_context == context
    assert fake.header_status_label.text == "Gmail intake accepted"
    assert fake.status_label.text == "Gmail intake accepted: Court reply needed"
    assert calls == [context]
    assert any("thread_id=thread-200" in entry for entry in logs)


def test_gmail_intake_acceptance_skips_message_load_while_busy(monkeypatch) -> None:
    calls: list[InboundMailContext] = []
    logs: list[str] = []
    message_box_calls: list[tuple[str, str]] = []
    attention_calls: list[object] = []
    original_information = app_window_module.QMessageBox.information
    app_window_module.QMessageBox.information = (
        lambda _self, title, text: message_box_calls.append((title, text))
    )
    monkeypatch.setattr(
        app_window_module,
        "request_window_attention",
        lambda window: attention_calls.append(window)
        or WindowAttentionResult(
            requested=True,
            restored=False,
            focused=False,
            flashed=True,
            reason="foreground_blocked",
        ),
    )
    fake = SimpleNamespace(
        _busy=True,
        _last_gmail_intake_context=None,
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _append_log=logs.append,
        _start_gmail_message_load=calls.append,
    )

    QtMainWindow._on_gmail_intake_received(
        fake,
        InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
    )

    try:
        assert calls == []
        assert fake.header_status_label.text == "Gmail intake blocked"
        assert fake.status_label.text == "Gmail intake blocked by current task"
        assert attention_calls == [fake, fake]
        assert any("fetch skipped because another task is already running" in entry for entry in logs)
        assert message_box_calls == [
            (
                "Gmail intake",
                "Gmail intake was received, but another task is already running.\n\n"
                "Finish or cancel the current translation, then click the Gmail extension again.",
            )
        ]
    finally:
        app_window_module.QMessageBox.information = original_information


def test_gmail_batch_review_dialog_returns_selected_attachments_and_target_lang() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachments = (
        GmailAttachmentCandidate(
            attachment_id="att-1",
            filename="court.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            source_message_id="msg-100",
        ),
        GmailAttachmentCandidate(
            attachment_id="att-2",
            filename="photo.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            source_message_id="msg-100",
        ),
    )
    dialog = QtGmailBatchReviewDialog(
        parent=None,
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=attachments,
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        target_lang="FR",
        default_start_page=2,
        output_dir_text="C:/out",
    )
    try:
        assert isinstance(dialog.workflow_combo, NoWheelComboBox)
        assert dialog.workflow_combo.isEditable() is False
        assert isinstance(dialog.target_lang_combo, NoWheelComboBox)
        assert dialog.target_lang_combo.isEditable() is False
        assert dialog.prepare_btn.objectName() == "PrimaryButton"
        assert dialog.summary_info_btn.objectName() == "InlineInfoButton"
        assert dialog.summary_label.text() == "Court reply needed | 2 files"
        assert dialog.output_dir_label.text() == "Folder: out"
        assert dialog.target_lang_combo.currentText() == "FR"
        assert dialog.table.horizontalHeaderItem(0).text() == "File"
        assert dialog.table.horizontalHeaderItem(3).text() == "Start"
        assert dialog.start_page_label.text() == "Start page"
        assert dialog.table.item(0, 3).text() == "1"
        assert dialog.table.item(1, 3).text() == "1"
        assert dialog.preview_btn.text() == "Preview"
        assert dialog.prepare_btn.text() == "Prepare selected"
        dialog.target_lang_combo.setCurrentText("EN")
        dialog.table.selectAll()
        dialog._accept_selection()
        assert dialog.selected_attachments == attachments
        assert dialog.review_result == GmailBatchReviewResult(
            selections=(
                GmailAttachmentSelection(candidate=attachments[0], start_page=1),
                GmailAttachmentSelection(candidate=attachments[1], start_page=1),
            ),
            target_lang="EN",
        )
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_batch_review_dialog_interpretation_mode_hides_translation_controls_and_requires_one_attachment() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachments = (
        GmailAttachmentCandidate(
            attachment_id="att-1",
            filename="notice.pdf",
            mime_type="application/pdf",
            size_bytes=2048,
            source_message_id="msg-100",
        ),
        GmailAttachmentCandidate(
            attachment_id="att-2",
            filename="photo.jpg",
            mime_type="image/jpeg",
            size_bytes=1024,
            source_message_id="msg-100",
        ),
    )
    dialog = QtGmailBatchReviewDialog(
        parent=None,
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=attachments,
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        target_lang="FR",
        default_start_page=2,
        output_dir_text="C:/out",
    )
    try:
        dialog.workflow_combo.setCurrentIndex(
            dialog.workflow_combo.findData(GMAIL_INTAKE_WORKFLOW_INTERPRETATION)
        )
        assert dialog.target_lang_combo.isHidden()
        assert dialog.start_page_spin.isHidden()
        assert dialog.table.isColumnHidden(3) is True
        assert dialog.table.selectionMode() == dialog.table.SelectionMode.SingleSelection
        assert dialog.prepare_btn.text() == "Prepare notice"
        dialog.table.selectRow(0)
        dialog._refresh_actions()
        assert dialog.prepare_btn.text() == "Prepare notice"
        dialog._accept_selection()
        assert dialog.review_result == GmailBatchReviewResult(
            selections=(GmailAttachmentSelection(candidate=attachments[0], start_page=1),),
            target_lang="",
            workflow_kind=GMAIL_INTAKE_WORKFLOW_INTERPRETATION,
        )
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_batch_review_dialog_preview_updates_start_page(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )

    class _FakePreviewDialog:
        def __init__(self, **kwargs) -> None:
            assert kwargs["initial_start_page"] == 1
            self.selected_start_page = 3
            self.resolved_page_count = 5
            self.resolved_local_path = tmp_path / "preview.pdf"

        def exec(self) -> int:
            return 1

        def deleteLater(self) -> None:
            return None

    monkeypatch.setattr(dialogs_module, "QtGmailAttachmentPreviewDialog", _FakePreviewDialog)

    dialog = QtGmailBatchReviewDialog(
        parent=None,
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        target_lang="FR",
        default_start_page=2,
        output_dir_text="C:/out",
    )
    try:
        dialog.table.selectRow(0)
        dialog._open_preview_for_current_row()
        assert dialog.table.item(0, 3).text() == "3"
        assert dialog.pages_value_label.text() == "5 pages"
        assert dialog.detail_attachment_label.text() == "court.pdf"
        assert dialog._preview_cache[attachment.attachment_id] == (tmp_path / "preview.pdf")
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def _preview_png_bytes(page_number: int) -> tuple[bytes, int, int]:
    width = 420
    height = 620
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#f7f4ee") if page_number % 2 else QColor("#eef4ff"))
    painter = QPainter(image)
    painter.setPen(QPen(QColor("#1c2430"), 4))
    painter.drawRect(18, 18, width - 36, height - 36)
    painter.setPen(QColor("#243243"))
    painter.drawText(48, 70, f"Page {page_number}")
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data()), width, height


class _FakeLazyPreviewDialog(QtGmailAttachmentPreviewDialog):
    def __init__(self, *args, **kwargs) -> None:
        self.started_pages: list[int] = []
        super().__init__(*args, **kwargs)

    def _start_bootstrap(self) -> None:
        return None

    def _start_page_worker(self, page_number: int) -> None:
        self.started_pages.append(page_number)
        self._inflight_pages.add(page_number)
        image_bytes, width, height = _preview_png_bytes(page_number)
        self._on_page_loaded(
            GmailAttachmentPreviewPageResult(
                attachment=self._attachment,
                local_path=Path("C:/preview/sample.pdf"),
                page_count=max(1, int(self._page_count or 1)),
                page_number=page_number,
                image_bytes=image_bytes,
                image_format="png",
                width_px=width,
                height_px=height,
            )
        )


class _TrackingScaledPreviewDialog(_FakeLazyPreviewDialog):
    def __init__(self, *args, **kwargs) -> None:
        self.scaled_refresh_count = 0
        super().__init__(*args, **kwargs)

    def _refresh_scaled_preview(self) -> None:
        self.scaled_refresh_count += 1
        super()._refresh_scaled_preview()


def _wait_for_preview_refresh(dialog: QtGmailAttachmentPreviewDialog) -> None:
    app = QApplication.instance()
    assert app is not None
    QTest.qWait(dialog._PAGE_REFRESH_DEBOUNCE_MS + 40)
    app.processEvents()


def test_gmail_attachment_preview_dialog_builds_scroll_cards_and_accepts_selected_page(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    dialog = _FakeLazyPreviewDialog(
        parent=None,
        attachment=attachment,
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        preview_dir=tmp_path,
        initial_start_page=1,
        cached_path=tmp_path / "preview.pdf",
        known_page_count=5,
    )
    try:
        dialog.show()
        app.processEvents()
        assert dialog.use_page_btn.objectName() == "PrimaryButton"
        dialog._on_bootstrap_loaded(
            GmailAttachmentPreviewBootstrapResult(
                attachment=attachment,
                local_path=tmp_path / "preview.pdf",
                page_count=5,
                page_sizes=((420.0, 620.0),) * 5,
            )
        )
        app.processEvents()
        _wait_for_preview_refresh(dialog)
        assert len(dialog._page_cards) == 5
        assert dialog.jump_spin.value() == 1
        assert "Page 1 is the default." in dialog.status_label.text()
        assert dialog._page_cards[1].use_page_btn.text() == "Start from this page"
        assert dialog._page_cards[1].use_page_btn.objectName() == "PrimaryButton"
        assert 1 in dialog.started_pages
        dialog._page_cards[4].use_page_btn.click()
        assert dialog.selected_start_page == 4
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_attachment_preview_dialog_jump_scrolls_and_suppresses_duplicate_requests(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    dialog = _FakeLazyPreviewDialog(
        parent=None,
        attachment=attachment,
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        preview_dir=tmp_path,
        initial_start_page=4,
        cached_path=tmp_path / "preview.pdf",
        known_page_count=6,
    )
    try:
        dialog.show()
        app.processEvents()
        dialog._on_bootstrap_loaded(
            GmailAttachmentPreviewBootstrapResult(
                attachment=attachment,
                local_path=tmp_path / "preview.pdf",
                page_count=6,
                page_sizes=((420.0, 620.0),) * 6,
            )
        )
        app.processEvents()
        _wait_for_preview_refresh(dialog)
        dialog._scroll_to_page(4)
        _wait_for_preview_refresh(dialog)
        assert dialog.jump_spin.value() == 4
        assert 4 in dialog.started_pages

        dialog.jump_spin.setValue(5)
        dialog._jump_to_page()
        _wait_for_preview_refresh(dialog)
        assert dialog._current_page == 5
        assert dialog.jump_spin.value() == 5
        assert 5 in dialog.started_pages

        dialog._page_cache.pop(6, None)
        dialog._page_cards[6].clear_cached_pixmap()
        dialog._queue_page_render(6)
        dialog._queue_page_render(6)
        assert dialog._queued_pages == [6]

        cached_page_count = dialog.started_pages.count(5)
        dialog._queue_page_render(5)
        dialog._start_next_page_workers()
        assert dialog.started_pages.count(5) == cached_page_count
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_attachment_preview_dialog_image_preview_uses_page_one(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="photo.jpg",
        mime_type="image/jpeg",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    dialog = _FakeLazyPreviewDialog(
        parent=None,
        attachment=attachment,
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        preview_dir=tmp_path,
        initial_start_page=5,
        cached_path=tmp_path / "preview.jpg",
        known_page_count=1,
    )
    try:
        dialog.show()
        app.processEvents()
        assert dialog.use_page_btn.objectName() == "PrimaryButton"
        dialog._on_bootstrap_loaded(
            GmailAttachmentPreviewBootstrapResult(
                attachment=attachment,
                local_path=tmp_path / "preview.jpg",
                page_count=1,
            )
        )
        _wait_for_preview_refresh(dialog)
        assert dialog._current_page == 1
        assert dialog.jump_widget.isHidden()
        assert dialog.use_page_btn.isVisible()
        assert dialog.use_page_btn.text() == "Start from this page"
        dialog.use_page_btn.click()
        assert dialog.selected_start_page == 1
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_review_queue_dialog_keeps_single_select_and_primary_open_action(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    dialog = QtReviewQueueDialog(
        parent=None,
        review_queue=[
            {"page_number": 2, "score": 0.8, "status": "failed", "reasons": ["validator_failed"]},
            {"page_number": 1, "score": 0.6, "status": "done", "reasons": ["spot_check"]},
        ],
        run_dir=tmp_path,
        run_summary_path=tmp_path / "summary.json",
    )
    try:
        assert dialog.table.selectionMode() == dialog.table.SelectionMode.SingleSelection
        assert dialog.open_page_btn.objectName() == "PrimaryButton"
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_attachment_preview_dialog_preserves_reserved_height_after_cache_eviction(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    dialog = _FakeLazyPreviewDialog(
        parent=None,
        attachment=attachment,
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        preview_dir=tmp_path,
        initial_start_page=1,
        cached_path=tmp_path / "preview.pdf",
        known_page_count=3,
    )
    try:
        dialog.show()
        app.processEvents()
        dialog._on_bootstrap_loaded(
            GmailAttachmentPreviewBootstrapResult(
                attachment=attachment,
                local_path=tmp_path / "preview.pdf",
                page_count=3,
                page_sizes=((420.0, 620.0),) * 3,
            )
        )
        app.processEvents()
        first_card = dialog._page_cards[1]
        reserved_height = first_card.preview_label.height()
        assert reserved_height > 0
        _wait_for_preview_refresh(dialog)
        rendered_height = first_card.preview_label.height()
        assert rendered_height == first_card._reserved_height_for_width(first_card._target_width)
        first_card.clear_cached_pixmap()
        app.processEvents()
        assert first_card.preview_label.height() == rendered_height
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_attachment_preview_dialog_coalesces_scaled_preview_refresh(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    dialog = _TrackingScaledPreviewDialog(
        parent=None,
        attachment=attachment,
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        preview_dir=tmp_path,
        initial_start_page=1,
        cached_path=tmp_path / "preview.pdf",
        known_page_count=3,
    )
    try:
        dialog.show()
        app.processEvents()
        dialog._on_bootstrap_loaded(
            GmailAttachmentPreviewBootstrapResult(
                attachment=attachment,
                local_path=tmp_path / "preview.pdf",
                page_count=3,
                page_sizes=((420.0, 620.0),) * 3,
            )
        )
        _wait_for_preview_refresh(dialog)
        baseline = dialog.scaled_refresh_count
        dialog._schedule_scaled_preview_refresh()
        dialog._schedule_scaled_preview_refresh()
        dialog._schedule_scaled_preview_refresh()
        app.processEvents()
        assert dialog.scaled_refresh_count == baseline
        QTest.qWait(90)
        app.processEvents()
        assert dialog.scaled_refresh_count == baseline + 1
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_attachment_preview_dialog_debounces_visible_refresh(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    class _CountingLazyPreviewDialog(_FakeLazyPreviewDialog):
        def __init__(self, *args, **kwargs) -> None:
            self.refresh_calls = 0
            super().__init__(*args, **kwargs)

        def _start_page_worker(self, page_number: int) -> None:
            self.started_pages.append(page_number)

        def _refresh_visible_pages(self) -> None:
            self.refresh_calls += 1
            super()._refresh_visible_pages()

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    dialog = _CountingLazyPreviewDialog(
        parent=None,
        attachment=attachment,
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        preview_dir=tmp_path,
        initial_start_page=2,
        cached_path=tmp_path / "preview.pdf",
        known_page_count=4,
    )
    try:
        dialog.show()
        app.processEvents()
        dialog._on_bootstrap_loaded(
            GmailAttachmentPreviewBootstrapResult(
                attachment=attachment,
                local_path=tmp_path / "preview.pdf",
                page_count=4,
                page_sizes=((420.0, 620.0),) * 4,
            )
        )
        app.processEvents()
        dialog._visible_refresh_timer.stop()
        dialog.refresh_calls = 0
        dialog._schedule_visible_page_refresh()
        dialog._schedule_visible_page_refresh()
        dialog._schedule_visible_page_refresh()
        assert dialog._visible_refresh_timer.isActive() is True
        _wait_for_preview_refresh(dialog)
        assert dialog.refresh_calls == 1
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_batch_review_dialog_transfers_preview_cache_on_accept(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    dialog = QtGmailBatchReviewDialog(
        parent=None,
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        target_lang="FR",
        default_start_page=2,
        output_dir_text="C:/out",
    )
    try:
        preview_dir = dialog._ensure_preview_dir()
        cached_file = preview_dir / "preview.pdf"
        cached_file.write_text("preview", encoding="utf-8")
        dialog._preview_cache[attachment.attachment_id] = cached_file
        dialog._set_row_page_count(0, 4)
        dialog.table.selectRow(0)
        dialog._accept_selection()
        transfer = dialog.take_preview_cache_transfer()
        assert isinstance(transfer, GmailBatchReviewPreviewCacheTransfer)
        assert transfer.cached_paths == {attachment.attachment_id: cached_file}
        assert transfer.cached_page_counts == {attachment.attachment_id: 4}
        dialog.deleteLater()
        assert cached_file.exists()
        transfer.cleanup()
        assert not preview_dir.exists()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_batch_review_dialog_reject_cleans_preview_cache(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    dialog = QtGmailBatchReviewDialog(
        parent=None,
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        target_lang="FR",
        default_start_page=2,
        output_dir_text="C:/out",
    )
    try:
        preview_dir = dialog._ensure_preview_dir()
        cached_file = preview_dir / "preview.pdf"
        cached_file.write_text("preview", encoding="utf-8")
        dialog._preview_cache[attachment.attachment_id] = cached_file
        dialog.reject()
        app.processEvents()
        assert not preview_dir.exists()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_message_load_finished_starts_prepare_after_review_selection() -> None:
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    load_result = GmailMessageLoadResult(
        ok=True,
        classification="ready",
        status_message="ready",
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
    )
    calls: dict[str, object] = {}
    resolved_outdir = str(Path("C:/Users/FA507/Downloads").resolve())
    fake = SimpleNamespace(
        _set_busy=lambda busy, translation=False: calls.__setitem__("set_busy", (busy, translation)),
        _run_started_at=3.0,
        _last_gmail_message_load_result=None,
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        lang_combo=_FakeCombo("AR"),
        outdir_edit=_FakeEdit(""),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _refresh_lang_badge=lambda: calls.__setitem__("badge_refreshed", True),
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _resolve_effective_gmail_output_dir_text=lambda: resolved_outdir,
        _open_gmail_batch_review_dialog=lambda result, *, output_dir_text: calls.__setitem__(
            "dialog_output_dir",
            output_dir_text,
        )
        or GmailBatchReviewResult(
            selections=(GmailAttachmentSelection(candidate=attachment, start_page=2),),
            target_lang="EN",
        ),
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_gmail_batch_prepare=lambda result, selected, *, output_dir_text: calls.__setitem__(
            "prepare",
            (result, selected, output_dir_text),
        ),
    )

    QtMainWindow._on_gmail_message_load_finished(fake, load_result)

    assert fake._run_started_at is None
    assert fake._last_gmail_message_load_result == load_result
    assert fake.status_label.text == "Gmail message ready for review"
    assert fake.header_status_label.text == "Gmail message ready"
    assert fake.lang_combo.currentText() == "EN"
    assert calls["dialog_output_dir"] == resolved_outdir
    assert calls["badge_refreshed"] is True
    assert calls["set_busy"] == (False, False)
    assert "after_cleanup" in calls
    callback = calls["after_cleanup"]
    assert callable(callback)
    callback()
    assert calls["prepare"] == (
        load_result,
        GmailBatchReviewResult(
            selections=(GmailAttachmentSelection(candidate=attachment, start_page=2),),
            target_lang="EN",
        ),
        resolved_outdir,
    )


def test_gmail_message_load_finished_starts_interpretation_prepare_without_touching_target_lang() -> None:
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="notice.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    load_result = GmailMessageLoadResult(
        ok=True,
        classification="ready",
        status_message="ready",
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
    )
    calls: dict[str, object] = {}
    resolved_outdir = str(Path("C:/Users/FA507/Downloads").resolve())
    fake = SimpleNamespace(
        _set_busy=lambda busy, translation=False: calls.__setitem__("set_busy", (busy, translation)),
        _run_started_at=3.0,
        _last_gmail_message_load_result=None,
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        lang_combo=_FakeCombo("AR"),
        outdir_edit=_FakeEdit(""),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _refresh_lang_badge=lambda: calls.__setitem__("badge_refreshed", True),
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _resolve_effective_gmail_output_dir_text=lambda: resolved_outdir,
        _open_gmail_batch_review_dialog=lambda result, *, output_dir_text: GmailBatchReviewResult(
            selections=(GmailAttachmentSelection(candidate=attachment, start_page=1),),
            workflow_kind=GMAIL_INTAKE_WORKFLOW_INTERPRETATION,
        ),
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_gmail_interpretation_prepare=lambda result, selected, *, output_dir_text: calls.__setitem__(
            "prepare",
            (result, selected, output_dir_text),
        ),
    )

    QtMainWindow._on_gmail_message_load_finished(fake, load_result)

    assert fake.lang_combo.currentText() == "AR"
    assert "badge_refreshed" not in calls
    callback = calls["after_cleanup"]
    assert callable(callback)
    callback()
    assert calls["prepare"] == (
        load_result,
        GmailBatchReviewResult(
            selections=(GmailAttachmentSelection(candidate=attachment, start_page=1),),
            workflow_kind=GMAIL_INTAKE_WORKFLOW_INTERPRETATION,
        ),
        resolved_outdir,
    )


def test_gmail_message_load_finished_cancel_keeps_current_target_language() -> None:
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    load_result = GmailMessageLoadResult(
        ok=True,
        classification="ready",
        status_message="ready",
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
    )
    calls: dict[str, object] = {}
    logs: list[str] = []
    fake = SimpleNamespace(
        _set_busy=lambda busy, translation=False: calls.__setitem__("set_busy", (busy, translation)),
        _run_started_at=3.0,
        _last_gmail_message_load_result=None,
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        lang_combo=_FakeCombo("AR"),
        outdir_edit=_FakeEdit(""),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _refresh_lang_badge=lambda: calls.__setitem__("badge_refreshed", True),
        _append_log=logs.append,
        _resolve_effective_gmail_output_dir_text=lambda: str(Path("C:/Users/FA507/Downloads").resolve()),
        _open_gmail_batch_review_dialog=lambda result, *, output_dir_text: None,
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_gmail_batch_prepare=lambda result, selected, *, output_dir_text: calls.__setitem__(
            "prepare",
            (result, selected, output_dir_text),
        ),
    )

    QtMainWindow._on_gmail_message_load_finished(fake, load_result)

    assert fake.lang_combo.currentText() == "AR"
    assert "badge_refreshed" not in calls
    assert fake.status_label.text == "Gmail review canceled"
    assert fake.header_status_label.text == "Gmail review canceled"
    assert any("review canceled" in entry for entry in logs)
    assert "after_cleanup" not in calls


def test_open_gmail_batch_review_dialog_takes_preview_cache_transfer(monkeypatch) -> None:
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    load_result = GmailMessageLoadResult(
        ok=True,
        classification="ready",
        status_message="ready",
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
    )
    captured: dict[str, object] = {}
    expected_result = GmailBatchReviewResult(
        selections=(GmailAttachmentSelection(candidate=attachment, start_page=2),),
        target_lang="EN",
    )
    expected_transfer = GmailBatchReviewPreviewCacheTransfer(
        cached_paths={attachment.attachment_id: Path("C:/tmp/preview.pdf")},
        cached_page_counts={attachment.attachment_id: 5},
    )
    attention_calls: list[object] = []

    class _FakeReviewDialog:
        def __init__(self, **kwargs) -> None:
            captured["init_kwargs"] = kwargs
            self.review_result = expected_result

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def take_preview_cache_transfer(self) -> GmailBatchReviewPreviewCacheTransfer:
            return expected_transfer

        def deleteLater(self) -> None:
            return None

    monkeypatch.setattr(app_window_module, "QtGmailBatchReviewDialog", _FakeReviewDialog)
    monkeypatch.setattr(
        app_window_module,
        "request_window_attention",
        lambda window: attention_calls.append(window)
        or WindowAttentionResult(
            requested=True,
            restored=False,
            focused=True,
            flashed=False,
            reason="foreground_set",
        ),
    )

    fake = SimpleNamespace(
        start_edit=_FakeEdit("3"),
        _defaults={"default_start_page": 1},
        lang_combo=_FakeCombo("FR"),
        _gmail_batch_preview_cache_transfer=None,
        _gmail_batch_review_dialog=None,
    )

    result = QtMainWindow._open_gmail_batch_review_dialog(
        fake,
        load_result,
        output_dir_text="C:/out",
    )

    assert result == expected_result
    assert fake._gmail_batch_preview_cache_transfer is expected_transfer
    assert captured["init_kwargs"]["default_start_page"] == 1
    assert captured["init_kwargs"]["output_dir_text"] == "C:/out"
    assert attention_calls == [fake]


def test_start_gmail_batch_prepare_passes_preview_cache_to_worker(monkeypatch) -> None:
    attachment = GmailAttachmentCandidate(
        attachment_id="att-1",
        filename="court.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        source_message_id="msg-100",
    )
    load_result = GmailMessageLoadResult(
        ok=True,
        classification="ready",
        status_message="ready",
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(attachment,),
        ),
    )
    review_result = GmailBatchReviewResult(
        selections=(GmailAttachmentSelection(candidate=attachment, start_page=2),),
        target_lang="EN",
    )
    captured: dict[str, object] = {}

    class _FakeSignal:
        def connect(self, callback) -> None:
            captured.setdefault("connections", []).append(callback)

    class _FakeThread:
        def __init__(self, _parent) -> None:
            self.started = _FakeSignal()
            self.finished = _FakeSignal()

        def quit(self) -> None:
            captured["thread_quit"] = True

        def start(self) -> None:
            captured["thread_started"] = True

    class _FakeWorker:
        def __init__(self, **kwargs) -> None:
            captured["worker_kwargs"] = kwargs
            self.log = _FakeSignal()
            self.finished = _FakeSignal()
            self.error = _FakeSignal()

        def moveToThread(self, _thread) -> None:
            captured["moved_to_thread"] = True

        def run(self) -> None:
            return None

    monkeypatch.setattr(app_window_module, "QThread", _FakeThread)
    monkeypatch.setattr(app_window_module, "GmailBatchPrepareWorker", _FakeWorker)

    fake = SimpleNamespace(
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _gmail_batch_preview_cache_transfer=GmailBatchReviewPreviewCacheTransfer(
            cached_paths={attachment.attachment_id: Path("C:/tmp/preview.pdf")},
            cached_page_counts={attachment.attachment_id: 5},
        ),
        _append_log=lambda _message: None,
        _on_gmail_batch_prepare_finished=lambda _result: None,
        _on_gmail_batch_prepare_error=lambda _message: None,
        _cleanup_worker=lambda: None,
        _worker_thread=None,
        _worker=None,
        _run_started_at=None,
        _set_busy=lambda busy, translation=False: captured.__setitem__("set_busy", (busy, translation)),
    )

    QtMainWindow._start_gmail_batch_prepare(
        fake,
        load_result,
        review_result,
        output_dir_text="C:/out",
    )

    assert captured["worker_kwargs"]["cached_preview_paths"] == {
        attachment.attachment_id: Path("C:/tmp/preview.pdf")
    }
    assert captured["worker_kwargs"]["cached_preview_page_counts"] == {
        attachment.attachment_id: 5
    }
    assert captured["set_busy"] == (True, False)
    assert captured["thread_started"] is True


def test_resolve_effective_gmail_output_dir_text_falls_back_to_downloads(tmp_path: Path) -> None:
    downloads_dir = tmp_path / "Downloads"
    logs: list[str] = []
    fake = SimpleNamespace(
        outdir_edit=_FakeEdit(str(tmp_path / "missing-out")),
        _defaults=_base_gui_settings(default_outdir=""),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _append_log=logs.append,
        _writable_output_dir_text=QtMainWindow._writable_output_dir_text,
        _default_downloads_dir=lambda: downloads_dir,
    )

    resolved = QtMainWindow._resolve_effective_gmail_output_dir_text(fake)

    assert resolved == str(downloads_dir.resolve())
    assert downloads_dir.exists() is True
    assert fake.outdir_edit.text() == resolved
    assert fake.status_label.text == "Gmail output folder set to Downloads"
    assert fake.header_status_label.text == "Gmail output folder set"
    assert any("fallback applied" in entry for entry in logs)
    assert any(str(downloads_dir.resolve()) in entry for entry in logs)


def test_resolve_effective_gmail_output_dir_text_uses_default_before_downloads(tmp_path: Path) -> None:
    default_outdir = tmp_path / "default-out"
    default_outdir.mkdir()
    downloads_dir = tmp_path / "Downloads"
    logs: list[str] = []
    fake = SimpleNamespace(
        outdir_edit=_FakeEdit(str(tmp_path / "missing-out")),
        _defaults=_base_gui_settings(default_outdir=str(default_outdir)),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _append_log=logs.append,
        _writable_output_dir_text=QtMainWindow._writable_output_dir_text,
        _default_downloads_dir=lambda: downloads_dir,
    )

    resolved = QtMainWindow._resolve_effective_gmail_output_dir_text(fake)

    assert resolved == str(default_outdir.resolve())
    assert fake.outdir_edit.text() == resolved
    assert downloads_dir.exists() is False
    assert logs == []


def test_resolve_effective_gmail_output_dir_text_preserves_valid_current_dir(tmp_path: Path) -> None:
    current_outdir = tmp_path / "current-out"
    current_outdir.mkdir()
    default_outdir = tmp_path / "default-out"
    default_outdir.mkdir()
    fake = SimpleNamespace(
        outdir_edit=_FakeEdit(str(current_outdir)),
        _defaults=_base_gui_settings(default_outdir=str(default_outdir)),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _append_log=lambda _message: None,
        _writable_output_dir_text=QtMainWindow._writable_output_dir_text,
        _default_downloads_dir=lambda: tmp_path / "Downloads",
    )

    resolved = QtMainWindow._resolve_effective_gmail_output_dir_text(fake)

    assert resolved == str(current_outdir.resolve())
    assert fake.outdir_edit.text() == str(current_outdir)


def test_gmail_batch_prepare_finished_starts_first_translation_after_cleanup() -> None:
    temp_dir = Path.cwd()
    session = GmailBatchSession(
        intake_context=InboundMailContext(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
        ),
        message=FetchedGmailMessage(
            message_id="msg-100",
            thread_id="thread-200",
            subject="Court reply needed",
            from_header="Tribunal <court@example.com>",
            account_email="court@example.com",
            attachments=(),
        ),
        gog_path=Path("C:/gog.exe"),
        account_email="court@example.com",
        downloaded_attachments=(
            SimpleNamespace(
                candidate=GmailAttachmentCandidate(
                    attachment_id="att-1",
                    filename="court.pdf",
                    mime_type="application/pdf",
                    size_bytes=2048,
                    source_message_id="msg-100",
                ),
                saved_path=temp_dir / "court.pdf",
            ),
        ),
        download_dir=temp_dir,
    )
    calls: dict[str, object] = {"clear": 0}
    fake = SimpleNamespace(
        _set_busy=lambda busy, translation=False: calls.__setitem__("set_busy", (busy, translation)),
        _run_started_at=5.0,
        _gmail_batch_session=None,
        _clear_gmail_batch_session=lambda: calls.__setitem__("clear", int(calls["clear"]) + 1),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _append_log=lambda message: calls.__setitem__("log", message),
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_next_gmail_batch_translation=lambda: calls.__setitem__("started", True),
    )

    QtMainWindow._on_gmail_batch_prepare_finished(fake, session)

    assert fake._run_started_at is None
    assert fake._gmail_batch_session is session
    assert fake.status_label.text == "Gmail batch queued: 1 attachment(s)"
    assert fake.header_status_label.text == "Gmail batch queued"
    assert calls["set_busy"] == (False, False)
    assert calls["clear"] == 1
    callback = calls["after_cleanup"]
    assert callable(callback)
    callback()
    assert calls["started"] is True


def test_gmail_batch_run_success_schedules_next_item_after_joblog_save(tmp_path: Path) -> None:
    session = _build_gmail_batch_session(tmp_path, count=2)
    output_docx = tmp_path / "translated-1.docx"
    output_docx.write_bytes(b"docx")
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    calls: dict[str, object] = {"set_busy": []}
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-1"),
        _gmail_batch_session=session,
        _gmail_batch_in_progress=True,
        _gmail_batch_current_index=0,
        _set_busy=lambda busy, translation=False: calls["set_busy"].append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _prepare_joblog_seed=lambda summary: setattr(fake, "_last_joblog_seed", object()),
        _open_save_to_joblog_dialog=lambda **kwargs: calls.__setitem__("joblog_kwargs", kwargs) or JobLogSavedResult(
            row_id=7,
            translated_docx_path=output_docx,
            word_count=321,
            case_number="123/26.0",
            case_entity="Tribunal",
            case_city="Beja",
            court_email="court@example.com",
            run_id="run-1",
        ),
        _record_gmail_batch_saved_result=lambda result, *, run_dir: calls.__setitem__(
            "saved_result",
            (result, run_dir),
        )
        or True,
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_next_gmail_batch_translation=lambda: calls.__setitem__("next_started", True),
        _update_live_counters=lambda: calls.__setitem__("live_updated", True),
        _update_controls=lambda: calls.__setitem__("controls_updated", True),
        _has_active_gmail_batch=None,
        _current_gmail_batch_attachment=None,
    )
    fake._has_active_gmail_batch = QtMainWindow._has_active_gmail_batch.__get__(fake, QtMainWindow)
    fake._current_gmail_batch_attachment = QtMainWindow._current_gmail_batch_attachment.__get__(fake, QtMainWindow)

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=True,
            exit_code=0,
            output_docx=output_docx,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=3,
            failed_page=None,
            run_summary_path=None,
        ),
    )

    assert fake._last_output_docx == output_docx.resolve()
    assert fake.final_docx_edit.text() == str(output_docx.resolve())
    assert calls["joblog_kwargs"] == {"allow_honorarios_export": False}
    saved_result, saved_run_dir = calls["saved_result"]
    assert isinstance(saved_result, JobLogSavedResult)
    assert saved_run_dir == run_dir
    assert calls["set_busy"] == [(False, False), (True, False)]
    callback = calls["after_cleanup"]
    assert callable(callback)
    callback()
    assert calls["next_started"] is True


def test_arabic_gmail_batch_run_reviews_before_joblog_save(tmp_path: Path) -> None:
    session = _build_gmail_batch_session(tmp_path, count=2)
    output_docx = tmp_path / "translated-ar.docx"
    output_docx.write_bytes(b"docx")
    run_dir = tmp_path / "run-ar"
    run_dir.mkdir()
    calls: dict[str, object] = {"set_busy": []}
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-ar"),
        _gmail_batch_session=session,
        _gmail_batch_in_progress=True,
        _gmail_batch_current_index=0,
        _last_run_config=SimpleNamespace(target_lang=TargetLang.AR),
        _set_busy=lambda busy, translation=False: calls["set_busy"].append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _prepare_joblog_seed=lambda summary: setattr(fake, "_last_joblog_seed", object()),
        _open_arabic_docx_review_dialog=lambda **kwargs: calls.__setitem__("review_kwargs", kwargs) or True,
        _open_save_to_joblog_dialog=lambda **kwargs: calls.__setitem__("joblog_kwargs", kwargs) or JobLogSavedResult(
            row_id=8,
            translated_docx_path=output_docx,
            word_count=222,
            case_number="123/26.0",
            case_entity="Tribunal",
            case_city="Beja",
            court_email="court@example.com",
            run_id="run-ar",
        ),
        _record_gmail_batch_saved_result=lambda result, *, run_dir: calls.__setitem__(
            "saved_result",
            (result, run_dir),
        )
        or True,
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_next_gmail_batch_translation=lambda: calls.__setitem__("next_started", True),
        _update_live_counters=lambda: None,
        _update_controls=lambda: None,
        _has_active_gmail_batch=None,
        _current_gmail_batch_attachment=None,
    )
    fake._has_active_gmail_batch = QtMainWindow._has_active_gmail_batch.__get__(fake, QtMainWindow)
    fake._current_gmail_batch_attachment = QtMainWindow._current_gmail_batch_attachment.__get__(fake, QtMainWindow)

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=True,
            exit_code=0,
            output_docx=output_docx,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=3,
            failed_page=None,
            run_summary_path=None,
        ),
    )

    assert calls["review_kwargs"] == {
        "output_docx": output_docx.resolve(),
        "is_gmail_batch": True,
        "attachment_label": "attachment-1.pdf",
    }
    assert calls["joblog_kwargs"] == {"allow_honorarios_export": False}
    callback = calls["after_cleanup"]
    assert callable(callback)
    callback()
    assert calls["next_started"] is True


def test_arabic_gmail_batch_run_stops_when_review_is_cancelled(tmp_path: Path) -> None:
    session = _build_gmail_batch_session(tmp_path, count=2)
    output_docx = tmp_path / "translated-ar.docx"
    output_docx.write_bytes(b"docx")
    run_dir = tmp_path / "run-ar"
    run_dir.mkdir()
    calls: dict[str, object] = {}
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-ar"),
        _gmail_batch_session=session,
        _gmail_batch_in_progress=True,
        _gmail_batch_current_index=0,
        _last_run_config=SimpleNamespace(target_lang=TargetLang.AR),
        _set_busy=lambda busy, translation=False: calls.setdefault("set_busy", []).append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _prepare_joblog_seed=lambda summary: setattr(fake, "_last_joblog_seed", object()),
        _open_arabic_docx_review_dialog=lambda **kwargs: calls.__setitem__("review_kwargs", kwargs) or False,
        _open_save_to_joblog_dialog=lambda **kwargs: calls.__setitem__("joblog_kwargs", kwargs) or None,
        _record_gmail_batch_saved_result=lambda result, *, run_dir: True,
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_next_gmail_batch_translation=lambda: calls.__setitem__("next_started", True),
        _stop_gmail_batch=lambda **kwargs: calls.__setitem__("stop_kwargs", kwargs),
        _update_live_counters=lambda: None,
        _update_controls=lambda: None,
        _has_active_gmail_batch=None,
        _current_gmail_batch_attachment=None,
    )
    fake._has_active_gmail_batch = QtMainWindow._has_active_gmail_batch.__get__(fake, QtMainWindow)
    fake._current_gmail_batch_attachment = QtMainWindow._current_gmail_batch_attachment.__get__(fake, QtMainWindow)

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=True,
            exit_code=0,
            output_docx=output_docx,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=3,
            failed_page=None,
            run_summary_path=None,
        ),
    )

    assert calls["review_kwargs"]["attachment_label"] == "attachment-1.pdf"
    assert "joblog_kwargs" not in calls
    assert "Arabic DOCX review" in calls["stop_kwargs"]["information_message"]
    assert "after_cleanup" not in calls


def test_arabic_normal_run_opens_review_before_joblog(tmp_path: Path) -> None:
    output_docx = tmp_path / "translated-ar.docx"
    output_docx.write_bytes(b"docx")
    run_dir = tmp_path / "run-ar"
    run_dir.mkdir()
    calls: dict[str, object] = {}
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-ar"),
        _gmail_batch_session=None,
        _gmail_batch_in_progress=False,
        _gmail_batch_current_index=None,
        _last_run_config=SimpleNamespace(target_lang=TargetLang.AR),
        _set_busy=lambda busy, translation=False: calls.setdefault("set_busy", []).append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _prepare_joblog_seed=lambda summary: setattr(fake, "_last_joblog_seed", object()),
        _open_arabic_docx_review_dialog=lambda **kwargs: calls.__setitem__("review_kwargs", kwargs) or True,
        _show_saved_docx_dialog=lambda title: calls.__setitem__("show_saved_title", title),
        _open_save_to_joblog_dialog=lambda **kwargs: calls.__setitem__("joblog_kwargs", kwargs) or None,
        _update_live_counters=lambda: None,
        _update_controls=lambda: None,
        _has_active_gmail_batch=lambda: False,
    )

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=True,
            exit_code=0,
            output_docx=output_docx,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=3,
            failed_page=None,
            run_summary_path=None,
        ),
    )

    assert calls["review_kwargs"] == {
        "output_docx": output_docx.resolve(),
        "is_gmail_batch": False,
    }
    assert calls["joblog_kwargs"] == {}
    assert "show_saved_title" not in calls


def test_arabic_normal_run_does_not_open_joblog_when_review_is_cancelled(tmp_path: Path) -> None:
    output_docx = tmp_path / "translated-ar.docx"
    output_docx.write_bytes(b"docx")
    run_dir = tmp_path / "run-ar"
    run_dir.mkdir()
    calls: dict[str, object] = {}
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-ar"),
        _gmail_batch_session=None,
        _gmail_batch_in_progress=False,
        _gmail_batch_current_index=None,
        _last_run_config=SimpleNamespace(target_lang=TargetLang.AR),
        _set_busy=lambda busy, translation=False: calls.setdefault("set_busy", []).append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _prepare_joblog_seed=lambda summary: setattr(fake, "_last_joblog_seed", object()),
        _open_arabic_docx_review_dialog=lambda **kwargs: calls.__setitem__("review_kwargs", kwargs) or False,
        _show_saved_docx_dialog=lambda title: calls.__setitem__("show_saved_title", title),
        _open_save_to_joblog_dialog=lambda **kwargs: calls.__setitem__("joblog_kwargs", kwargs) or None,
        _update_live_counters=lambda: None,
        _update_controls=lambda: None,
        _has_active_gmail_batch=lambda: False,
    )

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=True,
            exit_code=0,
            output_docx=output_docx,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=3,
            failed_page=None,
            run_summary_path=None,
        ),
    )

    assert calls["review_kwargs"]["is_gmail_batch"] is False
    assert "joblog_kwargs" not in calls
    assert "show_saved_title" not in calls
    assert "Arabic DOCX review was closed" in calls["logs"][-1]


def test_non_arabic_normal_run_still_uses_saved_docx_prompt(tmp_path: Path) -> None:
    output_docx = tmp_path / "translated-en.docx"
    output_docx.write_bytes(b"docx")
    run_dir = tmp_path / "run-en"
    run_dir.mkdir()
    calls: dict[str, object] = {}
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-en"),
        _gmail_batch_session=None,
        _gmail_batch_in_progress=False,
        _gmail_batch_current_index=None,
        _last_run_config=SimpleNamespace(target_lang=TargetLang.EN),
        _set_busy=lambda busy, translation=False: calls.setdefault("set_busy", []).append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _prepare_joblog_seed=lambda summary: setattr(fake, "_last_joblog_seed", object()),
        _open_arabic_docx_review_dialog=lambda **kwargs: calls.__setitem__("review_kwargs", kwargs) or True,
        _show_saved_docx_dialog=lambda title: calls.__setitem__("show_saved_title", title),
        _open_save_to_joblog_dialog=lambda **kwargs: calls.__setitem__("joblog_kwargs", kwargs) or None,
        _update_live_counters=lambda: None,
        _update_controls=lambda: None,
        _has_active_gmail_batch=lambda: False,
    )

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=True,
            exit_code=0,
            output_docx=output_docx,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=3,
            failed_page=None,
            run_summary_path=None,
        ),
    )

    assert calls["show_saved_title"] == "Translation complete"
    assert calls["joblog_kwargs"] == {}
    assert "review_kwargs" not in calls


def test_arabic_docx_review_dialog_detects_save_and_accepts(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    docx_path = tmp_path / "arabic.docx"
    docx_path.write_bytes(b"first")
    fingerprints = iter([(1, 5), (2, 6), (2, 6)])
    monotonic_values = iter([0.0, 0.2])
    monkeypatch.setattr(
        dialogs_module,
        "open_docx_in_word",
        lambda _path: WordAutomationResult(ok=True, action="open", message="opened"),
    )
    monkeypatch.setattr(
        QtArabicDocxReviewDialog,
        "_read_fingerprint",
        lambda self: next(fingerprints),
    )
    monkeypatch.setattr(dialogs_module.time, "monotonic", lambda: next(monotonic_values))

    dialog = QtArabicDocxReviewDialog(
        parent=None,
        docx_path=docx_path,
        is_gmail_batch=False,
        poll_interval_ms=20,
        quiet_period_ms=60,
        auto_open=False,
    )
    try:
        dialog._poll_for_save()
        dialog._poll_for_save()
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_arabic_docx_review_dialog_align_save_accepts(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    docx_path = tmp_path / "arabic.docx"
    docx_path.write_bytes(b"docx")
    monkeypatch.setattr(
        dialogs_module,
        "open_docx_in_word",
        lambda _path: WordAutomationResult(ok=True, action="open", message="opened"),
    )
    monkeypatch.setattr(
        dialogs_module,
        "align_right_and_save_docx_in_word",
        lambda _path: WordAutomationResult(
            ok=True,
            action="align_right_and_save",
            message="aligned",
        ),
    )

    dialog = QtArabicDocxReviewDialog(
        parent=None,
        docx_path=docx_path,
        is_gmail_batch=False,
        auto_open=False,
    )
    try:
        dialog._align_right_and_save()
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_arabic_docx_review_dialog_keeps_manual_fallback_when_open_fails(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    docx_path = tmp_path / "arabic.docx"
    docx_path.write_bytes(b"docx")
    monkeypatch.setattr(
        dialogs_module,
        "open_docx_in_word",
        lambda _path: WordAutomationResult(ok=False, action="open", message="boom"),
    )
    warnings: dict[str, str] = {}
    monkeypatch.setattr(
        dialogs_module.QMessageBox,
        "warning",
        lambda _self, _title, text: warnings.__setitem__("text", text),
    )

    dialog = QtArabicDocxReviewDialog(
        parent=None,
        docx_path=docx_path,
        is_gmail_batch=False,
        auto_open=False,
    )
    try:
        dialog._open_in_word(initial=False)
        assert dialog.continue_now_btn.isEnabled() is True
        assert dialog.continue_without_changes_btn.isEnabled() is True
        assert warnings["text"].startswith("boom")
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_save_to_joblog_dialog_open_translation_docx_uses_resolved_path(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    output_docx = tmp_path / "translated.docx"
    output_docx.write_bytes(b"docx")
    seed = JobLogSeed(
        completed_at="2026-03-08T20:00:00",
        translation_date="2026-03-08",
        job_type="Translation",
        case_number="21/25.0FBPTM",
        court_email="court@example.com",
        case_entity="Tribunal",
        case_city="Beja",
        service_entity="Tribunal",
        service_city="Beja",
        service_date="2026-03-08",
        lang="AR",
        pages=1,
        word_count=100,
        rate_per_word=0.1,
        expected_total=10.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="AR",
        total_tokens=1000,
        estimated_api_cost=1.0,
        quality_risk_score=0.1,
        profit=9.0,
        pdf_path=tmp_path / "source.pdf",
        output_docx=output_docx,
        partial_docx=None,
    )
    opened: dict[str, Path] = {}
    monkeypatch.setattr(
        dialogs_module,
        "_open_path_in_system",
        lambda _parent, target: opened.__setitem__("path", target),
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        assert dialog.open_translation_btn.isEnabled() is True
        dialog._open_translation_docx()
        assert opened["path"] == output_docx.resolve()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_record_gmail_batch_saved_result_stages_translated_docx_copy(tmp_path: Path) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    original = tmp_path / "translated.docx"
    original.write_bytes(b"translated-bytes")
    report_path = tmp_path / "gmail_batch_session.json"
    session.session_report_path = report_path
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _current_gmail_batch_attachment=lambda: session.downloaded_attachments[0],
        _persist_gmail_batch_session_report=lambda **kwargs: app_window_module.QtMainWindow._persist_gmail_batch_session_report(
            SimpleNamespace(_gmail_batch_session=session, _append_log=lambda *_args, **_kwargs: None),
            **kwargs,
        ),
    )

    consistent = QtMainWindow._record_gmail_batch_saved_result(
        fake,
        JobLogSavedResult(
            row_id=42,
            translated_docx_path=original,
            word_count=314,
            case_number="21/25.0FBPTM",
            case_entity="Tribunal Judicial da Comarca de Beja",
            case_city="Beja",
            court_email="falentejo.judicial@tribunais.org.pt",
            run_id="run-42",
        ),
        run_dir=tmp_path / "21-25_AR_run",
    )

    assert consistent is True
    assert len(session.confirmed_items) == 1
    item = session.confirmed_items[0]
    assert item.translated_docx_path == original.resolve()
    assert item.translated_docx_path.name == original.name
    assert item.translated_docx_path.read_bytes() == b"translated-bytes"
    assert item.staged_translated_docx_path != original.resolve()
    assert item.staged_translated_docx_path.parent == session.download_dir / "_draft_attachments"
    assert item.staged_translated_docx_path.name == original.name
    assert item.staged_translated_docx_path.read_bytes() == b"translated-bytes"
    assert item.run_dir == (tmp_path / "21-25_AR_run").resolve()
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "joblog_saved"
    assert payload["runs"][0]["run_id"] == "run-42"
    assert payload["runs"][0]["run_dir"].endswith("21-25_AR_run")


def test_start_next_gmail_batch_translation_preserves_attachment_override_on_apply_safe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    out_dir = tmp_path / "out"
    out_dir.mkdir()

    window = QtMainWindow()
    try:
        session = _build_gmail_batch_session(tmp_path, count=1)
        session.downloaded_attachments[0].start_page = 4
        session.selected_target_lang = "EN"
        session.session_report_path = tmp_path / "gmail_batch_session.json"
        window._gmail_batch_session = session
        window.lang_combo.setCurrentText("EN")
        window.outdir_edit.setText(str(out_dir))
        window.pdf_edit.clear()
        window.ocr_mode_combo.setCurrentText("auto")
        window.ocr_engine_combo.setCurrentText("local_then_api")
        window.images_combo.setCurrentText("auto")
        window.effort_policy_combo.setCurrentText("adaptive")
        window.workers_spin.setValue(3)
        window.resume_check.setChecked(True)
        window.keep_check.setChecked(False)

        monkeypatch.setattr("legalpdf_translate.qt_gui.app_window.which", lambda _name: None)
        monkeypatch.setattr(
            "legalpdf_translate.qt_gui.app_window.extract_ordered_page_text",
            lambda *_args, **_kwargs: SimpleNamespace(text="", extraction_failed=True),
        )
        monkeypatch.setattr(window, "_show_ocr_heavy_runtime_warning", lambda _config: "apply_safe")

        calls: dict[str, object] = {}
        monkeypatch.setattr(
            app_window_module.QMessageBox,
            "critical",
            lambda _self, _title, text: calls.__setitem__("critical", text),
        )
        monkeypatch.setattr(
            window,
            "_start_translation_run",
            lambda **kwargs: calls.__setitem__("start_kwargs", kwargs),
        )
        monkeypatch.setattr(
            window,
            "_stop_gmail_batch",
            lambda **kwargs: calls.__setitem__("stop_kwargs", kwargs),
        )

        window._start_next_gmail_batch_translation()

        assert "critical" not in calls
        assert "stop_kwargs" not in calls
        start_kwargs = calls["start_kwargs"]
        assert isinstance(start_kwargs, dict)
        config = start_kwargs["config"]
        assert isinstance(config, RunConfig)
        assert config.pdf_path == session.downloaded_attachments[0].saved_path.resolve()
        assert config.output_dir == out_dir.resolve()
        assert config.target_lang == TargetLang.EN
        assert config.start_page == 4
        assert config.effort_policy == EffortPolicy.FIXED_HIGH
        assert config.ocr_mode == OcrMode.ALWAYS
        assert config.ocr_engine == OcrEnginePolicy.API
        assert isinstance(config.gmail_batch_context, dict)
        assert config.gmail_batch_context["source"] == "gmail_intake"
        assert config.gmail_batch_context["session_id"] == session.session_id
        assert config.gmail_batch_context["selected_attachment_filename"] == "attachment-1.pdf"
        assert config.gmail_batch_context["selected_start_page"] == 4
        assert config.gmail_batch_context["gmail_batch_session_report_path"].endswith(
            "gmail_batch_session.json"
        )
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_start_next_gmail_batch_translation_falls_back_to_downloads_for_missing_outdir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    downloads_dir = tmp_path / "Downloads"

    window = QtMainWindow()
    try:
        session = _build_gmail_batch_session(tmp_path, count=1)
        window._gmail_batch_session = session
        window.lang_combo.setCurrentText("EN")
        window.outdir_edit.setText(str(tmp_path / "missing-out"))
        window._defaults["default_outdir"] = ""
        window.pdf_edit.clear()
        window.ocr_mode_combo.setCurrentText("auto")
        window.ocr_engine_combo.setCurrentText("local_then_api")
        window.images_combo.setCurrentText("auto")
        window.effort_policy_combo.setCurrentText("adaptive")
        window.workers_spin.setValue(3)
        window.resume_check.setChecked(True)
        window.keep_check.setChecked(False)

        monkeypatch.setattr(
            app_window_module.QtMainWindow,
            "_default_downloads_dir",
            staticmethod(lambda: downloads_dir),
        )
        monkeypatch.setattr("legalpdf_translate.qt_gui.app_window.which", lambda _name: None)
        monkeypatch.setattr(
            "legalpdf_translate.qt_gui.app_window.extract_ordered_page_text",
            lambda *_args, **_kwargs: SimpleNamespace(text="", extraction_failed=True),
        )
        monkeypatch.setattr(window, "_show_ocr_heavy_runtime_warning", lambda _config: "apply_safe")

        calls: dict[str, object] = {}
        monkeypatch.setattr(
            app_window_module.QMessageBox,
            "critical",
            lambda _self, _title, text: calls.__setitem__("critical", text),
        )
        monkeypatch.setattr(
            window,
            "_start_translation_run",
            lambda **kwargs: calls.__setitem__("start_kwargs", kwargs),
        )
        monkeypatch.setattr(
            window,
            "_stop_gmail_batch",
            lambda **kwargs: calls.__setitem__("stop_kwargs", kwargs),
        )

        window._start_next_gmail_batch_translation()

        assert "critical" not in calls
        assert "stop_kwargs" not in calls
        start_kwargs = calls["start_kwargs"]
        assert isinstance(start_kwargs, dict)
        config = start_kwargs["config"]
        assert isinstance(config, RunConfig)
        assert config.output_dir == downloads_dir.resolve()
        assert config.start_page == 1
        assert window.outdir_edit.text() == str(downloads_dir.resolve())
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_gmail_batch_run_stops_when_joblog_is_cancelled(tmp_path: Path) -> None:
    session = _build_gmail_batch_session(tmp_path, count=2)
    output_docx = tmp_path / "translated-1.docx"
    output_docx.write_bytes(b"docx")
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    calls: dict[str, object] = {}
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-1"),
        _gmail_batch_session=session,
        _gmail_batch_in_progress=True,
        _gmail_batch_current_index=0,
        _set_busy=lambda busy, translation=False: calls.setdefault("set_busy", []).append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _prepare_joblog_seed=lambda summary: setattr(fake, "_last_joblog_seed", object()),
        _open_save_to_joblog_dialog=lambda **kwargs: calls.__setitem__("joblog_kwargs", kwargs) or None,
        _record_gmail_batch_saved_result=lambda result, *, run_dir: True,
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_next_gmail_batch_translation=lambda: calls.__setitem__("next_started", True),
        _stop_gmail_batch=lambda **kwargs: calls.__setitem__("stop_kwargs", kwargs),
        _update_live_counters=lambda: calls.__setitem__("live_updated", True),
        _update_controls=lambda: calls.__setitem__("controls_updated", True),
        _has_active_gmail_batch=None,
        _current_gmail_batch_attachment=None,
    )
    fake._has_active_gmail_batch = QtMainWindow._has_active_gmail_batch.__get__(fake, QtMainWindow)
    fake._current_gmail_batch_attachment = QtMainWindow._current_gmail_batch_attachment.__get__(fake, QtMainWindow)

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=True,
            exit_code=0,
            output_docx=output_docx,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=3,
            failed_page=None,
            run_summary_path=None,
        ),
    )

    assert calls["joblog_kwargs"] == {"allow_honorarios_export": False}
    assert "after_cleanup" not in calls
    assert "Save to Job Log was cancelled" in calls["stop_kwargs"]["information_message"]
    assert "next_started" not in calls


def test_gmail_batch_run_stops_on_consistency_mismatch(tmp_path: Path) -> None:
    session = _build_gmail_batch_session(tmp_path, count=2)
    output_docx = tmp_path / "translated-1.docx"
    output_docx.write_bytes(b"docx")
    run_dir = tmp_path / "run-1"
    run_dir.mkdir()
    calls: dict[str, object] = {}
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-1"),
        _gmail_batch_session=session,
        _gmail_batch_in_progress=True,
        _gmail_batch_current_index=0,
        _set_busy=lambda busy, translation=False: calls.setdefault("set_busy", []).append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _prepare_joblog_seed=lambda summary: setattr(fake, "_last_joblog_seed", object()),
        _open_save_to_joblog_dialog=lambda **kwargs: JobLogSavedResult(
            row_id=7,
            translated_docx_path=output_docx,
            word_count=321,
            case_number="123/26.0",
            case_entity="Tribunal",
            case_city="Beja",
            court_email="court@example.com",
            run_id="run-1",
        ),
        _record_gmail_batch_saved_result=lambda result, *, run_dir: False,
        _run_after_worker_cleanup=lambda callback: calls.__setitem__("after_cleanup", callback),
        _start_next_gmail_batch_translation=lambda: calls.__setitem__("next_started", True),
        _stop_gmail_batch=lambda **kwargs: calls.__setitem__("stop_kwargs", kwargs),
        _update_live_counters=lambda: calls.__setitem__("live_updated", True),
        _update_controls=lambda: calls.__setitem__("controls_updated", True),
        _has_active_gmail_batch=None,
        _current_gmail_batch_attachment=None,
    )
    fake._has_active_gmail_batch = QtMainWindow._has_active_gmail_batch.__get__(fake, QtMainWindow)
    fake._current_gmail_batch_attachment = QtMainWindow._current_gmail_batch_attachment.__get__(fake, QtMainWindow)

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=True,
            exit_code=0,
            output_docx=output_docx,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=3,
            failed_page=None,
            run_summary_path=None,
        ),
    )

    assert "after_cleanup" not in calls
    assert "Split this reply into separate batches" in calls["stop_kwargs"]["warning_message"]
    assert "next_started" not in calls


def test_gmail_batch_failure_stops_and_preserves_confirmed_items(tmp_path: Path, monkeypatch) -> None:
    session = _build_gmail_batch_session(tmp_path, count=2)
    session.confirmed_items.append(
        SimpleNamespace(
            downloaded_attachment=session.downloaded_attachments[0],
            translated_docx_path=tmp_path / "translated-1.docx",
            translated_word_count=200,
            joblog_row_id=5,
            run_id="run-1",
            case_number="123/26.0",
            case_entity="Tribunal",
            case_city="Beja",
            court_email="court@example.com",
        )
    )
    run_dir = tmp_path / "run-2"
    run_dir.mkdir()
    calls: dict[str, object] = {}
    monkeypatch.setattr(app_window_module.QMessageBox, "warning", lambda *_args, **_kwargs: None)
    fake = SimpleNamespace(
        _worker=SimpleNamespace(workflow="workflow-2"),
        _gmail_batch_session=session,
        _gmail_batch_in_progress=True,
        _gmail_batch_current_index=1,
        _set_busy=lambda busy, translation=False: calls.setdefault("set_busy", []).append((busy, translation)),
        _run_started_at=4.0,
        queue_status_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _last_joblog_seed=None,
        _last_review_queue=[],
        _last_summary=None,
        _last_run_dir=None,
        _last_run_report_path=None,
        _last_output_docx=None,
        final_docx_edit=_FakeEdit(""),
        _dashboard_error_count=0,
        _progress_done_pages=0,
        _progress_total_pages=0,
        _can_export_partial=False,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _stop_gmail_batch=lambda **kwargs: calls.__setitem__("stop_kwargs", kwargs),
        _update_live_counters=lambda: calls.__setitem__("live_updated", True),
        _update_controls=lambda: calls.__setitem__("controls_updated", True),
        _has_active_gmail_batch=None,
        _current_gmail_batch_attachment=None,
    )
    fake._has_active_gmail_batch = QtMainWindow._has_active_gmail_batch.__get__(fake, QtMainWindow)
    fake._current_gmail_batch_attachment = QtMainWindow._current_gmail_batch_attachment.__get__(fake, QtMainWindow)

    QtMainWindow._on_finished(
        fake,
        RunSummary(
            success=False,
            exit_code=1,
            output_docx=None,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=1,
            failed_page=2,
            error="cancelled",
            run_summary_path=None,
        ),
    )

    assert len(session.confirmed_items) == 1
    assert "attachment-2.pdf" in calls["stop_kwargs"]["log_message"]


def test_complete_gmail_batch_stage_three_marks_session_ready(tmp_path: Path) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    calls: dict[str, object] = {}
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _gmail_batch_in_progress=True,
        _gmail_batch_current_index=0,
        _set_busy=lambda busy, translation=False: calls.setdefault("set_busy", []).append((busy, translation)),
        _run_started_at=8.0,
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _append_log=lambda message: calls.__setitem__("log", message),
        _consume_advisor_choice=lambda: calls.__setitem__("advisor_consumed", True),
        _update_controls=lambda: calls.__setitem__("controls_updated", True),
        _finalize_completed_gmail_batch=lambda: calls.__setitem__("finalized", True),
    )

    QtMainWindow._complete_gmail_batch_stage_three(fake)

    assert fake._gmail_batch_in_progress is False
    assert fake._gmail_batch_current_index is None
    assert fake.status_label.text == "Gmail batch ready for finalization"
    assert fake.header_status_label.text == "Gmail batch ready"
    assert calls["set_busy"] == [(False, False)]
    assert calls["advisor_consumed"] is True
    assert calls["finalized"] is True


def test_build_gmail_batch_honorarios_draft_aggregates_confirmed_items(tmp_path: Path) -> None:
    session = _build_gmail_batch_session(tmp_path, count=2)
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=tmp_path / "translated-1.docx",
            translated_word_count=125,
        ),
        _build_gmail_batch_confirmed_item(
            session,
            index=1,
            translated_docx_path=tmp_path / "translated-2.docx",
            translated_word_count=375,
        ),
    ]
    fake = SimpleNamespace(_gmail_batch_session=session)

    draft = QtMainWindow._build_gmail_batch_honorarios_draft(fake)

    assert draft.case_number == "123/26.0"
    assert draft.case_entity == "Tribunal"
    assert draft.case_city == "Beja"
    assert draft.word_count == 500


def test_finalize_completed_gmail_batch_skips_when_user_declines(tmp_path: Path, monkeypatch) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=tmp_path / "translated-1.docx",
            translated_word_count=125,
        )
    ]
    calls: dict[str, object] = {}
    monkeypatch.setattr(app_window_module.QMessageBox, "question", lambda *args, **kwargs: 65536)
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _set_gmail_batch_finalization_state=lambda **kwargs: calls.__setitem__("state", kwargs),
    )

    QtMainWindow._finalize_completed_gmail_batch(fake)

    assert calls["state"]["status_text"] == "Gmail batch finalization skipped"
    assert "honorários generation" in calls["state"]["log_message"]


def test_finalize_completed_gmail_batch_stops_when_honorarios_dialog_is_cancelled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    translated = tmp_path / "translated-1.docx"
    translated.write_bytes(b"docx")
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=translated,
            translated_word_count=125,
        )
    ]
    calls: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory) -> None:
            calls["draft"] = draft
            calls["default_directory"] = default_directory
            self.saved_path = None

        def exec(self) -> int:
            return 0

        def deleteLater(self) -> None:
            calls["deleted"] = True

    monkeypatch.setattr(app_window_module.QMessageBox, "question", lambda *args, **kwargs: 16384)
    monkeypatch.setattr(app_window_module, "QtHonorariosExportDialog", _FakeHonorariosDialog)
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _build_gmail_batch_honorarios_draft=lambda: QtMainWindow._build_gmail_batch_honorarios_draft(
            SimpleNamespace(_gmail_batch_session=session)
        ),
        _gmail_batch_honorarios_default_directory=lambda: translated.parent,
        _set_gmail_batch_finalization_state=lambda **kwargs: calls.__setitem__("state", kwargs),
        _offer_gmail_batch_reply_draft=lambda honorarios_pdf, profile: calls.__setitem__(
            "offered",
            (honorarios_pdf, profile.document_name),
        ),
    )

    QtMainWindow._finalize_completed_gmail_batch(fake)

    assert calls["draft"].word_count == 125
    assert calls["state"]["status_text"] == "Gmail batch finalization skipped"
    assert "offered" not in calls
    assert calls["deleted"] is True


def test_finalize_completed_gmail_batch_records_honorarios_paths_in_session_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    session.session_report_path = tmp_path / "gmail_batch_session.json"
    translated = tmp_path / "translated-1.docx"
    translated.write_bytes(b"docx")
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=translated,
            translated_word_count=125,
        )
    ]
    requested_path = tmp_path / "translated-1.docx"
    saved_path = tmp_path / "Requerimento_Honorarios_123-26.docx"
    calls: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory) -> None:
            self.saved_path = saved_path
            self.saved_pdf_path = saved_path.with_suffix(".pdf")
            self.saved_pdf_path.write_bytes(b"%PDF-1.7")
            self.requested_path = requested_path
            self.auto_renamed = True
            self.generated_draft = draft

        def exec(self) -> int:
            return 1

        def deleteLater(self) -> None:
            calls["deleted"] = True

    monkeypatch.setattr(app_window_module.QMessageBox, "question", lambda *args, **kwargs: 16384)
    monkeypatch.setattr(app_window_module, "QtHonorariosExportDialog", _FakeHonorariosDialog)
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _build_gmail_batch_honorarios_draft=lambda: QtMainWindow._build_gmail_batch_honorarios_draft(
            SimpleNamespace(_gmail_batch_session=session)
        ),
        _gmail_batch_honorarios_default_directory=lambda: translated.parent,
        _set_gmail_batch_finalization_state=lambda **kwargs: calls.__setitem__("state", kwargs),
        _offer_gmail_batch_reply_draft=lambda honorarios_pdf, profile: calls.__setitem__(
            "offered",
            (honorarios_pdf, profile.document_name),
        )
        or True,
        _persist_gmail_batch_session_report=lambda **kwargs: app_window_module.QtMainWindow._persist_gmail_batch_session_report(
            SimpleNamespace(_gmail_batch_session=session, _append_log=lambda *_args, **_kwargs: None),
            **kwargs,
        ),
    )

    QtMainWindow._finalize_completed_gmail_batch(fake)

    payload = json.loads(session.session_report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "honorarios_ready"
    assert payload["finalization"]["honorarios_requested"] is True
    assert payload["finalization"]["requested_save_path"].endswith("translated-1.docx")
    assert payload["finalization"]["requested_pdf_save_path"].endswith("translated-1.pdf")
    assert payload["finalization"]["actual_saved_path"].endswith("Requerimento_Honorarios_123-26.docx")
    assert payload["finalization"]["actual_pdf_saved_path"].endswith("Requerimento_Honorarios_123-26.pdf")
    assert payload["finalization"]["auto_renamed"] is True
    assert calls["offered"] == (saved_path.with_suffix(".pdf"), "Adel Belghali")
    assert calls["deleted"] is True


def test_finalize_completed_gmail_batch_blocks_draft_when_honorarios_pdf_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    session.session_report_path = tmp_path / "gmail_batch_session.json"
    translated = tmp_path / "translated-1.docx"
    translated.write_bytes(b"docx")
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=translated,
            translated_word_count=125,
        )
    ]
    saved_path = tmp_path / "Requerimento_Honorarios_123-26.docx"
    calls: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory) -> None:
            self.saved_path = saved_path
            self.requested_path = saved_path
            self.saved_pdf_path = None
            self.pdf_export_error = "Word PDF export failed."
            self.auto_renamed = False
            self.generated_draft = draft

        def exec(self) -> int:
            return 1

        def deleteLater(self) -> None:
            calls["deleted"] = True

    monkeypatch.setattr(app_window_module.QMessageBox, "question", lambda *args, **kwargs: 16384)
    monkeypatch.setattr(app_window_module, "QtHonorariosExportDialog", _FakeHonorariosDialog)
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _build_gmail_batch_honorarios_draft=lambda: QtMainWindow._build_gmail_batch_honorarios_draft(
            SimpleNamespace(_gmail_batch_session=session)
        ),
        _gmail_batch_honorarios_default_directory=lambda: translated.parent,
        _set_gmail_batch_finalization_state=lambda **kwargs: calls.__setitem__("state", kwargs),
        _offer_gmail_batch_reply_draft=lambda *args, **kwargs: calls.__setitem__("offered", True),
        _persist_gmail_batch_session_report=lambda **kwargs: app_window_module.QtMainWindow._persist_gmail_batch_session_report(
            SimpleNamespace(_gmail_batch_session=session, _append_log=lambda *_args, **_kwargs: None),
            **kwargs,
        ),
    )

    QtMainWindow._finalize_completed_gmail_batch(fake)

    payload = json.loads(session.session_report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "draft_unavailable"
    assert payload["halt_reason"] == "honorarios_pdf_generation_failed"
    assert payload["finalization"]["requested_pdf_save_path"].endswith("Requerimento_Honorarios_123-26.pdf")
    assert payload["finalization"]["actual_pdf_saved_path"] == ""
    assert payload["finalization"]["draft_created"] is False
    assert "PDF generation failed" in payload["finalization"]["draft_failure_reason"]
    assert calls["state"]["status_text"] == "Gmail draft unavailable"
    assert "sibling PDF could not be generated" in calls["state"]["log_message"]
    assert "offered" not in calls
    assert calls["deleted"] is True


def test_offer_gmail_batch_reply_draft_builds_threaded_request_and_clears_batch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_batch_session(tmp_path, count=2)
    report_path = tmp_path / "gmail_batch_session.json"
    session.session_report_path = report_path
    translated_one = tmp_path / "staged-translated-1.docx"
    translated_two = tmp_path / "staged-translated-2.docx"
    honorarios = tmp_path / "honorarios.pdf"
    translated_one.write_bytes(b"one")
    translated_two.write_bytes(b"two")
    honorarios.write_bytes(b"%PDF-1.7")
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=translated_one,
            translated_word_count=125,
        ),
        _build_gmail_batch_confirmed_item(
            session,
            index=1,
            translated_docx_path=translated_two,
            translated_word_count=375,
        ),
    ]
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        app_window_module,
        "assess_gmail_draft_prereqs",
        lambda **kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path(r"C:\gog.exe"),
            account_email="adel.belghali@gmail.com",
            accounts=("adel.belghali@gmail.com",),
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "build_gmail_batch_reply_request",
        lambda **kwargs: calls.__setitem__("request_kwargs", kwargs)
        or SimpleNamespace(
            gog_path=kwargs["gog_path"],
            account_email=kwargs["account_email"],
            to_email=kwargs["to_email"],
            subject=kwargs["subject"],
            body="body",
            attachments=tuple(kwargs["translated_docxs"]) + (kwargs["honorarios_pdf"],),
            reply_to_message_id=kwargs["reply_to_message_id"],
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "create_gmail_draft_via_gog",
        lambda request: SimpleNamespace(ok=True, message="ok", stdout="", stderr="", payload={"id": "draft-1"}),
    )
    monkeypatch.setattr(
        app_window_module,
        "validate_translated_docx_artifacts_for_gmail_draft",
        lambda **kwargs: tuple(kwargs["translated_docxs"]),
    )
    monkeypatch.setattr(app_window_module.QMessageBox, "question", lambda *args, **kwargs: 65536)
    opened: list[object] = []
    monkeypatch.setattr(app_window_module.QDesktopServices, "openUrl", opened.append)

    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _defaults={"gmail_gog_path": "", "gmail_account_email": ""},
        _set_gmail_batch_finalization_state=lambda **kwargs: calls.__setitem__("state", kwargs),
        _clear_gmail_batch_session=lambda: calls.__setitem__("cleared", True),
        _persist_gmail_batch_session_report=lambda **kwargs: app_window_module.QtMainWindow._persist_gmail_batch_session_report(
            SimpleNamespace(_gmail_batch_session=session, _append_log=lambda *_args, **_kwargs: None),
            **kwargs,
        ),
    )

    profile = default_primary_profile(email="adel@example.com")
    profile.phone_number = "+351912345678"

    assert QtMainWindow._offer_gmail_batch_reply_draft(fake, honorarios, profile) is True

    assert calls["request_kwargs"]["subject"] == "Court reply needed"
    assert calls["request_kwargs"]["reply_to_message_id"] == "msg-100"
    assert calls["request_kwargs"]["translated_docxs"] == (translated_one, translated_two)
    assert calls["request_kwargs"]["honorarios_pdf"] == honorarios
    assert calls["request_kwargs"]["profile"].phone_number == "+351912345678"
    assert calls["state"]["status_text"] == "Gmail reply draft ready"
    assert calls["cleared"] is True
    assert opened == []
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "draft_ready"
    assert payload["finalization"]["draft_created"] is True
    assert payload["finalization"]["final_attachment_basenames"] == [
        "staged-translated-1.docx",
        "staged-translated-2.docx",
        "honorarios.pdf",
    ]


def test_offer_gmail_interpretation_reply_draft_builds_threaded_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_interpretation_session(tmp_path)
    honorarios = tmp_path / "honorarios.pdf"
    honorarios.write_bytes(b"%PDF-1.7")
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        app_window_module,
        "assess_gmail_draft_prereqs",
        lambda **kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path(r"C:\gog.exe"),
            account_email="adel.belghali@gmail.com",
            accounts=("adel.belghali@gmail.com",),
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "build_interpretation_gmail_reply_request",
        lambda **kwargs: calls.__setitem__("request_kwargs", kwargs)
        or SimpleNamespace(
            gog_path=kwargs["gog_path"],
            account_email=kwargs["account_email"],
            to_email=kwargs["to_email"],
            subject=kwargs["subject"],
            body="body",
            attachments=(kwargs["honorarios_pdf"],),
            reply_to_message_id=kwargs["reply_to_message_id"],
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "create_gmail_draft_via_gog",
        lambda request: SimpleNamespace(ok=True, message="ok", stdout="", stderr="", payload={"id": "draft-1"}),
    )
    monkeypatch.setattr(app_window_module.QMessageBox, "question", lambda *args, **kwargs: 65536)
    opened: list[object] = []
    monkeypatch.setattr(app_window_module.QDesktopServices, "openUrl", opened.append)

    fake = SimpleNamespace(
        _gmail_interpretation_session=session,
        _defaults={"gmail_gog_path": "", "gmail_account_email": ""},
    )

    profile = default_primary_profile(email="adel@example.com")
    profile.phone_number = "+351912345678"

    assert QtMainWindow._offer_gmail_interpretation_reply_draft(
        fake,
        honorarios_pdf=honorarios,
        court_email="beja.judicial@tribunais.org.pt",
        profile=profile,
    ) is True

    assert calls["request_kwargs"]["subject"] == "Court reply needed"
    assert calls["request_kwargs"]["reply_to_message_id"] == "msg-100"
    assert calls["request_kwargs"]["honorarios_pdf"] == honorarios
    assert calls["request_kwargs"]["profile"].phone_number == "+351912345678"
    assert session.draft_created is True
    assert session.final_attachment_basenames == ("honorarios.pdf",)
    assert opened == []


def test_finalize_gmail_interpretation_session_builds_notice_seed_and_offers_reply(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_interpretation_session(tmp_path)
    session.session_report_path = tmp_path / "gmail_interpretation_session.json"
    seed = build_blank_interpretation_seed()
    seed.case_number = "109/26.0PBBJA"
    seed.case_entity = "Juízo Local Criminal de Beja"
    seed.case_city = "Beja"
    seed.service_entity = "Juízo Local Criminal de Beja"
    seed.service_city = "Beja"
    seed.service_date = "2026-03-09"
    seed.court_email = "court@example.pt"
    saved_result = JobLogSavedResult(
        row_id=42,
        word_count=0,
        case_number="109/26.0PBBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        court_email="court@example.pt",
        run_id="",
        translated_docx_path=None,
        payload={
            "case_number": "109/26.0PBBJA",
            "case_entity": "Juízo Local Criminal de Beja",
            "case_city": "Beja",
            "court_email": "court@example.pt",
            "service_date": "2026-03-09",
            "service_entity": "Juízo Local Criminal de Beja",
            "service_city": "Beja",
            "travel_km_outbound": 39.0,
            "travel_km_return": 39.0,
            "use_service_location_in_honorarios": False,
        },
    )
    calls: dict[str, object] = {}
    draft = dialogs_module.build_interpretation_honorarios_draft(
        case_number="109/26.0PBBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        service_date="2026-03-09",
        service_entity="Juízo Local Criminal de Beja",
        service_city="Beja",
        travel_km_outbound=39,
        travel_km_return=39,
        recipient_block=dialogs_module.default_interpretation_recipient_block("Juízo Local Criminal de Beja"),
        profile=default_primary_profile(),
    )

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory, profile_save_callback=None) -> None:
            calls["dialog_draft"] = draft
            self.saved_path = tmp_path / "interpretation_honorarios.docx"
            self.saved_path.write_bytes(b"docx")
            self.saved_pdf_path = tmp_path / "interpretation_honorarios.pdf"
            self.saved_pdf_path.write_bytes(b"%PDF-1.7")
            self.requested_path = self.saved_path
            self.auto_renamed = False
            self.generated_draft = draft

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def deleteLater(self) -> None:
            calls["dialog_deleted"] = True

    monkeypatch.setattr(
        app_window_module,
        "load_joblog_settings",
        lambda: {"vocab_cities": ["Beja"], "vocab_court_emails": ["court@example.pt"]},
    )
    monkeypatch.setattr(
        app_window_module,
        "metadata_config_from_settings",
        lambda _settings: SimpleNamespace(),
    )
    monkeypatch.setattr(
        app_window_module,
        "extract_interpretation_notification_metadata_from_pdf_with_diagnostics",
        lambda pdf_path, **kwargs: calls.__setitem__("source_pdf", pdf_path)
        or SimpleNamespace(
            suggestion=dialogs_module.MetadataSuggestion(case_number="109/26.0PBBJA"),
            diagnostics=dialogs_module.MetadataExtractionDiagnostics(
                page_numbers=(1,),
                embedded_text_pages=(1,),
                embedded_text_found=True,
            ),
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "build_interpretation_seed_from_notification_pdf",
        lambda **kwargs: calls.__setitem__("seed_kwargs", kwargs) or seed,
    )
    monkeypatch.setattr(app_window_module, "QtHonorariosExportDialog", _FakeHonorariosDialog)

    fake = SimpleNamespace(
        _gmail_interpretation_session=session,
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _open_save_to_joblog_dialog_for_seed=lambda seed_value, allow_honorarios_export=False: calls.__setitem__(
            "saved_seed",
            seed_value,
        )
        or saved_result,
        _build_gmail_interpretation_honorarios_draft=lambda result: calls.__setitem__("saved_result", result) or draft,
        _gmail_interpretation_honorarios_default_directory=lambda: tmp_path,
        _offer_gmail_interpretation_reply_draft=lambda **kwargs: calls.__setitem__("offered", kwargs) or True,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _clear_gmail_batch_session=lambda: calls.__setitem__("cleared", True),
        _save_profile_settings_from_dialog=lambda profiles, primary_profile_id: None,
        _persist_gmail_batch_session_report=lambda **kwargs: app_window_module.QtMainWindow._persist_gmail_batch_session_report(
            SimpleNamespace(_gmail_interpretation_session=session, _append_log=lambda *_args, **_kwargs: None),
            **kwargs,
        ),
    )

    QtMainWindow._finalize_gmail_interpretation_session(fake)

    payload = json.loads(session.session_report_path.read_text(encoding="utf-8"))
    assert calls["source_pdf"] == session.downloaded_attachment.saved_path.resolve()
    assert calls["seed_kwargs"]["pdf_path"] == session.downloaded_attachment.saved_path.resolve()
    assert calls["saved_seed"] is seed
    assert calls["saved_result"] is saved_result
    assert calls["offered"]["court_email"] == "court@example.pt"
    assert calls["offered"]["honorarios_pdf"] == (tmp_path / "interpretation_honorarios.pdf").resolve()
    assert payload["status"] == "draft_ready"
    assert payload["metadata_extraction"]["input_kind"] == "pdf"
    assert payload["metadata_extraction"]["embedded_text_found"] is True
    assert payload["pdf_export"]["status"] == "ready"
    assert payload["finalization"]["honorarios_requested"] is True
    assert payload["finalization"]["requested_save_path"].endswith("interpretation_honorarios.docx")
    assert payload["finalization"]["requested_pdf_save_path"].endswith("interpretation_honorarios.pdf")
    assert payload["finalization"]["actual_saved_path"].endswith("interpretation_honorarios.docx")
    assert payload["finalization"]["actual_pdf_saved_path"].endswith("interpretation_honorarios.pdf")
    assert calls["cleared"] is True


def test_finalize_gmail_interpretation_session_blocks_draft_when_honorarios_pdf_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_interpretation_session(tmp_path)
    session.session_report_path = tmp_path / "gmail_interpretation_session.json"
    seed = build_blank_interpretation_seed()
    seed.case_number = "109/26.0PBBJA"
    seed.case_entity = "Juízo Local Criminal de Beja"
    seed.case_city = "Beja"
    seed.service_entity = "Juízo Local Criminal de Beja"
    seed.service_city = "Beja"
    seed.service_date = "2026-03-09"
    seed.court_email = "court@example.pt"
    saved_result = JobLogSavedResult(
        row_id=42,
        word_count=0,
        case_number="109/26.0PBBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        court_email="court@example.pt",
        run_id="",
        translated_docx_path=None,
        payload={
            "case_number": "109/26.0PBBJA",
            "case_entity": "Juízo Local Criminal de Beja",
            "case_city": "Beja",
            "court_email": "court@example.pt",
            "service_date": "2026-03-09",
            "service_entity": "Juízo Local Criminal de Beja",
            "service_city": "Beja",
            "travel_km_outbound": 39.0,
            "travel_km_return": 39.0,
            "use_service_location_in_honorarios": False,
        },
    )
    calls: dict[str, object] = {}
    draft = dialogs_module.build_interpretation_honorarios_draft(
        case_number="109/26.0PBBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        service_date="2026-03-09",
        service_entity="Juízo Local Criminal de Beja",
        service_city="Beja",
        travel_km_outbound=39,
        travel_km_return=39,
        recipient_block=dialogs_module.default_interpretation_recipient_block("Juízo Local Criminal de Beja"),
        profile=default_primary_profile(),
    )

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory, profile_save_callback=None) -> None:
            self.saved_path = tmp_path / "interpretation_honorarios.docx"
            self.saved_path.write_bytes(b"docx")
            self.saved_pdf_path = None
            self.pdf_export_error = "Word PDF export failed."
            self.requested_path = self.saved_path
            self.auto_renamed = False
            self.generated_draft = draft

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def deleteLater(self) -> None:
            calls["dialog_deleted"] = True

    monkeypatch.setattr(
        app_window_module,
        "load_joblog_settings",
        lambda: {"vocab_cities": ["Beja"], "vocab_court_emails": ["court@example.pt"]},
    )
    monkeypatch.setattr(
        app_window_module,
        "metadata_config_from_settings",
        lambda _settings: SimpleNamespace(),
    )
    monkeypatch.setattr(
        app_window_module,
        "extract_interpretation_notification_metadata_from_pdf_with_diagnostics",
        lambda pdf_path, **kwargs: calls.__setitem__("source_pdf", pdf_path)
        or SimpleNamespace(
            suggestion=dialogs_module.MetadataSuggestion(case_number="109/26.0PBBJA"),
            diagnostics=dialogs_module.MetadataExtractionDiagnostics(
                page_numbers=(1,),
                embedded_text_pages=(1,),
                embedded_text_found=True,
            ),
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "build_interpretation_seed_from_notification_pdf",
        lambda **kwargs: calls.__setitem__("seed_kwargs", kwargs) or seed,
    )
    monkeypatch.setattr(app_window_module, "QtHonorariosExportDialog", _FakeHonorariosDialog)
    monkeypatch.setattr(
        app_window_module,
        "show_local_only_honorarios_ready_box",
        lambda *_args, **kwargs: calls.__setitem__("local_only_box", kwargs),
    )

    fake = SimpleNamespace(
        _gmail_interpretation_session=session,
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        _dashboard_snapshot=SimpleNamespace(current_task=""),
        _open_save_to_joblog_dialog_for_seed=lambda seed_value, allow_honorarios_export=False: calls.__setitem__(
            "saved_seed",
            seed_value,
        )
        or saved_result,
        _build_gmail_interpretation_honorarios_draft=lambda result: calls.__setitem__("saved_result", result) or draft,
        _gmail_interpretation_honorarios_default_directory=lambda: tmp_path,
        _offer_gmail_interpretation_reply_draft=lambda **kwargs: calls.__setitem__("offered", kwargs) or True,
        _append_log=lambda message: calls.setdefault("logs", []).append(message),
        _clear_gmail_batch_session=lambda: calls.__setitem__("cleared", True),
        _save_profile_settings_from_dialog=lambda profiles, primary_profile_id: None,
        _persist_gmail_batch_session_report=lambda **kwargs: app_window_module.QtMainWindow._persist_gmail_batch_session_report(
            SimpleNamespace(_gmail_interpretation_session=session, _append_log=lambda *_args, **_kwargs: None),
            **kwargs,
        ),
    )

    QtMainWindow._finalize_gmail_interpretation_session(fake)

    payload = json.loads(session.session_report_path.read_text(encoding="utf-8"))
    assert fake.status_label.text == "Interpretation honorários ready locally"
    assert fake.header_status_label.text == "Gmail draft unavailable"
    assert fake._dashboard_snapshot.current_task == "Interpretation honorários ready locally"
    assert payload["status"] == "draft_unavailable"
    assert payload["halt_reason"] == "honorarios_pdf_generation_failed"
    assert payload["pdf_export"]["status"] == "unavailable"
    assert payload["pdf_export"]["local_only"] is False
    assert payload["finalization"]["requested_pdf_save_path"].endswith("interpretation_honorarios.pdf")
    assert payload["finalization"]["actual_pdf_saved_path"] == ""
    assert "PDF generation failed" in payload["finalization"]["draft_failure_reason"]
    assert any("PDF could not be generated" in message for message in calls["logs"])
    assert "offered" not in calls
    assert calls["local_only_box"]["docx_path"] == (tmp_path / "interpretation_honorarios.docx")
    assert calls["dialog_deleted"] is True
    assert calls["cleared"] is True


def test_open_new_interpretation_honorarios_uses_save_first_flow_and_opens_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seed = build_blank_interpretation_seed()
    saved_result = JobLogSavedResult(
        row_id=42,
        word_count=0,
        case_number="109/26.0PBBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        court_email="court@example.pt",
        run_id="",
        translated_docx_path=None,
        payload={},
    )
    draft = object()
    calls: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory, profile_save_callback=None) -> None:
            calls["dialog_parent"] = parent
            calls["dialog_draft"] = draft
            calls["default_directory"] = default_directory
            calls["profile_save_callback"] = profile_save_callback
            self.saved_path = tmp_path / "interpretation_honorarios.docx"
            self.saved_path.write_bytes(b"docx")
            self.saved_pdf_path = tmp_path / "interpretation_honorarios.pdf"
            self.saved_pdf_path.write_bytes(b"%PDF-1.7")
            self.generated_draft = SimpleNamespace(
                profile=default_primary_profile(),
                include_transport_sentence_in_honorarios=False,
            )

        def exec(self) -> int:
            calls["exec"] = True
            return QDialog.DialogCode.Accepted

        def deleteLater(self) -> None:
            calls["deleted"] = True

    monkeypatch.setattr(app_window_module, "build_blank_interpretation_seed", lambda: seed)
    monkeypatch.setattr(app_window_module, "QtHonorariosExportDialog", _FakeHonorariosDialog)
    monkeypatch.setattr(
        app_window_module.QtMainWindow,
        "_persist_saved_interpretation_honorarios_toggle",
        lambda _self, *, saved_result, include_transport_sentence_in_honorarios: calls.__setitem__(
            "persist_toggle",
            include_transport_sentence_in_honorarios,
        )
        or replace(
            saved_result,
            payload={"include_transport_sentence_in_honorarios": 0},
        ),
    )
    fake = SimpleNamespace()
    fake._open_save_to_joblog_dialog_for_seed = (
        lambda seed_value, allow_honorarios_export=False: calls.__setitem__("seed", seed_value)
        or calls.__setitem__("allow_honorarios_export", allow_honorarios_export)
        or saved_result
    )
    fake._build_saved_interpretation_honorarios_draft = (
        lambda saved_value: calls.__setitem__("saved_result", saved_value) or draft
    )
    fake._manual_interpretation_honorarios_default_directory = lambda: tmp_path
    fake._save_profile_settings_from_dialog = lambda profiles, primary_profile_id: None
    fake._offer_manual_interpretation_gmail_draft = lambda **kwargs: calls.__setitem__("manual_offer", kwargs) or True

    QtMainWindow._open_new_interpretation_honorarios(fake)

    assert calls["seed"] is seed
    assert calls["allow_honorarios_export"] is False
    assert calls["saved_result"] is saved_result
    assert calls["dialog_parent"] is fake
    assert calls["dialog_draft"] is draft
    assert calls["default_directory"] == tmp_path
    assert calls["profile_save_callback"] is fake._save_profile_settings_from_dialog
    assert calls["exec"] is True
    assert calls["persist_toggle"] is False
    assert calls["manual_offer"]["saved_result"] is not saved_result
    assert calls["manual_offer"]["saved_result"].payload["include_transport_sentence_in_honorarios"] == 0
    assert calls["manual_offer"]["honorarios_pdf"] == tmp_path / "interpretation_honorarios.pdf"
    assert calls["deleted"] is True


def test_open_new_interpretation_honorarios_stops_when_save_is_cancelled(
    monkeypatch,
) -> None:
    seed = build_blank_interpretation_seed()
    calls: dict[str, object] = {}

    monkeypatch.setattr(app_window_module, "build_blank_interpretation_seed", lambda: seed)
    monkeypatch.setattr(
        app_window_module,
        "QtHonorariosExportDialog",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("export dialog should not open after cancel")),
    )
    fake = SimpleNamespace()
    fake._open_save_to_joblog_dialog_for_seed = (
        lambda seed_value, allow_honorarios_export=False: calls.__setitem__("seed", seed_value)
        or calls.__setitem__("allow_honorarios_export", allow_honorarios_export)
        or None
    )

    QtMainWindow._open_new_interpretation_honorarios(fake)

    assert calls["seed"] is seed
    assert calls["allow_honorarios_export"] is False
    assert "saved_result" not in calls


def test_open_new_interpretation_honorarios_shows_local_only_handoff_after_export_dialog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    seed = build_blank_interpretation_seed()
    saved_result = JobLogSavedResult(
        row_id=42,
        word_count=0,
        case_number="109/26.0PBBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        court_email="court@example.pt",
        run_id="",
        translated_docx_path=None,
        payload={},
    )
    draft = object()
    calls: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory, profile_save_callback=None) -> None:
            self.saved_path = tmp_path / "interpretation_honorarios.docx"
            self.saved_path.write_bytes(b"docx")
            self.saved_pdf_path = None
            self.pdf_unavailable_explained = True
            self.generated_draft = SimpleNamespace(
                profile=default_primary_profile(),
                include_transport_sentence_in_honorarios=True,
            )

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def deleteLater(self) -> None:
            calls["deleted"] = True

    monkeypatch.setattr(app_window_module, "build_blank_interpretation_seed", lambda: seed)
    monkeypatch.setattr(app_window_module, "QtHonorariosExportDialog", _FakeHonorariosDialog)
    monkeypatch.setattr(
        app_window_module,
        "show_local_only_honorarios_ready_box",
        lambda _parent, *, docx_path, pdf_error="", gmail_blocked: calls.__setitem__(
            "local_only_box",
            {
                "docx_path": docx_path,
                "pdf_error": pdf_error,
                "gmail_blocked": gmail_blocked,
            },
        ),
    )
    monkeypatch.setattr(
        app_window_module.QtMainWindow,
        "_persist_saved_interpretation_honorarios_toggle",
        lambda _self, *, saved_result, include_transport_sentence_in_honorarios: saved_result,
    )
    fake = SimpleNamespace()
    fake._open_save_to_joblog_dialog_for_seed = lambda *_args, **_kwargs: saved_result
    fake._build_saved_interpretation_honorarios_draft = lambda _saved_value: draft
    fake._manual_interpretation_honorarios_default_directory = lambda: tmp_path
    fake._save_profile_settings_from_dialog = lambda profiles, primary_profile_id: None
    fake._offer_manual_interpretation_gmail_draft = lambda **kwargs: calls.__setitem__("manual_offer", kwargs) or True

    QtMainWindow._open_new_interpretation_honorarios(fake)

    assert "manual_offer" not in calls
    assert calls["local_only_box"] == {
        "docx_path": (tmp_path / "interpretation_honorarios.docx").resolve(),
        "pdf_error": "",
        "gmail_blocked": True,
    }
    assert calls["deleted"] is True


def test_offer_manual_interpretation_gmail_draft_builds_non_threaded_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    honorarios_pdf = tmp_path / "interpretation_honorarios.pdf"
    honorarios_pdf.write_bytes(b"%PDF-1.7")
    saved_result = JobLogSavedResult(
        row_id=42,
        word_count=0,
        case_number="109/26.0PBBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        court_email="court@example.pt",
        run_id="",
        translated_docx_path=None,
        payload={"court_email": "court@example.pt", "case_number": "109/26.0PBBJA"},
    )
    calls: dict[str, object] = {}

    monkeypatch.setattr(
        app_window_module,
        "assess_gmail_draft_prereqs",
        lambda **kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path(r"C:\gog.exe"),
            account_email="adel.belghali@gmail.com",
            accounts=("adel.belghali@gmail.com",),
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "build_manual_interpretation_gmail_request",
        lambda **kwargs: calls.__setitem__("request_kwargs", kwargs)
        or SimpleNamespace(
            gog_path=kwargs["gog_path"],
            account_email=kwargs["account_email"],
            to_email=kwargs["to_email"],
            subject="subject",
            body="body",
            attachments=(kwargs["honorarios_pdf"],),
            reply_to_message_id=None,
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "create_gmail_draft_via_gog",
        lambda request: SimpleNamespace(ok=True, message="ok", stdout="", stderr="", payload={"id": "draft-1"}),
    )
    answers = iter([16384, 65536])
    monkeypatch.setattr(app_window_module.QMessageBox, "question", lambda *args, **kwargs: next(answers))
    opened: list[object] = []
    monkeypatch.setattr(app_window_module.QDesktopServices, "openUrl", opened.append)

    fake = SimpleNamespace(
        _defaults={"gmail_gog_path": "", "gmail_account_email": ""},
    )

    profile = default_primary_profile(email="adel@example.com")
    profile.phone_number = "+351912345678"

    assert QtMainWindow._offer_manual_interpretation_gmail_draft(
        fake,
        saved_result=saved_result,
        honorarios_pdf=honorarios_pdf,
        profile=profile,
    ) is True

    assert calls["request_kwargs"]["to_email"] == "court@example.pt"
    assert calls["request_kwargs"]["case_number"] == "109/26.0PBBJA"
    assert calls["request_kwargs"]["honorarios_pdf"] == honorarios_pdf
    assert calls["request_kwargs"]["profile"].phone_number == "+351912345678"
    assert opened == []


def test_offer_manual_interpretation_gmail_draft_blocks_when_pdf_is_missing(
    monkeypatch,
) -> None:
    saved_result = JobLogSavedResult(
        row_id=42,
        word_count=0,
        case_number="109/26.0PBBJA",
        case_entity="Juízo Local Criminal de Beja",
        case_city="Beja",
        court_email="court@example.pt",
        run_id="",
        translated_docx_path=None,
        payload={"court_email": "court@example.pt", "case_number": "109/26.0PBBJA"},
    )
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        app_window_module.QMessageBox,
        "warning",
        lambda *args, **kwargs: calls.__setitem__("warning", args[2] if len(args) > 2 else kwargs.get("text")),
    )
    monkeypatch.setattr(
        app_window_module,
        "build_manual_interpretation_gmail_request",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("request builder should not run without a PDF")),
    )

    fake = SimpleNamespace(
        _defaults={"gmail_gog_path": "", "gmail_account_email": ""},
    )

    assert QtMainWindow._offer_manual_interpretation_gmail_draft(
        fake,
        saved_result=saved_result,
        honorarios_pdf=None,
        profile=default_primary_profile(),
    ) is False
    assert "requires the PDF" in calls["warning"]


def test_offer_gmail_batch_reply_draft_keeps_batch_when_prereqs_are_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    translated = tmp_path / "translated-1.docx"
    translated.write_bytes(b"one")
    honorarios = tmp_path / "honorarios.pdf"
    honorarios.write_bytes(b"%PDF-1.7")
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=translated,
            translated_word_count=125,
        )
    ]
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        app_window_module,
        "assess_gmail_draft_prereqs",
        lambda **kwargs: SimpleNamespace(
            ready=False,
            message="No Gmail account is authenticated in gog.",
            gog_path=Path(r"C:\gog.exe"),
            account_email=None,
            accounts=(),
        ),
    )
    monkeypatch.setattr(
        app_window_module.QMessageBox,
        "warning",
        lambda *args, **kwargs: calls.__setitem__("warning", args[2] if len(args) > 2 else kwargs.get("text")),
    )
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _defaults={"gmail_gog_path": "", "gmail_account_email": ""},
        _set_gmail_batch_finalization_state=lambda **kwargs: calls.__setitem__("state", kwargs),
        _clear_gmail_batch_session=lambda: calls.__setitem__("cleared", True),
    )

    assert QtMainWindow._offer_gmail_batch_reply_draft(fake, honorarios, default_primary_profile()) is False
    assert "No Gmail account is authenticated in gog." in calls["warning"]
    assert calls["state"]["status_text"] == "Gmail draft unavailable"


def test_offer_gmail_batch_reply_draft_rejects_duplicate_attachment_paths(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    translated = tmp_path / "translated-1.docx"
    translated.write_bytes(b"one")
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=translated,
            translated_word_count=125,
        )
    ]
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        app_window_module,
        "assess_gmail_draft_prereqs",
        lambda **kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path(r"C:\gog.exe"),
            account_email="adel.belghali@gmail.com",
            accounts=("adel.belghali@gmail.com",),
        ),
    )
    monkeypatch.setattr(
        app_window_module.QMessageBox,
        "critical",
        lambda *args, **kwargs: calls.__setitem__("critical", args[2] if len(args) > 2 else kwargs.get("text")),
    )
    monkeypatch.setattr(
        app_window_module,
        "validate_translated_docx_artifacts_for_gmail_draft",
        lambda **kwargs: (translated, translated),
    )
    monkeypatch.setattr(
        app_window_module,
        "create_gmail_draft_via_gog",
        lambda request: (_ for _ in ()).throw(AssertionError("draft creation should not run on duplicate attachments")),
    )
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _defaults={"gmail_gog_path": "", "gmail_account_email": ""},
        _set_gmail_batch_finalization_state=lambda **kwargs: calls.__setitem__("state", kwargs),
        _clear_gmail_batch_session=lambda: calls.__setitem__("cleared", True),
    )

    honorarios = tmp_path / "honorarios.pdf"
    honorarios.write_bytes(b"%PDF-1.7")

    assert QtMainWindow._offer_gmail_batch_reply_draft(fake, honorarios, default_primary_profile()) is False

    assert "Duplicate Gmail draft attachment paths" in calls["critical"]
    assert calls["state"]["status_text"] == "Gmail draft failed"
    assert "duplicate" in calls["state"]["log_message"].lower()
    assert "cleared" not in calls
    assert "cleared" not in calls


def test_offer_gmail_batch_reply_draft_blocks_contaminated_translated_attachment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    translated = tmp_path / "staged-translated-1.docx"
    translated.write_bytes(b"one")
    honorarios = tmp_path / "honorarios.pdf"
    honorarios.write_bytes(b"%PDF-1.7")
    session.confirmed_items = [
        _build_gmail_batch_confirmed_item(
            session,
            index=0,
            translated_docx_path=translated,
            translated_word_count=125,
        )
    ]
    calls: dict[str, object] = {}
    monkeypatch.setattr(
        app_window_module,
        "assess_gmail_draft_prereqs",
        lambda **kwargs: SimpleNamespace(
            ready=True,
            message="ready",
            gog_path=Path(r"C:\gog.exe"),
            account_email="adel.belghali@gmail.com",
            accounts=("adel.belghali@gmail.com",),
        ),
    )
    monkeypatch.setattr(
        app_window_module,
        "validate_translated_docx_artifacts_for_gmail_draft",
        lambda **kwargs: (_ for _ in ()).throw(
            ValueError(
                "Translated DOCX is contaminated with honorários content and cannot be attached:\n"
                f"{translated}\n\n"
                "Rerun the translation to create a clean translated DOCX before creating the Gmail draft."
            )
        ),
    )
    monkeypatch.setattr(
        app_window_module.QMessageBox,
        "critical",
        lambda *args, **kwargs: calls.__setitem__("critical", args[2] if len(args) > 2 else kwargs.get("text")),
    )
    monkeypatch.setattr(
        app_window_module,
        "create_gmail_draft_via_gog",
        lambda request: (_ for _ in ()).throw(AssertionError("draft creation should not run on contaminated attachments")),
    )
    fake = SimpleNamespace(
        _gmail_batch_session=session,
        _defaults={"gmail_gog_path": "", "gmail_account_email": ""},
        _set_gmail_batch_finalization_state=lambda **kwargs: calls.__setitem__("state", kwargs),
        _clear_gmail_batch_session=lambda: calls.__setitem__("cleared", True),
    )

    assert QtMainWindow._offer_gmail_batch_reply_draft(fake, honorarios, default_primary_profile()) is False
    assert "contaminated with honorários content" in calls["critical"]
    assert calls["state"]["status_text"] == "Gmail draft failed"
    assert "cleared" not in calls


def test_noncanonical_main_window_title_includes_branch_and_sha() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    identity = RuntimeBuildIdentity(
        worktree_path="C:/repo/noncanonical",
        branch="feat/ocr-runtime-gemini-integration",
        head_sha="1fc24ee",
        labels=("gemini", "gmail"),
        is_canonical=False,
        is_lineage_valid=True,
        canonical_worktree_path="C:/repo/canonical",
        canonical_branch="feat/ai-docs-bootstrap",
        approved_base_branch="feat/ai-docs-bootstrap",
        approved_base_head_floor="4e9d20e",
        canonical_head_floor="4e9d20e",
        reasons=("branch mismatch",),
    )
    window = QtMainWindow(build_identity=identity)
    try:
        assert window.windowTitle() == "LegalPDF Translate [feat/ocr-runtime-gemini-integration@1fc24ee]"
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_workspace_controller_assigns_titles_and_tracks_last_active_window() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    controller = WorkspaceWindowController(app=app, build_identity=None)
    first = controller.create_workspace(show=False, focus=False)
    second = controller.create_workspace(show=False, focus=False)
    try:
        assert "Workspace 1" in first.windowTitle()
        assert "Workspace 2" in second.windowTitle()
        controller.note_window_activated(second)
        assert controller.last_active_window() is second
    finally:
        _close_qt_windows(app, [first, second])
        if owns_app:
            app.quit()


def test_workspace_controller_apply_shared_settings_updates_runtime_theme(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    controller = WorkspaceWindowController(app=app, build_identity=None)
    applied_themes: list[str] = []
    refreshed_payloads: list[dict[str, object]] = []

    class _FakeWindow:
        def reload_shared_settings(self, values: dict[str, object]) -> None:
            refreshed_payloads.append(dict(values))

    fake_window = _FakeWindow()
    controller._windows[id(fake_window)] = fake_window  # type: ignore[assignment]
    monkeypatch.setattr(
        window_controller_module,
        "apply_app_appearance",
        lambda _app, *, theme: applied_themes.append(theme) or "",
    )
    monkeypatch.setattr(controller, "sync_gmail_intake_bridge", lambda **_kwargs: None)
    try:
        controller.apply_shared_settings(
            source_window=None,
            persist=False,
            values={"ui_theme": "dark_simple"},
        )
        assert applied_themes == ["dark_simple"]
        assert refreshed_payloads == [{"ui_theme": "dark_simple"}]
    finally:
        controller._windows.clear()
        if owns_app:
            app.quit()


def test_main_window_reapplies_shell_effect_colors_on_theme_reload() -> None:
    from legalpdf_translate.qt_gui.styles import theme_effect_specs

    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        futuristic = theme_effect_specs("dark_futuristic")
        simple = theme_effect_specs("dark_simple")
        initial_title_effect = window.title_label.graphicsEffect()
        initial_footer_effect = window.footer_card.graphicsEffect()

        assert window.title_label.graphicsEffect() is initial_title_effect
        assert window.footer_card.graphicsEffect() is initial_footer_effect
        assert window.title_label.graphicsEffect().color().getRgb() == futuristic["title_glow"]["color"].getRgb()
        assert window.footer_card.graphicsEffect().color().getRgb() == futuristic["footer_glow"]["color"].getRgb()
        assert int(window.title_label.graphicsEffect().blurRadius()) == int(futuristic["title_glow"]["blur_radius"])

        window.reload_shared_settings({"ui_theme": "dark_futuristic"})
        assert window.title_label.graphicsEffect() is initial_title_effect
        assert window.footer_card.graphicsEffect() is initial_footer_effect

        window.reload_shared_settings({"ui_theme": "dark_simple"})
        assert window._applied_effect_theme == "dark_simple"
        assert window.title_label.graphicsEffect() is initial_title_effect
        assert window.footer_card.graphicsEffect() is initial_footer_effect
        assert window.title_label.graphicsEffect().color().getRgb() == simple["title_glow"]["color"].getRgb()
        assert window.footer_card.graphicsEffect().color().getRgb() == simple["footer_glow"]["color"].getRgb()
        assert int(window.title_label.graphicsEffect().blurRadius()) == int(simple["title_glow"]["blur_radius"])

        window.reload_shared_settings({"ui_theme": "dark_futuristic"})
        assert window._applied_effect_theme == "dark_futuristic"
        assert window.title_label.graphicsEffect() is initial_title_effect
        assert window.footer_card.graphicsEffect() is initial_footer_effect
        assert window.title_label.graphicsEffect().color().getRgb() == futuristic["title_glow"]["color"].getRgb()
        assert window.footer_card.graphicsEffect().color().getRgb() == futuristic["footer_glow"]["color"].getRgb()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_workspace_title_includes_selected_pdf_name(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    controller = WorkspaceWindowController(app=app, build_identity=None)
    window = controller.create_workspace(show=False, focus=False)
    pdf_path = tmp_path / "sample-title.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    try:
        window.pdf_edit.setText(str(pdf_path))
        app.processEvents()
        assert "Workspace 1" in window.windowTitle()
        assert "sample-title.pdf" in window.windowTitle()
    finally:
        _close_qt_windows(app, [window])
        if owns_app:
            app.quit()


def test_new_window_action_stays_available_while_workspace_is_busy() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    controller = WorkspaceWindowController(app=app, build_identity=None)
    window = controller.create_workspace(show=False, focus=False)
    try:
        window._set_busy(True, translation=True)
        assert window.more_btn.isEnabled() is True
        assert window._overflow_menu_actions["new_window"].isEnabled() is True
        window._open_new_window()
        app.processEvents()
        titles = [item.windowTitle() for item in controller.windows()]
        assert len(titles) == 2
        assert any("Workspace 2" in title for title in titles)
    finally:
        _close_qt_windows(app, list(controller.windows()))
        if owns_app:
            app.quit()


def test_workspace_controller_run_target_reservations_block_other_workspaces(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    controller = WorkspaceWindowController(app=app, build_identity=None)
    first = controller.create_workspace(show=False, focus=False)
    second = controller.create_workspace(show=False, focus=False)
    queue_targets = (
        tmp_path / "alpha_EN_run",
        tmp_path / "beta_EN_run",
    )
    try:
        first_reservation = controller.reserve_run_targets(first, queue_targets)
        assert first_reservation.reservation is not None
        assert first_reservation.conflict is None

        blocked = controller.reserve_run_targets(second, (queue_targets[1],))
        assert blocked.conflict is not None
        assert blocked.conflict.owner_workspace_index == 1
        assert blocked.reservation is None

        controller.release_run_targets(first, first_reservation.reservation)
        second_reservation = controller.reserve_run_targets(second, (queue_targets[1],))
        assert second_reservation.conflict is None
        assert second_reservation.reservation is not None
    finally:
        _close_qt_windows(app, [first, second])
        if owns_app:
            app.quit()


def test_settings_dialog_shows_build_identity_summary() -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    identity = RuntimeBuildIdentity(
        worktree_path="C:/repo/noncanonical",
        branch="feat/ocr-runtime-gemini-integration",
        head_sha="1fc24ee",
        labels=("gemini", "gmail"),
        is_canonical=False,
        is_lineage_valid=True,
        canonical_worktree_path="C:/repo/canonical",
        canonical_branch="feat/ai-docs-bootstrap",
        approved_base_branch="feat/ai-docs-bootstrap",
        approved_base_head_floor="4e9d20e",
        canonical_head_floor="4e9d20e",
        reasons=("branch mismatch",),
    )
    settings_dialog = QtSettingsDialog(
        parent=None,
        settings={},
        apply_callback=lambda *_args, **_kwargs: None,
        collect_debug_paths=lambda: [],
        current_pdf_path=None,
        build_identity=identity,
    )
    try:
        text = settings_dialog.build_identity_label.text()
        assert "Status: noncanonical" in text
        assert "Branch: feat/ocr-runtime-gemini-integration" in text
        assert "HEAD SHA: 1fc24ee" in text
        assert "Approved base branch: feat/ai-docs-bootstrap" in text
        assert "Approved base head floor: 4e9d20e" in text
        assert "Lineage valid: yes" in text
    finally:
        settings_dialog.close()
        settings_dialog.deleteLater()
        if owns_app:
            app.quit()


def test_open_profile_dialog_creates_and_reuses_profile_manager(monkeypatch) -> None:
    calls: dict[str, object] = {"created": 0, "raised": 0, "activated": 0, "shown": 0}

    class _FakeSignal:
        def connect(self, _callback) -> None:
            return None

    class _FakeProfileDialog:
        def __init__(self, *, parent, settings, save_callback) -> None:
            calls["created"] = int(calls["created"]) + 1
            calls["parent"] = parent
            calls["settings"] = settings
            calls["save_callback"] = save_callback
            self.destroyed = _FakeSignal()
            self._visible = True

        def isVisible(self) -> bool:
            return self._visible

        def raise_(self) -> None:
            calls["raised"] = int(calls["raised"]) + 1

        def activateWindow(self) -> None:
            calls["activated"] = int(calls["activated"]) + 1

        def setModal(self, _value: bool) -> None:
            return None

        def setAttribute(self, *_args) -> None:
            return None

        def show(self) -> None:
            calls["shown"] = int(calls["shown"]) + 1

    monkeypatch.setattr(app_window_module, "QtProfileManagerDialog", _FakeProfileDialog)

    fake = SimpleNamespace(
        _profile_dialog=None,
        _defaults={"profiles": [], "primary_profile_id": "primary"},
        _save_profile_settings_from_dialog=lambda profiles, primary_profile_id: None,
    )

    QtMainWindow._open_profile_dialog(fake)
    assert calls["created"] == 1
    assert calls["shown"] == 1
    assert calls["raised"] == 1
    assert calls["activated"] == 1
    assert fake._profile_dialog is not None

    existing = fake._profile_dialog
    QtMainWindow._open_profile_dialog(fake)
    assert calls["created"] == 1
    assert fake._profile_dialog is existing
    assert calls["raised"] == 2
    assert calls["activated"] == 2


def test_joblog_combo_boxes_remain_plain_editable_inputs(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    seed = JobLogSeed(
        completed_at=datetime.now().isoformat(timespec="seconds"),
        translation_date="2026-03-06",
        job_type="Translation",
        case_number="",
        court_email="",
        case_entity="",
        case_city="",
        service_entity="",
        service_city="",
        service_date="2026-03-06",
        lang="EN",
        pages=1,
        word_count=1,
        rate_per_word=0.08,
        expected_total=0.08,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="EN",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.08,
        pdf_path=pdf_path,
    )
    joblog_dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        joblog_dialog.show()
        app.processEvents()
        assert isinstance(joblog_dialog.translation_date_edit, GuardedDateEdit)
        assert isinstance(joblog_dialog.service_date_edit, GuardedDateEdit)
        joblog_dialog.translation_date_edit.setCalendarDate(QDate(2026, 3, 11))
        joblog_dialog.service_date_edit.setCalendarDate(QDate(2026, 3, 12))
        assert joblog_dialog.translation_date_edit.text() == "2026-03-11"
        assert joblog_dialog.service_date_edit.text() == "2026-03-12"
        translation_calendar = joblog_dialog.translation_date_edit.calendarWidget()
        service_calendar = joblog_dialog.service_date_edit.calendarWidget()
        assert translation_calendar.firstDayOfWeek() == Qt.DayOfWeek.Monday
        assert service_calendar.firstDayOfWeek() == Qt.DayOfWeek.Monday
        assert translation_calendar.horizontalHeaderFormat() == QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
        assert translation_calendar.minimumWidth() >= 336
        translation_calendar.setCurrentPage(2026, 3)
        app.processEvents()
        assert (
            translation_calendar.dateTextFormat(QDate(2026, 2, 28)).foreground().color().name().lower()
            == CALENDAR_WEEKEND_COLOR.lower()
        )
        assert (
            translation_calendar.dateTextFormat(QDate(2026, 3, 1)).foreground().color().name().lower()
            == CALENDAR_WEEKEND_COLOR.lower()
        )
        assert isinstance(joblog_dialog.lang_edit, NoWheelComboBox)
        assert joblog_dialog.lang_edit.isEditable() is False
        assert [joblog_dialog.lang_edit.itemText(i) for i in range(joblog_dialog.lang_edit.count())] == ["EN", "FR", "AR"]
        assert joblog_dialog.pages_edit.isReadOnly() is True
        assert joblog_dialog.service_group.isVisible() is False
        assert isinstance(joblog_dialog.job_type_combo, NoWheelComboBox)
        assert isinstance(joblog_dialog.case_entity_combo, NoWheelComboBox)
        assert isinstance(joblog_dialog.case_city_combo, NoWheelComboBox)
        assert isinstance(joblog_dialog.service_entity_combo, NoWheelComboBox)
        assert isinstance(joblog_dialog.service_city_combo, NoWheelComboBox)
        assert isinstance(joblog_dialog.court_email_combo, NoWheelComboBox)
        assert joblog_dialog.job_type_combo.isEditable() is False
        assert joblog_dialog.case_entity_combo.isEditable() is False
        assert joblog_dialog.case_city_combo.isEditable() is False
        assert joblog_dialog.service_entity_combo.isEditable() is False
        assert joblog_dialog.service_city_combo.isEditable() is False
        assert joblog_dialog.court_email_combo.isEditable() is True
        assert joblog_dialog.save_btn.objectName() == "PrimaryButton"
        assert joblog_dialog.save_btn.isDefault() is False
        assert joblog_dialog.save_btn.autoDefault() is False
        joblog_dialog.job_type_combo.setCurrentText("Interpretation")
        app.processEvents()
        assert joblog_dialog.service_group.isVisible() is True
        joblog_dialog.job_type_combo.setCurrentText("Translation")
        app.processEvents()
        assert joblog_dialog.service_group.isVisible() is False
        joblog_dialog.case_entity_combo.addItem("Case Entity")
        joblog_dialog.case_entity_combo.setCurrentText("Case Entity")
        joblog_dialog.case_city_combo.addItem("Beja")
        joblog_dialog.case_city_combo.setCurrentText("Beja")
        joblog_dialog.service_entity_combo.addItem("Different Entity")
        joblog_dialog.service_entity_combo.setCurrentText("Different Entity")
        joblog_dialog.service_city_combo.addItem("Serpa")
        joblog_dialog.service_city_combo.setCurrentText("Serpa")
        joblog_dialog.translation_date_edit.setText("2026-03-13")
        joblog_dialog.service_date_edit.setText("2026-03-14")
        payload = joblog_dialog._normalized_payload()
        assert payload["service_entity"] == "Case Entity"
        assert payload["service_city"] == "Beja"
        assert payload["service_date"] == "2026-03-13"
    finally:
        joblog_dialog.close()
        joblog_dialog.deleteLater()
        if owns_app:
            app.quit()


def test_on_finished_failure_dialog_includes_failure_context(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    summary_path = run_dir / "run_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "suspected_cause": "transport_instability",
                "halt_reason": "cancelled_after_request_timeout",
                "failure_context": {
                    "page_number": 1,
                    "error": "runtime_failure",
                    "exception_class": "APITimeoutError",
                    "validator_defect_reason": "Latin letters or digits found outside wrapped tokens.",
                    "ar_violation_kind": "latin_or_digits_outside_wrapped_tokens",
                    "ar_violation_samples": ["الاسم: Adel Belghali"],
                    "request_type": "text_only",
                    "request_timeout_budget_seconds": 480.0,
                    "request_elapsed_before_failure_seconds": 479.8,
                    "cancel_requested_before_failure": True,
                },
            }
        ),
        encoding="utf-8",
    )

    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.QMessageBox.warning",
        lambda _self, title, text: captured.update({"title": title, "text": text}),
    )

    window = QtMainWindow()
    try:
        summary = RunSummary(
            success=False,
            exit_code=1,
            output_docx=None,
            partial_docx=None,
            run_dir=run_dir,
            completed_pages=0,
            failed_page=1,
            error="runtime_failure",
            run_summary_path=summary_path,
        )
        window._on_finished(summary)
        assert captured["title"] == "Translation stopped"
        assert "Suspected cause: transport_instability" in captured["text"]
        assert "Halt reason: cancelled_after_request_timeout" in captured["text"]
        assert "Validator reason: Latin letters or digits found outside wrapped tokens." in captured["text"]
        assert "Arabic violation: latin_or_digits_outside_wrapped_tokens" in captured["text"]
        assert "Arabic samples: الاسم: Adel Belghali" in captured["text"]
        assert "Request type: text_only" in captured["text"]
        assert "Request deadline: 480s" in captured["text"]
        assert "Elapsed before failure: 479.8s" in captured["text"]
        assert "Failure class: APITimeoutError" in captured["text"]
        assert "Cancel requested before failure: yes" in captured["text"]
        log_text = window.log_text.toPlainText()
        assert "Failure context: request_type=text_only deadline=480.0s elapsed=479.800s cancel_requested=yes" in log_text
        assert "Failure classification: suspected_cause=transport_instability halt_reason=cancelled_after_request_timeout exception_class=APITimeoutError" in log_text
        assert (
            "Validator classification: reason=Latin letters or digits found outside wrapped tokens. "
            "ar_violation_kind=latin_or_digits_outside_wrapped_tokens"
        ) in log_text
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_fixed_xhigh_warning_switch_sets_fixed_high(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        window.effort_policy_combo.setCurrentText("fixed_xhigh")
        monkeypatch.setattr(window, "_warn_fixed_xhigh_for_enfr", lambda: "switch")
        config_calls = {"count": 0}

        def _build_config(**kwargs) -> RunConfig:
            config_calls["count"] += 1
            return RunConfig(
                pdf_path=Path("sample.pdf"),
                output_dir=Path("."),
                target_lang=TargetLang.EN,
                effort="high",
                effort_policy=(
                    EffortPolicy.FIXED_XHIGH
                    if config_calls["count"] == 1
                    else EffortPolicy.FIXED_HIGH
                ),
                image_mode=ImageMode.OFF,
                ocr_mode=OcrMode.AUTO,
                ocr_engine=OcrEnginePolicy.LOCAL_THEN_API,
                start_page=1,
                end_page=None,
                max_pages=None,
                workers=1,
                resume=True,
                keep_intermediates=True,
                page_breaks=True,
                context_text=None,
                allow_xhigh_escalation=False,
                diagnostics_admin_mode=True,
                diagnostics_include_sanitized_snippets=False,
                advisor_recommendation_applied=None,
                advisor_recommendation=None,
                budget_cap_usd=None,
                cost_profile_id="default_local",
            )

        monkeypatch.setattr(window, "_build_config", _build_config)
        monkeypatch.setattr(window, "_warn_ocr_api_only_if_needed", lambda config, rebuild_config=None: config)
        monkeypatch.setattr(window, "_save_settings", lambda: None)
        monkeypatch.setattr(window, "_start_translation_run", lambda **_kwargs: True)
        window._start()
        assert window.effort_policy_combo.currentText() == "fixed_high"
        assert config_calls["count"] == 2
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_busy_close_force_close_accepts_and_uses_force_exit(monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    window = QtMainWindow()
    try:
        calls = {"forced": False}
        window._busy = True
        window._running = True
        window._resolve_busy_close_choice = lambda: "force_close"  # type: ignore[method-assign]
        monkeypatch.setattr(window, "_force_exit_app", lambda: calls.__setitem__("forced", True))
        event = QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted() is True
        assert calls == {"forced": True}
    finally:
        window._busy = False
        window._running = False
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_translate_gating_requires_output_folder(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    outdir = tmp_path / "out"
    outdir.mkdir()

    fake = SimpleNamespace(
        _busy=False,
        pdf_edit=_FakeEdit(str(pdf_path)),
        outdir_edit=_FakeEdit(""),
    )

    assert QtMainWindow._can_start(fake) is False
    fake.outdir_edit.setText(str(outdir))
    assert QtMainWindow._can_start(fake) is True


def test_restore_settings_ignores_missing_last_outdir_uses_valid_default(tmp_path: Path) -> None:
    default_outdir = tmp_path / "default-out"
    default_outdir.mkdir()
    fake = _make_restore_settings_fake(
        _base_gui_settings(
            last_outdir=str(tmp_path / "missing-last"),
            default_outdir=str(default_outdir),
        )
    )

    QtMainWindow._restore_settings(fake)

    assert fake.outdir_edit.text() == str(default_outdir.resolve())


def test_restore_settings_leaves_output_folder_blank_when_saved_paths_are_missing(tmp_path: Path) -> None:
    fake = _make_restore_settings_fake(
        _base_gui_settings(
            last_outdir=str(tmp_path / "missing-last"),
            default_outdir=str(tmp_path / "missing-default"),
        )
    )

    QtMainWindow._restore_settings(fake)

    assert fake.outdir_edit.text() == ""


def test_restore_settings_keeps_queue_form_session_local() -> None:
    fake = _make_restore_settings_fake(
        _base_gui_settings(
            queue_manifest_path="C:/tmp/queue.json",
            queue_rerun_failed_only=True,
        )
    )

    QtMainWindow._restore_settings(fake)

    assert fake.queue_manifest_edit.text() == ""
    assert fake.queue_rerun_failed_only_check.isChecked() is False


def test_new_run_resets_runtime_state() -> None:
    calls = {"details": None, "update_controls": False, "advisor_refreshed": False}
    fake = SimpleNamespace(
        _busy=False,
        _review_queue_dialog=None,
        _last_summary=object(),
        _last_run_report_path=object(),
        _last_output_docx=object(),
        _last_run_config=object(),
        _last_joblog_seed=object(),
        _last_review_queue=[{"page_number": 1}],
        _advisor_recommendation={"recommended_ocr_mode": "auto"},
        _advisor_recommendation_applied=True,
        _advisor_override_ocr_mode="auto",
        _advisor_override_image_mode="auto",
        _last_workflow=object(),
        _worker=object(),
        _worker_thread=object(),
        _can_export_partial=True,
        progress=_FakeProgress(),
        page_label=_FakeLabel(),
        status_label=_FakeLabel(),
        header_status_label=_FakeLabel(),
        final_docx_edit=_FakeEdit("filled"),
        log_text=_FakeTextBox(),
        details_btn=_FakeButton(),
        _set_details_visible=lambda visible: calls.__setitem__("details", visible),
        _refresh_advisor_banner=lambda: calls.__setitem__("advisor_refreshed", True),
        _update_controls=lambda: calls.__setitem__("update_controls", True),
        _reset_live_counters=lambda: None,
    )

    QtMainWindow._new_run(fake)

    assert fake._last_summary is None
    assert fake._last_run_report_path is None
    assert fake._last_output_docx is None
    assert fake._last_run_config is None
    assert fake._last_joblog_seed is None
    assert fake._last_review_queue == []
    assert fake._advisor_recommendation is None
    assert fake._advisor_recommendation_applied is None
    assert fake._advisor_override_ocr_mode is None
    assert fake._advisor_override_image_mode is None
    assert fake._last_workflow is None
    assert fake._worker is None
    assert fake._worker_thread is None
    assert fake._can_export_partial is False
    assert fake.progress.value == 0
    assert fake.status_label.text == "Idle"
    assert fake.header_status_label.text == "Idle"
    assert fake.final_docx_edit.text() == ""
    assert fake.log_text.cleared is True
    assert fake.details_btn.checked is False
    assert calls == {"details": False, "update_controls": True, "advisor_refreshed": True}


def test_save_settings_uses_existing_gui_keys(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.save_gui_settings",
        lambda values: captured.update(values),
    )

    fake = SimpleNamespace(
        _defaults={},
        _transient_safe_profile_active=False,
        _transient_safe_profile_backup=None,
        outdir_edit=_FakeEdit("C:/tmp/out"),
        lang_combo=_FakeCombo("FR"),
        effort_combo=_FakeCombo("high"),
        effort_policy_combo=_FakeCombo("adaptive"),
        images_combo=_FakeCombo("auto"),
        ocr_mode_combo=_FakeCombo("auto"),
        ocr_engine_combo=_FakeCombo("local_then_api"),
        start_edit=_FakeEdit("3"),
        end_edit=_FakeEdit("8"),
        max_edit=_FakeEdit(""),
        workers_spin=_FakeSpin(4),
        resume_check=_FakeCheck(True),
        breaks_check=_FakeCheck(False),
        keep_check=_FakeCheck(True),
    )

    QtMainWindow._save_settings(fake)

    expected = {
        "last_outdir",
        "last_lang",
        "effort",
        "effort_policy",
        "image_mode",
        "ocr_mode",
        "ocr_engine",
        "start_page",
        "end_page",
        "max_pages",
        "workers",
        "resume",
        "page_breaks",
        "keep_intermediates",
    }
    assert set(captured.keys()) == expected
    assert fake._defaults["last_lang"] == "FR"
    assert fake._defaults["workers"] == 4


def test_apply_settings_from_dialog_keeps_workspace_draft_fields(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings = _base_gui_settings()
    default_outdir = tmp_path / "defaults"
    default_outdir.mkdir()
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda values: settings.update(values))

    window = QtMainWindow()
    try:
        draft_outdir = tmp_path / "draft-out"
        draft_outdir.mkdir()
        window.lang_combo.setCurrentText("FR")
        window.outdir_edit.setText(str(draft_outdir))
        window.start_edit.setText("9")
        window.apply_settings_from_dialog(
            {
                "default_lang": "AR",
                "default_effort": "xhigh",
                "default_effort_policy": "fixed_high",
                "default_outdir": str(default_outdir),
            },
            False,
        )

        assert window.lang_combo.currentText() == "FR"
        assert window.outdir_edit.text() == str(draft_outdir)
        assert window.start_edit.text() == "9"
        assert window._defaults["default_lang"] == "AR"
        assert window._defaults["default_start_page"] == 1
        assert window._defaults["default_outdir"] == str(default_outdir)
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_closing_window_does_not_persist_workspace_draft_state(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    persisted: list[dict[str, object]] = []
    settings = _base_gui_settings()
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda values: persisted.append(dict(values)))

    window = QtMainWindow()
    try:
        draft_outdir = tmp_path / "draft-close"
        draft_outdir.mkdir()
        window.lang_combo.setCurrentText("FR")
        window.outdir_edit.setText(str(draft_outdir))
        window.start_edit.setText("12")
        window.close()
        assert persisted == []
    finally:
        window.deleteLater()
        if owns_app:
            app.quit()


def test_workspace_draft_state_is_isolated_until_explicit_commit(monkeypatch, tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings_store = _base_gui_settings(
        gmail_intake_bridge_enabled=False,
        last_lang="EN",
        last_outdir="",
        start_page=1,
        workers=3,
    )
    monkeypatch.setattr(window_controller_module, "load_gui_settings", lambda: dict(settings_store))
    monkeypatch.setattr(app_window_module, "load_gui_settings", lambda: dict(settings_store))
    monkeypatch.setattr(app_window_module, "save_gui_settings", lambda values: settings_store.update(values))

    controller = WorkspaceWindowController(app=app, build_identity=None)
    windows: list[QtMainWindow] = []
    try:
        first = controller.create_workspace(show=False, focus=False)
        windows.append(first)
        committed_outdir = tmp_path / "committed-out"
        committed_outdir.mkdir()
        first.lang_combo.setCurrentText("FR")
        first.outdir_edit.setText(str(committed_outdir))
        first.start_edit.setText("7")

        second = controller.create_workspace(show=False, focus=False)
        windows.append(second)
        assert second.lang_combo.currentText() == "EN"
        assert second.outdir_edit.text() == ""
        assert second.start_edit.text() == "1"

        first._save_settings()

        third = controller.create_workspace(show=False, focus=False)
        windows.append(third)
        assert third.lang_combo.currentText() == "FR"
        assert third.outdir_edit.text() == str(committed_outdir.resolve())
        assert third.start_edit.text() == "1"
        assert second.lang_combo.currentText() == "EN"
        assert second.outdir_edit.text() == ""
        assert second.start_edit.text() == "1"
    finally:
        _close_qt_windows(app, windows)
        if owns_app:
            app.quit()


def test_derive_queue_base_inputs_uses_manifest_when_form_is_blank() -> None:
    jobs = [
        {
            "payload": {
                "pdf": "C:/docs/job-a.pdf",
                "outdir": "C:/exports",
                "lang": "FR",
            }
        }
    ]

    pdf_value, outdir_value, lang_value = QtMainWindow._derive_queue_base_inputs(
        jobs=jobs,
        current_pdf="",
        current_outdir="",
        current_lang="",
    )

    assert pdf_value == "C:/docs/job-a.pdf"
    assert outdir_value == "C:/exports"
    assert lang_value == "FR"


def test_on_form_changed_keeps_workspace_state_session_local() -> None:
    calls = {"page_count": False, "controls": False}
    fake = SimpleNamespace(
        _refresh_page_count=lambda: calls.__setitem__("page_count", True),
        _update_controls=lambda: calls.__setitem__("controls", True),
    )

    QtMainWindow._on_form_changed(fake)

    assert calls == {"page_count": True, "controls": True}


def test_schedule_save_settings_starts_timer() -> None:
    timer = _FakeTimer()
    fake = SimpleNamespace(_settings_save_timer=timer)
    QtMainWindow._schedule_save_settings(fake)
    assert timer.started is True


def test_report_button_enabled_during_and_after_run() -> None:
    menu_calls: dict[str, bool] = {}
    report_button = _FakeButton()
    fake = SimpleNamespace(
        _can_start=lambda: True,
        _busy=True,
        _running=True,
        _cancel_pending=False,
        _can_export_partial=False,
        _last_workflow=None,
        _has_rebuildable_pages=lambda: False,
        _last_output_docx=None,
        _last_run_report_path=None,
        _last_joblog_seed=None,
        _last_review_queue=[],
        _resolve_report_run_dir=lambda: Path("C:/tmp/run"),
        translate_btn=_FakeButton(),
        analyze_btn=_FakeButton(),
        cancel_btn=_FakeButton(),
        new_btn=_FakeButton(),
        partial_btn=_FakeButton(),
        rebuild_btn=_FakeButton(),
        open_btn=_FakeButton(),
        report_btn=report_button,
        review_queue_btn=_FakeButton(),
        save_joblog_btn=_FakeButton(),
        open_joblog_btn=_FakeButton(),
        _simple_mode=False,
        _set_menu_enabled=lambda key, enabled: menu_calls.__setitem__(key, enabled),
    )

    QtMainWindow._update_controls(fake)
    assert report_button.enabled is True
    assert fake.review_queue_btn.enabled is False

    fake._busy = False
    fake._running = False
    QtMainWindow._update_controls(fake)
    assert report_button.enabled is True
    assert fake.review_queue_btn.enabled is True

    fake._resolve_report_run_dir = lambda: None
    fake._last_review_queue = []
    QtMainWindow._update_controls(fake)
    assert report_button.enabled is False
    assert fake.review_queue_btn.enabled is False


def test_prepare_joblog_seed_prefills_metrics_from_run_summary(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    run_dir = tmp_path / "run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "page_0001.txt").write_text("hello world", encoding="utf-8")
    run_summary_path = run_dir / "run_summary.json"
    run_summary_path.write_text(
        json.dumps(
            {
                "run_id": "run-20260305-120000",
                "lang": "FR",
                "quality_risk_score": 0.37,
                "totals": {
                    "total_tokens": 8123,
                    "total_cost_estimate_if_available": 4.56,
                },
            }
        ),
        encoding="utf-8",
    )

    def _fake_seed_from_run(**_: object) -> JobLogSeed:
        return JobLogSeed(
            completed_at=datetime.now().isoformat(timespec="seconds"),
            translation_date="2026-03-05",
            job_type="Translation",
            case_number="",
            court_email="",
            case_entity="",
            case_city="",
            service_entity="",
            service_city="",
            service_date="2026-03-05",
            lang="FR",
            pages=1,
            word_count=2,
            rate_per_word=0.08,
            expected_total=0.16,
            amount_paid=0.0,
            api_cost=0.0,
            run_id="",
            target_lang="FR",
            total_tokens=None,
            estimated_api_cost=None,
            quality_risk_score=None,
            profit=0.16,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.load_joblog_settings",
        lambda: {
            "default_rate_per_word": {"FR": 0.08},
            "vocab_cities": [],
            "vocab_court_emails": ["beja.judicial@tribunais.org.pt"],
        },
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.build_seed_from_run",
        _fake_seed_from_run,
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.extract_pdf_header_metadata_priority_pages",
        lambda *_args, **_kwargs: SimpleNamespace(
            case_entity="",
            case_city="",
            case_number="",
            court_email="tribunal@example.pt",
        ),
    )
    fake = SimpleNamespace(
        _last_run_config=SimpleNamespace(
            target_lang=SimpleNamespace(value="FR"),
            pdf_path=pdf_path,
        ),
        _append_log=lambda _msg: None,
        _last_joblog_seed=None,
    )
    summary = SimpleNamespace(
        run_dir=run_dir,
        completed_pages=1,
        run_summary_path=run_summary_path,
        output_docx=None,
        partial_docx=None,
    )

    QtMainWindow._prepare_joblog_seed(fake, summary)

    assert fake._last_joblog_seed is not None
    assert fake._last_joblog_seed.run_id == "run-20260305-120000"
    assert fake._last_joblog_seed.target_lang == "FR"
    assert fake._last_joblog_seed.total_tokens == 8123
    assert fake._last_joblog_seed.estimated_api_cost == 4.56
    assert fake._last_joblog_seed.quality_risk_score == 0.37
    assert fake._last_joblog_seed.api_cost == 4.56
    assert fake._last_joblog_seed.court_email == "tribunal@example.pt"


def test_count_words_from_docx_uses_visible_output_text(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "page_0001.txt").write_text("one two three", encoding="utf-8")
    (pages_dir / "page_0002.txt").write_text("alpha beta", encoding="utf-8")
    output = tmp_path / "out.docx"

    assemble_docx(pages_dir, output, lang=TargetLang.EN, page_breaks=False)

    assert count_words_from_docx(output) == 5


def test_count_words_from_output_artifacts_prefers_final_docx(tmp_path: Path) -> None:
    final_pages = tmp_path / "final_pages"
    final_pages.mkdir()
    (final_pages / "page_0001.txt").write_text("one two three four", encoding="utf-8")
    final_docx = tmp_path / "final.docx"
    assemble_docx(final_pages, final_docx, lang=TargetLang.EN, page_breaks=False)

    partial_pages = tmp_path / "partial_pages"
    partial_pages.mkdir()
    (partial_pages / "page_0001.txt").write_text("fallback text", encoding="utf-8")
    partial_docx = tmp_path / "partial.docx"
    assemble_docx(partial_pages, partial_docx, lang=TargetLang.EN, page_breaks=False)

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "page_0001.txt").write_text("should not be used", encoding="utf-8")

    assert (
        count_words_from_output_artifacts(
            output_docx=final_docx,
            partial_docx=partial_docx,
            pages_dir=pages_dir,
        )
        == 4
    )


def test_count_words_from_output_artifacts_uses_partial_docx_when_final_missing(tmp_path: Path) -> None:
    partial_pages = tmp_path / "partial_pages"
    partial_pages.mkdir()
    (partial_pages / "page_0001.txt").write_text("alpha beta gamma", encoding="utf-8")
    partial_docx = tmp_path / "partial.docx"
    assemble_docx(partial_pages, partial_docx, lang=TargetLang.EN, page_breaks=False)

    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "page_0001.txt").write_text("fallback words ignored", encoding="utf-8")

    assert (
        count_words_from_output_artifacts(
            output_docx=tmp_path / "missing.docx",
            partial_docx=partial_docx,
            pages_dir=pages_dir,
        )
        == 3
    )


def test_count_words_from_output_artifacts_falls_back_to_pages_dir(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "page_0001.txt").write_text("one two", encoding="utf-8")
    (pages_dir / "page_0002.txt").write_text("three", encoding="utf-8")

    assert (
        count_words_from_output_artifacts(
            output_docx=tmp_path / "missing.docx",
            partial_docx=tmp_path / "missing_partial.docx",
            pages_dir=pages_dir,
        )
        == 3
    )


def test_build_seed_from_run_uses_docx_word_count_for_expected_total_and_profit(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    (pages_dir / "page_0001.txt").write_text("one two three four five", encoding="utf-8")
    output = tmp_path / "out.docx"
    assemble_docx(pages_dir, output, lang=TargetLang.EN, page_breaks=False)

    seed = build_seed_from_run(
        pdf_path=tmp_path / "sample.pdf",
        lang="EN",
        output_docx=output,
        partial_docx=None,
        pages_dir=tmp_path / "missing_pages",
        completed_pages=1,
        completed_at="2026-03-06T17:00:00",
        default_rate_per_word=0.1,
        api_cost=0.25,
    )

    assert seed.word_count == 5
    assert seed.expected_total == 0.5
    assert seed.profit == 0.25


def test_prepare_joblog_seed_uses_ranked_court_email_suggestion_when_no_exact_email(tmp_path: Path, monkeypatch) -> None:
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    run_dir = tmp_path / "run"
    pages_dir = run_dir / "pages"
    pages_dir.mkdir(parents=True)
    (pages_dir / "page_0001.txt").write_text("hello world", encoding="utf-8")

    def _fake_seed_from_run(**_: object) -> JobLogSeed:
        return JobLogSeed(
            completed_at=datetime.now().isoformat(timespec="seconds"),
            translation_date="2026-03-05",
            job_type="Translation",
            case_number="",
            court_email="",
            case_entity="",
            case_city="",
            service_entity="",
            service_city="",
            service_date="2026-03-05",
            lang="FR",
            pages=1,
            word_count=2,
            rate_per_word=0.08,
            expected_total=0.16,
            amount_paid=0.0,
            api_cost=0.0,
            run_id="",
            target_lang="FR",
            total_tokens=None,
            estimated_api_cost=None,
            quality_risk_score=None,
            profit=0.16,
            pdf_path=pdf_path,
        )

    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.load_joblog_settings",
        lambda: {
            "default_rate_per_word": {"FR": 0.08},
            "vocab_cities": ["Beja"],
            "vocab_court_emails": [
                "beja.ministeriopublico@tribunais.org.pt",
                "beja.judicial@tribunais.org.pt",
            ],
        },
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.build_seed_from_run",
        _fake_seed_from_run,
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.extract_pdf_header_metadata_priority_pages",
        lambda *_args, **_kwargs: SimpleNamespace(
            case_entity="Ministério Público",
            case_city="Beja",
            case_number="140/22.5JAFAR",
            court_email=None,
        ),
    )
    fake = SimpleNamespace(
        _last_run_config=SimpleNamespace(
            target_lang=SimpleNamespace(value="FR"),
            pdf_path=pdf_path,
        ),
        _append_log=lambda _msg: None,
        _last_joblog_seed=None,
    )
    summary = SimpleNamespace(
        run_dir=run_dir,
        completed_pages=1,
        run_summary_path=None,
        output_docx=None,
        partial_docx=None,
    )

    QtMainWindow._prepare_joblog_seed(fake, summary)

    assert fake._last_joblog_seed is not None
    assert fake._last_joblog_seed.court_email == "beja.ministeriopublico@tribunais.org.pt"


def test_save_to_joblog_dialog_saves_new_run_metric_fields(monkeypatch, tmp_path: Path) -> None:
    captured_payload: dict[str, object] = {}
    saved_settings: dict[str, object] = {}
    callback_state = {"called": False, "accepted": False}

    class _FakeConn:
        def close(self) -> None:
            return

    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.open_job_log",
        lambda _path: _FakeConn(),
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.insert_job_run",
        lambda _conn, payload: captured_payload.update(payload) or 42,
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.save_joblog_settings",
        lambda payload: saved_settings.update(payload),
    )

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Translation",
        case_number="",
        court_email="seed@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="FR",
        pages=3,
        word_count=1000,
        rate_per_word=0.08,
        expected_total=80.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="FR",
        total_tokens=5000,
        estimated_api_cost=2.5,
        quality_risk_score=0.2,
        profit=77.5,
        pdf_path=tmp_path / "sample.pdf",
        output_docx=tmp_path / "translated.docx",
    )

    settings = {
        "vocab_case_entities": [],
        "vocab_service_entities": [],
        "vocab_cities": [],
        "vocab_job_types": [],
        "vocab_court_emails": [],
        "default_rate_per_word": {"FR": 0.08},
        "joblog_visible_columns": [],
        "metadata_ai_enabled": True,
        "metadata_photo_enabled": True,
        "service_equals_case_by_default": True,
        "non_court_service_entities": [],
        "ocr_mode": "auto",
        "ocr_engine": "local_then_api",
        "ocr_api_base_url": "",
        "ocr_api_model": "",
        "ocr_api_key_env_name": "DEEPSEEK_API_KEY",
    }

    def _ensure_in_vocab(key: str, value: str) -> None:
        cleaned = value.strip()
        if not cleaned:
            return
        bucket = list(settings[key])
        lowered = {item.casefold() for item in bucket}
        if cleaned.casefold() in lowered:
            return
        bucket.append(cleaned)
        settings[key] = bucket

    fake = SimpleNamespace(
        _seed=seed,
        _db_path=tmp_path / "joblog.sqlite3",
        _settings=settings,
        _on_saved=lambda: callback_state.__setitem__("called", True),
        _edit_row_id=None,
        _saved=False,
        _saved_result=None,
        accept=lambda: callback_state.__setitem__("accepted", True),
        _parse_float=None,
        _parse_optional_int=None,
        _parse_optional_float=None,
        _collect_raw_values=None,
        _normalized_payload=None,
        _persist_interpretation_distance_for_current_city=None,
        _resolved_seed_docx_path=None,
        _refresh_vocab_widgets=lambda: None,
        translation_date_edit=_FakeEdit("2026-03-05"),
        lang_edit=_FakeEdit("FR"),
        pages_edit=_FakeEdit("3"),
        word_count_edit=_FakeEdit("1000"),
        rate_edit=_FakeEdit("0.08"),
        expected_total_edit=_FakeEdit("80"),
        amount_paid_edit=_FakeEdit("0"),
        api_cost_edit=_FakeEdit("2.50"),
        profit_edit=_FakeEdit("77.50"),
        total_tokens_edit=_FakeEdit("5300"),
        estimated_api_cost_edit=_FakeEdit("2.90"),
        quality_risk_score_edit=_FakeEdit("0.44"),
        service_date_edit=_FakeEdit("2026-03-05"),
        travel_km_outbound_edit=_FakeEdit(""),
        travel_km_return_edit=_FakeEdit(""),
        case_entity_combo=_FakeCombo("Case Entity"),
        case_city_combo=_FakeCombo("Beja"),
        service_entity_combo=_FakeCombo("Case Entity"),
        service_city_combo=_FakeCombo("Beja"),
        service_same_check=_FakeCheck(False),
        use_service_location_check=_FakeCheck(False),
        job_type_combo=_FakeCombo("Translation"),
        case_number_edit=_FakeEdit("ABC-1"),
        court_email_combo=_FakeCombo("court@example.pt"),
        run_id_edit=_FakeEdit("run-override"),
        target_lang_edit=_FakeEdit("AR"),
    )
    fake._parse_float = QtSaveToJobLogDialog._parse_float.__get__(fake, QtSaveToJobLogDialog)
    fake._parse_optional_int = QtSaveToJobLogDialog._parse_optional_int.__get__(fake, QtSaveToJobLogDialog)
    fake._parse_optional_float = QtSaveToJobLogDialog._parse_optional_float.__get__(fake, QtSaveToJobLogDialog)
    fake._collect_raw_values = QtSaveToJobLogDialog._collect_raw_values.__get__(fake, QtSaveToJobLogDialog)
    fake._normalized_payload = QtSaveToJobLogDialog._normalized_payload.__get__(fake, QtSaveToJobLogDialog)
    fake._persist_interpretation_distance_for_current_city = (
        QtSaveToJobLogDialog._persist_interpretation_distance_for_current_city.__get__(fake, QtSaveToJobLogDialog)
    )
    fake._resolved_seed_docx_path = QtSaveToJobLogDialog._resolved_seed_docx_path.__get__(fake, QtSaveToJobLogDialog)

    QtSaveToJobLogDialog._save(fake)

    assert captured_payload["run_id"] == "run-override"
    assert captured_payload["target_lang"] == "AR"
    assert captured_payload["total_tokens"] == 5300
    assert captured_payload["estimated_api_cost"] == 2.9
    assert captured_payload["quality_risk_score"] == 0.44
    assert captured_payload["api_cost"] == 2.5
    assert captured_payload["court_email"] == "court@example.pt"
    assert callback_state == {"called": True, "accepted": True}


def test_save_to_joblog_dialog_interpretation_save_returns_saved_result_without_translated_docx(
    monkeypatch,
    tmp_path: Path,
) -> None:
    captured_payload: dict[str, object] = {}
    callback_state = {"called": False, "accepted": False}

    class _FakeConn:
        def close(self) -> None:
            return

    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.open_job_log",
        lambda _path: _FakeConn(),
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.insert_job_run",
        lambda _conn, payload: captured_payload.update(payload) or 77,
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.save_joblog_settings",
        lambda _payload: None,
    )

    seed = build_blank_interpretation_seed()
    seed.case_number = "109/26.0PBBJA"
    seed.court_email = "court@example.pt"
    seed.case_entity = "Juízo Local Criminal de Beja"
    seed.case_city = "Beja"
    seed.service_entity = "Juízo Local Criminal de Beja"
    seed.service_city = "Beja"
    seed.service_date = "2026-03-09"
    seed.translation_date = "2026-03-09"
    settings = {
        "vocab_case_entities": [],
        "vocab_service_entities": [],
        "vocab_cities": [],
        "vocab_job_types": [],
        "vocab_court_emails": [],
        "default_rate_per_word": {},
        "joblog_visible_columns": [],
        "metadata_ai_enabled": True,
        "metadata_photo_enabled": True,
        "service_equals_case_by_default": True,
        "non_court_service_entities": [],
        "ocr_mode": "auto",
        "ocr_engine": "local_then_api",
        "ocr_api_base_url": "",
        "ocr_api_model": "",
        "ocr_api_key_env_name": "DEEPSEEK_API_KEY",
    }

    fake = SimpleNamespace(
        _seed=seed,
        _db_path=tmp_path / "joblog.sqlite3",
        _settings=settings,
        _on_saved=lambda: callback_state.__setitem__("called", True),
        _edit_row_id=None,
        _saved=False,
        _saved_result=None,
        accept=lambda: callback_state.__setitem__("accepted", True),
        _parse_float=None,
        _parse_optional_int=None,
        _parse_optional_float=None,
        _collect_raw_values=None,
        _normalized_payload=None,
        _persist_interpretation_distance_for_current_city=lambda: None,
        _resolved_seed_docx_path=lambda: None,
        _refresh_vocab_widgets=lambda: None,
        translation_date_edit=_FakeEdit("2026-03-09"),
        lang_edit=_FakeEdit(""),
        pages_edit=_FakeEdit(""),
        word_count_edit=_FakeEdit(""),
        rate_edit=_FakeEdit(""),
        expected_total_edit=_FakeEdit(""),
        amount_paid_edit=_FakeEdit("0"),
        api_cost_edit=_FakeEdit("0"),
        profit_edit=_FakeEdit("0"),
        total_tokens_edit=_FakeEdit(""),
        estimated_api_cost_edit=_FakeEdit(""),
        quality_risk_score_edit=_FakeEdit(""),
        service_date_edit=_FakeEdit("2026-03-09"),
        travel_km_outbound_edit=_FakeEdit("39"),
        travel_km_return_edit=_FakeEdit("39"),
        case_entity_combo=_FakeCombo("Juízo Local Criminal de Beja"),
        case_city_combo=_FakeCombo("Beja"),
        service_entity_combo=_FakeCombo("Juízo Local Criminal de Beja"),
        service_city_combo=_FakeCombo("Beja"),
        service_same_check=_FakeCheck(True),
        use_service_location_check=_FakeCheck(False),
        job_type_combo=_FakeCombo("Interpretation"),
        case_number_edit=_FakeEdit("109/26.0PBBJA"),
        court_email_combo=_FakeCombo("court@example.pt"),
        run_id_edit=_FakeEdit(""),
        target_lang_edit=_FakeEdit(""),
    )
    fake._parse_float = QtSaveToJobLogDialog._parse_float.__get__(fake, QtSaveToJobLogDialog)
    fake._parse_optional_int = QtSaveToJobLogDialog._parse_optional_int.__get__(fake, QtSaveToJobLogDialog)
    fake._parse_optional_float = QtSaveToJobLogDialog._parse_optional_float.__get__(fake, QtSaveToJobLogDialog)
    fake._collect_raw_values = QtSaveToJobLogDialog._collect_raw_values.__get__(fake, QtSaveToJobLogDialog)
    fake._normalized_payload = QtSaveToJobLogDialog._normalized_payload.__get__(fake, QtSaveToJobLogDialog)

    QtSaveToJobLogDialog._save(fake)

    assert captured_payload["job_type"] == "Interpretation"
    assert captured_payload["service_date"] == "2026-03-09"
    assert fake._saved_result is not None
    assert fake._saved_result.row_id == 77
    assert fake._saved_result.translated_docx_path is None
    assert fake._saved_result.payload["service_city"] == "Beja"
    assert callback_state == {"called": True, "accepted": True}


def test_save_to_joblog_dialog_edit_mode_updates_existing_row(monkeypatch, tmp_path: Path) -> None:
    updated: dict[str, object] = {}
    callback_state = {"called": False, "accepted": False}

    class _FakeConn:
        def close(self) -> None:
            return

    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.open_job_log",
        lambda _path: _FakeConn(),
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.update_job_run",
        lambda _conn, *, row_id, values: updated.update({"row_id": row_id, **values}),
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.dialogs.insert_job_run",
        lambda _conn, _payload: (_ for _ in ()).throw(AssertionError("insert should not be used in edit mode")),
    )
    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.save_joblog_settings", lambda _payload: None)

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Translation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="FR",
        pages=3,
        word_count=1000,
        rate_per_word=0.08,
        expected_total=80.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="FR",
        total_tokens=5000,
        estimated_api_cost=2.5,
        quality_risk_score=0.2,
        profit=77.5,
        pdf_path=None,
        output_docx=tmp_path / "translated.docx",
    )

    settings = {
        "vocab_case_entities": [],
        "vocab_service_entities": [],
        "vocab_cities": [],
        "vocab_job_types": [],
        "vocab_court_emails": [],
        "default_rate_per_word": {"FR": 0.08},
        "joblog_visible_columns": [],
        "metadata_ai_enabled": True,
        "metadata_photo_enabled": True,
        "service_equals_case_by_default": True,
        "non_court_service_entities": [],
        "ocr_mode": "auto",
        "ocr_engine": "local_then_api",
        "ocr_api_base_url": "",
        "ocr_api_model": "",
        "ocr_api_key_env_name": "DEEPSEEK_API_KEY",
    }

    fake = SimpleNamespace(
        _seed=seed,
        _db_path=tmp_path / "joblog.sqlite3",
        _settings=settings,
        _on_saved=lambda: callback_state.__setitem__("called", True),
        _edit_row_id=77,
        _saved=False,
        _saved_result=None,
        accept=lambda: callback_state.__setitem__("accepted", True),
        _parse_float=None,
        _parse_optional_int=None,
        _parse_optional_float=None,
        _collect_raw_values=None,
        _normalized_payload=None,
        _persist_interpretation_distance_for_current_city=None,
        _resolved_seed_docx_path=None,
        _refresh_vocab_widgets=lambda: None,
        translation_date_edit=_FakeEdit("2026-03-06"),
        lang_edit=_FakeEdit("AR"),
        pages_edit=_FakeEdit("7"),
        word_count_edit=_FakeEdit("1666"),
        rate_edit=_FakeEdit("0.09"),
        expected_total_edit=_FakeEdit("149.94"),
        amount_paid_edit=_FakeEdit("100"),
        api_cost_edit=_FakeEdit("2.50"),
        profit_edit=_FakeEdit("97.50"),
        total_tokens_edit=_FakeEdit("5300"),
        estimated_api_cost_edit=_FakeEdit("2.90"),
        quality_risk_score_edit=_FakeEdit("0.44"),
        service_date_edit=_FakeEdit("2026-03-06"),
        travel_km_outbound_edit=_FakeEdit(""),
        travel_km_return_edit=_FakeEdit(""),
        case_entity_combo=_FakeCombo("Case Entity"),
        case_city_combo=_FakeCombo("Beja"),
        service_entity_combo=_FakeCombo("Case Entity"),
        service_city_combo=_FakeCombo("Beja"),
        service_same_check=_FakeCheck(False),
        use_service_location_check=_FakeCheck(False),
        job_type_combo=_FakeCombo("Translation"),
        case_number_edit=_FakeEdit("XYZ-2"),
        court_email_combo=_FakeCombo("history@example.pt"),
        run_id_edit=_FakeEdit("run-edited"),
        target_lang_edit=_FakeEdit("AR"),
    )
    fake._parse_float = QtSaveToJobLogDialog._parse_float.__get__(fake, QtSaveToJobLogDialog)
    fake._parse_optional_int = QtSaveToJobLogDialog._parse_optional_int.__get__(fake, QtSaveToJobLogDialog)
    fake._parse_optional_float = QtSaveToJobLogDialog._parse_optional_float.__get__(fake, QtSaveToJobLogDialog)
    fake._collect_raw_values = QtSaveToJobLogDialog._collect_raw_values.__get__(fake, QtSaveToJobLogDialog)
    fake._normalized_payload = QtSaveToJobLogDialog._normalized_payload.__get__(fake, QtSaveToJobLogDialog)
    fake._persist_interpretation_distance_for_current_city = (
        QtSaveToJobLogDialog._persist_interpretation_distance_for_current_city.__get__(fake, QtSaveToJobLogDialog)
    )
    fake._resolved_seed_docx_path = QtSaveToJobLogDialog._resolved_seed_docx_path.__get__(fake, QtSaveToJobLogDialog)

    QtSaveToJobLogDialog._save(fake)

    assert updated["row_id"] == 77
    assert updated["translation_date"] == "2026-03-06"
    assert updated["lang"] == "AR"
    assert updated["pages"] == 7
    assert updated["word_count"] == 1666
    assert updated["case_number"] == "XYZ-2"
    assert updated["run_id"] == "run-edited"
    assert callback_state == {"called": True, "accepted": True}
    assert fake._saved_result is not None
    assert fake._saved_result.row_id == 77


def test_edit_joblog_dialog_keeps_header_autofill_available_without_pdf_path(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    translated = tmp_path / "translated.docx"
    translated.write_bytes(b"docx")
    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="FR",
        pages=3,
        word_count=1000,
        rate_per_word=0.08,
        expected_total=80.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="FR",
        total_tokens=5000,
        estimated_api_cost=2.5,
        quality_risk_score=0.2,
        profit=77.5,
        pdf_path=None,
        output_docx=translated,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed, edit_row_id=5)
    try:
        assert dialog.windowTitle() == "Edit Job Log Entry"
        assert dialog.autofill_header_btn.isEnabled() is True
        assert dialog.autofill_photo_btn.isEnabled() is True
        assert dialog.open_translation_btn.isEnabled() is True
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_translation_mode_disables_header_autofill_without_pdf_path(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Translation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="FR",
        pages=3,
        word_count=1000,
        rate_per_word=0.08,
        expected_total=80.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="FR",
        total_tokens=5000,
        estimated_api_cost=2.5,
        quality_risk_score=0.2,
        profit=77.5,
        pdf_path=None,
        output_docx=tmp_path / "translated.docx",
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed, edit_row_id=5)
    try:
        assert dialog.autofill_header_btn.text() == "Autofill from PDF header"
        assert dialog.autofill_header_btn.isEnabled() is False
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_mode_hides_translation_only_fields(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="FR",
        pages=3,
        word_count=1000,
        rate_per_word=0.08,
        expected_total=80.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="FR",
        total_tokens=5000,
        estimated_api_cost=2.5,
        quality_risk_score=0.2,
        profit=77.5,
        pdf_path=None,
        output_docx=tmp_path / "translated.docx",
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed, edit_row_id=5)
    try:
        dialog.show()
        app.processEvents()
        assert isinstance(dialog.translation_date_edit, GuardedDateEdit)
        assert dialog.primary_date_label.text() == "Service date"
        dialog.translation_date_edit.setCalendarDate(QDate(2026, 3, 8))
        assert dialog.translation_date_edit.text() == "2026-03-08"
        assert dialog.lang_edit.isVisible() is False
        assert dialog.pages_edit.isVisible() is False
        assert dialog.word_count_edit.isVisible() is False
        assert dialog.service_date_edit.isVisible() is False
        assert dialog.metrics_section.isVisible() is False
        assert dialog.finance_section.isVisible() is False
        assert dialog.photo_translation_check.isVisible() is False
        assert dialog.photo_hint.text() == "Photo autofill ready."
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_save_to_joblog_dialog_return_key_saves_without_default_button(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Translation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="FR",
        pages=3,
        word_count=1000,
        rate_per_word=0.08,
        expected_total=80.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="FR",
        total_tokens=5000,
        estimated_api_cost=2.5,
        quality_risk_score=0.2,
        profit=77.5,
        pdf_path=None,
        output_docx=tmp_path / "translated.docx",
    )
    captured: dict[str, object] = {}
    def _fake_insert_job_run(_conn, payload):
        captured["payload"] = payload
        return 1

    monkeypatch.setattr(dialogs_module, "insert_job_run", _fake_insert_job_run)
    monkeypatch.setattr(dialogs_module, "_save_joblog_settings_bundle", lambda *args, **kwargs: None)

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        accepted = {"count": 0}
        dialog.accepted.connect(lambda accepted=accepted: accepted.__setitem__("count", accepted["count"] + 1))
        _close_qt_transients(app, keep=(dialog,))
        _activate_dialog_and_focus(app, dialog, dialog.case_number_edit)
        QTest.keyClick(dialog.case_number_edit, Qt.Key.Key_Return)
        _drain_qt_events(app, cycles=4, wait_ms=5)
        assert "payload" in captured
        assert accepted["count"] == 1
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert dialog.save_btn.isDefault() is False
    finally:
        dialog.close()
        dialog.deleteLater()
        _close_qt_transients(app)
        if owns_app:
            app.quit()


def test_save_to_joblog_dialog_return_key_save_shortcut_is_stable_across_repeated_runs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    def _make_seed(index: int) -> JobLogSeed:
        return JobLogSeed(
            completed_at="2026-03-05T10:00:00",
            translation_date="2026-03-05",
            job_type="Translation",
            case_number=f"ABC-{index}",
            court_email="court@example.pt",
            case_entity="Case Entity",
            case_city="Beja",
            service_entity="Case Entity",
            service_city="Beja",
            service_date="2026-03-05",
            lang="FR",
            pages=3,
            word_count=1000,
            rate_per_word=0.08,
            expected_total=80.0,
            amount_paid=0.0,
            api_cost=0.0,
            run_id=f"run-{index}",
            target_lang="FR",
            total_tokens=5000,
            estimated_api_cost=2.5,
            quality_risk_score=0.2,
            profit=77.5,
            pdf_path=None,
            output_docx=tmp_path / f"translated-{index}.docx",
        )

    captured_payloads: list[dict[str, object]] = []

    def _fake_insert_job_run(_conn, payload):
        captured_payloads.append(dict(payload))
        return len(captured_payloads)

    monkeypatch.setattr(dialogs_module, "insert_job_run", _fake_insert_job_run)
    monkeypatch.setattr(dialogs_module, "_save_joblog_settings_bundle", lambda *args, **kwargs: None)

    try:
        for attempt in range(6):
            dialog = QtSaveToJobLogDialog(
                parent=None,
                db_path=tmp_path / f"joblog-{attempt}.sqlite3",
                seed=_make_seed(attempt),
            )
            accepted = {"count": 0}
            dialog.accepted.connect(lambda accepted=accepted: accepted.__setitem__("count", accepted["count"] + 1))
            try:
                _close_qt_transients(app, keep=(dialog,))
                _activate_dialog_and_focus(app, dialog, dialog.case_number_edit)
                QTest.keyClick(dialog.case_number_edit, Qt.Key.Key_Return)
                _drain_qt_events(app, cycles=4, wait_ms=5)
                assert accepted["count"] == 1
                assert dialog.result() == QDialog.DialogCode.Accepted
            finally:
                dialog.close()
                dialog.deleteLater()
                _close_qt_transients(app)
        assert len(captured_payloads) == 6
    finally:
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_defaults_service_same_and_one_way_distance(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="",
        service_city="",
        service_date="2026-03-05",
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.service_same_check.isChecked() is True
        assert dialog.service_group.is_expanded() is False
        assert dialog.service_group.summary_label.text() == "Same as case"
        assert dialog.service_city_combo.currentText() == "Beja"
        assert dialog.include_transport_sentence_check.isChecked() is True
        assert dialog.travel_km_outbound_edit.text() == "39"
        assert dialog.travel_km_return_edit is dialog.travel_km_outbound_edit
        assert dialog.travel_km_outbound_edit.isEnabled() is True
        assert dialog.add_case_entity_btn.objectName() == "CompactAddButton"
        assert dialog.add_service_entity_btn.objectName() == "CompactAddButton"
        assert dialog.use_service_location_check.text() == "Mention service location in text"
        assert dialog.include_transport_sentence_check.text() == "Include transport sentence"
        assert dialog.interpretation_hint_label.text() == "Distance saved by city."
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_service_city_switches_to_saved_distance(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    profile = default_primary_profile()
    profile.travel_distances_by_city = {"Beja": 39.0, "Cuba": 26.0}
    monkeypatch.setattr(
        dialogs_module,
        "load_profile_settings",
        lambda: ([profile], profile.id),
    )

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="",
        service_city="",
        service_date="2026-03-05",
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.travel_km_outbound_edit.text() == "39"
        dialog.service_same_check.setChecked(False)
        dialog.service_city_combo.setCurrentText("Cuba")
        app.processEvents()
        assert dialog.service_group.is_expanded() is True
        assert dialog.travel_km_outbound_edit.text() == "26"
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_city_combos_include_profile_distance_cities(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    profile = default_primary_profile()
    profile.travel_distances_by_city = {"Beja": 39.0, "Cuba": 26.0}
    monkeypatch.setattr(
        dialogs_module,
        "load_profile_settings",
        lambda: ([profile], profile.id),
    )

    dialog = QtSaveToJobLogDialog(
        parent=None,
        db_path=tmp_path / "joblog.sqlite3",
        seed=build_blank_interpretation_seed(),
    )
    try:
        dialog.show()
        app.processEvents()
        assert dialog.case_city_combo.findText("Cuba") >= 0
        assert dialog.service_city_combo.findText("Cuba") >= 0
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_service_section_expands_when_location_is_mentioned(
    tmp_path: Path,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="",
        service_city="",
        service_date="2026-03-05",
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.service_group.is_expanded() is False
        dialog.use_service_location_check.setChecked(True)
        app.processEvents()
        assert dialog.service_group.is_expanded() is True
        assert dialog.service_group.summary_label.text() == "Location: Beja"
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_header_autofill_reveals_distinct_service_location(
    tmp_path: Path,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="",
        service_city="",
        service_date="2026-03-05",
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.show()
        app.processEvents()
        dialog._apply_header_suggestion(
            dialogs_module.MetadataSuggestion(
                case_entity="Case Entity",
                case_city="Beja",
                case_number="109/26.0PBBJA",
                service_entity="GNR",
                service_city="Cuba",
            )
        )
        app.processEvents()
        assert dialog.service_same_check.isChecked() is False
        assert dialog.service_entity_combo.currentText() == "GNR"
        assert dialog.service_city_combo.currentText() == "Cuba"
        assert dialog.service_group.is_expanded() is True
        assert dialog.service_group.summary_label.text() == "Cuba"
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_header_autofill_does_not_promote_unknown_city(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    warnings: list[str] = []

    def _capture_warning(*args, **_kwargs):
        warnings.append(str(args[2]))
        return dialogs_module.QMessageBox.StandardButton.Ok

    monkeypatch.setattr(dialogs_module.QMessageBox, "warning", _capture_warning)

    dialog = QtSaveToJobLogDialog(
        parent=None,
        db_path=tmp_path / "joblog.sqlite3",
        seed=build_blank_interpretation_seed(),
    )
    try:
        dialog.show()
        app.processEvents()
        dialog._apply_header_suggestion(
            dialogs_module.MetadataSuggestion(
                case_entity="Case Entity",
                case_city="Camões",
                case_number="109/26.0PBBJA",
            )
        )
        app.processEvents()
        assert dialog.case_city_combo.currentText() == ""
        assert dialog.case_city_combo.findText("Camões") == -1
        assert "Camões" not in dialog._settings["vocab_cities"]
        assert any("Camões" in message for message in warnings)
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_validation_error_expands_service_section(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="",
        service_city="",
        service_date="2026-03-05",
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    messages: list[str] = []
    monkeypatch.setattr(
        dialogs_module.QMessageBox,
        "critical",
        lambda _parent, _title, message: messages.append(message),
    )

    def _raise_invalid() -> dict[str, object]:
        raise ValueError("Service city must be set.")

    monkeypatch.setattr(dialog, "_normalized_payload", _raise_invalid)

    try:
        dialog.show()
        app.processEvents()
        assert dialog.service_group.is_expanded() is False
        dialog._save()
        app.processEvents()
        assert messages == ["Service city must be set."]
        assert dialog.service_group.is_expanded() is True
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_uses_repaired_legacy_primary_profile_distance(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    legacy_profile = default_primary_profile()
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 8,
                "profiles": [
                    {
                        "id": legacy_profile.id,
                        "first_name": legacy_profile.first_name,
                        "last_name": legacy_profile.last_name,
                        "document_name_override": legacy_profile.document_name_override,
                        "email": legacy_profile.email,
                        "phone_number": legacy_profile.phone_number,
                        "postal_address": legacy_profile.postal_address,
                        "iban": legacy_profile.iban,
                        "iva_text": legacy_profile.iva_text,
                        "irs_text": legacy_profile.irs_text,
                        "travel_origin_label": "",
                        "travel_distances_by_city": {},
                    }
                ],
                "primary_profile_id": legacy_profile.id,
            }
        ),
        encoding="utf-8",
    )

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="",
        service_city="",
        service_date="2026-03-05",
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.service_city_combo.currentText() == "Beja"
        assert dialog.travel_km_outbound_edit.text() == "39"
        profiles, primary_profile_id = user_settings.load_profile_settings()
        stored_profile = next(profile for profile in profiles if profile.id == primary_profile_id)
        assert stored_profile.travel_origin_label == "Marmelar"
        assert stored_profile.travel_distances_by_city["Beja"] == 39.0
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_save_persists_manual_distance_for_service_city(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    profile = default_primary_profile()
    profile.travel_distances_by_city = {"Beja": 39.0}
    saved: dict[str, object] = {}
    monkeypatch.setattr(
        dialogs_module,
        "load_profile_settings",
        lambda: ([profile], profile.id),
    )
    monkeypatch.setattr(
        dialogs_module,
        "save_profile_settings",
        lambda *, profiles, primary_profile_id: saved.update(
            {"profiles": profiles, "primary_profile_id": primary_profile_id}
        ),
    )
    monkeypatch.setattr(
        dialogs_module.QInputDialog,
        "getDouble",
        lambda *_args, **_kwargs: (0.0, False),
    )

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.show()
        app.processEvents()
        dialog.service_same_check.setChecked(False)
        dialog.service_city_combo.setCurrentText("Cuba")
        app.processEvents()
        dialog.travel_km_outbound_edit.setText("26")
        dialog._save()
        assert dialog.saved is True
        assert profile.travel_distances_by_city["Cuba"] == 26.0
        assert saved["primary_profile_id"] == profile.id
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_honorarios_rejects_zero_distance(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(dialogs_module, "settings_path", lambda: settings_file)
    user_settings.save_joblog_settings_to_path(
        settings_file,
        {
            **user_settings.DEFAULT_JOBLOG_SETTINGS,
            "vocab_cities": ["Beja", "Cuba"],
        },
    )
    profile = default_primary_profile()
    profile.travel_distances_by_city = {"Beja": 39.0}
    user_settings.save_profile_settings_to_path(
        settings_file,
        profiles=[profile],
        primary_profile_id=profile.id,
    )
    monkeypatch.setattr(
        dialogs_module,
        "load_profile_settings",
        lambda: user_settings.load_profile_settings_from_path(settings_file),
    )

    seed = build_blank_interpretation_seed()
    seed.case_entity = "Ministério Público de Beja"
    seed.case_city = "Beja"
    seed.service_entity = "GNR"
    seed.service_city = "Cuba"
    seed.translation_date = "2026-03-20"
    seed.service_date = "2026-03-20"

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.show()
        app.processEvents()
        dialog.service_same_check.setChecked(False)
        dialog.case_number_edit.setText("305/23.2GCBJA")
        dialog.travel_km_outbound_edit.setText("0")
        with pytest.raises(ValueError, match="greater than 0"):
            dialog._build_honorarios_draft()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_honorarios_export_dialog_interpretation_rejects_zero_distance(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(dialogs_module, "settings_path", lambda: settings_file)
    user_settings.save_joblog_settings_to_path(
        settings_file,
        {
            **user_settings.DEFAULT_JOBLOG_SETTINGS,
            "vocab_cities": ["Beja", "Cuba"],
        },
    )
    profile = default_primary_profile(email="adel@example.com")
    profile.travel_origin_label = "Marmelar"
    profile.travel_distances_by_city = {"Beja": 39.0}
    user_settings.save_profile_settings_to_path(
        settings_file,
        profiles=[profile],
        primary_profile_id=profile.id,
    )
    monkeypatch.setattr(
        dialogs_module,
        "load_profile_settings",
        lambda: user_settings.load_profile_settings_from_path(settings_file),
    )

    draft = dialogs_module.build_interpretation_honorarios_draft(
        case_number="305/23.2GCBJA",
        case_entity="Ministério Público de Beja",
        case_city="Beja",
        service_date="2026-03-20",
        service_entity="GNR",
        service_city="Cuba",
        use_service_location_in_honorarios=True,
        include_transport_sentence_in_honorarios=True,
        travel_km_outbound=26.0,
        travel_km_return=26.0,
        recipient_block=dialogs_module.default_interpretation_recipient_block(
            "Ministério Público de Beja",
            "Beja",
        ),
        profile=profile,
    )

    dialog = dialogs_module.QtHonorariosExportDialog(parent=None, draft=draft, default_directory=tmp_path)
    try:
        dialog.show()
        app.processEvents()
        dialog.travel_km_outbound_edit.setText("0")
        with pytest.raises(ValueError, match="greater than 0"):
            dialog._build_draft()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_pdf_header_autofill_allows_manual_pdf_pick_when_seed_has_no_pdf(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Interpretation",
        case_number="",
        court_email="",
        case_entity="",
        case_city="",
        service_entity="",
        service_city="",
        service_date="2026-03-05",
        lang="",
        pages=0,
        word_count=0,
        rate_per_word=0.0,
        expected_total=0.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="",
        target_lang="",
        total_tokens=None,
        estimated_api_cost=None,
        quality_risk_score=None,
        profit=0.0,
    )

    monkeypatch.setattr(
        dialogs_module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(pdf_path), "PDF Files (*.pdf)"),
    )
    monkeypatch.setattr(
        dialogs_module,
        "extract_interpretation_notification_metadata_from_pdf_with_diagnostics",
        lambda *_args, **_kwargs: SimpleNamespace(
            suggestion=dialogs_module.MetadataSuggestion(
                case_entity="Juízo Local Criminal de Beja",
                case_city="Beja",
                case_number="109/26.0PBBJA",
                court_email="beja.judicial@tribunais.org.pt",
                service_entity="Juízo Local Criminal de Beja",
                service_city="Beja",
                service_date="2026-02-26",
            ),
            diagnostics=dialogs_module.MetadataExtractionDiagnostics(
                page_numbers=(1,),
                embedded_text_pages=(1,),
                embedded_text_found=True,
                extracted_fields=("case_entity", "case_city", "case_number", "service_date"),
            ),
        ),
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        assert dialog.autofill_header_btn.text() == "Autofill from notification PDF..."
        assert dialog.autofill_header_btn.isEnabled() is True
        dialog._autofill_from_pdf_header()
        assert dialog.case_number_edit.text() == "109/26.0PBBJA"
        assert dialog.case_city_combo.currentText() == "Beja"
        assert dialog.translation_date_edit.text() == "2026-02-26"
        assert dialog._seed.pdf_path == pdf_path.resolve()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_edit_joblog_dialog_interpretation_autofill_surfaces_notice_diagnostics_when_empty(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    pdf_path = tmp_path / "notice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    seed = build_blank_interpretation_seed()
    warnings: list[str] = []

    monkeypatch.setattr(
        dialogs_module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(pdf_path), "PDF Files (*.pdf)"),
    )
    monkeypatch.setattr(
        dialogs_module,
        "extract_interpretation_notification_metadata_from_pdf_with_diagnostics",
        lambda *_args, **_kwargs: SimpleNamespace(
            suggestion=dialogs_module.MetadataSuggestion(),
            diagnostics=dialogs_module.MetadataExtractionDiagnostics(
                page_numbers=(1, 2),
                ocr_attempted_pages=(1, 2),
                ocr_attempted=True,
                local_ocr_available=False,
                api_ocr_configured=True,
                api_env_names=("OPENAI_API_KEY", "DEEPSEEK_API_KEY"),
                effective_ocr_mode="auto",
                ocr_failure_reason="Local OCR unavailable: 'tesseract' executable was not found in PATH.",
                runtime_caveat="OpenAI client is unavailable in this temporary launcher.",
            ),
        ),
    )
    monkeypatch.setattr(
        dialogs_module.QMessageBox,
        "warning",
        lambda _parent, _title, text: warnings.append(text) or dialogs_module.QMessageBox.StandardButton.Ok,
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog._autofill_from_pdf_header()
        assert warnings
        assert "No notification metadata could be extracted automatically." in warnings[0]
        assert "Local OCR: unavailable" in warnings[0]
        assert "API OCR: configured, but unavailable in this session." in warnings[0]
        assert "Runtime caveat: OpenAI client is unavailable in this temporary launcher." in warnings[0]
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_save_to_joblog_dialog_small_screen_uses_scrollable_body_and_collapsed_sections(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    monkeypatch.setattr(
        window_adaptive_module,
        "available_screen_geometry",
        lambda _widget: QRect(0, 0, 820, 620),
    )

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Translation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="FR",
        pages=3,
        word_count=1000,
        rate_per_word=0.08,
        expected_total=80.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="FR",
        total_tokens=5000,
        estimated_api_cost=2.5,
        quality_risk_score=0.2,
        profit=77.5,
        pdf_path=tmp_path / "sample.pdf",
        output_docx=tmp_path / "translated.docx",
    )

    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.width() <= 672
        assert dialog.height() <= 545
        assert dialog.form_scroll_area.widgetResizable() is True
        assert dialog.metrics_section.is_expanded() is False
        assert dialog.finance_section.is_expanded() is False
        assert dialog.save_btn.parentWidget() is dialog.action_bar
        assert dialog.cancel_btn.parentWidget() is dialog.action_bar
        action_margins = dialog.action_bar.layout().contentsMargins()
        assert action_margins.left() == 10
        assert action_margins.top() == 8
        assert action_margins.right() == 10
        assert action_margins.bottom() == 8
        assert dialog.save_btn.height() < dialog.action_bar.height()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def _joblog_row_payload(
    index: int = 0,
    *,
    completed_at: str | None = None,
    translation_date: str | None = None,
    case_number: str | None = None,
    lang: str = "AR",
    target_lang: str | None = None,
) -> dict[str, object]:
    day = index + 6
    resolved_translation_date = translation_date or f"2026-03-{day:02d}"
    return {
        "completed_at": completed_at or f"{resolved_translation_date}T16:58:34",
        "translation_date": resolved_translation_date,
        "job_type": "Translation",
        "case_number": case_number or f"case-{index}",
        "court_email": "beja.judicial@tribunais.org.pt",
        "case_entity": "Juizo Local Criminal de Beja",
        "case_city": "Beja",
        "service_entity": "Juizo Local Criminal de Beja",
        "service_city": "Beja",
        "service_date": resolved_translation_date,
        "lang": lang,
        "target_lang": target_lang or lang,
        "run_id": f"20260306_16583{index}",
        "pages": 7,
        "word_count": 1666,
        "total_tokens": 57126,
        "rate_per_word": 0.09,
        "expected_total": 149.94,
        "amount_paid": 0.0,
        "api_cost": 0.56,
        "estimated_api_cost": 0.56,
        "quality_risk_score": 0.1754,
        "profit": 149.38,
    }


def test_joblog_window_inline_edit_uses_combo_and_text_editors_and_saves(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        insert_job_run(conn, _joblog_row_payload(case_number="109/26.0PBBJA"))

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        window._visible_columns = ["translation_date", "service_date", "job_type", "pages", "case_number"]
        window._apply_visible_columns()
        window._on_table_cell_double_clicked(0, window._table_column_index("job_type"))
        job_type_widget = window.table.cellWidget(0, window._table_column_index("job_type"))
        translation_date_widget = window.table.cellWidget(0, window._table_column_index("translation_date"))
        service_date_widget = window.table.cellWidget(0, window._table_column_index("service_date"))
        pages_widget = window.table.cellWidget(0, window._table_column_index("pages"))
        assert isinstance(job_type_widget, NoWheelComboBox)
        assert job_type_widget.isEditable() is False
        assert isinstance(translation_date_widget, GuardedDateEdit)
        assert isinstance(service_date_widget, GuardedDateEdit)
        inline_translation_calendar = translation_date_widget.calendarWidget()
        inline_service_calendar = service_date_widget.calendarWidget()
        assert inline_translation_calendar.firstDayOfWeek() == Qt.DayOfWeek.Monday
        assert inline_service_calendar.firstDayOfWeek() == Qt.DayOfWeek.Monday
        assert inline_translation_calendar.horizontalHeaderFormat() == QCalendarWidget.HorizontalHeaderFormat.ShortDayNames
        inline_translation_calendar.setCurrentPage(2026, 3)
        app.processEvents()
        assert (
            inline_translation_calendar.dateTextFormat(QDate(2026, 2, 28)).foreground().color().name().lower()
            == CALENDAR_WEEKEND_COLOR.lower()
        )
        assert isinstance(pages_widget, QLineEdit)
        assert window.refresh_btn.isEnabled() is False
        assert window.columns_btn.isEnabled() is False

        job_type_widget.setCurrentText("Interpretation")
        translation_date_widget.setCalendarDate(QDate(2026, 3, 11))
        service_date_widget.setCalendarDate(QDate(2026, 3, 12))
        assert isinstance(pages_widget, QLineEdit)
        pages_widget.setText("9")

        case_number_widget = window.table.cellWidget(0, window._table_column_index("case_number"))
        assert isinstance(case_number_widget, QLineEdit)
        case_number_widget.setText("updated-case")

        window._save_inline_edit(int(window._rows_data[0]["id"]))

        with open_job_log(db_path) as conn:
            row = conn.execute(
                "SELECT job_type, pages, case_number, translation_date, service_date FROM job_runs WHERE id = 1"
            ).fetchone()
        assert row is not None
        assert row[0] == "Interpretation"
        assert int(row[1]) == 9
        assert row[2] == "updated-case"
        assert row[3] == "2026-03-11"
        assert row[4] == "2026-03-12"
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_joblog_window_inline_edit_cancel_restores_values_and_blocks_other_row(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        for index in range(2):
            insert_job_run(conn, _joblog_row_payload(index=index))

    messages: list[str] = []
    monkeypatch.setattr(
        dialogs_module.QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        window._on_table_cell_double_clicked(0, window._table_column_index("case_number"))
        case_number_widget = window.table.cellWidget(0, window._table_column_index("case_number"))
        assert isinstance(case_number_widget, QLineEdit)
        case_number_widget.setText("changed")

        window._on_table_cell_double_clicked(1, window._table_column_index("case_number"))
        assert messages == ["Finish editing the current row first."]

        window._cancel_inline_edit(int(window._rows_data[0]["id"]))
        restored_item = window.table.item(0, window._table_column_index("case_number"))
        assert restored_item is not None
        assert restored_item.text() == "case-1"
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_joblog_window_edit_action_opens_historical_row_in_edit_mode(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        insert_job_run(conn, _joblog_row_payload(case_number="109/26.0PBBJA"))

    captured: dict[str, object] = {}

    class _FakeEditDialog:
        def __init__(self, *, parent, db_path, seed, on_saved, allow_honorarios_export, edit_row_id) -> None:
            captured["db_path"] = db_path
            captured["seed"] = seed
            captured["allow_honorarios_export"] = allow_honorarios_export
            captured["edit_row_id"] = edit_row_id
            captured["on_saved"] = on_saved

        def exec(self) -> int:
            captured["exec"] = True
            return 0

    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.QtSaveToJobLogDialog", _FakeEditDialog)

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        row_id = int(window._rows_data[0]["id"])
        window._open_edit_dialog(row_id)
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()

    assert captured["db_path"] == db_path
    assert captured["edit_row_id"] == row_id
    assert captured["allow_honorarios_export"] is True
    assert captured["exec"] is True
    seed = captured["seed"]
    assert isinstance(seed, JobLogSeed)
    assert seed.case_number == "109/26.0PBBJA"
    assert seed.pdf_path is None


def test_joblog_window_add_blank_interpretation_entry_opens_dialog_with_interpretation_seed(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    captured: dict[str, object] = {}

    class _FakeAddDialog:
        def __init__(self, *, parent, db_path, seed, on_saved, allow_honorarios_export, edit_row_id=None) -> None:
            captured["db_path"] = db_path
            captured["seed"] = seed
            captured["allow_honorarios_export"] = allow_honorarios_export
            captured["edit_row_id"] = edit_row_id
            captured["on_saved"] = on_saved

        def exec(self) -> int:
            captured["exec"] = True
            return 0

    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.QtSaveToJobLogDialog", _FakeAddDialog)

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        assert window.add_blank_interpretation_action.text() == "Blank/manual interpretation entry"
        window._open_blank_interpretation_dialog()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()

    assert captured["db_path"] == db_path
    assert captured["allow_honorarios_export"] is True
    assert captured["edit_row_id"] is None
    assert captured["exec"] is True
    seed = captured["seed"]
    assert isinstance(seed, JobLogSeed)
    assert seed.job_type == "Interpretation"
    assert seed.service_city == ""
    assert seed.use_service_location_in_honorarios is False
    assert seed.include_transport_sentence_in_honorarios is True


def test_joblog_window_add_interpretation_from_notification_pdf_opens_prefilled_dialog(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    pdf_path = tmp_path / "notification.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    captured: dict[str, object] = {}

    class _FakeAddDialog:
        def __init__(self, *, parent, db_path, seed, on_saved, allow_honorarios_export, edit_row_id=None) -> None:
            captured["db_path"] = db_path
            captured["seed"] = seed
            captured["allow_honorarios_export"] = allow_honorarios_export
            captured["edit_row_id"] = edit_row_id
            captured["on_saved"] = on_saved

        def exec(self) -> int:
            captured["exec"] = True
            return 0

    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.QtSaveToJobLogDialog", _FakeAddDialog)
    monkeypatch.setattr(
        dialogs_module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(pdf_path), "PDF Files (*.pdf)"),
    )
    seed_payload = asdict(
        JobLogSeed(
            completed_at="2026-03-18T10:00:00",
            translation_date="2025-04-09",
            job_type="Interpretation",
            case_number="000055/25.5GAFAL",
            court_email="beja.ministeriopublico@tribunais.org.pt",
            case_entity="Ministério Público de Beja",
            case_city="Beja",
            service_entity="GNR",
            service_city="Vidigueira",
            service_date="2025-04-09",
            lang="",
            pages=0,
            word_count=0,
            rate_per_word=0.0,
            expected_total=0.0,
            amount_paid=0.0,
            api_cost=0.0,
            run_id="",
            target_lang="",
            total_tokens=None,
            estimated_api_cost=None,
            quality_risk_score=None,
            profit=0.0,
            pdf_path=pdf_path.resolve(),
            output_docx=None,
            partial_docx=None,
        )
    )
    monkeypatch.setattr(
        dialogs_module,
        "shared_service_autofill_interpretation_from_notification_pdf",
        lambda **_kwargs: {
            "status": "ok",
            "normalized_payload": seed_payload,
            "diagnostics": {
                "metadata_extraction": {
                    "extracted_fields": [
                        "case_entity",
                        "case_city",
                        "case_number",
                        "court_email",
                        "service_entity",
                        "service_city",
                        "service_date",
                    ]
                }
            },
        },
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        window._open_notification_interpretation_dialog()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()

    assert captured["db_path"] == db_path
    assert captured["allow_honorarios_export"] is True
    assert captured["edit_row_id"] is None
    assert captured["exec"] is True
    seed = captured["seed"]
    assert isinstance(seed, JobLogSeed)
    assert seed.job_type == "Interpretation"
    assert seed.pdf_path == pdf_path.resolve()
    assert seed.translation_date == "2025-04-09"
    assert seed.service_date == "2025-04-09"
    assert seed.case_number == "000055/25.5GAFAL"
    assert seed.case_entity == "Ministério Público de Beja"
    assert seed.case_city == "Beja"
    assert seed.court_email == "beja.ministeriopublico@tribunais.org.pt"
    assert seed.service_entity == "GNR"
    assert seed.service_city == "Vidigueira"
    assert seed.use_service_location_in_honorarios is False
    assert seed.include_transport_sentence_in_honorarios is True
    assert seed.include_transport_sentence_in_honorarios is True


def test_joblog_window_add_interpretation_from_photo_opens_prefilled_dialog_and_prompts_distance(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-image")
    captured: dict[str, object] = {}

    class _FakeAddDialog:
        def __init__(self, *, parent, db_path, seed, on_saved, allow_honorarios_export, edit_row_id=None) -> None:
            captured["db_path"] = db_path
            captured["seed"] = seed
            captured["allow_honorarios_export"] = allow_honorarios_export
            captured["edit_row_id"] = edit_row_id
            captured["on_saved"] = on_saved

        def _prompt_interpretation_distance_for_imported_city(self) -> None:
            captured["prompt_called"] = True

        def exec(self) -> int:
            captured["exec"] = True
            return 0

    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.QtSaveToJobLogDialog", _FakeAddDialog)
    monkeypatch.setattr(
        dialogs_module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(image_path), "Image Files (*.jpg)"),
    )
    seed_payload = asdict(
        JobLogSeed(
            completed_at="2026-03-18T10:00:00",
            translation_date="2026-02-02",
            job_type="Interpretation",
            case_number="69/26.8PBBBJA",
            court_email="",
            case_entity="Ministério Público de Beja",
            case_city="Beja",
            service_entity="",
            service_city="",
            service_date="2026-02-02",
            lang="",
            pages=0,
            word_count=0,
            rate_per_word=0.0,
            expected_total=0.0,
            amount_paid=0.0,
            api_cost=0.0,
            run_id="",
            target_lang="",
            total_tokens=None,
            estimated_api_cost=None,
            quality_risk_score=None,
            profit=0.0,
            pdf_path=None,
            output_docx=None,
            partial_docx=None,
        )
    )
    monkeypatch.setattr(
        dialogs_module,
        "shared_service_autofill_interpretation_from_photo",
        lambda **_kwargs: {
            "status": "ok",
            "normalized_payload": seed_payload,
            "diagnostics": {
                "metadata_extraction": {
                    "extracted_fields": [
                        "case_entity",
                        "case_city",
                        "case_number",
                        "service_date",
                    ]
                }
            },
        },
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        window._open_photo_interpretation_dialog()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()

    assert captured["db_path"] == db_path
    assert captured["allow_honorarios_export"] is True
    assert captured["edit_row_id"] is None
    assert captured["exec"] is True
    assert captured["prompt_called"] is True
    seed = captured["seed"]
    assert isinstance(seed, JobLogSeed)
    assert seed.job_type == "Interpretation"
    assert seed.pdf_path is None
    assert seed.translation_date == "2026-02-02"
    assert seed.service_date == "2026-02-02"
    assert seed.case_number == "69/26.8PBBBJA"
    assert seed.case_entity == "Ministério Público de Beja"
    assert seed.case_city == "Beja"


def test_build_interpretation_seed_from_photo_screenshot_leaves_service_date_blank_when_missing() -> None:
    seed = build_interpretation_seed_from_photo_screenshot(
        suggestion=dialogs_module.MetadataSuggestion(
            case_entity="Ministério Público de Beja",
            case_city="Beja",
            case_number="69/26.8PBBBJA",
        ),
        vocab_court_emails=["beja.ministeriopublico@tribunais.org.pt"],
    )

    assert seed.translation_date == ""
    assert seed.service_date == ""
    assert seed.case_number == "69/26.8PBBBJA"
    assert seed.case_entity == "Ministério Público de Beja"
    assert seed.case_city == "Beja"


def test_save_to_joblog_dialog_interpretation_photo_autofill_prompts_and_saves_distance(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-image")
    profile = default_primary_profile()
    profile.travel_distances_by_city = {}
    saved: dict[str, object] = {}

    monkeypatch.setattr(
        dialogs_module,
        "load_profile_settings",
        lambda: ([profile], profile.id),
    )
    monkeypatch.setattr(
        dialogs_module,
        "save_profile_settings",
        lambda *, profiles, primary_profile_id: saved.update(
            {"profiles": profiles, "primary_profile_id": primary_profile_id}
        ),
    )
    monkeypatch.setattr(
        dialogs_module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(image_path), "Image Files (*.jpg)"),
    )
    monkeypatch.setattr(
        dialogs_module,
        "extract_interpretation_photo_metadata_from_image",
        lambda *_args, **_kwargs: dialogs_module.MetadataSuggestion(
            case_entity="Ministério Público de Beja",
            case_city="Beja",
            case_number="69/26.8PBBBJA",
            service_date="2026-02-02",
        ),
    )
    monkeypatch.setattr(
        dialogs_module,
        "extract_photo_metadata_from_image",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("generic photo extractor should not be used")),
    )
    monkeypatch.setattr(
        dialogs_module.QInputDialog,
        "getDouble",
        lambda *_args, **_kwargs: (39.0, True),
    )

    dialog = QtSaveToJobLogDialog(
        parent=None,
        db_path=tmp_path / "joblog.sqlite3",
        seed=build_blank_interpretation_seed(),
    )
    try:
        dialog._autofill_from_photo()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()

    assert dialog.case_entity_combo.currentText() == "Ministério Público de Beja"
    assert dialog.case_city_combo.currentText() == "Beja"
    assert dialog.case_number_edit.text() == "69/26.8PBBBJA"
    assert dialog.service_date_edit.text() == "2026-02-02"
    assert dialog.travel_km_outbound_edit.text() == "39"
    assert dialog.travel_km_return_edit.text() == "39"
    assert profile.travel_distances_by_city["Beja"] == 39.0
    assert saved["primary_profile_id"] == profile.id


def test_save_to_joblog_dialog_interpretation_photo_autofill_clears_missing_service_date(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(b"fake-image")

    monkeypatch.setattr(
        dialogs_module.QFileDialog,
        "getOpenFileName",
        lambda *_args, **_kwargs: (str(image_path), "Image Files (*.jpg)"),
    )
    monkeypatch.setattr(
        dialogs_module,
        "extract_interpretation_photo_metadata_from_image",
        lambda *_args, **_kwargs: dialogs_module.MetadataSuggestion(
            case_entity="Ministério Público de Beja",
            case_city="Beja",
            case_number="69/26.8PBBBJA",
            service_date="",
        ),
    )
    monkeypatch.setattr(
        dialogs_module.QInputDialog,
        "getDouble",
        lambda *_args, **_kwargs: (39.0, True),
    )

    dialog = QtSaveToJobLogDialog(
        parent=None,
        db_path=tmp_path / "joblog.sqlite3",
        seed=build_blank_interpretation_seed(),
    )
    try:
        assert dialog.translation_date_edit.text() == ""
        dialog._autofill_from_photo()
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()

    assert dialog.translation_date_edit.text() == ""
    assert dialog.case_entity_combo.currentText() == "Ministério Público de Beja"
    assert dialog.case_city_combo.currentText() == "Beja"
    assert dialog.case_number_edit.text() == "69/26.8PBBBJA"


def test_honorarios_export_dialog_interpretation_defaults_to_collapsed_service_and_recipient_sections(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    profile = default_primary_profile(email="adel@example.com")
    profile.travel_origin_label = "Marmelar"
    profile.travel_distances_by_city = {"Ferreira do Alentejo": 42.0}
    monkeypatch.setattr(dialogs_module, "load_profile_settings", lambda: ([profile], profile.id))

    draft = dialogs_module.build_interpretation_honorarios_draft(
        case_number="66/26.3GAFAL",
        case_entity="Tribunal Judicial",
        case_city="Ferreira do Alentejo",
        service_date="2026-03-11",
        service_entity="Tribunal Judicial",
        service_city="Ferreira do Alentejo",
        use_service_location_in_honorarios=False,
        include_transport_sentence_in_honorarios=True,
        travel_km_outbound=42.0,
        travel_km_return=42.0,
        recipient_block=dialogs_module.default_interpretation_recipient_block(
            "Tribunal Judicial",
            "Ferreira do Alentejo",
        ),
        profile=profile,
    )

    dialog = dialogs_module.QtHonorariosExportDialog(parent=None, draft=draft, default_directory=tmp_path)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.service_group.is_expanded() is False
        assert dialog.service_group.summary_label.text() == "2026-03-11 · Same as case"
        assert dialog.text_group.is_expanded() is True
        assert dialog.recipient_group.is_expanded() is False
        assert dialog.recipient_group.summary_label.text() == "Auto from case"
        assert dialog.use_service_location_check.text() == "Mention service location in text"
        assert dialog.include_transport_sentence_check.text() == "Include transport sentence"
        assert dialog.distance_hint_label.text() == "Saved by city."
        assert dialog.service_group_help_btn.objectName() == "InlineInfoButton"
        assert dialog.recipient_group_help_btn.objectName() == "InlineInfoButton"
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_honorarios_export_dialog_service_section_expands_for_explicit_location(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    profile = default_primary_profile(email="adel@example.com")
    profile.travel_origin_label = "Marmelar"
    profile.travel_distances_by_city = {"Ferreira do Alentejo": 42.0}
    monkeypatch.setattr(dialogs_module, "load_profile_settings", lambda: ([profile], profile.id))

    draft = dialogs_module.build_interpretation_honorarios_draft(
        case_number="66/26.3GAFAL",
        case_entity="Tribunal Judicial",
        case_city="Ferreira do Alentejo",
        service_date="2026-03-11",
        service_entity="Tribunal Judicial",
        service_city="Ferreira do Alentejo",
        use_service_location_in_honorarios=False,
        include_transport_sentence_in_honorarios=True,
        travel_km_outbound=42.0,
        travel_km_return=42.0,
        recipient_block=dialogs_module.default_interpretation_recipient_block(
            "Tribunal Judicial",
            "Ferreira do Alentejo",
        ),
        profile=profile,
    )

    dialog = dialogs_module.QtHonorariosExportDialog(parent=None, draft=draft, default_directory=tmp_path)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.service_group.is_expanded() is False
        dialog.use_service_location_check.setChecked(True)
        app.processEvents()
        assert dialog.service_group.is_expanded() is True
        assert dialog.service_group.summary_label.text() == "2026-03-11 · Location: Ferreira do Alentejo"
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_honorarios_export_dialog_distinct_service_values_start_expanded(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    profile = default_primary_profile(email="adel@example.com")
    profile.travel_origin_label = "Marmelar"
    profile.travel_distances_by_city = {"Cuba": 26.0}
    monkeypatch.setattr(dialogs_module, "load_profile_settings", lambda: ([profile], profile.id))

    draft = dialogs_module.build_interpretation_honorarios_draft(
        case_number="66/26.3GAFAL",
        case_entity="Tribunal Judicial",
        case_city="Ferreira do Alentejo",
        service_date="2026-03-11",
        service_entity="GNR",
        service_city="Cuba",
        use_service_location_in_honorarios=True,
        include_transport_sentence_in_honorarios=True,
        travel_km_outbound=26.0,
        travel_km_return=26.0,
        recipient_block=dialogs_module.default_interpretation_recipient_block(
            "Tribunal Judicial",
            "Ferreira do Alentejo",
        ),
        profile=profile,
    )

    dialog = dialogs_module.QtHonorariosExportDialog(parent=None, draft=draft, default_directory=tmp_path)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.service_same_check.isChecked() is False
        assert dialog.service_group.is_expanded() is True
        assert dialog.service_group.summary_label.text() == "2026-03-11 · Location: Cuba"
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_honorarios_export_dialog_recipient_section_expands_after_manual_edit(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    profile = default_primary_profile(email="adel@example.com")
    profile.travel_origin_label = "Marmelar"
    profile.travel_distances_by_city = {"Ferreira do Alentejo": 42.0}
    monkeypatch.setattr(dialogs_module, "load_profile_settings", lambda: ([profile], profile.id))

    draft = dialogs_module.build_interpretation_honorarios_draft(
        case_number="66/26.3GAFAL",
        case_entity="Tribunal Judicial",
        case_city="Ferreira do Alentejo",
        service_date="2026-03-11",
        service_entity="Tribunal Judicial",
        service_city="Ferreira do Alentejo",
        use_service_location_in_honorarios=False,
        include_transport_sentence_in_honorarios=True,
        travel_km_outbound=42.0,
        travel_km_return=42.0,
        recipient_block=dialogs_module.default_interpretation_recipient_block(
            "Tribunal Judicial",
            "Ferreira do Alentejo",
        ),
        profile=profile,
    )

    dialog = dialogs_module.QtHonorariosExportDialog(parent=None, draft=draft, default_directory=tmp_path)
    try:
        dialog.show()
        app.processEvents()
        assert dialog.recipient_group.is_expanded() is False
        dialog.recipient_block_edit.setPlainText("Exmo. Senhor Juiz\nTribunal Judicial\nFerreira do Alentejo")
        app.processEvents()
        assert dialog.recipient_group.is_expanded() is True
        assert dialog.recipient_group.summary_label.text() == "Exmo. Senhor Juiz (+2)"
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()


def test_joblog_window_interpretation_honorarios_skips_gmail_offer(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        insert_job_run(
            conn,
            {
                "completed_at": "2026-03-09T10:00:00",
                "translation_date": "2026-03-09",
                "job_type": "Interpretation",
                "case_number": "000055/25.5GAFAL",
                "court_email": "beja.ministeriopublico@tribunais.org.pt",
                "case_entity": "Ministério Público de Beja",
                "case_city": "Beja",
                "service_entity": "GNR",
                "service_city": "Vidigueira",
                "service_date": "2026-03-09",
                "travel_km_outbound": 50.0,
                "travel_km_return": 50.0,
                "use_service_location_in_honorarios": 1,
                "lang": "",
                "target_lang": "",
                "run_id": "",
                "pages": 0,
                "word_count": 0,
                "rate_per_word": 0.0,
                "expected_total": 0.0,
                "amount_paid": 0.0,
                "api_cost": 0.0,
                "profit": 0.0,
            },
        )

    captured: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory) -> None:
            self.saved_path = tmp_path / "interpretation_honorarios.docx"
            self.saved_pdf_path = tmp_path / "interpretation_honorarios.pdf"
            self.saved_pdf_path.write_bytes(b"%PDF-1.7")
            self.generated_draft = draft
            captured["draft"] = draft

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.QtHonorariosExportDialog", _FakeHonorariosDialog)
    monkeypatch.setattr(
        dialogs_module.QtJobLogWindow,
        "_offer_gmail_draft_for_honorarios",
        lambda *args, **kwargs: captured.__setitem__("gmail_called", True),
    )
    monkeypatch.setattr(
        dialogs_module.QtJobLogWindow,
        "_offer_gmail_draft_for_interpretation_honorarios",
        lambda *args, **kwargs: captured.__setitem__("interpretation_gmail_called", True),
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        window.table.selectRow(0)
        QApplication.processEvents()
        window._open_honorarios_dialog()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()

    draft = captured["draft"]
    assert draft.kind.value == "interpretation"
    assert draft.service_city == "Vidigueira"
    assert captured.get("gmail_called") is not True
    assert captured.get("interpretation_gmail_called") is True


def test_joblog_window_interpretation_honorarios_shows_local_only_handoff_after_export_dialog(
    tmp_path: Path,
    monkeypatch,
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        insert_job_run(
            conn,
            {
                "completed_at": "2026-03-09T10:00:00",
                "translation_date": "2026-03-09",
                "job_type": "Interpretation",
                "case_number": "000055/25.5GAFAL",
                "court_email": "beja.ministeriopublico@tribunais.org.pt",
                "case_entity": "Ministério Público de Beja",
                "case_city": "Beja",
                "service_entity": "GNR",
                "service_city": "Vidigueira",
                "service_date": "2026-03-09",
                "travel_km_outbound": 50.0,
                "travel_km_return": 50.0,
                "use_service_location_in_honorarios": 1,
                "lang": "",
                "target_lang": "",
                "run_id": "",
                "pages": 0,
                "word_count": 0,
                "rate_per_word": 0.0,
                "expected_total": 0.0,
                "amount_paid": 0.0,
                "api_cost": 0.0,
                "profit": 0.0,
            },
        )

    captured: dict[str, object] = {}

    class _FakeHonorariosDialog:
        def __init__(self, *, parent, draft, default_directory) -> None:
            self.saved_path = tmp_path / "interpretation_honorarios.docx"
            self.saved_path.write_bytes(b"docx")
            self.saved_pdf_path = None
            self.pdf_unavailable_explained = True
            self.generated_draft = draft

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("legalpdf_translate.qt_gui.dialogs.QtHonorariosExportDialog", _FakeHonorariosDialog)
    monkeypatch.setattr(
        dialogs_module,
        "show_local_only_honorarios_ready_box",
        lambda _parent, *, docx_path, pdf_error="", gmail_blocked: captured.__setitem__(
            "local_only_box",
            {
                "docx_path": docx_path,
                "pdf_error": pdf_error,
                "gmail_blocked": gmail_blocked,
            },
        ),
    )
    monkeypatch.setattr(
        dialogs_module.QtJobLogWindow,
        "_offer_gmail_draft_for_interpretation_honorarios",
        lambda *args, **kwargs: captured.__setitem__("interpretation_gmail_called", True),
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        window.table.selectRow(0)
        QApplication.processEvents()
        window._open_honorarios_dialog()
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()

    assert captured["local_only_box"] == {
        "docx_path": (tmp_path / "interpretation_honorarios.docx").resolve(),
        "pdf_error": "",
        "gmail_blocked": True,
    }
    assert captured.get("interpretation_gmail_called") is not True


def test_joblog_window_action_cell_uses_icon_buttons_and_delete_removes_row(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        for index in range(2):
            insert_job_run(conn, _joblog_row_payload(index=index))

    prompts: list[str] = []
    monkeypatch.setattr(
        dialogs_module.QMessageBox,
        "question",
        lambda _parent, _title, message, *_args, **_kwargs: (
            prompts.append(message),
            dialogs_module.QMessageBox.StandardButton.Yes,
        )[1],
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        assert window.table.selectionMode() == window.table.SelectionMode.ExtendedSelection
        action_widget = window.table.cellWidget(0, 0)
        assert action_widget is not None
        buttons = action_widget.findChildren(QToolButton)
        assert len(buttons) == 2
        assert [button.toolTip() for button in buttons] == ["Edit row", "Delete row"]
        assert [button.text() for button in buttons] == ["", ""]

        deleted_row_id = int(window._rows_data[0]["id"])
        window._confirm_delete_row(deleted_row_id)

        with open_job_log(db_path) as conn:
            rows = conn.execute("SELECT id FROM job_runs ORDER BY completed_at DESC, id DESC").fetchall()
        assert [int(row[0]) for row in rows] == [1]
        assert prompts == ["Delete this Job Log row (case-1)?"]
        assert window.table.currentRow() == 0
        assert int(window._rows_data[0]["id"]) == 1
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_joblog_window_honorarios_requires_exactly_one_selected_row(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        for index in range(3):
            insert_job_run(conn, _joblog_row_payload(index=index))

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        assert window.honorarios_btn.isEnabled() is False
        window.table.selectRow(0)
        QApplication.processEvents()
        assert window.honorarios_btn.isEnabled() is True

        selection_model = window.table.selectionModel()
        assert selection_model is not None
        selection_model.select(
            window.table.model().index(2, window._table_column_index("case_number")),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
        QApplication.processEvents()

        assert len(window._selected_row_indices()) == 2
        assert window.delete_selected_btn.isEnabled() is True
        assert window.honorarios_btn.isEnabled() is False
        assert window._selected_row_data() is None
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_joblog_window_bulk_delete_selected_rows_removes_all_selected_rows(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        for index in range(3):
            insert_job_run(conn, _joblog_row_payload(index=index))

    prompts: list[str] = []
    monkeypatch.setattr(
        dialogs_module.QMessageBox,
        "question",
        lambda _parent, _title, message, *_args, **_kwargs: (
            prompts.append(message),
            dialogs_module.QMessageBox.StandardButton.Yes,
        )[1],
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        selection_model = window.table.selectionModel()
        assert selection_model is not None
        window.table.selectRow(0)
        selection_model.select(
            window.table.model().index(2, window._table_column_index("case_number")),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
        QApplication.processEvents()

        assert len(window._selected_row_ids()) == 2
        assert window.delete_selected_btn.isEnabled() is True

        window._confirm_delete_selected_rows()

        with open_job_log(db_path) as conn:
            rows = conn.execute("SELECT case_number FROM job_runs ORDER BY completed_at DESC, id DESC").fetchall()
        remaining = [str(row[0]) for row in rows]
        assert len(remaining) == 1
        assert prompts and prompts[0].startswith("Delete 2 Job Log rows")
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_joblog_window_delete_is_blocked_during_inline_edit_and_other_row_actions_disable(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        for index in range(2):
            insert_job_run(conn, _joblog_row_payload(index=index))

    messages: list[str] = []
    monkeypatch.setattr(
        dialogs_module.QMessageBox,
        "information",
        lambda _parent, _title, message: messages.append(message),
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        window._on_table_cell_double_clicked(0, window._table_column_index("case_number"))
        assert window.delete_selected_btn.isEnabled() is False
        assert window.honorarios_btn.isEnabled() is False
        second_row_actions = window.table.cellWidget(1, 0)
        assert second_row_actions is not None
        buttons = second_row_actions.findChildren(QToolButton)
        assert len(buttons) == 2
        assert all(button.isEnabled() is False for button in buttons)

        window._confirm_delete_row(int(window._rows_data[1]["id"]))
        assert messages == ["Finish editing the current row first."]

        with open_job_log(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()
        assert count is not None
        assert int(count[0]) == 2
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_joblog_window_delete_key_removes_selected_rows_when_table_has_focus(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        for index in range(3):
            insert_job_run(conn, _joblog_row_payload(index=index))

    monkeypatch.setattr(
        dialogs_module.QMessageBox,
        "question",
        lambda *_args, **_kwargs: dialogs_module.QMessageBox.StandardButton.Yes,
    )

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        selection_model = window.table.selectionModel()
        assert selection_model is not None
        _activate_dialog_and_focus(app, window, window.table)
        window.table.selectRow(0)
        selection_model.select(
            window.table.model().index(1, window._table_column_index("case_number")),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
        _drain_qt_events(app, cycles=3, wait_ms=5)
        assert QApplication.focusWidget() in {window.table, window.table.viewport()}

        QTest.keyClick(window.table, Qt.Key.Key_Delete)
        _drain_qt_events(app, cycles=3, wait_ms=5)

        with open_job_log(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM job_runs").fetchone()
        assert count is not None
        assert int(count[0]) == 1
    finally:
        window.close()
        window.deleteLater()
        _close_qt_transients(app)
        if owns_app:
            app.quit()


def test_joblog_window_uses_scrollable_resizable_columns_and_persists_widths(
    tmp_path: Path, monkeypatch
) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    user_settings.save_joblog_settings(
        {
            "joblog_visible_columns": [
                "translation_date",
                "case_number",
                "court_email",
                "service_entity",
            ],
            "joblog_column_widths": {
                "case_number": 220,
            },
        }
    )

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        insert_job_run(conn, _joblog_row_payload(case_number="109/26.0PBBJA"))

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        header = window.table.horizontalHeader()
        assert window.table.horizontalScrollBarPolicy() == dialogs_module.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        assert window.table.horizontalScrollMode() == dialogs_module.QAbstractItemView.ScrollMode.ScrollPerPixel
        assert header.sectionResizeMode(window._table_column_index("case_number")) == dialogs_module.QHeaderView.ResizeMode.Interactive
        assert window.table.columnWidth(window._table_column_index("case_number")) == 220
        service_entity_column = window._table_column_index("service_entity")
        assert window.table.columnWidth(service_entity_column) >= window._header_text_width(service_entity_column)

        window.table.setColumnWidth(window._table_column_index("court_email"), 240)
        loaded = user_settings.load_joblog_settings()
        assert loaded["joblog_column_widths"]["court_email"] == 240
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_normalize_joblog_payload_allows_interpretation_without_translation_fields() -> None:
    seed = build_blank_interpretation_seed()
    payload = dialogs_module._normalize_joblog_payload(
        seed=seed,
        raw_values={
            "translation_date": "2026-03-09",
            "job_type": "Interpretation",
            "case_number": "000055/25.5GAFAL",
            "court_email": "",
            "case_entity": "Ministério Público de Beja",
            "case_city": "Beja",
            "service_entity": "GNR",
            "service_city": "Vidigueira",
            "service_date": "2026-03-09",
            "travel_km_outbound": "50",
            "travel_km_return": "50",
            "lang": "",
            "target_lang": "",
            "run_id": "",
            "pages": "",
            "word_count": "",
            "total_tokens": "",
            "rate_per_word": "",
            "expected_total": "",
            "amount_paid": "0",
            "api_cost": "0",
            "estimated_api_cost": "",
            "quality_risk_score": "",
            "profit": "",
        },
        service_same_checked=False,
        use_service_location_in_honorarios_checked=True,
        include_transport_sentence_in_honorarios_checked=True,
    )

    assert payload["job_type"] == "Interpretation"
    assert payload["pages"] == 0
    assert payload["word_count"] == 0
    assert payload["travel_km_outbound"] == 50.0
    assert payload["travel_km_return"] == 50.0
    assert payload["use_service_location_in_honorarios"] == 1
    assert payload["include_transport_sentence_in_honorarios"] == 1


def test_normalize_joblog_payload_interpretation_ignores_invalid_distance_when_transport_clause_disabled() -> None:
    seed = build_blank_interpretation_seed()
    seed.travel_km_outbound = 39.0
    seed.travel_km_return = 39.0
    payload = dialogs_module._normalize_joblog_payload(
        seed=seed,
        raw_values={
            "translation_date": "2026-03-09",
            "job_type": "Interpretation",
            "case_number": "000055/25.5GAFAL",
            "court_email": "",
            "case_entity": "Ministério Público de Beja",
            "case_city": "Beja",
            "service_entity": "GNR",
            "service_city": "Vidigueira",
            "service_date": "2026-03-09",
            "travel_km_outbound": "not-a-number",
            "travel_km_return": "still-bad",
            "lang": "",
            "target_lang": "",
            "run_id": "",
            "pages": "",
            "word_count": "",
            "total_tokens": "",
            "rate_per_word": "",
            "expected_total": "",
            "amount_paid": "0",
            "api_cost": "0",
            "estimated_api_cost": "",
            "quality_risk_score": "",
            "profit": "",
        },
        service_same_checked=False,
        use_service_location_in_honorarios_checked=False,
        include_transport_sentence_in_honorarios_checked=False,
    )

    assert payload["travel_km_outbound"] == 39.0
    assert payload["travel_km_return"] == 39.0
    assert payload["include_transport_sentence_in_honorarios"] == 0


def test_joblog_window_small_screen_is_bounded(tmp_path: Path, monkeypatch) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    monkeypatch.setattr(
        window_adaptive_module,
        "available_screen_geometry",
        lambda _widget: QRect(0, 0, 900, 640),
    )

    db_path = tmp_path / "joblog.sqlite3"
    with open_job_log(db_path) as conn:
        insert_job_run(conn, _joblog_row_payload(case_number="109/26.0PBBJA"))

    window = QtJobLogWindow(parent=None, db_path=db_path)
    try:
        window.show()
        app.processEvents()
        assert window.width() <= 810
        assert window.height() <= 537
    finally:
        window.close()
        window.deleteLater()
        if owns_app:
            app.quit()


def test_save_to_joblog_dialog_saved_result_is_none_until_saved(tmp_path: Path) -> None:
    app = QApplication.instance()
    owns_app = app is None
    if app is None:
        app = QApplication(sys.argv[:1])

    seed = JobLogSeed(
        completed_at="2026-03-05T10:00:00",
        translation_date="2026-03-05",
        job_type="Translation",
        case_number="ABC-1",
        court_email="court@example.pt",
        case_entity="Case Entity",
        case_city="Beja",
        service_entity="Case Entity",
        service_city="Beja",
        service_date="2026-03-05",
        lang="FR",
        pages=3,
        word_count=1000,
        rate_per_word=0.08,
        expected_total=80.0,
        amount_paid=0.0,
        api_cost=0.0,
        run_id="run-1",
        target_lang="FR",
        total_tokens=5000,
        estimated_api_cost=2.5,
        quality_risk_score=0.2,
        profit=77.5,
        pdf_path=tmp_path / "sample.pdf",
        output_docx=tmp_path / "translated.docx",
    )
    dialog = QtSaveToJobLogDialog(parent=None, db_path=tmp_path / "joblog.sqlite3", seed=seed)
    try:
        assert dialog.saved_result is None
        dialog.reject()
        assert dialog.saved_result is None
    finally:
        dialog.close()
        dialog.deleteLater()
        if owns_app:
            app.quit()
