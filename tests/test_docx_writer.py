from pathlib import Path

from docx import Document

from legalpdf_translate.docx_writer import assemble_docx
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
