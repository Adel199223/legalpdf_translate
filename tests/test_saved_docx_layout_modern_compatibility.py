"""Mode15 is a new automatic package contract; historical bytes stay valid."""
import base64
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
import pytest

from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests.test_saved_docx_layout import changed_part
from tests.test_saved_docx_layout_horizontal_flow import automatic
from tests.test_saved_docx_layout_partitions import packet


def settings(raw):
    with ZipFile(io.BytesIO(raw)) as package:
        return etree.fromstring(package.read("word/settings.xml"))


def modes(root):
    return [n.get(model.W + "val") for n in root.iter(model.W + "compatSetting")
            if n.get(model.W + "name") == "compatibilityMode"]


@pytest.mark.parametrize("lang", ["EN", "FR", "AR"])
@pytest.mark.parametrize("partitioned", [False, True])
def test_new_automatic_candidates_use_mode15_preserve_package_and_parts(lang, partitioned):
    args = packet(lang) if partitioned else automatic(lang)
    raw, snapshot, pages, decisions = args
    artifact = writer.build_unreviewed_docx(*args)
    assert artifact.source_map["writer_version"] == writer.AUTOMATIC_SEPARATED_WRITER_VERSION
    assert modes(settings(artifact.docx_bytes)) == ["15"]
    with ZipFile(io.BytesIO(raw)) as before, ZipFile(io.BytesIO(artifact.docx_bytes)) as after:
        assert before.namelist() == after.namelist()
        assert all(before.read(n) == after.read(n) for n in before.namelist()
                   if n not in {"word/document.xml", "word/settings.xml"})
    assert snapshot == model.inspect_docx(raw, lang)
    assert bool(artifact.source_map["paragraphs"][0].get("parts")) == partitioned
    assert ("derived_horizontal_plan" in artifact.source_map) == (lang == "AR")
    writer.validate_built_docx(artifact.docx_bytes, artifact.source_map, original_docx=raw,
        snapshot=snapshot, pages=pages, decisions=decisions, require_review=False)


@pytest.mark.parametrize("old_modes", [[], ["12"], ["14"], ["12", "14"], ["15", "15"]])
def test_only_mode_entry_is_normalized_and_other_settings_retained(old_modes):
    raw, _, pages, decisions = automatic("EN")
    def initial(root):
        for node in list(root.iter(model.W + "compatSetting")):
            if node.get(model.W + "name") == "compatibilityMode":
                node.getparent().remove(node)
        compat = root.find(model.W + "compat")
        if compat is None:
            compat = etree.SubElement(root, model.W + "compat")
        etree.SubElement(compat, model.W + "compatSetting", {
            model.W + "name": "fictionalUnrelatedSetting", model.W + "val": "7"})
        for value in old_modes:
            etree.SubElement(compat, model.W + "compatSetting", {
                model.W + "name": "compatibilityMode", model.W + "val": value})
    raw = changed_part(raw, "word/settings.xml", initial)
    snapshot = model.inspect_docx(raw, "EN")
    # Package edits above affect identity only; decisions carry no stale raw hash.
    artifact = writer.build_unreviewed_docx(raw, snapshot, pages, decisions)
    assert modes(settings(artifact.docx_bytes)) == ["15"]
    assert settings(artifact.docx_bytes).find(".//" + model.W + "compatSetting[@" + model.W + "name='fictionalUnrelatedSetting']").get(model.W + "val") == "7"


@pytest.mark.parametrize("damage", ["absent", "wrong", "duplicate", "unrelated"])
def test_independent_verifier_rejects_unauthorized_settings_delta(damage):
    raw, snapshot, pages, decisions = automatic("EN")
    artifact = writer.build_unreviewed_docx(raw, snapshot, pages, decisions)
    def corrupt(root):
        node = next(n for n in root.iter(model.W + "compatSetting")
                    if n.get(model.W + "name") == "compatibilityMode")
        if damage == "absent": node.getparent().remove(node)
        elif damage == "wrong": node.set(model.W + "val", "12")
        elif damage == "duplicate": node.getparent().append(deepcopy(node))
        else: etree.SubElement(root, model.W + "updateFields", {model.W + "val": "1"})
    changed = changed_part(artifact.docx_bytes, "word/settings.xml", corrupt)
    with pytest.raises(model.SavedDocxLayoutError, match="unaffected_package_changed"):
        writer.validate_built_docx(changed, artifact.source_map, original_docx=raw,
            snapshot=snapshot, pages=pages, decisions=decisions, require_review=False)


