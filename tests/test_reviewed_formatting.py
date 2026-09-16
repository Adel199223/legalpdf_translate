"""Synthetic, offline tests; no private document or render/certification claims."""
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import hashlib
import io
import json

from PIL import Image
import pytest

from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.formatting_support import fingerprint
from legalpdf_translate.reviewed_formatting import (
    FormattingPageInput, ReviewedFormattingError, validate_reviewed_formatting,
)


def packet(*, source_parts=None, target_parts=None):
    source_parts = source_parts or [
        "Tribunal Judicial da Comarca de Exemplo\nJuízo Local Criminal de Exemplo\n\n",
        "Decide-se manter o prazo de 10 dias.\n\n",
        "A Juiz de Direito\nNome Exemplo\n\n",
        "Largo do Exemplo - 1234-567 Exemplo\nTelef: 123456789\n", "1 / 1",
    ]
    target_parts = target_parts or [
        "Tribunal judiciaire d’Exemple\nDivision pénale locale\n\n",
        "Le délai de 10 jours est maintenu.\n\n",
        "Le juge\nNome Exemplo\n\n",
        "Largo do Exemplo - 1234-567 Exemplo\nTél. : 123456789\n", "1 / 1",
    ]
    raster = io.BytesIO()
    Image.new("RGB", (600, 840), "white").save(raster, format="PNG")
    image_bytes = raster.getvalue()
    image_hash = hashlib.sha256(image_bytes).hexdigest()
    source_text, target_text = "".join(source_parts), "".join(target_parts)
    source = PageStructure(
        page_number=1, source_sha256=text_sha256(source_text),
        source_text_sha256=text_sha256(source_text), source_file_sha256="a" * 64,
        uncertain=True, provenance="reviewed_image_source_v1",
        blocks=[StructureBlock(id="p0001_b100000001", text=source_text, uncertain=True)],
        metadata={"source_page_identity": {"source_file_sha256": "a" * 64,
            "image_sha256": image_hash, "source_type": "browser_pdf_image",
            "paper_size_basis": "a4_assumed"},
            "reviewed_source": {"geometry_status": "not_verified", "review_image_sha256": image_hash}},
    ).to_dict()
    target = deepcopy(source)
    target["blocks"][0]["text"] = target_text
    target["translation_sha256"] = text_sha256(target_text)
    page = FormattingPageInput(source, target, "b" * 64, "c" * 64, image_bytes)
    boxes = [[20, 20, 550, 70], [40, 150, 550, 400], [40, 500, 250, 560],
             [40, 775, 500, 810], [500, 815, 550, 835]]
    fragments = []
    source_start = target_start = 0
    for index, (left, right, role, bbox) in enumerate(zip(
            source_parts, target_parts, ["header", "body", "signature", "footer", "folio"], boxes), 1):
        fragments.append({"rendering_id": f"p0001_f{index:04d}",
            "parent_block_id": "p0001_b100000001",
            "source_range": [source_start, source_start + len(left)],
            "target_range": [target_start, target_start + len(right)],
            "source_text_sha256": text_sha256(left), "target_text_sha256": text_sha256(right),
            "role": role, "alignment": "left", "bold": False, "italic": False, "bbox_px": bbox,
            "review_note": "Synthetic source-image region reviewed for this fragment only."})
        source_start += len(left)
        target_start += len(right)
    manifest = {"version": "reviewed_formatting_v1", "policy": "source_page_matched_reviewed_v1",
        "boundary_policy": "whole_lines_trailing_separators_v1", "offset_unit": "unicode_codepoint",
        "reviewer_kind": "ai_test_review",
        "source_file_sha256": "a" * 64, "target_lang": "FR", "preferences_sha256": "d" * 64,
        "full_case_pages": [1], "pages": [{"page_number": 1,
            "commit_file_sha256": page.commit_file_sha256, "bundle_sha256": page.bundle_sha256,
            "source_structure_sha256": fingerprint(source), "target_structure_sha256": fingerprint(target),
            "source_image_sha256": image_hash, "image_size_px": [600, 840],
            "frame": {"origin": "top_left", "units": "pixel", "page_size_pt": [595.276, 841.89],
                      "paper_size_basis": "a4_assumed"}, "fragments": fragments}]}
    return manifest, page


