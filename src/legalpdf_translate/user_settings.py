"""Persistent local GUI settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_FOLDER_NAME = "LegalPDFTranslate"
SETTINGS_FILENAME = "settings.json"
SETTINGS_SCHEMA_VERSION = 2
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
DEFAULT_JOBLOG_VISIBLE_COLUMNS = [
    "translation_date",
    "case_number",
    "job_type",
    "service_entity",
    "service_city",
    "lang",
    "pages",
    "word_count",
    "rate_per_word",
    "expected_total",
    "amount_paid",
    "api_cost",
    "profit",
]
DEFAULT_OCR_SETTINGS: dict[str, Any] = {
    "ocr_mode": "auto",
    "ocr_engine": "local_then_api",
    "ocr_api_base_url": "",
    "ocr_api_model": "",
    "ocr_api_key_env_name": "DEEPSEEK_API_KEY",
}
DEFAULT_GLOBAL_SETTINGS: dict[str, Any] = {
    "settings_schema_version": SETTINGS_SCHEMA_VERSION,
    "ui_theme": "dark_futuristic",
    "ui_scale": 1.0,
    "default_lang": "EN",
    "default_effort": "high",
    "default_images_mode": "auto",
    "default_workers": 3,
    "default_resume": True,
    "default_keep_intermediates": True,
    "default_page_breaks": True,
    "default_start_page": 1,
    "default_end_page": None,
    "default_outdir": "",
    "ocr_mode_default": "auto",
    "ocr_engine_default": "local_then_api",
    "perf_max_transport_retries": 4,
    "perf_backoff_cap_seconds": 12.0,
    "perf_timeout_text_seconds": 90,
    "perf_timeout_image_seconds": 120,
    "adaptive_effort_enabled": False,
    "adaptive_effort_xhigh_only_when_image_or_validator_fail": True,
    "diagnostics_show_cost_summary": True,
    "diagnostics_verbose_metadata_logs": False,
    "min_chars_to_accept_ocr": 200,
}
ALLOWED_GUI_KEYS = {
    "settings_schema_version",
    "ui_theme",
    "ui_scale",
    "default_lang",
    "default_effort",
    "default_images_mode",
    "default_workers",
    "workers",
    "default_resume",
    "default_keep_intermediates",
    "default_page_breaks",
    "default_start_page",
    "default_end_page",
    "default_outdir",
    "ocr_mode_default",
    "ocr_engine_default",
    "perf_max_transport_retries",
    "perf_backoff_cap_seconds",
    "perf_timeout_text_seconds",
    "perf_timeout_image_seconds",
    "adaptive_effort_enabled",
    "adaptive_effort_xhigh_only_when_image_or_validator_fail",
    "diagnostics_show_cost_summary",
    "diagnostics_verbose_metadata_logs",
    "min_chars_to_accept_ocr",
    "last_outdir",
    "last_lang",
    "effort",
    "image_mode",
    "resume",
    "keep_intermediates",
    "page_breaks",
    "start_page",
    "end_page",
    "max_pages",
    "ocr_mode",
    "ocr_engine",
    "ocr_api_base_url",
    "ocr_api_model",
    "ocr_api_key_env_name",
}
ALLOWED_JOBLOG_KEYS = {
    "vocab_case_entities",
    "vocab_service_entities",
    "vocab_cities",
    "vocab_job_types",
    "default_rate_per_word",
    "joblog_visible_columns",
    "metadata_ai_enabled",
    "metadata_photo_enabled",
    "service_equals_case_by_default",
    "non_court_service_entities",
    "ocr_mode",
    "ocr_engine",
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
    "image_mode": "auto",
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
    "default_rate_per_word": {"EN": 0.08, "FR": 0.08, "AR": 0.09},
    "joblog_visible_columns": list(DEFAULT_JOBLOG_VISIBLE_COLUMNS),
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


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def save_settings(data: dict[str, Any]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp_path.replace(path)


def app_data_dir() -> Path:
    return settings_path().parent


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


def load_gui_settings() -> dict[str, Any]:
    data = load_settings()
    merged = dict(DEFAULT_GUI_SETTINGS)
    for key in ALLOWED_GUI_KEYS:
        if key in data:
            merged[key] = data[key]

    # Backward-compatible migration from previously saved "last used" keys.
    if "default_lang" not in data and "last_lang" in data:
        merged["default_lang"] = data["last_lang"]
    if "default_effort" not in data and "effort" in data:
        merged["default_effort"] = data["effort"]
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
    merged["image_mode"] = str(merged.get("image_mode", "auto") or "auto")
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
    merged["ocr_api_base_url"] = str(merged.get("ocr_api_base_url", "") or "")
    merged["ocr_api_model"] = str(merged.get("ocr_api_model", "") or "")
    ocr_env_value = merged.get("ocr_api_key_env_name")
    if "ocr_api_key_env_name" not in data or not str(ocr_env_value or "").strip():
        ocr_env_value = data.get("ocr_api_key_env", "DEEPSEEK_API_KEY")
    merged["ocr_api_key_env_name"] = str(ocr_env_value or "DEEPSEEK_API_KEY")
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
    merged["default_images_mode"] = _coerce_choice(
        merged.get("default_images_mode"),
        default="auto",
        allowed={"off", "auto", "always"},
    )
    merged["default_workers"] = max(1, min(6, _coerce_int(merged.get("default_workers"), 3)))
    merged["default_resume"] = _coerce_bool(merged.get("default_resume"), True)
    merged["default_keep_intermediates"] = _coerce_bool(merged.get("default_keep_intermediates"), True)
    merged["default_page_breaks"] = _coerce_bool(merged.get("default_page_breaks"), True)
    merged["default_start_page"] = max(1, _coerce_int(merged.get("default_start_page"), 1))
    merged["default_end_page"] = _coerce_optional_int(merged.get("default_end_page"))
    merged["default_outdir"] = str(merged.get("default_outdir", "") or "")
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
    merged["perf_timeout_text_seconds"] = max(5, _coerce_int(merged.get("perf_timeout_text_seconds"), 90))
    merged["perf_timeout_image_seconds"] = max(5, _coerce_int(merged.get("perf_timeout_image_seconds"), 120))
    merged["adaptive_effort_enabled"] = _coerce_bool(merged.get("adaptive_effort_enabled"), False)
    merged["adaptive_effort_xhigh_only_when_image_or_validator_fail"] = _coerce_bool(
        merged.get("adaptive_effort_xhigh_only_when_image_or_validator_fail"),
        True,
    )
    merged["diagnostics_show_cost_summary"] = _coerce_bool(merged.get("diagnostics_show_cost_summary"), True)
    merged["diagnostics_verbose_metadata_logs"] = _coerce_bool(
        merged.get("diagnostics_verbose_metadata_logs"),
        False,
    )
    merged["min_chars_to_accept_ocr"] = max(20, _coerce_int(merged.get("min_chars_to_accept_ocr"), 200))
    return merged


def save_gui_settings(values: dict[str, Any]) -> None:
    data = load_settings()
    data["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
    for key in ALLOWED_GUI_KEYS:
        if key in values:
            data[key] = values[key]
    save_settings(data)


def load_joblog_settings() -> dict[str, Any]:
    data = load_settings()
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
    merged["vocab_entities"] = _coerce_str_list(
        merged.get("vocab_entities"),
        fallback=DEFAULT_VOCAB_CASE_ENTITIES,
    )
    merged["joblog_visible_columns"] = _coerce_str_list(
        merged.get("joblog_visible_columns"),
        fallback=DEFAULT_JOBLOG_VISIBLE_COLUMNS,
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
    merged["ocr_api_base_url"] = str(merged.get("ocr_api_base_url", "") or "")
    merged["ocr_api_model"] = str(merged.get("ocr_api_model", "") or "")
    ocr_env_value = merged.get("ocr_api_key_env_name")
    if "ocr_api_key_env_name" not in data or not str(ocr_env_value or "").strip():
        ocr_env_value = data.get("ocr_api_key_env", "DEEPSEEK_API_KEY")
    merged["ocr_api_key_env_name"] = str(ocr_env_value or "DEEPSEEK_API_KEY")
    if not merged["vocab_case_entities"]:
        merged["vocab_case_entities"] = list(merged["vocab_entities"])
    if not merged["vocab_service_entities"]:
        merged["vocab_service_entities"] = list(merged["vocab_entities"])
    return merged


def save_joblog_settings(values: dict[str, Any]) -> None:
    data = load_settings()
    data["settings_schema_version"] = SETTINGS_SCHEMA_VERSION
    for key in ALLOWED_JOBLOG_KEYS:
        if key in values:
            data[key] = values[key]
    save_settings(data)


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
