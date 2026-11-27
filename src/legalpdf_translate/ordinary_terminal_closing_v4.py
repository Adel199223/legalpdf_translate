"""Finite raw signature labels; source-owned pagination only, never role inference."""
from copy import deepcopy
import re
import unicodedata

from . import saved_docx_layout as model

W = model.W
VERSION = 'bounded_terminal_signature_context_v4'
KIND = 'source_terminal_signature_label_group_v1'
NS = {'w': W[1:-1]}


def _canonical(value):
    return model._canonical(value)


def placeholder(text):
    """Return exact raw spans without normalization or directional projection."""
    if type(text) is not str or len(text) > 1600:
        return None
    match = re.fullmatch(r' *(?P<label>[^_]*?)(?P<line>_{3,}) *', text)
    if match is None:
        return None
    label = match['label'].rstrip(' ')
    label_span = delimiter_span = None
    if label:
        if len(label) > 80:
            return None
        if label[-1] not in ':\uff1a':
            return None
        prefix = label[:-1]
        if len(prefix.split()) > 12 or not prefix.strip(' '):
            return None
        if prefix.count('(') != prefix.count(')') or prefix.count('(') > 1:
            return None
        if '(' in prefix:
            start, end = prefix.index('('), prefix.index(')')
            if start >= end:
                return None
            inside = prefix[start+1:end]
            outside = prefix[:start] + prefix[end+1:]
            if not any(unicodedata.category(c).startswith('L') for c in inside):
                return None
        else:
            outside = prefix
        if (not any(unicodedata.category(c).startswith('L') for c in outside)
                or any(c not in ' ()' and not unicodedata.category(c).startswith(('L', 'M')) for c in prefix)):
            return None
        start = match.start('label')
        label_span = {'start': start, 'end': start+len(prefix),
            'sha256': model._sha(prefix.encode())}
        delimiter_span = {'start': start+len(prefix), 'end': start+len(label),
            'sha256': model._sha(label[-1].encode())}
    elif match['label'].strip(' '):
        return None
    return {'label_span': label_span, 'delimiter_span': delimiter_span,
        'underscore_span': {'start': match.start('line'), 'end': match.end('line'),
            'sha256': model._sha(match['line'].encode())}}


def artifact_context(artifact):
    members, _ = model._package(artifact.docx_bytes)
    root = model._xml(members['word/document.xml'])
    mapped = {row['paragraph_id']: row for row in artifact.source_map['paragraphs']}
    nodes = {}
    for identifier, row in mapped.items():
        hits = root.xpath(row['location'], namespaces=NS)
        if row.get('part_uri', 'word/document.xml') != 'word/document.xml' or len(hits) != 1 or hits[0] in nodes.values():
            model._fail('source_closing_group_mapping')
        nodes[identifier] = hits[0]
    return {'root': root, 'nodes': nodes, 'mapped': mapped, 'members': members}


def _owned(identifier, nodes, mapped, rows, members, *, footer=False):
    from .ordinary_terminal_closing_group import _plain, _on
    node = nodes[identifier]
    if (not _plain(identifier, nodes, mapped, rows, node.getroottree().getroot().find(W+'body'), footer=footer)
            or rows[identifier].get('has_numbering') or _on(node, 'pageBreakBefore', members)):
        return False
    expected = rows[identifier]['text']
    if rows[identifier].get('has_page_break'):
        tokens = rows[identifier]['tokens']
        if (not footer or not expected.endswith('\f') or expected.count('\f') != 1
                or not tokens or tokens[-1]['kind'] != 'page_break'):
            return False
        expected = expected[:-1]
    try:
        styles = model._styles(members)
        return model._paragraph_inventory(node, styles)['text'] == expected
    except model.SavedDocxLayoutError:
        return False