def test_verifier_does_not_trust_corrupted_builder_settings_helper(monkeypatch):
    args = automatic("FR")
    monkeypatch.setattr(writer, "_modern_compatibility_settings", lambda raw: raw)
    with pytest.raises(model.SavedDocxLayoutError, match="unaffected_package_changed"):
        writer.build_unreviewed_docx(*args)


@pytest.mark.parametrize("version", ["invented", writer.WRITER_VERSION])
def test_wrong_version_cannot_relabel_new_en_package(version):
    raw, snapshot, pages, decisions = automatic("EN")
    artifact = writer.build_unreviewed_docx(raw, snapshot, pages, decisions)
    mapping = dict(artifact.source_map, writer_version=version)
    with pytest.raises(model.SavedDocxLayoutError):
        writer.validate_built_docx(artifact.docx_bytes, mapping, original_docx=raw,
            snapshot=snapshot, pages=pages, decisions=decisions, require_review=False)


def test_modern_automatic_version_cannot_claim_reviewed_saved_build():
    raw, snapshot, pages, decisions = automatic("EN")
    artifact = writer.build_unreviewed_docx(raw, snapshot, pages, decisions)
    decisions["review"].update(document_reviewed=True, pages_reviewed=[1], reviewer="Fictional", note="Reviewed")
    with pytest.raises(model.SavedDocxLayoutError, match="unsupported_writer_version"):
        writer.validate_built_docx(artifact.docx_bytes, artifact.source_map, original_docx=raw,
            snapshot=snapshot, pages=pages, decisions=decisions, require_review=True)


@pytest.mark.parametrize("index", [0, 1, 2])
def test_frozen_historical_v1_v2_v3_artifacts_verify_exactly(index):
    fixture = json.loads((Path(__file__).parent / "fixtures/saved_docx_layout_historical_writer_versions.json").read_bytes())
    row = fixture["cases"][index]
    original = base64.b64decode(row["original_docx_b64"])
    stream = io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source, ZipFile(stream, "w") as target:
        for info in source.infolist():
            value = (base64.b64decode(row["output_parts_b64"][info.filename])
                     if info.filename in row["output_parts_b64"] else source.read(info.filename))
            target.writestr(info, value)
    output = stream.getvalue()
    assert hashlib.sha256(output).hexdigest() == row["output_docx_sha256"]
    assert hashlib.sha256(model._canonical(row["source_map"])).hexdigest() == row["source_map_sha256"]
    writer.validate_built_docx(output, row["source_map"], original_docx=original,
        snapshot=row["snapshot"], pages=row["pages"], decisions=row["decisions"], require_review=False)


@pytest.mark.parametrize("lang", ["EN", "FR", "AR"])
def test_frozen_v4_adjacent_tables_remain_valid_without_new_separators(lang):
    fixture = json.loads((Path(__file__).parent / "fixtures/saved_docx_layout_historical_v4.json").read_bytes())
    row = next(case for case in fixture["cases"] if case["lang"] == lang)
    original = base64.b64decode(row["original_docx_b64"])
    stream = io.BytesIO()
    with ZipFile(io.BytesIO(original)) as source, ZipFile(stream, "w") as target:
        for info in source.infolist():
            value = (base64.b64decode(row["output_parts_b64"][info.filename])
                     if info.filename in row["output_parts_b64"] else source.read(info.filename))
            target.writestr(info, value)
    output = stream.getvalue()
    assert hashlib.sha256(output).hexdigest() == row["output_docx_sha256"]
    assert row["source_map"]["writer_version"] == writer.AUTOMATIC_MODERN_WRITER_VERSION
    writer.validate_built_docx(output, row["source_map"], original_docx=original,
        snapshot=row["snapshot"], pages=row["pages"], decisions=row["decisions"], require_review=False)


