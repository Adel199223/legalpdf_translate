"""Source geometry, not absolute PDF index, owns local source folios."""
from hashlib import sha256
import json
from types import SimpleNamespace
from zipfile import ZipFile

from docx import Document
import fitz
import pytest

from legalpdf_translate.docx_writer import assemble_docx, _source_bound_terminal_folios_v3
from legalpdf_translate.types import TargetLang


def source(labels, *, y=780, duplicate=False, rotation=0):
    with fitz.open() as pdf:
        for label in labels:
            page = pdf.new_page(width=595, height=842)
            page.insert_text((50, 80), "Fictional source document.")
            page.insert_text((260, y), label)
            if duplicate: page.insert_text((260, 760), label)
            page.set_rotation(rotation)
        return pdf.tobytes()


def has_page(path):
    with ZipFile(path) as package:
        return any(b"PAGE" in package.read(name) for name in package.namelist() if name.startswith("word/footer"))


def build(tmp_path, originals, targets, *, version="terminal_source_bound_folio_v3", **kwargs):
    folder = tmp_path / "pages"
    folder.mkdir()
    for number, text in enumerate(targets, 1):
        (folder / f"page_{number:04d}.txt").write_text("نص المصدر\n" + text, encoding="utf-8")
    pdf = source(originals)
    path = assemble_docx(folder, tmp_path / "out.docx", lang=TargetLang.AR, page_breaks=True,
        page_numbers=list(range(1, len(targets) + 1)), terminal_folio_policy=version,
        terminal_folio_source_pdf=pdf, terminal_folio_source_sha256=sha256(pdf).hexdigest(), **kwargs)
    return path


def test_local_folios_restart_between_distinct_documents_without_generated_counter(tmp_path):
    targets = ["الصفحة 1", "ص. 1 / 2", "ص. 2 / 2"]
    path = build(tmp_path, ["Page 1", "Page 1 / 2", "Page 2 / 2"], targets)
    assert not has_page(path)
    text = "\n".join(p.text for p in Document(path).paragraphs).replace("\u200e", "")
    assert all(label in text for label in targets)
    mapping = json.loads(path.with_suffix(".source_map.json").read_text(encoding="utf-8"))
    assert [(p["source_folio_proof"]["number"], p["source_folio_proof"]["total"]) for p in mapping["pages"]] == [(1, None), (1, 2), (2, 2)]
    assert all(p["generated_page_suppressed"] for p in mapping["pages"])
    assert all(len(p["source_folio_proof"]["source_pdf_sha256"]) == 64 for p in mapping["pages"])


@pytest.mark.parametrize("source_label,target_label", [
    ("Page 7 of 12", "الصفحة ٧ من ١٢"), ("Pag. 4 / 9", "ص. ۴ / ۹"), ("Page 23", "صفحة 23")])
def test_local_values_are_source_bound_not_reference_specific(tmp_path, source_label, target_label):
    assert not has_page(build(tmp_path, [source_label], [target_label]))


def test_source_bound_primary_map_and_counter_suppression_survive_automatic_layout(tmp_path):
    from legalpdf_translate.ordinary_auto_layout_artifacts import bind_raw_page_map, build_unreviewed_candidate, verify_unreviewed_candidate
    from legalpdf_translate.saved_docx_layout import default_decisions
    from io import BytesIO

    pdf = source(["Page 7"])
    folder = tmp_path / "pages"
    folder.mkdir()
    (folder / "page_0001.txt").write_text("نص المصدر\nص. 7", encoding="utf-8")
    path = assemble_docx(folder, tmp_path / "raw.docx", lang=TargetLang.AR, page_breaks=True,
        page_numbers=[1], terminal_folio_policy="terminal_source_bound_folio_v3",
        terminal_folio_source_pdf=pdf, terminal_folio_source_sha256=sha256(pdf).hexdigest())
    raw = path.read_bytes()
    mapping = json.loads(path.with_suffix(".source_map.json").read_text(encoding="utf-8"))
    snapshot = bind_raw_page_map(raw, mapping, source_pdf_sha256=sha256(pdf).hexdigest(), selected_pages=(1,), target_lang="AR")
    frames = [{"page_number": 1, "width_px": 595, "height_px": 842, "image_sha256": "b" * 64}]
    decisions = default_decisions(snapshot.saved_snapshot, frames)
    for choice in decisions["paragraphs"]: choice["regions"] = [{"page_number": 1, "bbox_px": [10, 10, 200, 100]}]
    evidence = {"version": "fictional_proposal_v1", "document_reviewed": False, "rendered_layout_acceptance": "not_evaluated"}
    candidate = build_unreviewed_candidate(raw, snapshot, frames, decisions, proposal_evidence=evidence)
    verify_unreviewed_candidate(raw, snapshot, frames, decisions, candidate, proposal_evidence=evidence)
    with ZipFile(BytesIO(candidate.docx_bytes)) as package:
        assert not any(b"PAGE" in package.read(name) for name in package.namelist() if name.startswith("word/footer"))
    assert "ص. 7" in "\n".join(p.text for p in Document(BytesIO(candidate.docx_bytes)).paragraphs).replace("\u200e", "")


@pytest.mark.parametrize("original,target", [("1", "ص. 1"), ("1 / 2", "ص. 1 / 2"), ("Article 1", "ص. 1"),
    ("Reference Page 1", "ص. 1"), ("Page 1", "ص. 2"), ("Page 1 / 2", "ص. 1 / 3"),
    ("Page 1", "ص. 1 / 2"), ("Page 1", "1"), ("Page 0", "ص. 0")])
def test_bare_numbers_references_changed_values_and_uncertain_labels_keep_counter(tmp_path, original, target):
    assert has_page(build(tmp_path, [original], [target]))


@pytest.mark.parametrize("mutation", ["missing_source", "changed_hash", "body_label", "duplicate", "rotated", "structured"])
def test_source_proof_requires_exact_bytes_unique_bottom_geometry_and_plain_text(mutation):
    pdf = source(["Page 1"], y=200 if mutation == "body_label" else 780,
                 duplicate=mutation == "duplicate", rotation=90 if mutation == "rotated" else 0)
    pages = [SimpleNamespace(number=1, text="نص\nص. 1", structure={} if mutation == "structured" else None)]
    digest = "a" * 64 if mutation == "changed_hash" else sha256(pdf).hexdigest()
    assert _source_bound_terminal_folios_v3(pages, None if mutation == "missing_source" else pdf, digest) == []


def test_all_selected_pages_must_have_source_grounded_folios(tmp_path):
    assert has_page(build(tmp_path, ["Page 1", "No folio"], ["ص. 1", "ص. 1"]))


def test_partial_output_retains_generated_counter_even_with_matching_source(tmp_path):
    assert has_page(build(tmp_path, ["Page 1"], ["ص. 1"], partial_output=True))


@pytest.mark.parametrize("version", [None, "terminal_labeled_folio_v1", "terminal_labeled_folio_v2"])
def test_historical_policy_keeps_original_global_index_behavior(tmp_path, version):
    assert has_page(build(tmp_path, ["Page 7"], ["Page 7"], version=version))
