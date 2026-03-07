from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QBoxLayout

from legalpdf_translate.build_identity import RuntimeBuildIdentity
from legalpdf_translate.docx_writer import assemble_docx
from legalpdf_translate.qt_gui.app_window import QtMainWindow
from legalpdf_translate.qt_gui.dialogs import (
    JobLogSeed,
    QtSaveToJobLogDialog,
    QtSettingsDialog,
    build_seed_from_run,
    count_words_from_docx,
    count_words_from_output_artifacts,
)
from legalpdf_translate.qt_gui.guarded_inputs import NoWheelComboBox, NoWheelSpinBox
from legalpdf_translate.types import TargetLang
from legalpdf_translate.types import (
    EffortPolicy,
    ImageMode,
    OcrEnginePolicy,
    OcrMode,
    RunConfig,
    RunSummary,
)


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
    finally:
        settings_dialog.close()
        settings_dialog.deleteLater()
        if owns_app:
            app.quit()


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
        assert "Request type: text_only" in captured["text"]
        assert "Request deadline: 480s" in captured["text"]
        assert "Elapsed before failure: 479.8s" in captured["text"]
        assert "Failure class: APITimeoutError" in captured["text"]
        assert "Cancel requested before failure: yes" in captured["text"]
        log_text = window.log_text.toPlainText()
        assert "Failure context: request_type=text_only deadline=480.0s elapsed=479.800s cancel_requested=yes" in log_text
        assert "Failure classification: suspected_cause=transport_instability halt_reason=cancelled_after_request_timeout exception_class=APITimeoutError" in log_text
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

        def _build_config() -> RunConfig:
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
        monkeypatch.setattr(window, "_warn_ocr_api_only_if_needed", lambda config: None)
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
        lambda _conn, payload: captured_payload.update(payload),
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
        _ensure_in_vocab=_ensure_in_vocab,
        accept=lambda: callback_state.__setitem__("accepted", True),
        _parse_float=None,
        _parse_optional_int=None,
        _parse_optional_float=None,
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
