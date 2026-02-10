"""DOCX assembly utilities."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .types import TargetLang


def timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def build_output_docx_path(
    output_dir: Path,
    pdf_stem: str,
    lang: TargetLang,
    *,
    partial: bool = False,
) -> Path:
    suffix = "_PARTIAL" if partial else ""
    return output_dir / f"{pdf_stem}_{lang.value}_{timestamp_for_filename()}{suffix}.docx"


def _add_rtl_flags(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    rtl = OxmlElement("w:rtl")
    rtl.set(qn("w:val"), "1")
    p_pr.append(bidi)
    p_pr.append(rtl)


def assemble_docx(
    pages_dir: Path,
    output_path: Path,
    *,
    lang: TargetLang,
    page_breaks: bool,
    up_to_page: int | None = None,
) -> Path:
    page_files = sorted(pages_dir.glob("page_*.txt"))
    if up_to_page is not None:
        page_files = [path for path in page_files if int(path.stem.split("_")[1]) <= up_to_page]

    document = Document()
    if document.paragraphs and document.paragraphs[0].text == "":
        first = document.paragraphs[0]._element
        first.getparent().remove(first)
    for page_idx, page_file in enumerate(page_files):
        page_text = page_file.read_text(encoding="utf-8")
        lines = page_text.split("\n")
        for line in lines:
            if line.strip() == "":
                continue
            paragraph = document.add_paragraph(line)
            if lang == TargetLang.AR:
                _add_rtl_flags(paragraph)
        if page_breaks and page_idx < len(page_files) - 1:
            if document.paragraphs:
                run = document.paragraphs[-1].add_run()
            else:
                run = document.add_paragraph().add_run()
            run.add_break(WD_BREAK.PAGE)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(output_path)
    return output_path
