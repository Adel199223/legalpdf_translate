"""Source-local accepted footer pagination; no relocation or role authority."""
from copy import deepcopy
import re

from . import saved_docx_layout as model
from . import ordinary_terminal_closing_v4 as v4

W = model.W
NS = v4.NS
VERSION = 'bounded_terminal_signature_context_v5'
KIND = 'source_local_accepted_footer_signature_group_v1'
LEDGER = 'local_source_footer_associations'


def association_context(snapshot, decisions, context, evidence, promoted):
    """Requalify accepted layout independently of any closing group or direction ledger."""
    from .ordinary_layout_contracts import proposal_source_evidence, PROPOSAL_VERSION_V3, RETAINED_TERMINAL_ASSOCIATIONS_V1
    owners = {page: list(ids) for page, ids in context['page_groups']}
    rows = {p['id']: p for p in snapshot['paragraphs']}
    choices = {p['paragraph_id']: p for p in decisions['paragraphs']}
    selected = context['selected_pages']
    records = evidence.get('pages')
    if (type(records) is not list or len(records) != len(selected)
            or any(type(p) is not int for p in selected)
            or [p.get('page_number') for p in records] != selected
            or any(type(p.get('page_number')) is not int for p in records)):
        model._fail('source_closing_local_association')
    promoted_by_page = {p['source_page_number']: p for p in promoted}
    result = []
    for page in records:
        number = page['page_number']
        ids = owners[number]
        membership = [{**deepcopy(choices[i]), 'regions': [{'page_number': number, 'bbox_px': [0, 0, 1, 1]}]} for i in ids]
        view = {'paragraphs': [rows[i] for i in ids], 'decisions': {'paragraphs': membership}}
        proposal = {'version': PROPOSAL_VERSION_V3, 'page_number': number,
            'paragraphs': [choices[i] for i in ids], 'bands': decisions['bands'],
            'paragraph_partitions': decisions.get('paragraph_partitions', []),
            'source_coverage_findings': [], 'source_layout_evidence': page.get('layout', [])}
        checked = proposal_source_evidence(snapshot, view, proposal)
        accepted = [item for item in checked['layout'] if item['kind'] == 'source_footer']
        if len(accepted) > 1:
            model._fail('source_footer_duplicate_page')
        if not accepted:
            continue
        footer = accepted[0]
        if number in promoted_by_page:
            old = promoted_by_page[number]
            if model._canonical(footer) != model._canonical({k: old[k] for k in ('kind', 'paragraph_ids', 'bbox')}):
                model._fail('source_closing_local_association')
            continue
        identity = page.get('retained_terminal_associations')
        if (type(identity) is not dict
                or set(identity) != {'version', 'canonical_proposal_sha256', 'associations', 'review_required'}
                or identity['version'] != RETAINED_TERMINAL_ASSOCIATIONS_V1 or identity['review_required'] is not True
                or type(identity['associations']) is not list):
            model._fail('source_closing_local_association')
        canonical, response = identity['canonical_proposal_sha256'], page.get('response_sha256')
        if any(type(value) is not str or re.fullmatch(r'[a-f0-9]{64}', value) is None for value in (canonical, response)):
            model._fail('source_closing_local_association')
        result.append({'source_page_number': number, 'accepted_footer': deepcopy(footer),
            'canonical_proposal_sha256': canonical, 'response_sha256': response})
    return result


