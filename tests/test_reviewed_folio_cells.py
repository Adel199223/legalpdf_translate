"""Synthetic source-bound docket exclusions and rendered-cell folio scanning."""
from copy import deepcopy
from dataclasses import replace

import pytest

from legalpdf_translate.reviewed_folios import FolioFragmentInput, ReviewedFolioError
from tests.test_reviewed_folios import case, sha, validate


DOCKET = "123/26.1T8ABC"


def fixture(*, lang="AR", source_parts=None, target_parts=None, cells=False,
            role="body", lower=False, absent=False):
    groups, pages = case(lang=lang, groups=((1, 1),), absent=(1,) if absent else ())
    original = pages[0]
    source_parts = source_parts or [DOCKET + "\n", "Conteúdo jurídico completo.\n"]
    target_parts = target_parts or ["[[" + DOCKET + "]]\n", "Complete reviewed content.\n"]
    if not absent:
        source_parts = [*source_parts, "Pág. 1 de 1\n"]
        target_parts = [*target_parts, {"AR": "الصفحة 1 من 1\n", "EN": "Page 1 of 1\n",
                                        "FR": "Page 1 sur 1\n"}[lang]]
    source, target = deepcopy(original.source_structure), deepcopy(original.target_structure)
    source_text, target_text = "".join(source_parts), "".join(target_parts)
    for structure in (source, target):
        structure["source_sha256"] = structure["source_text_sha256"] = sha(source_text)
        structure["metadata"]["selected_text_sha256"] = sha(source_text)
    source["blocks"][0]["text"] = source_text
    target["blocks"][0]["text"] = target_text
    target["translation_sha256"] = sha(target_text)
    fragments, left, right = [], 0, 0
    for index, (source_part, target_part) in enumerate(zip(source_parts, target_parts), 1):
        is_folio = not absent and index == len(source_parts)
        item_role = "folio" if is_folio else role if index == 1 else "body"
        if is_folio:
            box = (500, 805, 580, 830)
        elif cells and index <= 3:
            box = (10 + (index - 1) * 200, 50, 180 + (index - 1) * 200, 85)
        else:
            top = 250 if index == 1 and lower else 20 if index == 1 else 100 + index * 50
            box = (20, top, 580, top + 30)
        fragments.append(FolioFragmentInput(f"p0001_f{index:04d}", source["blocks"][0]["id"],
            (left, left + len(source_part)), (right, right + len(target_part)), item_role, box))
        left += len(source_part)
        right += len(target_part)
    layout = None
    if cells:
        layout = {"version": "reviewed_region_layout_v1", "header": [],
            "body": [{"kind": "table", "table_id": "p0001_t0001", "column_widths": [34, 33, 33],
                      "rows": [{"cells": [{"fragment_ids": [f.rendering_id]} for f in fragments[:3]]}]}],
            "footer": [] if absent else [fragments[-1].rendering_id]}
        for fragment in fragments[3:-1] if not absent else fragments[3:]:
            layout["body"].append({"kind": "paragraph", "fragment_id": fragment.rendering_id})
    pages[0] = replace(original, source_structure=source, target_structure=target,
        folio_fragment_id=None if absent else fragments[-1].rendering_id, fragments=tuple(fragments),
        region_layout=layout, image_width_px=600 if cells else None)
    return groups, pages


@pytest.mark.parametrize("lang", ["AR", "EN", "FR"])
@pytest.mark.parametrize("reference", ["", " [987654321]"])
@pytest.mark.parametrize("role", ["body", "header"])
def test_source_bound_docket_and_optional_literal_reference_are_not_folios(lang, reference, role):
    value = fixture(lang=lang, role=role, source_parts=[DOCKET + reference + "\n", "Conteúdo.\n"],
        target_parts=["\u2066[[" + DOCKET + "]]" + reference + "\u2069\n", "Content.\n"])
    before = deepcopy(value)
    result = validate(value, lang=lang)
    assert result[0].source_numbers == result[0].target_numbers == ("1", "1")
    assert value == before


@pytest.mark.parametrize("lang", ["AR", "EN", "FR"])
def test_first_docket_cell_keeps_literal_pipe_and_independent_offsets(lang):
    value = fixture(lang=lang, cells=True,
        source_parts=[DOCKET + " | ", "Referência: 987 | ", "Data: 23/06/2026\n"],
        target_parts=["[[" + DOCKET + "]] | ", "Reference: [[987]] | ", "Date: [[23/06/2026]]\n"])
    before = deepcopy(value)
    assert validate(value, lang=lang)[0].source_numbers == ("1", "1")
    assert value == before
    page = value[1][0]
    assert page.fragments[0].source_range != page.fragments[0].target_range
    assert page.source_structure["blocks"][0]["text"].count("|") == 2
    assert page.target_structure["blocks"][0]["text"].count("|") == 2


@pytest.mark.parametrize("cells", [False, True])
def test_preserved_source_docket_does_not_invent_an_absent_folio(cells):
    options = (dict(source_parts=[DOCKET + " | ", "Referência: 987 | ", "Data: 23/06/2026\n"],
                    target_parts=["[[" + DOCKET + "]] | ", "Reference: 987 | ", "Date: 23/06/2026\n"])
               if cells else {})
    result = validate(fixture(cells=cells, absent=True, **options))
    assert result[0].folio_fragment_id is None and result[0].source_form is None


