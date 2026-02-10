"""Load static instruction resources in source and frozen modes."""

from __future__ import annotations

import sys
from pathlib import Path

from .types import TargetLang


def get_resources_dir() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "resources"
        return Path(sys.executable).resolve().parent / "resources"
    return Path(__file__).resolve().parents[2] / "resources"


def load_system_instructions(target_lang: TargetLang) -> str:
    resources_dir = get_resources_dir()
    if target_lang in (TargetLang.EN, TargetLang.FR):
        filename = "system_instructions_enfr.txt"
    else:
        filename = "system_instructions_ar.txt"
    path = resources_dir / filename
    return path.read_text(encoding="utf-8")
