"""Explicit visual decisions for ordinary operator-reviewed DOCX revisions.

Trusted backend code supplies saved config and the exact source context. Views
contain private source/target text for safe local rendering, never diagnostics.
All hashes, paths, IDs and evidence envelopes are generated here. Geometry and
rendered layout remain unverified; this is neither certification nor authority.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import re
import stat
import uuid

from PIL import Image

from .checkpoint import build_run_paths, load_run_state, settings_fingerprint
from .formatting_support import formatting_fingerprint
from .ordinary_reviewed_source import OrdinaryReviewedSourceContext
from .reviewed_formatting import (
    BOUNDARY_POLICY, CELL_BOUNDARY_POLICY, SOURCE_GAP_POLICY,
    FormattingPageInput, validate_reviewed_formatting,
)
from .reviewed_regions import RegionFragmentInput, validate_reviewed_regions
from .run_docx_formatting import (
    OPERATOR_REVIEW_PROFILE, begin_run_formatting_review, submit_run_formatting_review,
    prepare_run_docx_formatting, build_run_reviewed_docx,
)
from .run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
from .types import RunConfig

VERSION = "ordinary_visual_formatting_review_v1"
_MAX_JSON = 8 * 1024 * 1024
_MAX_DRAFT = 64 * 1024 * 1024
_MAX_GENERATIONS = 1000
_MAX_FRAGMENTS = 5000


class FormattingReviewServiceError(ValueError):
    """Only content-free categories cross the public service boundary."""


def _fail(code):
    raise FormattingReviewServiceError("formatting_review_" + code) from None


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    if not 0 < len(raw) <= _MAX_JSON:
        _fail("record_too_large")
    return raw


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("invalid_record")
            result[key] = value
        return result
    def constant(_value):
        _fail("invalid_record")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def _id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        _fail("invalid_id")
    return value


def _direct(value, *, directory=False):
    path = Path(value).expanduser().absolute()
    if ".." in path.parts:
        _fail("invalid_path")
    for item in (path, *path.parents):
        info = item.lstat()
        if (item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400
                or (item != path or directory) and not stat.S_ISDIR(info.st_mode)):
            _fail("indirect_path")
    if not directory:
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_nlink", 1) != 1:
            _fail("indirect_path")
    return path.resolve(strict=True)


def _read(path):
    path = _direct(path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > _MAX_JSON:
            _fail("record_too_large")
        raw = stream.read(_MAX_JSON + 1)
        after = os.fstat(stream.fileno())
    if (before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns
            or len(raw) != before.st_size or len(raw) > _MAX_JSON
            or (before.st_dev, before.st_ino) != (path.stat().st_dev, path.stat().st_ino)):
        _fail("record_changed")
    return raw


def _mkdir(path):
    _direct(path.parent, directory=True)
    path.mkdir(exist_ok=True)
    return _direct(path, directory=True)


def _write(path, value):
    raw = _json(value)
    _direct(path.parent, directory=True)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if _read(path) != raw:
        _fail("publication_changed")
    return raw


def _text(value):
    if type(value) is not str or not value.strip() or len(value) > 1000:
        _fail("invalid_review_note")
    value.encode("utf-8")
    return value


def _sequence(value, maximum=_MAX_FRAGMENTS):
    if type(value) is not tuple or len(value) > maximum:
        _fail("invalid_decision")
    return value


@dataclass(frozen=True, slots=True)
class FormattingFragment:
    parent_number: int
    source_range: tuple[int, int]
    target_range: tuple[int, int]
    bbox_px: tuple[float, float, float, float]
    role: str
    alignment: str
    bold: bool
    italic: bool
    review_note: str


@dataclass(frozen=True, slots=True)
class FormattingParagraph:
    fragment_number: int


@dataclass(frozen=True, slots=True)
class FormattingTable:
    column_widths: tuple[int, ...]
    rows: tuple[tuple[tuple[int, ...], ...], ...]
    column_gaps_px: tuple[float, ...] | None = None


@dataclass(frozen=True, slots=True)
class FormattingPageDecision:
    fragments: tuple[FormattingFragment, ...]
    header: tuple[int, ...]
    body: tuple[FormattingParagraph | FormattingTable, ...]
    footer: tuple[int, ...]
    folio_fragment_number: int | None
    full_page_review_completed: bool
    source_target_mapping_reviewed: bool
    reviewer: str
    review_note: str


@dataclass(frozen=True, slots=True)
class FormattingDocumentGroup:
    start_page: int
    end_page: int


@dataclass(frozen=True, slots=True)
class FormattingDocumentDecision:
    groups: tuple[FormattingDocumentGroup, ...]
    all_pages_reviewed: bool
    allow_pipe_cell_boundaries: bool
    preserve_source_gaps: bool
    reviewer: str
    review_note: str


def _page_decision_dict(decision):
    """Keep existing v1 serialized decisions exact when gutters are absent."""
    value = asdict(decision)
    for row in value["body"]:
        if "column_gaps_px" in row and row["column_gaps_px"] is None:
            del row["column_gaps_px"]
    return value


def _typed_page(value):
    """Decode only our exact typed decision schema; never accept a manifest."""
    fragments = tuple(FormattingFragment(**{**row, "source_range": tuple(row["source_range"]),
        "target_range": tuple(row["target_range"]), "bbox_px": tuple(row["bbox_px"])}) for row in value["fragments"])
    body = tuple(FormattingParagraph(**row) if set(row) == {"fragment_number"}
        else FormattingTable(**{**row, "column_widths": tuple(row["column_widths"]),
            "rows": tuple(tuple(tuple(cell) for cell in cells) for cells in row["rows"]),
            "column_gaps_px": tuple(row["column_gaps_px"]) if "column_gaps_px" in row else None}) for row in value["body"])
    decision = FormattingPageDecision(**{**value, "fragments": fragments,
        "header": tuple(value["header"]), "body": body, "footer": tuple(value["footer"])})
    if _json(_page_decision_dict(decision)) != _json(value):
        _fail("decision_changed")
    return decision


def _typed_document(value):
    decision = FormattingDocumentDecision(**{**value,
        "groups": tuple(FormattingDocumentGroup(**row) for row in value["groups"])})
    if _json(asdict(decision)) != _json(value):
        _fail("decision_changed")
    return decision


class OrdinaryFormattingReviewService:
    """One completed run and explicitly selected original source revision.

    Callers must resolve config/context through trusted mode/workspace ownership.
    No operation takes a caller path, evidence hash, manifest, or target text edit.
    Separate image bytes are intentionally excluded from JSON views.
    """

    def __init__(self, config: RunConfig, source_context: OrdinaryReviewedSourceContext, *,
                 page_matched_derivative: bool = False):
        try:
            if type(config) is not RunConfig or type(source_context) is not OrdinaryReviewedSourceContext:
                _fail("saved_config_and_context_required")
            if type(config.page_breaks) is not bool or type(config.strip_bidi_controls) is not bool:
                _fail("invalid_saved_settings")
            if type(page_matched_derivative) is not bool:
                _fail("invalid_derivative_choice")
            self._config = replace(deepcopy(config), pdf_path=_direct(config.pdf_path),
                                   output_dir=_direct(config.output_dir, directory=True))
            self._context = source_context
            self._render_config = replace(self._config, page_breaks=True) if page_matched_derivative else self._config
            self.run_dir = build_run_paths(self._config.output_dir, self._config.pdf_path,
                self._config.target_lang, gmail_batch_context=self._config.gmail_batch_context).run_dir
            self._root = self.run_dir / "visual_formatting_reviews"
            self._owner = {"run_dir": str(self.run_dir), "source_path": str(self._config.pdf_path),
                "target_lang": self._config.target_lang.value, "source_context": source_context.identity,
                "settings": settings_fingerprint(self._config, ordinary_source_review=source_context.identity)}
            if page_matched_derivative:
                self._owner["formatting_derivative"] = {
                    "version": "explicit_source_page_matched_derivative_v1",
                    "original_page_breaks": self._config.page_breaks, "page_breaks": True,
                    "original_formatting_fingerprint": formatting_fingerprint(self._config),
                    "formatting_fingerprint": formatting_fingerprint(self._render_config)}
        except FormattingReviewServiceError:
            raise
        except Exception:
            _fail("invalid_saved_config")

    @contextmanager
    def _scope(self):
        try:
            with run_workspace_slot(self.run_dir):
                yield
        except FormattingReviewServiceError:
            raise
        except RunWorkspaceBusy:
            _fail("run_busy")
        except Exception:
            _fail("operation_failed")

    def _snapshot(self):
        checkpoint = self.run_dir / "run_state.json"
        raw = _read(checkpoint)
        state = load_run_state(checkpoint)
        if state is None or _read(checkpoint) != raw:
            _fail("checkpoint_changed")
        if (Path(state.run_dir_abs).resolve() != self.run_dir.resolve()
                or Path(state.pdf_path).resolve() != self._config.pdf_path
                or state.lang != self._owner["target_lang"] or state.settings != self._owner["settings"]):
            _fail("saved_owner_changed")
        notices = []
        if state.run_status == "running":
            _fail("run_busy")
        if (state.run_status != "completed" or not 1 <= state.total_pages <= 1000
                or sorted(state.pages) != sorted(str(n) for n in range(1, state.total_pages + 1))
                or any(row.get("status") != "done" for row in state.pages.values())):
            notices.append("reviewed_profile_unsupported_selection")
        if self._context.reviewer_kind != "operator_review":
            notices.append("reviewed_profile_unsupported_source_reviewer")
        if not self._render_config.page_breaks:
            notices.append("reviewed_profile_requires_page_breaks")
        if not self._config.strip_bidi_controls:
            notices.append("reviewed_profile_requires_bidi_stripping")
        if not state.protocol_identity or state.protocol_identity.get("protocol") != "legal_blocks_v2":
            notices.append("reviewed_profile_unsupported_protocol")
        if notices:
            return state, {"status": "declined", "notice_codes": notices}, {}
        acquisition = begin_run_formatting_review(self.run_dir, self._render_config, state,
            reviewer_kind="operator_review", review_profile=OPERATOR_REVIEW_PROFILE)
        if acquisition["notice_codes"]:
            return state, {"status": "declined", "notice_codes": acquisition["notice_codes"]}, {}
        artifacts = dict(self._context.evidence.artifacts)
        images, identities, sizes = {}, {}, {}
        for binding, parents in zip(acquisition["binding"]["pages"], acquisition["review_inputs"]):
            number = binding["page_number"]
            identity = binding["source_identity"]
            image = artifacts.get(identity["image_sha256"])
            if image is None or _sha(image) != identity["image_sha256"]:
                _fail("source_image_changed")
            images[number] = image
            identities[number] = identity
            source = parents["source_structure"]
            sizes[number] = (source["width_pt"], source["height_pt"])
        verified = self._context.verify(source_hash=acquisition["binding"]["physical_source"]["sha256"],
                                        page_identities=identities, page_sizes=sizes)
        for number, parents in enumerate(acquisition["review_inputs"], 1):
            if _json(verified[number]["source_structure"]) != _json(parents["source_structure"]):
                _fail("source_commit_changed")
        return state, acquisition, images

    def _folder(self, draft_id):
        _direct(self._root, directory=True)
        return _direct(self._root / "drafts" / _id(draft_id), directory=True)

    def _load(self, draft_id, *, editable=False):
        folder = self._folder(draft_id)
        parent_raw = _read(folder / "parents.json")
        parents = _decode(parent_raw)
        if (set(parents) != {"version", "draft_id", "owner", "acquisition"}
                or parents["version"] != VERSION or parents["draft_id"] != draft_id
                or _json(parents["owner"]) != _json(self._owner)):
            _fail("draft_owner_changed")
        if editable and (folder / "submitted.json").exists():
            _fail("draft_submitted")
        if editable and (folder / "submit_intent.json").exists():
            _fail("draft_submission_started")
        files = []
        for path in folder.glob("[0-9][0-9][0-9][0-9][0-9][0-9].json"):
            if len(files) >= _MAX_GENERATIONS:
                _fail("invalid_generation")
            files.append(path)
        files.sort()
        if not files:
            _fail("invalid_generation")
        previous, total, record = None, len(parent_raw), None
        for number, path in enumerate(files, 1):
            if path.name != f"{number:06d}.json":
                _fail("invalid_generation")
            # Enforce the aggregate bound before each bounded record read.
            if _direct(path).stat().st_size > _MAX_DRAFT - total:
                _fail("draft_too_large")
            raw = _read(path)
            total += len(raw)
            record = _decode(raw)
            if (set(record) != {"version", "draft_id", "generation", "parent_sha256", "previous_sha256",
                                "page_decisions", "document_decision"}
                    or record["version"] != VERSION or record["draft_id"] != draft_id
                    or record["generation"] != number or type(record["generation"]) is not int
                    or record["parent_sha256"] != _sha(parent_raw) or record["previous_sha256"] != previous
                    or type(record["page_decisions"]) is not list
                    or len(record["page_decisions"]) != len(parents["acquisition"]["review_inputs"])):
                _fail("generation_changed")
            previous = _sha(raw)
        return parents, record, previous, total

    def _fresh(self, parents):
        state, current, images = self._snapshot()
        if current["status"] == "declined":
            return state, current, images
        if _json(current) != _json(parents["acquisition"]):
            _fail("draft_inputs_changed")
        return state, current, images

    def _view(self, parents, record, images):
        pages = []
        for number, pair in enumerate(parents["acquisition"]["review_inputs"], 1):
            with Image.open(BytesIO(images[number])) as image:
                size = list(image.size)
            source, target = pair["source_structure"], pair["target_structure"]
            pages.append({"page_number": number, "image_size_px": size,
                "source_provenance": source["provenance"], "source_uncertain": source["uncertain"],
                "parents": [{"parent_number": index, "source_text": left["text"], "target_text": right["text"]}
                    for index, (left, right) in enumerate(zip(source["blocks"], target["blocks"]), 1)],
                "decision": None if record["page_decisions"][number - 1] is None else
                    deepcopy(record["page_decisions"][number - 1]["decision"])})
        return {**self._formatting_choice(), "status": "draft", "draft_id": record["draft_id"], "generation": record["generation"],
            "source_revision_id": self._context.revision_id, "review_profile": OPERATOR_REVIEW_PROFILE,
            "reviewer_kind": "operator_review", "offset_unit": "unicode_codepoint",
            "geometry_status": "not_verified", "rendered_layout_acceptance": "not_evaluated",
            "layout_review_required": True, "notice_codes": [], "pages": pages,
            "document_decision": deepcopy(record["document_decision"])}

    def _formatting_choice(self):
        return ({"formatting_derivative": deepcopy(self._owner["formatting_derivative"])}
                if "formatting_derivative" in self._owner else {})

    def prepare(self):
        with self._scope():
            _state, acquisition, images = self._snapshot()
            if acquisition["status"] == "declined":
                return acquisition
            draft_id = uuid.uuid4().hex
            _mkdir(self._root)
            _mkdir(self._root / "drafts")
            folder = self._root / "drafts" / draft_id
            folder.mkdir(exist_ok=False)
            parents = {"version": VERSION, "draft_id": draft_id, "owner": self._owner, "acquisition": acquisition}
            parent_raw = _write(folder / "parents.json", parents)
            record = {"version": VERSION, "draft_id": draft_id, "generation": 1,
                "parent_sha256": _sha(parent_raw), "previous_sha256": None,
                "page_decisions": [None] * len(acquisition["review_inputs"]), "document_decision": None}
            _write(folder / "000001.json", record)
            return self._view(parents, record, images)

    def read(self, draft_id):
        with self._scope():
            parents, record, digest, _ = self._load(draft_id)
            state, fresh, images = self._fresh(parents)
            if fresh["status"] == "declined":
                return fresh
            view = self._view(parents, record, images)
            intent_path = self._folder(draft_id) / "submit_intent.json"
            if intent_path.exists():
                intent = self._intent(_decode(_read(intent_path)), record, digest)
                prepared = self._find_publication(intent, state)
                if prepared is None:
                    if (self._folder(draft_id) / "submitted.json").exists():
                        _fail("submission_publication_changed")
                    return {**view, "status": "submission_pending"}
                self._finish_receipts(intent, prepared)
                return {**view, **self._revision_view(prepared, status="submitted")}
            return view

    def image(self, draft_id, *, page_number: int):
        with self._scope():
            parents, _, _, _ = self._load(draft_id)
            _, fresh, images = self._fresh(parents)
            if fresh["status"] == "declined":
                _fail("draft_no_longer_supported")
            if type(page_number) is not int or page_number not in images:
                _fail("invalid_page")
            return images[page_number]

    def _page(self, decision, pair, template, image):
        if type(decision) is not FormattingPageDecision:
            _fail("invalid_page_decision")
        for value in (decision.full_page_review_completed, decision.source_target_mapping_reviewed):
            if type(value) is not bool:
                _fail("invalid_page_decision")
        _text(decision.reviewer)
        _text(decision.review_note)
        fragments = _sequence(decision.fragments)
        source, target = pair["source_structure"], pair["target_structure"]
        number = template["page_number"]
        with Image.open(BytesIO(image)) as opened:
            if opened.format != "PNG" or opened.width * opened.height > 40_000_000:
                _fail("invalid_source_image")
            size = opened.size
            opened.verify()
        rows = []
        for index, fragment in enumerate(fragments, 1):
            if (type(fragment) is not FormattingFragment or type(fragment.parent_number) is not int
                    or not 1 <= fragment.parent_number <= len(source["blocks"])):
                _fail("invalid_fragment")
            left, right = source["blocks"][fragment.parent_number - 1], target["blocks"][fragment.parent_number - 1]
            for span, text in ((fragment.source_range, left["text"]), (fragment.target_range, right["text"])):
                if (len(_sequence(span, 2)) != 2 or any(type(n) is not int for n in span)
                        or not 0 <= span[0] < span[1] <= len(text)):
                    _fail("invalid_unicode_range")
            box = _sequence(fragment.bbox_px, 4)
            if (len(box) != 4 or any(type(n) not in (int, float) for n in box)
                    or not 0 <= box[0] < box[2] <= size[0] or not 0 <= box[1] < box[3] <= size[1]
                    or not all(math.isfinite(n) for n in box)):
                _fail("invalid_box")
            if (fragment.role not in {"header", "body", "signature", "footer", "folio"}
                    or fragment.alignment not in {"left", "right", "center", "justify"}
                    or type(fragment.bold) is not bool or type(fragment.italic) is not bool):
                _fail("invalid_style")
            rows.append({"rendering_id": f"p{number:04d}_f{index:04d}", "parent_block_id": left["id"],
                "source_range": list(fragment.source_range), "target_range": list(fragment.target_range),
                "source_text_sha256": _sha(left["text"][slice(*fragment.source_range)].encode()),
                "target_text_sha256": _sha(right["text"][slice(*fragment.target_range)].encode()),
                "bbox_px": list(box), "role": fragment.role, "alignment": fragment.alignment,
                "bold": fragment.bold, "italic": fragment.italic, "review_note": _text(fragment.review_note)})
        def reference(value):
            if type(value) is not int or not 1 <= value <= len(rows):
                _fail("invalid_fragment_owner")
            return rows[value - 1]["rendering_id"]
        header = [reference(n) for n in _sequence(decision.header)]
        footer = [reference(n) for n in _sequence(decision.footer)]
        body, table_number = [], 0
        gutters = any(type(block) is FormattingTable and block.column_gaps_px is not None
                      for block in _sequence(decision.body))
        for block in _sequence(decision.body):
            if type(block) is FormattingParagraph:
                body.append({"kind": "paragraph", "fragment_id": reference(block.fragment_number)})
            elif type(block) is FormattingTable:
                table_number += 1
                widths = _sequence(block.column_widths, 4)
                if not widths or any(type(w) is not int or not 1 <= w <= 100 for w in widths) or sum(widths) != 100:
                    _fail("invalid_table_widths")
                table_rows = []
                for row in _sequence(block.rows, 100):
                    if len(_sequence(row, 4)) != len(widths):
                        _fail("invalid_table_row")
                    table_rows.append({"cells": [{"fragment_ids": [reference(n) for n in _sequence(cell)]} for cell in row]})
                body.append({"kind": "table", "table_id": f"p{number:04d}_t{table_number:04d}",
                             "column_widths": list(widths), "rows": table_rows})
                if gutters:
                    if block.column_gaps_px is None:
                        _fail("explicit_table_gaps_required")
                    gaps = _sequence(block.column_gaps_px, 3)
                    if (len(gaps) != len(widths) - 1 or any(type(g) not in (int, float)
                            or not math.isfinite(g) or g < 0 for g in gaps)):
                        _fail("invalid_table_gaps")
                    body[-1]["column_gaps_px"] = list(gaps)
            else:
                _fail("invalid_body_owner")
        layout = {"version": "reviewed_region_layout_v1", "header": header, "body": body, "footer": footer}
        if gutters:
            layout.update(version="reviewed_region_layout_v2",
                          gutter_policy="explicit_source_supported_column_gaps_v1")
        if rows:
            validate_reviewed_regions(layout, fragments=tuple(RegionFragmentInput(
                r["rendering_id"], r["role"], tuple(r["bbox_px"])) for r in rows), page_number=number, image_size_px=size)
        elif header or body or footer or decision.full_page_review_completed:
            _fail("incomplete_page_review")
        return {**template, "image_size_px": list(size),
            "frame": {"origin": "top_left", "units": "pixel", "page_size_pt": [source["width_pt"], source["height_pt"]],
                      "paper_size_basis": "a4_assumed"}, "fragments": rows, "region_layout": layout,
            "folio_fragment_id": None if decision.folio_fragment_number is None else reference(decision.folio_fragment_number)}

    def _document(self, decision, count):
        if type(decision) is not FormattingDocumentDecision:
            _fail("invalid_document_decision")
        for value in (decision.all_pages_reviewed, decision.allow_pipe_cell_boundaries, decision.preserve_source_gaps):
            if type(value) is not bool:
                _fail("invalid_document_decision")
        _text(decision.reviewer)
        _text(decision.review_note)
        expected = 1
        for group in _sequence(decision.groups, count):
            if (type(group) is not FormattingDocumentGroup or type(group.start_page) is not int
                    or type(group.end_page) is not int or group.start_page != expected
                    or not expected <= group.end_page <= count):
                _fail("invalid_document_groups")
            expected = group.end_page + 1
        if expected != count + 1:
            _fail("incomplete_document_groups")

    def _advance(self, parents, record, previous, total, expected_generation):
        if type(expected_generation) is not int or expected_generation != record["generation"]:
            _fail("stale_generation")
        if expected_generation >= _MAX_GENERATIONS:
            _fail("generation_limit")
        record["generation"] += 1
        record["previous_sha256"] = previous
        if total + len(_json(record)) > _MAX_DRAFT:
            _fail("draft_too_large")
        _write(self._folder(record["draft_id"]) / f"{record['generation']:06d}.json", record)

    def save_page(self, draft_id, *, expected_generation: int, page_number: int, decision: FormattingPageDecision):
        with self._scope():
            parents, record, previous, total = self._load(draft_id, editable=True)
            _, fresh, images = self._fresh(parents)
            if fresh["status"] == "declined":
                return fresh
            if type(page_number) is not int or not 1 <= page_number <= len(record["page_decisions"]):
                _fail("invalid_page")
            acquisition = parents["acquisition"]
            page = self._page(decision, acquisition["review_inputs"][page_number - 1],
                              acquisition["formatting_manifest"]["pages"][page_number - 1], images[page_number])
            record["page_decisions"][page_number - 1] = {"decision": _page_decision_dict(decision), "manifest_page": page}
            # A later page change invalidates the document-wide completion assertion.
            record["document_decision"] = None
            self._advance(parents, record, previous, total, expected_generation)
            return self._view(parents, record, images)

    def save_document(self, draft_id, *, expected_generation: int, decision: FormattingDocumentDecision):
        with self._scope():
            parents, record, previous, total = self._load(draft_id, editable=True)
            _, fresh, images = self._fresh(parents)
            if fresh["status"] == "declined":
                return fresh
            self._document(decision, len(record["page_decisions"]))
            record["document_decision"] = asdict(decision)
            self._advance(parents, record, previous, total, expected_generation)
            return self._view(parents, record, images)

    def submit(self, draft_id, *, expected_generation: int, reviewer: str, accept_formatting: bool):
        with self._scope():
            parents, record, generation_hash, _ = self._load(draft_id)
            state, fresh, images = self._fresh(parents)
            if fresh["status"] == "declined":
                return fresh
            if type(expected_generation) is not int or expected_generation != record["generation"]:
                _fail("stale_generation")
            if accept_formatting is not True:
                _fail("explicit_acceptance_required")
            _text(reviewer)
            document = record["document_decision"]
            if document is None or document["all_pages_reviewed"] is not True or any(
                    row is None or row["decision"]["full_page_review_completed"] is not True
                    or row["decision"]["source_target_mapping_reviewed"] is not True for row in record["page_decisions"]):
                _fail("incomplete_review")
            self._document(_typed_document(document), len(record["page_decisions"]))
            manifest = deepcopy(fresh["formatting_manifest"])
            manifest["document_groups"] = document["groups"]
            manifest["boundary_policy"] = CELL_BOUNDARY_POLICY if document["allow_pipe_cell_boundaries"] else BOUNDARY_POLICY
            if document["preserve_source_gaps"]:
                manifest["spacing_policy"] = SOURCE_GAP_POLICY
            manifest["pages"] = []
            for number, row in enumerate(record["page_decisions"], 1):
                page = self._page(_typed_page(row["decision"]), fresh["review_inputs"][number - 1],
                    fresh["formatting_manifest"]["pages"][number - 1], images[number])
                if _json(page) != _json(row["manifest_page"]):
                    _fail("saved_mapping_changed")
                manifest["pages"].append(page)
            raw = _json(manifest)
            validate_reviewed_formatting(raw, expected_manifest_sha256=_sha(raw), pages=[FormattingPageInput(
                pair["source_structure"], pair["target_structure"], binding["commit_file_sha256"],
                binding["bundle_sha256"], images[binding["page_number"]])
                for pair, binding in zip(fresh["review_inputs"], fresh["binding"]["pages"])],
                source_file_sha256=manifest["source_file_sha256"], target_lang=manifest["target_lang"],
                preferences_sha256=manifest["preferences_sha256"], expected_reviewer_kind="operator_review")
            evidence = {**self._formatting_choice(), "version": VERSION, "kind": "explicit_operator_formatting_acceptance",
                "reviewer_kind": "operator_review", "reviewer": reviewer, "accept_formatting": True,
                "source_context": self._context.identity, "draft_id": draft_id, "generation": expected_generation,
                "generation_sha256": generation_hash, "formatting_manifest_sha256": _sha(raw),
                "page_decisions": [row["decision"] for row in record["page_decisions"]], "document_decision": document}
            evidence_raw = _json(evidence)
            intent = {"version": VERSION, "owner": self._owner, "draft_id": draft_id,
                "generation": expected_generation, "generation_sha256": generation_hash,
                "reviewer": reviewer, "formatting_manifest_sha256": _sha(raw),
                "review_evidence_sha256": _sha(evidence_raw)}
            intent_path = self._folder(draft_id) / "submit_intent.json"
            self._write_once(intent_path, intent, code="submission_inputs_changed")
            # A fresh context/physical-source check immediately precedes adapter publication.
            _, repeated, _ = self._fresh(parents)
            if repeated["status"] == "declined":
                return repeated
            prepared = self._find_publication(intent, state)
            if prepared is None:
                started = self._folder(draft_id) / "adapter_started.json"
                if started.exists():
                    # An interrupted adapter may have left an incomplete folder.
                    # Never repeat an uncertain publication or infer the latest.
                    _fail("submission_publication_unresolved")
                _write(started, {"version": VERSION, "intent_sha256": _sha(_json(intent))})
                revision_id = submit_run_formatting_review(self.run_dir, self._render_config, state,
                    reviewer_kind="operator_review", source_review=self._context.source_review_json,
                    source_evidence=self._context.evidence, source_review_evidence=self._context.decision_evidence,
                    formatting_manifest=raw, review_evidence=evidence_raw, review_profile=OPERATOR_REVIEW_PROFILE)
                prepared = self._find_publication(intent, state)
                if prepared is None or prepared.revision_id != revision_id:
                    _fail("submitted_revision_not_ready")
            self._finish_receipts(intent, prepared)
            return self._revision_view(prepared, status="submitted")

    def _write_once(self, path, value, *, code="publication_changed"):
        if path.exists() or path.is_symlink():
            if _read(path) != _json(value):
                _fail(code)
        else:
            _write(path, value)

    def _intent(self, intent, record, digest):
        if (set(intent) != {"version", "owner", "draft_id", "generation", "generation_sha256", "reviewer",
                            "formatting_manifest_sha256", "review_evidence_sha256"}
                or intent["version"] != VERSION or _json(intent["owner"]) != _json(self._owner)
                or intent["draft_id"] != record["draft_id"] or type(intent["generation"]) is not int
                or intent["generation"] != record["generation"]
                or intent["generation_sha256"] != digest
                or any(type(intent[key]) is not str or re.fullmatch(r"[a-f0-9]{64}", intent[key]) is None
                       for key in ("generation_sha256", "formatting_manifest_sha256", "review_evidence_sha256"))):
            _fail("submission_intent_changed")
        _text(intent["reviewer"])
        return intent

    def _find_publication(self, intent, state):
        """Recover exactly one complete adapter publication, never newest/first."""
        root = self.run_dir / "formatting_reviews"
        if not root.exists():
            return None
        _direct(root, directory=True)
        matches = []
        with os.scandir(root) as entries:
            for count, entry in enumerate(entries, 1):
                if count > 1000:
                    _fail("revision_inventory_too_large")
                folder = _direct(root / _id(entry.name), directory=True)
                marker = folder / "revision.json"
                if not marker.exists():
                    continue  # Incomplete immutable folders are not revisions.
                revision = _decode(_read(marker))
                files = revision.get("files", {})
                descriptor = files.get("review_evidence.bin", {})
                if descriptor.get("sha256") != intent["review_evidence_sha256"]:
                    continue
                evidence_raw = _read(folder / "review_evidence.bin")
                evidence = _decode(evidence_raw)
                if (_sha(evidence_raw) != intent["review_evidence_sha256"]
                        or files.get("formatting.json", {}).get("sha256") != intent["formatting_manifest_sha256"]
                        or evidence.get("source_context") != self._context.identity
                        or _json(evidence.get("formatting_derivative")) != _json(self._owner.get("formatting_derivative"))
                        or evidence.get("draft_id") != intent["draft_id"]
                        or type(evidence.get("generation")) is not int or evidence.get("generation") != intent["generation"]
                        or evidence.get("generation_sha256") != intent["generation_sha256"]
                        or evidence.get("reviewer") != intent["reviewer"]
                        or evidence.get("accept_formatting") is not True
                        or evidence.get("reviewer_kind") != "operator_review"):
                    _fail("submission_publication_changed")
                prepared = prepare_run_docx_formatting(self.run_dir, self._render_config, state,
                    revision_id=entry.name, review_profile=OPERATOR_REVIEW_PROFILE)
                if prepared.status != "ready":
                    _fail("submitted_revision_not_ready")
                matches.append(prepared)
        if len(matches) > 1:
            _fail("ambiguous_submission_publication")
        return matches[0] if matches else None

    def _finish_receipts(self, intent, prepared):
        receipt = {"version": VERSION, "owner": self._owner, "draft_id": intent["draft_id"],
            "generation": intent["generation"], "generation_sha256": intent["generation_sha256"],
            "revision_id": prepared.revision_id, "revision_sha256": prepared.revision_sha256}
        _mkdir(self._root / "revisions")
        self._write_once(self._root / "revisions" / (prepared.revision_id + ".json"), receipt)
        self._write_once(self._folder(intent["draft_id"]) / "submitted.json", receipt)

    def _selected(self, revision_id):
        receipt = _decode(_read(self._root / "revisions" / (_id(revision_id) + ".json")))
        if (set(receipt) != {"version", "owner", "draft_id", "generation", "generation_sha256", "revision_id", "revision_sha256"}
                or receipt["version"] != VERSION or _json(receipt["owner"]) != _json(self._owner)
                or type(receipt["generation"]) is not int or receipt["revision_id"] != revision_id):
            _fail("revision_owner_changed")
        parents, record, digest, _ = self._load(receipt["draft_id"])
        intent = self._intent(_decode(_read(self._folder(receipt["draft_id"]) / "submit_intent.json")), record, digest)
        if (_decode(_read(self._folder(receipt["draft_id"]) / "submitted.json")) != receipt
                or record["generation"] != receipt["generation"] or digest != receipt["generation_sha256"]):
            _fail("submitted_generation_changed")
        state, fresh, _ = self._fresh(parents)
        if fresh["status"] == "declined":
            return state, fresh
        preparation = self._find_publication(intent, state)
        if (preparation is None or preparation.revision_id != revision_id
                or preparation.revision_sha256 != receipt["revision_sha256"]):
            _fail("revision_changed")
        return state, preparation

    def _revision_view(self, prepared, *, status=None):
        return {**self._formatting_choice(), "status": status or prepared.status, "revision_id": prepared.revision_id,
            "source_revision_id": self._context.revision_id, "notice_codes": list(prepared.notice_codes),
            "review_profile": OPERATOR_REVIEW_PROFILE, "reviewer_kind": "operator_review",
            "geometry_status": "not_verified", "rendered_layout_acceptance": "not_evaluated",
            "layout_review_required": True}

    def inspect(self, revision_id):
        with self._scope():
            _, prepared = self._selected(revision_id)
            return prepared if type(prepared) is dict else self._revision_view(prepared)

    def rebuild(self, revision_id):
        """Return a backend artifact path; never fall back or select it silently."""
        with self._scope():
            state, prepared = self._selected(revision_id)
            if type(prepared) is dict:
                return prepared
            if prepared.status != "ready":
                return self._revision_view(prepared)
            output_dir = _direct(state.frozen_outdir_abs, directory=True)
            if output_dir != self._config.output_dir:
                _fail("saved_output_owner_changed")
            output = build_run_paths(output_dir, self._config.pdf_path, self._config.target_lang,
                run_started_at=state.run_started_at, gmail_batch_context=self._config.gmail_batch_context).final_docx_path
            path = build_run_reviewed_docx(prepared, config=self._render_config, state=state, output_path=output)
            # Binding and source storage remain valid after package publication.
            _, rechecked = self._selected(revision_id)
            if type(rechecked) is dict or rechecked.status != "ready":
                _fail("inputs_changed_during_rebuild")
            return {**self._revision_view(rechecked, status="built"), "output_docx": path,
                    "source_map": path.with_suffix(".source_map.json"),
                    "assembly_receipt": path.with_suffix(".formatting_assembly.json")}
