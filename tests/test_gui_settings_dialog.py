from __future__ import annotations

import legalpdf_translate.gui_settings_dialog as settings_dialog
from legalpdf_translate.gui_settings_dialog import GuiSettingsDialog


class _FakeWidget:
    def __init__(self, **initial: object) -> None:
        self.values: dict[str, object] = dict(initial)

    def configure(self, **kwargs: object) -> None:
        self.values.update(kwargs)

    def cget(self, key: str) -> object:
        return self.values.get(key, "")


class _FakeVar:
    def __init__(self, value: object) -> None:
        self._value = value

    def get(self) -> object:
        return self._value

    def set(self, value: object) -> None:
        self._value = value


class _FakeApp:
    def __init__(self) -> None:
        self.settings_window = object()


def _make_dialog_stub() -> GuiSettingsDialog:
    dialog = GuiSettingsDialog.__new__(GuiSettingsDialog)
    dialog.openai_entry = _FakeWidget(show="*")
    dialog.openai_toggle = _FakeWidget(text="Show")
    dialog.ocr_entry = _FakeWidget(show="*")
    dialog.ocr_toggle = _FakeWidget(text="Show")
    dialog.openai_status_var = _FakeVar("Not stored")
    dialog.ocr_status_var = _FakeVar("Not stored")
    dialog.provider_summary_var = _FakeVar("")
    dialog._app = _FakeApp()
    dialog._destroyed = False
    dialog.destroy = lambda: setattr(dialog, "_destroyed", True)  # type: ignore[method-assign]
    return dialog


def test_settings_dialog_show_hide_toggles_for_both_keys() -> None:
    dialog = _make_dialog_stub()

    dialog._toggle_openai_key()
    assert dialog.openai_entry.values.get("show") == ""
    assert dialog.openai_toggle.values.get("text") == "Hide"
    dialog._toggle_openai_key()
    assert dialog.openai_entry.values.get("show") == "*"
    assert dialog.openai_toggle.values.get("text") == "Show"

    dialog._toggle_ocr_key()
    assert dialog.ocr_entry.values.get("show") == ""
    assert dialog.ocr_toggle.values.get("text") == "Hide"
    dialog._toggle_ocr_key()
    assert dialog.ocr_entry.values.get("show") == "*"
    assert dialog.ocr_toggle.values.get("text") == "Show"


def test_settings_dialog_refresh_status_reads_store_state(monkeypatch) -> None:
    dialog = _make_dialog_stub()
    monkeypatch.setattr(settings_dialog, "get_openai_key", lambda: "stored-openai")
    monkeypatch.setattr(settings_dialog, "get_ocr_key", lambda: None)

    dialog._refresh_key_status()

    assert dialog.openai_status_var.get() == "Stored"
    assert dialog.ocr_status_var.get() == "Not stored"
    assert "OpenAI credentials present" in str(dialog.provider_summary_var.get())


def test_settings_dialog_cancel_resets_window_handle() -> None:
    dialog = _make_dialog_stub()

    dialog._cancel()

    assert dialog._app.settings_window is None
    assert dialog._destroyed is True
