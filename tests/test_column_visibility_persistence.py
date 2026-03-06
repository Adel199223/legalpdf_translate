from __future__ import annotations

from pathlib import Path

import legalpdf_translate.user_settings as user_settings
from legalpdf_translate.joblog_db import update_joblog_visible_columns
from legalpdf_translate.user_settings import load_joblog_settings, save_joblog_settings


def test_column_visibility_toggles_persist(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    selected = update_joblog_visible_columns(
        [
            "translation_date",
            "case_number",
            "service_entity",
            "service_city",
            "profit",
        ]
    )
    save_joblog_settings({"joblog_visible_columns": selected})

    loaded = load_joblog_settings()
    assert loaded["joblog_visible_columns"] == selected


def test_column_visibility_sanitizes_unknown_columns() -> None:
    selected = update_joblog_visible_columns(["profit", "unknown", "profit", "case_city"])
    assert selected == ["profit", "case_city"]


def test_column_visibility_allows_court_email() -> None:
    selected = update_joblog_visible_columns(["court_email", "profit"])
    assert selected == ["court_email", "profit"]


def test_joblog_settings_persist_court_email_vocab(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    save_joblog_settings(
        {
            "vocab_court_emails": [
                "beja.judicial@tribunais.org.pt",
                "BEJA.JUDICIAL@tribunais.org.pt",
                "cuba.judicial@tribunais.org.pt",
            ]
        }
    )

    loaded = load_joblog_settings()
    assert loaded["vocab_court_emails"] == [
        "beja.judicial@tribunais.org.pt",
        "cuba.judicial@tribunais.org.pt",
    ]
