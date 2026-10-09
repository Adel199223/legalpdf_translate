"""Physical AR containers preserve content; native Word acceptance is separate."""
from copy import deepcopy

import pytest

from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests.test_saved_docx_layout_writer import packet, xml


def automatic(lang="AR"):
    raw, snapshot, pages, decisions = packet(lang)
    ids = [p["id"] for p in snapshot["paragraphs"]]
    decisions["bands"] = [{"kind": "flow", "groups": [{"paragraph_ids": ids, "panel": False}]}]
    decisions["review"].update(document_reviewed=False, pages_reviewed=[], reviewer="", note="")
    for choice, box in zip(decisions["paragraphs"], ([150, 20, 400, 45], [600, 50, 850, 75],
            [150, 80, 400, 105], [520, 110, 840, 135], [540, 140, 820, 165], [150, 170, 400, 195])):
        choice["regions"][0]["bbox_px"] = box
        choice["role"] = "reference"
        choice["heading_level"] = 0
        choice["heading_size_pt"] = None
    return raw, snapshot, pages, decisions


def test_ar_physical_cells_merge_only_contiguous_overlapping_boxes_and_preserve_runs():
    raw, snapshot, pages, dec = automatic()
    built = writer.build_unreviewed_docx(raw, snapshot, pages, dec)
    plan = built.source_map["derived_horizontal_plan"]
    ids = [p["id"] for p in snapshot["paragraphs"]]
    assert [p["paragraph_ids"] for p in plan] == [[ids[0]], [ids[1]], [ids[2]], ids[3:5]]
    root = xml(built.docx_bytes)
    assert all(n.get(model.W + "val") == "0" for n in root.iter(model.W + "bidiVisual"))
    assert all(sum(p["cell_widths_twips"]) == sum(plan[0]["cell_widths_twips"]) for p in plan)
    assert plan[0]["cell_widths_twips"][0] < plan[1]["cell_widths_twips"][0]
    for row in built.source_map["paragraphs"][:-1]:
        assert "tc" in row["location"]
    # Independent validation checks XML space, run direction/font and exact text.
    writer.validate_built_docx(built.docx_bytes, built.source_map, original_docx=raw,
        snapshot=snapshot, pages=pages, decisions=dec, require_review=False)
    tables = list(root[0].findall(model.W + "tbl"))
    for table in tables:
        assert table.getnext().tag == model.W + "p"
        assert not list(table.getnext().iter(model.W + "t"))


@pytest.mark.parametrize("lang", ["EN", "FR"])
def test_other_languages_keep_flow_without_ar_horizontal_containers(lang):
    built = writer.build_unreviewed_docx(*automatic(lang))
    assert built.source_map["writer_version"] == writer.AUTOMATIC_MODERN_WRITER_VERSION
    assert "derived_horizontal_plan" not in built.source_map


def test_unknown_and_fullwidth_split_frames_and_tiny_content_is_widened():
    raw, snapshot, pages, dec = automatic()
    dec["paragraphs"][1]["regions"][0]["bbox_px"] = [0, 50, 1000, 75]
    dec["paragraphs"][3].update(regions=[], unmapped_reason="No reliable region")
    dec["paragraphs"][0]["regions"][0]["bbox_px"] = [151, 20, 152, 45]
    built = writer.build_unreviewed_docx(raw, snapshot, pages, dec)
    plan = built.source_map["derived_horizontal_plan"]
    assert plan[0]["cell_widths_twips"][1] == 360
    assert len(plan) == 3


def test_legacy_automatic_ar_verifies_using_recorded_version_and_plan_tampering_fails():
    raw, snapshot, pages, dec = automatic()
    checked = model.validate_decisions(snapshot, pages, dec, require_review=False)
    members, infos, original, _, _ = model._load_docx(raw)
    root, locations, structural = writer._assemble(original, snapshot, checked)
    from lxml import etree
    legacy = writer._write(members, infos, etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True))
    mapping = writer._source_map(snapshot, pages, checked, locations, structural, legacy,
                                 require_review=False, writer_version=writer.WRITER_VERSION)
    writer.validate_built_docx(legacy, mapping, original_docx=raw, snapshot=snapshot,
        pages=pages, decisions=dec, require_review=False)
    built = writer.build_unreviewed_docx(raw, snapshot, pages, dec)
    changed = deepcopy(built.source_map)
    changed["derived_horizontal_plan"][0]["cell_widths_twips"][0] += 1
    with pytest.raises(model.SavedDocxLayoutError):
        writer.validate_built_docx(built.docx_bytes, changed, original_docx=raw,
            snapshot=snapshot, pages=pages, decisions=dec, require_review=False)


