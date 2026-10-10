"""Bounded local text edits, independent of paid translation/layout contracts.

Paragraph identifiers include the story URI and XML ownership path. This module
never extracts a ZIP, opens Word, reads a caller path or invokes a provider.
"""
from __future__ import annotations

from copy import deepcopy
from io import BytesIO
from zipfile import ZipFile, BadZipFile
import re
import unicodedata

from lxml import etree
from .ordinary_section_ownership import word_section_signature

from .ordinary_layout_contracts import digest, fail
from .ordinary_edited_revision import _inventory

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SPACE = "{http://www.w3.org/XML/1998/namespace}space"
STORY = re.compile(r"word/(?:document|header\d+|footer\d+)\.xml\Z")
MAX_TEXT = 32000
MAX_ACTIONS = 200


def package(raw):
    try:
        if type(raw) is not bytes or not 0 < len(raw) <= 32 * 1024 * 1024:
            fail("correction_docx_invalid")
        with ZipFile(BytesIO(raw)) as archive:
            infos = archive.infolist()
            if (len(infos) > 2048 or len({i.filename for i in infos}) != len(infos)
                    or sum(i.file_size for i in infos) > 128 * 1024 * 1024
                    or any(i.flag_bits & 1 or i.file_size > 32 * 1024 * 1024 for i in infos)):
                fail("correction_docx_invalid")
            members = {i.filename: archive.read(i) for i in infos}
        if "word/document.xml" not in members:
            fail("correction_docx_invalid")
        from .saved_docx_layout import _FIXED_PARTS, _PART_PATTERN
        extra = {"word/footnotes.xml", "word/endnotes.xml", "word/_rels/footnotes.xml.rels", "word/_rels/endnotes.xml.rels"}
        if any(name not in _FIXED_PARTS and name not in extra and not _PART_PATTERN.fullmatch(name) for name in members):
            fail("correction_unsupported_package_part")
        forbidden = {W + tag for tag in ("drawing", "pict", "object", "altChunk", "ins", "del", "moveFrom", "moveTo",
            "commentReference", "commentRangeStart", "commentRangeEnd", "vanish", "webHidden", "sdt")}
        for name, data in members.items():
            if name.endswith(".xml") or name.endswith(".rels"):
                if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                    fail("correction_docx_invalid")
                root = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
                if any(node.tag in forbidden for node in root.iter()):
                    fail("correction_unsupported_content")
                if name.endswith(".rels") and any(n.get("TargetMode") == "External" for n in root):
                    fail("correction_external_relationship")
                if name == "[Content_Types].xml" and any("macro" in str(n.get("ContentType", "")).lower() for n in root):
                    fail("correction_unsupported_package_part")
        roots = {}
        for name, data in members.items():
            if STORY.fullmatch(name):
                if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                    fail("correction_docx_invalid")
                roots[name] = etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True))
        _inventory(raw)  # Includes all stories/objects/controls, even noneditable stories.
        return members, infos, roots
    except (BadZipFile, KeyError, etree.XMLSyntaxError, ValueError) as exc:
        if getattr(exc, "code", None):
            raise
        fail("correction_docx_invalid")


def _path(node, root):
    steps = []
    while node is not root:
        parent = node.getparent()
        steps.append(parent.index(node))
        node = parent
    return list(reversed(steps))


def _nodes(roots):
    return [(name, node, _path(node, root)) for name, root in sorted(roots.items())
            for node in root.iter(W + "p")]


def _editable(node):
    return node.find(W + "pPr/" + W + "sectPr") is None and all(child.tag in {W + "pPr", W + "r", W + "proofErr"} for child in node) and all(
        child.tag in {W + "rPr", W + "t"} for run in node.findall(W + "r") for child in run)


def paragraphs(raw):
    _, _, roots = package(raw)
    return [{"paragraph_id": digest((name + ":" + ".".join(map(str, path))).encode())[:32],
             "part_uri": name, "location": path,
             "text": "".join(t.text or "" for t in node.iter(W + "t")),
             "editable": _editable(node)} for name, node, path in _nodes(roots)]


def checked_text(value):
    if (type(value) is not str or not value.strip() or len(value) > MAX_TEXT
            or any(unicodedata.category(c) in {"Cc", "Cs"} or c in "\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069" for c in value)):
        fail("correction_invalid_text")
    return value