@pytest.mark.parametrize("target", [
    "124/26.1T8ABC", "123/25.1T8ABC", "123/26.2T8ABC", "123/26.1T8ABD",
    "123/26.1t8abc", "123 /26.1T8ABC", "123/26.1T8ABC-A", "123/26", "Missing docket",
    "[[123/26.1T8ABC", "123/26.1T8ABC\u2069", "123/26.1T8ABC extra",
])
def test_changed_missing_or_malformed_target_docket_never_gets_source_exception(target):
    value = fixture(target_parts=[target + "\n", "Content.\n"])
    with pytest.raises(ReviewedFolioError, match="^folio_docket_target_changed$"):
        validate(value)


@pytest.mark.parametrize("target_reference", ["", " [987654322]", " [[987654321]]", " [987 654321]",
                                              " [987654321] [1]", " [987654321/9]"])
def test_numeric_reference_is_exact_and_cannot_be_silently_dropped(target_reference):
    value = fixture(source_parts=[DOCKET + " [987654321]\n", "Conteúdo.\n"],
        target_parts=["[[" + DOCKET + "]]" + target_reference + "\n", "Content.\n"])
    with pytest.raises(ReviewedFolioError, match="^folio_docket_target_changed$"):
        validate(value)


@pytest.mark.parametrize("source", ["1/1", "1 / 1", "1\u00a0/\u00a01", "1\u202f/\u202f1", "1/99",
    "123/26", "123/26.1", "123/26.123", "123/26.1T", "123/26.1t8abc", "123/26.1T8ABC-A",
    "123/26.1T8ABC Page 9 of 9", "123/26.1T8ABC [1/9]", "+123/26.1T8ABC"])
def test_closed_docket_exception_never_becomes_general_slash_exemption(source):
    value = fixture(source_parts=[source + "\n", "Conteúdo.\n"],
                    target_parts=[source + "\n", "Content.\n"])
    with pytest.raises(ReviewedFolioError):
        validate(value)


@pytest.mark.parametrize("role,lower", [("signature", False), ("footer", False), ("folio", False),
                                         ("body", True), ("header", True)])
def test_docket_exception_requires_reviewed_top_quarter_header_or_body(role, lower):
    with pytest.raises(ReviewedFolioError):
        validate(fixture(role=role, lower=lower))


@pytest.mark.parametrize("lang,label", [("EN", "Page 9 of 9"), ("FR", "Page 9 sur 9"),
                                         ("AR", "الصفحة 9 من 9"), ("AR", "صفحة تسعة من تسعة"),
                                         ("EN", "Page nine of nine"), ("FR", "Page 1 vers 2"),
                                         ("EN", "1\u00a0/\u00a09"), ("AR", "١ / ٩")])
@pytest.mark.parametrize("with_docket", [False, True])
@pytest.mark.parametrize("absent", [False, True])
def test_invented_or_malformed_later_target_cell_folio_is_always_scanned(lang, label, with_docket, absent):
    first_source = DOCKET if with_docket else "Referência: 987"
    first_target = "[[" + DOCKET + "]]" if with_docket else "Reference: 987"
    value = fixture(lang=lang, cells=True, absent=absent,
        source_parts=[first_source + " | ", "Requerente: Exemplo | ", "Data: 23/06/2026\n"],
        target_parts=[first_target + " | ", label + " | ", "Date: 23/06/2026\n"])
    with pytest.raises(ReviewedFolioError):
        validate(value, lang=lang)


@pytest.mark.parametrize("label", ["Pág. 9 de 9", "Página nove de nove", "1\u00a0/\u00a09", "1 / 9"])
def test_hidden_source_folio_in_later_rendered_cell_cannot_be_omitted(label):
    value = fixture(cells=True,
        source_parts=[DOCKET + " | ", label + " | ", "Data: 23/06/2026\n"],
        target_parts=["[[" + DOCKET + "]] | ", "Reference: 987 | ", "Date: 23/06/2026\n"])
    with pytest.raises(ReviewedFolioError):
        validate(value)


@pytest.mark.parametrize("side", ["source", "target"])
def test_last_cell_folio_without_trailing_pipe_is_not_hidden(side):
    source_parts = [DOCKET + " | ", "Referência: 987 | ", "Data: 23/06/2026\n"]
    target_parts = ["[[" + DOCKET + "]] | ", "Reference: 987 | ", "Date: 23/06/2026\n"]
    (source_parts if side == "source" else target_parts)[2] = "1 / 9\n"
    with pytest.raises(ReviewedFolioError):
        validate(fixture(cells=True, source_parts=source_parts, target_parts=target_parts))


def test_raw_parent_scan_remains_active_when_docket_field_is_not_independently_partitioned():
    # No complete docket field can be proven in this single unpartitioned line.
    value = fixture(source_parts=[DOCKET + " | Referência: 987 | Page 9 of 9\n", "Conteúdo.\n"],
        target_parts=["[[" + DOCKET + "]] | Reference: 987 | Page 9 of 9\n", "Content.\n"])
    with pytest.raises(ReviewedFolioError):
        validate(value)


def test_source_exception_does_not_cover_an_invented_additional_target_docket():
    value = fixture(source_parts=[DOCKET + "\n", "Conteúdo.\n"],
        target_parts=["[[" + DOCKET + "]]\n999/26.1T8ABC\n", "Content.\n"])
    with pytest.raises(ReviewedFolioError, match="^folio_docket_target_changed$"):
        validate(value)


def test_normal_folio_is_not_double_counted_by_parent_and_fragment_views():
    value = fixture()
    result = validate(value)
    assert len(result) == 1 and result[0].source_numbers == ("1", "1")


def test_ordinary_labelled_legal_identifier_needs_no_exemption():
    value = fixture(source_parts=["Processo " + DOCKET + "\n", "Conteúdo.\n"],
        target_parts=["Dossier " + DOCKET + "\n", "Content.\n"], lower=True)
    assert validate(value)[0].source_numbers == ("1", "1")
