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
            {"text": "Data", "source_text": "Data", "bbox": [5, 5, 45, 35], "row": 0, "col": 0},
            {"text": "12/10/2026", "source_text": "12/10/2026", "bbox": [45, 5, 115, 35], "row": 0, "col": 1},
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


def _word_tsv(*lines: dict) -> str:
    """Realistic one-word TSV rows; line order is intentionally not sorted."""
    rows = [_TSV.splitlines()[0], _TSV.splitlines()[1]]
    for line in lines:
        left = line.get("left", 100)
        for index, token in enumerate(line["text"].split(), 1):
            token_width = max(15, len(token) * 10)
            rows.append("\t".join(str(value) for value in (
                5, 1, line.get("block", 1), line.get("paragraph", 1),
                line.get("line", 1), index, left, line.get("top", 400),
                token_width, line.get("height", 30), line.get("confidence", 96), token,
            )))
            left += token_width + line.get("word_gap", 10)
    return "\n".join(rows)


def test_tsv_wraps_three_list_lines_from_same_paragraph_without_changing_tokens() -> None:
    tsv = _word_tsv(
        {"text": "1. Comparecer perante o tribunal", "line": 1},
        {"text": "na data e hora indicadas", "line": 2, "top": 440, "left": 130},
        {"text": "com a identificação original.", "line": 3, "top": 480, "left": 130},
        {"text": "2. Trazer os documentos.", "line": 4, "top": 520},
    )
    structure = structure_from_tesseract_tsv(tsv, page_size=(500, 1000))
    assert [block.role for block in structure.blocks] == ["list_item", "list_item"]
    assert structure.blocks[0].text == (
        "1. Comparecer perante o tribunal na data e hora indicadas com a identificação original."
    )
    assert structure.text.split() == [row.split("\t")[-1] for row in tsv.splitlines()[2:]]
    assert structure.blocks[0].bbox == (50, 200, 212.5, 255)
    assert len(structure.metadata["ocr_line_groups"]) == 4


@pytest.mark.parametrize("change", [
    {"paragraph": 2}, {"block": 2}, {"line": 3}, {"line": "bad"},
    {"left": 600}, {"left": 200}, {"top": 600}, {"top": 415},
    {"height": 5}, {"confidence": 89}, {"word_gap": 130},
    {"text": "2. Outra obrigação"}, {"text": "DESPACHO"},
    {"text": "Rua do Tribunal"}, {"text": "Tribunal Judicial", "top": 50},
    {"text": "Email secretaria@example.test", "top": 1800},
])
def test_tsv_does_not_join_unproven_list_continuations(change: dict) -> None:
    continuation = {"text": "na data indicada.", "line": 2, "top": 440, "left": 130}
    continuation.update(change)
    tsv = _word_tsv({"text": "1. Comparecer perante o tribunal", "line": 1}, continuation)
    structure = structure_from_tesseract_tsv(tsv)
    assert len(structure.blocks) == 2
    assert structure.text.split() == [row.split("\t")[-1] for row in tsv.splitlines()[2:]]


@pytest.mark.parametrize("first", [
    {"text": "1. Comparecer perante o tribunal."},
    {"text": "1. Comparecer perante o tribunal", "confidence": 89},
])
def test_tsv_does_not_extend_completed_or_low_confidence_list(first: dict) -> None:
    tsv = _word_tsv(first, {"text": "na data indicada.", "line": 2, "top": 440, "left": 130})
    assert len(structure_from_tesseract_tsv(tsv).blocks) == 2


def test_tsv_word_evidence_binds_raw_pixels_and_final_joined_block_ids() -> None:
    tsv = _word_tsv(
        {"text": "1. Comparecer perante o tribunal"},
        {"text": "na data indicada.", "line": 2, "top": 440, "left": 130},
        {"text": "2. Trazer identificação.", "line": 3, "top": 480},
    )
    structure = structure_from_tesseract_tsv(tsv, page_number=5, page_size=(500, 1000))
    packet = structure.metadata["ocr_word_evidence"]
    assert set(packet) == {"version", "tsv_sha256", "image_size_px", "words"}
    assert packet["version"] == 1
    assert packet["tsv_sha256"] == text_sha256(tsv)
    assert packet["image_size_px"] == [1000, 2000]
    assert packet["words"][0] == {
        "block_id": "p0005_b0001", "text": "1.", "bbox_px": [100, 400, 120, 430],
        "confidence": 96, "group": [1, 1, 1], "word_number": 1,
    }
    assert [word["text"] for word in packet["words"]] == structure.text.split()
    for block in structure.blocks:
        assert [word["text"] for word in packet["words"] if word["block_id"] == block.id] == block.text.split()
    assert packet["words"][5]["block_id"] == "p0005_b0001"
    assert packet["words"][-1]["block_id"] == "p0005_b0002"
    assert structure.metadata["extraction_version"] == "new_run_source_v2"


def test_rebind_updates_word_block_ids_without_scaling_raw_pixel_evidence() -> None:
    original = structure_from_tesseract_tsv(_word_tsv(
        {"text": "1. Comparecer perante o tribunal"},
        {"text": "na data indicada.", "line": 2, "top": 440, "left": 130},
    ), page_size=(500, 1000))
    before = original.to_dict()
    rebound = rebind_page_structure(original, page_number=8, page_size=(250, 500))
    expected_packet = json.loads(json.dumps(before["metadata"]["ocr_word_evidence"]))
    for word in expected_packet["words"]:
        word["block_id"] = "p0008_b0001"
    assert rebound.metadata["ocr_word_evidence"] == expected_packet
    assert rebound.blocks[0].bbox == tuple(value / 2 for value in original.blocks[0].bbox)
    assert original.to_dict() == before


