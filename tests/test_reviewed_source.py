"""Fictional reviewed-image cases; never load or adapt private real candidates."""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from legalpdf_translate.reviewed_source import (
    ReviewedSourceEvidence, ReviewedSourceError, REVIEWED_SOURCE_VERSION,
    REVIEWED_ACCEPTANCE_VERSION, adapt_reviewed_candidate,
)
from legalpdf_translate.source_readiness import (
    source_structure_digest, source_readiness_diagnostics, _digest,
    verify_source_review, verify_reviewed_page, SourceReadinessError,
)
from tests.test_source_review_candidate import fixture, put, encode, digest, bind_review, build
from tests.test_new_translation_blocks import SOURCE


def reviewed_fixture(pages=2, *, document_bytes=b"FICTIONAL PDF", page_sizes=None, page_identities=None):
    template, _, initial = fixture()
    document = digest(document_bytes)
    artifacts = {document: document_bytes}
    manifest = {"version": 1, "kind": "source_review_candidate_manifest",
                "document_sha256": document, "pages": []}
    starts = {1, 3, 4} if pages == 9 else {1}
    for number in range(1, pages + 1):
        page = deepcopy(template["pages"][0])
        page["page_number"] = number
        original = page["variants"][0]
        raw = json.loads(initial[original["structure_sha256"]])
        raw["page_number"] = number
        raw["source_file_sha256"] = document
        raw["metadata"]["source_page_identity"]["source_file_sha256"] = document
        rename = {b["id"]: b["id"].replace("p0001_", f"p{number:04d}_") for b in raw["blocks"]}
        for block in raw["blocks"]:
            block["id"] = rename[block["id"]]
        for word in raw["metadata"]["ocr_word_evidence"]["words"]:
            word["block_id"] = rename[word["block_id"]]
        # CRLF remains raw evidence, with the normalized selected-text hash intact.
        text = initial[original["text_sha256"]].replace(b"\n", b"\r\n")
        variant = {"id": "baseline", "text_sha256": put(artifacts, text),
                   "tsv_sha256": put(artifacts, initial[original["tsv_sha256"]]),
                   "structure_sha256": put(artifacts, raw)}
        put(artifacts, initial[page["image_sha256"]])
        count = 3 if number in ({1, 4} if pages == 9 else {1}) else 1
        page["variants"] = [{**variant, "id": label} for label in ("baseline", "psm3", "psm11")[:count]]
        page["baseline_variant"] = "baseline"
        before = "\n".join(b["text"] for b in raw["blocks"])
        after = SOURCE.replace("circunstancias", "circunstâncias") + "\n\n" + "Revisão explícita."
        ids = [b["id"] for b in raw["blocks"]]
        page["actions"] = [{"id": "whole_page", "kind": "replace", "baseline_block_ids": ids,
            "before_text": before, "before_sha256": digest(before.encode()),
            "after_text": after, "after_sha256": digest(after.encode()),
            "region_px": [0, 0, 200, 300],
            "evidence_refs": [{"variant_id": v["id"], "block_ids": ids} for v in page["variants"]],
            "rationale": "Fictional full-page review only."}]
        page["reading_order"] = ["whole_page"]
        manifest["pages"].append(page)
        review = {"version": 1, "kind": "image_source_review", "review_kind": "ai_test_review",
            "reviewer": "Fictional test reviewer", "document_sha256": document,
            "page_number": number, "image_sha256": page["image_sha256"], "page_plan_sha256": "",
            "full_page_review_completed": True, "reading_order_reviewed": True,
            "boundary": {"decision": "start" if number in starts else "continuation",
                         "rationale": "Fictional boundary."},
            "findings": [{"id": "f1", "category": "reading_order", "status": "resolved",
                         "action_ids": ["whole_page"], "rationale": "Fictional order."}]}
        bind_review(manifest, review, artifacts, number - 1)
    candidate = build(manifest, artifacts, require_complete=True)
    evidence = ReviewedSourceEvidence(encode(candidate), encode(manifest), tuple(artifacts.items()))
    identities = page_identities or {n: {"source_file_sha256": document,
        "image_sha256": manifest["pages"][n - 1]["image_sha256"], "source_type": "browser_pdf_image",
        "paper_size_basis": "source_pdf"} for n in range(1, pages + 1)}
    sizes = page_sizes or {n: (595.276, 841.89) for n in range(1, pages + 1)}
    bindings = dict(candidate_sha256=digest(evidence.candidate), manifest_sha256=digest(evidence.manifest),
                    source_hash=document, page_identities=identities, page_sizes=sizes)
    sources = adapt_reviewed_candidate(evidence, **bindings)
    return SimpleNamespace(evidence=evidence, bindings=bindings, sources=sources, manifest=manifest,
                           candidate=candidate, artifacts=artifacts)


