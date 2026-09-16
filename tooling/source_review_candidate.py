"""Pure, opt-in source-review candidates; deliberately not production sources.

Callers supply bytes indexed by SHA256 and independently pinned manifest,
document and complete page inventory. No file, environment, provider, image
renderer, subprocess or application imports are used. Review records are
assertions by the named reviewer, NOT proof of OCR or legal correctness.

Manifest v1: kind=source_review_candidate_manifest, document_sha256, pages.
Each page binds PNG dimensions/hash, raw TXT/TSV/structure variants, a baseline,
explicit actions, reading_order and an image_source_review evidence hash.
Actions own every baseline block exactly once (retain/replace/omit_nontext);
transcribe owns a new non-overlapping image region, never fabricated OCR words.
Image review binds the entire page plan, including actions and order, via
SHA256(canonical JSON excluding review_evidence_sha256). It records reviewer,
full-page/order checks, boundary proposal and resolved/unresolved findings.

Output has separate reviewed_image_transcription_candidate_v1 provenance.
Review-record completeness is structural, not source or layout acceptance.
Raw OCR remains byte-bound evidence; no corrected PageStructure, word boxes,
confidence or accepted production review is emitted. Keep returned private
content out of Git/logs. See synthetic tests for the complete record schema.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import struct
import zlib
from typing import Mapping


_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
_MAX_JSON = 8_000_000
_MAX_ITEMS = 5000


class CandidateError(ValueError):
    """Content-free error; never include private text in diagnostics."""


def _require(condition, code="candidate_manifest_invalid"):
    if not condition:
        raise CandidateError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical_json(value) -> bytes:
    """Stable UTF-8 encoding used for review-plan and candidate identities."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _pairs(items):
    result = {}
    for key, value in items:
        _require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _json(raw):
    _require(type(raw) is bytes and 0 < len(raw) <= _MAX_JSON, "json_bytes_invalid")
    def invalid_constant(_):
        raise CandidateError("nonfinite_json")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                       parse_constant=invalid_constant)
    # Reject overflowed JSON exponents too, not just NaN/Infinity spellings.
    canonical_json(value)
    return value


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names.split()))


def _list(value, *, empty=False):
    _require(type(value) is list and (0 if empty else 1) <= len(value) <= _MAX_ITEMS)
    return value


def _text(value, *, empty=False):
    _require(type(value) is str and len(value) <= _MAX_JSON
             and (empty or bool(value.strip())))
    return value


def _id(value):
    _require(type(value) is str and _ID.fullmatch(value) is not None)
    return value


def _hash(value):
    _require(type(value) is str and _HASH.fullmatch(value) is not None,
             "artifact_binding_invalid")
    return value


def _artifact(artifacts, key):
    _hash(key)
    raw = artifacts.get(key)
    _require(type(raw) is bytes and _sha(raw) == key, "artifact_binding_invalid")
    return raw


def _box(value, size):
    _require(type(value) is list and len(value) == 4
             and all(type(n) in (int, float) and math.isfinite(n) for n in value),
             "region_invalid")
    _require(0 <= value[0] < value[2] <= size[0]
             and 0 <= value[1] < value[3] <= size[1], "region_invalid")


def _png_size(raw):
    # Only the PNG header is inspected. This is not a full decode/pixel review.
    _require(len(raw) >= 33 and raw[:8] == b"\x89PNG\r\n\x1a\n"
             and raw[8:16] == b"\0\0\0\rIHDR", "raster_header_invalid")
    _require(zlib.crc32(raw[12:29]) == struct.unpack(">I", raw[29:33])[0],
             "raster_header_invalid")
    size = list(struct.unpack(">II", raw[16:24]))
    _require(all(0 < n <= 100_000 for n in size), "raster_header_invalid")
    return size


