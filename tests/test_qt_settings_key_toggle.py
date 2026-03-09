from __future__ import annotations

from types import SimpleNamespace

import legalpdf_translate.qt_gui.dialogs as dialogs
from legalpdf_translate.qt_gui.dialogs import QtSettingsDialog


class _FakeLineEdit:
    def __init__(self, text: str = "") -> None:
        self._text = text
        self._echo = dialogs.QLineEdit.EchoMode.Password
        self._placeholder = ""

    def text(self) -> str:
        return self._text

    def setText(self, value: str) -> None:
        self._text = value

    def clear(self) -> None:
        self._text = ""

    def echoMode(self):  # type: ignore[no-untyped-def]
        return self._echo

    def setEchoMode(self, mode) -> None:  # type: ignore[no-untyped-def]
        self._echo = mode

    def setPlaceholderText(self, value: str) -> None:
        self._placeholder = value

    def placeholderText(self) -> str:
        return self._placeholder


class _FakeButton:
    def __init__(self) -> None:
        self.text = ""
        self.enabled: bool | None = None

    def setText(self, text: str) -> None:
        self.text = text

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled


class _FakeLabel:
    def __init__(self) -> None:
        self.text = ""

    def setText(self, text: str) -> None:
        self.text = text


class _FakeCombo:
    def __init__(self, value: str) -> None:
        self._value = value

    def currentText(self) -> str:
        return self._value


def test_refresh_key_status_enables_show_button_when_key_exists(monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "get_openai_key", lambda: "stored-openai")
    monkeypatch.setattr(dialogs, "get_ocr_key", lambda: None)
    monkeypatch.setattr(dialogs.QMessageBox, "critical", lambda *args, **kwargs: None)

    fake = SimpleNamespace(
        openai_key_edit=_FakeLineEdit("x"),
        ocr_key_edit=_FakeLineEdit("y"),
        openai_toggle_btn=_FakeButton(),
        ocr_toggle_btn=_FakeButton(),
        openai_status_label=_FakeLabel(),
        ocr_status_label=_FakeLabel(),
        provider_summary_label=_FakeLabel(),
    )

    QtSettingsDialog._refresh_key_status(fake)

    assert fake.openai_status_label.text == "Stored"
    assert fake.ocr_status_label.text == "Not stored"
    assert fake.openai_toggle_btn.enabled is True
    assert fake.ocr_toggle_btn.enabled is False
    assert fake.ocr_key_edit.text() == ""


def test_toggle_openai_key_reveals_stored_value_then_hides(monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "get_openai_key", lambda: "stored-openai-key")
    monkeypatch.setattr(
        dialogs.QMessageBox,
        "question",
        lambda *args, **kwargs: dialogs.QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(dialogs.QMessageBox, "critical", lambda *args, **kwargs: None)
    monkeypatch.setattr(dialogs.QMessageBox, "warning", lambda *args, **kwargs: None)

    fake = SimpleNamespace(
        openai_key_edit=_FakeLineEdit(),
        openai_toggle_btn=_FakeButton(),
        _refresh_key_status=lambda: None,
    )

    QtSettingsDialog._toggle_openai_key(fake)
    assert fake.openai_key_edit.text() == "stored-openai-key"
    assert fake.openai_key_edit.echoMode() == dialogs.QLineEdit.EchoMode.Normal
    assert fake.openai_toggle_btn.text == "Hide"

    QtSettingsDialog._toggle_openai_key(fake)
    assert fake.openai_key_edit.echoMode() == dialogs.QLineEdit.EchoMode.Password
    assert fake.openai_toggle_btn.text == "Show"


def test_clear_openai_key_resets_mask_and_refreshes(monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "delete_openai_key", lambda: None)
    monkeypatch.setattr(dialogs.QMessageBox, "critical", lambda *args, **kwargs: None)

    calls = {"refresh": 0}
    fake = SimpleNamespace(
        openai_key_edit=_FakeLineEdit("temp"),
        openai_toggle_btn=_FakeButton(),
        _refresh_key_status=lambda: calls.__setitem__("refresh", calls["refresh"] + 1),
    )
    fake.openai_key_edit.setEchoMode(dialogs.QLineEdit.EchoMode.Normal)

    QtSettingsDialog._clear_openai_key(fake)

    assert fake.openai_key_edit.text() == ""
    assert fake.openai_key_edit.echoMode() == dialogs.QLineEdit.EchoMode.Password
    assert fake.openai_toggle_btn.text == "Show"
    assert calls["refresh"] == 1


def test_refresh_provider_controls_uses_selected_provider_defaults(monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "get_openai_key", lambda: "stored-openai")
    monkeypatch.setattr(dialogs, "get_ocr_key", lambda: "stored-ocr")

    fake = SimpleNamespace(
        ocr_provider_combo=_FakeCombo("gemini"),
        ocr_model_edit=_FakeLineEdit(""),
        ocr_env_edit=_FakeLineEdit(""),
        ocr_base_url_edit=_FakeLineEdit(""),
        provider_summary_label=_FakeLabel(),
    )

    QtSettingsDialog._refresh_provider_controls(fake)

    assert fake.ocr_model_edit.placeholderText() == "gemini-3.1-flash-lite-preview"
    assert fake.ocr_env_edit.placeholderText() == "GEMINI_API_KEY"
    assert "OCR provider: gemini" in fake.provider_summary_label.text
