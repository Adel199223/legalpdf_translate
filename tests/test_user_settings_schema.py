from __future__ import annotations

import json
from pathlib import Path

import legalpdf_translate.user_settings as user_settings


def test_load_gui_settings_provides_schema_and_defaults(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    loaded = user_settings.load_gui_settings()

    assert loaded["settings_schema_version"] == user_settings.SETTINGS_SCHEMA_VERSION
    assert loaded["ui_theme"] in {"dark_futuristic", "dark_simple"}
    assert loaded["ui_scale"] in {1.0, 1.1, 1.25}
    assert "perf_max_transport_retries" in loaded
    assert "diagnostics_verbose_metadata_logs" in loaded


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


def test_save_gui_settings_writes_schema_version(tmp_path: Path, monkeypatch) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(user_settings, "settings_path", lambda: settings_file)

    user_settings.save_gui_settings({"ui_theme": "dark_simple"})
    raw = json.loads(settings_file.read_text(encoding="utf-8"))

    assert raw["settings_schema_version"] == user_settings.SETTINGS_SCHEMA_VERSION
    assert raw["ui_theme"] == "dark_simple"