def validate(manifest, page, **kwargs):
    raw = json.dumps(manifest, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    options = dict(expected_manifest_sha256=hashlib.sha256(raw).hexdigest(), pages=[page],
                   source_file_sha256="a" * 64, target_lang="FR", preferences_sha256="d" * 64)
    options.update(kwargs)
    return validate_reviewed_formatting(raw, **options)


def rebind(manifest, page):
    row = manifest["pages"][0]
    row["source_structure_sha256"] = fingerprint(page.source_structure)
    row["target_structure_sha256"] = fingerprint(page.target_structure)
    for fragment in row["fragments"]:
        for side in ("source", "target"):
            original = getattr(page, side + "_structure")["blocks"][0]["text"]
            start, end = fragment[side + "_range"]
            fragment[side + "_text_sha256"] = text_sha256(original[start:end])


def test_valid_detached_projection_preserves_every_character_and_uncertainty():
    manifest, page = packet()
    before = deepcopy((manifest, page.source_structure, page.target_structure))
    result = validate(manifest, page)
    projected = result.pages[0]
    assert result.policy == "source_page_matched_reviewed_v1"
    assert result.rendered_layout_acceptance == "not_evaluated"
    assert result.rendered_page_count is None
    assert projected.source_uncertain and projected.geometry_status == "not_verified"
    assert "".join(f.source_text for f in projected.fragments) == page.source_structure["blocks"][0]["text"]
    assert "".join(f.target_text for f in projected.fragments) == page.target_structure["blocks"][0]["text"]
    assert json.loads(projected.source_structure_json) == page.source_structure
    assert json.loads(projected.target_structure_json) == page.target_structure
    assert (manifest, page.source_structure, page.target_structure) == before
    with pytest.raises(FrozenInstanceError):
        result.policy = "flow"
    manifest["pages"][0]["fragments"][0]["bbox_px"][0] = 999
    page.source_structure["blocks"][0]["text"] = "mutated later"
    assert projected.fragments[0].bbox_px[0] == 20
    assert json.loads(projected.source_structure_json)["blocks"][0]["text"] != "mutated later"


@pytest.mark.parametrize("change", [
    lambda m: m.update(version="reviewed_formatting_v2"),
    lambda m: m.update(policy="flow"),
    lambda m: m.update(boundary_policy="arbitrary_offsets"),
    lambda m: m.update(reviewer_kind="human_certified"),
    lambda m: m.update(source_file_sha256="e" * 64),
    lambda m: m.update(target_lang="AR"),
    lambda m: m.update(preferences_sha256="e" * 64),
    lambda m: m.update(full_case_pages=[2]),
    lambda m: m.update(full_case_pages=[True]),
    lambda m: m.update(rendered_layout_acceptance="passed"),
    lambda m: m["pages"][0].update(page_number=2),
    lambda m: m["pages"][0].update(commit_file_sha256="e" * 64),
    lambda m: m["pages"][0].update(bundle_sha256="e" * 64),
    lambda m: m["pages"][0].update(source_structure_sha256="e" * 64),
    lambda m: m["pages"][0].update(target_structure_sha256="e" * 64),
    lambda m: m["pages"][0].update(source_image_sha256="e" * 64),
    lambda m: m["pages"][0].update(image_size_px=[601, 840]),
    lambda m: m["pages"][0]["frame"].update(origin="bottom_left"),
    lambda m: m["pages"][0]["frame"].update(units="point"),
    lambda m: m["pages"][0]["frame"].update(page_size_pt=[600, 840]),
    lambda m: m["pages"][0]["frame"].update(paper_size_basis="ocr_verified"),
])
def test_wrong_schema_or_binding_rejected(change):
    manifest, page = packet()
    change(manifest)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


@pytest.mark.parametrize("change", [
    lambda f: f.update(rendering_id="p0002_f0001"),
    lambda f: f.update(parent_block_id="p0001_b9999"),
    lambda f: f.update(source_range=[1, f["source_range"][1]]),
    lambda f: f.update(target_range=[0, f["target_range"][1] - 1]),
    lambda f: f.update(source_range=[False, f["source_range"][1]]),
    lambda f: f.update(source_text_sha256="e" * 64),
    lambda f: f.update(target_text_sha256="e" * 64),
    lambda f: f.update(role="table"),
    lambda f: f.update(alignment="auto"),
    lambda f: f.update(bbox_px=[0, 0, 600, 840]),
    lambda f: f.update(bbox_px=[20, 220, 550, 250]),
    lambda f: f.update(bbox_px=[20, 20, 601, 70]),
    lambda f: f.update(bbox_px=[20, 20, 10, 70]),
    lambda f: f.update(bbox_px=[True, 20, 550, 70]),
    lambda f: f.update(review_note=""),
    lambda f: f.update(alias_of="p0001_f0002"),
    lambda f: f.update(generated_page_number=True),
])
def test_invalid_fragment_rejected(change):
    manifest, page = packet()
    change(manifest["pages"][0]["fragments"][0])
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


@pytest.mark.parametrize("kind", ["reverse", "duplicate", "drop", "overlap", "intra_line", "lost_separator"])
def test_partition_coverage_and_order_rejected_even_with_rebound_slice_hashes(kind):
    manifest, page = packet()
    fragments = manifest["pages"][0]["fragments"]
    if kind == "reverse":
        fragments.reverse()
    elif kind == "duplicate":
        fragments.insert(1, deepcopy(fragments[0]))
    elif kind == "drop":
        fragments.pop()
    elif kind == "overlap":
        fragments[1]["source_range"][0] -= 1
    else:
        offset = 8 if kind == "intra_line" else fragments[0]["source_range"][1] - 1
        fragments[0]["source_range"][1] = offset
        fragments[1]["source_range"][0] = offset
    rebind(manifest, page)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


@pytest.mark.parametrize("source_parts", [
    ["Tribunal [[Judicial\n", "da Comarca]]\n", "Assinatura\n", "Telef: 123456789\n", "1 / 1"],
    ["Tribunal \u2067Judicial\n", "da Comarca\u2069\n", "Assinatura\n", "Telef: 123456789\n", "1 / 1"],
    ["Tribunal \u202bJudicial\n", "da Comarca\u202c\n", "Assinatura\n", "Telef: 123456789\n", "1 / 1"],
    ["Tribunal Judicial\n", "\u0301Texto\n", "Assinatura\n", "Telef: 123456789\n", "1 / 1"],
    ["Tribunal Judicial\n", "\u200dTexto\n", "Assinatura\n", "Telef: 123456789\n", "1 / 1"],
])
def test_unsafe_line_boundary_inside_wrapper_bidi_or_combining_context_rejected(source_parts):
    manifest, page = packet(source_parts=source_parts)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def test_crlf_complete_graphemes_and_balanced_tokens_supported():
    manifest, page = packet()
    source_parts = [page.source_structure["blocks"][0]["text"][slice(*f["source_range"])]
                    for f in manifest["pages"][0]["fragments"]]
    target_parts = [page.target_structure["blocks"][0]["text"][slice(*f["target_range"])]
                    for f in manifest["pages"][0]["fragments"]]
    target_parts[1] = "Texte [[Cafe\u0301]] \u2067نص\u2069 👩\u200d⚖️ 🇫🇷.\n\n"
    manifest, page = packet(source_parts=[s.replace("\n", "\r\n") for s in source_parts],
                            target_parts=[s.replace("\n", "\r\n") for s in target_parts])
    assert validate(manifest, page).pages[0].fragments[1].target_text == target_parts[1].replace("\n", "\r\n")
    fragments = manifest["pages"][0]["fragments"]
    cut = fragments[0]["source_range"][1] - 1
    fragments[0]["source_range"][1] = cut
    fragments[1]["source_range"][0] = cut
    rebind(manifest, page)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


@pytest.mark.parametrize("role,index,box", [
    ("header", 1, [40, 100, 550, 140]),
    ("footer", 1, [40, 750, 550, 780]),
    ("footer", 3, [40, 500, 550, 530]),
    ("folio", 1, [40, 800, 550, 820]),
])
def test_operating_prose_or_wrong_region_cannot_be_furniture(role, index, box):
    manifest, page = packet()
    manifest["pages"][0]["fragments"][index].update(role=role, bbox_px=box)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def test_original_source_geometry_and_target_metadata_cannot_be_silently_changed():
    manifest, page = packet()
    page.target_structure["uncertain"] = False
    rebind(manifest, page)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def test_physical_raster_and_manifest_hashes_required():
    manifest, page = packet()
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page, expected_manifest_sha256="e" * 64)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, replace(page, source_image_bytes=page.source_image_bytes + b"changed"))


