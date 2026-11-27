"""Comprehensive offline tests for gemini_structural_v1 extraction, schema, OOXML assembly, and workflow."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile
import xml.etree.ElementTree as ET

import fitz
from PIL import Image, ImageDraw
import pytest

from legalpdf_translate import gemini_decisions
from legalpdf_translate import workflow as workflow_module
from legalpdf_translate.accounting_policy import gemini_accounting_policy
from legalpdf_translate.gemini_client import GeminiInteractionsClient
from legalpdf_translate.gemini_structural_schema import (
    PageStructuralDocument,
    StructuralValidationError,
    gemini_structural_response_format,
    parse_and_validate_structural_page,
)
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.source_structural_evidence import extract_source_structural_evidence
from legalpdf_translate.structural_docx_assembler import StructuralPageBundle, assemble_structural_docx
from legalpdf_translate.types import ImageMode, OcrMode, ReasoningEffort, RunConfig, TargetLang
from legalpdf_translate.workflow import TranslationWorkflow

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _qn(tag: str) -> str:
    return f"{{{W_NS}}}{tag}"


def _make_crest_png_bytes() -> bytes:
    img = Image.new("RGB", (90, 72), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((10, 8, 80, 64), outline="black", width=3)
    draw.ellipse((25, 18, 65, 54), fill=(30, 60, 120), outline="black", width=2)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _create_synthetic_despacho_pdf(path: Path) -> None:
    doc = fitz.open()
    p1 = doc.new_page(width=595.3, height=841.9)
    p1.insert_image(fitz.Rect(267, 28, 328, 76), stream=_make_crest_png_bytes())
    p1.insert_text((195, 95), "MINISTERIO PUBLICO", fontsize=11)
    # 1x3 metadata rule band lines
    p1.draw_line((68, 125), (527, 125), width=1.0)
    p1.draw_line((68, 165), (527, 165), width=1.0)
    p1.insert_text((74, 148), "Processo: 123/25.0T9BJA", fontsize=10)
    p1.insert_text((240, 148), "Inquerito", fontsize=10)
    p1.insert_text((415, 148), "Ref: 998877", fontsize=10)
    # First-line indented multi-line paragraph block
    p1.insert_text((104, 210), "Os presentes autos tiveram inicio com participacao formal elaborada", fontsize=12)
    p1.insert_text((68, 226), "pela autoridade policial competente junto do tribunal de Beja em", fontsize=12)
    p1.insert_text((68, 242), "12 de janeiro de 2025 relativamente aos factos descritos no auto.", fontsize=12)

    p2 = doc.new_page(width=595.3, height=841.9)
    p2.insert_text((68, 120), "Em face do exposto, determina-se a notificacao do arguido para comparecer.", fontsize=12)
    doc.save(path)
    doc.close()


def _create_synthetic_vector_citius_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=595.4, height=841.7)
    # Two horizontal full-width band dividers & two-column outline glyph proxies (zero embedded text)
    page.draw_line((30, 270), (230, 270), width=0.8)
    page.draw_line((258, 270), (560, 270), width=0.8)
    page.draw_line((30, 440), (230, 440), width=0.8)
    page.draw_line((258, 440), (560, 440), width=0.8)
    for idx in range(30):
        y = 120 + idx * 14
        page.draw_rect(fitz.Rect(35, y, 180, y + 8), color=(0, 0, 0), width=0.5)
        page.draw_rect(fitz.Rect(265, y, 520, y + 8), color=(0, 0, 0), width=0.5)
    doc.save(path)
    doc.close()


def _sample_citius_page_json(*, document_starts_here: bool = True, footer_counter: str = "Page {page} of {total}") -> dict:
    return {
        "schema_version": "gemini_structural_v1",
        "page_archetype": "citius_notification",
        "document_starts_here": document_starts_here,
        "continuation_from_previous": False,
        "margins_pt": {"left": 45.0, "right": 45.0, "top": 40.0, "bottom": 44.0},
        "font_preference": "arial_11_5",
        "header_stationery": {
            "present": False,
            "style": "none",
            "top_left_stamp_lines": [],
            "center_crest_present": False,
            "center_institution_lines": [],
            "sub_line": "",
        },
        "footer_stationery": {
            "present": True,
            "court_contact_lines": ["Indicate this reference on reply | Beja Local Criminal Court"],
            "page_counter_template": footer_counter,
            "legal_note": "During judicial holidays deadlines follow statutory rules.",
        },
        "regions": [
            {
                "kind": "two_col_panel",
                "left_width_pct": 42,
                "col_widths_pct": [],
                "border_style": "none",
                "vertical_divider": True,
                "header_row": False,
                "left_items": [
                    {
                        "item_type": "heading_2",
                        "align": "left",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "none",
                        "shading": "none",
                        "size_role": "small",
                        "keep_with_next": True,
                        "runs": [{"text": "Beja Judicial Court", "bold": True, "italic": False, "underline": False}],
                    },
                    {
                        "item_type": "paragraph",
                        "align": "left",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "none",
                        "shading": "none",
                        "size_role": "small",
                        "keep_with_next": False,
                        "runs": [{"text": "Rua Example 12, 7800-001 Beja", "bold": False, "italic": False, "underline": False}],
                    },
                ],
                "right_items": [
                    {
                        "item_type": "title",
                        "align": "left",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "none",
                        "shading": "none",
                        "size_role": "heading",
                        "keep_with_next": True,
                        "runs": [{"text": "Notification by Ordinary Post", "bold": True, "italic": False, "underline": False}],
                    },
                    {
                        "item_type": "paragraph",
                        "align": "left",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "none",
                        "shading": "none",
                        "size_role": "body",
                        "keep_with_next": False,
                        "runs": [
                            {"text": "Case No.: ", "bold": True, "italic": False, "underline": False},
                            {"text": "123/25.0T9BJA", "bold": False, "italic": False, "underline": False},
                        ],
                    },
                ],
                "metadata_cells": [],
                "table_rows": [],
                "flow_items": [],
            },
            {
                "kind": "flow_block",
                "left_width_pct": 50,
                "col_widths_pct": [],
                "border_style": "none",
                "vertical_divider": False,
                "header_row": False,
                "left_items": [],
                "right_items": [],
                "metadata_cells": [],
                "table_rows": [],
                "flow_items": [
                    {
                        "item_type": "horizontal_rule",
                        "align": "center",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "bottom",
                        "shading": "none",
                        "size_role": "small",
                        "keep_with_next": False,
                        "runs": [],
                    }
                ],
            },
            {
                "kind": "two_col_panel",
                "left_width_pct": 38,
                "col_widths_pct": [],
                "border_style": "left_shaded_panel",
                "vertical_divider": True,
                "header_row": False,
                "left_items": [
                    {
                        "item_type": "paragraph",
                        "align": "left",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "none",
                        "shading": "none",
                        "size_role": "small",
                        "keep_with_next": False,
                        "runs": [{"text": "Legal Aid Contact Details", "bold": True, "italic": True, "underline": False}],
                    }
                ],
                "right_items": [
                    {
                        "item_type": "callout_box",
                        "align": "justify",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "box",
                        "shading": "light_gray",
                        "size_role": "body",
                        "keep_with_next": False,
                        "runs": [
                            {"text": "Notice: ", "bold": True, "italic": False, "underline": False},
                            {"text": "You are hereby notified to appear before Beja Court.", "bold": False, "italic": False, "underline": False},
                        ],
                    }
                ],
                "metadata_cells": [],
                "table_rows": [],
                "flow_items": [],
            },
        ],
    }


def _sample_despacho_page_json(*, starts_here: bool = True, continuation: bool = False) -> dict:
    return {
        "schema_version": "gemini_structural_v1",
        "page_archetype": "despacho",
        "document_starts_here": starts_here,
        "continuation_from_previous": continuation,
        "margins_pt": {"left": 68.0, "right": 68.0, "top": 108.0, "bottom": 52.0},
        "font_preference": "times_12",
        "header_stationery": {
            "present": True,
            "style": "court_despacho_stationery",
            "top_left_stamp_lines": ["Electronically signed", "Ref. 998877"],
            "center_crest_present": True,
            "center_institution_lines": ["Public Prosecutor's Office", "District of Beja"],
            "sub_line": "Department of Investigation and Penal Action",
        },
        "footer_stationery": {
            "present": True,
            "court_contact_lines": ["Largo Example, No. 1, 7800-001 Beja"],
            "page_counter_template": "Page {page} of {total}",
            "legal_note": "",
        },
        "regions": [
            {
                "kind": "metadata_rule_band",
                "left_width_pct": 50,
                "col_widths_pct": [28, 44, 28],
                "border_style": "top_bottom_inside_v",
                "vertical_divider": False,
                "header_row": False,
                "left_items": [],
                "right_items": [],
                "metadata_cells": [
                    {
                        "align": "left",
                        "paragraphs": [
                            {
                                "item_type": "paragraph",
                                "align": "left",
                                "indent_style": "none",
                                "first_line_indent_cm": 0.0,
                                "left_indent_cm": 0.0,
                                "border": "none",
                                "shading": "none",
                                "size_role": "small",
                                "keep_with_next": False,
                                "runs": [
                                    {"text": "Case No.: ", "bold": True, "italic": False, "underline": False},
                                    {"text": "123/25.0T9BJA", "bold": False, "italic": False, "underline": False},
                                ],
                            }
                        ],
                    },
                    {
                        "align": "center",
                        "paragraphs": [
                            {
                                "item_type": "paragraph",
                                "align": "center",
                                "indent_style": "none",
                                "first_line_indent_cm": 0.0,
                                "left_indent_cm": 0.0,
                                "border": "none",
                                "shading": "none",
                                "size_role": "small",
                                "keep_with_next": False,
                                "runs": [{"text": "Inquiry Proceedings", "bold": True, "italic": False, "underline": False}],
                            }
                        ],
                    },
                    {
                        "align": "right",
                        "paragraphs": [
                            {
                                "item_type": "paragraph",
                                "align": "right",
                                "indent_style": "none",
                                "first_line_indent_cm": 0.0,
                                "left_indent_cm": 0.0,
                                "border": "none",
                                "shading": "none",
                                "size_role": "small",
                                "keep_with_next": False,
                                "runs": [{"text": "Ref: 998877", "bold": False, "italic": False, "underline": False}],
                            }
                        ],
                    },
                ],
                "table_rows": [],
                "flow_items": [],
            },
            {
                "kind": "flow_block",
                "left_width_pct": 50,
                "col_widths_pct": [],
                "border_style": "none",
                "vertical_divider": False,
                "header_row": False,
                "left_items": [],
                "right_items": [],
                "metadata_cells": [],
                "table_rows": [],
                "flow_items": [
                    {
                        "item_type": "heading_1",
                        "align": "left",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "none",
                        "shading": "none",
                        "size_role": "heading",
                        "keep_with_next": True,
                        "runs": [{"text": "I. Preliminary Order", "bold": True, "italic": False, "underline": False}],
                    },
                    {
                        "item_type": "paragraph",
                        "align": "justify",
                        "indent_style": "first_line",
                        "first_line_indent_cm": 1.25,
                        "left_indent_cm": 0.0,
                        "border": "none",
                        "shading": "none",
                        "size_role": "body",
                        "keep_with_next": False,
                        "runs": [
                            {
                                "text": "These proceedings originated from an official report submitted by the police authority on 12 January 2025.",
                                "bold": False,
                                "italic": False,
                                "underline": False,
                            }
                        ],
                    },
                    {
                        "item_type": "list_number",
                        "align": "justify",
                        "indent_style": "hanging",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 1.2,
                        "border": "none",
                        "shading": "none",
                        "size_role": "body",
                        "keep_with_next": False,
                        "runs": [{"text": "1. Notify the defendant for questioning pursuant to Article 58.", "bold": False, "italic": False, "underline": False}],
                    },
                    {
                        "item_type": "divider_stars",
                        "align": "center",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "none",
                        "shading": "none",
                        "size_role": "body",
                        "keep_with_next": False,
                        "runs": [],
                    },
                ],
            },
        ],
    }


def _sample_arabic_form_page_json() -> dict:
    return {
        "schema_version": "gemini_structural_v1",
        "page_archetype": "form_record",
        "document_starts_here": True,
        "continuation_from_previous": False,
        "margins_pt": {"left": 45.0, "right": 45.0, "top": 42.0, "bottom": 48.0},
        "font_preference": "arial_12_5",
        "header_stationery": {
            "present": True,
            "style": "police_form_header",
            "top_left_stamp_lines": [],
            "center_crest_present": False,
            "center_institution_lines": ["الشرطة القضائية - وحدة التحقيق"],
            "sub_line": "محضر استماع لشاهد",
        },
        "footer_stationery": {
            "present": True,
            "court_contact_lines": ["المرجع: [[NUIPC-4455/25]]"],
            "page_counter_template": "الصفحة {page} من {total}",
            "legal_note": "",
        },
        "regions": [
            {
                "kind": "flow_block",
                "left_width_pct": 50,
                "col_widths_pct": [],
                "border_style": "none",
                "vertical_divider": False,
                "header_row": False,
                "left_items": [],
                "right_items": [],
                "metadata_cells": [],
                "table_rows": [],
                "flow_items": [
                    {
                        "item_type": "heading_1",
                        "align": "right",
                        "indent_style": "none",
                        "first_line_indent_cm": 0.0,
                        "left_indent_cm": 0.0,
                        "border": "bottom",
                        "shading": "none",
                        "size_role": "heading",
                        "keep_with_next": True,
                        "runs": [{"text": "البيانات التعريفية", "bold": True, "italic": False, "underline": False}],
                    }
                ],
            },
            {
                "kind": "table",
                "left_width_pct": 50,
                "col_widths_pct": [26, 74],
                "border_style": "full_grid",
                "vertical_divider": False,
                "header_row": True,
                "left_items": [],
                "right_items": [],
                "metadata_cells": [],
                "table_rows": [
                    {
                        "cells": [
                            {
                                "col_span": 1,
                                "shading": "none",
                                "align": "right",
                                "paragraphs": [
                                    {
                                        "item_type": "paragraph",
                                        "align": "right",
                                        "indent_style": "none",
                                        "first_line_indent_cm": 0.0,
                                        "left_indent_cm": 0.0,
                                        "border": "none",
                                        "shading": "none",
                                        "size_role": "body",
                                        "keep_with_next": False,
                                        "runs": [{"text": "الحقل", "bold": True, "italic": False, "underline": False}],
                                    }
                                ],
                            },
                            {
                                "col_span": 1,
                                "shading": "none",
                                "align": "right",
                                "paragraphs": [
                                    {
                                        "item_type": "paragraph",
                                        "align": "right",
                                        "indent_style": "none",
                                        "first_line_indent_cm": 0.0,
                                        "left_indent_cm": 0.0,
                                        "border": "none",
                                        "shading": "none",
                                        "size_role": "body",
                                        "keep_with_next": False,
                                        "runs": [{"text": "القيمة", "bold": True, "italic": False, "underline": False}],
                                    }
                                ],
                            },
                        ]
                    },
                    {
                        "cells": [
                            {
                                "col_span": 1,
                                "shading": "none",
                                "align": "right",
                                "paragraphs": [
                                    {
                                        "item_type": "paragraph",
                                        "align": "right",
                                        "indent_style": "none",
                                        "first_line_indent_cm": 0.0,
                                        "left_indent_cm": 0.0,
                                        "border": "none",
                                        "shading": "none",
                                        "size_role": "body",
                                        "keep_with_next": False,
                                        "runs": [{"text": "الاسم الكامل", "bold": True, "italic": False, "underline": False}],
                                    }
                                ],
                            },
                            {
                                "col_span": 1,
                                "shading": "none",
                                "align": "right",
                                "paragraphs": [
                                    {
                                        "item_type": "paragraph",
                                        "align": "right",
                                        "indent_style": "none",
                                        "first_line_indent_cm": 0.0,
                                        "left_indent_cm": 0.0,
                                        "border": "none",
                                        "shading": "none",
                                        "size_role": "body",
                                        "keep_with_next": False,
                                        "runs": [
                                            {"text": "[[João Silva]] رقم [[123/25]]", "bold": False, "italic": False, "underline": False}
                                        ],
                                    }
                                ],
                            },
                        ]
                    },
                ],
                "flow_items": [],
            },
        ],
    }


def test_gemini_structural_json_schema_is_inline_and_strict() -> None:
    fmt = gemini_structural_response_format()
    assert fmt["type"] == "json_schema"
    assert fmt["strict"] is True
    raw = json.dumps(fmt["schema"])
    assert "$defs" not in raw
    assert "$ref" not in raw
    assert "regions" in fmt["schema"]["properties"]


def test_source_structural_evidence_handles_vector_outlined_and_crest_pdfs(tmp_path: Path) -> None:
    vector_pdf = tmp_path / "citius_vector.pdf"
    despacho_pdf = tmp_path / "despacho.pdf"
    _create_synthetic_vector_citius_pdf(vector_pdf)
    _create_synthetic_despacho_pdf(despacho_pdf)

    vec_ev = extract_source_structural_evidence(vector_pdf, 0)
    assert vec_ev.vector_outlined_text_likely is True
    assert vec_ev.two_column_bands_detected is True
    assert vec_ev.suggested_archetype == "citius_notification"

    desp_ev = extract_source_structural_evidence(despacho_pdf, 0)
    assert desp_ev.has_top_center_crest is True
    assert desp_ev.crest_asset is not None
    assert desp_ev.metadata_band_detected is True
    assert desp_ev.first_line_indent_pt is not None
    assert desp_ev.suggested_archetype == "despacho"


def test_parse_structural_page_en_and_ar_validation_and_space_preservation() -> None:
    raw_en = json.dumps(_sample_despacho_page_json())
    doc, flat, meta = parse_and_validate_structural_page(raw_en, lang=TargetLang.EN)
    assert meta["archetype"] == "despacho"
    assert "Case No.: 123/25.0T9BJA" in flat
    assert doc.regions[1].flow_items[1].first_line_indent_cm == 1.25

    leaking = _sample_despacho_page_json()
    leaking["regions"][1]["flow_items"][1]["runs"][0]["text"] = "Tribunal Judicial de Beja decidiu em 12 de janeiro de 2025."
    with pytest.raises(StructuralValidationError) as exc_info:
        parse_and_validate_structural_page(json.dumps(leaking), lang=TargetLang.EN)
    assert exc_info.value.code == "pt_language_leak"

    raw_ar = json.dumps(_sample_arabic_form_page_json(), ensure_ascii=False)
    doc_ar, flat_ar, _ = parse_and_validate_structural_page(
        raw_ar,
        lang=TargetLang.AR,
        expected_ar_tokens=["NUIPC-4455/25", "João Silva", "123/25"],
    )
    assert "\u2066[[João Silva]]\u2069" in flat_ar

    # Expected simple tokens get autofixed cleanly, while unwrapped foreign Latin words still fail validation.
    raw_ar_fixable = raw_ar.replace("[[123/25]]", "123/25")
    _, flat_fixed, meta_ar = parse_and_validate_structural_page(
        raw_ar_fixable,
        lang=TargetLang.AR,
        expected_ar_tokens=["NUIPC-4455/25", "João Silva", "123/25"],
    )
    assert meta_ar["autofix_applied_count"] >= 1
    assert "\u2066[[123/25]]\u2069" in flat_fixed

    raw_ar_bad = raw_ar.replace("الاسم الكامل", "Tribunal de Beja")
    with pytest.raises(StructuralValidationError) as exc_ar:
        parse_and_validate_structural_page(
            raw_ar_bad,
            lang=TargetLang.AR,
            expected_ar_tokens=["NUIPC-4455/25", "João Silva", "123/25"],
        )
    assert exc_ar.value.code == "ar_latin_or_digits_outside_tokens"


def test_assemble_structural_docx_multidoc_en_and_rtl_ar_form(tmp_path: Path) -> None:
    despacho_pdf = tmp_path / "despacho.pdf"
    _create_synthetic_despacho_pdf(despacho_pdf)
    desp_ev = extract_source_structural_evidence(despacho_pdf, 0)

    citius_doc = PageStructuralDocument.model_validate(_sample_citius_page_json(document_starts_here=True))
    desp_doc_1 = PageStructuralDocument.model_validate(_sample_despacho_page_json(starts_here=True, continuation=False))
    desp_doc_2 = PageStructuralDocument.model_validate(_sample_despacho_page_json(starts_here=False, continuation=True))

    out_en = tmp_path / "combined_en.docx"
    stats: dict[str, int] = {}
    assemble_structural_docx(
        [
            StructuralPageBundle(1, citius_doc),
            StructuralPageBundle(2, desp_doc_1, crest_asset=desp_ev.crest_asset),
            StructuralPageBundle(3, desp_doc_2, crest_asset=desp_ev.crest_asset),
        ],
        out_en,
        lang=TargetLang.EN,
        page_breaks=True,
        stats=stats,
    )
    assert out_en.is_file()
    assert stats["section_count"] == 2

    with ZipFile(out_en) as z:
        names = z.namelist()
        assert any(n.startswith("word/media/") for n in names)
        assert "word/header2.xml" in names
        assert "word/footer1.xml" in names and "word/footer2.xml" in names
        root = ET.fromstring(z.read("word/document.xml"))
        sects = list(root.iter(_qn("sectPr")))
        assert len(sects) == 2
        tbl_borders = [{c.tag.split("}")[-1]: c.get(_qn("val")) for c in bdr} for bdr in root.iter(_qn("tblBorders"))]
        assert any(b.get("top") == "single" and b.get("bottom") == "single" and b.get("left") == "nil" for b in tbl_borders)
        footer_parts = [n for n in names if n.startswith("word/footer")]
        assert footer_parts
        assert all("PAGE" in z.read(fn).decode("utf-8") and "SECTIONPAGES" in z.read(fn).decode("utf-8") for fn in footer_parts)
        settings_xml = z.read("word/settings.xml").decode("utf-8")
        assert 'compatibilityMode' in settings_xml and 'val="15"' in settings_xml

    # Arabic form with bordered table + bidiVisual + RTL + clean placeholder unwrap
    raw_ar = json.dumps(_sample_arabic_form_page_json(), ensure_ascii=False)
    doc_ar, _, _ = parse_and_validate_structural_page(raw_ar, lang=TargetLang.AR)
    out_ar = tmp_path / "form_ar.docx"
    assemble_structural_docx(
        [StructuralPageBundle(1, doc_ar)],
        out_ar,
        lang=TargetLang.AR,
        strip_bidi_controls=True,
    )
    with ZipFile(out_ar) as z:
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "[[" not in doc_xml and "]]" not in doc_xml
        assert "João Silva" in doc_xml
        root = ET.fromstring(doc_xml)
        assert any(t.find(_qn("tblPr")).find(_qn("bidiVisual")) is not None for t in root.iter(_qn("tbl")))
        assert any(p.find(_qn("pPr")).find(_qn("bidi")) is not None for p in root.iter(_qn("p")) if p.find(_qn("pPr")) is not None)


def test_workflow_gemini_structural_pipeline_resume_partial_rebuild_and_decisions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "despacho_input.pdf"
    outdir = tmp_path / "out"
    outdir.mkdir()
    _create_synthetic_despacho_pdf(pdf_path)

    class _FakeGeminiStructuralClient(GeminiInteractionsClient):
        def __init__(self) -> None:
            super().__init__(api_key="fake-gem-key", model="gemini-4-neon", max_transport_retries=0)
            self.calls: list[dict] = []

        def create_page_response(self, **kwargs):
            self.calls.append(kwargs)
            prompt = kwargs["prompt_text"]
            page_num = 1 if "PAGE 1 OF" in prompt else 2
            if len(self.calls) == 1:
                # Force attempt-1 PT language leak -> verify attempt-2 recovery fixes it!
                bad = _sample_despacho_page_json(starts_here=True, continuation=False)
                bad["regions"][1]["flow_items"][1]["runs"][0]["text"] = "Tribunal Judicial de Beja em 12 de janeiro de 2025."
                raw = json.dumps(bad)
            else:
                payload = _sample_despacho_page_json(
                    starts_here=(page_num == 1),
                    continuation=(page_num > 1),
                )
                raw = json.dumps(payload)
            return ApiCallResult(
                raw_output=raw,
                usage={"input_tokens": 200, "output_tokens": 180, "reasoning_tokens": 40, "total_tokens": 420},
                response_id=f"gem-struct-{len(self.calls)}",
                response_status="completed",
                model="gemini-4-neon",
                effort=kwargs["effort"],
            )

    decision_calls = []

    class _FakeDecisionSdk:
        def __init__(self) -> None:
            self.decisions = SimpleNamespace(create=self._create)

        def _create(self, **kwargs):
            decision_calls.append(kwargs)
            return SimpleNamespace(
                usage=SimpleNamespace(total_input_tokens=30, total_output_tokens=0, total_tokens=30),
                answers=[
                    SimpleNamespace(noul=0.95, confidence=0.95),
                    SimpleNamespace(choice="aligned", confidence=0.93, probabilities={"aligned": 0.93}),
                ],
            )

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gem-key")
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {"translation_provider": "gemini"})
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(
        workflow_module,
        "run_translation_auth_test",
        lambda *a, **k: SimpleNamespace(ok=True, status="ok", message="ok", credential_source=SimpleNamespace(kind="env", name="GEMINI_API_KEY"), status_code=200, exception_class=""),
    )
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {"translation_provider": "gemini"})
    monkeypatch.setattr(gemini_decisions, "resolve_gemini_key_with_source", lambda *a, **k: ("fake-gem-key", None))
    monkeypatch.setattr(gemini_decisions, "_create_decisions_client", lambda key: _FakeDecisionSdk())

    client = _FakeGeminiStructuralClient()
    config = RunConfig(
        pdf_path=pdf_path,
        output_dir=outdir,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.XHIGH,
        image_mode=ImageMode.AUTO,
        ocr_mode=OcrMode.OFF,
        workers=1,
        resume=True,
        gemini_decisions_advisory_enabled=True,
    )
    wf = TranslationWorkflow(
        client=client,
        gui_settings={"translation_provider": "gemini"},
        accounting_policy=gemini_accounting_policy(),
    )
    summary = wf.run(config)
    assert summary.success, summary.error
    assert summary.output_docx is not None and summary.output_docx.is_file()
    # Page 1 took 2 calls (leak retry), Page 2 took 1 call, both with high-detail images & response_format
    assert len(client.calls) == 3
    assert all("response_format" in c and c["image_data_url"] is not None and c["image_detail"] == "high" for c in client.calls)
    assert any("Structural DOCX reconstruction summary" in str(c) for c in decision_calls)
    assert wf._last_structural_advisory is not None
    assert wf._last_structural_advisory["parity_triage"] == "aligned"

    pages_dir = summary.run_dir / "pages"
    assert (pages_dir / "page_0001.structural.json").is_file()
    assert (pages_dir / "page_0002.structural.json").is_file()

    # Partial export and offline rebuild preserve rich structural crest & metadata rule table
    partial = wf.export_partial_docx()
    assert partial is not None and partial.is_file()
    rebuilt = wf.rebuild_docx(config)
    assert rebuilt.is_file()
    with ZipFile(rebuilt) as z:
        assert any(n.startswith("word/media/") for n in z.namelist())
        assert "123/25.0T9BJA" in z.read("word/document.xml").decode("utf-8")

    # Resume with unchanged config makes zero additional API calls
    resumed = TranslationWorkflow(
        client=client,
        gui_settings={"translation_provider": "gemini"},
        accounting_policy=gemini_accounting_policy(),
    ).run(config)
    assert resumed.success
    assert len(client.calls) == 3


def test_gemini_structural_protocol_activates_for_browser_qt_and_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import time
    from legalpdf_translate import cli
    from legalpdf_translate import translation_service
    from legalpdf_translate.qt_gui import worker as qt_worker
    from legalpdf_translate.translation_policy import resolve_provider_translation_protocol

    monkeypatch.delenv("LEGALPDF_TRANSLATION_PROTOCOL", raising=False)
    assert resolve_provider_translation_protocol(provider="gemini") == "gemini_structural_v1"
    assert resolve_provider_translation_protocol(provider="openai") == "legacy_text_v1"

    pdf_path = tmp_path / "citius_notice.pdf"
    _create_synthetic_vector_citius_pdf(pdf_path)

    class _FakeBrowserGemini(GeminiInteractionsClient):
        def __init__(self, **kw) -> None:
            super().__init__(api_key="fake-gem", model="gemini-4-neon", max_transport_retries=0)

        def create_page_response(self, **kwargs):
            assert kwargs.get("response_format", {}).get("name") == "gemini_structural_v1"
            return ApiCallResult(
                raw_output=json.dumps(_sample_citius_page_json()),
                usage={"input_tokens": 120, "output_tokens": 90, "reasoning_tokens": 20, "total_tokens": 230},
                response_id="gem-caller-1",
                response_status="completed",
                model="gemini-4-neon",
                effort=kwargs["effort"],
            )

    monkeypatch.setenv("GEMINI_API_KEY", "fake-gem-key")
    monkeypatch.setattr(workflow_module, "load_gui_settings", lambda: {"translation_provider": "gemini"})
    monkeypatch.setattr(workflow_module, "load_environment", lambda: None)
    monkeypatch.setattr(
        workflow_module,
        "run_translation_auth_test",
        lambda *a, **k: SimpleNamespace(ok=True, status="ok", message="ok", credential_source=SimpleNamespace(kind="env", name="GEMINI_API_KEY"), status_code=200, exception_class=""),
    )
    monkeypatch.setattr(cli, "load_gui_settings", lambda: {"translation_provider": "gemini"})
    monkeypatch.setattr(qt_worker, "load_gui_settings", lambda: {"translation_provider": "gemini"})
    monkeypatch.setattr(translation_service, "GeminiInteractionsClient", _FakeBrowserGemini)
    monkeypatch.setattr(qt_worker, "GeminiInteractionsClient", _FakeBrowserGemini)
    monkeypatch.setattr(workflow_module, "GeminiInteractionsClient", _FakeBrowserGemini)
    monkeypatch.setattr(workflow_module, "create_translation_client", lambda **kw: _FakeBrowserGemini())

    # 1. Browser TranslationJobManager
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(json.dumps({"translation_provider": "gemini"}), encoding="utf-8")
    out_browser = tmp_path / "out_browser"
    out_browser.mkdir()
    manager = translation_service.TranslationJobManager()
    started = manager.start_translate(
        runtime_mode="shadow",
        workspace_id="gemini-struct-test",
        settings_path=settings_path,
        form_values={
            "translation_provider": "gemini",
            "translation_model": "gemini-4-neon",
            "source_path": str(pdf_path),
            "output_dir": str(out_browser),
            "target_lang": "EN",
            "image_mode": "auto",
            "ocr_mode": "off",
            "workers": 1,
            "resume": False,
        },
    )
    deadline = time.monotonic() + 20.0
    job = manager.get_job(started["job_id"])
    while job and job["status"] in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.02)
        job = manager.get_job(started["job_id"])
    assert job is not None and job["status"] == "completed", job
    assert "automatic_layout" not in (job.get("result") or {})
    docx_browser = Path(job["artifacts"]["output_docx"])
    assert docx_browser.is_file()
    with ZipFile(docx_browser) as z:
        assert "Notification by Ordinary Post" in z.read("word/document.xml").decode("utf-8")

    # 2. Qt TranslationRunWorker
    out_qt = tmp_path / "out_qt"
    out_qt.mkdir()
    cfg_qt = RunConfig(
        pdf_path=pdf_path,
        output_dir=out_qt,
        target_lang=TargetLang.EN,
        effort=ReasoningEffort.XHIGH,
        image_mode=ImageMode.AUTO,
        ocr_mode=OcrMode.OFF,
        workers=1,
        resume=False,
    )
    worker = qt_worker.TranslationRunWorker(config=cfg_qt, max_transport_retries=0, backoff_cap_seconds=1.0)
    finished, errors = [], []
    worker.finished.connect(finished.append)
    worker.error.connect(errors.append)
    worker.run()
    assert not errors and len(finished) == 1 and finished[0].success

    # 3. CLI
    out_cli = tmp_path / "out_cli"
    out_cli.mkdir()
    rc = cli.main([
        "--pdf", str(pdf_path),
        "--lang", "EN",
        "--outdir", str(out_cli),
        "--provider", "gemini",
        "--images", "auto",
        "--ocr-mode", "off",
        "--workers", "1",
        "--resume", "false",
    ])
    assert rc == 0
    assert any(out_cli.glob("*.docx"))


def test_compact_styled_paragraph_text_and_top_left_crest_rendering(tmp_path: Path) -> None:
    pdf_path = tmp_path / "top_left_crest.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(fitz.Rect(28, 22, 92, 74), stream=_make_crest_png_bytes())
    page.insert_text((100, 42), "MINISTERIO PUBLICO - Beja", fontsize=11)
    page.insert_text((360, 42), "Official Letter 123/26", fontsize=11)
    doc.save(pdf_path)
    doc.close()

    ev = extract_source_structural_evidence(pdf_path, 0)
    assert ev.crest_asset is not None
    assert ev.has_top_center_crest is False
    assert ev.crest_asset.bbox_norm[0] < 0.25

    compact_raw = json.dumps(
        {
            "schema_version": "ignored_any_string",
            "page_archetype": "citius_notification",
            "document_starts_here": True,
            "regions": [
                {
                    "kind": "two_col_panel",
                    "left_width_pct": 48,
                    "left_items": [
                        {"text": "Public Prosecutor's Office - Beja", "bold": True},
                    ],
                    "right_items": [
                        {"text": "Official Letter 123/26", "bold": True},
                    ],
                },
                {
                    "kind": "flow_block",
                    "flow_items": [
                        {"text": "Notification of inquiry closure.", "item_type": "paragraph"},
                    ],
                },
            ],
        }
    )
    parsed, flat, meta = parse_and_validate_structural_page(compact_raw, lang=TargetLang.EN)
    assert meta["archetype"] == "citius_notification"
    assert parsed.schema_version == "gemini_structural_v1"
    assert "Public Prosecutor's Office - Beja" in flat

    out_docx = tmp_path / "top_left_crest.docx"
    assemble_structural_docx([StructuralPageBundle(1, parsed, crest_asset=ev.crest_asset)], out_docx, lang=TargetLang.EN)
    with ZipFile(out_docx) as z:
        assert any(n.startswith("word/media/") for n in z.namelist())
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "Public Prosecutor" in doc_xml
        assert "Notification of inquiry closure." in doc_xml

    with pytest.raises(StructuralValidationError) as exc_bad:
        parse_and_validate_structural_page(json.dumps({"regions": "not_a_list"}), lang=TargetLang.EN)
    assert exc_bad.value.code == "invalid_structural_schema"
    assert "regions:" in exc_bad.value.details.get("error_summary", "")

    # Arabic high-signal identifiers must remain preserved while page counter "1" does not cause false mismatch
    raw_ar = json.dumps(_sample_arabic_form_page_json(), ensure_ascii=False)
    doc_ar_page, flat_ar_page, _ = parse_and_validate_structural_page(
        raw_ar,
        lang=TargetLang.AR,
        expected_ar_tokens=["NUIPC-4455/25", "123/25", "1"],
    )
    assert "NUIPC-4455/25" in flat_ar_page
    with pytest.raises(StructuralValidationError) as exc_missing_id:
        parse_and_validate_structural_page(
            raw_ar,
            lang=TargetLang.AR,
            expected_ar_tokens=["NUIPC-4455/25", "999/26.9PBBJA"],
        )
    assert exc_missing_id.value.code == "ar_token_violation"

    # Signature underscores are capped cleanly to avoid multi-line wrap spillover
    sig_doc = PageStructuralDocument.model_validate(
        {
            "page_archetype": "form_record",
            "regions": [
                {
                    "kind": "flow_block",
                    "flow_items": [{"text": "Interpreter: " + ("_" * 80), "item_type": "signature_block"}],
                }
            ],
        }
    )
    sig_docx = tmp_path / "sig_capped.docx"
    assemble_structural_docx([StructuralPageBundle(1, sig_doc)], sig_docx, lang=TargetLang.EN)
    with ZipFile(sig_docx) as z:
        assert ("_" * 60) not in z.read("word/document.xml").decode("utf-8")


def test_rtl_crest_logical_jc_ppr_order_and_form_continuation_header(tmp_path: Path) -> None:
    import xml.etree.ElementTree as ET

    # Wide banner (w/h > 2.6) must be ignored in favor of compact Coat of Arms crest.
    banner_pdf = tmp_path / "police_banner.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Compact crest at x0=153 (~0.257 * page_w)
    page.insert_image(fitz.Rect(153, 16, 179, 42), stream=_make_crest_png_bytes())
    # Wide banner wordmark 4.4:1
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 220, 50), False)
    pix.clear_with(200)
    page.insert_image(fitz.Rect(57, 63, 170, 89), stream=pix.tobytes("png"))
    doc.save(banner_pdf)
    doc.close()

    ev = extract_source_structural_evidence(banner_pdf, 0)
    assert ev.crest_asset is not None
    assert (ev.crest_asset.width_pt / max(1.0, ev.crest_asset.height_pt)) <= 2.6

    ar_citius = PageStructuralDocument.model_validate(
        {
            "page_archetype": "citius_notification",
            "document_starts_here": True,
            "footer_stationery": {"present": True, "page_counter_template": "صفحة [[1]]"},
            "regions": [
                {
                    "kind": "two_col_panel",
                    "left_width_pct": 52,
                    "left_items": [{"text": "النيابة العامة", "align": "right", "bold": True}],
                    "right_items": [{"text": "إشعار", "align": "left"}, {"text": "[[123/25]]", "align": "right"}],
                },
                {
                    "kind": "flow_block",
                    "flow_items": [{"text": "الموضوع: إشعار", "align": "right", "border": "bottom"}],
                },
            ],
        }
    )
    form_p1 = PageStructuralDocument.model_validate(
        {
            "page_archetype": "form_record",
            "document_starts_here": True,
            "header_stationery": {
                "present": True,
                "style": "police_form_header",
                "center_crest_present": True,
                "center_institution_lines": ["وزارة الإدارة الداخلية", "شرطة الأمن العام"],
                "top_left_stamp_lines": ["[[NPP: 431789/2025]]"],
            },
            "footer_stationery": {"present": True, "legal_note": "وثيقة معالجة بالحاسوب"},
            "regions": [
                {
                    "kind": "flow_block",
                    "flow_items": [{"text": "الإجراء", "item_type": "heading_1", "align": "right", "border": "bottom"}],
                },
                {
                    "kind": "table",
                    "col_widths_pct": [30, 70],
                    "border_style": "none",
                    "table_rows": [{"cells": [{"paragraphs": [{"text": "التاريخ:"}]}, {"paragraphs": [{"text": "[[2025-12-03]]"}]}]}],
                },
            ],
        }
    )
    form_p2_cont = PageStructuralDocument.model_validate(
        {
            "page_archetype": "form_record",
            "document_starts_here": False,
            "continuation_from_previous": True,
            "regions": [
                {
                    "kind": "two_col_panel",
                    "left_width_pct": 50,
                    "left_items": [{"text": "شرطة الأمن العام"}],
                    "right_items": [{"text": "[[NPP: 431789/2025]]", "align": "left"}],
                },
                {
                    "kind": "flow_block",
                    "flow_items": [
                        {"item_type": "horizontal_rule", "text": ""},
                        {"text": "تتمة المحضر", "align": "justify"},
                    ],
                },
            ],
        }
    )

    out_docx = tmp_path / "rtl_combined.docx"
    assemble_structural_docx(
        [
            StructuralPageBundle(1, ar_citius, crest_asset=ev.crest_asset),
            StructuralPageBundle(2, form_p1, crest_asset=ev.crest_asset),
            StructuralPageBundle(3, form_p2_cont),
        ],
        out_docx,
        lang=TargetLang.AR,
    )
    WNS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with ZipFile(out_docx) as z:
        # Top-left crest was embedded in RTL citius_notification too.
        assert any(n.startswith("word/media/") for n in z.namelist())
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert "w:val=\"right\"" not in doc_xml
        assert "w:val=\"start\"" in doc_xml
        root = ET.fromstring(doc_xml)
        for ppr in root.findall(f".//{WNS}pPr"):
            tags = [el.tag.split("}")[-1] for el in ppr]
            if "pBdr" in tags and "jc" in tags:
                assert tags.index("pBdr") < tags.index("jc")
        # Leaked continuation header must be promoted to Word header, not inside flowing body.
        footer_parts = [z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/footer")]
        assert any("PAGE" in fp for fp in footer_parts)
        header_parts = [z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/header")]
        assert any("NPP: 431789/2025" in hp for hp in header_parts)
        # Ensure continuation body no longer has duplicate leaked banner before "تتمة المحضر"
        sect2_body_text = "".join(t.text or "" for t in root.findall(f".//{WNS}t"))
        assert "تتمة المحضر" in sect2_body_text
        assert sect2_body_text.count("شرطة الأمن العام") == 0
        # Ensure form_record section has titlePg (different first page header/footer)
        assert "titlePg" in doc_xml


def test_rtl_token_punctuation_lrm_multi_section_and_empty_body_regressions(tmp_path: Path) -> None:
    # 1. Empty body page containing only stationery + divider_stars must fail completeness validation.
    header_only_payload = {
        "page_archetype": "despacho",
        "document_starts_here": False,
        "continuation_from_previous": True,
        "header_stationery": {
            "present": True,
            "style": "court_despacho_stationery",
            "center_crest_present": True,
            "center_institution_lines": ["النيابة العامة"],
        },
        "footer_stationery": {
            "present": True,
            "court_contact_lines": ["قصر العدل - [[7800-597 Beja]]"],
            "page_counter_template": "{page} / {total}",
        },
        "regions": [
            {
                "kind": "flow_block",
                "flow_items": [{"item_type": "divider_stars", "text": "* * *", "align": "center"}],
            }
        ],
    }
    with pytest.raises(StructuralValidationError) as exc_info:
        parse_and_validate_structural_page(
            json.dumps(header_only_payload, ensure_ascii=False),
            lang=TargetLang.AR,
        )
    assert exc_info.value.code == "empty_structural_body"

    # 2. Multi-section RTL DOCX keeps comma in RTL run after [[date]]، protects pure-LTR postal line with LRM,
    # clones consistent continuation header from lead header when stamp differs, and uses SECTIONPAGES + w:start="1" + ltr slash counter.
    sec1_doc = PageStructuralDocument.model_validate(
        {
            "page_archetype": "citius_notification",
            "document_starts_here": True,
            "footer_stationery": {"present": True, "page_counter_template": "صفحة {page} من {total}"},
            "regions": [
                {
                    "kind": "two_col_panel",
                    "left_width_pct": 50,
                    "left_items": [
                        {"text": "قصر العدل - [[Praça Dr. Mário Soares]]", "align": "right"},
                        {"text": "[[7800-597 Beja]]", "align": "right"},
                    ],
                    "right_items": [{"text": "كتاب رسمي", "align": "left"}],
                },
                {
                    "kind": "flow_block",
                    "flow_items": [{"text": "في جلسة [[02-06-2026]]، صرّحت المجني عليها.", "align": "justify"}],
                },
            ],
        }
    )
    sec2_p1 = PageStructuralDocument.model_validate(
        {
            "page_archetype": "despacho",
            "document_starts_here": True,
            "header_stationery": {
                "present": True,
                "style": "court_despacho_stationery",
                "center_crest_present": True,
                "top_left_stamp_lines": ["موقّع بتاريخ [[28-10-2026]]، من قبل"],
                "center_institution_lines": ["النيابة العامة الموحدة"],
            },
            "footer_stationery": {
                "present": True,
                "court_contact_lines": ["قصر العدل - [[Praça Dr. Mário Soares - 7800-597 Beja]]"],
                "page_counter_template": "{page} / {total}",
            },
            "regions": [{"kind": "flow_block", "flow_items": [{"text": "أولاً. تم الاطلاع.", "align": "justify"}]}],
        }
    )
    sec2_p2 = PageStructuralDocument.model_validate(
        {
            "page_archetype": "despacho",
            "document_starts_here": False,
            "continuation_from_previous": True,
            "header_stationery": {
                "present": True,
                "style": "court_despacho_stationery",
                "center_crest_present": True,
                "top_left_stamp_lines": [],
                "center_institution_lines": ["مكتب مختلف غير موحد"],
            },
            "footer_stationery": {
                "present": True,
                "court_contact_lines": ["قصر العدل"],
                "page_counter_template": "{page} / {total}",
            },
            "regions": [{"kind": "flow_block", "flow_items": [{"text": "ثانياً. متابعة الإجراءات.", "align": "justify"}]}],
        }
    )

    out_docx = tmp_path / "audit_regressions.docx"
    assemble_structural_docx(
        [
            StructuralPageBundle(1, sec1_doc),
            StructuralPageBundle(2, sec2_p1),
            StructuralPageBundle(3, sec2_p2),
        ],
        out_docx,
        lang=TargetLang.AR,
    )
    with ZipFile(out_docx) as z:
        doc_xml = z.read("word/document.xml").decode("utf-8")
        assert 'w:start="1"' in doc_xml
        # Arabic comma after [[02-06-2026]] must stay in an RTL run, not merged into LTR date run.
        root = ET.fromstring(doc_xml)
        comma_ok = False
        postal_lrm_ok = False
        for p_el in root.findall(f".//{_qn('p')}"):
            runs = p_el.findall(f".//{_qn('r')}")
            for r_el in runs:
                txt = "".join(t.text or "" for t in r_el.findall(f".//{_qn('t')}"))
                rpr = r_el.find(_qn("rPr"))
                rtl_el = rpr.find(_qn("rtl")) if rpr is not None else None
                rtl_val = rtl_el.attrib.get(_qn("val")) if rtl_el is not None else None
                if "7800-597 Beja" in txt:
                    assert "\u200e" in txt
                    postal_lrm_ok = True
                if txt.lstrip().startswith("،"):
                    assert rtl_val == "1"
                    comma_ok = True
        assert postal_lrm_ok and comma_ok

        # Section 2 continuation header should inherit lead wording instead of drifted wording.
        hdr_texts = "\n".join(z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/header"))
        assert "النيابة العامة الموحدة" in hdr_texts
        assert "مكتب مختلف غير موحد" not in hdr_texts

        # Multi-section document uses SECTIONPAGES, and RTL slash counter uses non-bidi LTR paragraph.
        ftr_xmls = [z.read(n).decode("utf-8") for n in z.namelist() if n.startswith("word/footer")]
        assert any("SECTIONPAGES" in fxml for fxml in ftr_xmls)
        slash_ftr = next(fxml for fxml in ftr_xmls if " / " in fxml)
        slash_root = ET.fromstring(slash_ftr)
        counter_p = next(
            p for p in slash_root.findall(f".//{_qn('p')}")
            if "/" in "".join(t.text or "" for t in p.findall(f".//{_qn('t')}"))
        )
        counter_ppr = counter_p.find(_qn("pPr"))
        assert counter_ppr is not None and counter_ppr.find(_qn("bidi")) is None
