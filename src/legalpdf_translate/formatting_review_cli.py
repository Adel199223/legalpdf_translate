"""Local, explicit formatting review for saved ordinary translation runs.

Run with ``python -m legalpdf_translate.formatting_review_cli --help``. This
entrypoint never loads ambient preferences or credentials. Saved fingerprint
settings are required verbatim; unsupported/ambiguous runs fail closed. Review
packets contain private parent text and must be kept with the source evidence.
Even draft/inspect acquires the shared lock and may create .run_workspace.lock.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

from .checkpoint import build_run_paths, load_run_state, settings_fingerprint
from .run_docx_formatting import (OPERATOR_REVIEW_PROFILE, STRICT_REVIEW_PROFILE,
                                 prepare_run_docx_formatting)
from .run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
from .types import (EffortPolicy, ImageMode, OcrEnginePolicy, OcrMode, ReasoningEffort,
                    RunConfig, TargetLang)

PACKET_VERSION = "ordinary_formatting_review_packet_v1"
MAX_JSON = 8 * 1024 * 1024
MAX_INPUTS = 64 * 1024 * 1024
MAX_EVIDENCE = 256 * 1024 * 1024
_HASH = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_PACKET_KEYS = {"version", "run_dir", "review_profile", "reviewer_kind", "inputs_sha256"}
_GUIDE = """# Local formatting review

This packet is an unaccepted draft. Keep packet.json and review_inputs.json
unchanged. Edit formatting.json only. Inputs retain the exact source and target
parents, committed hashes, saved formatting preferences and source image paths.
No source fidelity, geometry or rendered layout acceptance is created here.

For every selected page, inspect the retained source image and both parent texts.
Author the image size/frame, fragments, region layout and document groups. Source
and target ranges are independently reviewed Unicode codepoint offsets, not
UTF-16 offsets or bytes. They must partition each parent completely and exactly;
trailing line separators belong to their preceding fragment. Hash each exact
UTF-8 slice with SHA-256. Fragment IDs are page-local p0001_f0001-style IDs in
reading order. Boxes are reviewed source pixel coordinates. Do not guess cuts,
boxes, roles, folios, document boundaries or target associations from appearance.

Submit requires the separately authored source review envelope, its decision
evidence bytes, the edited formatting manifest, and formatting decision evidence
bytes. For reviewed-image sources, also supply the directory containing every
candidate/manifest/blob file named and hash-bound by the source envelope. Relative
paths resolve inside that explicit evidence root; absolute paths must also stay
inside it. The original source envelope is retained unchanged.

Every command requires an explicit run and profile. Operator output also requires
actual operator source and formatting decisions. Submission creates a new owned
revision; inspect/rebuild require that exact revision ID. No latest-revision or
persisted selection is inferred. Missing saved preferences are errors; page breaks
and bidi settings are never switched. Unsupported profiles decline. Rebuild first
checks readiness and writes no DOCX when declined. Existing ordinary rebuild is
available through the existing app. A successful package still needs visual review.

