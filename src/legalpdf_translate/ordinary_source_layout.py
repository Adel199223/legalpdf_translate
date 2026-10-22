"""Closed source-evidence transformations layered over immutable V6 candidates."""
from copy import deepcopy
from io import BytesIO
import re
import unicodedata
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
from lxml import etree
from . import saved_docx_layout as model

VERSION = "saved_docx_layout_writer_source_layout_v7"
W = model.W
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
NS = {"w": W[1:-1]}
CLOCK_DIRECTION_V1 = 'clock_h_colon_ltr_v1'
INLINE_FOLIO_DIRECTION_V1 = 'source_bound_folio_separator_ltr_v1'
_FOLIO_NUMBER = r'\u200e?[0-9\u0660-\u0669\u06f0-\u06f9]{1,4}\u200e?'
_INLINE_FRACTION = re.compile(_FOLIO_NUMBER + r' */ *' + _FOLIO_NUMBER)
_CLOCK = re.compile(r'\u200e?[0-9]{2}\u200e?:(?:\u200e?[0-9]{2}\u200e?:)?\u200e?[0-9]{2}h\u200e?')
_CLOCK_LEFT = set('([{«“"\'،؛')
_CLOCK_RIGHT = set(')]}»”"\'.,;!?،؛؟')


def _clock_space(char):
    return char.isspace() and unicodedata.category(char) not in {'Cc', 'Cf'}


def _clock_matches(text):
    """Recognition only; original marks, characters and offsets are never replaced."""
    for match in _CLOCK.finditer(text):
        start, end = match.span()
        if start and not (_clock_space(text[start - 1]) or text[start - 1] in _CLOCK_LEFT):
            continue
        tail = end
        while tail < len(text) and text[tail] in _CLOCK_RIGHT:
            tail += 1
        if tail < len(text) and not _clock_space(text[tail]):
            continue
        numbers = match.group().replace('\u200e', '')[:-1].split(':')
        if int(numbers[0]) > 23 or any(int(value) > 59 for value in numbers[1:]):
            continue
        yield start, end


def _clock_run_inventory(paragraph, row):
    """Decline hidden structure; return exact direct-run character ownership."""
    if (row.get('has_field') or row.get('has_numbering') or row.get('has_page_break')
            or 'numPr' in row.get('ppr_xml', '') or any(t['kind'] != 't' for t in row['tokens'])
            or any(child.tag not in {W+'pPr', W+'r'} for child in paragraph)):
        return None
    props = paragraph.findall(W+'pPr')
    if len(props) != 1 or props[0].find(W+'numPr') is not None or props[0].find(W+'sectPr') is not None:
        return None
    bidi = props[0].findall(W+'bidi')
    if len(bidi) != 1 or bidi[0].get(W+'val') not in {'1', 'true', 'on'}:
        return None
    runs = paragraph.findall(W+'r')
    offsets, text, offset = [], '', 0
    for index, run in enumerate(runs):
        if (any(child.tag not in {W+'rPr', W+'t'} for child in run)
                or len(run.findall(W+'rPr')) > 1):
            return None
        value = ''.join(t.text or '' for t in run.findall(W+'t'))
        offsets.append((index, offset, offset + len(value), run, value))
        text += value
        offset += len(value)
    if (text != ''.join(t['text'] for t in row['tokens'])
            or any(unicodedata.category(char) in {'Cc', 'Cf'} and char != '\u200e' for char in text)):
        return None
    return text, offsets


def _clock_rtl(run):
    props = run.findall(W+'rPr')
    if len(props) != 1:
        return None
    values = props[0].findall(W+'rtl')
    if (len(values) != 1 or set(values[0].attrib) != {W+'val'} or len(values[0])
            or values[0].get(W+'val') not in {'0', '1'}):
        return None
    return values[0]


def _clock_colons(text, offsets, start, end):
    """Every colon is whole-run; digits and h must already be explicit LTR."""
    colons = []
    for index, left, right, run, value in offsets:
        if right <= start or left >= end:
            continue
        direction = _clock_rtl(run)
        part = text[max(left, start):min(right, end)]
        if any(char in '0123456789h' for char in part) and (direction is None or direction.get(W+'val') != '0'):
            return None
        for position in range(max(left, start), min(right, end)):
            if text[position] == ':':
                if value != ':' or right != left + 1 or direction is None:
                    return None
                colons.append((index, position, direction))
    return colons


def _apply_clock_direction(nodes, mapped, rows, owners, decisions, plan, target_lang, selected_pages):
    plan.update(clock_direction_version=CLOCK_DIRECTION_V1, clock_ltr_spans=[])
    if target_lang != 'AR':
        return
    excluded = {p['paragraph_id'] for p in decisions.get('paragraph_partitions', [])}
    excluded.update(p['paragraph_ids'][0] for p in plan['decorative_rules'])
    ownership = {}
    for page, ids in owners.items():
        for pid in ids:
            ownership.setdefault(pid, []).append(page)
    owner = {pid: pages[0] for pid, pages in ownership.items() if len(pages) == 1 and pages[0] in selected_pages}
    for identifier, row in rows.items():
        if (identifier not in owner or identifier in excluded or mapped[identifier].get('parts')
                or mapped[identifier].get('part_uri', 'word/document.xml') != 'word/document.xml'):
            continue
        inventory = _clock_run_inventory(nodes[identifier], row)
        if inventory is None:
            continue
        text, offsets = inventory
        for start, end in _clock_matches(text):
            colons = _clock_colons(text, offsets, start, end)
            if colons is None:
                continue
            changed = [(index, position, node) for index, position, node in colons if node.get(W+'val') == '1']
            if not changed:
                continue
            plan['clock_ltr_spans'].append({'paragraph_id':identifier, 'source_page_number':owner[identifier],
                'start':start, 'end':end, 'clock_text_sha256':model._sha(text[start:end].encode('utf-8')),
                'colon_runs':[{'run_index':index, 'character_offset':position, 'before_rtl':1, 'after_rtl':0}
                              for index, position, _ in changed]})
            for _, _, node in changed:
                node.set(W+'val', '0')


