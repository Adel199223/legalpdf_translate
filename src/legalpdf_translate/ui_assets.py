"""UI asset loading helpers for source and PyInstaller environments."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageTk
from .resources_loader import resource_path as _shared_resource_path

_pil_cache: dict[str, Image.Image] = {}
_photo_cache: dict[tuple[str, tuple[int, int] | None], ImageTk.PhotoImage] = {}


def resource_path(rel_path: str) -> Path:
    return _shared_resource_path(rel_path)


def load_image(rel_path: str, size: tuple[int, int] | None = None) -> ImageTk.PhotoImage:
    key = (rel_path.replace("\\", "/"), size)
    cached_photo = _photo_cache.get(key)
    if cached_photo is not None:
        return cached_photo

    source_key = rel_path.replace("\\", "/")
    source_image = _pil_cache.get(source_key)
    if source_image is None:
        path = resource_path(rel_path)
        if not path.exists():
            raise FileNotFoundError(f"UI asset not found: {path}")
        source_image = Image.open(path).convert("RGBA")
        _pil_cache[source_key] = source_image

    rendered = source_image
    if size is not None:
        width = max(1, int(size[0]))
        height = max(1, int(size[1]))
        if (width, height) != source_image.size:
            resampling = getattr(Image, "Resampling", Image)
            rendered = source_image.resize((width, height), resampling.LANCZOS)

    photo = ImageTk.PhotoImage(rendered)
    _photo_cache[key] = photo
    return photo
