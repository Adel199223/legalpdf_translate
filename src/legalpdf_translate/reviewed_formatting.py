"""Detached, source-image-reviewed whole-line formatting partitions.

This first profile is deliberately narrower than a general grapheme segmenter:
cuts may occur only after a complete LF/CRLF-delimited line (with trailing blank
separators owned by the preceding fragment), outside placeholder/bidi scopes.
No original PageStructure, uncertainty flag, text, commit or preference changes.

The caller must first validate the original per-page commits and their historic
source/language/preferences provenance. Commit hashes here bind that evidence;
they do not replace its verification. Image hashes bind actual supplied bytes,
but role/box observations remain AI-test-review assertions, not OCR geometry or
legal/rendered-layout certification. No files, providers or renderers are used.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import json
import math
import re
import unicodedata
from typing import Any, Mapping, Sequence

from PIL import Image

from .document_structure import PageStructure, validate_page_structure
from .formatting_support import _contact_furniture
from .section_furniture import _safe_header

VERSION = "reviewed_formatting_v1"
POLICY = "source_page_matched_reviewed_v1"
REGION_VERSION = "reviewed_formatting_v2"
REGION_POLICY = "source_page_matched_reviewed_regions_v2"
FOLIO_POLICY = "reviewed_document_local_folios_v1"
BOUNDARY_POLICY = "whole_lines_trailing_separators_v1"
CELL_BOUNDARY_POLICY = "whole_lines_and_reviewed_pipe_cells_v1"
SOURCE_GAP_POLICY = "reviewed_source_region_gaps_v1"
MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_IMAGE_BYTES = 40 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_PAGES = 1000
MAX_FRAGMENTS = 5000
_HASH = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_RENDERING_ID = re.compile(r"p([0-9]{4,})_f([0-9]{4,})\Z", re.ASCII)
_FOLIO = re.compile(r"([0-9]+)\s*/\s*([0-9]+)\Z", re.ASCII)
_BIDI_OPEN = {"\u202a": "embedding", "\u202b": "embedding", "\u202d": "embedding",
              "\u202e": "embedding", "\u2066": "isolate", "\u2067": "isolate", "\u2068": "isolate"}
_BIDI_MARKS = frozenset("\u061c\u200e\u200f\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


class ReviewedFormattingError(ValueError):
    """Only content-free validation categories leave this module."""


@dataclass(frozen=True, slots=True)
class FormattingPageInput:
    source_structure: Mapping[str, Any] | PageStructure
    target_structure: Mapping[str, Any] | PageStructure
    commit_file_sha256: str
    bundle_sha256: str
    source_image_bytes: bytes


@dataclass(frozen=True, slots=True)
class ReviewedFormattingFragment:
    rendering_id: str
    parent_block_id: str
    source_range: tuple[int, int]
    target_range: tuple[int, int]
    source_text: str
    target_text: str
    source_text_sha256: str
    target_text_sha256: str
    role: str
    alignment: str
    bold: bool
    italic: bool
    bbox_px: tuple[float, float, float, float]
    review_note: str
    parent_uncertain: bool


@dataclass(frozen=True, slots=True)
class ReviewedFormattingPage:
    page_number: int
    section_index: int
    commit_file_sha256: str
    bundle_sha256: str
    source_structure_sha256: str
    target_structure_sha256: str
    source_structure_json: bytes
    target_structure_json: bytes
    source_image_sha256: str
    image_size_px: tuple[int, int]
    page_size_pt: tuple[float, float]
    paper_size_basis: str
    fragments: tuple[ReviewedFormattingFragment, ...]
    source_uncertain: bool
    geometry_status: str = "not_verified"
    original_parent_separator: str = "\n"
    region_layout_json: bytes | None = None
    folio_fragment_id: str | None = None


@dataclass(frozen=True, slots=True)
class ReviewedFormattingProjection:
    manifest_sha256: str
    source_file_sha256: str
    target_lang: str
    preferences_sha256: str
    pages: tuple[ReviewedFormattingPage, ...]
    version: str = VERSION
    policy: str = POLICY
    boundary_policy: str = BOUNDARY_POLICY
    offset_unit: str = "unicode_codepoint"
    reviewer_kind: str = "ai_test_review"
    geometry_basis: str = "reviewed_image_regions_not_ocr"
    layout_review_required: bool = True
    rendered_layout_acceptance: str = "not_evaluated"
    rendered_page_count: None = None
    document_groups_json: bytes | None = None
    folio_policy: str | None = None
    spacing_policy: str | None = None


def _fail(code: str) -> None:
    raise ReviewedFormattingError(code)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash(value: Any) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        _fail("invalid_sha256")
    return value


def _keys(value: Any, expected: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) != expected:
        _fail("invalid_schema")
    return value


def _canonical(value: Any) -> bytes:
    try:
        result = json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _fail("invalid_json_value")
    if len(result) > MAX_MANIFEST_BYTES:
        _fail("json_value_too_large")
    return result


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate_json_keys")
        result[key] = value
    return result


def _parse(raw: bytes, expected_hash: str) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_MANIFEST_BYTES:
        _fail("invalid_manifest_bytes")
    if _sha(raw) != _hash(expected_hash):
        _fail("manifest_hash_mismatch")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                          parse_constant=lambda _: _fail("invalid_json_constant"))
    except (ValueError, UnicodeError, RecursionError):
        _fail("invalid_manifest_json")


def _text_hash(text: str) -> str:
    if not isinstance(text, str):
        _fail("invalid_text")
    try:
        encoded = text.encode("utf-8")
    except UnicodeError:
        _fail("invalid_unicode")
    if len(encoded) > MAX_TEXT_BYTES:
        _fail("text_too_large")
    return _sha(encoded)


def _line_boundaries(text: str) -> frozenset[int]:
    """Conservative cuts, not a general UAX #29 implementation."""
    _text_hash(text)
    safe, stack, placeholder = {0}, [], False
    index = 0
    while index < len(text):
        if text.startswith("[[", index):
            if placeholder:
                _fail("nested_placeholder")
            placeholder = True
            index += 2
            continue
        if text.startswith("]]", index):
            if not placeholder:
                _fail("unmatched_placeholder")
            placeholder = False
            index += 2
            continue
        char = text[index]
        if char in _BIDI_OPEN:
            stack.append(_BIDI_OPEN[char])
        elif char == "\u202c":
            if not stack or stack[-1] != "embedding":
                _fail("unbalanced_bidi_scope")
            stack.pop()
        elif char == "\u2069":
            # Deliberately reject implicit closing of embedded scopes.
            if not stack or stack[-1] != "isolate":
                _fail("unbalanced_bidi_scope")
            stack.pop()
        if char == "\r" and (index + 1 == len(text) or text[index + 1] != "\n"):
            _fail("unsupported_line_separator")
        cut = index + 1
        if char == "\n" and not stack and not placeholder:
            if cut == len(text):
                safe.add(cut)
            else:
                next_end = text.find("\n", cut)
                next_line = text[cut:next_end if next_end >= 0 else len(text)]
                next_char = text[cut]
                # Trailing blank lines remain with the previous fragment.
                if (next_line.strip() and unicodedata.category(next_char) not in {"Mn", "Mc", "Me"}
                        and next_char not in {"\u200c", "\u200d"}
                        and not 0x1F3FB <= ord(next_char) <= 0x1F3FF):
                    safe.add(cut)
        index += 1
    if stack or placeholder:
        _fail("unclosed_text_scope")
    safe.add(len(text))
    return frozenset(safe)


