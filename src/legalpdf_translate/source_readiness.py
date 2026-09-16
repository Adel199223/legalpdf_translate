"""Read-only source diagnostics and explicit, private full-case review binding.

No recognition, source repair, approval generation or transport lives here.
The legacy OCR score ranks candidates; it never proves transcription fidelity.
"""
from __future__ import annotations

from copy import deepcopy
import json
import math
import re

from .document_structure import PageStructure, validate_page_structure, text_sha256, MAX_OCR_WORDS
from .structured_artifacts import StructuredArtifactError, _decode

SOURCE_READINESS_VERSION = "source_readiness_v1"
_HASH = re.compile(r"[a-f0-9]{64}\Z")


class SourceReadinessError(StructuredArtifactError):
    """Content-free source review failure, distinct from output validation."""


def _digest(value):
    return text_sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=False, allow_nan=False))


def source_structure_digest(source: PageStructure) -> str:
    """Bind all source-owned fields, excluding only the derived diagnostic cache."""
    value = validate_page_structure(source).to_dict()
    value["metadata"].pop("source_readiness", None)
    return _digest(value)


def source_readiness_diagnostics(source: PageStructure | dict) -> dict:
    source = validate_page_structure(source)
    codes = set()
    counts = {"words": 0, "below_60": 0, "below_90": 0,
              "small_low_confidence_words": 0, "wide_word_gaps": 0}
    if not source.text.strip():
        codes.add("source_text_missing")
    if source.uncertain or any(block.uncertain for block in source.blocks):
        codes.add("source_structure_uncertain")
    if source.metadata.get("document_boundary_review_required"):
        codes.add("document_boundary_unresolved")
    if source.provenance == "local_ocr_tsv":
        # Even high-confidence words do not prove omitted ink or correct order.
        codes.update(("source_image_fidelity_not_reviewed", "unrecognized_ink_not_evaluated",
                      "ocr_reading_order_not_reviewed"))
        try:
            packet = source.metadata["ocr_word_evidence"]
            words = packet["words"]
            width, height = packet["image_size_px"]
            if (type(packet["version"]) is not int or packet["version"] != 1
                    or not _is_hash(packet["tsv_sha256"])
                    or packet["tsv_sha256"] != source.metadata.get("ocr_tsv_sha256")
                    or any(type(v) is not int or v <= 0 for v in (width, height))
                    or not isinstance(words, list) or not 0 < len(words) <= MAX_OCR_WORDS):
                raise ValueError
            owners = {block.id: [] for block in source.blocks}
            groups = {}
            for word in words:
                confidence = word["confidence"]
                box = word["bbox_px"]
                if (type(confidence) not in (int, float) or not math.isfinite(confidence)
                        or not 0 <= confidence <= 100 or len(box) != 4
                        or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
                        or not 0 <= box[0] < box[2] <= width or not 0 <= box[1] < box[3] <= height
                        or not isinstance(word["text"], str) or not word["text"].strip()
                        or re.search(r"\s", word["text"])):
                    raise ValueError
                owners[word["block_id"]].append(word["text"])
                groups.setdefault(tuple(word["group"]), []).append(box)
                counts["words"] += 1
                counts["below_60"] += int(confidence < 60)
                counts["below_90"] += int(confidence < 90)
                # Diagnostic only: small print can carry dates/IDs/contact fields.
                counts["small_low_confidence_words"] += int(confidence < 90 and box[3] - box[1] < height * .012)
            if any(owners[b.id] != b.text.split() for b in source.blocks):
                raise ValueError
            for boxes in groups.values():
                if any(b[0] < a[0] for a, b in zip(boxes, boxes[1:])):
                    codes.add("ocr_word_order_conflict")
                boxes = sorted(boxes)
                counts["wide_word_gaps"] += sum(b[0] - a[2] > width * .12 for a, b in zip(boxes, boxes[1:]))
            if counts["below_90"]:
                codes.add("low_confidence_source_words")
            if counts["small_low_confidence_words"]:
                codes.add("small_source_fields_require_review")
            if counts["wide_word_gaps"]:
                codes.add("possible_mixed_columns")
            if any(b.uncertain and (b.role == "footer" or b.bbox and b.bbox[1] > source.height_pt * .85)
                   for b in source.blocks):
                codes.add("uncertain_footer_content")
        except (KeyError, TypeError, ValueError, OverflowError):
            counts = {key: None for key in counts}
            codes.add("same_pass_word_evidence_invalid_or_missing")
    elif source.provenance != "digital_pdf":
        codes.add("source_geometry_not_verified")
    try:
        source_digest = source_structure_digest(source)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        source_digest = None
        codes.add("source_binding_invalid")
    return {"version": SOURCE_READINESS_VERSION, "status": "review_required",
            "fidelity_status": "not_evaluated", "winner_score_is_fidelity": False,
            "source_structure_sha256": source_digest,
            "codes": sorted(codes), "counts": counts}


