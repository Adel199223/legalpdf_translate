"""Rich Word 2013+ OOXML assembler for gemini_structural_v1 PageStructuralDocument IR."""

from __future__ import annotations

from dataclasses import dataclass
import io
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from .docx_writer import (
    _LRM,
    _append_block_text,
    _classify_directional_char,
    _ensure_primary_compatibility_mode15,
    _is_rtl_target_lang,
    _set_ltr_run_props,
    _set_rtl_visual_alignment,
    _verify_docx_visible_content,
    save_document_atomic,
    unwrap_internal_placeholders,
)
from .gemini_structural_schema import (
    FooterStationerySpec,
    HeaderStationerySpec,
    PageRegionSpec,
    PageStructuralDocument,
    StyledParagraph,
)
from .source_structural_evidence import HeaderCrestAsset
from .types import TargetLang

_FONT_MAP = {
    "times_12": ("Times New Roman", {"title": 13.5, "heading": 12.0, "body": 12.0, "small": 10.0, "footnote": 8.5}),
    "arial_11_5": ("Arial", {"title": 13.0, "heading": 12.0, "body": 11.5, "small": 9.5, "footnote": 8.0}),
    "arial_12_5": ("Arial", {"title": 14.0, "heading": 13.0, "body": 12.5, "small": 10.5, "footnote": 8.5}),
    "calibri_11": ("Calibri", {"title": 13.0, "heading": 11.5, "body": 11.0, "small": 9.5, "footnote": 8.0}),
}
_MARGIN_TWIPS_PER_PT = 20.0


@dataclass(frozen=True, slots=True)
class StructuralPageBundle:
    """Validated per-page structural translation paired with optional source geometry/crest."""

    page_number: int
    document: PageStructuralDocument
    width_pt: float = 595.3
    height_pt: float = 841.9
    crest_asset: HeaderCrestAsset | None = None


def _pt_to_twips(value_pt: float) -> int:
    return max(0, int(round(float(value_pt) * _MARGIN_TWIPS_PER_PT)))


_PPR_ORDER_AFTER_BDR = (
    "w:shd",
    "w:tabs",
    "w:suppressAutoHyphens",
    "w:kinsoku",
    "w:wordWrap",
    "w:overflowPunct",
    "w:topLinePunct",
    "w:autoSpaceDE",
    "w:autoSpaceDN",
    "w:bidi",
    "w:adjustRightInd",
    "w:snapToGrid",
    "w:spacing",
    "w:ind",
    "w:contextualSpacing",
    "w:mirrorIndents",
    "w:suppressOverlap",
    "w:jc",
    "w:textDirection",
    "w:textAlignment",
    "w:textboxTightWrap",
    "w:outlineLvl",
    "w:divId",
    "w:cnfStyle",
    "w:rPr",
    "w:sectPr",
    "w:pPrChange",
)
_PPR_ORDER_AFTER_SHD = _PPR_ORDER_AFTER_BDR[1:]
_PPR_ORDER_AFTER_BIDI = _PPR_ORDER_AFTER_BDR[10:]


def _set_paragraph_bidi(paragraph, *, rtl: bool) -> None:
    ppr = paragraph._p.get_or_add_pPr()
    existing = ppr.find(qn("w:bidi"))
    if rtl:
        if existing is not None:
            ppr.remove(existing)
        bidi = OxmlElement("w:bidi")
        bidi.set(qn("w:val"), "1")
        ppr.insert_element_before(bidi, *_PPR_ORDER_AFTER_BIDI)
    elif existing is not None:
        ppr.remove(existing)


def _set_paragraph_borders(paragraph, border_kind: str) -> None:
    if border_kind == "none":
        return
    ppr = paragraph._p.get_or_add_pPr()
    existing = ppr.find(qn("w:pBdr"))
    if existing is not None:
        ppr.remove(existing)
    pdr = OxmlElement("w:pBdr")
    sides: tuple[str, ...]
    if border_kind == "bottom":
        sides = ("bottom",)
    elif border_kind == "top_bottom":
        sides = ("top", "bottom")
    elif border_kind == "box":
        sides = ("top", "left", "bottom", "right")
    else:
        sides = ()
    for side in sides:
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "6" if side in {"top", "bottom"} else "4")
        el.set(qn("w:space"), "4")
        el.set(qn("w:color"), "262626")
        pdr.append(el)
    if len(pdr):
        ppr.insert_element_before(pdr, *_PPR_ORDER_AFTER_BDR)


def _set_paragraph_shading(paragraph, shading: str) -> None:
    if shading != "light_gray":
        return
    ppr = paragraph._p.get_or_add_pPr()
    existing = ppr.find(qn("w:shd"))
    if existing is not None:
        ppr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F3F3F3")
    ppr.insert_element_before(shd, *_PPR_ORDER_AFTER_SHD)


def _set_cell_shading(cell, shading: str, *, fill_hex: str = "F2F2F2") -> None:
    if shading != "light_gray":
        return
    tcpr = cell._tc.get_or_add_tcPr()
    existing = tcpr.find(qn("w:shd"))
    if existing is not None:
        tcpr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill_hex)
    tcpr.append(shd)


def _set_table_borders(table, border_map: Mapping[str, tuple[str, str, str]]) -> None:
    tbl_pr = table._tbl.tblPr
    existing = tbl_pr.find(qn("w:tblBorders"))
    if existing is not None:
        tbl_pr.remove(existing)
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        val, sz, color = border_map.get(side, ("nil", "0", "auto"))
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), val)
        if val != "nil":
            el.set(qn("w:sz"), sz)
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), color)
        borders.append(el)
    tbl_pr.append(borders)


def _set_cell_right_border(cell, *, val: str = "single", sz: str = "4", color: str = "B0B0B0") -> None:
    tcpr = cell._tc.get_or_add_tcPr()
    existing = tcpr.find(qn("w:tcBorders"))
    if existing is not None:
        tcpr.remove(existing)
    tc_bdr = OxmlElement("w:tcBorders")
    side_el = OxmlElement("w:right")
    side_el.set(qn("w:val"), val)
    side_el.set(qn("w:sz"), sz)
    side_el.set(qn("w:space"), "0")
    side_el.set(qn("w:color"), color)
    tc_bdr.append(side_el)
    tcpr.append(tc_bdr)


