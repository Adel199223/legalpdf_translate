"""Closed numeric references keep saved character order in Arabic DOCX runs.

These synthetic OOXML checks do not claim native Word visual acceptance.
"""

from copy import deepcopy
import hashlib
import json
import subprocess
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.docx_writer import (
    _keep_numeric_slash_separators_ltr,
    _segment_rtl_placeholder_aware_runs,
    assemble_docx,
    sanitize_bidi_controls,
    unwrap_internal_placeholders,
)
from legalpdf_translate.types import TargetLang


def _protected(value, isolated):
    return f"\u2066[[{value}]]\u2069" if isolated else f"[[{value}]]"


def _expected(text, strip):
    text = unwrap_internal_placeholders(text)
    return sanitize_bidi_controls(text) if strip else text


@pytest.mark.parametrize("value", ["2/98", "14/2", "38/2009", "02/0098", "12345/67890"])
@pytest.mark.parametrize("shape", ["plain", "whole", "split", "mixed"])
@pytest.mark.parametrize("isolated", [False, True])
@pytest.mark.parametrize("strip", [False, True])
def test_closed_numeric_reference_is_one_ltr_run(value, shape, isolated, strip):
    left, right = value.split("/")
    token = {"plain": value, "whole": _protected(value, isolated),
             "split": _protected(left, isolated) + "/" + _protected(right, isolated),
             "mixed": _protected(left, isolated) + "/" + right}[shape]
    text = f"القانون {token} ثم النص."
    runs, mixed = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=strip)
    assert "".join(chunk for _, chunk in runs) == _expected(text, strip)
    assert mixed
    assert any(kind == "ltr" and sanitize_bidi_controls(chunk) == value for kind, chunk in runs)
    assert not any(kind == "rtl" and "/" in chunk for kind, chunk in runs)


@pytest.mark.parametrize("value", [
    "A[[2]]/[[98]]", "[[2]]/[[98]]B", "_[[2]]/[[98]]", "[[2]]/[[98]]_",
    "أ[[2]]/[[98]]", "[[2]]/[[98]]أ", "A\u0301[[2]]/[[98]]", "[[2]]/[[98]]\u0301",
    "A\u200d[[2]]/[[98]]", "[[2]]/[[98]]\u200c", "A\u0301.[[2]]/[[98]]",
    "[[2]] / [[98]]", "[[2]]\t/[[98]]", "[[2]]/\n[[98]]", "[[2]]\r\n/[[98]]",
    "[[2]]/[[98]]/[[1]]", "/[[2]]/[[98]]", "[[2]]/[[98]]/", "[[2]]//[[98]]",
    "ABC-[[2]]/[[98]]", "[[2]]/[[98]]-A", "12.[[2]]/[[98]]", "[[2]]/[[98]].5",
    "[[2]]/[[98]]:30", "ABC\\[[2]]/[[98]]", "[[2]]/[[98]]@A", "[[2]]/[[98]]+5",
    "ABC--[[2]]/[[98]]", "[[2]]/[[98]]..5", "-[[2]]/[[98]]", "+[[2]]/[[98]]",
    "[[2]]/[[AA]]", "[[٢]]/[[٩٨]]", "[[۲]]/[[۹۸]]", "[[[2]]/[[98]]]",
])
@pytest.mark.parametrize("strip", [False, True])
def test_partial_ambiguous_or_non_ascii_values_are_not_joined(value, strip):
    text = f"النص {value} نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=strip)
    assert "".join(chunk for _, chunk in runs) == _expected(text, strip)
    assert any(kind == "rtl" and "/" in chunk for kind, chunk in runs)


@pytest.mark.parametrize("value", ["[[2]]/[[98]", "[[2]]/98]]"])
def test_malformed_saved_wrappers_are_not_repaired(value):
    text = "النص " + value + " نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=True)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    assert ("ltr", "2/98") not in runs