Exit codes: 0 completed, 1 integrity/operation error, 2 invalid arguments,
3 reviewed profile declined. Commands acquire the run lock; the stable lock file
may remain after draft/inspect. An interrupted exclusive packet/revision directory
may remain incomplete and is never overwritten automatically.
"""


class FormattingReviewCLIError(ValueError):
    """Only fixed, content-free error codes leave this module."""


def _fail(code):
    raise FormattingReviewCLIError(code)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                _fail("duplicate_json_key")
            value[key] = item
        return value
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                       parse_constant=lambda _: _fail("nonfinite_json"))
    _encode(value)  # Reject overflowing exponents and invalid Unicode too.
    return value


def _direct_path(value, *, directory=False, within=None):
    path = Path(value).expanduser()
    if ".." in path.parts or str(path).startswith(("\\\\", "//")):
        _fail("nonlocal_or_unnormalized_path")
    path = path.absolute()
    for item in (path, *path.parents):
        info = item.lstat()
        if item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            _fail("linked_path")
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        _fail("invalid_path_type")
    resolved = path.resolve(strict=True)
    if within is not None and not resolved.is_relative_to(within):
        _fail("path_outside_evidence_root")
    return resolved


def _read(value, *, maximum=MAX_JSON, within=None):
    path = _direct_path(value, within=within)
    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    before = identity(path.stat())
    with path.open("rb") as stream:
        opened = identity(os.fstat(stream.fileno()))
        raw = stream.read(maximum + 1)
        after = identity(os.fstat(stream.fileno()))
    if len(raw) > maximum:
        _fail("local_file_too_large")
    if before != opened or opened != after or after != identity(_direct_path(path, within=within).stat()):
        _fail("local_file_changed")
    return raw


def _exclusive(path, raw):
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _saved_run(root):
    """Caller holds root's lock. Reconstruct only persisted fingerprint fields."""
    checkpoint = root / "run_state.json"
    raw = _read(checkpoint, maximum=MAX_INPUTS, within=root)
    payload = _decode(raw)
    if type(payload) is not dict or any(type(payload.get(key)) is not str or not payload[key]
            for key in ("pdf_path", "lang", "frozen_outdir_abs", "run_dir_abs", "run_started_at")):
        _fail("saved_run_identity_missing")
    state = load_run_state(checkpoint)
    if state is None or _read(checkpoint, maximum=MAX_INPUTS, within=root) != raw:
        _fail("checkpoint_unavailable_or_changed")
    if state.run_status.strip().lower() == "running":
        _fail("run_marked_running")
    if _direct_path(payload["run_dir_abs"], directory=True) != root:
        _fail("unsupported_run_redirect")
    settings = payload.get("settings")
    if type(settings) is not dict:
        _fail("saved_settings_missing")
    for key in ("page_breaks", "strip_bidi_controls", "keep_intermediates", "allow_xhigh_escalation"):
        if type(settings.get(key)) is not bool:
            _fail("saved_preferences_missing_or_invalid")
    for key in ("start_page", "workers"):
        if type(settings.get(key)) is not int:
            _fail("saved_selection_missing_or_invalid")
    for key in ("end_page", "max_pages"):
        if key not in settings or (settings[key] is not None and type(settings[key]) is not int):
            _fail("saved_selection_missing_or_invalid")
    if (not 1 <= settings["workers"] <= 6 or settings["start_page"] < 1
            or any(settings[key] is not None and settings[key] < 1 for key in ("end_page", "max_pages"))
            or (settings["end_page"] is not None and settings["end_page"] < settings["start_page"])):
        _fail("saved_selection_missing_or_invalid")
    for key in ("effort", "effort_policy", "image_mode", "ocr_mode", "ocr_engine",
                "ocr_api_base_url", "ocr_api_model", "glossary_file_path"):
        if type(settings.get(key)) is not str:
            _fail("saved_settings_missing_or_invalid")
    source = _direct_path(payload["pdf_path"])
    output = _direct_path(payload["frozen_outdir_abs"], directory=True)
    config = RunConfig(pdf_path=source, output_dir=output, target_lang=TargetLang(payload["lang"]),
        effort=ReasoningEffort(settings["effort"]), effort_policy=EffortPolicy(settings["effort_policy"]),
        image_mode=ImageMode(settings["image_mode"]), ocr_mode=OcrMode(settings["ocr_mode"]),
        ocr_engine=OcrEnginePolicy(settings["ocr_engine"]),
        ocr_api_base_url=settings["ocr_api_base_url"] or None, ocr_api_model=settings["ocr_api_model"] or None,
        glossary_file=_direct_path(settings["glossary_file_path"]) if settings["glossary_file_path"] else None,
        allow_xhigh_escalation=settings["allow_xhigh_escalation"], start_page=settings["start_page"],
        end_page=settings["end_page"], max_pages=settings["max_pages"], workers=settings["workers"],
        page_breaks=settings["page_breaks"], strip_bidi_controls=settings["strip_bidi_controls"],
        keep_intermediates=settings["keep_intermediates"])
    ordinary_identity = _ordinary_settings_identity(settings, state, root, source)
    restored = settings_fingerprint(config, ordinary_source_review=ordinary_identity)
    if ordinary_identity is not None and set(settings) != set(restored):
        _fail("saved_settings_not_reconstructable")
    if any(key not in settings or settings[key] != value for key, value in restored.items()):
        _fail("saved_settings_not_reconstructable")
    paths = build_run_paths(output, source, config.target_lang, run_started_at=state.run_started_at)
    if paths.run_dir != root:
        # Routing context is not checkpointed in the fingerprint. Never guess
        # Gmail scope or use a neighbouring run with the same source/language.
        _fail("unsupported_run_location")
    return config, state, raw


