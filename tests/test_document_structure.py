from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legalpdf_translate.document_structure import (
    PageStructure, classify_document_boundaries, parse_ocr_structure, plain_text_from_structure, rebind_page_structure,
    structure_from_ordered, structure_from_tesseract_tsv, structure_from_text, text_sha256,
    validate_page_structure,
)
from legalpdf_translate.pdf_text_order import TextBlock


def test_text_fallback_is_stable_compact_and_marks_uncertain_structure() -> None:
    text = "NOTIFICAÇÃO\nO tribunal informa que\na audiência será realizada.\n\n1. Comparecer à hora marcada.\n2. Trazer identificação."
    first = structure_from_text(text, page_number=2)
    second = structure_from_text(text, page_number=2)
    assert first.fingerprint == second.fingerprint
    assert first.uncertain
    assert [block.id for block in first.blocks] == [f"p0002_b{index:04d}" for index in range(1, 5)]
    assert [block.role for block in first.blocks] == ["heading", "paragraph", "list_item", "list_item"]
    assert first.blocks[1].text == "O tribunal informa que a audiência será realizada."
    assert first.source_sha256 == text_sha256(plain_text_from_structure(first))
    assert PageStructure.from_dict(first.to_dict()).to_dict() == first.to_dict()
    assert not any(block.continuation_of for block in first.blocks)


@pytest.mark.parametrize("mutate", [
    lambda value: value.update(version=2),
    lambda value: value.update(page_number=0),
    lambda value: value.update(width_pt=float("nan")),
    lambda value: value["blocks"][0].update(role="script"),
    lambda value: value["blocks"].append(value["blocks"][0].copy()),
    lambda value: value["blocks"][0].update(id="p0002_b0001"),
    lambda value: value["blocks"][0].update(bbox=[0, 0, -1, 2]),
    lambda value: value["blocks"][0].update(bold="true"),
    lambda value: value["blocks"][0].update(role="table_cell", table_id="table", row=0),
])
def test_malformed_structure_rejected(mutate) -> None:
    value = structure_from_text("Conteúdo completo.", page_number=1).to_dict()
    mutate(value)
    with pytest.raises(ValueError):
        validate_page_structure(value)


def test_ocr_table_geometry_and_page_rebinding() -> None:
    raw = json.dumps({"blocks": [
        {"text": "Data", "role": "table_cell", "table_id": "p0001_t0001", "row": 0, "col": 0, "bbox": [.1, .2, .4, .3], "bold": True},
        {"text": "12/10/2026", "role": "table_cell", "table_id": "p0001_t0001", "row": 0, "col": 1, "bbox": [.4, .2, .8, .3]},
    ]})
    structure = parse_ocr_structure(raw, page_size=(600, 800))
    assert structure.blocks[0].bbox == (60, 160, 240, 240)
    assert structure.blocks[0].bold
    rebound = rebind_page_structure(structure, page_number=8, page_size=(300, 400), source_file_sha256="a" * 64)
    assert rebound.blocks[0].id == "p0008_b0001"
    assert rebound.blocks[0].table_id == "p0008_t0001"
    assert rebound.blocks[0].bbox == (30, 80, 120, 120)
    assert rebound.source_file_sha256 == "a" * 64
    assert structure.page_number == 1  # Rebinding does not mutate the source.
    malformed = json.loads(raw)
    malformed["blocks"][1]["col"] = 0
    with pytest.raises(ValueError, match="Duplicate table"):
        parse_ocr_structure(json.dumps(malformed))


def test_target_sidecar_retains_source_hash_with_distinct_target_hash() -> None:
    source = structure_from_text("Comparecer à audiência.", page_number=1).to_dict()
    original_hash = source["source_sha256"]
    source["blocks"][0]["text"] = "Attend the hearing."
    source["translation_sha256"] = text_sha256("Attend the hearing.")
    translated = validate_page_structure(source)
    assert translated.source_sha256 == original_hash
    assert text_sha256(plain_text_from_structure(translated)) == translated.translation_sha256




def test_digital_table_only_replaces_blocks_when_all_source_tokens_are_present() -> None:
    ordered = SimpleNamespace(
        text="Data 12/10/2026", page_width=600, page_height=800, fragmented=False,
        all_blocks=(TextBlock(10, 10, 110, 30, "Data 12/10/2026"),),
        tables=({"bbox": [5, 5, 115, 35], "table_id": "p0001_t0001", "cells": [
            {"text": "Data", "bbox": [5, 5, 45, 35], "row": 0, "col": 0},
            {"text": "12/10/2026", "bbox": [45, 5, 115, 35], "row": 0, "col": 1},
        ]},),
    )
    structured = structure_from_ordered(ordered, page_number=1)
    assert [block.role for block in structured.blocks] == ["table_cell", "table_cell"]
    ordered.tables[0]["cells"][1]["text"] = "12/10/2027"
    rejected = structure_from_ordered(ordered, page_number=1)
    assert rejected.text == "Data 12/10/2026"
    assert rejected.uncertain


