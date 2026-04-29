from __future__ import annotations

import json
from pathlib import Path

import legalpdf_translate.user_settings as user_settings
from legalpdf_translate.glossary import default_ar_entries, default_en_entries, default_fr_entries
from legalpdf_translate.user_profile import DEFAULT_PRIMARY_PROFILE_ID, default_primary_profile


def _legacy_blank_default_primary_profile_payload() -> dict[str, object]:
    profile = default_primary_profile()
    return {
        "id": profile.id,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "document_name_override": profile.document_name_override,
        "email": profile.email,
        "phone_number": profile.phone_number,
        "postal_address": profile.postal_address,
        "iban": profile.iban,
        "iva_text": profile.iva_text,
        "irs_text": profile.irs_text,
        "travel_origin_label": "",
        "travel_distances_by_city": {},
    }


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
    assert isinstance(loaded["profiles"], list)
    assert len(loaded["profiles"]) == 1
    assert loaded["primary_profile_id"] == DEFAULT_PRIMARY_PROFILE_ID
    assert loaded["profiles"][0]["id"] == DEFAULT_PRIMARY_PROFILE_ID
    assert loaded["profiles"][0]["phone_number"] == ""
    assert loaded["profiles"][0]["travel_origin_label"] == "Marmelar"
    assert loaded["profiles"][0]["travel_distances_by_city"]["Beja"] == 39.0
    assert loaded["gmail_intake_bridge_enabled"] is False
    assert loaded["gmail_intake_bridge_token"] == ""
    assert loaded["gmail_intake_port"] == 8765
    assert isinstance(loaded["allow_xhigh_escalation"], bool)
    assert loaded["perf_timeout_text_seconds"] == 480
    assert loaded["perf_timeout_image_seconds"] == 720
    assert loaded["ocr_api_provider"] in {"openai", "gemini"}
    assert loaded["ocr_api_provider_default"] in {"openai", "gemini"}
    assert loaded["ocr_api_key_env_name"] == "OPENAI_API_KEY"


