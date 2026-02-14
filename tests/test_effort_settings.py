"""Tests for openai_reasoning_effort_lemma setting and effort parameter wiring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Settings: load_gui_settings
# ---------------------------------------------------------------------------


def test_load_gui_settings_lemma_effort_default(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{}", encoding="utf-8")
    with patch("legalpdf_translate.user_settings.settings_path", return_value=settings_file):
        from legalpdf_translate.user_settings import load_gui_settings

        settings = load_gui_settings()
    assert settings["openai_reasoning_effort_lemma"] == "high"


def test_load_gui_settings_lemma_effort_saved(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"openai_reasoning_effort_lemma": "high"}),
        encoding="utf-8",
    )
    with patch("legalpdf_translate.user_settings.settings_path", return_value=settings_file):
        from legalpdf_translate.user_settings import load_gui_settings

        settings = load_gui_settings()
    assert settings["openai_reasoning_effort_lemma"] == "high"


def test_load_gui_settings_lemma_effort_invalid(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"openai_reasoning_effort_lemma": "ultra"}),
        encoding="utf-8",
    )
    with patch("legalpdf_translate.user_settings.settings_path", return_value=settings_file):
        from legalpdf_translate.user_settings import load_gui_settings

        settings = load_gui_settings()
    # "ultra" is not in allowed={medium, high, xhigh}, so it falls back to "high"
    assert settings["openai_reasoning_effort_lemma"] == "high"


def test_load_gui_settings_lemma_effort_xhigh_valid(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps({"openai_reasoning_effort_lemma": "xhigh"}),
        encoding="utf-8",
    )
    with patch("legalpdf_translate.user_settings.settings_path", return_value=settings_file):
        from legalpdf_translate.user_settings import load_gui_settings

        settings = load_gui_settings()
    # "xhigh" is now in allowed set, should load as-is
    assert settings["openai_reasoning_effort_lemma"] == "xhigh"


# ---------------------------------------------------------------------------
# study_glossary: effort parameter
# ---------------------------------------------------------------------------


def test_translate_term_effort_param() -> None:
    """translate_term_for_lang forwards the effort parameter to the client."""
    mock_client = MagicMock()
    mock_client.create_page_response.return_value = MagicMock(
        raw_output="```\nThe defendant\n```",
    )
    from legalpdf_translate.study_glossary import translate_term_for_lang

    try:
        translate_term_for_lang(
            "arguido",
            "EN",
            client=mock_client,
            effort="high",
        )
    except Exception:
        pass  # validation may fail on mock output, but we check the call

    call_kwargs = mock_client.create_page_response.call_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("effort") == "high"


def test_translate_term_effort_default() -> None:
    """translate_term_for_lang uses 'medium' effort by default."""
    mock_client = MagicMock()
    mock_client.create_page_response.return_value = MagicMock(
        raw_output="```\nThe defendant\n```",
    )
    from legalpdf_translate.study_glossary import translate_term_for_lang

    try:
        translate_term_for_lang(
            "arguido",
            "EN",
            client=mock_client,
        )
    except Exception:
        pass

    call_kwargs = mock_client.create_page_response.call_args
    assert call_kwargs is not None
    assert call_kwargs.kwargs.get("effort") == "medium"


def test_fill_translations_effort_passthrough() -> None:
    """fill_translations_for_entry passes effort through to translate_term_for_lang."""
    from legalpdf_translate.study_glossary import (
        StudyGlossaryEntry,
        fill_translations_for_entry,
    )

    entry = StudyGlossaryEntry(
        term_pt="arguido",
        translations_by_lang={"EN": ""},
        tf=5,
        df_pages=2,
        sample_snippets=[],
        category="roles",
        status="new",
        next_review_date=None,
    )

    with patch("legalpdf_translate.study_glossary.translate_term_for_lang") as mock_translate:
        mock_translate.side_effect = Exception("mock")
        fill_translations_for_entry(
            entry,
            supported_langs=["EN"],
            effort="high",
        )
        assert mock_translate.call_count >= 1
        call_kwargs = mock_translate.call_args
        assert call_kwargs.kwargs.get("effort") == "high"
