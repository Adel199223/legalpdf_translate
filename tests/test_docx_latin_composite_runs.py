"""Fictional composite references; validation and visible text stay unchanged."""
import pytest

from legalpdf_translate.docx_writer import _segment_rtl_placeholder_aware_runs, sanitize_bidi_controls


def token(value):
    return "\u2066[[" + value + "]]\u2069"


@pytest.mark.parametrize("literal,wrapped", [
    ("Example Meter 9000 MK II TEST 00123", "Example Meter " + token("9000") + " MK II TEST " + token("00123")),
    ("EN 999", "EN " + token("999")),
    ("1234-567 Vila Nova", token("1234-567") + " " + token("Vila Nova")),
    ("Ana de Sá", token("Ana") + " de " + token("Sá")),
])
@pytest.mark.parametrize("strip", [True, False])
def test_mixed_paragraph_keeps_full_latin_sequence_ltr(literal, wrapped, strip):
    source = "نص " + wrapped + " نهاية"
    runs, mixed = _segment_rtl_placeholder_aware_runs(source, strip_bidi_controls=strip)
    clean = [(kind, sanitize_bidi_controls(value)) for kind, value in runs]
    assert mixed
    assert "".join(value for _, value in clean) == "نص " + literal + " نهاية"
    assert ("ltr", literal) in clean
    assert not any(kind == "ltr" and (value.startswith(" ") or value.endswith(" ")) for kind, value in clean)


def test_arabic_connector_does_not_join_distinct_identifiers():
    source = "نص " + token("Example 12") + " و " + token("Other 34")
    runs, _ = _segment_rtl_placeholder_aware_runs(source, strip_bidi_controls=True)
    assert ("ltr", "Example 12") in runs and ("ltr", "Other 34") in runs
    assert any(kind == "rtl" and "و" in value for kind, value in runs)


def test_numeric_only_groups_do_not_gain_broad_space_equivalence():
    source = "نص " + token("12") + " " + token("34") + " نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(source, strip_bidi_controls=True)
    assert not any(kind == "ltr" and "12 34" in value for kind, value in runs)


def test_composite_does_not_cross_an_explicit_line_boundary():
    source = "نص " + token("Example") + "\n" + token("9000") + " نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(source, strip_bidi_controls=True)
    assert not any(kind == "ltr" and "Example\n9000" in value for kind, value in runs)


def test_retained_rtl_isolate_terminates_composite_grouping():
    source = "نص " + token("Example") + " " + "\u2067[[9000]]\u2069" + " نهاية"
    runs, _ = _segment_rtl_placeholder_aware_runs(source, strip_bidi_controls=False)
    assert not any(kind == "ltr" and "Example 9000" in sanitize_bidi_controls(value) for kind, value in runs)


def test_assembled_docx_has_one_ltr_device_reference_and_no_token_markers(tmp_path):
    from zipfile import ZipFile
    from lxml import etree
    from legalpdf_translate.docx_writer import assemble_docx
    from legalpdf_translate.types import TargetLang
    pages = tmp_path / "pages"
    pages.mkdir()
    literal = "Example Meter 9000 MK II TEST 00123"
    (pages / "page_0001.txt").write_text(
        "نص Example Meter " + token("9000") + " MK II TEST " + token("00123") + " نهاية", encoding="utf-8")
    output = tmp_path / "example.docx"
    assemble_docx(pages, output, lang=TargetLang.AR, page_breaks=True)
    with ZipFile(output) as archive:
        xml = archive.read("word/document.xml")
    assert b"[[" not in xml and b"]]" not in xml
    root = etree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    matches = [run for run in root.findall(".//w:r", ns)
               if literal in sanitize_bidi_controls("".join(run.itertext()))]
    assert len(matches) == 1
    rtl = matches[0].find("w:rPr/w:rtl", ns)
    assert rtl is None or rtl.get("{" + ns["w"] + "}val") == "0"