def _variant(value, page, document, artifacts):
    _keys(value, "id text_sha256 tsv_sha256 structure_sha256")
    _id(value["id"])
    txt = _artifact(artifacts, value["text_sha256"]).decode("utf-8")
    tsv = _artifact(artifacts, value["tsv_sha256"]).decode("utf-8")
    source = _json(_artifact(artifacts, value["structure_sha256"]))
    _require(type(source) is dict and type(source.get("version")) is int
             and source["version"] == 1 and source.get("provenance") == "local_ocr_tsv"
             and type(source.get("page_number")) is int
             and source["page_number"] == page["page_number"]
             and source.get("source_file_sha256") == document
             and source.get("translation_sha256") is None, "raw_source_identity_invalid")
    blocks = {}
    for block in _list(source["blocks"]):
        identity = _id(block["id"])
        _require(identity.startswith(f"p{page['page_number']:04d}_b")
                 and identity not in blocks, "raw_block_identity_invalid")
        blocks[identity] = _text(block["text"])
    combined = "\n".join(blocks.values())
    _require(source["source_sha256"] == source["source_text_sha256"]
             == _sha(combined.encode()), "raw_source_text_invalid")
    metadata = source["metadata"]
    identity = metadata["source_page_identity"]
    _require(identity["source_file_sha256"] == document
             and identity["image_sha256"] == page["image_sha256"], "raw_source_identity_invalid")
    packet = metadata["ocr_word_evidence"]
    _require(type(packet["version"]) is int and packet["version"] == 1
             and packet["image_size_px"] == page["image_size_px"]
             and packet["tsv_sha256"] == metadata["ocr_tsv_sha256"] == value["tsv_sha256"],
             "raw_word_binding_invalid")
    selected = txt.replace("\r\n", "\n").replace("\r", "\n").strip()
    _require(metadata["selected_text_sha256"] == _sha(selected.encode()),
             "raw_source_text_invalid")
    words = packet["words"]
    _require(type(words) is list and 0 < len(words) <= 50_000, "raw_word_binding_invalid")
    owners = {key: [] for key in blocks}
    for word in words:
        _text(word["text"])
        _require(len(word["text"].split()) == 1 and word["block_id"] in owners,
                 "raw_word_binding_invalid")
        _box(word["bbox_px"], page["image_size_px"])
        confidence = word["confidence"]
        _require(type(confidence) in (int, float) and math.isfinite(confidence)
                 and 0 <= confidence <= 100, "raw_word_binding_invalid")
        owners[word["block_id"]].append(word["text"])
    reader = csv.DictReader(io.StringIO(tsv), delimiter="\t")
    fields = "level page_num block_num par_num line_num word_num left top width height conf text".split()
    _require(reader.fieldnames == fields, "raw_tsv_invalid")
    rows = [row for row in reader if row["level"] == "5" and row["text"].strip()]
    _require(len(rows) == len(words), "raw_word_binding_invalid")
    for row, word in zip(rows, words):
        left, top, width, height = (int(row[k]) for k in ("left", "top", "width", "height"))
        _require(row["text"] == word["text"]
                 and [left, top, left + width, top + height] == word["bbox_px"]
                 and float(row["conf"]) == word["confidence"], "raw_word_binding_invalid")
    _require(all(owners[key] == text.split() for key, text in blocks.items())
             and [word["text"] for word in words] == txt.split() == combined.split(),
             "raw_word_binding_invalid")
    boxes = {key: [word["bbox_px"] for word in words if word["block_id"] == key]
             for key in blocks}
    return blocks, boxes