def _checked_clock_plan(plan, expected_mode, rows, owners, selected_pages):
    keys = {'clock_direction_version', 'clock_ltr_spans'}
    if expected_mode is None:
        if keys.intersection(plan): model._fail('source_clock_direction_version')
        return {}
    if (expected_mode != CLOCK_DIRECTION_V1 or plan.get('clock_direction_version') != expected_mode
            or type(plan.get('clock_ltr_spans')) is not list):
        model._fail('source_clock_direction_version')
    by_id, previous = {}, (-1, -1)
    order = {pid:index for index,pid in enumerate(rows)}
    for span in plan['clock_ltr_spans']:
        if (type(span) is not dict or set(span) != {'paragraph_id','source_page_number','start','end','clock_text_sha256','colon_runs'}
                or type(span['paragraph_id']) is not str or span['paragraph_id'] not in rows
                or type(span['source_page_number']) is not int
                or span['source_page_number'] not in selected_pages
                or [page for page,ids in owners.items() if span['paragraph_id'] in ids] != [span['source_page_number']]
                or type(span['start']) is not int or type(span['end']) is not int
                or not 0 <= span['start'] < span['end'] <= len(rows[span['paragraph_id']]['text'])
                or type(span['colon_runs']) is not list or not span['colon_runs']):
            model._fail('source_clock_direction_delta')
        key = (order[span['paragraph_id']], span['start'])
        if key <= previous: model._fail('source_clock_direction_delta')
        previous = key
        by_id.setdefault(span['paragraph_id'], []).append(span)
    return by_id


def _verified_clock_copy(actual, baseline, row, spans):
    """Prove listed actual attributes, undo only them, then compare complete XML."""
    restored = deepcopy(actual)
    if not spans:
        return restored
    inventory = _clock_run_inventory(baseline, row)
    actual_inventory = _clock_run_inventory(restored, row)
    if inventory is None or actual_inventory is None:
        model._fail('source_clock_direction_delta')
    text, offsets = inventory
    matches = set(_clock_matches(text))
    used, previous_end = set(), -1
    for span in spans:
        start, end = span['start'], span['end']
        if ((start, end) not in matches or start < previous_end
                or span['clock_text_sha256'] != model._sha(text[start:end].encode('utf-8'))):
            model._fail('source_clock_direction_delta')
        previous_end = end
        colon_inventory = _clock_colons(text, offsets, start, end)
        if colon_inventory is None: model._fail('source_clock_direction_delta')
        expected = [(index, position) for index, position, node in colon_inventory if node.get(W+'val') == '1']
        declared = []
        for change in span['colon_runs']:
            if (type(change) is not dict or set(change) != {'run_index','character_offset','before_rtl','after_rtl'}
                    or any(type(change[k]) is not int for k in change)
                    or change['before_rtl'] != 1 or change['after_rtl'] != 0):
                model._fail('source_clock_direction_delta')
            key = (change['run_index'], change['character_offset'])
            if key in used or key not in expected: model._fail('source_clock_direction_delta')
            used.add(key);declared.append(key)
            index, position = key
            actual_run = actual_inventory[1][index]
            direction = _clock_rtl(actual_run[3])
            if actual_run[1] != position or actual_run[4] != ':' or direction is None or direction.get(W+'val') != '0':
                model._fail('source_clock_direction_delta')
            direction.set(W+'val', '1')
        if not expected or declared != expected: model._fail('source_clock_direction_delta')
    if model._c14n(restored) != model._c14n(baseline): model._fail('source_clock_direction_delta')
    return restored

def _inline_folio_run_inventory(paragraph, row):
    """Direct plain runs, with only the exact represented terminal page break."""
    tokens = row['tokens']
    terminal_break = bool(tokens and tokens[-1]['kind'] == 'page_break')
    content = tokens[:-1] if terminal_break else tokens
    if (row.get('has_field') or row.get('has_numbering')
            or bool(row.get('has_page_break')) != terminal_break
            or 'numPr' in row.get('ppr_xml', '') or not content
            or any(t['kind'] != 't' for t in content)
            or any(child.tag not in {W+'pPr', W+'r'} for child in paragraph)):
        return None
    props = paragraph.findall(W+'pPr')
    if len(props) != 1 or props[0].find(W+'numPr') is not None or props[0].find(W+'sectPr') is not None:
        return None
    bidi = props[0].findall(W+'bidi')
    if len(bidi) != 1 or bidi[0].get(W+'val') not in {'1', 'true', 'on'}:
        return None
    runs = paragraph.findall(W+'r')
    offsets, text, offset, breaks = [], '', 0, 0
    for index, run in enumerate(runs):
        if len(run.findall(W+'rPr')) > 1 or run.text:
            return None
        rpr = run.find(W+'rPr')
        if rpr is not None and any(node.tag in {W+'vanish', W+'webHidden', W+'specVanish', W+'rPrChange'} for node in rpr.iter()):
            return None
        for child in run:
            if child.tag in {W+'rPr', W+'t'}:
                if child.tag == W+'t' and len(child):
                    return None
                continue
            if (child.tag != W+'br' or not terminal_break or index != len(runs)-1
                    or child is not run[-1] or dict(child.attrib) != {W+'type':'page'}
                    or len(child) or child.text):
                return None
            breaks += 1
        value = ''.join(t.text or '' for t in run.findall(W+'t'))
        offsets.append((index, offset, offset+len(value), run, value))
        text += value
        offset += len(value)
    if (breaks != int(terminal_break) or text != ''.join(t['text'] for t in content)
            or row['text'] != text + ('\f' if terminal_break else '')
            or any(unicodedata.category(char) in {'Cc', 'Cf'} and char != '\u200e' for char in text)):
        return None
    return text, offsets


