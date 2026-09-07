"""Passive format identity and source-bound continuation tests, without model code."""
from __future__ import annotations

import json
import ast
from pathlib import Path
from types import SimpleNamespace
import pytest
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.formatting_support import (digest_text, flatten_blocks, formatting_fingerprint,
    link_source_continuations, save_translated_structure)
from legalpdf_translate.types import TargetLang


def test_format_identity_uses_only_format_controls_and_does_not_mutate_config():
    config = SimpleNamespace(target_lang=TargetLang.AR, page_breaks=False, strip_bidi_controls=True,
                             model="unchanged-production", effort="high", review_policy="unchanged")
    before = vars(config).copy()
    original = formatting_fingerprint(config)
    assert vars(config) == before
    config.model, config.effort, config.review_policy = "other-model", "medium", "other-review"
    assert formatting_fingerprint(config) == original
    config.page_breaks = True
    assert formatting_fingerprint(config) != original
    config.page_breaks, config.strip_bidi_controls = False, False
    assert formatting_fingerprint(config) != original
    config.strip_bidi_controls, config.target_lang = True, TargetLang.FR
    assert formatting_fingerprint(config) != original


@pytest.mark.parametrize("module", ["formatting_support", "docx_writer", "document_structure", "document_layout",
                                   "document_spacing", "section_furniture", "docx_furniture_reflow"])
def test_formatting_modules_have_no_model_prompt_or_provider_dependencies(module):
    path = Path(__file__).resolve().parents[1] / "src" / "legalpdf_translate" / f"{module}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    forbidden = {"translation_structure", "model_policy", "arabic_output_recovery", "arabic_source_spans",
                 "arabic_pre_tokenize", "openai_client", "ocr_engine", "fidelity_review", "fidelity_checks",
                 "workflow", "workflow_components", "benchmark_dispatch", "usage_accounting"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not forbidden.intersection((node.module or "").split("."))
        elif isinstance(node, ast.Import):
            assert all(not forbidden.intersection(alias.name.split(".")) for alias in node.names)
        elif isinstance(node, ast.Assign):
            assert not any(isinstance(target, ast.Name) and target.id == "OCR_STRUCTURE_PROMPT"
                           for target in node.targets)


def _source_blocks() -> list[StructureBlock]:
    return [StructureBlock("p0001_b0001", "Primeira obrigação.", bbox=(20, 30, 500, 60), bold=True),
            StructureBlock("p0001_b0002", "Segunda obrigação.", role="heading", alignment="center")]


def test_translated_sidecar_retains_source_geometry_hashes_and_complete_translated_text(tmp_path):
    source = PageStructure(page_number=1, source_sha256=text_sha256("source"), blocks=_source_blocks())
    rows = [{"id": block.id, "text": text} for block, text in zip(source.blocks, ["First obligation.", "Second obligation."])]
    path = tmp_path / "page_0001.structure.json"
    payload = save_translated_structure(path=path, source_structure=source, translated_blocks=rows,
                                       translated_text=flatten_blocks(rows), translation_fingerprint="identity")
    assert payload["source_sha256"] == source.source_sha256
    assert payload["translation_sha256"] == digest_text(flatten_blocks(rows))
    assert payload["blocks"][0]["bbox"] == [20, 30, 500, 60]
    assert payload["blocks"][1]["alignment"] == "center"
    assert source.blocks[0].text == "Primeira obrigação."
    assert json.loads(path.read_text(encoding="utf-8")) == payload
    with pytest.raises(ValueError, match="does not match"):
        save_translated_structure(path=tmp_path / "bad.json", source_structure=source, translated_blocks=rows,
                                  translated_text="Only a partial paragraph.")
    assert not (tmp_path / "bad.json").exists()


def _continuation_pages() -> dict[int, PageStructure]:
    return {
        1: PageStructure(page_number=1, source_sha256=text_sha256("source one"), blocks=[
            StructureBlock("p0001_b0001", "O arguido deve comparecer na audiência de julgamento marcada para",
                           bbox=(30, 700, 540, 800))]),
        2: PageStructure(page_number=2, source_sha256=text_sha256("source two"), blocks=[
            StructureBlock("p0002_b0001", "o dia indicado na notificação.", bbox=(30, 50, 540, 95))]),
    }