def test_duplicate_json_keys_rejected():
    manifest, page = packet()
    raw = json.dumps(manifest).replace('"version": "reviewed_formatting_v1"',
        '"version": "reviewed_formatting_v1", "version": "reviewed_formatting_v1"').encode()
    with pytest.raises(ReviewedFormattingError):
        validate_reviewed_formatting(raw, expected_manifest_sha256=hashlib.sha256(raw).hexdigest(),
            pages=[page], source_file_sha256="a" * 64, target_lang="FR", preferences_sha256="d" * 64)


@pytest.mark.parametrize("key,value", [
    ("role", []), ("alignment", []), ("bold", 1), ("italic", "false"),
    ("bbox_px", None), ("review_note", None), ("source_range", [0, 1.5]),
])
def test_malformed_fragment_values_raise_content_free_validation_error(key, value):
    manifest, page = packet()
    manifest["pages"][0]["fragments"][0][key] = value
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


@pytest.mark.parametrize("key,value", [("target_lang", []), ("preferences_sha256", None),
                                        ("pages", []), ("source_file_sha256", True)])
def test_malformed_api_values_fail_closed(key, value):
    manifest, page = packet()
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page, **{key: value})


@pytest.mark.parametrize("tail", ["[[unterminated", "]]", "\u2069", "\u2067unclosed", "\u202c", "x\ry"])
def test_unbalanced_target_scopes_and_lone_cr_rejected(tail):
    manifest, page = packet()
    page.target_structure["blocks"][0]["text"] += tail
    page.target_structure["translation_sha256"] = text_sha256(page.target_structure["blocks"][0]["text"])
    manifest["pages"][0]["fragments"][-1]["target_range"][1] += len(tail)
    rebind(manifest, page)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def test_same_dimension_wrong_raster_cannot_be_rebound_without_original_source_identity():
    manifest, page = packet()
    data = io.BytesIO()
    Image.new("RGB", (600, 840), "black").save(data, format="PNG")
    page = replace(page, source_image_bytes=data.getvalue())
    manifest["pages"][0]["source_image_sha256"] = hashlib.sha256(page.source_image_bytes).hexdigest()
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def test_not_an_image_rejected_even_if_all_hashes_coherently_rebound():
    manifest, page = packet()
    page = replace(page, source_image_bytes=b"not a PNG")
    raster_hash = hashlib.sha256(page.source_image_bytes).hexdigest()
    for structure in (page.source_structure, page.target_structure):
        structure["metadata"]["source_page_identity"]["image_sha256"] = raster_hash
        structure["metadata"]["reviewed_source"]["review_image_sha256"] = raster_hash
    manifest["pages"][0]["source_image_sha256"] = raster_hash
    rebind(manifest, page)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def test_two_original_parents_each_preserve_their_own_text_and_implicit_separator():
    manifest, page = packet()
    first = manifest["pages"][0]["fragments"][0]
    for side in ("source", "target"):
        structure = getattr(page, side + "_structure")
        original = structure["blocks"][0]
        cut = first[side + "_range"][1]
        # The original block boundary owns one existing separator newline.
        left, right = deepcopy(original), deepcopy(original)
        left["text"] = original["text"][:cut - 1]
        right["id"] = "p0001_b100000002"
        right["text"] = original["text"][cut:]
        structure["blocks"] = [left, right]
        first[side + "_range"][1] -= 1
        first[side + "_text_sha256"] = text_sha256(left["text"])
        for fragment in manifest["pages"][0]["fragments"][1:]:
            fragment["parent_block_id"] = right["id"]
            fragment[side + "_range"] = [n - cut for n in fragment[side + "_range"]]
    manifest["pages"][0]["source_structure_sha256"] = fingerprint(page.source_structure)
    manifest["pages"][0]["target_structure_sha256"] = fingerprint(page.target_structure)
    result = validate(manifest, page).pages[0]
    assert result.original_parent_separator == "\n"
    for side in ("source", "target"):
        originals = getattr(page, side + "_structure")["blocks"]
        reconstructed = result.original_parent_separator.join(
            "".join(getattr(fragment, side + "_text") for fragment in result.fragments
                    if fragment.parent_block_id == original["id"]) for original in originals)
        assert reconstructed == "\n".join(original["text"] for original in originals)