def derive(root, nodes, mapped, rows, choices, owners, plan, members, associations, inherited=()):
    from .ordinary_terminal_closing_group import _signature, _visible, _on
    if type(associations) is not list:
        model._fail('source_closing_local_association')
    body = root.find(W+'body')
    if len(set(nodes.values())) != len(nodes):
        return []
    reverse = {node: i for i, node in nodes.items()}
    positions = {node: index for index, node in enumerate(body)}
    owner_pages = {}
    for page, ids in owners.items():
        for i in ids:
            owner_pages.setdefault(i, []).append(page)
    occupied = {i for group in inherited for i in group['paragraph_ids']}
    result = []
    for association in associations:
        page = association['source_page_number']
        foot = association['accepted_footer']['paragraph_ids']
        ids = owners.get(page, [])
        if (type(page) is not int or not 1 <= len(foot) <= 2 or len(set(foot)) != len(foot)
                or ids[-len(foot):] != foot or any(choices[i]['role'] != 'source_folio' for i in foot)):
            continue
        start = len(ids)-len(foot)
        tail = start
        # Inspect six rows plus one rejection sentinel, never an unbounded tail.
        while tail and start-tail < 7 and choices[ids[tail-1]]['role'] == 'signature':
            tail -= 1
        signs = ids[tail:start]
        if not 2 <= len(signs) <= 6:
            continue
        base = signs+foot
        if any(type(rows[i]['text']) is not str or len(rows[i]['text']) > 1600 for i in base):
            continue
        base_chars = sum(len(rows[i]['text']) for i in base)
        if base_chars > 1600:
            continue
        context = []
        chars = words = 0
        while tail and len(context) < 2 and choices[ids[tail-1]]['role'] == 'body':
            i = ids[tail-1]
            raw = rows[i]['text']
            if type(raw) is not str or len(raw) > 320 or chars+len(raw) > 480 or base_chars+chars+len(raw) > 1600:
                break
            text = _visible(raw)
            if text is None or not text.strip():
                break
            count = len(text.split())
            if count > 60 or words+count > 80:
                break
            context.insert(0, i); tail -= 1; chars += len(raw); words += count
        selected = context+base
        if (len(selected) > 10 or len(selected) == len(ids) or occupied.intersection(selected)
                or any(owner_pages.get(i) != [page] for i in selected)):
            continue
        # Raw bounds above precede inherited regex and per-node inventory work.
        if (not all(_signature(rows[i]['text']) for i in signs)
                or not any(_visible(rows[i]['text']).strip().split(':', 1)[0].strip() and ':' in _visible(rows[i]['text']) for i in signs)
                or any(not v4._owned(i, nodes, mapped, rows, members, footer=i in foot) for i in selected)):
            continue
        physical = [positions.get(nodes[i]) for i in selected]
        if (any(p is None for p in physical) or physical != list(range(physical[0], physical[0]+len(physical)))
                or physical[0] == 0):
            continue
        before = body[physical[0]-1]
        if (before not in reverse or _on(before, 'keepNext', members) or _on(before, 'pageBreakBefore', members)
                or _on(nodes[selected[-1]], 'keepNext', members)):
            continue
        proofs = [{'paragraph_id': i, 'role': choices[i]['role'],
            'snapshot_paragraph_sha256': rows[i]['paragraph_sha256'],
            'raw_text_sha256': model._sha(rows[i]['text'].encode())} for i in selected]
        result.append({'kind': KIND, 'source_page_number': page, 'context_ids': context,
            'signature_ids': signs, 'footer_ids': list(foot), 'paragraph_ids': selected,
            'local_association_sha256': model._sha(model._canonical(association)), 'paragraph_proofs': proofs})
        occupied.update(selected)
    return result


def apply(root, nodes, mapped, rows, choices, owners, plan, members, associations, legacy_context):
    from . import ordinary_terminal_closing_group as closing
    old = closing.derive(root, nodes, mapped, rows, choices, owners, plan, members,
        version=closing.VERSION_V4, base_context=legacy_context)
    new = derive(root, nodes, mapped, rows, choices, owners, plan, members, associations, old)
    closing.apply(root, nodes, mapped, rows, choices, owners, plan, members,
        version=closing.VERSION_V4, base_context=legacy_context)
    v4.apply_new(nodes, new, plan, members)
    plan['source_closing_group_version'] = VERSION
    plan[LEDGER] = deepcopy(associations)


def verify(root, mapping, rows, choices, owners, plan, members, before, legacy_context, associations):
    from . import ordinary_terminal_closing_group as closing
    if (type(associations) is not list
            or model._canonical(plan.get(LEDGER)) != model._canonical(associations)):
        model._fail('source_closing_local_association')
    pre_root, pre_nodes, pre_mapped, pre_members = (before[k] for k in ('root', 'nodes', 'mapped', 'members'))
    if model._canonical(mapping.get('paragraphs')) != model._canonical(list(pre_mapped.values())):
        model._fail('source_closing_group_mapping')
    old = closing.derive(pre_root, pre_nodes, pre_mapped, rows, choices, owners, plan, pre_members,
        version=closing.VERSION_V4, base_context=legacy_context)
    new = derive(pre_root, pre_nodes, pre_mapped, rows, choices, owners, plan, pre_members, associations, old)
    if model._canonical(old+new) != model._canonical(plan.get('source_closing_groups')):
        model._fail('source_closing_group_eligibility')
    simulated = deepcopy(pre_root)
    simulated_nodes = {i: simulated.xpath(pre_root.getroottree().getpath(n), namespaces=NS)[0] for i, n in pre_nodes.items()}
    wanted = deepcopy(plan)
    apply(simulated, simulated_nodes, pre_mapped, rows, choices, owners, wanted, pre_members, associations, legacy_context)
    for key in (LEDGER, 'source_closing_groups', 'source_closing_pagination_additions', 'source_closing_structural_additions'):
        if model._canonical(wanted[key]) != model._canonical(plan.get(key)):
            model._fail('source_closing_group_delta')
    if model._c14n(root) != model._c14n(simulated):
        model._fail('source_closing_group_pagination')
    inverse = deepcopy(root)
    for name, ids in wanted['source_closing_pagination_additions'].items():
        for i in ids:
            path = pre_root.getroottree().getpath(pre_nodes[i])
            v4._restore(inverse.xpath(path, namespaces=NS)[0], pre_nodes[i], name)
    for row in wanted['source_closing_structural_additions']['paragraphs']:
        path = row['baseline_location']
        for name in row['additions']:
            v4._restore(inverse.xpath(path, namespaces=NS)[0], pre_root.xpath(path, namespaces=NS)[0], name)
    if model._c14n(inverse) != model._c14n(pre_root):
        model._fail('source_closing_group_inverse')