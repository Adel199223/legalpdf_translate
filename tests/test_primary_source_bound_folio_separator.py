"""Width-variant folio recognition is opt-in and still needs source proof."""
from hashlib import sha256
import json
from types import SimpleNamespace

from docx import Document
import pytest

from legalpdf_translate.docx_writer import (
    _source_bound_terminal_folios_v3, _source_bound_terminal_folios_v4,
)
from tests.test_primary_source_bound_folio import build, has_page, source


def test_v4_fullwidth_solidus_local_folios_preserve_target_characters(tmp_path):
    targets = ["ص. 1", "الصفحة 1 / 2", "الصفحة 2 ／ 2"]
    path = build(tmp_path, ["Page 1", "Page 1 / 2", "Page 2 / 2"], targets,
                 version="terminal_source_bound_folio_v4")
    assert not has_page(path)
    text = "\n".join(p.text for p in Document(path).paragraphs).replace("\u200e", "")
    assert all(target in text for target in targets)
    mapping = json.loads(path.with_suffix(".source_map.json").read_text(encoding="utf-8"))
    assert all(p["primary_folio_policy"] == "terminal_source_bound_folio_v4" for p in mapping["pages"])
    assert [(p["source_folio_proof"]["number"], p["source_folio_proof"]["total"])
            for p in mapping["pages"]] == [(1, None), (1, 2), (2, 2)]
    assert mapping["pages"][-1]["source_folio_proof"]["target_line_sha256"] == sha256(targets[-1].encode()).hexdigest()


@pytest.mark.parametrize("version", [None, "terminal_labeled_folio_v1", "terminal_labeled_folio_v2", "terminal_source_bound_folio_v3"])
def test_historical_policies_keep_fullwidth_solidus_fallback(tmp_path, version):
    assert has_page(build(tmp_path, ["Page 1 / 2"], ["الصفحة 1 ／ 2"], version=version))


@pytest.mark.parametrize("target", [
    "الصفحة 7 ／ 12", "الصفحة ٧ ／ ١٢", "ص. ۷ ／ ۱۲", "Page 7 ／ 12",
])
def test_v4_variant_does_not_depend_on_specific_local_numbers_or_digit_forms(target):
    pdf = source(["Page 7 / 12"])
    pages = [SimpleNamespace(number=1, text="Fictional body.\n" + target, structure=None)]
    assert _source_bound_terminal_folios_v3(pages, pdf, sha256(pdf).hexdigest()) == []
    result = _source_bound_terminal_folios_v4(pages, pdf, sha256(pdf).hexdigest())
    assert len(result) == 1 and (result[0]["number"], result[0]["total"]) == (7, 12)


@pytest.mark.parametrize("target", [
    "7 ／ 12", "Reference Page 7 ／ 12", "Article 7 ／ 12", "Page 7 ／ 12 extra",
    "Page 7 ／ 12\nLater body.", "Page 7 ∕ 12", "Page 7 ⁄ 12", "Page 7 \\ 12",
    "Page 7 ／／ 12", "Page 7 ／ 13", "Page 8 ／ 12", "Page 0 ／ 12",
    "Page 12 ／ 7", "Page 7 ／ 12: invoice", "Page 7 ／ 12\u200b",
])
def test_v4_nonfolios_changed_values_and_other_confusables_are_rejected(target):
    pdf = source(["Page 7 / 12"])
    pages = [SimpleNamespace(number=1, text=target, structure=None)]
    assert _source_bound_terminal_folios_v4(pages, pdf, sha256(pdf).hexdigest()) == []


@pytest.mark.parametrize("mutation", ["no_source", "changed_hash", "no_label", "body", "duplicate", "rotated", "structured", "source_variant"])
def test_v4_target_variant_cannot_substitute_for_original_source_proof(mutation):
    pdf = source(["7 / 12" if mutation == "no_label" else "Page 7 ／ 12" if mutation == "source_variant" else "Page 7 / 12"],
                 y=200 if mutation == "body" else 780, duplicate=mutation == "duplicate",
                 rotation=90 if mutation == "rotated" else 0)
    pages = [SimpleNamespace(number=1, text="Page 7 ／ 12", structure={} if mutation == "structured" else None)]
    digest = "a" * 64 if mutation == "changed_hash" else sha256(pdf).hexdigest()
    assert _source_bound_terminal_folios_v4(pages, None if mutation == "no_source" else pdf, digest) == []


def test_v4_all_selected_pages_and_complete_output_still_required(tmp_path):
    assert has_page(build(tmp_path, ["Page 7 / 12", "No source folio"],
                         ["Page 7 ／ 12", "Page 8 ／ 12"], version="terminal_source_bound_folio_v4"))


def test_v4_partial_output_keeps_generated_counter(tmp_path):
    assert has_page(build(tmp_path, ["Page 7 / 12"], ["Page 7 ／ 12"],
                         version="terminal_source_bound_folio_v4", partial_output=True))
