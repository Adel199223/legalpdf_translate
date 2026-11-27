"""Fresh pagination-only terminal groups over exact generated reference frames."""
from copy import deepcopy
from lxml import etree

from . import saved_docx_layout as model

W = model.W
NS = {'w': W[1:-1]}
STRUCTURAL_VERSION = 'bounded_terminal_structural_keep_v1'


def _signature(node, omitted=()):
    if node in omitted:
        return ('owned_paragraph',)
    return (node.tag, tuple(sorted(node.attrib.items())), node.text or '', node.tail or '',
            tuple(_signature(child, omitted) for child in node))


def _hash(node):
    return model._sha(model._c14n(node).encode())


def baseline_context(artifact, snapshot, pages, decisions, context):
    """Recompute the known writer geometry; serialized plan membership is insufficient."""
    from .saved_docx_layout_writer import _horizontal_plan, _ordinary_presentation
    members, _ = model._package(artifact.docx_bytes)
    root = model._xml(members['word/document.xml'])
    ordinary_context={k:context[k] for k in ('selected_pages','page_groups','local_source_folio_proof') if k in context}
    presentation, presentation_plan = _ordinary_presentation(snapshot, pages, decisions, ordinary_context)
    is_ar=snapshot['target_lang']=='AR'
    horizontal = _horizontal_plan(root, snapshot, pages, presentation) if is_ar else []
    # The writer emits this key only for its AR horizontal-presentation route.
    # An explicit null or invented EN plan is not the legitimate absent key.
    if (presentation_plan != artifact.source_map.get('ordinary_presentation_plan')
            or ('derived_horizontal_plan' in artifact.source_map) != is_ar
            or is_ar and horizontal != artifact.source_map['derived_horizontal_plan']):
        model._fail('source_closing_carrier_plan')
    structural = artifact.source_map.get('structural_paragraphs', [])
    if len(set(structural)) != len(structural):
        model._fail('source_closing_structural_ownership')
    nodes = {}
    for row in artifact.source_map['paragraphs']:
        hits = root.xpath(row['location'], namespaces=NS)
        if len(hits) != 1 or hits[0] in nodes.values():
            model._fail('source_closing_group_mapping')
        nodes[row['paragraph_id']] = hits[0]
    return {'root': root, 'nodes': nodes, 'structural': structural, 'horizontal': horizontal,
            'mapped': {row['paragraph_id']: {'part_uri':'word/document.xml',**row} for row in artifact.source_map['paragraphs']},
            'members': members}


def _owned_plain(identifier, node, nodes, mapped, rows, members):
    from .ordinary_terminal_closing_group import _plain, _on
    if not _plain(identifier, nodes, mapped, rows, node.getparent()):
        return False
    if rows[identifier].get('has_numbering') or _on(node, 'pageBreakBefore', members):
        return False
    try:
        styles = model._styles(members)
        if model._paragraph_inventory(node, styles)['text'] != rows[identifier]['text']:
            return False
        if any(model._effective(node, run, styles)['page_break_before'] for run in node.findall(W+'r')):
            return False
    except model.SavedDocxLayoutError:
        return False
    return True


def _empty(node, root, baseline):
    from .saved_docx_layout_writer import _empty as writer_empty
    from .ordinary_terminal_closing_group import _on
    path = root.getroottree().getpath(node)
    try:
        inventory=model._paragraph_inventory(node,model._styles(baseline['members']))
    except model.SavedDocxLayoutError:
        return False
    return (not inventory['text'] and not inventory['has_page_break']
            and baseline['structural'].count(path) == 1 and _signature(node) == _signature(writer_empty())
            and not _on(node, 'keepNext', baseline['members'])
            and not _on(node, 'pageBreakBefore', baseline['members']))


def _frame(identifier, root, nodes, mapped, rows, choices, page, baseline):
    """Exactly one writer-owned paragraph, its side empties and following anchor."""
    from .saved_docx_layout_writer import _table, _empty as writer_empty
    from .ordinary_terminal_closing_group import _on
    body = root.find(W+'body'); node = nodes[identifier]
    if (choices[identifier]['role'] != 'reference'
            or not _owned_plain(identifier, node, nodes, mapped, rows, baseline['members'])):
        return None
    matches = [p for p in baseline['horizontal'] if p['paragraph_ids'] == [identifier]
               and p['page_number'] == page]
    if len(matches) != 1:
        return None
    item = matches[0]; widths = [width for width in item['cell_widths_twips'] if width]
    content = 1 if item['cell_widths_twips'][0] else 0
    if not 2 <= len(widths) <= 3 or not 0 <= content < len(widths):
        return None
    table = node.getparent().getparent().getparent()
    if table.tag != W+'tbl' or table.getparent() is not body:
        return None
    trs = table.findall(W+'tr'); cells = trs[0].findall(W+'tc') if len(trs) == 1 else []
    if (len(cells) != len(widths) or len(list(table.iter(W+'tbl'))) != 1
            or any(len(cell.findall(W+'p')) != 1 for cell in cells)
            or list(table.iter(W+'p')) != [cell.find(W+'p') for cell in cells]
            or cells[content].find(W+'p') is not node):
        return None
    try:
        expected, targets = _table(widths, spacer_indices=[i for i in range(len(widths)) if i != content])
    except model.SavedDocxLayoutError:
        return None
    empties = []
    for index, (cell, _) in enumerate(targets):
        if index == content:
            cell.append(deepcopy(node))
        else:
            empty = cells[index].find(W+'p')
            if not _empty(empty, root, baseline):
                return None
            empties.append(empty); cell.append(writer_empty())
    if _signature(table, (node,)) != _signature(expected, (targets[content][0].find(W+'p'),)):
        return None
    position = body.index(table)
    if position + 1 >= len(body) or not _empty(body[position+1], root, baseline):
        return None
    anchor = body[position+1]; empties.append(anchor)
    if _on(baseline['nodes'][identifier], 'keepNext', baseline['members']):
        return None
    certificate = {'kind': 'exact_writer_horizontal_reference_frame', 'paragraph_id': identifier,
        'source_page_number': page, 'derived_horizontal_plan': deepcopy(item),
        'table_location': root.getroottree().getpath(table),
        'scaffold_sha256': model._sha(repr(_signature(table, (node,))).encode()),
        'structural_locations': [root.getroottree().getpath(p) for p in empties]}
    return table, anchor, certificate


