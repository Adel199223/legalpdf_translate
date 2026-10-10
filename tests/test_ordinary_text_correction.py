"""Synthetic local correction lineage; no provider or native calls."""
from dataclasses import replace
from io import BytesIO
from zipfile import ZipFile

from docx import Document
from lxml import etree
import pytest

from legalpdf_translate.ordinary_layout_contracts import OrdinaryLayoutError
from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
from legalpdf_translate.ordinary_text_correction import paragraphs, apply_actions, word_changes
from tests.test_ordinary_layout_service import make_case, nonce
from legalpdf_translate.ordinary_text_correction import W


def action(pid, text, kind="replace"):
    return {"kind": kind, "paragraph_id": pid, "text": text, "source_page": 1, "source_bbox": [.1, .1, .9, .2]}


@pytest.mark.parametrize("lang,text", [("EN", "Corrected fictional address R"), ("FR", "Adresse fictive corrigée R"), ("AR", "عنوان خيالي R 123")])
def test_approval_delivery_reload_and_immutable_original(tmp_path, monkeypatch, lang, text):
    case = make_case(tmp_path, monkeypatch, lang)
    service = case.manager.service
    state = service.text_correction_state(case.job)
    pid = state["paragraphs"][0]["paragraph_id"]
    draft = service.draft_text_correction(case.job, nonce(), state["parent"], [action(pid, text)])
    assert service.state(case.job.job_id)["delivery"] is None
    selected = service.approve_text_correction(case.job, draft["draft_id"], nonce(), True, True, "Compared with source")
    assert selected["delivery"]["text_approved"] and selected["delivery"]["output_review_required"]
    artifact = case.manager.resolve_delivery(case.job.job_id, 1)
    assert paragraphs(artifact.path.read_bytes())[0]["text"] == text
    assert artifact.word_count > 0 and artifact.kind == "text_corrected"
    reopened = OrdinaryLayoutManager(case.root, mode="shadow", workspace_id="fixture", job_resolver=lambda _: case.job)
    assert reopened.resolve_delivery(case.job.job_id, 1) == artifact
    assert case.job.original_docx == case.job.reviewed_docx
    assert service.text_correction_state(case.job)["paragraphs"][0]["paragraph_id"] == pid