def decision_envelope(case, *, paths=None):
    def entry(name, raw):
        return {"path": (paths or {}).get(digest(raw), f"C:/fictional/{name}.json"), "sha256": digest(raw)}
    return {"version": REVIEWED_ACCEPTANCE_VERSION, "review_kind": "ai_test_review",
        "review_evidence_sha256": digest(b"SEPARATE FICTIONAL SOURCE DECISION"),
        "source_file_sha256": case.bindings["source_hash"],
        "candidate_file": entry("candidate", case.evidence.candidate),
        "manifest_file": entry("manifest", case.evidence.manifest),
        "evidence_files": [entry(key, raw) for key, raw in case.evidence.artifacts],
        "pages": [{"page_number": n, "reviewed_source_sha256": source_structure_digest(s),
            "readiness_sha256": _digest(source_readiness_diagnostics(s)),
            "source_fidelity": "accepted", "document_boundary": "accepted", "unresolved_findings": []}
            for n, s in case.sources.items()]}


def verify(case, review=None, evidence=None):
    return verify_source_review(json.dumps(decision_envelope(case) if review is None else review),
        source_hash=case.bindings["source_hash"], page_identities=case.bindings["page_identities"],
        page_sizes=case.bindings["page_sizes"],
        reviewed_evidence=case.evidence if evidence is None else evidence)


@pytest.mark.parametrize("pages,variants", [(9, 13), (2, 4)])
def test_complete_case_exact_text_ids_provenance_and_immutability(pages, variants):
    case = reviewed_fixture(pages)
    before = deepcopy(case.evidence)
    sources = adapt_reviewed_candidate(case.evidence, **case.bindings)
    assert case.evidence == before
    assert sum(len(p["variants"]) for p in case.manifest["pages"]) == variants
    assert [n for n, s in sources.items() if s.document_start] == ([1, 3, 4] if pages == 9 else [1])
    for n, source in sources.items():
        assert source.text == case.candidate["pages"][n - 1]["candidate_text"]
        assert "circunstâncias" in source.text and "\n\n" in source.text
        assert source.provenance == REVIEWED_SOURCE_VERSION and source.uncertain
        assert not source.continuation_from_previous and not source.continuation_to_next
        assert len(source.blocks) == 1 and source.blocks[0].id.endswith("_b100000001")
        assert source.blocks[0].bbox is None and source.blocks[0].role == "paragraph"
        assert source.blocks[0].table_id is None and source.blocks[0].continuation_of is None
        assert "ocr_word_evidence" not in source.metadata
        assert source.metadata["reviewed_source"]["source_acceptance"] == "not_evaluated"
        assert source_readiness_diagnostics(source)["status"] == "review_required"
    assert verify(case)


@pytest.mark.parametrize("change", [
    lambda c: c.update(production_eligible=True),
    lambda c: c.update(source_acceptance="accepted"),
    lambda c: c.update(layout_acceptance="accepted"),
    lambda c: c.update(provenance="local_ocr_tsv"),
    lambda c: c.update(version=True),
    lambda c: c["pages"].pop(),
    lambda c: c["pages"].append(deepcopy(c["pages"][0])),
    lambda c: c["pages"][0].update(candidate_text="altered"),
    lambda c: c["pages"][0].update(review_record_complete=False),
    lambda c: c["pages"][0].update(bbox=[0, 0, 200, 300]),
    lambda c: c["pages"][0]["review"].update(full_page_review_completed=False),
    lambda c: c["pages"][0]["review"]["boundary"].update(decision="continuation"),
    lambda c: c["review_manifest"]["pages"][0]["actions"][0].update(after_text="forged"),
])
def test_resigned_candidate_does_not_hide_schema_or_record_drift(change):
    case = reviewed_fixture()
    changed = deepcopy(case.candidate)
    change(changed)
    changed["candidate_sha256"] = digest(encode({k: v for k, v in changed.items() if k != "candidate_sha256"}))
    raw = encode(changed)
    with pytest.raises(ReviewedSourceError):
        adapt_reviewed_candidate(replace(case.evidence, candidate=raw),
            **{**case.bindings, "candidate_sha256": digest(raw)})


@pytest.mark.parametrize("kind", ["external_hash", "manifest_hash", "image", "document", "page_inventory",
    "size", "duplicate_artifact", "raw_artifact", "duplicate_json", "nonfinite", "oversize", "wrong_type"])