def adjacent_packet(lang, panels=False):
    from tests.test_saved_docx_layout_writer import packet as column_packet
    raw, snapshot, pages, decisions = column_packet(lang)
    decisions["review"].update(document_reviewed=False, pages_reviewed=[], reviewer="", note="")
    if panels:
        ids = [row["id"] for row in snapshot["paragraphs"]]
        decisions["bands"] = [{"kind": "flow", "groups": [
            {"paragraph_ids": [identifier], "panel": True} for identifier in ids[:-1]] + [
            {"paragraph_ids": ids[-1:], "panel": False}]}]
    return raw, snapshot, pages, decisions


@pytest.mark.parametrize("lang", ["EN", "FR", "AR"])
@pytest.mark.parametrize("panels", [False, True])
def test_v5_only_separates_direct_body_tables_not_nested_cells(lang, panels):
    args = adjacent_packet(lang, panels)
    artifact = writer.build_unreviewed_docx(*args)
    with ZipFile(io.BytesIO(artifact.docx_bytes)) as package:
        root = etree.fromstring(package.read("word/document.xml"))
    body = root[0]
    assert not any(a.tag == b.tag == model.W + "tbl" for a, b in zip(body, list(body)[1:]))
    assert artifact.source_map["writer_version"] == writer.AUTOMATIC_SEPARATED_WRITER_VERSION
    assert artifact.source_map["structural_paragraph_qualification"].endswith("_v5")
    separators = [node for node in body if node.tag == model.W + "p"
                  and node.getprevious() is not None and node.getnext() is not None
                  and node.getprevious().tag == node.getnext().tag == model.W + "tbl"]
    assert len(separators) == (4 if panels else 1)
    for separator in separators:
        shape = lambda node: [(child.tag, dict(child.attrib), child.text, child.tail)
                              for child in node.iter()]
        assert shape(separator) == shape(writer._empty())
        assert root.getroottree().getpath(separator) in artifact.source_map["structural_paragraphs"]
    writer.validate_built_docx(artifact.docx_bytes, artifact.source_map, original_docx=args[0],
        snapshot=args[1], pages=args[2], decisions=args[3], require_review=False)


@pytest.mark.parametrize("damage", ["remove", "move", "text", "hidden"])
def test_v5_separator_damage_is_rejected_without_ownership_waiver(damage):
    args = adjacent_packet("EN")
    artifact = writer.build_unreviewed_docx(*args)
    def corrupt(root):
        body = root[0]
        separator = next(node for node in body if node.tag == model.W + "p"
            and node.getprevious() is not None and node.getnext() is not None
            and node.getprevious().tag == node.getnext().tag == model.W + "tbl")
        if damage == "remove": body.remove(separator)
        elif damage == "move": body.remove(separator); body.insert(0, separator)
        else:
            run = etree.SubElement(separator, model.W + "r")
            if damage == "text": etree.SubElement(run, model.W + "t").text = "Unauthorized"
            else: etree.SubElement(etree.SubElement(run, model.W + "rPr"), model.W + "vanish")
    changed = changed_part(artifact.docx_bytes, "word/document.xml", corrupt)
    with pytest.raises(model.SavedDocxLayoutError):
        writer.validate_built_docx(changed, artifact.source_map, original_docx=args[0],
            snapshot=args[1], pages=args[2], decisions=args[3], require_review=False)


def test_v5_independent_adjacency_guard_does_not_trust_builder(monkeypatch):
    assemble = writer._assemble
    def broken(*args, **kwargs):
        kwargs["separate_body_tables"] = False
        return assemble(*args, **kwargs)
    monkeypatch.setattr(writer, "_assemble", broken)
    with pytest.raises(model.SavedDocxLayoutError, match="output_adjacent_body_tables"):
        writer.build_unreviewed_docx(*adjacent_packet("FR"))
