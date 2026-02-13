from pathlib import Path
from zipfile import ZipFile

from docx import Document

import legalpdf_translate.docx_writer as docx_writer
from legalpdf_translate.docx_writer import assemble_docx, sanitize_bidi_controls
from legalpdf_translate.types import TargetLang


def _write_page(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_assemble_docx_has_no_empty_paragraphs_and_page_break(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    _write_page(pages_dir / "page_0001.txt", "Line A\n\nLine B")
    _write_page(pages_dir / "page_0002.txt", "Line C")
    out = tmp_path / "out.docx"

    assemble_docx(pages_dir, out, lang=TargetLang.EN, page_breaks=True)

    doc = Document(out)
    texts = [p.text for p in doc.paragraphs]
    assert "" not in texts
    assert texts == ["Line A", "Line B", "Line C"]
    assert 'w:type="page"' in doc.element.xml


def test_assemble_docx_arabic_sets_rtl_bidi_flags(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    _write_page(pages_dir / "page_0001.txt", "النص \u2066[[ABC-123]]\u2069")
    out = tmp_path / "ar.docx"

    assemble_docx(pages_dir, out, lang=TargetLang.AR, page_breaks=False)

    doc = Document(out)
    paragraph_xml = doc.paragraphs[0]._p.xml
    assert "<w:bidi" in paragraph_xml
    assert "<w:rtl" in paragraph_xml


def test_save_document_atomic_fsyncs_temp_file(tmp_path: Path, monkeypatch) -> None:
    pages_dir = tmp_path / "pages"
    _write_page(pages_dir / "page_0001.txt", "Line A")
    out = tmp_path / "out.docx"

    calls = {"count": 0}
    original_fsync = docx_writer.os.fsync

    def _counting_fsync(fd: int) -> None:
        calls["count"] += 1
        original_fsync(fd)

    monkeypatch.setattr(docx_writer.os, "fsync", _counting_fsync)
    assemble_docx(pages_dir, out, lang=TargetLang.EN, page_breaks=False)

    assert out.exists()
    assert calls["count"] >= 1


def test_sanitize_bidi_controls_removes_expected_codepoints_only() -> None:
    text = "A \u2066[[ABC-123]]\u2069 \u200eB\u200f \u202aC\u202e \u061cD\ufeff."

    sanitized = sanitize_bidi_controls(text)

    assert sanitized == "A [[ABC-123]] B C D."


def test_assemble_docx_strips_bidi_controls_from_document_xml(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    _write_page(
        pages_dir / "page_0001.txt",
        "x\u2066[[TOK]]\u2069 y \u200ez\u200f \u202aA\u202e \u061cB\ufeff",
    )
    out = tmp_path / "clean.docx"

    assemble_docx(pages_dir, out, lang=TargetLang.AR, page_breaks=False)

    with ZipFile(out) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    for marker in ("\u061c", "\u200e", "\u200f", "\u202a", "\u202b", "\u202c", "\u202d", "\u202e", "\u2066", "\u2067", "\u2068", "\u2069", "\ufeff"):
        assert marker not in document_xml
    assert "<w:bidi" in document_xml
    assert "<w:rtl" in document_xml


def test_assemble_docx_can_preserve_bidi_controls_when_requested(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    _write_page(pages_dir / "page_0001.txt", "token \u2066[[ABC-123]]\u2069")
    out = tmp_path / "preserve.docx"

    assemble_docx(
        pages_dir,
        out,
        lang=TargetLang.AR,
        page_breaks=False,
        strip_bidi_controls=False,
    )

    with ZipFile(out) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "\u2066" in document_xml
    assert "\u2069" in document_xml