def _replace(node, text, language):
    """Keep pPr and one uniform character style; explicitly report style reset."""
    runs = node.findall(W + "r")
    styles = [etree.tostring(r.find(W + "rPr"), method="c14n") if r.find(W + "rPr") is not None else b"" for r in runs]
    uniform = len(set(styles)) <= 1
    rpr = deepcopy(runs[0].find(W + "rPr")) if runs and uniform else None
    for child in list(node):
        if child.tag != W + "pPr":
            node.remove(child)
    if language == "AR":
        from .docx_writer import _segment_directional_runs
        segments, _ = _segment_directional_runs(text)
        if "".join(value for _, value in segments) != text:
            fail("correction_text_projection_changed")
        ppr = node.find(W + "pPr")
        if ppr is None:
            ppr = etree.Element(W + "pPr"); node.insert(0, ppr)
        bidi = ppr.find(W + "bidi")
        if bidi is None:
            bidi = etree.SubElement(ppr, W + "bidi")
        bidi.set(W + "val", "1" if any(unicodedata.bidirectional(c) in {"R", "AL"} for c in text) else "0")
    else:
        segments = [("ltr", text)]
    for direction, value in segments:
        run = etree.SubElement(node, W + "r")
        props = deepcopy(rpr) if rpr is not None else etree.Element(W + "rPr")
        if language == "AR":
            for tag in ("rtl", "cs"):
                old = props.find(W + tag)
                if old is not None:
                    props.remove(old)
                etree.SubElement(props, W + tag).set(W + "val", "1" if direction == "rtl" else "0")
            lang = props.find(W + "lang")
            if lang is None:
                lang = etree.SubElement(props, W + "lang")
            lang.set(W + "val", "ar-SA" if direction == "rtl" else "en-US")
            lang.set(W + "bidi", "ar-SA")
            fonts = props.find(W + "rFonts")
            if fonts is None:
                fonts = etree.SubElement(props, W + "rFonts")
            if direction == "rtl" and not fonts.get(W + "cs"):
                fonts.set(W + "cs", fonts.get(W + "ascii", "Arial"))
        if len(props):
            run.append(props)
        etree.SubElement(run, W + "t", {SPACE: "preserve"}).text = value
    return not uniform


def apply_actions(raw, actions, language, selected_pages, *, paragraph_map=None):
    if (type(actions) is not list or not 1 <= len(actions) <= MAX_ACTIONS
            or language not in {"EN", "FR", "AR"}):
        fail("correction_invalid_actions")
    members, infos, roots = package(raw)
    rows = paragraphs(raw)
    if paragraph_map is not None:
        if len(paragraph_map) != len(rows):
            fail("correction_map_changed", 409)
        for row, mapped in zip(rows, paragraph_map):
            if (row["part_uri"], row["location"]) != (mapped["part_uri"], mapped["location"]):
                fail("correction_map_changed", 409)
            row["paragraph_id"] = mapped["paragraph_id"]
    nodes = {r["paragraph_id"]: n for r, (_, n, _) in zip(rows, _nodes(roots))}
    node_ids = {id(node): pid for pid, node in nodes.items()}
    provenance = {r["paragraph_id"]: {k: deepcopy(v) for k, v in r.items() if k not in {"text", "editable"}}
                  for r in (paragraph_map or rows)}
    by_id = {r["paragraph_id"]: r for r in rows}
    touched, changes = set(), []
    for action in actions:
        if type(action) is not dict or set(action) != {"kind", "paragraph_id", "text", "source_page", "source_bbox"}:
            fail("correction_invalid_action")
        kind, pid = action["kind"], action["paragraph_id"]
        if kind not in {"replace", "delete", "insert_before", "insert_after"} or pid not in nodes or pid in touched:
            fail("correction_invalid_action")
        touched.add(pid)
        node, row = nodes[pid], by_id[pid]
        if not row["editable"]:
            fail("correction_paragraph_controls")
        page, bbox = action["source_page"], action["source_bbox"]
        if type(page) is not int or page not in selected_pages:
            fail("correction_source_page_required")
        if (type(bbox) is not list or len(bbox) != 4 or any(type(v) not in {int, float} or not 0 <= v <= 1 for v in bbox)
                or not bbox[0] < bbox[2] or not bbox[1] < bbox[3]):
            fail("correction_source_region_required")
        before = row["text"] if kind in {"replace", "delete"} else ""
        text = checked_text(action["text"]) if kind != "delete" else ""
        if kind == "delete" and action["text"] != "":
            fail("correction_invalid_action")
        reset = False
        if kind == "delete":
            parent = node.getparent()
            if parent.tag == W + "tc" and len(parent.findall(W + "p")) <= 1:
                fail("correction_cell_requires_paragraph")
            if node.find(W + "pPr/" + W + "pageBreakBefore") is not None:
                fail("correction_paragraph_controls")
            parent.remove(node)
        else:
            target = node
            if kind.startswith("insert_"):
                target = deepcopy(node)
                ppr = target.find(W + "pPr")
                if ppr is not None:
                    for tag in ("pageBreakBefore", "keepNext", "keepLines"):
                        inherited = ppr.find(W + tag)
                        if inherited is not None:
                            ppr.remove(inherited)
                parent = node.getparent()
                parent.insert(parent.index(node) + (kind == "insert_after"), target)
                from .ordinary_layout_contracts import encode
                node_ids[id(target)] = "insert_" + digest(raw + encode(action))[:32]
                provenance[node_ids[id(target)]] = {"parent_paragraph_id": pid, "association_status": "operator_inserted",
                    "regions": [{"page_number": page, "bbox_normalized": deepcopy(bbox)}]}
            reset = _replace(target, text, language)
            if kind == "replace":
                provenance[pid]["association_status"] = "operator_corrected_inherited_coarse_association"
        changes.append({**deepcopy(action), "before": before, "after": text,
                        "formatting_reset": reset, "source_association": "operator_supplied_coarse_region"})
    for name, root in roots.items():
        members[name] = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        for info in infos:
            archive.writestr(info, members[info.filename])
    result = output.getvalue()
    if not any(row["text"].strip() for row in paragraphs(result)):
        fail("correction_delivery_empty")
    mapping = [{**provenance[node_ids[id(node)]], "paragraph_id": node_ids[id(node)], "part_uri": name, "location": path}
               for name, node, path in _nodes(roots)]
    if len({r["paragraph_id"] for r in mapping}) != len(mapping):
        fail("correction_duplicate_paragraph_id")
    return result, changes, mapping