def two_page_packet(*, target_parts=None):
    manifest, original = packet(target_parts=target_parts)
    inputs, rows = [], []
    for number in (1, 2):
        current_manifest, page = packet(target_parts=target_parts)
        for structure in (page.source_structure, page.target_structure):
            structure["page_number"] = number
            structure["blocks"][0]["id"] = f"p{number:04d}_b100000001"
            structure["blocks"][0]["text"] = structure["blocks"][0]["text"][:-5] + f"{number} / 2"
        source_hash = text_sha256(page.source_structure["blocks"][0]["text"])
        for structure in (page.source_structure, page.target_structure):
            structure["source_sha256"] = structure["source_text_sha256"] = source_hash
        page.target_structure["translation_sha256"] = text_sha256(page.target_structure["blocks"][0]["text"])
        page = replace(page, commit_file_sha256=text_sha256(f"commit{number}"),
                       bundle_sha256=text_sha256(f"bundle{number}"))
        row = current_manifest["pages"][0]
        row.update(page_number=number, commit_file_sha256=page.commit_file_sha256, bundle_sha256=page.bundle_sha256)
        for index, fragment in enumerate(row["fragments"], 1):
            fragment.update(rendering_id=f"p{number:04d}_f{index:04d}",
                            parent_block_id=f"p{number:04d}_b100000001")
        rebind(current_manifest, page)
        rows.append(row)
        inputs.append(page)
    manifest.update(full_case_pages=[1, 2], pages=rows)
    return manifest, inputs


