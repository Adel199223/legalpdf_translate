from __future__ import annotations

import tkinter as tk

import legalpdf_translate.gui_app as gui_app_module
from legalpdf_translate.gui_app import LegalPDFTranslateApp


class _FakeWidget:
    def __init__(self) -> None:
        self.state: str | None = None
        self.values: dict[str, object] = {}

    def configure(self, **kwargs: object) -> None:
        self.values.update(kwargs)
        if "state" in kwargs:
            self.state = str(kwargs["state"])


class _FakeVar:
    def __init__(self, value: object) -> None:
        self._value = value

    def get(self) -> object:
        return self._value

    def set(self, value: object) -> None:
        self._value = value


def _make_app_stub() -> LegalPDFTranslateApp:
    app = LegalPDFTranslateApp.__new__(LegalPDFTranslateApp)
    app._busy = False
    app._running_translation = False
    app._can_export_partial = False
    app.last_output_docx = None
    app.last_joblog_seed = None
    app.last_run_report_path = None

    app._config_control_states = [
        (_FakeWidget(), tk.NORMAL),
        (_FakeWidget(), "readonly"),
    ]
    app.context_text = _FakeWidget()
    app.translate_btn = _FakeWidget()
    app.analyze_btn = _FakeWidget()
    app.cancel_btn = _FakeWidget()
    app.new_run_btn = _FakeWidget()
    app.export_partial_btn = _FakeWidget()
    app.rebuild_btn = _FakeWidget()
    app.open_outdir_btn = _FakeWidget()
    app.run_report_btn = _FakeWidget()
    app.save_joblog_btn = _FakeWidget()
    app.open_joblog_btn = _FakeWidget()

    app._can_start_translation = lambda: True  # type: ignore[method-assign]
    app._has_rebuildable_pages = lambda: False  # type: ignore[method-assign]
    return app


def test_state_transition_idle_running_finished_idle() -> None:
    app = _make_app_stub()

    app._set_busy(True, translation=True)
    assert app._busy is True
    assert app._running_translation is True
    assert app.cancel_btn.state == tk.NORMAL
    assert app.translate_btn.state == tk.DISABLED
    assert app.context_text.state == tk.DISABLED
    for widget, _ in app._config_control_states:
        assert widget.state == tk.DISABLED

    app._set_busy(False, translation=False)
    assert app._busy is False
    assert app._running_translation is False
    assert app.cancel_btn.state == tk.DISABLED
    assert app.translate_btn.state == tk.NORMAL
    assert app.context_text.state == tk.NORMAL
    assert app._config_control_states[0][0].state == tk.NORMAL
    assert app._config_control_states[1][0].state == "readonly"


def test_new_run_clears_runtime_state_without_restart() -> None:
    app = _make_app_stub()
    app._busy = False
    app.last_summary = object()
    app.last_output_docx = object()
    app.last_joblog_seed = object()
    app._can_export_partial = True
    app.workflow = object()
    app.worker = object()
    app.progress = _FakeWidget()
    app.status_var = _FakeVar("Running")
    app._details_expanded = True

    calls: dict[str, object] = {}

    def _new_queue() -> object:
        calls["queue"] = True
        app.queue = "new-queue"
        return app.queue

    def _clear_log() -> None:
        calls["clear_log"] = True

    def _set_details_expanded(expanded: bool) -> None:
        calls["details"] = expanded

    def _persist_gui_settings() -> None:
        calls["persist"] = True

    def _reset_live_counters() -> None:
        calls["counters"] = True

    app._new_queue = _new_queue  # type: ignore[method-assign]
    app._clear_log = _clear_log  # type: ignore[method-assign]
    app._set_details_expanded = _set_details_expanded  # type: ignore[method-assign]
    app._persist_gui_settings = _persist_gui_settings  # type: ignore[method-assign]
    app._reset_live_counters = _reset_live_counters  # type: ignore[method-assign]

    app._new_run()

    assert app.last_summary is None
    assert app.last_output_docx is None
    assert app.last_joblog_seed is None
    assert app._can_export_partial is False
    assert app.workflow is None
    assert app.worker is None
    assert app.progress.values.get("value") == 0
    assert app.status_var.get() == "Idle"
    assert calls == {"queue": True, "counters": True, "clear_log": True, "details": False, "persist": True}


def test_on_close_blocked_while_busy(monkeypatch) -> None:
    calls: dict[str, object] = {}

    class _FakeWin:
        def winfo_exists(self) -> bool:
            return True

        def destroy(self) -> None:
            calls["settings_destroy"] = True

    class _FakeMaster:
        def destroy(self) -> None:
            calls["master_destroy"] = True

    app = LegalPDFTranslateApp.__new__(LegalPDFTranslateApp)
    app._busy = True
    app.settings_window = _FakeWin()
    app.master = _FakeMaster()
    app._persist_gui_settings = lambda: calls.__setitem__("persist", True)  # type: ignore[method-assign]

    monkeypatch.setattr(
        gui_app_module.messagebox,
        "showwarning",
        lambda title, message: calls.__setitem__("warning", (title, message)),
    )

    app._on_close()

    assert "warning" in calls
    assert "persist" not in calls
    assert "settings_destroy" not in calls
    assert "master_destroy" not in calls


def test_settings_persist_is_debounced() -> None:
    calls: dict[str, object] = {}
    scheduled: dict[str, object] = {}

    app = LegalPDFTranslateApp.__new__(LegalPDFTranslateApp)
    app._settings_persist_after_id = None

    def _after(delay_ms: int, callback):  # type: ignore[no-untyped-def]
        calls["delay"] = delay_ms
        scheduled["callback"] = callback
        return "after-id-1"

    def _after_cancel(after_id: str) -> None:
        calls["cancelled"] = after_id

    app.after = _after  # type: ignore[method-assign]
    app.after_cancel = _after_cancel  # type: ignore[method-assign]
    app._persist_gui_settings = lambda: calls.__setitem__("persisted", True)  # type: ignore[method-assign]

    app._schedule_settings_persist()
    first_id = app._settings_persist_after_id
    app._schedule_settings_persist()

    assert first_id == "after-id-1"
    assert calls["cancelled"] == "after-id-1"
    assert calls["delay"] == 250

    # Simulate Tk callback execution.
    callback = scheduled["callback"]
    callback()
    assert app._settings_persist_after_id is None
    assert calls["persisted"] is True
