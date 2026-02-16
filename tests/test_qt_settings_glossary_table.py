from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import legalpdf_translate.qt_gui.dialogs as dialogs
from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.qt_gui.dialogs import QtSettingsDialog


class _FakeSignal:
    """No-op signal stand-in for currentIndexChanged.connect()."""

    def connect(self, _slot: object) -> None:  # noqa: ARG002
        pass


class _FakeItem:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _FakeMatchCombo:
    def __init__(self, value: str = "exact") -> None:
        self._value = value
        self.currentIndexChanged = _FakeSignal()

    def setObjectName(self, _name: str) -> None:  # noqa: ARG002
        pass

    def currentData(self):  # type: ignore[no-untyped-def]
        return self._value

    def currentText(self) -> str:
        return "Contains" if self._value == "contains" else "Exact"


class _FakeSourceLangCombo:
    def __init__(self, value: str = "AUTO") -> None:
        self._value = value
        self.currentIndexChanged = _FakeSignal()

    def setObjectName(self, _name: str) -> None:  # noqa: ARG002
        pass

    def currentData(self):  # type: ignore[no-untyped-def]
        return self._value

    def currentText(self) -> str:
        return self._value


class _FakeTierCombo:
    def __init__(self, value: int = 2) -> None:
        self._value = value
        self.currentIndexChanged = _FakeSignal()

    def setObjectName(self, _name: str) -> None:  # noqa: ARG002
        pass

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

    def scrollToItem(self, _item: object) -> None:  # noqa: ARG002
        pass

    def setCurrentCell(self, _row: int, _col: int) -> None:  # noqa: ARG002
        pass

    def editItem(self, _item: object) -> None:  # noqa: ARG002
        pass

    def set_selected_rows(self, rows: list[int]) -> None:
        self._selected_rows = rows


class _FakeLabel:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, text: str) -> None:
        self.value = text


class _FakeSizeAdjustPolicy:
    AdjustToContents = 0


class _FakeComboNoSetCurrentData:
    SizeAdjustPolicy = _FakeSizeAdjustPolicy

    def __init__(self) -> None:
        self.items: list[tuple[str, object]] = []
        self.current_index: int = -1

    def setObjectName(self, _name: str) -> None:  # noqa: ARG002
        pass

    def setSizeAdjustPolicy(self, _policy: object) -> None:  # noqa: ARG002
        pass

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
        _glossary_populating=False,
        _glossary_auto_save_timer=None,
        _new_glossary_match_combo=lambda _match="exact": _FakeMatchCombo("exact"),
        _new_glossary_source_lang_combo=lambda _source_lang="PT": _FakeSourceLangCombo(_source_lang),
        _new_glossary_tier_combo=lambda _tier=2: _FakeTierCombo(3),
        _update_glossary_warning_label=lambda _rows: None,
        _read_glossary_table_rows=lambda: [],
        _schedule_glossary_auto_save=lambda *_args: None,
    )

    monkeypatch.setattr(dialogs, "QTableWidgetItem", _FakeItem)

    QtSettingsDialog._add_glossary_row(fake)
    assert table.rowCount() == 1
    assert isinstance(table.item(0, 0), _FakeItem)
    assert table.item(0, 0).text() == ""
    # New row should default source lang to PT
    assert table.cellWidget(0, 3)._value == "PT"

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


def test_add_glossary_row_defaults_source_lang_to_pt(monkeypatch) -> None:
    table = _FakeTable()
    created_combos: list[_FakeSourceLangCombo] = []

    def _track_combo(lang: str = "PT") -> _FakeSourceLangCombo:
        combo = _FakeSourceLangCombo(lang)
        created_combos.append(combo)
        return combo

    fake = SimpleNamespace(
        glossary_table=table,
        _glossary_selected_tier=1,
        _glossary_populating=False,
        _glossary_auto_save_timer=None,
        _new_glossary_match_combo=lambda _match="exact": _FakeMatchCombo("exact"),
        _new_glossary_source_lang_combo=_track_combo,
        _new_glossary_tier_combo=lambda _tier=2: _FakeTierCombo(1),
        _schedule_glossary_auto_save=lambda *_args: None,
    )
    monkeypatch.setattr(dialogs, "QTableWidgetItem", _FakeItem)

    QtSettingsDialog._add_glossary_row(fake)

    assert len(created_combos) == 1
    assert created_combos[0]._value == "PT"


def test_glossary_auto_save_skipped_during_population() -> None:
    fake = SimpleNamespace(
        _glossary_populating=True,
        _glossary_auto_save_timer=None,
    )
    # Should not raise; guard returns early
    QtSettingsDialog._on_glossary_cell_changed(fake, 0, 0)
    QtSettingsDialog._schedule_glossary_auto_save(fake)


def test_schedule_glossary_auto_save_starts_timer() -> None:
    class _FakeTimer:
        def __init__(self) -> None:
            self.started = False

        def start(self) -> None:
            self.started = True

    timer = _FakeTimer()
    fake = SimpleNamespace(
        _glossary_populating=False,
        _glossary_auto_save_timer=timer,
    )
    QtSettingsDialog._schedule_glossary_auto_save(fake)
    assert timer.started


