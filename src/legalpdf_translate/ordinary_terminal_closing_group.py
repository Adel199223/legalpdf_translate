"""Bounded source-terminal signing blocks; pagination flags never edit content."""
from copy import deepcopy
import re
import unicodedata
from lxml import etree
from . import saved_docx_layout as model

W=model.W
VERSION='bounded_terminal_signature_context_v1'
VERSION_V2='bounded_terminal_signature_context_v2'
VERSION_V3='bounded_terminal_signature_context_v3'
VERSION_V4='bounded_terminal_signature_context_v4'
VERSION_V5='bounded_terminal_signature_context_v5'
_LINE=re.compile(r'(?P<label>[^_…─—]{0,80}?)(?P<line>_{3,}|\.{6,}|…{3,}|─{3,}|—{3,})')
_DIR={'\u200e','\u200f','\u2066','\u2069'}


def _on(node,name,members):
    styles,_,defaults=model._styles(members);props=node.find(W+'pPr')
    style=props.find(W+'pStyle') if props is not None else None
    default=next((s.get(W+'styleId') for s in styles.values() if s.get(W+'type')=='paragraph' and s.get(W+'default')=='1'),None)
    chain=model._style_chain(style.get(W+'val') if style is not None else default,styles)
    found=[p.find(W+name) for p in [defaults,*(s.find(W+'pPr') for s in chain),props] if p is not None and p.find(W+name) is not None]
    return model._on(found[-1]) if found else False


def _visible(text):
    if any(unicodedata.category(c) in {'Cc','Zl','Zp'} or unicodedata.category(c)=='Cf' and c not in _DIR for c in text):return None
    depth=0
    for c in text:
        if c=='\u2066':
            if depth:return None
            depth=1
        elif c=='\u2069':
            if not depth:return None
            depth=0
    if depth or text.count('\u200e')%2 or text.count('\u200f')%2:return None
    return ''.join(c for c in text if c not in _DIR)


def _plain(identifier,nodes,mapped,rows,body,*,footer=False):
    node=nodes[identifier];row=rows[identifier]
    if node.getparent() is not body or mapped[identifier].get('parts'):return False
    if mapped[identifier].get('part_uri')!='word/document.xml':return False
    if row.get('has_field') or 'numPr' in row.get('ppr_xml','') or (row.get('has_page_break') and not footer):return False
    if any(t['kind']!='t' for t in row['tokens']) and not footer:return False
    if any(child.tag not in {W+'pPr',W+'r'} for child in node):return False
    if any(child.tag not in {W+'rPr',W+'t'} for run in node.findall(W+'r') for child in run):return False
    if any(n.tag not in {W+'p',W+'pPr',W+'r',W+'rPr',W+'t',
        *{W+x for x in model._PPROPS},*{W+x for x in model._RPROPS}} for n in node.iter()):return False
    if any(n.tag in {W+'numPr',W+'sectPr',W+'framePr',W+'pageBreakBefore'} for n in node.iter()):return False
    return _visible(row['text']) is not None


def _signature(text):
    text=_visible(text)
    if text is None:return False
    match=_LINE.fullmatch(text.strip())
    if match is None:return False
    label=match['label'].strip()
    return not label or (len(label.split())<=12 and label.endswith(':') and label.count(':')==1
        and any(unicodedata.category(c).startswith('L') for c in label)
        and not any(c in label for c in '.!?؟;؛'))


