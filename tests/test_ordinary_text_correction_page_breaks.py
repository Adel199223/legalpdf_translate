"""Fictional pagination controls and local correction lineage; no native calls."""
from copy import deepcopy
import hashlib
from io import BytesIO
from zipfile import ZipFile

from docx import Document
from docx.enum.text import WD_BREAK
from lxml import etree
import pytest

from legalpdf_translate.ordinary_layout_contracts import OrdinaryLayoutError
from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
from legalpdf_translate.ordinary_text_correction import (
    W, apply_actions, count_correction_words, package, paragraphs, word_changes,
)
from tests.test_ordinary_layout_service import make_case, nonce
from tests.test_ordinary_text_correction import action


def fictional_docx(shared=False, language="EN"):
    doc = Document()
    paragraph = doc.add_paragraph("Fictional measurement clause.")
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.alignment = 2
    if language == "AR":
        etree.SubElement(paragraph._p.get_or_add_pPr(), W + "bidi").set(W + "val", "1")
    run = paragraph.runs[-1] if shared else paragraph.add_run()
    run.bold = True
    run.add_break(WD_BREAK.PAGE)
    doc.add_paragraph("Fictional next page.")
    footer = doc.sections[0].footer.paragraphs[0]._p
    for tag, attrs, text in [
        ("fldChar", {W + "fldCharType": "begin"}, None),
        ("instrText", {}, " PAGE "),
        ("fldChar", {W + "fldCharType": "separate"}, None),
        ("t", {}, "77"),
        ("fldChar", {W + "fldCharType": "end"}, None),
    ]:
        etree.SubElement(etree.SubElement(footer, W + "r"), W + tag, attrs).text = text
    out = BytesIO(); doc.save(out)
    return out.getvalue()


def first_paragraph(raw):
    return next(package(raw)[2]["word/document.xml"].iter(W + "p"))


def edit_document(raw, mutate):
    out = BytesIO()
    with ZipFile(BytesIO(raw)) as source, ZipFile(out, "w") as target:
        for info in source.infolist():
            value = source.read(info)
            if info.filename == "word/document.xml":
                root = etree.fromstring(value)
                mutate(next(root.iter(W + "p")))
                value = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
            target.writestr(info, value)
    return out.getvalue()


@pytest.mark.parametrize("shared", [False, True])
@pytest.mark.parametrize("language,text", [("EN", "Corrected fictional measurement wording."), ("AR", "صياغة خيالية مصححة للقياس.")])
def test_replace_preserves_exact_suffix_break_style_and_paragraph_properties(shared, language, text):
    raw = fictional_docx(shared, language)
    before = first_paragraph(raw)
    control = next(before.iter(W + "br"))
    control_bytes = etree.tostring(control, method="c14n")
    control_style = etree.tostring(control.getparent().find(W + "rPr"), method="c14n")
    props = etree.tostring(before.find(W + "pPr"), method="c14n")
    row = paragraphs(raw)[0]
    assert row["editable"]
    edited, changes, mapping = apply_actions(raw, [action(row["paragraph_id"], text)], language, (1,))
    after = first_paragraph(edited)
    preserved = list(after.iter(W + "br"))
    assert len(preserved) == 1
    assert etree.tostring(preserved[0], method="c14n") == control_bytes
    assert etree.tostring(preserved[0].getparent().find(W + "rPr"), method="c14n") == control_style
    assert etree.tostring(after.find(W + "pPr"), method="c14n") == props
    assert list(after.iter())[-1] is preserved[0]
    assert paragraphs(edited)[0]["text"] == text
    assert paragraphs(edited)[1]["text"] == paragraphs(raw)[1]["text"]
    assert mapping[0]["paragraph_id"] == row["paragraph_id"]
    assert changes[0]["after"] == text
    assert count_correction_words(edited) == len(text.split()) + 3


@pytest.mark.parametrize("kind", ["delete", "insert_before", "insert_after"])
def test_control_anchor_refuses_insert_and_delete(kind):
    raw = fictional_docx()
    row = paragraphs(raw)[0]
    with pytest.raises(OrdinaryLayoutError, match="correction_paragraph_controls"):
        apply_actions(raw, [action(row["paragraph_id"], "" if kind == "delete" else "New text", kind)], "EN", (1,))


