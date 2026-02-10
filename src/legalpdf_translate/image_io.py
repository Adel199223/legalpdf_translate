"""Page image rendering and data-url generation."""

from __future__ import annotations

import base64
import io
from pathlib import Path

import fitz
from PIL import Image

from .config import (
    AUTO_IMAGE_NEWLINE_RATIO_MAX_TEXT_LENGTH,
    AUTO_IMAGE_NEWLINE_RATIO_THRESHOLD,
    AUTO_IMAGE_TEXT_LENGTH_THRESHOLD,
    IMAGE_INITIAL_DPI,
    IMAGE_INITIAL_QUALITY,
    IMAGE_MAX_DATA_URL_BYTES,
    IMAGE_MAX_DPI,
    IMAGE_MIN_QUALITY,
    IMAGE_SCALE_FACTOR,
)
from .types import ImageMode


def should_include_image(
    mode: ImageMode,
    ordered_text: str,
    extraction_failed: bool,
    fragmented: bool = False,
) -> bool:
    if mode == ImageMode.OFF:
        return False
    if mode == ImageMode.ALWAYS:
        return True

    if extraction_failed:
        return True
    if ordered_text.strip() == "":
        return True

    text_length = len(ordered_text)
    if text_length < AUTO_IMAGE_TEXT_LENGTH_THRESHOLD:
        return True

    ratio = ordered_text.count("\n") / max(text_length, 1)
    if ratio > AUTO_IMAGE_NEWLINE_RATIO_THRESHOLD and text_length < AUTO_IMAGE_NEWLINE_RATIO_MAX_TEXT_LENGTH:
        return True

    if fragmented:
        return True
    return False


def _pixmap_to_pil(page: fitz.Page, dpi: int) -> Image.Image:
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def _encode_jpeg(image: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()


def _data_url_from_bytes(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def render_page_image_data_url(
    pdf_path: Path,
    page_index: int,
    save_path: Path | None = None,
    start_dpi: int = IMAGE_INITIAL_DPI,
    max_dpi: int = IMAGE_MAX_DPI,
    max_data_url_bytes: int = IMAGE_MAX_DATA_URL_BYTES,
) -> tuple[str, bytes]:
    dpi = min(start_dpi, max_dpi)
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_index)
        image = _pixmap_to_pil(page, dpi=dpi)

    quality = IMAGE_INITIAL_QUALITY
    current = image
    image_bytes = _encode_jpeg(current, quality=quality)
    data_url = _data_url_from_bytes(image_bytes)

    while len(data_url.encode("utf-8")) >= max_data_url_bytes:
        if quality > IMAGE_MIN_QUALITY:
            quality = max(IMAGE_MIN_QUALITY, quality - 10)
        else:
            new_width = max(640, int(current.width * IMAGE_SCALE_FACTOR))
            new_height = max(640, int(current.height * IMAGE_SCALE_FACTOR))
            if new_width == current.width and new_height == current.height:
                break
            current = current.resize((new_width, new_height), Image.Resampling.LANCZOS)
        image_bytes = _encode_jpeg(current, quality=quality)
        data_url = _data_url_from_bytes(image_bytes)

    if len(data_url.encode("utf-8")) >= max_data_url_bytes:
        raise RuntimeError("Unable to compress page image below 20MB data URL limit.")

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(image_bytes)

    return data_url, image_bytes
