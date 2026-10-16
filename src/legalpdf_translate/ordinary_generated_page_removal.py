"""Certify explicit Word removal of app-generated PAGE furniture only."""
from copy import deepcopy
import posixpath
import re

from lxml import etree

from .ordinary_layout_contracts import digest, fail
from .ordinary_presentation import _v6_page_signature
from .ordinary_section_ownership import verified_word_story_projection
from .ordinary_text_correction import package, paragraphs, imported_word_map
from .ordinary_source_layout import _pack
from . import saved_docx_layout as model

W = model.W
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
STORY = re.compile(r"word/(header|footer)[0-9]+\.xml\Z")


def _generated(raw, language):
    root = model._xml(raw)
    return (root.tag == W + "ftr" and len(root) == 1 and root[0].tag == W + "p"
        and model._c14n(root[0]) == model._c14n(_v6_page_signature(root[0].nsmap, language)))


def _empty(raw):
    root = model._xml(raw)
    allowed = {W + name for name in ("hdr", "ftr", "p", "pPr", "pStyle", "jc", "r", "rPr",
        "rFonts", "sz", "szCs", "lang", "rtl", "bidi", "spacing", "t")}
    return (root.tag in {W + "hdr", W + "ftr"} and len(root) == 1 and root[0].tag == W + "p"
        and all(node.tag in allowed and not (node.text or "").strip() for node in root.iter()))


def _slots(members):
    document = model._xml(members["word/document.xml"])
    rels = model._xml(members["word/_rels/document.xml.rels"])
    by_id = {}
    for rel in rels:
        key = rel.get("Id")
        if key in by_id:
            fail("generated_page_removal_ownership", 409)
        by_id[key] = rel
    slots, inherited = {}, {}
    for number, section in enumerate(document.iter(W + "sectPr")):
        seen = set()
        for ref in section:
            if ref.tag not in {W + "headerReference", W + "footerReference"}:
                continue
            kind = "header" if ref.tag == W + "headerReference" else "footer"
            slot = ref.get(W + "type")
            rel = by_id.get(ref.get(R + "id"))
            if (slot not in {"first", "default", "even"} or (kind, slot) in seen
                    or set(ref.attrib) != {W + "type", R + "id"} or rel is None
                    or rel.get("TargetMode") is not None
                    or rel.get("Type") != R[1:-1] + "/" + kind):
                fail("generated_page_removal_ownership", 409)
            seen.add((kind, slot))
            target = rel.get("Target", "")
            name = posixpath.normpath("word/" + target)
            if (not target or "\\" in target or target.startswith("/") or ".." in target.split("/")
                    or not re.fullmatch("word/" + kind + r"[0-9]+\.xml", name) or name not in members):
                fail("generated_page_removal_ownership", 409)
            inherited[kind, slot] = name
        for kind in ("header", "footer"):
            for slot in ("first", "default", "even"):
                slots[number, kind, slot] = inherited.get((kind, slot))
    return document, rels, slots


def _without_stories(members, removed):
    result = dict(members)
    document, rels, _ = _slots(result)
    removed_ids = set()
    for rel in list(rels):
        if posixpath.normpath("word/" + rel.get("Target", "")) in removed:
            removed_ids.add(rel.get("Id"))
            rels.remove(rel)
    for section in document.iter(W + "sectPr"):
        for ref in list(section):
            if ref.tag in {W + "headerReference", W + "footerReference"} and ref.get(R + "id") in removed_ids:
                section.remove(ref)
    types = model._xml(result["[Content_Types].xml"])
    for item in list(types):
        if item.get("PartName", "").lstrip("/") in removed:
            types.remove(item)
    for name in removed:
        result.pop(name)
    for name, root in (("word/document.xml", document), ("word/_rels/document.xml.rels", rels),
            ("[Content_Types].xml", types)):
        result[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    return _pack(result)


def certified_removal(origin, base, edited, language):
    """Return normalized copies; caller must run its unchanged strict qualifier."""
    original, _, _ = package(origin)
    before, _, _ = package(base)
    after, _, _ = package(edited)
    try:
        lineage = verified_word_story_projection(original, before)
    except ValueError:
        fail("generated_page_removal_origin_changed", 409)
    certified = {lineage["part_map"][name] for name in lineage["part_map"]
        if name.startswith("word/footer") and _generated(original[name], language)
        and _generated(before[lineage["part_map"][name]], language)}
    if not certified:
        fail("generated_page_removal_origin_unavailable", 409)
    _, _, old_slots = _slots(before)
    _, _, new_slots = _slots(after)
    if old_slots.keys() != new_slots.keys():
        fail("generated_page_removal_ownership", 409)
    empty_after = {name for name in after if STORY.fullmatch(name) and _empty(after[name])}
    removed = set()
    for key, old in old_slots.items():
        new = new_slots[key]
        if old in certified:
            if new is not None and new not in empty_after:
                fail("generated_page_removal_not_empty", 409)
            removed.add(old)
        elif old is None:
            if new is not None and new not in empty_after:
                fail("generated_page_removal_ownership", 409)
        elif new is None or new in empty_after:
            fail("generated_page_removal_source_story_changed", 409)
    if removed != certified:
        fail("generated_page_removal_ownership", 409)
    # Only new blank serialization stories and blank successors of certified
    # generated slots may disappear from the comparison. Existing source stories
    # retain the ordinary projection and exact text/control requirements.
    referenced_after = set(new_slots.values())
    ignored = {name for name in empty_after if name in referenced_after and (name not in before or name in certified)}
    normalized_base = _without_stories(before, removed)
    normalized_edited = _without_stories(after, ignored)
    certificate = {"version": "certified_generated_page_removal_v1", "origin_sha256": digest(origin),
        "parent_sha256": digest(base), "edited_sha256": digest(edited),
        "removed_parent_parts": sorted(removed), "ignored_empty_edited_parts": sorted(ignored),
        "normalized_parent_sha256": digest(normalized_base), "normalized_edited_sha256": digest(normalized_edited)}
    return normalized_base, normalized_edited, certificate


def removal_paragraph_map(base, edited, mapping, normalized_base, normalized_edited, certificate):
    """Keep substantive IDs; added blank serialization stories get no source ID."""
    removed = set(certificate["removed_parent_parts"])
    kept = [item for row, item in zip(paragraphs(base), mapping) if row["part_uri"] not in removed]
    mapped = imported_word_map(normalized_base, normalized_edited, kept)
    by_location = {(row["part_uri"], tuple(row["location"])): row for row in mapped}
    result = []
    for row in paragraphs(edited):
        value = by_location.get((row["part_uri"], tuple(row["location"])))
        if value is None:
            if row["part_uri"] not in certificate["ignored_empty_edited_parts"] or row["text"].strip():
                fail("generated_page_removal_map_changed", 409)
            key = (digest(base) + "|" + row["part_uri"] + "|" + repr(row["location"])).encode()
            value = {"paragraph_id": "p-empty-" + digest(key)[:24], "parent_paragraph_id": None,
                "regions": [], "association_status": "unowned_empty_serialization_story",
                "part_uri": row["part_uri"], "location": row["location"]}
        result.append(deepcopy(value))
    if len({row["paragraph_id"] for row in result}) != len(result):
        fail("generated_page_removal_map_changed", 409)
    return result