def test_two_pages_keep_distinct_sections_and_original_target_header_variants():
    manifest, inputs = two_page_packet()
    second = inputs[1].target_structure
    second["blocks"][0]["text"] = second["blocks"][0]["text"].replace("Tribunal", "TRIBUNAL", 1)
    second["translation_sha256"] = text_sha256(second["blocks"][0]["text"])
    row = manifest["pages"][1]
    row["target_structure_sha256"] = fingerprint(second)
    first_fragment = row["fragments"][0]
    first_fragment["target_text_sha256"] = text_sha256(second["blocks"][0]["text"][slice(*first_fragment["target_range"])])
    result = validate(manifest, inputs[0], pages=inputs)
    assert [p.section_index for p in result.pages] == [0, 1]
    assert result.pages[0].fragments[0].target_text.startswith("Tribunal")
    assert result.pages[1].fragments[0].target_text.startswith("TRIBUNAL")
    assert result.rendered_page_count is None and result.layout_review_required


def test_page_order_or_duplicate_original_commit_rejected():
    manifest, inputs = two_page_packet()
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, inputs[0], pages=inputs[::-1])
    inputs[1] = replace(inputs[1], commit_file_sha256=inputs[0].commit_file_sha256)
    manifest["pages"][1]["commit_file_sha256"] = inputs[0].commit_file_sha256
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, inputs[0], pages=inputs)


