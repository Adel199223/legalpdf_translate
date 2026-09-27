"""Owned immutable layout baselines, review acceptances and delivery selections.

No credentials, provider or native operations belong in this local service.
Filesystem primitives share the already bounded saved-layout storage policy.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from functools import wraps
from pathlib import Path
import re

from . import saved_docx_layout_service as storage
from .joblog_flow import count_words_from_docx
from .ordinary_layout_contracts import (VERSION, OrdinaryLayoutError, DeliveryArtifact, decode, digest,
    encode, fail, generation, identifier, job_identity, nonce, validated_groups)
from .run_workspace_lock import RunWorkspaceBusy, run_workspace_slot
from .saved_docx_layout import inspect_docx

MAX_RECORDS = 256


def public(function):
    @wraps(function)
    def call(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except OrdinaryLayoutError:
            raise
        except RunWorkspaceBusy:
            fail("workspace_busy", 409)
        except Exception as exc:
            code = getattr(exc, "code", "operation_failed")
            if type(code) is not str or re.fullmatch(r"[a-z][a-z0-9_]{0,120}", code) is None:
                code = "operation_failed"
            fail(code, getattr(exc, "status", 422))
    return call


def _write(path, value):
    payload = encode(value)
    storage._atomic(path, encode({"payload": value, "sha256": digest(payload)}))


def _read(path):
    value = decode(storage._read(path))
    if type(value) is not dict or set(value) != {"payload", "sha256"} or digest(encode(value["payload"])) != value["sha256"]:
        fail("record_changed", 409)
    return value["payload"]


def _records(folder):
    if not folder.exists():
        return []
    storage._direct(folder, directory=True)
    files = list(folder.iterdir())
    if len(files) > MAX_RECORDS * 2:
        fail("record_limit", 413)
    return [p for p in sorted(files) if re.fullmatch(r"[a-f0-9]{32}\.json", p.name)]


def _directories(folder):
    if not folder.exists():
        return []
    storage._direct(folder, directory=True)
    rows = []
    for path in folder.iterdir():
        if len(rows) >= MAX_RECORDS:
            fail("record_limit", 413)
        nonce(path.name)
        storage._direct(path, directory=True)
        rows.append(path)
    return sorted(rows)


class OrdinaryLayoutService:
    @public
    def __init__(self, root, *, mode, workspace_id, saved_service=None):
        if (mode not in {"live", "shadow"} or type(workspace_id) is not str
                or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9._-]{0,126}[A-Za-z0-9])?", workspace_id) is None):
            fail("invalid_owner")
        self.saved = saved_service or storage.SavedDocxLayoutService(root, mode=mode, workspace_id=workspace_id)
        expected_saved_root = storage._direct(root, directory=True, missing=True) / "saved_docx_layout" / workspace_id
        if self.saved._owner != {"mode": mode, "workspace_id": workspace_id, "root": str(expected_saved_root)}:
            fail("review_owner_mismatch", 409)
        self.mode, self.workspace_id = mode, workspace_id
        self.root = storage._direct(root, directory=True, missing=True) / "ordinary_layout" / workspace_id / mode
        self.owner = {"mode": mode, "workspace_id": workspace_id, "root": str(self.root)}

    def folder(self, job_id, *, create=False):
        identifier(job_id)
        if create:
            storage._mkdir(self.root)
        storage._direct(self.root, directory=True)
        folder = self.root / job_id
        if create:
            storage._mkdir(folder)
        storage._direct(folder, directory=True)
        owner = folder / "owner.json"
        expected = {"version": VERSION, "owner": self.owner, "job_id": job_id}
        if create and not owner.exists():
            with run_workspace_slot(folder):
                if not owner.exists():
                    _write(owner, expected)
        if _read(owner) != expected:
            fail("owner_changed", 409)
        return folder

    @contextmanager
    def scope(self, job_id, *, create=False):
        folder = self.folder(job_id, create=create)
        with run_workspace_slot(folder):
            yield folder

    def _baseline(self, folder):
        pointers = sorted((folder / "prepared").glob("*.json")) if (folder / "prepared").exists() else []
        if not pointers:
            fail("not_prepared", 409)
        if len(pointers) > MAX_RECORDS:
            fail("record_limit", 413)
        for number, path in enumerate(pointers, 1):
            if path.name != f"{number:06d}.json":
                fail("record_changed", 409)
        pointer = _read(pointers[-1])
        baseline = folder / "baselines" / nonce(pointer["baseline_id"])
        manifest = _read(baseline / "manifest.json")
        if digest(encode(manifest)) != pointer["manifest_sha256"]:
            fail("record_changed", 409)
        for name, info in manifest["files"].items():
            if name not in {"provider.docx", "reviewed.docx", "source.pdf"}:
                fail("record_changed", 409)
            raw = storage._read(baseline / name, 64 * 1024 * 1024)
            if digest(raw) != info["sha256"] or len(raw) != info["bytes"]:
                fail("baseline_changed", 409)
        return baseline, manifest

    def _selections(self, folder):
        paths = sorted((folder / "selections").glob("*.json")) if (folder / "selections").exists() else []
        if len(paths) > MAX_RECORDS:
            fail("record_limit", 413)
        rows = []
        for number, path in enumerate(paths, 1):
            row = _read(path)
            if path.name != f"{number:06d}.json" or row["generation"] != number:
                fail("record_changed", 409)
            raw = storage._read(folder / "deliveries" / nonce(row["selection_id"]) / "output.docx", storage.DOCX_MAX_BYTES)
            if digest(raw) != row["sha256"]:
                fail("delivery_changed", 409)
            rows.append(row)
        return rows

    def _view(self, folder):
        baseline, manifest = self._baseline(folder)
        view = self.saved.read(manifest["review_id"])
        rows = self._selections(folder)
        selection = deepcopy(rows[-1]) if rows else None
        frozen = _read(folder / "frozen.json") if (folder / "frozen.json").exists() else None
        if selection:
            selection["stale"] = selection["baseline_id"] != baseline.name or (not frozen and
                selection["kind"] == "reviewed" and selection["review_generation"] != view["generation"])
        return {"job_id": manifest["identity"]["job_id"], "baseline_id": baseline.name,
                "generation": view["generation"], "status": "prepared", "review": view,
                "delivery_generation": len(rows), "delivery": selection, "frozen": frozen,
                "selected_pages": manifest["identity"]["selected_pages"],
                "output_reviews": [_read(p) for p in _records(baseline / "acceptances")],
                "suggestions": [_read(p) for p in _records(baseline / "suggestion_results")],
                "preparation_nonce": manifest["prepare_nonce"]}

    @public
    def state(self, job_id):
        identifier(job_id)
        if not self.root.exists() or not (self.root / job_id).exists():
            return {"job_id": job_id, "status": "unprepared", "generation": 0,
                    "delivery_generation": 0, "delivery": None, "review": None, "frozen": None}
        with self.scope(job_id) as folder:
            return self._view(folder)

    @public
    def prepare(self, job, prepare_nonce):
        nonce(prepare_nonce)
        identity = job_identity(job, self.mode, self.workspace_id)
        with self.scope(job.job_id, create=True) as folder:
            baselines = storage._mkdir(folder / "baselines")
            baseline = baselines / prepare_nonce
            if baseline.exists():
                if not (baseline / "manifest.json").exists():
                    fail("preparation_incomplete", 409)
                manifest = _read(baseline / "manifest.json")
                if manifest["identity"] != identity:
                    fail("nonce_conflict", 409)
                prepared = storage._mkdir(folder / "prepared")
                pointers = sorted(prepared.glob("*.json"))
                if not any(_read(p)["baseline_id"] == prepare_nonce for p in pointers):
                    if (folder / "frozen.json").exists() or len(pointers) >= MAX_RECORDS or manifest.get("prepared_generation") != len(pointers) + 1:
                        fail("preparation_incomplete", 409)
                    _write(prepared / f"{len(pointers) + 1:06d}.json",
                        {"baseline_id": prepare_nonce, "manifest_sha256": digest(encode(manifest))})
                return self._view(folder)
            if (folder / "frozen.json").exists():
                fail("delivery_frozen", 409)
            if len(_directories(baselines)) >= MAX_RECORDS:
                fail("record_limit", 413)
            storage._mkdir(baseline)
            files = {}
            for name, raw in (("provider.docx", job.original_docx), ("reviewed.docx", job.reviewed_docx), ("source.pdf", job.source_pdf)):
                storage._atomic(baseline / name, raw)
                files[name] = {"sha256": digest(raw), "bytes": len(raw)}
            imported = self.saved.import_document(job.source_pdf, job.reviewed_docx, job.target_lang, prepare_nonce)
            if not set(job.selected_pages) <= {p["page_number"] for p in imported["pages"]}:
                fail("invalid_page_selection")
            snapshot = inspect_docx(job.reviewed_docx, job.target_lang)
            groups = validated_groups(job, snapshot)
            if groups:
                decisions = deepcopy(imported["decisions"])
                by_id = {row["paragraph_id"]: row for row in decisions["paragraphs"]}
                frames = {p["page_number"]: p for p in imported["pages"]}
                for number, ids in groups.items():
                    frame = frames[number]
                    for pid in ids:
                        by_id[pid]["regions"] = [{"page_number": number, "bbox_px": [0, 0, frame["width_px"], frame["height_px"]]}]
                seed_nonce = digest((prepare_nonce + "page_seed").encode())[:32]
                imported = self.saved.save_decisions(imported["review_id"], imported["generation"], seed_nonce, decisions)
            prepared = storage._mkdir(folder / "prepared")
            number = len(list(prepared.glob("*.json"))) + 1
            manifest = {"version": VERSION, "identity": identity, "prepare_nonce": prepare_nonce,
                        "prepared_generation": number, "review_id": imported["review_id"], "files": files}
            _write(baseline / "manifest.json", manifest)
            _write(prepared / f"{number:06d}.json", {"baseline_id": prepare_nonce, "manifest_sha256": digest(encode(manifest))})
            return self._view(folder)

    @public
    def assert_current(self, job, *, allow_frozen_review_change=False):
        identity = job_identity(job, self.mode, self.workspace_id)
        with self.scope(job.job_id) as folder:
            _, manifest = self._baseline(folder)
            expected = deepcopy(manifest["identity"])
            if allow_frozen_review_change and (folder / "frozen.json").exists():
                identity["reviewed_sha256"] = expected["reviewed_sha256"]
            if identity != expected:
                fail("baseline_stale", 409)
            return self._view(folder)

    def _artifact(self, manifest, artifact_id, expected_generation):
        artifact = self.saved.verified_artifact(manifest["review_id"], artifact_id)
        identity = manifest["identity"]
        if (artifact.generation != expected_generation or artifact.current_generation != expected_generation
                or artifact.source_pdf_sha256 != identity["source_sha256"]
                or artifact.saved_docx_sha256 != identity["reviewed_sha256"]
                or artifact.target_lang != identity["target_lang"] or artifact.receipt.get("exact_text_preserved") is not True):
            fail("artifact_stale", 409)
        return artifact

    @public
    def accept_output(self, job_id, artifact_id, expected_generation, acceptance_nonce, all_pages_reviewed, *, expected_baseline_id):
        nonce(artifact_id); nonce(acceptance_nonce); generation(expected_generation)
        if all_pages_reviewed is not True:
            fail("output_review_required", 409)
        with self.scope(job_id) as folder:
            baseline, manifest = self._baseline(folder)
            if nonce(expected_baseline_id) != baseline.name:
                fail("baseline_stale", 409)
            acceptances = storage._mkdir(baseline / "acceptances")
            path = acceptances / (acceptance_nonce + ".json")
            request = {"artifact_id": artifact_id, "generation": expected_generation, "all_pages_reviewed": True}
            if path.exists():
                if _read(path)["request"] != request:
                    fail("nonce_conflict", 409)
                return self._view(folder)
            if (folder / "frozen.json").exists():
                fail("delivery_frozen", 409)
            artifact = self._artifact(manifest, artifact_id, expected_generation)
            if len(_records(acceptances)) >= MAX_RECORDS:
                fail("record_limit", 413)
            _write(path, {"acceptance_nonce": acceptance_nonce, "request": request, "sha256": digest(artifact.docx_bytes),
                          "review_kind": "operator_output_review"})
            return self._view(folder)

    @public
    def select_delivery(self, job_id, expected_delivery_generation, selection_nonce, kind,
                        review_id=None, artifact_id=None, expected_review_generation=None, keep_ordinary_confirmed=False,
                        *, expected_baseline_id):
        generation(expected_delivery_generation, zero=True); nonce(selection_nonce)
        if kind not in {"original", "reviewed"} or type(keep_ordinary_confirmed) is not bool:
            fail("invalid_selection")
        request = {"expected_delivery_generation": expected_delivery_generation, "kind": kind,
            "review_id": review_id, "artifact_id": artifact_id, "expected_review_generation": expected_review_generation,
            "keep_ordinary_confirmed": keep_ordinary_confirmed}
        with self.scope(job_id) as folder:
            baseline, manifest = self._baseline(folder)
            if nonce(expected_baseline_id) != baseline.name:
                fail("baseline_stale", 409)
            rows = self._selections(folder)
            prior = next((r for r in rows if r["selection_id"] == selection_nonce), None)
            if prior:
                if prior["request"] != request:
                    fail("nonce_conflict", 409)
                return self._view(folder)
            if (folder / "frozen.json").exists():
                fail("delivery_frozen", 409)
            if len(rows) != expected_delivery_generation:
                fail("delivery_generation_conflict", 409)
            if len(rows) >= MAX_RECORDS:
                fail("record_limit", 413)
            if kind == "reviewed":
                nonce(review_id); nonce(artifact_id); generation(expected_review_generation)
                if review_id != manifest["review_id"]:
                    fail("review_owner_mismatch", 409)
                artifact = self._artifact(manifest, artifact_id, expected_review_generation)
                raw = artifact.docx_bytes
                accepts = [_read(p) for p in _records(baseline / "acceptances")]
                if not any(a["request"] == {"artifact_id": artifact_id, "generation": expected_review_generation,
                        "all_pages_reviewed": True} and a["sha256"] == digest(raw) for a in accepts):
                    fail("output_review_required", 409)
            else:
                if not keep_ordinary_confirmed or any(v is not None for v in (review_id, artifact_id, expected_review_generation)):
                    fail("ordinary_layout_confirmation_required", 409)
                raw = storage._read(baseline / "reviewed.docx", storage.DOCX_MAX_BYTES)
            deliveries = storage._mkdir(folder / "deliveries")
            destination = deliveries / selection_nonce
            storage._mkdir(destination)
            output = destination / "output.docx"
            if output.exists():
                if storage._read(output, storage.DOCX_MAX_BYTES) != raw:
                    fail("delivery_changed", 409)
            else:
                storage._atomic(output, raw)
            count = count_words_from_docx(output)
            if type(count) is not int or count <= 0:
                fail("delivery_empty")
            row = {"version": VERSION, "selection_id": selection_nonce, "generation": len(rows) + 1,
                "baseline_id": baseline.name, "kind": kind, "sha256": digest(raw), "word_count": count,
                "review_generation": expected_review_generation, "artifact_id": artifact_id, "request": request}
            selections = storage._mkdir(folder / "selections")
            _write(selections / f"{row['generation']:06d}.json", row)
            return self._view(folder)

    @public
    def resolve_delivery(self, job_id, expected_delivery_generation, freeze_nonce=None, *, require_settled=False):
        generation(expected_delivery_generation)
        if freeze_nonce is not None:
            nonce(freeze_nonce)
        with self.scope(job_id) as folder:
            baseline, manifest = self._baseline(folder)
            if freeze_nonce or require_settled:
                self._require_settled(folder)
            view = self._view(folder)
            row = view["delivery"]
            if row is None or row["generation"] != expected_delivery_generation or row["stale"]:
                fail("delivery_stale", 409)
            if row["kind"] == "reviewed" and not view["frozen"]:
                self._artifact(manifest, row["artifact_id"], row["review_generation"])
            frozen = folder / "frozen.json"
            if frozen.exists():
                record = _read(frozen)
                if (record["generation"] != row["generation"] or record["sha256"] != row["sha256"]
                        or (freeze_nonce and record["freeze_nonce"] != freeze_nonce)):
                    fail("delivery_frozen", 409)
            elif freeze_nonce:
                _write(frozen, {"freeze_nonce": freeze_nonce, "generation": row["generation"], "sha256": row["sha256"]})
            identity = manifest["identity"]
            path = folder / "deliveries" / row["selection_id"] / "output.docx"
            return DeliveryArtifact(job_id, identity["run_id"], path, row["sha256"], row["word_count"],
                identity["target_lang"], identity["source_sha256"], row["generation"], row["selection_id"], row["kind"], frozen.exists())

    def _require_settled(self, folder):
        for baseline in _directories(folder / "baselines"):
            for operation in _directories(baseline / "suggestions"):
                if (not (operation / "intent.json").exists() or not (operation / "result.json").exists()
                        or not (operation / "accounting_summary.json").exists()):
                    fail("accounting_unsettled", 409)
                _read(operation / "intent.json")
                _read(operation / "result.json")
                if _read(operation / "accounting_summary.json").get("cost_usd") is None:
                    fail("accounting_unsettled", 409)

    @public
    def review_artifact(self, job_id, artifact_id, expected_generation, *, expected_baseline_id):
        nonce(artifact_id); generation(expected_generation)
        with self.scope(job_id) as folder:
            baseline, manifest = self._baseline(folder)
            if baseline.name != nonce(expected_baseline_id):
                fail("baseline_stale", 409)
            return self._artifact(manifest, artifact_id, expected_generation)

    @public
    def begin_suggestion(self, job_id, expected_generation, operation_nonce, page_numbers, policy, *, expected_baseline_id):
        generation(expected_generation); nonce(operation_nonce)
        with self.scope(job_id) as folder:
            baseline, manifest = self._baseline(folder)
            if nonce(expected_baseline_id) != baseline.name:
                fail("baseline_stale", 409)
            if any((other / "suggestions" / operation_nonce).exists() for other in _directories(folder / "baselines") if other != baseline):
                fail("nonce_conflict", 409)
            operations = storage._mkdir(baseline / "suggestions")
            operation = operations / operation_nonce
            request = {"expected_generation": expected_generation, "page_numbers": page_numbers, "policy": policy}
            if operation.exists():
                intent = _read(operation / "intent.json")
                if intent["request"] != request:
                    fail("nonce_conflict", 409)
                return operation, intent, False
            if (folder / "frozen.json").exists():
                fail("delivery_frozen", 409)
            if self.saved.read(manifest["review_id"])["generation"] != expected_generation:
                fail("generation_conflict", 409)
            for prior_baseline in _directories(folder / "baselines"):
                if any(not (prior / "result.json").exists() for prior in _directories(prior_baseline / "suggestions")):
                    fail("suggestion_pending", 409)
            if len(_directories(operations)) >= MAX_RECORDS:
                fail("record_limit", 413)
            storage._mkdir(operation)
            intent = {"version": VERSION, "operation_nonce": operation_nonce, "baseline_id": baseline.name,
                "review_id": manifest["review_id"], "identity": manifest["identity"], "request": request}
            _write(operation / "intent.json", intent)
            return operation, intent, True

    @public
    def suggestion(self, job_id, operation_nonce, *, expected_baseline_id=None,
                   expected_generation=None, page_numbers=None):
        nonce(operation_nonce)
        with self.scope(job_id) as folder:
            operation = self._operation(folder, operation_nonce)
            intent = _read(operation / "intent.json")
            if expected_baseline_id is not None and (nonce(expected_baseline_id) != intent["baseline_id"]
                    or expected_generation != intent["request"]["expected_generation"]
                    or page_numbers != intent["request"]["page_numbers"]):
                fail("nonce_conflict", 409)
            if (operation / "result.json").exists():
                return _read(operation / "result.json")
            return {"operation_nonce": operation_nonce, "status": "pending_or_interrupted",
                    "baseline_id": intent["baseline_id"],
                    "generation": intent["request"]["expected_generation"], "retry_dispatch_allowed": False,
                    "cancel_requested": (operation / "cancel.json").exists()}

    def _operation(self, folder, operation_nonce):
        nonce(operation_nonce)
        matches = [b / "suggestions" / operation_nonce for b in _directories(folder / "baselines")
                   if (b / "suggestions" / operation_nonce).exists()]
        if not matches:
            fail("suggestion_not_found", 404)
        if len(matches) != 1:
            fail("nonce_conflict", 409)
        return matches[0]

    @public
    def cancel_suggestion(self, job_id, operation_nonce, expected_generation, *, expected_baseline_id):
        generation(expected_generation); nonce(expected_baseline_id)
        with self.scope(job_id) as folder:
            operation = self._operation(folder, operation_nonce)
            intent = _read(operation / "intent.json")
            if (intent["baseline_id"] != expected_baseline_id
                    or intent["request"]["expected_generation"] != expected_generation):
                fail("nonce_conflict", 409)
            if (operation / "result.json").exists():
                return _read(operation / "result.json")
            record = {"operation_nonce": operation_nonce, "baseline_id": expected_baseline_id,
                "generation": expected_generation, "status": "cancel_requested", "retry_dispatch_allowed": False}
            if (operation / "cancel.json").exists():
                if _read(operation / "cancel.json") != record:
                    fail("record_changed", 409)
            else:
                _write(operation / "cancel.json", record)
            return record

    @public
    def cancellation_requested(self, job_id, operation_nonce):
        with self.scope(job_id) as folder:
            operation = self._operation(folder, operation_nonce)
            path = operation / "cancel.json"
            if path.exists():
                _read(path)
                return True
            return False

    @public
    def finish_suggestion(self, job_id, operation_nonce, result, *, baseline_id):
        with self.scope(job_id) as folder:
            baseline = storage._direct(folder / "baselines" / nonce(baseline_id), directory=True)
            operation = baseline / "suggestions" / nonce(operation_nonce)
            _read(operation / "intent.json")
            if (operation / "result.json").exists():
                if _read(operation / "result.json") != result:
                    fail("receipt_changed", 409)
                return result
            _write(operation / "result.json", result)
            summaries = storage._mkdir(baseline / "suggestion_results")
            _write(summaries / (operation_nonce + ".json"), result)
            return result

    @public
    def apply_suggestion(self, job_id, operation_nonce, expected_generation, decisions, *, baseline_id):
        """Serialize proposal application against baseline changes and delivery freeze."""
        with self.scope(job_id) as folder:
            baseline, manifest = self._baseline(folder)
            if baseline.name != nonce(baseline_id):
                fail("baseline_stale", 409)
            if (folder / "frozen.json").exists():
                fail("delivery_frozen", 409)
            operation = baseline / "suggestions" / nonce(operation_nonce)
            intent = _read(operation / "intent.json")
            if intent["request"]["expected_generation"] != expected_generation:
                fail("generation_conflict", 409)
            return self.saved.save_decisions(manifest["review_id"], expected_generation,
                digest((operation_nonce + "proposal_apply").encode())[:32], decisions)
