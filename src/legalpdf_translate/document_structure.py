"""Versioned, local document geometry with deterministic source block identities."""

from __future__ import annotations

import csv
from collections import Counter
from dataclasses import asdict, dataclass, field
import hashlib
import io
import json
import math
import re
import unicodedata
from typing import Any

STRUCTURE_VERSION = 1
ROLES = frozenset({"paragraph", "heading", "header", "footer", "address", "list_item", "table_cell", "signature", "reference"})
_BLOCK_ID = re.compile(r"p[0-9]{4,}_b[0-9]{4,}\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")


def text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class StructureBlock:
    id: str
    text: str
    role: str = "paragraph"
    bbox: tuple[float, float, float, float] | None = None
    table_id: str | None = None
    row: int | None = None
    col: int | None = None
    alignment: str | None = None
    bold: bool = False
    italic: bool = False
    uncertain: bool = False
    document_start: bool = False
    continuation_of: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        if self.bbox is not None:
            value["bbox"] = list(self.bbox)
        return value


@dataclass(slots=True)
class PageStructure:
    page_number: int
    source_sha256: str
    blocks: list[StructureBlock]
    width_pt: float = 595.276
    height_pt: float = 841.89
    version: int = STRUCTURE_VERSION
    uncertain: bool = False
    provenance: str = "text_fallback"
    source_file_sha256: str = ""
    source_text_sha256: str = ""
    translation_sha256: str | None = None
    document_start: bool = False
    continuation_from_previous: bool = False
    continuation_to_next: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(block.text for block in self.blocks)

    @property
    def fingerprint(self) -> str:
        return text_sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["blocks"] = [block.to_dict() for block in self.blocks]
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PageStructure":
        return validate_page_structure(payload)


def validate_page_structure(payload: dict[str, Any] | PageStructure) -> PageStructure:
    if isinstance(payload, PageStructure):
        payload = payload.to_dict()
    if not isinstance(payload, dict) or payload.get("version") != STRUCTURE_VERSION:
        raise ValueError("Unsupported page structure version.")
    page_number = payload.get("page_number")
    if type(page_number) is not int or page_number < 1:
        raise ValueError("Structure page_number must be positive.")
    for name in ("width_pt", "height_pt"):
        value = payload.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 1 <= value <= 20000:
            raise ValueError("Page dimensions must be finite positive points.")
    for name in ("source_sha256", "source_text_sha256", "source_file_sha256", "translation_sha256"):
        value = payload.get(name)
        if value not in (None, "") and (not isinstance(value, str) or not _HASH.fullmatch(value)):
            raise ValueError("Invalid structure hash.")
    if not isinstance(payload.get("source_sha256"), str) or not _HASH.fullmatch(payload["source_sha256"]):
        raise ValueError("Source hash is required.")
    for name in ("uncertain", "document_start", "continuation_from_previous", "continuation_to_next"):
        if type(payload.get(name, False)) is not bool:
            raise ValueError("Structure flags must be boolean.")
    raw_blocks = payload.get("blocks")
    if not isinstance(raw_blocks, list) or len(raw_blocks) > 5000:
        raise ValueError("Structure blocks must be a bounded list.")
    blocks: list[StructureBlock] = []
    seen = set()
    cells = set()
    for raw in raw_blocks:
        if not isinstance(raw, dict):
            raise ValueError("Invalid structure block.")
        identity = raw.get("id")
        if not isinstance(identity, str) or not _BLOCK_ID.fullmatch(identity) or not identity.startswith(f"p{page_number:04d}_b") or identity in seen:
            raise ValueError("Block IDs must be unique and attributed to their source page.")
        seen.add(identity)
        if not isinstance(raw.get("text"), str) or raw.get("role", "paragraph") not in ROLES:
            raise ValueError("Invalid block text or role.")
        if raw.get("alignment") not in {None, "left", "right", "center", "justify"}:
            raise ValueError("Invalid block alignment.")
        bbox = raw.get("bbox")
        if bbox is not None:
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4 or any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n) for n in bbox):
                raise ValueError("Invalid block bounding box.")
            if bbox[2] < bbox[0] or bbox[3] < bbox[1]:
                raise ValueError("Block bounding box is inverted.")
        for name in ("bold", "italic", "uncertain", "document_start"):
            if type(raw.get(name, False)) is not bool:
                raise ValueError("Block flags must be boolean.")
        table_id, row, col = raw.get("table_id"), raw.get("row"), raw.get("col")
        if raw.get("role") == "table_cell":
            if not isinstance(table_id, str) or not table_id or len(table_id) > 100 or type(row) is not int or type(col) is not int or not 0 <= row < 1000 or not 0 <= col < 100:
                raise ValueError("Table cells require a table ID and zero-based row/col.")
            if (table_id, row, col) in cells:
                raise ValueError("Duplicate table cell coordinate.")
            cells.add((table_id, row, col))
        elif table_id is not None or row is not None or col is not None:
            raise ValueError("Only table cells can carry table coordinates.")
        continuation = raw.get("continuation_of")
        if continuation is not None and (not isinstance(continuation, str) or not _BLOCK_ID.fullmatch(continuation) or continuation == identity):
            raise ValueError("Invalid confirmed continuation link.")
        allowed = StructureBlock.__dataclass_fields__
        block_values = {key: value for key, value in raw.items() if key in allowed}
        if bbox is not None:
            block_values["bbox"] = tuple(bbox)
        blocks.append(StructureBlock(**block_values))
    if not isinstance(payload.get("metadata", {}), dict):
        raise ValueError("Structure metadata must be an object.")
    values = {key: value for key, value in payload.items() if key in PageStructure.__dataclass_fields__}
    values["blocks"] = blocks
    return PageStructure(**values)


