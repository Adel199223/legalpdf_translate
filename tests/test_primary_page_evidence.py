from pathlib import Path

import fitz
import pytest

from legalpdf_translate import ordinary_primary_page_evidence as evidence
from legalpdf_translate.browser_pdf_bundle import (
    browser_pdf_bundle_dir, write_browser_pdf_bundle,
)


def pdf(path: Path, pages: list[str]) -> Path:
    with fitz.open() as document:
        for text in pages:
            document.new_page().insert_text((40, 60), text)
        document.save(path)
    return path


def hints(prompt: str) -> list[str]:
    marker = "also found on this page: "
    if marker not in prompt:
        return []
    return prompt.split(marker, 1)[1].split(". Treat them", 1)[0].split(", ")


def test_visual_field_ownership_and_document_first_use(tmp_path):
    path = pdf(tmp_path / "form.pdf", ["Letter", "NPP NUIPC\nTime: one interval", "NPP NUIPC"])
    first = evidence.primary_visual_guidance(path, 2, (1, 2, 3), "NPP NUIPC Time")
    repeat = evidence.primary_visual_guidance(path, 3, (1, 2, 3), "NUIPC NPP NEW")
    assert not hints(first)
    assert hints(repeat) == ["NPP", "NUIPC"]
    assert "once at the visible row" in first and "genuinely repeated row" in first
    assert "both endpoints" in first and "printed parentheses and punctuation" in first
    assert "Follow explicit approved terminology" in repeat
    assert "no first-use determination" in repeat


def test_only_earlier_selected_whole_strings_in_selected_page_order(tmp_path):
    path = pdf(tmp_path / "source.pdf", ["UNSELECTED", "AAA PARTref", "BBB CCC", "TARGET"])
    result = evidence.primary_visual_guidance(
        path, 4, [3, 2, 4], "UNSELECTED AAA BBB CCC PART CCCC XCCC",
    )
    assert hints(result) == ["BBB", "CCC", "AAA"]
    assert not hints(evidence.primary_visual_guidance(path, 3, (3, 2, 4), "AAA"))


def test_hidden_or_unreliable_text_layer_cannot_mark_first_use(tmp_path):
    path = tmp_path / "hidden.pdf"
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((40, 60), "ABC")
        page.insert_text((40, 80), "HIDDEN", render_mode=3)
        doc.new_page().insert_text((40, 60), "ABC HIDDEN")
        doc.save(path)
    assert not hints(evidence.primary_visual_guidance(path, 2, (1, 2), "ABC HIDDEN"))
    assert not hints(evidence.primary_visual_guidance(path, 2, (1, 2), "ABC\ufffd"))


def test_authenticated_browser_evidence_and_tamper(tmp_path):
    path = tmp_path / "bundle.pdf"
    path.write_bytes(b"browser PDF case")
    pages = []
    for index, text in enumerate(("First ABC", "Again ABC"), 1):
        item = {"text": text, "x": 40, "y": 40, "width": 80, "height": 12,
                "dir": "ltr", "has_eol": True}
        pages.append({"page_number": index, "image_bytes": b"test raster", "mime_type": "image/png",
                      "width_px": 600, "height_px": 800,
                      "text_content": {"version": 1, "page_number": index, "page_width": 600,
                                       "page_height": 800, "items": [item]}})
    manifest = write_browser_pdf_bundle(source_path=path, page_count=2, pages=pages)
    assert hints(evidence.primary_visual_guidance(path, 2, [1, 2], "ABC")) == ["ABC"]
    sidecar = browser_pdf_bundle_dir(path) / manifest["pages"][0]["text_path"]
    sidecar.write_bytes(b"{}")
    assert not hints(evidence.primary_visual_guidance(path, 2, [1, 2], "ABC"))


@pytest.mark.parametrize("selection,page", [([1, True, 2], 2), ([1, 1, 2], 2), ([1], 2),
                                            (range(1, 14), 2), ([1, 2], True)])
def test_invalid_or_oversized_scope_does_not_open_the_pdf(tmp_path, monkeypatch, selection, page):
    path = pdf(tmp_path / "small.pdf", ["ABC", "ABC"])
    monkeypatch.setattr(fitz, "open", lambda *a, **k: pytest.fail("Unexpected PDF read"))
    assert not hints(evidence.primary_visual_guidance(path, page, selection, "ABC"))


def test_caps_on_input_file_text_hint_list_and_non_pdf(tmp_path, monkeypatch):
    words = " ".join("A" + chr(65 + n) for n in range(18))
    path = pdf(tmp_path / "small.pdf", [words, words])
    assert len(hints(evidence.primary_visual_guidance(path, 2, [1, 2], words))) == 12
    assert not hints(evidence.primary_visual_guidance(path, 2, [1, 2], words * 1_000))
    monkeypatch.setattr(evidence, "_MAX_PDF_BYTES", 1)
    assert not hints(evidence.primary_visual_guidance(path, 2, [1, 2], words))
    assert not hints(evidence.primary_visual_guidance(tmp_path / "image.png", 2, [1, 2], words))