def test_missing_or_corrupt_evidence_fails_closed(kind):
    case = reviewed_fixture()
    args, evidence = deepcopy(case.bindings), case.evidence
    if kind == "external_hash": args["candidate_sha256"] = "a" * 64
    if kind == "manifest_hash": args["manifest_sha256"] = "a" * 64
    if kind == "image": args["page_identities"][1]["image_sha256"] = "a" * 64
    if kind == "document": args["source_hash"] = "a" * 64
    if kind == "page_inventory": args["page_identities"].pop(2)
    if kind == "size": args["page_sizes"][1] = (float("nan"), 400)
    if kind == "duplicate_artifact": evidence = replace(evidence, artifacts=evidence.artifacts + evidence.artifacts[:1])
    if kind == "raw_artifact":
        key, raw = evidence.artifacts[0]
        evidence = replace(evidence, artifacts=((key, raw + b"changed"),) + evidence.artifacts[1:])
    if kind in {"duplicate_json", "nonfinite", "oversize"}:
        raw = {"duplicate_json": b'{"version":1,"version":1}',
               "nonfinite": b'{"version":NaN}', "oversize": b" " * 8_000_001}[kind]
        evidence = replace(evidence, candidate=raw)
        args["candidate_sha256"] = digest(raw)
    if kind == "wrong_type": evidence = {}
    with pytest.raises(ReviewedSourceError):
        adapt_reviewed_candidate(evidence, **args)


@pytest.mark.parametrize("change", [
    lambda r: r["pages"][1].update(source_fidelity="not_evaluated"),
    lambda r: r["pages"][1].update(document_boundary="unresolved"),
    lambda r: r["pages"][1].update(unresolved_findings=["material"]),
    lambda r: r["pages"][0].update(reviewed_source_sha256="a" * 64),
    lambda r: r["pages"][0].update(readiness_sha256="a" * 64),
    lambda r: r["pages"][0].update(source_structure={}),
    lambda r: r["pages"].pop(),
    lambda r: r["pages"].reverse(),
    lambda r: r["candidate_file"].update(sha256="a" * 64),
    lambda r: r["evidence_files"].pop(),
])
def test_explicit_full_case_source_decision_is_required(change):
    case = reviewed_fixture()
    envelope = decision_envelope(case)
    change(envelope)
    with pytest.raises(SourceReadinessError):
        verify(case, envelope)


def test_bare_candidate_or_legacy_review_cannot_activate_reviewed_source():
    case = reviewed_fixture()
    from tests.source_readiness_fixtures import synthetic_review
    for raw in (case.evidence.candidate.decode(), synthetic_review(list(case.sources.values())),
                json.dumps(decision_envelope(case))):
        with pytest.raises(SourceReadinessError):
            verify_source_review(raw, page_identities=case.bindings["page_identities"],
                                 source_hash=case.bindings["source_hash"])


@pytest.mark.parametrize("change", [
    lambda s: s.blocks[0].__setattr__("text", "altered"),
    lambda s: s.__setattr__("uncertain", False),
    lambda s: s.__setattr__("document_start", False),
    lambda s: s.blocks[0].__setattr__("bbox", (0, 0, 10, 10)),
    lambda s: s.metadata["reviewed_source"]["mapping"][0].update(action_id="forged"),
])
def test_adapted_structure_drift_never_inherits_source_acceptance(change):
    case = reviewed_fixture()
    source = deepcopy(case.sources[1])
    change(source)
    with pytest.raises(SourceReadinessError):
        verify_reviewed_page(json.dumps(decision_envelope(case)), source=source,
            page_identities=case.bindings["page_identities"], source_hash=case.bindings["source_hash"],
            reviewed_evidence=case.evidence, page_sizes=case.bindings["page_sizes"])


def test_layout_rejects_forged_old_geometry_even_with_old_eligibility(tmp_path, monkeypatch):
    from legalpdf_translate import layout_integration as layout
    case = reviewed_fixture()
    source = case.sources[1]
    source.uncertain = False
    source.blocks[0].uncertain = False
    source.blocks[0].bbox = (10, 20, 300, 400)
    monkeypatch.setattr(layout, "_render_source", lambda *a: pytest.fail("No render"))
    monkeypatch.setattr(layout, "_file_hash", lambda *a: pytest.fail("No cache lookup"))
    result = layout.derive_source_layout(source, tmp_path / "absent.pdf",
                                         layout_eligibility={"status": "eligible"})
    assert result["status"] == "needs_review" and result["review_required"]
    assert result["bands"] == []
    assert "reviewed_source_geometry_not_verified" in result["warnings"]
