from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

if os.name != "nt" and "DISPLAY" not in os.environ:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QBoxLayout

from legalpdf_translate.qt_gui.app_window import QtMainWindow
from legalpdf_translate.qt_gui.dialogs import JobLogSeed, QtSaveToJobLogDialog


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

    def value(self) -> int:
        return self._value


class _FakeCheck:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


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
        },
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.build_seed_from_run",
        _fake_seed_from_run,
    )
    monkeypatch.setattr(
        "legalpdf_translate.qt_gui.app_window.extract_pdf_header_metadata",
        lambda *_args, **_kwargs: SimpleNamespace(case_entity="", case_city="", case_number=""),
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
    )

    QtMainWindow._prepare_joblog_seed(fake, summary)

    assert fake._last_joblog_seed is not None
    assert fake._last_joblog_seed.run_id == "run-20260305-120000"
    assert fake._last_joblog_seed.target_lang == "FR"
    assert fake._last_joblog_seed.total_tokens == 8123
    assert fake._last_joblog_seed.estimated_api_cost == 4.56
    assert fake._last_joblog_seed.quality_risk_score == 0.37
    assert fake._last_joblog_seed.api_cost == 4.56


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

    fake = SimpleNamespace(
        _seed=seed,
        _db_path=tmp_path / "joblog.sqlite3",
        _settings={
            "vocab_case_entities": [],
            "vocab_service_entities": [],
            "vocab_cities": [],
            "vocab_job_types": [],
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
        },
        _on_saved=lambda: callback_state.__setitem__("called", True),
        _saved=False,
        _ensure_in_vocab=lambda _key, _value: None,
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
    assert callback_state == {"called": True, "accepted": True}
    assert saved_settings["ocr_mode"] == "auto"
