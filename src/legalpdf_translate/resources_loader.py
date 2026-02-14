"""Load static instruction resources in source and frozen modes."""

from __future__ import annotations

import sys
from pathlib import Path

from .types import TargetLang


def _resource_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def resource_path(rel_path: str) -> Path:
    return (_resource_base_dir() / rel_path).resolve()


def get_resources_dir() -> Path:
    return resource_path("resources")


def load_system_instructions(target_lang: TargetLang) -> str:
    resources_dir = get_resources_dir()
    if target_lang == TargetLang.EN:
        filename = "system_instructions_en.txt"
    elif target_lang == TargetLang.FR:
        filename = "system_instructions_fr.txt"
    else:
        filename = "system_instructions_ar.txt"
    path = resources_dir / filename
    return path.read_text(encoding="utf-8")
