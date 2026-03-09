from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QCloseEvent, QColor, QImage, QPainter, QPen
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QBoxLayout, QDialog

from legalpdf_translate.gmail_batch import (
    FetchedGmailMessage,
    GmailAttachmentCandidate,
    GmailAttachmentSelection,
    GmailBatchConfirmedItem,
    GmailBatchSession,
    GmailMessageLoadResult,
)
import legalpdf_translate.qt_gui.app_window as app_window_module
import legalpdf_translate.qt_gui.dialogs as dialogs_module
import legalpdf_translate.user_settings as user_settings
from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.docx_writer import assemble_docx
from legalpdf_translate.gmail_focus import (
    WindowAttentionResult,
    bridge_runtime_metadata_path,
    load_bridge_runtime_metadata,
)
from legalpdf_translate.gmail_intake import InboundMailContext
from legalpdf_translate.qt_gui.app_window import QtMainWindow
from legalpdf_translate.qt_gui.dialogs import (
    GmailBatchReviewPreviewCacheTransfer,
    GmailBatchReviewResult,
    JobLogSeed,
    JobLogSavedResult,
    QtArabicDocxReviewDialog,
    QtGmailAttachmentPreviewDialog,
    QtGmailBatchReviewDialog,
    QtSaveToJobLogDialog,
    QtSettingsDialog,
    build_seed_from_run,
    count_words_from_docx,
    count_words_from_output_artifacts,
)
from legalpdf_translate.qt_gui.guarded_inputs import NoWheelComboBox, NoWheelSpinBox
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
        run_dir=resolved_run_dir,
        translated_word_count=translated_word_count,
        joblog_row_id=joblog_row_id or (index + 1),
        run_id=run_id or f"run-{index + 1}",
        case_number=case_number,
        case_entity=case_entity,
        case_city=case_city,
        court_email=court_email,
    )


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
        assert window.translate_btn.text() == "Start Translate"
        assert window.show_adv.text() == "Advanced Settings"
        assert window.progress_panel_title.text() == "Conversion Output"
        assert window.more_btn.menu() is window.more_menu
        assert window.more_btn.text() == "..."
        assert window.footer_meta_label.text() == "Project v3.0 | LegalPDF"
        assert window.translate_btn.minimumHeight() == window.cancel_btn.minimumHeight() == window.more_btn.minimumHeight()
        assert window.cancel_btn.width() == 186
        assert window.more_btn.width() == 92
        assert "review_queue" in window._menu_actions
        assert "save_joblog" in window._menu_actions
        assert "job_log" in window._menu_actions
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
    finally:
        window.close()
        window.deleteLater()
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
        assert window.progress_panel_title.text() == "Conversion Output"
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
        assert window.flag_label.text() == ""
        pixmap = window.flag_label.pixmap()
        assert pixmap is not None and not pixmap.isNull()
        assert window.lang_caret_btn.icon().isNull() is False
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
        assert isinstance(settings_dialog.default_lang_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_effort_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_effort_policy_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_images_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.default_workers_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.ocr_mode_default_combo, NoWheelComboBox)
        assert isinstance(settings_dialog.ocr_engine_default_combo, NoWheelComboBox)
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
        "ensure_edge_native_host_registered",
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
        assert dialog.target_lang_combo.currentText() == "FR"
        assert dialog.table.item(0, 3).text() == "2"
        assert dialog.table.item(1, 3).text() == "1"
        dialog.target_lang_combo.setCurrentText("EN")
        dialog.table.selectAll()
        dialog._accept_selection()
        assert dialog.selected_attachments == attachments
        assert dialog.review_result == GmailBatchReviewResult(
            selections=(
                GmailAttachmentSelection(candidate=attachments[0], start_page=2),
                GmailAttachmentSelection(candidate=attachments[1], start_page=1),
            ),
            target_lang="EN",
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
            assert kwargs["initial_start_page"] == 2
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
        assert dialog.pages_value_label.text() == "Pages: 5"
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
        initial_start_page=2,
        cached_path=tmp_path / "preview.pdf",
        known_page_count=5,
    )
    try:
        dialog.show()
        app.processEvents()
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
        assert dialog.jump_spin.value() == 2
        assert 2 in dialog.started_pages
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
        dialog.use_page_btn.click()
        assert dialog.selected_start_page == 1
        assert dialog.result() == QDialog.DialogCode.Accepted
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
    assert captured["init_kwargs"]["default_start_page"] == 3
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
    assert item.translated_docx_path != original.resolve()
    assert item.translated_docx_path.parent == session.download_dir / "_draft_attachments"
    assert item.translated_docx_path.name == original.name
    assert item.translated_docx_path.read_bytes() == b"translated-bytes"
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
        _offer_gmail_batch_reply_draft=lambda honorarios_docx: calls.__setitem__("offered", honorarios_docx),
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
            self.requested_path = requested_path
            self.auto_renamed = True

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
        _offer_gmail_batch_reply_draft=lambda honorarios_docx: calls.__setitem__("offered", honorarios_docx) or True,
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
    assert payload["finalization"]["actual_saved_path"].endswith("Requerimento_Honorarios_123-26.docx")
    assert payload["finalization"]["auto_renamed"] is True
    assert calls["offered"] == saved_path
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
    honorarios = tmp_path / "honorarios.docx"
    translated_one.write_bytes(b"one")
    translated_two.write_bytes(b"two")
    honorarios.write_bytes(b"three")
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
            attachments=tuple(kwargs["translated_docxs"]) + (kwargs["honorarios_docx"],),
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

    assert QtMainWindow._offer_gmail_batch_reply_draft(fake, honorarios) is True

    assert calls["request_kwargs"]["subject"] == "Court reply needed"
    assert calls["request_kwargs"]["reply_to_message_id"] == "msg-100"
    assert calls["request_kwargs"]["translated_docxs"] == (translated_one, translated_two)
    assert calls["request_kwargs"]["honorarios_docx"] == honorarios
    assert calls["state"]["status_text"] == "Gmail reply draft ready"
    assert calls["cleared"] is True
    assert opened == []
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["status"] == "draft_ready"
    assert payload["finalization"]["draft_created"] is True
    assert payload["finalization"]["final_attachment_basenames"] == [
        "staged-translated-1.docx",
        "staged-translated-2.docx",
        "honorarios.docx",
    ]


