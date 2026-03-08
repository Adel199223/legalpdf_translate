"""DOCX assembly utilities with atomic save semantics."""

from __future__ import annotations

import os
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .types import TargetLang

_LRM = "\u200e"
_RTL_LANG_BIDI_CODES = {
    "AR": "ar-SA",
    "HE": "he-IL",
    "FA": "fa-IR",
    "UR": "ur-PK",
}
_PLACEHOLDER_RE = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)
_RTL_STRONG_BIDI_CATEGORIES = {"R", "AL"}
_LTR_STRONG_BIDI_CATEGORIES = {"L", "EN", "AN"}
_BIDI_CONTROL_CODEPOINTS = str.maketrans(
    "",
    "",
    "\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069\ufeff",
)
_DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
_VISIBLE_WORD_RE = re.compile(r"\S+")


@dataclass(frozen=True)
class _DocxVisibleContentSummary:
    paragraph_count: int
    visible_paragraph_count: int
    text_node_count: int
    text_char_count: int
    word_count: int


def sanitize_bidi_controls(text: str) -> str:
    if not text:
        return text
    return text.translate(_BIDI_CONTROL_CODEPOINTS)


def unwrap_internal_placeholders(text: str) -> str:
    if not text:
        return text
    return _PLACEHOLDER_RE.sub(lambda match: match.group(1), text)


def _is_rtl_target_lang(lang: TargetLang | str) -> bool:
    if isinstance(lang, TargetLang):
        code = lang.value
    else:
        code = str(lang)
    return code.strip().upper() in _RTL_LANG_BIDI_CODES


def _rtl_bidi_lang_code(lang: TargetLang | str) -> str:
    if isinstance(lang, TargetLang):
        code = lang.value
    else:
        code = str(lang)
    return _RTL_LANG_BIDI_CODES.get(code.strip().upper(), "ar-SA")


def _classify_directional_char(char: str) -> str:
    bidi = unicodedata.bidirectional(char)
    if bidi in _RTL_STRONG_BIDI_CATEGORIES:
        return "rtl"
    if bidi in _LTR_STRONG_BIDI_CATEGORIES:
        return "ltr"
    return "neutral"


def _nearest_strong_kind(segments: list[tuple[str, str]], index: int) -> str | None:
    for lookup in range(index - 1, -1, -1):
        kind = segments[lookup][0]
        if kind != "neutral":
            return kind
    for lookup in range(index + 1, len(segments)):
        kind = segments[lookup][0]
        if kind != "neutral":
            return kind
    return None


def _segment_directional_runs(text: str) -> tuple[list[tuple[str, str]], bool]:
    if not text:
        return [], False

    raw_segments: list[tuple[str, str]] = []
    current_kind = _classify_directional_char(text[0])
    current_chars = [text[0]]

    for char in text[1:]:
        kind = _classify_directional_char(char)
        if kind == current_kind:
            current_chars.append(char)
            continue
        raw_segments.append((current_kind, "".join(current_chars)))
        current_kind = kind
        current_chars = [char]
    raw_segments.append((current_kind, "".join(current_chars)))

    relabeled_segments: list[tuple[str, str]] = []
    for index, (kind, chunk) in enumerate(raw_segments):
        if kind != "neutral":
            relabeled_segments.append((kind, chunk))
            continue
        neighbor_kind = _nearest_strong_kind(raw_segments, index) or "rtl"
        relabeled_segments.append((neighbor_kind, chunk))

    merged_segments: list[tuple[str, str]] = []
    for kind, chunk in relabeled_segments:
        if merged_segments and merged_segments[-1][0] == kind:
            prev_kind, prev_chunk = merged_segments[-1]
            merged_segments[-1] = (prev_kind, f"{prev_chunk}{chunk}")
            continue
        merged_segments.append((kind, chunk))

    has_rtl = any(kind == "rtl" for kind, _ in merged_segments)
    has_ltr = any(kind == "ltr" for kind, _ in merged_segments)
    return merged_segments, has_rtl and has_ltr


def _wrap_ltr_run_with_lrm(text: str) -> str:
    if not text.strip():
        return text
    if text.startswith(_LRM) and text.endswith(_LRM):
        return text
    leading_ws = len(text) - len(text.lstrip())
    trailing_ws = len(text) - len(text.rstrip())
    core_end = len(text) - trailing_ws if trailing_ws else len(text)
    core = text[leading_ws:core_end]
    if not core:
        return text
    return f"{text[:leading_ws]}{_LRM}{core}{_LRM}{text[core_end:]}"