def test_parentheses_and_terminal_punctuation_do_not_change_the_reference():
    text = "النص ([[2]]/[[98]])؛ ثم [[14]]/[[2]]."
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=True)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    assert ("ltr", "2/98") in runs and ("ltr", "14/2") in runs


@pytest.mark.parametrize("control", ["\u061c", "\u200f", "\u202a", "\u202b", "\u202d", "\u202e", "\u2067", "\u2068", "\ufeff"])
@pytest.mark.parametrize("location", ["start", "inside", "end"])
def test_conflicting_retained_controls_decline_slash_join(control, location):
    token = "[[2]]/[[98]]"
    token = control + token if location == "start" else token + control if location == "end" else "[[2]]/" + control + "[[98]]"
    text = "النص " + token + " نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=False)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    assert any(kind == "rtl" and "/" in chunk for kind, chunk in runs)
    stripped, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=True)
    assert ("ltr", "2/98") in stripped


@pytest.mark.parametrize("opener,closer", [("\u2067", "\u2069"), ("\u2068", "\u2069"),
                                          ("\u202a", "\u202c"), ("\u202b", "\u202c"),
                                          ("\u202d", "\u202c"), ("\u202e", "\u202c")])
@pytest.mark.parametrize("separator", [" ", "\n"])
def test_enclosing_conflicting_scope_is_seen_even_before_an_explicit_line(opener, closer, separator):
    token = "\u2066[[2]]\u2069/\u2066[[98]]\u2069"
    text = opener + "النص" + separator + "المرجع " + token + " نهاية" + closer
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=False)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    assert any(kind == "rtl" and "/" in chunk for kind, chunk in runs)


@pytest.mark.parametrize("text", ["النص \u2066[[2]]/[[98]] نهاية", "النص [[2]]/[[98]]\u2069 نهاية",
                                   "\u2066النص [[2]]/[[98]] نهاية", "النص [[2]]/[[98]]\u202c نهاية"])
def test_incomplete_retained_scopes_are_not_inferred_as_owned_tokens(text):
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=False)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    assert any(kind == "rtl" and "/" in chunk for kind, chunk in runs)


def test_balanced_ltr_scope_and_separate_completed_rtl_scope_are_supported():
    text = "\u2067نص آخر\u2069 ثم \u2066المرجع [[2]]/[[98]] نهاية\u2069"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=False)
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)
    assert ("ltr", "2/98") in runs


def test_slash_rule_changes_only_slash_direction_and_preserves_line_barriers():
    segments = [("rtl", "نص "), ("ltr", "2"), ("rtl", "/"), ("ltr", "98"),
                ("rtl", " ثم\n"), ("ltr", "2"), ("rtl", "/\n"), ("ltr", "98")]
    joined = _keep_numeric_slash_separators_ltr(segments)
    before = [(kind, char) for kind, chunk in segments for char in chunk]
    after = [(kind, char) for kind, chunk in joined for char in chunk]
    changed = [(left, right) for left, right in zip(before, after) if left != right]
    assert changed == [(("rtl", "/"), ("ltr", "/"))]
    assert "".join(chunk for _, chunk in joined) == "".join(chunk for _, chunk in segments)
    assert not any("2/\n98" in chunk for _, chunk in joined)


def test_clock_and_legal_label_punctuation_keep_their_existing_behavior():
    text = "القانون: [[2]]/[[98]]؛ الموعد: [[09]]:[[30]]، الاسم: [[João]] والمبلغ [[150,00]]"
    runs, _ = _segment_rtl_placeholder_aware_runs(text, strip_bidi_controls=True)
    assert [chunk for kind, chunk in runs if kind == "ltr"] == ["2/98", "09:30", "João", "150,00"]
    assert sum(chunk.count(":") for kind, chunk in runs if kind == "rtl") == 3
    assert "".join(chunk for _, chunk in runs) == unwrap_internal_placeholders(text)


