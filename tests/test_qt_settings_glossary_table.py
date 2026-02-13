from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import legalpdf_translate.qt_gui.dialogs as dialogs
from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.qt_gui.dialogs import QtSettingsDialog


class _FakeItem:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _FakeMatchCombo:
    def __init__(self, value: str = "exact") -> None:
        self._value = value

    def currentData(self):  # type: ignore[no-untyped-def]
        return self._value

    def currentText(self) -> str:
        return "Contains" if self._value == "contains" else "Exact"


class _FakeSourceLangCombo:
    def __init__(self, value: str = "AUTO") -> None:
        self._value = value

    def currentData(self):  # type: ignore[no-untyped-def]
        return self._value

    def currentText(self) -> str:
        return self._value


class _FakeTierCombo:
    def __init__(self, value: int = 2) -> None:
        self._value = value

    def currentData(self):  # type: ignore[no-untyped-def]
        return self._value

    def currentText(self) -> str:
        return f"T{self._value}"


class _FakeIndex:
    def __init__(self, row: int) -> None:
        self._row = row

    def row(self) -> int:
        return self._row


class _FakeTable:
    def __init__(self) -> None:
        self.rows: list[list[object | None]] = []
        self._selected_rows: list[int] = []

    def rowCount(self) -> int:
        return len(self.rows)

    def setRowCount(self, value: int) -> None:
        if value == 0:
            self.rows = []

    def insertRow(self, row: int) -> None:
        self.rows.insert(row, [None, None, None, None, None])

    def setItem(self, row: int, column: int, item: object) -> None:
        self.rows[row][column] = item

    def item(self, row: int, column: int):  # type: ignore[no-untyped-def]
        return self.rows[row][column]

    def setCellWidget(self, row: int, column: int, widget: object) -> None:
        self.rows[row][column] = widget

    def cellWidget(self, row: int, column: int):  # type: ignore[no-untyped-def]
        return self.rows[row][column]

    def selectedIndexes(self):  # type: ignore[no-untyped-def]
        return [_FakeIndex(row) for row in self._selected_rows]

    def removeRow(self, row: int) -> None:
        del self.rows[row]

    def set_selected_rows(self, rows: list[int]) -> None:
        self._selected_rows = rows


class _FakeLabel:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, text: str) -> None:
        self.value = text


class _FakeComboNoSetCurrentData:
    def __init__(self) -> None:
        self.items: list[tuple[str, object]] = []
        self.current_index: int = -1

    def addItem(self, text: str, data: object = None) -> None:  # type: ignore[assignment]
        self.items.append((text, data))

    def findData(self, data: object) -> int:
        for idx, (_text, item_data) in enumerate(self.items):
            if item_data == data:
                return idx
        return -1

    def setCurrentIndex(self, index: int) -> None:
        self.current_index = index

    def currentData(self):  # type: ignore[no-untyped-def]
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index][1]
        return None

    def currentText(self) -> str:
        if 0 <= self.current_index < len(self.items):
            return self.items[self.current_index][0]
        return ""


class _FakeComboFindDataMiss(_FakeComboNoSetCurrentData):
    def findData(self, data: object) -> int:  # noqa: ARG002
        return -1


def test_visible_glossary_rows_filters_by_selected_tier_and_search() -> None:
    fake = SimpleNamespace(
        _glossaries_by_lang={
            "AR": [
                GlossaryEntry("foo long", "x", "exact", "ANY", 1),
                GlossaryEntry("bar", "y", "exact", "ANY", 2),
                GlossaryEntry("foo short", "z", "exact", "ANY", 1),
            ]
        },
        _glossary_selected_tier=1,
        _glossary_search_text="foo",
    )

    rows = QtSettingsDialog._visible_glossary_rows(fake, "AR")

    assert [entry.source_text for entry in rows] == ["foo long", "foo short"]


def test_on_glossary_language_changed_switches_table_data() -> None:
    refreshed: list[str] = []
    active_tiers_set: list[list[int]] = []
    fake = SimpleNamespace(
        _glossary_current_lang="EN",
        _enabled_glossary_tiers_by_lang={"EN": [1, 2], "AR": [1]},
        _save_current_glossary_language_rows=lambda: None,
        _set_active_tier_checks=lambda tiers: active_tiers_set.append(tiers),
        _refresh_glossary_table_view=lambda: refreshed.append("yes"),
    )

    QtSettingsDialog._on_glossary_language_changed(fake, "AR")

    assert fake._glossary_current_lang == "AR"
    assert active_tiers_set == [[1]]
    assert refreshed == ["yes"]


def test_save_current_glossary_language_rows_merges_visible_rows_and_preserves_hidden() -> None:
    existing_visible = GlossaryEntry("visible old", "old", "exact", "ANY", 1)
    existing_hidden = GlossaryEntry("hidden row", "keep", "exact", "ANY", 3)
    updated_visible = GlossaryEntry("visible new", "new", "exact", "ANY", 1)
    fake = SimpleNamespace(
        _glossary_current_lang="AR",
        _glossaries_by_lang={"AR": [existing_visible, existing_hidden]},
        _glossary_view_keys=[("visible old", "old", "exact", "ANY", 1)],
        _enabled_glossary_tiers_by_lang={"AR": [1, 2]},
        _read_glossary_table_rows=lambda: [updated_visible],
        _read_active_tier_checks=lambda: [1, 2],
        _glossary_entry_key=lambda entry: (entry.source_text, entry.preferred_translation, entry.match_mode, entry.source_lang, entry.tier),
    )

    QtSettingsDialog._save_current_glossary_language_rows(fake)

    assert fake._glossaries_by_lang["AR"] == [existing_hidden, updated_visible]
    assert fake._enabled_glossary_tiers_by_lang["AR"] == [1, 2]


