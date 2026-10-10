"""Explicit immutable local correction drafts and approval selections."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from . import saved_docx_layout_service as storage
from .ordinary_layout_contracts import DeliveryArtifact, digest, encode, fail, job_identity, nonce, generation
from .ordinary_text_correction import paragraphs, apply_actions, word_changes, count_correction_words

VERSION = "ordinary_text_correction_v1"


def _qualify_corrected_formatting(base, edited):
    from .ordinary_edited_revision import qualify_edited_docx
    from .ordinary_text_correction import package
    from .ordinary_section_ownership import word_section_signature
    qualify_edited_docx(base, edited)
    try:
        before, _, _ = package(base)
        after, _, _ = package(edited)
        same = word_section_signature(before) == word_section_signature(after)
    except ValueError:
        fail("correction_word_section_changed", 409)
    if not same:
        fail("correction_word_section_changed", 409)


class TextCorrectionMixin:
    def _correction_findings(self, folder, view):
        from .ordinary_layout_service import _read
        findings = {}
        for suggestion in view.get("suggestions", []):
            for finding in suggestion.get("source_coverage_findings", (suggestion.get("result") or {}).get("source_coverage_findings", [])):
                findings[finding["finding_id"]] = deepcopy(finding)
        source_folder = folder
        if (folder / "alias.json").exists():
            source_folder = self.folder(_read(folder / "alias.json")["origin_job_id"])
        if (source_folder / "automatic.json").exists():
            _, manifest = self._baseline(source_folder)
            candidate = self._verified_automatic(source_folder, manifest, _read(source_folder / "automatic.json"))
            for page in (candidate.source_map.get("source_evidence") or {}).get("pages", []):
                for finding in page.get("findings", []):
                    findings[finding["finding_id"]] = deepcopy(finding)
        for finding in findings.values():
            finding["review_status"] = "unresolved"
            selected_sha = (view.get("delivery") or {}).get("sha256")
            path = folder / "source_finding_reviews" / finding["finding_id"] / (str(selected_sha) + ".json")
            if path.exists():
                disposition = _read(path)
                if disposition["finding_sha256"] != digest(encode({k:v for k,v in finding.items() if k != "review_status"})):
                    fail("correction_finding_changed", 409)
                if disposition["parent"]["sha256"] == (view.get("delivery") or {}).get("sha256"):
                    finding["review_status"] = disposition["disposition"]
        return list(findings.values())

    def review_source_finding(self, job, finding_id, parent, disposition, source_compared):
        from .ordinary_layout_service import _write, _read
        if disposition not in {"reviewed_no_change", "corrected"} or source_compared is not True:
            fail("correction_review_required")
        with self.scope(job.job_id) as folder:
            self._correction_identity(folder, job)
            _, current, _ = self._correction_parent(folder, job)
            if parent != current:
                fail("correction_parent_stale", 409)
            finding = next((f for f in self._correction_findings(folder, self.state(job.job_id)) if f["finding_id"] == finding_id), None)
            if finding is None:
                fail("correction_finding_unavailable")
            if disposition == "corrected" and (self.state(job.job_id).get("delivery") or {}).get("kind") != "text_corrected":
                fail("correction_approval_required")
            value = {"finding_sha256": digest(encode({k:v for k,v in finding.items() if k != "review_status"})),
                     "disposition": disposition, "parent": current, "source_compared": True}
            path = storage._mkdir(folder / "source_finding_reviews" / finding_id) / (current["sha256"] + ".json")
            if path.exists():
                if _read(path) != value:
                    fail("correction_finding_conflict", 409)
            else:
                _write(path, value)
            return self.text_correction_state(job)

    def _text_delivery_map(self, record):
        return {"version": VERSION, "docx_sha256": record["sha256"],
            "parent_docx_sha256": record["parent"]["sha256"], "identity": record["identity"],
            "paragraphs": record["paragraph_map"], "changes": record["changes"],
            "source_character_coverage": "operator_reviewed_changes_only", "rendered_layout_acceptance": "not_evaluated"}
    def _correction_records(self, folder):
        from .ordinary_layout_service import _records, _read
        return [_read(p) for p in _records(folder / "text_corrections")]

    def _correction_view(self, folder, view):
        rows = self._selections(folder)
        if rows and rows[-1]["kind"] == "text_corrected":
            view["delivery"] = deepcopy(rows[-1])
            reviewed = self._text_output_reviewed(folder, rows[-1])
            view["delivery"].update(stale=False, document_reviewed=reviewed,
                rendered_layout_acceptance="not_evaluated", text_approved=True)
            view["delivery"]["output_review_required"] = not reviewed
            view["delivery_generation"] = len(rows)
            view["text_correction"] = {"revision_id": rows[-1]["artifact_id"],
                "status": "approved", "output_review_required": not reviewed}
        view["text_correction_available"] = not bool(view.get("frozen"))
        return view

    def _correction_identity(self, folder, job):
        from .ordinary_layout_service import _read
        if (folder / "alias.json").exists():
            expected = _read(folder / "alias.json")["job_identity"]
        else:
            _, manifest = self._baseline(folder)
            expected = manifest["identity"]
        identity = job_identity(job, self.mode, self.workspace_id)
        if identity != expected:
            fail("correction_owner_changed", 409)
        return identity

    def _inherited_correction_map(self, folder, raw):
        from .ordinary_layout_service import _read
        from .ordinary_text_correction import package, _nodes
        mapping = [{k: v for k, v in row.items() if k not in {"text", "editable"}} for row in paragraphs(raw)]
        for row in mapping:
            row.update(parent_paragraph_id=None, regions=[], association_status="unmapped_source_reference_required")
        source_folder = folder
        if (folder / "alias.json").exists():
            source_folder = self.folder(_read(folder / "alias.json")["origin_job_id"])
        if (source_folder / "automatic.json").exists():
            baseline, manifest = self._baseline(source_folder)
            candidate = self._verified_automatic(source_folder, manifest, _read(source_folder / "automatic.json"))
            selected = (self.state(folder.name).get("delivery") or {})
            if selected.get("kind") not in {"automatic_unreviewed", "automatic_unreviewed_edited"}:
                return mapping
            from .ordinary_edited_revision import qualify_edited_docx
            try:
                qualify_edited_docx(candidate.docx_bytes, raw, source_layout_map=candidate.source_map)
            except ValueError:
                return mapping
            _, _, roots = package(raw)
            actual = {(name, tuple(path)): row for row, (name, _, path) in zip(mapping, _nodes(roots))}
            decorative_ids = {pid for rule in (candidate.source_map.get("source_layout_plan") or {}).get("decorative_rules", [])
                              for pid in rule["paragraph_ids"]}
            for logical in candidate.source_map.get("paragraphs", []):
                locations = logical.get("parts") or [logical]
                for part in locations:
                    uri = part.get("part_uri", logical.get("part_uri", "word/document.xml"))
                    location = part.get("location")
                    if uri not in roots or type(location) is not str:
                        continue
                    root = roots[uri]
                    found = root.xpath(location, namespaces={"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"})
                    if len(found) != 1:
                        continue
                    from .ordinary_text_correction import _path
                    row = actual.get((uri, tuple(_path(found[0], root))))
                    if row is not None:
                        row.update(parent_paragraph_id=logical["paragraph_id"], regions=deepcopy(logical.get("regions", [])),
                            association_status="inherited_coarse_source_association")
                        if logical["paragraph_id"] in decorative_ids:
                            row["decorative_rule"] = True
        return mapping

    def _correction_parent(self, folder, job, *, allow_frozen=False):
        from .ordinary_layout_service import _read
        view = self.state(job.job_id)
        if view.get("frozen") and not allow_frozen:
            fail("delivery_frozen", 409)
        self._require_settled(folder)
        if view.get("delivery"):
            artifact = self.resolve_delivery(job.job_id, view["delivery_generation"])
            raw = storage._read(artifact.path, storage.DOCX_MAX_BYTES)
            parent = {"sha256": artifact.sha256, "selection_id": artifact.selection_id,
                      "delivery_generation": artifact.generation, "baseline_id": view["baseline_id"]}
        else:
            raw = job.reviewed_docx
            parent = {"sha256": digest(raw), "selection_id": None,
                      "delivery_generation": view["delivery_generation"], "baseline_id": view["baseline_id"]}
        mapping = self._inherited_correction_map(folder, raw)
        if (view.get("delivery") or {}).get("kind") == "text_corrected":
            record = self._verify_correction(folder, view["delivery"]["artifact_id"])
            mapping = deepcopy(record["paragraph_map"])
        return raw, parent, mapping

    def text_correction_state(self, job):
        with self.scope(job.job_id) as folder:
            identity = self._correction_identity(folder, job)
            raw, parent, mapping = self._correction_parent(folder, job, allow_frozen=True)
            current = paragraphs(raw)
            for row, mapped in zip(current, mapping):
                row.update({k:v for k,v in mapped.items() if k not in {"text", "editable"}})
                if mapped.get("decorative_rule"):
                    row["editable"] = False
            from .ordinary_layout_service import _read
            drafts = []
            for record in self._correction_records(folder):
                draft_id = record["draft_id"]
                status = "cancelled" if (folder / "text_corrections" / draft_id / "cancelled.json").exists() else "draft"
                if any(r.get("artifact_id") == draft_id for r in self._selections(folder)):
                    status = "approved"
                drafts.append({"draft_id": draft_id, "status": status,
                    "parent_sha256": record["parent"]["sha256"], "changes": record["changes"]})
            return {"version": VERSION, "job_id": job.job_id, "identity": identity,
                "parent": parent, "paragraphs": current, "drafts": drafts,
                "source_findings": self._correction_findings(folder, self.state(job.job_id)),
                "selected_kind": (self.state(job.job_id).get("delivery") or {}).get("kind"),
                "source_pages": list(job.selected_pages), "paid_calls": 0,
                "frozen": bool(self.state(job.job_id).get("frozen")),
                "output_review_required": bool((self.state(job.job_id).get("delivery") or {}).get("output_review_required"))}

    def draft_text_correction(self, job, draft_nonce, expected_parent, actions, *, import_word=False):
        from .ordinary_layout_service import _read, _write, _put_immutable
        nonce(draft_nonce)
        if type(import_word) is not bool or type(expected_parent) is not dict:
            fail("correction_invalid_request")
        with self.scope(job.job_id) as folder:
            identity = self._correction_identity(folder, job)
            raw, parent, mapping = self._correction_parent(folder, job)
            if parent != expected_parent:
                fail("correction_parent_stale", 409)
            request = {"parent": parent, "actions": actions, "import_word": import_word}
            path = folder / "text_corrections" / (draft_nonce + ".json")
            if path.exists():
                prior = self._verify_correction(folder, draft_nonce)
                if prior["request"] != request:
                    fail("nonce_conflict", 409)
                return deepcopy(prior)
            if len(self._correction_records(folder)) >= 256:
                fail("record_limit", 413)
            if import_word:
                if actions != []:
                    fail("correction_invalid_request")
                working_path = (self.text_corrected_review_copy(job.job_id)
                    if (self.state(job.job_id).get("delivery") or {}).get("kind") == "text_corrected"
                    else folder / "automatic" / "working.docx")
                output = storage._read(working_path, storage.DOCX_MAX_BYTES)
                changes = word_changes(raw, output)
                # Structural ownership is exact. Stable IDs survive Word serialization.
                translated = {r["paragraph_id"]: m["paragraph_id"] for r, m in zip(paragraphs(raw), mapping)}
                for change in changes:
                    change["paragraph_id"] = translated[change["paragraph_id"]]
                out_map = [{**m, "part_uri": r["part_uri"], "location": r["location"]} for r, m in zip(paragraphs(output), mapping)]
            else:
                output, changes, out_map = apply_actions(raw, actions, job.target_lang,
                    job.selected_pages, paragraph_map=mapping)
            destination = storage._mkdir(folder / "text_corrections" / draft_nonce)
            _put_immutable(destination / "parent.docx", raw)
            _put_immutable(destination / "output.docx", output)
            count = count_correction_words(output)
            if type(count) is not int or count <= 0:
                fail("delivery_empty")
            record = {"version": VERSION, "draft_id": draft_nonce, "identity": identity,
                "parent": parent, "request": request, "changes": changes,
                "base_paragraph_map": mapping, "paragraph_map": out_map, "sha256": digest(output), "word_count": count,
                "source_map_kind": "operator_text_correction_not_raw_writer_map",
                "source_character_coverage": "not_proven", "paid_calls": 0,
                "document_reviewed": False, "rendered_layout_acceptance": "not_evaluated"}
            _write(path, record)
            self._verify_correction(folder, draft_nonce)
            return deepcopy(record)

    def _verify_correction(self, folder, draft_id):
        from .ordinary_layout_service import _read
        nonce(draft_id)
        record = _read(folder / "text_corrections" / (draft_id + ".json"))
        expected = (_read(folder / "alias.json")["job_identity"] if (folder / "alias.json").exists()
                    else self._baseline(folder)[1]["identity"])
        if record["identity"] != expected:
            fail("correction_owner_changed", 409)
        destination = folder / "text_corrections" / draft_id
        base = storage._read(destination / "parent.docx", storage.DOCX_MAX_BYTES)
        output = storage._read(destination / "output.docx", storage.DOCX_MAX_BYTES)
        if (record["version"] != VERSION or record["draft_id"] != draft_id
                or digest(base) != record["parent"]["sha256"] or digest(output) != record["sha256"]
                or count_correction_words(output) != record["word_count"]):
            fail("correction_revision_changed", 409)
        request = record["request"]
        if record.get("formatting_only"):
            _qualify_corrected_formatting(base, output)
        elif request["import_word"]:
            changes = word_changes(base, output)
            if [(c["before"], c["after"]) for c in changes] != [(c["before"], c["after"]) for c in record["changes"]]:
                fail("correction_revision_changed", 409)
        else:
            # Base map is retained explicitly; do not reassign IDs after deletion.
            mapped = record.get("base_paragraph_map") or paragraphs(base)
            derived, changes, mapping = apply_actions(base, request["actions"], record["identity"]["target_lang"],
                record["identity"]["selected_pages"], paragraph_map=mapped)
            if derived != output or changes != record["changes"] or mapping != record["paragraph_map"]:
                fail("correction_revision_changed", 409)
        return record

    def _text_output_reviewed(self, folder, row):
        from .ordinary_layout_service import _read
        path = folder / "text_output_reviews" / (row["selection_id"] + ".json")
        if not path.exists():
            return False
        value = _read(path)
        if value != {"selection_id": row["selection_id"], "sha256": row["sha256"], "generation": row["generation"], "all_pages_reviewed": True}:
            fail("correction_output_review_changed", 409)
        return True

    def review_text_output(self, job, selected_id, expected_generation, all_pages_reviewed):
        from .ordinary_layout_service import _write
        nonce(selected_id); generation(expected_generation)
        if all_pages_reviewed is not True:
            fail("correction_output_review_required")
        with self.scope(job.job_id) as folder:
            self._correction_identity(folder, job)
            row = self._selections(folder)[-1]
            if row["kind"] != "text_corrected" or (row["selection_id"], row["generation"]) != (selected_id, expected_generation):
                fail("correction_parent_stale", 409)
            self._verify_correction(folder, row["artifact_id"])
            path = storage._mkdir(folder / "text_output_reviews") / (selected_id + ".json")
            if not path.exists():
                _write(path, {"selection_id": selected_id, "sha256": row["sha256"], "generation": expected_generation, "all_pages_reviewed": True})
            self._text_output_reviewed(folder, row)
            return self.state(job.job_id)

    def _text_working_selection(self, folder):
        rows = self._selections(folder)
        by_id = {row["selection_id"]: row for row in rows}
        row = rows[-1]
        seen = set()
        while row.get("request", {}).get("formatting_only_parent"):
            if row["selection_id"] in seen:
                fail("correction_lineage_changed", 409)
            seen.add(row["selection_id"])
            self._verify_correction(folder, row["artifact_id"])
            parent = by_id.get(row["request"]["formatting_only_parent"])
            if not parent or parent["generation"] >= row["generation"] or parent["kind"] != "text_corrected":
                fail("correction_lineage_changed", 409)
            row = parent
        return row

    def text_corrected_review_copy(self, job_id):
        from .ordinary_layout_service import _put_immutable
        with self.scope(job_id) as folder:
            row = self._text_working_selection(folder)
            self._verify_correction(folder, row["artifact_id"])
            destination = folder / "deliveries" / row["selection_id"]
            working = destination / "working.docx"
            if not working.exists():
                _put_immutable(working, storage._read(destination / "output.docx", storage.DOCX_MAX_BYTES))
            return working

    def adopt_text_corrected_word_edit(self, job_id, *, without_changes=False):
        from .ordinary_layout_service import _write, _put_immutable
        from .ordinary_edited_revision import qualify_edited_docx
        with self.scope(job_id) as folder:
            rows = self._selections(folder)
            parent = rows[-1]
            prior = self._verify_correction(folder, parent["artifact_id"])
            working = self.text_corrected_review_copy(job_id)
            raw = storage._read(working, storage.DOCX_MAX_BYTES)
            if digest(raw) == parent["sha256"]:
                return self.state(job_id)
            if (folder / "frozen.json").exists():
                fail("delivery_frozen", 409)
            if without_changes:
                fail("edited_revision_changes_detected", 409)
            _qualify_corrected_formatting(storage._read(folder / "deliveries" / parent["selection_id"] / "output.docx", storage.DOCX_MAX_BYTES), raw)
            revision = digest(encode({"parent": parent["selection_id"], "sha256": digest(raw)}))[:32]
            destination = storage._mkdir(folder / "text_corrections" / revision)
            _put_immutable(destination / "parent.docx", storage._read(folder / "deliveries" / parent["selection_id"] / "output.docx", storage.DOCX_MAX_BYTES))
            _put_immutable(destination / "output.docx", raw)
            record = deepcopy(prior)
            record.update(draft_id=revision, parent={"sha256": parent["sha256"], "selection_id": parent["selection_id"],
                "delivery_generation": parent["generation"], "baseline_id": parent["baseline_id"]}, sha256=digest(raw),
                word_count=count_correction_words(raw), formatting_only=True, changes=[],
                request={"import_word": False, "actions": []},
                base_paragraph_map=prior["paragraph_map"])
            _write(folder / "text_corrections" / (revision + ".json"), record)
            self._verify_correction(folder, revision)
            delivered = storage._mkdir(folder / "deliveries" / revision)
            _put_immutable(delivered / "output.docx", raw)
            _write(delivered / "source_map.json", self._text_delivery_map(record))
            row = deepcopy(parent)
            row.update(selection_id=revision, generation=len(rows)+1, artifact_id=revision, sha256=digest(raw),
                word_count=record["word_count"], request={"formatting_only_parent": parent["selection_id"]})
            _write(folder / "selections" / f"{row['generation']:06d}.json", row)
            return self.state(job_id)

    def approve_text_correction(self, job, draft_id, approval_nonce, source_compared, changes_reviewed, rationale):
        from .ordinary_layout_service import _read, _write, _put_immutable
        nonce(draft_id); nonce(approval_nonce)
        if (source_compared is not True or changes_reviewed is not True or type(rationale) is not str
                or len(rationale) > 2000):
            fail("correction_review_required")
        with self.scope(job.job_id) as folder:
            identity = self._correction_identity(folder, job)
            record = self._verify_correction(folder, draft_id)
            approvals = self._selections(folder)
            request = {"draft_id": draft_id, "source_compared": True, "changes_reviewed": True, "rationale": rationale}
            prior = next((r for r in approvals if r["selection_id"] == approval_nonce), None)
            if prior:
                if prior.get("request") != request:
                    fail("nonce_conflict", 409)
                return self.state(job.job_id)
            _, parent, _ = self._correction_parent(folder, job)
            if parent != record["parent"] or record["identity"] != identity:
                fail("correction_parent_stale", 409)
            if (folder / "text_corrections" / draft_id / "cancelled.json").exists():
                fail("correction_cancelled", 409)
            destination = storage._mkdir(folder / "deliveries" / approval_nonce)
            _put_immutable(destination / "output.docx", storage._read(folder / "text_corrections" / draft_id / "output.docx", storage.DOCX_MAX_BYTES))
            _write(destination / "source_map.json", self._text_delivery_map(record))
            row = {"version": VERSION, "selection_id": approval_nonce, "generation": len(approvals)+1,
                "baseline_id": parent["baseline_id"], "kind": "text_corrected", "sha256": record["sha256"],
                "word_count": record["word_count"], "review_generation": None, "artifact_id": draft_id,
                "request": request, "text_approved": True, "output_review_required": True}
            _write(storage._mkdir(folder / "selections") / f"{row['generation']:06d}.json", row)
            return self.state(job.job_id)

    def cancel_text_correction(self, job, draft_id):
        from .ordinary_layout_service import _write
        with self.scope(job.job_id) as folder:
            self._correction_identity(folder, job)
            self._verify_correction(folder, draft_id)
            if any(r.get("artifact_id") == draft_id for r in self._selections(folder)):
                fail("correction_already_approved", 409)
            path = folder / "text_corrections" / draft_id / "cancelled.json"
            if not path.exists():
                _write(path, {"draft_id": draft_id, "status": "cancelled"})
            return self.text_correction_state(job)

    def _resolve_text_delivery(self, folder, job_id, expected, freeze_nonce, require_settled):
        from .ordinary_layout_service import _read, _write
        rows = self._selections(folder)
        if not rows or rows[-1]["kind"] != "text_corrected":
            return None
        row = rows[-1]
        if expected != row["generation"]:
            fail("delivery_stale", 409)
        if require_settled or freeze_nonce:
            self._require_settled(folder)
            if not self._text_output_reviewed(folder, row):
                fail("correction_output_review_required", 409)
        record = self._verify_correction(folder, row["artifact_id"])
        if row["sha256"] != record["sha256"] or row["word_count"] != record["word_count"]:
            fail("correction_revision_changed", 409)
        frozen = folder / "frozen.json"
        if freeze_nonce:
            value = {"freeze_nonce": freeze_nonce, "generation": expected, "sha256": row["sha256"]}
            if frozen.exists() and _read(frozen) != value:
                fail("delivery_frozen", 409)
            if not frozen.exists():
                _write(frozen, value)
        if frozen.exists() and (_read(frozen)["generation"], _read(frozen)["sha256"]) != (expected, row["sha256"]):
            fail("delivery_frozen", 409)
        identity = record["identity"]
        path = folder / "deliveries" / row["selection_id"] / "output.docx"
        raw = storage._read(path, storage.DOCX_MAX_BYTES)
        if (digest(raw) != record["sha256"]
                or count_correction_words(raw) != record["word_count"]
                or _read(path.parent / "source_map.json") != self._text_delivery_map(record)):
            fail("correction_delivery_changed", 409)
        return DeliveryArtifact(job_id, identity["run_id"], path,
            row["sha256"], row["word_count"], identity["target_lang"], identity["source_sha256"], expected,
            row["selection_id"], "text_corrected", frozen.exists())
