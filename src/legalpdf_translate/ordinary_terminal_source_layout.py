"""Versioned source-footer ownership and baseline-bounded metadata spacing."""
from copy import deepcopy
import unicodedata
import re
from lxml import etree
from . import saved_docx_layout as model

W = model.W
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
FOOTER_VERSION = 'terminal_body_flow_v1'
SPACING_VERSION = 'baseline_metadata_heading_spacing_v1'
_BOOLEAN = re.compile(r'(?:yes|no|oui|non|نعم|لا)(?:\s*[-–—]\s*(?P<label>[^:]{1,40}):\s*(?P<value>[^:]{1,80}))?',re.IGNORECASE)


def _boolean_field(value):
    match=_BOOLEAN.fullmatch(value)
    if match is None:return False
    if match['label'] is None:return True
    label,detail=match['label'].strip(),match['value'].strip()
    return (bool(label and detail) and len(label.split())<=6 and len(detail.split())<=12
        and all(c.isspace() or unicodedata.category(c)[0] in {'L','M','N'} for c in label)
        and not any(c in detail for c in '.!?؟;؛:'))


def _ppr(node):
    props = node.find(W+'pPr')
    if props is None:
        props = etree.Element(W+'pPr');node.insert(0,props)
    return props


def _spacing(props):
    result = {}
    for p in props:
        spacing = p.find(W+'spacing') if p is not None else None
        if spacing is not None:
            if any(spacing.get(W+k) is not None for k in
                   ('beforeLines','afterLines','beforeAutospacing','afterAutospacing')):
                return None
            for key in ('before','after'):
                if spacing.get(W+key) is not None:result[key] = int(spacing.get(W+key))
    return {k:result.get(k,0) for k in ('before','after')}


def _baseline_spacing(row, members):
    styles, _, defaults = model._styles(members)
    original = model._xml(row['ppr_xml'].encode()) if row['ppr_xml'] else None
    style = original.find(W+'pStyle') if original is not None else None
    default = next((s.get(W+'styleId') for s in styles.values()
                    if s.get(W+'type')=='paragraph' and s.get(W+'default')=='1'),None)
    chain = model._style_chain(style.get(W+'val') if style is not None else default,styles)
    return _spacing([defaults,*(s.find(W+'pPr') for s in chain),original])


def _field_pairs(nodes, choices, rows, owners, mapped):
    """A bounded label/value row, never table membership alone, proves fields."""
    reverse={node:identifier for identifier,node in nodes.items()}
    pages={i:p for p,ids in owners.items() for i in ids}
    qualified=[];seen=set()
    for node in nodes.values():
        tr=next((a for a in node.iterancestors() if a.tag==W+'tr'),None)
        if tr is None or tr in seen:continue
        seen.add(tr);cells=tr.findall(W+'tc')
        if len(cells)!=2 or any(list(c.iter(W+'tbl')) for c in cells):continue
        paragraphs=[list(c.iter(W+'p')) for c in cells]
        if any(len(p)!=1 or p[0] not in reverse for p in paragraphs):continue
        ids=[reverse[p[0]] for p in paragraphs]
        if ids[0] not in pages or pages[ids[0]]!=pages.get(ids[1]):continue
        source_ids=owners[pages[ids[0]]];start=source_ids.index(ids[0])
        if source_ids[start:start+2]!=ids or any(mapped[i].get('parts') for i in ids):continue
        if any(choices[i]['role'] not in {'body','list','institution','reference','recipient'}
               or rows[i].get('has_page_break') or rows[i].get('has_field')
               or 'numPr' in rows[i].get('ppr_xml','')
               or any(t['kind']!='t' for t in rows[i]['tokens']) for i in ids):continue
        if any(unicodedata.category(c)=='Cf' and c not in '\u200e\u200f\u2066\u2069'
               for i in ids for c in rows[i]['text']):continue
        visible=[''.join(c for c in rows[i]['text'] if unicodedata.category(c)!='Cf').strip() for i in ids]
        if any(not v or any(unicodedata.category(c)=='Cc' for c in v) for v in visible):continue
        labels=[index for index,v in enumerate(visible)
                if v.endswith(':') and v.count(':')==1 and len(v)<=80 and len(v.split())<=8]
        basis='canonical_two_cell_label_value_row'
        if len(labels)==1:
            label=labels[0];value=visible[1-label]
            if len(value)>160 or len(value.split())>20 or value.endswith(('.','!','?','؟','؛',';')):continue
        else:
            question,value=visible
            if (len(question)>80 or len(question.split())>12
                    or not question.endswith(('?','؟')) or sum(question.count(c) for c in '?؟')!=1
                    or any(c in question for c in '.!;؛:')
                    or any(c in question+value for c in '\"\'“”«»')
                    or not _boolean_field(value) or value.endswith('.')
                    or len(value)>160 or len(value.split())>20):continue
            label=0;basis='canonical_two_cell_boolean_row'
        qualified.append({'label_id':ids[label],'value_id':ids[1-label],
                          'source_page_number':pages[ids[0]],'basis':basis})
    return qualified