def _configure_table_grid(
    table,
    col_widths_twips: list[int],
    *,
    rtl: bool,
    cell_pad_h: int = 100,
    cell_pad_v: int = 60,
    force_ltr_in_rtl_section: bool = False,
) -> None:
    total_twips = sum(col_widths_twips)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    tbl_pr = table._tbl.tblPr

    for tag in ("w:tblW", "w:tblLayout", "w:bidiVisual", "w:tblCellMar"):
        existing = tbl_pr.find(qn(tag))
        if existing is not None:
            tbl_pr.remove(existing)

    tbl_w = OxmlElement("w:tblW")
    tbl_w.set(qn("w:w"), str(total_twips))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_pr.append(tbl_w)

    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    tbl_pr.append(layout)

    if rtl:
        tbl_pr.append(OxmlElement("w:bidiVisual"))
    elif force_ltr_in_rtl_section:
        bv = OxmlElement("w:bidiVisual")
        bv.set(qn("w:val"), "0")
        tbl_pr.append(bv)

    cell_mar = OxmlElement("w:tblCellMar")
    for side, val in (("top", cell_pad_v), ("bottom", cell_pad_v), ("left", cell_pad_h), ("right", cell_pad_h)):
        m = OxmlElement(f"w:{side}")
        m.set(qn("w:w"), str(val))
        m.set(qn("w:type"), "dxa")
        cell_mar.append(m)
    tbl_pr.append(cell_mar)

    tbl_grid = table._tbl.tblGrid
    for old in list(tbl_grid):
        tbl_grid.remove(old)
    for w_tw in col_widths_twips:
        gc = OxmlElement("w:gridCol")
        gc.set(qn("w:w"), str(w_tw))
        tbl_grid.append(gc)

    for row in table.rows:
        for idx, width_tw in enumerate(col_widths_twips):
            if idx < len(row.cells):
                tc = row.cells[idx]._tc
                tcpr = tc.get_or_add_tcPr()
                old_w = tcpr.find(qn("w:tcW"))
                if old_w is not None:
                    tcpr.remove(old_w)
                tc_w = OxmlElement("w:tcW")
                tc_w.set(qn("w:w"), str(width_tw))
                tc_w.set(qn("w:type"), "dxa")
                tcpr.append(tc_w)


def _normalize_col_widths_twips(pcts: Sequence[int], col_count: int, total_twips: int) -> list[int]:
    if col_count <= 0:
        return []
    if len(pcts) == col_count and all(isinstance(v, (int, float)) and v > 0 for v in pcts):
        total_pct = float(sum(pcts)) or float(col_count)
        widths = [max(400, int(round(total_twips * (float(p) / total_pct)))) for p in pcts]
    else:
        base = max(400, total_twips // col_count)
        widths = [base] * col_count
    diff = total_twips - sum(widths)
    widths[-1] = max(400, widths[-1] + diff)
    return widths


def _apply_run_typography(run, *, font_name: str, size_pt: float, underline: bool = False, color: RGBColor | None = None) -> None:
    run.font.name = font_name
    run.font.size = Pt(size_pt)
    if underline:
        run.underline = True
    if color is not None:
        run.font.color.rgb = color
    rpr = run._r.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.insert(0, rfonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), font_name)
    half_pt = str(int(round(size_pt * 2)))
    for tag in ("w:sz", "w:szCs"):
        node = rpr.find(qn(tag))
        if node is None:
            node = OxmlElement(tag)
            rpr.append(node)
        node.set(qn("w:val"), half_pt)


_LONG_UNDERSCORE_RE = re.compile(r"_{20,}")


def _cap_signature_underscores(text: str) -> str:
    return _LONG_UNDERSCORE_RE.sub("_" * 34, text)


def _style_font_pair(font_preference: str, *, lang: TargetLang | str, archetype: str = "") -> tuple[str, dict[str, float]]:
    if _is_rtl_target_lang(lang):
        if archetype == "form_record":
            return ("Arial", {"title": 12.5, "heading": 11.5, "body": 10.5, "small": 9.0, "footnote": 8.0})
        if font_preference == "arial_11_5":
            return _FONT_MAP["arial_11_5"]
        return _FONT_MAP["arial_12_5"]
    if archetype == "citius_notification":
        return ("Arial", {"title": 11.5, "heading": 10.5, "body": 10.5, "small": 8.5, "footnote": 8.0})
    return _FONT_MAP.get(font_preference, _FONT_MAP["times_12"])


def _alignment_enum(align: str, *, rtl: bool, explicit_override: bool = False) -> WD_ALIGN_PARAGRAPH:
    if align == "center":
        return WD_ALIGN_PARAGRAPH.CENTER
    if align == "justify":
        return WD_ALIGN_PARAGRAPH.JUSTIFY
    if align == "right":
        return WD_ALIGN_PARAGRAPH.RIGHT
    if align == "left":
        if rtl and not explicit_override:
            return WD_ALIGN_PARAGRAPH.RIGHT
        return WD_ALIGN_PARAGRAPH.LEFT
    return WD_ALIGN_PARAGRAPH.RIGHT if rtl else WD_ALIGN_PARAGRAPH.LEFT


def _set_paragraph_alignment(
    paragraph,
    align: str,
    *,
    rtl: bool,
    explicit_override: bool = False,
) -> None:
    if rtl:
        eff = align if align in {"left", "right", "center", "justify"} else "right"
        if eff == "left" and not explicit_override:
            eff = "right"
        _set_rtl_visual_alignment(paragraph, eff)
        return
    paragraph.alignment = _alignment_enum(align, rtl=False, explicit_override=explicit_override)


