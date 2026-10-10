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
from .ordinary_text_correction_service import TextCorrectionMixin

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


def _put_immutable(path, raw):
    """Finish an interrupted local publication only if every retained byte agrees."""
    if path.exists():
        if storage._read(path, max(len(raw), 1)) != raw:
            fail("automatic_candidate_changed", 409)
    else:
        storage._atomic(path, raw)


def _records(folder):
    if not folder.exists():
        return []
    storage._direct(folder, directory=True)
    files = list(folder.iterdir())
    if len(files) > MAX_RECORDS * 2:
        fail("record_limit", 413)
    return [p for p in sorted(files) if re.fullmatch(r"[a-f0-9]{32}\.json", p.name)]


def _edited_records(folder):
    if not folder.exists():
        return []
    storage._direct(folder, directory=True)
    rows = sorted(folder.glob("[0-9][0-9][0-9][0-9][0-9][0-9].json"))
    if len(rows) > MAX_RECORDS or any(p.name != f"{index:06d}.json" for index, p in enumerate(rows, 1)):
        fail("record_changed", 409)
    return rows


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


def _candidate_word_count(candidate, path):
    """A verified V7 map owns source footer words; legacy count is unchanged."""
    if candidate.source_map.get("writer_version") == "saved_docx_layout_writer_source_layout_v7":
        from .ordinary_source_layout import owned_story_count_descriptor
        from .joblog_flow import count_words_from_owned_story_map
        descriptor = owned_story_count_descriptor(candidate.source_map)
        raw=storage._read(path, storage.DOCX_MAX_BYTES)
        from .ordinary_edited_revision import qualify_edited_docx
        projection=qualify_edited_docx(candidate.docx_bytes,raw,source_layout_map=candidate.source_map)
        if projection:
            for row in descriptor['paragraphs']:
                row['part_uri']=projection['part_map'].get(row['part_uri'],row['part_uri'])
        descriptor["docx_sha256"] = digest(raw)
        return count_words_from_owned_story_map(path, descriptor)
    return count_words_from_docx(path)