@pytest.mark.parametrize("strip", [False, True])
def test_saved_structured_docx_keeps_actual_split_wrapper_shape_in_one_ltr_run(tmp_path, monkeypatch, strip):
    def no_native(*args, **kwargs):
        pytest.fail("Synthetic numeric-slash DOCX must not launch native processes")
    monkeypatch.setattr(subprocess, "Popen", no_native)
    pages = tmp_path / "pages"
    pages.mkdir()
    token = "\u2066[[2]]\u2069/\u2066[[98]]\u2069"
    source = PageStructure(page_number=1, source_sha256="a" * 64, source_file_sha256="b" * 64,
        blocks=[StructureBlock("p0001_b0001", text="Referência 2/98.", role="paragraph", bbox=(50, 100, 540, 140)),
                StructureBlock("p0001_b0002", text="Outra referência 2/98.", role="paragraph", bbox=(50, 180, 540, 220))])
    source.source_sha256 = source.source_text_sha256 = text_sha256(source.text)
    target = deepcopy(source.to_dict())
    texts = [f"القانون {token} واجب التطبيق.", f"المرجع {token} في النص."]
    for block, text in zip(target["blocks"], texts):
        block["text"] = text
    translated = "\n".join(texts)
    target["translation_sha256"] = text_sha256(translated)
    (pages / "page_0001.txt").write_text(translated, encoding="utf-8")
    (pages / "page_0001.source_structure.json").write_text(json.dumps(source.to_dict(), ensure_ascii=False), encoding="utf-8")
    (pages / "page_0001.structure.json").write_text(json.dumps(target, ensure_ascii=False), encoding="utf-8")
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pages.iterdir()}
    output = assemble_docx(pages, tmp_path / "references.docx", lang=TargetLang.AR,
                           page_breaks=False, page_numbers=[1], strip_bidi_controls=strip)
    assert {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in pages.iterdir()} == before
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    val = "{" + ns["w"] + "}val"
    with ZipFile(output) as archive:
        xml = archive.read("word/document.xml")
    root = ET.fromstring(xml)
    assert b"[[" not in xml and b"]]" not in xml
    found = []
    for paragraph in root.findall("./w:body/w:p", ns):
        actual = "".join(node.text or "" for node in paragraph.findall(".//w:t", ns))
        clean = sanitize_bidi_controls(actual)
        if "2/98" not in clean:
            continue
        found.append(clean)
        assert paragraph.find("w:pPr/w:bidi", ns) is not None
        reference_runs = []
        for run in paragraph.findall("w:r", ns):
            text = "".join(node.text or "" for node in run.findall("w:t", ns))
            if "/" in text:
                reference_runs.append(run)
                assert sanitize_bidi_controls(text) == "2/98"
                assert run.find("w:rPr/w:rtl", ns).get(val) == "0"
                assert run.find("w:rPr/w:sz", ns).get(val) == "22"
                assert run.find("w:rPr/w:rFonts", ns).get("{" + ns["w"] + "}ascii") == "Arial"
            elif any("\u0620" <= char <= "\u064a" for char in text):
                assert run.find("w:rPr/w:rtl", ns).get(val) == "1"
        assert len(reference_runs) == 1
        # Writer-inserted LRMs are the only permitted extra controls.
        index = len(found) - 1
        assert actual.replace("\u200e", "") == _expected(texts[index], strip)
    assert found == [sanitize_bidi_controls(unwrap_internal_placeholders(text)) for text in texts]


@pytest.mark.parametrize("lang", [TargetLang.EN, TargetLang.FR])
def test_non_rtl_document_remains_ordinary_text(tmp_path, lang):
    pages = tmp_path / "pages"
    pages.mkdir()
    (pages / "page_0001.txt").write_text("Reference 2/98.", encoding="utf-8")
    output = assemble_docx(pages, tmp_path / "latin.docx", lang=lang, page_breaks=False)
    with ZipFile(output) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    assert "".join(node.text or "" for node in root.findall(".//w:body/w:p/w:r/w:t", ns)) == "Reference 2/98."
    assert root.find(".//w:body/w:p/w:pPr/w:bidi", ns) is None