def test_digital_signature_may_precede_header_and_explicit_styles_are_preserved():
    manifest, page = packet(source_parts=["Assinado em 23-06-2026, por\nNome Exemplo, Juiz de Direito\n",
        "Tribunal Judicial da Comarca de Exemplo\nJuízo Local Criminal de Exemplo\n",
        "Decide-se manter o prazo.\n", "Largo do Exemplo\nTelef: 123456789\n", "1 / 1"],
        target_parts=["Signé le 23-06-2026, par\nNome Exemplo, Le juge\n",
        "Tribunal judiciaire\nDivision pénale locale\n", "Le délai est maintenu.\n",
        "Largo do Exemplo\nTél. : 123456789\n", "1 / 1"])
    fragments = manifest["pages"][0]["fragments"]
    fragments[0].update(role="signature", bbox_px=[10, 10, 300, 35], italic=True)
    fragments[1].update(role="header", bbox_px=[30, 40, 550, 80], bold=True)
    fragments[2].update(role="body")
    projected = validate(manifest, page).pages[0].fragments
    assert projected[0].role == "signature" and projected[0].italic
    assert projected[1].role == "header" and projected[1].bold
    assert page.source_structure["blocks"][0]["bold"] is False


def test_contact_footer_and_literal_folio_may_share_disjoint_bottom_band():
    manifest, page = packet()
    fragments = manifest["pages"][0]["fragments"]
    fragments[-2]["bbox_px"] = [180, 805, 450, 830]
    fragments[-1]["bbox_px"] = [520, 810, 550, 825]
    projected = validate(manifest, page).pages[0].fragments
    assert projected[-2].bbox_px == (180, 805, 450, 830)
    assert projected[-1].bbox_px == (520, 810, 550, 825)
    assert projected[-1].source_text == projected[-1].target_text == "1 / 1"


@pytest.mark.parametrize("role,box", [
    ("folio", [440, 810, 550, 825]),  # actual 2-D overlap
    ("folio", [520, 750, 550, 790]),  # earlier, different vertical band
    ("body", [520, 810, 550, 825]),   # not an admitted furniture exception
])
def test_same_band_exception_cannot_cover_overlap_reordering_or_body(role, box):
    manifest, page = packet()
    fragments = manifest["pages"][0]["fragments"]
    fragments[-2]["bbox_px"] = [180, 805, 450, 830]
    fragments[-1].update(role=role, bbox_px=box)
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)


def actual_size_footer_packet():
    """Synthetic text/raster with the actual reviewed FR coordinate frame."""
    manifest, page = packet()
    raster = io.BytesIO()
    Image.new("RGB", (1191, 1684), "white").save(raster, format="PNG")
    page = replace(page, source_image_bytes=raster.getvalue())
    image_hash = hashlib.sha256(page.source_image_bytes).hexdigest()
    for structure in (page.source_structure, page.target_structure):
        structure["metadata"]["source_page_identity"]["image_sha256"] = image_hash
        structure["metadata"]["reviewed_source"]["review_image_sha256"] = image_hash
    row = manifest["pages"][0]
    row.update(source_image_sha256=image_hash, image_size_px=[1191, 1684])
    fragments = row["fragments"]
    fragments[0]["bbox_px"] = [40, 40, 1150, 140]
    fragments[1]["bbox_px"] = [40, 300, 1150, 800]
    fragments[2].update(role="body", bbox_px=[40, 900, 1150, 1590])
    fragments[3]["bbox_px"] = [393, 1604, 812, 1638]
    fragments[4]["bbox_px"] = [1049, 1615, 1085, 1634]
    rebind(manifest, page)
    return manifest, page


def test_actual_size_contained_folio_keeps_truthful_coordinates():
    manifest, page = actual_size_footer_packet()
    result = validate(manifest, page).pages[0]
    assert result.image_size_px == (1191, 1684)
    assert result.fragments[-2].bbox_px == (393, 1604, 812, 1638)
    assert result.fragments[-1].bbox_px == (1049, 1615, 1085, 1634)


@pytest.mark.parametrize("box", [
    [1049, 1348, 1085, 1634],  # overlaps the earlier wide body, not the footer
    [1049, 1600, 1085, 1634],  # just above the footer band, without a body overlap
    [1049, 1615, 1085, 1650],  # extends below the footer band
])
def test_same_band_folio_cannot_extend_outside_preceding_footer_vertical_span(box):
    manifest, page = actual_size_footer_packet()
    manifest["pages"][0]["fragments"][-1]["bbox_px"] = box
    with pytest.raises(ReviewedFormattingError):
        validate(manifest, page)
