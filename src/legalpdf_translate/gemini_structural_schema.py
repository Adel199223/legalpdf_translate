"""Strict Pydantic structural IR, Gemini JSON schema, prompts, and validators for gemini_structural_v1."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
import json
import re
from typing import Any, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .arabic_pre_tokenize import extract_locked_tokens
from .docx_writer import sanitize_bidi_controls, unwrap_internal_placeholders
from .output_normalize import normalize_output_text_with_stats
from .translation_fidelity import FIDELITY_GUIDANCE
from .types import TargetLang
from .validators import validate_ar, validate_enfr

STRUCTURAL_PROTOCOL_VERSION = "gemini_structural_v1"
STRUCTURAL_SCHEMA_VERSION = "gemini_structural_v1"
MAX_STRUCTURAL_RESPONSE_BYTES = 3 * 1024 * 1024
_NUMBER_GROUP_RE = re.compile(r"\b\d{2,}(?:[./-]\d+)+\b")

PageArchetype = Literal[
    "citius_notification",
    "despacho",
    "form_record",
    "certificate_letter",
    "general_legal",
]
FontPreference = Literal["times_12", "arial_11_5", "arial_12_5", "calibri_11"]
HeaderStationeryStyle = Literal[
    "none",
    "court_despacho_stationery",
    "police_form_header",
    "simple_stamp",
]
ParagraphItemType = Literal[
    "title",
    "heading_1",
    "heading_2",
    "paragraph",
    "list_bullet",
    "list_number",
    "callout_box",
    "divider_stars",
    "horizontal_rule",
    "barcode_line",
    "signature_block",
]
AlignKind = Literal["left", "center", "right", "justify"]
IndentStyle = Literal["none", "first_line", "left_block", "right_block", "hanging"]
ParagraphBorder = Literal["none", "bottom", "top_bottom", "box"]
ShadingStyle = Literal["none", "light_gray"]
SizeRole = Literal["title", "heading", "body", "small", "footnote"]
RegionKind = Literal["two_col_panel", "metadata_rule_band", "table", "flow_block"]
RegionBorderStyle = Literal[
    "none",
    "top_bottom_only",
    "top_bottom_inside_v",
    "full_grid",
    "outer_box",
    "left_shaded_panel",
]


class StructuralValidationError(ValueError):
    """Content-safe defect code suitable for bounded retry and diagnostics."""

    def __init__(self, code: str, *, retry_kind: str = "formatting", details: Mapping[str, Any] | None = None):
        super().__init__(code)
        self.code = code
        self.retry_kind = retry_kind
        self.details = dict(details or {})


def _strip_none_fields(raw: Any) -> Any:
    """Drop None values on objects before validation so defaulted fields use clean defaults."""
    if isinstance(raw, Mapping):
        return {k: v for k, v in raw.items() if v is not None}
    return raw


class InlineRun(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(description="Translated run text. Keep leading/trailing spaces needed between runs.")
    bold: bool = Field(default=False)
    italic: bool = Field(default=False)
    underline: bool = Field(default=False)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)


class StyledParagraph(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str = Field(
        default="",
        description="Translated paragraph text when uniform styling applies. Omit or leave empty ONLY when using mixed-style runs.",
    )
    bold: bool = Field(default=False)
    italic: bool = Field(default=False)
    underline: bool = Field(default=False)
    runs: list[InlineRun] = Field(
        default_factory=list,
        description="Use ONLY when bold/italic/underline switches within the same paragraph.",
    )
    item_type: ParagraphItemType = Field(default="paragraph")
    align: AlignKind = Field(default="left")
    indent_style: IndentStyle = Field(default="none")
    first_line_indent_cm: float = Field(default=0.0)
    left_indent_cm: float = Field(default=0.0)
    border: ParagraphBorder = Field(default="none")
    shading: ShadingStyle = Field(default="none")
    size_role: SizeRole = Field(default="body")
    keep_with_next: bool = Field(default=False)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)

    @field_validator("first_line_indent_cm")
    @classmethod
    def _clamp_first_line(cls, value: float) -> float:
        return round(max(0.0, min(3.0, float(value))), 2)

    @field_validator("left_indent_cm")
    @classmethod
    def _clamp_left_indent(cls, value: float) -> float:
        return round(max(0.0, min(6.0, float(value))), 2)

    def effective_runs(self) -> list[InlineRun]:
        if self.runs:
            return list(self.runs)
        if self.text:
            return [
                InlineRun(
                    text=self.text,
                    bold=self.bold,
                    italic=self.italic,
                    underline=self.underline,
                )
            ]
        return []

    def plain_text(self) -> str:
        return "".join(run.text for run in self.effective_runs())


class TableCellSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    col_span: int = Field(default=1)
    shading: ShadingStyle = Field(default="none")
    align: AlignKind = Field(default="left")
    paragraphs: list[StyledParagraph] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)

    @field_validator("col_span", mode="before")
    @classmethod
    def _clamp_span(cls, value: Any) -> int:
        return max(1, min(12, int(round(float(value)))))


class TableRowSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cells: list[TableCellSpec] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)


class MetadataBandCellSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    align: Literal["left", "center", "right"] = Field(default="left")
    paragraphs: list[StyledParagraph] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)


class HeaderStationerySpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    present: bool = Field(default=False)
    style: HeaderStationeryStyle = Field(default="none")
    top_left_stamp_lines: list[str] = Field(default_factory=list)
    center_crest_present: bool = Field(default=False)
    center_institution_lines: list[str] = Field(default_factory=list)
    sub_line: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)


class FooterStationerySpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    present: bool = Field(default=False)
    court_contact_lines: list[str] = Field(default_factory=list)
    page_counter_template: str = Field(
        default="",
        description="Localized template using {page} and optional {total}, e.g. 'Page {page} of {total}' or '' if none.",
    )
    legal_note: str = Field(default="")

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)


class MarginsPtSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    left: float = Field(default=54.0)
    right: float = Field(default=54.0)
    top: float = Field(default=54.0)
    bottom: float = Field(default=48.0)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)

    @field_validator("left", "right", "top", "bottom")
    @classmethod
    def _clamp_margin(cls, value: float) -> float:
        return round(max(24.0, min(160.0, float(value))), 1)


class PageRegionSpec(BaseModel):
    model_config = ConfigDict(extra="ignore")

    kind: RegionKind = Field(description="Visual region kind in top-to-bottom page flow.")
    left_width_pct: int = Field(default=44)
    col_widths_pct: list[int] = Field(default_factory=list)
    border_style: RegionBorderStyle = Field(default="none")
    vertical_divider: bool = Field(default=False)
    header_row: bool = Field(default=False)
    left_items: list[StyledParagraph] = Field(default_factory=list)
    right_items: list[StyledParagraph] = Field(default_factory=list)
    metadata_cells: list[MetadataBandCellSpec] = Field(default_factory=list)
    table_rows: list[TableRowSpec] = Field(default_factory=list)
    flow_items: list[StyledParagraph] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)

    @field_validator("left_width_pct", mode="before")
    @classmethod
    def _clamp_left_pct(cls, value: Any) -> int:
        return max(15, min(85, int(round(float(value)))))

    @field_validator("col_widths_pct", mode="before")
    @classmethod
    def _coerce_col_widths(cls, value: Any) -> list[int]:
        if not isinstance(value, list):
            return []
        return [max(1, int(round(float(v)))) for v in value if v is not None]


class PageStructuralDocument(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default=STRUCTURAL_SCHEMA_VERSION)
    page_archetype: PageArchetype = Field(default="general_legal")
    document_starts_here: bool = Field(
        default=True,
        description="True on page 1 OR when a distinct new document/packet section starts on this page.",
    )
    continuation_from_previous: bool = Field(
        default=False,
        description="True when this page continues running body prose or a form table directly from the previous page of the same document.",
    )
    margins_pt: MarginsPtSpec = Field(default_factory=MarginsPtSpec)
    font_preference: FontPreference = Field(default="times_12")
    header_stationery: HeaderStationerySpec = Field(default_factory=HeaderStationerySpec)
    footer_stationery: FooterStationerySpec = Field(default_factory=FooterStationerySpec)
    regions: list[PageRegionSpec] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_none(cls, data: Any) -> Any:
        return _strip_none_fields(data)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: Any) -> str:
        _ = value
        return STRUCTURAL_SCHEMA_VERSION


def _inline_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Expand Pydantic $defs/$ref inline and strip keywords Gemini ignores/dislikes."""
    defs = schema.get("$defs") or {}

    def resolve(node: Any) -> Any:
        if isinstance(node, list):
            return [resolve(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            ref_name = str(node["$ref"]).split("/")[-1]
            target = resolve(deepcopy(defs[ref_name]))
            if "description" in node and isinstance(target, dict) and "description" not in target:
                target["description"] = node["description"]
            return target
        out: dict[str, Any] = {}
        for key, value in node.items():
            if key in {"$defs", "default", "title", "const"}:
                continue
            if key == "anyOf" and isinstance(value, list):
                resolved_opts = [resolve(opt) for opt in value]
                types = [opt.get("type") for opt in resolved_opts if isinstance(opt, dict) and isinstance(opt.get("type"), str)]
                if len(types) == len(resolved_opts) and "null" in types:
                    non_null = [opt for opt in resolved_opts if opt.get("type") != "null"]
                    if len(non_null) == 1:
                        merged = dict(non_null[0])
                        merged["type"] = [merged["type"], "null"]
                        return merged
                out[key] = resolved_opts
            else:
                out[key] = resolve(value)
        if out.get("type") == "object" and "properties" in out:
            out["additionalProperties"] = False
        return out

    cleaned = resolve(deepcopy(schema))
    cleaned.pop("$defs", None)
    return cleaned


def gemini_structural_response_format() -> dict[str, Any]:
    """Return Gemini/Interactions-compatible strict inline JSON Schema response_format."""
    return {
        "type": "json_schema",
        "name": STRUCTURAL_PROTOCOL_VERSION,
        "strict": True,
        "schema": _inline_json_schema(PageStructuralDocument.model_json_schema()),
    }


_LANG_STRUCTURAL_GUIDANCE = {
    "EN": (
        "Translate ALL Portuguese legal, institutional, court, ministerial, address-label, and month terms into formal legal English "
        "(British spelling). Do NOT leave Portuguese court/institution names or legal nouns untranslated (e.g. 'Tribunal Judicial' -> "
        "'Judicial Court', 'Juízo Local Criminal' -> 'Local Criminal Court', 'Ministério Público' -> 'Public Prosecutor\\'s Office', "
        "'Notificação por Via Postal Simples' -> 'Notification by Ordinary Post', 'Despacho' -> 'Order' or 'Prosecutor\\'s Order'). "
        "Preserve accented personal names, postal street addresses, case/process codes, article numbers, dates (month names translated to English), "
        "amounts, and identifiers verbatim."
    ),
    "FR": (
        "Translate ALL Portuguese legal, institutional, court, ministerial, and month terms into formal legal French while keeping Portuguese jurisdictional identity intact. "
        "Do NOT leave Portuguese court names, agency titles, or month names untranslated. Preserve personal names, addresses, case numbers, dates, and identifiers verbatim."
    ),
    "AR": (
        "Translate into Modern Standard Arabic while following strict literal wrapping rules: "
        "keep every supplied [[...]] locked token unchanged inside its InlineRun/header/footer string with exact spelling and occurrence counts. "
        "Preserve all digits (0-9), personal names, postal street names, emails, URLs, barcodes, and case/reference numbers inside [[...]] wrappers without alteration. "
        "Do NOT leave unwrapped Latin letters or ASCII digits outside [[...]]. Translate all Portuguese legal terms, court names, headings, months, and table labels into formal legal Arabic. "
        "Use 'arial_12_5' or 'arial_11_5' for font_preference and align='right' or align='justify' on Arabic prose."
    ),
}


def build_structural_system_instructions(lang: TargetLang | str) -> str:
    code = lang.value if isinstance(lang, TargetLang) else str(lang).upper()
    lang_rules = _LANG_STRUCTURAL_GUIDANCE.get(code, _LANG_STRUCTURAL_GUIDANCE["EN"])
    return (
        "You are an expert legal document translator and Word document layout architect.\n"
        "For the assigned source page (provided as an image and/or extracted text + geometry hints), produce ONE faithful, complete translation "
        "captured inside the exact JSON schema so the resulting Word document closely mirrors the original document's visual architecture.\n\n"
        "ARCHITECTURAL MAPPING RULES:\n"
        "1. Translate EVERY readable element visible on the source page once (headers, stamps, metadata bars, left sidebars, main text, boxes, tables, footers, signatures, barcodes). Never drop, summarize, or invent text.\n"
        "2. Recognize Portuguese legal archetypes and choose matching Word layout structures:\n"
        "   - 'citius_notification': Two-column notification/letter headers & Legal Aid sidebars -> put 2-column bands in regions of kind='two_col_panel' (left_items + right_items, accurate left_width_pct, border_style='left_shaded_panel' if shaded panel, vertical_divider=true if separated). Full-width horizontal divider bars go as horizontal_rule or border='top_bottom'. Put page-bottom court notes and page counter in footer_stationery with page_counter_template='Page {page}' (or translated equivalent using literal {page}/{total}, NEVER wrap {page} or counter digits in [[...]]).\n"
        "   - 'despacho': Repeating top stationery (agency title, crest, top-left electronic signature stamp) goes in header_stationery (NOT repeated inside flow body!). Repeating bottom address/page counter goes in footer_stationery with page_counter_template='Page {page} of {total}' (or translated equivalent with {page}/{total}). The full-width 1x3 (or 1x2) case/proceeding/reference band directly under header goes in kind='metadata_rule_band' with border_style='top_bottom_only' or 'top_bottom_inside_v'. Main narrative prose uses item_type='paragraph', align='justify', indent_style='first_line', first_line_indent_cm=1.25. Numbered/bulleted items use list_number/list_bullet with indent_style='hanging'. Section dividers like '* * *' use item_type='divider_stars'. Use font_preference='times_12' for EN/FR.\n"
        "   - 'form_record': Structured police/agency records -> bordered tables use kind='table' with border_style='full_grid' (or 'none' when source rows are borderless), accurate col_widths_pct, row cells with bold labels + values. Section headers with underlines/rules use heading_1/heading_2 with border='bottom'. Top agency crest/masthead belongs in header_stationery ONLY on page 1 of the form (center_crest_present=false on continuation pages), and continuation running top headers (e.g. 'NPP/NUIPC... | Polícia...') must go in header_stationery (NOT inside regions!). Put page footer notes and counter using literal {page}/{total} in footer_stationery.\n"
        "3. Multi-document PDFs: set document_starts_here=true ONLY on page 1 OR when a brand-new legal document begins on this page (e.g. a Dispatch starts after a 2-page Citius Notification). Set continuation_from_previous=true when continuing running prose/form from the previous page, and do NOT emit duplicate body metadata_rule_band headers or duplicate top running page headers in regions.\n"
        "4. KEEP JSON COMPACT: omit optional defaulted fields and empty arrays! Put uniform paragraph text in `text` (plus `bold`/`italic`/`underline` when uniform), and use `runs` ONLY when bold/italic/underline changes mid-paragraph.\n\n"
        + lang_rules
        + "\n\n"
        + FIDELITY_GUIDANCE
    )


def build_structural_page_prompt(
    *,
    lang: TargetLang,
    page_number: int,
    total_pages: int,
    source_text: str,
    geometry_hints: Mapping[str, Any],
    context_text: str | None = None,
    glossary_prompt: str | None = None,
    prompt_addendum: str | None = None,
) -> str:
    payload: dict[str, Any] = {
        "target_lang": lang.value,
        "page_number": page_number,
        "total_pages": total_pages,
        "source_geometry_hints": dict(geometry_hints),
    }
    if context_text and context_text.strip():
        payload["user_context_not_to_copy_verbatim_into_source"] = context_text.strip()
    lines = [
        f"TARGET LANGUAGE: {lang.value} | PAGE {page_number} OF {total_pages}",
        "Return ONLY JSON conforming strictly to the PageStructuralDocument schema.",
        "If an attached source page image is present, use it as primary visual authority for columns, tables, rules, borders, shaded sidebars, bold/italic styling, indents, and any text missing from extracted OCR/text.",
        "<<<SOURCE GEOMETRY HINTS JSON>>>",
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        "<<<END GEOMETRY HINTS>>>",
        "<<<BEGIN EXTRACTED SOURCE TEXT AID>>>",
        source_text,
        "<<<END EXTRACTED SOURCE TEXT AID>>>",
    ]
    if glossary_prompt and glossary_prompt.strip():
        lines.append(glossary_prompt.strip())
    if prompt_addendum and prompt_addendum.strip():
        lines.append(prompt_addendum.strip())
    return "\n".join(lines)


def build_structural_retry_prompt(
    *,
    original_prompt: str,
    defect_code: str,
    defect_reason: str,
    lang: TargetLang,
    expected_ar_tokens: Sequence[str] = (),
) -> str:
    hints = [
        original_prompt,
        "",
        f"<<<VALIDATION REPAIR REQUIRED: {defect_code}>>>",
        f"Previous response failed validation: {defect_reason}",
        "Re-emit the complete PageStructuralDocument JSON for this page, fixing the defect above without dropping any text.",
    ]
    if defect_code in {"pt_language_leak"} and lang != TargetLang.AR:
        hints.append(
            "CRITICAL: Translate ALL remaining Portuguese legal, court, institutional, and month terms into the target language."
        )
    elif defect_code in {"ar_token_violation", "ar_latin_or_digits_outside_tokens"} and lang == TargetLang.AR:
        tokens = [t for t in expected_ar_tokens if t]
        hints.append(
            "CRITICAL ARABIC RULE: Every Latin word, acronym, name, address, barcode, and number must remain inside [[...]] tokens, "
            "all required tokens must appear intact, and ZERO Latin letters or digits may appear outside [[...]]."
        )
        if tokens:
            hints.append("Required tokens to preserve: " + " | ".join(f"[[{t}]]" for t in tokens[:60]))
    elif defect_code in {"incomplete_source_coverage", "incomplete_source_identifiers"}:
        hints.append(
            "CRITICAL COMPLETENESS RULE: Include ALL body paragraphs, numbered items, table rows, addresses, and numeric/case identifiers from the page."
        )
    return "\n".join(hints)


def _strip_code_fence(raw: str) -> str:
    text = str(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return text


def _apply_leaf_text_transform(doc: PageStructuralDocument, transform) -> PageStructuralDocument:
    """Apply a deterministic normalization transform to every visible text string in the IR."""
    def clean_list(items: list[str]) -> list[str]:
        return [res for item in items if (res := transform(item).strip())]

    doc.header_stationery.top_left_stamp_lines = clean_list(doc.header_stationery.top_left_stamp_lines)
    doc.header_stationery.center_institution_lines = clean_list(doc.header_stationery.center_institution_lines)
    doc.header_stationery.sub_line = transform(doc.header_stationery.sub_line).strip()

    doc.footer_stationery.court_contact_lines = clean_list(doc.footer_stationery.court_contact_lines)
    doc.footer_stationery.legal_note = transform(doc.footer_stationery.legal_note).strip()
    # Keep {page}/{total} placeholders intact in template
    tpl = sanitize_bidi_controls(doc.footer_stationery.page_counter_template).strip()
    doc.footer_stationery.page_counter_template = tpl

    def norm_paras(paras: list[StyledParagraph]) -> list[StyledParagraph]:
        kept: list[StyledParagraph] = []
        for para in paras:
            if para.item_type in {"horizontal_rule", "divider_stars"}:
                kept.append(para)
                continue
            if para.runs:
                new_runs: list[InlineRun] = []
                for run in para.runs:
                    cleaned = transform(run.text, preserve_edge_ws=True)
                    if cleaned:
                        run.text = cleaned
                        new_runs.append(run)
                para.runs = new_runs
                if new_runs:
                    para.text = ""
                    kept.append(para)
                elif para.text:
                    cleaned_text = transform(para.text, preserve_edge_ws=True)
                    if cleaned_text:
                        para.text = cleaned_text
                        kept.append(para)
            elif para.text:
                cleaned_text = transform(para.text, preserve_edge_ws=True)
                if cleaned_text:
                    para.text = cleaned_text
                    kept.append(para)
        return kept

    cleaned_regions: list[PageRegionSpec] = []
    for region in doc.regions:
        if region.kind == "two_col_panel":
            region.left_items = norm_paras(region.left_items)
            region.right_items = norm_paras(region.right_items)
            if region.left_items or region.right_items:
                cleaned_regions.append(region)
        elif region.kind == "metadata_rule_band":
            for cell in region.metadata_cells:
                cell.paragraphs = norm_paras(cell.paragraphs)
            region.metadata_cells = [c for c in region.metadata_cells if c.paragraphs]
            if region.metadata_cells:
                cleaned_regions.append(region)
        elif region.kind == "table":
            new_rows: list[TableRowSpec] = []
            for row in region.table_rows:
                for cell in row.cells:
                    cell.paragraphs = norm_paras(cell.paragraphs)
                if row.cells and any(c.paragraphs for c in row.cells):
                    new_rows.append(row)
            region.table_rows = new_rows
            if region.table_rows:
                cleaned_regions.append(region)
        else:
            region.flow_items = norm_paras(region.flow_items)
            if region.flow_items:
                cleaned_regions.append(region)
    doc.regions = cleaned_regions
    return doc


def flatten_structural_text(doc: PageStructuralDocument, *, unwrap_tokens: bool = False) -> str:
    """Extract readable non-empty lines from the structural page for validation & plain TXT export."""
    lines: list[str] = []

    def add_line(text: str) -> None:
        val = unwrap_internal_placeholders(text) if unwrap_tokens else text
        val = " ".join(val.splitlines()).strip()
        if val:
            lines.append(val)

    def add_paras(paras: Sequence[StyledParagraph]) -> None:
        for para in paras:
            if para.item_type == "divider_stars":
                lines.append("* * *")
            elif para.item_type == "horizontal_rule":
                continue
            else:
                add_line(para.plain_text())

    if doc.header_stationery.present:
        for line in doc.header_stationery.top_left_stamp_lines:
            add_line(line)
        for line in doc.header_stationery.center_institution_lines:
            add_line(line)
        if doc.header_stationery.sub_line:
            add_line(doc.header_stationery.sub_line)

    for region in doc.regions:
        if region.kind == "two_col_panel":
            add_paras(region.left_items)
            add_paras(region.right_items)
        elif region.kind == "metadata_rule_band":
            parts = []
            for cell in region.metadata_cells:
                cell_text = " | ".join(p.plain_text().strip() for p in cell.paragraphs if p.plain_text().strip())
                if cell_text:
                    parts.append(cell_text)
            if parts:
                add_line(" | ".join(parts))
        elif region.kind == "table":
            for row in region.table_rows:
                row_parts = []
                for cell in row.cells:
                    cell_text = " ".join(p.plain_text().strip() for p in cell.paragraphs if p.plain_text().strip())
                    row_parts.append(cell_text)
                if any(row_parts):
                    add_line(" | ".join(p for p in row_parts if p))
        else:
            add_paras(region.flow_items)

    if doc.footer_stationery.present:
        for line in doc.footer_stationery.court_contact_lines:
            add_line(line)
        if doc.footer_stationery.legal_note:
            add_line(doc.footer_stationery.legal_note)

    return "\n".join(lines)


def parse_and_validate_structural_page(
    raw_output: str,
    *,
    lang: TargetLang,
    source_text: str = "",
    expected_ar_tokens: Sequence[str] = (),
) -> tuple[PageStructuralDocument, str, dict[str, Any]]:
    """Parse Gemini structural JSON, normalize leaf strings, and validate fidelity & token locks."""
    if not isinstance(raw_output, str) or len(raw_output.encode("utf-8", errors="replace")) > MAX_STRUCTURAL_RESPONSE_BYTES:
        raise StructuralValidationError("invalid_structural_size", retry_kind="formatting")

    cleaned_json = _strip_code_fence(raw_output)
    try:
        raw_obj = json.loads(cleaned_json)
    except (ValueError, TypeError, RecursionError) as exc:
        raise StructuralValidationError("invalid_structural_json", retry_kind="formatting") from exc

    try:
        doc = PageStructuralDocument.model_validate(raw_obj)
    except ValidationError as exc:
        summary = "; ".join(
            f"{'.'.join(str(x) for x in err.get('loc', ()))}:{err.get('type', 'error')}"
            for err in exc.errors()[:5]
        )
        raise StructuralValidationError(
            "invalid_structural_schema",
            retry_kind="formatting",
            details={"error_count": len(exc.errors()), "error_summary": summary},
        ) from exc

    norm_stats: dict[str, int] = {"autofix_count": 0}
    expected_tokens_list = [tok for tok in expected_ar_tokens if tok]

    def transform_text(value: str, *, preserve_edge_ws: bool = False) -> str:
        if not value:
            return ""
        if not value.strip():
            return " " if preserve_edge_ws else ""
        lead_ws = value[: len(value) - len(value.lstrip(" "))] if preserve_edge_ws else ""
        trail_ws = value[len(value.rstrip(" ")) :] if preserve_edge_ws else ""
        core = value.strip(" ") if preserve_edge_ws else value
        norm_text, count = normalize_output_text_with_stats(
            core,
            lang=lang,
            strip_trailing_spaces=not preserve_edge_ws,
            expected_ar_tokens=expected_tokens_list if lang == TargetLang.AR else None,
        )
        norm_stats["autofix_count"] += int(count or 0)
        return f"{lead_ws}{norm_text}{trail_ws}"

    doc = _apply_leaf_text_transform(doc, transform_text)
    flat_text = flatten_structural_text(doc, unwrap_tokens=False)
    unwrapped_flat = flatten_structural_text(doc, unwrap_tokens=True)

    if not unwrapped_flat.strip():
        raise StructuralValidationError("empty_structural_output", retry_kind="completeness")

    # Deterministic content completeness guard against silent drops when extracted source is substantial.
    src_compact = "".join(source_text.split())
    out_compact = "".join(unwrapped_flat.split())
    if len(src_compact) >= 120 and len(out_compact) < max(30, int(0.18 * len(src_compact))):
        raise StructuralValidationError(
            "incomplete_source_coverage",
            retry_kind="completeness",
            details={"source_chars": len(src_compact), "output_chars": len(out_compact)},
        )

    src_ids = Counter(_NUMBER_GROUP_RE.findall(source_text))
    if sum(src_ids.values()) >= 2:
        out_digits_source = flatten_structural_text(doc, unwrap_tokens=True)
        matched = sum(1 for key in src_ids if key in out_digits_source)
        if matched * 2 < len(src_ids):
            raise StructuralValidationError(
                "incomplete_source_identifiers",
                retry_kind="completeness",
                details={"source_id_count": len(src_ids), "matched_id_count": matched},
            )

    if lang in (TargetLang.EN, TargetLang.FR):
        res = validate_enfr(flat_text, lang=lang)
        if not res.ok:
            code = "pt_language_leak" if "Portuguese" in str(res.reason or "") else "invalid_enfr_output"
            raise StructuralValidationError(code, retry_kind="language", details=res.details or {})
    elif lang == TargetLang.AR:
        res = validate_ar(flat_text, expected_tokens=None)
        if not res.ok:
            code = (
                "ar_latin_or_digits_outside_tokens"
                if res.kind == "latin_or_digits_outside_wrapped_tokens"
                else "ar_token_violation"
            )
            raise StructuralValidationError(
                code,
                retry_kind="ar_tokens",
                details={"reason": res.reason or "", "kind": res.kind or "", **(res.details or {})},
            )
        # Verify high-signal alphanumeric/numeric identifiers from source remain present in translated output,
        # without falsely failing when footer page digits move to {page} or multi-word labels split cleanly.
        unwrapped_compact = " ".join(unwrapped_flat.split())
        missing_high_signal = [
            tok
            for tok in expected_tokens_list
            if len(tok) >= 4
            and (any(ch.isdigit() for ch in tok) or "@" in tok or "/" in tok)
            and " " not in tok
            and tok not in unwrapped_compact
        ]
        if missing_high_signal:
            raise StructuralValidationError(
                "ar_token_violation",
                retry_kind="ar_tokens",
                details={
                    "reason": "missing_high_signal_ar_identifiers",
                    "missing_count": len(missing_high_signal),
                },
            )
    else:
        res = validate_enfr(flat_text, lang=None)
        if not res.ok:
            raise StructuralValidationError("invalid_output", retry_kind="formatting", details=res.details or {})

    return doc, flat_text, {
        "autofix_applied_count": norm_stats["autofix_count"],
        "region_count": len(doc.regions),
        "archetype": doc.page_archetype,
        "output_chars": len(unwrapped_flat),
    }