def _ordinary_settings_identity(settings, state, root, source):
    """Preserve the known opt-in identity and bind it to genuine saved commits."""
    if "ordinary_source_review" not in settings:
        return None
    value = settings["ordinary_source_review"]
    hashes = {"source_file_sha256", "source_review_sha256", "candidate_file_sha256",
              "manifest_file_sha256", "decision_evidence_sha256", "artifacts_sha256"}
    if (type(value) is not dict or set(value) != hashes | {"version", "revision_id", "reviewer_kind"}
            or value.get("version") != "ordinary_reviewed_source_context_v1"
            or type(value.get("revision_id")) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", value["revision_id"]) is None
            or value.get("reviewer_kind") not in {"operator_review", "ai_test_review"}
            or any(type(value.get(key)) is not str or _HASH.fullmatch(value[key]) is None for key in hashes)
            or state.protocol_identity.get("protocol") != "legal_blocks_v2"
            or value["source_file_sha256"] != state.pdf_fingerprint
            or _sha(_read(source, maximum=MAX_EVIDENCE)) != value["source_file_sha256"]):
        _fail("saved_source_review_identity_invalid")
    from .structured_artifacts import validate_structured_rebuild_page
    pages_dir = _direct_path(root / "pages", directory=True, within=root)
    for key, page in state.pages.items():
        if page.get("status") != "done":
            continue
        if page.get("ordinary_source_review") != value:
            _fail("saved_source_review_identity_changed")
        record, _ = validate_structured_rebuild_page(pages_dir, int(key),
            expected_commit=page.get("structured_commit"), protocol_identity=state.protocol_identity)
        target = _decode(_read(pages_dir / f"page_{int(key):04d}.structure.json", within=pages_dir))
        source_row = _decode(_read(pages_dir / f"page_{int(key):04d}.source_structure.json", within=pages_dir))
        metadata = record.get("page_result", {}).get("metadata", {})
        review = source_row.get("metadata", {}).get("reviewed_source", {})
        if (metadata.get("ordinary_source_review") != value
                or target.get("metadata", {}).get("ordinary_source_review") != value
                or review.get("candidate_file_sha256") != value["candidate_file_sha256"]
                or review.get("manifest_sha256") != value["manifest_file_sha256"]
                or review.get("review_kind") != value["reviewer_kind"]):
            _fail("saved_source_review_identity_changed")
    return value


def _unchanged_checkpoint(root, expected):
    if _read(root / "run_state.json", maximum=MAX_INPUTS, within=root) != expected:
        _fail("checkpoint_changed")


def _inputs(draft, config, checkpoint):
    result = {key: value for key, value in draft.items() if key != "formatting_manifest"}
    result["checkpoint_sha256"] = _sha(checkpoint)
    result["source_images"] = []
    physical = draft["binding"]["physical_source"]
    if "bundle_manifest_sha256" in physical:
        from .browser_pdf_bundle import browser_pdf_bundle_manifest_path
        path = _direct_path(browser_pdf_bundle_manifest_path(config.pdf_path))
        raw = _read(path)
        if _sha(raw) != physical["bundle_manifest_sha256"]:
            _fail("source_bundle_changed")
        pages = {row["page_number"]: row for row in _decode(raw)["pages"]}
        for page in draft["binding"]["pages"]:
            path_image = _direct_path(path.parent / pages[page["page_number"]]["image_path"], within=path.parent)
            image = _read(path_image, maximum=40 * 1024 * 1024, within=path.parent)
            if _sha(image) != page["source_identity"]["image_sha256"]:
                _fail("source_image_changed")
            result["source_images"].append({"page_number": page["page_number"],
                "path": str(path_image), "sha256": _sha(image)})
    return result


