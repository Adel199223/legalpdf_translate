"""Narrow source-owned OCR flow eligibility, never general scan certainty.

Same-pass word evidence may justify simple flow and existing conservative
furniture/continuation rules. It cannot certify transcription, omitted ink,
semantic tables, reading meaning or legal fidelity. Original uncertainty is
never changed. Pixel diagnostics are exact-raster, hash-bound provenance;
validation recomputes source gates but does not claim to rerender absent pixels.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import io
import json
import math
import re

from .document_structure import SOURCE_STRUCTURE_VERSION, validate_page_structure, text_sha256

LAYOUT_ELIGIBILITY_VERSION = 1
LAYOUT_ELIGIBILITY_POLICY = "local_ocr_simple_flow_v1"
MAX_WORDS = 50000
MAX_EVIDENCE_BYTES = 4 * 1024 * 1024
MAX_IMAGE_PIXELS = 40000000
MIN_CONFIDENCE = 90.0
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_REASONS = {"local_ocr_reading_order_requires_review"}


def _digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _require(condition, reason):
    if not condition:
        raise ValueError(reason)


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _box(value, width, height):
    return (isinstance(value, list) and len(value) == 4 and all(_number(n) for n in value)
            and 0 <= value[0] < value[2] <= width and 0 <= value[1] < value[3] <= height)


def _union(boxes):
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def _source_gates(value, identity):
    source = validate_page_structure(value)
    metadata = source.metadata
    _require(source.provenance == "local_ocr_tsv", "not_local_same_pass_ocr")
    _require(isinstance(identity, dict) and identity == metadata.get("source_page_identity"), "source_identity_mismatch")
    _require(set(identity) == {"source_file_sha256", "image_sha256", "source_type", "paper_size_basis"}
             and all(isinstance(value, str) for value in identity.values()), "source_identity_schema")
    _require(identity.get("source_type") in {"browser_pdf_image", "image"}, "unsupported_source_lane")
    _require(identity.get("paper_size_basis") == "a4_assumed", "unsupported_raster_page_frame")
    _require(identity.get("source_file_sha256") == source.source_file_sha256
             and isinstance(source.source_file_sha256, str) and _HASH.fullmatch(source.source_file_sha256), "source_file_binding_missing")
    _require(isinstance(identity.get("image_sha256"), str) and _HASH.fullmatch(identity["image_sha256"]), "source_raster_binding_missing")
    _require(not metadata.get("document_boundary_review_required")
             and not any(b.document_start for b in source.blocks[1:]), "document_boundary_uncertain")
    _require(isinstance(metadata.get("warnings"), list)
             and set(metadata["warnings"]) == _REASONS, "unrecognized_source_uncertainty")
    _require(not metadata.get("ocr_word_evidence_unavailable"), "word_evidence_unavailable")
    _require(metadata.get("text_binding") == "ordered_non_whitespace_tokens", "selected_text_binding_missing")
    _require(type(metadata.get("psm")) is int and metadata["psm"] in {6, 11}
             and isinstance(metadata.get("local_pass"), str)
             and bool(metadata["local_pass"]) and isinstance(metadata.get("language_pack"), str)
             and bool(metadata["language_pack"]), "same_pass_identity_missing")
    _require(metadata.get("extraction_version") == SOURCE_STRUCTURE_VERSION,
             "extraction_version_unsupported")
    for name in ("selected_text_sha256", "image_sha256"):
        _require(isinstance(metadata.get(name), str) and _HASH.fullmatch(metadata[name]), "selected_input_hash_missing")
    _require(bool(source.blocks) and len(source.blocks) <= 5000, "source_block_limit")
    for block in source.blocks:
        _require(not block.uncertain and not block.table_id and block.role != "table_cell", "complex_or_uncertain_block")
        _require(block.bbox is not None and _box(list(block.bbox), source.width_pt, source.height_pt), "block_geometry_invalid")
    packet = metadata.get("ocr_word_evidence")
    _require(isinstance(packet, dict) and set(packet) == {"version", "tsv_sha256", "image_size_px", "words"}
             and type(packet["version"]) is int and packet["version"] == 1, "word_evidence_schema")
    _require(isinstance(packet["tsv_sha256"], str) and _HASH.fullmatch(packet["tsv_sha256"]), "tsv_binding_missing")
    _require(len(json.dumps(packet, ensure_ascii=False, allow_nan=False).encode()) <= MAX_EVIDENCE_BYTES, "word_evidence_size_limit")
    size, words = packet["image_size_px"], packet["words"]
    _require(isinstance(size, list) and len(size) == 2 and all(type(n) is int and n >= 128 for n in size)
             and size[0] * size[1] <= MAX_IMAGE_PIXELS, "raster_dimensions_invalid")
    width, height = size
    _require(isinstance(words, list) and 4 <= len(words) <= MAX_WORDS, "word_count_limit")
    by_id = {block.id: block for block in source.blocks}
    owned = {block.id: [] for block in source.blocks}
    lines = OrderedDict()
    previous_group = None
    closed_groups = set()
    seen_ids = []
    for word in words:
        _require(isinstance(word, dict) and set(word) == {"block_id", "text", "bbox_px", "confidence", "group", "word_number"}, "word_schema")
        owner, text, box, group = word["block_id"], word["text"], word["bbox_px"], word["group"]
        _require(owner in by_id and isinstance(text, str) and text and text.split() == [text], "word_text_or_owner_invalid")
        _require(_number(word["confidence"]) and MIN_CONFIDENCE <= word["confidence"] <= 100, "word_confidence_low")
        _require(_box(box, width, height), "word_geometry_invalid")
        _require(isinstance(group, list) and len(group) == 3
                 and all(type(n) is int and n > 0 for n in group), "word_group_invalid")
        key = tuple(group)
        if key != previous_group:
            _require(key not in closed_groups, "noncontiguous_ocr_line")
            if previous_group is not None:
                closed_groups.add(previous_group)
            previous_group = key
        line = lines.setdefault(key, [])
        _require(type(word["word_number"]) is int and word["word_number"] == len(line) + 1, "word_order_invalid")
        _require(not line or line[0]["block_id"] == owner, "line_ownership_conflict")
        if line:
            gap = box[0] - line[-1]["bbox_px"][2]
            _require(-1.0 <= gap <= max(18.0, width * .045), "word_overlap_or_column_gap")
        line.append(word)
        owned[owner].append(word)
        if not seen_ids or seen_ids[-1] != owner:
            seen_ids.append(owner)
    _require(seen_ids == [block.id for block in source.blocks], "source_block_order_mismatch")
    source_texts = []
    for block in source.blocks:
        block_words = owned[block.id]
        _require(bool(block_words), "unowned_source_block")
        text = " ".join(word["text"] for word in block_words)
        _require("|" not in text and "\t" not in text, "unresolved_table_text")
        # A translated sidecar retains exact source OCR evidence. Its text is
        # separately checked by the existing source/target pair validator.
        if source.translation_sha256 is None:
            _require(text == block.text, "source_word_text_mismatch")
        source_texts.append(text)
        pixels = _union([word["bbox_px"] for word in block_words])
        projected = [pixels[0] / width * source.width_pt, pixels[1] / height * source.height_pt,
                     pixels[2] / width * source.width_pt, pixels[3] / height * source.height_pt]
        _require(all(abs(a - b) <= 1.0 for a, b in zip(projected, block.bbox)), "source_word_geometry_mismatch")
    _require(source.source_sha256 == source.source_text_sha256 == text_sha256("\n".join(source_texts)), "source_text_hash_mismatch")
    if source.translation_sha256 is not None:
        _require(source.translation_sha256 == text_sha256(source.text), "target_text_hash_mismatch")
    line_boxes = []
    body_lefts = []
    for line in lines.values():
        box = _union([word["bbox_px"] for word in line])
        if line_boxes:
            _require(box[1] >= line_boxes[-1][3] - 1.0, "line_overlap_or_reading_order")
        line_boxes.append(box)
        owner = by_id[line[0]["block_id"]]
        if owner.role not in {"header", "footer"}:
            body_lefts.append(box[0])
    _require(bool(body_lefts), "no_substantive_body")
    _require(max(body_lefts) - min(body_lefts) <= max(12.0, width * .04), "multiple_body_columns_or_alignment")
    # Furniture candidates must be spatially isolated; recurrence, safe contact
    # text, section boundaries and partial-selection rules remain caller-owned.
    header_boxes = [list(b.bbox) for b in source.blocks if b.role == "header"]
    footer_boxes = [list(b.bbox) for b in source.blocks if b.role == "footer"]
    body_boxes = [list(b.bbox) for b in source.blocks if b.role not in {"header", "footer"}]
    if header_boxes:
        _require(max(b[3] for b in header_boxes) <= source.height_pt * .25
                 and min(b[1] for b in body_boxes) - max(b[3] for b in header_boxes) >= 6,
                 "header_body_separation_missing")
    if footer_boxes:
        _require(min(b[1] for b in footer_boxes) >= source.height_pt * .80
                 and min(b[1] for b in footer_boxes) - max(b[3] for b in body_boxes) >= 6,
                 "footer_body_separation_missing")
    bindings = {"source_identity": identity, "page_number": source.page_number,
                "source_sha256": source.source_sha256, "selected_text_sha256": metadata["selected_text_sha256"],
                "image_sha256": metadata["image_sha256"], "word_evidence_sha256": _digest(packet),
                "source_geometry_sha256": _digest({"size": [source.width_pt, source.height_pt],
                    "blocks": [{k: v for k, v in b.to_dict().items() if k != "text"} for b in source.blocks],
                    "flags": [source.uncertain, source.document_start, source.continuation_from_previous, source.continuation_to_next]}),
                "extraction": {key: metadata.get(key) for key in ("extraction_version", "local_pass", "psm", "language_pack", "text_binding", "warnings")}}
    return source, bindings, packet


def _pixel_diagnostics(image_bytes, packet):
    # Two bounded local raster traversals (Pillow mask/histogram and Python
    # ruling detection); no OCR. Large 40M-pixel images may be comparatively
    # slow; the resulting record is a format-only source-bound derivative.
    from PIL import Image, ImageChops, ImageDraw
    _require(isinstance(image_bytes, bytes) and len(image_bytes) <= 32 * 1024 * 1024, "raster_bytes_limit")
    try:
        opened = Image.open(io.BytesIO(image_bytes))
    except Image.DecompressionBombError as exc:
        raise ValueError("raster_dimensions_invalid") from exc
    with opened as original:
        _require(list(original.size) == packet["image_size_px"], "raster_dimensions_mismatch")
        _require(original.width * original.height <= MAX_IMAGE_PIXELS, "raster_dimensions_invalid")
        if original.mode == "RGBA":
            background = Image.new("RGBA", original.size, "white")
            background.alpha_composite(original)
            gray = background.convert("L")
        else:
            gray = original.convert("L")
    dark = gray.point([255 if n < 180 else 0 for n in range(256)], mode="L")
    ink = dark.histogram()[255]
    width, height = dark.size
    mask = Image.new("L", dark.size, 0)
    drawing = ImageDraw.Draw(mask)
    pad = max(1, round(width / 600))
    for word in packet["words"]:
        x0, y0, x1, y1 = word["bbox_px"]
        drawing.rectangle((math.floor(x0) - pad, math.floor(y0) - pad,
                           math.ceil(x1) + pad, math.ceil(y1) + pad), fill=255)
    unexplained = ImageChops.subtract(dark, mask).histogram()[255]
    horizontal, vertical = 0, 0
    columns = [0] * width
    pixels = dark.tobytes()
    for y in range(height):
        run = 0
        for x in range(width):
            if pixels[y * width + x]:
                run += 1
                columns[x] += 1
                horizontal = max(horizontal, run)
                vertical = max(vertical, columns[x])
            else:
                run = 0
                columns[x] = 0
    return {"version": 1, "image_size_px": [width, height], "dark_pixels": ink,
            "unexplained_dark_pixels": unexplained, "maximum_horizontal_stroke_px": horizontal,
            "maximum_vertical_stroke_px": vertical}


def _pixels_eligible(value, packet):
    keys = {"version", "image_size_px", "dark_pixels", "unexplained_dark_pixels",
            "maximum_horizontal_stroke_px", "maximum_vertical_stroke_px"}
    if (not isinstance(value, dict) or set(value) != keys or type(value.get("version")) is not int
            or value["version"] != 1 or value.get("image_size_px") != packet["image_size_px"]):
        return False
    fields = keys - {"version", "image_size_px"}
    if any(type(value[name]) is not int or value[name] < 0 for name in fields):
        return False
    width, height = packet["image_size_px"]
    ink = value["dark_pixels"]
    return bool(20 <= ink <= width * height and value["unexplained_dark_pixels"] <= min(12, ink * .005)
                and 1 <= value["maximum_horizontal_stroke_px"] <= width
                and value["maximum_horizontal_stroke_px"] < max(30, width * .20)
                and 1 <= value["maximum_vertical_stroke_px"] <= height
                and value["maximum_vertical_stroke_px"] < max(30, height * .12))


def _record(bindings, pixels, reasons):
    record = {"version": LAYOUT_ELIGIBILITY_VERSION, "policy": LAYOUT_ELIGIBILITY_POLICY,
              "status": "needs_review" if reasons else "eligible_simple_flow",
              "scope": ["simple_flow", "section_furniture", "confirmed_continuation"],
              "bindings": bindings, "pixel_diagnostics": pixels, "reasons": reasons}
    # Caller dictionaries (notably source_identity) must not remain aliased to
    # a record whose consumer is allowed to serialize or inspect it separately.
    record = json.loads(json.dumps(record, ensure_ascii=False, allow_nan=False))
    record["record_sha256"] = _digest(record)
    return record


def derive_layout_eligibility(source, *, image_bytes: bytes, source_identity: dict) -> dict:
    """Derive a detached bounded record; no I/O, OCR or mutation of source."""
    bindings, pixels = {}, {}
    try:
        parsed, bindings, packet = _source_gates(source, source_identity)
        _require(hashlib.sha256(image_bytes).hexdigest() == bindings["image_sha256"], "ocr_input_raster_mismatch")
        pixels = _pixel_diagnostics(image_bytes, packet)
        _require(_pixels_eligible(pixels, packet), "raster_has_unexplained_ink_or_rulings")
        return _record(bindings, pixels, [])
    except (ValueError, TypeError, KeyError, OverflowError, OSError, UnicodeError) as exc:
        reason = str(exc)
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,100}", reason):
            reason = "invalid_layout_eligibility_evidence"
        try:
            return _record(bindings, pixels, [reason])
        except (ValueError, TypeError, OverflowError, UnicodeError):
            # Malformed retained strings (for example escaped lone surrogates)
            # must not make even the fail-closed diagnostic unserializable.
            return _record({}, {}, ["invalid_layout_eligibility_evidence"])


def valid_layout_eligibility(source, record) -> bool:
    """Recompute source/policy gates; pixel claims remain hash-bound provenance."""
    try:
        expected_keys = {"version", "policy", "status", "scope", "bindings", "pixel_diagnostics", "reasons", "record_sha256"}
        if not isinstance(record, dict) or set(record) != expected_keys:
            return False
        if (type(record["version"]) is not int or record["version"] != LAYOUT_ELIGIBILITY_VERSION
                or record["policy"] != LAYOUT_ELIGIBILITY_POLICY
                or record["status"] != "eligible_simple_flow" or record["reasons"]
                or record["scope"] != ["simple_flow", "section_furniture", "confirmed_continuation"]
                or record["record_sha256"] != _digest({k: v for k, v in record.items() if k != "record_sha256"})):
            return False
        parsed, bindings, packet = _source_gates(source, record["bindings"]["source_identity"])
        return bindings == record["bindings"] and _pixels_eligible(record["pixel_diagnostics"], packet)
    except (ValueError, TypeError, KeyError, OverflowError, UnicodeError):
        return False