def _render_styled_paragraph(
    paragraph,
    spec: StyledParagraph,
    *,
    lang: TargetLang | str,
    strip_bidi_controls: bool,
    font_name: str,
    sizes_map: Mapping[str, float],
    in_table_cell: bool = False,
    compact: bool = False,
    allow_physical_left: bool = False,
) -> None:
    rtl = _is_rtl_target_lang(lang)
    _set_paragraph_bidi(paragraph, rtl=rtl)

    pfmt = paragraph.paragraph_format
    size_pt = sizes_map.get(spec.size_role, sizes_map["body"])
    _set_paragraph_alignment(paragraph, spec.align, rtl=rtl, explicit_override=allow_physical_left)

    if spec.item_type == "horizontal_rule":
        pfmt.space_before = Pt(0)
        pfmt.space_after = Pt(2)
        pfmt.line_spacing = Pt(2.0)
        _set_paragraph_borders(paragraph, "bottom")
        r = paragraph.add_run("")
        _apply_run_typography(r, font_name=font_name, size_pt=1.0)
        return

    if spec.item_type == "divider_stars":
        _set_paragraph_alignment(paragraph, "center", rtl=rtl)
        pfmt.space_before = Pt(4)
        pfmt.space_after = Pt(4)
        pfmt.line_spacing = 1.0
        r = paragraph.add_run("* * *")
        _apply_run_typography(r, font_name=font_name, size_pt=size_pt)
        return

    # Indentation
    if spec.indent_style == "first_line":
        indent_cm = spec.first_line_indent_cm if spec.first_line_indent_cm > 0 else 1.25
        pfmt.first_line_indent = Cm(indent_cm)
    elif spec.indent_style == "hanging":
        left_cm = spec.left_indent_cm if spec.left_indent_cm > 0 else 1.2
        pfmt.left_indent = Cm(left_cm)
        pfmt.first_line_indent = Cm(-0.55)
    elif spec.indent_style == "left_block":
        left_cm = spec.left_indent_cm if spec.left_indent_cm > 0 else 1.5
        pfmt.left_indent = Cm(left_cm)
    elif spec.indent_style == "right_block":
        pfmt.right_indent = Cm(spec.left_indent_cm if spec.left_indent_cm > 0 else 1.5)

    # Spacing tuned by role, container, and archetype density
    if in_table_cell:
        pfmt.space_before = Pt(0)
        pfmt.space_after = Pt(1.2 if compact else 2.2)
        pfmt.line_spacing = 1.04 if compact else 1.08
    elif spec.item_type in {"title", "heading_1", "heading_2"}:
        pfmt.space_before = Pt((4 if compact else 7) if spec.item_type != "title" else (2 if compact else 4))
        pfmt.space_after = Pt((3 if compact else 6) if spec.border == "bottom" else (2.5 if compact else 4))
        pfmt.line_spacing = 1.08 if compact else 1.12
        pfmt.keep_with_next = True
    elif spec.item_type == "callout_box":
        pfmt.space_before = Pt(3 if compact else 5)
        pfmt.space_after = Pt(3 if compact else 5)
        pfmt.line_spacing = 1.08 if compact else 1.12
        pfmt.keep_together = True
    elif spec.item_type == "signature_block":
        pfmt.space_before = Pt(4 if compact else 6)
        pfmt.space_after = Pt(2 if compact else 4)
        pfmt.line_spacing = 1.08 if compact else 1.12
        pfmt.keep_together = True
    else:
        pfmt.space_before = Pt(0)
        pfmt.space_after = Pt((2.5 if compact else 4) if spec.item_type in {"list_bullet", "list_number"} else (3.0 if compact else 5))
        pfmt.line_spacing = 1.08 if compact else 1.15

    if spec.keep_with_next:
        pfmt.keep_with_next = True

    border = spec.border
    if spec.item_type == "callout_box" and border == "none":
        border = "box"
    _set_paragraph_borders(paragraph, border)
    _set_paragraph_shading(paragraph, spec.shading if spec.item_type != "callout_box" else (spec.shading if spec.shading != "none" else "light_gray"))

    plain_para_check = unwrap_internal_placeholders(spec.plain_text()).strip()
    pure_ltr_alnum_num_line = (
        rtl
        and bool(plain_para_check)
        and not any(_classify_directional_char(ch) == "rtl" for ch in plain_para_check)
        and any(ch.isdigit() for ch in plain_para_check)
        and any(ch.isalpha() for ch in plain_para_check)
    )

    for run_spec in spec.effective_runs():
        if not unwrap_internal_placeholders(run_spec.text).strip():
            continue
        token_text = _cap_signature_underscores(run_spec.text)
        start_idx = len(paragraph.runs)
        _append_block_text(
            paragraph,
            token_text,
            lang=lang,
            strip_bidi_controls=strip_bidi_controls,
            bold=run_spec.bold or spec.item_type in {"title", "heading_1"},
            italic=run_spec.italic,
        )
        for added in paragraph.runs[start_idx:]:
            _apply_run_typography(
                added,
                font_name=font_name,
                size_pt=size_pt,
                underline=run_spec.underline,
            )
            if pure_ltr_alnum_num_line and added.text and not added.text.startswith(_LRM):
                added.text = f"{_LRM}{added.text.strip(_LRM)}{_LRM}"


def _insert_word_field(
    paragraph,
    field_name: str,
    *,
    font_name: str,
    size_pt: float,
    ltr_run: bool = False,
) -> None:
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {field_name} "
    sep = OxmlElement("w:fldChar")
    sep.set(qn("w:fldCharType"), "separate")
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")

    for child in (begin, instr, sep):
        r = paragraph.add_run("")
        _apply_run_typography(r, font_name=font_name, size_pt=size_pt)
        r._r.append(child)
    val_run = paragraph.add_run("1")
    _apply_run_typography(val_run, font_name=font_name, size_pt=size_pt)
    if ltr_run:
        _set_ltr_run_props(val_run)
    end_run = paragraph.add_run("")
    _apply_run_typography(end_run, font_name=font_name, size_pt=size_pt)
    end_run._r.append(end)


def _is_pure_ltr_slash_counter(template: str) -> bool:
    plain = unwrap_internal_placeholders(template).replace("{page}", "").replace("{total}", "")
    return "/" in plain and not any(_classify_directional_char(ch) == "rtl" for ch in plain)


