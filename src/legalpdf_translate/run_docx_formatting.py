"""Run-owned reviewed formatting acquisition and offline rebuild adapter.

The default builds only the existing complete AI-reviewed browser-image profile.
An explicitly selected operator profile requires genuine operator source and
formatting reviews; digital/OCR/partial profiles retain explicit decline notices.
Normal DOCX flow remains the caller's fallback. No private acceptance caller,
provider, OCR, native renderer, checkpoint writer, accounting writer or
preference mutation belongs here.

The caller owns the ordinary run lock. Submitted revisions are exclusive local
artifacts, never a signature/certification or a substitute for source review.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any
import uuid

REVIEW_VERSION = "run_formatting_review_v1"
OPERATOR_REVIEW_VERSION = "run_formatting_review_v2"
STRICT_REVIEW_PROFILE = "strict_ai_test_v1"
OPERATOR_REVIEW_PROFILE = "ordinary_operator_browser_v1"
ASSEMBLY_VERSION = "run_reviewed_docx_assembly_v1"
_DIRECTORY = "formatting_reviews"
_ID = re.compile(r"[a-f0-9]{32}\Z", re.ASCII)
_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_MAX_FILE = 8 * 1024 * 1024
_MAX_IMAGE = 40 * 1024 * 1024
_MAX_EVIDENCE = 256 * 1024 * 1024
_MAX_PAGES = 1000


class RunDocxFormattingError(ValueError):
    """Content-free integrity or malformed-input failure; do not fall back."""


@dataclass(frozen=True, slots=True)
class RunDocxPreparation:
    status: str
    notice_codes: tuple[str, ...]
    selected_pages: tuple[int, ...]
    run_dir: Path
    partial_output: bool
    revision_id: str | None = None
    binding_bytes: bytes = b""
    revision_sha256: str | None = None
    projection: Any = field(default=None, repr=False)
    review_profile: str = STRICT_REVIEW_PROFILE

    @property
    def expected_reviewer_kind(self) -> str:
        return _profile_reviewer(self.review_profile)


def _fail(code):
    raise RunDocxFormattingError(code)


def _profile_reviewer(profile):
    if type(profile) is not str or profile not in {STRICT_REVIEW_PROFILE, OPERATOR_REVIEW_PROFILE}:
        _fail("run_formatting_invalid_review_profile")
    return "operator_review" if profile == OPERATOR_REVIEW_PROFILE else "ai_test_review"


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        _fail("run_formatting_invalid_json")


def _decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail("run_formatting_duplicate_json_key")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: _fail("run_formatting_nonfinite_json"))
    except (UnicodeError, ValueError, TypeError, RecursionError):
        _fail("run_formatting_invalid_json")


def _path(value, *, directory=False, within=None):
    try:
        path = Path(value).expanduser().absolute()
        info = path.lstat()
        for item in (path, *path.parents):
            item_info = item.lstat()
            if (item.is_symlink() or getattr(item_info, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)):
                _fail("run_formatting_linked_path")
        if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
            _fail("run_formatting_invalid_path")
        resolved = path.resolve(strict=True)
        if within is not None and not resolved.is_relative_to(within):
            _fail("run_formatting_path_outside_owner")
        return resolved
    except RunDocxFormattingError:
        raise
    except (OSError, TypeError, ValueError):
        _fail("run_formatting_path_unavailable")


def _read(value, *, maximum=_MAX_FILE, within=None):
    path = _path(value, within=within)
    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    try:
        before = identity(path.stat())
        with path.open("rb") as stream:
            opened = identity(os.fstat(stream.fileno()))
            raw = stream.read(maximum + 1)
            after = identity(os.fstat(stream.fileno()))
        if before != opened or opened != after or after != identity(path.stat()):
            _fail("run_formatting_file_changed_during_read")
        if len(raw) > maximum:
            _fail("run_formatting_file_too_large")
        return raw
    except OSError:
        _fail("run_formatting_file_unavailable")


def _exclusive(path, raw):
    try:
        with path.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        _fail("run_formatting_exclusive_publish_failed")


def _selection(state, page_numbers):
    try:
        entries = state.pages
        numbers = sorted(int(key) for key in entries)
        if (not numbers or len(numbers) > _MAX_PAGES or len(set(numbers)) != len(numbers)
                or any(str(number) not in entries or number < 1 for number in numbers)
                or type(state.total_pages) is not int or not 1 <= state.total_pages <= _MAX_PAGES
                or numbers[-1] > state.total_pages
                or any(type(value) is not int for value in (state.selection_start_page,
                    state.selection_end_page, state.selection_page_count))
                or state.selection_start_page != numbers[0] or state.selection_end_page != numbers[-1]
                or state.selection_page_count != len(numbers)):
            _fail("run_formatting_invalid_selection")
        completed = tuple(number for number in numbers if entries[str(number)].get("status") == "done")
        selected = completed if page_numbers is None else tuple(page_numbers)
        if (not selected or any(type(n) is not int or n not in completed for n in selected)
                or tuple(sorted(set(selected))) != selected):
            _fail("run_formatting_invalid_completed_selection")
        return tuple(numbers), selected
    except (AttributeError, TypeError, ValueError, KeyError):
        _fail("run_formatting_invalid_selection")


def _physical_source(source_path, total):
    """Read retained source/raster bytes; never render a missing raster."""
    from .browser_pdf_bundle import browser_pdf_bundle_manifest_path, load_browser_pdf_bundle
    from .source_document import is_image_source, is_pdf_source

    source_path = _path(source_path)
    source_hash = _sha(_read(source_path, maximum=_MAX_EVIDENCE))
    images, identities, physical = {}, {}, {"path": str(source_path), "sha256": source_hash}
    try:
        bundle = load_browser_pdf_bundle(source_path) if is_pdf_source(source_path) else None
    except (OSError, TypeError, ValueError, OverflowError):
        _fail("run_formatting_invalid_source_bundle")
    if bundle is not None:
        manifest_path = _path(browser_pdf_bundle_manifest_path(source_path))
        raw = _read(manifest_path)
        # Public bundle loading checks the source path/stat. Recheck this exact
        # manifest's page inventory and confine all rasters to its own directory.
        record = _decode(raw)
        if type(record) is not dict:
            _fail("run_formatting_invalid_source_bundle")
        rows = record.get("pages")
        if (_json(record) != _json(bundle)
                or type(record.get("page_count")) is not int or record["page_count"] != total
                or type(rows) is not list or len(rows) != total
                or any(type(row) is not dict or type(row.get("page_number")) is not int for row in rows)
                or [row.get("page_number") for row in rows] != list(range(1, total + 1))):
            _fail("run_formatting_source_page_inventory_changed")
        root = _path(manifest_path.parent, directory=True)
        physical["bundle_manifest_sha256"] = _sha(raw)
        inventory_size = 0
        for number, row in enumerate(rows, 1):
            if type(row.get("image_path")) is not str:
                _fail("run_formatting_invalid_raster_path")
            path = _path(root / row["image_path"], within=root)
            image = _read(path, maximum=_MAX_IMAGE, within=root)
            images[number] = image
            inventory_size += len(image)
            if inventory_size > _MAX_EVIDENCE:
                _fail("run_formatting_raster_inventory_too_large")
            identities[number] = {"source_file_sha256": source_hash, "image_sha256": _sha(image),
                "source_type": "browser_pdf_image", "paper_size_basis": "a4_assumed"}
        if _read(manifest_path) != raw:
            _fail("run_formatting_source_changed_during_read")
    elif is_image_source(source_path):
        if total != 1:
            _fail("run_formatting_source_page_inventory_changed")
        images[1] = _read(source_path, maximum=_MAX_IMAGE)
        identities[1] = {"source_file_sha256": source_hash, "image_sha256": source_hash,
                         "source_type": "image", "paper_size_basis": "a4_assumed"}
    elif is_pdf_source(source_path):
        identities = {number: {"source_file_sha256": source_hash, "image_sha256": "",
            "source_type": "pdf", "paper_size_basis": "source_pdf"} for number in range(1, total + 1)}
    else:
        _fail("run_formatting_unsupported_source_file")
    if sum(len(raw) for raw in images.values()) > _MAX_EVIDENCE:
        _fail("run_formatting_raster_inventory_too_large")
    if _sha(_read(source_path, maximum=_MAX_EVIDENCE)) != source_hash:
        _fail("run_formatting_source_changed_during_read")
    return source_hash, identities, images, physical


def _capture(run_dir, config, state, *, page_numbers=None, partial_output=False):
    from .formatting_support import formatting_fingerprint
    from .structured_artifacts import validate_structured_rebuild_page

    run_dir = _path(run_dir, directory=True)
    pages_dir = _path(run_dir / "pages", directory=True, within=run_dir)
    selection, selected = _selection(state, page_numbers)
    if type(partial_output) is not bool or type(config.page_breaks) is not bool or type(config.strip_bidi_controls) is not bool:
        _fail("run_formatting_invalid_preferences")
    lang = config.target_lang.value
    if (lang not in {"AR", "EN", "FR"} or state.lang != lang
            or (state.run_dir_abs and Path(state.run_dir_abs).resolve() != run_dir)
            or Path(state.pdf_path).resolve() != Path(config.pdf_path).resolve()):
        _fail("run_formatting_checkpoint_identity_changed")
    source_hash, identities, images, physical = _physical_source(config.pdf_path, state.total_pages)
    if source_hash != state.pdf_fingerprint:
        _fail("run_formatting_source_changed")
    rows, inputs, edited = [], [], []
    for number in selected:
        expected = state.pages[str(number)].get("structured_commit")
        if not expected or not state.protocol_identity:
            _fail("run_formatting_structured_checkpoint_required")
        record, changed = validate_structured_rebuild_page(pages_dir, number, expected_commit=expected,
                                                          protocol_identity=state.protocol_identity)
        stem = f"page_{number:04d}"
        raws = {"source": _read(pages_dir / (stem + ".source_structure.json"), within=pages_dir),
                "target": _read(pages_dir / (stem + ".structure.json"), within=pages_dir),
                "text": _read(pages_dir / (stem + ".txt"), within=pages_dir),
                "commit": _read(pages_dir / (stem + ".commit.json"), maximum=65536, within=pages_dir)}
        source, target = _decode(raws["source"]), _decode(raws["target"])
        if (type(source) is not dict or type(target) is not dict
                or type(source.get("metadata")) is not dict
                or source.get("source_file_sha256") != source_hash
                or source.get("metadata", {}).get("source_page_identity") != identities[number]):
            _fail("run_formatting_retained_source_identity_changed")
        if changed:
            edited.append(number)
        verified, changed_again = validate_structured_rebuild_page(pages_dir, number,
            expected_commit=expected, protocol_identity=state.protocol_identity)
        if verified != record or changed_again != changed or _decode(raws["commit"]) != record:
            _fail("run_formatting_page_changed_during_read")
        if _read(pages_dir / (stem + ".txt"), within=pages_dir) != raws["text"]:
            _fail("run_formatting_page_changed_during_read")
        for kind in ("source", "target"):
            if _sha(raws[kind]) != record["artifacts"][kind]["sha256"]:
                _fail("run_formatting_page_changed_during_read")
        ignored_sidecars = {}
        for suffix in ("layout.json", "layout_eligibility.json"):
            sidecar = pages_dir / (stem + "." + suffix)
            if sidecar.exists() or sidecar.is_symlink():
                content = _read(sidecar, within=pages_dir)
                ignored_sidecars[suffix] = {"sha256": _sha(content), "bytes": len(content)}
        rows.append({"page_number": number, "commit_file_sha256": _sha(raws["commit"]),
            "bundle_sha256": record["bundle_sha256"], "source_structure_sha256": _sha(_json(source)),
            "target_structure_sha256": _sha(_json(target)), "current_text_sha256": _sha(raws["text"]),
            "source_provenance": source.get("provenance"), "source_identity": identities[number],
            "original_commit": record, "edited_target": changed,
            "ignored_layout_sidecars": ignored_sidecars})
        inputs.append((source, target, raws))
    binding = {"run_dir": str(run_dir), "physical_source": physical, "target_lang": lang,
        "total_source_pages": state.total_pages, "selection_pages": list(selection),
        "selected_pages": list(selected), "partial_output": partial_output,
        "protocol_identity": json.loads(_json(state.protocol_identity)),
        "formatting_preferences": {"page_breaks": config.page_breaks, "strip_bidi_controls": config.strip_bidi_controls},
        "preferences_sha256": formatting_fingerprint(config), "pages": rows}
    return binding, inputs, identities, images, tuple(edited)


def _notices(binding, reviewer_kind, source_reviewer_kind=None, *,
             review_profile=STRICT_REVIEW_PROFILE, inputs=()):
    expected_reviewer = _profile_reviewer(review_profile)
    source_reviews = [source.get("metadata", {}).get("reviewed_source") for source, _, _ in inputs]
    notices = []
    if (binding["partial_output"] or binding["selection_pages"] != list(range(1, binding["total_source_pages"] + 1))
            or binding["selected_pages"] != binding["selection_pages"]):
        notices.append("reviewed_profile_unsupported_selection")
    if not binding["formatting_preferences"]["page_breaks"]:
        notices.append("reviewed_profile_requires_page_breaks")
    if not binding["formatting_preferences"]["strip_bidi_controls"]:
        notices.append("reviewed_profile_requires_bidi_stripping")
    if reviewer_kind != expected_reviewer:
        notices.append("reviewed_profile_unsupported_reviewer")
    if ((source_reviewer_kind is not None and source_reviewer_kind != expected_reviewer)
            or (review_profile == OPERATOR_REVIEW_PROFILE and (not inputs or any(
                type(review) is not dict or review.get("review_kind") != "operator_review"
                for review in source_reviews)))):
        notices.append("reviewed_profile_unsupported_source_reviewer")
    if binding["protocol_identity"].get("protocol") != "legal_blocks_v2":
        notices.append("reviewed_profile_unsupported_protocol")
    if any(row["source_provenance"] != "reviewed_image_source_v1"
           or row["source_identity"]["source_type"] != "browser_pdf_image" for row in binding["pages"]):
        notices.append("reviewed_profile_unsupported_source_provenance")
    if any(row["edited_target"] for row in binding["pages"]):
        notices.append("reviewed_profile_stale_edited_target")
    return tuple(notices)


def _verify_source(raw, evidence, decision_evidence, binding, inputs, identities):
    from .source_readiness import verify_source_review
    envelope = _decode(raw)
    if (type(envelope) is not dict or type(decision_evidence) is not bytes
            or not 0 < len(decision_evidence) <= _MAX_FILE
            or envelope.get("review_evidence_sha256") != _sha(decision_evidence)):
        _fail("run_formatting_source_decision_evidence_changed")
    sizes = {number: (595.276, 841.89) for number, identity in identities.items()
             if identity["paper_size_basis"] == "a4_assumed"}
    rows = verify_source_review(raw.decode("utf-8"), page_identities=identities,
        source_hash=binding["physical_source"]["sha256"], reviewed_evidence=evidence, page_sizes=sizes or None)
    for row, (source, _, _) in zip(binding["pages"], inputs):
        if _json(rows[row["page_number"]]["source_structure"]) != _json(source):
            _fail("run_formatting_source_review_does_not_match_commit")
    return envelope["review_kind"]


def _manifest_binding(raw, binding, reviewer_kind):
    manifest = _decode(raw)
    if (type(manifest) is not dict or manifest.get("reviewer_kind") != reviewer_kind
            or manifest.get("source_file_sha256") != binding["physical_source"]["sha256"]
            or manifest.get("target_lang") != binding["target_lang"]
            or manifest.get("preferences_sha256") != binding["preferences_sha256"]
            or manifest.get("full_case_pages") != binding["selected_pages"]
            or type(manifest.get("pages")) is not list or len(manifest["pages"]) != len(binding["pages"])):
        _fail("run_formatting_manifest_binding_changed")
    for expected, actual in zip(binding["pages"], manifest["pages"]):
        if type(actual) is not dict or any(actual.get(key) != expected[key] for key in (
                "page_number", "commit_file_sha256", "bundle_sha256", "source_structure_sha256", "target_structure_sha256")):
            _fail("run_formatting_manifest_page_changed")
    return manifest


def _projection(raw, binding, inputs, images, *, review_profile=STRICT_REVIEW_PROFILE):
    from .reviewed_formatting import FormattingPageInput, validate_reviewed_formatting
    return validate_reviewed_formatting(raw, expected_manifest_sha256=_sha(raw),
        pages=[FormattingPageInput(source, target, row["commit_file_sha256"], row["bundle_sha256"],
                                   images[row["page_number"]])
               for row, (source, target, _) in zip(binding["pages"], inputs)],
        source_file_sha256=binding["physical_source"]["sha256"], target_lang=binding["target_lang"],
        preferences_sha256=binding["preferences_sha256"],
        expected_reviewer_kind=_profile_reviewer(review_profile))


def begin_run_formatting_review(run_dir, config, state, *, reviewer_kind, page_numbers=None,
                                partial_output=False, review_profile=STRICT_REVIEW_PROFILE):
    """Return an unaccepted run-bound draft; never infer boxes or target cuts.

    A local review UI/CLI can use the retained source/target structures here and
    independently author fragments, regions, folios and document groups. Empty
    declarations intentionally cannot be assembled. The source review envelope
    must be supplied separately on submission; this API never manufactures it.
    """
    if type(reviewer_kind) is not str or reviewer_kind not in {"ai_test_review", "operator_review"}:
        _fail("run_formatting_invalid_reviewer")
    _profile_reviewer(review_profile)
    binding, inputs, _, images, _ = _capture(run_dir, config, state, page_numbers=page_numbers,
                                           partial_output=partial_output)
    from .reviewed_formatting import REGION_VERSION, REGION_POLICY, BOUNDARY_POLICY, FOLIO_POLICY
    rows = []
    for row, (source, target, _) in zip(binding["pages"], inputs):
        number = row["page_number"]
        rows.append({key: row[key] for key in ("page_number", "commit_file_sha256", "bundle_sha256",
                    "source_structure_sha256", "target_structure_sha256")})
        rows[-1].update(source_image_sha256=_sha(images[number]) if number in images else None,
            image_size_px=None, frame=None, fragments=[], region_layout=None, folio_fragment_id=None)
    result = {"version": "run_formatting_review_draft_v1", "status": "draft", "binding": binding,
        "notice_codes": list(_notices(binding, reviewer_kind, review_profile=review_profile, inputs=inputs)),
        "review_inputs": [{"source_structure": source, "target_structure": target} for source, target, _ in inputs],
        "formatting_manifest": {"version": REGION_VERSION, "policy": REGION_POLICY,
            "boundary_policy": BOUNDARY_POLICY, "offset_unit": "unicode_codepoint", "reviewer_kind": reviewer_kind,
            "source_file_sha256": binding["physical_source"]["sha256"], "target_lang": binding["target_lang"],
            "preferences_sha256": binding["preferences_sha256"], "full_case_pages": binding["selected_pages"],
            "document_groups": [], "folio_policy": FOLIO_POLICY, "pages": rows}}
    if review_profile == OPERATOR_REVIEW_PROFILE:
        result.update(version="run_formatting_review_draft_v2", review_profile=review_profile)
    return result


def submit_run_formatting_review(run_dir, config, state, *, reviewer_kind, source_review: bytes,
        source_evidence, source_review_evidence: bytes, formatting_manifest: bytes,
        review_evidence: bytes, page_numbers=None,
        partial_output=False, review_profile=STRICT_REVIEW_PROFILE) -> str:
    """Save one exclusive source-verified acquisition revision owned by the run.

    Unsupported reviewer/provenance/selection profiles remain submitted and
    explicitly declined for assembly; their records are never relabelled AI.
    Supported profiles pass the actual strict pure formatting validator now and
    again on rebuild. Review evidence is caller-authored, not synthesized here.
    """
    if type(reviewer_kind) is not str or reviewer_kind not in {"ai_test_review", "operator_review"}:
        _fail("run_formatting_invalid_reviewer")
    _profile_reviewer(review_profile)
    if any(type(raw) is not bytes or not 0 < len(raw) <= _MAX_FILE
           for raw in (source_review, source_review_evidence, formatting_manifest, review_evidence)):
        _fail("run_formatting_invalid_review_bytes")
    if source_evidence is not None:
        from .reviewed_source import ReviewedSourceEvidence
        if type(source_evidence) is not ReviewedSourceEvidence:
            _fail("run_formatting_invalid_source_evidence")
    binding, inputs, identities, images, edited = _capture(run_dir, config, state,
        page_numbers=page_numbers, partial_output=partial_output)
    if edited:
        _fail("run_formatting_edited_target_requires_new_mapping")
    source_reviewer = _verify_source(source_review, source_evidence, source_review_evidence,
                                     binding, inputs, identities)
    _manifest_binding(formatting_manifest, binding, reviewer_kind)
    notices = _notices(binding, reviewer_kind, source_reviewer, review_profile=review_profile, inputs=inputs)
    if not notices:
        _projection(formatting_manifest, binding, inputs, images, review_profile=review_profile)
    files = {"source_review.json": source_review, "formatting.json": formatting_manifest,
             "review_evidence.bin": review_evidence, "source_decision_evidence.bin": source_review_evidence}
    if source_evidence is not None:
        files.update({"candidate.json": source_evidence.candidate, "source_manifest.json": source_evidence.manifest})
        for digest, raw in source_evidence.artifacts:
            if type(digest) is not str or not _HASH.fullmatch(digest) or _sha(raw) != digest:
                _fail("run_formatting_source_evidence_hash_changed")
            files[f"evidence/{digest}.bin"] = raw
    if sum(len(raw) for raw in files.values()) > _MAX_EVIDENCE:
        _fail("run_formatting_review_inventory_too_large")
    again, *_ = _capture(run_dir, config, state, page_numbers=binding["selected_pages"], partial_output=partial_output)
    if _json(again) != _json(binding):
        _fail("run_formatting_inputs_changed_before_submission")
    root = Path(binding["run_dir"]) / _DIRECTORY
    root.mkdir(exist_ok=True)
    root = _path(root, directory=True, within=Path(binding["run_dir"]))
    revision_id = uuid.uuid4().hex
    folder = root / revision_id
    folder.mkdir(exist_ok=False)
    if source_evidence is not None:
        (folder / "evidence").mkdir()
    for name, raw in files.items():
        _exclusive(folder / name, raw)
    revision = {"version": REVIEW_VERSION, "revision_id": revision_id, "status": "submitted",
        "region_review_kind": reviewer_kind, "source_review_kind": source_reviewer,
        "binding": binding, "binding_sha256": _sha(_json(binding)), "notice_codes": list(notices),
        "source_geometry_status": "not_verified", "layout_acceptance": "not_evaluated",
        "has_reviewed_source_evidence": source_evidence is not None,
        "files": {name: {"sha256": _sha(raw), "bytes": len(raw)} for name, raw in files.items()}}
    if review_profile == OPERATOR_REVIEW_PROFILE:
        revision.update(version=OPERATOR_REVIEW_VERSION, review_profile=review_profile)
    _exclusive(folder / "revision.json", _json(revision))
    return revision_id


def _load_revision(run_dir, revision_id):
    if type(revision_id) is not str or not _ID.fullmatch(revision_id):
        _fail("run_formatting_invalid_revision_id")
    root = _path(run_dir / _DIRECTORY, directory=True, within=run_dir)
    folder = _path(root / revision_id, directory=True, within=root)
    raw = _read(folder / "revision.json", within=folder)
    revision = _decode(raw)
    operator_revision = type(revision) is dict and revision.get("version") == OPERATOR_REVIEW_VERSION
    expected = {"version", "revision_id", "status", "region_review_kind", "source_review_kind", "binding",
                "binding_sha256", "notice_codes", "source_geometry_status", "layout_acceptance",
                "has_reviewed_source_evidence", "files"} | ({"review_profile"} if operator_revision else set())
    if (type(revision) is not dict or set(revision) != expected
            or revision["version"] != (OPERATOR_REVIEW_VERSION if operator_revision else REVIEW_VERSION)
            or (operator_revision and revision["review_profile"] != OPERATOR_REVIEW_PROFILE)
            or revision["revision_id"] != revision_id or revision["status"] != "submitted"
            or type(revision["region_review_kind"]) is not str
            or revision["region_review_kind"] not in {"ai_test_review", "operator_review"}
            or type(revision["source_review_kind"]) is not str
            or revision["source_review_kind"] not in {"ai_test_review", "operator_review"}
            or type(revision["binding"]) is not dict or type(revision["notice_codes"]) is not list
            or any(type(code) is not str for code in revision["notice_codes"])
            or revision["source_geometry_status"] != "not_verified" or revision["layout_acceptance"] != "not_evaluated"
            or type(revision["has_reviewed_source_evidence"]) is not bool
            or revision["binding_sha256"] != _sha(_json(revision["binding"]))
            or type(revision["files"]) is not dict):
        _fail("run_formatting_invalid_revision")
    files, inventory_size = {}, 0
    for name, descriptor in revision["files"].items():
        if (name not in {"source_review.json", "formatting.json", "review_evidence.bin",
                        "source_decision_evidence.bin", "candidate.json", "source_manifest.json"}
                and re.fullmatch(r"evidence/[a-f0-9]{64}\.bin", name) is None):
            _fail("run_formatting_invalid_revision_file")
        maximum = _MAX_EVIDENCE if name.startswith("evidence/") else _MAX_FILE
        content = _read(folder / name, maximum=maximum, within=folder)
        if (type(descriptor) is not dict or type(descriptor.get("bytes")) is not int
                or descriptor != {"sha256": _sha(content), "bytes": len(content)}):
            _fail("run_formatting_revision_file_changed")
        files[name] = content
        inventory_size += len(content)
        if inventory_size > _MAX_EVIDENCE:
            _fail("run_formatting_review_inventory_too_large")
    base = {"source_review.json", "formatting.json", "review_evidence.bin", "source_decision_evidence.bin"}
    if not base <= set(files):
        _fail("run_formatting_incomplete_revision")
    source_review = _decode(files["source_review.json"])
    if (type(source_review) is not dict or source_review.get("review_kind") != revision["source_review_kind"]
            or source_review.get("review_evidence_sha256") != _sha(files["source_decision_evidence.bin"])):
        _fail("run_formatting_source_decision_evidence_changed")
    evidence = None
    if revision["has_reviewed_source_evidence"]:
        from .reviewed_source import ReviewedSourceEvidence
        if not {"candidate.json", "source_manifest.json"} <= set(files):
            _fail("run_formatting_incomplete_source_evidence")
        evidence = ReviewedSourceEvidence(files["candidate.json"], files["source_manifest.json"],
            tuple((name[9:-4], content) for name, content in files.items() if name.startswith("evidence/")))
    elif set(files) != base:
        _fail("run_formatting_unexpected_source_evidence")
    if _read(folder / "revision.json", within=folder) != raw:
        _fail("run_formatting_revision_changed_during_read")
    return revision, files, evidence, _sha(raw)


def prepare_run_docx_formatting(run_dir, config, state, *, revision_id=None,
                                page_numbers=None, partial_output=False,
                                review_profile=STRICT_REVIEW_PROFILE) -> RunDocxPreparation:
    """Prepare a reviewed rebuild or return explicit ordinary-flow notices.

    Bad physical/committed evidence raises; unsupported profiles, edited TXT,
    absent review and stale review bindings decline this optional profile.
    Operator revisions require an explicit matching profile on each call; a
    persisted reviewer label never selects that profile or upgrades v1 records.
    """
    run_dir = _path(run_dir, directory=True)
    _profile_reviewer(review_profile)
    if type(partial_output) is not bool:
        _fail("run_formatting_invalid_preferences")
    _, selected = _selection(state, page_numbers)
    if revision_id is None:
        return RunDocxPreparation("declined", ("reviewed_profile_review_missing",), selected, run_dir,
                                  partial_output, review_profile=review_profile)
    binding, inputs, identities, images, _ = _capture(run_dir, config, state,
        page_numbers=selected, partial_output=partial_output)
    revision, files, evidence, revision_hash = _load_revision(run_dir, revision_id)
    notices = _notices(binding, revision["region_review_kind"], revision["source_review_kind"],
                       review_profile=review_profile, inputs=inputs)
    if revision.get("review_profile", STRICT_REVIEW_PROFILE) != review_profile:
        notices = (*notices, "reviewed_profile_review_profile_mismatch")
    if _json(binding) != _json(revision["binding"]):
        notices = tuple(dict.fromkeys((*notices, "reviewed_profile_stale_review")))
    if notices:
        return RunDocxPreparation("declined", notices, selected, run_dir, partial_output,
                                  revision_id, _json(binding), revision_hash, review_profile=review_profile)
    _verify_source(files["source_review.json"], evidence, files["source_decision_evidence.bin"],
                   binding, inputs, identities)
    _manifest_binding(files["formatting.json"], binding, revision["region_review_kind"])
    projection = _projection(files["formatting.json"], binding, inputs, images, review_profile=review_profile)
    return RunDocxPreparation("ready", (), selected, run_dir, partial_output, revision_id,
                              _json(binding), revision_hash, projection, review_profile)


def build_run_reviewed_docx(preparation: RunDocxPreparation, *, config, state, output_path) -> Path:
    """Publish a verified, non-overwriting ordinary DOCX/map pair after recheck.

    The caller must hold the run lock and may use normal assemble_docx only for
    an explicitly declined preparation. A failed publication is not success;
    any partial files remain available for diagnosis and are never overwritten.
    """
    if type(preparation) is not RunDocxPreparation or preparation.status != "ready":
        _fail("run_formatting_ready_preparation_required")
    fresh = prepare_run_docx_formatting(preparation.run_dir, config, state,
        revision_id=preparation.revision_id, page_numbers=preparation.selected_pages,
        partial_output=preparation.partial_output, review_profile=preparation.review_profile)
    if (fresh.status != "ready" or fresh.binding_bytes != preparation.binding_bytes
            or fresh.revision_sha256 != preparation.revision_sha256):
        _fail("run_formatting_preparation_changed")
    from .reviewed_formatting_writer import build_reviewed_docx, validate_reviewed_docx
    writer_options = ({"expected_reviewer_kind": fresh.expected_reviewer_kind}
                      if fresh.review_profile == OPERATOR_REVIEW_PROFILE else {})
    artifact = build_reviewed_docx(fresh.projection, **writer_options)
    validate_reviewed_docx(artifact.docx_bytes, artifact.source_map_bytes, projection=fresh.projection,
                           **writer_options)
    checked = prepare_run_docx_formatting(preparation.run_dir, config, state,
        revision_id=preparation.revision_id, page_numbers=preparation.selected_pages,
        partial_output=preparation.partial_output, review_profile=preparation.review_profile)
    if (checked.status != "ready" or checked.binding_bytes != fresh.binding_bytes
            or checked.revision_sha256 != fresh.revision_sha256):
        _fail("run_formatting_inputs_changed_during_assembly")
    requested = Path(output_path).expanduser().absolute()
    parent = _path(requested.parent, directory=True)
    if (requested.suffix.lower() != ".docx" or parent.is_relative_to(preparation.run_dir / "pages")
            or parent.is_relative_to(preparation.run_dir / _DIRECTORY)):
        _fail("run_formatting_invalid_output_path")
    from .docx_writer import resolve_noncolliding_output_path
    output = resolve_noncolliding_output_path(parent / requested.name)
    mapping = output.with_suffix(".source_map.json")
    assembly_path = output.with_suffix(".formatting_assembly.json")
    if mapping.exists() or assembly_path.exists():
        _fail("run_formatting_output_companion_exists")
    summary = {"version": ASSEMBLY_VERSION, "revision_id": fresh.revision_id,
        "revision_sha256": fresh.revision_sha256, "binding_sha256": _sha(fresh.binding_bytes),
        "selected_pages": list(fresh.selected_pages), "docx_sha256": _sha(artifact.docx_bytes),
        "source_map_sha256": _sha(artifact.source_map_bytes), "provider_dispatch_count": 0,
        "layout_review_required": True, "rendered_layout_acceptance": "not_evaluated"}
    if fresh.review_profile == OPERATOR_REVIEW_PROFILE:
        summary.update(review_profile=fresh.review_profile, source_review_kind="operator_review",
                       region_review_kind=fresh.expected_reviewer_kind)
    # DOCX is published last; a companion without a DOCX is not a completed output.
    _exclusive(mapping, artifact.source_map_bytes)
    _exclusive(assembly_path, _json(summary))
    _exclusive(output, artifact.docx_bytes)
    if (_read(output, maximum=32 * 1024 * 1024) != artifact.docx_bytes
            or _read(mapping, maximum=128 * 1024 * 1024) != artifact.source_map_bytes
            or _read(assembly_path) != _json(summary)):
        _fail("run_formatting_published_output_changed")
    final = prepare_run_docx_formatting(preparation.run_dir, config, state,
        revision_id=preparation.revision_id, page_numbers=preparation.selected_pages,
        partial_output=preparation.partial_output, review_profile=preparation.review_profile)
    if (final.status != "ready" or final.binding_bytes != fresh.binding_bytes
            or final.revision_sha256 != fresh.revision_sha256):
        _fail("run_formatting_inputs_changed_during_publication")
    return output
