"""Bounded source-terminal signing blocks; pagination flags never edit content."""
from copy import deepcopy
import re
import unicodedata
from lxml import etree
from . import saved_docx_layout as model

W=model.W
VERSION='bounded_terminal_signature_context_v1'
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


def derive(root,nodes,mapped,rows,choices,owners,plan,members):
    """Derive whole owned paragraph groups, never case IDs or physical page count."""
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
        if before not in nodes.values() or _on(before,'keepNext',members):continue
        if _on(nodes[selected[-1]],'keepNext',members):continue
        result.append({'source_page_number':footer['source_page_number'],'context_ids':context,
            'signature_ids':signatures,'footer_ids':footer_ids,'paragraph_ids':selected})
    return result


def apply(root,nodes,mapped,rows,choices,owners,plan,members):
    from .saved_docx_layout_writer import _set,_P_ORDER
    groups=derive(root,nodes,mapped,rows,choices,owners,plan,members)
    plan['source_closing_group_version']=VERSION;plan['source_closing_groups']=groups
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


def expected_presentation(baseline,identifier,plan):
    from .saved_docx_layout_writer import _set,_P_ORDER
    result=deepcopy(baseline)
    for name,ids in plan.get('source_closing_pagination_additions',{}).items():
        if identifier in ids:
            props=result.find(W+'pPr')
            if props is None:props=etree.Element(W+'pPr');result.insert(0,props)
            _set(props,name,order=_P_ORDER)
    return result


def verify(root,mapping,rows,choices,owners,plan,members,baseline_nodes=None):
    """Re-derive eligibility and inventory actual node adjacency/keep-chain ends."""
    nodes={}
    for row in mapping['paragraphs']:
        hits=root.xpath(row['location'],namespaces={'w':W[1:-1]})
        if len(hits)!=1 or hits[0] in nodes.values():model._fail('source_closing_group_mapping')
        nodes[row['paragraph_id']]=hits[0]
    mapped={r['paragraph_id']:r for r in mapping['paragraphs']}
    # Derivation must inspect the pre-addition keep state to detect incoming chains.
    groups=derive(root,nodes,mapped,rows,choices,owners,plan,members)
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
        selected=[nodes[i] for i in group['paragraph_ids']]
        indices=[body.index(n) for n in selected]
        if indices!=list(range(indices[0],indices[0]+len(indices))):model._fail('source_closing_group_adjacency')
        if _on(body[indices[0]-1],'keepNext',members) or _on(selected[-1],'keepNext',members):model._fail('source_closing_group_boundary_chain')
        if any(not _on(n,'keepNext',members) for n in selected[:-1]) or any(not _on(n,'keepLines',members) for n in selected):model._fail('source_closing_group_pagination')
