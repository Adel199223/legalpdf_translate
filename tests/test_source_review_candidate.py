"""Fictional, in-memory source reviews only; no real OCR or document repair."""
from copy import deepcopy
import hashlib
import json
import struct
import zlib

import pytest

from tooling.source_review_candidate import (
    CandidateError, build_candidate, verify_candidate,
)


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(value).hexdigest()


def png(width=200, height=300):
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + b"\xff" * width) * height))
            + chunk(b"IEND", b""))


def put(artifacts, value):
    raw = value if isinstance(value, bytes) else encode(value)
    key = digest(raw)
    artifacts[key] = raw
    return key


def fixture():
    artifacts = {}
    document = put(artifacts, b"Fictional document only")
    raster = put(artifacts, png())
    blocks = [
        {"id": "p0001_b0001", "text": "Processo 12I/26", "bbox": [10, 10, 180, 30]},
        {"id": "p0001_b0002", "text": "Artigo 42", "bbox": [10, 40, 180, 60]},
        {"id": "p0001_b0003", "text": "sete", "bbox": [10, 70, 180, 90]},
    ]
    text = "\n".join(b["text"] for b in blocks)
    words = []
    rows = ["level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"]
    for index, block in enumerate(blocks, 1):
        for n, word in enumerate(block["text"].split(), 1):
            box = [10 + (n - 1) * 50, 10 + (index - 1) * 30,
                   50 + (n - 1) * 50, 30 + (index - 1) * 30]
            words.append({"block_id": block["id"], "text": word, "bbox_px": box,
                          "confidence": 80, "group": [1, index, 1, 1], "word_number": n})
            rows.append(f"5\t1\t{index}\t1\t1\t{n}\t{box[0]}\t{box[1]}\t40\t20\t80\t{word}")
    tsv = put(artifacts, ("\n".join(rows) + "\n").encode())
    raw_text = put(artifacts, (text + "\n").encode())
    source = {"version": 1, "page_number": 1, "provenance": "local_ocr_tsv",
              "source_file_sha256": document, "source_sha256": digest(text.encode()),
              "source_text_sha256": digest(text.encode()), "translation_sha256": None,
              "blocks": blocks, "width_pt": 200, "height_pt": 300,
              "uncertain": True, "document_start": False,
              "metadata": {"source_page_identity": {"source_file_sha256": document,
                          "image_sha256": raster},
                  "ocr_tsv_sha256": tsv, "selected_text_sha256": digest(text.encode()),
                  "ocr_word_evidence": {"version": 1, "tsv_sha256": tsv,
                                       "image_size_px": [200, 300], "words": words}}}
    variant = {"id": "baseline", "text_sha256": raw_text, "tsv_sha256": tsv,
               "structure_sha256": put(artifacts, source)}
    actions = []
    for index, block in enumerate(blocks, 1):
        after = ["Processo 121/26", "Artigo 42", ""][index - 1]
        actions.append({"id": f"a{index}", "kind": ["replace", "retain", "omit_nontext"][index - 1],
                        "baseline_block_ids": [block["id"]], "before_text": block["text"],
                        "before_sha256": digest(block["text"].encode()), "after_text": after,
                        "after_sha256": digest(after.encode()), "region_px": block["bbox"],
                        "evidence_refs": [{"variant_id": "baseline", "block_ids": [block["id"]]}],
                        "rationale": "Fictional image review: digit, citation, decorative separator."})
    page = {"page_number": 1, "image_sha256": raster, "image_size_px": [200, 300],
            "variants": [variant], "baseline_variant": "baseline", "actions": actions,
            "reading_order": ["a1", "a2"], "review_evidence_sha256": ""}
    manifest = {"version": 1, "kind": "source_review_candidate_manifest",
                "document_sha256": document, "pages": [page]}
    review = {"version": 1, "kind": "image_source_review", "review_kind": "ai_test_review",
              "reviewer": "Synthetic reviewer", "document_sha256": document, "page_number": 1,
              "image_sha256": raster, "page_plan_sha256": "",
              "full_page_review_completed": True, "reading_order_reviewed": True,
              "boundary": {"decision": "start", "rationale": "Fictional first page."},
              "findings": [{"id": "f1", "category": "identifier", "status": "resolved",
                            "action_ids": ["a1"], "rationale": "Image clearly shows the digit."}]}
    bind_review(manifest, review, artifacts)
    return manifest, review, artifacts


def bind_review(manifest, review, artifacts, page_index=0):
    page = manifest["pages"][page_index]
    review["page_plan_sha256"] = digest(encode(
        {k: v for k, v in page.items() if k != "review_evidence_sha256"}))
    page["review_evidence_sha256"] = put(artifacts, review)


