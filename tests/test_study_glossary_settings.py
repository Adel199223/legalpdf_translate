from __future__ import annotations

import json
from pathlib import Path

import legalpdf_translate.user_settings as user_settings


def test_study_glossary_defaults_are_present(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    loaded = user_settings.load_gui_settings()

    assert loaded["study_glossary_entries"] == []
    assert loaded["study_glossary_include_snippets"] is False
    assert loaded["study_glossary_snippet_max_chars"] == 120
    assert loaded["study_glossary_last_run_dirs"] == []
    assert loaded["study_glossary_corpus_source"] == "run_folders"
    assert loaded["study_glossary_pdf_paths"] == []
    assert loaded["study_glossary_default_coverage_percent"] == 80


def test_study_glossary_settings_normalize_entries_and_limits(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "study_glossary_entries": [
                    {
                        "term_pt": "acusação",
                        "translations_by_lang": {"AR": "الاتهام"},
                        "tf": "5",
                        "df_pages": "2",
                        "df_docs": "1",
                        "sample_snippets": ["  exemplo  "],
                        "category": "procedure",
                        "status": "learning",
                    }
                ],
                "study_glossary_snippet_max_chars": 500,
                "study_glossary_default_coverage_percent": 10,
                "study_glossary_last_run_dirs": ["C:/runs/a", "C:/runs/a", " "],
                "study_glossary_corpus_source": "invalid_mode",
                "study_glossary_pdf_paths": ["C:/pdfs/a.pdf", "C:/pdfs/a.pdf", " "],
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()
    assert loaded["study_glossary_snippet_max_chars"] == 300
    assert loaded["study_glossary_default_coverage_percent"] == 50
    assert loaded["study_glossary_last_run_dirs"] == ["C:/runs/a"]
    assert loaded["study_glossary_corpus_source"] == "run_folders"
    assert loaded["study_glossary_pdf_paths"] == ["C:/pdfs/a.pdf"]
    entry = loaded["study_glossary_entries"][0]
    assert entry["term_pt"] == "acusação"
    assert entry["translations_by_lang"] == {"EN": "", "FR": "", "AR": "الاتهام"}
    assert entry["tf"] == 5
    assert entry["df_pages"] == 2
    assert entry["df_docs"] == 1


def test_study_glossary_expands_when_new_target_language_added(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    monkeypatch.setattr(user_settings, "supported_learning_langs", lambda: ["EN", "FR", "AR", "ES"])
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "study_glossary_entries": [
                    {
                        "term_pt": "acusação",
                        "translations_by_lang": {"AR": "الاتهام"},
                        "tf": 3,
                        "df_pages": 1,
                        "df_docs": 1,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()
    entry = loaded["study_glossary_entries"][0]
    assert entry["translations_by_lang"] == {"EN": "", "FR": "", "AR": "الاتهام", "ES": ""}
    assert entry["df_docs"] == 1
