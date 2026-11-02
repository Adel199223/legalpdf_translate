"""Fictional source fractions prove suppression without deleting source text."""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
import uuid
from zipfile import ZipFile

import fitz
from docx import Document
import pytest

from legalpdf_translate.docx_writer import assemble_docx
from legalpdf_translate.types import TargetLang
from legalpdf_translate.saved_docx_layout import default_decisions
from legalpdf_translate.ordinary_auto_layout_artifacts import bind_raw_page_map, build_unreviewed_candidate, verify_unreviewed_candidate
from legalpdf_translate.ordinary_source_folio_proof import KEY, RECIPE_KEY, VERSION, derive_proof, verify_proof, target_spans


def source_pdf(labels=("1 / 3", "2 / 3", "3 / 3"), *, duplicate=False, midpage=False, rotated=False):
    with fitz.open() as pdf:
        for label in labels:
            page = pdf.new_page(width=1000, height=1400)
            page.insert_text((80, 100), "Fictional source wording.")
            if label:
                page.insert_text((500, 1320 if not midpage else 500), label, fontsize=10)
            if duplicate:
                page.insert_text((700, 1320), label, fontsize=10)
            if rotated:
                page.set_rotation(90)
        return pdf.tobytes()


def fixture(tmp_path, *, labels=("Contact details. 1 / 3", "Contact details. 2 / 3", "3\u060d3"), source=None):
    pdf = source or source_pdf()
    pages = tmp_path / "pages"; pages.mkdir()
    for number, label in enumerate(labels, 1):
        (pages / f"page_{number:04d}.txt").write_text("Fictional body wording.\n" + label, encoding="utf-8")
    output = assemble_docx(pages, tmp_path / "raw.docx", lang=TargetLang.AR, page_breaks=True, page_numbers=[1, 2, 3])
    raw = output.read_bytes(); mapping = json.loads(output.with_suffix(".source_map.json").read_text(encoding="utf-8"))
    snapshot = bind_raw_page_map(raw, mapping, source_pdf_sha256=hashlib.sha256(pdf).hexdigest(), selected_pages=(1, 2, 3), target_lang="AR")
    frames = [{"page_number": n, "width_px": 1000, "height_px": 1400, "image_sha256": str(n)*64} for n in (1, 2, 3)]
    decisions = default_decisions(snapshot.saved_snapshot, frames)
    for choice, row in zip(decisions["paragraphs"], snapshot.paragraphs):
        if row.page_number is None:
            continue
        folio = "/" in row.text or "\u060d" in row.text
        choice.update(role="source_folio" if folio else "body", regions=[{"page_number": row.page_number,
            "bbox_px": [50, 1290, 950, 1350] if folio else [50, 100, 950, 500]}])
    proof = derive_proof(pdf, frames, (1, 2, 3), snapshot.source_pdf_sha256)
    evidence = {"version": "fictional_proposal_v1", "document_reviewed": False,
        "rendered_layout_acceptance": "not_evaluated", RECIPE_KEY: VERSION, KEY: proof}
    return raw, snapshot, frames, decisions, evidence, pdf, mapping


def build(values):
    raw, snapshot, frames, decisions, evidence, pdf, _ = values
    return build_unreviewed_candidate(raw, snapshot, frames, decisions, proposal_evidence=evidence, source_pdf_bytes=pdf)


def has_page(raw):
    with ZipFile(BytesIO(raw)) as z:
        return any(b" PAGE " in z.read(n) for n in z.namelist() if n.startswith("word/footer"))


def body_text(raw):
    return [p.text for p in Document(BytesIO(raw)).paragraphs]


def test_mixed_contacts_unicode_separator_and_terminal_breaks_preserve_every_character(tmp_path):
    values = fixture(tmp_path); before = deepcopy(values[3:5]); artifact = build(values)
    assert not has_page(artifact.docx_bytes)
    assert body_text(artifact.docx_bytes) == body_text(values[0])
    plan = artifact.source_map["ordinary_presentation_plan"]
    assert len(plan["local_source_folio_spans"]) == 3
    assert artifact.source_map["suppressed_generated_page_footer_parts"] == ["word/footer1.xml"]
    assert values[3:5] == before
    verify_unreviewed_candidate(*values[:4], artifact, proposal_evidence=values[4], source_pdf_bytes=values[5])