def test_persist_glossary_to_disk_calls_save_gui_settings(monkeypatch) -> None:
    saved_values: list[dict] = []
    monkeypatch.setattr(dialogs, "save_gui_settings", lambda v: saved_values.append(v))

    fake = SimpleNamespace(
        _glossary_current_lang="AR",
        _glossaries_by_lang={"AR": [], "EN": [], "FR": []},
        _enabled_glossary_tiers_by_lang={"AR": [1, 2], "EN": [1, 2], "FR": [1, 2]},
        _glossary_seed_version=2,
        _glossary_view_keys=[],
        _glossary_auto_save_timer=None,
        _commit_glossary_cell_editor=lambda: None,
        _save_current_glossary_language_rows=lambda: None,
        _propagate_glossary_source_phrases=lambda: None,
        _read_glossary_table_rows=lambda: [],
        _read_active_tier_checks=lambda: [1, 2],
        _glossary_entry_key=lambda entry: (
            entry.source_text,
            entry.preferred_translation,
            entry.match_mode,
            entry.source_lang,
            entry.tier,
        ),
    )

    QtSettingsDialog._persist_glossary_to_disk(fake)

    assert len(saved_values) == 1
    assert "personal_glossaries_by_lang" in saved_values[0]
    assert "glossaries_by_lang" in saved_values[0]
    assert "enabled_glossary_tiers_by_target_lang" in saved_values[0]


def test_propagate_source_phrases_adds_missing() -> None:
    fake = SimpleNamespace(
        _glossaries_by_lang={
            "AR": [GlossaryEntry("tribunal", "المحكمة", "exact", "PT", 1)],
            "EN": [],
            "FR": [GlossaryEntry("tribunal", "court", "exact", "PT", 1)],
        },
    )

    QtSettingsDialog._propagate_glossary_source_phrases(fake)

    en_sources = [e.source_text for e in fake._glossaries_by_lang["EN"]]
    assert "tribunal" in en_sources
    en_tribunal = [e for e in fake._glossaries_by_lang["EN"] if e.source_text == "tribunal"][0]
    assert en_tribunal.preferred_translation == "..."
    assert en_tribunal.match_mode == "exact"
    assert en_tribunal.source_lang == "PT"
    assert en_tribunal.tier == 1


def test_propagate_does_not_overwrite_existing() -> None:
    fake = SimpleNamespace(
        _glossaries_by_lang={
            "AR": [GlossaryEntry("tribunal", "المحكمة", "exact", "PT", 1)],
            "EN": [GlossaryEntry("tribunal", "court", "exact", "PT", 1)],
            "FR": [],
        },
    )

    QtSettingsDialog._propagate_glossary_source_phrases(fake)

    en_tribunal = [e for e in fake._glossaries_by_lang["EN"] if e.source_text.casefold() == "tribunal"]
    assert len(en_tribunal) == 1
    assert en_tribunal[0].preferred_translation == "court"


def test_propagate_normalizes_casefolding() -> None:
    fake = SimpleNamespace(
        _glossaries_by_lang={
            "AR": [GlossaryEntry("Tribunal", "المحكمة", "exact", "PT", 1)],
            "EN": [GlossaryEntry("tribunal", "court", "exact", "PT", 1)],
            "FR": [],
        },
    )

    QtSettingsDialog._propagate_glossary_source_phrases(fake)

    fr_entries = [e for e in fake._glossaries_by_lang["FR"] if "tribunal" in e.source_text.casefold()]
    assert len(fr_entries) == 1


def test_read_glossary_table_rows_placeholder_for_empty_translation() -> None:
    """Row with source but empty translation should use '...' placeholder."""
    table = _FakeTable()
    table.rows = [
        [_FakeItem("Hello"), _FakeItem(""), _FakeMatchCombo("exact"), _FakeSourceLangCombo("PT"), _FakeTierCombo(1)],
        [_FakeItem(""), _FakeItem("orphan"), _FakeMatchCombo("exact"), _FakeSourceLangCombo("AUTO"), _FakeTierCombo(1)],
    ]
    fake = SimpleNamespace(
        glossary_table=table,
        _glossary_current_lang="FR",
        _glossary_match_value=lambda combo: QtSettingsDialog._glossary_match_value(SimpleNamespace(), combo),
        _glossary_source_lang_value=lambda combo: QtSettingsDialog._glossary_source_lang_value(SimpleNamespace(), combo),
        _glossary_tier_value=lambda combo: QtSettingsDialog._glossary_tier_value(SimpleNamespace(), combo),
    )

    rows = QtSettingsDialog._read_glossary_table_rows(fake)

    # "Hello" row should survive with "..." placeholder translation
    assert len(rows) == 1
    assert rows[0].source_text == "Hello"
    assert rows[0].preferred_translation == "..."
    # Row with empty source but non-empty target is dropped by normalize


def test_save_current_glossary_rows_updates_view_keys() -> None:
    """After save, _glossary_view_keys should reflect current table content."""
    entry_a = GlossaryEntry("aaa", "xxx", "exact", "PT", 1)
    entry_b = GlossaryEntry("bbb", "yyy", "exact", "PT", 1)

    def _entry_key(entry: GlossaryEntry) -> tuple:
        return (entry.source_text, entry.preferred_translation, entry.match_mode, entry.source_lang, entry.tier)

    fake = SimpleNamespace(
        _glossary_current_lang="FR",
        _glossaries_by_lang={"FR": [entry_a]},
        _glossary_view_keys=[_entry_key(entry_a)],
        _enabled_glossary_tiers_by_lang={"FR": [1, 2]},
        _read_glossary_table_rows=lambda: [entry_b],
        _read_active_tier_checks=lambda: [1, 2],
        _glossary_entry_key=_entry_key,
    )

    QtSettingsDialog._save_current_glossary_language_rows(fake)

    # view_keys should now match the table content (entry_b), not the original (entry_a)
    assert _entry_key(entry_b) in fake._glossary_view_keys
    assert _entry_key(entry_a) not in fake._glossary_view_keys