def _inline_folio_separator(text, offsets, source_span):
    start, end = source_span['start'], source_span['end']
    if (not 0 <= start < end <= len(text) or _INLINE_FRACTION.fullmatch(text[start:end]) is None
            or re.fullmatch(r'\u200e? *', text[end:]) is None
            or start >= 2 and text[start-2:start] == '\u200e\u200e'
            or model._sha(text[start:end].encode()) != source_span['literal_sha256']):
        return None
    separators = []
    for index, left, right, run, value in offsets:
        if right <= start or left >= end:
            continue
        direction = _clock_rtl(run)
        part = text[max(left,start):min(right,end)]
        if any(char.isdecimal() for char in part) and (direction is None or direction.get(W+'val') != '0'):
            return None
        if '/' in part:
            if re.fullmatch(r' */ *', value) is None or direction is None:
                return None
            separators.append((index,left,right,direction))
    return separators[0] if len(separators) == 1 else None


def _inline_folio_expected(nodes, mapped, snapshot, pages, decisions, context):
    """Recompute source qualification and the only allowed baseline run delta."""
    from .ordinary_source_folio_proof import direction_target_spans
    qualified = direction_target_spans(snapshot, pages, decisions, context)
    if snapshot['target_lang'] != 'AR':
        return []
    owners = {}
    for page, ids in context['page_groups']:
        for identifier in ids:
            owners.setdefault(identifier, []).append(page)
    by_id = {span['paragraph_id']:span for span in qualified}
    result = []
    for row in snapshot['paragraphs']:
        identifier = row['id']
        span = by_id.get(identifier)
        node = nodes[identifier]
        if (span is None or owners.get(identifier) != [span['page_number']]
                or mapped[identifier].get('parts')
                or mapped[identifier].get('part_uri','word/document.xml') != 'word/document.xml'
                or node.getparent() is None or node.getparent().tag != W+'body'):
            continue
        inventory = _inline_folio_run_inventory(node,row)
        if inventory is None:
            continue
        separator = _inline_folio_separator(*inventory,span)
        if separator is None or separator[3].get(W+'val') != '1':
            continue
        index,left,right,_ = separator
        result.append({'paragraph_id':identifier,'source_page_number':span['page_number'],
            'start':span['start'],'end':span['end'],'literal_sha256':span['literal_sha256'],
            'separator_runs':[{'run_index':index,'start':left,'end':right,'before_rtl':1,'after_rtl':0}]})
    return result


def _apply_inline_folio_direction(nodes, mapped, snapshot, pages, decisions, context, plan):
    spans = _inline_folio_expected(nodes,mapped,snapshot,pages,decisions,context)
    plan.update(inline_folio_direction_version=INLINE_FOLIO_DIRECTION_V1,inline_folio_ltr_spans=spans)
    for span in spans:
        run = nodes[span['paragraph_id']].findall(W+'r')[span['separator_runs'][0]['run_index']]
        _clock_rtl(run).set(W+'val','0')


def _checked_inline_folio_plan(plan, expected_mode, rows, owners, selected_pages):
    keys = {'inline_folio_direction_version','inline_folio_ltr_spans'}
    if expected_mode is None:
        if keys.intersection(plan):model._fail('source_inline_folio_direction_version')
        return {}
    if (expected_mode != INLINE_FOLIO_DIRECTION_V1 or plan.get('inline_folio_direction_version') != expected_mode
            or type(plan.get('inline_folio_ltr_spans')) is not list):
        model._fail('source_inline_folio_direction_version')
    order = {identifier:index for index,identifier in enumerate(rows)}
    by_id, previous = {}, (-1,-1)
    for span in plan['inline_folio_ltr_spans']:
        if (type(span) is not dict or set(span) != {'paragraph_id','source_page_number','start','end','literal_sha256','separator_runs'}
                or type(span['paragraph_id']) is not str or span['paragraph_id'] not in rows
                or type(span['source_page_number']) is not int or span['source_page_number'] not in selected_pages
                or [page for page,ids in owners.items() if span['paragraph_id'] in ids] != [span['source_page_number']]
                or type(span['start']) is not int or type(span['end']) is not int
                or not 0 <= span['start'] < span['end'] <= len(rows[span['paragraph_id']]['text'])
                or type(span['literal_sha256']) is not str or re.fullmatch(r'[a-f0-9]{64}',span['literal_sha256']) is None
                or type(span['separator_runs']) is not list or len(span['separator_runs']) != 1):
            model._fail('source_inline_folio_direction_delta')
        key = (order[span['paragraph_id']],span['start'])
        if key <= previous:model._fail('source_inline_folio_direction_delta')
        previous = key
        change = span['separator_runs'][0]
        if (type(change) is not dict or set(change) != {'run_index','start','end','before_rtl','after_rtl'}
                or any(type(change[k]) is not int for k in change)
                or change['run_index'] < 0 or not 0 <= change['start'] < change['end']
                or change['before_rtl'] != 1 or change['after_rtl'] != 0):
            model._fail('source_inline_folio_direction_delta')
        by_id.setdefault(span['paragraph_id'],[]).append(span)
    return by_id


def _verified_inline_folio_copy(actual, baseline, row, spans):
    """Undo only enumerated separator attributes; caller composes clock undo."""
    restored = deepcopy(actual)
    if not spans:
        return restored
    inventory = _inline_folio_run_inventory(baseline,row)
    actual_inventory = _inline_folio_run_inventory(restored,row)
    if inventory is None or actual_inventory is None:
        model._fail('source_inline_folio_direction_delta')
    for span in spans:
        separator = _inline_folio_separator(*inventory,span)
        if separator is None or separator[3].get(W+'val') != '1':
            model._fail('source_inline_folio_direction_delta')
        index,left,right,_ = separator
        if span['separator_runs'] != [{'run_index':index,'start':left,'end':right,'before_rtl':1,'after_rtl':0}]:
            model._fail('source_inline_folio_direction_delta')
        if index >= len(actual_inventory[1]):model._fail('source_inline_folio_direction_delta')
        actual_run = actual_inventory[1][index]
        direction = _clock_rtl(actual_run[3])
        if (actual_run[1:3] != (left,right) or actual_run[4] != inventory[1][index][4]
                or direction is None or direction.get(W+'val') != '0'):
            model._fail('source_inline_folio_direction_delta')
        direction.set(W+'val','1')
    return restored


