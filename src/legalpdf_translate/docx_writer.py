"""DOCX assembly utilities with atomic save semantics."""

from __future__ import annotations

import os
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .types import TargetLang


def _add_rtl_flags(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    rtl = OxmlElement("w:rtl")
    rtl.set(qn("w:val"), "1")
    p_pr.append(bidi)
    p_pr.append(rtl)


def _verify_non_empty_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"DOCX file was not created: {path}")
    if path.stat().st_size <= 0:
        raise RuntimeError(f"DOCX file is empty: {path}")


def _verify_docx_readable(path: Path) -> None:
    try:
        Document(path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"DOCX validation failed for {path}: {exc}") from exc


def resolve_noncolliding_output_path(output_path: Path) -> Path:
    final_path = output_path.expanduser().resolve()
    if not final_path.exists():
        return final_path

    stem = final_path.stem
    suffix = final_path.suffix
    index = 1
    while True:
        candidate = final_path.with_name(f"{stem}_{index:02d}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def save_document_atomic(
    document: Document,
    output_path: Path,
    *,
    verify_readable: bool = True,
) -> Path:
    final_path = resolve_noncolliding_output_path(output_path)
    tmp_path = final_path.with_name(f"{final_path.name}.tmp")

    final_path.parent.mkdir(parents=True, exist_ok=True)
    if tmp_path.exists():
        tmp_path.unlink()

    try:
        document.save(tmp_path)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed writing temporary DOCX: {tmp_path}") from exc

    _verify_non_empty_file(tmp_path)
    if verify_readable:
        _verify_docx_readable(tmp_path)

    try:
        os.replace(tmp_path, final_path)
    except OSError as exc:
        raise RuntimeError(f"Failed to atomically replace DOCX at {final_path}") from exc

    _verify_non_empty_file(final_path)
    if verify_readable:
        _verify_docx_readable(final_path)
    return final_path


def assemble_docx(
    pages_dir: Path,
    output_path: Path,
    *,
    lang: TargetLang,
    page_breaks: bool,
    up_to_page: int | None = None,
    verify_readable: bool = True,
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

    return save_document_atomic(document, output_path, verify_readable=verify_readable)
