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
    assert set(loaded["personal_glossaries_by_lang"].keys()) == {"EN", "FR", "AR"}
    assert loaded["personal_glossaries_by_lang"] == loaded["glossaries_by_lang"]
    assert loaded["prompt_addendum_by_lang"] == {"EN": "", "FR": "", "AR": ""}
    assert loaded["calibration_sample_pages_default"] == 5
    assert loaded["calibration_user_seed"] == ""
    assert loaded["calibration_enable_excerpt_storage"] is False
    assert loaded["calibration_excerpt_max_chars"] == 200
    assert loaded["study_glossary_entries"] == []
    assert loaded["study_glossary_include_snippets"] is False
    assert loaded["study_glossary_snippet_max_chars"] == 120
    assert loaded["study_glossary_last_run_dirs"] == []
    assert loaded["study_glossary_default_coverage_percent"] == 80
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
    assert loaded["default_effort_policy"] == "adaptive"
    assert loaded["effort_policy"] == "adaptive"
    assert loaded["default_workers"] == 3
    assert loaded["workers"] == 3
    assert loaded["default_resume"] is True
    assert loaded["resume"] is True
    assert loaded["ocr_mode_default"] == "auto"
    assert loaded["ocr_engine_default"] == "local_then_api"
    assert loaded["ocr_mode"] == "auto"
    assert loaded["ocr_engine"] == "local_then_api"
    assert loaded["gmail_gog_path"] == ""
    assert loaded["gmail_account_email"] == ""
    assert isinstance(loaded["allow_xhigh_escalation"], bool)
    assert loaded["perf_timeout_text_seconds"] == 480
    assert loaded["perf_timeout_image_seconds"] == 720
    assert loaded["ocr_api_provider"] in {"openai", "gemini"}
    assert loaded["ocr_api_provider_default"] in {"openai", "gemini"}


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


def test_load_gui_settings_uses_provider_aware_ocr_env_default(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(json.dumps({"ocr_api_provider": "gemini", "ocr_api_key_env_name": ""}), encoding="utf-8")

    loaded = user_settings.load_gui_settings()

    assert loaded["ocr_api_provider"] == "gemini"
    assert loaded["ocr_api_key_env_name"] == "GEMINI_API_KEY"


def test_load_gui_settings_migrates_legacy_single_scope_to_personal(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "glossary_seed_version": 2,
                "glossary_seed_preset_version": 2,
                "glossaries_by_lang": {
                    "EN": [
                        {
                            "source_text": "acusação",
                            "preferred_translation": "indictment",
                            "match_mode": "exact",
                            "source_lang": "PT",
                            "tier": 2,
                        }
                    ],
                    "FR": [],
                    "AR": [],
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()
    assert loaded["personal_glossaries_by_lang"] == loaded["glossaries_by_lang"]
    assert loaded["personal_glossaries_by_lang"]["EN"][0]["source_text"] == "acusação"


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


def test_load_gui_settings_migrates_legacy_timeout_defaults(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 2,
                "perf_timeout_text_seconds": 90,
                "perf_timeout_image_seconds": 120,
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["perf_timeout_text_seconds"] == 480
    assert loaded["perf_timeout_image_seconds"] == 720


def test_load_gui_settings_preserves_custom_timeout_values(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 2,
                "perf_timeout_text_seconds": 300,
                "perf_timeout_image_seconds": 900,
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["perf_timeout_text_seconds"] == 300
    assert loaded["perf_timeout_image_seconds"] == 900


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
            "study_glossary_entries": [
                {
                    "term_pt": "acusação",
                    "translations_by_lang": {"AR": "الاتهام"},
                    "tf": 5,
                    "df_pages": 2,
                    "df_docs": 2,
                }
            ],
            "study_glossary_include_snippets": True,
            "study_glossary_snippet_max_chars": 150,
            "study_glossary_last_run_dirs": ["C:/runs/demo_run"],
            "study_glossary_default_coverage_percent": 85,
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
    assert loaded["study_glossary_include_snippets"] is True
    assert loaded["study_glossary_snippet_max_chars"] == 150
    assert loaded["study_glossary_last_run_dirs"] == ["C:/runs/demo_run"]
    assert loaded["study_glossary_default_coverage_percent"] == 85
    assert loaded["study_glossary_entries"][0]["translations_by_lang"] == {"EN": "", "FR": "", "AR": "الاتهام"}
    assert loaded["study_glossary_entries"][0]["df_docs"] == 2


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


def test_load_gui_settings_expands_consistency_glossaries_for_future_langs(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    monkeypatch.setattr(user_settings, "supported_target_langs", lambda: ["EN", "FR", "AR", "ES"])
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "glossary_seed_version": 2,
                "glossary_seed_preset_version": 2,
                "glossaries_by_lang": {
                    "AR": [
                        {
                            "source_text": "acusação",
                            "preferred_translation": "الاتهام",
                            "match_mode": "exact",
                            "source_lang": "PT",
                            "tier": 1,
                        }
                    ],
                    "EN": [],
                    "FR": [],
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()
    assert set(loaded["glossaries_by_lang"].keys()) == {"EN", "FR", "AR", "ES"}
    assert loaded["glossaries_by_lang"]["AR"] == [
        {
            "source_text": "acusação",
            "preferred_translation": "الاتهام",
            "match_mode": "exact",
            "source_lang": "PT",
            "tier": 1,
        }
    ]
    assert loaded["glossaries_by_lang"]["ES"] == []
    assert loaded["enabled_glossary_tiers_by_target_lang"]["ES"] == [1, 2]
