from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from legalpdf_translate.qt_gui.app_window import QtMainWindow


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

    def currentText(self) -> str:
        return self._value


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
    calls = {"details": None, "save_settings": False, "update_controls": False}
    fake = SimpleNamespace(
        _busy=False,
        _last_summary=object(),
        _last_run_report_path=object(),
        _last_output_docx=object(),
        _last_run_config=object(),
        _last_joblog_seed=object(),
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
    assert calls == {"details": False, "save_settings": True, "update_controls": True}


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
        _resolve_report_run_dir=lambda: Path("C:/tmp/run"),
        translate_btn=_FakeButton(),
        analyze_btn=_FakeButton(),
        cancel_btn=_FakeButton(),
        new_btn=_FakeButton(),
        partial_btn=_FakeButton(),
        rebuild_btn=_FakeButton(),
        open_btn=_FakeButton(),
        report_btn=report_button,
        save_joblog_btn=_FakeButton(),
        open_joblog_btn=_FakeButton(),
        _simple_mode=False,
        _set_menu_enabled=lambda key, enabled: menu_calls.__setitem__(key, enabled),
    )

    QtMainWindow._update_controls(fake)
    assert report_button.enabled is True

    fake._busy = False
    fake._running = False
    QtMainWindow._update_controls(fake)
    assert report_button.enabled is True

    fake._resolve_report_run_dir = lambda: None
    QtMainWindow._update_controls(fake)
    assert report_button.enabled is False