def plain_text_from_structure(structure: PageStructure | dict[str, Any]) -> str:
    """Canonical legacy TXT representation; block boundaries use one newline."""
    return validate_page_structure(structure).text


def classify_document_boundaries(structure: PageStructure | dict[str, Any]) -> PageStructure:
    """Mark separate source documents only from explicit document-title evidence.

    Court names, process identifiers and ordinary reasoning headings do not
    establish a new document. Ambiguous candidates request review rather than
    inserting a hard page break. This derives no legal content or continuation.
    """
    result = validate_page_structure(structure)
    if result.page_number == 1 or result.document_start:
        result.document_start = True
        result.continuation_from_previous = False
        if result.blocks:
            result.blocks[0].document_start = True
            result.blocks[0].continuation_of = None
        result.metadata["document_boundary_basis"] = "first_source_page" if result.page_number == 1 else "explicit_source_boundary"
        return result

    def title_kind(text: str) -> str | None:
        clean = " ".join(text.split()).strip().rstrip(":").lower()
        clean = "".join(character for character in unicodedata.normalize("NFKD", clean) if not unicodedata.combining(character))
        if not clean or len(clean) > 160:
            return None
        if re.fullmatch(r"(?:mandado de )?notificacao(?: por via postal(?: simples| registada)?| pessoal| judicial| para .+)?", clean):
            return "notification"
        if re.fullmatch(r"acusacao(?: publica| em processo .+| do ministerio publico)?", clean):
            return "prosecution"
        if re.fullmatch(r"(?:despacho|decisao|sentenca)(?: final| judicial| instrutoria| de .+| do ministerio publico)?", clean):
            return "decision"
        return None

    ambiguous = False
    for index, block in enumerate(result.blocks):
        kind = title_kind(block.text)
        if kind is None:
            continue
        if block.role in {"footer", "table_cell", "list_item", "reference", "address", "signature"}:
            continue
        preceding_body = any(
            prior.text.strip() and prior.role not in {"header", "reference", "address"}
            for prior in result.blocks[:index]
        )
        top_geometry = bool(block.bbox and block.bbox[1] <= result.height_pt * .35)
        standalone_heading = block.role == "heading" and "\n" not in block.text.strip()
        # An explicit box well below the start overrides a heading-only guess:
        # this may be an ordinary decision section inside an existing document.
        geometry_conflict = bool(block.bbox and block.bbox[1] > result.height_pt * .45)
        if not preceding_body and not geometry_conflict and (top_geometry or standalone_heading) and not block.uncertain:
            result.document_start = True
            result.continuation_from_previous = False
            block.document_start = True
            block.continuation_of = None
            result.metadata["document_boundary_basis"] = "document_type_title"
            result.metadata["document_type"] = kind
            return result
        ambiguous = True
        block.uncertain = True
    if ambiguous:
        result.uncertain = True
        result.metadata["document_boundary_review_required"] = True
        result.metadata["document_boundary_basis"] = "ambiguous_document_type_title"
    return result


def rebind_page_structure(structure: PageStructure | dict[str, Any], *, page_number: int, source_file_sha256: str = "", page_size: tuple[float, float] | None = None) -> PageStructure:
    """Attach single-image OCR geometry to its actual source page and point size."""
    result = validate_page_structure(structure)
    old_page = result.page_number
    width, height = page_size or (result.width_pt, result.height_pt)
    for index, block in enumerate(result.blocks, 1):
        block.id = f"p{page_number:04d}_b{index:04d}"
        if block.table_id:
            block.table_id = block.table_id.replace(f"p{old_page:04d}_", f"p{page_number:04d}_")
        if block.bbox:
            x0, y0, x1, y1 = block.bbox
            block.bbox = (x0 * width / result.width_pt, y0 * height / result.height_pt, x1 * width / result.width_pt, y1 * height / result.height_pt)
    result.page_number, result.width_pt, result.height_pt = page_number, width, height
    result.source_file_sha256 = source_file_sha256 or result.source_file_sha256
    return validate_page_structure(result)