def test_load_gui_settings_coerces_gmail_intake_bridge_fields(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 5,
                "gmail_intake_bridge_enabled": True,
                "gmail_intake_bridge_token": "  shared-token  ",
                "gmail_intake_port": "70000",
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["settings_schema_version"] == 5
    assert loaded["gmail_intake_bridge_enabled"] is True
    assert loaded["gmail_intake_bridge_token"] == "shared-token"
    assert loaded["gmail_intake_port"] == 65535


def test_load_gui_settings_seeds_profile_email_from_existing_gmail_account(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "gmail_account_email": "translator@example.com",
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["profiles"][0]["email"] == "translator@example.com"
    assert loaded["profiles"][0]["phone_number"] == ""


def test_load_gui_settings_preserves_profile_email_when_profiles_exist(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "gmail_account_email": "translator@example.com",
                "profiles": [
                    {
                        "id": "alt",
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "document_name_override": "",
                        "email": "custom@example.com",
                        "phone_number": "+351912345678",
                        "postal_address": "Rua A",
                        "iban": "PT50003506490000832760029",
                        "iva_text": "23%",
                        "irs_text": "Sem retenção",
                        "travel_origin_label": "Marmelar",
                        "travel_distances_by_city": {"Beja": 39.0},
                    }
                ],
                "primary_profile_id": "alt",
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["profiles"][0]["email"] == "custom@example.com"
    assert loaded["profiles"][0]["phone_number"] == "+351912345678"
    assert loaded["profiles"][0]["travel_origin_label"] == "Marmelar"
    assert loaded["profiles"][0]["travel_distances_by_city"]["Beja"] == 39.0
    assert loaded["primary_profile_id"] == "alt"


def test_load_gui_settings_backfills_blank_phone_when_profile_payload_is_legacy(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 8,
                "profiles": [
                    {
                        "id": "alt",
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "document_name_override": "",
                        "email": "custom@example.com",
                        "postal_address": "Rua A",
                        "iban": "PT50003506490000832760029",
                        "iva_text": "23%",
                        "irs_text": "Sem retenção",
                    }
                ],
                "primary_profile_id": "alt",
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["profiles"][0]["phone_number"] == ""
    assert loaded["profiles"][0]["travel_origin_label"] == ""
    assert loaded["profiles"][0]["travel_distances_by_city"] == {}


def test_load_gui_settings_repairs_legacy_default_primary_blank_travel_fields(
    tmp_path: Path, monkeypatch
) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 8,
                "profiles": [_legacy_blank_default_primary_profile_payload()],
                "primary_profile_id": DEFAULT_PRIMARY_PROFILE_ID,
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["settings_schema_version"] == 8
    assert loaded["profiles"][0]["travel_origin_label"] == "Marmelar"
    assert loaded["profiles"][0]["travel_distances_by_city"] == {
        "Beja": 39.0,
        "Moura": 26.0,
        "Vidigueira": 15.0,
        "Cuba": 25.0,
        "Odemira": 132.0,
        "Ferreira do Alentejo": 50.0,
        "Serpa": 34.0,
        "Brinches": 23.0,
    }
    assert "Mora" not in loaded["profiles"][0]["travel_distances_by_city"]


def test_load_gui_settings_normalizes_missing_primary_profile_id(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "id": "secondary",
                        "first_name": "Jane",
                        "last_name": "Doe",
                        "document_name_override": "",
                        "email": "",
                        "phone_number": "",
                        "postal_address": "Rua A",
                        "iban": "PT50003506490000832760029",
                        "iva_text": "23%",
                        "irs_text": "Sem retenção",
                        "travel_origin_label": "Marmelar",
                        "travel_distances_by_city": {"Beja": 39.0},
                    }
                ],
                "primary_profile_id": "missing",
            }
        ),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["primary_profile_id"] == "secondary"


def test_save_profile_settings_persists_profiles_and_primary(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    profiles, primary_profile_id = user_settings.load_profile_settings()
    extra_profile = {
        "id": "secondary",
        "first_name": "Jane",
        "last_name": "Doe",
        "document_name_override": "",
        "email": "",
        "phone_number": "+351911111111",
        "postal_address": "Rua B",
        "iban": "PT50003506490000832760029",
        "iva_text": "23%",
        "irs_text": "Sem retenção",
        "travel_origin_label": "Rua B",
        "travel_distances_by_city": {"Cuba": 12.5},
    }
    normalized = user_settings.load_gui_settings()
    profile_objects, _ = user_settings.normalize_profiles(
        normalized["profiles"] + [extra_profile],
        "secondary",
    )

    user_settings.save_profile_settings(
        profiles=profile_objects,
        primary_profile_id="secondary",
    )

    reloaded = user_settings.load_gui_settings()

    assert reloaded["primary_profile_id"] == "secondary"
    assert len(reloaded["profiles"]) == 2
    assert reloaded["profiles"][1]["phone_number"] == "+351911111111"
    assert reloaded["profiles"][1]["travel_origin_label"] == "Rua B"
    assert reloaded["profiles"][1]["travel_distances_by_city"]["Cuba"] == 12.5


def test_save_profile_settings_persists_repaired_legacy_default_primary_travel_fields(
    tmp_path: Path, monkeypatch
) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps(
            {
                "settings_schema_version": 8,
                "profiles": [_legacy_blank_default_primary_profile_payload()],
                "primary_profile_id": DEFAULT_PRIMARY_PROFILE_ID,
            }
        ),
        encoding="utf-8",
    )

    profiles, primary_profile_id = user_settings.load_profile_settings()

    user_settings.save_profile_settings(
        profiles=profiles,
        primary_profile_id=primary_profile_id,
    )

    raw = json.loads(settings_file.read_text(encoding="utf-8"))

    assert raw["settings_schema_version"] == user_settings.SETTINGS_SCHEMA_VERSION
    assert raw["primary_profile_id"] == DEFAULT_PRIMARY_PROFILE_ID
    assert raw["profiles"][0]["travel_origin_label"] == "Marmelar"
    assert raw["profiles"][0]["travel_distances_by_city"] == {
        "Beja": 39.0,
        "Moura": 26.0,
        "Vidigueira": 15.0,
        "Cuba": 25.0,
        "Odemira": 132.0,
        "Ferreira do Alentejo": 50.0,
        "Serpa": 34.0,
        "Brinches": 23.0,
    }
    assert "Mora" not in raw["profiles"][0]["travel_distances_by_city"]


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


def test_load_gui_settings_normalizes_openai_legacy_ocr_env_default(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps({"ocr_api_provider": "openai", "ocr_api_key_env_name": "DEEPSEEK_API_KEY"}),
        encoding="utf-8",
    )

    loaded = user_settings.load_gui_settings()

    assert loaded["ocr_api_provider"] == "openai"
    assert loaded["ocr_api_key_env_name"] == "OPENAI_API_KEY"


def test_load_joblog_settings_normalizes_openai_legacy_ocr_env_default(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text(
        json.dumps({"ocr_api_provider": "openai", "ocr_api_key_env_name": "DEEPSEEK_API_KEY"}),
        encoding="utf-8",
    )

    loaded = user_settings.load_joblog_settings()

    assert loaded["ocr_api_provider"] == "openai"
    assert loaded["ocr_api_key_env_name"] == "OPENAI_API_KEY"


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
