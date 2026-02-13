from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import legalpdf_translate.qt_gui.dialogs as dialogs
from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.qt_gui.dialogs import QtSettingsDialog
from legalpdf_translate.study_glossary import StudyGlossaryEntry


class _FakeCheck:
    def __init__(self, checked: bool) -> None:
        self._checked = checked

    def isChecked(self) -> bool:
        return self._checked


class _FakeSpin:
    def __init__(self, value: int) -> None:
        self._value = value

    def value(self) -> int:
        return self._value


class _FakeLabel:
    def __init__(self) -> None:
        self.value = ""

    def setText(self, value: str) -> None:
        self.value = value


class _FakeProgress:
    def __init__(self) -> None:
        self.value = 0

    def setValue(self, value: int) -> None:
        self.value = value


class _FakeControl:
    def __init__(self) -> None:
        self.enabled = True

    def setEnabled(self, value: bool) -> None:
        self.enabled = bool(value)


class _FakeCombo:
    def __init__(self, value: str) -> None:
        self._value = value

    def currentData(self) -> str:
        return self._value

    def currentText(self) -> str:
        return self._value


def test_visible_study_entries_filters_by_search_and_flags() -> None:
    fake = SimpleNamespace(
        _study_entries=[
            StudyGlossaryEntry(
                term_pt="acusação",
                translations_by_lang={"EN": "indictment", "FR": "", "AR": "الاتهام"},
                tf=5,
                df_pages=2,
                df_docs=1,
                sample_snippets=[],
                category="procedure",
                status="new",
                next_review_date=None,
                coverage_tier="core80",
            ),
            StudyGlossaryEntry(
                term_pt="custas",
                translations_by_lang={"EN": "costs", "FR": "", "AR": "المصاريف"},
                tf=4,
                df_pages=2,
                df_docs=1,
                sample_snippets=[],
                category="decision_costs",
                status="known",
                next_review_date=None,
                coverage_tier="next15",
            ),
        ],
        _study_supported_langs=["EN", "FR", "AR"],
        _study_search_text="اتهام",
        _study_filters={"category": "procedure", "status": "new", "coverage_tier": "core80"},
    )

    rows = QtSettingsDialog._visible_study_entries(fake)

    assert len(rows) == 1
    assert rows[0].term_pt == "acusação"


def test_collect_study_settings_values_serializes_expected_fields() -> None:
    fake = SimpleNamespace(
        _study_supported_langs=["EN", "FR", "AR"],
        _study_entries=[
            StudyGlossaryEntry(
                term_pt="acusação",
                translations_by_lang={"EN": "indictment", "FR": "", "AR": "الاتهام"},
                tf=5,
                df_pages=2,
                df_docs=2,
                sample_snippets=[],
                category="procedure",
                status="learning",
                next_review_date="2026-02-14",
                coverage_tier="core80",
                confidence=0.8,
            )
        ],
        _save_current_study_table_rows=lambda: None,
        study_include_snippets_check=_FakeCheck(True),
        study_snippet_chars_spin=_FakeSpin(140),
        study_coverage_spin=_FakeSpin(82),
        _collect_study_run_dirs=lambda: ["C:/runs/demo_run"],
        _current_study_corpus_source=lambda: "run_folders",
        _collect_study_pdf_paths=lambda: [],
    )

    values = QtSettingsDialog._collect_study_settings_values(fake)

    assert values["study_glossary_include_snippets"] is True
    assert values["study_glossary_snippet_max_chars"] == 140
    assert values["study_glossary_default_coverage_percent"] == 82
    assert values["study_glossary_last_run_dirs"] == ["C:/runs/demo_run"]
    assert values["study_glossary_corpus_source"] == "run_folders"
    assert values["study_glossary_pdf_paths"] == []
    rows = values["study_glossary_entries"]
    assert isinstance(rows, list)
    assert rows[0]["term_pt"] == "acusação"


