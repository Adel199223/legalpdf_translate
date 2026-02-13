from __future__ import annotations

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
        self.rows.insert(row, [None, None, None])

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


def test_on_glossary_language_changed_switches_table_data() -> None:
    loaded: list[list[GlossaryEntry]] = []
    fake = SimpleNamespace(
        _glossary_current_lang="EN",
        _glossaries_by_lang={
            "EN": [GlossaryEntry(source="a", target="b", match="exact")],
            "AR": [GlossaryEntry(source="c", target="d", match="contains")],
        },
        _save_current_glossary_language_rows=lambda: None,
        _set_glossary_table_rows=lambda rows: loaded.append(rows),
    )

    QtSettingsDialog._on_glossary_language_changed(fake, "AR")

    assert fake._glossary_current_lang == "AR"
    assert loaded == [[GlossaryEntry(source="c", target="d", match="contains")]]


def test_save_current_glossary_language_rows_updates_language_bucket() -> None:
    expected = [GlossaryEntry(source="foo", target="bar", match="exact")]
    fake = SimpleNamespace(
        _glossary_current_lang="AR",
        _glossaries_by_lang={"EN": [], "FR": [], "AR": []},
        _read_glossary_table_rows=lambda: expected,
    )

    QtSettingsDialog._save_current_glossary_language_rows(fake)

    assert fake._glossaries_by_lang["AR"] == expected


def test_read_glossary_table_rows_filters_invalid_and_dedupes_rows() -> None:
    table = _FakeTable()
    table.rows = [
        [_FakeItem("صرف الأتعاب"), _FakeItem("دفع الأتعاب المستحقة"), _FakeMatchCombo("contains")],
        [_FakeItem(""), _FakeItem("x"), _FakeMatchCombo("exact")],
        [_FakeItem("صرف الأتعاب"), _FakeItem("دفع الأتعاب المستحقة"), _FakeMatchCombo("contains")],
    ]
    fake = SimpleNamespace(
        glossary_table=table,
        _glossary_current_lang="AR",
        _glossary_match_value=lambda combo: QtSettingsDialog._glossary_match_value(SimpleNamespace(), combo),
    )

    rows = QtSettingsDialog._read_glossary_table_rows(fake)

    assert rows == [GlossaryEntry(source="صرف الأتعاب", target="دفع الأتعاب المستحقة", match="contains")]


def test_add_and_remove_glossary_rows(monkeypatch) -> None:
    table = _FakeTable()
    fake = SimpleNamespace(
        glossary_table=table,
        _new_glossary_match_combo=lambda _match="exact": _FakeMatchCombo("exact"),
    )

    monkeypatch.setattr(dialogs, "QTableWidgetItem", _FakeItem)

    QtSettingsDialog._add_glossary_row(fake)
    assert table.rowCount() == 1
    assert isinstance(table.item(0, 0), _FakeItem)
    assert table.item(0, 0).text() == ""

    table.set_selected_rows([0])
    QtSettingsDialog._remove_selected_glossary_rows(fake)
    assert table.rowCount() == 0