def _draft_packet(args, root, config, checkpoint, workflow):
    draft = workflow.begin_docx_formatting_review(config, reviewer_kind=args.reviewer_kind,
                                                 review_profile=args.profile)
    inputs = _encode(_inputs(draft, config, checkpoint))
    if len(inputs) > MAX_INPUTS:
        _fail("review_inputs_too_large")
    requested = Path(args.output).expanduser().absolute()
    if ".." in requested.parts:
        _fail("nonlocal_or_unnormalized_path")
    parent = _direct_path(requested.parent, directory=True)
    destination = parent / requested.name
    if destination.is_relative_to(root):
        _fail("packet_must_be_outside_run")
    packet = {"version": PACKET_VERSION, "run_dir": str(root), "review_profile": args.profile,
              "reviewer_kind": args.reviewer_kind, "inputs_sha256": _sha(inputs)}
    _unchanged_checkpoint(root, checkpoint)
    destination.mkdir(exist_ok=False)
    _exclusive(destination / "review_inputs.json", inputs)
    _exclusive(destination / "formatting.json", _encode(draft["formatting_manifest"]))
    _exclusive(destination / "README.md", _GUIDE.encode("utf-8"))
    _unchanged_checkpoint(root, checkpoint)
    _exclusive(destination / "packet.json", _encode(packet))  # Completion marker last.
    return {"status": "draft", "packet": str(destination), "notice_codes": draft["notice_codes"],
            "selected_pages": draft["binding"]["selected_pages"]}, 0


def _check_packet(args, root, config, checkpoint, workflow):
    folder = _direct_path(args.packet, directory=True)
    packet = _decode(_read(folder / "packet.json", within=folder))
    if (type(packet) is not dict or set(packet) != _PACKET_KEYS or packet["version"] != PACKET_VERSION
            or packet["run_dir"] != str(root) or packet["review_profile"] != args.profile
            or packet["reviewer_kind"] != args.reviewer_kind):
        _fail("review_packet_identity_changed")
    raw = _read(folder / "review_inputs.json", maximum=MAX_INPUTS, within=folder)
    if _sha(raw) != packet["inputs_sha256"]:
        _fail("review_packet_inputs_changed")
    draft = workflow.begin_docx_formatting_review(config, reviewer_kind=args.reviewer_kind,
                                                 review_profile=args.profile)
    if _encode(_decode(raw)) != _encode(_inputs(draft, config, checkpoint)):
        _fail("review_packet_stale")


def _source_evidence(envelope_raw, root_arg):
    from .reviewed_source import REVIEWED_ACCEPTANCE_VERSION, ReviewedSourceEvidence
    envelope = _decode(envelope_raw)
    if type(envelope) is not dict:
        _fail("invalid_source_review")
    if envelope.get("version") != REVIEWED_ACCEPTANCE_VERSION:
        if root_arg is not None:
            _fail("unexpected_source_evidence_root")
        return None
    if root_arg is None:
        _fail("source_evidence_root_required")
    root = _direct_path(root_arg, directory=True)
    blobs = envelope.get("evidence_files")
    if type(blobs) is not list or not 0 < len(blobs) <= 5000:
        _fail("invalid_source_evidence_inventory")
    paths, digests, contents, total = set(), set(), [], 0
    for index, row in enumerate([envelope.get("candidate_file"), envelope.get("manifest_file"), *blobs]):
        if (type(row) is not dict or set(row) != {"path", "sha256"}
                or type(row["path"]) is not str or not row["path"]
                or type(row["sha256"]) is not str or not _HASH.fullmatch(row["sha256"])):
            _fail("invalid_source_evidence_descriptor")
        path = _direct_path(root / row["path"], within=root)
        if path in paths or (index >= 2 and row["sha256"] in digests):
            _fail("duplicate_source_evidence")
        paths.add(path)
        if index >= 2:
            digests.add(row["sha256"])
        raw = _read(path, maximum=min(MAX_JSON if index < 2 else MAX_EVIDENCE, MAX_EVIDENCE - total), within=root)
        total += len(raw)
        if _sha(raw) != row["sha256"]:
            _fail("source_evidence_hash_changed")
        contents.append(raw)
    return ReviewedSourceEvidence(contents[0], contents[1],
                                  tuple((row["sha256"], raw) for row, raw in zip(blobs, contents[2:])))


def _prepared_result(prepared):
    return {"status": prepared.status, "revision_id": prepared.revision_id,
            "review_profile": prepared.review_profile, "notice_codes": list(prepared.notice_codes),
            "selected_pages": list(prepared.selected_pages), "layout_review_required": True,
            "rendered_layout_acceptance": "not_evaluated"}