def _is_hash(value):
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _source_identity(value, source_hash):
    if (not isinstance(value, dict) or set(value) != {"source_file_sha256", "image_sha256", "source_type", "paper_size_basis"}
            or value["source_file_sha256"] != source_hash or not _is_hash(source_hash)
            or value["source_type"] not in {"pdf", "image", "browser_pdf_image"}
            or value["paper_size_basis"] not in {"source_pdf", "a4_assumed"}
            or (value["source_type"] == "pdf" and value["image_sha256"] != "")
            or (value["source_type"] != "pdf" and not _is_hash(value["image_sha256"]))):
        raise SourceReadinessError("source_review_identity_invalid")


def verify_source_review(raw: str | None, *, page_identities: dict, source_hash: str,
                         reviewed_evidence=None, page_sizes: dict | None = None) -> dict[int, dict]:
    """Verify a caller-supplied review, not perform or infer one.

    All pages must have an explicit completed source/boundary review, including
    pages outside the pilot dispatch subset. The production caller must also
    bind these exact private bytes in the externally approved config manifest.
    A reviewed source still does not certify translation or layout acceptance.
    """
    try:
        if (not isinstance(raw, str) or len(raw.encode("utf-8")) > 8_000_000
                or not isinstance(page_identities, dict) or not 0 < len(page_identities) <= 5000
                or any(type(n) is not int or n < 1 for n in page_identities)):
            raise ValueError
        review = _decode(raw.encode("utf-8"))
        from .reviewed_source import REVIEWED_ACCEPTANCE_VERSION, REVIEWED_SOURCE_VERSION
        if isinstance(review, dict) and review.get("version") == REVIEWED_ACCEPTANCE_VERSION:
            return _verify_reviewed_transcription(review, page_identities=page_identities,
                source_hash=source_hash, evidence=reviewed_evidence, page_sizes=page_sizes)
        if reviewed_evidence is not None:
            raise ValueError
        if (set(review) != {"version", "review_kind", "review_evidence_sha256", "source_file_sha256", "pages"}
                or review["version"] != SOURCE_READINESS_VERSION
                or review["review_kind"] not in {"ai_test_review", "operator_review"}
                or not _is_hash(review["review_evidence_sha256"])
                or review["source_file_sha256"] != source_hash
                or not isinstance(review["pages"], list) or len(review["pages"]) != len(page_identities)):
            raise ValueError
        rows = {}
        for row in review["pages"]:
            if (set(row) != {"source_structure", "reviewed_source_sha256", "readiness_sha256",
                            "source_fidelity", "document_boundary", "unresolved_findings"}
                    or row["source_fidelity"] != "accepted" or row["document_boundary"] != "accepted"
                    or row["unresolved_findings"] != []):
                raise ValueError
            source = validate_page_structure(row["source_structure"])
            if source.provenance == REVIEWED_SOURCE_VERSION or "reviewed_source" in source.metadata:
                raise ValueError  # A legacy review cannot opt into reviewed-text routing.
            number = source.page_number
            if number in rows or number not in page_identities or not source.blocks or not source.text.strip():
                raise ValueError
            identity = source.metadata.get("source_page_identity")
            _source_identity(identity, source_hash)
            if (identity != page_identities[number] or source.source_file_sha256 != source_hash
                    or source.translation_sha256 is not None
                    or source.source_sha256 != text_sha256(source.text)
                    or source.source_text_sha256 != text_sha256(source.text)
                    or source.metadata.get("document_boundary_review_required")
                    or not _is_hash(source.metadata.get("selected_text_sha256"))
                    or row["reviewed_source_sha256"] != source_structure_digest(source)
                    or row["readiness_sha256"] != _digest(source_readiness_diagnostics(source))):
                raise ValueError
            rows[number] = deepcopy(row)
        if set(rows) != set(page_identities):
            raise ValueError
        return rows
    except (ValueError, TypeError, KeyError, OverflowError, AttributeError, UnicodeError, RecursionError):
        raise SourceReadinessError("acceptance_source_review_unresolved") from None


