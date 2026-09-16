"""Fictional folio/boundary consistency only; no real review or file operations."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib

import pytest

from legalpdf_translate.document_structure import PageStructure, StructureBlock
from legalpdf_translate.reviewed_folios import (
    FolioFragmentInput, FolioPageInput, ReviewedFolioError,
    validate_document_local_folios,
)


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def case(*, lang="AR", groups=((1, 2), (3, 3), (4, 9)), absent=(),
         source_folios=None, target_folios=None):
    """Model adapter metadata without pretending these invented pins prove review."""
    groups = [{"start_page": start, "end_page": end} for start, end in groups]
    pages = []
    for number in range(1, groups[-1]["end_page"] + 1):
        group = next(group for group in groups if group["start_page"] <= number <= group["end_page"])
        start = number == group["start_page"]
        local, total = number - group["start_page"] + 1, group["end_page"] - group["start_page"] + 1
        worded = group["start_page"] == 1
        source_folio = f"Pág. {local} de {total}" if worded else f"{local} / {total}"
        target_folio = ({"AR": f"الصفحة {local} من {total}", "FR": f"Page {local} sur {total}",
                         "EN": f"Page {local} of {total}"}[lang] if worded else f"{local} / {total}")
        source_folio = (source_folios or {}).get(number, source_folio)
        target_folio = (target_folios or {}).get(number, target_folio)
        left, right = "Texto jurídico completo.\n", "Complete reviewed text.\n"
        if number in absent:
            source_folio = target_folio = None
        source_text = left + (source_folio + "\n" if source_folio is not None else "")
        target_text = right + (target_folio + "\n" if target_folio is not None else "")
        block_id = f"p{number:04d}_b100000001"
        image = sha(f"image-{number}")
        source = PageStructure(number, sha(source_text),
            [StructureBlock(block_id, source_text, uncertain=True, document_start=start)],
            uncertain=True, provenance="reviewed_image_source_v1", source_file_sha256="a" * 64,
            source_text_sha256=sha(source_text), document_start=start,
            metadata={"source_page_identity": {"source_file_sha256": "a" * 64, "image_sha256": image,
                "source_type": "browser_pdf_image", "paper_size_basis": "a4_assumed"},
                "selected_text_sha256": sha(source_text), "source_coverage_status": "reviewed_image_transcription",
                "document_boundary_review_required": False, "document_boundary_basis": "explicit_reviewed_image_boundary",
                "reviewed_source": {"version": "reviewed_image_source_v1", "candidate_file_sha256": "b" * 64,
                    "candidate_sha256": "c" * 64, "manifest_sha256": "d" * 64,
                    "review_evidence_sha256": sha(f"review-{number}"), "review_image_sha256": image,
                    "review_kind": "ai_test_review", "boundary": {"decision": "start" if start else "continuation",
                        "rationale": "Fictional explicit source boundary review."},
                    "mapping": [{"id": block_id, "action_id": "whole_page", "baseline_block_ids": [f"p{number:04d}_b0001"]}],
                    "raw_variants": [{"id": "baseline", "text_sha256": sha(f"rawtext-{number}"),
                        "tsv_sha256": sha(f"rawtsv-{number}"), "structure_sha256": sha(f"rawstructure-{number}")}],
                    "geometry_status": "not_verified", "source_acceptance": "not_evaluated", "layout_acceptance": "not_evaluated"}}
        ).to_dict()
        target = deepcopy(source)
        target["blocks"][0]["text"] = target_text
        target["translation_sha256"] = sha(target_text)
        fragments = [FolioFragmentInput(f"p{number:04d}_f0001", block_id, (0, len(left)),
            (0, len(right)), "body", (20, 100, 580, 300))]
        if source_folio is not None or target_folio is not None:
            fragments.append(FolioFragmentInput(f"p{number:04d}_f0002", block_id,
                (len(left), len(source_text)), (len(right), len(target_text)), "folio", (500, 805, 580, 830)))
        pages.append(FolioPageInput(source, target, 840,
            fragments[-1].rendering_id if len(fragments) == 2 else None, tuple(fragments)))
    return groups, pages


def validate(value, *, lang="AR"):
    groups, pages = value
    return validate_document_local_folios(groups, pages=pages, source_file_sha256="a" * 64, target_lang=lang)


@pytest.mark.parametrize("lang", ["AR", "EN", "FR"])
def test_document_local_groups_preserve_originals_and_adapter_uncertainty(lang):
    value = case(lang=lang)
    before = deepcopy(value)
    result = validate(value, lang=lang)
    assert value == before
    assert [(row.local_page, row.local_total) for row in result] == [(1, 2), (2, 2), (1, 1),
        (1, 6), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6)]
    assert [row.document_index for row in result] == [1, 1, 2, 3, 3, 3, 3, 3, 3]
    assert [row.source_page for row in result] == list(range(1, 10))
    assert result[0].source_form == "pt_pag_de" and result[2].source_form == "slash"
    assert result[0].source_numbers == result[0].target_numbers == ("1", "2")
    assert all(page.source_structure["uncertain"] for page in value[1])
    assert all(page.source_structure["metadata"]["reviewed_source"]["source_acceptance"] == "not_evaluated"
               for page in value[1])
    with pytest.raises(FrozenInstanceError):
        result[0].local_page = 99


@pytest.mark.parametrize("source,target", [
    ("Página 1 de 2", "صفحة ١ من ٢"),
    ("Pág. 01 de 02", "الصفحة [[٠١]] من [[٠٢]]"),
    ("Pág. 1 de 2", "\u2067الصفحة \u2066[[1]]\u2069 من [[2]]\u2069"),
    ("pág. 1 de 2", "الصفحة 1 من 2"),
    ("Pág. 1 de 2", "ص. \u2066[[1]]\u2069 من \u2066[[2]]\u2069"),
    ("Pág. 1 de 2", "ص. ١ من ٢"),
])
def test_closed_worded_forms_and_digit_representation_preserve_exact_number_tokens(source, target):
    value = case(source_folios={1: source}, target_folios={1: target})
    row = validate(value)[0]
    assert row.source_numbers == row.target_numbers
    fragment = value[1][0].fragments[-1]
    raw = value[1][0].target_structure["blocks"][0]["text"][slice(*fragment.target_range)]
    assert row.target_folio_sha256 == sha(raw)


def test_missing_folio_does_not_renumber_other_pages():
    rows = validate(case(absent=(2, 6)))
    assert rows[1].folio_fragment_id is None and rows[1].source_form is None
    assert rows[5].folio_fragment_id is None and rows[5].local_page == 3
    assert (rows[6].local_page, rows[6].local_total) == (4, 6)


def test_reviewed_transcription_may_have_no_baseline_ocr_block():
    # reviewed_source transcribe actions may recover text entirely missed by
    # baseline OCR. Exact external action/image evidence remains mandatory.
    value = case()
    edit_source_and_target(value[1][0], lambda source:
        source["metadata"]["reviewed_source"]["mapping"][0].update(baseline_block_ids=[]))
    assert validate(value)[0].local_page == 1


def test_slash_arabic_indic_digits_are_representation_only():
    row = validate(case(target_folios={4: "[[١]] / [[٦]]"}))[3]
    assert row.source_form == row.target_form == "slash"
    assert row.source_numbers == row.target_numbers == ("1", "6")


@pytest.mark.parametrize("source,target", [("4 / 9", "4 / 9"), ("2 / 6", "2 / 6"),
    ("1 / 0", "1 / 0"), ("1 / x", "1 / 6"), ("1 / 6", "2 / 6"),
    ("1 / 6", "1 / 9"), ("1 / 6", "١ / ٧"), ("1 / 6", "1 // 6")])
def test_slash_folios_use_document_position_not_global_page_or_claimed_numbers(source, target):
    with pytest.raises(ReviewedFolioError):
        validate(case(source_folios={4: source}, target_folios={4: target}))


@pytest.mark.parametrize("source", ["Pág. 0 de 2", "Pág. 2 de 2", "Pág. 1 de 9", "Pág. 1 para 2",
    "Página um de dois", "Pág. -1 de 2", "Pág. 1.0 de 2", "Pág. 1000000 de 2",
    "Pág. ١ de ٢", "[[Pág. 1 de 2", "Pág. 1 de 2 extra", "Pág. 1 de 2\nPág. 1 de 2"])
def test_malformed_or_changed_source_numbering_rejected(source):
    with pytest.raises(ReviewedFolioError):
        validate(case(source_folios={1: source}))


@pytest.mark.parametrize("target", ["الصفحة 2 من 2", "الصفحة 1 من 9", "1 / 2", "Pág. 1 de 2",
    "الملف 1 من 2", "الصفحة 1 إلى 2", "الصفحة 1 من 2 extra", "الصفحة 1 من 2\nالصفحة 1 من 2",
    "الصفحة 1 من 2 3", "الصفحة ۱ من ۲", "الصفحة ٠1 من ٢", "الصفحة +1 من 2",
    "الصفحة 1.0 من 2", "الصفحة 0 من 2", "الصفحة [[1] من 2", "الصفحة ١\u202e من ٢"])
def test_malformed_changed_or_wrong_semantic_target_rejected(target):
    with pytest.raises(ReviewedFolioError):
        validate(case(target_folios={1: target}))


@pytest.mark.parametrize("target", ["ص 1 من 2", "ص.1 من 2", "ص: 1 من 2", "ص. 1 إلى 2",
    "ص. 2 من 2", "ص. 1 من 9", "ص. 1 من 2 extra", "ص. ۱ من ۲", "ص. ٠1 من ٢",
    "ص. +1 من 2", "ص. 1.0 من 2", "ص. 1 من 2\nص. 1 من 2", "ص. [[1] من 2"])
def test_arabic_abbreviated_folio_retains_closed_grammar_and_exact_numbers(target):
    with pytest.raises(ReviewedFolioError):
        validate(case(target_folios={1: target}))


@pytest.mark.parametrize("label", ["ص. 2 من 2", "ص 2 من 2", "ص.2 من 2", "ص: 2 من 2"])
def test_target_only_abbreviated_or_malformed_folio_cannot_hide_in_body(label):
    groups, pages = case(absent=(2,))
    page = pages[1]
    text = page.target_structure["blocks"][0]["text"] + label + "\n"
    page.target_structure["blocks"][0]["text"] = text
    page.target_structure["translation_sha256"] = sha(text)
    pages[1] = replace(page, fragments=(replace(page.fragments[0], target_range=(0, len(text))),))
    with pytest.raises(ReviewedFolioError):
        validate((groups, pages))


@pytest.mark.parametrize("body_text", ["صدر الأمر.\n", "صُدر الأمر.\n", "صَادَر القاضي.\n",
    "ص\u200dدر الأمر.\n", "ص\u200cدر الأمر.\n"])
def test_arabic_words_starting_with_sad_are_not_page_abbreviations(body_text):
    groups, pages = case(target_folios={1: "ص. 1 من 2"})
    page = pages[0]
    body, folio = page.fragments
    text = body_text + page.target_structure["blocks"][0]["text"][folio.target_range[0]:]
    page.target_structure["blocks"][0]["text"] = text
    page.target_structure["translation_sha256"] = sha(text)
    pages[0] = replace(page, fragments=(replace(body, target_range=(0, len(body_text))),
        replace(folio, target_range=(len(body_text), len(text)))))
    assert validate((groups, pages))[0].target_form == "ar_abbreviated_page_min"


@pytest.mark.parametrize("lang,target", [("FR", "Page 1 of 2"), ("EN", "Page 1 sur 2"),
    ("AR", "الصفحة 1 من 2")])
def test_target_connector_and_slash_family_are_not_interchangeable(lang, target):
    with pytest.raises(ReviewedFolioError):
        validate(case(lang=lang, target_folios={1 if lang != "AR" else 3: target}), lang=lang)


@pytest.mark.parametrize("groups", [[], [{"start_page": 1, "end_page": 9}],
    [{"start_page": 1, "end_page": 2}, {"start_page": 4, "end_page": 9}],
    [{"start_page": 1, "end_page": 3}, {"start_page": 3, "end_page": 9}],
    [{"start_page": True, "end_page": 2}, {"start_page": 3, "end_page": 9}],
    [{"start_page": 1, "end_page": 2.0}], [{"start_page": 1, "end_page": 0}],
    [{"start_page": 1, "end_page": 10}], [{"start_page": 1, "end_page": 9, "approved": True}]])
def test_groups_are_explicit_exact_accepted_boundary_partition(groups):
    _, pages = case()
    with pytest.raises(ReviewedFolioError):
        validate((groups, pages))


def edit_source_and_target(page, edit):
    for structure in (page.source_structure, page.target_structure):
        edit(structure)


@pytest.mark.parametrize("change", [
    lambda s: s.update(document_start=True),
    lambda s: s["blocks"][0].update(document_start=True),
    lambda s: s["metadata"].update(document_boundary_review_required=True),
    lambda s: s["metadata"].update(document_boundary_basis="document_type_title"),
    lambda s: s["metadata"]["reviewed_source"]["boundary"].update(decision="unresolved"),
    lambda s: s["metadata"]["reviewed_source"]["boundary"].update(decision="start"),
    lambda s: s["metadata"]["reviewed_source"]["boundary"].update(rationale=""),
    lambda s: s["metadata"]["reviewed_source"].update(review_evidence_sha256="bad"),
    lambda s: s["metadata"]["reviewed_source"].update(candidate_file_sha256="f" * 64),
    lambda s: s["metadata"]["reviewed_source"].update(review_image_sha256="f" * 64),
    lambda s: s["metadata"]["reviewed_source"].update(source_acceptance="accepted"),
    lambda s: s["metadata"]["reviewed_source"].update(geometry_status="verified"),
    lambda s: s["metadata"]["reviewed_source"]["mapping"][0].update(id="p0002_b9999"),
    lambda s: s["metadata"]["reviewed_source"]["raw_variants"][0].update(tsv_sha256="bad"),
])
def test_boundary_and_provenance_must_agree_without_inventing_acceptance(change):
    value = case()
    edit_source_and_target(value[1][1], change)
    with pytest.raises(ReviewedFolioError):
        validate(value)


@pytest.mark.parametrize("role", ["body", "signature", "footer", "header"])
def test_role_relabel_does_not_hide_original_folio(role):
    groups, pages = case()
    page = pages[0]
    pages[0] = replace(page, folio_fragment_id=None,
        fragments=(*page.fragments[:-1], replace(page.fragments[-1], role=role)))
    with pytest.raises(ReviewedFolioError):
        validate((groups, pages))


@pytest.mark.parametrize("separator", ["\u00a0", "\u202f", "\u2003"])
def test_unicode_space_slash_cannot_evade_folio_classification(separator):
    text = f"1{separator}/{separator}6"
    groups, pages = case(source_folios={4: text}, target_folios={4: text})
    page = pages[3]
    pages[3] = replace(page, folio_fragment_id=None,
        fragments=(*page.fragments[:-1], replace(page.fragments[-1], role="body")))
    with pytest.raises(ReviewedFolioError):
        validate((groups, pages))


@pytest.mark.parametrize("kind", ["false_absence", "wrong_id", "merged_body", "omitted_fragment",
    "source_range", "target_range", "folio_above_footer", "duplicate_fragment", "bool_range", "nan_box"])
def test_folio_ownership_geometry_and_complete_coverage_are_checked(kind):
    groups, pages = case()
    page = pages[0]
    body, folio = page.fragments
    if kind in {"false_absence", "wrong_id"}:
        pages[0] = replace(page, folio_fragment_id=None if kind == "false_absence" else "p0001_f9999")
    elif kind == "merged_body":
        pages[0] = replace(page, folio_fragment_id=None, fragments=(replace(body,
            source_range=(0, folio.source_range[1]), target_range=(0, folio.target_range[1])),))
    elif kind == "omitted_fragment":
        pages[0] = replace(page, folio_fragment_id=None, fragments=(body,))
    elif kind == "source_range":
        pages[0] = replace(page, fragments=(body, replace(folio, source_range=body.source_range)))
    elif kind == "target_range":
        pages[0] = replace(page, fragments=(body, replace(folio, target_range=body.target_range)))
    elif kind == "folio_above_footer":
        pages[0] = replace(page, fragments=(body, replace(folio, bbox_px=(500, 100, 580, 130))))
    elif kind == "duplicate_fragment":
        pages[0] = replace(page, fragments=(body, folio, folio))
    elif kind == "bool_range":
        pages[0] = replace(page, fragments=(replace(body, source_range=(False, body.source_range[1])), folio))
    elif kind == "nan_box":
        pages[0] = replace(page, fragments=(body, replace(folio, bbox_px=(500, float("nan"), 580, 830))))
    with pytest.raises(ReviewedFolioError):
        validate((groups, pages))


def test_target_only_folio_cannot_hide_in_body_when_source_has_none():
    groups, pages = case(absent=(2,))
    page = pages[1]
    body = page.fragments[0]
    text = page.target_structure["blocks"][0]["text"] + "الصفحة 2 من 2\n"
    page.target_structure["blocks"][0]["text"] = text
    page.target_structure["translation_sha256"] = sha(text)
    pages[1] = replace(page, fragments=(replace(body, target_range=(0, len(text))),))
    with pytest.raises(ReviewedFolioError):
        validate((groups, pages))


def test_unmatched_source_folio_cannot_be_relabelled_as_body():
    groups, pages = case(source_folios={1: "Pág. 1 para 2"})
    page = pages[0]
    pages[0] = replace(page, folio_fragment_id=None,
        fragments=(*page.fragments[:-1], replace(page.fragments[-1], role="body")))
    with pytest.raises(ReviewedFolioError):
        validate((groups, pages))


def test_source_hash_target_structure_or_unsupported_language_cannot_be_substituted():
    value = case()
    value[1][0].target_structure["source_file_sha256"] = "e" * 64
    with pytest.raises(ReviewedFolioError):
        validate(value)
    groups, pages = case()
    with pytest.raises(ReviewedFolioError):
        validate_document_local_folios(groups, pages=pages, source_file_sha256="e" * 64, target_lang="AR")
    with pytest.raises(ReviewedFolioError):
        validate_document_local_folios(groups, pages=pages, source_file_sha256="a" * 64, target_lang="HE")


def test_v1_folio_contract_remains_global_slash_only():
    from tests.test_reviewed_formatting import packet, validate as validate_v1
    from legalpdf_translate.reviewed_formatting import ReviewedFormattingError
    manifest, page = packet()
    assert validate_v1(manifest, page).version == "reviewed_formatting_v1"
    manifest, page = packet(source_parts=["Tribunal Judicial da Comarca de Exemplo\n",
        "Texto.\n", "A Juiz de Direito\n", "Rua Exemplo\nTelef: 123456789\n", "Pág. 1 de 1"])
    with pytest.raises(ReviewedFormattingError):
        validate_v1(manifest, page)


def metadata_case(source_line, target_line):
    """A whole-line top-quarter metadata fragment plus an independent real folio."""
    groups, pages = case(lang="EN", groups=((1, 2),),
        source_folios={1: "1 / 2"}, target_folios={1: "1 / 2"})
    page = pages[0]
    body, folio = page.fragments
    source = deepcopy(page.source_structure)
    target = deepcopy(page.target_structure)
    left, right = source_line + "\n", target_line + "\n"
    source_text = left + source["blocks"][0]["text"][folio.source_range[0]:]
    target_text = right + target["blocks"][0]["text"][folio.target_range[0]:]
    source["blocks"][0]["text"] = source_text
    source["source_sha256"] = source["source_text_sha256"] = sha(source_text)
    source["metadata"]["selected_text_sha256"] = sha(source_text)
    target.update({key: deepcopy(value) for key, value in source.items() if key not in {"blocks", "translation_sha256"}})
    target["blocks"][0]["text"] = target_text
    target["translation_sha256"] = sha(target_text)
    pages[0] = replace(page, source_structure=source, target_structure=target, fragments=(
        replace(body, source_range=(0, len(left)), target_range=(0, len(right)), bbox_px=(20, 100, 580, 120)),
        replace(folio, source_range=(len(left), len(source_text)), target_range=(len(right), len(target_text)))))
    return groups, pages


@pytest.mark.parametrize("source,target", [
    ("236/25.1GCBJA | Processo Comum (Tribunal Singular) | 36592224",
     "236/25.1GCBJA | Ordinary proceedings (single-judge court) | 36592224"),
    ("236/25.1GCBJA\t|\tProcesso Comum\t|\t36592224",
     "236/25.1GCBJA\t|\tOrdinary proceedings\t|\t36592224"),
    ("236/25.1GCBJA | Referência 36592224", "[[236/25.1GCBJA]] | Reference 36592224"),
    ("236/25.1GCBJA [36592224] | Processo Comum | Tribunal Singular | Beja",
     "\u2066[[236/25.1GCBJA]]\u2069 [36592224] | Ordinary proceedings | Single-judge court | Beja"),
])
def test_complete_docket_field_in_pipe_metadata_preserves_real_folio_and_all_bytes(source, target):
    value = metadata_case(source, target)
    before = deepcopy(value)
    result = validate(value, lang="EN")
    assert value == before
    assert result[0].folio_fragment_id == "p0001_f0002"
    assert result[0].source_form == result[0].target_form == "slash"
    assert result[0].source_numbers == result[0].target_numbers == ("1", "2")
    assert result[0].source_folio_sha256 == result[0].target_folio_sha256 == sha("1 / 2\n")


@pytest.mark.parametrize("target", [
    "237/25.1GCBJA | Ordinary proceedings | 36592224",
    "236/25.1GCBJA [36592225] | Ordinary proceedings | 36592224",
    "236/25.1GCBJA | Ordinary proceedings | 36592224",
    "236/25.1gcbja [36592224] | Ordinary proceedings | 36592224",
])
def test_metadata_docket_and_bracketed_reference_require_exact_source_retention(target):
    source = "236/25.1GCBJA [36592224] | Processo Comum | 36592224"
    with pytest.raises(ReviewedFolioError, match="folio_docket_target_changed"):
        validate(metadata_case(source, target), lang="EN")


@pytest.mark.parametrize("side", ["source", "target", "both"])
@pytest.mark.parametrize("position", [1, 2])
@pytest.mark.parametrize("form", ["worded", "wrong_total", "malformed", "slash", "bad_slash"])
def test_docket_mask_never_hides_appended_or_buried_folio_field(side, position, form):
    labels = {"worded": ("Pág. 1 de 2", "Page 1 of 2"),
        "wrong_total": ("Pág. 1 de 9", "Page 1 of 9"),
        "malformed": ("Pág. 1 para 2", "Page 1 to 2"),
        "slash": ("1 / 2", "1 / 2"), "bad_slash": ("1 / x", "1 / x")}
    left = ["236/25.1GCBJA", "Processo Comum", "36592224"]
    right = ["236/25.1GCBJA", "Ordinary proceedings", "36592224"]
    if side in {"source", "both"}:
        left[position] = labels[form][0]
    if side in {"target", "both"}:
        right[position] = labels[form][1]
    with pytest.raises(ReviewedFolioError, match="folio_(?:form_invalid|missing_duplicate_or_relabelled)"):
        validate(metadata_case(" | ".join(left), " | ".join(right)), lang="EN")


@pytest.mark.parametrize("line", [
    "236/25.1gcbja | Metadata | 36592224",
    "236/25.1GCBJA-extra | Metadata | 36592224",
    "236/25.1GCBJA text | Metadata | 36592224",
    "236/25.1GCBJA| Metadata | 36592224",
    "236/25.1GCBJA |Metadata | 36592224",
    "236/25.1GCBJA\u00a0|\u00a0Metadata | 36592224",
    "236/25.1GCBJA | | 36592224",
    "236/25.1GCBJA | Metadata | 36592224 | Beja | Extra",
    "[[236/25.1GCBJA | Metadata | 36592224",
    "236/25.1GCBJA\u2066 | Metadata | 36592224",
    "Metadata | 236/25.1GCBJA | 36592224",
])
def test_nonclosed_docket_metadata_does_not_gain_a_folio_exception(line):
    with pytest.raises(ReviewedFolioError, match="folio_(?:form_invalid|placeholder_invalid|bidi_scope_invalid)"):
        validate(metadata_case(line, line), lang="EN")


@pytest.mark.parametrize("line", [
    "2/98 | Metadata | 36592224", "1 / 2 | Metadata | 36592224",
    "Metadata | 2/98 | 36592224", "Metadata|Page 1 of 2|36592224",
])
def test_pipe_fields_keep_bare_ratios_and_hidden_page_labels_under_folio_validation(line):
    with pytest.raises(ReviewedFolioError):
        validate(metadata_case(line, line), lang="EN")


@pytest.mark.parametrize("line", [
    "Processo 236/25.1GCBJA | Metadata | 36592224",
    "Referência x236/25.1GCBJA | Metadata | 36592224",
    "Acórdão n.º 2/98 | Artigo 1.º | Referência 36592224",
    "Article 2/98 | Reference 236/25.1GCBJA | Case metadata",
])
def test_embedded_identifiers_and_citation_prose_are_not_bare_folio_fields(line):
    value = metadata_case(line, line)
    before = deepcopy(value)
    assert validate(value, lang="EN")[0].source_numbers == ("1", "2")
    assert value == before


@pytest.mark.parametrize("change", ["below_top_quarter", "signature", "target_only"])
def test_metadata_docket_exemption_requires_source_proof_and_top_body_header_owner(change):
    source = "236/25.1GCBJA | Processo Comum | 36592224"
    target = "236/25.1GCBJA | Ordinary proceedings | 36592224"
    value = metadata_case("Metadata | Processo Comum | 36592224" if change == "target_only" else source, target)
    groups, pages = value
    if change != "target_only":
        body, folio = pages[0].fragments
        body = replace(body, bbox_px=(20, 300, 580, 330)) if change == "below_top_quarter" else replace(body, role="signature")
        pages[0] = replace(pages[0], fragments=(body, folio))
    with pytest.raises(ReviewedFolioError, match="folio_form_invalid"):
        validate((groups, pages), lang="EN")