@pytest.mark.parametrize("language,text,original_language,direction", [
    ("AR", "صياغة خيالية مصححة.", "EN", "1"),
    ("EN", "صياغة خيالية مصححة.", "EN", "1"),
    ("EN", "Corrected fictional wording.", "AR", "0"),
])
def test_break_replacement_updates_direction_like_plain_text(language, text, original_language, direction):
    raw = fictional_docx(language=original_language)
    row = paragraphs(raw)[0]
    edited, _, _ = apply_actions(raw, [action(row["paragraph_id"], text)], language, (1,))
    after = first_paragraph(edited)
    assert after.find(W + "pPr/" + W + "bidi").get(W + "val") == direction
    assert after.find(W + "pPr/" + W + "keepNext") is not None
    assert after.find(W + "pPr/" + W + "jc").get(W + "val") == "right"
    assert len(list(after.iter(W + "br"))) == 1


@pytest.mark.parametrize("control", ["prefix", "interior", "tab", "field", "section", "wrapper", "only", "duplicate", "line", "attribute"])
def test_unsupported_control_profiles_remain_uneditable(control):
    def mutate(p):
        br = next(p.iter(W + "br"))
        if control == "prefix":
            br.getparent().remove(br); p.findall(W + "r")[0].insert(0, br)
        elif control == "interior":
            etree.SubElement(p[-1], W + "t").text = "Text after break"
        elif control == "tab":
            etree.SubElement(p[1], W + "tab")
        elif control == "field":
            etree.SubElement(p[1], W + "fldChar", {W + "fldCharType": "begin"})
        elif control == "section":
            etree.SubElement(p.find(W + "pPr"), W + "sectPr")
        elif control == "wrapper":
            run = p.findall(W + "r")[0]; p.remove(run)
            etree.SubElement(p, W + "dir", {W + "val": "ltr"}).append(run)
        elif control == "only":
            for t in list(p.iter(W + "t")):
                t.getparent().remove(t)
        elif control == "duplicate":
            br.addnext(deepcopy(br))
        elif control == "line":
            br.set(W + "type", "textWrapping")
        elif control == "attribute":
            br.set(W + "clear", "all")
    raw = edit_document(fictional_docx(), mutate)
    row = paragraphs(raw)[0]
    assert not row["editable"]
    with pytest.raises(OrdinaryLayoutError, match="correction_paragraph_controls"):
        apply_actions(raw, [action(row["paragraph_id"], "Replacement")], "EN", (1,))


@pytest.mark.parametrize("shared", [False, True])
def test_word_import_allows_wording_with_unchanged_trailing_control(shared):
    base = fictional_docx(shared)
    edited = edit_document(base, lambda p: setattr(next(p.iter(W + "t")), "text", "Corrected Word measurement."))
    changes = word_changes(base, edited)
    assert len(changes) == 1
    assert changes[0]["before"] == "Fictional measurement clause."
    assert changes[0]["after"] == "Corrected Word measurement."
    # Normal Word formatting/run splitting may move the suffix into its own run.
    doc = Document(BytesIO(edited))
    run = doc.paragraphs[0].runs[0]
    run.bold = False
    out = BytesIO(); doc.save(out)
    assert word_changes(base, out.getvalue()) == changes


@pytest.mark.parametrize("mutation", ["remove", "duplicate", "type", "attrs", "prefix", "interior", "other_paragraph"])
@pytest.mark.parametrize("change_wording", [False, True])
def test_word_import_rejects_control_changes_and_movement(mutation, change_wording):
    base = fictional_docx(True)
    def mutate(p):
        br = next(p.iter(W + "br")); run = br.getparent()
        if change_wording:
            next(p.iter(W + "t")).text = "Changed fictional wording"
        if mutation == "remove":
            run.remove(br)
        elif mutation == "duplicate":
            br.addnext(deepcopy(br))
        elif mutation == "type":
            br.set(W + "type", "column")
        elif mutation == "attrs":
            br.set(W + "clear", "all")
        elif mutation == "prefix":
            run.remove(br); run.insert(0, br)
        elif mutation == "interior":
            t = next(p.iter(W + "t")); original = t.text
            t.text = original[:8]; etree.SubElement(run, W + "t").text = original[8:]
        elif mutation == "other_paragraph":
            run.remove(br); etree.SubElement(p.getnext(), W + "r").append(br)
    with pytest.raises(OrdinaryLayoutError, match="correction_word_structure_unsupported|correction_paragraph_controls"):
        word_changes(base, edit_document(base, mutate))


def test_word_import_rejects_added_break():
    base = fictional_docx()
    def mutate(p):
        next(p.iter(W + "t")).text = "Changed text"
        etree.SubElement(p.getnext()[-1], W + "br", {W + "type": "page"})
    with pytest.raises(OrdinaryLayoutError, match="correction_word_structure_unsupported"):
        word_changes(base, edit_document(base, mutate))


