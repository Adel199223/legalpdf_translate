"""Qualify a Word formatting edit against an immutable ordinary candidate."""
from __future__ import annotations

from io import BytesIO
import re
from zipfile import BadZipFile, ZipFile

from lxml import etree

from .ordinary_layout_contracts import fail

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_TEXT = {_W + "t", _W + "tab", _W + "br", _W + "cr", _W + "instrText",
         _W + "delText", _W + "fldChar", _W + "sym",
         _W + "footnoteReference", _W + "endnoteReference"}
_CONTENT = {_W + "p", _W + "tbl", _W + "tr", _W + "tc"}
_NOTES = {_W + "footnote", _W + "endnote"}


def _system_separator_note(note, note_tag):
    """Only Word's empty reserved separator entries are serialization furniture."""
    controls = {("separator", "-1"): "separator", ("continuationSeparator", "0"): "continuationSeparator"}
    control = controls.get((note.get(_W + "type"), note.get(_W + "id")))
    if (note.tag != note_tag or control is None
            or set(note.attrib) != {_W + "type", _W + "id"}):
        return False
    if len(note) != 1 or note[0].tag != _W + "p":
        return False
    paragraph = note[0]
    metadata = {_W + key for key in ("rsidR", "rsidRDefault", "rsidP", "rsidRPr", "rsidDel")}
    metadata.update("{http://schemas.microsoft.com/office/word/2010/wordml}" + key
                    for key in ("paraId", "textId"))
    children = list(paragraph)
    if children and children[0].tag == _W + "pPr":
        properties = children.pop(0)
        if (properties.attrib or len(properties) > 1
                or any(child.tag != _W + "spacing" or len(child)
                       or set(child.attrib) - {_W + key for key in (
                           "before", "after", "line", "lineRule", "beforeAutospacing",
                           "afterAutospacing", "beforeLines", "afterLines")}
                       for child in properties)):
            return False
    if (set(paragraph.attrib) - metadata or len(children) != 1
            or children[0].tag != _W + "r" or children[0].attrib
            or len(children[0]) != 1 or children[0][0].tag != _W + control
            or children[0][0].attrib or len(children[0][0])):
        return False
    return all(not (node.text or "").strip() and not (node.tail or "").strip()
               for node in note.iter())


def _normal_note(note):
    try:
        return (int(note.get(_W + "id", "")) > 0
                and note.get(_W + "type") in {None, "normal"}
                and not set(note.attrib) - {_W + "id", _W + "type"})
    except ValueError:
        return False


def _location(node, root):
    steps = []
    while node is not root:
        parent = node.getparent()
        if parent is None:
            fail("edited_docx_invalid", 409)
        index = 1
        for sibling in parent:
            if sibling is node:
                break
            if sibling.tag == node.tag:
                index += 1
        steps.append((node.tag, index))
        node = parent
    return tuple(reversed(steps))


def _inventory(raw: bytes) -> tuple:
    """Keep exact ordered text and ownership positions; allow Word style edits."""
    try:
        with ZipFile(BytesIO(raw)) as archive:
            names = archive.namelist()
            if (len(names) > 1024 or len(names) != len(set(names))
                    or "word/document.xml" not in names
                    or sum(i.file_size for i in archive.infolist()) > 128 * 1024 * 1024
                    or any(i.file_size > 32 * 1024 * 1024 or i.flag_bits & 1 for i in archive.infolist())):
                fail("edited_docx_invalid", 409)
            stories = sorted(name for name in names if name == "word/document.xml" or
                re.fullmatch(r"word/(?:header\d+|footer\d+|footnotes|endnotes|comments)\.xml", name))
            result = []
            for name in stories:
                root = etree.fromstring(archive.read(name),
                    parser=etree.XMLParser(resolve_entities=False, no_network=True))
                body = root.find(_W + "body") if name == "word/document.xml" else root
                if body is None:
                    fail("edited_docx_invalid", 409)
                note_tag = {"word/footnotes.xml": _W + "footnote",
                            "word/endnotes.xml": _W + "endnote"}.get(name)
                removed = 0
                if note_tag and root.tag == note_tag + "s":
                    for note in list(root):
                        if _system_separator_note(note, note_tag):
                            root.remove(note)
                            removed += 1
                    # An arbitrary empty added story is still an ownership
                    # change. Omit only one emptied by verified system notes.
                    if (removed and len(root) == 0 and not (root.text or "").strip()
                            and not set(root.attrib) - {
                                "{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable"}):
                        continue
                rows = []
                for node in body.iter():
                    if node.tag in _NOTES:
                        value = (tuple(sorted(node.attrib.items())) if _normal_note(node)
                                 else etree.tostring(node, method="c14n"))
                        rows.append((_location(node, body), node.tag, value))
                        continue
                    if node.tag not in _CONTENT:
                        continue
                    if node.tag != _W + "p":
                        rows.append((_location(node, body), node.tag))
                        continue
                    tokens = []
                    for child in node.iter():
                        if child.tag in _TEXT:
                            if child.tag in {_W + "t", _W + "instrText", _W + "delText"}:
                                tokens.append((child.tag, child.text or ""))
                            elif child.tag == _W + "tab":
                                tokens.append(("tab", ""))
                            else:
                                tokens.append((child.tag, tuple(sorted(child.attrib.items()))))
                        elif child.tag in {_W + "drawing", _W + "object", _W + "pict"}:
                            tokens.append(("object", etree.tostring(child, method="c14n")))
                        elif child.tag == _W + "fldSimple":
                            tokens.append(("field", tuple(sorted(child.attrib.items()))))
                    # Splitting or merging text runs for formatting does not
                    # change ordered wording, tabs, fields or breaks.
                    collapsed = []
                    for kind, value in tokens:
                        if kind in {_W + "t", _W + "instrText", _W + "delText"} and collapsed and collapsed[-1][0] == kind:
                            collapsed[-1] = (kind, collapsed[-1][1] + value)
                        else:
                            collapsed.append((kind, value))
                    rows.append((_location(node, body), node.tag, tuple(collapsed)))
                result.append((name, tuple(rows)))
        return tuple(result)
    except (BadZipFile, KeyError, ValueError, etree.XMLSyntaxError, OverflowError):
        fail("edited_docx_invalid", 409)


def qualify_edited_docx(candidate: bytes, edited: bytes) -> None:
    """A source map remains valid only for unchanged paragraph ownership/text."""
    if _inventory(candidate) != _inventory(edited):
        fail("edited_layout_rebase_required", 409)