def verify_reviewed_page(raw: str | None, *, page_identities: dict, source_hash: str,
                         source: PageStructure, reviewed_evidence=None, page_sizes=None):
    rows = verify_source_review(raw, page_identities=page_identities, source_hash=source_hash,
        reviewed_evidence=reviewed_evidence, page_sizes=page_sizes)
    if (source.page_number not in rows
            or rows[source.page_number]["reviewed_source_sha256"] != source_structure_digest(source)):
        raise SourceReadinessError("acceptance_reviewed_source_changed")


def _verify_reviewed_transcription(review, *, page_identities, source_hash, evidence, page_sizes):
    """Check a separately authored decision; the pure adapter never creates one."""
    from .reviewed_source import adapt_reviewed_candidate, ReviewedSourceError
    if (set(review) != {"version", "review_kind", "review_evidence_sha256", "source_file_sha256",
                       "candidate_file", "manifest_file", "evidence_files", "pages"}
            or review["review_kind"] not in {"ai_test_review", "operator_review"}
            or not _is_hash(review["review_evidence_sha256"])
            or review["source_file_sha256"] != source_hash
            or not isinstance(review["evidence_files"], list)
            or not 0 < len(review["evidence_files"]) <= 50_000):
        raise ValueError
    entries = [review["candidate_file"], review["manifest_file"], *review["evidence_files"]]
    paths = set()
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != {"path", "sha256"}
                or not isinstance(entry["path"], str) or not entry["path"]
                or entry["path"] in paths or not _is_hash(entry["sha256"])):
            raise ValueError
        paths.add(entry["path"])
    if evidence is None or {key for key, _ in evidence.artifacts} != {e["sha256"] for e in review["evidence_files"]}:
        raise ValueError
    for identity in page_identities.values():
        _source_identity(identity, source_hash)
    try:
        sources = adapt_reviewed_candidate(evidence,
            candidate_sha256=review["candidate_file"]["sha256"],
            manifest_sha256=review["manifest_file"]["sha256"], source_hash=source_hash,
            page_identities=page_identities, page_sizes=page_sizes)
    except ReviewedSourceError:
        raise ValueError from None
    if (not isinstance(review["pages"], list) or len(review["pages"]) != len(sources)
            or [r["page_number"] for r in review["pages"]] != sorted(sources)):
        raise ValueError
    rows = {}
    for row in review["pages"]:
        if (set(row) != {"page_number", "reviewed_source_sha256", "readiness_sha256",
                        "source_fidelity", "document_boundary", "unresolved_findings"}
                or type(row["page_number"]) is not int
                or row["source_fidelity"] != "accepted" or row["document_boundary"] != "accepted"
                or row["unresolved_findings"] != []):
            raise ValueError
        source = sources[row["page_number"]]
        if (row["reviewed_source_sha256"] != source_structure_digest(source)
                or row["readiness_sha256"] != _digest(source_readiness_diagnostics(source))):
            raise ValueError
        rows[source.page_number] = {**deepcopy(row), "source_structure": source.to_dict()}
    return rows