@pytest.mark.parametrize("role", ["body", "list", "signature", "source_folio"])
def test_narrative_and_furniture_never_become_horizontal_tables(role):
    raw, snapshot, pages, dec = automatic()
    dec["paragraphs"][0]["role"] = role
    dec["paragraphs"][1]["role"] = "heading"
    dec["paragraphs"][1]["heading_level"] = 1
    dec["paragraphs"][1]["heading_size_pt"] = 12
    built = writer.build_unreviewed_docx(raw, snapshot, pages, dec)
    framed = {pid for item in built.source_map["derived_horizontal_plan"] for pid in item["paragraph_ids"]}
    assert snapshot["paragraphs"][0]["id"] not in framed
    assert snapshot["paragraphs"][1]["id"] not in framed


@pytest.mark.parametrize("inherited", [False, True])
def test_page_break_before_never_moves_a_metadata_paragraph_into_a_table(inherited):
    from docx import Document
    import io
    raw, _, pages, dec = automatic()
    doc = Document(io.BytesIO(raw))
    if inherited:
        doc.styles["Normal"].paragraph_format.page_break_before = True
    else:
        doc.paragraphs[0].paragraph_format.page_break_before = True
    stream = io.BytesIO()
    doc.save(stream)
    raw = stream.getvalue()
    snapshot = model.inspect_docx(raw, "AR")
    dec["docx_sha256"] = snapshot["docx_sha256"]
    # Decision identity is generated by the existing default builder.
    from tests.test_saved_docx_layout import reviewed
    _, _, updated = reviewed(raw, "AR", pages)
    for key in ("paragraphs", "bands", "review"):
        updated[key] = dec[key]
    built = writer.build_unreviewed_docx(raw, snapshot, pages, updated)
    framed = {pid for item in built.source_map["derived_horizontal_plan"] for pid in item["paragraph_ids"]}
    assert snapshot["paragraphs"][0]["has_page_break"]
    assert snapshot["paragraphs"][0]["id"] not in framed


def test_new_ar_sets_one_mode15_and_rejects_other_settings_changes():
    import io
    from zipfile import ZipFile
    from lxml import etree
    from tests.test_saved_docx_layout import changed_part
    raw, snapshot, pages, dec = automatic()
    built = writer.build_unreviewed_docx(raw, snapshot, pages, dec)
    with ZipFile(io.BytesIO(built.docx_bytes)) as archive:
        settings = etree.fromstring(archive.read("word/settings.xml"))
    modes = [n for n in settings.iter(model.W + "compatSetting") if n.get(model.W + "name") == "compatibilityMode"]
    assert len(modes) == 1 and modes[0].get(model.W + "val") == "15"
    for value in ("12", "16"):
        altered = changed_part(built.docx_bytes, "word/settings.xml", lambda root: next(
            n for n in root.iter(model.W + "compatSetting") if n.get(model.W + "name") == "compatibilityMode"
        ).set(model.W + "val", value))
        with pytest.raises(model.SavedDocxLayoutError, match="unaffected_package_changed"):
            writer.validate_built_docx(altered, built.source_map, original_docx=raw,
                snapshot=snapshot, pages=pages, decisions=dec, require_review=False)


@pytest.mark.parametrize("lang", ["EN", "FR"])
def test_reviewed_other_language_settings_remain_byte_identical(lang):
    import io
    from zipfile import ZipFile
    raw, snapshot, pages, dec = automatic(lang)
    dec["review"].update(document_reviewed=True, pages_reviewed=[1], reviewer="Fictional", note="Reviewed")
    built = writer.build_docx(raw, snapshot, pages, dec)
    with ZipFile(io.BytesIO(raw)) as original, ZipFile(io.BytesIO(built.docx_bytes)) as output:
        assert original.read("word/settings.xml") == output.read("word/settings.xml")