def test_legacy_multi_token_tsv_rows_keep_text_without_inventing_word_boxes() -> None:
    structure = structure_from_tesseract_tsv(_TSV)
    assert "ocr_word_evidence" not in structure.metadata
    assert structure.metadata["ocr_word_evidence_unavailable"] == "invalid_word_evidence"
    assert structure.metadata["ocr_tsv_sha256"] == text_sha256(_TSV)


@pytest.mark.parametrize("column,value", [("conf", "101"), ("word_num", "0"), ("par_num", "bad")])
def test_malformed_word_packet_retains_extraction_without_claiming_evidence(column: str, value: str) -> None:
    rows = [row.split("\t") for row in _word_tsv({"text": "Conteúdo integral."}).splitlines()]
    rows[2][rows[0].index(column)] = value
    tsv = "\n".join("\t".join(row) for row in rows)
    structure = structure_from_tesseract_tsv(tsv)
    assert structure.text.split() == ["Conteúdo", "integral."]
    assert "ocr_word_evidence" not in structure.metadata
    assert structure.metadata["ocr_word_evidence_unavailable"] == "invalid_word_evidence"


@pytest.mark.parametrize("bound", ["MAX_OCR_WORDS", "MAX_OCR_WORD_EVIDENCE_BYTES"])
def test_word_packet_overflow_keeps_extraction_but_omits_evidence(monkeypatch, bound: str) -> None:
    monkeypatch.setattr("legalpdf_translate.document_structure." + bound, 1)
    structure = structure_from_tesseract_tsv(_word_tsv({"text": "Conteúdo integral."}))
    assert structure.text == "Conteúdo integral."
    assert "ocr_word_evidence" not in structure.metadata
    assert structure.metadata["ocr_word_evidence_unavailable"] == "word_evidence_bound_exceeded"


def test_tsv_interleaved_line_groups_never_reorder_source_tokens() -> None:
    tsv = _word_tsv(
        {"text": "Primeiro", "block": 1},
        {"text": "Segundo", "block": 2, "top": 500},
        {"text": "Terceiro", "block": 1},
    )
    structure = structure_from_tesseract_tsv(tsv)
    assert structure.text.split() == ["Primeiro", "Segundo", "Terceiro"]
    assert [word["text"] for word in structure.metadata["ocr_word_evidence"]["words"]] == structure.text.split()
    # Duplicate/conflicting groups are retained for rejection by the separate
    # eligibility policy; the parser must not repair or sort their evidence.
    assert len(structure.metadata["ocr_line_groups"]) == 3


def test_tsv_list_indent_must_stay_near_original_item_not_drift_each_line() -> None:
    tsv = _word_tsv(
        {"text": "1. Comparecer perante o tribunal", "left": 100},
        {"text": "na data e hora indicadas", "line": 2, "top": 440, "left": 150},
        {"text": "com todos os documentos", "line": 3, "top": 480, "left": 200},
    )
    structure = structure_from_tesseract_tsv(tsv)
    assert len(structure.blocks) == 2
    assert structure.blocks[0].text.endswith("na data e hora indicadas")
    assert structure.blocks[1].text == "com todos os documentos"


def test_tsv_list_join_never_sorts_backwards_words() -> None:
    rows = _word_tsv(
        {"text": "1. Comparecer perante o tribunal"},
        {"text": "na data indicada.", "line": 2, "top": 440, "left": 130},
    ).splitlines()
    rows[7], rows[8] = rows[8], rows[7]
    structure = structure_from_tesseract_tsv("\n".join(rows))
    assert len(structure.blocks) == 2
    assert structure.blocks[1].text == "data na indicada."
    assert [word["text"] for word in structure.metadata["ocr_word_evidence"]["words"]] == structure.text.split()


@pytest.mark.parametrize("mutate", [
    lambda packet: packet.update(version=True),
    lambda packet: packet.update(version=2),
    lambda packet: packet.update(words={}),
    lambda packet: packet["words"][0].update(block_id="p0009_b0001"),
    lambda packet: packet["words"][0].update(block_id=[]),
])
def test_rebind_rejects_unbound_word_metadata_without_mutating_input(mutate) -> None:
    source = structure_from_tesseract_tsv(_word_tsv({"text": "Conteúdo integral."}))
    mutate(source.metadata["ocr_word_evidence"])
    before = source.to_dict()
    with pytest.raises(ValueError, match="source word"):
        rebind_page_structure(source, page_number=8)
    assert source.to_dict() == before


@pytest.mark.parametrize("dimension", ["1000.5", "2000.5"])
def test_tsv_noninteger_image_dimensions_do_not_claim_pixel_evidence(dimension: str) -> None:
    tsv = _word_tsv({"text": "Conteúdo integral."}).replace("1000\t2000", dimension + "\t2000")
    structure = structure_from_tesseract_tsv(tsv)
    assert structure.text == "Conteúdo integral."
    assert "ocr_word_evidence" not in structure.metadata


def test_tsv_multiple_page_rows_do_not_claim_single_image_evidence() -> None:
    tsv = _word_tsv({"text": "Conteúdo integral."}) + "\n1\t2\t0\t0\t0\t0\t0\t0\t1000\t2000\t-1\t"
    structure = structure_from_tesseract_tsv(tsv)
    assert structure.text == "Conteúdo integral."
    assert "ocr_word_evidence" not in structure.metadata








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