def test_save_current_study_table_rows_preserves_hidden_entries() -> None:
    hidden = StudyGlossaryEntry(
        term_pt="custas",
        translations_by_lang={"EN": "costs", "FR": "", "AR": "المصاريف"},
        tf=3,
        df_pages=1,
        df_docs=1,
        sample_snippets=[],
        category="decision_costs",
        status="new",
        next_review_date=None,
    )
    visible_old = StudyGlossaryEntry(
        term_pt="acusação",
        translations_by_lang={"EN": "old", "FR": "", "AR": ""},
        tf=1,
        df_pages=1,
        df_docs=1,
        sample_snippets=[],
        category="procedure",
        status="new",
        next_review_date=None,
    )
    visible_new = StudyGlossaryEntry(
        term_pt="acusação",
        translations_by_lang={"EN": "indictment", "FR": "", "AR": "الاتهام"},
        tf=5,
        df_pages=2,
        df_docs=2,
        sample_snippets=[],
        category="procedure",
        status="learning",
        next_review_date="2026-02-14",
    )
    fake = SimpleNamespace(
        _study_entries=[visible_old, hidden],
        _study_supported_langs=["EN", "FR", "AR"],
        _study_entry_view_terms=["acusação"],
        _study_entry_key=lambda value: str(value).casefold(),
        _read_study_entries_table_rows=lambda: [visible_new],
    )

    QtSettingsDialog._save_current_study_table_rows(fake)

    terms = {entry.term_pt for entry in fake._study_entries}
    assert terms == {"acusação", "custas"}
    updated = next(entry for entry in fake._study_entries if entry.term_pt == "acusação")
    assert updated.translations_by_lang["EN"] == "indictment"


