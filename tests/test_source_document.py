from __future__ import annotations

import builtins
import io
from pathlib import Path

from PIL import Image
import pytest

from legalpdf_translate.browser_pdf_bundle import write_browser_pdf_bundle
from legalpdf_translate.ocr_engine import OcrResult
from legalpdf_translate.source_document import (
    ocr_source_page_text,
    render_source_page_image_data_url,
)
from legalpdf_translate.source_document import (
    extract_ordered_source_text,
    get_source_page_count,
    is_image_source,
    is_supported_source_file,
    source_type_label,
)
from legalpdf_translate.types import OcrMode


def test_image_source_helpers_accept_common_suffixes(tmp_path: Path) -> None:
    image_path = tmp_path / "photo.JPG"
    image_path.write_bytes(b"not-a-real-image")

    assert is_image_source(image_path) is True
    assert is_supported_source_file(image_path) is True
    assert source_type_label(image_path) == "image"
    assert get_source_page_count(image_path) == 1


def test_extract_ordered_source_text_for_image_returns_blank_failed_text(tmp_path: Path) -> None:
    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"png")

    ordered = extract_ordered_source_text(image_path, 0)

    assert ordered.text == ""
    assert ordered.extraction_failed is True


def test_extract_ordered_source_text_rejects_nonzero_image_page_index(tmp_path: Path) -> None:
    image_path = tmp_path / "scan.png"
    image_path.write_bytes(b"png")

    with pytest.raises(ValueError, match="exactly one page"):
        extract_ordered_source_text(image_path, 1)


def test_browser_pdf_bundle_short_circuits_native_pdf_imports(tmp_path: Path, monkeypatch) -> None:
    source_pdf = tmp_path / "bundle-source.pdf"
    source_pdf.write_bytes(b"%PDF-1.7\n")
    image = Image.new("RGB", (24, 18), color=(255, 255, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    write_browser_pdf_bundle(
        source_path=source_pdf,
        page_count=1,
        pages=[
            {
                "page_number": 1,
                "mime_type": "image/png",
                "width_px": 24,
                "height_px": 18,
                "image_bytes": buffer.getvalue(),
            }
        ],
    )

    original_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = str(name or "").split(".", 1)[0]
        if root in {"fitz", "pymupdf", "mupdf"}:
            raise AssertionError(f"native PDF runtime should not be imported for bundle-backed source: {name}")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    assert get_source_page_count(source_pdf) == 1
    ordered = extract_ordered_source_text(source_pdf, 0)
    assert ordered.text == ""
    assert ordered.extraction_failed is True

    rendered = render_source_page_image_data_url(source_pdf, 0)
    assert rendered.data_url.startswith("data:image/jpeg;base64,")

    import legalpdf_translate.ocr_helpers as ocr_helpers

    monkeypatch.setattr(
        ocr_helpers,
        "invoke_ocr_image",
        lambda engine, image_bytes, **kwargs: OcrResult(
            text="bundle ocr",
            engine="stub",
            failed_reason="",
            chars=10,
        ),
    )
    ocr_result = ocr_source_page_text(source_pdf, 1, OcrMode.AUTO, object())
    assert ocr_result.text == "bundle ocr"