def _table_boundary(table,root,nodes,mapped,rows,choices,owners,plan,members,page,first):
    """One exact generated, re-certified field pair; no generic table bypass."""
    from .ordinary_terminal_source_layout import _field_pairs
    from .saved_docx_layout_writer import _table
    body=root.find(W+'body')
    if table.tag!=W+'tbl' or table.getparent() is not body:return None
    trs=table.findall(W+'tr');cells=trs[0].findall(W+'tc') if len(trs)==1 else []
    if len(cells)!=2 or any(len(cell.findall(W+'p'))!=1 for cell in cells):return None
    paragraphs=[cell.find(W+'p') for cell in cells]
    if list(table.iter(W+'p'))!=paragraphs or len(list(table.iter(W+'tbl')))!=1:return None
    reverse={node:i for i,node in nodes.items()}
    if any(p not in reverse for p in paragraphs):return None
    ids=[reverse[p] for p in paragraphs]
    source_ids=owners[page];start=source_ids.index(first)
    if (start<2 or source_ids[start-2:start]!=ids
            or any(sum(i in values for values in owners.values())!=1 for i in ids)
            or any(mapped[i].get('parts') or rows[i].get('has_numbering') for i in ids)):
        return None
    for i,p,cell in zip(ids,paragraphs,cells):
        if not _plain(i,nodes,mapped,rows,cell) or _on(p,'keepNext',members):return None
        try:
            context=model._styles(members)
            inventory=model._paragraph_inventory(p,context)
            if inventory['text']!=rows[i]['text']:return None
            if any(model._effective(p,run,context)['page_break_before'] for run in p.findall(W+'r')):return None
        except model.SavedDocxLayoutError:
            return None
    pairs=[p for p in _field_pairs(nodes,choices,rows,owners,mapped)
           if p['basis']=='canonical_two_cell_label_value_row'
           and {p['label_id'],p['value_id']}==set(ids) and p['source_page_number']==page]
    if len(pairs)!=1 or pairs[0] not in plan.get('spacing_field_pairs',[]):return None
    # Match the writer's exact non-panel scaffold, with the existing paragraph
    # nodes removed. Unknown/merged/custom/hidden table structure cannot pass.
    try:
        widths=[int(cell.find(W+'tcPr/'+W+'tcW').get(W+'w')) for cell in cells]
        right=int(cells[0].find(W+'tcPr/'+W+'tcMar/'+W+'right').get(W+'w'))
        left=int(cells[1].find(W+'tcPr/'+W+'tcMar/'+W+'left').get(W+'w'))
        if right!=left or not 0<=right<=360:return None
        expected,_=_table(widths,gutter_pt=right/10)
    except (AttributeError,ValueError,TypeError,model.SavedDocxLayoutError):
        return None
    actual=deepcopy(table)
    for cell in actual.findall(W+'tr/'+W+'tc'):
        for p in list(cell.findall(W+'p')):cell.remove(p)
    def signature(node):
        return (node.tag,tuple(sorted(node.attrib.items())),node.text or '',node.tail or '',tuple(signature(n) for n in node))
    if signature(actual)!=signature(expected):return None
    return {'kind':'certified_two_cell_field_table','source_page_number':page,
            'paragraph_ids':ids,'field_pair':deepcopy(pairs[0]),
            'table_sha256':model._sha(model._c14n(table).encode())}


