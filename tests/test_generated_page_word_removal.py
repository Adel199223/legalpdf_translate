"""Explicit generated furniture removal; fictional packages, no Word/API calls."""
from io import BytesIO
from zipfile import ZipFile

from docx import Document
from lxml import etree
import pytest

from legalpdf_translate.docx_writer import _add_page_number_footer, _configure_styles
from legalpdf_translate.ordinary_generated_page_removal import certified_removal, removal_paragraph_map, W, R
from legalpdf_translate.ordinary_layout_contracts import OrdinaryLayoutError, digest, encode
from legalpdf_translate.ordinary_text_correction import paragraphs
from legalpdf_translate.ordinary_text_correction_service import _qualify_corrected_formatting
from legalpdf_translate.ordinary_source_layout import _pack


def fixture(language="AR"):
    doc = Document()
    doc.add_paragraph("Fictional institution")
    doc.add_paragraph("Preserve source contact 1/3 and every approved word.")
    _configure_styles(doc, language)
    _add_page_number_footer(doc, language)
    stream = BytesIO(); doc.save(stream)
    return stream.getvalue()


def members(raw):
    with ZipFile(BytesIO(raw)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def word_deleted(raw, *, expanded=True):
    """Model actual Word's blank story slots, not just a hand-edited XML field."""
    parts = members(raw)
    footer = etree.fromstring(parts["word/footer1.xml"])
    for child in list(footer[0]):
        if child.tag != W + "pPr": footer[0].remove(child)
    parts["word/footer1.xml"] = etree.tostring(footer)
    if expanded:
        document = etree.fromstring(parts["word/document.xml"])
        rels = etree.fromstring(parts["word/_rels/document.xml.rels"])
        types = etree.fromstring(parts["[Content_Types].xml"])
        section = next(document.iter(W + "sectPr"))
        for ref in list(section.findall(W + "footerReference")) + list(section.findall(W + "headerReference")):
            section.remove(ref)
        for kind in ("header", "footer"):
            for number, slot in enumerate(("even", "default", "first"), 1):
                name = f"word/{kind}{number}.xml"
                root = etree.Element(W + ("hdr" if kind == "header" else "ftr"), nsmap={"w": W[1:-1]})
                ppr = etree.SubElement(etree.SubElement(root, W + "p"), W + "pPr")
                etree.SubElement(ppr, W + "pStyle").set(W + "val", "Header" if kind == "header" else "Footer")
                parts[name] = etree.tostring(root)
                rid = f"rIdBlank{kind}{number}"
                etree.SubElement(rels, "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship",
                    Id=rid, Type=R[1:-1] + "/" + kind, Target=name[5:])
                ref = etree.SubElement(section, W + kind + "Reference")
                ref.set(W + "type", slot); ref.set(R + "id", rid)
                if name not in {row.get("PartName", "").lstrip("/") for row in types}:
                    etree.SubElement(types, "{http://schemas.openxmlformats.org/package/2006/content-types}Override",
                        PartName="/" + name, ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml." + kind + "+xml")
        # Remove the old no-longer-used relationship, retaining the real Word
        # logical move from old footer1 default to new footer2 default.
        for rel in list(rels):
            if rel.get("Target") == "footer1.xml" and rel.get("Id") == "rId9": rels.remove(rel)
        parts["word/document.xml"] = etree.tostring(document)
        parts["word/_rels/document.xml.rels"] = etree.tostring(rels)
        parts["[Content_Types].xml"] = etree.tostring(types)
    return _pack(parts)


def qualified(origin, base, edited):
    normalized_base, normalized_edited, certificate = certified_removal(origin, base, edited, "AR")
    _qualify_corrected_formatting(normalized_base, normalized_edited)
    return normalized_base, normalized_edited, certificate


@pytest.mark.parametrize("expanded", [False, True])
def test_only_certified_generated_page_disappears_and_source_ids_survive(expanded):
    origin = fixture()
    doc = Document(BytesIO(origin)); doc.paragraphs[0].text = "Ten approved fictional corrections retained"
    stream = BytesIO(); doc.save(stream); base = stream.getvalue()
    edited = word_deleted(base, expanded=expanded)
    # The generic adoption contract continues to protect fields.
    with pytest.raises(OrdinaryLayoutError): _qualify_corrected_formatting(base, edited)
    normalized_base, normalized_edited, certificate = qualified(origin, base, edited)
    original_map = paragraphs(base)
    mapping = removal_paragraph_map(base, edited, original_map, normalized_base, normalized_edited, certificate)
    before_body = [row for row in original_map if row["part_uri"] == "word/document.xml"]
    after_body = [row for row in mapping if row["part_uri"] == "word/document.xml"]
    assert [row["paragraph_id"] for row in after_body] == [row["paragraph_id"] for row in before_body]
    assert [p["text"] for p in paragraphs(base) if p["part_uri"] == "word/document.xml"] == [
        p["text"] for p in paragraphs(edited) if p["part_uri"] == "word/document.xml"]
    assert certificate["origin_sha256"] == digest(origin)
    assert certificate["removed_parent_parts"] == ["word/footer1.xml"]
    assert len(certificate["ignored_empty_edited_parts"]) == (6 if expanded else 1)


@pytest.mark.parametrize("mutation", ["body", "custom_origin", "unproven_origin", "replacement_field", "header_text",
    "header_control", "header_object", "section", "section_flag", "body_control", "orphan_header", "source_story",
    "nonpage_field", "source_footer_loss"])
def test_other_text_controls_stories_and_unproven_furniture_still_refuse(mutation):
    origin = fixture(); base = origin; edited = word_deleted(base)
    target = members(edited)
    if mutation in {"body", "body_control", "section", "section_flag"}:
        root = etree.fromstring(target["word/document.xml"])
        if mutation == "body": next(root.iter(W + "t")).text = "Unapproved source alteration"
        elif mutation == "body_control": etree.SubElement(next(root.iter(W + "r")), W + "br").set(W + "type", "page")
        elif mutation == "section_flag": etree.SubElement(next(root.iter(W + "sectPr")), W + "titlePg")
        else: next(root.iter(W + "pgMar")).set(W + "top", "999")
        target["word/document.xml"] = etree.tostring(root)
    elif mutation in {"header_text", "header_control", "header_object", "orphan_header"}:
        root = etree.fromstring(target["word/header1.xml"])
        run = etree.SubElement(root[0], W + "r")
        if mutation == "header_control": etree.SubElement(run, W + "fldChar").set(W + "fldCharType", "begin")
        elif mutation == "header_object": etree.SubElement(run, W + "drawing")
        elif mutation == "header_text": etree.SubElement(run, W + "t").text = "Unapproved header"
        if mutation == "orphan_header": target["word/header9.xml"] = etree.tostring(root)
        else: target["word/header1.xml"] = etree.tostring(root)
    elif mutation == "replacement_field": target["word/footer2.xml"] = members(base)["word/footer1.xml"]
    elif mutation == "nonpage_field":
        root = etree.fromstring(members(base)["word/footer1.xml"])
        next(root.iter(W + "instrText")).text = " NUMPAGES "
        target["word/footer2.xml"] = etree.tostring(root)
    elif mutation == "custom_origin":
        altered = members(origin); root = etree.fromstring(altered["word/footer1.xml"])
        etree.SubElement(etree.SubElement(root[0], W + "r"), W + "t").text = "Source footer must remain"
        altered["word/footer1.xml"] = etree.tostring(root); origin = base = _pack(altered)
    elif mutation == "source_story":
        doc = Document(BytesIO(origin)); doc.sections[0].header.paragraphs[0].text = "Source header must remain"
        stream = BytesIO(); doc.save(stream); origin = base = stream.getvalue(); target = members(word_deleted(base))
    elif mutation == "source_footer_loss":
        doc = Document(BytesIO(origin)); doc.sections[0].different_first_page_header_footer = True
        doc.sections[0].first_page_footer.paragraphs[0].text = "Source footer must remain"
        stream = BytesIO(); doc.save(stream); origin = base = stream.getvalue(); target = members(word_deleted(base))
    else:
        altered = members(origin); root = etree.fromstring(altered["word/footer1.xml"])
        for child in list(root[0]):
            if child.tag != W + "pPr": root[0].remove(child)
        altered["word/footer1.xml"] = etree.tostring(root); origin = _pack(altered)
    with pytest.raises(OrdinaryLayoutError): qualified(origin, base, _pack(target))


@pytest.mark.parametrize("refusal", [None, "text", "missing_origin", "changed_origin"])
def test_corrected_adoption_retains_prior_generation_and_revalidates_certificate(tmp_path, monkeypatch, refusal):
    from tests import test_ordinary_layout_service as cases
    from tests.test_ordinary_text_correction import action
    from legalpdf_translate.ordinary_layout_service import _read
    from legalpdf_translate.ordinary_text_correction_service import TextCorrectionMixin
    origin = fixture()
    monkeypatch.setattr(cases, "docx_bytes", lambda *args, **kwargs: origin)
    case = cases.make_case(tmp_path, monkeypatch, "AR")
    service = case.manager.service
    state = service.text_correction_state(case.job)
    draft = service.draft_text_correction(case.job, cases.nonce(), state["parent"], [
        action(state["paragraphs"][0]["paragraph_id"], "Approved fictional correction")])
    service.approve_text_correction(case.job, draft["draft_id"], cases.nonce(), True, True, "Source checked")
    original_delivery = service.resolve_delivery(case.job.job_id, 1)
    before = original_delivery.path.read_bytes()
    # Fixture replaces only the trusted automatic-candidate retrieval boundary;
    # pure tests above exercise provenance/signature and all delta guards.
    if refusal != "missing_origin":
        trusted = word_deleted(origin, expanded=False) if refusal == "changed_origin" else origin
        monkeypatch.setattr(TextCorrectionMixin, "_generated_page_origin", lambda self, folder: (trusted, "AR"))
    working = service.text_corrected_review_copy(case.job.job_id)
    working.write_bytes(word_deleted(before))
    if refusal == "text":
        doc = Document(working); doc.paragraphs[0].text = "Unapproved hidden wording change"; doc.save(working)
    parent = service.text_correction_state(case.job)["parent"]
    if refusal is not None:
        folder = service.folder(case.job.job_id)
        protected = {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()
            and path != working and path.suffix != ".lock"}
        with pytest.raises(OrdinaryLayoutError): service.check_text_correction_word(case.job, parent)
        assert service.state(case.job.job_id)["delivery_generation"] == 1
        assert original_delivery.path.read_bytes() == before
        assert protected == {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()
            and path != working and path.suffix != ".lock"}
        return
    service.check_text_correction_word(case.job, parent)
    adopted = service.state(case.job.job_id)
    assert adopted["delivery_generation"] == 2 and adopted["delivery"]["output_review_required"]
    assert original_delivery.path.read_bytes() == before
    selected = service.resolve_delivery(case.job.job_id, 2)
    assert "Approved fictional correction" in [row["text"] for row in paragraphs(selected.path.read_bytes())]
    assert service.adopt_text_corrected_word_edit(case.job.job_id)["delivery_generation"] == 2
    from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
    reopened = OrdinaryLayoutManager(case.root, mode="shadow", workspace_id="fixture", job_resolver=lambda _: case.job)
    assert reopened.resolve_delivery(case.job.job_id, 2).sha256 == selected.sha256
    doc = Document(working); doc.paragraphs[0].runs[0].bold = True; doc.save(working)
    service.check_text_correction_word(case.job, service.text_correction_state(case.job)["parent"])
    assert service.state(case.job.job_id)["delivery_generation"] == 3
    path = service.folder(case.job.job_id) / "text_corrections" / (adopted["delivery"]["artifact_id"] + ".json")
    record = _read(path)
    assert record["generated_page_removal"]["origin_sha256"] == digest(origin)
    record["generated_page_removal"]["origin_sha256"] = "f" * 64
    path.write_bytes(encode({"payload": record, "sha256": digest(encode(record))}))
    with pytest.raises(OrdinaryLayoutError, match="revision_changed"):
        service._verify_correction(service.folder(case.job.job_id), adopted["delivery"]["artifact_id"])