def _add_footer_page_counter(
    paragraph,
    template: str,
    *,
    lang: TargetLang | str,
    strip_bidi_controls: bool,
    font_name: str,
    size_pt: float,
    use_section_pages: bool = False,
) -> None:
    rtl = _is_rtl_target_lang(lang)
    force_ltr_slash = rtl and _is_pure_ltr_slash_counter(template)
    if force_ltr_slash:
        _set_paragraph_bidi(paragraph, rtl=False)
        paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
    else:
        _set_paragraph_bidi(paragraph, rtl=rtl)
    total_field = "SECTIONPAGES" if use_section_pages else "NUMPAGES"
    parts = template.split("{page}")
    for p_idx, part in enumerate(parts):
        if p_idx > 0:
            _insert_word_field(paragraph, "PAGE", font_name=font_name, size_pt=size_pt, ltr_run=force_ltr_slash)
        sub_parts = part.split("{total}")
        for t_idx, sub in enumerate(sub_parts):
            if t_idx > 0:
                _insert_word_field(paragraph, total_field, font_name=font_name, size_pt=size_pt, ltr_run=force_ltr_slash)
            if force_ltr_slash and sub:
                r = paragraph.add_run(unwrap_internal_placeholders(sub))
                _apply_run_typography(r, font_name=font_name, size_pt=size_pt, color=RGBColor(0x40, 0x40, 0x40))
                _set_ltr_run_props(r)
            elif unwrap_internal_placeholders(sub):
                start_idx = len(paragraph.runs)
                _append_block_text(paragraph, sub, lang=lang, strip_bidi_controls=strip_bidi_controls)
                for added in paragraph.runs[start_idx:]:
                    _apply_run_typography(added, font_name=font_name, size_pt=size_pt, color=RGBColor(0x40, 0x40, 0x40))


def _clear_header_footer_part(part) -> None:
    part.is_linked_to_previous = False
    for child in list(part._element):
        part._element.remove(child)
    part.add_paragraph()


_PAGE_COUNTER_FALLBACK_RE = re.compile(
    r"^([^\d]{0,24})(\d{1,3})(?:\s*(/|of|de|من)\s*(\d{1,3}))?([^\d]{0,16})$"
)


def _normalize_footer_counter_template(raw_tpl: str) -> str:
    clean = unwrap_internal_placeholders(raw_tpl or "").strip()
    if not clean:
        return ""
    if "{page}" in clean:
        return clean
    m = _PAGE_COUNTER_FALLBACK_RE.match(clean)
    if not m:
        return ""
    prefix, _p1, sep, g_total, suffix = m.groups()
    if sep is not None and g_total is not None:
        return f"{prefix}{{page}} {sep} {{total}}{suffix}".strip()
    return f"{prefix}{{page}}{suffix}".strip()


def _usable_header_crest(crest_asset: HeaderCrestAsset | None) -> HeaderCrestAsset | None:
    _ = crest_asset
    return None


def _render_stationery_header(
    section,
    header_spec: HeaderStationerySpec,
    *,
    crest_asset: HeaderCrestAsset | None,
    usable_width_twips: int,
    lang: TargetLang | str,
    strip_bidi_controls: bool,
    font_name: str,
    header_part=None,
) -> None:
    target_part = section.header if header_part is None else header_part
    _clear_header_footer_part(target_part)
    if not header_spec.present:
        return

    _ = crest_asset
    rtl = _is_rtl_target_lang(lang)
    has_left_stamp = bool(header_spec.top_left_stamp_lines)
    has_center_block = bool(
        header_spec.center_institution_lines
        or header_spec.sub_line
    )

    if has_left_stamp and has_center_block:
        # Clear default paragraph only visually by keeping compact 1x3 layout table
        p0 = target_part.paragraphs[0]
        p0._element.getparent().remove(p0._element)
        widths = _normalize_col_widths_twips([28, 44, 28], 3, usable_width_twips)
        table = target_part.add_table(rows=1, cols=3, width=Pt(usable_width_twips / _MARGIN_TWIPS_PER_PT))
        _configure_table_grid(
            table,
            widths,
            rtl=False,
            cell_pad_h=40,
            cell_pad_v=10,
            force_ltr_in_rtl_section=rtl,
        )
        _set_table_borders(table, {})

        stamp_cell = table.cell(0, 0)
        stamp_cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        for idx, line in enumerate(header_spec.top_left_stamp_lines):
            p = stamp_cell.paragraphs[0] if idx == 0 else stamp_cell.add_paragraph()
            _set_paragraph_bidi(p, rtl=rtl)
            _set_paragraph_alignment(p, "left", rtl=rtl, explicit_override=True)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0.5)
            p.paragraph_format.line_spacing = 1.0
            if unwrap_internal_placeholders(line).strip():
                start_idx = len(p.runs)
                _append_block_text(p, line, lang=lang, strip_bidi_controls=strip_bidi_controls)
                for added in p.runs[start_idx:]:
                    _apply_run_typography(added, font_name=font_name, size_pt=7.5, color=RGBColor(0x40, 0x40, 0x40))

        center_cell = table.cell(0, 1)
        center_cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        need_first = True
        for idx, line in enumerate(header_spec.center_institution_lines):
            p = center_cell.paragraphs[0] if need_first else center_cell.add_paragraph()
            need_first = False
            _set_paragraph_bidi(p, rtl=rtl)
            _set_paragraph_alignment(p, "center", rtl=rtl)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.05
            if unwrap_internal_placeholders(line).strip():
                start_idx = len(p.runs)
                _append_block_text(p, line, lang=lang, strip_bidi_controls=strip_bidi_controls, bold=(idx == 0))
                for added in p.runs[start_idx:]:
                    _apply_run_typography(added, font_name=font_name, size_pt=10.5 if idx == 0 else 9.5)
        if header_spec.sub_line:
            p = center_cell.paragraphs[0] if need_first else center_cell.add_paragraph()
            _set_paragraph_bidi(p, rtl=rtl)
            _set_paragraph_alignment(p, "center", rtl=rtl)
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.line_spacing = 1.05
            if unwrap_internal_placeholders(header_spec.sub_line).strip():
                start_idx = len(p.runs)
                _append_block_text(p, header_spec.sub_line, lang=lang, strip_bidi_controls=strip_bidi_controls)
                for added in p.runs[start_idx:]:
                    _apply_run_typography(added, font_name=font_name, size_pt=9.0)
        return

    need_first = True
    for idx, line in enumerate(header_spec.center_institution_lines):
        p = target_part.paragraphs[0] if need_first else target_part.add_paragraph()
        need_first = False
        _set_paragraph_bidi(p, rtl=rtl)
        _set_paragraph_alignment(p, "center", rtl=rtl)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(1)
        if unwrap_internal_placeholders(line).strip():
            start_idx = len(p.runs)
            _append_block_text(p, line, lang=lang, strip_bidi_controls=strip_bidi_controls, bold=(idx == 0))
            for added in p.runs[start_idx:]:
                _apply_run_typography(added, font_name=font_name, size_pt=10.5 if idx == 0 else 9.5)
    if header_spec.sub_line:
        p = target_part.paragraphs[0] if need_first else target_part.add_paragraph()
        need_first = False
        _set_paragraph_bidi(p, rtl=rtl)
        _set_paragraph_alignment(p, "center", rtl=rtl)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(1)
        if unwrap_internal_placeholders(header_spec.sub_line).strip():
            start_idx = len(p.runs)
            _append_block_text(p, header_spec.sub_line, lang=lang, strip_bidi_controls=strip_bidi_controls)
            for added in p.runs[start_idx:]:
                _apply_run_typography(added, font_name=font_name, size_pt=9.0)
    for line in header_spec.top_left_stamp_lines:
        p = target_part.paragraphs[0] if need_first else target_part.add_paragraph()
        need_first = False
        _set_paragraph_bidi(p, rtl=rtl)
        _set_paragraph_alignment(p, "left", rtl=rtl, explicit_override=True)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0.5)
        if unwrap_internal_placeholders(line).strip():
            start_idx = len(p.runs)
            _append_block_text(p, line, lang=lang, strip_bidi_controls=strip_bidi_controls)
            for added in p.runs[start_idx:]:
                _apply_run_typography(added, font_name=font_name, size_pt=8.0, color=RGBColor(0x40, 0x40, 0x40))