def _add_rtl_flags(paragraph) -> None:
    if paragraph.alignment != WD_ALIGN_PARAGRAPH.CENTER:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_pr = paragraph._p.get_or_add_pPr()
    bidi = p_pr.find(qn("w:bidi"))
    if bidi is None:
        bidi = OxmlElement("w:bidi")
        p_pr.append(bidi)
    bidi.set(qn("w:val"), "1")

    rtl = p_pr.find(qn("w:rtl"))
    if rtl is None:
        rtl = OxmlElement("w:rtl")
        p_pr.append(rtl)
    rtl.set(qn("w:val"), "1")


def _set_rtl_run_props(run, *, bidi_lang: str) -> None:
    r_pr = run._r.get_or_add_rPr()
    rtl = r_pr.find(qn("w:rtl"))
    if rtl is None:
        rtl = OxmlElement("w:rtl")
        r_pr.append(rtl)
    rtl.set(qn("w:val"), "1")

    lang = r_pr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        r_pr.append(lang)
    lang.set(qn("w:val"), bidi_lang)
    lang.set(qn("w:bidi"), bidi_lang)


def _set_ltr_run_props(run, *, lang_code: str = "en-US") -> None:
    r_pr = run._r.get_or_add_rPr()
    rtl = r_pr.find(qn("w:rtl"))
    if rtl is None:
        rtl = OxmlElement("w:rtl")
        r_pr.append(rtl)
    rtl.set(qn("w:val"), "0")

    lang = r_pr.find(qn("w:lang"))
    if lang is None:
        lang = OxmlElement("w:lang")
        r_pr.append(lang)
    lang.set(qn("w:val"), lang_code)


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


def _read_docx_visible_content_summary(path: Path) -> _DocxVisibleContentSummary:
    try:
        with ZipFile(path, "r") as archive:
            document_xml = archive.read("word/document.xml")
    except KeyError as exc:
        raise RuntimeError(f"DOCX is missing word/document.xml: {path}") from exc
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed reading DOCX body XML from {path}: {exc}") from exc

    try:
        root = ET.fromstring(document_xml)
    except ET.ParseError as exc:
        raise RuntimeError(f"DOCX body XML is malformed in {path}: {exc}") from exc

    paragraphs = root.findall(".//w:body/w:p", _DOCX_NS)
    paragraph_count = len(paragraphs)
    visible_paragraph_count = 0
    text_node_count = 0
    text_char_count = 0
    word_count = 0

    for paragraph in paragraphs:
        text_nodes = [node.text or "" for node in paragraph.findall(".//w:t", _DOCX_NS)]
        text_node_count += len(text_nodes)
        paragraph_text = "".join(text_nodes)
        if not paragraph_text.strip():
            continue
        visible_paragraph_count += 1
        text_char_count += len(paragraph_text.strip())
        word_count += len(_VISIBLE_WORD_RE.findall(paragraph_text))

    return _DocxVisibleContentSummary(
        paragraph_count=paragraph_count,
        visible_paragraph_count=visible_paragraph_count,
        text_node_count=text_node_count,
        text_char_count=text_char_count,
        word_count=word_count,
    )


def _verify_docx_visible_content(
    path: Path,
    *,
    stage: str,
    expected_visible_paragraphs: int,
    baseline: _DocxVisibleContentSummary | None = None,
) -> _DocxVisibleContentSummary:
    summary = _read_docx_visible_content_summary(path)
    if expected_visible_paragraphs > 0 and summary.visible_paragraph_count == 0:
        raise RuntimeError(
            f"DOCX content verification failed after {stage}: {path} has no visible paragraphs"
        )
    if expected_visible_paragraphs > 0 and summary.text_char_count == 0:
        raise RuntimeError(
            f"DOCX content verification failed after {stage}: {path} has no visible text"
        )
    if baseline is not None and baseline.visible_paragraph_count > 0 and summary.visible_paragraph_count == 0:
        raise RuntimeError(
            f"DOCX content verification failed after {stage}: {path} lost all visible paragraphs"
        )
    return summary


def _fsync_file(path: Path) -> None:
    try:
        with path.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise RuntimeError(f"Failed to fsync temporary DOCX: {path}") from exc


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
    _fsync_file(tmp_path)
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


# Surgical regex patterns for removing compatibilityMode from settings.xml
# without re-serializing the entire XML (which can break namespace prefixes).
_COMPAT_SETTING_RE = re.compile(
    r'<w:compatSetting\b[^>]*\bw:name\s*=\s*"compatibilityMode"[^>]*/>'
    r"|"
    r'<w:compatSetting\b[^>]*\bw:name\s*=\s*"compatibilityMode"[^>]*>.*?</w:compatSetting>',
    re.DOTALL,
)
_EMPTY_COMPAT_RE = re.compile(
    r"<w:compat\b[^>]*/>\s*"
    r"|"
    r"<w:compat\b[^>]*>\s*</w:compat>\s*",
    re.DOTALL,
)


