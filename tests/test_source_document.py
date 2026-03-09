from __future__ import annotations

from pathlib import Path

import pytest

from legalpdf_translate.source_document import (
    extract_ordered_source_text,
    get_source_page_count,
    is_image_source,
    is_supported_source_file,
    source_type_label,
)


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
