"""Job-owned browser handles for explicit saved-text formatting derivatives.

Only trusted job config/context enters the ordinary service. Durable records are
bound to that exact job and source revision. A rebuild nonce is consumed before
assembly; missing completion evidence never authorizes an automatic retry.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from uuid import uuid4

from .ordinary_formatting_review_service import OrdinaryFormattingReviewService
from .run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
from .translation_service import read_reviewed_formatting_file

VERSION = "browser_formatting_review_v1"
KINDS = ("output_docx", "source_map", "assembly_receipt")
_LIMIT = 256
_MAX_JSON = 8 * 1024 * 1024


class BrowserFormattingReviewError(ValueError):
    """Content-free error categories for the browser boundary."""


def _fail(code):
    raise BrowserFormattingReviewError("browser_formatting_review_" + code) from None


def _id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        _fail("invalid_id")
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                _fail("record_changed")
            result[key] = value
        return result
    def constant(_value):
        _fail("record_changed")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def _directory(path, *, create=False):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or str(path).startswith(("\\\\", "//")):
        _fail("storage_unavailable")
    if create:
        _directory(path.parent)
        path.mkdir(exist_ok=True)
    for item in (path, *path.parents):
        info = item.lstat()
        if (not stat.S_ISDIR(info.st_mode) or item.is_symlink()
                or getattr(info, "st_file_attributes", 0) & 0x400):
            _fail("storage_unavailable")
    return path.resolve(strict=True)


def _read(path):
    return read_reviewed_formatting_file(path, maximum=_MAX_JSON)


def _write(path, value):
    raw = _json(value)
    if not 0 < len(raw) <= _MAX_JSON:
        _fail("record_too_large")
    _directory(path.parent)
    with path.open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    if _read(path) != raw:
        _fail("publication_changed")
    return raw


def _folders(root):
    """Bound the inventory before accumulating it; never select a latest entry."""
    _directory(root)
    result = []
    with os.scandir(root) as entries:
        for entry in entries:
            if len(result) >= _LIMIT:
                _fail("registry_full")
            result.append(_directory(root / _id(entry.name)))
    return result


class BrowserFormattingReviewManager:
    """Persistent draft/nonce records, requiring an extant trusted job on every call.

    Full application restart does not invent jobs from forms or disk. A new
    manager can recover an exact review only when its original job is available.
    Every operation holds the existing run OS lock, including same-thread nested
    service calls. Other threads/processes fail promptly without publication.
    """

    def __init__(self, translation_jobs):
        self._jobs = translation_jobs

    def _trusted(self, runtime_mode, workspace_id, job_id, settings_path):
        if (runtime_mode not in {"live", "shadow"} or type(workspace_id) is not str
                or not 0 < len(workspace_id) <= 128
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*[A-Za-z0-9]|[A-Za-z0-9]", workspace_id) is None):
            _fail("owner_required")
        return self._jobs.trusted_formatting_job(job_id=job_id, runtime_mode=runtime_mode,
            workspace_id=workspace_id, settings_path=settings_path)

    @contextmanager
    def _scope(self, runtime_mode, workspace_id, job_id, settings_path, review_id=None):
        try:
            trusted = self._trusted(runtime_mode, workspace_id, job_id, settings_path)
            with run_workspace_slot(trusted.run_dir):
                # Recheck after lock acquisition and after every operation.
                current = self._trusted(runtime_mode, workspace_id, job_id, settings_path)
                if trusted.owner_json != current.owner_json:
                    _fail("owner_changed")
                root = trusted.run_dir / "browser_formatting_reviews"
                if review_id is None:
                    yield trusted, root, None, None
                else:
                    folder = _directory(root / _id(review_id))
                    owner = _decode(_read(folder / "owner.json"))
                    if (type(owner) is not dict or set(owner) != {"version", "review_id", "job_owner", "page_matched_derivative"}
                            or type(owner["page_matched_derivative"]) is not bool
                            or owner["version"] != VERSION or owner["review_id"] != review_id
                            or _json(owner["job_owner"]) != trusted.owner_json.encode("utf-8")):
                        _fail("owner_changed")
                    service = OrdinaryFormattingReviewService(trusted.config, trusted.source_context,
                        page_matched_derivative=owner["page_matched_derivative"])
                    yield trusted, folder, owner, service
                if self._trusted(runtime_mode, workspace_id, job_id, settings_path).owner_json != trusted.owner_json:
                    _fail("owner_changed")
        except BrowserFormattingReviewError:
            raise
        except RunWorkspaceBusy:
            _fail("run_busy")
        except Exception:
            _fail("operation_failed")

    @staticmethod
    def _view(owner, result):
        view = {k: deepcopy(v) for k, v in result.items() if k != "draft_id"}
        view.update(review_id=owner["review_id"], job_id=owner["job_owner"]["job_id"],
                    page_matched_derivative=owner["page_matched_derivative"])
        for page in view.get("pages", []):
            page["image_available"] = True
        return _decode(_json(view))

    def prepare(self, *, runtime_mode, workspace_id, job_id, settings_path, page_matched_derivative):
        if type(page_matched_derivative) is not bool:
            _fail("invalid_derivative_choice")
        with self._scope(runtime_mode, workspace_id, job_id, settings_path) as (trusted, root, _, __):
            service = OrdinaryFormattingReviewService(trusted.config, trusted.source_context,
                page_matched_derivative=page_matched_derivative)
            if root.exists():
                if len(_folders(root)) >= _LIMIT:
                    _fail("registry_full")
            result = service.prepare()
            if result["status"] == "declined":
                return {**deepcopy(result), "job_id": job_id, "page_matched_derivative": page_matched_derivative}
            review_id = _id(result["draft_id"])
            _directory(root, create=True)
            folder = root / review_id
            folder.mkdir(exist_ok=False)
            owner = {"version": VERSION, "review_id": review_id,
                "job_owner": json.loads(trusted.owner_json), "page_matched_derivative": page_matched_derivative}
            _write(folder / "owner.json", owner)
            return self._view(owner, result)

    @staticmethod
    def _selected(service, review_id, revision_id):
        revision_id = _id(revision_id)
        view = service.read(review_id)
        if view.get("status") != "submitted" or view.get("revision_id") != revision_id:
            _fail("revision_unavailable")
        selected = service.inspect(revision_id)
        if selected.get("status") != "ready" or selected.get("revision_id") != revision_id:
            _fail("revision_unavailable")
        return view, selected

    @staticmethod
    def _intent(folder, owner):
        raw = _read(folder / "intent.json")
        intent = _decode(raw)
        if (type(intent) is not dict or set(intent) != {"version", "owner", "operation_nonce", "revision_id", "generation", "artifact_id"}
                or intent["version"] != VERSION or _json(intent["owner"]) != _json(owner)
                or intent["operation_nonce"] != folder.name or type(intent["generation"]) is not int
                or intent["generation"] < 1):
            _fail("operation_changed")
        _id(intent["revision_id"])
        _id(intent["artifact_id"])
        return intent, _sha(raw)

    @staticmethod
    def _files(trusted, revision_id, paths):
        if type(paths) is not dict or set(paths) != set(KINDS):
            _fail("artifact_changed")
        docx = Path(paths["output_docx"])
        if docx.suffix != ".docx" or docx.parent != trusted.config.output_dir.resolve(strict=True):
            _fail("artifact_changed")
        expected = {"output_docx": docx, "source_map": docx.with_suffix(".source_map.json"),
            "assembly_receipt": docx.with_suffix(".formatting_assembly.json")}
        if any(Path(paths[k]) != expected[k] for k in KINDS):
            _fail("artifact_changed")
        maximum = {"output_docx": 32, "source_map": 128, "assembly_receipt": 8}
        raw = {k: read_reviewed_formatting_file(expected[k], maximum=maximum[k] * 1024 * 1024) for k in KINDS}
        receipt = _decode(raw["assembly_receipt"])
        revision_raw = _read(trusted.run_dir / "formatting_reviews" / _id(revision_id) / "revision.json")
        revision = _decode(revision_raw)
        if (receipt.get("version") != "run_reviewed_docx_assembly_v1"
                or receipt.get("review_profile") != "ordinary_operator_browser_v1"
                or receipt.get("source_review_kind") != "operator_review" or receipt.get("region_review_kind") != "operator_review"
                or receipt.get("revision_id") != revision_id or receipt.get("revision_sha256") != _sha(revision_raw)
                or receipt.get("binding_sha256") != _sha(_json(revision["binding"]))
                or _json(receipt.get("selected_pages")) != _json([p["page_number"] for p in revision["binding"]["pages"]])
                or receipt.get("docx_sha256") != _sha(raw["output_docx"])
                or receipt.get("source_map_sha256") != _sha(raw["source_map"])
                or type(receipt.get("provider_dispatch_count")) is not int or receipt["provider_dispatch_count"] != 0
                or receipt.get("layout_review_required") is not True
                or receipt.get("rendered_layout_acceptance") != "not_evaluated"):
            _fail("artifact_changed")
        files = {k: {"path": str(expected[k]), "sha256": _sha(raw[k]), "size": len(raw[k])} for k in KINDS}
        return files, raw

    def _completed(self, trusted, folder, intent, intent_sha):
        result = _decode(_read(folder / "result.json"))
        if (type(result) is not dict or set(result) != {"version", "intent_sha256", "record"}
                or result["version"] != VERSION or result["intent_sha256"] != intent_sha):
            _fail("operation_changed")
        record = result["record"]
        if (type(record) is not dict or set(record) != {"artifact_id", "review_id", "revision_id", "files"}
                or record["artifact_id"] != intent["artifact_id"] or record["revision_id"] != intent["revision_id"]
                or record["review_id"] != intent["owner"]["review_id"]):
            _fail("artifact_changed")
        files, raw = self._files(trusted, record["revision_id"], {k: record["files"][k]["path"] for k in KINDS})
        if _json(files) != _json(record["files"]):
            _fail("artifact_changed")
        public = self._jobs.register_reviewed_formatting_artifact(trusted=trusted, record=record)
        return public, raw

    def _operations(self, trusted, folder, owner, service):
        operations, artifacts = [], []
        root = folder / "operations"
        if not root.exists():
            return operations, artifacts
        for operation in sorted(_folders(root)):
            intent, digest = self._intent(operation, owner)
            view, _ = self._selected(service, owner["review_id"], intent["revision_id"])
            if view["generation"] != intent["generation"]:
                _fail("operation_changed")
            item = {"operation_nonce": intent["operation_nonce"], "revision_id": intent["revision_id"], "status": "pending"}
            if (operation / "result.json").exists():
                public, _ = self._completed(trusted, operation, intent, digest)
                item.update(status="built", artifact_id=public["artifact_id"])
                artifacts.append(public)
            operations.append(item)
        return operations, artifacts

    def read(self, *, runtime_mode, workspace_id, job_id, settings_path, review_id):
        with self._scope(runtime_mode, workspace_id, job_id, settings_path, review_id) as (trusted, folder, owner, service):
            result = self._view(owner, service.read(review_id))
            operations, artifacts = self._operations(trusted, folder, owner, service)
            return {**result, "rebuild_operations": operations, "artifacts": artifacts}

    def image(self, *, runtime_mode, workspace_id, job_id, settings_path, review_id, page_number):
        with self._scope(runtime_mode, workspace_id, job_id, settings_path, review_id) as (_, __, ___, service):
            return service.image(review_id, page_number=page_number)

    def save_page(self, *, runtime_mode, workspace_id, job_id, settings_path, review_id,
                  expected_generation, page_number, decision):
        with self._scope(runtime_mode, workspace_id, job_id, settings_path, review_id) as (_, __, owner, service):
            return self._view(owner, service.save_page(review_id, expected_generation=expected_generation,
                page_number=page_number, decision=decision))

    def save_document(self, *, runtime_mode, workspace_id, job_id, settings_path, review_id, expected_generation, decision):
        with self._scope(runtime_mode, workspace_id, job_id, settings_path, review_id) as (_, __, owner, service):
            return self._view(owner, service.save_document(review_id, expected_generation=expected_generation, decision=decision))

    def submit(self, *, runtime_mode, workspace_id, job_id, settings_path, review_id,
               expected_generation, reviewer, accept_formatting):
        with self._scope(runtime_mode, workspace_id, job_id, settings_path, review_id) as (_, __, owner, service):
            return self._view(owner, service.submit(review_id, expected_generation=expected_generation,
                reviewer=reviewer, accept_formatting=accept_formatting))

    def inspect(self, *, runtime_mode, workspace_id, job_id, settings_path, review_id, revision_id):
        with self._scope(runtime_mode, workspace_id, job_id, settings_path, review_id) as (_, __, owner, service):
            _, selected = self._selected(service, review_id, revision_id)
            return self._view(owner, selected)

    def rebuild(self, *, runtime_mode, workspace_id, job_id, settings_path, review_id, revision_id, operation_nonce):
        with self._scope(runtime_mode, workspace_id, job_id, settings_path, review_id) as (trusted, folder, owner, service):
            operation_nonce = _id(operation_nonce)
            view, selected = self._selected(service, review_id, revision_id)
            root = _directory(folder / "operations", create=True)
            operation = root / operation_nonce
            if operation.exists():
                intent, digest = self._intent(_directory(operation), owner)
                if intent["revision_id"] != revision_id or intent["generation"] != view["generation"]:
                    _fail("operation_changed")
                if not (operation / "result.json").exists():
                    return {**self._view(owner, selected), "status": "pending", "operation_nonce": operation_nonce,
                        "rebuild_operations": [{"operation_nonce": operation_nonce, "revision_id": revision_id, "status": "pending"}], "artifacts": []}
                public, _ = self._completed(trusted, operation, intent, digest)
                return self._built_view(owner, selected, operation_nonce, public)
            existing, _ = self._operations(trusted, folder, owner, service)
            if any(row["status"] == "pending" for row in existing):
                _fail("operation_outcome_unknown")
            if len(existing) >= _LIMIT:
                _fail("operation_limit")
            operation.mkdir(exist_ok=False)
            intent = {"version": VERSION, "owner": owner, "operation_nonce": operation_nonce,
                "revision_id": revision_id, "generation": view["generation"], "artifact_id": uuid4().hex}
            digest = _sha(_write(operation / "intent.json", intent))
            built = service.rebuild(revision_id)  # Exactly one attempt after durable intent.
            if built.get("status") != "built" or built.get("revision_id") != revision_id:
                _fail("build_incomplete")
            self._selected(service, review_id, revision_id)
            files, _ = self._files(trusted, revision_id, {k: built[k] for k in KINDS})
            record = {"artifact_id": intent["artifact_id"], "review_id": review_id, "revision_id": revision_id, "files": files}
            _write(operation / "result.json", {"version": VERSION, "intent_sha256": digest, "record": record})
            public, _ = self._completed(trusted, operation, intent, digest)
            return self._built_view(owner, selected, operation_nonce, public)

    def _built_view(self, owner, selected, nonce, artifact):
        return {**self._view(owner, selected), "status": "built", "operation_nonce": nonce, "artifact": artifact,
            "rebuild_operations": [{"operation_nonce": nonce, "revision_id": artifact["revision_id"],
                "status": "built", "artifact_id": artifact["artifact_id"]}], "artifacts": [artifact]}

    def artifact(self, *, runtime_mode, workspace_id, job_id, settings_path, review_id, artifact_id, artifact_kind):
        with self._scope(runtime_mode, workspace_id, job_id, settings_path, review_id) as (trusted, folder, owner, service):
            _id(artifact_id)
            if type(artifact_kind) is not str or artifact_kind not in KINDS:
                _fail("artifact_unavailable")
            matches = []
            for operation in _folders(folder / "operations"):
                intent, digest = self._intent(operation, owner)
                if intent["artifact_id"] == artifact_id:
                    matches.append((operation, intent, digest))
            if len(matches) != 1:
                _fail("artifact_unavailable")
            operation, intent, digest = matches[0]
            view, _ = self._selected(service, review_id, intent["revision_id"])
            if view["generation"] != intent["generation"]:
                _fail("operation_changed")
            _, raw = self._completed(trusted, operation, intent, digest)
            return raw[artifact_kind]