def _incoming(table, root, nodes, mapped, rows, choices, owners, page, first, members):
    """An untouched known two-cell stop sentinel; no semantic field assertion."""
    from .saved_docx_layout_writer import _table
    from .ordinary_terminal_closing_group import _on
    body = root.find(W+'body')
    if table.tag != W+'tbl' or table.getparent() is not body:
        return None
    trs = table.findall(W+'tr'); cells = trs[0].findall(W+'tc') if len(trs) == 1 else []
    if (len(cells) != 2 or any(len(cell.findall(W+'p')) != 1 for cell in cells)
            or len(list(table.iter(W+'tbl'))) != 1):
        return None
    paragraphs = [cell.find(W+'p') for cell in cells]
    if list(table.iter(W+'p')) != paragraphs:
        return None
    reverse = {node: identifier for identifier, node in nodes.items()}
    if any(p not in reverse for p in paragraphs):
        return None
    ids = [reverse[p] for p in paragraphs]; start = owners[page].index(first)
    if (start < 2 or owners[page][start-2:start] != ids
            or any(sum(i in group for group in owners.values()) != 1 for i in ids)):
        return None
    for identifier, node in zip(ids, paragraphs):
        if (choices[identifier]['role'] not in {'body','list','institution','reference','recipient'}
                or not _owned_plain(identifier, node, nodes, mapped, rows, members)
                or _on(node, 'keepNext', members) or _on(node, 'pageBreakBefore', members)):
            return None
    try:
        widths = [int(cell.find(W+'tcPr/'+W+'tcW').get(W+'w')) for cell in cells]
        right = int(cells[0].find(W+'tcPr/'+W+'tcMar/'+W+'right').get(W+'w'))
        left = int(cells[1].find(W+'tcPr/'+W+'tcMar/'+W+'left').get(W+'w'))
        if right != left or not 0 <= right <= 360:
            return None
        expected, targets = _table(widths, gutter_pt=right/10)
    except (AttributeError, ValueError, TypeError, model.SavedDocxLayoutError):
        return None
    for (cell, _), node in zip(targets, paragraphs):
        cell.append(deepcopy(node))
    if _signature(table, paragraphs) != _signature(expected, [cell.find(W+'p') for cell, _ in targets]):
        return None
    return {'kind': 'exact_writer_two_cell_stop_sentinel', 'source_page_number': page,
            'paragraph_ids': ids, 'scaffold_sha256': model._sha(repr(_signature(table, paragraphs)).encode())}


