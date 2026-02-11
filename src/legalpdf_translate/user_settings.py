"""Persistent local GUI settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_FOLDER_NAME = "LegalPDFTranslate"
SETTINGS_FILENAME = "settings.json"
ALLOWED_GUI_KEYS = {
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
}
DEFAULT_GUI_SETTINGS: dict[str, Any] = {
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


def load_gui_settings() -> dict[str, Any]:
    data = load_settings()
    merged = dict(DEFAULT_GUI_SETTINGS)
    for key in ALLOWED_GUI_KEYS:
        if key in data:
            merged[key] = data[key]

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
    return merged


def save_gui_settings(values: dict[str, Any]) -> None:
    data = load_settings()
    for key in ALLOWED_GUI_KEYS:
        if key in values:
            data[key] = values[key]
    sanitized: dict[str, Any] = {}
    for key in ALLOWED_GUI_KEYS:
        if key in data:
            sanitized[key] = data[key]
    save_settings(sanitized)


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