def _range(value: Any, *, text: str, start: int, boundaries: frozenset[int]) -> tuple[int, int]:
    if (not isinstance(value, list) or len(value) != 2 or any(type(n) is not int for n in value)
            or value[0] != start or not 0 <= value[0] < value[1] <= len(text)
            or value[0] not in boundaries or value[1] not in boundaries):
        _fail("invalid_line_partition")
    return value[0], value[1]


def _number(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        _fail("invalid_coordinate")
    return float(value)


def _box(value: Any, width: int, height: int) -> tuple[float, float, float, float]:
    if not isinstance(value, list) or len(value) != 4:
        _fail("invalid_region")
    x0, y0, x1, y1 = map(_number, value)
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        _fail("region_outside_image")
    return x0, y0, x1, y1


def _visible(text: str) -> str:
    # Only for conservative semantic checks. Returned fragment text is raw.
    text = re.sub(r"\[\[([^\[\]]*)\]\]", r"\1", text)
    return "".join(char for char in text if char not in _BIDI_MARKS).strip()


def _role(role: str, source: str, target: str, box: tuple, *, page: int, total: int, height: int,
          document_local_folios: bool = False) -> None:
    if not isinstance(role, str) or role not in {"header", "body", "signature", "footer", "folio"}:
        _fail("unsupported_fragment_role")
    if not source.strip() or not target.strip():
        _fail("empty_fragment")
    if role == "header":
        if box[3] > height * .25 or not _safe_header({"text": source.strip()}):
            _fail("unsupported_header_assertion")
    elif role == "footer":
        # V2 reviews the complete explicit footer container after validating
        # ownership below. An address and its contact line may be separate
        # editable fragments; each still needs bottom-band geometry here.
        if (box[1] < height * .80
                or not document_local_folios and not _contact_furniture([{"text": source.strip()}])):
            _fail("unsupported_footer_assertion")
    elif role == "folio":
        if document_local_folios:
            # Full source/target scanning and exact document-local grammar are
            # checked across the complete case below, not inferred here.
            if box[1] < height * .80:
                _fail("unsupported_or_changed_folio")
            return
        match = _FOLIO.fullmatch(source.strip())
        if (box[1] < height * .80 or not match or len(match[1]) > 6 or len(match[2]) > 6
                or (int(match[1]), int(match[2])) != (page, total)
                or re.sub(r"\s", "", _visible(source)) != re.sub(r"\s", "", _visible(target))):
            _fail("unsupported_or_changed_folio")


def _payload(value: Mapping | PageStructure) -> tuple[dict, bytes]:
    raw = value.to_dict() if isinstance(value, PageStructure) else value
    if not isinstance(raw, Mapping):
        _fail("invalid_page_structure")
    encoded = _canonical(dict(raw))
    payload = json.loads(encoded)
    try:
        validate_page_structure(payload)
    except (ValueError, TypeError, KeyError, OverflowError):
        _fail("invalid_page_structure")
    return payload, encoded


def _bound_pair(input_page: FormattingPageInput, *, number: int, source_hash: str):
    source, source_json = _payload(input_page.source_structure)
    target, target_json = _payload(input_page.target_structure)
    immutable = set(source) | set(target)
    immutable -= {"blocks", "metadata", "translation_sha256"}
    if (source.get("page_number") != number or source.get("source_file_sha256") != source_hash
            or any(source.get(key) != target.get(key) for key in immutable)
            or source.get("translation_sha256") is not None
            or source.get("provenance") != "reviewed_image_source_v1"
            or source.get("uncertain") is not True
            or not source["blocks"] or len(source["blocks"]) != len(target["blocks"])):
        _fail("source_target_identity_mismatch")
    if any(target.get("metadata", {}).get(key) != value for key, value in source.get("metadata", {}).items()):
        _fail("source_metadata_changed")
    for left, right in zip(source["blocks"], target["blocks"]):
        if (left.get("role") != "paragraph" or left.get("table_id") is not None
                or left.get("continuation_of") is not None
                or {k: v for k, v in left.items() if k != "text"} != {k: v for k, v in right.items() if k != "text"}):
            _fail("unsupported_or_changed_parent")
    source_text = "\n".join(block["text"] for block in source["blocks"])
    target_text = "\n".join(block["text"] for block in target["blocks"])
    if (source.get("source_sha256") != _text_hash(source_text)
            or source.get("source_text_sha256") != _text_hash(source_text)
            or target.get("translation_sha256") != _text_hash(target_text)):
        _fail("parent_text_hash_mismatch")
    return source, target, source_json, target_json


def _image(input_page: FormattingPageInput, row: dict, source: dict) -> tuple[int, int]:
    raw = input_page.source_image_bytes
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_IMAGE_BYTES:
        _fail("invalid_image_bytes")
    image_hash = _sha(raw)
    identity = source.get("metadata", {}).get("source_page_identity", {})
    review = source.get("metadata", {}).get("reviewed_source", {})
    if (not isinstance(identity, dict) or not isinstance(review, dict)
            or row["source_image_sha256"] != image_hash or identity.get("image_sha256") != image_hash
            or identity.get("source_file_sha256") != source["source_file_sha256"]
            or identity.get("source_type") != "browser_pdf_image"
            or identity.get("paper_size_basis") != "a4_assumed"
            or review.get("review_image_sha256") != image_hash or review.get("geometry_status") != "not_verified"):
        _fail("source_image_identity_mismatch")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            size = image.size
            if image.format != "PNG" or getattr(image, "n_frames", 1) != 1 or size[0] * size[1] > MAX_IMAGE_PIXELS:
                _fail("unsupported_image")
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
    except ReviewedFormattingError:
        raise
    except Exception:
        _fail("invalid_source_image")
    if (not isinstance(row["image_size_px"], list) or len(row["image_size_px"]) != 2
            or any(type(n) is not int for n in row["image_size_px"]) or row["image_size_px"] != list(size)):
        _fail("image_size_mismatch")
    frame = _keys(row["frame"], {"origin", "units", "page_size_pt", "paper_size_basis"})
    if (frame["origin"] != "top_left" or frame["units"] != "pixel" or frame["paper_size_basis"] != "a4_assumed"
            or not isinstance(frame["page_size_pt"], list) or len(frame["page_size_pt"]) != 2
            or any(type(n) not in (int, float) for n in frame["page_size_pt"])
            or frame["page_size_pt"] != [source["width_pt"], source["height_pt"]]):
        _fail("source_frame_mismatch")
    return size


def _fragments(rows: Any, source: dict, target: dict, *, width: int, height: int, total: int,
               region_layout: dict | None = None, document_local_folios: bool = False,
               boundary_policy: str = BOUNDARY_POLICY):
    if (region_layout is not None) != document_local_folios:
        _fail("incomplete_region_profile")
    inline_cells = boundary_policy == CELL_BOUNDARY_POLICY
    if type(boundary_policy) is not str or boundary_policy not in {BOUNDARY_POLICY, CELL_BOUNDARY_POLICY} or inline_cells and region_layout is None:
        _fail("unsupported_boundary_policy")
    if not isinstance(rows, list) or not 0 < len(rows) <= MAX_FRAGMENTS:
        _fail("invalid_fragment_list")
    parent_index = source_start = target_start = 0
    result, seen = [], set()
    last_bottom = -1.0
    boundaries, cell_boundaries, inline_edges = {}, {}, set()
    for index, row in enumerate(rows, 1):
        _keys(row, {"rendering_id", "parent_block_id", "source_range", "target_range",
                   "source_text_sha256", "target_text_sha256", "role", "alignment", "bold", "italic",
                   "bbox_px", "review_note"})
        if parent_index >= len(source["blocks"]):
            _fail("extra_parent_fragment")
        left, right = source["blocks"][parent_index], target["blocks"][parent_index]
        render_id = row["rendering_id"]
        match = _RENDERING_ID.fullmatch(render_id) if isinstance(render_id, str) and len(render_id) <= 40 else None
        if (not match or render_id != f"p{source['page_number']:04d}_f{index:04d}" or render_id in seen
                or row["parent_block_id"] != left["id"]):
            _fail("fragment_identity_or_order_mismatch")
        seen.add(render_id)
        if parent_index not in boundaries:
            boundaries[parent_index] = (_line_boundaries(left["text"]), _line_boundaries(right["text"]))
            if inline_cells:
                from .reviewed_cell_boundaries import ReviewedCellBoundariesError, pipe_cell_boundaries
                try:
                    cell_boundaries[parent_index] = (pipe_cell_boundaries(left["text"]),
                                                     pipe_cell_boundaries(right["text"]))
                except ReviewedCellBoundariesError:
                    _fail("invalid_reviewed_cell_boundary")
        admitted = tuple(boundaries[parent_index][side] | cell_boundaries.get(parent_index, (frozenset(), frozenset()))[side]
                         for side in (0, 1))
        source_range = _range(row["source_range"], text=left["text"], start=source_start,
                              boundaries=admitted[0])
        target_range = _range(row["target_range"], text=right["text"], start=target_start,
                              boundaries=admitted[1])
        if source_range[0] not in boundaries[parent_index][0] or target_range[0] not in boundaries[parent_index][1]:
            previous = result[-1] if result else None
            if previous is None or previous.parent_block_id != left["id"]:
                _fail("invalid_inline_cell_adjacency")
            inline_edges.add((previous.rendering_id, render_id))
        source_text, target_text = left["text"][slice(*source_range)], right["text"][slice(*target_range)]
        if (row["source_text_sha256"] != _text_hash(source_text)
                or row["target_text_sha256"] != _text_hash(target_text)):
            _fail("fragment_text_hash_mismatch")
        if not isinstance(row["alignment"], str) or row["alignment"] not in {"left", "right", "center", "justify"}:
            _fail("unsupported_alignment")
        if type(row["bold"]) is not bool or type(row["italic"]) is not bool:
            _fail("invalid_style_flag")
        note = row["review_note"]
        if not isinstance(note, str) or not note.strip() or len(note) > 1000:
            _fail("invalid_review_note")
        _text_hash(note)
        box = _box(row["bbox_px"], width, height)
        if region_layout is None and box[1] < last_bottom:
            # Literal folios may sit beside a contact footer in the same bottom
            # band. Source/target ranges still establish their logical order;
            # the folio must be vertically contained by that footer and
            # horizontally disjoint. No overlapping ink boxes/general columns.
            previous = result[-1] if result else None
            same_band_folio = bool(previous and previous.role == "footer" and row["role"] == "folio"
                and previous.bbox_px[1] <= box[1] < box[3] <= previous.bbox_px[3]
                and (box[0] >= previous.bbox_px[2] or box[2] <= previous.bbox_px[0]))
            if not same_band_folio:
                _fail("overlapping_or_reordered_source_regions")
        last_bottom = max(last_bottom, box[3])
        _role(row["role"], source_text, target_text, box, page=source["page_number"], total=total, height=height,
              document_local_folios=document_local_folios)
        result.append(ReviewedFormattingFragment(render_id, left["id"], source_range, target_range,
            source_text, target_text, row["source_text_sha256"], row["target_text_sha256"],
            row["role"], row["alignment"], row["bold"], row["italic"], box, note, left.get("uncertain", False)))
        source_start, target_start = source_range[1], target_range[1]
        source_done, target_done = source_start == len(left["text"]), target_start == len(right["text"])
        if source_done != target_done:
            _fail("source_target_parent_end_mismatch")
        if source_done:
            parent_index += 1
            source_start = target_start = 0
    if parent_index != len(source["blocks"]) or source_start or target_start:
        _fail("incomplete_parent_coverage")
    if region_layout is not None:
        _validated_regions(region_layout, fragments=result, page_number=source["page_number"],
                           image_size_px=(width, height))
        # Validated ownership places every footer fragment in this page's one
        # explicit footer container. Folios have their own grammar and cannot
        # provide contact evidence. Keep the existing group size/text limits.
        contact_footer = [{"text": f.source_text.strip()} for f in result if f.role == "footer"]
        if contact_footer and not _contact_furniture(contact_footer):
            _fail("unsupported_footer_assertion")
        if inline_cells:
            from .reviewed_cell_boundaries import ReviewedCellBoundariesError, validated_inline_cell_pairs
            from .reviewed_regions import RegionFragmentInput
            try:
                pairs = validated_inline_cell_pairs(region_layout,
                    fragments=tuple(RegionFragmentInput(f.rendering_id, f.role, f.bbox_px) for f in result),
                    page_number=source["page_number"], image_size_px=(width, height))
            except (ReviewedCellBoundariesError, ValueError, TypeError, KeyError):
                _fail("invalid_reviewed_cell_boundary")
            if not inline_edges <= pairs:
                _fail("invalid_inline_cell_adjacency")
    return tuple(result)


def _validated_regions(layout, *, fragments, page_number, image_size_px):
    from .reviewed_regions import RegionFragmentInput, ReviewedRegionsError, validate_reviewed_regions
    try:
        return validate_reviewed_regions(layout, fragments=tuple(
            RegionFragmentInput(f.rendering_id, f.role, f.bbox_px) for f in fragments),
            page_number=page_number, image_size_px=image_size_px)
    except ReviewedRegionsError:
        _fail("invalid_reviewed_region_layout")


def _validated_folios(groups, *, pages, source_file_sha256, target_lang,
                      boundary_policy=BOUNDARY_POLICY):
    from .reviewed_folios import FolioFragmentInput, FolioPageInput, ReviewedFolioError, validate_document_local_folios
    try:
        return validate_document_local_folios(groups, pages=tuple(FolioPageInput(
            json.loads(p.source_structure_json), json.loads(p.target_structure_json), p.image_size_px[1],
            p.folio_fragment_id, tuple(FolioFragmentInput(f.rendering_id, f.parent_block_id,
                f.source_range, f.target_range, f.role, f.bbox_px) for f in p.fragments),
                region_layout=json.loads(p.region_layout_json) if boundary_policy == CELL_BOUNDARY_POLICY else None,
                image_width_px=p.image_size_px[0] if boundary_policy == CELL_BOUNDARY_POLICY else None) for p in pages),
            source_file_sha256=source_file_sha256, target_lang=target_lang)
    except ReviewedFolioError:
        _fail("invalid_document_local_folios")


def validate_reviewed_formatting(manifest_bytes: bytes, *, expected_manifest_sha256: str,
                                pages: Sequence[FormattingPageInput], source_file_sha256: str,
                                target_lang: str, preferences_sha256: str,
                                expected_reviewer_kind: str = "ai_test_review") -> ReviewedFormattingProjection:
    """Validate a pinned detached manifest against immutable original inputs.

    Offsets are Python/Unicode codepoint offsets, never UTF-16 code units or
    bytes. Each source and target parent is reconstructed separately, verbatim;
    its final separators belong to that fragment. Original inter-parent newlines
    remain in the retained original structures, not invented fragment text.
    One source page maps to one prospective section; rendered pages are unknown.
    Reviewer kind is caller-selected provenance, not reviewer authority or a
    certification. The strict default is unchanged for acceptance callers.
    """
    if type(expected_reviewer_kind) is not str or expected_reviewer_kind not in {"ai_test_review", "operator_review"}:
        _fail("invalid_expected_reviewer_kind")
    source_file_sha256, preferences_sha256 = _hash(source_file_sha256), _hash(preferences_sha256)
    if not isinstance(target_lang, str) or target_lang not in {"EN", "FR", "AR"}:
        _fail("invalid_target_language")
    if not isinstance(pages, (list, tuple)) or not 0 < len(pages) <= MAX_PAGES or any(
            not isinstance(page, FormattingPageInput) for page in pages):
        _fail("invalid_page_inputs")
    manifest = _parse(manifest_bytes, expected_manifest_sha256)
    regions = isinstance(manifest, dict) and manifest.get("version") == REGION_VERSION
    _keys(manifest, {
        "version", "policy", "boundary_policy", "offset_unit", "reviewer_kind", "source_file_sha256",
        "target_lang", "preferences_sha256", "full_case_pages", "pages"}
        | ({"document_groups", "folio_policy"} if regions else set())
        | ({"spacing_policy"} if regions and "spacing_policy" in manifest else set()))
    if (manifest["version"] != (REGION_VERSION if regions else VERSION)
            or manifest["policy"] != (REGION_POLICY if regions else POLICY)
            or (regions and manifest["folio_policy"] != FOLIO_POLICY)
            or ("spacing_policy" in manifest and manifest["spacing_policy"] != SOURCE_GAP_POLICY)
            or type(manifest["boundary_policy"]) is not str
            or manifest["boundary_policy"] not in ({BOUNDARY_POLICY, CELL_BOUNDARY_POLICY} if regions else {BOUNDARY_POLICY})
            or manifest["reviewer_kind"] != expected_reviewer_kind
            or manifest["offset_unit"] != "unicode_codepoint"
            or manifest["source_file_sha256"] != source_file_sha256 or manifest["target_lang"] != target_lang
            or manifest["preferences_sha256"] != preferences_sha256):
        _fail("manifest_binding_mismatch")
    numbers = manifest["full_case_pages"]
    if (not isinstance(numbers, list) or any(type(n) is not int for n in numbers)
            or numbers != list(range(1, len(pages) + 1)) or not isinstance(manifest["pages"], list)
            or len(manifest["pages"]) != len(pages)):
        _fail("incomplete_or_unordered_case")
    projected, commits, bundles = [], set(), set()
    for number, (row, input_page) in enumerate(zip(manifest["pages"], pages), 1):
        _keys(row, {"page_number", "commit_file_sha256", "bundle_sha256", "source_structure_sha256",
                   "target_structure_sha256", "source_image_sha256", "image_size_px", "frame", "fragments"}
                   | ({"region_layout", "folio_fragment_id"} if regions else set()))
        if (type(row["page_number"]) is not int or row["page_number"] != number
                or row["commit_file_sha256"] != _hash(input_page.commit_file_sha256)
                or row["bundle_sha256"] != _hash(input_page.bundle_sha256)
                or input_page.commit_file_sha256 in commits or input_page.bundle_sha256 in bundles):
            _fail("original_page_commit_mismatch")
        commits.add(input_page.commit_file_sha256)
        bundles.add(input_page.bundle_sha256)
        source, target, source_json, target_json = _bound_pair(input_page, number=number, source_hash=source_file_sha256)
        if (row["source_structure_sha256"] != _sha(source_json) or row["target_structure_sha256"] != _sha(target_json)):
            _fail("original_structure_hash_mismatch")
        width, height = _image(input_page, row, source)
        fragments = _fragments(row["fragments"], source, target, width=width, height=height, total=len(pages),
                               region_layout=row.get("region_layout"), document_local_folios=regions,
                               boundary_policy=manifest["boundary_policy"])
        projected.append(ReviewedFormattingPage(number, number - 1, input_page.commit_file_sha256,
            input_page.bundle_sha256, row["source_structure_sha256"], row["target_structure_sha256"],
            source_json, target_json, row["source_image_sha256"], (width, height),
            (source["width_pt"], source["height_pt"]), "a4_assumed", fragments, source["uncertain"],
            region_layout_json=_canonical(row["region_layout"]) if regions else None,
            folio_fragment_id=row.get("folio_fragment_id")))
    if regions:
        _validated_folios(manifest["document_groups"], pages=projected,
                           source_file_sha256=source_file_sha256, target_lang=target_lang,
                           boundary_policy=manifest["boundary_policy"])
        return ReviewedFormattingProjection(expected_manifest_sha256, source_file_sha256,
            target_lang, preferences_sha256, tuple(projected), version=REGION_VERSION, policy=REGION_POLICY,
            document_groups_json=_canonical(manifest["document_groups"]), folio_policy=FOLIO_POLICY,
            boundary_policy=manifest["boundary_policy"], spacing_policy=manifest.get("spacing_policy"),
            reviewer_kind=expected_reviewer_kind)
    return ReviewedFormattingProjection(expected_manifest_sha256, source_file_sha256,
        target_lang, preferences_sha256, tuple(projected), reviewer_kind=expected_reviewer_kind)
