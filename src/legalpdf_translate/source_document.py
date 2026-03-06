"""Source-document helpers for PDF and single-image inputs."""

from __future__ import annotations

from pathlib import Path

from .image_io import render_image_file_data_url, render_page_image_data_url
from .ocr_engine import OCREngine, OcrResult
from .ocr_helpers import ocr_image_file_text, ocr_pdf_page_text
from .pdf_text_order import OrderedPageText, extract_ordered_page_text, get_page_count
from .types import OcrMode

SUPPORTED_IMAGE_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

SOURCE_FILE_DIALOG_FILTER = (
    "Supported Files (*.pdf *.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;"
    "PDF Files (*.pdf);;"
    "Image Files (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff);;"
    "All Files (*.*)"
)


def is_image_source(path: Path) -> bool:
    return path.suffix.strip().lower() in SUPPORTED_IMAGE_SUFFIXES


def is_pdf_source(path: Path) -> bool:
    return path.suffix.strip().lower() == ".pdf"


def is_supported_source_file(path: Path) -> bool:
    return is_pdf_source(path) or is_image_source(path)


def source_type_label(path: Path) -> str:
    if is_pdf_source(path):
        return "pdf"
    if is_image_source(path):
        return "image"
    return "unsupported"


def get_source_page_count(path: Path) -> int:
    if is_pdf_source(path):
        return get_page_count(path)
    if is_image_source(path):
        return 1
    raise ValueError(f"Unsupported source file type: {path}")


def extract_ordered_source_text(path: Path, page_index: int) -> OrderedPageText:
    if is_pdf_source(path):
        return extract_ordered_page_text(path, page_index)
    if not is_image_source(path):
        raise ValueError(f"Unsupported source file type: {path}")
    if page_index != 0:
        raise ValueError("Image sources expose exactly one page at page_index=0.")
    return OrderedPageText(
        text="",
        extraction_failed=True,
        newline_to_char_ratio=0.0,
        fragmented=False,
        block_count=0,
        header_blocks_count=0,
        footer_blocks_count=0,
        barcode_blocks_count=0,
        body_blocks_count=0,
        two_column_detected=False,
    )


def render_source_page_image_data_url(
    path: Path,
    page_index: int,
    save_path: Path | None = None,
    *,
    start_dpi: int = 144,
    max_dpi: int = 220,
    max_data_url_bytes: int = 2_200_000,
):
    if is_pdf_source(path):
        return render_page_image_data_url(
            path,
            page_index,
            save_path=save_path,
            start_dpi=start_dpi,
            max_dpi=max_dpi,
            max_data_url_bytes=max_data_url_bytes,
        )
    if not is_image_source(path):
        raise ValueError(f"Unsupported source file type: {path}")
    if page_index != 0:
        raise ValueError("Image sources expose exactly one page at page_index=0.")
    return render_image_file_data_url(
        path,
        save_path=save_path,
        max_data_url_bytes=max_data_url_bytes,
    )


def ocr_source_page_text(
    path: Path,
    page_number: int,
    mode: OcrMode,
    engine: OCREngine,
    *,
    prefer_header: bool = False,
    lang_hint: str | None = None,
) -> OcrResult:
    if is_pdf_source(path):
        return ocr_pdf_page_text(
            path,
            page_number,
            mode,
            engine,
            prefer_header=prefer_header,
            lang_hint=lang_hint,
        )
    if not is_image_source(path):
        raise ValueError(f"Unsupported source file type: {path}")
    if page_number != 1:
        raise ValueError("Image sources expose exactly one page at page_number=1.")
    return ocr_image_file_text(
        path,
        mode,
        engine,
        prefer_header=prefer_header,
        lang_hint=lang_hint,
    )