def _actions(page, variants):
    baseline = variants[page["baseline_variant"]][0]
    owned = set()
    actions = {}
    regions = []
    for action in _list(page["actions"]):
        _keys(action, "id kind baseline_block_ids before_text before_sha256 after_text "
              "after_sha256 region_px evidence_refs rationale")
        identity = _id(action["id"])
        _require(identity not in actions, "duplicate_action")
        kind = action["kind"]
        _require(kind in {"retain", "replace", "omit_nontext", "transcribe"})
        ids = _list(action["baseline_block_ids"], empty=kind == "transcribe")
        _require(all(type(key) is str and key in baseline and key not in owned for key in ids)
                 and len(set(ids)) == len(ids), "block_ownership_invalid")
        _require(ids == [key for key in baseline if key in ids], "before_order_invalid")
        owned.update(ids)
        before = _text(action["before_text"], empty=kind == "transcribe")
        after = _text(action["after_text"], empty=kind == "omit_nontext")
        _require(before == "\n".join(baseline[key] for key in ids)
                 and action["before_sha256"] == _sha(before.encode())
                 and action["after_sha256"] == _sha(after.encode()), "action_text_binding_invalid")
        _require((kind != "transcribe" or (not ids and not before))
                 and (kind != "omit_nontext" or after == "")
                 and (kind != "retain" or after == before)
                 and (kind != "replace" or after != before), "action_kind_invalid")
        _text(action["rationale"])
        _box(action["region_px"], page["image_size_px"])
        box = action["region_px"]
        for old in regions:
            _require(max(box[0], old[0]) >= min(box[2], old[2])
                     or max(box[1], old[1]) >= min(box[3], old[3]), "region_ownership_conflict")
        regions.append(box)
        references = set()
        for ref in _list(action["evidence_refs"], empty=kind == "transcribe"):
            _keys(ref, "variant_id block_ids")
            _require(type(ref["variant_id"]) is str and ref["variant_id"] in variants,
                     "evidence_reference_invalid")
            for key in _list(ref["block_ids"]):
                pair = (ref["variant_id"], key)
                ref_blocks, ref_boxes = variants[ref["variant_id"]]
                _require(type(key) is str and key in ref_blocks
                         and pair not in references, "evidence_reference_invalid")
                # Region is review evidence, not replacement word geometry.
                _require(all(box[0] <= b[0] and box[1] <= b[1]
                             and box[2] >= b[2] and box[3] >= b[3]
                             for b in ref_boxes[key]), "evidence_region_mismatch")
                references.add(pair)
        _require(all((page["baseline_variant"], key) in references for key in ids),
                 "baseline_evidence_missing")
        actions[identity] = action
    _require(owned == set(baseline), "block_coverage_incomplete")
    order = _list(page["reading_order"])
    _require(all(type(key) is str for key in order) and len(set(order)) == len(order)
             and set(order) == {key for key, a in actions.items() if a["kind"] != "omit_nontext"},
             "reading_order_incomplete")
    return actions, "\n".join(actions[key]["after_text"] for key in order)


def _review(page, document, actions, artifacts):
    review = _json(_artifact(artifacts, page["review_evidence_sha256"]))
    _keys(review, "version kind review_kind reviewer document_sha256 page_number image_sha256 "
          "page_plan_sha256 full_page_review_completed reading_order_reviewed boundary findings")
    plan = {key: value for key, value in page.items() if key != "review_evidence_sha256"}
    _require(type(review["version"]) is int and review["version"] == 1
             and review["kind"] == "image_source_review"
             and review["review_kind"] in {"ai_test_review", "operator_review"}
             and review["document_sha256"] == document
             and type(review["page_number"]) is int and review["page_number"] == page["page_number"]
             and review["image_sha256"] == page["image_sha256"]
             and review["page_plan_sha256"] == _sha(canonical_json(plan)), "review_binding_invalid")
    _text(review["reviewer"])
    for field in ("full_page_review_completed", "reading_order_reviewed"):
        _require(type(review[field]) is bool)
    boundary = review["boundary"]
    _keys(boundary, "decision rationale")
    _require(boundary["decision"] in {"start", "continuation", "unresolved"})
    _require(page["page_number"] != 1 or boundary["decision"] != "continuation",
             "first_page_boundary_invalid")
    _text(boundary["rationale"])
    complete = (review["full_page_review_completed"] and review["reading_order_reviewed"]
                and boundary["decision"] != "unresolved")
    seen = set()
    for finding in _list(review["findings"], empty=True):
        _keys(finding, "id category status action_ids rationale")
        identity = _id(finding["id"])
        _require(identity not in seen)
        seen.add(identity)
        _require(finding["category"] in {"identifier", "citation", "omission", "invention",
                 "reading_order", "boundary", "other"}
                 and finding["status"] in {"resolved", "unresolved"})
        refs = _list(finding["action_ids"], empty=finding["status"] == "unresolved")
        _require(all(type(key) is str and key in actions for key in refs)
                 and len(set(refs)) == len(refs))
        _text(finding["rationale"])
        complete = complete and finding["status"] == "resolved"
    return review, complete


