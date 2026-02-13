from __future__ import annotations

import json
from pathlib import Path

import legalpdf_translate.user_settings as user_settings
from legalpdf_translate.glossary import default_ar_entries, default_en_entries, default_fr_entries


def test_load_gui_settings_provides_schema_and_defaults(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    loaded = user_settings.load_gui_settings()

    assert loaded["settings_schema_version"] == user_settings.SETTINGS_SCHEMA_VERSION
    assert loaded["ui_theme"] in {"dark_futuristic", "dark_simple"}
    assert loaded["ui_scale"] in {1.0, 1.1, 1.25}
    assert "perf_max_transport_retries" in loaded
    assert "diagnostics_verbose_metadata_logs" in loaded
    assert loaded["diagnostics_admin_mode"] is True
    assert loaded["diagnostics_include_sanitized_snippets"] is False
    assert loaded["glossary_file_path"] == ""
    assert loaded["glossary_seed_version"] == 2
    assert loaded["glossary_seed_preset_version"] == 2
    assert set(loaded["glossaries_by_lang"].keys()) == {"EN", "FR", "AR"}
    assert loaded["enabled_glossary_tiers_by_target_lang"] == {"EN": [1, 2], "FR": [1, 2], "AR": [1, 2]}
    assert len(loaded["glossaries_by_lang"]["EN"]) == len(default_en_entries())
    assert len(loaded["glossaries_by_lang"]["FR"]) == len(default_fr_entries())
    assert len(loaded["glossaries_by_lang"]["AR"]) == len(default_ar_entries())
    assert loaded["glossaries_by_lang"]["EN"][0]["source_lang"] == "PT"
    assert loaded["glossaries_by_lang"]["FR"][0]["source_lang"] == "PT"
    assert loaded["glossaries_by_lang"]["AR"][0]["source_lang"] == "PT"
    assert "source_text" in loaded["glossaries_by_lang"]["AR"][0]
    assert "preferred_translation" in loaded["glossaries_by_lang"]["AR"][0]
    assert "match_mode" in loaded["glossaries_by_lang"]["AR"][0]
    assert "tier" in loaded["glossaries_by_lang"]["AR"][0]
    assert loaded["default_effort_policy"] in {"adaptive", "fixed_high", "fixed_xhigh"}
    assert loaded["effort_policy"] in {"adaptive", "fixed_high", "fixed_xhigh"}
    assert isinstance(loaded["allow_xhigh_escalation"], bool)


def test_load_gui_settings_migrates_old_last_used_fields(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "last_lang": "FR",
                "effort": "xhigh",
                "image_mode": "always",
                "resume": False,
                "ocr_mode": "always",
                "ocr_engine": "api",
                "ocr_api_key_env": "LEGACY_ENV_NAME",
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["default_lang"] == "FR"
    assert loaded["default_effort"] == "xhigh"
    assert loaded["default_images_mode"] == "always"
    assert loaded["default_resume"] is False
    assert loaded["ocr_mode_default"] == "always"
    assert loaded["ocr_engine_default"] == "api"
    assert loaded["ocr_api_key_env_name"] == "LEGACY_ENV_NAME"
    assert loaded["default_effort_policy"] == "fixed_xhigh"
    assert loaded["effort_policy"] == "fixed_xhigh"


def test_load_gui_settings_maps_legacy_adaptive_flags(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "adaptive_effort_enabled": True,
                "adaptive_effort_xhigh_only_when_image_or_validator_fail": True,
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["default_effort_policy"] == "adaptive"
    assert loaded["allow_xhigh_escalation"] is True


def test_save_gui_settings_writes_schema_version(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    user_settings.save_gui_settings({"ui_theme": "dark_simple"})
    raw = json.loads(settings_file.read_text(encoding="utf-8"))

    assert raw["settings_schema_version"] == user_settings.SETTINGS_SCHEMA_VERSION
    assert raw["ui_theme"] == "dark_simple"


def test_load_gui_settings_does_not_reseed_ar_when_user_cleared_rows(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "glossary_seed_version": 2,
                "glossary_seed_preset_version": 2,
                "glossaries_by_lang": {"EN": [], "FR": [], "AR": []},
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()
    assert loaded["glossaries_by_lang"]["AR"] == []
    assert loaded["glossaries_by_lang"]["EN"] == []
    assert loaded["glossaries_by_lang"]["FR"] == []
    assert loaded["enabled_glossary_tiers_by_target_lang"]["AR"] == [1, 2]


def test_load_gui_settings_migrates_legacy_literal_glossary_file(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    legacy_glossary = tmp_path / "legacy_glossary.json"
    legacy_glossary.write_text(
        json.dumps(
            {
                "version": 1,
                "rules": [
                    {
                        "target_lang": "AR",
                        "match_type": "literal",
                        "match": "صرف الأتعاب",
                        "replace": "دفع الأتعاب المستحقة",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "glossary_seed_version": 2,
                "glossary_seed_preset_version": 2,
                "glossaries_by_lang": {"EN": [], "FR": [], "AR": []},
                "glossary_file_path": str(legacy_glossary),
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()
    matching_rows = [
        row
        for row in loaded["glossaries_by_lang"]["AR"]
        if row["source_text"] == "صرف الأتعاب"
        and row["preferred_translation"] == "دفع الأتعاب المستحقة"
        and row["match_mode"] == "exact"
        and row["source_lang"] == "ANY"
        and row["tier"] == 2
    ]
    assert len(matching_rows) == 1


def test_save_and_load_glossaries_by_lang_round_trip(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    user_settings.save_gui_settings(
        {
            "glossaries_by_lang": {
                "EN": [],
                "FR": [],
                "AR": [
                    {
                        "source_text": "honorários devidos",
                        "preferred_translation": "دفع الأتعاب المستحقة",
                        "match_mode": "contains",
                        "source_lang": "PT",
                        "tier": 1,
                    }
                ],
            },
            "enabled_glossary_tiers_by_target_lang": {"EN": [1, 2], "FR": [1], "AR": [1, 2, 3]},
            "glossary_seed_version": 2,
            "glossary_seed_preset_version": 2,
        }
    )

    loaded = user_settings.load_gui_settings()
    matching_rows = [
        row
        for row in loaded["glossaries_by_lang"]["AR"]
        if row["source_text"] == "honorários devidos"
        and row["preferred_translation"] == "دفع الأتعاب المستحقة"
        and row["match_mode"] == "contains"
        and row["source_lang"] == "PT"
        and row["tier"] == 1
    ]
    assert len(matching_rows) == 1
    assert loaded["enabled_glossary_tiers_by_target_lang"] == {"EN": [1, 2], "FR": [1], "AR": [1, 2, 3]}


def test_load_gui_settings_normalizes_enabled_tiers_for_future_langs(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "enabled_glossary_tiers_by_target_lang": {"AR": [2, 6, 6], "EN": ["x"]},
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["enabled_glossary_tiers_by_target_lang"]["AR"] == [2, 6]
    assert loaded["enabled_glossary_tiers_by_target_lang"]["EN"] == [1, 2]
    assert loaded["enabled_glossary_tiers_by_target_lang"]["FR"] == [1, 2]