def _xml(raw):
    return model._xml(raw)

def _bytes(root):
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8",standalone=True)

def _folio_ltr_span(paragraph, *, legacy_wrapper=False, controlled_numeric=False):
    """One closed Arabic folio expression; no text or font substitutions."""
    text=''.join(n.text or '' for n in paragraph.iter(W+'t'))
    if controlled_numeric:
        # The primary writer wraps protected numbers with LRM. Accept only
        # those marks at numeric boundaries; retain their exact text/offsets.
        number=r'\u200e?[0-9\u0660-\u0669\u06f0-\u06f9]{1,4}\u200e?'
        match=re.fullmatch(r'(?:الصفحة|صفحة)\s+('+number+r'(?:[ \t]*[/／][ \t]*'+number+r')?)[ \t]*',text)
    else:
        match=re.fullmatch(r'(?:الصفحة|صفحة)\s+([0-9\u0660-\u0669\u06f0-\u06f9]{1,4}(?:\s*/\s*[0-9\u0660-\u0669\u06f0-\u06f9]{1,4})?)\s*',text)
    runs=paragraph.findall(W+'r')
    if match is None or any(child.tag not in {W+'pPr',W+'r'} for child in paragraph):return None
    if any(any(child.tag not in {W+'rPr',W+'t'} for child in run) for run in runs):return None
    start,end=match.span(1);offset=0;before=[];numeric=[];after=[]
    for run in runs:
        value=''.join(n.text or '' for n in run.findall(W+'t'))
        for left,right,destination in ((offset,min(offset+len(value),start),before),(max(offset,start),min(offset+len(value),end),numeric),(max(offset,end),offset+len(value),after)):
            if right<=left:continue
            piece=deepcopy(run)
            for node in list(piece.findall(W+'t')):piece.remove(node)
            node=etree.SubElement(piece,W+'t');node.text=value[left-offset:right-offset]
            node.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
            if destination is numeric or destination is before:
                props=piece.find(W+'rPr')
                if props is None:props=etree.Element(W+'rPr');piece.insert(0,props)
                for old in list(props.findall(W+'rtl')):props.remove(old)
                etree.SubElement(props,W+'rtl').set(W+'val','0' if destination is numeric else '1')
            destination.append(piece)
        offset+=len(value)
    if not numeric:return None
    for run in runs:paragraph.remove(run)
    paragraph.extend(before)
    if legacy_wrapper:
        direction=etree.SubElement(paragraph,W+'dir');direction.set(W+'val','ltr');direction.extend(numeric)
    else:
        paragraph.extend(numeric)
    paragraph.extend(after)
    return {'start':start,'end':end,'literal':text[start:end]}

def _pack(members):
    out=BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED) as z:
        for name in sorted(members):
            info=ZipInfo(name,date_time=(1980,1,1,0,0,0));info.compress_type=ZIP_DEFLATED;z.writestr(info,members[name])
    return out.getvalue()

def _node_at(root,path):
    found=root.xpath(path,namespaces=NS)
    if len(found)!=1 or found[0].tag!=W+"p":model._fail("source_layout_location_changed")
    return found[0]

def _top(node,body):
    while node.getparent() is not body:
        node=node.getparent()
        if node is None:model._fail("source_layout_body_ownership")
    return node

