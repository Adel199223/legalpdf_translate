"""Persistent local GUI settings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_FOLDER_NAME = "LegalPDFTranslate"
SETTINGS_FILENAME = "settings.json"


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


def load_last_outdir() -> Path | None:
    data = load_settings()
    value = data.get("last_outdir")
    if not isinstance(value, str):
        return None
    candidate = Path(value).expanduser().resolve()
    if not candidate.exists() or not candidate.is_dir():
        return None
    return candidate


def save_last_outdir(path: Path) -> None:
    data = load_settings()
    data["last_outdir"] = str(path.expanduser().resolve())
    save_settings(data)