def _role(text: str) -> str:
    clean = text.strip()
    if re.match(r"^(?:[0-9]+[.)]|[a-zA-Z][)]|[-•])\s", clean):
        return "list_item"
    if len(clean) < 130 and (clean.isupper() or re.fullmatch(r"(?:Despacho|Acusação|Sentença|Notificação|Decisão|Assunto)\s*:?", clean, re.I)):
        return "heading"
    if re.match(r"^(?:Processo|Referência|Ref\.|N[.º°])\b", clean, re.I):
        return "reference"
    if re.match(r"^(?:Rua|Av\.|Avenida|Travessa|Exm[.º°ª]|Exmo|Exma)\b", clean, re.I):
        return "address"
    return "paragraph"


def _finish(blocks: list[StructureBlock], *, page_number: int, page_size: tuple[float, float] | None, source_file_sha256: str, provenance: str, uncertain: bool) -> PageStructure:
    for index, block in enumerate(blocks, 1):
        block.id = f"p{page_number:04d}_b{index:04d}"
    width, height = page_size or (595.276, 841.89)
    if width <= 0 or height <= 0:
        width, height = 595.276, 841.89
    source_hash = text_sha256("\n".join(block.text for block in blocks))
    return validate_page_structure(PageStructure(
        page_number=page_number, source_sha256=source_hash, source_text_sha256=source_hash,
        source_file_sha256=source_file_sha256, width_pt=width, height_pt=height,
        blocks=blocks, uncertain=uncertain, provenance=provenance,
    ))


def structure_from_text(text: str, *, page_number: int, source_file_sha256: str = "", page_size: tuple[float, float] | None = None) -> PageStructure:
    """Conservative text fallback; no guessed tables or confirmed continuations."""
    paragraphs = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    blocks = []
    for paragraph in paragraphs:
        if not paragraph.strip():
            continue
        lines = paragraph.splitlines()
        # Preserve explicit lists/address/heading rows, but join wrapped prose
        # locally so OCR line breaks do not become Word paragraphs.
        current: list[str] = []
        for line in lines:
            role = _role(line)
            if role != "paragraph":
                if current:
                    blocks.append(StructureBlock("", " ".join(current), uncertain=True))
                    current = []
                blocks.append(StructureBlock("", line.strip(), role=role, uncertain=True))
            else:
                current.append(line.strip())
        if current:
            blocks.append(StructureBlock("", " ".join(current), uncertain=True))
    return _finish(blocks, page_number=page_number, page_size=page_size, source_file_sha256=source_file_sha256, provenance="text_fallback", uncertain=True)


def structure_from_ordered(ordered: Any, *, page_number: int, source_file_sha256: str = "") -> PageStructure:
    size = (float(getattr(ordered, "page_width", 0)), float(getattr(ordered, "page_height", 0)))
    raw_blocks = getattr(ordered, "all_blocks", ())
    if not raw_blocks:
        return structure_from_text(ordered.text, page_number=page_number, source_file_sha256=source_file_sha256, page_size=size)
    blocks = []
    for raw in raw_blocks:
        group = getattr(getattr(raw, "group", "body"), "value", getattr(raw, "group", "body"))
        role = group if group in {"header", "footer"} else _role(raw.text)
        if bool(getattr(raw, "bold", False)) and len(raw.text) < 150:
            role = "heading"
        blocks.append(StructureBlock(
            "", raw.text, role=role, bbox=(raw.x0, raw.y0, raw.x1, raw.y1),
            bold=bool(getattr(raw, "bold", False)), italic=bool(getattr(raw, "italic", False)),
            alignment=getattr(raw, "alignment", None),
        ))
    table_warnings = []
    for table in getattr(ordered, "tables", ()):
        bbox = table.get("bbox", [])
        if len(bbox) != 4:
            continue
        inside = [index for index, block in enumerate(blocks) if block.bbox and
                  block.bbox[0] >= bbox[0] - 2 and block.bbox[1] >= bbox[1] - 2 and
                  block.bbox[2] <= bbox[2] + 2 and block.bbox[3] <= bbox[3] + 2]
        cells = table.get("cells", [])
        source_words = Counter(re.findall(r"\w+|[^\w\s]", " ".join(blocks[index].text for index in inside)))
        cell_words = Counter(re.findall(r"\w+|[^\w\s]", " ".join(cell.get("text", "") for cell in cells)))
        if not inside or source_words != cell_words:
            table_warnings.append("table_content_coverage_uncertain")
            continue
        replacement = [StructureBlock("", cell["text"], role="table_cell", bbox=tuple(cell["bbox"]),
                       table_id=table["table_id"], row=cell["row"], col=cell["col"]) for cell in cells]
        insertion = min(inside)
        blocks = [block for index, block in enumerate(blocks) if index not in inside]
        blocks[insertion:insertion] = replacement
    result = _finish(blocks, page_number=page_number, page_size=size, source_file_sha256=source_file_sha256, provenance="digital_pdf", uncertain=bool(getattr(ordered, "fragmented", False)) or bool(table_warnings))
    if table_warnings:
        result.metadata["warnings"] = table_warnings
    return result




