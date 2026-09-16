"""Synthetic same-line metadata cells; no real-document acceptance."""
from copy import deepcopy
from dataclasses import replace
import io
import json
import zipfile

from lxml import etree
import pytest

from legalpdf_translate.document_structure import text_sha256
from legalpdf_translate.formatting_support import fingerprint
from legalpdf_translate.reviewed_formatting import (
    BOUNDARY_POLICY, CELL_BOUNDARY_POLICY, ReviewedFormattingError,
)
from legalpdf_translate.reviewed_formatting_writer import (
    ReviewedFormattingWriterError, build_reviewed_docx, validate_reviewed_docx,
)
from legalpdf_translate.reviewed_folios import (
    FolioFragmentInput, FolioPageInput, ReviewedFolioError, validate_document_local_folios,
)
from tests.test_reviewed_formatting import validate
from tests.test_reviewed_formatting_v2 import region_packet


def inline_packet(lang="FR", *, source_cells=None, target_cells=None):
    manifest, page = region_packet()
    old = manifest["pages"][0]["fragments"]
    source_cells = source_cells or ["Processo: 123 | ", "Referência: 9876 | ", "Data: 23-06-2026\n\n"]
    target_cells = target_cells or ({
        "AR": ["الملف [[123]] | ", "المرجع [[9876]] | ", "التاريخ [[23-06-2026]]\n\n"],
        "EN": ["Case: 123 | ", "Document reference: 9876 | ", "Date: 23-06-2026\n\n"],
        "FR": ["Dossier : 123 | ", "Référence du document : 9876 | ", "Date : 23-06-2026\n\n"],
    }[lang])
    parts = {}
    for side, cells in (("source", source_cells), ("target", target_cells)):
        original = getattr(page, side + "_structure")["blocks"][0]["text"]
        parts[side] = [original[slice(*old[0][side + "_range"])], *cells,
                       original[slice(*old[3][side + "_range"])], original[slice(*old[4][side + "_range"])]]
        getattr(page, side + "_structure")["blocks"][0]["text"] = "".join(parts[side])
    source_hash = text_sha256("".join(parts["source"]))
    for structure in (page.source_structure, page.target_structure):
        structure["source_sha256"] = structure["source_text_sha256"] = source_hash
        structure["metadata"]["selected_text_sha256"] = source_hash
    page.target_structure["translation_sha256"] = text_sha256("".join(parts["target"]))
    boxes = [old[0]["bbox_px"], [40,150,180,200], [200,150,380,200], [400,150,550,200],
             old[3]["bbox_px"], old[4]["bbox_px"]]
    roles = ["header", "body", "body", "body", "footer", "folio"]
    starts = {"source": 0, "target": 0}
    fragments = []
    for index, (role, box) in enumerate(zip(roles, boxes)):
        row = {**deepcopy(old[0]), "rendering_id": f"p0001_f{index+1:04d}", "role":role,
               "bbox_px":box, "alignment":"right" if lang=="AR" else "left"}
        for side in ("source", "target"):
            content = parts[side][index]
            row[side + "_range"] = [starts[side], starts[side]+len(content)]
            row[side + "_text_sha256"] = text_sha256(content)
            starts[side] += len(content)
        fragments.append(row)
    row = manifest["pages"][0]
    row.update(fragments=fragments, folio_fragment_id="p0001_f0006",
        source_structure_sha256=fingerprint(page.source_structure),
        target_structure_sha256=fingerprint(page.target_structure),
        region_layout={"version":"reviewed_region_layout_v1","header":["p0001_f0001"],
            "body":[{"kind":"table","table_id":"p0001_t0001","column_widths":[25,40,35],
                     "rows":[{"cells":[{"fragment_ids":[f"p0001_f{i:04d}"]} for i in (2,3,4)]}]}],
            "footer":["p0001_f0005","p0001_f0006"]})
    manifest.update(boundary_policy=CELL_BOUNDARY_POLICY, target_lang=lang)
    return manifest,page