class OrdinaryLayoutService(TextCorrectionMixin):
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
        automatic = _read(folder / "automatic.json") if (folder / "automatic.json").exists() else None
        edited = self._latest_edited(folder)
        if automatic is not None and not selection:
            active = edited or automatic
            selection = {"version": VERSION, "selection_id": active.get("revision_id", automatic["candidate_id"]),
                "generation": 0, "baseline_id": automatic["baseline_id"],
                "kind": "automatic_unreviewed_edited" if edited else "automatic_unreviewed",
                "sha256": active["sha256"],
                "word_count": active["word_count"], "review_generation": automatic["review_generation"],
                "artifact_id": automatic["candidate_id"], "stale": False,
                "document_reviewed": False, "rendered_layout_acceptance": "not_evaluated",
                "word_edit_qualified": bool(edited)}
        frozen = _read(folder / "frozen.json") if (folder / "frozen.json").exists() else None
        if selection:
            selection["stale"] = selection["baseline_id"] != baseline.name or (not frozen and
                selection["kind"] == "reviewed" and selection["review_generation"] != view["generation"])
        return self._correction_view(folder, {"job_id": manifest["identity"]["job_id"], "baseline_id": baseline.name,
                "generation": view["generation"], "status": "prepared", "review": view,
                "delivery_generation": len(rows), "delivery": selection, "frozen": frozen,
                "selected_pages": manifest["identity"]["selected_pages"],
                "output_reviews": [_read(p) for p in _records(baseline / "acceptances")],
                "suggestions": [_read(p) for p in _records(baseline / "suggestion_results")],
                "preparation_nonce": manifest["prepare_nonce"],
                "automatic_candidate": automatic, "edited_revision": edited})

    def _latest_edited(self, folder):
        records = _edited_records(folder / "edited_revisions")
        return _read(records[-1]) if records else None

    def _verified_edited(self, folder, manifest, automatic, record):
        candidate = self._verified_automatic(folder, manifest, automatic)
        if (set(record) != {"version", "revision_id", "candidate_id", "candidate_sha256",
                "source_map_sha256", "review_generation", "sha256", "word_count",
                "document_reviewed", "rendered_layout_acceptance", "word_edit_qualified"}
                or record["version"] != VERSION
                or record["document_reviewed"] is not False
                or record["rendered_layout_acceptance"] != "not_evaluated"
                or record["word_edit_qualified"] is not True
                or record["candidate_id"] != automatic["candidate_id"]
                or record["candidate_sha256"] != automatic["sha256"]
                or record["source_map_sha256"] != automatic["source_map_sha256"]
                or record["review_generation"] != automatic["review_generation"]):
            fail("edited_revision_stale", 409)
        revision_id = nonce(record["revision_id"])
        raw = storage._read(folder / "edited_revisions" / revision_id / "output.docx", storage.DOCX_MAX_BYTES)
        if (digest(raw) != record["sha256"]
                or revision_id != digest(automatic["candidate_id"].encode("ascii") + raw)[:32]):
            fail("edited_revision_stale", 409)
        from .ordinary_edited_revision import qualify_edited_docx
        qualify_edited_docx(candidate.docx_bytes, raw, source_layout_map=candidate.source_map)
        if _candidate_word_count(candidate, folder / "edited_revisions" / revision_id / "output.docx") != record["word_count"]:
            fail("edited_revision_stale", 409)
        return record

    def _alias_view(self, job_id, record):
        origin = record["origin_job_id"]
        if origin == job_id:
            fail("automatic_alias_changed", 409)
        with self.scope(origin) as source:
            baseline, manifest = self._baseline(source)
            current = self._view(source)
            automatic = _read(source / "automatic.json")
            candidate = self._verified_automatic(source, manifest, automatic)
            if current["delivery"] is None or current["delivery"]["kind"] not in {
                    "automatic_unreviewed", "automatic_unreviewed_edited"}:
                fail("automatic_alias_rebase_required", 409)
            if current["delivery"]["kind"] == "automatic_unreviewed_edited":
                self._verified_edited(source, manifest, automatic, self._latest_edited(source))
            if (baseline.name != record["baseline_id"]
                    or automatic["candidate_id"] != record["candidate_id"]
                    or current["generation"] != record["review_generation"]
                    or current["delivery"]["sha256"] != record["delivery_sha256"]
                    or current["delivery"]["selection_id"] != record["selection_id"]
                    or current["delivery"]["kind"] != record["kind"]):
                fail("automatic_alias_rebase_required", 409)
            view = deepcopy(current)
        alias_folder = self.folder(job_id)
        if _edited_records(alias_folder / "alias_edits"):
            edited = self._verified_alias_edited(alias_folder, record, candidate)
            view["delivery"].update(kind="automatic_unreviewed_edited",
                selection_id=edited["revision_id"], sha256=edited["sha256"],
                word_count=edited["word_count"])
        frozen_path = alias_folder / "frozen.json"
        view["frozen"] = frozen_path.exists()
        if frozen_path.exists() and not self._selections(alias_folder):
            frozen = _read(frozen_path)
            if frozen.get("generation") != 0 or frozen.get("sha256") != view["delivery"]["sha256"]:
                fail("delivery_frozen", 409)
        view["job_id"] = job_id
        view["automatic_alias"] = True
        view["editor_rebase_required"] = True
        return self._correction_view(alias_folder, view)

    def _verified_alias_edited(self, folder, alias, candidate):
        rows = _edited_records(folder / "alias_edits")
        if not rows:
            fail("edited_revision_stale", 409)
        edited = _read(rows[-1])
        revision_id = edited.get("revision_id")
        nonce(revision_id)
        raw = storage._read(folder / "alias_edits" / revision_id / "output.docx", storage.DOCX_MAX_BYTES)
        from .ordinary_edited_revision import qualify_edited_docx
        qualify_edited_docx(candidate.docx_bytes, raw, source_layout_map=candidate.source_map)
        count = _candidate_word_count(candidate, folder / "alias_edits" / revision_id / "output.docx")
        expected = {"version": VERSION, "revision_id": digest(alias["candidate_id"].encode("ascii") + raw)[:32],
            "candidate_id": alias["candidate_id"], "candidate_sha256": candidate.docx_sha256,
            "origin_delivery_sha256": alias["delivery_sha256"], "sha256": digest(raw),
            "word_count": count, "document_reviewed": False,
            "rendered_layout_acceptance": "not_evaluated", "word_edit_qualified": True}
        if edited != expected:
            fail("edited_revision_stale", 409)
        return edited

    @public
    def adopt_automatic_alias(self, job, origin_job_id, candidate_id):
        """Bind a rebuilt browser job to the same verified paid run artifact."""
        current_identity = job_identity(job, self.mode, self.workspace_id)
        identifier(origin_job_id); nonce(candidate_id)
        if origin_job_id == job.job_id:
            return self.state(job.job_id)
        with self.scope(origin_job_id) as source:
            baseline, manifest = self._baseline(source)
            automatic = _read(source / "automatic.json")
            self._verified_automatic(source, manifest, automatic)
            old_identity = manifest["identity"]
            if (automatic["candidate_id"] != candidate_id
                    or any(current_identity[key] != old_identity[key] for key in (
                        "run_id", "mode", "workspace_id", "source_sha256", "original_sha256",
                        "target_lang", "selected_pages"))
                    or current_identity["binding"].get("raw_source_map_sha256") !=
                        old_identity["binding"].get("raw_source_map_sha256")):
                fail("automatic_alias_identity_changed", 409)
            current = self._view(source)
            if current["delivery"] is None or current["delivery"]["kind"] not in {
                    "automatic_unreviewed", "automatic_unreviewed_edited"}:
                fail("automatic_alias_rebase_required", 409)
            if current["delivery"]["kind"] == "automatic_unreviewed_edited":
                self._verified_edited(source, manifest, automatic, self._latest_edited(source))
            record = {"version": VERSION, "job_identity": current_identity,
                "origin_job_id": origin_job_id, "baseline_id": baseline.name,
                "candidate_id": candidate_id, "review_generation": current["generation"],
                "delivery_sha256": current["delivery"]["sha256"],
                "selection_id": current["delivery"]["selection_id"],
                "kind": current["delivery"]["kind"]}
        with self.scope(job.job_id, create=True) as folder:
            if (folder / "prepared").exists():
                fail("automatic_alias_conflict", 409)
            path = folder / "alias.json"
            if path.exists():
                if _read(path) != record:
                    fail("automatic_alias_conflict", 409)
            else:
                _write(path, record)
        return self._alias_view(job.job_id, record)

    @public
    def automatic_review_copy(self, job_id):
        with self.scope(job_id) as folder:
            if self._selections(folder) and self._selections(folder)[-1]["kind"] == "text_corrected":
                return self.text_corrected_review_copy(job_id)
            if (folder / "alias.json").exists():
                record = _read(folder / "alias.json")
                self._alias_view(job_id, record)
                delivered = self.resolve_delivery(record["origin_job_id"], 0)
                copy = folder / "automatic" / "working.docx"
                if not copy.exists():
                    storage._mkdir(folder / "automatic")
                    _put_immutable(copy, storage._read(delivered.path, storage.DOCX_MAX_BYTES))
                return copy
            baseline, manifest = self._baseline(folder)
            record = _read(folder / "automatic.json")
            if record["baseline_id"] != baseline.name:
                fail("automatic_candidate_stale", 409)
            candidate = self._verified_automatic(folder, manifest, record)
            copy = folder / "automatic" / "working.docx"
            if not copy.exists():
                _put_immutable(copy, candidate.docx_bytes)
            return copy

    @public
    def adopt_automatic_word_edit(self, job_id, *, without_changes=False):
        """Commit a reviewed Word working copy as a separate unreviewed revision."""
        with self.scope(job_id) as folder:
            if self._selections(folder) and self._selections(folder)[-1]["kind"] == "text_corrected":
                return self.adopt_text_corrected_word_edit(job_id, without_changes=without_changes)
            if (folder / "alias.json").exists():
                record = _read(folder / "alias.json")
                view = self._alias_view(job_id, record)
                if view["frozen"]:
                    working = storage._read(folder / "automatic" / "working.docx", storage.DOCX_MAX_BYTES)
                    if digest(working) != view["delivery"]["sha256"]:
                        fail("delivery_frozen", 409)
                    return view
                delivered = self.resolve_delivery(record["origin_job_id"], 0)
                working_path = folder / "automatic" / "working.docx"
                working = storage._read(working_path, storage.DOCX_MAX_BYTES)
                if digest(working) == view["delivery"]["sha256"]:
                    return view
                if without_changes:
                    fail("edited_revision_changes_detected", 409)
                with self.scope(record["origin_job_id"]) as source:
                    _, manifest = self._baseline(source)
                    automatic = _read(source / "automatic.json")
                    candidate = self._verified_automatic(source, manifest, automatic)
                from .ordinary_edited_revision import qualify_edited_docx
                qualify_edited_docx(candidate.docx_bytes, working, source_layout_map=candidate.source_map)
                count = _candidate_word_count(candidate, working_path)
                if type(count) is not int or count <= 0:
                    fail("delivery_empty", 409)
                revision_id = digest(record["candidate_id"].encode("ascii") + working)[:32]
                edited = {"version": VERSION, "revision_id": revision_id,
                    "candidate_id": record["candidate_id"], "candidate_sha256": candidate.docx_sha256,
                    "origin_delivery_sha256": record["delivery_sha256"], "sha256": digest(working),
                    "word_count": count, "document_reviewed": False,
                    "rendered_layout_acceptance": "not_evaluated", "word_edit_qualified": True}
                records = _edited_records(folder / "alias_edits")
                if len(records) >= MAX_RECORDS:
                    fail("record_limit", 413)
                destination = storage._mkdir(folder / "alias_edits" / revision_id)
                _put_immutable(destination / "output.docx", working)
                _write(folder / "alias_edits" / f"{len(records)+1:06d}.json", edited)
                self._verified_alias_edited(folder, record, candidate)
                return self._alias_view(job_id, record)
            baseline, manifest = self._baseline(folder)
            automatic = _read(folder / "automatic.json")
            if automatic["baseline_id"] != baseline.name or self._selections(folder):
                fail("edited_revision_rebase_required", 409)
            candidate = self._verified_automatic(folder, manifest, automatic)
            working_path = folder / "automatic" / "working.docx"
            working = storage._read(working_path, storage.DOCX_MAX_BYTES)
            frozen = folder / "frozen.json"
            if frozen.exists():
                prior = self._latest_edited(folder)
                accepted_sha = prior["sha256"] if prior else automatic["sha256"]
                frozen_record = _read(frozen)
                if frozen_record.get("generation") != 0 or frozen_record.get("sha256") != accepted_sha:
                    fail("delivery_frozen", 409)
                if digest(working) != accepted_sha:
                    fail("delivery_frozen", 409)
                return self._view(folder)
            if working == candidate.docx_bytes:
                return self._view(folder)
            if without_changes:
                fail("edited_revision_changes_detected", 409)
            from .ordinary_edited_revision import qualify_edited_docx
            qualify_edited_docx(candidate.docx_bytes, working, source_layout_map=candidate.source_map)
            count = _candidate_word_count(candidate, working_path)
            if type(count) is not int or count <= 0:
                fail("delivery_empty", 409)
            records = _edited_records(folder / "edited_revisions")
            revision_id = digest(automatic["candidate_id"].encode("ascii") + working)[:32]
            record = {"version": VERSION, "revision_id": revision_id,
                "candidate_id": automatic["candidate_id"], "candidate_sha256": automatic["sha256"],
                "source_map_sha256": automatic["source_map_sha256"],
                "review_generation": automatic["review_generation"],
                "sha256": digest(working), "word_count": count,
                "document_reviewed": False, "rendered_layout_acceptance": "not_evaluated",
                "word_edit_qualified": True}
            if records and _read(records[-1]) == record:
                self._verified_edited(folder, manifest, automatic, record)
                return self._view(folder)
            if len(records) >= MAX_RECORDS:
                fail("record_limit", 413)
            destination = storage._mkdir(folder / "edited_revisions" / revision_id)
            _put_immutable(destination / "output.docx", working)
            record_path = folder / "edited_revisions" / f"{len(records)+1:06d}.json"
            _write(record_path, record)
            self._verified_edited(folder, manifest, automatic, record)
            return self._view(folder)

    def _verified_automatic(self, folder, manifest, record):
        candidate = self.saved.verified_unreviewed_candidate(manifest["review_id"], record["candidate_id"])
        identity = manifest["identity"]
        if (candidate.review_id != manifest["review_id"]
                or candidate.generation != record["review_generation"]
                or candidate.current_generation != record["review_generation"]
                or candidate.source_pdf_sha256 != identity["source_sha256"]
                or candidate.raw_docx_sha256 != identity["original_sha256"]
                or candidate.raw_source_map_sha256 != identity["binding"].get("raw_source_map_sha256")
                or list(candidate.selected_pages) != identity["selected_pages"]
                or candidate.target_lang != identity["target_lang"]
                or candidate.policy_fingerprint != record["policy_fingerprint"]
                or candidate.docx_sha256 != record["sha256"]
                or candidate.source_map_sha256 != record["source_map_sha256"]
                or candidate.receipt.get("document_reviewed") is not False
                or candidate.receipt.get("rendered_layout_acceptance") != "not_evaluated"):
            fail("automatic_candidate_stale", 409)
        raw = storage._read(folder / "automatic" / "output.docx", storage.DOCX_MAX_BYTES)
        if digest(raw) != record["sha256"] or raw != candidate.docx_bytes:
            fail("automatic_candidate_changed", 409)
        mapped = storage._read(folder / "automatic" / "source_map.json", 8 * 1024 * 1024)
        receipt = storage._read(folder / "automatic" / "receipt.json", 8 * 1024 * 1024)
        if (digest(mapped) != record["source_map_sha256"] or mapped != encode(candidate.source_map)
                or digest(receipt) != record["receipt_sha256"] or receipt != encode(candidate.receipt)):
            fail("automatic_candidate_changed", 409)
        return candidate

    @public
    def publish_automatic_candidate(self, job_id, *, expected_baseline_id, operation_nonce,
                                    candidate_id, expected_generation, policy_fingerprint):
        nonce(expected_baseline_id); nonce(operation_nonce); nonce(candidate_id)
        generation(expected_generation)
        if type(policy_fingerprint) is not str or re.fullmatch(r"[a-f0-9]{64}", policy_fingerprint) is None:
            fail("invalid_policy_fingerprint")
        with self.scope(job_id) as folder:
            if self._selections(folder) and self._selections(folder)[-1]["kind"] == "text_corrected":
                fail("correction_layout_rebase_required", 409)
            baseline, manifest = self._baseline(folder)
            if baseline.name != expected_baseline_id or (folder / "frozen.json").exists():
                fail("baseline_stale", 409)
            operation = baseline / "suggestions" / operation_nonce
            if not operation.exists():
                fail("suggestion_not_found", 404)
            result = _read(operation / "result.json")
            if result.get("status") != "applied_unreviewed" or result.get("generation") != expected_generation:
                fail("automatic_proposal_unavailable", 409)
            self._require_settled(folder)
            record_path = folder / "automatic.json"
            if record_path.exists():
                record = _read(record_path)
                if (record["baseline_id"] != baseline.name or record["operation_nonce"] != operation_nonce
                        or record["candidate_id"] != candidate_id or record["review_generation"] != expected_generation
                        or record["policy_fingerprint"] != policy_fingerprint):
                    fail("automatic_candidate_conflict", 409)
                self._verified_automatic(folder, manifest, record)
                return self._view(folder)
            if self._selections(folder):
                fail("delivery_already_selected", 409)
            candidate = self.saved.verified_unreviewed_candidate(manifest["review_id"], candidate_id)
            record = {"version": VERSION, "baseline_id": baseline.name,
                "operation_nonce": operation_nonce, "candidate_id": candidate_id,
                "review_generation": expected_generation, "policy_fingerprint": policy_fingerprint,
                "sha256": candidate.docx_sha256, "source_map_sha256": candidate.source_map_sha256,
                "receipt_sha256": digest(encode(candidate.receipt)),
                "word_count": 0, "document_reviewed": False,
                "rendered_layout_acceptance": "not_evaluated"}
            destination = storage._mkdir(folder / "automatic")
            _put_immutable(destination / "output.docx", candidate.docx_bytes)
            _put_immutable(destination / "working.docx", candidate.docx_bytes)
            _put_immutable(destination / "source_map.json", encode(candidate.source_map))
            _put_immutable(destination / "receipt.json", encode(candidate.receipt))
            count = _candidate_word_count(candidate, destination / "output.docx")
            if type(count) is not int or count <= 0:
                fail("delivery_empty")
            record["word_count"] = count
            self._verified_automatic(folder, manifest, record)
            _write(record_path, record)
            return self._view(folder)

    @public
    def state(self, job_id):
        identifier(job_id)
        if not self.root.exists() or not (self.root / job_id).exists():
            return {"job_id": job_id, "status": "unprepared", "generation": 0,
                    "delivery_generation": 0, "delivery": None, "review": None, "frozen": None}
        with self.scope(job_id) as folder:
            if (folder / "alias.json").exists():
                return self._alias_view(job_id, _read(folder / "alias.json"))
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
            if (folder / "alias.json").exists():
                record = _read(folder / "alias.json")
                if identity != record["job_identity"]:
                    fail("automatic_alias_identity_changed", 409)
                return self._alias_view(job.job_id, record)
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
            if self._selections(folder) and self._selections(folder)[-1]["kind"] == "text_corrected":
                fail("correction_layout_rebase_required", 409)
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
        generation(expected_delivery_generation, zero=True)
        if freeze_nonce is not None:
            nonce(freeze_nonce)
        with self.scope(job_id) as folder:
            corrected = self._resolve_text_delivery(folder, job_id, expected_delivery_generation, freeze_nonce, require_settled)
            if corrected is not None:
                return corrected
            if (folder / "alias.json").exists():
                record = _read(folder / "alias.json")
                view = self._alias_view(job_id, record)
                if expected_delivery_generation != 0 or view["delivery"]["stale"]:
                    fail("delivery_stale", 409)
                original = self.resolve_delivery(record["origin_job_id"], 0,
                    require_settled=require_settled)
                if (original.sha256 != record["delivery_sha256"]
                        or original.selection_id != record["selection_id"]
                        or original.kind != record["kind"]):
                    fail("automatic_alias_rebase_required", 409)
                if _edited_records(folder / "alias_edits"):
                    edited = _read(_edited_records(folder / "alias_edits")[-1])
                    selected_path = folder / "alias_edits" / edited["revision_id"] / "output.docx"
                    selected_sha = edited["sha256"]
                    selected_count = edited["word_count"]
                    selected_id = edited["revision_id"]
                    selected_kind = "automatic_unreviewed_edited"
                else:
                    selected_path = original.path
                    selected_sha = original.sha256
                    selected_count = original.word_count
                    selected_id = original.selection_id
                    selected_kind = original.kind
                frozen = folder / "frozen.json"
                if freeze_nonce:
                    frozen_record = {"freeze_nonce": freeze_nonce, "generation": 0,
                        "sha256": selected_sha}
                    if frozen.exists() and _read(frozen) != frozen_record:
                        fail("delivery_frozen", 409)
                    if not frozen.exists():
                        _write(frozen, frozen_record)
                return DeliveryArtifact(job_id, original.run_id, selected_path, selected_sha,
                    selected_count, original.target_lang, original.source_sha256, 0,
                    selected_id, selected_kind, frozen.exists())
            baseline, manifest = self._baseline(folder)
            if freeze_nonce or require_settled:
                self._require_settled(folder)
            view = self._view(folder)
            row = view["delivery"]
            if row is None or row["generation"] != expected_delivery_generation or row["stale"]:
                fail("delivery_stale", 409)
            if row["kind"] == "automatic_unreviewed":
                automatic = _read(folder / "automatic.json")
                self._verified_automatic(folder, manifest, automatic)
                path = folder / "automatic" / "output.docx"
                frozen = folder / "frozen.json"
                if freeze_nonce:
                    record = {"freeze_nonce": freeze_nonce, "generation": 0, "sha256": automatic["sha256"]}
                    if frozen.exists() and _read(frozen) != record:
                        fail("delivery_frozen", 409)
                    if not frozen.exists():
                        _write(frozen, record)
                if frozen.exists():
                    frozen_record = _read(frozen)
                    if frozen_record.get("generation") != 0 or frozen_record.get("sha256") != automatic["sha256"]:
                        fail("delivery_frozen", 409)
                identity = manifest["identity"]
                return DeliveryArtifact(job_id, identity["run_id"], path, automatic["sha256"],
                    automatic["word_count"], identity["target_lang"], identity["source_sha256"],
                    0, automatic["candidate_id"], "automatic_unreviewed", (folder / "frozen.json").exists())
            if row["kind"] == "automatic_unreviewed_edited":
                automatic = _read(folder / "automatic.json")
                edited = self._latest_edited(folder)
                if edited is None:
                    fail("edited_revision_stale", 409)
                self._verified_edited(folder, manifest, automatic, edited)
                path = folder / "edited_revisions" / edited["revision_id"] / "output.docx"
                frozen = folder / "frozen.json"
                if freeze_nonce:
                    record = {"freeze_nonce": freeze_nonce, "generation": 0, "sha256": edited["sha256"]}
                    if frozen.exists() and _read(frozen) != record:
                        fail("delivery_frozen", 409)
                    if not frozen.exists():
                        _write(frozen, record)
                if frozen.exists():
                    frozen_record = _read(frozen)
                    if frozen_record.get("generation") != 0 or frozen_record.get("sha256") != edited["sha256"]:
                        fail("delivery_frozen", 409)
                identity = manifest["identity"]
                return DeliveryArtifact(job_id, identity["run_id"], path, edited["sha256"],
                    edited["word_count"], identity["target_lang"], identity["source_sha256"],
                    0, edited["revision_id"], "automatic_unreviewed_edited", frozen.exists())
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
            summaries = storage._mkdir(baseline / "suggestion_results")
            summary_path = summaries / (operation_nonce + ".json")
            if summary_path.exists():
                if _read(summary_path) != result:
                    fail("receipt_changed", 409)
            _write(operation / "result.json", result)
            if not summary_path.exists():
                _write(summary_path, result)
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
