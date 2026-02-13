from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import legalpdf_translate.qt_gui.dialogs as dialogs
from legalpdf_translate.qt_gui.dialogs import QtSettingsDialog


class _FakeLineEdit:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def text(self) -> str:
        return self._text

    def setText(self, value: str) -> None:
        self._text = value

    def clear(self) -> None:
        self._text = ""


def _fake_settings_with_glossary(text: str) -> SimpleNamespace:
    fake = SimpleNamespace(glossary_file_edit=_FakeLineEdit(text))
    fake._resolve_glossary_path = lambda: QtSettingsDialog._resolve_glossary_path(fake)
    fake._load_glossary_editor_text = lambda p: QtSettingsDialog._load_glossary_editor_text(fake, p)
    fake._default_glossary_save_path = lambda: QtSettingsDialog._default_glossary_save_path(fake)
    return fake


def test_view_edit_loads_builtin_when_path_empty(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _DummyEditor:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.saved_path = None

        def exec(self):  # type: ignore[no-untyped-def]
            return dialogs.QDialog.DialogCode.Rejected

    monkeypatch.setattr(dialogs, "QtGlossaryEditorDialog", _DummyEditor)
    monkeypatch.setattr(dialogs.QMessageBox, "critical", lambda *args, **kwargs: None)

    fake = _fake_settings_with_glossary("")
    QtSettingsDialog._open_glossary_editor(fake)

    assert captured["initial_path"] is None
    assert captured["source_label"] == "Built-in glossary"
    assert '"version": 1' in str(captured["initial_text"])


def test_view_edit_loads_file_content_when_path_set(tmp_path: Path, monkeypatch) -> None:
    glossary_path = tmp_path / "custom_glossary.json"
    raw = '{"version": 1, "rules": []}'
    glossary_path.write_text(raw, encoding="utf-8")
    captured: dict[str, object] = {}

    class _DummyEditor:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.saved_path = None

        def exec(self):  # type: ignore[no-untyped-def]
            return dialogs.QDialog.DialogCode.Rejected

    monkeypatch.setattr(dialogs, "QtGlossaryEditorDialog", _DummyEditor)
    monkeypatch.setattr(dialogs.QMessageBox, "critical", lambda *args, **kwargs: None)

    fake = _fake_settings_with_glossary(str(glossary_path))
    QtSettingsDialog._open_glossary_editor(fake)

    assert captured["initial_path"] == glossary_path.resolve()
    assert captured["source_label"] == str(glossary_path.resolve())
    assert captured["initial_text"] == raw


def test_validate_helper_accepts_and_rejects_json() -> None:
    valid = '{"version": 1, "rules": []}'
    assert dialogs.QtGlossaryEditorDialog._validated_text(valid, source="editor") == valid

    with pytest.raises(ValueError, match="Invalid glossary JSON"):
        dialogs.QtGlossaryEditorDialog._validated_text("{bad", source="editor")


def test_save_without_existing_path_uses_default_appdata_and_updates_field(
    tmp_path: Path, monkeypatch
) -> None:
    captured: dict[str, object] = {}
    expected = (tmp_path / "glossary.json").resolve()

    class _DummyEditor:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            self.saved_path = kwargs["default_save_path"]

        def exec(self):  # type: ignore[no-untyped-def]
            return dialogs.QDialog.DialogCode.Accepted

    monkeypatch.setattr(dialogs, "QtGlossaryEditorDialog", _DummyEditor)
    monkeypatch.setattr(dialogs, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(dialogs.QMessageBox, "critical", lambda *args, **kwargs: None)

    fake = _fake_settings_with_glossary("")
    QtSettingsDialog._open_glossary_editor(fake)

    assert captured["default_save_path"] == expected
    assert fake.glossary_file_edit.text() == str(expected)


def test_save_as_updates_glossary_file_path(tmp_path: Path, monkeypatch) -> None:
    selected = (tmp_path / "chosen_glossary.json").resolve()

    class _DummyEditor:
        def __init__(self, **kwargs) -> None:
            self.saved_path = selected

        def exec(self):  # type: ignore[no-untyped-def]
            return dialogs.QDialog.DialogCode.Accepted

    monkeypatch.setattr(dialogs, "QtGlossaryEditorDialog", _DummyEditor)
    monkeypatch.setattr(dialogs.QMessageBox, "critical", lambda *args, **kwargs: None)

    fake = _fake_settings_with_glossary("")
    QtSettingsDialog._open_glossary_editor(fake)

    assert fake.glossary_file_edit.text() == str(selected)


def test_write_text_atomically_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "glossary.json"
    payload = '{"version": 1, "rules": []}'

    written = dialogs.QtGlossaryEditorDialog._write_text_atomically(target, payload)

    assert written == target.resolve()
    assert target.read_text(encoding="utf-8") == payload


def test_use_builtin_clears_custom_path(monkeypatch) -> None:
    monkeypatch.setattr(
        dialogs.QMessageBox,
        "question",
        lambda *args, **kwargs: dialogs.QMessageBox.StandardButton.Ok,
    )
    monkeypatch.setattr(dialogs.QMessageBox, "information", lambda *args, **kwargs: None)

    fake = SimpleNamespace(glossary_file_edit=_FakeLineEdit("C:/temp/custom.json"))
    QtSettingsDialog._use_builtin_glossary(fake)

    assert fake.glossary_file_edit.text() == ""

