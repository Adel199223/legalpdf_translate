"""Persistent local GUI settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import (
    DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS,
    DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS,
)
from .ocr_engine import default_ocr_api_env_name
from .glossary import (
    default_ar_entries,
    entries_from_legacy_rules,
    normalize_enabled_tiers_by_target_lang,
    normalize_glossaries,
    seed_missing_entries_for_target_lang,
    serialize_glossaries,
    supported_target_langs,
)
from .study_glossary import normalize_study_entries, serialize_study_entries, supported_learning_langs
from .user_profile import (
    backfill_legacy_default_primary_profile_travel_fields,
    default_primary_profile,
    normalize_profiles,
    primary_profile,
    serialize_profiles,
    UserProfile,
)
from .types import OcrApiProvider

APP_FOLDER_NAME = "LegalPDFTranslate"
SETTINGS_FILENAME = "settings.json"
SETTINGS_SCHEMA_VERSION = 9
DEFAULT_VOCAB_CASE_ENTITIES = [
    "Ministério Público",
    "Tribunal Judicial",
    "Juízo Local Criminal",
    "Juízo Central Cível",
    "Tribunal do Trabalho",
]
DEFAULT_VOCAB_SERVICE_ENTITIES = [
    "Ministério Público",
    "Tribunal Judicial",
    "GNR",
    "PSP",
    "Advogado",
]
DEFAULT_VOCAB_CITIES = [
    "Beja",
    "Moura",
    "Cuba",
    "Ferreira do Alentejo",
    "Serpa",
]
DEFAULT_VOCAB_JOB_TYPES = ["Translation", "Interpretation"]
DEFAULT_VOCAB_COURT_EMAILS = [
    "beja.ministeriopublico@tribunais.org.pt",
    "beja.trabalho.ministeriopublico@tribunais.org.pt",
    "beja.familia.ministeriopublico@tribunais.org.pt",
    "moita.ministeriopublico@tribunais.org.pt",
    "cuba.ministeriopublico@tribunais.org.pt",
    "beja.judicial@tribunais.org.pt",
    "falentejo.judicial@tribunais.org.pt",
    "serpa.judicial@tribunais.org.pt",
    "moura.judicial@tribunais.org.pt",
    "rmonsaraz.judicial@tribunais.org.pt",
    "cuba.judicial@tribunais.org.pt",
]
DEFAULT_JOBLOG_VISIBLE_COLUMNS = [
    "translation_date",
    "case_number",
    "run_id",
    "job_type",
    "service_entity",
    "service_city",
    "lang",
    "target_lang",
    "pages",
    "word_count",
    "total_tokens",
    "rate_per_word",
    "expected_total",
    "amount_paid",
    "api_cost",
    "estimated_api_cost",
    "quality_risk_score",
    "profit",
]
DEFAULT_OCR_SETTINGS: dict[str, Any] = {
    "ocr_mode": "auto",
    "ocr_engine": "local_then_api",
    "ocr_api_provider": "openai",
    "ocr_api_base_url": "",
    "ocr_api_model": "",
    "ocr_api_key_env_name": default_ocr_api_env_name(OcrApiProvider.OPENAI),
}
DEFAULT_GLOBAL_SETTINGS: dict[str, Any] = {
    "settings_schema_version": SETTINGS_SCHEMA_VERSION,
    "profiles": serialize_profiles([default_primary_profile()]),
    "primary_profile_id": default_primary_profile().id,
    "ui_theme": "dark_futuristic",
    "ui_scale": 1.0,
    "default_lang": "EN",
    "default_effort": "high",
    "default_effort_policy": "adaptive",
    "default_images_mode": "off",
    "default_workers": 3,
    "default_resume": True,
    "default_keep_intermediates": True,
    "default_page_breaks": True,
    "default_start_page": 1,
    "default_end_page": None,
    "default_outdir": "",
    "personal_glossaries_by_lang": {},
    "glossaries_by_lang": {},
    "enabled_glossary_tiers_by_target_lang": {},
    "glossary_seed_version": 0,
    "glossary_seed_preset_version": 0,
    "glossary_file_path": "",
    "prompt_addendum_by_lang": {},
    "calibration_sample_pages_default": 5,
    "calibration_user_seed": "",
    "calibration_enable_excerpt_storage": False,
    "calibration_excerpt_max_chars": 200,
    "study_glossary_entries": [],
    "study_glossary_include_snippets": False,
    "study_glossary_snippet_max_chars": 120,
    "study_glossary_last_run_dirs": [],
    "study_glossary_corpus_source": "run_folders",
    "study_glossary_pdf_paths": [],
    "study_glossary_default_coverage_percent": 80,
    "ocr_mode_default": "auto",
    "ocr_engine_default": "local_then_api",
    "ocr_api_provider_default": "openai",
    "perf_max_transport_retries": 4,
    "perf_backoff_cap_seconds": 12.0,
    "perf_timeout_text_seconds": DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS,
    "perf_timeout_image_seconds": DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS,
    "adaptive_effort_enabled": False,
    "adaptive_effort_xhigh_only_when_image_or_validator_fail": True,
    "allow_xhigh_escalation": False,
    "diagnostics_show_cost_summary": True,
    "diagnostics_verbose_metadata_logs": False,
    "diagnostics_admin_mode": True,
    "diagnostics_include_sanitized_snippets": False,
    "min_chars_to_accept_ocr": 200,
    "openai_reasoning_effort_lemma": "high",
    "gmail_gog_path": "",
    "gmail_account_email": "",
    "gmail_intake_bridge_enabled": False,
    "gmail_intake_bridge_token": "",
    "gmail_intake_port": 8765,
}
ALLOWED_GUI_KEYS = {
    "settings_schema_version",
    "profiles",
    "primary_profile_id",
    "ui_theme",
    "ui_scale",
    "default_lang",
    "default_effort",
    "default_effort_policy",
    "default_images_mode",
    "default_workers",
    "workers",
    "default_resume",
    "default_keep_intermediates",
    "default_page_breaks",
    "default_start_page",
    "default_end_page",
    "default_outdir",
    "personal_glossaries_by_lang",
    "glossaries_by_lang",
    "enabled_glossary_tiers_by_target_lang",
    "glossary_seed_version",
    "glossary_seed_preset_version",
    "glossary_file_path",
    "prompt_addendum_by_lang",
    "calibration_sample_pages_default",
    "calibration_user_seed",
    "calibration_enable_excerpt_storage",
    "calibration_excerpt_max_chars",
    "study_glossary_entries",
    "study_glossary_include_snippets",
    "study_glossary_snippet_max_chars",
    "study_glossary_last_run_dirs",
    "study_glossary_corpus_source",
    "study_glossary_pdf_paths",
    "study_glossary_default_coverage_percent",
    "ocr_mode_default",
    "ocr_engine_default",
    "perf_max_transport_retries",
    "perf_backoff_cap_seconds",
    "perf_timeout_text_seconds",
    "perf_timeout_image_seconds",
    "adaptive_effort_enabled",
    "adaptive_effort_xhigh_only_when_image_or_validator_fail",
    "allow_xhigh_escalation",
    "diagnostics_show_cost_summary",
    "diagnostics_verbose_metadata_logs",
    "diagnostics_admin_mode",
    "diagnostics_include_sanitized_snippets",
    "min_chars_to_accept_ocr",
    "openai_reasoning_effort_lemma",
    "last_outdir",
    "last_lang",
    "effort",
    "effort_policy",
    "image_mode",
    "resume",
    "keep_intermediates",
    "page_breaks",
    "start_page",
    "end_page",
    "max_pages",
    "ocr_mode",
    "ocr_engine",
    "ocr_api_provider",
    "ocr_api_base_url",
    "ocr_api_model",
    "ocr_api_key_env_name",
    "gmail_gog_path",
    "gmail_account_email",
    "gmail_intake_bridge_enabled",
    "gmail_intake_bridge_token",
    "gmail_intake_port",
}
ALLOWED_JOBLOG_KEYS = {
    "vocab_case_entities",
    "vocab_service_entities",
    "vocab_cities",
    "vocab_job_types",
    "vocab_court_emails",
    "default_rate_per_word",
    "joblog_visible_columns",
    "joblog_column_widths",
    "metadata_ai_enabled",
    "metadata_photo_enabled",
    "service_equals_case_by_default",
    "non_court_service_entities",
    "ocr_mode",
    "ocr_engine",
    "ocr_api_provider",
    "ocr_api_base_url",
    "ocr_api_model",
    "ocr_api_key_env_name",
    "vocab_entities",
}
DEFAULT_GUI_SETTINGS: dict[str, Any] = {
    **DEFAULT_GLOBAL_SETTINGS,
    "last_outdir": "",
    "last_lang": "EN",
    "effort": "high",
    "effort_policy": "adaptive",
    "image_mode": "off",
    "resume": True,
    "keep_intermediates": True,
    "page_breaks": True,
    "start_page": 1,
    "end_page": None,
    "max_pages": None,
    "workers": 3,
    **DEFAULT_OCR_SETTINGS,
}
DEFAULT_JOBLOG_SETTINGS: dict[str, Any] = {
    "vocab_case_entities": list(DEFAULT_VOCAB_CASE_ENTITIES),
    "vocab_service_entities": list(DEFAULT_VOCAB_SERVICE_ENTITIES),
    "vocab_cities": list(DEFAULT_VOCAB_CITIES),
    "vocab_job_types": list(DEFAULT_VOCAB_JOB_TYPES),
    "vocab_court_emails": list(DEFAULT_VOCAB_COURT_EMAILS),
    "default_rate_per_word": {"EN": 0.08, "FR": 0.08, "AR": 0.09},
    "joblog_visible_columns": list(DEFAULT_JOBLOG_VISIBLE_COLUMNS),
    "joblog_column_widths": {},
    "metadata_ai_enabled": True,
    "metadata_photo_enabled": True,
    "service_equals_case_by_default": True,
    "non_court_service_entities": ["GNR", "PSP"],
    "vocab_entities": list(DEFAULT_VOCAB_CASE_ENTITIES),
    **DEFAULT_OCR_SETTINGS,
}


def settings_path() -> Path:
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        root = Path(appdata)
    else:
        root = Path.home() / ".legalpdf_translate"
    return root / APP_FOLDER_NAME / SETTINGS_FILENAME


def load_settings_from_path(path: Path) -> dict[str, Any]:
    resolved_path = path.expanduser().resolve()
    if not resolved_path.exists():
        return {}
    try:
        raw = resolved_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def load_settings() -> dict[str, Any]:
    return load_settings_from_path(settings_path())


def save_settings_to_path(path: Path, data: dict[str, Any]) -> None:
    resolved_path = path.expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = resolved_path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(resolved_path)


def save_settings(data: dict[str, Any]) -> None:
    save_settings_to_path(settings_path(), data)


def app_data_dir() -> Path:
    return settings_path().parent


def app_data_dir_from_settings_path(path: Path) -> Path:
    return path.expanduser().resolve().parent


def _coerce_bool(value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _coerce_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            try:
                return int(cleaned)
            except ValueError:
                return default
    return default


def _coerce_optional_int(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned == "":
            return None
        try:
            return int(cleaned)
        except ValueError:
            return None
    return None


def _coerce_float(value: object, default: float) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (float, int)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        if cleaned:
            try:
                return float(cleaned)
            except ValueError:
                return default
    return default


def _coerce_str_list(value: object, *, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(fallback)
    output: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if cleaned == "":
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(cleaned)
    if not output:
        return list(fallback)
    return output


def _coerce_joblog_column_widths(value: object) -> dict[str, int]:
    allowed = {
        "translation_date",
        "case_number",
        "court_email",
        "run_id",
        "job_type",
        "case_entity",
        "case_city",
        "service_entity",
        "service_city",
        "service_date",
        "travel_km_outbound",
        "travel_km_return",
        "lang",
        "target_lang",
        "pages",
        "word_count",
        "total_tokens",
        "rate_per_word",
        "expected_total",
        "amount_paid",
        "api_cost",
        "estimated_api_cost",
        "quality_risk_score",
        "profit",
    }
    if not isinstance(value, dict):
        return {}
    output: dict[str, int] = {}
    for raw_key, raw_value in value.items():
        if not isinstance(raw_key, str):
            continue
        key = raw_key.strip()
        if key not in allowed:
            continue
        width = _coerce_int(raw_value, 0)
        if width <= 0:
            continue
        output[key] = width
    return output


def _coerce_rate_map(value: object, *, fallback: dict[str, float]) -> dict[str, float]:
    if not isinstance(value, dict):
        return dict(fallback)
    output = dict(fallback)
    for lang in ("EN", "FR", "AR"):
        raw = value.get(lang)
        if isinstance(raw, (int, float)):
            output[lang] = float(raw)
        elif isinstance(raw, str):
            cleaned = raw.strip().replace(",", ".")
            if cleaned:
                try:
                    output[lang] = float(cleaned)
                except ValueError:
                    continue
    return output


def _coerce_choice(value: object, *, default: str, allowed: set[str]) -> str:
    if isinstance(value, str):
        cleaned = value.strip().lower()
        if cleaned in allowed:
            return cleaned
    return default


def _normalize_gui_settings(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_GUI_SETTINGS)
    for key in ALLOWED_GUI_KEYS:
        if key in data:
            merged[key] = data[key]

    # Backward-compatible migration from previously saved "last used" keys.
    if "default_lang" not in data and "last_lang" in data:
        merged["default_lang"] = data["last_lang"]
    if "default_effort" not in data and "effort" in data:
        merged["default_effort"] = data["effort"]
    if "default_effort_policy" not in data:
        if "adaptive_effort_enabled" in data:
            merged["default_effort_policy"] = "adaptive" if bool(data.get("adaptive_effort_enabled")) else "fixed_high"
        elif "default_effort" in data:
            merged["default_effort_policy"] = "fixed_xhigh" if str(data.get("default_effort")).strip().lower() == "xhigh" else "fixed_high"
        elif "effort" in data:
            merged["default_effort_policy"] = "fixed_xhigh" if str(data.get("effort")).strip().lower() == "xhigh" else "fixed_high"
    if "default_images_mode" not in data and "image_mode" in data:
        merged["default_images_mode"] = data["image_mode"]
    if "default_resume" not in data and "resume" in data:
        merged["default_resume"] = data["resume"]
    if "default_keep_intermediates" not in data and "keep_intermediates" in data:
        merged["default_keep_intermediates"] = data["keep_intermediates"]
    if "default_page_breaks" not in data and "page_breaks" in data:
        merged["default_page_breaks"] = data["page_breaks"]
    if "default_start_page" not in data and "start_page" in data:
        merged["default_start_page"] = data["start_page"]
    if "default_end_page" not in data and "end_page" in data:
        merged["default_end_page"] = data["end_page"]
    if "default_workers" not in data and "workers" in data:
        merged["default_workers"] = data["workers"]
    if "default_outdir" not in data and "last_outdir" in data:
        merged["default_outdir"] = data["last_outdir"]
    if "ocr_mode_default" not in data and "ocr_mode" in data:
        merged["ocr_mode_default"] = data["ocr_mode"]
    if "ocr_engine_default" not in data and "ocr_engine" in data:
        merged["ocr_engine_default"] = data["ocr_engine"]

    merged["last_outdir"] = str(merged.get("last_outdir", "") or "")
    merged["last_lang"] = str(merged.get("last_lang", "EN") or "EN")
    merged["effort"] = str(merged.get("effort", "high") or "high")
    if "effort_policy" not in data:
        if "default_effort_policy" in data:
            merged["effort_policy"] = merged.get("default_effort_policy")
        elif "effort" in data:
            merged["effort_policy"] = "fixed_xhigh" if merged["effort"].strip().lower() == "xhigh" else "fixed_high"
    merged["effort_policy"] = _coerce_choice(
        merged.get("effort_policy"),
        default="adaptive",
        allowed={"adaptive", "fixed_high", "fixed_xhigh"},
    )
    if (
        "allow_xhigh_escalation" not in data
        and "adaptive_effort_xhigh_only_when_image_or_validator_fail" in data
    ):
        merged["allow_xhigh_escalation"] = data.get("adaptive_effort_xhigh_only_when_image_or_validator_fail")
    merged["allow_xhigh_escalation"] = _coerce_bool(
        merged.get("allow_xhigh_escalation"),
        bool(merged.get("adaptive_effort_xhigh_only_when_image_or_validator_fail", False)),
    )
    merged["image_mode"] = _coerce_choice(
        merged.get("image_mode"),
        default=str(merged.get("default_images_mode", "off") or "off"),
        allowed={"off", "auto", "always"},
    )
    merged["resume"] = _coerce_bool(merged.get("resume"), True)
    merged["keep_intermediates"] = _coerce_bool(merged.get("keep_intermediates"), True)
    merged["page_breaks"] = _coerce_bool(merged.get("page_breaks"), True)
    merged["start_page"] = _coerce_int(merged.get("start_page"), 1)
    merged["end_page"] = _coerce_optional_int(merged.get("end_page"))
    merged["max_pages"] = _coerce_optional_int(merged.get("max_pages"))
    merged["workers"] = max(1, min(6, _coerce_int(merged.get("workers"), 3)))
    merged["ocr_mode"] = _coerce_choice(
        merged.get("ocr_mode"),
        default="auto",
        allowed={"off", "auto", "always"},
    )
    merged["ocr_engine"] = _coerce_choice(
        merged.get("ocr_engine"),
        default="local_then_api",
        allowed={"local", "local_then_api", "api"},
    )
    merged["ocr_api_provider"] = _coerce_choice(
        merged.get("ocr_api_provider"),
        default="openai",
        allowed={"openai", "gemini"},
    )
    merged["ocr_api_base_url"] = str(merged.get("ocr_api_base_url", "") or "")
    merged["ocr_api_model"] = str(merged.get("ocr_api_model", "") or "")
    ocr_env_value = merged.get("ocr_api_key_env_name")
    if "ocr_api_key_env_name" not in data or not str(ocr_env_value or "").strip():
        fallback_env = (
            default_ocr_api_env_name(OcrApiProvider.GEMINI)
            if merged["ocr_api_provider"] == "gemini"
            else default_ocr_api_env_name(OcrApiProvider.OPENAI)
        )
        ocr_env_value = data.get("ocr_api_key_env", fallback_env)
    resolved_ocr_env = str(
        ocr_env_value
        or (
            default_ocr_api_env_name(OcrApiProvider.GEMINI)
            if merged["ocr_api_provider"] == "gemini"
            else default_ocr_api_env_name(OcrApiProvider.OPENAI)
        )
    ).strip()
    if merged["ocr_api_provider"] == "openai" and resolved_ocr_env in {"", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"}:
        resolved_ocr_env = default_ocr_api_env_name(OcrApiProvider.OPENAI)
    if merged["ocr_api_provider"] == "gemini" and resolved_ocr_env == "":
        resolved_ocr_env = default_ocr_api_env_name(OcrApiProvider.GEMINI)
    merged["ocr_api_key_env_name"] = resolved_ocr_env
    merged["gmail_gog_path"] = str(merged.get("gmail_gog_path", "") or "")
    merged["gmail_account_email"] = str(merged.get("gmail_account_email", "") or "")
    normalized_profiles, primary_profile_id = normalize_profiles(
        merged.get("profiles"),
        merged.get("primary_profile_id"),
        fallback_email=merged["gmail_account_email"],
    )
    if "profiles" not in data and merged["gmail_account_email"] and normalized_profiles:
        first_profile = normalized_profiles[0]
        if not str(first_profile.email or "").strip():
            normalized_profiles[0] = type(first_profile)(
                id=first_profile.id,
                first_name=first_profile.first_name,
                last_name=first_profile.last_name,
                document_name_override=first_profile.document_name_override,
                email=merged["gmail_account_email"],
                phone_number=first_profile.phone_number,
                postal_address=first_profile.postal_address,
                iban=first_profile.iban,
                iva_text=first_profile.iva_text,
                irs_text=first_profile.irs_text,
            )
    settings_schema_version_raw = _coerce_int(
        data.get("settings_schema_version"),
        0,
    )
    if settings_schema_version_raw < 9:
        normalized_profiles = [
            backfill_legacy_default_primary_profile_travel_fields(profile)
            for profile in normalized_profiles
        ]
    merged["profiles"] = serialize_profiles(normalized_profiles)
    merged["primary_profile_id"] = primary_profile_id
    merged["gmail_intake_bridge_enabled"] = _coerce_bool(
        merged.get("gmail_intake_bridge_enabled"),
        False,
    )
    merged["gmail_intake_bridge_token"] = str(merged.get("gmail_intake_bridge_token", "") or "").strip()
    merged["gmail_intake_port"] = max(
        1,
        min(65535, _coerce_int(merged.get("gmail_intake_port"), 8765)),
    )
    merged["settings_schema_version"] = _coerce_int(
        merged.get("settings_schema_version"),
        SETTINGS_SCHEMA_VERSION,
    )
    merged["ui_theme"] = _coerce_choice(
        merged.get("ui_theme"),
        default="dark_futuristic",
        allowed={"dark_futuristic", "dark_simple"},
    )
    ui_scale = _coerce_float(merged.get("ui_scale"), 1.0)
    if ui_scale not in (1.0, 1.1, 1.25):
        ui_scale = 1.0
    merged["ui_scale"] = ui_scale
    merged["default_lang"] = str(merged.get("default_lang", "EN") or "EN").strip().upper()
    if merged["default_lang"] not in {"EN", "FR", "AR"}:
        merged["default_lang"] = "EN"
    merged["default_effort"] = _coerce_choice(
        merged.get("default_effort"),
        default="high",
        allowed={"high", "xhigh"},
    )
    merged["default_effort_policy"] = _coerce_choice(
        merged.get("default_effort_policy"),
        default="adaptive",
        allowed={"adaptive", "fixed_high", "fixed_xhigh"},
    )
    merged["default_images_mode"] = _coerce_choice(
        merged.get("default_images_mode"),
        default="off",
        allowed={"off", "auto", "always"},
    )
    merged["default_workers"] = max(1, min(6, _coerce_int(merged.get("default_workers"), 3)))
    merged["default_resume"] = _coerce_bool(merged.get("default_resume"), True)
    merged["default_keep_intermediates"] = _coerce_bool(merged.get("default_keep_intermediates"), True)
    merged["default_page_breaks"] = _coerce_bool(merged.get("default_page_breaks"), True)
    # Default translation start page is fixed to page 1; later pages are explicit per-run overrides only.
    merged["default_start_page"] = 1
    merged["default_end_page"] = _coerce_optional_int(merged.get("default_end_page"))
    merged["default_outdir"] = str(merged.get("default_outdir", "") or "")
    merged["ocr_api_provider_default"] = _coerce_choice(
        merged.get("ocr_api_provider_default"),
        default="openai",
        allowed={"openai", "gemini"},
    )
    supported_langs = supported_target_langs()
    has_personal_scope = "personal_glossaries_by_lang" in data
    personal_source = (
        merged.get("personal_glossaries_by_lang")
        if has_personal_scope
        else merged.get("glossaries_by_lang")
    )
    normalized_personal_glossaries = normalize_glossaries(personal_source, supported_langs)
    enabled_tiers = normalize_enabled_tiers_by_target_lang(
        merged.get("enabled_glossary_tiers_by_target_lang"),
        supported_langs,
    )
    glossary_seed_version = _coerce_int(merged.get("glossary_seed_version"), 0)
    glossary_seed_preset_version = _coerce_int(merged.get("glossary_seed_preset_version"), 0)
    merged["glossary_file_path"] = str(merged.get("glossary_file_path", "") or "")
    has_any_glossary_rows = any(normalized_personal_glossaries.get(lang) for lang in supported_langs)
    if not has_any_glossary_rows and merged["glossary_file_path"].strip():
        legacy_glossaries = entries_from_legacy_rules(Path(merged["glossary_file_path"]))
        for lang in supported_langs:
            legacy_rows = legacy_glossaries.get(lang, [])
            if legacy_rows:
                normalized_personal_glossaries[lang] = legacy_rows
        has_any_glossary_rows = any(normalized_personal_glossaries.get(lang) for lang in supported_langs)
    raw_glossaries = data.get("personal_glossaries_by_lang")
    if not isinstance(raw_glossaries, dict):
        raw_glossaries = data.get("glossaries_by_lang")
    has_explicit_ar_rows = False
    if isinstance(raw_glossaries, dict):
        for raw_lang in raw_glossaries.keys():
            if str(raw_lang).strip().upper() == "AR":
                has_explicit_ar_rows = True
                break
    if glossary_seed_version < 2 and not normalized_personal_glossaries.get("AR") and not has_explicit_ar_rows:
        normalized_personal_glossaries["AR"] = default_ar_entries()
    if glossary_seed_preset_version < 2:
        for target_lang in ("AR", "EN", "FR"):
            normalized_personal_glossaries[target_lang] = seed_missing_entries_for_target_lang(
                target_lang,
                normalized_personal_glossaries.get(target_lang, []),
            )
    serialized_personal = serialize_glossaries(normalized_personal_glossaries, supported_langs)
    merged["personal_glossaries_by_lang"] = serialized_personal
    # Backward-compatible mirror for existing UI/tests and downstream consumers.
    merged["glossaries_by_lang"] = serialized_personal
    merged["enabled_glossary_tiers_by_target_lang"] = {
        lang: list(enabled_tiers.get(lang, [1, 2]))
        for lang in supported_langs
    }
    merged["glossary_seed_version"] = glossary_seed_version if glossary_seed_version >= 2 else 2
    merged["glossary_seed_preset_version"] = glossary_seed_preset_version if glossary_seed_preset_version >= 2 else 2
    raw_addendum = merged.get("prompt_addendum_by_lang")
    normalized_addendum: dict[str, str] = {}
    if isinstance(raw_addendum, dict):
        for lang in supported_langs:
            value = str(raw_addendum.get(lang, "") or "").strip()
            normalized_addendum[lang] = value[:5000]
    else:
        for lang in supported_langs:
            normalized_addendum[lang] = ""
    merged["prompt_addendum_by_lang"] = normalized_addendum
    merged["calibration_sample_pages_default"] = max(
        1,
        min(20, _coerce_int(merged.get("calibration_sample_pages_default"), 5)),
    )
    merged["calibration_user_seed"] = str(merged.get("calibration_user_seed", "") or "").strip()
    merged["calibration_enable_excerpt_storage"] = _coerce_bool(
        merged.get("calibration_enable_excerpt_storage"),
        False,
    )
    merged["calibration_excerpt_max_chars"] = max(
        40,
        min(500, _coerce_int(merged.get("calibration_excerpt_max_chars"), 200)),
    )
    merged["ocr_mode_default"] = _coerce_choice(
        merged.get("ocr_mode_default"),
        default="auto",
        allowed={"off", "auto", "always"},
    )
    merged["ocr_engine_default"] = _coerce_choice(
        merged.get("ocr_engine_default"),
        default="local_then_api",
        allowed={"local", "local_then_api", "api"},
    )
    merged["perf_max_transport_retries"] = max(0, _coerce_int(merged.get("perf_max_transport_retries"), 4))
    merged["perf_backoff_cap_seconds"] = max(1.0, _coerce_float(merged.get("perf_backoff_cap_seconds"), 12.0))
    legacy_text_timeout = _coerce_int(
        data.get("perf_timeout_text_seconds"),
        DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS,
    )
    legacy_image_timeout = _coerce_int(
        data.get("perf_timeout_image_seconds"),
        DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS,
    )
    if settings_schema_version_raw < 3:
        if "perf_timeout_text_seconds" not in data or legacy_text_timeout == 90:
            merged["perf_timeout_text_seconds"] = DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS
        if "perf_timeout_image_seconds" not in data or legacy_image_timeout == 120:
            merged["perf_timeout_image_seconds"] = DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS
    merged["perf_timeout_text_seconds"] = max(
        5,
        _coerce_int(
            merged.get("perf_timeout_text_seconds"),
            DEFAULT_TRANSLATION_TIMEOUT_TEXT_SECONDS,
        ),
    )
    merged["perf_timeout_image_seconds"] = max(
        5,
        _coerce_int(
            merged.get("perf_timeout_image_seconds"),
            DEFAULT_TRANSLATION_TIMEOUT_IMAGE_SECONDS,
        ),
    )
    merged["adaptive_effort_enabled"] = _coerce_bool(merged.get("adaptive_effort_enabled"), False)
    merged["adaptive_effort_xhigh_only_when_image_or_validator_fail"] = _coerce_bool(
        merged.get("adaptive_effort_xhigh_only_when_image_or_validator_fail"),
        True,
    )
    # Keep legacy adaptive flags mirrored for backward compatibility.
    merged["adaptive_effort_enabled"] = merged["default_effort_policy"] == "adaptive"
    merged["adaptive_effort_xhigh_only_when_image_or_validator_fail"] = bool(merged["allow_xhigh_escalation"])
    merged["diagnostics_show_cost_summary"] = _coerce_bool(merged.get("diagnostics_show_cost_summary"), True)
    merged["diagnostics_verbose_metadata_logs"] = _coerce_bool(
        merged.get("diagnostics_verbose_metadata_logs"),
        False,
    )
    merged["diagnostics_admin_mode"] = _coerce_bool(merged.get("diagnostics_admin_mode"), True)
    merged["diagnostics_include_sanitized_snippets"] = _coerce_bool(
        merged.get("diagnostics_include_sanitized_snippets"),
        False,
    )
    merged["min_chars_to_accept_ocr"] = max(20, _coerce_int(merged.get("min_chars_to_accept_ocr"), 200))
    merged["openai_reasoning_effort_lemma"] = _coerce_choice(
        merged.get("openai_reasoning_effort_lemma"),
        default="high",
        allowed={"medium", "high", "xhigh"},
    )
    learning_langs = supported_learning_langs()
    normalized_study_entries = normalize_study_entries(merged.get("study_glossary_entries"), learning_langs)
    merged["study_glossary_entries"] = serialize_study_entries(normalized_study_entries, learning_langs)
    merged["study_glossary_include_snippets"] = _coerce_bool(
        merged.get("study_glossary_include_snippets"),
        False,
    )
    merged["study_glossary_snippet_max_chars"] = max(
        40,
        min(300, _coerce_int(merged.get("study_glossary_snippet_max_chars"), 120)),
    )
    coverage_percent = _coerce_int(merged.get("study_glossary_default_coverage_percent"), 80)
    merged["study_glossary_default_coverage_percent"] = max(50, min(95, coverage_percent))
    raw_study_dirs = merged.get("study_glossary_last_run_dirs")
    normalized_run_dirs: list[str] = []
    seen_dirs: set[str] = set()
    if isinstance(raw_study_dirs, list):
        for item in raw_study_dirs:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen_dirs:
                continue
            seen_dirs.add(key)
            normalized_run_dirs.append(cleaned)
    merged["study_glossary_last_run_dirs"] = normalized_run_dirs
    corpus_source = str(merged.get("study_glossary_corpus_source", "run_folders") or "").strip().lower()
    if corpus_source not in {"run_folders", "current_pdf", "select_pdfs", "joblog_runs"}:
        corpus_source = "run_folders"
    merged["study_glossary_corpus_source"] = corpus_source
    raw_pdf_paths = merged.get("study_glossary_pdf_paths")
    normalized_pdf_paths: list[str] = []
    seen_pdf_paths: set[str] = set()
    if isinstance(raw_pdf_paths, list):
        for item in raw_pdf_paths:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if cleaned == "":
                continue
            key = cleaned.casefold()
            if key in seen_pdf_paths:
                continue
            seen_pdf_paths.add(key)
            normalized_pdf_paths.append(cleaned)
    merged["study_glossary_pdf_paths"] = normalized_pdf_paths
    return merged


def load_gui_settings_from_path(path: Path) -> dict[str, Any]:
    return _normalize_gui_settings(load_settings_from_path(path))


def load_gui_settings() -> dict[str, Any]:
    return load_gui_settings_from_path(settings_path())


def save_gui_settings_to_path(path: Path, values: dict[str, Any]) -> None:
    data = load_settings_from_path(path)
    data["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
    for key in ALLOWED_GUI_KEYS:
        if key in values:
            data[key] = values[key]
    data["default_start_page"] = 1
    save_settings_to_path(path, data)


def save_gui_settings(values: dict[str, Any]) -> None:
    save_gui_settings_to_path(settings_path(), values)


def load_profile_settings_from_path(path: Path) -> tuple[list[UserProfile], str]:
    data = load_gui_settings_from_path(path)
    profiles, primary_profile_id = normalize_profiles(
        data.get("profiles"),
        data.get("primary_profile_id"),
        fallback_email=str(data.get("gmail_account_email", "") or ""),
    )
    return profiles, primary_profile_id


def load_profile_settings() -> tuple[list[UserProfile], str]:
    return load_profile_settings_from_path(settings_path())


def save_profile_settings_to_path(
    path: Path,
    *,
    profiles: list[UserProfile],
    primary_profile_id: str,
) -> None:
    normalized_profiles, normalized_primary_id = normalize_profiles(
        serialize_profiles(profiles),
        primary_profile_id,
        fallback_email="",
    )
    save_gui_settings_to_path(
        path,
        {
            "profiles": serialize_profiles(normalized_profiles),
            "primary_profile_id": primary_profile(normalized_profiles, normalized_primary_id).id,
        },
    )


def save_profile_settings(
    *,
    profiles: list[UserProfile],
    primary_profile_id: str,
) -> None:
    save_profile_settings_to_path(
        settings_path(),
        profiles=profiles,
        primary_profile_id=primary_profile_id,
    )


def _normalize_joblog_settings(data: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_JOBLOG_SETTINGS)
    for key in ALLOWED_JOBLOG_KEYS:
        if key in data:
            merged[key] = data[key]

    merged["vocab_case_entities"] = _coerce_str_list(
        merged.get("vocab_case_entities"),
        fallback=DEFAULT_VOCAB_CASE_ENTITIES,
    )
    merged["vocab_service_entities"] = _coerce_str_list(
        merged.get("vocab_service_entities"),
        fallback=DEFAULT_VOCAB_SERVICE_ENTITIES,
    )
    merged["vocab_cities"] = _coerce_str_list(
        merged.get("vocab_cities"),
        fallback=DEFAULT_VOCAB_CITIES,
    )
    merged["vocab_job_types"] = _coerce_str_list(
        merged.get("vocab_job_types"),
        fallback=DEFAULT_VOCAB_JOB_TYPES,
    )
    merged["vocab_court_emails"] = _coerce_str_list(
        merged.get("vocab_court_emails"),
        fallback=DEFAULT_VOCAB_COURT_EMAILS,
    )
    merged["vocab_entities"] = _coerce_str_list(
        merged.get("vocab_entities"),
        fallback=DEFAULT_VOCAB_CASE_ENTITIES,
    )
    merged["joblog_visible_columns"] = _coerce_str_list(
        merged.get("joblog_visible_columns"),
        fallback=DEFAULT_JOBLOG_VISIBLE_COLUMNS,
    )
    merged["joblog_column_widths"] = _coerce_joblog_column_widths(
        merged.get("joblog_column_widths"),
    )
    merged["non_court_service_entities"] = _coerce_str_list(
        merged.get("non_court_service_entities"),
        fallback=["GNR", "PSP"],
    )
    merged["metadata_ai_enabled"] = _coerce_bool(merged.get("metadata_ai_enabled"), True)
    merged["metadata_photo_enabled"] = _coerce_bool(merged.get("metadata_photo_enabled"), True)
    merged["service_equals_case_by_default"] = _coerce_bool(merged.get("service_equals_case_by_default"), True)
    merged["default_rate_per_word"] = _coerce_rate_map(
        merged.get("default_rate_per_word"),
        fallback=DEFAULT_JOBLOG_SETTINGS["default_rate_per_word"],
    )
    merged["ocr_mode"] = _coerce_choice(
        merged.get("ocr_mode"),
        default="auto",
        allowed={"off", "auto", "always"},
    )
    merged["ocr_engine"] = _coerce_choice(
        merged.get("ocr_engine"),
        default="local_then_api",
        allowed={"local", "local_then_api", "api"},
    )
    merged["ocr_api_provider"] = _coerce_choice(
        merged.get("ocr_api_provider"),
        default="openai",
        allowed={"openai", "gemini"},
    )
    merged["ocr_api_base_url"] = str(merged.get("ocr_api_base_url", "") or "")
    merged["ocr_api_model"] = str(merged.get("ocr_api_model", "") or "")
    ocr_provider = OcrApiProvider.GEMINI if merged["ocr_api_provider"] == "gemini" else OcrApiProvider.OPENAI
    default_ocr_env = default_ocr_api_env_name(ocr_provider)
    ocr_env_value = merged.get("ocr_api_key_env_name")
    if "ocr_api_key_env_name" not in data or not str(ocr_env_value or "").strip():
        ocr_env_value = data.get("ocr_api_key_env", default_ocr_env)
    resolved_ocr_env = str(ocr_env_value or default_ocr_env).strip() or default_ocr_env
    if merged["ocr_api_provider"] == "openai" and resolved_ocr_env in {"", "OPENAI_API_KEY", "DEEPSEEK_API_KEY"}:
        resolved_ocr_env = default_ocr_api_env_name(OcrApiProvider.OPENAI)
    if merged["ocr_api_provider"] == "gemini" and resolved_ocr_env == "":
        resolved_ocr_env = default_ocr_api_env_name(OcrApiProvider.GEMINI)
    merged["ocr_api_key_env_name"] = resolved_ocr_env
    if not merged["vocab_case_entities"]:
        merged["vocab_case_entities"] = list(merged["vocab_entities"])
    if not merged["vocab_service_entities"]:
        merged["vocab_service_entities"] = list(merged["vocab_entities"])
    return merged


def load_joblog_settings_from_path(path: Path) -> dict[str, Any]:
    return _normalize_joblog_settings(load_settings_from_path(path))


def load_joblog_settings() -> dict[str, Any]:
    return load_joblog_settings_from_path(settings_path())


def save_joblog_settings_to_path(path: Path, values: dict[str, Any]) -> None:
    data = load_settings_from_path(path)
    data["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
    for key in ALLOWED_JOBLOG_KEYS:
        if key in values:
            data[key] = values[key]
    save_settings_to_path(path, data)


def save_joblog_settings(values: dict[str, Any]) -> None:
    save_joblog_settings_to_path(settings_path(), values)


def load_last_outdir() -> Path | None:
    data = load_gui_settings()
    value = data.get("last_outdir")
    if not isinstance(value, str) or value.strip() == "":
        return None
    candidate = Path(value).expanduser().resolve()
    if not candidate.exists() or not candidate.is_dir():
        return None
    return candidate


def save_last_outdir(path: Path) -> None:
    save_gui_settings({"last_outdir": str(path.expanduser().resolve())})
