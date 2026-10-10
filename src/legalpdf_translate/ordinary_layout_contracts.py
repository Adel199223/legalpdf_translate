"""Pure, text-preserving contracts for ordinary-job layout proposals."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import unicodedata
from typing import Any, Mapping

from .saved_docx_layout import inspect_docx, validate_decisions

VERSION = "ordinary_layout_v1"
PROPOSAL_VERSION = "ordinary_layout_proposal_v1"
PROPOSAL_VERSION_V2 = "ordinary_layout_proposal_v2"
PROPOSAL_VERSION_V3 = "ordinary_layout_proposal_v3"
MAX_PAGE_PARAGRAPHS = 200
MAX_PAGE_CODEPOINTS = 32_000
MAX_OUTPUT_TOKENS = 32000
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 480.0


class OrdinaryLayoutError(ValueError):
    def __init__(self, code: str, status: int = 422):
        self.code = code if code.startswith("ordinary_layout_") else "ordinary_layout_" + code
        self.status = self.status_code = status
        super().__init__(self.code)


def fail(code, status=422):
    raise OrdinaryLayoutError(code, status) from None


def identifier(value):
    if type(value) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value) is None:
        fail("invalid_id")
    return value


def nonce(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        fail("invalid_nonce")
    return value


def generation(value, *, zero=False):
    if type(value) is not int or not (0 if zero else 1) <= value <= 10000:
        fail("invalid_generation")
    return value


def encode(value):
    try:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                         separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        fail("invalid_record")
    if len(raw) > 8 * 1024 * 1024:
        fail("record_too_large", 413)
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                fail("invalid_record")
            result[key] = value
        return result
    try:
        return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: fail("invalid_record"))
    except (ValueError, TypeError, UnicodeError, RecursionError):
        fail("invalid_record")


@dataclass(frozen=True)
class OrdinaryLayoutJob:
    """Only a trusted server resolver constructs this value; never hydrate HTTP data."""
    job_id: str
    mode: str
    workspace_id: str
    run_id: str
    source_pdf: bytes
    reviewed_docx: bytes
    original_docx: bytes
    target_lang: str
    selected_pages: tuple[int, ...]
    binding: Mapping[str, Any]
    page_groups: Mapping[int, tuple[str, ...]] = field(default_factory=dict)
    mapping_docx_sha256: str = ""


@dataclass(frozen=True)
class DeliveryArtifact:
    job_id: str
    run_id: str
    path: Path
    sha256: str
    word_count: int
    target_lang: str
    source_sha256: str
    generation: int
    selection_id: str
    kind: str
    frozen: bool


@dataclass(frozen=True)
class LayoutSuggestionPolicy:
    """Caller-approved quote; actual accountant bounds must fit this ceiling."""
    model: str
    max_page_cost_usd: str
    max_operation_cost_usd: str
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    timeout_seconds: float = REQUEST_TIMEOUT_SECONDS
    effort: str = "high"

    def public(self):
        try:
            amounts = [Decimal(self.max_page_cost_usd), Decimal(self.max_operation_cost_usd)]
            if any(not x.is_finite() or x <= 0 for x in amounts):
                raise ValueError
        except (ValueError, InvalidOperation, TypeError):
            fail("paid_policy_unavailable", 503)
        if (type(self.model) is not str or not self.model or self.effort not in {"low", "medium", "high"}
                or type(self.max_output_tokens) is not int or not 1 <= self.max_output_tokens <= MAX_OUTPUT_TOKENS
                or type(self.timeout_seconds) not in {float, int} or not 5 <= self.timeout_seconds <= REQUEST_TIMEOUT_SECONDS):
            fail("paid_policy_unavailable", 503)
        return {"model": self.model, "max_page_cost_usd": str(amounts[0]),
                "max_operation_cost_usd": str(amounts[1]), "max_output_tokens": self.max_output_tokens,
                "timeout_seconds": self.timeout_seconds, "effort": self.effort}


def job_identity(job, mode, workspace_id):
    if type(job) is not OrdinaryLayoutJob or job.mode != mode or job.workspace_id != workspace_id:
        fail("job_owner_mismatch", 409)
    identifier(job.job_id)
    identifier(job.run_id)
    if job.target_lang not in {"EN", "FR", "AR"}:
        fail("invalid_language")
    for raw, maximum in ((job.source_pdf, 64 * 1024 * 1024), (job.reviewed_docx, 32 * 1024 * 1024),
                         (job.original_docx, 32 * 1024 * 1024)):
        if type(raw) is not bytes or not 0 < len(raw) <= maximum:
            fail("invalid_job_bytes")
    pages = job.selected_pages
    if (type(pages) is not tuple or not pages or len(pages) > 100
            or any(type(n) is not int or not 1 <= n <= 100 for n in pages)
            or tuple(sorted(set(pages))) != pages):
        fail("invalid_page_selection")
    if not isinstance(job.binding, Mapping) or not job.binding:
        fail("missing_job_binding")
    return {"job_id": job.job_id, "run_id": job.run_id, "mode": mode, "workspace_id": workspace_id,
            "source_sha256": digest(job.source_pdf), "reviewed_sha256": digest(job.reviewed_docx),
            "original_sha256": digest(job.original_docx), "target_lang": job.target_lang,
            "selected_pages": list(pages), "binding": decode(encode(dict(job.binding)))}


def validated_groups(job, snapshot):
    if not job.page_groups:
        return {}
    if job.mapping_docx_sha256 != digest(job.reviewed_docx):
        fail("page_mapping_stale", 409)
    rows = snapshot["paragraphs"]
    groups = {}
    for page, ids in job.page_groups.items():
        if type(page) is not int or page not in job.selected_pages or type(ids) not in {list, tuple} or not ids:
            fail("invalid_page_mapping")
        groups[page] = list(ids)
    if [pid for page in sorted(groups) for pid in groups[page]] != [row["id"] for row in rows]:
        fail("page_mapping_coverage")
    return groups


def page_ids(view, page_number):
    """Use current reviewed/seeded associations, never guess from paragraph counts."""
    ids = []
    for row in view["decisions"]["paragraphs"]:
        numbers = {r["page_number"] for r in row["regions"]}
        if numbers == {page_number}:
            ids.append(row["paragraph_id"])
        elif page_number in numbers:
            fail("ambiguous_page_mapping", 409)
    all_ids = [r["id"] for r in view["paragraphs"]]
    if not ids or all_ids[all_ids.index(ids[0]):all_ids.index(ids[-1]) + 1] != ids:
        fail("page_mapping_required", 409)
    if len(ids) > MAX_PAGE_PARAGRAPHS:
        fail("proposal_page_too_large", 413)
    texts = [r["text"] for r in view["paragraphs"] if r["id"] in ids]
    if sum(len(t) for t in texts) > MAX_PAGE_CODEPOINTS:
        fail("proposal_page_too_large", 413)
    return ids


def _object(properties):
    return {"type": "object", "additionalProperties": False, "properties": properties, "required": list(properties)}


def proposal_schema(page_number, ids, *, version=PROPOSAL_VERSION_V3):
    pid = {"type": "string", "enum": list(ids)}
    boolean = {"type": "boolean"}
    nullable_spacing = {"type": ["number", "null"], "minimum": 0, "maximum": 72}
    group = _object({"paragraph_ids": {"type": "array", "items": pid,
        "minItems": 1, "maxItems": len(ids)}, "panel": boolean})
    groups = {"type": "array", "items": group, "minItems": 1, "maxItems": len(ids)}
    flow = _object({"kind": {"type": "string", "enum": ["flow"]}, "groups": groups})
    columns = _object({"kind": {"type": "string", "enum": ["columns"]},
        "widths_pct": {"type": "array", "items": {"type": "number", "minimum": 10, "maximum": 90},
            "minItems": 2, "maxItems": 3}, "gutter_pt": {"type": "number", "minimum": 0, "maximum": 36},
        "cells": {"type": "array", "items": _object({"groups": groups}), "minItems": 2, "maxItems": 3}})
    presentation = {"paragraph_id": pid, "bbox": {"type": ["array", "null"],
            "items": {"type": "number", "minimum": 0, "maximum": 1}, "minItems": 4, "maxItems": 4},
        "alignment": {"type": "string", "enum": ["inherit", "left", "right", "center", "justify"]},
        "space_before_pt": nullable_spacing, "space_after_pt": nullable_spacing,
        "bold": boolean, "italic": boolean, "underline": boolean,
        "emphasis": {"type": "array", "maxItems": 1000,
            "items": _object({"start": {"type": "integer", "minimum": 0}, "end": {"type": "integer", "minimum": 1},
                "bold": boolean, "italic": boolean, "underline": boolean})}}
    # Match the writer's role-dependent heading contract at generation time.
    # Semantic coverage, physical column pairing and safe phrase cuts remain local checks.
    choice = {"anyOf": [
        _object({**presentation, "role": {"type": "string", "enum": ["heading"]},
            "heading_level": {"type": "integer", "enum": [1, 2, 3]},
            "heading_size_pt": {"type": ["number", "null"], "minimum": 1, "maximum": 24}}),
        _object({**presentation, "role": {"type": "string",
                "enum": ["institution", "reference", "recipient", "body", "list", "signature", "source_folio"]},
            "heading_level": {"type": "integer", "enum": [0]}, "heading_size_pt": {"type": "null"}})]}
    response = {"type": "json_schema", "strict": True, "name": "ordinary_source_layout_v2", "schema": _object({
        "version": {"type": "string", "enum": [PROPOSAL_VERSION_V2]}, "page_number": {"type": "integer", "enum": [page_number]},
        "paragraphs": {"type": "array", "items": choice, "minItems": len(ids), "maxItems": len(ids)},
        "bands": {"type": "array", "items": {"anyOf": [flow, columns]}, "minItems": 1, "maxItems": len(ids)},
        "paragraph_partitions": {"type": "array", "maxItems": len(ids), "items": _object({
            "paragraph_id": pid, "split_before": {"type": "array", "minItems": 1, "maxItems": 7,
                "items": {"type": "string", "minLength": 1, "maxLength": 160}}})}})}

    if version == PROPOSAL_VERSION_V3:
        box = {"type": "array", "minItems": 4, "maxItems": 4,
               "items": {"type": "number", "minimum": 0, "maximum": 1}}
        fields = response["schema"]["properties"]
        fields["version"]["enum"] = [PROPOSAL_VERSION_V3]
        fields["source_coverage_findings"] = {"type": "array", "maxItems": 32, "items": _object({
            "kind": {"type": "string", "enum": ["missing_readable_literal"]},
            "literal": {"type": "string", "minLength": 1, "maxLength": 160},
            "source_bbox": box, "insertion_context": _object({"paragraph_id": pid,
                "position": {"type": "string", "enum": ["before", "after", "within"]}})})}
        fields["source_layout_evidence"] = {"type": "array", "maxItems": len(ids), "items": _object({
            "kind": {"type": "string", "enum": ["decorative_rule", "source_footer"]},
            "paragraph_ids": {"type": "array", "minItems": 1, "maxItems": len(ids), "items": pid},
            "bbox": box})}
        response["schema"]["required"] += ["source_coverage_findings", "source_layout_evidence"]
        response["name"] = "ordinary_source_layout_v3"
    elif version != PROPOSAL_VERSION_V2:
        fail("invalid_proposal_version")
    return response


def proposal_source_evidence(snapshot, view, proposal):
    """Provider evidence is a proposal for explicit review, never a transcription certificate."""
    if proposal.get("version") != PROPOSAL_VERSION_V3:
        return {"version": "ordinary_source_evidence_v1", "findings": [], "layout": []}
    page = proposal.get("page_number")
    ids = page_ids(view, page)
    def box(value):
        if (type(value) is not list or len(value) != 4 or
                any(type(v) not in {int, float} or not 0 <= v <= 1 for v in value) or
                value[0] >= value[2] or value[1] >= value[3]):
            fail("invalid_source_evidence_box")
    findings = proposal.get("source_coverage_findings")
    evidence = proposal.get("source_layout_evidence")
    if type(findings) is not list or len(findings) > 32 or type(evidence) is not list or len(evidence) > len(ids):
        fail("invalid_source_evidence")
    normalized = []
    for index, row in enumerate(findings):
        if type(row) is not dict or set(row) != {"kind", "literal", "source_bbox", "insertion_context"}:
            fail("invalid_source_finding")
        literal = row["literal"]
        context = row["insertion_context"]
        if (row["kind"] != "missing_readable_literal" or type(literal) is not str or
                not 1 <= len(literal) <= 160 or not literal.strip() or
                any(unicodedata.category(c).startswith("C") for c in literal) or
                type(context) is not dict or set(context) != {"paragraph_id", "position"} or
                type(context["paragraph_id"]) is not str or context["paragraph_id"] not in ids or
                context["position"] not in {"before", "after", "within"}):
            fail("invalid_source_finding")
        box(row["source_bbox"])
        normalized.append({**deepcopy(row), "finding_id": digest(encode([page, index, row])),
                           "page_number": page, "review_status": "unresolved"})
    baseline = {row["id"]: row for row in snapshot["paragraphs"]}
    choices = {}
    for row in proposal.get("paragraphs", []):
        if type(row) is not dict or type(row.get("paragraph_id")) is not str or row["paragraph_id"] not in ids:
            fail("invalid_source_layout_evidence")
        choices[row["paragraph_id"]] = row
    if set(choices) != set(ids):
        fail("invalid_source_layout_evidence")
    panel_ids, column_ids = set(), set()
    for band in proposal.get("bands", []):
        if type(band) is not dict:
            fail("invalid_source_layout_evidence")
        if band.get("kind") == "flow":
            groups = band.get("groups")
        elif band.get("kind") == "columns" and type(band.get("cells")) is list:
            groups = []
            for cell in band["cells"]:
                if type(cell) is not dict or type(cell.get("groups")) is not list:
                    fail("invalid_source_layout_evidence")
                groups.extend(cell["groups"])
                for group in cell["groups"]:
                    if type(group) is not dict or type(group.get("paragraph_ids")) is not list or any(type(pid) is not str for pid in group["paragraph_ids"]):fail("invalid_source_layout_evidence")
                    column_ids.update(group["paragraph_ids"])
        else:
            fail("invalid_source_layout_evidence")
        if type(groups) is not list:
            fail("invalid_source_layout_evidence")
        for group in groups:
            if type(group) is not dict or type(group.get("paragraph_ids")) is not list or any(type(pid) is not str for pid in group["paragraph_ids"]):
                fail("invalid_source_layout_evidence")
            if group.get("panel"):
                panel_ids.update(group["paragraph_ids"])
    partition_rows = proposal.get("paragraph_partitions", [])
    if type(partition_rows) is not list or any(type(row) is not dict or type(row.get("paragraph_id")) is not str for row in partition_rows):
        fail("invalid_source_layout_evidence")
    partitions = {row["paragraph_id"] for row in partition_rows}
    used = set()
    accepted, rejected = [], []
    for evidence_index, row in enumerate(evidence):
        if type(row) is not dict or set(row) != {"kind", "paragraph_ids", "bbox"}:
            fail("invalid_source_layout_evidence")
        box(row["bbox"])
        owned = row["paragraph_ids"]
        if (type(owned) is not list or not owned or any(type(pid) is not str or pid not in ids for pid in owned) or
                len(set(owned)) != len(owned) or used.intersection(owned)):
            fail("invalid_source_layout_evidence")
        used.update(owned)
        indices = [ids.index(pid) for pid in owned]
        if indices != list(range(indices[0], indices[0] + len(indices))):
            fail("invalid_source_layout_evidence")
        for pid in owned:
            raw = baseline[pid]
            if any(t["kind"] == "page_break" for t in raw["tokens"][:-1]):
                fail("invalid_source_layout_evidence")
            if raw.get("has_page_break") and (row["kind"] != "source_footer" or pid != owned[-1] or not raw["tokens"] or raw["tokens"][-1]["kind"] != "page_break"):
                fail("invalid_source_layout_evidence")
            if (pid in partitions or pid in panel_ids or raw.get("has_numbering") or "numPr" in raw.get("ppr_xml", "") or raw.get("has_field") or
                    any(t["kind"] != "t" and not (row["kind"] == "source_footer" and t["kind"] == "page_break") for t in raw["tokens"])):
                fail("invalid_source_layout_evidence")
        if row["kind"] == "decorative_rule":
            text = "".join(t["text"] for t in baseline[owned[0]]["tokens"] if t["kind"] == "t")
            if (len(owned) != 1 or choices[owned[0]]["role"] != "body" or
                    re.fullmatch(r"[_─━—–-]{3,}", text.strip()) is None or row["bbox"][3] - row["bbox"][1] > .03):
                fail("invalid_decorative_rule_evidence")
            if owned[0] in column_ids:
                rejected.append({"index": evidence_index, "kind": row["kind"],
                    "paragraph_ids": deepcopy(owned), "reason": "decorative_rule_requires_plain_flow"})
                continue
        elif row["kind"] == "source_footer":
            if any(pid in column_ids for pid in owned):
                fail("invalid_source_layout_evidence")
            if (indices[-1] != len(ids)-1 or row["bbox"][1] < .85 or
                    any(not "".join(t["text"] for t in baseline[pid]["tokens"] if t["kind"] == "t").strip() for pid in owned) or
                    any(choices[pid]["role"] not in {"body", "source_folio"} for pid in owned)):
                fail("invalid_source_footer_evidence")
        else:
            fail("invalid_source_layout_evidence")
        accepted.append(deepcopy(row))
    return {"version": "ordinary_source_evidence_v1", "page_number": page,
            "findings": normalized, "layout": accepted, "source_coverage_verified": False,
            **({"normalization": {"version": "ordinary_optional_layout_hint_normalization_v1",
                 "canonical_proposal_sha256": digest(encode(proposal)), "rejected_hints": rejected,
                 "review_required": True}} if rejected else {})}



def source_evidence_review_fields(records):
    """Current review warning, absent for historical or fully supported evidence."""
    rejected = [{"page_number": page["page_number"], **row}
                for page in records
                if page.get("normalization", {}).get("version") == "ordinary_optional_layout_hint_normalization_v1"
                for row in page["normalization"]["rejected_hints"]]
    return ({"source_layout_review_required": True, "source_layout_rejected_hints": rejected}
            if rejected else {})


def _ids(band):
    groups = band["groups"] if band["kind"] == "flow" else [g for c in band["cells"] for g in c["groups"]]
    return [i for g in groups for i in g["paragraph_ids"]]


def _resolve_partition_anchors(proposal, snapshot, ids):
    """Convert unique literal starts; the saved model validates cut semantics."""
    partitions = proposal.get("paragraph_partitions", [])
    if type(partitions) is not list or len(partitions) > len(ids):
        fail("invalid_proposal_partitions")
    rows = {row["id"]: row for row in snapshot["paragraphs"]}
    resolved, seen = [], []
    for item in partitions:
        if type(item) is not dict or set(item) != {"paragraph_id", "split_before"}:
            fail("invalid_proposal_partitions")
        pid, anchors = item["paragraph_id"], item["split_before"]
        if (type(pid) is not str or pid not in ids or pid in seen
                or type(anchors) is not list or not 1 <= len(anchors) <= 7
                or any(type(anchor) is not str or not 1 <= len(anchor) <= 160
                       or not anchor.strip() for anchor in anchors)):
            fail("invalid_proposal_partitions")
        text = rows[pid]["text"]
        offsets = []
        for anchor in anchors:
            offset = text.find(anchor)
            if offset < 0 or text.find(anchor, offset + 1) >= 0:
                fail("proposal_partition_anchor_ambiguous")
            offsets.append(offset)
        if offsets != sorted(set(offsets)):
            fail("proposal_partition_anchor_order")
        seen.append(pid)
        resolved.append({"paragraph_id": pid, "offsets": offsets})
    if seen != [pid for pid in ids if pid in seen]:
        fail("proposal_partition_parent_order")
    if len(ids) + sum(len(item["offsets"]) for item in resolved) > MAX_PAGE_PARAGRAPHS:
        fail("proposal_partition_page_too_large", 413)
    return resolved


def _canonical_flow_groups(bands, ids):
    """Restore only complete whole plain-flow intervals to immutable raw order."""
    if (type(bands) is not list or len(bands) != 1 or type(bands[0]) is not dict
            or bands[0].get("kind") != "flow"):
        return bands
    groups = bands[0].get("groups")
    if type(groups) is not list or not groups:
        return bands
    ordinal = {pid: index for index, pid in enumerate(ids)}
    intervals = []
    for group in groups:
        if type(group) is not dict or group.get("panel") is not False:
            return bands
        owned = group.get("paragraph_ids")
        if type(owned) is not list or not owned or any(type(pid) is not str or pid not in ordinal for pid in owned):
            return bands
        positions = [ordinal[pid] for pid in owned]
        if positions != list(range(positions[0], positions[0] + len(positions))):
            return bands
        intervals.append((positions[0], group))
    flattened = [pid for group in groups for pid in group["paragraph_ids"]]
    if len(flattened) != len(ids) or len(set(flattened)) != len(ids) or set(flattened) != set(ids):
        return bands
    if flattened == ids:
        return bands
    result = deepcopy(bands)
    result[0]["groups"] = [deepcopy(group) for _, group in sorted(intervals, key=lambda item: item[0])]
    return result


def _canonical_columns_rows(bands, ids, choices):
    """Separate source rows only when whole existing column groups prove order."""
    try:
        flattened = [pid for band in bands for pid in _ids(band)]
    except (TypeError, KeyError):
        return bands
    if flattened == ids:
        return bands
    if (any(type(pid) is not str for pid in flattened)
            or len(flattened) != len(ids) or len(set(flattened)) != len(ids)
            or set(flattened) != set(ids)):
        return bands
    ordinal = {pid: index for index, pid in enumerate(ids)}
    boxes = {choice["paragraph_id"]: choice["bbox"] for choice in choices}
    result = []
    for band in bands:
        owned = _ids(band)
        if band.get("kind") != "columns" or owned == sorted(owned, key=ordinal.get):
            result.append(band)
            continue
        cells = band.get("cells")
        if type(cells) is not list or len(cells) not in {2, 3}:
            return bands
        if any(type(cell) is not dict or type(cell.get("groups")) is not list for cell in cells):
            return bands
        count = len(cells[0]["groups"])
        if count < 2 or any(len(cell["groups"]) != count for cell in cells):
            return bands
        for cell in cells:
            for group in cell["groups"]:
                if (type(group) is not dict or type(group.get("panel")) is not bool
                        or type(group.get("paragraph_ids")) is not list or not group["paragraph_ids"]):
                    return bands
                positions = [ordinal[pid] for pid in group["paragraph_ids"]]
                if positions != list(range(positions[0], positions[0] + len(positions))):
                    return bands
        start, end = min(ordinal[pid] for pid in owned), max(ordinal[pid] for pid in owned) + 1
        row_order = [pid for row in range(count) for cell in cells
                     for pid in cell["groups"][row]["paragraph_ids"]]
        if row_order != ids[start:end]:
            return bands
        previous_bottom = None
        for row in range(count):
            row_ids = [pid for cell in cells for pid in cell["groups"][row]["paragraph_ids"]]
            row_boxes = [boxes[pid] for pid in row_ids]
            if any(type(box) is not list or len(box) != 4
                    or any(type(v) not in {int, float} or not 0 <= v <= 1 for v in box)
                    or box[0] >= box[2] or box[1] >= box[3] for box in row_boxes):
                return bands
            top, bottom = min(box[1] for box in row_boxes), max(box[3] for box in row_boxes)
            if previous_bottom is not None and previous_bottom > top:
                return bands
            previous_bottom = bottom
        for row in range(count):
            split = deepcopy(band)
            for cell in split["cells"]:
                cell["groups"] = [cell["groups"][row]]
            result.append(split)
    return result if [pid for band in result for pid in _ids(band)] == ids else bands


def _generated_emphasis(row, spans):
    """Drop only optional word-interior endpoints; never repair unsafe literals."""
    from .saved_docx_layout import _phrase_edge, _emphasis_end_edge, _protected_ranges
    if type(spans) is not list or len(spans) > 1000:
        fail("invalid_proposal_decisions")
    if not spans:
        return []
    previous = 0
    for span in spans:
        if (type(span) is not dict or set(span) != {"start", "end", "bold", "italic", "underline"}
                or type(span["start"]) is not int or type(span["end"]) is not int
                or not previous <= span["start"] < span["end"] <= len(row["text"])
                or any(type(span[k]) is not bool for k in ("bold", "italic", "underline"))
                or not any(span[k] for k in ("bold", "italic", "underline"))):
            fail("invalid_proposal_decisions")
        previous = span["end"]
    try:
        ranges = _protected_ranges(row)
    except ValueError:
        fail("invalid_proposal_decisions")
    retained = []
    def word_interior(offset):
        return (0 < offset < len(row["text"])
                and all(unicodedata.category(char)[0] in {"L", "M", "N"}
                        for char in row["text"][offset - 1:offset + 1]))
    for span in spans:
        start, end = span["start"], span["end"]
        if (any(a < cut < b for a, b in ranges for cut in (start, end))
                or any(token["kind"] != "t" and start < token["end"] and end > token["start"] for token in row["tokens"])):
            fail("invalid_proposal_decisions")
        valid_start, valid_end = _phrase_edge(row["text"], start), _emphasis_end_edge(row["text"], end)
        if (not valid_start and not word_interior(start)) or (not valid_end and not word_interior(end)):
            fail("invalid_proposal_decisions")
        if valid_start and valid_end:
            retained.append(deepcopy(span))
    return retained


def normalize_proposals(snapshot, view, proposals):
    decisions = deepcopy(view["decisions"])
    by_id = {row["paragraph_id"]: index for index, row in enumerate(decisions["paragraphs"])}
    replacements, id_page = {}, {}
    partitions = deepcopy(decisions.get("paragraph_partitions", []))
    for proposal in proposals:
        if type(proposal) is not dict:
            fail("invalid_proposal")
        expected_keys = {"version", "page_number", "paragraphs", "bands"}
        if proposal.get("version") in {PROPOSAL_VERSION_V2, PROPOSAL_VERSION_V3}:
            expected_keys.add("paragraph_partitions")
        if proposal.get("version") == PROPOSAL_VERSION_V3:
            expected_keys.update({"source_coverage_findings", "source_layout_evidence"})
        if set(proposal) != expected_keys:
            fail("invalid_proposal")
        page = proposal["page_number"]
        if proposal["version"] not in {PROPOSAL_VERSION, PROPOSAL_VERSION_V2, PROPOSAL_VERSION_V3} or type(page) is not int or page in replacements:
            fail("invalid_proposal")
        ids = page_ids(view, page)
        if type(proposal["paragraphs"]) is not list or [p.get("paragraph_id") for p in proposal["paragraphs"] if type(p) is dict] != ids:
            fail("proposal_coverage")
        partitions = [item for item in partitions if item["paragraph_id"] not in ids]
        partitions.extend(_resolve_partition_anchors(proposal, snapshot, ids))
        frame = next((p for p in view["pages"] if p["page_number"] == page), None)
        if frame is None:
            fail("invalid_proposal_page")
        for choice in proposal["paragraphs"]:
            expected = set(decisions["paragraphs"][0]) - {"regions", "unmapped_reason"} | {"bbox"}
            if set(choice) != expected:
                fail("invalid_proposal")
            row = deepcopy(choice)
            box = row.pop("bbox")
            if box is not None and (type(box) is not list or len(box) != 4
                    or any(type(v) not in {int, float} or not 0 <= v <= 1 for v in box)):
                fail("invalid_proposal_box")
            # Finite, bounded coordinates may still describe no usable source area.
            # Keep the valid styles while making that association explicitly unmapped.
            unusable_box = box is not None and (box[0] >= box[2] or box[1] >= box[3])
            row["regions"] = [] if box is None or unusable_box else [{"page_number": page,
                "bbox_px": [v * (frame["width_px"] if i % 2 == 0 else frame["height_px"]) for i, v in enumerate(box)]}]
            row["unmapped_reason"] = (
                "Suggested source box is empty or reversed; operator source association is required."
                if unusable_box else "Source association requires operator review." if box is None else "")
            baseline = snapshot["paragraphs"][by_id[row["paragraph_id"]]]
            row["emphasis"] = _generated_emphasis(baseline, row["emphasis"])
            has_visible_text = any(token["kind"] == "t" and any(
                not char.isspace() and unicodedata.category(char)[0] in {"L", "N", "P", "S"}
                for char in token["text"]) for token in baseline["tokens"])
            # Real footer/folio text may share a paragraph with its terminal
            # page break. Its presentation uses the same bounded validator as
            # other text; only control-only sentinel rows must remain neutral.
            if baseline["has_page_break"] and not has_visible_text and any((row["role"] != "body", row["heading_level"] != 0,
                    row["bold"], row["italic"], row["underline"], row["emphasis"], row["alignment"] != "inherit",
                    not (row["space_before_pt"] is None or type(row["space_before_pt"]) in {int, float} and row["space_before_pt"] == 0),
                    not (row["space_after_pt"] is None or type(row["space_after_pt"]) in {int, float} and row["space_after_pt"] == 0))):
                fail("page_break_requires_flow")
            decisions["paragraphs"][by_id[row["paragraph_id"]]] = row
        bands = _canonical_flow_groups(proposal["bands"], ids)
        bands = _canonical_columns_rows(bands, ids, proposal["paragraphs"])
        try:
            if [pid for band in bands for pid in _ids(band)] != ids:
                fail("proposal_coverage")
        except (TypeError, KeyError):
            fail("invalid_proposal")
        proposal_source_evidence(snapshot, view, proposal)
        replacements[page] = deepcopy(bands)
        id_page.update({pid: page for pid in ids})
    bands, inserted = [], set()
    for band in decisions["bands"]:
        if band["kind"] == "columns":
            pages = {id_page.get(pid) for pid in _ids(band)}
            if len(pages) > 1 and pages != {None}:
                fail("proposal_crosses_existing_columns", 409)
            units = [(id_page.get(_ids(band)[0]), band)]
        else:
            units = []
            for group in band["groups"]:
                chunks = []
                for pid in group["paragraph_ids"]:
                    page = id_page.get(pid)
                    if chunks and chunks[-1][0] == page:
                        chunks[-1][1].append(pid)
                    else:
                        chunks.append((page, [pid]))
                units.extend((page, {"kind": "flow", "groups": [{"paragraph_ids": ids, "panel": group["panel"]}]})
                             for page, ids in chunks)
        for page, unit in units:
            if page is None:
                bands.append(unit)
            elif page not in inserted:
                bands.extend(replacements[page])
                inserted.add(page)
    decisions["bands"] = bands
    if partitions:
        from .saved_docx_layout import PARTITION_DECISIONS_VERSION
        order = {row["id"]: i for i, row in enumerate(snapshot["paragraphs"])}
        partitions.sort(key=lambda item: order[item["paragraph_id"]])
        decisions["version"] = PARTITION_DECISIONS_VERSION
        decisions["paragraph_partitions"] = partitions
    elif "paragraph_partitions" in decisions:
        from .saved_docx_layout import DECISIONS_VERSION
        decisions["version"] = DECISIONS_VERSION
        decisions.pop("paragraph_partitions")
    decisions["review"].update(document_reviewed=False, pages_reviewed=[], reviewer="", note="")
    try:
        return validate_decisions(snapshot, view["pages"], decisions)
    except ValueError:
        fail("invalid_proposal_decisions")