def derive(root, nodes, mapped, rows, choices, owners, plan, members, baseline):
    from .ordinary_terminal_closing_group import _plain, _visible, _signature as signature_line, _on
    if plan['source_footers'] or baseline is None:
        return []
    body = root.find(W+'body'); result = []
    for association in plan.get('retained_terminal_associations', []):
        page = association['source_page_number']; ids = owners[page]; footer = association['paragraph_ids']
        if not 1 <= len(footer) <= 2 or ids[-len(footer):] != footer:
            continue
        start = len(ids)-len(footer); tail = start
        while tail and choices[ids[tail-1]]['role'] == 'signature': tail -= 1
        signatures = ids[tail:start]
        if not 2 <= len(signatures) <= 6:
            continue
        if any(not _plain(i,nodes,mapped,rows,body) or not signature_line(rows[i]['text'])
               or not _owned_plain(i,nodes[i],nodes,mapped,rows,members) for i in signatures):
            continue
        context = []; chars = words = 0
        while tail and len(context) < 2 and choices[ids[tail-1]]['role'] == 'body':
            identifier = ids[tail-1]
            if not _plain(identifier,nodes,mapped,rows,body) or not _owned_plain(identifier,nodes[identifier],nodes,mapped,rows,members): break
            text = _visible(rows[identifier]['text']); length = len(text); count = len(text.split())
            if not text.strip() or length > 320 or count > 60 or chars+length > 480 or words+count > 80: break
            context.insert(0,identifier); tail -= 1; chars += length; words += count
        selected = context + signatures + footer
        if (len(selected) > 10 or len(selected) == len(ids)
                or any([p for p,owned in owners.items() if identifier in owned] != [page] for identifier in selected)
                or any(_visible(rows[i]['text']) is None for i in selected)
                or sum(len(_visible(rows[i]['text'])) for i in selected) > 1600):
            continue
        physical = []; carrier = None; valid = True
        for identifier in selected:
            node = nodes[identifier]
            if node.getparent() is body:
                if not _owned_plain(identifier,node,nodes,mapped,rows,members): valid = False; break
                physical.append(node)
            else:
                if (carrier is not None or identifier not in footer or len(footer) != 2
                        or identifier != footer[0] or nodes[footer[-1]].getparent() is not body): valid = False; break
                found = _frame(identifier,root,nodes,mapped,rows,choices,page,baseline)
                if found is None: valid = False; break
                table, anchor, carrier = found; physical.extend((table,anchor))
        if not valid or not physical: continue
        positions = [body.index(node) for node in physical]
        if positions != list(range(positions[0],positions[0]+len(positions))) or positions[0] == 0: continue
        before = body[positions[0]-1]; boundary = None
        if before in nodes.values():
            if _on(before,'keepNext',members) or _on(before,'pageBreakBefore',members): continue
        else:
            boundary = _incoming(before,root,nodes,mapped,rows,choices,owners,page,selected[0],members)
            if boundary is None: continue
        if nodes[selected[-1]].getparent() is not body or _on(nodes[selected[-1]],'keepNext',members): continue
        result.append({'source_page_number':page,'context_ids':context,'signature_ids':signatures,
            'footer_ids':list(footer),'paragraph_ids':selected,
            'retained_association_sha256':model._sha(model._canonical(association)),
            'in_body_pagination_only':True,
            **({'reference_carrier':carrier} if carrier is not None else {}),
            **({'predecessor_boundary':boundary} if boundary is not None else {})})
    return result


def structural_additions(root, groups, baseline):
    from .saved_docx_layout_writer import _set, _P_ORDER
    result = []; seen = set()
    for group in groups:
        for path in group.get('reference_carrier',{}).get('structural_locations',[]):
            if path in seen: model._fail('source_closing_structural_ownership')
            seen.add(path); hits = root.xpath(path,namespaces=NS)
            old = baseline['root'].xpath(path,namespaces=NS)
            if len(hits) != 1 or len(old) != 1 or not _empty(old[0],baseline['root'],baseline):
                model._fail('source_closing_structural_ownership')
            additions = []
            props = hits[0].find(W+'pPr')
            for name in ('keepNext','keepLines'):
                previous = props.find(W+name)
                if previous is None or not model._on(previous):
                    _set(props,name,order=_P_ORDER); additions.append(name)
            result.append({'baseline_location':path,'baseline_sha256':_hash(old[0]),'additions':additions})
    return result


def verify(root, nodes, rows, choices, owners, plan, members, baseline):
    """Derive from trusted pre-closing reconstruction; compare only explicit deltas."""
    from .saved_docx_layout_writer import _set, _P_ORDER
    from .ordinary_terminal_closing_group import _on
    expected = derive(baseline['root'],baseline['nodes'],baseline['mapped'],rows,choices,owners,
                      plan,baseline['members'],baseline)
    actual = [group for group in plan['source_closing_groups'] if group.get('in_body_pagination_only')]
    if actual != expected: model._fail('source_closing_group_eligibility')
    copy = deepcopy(baseline['root'])
    expected_ledger = structural_additions(copy,expected,baseline)
    ledger = plan.get('source_closing_structural_additions')
    if ledger != {'version':STRUCTURAL_VERSION,'paragraphs':expected_ledger}:
        model._fail('source_closing_structural_delta')
    for item in expected_ledger:
        hits = root.xpath(item['baseline_location'],namespaces=NS)
        old = baseline['root'].xpath(item['baseline_location'],namespaces=NS)
        if len(hits) != 1 or len(old) != 1 or _hash(old[0]) != item['baseline_sha256']:
            model._fail('source_closing_structural_delta')
        wanted = deepcopy(old[0]); props = wanted.find(W+'pPr')
        for name in item['additions']: _set(props,name,order=_P_ORDER)
        if _signature(hits[0]) != _signature(wanted): model._fail('source_closing_structural_delta')
    for group in expected:
        for identifier in group['paragraph_ids']:
            if not _on(nodes[identifier],'keepLines',members): model._fail('source_closing_group_pagination')
        if any(not _on(nodes[i],'keepNext',members) for i in group['paragraph_ids'][:-1]):
            model._fail('source_closing_group_pagination')
        if _on(nodes[group['paragraph_ids'][-1]],'keepNext',members):
            model._fail('source_closing_group_boundary_chain')
