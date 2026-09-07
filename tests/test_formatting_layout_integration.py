"""Offline layout derivatives must never retranslate or corrupt saved evidence."""
from copy import deepcopy
import json
from pathlib import Path

import fitz
import pytest

from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.layout_integration import (
    derive_source_layout, load_rebuild_layout, prepare_layout_rebuild,
)
import legalpdf_translate.layout_integration as integration
from legalpdf_translate.formatting_support import save_translated_structure, write_json_atomic


def _case(tmp_path):
    pdf = tmp_path / "source.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.insert_text((40, 45), "Synthetic notice")
        doc.save(pdf)
    blocks = [StructureBlock(f"p0001_b{i:04d}", text, bbox=box) for i, (text, box) in enumerate([
        ("Institution", (30, 30, 240, 50)), ("Contact", (30, 65, 240, 85)),
        ("Notice", (320, 30, 565, 50)), ("Recipient", (320, 65, 565, 85)),
        ("Conditions", (30, 160, 240, 180)), ("Payment", (30, 200, 240, 230)),
        ("Explanation", (320, 160, 565, 180)), ("Obligations", (320, 200, 565, 230)),
    ], 1)]
    text = "\n".join(b.text for b in blocks)
    source = PageStructure(1, text_sha256(text), blocks, width_pt=600, height_pt=800,
                           source_file_sha256=integration._file_hash(pdf), source_text_sha256=text_sha256(text))
    pages = tmp_path / "pages"
    pages.mkdir()
    write_json_atomic(pages / "page_0001.source_structure.json", source.to_dict())
    target_rows = [{"id": b.id, "text": "Translated " + b.text} for b in blocks]
    target_text = "\n".join(b["text"] for b in target_rows)
    txt = pages / "page_0001.txt"
    txt.write_text(target_text, encoding="utf-8")
    target = save_translated_structure(path=pages / "page_0001.structure.json", source_structure=source,
                                      translated_blocks=target_rows, translated_text=target_text,
                                      translation_fingerprint="historical-model-identity")
    return pdf, source, pages, txt, target


def test_rebuild_adds_only_format_derivative_and_keeps_source_and_text(tmp_path):
    pdf, source, pages, txt, target = _case(tmp_path)
    originals = {p: p.read_bytes() for p in pages.iterdir()}
    result = prepare_layout_rebuild(pages, pdf, cache_dir=tmp_path / "cache")
    assert result["prepared_pages"] == [1]
    assert all(p.read_bytes() == data for p, data in originals.items())
    layout = load_rebuild_layout(txt, target)
    assert layout["status"] == "regions"
    assert layout["source_sha256"] == source.source_sha256


def test_layout_cache_reuses_pixel_evidence_across_target_text(tmp_path, monkeypatch):
    pdf, source, pages, txt, target = _case(tmp_path)
    first = derive_source_layout(source, pdf, cache_dir=tmp_path / "cache")
    monkeypatch.setattr(integration, "_render_source", lambda *args: pytest.fail("Cached layout must not re-render"))
    assert derive_source_layout(target, pdf, cache_dir=tmp_path / "cache") == first


def test_geometry_change_invalidates_only_layout_cache(tmp_path, monkeypatch):
    pdf, source, pages, txt, target = _case(tmp_path)
    derive_source_layout(source, pdf, cache_dir=tmp_path / "cache")
    original = integration._render_source
    calls = []
    monkeypatch.setattr(integration, "_render_source", lambda *args: (calls.append(1), original(*args))[1])
    changed = deepcopy(source.to_dict())
    changed["blocks"][0]["bbox"][1] = 28
    derive_source_layout(changed, pdf, cache_dir=tmp_path / "cache")
    assert calls == [1]
    assert "historical-model-identity" in (pages / "page_0001.structure.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("corruption", ["malformed", "translation", "geometry", "source"])
def test_untrusted_derivative_requires_review_but_preserves_text_ids(tmp_path, corruption):
    pdf, source, pages, txt, target = _case(tmp_path)
    prepare_layout_rebuild(pages, pdf)
    path = txt.with_suffix(".layout.json")
    record = json.loads(path.read_text(encoding="utf-8"))
    if corruption == "translation":
        record["translation_sha256"] = "a" * 64
    elif corruption == "geometry":
        record["layout"]["geometry_sha256"] = "a" * 64
    elif corruption == "source":
        record["source_file_sha256"] = "a" * 64
    path.write_text("invalid" if corruption == "malformed" else json.dumps(record), encoding="utf-8")
    layout = load_rebuild_layout(txt, target)
    assert layout["status"] == "needs_review" and layout["review_required"]
    assert layout["bands"] == [] and len(target["blocks"]) == 8


@pytest.mark.parametrize("missing", ["source_pdf", "source_sidecar", "wrong_pdf", "changed_role"])
def test_rebuild_never_adopts_unpaired_source_evidence(tmp_path, missing):
    pdf, source, pages, txt, target = _case(tmp_path)
    originals = {p: p.read_bytes() for p in pages.iterdir() if ".source_structure." not in p.name}
    if missing == "source_pdf":
        pdf = tmp_path / "missing.pdf"
    elif missing == "source_sidecar":
        (pages / "page_0001.source_structure.json").unlink()
    elif missing == "wrong_pdf":
        pdf = tmp_path / "unrelated.pdf"
        pdf.write_bytes(b"not the source")
    else:
        raw = source.to_dict()
        raw["blocks"][0]["role"] = "address"
        write_json_atomic(pages / "page_0001.source_structure.json", raw)
    result = prepare_layout_rebuild(pages, pdf)
    assert result["review_required_pages"] == [1]
    assert load_rebuild_layout(txt, target)["review_required"]
    assert all(p.read_bytes() == data for p, data in originals.items())


def test_legacy_rebuild_and_cancellation_do_not_extract_or_write(tmp_path, monkeypatch):
    pdf, source, pages, txt, target = _case(tmp_path)
    monkeypatch.setattr(integration, "_render_source", lambda *args: pytest.fail("No render allowed"))
    assert prepare_layout_rebuild(pages, pdf, cancelled=lambda: True)["cancelled"]
    assert not txt.with_suffix(".layout.json").exists()
    (pages / "page_0001.structure.json").unlink()
    assert prepare_layout_rebuild(pages, pdf)["legacy_pages"] == [1]
    assert not txt.with_suffix(".layout.json").exists()


def test_missing_optional_derivative_does_not_override_source_layout(tmp_path):
    pdf, source, pages, txt, target = _case(tmp_path)
    assert load_rebuild_layout(txt, target) is None