def _render_continuation_panel_header(
    section,
    region: PageRegionSpec,
    *,
    usable_width_twips: int,
    lang: TargetLang | str,
    strip_bidi_controls: bool,
    font_name: str,
    sizes_map: Mapping[str, float],
) -> None:
    header_part = section.header
    _clear_header_footer_part(header_part)
    rtl = _is_rtl_target_lang(lang)
    p0 = header_part.paragraphs[0]
    p0._element.getparent().remove(p0._element)
    table = header_part.add_table(rows=1, cols=2, width=Pt(usable_width_twips / _MARGIN_TWIPS_PER_PT))
    widths = _normalize_col_widths_twips([region.left_width_pct, 100 - region.left_width_pct], 2, usable_width_twips)
    _configure_table_grid(table, widths, rtl=rtl, cell_pad_h=60, cell_pad_v=14)
    _set_table_borders(table, {"bottom": ("single", "4", "404040")})
    header_sizes = {**sizes_map, "body": min(sizes_map.get("small", 9.0), 9.0), "small": 8.5}
    for col_idx, items in ((0, region.left_items), (1, region.right_items)):
        cell = table.cell(0, col_idx)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        if not items:
            _set_paragraph_bidi(cell.paragraphs[0], rtl=rtl)
            continue
        allow_left = rtl and all(it.align == "left" for it in items) and col_idx == 1
        for p_idx, item in enumerate(items):
            p = cell.paragraphs[0] if p_idx == 0 else cell.add_paragraph()
            cloned = item.model_copy(update={"size_role": "small"})
            _render_styled_paragraph(
                p,
                cloned,
                lang=lang,
                strip_bidi_controls=strip_bidi_controls,
                font_name=font_name,
                sizes_map=header_sizes,
                in_table_cell=True,
                compact=True,
                allow_physical_left=allow_left,
            )


def _render_stationery_footer(
    section,
    footer_spec: FooterStationerySpec,
    *,
    lang: TargetLang | str,
    strip_bidi_controls: bool,
    font_name: str,
    footer_part=None,
    use_section_pages: bool = False,
) -> None:
    target_part = section.footer if footer_part is None else footer_part
    _clear_header_footer_part(target_part)
    if not footer_spec.present:
        return

    rtl = _is_rtl_target_lang(lang)
    need_first = True
    for line in footer_spec.court_contact_lines:
        p = target_part.paragraphs[0] if need_first else target_part.add_paragraph()
        need_first = False
        _set_paragraph_bidi(p, rtl=rtl)
        _set_paragraph_alignment(p, "center", rtl=rtl)
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0.5)
        p.paragraph_format.line_spacing = 1.0
        if unwrap_internal_placeholders(line).strip():
            start_idx = len(p.runs)
            _append_block_text(p, line, lang=lang, strip_bidi_controls=strip_bidi_controls)
            for added in p.runs[start_idx:]:
                _apply_run_typography(added, font_name=font_name, size_pt=8.0, color=RGBColor(0x40, 0x40, 0x40))
    if footer_spec.legal_note:
        p = target_part.paragraphs[0] if need_first else target_part.add_paragraph()
        need_first = False
        _set_paragraph_bidi(p, rtl=rtl)
        _set_paragraph_alignment(p, "center", rtl=rtl)
        p.paragraph_format.space_before = Pt(0.5)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.0
        if unwrap_internal_placeholders(footer_spec.legal_note).strip():
            start_idx = len(p.runs)
            _append_block_text(p, footer_spec.legal_note, lang=lang, strip_bidi_controls=strip_bidi_controls)
            for added in p.runs[start_idx:]:
                _apply_run_typography(added, font_name=font_name, size_pt=7.5, color=RGBColor(0x40, 0x40, 0x40))
    counter_tpl = _normalize_footer_counter_template(footer_spec.page_counter_template)
    if counter_tpl and "{page}" in counter_tpl:
        p = target_part.paragraphs[0] if need_first else target_part.add_paragraph()
        _set_paragraph_bidi(p, rtl=rtl)
        _set_paragraph_alignment(p, "right" if not rtl else "left", rtl=rtl, explicit_override=True)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(0)
        _add_footer_page_counter(
            p,
            counter_tpl,
            lang=lang,
            strip_bidi_controls=strip_bidi_controls,
            font_name=font_name,
            size_pt=8.0,
            use_section_pages=use_section_pages,
        )