def build(manifest, artifacts, **kwargs):
    raw = encode(manifest)
    return build_candidate(raw, expected_manifest_sha256=digest(raw),
                           document_sha256=manifest["document_sha256"],
                           page_numbers=tuple(p["page_number"] for p in manifest["pages"]),
                           artifacts=artifacts, **kwargs)


def test_complete_record_is_deterministic_nonproduction_and_does_not_mutate():
    manifest, _, artifacts = fixture()
    before = deepcopy((manifest, artifacts))
    result = build(manifest, artifacts, require_complete=True)
    assert result == build(manifest, artifacts, require_complete=True)
    assert (manifest, artifacts) == before
    assert result["status"] == "review_record_complete"
    assert result["production_eligible"] is False
    assert result["source_acceptance"] == result["layout_acceptance"] == "not_evaluated"
    assert result["provenance"] == "reviewed_image_transcription_candidate_v1"
    assert result["pages"][0]["candidate_text"] == "Processo 121/26\nArtigo 42"
    assert "confidence" not in result["pages"][0]
    assert "source_structure" not in result["pages"][0]
    assert verify_candidate(encode(result), encode(manifest),
        expected_manifest_sha256=digest(encode(manifest)),
        document_sha256=manifest["document_sha256"], page_numbers=(1,),
        artifacts=artifacts) == result
    result["review_manifest"]["pages"][0]["actions"][0]["after_text"] = "mutated"
    assert (manifest, artifacts) == before


def test_image_only_omission_and_explicit_reordering_keep_separate_provenance():
    manifest, review, artifacts = fixture()
    page = manifest["pages"][0]
    text = "A mesma expressão repetida repetida."
    page["actions"].append({"id": "a4", "kind": "transcribe", "baseline_block_ids": [],
        "before_text": "", "before_sha256": digest(b""), "after_text": text,
        "after_sha256": digest(text.encode()), "region_px": [10, 100, 180, 140],
        "evidence_refs": [], "rationale": "Omitted image text; repetition is visible."})
    page["reading_order"] = ["a2", "a1", "a4"]
    bind_review(manifest, review, artifacts)
    result = build(manifest, artifacts, require_complete=True)
    assert result["pages"][0]["candidate_text"] == "Artigo 42\nProcesso 121/26\n" + text
    assert result["pages"][0]["boundary_proposal"]["decision"] == "start"


@pytest.mark.parametrize("category", ["identifier", "citation", "omission", "invention", "reading_order", "boundary", "other"])
def test_unresolved_semantic_findings_are_retained_and_block_completeness(category):
    manifest, review, artifacts = fixture()
    review["findings"][0].update(category=category, status="unresolved")
    bind_review(manifest, review, artifacts)
    candidate = build(manifest, artifacts)
    assert candidate["status"] == "review_record_incomplete"
    assert candidate["pages"][0]["review"]["findings"][0]["status"] == "unresolved"
    with pytest.raises(CandidateError, match="candidate_review_unresolved"):
        build(manifest, artifacts, require_complete=True)


@pytest.mark.parametrize("change", [
    lambda p: p["actions"].pop(),
    lambda p: p["actions"][1].update(baseline_block_ids=["p0001_b0001"]),
    lambda p: p["actions"][0].update(before_text="incorrect"),
    lambda p: p["actions"][0].update(before_sha256="0"*64),
    lambda p: p["actions"][0].update(after_sha256="0"*64),
    lambda p: p["actions"][0].update(kind="retain"),
    lambda p: p["actions"][0].update(kind="delete"),
    lambda p: p["actions"][0].update(confidence=100),
    lambda p: p["actions"][0].update(region_px=[10, 10, 10, 20]),
    lambda p: p["actions"][0].update(region_px=[-1, 10, 20, 20]),
    lambda p: p["actions"][0].update(region_px=[0, 0, 201, 300]),
    lambda p: p["actions"][0].update(region_px=[False, 10, 20, 20]),
    lambda p: p["actions"][1].update(region_px=[10, 10, 180, 30]),
    lambda p: p["actions"][0].update(evidence_refs=[{"variant_id": "unknown", "block_ids": ["p0001_b0001"]}]),
    lambda p: p["actions"][0].update(evidence_refs=[{"variant_id": "baseline", "block_ids": ["foreign"]}]),
    lambda p: p["actions"][0].update(rationale=" "),
    lambda p: p.update(reading_order=["a1"]),
    lambda p: p.update(reading_order=["a1", "a1", "a2"]),
    lambda p: p.update(reading_order=["a1", "a2", "a3"]),
    lambda p: p.update(image_size_px=[100, 300]),
    lambda p: p.update(baseline_variant="foreign"),
    lambda p: p.update(production_eligible=True),
])
def test_invalid_page_plan_is_rejected_even_with_rebound_review(change):
    manifest, review, artifacts = fixture()
    change(manifest["pages"][0])
    bind_review(manifest, review, artifacts)
    with pytest.raises(CandidateError):
        build(manifest, artifacts)