def execute(args):
    root = _direct_path(args.run, directory=True)
    with run_workspace_slot(root):
        config, state, checkpoint = _saved_run(root)
        # Supplying an empty settings mapping prevents ambient preference reads.
        from .workflow import TranslationWorkflow
        workflow = TranslationWorkflow(gui_settings={}, log_callback=lambda _: None)
        if args.command == "draft":
            return _draft_packet(args, root, config, checkpoint, workflow)
        if args.command == "submit":
            _check_packet(args, root, config, checkpoint, workflow)
            source = _read(args.source_review)
            evidence = _source_evidence(source, args.source_evidence_root)
            decision, manifest, formatting_decision = (_read(args.source_decision_evidence),
                _read(args.manifest), _read(args.formatting_evidence))
            _unchanged_checkpoint(root, checkpoint)
            revision = workflow.submit_docx_formatting_review(config, reviewer_kind=args.reviewer_kind,
                review_profile=args.profile, source_review=source, source_evidence=evidence,
                source_review_evidence=decision, formatting_manifest=manifest, review_evidence=formatting_decision)
        else:
            revision = args.revision
        prepared = prepare_run_docx_formatting(root, config, state, revision_id=revision, review_profile=args.profile)
        _unchanged_checkpoint(root, checkpoint)
        result = _prepared_result(prepared)
        if args.command == "submit":
            result["status"] = "submitted"
            result["assembly_status"] = prepared.status
        if prepared.status != "ready":
            return result, 3
        if args.command == "rebuild":
            output = workflow.rebuild_docx(config, formatting_revision_id=revision,
                                          formatting_review_profile=args.profile)
            from .reviewed_formatting_writer import validate_reviewed_docx
            validate_reviewed_docx(_read(output, maximum=32 * 1024 * 1024),
                _read(output.with_suffix(".source_map.json")), projection=prepared.projection,
                expected_reviewer_kind=prepared.expected_reviewer_kind)
            result.update(status="rebuilt", output_docx=str(output), provider_dispatch_count=0)
        return result, 0


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        _fail("invalid_arguments")


def build_arg_parser():
    parser = _Parser(prog="python -m legalpdf_translate.formatting_review_cli",
        description="Explicit local formatting review using saved run preferences; no API/OCR/native dispatch.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("draft", "submit", "inspect", "rebuild"):
        command = commands.add_parser(name)
        command.add_argument("--run", required=True, help="Self-owned ordinary run directory containing run_state.json.")
        command.add_argument("--profile", required=True, choices=[STRICT_REVIEW_PROFILE, OPERATOR_REVIEW_PROFILE])
        if name in {"draft", "submit"}:
            command.add_argument("--reviewer-kind", required=True, choices=["ai_test_review", "operator_review"])
        if name == "draft":
            command.add_argument("--output", required=True, help="New packet directory outside the run; existing parent required.")
        elif name == "submit":
            command.add_argument("--packet", required=True, help="Unmodified draft packet directory.")
            command.add_argument("--manifest", required=True, help="Explicitly reviewed formatting JSON.")
            command.add_argument("--source-review", required=True, help="Original source review envelope JSON.")
            command.add_argument("--source-decision-evidence", required=True)
            command.add_argument("--formatting-evidence", required=True)
            command.add_argument("--source-evidence-root", help="Required for reviewed-image candidate/manifest/blob files.")
        else:
            command.add_argument("--revision", required=True, help="Exact previously submitted revision ID.")
    return parser


def main(argv=None):
    try:
        args = build_arg_parser().parse_args(argv)
        result, code = execute(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return code
    except FormattingReviewCLIError as exc:
        code = str(exc)
        print(json.dumps({"status": "error", "code": code}), file=sys.stderr)
        return 2 if code == "invalid_arguments" else 1
    except RunWorkspaceBusy:
        print('{"status":"error","code":"run_busy"}', file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print('{"status":"error","code":"interrupted"}', file=sys.stderr)
        return 130
    except Exception:
        # Source text, paths and arbitrary validator messages never become CLI errors.
        print('{"status":"error","code":"formatting_review_failed"}', file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