def build_candidate(manifest_bytes: bytes, *, expected_manifest_sha256: str,
                    document_sha256: str, page_numbers: tuple[int, ...],
                    artifacts: Mapping[str, bytes], require_complete: bool = False) -> dict:
    """Build an isolated review record, never an accepted production source.

The manifest digest and full document/page inventory must come from the calling
scope, not be inferred from a possibly partial manifest. Inputs are never edited.
Unresolved reviews return an explicit incomplete candidate unless the caller
requests require_complete, which fails closed. Missing/invalid evidence always
raises a content-free CandidateError.
    """
    try:
        _require(type(require_complete) is bool)
        _require(type(artifacts) is dict, "artifact_mapping_invalid")
        _require(type(manifest_bytes) is bytes and _sha(manifest_bytes)
                 == _hash(expected_manifest_sha256), "manifest_binding_invalid")
        _require(type(page_numbers) is tuple and 0 < len(page_numbers) <= _MAX_ITEMS
                 and all(type(n) is int for n in page_numbers)
                 and page_numbers == tuple(range(1, len(page_numbers) + 1)),
                 "complete_page_inventory_required")
        _artifact(artifacts, document_sha256)
        manifest = _json(manifest_bytes)
        _keys(manifest, "version kind document_sha256 pages")
        _require(type(manifest["version"]) is int and manifest["version"] == 1
                 and manifest["kind"] == "source_review_candidate_manifest"
                 and manifest["document_sha256"] == document_sha256)
        pages = _list(manifest["pages"])
        _require(tuple(p["page_number"] for p in pages) == page_numbers,
                 "complete_page_inventory_required")
        result_pages = []
        all_complete = True
        for page in pages:
            _keys(page, "page_number image_sha256 image_size_px variants baseline_variant "
                  "actions reading_order review_evidence_sha256")
            _require(type(page["page_number"]) is int)
            size = page["image_size_px"]
            _require(type(size) is list and len(size) == 2
                     and all(type(n) is int and n > 0 for n in size)
                     and size == _png_size(_artifact(artifacts, page["image_sha256"])),
                     "raster_dimensions_invalid")
            variants = {}
            for variant in _list(page["variants"]):
                _id(variant["id"])
                _require(variant["id"] not in variants, "duplicate_variant")
                variants[variant["id"]] = _variant(variant, page, document_sha256, artifacts)
            _require(type(page["baseline_variant"]) is str and page["baseline_variant"] in variants)
            actions, text = _actions(page, variants)
            review, complete = _review(page, document_sha256, actions, artifacts)
            all_complete = all_complete and complete
            result_pages.append({"page_number": page["page_number"],
                "candidate_text": text, "candidate_text_sha256": _sha(text.encode()),
                "review_record_complete": complete, "review": review,
                "boundary_proposal": dict(review["boundary"])})
        _require(not require_complete or all_complete, "candidate_review_unresolved")
        result = {"version": 1, "kind": "offline_source_review_candidate",
                  "provenance": "reviewed_image_transcription_candidate_v1",
                  "status": "review_record_complete" if all_complete else "review_record_incomplete",
                  "production_eligible": False, "source_acceptance": "not_evaluated",
                  "layout_acceptance": "not_evaluated", "manifest_sha256": expected_manifest_sha256,
                  "review_manifest": manifest, "pages": result_pages}
        result["candidate_sha256"] = _sha(canonical_json(result))
        return result
    except CandidateError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, IndexError,
            OverflowError, RecursionError, UnicodeError, struct.error, csv.Error):
        raise CandidateError("candidate_evidence_invalid") from None


def verify_candidate(candidate_bytes: bytes, manifest_bytes: bytes, **bindings) -> dict:
    """Rebuild from pinned immutable evidence and reject any candidate drift."""
    expected = build_candidate(manifest_bytes, **bindings)
    try:
        actual = _json(candidate_bytes)
        _require(canonical_json(actual) == canonical_json(expected), "candidate_changed")
    except CandidateError:
        raise
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise CandidateError("candidate_changed") from None
    return expected