@pytest.mark.parametrize("case", ["missing", "duplicate", "midpage", "rotated", "invalid_pair", "leading_zero", "prose"])
def test_uncertain_source_never_supplies_complete_proof(tmp_path, case):
    options = {"duplicate": case == "duplicate", "midpage": case == "midpage", "rotated": case == "rotated"}
    labels = {"missing": ("1/3", "2/3", ""), "invalid_pair": ("1/3", "2/3", "4/3"),
        "leading_zero": ("01/3", "2/3", "3/3"), "prose": ("Reference 1/3", "2/3", "3/3")}.get(case, ("1/3", "2/3", "3/3"))
    values = fixture(tmp_path, source=source_pdf(labels, **options))
    assert has_page(build(values).docx_bytes)


@pytest.mark.parametrize("labels", [
    ("Contact. 2/3", "Contact. 2/3", "3\u060d3"),
    ("Contact. 1/4", "Contact. 2/3", "3\u060d3"),
    ("1/3 contact continues", "Contact. 2/3", "3\u060d3"),
    ("Contact. 1/3 and 1/3", "Contact. 2/3", "3\u060d3"),
    ("Contact. 01/3", "Contact. 2/3", "3\u060d3"),
])
def test_target_is_one_exact_matching_terminal_numeric_span(tmp_path, labels):
    values = fixture(tmp_path, labels=labels)
    assert has_page(build(values).docx_bytes)
    assert body_text(build(values).docx_bytes) == body_text(values[0])


@pytest.mark.parametrize("change", ["body_role", "wrong_center", "midpage", "panel", "missing_region", "partition", "control"])
def test_target_role_geometry_owner_and_control_guards(tmp_path, change):
    values = fixture(tmp_path); raw, snapshot, frames, decisions, evidence, _, _ = values
    context = {"selected_pages": [1, 2, 3], "page_groups": [[p, list(ids)] for p, ids in snapshot.page_groups], KEY: evidence[KEY]}
    snap = snapshot.saved_snapshot
    choice = next(c for c in decisions["paragraphs"] if c["role"] == "source_folio")
    identifier = choice["paragraph_id"]
    if change == "body_role": choice["role"] = "body"
    elif change == "wrong_center": choice["regions"][0]["bbox_px"] = [50, 1290, 100, 1350]
    elif change == "midpage": choice["regions"][0]["bbox_px"] = [50, 100, 950, 300]
    elif change == "missing_region": choice["regions"] = []
    elif change == "partition": decisions["paragraph_partitions"] = [{"paragraph_id": identifier, "offsets": [8]}]
    elif change == "control": next(r for r in snap["paragraphs"] if r["id"] == identifier)["tokens"].insert(0, {"kind": "tab"})
    else:
        for band in decisions["bands"]:
            for group in band.get("groups", []):
                if identifier in group["paragraph_ids"]: group["panel"] = True
    assert target_spans(snap, frames, decisions, context) == []


@pytest.mark.parametrize("change", ["source_hash", "image_hash", "pair", "box", "version", "page_bool", "missing_source", "missing_proof", "unknown_recipe"])
def test_rehashed_or_stale_proof_is_rejected_against_actual_source(tmp_path, change):
    values = list(fixture(tmp_path)); proof = values[4][KEY]
    if change == "source_hash": proof["source_pdf_sha256"] = "a" * 64
    elif change == "image_hash": proof["frames"][0]["image_sha256"] = "a" * 64
    elif change == "pair": proof["folios"][0]["fraction"]["numerator"] = 2
    elif change == "box": proof["folios"][0]["fraction"]["bbox"][0] = .1
    elif change == "version": proof["version"] = "future"
    elif change == "page_bool": proof["folios"][0]["page_number"] = True
    elif change == "missing_source": values[5] = None
    elif change == "missing_proof": del values[4][KEY]
    else: values[4][RECIPE_KEY] = "future"
    with pytest.raises(ValueError, match="source_folio_proof"):
        build(values)


@pytest.mark.parametrize("edge,delta,accepted", [
    ("right", 20, True), ("right", 20.01, False),
    ("left", 20, True), ("left", 20.01, False),
    ("top", .01, False), ("bottom", .01, False),
])
def test_source_center_has_versioned_horizontal_only_coarse_box_tolerance(tmp_path, edge, delta, accepted):
    values = fixture(tmp_path)
    raw, snapshot, frames, decisions, evidence, _, _ = values
    context = {"selected_pages":[1,2,3], "page_groups":[[p,list(ids)] for p,ids in snapshot.page_groups], KEY:evidence[KEY]}
    box = evidence[KEY]["folios"][0]["fraction"]["bbox"]
    cx,cy = (box[0]+box[2])*500, (box[1]+box[3])*700
    choice = next(c for c in decisions["paragraphs"] if c["role"] == "source_folio")
    bounds = choice["regions"][0]["bbox_px"]
    if edge == "right": bounds[2] = cx - delta
    elif edge == "left": bounds[0] = cx + delta
    elif edge == "top": bounds[1] = cy + delta
    else: bounds[3] = cy - delta
    assert bool(target_spans(snapshot.saved_snapshot,frames,decisions,context)) is accepted


