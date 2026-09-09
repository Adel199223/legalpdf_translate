"""Source-document helpers for PDF and single-image inputs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from .browser_pdf_bundle import (
    browser_pdf_bundle_page_count,
    browser_pdf_bundle_page_image_path,
)
from .types import OcrMode

if TYPE_CHECKING:
    from .ocr_engine import OCREngine, OcrResult
    from .pdf_text_order import OrderedPageText

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


def _blank_ordered_page_text() -> "OrderedPageText":
    from .pdf_text_order import OrderedPageText

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
        page_width=0.0,
        page_height=0.0,
        body_blocks=tuple(),
    )


def source_has_browser_pdf_bundle(path: Path) -> bool:
    return is_pdf_source(path) and browser_pdf_bundle_page_count(path) is not None


def get_source_page_count(path: Path) -> int:
    if is_pdf_source(path):
        bundle_page_count = browser_pdf_bundle_page_count(path)
        if isinstance(bundle_page_count, int) and bundle_page_count > 0:
            return bundle_page_count
        from .pdf_text_order import get_page_count

        return get_page_count(path)
    if is_image_source(path):
        return 1
    raise ValueError(f"Unsupported source file type: {path}")


def extract_ordered_source_text(path: Path, page_index: int, *, preserve_structure: bool = False) -> "OrderedPageText":
    if is_pdf_source(path):
        if source_has_browser_pdf_bundle(path):
            return _blank_ordered_page_text()
        from .pdf_text_order import extract_ordered_page_text

        return extract_ordered_page_text(path, page_index, **({"preserve_structure": True} if preserve_structure else {}))
    if not is_image_source(path):
        raise ValueError(f"Unsupported source file type: {path}")
    if page_index != 0:
        raise ValueError("Image sources expose exactly one page at page_index=0.")
    return _blank_ordered_page_text()


def source_page_identity(path: Path, page_number: int) -> dict:
    """Read source/raster hashes without native imports for browser bundles."""
    if type(page_number) is not int or page_number < 1:
        raise ValueError("Source page number must be positive.")
    if not is_supported_source_file(path):
        raise ValueError("Unsupported source file.")
    def digest(file: Path) -> str:
        with file.open("rb") as stream:
            return hashlib.file_digest(stream, "sha256").hexdigest()
    image_path = browser_pdf_bundle_page_image_path(path, page_number) if is_pdf_source(path) else path
    if is_pdf_source(path) and source_has_browser_pdf_bundle(path) and image_path is None:
        raise ValueError("Browser PDF page image evidence is unavailable.")
    if is_image_source(path) and page_number != 1:
        raise ValueError("Image sources expose exactly one page.")
    return {"source_file_sha256": digest(path), "image_sha256": digest(image_path) if image_path is not None else "",
            "source_type": "browser_pdf_image" if is_pdf_source(path) and image_path is not None else source_type_label(path),
            "paper_size_basis": "a4_assumed" if image_path is not None else "source_pdf"}


def source_page_dimensions(path: Path, page_number: int) -> tuple[float, float]:
    """OCR uses raster-oriented PDF dimensions; images explicitly assume A4."""
    if source_page_identity(path, page_number)["paper_size_basis"] == "a4_assumed":
        return 595.276, 841.89
    import fitz
    import math
    with fitz.open(path) as document:
        rect = document.load_page(page_number - 1).rect
        size = float(rect.width), float(rect.height)
    if any(not math.isfinite(value) or not 1 <= value <= 20000 for value in size):
        raise ValueError("Invalid source paper dimensions.")
    return size


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
        bundle_page_path = browser_pdf_bundle_page_image_path(path, page_index + 1)
        if bundle_page_path is not None:
            from .image_io import render_image_file_data_url

            return render_image_file_data_url(
                bundle_page_path,
                save_path=save_path,
                max_data_url_bytes=max_data_url_bytes,
            )
        from .image_io import render_page_image_data_url

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
    from .image_io import render_image_file_data_url

    return render_image_file_data_url(
        path,
        save_path=save_path,
        max_data_url_bytes=max_data_url_bytes,
    )


def ocr_source_page_text(
    path: Path,
    page_number: int,
    mode: OcrMode,
    engine: "OCREngine",
    *,
    prefer_header: bool = False,
    lang_hint: str | None = None,
    preserve_structure: bool = False,
) -> "OcrResult":
    options = {"preserve_structure": True} if preserve_structure and not prefer_header and mode != OcrMode.OFF else {}
    identity = source_page_identity(path, page_number) if options else None
    def finish(result):
        if options:
            if source_page_identity(path, page_number) != identity:
                result.text, result.chars, result.structure = "", 0, None
                result.failed_reason = "Source changed during OCR; source review is required."
            result.structure_metadata = {**(result.structure_metadata or {}),
                                         "source_identity": identity, "source_page_number": page_number}
        return result
    if is_pdf_source(path):
        bundle_page_path = browser_pdf_bundle_page_image_path(path, page_number)
        if bundle_page_path is not None:
            from .ocr_helpers import ocr_image_file_text

            return finish(ocr_image_file_text(
                bundle_page_path,
                mode,
                engine,
                prefer_header=prefer_header,
                lang_hint=lang_hint,
                **options,
            ))
        from .ocr_helpers import ocr_pdf_page_text

        return finish(ocr_pdf_page_text(
            path,
            page_number,
            mode,
            engine,
            prefer_header=prefer_header,
            lang_hint=lang_hint,
            **options,
        ))
    if not is_image_source(path):
        raise ValueError(f"Unsupported source file type: {path}")
    if page_number != 1:
        raise ValueError("Image sources expose exactly one page at page_number=1.")
    from .ocr_helpers import ocr_image_file_text

    return finish(ocr_image_file_text(
        path,
        mode,
        engine,
        prefer_header=prefer_header,
        lang_hint=lang_hint,
        **options,
    ))


def ocr_source_page_crop_text(
    path: Path,
    page_number: int,
    crop_rect: tuple[float, float, float, float],
    mode: OcrMode,
    engine: "OCREngine",
    *,
    lang_hint: str | None = None,
) -> "OcrResult":
    if is_pdf_source(path):
        bundle_page_path = browser_pdf_bundle_page_image_path(path, page_number)
        if bundle_page_path is not None:
            from .ocr_helpers import ocr_image_file_text

            return ocr_image_file_text(
                bundle_page_path,
                mode,
                engine,
                prefer_header=False,
                lang_hint=lang_hint,
            )
        from .ocr_helpers import ocr_pdf_page_crop_text

        return ocr_pdf_page_crop_text(
            path,
            page_number,
            crop_rect,
            mode,
            engine,
            lang_hint=lang_hint,
        )
    if not is_image_source(path):
        raise ValueError(f"Unsupported source file type: {path}")
    if page_number != 1:
        raise ValueError("Image sources expose exactly one page at page_number=1.")
    from .ocr_helpers import ocr_image_file_text

    return ocr_image_file_text(
        path,
        mode,
        engine,
        prefer_header=False,
        lang_hint=lang_hint,
    )


__all__ = [
    "SOURCE_FILE_DIALOG_FILTER",
    "extract_ordered_source_text",
    "get_source_page_count",
    "is_image_source",
    "is_pdf_source",
    "is_supported_source_file",
    "ocr_source_page_crop_text",
    "ocr_source_page_text",
    "render_source_page_image_data_url",
    "source_has_browser_pdf_bundle",
    "source_type_label",
]