def derive(root, nodes, mapped, rows, choices, owners, plan, members, inherited=()):
    from .ordinary_terminal_closing_group import _visible, _on
    if plan.get('footer_placement') != 'terminal_body_flow_v1':
        return []
    occupied = {identifier for group in inherited for identifier in group['paragraph_ids']}
    body = root.find(W+'body')
    result = []
    if len(set(nodes.values())) != len(nodes):
        return []
    for footer in plan['source_footers']:
        page = footer['source_page_number']
        ids = owners.get(page, [])
        foot = footer['paragraph_ids']
        if (type(page) is not int or not 1 <= len(foot) <= 2 or ids[-len(foot):] != foot
                or len(set(foot)) != len(foot)):
            continue
        start = len(ids)-len(foot)
        tail = start
        while tail and choices[ids[tail-1]]['role'] == 'signature' and start-tail < 7:
            tail -= 1
        signs = ids[tail:start]
        if not 2 <= len(signs) <= 6:
            continue
        # Whole rows and total budget are checked before regex or inventories.
        if any(type(rows[i]['text']) is not str or len(rows[i]['text']) > 1600 for i in signs+foot):
            continue
        if sum(len(rows[i]['text']) for i in signs+foot) > 1600:
            continue
        proofs = []
        for i in signs:
            proof = placeholder(rows[i]['text'])
            if proof is None:
                break
            proofs.append({'paragraph_id': i, 'role': choices[i]['role'],
                'snapshot_paragraph_sha256': rows[i]['paragraph_sha256'],
                'raw_text_sha256': model._sha(rows[i]['text'].encode()), **proof})
        if (len(proofs) != len(signs) or not any(p['delimiter_span'] is not None
                and rows[p['paragraph_id']]['text'][p['delimiter_span']['start']:p['delimiter_span']['end']] == '\uff1a'
                for p in proofs)):
            continue
        context = []
        chars = words = 0
        while tail and len(context) < 2 and choices[ids[tail-1]]['role'] == 'body':
            i = ids[tail-1]
            if len(rows[i]['text']) > 320 or not _owned(i, nodes, mapped, rows, members):
                break
            text = _visible(rows[i]['text'])
            if text is None or not text.strip() or len(text.split()) > 60 or chars+len(text) > 480 or words+len(text.split()) > 80:
                break
            context.insert(0, i); tail -= 1; chars += len(text); words += len(text.split())
        selected = context+signs+foot
        if (len(selected) > 10 or len(selected) == len(ids) or occupied.intersection(selected)
                or sum(len(rows[i]['text']) for i in selected) > 1600
                or any([p for p, group in owners.items() if i in group] != [page] for i in selected)
                or any(not _owned(i, nodes, mapped, rows, members, footer=i in foot) for i in selected)):
            continue
        positions = [body.index(nodes[i]) for i in selected]
        if positions != list(range(positions[0], positions[0]+len(positions))) or positions[0] == 0:
            continue
        before = body[positions[0]-1]
        if before not in nodes.values() or _on(before, 'keepNext', members) or _on(before, 'pageBreakBefore', members):
            continue
        if _on(nodes[selected[-1]], 'keepNext', members):
            continue
        result.append({'kind': KIND, 'source_page_number': page, 'context_ids': context,
            'signature_ids': signs, 'footer_ids': list(foot), 'paragraph_ids': selected,
            'source_footer_sha256': model._sha(_canonical(footer)), 'placeholder_proofs': proofs})
        occupied.update(selected)
    return result


def apply_new(nodes, groups, plan, members):
    from .ordinary_terminal_closing_group import _on
    from .saved_docx_layout_writer import _set, _P_ORDER
    for group in groups:
        for name, ids in [('keepNext', group['paragraph_ids'][:-1]), ('keepLines', group['paragraph_ids'])]:
            for i in ids:
                if _on(nodes[i], name, members):
                    continue
                props = nodes[i].find(W+'pPr')
                if props is None:
                    props = model.etree.Element(W+'pPr'); nodes[i].insert(0, props)
                _set(props, name, order=_P_ORDER)
                plan['source_closing_pagination_additions'][name].append(i)
    plan['source_closing_groups'].extend(groups)
    plan['source_closing_group_version'] = VERSION


def _restore(actual, before, name):
    """Restore absence or the exact prior property, attributes and child order."""
    props, old = actual.find(W+'pPr'), before.find(W+'pPr')
    if props is None:
        model._fail('source_closing_group_inverse')
    for node in list(props.findall(W+name)):
        props.remove(node)
    prior = old.find(W+name) if old is not None else None
    if prior is not None:
        following = {node.tag for node in list(old)[old.index(prior)+1:]}
        position = next((i for i, node in enumerate(props) if node.tag in following), len(props))
        props.insert(position, deepcopy(prior))
    if old is None and len(props) == 0 and not props.attrib and not props.text:
        actual.remove(props)


def verify(root, mapping, rows, choices, owners, plan, members, before, legacy_context):
    from . import ordinary_terminal_closing_group as closing
    pre_root, pre_nodes, pre_mapped, pre_members = (before[k] for k in ('root', 'nodes', 'mapped', 'members'))
    if _canonical(mapping.get('paragraphs')) != _canonical(list(pre_mapped.values())):
        model._fail('source_closing_group_mapping')
    old = closing.derive(pre_root, pre_nodes, pre_mapped, rows, choices, owners, plan, pre_members,
        version=closing.VERSION_V3, base_context=legacy_context)
    new = derive(pre_root, pre_nodes, pre_mapped, rows, choices, owners, plan, pre_members, old)
    if _canonical(old+new) != _canonical(plan.get('source_closing_groups')):
        model._fail('source_closing_group_eligibility')
    simulated = deepcopy(pre_root)
    simulated_nodes = {i: simulated.xpath(pre_root.getroottree().getpath(n), namespaces=NS)[0] for i, n in pre_nodes.items()}
    wanted = deepcopy(plan)
    closing.apply(simulated, simulated_nodes, pre_mapped, rows, choices, owners, wanted, pre_members,
        version=closing.VERSION_V3, base_context=legacy_context)
    apply_new(simulated_nodes, new, wanted, pre_members)
    for key in ('source_closing_groups', 'source_closing_pagination_additions', 'source_closing_structural_additions'):
        if _canonical(wanted[key]) != _canonical(plan.get(key)):
            model._fail('source_closing_group_delta')
    if model._c14n(root) != model._c14n(simulated):
        model._fail('source_closing_group_pagination')
    inverse = deepcopy(root)
    for name, ids in wanted['source_closing_pagination_additions'].items():
        for i in ids:
            path = pre_root.getroottree().getpath(pre_nodes[i])
            _restore(inverse.xpath(path, namespaces=NS)[0], pre_nodes[i], name)
    for row in wanted['source_closing_structural_additions']['paragraphs']:
        path = row['baseline_location']
        for name in row['additions']:
            _restore(inverse.xpath(path, namespaces=NS)[0], pre_root.xpath(path, namespaces=NS)[0], name)
    if model._c14n(inverse) != model._c14n(pre_root):
        model._fail('source_closing_group_inverse')
