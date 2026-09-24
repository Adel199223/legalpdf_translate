"""Owned browser-facing operations for explicit ordinary source review.

This is a service bridge, not a route or authentication boundary. A backend
resolves the existing runtime target and saved form config before registration.
All subsequent client operations carry only scope/opaque IDs and typed review
decisions. Returned source text is private UI content, never a diagnostic log.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
import json
import os
from pathlib import Path
import re
import threading
from uuid import uuid4

from .ordinary_source_review_service import OrdinarySourceReviewService, SourcePageDecision
from .translation_service import TranslationJobManager
from .types import RunConfig


class BrowserSourceReviewError(ValueError):
    """Fixed content-free error; no source text or caller paths are included."""


def _fail(code):
    raise BrowserSourceReviewError("browser_source_review_" + code) from None


def _owner(mode, workspace):
    # Match existing normalized _active_target IDs; never supply a fallback or
    # invent a session-local workspace to repair a missing request scope.
    if (mode not in {"live", "shadow"} or type(workspace) is not str or not workspace
            or re.fullmatch(r"[A-Za-z0-9._-]+", workspace) is None
            or workspace.strip("._-") != workspace):
        _fail("owner_required")
    return mode, workspace


def _id(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{32}", value) is None:
        _fail("invalid_id")
    return value


@dataclass(slots=True)
class _Review:
    owner: tuple[str, str]
    config: RunConfig
    settings_path: Path
    service: OrdinarySourceReviewService
    draft_id: str | None = None
    revisions: set[str] = field(default_factory=set)
    jobs: dict[str, str] = field(default_factory=dict)
    operations: dict[str, dict[str, str | None]] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class BrowserSourceReviewManager:
    """In-memory handles over persistent immutable source revisions.

    ``prepare`` and ``restore`` accept trusted backend-resolved config/settings,
    not JSON from a browser. After a server restart ``restore`` requires an exact
    revision ID and the original backend config; there is no auto-latest policy.
    BrowserAppServices can inject this manager separately from translation_jobs.
    """

    def __init__(self, translation_jobs: TranslationJobManager):
        self._jobs = translation_jobs
        self._lock = threading.RLock()
        self._reviews: dict[str, _Review] = {}

    def _register(self, owner, config, settings_path):
        if type(config) is not RunConfig or not isinstance(settings_path, Path):
            _fail("backend_config_required")
        candidate = settings_path.expanduser()
        path = candidate.resolve()
        # A fresh profile uses ordinary in-memory defaults until settings are saved.
        # Existing non-files and dangling links are not an absent settings file.
        if os.path.lexists(candidate) and not path.is_file():
            _fail("settings_unavailable")
        saved = deepcopy(config)
        return _Review(owner, saved, path, OrdinarySourceReviewService(saved))

    def _publish_handle(self, record):
        with self._lock:
            if len(self._reviews) >= 256:
                _fail("registry_full")
            review_id = uuid4().hex
            self._reviews[review_id] = record
            return review_id

    def _entry(self, mode, workspace, review_id):
        owner = _owner(mode, workspace)
        with self._lock:
            entry = self._reviews.get(_id(review_id))
        if entry is None or entry.owner != owner:
            _fail("unavailable")
        return entry

    @staticmethod
    def _view(review_id, result):
        # Images are fetched separately by owned review ID/page number. Never
        # put bytes, local source paths or retained context into JSON payloads.
        view = {key: deepcopy(value) for key, value in result.items() if key not in {"draft_id", "pages"}}
        view["review_id"] = review_id
        if "pages" in result:
            view["pages"] = []
            for page in result["pages"]:
                row = {key: deepcopy(value) for key, value in page.items() if key != "image_bytes"}
                row["image_available"] = type(page.get("image_bytes")) is bytes
                view["pages"].append(row)
        return json.loads(json.dumps(view, ensure_ascii=False, allow_nan=False))

    def prepare(self, *, runtime_mode, workspace_id, config, settings_path) -> dict:
        try:
            entry = self._register(_owner(runtime_mode, workspace_id), config, settings_path)
            result = entry.service.prepare()
            if result["status"] == "declined":
                return deepcopy(result)
            entry.draft_id = result["draft_id"]
            return self._view(self._publish_handle(entry), result)
        except BrowserSourceReviewError:
            raise
        except Exception:
            _fail("prepare_failed")

    def restore(self, *, runtime_mode, workspace_id, config, settings_path, revision_id) -> dict:
        """Explicit restart recovery using server-owned original config."""
        try:
            entry = self._register(_owner(runtime_mode, workspace_id), config, settings_path)
            revision_id = _id(revision_id)
            context = entry.service.load_context(revision_id)
            if context.revision_id != revision_id or context.reviewer_kind != "operator_review":
                _fail("revision_changed")
            entry.revisions.add(revision_id)
            # Restore is an explicit recovery operation; preserve saved content
            # preferences while selecting the operational resume flag.
            entry.config = replace(entry.config, resume=True)
            return {"status": "restored", "review_id": self._publish_handle(entry),
                "revision_id": revision_id, "reviewer_kind": "operator_review"}
        except BrowserSourceReviewError:
            raise
        except Exception:
            _fail("restore_failed")

    def read(self, *, runtime_mode, workspace_id, review_id) -> dict:
        try:
            entry = self._entry(runtime_mode, workspace_id, review_id)
            with entry.lock:
                operations = [{"operation_nonce": nonce, **record}
                              for nonce, record in sorted(entry.operations.items())]
                jobs = [{"job_id": job_id, "revision_id": revision_id}
                        for job_id, revision_id in sorted(entry.jobs.items())]
                if entry.draft_id is None or operations:
                    # Association-only recovery stays available while Workflow
                    # owns the run slot. It does not revalidate source content.
                    return {"status": "restored" if entry.draft_id is None else "submitted",
                        "review_id": review_id, "submitted": True,
                        "revision_ids": sorted(entry.revisions), "reviewer_kind": "operator_review",
                        "translation_operations": operations, "translation_jobs": jobs}
                result = entry.service.read(entry.draft_id)
                if result.get("submitted") is True:
                    # Recover a lost submit response using this handle's exact
                    # associations, never a newest-revision lookup or selection.
                    result["revision_ids"] = sorted(entry.revisions)
                return self._view(review_id, result)
        except BrowserSourceReviewError:
            raise
        except Exception:
            _fail("read_failed")

    def image(self, *, runtime_mode, workspace_id, review_id, page_number) -> bytes:
        try:
            entry = self._entry(runtime_mode, workspace_id, review_id)
            with entry.lock:
                if entry.draft_id is None or type(page_number) is not int or page_number < 1:
                    _fail("image_unavailable")
                pages = entry.service.read(entry.draft_id)["pages"]
                for page in pages:
                    if page["page_number"] == page_number:
                        return page["image_bytes"]
                _fail("image_unavailable")
        except BrowserSourceReviewError:
            raise
        except Exception:
            _fail("image_unavailable")

    def save_page(self, *, runtime_mode, workspace_id, review_id, expected_generation,
                  page_number, decision: SourcePageDecision) -> dict:
        try:
            entry = self._entry(runtime_mode, workspace_id, review_id)
            with entry.lock:
                if entry.draft_id is None:
                    _fail("draft_unavailable")
                result = entry.service.save_page(entry.draft_id, expected_generation=expected_generation,
                    page_number=page_number, decision=decision)
                return self._view(review_id, result)
        except BrowserSourceReviewError:
            raise
        except Exception:
            _fail("save_failed")

    def submit(self, *, runtime_mode, workspace_id, review_id, expected_generation,
               reviewer, accept_source) -> dict:
        try:
            entry = self._entry(runtime_mode, workspace_id, review_id)
            with entry.lock:
                if entry.draft_id is None:
                    _fail("draft_unavailable")
                result = entry.service.submit(entry.draft_id, expected_generation=expected_generation,
                    reviewer=reviewer, accept_source=accept_source)
                entry.revisions.add(result["revision_id"])
                return self._view(review_id, result)
        except BrowserSourceReviewError:
            raise
        except Exception:
            _fail("submit_failed")

    def start_translate(self, *, runtime_mode, workspace_id, review_id, revision_id, operation_nonce) -> dict:
        try:
            entry = self._entry(runtime_mode, workspace_id, review_id)
            with entry.lock:
                revision_id = _id(revision_id)
                operation_nonce = _id(operation_nonce)
                operation = entry.operations.get(operation_nonce)
                if operation is not None:
                    if operation["revision_id"] != revision_id:
                        _fail("operation_revision_changed")
                    if operation["status"] != "started":
                        _fail("operation_outcome_unknown")
                    job = self._jobs.get_job(operation["job_id"])
                    if (job is None or job.get("runtime_mode") != runtime_mode
                            or job.get("workspace_id") != workspace_id):
                        _fail("job_unavailable")
                    return job
                if revision_id not in entry.revisions:
                    _fail("revision_unavailable")
                if len(entry.operations) >= 256:
                    _fail("operation_limit")
                context = entry.service.load_context(revision_id)
                # Retain the nonce before a call that may start a background job.
                # An exception cannot make the same logical operation dispatch again.
                operation = {"revision_id": revision_id, "status": "starting", "job_id": None}
                entry.operations[operation_nonce] = operation

                def load_reviewed_source():
                    # An image/read queued during this start can hold the run
                    # slot after the request releases entry.lock. Serialize the
                    # background reload with this review's own reads, while
                    # retaining prompt failure for unrelated run-slot owners.
                    with entry.lock:
                        return entry.service.load_context(revision_id)

                try:
                    job = self._jobs.start_reviewed_translate(runtime_mode=runtime_mode, workspace_id=workspace_id,
                        config=deepcopy(entry.config), settings_path=entry.settings_path, reviewed_source_context=context,
                        reviewed_source_loader=load_reviewed_source)
                    if (not isinstance(job, dict) or not isinstance(job.get("job_id"), str) or not job["job_id"]
                            or job.get("runtime_mode") != runtime_mode or job.get("workspace_id") != workspace_id):
                        _fail("job_unavailable")
                    entry.jobs[job["job_id"]] = revision_id
                    operation.update(status="started", job_id=job["job_id"])
                    return job
                finally:
                    if operation["status"] == "starting":
                        operation["status"] = "unknown"
        except BrowserSourceReviewError:
            raise
        except Exception:
            _fail("translation_start_failed")

    def resume(self, *, runtime_mode, workspace_id, review_id, job_id, revision_id) -> dict:
        try:
            entry = self._entry(runtime_mode, workspace_id, review_id)
            with entry.lock:
                if entry.jobs.get(job_id) != _id(revision_id):
                    _fail("job_unavailable")
                job = self._jobs.get_job(job_id)
                if (job is None or job.get("runtime_mode") != runtime_mode
                        or job.get("workspace_id") != workspace_id):
                    _fail("job_unavailable")
                # Validate now and again through the retained loader in the new
                # background job. No revision selection is inferred from disk.
                entry.service.load_context(revision_id)
                resumed = self._jobs.resume_job(job_id=job_id, settings_path=entry.settings_path)
                entry.jobs[resumed["job_id"]] = revision_id
                return resumed
        except BrowserSourceReviewError:
            raise
        except Exception:
            _fail("resume_failed")