@pytest.mark.parametrize("kind,text,expected", [
    ("replace", "Historical corrected court wording.", "3a6fec885a33ce2b03a98917a096d8e28b26585a3b03602447a2dc41c96c7697"),
    ("insert_before", "Historical inserted wording.", "f345509adf806a68d5ee90cc7d7d9be925aab7069c93ed29f259a9feaa2c8d3a"),
    ("delete", "", "e008a3c2cc3d165a4b67963022e18bb61347d6a604ab82dd454ddccdcc9aa816"),
])
def test_historical_plain_corrections_replay_exact_package_bytes(kind, text, expected):
    # Hashes produced with the pinned dependencies and the approved baseline
    # 9250d61 correction code, before this control-preservation repair.
    doc = Document()
    doc.add_paragraph("Historical fictional court.")
    doc.add_paragraph("Stable second paragraph.")
    stream = BytesIO(); doc.save(stream)
    out = BytesIO()
    with ZipFile(BytesIO(stream.getvalue())) as source, ZipFile(out, "w") as target:
        for info in source.infolist():
            info.date_time = (2026, 1, 1, 0, 0, 0)
            target.writestr(info, source.read(info.filename))
    raw = out.getvalue()
    edited, _, _ = apply_actions(raw, [action(paragraphs(raw)[0]["paragraph_id"], text, kind)], "EN", (1,))
    assert hashlib.sha256(edited).hexdigest() == expected


@pytest.mark.parametrize("import_word", [False, True])
def test_approval_reload_counts_and_atomic_rejection_preserve_selected_output(tmp_path, monkeypatch, import_word):
    raw = fictional_docx(True)
    monkeypatch.setattr("tests.test_ordinary_layout_service.docx_bytes", lambda *args, **kwargs: raw)
    case = make_case(tmp_path, monkeypatch)
    service = case.manager.service
    state = service.text_correction_state(case.job)
    row = state["paragraphs"][0]
    assert row["editable"]
    draft = service.draft_text_correction(case.job, nonce(), state["parent"], [action(row["paragraph_id"], "Approved fictional measurement clause.")])
    service.approve_text_correction(case.job, draft["draft_id"], nonce(), True, True, "Source compared")
    artifact = service.resolve_delivery(case.job.job_id, 1)
    before = artifact.path.read_bytes()
    assert artifact.word_count == 7  # Four body words plus three next-page words; PAGE excluded.
    reopened = OrdinaryLayoutManager(case.root, mode="shadow", workspace_id="fixture", job_resolver=lambda _: case.job)
    assert reopened.resolve_delivery(case.job.job_id, 1) == artifact
    state = service.text_correction_state(case.job)
    if import_word:
        working = service.text_corrected_review_copy(case.job.job_id)
        working.write_bytes(edit_document(working.read_bytes(), lambda p: setattr(next(p.iter(W + "t")), "text", "Imported fictional measurement clause with correction.")))
        imported = service.draft_text_correction(case.job, nonce(), state["parent"], [], import_word=True)
        service.approve_text_correction(case.job, imported["draft_id"], nonce(), True, True, "Word wording compared")
        assert artifact.path.read_bytes() == before
        artifact = service.resolve_delivery(case.job.job_id, 2)
        before = artifact.path.read_bytes()
        assert artifact.word_count == 9
        assert reopened.resolve_delivery(case.job.job_id, 2) == artifact
        assert service.state(case.job.job_id)["delivery"]["output_review_required"]
        state = service.text_correction_state(case.job)
        working = service.text_corrected_review_copy(case.job.job_id)
        def mutate(p):
            br = next(p.iter(W + "br")); br.getparent().remove(br)
            p.findall(W + "r")[0].insert(0, br)
            next(p.iter(W + "t")).text = "Unsafe imported wording"
        working.write_bytes(edit_document(working.read_bytes(), mutate))
        actions = []
    else:
        # First action is valid but a later unsupported anchor edit rejects all.
        actions = [action(state["paragraphs"][1]["paragraph_id"], "Discarded valid change"), action(row["paragraph_id"], "", "delete")]
    with pytest.raises(OrdinaryLayoutError, match="correction_paragraph_controls"):
        service.draft_text_correction(case.job, nonce(), state["parent"], actions, import_word=import_word)
    assert artifact.path.read_bytes() == before
    assert service.resolve_delivery(case.job.job_id, 2 if import_word else 1) == artifact
    assert len(service.text_correction_state(case.job)["drafts"]) == (2 if import_word else 1)
    assert case.job.original_docx == raw