@pytest.mark.parametrize("change", [
    lambda r: r.update(page_plan_sha256="0"*64),
    lambda r: r.update(image_sha256="0"*64),
    lambda r: r.update(document_sha256="0"*64),
    lambda r: r.update(page_number=2),
    lambda r: r.update(review_kind="certified"),
    lambda r: r.update(reviewer=""),
    lambda r: r.update(full_page_review_completed="yes"),
    lambda r: r["findings"][0].update(action_ids=["absent"]),
    lambda r: r.update(source_fidelity="accepted"),
])
def test_stale_or_spoofed_review_fails(change):
    manifest, review, artifacts = fixture()
    change(review)
    manifest["pages"][0]["review_evidence_sha256"] = put(artifacts, review)
    with pytest.raises(CandidateError):
        build(manifest, artifacts)


@pytest.mark.parametrize("field", ["full_page_review_completed", "reading_order_reviewed", "boundary"])
def test_incomplete_review_is_never_complete(field):
    manifest, review, artifacts = fixture()
    if field == "boundary":
        review[field]["decision"] = "unresolved"
    else:
        review[field] = False
    bind_review(manifest, review, artifacts)
    assert build(manifest, artifacts)["status"] == "review_record_incomplete"
    with pytest.raises(CandidateError):
        build(manifest, artifacts, require_complete=True)


@pytest.mark.parametrize("role", ["document", "image", "text", "tsv", "structure", "review"])
def test_all_evidence_bytes_are_checked_not_just_declared_hashes(role):
    manifest, _, artifacts = fixture()
    page = manifest["pages"][0]
    hashes = {"document": manifest["document_sha256"], "image": page["image_sha256"],
              "review": page["review_evidence_sha256"],
              **{k: page["variants"][0][k+"_sha256"] for k in ("text", "tsv", "structure")}}
    artifacts[hashes[role]] += b"changed"
    with pytest.raises(CandidateError, match="artifact_binding_invalid"):
        build(manifest, artifacts)


def test_external_inventory_and_manifest_hash_cannot_be_self_supplied_from_partial_case():
    manifest, _, artifacts = fixture()
    raw = encode(manifest)
    for overrides in ({"page_numbers": (1, 2)}, {"page_numbers": (True,)},
                      {"page_numbers": (1, 1)}, {"document_sha256": "0"*64},
                      {"expected_manifest_sha256": "0"*64}):
        args = dict(expected_manifest_sha256=digest(raw),
                    document_sha256=manifest["document_sha256"], page_numbers=(1,), artifacts=artifacts)
        args.update(overrides)
        with pytest.raises(CandidateError):
            build_candidate(raw, **args)


def test_duplicate_keys_nonfinite_json_and_changed_candidate_fail_closed():
    manifest, _, artifacts = fixture()
    for raw in (b'{"version":1,"version":1}', b'{"number":NaN}', b'{"number":Infinity}'):
        with pytest.raises(CandidateError):
            build_candidate(raw, expected_manifest_sha256=digest(raw),
                document_sha256=manifest["document_sha256"], page_numbers=(1,), artifacts=artifacts)
    candidate = build(manifest, artifacts)
    candidate["pages"][0]["candidate_text"] += " fabricated"
    with pytest.raises(CandidateError, match="candidate_changed"):
        verify_candidate(encode(candidate), encode(manifest),
            expected_manifest_sha256=digest(encode(manifest)),
            document_sha256=manifest["document_sha256"], page_numbers=(1,), artifacts=artifacts)


def alter_source(manifest, artifacts, change, variant_index=0):
    variant = manifest["pages"][0]["variants"][variant_index]
    source = json.loads(artifacts[variant["structure_sha256"]])
    change(source)
    variant["structure_sha256"] = put(artifacts, source)


@pytest.mark.parametrize("change", [
    lambda s: s.update(provenance="reviewed_image_transcription"),
    lambda s: s.update(source_file_sha256="0"*64),
    lambda s: s.update(page_number=2),
    lambda s: s.update(source_sha256="0"*64),
    lambda s: s.update(translation_sha256="1"*64),
    lambda s: s["blocks"][0].update(text="changed source text"),
    lambda s: s["metadata"].update(selected_text_sha256="0"*64),
    lambda s: s["metadata"]["ocr_word_evidence"].update(tsv_sha256="0"*64),
    lambda s: s["metadata"]["ocr_word_evidence"].update(image_size_px=[100, 300]),
    lambda s: s["metadata"]["ocr_word_evidence"]["words"][0].update(confidence=100),
    lambda s: s["metadata"]["ocr_word_evidence"]["words"][0].update(bbox_px=[1, 1, 2, 2]),
    lambda s: s["metadata"]["ocr_word_evidence"]["words"][0].update(block_id="p0001_b0002"),
    lambda s: s["metadata"]["ocr_word_evidence"]["words"].pop(),
])
def test_raw_source_inconsistency_fails_even_when_artifact_hash_is_rebound(change):
    manifest, review, artifacts = fixture()
    alter_source(manifest, artifacts, change)
    bind_review(manifest, review, artifacts)
    with pytest.raises(CandidateError):
        build(manifest, artifacts)


