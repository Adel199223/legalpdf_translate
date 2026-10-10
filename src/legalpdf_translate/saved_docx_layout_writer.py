"""Presentation-only saved-DOCX derivatives; no translation or file side effects."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import io
from zipfile import ZipFile

from lxml import etree

from . import saved_docx_layout as model

WRITER_VERSION = "saved_docx_layout_writer_v1"
HORIZONTAL_WRITER_VERSION = "saved_docx_layout_writer_ar_horizontal_v2"
PARTITION_WRITER_VERSION = "saved_docx_layout_writer_partitions_v3"
AUTOMATIC_MODERN_WRITER_VERSION = "saved_docx_layout_writer_automatic_modern_v4"
AUTOMATIC_SEPARATED_WRITER_VERSION = "saved_docx_layout_writer_automatic_separated_v5"
W = model.W
_P_ORDER = ("pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
    "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens", "kinsoku",
    "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN", "bidi",
    "adjustRightInd", "snapToGrid", "spacing", "ind", "contextualSpacing", "mirrorIndents",
    "suppressOverlap", "jc", "textDirection", "textAlignment", "textboxTightWrap", "outlineLvl",
    "divId", "cnfStyle", "rPr", "sectPr", "pPrChange")
_R_ORDER = ("rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike",
    "dstrike", "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish",
    "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight",
    "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
    "eastAsianLayout", "specVanish", "oMath", "rPrChange")


@dataclass(frozen=True, slots=True)
class SavedDocxLayoutArtifact:
    docx_bytes: bytes
    source_map: dict


def _node(name, **attributes):
    node = etree.Element(W + name)
    for key, value in attributes.items():
        node.set(W + key, str(value))
    return node


def _set(parent, name, *, order=(), **attributes):
    for old in list(parent.findall(W + name)):
        parent.remove(old)
    node = _node(name, **attributes)
    rank = order.index(name) if name in order else len(order)
    position = next((i for i, old in enumerate(parent)
                     if old.tag[len(W):] in order and order.index(old.tag[len(W):]) > rank), len(parent))
    parent.insert(position, node)
    return node


def _rpr(run):
    props = run.find(W + "rPr")
    if props is None:
        props = _node("rPr")
        run.insert(0, props)
    return props


def _added_presentation(props, choice, baseline, *, span=None):
    for key, tags in (("bold", ("b", "bCs")), ("italic", ("i", "iCs")), ("underline", ("u",))):
        if choice[key] or (span is not None and span[key]):
            for tag in tags:
                existing = props.find(W + tag)
                if tag == "u" and existing is not None and existing.get(W + "val", "single") not in {"none", "0", "false"}:
                    continue
                inherited = baseline.get("underline_attrs")
                if tag == "u" and existing is None and inherited is not None and inherited.get(W + "val", "single") not in {"none", "0", "false"}:
                    continue
                _set(props, tag, order=_R_ORDER, val="single" if tag == "u" else "1")
    if choice["heading_size_pt"] is not None:
        for tag, key in (("sz", "size_pt"), ("szCs", "cs_size_pt")):
            size = max(baseline[key], choice["heading_size_pt"])
            _set(props, tag, order=_R_ORDER, val=round(size * 2))


def _paragraph_presentation(paragraph, choice, *, bidi):
    props = paragraph.find(W + "pPr")
    if props is None:
        props = _node("pPr")
        paragraph.insert(0, props)
    if choice["alignment"] != "inherit":
        alignment = choice["alignment"]
        if bidi:
            alignment = {"left": "end", "right": "start", "center": "center", "justify": "both"}[alignment]
        elif alignment == "justify":
            alignment = "both"
        _set(props, "jc", order=_P_ORDER, val=alignment)
    if choice["space_before_pt"] is not None or choice["space_after_pt"] is not None:
        old = props.find(W + "spacing")
        attrs = dict(old.attrib) if old is not None else {}
        for key, tag in (("space_before_pt", "before"), ("space_after_pt", "after")):
            if choice[key] is not None:
                attrs[W + tag] = str(round(choice[key] * 20))
                attrs.pop(W + tag + "Lines", None)
                attrs.pop(W + tag + "Autospacing", None)
        new = _set(props, "spacing", order=_P_ORDER)
        new.attrib.update(attrs)
    if choice["heading_level"]:
        _set(props, "outlineLvl", order=_P_ORDER, val=choice["heading_level"] - 1)
        _set(props, "keepNext", order=_P_ORDER, val=1)


def _styled_paragraph(original, baseline, choice, target_lang):
    paragraph = deepcopy(original)
    _paragraph_presentation(paragraph, choice, bidi=baseline["bidi"])
    offset = 0
    run_index = 0
    for run in list(paragraph):
        if run.tag != W + "r":
            continue
        run_baseline = baseline["runs"][run_index]
        run_index += 1
        properties = run.find(W + "rPr")
        has_span = any(span["start"] < run_baseline["end"] and span["end"] > run_baseline["start"]
                       for span in choice["emphasis"])
        if not has_span:
            if any(choice[k] for k in ("bold", "italic", "underline")) or choice["heading_size_pt"] is not None:
                _added_presentation(_rpr(run), choice, run_baseline)
            offset = run_baseline["end"]
            continue
        replacements = []
        for child in run:
            if child is properties:
                continue
            text = child.text or "" if child.tag == W + "t" else "\0"
            end = offset + len(text)
            boundaries = sorted({offset, end, *(cut for span in choice["emphasis"]
                for cut in (span["start"], span["end"]) if offset < cut < end)})
            if not text:
                boundaries = [offset, offset]
            for start, stop in zip(boundaries, boundaries[1:]):
                new = etree.Element(W + "r", attrib=dict(run.attrib), nsmap=run.nsmap)
                if properties is not None:
                    new.append(deepcopy(properties))
                span = next((span for span in choice["emphasis"] if span["start"] <= start < span["end"]), None)
                if span is not None or any(choice[k] for k in ("bold", "italic", "underline")) or choice["heading_size_pt"] is not None:
                    _added_presentation(_rpr(new), choice, run_baseline, span=span)
                node = deepcopy(child)
                if child.tag == W + "t":
                    node.text = text[start - offset:stop - offset]
                    if node.text and (node.text[0].isspace() or node.text[-1].isspace()):
                        node.set(model.XML_SPACE, "preserve")
                new.append(node)
                replacements.append(new)
            offset = end
        index = paragraph.index(run)
        paragraph.remove(run)
        for new in replacements:
            paragraph.insert(index, new)
            index += 1
    return paragraph


def _table(widths, *, panel=False, gutter_pt=0, spacer_indices=()):
    table = _node("tbl")
    props = _node("tblPr")
    table.append(props)
    props.append(_node("bidiVisual", val=0))
    props.append(_node("tblW", w=sum(widths), type="dxa"))
    props.append(_node("jc", val="left"))
    borders = _node("tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        borders.append(_node(side, val="nil"))
    props.append(borders)
    props.append(_node("tblLayout", type="fixed"))
    margin = _node("tblCellMar")
    for side in ("top", "left", "bottom", "right"):
        margin.append(_node(side, w=0, type="dxa"))
    props.append(margin)
    grid = _node("tblGrid")
    for width in widths:
        grid.append(_node("gridCol", w=width))
    table.append(grid)
    row = _node("tr")
    table.append(row)
    cells = []
    for index, width in enumerate(widths):
        cell, cp = _node("tc"), _node("tcPr")
        cell.append(cp)
        cp.append(_node("tcW", w=width, type="dxa"))
        if panel:
            cp.append(_node("shd", val="clear", color="auto", fill="E7E7E7"))
        margins = _node("tcMar")
        left = 100 if panel else round(gutter_pt * 10) if index else 0
        right = 100 if panel else round(gutter_pt * 10) if index < len(widths) - 1 else 0
        if width <= 0 or (index not in spacer_indices and width - left - right < 360):
            model._fail("layout_column_too_narrow")
        for side, amount in (("top", 100 if panel else 0), ("left", left), ("bottom", 100 if panel else 0), ("right", right)):
            margins.append(_node(side, w=amount, type="dxa"))
        cp.append(margins)
        cp.append(_node("vAlign", val="top"))
        row.append(cell)
        cells.append((cell, width - left - right))
    return table, cells


def _partition_children(paragraph, offsets):
    """Slice existing text nodes/runs verbatim; never trim boundary whitespace."""
    total = sum(len(node.text or "") for node in paragraph.iter(W + "t"))
    boundaries = [0, *offsets, total]
    children = []
    for start, end in zip(boundaries, boundaries[1:]):
        child = deepcopy(paragraph)
        for node in list(child):
            if node.tag != W + "pPr":
                child.remove(node)
        cursor = 0
        for run in paragraph:
            if run.tag != W + "r":
                continue
            result = deepcopy(run)
            for node in list(result):
                if node.tag != W + "rPr":
                    result.remove(node)
            for node in run:
                if node.tag == W + "rPr":
                    continue
                if node.tag != W + "t":
                    model._fail("unsupported_partition_parent")
                text = node.text or ""
                stop = cursor + len(text)
                lo, hi = max(start, cursor), min(end, stop)
                if lo < hi:
                    sliced = deepcopy(node)
                    sliced.text = text[lo - cursor:hi - cursor]
                    if sliced.text[0].isspace() or sliced.text[-1].isspace():
                        sliced.set(model.XML_SPACE, "preserve")
                    result.append(sliced)
                cursor = stop
            if any(n.tag == W + "t" for n in result):
                child.append(result)
        children.append(child)
    return children


def _joined_children(children):
    joined = deepcopy(children[0])
    for child in children[1:]:
        for run in child:
            if run.tag != W + "pPr":
                joined.append(deepcopy(run))
    return joined


def _empty():
    paragraph, props = _node("p"), _node("pPr")
    props.append(_node("spacing", before=0, after=0, line=20, lineRule="exact"))
    paragraph.append(props)
    return paragraph


def _usable_width(section):
    size, margins = section.find(W + "pgSz"), section.find(W + "pgMar")
    try:
        width = int(size.get(W + "w", "11906")) if size is not None else 11906
        left = int(margins.get(W + "left", "1440")) if margins is not None else 1440
        right = int(margins.get(W + "right", "1440")) if margins is not None else 1440
    except (TypeError, ValueError):
        model._fail("invalid_section_width")
    if not 2880 <= width - left - right <= 31680:
        model._fail("unsupported_section_width")
    return width - left - right


def _horizontal_plan(original_root, snapshot, pages, decisions):
    """Derived horizontal presentation only; source regions remain untouched."""
    section = original_root[0][-1]
    usable = _usable_width(section)
    size, margins = section.find(W + "pgSz"), section.find(W + "pgMar")
    page_width = int(size.get(W + "w", "11906")) if size is not None else 11906
    left_margin = int(margins.get(W + "left", "1440")) if margins is not None else 1440
    frames = {p["page_number"]: p for p in pages}
    choices = {p["paragraph_id"]: p for p in decisions["paragraphs"]}
    rows = {p["id"]: p for p in snapshot["paragraphs"]}
    plan = []
    for bi, band in enumerate(decisions["bands"]):
        if band["kind"] != "flow":
            continue
        for gi, group in enumerate(band["groups"]):
            if group["panel"]:
                continue
            metadata_roles = {"institution", "reference", "recipient"}
            metadata_group = all(choices[pid]["role"] in metadata_roles | {"heading"}
                                 or not rows[pid]["text"].strip() for pid in group["paragraph_ids"])
            current = None
            for identifier in group["paragraph_ids"]:
                regions = choices[identifier]["regions"]
                role = choices[identifier]["role"]
                eligible = (role in metadata_roles or role == "heading" and metadata_group)
                eligible = (eligible and not rows[identifier]["has_page_break"] and len(regions) == 1
                            and all(t["kind"] == "t" for t in rows[identifier]["tokens"]))
                if eligible:
                    region = regions[0]
                    frame = frames[region["page_number"]]
                    x0, _, x1, _ = region["bbox_px"]
                    x0, x1 = x0 / frame["width_px"], x1 / frame["width_px"]
                    eligible = x1 - x0 <= .65
                if not eligible:
                    current = None
                    continue
                overlap = 0 if current is None else min(current["x1"], x1) - max(current["x0"], x0)
                merge = (current is not None and current["page_number"] == region["page_number"]
                         and overlap >= .5 * min(current["x1"] - current["x0"], x1 - x0)
                         and max(current["x1"], x1) - min(current["x0"], x0) <= .65)
                if merge:
                    current["paragraph_ids"].append(identifier)
                    current["x0"], current["x1"] = min(current["x0"], x0), max(current["x1"], x1)
                else:
                    current = {"band_index": bi, "group_index": gi, "paragraph_ids": [identifier],
                               "page_number": region["page_number"], "x0": x0, "x1": x1}
                    plan.append(current)
    for item in plan:
        start = max(0, min(usable, round(item["x0"] * page_width - left_margin)))
        end = max(0, min(usable, round(item["x1"] * page_width - left_margin)))
        if end - start < 360:
            start = max(0, min(usable - 360, start))
            end = start + 360
        item["cell_widths_twips"] = [start, end - start, usable - end]
    return plan


def _assemble(original_root, snapshot, decisions, *, horizontal_plan=None, separate_body_tables=False):
    root = deepcopy(original_root)
    body = root[0]
    section = deepcopy(body[-1])
    originals = {row["id"]: p for row, p in zip(snapshot["paragraphs"], list(body)[:-1])}
    baselines = {row["id"]: row for row in snapshot["paragraphs"]}
    choices = {row["paragraph_id"]: row for row in decisions["paragraphs"]}
    for child in list(body):
        body.remove(child)
    width = _usable_width(section)
    owned, structural = {}, []
    partitions = {p["paragraph_id"]: p["offsets"] for p in decisions.get("paragraph_partitions", [])}
    starts = {item["paragraph_ids"][0]: item for item in horizontal_plan or []}
    framed = {identifier for item in horizontal_plan or [] for identifier in item["paragraph_ids"]}
    def add_groups(container, groups, available):
        for group in groups:
            parent = container
            if group["panel"]:
                table, cells = _table([available], panel=True)
                container.append(table)
                parent = cells[0][0]
            for identifier in group["paragraph_ids"]:
                if parent is body and identifier in framed:
                    if identifier not in starts:
                        continue
                    item = starts[identifier]
                    widths = [w for w in item["cell_widths_twips"] if w]
                    content_index = 1 if item["cell_widths_twips"][0] else 0
                    table, cells = _table(widths, spacer_indices=[i for i in range(len(widths)) if i != content_index])
                    body.append(table)
                    for ci, (cell, _) in enumerate(cells):
                        if ci != content_index:
                            empty = _empty()
                            cell.append(empty)
                            structural.append(empty)
                        else:
                            for pid in item["paragraph_ids"]:
                                paragraph = _styled_paragraph(originals[pid], baselines[pid], choices[pid], snapshot["target_lang"])
                                cell.append(paragraph)
                                owned[pid] = paragraph
                    # A one-point anchor prevents adjacent tables merging in Word.
                    anchor = _empty()
                    body.append(anchor)
                    structural.append(anchor)
                    continue
                paragraph = _styled_paragraph(originals[identifier], baselines[identifier], choices[identifier], snapshot["target_lang"])
                if identifier in partitions:
                    children = _partition_children(paragraph, partitions[identifier])
                    parent.extend(children)
                    owned[identifier] = children
                else:
                    parent.append(paragraph)
                    owned[identifier] = paragraph
            if group["panel"] and container.tag == W + "tc":
                anchor = _empty()
                container.append(anchor)
                structural.append(anchor)
    for band in decisions["bands"]:
        if band["kind"] == "flow":
            add_groups(body, band["groups"], width)
        else:
            widths = [round(width * percent / 100) for percent in band["widths_pct"][:-1]]
            widths.append(width - sum(widths))
            table, cells = _table(widths, gutter_pt=band["gutter_pt"])
            body.append(table)
            for (cell, available), spec in zip(cells, band["cells"]):
                add_groups(cell, spec["groups"], available)
    if body[-1].tag == W + "tbl":
        anchor = _empty()
        body.append(anchor)
        structural.append(anchor)
    if separate_body_tables:
        # Word merges adjacent body tables on save. Only new v5 candidates
        # receive a visible-layout-neutral, owned one-point separator.
        for previous, following in zip(list(body), list(body)[1:]):
            if previous.tag == W + "tbl" and following.tag == W + "tbl":
                separator = _empty()
                body.insert(body.index(following), separator)
                structural.append(separator)
    body.append(section)
    tree = root.getroottree()
    locations = {identifier: ([tree.getpath(p) for p in paragraph] if isinstance(paragraph, list)
                             else tree.getpath(paragraph)) for identifier, paragraph in owned.items()}
    return root, locations, [tree.getpath(p) for p in structural]


def _write(members, infos, document_xml):
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        for info in infos:
            archive.writestr(info, document_xml if info.filename == "word/document.xml" else members[info.filename])
    return output.getvalue()


def _ar_compatibility_settings(raw):
    """Exactly one modern Word mode; preserve all other settings and prefixes."""
    root = model._xml(raw)
    compat = root.find(W + "compat")
    if compat is None:
        compat = _node("compat")
        root.append(compat)
    for child in list(compat):
        if child.tag == W + "compatSetting" and child.get(W + "name") == "compatibilityMode":
            compat.remove(child)
    mode = _node("compatSetting", uri="http://schemas.microsoft.com/office/word", val="15")
    mode.set(W + "name", "compatibilityMode")
    compat.append(mode)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _modern_compatibility_settings(raw):
    """New automatic derivatives use one mode15 across all existing settings."""
    root = model._xml(raw)
    for node in list(root.iter(W + "compatSetting")):
        if node.get(W + "name") == "compatibilityMode":
            node.getparent().remove(node)
    compat = root.find(W + "compat")
    if compat is None:
        compat = _node("compat")
        root.append(compat)
    mode = _node("compatSetting", uri="http://schemas.microsoft.com/office/word", val="15")
    mode.set(W + "name", "compatibilityMode")
    compat.append(mode)
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _expected_modern_settings(raw):
    """Derive the allowed package delta independently of the builder helper."""
    root = model._xml(raw)
    for node in root.xpath(".//w:compatSetting[@w:name='compatibilityMode']", namespaces={"w": W[1:-1]}):
        node.getparent().remove(node)
    compat = root.find(W + "compat")
    if compat is None:
        compat = etree.SubElement(root, W + "compat")
    etree.SubElement(compat, W + "compatSetting", {
        W + "uri": "http://schemas.microsoft.com/office/word",
        W + "val": "15", W + "name": "compatibilityMode"})
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _semantic_segments(paragraph, context):
    row = model._paragraph_inventory(paragraph, context)
    runs = [child for child in paragraph if child.tag == W + "r"]
    result = []
    for token in row["tokens"]:
        props = runs[token["run"]].find(W + "rPr")
        signature = model._c14n(props)
        item = [token["kind"], token["text"], signature]
        if result and item[0] == "t" and result[-1][0] == "t" and result[-1][2] == signature:
            result[-1][1] += item[1]
        elif item[0] != "t" or item[1]:
            result.append(item)
    return row, result


def _independent_paragraph_check(original, actual, original_row, choice, context):
    """Compare baseline properties directly, independently of the assembler.

    The expected scaffold below protects structure. This separate check prevents
    an assembler defect shared with that scaffold from approving changed font,
    direction, language, text or unrequested presentation changes.
    """
    output_row = model._paragraph_inventory(actual, context)
    if model._content_tokens(original_row["tokens"]) != model._content_tokens(output_row["tokens"]):
        model._fail("output_content_changed")
    original_text = [t for t in original_row["tokens"] if t["kind"] == "t" and t["text"]]
    text_index = 0
    for token in output_row["tokens"]:
        if token["kind"] != "t" or not token["text"]:
            continue
        while text_index < len(original_text) and original_text[text_index]["end"] <= token["start"]:
            text_index += 1
        cursor = text_index
        while cursor < len(original_text) and original_text[cursor]["start"] < token["end"]:
            before = original_text[cursor]
            if token.get("xml_space") != before.get("xml_space"):
                split = token["start"] > before["start"] or token["end"] < before["end"]
                permitted = (token.get("xml_space") == "preserve" and split
                             and (token["text"][0].isspace() or token["text"][-1].isspace()))
                if not permitted:
                    model._fail("output_text_space_semantics_changed")
            cursor += 1
    original_runs = [n for n in original if n.tag == W + "r"]
    output_runs = [n for n in actual if n.tag == W + "r"]
    changes = {"b", "bCs", "i", "iCs", "u", "sz", "szCs"}
    def signature(props, removed):
        if props is None:
            return []
        return [model._c14n(n) for n in props if n.tag not in {W + tag for tag in removed}]
    def attrs(props, tag):
        node = props.find(W + tag) if props is not None else None
        return None if node is None else dict(node.attrib)
    oi = ai = 0
    source_nonempty = [(b, n) for b, n in zip(original_row["runs"], original_runs) if b["end"] > b["start"]]
    target_nonempty = [(b, n) for b, n in zip(output_row["runs"], output_runs) if b["end"] > b["start"]]
    while oi < len(source_nonempty) and ai < len(target_nonempty):
        baseline, before = source_nonempty[oi]
        rendered, after = target_nonempty[ai]
        start, end = max(baseline["start"], rendered["start"]), min(baseline["end"], rendered["end"])
        bprops, aprops = before.find(W + "rPr"), after.find(W + "rPr")
        if signature(bprops, changes) != signature(aprops, changes):
            model._fail("output_baseline_run_semantics_changed")
        cuts = sorted({start, end, *(cut for span in choice["emphasis"] for cut in (span["start"], span["end"]) if start < cut < end)})
        for offset in cuts[:-1]:
            span = next((s for s in choice["emphasis"] if s["start"] <= offset < s["end"]), None)
            for key, tags in (("bold", ("b", "bCs")), ("italic", ("i", "iCs")), ("underline", ("u",))):
                for tag in tags:
                    expected = attrs(bprops, tag)
                    if choice[key] or (span is not None and span[key]):
                        inherited = baseline.get("underline_attrs")
                        preserved_underline = tag == "u" and (
                            (expected is not None and expected.get(W + "val", "single") not in {"none", "0", "false"})
                            or (expected is None and inherited is not None and inherited.get(W + "val", "single") not in {"none", "0", "false"}))
                        if not preserved_underline:
                            expected = {W + "val": "single" if tag == "u" else "1"}
                    if attrs(aprops, tag) != expected:
                        model._fail("output_unauthorized_emphasis")
            for tag, key in (("sz", "size_pt"), ("szCs", "cs_size_pt")):
                expected = attrs(bprops, tag)
                if choice["heading_size_pt"] is not None:
                    expected = {W + "val": str(round(max(baseline[key], choice["heading_size_pt"]) * 2))}
                if attrs(aprops, tag) != expected:
                    model._fail("output_unauthorized_heading_size")
        if baseline["end"] <= rendered["end"]:
            oi += 1
        if rendered["end"] <= baseline["end"]:
            ai += 1
    if oi != len(source_nonempty) or ai != len(target_nonempty):
        model._fail("output_run_coverage_changed")
    before, after = original.find(W + "pPr"), actual.find(W + "pPr")
    permitted = {"jc"} if choice["alignment"] != "inherit" else set()
    if choice["space_before_pt"] is not None or choice["space_after_pt"] is not None:
        permitted.add("spacing")
    if choice["heading_level"]:
        permitted.update(("outlineLvl", "keepNext"))
    if signature(before, permitted) != signature(after, permitted):
        model._fail("output_baseline_paragraph_semantics_changed")
    if "jc" in permitted:
        value = choice["alignment"]
        if original_row["bidi"]:
            value = {"left": "end", "right": "start", "center": "center", "justify": "both"}[value]
        elif value == "justify":
            value = "both"
        if attrs(after, "jc") != {W + "val": value}:
            model._fail("output_unauthorized_alignment")
    if "spacing" in permitted:
        expected = attrs(before, "spacing") or {}
        for key, tag in (("space_before_pt", "before"), ("space_after_pt", "after")):
            if choice[key] is not None:
                expected[W + tag] = str(round(choice[key] * 20))
                expected.pop(W + tag + "Lines", None)
                expected.pop(W + tag + "Autospacing", None)
        if attrs(after, "spacing") != expected:
            model._fail("output_unauthorized_spacing")
    if choice["heading_level"] and (attrs(after, "outlineLvl") != {W + "val": str(choice["heading_level"] - 1)}
                                   or attrs(after, "keepNext") != {W + "val": "1"}):
        model._fail("output_unauthorized_heading_properties")


def validate_built_docx(docx_bytes: bytes, source_map: dict, *, original_docx: bytes,
                        snapshot: dict, pages: list, decisions: dict,
                        require_review: bool = True) -> None:
    """Reparse independently, check ownership/content, then exact approved scaffold."""
    actual_snapshot = model.inspect_docx(original_docx, snapshot["target_lang"])
    if actual_snapshot != snapshot:
        model._fail("snapshot_identity_mismatch")
    decisions = model.validate_decisions(snapshot, pages, decisions, require_review=require_review)
    if not require_review and (decisions["review"]["document_reviewed"]
                               or decisions["review"]["pages_reviewed"]):
        model._fail("automatic_review_claim")
    original, _, original_root, _, context = model._load_docx(original_docx)
    output, _ = model._package(docx_bytes)
    version = source_map.get("writer_version")
    partitioned = decisions["version"] == model.PARTITION_DECISIONS_VERSION
    separated = version == AUTOMATIC_SEPARATED_WRITER_VERSION
    modern = version in {AUTOMATIC_MODERN_WRITER_VERSION, AUTOMATIC_SEPARATED_WRITER_VERSION}
    if (version not in {WRITER_VERSION, HORIZONTAL_WRITER_VERSION, PARTITION_WRITER_VERSION,
                       AUTOMATIC_MODERN_WRITER_VERSION, AUTOMATIC_SEPARATED_WRITER_VERSION}
            or (modern and require_review)
            or (version == PARTITION_WRITER_VERSION and not partitioned)
            or (partitioned and version not in {PARTITION_WRITER_VERSION, AUTOMATIC_MODERN_WRITER_VERSION, AUTOMATIC_SEPARATED_WRITER_VERSION})):
        model._fail("unsupported_writer_version")
    horizontal = (snapshot["target_lang"] == "AR" and
        (version == HORIZONTAL_WRITER_VERSION and not require_review
         or version in {PARTITION_WRITER_VERSION, AUTOMATIC_MODERN_WRITER_VERSION, AUTOMATIC_SEPARATED_WRITER_VERSION}))
    expected_parts = dict(original)
    if modern:
        expected_parts["word/settings.xml"] = _expected_modern_settings(original["word/settings.xml"])
    elif horizontal:
        expected_parts["word/settings.xml"] = _ar_compatibility_settings(original["word/settings.xml"])
    if set(output) != set(original) or any(output[n] != expected_parts[n] for n in original if n != "word/document.xml"):
        model._fail("unaffected_package_changed")
    actual_root = model._xml(output["word/document.xml"])
    if horizontal:
        plan = _horizontal_plan(original_root, snapshot, pages, decisions)
    elif version in {WRITER_VERSION, PARTITION_WRITER_VERSION, AUTOMATIC_MODERN_WRITER_VERSION, AUTOMATIC_SEPARATED_WRITER_VERSION}:
        plan = None
    else:
        model._fail("unsupported_writer_version")
    expected_root, locations, structural = _assemble(original_root, snapshot, decisions,
        horizontal_plan=plan, separate_body_tables=separated)
    expected_map = _source_map(snapshot, pages, decisions, locations, structural, docx_bytes,
                               require_review=require_review, horizontal_plan=plan, writer_version=version)
    if source_map != expected_map:
        model._fail("source_map_mismatch")
    if actual_root.tag != W + "document" or len(actual_root) != 1 or actual_root[0].tag != W + "body":
        model._fail("invalid_output_structure")
    if separated and any(a.tag == b.tag == W + "tbl"
                         for a, b in zip(actual_root[0], list(actual_root[0])[1:])):
        model._fail("output_adjacent_body_tables")
    actual_paragraphs = list(actual_root[0].iter(W + "p"))
    located, owned = [], set()
    originals = {row["id"]: p for row, p in zip(snapshot["paragraphs"], list(original_root[0])[:-1])}
    choices = {row["paragraph_id"]: row for row in decisions["paragraphs"]}
    for row in snapshot["paragraphs"]:
        paths = locations[row["id"]]
        paths = paths if isinstance(paths, list) else [paths]
        nodes = [actual_root.getroottree().xpath(path, namespaces=actual_root.nsmap) for path in paths]
        if any(len(found) != 1 or found[0] in owned for found in nodes):
            model._fail("output_paragraph_ownership")
        children = [found[0] for found in nodes]
        owned.update(children)
        paragraph = _joined_children(children)
        _independent_paragraph_check(originals[row["id"]], paragraph, row, choices[row["id"]], context)
        cuts = next((p["offsets"] for p in decisions.get("paragraph_partitions", [])
                     if p["paragraph_id"] == row["id"]), [])
        boundaries = [0, *cuts, len(row["text"])]
        if len(children) != len(boundaries) - 1:
            model._fail("output_partition_child_count_changed")
        # The first child's pPr has just passed the baseline/choice check.
        # Compare each later child directly to that independently qualified
        # presentation; never trust a second invocation of the splitter.
        qualified_ppr = model._c14n(children[0].find(W + "pPr"))
        for child, start, end in zip(children, boundaries, boundaries[1:]):
            text = "".join(node.text or "" for node in child.iter(W + "t"))
            if cuts and text != row["text"][start:end]:
                model._fail("output_partition_text_range_changed")
            if model._c14n(child.find(W + "pPr")) != qualified_ppr:
                model._fail("output_partition_paragraph_properties_changed")
        actual, semantics = _semantic_segments(paragraph, context)
        if model._content_tokens(actual["tokens"]) != model._content_tokens(row["tokens"]):
            model._fail("output_content_changed")
        expected = _joined_children([expected_root.getroottree().xpath(path, namespaces=expected_root.nsmap)[0] for path in paths])
        _, expected_semantics = _semantic_segments(expected, context)
        if semantics != expected_semantics:
            model._fail("output_run_semantics_changed")
        located.extend(children)
    if [p for p in actual_paragraphs if p in owned] != located:
        model._fail("output_paragraph_order_changed")
    for path in structural:
        found = actual_root.getroottree().xpath(path, namespaces=actual_root.nsmap)
        if len(found) != 1 or found[0] in owned or list(found[0].iter(W + "t")) or list(found[0].iter(W + "r")):
            model._fail("output_structural_paragraph_changed")
        owned.add(found[0])
    if owned != set(actual_paragraphs):
        model._fail("unowned_output_paragraph")
    if model._c14n(actual_root) != model._c14n(expected_root):
        model._fail("output_layout_changed")


def _source_map(snapshot, pages, decisions, locations, structural, raw, *, writer_version,
                require_review=True, horizontal_plan=None):
    mapping = {"version": model.VERSION, "writer_version": writer_version,
        "docx_sha256": model._sha(raw), "input_docx_sha256": snapshot["docx_sha256"],
        "decisions_sha256": model._sha(model._canonical(decisions)), "target_lang": snapshot["target_lang"],
        "geometry_basis": "reviewed_image_regions_not_ocr" if require_review else "model_proposal_unreviewed",
        "rendered_layout_acceptance": "not_evaluated",
        "rendered_page_count": None, "exact_text_preserved": True, "logical_order_preserved": True,
        "source_character_coverage": "not_proven", "source_pages": deepcopy(pages),
        "review": deepcopy(decisions["review"]), "structural_paragraphs": structural,
        "paragraphs": [{"paragraph_id": c["paragraph_id"], "location": (locations[c["paragraph_id"]][0]
            if isinstance(locations[c["paragraph_id"]], list) else locations[c["paragraph_id"]]),
            "regions": deepcopy(c["regions"]), "unmapped_reason": c["unmapped_reason"]}
            for c in decisions["paragraphs"]],
        "qualifications": [{"paragraph_id": c["paragraph_id"], "reason": c["unmapped_reason"]}
                           for c in decisions["paragraphs"] if not c["regions"]]}
    if not require_review:
        mapping["document_reviewed"] = False
    if horizontal_plan is not None:
        mapping["derived_horizontal_plan"] = deepcopy(horizontal_plan)
        mapping["derived_horizontal_plan_sha256"] = model._sha(model._canonical(horizontal_plan))
        mapping["structural_paragraph_qualification"] = "empty_spacer_cells_and_table_separation_anchors"
    if writer_version == AUTOMATIC_SEPARATED_WRITER_VERSION:
        mapping["structural_paragraph_qualification"] = "empty_spacer_cells_and_explicit_adjacent_body_table_separators_v5"
    if decisions["version"] == model.PARTITION_DECISIONS_VERSION:
        mapping["paragraph_partitions_sha256"] = model._sha(model._canonical(decisions["paragraph_partitions"]))
        mapping["partition_geometry_basis"] = "inherited_parent_source_association_not_precise_child_geometry"
        rows = {row["id"]: row for row in snapshot["paragraphs"]}
        parts = {p["paragraph_id"]: p["offsets"] for p in decisions["paragraph_partitions"]}
        for row in mapping["paragraphs"]:
            identifier = row["paragraph_id"]
            if identifier in parts:
                boundaries = [0, *parts[identifier], len(rows[identifier]["text"])]
                row["parts"] = [{"part_id": f"{identifier}.part{index:03d}", "parent_id": identifier,
                    "start": start, "end": end, "location": path}
                    for index, (start, end, path) in enumerate(zip(boundaries, boundaries[1:], locations[identifier]), 1)]
    return mapping


def build_docx(docx_bytes: bytes, snapshot: dict, pages: list, decisions: dict) -> SavedDocxLayoutArtifact:
    """Build and verify a detached in-memory copy; never overwrite an input."""
    try:
        if model.inspect_docx(docx_bytes, snapshot["target_lang"]) != snapshot:
            model._fail("snapshot_identity_mismatch")
        checked = model.validate_decisions(snapshot, pages, decisions, require_review=True)
        members, infos, original_root, _, _ = model._load_docx(docx_bytes)
        plan = (_horizontal_plan(original_root, snapshot, pages, checked)
                if checked["version"] == model.PARTITION_DECISIONS_VERSION and snapshot["target_lang"] == "AR" else None)
        if plan is not None:
            members = dict(members)
            members["word/settings.xml"] = _ar_compatibility_settings(members["word/settings.xml"])
        root, locations, structural = _assemble(original_root, snapshot, checked, horizontal_plan=plan)
        xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        raw = _write(members, infos, xml)
        mapping = _source_map(snapshot, pages, checked, locations, structural, raw, horizontal_plan=plan,
                              writer_version=(PARTITION_WRITER_VERSION
                                  if checked["version"] == model.PARTITION_DECISIONS_VERSION else WRITER_VERSION))
        validate_built_docx(raw, mapping, original_docx=docx_bytes, snapshot=snapshot, pages=pages, decisions=checked)
        return SavedDocxLayoutArtifact(raw, mapping)
    except model.SavedDocxLayoutError:
        raise
    except (TypeError, ValueError, KeyError, IndexError, OverflowError, AttributeError, etree.XPathError):
        model._fail("invalid_saved_docx_writer_input")


def build_unreviewed_docx(docx_bytes: bytes, snapshot: dict, pages: list,
                          decisions: dict) -> SavedDocxLayoutArtifact:
    """Build the same editable layout with explicit unreviewed provenance."""
    try:
        if model.inspect_docx(docx_bytes, snapshot["target_lang"]) != snapshot:
            model._fail("snapshot_identity_mismatch")
        checked = model.validate_decisions(snapshot, pages, decisions, require_review=False)
        if checked["review"]["document_reviewed"] or checked["review"]["pages_reviewed"]:
            model._fail("automatic_review_claim")
        members, infos, original_root, _, _ = model._load_docx(docx_bytes)
        plan = _horizontal_plan(original_root, snapshot, pages, checked) if snapshot["target_lang"] == "AR" else None
        members = dict(members)
        members["word/settings.xml"] = _modern_compatibility_settings(members["word/settings.xml"])
        root, locations, structural = _assemble(original_root, snapshot, checked, horizontal_plan=plan,
                                                separate_body_tables=True)
        xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        raw = _write(members, infos, xml)
        mapping = _source_map(snapshot, pages, checked, locations, structural, raw,
                              require_review=False, horizontal_plan=plan,
                              writer_version=AUTOMATIC_SEPARATED_WRITER_VERSION)
        validate_built_docx(raw, mapping, original_docx=docx_bytes, snapshot=snapshot,
                            pages=pages, decisions=checked, require_review=False)
        return SavedDocxLayoutArtifact(raw, mapping)
    except model.SavedDocxLayoutError:
        raise
    except (TypeError, ValueError, KeyError, IndexError, OverflowError, AttributeError, etree.XPathError):
        model._fail("invalid_saved_docx_writer_input")
