"""Static configuration values and environment helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from dotenv import load_dotenv

OPENAI_MODEL: Final[str] = "gpt-5.2"
OPENAI_STORE: Final[bool] = False

DEFAULT_REASONING_EFFORT: Final[str] = "high"
RETRY_REASONING_EFFORT: Final[str] = "medium"

RUN_STATE_VERSION: Final[int] = 3

IMAGE_MAX_DATA_URL_BYTES: Final[int] = 20 * 1024 * 1024
IMAGE_INITIAL_DPI: Final[int] = 200
IMAGE_MAX_DPI: Final[int] = 250
IMAGE_MIN_QUALITY: Final[int] = 35
IMAGE_INITIAL_QUALITY: Final[int] = 85
IMAGE_SCALE_FACTOR: Final[float] = 0.85

AUTO_IMAGE_TEXT_LENGTH_THRESHOLD: Final[int] = 40
AUTO_IMAGE_NEWLINE_RATIO_THRESHOLD: Final[float] = 0.12
AUTO_IMAGE_NEWLINE_RATIO_MAX_TEXT_LENGTH: Final[int] = 1500

TOP_ZONE_RATIO: Final[float] = 0.15
BOTTOM_ZONE_RATIO: Final[float] = 0.15

CONTEXT_EMPTY_HASH_MARKER: Final[str] = "NO_CONTEXT"


def load_environment(dotenv_path: Path | None = None) -> None:
    """Load environment variables from .env when available."""
    if dotenv_path is None:
        load_dotenv()
        return
    load_dotenv(dotenv_path=dotenv_path)