def test_raw_windows_line_endings_are_bound_separately_from_selected_text():
    manifest, review, artifacts = fixture()
    variant = manifest["pages"][0]["variants"][0]
    raw = artifacts[variant["text_sha256"]].replace(b"\n", b"\r\n")
    variant["text_sha256"] = put(artifacts, raw)
    bind_review(manifest, review, artifacts)
    assert build(manifest, artifacts, require_complete=True)["production_eligible"] is False


def test_review_region_cannot_point_elsewhere_on_the_same_image():
    manifest, review, artifacts = fixture()
    manifest["pages"][0]["actions"][0]["region_px"] = [10, 200, 180, 250]
    bind_review(manifest, review, artifacts)
    with pytest.raises(CandidateError, match="evidence_region_mismatch"):
        build(manifest, artifacts)


def test_every_variant_is_validated_even_when_no_action_cites_it():
    manifest, review, artifacts = fixture()
    other = deepcopy(manifest["pages"][0]["variants"][0])
    other["id"] = "alternative"
    manifest["pages"][0]["variants"].append(other)
    bind_review(manifest, review, artifacts)
    assert build(manifest, artifacts)["status"] == "review_record_complete"
    alter_source(manifest, artifacts, lambda s: s.update(page_number=3), variant_index=1)
    bind_review(manifest, review, artifacts)
    with pytest.raises(CandidateError):
        build(manifest, artifacts)


def test_full_case_checks_later_pages_and_does_not_accept_a_pilot_subset():
    manifest, review, artifacts = fixture()
    page = deepcopy(manifest["pages"][0])
    page["page_number"] = 2
    variant = page["variants"][0]
    source = json.loads(artifacts[variant["structure_sha256"]])
    source["page_number"] = 2
    for block in source["blocks"]:
        block["id"] = block["id"].replace("p0001", "p0002")
    for word in source["metadata"]["ocr_word_evidence"]["words"]:
        word["block_id"] = word["block_id"].replace("p0001", "p0002")
    variant["structure_sha256"] = put(artifacts, source)
    for action in page["actions"]:
        action["baseline_block_ids"] = [k.replace("p0001", "p0002") for k in action["baseline_block_ids"]]
        for ref in action["evidence_refs"]:
            ref["block_ids"] = [k.replace("p0001", "p0002") for k in ref["block_ids"]]
    manifest["pages"].append(page)
    review2 = deepcopy(review)
    review2.update(page_number=2, full_page_review_completed=False)
    review2["boundary"]["decision"] = "continuation"
    bind_review(manifest, review2, artifacts, 1)
    candidate = build(manifest, artifacts)
    assert len(candidate["pages"]) == 2
    assert candidate["pages"][0]["review_record_complete"]
    assert not candidate["pages"][1]["review_record_complete"]
    with pytest.raises(CandidateError, match="candidate_review_unresolved"):
        build(manifest, artifacts, require_complete=True)
    review2["full_page_review_completed"] = True
    bind_review(manifest, review2, artifacts, 1)
    assert build(manifest, artifacts, require_complete=True)["status"] == "review_record_complete"


def test_imports_and_execution_have_no_ambient_io_or_production_dependencies(monkeypatch):
    import ast
    import builtins
    import inspect
    import os
    import socket
    import subprocess
    from tooling import source_review_candidate as module
    tree = ast.parse(inspect.getsource(module))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    imports |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    assert imports <= {"__future__", "csv", "hashlib", "io", "json", "math", "re",
                       "struct", "zlib", "typing"}
    manifest, _, artifacts = fixture()
    def forbidden(*args, **kwargs):
        pytest.fail("Ambient side effect forbidden")
    with monkeypatch.context() as guard:
        guard.setattr(builtins, "open", forbidden)
        guard.setattr(os, "getenv", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(subprocess, "Popen", forbidden)
        assert build(manifest, artifacts)["production_eligible"] is False


def test_candidate_schema_cannot_be_used_as_production_source_acceptance():
    from legalpdf_translate.source_readiness import verify_source_review
    manifest, _, artifacts = fixture()
    result = build(manifest, artifacts, require_complete=True)
    with pytest.raises(ValueError, match="acceptance_source_review_unresolved"):
        verify_source_review(encode(result).decode(), page_identities={1: {}},
                             source_hash=manifest["document_sha256"])