def _furnished_continuation_pages() -> dict[int, PageStructure]:
    pages = _continuation_pages()
    for number, page in pages.items():
        page.blocks.insert(0, StructureBlock(f"p{number:04d}_b0002", "Tribunal Judicial da Comarca", role="header",
                                             bbox=(200, 90, 400, 112)))
        page.blocks.extend([
            StructureBlock(f"p{number:04d}_b0003", "Largo da Justiça, 1", role="footer", bbox=(200, 802, 400, 810)),
            StructureBlock(f"p{number:04d}_b0004", "Telef: 210000000; E-mail: tribunal@example.invalid", role="footer",
                           bbox=(190, 812, 410, 820)),
        ])
        if number == 2:
            page.blocks[1].bbox = (30, 150, 540, 175)
        page.source_file_sha256 = "a" * 64
        page.source_sha256 = page.source_text_sha256 = text_sha256(page.text)
    return pages


def test_identical_page_furniture_allows_strong_source_continuation_without_dropping_content():
    pages = _furnished_continuation_pages()
    original = {number: page.to_dict() for number, page in pages.items()}
    linked = link_source_continuations(pages)
    assert linked[2].blocks[1].continuation_of == "p0001_b0001"
    proof = linked[2].metadata["continuation_bridge"]
    assert proof["kind"] == "repeated_source_furniture"
    assert len(proof["furniture_pairs"]) == 3
    assert proof["previous_trailing_ids"] == ["p0001_b0003", "p0001_b0004"]
    assert proof["current_leading_ids"] == ["p0002_b0002"]
    assert {number: page.to_dict() for number, page in pages.items()} == original
    assert all(linked[number].text == page.text for number, page in pages.items())
    assert {number: page.to_dict() for number, page in link_source_continuations(linked).items()} == {
        number: page.to_dict() for number, page in linked.items()}


@pytest.mark.parametrize("guard", ["changed_header", "changed_contact", "substantive_footer", "footer_without_contact",
    "heading", "reference", "signature", "body_header", "header_wrong_position", "footer_wrong_position",
    "header_geometry_shift", "uncertain_header", "uncertain_footer", "boundary", "different_file", "terminal_sentence"])
def test_page_furniture_never_justifies_a_false_join(guard):
    pages = _furnished_continuation_pages()
    if guard == "changed_header":
        pages[2].blocks[0].text += " — Outro Juízo"
    elif guard == "changed_contact":
        pages[2].blocks[-1].text = "Telef: 220000000; E-mail: different@example.invalid"
    elif guard == "substantive_footer":
        for page in pages.values():
            page.blocks[-1].text += "; O prazo deve ser cumprido."
    elif guard == "footer_without_contact":
        for page in pages.values():
            page.blocks.pop()
    elif guard in {"heading", "reference", "signature", "body_header"}:
        pages[2].blocks[0].role = "paragraph" if guard == "body_header" else guard
    elif guard == "header_wrong_position":
        pages[2].blocks[0].bbox = (200, 400, 400, 422)
    elif guard == "footer_wrong_position":
        pages[1].blocks[-1].bbox = (200, 300, 400, 320)
    elif guard == "header_geometry_shift":
        pages[2].blocks[0].bbox = (200, 140, 400, 162)
    elif guard == "uncertain_header":
        pages[2].blocks[0].uncertain = True
    elif guard == "uncertain_footer":
        pages[1].blocks[-1].uncertain = True
    elif guard == "boundary":
        pages[2].blocks[0].document_start = True
    elif guard == "different_file":
        pages[2].source_file_sha256 = "b" * 64
    else:
        pages[1].blocks[1].text += "."
    assert not link_source_continuations(pages)[2].continuation_from_previous