def word_changes(base, working):
    """Import wording only when every story/table/control owner is unchanged."""
    a, b = _inventory(base), _inventory(working)
    original_members, _, original_roots = package(base)
    edited_members, _, edited_roots = package(working)
    try:
        sections_equal = word_section_signature(original_members) == word_section_signature(edited_members)
    except ValueError:
        fail("correction_word_section_changed", 409)
    if not sections_equal:
        fail("correction_word_section_changed", 409)
    def relationships(members):
        return [(name, tuple(sorted(tuple(sorted((k,v) for k,v in child.attrib.items() if k != "Id"))
                    for child in etree.fromstring(raw)
                    if not child.get("Type", "").endswith(("/stylesWithEffects", "/footnotes", "/endnotes", "/thumbnail")))))
                for name, raw in sorted(members.items()) if name.endswith(".rels")]
    if relationships(original_members) != relationships(edited_members):
        fail("correction_word_relationships_changed", 409)
    def skeleton(value):
        return tuple((name, tuple((row[:-1] + (tuple((k, v) for k, v in row[-1] if k != W + "t"),))
            if len(row) == 3 and row[1] == W + "p" else row for row in rows)) for name, rows in value if STORY.fullmatch(name))
    def uneditable_stories(members):
        rows = []
        for name, raw in sorted(members.items()):
            if not re.fullmatch(r"word/(footnotes|endnotes)\.xml", name):
                continue
            root = etree.fromstring(raw)
            substantive = []
            for note in root:
                if note.get(W + "type") in {"separator", "continuationSeparator"}:
                    # Word may create these system-only stories during a normal save.
                    if any(n.tag not in {W+"footnote", W+"endnote", W+"p", W+"pPr", W+"spacing", W+"r", W+"separator", W+"continuationSeparator"} for n in note.iter()):
                        fail("correction_word_story_unsupported", 409)
                    continue
                substantive.append(etree.tostring(note, method="c14n"))
            if substantive:
                rows.append((name, substantive))
        return rows
    if uneditable_stories(original_members) != uneditable_stories(edited_members):
        fail("correction_word_story_unsupported", 409)
    if skeleton(a) != skeleton(b):
        fail("correction_word_structure_unsupported", 409)
    before, after = paragraphs(base), paragraphs(working)
    if [(r["part_uri"], r["location"]) for r in before] != [(r["part_uri"], r["location"]) for r in after]:
        fail("correction_word_structure_unsupported", 409)
    changes = []
    for old, new in zip(before, after):
        if old["text"] != new["text"]:
            checked_text(new["text"])
            if not old["editable"] or not new["editable"]:
                fail("correction_paragraph_controls")
            changes.append({"kind": "replace", "paragraph_id": old["paragraph_id"],
                "before": old["text"], "after": new["text"], "formatting_reset": False,
                "source_association": "source_comparison_required"})
    if not changes:
        fail("correction_no_text_changes")
    return changes


def count_correction_words(raw):
    """Count verified body/header/footer story text, including moved source text."""
    _, _, roots = package(raw)
    total = 0
    for _, node, _ in _nodes(roots):
        parts = []
        fields = []
        for item in node.iter():
            if item.tag == W + "fldChar":
                kind = item.get(W + "fldCharType")
                if kind == "begin":
                    fields.append(False)
                elif kind == "end" and fields:
                    fields.pop()
            elif item.tag == W + "instrText" and fields:
                if re.match(r"\s*PAGE(?:\s|$)", item.text or "", re.I):
                    fields[-1] = True
            elif item.tag == W + "t" and not any(fields) and not any(
                    ancestor.tag == W + "fldSimple" and re.match(r"\s*PAGE(?:\s|$)", ancestor.get(W+"instr", ""), re.I)
                    for ancestor in item.iterancestors()):
                parts.append(item.text or "")
            elif item.tag in {W+"tab", W+"br", W+"cr"}:
                parts.append(" ")
        total += len("".join(parts).split())
    return total
