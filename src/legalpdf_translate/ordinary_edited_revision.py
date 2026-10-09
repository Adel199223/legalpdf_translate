"""Qualify a Word formatting edit against an immutable ordinary candidate."""
from __future__ import annotations

from io import BytesIO
import re
from zipfile import BadZipFile, ZipFile

from lxml import etree

from .ordinary_layout_contracts import fail

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_TEXT = {_W + "t", _W + "tab", _W + "br", _W + "cr", _W + "instrText",
         _W + "delText", _W + "fldChar", _W + "sym"}
_CONTENT = {_W + "p", _W + "tbl", _W + "tr", _W + "tc"}


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
                rows = []
                for node in body.iter():
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