def _configure_structural_section(
    section,
    bundle: StructuralPageBundle,
    *,
    lang: TargetLang | str,
    different_first_page: bool = False,
    restart_page_numbering: bool = False,
) -> int:
    rtl = _is_rtl_target_lang(lang)
    doc = bundle.document
    section.page_width = Pt(bundle.width_pt)
    section.page_height = Pt(bundle.height_pt)
    section.different_first_page_header_footer = bool(different_first_page)

    if rtl:
        if section._sectPr.find(qn("w:bidi")) is None:
            section._sectPr.append(OxmlElement("w:bidi"))

    for node in list(section._sectPr.findall(qn("w:pgNumType"))):
        section._sectPr.remove(node)
    if restart_page_numbering:
        pg_num = OxmlElement("w:pgNumType")
        pg_num.set(qn("w:start"), "1")
        section._sectPr.append(pg_num)

    # Archetype-calibrated clean margins
    if doc.page_archetype == "citius_notification":
        left_pt = max(34.0, min(54.0, doc.margins_pt.left))
        right_pt = max(34.0, min(54.0, doc.margins_pt.right))
        top_pt = max(24.0, min(54.0, doc.margins_pt.top))
        bottom_pt = max(26.0, min(58.0, doc.margins_pt.bottom))
    elif doc.page_archetype == "form_record":
        left_pt = max(36.0, min(56.0, doc.margins_pt.left))
        right_pt = max(36.0, min(56.0, doc.margins_pt.right))
        min_form_top = 56.0 if (doc.header_stationery.present or different_first_page) else 28.0
        top_pt = max(min_form_top, min(86.0, max(doc.margins_pt.top, min_form_top)))
        bottom_pt = max(28.0, min(56.0, doc.margins_pt.bottom))
    else:
        left_pt = max(54.0, min(74.0, doc.margins_pt.left))
        right_pt = max(54.0, min(74.0, doc.margins_pt.right))
        bottom_pt = max(48.0, min(72.0, doc.margins_pt.bottom))
        if doc.header_stationery.present and (
            doc.header_stationery.center_institution_lines
            or doc.header_stationery.top_left_stamp_lines
            or doc.header_stationery.sub_line
        ):
            top_pt = max(72.0, min(116.0, max(doc.margins_pt.top, 76.0)))
        else:
            top_pt = max(46.0, min(78.0, doc.margins_pt.top))

    section.left_margin = Pt(left_pt)
    section.right_margin = Pt(right_pt)
    section.top_margin = Pt(top_pt)
    section.bottom_margin = Pt(bottom_pt)
    section.header_distance = Pt(12.0 if doc.page_archetype == "citius_notification" else 16.0)
    section.footer_distance = Pt(12.0 if doc.page_archetype == "citius_notification" else 16.0)

    usable_twips = max(2400, _pt_to_twips(bundle.width_pt - left_pt - right_pt))
    return usable_twips


def _add_slim_spacer(document: Document, *, font_name: str, space_after_pt: float) -> None:
    spacer = document.add_paragraph("")
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.space_after = Pt(space_after_pt)
    spacer.paragraph_format.line_spacing = Pt(2.0)
    _apply_run_typography(spacer.add_run(""), font_name=font_name, size_pt=1.0)


def _render_region(
    document: Document,
    region,
    *,
    usable_twips: int,
    lang: TargetLang | str,
    strip_bidi_controls: bool,
    font_name: str,
    sizes_map: Mapping[str, float],
    top_left_crest_asset: HeaderCrestAsset | None = None,
    compact: bool = False,
) -> None:
    rtl = _is_rtl_target_lang(lang)
    kind = region.kind
    pad_v = 28 if compact else 55

    if kind == "two_col_panel":
        bmap: dict[str, tuple[str, str, str]] = {}
        if region.border_style in {"top_bottom_rule", "top_bottom_only"}:
            bmap = {"top": ("single", "6", "404040"), "bottom": ("single", "6", "404040")}
        elif region.border_style == "outer_box":
            bmap = {s: ("single", "4", "404040") for s in ("top", "left", "bottom", "right")}
        elif region.border_style == "full_grid":
            bmap = {s: ("single", "4", "404040") for s in ("top", "left", "bottom", "right", "insideH", "insideV")}
        if region.vertical_divider and "insideV" not in bmap:
            bmap["insideV"] = ("single", "4", "BFBFBF")

        _ = top_left_crest_asset
        table = document.add_table(rows=1, cols=2)
        widths = _normalize_col_widths_twips([region.left_width_pct, 100 - region.left_width_pct], 2, usable_twips)
        _configure_table_grid(table, widths, rtl=rtl, cell_pad_h=95, cell_pad_v=pad_v)
        _set_table_borders(table, bmap)
        col_pairs = ((0, region.left_items), (1, region.right_items))

        right_col_idx = col_pairs[-1][0]
        for col_idx, items in col_pairs:
            cell = table.cell(0, col_idx)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
            if col_idx == 0 and region.border_style == "left_shaded_panel":
                _set_cell_shading(cell, "light_gray", fill_hex="F3F3F3")
                _set_cell_right_border(cell)
            if not items:
                p = cell.paragraphs[0]
                _set_paragraph_bidi(p, rtl=rtl)
                continue
            allow_left = rtl and col_idx == right_col_idx and all(it.align == "left" for it in items)
            for p_idx, item in enumerate(items):
                p = cell.paragraphs[0] if p_idx == 0 else cell.add_paragraph()
                _render_styled_paragraph(
                    p,
                    item,
                    lang=lang,
                    strip_bidi_controls=strip_bidi_controls,
                    font_name=font_name,
                    sizes_map=sizes_map,
                    in_table_cell=True,
                    compact=compact,
                    allow_physical_left=allow_left,
                )
        _add_slim_spacer(document, font_name=font_name, space_after_pt=2.0 if compact else 4.0)
        return

    if kind == "metadata_rule_band":
        cols = max(1, len(region.metadata_cells))
        table = document.add_table(rows=1, cols=cols)
        widths = _normalize_col_widths_twips(region.col_widths_pct, cols, usable_twips)
        _configure_table_grid(table, widths, rtl=rtl, cell_pad_h=90, cell_pad_v=pad_v)
        bmap = {
            "top": ("single", "6", "000000"),
            "bottom": ("single", "6", "000000"),
        }
        if region.border_style == "top_bottom_inside_v":
            bmap["insideV"] = ("single", "4", "595959")
        elif region.border_style == "full_grid":
            bmap = {s: ("single", "4", "000000") for s in ("top", "left", "bottom", "right", "insideH", "insideV")}
        _set_table_borders(table, bmap)
        for col_idx, cell_spec in enumerate(region.metadata_cells):
            cell = table.cell(0, col_idx)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            for p_idx, item in enumerate(cell_spec.paragraphs):
                p = cell.paragraphs[0] if p_idx == 0 else cell.add_paragraph()
                _render_styled_paragraph(
                    p,
                    item,
                    lang=lang,
                    strip_bidi_controls=strip_bidi_controls,
                    font_name=font_name,
                    sizes_map=sizes_map,
                    in_table_cell=True,
                    compact=compact,
                )
        _add_slim_spacer(document, font_name=font_name, space_after_pt=3.0 if compact else 5.0)
        return

    if kind == "table":
        rows = region.table_rows
        if not rows:
            return
        max_cols = max(sum(cell.col_span for cell in r.cells) for r in rows)
        if max_cols <= 0:
            return
        table = document.add_table(rows=len(rows), cols=max_cols)
        widths = _normalize_col_widths_twips(region.col_widths_pct, max_cols, usable_twips)
        _configure_table_grid(table, widths, rtl=rtl, cell_pad_h=85, cell_pad_v=pad_v)
        if region.border_style in {"none"}:
            _set_table_borders(table, {})
        elif region.border_style in {"top_bottom_only", "top_bottom_rule"}:
            _set_table_borders(table, {"top": ("single", "6", "262626"), "bottom": ("single", "6", "262626")})
        elif region.border_style == "outer_box":
            _set_table_borders(table, {s: ("single", "6", "262626") for s in ("top", "left", "bottom", "right")})
        else:
            _set_table_borders(table, {s: ("single", "4", "404040") for s in ("top", "left", "bottom", "right", "insideH", "insideV")})

        for r_idx, row_spec in enumerate(rows):
            tr = table.rows[r_idx]._tr
            trpr = tr.get_or_add_trPr()
            if trpr.find(qn("w:cantSplit")) is None:
                trpr.append(OxmlElement("w:cantSplit"))
            if region.header_row and r_idx == 0 and trpr.find(qn("w:tblHeader")) is None:
                trpr.append(OxmlElement("w:tblHeader"))
            col_cursor = 0
            for cell_spec in row_spec.cells:
                if col_cursor >= max_cols:
                    break
                span = min(cell_spec.col_span, max_cols - col_cursor)
                cell = table.cell(r_idx, col_cursor)
                if span > 1:
                    cell = cell.merge(table.cell(r_idx, col_cursor + span - 1))
                cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
                shading = "light_gray" if (cell_spec.shading == "light_gray" or (region.header_row and r_idx == 0)) else "none"
                _set_cell_shading(cell, shading, fill_hex="EDEDED" if (region.header_row and r_idx == 0) else "F3F3F3")
                for p_idx, item in enumerate(cell_spec.paragraphs):
                    p = cell.paragraphs[0] if p_idx == 0 else cell.add_paragraph()
                    if region.header_row and r_idx == 0 and item.item_type == "paragraph":
                        item.bold = True
                        for run in item.runs:
                            run.bold = True
                    _render_styled_paragraph(
                        p,
                        item,
                        lang=lang,
                        strip_bidi_controls=strip_bidi_controls,
                        font_name=font_name,
                        sizes_map=sizes_map,
                        in_table_cell=True,
                        compact=compact,
                    )
                col_cursor += span
        _add_slim_spacer(document, font_name=font_name, space_after_pt=2.5 if compact else 4.5)
        return

    # Default: flow_block
    for item in region.flow_items:
        p = document.add_paragraph("")
        _render_styled_paragraph(
            p,
            item,
            lang=lang,
            strip_bidi_controls=strip_bidi_controls,
            font_name=font_name,
            sizes_map=sizes_map,
            in_table_cell=False,
            compact=compact,
        )