def test_cancel_stale_approval_owner_and_freeze(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    service = case.manager.service
    state = service.text_correction_state(case.job)
    edits = [action(state["paragraphs"][0]["paragraph_id"], "Replacement")]
    a = service.draft_text_correction(case.job, nonce(), state["parent"], edits)
    b = service.draft_text_correction(case.job, nonce(), state["parent"], edits)
    service.cancel_text_correction(case.job, b["draft_id"])
    with pytest.raises(OrdinaryLayoutError, match="cancelled"):
        service.approve_text_correction(case.job, b["draft_id"], nonce(), True, True, "Compared")
    with pytest.raises(OrdinaryLayoutError, match="owner_changed"):
        service.text_correction_state(replace(case.job, run_id="wrong-run"))
    service.approve_text_correction(case.job, a["draft_id"], nonce(), True, True, "Compared")
    with pytest.raises(OrdinaryLayoutError, match="parent_stale"):
        service.draft_text_correction(case.job, nonce(), state["parent"], edits)
    selected = service.state(case.job.job_id)["delivery"]
    service.review_text_output(case.job, selected["selection_id"], 1, True)
    case.manager.resolve_delivery(case.job.job_id, 1, nonce())
    with pytest.raises(OrdinaryLayoutError, match="frozen"):
        service.draft_text_correction(case.job, nonce(), state["parent"], edits)


def test_insert_delete_preserve_stable_ids_and_package(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    service = case.manager.service
    state = service.text_correction_state(case.job)
    first, second = state["paragraphs"]
    draft = service.draft_text_correction(case.job, nonce(), state["parent"], [
        action(first["paragraph_id"], "Inserted source annotation", "insert_before")])
    service.approve_text_correction(case.job, draft["draft_id"], nonce(), True, True, "Source annotation")
    state = service.text_correction_state(case.job)
    assert [r["paragraph_id"] for r in state["paragraphs"]][1:] == [first["paragraph_id"], second["paragraph_id"]]
    draft = service.draft_text_correction(case.job, nonce(), state["parent"], [action(first["paragraph_id"], "", "delete")])
    service.approve_text_correction(case.job, draft["draft_id"], nonce(), True, True, "Duplicate removed")
    assert service.text_correction_state(case.job)["paragraphs"][-1]["paragraph_id"] == second["paragraph_id"]


def test_word_import_requires_safe_structure_and_keeps_unapproved_bytes(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    base = case.job.reviewed_docx
    doc = Document(BytesIO(base)); doc.paragraphs[0].text = "Edited fictional text"
    stream = BytesIO(); doc.save(stream); working = stream.getvalue()
    assert len(word_changes(base, working)) == 1
    doc.add_paragraph("Unowned insertion"); stream = BytesIO(); doc.save(stream)
    with pytest.raises(OrdinaryLayoutError, match="structure_unsupported|section_changed"):
        word_changes(base, stream.getvalue())


def test_missing_region_and_controls_refuse_before_publication(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    pid = paragraphs(case.job.reviewed_docx)[0]["paragraph_id"]
    bad = action(pid, "Missing source region", "insert_after"); bad["source_bbox"] = None
    with pytest.raises(OrdinaryLayoutError, match="region_required"):
        apply_actions(case.job.reviewed_docx, [bad], "EN", (1,))
    with pytest.raises(OrdinaryLayoutError, match="invalid_text"):
        apply_actions(case.job.reviewed_docx, [action(pid, "Bad\u202e control")], "EN", (1,))


def test_literal_brackets_and_repeated_insert_ids_are_exact(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch, "AR")
    raw = case.job.reviewed_docx
    pid = paragraphs(raw)[0]["paragraph_id"]
    output, _, mapping = apply_actions(raw, [action(pid, "النص [[ABC]]")], "AR", (1,))
    assert paragraphs(output)[0]["text"] == "النص [[ABC]]"
    inserted, _, mapping = apply_actions(output, [action(pid, "نص جديد", "insert_after")], "AR", (1,), paragraph_map=mapping)
    again, _, mapping = apply_actions(inserted, [action(pid, "نص جديد", "insert_after")], "AR", (1,), paragraph_map=mapping)
    assert len(paragraphs(again)) == len({r["paragraph_id"] for r in mapping}) == 4


def test_word_section_and_noneditable_story_change_refuse(tmp_path, monkeypatch):
    from lxml import etree
    case = make_case(tmp_path, monkeypatch)
    doc = Document(BytesIO(case.job.reviewed_docx)); doc.paragraphs[0].text = "Approved wording candidate"
    props = doc.paragraphs[1]._p.get_or_add_pPr(); etree.SubElement(props, W + "sectPr")
    stream = BytesIO(); doc.save(stream)
    with pytest.raises(OrdinaryLayoutError, match="section_changed"):
        word_changes(case.job.reviewed_docx, stream.getvalue())
    def note(raw, text):
        output = BytesIO()
        with ZipFile(BytesIO(raw)) as source, ZipFile(output, "w") as target:
            for info in source.infolist():
                target.writestr(info, source.read(info))
            target.writestr("word/footnotes.xml", f'<w:footnotes xmlns:w="{W[1:-1]}"><w:footnote w:id="1"><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:footnote></w:footnotes>')
        return output.getvalue()
    original = note(case.job.reviewed_docx, "Original note")
    doc = Document(BytesIO(case.job.reviewed_docx)); doc.paragraphs[0].text = "Changed body"
    stream = BytesIO(); doc.save(stream)
    with pytest.raises(OrdinaryLayoutError, match="story_unsupported"):
        word_changes(original, note(stream.getvalue(), "Hidden note change"))


@pytest.mark.parametrize("what", ["docx", "map"])
def test_selected_copy_and_rehashed_map_tampering_refuse(tmp_path, monkeypatch, what):
    from legalpdf_translate.ordinary_layout_service import _read, _write
    case = make_case(tmp_path, monkeypatch)
    service = case.manager.service
    state = service.text_correction_state(case.job)
    draft = service.draft_text_correction(case.job, nonce(), state["parent"], [action(state["paragraphs"][0]["paragraph_id"], "Corrected")])
    selected = service.approve_text_correction(case.job, draft["draft_id"], nonce(), True, True, "")
    delivery = service.resolve_delivery(case.job.job_id, 1)
    if what == "docx":
        delivery.path.write_bytes(case.job.original_docx)
    else:
        path = delivery.path.parent / "source_map.json"
        value = _read(path); value["source_character_coverage"] = "invented_complete"
        from legalpdf_translate.ordinary_layout_contracts import digest, encode
        path.write_bytes(encode({"payload": value, "sha256": digest(encode(value))}))
    with pytest.raises(OrdinaryLayoutError, match="changed"):
        service.resolve_delivery(case.job.job_id, 1)


def test_repeated_formatting_uses_one_working_root_and_imports_later_text(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    service = case.manager.service
    state = service.text_correction_state(case.job)
    draft = service.draft_text_correction(case.job, nonce(), state["parent"], [action(state["paragraphs"][0]["paragraph_id"], "Corrected fictional wording")])
    service.approve_text_correction(case.job, draft["draft_id"], nonce(), True, True, "")
    working = service.text_corrected_review_copy(case.job.job_id)
    for bold in [True, False]:
        doc = Document(working); doc.paragraphs[0].runs[0].bold = bold; doc.save(working)
        service.adopt_text_corrected_word_edit(case.job.job_id)
        assert service.text_corrected_review_copy(case.job.job_id) == working
    doc = Document(working); doc.paragraphs[0].text = "Explicit later text edit"; doc.save(working)
    with pytest.raises(OrdinaryLayoutError):
        service.adopt_text_corrected_word_edit(case.job.job_id)
    state = service.text_correction_state(case.job)
    imported = service.draft_text_correction(case.job, nonce(), state["parent"], [], import_word=True)
    assert imported["changes"][0]["after"] == "Explicit later text edit"
    assert working.exists()


def test_source_finding_requires_explicit_review_and_is_revision_bound(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch); service = case.manager.service
    original_state = service.state
    finding = {"finding_id": "a"*64, "kind": "missing_readable_literal", "literal": "R", "page_number": 1, "source_bbox": [.1,.1,.2,.2], "insertion_context": {"paragraph_id": "p1", "position": "before"}}
    def state(job_id):
        value = original_state(job_id); value["suggestions"] = [{"source_coverage_findings": [finding]}]; return value
    monkeypatch.setattr(service, "state", state)
    view = service.text_correction_state(case.job)
    assert view["source_findings"][0]["review_status"] == "unresolved"
    with pytest.raises(OrdinaryLayoutError):
        service.review_source_finding(case.job, finding["finding_id"], view["parent"], "corrected", True)
    reviewed = service.review_source_finding(case.job, finding["finding_id"], view["parent"], "reviewed_no_change", True)
    # There is no automatic selected artifact in this fixture; a new selected correction must still reset review.
    draft = service.draft_text_correction(case.job, nonce(), view["parent"], [action(view["paragraphs"][0]["paragraph_id"], "Corrected")])
    service.approve_text_correction(case.job, draft["draft_id"], nonce(), True, True, "")
    current = service.text_correction_state(case.job)
    assert current["source_findings"][0]["review_status"] == "unresolved"
    current = service.review_source_finding(case.job, finding["finding_id"], current["parent"], "corrected", True)
    assert current["source_findings"][0]["review_status"] == "corrected"


def test_correction_counts_meaningful_header_footer_text_once():
    from legalpdf_translate.ordinary_text_correction import count_correction_words
    doc = Document(); doc.add_paragraph("Body two")
    doc.sections[0].header.paragraphs[0].text = "Header three words"
    doc.sections[0].footer.paragraphs[0].text = "Source footer four words"
    stream = BytesIO(); doc.save(stream)
    assert count_correction_words(stream.getvalue()) == 9


def test_semantic_word_sections_allow_benign_metadata_but_reject_footer_repoint(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    doc = Document(BytesIO(case.job.reviewed_docx)); doc.sections[0].footer.paragraphs[0].text = "Owned footer"
    stream = BytesIO(); doc.save(stream); original = stream.getvalue()
    def edit(repoint=False):
        output = BytesIO()
        with ZipFile(BytesIO(original)) as source, ZipFile(output, "w") as target:
            for info in source.infolist():
                raw = source.read(info)
                if info.filename == "word/document.xml":
                    root = etree.fromstring(raw); next(root.iter(W+"t")).text = "Changed text"
                    section = next(root.iter(W+"sectPr")); section.set(W+"rsidR", "12345678")
                    reference = next(section.iter(W+"footerReference")); reference.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "rIdChanged")
                    raw = etree.tostring(root)
                elif info.filename == "word/_rels/document.xml.rels":
                    root = etree.fromstring(raw)
                    for rel in root:
                        if rel.get("Type").endswith("/footer"):
                            rel.set("Id", "rIdChanged")
                            if repoint: rel.set("Target", "footer999.xml")
                    raw = etree.tostring(root)
                target.writestr(info,raw)
        return output.getvalue()
    assert len(word_changes(original,edit())) == 1
    with pytest.raises(OrdinaryLayoutError,match="section_changed"):
        word_changes(original,edit(True))


def test_natural_arabic_in_latin_target_gets_native_direction_and_literal_brackets(tmp_path, monkeypatch):
    case=make_case(tmp_path,monkeypatch)
    raw=case.job.reviewed_docx
    value="نص [[ABC]]"
    edited,changes,mapping=apply_actions(raw,[action(paragraphs(raw)[0]["paragraph_id"],value)],"EN",(1,))
    with ZipFile(BytesIO(edited)) as archive:root=etree.fromstring(archive.read("word/document.xml"))
    first=next(root.iter(W+"p"))
    assert first.find(W+"pPr/"+W+"bidi").get(W+"val")=="1"
    assert "".join(n.text or "" for n in first.iter(W+"t"))==value
    replaced,_,_=apply_actions(edited,[action(mapping[0]["paragraph_id"],"Latin text")],"EN",(1,),paragraph_map=mapping)
    with ZipFile(BytesIO(replaced)) as archive:root=etree.fromstring(archive.read("word/document.xml"))
    assert next(root.iter(W+"p")).find(W+"pPr/"+W+"bidi").get(W+"val")=="0"