def test_external_verified_continuation_metadata_is_preserved_but_flags_do_not_prove_a_join():
    pages = _furnished_continuation_pages()
    pages[2].metadata["confirmed_continuation"] = {"reviewed": True, "evidence": "synthetic source inspection"}
    pages[2].metadata["continuation_evidence"] = {"origin": "external verified record"}
    linked = link_source_continuations(pages)
    assert linked[2].metadata["confirmed_continuation"] == pages[2].metadata["confirmed_continuation"]
    assert linked[2].metadata["continuation_evidence"] == pages[2].metadata["continuation_evidence"]
    pages[1].blocks[1].bbox = None
    pages[1].continuation_to_next = pages[2].continuation_from_previous = True
    assert not link_source_continuations(pages)[2].continuation_from_previous


@pytest.mark.parametrize("role", ["heading", "table_cell", "signature", "reference"])
def test_even_empty_semantic_structure_is_not_crossed_by_a_furniture_bridge(role):
    pages = _furnished_continuation_pages()
    extra = StructureBlock("p0002_b0005", "", role=role)
    if role == "table_cell":
        extra.table_id, extra.row, extra.col = "t1", 0, 0
    pages[2].blocks.insert(0, extra)
    assert not link_source_continuations(pages)[2].continuation_from_previous


def test_positive_source_geometry_and_syntax_produce_stable_links_without_mutating_inputs():
    pages = _continuation_pages()
    linked = link_source_continuations(pages)
    assert linked[1].continuation_to_next and linked[2].continuation_from_previous
    assert linked[2].blocks[0].continuation_of == "p0001_b0001"
    assert not pages[1].continuation_to_next
    assert pages[2].blocks[0].continuation_of is None
    assert {number: page.to_dict() for number, page in link_source_continuations(linked).items()} == {
        number: page.to_dict() for number, page in linked.items()}


@pytest.mark.parametrize("guard", ["missing_geometry", "wrong_geometry", "flags_without_geometry", "syntax_end", "syntax_start",
                                  "short_tail", "page_boundary", "block_boundary", "heading_boundary", "empty_boundary",
                                  "source_gap", "uncertain_tail", "uncertain_head", "uncertain_previous", "uncertain_current",
                                  "intervening_footer", "intervening_signature"])
def test_continuations_require_positive_evidence_and_cannot_cross_boundaries_or_uncertainty(guard):
    pages = _continuation_pages()
    tail, head = pages[1].blocks[0], pages[2].blocks[0]
    if guard in {"missing_geometry", "flags_without_geometry"}:
        tail.bbox = None
        if guard == "flags_without_geometry":
            pages[1].continuation_to_next = pages[2].continuation_from_previous = True
    elif guard == "wrong_geometry":
        tail.bbox = (30, 50, 540, 95)
    elif guard == "syntax_end":
        tail.text += "."
    elif guard == "syntax_start":
        head.text = "O dia indicado."
    elif guard == "short_tail":
        tail.text = "Deve comparecer"
    elif guard == "page_boundary":
        pages[2].document_start = True
    elif guard == "block_boundary":
        head.document_start = True
    elif guard in {"heading_boundary", "empty_boundary"}:
        pages[2].blocks.insert(0, StructureBlock("p0002_b0002", "NOVA PEÇA" if guard == "heading_boundary" else "",
                                               role="heading", document_start=True))
    elif guard == "source_gap":
        pages.pop(1)
    elif guard == "uncertain_tail":
        tail.uncertain = True
    elif guard == "uncertain_head":
        head.uncertain = True
    elif guard == "uncertain_previous":
        pages[1].uncertain = True
    elif guard == "uncertain_current":
        pages[2].uncertain = True
    elif guard in {"intervening_footer", "intervening_signature"}:
        pages[1].blocks.append(StructureBlock("p0001_b0002", "Additional retained source content.",
                                               role="footer" if guard == "intervening_footer" else "signature"))
    linked = link_source_continuations(pages)
    assert not linked[2].continuation_from_previous
    assert all(block.continuation_of is None for block in linked[2].blocks)
