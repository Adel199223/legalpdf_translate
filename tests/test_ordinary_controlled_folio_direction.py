"""Preserve numeric order without changing text or replaying old layout policy."""
from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate.ordinary_source_layout import _folio_ltr_span
from tests import test_ordinary_source_layout as fixture

W = model.W
LRM = "\u200e"


def paragraph(text):
    node = etree.Element(W + "p", nsmap={"w": W[1:-1]})
    for part in text.split("|"):
        run = etree.SubElement(node, W + "r")
        props = etree.SubElement(run, W + "rPr")
        etree.SubElement(props, W + "sz").set(W + "val", "22")
        etree.SubElement(props, W + "rtl").set(W + "val", "1")
        etree.SubElement(run, W + "t").text = part
    return node


@pytest.mark.parametrize("separator", ["/", "／"])
def test_numeric_marks_and_separator_share_ltr_without_changing_any_character(separator):
    text = f"الصفحة |{LRM}12{LRM}| {separator} |{LRM}37{LRM}"
    original = paragraph(text)
    before = etree.tostring(original)
    assert _folio_ltr_span(original) is None
    assert etree.tostring(original) == before
    span = _folio_ltr_span(original, controlled_numeric=True)
    assert span["literal"] == f"{LRM}12{LRM} {separator} {LRM}37{LRM}"
    assert "".join(n.text or "" for n in original.iter(W + "t")) == text.replace("|", "")
    runs = original.findall(W + "r")
    assert runs[0].find(W + "rPr/" + W + "rtl").get(W + "val") == "1"
    assert all(r.find(W + "rPr/" + W + "rtl").get(W + "val") == "0" for r in runs[1:])
    assert all(r.find(W + "rPr/" + W + "sz").get(W + "val") == "22" for r in runs)


@pytest.mark.parametrize("text", [
    "الصفحة \u202e1 / 2", "الصفحة \u20661\u2069 / 2",
    "الصفحة \u200f1 / 2", "الصفحة 1\u200e2 / 3",
    "الصفحة 1 / 2 يشمل التزاماً", "الصفحة 1 ⁄ 2",
    "الصفحة 1 / 2 / 3", "رقم الملف 1 / 2",
])
def test_other_controls_prose_and_confusables_do_not_expand_folio_grammar(text):
    node = paragraph(text)
    before = etree.tostring(node)
    assert _folio_ltr_span(node, controlled_numeric=True) is None
    assert etree.tostring(node) == before


def marked_fixture(monkeypatch):
    original = fixture.document_bytes

    def document_bytes(texts, edit):
        texts = [text.replace("الصفحة 2 / 7", f"الصفحة {LRM}2{LRM} / {LRM}7{LRM}")
                 .replace("الصفحة 7 / 7", f"الصفحة {LRM}7{LRM} ／ {LRM}7{LRM}")
                 for text in texts]
        return original(texts, edit)

    monkeypatch.setattr(fixture, "document_bytes", document_bytes)
    return fixture.multipage_fixture("AR")


def test_new_writer_context_is_bound_and_old_marked_output_replays_exactly(monkeypatch):
    args = marked_fixture(monkeypatch)
    old = fixture.build(args)
    assert old.source_map["source_layout_plan"]["folio_direction_version"] == "numeric_run_ltr_v2"
    assert old.source_map["source_layout_plan"]["folio_ltr_spans"] == []
    before = (old.docx_bytes, deepcopy(old.source_map))
    fixture.verify(old, args)
    assert before == (old.docx_bytes, old.source_map)

    new_args = list(args)
    new_args[4] = {**args[4], "source_folio_direction_version": "numeric_run_ltr_v3"}
    new = fixture.build(new_args)
    fixture.verify(new, new_args)
    plan = new.source_map["source_layout_plan"]
    assert plan["folio_direction_version"] == "numeric_run_ltr_v3"
    assert len(plan["folio_ltr_spans"]) == 2
    with ZipFile(BytesIO(new.docx_bytes)) as archive:
        for part in ("word/footer2.xml", "word/footer3.xml"):
            footer = etree.fromstring(archive.read(part))
            folio = footer.findall(W + "p")[-1]
            assert LRM in "".join(n.text or "" for n in folio.iter(W + "t"))
            assert not list(folio.iter(W + "dir"))
    with pytest.raises(ValueError, match="source_folio_direction_version"):
        fixture.verify(new, args)
    with pytest.raises(ValueError, match="source_folio_direction_version"):
        fixture.verify(old, new_args)


def test_exact_previous_source_bound_policy_keeps_its_original_normalizers():
    from legalpdf_translate.ordinary_auto_layout import (
        _optional_hint_policy, _source_bound_v3_policy, _metadata_normalization_policies,
        _source_folio_policies, _band_normalization_version, _source_normalization_version,
        frozen_automatic_layout_policy)

    old = _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v3", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v2")
    assert old == _source_bound_v3_policy()
    assert old != frozen_automatic_layout_policy()
    assert old in _metadata_normalization_policies() & _source_folio_policies()
    assert _band_normalization_version(old.split(":", 1)[1]) == "ordinary_metadata_band_normalization_v2"
    assert _source_normalization_version(old.split(":", 1)[1]) == "ordinary_optional_layout_hint_normalization_v3"
