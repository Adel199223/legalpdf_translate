"""PDF rendering helpers for OCR workflows."""

from __future__ import annotations

import io
from pathlib import Path

import fitz
from PIL import Image

from .ocr_engine import OCREngine, OcrResult, invoke_ocr_image
from .types import OcrMode


def _page_to_png_bytes(page: fitz.Page, *, dpi: int) -> bytes:
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_page_png(pdf_path: Path, page_number: int, dpi: int = 200) -> bytes:
    page_index = int(page_number) - 1
    if page_index < 0:
        raise ValueError("page_number must be >= 1")
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_index)
        return _page_to_png_bytes(page, dpi=dpi)


def render_header_png(
    pdf_path: Path,
    page_number: int,
    dpi: int = 200,
    header_ratio: float = 0.22,
) -> bytes:
    page_png = render_page_png(pdf_path, page_number, dpi=dpi)
    image = Image.open(io.BytesIO(page_png))
    if image.mode != "RGB":
        image = image.convert("RGB")
    header_height = max(1, int(float(image.height) * float(header_ratio)))
    header = image.crop((0, 0, image.width, header_height))
    buffer = io.BytesIO()
    header.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_image_png(image_path: Path) -> bytes:
    image = Image.open(image_path)
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def render_image_header_png(
    image_path: Path,
    *,
    header_ratio: float = 0.22,
) -> bytes:
    image_png = render_image_png(image_path)
    image = Image.open(io.BytesIO(image_png))
    if image.mode != "RGB":
        image = image.convert("RGB")
    header_height = max(1, int(float(image.height) * float(header_ratio)))
    header = image.crop((0, 0, image.width, header_height))
    buffer = io.BytesIO()
    header.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def ocr_pdf_page_text(
    pdf_path: Path,
    page_number: int,
    mode: OcrMode,
    engine: OCREngine,
    *,
    prefer_header: bool = False,
    lang_hint: str | None = None,
) -> OcrResult:
    if mode == OcrMode.OFF:
        return OcrResult(text="", engine="none", failed_reason="ocr disabled by mode=off", chars=0)
    try:
        image_bytes = (
            render_header_png(pdf_path, page_number)
            if prefer_header
            else render_page_png(pdf_path, page_number)
        )
    except Exception as exc:  # noqa: BLE001
        return OcrResult(text="", engine="none", failed_reason=f"render failed: {exc}", chars=0)
    return invoke_ocr_image(engine, image_bytes, lang_hint=lang_hint, source_type="pdf")


def ocr_image_file_text(
    image_path: Path,
    mode: OcrMode,
    engine: OCREngine,
    *,
    prefer_header: bool = False,
    lang_hint: str | None = None,
) -> OcrResult:
    if mode == OcrMode.OFF:
        return OcrResult(text="", engine="none", failed_reason="ocr disabled by mode=off", chars=0)
    try:
        image_bytes = render_image_header_png(image_path) if prefer_header else render_image_png(image_path)
    except Exception as exc:  # noqa: BLE001
        return OcrResult(text="", engine="none", failed_reason=f"render failed: {exc}", chars=0)
    return invoke_ocr_image(engine, image_bytes, lang_hint=lang_hint, source_type="image")
