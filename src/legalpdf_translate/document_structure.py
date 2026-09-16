"""Versioned, local document geometry with deterministic source block identities."""

from __future__ import annotations

import csv
from collections import Counter
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import io
import json
import math
import re
import unicodedata
from typing import Any

STRUCTURE_VERSION = 1
SOURCE_STRUCTURE_VERSION = "new_run_source_v3"
MAX_SOURCE_BLOCKS = 5000
MAX_OCR_STRUCTURE_BYTES = 4_000_000
MAX_OCR_WORDS = 50_000
MAX_OCR_WORD_EVIDENCE_BYTES = 4_000_000
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
    if not isinstance(raw_blocks, list) or len(raw_blocks) > MAX_SOURCE_BLOCKS:
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
    """Mark source boundaries from corroborated titles, flag missing-title scans.

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
    elif result.provenance == "local_ocr_tsv":
        # A scan can start a decision/prosecution without a standalone title.
        # No title is not proof of continuation. Recurring court headers and
        # identifiers alone cannot safely distinguish joined source documents.
        # Keep all source text/boxes and request review, never invent a title or
        # use private case/page-specific exceptions to force a document break.
        result.uncertain = True
        result.metadata["document_boundary_review_required"] = True
        result.metadata["document_boundary_basis"] = "unconfirmed_ocr_document_boundary"
        result.metadata["document_boundary_signals"] = sorted({
            "recurring_header_not_sufficient" for block in result.blocks
            if block.role == "header"})
    return result


def apply_reviewed_document_boundary(structure: PageStructure | dict[str, Any], review: dict) -> PageStructure:
    """Apply a completed explicit review bound to the entire pre-decision source.

    This is a caller-owned review record, not a classifier-generated approval.
    It changes only boundary flags; text, boxes and OCR uncertainty stay intact.
    Acceptance independently requires the final source in its approved review.
    """
    from .source_readiness import source_structure_digest
    result = validate_page_structure(structure)
    if (not isinstance(review, dict) or set(review) != {"source_structure_sha256", "decision", "review_kind", "review_evidence_sha256"}
            or review["source_structure_sha256"] != source_structure_digest(result)
            or review["decision"] not in {"start", "continuation"}
            or review["review_kind"] not in {"ai_test_review", "operator_review"}
            or not isinstance(review["review_evidence_sha256"], str)
            or not _HASH.fullmatch(review["review_evidence_sha256"])
            or not result.source_file_sha256 or not result.metadata.get("source_page_identity")
            or result.page_number == 1 and review["decision"] != "start"):
        raise ValueError("document_boundary_review_invalid")
    result.document_start = review["decision"] == "start"
    # Boundary continuation is not proof of a paragraph-level continuation.
    if result.document_start:
        result.continuation_from_previous = False
    for index, block in enumerate(result.blocks):
        block.document_start = result.document_start and index == 0
        if block.document_start:
            block.continuation_of = None
    result.metadata.pop("source_readiness", None)
    result.metadata.update(document_boundary_review_required=False,
        document_boundary_basis="explicit_reviewed_source_boundary", document_boundary_review=deepcopy(review))
    return result


def rebind_page_structure(structure: PageStructure | dict[str, Any], *, page_number: int, source_file_sha256: str = "", page_size: tuple[float, float] | None = None) -> PageStructure:
    """Attach single-image OCR geometry to its actual source page and point size."""
    result = validate_page_structure(structure)
    result.metadata = deepcopy(result.metadata)
    old_page = result.page_number
    width, height = page_size or (result.width_pt, result.height_pt)
    if any(type(value) not in (int, float) or not math.isfinite(value) or not 1 <= value <= 20000
           for value in (width, height)):
        raise ValueError("Page dimensions must be finite positive points.")
    def scaled_box(box):
        if (not isinstance(box, (list, tuple)) or len(box) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in box)):
            raise ValueError("Invalid source line geometry.")
        return [box[0] * width / result.width_pt, box[1] * height / result.height_pt,
                box[2] * width / result.width_pt, box[3] * height / result.height_pt]
    rebound_ids = {}
    for index, block in enumerate(result.blocks, 1):
        rebound_ids[block.id] = f"p{page_number:04d}_b{index:04d}"
        block.id = rebound_ids[block.id]
        if block.table_id:
            block.table_id = block.table_id.replace(f"p{old_page:04d}_", f"p{page_number:04d}_")
        if block.bbox:
            x0, y0, x1, y1 = block.bbox
            block.bbox = (x0 * width / result.width_pt, y0 * height / result.height_pt, x1 * width / result.width_pt, y1 * height / result.height_pt)
    # OCR line boxes use the same derived point frame as block boxes. Raw
    # raster hashes/dimensions stay unchanged; never mutate supplied metadata.
    for key in ("ocr_line_groups", "source_lines"):
        if key in result.metadata:
            if not isinstance(result.metadata[key], list):
                raise ValueError("Invalid source line metadata.")
            for line in result.metadata[key]:
                if not isinstance(line, dict):
                    raise ValueError("Invalid source line metadata.")
                if line.get("bbox") is not None:
                    line["bbox"] = scaled_box(line["bbox"])
    # This packet is raw same-pass raster evidence, not point-space geometry.
    # Only final emitted block ownership changes when the page is rebound.
    if "ocr_word_evidence" in result.metadata:
        packet = result.metadata["ocr_word_evidence"]
        if (not isinstance(packet, dict) or type(packet.get("version")) is not int
                or packet["version"] != 1 or not isinstance(packet.get("words"), list)
                or len(packet["words"]) > MAX_OCR_WORDS):
            raise ValueError("Invalid source word metadata.")
        for word in packet["words"]:
            if not isinstance(word, dict) or not isinstance(word.get("block_id"), str) or word["block_id"] not in rebound_ids:
                raise ValueError("Invalid source word block ownership.")
            word["block_id"] = rebound_ids[word["block_id"]]
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
        if (role in {"paragraph", "address"} and raw.y1 >= size[1] * .85
                and re.match(r"\s*(?:Telef(?:one)?[.: ]|Fax[.: ]|E-?mail[.: ]|Largo\b|Rua\b|Av[. ])", raw.text, re.I)):
            role = "footer"
        if role not in {"header", "footer"} and bool(getattr(raw, "bold", False)) and len(raw.text) < 150:
            role = "heading"
        blocks.append(StructureBlock(
            "", raw.text, role=role, bbox=(raw.x0, raw.y0, raw.x1, raw.y1),
            bold=bool(getattr(raw, "bold", False)), italic=bool(getattr(raw, "italic", False)),
            alignment=getattr(raw, "alignment", None),
        ))
    table_warnings = list(getattr(ordered, "extraction_metadata", {}).get("warnings", []))
    for table in getattr(ordered, "tables", ()):
        bbox = table.get("bbox", [])
        if len(bbox) != 4:
            continue
        inside = [index for index, block in enumerate(blocks) if block.bbox and
                  block.bbox[0] >= bbox[0] - 2 and block.bbox[1] >= bbox[1] - 2 and
                  block.bbox[2] <= bbox[2] + 2 and block.bbox[3] <= bbox[3] + 2]
        cells = table.get("cells", [])
        if not cells or any(not isinstance(cell.get("source_text"), str) or
                            " ".join(cell["text"].split()) != " ".join(cell["source_text"].split()) for cell in cells):
            table_warnings.append("table_cell_association_uncertain")
            continue
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
    result.metadata.update(getattr(ordered, "extraction_metadata", {}))
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


def _positive_tsv_integer(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value) or int(value) < 1:
        raise ValueError("Invalid OCR word index.")
    return int(value)


def _confirmed_list_wrap(previous, current, *, anchor_left: float | None) -> bool:
    """Join only adjacent, confident lines in the same OCR list paragraph."""
    if previous is None or anchor_left is None:
        return False
    prior_key, prior_box, prior_text, prior_confident = previous
    key, box, _text, confident = current
    try:
        current_indices = tuple(_positive_tsv_integer(value) for value in key)
        prior_indices = tuple(_positive_tsv_integer(value) for value in prior_key)
        if key[:2] != prior_key[:2] or current_indices[2] != prior_indices[2] + 1:
            return False
    except ValueError:
        return False
    if not prior_confident or not confident or re.search(r"[.!?;:]\s*$", prior_text):
        return False
    prior_height, height = prior_box[3] - prior_box[1], box[3] - box[1]
    if min(prior_height, height) <= 0 or not .5 <= height / prior_height <= 2:
        return False
    gap = box[1] - prior_box[3]
    # Reject overlapping rows, paragraph gaps, column hops and drifting indents.
    if not 0 <= gap <= .8 * max(prior_height, height):
        return False
    if not anchor_left - .35 * height <= box[0] <= anchor_left + 2 * height:
        return False
    overlap = min(prior_box[2], box[2]) - max(prior_box[0], box[0])
    return overlap >= .25 * min(prior_box[2] - prior_box[0], box[2] - box[0]) > 0


def _attach_ocr_word_evidence(result: PageStructure, word_owners, *, tsv: str, pixel_width: float, pixel_height: float, page_rows) -> None:
    """Keep bounded raw observations; never fabricate boxes for split tokens."""
    result.metadata["ocr_tsv_sha256"] = text_sha256(tsv)
    if len(word_owners) > MAX_OCR_WORDS:
        result.metadata["ocr_word_evidence_unavailable"] = "word_evidence_bound_exceeded"
        return
    try:
        if not pixel_width.is_integer() or not pixel_height.is_integer() or len(page_rows) != 1:
            raise ValueError("Invalid OCR image evidence.")
        source_page = _positive_tsv_integer(page_rows[0]["page_num"])
        words = []
        for row, block_index in word_owners:
            token = row["text"]
            confidence = float(row["conf"])
            if (not token or re.search(r"\s", token) or not 0 <= confidence <= 100
                    or _positive_tsv_integer(row["page_num"]) != source_page):
                raise ValueError("Invalid OCR word evidence.")
            left, top, word_width, word_height = (float(row[name]) for name in ("left", "top", "width", "height"))
            words.append({
                "block_id": result.blocks[block_index].id, "text": token,
                "bbox_px": [left, top, left + word_width, top + word_height],
                "confidence": confidence,
                "group": [_positive_tsv_integer(row[name]) for name in ("block_num", "par_num", "line_num")],
                "word_number": _positive_tsv_integer(row["word_num"]),
            })
        packet = {"version": 1, "tsv_sha256": result.metadata["ocr_tsv_sha256"],
                  "image_size_px": [int(pixel_width), int(pixel_height)], "words": words}
        if len(json.dumps(packet, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")) > MAX_OCR_WORD_EVIDENCE_BYTES:
            result.metadata["ocr_word_evidence_unavailable"] = "word_evidence_bound_exceeded"
            return
        result.metadata["ocr_word_evidence"] = packet
    except (KeyError, TypeError, ValueError):
        result.metadata["ocr_word_evidence_unavailable"] = "invalid_word_evidence"


def structure_from_tesseract_tsv(tsv: str, *, page_number: int = 1, page_size: tuple[float, float] | None = None, source_file_sha256: str = "") -> PageStructure:
    """Retain Tesseract line geometry/reading order from the same local OCR pass."""
    if not isinstance(tsv, str) or len(tsv.encode("utf-8")) > MAX_OCR_STRUCTURE_BYTES:
        raise ValueError("OCR TSV exceeds the local bound.")
    rows = list(csv.DictReader(io.StringIO(tsv), delimiter="\t"))
    if not rows or "level" not in rows[0]:
        raise ValueError("Missing Tesseract TSV geometry.")
    page_rows = [row for row in rows if row.get("level") == "1"]
    pixel_width = float(page_rows[0]["width"]) if page_rows else 0
    pixel_height = float(page_rows[0]["height"]) if page_rows else 0
    width, height = page_size or (595.276, 841.89)
    if not all(math.isfinite(value) and value > 0 for value in (pixel_width, pixel_height)):
        raise ValueError("Missing OCR image dimensions.")
    lines: list[tuple[tuple[str, str, str], list[dict[str, str]]]] = []
    for row in rows:
        if row.get("level") == "5" and row.get("text", "").strip():
            numbers = [float(row[name]) for name in ("left", "top", "width", "height", "conf")]
            if (not all(math.isfinite(number) for number in numbers) or min(numbers[:4]) < 0
                    or numbers[0] + numbers[2] > pixel_width or numbers[1] + numbers[3] > pixel_height):
                raise ValueError("Invalid OCR word geometry/confidence.")
            key = (row["block_num"], row["par_num"], row["line_num"])
            # Keep actual row order even for malformed interleaved line groups.
            # Re-grouping such rows would silently reorder source tokens.
            if not lines or lines[-1][0] != key:
                lines.append((key, []))
            lines[-1][1].append(row)
    blocks = []
    line_groups = []
    word_owners = []
    previous_paragraph = None
    previous_line = None
    list_anchor_left = None
    for key, words in lines:
        text = " ".join(word["text"] for word in words)
        left = min(float(word["left"]) for word in words)
        top = min(float(word["top"]) for word in words)
        right = max(float(word["left"]) + float(word["width"]) for word in words)
        bottom = max(float(word["top"]) + float(word["height"]) for word in words)
        uncertain = any(float(word.get("conf", "0")) < 60 for word in words)
        bbox = (left / pixel_width * width, top / pixel_height * height, right / pixel_width * width, bottom / pixel_height * height)
        role = _role(text)
        if top < pixel_height * .15 and re.search(r"tribunal judicial|minist.rio p.blico|procuradoria", text, re.I):
            role = "header"
        elif bottom > pixel_height * .85 and re.search(r"@|telef|fax|largo|p.g\.", text, re.I):
            role = "footer"
        ordered_words = sorted(words, key=lambda word: float(word["left"]))
        if any(float(b["left"]) - (float(a["left"]) + float(a["width"])) > pixel_width * .12
               for a, b in zip(ordered_words, ordered_words[1:])):
            uncertain = True
        paragraph = key[:2]
        confident_line = not uncertain and all(90 <= float(word["conf"]) <= 100 for word in words)
        confident_line = confident_line and all(float(a["left"]) + float(a["width"]) <= float(b["left"])
                                                for a, b in zip(words, words[1:]))
        current_line = (key, (left, top, right, bottom), text, confident_line)
        same_paragraph = bool(blocks and paragraph == previous_paragraph and role == "paragraph")
        paragraph_wrap = same_paragraph and blocks[-1].role == "paragraph"
        list_wrap = (same_paragraph and blocks[-1].role == "list_item" and not blocks[-1].uncertain
                     and _confirmed_list_wrap(previous_line, current_line, anchor_left=list_anchor_left))
        if paragraph_wrap or list_wrap:
            prior = blocks[-1]
            prior.text += " " + text
            prior.bbox = (min(prior.bbox[0], bbox[0]), min(prior.bbox[1], bbox[1]), max(prior.bbox[2], bbox[2]), max(prior.bbox[3], bbox[3]))
            prior.uncertain = prior.uncertain or uncertain
        else:
            blocks.append(StructureBlock("", text, role=role, bbox=bbox, uncertain=uncertain))
            list_anchor_left = left if role == "list_item" else None
        word_owners.extend((word, len(blocks) - 1) for word in words)
        previous_paragraph = paragraph
        previous_line = current_line
        line_groups.append({"block": key[0], "paragraph": key[1], "line": key[2], "bbox": list(bbox)})
    result = _finish(blocks, page_number=page_number, page_size=(width, height), source_file_sha256=source_file_sha256, provenance="local_ocr_tsv", uncertain=any(block.uncertain for block in blocks))
    result.metadata["ocr_line_groups"] = line_groups
    _attach_ocr_word_evidence(result, word_owners, tsv=tsv, pixel_width=pixel_width,
                              pixel_height=pixel_height, page_rows=page_rows)
    result.metadata.update(extraction_version=SOURCE_STRUCTURE_VERSION,
                           coordinate_space="image_normalized_to_points",
                           paper_size_basis="source_pdf" if page_size else "a4_assumed",
                           reading_order_basis="tesseract_block_paragraph_line", semantic_tables_inferred=False)
    return result