def test_offer_gmail_batch_reply_draft_keeps_batch_when_prereqs_are_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session = _build_gmail_batch_session(tmp_path, count=1)
    translated = tmp_path / "translated-1.docx"
    translated.write_bytes(b"one")
    honorarios = tmp_path / "honorarios.docx"
    honorarios.write_bytes(b"two")
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

    assert QtMainWindow._offer_gmail_batch_reply_draft(fake, honorarios) is False
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
        lambda **kwargs: tuple(kwargs["translated_docxs"]),
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

    assert QtMainWindow._offer_gmail_batch_reply_draft(fake, translated) is False

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
    honorarios = tmp_path / "honorarios.docx"
    honorarios.write_bytes(b"three")
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

    assert QtMainWindow._offer_gmail_batch_reply_draft(fake, honorarios) is False
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
        assert isinstance(joblog_dialog.court_email_combo, NoWheelComboBox) is False
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
        calls = {"saved": False, "forced": False}
        window._busy = True
        window._running = True
        window._resolve_busy_close_choice = lambda: "force_close"  # type: ignore[method-assign]
        monkeypatch.setattr(window, "_save_settings", lambda: calls.__setitem__("saved", True))
        monkeypatch.setattr(window, "_force_exit_app", lambda: calls.__setitem__("forced", True))
        event = QCloseEvent()
        window.closeEvent(event)
        assert event.isAccepted() is True
        assert calls == {"saved": True, "forced": True}
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


def test_new_run_resets_runtime_state() -> None:
    calls = {"details": None, "save_settings": False, "update_controls": False, "advisor_refreshed": False}
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
        _save_settings=lambda: calls.__setitem__("save_settings", True),
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
    assert calls == {"details": False, "save_settings": True, "update_controls": True, "advisor_refreshed": True}


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
        queue_manifest_edit=_FakeEdit("C:/tmp/queue.json"),
        queue_rerun_failed_only_check=_FakeCheck(False),
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
        "queue_manifest_path",
        "queue_rerun_failed_only",
    }
    assert set(captured.keys()) == expected
    assert fake._defaults["last_lang"] == "FR"
    assert fake._defaults["workers"] == 4


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


def test_on_form_changed_uses_scheduled_save() -> None:
    calls = {"scheduled": False, "page_count": False, "controls": False}
    fake = SimpleNamespace(
        _schedule_save_settings=lambda: calls.__setitem__("scheduled", True),
        _refresh_page_count=lambda: calls.__setitem__("page_count", True),
        _update_controls=lambda: calls.__setitem__("controls", True),
    )

    QtMainWindow._on_form_changed(fake)

    assert calls == {"scheduled": True, "page_count": True, "controls": True}


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
        _saved=False,
        _saved_result=None,
        _ensure_in_vocab=_ensure_in_vocab,
        accept=lambda: callback_state.__setitem__("accepted", True),
        _parse_float=None,
        _parse_optional_int=None,
        _parse_optional_float=None,
        _resolved_seed_docx_path=None,
        rate_edit=_FakeEdit("0.08"),
        expected_total_edit=_FakeEdit("80"),
        amount_paid_edit=_FakeEdit("0"),
        api_cost_edit=_FakeEdit("2.50"),
        profit_edit=_FakeEdit("77.50"),
        total_tokens_edit=_FakeEdit("5300"),
        estimated_api_cost_edit=_FakeEdit("2.90"),
        quality_risk_score_edit=_FakeEdit("0.44"),
        service_date_edit=_FakeEdit("2026-03-05"),
        case_entity_combo=_FakeCombo("Case Entity"),
        case_city_combo=_FakeCombo("Beja"),
        service_entity_combo=_FakeCombo("Case Entity"),
        service_city_combo=_FakeCombo("Beja"),
        service_same_check=_FakeCheck(False),
        job_type_combo=_FakeCombo("Translation"),
        case_number_edit=_FakeEdit("ABC-1"),
        court_email_combo=_FakeCombo("court@example.pt"),
        run_id_edit=_FakeEdit("run-override"),
        target_lang_edit=_FakeEdit("AR"),
    )
    fake._parse_float = QtSaveToJobLogDialog._parse_float.__get__(fake, QtSaveToJobLogDialog)
    fake._parse_optional_int = QtSaveToJobLogDialog._parse_optional_int.__get__(fake, QtSaveToJobLogDialog)
    fake._parse_optional_float = QtSaveToJobLogDialog._parse_optional_float.__get__(fake, QtSaveToJobLogDialog)
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
    assert saved_settings["ocr_mode"] == "auto"
    assert saved_settings["vocab_court_emails"] == ["court@example.pt"]
    assert fake._saved_result is not None
    assert fake._saved_result.row_id == 42
    assert fake._saved_result.translated_docx_path == (tmp_path / "translated.docx").resolve()


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
