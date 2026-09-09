"""Passive source evidence: no provider, native OCR or extra recognition pass."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from legalpdf_translate import document_structure as ds
from legalpdf_translate import ocr_engine as oe
from legalpdf_translate import ocr_helpers as oh
from legalpdf_translate import pdf_text_order as po
from legalpdf_translate import source_document as sd
from legalpdf_translate.types import OcrMode


@pytest.fixture(autouse=True)
def forbid_native(monkeypatch):
    monkeypatch.setattr(oe.subprocess, "run", lambda *a, **k: pytest.fail("native OCR forbidden"))


def tsv(text="Alpha Beta", *, gap=5, confidence=95):
    rows = ["level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext",
            "1\t1\t0\t0\t0\t0\t0\t0\t600\t800\t-1\t"]
    for index, word in enumerate(text.split(), 1):
        rows.append(f"5\t1\t1\t1\t1\t{index}\t{20 + (index-1)*(40+gap)}\t200\t40\t12\t{confidence}\t{word}")
    return "\n".join(rows)


def make_pdf(tmp_path):
    path = tmp_path / "source.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.insert_text((30, 40), "Tribunal Judicial", fontname="hebo")
        page.insert_text((30, 160), "A source paragraph.")
        page.insert_text((30, 730), "Telef: 123456789")
        doc.save(path)
    return path


def test_digital_evidence_is_opt_in_and_retains_all_roles(tmp_path):
    path = make_pdf(tmp_path)
    legacy = sd.extract_ordered_source_text(path, 0)
    evidence = sd.extract_ordered_source_text(path, 0, preserve_structure=True)
    assert legacy.all_blocks == () and legacy.tables == ()
    assert evidence.text == legacy.text
    source = ds.structure_from_ordered(evidence, page_number=1, source_file_sha256="a"*64)
    assert [b.role for b in source.blocks] == ["header", "paragraph", "footer"]
    assert source.blocks[0].bold
    assert all(b.bbox for b in source.blocks)
    assert source.width_pt == 600 and source.height_pt == 800


def test_reference_retains_geometric_position_only_in_structured_mode():
    def blocks():
        return [po.TextBlock(30, 180, 260, 200, "Ordinary content first."),
                po.TextBlock(30, 220, 260, 240, "Processo: 187/26.2GCBJA")]
    legacy, _ = po.order_text_blocks_with_metadata(blocks(), 600, 800)
    current, _ = po.order_text_blocks_with_metadata(blocks(), 600, 800, preserve_structure=True)
    assert legacy.index("Processo") < legacy.index("Ordinary")
    assert current.index("Ordinary") < current.index("Processo")


def test_digital_rotated_dimensions_are_source_coordinate_frame(tmp_path):
    path = tmp_path / "rotated.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.insert_text((40, 180), "Source contents remain complete.")
        page.set_rotation(90)
        doc.save(path)
    ordered = sd.extract_ordered_source_text(path, 0, preserve_structure=True)
    source = ds.structure_from_ordered(ordered, page_number=1)
    assert (source.width_pt, source.height_pt) == (600, 800)
    assert source.uncertain
    assert sd.source_page_dimensions(path, 1) == (800, 600)


@pytest.mark.parametrize("swapped", [False, True])
def test_table_requires_cell_owned_spatial_words(swapped):
    row = SimpleNamespace(cells=[(0, 0, 100, 100), (100, 0, 200, 100)])
    table = SimpleNamespace(rows=[row], bbox=(0, 0, 200, 100),
        extract=lambda: [["Beta", "Alpha"]] if swapped else [["Alpha", "Beta"]])
    page = SimpleNamespace(find_tables=lambda: SimpleNamespace(tables=[table]),
        get_text=lambda kind: [(10, 10, 40, 20, "Alpha", 0, 0, 0),
                               (110, 10, 140, 20, "Beta", 0, 0, 1)])
    tables, warnings = po._extract_tables(page, 0)
    assert bool(tables) is not swapped
    assert bool(warnings) is swapped


def test_rebind_scales_block_and_line_geometry_without_mutating_input():
    source = ds.structure_from_tesseract_tsv(tsv(), page_size=(600, 800)).to_dict()
    original = source["metadata"]["ocr_line_groups"][0]["bbox"][:]
    rebound = ds.rebind_page_structure(source, page_number=5, page_size=(300, 400))
    assert source["metadata"]["ocr_line_groups"][0]["bbox"] == original
    assert rebound.metadata["ocr_line_groups"][0]["bbox"] == [v / 2 for v in original]
    assert rebound.blocks[0].id == "p0005_b0001"


@pytest.mark.parametrize("proof", [None, "swapped"])
def test_structure_never_adopts_unproven_table_cell_associations(proof):
    cells = [{"text": "Alpha", "bbox": [0, 0, 100, 100], "row": 0, "col": 0},
             {"text": "Beta", "bbox": [100, 0, 200, 100], "row": 0, "col": 1}]
    if proof == "swapped":
        cells[0]["source_text"], cells[1]["source_text"] = "Beta", "Alpha"
    ordered = SimpleNamespace(text="Alpha Beta", page_width=600, page_height=800,
        fragmented=False, all_blocks=(po.TextBlock(0, 0, 200, 100, "Alpha Beta"),),
        tables=[{"bbox": [0, 0, 200, 100], "table_id": "t1", "cells": cells}])
    source = ds.structure_from_ordered(ordered, page_number=1)
    assert source.text == "Alpha Beta" and source.uncertain
    assert all(block.role != "table_cell" for block in source.blocks)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "900"])
def test_tsv_invalid_or_outside_geometry_rejected(bad):
    malformed = tsv().replace("\t20\t200\t40\t12\t", f"\t{bad}\t200\t40\t12\t")
    with pytest.raises(ValueError):
        ds.structure_from_tesseract_tsv(malformed)


def test_tsv_joined_columns_remain_uncertain():
    assert ds.structure_from_tesseract_tsv(tsv(gap=100)).uncertain


def test_same_winner_text_score_passes_and_tsv_binding(monkeypatch):
    monkeypatch.setattr(oe, "which", lambda _: "fake_tesseract")
    engine = oe.LocalTesseractEngine()
    calls = []
    def fake_pass(*, input_path, pass_spec, preserve_structure=False):
        calls.append((pass_spec.name, pass_spec.lang, pass_spec.psm))
        text = "Alpha  Beta\n" if len(calls) % 3 == 1 else "Gamma  Delta\n"
        result = (0, text, "")
        return result + (tsv("Alpha Beta" if "Alpha" in text else "Gamma Delta"),) if preserve_structure else result
    monkeypatch.setattr(engine, "_run_pass", fake_pass)
    monkeypatch.setattr(oe, "_text_quality_score", lambda value: .4 if "Alpha" in value else .9)
    legacy = engine.ocr_image(b"pixels", "pt_latin_default")
    original_calls = calls[:]
    calls.clear()
    current = engine.ocr_image(b"pixels", "pt_latin_default", preserve_structure=True)
    assert calls == original_calls
    assert (current.text, current.selected_pass, current.quality_score, current.attempts) == (
        legacy.text, legacy.selected_pass, legacy.quality_score, legacy.attempts)
    assert legacy.structure is None
    assert current.structure["blocks"][0]["text"] == "Gamma Delta"
    assert current.structure["metadata"]["selected_text_sha256"] == ds.text_sha256(current.text)
    assert current.structure["metadata"]["image_sha256"] == hashlib.sha256(b"pixels").hexdigest()


def test_bad_tsv_never_changes_selected_text_or_adds_calls(monkeypatch):
    monkeypatch.setattr(oe, "which", lambda _: "fake_tesseract")
    engine = oe.LocalTesseractEngine()
    calls = []
    def fake_pass(**kwargs):
        calls.append(kwargs["pass_spec"])
        return 0, "Complete chosen source text", "", tsv("Wrong text")
    monkeypatch.setattr(engine, "_run_pass", fake_pass)
    monkeypatch.setattr(oe, "_text_quality_score", lambda _: .9)
    result = engine.ocr_image(b"pixels", preserve_structure=True)
    assert result.text == "Complete chosen source text" and result.structure is None and len(calls) == 1


def test_one_recognition_command_produces_both_renderers(tmp_path, monkeypatch):
    monkeypatch.setattr(oe, "which", lambda _: "fake_tesseract")
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        Path(command[2] + ".txt").write_bytes(b"Alpha Beta\r\n")
        Path(command[2] + ".tsv").write_bytes(tsv().encode("utf-8"))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
    monkeypatch.setattr(oe.subprocess, "run", fake_run)
    result = oe.LocalTesseractEngine()._run_pass(input_path=tmp_path / "input.png",
        pass_spec=oe._LocalPassSpec("pass_a", "por+eng+fra", 6), preserve_structure=True)
    assert len(calls) == 1 and calls[0][-2:] == ["txt", "tsv"]
    assert result[1] == "Alpha Beta\r\n" and result[3] == tsv()


def test_adapter_internal_typeerror_never_redispatches():
    calls = []
    class Broken:
        def ocr_image(self, image, **kwargs):
            calls.append(kwargs)
            raise TypeError("source_type internal provider error after dispatch")
    with pytest.raises(TypeError):
        oe.invoke_ocr_image(Broken(), b"image", preserve_structure=True)
    assert len(calls) == 1


def test_legacy_adapter_compatibility_resolved_before_dispatch():
    calls = []
    class Legacy:
        def ocr_image(self, image, lang_hint=None):
            calls.append(lang_hint)
            return oe.OcrResult("source", "api", None, 6)
    result = oe.invoke_ocr_image(Legacy(), b"image", "pt", preserve_structure=True)
    assert result.text == "source" and calls == ["pt"]


def test_api_fallback_receives_no_new_structure_option():
    calls = []
    class Local:
        def ocr_image(self, image, **kwargs):
            calls.append(("local", kwargs))
            return oe.OcrResult("", "local", "unavailable", 0)
    class Api:
        def ocr_image(self, image, **kwargs):
            calls.append(("api", kwargs))
            return oe.OcrResult("complete source", "api", None, 15)
    result = oe.LocalThenApiEngine(local_engine=Local(), api_engine=Api()).ocr_image(b"image", preserve_structure=True)
    assert result.text == "complete source" and result.structure is None
    assert calls[0][1]["preserve_structure"] is True
    assert "preserve_structure" not in calls[1][1]


def test_ocr_off_neither_hashes_renders_nor_dispatches(tmp_path, monkeypatch):
    monkeypatch.setattr(sd, "source_page_identity", lambda *a: pytest.fail("identity access while off"))
    monkeypatch.setattr(oh, "render_page_png", lambda *a: pytest.fail("render while off"))
    result = sd.ocr_source_page_text(tmp_path / "missing.pdf", 1, OcrMode.OFF, object(), preserve_structure=True)
    assert result.engine == "none" and result.structure is None


def test_changed_or_recovered_text_discards_geometry_not_content():
    source = ds.structure_from_tesseract_tsv(tsv())
    source.metadata.update(selected_text_sha256=ds.text_sha256("Alpha Beta"), image_sha256=hashlib.sha256(b"pixels").hexdigest())
    result = oe.OcrResult("Recovered new text", "local", None, 18, structure=source.to_dict())
    oh._bind_ocr_structure(result, b"pixels")
    assert result.text == "Recovered new text" and result.structure is None


def test_plain_ocr_text_fallback_has_no_guessed_geometry():
    source = ds.structure_from_text("Heading\n\nA paragraph wraps\nacross lines.", page_number=1)
    assert source.uncertain and all(block.bbox is None for block in source.blocks)