@pytest.mark.parametrize("lang", ["FR", "EN", "AR"])
def test_three_independently_mapped_cells_preserve_every_character(lang):
    manifest,page = inline_packet(lang)
    before = deepcopy((manifest,page))
    projection = validate(manifest,page,target_lang=lang)
    assert projection.boundary_policy == CELL_BOUNDARY_POLICY
    assert projection.pages[0].fragments[1].source_range != projection.pages[0].fragments[1].target_range
    for side in ("source","target"):
        assert "".join(getattr(f, side+"_text") for f in projection.pages[0].fragments) == getattr(page,side+"_structure")["blocks"][0]["text"]
    artifact = build_reviewed_docx(projection)
    validate_reviewed_docx(artifact.docx_bytes,artifact.source_map_bytes,projection=projection)
    with zipfile.ZipFile(io.BytesIO(artifact.docx_bytes)) as package:
        xml=etree.fromstring(package.read("word/document.xml"))
    ns={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    cells=xml.findall(".//w:tbl/w:tr/w:tc",ns)
    assert len(cells)==3
    assert ["".join(c.itertext()).count("|") for c in cells] == [1,1,0]
    assert (manifest,page)==before


def test_arabic_literal_isolates_reach_editable_docx_cells_without_target_edits():
    cells = ["\u2066[[ABC-123]]\u2069 | ", "مرجع المستند | ", "\u2066[[23-06-2026]]\u2069\n\n"]
    manifest, page = inline_packet("AR", target_cells=cells)
    before = deepcopy((manifest, page))
    projection = validate(manifest, page, target_lang="AR")
    artifact = build_reviewed_docx(projection)
    validate_reviewed_docx(artifact.docx_bytes, artifact.source_map_bytes, projection=projection)
    assert [f.target_text for f in projection.pages[0].fragments[1:4]] == cells
    with zipfile.ZipFile(io.BytesIO(artifact.docx_bytes)) as package:
        xml = etree.fromstring(package.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    rendered_cells = xml.findall(".//w:tbl/w:tr/w:tc", ns)
    assert len(rendered_cells) == 3
    text = ["".join(c.itertext()).replace("\u200e", "") for c in rendered_cells]
    assert "ABC-123" in text[0] and "مرجع المستند" in text[1] and "23-06-2026" in text[2]
    assert [value.count("|") for value in text] == [1, 1, 0]
    assert (manifest, page) == before


@pytest.mark.parametrize("side", ["source","target"])
def test_inline_on_one_side_and_whole_lines_on_the_other(side):
    kwargs={side+"_cells":["Field alpha\n", "Field beta\n", "Field gamma\n\n"]}
    manifest,page=inline_packet(**kwargs)
    projection=validate(manifest,page)
    build_reviewed_docx(projection)


def folio_input(manifest,page):
    row=manifest["pages"][0]
    return FolioPageInput(page.source_structure,page.target_structure,840,row["folio_fragment_id"],
        tuple(FolioFragmentInput(f["rendering_id"],f["parent_block_id"],tuple(f["source_range"]),
            tuple(f["target_range"]),f["role"],tuple(f["bbox_px"])) for f in row["fragments"]),
        region_layout=row["region_layout"],image_width_px=600)


def test_direct_folio_gate_requires_real_cell_context():
    manifest,page=inline_packet()
    original=folio_input(manifest,page)
    validate_document_local_folios(manifest["document_groups"],pages=[original],source_file_sha256="a"*64,target_lang="FR")
    for value in (replace(original,region_layout=None,image_width_px=None),
                  replace(original,region_layout={}),replace(original,image_width_px=100)):
        with pytest.raises(ReviewedFolioError):
            validate_document_local_folios(manifest["document_groups"],pages=[value],source_file_sha256="a"*64,target_lang="FR")


@pytest.mark.parametrize("policy", [BOUNDARY_POLICY,"arbitrary_cells",None,[],{}])
def test_old_and_invalid_policies_cannot_admit_inline_cells(policy):
    manifest,page=inline_packet()
    manifest["boundary_policy"]=policy
    with pytest.raises(ReviewedFormattingError): validate(manifest,page)


@pytest.mark.parametrize("side", ["source","target"])
@pytest.mark.parametrize("cells", [
    ["João ","Guerreiro | ","Clock: 09:30\n\n"],
    ["Clock: 09:","30 | ","Field three\n\n"],
    ["Name: [[A | ","B]] | ","Field three\n\n"],
    ["Name: \u2066A | ","B\u2069 | ","Field three\n\n"],
    ["Field one | ","\u0301accent | ","Field three\n\n"],
    ["حقل | ","\u200dمتصل | ","آخر\n\n"],
])
def test_unsafe_cuts_fail_even_when_hashes_and_geometry_are_rebound(side,cells):
    manifest,page=inline_packet(**{side+"_cells":cells})
    with pytest.raises(ReviewedFormattingError): validate(manifest,page)


@pytest.mark.parametrize("kind", ["same_cell","paragraphs","cross_rows","cross_tables","footer"])
def test_inline_boundary_cannot_escape_distinct_cells_in_one_row(kind):
    manifest,page=inline_packet()
    row=manifest["pages"][0]
    layout=row["region_layout"]
    table=layout["body"][0]
    if kind=="same_cell":
        table["rows"][0]["cells"]=[{"fragment_ids":["p0001_f0002","p0001_f0003","p0001_f0004"]}]
        table["column_widths"]=[100]
    elif kind=="paragraphs":
        layout["body"]=[{"kind":"paragraph","fragment_id":f"p0001_f{i:04d}"} for i in (2,3,4)]
    elif kind=="cross_rows":
        table["column_widths"]=[100]
        table["rows"]=[{"cells":[{"fragment_ids":[f"p0001_f{i:04d}"]}]} for i in (2,3,4)]
    elif kind=="cross_tables":
        layout["body"]=[{"kind":"table","table_id":f"p0001_t{i-1:04d}","column_widths":[100],
                         "rows":[{"cells":[{"fragment_ids":[f"p0001_f{i:04d}"]}]}]} for i in (2,3,4)]
    else:
        row["fragments"][1]["role"]="footer"
    if kind in ("same_cell","paragraphs","cross_rows","cross_tables"):
        # Make each alternative geometry valid; rejection must still enforce
        # the inline ownership rule, not rely solely on overlapping boxes.
        for index,fragment in enumerate(row["fragments"][1:4]):
            fragment["bbox_px"]=[40,150+index*80,550,200+index*80]
    with pytest.raises(ReviewedFormattingError): validate(manifest,page)
    with pytest.raises(ReviewedFolioError):
        validate_document_local_folios(manifest["document_groups"],pages=[folio_input(manifest,page)],
                                      source_file_sha256="a"*64,target_lang="FR")


def test_writer_rechecks_inline_policy_in_forged_projection():
    manifest,page=inline_packet()
    projection=validate(manifest,page)
    with pytest.raises(ReviewedFormattingWriterError):
        build_reviewed_docx(replace(projection,boundary_policy=BOUNDARY_POLICY))
    with pytest.raises(ReviewedFormattingWriterError):
        build_reviewed_docx(replace(projection,version="reviewed_formatting_v1",policy="source_page_matched_reviewed_v1"))


def test_opening_letterhead_can_remain_ordered_body_content():
    manifest,page=inline_packet()
    row=manifest["pages"][0]
    # Existing header content is an opening body letterhead in this case.
    row["fragments"][0].update(role="body",bold=True)
    row["region_layout"]["header"]=[]
    row["region_layout"]["body"].insert(0,{"kind":"paragraph","fragment_id":"p0001_f0001"})
    projection=validate(manifest,page)
    build_reviewed_docx(projection)
    row["fragments"][0]["role"]="header"
    with pytest.raises(ReviewedFormattingError): validate(manifest,page)