def transform(base, snapshot, pages, decisions, context, evidence, folio_direction_mode='numeric_run_ltr_v2', clock_direction_mode=None, inline_folio_direction_mode=None, footer_placement_mode=None, source_spacing_mode=None, closing_group_mode=None):
    """No side effects; only explicitly qualified decorative/footer rows may change."""
    from .saved_docx_layout_writer import SavedDocxLayoutArtifact
    from .ordinary_layout_contracts import proposal_source_evidence, PROPOSAL_VERSION_V3
    if folio_direction_mode not in {'legacy_none','direction_wrapper_v1','numeric_run_ltr_v2','numeric_run_ltr_v3'}:model._fail('source_folio_direction_version')
    if clock_direction_mode not in {None, CLOCK_DIRECTION_V1}:model._fail('source_clock_direction_version')
    if inline_folio_direction_mode not in {None, INLINE_FOLIO_DIRECTION_V1}:model._fail('source_inline_folio_direction_version')
    from .ordinary_terminal_source_layout import FOOTER_VERSION, SPACING_VERSION
    if footer_placement_mode not in {None, FOOTER_VERSION}:model._fail('source_footer_placement_version')
    if source_spacing_mode not in {None, SPACING_VERSION} or (source_spacing_mode is not None and footer_placement_mode is None):model._fail('source_spacing_version')
    if closing_group_mode not in {None, 'bounded_terminal_signature_context_v1'} or closing_group_mode is not None and footer_placement_mode is None:model._fail('source_closing_group_version')
    if base.source_map.get("writer_version")!="saved_docx_layout_writer_ordinary_presentation_v6":model._fail("source_layout_base_version")
    if type(evidence) is not dict or evidence.get("version")!="ordinary_source_evidence_v1" or type(evidence.get("pages")) is not list:model._fail("source_layout_evidence_invalid")
    # Revalidate the evidence against the trusted snapshot and current decisions.
    owners={page:list(ids) for page,ids in context["page_groups"]}
    rows={p["id"]:p for p in snapshot["paragraphs"]}
    choices={p["paragraph_id"]:p for p in decisions["paragraphs"]}
    layout=[];seen=set()
    for page in evidence["pages"]:
        number=page.get("page_number")
        if number not in owners or number in seen:model._fail("source_layout_evidence_page")
        seen.add(number);ids=owners[number]
        membership=[{**deepcopy(choices[i]),"regions":[{"page_number":number,"bbox_px":[0,0,1,1]}]} for i in ids]
        view={"paragraphs":[rows[i] for i in ids],"decisions":{"paragraphs":membership}}
        proposal={"version":PROPOSAL_VERSION_V3,"page_number":number,"paragraphs":[choices[i] for i in ids],"bands":decisions["bands"],"paragraph_partitions":decisions.get("paragraph_partitions",[]),"source_coverage_findings":[],"source_layout_evidence":page.get("layout",[])}
        checked=proposal_source_evidence(snapshot,view,proposal)
        layout.extend({**item,"source_page_number":number} for item in checked["layout"])
    members,_=model._package(base.docx_bytes)
    members=dict(members);root=_xml(members["word/document.xml"]);body=root.find(W+"body")
    mapped={p["paragraph_id"]:p for p in base.source_map["paragraphs"]}
    nodes={i:_node_at(root,p["location"]) for i,p in mapped.items()}
    part_nodes={i:[_node_at(root,p["location"]) for p in row.get("parts",[])] for i,row in mapped.items()}
    structural=[_node_at(root,path) for path in base.source_map["structural_paragraphs"]]
    plan={"version":"ordinary_source_layout_plan_v1","evidence_sha256":model._sha(model._canonical(evidence)),"decorative_rules":[],"source_footers":[],"qualifications":[],"footer_placement":"source_footer_on_first_output_page_of_source_section"}
    if folio_direction_mode!='legacy_none':plan['folio_ltr_spans']=[]
    if folio_direction_mode in {'numeric_run_ltr_v2','numeric_run_ltr_v3'}:plan['folio_direction_version']=folio_direction_mode
    frames={p["page_number"]:p for p in pages}
    for item in layout:
        if item["kind"]!="decorative_rule":continue
        identifier=item["paragraph_ids"][0];node=nodes[identifier]
        # A rule is a whole owned paragraph. It must not carry hidden content.
        if node.getparent() is not body or any(n.tag not in {W+"pPr",W+"r"} for n in node):model._fail("source_rule_structure")
        text="".join(n.text or "" for n in node.iter(W+"t"))
        for run in list(node.findall(W+"r")):node.remove(run)
        ppr=node.find(W+"pPr")
        if ppr is None:ppr=etree.Element(W+"pPr");node.insert(0,ppr)
        for name in ("pBdr","ind"): 
            for old in list(ppr.findall(W+name)):ppr.remove(old)
        borders=etree.SubElement(ppr,W+"pBdr");edge=etree.SubElement(borders,W+"bottom")
        for key,value in {"val":"single","sz":"4","space":"0","color":"000000"}.items():edge.set(W+key,value)
        section=body.find(W+"sectPr");size=section.find(W+"pgSz");margin=section.find(W+"pgMar")
        page_width=int(size.get(W+"w"));left_margin=int(margin.get(W+"left"));right_margin=int(margin.get(W+"right"))
        box=item["bbox"];ind=etree.SubElement(ppr,W+"ind");ind.set(W+"left",str(round(page_width*box[0])-left_margin));ind.set(W+"right",str(round(page_width*(1-box[2]))-right_margin))
        plan["decorative_rules"].append({**deepcopy(item),"removed_decorative_text":text})
    footers={item["source_page_number"]:item for item in layout if item["kind"]=="source_footer"}
    if len(footers)!=sum(item["kind"]=="source_footer" for item in layout):model._fail("source_footer_duplicate_page")
    if footers:
        eligible=set(footers)==set(context["selected_pages"]) and set(owners)==set(context["selected_pages"]) and {i for ids in owners.values() for i in ids}==set(rows)
        section=body.find(W+"sectPr")
        eligible=eligible and section is not None and not list(section.iter(W+"headerReference"))
        # Every top-level physical container belongs to one source page.
        top_pages={}
        for page,ids in owners.items():
            for identifier in ids:top_pages.setdefault(_top(nodes[identifier],body),set()).add(page)
        eligible=eligible and all(len(p)==1 for p in top_pages.values())
        # Custom footers are never silently replaced.
        rels=_xml(members["word/_rels/document.xml.rels"])
        targets={r.get("Id"):"word/"+r.get("Target","") for r in rels}
        from .ordinary_presentation import _v6_page_signature
        referenced_parts={targets.get(ref.get(R+"id")) for ref in section.findall(W+"footerReference")}
        eligible=eligible and len(referenced_parts)<=1
        for ref in section.findall(W+"footerReference"):
            name=targets.get(ref.get(R+"id"));f=_xml(members[name]) if name in members else None
            if f is None:eligible=False;continue
            if any(n.tag!=W+"p" for n in f):eligible=False
            for p in f:
                if list(p.findall(W+"r")) and model._c14n(p)!=model._c14n(_v6_page_signature(f.nsmap,snapshot["target_lang"])):eligible=False
        if not eligible:plan["qualifications"].append("source_footer_kept_in_flow_incomplete_or_custom_section_ownership")
        else:
            types=_xml(members["[Content_Types].xml"])
            def add_footer(name,footer):
                if name in members:model._fail("source_footer_part_collision")
                members[name]=_bytes(footer)
                rid="rIdSourceLayout"+str(len(rels)+1)
                relationship=etree.SubElement(rels,REL+"Relationship",Id=rid,Type=R[1:-1]+"/footer",Target=name[5:])
                etree.SubElement(types,CT+"Override",PartName="/"+name,ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml")
                return rid
            next_part=max([int(re.fullmatch(r'word/footer([0-9]+)\.xml',name).group(1)) for name in members if re.fullmatch(r'word/footer([0-9]+)\.xml',name)] or [0])+1
            if referenced_parts:
                from .ordinary_presentation import suppress_footer
                members,removed=suppress_footer(members,base.docx_bytes,snapshot['target_lang'],True)
                empty_name=next(iter(referenced_parts))
                empty_id=next(r.get('Id') for r in rels if targets.get(r.get('Id'))==empty_name)
                plan['suppressed_generated_footer_parts']=removed
            else:
                empty=etree.Element(W+"ftr",nsmap={"w":W[1:-1]});etree.SubElement(empty,W+"p")
                empty_name=f'word/footer{next_part}.xml';next_part+=1
                empty_id=add_footer(empty_name,empty)
            plan['empty_continuation_footer_part']=empty_name
            sections=[]
            for ordinal,page in enumerate(context["selected_pages"],1):
                item=footers[page];footer=etree.Element(W+"ftr",nsmap={"w":W[1:-1]})
                for identifier in item["paragraph_ids"]:
                    node=nodes[identifier]
                    if node.getparent() is not body:model._fail("source_footer_not_plain_body")
                    for br in list(node.iter(W+"br")):
                        if br.get(W+"type")!="page":model._fail("source_footer_control")
                        br.getparent().remove(br)
                    if folio_direction_mode!='legacy_none' and snapshot['target_lang']=='AR' and choices[identifier]['role']=='source_folio':
                        span=_folio_ltr_span(node,legacy_wrapper=folio_direction_mode=='direction_wrapper_v1',
                            controlled_numeric=folio_direction_mode=='numeric_run_ltr_v3')
                        if span is not None:plan['folio_ltr_spans'].append({'paragraph_id':identifier,**span})
                    body.remove(node);footer.append(node)
                name=f"word/footer{next_part}.xml";next_part+=1;first_id=add_footer(name,footer)
                sec=deepcopy(section)
                for old in list(sec.findall(W+"footerReference"))+list(sec.findall(W+"titlePg"))+list(sec.findall(W+"type")):sec.remove(old)
                for typ,rid in (("first",first_id),("default",empty_id),("even",empty_id)):
                    ref=etree.Element(W+"footerReference");ref.set(W+"type",typ);ref.set(R+"id",rid);sec.insert(0,ref)
                kind=etree.Element(W+"type");kind.set(W+"val","nextPage");sec.insert(3,kind)
                title=etree.Element(W+"titlePg");grid=sec.find(W+"docGrid");sec.insert(sec.index(grid) if grid is not None else len(sec),title)
                sections.append((page,sec));plan["source_footers"].append({**deepcopy(item),"part_uri":name})
                for identifier in item["paragraph_ids"]:mapped[identifier]=deepcopy(mapped[identifier]);mapped[identifier]["part_uri"]=name;mapped[identifier]["location"]=footer.getroottree().getpath(nodes[identifier])
            body.remove(section)
            for (page,sec),next_item in zip(sections,sections[1:]):
                next_page=next_item[0]
                starts=[_top(nodes[i],body) for i in owners[next_page] if nodes[i].getparent() is not None and nodes[i].getroottree().getroot() is root]
                if not starts:model._fail("source_section_body_empty")
                start=min(starts,key=body.index)
                anchor=etree.Element(W+"p");ppr=etree.SubElement(anchor,W+"pPr");ppr.append(sec);body.insert(body.index(start),anchor);structural.append(anchor)
            body.append(sections[-1][1])
            # Explicit sections replace raw terminal page breaks, not meaningful text.
            if any(node.get(W+"type")=="page" for node in root.iter(W+"br")):
                model._fail("source_section_unowned_page_break")
            members["word/_rels/document.xml.rels"]=_bytes(rels);members["[Content_Types].xml"]=_bytes(types)
    if footer_placement_mode is not None:
        from .ordinary_terminal_source_layout import apply
        apply(root,nodes,mapped,plan,owners,choices,members,rows,source_spacing_mode)
    if closing_group_mode is not None:
        from .ordinary_terminal_closing_group import apply as closing_apply
        closing_apply(root,nodes,mapped,rows,choices,owners,plan,members)
    if clock_direction_mode is not None:
        _apply_clock_direction(nodes, mapped, rows, owners, decisions, plan, snapshot['target_lang'], context['selected_pages'])
    if inline_folio_direction_mode is not None:
        _apply_inline_folio_direction(nodes,mapped,snapshot,pages,decisions,context,plan)
    members["word/document.xml"]=_bytes(root)
    raw=_pack(members);mapping=deepcopy(base.source_map)
    mapping.update(writer_version=VERSION,docx_sha256=model._sha(raw),base_source_map=deepcopy(base.source_map),source_layout_plan=plan,source_layout_plan_sha256=model._sha(model._canonical(plan)),exact_text_preserved=not bool(plan["decorative_rules"]),exact_meaningful_text_preserved=True)
    for row in mapping["paragraphs"]:
        identifier=row["paragraph_id"]
        if "part_uri" in mapped[identifier]:row.update({k:mapped[identifier][k] for k in ("part_uri","location")})
        else:
            row.update(part_uri="word/document.xml",location=root.getroottree().getpath(nodes[identifier]))
            for part,node in zip(row.get("parts",[]),part_nodes[identifier]):part["location"]=root.getroottree().getpath(node)
        if footer_placement_mode is not None:
            for part,node in zip(row.get("parts",[]),part_nodes[identifier]):part["location"]=root.getroottree().getpath(node)
    mapping["structural_paragraphs"]=[root.getroottree().getpath(n) for n in structural if n.getroottree().getroot() is root]
    if plan['source_footers'] and footer_placement_mode is None:
        mapping['logical_order_preserved']=False
        mapping['original_order_preserved']=False
        mapping['owned_parent_sequence_preserved']=True
        mapping['rendered_order_basis']='package_story_order_not_physical_pagination'
        stories={}
        for row in mapping['paragraphs']:stories.setdefault(row['part_uri'],[]).append(row['paragraph_id'])
        # Body order follows actual DOM, not the logical source-map row order.
        reverse={nodes[i]:i for i in nodes if mapped[i].get('part_uri','word/document.xml')=='word/document.xml'}
        stories['word/document.xml']=[reverse[n] for n in root.iter(W+'p') if n in reverse]
        mapping['rendered_story_paragraph_ids']=stories
        mapping['rendered_paragraph_ids']=[i for part in ['word/document.xml',*[r['part_uri'] for r in plan['source_footers']]] for i in stories.get(part,[])]
    return SavedDocxLayoutArtifact(raw,mapping)


def verify(actual, base, snapshot, pages, decisions, context, evidence, *, expected_folio_direction=None, expected_clock_direction=None, expected_inline_folio_direction=None, expected_footer_placement=None, expected_source_spacing=None, expected_closing_group=None):
    """Reconstruct the closed recipe, then independently inventory actual owned stories."""
    saved_plan=actual.source_map.get('source_layout_plan',{})
    if saved_plan.get('source_footer_placement_version')!=expected_footer_placement or saved_plan.get('source_spacing_version')!=expected_source_spacing:model._fail('source_terminal_policy_version')
    if saved_plan.get('source_closing_group_version')!=expected_closing_group:model._fail('source_closing_group_version')
    mode=saved_plan.get('folio_direction_version','direction_wrapper_v1' if 'folio_ltr_spans' in saved_plan else 'legacy_none')
    if (expected_folio_direction is not None and mode != expected_folio_direction
            or mode == 'numeric_run_ltr_v3' and expected_folio_direction != mode):
        model._fail('source_folio_direction_version')
    clock_rows={r['id']:r for r in snapshot['paragraphs']}
    clock_owners={page:list(ids) for page,ids in context['page_groups']}
    clock_plan=_checked_clock_plan(saved_plan,expected_clock_direction,clock_rows,clock_owners,context['selected_pages'])
    inline_plan=_checked_inline_folio_plan(saved_plan,expected_inline_folio_direction,clock_rows,clock_owners,context['selected_pages'])
    expected=transform(base,snapshot,pages,decisions,context,evidence,mode,expected_clock_direction,expected_inline_folio_direction,expected_footer_placement,expected_source_spacing,expected_closing_group)
    if actual.source_map!=expected.source_map:model._fail("source_layout_map_changed")
    actual_parts,_=model._package(actual.docx_bytes);expected_parts,_=model._package(expected.docx_bytes)
    if actual_parts!=expected_parts:model._fail("source_layout_package_changed")
    base_parts,_=model._package(base.docx_bytes)
    plan=actual.source_map['source_layout_plan']
    allowed_added={item['part_uri'] for item in plan['source_footers']}
    if plan['source_footers'] and plan['empty_continuation_footer_part'] not in base_parts:allowed_added.add(plan['empty_continuation_footer_part'])
    if set(actual_parts)!=set(base_parts)|allowed_added:model._fail('source_layout_package_members')
    permitted={'word/document.xml'}
    if allowed_added:permitted.update({'word/_rels/document.xml.rels','[Content_Types].xml'})
    permitted.update(plan.get('suppressed_generated_footer_parts',[]))
    if any(actual_parts[name]!=base_parts[name] for name in base_parts if name not in permitted):model._fail('source_layout_unaffected_part')
    actual_doc=_xml(actual_parts['word/document.xml']);base_doc=_xml(base_parts['word/document.xml'])
    base_owned={row['paragraph_id']:row for row in base.source_map['paragraphs']}
    if expected_inline_folio_direction is not None:
        base_nodes={identifier:_node_at(base_doc,row['location']) for identifier,row in base_owned.items()}
        actual_owned={row['paragraph_id']:row for row in actual.source_map['paragraphs']}
        independently_qualified=_inline_folio_expected(base_nodes,actual_owned,snapshot,pages,decisions,context)
        if saved_plan['inline_folio_ltr_spans'] != independently_qualified:model._fail('source_inline_folio_direction_delta')
    if plan['source_footers']:
        if expected_footer_placement is not None:
            from .ordinary_terminal_source_layout import verify_terminal_order
            verify_terminal_order(actual_doc,actual.source_map,clock_owners,plan)
        rels=_xml(actual_parts['word/_rels/document.xml.rels']);target={r.get('Id'):'word/'+r.get('Target','') for r in rels}
        sections=list(actual_doc.iter(W+'sectPr'))
        if len(sections)!=len(context['selected_pages']):model._fail('source_section_count')
        for section,item,page in zip(sections,plan['source_footers'],context['selected_pages']):
            title=section.find(W+'titlePg')
            if item['source_page_number']!=page or title is None or title.get(W+'val','true') not in {'true','1','on'}:model._fail('source_section_first_page')
            section_type=section.find(W+'type')
            if section_type is None or section_type.get(W+'val')!='nextPage':model._fail('source_section_next_page')
            references=section.findall(W+'footerReference')
            if len(references)!=3 or {r.get(W+'type') for r in references}!={'first','default','even'}:model._fail('source_section_footer_references')
            for reference in references:
                part=target.get(reference.get(R+'id'))
                if part!=(item['part_uri'] if reference.get(W+'type')=='first' and expected_footer_placement is None else plan['empty_continuation_footer_part']):model._fail('source_section_footer_references')
        empty=_xml(actual_parts[plan['empty_continuation_footer_part']])
        if len(empty)!=1 or empty[0].tag!=W+'p' or list(empty[0].findall(W+'r')) or list(empty.iter(W+'t')) or list(empty.iter(W+'instrText')):model._fail('source_section_continuation_footer')
        from .ordinary_presentation import suppress_footer
        expected_suppressed,_=suppress_footer(base_parts,base.docx_bytes,snapshot['target_lang'],True)
        for name in plan.get('suppressed_generated_footer_parts',[]):
            if actual_parts[name]!=expected_suppressed[name]:model._fail('source_section_generated_footer_delta')
    if expected_closing_group is not None:
        from .ordinary_terminal_closing_group import verify as closing_verify
        closing_verify(actual_doc,actual.source_map,clock_rows,{p['paragraph_id']:p for p in decisions['paragraphs']},clock_owners,plan,actual_parts,
            {i:_node_at(base_doc,row['location']) for i,row in base_owned.items()})
    mapping=actual.source_map;rules={r["paragraph_ids"][0]:r for r in mapping["source_layout_plan"]["decorative_rules"]}
    rows={r["id"]:r for r in snapshot["paragraphs"]};seen=set()
    for owned in mapping["paragraphs"]:
        identifier=owned["paragraph_id"]
        if identifier in seen:model._fail("source_layout_duplicate_owner")
        seen.add(identifier);root=_xml(actual_parts[owned["part_uri"]]);node=_node_at(root,owned["location"])
        visible="".join(n.text or "" for n in node.iter(W+"t"))
        if identifier in rules:
            edge=node.find(W+"pPr/"+W+"pBdr/"+W+"bottom")
            if visible or list(node.findall(W+'r')) or edge is None or dict(edge.attrib)!={W+k:v for k,v in {'val':'single','sz':'4','space':'0','color':'000000'}.items()}:model._fail("source_rule_delta_changed")
            approved=[r for page in evidence['pages'] for r in page['layout'] if r['kind']=='decorative_rule' and r['paragraph_ids']==[identifier]]
            if len(approved)!=1 or rules[identifier]['bbox']!=approved[0]['bbox']:model._fail('source_rule_evidence_changed')
            baseline=_node_at(base_doc,base_owned[identifier]['location'])
            section=base_doc.find('.//'+W+'sectPr');size=section.find(W+'pgSz');margin=section.find(W+'pgMar')
            page_width=int(size.get(W+'w'));left_margin=int(margin.get(W+'left'));right_margin=int(margin.get(W+'right'))
            box=approved[0]['bbox'];indent=node.find(W+'pPr/'+W+'ind')
            if indent is None or dict(indent.attrib)!={W+'left':str(round(page_width*box[0])-left_margin),W+'right':str(round(page_width*(1-box[2]))-right_margin)}:model._fail('source_rule_width_changed')
            original=''.join(n.text or '' for n in baseline.iter(W+'t'))
            if rules[identifier]['removed_decorative_text']!=original:model._fail('source_rule_text_delta_changed')
        elif owned.get("parts"):
            children=[_node_at(root,part['location']) for part in owned['parts']]
            combined=''.join(''.join(n.text or '' for n in child.iter(W+'t')) for child in children)
            original=''.join(t['text'] for t in rows[identifier]['tokens'] if t['kind']=='t')
            if combined!=original:model._fail('source_partition_meaningful_text_changed')
            for child,part in zip(children,base_owned[identifier]['parts']):
                baseline=_node_at(base_doc,part['location'])
                if model._c14n(child)!=model._c14n(baseline):model._fail('source_partition_controls_changed')
        else:
            baseline=deepcopy(_node_at(base_doc,base_owned[identifier]['location']))
            terminal_footer=expected_footer_placement is not None and any(identifier in item['paragraph_ids'] for item in plan['source_footers'])
            if owned['part_uri']!='word/document.xml' or terminal_footer:
                for br in list(baseline.iter(W+'br')):
                    if br.get(W+'type')!='page':model._fail('source_footer_control')
                    br.getparent().remove(br)
                span=next((item for item in plan.get('folio_ltr_spans',[]) if item['paragraph_id']==identifier),None)
                if span is not None:
                    expected_span=_folio_ltr_span(baseline,legacy_wrapper=mode=='direction_wrapper_v1',
                        controlled_numeric=mode=='numeric_run_ltr_v3')
                    if expected_span!={k:span[k] for k in ('start','end','literal')}:model._fail('source_folio_direction_delta')
                    if mode=='direction_wrapper_v1':
                        directions=node.findall(W+'dir')
                        if len(directions)!=1 or directions[0].get(W+'val')!='ltr' or ''.join(n.text or '' for n in directions[0].iter(W+'t'))!=span['literal']:model._fail('source_folio_direction_delta')
                        numeric=directions[0].findall(W+'r')
                    else:
                        if list(node.iter(W+'dir')):model._fail('source_folio_direction_delta')
                        numeric=[];offset=0
                        for run in node.findall(W+'r'):
                            value=''.join(n.text or '' for n in run.iter(W+'t'));end=offset+len(value)
                            if offset<span['end'] and end>span['start']:
                                if offset<span['start'] or end>span['end']:model._fail('source_folio_direction_delta')
                                numeric.append(run)
                            offset=end
                        if ''.join(n.text or '' for run in numeric for n in run.iter(W+'t'))!=span['literal']:model._fail('source_folio_direction_delta')
                    if not numeric or any(run.find(W+'rPr/'+W+'rtl') is None or run.find(W+'rPr/'+W+'rtl').get(W+'val')!='0' for run in numeric):model._fail('source_folio_direction_delta')
            if expected_footer_placement is not None:
                from .ordinary_terminal_source_layout import expected_presentation
                baseline=expected_presentation(baseline,identifier,plan)
            if expected_closing_group is not None:
                from .ordinary_terminal_closing_group import expected_presentation as closing_presentation
                baseline=closing_presentation(baseline,identifier,plan)
            comparison=node
            if owned['part_uri']=='word/document.xml':
                comparison=_verified_inline_folio_copy(node,baseline,rows[identifier],inline_plan.pop(identifier,[]))
                comparison=_verified_clock_copy(comparison,baseline,rows[identifier],clock_plan.pop(identifier,[]))
            if model._c14n(comparison)!=model._c14n(baseline):model._fail('source_layout_run_semantics_changed')
            original="".join(t["text"] for t in rows[identifier]["tokens"] if t["kind"]=="t")
            if visible!=original:model._fail("source_layout_meaningful_text_changed")
    if seen!=set(rows):model._fail("source_layout_coverage_changed")
    if clock_plan:model._fail('source_clock_direction_delta')
    if inline_plan:model._fail('source_inline_folio_direction_delta')


def owned_story_count_descriptor(source_map):
    """Call only after V7 candidate verification; no client-supplied map admission."""
    if source_map.get('writer_version')!=VERSION:raise ValueError('owned_story_count_version')
    rows=[]
    for row in source_map['paragraphs']:
        if row.get('parts'):
            rows.extend({'paragraph_id':part['part_id'],'part_uri':row['part_uri'],'location':part['location']} for part in row['parts'])
        else:rows.append({k:row[k] for k in ('paragraph_id','part_uri','location')})
    return {'version':'ordinary_owned_story_count_v1','docx_sha256':source_map['docx_sha256'],'paragraphs':rows}