def parse_ocr_structure(raw_output: str, *, page_number: int = 1, source_file_sha256: str = "", page_size: tuple[float, float] | None = None) -> PageStructure:
    clean = raw_output.strip()
    if clean.startswith("```") and clean.endswith("```"):
        if "\n" not in clean:
            raise ValueError("OCR did not return valid structure JSON.")
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        payload = json.loads(clean)
    except (ValueError, IndexError) as exc:
        raise ValueError("OCR did not return valid structure JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("blocks"), list) or not payload["blocks"]:
        raise ValueError("OCR structure has no blocks.")
    width, height = page_size or (595.276, 841.89)
    blocks = []
    for item in payload["blocks"]:
        if not isinstance(item, dict) or not isinstance(item.get("text"), str):
            raise ValueError("Invalid OCR block text.")
        values = {key: value for key, value in item.items() if key in StructureBlock.__dataclass_fields__}
        values["id"] = ""
        # OCR cannot confirm a cross-page/document relationship from one image.
        values["document_start"] = False
        values["continuation_of"] = None
        bbox = values.get("bbox")
        if bbox is not None:
            if not isinstance(bbox, list) or len(bbox) != 4 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in bbox):
                raise ValueError("OCR bounding box must contain normalized finite coordinates.")
            values["bbox"] = (bbox[0] * width, bbox[1] * height, bbox[2] * width, bbox[3] * height)
        blocks.append(StructureBlock(**values))
    return _finish(blocks, page_number=page_number, page_size=(width, height), source_file_sha256=source_file_sha256, provenance="api_ocr", uncertain=any(block.uncertain for block in blocks))


def structure_from_tesseract_tsv(tsv: str, *, page_number: int = 1, page_size: tuple[float, float] | None = None, source_file_sha256: str = "") -> PageStructure:
    """Retain Tesseract line geometry/reading order from the same local OCR pass."""
    rows = list(csv.DictReader(io.StringIO(tsv), delimiter="\t"))
    if not rows or "level" not in rows[0]:
        raise ValueError("Missing Tesseract TSV geometry.")
    page_rows = [row for row in rows if row.get("level") == "1"]
    pixel_width = float(page_rows[0]["width"]) if page_rows else 0
    pixel_height = float(page_rows[0]["height"]) if page_rows else 0
    width, height = page_size or (595.276, 841.89)
    if pixel_width <= 0 or pixel_height <= 0:
        raise ValueError("Missing OCR image dimensions.")
    lines: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        if row.get("level") == "5" and row.get("text", "").strip():
            key = (row["block_num"], row["par_num"], row["line_num"])
            lines.setdefault(key, []).append(row)
    blocks = []
    line_groups = []
    previous_paragraph = None
    for key, words in lines.items():
        text = " ".join(word["text"] for word in words)
        left = min(float(word["left"]) for word in words)
        top = min(float(word["top"]) for word in words)
        right = max(float(word["left"]) + float(word["width"]) for word in words)
        bottom = max(float(word["top"]) + float(word["height"]) for word in words)
        uncertain = any(float(word.get("conf", "0")) < 60 for word in words)
        bbox = (left / pixel_width * width, top / pixel_height * height, right / pixel_width * width, bottom / pixel_height * height)
        role = _role(text)
        paragraph = key[:2]
        if blocks and paragraph == previous_paragraph and role == "paragraph" and blocks[-1].role == "paragraph":
            prior = blocks[-1]
            prior.text += " " + text
            prior.bbox = (min(prior.bbox[0], bbox[0]), min(prior.bbox[1], bbox[1]), max(prior.bbox[2], bbox[2]), max(prior.bbox[3], bbox[3]))
            prior.uncertain = prior.uncertain or uncertain
        else:
            blocks.append(StructureBlock("", text, role=role, bbox=bbox, uncertain=uncertain))
        previous_paragraph = paragraph
        line_groups.append({"block": key[0], "paragraph": key[1], "line": key[2], "bbox": list(bbox)})
    result = _finish(blocks, page_number=page_number, page_size=(width, height), source_file_sha256=source_file_sha256, provenance="local_ocr_tsv", uncertain=any(block.uncertain for block in blocks))
    result.metadata["ocr_line_groups"] = line_groups
    return result