def _group_sections(bundles: Sequence[StructuralPageBundle]) -> list[list[StructuralPageBundle]]:
    sections: list[list[StructuralPageBundle]] = []
    for idx, bundle in enumerate(bundles):
        if idx == 0 or bundle.document.document_starts_here:
            sections.append([bundle])
        else:
            sections[-1].append(bundle)
    return sections


def _looks_like_continuation_running_header(region) -> bool:
    if getattr(region, "kind", None) != "two_col_panel":
        return False
    if getattr(region, "border_style", "none") != "none":
        return False
    left_n = len(getattr(region, "left_items", []) or ())
    right_n = len(getattr(region, "right_items", []) or ())
    if not (1 <= left_n <= 4 and 1 <= right_n <= 4):
        return False
    total_chars = sum(
        len(p.plain_text().strip())
        for p in (*(region.left_items or ()), *(region.right_items or ()))
    )
    return 0 < total_chars <= 240


def _strip_leading_continuation_banner(regions: list, *, archetype: str) -> tuple[Any, list]:
    """Extract a leaked continuation top-of-page banner from flowing body regions."""
    if archetype != "form_record" or not regions:
        return None, regions
    first = regions[0]
    if not _looks_like_continuation_running_header(first):
        return None, regions
    remaining = list(regions[1:])
    if remaining and remaining[0].kind == "flow_block" and remaining[0].flow_items:
        items = list(remaining[0].flow_items)
        if items[0].item_type == "horizontal_rule":
            if len(items) == 1:
                remaining = remaining[1:]
            else:
                remaining[0] = remaining[0].model_copy(update={"flow_items": items[1:]})
    return first, remaining