def test_historical_evidence_keeps_old_behavior_and_new_policy_has_distinct_identity(tmp_path):
    from legalpdf_translate.ordinary_auto_layout import frozen_automatic_layout_policy, _optional_hint_policy, _source_normalization_version, _metadata_normalization_policies
    values = fixture(tmp_path); values[4].pop(KEY); values[4].pop(RECIPE_KEY)
    assert has_page(build(values).docx_bytes)
    old = _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3", emphasis_normalization=True, metadata_normalization=True, primary_folio_version="terminal_labeled_folio_v2")
    assert old != frozen_automatic_layout_policy()
    assert old in _metadata_normalization_policies()
    assert _source_normalization_version(old.split(":", 1)[1]) == "ordinary_optional_layout_hint_normalization_v3"


def service_folio_binding_case(tmp_path):
    from legalpdf_translate.saved_docx_layout_service import SavedDocxLayoutService
    values = fixture(tmp_path); raw, _, _, _, _, pdf, mapping = values
    service = SavedDocxLayoutService(tmp_path / "app", mode="shadow", workspace_id="fixture")
    imported = service.import_document(pdf, raw, "AR", uuid.uuid4().hex)
    review_id = imported["review_id"]; view = service.read(review_id)
    decisions = deepcopy(view["decisions"])
    owners = {row.id: row.page_number for row in values[1].paragraphs}
    for choice, row in zip(decisions["paragraphs"], view["paragraphs"]):
        folio = "/" in row["text"] or "\u060d" in row["text"]
        if folio:
            page = owners[choice["paragraph_id"]]
            frame = view["pages"][page-1]
            choice.update(role="source_folio", regions=[{"page_number":page,"bbox_px":[0,frame["height_px"]*.9,frame["width_px"],frame["height_px"]*.98]}])
    saved = service.save_decisions(review_id, view["generation"], uuid.uuid4().hex, decisions)
    evidence = {"version":"fictional_proposal_v1", "document_reviewed":False, RECIPE_KEY:VERSION}
    return service, review_id, saved, mapping, evidence


@pytest.mark.parametrize("policy_kind", ["saved_source_v4", "prior_source_v3", "prior_labeled_v2"])
def test_service_generates_proof_locally_and_replays_from_retained_source(tmp_path, policy_kind):
    from legalpdf_translate.ordinary_auto_layout import (
        _source_bound_v4_policy, _source_bound_v3_policy, _optional_hint_policy)
    service, review_id, saved, mapping, evidence = service_folio_binding_case(tmp_path)
    policy = (_source_bound_v4_policy() if policy_kind == "saved_source_v4" else
        _source_bound_v3_policy() if policy_kind == "prior_source_v3" else
        _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
            emphasis_normalization=True, metadata_normalization=True,
            primary_folio_version="terminal_labeled_folio_v2", source_folio_proof=True))
    fingerprint = policy.split(":",1)[1]
    service.attach_ordinary_binding(review_id, mapping, (1,2,3), fingerprint, evidence, expected_generation=saved["generation"])
    # Retained generation/evidence can be reattached without rewriting it.
    folder = service._folder(review_id)
    retained = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*.json")}
    service.attach_ordinary_binding(review_id, mapping, (1,2,3), fingerprint, evidence, expected_generation=saved["generation"])
    assert retained == {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*.json")}
    built = service.build_unreviewed_candidate(review_id, saved["generation"], uuid.uuid4().hex)
    verified = service.verified_unreviewed_candidate(review_id,built["candidate_id"])
    assert not has_page(verified.docx_bytes)
    assert KEY not in evidence
    with pytest.raises(ValueError, match="ordinary_source_folio_direction_changed"):
        service.attach_ordinary_binding(review_id, mapping, (1,2,3), fingerprint,
            {**evidence, "source_folio_direction_version": "numeric_run_ltr_v3"},
            expected_generation=saved["generation"])


def test_current_fresh_minimal_folio_evidence_requires_real_attempt_witness(tmp_path):
    from legalpdf_translate.ordinary_auto_layout import frozen_automatic_layout_policy
    service, review_id, saved, mapping, evidence = service_folio_binding_case(tmp_path)
    folder = service._folder(review_id)
    retained = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*.json")}
    with pytest.raises(ValueError, match="ordinary_layout_proposal_repair_evidence_missing$"):
        service.attach_ordinary_binding(review_id, mapping, (1,2,3),
            frozen_automatic_layout_policy().split(":",1)[1], evidence,
            expected_generation=saved["generation"])
    assert retained == {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob("*.json")}
