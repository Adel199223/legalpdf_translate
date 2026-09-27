"""Pure, text-preserving contracts for ordinary-job layout proposals."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .saved_docx_layout import inspect_docx, validate_decisions

VERSION = "ordinary_layout_v1"
PROPOSAL_VERSION = "ordinary_layout_proposal_v1"
MAX_PAGE_PARAGRAPHS = 200
MAX_PAGE_CODEPOINTS = 32_000
MAX_OUTPUT_TOKENS = 8000
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUEST_TIMEOUT_SECONDS = 240.0


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


def proposal_schema(page_number, ids):
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
    return {"type": "json_schema", "strict": True, "name": "ordinary_source_layout_v1", "schema": _object({
        "version": {"type": "string", "enum": [PROPOSAL_VERSION]}, "page_number": {"type": "integer", "enum": [page_number]},
        "paragraphs": {"type": "array", "items": choice, "minItems": len(ids), "maxItems": len(ids)},
        "bands": {"type": "array", "items": {"anyOf": [flow, columns]}, "minItems": 1, "maxItems": len(ids)}})}


def _ids(band):
    groups = band["groups"] if band["kind"] == "flow" else [g for c in band["cells"] for g in c["groups"]]
    return [i for g in groups for i in g["paragraph_ids"]]


def normalize_proposals(snapshot, view, proposals):
    decisions = deepcopy(view["decisions"])
    by_id = {row["paragraph_id"]: index for index, row in enumerate(decisions["paragraphs"])}
    replacements, id_page = {}, {}
    for proposal in proposals:
        if type(proposal) is not dict or set(proposal) != {"version", "page_number", "paragraphs", "bands"}:
            fail("invalid_proposal")
        page = proposal["page_number"]
        if proposal["version"] != PROPOSAL_VERSION or type(page) is not int or page in replacements:
            fail("invalid_proposal")
        ids = page_ids(view, page)
        if type(proposal["paragraphs"]) is not list or [p.get("paragraph_id") for p in proposal["paragraphs"] if type(p) is dict] != ids:
            fail("proposal_coverage")
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
            if baseline["has_page_break"] and any((row["role"] != "body", row["heading_level"] != 0,
                    row["bold"], row["italic"], row["underline"], row["emphasis"], row["alignment"] != "inherit",
                    row["space_before_pt"] is not None, row["space_after_pt"] is not None)):
                fail("page_break_requires_flow")
            decisions["paragraphs"][by_id[row["paragraph_id"]]] = row
        bands = proposal["bands"]
        try:
            if [pid for band in bands for pid in _ids(band)] != ids:
                fail("proposal_coverage")
        except (TypeError, KeyError):
            fail("invalid_proposal")
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
    decisions["review"].update(document_reviewed=False, pages_reviewed=[], reviewer="", note="")
    try:
        return validate_decisions(snapshot, view["pages"], decisions)
    except ValueError:
        fail("invalid_proposal_decisions")
