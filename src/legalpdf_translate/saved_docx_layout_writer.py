"""Presentation-only saved-DOCX derivatives; no translation or file side effects."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import io
from zipfile import ZipFile

from lxml import etree

from . import saved_docx_layout as model

WRITER_VERSION = "saved_docx_layout_writer_v1"
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


def _table(widths, *, panel=False, gutter_pt=0):
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
        if width - left - right < 360:
            model._fail("layout_column_too_narrow")
        for side, amount in (("top", 100 if panel else 0), ("left", left), ("bottom", 100 if panel else 0), ("right", right)):
            margins.append(_node(side, w=amount, type="dxa"))
        cp.append(margins)
        cp.append(_node("vAlign", val="top"))
        row.append(cell)
        cells.append((cell, width - left - right))
    return table, cells


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


def _assemble(original_root, snapshot, decisions):
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
    def add_groups(container, groups, available):
        for group in groups:
            parent = container
            if group["panel"]:
                table, cells = _table([available], panel=True)
                container.append(table)
                parent = cells[0][0]
            for identifier in group["paragraph_ids"]:
                paragraph = _styled_paragraph(originals[identifier], baselines[identifier], choices[identifier], snapshot["target_lang"])
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
    body.append(section)
    tree = root.getroottree()
    locations = {identifier: tree.getpath(paragraph) for identifier, paragraph in owned.items()}
    return root, locations, [tree.getpath(p) for p in structural]


def _write(members, infos, document_xml):
    output = io.BytesIO()
    with ZipFile(output, "w") as archive:
        for info in infos:
            archive.writestr(info, document_xml if info.filename == "word/document.xml" else members[info.filename])
    return output.getvalue()


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
    if set(output) != set(original) or any(output[n] != original[n] for n in original if n != "word/document.xml"):
        model._fail("unaffected_package_changed")
    actual_root = model._xml(output["word/document.xml"])
    expected_root, locations, structural = _assemble(original_root, snapshot, decisions)
    expected_map = _source_map(snapshot, pages, decisions, locations, structural, docx_bytes,
                               require_review=require_review)
    if source_map != expected_map:
        model._fail("source_map_mismatch")
    if actual_root.tag != W + "document" or len(actual_root) != 1 or actual_root[0].tag != W + "body":
        model._fail("invalid_output_structure")
    actual_paragraphs = list(actual_root[0].iter(W + "p"))
    located, owned = [], set()
    originals = {row["id"]: p for row, p in zip(snapshot["paragraphs"], list(original_root[0])[:-1])}
    choices = {row["paragraph_id"]: row for row in decisions["paragraphs"]}
    for row in snapshot["paragraphs"]:
        nodes = actual_root.getroottree().xpath(locations[row["id"]], namespaces=actual_root.nsmap)
        if len(nodes) != 1 or nodes[0] in owned:
            model._fail("output_paragraph_ownership")
        paragraph = nodes[0]
        owned.add(paragraph)
        _independent_paragraph_check(originals[row["id"]], paragraph, row, choices[row["id"]], context)
        actual, semantics = _semantic_segments(paragraph, context)
        if model._content_tokens(actual["tokens"]) != model._content_tokens(row["tokens"]):
            model._fail("output_content_changed")
        expected = expected_root.getroottree().xpath(locations[row["id"]], namespaces=expected_root.nsmap)[0]
        _, expected_semantics = _semantic_segments(expected, context)
        if semantics != expected_semantics:
            model._fail("output_run_semantics_changed")
        located.append(paragraph)
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


def _source_map(snapshot, pages, decisions, locations, structural, raw, *, require_review=True):
    mapping = {"version": model.VERSION, "writer_version": WRITER_VERSION,
        "docx_sha256": model._sha(raw), "input_docx_sha256": snapshot["docx_sha256"],
        "decisions_sha256": model._sha(model._canonical(decisions)), "target_lang": snapshot["target_lang"],
        "geometry_basis": "reviewed_image_regions_not_ocr" if require_review else "model_proposal_unreviewed",
        "rendered_layout_acceptance": "not_evaluated",
        "rendered_page_count": None, "exact_text_preserved": True, "logical_order_preserved": True,
        "source_character_coverage": "not_proven", "source_pages": deepcopy(pages),
        "review": deepcopy(decisions["review"]), "structural_paragraphs": structural,
        "paragraphs": [{"paragraph_id": c["paragraph_id"], "location": locations[c["paragraph_id"]],
            "regions": deepcopy(c["regions"]), "unmapped_reason": c["unmapped_reason"]}
            for c in decisions["paragraphs"]],
        "qualifications": [{"paragraph_id": c["paragraph_id"], "reason": c["unmapped_reason"]}
                           for c in decisions["paragraphs"] if not c["regions"]]}
    if not require_review:
        mapping["document_reviewed"] = False
    return mapping


def build_docx(docx_bytes: bytes, snapshot: dict, pages: list, decisions: dict) -> SavedDocxLayoutArtifact:
    """Build and verify a detached in-memory copy; never overwrite an input."""
    try:
        if model.inspect_docx(docx_bytes, snapshot["target_lang"]) != snapshot:
            model._fail("snapshot_identity_mismatch")
        checked = model.validate_decisions(snapshot, pages, decisions, require_review=True)
        members, infos, original_root, _, _ = model._load_docx(docx_bytes)
        root, locations, structural = _assemble(original_root, snapshot, checked)
        xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        raw = _write(members, infos, xml)
        mapping = _source_map(snapshot, pages, checked, locations, structural, raw)
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
        root, locations, structural = _assemble(original_root, snapshot, checked)
        xml = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
        raw = _write(members, infos, xml)
        mapping = _source_map(snapshot, pages, checked, locations, structural, raw,
                              require_review=False)
        validate_built_docx(raw, mapping, original_docx=docx_bytes, snapshot=snapshot,
                            pages=pages, decisions=checked, require_review=False)
        return SavedDocxLayoutArtifact(raw, mapping)
    except model.SavedDocxLayoutError:
        raise
    except (TypeError, ValueError, KeyError, IndexError, OverflowError, AttributeError, etree.XPathError):
        model._fail("invalid_saved_docx_writer_input")