def _clone_zipinfo_for_rewrite(info: ZipInfo) -> ZipInfo:
    clone = ZipInfo(filename=info.filename, date_time=info.date_time)
    clone.compress_type = info.compress_type
    clone.comment = info.comment
    clone.extra = info.extra
    clone.create_system = info.create_system
    clone.create_version = info.create_version
    clone.extract_version = info.extract_version
    clone.internal_attr = info.internal_attr
    clone.external_attr = info.external_attr
    return clone


def _remove_compatibility_mode(docx_path: Path) -> None:
    """Remove compatibilityMode from word/settings.xml to avoid Word upgrade prompt.

    Uses regex surgery on the raw XML text so that namespace declarations,
    prefix mappings, and mc:Ignorable contracts are preserved byte-for-byte.
    """
    with ZipFile(docx_path, "r") as zin:
        if "word/settings.xml" not in zin.namelist():
            return
        settings_text = zin.read("word/settings.xml").decode("utf-8")

    modified = _COMPAT_SETTING_RE.sub("", settings_text)
    if modified == settings_text:
        return  # Nothing to remove.

    # Clean up empty <w:compat> element if all children were removed.
    modified = _EMPTY_COMPAT_RE.sub("", modified)

    tmp_path = docx_path.with_name(f"{docx_path.name}.compat_tmp")
    try:
        with ZipFile(docx_path, "r") as zin, ZipFile(tmp_path, "w") as zout:
            for item in zin.infolist():
                item_copy = _clone_zipinfo_for_rewrite(item)
                if item.filename == "word/settings.xml":
                    zout.writestr(item_copy, modified.encode("utf-8"))
                else:
                    zout.writestr(item_copy, zin.read(item.filename))
        os.replace(tmp_path, docx_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def assemble_docx(
    pages_dir: Path,
    output_path: Path,
    *,
    lang: TargetLang,
    page_breaks: bool,
    up_to_page: int | None = None,
    strip_bidi_controls: bool = True,
    verify_readable: bool = True,
    stats: dict[str, int] | None = None,
) -> Path:
    page_files = sorted(pages_dir.glob("page_*.txt"))
    if up_to_page is not None:
        page_files = [path for path in page_files if int(path.stem.split("_")[1]) <= up_to_page]
    if not page_files:
        raise RuntimeError(f"No page text files available for DOCX assembly: {pages_dir}")

    document = Document()
    if document.paragraphs and document.paragraphs[0].text == "":
        first = document.paragraphs[0]._element
        first.getparent().remove(first)
    rtl_lang = _is_rtl_target_lang(lang)
    rtl_bidi_lang = _rtl_bidi_lang_code(lang)
    _paragraph_count = 0
    _run_count = 0
    for page_idx, page_file in enumerate(page_files):
        page_text = page_file.read_text(encoding="utf-8")
        lines = page_text.split("\n")
        for line in lines:
            if rtl_lang:
                line = unwrap_internal_placeholders(line)
            if strip_bidi_controls:
                line = sanitize_bidi_controls(line)
            if line.strip() == "":
                continue
            paragraph = document.add_paragraph("")
            _paragraph_count += 1
            if rtl_lang:
                _add_rtl_flags(paragraph)
                directional_runs, has_mixed_direction = _segment_directional_runs(line)
                if not directional_runs:
                    continue
                for kind, run_text in directional_runs:
                    if not run_text:
                        continue
                    if kind == "ltr":
                        if has_mixed_direction:
                            run_text = _wrap_ltr_run_with_lrm(run_text)
                        run = paragraph.add_run(run_text)
                        _run_count += 1
                        _set_ltr_run_props(run)
                        continue
                    run = paragraph.add_run(run_text)
                    _run_count += 1
                    _set_rtl_run_props(run, bidi_lang=rtl_bidi_lang)
            else:
                paragraph.add_run(line)
                _run_count += 1
        if page_breaks and page_idx < len(page_files) - 1:
            if document.paragraphs:
                run = document.paragraphs[-1].add_run()
            else:
                run = document.add_paragraph().add_run()
                _paragraph_count += 1
            _run_count += 1
            run.add_break(WD_BREAK.PAGE)

    if stats is not None:
        stats["paragraph_count"] = _paragraph_count
        stats["run_count"] = _run_count
        stats["page_count"] = len(page_files)
    result_path = save_document_atomic(document, output_path, verify_readable=verify_readable)
    saved_summary = _verify_docx_visible_content(
        result_path,
        stage="save",
        expected_visible_paragraphs=_paragraph_count,
    )
    _remove_compatibility_mode(result_path)
    _verify_docx_visible_content(
        result_path,
        stage="compatibility rewrite",
        expected_visible_paragraphs=_paragraph_count,
        baseline=saved_summary,
    )
    return result_path