def derive(root,nodes,mapped,rows,choices,owners,plan,members,*,version=VERSION,base_context=None,local_footer_context=None):
    """Derive whole owned paragraph groups, never case IDs or physical page count."""
    if version==VERSION_V5:
        from . import ordinary_terminal_closing_v5 as v5
        old=derive(root,nodes,mapped,rows,choices,owners,plan,members,version=VERSION_V4,base_context=base_context)
        return old+v5.derive(root,nodes,mapped,rows,choices,owners,plan,members,local_footer_context,old)
    if version==VERSION_V4:
        from . import ordinary_terminal_closing_v4 as v4
        old=derive(root,nodes,mapped,rows,choices,owners,plan,members,version=VERSION_V3,base_context=base_context)
        return old+v4.derive(root,nodes,mapped,rows,choices,owners,plan,members,old)
    if version==VERSION_V3:
        from . import ordinary_terminal_closing_v3 as v3
        return (derive(root,nodes,mapped,rows,choices,owners,plan,members,version=VERSION_V2)
            +v3.derive(root,nodes,mapped,rows,choices,owners,plan,members,base_context))
    if version not in {VERSION,VERSION_V2}:model._fail('source_closing_group_version')
    body=root.find(W+'body');result=[]
    if len(set(nodes.values()))!=len(nodes):return result
    for footer in plan['source_footers']:
        ids=owners[footer['source_page_number']];footer_ids=footer['paragraph_ids']
        if not 1<=len(footer_ids)<=2 or ids[-len(footer_ids):]!=footer_ids:continue
        start=len(ids)-len(footer_ids);tail=start
        while tail and choices[ids[tail-1]]['role']=='signature':tail-=1
        signatures=ids[tail:start]
        if not 2<=len(signatures)<=6:continue
        if any(not _plain(i,nodes,mapped,rows,body,footer=i in footer_ids) for i in signatures+footer_ids):continue
        if not all(_signature(rows[i]['text']) for i in signatures):continue
        context=[];chars=words=0
        while tail and len(context)<2 and choices[ids[tail-1]]['role']=='body':
            i=ids[tail-1]
            if not _plain(i,nodes,mapped,rows,body):break
            text=_visible(rows[i]['text']);length=len(text);count=len(text.split())
            if not text.strip() or length>320 or count>60 or chars+length>480 or words+count>80:break
            context.insert(0,i);tail-=1;chars+=length;words+=count
        selected=context+signatures+footer_ids
        if len(selected)>10 or len(selected)==len(ids) or sum(len(_visible(rows[i]['text'])) for i in selected)>1600:continue
        positions=[body.index(nodes[i]) for i in selected]
        if positions!=list(range(positions[0],positions[0]+len(positions))):continue
        if positions[0]==0:continue
        before=body[positions[0]-1]
        boundary=None
        if before in nodes.values():
            if _on(before,'keepNext',members):continue
        elif version==VERSION_V2:
            boundary=_table_boundary(before,root,nodes,mapped,rows,choices,owners,plan,members,
                                     footer['source_page_number'],selected[0])
            if boundary is None:continue
        else:continue
        if _on(nodes[selected[-1]],'keepNext',members):continue
        result.append({'source_page_number':footer['source_page_number'],'context_ids':context,
            'signature_ids':signatures,'footer_ids':footer_ids,'paragraph_ids':selected,
            **({'predecessor_boundary':boundary} if boundary is not None else {})})
    return result


def apply(root,nodes,mapped,rows,choices,owners,plan,members,*,version=VERSION,base_context=None,local_footer_context=None):
    from .saved_docx_layout_writer import _set,_P_ORDER
    if version==VERSION_V5:
        from . import ordinary_terminal_closing_v5 as v5
        v5.apply(root,nodes,mapped,rows,choices,owners,plan,members,local_footer_context,base_context)
        return
    if version==VERSION_V4:
        from . import ordinary_terminal_closing_v4 as v4
        old=derive(root,nodes,mapped,rows,choices,owners,plan,members,version=VERSION_V3,base_context=base_context)
        new=v4.derive(root,nodes,mapped,rows,choices,owners,plan,members,old)
        apply(root,nodes,mapped,rows,choices,owners,plan,members,version=VERSION_V3,base_context=base_context)
        v4.apply_new(nodes,new,plan,members)
        return
    groups=derive(root,nodes,mapped,rows,choices,owners,plan,members,version=version,base_context=base_context)
    plan['source_closing_group_version']=version;plan['source_closing_groups']=groups
    additions={'keepNext':[],'keepLines':[]}
    for group in groups:
        for name,ids in [('keepNext',group['paragraph_ids'][:-1]),('keepLines',group['paragraph_ids'])]:
            for i in ids:
                props=nodes[i].find(W+'pPr')
                if props is None:props=etree.Element(W+'pPr');nodes[i].insert(0,props)
                existing=props.find(W+name)
                if existing is None or not model._on(existing):
                    _set(props,name,order=_P_ORDER);additions[name].append(i)
    plan['source_closing_pagination_additions']=additions
    if version==VERSION_V3:
        from . import ordinary_terminal_closing_v3 as v3
        plan['source_closing_structural_additions']={'version':v3.STRUCTURAL_VERSION,
            'paragraphs':v3.structural_additions(root,groups,base_context)}


def expected_presentation(baseline,identifier,plan):
    from .saved_docx_layout_writer import _set,_P_ORDER
    result=deepcopy(baseline)
    for name,ids in plan.get('source_closing_pagination_additions',{}).items():
        if identifier in ids:
            props=result.find(W+'pPr')
            if props is None:props=etree.Element(W+'pPr');result.insert(0,props)
            _set(props,name,order=_P_ORDER)
    return result