_TSV = "\n".join([
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
    "1\t1\t0\t0\t0\t0\t0\t0\t1000\t2000\t-1\t",
    "5\t1\t1\t1\t1\t1\t100\t200\t200\t40\t95\tO tribunal",
    "5\t1\t1\t1\t2\t1\t100\t250\t300\t40\t50\tnotifica a testemunha para comparecer.",
    "5\t1\t2\t1\t1\t1\t550\t200\t300\t40\t98\tSegunda coluna de texto.",
])


def test_tsv_retains_line_column_geometry_without_one_paragraph_per_wrapped_line() -> None:
    structure = structure_from_tesseract_tsv(_TSV, page_size=(500, 1000))
    assert len(structure.blocks) == 2
    assert structure.blocks[0].text == "O tribunal notifica a testemunha para comparecer."
    assert structure.blocks[0].bbox == (50, 100, 200, 145)
    assert structure.blocks[1].bbox[0] == 275
    assert structure.blocks[0].uncertain
    assert len(structure.metadata["ocr_line_groups"]) == 3








@pytest.mark.parametrize("title,kind", [
    ("NOTIFICAÇÃO POR VIA POSTAL SIMPLES", "notification"),
    ("Notificação para comparecer", "notification"),
    ("DESPACHO", "decision"), ("Decisão instrutória", "decision"),
    ("SENTENÇA", "decision"), ("Despacho de arquivamento", "decision"),
    ("ACUSAÇÃO", "prosecution"), ("Acusação do Ministério Público", "prosecution"),
])
def test_document_type_title_at_page_start_establishes_boundary(title: str, kind: str) -> None:
    payload = parse_ocr_structure(json.dumps({"blocks": [
        {"text": "Tribunal Judicial", "role": "header", "bbox": [.1, .04, .9, .08]},
        {"text": "Processo 100/26", "role": "reference", "bbox": [.1, .1, .9, .14]},
        {"text": title, "role": "heading", "bbox": [.1, .18, .9, .25]},
        {"text": "Segue o conteúdo integral do documento.", "role": "paragraph", "bbox": [.1, .3, .9, .4]},
    ]}), page_number=4)
    classified = classify_document_boundaries(payload)
    assert classified.document_start is True
    assert classified.blocks[2].document_start is True
    assert classified.metadata["document_type"] == kind
    assert classified.continuation_from_previous is False
    assert classified.text == payload.text
    assert payload.document_start is False


@pytest.mark.parametrize("title", ["Fundamentação", "FACTOS PROVADOS", "RELATÓRIO", "II. DECISÃO", "Processo 100/26", "Tribunal Judicial", "Ministério Público"])
def test_ongoing_reasoning_and_routine_headers_do_not_create_document_boundary(title: str) -> None:
    source = parse_ocr_structure(json.dumps({"blocks": [{"text": title, "role": "heading", "bbox": [.1, .1, .9, .2]}]}), page_number=3)
    classified = classify_document_boundaries(source)
    assert classified.document_start is False
    assert not classified.metadata.get("document_boundary_review_required")


def test_standalone_heading_can_establish_boundary_without_geometry() -> None:
    source = parse_ocr_structure('{"blocks":[{"text":"ACUSAÇÃO","role":"heading"}]}', page_number=6)
    assert classify_document_boundaries(source).document_start is True


@pytest.mark.parametrize("location", ["midpage", "after_body", "no_geometry", "uncertain"])
def test_ambiguous_document_title_requests_review_without_forcing_page_break(location: str) -> None:
    rows = [{"text": "DECISÃO", "role": "heading", "bbox": [.1, .1, .9, .2]}]
    if location == "midpage":
        rows[0]["bbox"] = [.1, .7, .9, .8]
    elif location == "after_body":
        rows.insert(0, {"text": "Prossegue a fundamentação do documento anterior.", "role": "paragraph"})
    elif location == "no_geometry":
        rows[0].pop("bbox")
        rows[0]["role"] = "paragraph"
    else:
        rows[0]["uncertain"] = True
    source = parse_ocr_structure(json.dumps({"blocks": rows}), page_number=3)
    result = classify_document_boundaries(source)
    assert result.document_start is False
    assert result.uncertain is True
    assert result.metadata["document_boundary_review_required"] is True
    assert result.blocks[-1].uncertain is True


def test_first_source_page_is_natural_boundary_without_guessing_type() -> None:
    source = structure_from_text("Texto de uma carta sem título.", page_number=1)
    result = classify_document_boundaries(source)
    assert result.document_start is True
    assert result.blocks[0].document_start is True
    assert result.metadata["document_boundary_basis"] == "first_source_page"
