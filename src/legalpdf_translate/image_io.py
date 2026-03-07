"""Page image rendering and data-url generation."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
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
from .types import ImageMode, TargetLang


@dataclass(slots=True)
class RenderedImage:
    data_url: str
    image_bytes: bytes
    encoded_bytes: int
    width_px: int
    height_px: int
    image_format: str
    compress_steps: int


def should_include_image(
    mode: ImageMode,
    ordered_text: str,
    extraction_failed: bool,
    fragmented: bool = False,
    *,
    lang: TargetLang | None = None,
) -> bool:
    if mode == ImageMode.OFF:
        return False
    if mode == ImageMode.ALWAYS:
        return True

    # EN/FR strict auto policy: only extraction failure or effectively no text.
    if lang in (TargetLang.EN, TargetLang.FR):
        if extraction_failed:
            return True
        return len(ordered_text.strip()) < 20

    # AR keeps stricter heuristics.
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
) -> RenderedImage:
    dpi = min(start_dpi, max_dpi)
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_index)
        image = _pixmap_to_pil(page, dpi=dpi)

    quality = IMAGE_INITIAL_QUALITY
    current = image
    image_bytes = _encode_jpeg(current, quality=quality)
    data_url = _data_url_from_bytes(image_bytes)
    compress_steps = 0
    max_bytes_limit = max(256 * 1024, min(max_data_url_bytes, IMAGE_MAX_DATA_URL_BYTES))

    while len(data_url.encode("utf-8")) >= max_bytes_limit:
        compress_steps += 1
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

    encoded_bytes = len(data_url.encode("utf-8"))
    if encoded_bytes >= max_bytes_limit:
        raise RuntimeError("Unable to compress page image below configured data URL limit.")

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(image_bytes)

    return RenderedImage(
        data_url=data_url,
        image_bytes=image_bytes,
        encoded_bytes=encoded_bytes,
        width_px=current.width,
        height_px=current.height,
        image_format="jpeg",
        compress_steps=compress_steps,
    )


def render_image_file_data_url(
    image_path: Path,
    save_path: Path | None = None,
    *,
    max_data_url_bytes: int = IMAGE_MAX_DATA_URL_BYTES,
) -> RenderedImage:
    current = Image.open(image_path)
    if current.mode != "RGB":
        current = current.convert("RGB")

    quality = IMAGE_INITIAL_QUALITY
    image_bytes = _encode_jpeg(current, quality=quality)
    data_url = _data_url_from_bytes(image_bytes)
    compress_steps = 0
    max_bytes_limit = max(256 * 1024, min(max_data_url_bytes, IMAGE_MAX_DATA_URL_BYTES))

    while len(data_url.encode("utf-8")) >= max_bytes_limit:
        compress_steps += 1
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

    encoded_bytes = len(data_url.encode("utf-8"))
    if encoded_bytes >= max_bytes_limit:
        raise RuntimeError("Unable to compress image below configured data URL limit.")

    if save_path is not None:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        save_path.write_bytes(image_bytes)

    return RenderedImage(
        data_url=data_url,
        image_bytes=image_bytes,
        encoded_bytes=encoded_bytes,
        width_px=current.width,
        height_px=current.height,
        image_format="jpeg",
        compress_steps=compress_steps,
    )