def apply(root, nodes, mapped, plan, owners, choices, members, rows, spacing_mode):
    """Move exact source-owned footer nodes after their source's last body node."""
    for identifier in mapped:mapped[identifier]=deepcopy(mapped[identifier])
    body=root.find(W+'body');sections=list(root.iter(W+'sectPr'))
    keep=[]
    if plan['source_footers']:
        if len(sections)!=len(plan['source_footers']):model._fail('source_terminal_section_count')
        for section,item in zip(sections,plan['source_footers']):
            page=item['source_page_number'];ids=item['paragraph_ids']
            if owners[page][-len(ids):]!=ids:model._fail('source_terminal_footer_sequence')
            anchor=section if section.getparent() is body else section.getparent().getparent()
            before=body[body.index(anchor)-1] if body.index(anchor)>0 else None
            group=[]
            if before is not None and before.tag==W+'p' and before in nodes.values():group.append(before)
            for identifier in ids:
                node=nodes[identifier];node.getparent().remove(node)
                body.insert(body.index(anchor),node);group.append(node)
                mapped[identifier]['part_uri']='word/document.xml'
            for node in group[:-1]:
                from .saved_docx_layout_writer import _set, _P_ORDER
                _set(_ppr(node),'keepNext',order=_P_ORDER,val='1')
                keep.append(next(i for i,n in nodes.items() if n is node))
            # All footer references point to the already verified empty story.
            refs=section.findall(W+'footerReference')
            default=next(r for r in refs if r.get(W+'type')=='default')
            for ref in refs:ref.set(R+'id',default.get(R+'id'))
            empty=etree.Element(W+'ftr',nsmap={'w':W[1:-1]});etree.SubElement(empty,W+'p')
            members[item['part_uri']]=etree.tostring(empty,xml_declaration=True,encoding='UTF-8',standalone=True)
        plan['footer_placement']=FOOTER_VERSION
        plan['terminal_keep_next_ids']=keep
    plan['source_footer_placement_version']=FOOTER_VERSION
    for identifier,node in nodes.items():
        if node.getroottree().getroot() is root:
            mapped[identifier]['part_uri']='word/document.xml'
            mapped[identifier]['location']=root.getroottree().getpath(node)
    if spacing_mode is None:return
    if spacing_mode!=SPACING_VERSION:model._fail('source_spacing_version')
    plan['source_spacing_version']=spacing_mode;changes=[]
    pairs=_field_pairs(nodes,choices,rows,owners,mapped)
    plan['spacing_field_pairs']=pairs
    field_ids={i for p in pairs for i in (p['label_id'],p['value_id'])}
    for identifier,node in nodes.items():
        if mapped[identifier].get('parts'):continue
        heading=choices[identifier]['role']=='heading'
        if node.getroottree().getroot() is not root:continue
        # Canonical metadata roles authorize spacing; table membership never does.
        metadata=choices[identifier]['role'] in {'institution','reference','recipient'} or identifier in field_ids
        if not heading and not metadata:continue
        baseline=_baseline_spacing(rows[identifier],members)
        if baseline is None:continue
        caps={k:max(v,120 if heading and k=='before' else 60 if k=='after' else 0)
              for k,v in baseline.items()}
        spacing=node.find(W+'pPr/'+W+'spacing')
        if spacing is None:continue
        if _spacing([node.find(W+'pPr')]) is None:continue
        for key,cap in caps.items():
            value=spacing.get(W+key)
            if value is not None and int(value)>cap:
                spacing.set(W+key,str(cap));changes.append({'paragraph_id':identifier,
                    'attribute':key,'old_twips':int(value),'new_twips':cap,
                    'basis':'baseline_heading' if heading else 'baseline_label_value_field' if identifier in field_ids else 'baseline_metadata_role'})
    plan['baseline_spacing_changes']=changes


def expected_presentation(baseline, identifier, plan):
    """Independent comparison permits exactly the recorded presentation deltas."""
    result=deepcopy(baseline)
    if identifier in plan.get('terminal_keep_next_ids',[]):
        from .saved_docx_layout_writer import _set, _P_ORDER
        _set(_ppr(result),'keepNext',order=_P_ORDER,val='1')
    for change in plan.get('baseline_spacing_changes',[]):
        if change['paragraph_id']==identifier:
            spacing=result.find(W+'pPr/'+W+'spacing')
            if spacing is None or spacing.get(W+change['attribute'])!=str(change['old_twips']):
                model._fail('source_baseline_spacing_delta')
            spacing.set(W+change['attribute'],str(change['new_twips']))
    return result


def verify_terminal_order(root, mapping, owners, plan):
    """Inventory actual XML independently of the transform's reconstruction."""
    if not plan['source_footers']:return
    body=root.find(W+'body');sections=list(root.iter(W+'sectPr'))
    owned={r['paragraph_id']:r for r in mapping['paragraphs']}
    ordered=list(root.iter(W+'p'));position={node:i for i,node in enumerate(ordered)}
    previous_end=-1;seen=set()
    for section,item in zip(sections,plan['source_footers']):
        end=section if section.getparent() is body else section.getparent().getparent()
        end_index=body.index(end);footer_ids=item['paragraph_ids'];nodes={}
        for identifier in owners[item['source_page_number']]:
            row=owned[identifier]
            if row['part_uri']!='word/document.xml':model._fail('source_terminal_footer_ownership')
            locations=[p['location'] for p in row.get('parts',[])] or [row['location']]
            nodes[identifier]=[]
            for location in locations:
                hits=root.xpath(location,namespaces={'w':W[1:-1]})
                if len(hits)!=1 or hits[0] in seen:model._fail('source_terminal_footer_ownership')
                node=hits[0];seen.add(node);top=node
                while top.getparent() is not body:
                    top=top.getparent()
                    if top is None:model._fail('source_terminal_footer_ownership')
                if not previous_end<body.index(top)<end_index:model._fail('source_terminal_section_ownership')
                nodes[identifier].append(node)
        footer_positions=[position[n] for i in footer_ids for n in nodes[i]]
        body_positions=[position[n] for i,children in nodes.items() if i not in footer_ids for n in children]
        if (any(len(nodes[i])!=1 or nodes[i][0].getparent() is not body for i in footer_ids)
                or footer_positions!=sorted(set(footer_positions))
                or body_positions and min(footer_positions)<=max(body_positions)):
            model._fail('source_terminal_footer_order')
        previous_end=end_index