def test_read_glossary_table_rows_filters_invalid_and_dedupes_rows() -> None:
    table = _FakeTable()
    table.rows = [
        [_FakeItem("honorários devidos"), _FakeItem("دفع الأتعاب المستحقة"), _FakeMatchCombo("contains"), _FakeSourceLangCombo("PT"), _FakeTierCombo(1)],
        [_FakeItem(""), _FakeItem("x"), _FakeMatchCombo("exact"), _FakeSourceLangCombo("AUTO"), _FakeTierCombo(2)],
        [_FakeItem("honorários devidos"), _FakeItem("دفع الأتعاب المستحقة"), _FakeMatchCombo("contains"), _FakeSourceLangCombo("PT"), _FakeTierCombo(1)],
    ]
    fake = SimpleNamespace(
        glossary_table=table,
        _glossary_current_lang="AR",
        _glossary_match_value=lambda combo: QtSettingsDialog._glossary_match_value(SimpleNamespace(), combo),
        _glossary_source_lang_value=lambda combo: QtSettingsDialog._glossary_source_lang_value(SimpleNamespace(), combo),
        _glossary_tier_value=lambda combo: QtSettingsDialog._glossary_tier_value(SimpleNamespace(), combo),
    )

    rows = QtSettingsDialog._read_glossary_table_rows(fake)

    assert rows == [
        GlossaryEntry(
            source_text="honorários devidos",
            preferred_translation="دفع الأتعاب المستحقة",
            match_mode="contains",
            source_lang="PT",
            tier=1,
        )
    ]


def test_add_and_remove_glossary_rows(monkeypatch) -> None:
    table = _FakeTable()
    fake = SimpleNamespace(
        glossary_table=table,
        _glossary_selected_tier=3,
        _new_glossary_match_combo=lambda _match="exact": _FakeMatchCombo("exact"),
        _new_glossary_source_lang_combo=lambda _source_lang="AUTO": _FakeSourceLangCombo("AUTO"),
        _new_glossary_tier_combo=lambda _tier=2: _FakeTierCombo(3),
        _update_glossary_warning_label=lambda _rows: None,
        _read_glossary_table_rows=lambda: [],
    )

    monkeypatch.setattr(dialogs, "QTableWidgetItem", _FakeItem)

    QtSettingsDialog._add_glossary_row(fake)
    assert table.rowCount() == 1
    assert isinstance(table.item(0, 0), _FakeItem)
    assert table.item(0, 0).text() == ""

    table.set_selected_rows([0])
    QtSettingsDialog._remove_selected_glossary_rows(fake)
    assert table.rowCount() == 0


def test_update_glossary_warning_label_sets_guidance() -> None:
    fake = SimpleNamespace(glossary_warning_label=_FakeLabel())
    rows = [
        GlossaryEntry("abc", "x", "contains", "ANY", 2),
        GlossaryEntry("word", "y", "exact", "ANY", 1),
    ]

    QtSettingsDialog._update_glossary_warning_label(fake, rows)

    assert "Contains on short phrases may overmatch." in fake.glossary_warning_label.value
    assert "Tier 1-2 should be reserved for high-impact phrases" in fake.glossary_warning_label.value


def test_new_glossary_tier_combo_falls_back_when_set_current_data_missing(monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "QComboBox", _FakeComboNoSetCurrentData)

    combo = QtSettingsDialog._new_glossary_tier_combo(SimpleNamespace(), 4)

    assert isinstance(combo, _FakeComboNoSetCurrentData)
    assert combo.currentData() == 4
    assert combo.currentText() == "T4"


def test_new_glossary_tier_combo_uses_first_item_when_find_data_misses(monkeypatch) -> None:
    monkeypatch.setattr(dialogs, "QComboBox", _FakeComboFindDataMiss)

    combo = QtSettingsDialog._new_glossary_tier_combo(SimpleNamespace(), 4)

    assert isinstance(combo, _FakeComboFindDataMiss)
    assert combo.currentData() == 1
    assert combo.currentText() == "T1"


def test_export_consistency_glossary_markdown_writes_content_only_markdown(tmp_path: Path, monkeypatch) -> None:
    output_path = (tmp_path / "ai_glossary.md").resolve()
    monkeypatch.setattr(dialogs, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(
        dialogs.QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(output_path), "Markdown (*.md)"),
    )
    monkeypatch.setattr(dialogs.QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(dialogs.QMessageBox, "critical", lambda *args, **kwargs: None)

    fake = SimpleNamespace(
        _save_current_glossary_language_rows=lambda: None,
        _glossaries_by_lang={
            "EN": [],
            "FR": [],
            "AR": [GlossaryEntry("acusação", "الاتهام", "exact", "PT", 1)],
        },
        _enabled_glossary_tiers_by_lang={"EN": [1, 2], "FR": [1], "AR": [1, 2]},
    )

    QtSettingsDialog._export_consistency_glossary_markdown(fake)

    content = output_path.read_text(encoding="utf-8")
    assert content.startswith("# AI Glossary")
    assert "## AR" in content
    assert "Enabled tiers: T1, T2" in content
    assert "| Source phrase (PDF text) | Preferred translation | Match | Source lang | Tier |" in content
    assert "acusação" in content