def test_export_study_glossary_markdown_current_filter_scope(tmp_path: Path, monkeypatch) -> None:
    output_path = (tmp_path / "study_export.md").resolve()

    class _FakeMessageBox:
        class ButtonRole:
            AcceptRole = object()
            ActionRole = object()

        class StandardButton:
            Cancel = object()

        def __init__(self, *args, **kwargs) -> None:  # noqa: D401, ANN002, ANN003
            self._clicked = None
            self._current = None
            self._all = None
            self._cancel = object()

        def setWindowTitle(self, _title: str) -> None:
            return None

        def setText(self, _text: str) -> None:
            return None

        def addButton(self, *args):  # type: ignore[no-untyped-def]
            if len(args) == 1:
                return self._cancel
            label = str(args[0])
            button = object()
            if label.startswith("Current"):
                self._current = button
            else:
                self._all = button
            return button

        def exec(self) -> None:
            self._clicked = self._current

        def clickedButton(self):  # type: ignore[no-untyped-def]
            return self._clicked

        def button(self, _value):  # type: ignore[no-untyped-def]
            return self._cancel

        @staticmethod
        def information(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
            return None

        @staticmethod
        def critical(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
            return None

    monkeypatch.setattr(dialogs, "QMessageBox", _FakeMessageBox)
    monkeypatch.setattr(dialogs.QFileDialog, "getSaveFileName", lambda *args, **kwargs: (str(output_path), "Markdown (*.md)"))
    monkeypatch.setattr(dialogs, "app_data_dir", lambda: tmp_path)

    visible_entry = StudyGlossaryEntry(
        term_pt="acusação",
        translations_by_lang={"EN": "indictment", "FR": "acte", "AR": "الاتهام"},
        tf=5,
        df_pages=2,
        df_docs=2,
        sample_snippets=["exemplo"],
        category="procedure",
        status="learning",
        next_review_date="2026-02-14",
        coverage_tier="core80",
    )
    hidden_entry = StudyGlossaryEntry(
        term_pt="custas",
        translations_by_lang={"EN": "costs", "FR": "frais", "AR": "المصاريف"},
        tf=3,
        df_pages=1,
        df_docs=1,
        sample_snippets=[],
        category="decision_costs",
        status="new",
        next_review_date=None,
        coverage_tier="long_tail",
    )
    fake = SimpleNamespace(
        _save_current_study_table_rows=lambda: None,
        _study_entries=[visible_entry, hidden_entry],
        _visible_study_entries=lambda: [visible_entry],
        _study_last_run_folders_processed=2,
        _study_last_total_pages_scanned=35,
        study_include_snippets_check=_FakeCheck(False),
        study_snippet_chars_spin=_FakeSpin(120),
        _study_supported_langs=["AR", "FR", "EN"],
    )

    QtSettingsDialog._export_study_glossary_markdown(fake)

    content = output_path.read_text(encoding="utf-8")
    assert "| PT | AR | FR | EN | TF | Pages | Docs | Tier | Category | Status |" in content
    assert "acusação" in content
    assert "custas" not in content


def test_cancel_generation_does_not_change_existing_study_entries() -> None:
    entries = [
        StudyGlossaryEntry(
            term_pt="acusação",
            translations_by_lang={"EN": "indictment", "FR": "", "AR": "الاتهام"},
            tf=5,
            df_pages=2,
            df_docs=2,
            sample_snippets=[],
            category="procedure",
            status="learning",
            next_review_date="2026-02-14",
        )
    ]
    fake = SimpleNamespace(
        _study_entries=list(entries),
        _set_study_generation_controls_busy=lambda busy: None,
        study_summary_label=_FakeLabel(),
        study_progress=_FakeProgress(),
        _study_candidate_thread=object(),
        _study_candidate_worker=object(),
    )

    QtSettingsDialog._on_study_candidate_cancelled(fake)

    assert fake._study_entries == entries
    assert fake.study_summary_label.value == "Generation cancelled. Existing study glossary is unchanged."
    assert fake.study_progress.value == 0


def test_refresh_study_corpus_source_controls_toggles_lists() -> None:
    fake = SimpleNamespace(
        _current_study_corpus_source=lambda: "select_pdfs",
        _study_current_pdf_path=None,
        _study_corpus_source="run_folders",
        study_run_dirs_list=_FakeControl(),
        study_add_run_dir_btn=_FakeControl(),
        study_remove_run_dir_btn=_FakeControl(),
        study_clear_run_dirs_btn=_FakeControl(),
        study_pdf_paths_list=_FakeControl(),
        study_add_pdf_btn=_FakeControl(),
        study_remove_pdf_btn=_FakeControl(),
        study_clear_pdf_btn=_FakeControl(),
        study_current_pdf_label=_FakeLabel(),
    )

    QtSettingsDialog._refresh_study_corpus_source_controls(fake)

    assert fake._study_corpus_source == "select_pdfs"
    assert fake.study_run_dirs_list.enabled is False
    assert fake.study_pdf_paths_list.enabled is True
    assert "not available" in fake.study_current_pdf_label.value


def test_resolve_study_corpus_inputs_current_pdf_requires_active_path(monkeypatch) -> None:
    messages: list[str] = []

    class _FakeMessageBox:
        @staticmethod
        def warning(_self, _title: str, message: str) -> None:
            messages.append(message)

        @staticmethod
        def information(_self, _title: str, message: str) -> None:
            messages.append(message)

    monkeypatch.setattr(dialogs, "QMessageBox", _FakeMessageBox)
    fake = SimpleNamespace(
        _current_study_corpus_source=lambda: "current_pdf",
        _collect_study_run_dirs=lambda: [],
        _collect_study_pdf_paths=lambda: [],
        _study_current_pdf_path=None,
    )

    resolved = QtSettingsDialog._resolve_study_corpus_inputs(fake)

    assert resolved is None
    assert any("No active PDF is available" in msg for msg in messages)


def test_resolve_study_corpus_inputs_select_pdfs_uses_selected_paths() -> None:
    fake = SimpleNamespace(
        _current_study_corpus_source=lambda: "select_pdfs",
        _collect_study_run_dirs=lambda: [],
        _collect_study_pdf_paths=lambda: ["C:/pdfs/a.pdf", "C:/pdfs/b.pdf"],
        _study_current_pdf_path=None,
    )

    resolved = QtSettingsDialog._resolve_study_corpus_inputs(fake)

    assert resolved == ("select_pdfs", [], ["C:/pdfs/a.pdf", "C:/pdfs/b.pdf"])


def test_resolve_study_corpus_inputs_joblog_unavailable(monkeypatch) -> None:
    messages: list[str] = []

    class _FakeMessageBox:
        @staticmethod
        def warning(_self, _title: str, message: str) -> None:
            messages.append(message)

        @staticmethod
        def information(_self, _title: str, message: str) -> None:
            messages.append(message)

    monkeypatch.setattr(dialogs, "QMessageBox", _FakeMessageBox)
    fake = SimpleNamespace(
        _current_study_corpus_source=lambda: "joblog_runs",
        _collect_study_run_dirs=lambda: [],
        _collect_study_pdf_paths=lambda: [],
        _study_current_pdf_path=None,
    )

    resolved = QtSettingsDialog._resolve_study_corpus_inputs(fake)

    assert resolved is None
    assert any("Job Log source is unavailable" in msg for msg in messages)


def test_merge_study_entries_into_ai_glossary_uses_defaults_and_skips_duplicates() -> None:
    fake = SimpleNamespace(
        _glossaries_by_lang={"EN": [], "FR": [], "AR": []},
    )
    selected = [
        StudyGlossaryEntry(
            term_pt="acusação",
            translations_by_lang={"EN": "indictment", "FR": "acte d’accusation", "AR": "الاتهام"},
            tf=5,
            df_pages=2,
            df_docs=1,
            sample_snippets=[],
            category="procedure",
            status="new",
            next_review_date=None,
        )
    ]

    added, skipped, conflicts = QtSettingsDialog._merge_study_entries_into_ai_glossary(
        fake,
        selected,
        replace_conflicts=False,
    )

    assert added == 3
    assert skipped == 0
    assert conflicts == 0
    for lang in ("EN", "FR", "AR"):
        row = fake._glossaries_by_lang[lang][0]
        assert row.source_text == "acusação"
        assert row.match_mode == "exact"
        assert row.source_lang == "PT"
        assert row.tier == 2

    added2, skipped2, conflicts2 = QtSettingsDialog._merge_study_entries_into_ai_glossary(
        fake,
        selected,
        replace_conflicts=False,
    )
    assert added2 == 0
    assert skipped2 == 3
    assert conflicts2 == 0


def test_merge_study_entries_into_ai_glossary_conflict_replace_toggle() -> None:
    fake = SimpleNamespace(
        _glossaries_by_lang={
            "EN": [],
            "FR": [],
            "AR": [GlossaryEntry("acusação", "ترجمة قديمة", "exact", "PT", 2)],
        },
    )
    selected = [
        StudyGlossaryEntry(
            term_pt="acusação",
            translations_by_lang={"EN": "", "FR": "", "AR": "الاتهام"},
            tf=4,
            df_pages=2,
            df_docs=1,
            sample_snippets=[],
            category="procedure",
            status="new",
            next_review_date=None,
        )
    ]

    added, skipped, conflicts = QtSettingsDialog._merge_study_entries_into_ai_glossary(
        fake,
        selected,
        replace_conflicts=False,
    )
    assert (added, skipped, conflicts) == (0, 1, 1)
    assert fake._glossaries_by_lang["AR"][0].preferred_translation == "ترجمة قديمة"

    added2, skipped2, conflicts2 = QtSettingsDialog._merge_study_entries_into_ai_glossary(
        fake,
        selected,
        replace_conflicts=True,
    )
    assert (added2, skipped2, conflicts2) == (1, 0, 1)
    assert fake._glossaries_by_lang["AR"][0].preferred_translation == "الاتهام"