def assemble_structural_docx(
    bundles: Sequence[StructuralPageBundle],
    output_path: Path,
    *,
    lang: TargetLang | str,
    page_breaks: bool = True,
    strip_bidi_controls: bool = True,
    stats: dict[str, int] | None = None,
    verify_readable: bool = True,
) -> Path:
    """Assemble validated PageStructuralDocument bundles into a high-fidelity editable Word DOCX."""
    if not bundles:
        raise ValueError("Cannot assemble structural DOCX from empty page list.")

    document = Document()
    sections_groups = _group_sections(bundles)

    for sec_idx, group in enumerate(sections_groups):
        lead = group[0]
        section = document.sections[0] if sec_idx == 0 else document.add_section(WD_SECTION_START.NEW_PAGE)
        font_name, sizes_map = _style_font_pair(
            lead.document.font_preference,
            lang=lang,
            archetype=lead.document.page_archetype,
        )

        # Pick strongest stationery specs within this document section (logos/crests are never embedded)
        header_spec = lead.document.header_stationery
        crest_asset = None
        if not header_spec.present:
            for member in group:
                if member.document.header_stationery.present:
                    header_spec = member.document.header_stationery
                    break
        footer_spec = lead.document.footer_stationery
        if not footer_spec.present:
            for member in group:
                if member.document.footer_stationery.present:
                    footer_spec = member.document.footer_stationery
                    break

        cont_header_spec: HeaderStationerySpec | None = None
        cont_banner_region = None
        stripped_regions_by_member: dict[int, list] = {}
        if len(group) > 1:
            for member_idx, member in enumerate(group[1:], start=1):
                if (
                    lead.document.page_archetype == "form_record"
                    and member.document.continuation_from_previous
                ):
                    extracted, kept = _strip_leading_continuation_banner(
                        list(member.document.regions),
                        archetype=lead.document.page_archetype,
                    )
                    if extracted is not None:
                        stripped_regions_by_member[member_idx] = kept
                        if cont_banner_region is None:
                            cont_banner_region = extracted
                if cont_header_spec is None:
                    m_hs = member.document.header_stationery
                    if m_hs.present and (
                        bool(header_spec.top_left_stamp_lines) != bool(m_hs.top_left_stamp_lines)
                        or m_hs.style != header_spec.style
                    ):
                        if (
                            header_spec.present
                            and m_hs.style == header_spec.style
                            and bool(header_spec.top_left_stamp_lines)
                            and not m_hs.top_left_stamp_lines
                        ):
                            cont_header_spec = header_spec.model_copy(update={"top_left_stamp_lines": []})
                        else:
                            cont_header_spec = m_hs

        different_first_page = bool(
            len(group) > 1
            and (
                cont_banner_region is not None
                or cont_header_spec is not None
                or (
                    lead.document.page_archetype == "form_record"
                    and header_spec.present
                    and any(not m.document.header_stationery.present for m in group[1:])
                )
            )
        )

        use_section_pages = len(sections_groups) > 1
        usable_twips = _configure_structural_section(
            section,
            lead,
            lang=lang,
            different_first_page=different_first_page,
            restart_page_numbering=(sec_idx > 0),
        )

        if different_first_page:
            _render_stationery_header(
                section,
                header_spec,
                crest_asset=crest_asset,
                usable_width_twips=usable_twips,
                lang=lang,
                strip_bidi_controls=strip_bidi_controls,
                font_name=font_name,
                header_part=section.first_page_header,
            )
            if cont_banner_region is not None:
                _render_continuation_panel_header(
                    section,
                    cont_banner_region,
                    usable_width_twips=usable_twips,
                    lang=lang,
                    strip_bidi_controls=strip_bidi_controls,
                    font_name=font_name,
                    sizes_map=sizes_map,
                )
            elif cont_header_spec is not None:
                _render_stationery_header(
                    section,
                    cont_header_spec,
                    crest_asset=crest_asset if cont_header_spec.center_crest_present else None,
                    usable_width_twips=usable_twips,
                    lang=lang,
                    strip_bidi_controls=strip_bidi_controls,
                    font_name=font_name,
                    header_part=section.header,
                )
            else:
                _clear_header_footer_part(section.header)
            _render_stationery_footer(
                section,
                footer_spec,
                lang=lang,
                strip_bidi_controls=strip_bidi_controls,
                font_name=font_name,
                footer_part=section.first_page_footer,
                use_section_pages=use_section_pages,
            )
            _render_stationery_footer(
                section,
                footer_spec,
                lang=lang,
                strip_bidi_controls=strip_bidi_controls,
                font_name=font_name,
                footer_part=section.footer,
                use_section_pages=use_section_pages,
            )
        else:
            _render_stationery_header(
                section,
                header_spec,
                crest_asset=crest_asset,
                usable_width_twips=usable_twips,
                lang=lang,
                strip_bidi_controls=strip_bidi_controls,
                font_name=font_name,
            )
            _render_stationery_footer(
                section,
                footer_spec,
                lang=lang,
                strip_bidi_controls=strip_bidi_controls,
                font_name=font_name,
                use_section_pages=use_section_pages,
            )

        seen_meta_signatures: set[str] = set()
        for member_idx, bundle in enumerate(group):
            if member_idx > 0 and page_breaks:
                prev_doc = group[member_idx - 1].document
                cur_doc = bundle.document
                # Allow running prose/forms with continuation_from_previous=True to flow smoothly
                # across Word page boundaries unless archetype switches or explicit fresh sub-page starts.
                should_break = (
                    not cur_doc.continuation_from_previous
                    or cur_doc.page_archetype != prev_doc.page_archetype
                )
                if should_break:
                    document.add_page_break()
            regions_for_member = stripped_regions_by_member.get(member_idx, bundle.document.regions)
            for region in regions_for_member:
                if region.kind == "metadata_rule_band":
                    sig = "|".join(
                        " ".join(p.plain_text().split())
                        for c in region.metadata_cells
                        for p in c.paragraphs
                    )
                    if sig and member_idx > 0 and bundle.document.continuation_from_previous and sig in seen_meta_signatures:
                        continue
                    if sig:
                        seen_meta_signatures.add(sig)
                _render_region(
                    document,
                    region,
                    usable_twips=usable_twips,
                    lang=lang,
                    strip_bidi_controls=strip_bidi_controls,
                    font_name=font_name,
                    sizes_map=sizes_map,
                    top_left_crest_asset=None,
                    compact=(bundle.document.page_archetype in {"citius_notification", "form_record"}),
                )

    body_paragraphs = list(document._element.body.iter(qn("w:p")))
    visible_paragraphs = sum(
        bool("".join(node.text or "" for node in p.iter(qn("w:t"))).strip())
        for p in body_paragraphs
    )
    if stats is not None:
        stats["paragraph_count"] = len(body_paragraphs)
        stats["run_count"] = len(list(document._element.body.iter(qn("w:r"))))
        stats["page_count"] = len(bundles)
        stats["source_page_count"] = len(bundles)
        stats["structured_page_count"] = len(bundles)
        stats["section_count"] = len(sections_groups)

    result_path = save_document_atomic(document, output_path, verify_readable=verify_readable)
    saved_summary = _verify_docx_visible_content(
        result_path,
        stage="save",
        expected_visible_paragraphs=visible_paragraphs,
    )
    _ensure_primary_compatibility_mode15(result_path)
    _verify_docx_visible_content(
        result_path,
        stage="compatibility rewrite",
        expected_visible_paragraphs=visible_paragraphs,
        baseline=saved_summary,
    )
    return result_path
