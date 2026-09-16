"""Synthetic v2 regions/local-folios; never rendered or legal acceptance."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json

import pytest

from legalpdf_translate.formatting_support import fingerprint
from legalpdf_translate.reviewed_formatting import FormattingPageInput, ReviewedFormattingError
from legalpdf_translate.reviewed_formatting_writer import (
    ReviewedFormattingWriterError, build_reviewed_docx,
)
from tests.test_reviewed_formatting import packet, validate
from tests.test_reviewed_folios import case


def region_packet(*, columns=False, source_parts=None, target_parts=None):
    manifest, page = packet(source_parts=source_parts, target_parts=target_parts)
    _, folio_pages = case(lang="FR", groups=((1, 1),))
    metadata = deepcopy(folio_pages[0].source_structure["metadata"])
    image_hash = hashlib.sha256(page.source_image_bytes).hexdigest()
    metadata["source_page_identity"]["image_sha256"] = image_hash
    metadata["reviewed_source"]["review_image_sha256"] = image_hash
    metadata["selected_text_sha256"] = page.source_structure["source_sha256"]
    for structure in (page.source_structure, page.target_structure):
        structure["document_start"] = True
        structure["blocks"][0]["document_start"] = True
        structure["metadata"] = deepcopy(metadata)
    row = manifest["pages"][0]
    row["source_structure_sha256"] = fingerprint(page.source_structure)
    row["target_structure_sha256"] = fingerprint(page.target_structure)
    manifest.update(version="reviewed_formatting_v2", policy="source_page_matched_reviewed_regions_v2",
                    folio_policy="reviewed_document_local_folios_v1",
                    document_groups=[{"start_page": 1, "end_page": 1}])
    ids = [f["rendering_id"] for f in row["fragments"]]
    row["folio_fragment_id"] = ids[-1]
    body = [{"kind": "paragraph", "fragment_id": rid} for rid in ids[1:3]]
    if columns:
        row["fragments"][1]["bbox_px"] = [40, 150, 270, 400]
        row["fragments"][2]["bbox_px"] = [310, 150, 550, 400]
        body = [{"kind": "table", "table_id": "p0001_t0001", "column_widths": [50, 50],
                 "rows": [{"cells": [{"fragment_ids": [ids[1]]}, {"fragment_ids": [ids[2]]}]}]}]
    row["region_layout"] = {"version": "reviewed_region_layout_v1", "header": [ids[0]],
                            "body": body, "footer": ids[3:]}
    return manifest, page


def split_footer_packet(*, source_lines=None):
    original, page = packet()
    parts = [[getattr(page, side + "_structure")["blocks"][0]["text"][slice(*f[side + "_range"])]
              for f in original["pages"][0]["fragments"]] for side in ("source", "target")]
    if source_lines is not None:
        parts[0][3] = "".join(source_lines)
        parts[1][3] = "".join("Adresse exemple\n" for _ in source_lines)
    manifest, page = region_packet(source_parts=parts[0], target_parts=parts[1])
    row = manifest["pages"][0]
    template = row["fragments"][3]
    starts = [template[side + "_range"][0] for side in ("source", "target")]
    split = []
    for index, lines in enumerate(zip(*(p[3].splitlines(keepends=True) for p in parts))):
        fragment = deepcopy(template)
        fragment["rendering_id"] = f"p0001_f{index + 4:04d}"
        fragment["bbox_px"] = [40, 720 + index * 12, 490, 730 + index * 12]
        for side_index, side in enumerate(("source", "target")):
            fragment[side + "_range"] = [starts[side_index], starts[side_index] + len(lines[side_index])]
            fragment[side + "_text_sha256"] = hashlib.sha256(lines[side_index].encode()).hexdigest()
            starts[side_index] += len(lines[side_index])
        split.append(fragment)
    folio = row["fragments"][-1]
    folio["rendering_id"] = f"p0001_f{len(split) + 4:04d}"
    row["fragments"][3:] = [*split, folio]
    row["folio_fragment_id"] = folio["rendering_id"]
    row["region_layout"]["footer"] = [f["rendering_id"] for f in row["fragments"][3:]]
    return manifest, page


def test_v2_split_address_and_contact_footer_remains_editable_without_text_changes():
    manifest, page = split_footer_packet()
    before = deepcopy((manifest, page))
    projection = validate(manifest, page)
    footers = [f for f in projection.pages[0].fragments if f.role == "footer"]
    assert len(footers) == 2
    assert "".join(f.source_text for f in projection.pages[0].fragments) == page.source_structure["blocks"][0]["text"]
    assert "".join(f.target_text for f in projection.pages[0].fragments) == page.target_structure["blocks"][0]["text"]
    built = build_reviewed_docx(projection)
    assert built.docx_bytes[:2] == b"PK"
    assert (manifest, page) == before


@pytest.mark.parametrize("lines", [
    ["Largo do Exemplo - 1234-567 Exemplo\n"],
    ["Deve comparecer no prazo de 10 dias.\n", "Telef: 123456789\n"],
    ["Rua Exemplo, artigo 5.\n", "Telef: 123456789\n"],
    ["Nome Exemplo\n", "Telef: 123456789\n"],
    ["Rua " + "x" * 590 + "\n", "Telef: 123456789\n"],
    ["Rua Exemplo\n"] * 4 + ["Telef: 123456789\n"],
])
def test_v2_grouped_footer_keeps_complete_contact_grammar_and_limits(lines):
    manifest, page = split_footer_packet(source_lines=lines)
    with pytest.raises(ReviewedFormattingError, match="unsupported_footer_assertion"):
        validate(manifest, page)


@pytest.mark.parametrize("change", ["above_bottom_band", "missing_owner", "body_owner", "reordered", "overlap"])
def test_v2_split_footer_requires_bottom_geometry_and_exact_footer_ownership(change):
    manifest, page = split_footer_packet()
    row = manifest["pages"][0]
    if change == "above_bottom_band":
        row["fragments"][3]["bbox_px"] = [40, 650, 490, 660]
    elif change == "missing_owner":
        row["region_layout"]["footer"].pop(0)
    elif change == "body_owner":
        rid = row["region_layout"]["footer"].pop(0)
        row["region_layout"]["body"].append({"kind": "paragraph", "fragment_id": rid})
    elif change == "reordered":
        row["region_layout"]["footer"][:2] = reversed(row["region_layout"]["footer"][:2])
    elif change == "overlap":
        row["fragments"][4]["bbox_px"] = row["fragments"][3]["bbox_px"][:]
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def test_v1_split_footer_does_not_acquire_collective_contact_semantics():
    manifest, page = split_footer_packet()
    manifest.update(version="reviewed_formatting_v1", policy="source_page_matched_reviewed_v1")
    manifest.pop("folio_policy")
    manifest.pop("document_groups")
    manifest["pages"][0].pop("region_layout")
    manifest["pages"][0].pop("folio_fragment_id")
    with pytest.raises(ReviewedFormattingError, match="unsupported_footer_assertion"):
        validate(manifest, page)


@pytest.mark.parametrize("columns", [False, True])
def test_v2_projection_binds_regions_groups_and_unchanged_text(columns):
    manifest, page = region_packet(columns=columns)
    before = deepcopy((manifest, page))
    projection = validate(manifest, page)
    assert projection.version == "reviewed_formatting_v2"
    assert json.loads(projection.document_groups_json) == manifest["document_groups"]
    assert json.loads(projection.pages[0].region_layout_json) == manifest["pages"][0]["region_layout"]
    assert projection.pages[0].folio_fragment_id == "p0001_f0005"
    assert projection.rendered_layout_acceptance == "not_evaluated"
    assert (manifest, page) == before


@pytest.mark.parametrize("change", [
    lambda m: m.pop("document_groups"),
    lambda m: m.update(folio_policy="auto_renumber"),
    lambda m: m["pages"][0].update(folio_fragment_id=None),
    lambda m: m["pages"][0]["region_layout"]["body"].pop(),
    lambda m: m["pages"][0]["region_layout"]["footer"].reverse(),
    lambda m: m["pages"][0]["region_layout"]["header"].append("p0001_f0002"),
])
def test_v2_rejects_unbound_regions_and_folios(change):
    manifest, page = region_packet()
    change(manifest)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def test_v1_cannot_silently_acquire_v2_semantics():
    manifest, page = region_packet(columns=True)
    manifest["version"] = "reviewed_formatting_v1"
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)
    original, original_page = packet()
    projection = validate(original, original_page)
    assert projection.version == "reviewed_formatting_v1"
    assert projection.document_groups_json is None
    assert projection.pages[0].region_layout_json is None


@pytest.mark.parametrize("kind", ["groups", "folio_policy", "regions", "folio_id"])
def test_v1_writer_rejects_unversioned_v2_fields(kind):
    manifest, page = packet()
    projection = validate(manifest, page)
    if kind == "groups":
        projection = replace(projection, document_groups_json=b"[]")
    elif kind == "folio_policy":
        projection = replace(projection, folio_policy="reviewed_document_local_folios_v1")
    else:
        field, value = (("region_layout_json", b"{}") if kind == "regions"
                        else ("folio_fragment_id", "p0001_f0005"))
        projection = replace(projection, pages=(replace(projection.pages[0], **{field: value}),))
    with pytest.raises(ReviewedFormattingWriterError):
        build_reviewed_docx(projection)


@pytest.mark.parametrize("field,value", [("folio_fragment_id", None), ("region_layout_json", b"{}")])
def test_v2_writer_does_not_trust_forged_dataclass(field, value):
    manifest, page = region_packet()
    projection = validate(manifest, page)
    forged_page = replace(projection.pages[0], **{field: value})
    with pytest.raises(ReviewedFormattingWriterError):
        build_reviewed_docx(replace(projection, pages=(forged_page,)))


def grouped_packet(lang="AR", *, target_folios=None):
    groups, originals = case(lang=lang, target_folios=target_folios)
    base, image_page = packet()
    image_hash = hashlib.sha256(image_page.source_image_bytes).hexdigest()
    base.update(version="reviewed_formatting_v2", policy="source_page_matched_reviewed_regions_v2",
                folio_policy="reviewed_document_local_folios_v1", document_groups=groups,
                target_lang=lang, full_case_pages=list(range(1, 10)), pages=[])
    pages = []
    for number, original in enumerate(originals, 1):
        source, target = original.source_structure, original.target_structure
        for structure in (source, target):
            structure["metadata"]["source_page_identity"]["image_sha256"] = image_hash
            structure["metadata"]["reviewed_source"]["review_image_sha256"] = image_hash
        page = FormattingPageInput(source, target, fingerprint(["commit", number]),
                                   fingerprint(["bundle", number]), image_page.source_image_bytes)
        fragments = []
        for f in original.fragments:
            source_text = source["blocks"][0]["text"][slice(*f.source_range)]
            target_text = target["blocks"][0]["text"][slice(*f.target_range)]
            fragments.append(dict(rendering_id=f.rendering_id, parent_block_id=f.parent_block_id,
                source_range=list(f.source_range), target_range=list(f.target_range),
                source_text_sha256=hashlib.sha256(source_text.encode()).hexdigest(),
                target_text_sha256=hashlib.sha256(target_text.encode()).hexdigest(),
                role=f.role, alignment="right" if lang == "AR" else "left", bold=False, italic=False,
                bbox_px=list(f.bbox_px), review_note="Fictional explicitly reviewed folio region."))
        base["pages"].append(dict(page_number=number, commit_file_sha256=page.commit_file_sha256,
            bundle_sha256=page.bundle_sha256, source_structure_sha256=fingerprint(source),
            target_structure_sha256=fingerprint(target), source_image_sha256=image_hash,
            image_size_px=[600, 840], frame={"origin": "top_left", "units": "pixel",
                "page_size_pt": [595.276, 841.89], "paper_size_basis": "a4_assumed"},
            fragments=fragments, folio_fragment_id=original.folio_fragment_id,
            region_layout={"version": "reviewed_region_layout_v1", "header": [],
                "body": [{"kind": "paragraph", "fragment_id": fragments[0]["rendering_id"]}],
                "footer": [original.folio_fragment_id]}))
        pages.append(page)
    return base, pages


@pytest.mark.parametrize("lang", ["AR", "FR", "EN"])
def test_full_case_local_numbering_v2_integration(lang):
    manifest, pages = grouped_packet(lang)
    projection = validate(manifest, pages[0], pages=pages, target_lang=lang)
    assert len(projection.pages) == 9
    assert [page.fragments[-1].source_text.strip() for page in projection.pages] == [
        "Pág. 1 de 2", "Pág. 2 de 2", "1 / 1", "1 / 6", "2 / 6", "3 / 6", "4 / 6", "5 / 6", "6 / 6"]


def test_full_arabic_case_keeps_abbreviated_folios_and_wrapped_local_numbers():
    manifest, pages = grouped_packet(target_folios={
        n: f"ص. \u2066[[{n}]]\u2069 من \u2066[[2]]\u2069" for n in (1, 2)})
    before = deepcopy((manifest, pages))
    projection = validate(manifest, pages[0], pages=pages, target_lang="AR")
    assert len(projection.pages) == 9
    assert build_reviewed_docx(projection).docx_bytes[:2] == b"PK"
    assert (manifest, pages) == before