def verify(root,mapping,rows,choices,owners,plan,members,baseline_nodes=None,*,base_context=None,pre_closing_context=None,local_footer_context=None):
    """Re-derive eligibility and inventory actual node adjacency/keep-chain ends."""
    if plan.get('source_closing_group_version')==VERSION_V5:
        from . import ordinary_terminal_closing_v5 as v5
        if pre_closing_context is None or base_context is None or local_footer_context is None:model._fail('source_closing_carrier_plan')
        v5.verify(root,mapping,rows,choices,owners,plan,members,pre_closing_context,base_context,local_footer_context)
        return
    if plan.get('source_closing_group_version')==VERSION_V4:
        from . import ordinary_terminal_closing_v4 as v4
        if pre_closing_context is None or base_context is None:model._fail('source_closing_carrier_plan')
        v4.verify(root,mapping,rows,choices,owners,plan,members,pre_closing_context,base_context)
        return
    nodes={}
    for row in mapping['paragraphs']:
        hits=root.xpath(row['location'],namespaces={'w':W[1:-1]})
        if len(hits)!=1 or hits[0] in nodes.values():model._fail('source_closing_group_mapping')
        nodes[row['paragraph_id']]=hits[0]
    mapped={r['paragraph_id']:r for r in mapping['paragraphs']}
    # Derivation must inspect the pre-addition keep state to detect incoming chains.
    version=plan.get('source_closing_group_version',VERSION)
    if version==VERSION_V3:
        from . import ordinary_terminal_closing_v3 as v3
        if base_context is None:model._fail('source_closing_carrier_plan')
        groups=(derive(root,nodes,mapped,rows,choices,owners,plan,members,version=VERSION_V2)
            +v3.derive(base_context['root'],base_context['nodes'],base_context['mapped'],rows,choices,owners,
                       plan,base_context['members'],base_context))
        v3.verify(root,nodes,rows,choices,owners,plan,members,base_context)
    else:
        groups=derive(root,nodes,mapped,rows,choices,owners,plan,members,version=version)
    if groups!=plan.get('source_closing_groups'):model._fail('source_closing_group_eligibility')
    additions=plan.get('source_closing_pagination_additions')
    permitted={'keepNext':[i for g in groups for i in g['paragraph_ids'][:-1]],
               'keepLines':[i for g in groups for i in g['paragraph_ids']]}
    if type(additions) is not dict or set(additions)!=set(permitted):model._fail('source_closing_group_delta')
    for name,ids in additions.items():
        if (type(ids) is not list or any(type(i) is not str for i in ids)
                or len(set(ids))!=len(ids) or not set(ids)<=set(permitted[name])):
            model._fail('source_closing_group_delta')
    if baseline_nodes is not None:
        expected={name:[] for name in permitted}
        for name,ids in permitted.items():
            for i in ids:
                if name=='keepNext' and i in plan.get('terminal_keep_next_ids',[]):continue
                before=baseline_nodes[i].find(W+'pPr/'+W+name)
                if before is None or not model._on(before):expected[name].append(i)
        if additions!=expected:model._fail('source_closing_group_delta')
    body=root.find(W+'body')
    for group in groups:
        if group.get('in_body_pagination_only'):continue  # V3 independently reconstructs the complete physical carrier.
        selected=[nodes[i] for i in group['paragraph_ids']]
        indices=[body.index(n) for n in selected]
        if indices!=list(range(indices[0],indices[0]+len(indices))):model._fail('source_closing_group_adjacency')
        before=body[indices[0]-1]
        if before in nodes.values():
            if _on(before,'keepNext',members):model._fail('source_closing_group_boundary_chain')
        elif (version not in {VERSION_V2,VERSION_V3} or _table_boundary(before,root,nodes,mapped,rows,choices,owners,plan,members,
                group['source_page_number'],group['paragraph_ids'][0])!=group.get('predecessor_boundary')):
            model._fail('source_closing_group_boundary_chain')
        if _on(selected[-1],'keepNext',members):model._fail('source_closing_group_boundary_chain')
        if any(not _on(n,'keepNext',members) for n in selected[:-1]) or any(not _on(n,'keepLines',members) for n in selected):model._fail('source_closing_group_pagination')
