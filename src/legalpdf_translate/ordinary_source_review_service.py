"""Explicit local source acquisition and operator decisions for ordinary runs.

No tooling/private acceptance authority, provider engine, ambient preferences or
automatic approval. Callers resolve the saved RunConfig; browser input supplies
typed review decisions and opaque IDs only, never hashes or evidence paths.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from .browser_pdf_bundle import browser_pdf_bundle_manifest_path
from .checkpoint import build_run_paths, settings_fingerprint
from .document_structure import rebind_page_structure
from .ocr_engine import LocalOcrEvidence, LocalTesseractEngine
from .ordinary_reviewed_source import OrdinaryReviewedSourceContext
from .reviewed_source import ReviewedSourceEvidence, adapt_reviewed_candidate
from .run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
from .source_readiness import source_readiness_diagnostics, source_structure_digest
from .source_review_candidate import build_candidate, canonical_json, _png_size, _variant, _actions, _review
from .structured_artifacts import _publish_file_exclusive
from .types import OcrMode, OcrEnginePolicy, RunConfig

VERSION = "ordinary_source_review_service_v1"
_SUBMISSION_VERSION = "ordinary_source_submission_v1"
_MAX_JSON = 8_000_000
_MAX_FILE = 64_000_000
_MAX_TOTAL = 256_000_000
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}\Z")
_HASH = re.compile(r"[a-f0-9]{64}\Z")


class SourceReviewServiceError(ValueError):
    """Content-free acquisition, ownership or review failure."""


def _fail(code):
    raise SourceReviewServiceError("source_review_" + code) from None


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _identifier(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        _fail("invalid_id")
    return value


def _direct(path, *, directory=False):
    if ".." in Path(path).parts or str(path).startswith(("\\\\", "//")):
        _fail("nonlocal_or_unnormalized_path")
    path = Path(os.path.abspath(path))
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        if item.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            _fail("indirect_path")
    info = path.lstat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        _fail("invalid_path")
    if not directory and getattr(info, "st_nlink", 1) != 1:
        _fail("indirect_file")
    return path


def _read(path, *, maximum=_MAX_JSON):
    path = _direct(path)
    def identity(info):
        return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns
    before = identity(path.stat())
    if not 0 <= before[2] <= maximum:
        _fail("file_changed_or_too_large")
    with path.open("rb") as stream:
        opened = identity(os.fstat(stream.fileno()))
        raw = stream.read(before[2] + 1)
        after = identity(os.fstat(stream.fileno()))
    if len(raw) != before[2] or len(raw) > maximum or before != opened or after != opened or identity(_direct(path).stat()) != after:
        _fail("file_changed_or_too_large")
    return raw


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("duplicate_key")
            result[key] = value
        return result
    def invalid(_):
        _fail("nonfinite_json")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    canonical_json(value)
    return value


def _write(path, raw):
    _direct(path.parent, directory=True)
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_FILE:
        _fail("invalid_object")
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if _read(path, maximum=_MAX_FILE) != raw:
        _fail("publication_changed")


def _mkdir(path):
    _direct(path.parent, directory=True)
    path.mkdir(exist_ok=True)
    return _direct(path, directory=True)


def _publish(path, raw):
    """Exact repeat or atomic no-clobber publication under the owning run lock."""
    _direct(path.parent, directory=True)
    if type(raw) is not bytes or not 0 < len(raw) <= _MAX_JSON:
        _fail("invalid_publication")
    if os.path.lexists(path):
        if _read(path) != raw:
            _fail("publication_changed")
        return
    # This existing production helper uses non-replacing Windows rename or an
    # exclusive POSIX link. A concurrent target can never be overwritten.
    _publish_file_exclusive(path, raw)
    if _read(path) != raw:
        _fail("publication_changed")


@dataclass(frozen=True, slots=True)
class SourceReviewAction:
    id: str
    kind: str
    baseline_block_ids: tuple[str, ...]
    after_text: str
    region_px: tuple[float, float, float, float]
    rationale: str


@dataclass(frozen=True, slots=True)
class SourceReviewFinding:
    id: str
    category: str
    status: str
    action_ids: tuple[str, ...]
    rationale: str


@dataclass(frozen=True, slots=True)
class SourcePageDecision:
    actions: tuple[SourceReviewAction, ...]
    reading_order: tuple[str, ...]
    full_page_review_completed: bool
    reading_order_reviewed: bool
    boundary_decision: str
    boundary_rationale: str
    findings: tuple[SourceReviewFinding, ...]
    reviewer: str


class OrdinarySourceReviewService:
    """One saved config/run owner. Methods return content-bearing local views.

    Views may be rendered safely as text and image bytes by a future local UI;
    they are not diagnostics and must not be logged. No arbitrary path input is
    accepted by any operation after the trusted backend creates this service.
    """

    def __init__(self, config: RunConfig):
        try:
            if type(config) is not RunConfig:
                _fail("config_required")
            self._config = replace(deepcopy(config),
                pdf_path=_direct(config.pdf_path), output_dir=_direct(config.output_dir, directory=True))
            if (type(config.workers) is not int or not 1 <= config.workers <= 6
                    or type(config.page_breaks) is not bool or type(config.keep_intermediates) is not bool):
                _fail("invalid_saved_settings")
            paths = build_run_paths(self._config.output_dir, self._config.pdf_path, config.target_lang,
                                    gmail_batch_context=self._config.gmail_batch_context)
            self.run_dir = paths.run_dir
            self._root = self.run_dir / "source_reviews"
            settings = settings_fingerprint(self._config)
            self._owner = {"run_dir": str(self.run_dir), "source_path": str(self._config.pdf_path),
                "target_lang": config.target_lang.value, "settings": settings,
                "ocr_api_provider": config.ocr_api_provider.value}
        except SourceReviewServiceError:
            raise
        except Exception:
            _fail("invalid_saved_config")

    @contextmanager
    def _scope(self, *, create=False, idle=True):
        try:
            with run_workspace_slot(self.run_dir, create=create):
                self._check_checkpoint(idle=idle)
                yield
        except SourceReviewServiceError:
            raise
        except RunWorkspaceBusy:
            raise
        except Exception:
            _fail("operation_failed")

    def _check_checkpoint(self, *, idle=False, context_identity=None):
        path = self.run_dir / "run_state.json"
        if not path.exists():
            return
        # Atomic progress replacement is allowed while workers verify evidence.
        # Read one coherent opened file, not three potentially different states.
        _direct(path)
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            raw = stream.read(_MAX_JSON + 1)
            after = os.fstat(stream.fileno())
        if (not stat.S_ISREG(before.st_mode) or getattr(before, "st_nlink", 1) != 1
                or before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns
                or len(raw) > _MAX_JSON):
            _fail("checkpoint_changed")
        state = _decode(raw)
        if (Path(state["run_dir_abs"]) != self.run_dir or Path(state["pdf_path"]) != self._config.pdf_path
                or state["lang"] != self._owner["target_lang"]):
            _fail("run_owner_changed")
        if idle and str(state["run_status"]).lower() == "running":
            _fail("run_busy")
        expected = self._owner["settings"]
        # The selected source identity is independently checked by Workflow;
        # every saved preference must still match this service's original owner.
        if any(state["settings"].get(key) != value for key, value in expected.items()):
            _fail("saved_settings_changed")
        if context_identity is not None and state["settings"].get("ordinary_source_review") != context_identity:
            _fail("selected_context_changed")

    def _snapshot(self):
        source = self._config.pdf_path
        if source.suffix.lower() != ".pdf":
            _fail("full_browser_source_required")
        raw_source = _read(source, maximum=_MAX_FILE)
        manifest_path = browser_pdf_bundle_manifest_path(source)
        raw_manifest = _read(manifest_path)
        bundle = _decode(raw_manifest)
        count = bundle.get("page_count")
        if (type(count) is not int or not 1 <= count <= 5000
                or bundle.get("source_path") != str(source)
                or bundle.get("source_size_bytes") != source.stat().st_size
                or bundle.get("source_mtime_ns") != source.stat().st_mtime_ns):
            _fail("browser_bundle_changed")
        rows = bundle.get("pages")
        if type(rows) is not list or [r.get("page_number") for r in rows] != list(range(1, count + 1)):
            _fail("full_browser_source_required")
        artifacts = {_sha(raw_source): raw_source, _sha(raw_manifest): raw_manifest}
        retained_bytes = len(raw_source) + len(raw_manifest)
        images, identities, sizes = {}, {}, {}
        for row in rows:
            relative = Path(row["image_path"])
            if relative.is_absolute() or ".." in relative.parts:
                _fail("image_path_invalid")
            path = _direct(manifest_path.parent / relative)
            if not path.is_relative_to(manifest_path.parent):
                _fail("image_path_invalid")
            if retained_bytes >= _MAX_TOTAL:
                _fail("evidence_too_large")
            image = _read(path, maximum=min(_MAX_FILE, _MAX_TOTAL - retained_bytes))
            retained_bytes += len(image)
            size = _png_size(image)
            n = row["page_number"]
            images[n] = image
            artifacts[_sha(image)] = image
            identities[n] = {"source_file_sha256": _sha(raw_source), "image_sha256": _sha(image),
                "source_type": "browser_pdf_image", "paper_size_basis": "a4_assumed"}
            sizes[n] = (595.276, 841.89)
            if row.get("width_px") != size[0] or row.get("height_px") != size[1]:
                _fail("image_size_changed")
        if sum(map(len, artifacts.values())) > _MAX_TOTAL:
            _fail("evidence_too_large")
        binding = {"source_sha256": _sha(raw_source), "bundle_sha256": _sha(raw_manifest),
            "pages": [{"page_number": n, "identity": identities[n], "size": list(sizes[n])} for n in images]}
        return binding, artifacts, images, identities, sizes

    def _object(self, raw, *, atomic=False):
        key = _sha(raw)
        path = self._root / "objects" / key
        if path.exists():
            if _read(path, maximum=_MAX_FILE) != raw:
                _fail("object_changed")
        else:
            (_publish if atomic else _write)(path, raw)
        return key

    def _objects(self, keys):
        if type(keys) is not list or not 0 < len(keys) <= 50_000 or len(set(keys)) != len(keys):
            _fail("invalid_objects")
        result, total = {}, 0
        for key in keys:
            if type(key) is not str or _HASH.fullmatch(key) is None:
                _fail("invalid_object_id")
            if total >= _MAX_TOTAL:
                _fail("evidence_too_large")
            raw = _read(self._root / "objects" / key, maximum=min(_MAX_FILE, _MAX_TOTAL - total))
            total += len(raw)
            if _sha(raw) != key or total > _MAX_TOTAL:
                _fail("object_changed_or_too_large")
            result[key] = raw
        return result

    def _draft(self, draft_id):
        directory = _direct(self._root / "drafts" / _identifier(draft_id), directory=True)
        generations = sorted(directory.glob("[0-9][0-9][0-9][0-9][0-9][0-9].json"))
        if not generations:
            _fail("draft_missing")
        raw = _read(generations[-1])
        draft = _decode(raw)
        if (draft.get("version") != VERSION or draft.get("draft_id") != draft_id
                or draft.get("owner") != self._owner
                or type(draft.get("generation")) is not int
                or generations[-1].stem != f"{draft['generation']:06d}"):
            _fail("draft_owner_changed")
        binding, _, _, identities, sizes = self._snapshot()
        if draft["binding"] != binding:
            _fail("source_changed")
        self._objects(draft["artifacts"])
        return draft, raw, directory, identities, sizes

    def prepare(self) -> dict:
        """Retain a genuine local baseline; never dispatch paid fallback OCR."""
        config = self._config
        if config.ocr_mode == OcrMode.OFF:
            return {"status": "declined", "notice_codes": ["source_review_ocr_disabled"]}
        if config.ocr_engine not in {OcrEnginePolicy.LOCAL, OcrEnginePolicy.LOCAL_THEN_API}:
            return {"status": "declined", "notice_codes": ["source_review_local_baseline_unavailable"]}
        if not config.keep_intermediates:
            return {"status": "declined", "notice_codes": ["source_review_retained_evidence_required"]}
        if config.pdf_path.suffix.lower() != ".pdf" or not browser_pdf_bundle_manifest_path(config.pdf_path).exists():
            return {"status": "declined", "notice_codes": ["source_review_full_browser_source_required"]}
        with self._scope(create=True):
            binding, artifacts, images, _, sizes = self._snapshot()
            count = len(images)
            if config.start_page != 1 or config.end_page not in {None, count} or config.max_pages not in {None, count}:
                return {"status": "declined", "notice_codes": ["source_review_full_selection_required"]}
            engine = LocalTesseractEngine(strict_unavailable=False)
            if not engine.is_available:
                return {"status": "declined", "notice_codes": ["source_review_local_baseline_unavailable"]}
            pages = []
            for n, image in images.items():
                result = engine.ocr_image(image, lang_hint=config.target_lang.value,
                                          source_type="pdf", preserve_structure=True,
                                          retain_local_evidence=True)
                evidence = result.local_evidence
                if (result.engine != "local" or result.failed_reason or not result.text
                        or type(evidence) is not LocalOcrEvidence or result.structure is None):
                    return {"status": "declined", "notice_codes": ["source_review_local_evidence_unavailable"]}
                if (evidence.image_sha256 != _sha(image) or evidence.selected_pass != result.selected_pass
                        or _decode(evidence.structure_bytes) != result.structure
                        or evidence.text_bytes.decode("utf-8").strip() != result.text):
                    _fail("local_evidence_changed")
                original = _decode(evidence.structure_bytes)
                source = rebind_page_structure(original, page_number=n,
                    source_file_sha256=binding["source_sha256"], page_size=sizes[n])
                source.metadata["source_page_identity"] = binding["pages"][n - 1]["identity"]
                # Candidate v1 binds selected TXT after newline normalization;
                # original renderer TXT and original engine structure remain
                # separately retained unchanged, including CRLF bytes.
                selected = evidence.text_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").strip()
                source.metadata["selected_text_sha256"] = _sha(selected.encode("utf-8"))
                raw_structure = canonical_json(source.to_dict())
                for raw in (evidence.text_bytes, evidence.tsv_bytes, evidence.structure_bytes, raw_structure):
                    if type(raw) is not bytes or len(raw) > _MAX_JSON:
                        _fail("local_evidence_too_large")
                    if _sha(raw) not in artifacts and sum(map(len, artifacts.values())) + len(raw) > _MAX_TOTAL:
                        _fail("evidence_too_large")
                    artifacts[_sha(raw)] = raw
                page = {"page_number": n, "image_sha256": _sha(image), "image_size_px": _png_size(image),
                    "variants": [{"id": "baseline", "text_sha256": _sha(evidence.text_bytes),
                        "tsv_sha256": _sha(evidence.tsv_bytes), "structure_sha256": _sha(raw_structure)}],
                    "baseline_variant": "baseline", "actions": [], "reading_order": [], "review_evidence_sha256": ""}
                _variant(page["variants"][0], page, binding["source_sha256"], artifacts)
                pages.append({"page": page, "original_structure_sha256": _sha(evidence.structure_bytes),
                    "selected_pass": evidence.selected_pass, "decision": None})
            if self._snapshot()[0] != binding:
                _fail("source_changed")
            if sum(map(len, artifacts.values())) > _MAX_TOTAL:
                _fail("evidence_too_large")
            _mkdir(self._root)
            for name in ("objects", "drafts", "revisions"):
                _mkdir(self._root / name)
            draft_id = uuid4().hex
            directory = _mkdir(self._root / "drafts" / draft_id)
            for raw in artifacts.values():
                self._object(raw)
            draft = {"version": VERSION, "draft_id": draft_id, "generation": 1,
                "owner": self._owner, "binding": binding, "artifacts": sorted(artifacts), "pages": pages}
            _write(directory / "000001.json", canonical_json(draft))
            return self._view(draft)

    def _view(self, draft):
        artifacts = self._objects(draft["artifacts"])
        pages = []
        for row in draft["pages"]:
            page = row["page"]
            variant = page["variants"][0]
            source = _decode(artifacts[variant["structure_sha256"]])
            # Word boxes remain genuine baseline evidence; no review is inferred.
            pages.append({"page_number": page["page_number"], "image_bytes": artifacts[page["image_sha256"]],
                "image_size_px": page["image_size_px"], "baseline_text": artifacts[variant["text_sha256"]].decode("utf-8"),
                "baseline_blocks": source["blocks"], "word_evidence": source["metadata"]["ocr_word_evidence"],
                "selected_pass": row["selected_pass"], "decision": deepcopy(row["decision"])})
        return {"status": "draft", "draft_id": draft["draft_id"], "generation": draft["generation"],
            "reviewer_kind": "operator_review", "notice_codes": [], "pages": pages}

    def read(self, draft_id) -> dict:
        with self._scope():
            draft, raw, directory, identities, sizes = self._draft(draft_id)
            view = self._view(draft)
            submission = self._submission(draft, raw, directory, identities, sizes)
            view["submitted"] = submission is not None and submission["complete"]
            if submission is not None:
                intent = submission["intent"]
                view["submission"] = {"status": "completed" if submission["complete"] else "pending",
                    "revision_id": intent["revision_id"], "generation": intent["generation"],
                    "reviewer": intent["reviewer"]}
            return view

    def _page_decision(self, row, decision, document, artifacts):
        if (type(decision) is not SourcePageDecision or type(decision.actions) is not tuple
                or type(decision.findings) is not tuple or type(decision.reading_order) is not tuple
                or len(decision.actions) > 5000 or len(decision.findings) > 5000):
            _fail("invalid_decision")
        page = deepcopy(row["page"])
        baseline, boxes = _variant(page["variants"][0], page, document, artifacts)
        actions = []
        for action in decision.actions:
            if (type(action) is not SourceReviewAction or type(action.baseline_block_ids) is not tuple
                    or type(action.region_px) is not tuple or any(key not in baseline for key in action.baseline_block_ids)):
                _fail("invalid_action")
            before = "\n".join(baseline[key] for key in action.baseline_block_ids)
            actions.append({"id": action.id, "kind": action.kind,
                "baseline_block_ids": list(action.baseline_block_ids), "before_text": before,
                "before_sha256": _sha(before.encode()), "after_text": action.after_text,
                "after_sha256": _sha(action.after_text.encode()), "region_px": list(action.region_px),
                "evidence_refs": ([{"variant_id": "baseline", "block_ids": list(action.baseline_block_ids)}]
                    if action.baseline_block_ids else []), "rationale": action.rationale})
        page["actions"], page["reading_order"] = actions, list(decision.reading_order)
        validated, _ = _actions(page, {"baseline": (baseline, boxes)})
        findings = []
        for finding in decision.findings:
            if type(finding) is not SourceReviewFinding or type(finding.action_ids) is not tuple:
                _fail("invalid_finding")
            findings.append({**asdict(finding), "action_ids": list(finding.action_ids)})
        review = {"version": 1, "kind": "image_source_review", "review_kind": "operator_review",
            "reviewer": decision.reviewer, "document_sha256": document, "page_number": page["page_number"],
            "image_sha256": page["image_sha256"], "page_plan_sha256": _sha(canonical_json(
                {key: value for key, value in page.items() if key != "review_evidence_sha256"})),
            "full_page_review_completed": decision.full_page_review_completed,
            "reading_order_reviewed": decision.reading_order_reviewed,
            "boundary": {"decision": decision.boundary_decision, "rationale": decision.boundary_rationale},
            "findings": findings}
        raw = canonical_json(review)
        artifacts[_sha(raw)] = raw
        page["review_evidence_sha256"] = _sha(raw)
        _review(page, document, validated, artifacts)
        return {**row, "page": page, "decision": {**asdict(decision), "reviewer_kind": "operator_review"}}

    def save_page(self, draft_id, *, expected_generation: int, page_number: int,
                  decision: SourcePageDecision) -> dict:
        with self._scope():
            draft, _, directory, _, _ = self._draft(draft_id)
            self._editable(draft, directory, expected_generation)
            if type(page_number) is not int or not 1 <= page_number <= len(draft["pages"]):
                _fail("invalid_page")
            artifacts = self._objects(draft["artifacts"])
            draft["pages"][page_number - 1] = self._page_decision(draft["pages"][page_number - 1],
                decision, draft["binding"]["source_sha256"], artifacts)
            for raw in artifacts.values():
                self._object(raw)
            draft["artifacts"], draft["generation"] = sorted(artifacts), draft["generation"] + 1
            if draft["generation"] > 999999:
                _fail("generation_limit")
            _write(directory / f"{draft['generation']:06d}.json", canonical_json(draft))
            return self._view(draft)

    def _editable(self, draft, directory, expected):
        if type(expected) is not int or expected != draft["generation"]:
            _fail("stale_generation")
        if (directory / "submitted.json").exists():
            _fail("draft_submitted")
        if os.path.lexists(directory / "submit_intent.json"):
            _fail("draft_submission_pending")

    def _validate_submission(self, intent, draft, draft_raw, identities, sizes, *, verify=True):
        intent_keys = {"version", "draft_id", "generation", "draft_sha256", "owner", "reviewer",
                       "accept_source", "revision_id", "revision_sha256", "revision"}
        marker_keys = {"version", "revision_id", "draft_id", "generation", "draft_sha256", "owner",
                       "binding", "artifacts", "context_identity", "candidate", "manifest", "decision", "envelope"}
        if (type(intent) is not dict or set(intent) != intent_keys
                or intent["version"] != _SUBMISSION_VERSION or intent["accept_source"] is not True
                or type(intent["generation"]) is not int or intent["generation"] != draft["generation"]
                or intent["draft_id"] != draft["draft_id"] or intent["draft_sha256"] != _sha(draft_raw)
                or canonical_json(intent["owner"]) != canonical_json(self._owner)
                or type(intent["reviewer"]) is not str or not intent["reviewer"].strip()
                or len(intent["reviewer"]) > 1000 or type(intent["revision_id"]) is not str
                or re.fullmatch(r"[a-f0-9]{32}", intent["revision_id"]) is None):
            _fail("submission_intent_changed")
        marker = intent["revision"]
        if (type(marker) is not dict or set(marker) not in (marker_keys, marker_keys | {"submission_version"})
                or ("submission_version" in marker and marker["submission_version"] != _SUBMISSION_VERSION)
                or marker["version"] != VERSION
                or marker["revision_id"] != intent["revision_id"] or marker["draft_id"] != draft["draft_id"]
                or type(marker["generation"]) is not int or marker["generation"] != draft["generation"]
                or marker["draft_sha256"] != _sha(draft_raw)
                or canonical_json(marker["owner"]) != canonical_json(self._owner)
                or canonical_json(marker["binding"]) != canonical_json(draft["binding"])
                or canonical_json(marker["artifacts"]) != canonical_json(draft["artifacts"])):
            _fail("submission_revision_changed")
        marker_raw = canonical_json(marker)
        if intent["revision_sha256"] != _sha(marker_raw):
            _fail("submission_revision_changed")
        artifacts = self._objects(marker["artifacts"])
        outputs = self._objects([marker[key] for key in ("candidate", "manifest", "decision", "envelope")])
        expected_manifest = {"version": 1, "kind": "source_review_candidate_manifest",
            "document_sha256": draft["binding"]["source_sha256"], "pages": [row["page"] for row in draft["pages"]]}
        if outputs[marker["manifest"]] != canonical_json(expected_manifest):
            _fail("submission_evidence_changed")
        decision = _decode(outputs[marker["decision"]])
        if (type(decision) is not dict or type(decision.get("recorded_at")) is not str
                or not decision["recorded_at"] or len(decision["recorded_at"]) > 100
                or type(decision.get("generation")) is not int):
            _fail("submission_decision_changed")
        expected_decision = {"version": VERSION, "kind": "explicit_operator_source_acceptance",
            "reviewer_kind": "operator_review", "reviewer": intent["reviewer"], "accept_source": True,
            "draft_id": draft["draft_id"], "generation": draft["generation"], "draft_sha256": _sha(draft_raw),
            "owner": self._owner, "source_sha256": draft["binding"]["source_sha256"],
            "candidate_sha256": marker["candidate"], "manifest_sha256": marker["manifest"],
            "recorded_at": decision["recorded_at"]}
        if outputs[marker["decision"]] != canonical_json(expected_decision):
            _fail("submission_decision_changed")
        evidence = ReviewedSourceEvidence(outputs[marker["candidate"]], outputs[marker["manifest"]],
            tuple(sorted(artifacts.items())))
        context = OrdinaryReviewedSourceContext(marker["revision_id"], "operator_review", outputs[marker["envelope"]],
            evidence, outputs[marker["decision"]], lambda: None)
        if canonical_json(context.identity) != canonical_json(marker["context_identity"]):
            _fail("submission_context_changed")
        if verify:
            context.verify(source_hash=draft["binding"]["source_sha256"], page_identities=identities, page_sizes=sizes)
        return marker_raw

    def _submission(self, draft, draft_raw, directory, identities, sizes, *, verify=True):
        intent_path, receipt_path = directory / "submit_intent.json", directory / "submitted.json"
        legacy = not os.path.lexists(intent_path)
        if legacy:
            if not os.path.lexists(receipt_path):
                return None
            receipt = _decode(_read(receipt_path))
            if (type(receipt) is not dict or set(receipt) != {"revision_id", "generation", "revision_sha256"}
                    or type(receipt["generation"]) is not int or type(receipt["revision_id"]) is not str
                    or re.fullmatch(r"[a-f0-9]{32}", receipt["revision_id"]) is None):
                _fail("submitted_generation_changed")
            revision_path = self._root / "revisions" / (receipt["revision_id"] + ".json")
            if not os.path.lexists(revision_path):
                _fail("legacy_submission_incomplete")
            marker = _decode(_read(revision_path))
            if "submission_version" in marker:
                _fail("submission_intent_missing")
            decision = _decode(self._objects([marker["decision"]])[marker["decision"]])
            # An in-memory verification view of the exact complete old record;
            # never publish a new intent or reconstruct an orphan legacy record.
            intent = {"version": _SUBMISSION_VERSION, "draft_id": draft["draft_id"],
                "generation": receipt["generation"], "draft_sha256": _sha(draft_raw), "owner": self._owner,
                "reviewer": decision["reviewer"], "accept_source": True, "revision_id": receipt["revision_id"],
                "revision_sha256": receipt["revision_sha256"], "revision": marker}
        else:
            intent = _decode(_read(intent_path))
        marker_raw = self._validate_submission(intent, draft, draft_raw, identities, sizes, verify=verify)
        receipt_raw = canonical_json({"revision_id": intent["revision_id"], "generation": intent["generation"],
                                      "revision_sha256": _sha(marker_raw)})
        revision_path = self._root / "revisions" / (intent["revision_id"] + ".json")
        complete = True
        for path, expected in ((receipt_path, receipt_raw), (revision_path, marker_raw)):
            if os.path.lexists(path):
                if _read(path) != expected:
                    _fail("publication_changed")
            else:
                complete = False
        return {"intent": intent, "marker_raw": marker_raw, "receipt_raw": receipt_raw,
                "complete": complete, "legacy": legacy}

    def _fresh_submission_draft(self, draft, draft_raw):
        current = self._draft(draft["draft_id"])
        if (current[1] != draft_raw or current[0]["draft_id"] != draft["draft_id"]
                or current[0]["generation"] != draft["generation"]):
            _fail("submission_draft_changed")
        return current

    def _finish_submission(self, draft, draft_raw, directory, identities, sizes, submission):
        intent = submission["intent"]
        for path, raw in ((directory / "submitted.json", submission["receipt_raw"]),
                          (self._root / "revisions" / (intent["revision_id"] + ".json"), submission["marker_raw"])):
            fresh = self._fresh_submission_draft(draft, draft_raw)
            current = self._submission(*fresh)
            if current is None or canonical_json(current["intent"]) != canonical_json(intent):
                _fail("submission_intent_changed")
            # Validation above may perform substantial I/O. Re-read the exact
            # selected generation again immediately before publishing bytes.
            self._fresh_submission_draft(draft, draft_raw)
            _publish(path, raw)
        fresh = self._fresh_submission_draft(draft, draft_raw)
        current = self._submission(*fresh)
        if (current is None or not current["complete"]
                or canonical_json(current["intent"]) != canonical_json(intent)):
            _fail("submission_intent_changed")
        self._fresh_submission_draft(draft, draft_raw)
        return {"status": "submitted", "revision_id": intent["revision_id"], "draft_id": draft["draft_id"],
                "generation": draft["generation"], "reviewer_kind": "operator_review", "notice_codes": []}

    def submit(self, draft_id, *, expected_generation: int, reviewer: str, accept_source: bool) -> dict:
        with self._scope():
            draft, draft_raw, directory, identities, sizes = self._draft(draft_id)
            if type(expected_generation) is not int or expected_generation != draft["generation"]:
                _fail("stale_generation")
            if accept_source is not True or type(reviewer) is not str or not reviewer.strip() or len(reviewer) > 1000:
                _fail("explicit_acceptance_required")
            submission = self._submission(draft, draft_raw, directory, identities, sizes)
            if submission is not None:
                if submission["intent"]["reviewer"] != reviewer:
                    _fail("submission_intent_changed")
                return self._finish_submission(draft, draft_raw, directory, identities, sizes, submission)
            self._editable(draft, directory, expected_generation)
            if any(row["decision"] is None for row in draft["pages"]):
                _fail("review_incomplete")
            artifacts = self._objects(draft["artifacts"])
            manifest = {"version": 1, "kind": "source_review_candidate_manifest",
                "document_sha256": draft["binding"]["source_sha256"], "pages": [row["page"] for row in draft["pages"]]}
            manifest_raw = canonical_json(manifest)
            candidate = build_candidate(manifest_raw, expected_manifest_sha256=_sha(manifest_raw),
                document_sha256=manifest["document_sha256"], page_numbers=tuple(identities),
                artifacts=artifacts, require_complete=True)
            candidate_raw = canonical_json(candidate)
            evidence = ReviewedSourceEvidence(candidate_raw, manifest_raw, tuple(sorted(artifacts.items())))
            sources = adapt_reviewed_candidate(evidence, candidate_sha256=_sha(candidate_raw),
                manifest_sha256=_sha(manifest_raw), source_hash=manifest["document_sha256"],
                page_identities=identities, page_sizes=sizes)
            revision_id = uuid4().hex
            decision_raw = canonical_json({"version": VERSION, "kind": "explicit_operator_source_acceptance",
                "reviewer_kind": "operator_review", "reviewer": reviewer, "accept_source": True,
                "draft_id": draft_id, "generation": expected_generation, "draft_sha256": _sha(draft_raw),
                "owner": self._owner, "source_sha256": manifest["document_sha256"],
                "candidate_sha256": _sha(candidate_raw), "manifest_sha256": _sha(manifest_raw),
                "recorded_at": datetime.now(UTC).isoformat()})
            def descriptor(raw):
                key = _sha(raw)
                return {"path": str(self._root / "objects" / key), "sha256": key}
            envelope_raw = canonical_json({"version": "reviewed_source_acceptance_v1", "review_kind": "operator_review",
                "review_evidence_sha256": _sha(decision_raw), "source_file_sha256": manifest["document_sha256"],
                "candidate_file": descriptor(candidate_raw), "manifest_file": descriptor(manifest_raw),
                "evidence_files": [descriptor(raw) for _, raw in evidence.artifacts],
                "pages": [{"page_number": n, "reviewed_source_sha256": source_structure_digest(source),
                    "readiness_sha256": _sha(canonical_json(source_readiness_diagnostics(source))),
                    "source_fidelity": "accepted", "document_boundary": "accepted", "unresolved_findings": []}
                    for n, source in sources.items()]})
            # Complete verification precedes any accepted revision publication.
            context = OrdinaryReviewedSourceContext(revision_id, "operator_review", envelope_raw,
                evidence, decision_raw, lambda: None)
            context.verify(source_hash=manifest["document_sha256"], page_identities=identities, page_sizes=sizes)
            if self._snapshot()[0] != draft["binding"]:
                _fail("source_changed")
            marker = {"version": VERSION, "revision_id": revision_id, "draft_id": draft_id,
                "submission_version": _SUBMISSION_VERSION,
                "generation": expected_generation, "draft_sha256": _sha(draft_raw), "owner": self._owner,
                "binding": draft["binding"], "artifacts": draft["artifacts"], "context_identity": context.identity,
                "candidate": self._object(candidate_raw, atomic=True), "manifest": self._object(manifest_raw, atomic=True),
                "decision": self._object(decision_raw, atomic=True), "envelope": self._object(envelope_raw, atomic=True)}
            raw_marker = canonical_json(marker)
            intent = {"version": _SUBMISSION_VERSION, "draft_id": draft_id, "generation": expected_generation,
                "draft_sha256": _sha(draft_raw), "owner": self._owner, "reviewer": reviewer, "accept_source": True,
                "revision_id": revision_id, "revision_sha256": _sha(raw_marker), "revision": marker}
            fresh = self._fresh_submission_draft(draft, draft_raw)
            self._validate_submission(intent, fresh[0], fresh[1], fresh[3], fresh[4])
            self._fresh_submission_draft(draft, draft_raw)
            _publish(directory / "submit_intent.json", canonical_json(intent))
            submission = self._submission(draft, draft_raw, directory, identities, sizes)
            return self._finish_submission(draft, draft_raw, directory, identities, sizes, submission)

    def _retained_context(self, revision_id):
        marker_raw = _read(self._root / "revisions" / (_identifier(revision_id) + ".json"))
        marker = _decode(marker_raw)
        if (marker.get("version") != VERSION or marker.get("revision_id") != revision_id
                or marker.get("owner") != self._owner):
            _fail("revision_owner_changed")
        draft, draft_raw, directory, identities, sizes = self._draft(marker["draft_id"])
        submitted = _decode(_read(directory / "submitted.json"))
        if (draft["generation"] != marker["generation"] or _sha(draft_raw) != marker["draft_sha256"]
                or type(marker["generation"]) is not int or type(submitted.get("generation")) is not int
                or submitted != {"revision_id": revision_id, "generation": marker["generation"],
                                 "revision_sha256": _sha(marker_raw)} or marker["binding"] != draft["binding"]
                or marker["artifacts"] != draft["artifacts"]):
            _fail("submitted_generation_changed")
        if "submission_version" in marker and not os.path.lexists(directory / "submit_intent.json"):
            _fail("submission_intent_missing")
        if os.path.lexists(directory / "submit_intent.json"):
            submission = self._submission(draft, draft_raw, directory, identities, sizes, verify=False)
            if not submission["complete"] or submission["marker_raw"] != marker_raw:
                _fail("submission_revision_changed")
        artifacts = self._objects(marker["artifacts"])
        outputs = self._objects([marker[key] for key in ("candidate", "manifest", "decision", "envelope")])
        evidence = ReviewedSourceEvidence(outputs[marker["candidate"]], outputs[marker["manifest"]],
            tuple(sorted(artifacts.items())))
        return marker, marker_raw, evidence, outputs[marker["decision"]], outputs[marker["envelope"]], identities, sizes

    def load_context(self, revision_id) -> OrdinaryReviewedSourceContext:
        # A free OS run slot permits read-only recovery of an abandoned running
        # checkpoint. Mutation operations retain the stricter running-state gate.
        with self._scope(idle=False):
            marker, raw, evidence, decision, envelope, identities, sizes = self._retained_context(revision_id)
            def guard():
                # Workflow's owner thread holds the run slot while translation
                # workers call this read-only guard. Acquiring that thread-owned
                # slot here would reject the owner's own workers. Stable bounded
                # file reads and immutable marker hashes independently recheck it.
                self._check_checkpoint(context_identity=marker["context_identity"])
                current = self._retained_context(revision_id)
                if current[1] != raw or current[2:5] != (evidence, decision, envelope):
                    _fail("retained_revision_changed")
            context = OrdinaryReviewedSourceContext(revision_id, "operator_review", envelope, evidence, decision, guard)
            if context.identity != marker["context_identity"]:
                _fail("context_identity_changed")
            context.verify(source_hash=marker["binding"]["source_sha256"], page_identities=identities, page_sizes=sizes)
            return context
