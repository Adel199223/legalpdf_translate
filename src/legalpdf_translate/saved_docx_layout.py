"""Bounded, provider-free saved Word import and explicit source-region decisions.

This profile owns no translation history and makes no OCR/visual acceptance claim.
Text projections are for review offsets; typed tokens retain their XML identity.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
import math
import posixpath
import re
import unicodedata
from zipfile import BadZipFile, ZipFile

from lxml import etree

VERSION = "saved_docx_source_region_review_v1"
DECISIONS_VERSION = "saved_docx_layout_decisions_v1"
PHRASE_POLICY = "conservative_phrase_boundaries_v1"
DOCX_MAX_BYTES = 32 * 1024 * 1024
EXPANDED_MAX_BYTES = 128 * 1024 * 1024
MEMBER_MAX_BYTES = 32 * 1024 * 1024
MAX_MEMBERS = 2048
MAX_PARAGRAPHS = 10000
MAX_CODEPOINTS = 8000000
PDF_MAX_BYTES = 64 * 1024 * 1024
MAX_SOURCE_PAGES = 100
MAX_PAGE_PIXELS = 12000000
MAX_RASTER_BYTES = 256 * 1024 * 1024
MAX_DECISION_BYTES = 16 * 1024 * 1024
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_FIXED_PARTS = frozenset({"[Content_Types].xml", "_rels/.rels", "docProps/core.xml",
    "docProps/app.xml", "docProps/thumbnail.jpeg", "word/document.xml",
    "word/_rels/document.xml.rels", "word/styles.xml", "word/stylesWithEffects.xml",
    "word/settings.xml", "word/webSettings.xml", "word/fontTable.xml", "word/numbering.xml"})
_PART_PATTERN = re.compile(r"(?:word/(?:theme/theme[0-9]+|header[0-9]+|footer[0-9]+)\.xml|"
    r"customXml/(?:item[0-9]+|itemProps[0-9]+)\.xml|customXml/_rels/item[0-9]+\.xml\.rels)\Z")
_REL_TYPES = frozenset({"officeDocument", "metadata/core-properties", "extended-properties",
    "thumbnail", "styles", "stylesWithEffects", "settings", "webSettings", "fontTable", "theme",
    "customXml", "customXmlProps", "numbering", "header", "footer"})
_RPROPS = frozenset({"rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps",
    "strike", "dstrike", "u", "color", "highlight", "sz", "szCs", "kern", "position",
    "spacing", "rtl", "cs", "lang", "vertAlign", "noProof", "snapToGrid"})
_PPROPS = frozenset({"pStyle", "keepNext", "keepLines", "pageBreakBefore", "widowControl",
    "tabs", "spacing", "ind", "jc", "textAlignment", "bidi", "contextualSpacing",
    "adjustRightInd", "snapToGrid", "suppressAutoHyphens", "outlineLvl", "shd", "pBdr", "rPr"})
_ROLES = frozenset({"institution", "reference", "recipient", "heading", "body", "list",
    "signature", "source_folio"})
_BIDI_OPEN = {"\u202a": "embedding", "\u202b": "embedding", "\u202d": "embedding",
    "\u202e": "embedding", "\u2066": "isolate", "\u2067": "isolate", "\u2068": "isolate"}
_LITERALS = re.compile(r"\[\[.*?\]\]|https?://[^\s<>]+|[\w.+-]+@[\w.-]+\.[\w-]+|"
    r"(?<!\w)(?:(?:[$€£]\s*\d[\d., ]*|\d[\d.,]*\s*[$€£])|"
    r"\d{3} \d{3} \d{3}|\d{1,4}(?:[/.:,-]\d{1,4})+(?:[A-Za-z][\w./-]*)?)(?!\w)", re.DOTALL)


class SavedDocxLayoutError(ValueError):
    """Content-free failure suitable for the local service/API."""

    def __init__(self, code: str, status: int = 422):
        self.code = code
        self.status = self.status_code = status
        super().__init__(code)


def _fail(code: str):
    raise SavedDocxLayoutError(code)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError):
        _fail("invalid_json_value")


def _xml(raw: bytes):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper() or b"\x00" in raw:
        _fail("unsupported_xml_declaration")
    try:
        root = etree.fromstring(raw, etree.XMLParser(resolve_entities=False, no_network=True,
            load_dtd=False, huge_tree=False, remove_comments=False))
        if root.getprevious() is not None or root.getnext() is not None:
            _fail("unsupported_xml_prolog")
        return root
    except (etree.XMLSyntaxError, ValueError, RecursionError):
        _fail("invalid_part_xml")


def _c14n(node) -> str:
    return etree.tostring(node, method="c14n", exclusive=True).decode("utf-8") if node is not None else ""


def _name(node) -> str:
    if not isinstance(node.tag, str) or not node.tag.startswith(W):
        _fail("unsupported_xml_node")
    return node.tag[len(W):]


def _on(node) -> bool:
    return node is not None and node.get(W + "val", "1") not in {"0", "false", "off"}


def _package(raw: bytes) -> tuple[dict[str, bytes], list]:
    if type(raw) is not bytes or not 0 < len(raw) <= DOCX_MAX_BYTES:
        _fail("docx_size_limit")
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if not 0 < len(infos) <= MAX_MEMBERS:
                _fail("docx_member_limit")
            if len({entry.filename for entry in infos}) != len(infos):
                _fail("duplicate_package_member")
            if sum(entry.file_size for entry in infos) > EXPANDED_MAX_BYTES:
                _fail("docx_expanded_size_limit")
            members = {}
            for entry in infos:
                name = entry.filename
                if (entry.flag_bits & 1 or entry.file_size > MEMBER_MAX_BYTES
                        or "\\" in name or ":" in name or "%" in name or name.startswith("/")
                        or any(part in {"", ".", ".."} for part in name.split("/"))):
                    _fail("unsupported_package_member")
                if name not in _FIXED_PARTS and not _PART_PATTERN.fullmatch(name):
                    _fail("unsupported_package_part")
                if entry.compress_type not in {0, 8}:
                    _fail("unsupported_package_compression")
                data = archive.read(entry)
                if len(data) != entry.file_size:
                    _fail("package_member_size_mismatch")
                members[name] = data
    except SavedDocxLayoutError:
        raise
    except (BadZipFile, OSError, RuntimeError, KeyError, ValueError, NotImplementedError):
        _fail("invalid_docx_package")
    if not {"word/document.xml", "word/styles.xml", "[Content_Types].xml", "_rels/.rels"} <= members.keys():
        _fail("incomplete_docx_package")
    for name, data in members.items():
        if name.endswith((".xml", ".rels")):
            root = _xml(data)
            if name.endswith(".rels"):
                origin = "" if name == "_rels/.rels" else posixpath.dirname(name).removesuffix("/_rels")
                ids = set()
                for rel in root:
                    target, kind = rel.get("Target", ""), rel.get("Type", "")
                    short = "metadata/core-properties" if kind.endswith("/metadata/core-properties") else kind.rsplit("/", 1)[-1]
                    if (rel.tag != "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
                            or rel.get("TargetMode", "Internal") != "Internal" or not rel.get("Id")
                            or rel.get("Id") in ids or short not in _REL_TYPES or not target
                            or any(char in target for char in ("\\", ":", "%", "?", "#"))):
                        _fail("unsupported_relationship")
                    resolved = posixpath.normpath(posixpath.join(origin, target))
                    if resolved.startswith(("../", "/")) or resolved not in members:
                        _fail("invalid_relationship_target")
                    ids.add(rel.get("Id"))
                    if short == "officeDocument" and resolved != "word/document.xml":
                        _fail("unsupported_main_document")
            if name == "[Content_Types].xml":
                main = [n for n in root if n.get("PartName") == "/word/document.xml"]
                if (len(main) != 1 or main[0].get("ContentType") !=
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
                        or any(any(s in n.get("ContentType", "").lower() for s in
                                   ("macro", "oleobject", "signature", "vba")) for n in root)):
                    _fail("unsupported_content_type")
            if name == "word/settings.xml" and any(etree.QName(n).localname in
                    {"attachedTemplate", "mailMerge", "documentProtection", "writeProtection",
                     "mirrorMargins", "gutterAtTop"} for n in root.iter()):
                _fail("unsupported_document_settings")
    return members, infos


def _properties(node, *, paragraph=False):
    if node is None:
        return
    seen = set()
    for child in node:
        name = _name(child)
        if name in seen or name not in (_PPROPS if paragraph else _RPROPS):
            _fail("unsupported_paragraph_properties" if paragraph else "unsupported_run_properties")
        seen.add(name)
        if name == "rPr" and paragraph:
            _properties(child)
        elif name in {"tabs", "pBdr"} and paragraph:
            expected = {"tab"} if name == "tabs" else {"top", "left", "bottom", "right", "between", "bar"}
            if any(_name(n) not in expected or len(n) or n.text for n in child):
                _fail("unsupported_paragraph_properties")
        elif len(child) or child.text:
            _fail("unsupported_property_content")
        if child.tail and child.tail.strip():
            _fail("unowned_xml_text")


def _styles(members):
    root = _xml(members["word/styles.xml"])
    styles = {}
    for style in root.findall(W + "style"):
        identifier = style.get(W + "styleId")
        if not identifier or identifier in styles:
            _fail("invalid_style_identity")
        styles[identifier] = style
    defaults = root.find(W + "docDefaults")
    default_rpr = defaults.find(W + "rPrDefault/" + W + "rPr") if defaults is not None else None
    default_ppr = defaults.find(W + "pPrDefault/" + W + "pPr") if defaults is not None else None
    return styles, default_rpr, default_ppr


def _style_chain(identifier, styles):
    chain, seen = [], set()
    while identifier:
        if identifier in seen or identifier not in styles or len(seen) >= 32:
            _fail("unsupported_style_inheritance")
        seen.add(identifier)
        style = styles[identifier]
        chain.insert(0, style)
        parent = style.find(W + "basedOn")
        identifier = parent.get(W + "val") if parent is not None else None
    return chain


def _effective(paragraph, run, context):
    styles, default_rpr, default_ppr = context
    ppr, rpr = paragraph.find(W + "pPr"), run.find(W + "rPr")
    ps = ppr.find(W + "pStyle") if ppr is not None else None
    default_style = next((s.get(W + "styleId") for s in styles.values()
                          if s.get(W + "type") == "paragraph" and s.get(W + "default") == "1"), None)
    pchain = _style_chain(ps.get(W + "val") if ps is not None else default_style, styles)
    rs = rpr.find(W + "rStyle") if rpr is not None else None
    rchain = _style_chain(rs.get(W + "val") if rs is not None else None, styles)
    properties = [default_rpr, *(s.find(W + "rPr") for s in pchain),
                  *(s.find(W + "rPr") for s in rchain), rpr]
    pproperties = [default_ppr, *(s.find(W + "pPr") for s in pchain), ppr]
    for props in properties:
        if props is not None and any(_on(props.find(W + tag)) for tag in ("vanish", "webHidden", "specVanish")):
            _fail("hidden_text_unsupported")
        if props is not None and props.find(W + "fitText") is not None:
            _fail("unsupported_run_fitting")
    if any(props is not None and any(props.find(W + tag) is not None for tag in
           ("numPr", "framePr", "sectPr", "pPrChange")) for props in pproperties):
        _fail("unsupported_inherited_paragraph_properties")
    def size(tag):
        values = [p.find(W + tag).get(W + "val") for p in properties
                  if p is not None and p.find(W + tag) is not None]
        try:
            value = int(values[-1]) / 2 if values else 11.0
        except (ValueError, TypeError):
            _fail("invalid_font_size")
        if not 0 < value <= 1638:
            _fail("invalid_font_size")
        return value
    bidi = [p.find(W + "bidi") for p in pproperties if p is not None and p.find(W + "bidi") is not None]
    underline = [p.find(W + "u") for p in properties if p is not None and p.find(W + "u") is not None]
    return {"size_pt": size("sz"), "cs_size_pt": size("szCs"), "bidi": _on(bidi[-1]) if bidi else False,
            "underline_attrs": dict(underline[-1].attrib) if underline else None,
            "page_break_before": any(_on(p.find(W + "pageBreakBefore")) for p in pproperties if p is not None)}


def _paragraph_inventory(paragraph, context, *, ordinal=1):
    if paragraph.tag != W + "p" or any(k not in {W + "rsidR", W + "rsidRDefault", W + "rsidP",
            W + "rsidRPr", "{http://schemas.microsoft.com/office/word/2010/wordml}paraId",
            "{http://schemas.microsoft.com/office/word/2010/wordml}textId"} for k in paragraph.attrib):
        _fail("unsupported_body_paragraph")
    ppr = paragraph.find(W + "pPr")
    _properties(ppr, paragraph=True)
    if len(paragraph.findall(W + "pPr")) > 1 or (ppr is not None and paragraph.index(ppr) != 0):
        _fail("invalid_paragraph_property_order")
    tokens, runs, offset, pages = [], [], 0, []
    effective_break = False
    for child in paragraph:
        if child is ppr:
            continue
        if child.tag == W + "proofErr":
            if len(child) or child.text or child.get(W + "type") not in {"spellStart", "spellEnd", "gramStart", "gramEnd"}:
                _fail("unsupported_proofing_marker")
            continue
        if child.tag != W + "r" or any(k not in {W + "rsidR", W + "rsidRPr", W + "rsidDel"} for k in child.attrib):
            _fail("unsupported_body_content")
        rpr = child.find(W + "rPr")
        _properties(rpr)
        if len(child.findall(W + "rPr")) > 1 or (rpr is not None and child.index(rpr) != 0):
            _fail("invalid_run_property_order")
        effective = _effective(paragraph, child, context)
        effective_break |= effective["page_break_before"]
        start, number = offset, len(runs)
        for node in child:
            if node is rpr:
                continue
            kind = _name(node)
            if len(node) or (kind != "t" and node.text):
                _fail("unsupported_run_content")
            if kind == "t":
                if any(key != XML_SPACE or value not in {"preserve", "default"} for key, value in node.attrib.items()):
                    _fail("unsupported_text_attributes")
                text = node.text or ""
            elif kind in {"tab", "cr"} and not node.attrib:
                text = "\t" if kind == "tab" else "\n"
            elif kind == "br" and set(node.attrib) <= {W + "type"}:
                break_type = node.get(W + "type", "textWrapping")
                if break_type not in {"textWrapping", "page"}:
                    _fail("unsupported_break_type")
                kind = "page_break" if break_type == "page" else "line_break"
                text = "\f" if break_type == "page" else "\n"
                if break_type == "page":
                    pages.append(offset)
            else:
                _fail("unsupported_run_content")
            token = {"kind": kind, "text": text, "start": offset, "end": offset + len(text), "run": number}
            if kind == "t":
                token["xml_space"] = node.get(XML_SPACE)
            tokens.append(token)
            offset += len(text)
        runs.append({"index": number, "start": start, "end": offset, "rpr_xml": _c14n(rpr),
                     "size_pt": effective["size_pt"], "cs_size_pt": effective["cs_size_pt"],
                     "underline_attrs": effective["underline_attrs"]})
    # Even an empty paragraph may inherit pageBreakBefore or unsupported numbering.
    dummy = etree.Element(W + "r")
    paragraph_effective = _effective(paragraph, dummy, context)
    effective_break |= paragraph_effective["page_break_before"]
    if len(pages) > 1 or (pages and pages[0] != offset - 1):
        _fail("nonterminal_page_break")
    if offset > MAX_CODEPOINTS:
        _fail("docx_text_limit")
    return {"id": f"p{ordinal:06d}", "ordinal": ordinal, "text": "".join(t["text"] for t in tokens),
        "has_page_break": bool(pages or effective_break), "bidi": paragraph_effective["bidi"], "tokens": tokens, "runs": runs,
        "ppr_xml": _c14n(ppr), "paragraph_sha256": _sha(_c14n(paragraph).encode()),
        "content_sha256": _sha(_canonical(_content_tokens(tokens)))}


def _content_tokens(tokens):
    """Run/text-node segmentation is presentation; token kind is content."""
    result = []
    for token in tokens:
        kind, text = token["kind"], token["text"]
        if kind == "t" and result and result[-1][0] == "t":
            result[-1][1] += text
        elif kind != "t" or text:
            result.append([kind, text])
    return result


def _story(root, context):
    # Inherited static furniture and a single, well-formed PAGE field only.
    field_state = None
    field_count = 0
    for paragraph in root:
        if paragraph.tag != W + "p":
            _fail("unsupported_inherited_furniture")
        copy = deepcopy(paragraph)
        for run in list(copy):
            if run.tag != W + "r":
                continue
            for node in list(run):
                if node.tag == W + "fldChar":
                    kind = node.get(W + "fldCharType")
                    if len(node) or set(node.attrib) != {W + "fldCharType"}:
                        _fail("unsupported_footer_field")
                    if kind == "begin" and field_state is None:
                        field_state = "instruction"
                        field_count += 1
                    elif kind == "separate" and field_state == "page":
                        field_state = "cache"
                    elif kind == "end" and field_state == "cache":
                        field_state = None
                    else:
                        _fail("unsupported_footer_field")
                    run.remove(node)
                elif node.tag == W + "instrText":
                    if field_state != "instruction" or len(node) or not re.fullmatch(r"\s*PAGE\s*", node.text or "", re.I):
                        _fail("unsupported_footer_field")
                    field_state = "page"
                    run.remove(node)
                elif node.tag == W + "t" and field_state is not None:
                    if field_state != "cache" or not re.fullmatch(r"[0-9]*", node.text or ""):
                        _fail("unsupported_footer_field")
        _paragraph_inventory(copy, context)
        if field_state is not None:
            _fail("unsupported_footer_field")
    if field_count > 1:
        _fail("unsupported_footer_field")


def _load_docx(docx_bytes):
    members, infos = _package(docx_bytes)
    root = _xml(members["word/document.xml"])
    if root.tag != W + "document" or len(root) != 1 or root[0].tag != W + "body":
        _fail("unsupported_document_body")
    body = root[0]
    if not len(body) or body[-1].tag != W + "sectPr" or sum(n.tag == W + "sectPr" for n in body) != 1:
        _fail("unsupported_document_sections")
    section = body[-1]
    allowed_section = {"headerReference", "footerReference", "pgSz", "pgMar", "cols", "docGrid",
                       "type", "pgNumType", "titlePg", "bidi", "rtlGutter"}
    if any(_name(n) not in allowed_section or len(n) or n.text for n in section):
        _fail("unsupported_section_properties")
    cols = section.find(W + "cols")
    if cols is not None and cols.get(W + "num", "1") != "1":
        _fail("unsupported_section_columns")
    margins = section.find(W + "pgMar")
    if margins is not None and margins.get(W + "gutter", "0") != "0":
        _fail("unsupported_section_gutter")
    paragraphs = list(body)[:-1]
    if not 0 < len(paragraphs) <= MAX_PARAGRAPHS:
        _fail("docx_paragraph_limit")
    context = _styles(members)
    rows = [_paragraph_inventory(p, context, ordinal=i) for i, p in enumerate(paragraphs, 1)]
    if sum(len(p["text"]) for p in rows) > MAX_CODEPOINTS:
        _fail("docx_text_limit")
    for name, data in members.items():
        if re.fullmatch(r"word/(?:header|footer)[0-9]+\.xml", name):
            _story(_xml(data), context)
    return members, infos, root, rows, context


def inspect_docx(docx_bytes: bytes, target_lang: str) -> dict:
    """Inventory every supported body token without altering the supplied file."""
    if target_lang not in {"EN", "FR", "AR"}:
        _fail("unsupported_target_language")
    try:
        members, _, root, rows, _ = _load_docx(docx_bytes)
        return {"version": VERSION, "docx_sha256": _sha(docx_bytes), "target_lang": target_lang,
            "paragraphs": rows, "package_sha256": {name: _sha(raw) for name, raw in sorted(members.items())},
            "section_sha256": _sha(_c14n(root[0][-1]).encode()),
            "offset_policy": "verbatim_text_tab_lf_formfeed_typed_v1", "phrase_policy": PHRASE_POLICY}
    except SavedDocxLayoutError:
        raise
    except (TypeError, ValueError, KeyError, IndexError, OverflowError, AttributeError):
        _fail("invalid_saved_docx")


def _pages(pages):
    if type(pages) is not list or not 0 < len(pages) <= MAX_SOURCE_PAGES:
        _fail("invalid_source_pages")
    result = {}
    for number, page in enumerate(pages, 1):
        if (type(page) is not dict or type(page.get("page_number")) is not int or page["page_number"] != number
                or any(type(page.get(k)) is not int or page[k] <= 0 for k in ("width_px", "height_px"))
                or page["width_px"] * page["height_px"] > MAX_PAGE_PIXELS
                or type(page.get("image_sha256")) is not str or not _HASH.fullmatch(page["image_sha256"])):
            _fail("invalid_source_page")
        result[number] = page
    return result


def _snapshot(snapshot):
    if type(snapshot) is not dict or snapshot.get("version") != VERSION or snapshot.get("target_lang") not in {"EN", "FR", "AR"}:
        _fail("invalid_snapshot")
    rows = snapshot.get("paragraphs")
    if type(rows) is not list or not 0 < len(rows) <= MAX_PARAGRAPHS:
        _fail("invalid_snapshot")
    if any(type(row) is not dict or row.get("id") != f"p{i:06d}" or type(row.get("text")) is not str
           or type(row.get("has_page_break")) is not bool for i, row in enumerate(rows, 1)):
        _fail("invalid_snapshot")
    return rows


def default_decisions(snapshot: dict, pages: list) -> dict:
    rows = _snapshot(snapshot)
    _pages(pages)
    return {"version": DECISIONS_VERSION, "paragraphs": [
        {"paragraph_id": row["id"], "regions": [], "unmapped_reason": "", "role": "body",
         "alignment": "inherit", "space_before_pt": None, "space_after_pt": None,
         "heading_level": 0, "heading_size_pt": None, "bold": False, "italic": False,
         "underline": False, "emphasis": []} for row in rows],
        "bands": [{"kind": "flow", "groups": [{"paragraph_ids": [row["id"] for row in rows], "panel": False}]}],
        "review": {"reviewer_kind": "operator_review", "reviewer": "", "note": "",
                   "pages_reviewed": [], "document_reviewed": False}}


def _keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        _fail("invalid_decision_schema")


def _number(value, minimum, maximum):
    return type(value) in {int, float} and math.isfinite(value) and minimum <= value <= maximum


def _text_field(value, maximum=2000):
    return type(value) is str and len(value) <= maximum and not any(ord(c) < 32 and c not in "\n\t\r" for c in value)


def _protected_ranges(row):
    text = row["text"]
    ranges = [m.span() for m in _LITERALS.finditer(text)]
    stack = []
    for index, char in enumerate(text):
        if char in _BIDI_OPEN:
            if len(stack) >= 128:
                _fail("unsafe_emphasis_bidi_scope")
            stack.append((_BIDI_OPEN[char], index))
        elif char in {"\u202c", "\u2069"}:
            kind = "embedding" if char == "\u202c" else "isolate"
            if not stack or stack[-1][0] != kind:
                _fail("unsafe_emphasis_bidi_scope")
            _, start = stack.pop()
            ranges.append((start, index + 1))
    if stack:
        _fail("unsafe_emphasis_bidi_scope")
    for run in row["runs"]:
        start, end = run["start"], run["end"]
        raw = text[start:end]
        if "\u200e" in raw:
            if raw.strip().startswith("\u200e") and raw.strip().endswith("\u200e"):
                ranges.append((start, end))
            else:
                # A saved control without a recognized complete literal owner
                # is retained, but cannot acquire a guessed new cut policy.
                ranges.append((0, len(text)))
    return ranges


def _phrase_edge(text, offset):
    if offset in {0, len(text)}:
        return True
    left, right = text[offset - 1], text[offset]
    if not (left in " \t\n\r\f" or right in " \t\n\r\f"):
        return False
    if (unicodedata.category(right).startswith("M") or unicodedata.category(left).startswith("C")
            or unicodedata.category(right).startswith("C") or right in "\u200c\u200d"
            or 0x1F3FB <= ord(right) <= 0x1F3FF):
        return False
    return True


def _emphasis(row, spans):
    if type(spans) is not list or len(spans) > 1000:
        _fail("invalid_emphasis_spans")
    if not spans:
        return
    ranges = _protected_ranges(row)
    previous = 0
    for span in spans:
        _keys(span, {"start", "end", "bold", "italic", "underline"})
        start, end = span["start"], span["end"]
        if (type(start) is not int or type(end) is not int or not previous <= start < end <= len(row["text"])
                or any(type(span[k]) is not bool for k in ("bold", "italic", "underline"))
                or not any(span[k] for k in ("bold", "italic", "underline"))):
            _fail("invalid_emphasis_spans")
        previous = end
        if (not _phrase_edge(row["text"], start) or not _phrase_edge(row["text"], end)
                or any(a < cut < b for a, b in ranges for cut in (start, end))
                or any(t["kind"] != "t" and start < t["end"] and end > t["start"] for t in row["tokens"])):
            _fail("unsafe_emphasis_boundary")


def validate_decisions(snapshot: dict, pages: list, decisions: dict, require_review: bool = False) -> dict:
    """Validate complete ownership/order even in drafts; return a detached value."""
    try:
        return _validate_decisions(snapshot, pages, decisions, require_review)
    except SavedDocxLayoutError:
        raise
    except (TypeError, ValueError, KeyError, IndexError, OverflowError, AttributeError, RecursionError):
        _fail("invalid_decisions")


def _validate_decisions(snapshot, pages, decisions, require_review):
    rows, frames = _snapshot(snapshot), _pages(pages)
    if len(_canonical(decisions)) > MAX_DECISION_BYTES:
        _fail("decision_size_limit")
    _keys(decisions, {"version", "paragraphs", "bands", "review"})
    if decisions["version"] != DECISIONS_VERSION or type(require_review) is not bool:
        _fail("unsupported_decisions_version")
    choices = decisions["paragraphs"]
    if type(choices) is not list or len(choices) != len(rows):
        _fail("incomplete_paragraph_decisions")
    expected = default_decisions(snapshot, pages)["paragraphs"][0]
    for row, choice in zip(rows, choices):
        _keys(choice, expected)
        if choice["paragraph_id"] != row["id"]:
            _fail("paragraph_decision_order")
        if (choice["role"] not in _ROLES or choice["alignment"] not in {"inherit", "left", "right", "center", "justify"}
                or any(type(choice[k]) is not bool for k in ("bold", "italic", "underline"))):
            _fail("invalid_paragraph_presentation")
        for key in ("space_before_pt", "space_after_pt"):
            if choice[key] is not None and not _number(choice[key], 0, 72):
                _fail("invalid_paragraph_spacing")
        if (type(choice["heading_level"]) is not int or choice["heading_level"] not in {0, 1, 2, 3}
                or ((choice["role"] == "heading") != (choice["heading_level"] > 0))
                or (choice["heading_size_pt"] is not None and (choice["role"] != "heading"
                    or not _number(choice["heading_size_pt"], 1, 24)))):
            _fail("invalid_heading_presentation")
        regions, reason = choice["regions"], choice["unmapped_reason"]
        if type(regions) is not list or len(regions) > 20 or not _text_field(reason):
            _fail("invalid_source_association")
        if regions and reason.strip():
            _fail("conflicting_source_association")
        for region in regions:
            _keys(region, {"page_number", "bbox_px"})
            number, box = region["page_number"], region["bbox_px"]
            if type(number) is not int or number not in frames or type(box) is not list or len(box) != 4:
                _fail("invalid_source_region")
            frame = frames[number]
            if (not all(_number(v, 0, frame["width_px"] if i % 2 == 0 else frame["height_px"]) for i, v in enumerate(box))
                    or not box[0] < box[2] or not box[1] < box[3]):
                _fail("invalid_source_region")
        _emphasis(row, choice["emphasis"])
    bands = decisions["bands"]
    if type(bands) is not list or not 0 < len(bands) <= MAX_PARAGRAPHS:
        _fail("invalid_layout_bands")
    seen, by_id = [], {row["id"]: row for row in rows}
    def groups(value, in_columns):
        if type(value) is not list or not 0 < len(value) <= MAX_PARAGRAPHS:
            _fail("invalid_layout_groups")
        for group in value:
            _keys(group, {"paragraph_ids", "panel"})
            ids = group["paragraph_ids"]
            if type(group["panel"]) is not bool or type(ids) is not list or not 0 < len(ids) <= MAX_PARAGRAPHS:
                _fail("invalid_layout_group")
            for identifier in ids:
                if type(identifier) is not str or identifier not in by_id:
                    _fail("invalid_paragraph_owner")
                if by_id[identifier]["has_page_break"] and (in_columns or group["panel"]):
                    _fail("page_break_requires_flow")
                seen.append(identifier)
    for band in bands:
        if type(band) is not dict:
            _fail("invalid_layout_band")
        if band.get("kind") == "flow":
            _keys(band, {"kind", "groups"})
            groups(band["groups"], False)
        elif band.get("kind") == "columns":
            _keys(band, {"kind", "widths_pct", "gutter_pt", "cells"})
            widths, cells = band["widths_pct"], band["cells"]
            if (type(widths) is not list or not 2 <= len(widths) <= 3
                    or any(not _number(v, 10, 90) for v in widths) or abs(sum(widths) - 100) > .001
                    or not _number(band["gutter_pt"], 0, 36) or type(cells) is not list or len(cells) != len(widths)):
                _fail("invalid_layout_columns")
            for cell in cells:
                _keys(cell, {"groups"})
                groups(cell["groups"], True)
        else:
            _fail("invalid_layout_band")
    if seen != [row["id"] for row in rows]:
        _fail("paragraph_coverage_or_order")
    review = decisions["review"]
    _keys(review, {"reviewer_kind", "reviewer", "note", "pages_reviewed", "document_reviewed"})
    if (review["reviewer_kind"] not in {"operator_review", "assistant_source_image_review"}
            or not _text_field(review["reviewer"], 200) or not _text_field(review["note"], 4000)
            or type(review["document_reviewed"]) is not bool or type(review["pages_reviewed"]) is not list
            or any(type(n) is not int or n not in frames for n in review["pages_reviewed"])
            or len(set(review["pages_reviewed"])) != len(review["pages_reviewed"])):
        _fail("invalid_review_attestation")
    if require_review or review["document_reviewed"]:
        if (not review["document_reviewed"] or not review["reviewer"].strip() or not review["note"].strip()
                or sorted(review["pages_reviewed"]) != list(frames)
                or any(not c["regions"] and not c["unmapped_reason"].strip() for c in choices)):
            _fail("incomplete_source_review")
    return json.loads(_canonical(decisions))
