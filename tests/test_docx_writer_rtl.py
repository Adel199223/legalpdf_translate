import re
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from legalpdf_translate.docx_writer import assemble_docx
from legalpdf_translate.types import TargetLang

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _W_NS}
_W_VAL = f"{{{_W_NS}}}val"
_DIR_MARKS = str.maketrans("", "", "\u200e\u200f\u2066\u2067\u2068\u2069")


def _write_page(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _read_document_xml(docx_path: Path) -> str:
    with ZipFile(docx_path) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def _first_paragraph_root(document_xml: str) -> ET.Element:
    root = ET.fromstring(document_xml)
    paragraph = root.find(".//w:body/w:p", _NS)
    assert paragraph is not None
    return paragraph


def _paragraph_roots(document_xml: str) -> list[ET.Element]:
    root = ET.fromstring(document_xml)
    return root.findall(".//w:body/w:p", _NS)


def _paragraph_runs(paragraph: ET.Element) -> list[dict[str, str | None]]:
    runs: list[dict[str, str | None]] = []
    for run in paragraph.findall("w:r", _NS):
        text = "".join((node.text or "") for node in run.findall(".//w:t", _NS))
        r_pr = run.find("w:rPr", _NS)
        rtl_val: str | None = None
        if r_pr is not None:
            rtl = r_pr.find("w:rtl", _NS)
            if rtl is not None:
                rtl_val = rtl.attrib.get(_W_VAL, "1")
        runs.append({"text": text, "rtl": rtl_val})
    return runs


def _clean_run_text(text: str | None) -> str:
    return (text or "").translate(_DIR_MARKS)


def test_arabic_docx_sets_rtl_paragraph_and_stable_mixed_runs(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    line = "العنوان: \u2066[[Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira]]\u2069"
    _write_page(pages_dir / "page_0001.txt", line)
    out = tmp_path / "rtl.docx"

    assemble_docx(pages_dir, out, lang=TargetLang.AR, page_breaks=False)

    document_xml = _read_document_xml(out)
    for marker in ("\u2066", "\u2067", "\u2068", "\u2069"):
        assert marker not in document_xml
    assert "[[" not in document_xml
    assert "]]" not in document_xml

    paragraph = _first_paragraph_root(document_xml)
    p_pr = paragraph.find("w:pPr", _NS)
    assert p_pr is not None
    assert p_pr.find("w:bidi", _NS) is not None
    jc = p_pr.find("w:jc", _NS)
    assert jc is not None
    assert jc.attrib.get(_W_VAL) == "right"

    runs = _paragraph_runs(paragraph)
    assert len(runs) >= 2
    combined = "".join((entry["text"] or "") for entry in runs).replace("\u200e", "")
    expected = "العنوان: Rua Luís de Camões no 6, 7960-011 Marmelar, Pedrógão, Vidigueira"
    assert combined == expected
    assert "no 6" in combined

    arabic_runs = [entry for entry in runs if entry["rtl"] == "1" and "العنوان" in (entry["text"] or "")]
    assert arabic_runs
    rua_runs = [entry for entry in runs if "Rua" in (entry["text"] or "")]
    assert rua_runs
    assert all(entry["rtl"] != "1" for entry in rua_runs)


def test_non_rtl_languages_do_not_get_rtl_paragraph_flags(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    _write_page(pages_dir / "page_0001.txt", "Address: Rua Luis de Camoes no. 6")
    out = tmp_path / "en.docx"

    assemble_docx(pages_dir, out, lang=TargetLang.EN, page_breaks=False)

    paragraph = _first_paragraph_root(_read_document_xml(out))
    p_pr = paragraph.find("w:pPr", _NS)
    if p_pr is not None:
        assert p_pr.find("w:bidi", _NS) is None
        assert p_pr.find("w:rtl", _NS) is None


def test_arabic_docx_month_date_mixed_direction_order_is_stable(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    _write_page(pages_dir / "page_0001.txt", "بيجا، \u2066[[10]]\u2069 فبراير \u2066[[2026]]\u2069")
    out = tmp_path / "ar_date.docx"

    assemble_docx(pages_dir, out, lang=TargetLang.AR, page_breaks=False)

    document_xml = _read_document_xml(out)
    for marker in ("\u2066", "\u2067", "\u2068", "\u2069"):
        assert marker not in document_xml
    assert "[[" not in document_xml
    assert "]]" not in document_xml

    paragraph = _first_paragraph_root(document_xml)
    combined = "".join((entry["text"] or "") for entry in _paragraph_runs(paragraph)).replace("\u200e", "")
    assert "فبراير" in combined
    assert re.search(r"10\s*فبراير\s*2026", combined) is not None


def test_arabic_docx_keeps_observed_mixed_script_punctuation_outside_ltr_token_runs(tmp_path: Path) -> None:
    pages_dir = tmp_path / "pages"
    _write_page(
        pages_dir / "page_0001.txt",
        "\n".join(
            [
                "\u2066[[305/23.2GCBJA]]\u2069 | مسطرة عادية (محكمة منفردة) | \u2066[[36312574]]\u2069",
                "I- وجهت النيابة العامة الاتهام، من أجل المحاكمة في مسطرة عادية،",
                (
                    "\u2066[[Soulimane Aouam]]\u2069، المولود بتاريخ \u2066[[18/01/2000]]\u2069، "
                    "المولود في بلجيكا وذو جنسية مغربية، ابن \u2066[[Louiza Elcokile]]\u2069 "
                    "و\u2066[[Mohmad Aouam]]\u2069، المقيم في "
                    "\u2066[[Rua 1.º de Dezembro, 2.º, 7800 – 190 Beja]]\u2069،"
                ),
                (
                    "جريمة تهديد مشددة، المنصوص عليها والمعاقب عليها بموجب المادتين "
                    "\u2066[[153.º]]\u2069 أو \u2066[[155.º]]\u2069 رقم، الفقرة "
                    "\u2066[[1]]\u2069، و\u2066[[a)]]\u2069، من قانون العقوبات."
                ),
            ]
        ),
    )
    out = tmp_path / "observed_shapes.docx"

    assemble_docx(pages_dir, out, lang=TargetLang.AR, page_breaks=False)

    paragraphs = _paragraph_roots(_read_document_xml(out))
    assert len(paragraphs) >= 4

    for paragraph in paragraphs[:4]:
        p_pr = paragraph.find("w:pPr", _NS)
        assert p_pr is not None
        assert p_pr.find("w:bidi", _NS) is not None

    header_runs = _paragraph_runs(paragraphs[0])
    header_ltr_runs = [_clean_run_text(entry["text"]) for entry in header_runs if entry["rtl"] != "1"]
    assert "305/23.2GCBJA" in header_ltr_runs
    assert "36312574" in header_ltr_runs
    assert all("|" not in text for text in header_ltr_runs)
    assert any("|" in _clean_run_text(entry["text"]) for entry in header_runs if entry["rtl"] == "1")

    opener_runs = _paragraph_runs(paragraphs[1])
    opener_ltr_runs = [_clean_run_text(entry["text"]).strip() for entry in opener_runs if entry["rtl"] != "1"]
    assert "I-" in opener_ltr_runs
    assert all("،" not in text for text in opener_ltr_runs)

    mixed_runs = _paragraph_runs(paragraphs[2])
    mixed_ltr_runs = [_clean_run_text(entry["text"]).strip() for entry in mixed_runs if entry["rtl"] != "1"]
    assert "Soulimane Aouam" in mixed_ltr_runs
    assert "18/01/2000" in mixed_ltr_runs
    assert "Louiza Elcokile" in mixed_ltr_runs
    assert "Mohmad Aouam" in mixed_ltr_runs
    assert "Rua 1.º de Dezembro, 2.º, 7800 – 190 Beja" in mixed_ltr_runs
    assert all("،" not in text for text in mixed_ltr_runs)

    statute_runs = _paragraph_runs(paragraphs[3])
    statute_ltr_runs = [_clean_run_text(entry["text"]).strip() for entry in statute_runs if entry["rtl"] != "1"]
    assert "153.º" in statute_ltr_runs
    assert "155.º" in statute_ltr_runs
    assert "1" in statute_ltr_runs
    assert "a)" in statute_ltr_runs
    assert all("،" not in text for text in statute_ltr_runs)
