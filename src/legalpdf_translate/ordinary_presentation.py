"""Trusted ordinary-only presentation derivation; never rewrites decisions/text."""
from copy import deepcopy
import re
from lxml import etree
from . import saved_docx_layout as model

W = model.W
VERSION = 'saved_docx_layout_writer_ordinary_presentation_v6'

def derive(snapshot, pages, decisions, context):
    if type(context) is not dict or set(context) != {'selected_pages', 'page_groups'}:
        model._fail('invalid_ordinary_writer_context')
    selected = context['selected_pages']
    groups = context['page_groups']
    if (type(selected) is not list or not selected or any(type(p) is not int or p < 1 for p in selected)
            or sorted(set(selected)) != selected or type(groups) is not list):
        model._fail('invalid_ordinary_writer_context')
    owners = {}
    for item in groups:
        if type(item) is not list or len(item) != 2 or item[0] not in selected or type(item[1]) is not list:
            model._fail('invalid_ordinary_writer_context')
        for identifier in item[1]:
            if type(identifier) is not str or identifier in owners:
                model._fail('invalid_ordinary_writer_context')
            owners[identifier] = item[0]
    rows = {p['id']: p for p in snapshot['paragraphs']}
    if set(owners) - set(rows):
        model._fail('invalid_ordinary_writer_context')
    choices = {p['paragraph_id']: p for p in decisions['paragraphs']}
    frames = {p['page_number']: p for p in pages}
    partitioned = {p['paragraph_id'] for p in decisions.get('paragraph_partitions', [])}
    units = []
    for band in decisions['bands']:
        if band['kind'] == 'flow':
            units.extend({'kind': 'flow', 'groups': [deepcopy(g)]} for g in band['groups'])
        else:
            units.append(deepcopy(band))
    def ids(unit):
        gs = unit['groups'] if unit['kind'] == 'flow' else [g for c in unit['cells'] for g in c['groups']]
        return [i for g in gs for i in g['paragraph_ids']]
    def envelope(unit):
        gs = unit['groups'] if unit['kind'] == 'flow' else [g for c in unit['cells'] for g in c['groups']]
        if any(g['panel'] for g in gs): return None
        boxes = []; page = None
        for identifier in ids(unit):
            row, choice = rows[identifier], choices[identifier]
            if (identifier in partitioned or choice['role'] not in {'institution','reference','recipient'}
                    or row.get('has_page_break') or row.get('has_field') or row.get('numbering')
                    or not row['tokens'] or any(t['kind'] != 't' for t in row['tokens'])
                    or len(choice['regions']) != 1): return None
            region = choice['regions'][0]; source = owners.get(identifier)
            if source is None or region['page_number'] != source or (page is not None and page != source): return None
            page = source; box = region['bbox_px']; frame = frames[source]
            if box[0] == 0 and box[1] == 0 and box[2] == frame['width_px'] and box[3] == frame['height_px']: return None
            boxes.append(box)
        return (page, min(b[1] for b in boxes), max(b[3] for b in boxes)) if boxes else None
    original = [i for u in units for i in ids(u)]; swaps = []
    # Adjacent inversion only; barriers and overlapping boxes are never crossed.
    envelopes = {id(unit): envelope(unit) for unit in units}
    for end in range(len(units)):
        changed = False
        for index in range(len(units)-1):
            left,right = envelopes[id(units[index])],envelopes[id(units[index+1])]
            if left and right and left[0] == right[0] and right[2] < left[1]:
                swaps.append({'left': ids(units[index]), 'right': ids(units[index+1]), 'page':left[0]})
                units[index],units[index+1] = units[index+1],units[index]
                changed = True
        if not changed: break
    rendered = [i for u in units for i in ids(u)]
    if len(original) != len(set(original)) or sorted(original) != sorted(rendered): model._fail('ordinary_presentation_coverage')
    presentation = deepcopy(decisions)
    if swaps: presentation['bands'] = units
    folios = set()
    for identifier,choice in choices.items():
        row = rows[identifier]; source = owners.get(identifier)
        if (choice['role'] != 'source_folio' or source is None or len(choice['regions']) != 1
                or any(t['kind'] != 't' for t in (row['tokens'][:-1] if row['tokens'] and row['tokens'][-1]['kind']=='page_break' else row['tokens'])) or identifier in partitioned): continue
        region = choice['regions'][0]; frame = frames.get(source)
        if not frame or region['page_number'] != source: continue
        box = region['bbox_px']; height = frame['height_px']
        text = row['text'].translate({ord(c):None for c in '\u200e\u200f\u2066\u2067\u2069'}).strip()
        if (box[1] >= .85*height and box[3]-box[1] <= .12*height
                and re.fullmatch(r'(?:(?:page|página|pagina|pág\.?|pag\.?|p\.?|صفحة|الصفحة)\s*)?[0-9\u0660-\u0669\u06f0-\u06f9]{1,4}(?:\s*(?:/|of|de|sur|من)\s*[0-9\u0660-\u0669\u06f0-\u06f9]{1,4})?',text,re.I)):
            folios.add(source)
    plan = {'context':deepcopy(context),'original_paragraph_ids':original,'rendered_paragraph_ids':rendered,
            'swaps':swaps,'suppress_generated_page':folios == set(selected)}
    return presentation, plan

def _v6_page_signature(nsmap, lang):
    """Frozen v6 app-PAGE signature; future raw writer changes cannot redefine it."""
    p=etree.Element(W+'p',nsmap=nsmap)
    def add(parent,tag,attrs=None,text=None):
        node=etree.SubElement(parent,W+tag,attrs or {});node.text=text;return node
    pp=add(p,'pPr');add(pp,'pStyle',{W+'val':'LegalPDFFooterText'});add(pp,'jc',{W+'val':'center'})
    run=add(p,'r');rp=add(run,'rPr');font,size=('Arial','22') if lang=='AR' else ('Times New Roman','21')
    add(rp,'rFonts',{W+k:font for k in ('ascii','hAnsi','eastAsia','cs')})
    add(rp,'color',{W+'val':'000000'});add(rp,'sz',{W+'val':size});add(rp,'szCs',{W+'val':size})
    add(run,'fldChar',{W+'fldCharType':'begin'});add(run,'instrText',{'{http://www.w3.org/XML/1998/namespace}space':'preserve'},' PAGE ')
    add(run,'fldChar',{W+'fldCharType':'separate'});add(run,'t',text='1');add(run,'fldChar',{W+'fldCharType':'end'})
    return p


def suppress_footer(members, raw, lang, enabled):
    result = dict(members); changed = []
    if not enabled: return result,changed
    rels = model._xml(members['word/_rels/document.xml.rels'])
    targets = {r.get('Id'):r.get('Target') for r in rels}
    root = model._xml(members['word/document.xml'])
    for ref in root.iter(W+'footerReference'):
        target=targets.get(ref.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'),'')
        name = 'word/'+target
        if name not in members or name in changed: continue
        footer=model._xml(members[name]);children=list(footer)
        if len(children)!=1 or children[0].tag != W+'p': continue
        if model._c14n(children[0]) != model._c14n(_v6_page_signature(children[0].nsmap,lang)): continue
        paragraph=children[0]
        for child in list(paragraph):
            if child.tag != W+'pPr':paragraph.remove(child)
        result[name]=etree.tostring(footer,xml_declaration=True,encoding='UTF-8',standalone=True)
        changed.append(name)
    return result,changed

def independent_check(snapshot,pages,decisions,context,actual_ids,original_members,output_members):
    """Check actual permutations and package deltas without the derivation helpers."""
    rows={r['id']:r for r in snapshot['paragraphs']}; choices={c['paragraph_id']:c for c in decisions['paragraphs']}
    owners={i:p for p,ids in context['page_groups'] for i in ids};frames={p['page_number']:p for p in pages}
    units=[]
    for band in decisions['bands']:
        if band['kind']=='flow': units.extend([[g] for g in band['groups']])
        else: units.append([g for cell in band['cells'] for g in cell['groups']])
    sequences=[[i for g in gs for i in g['paragraph_ids']] for gs in units]
    raw_ids=[i for seq in sequences for i in seq]
    if len(actual_ids)!=len(raw_ids) or set(actual_ids)!=set(raw_ids) or len(set(actual_ids))!=len(actual_ids):model._fail('output_presentation_coverage')
    positions={i:n for n,i in enumerate(actual_ids)}
    for seq in sequences:
        start=positions[seq[0]]
        if actual_ids[start:start+len(seq)]!=seq:model._fail('output_presentation_unit_order')
    cuts={p['paragraph_id'] for p in decisions.get('paragraph_partitions',[])}
    def safe_unit(index):
        gs=units[index];seq=sequences[index];source={owners.get(i) for i in seq}
        if len(source)!=1 or None in source or any(g['panel'] for g in gs):return None
        page=next(iter(source));ys=[]
        for i in seq:
            c=choices[i];row=rows[i]
            if (c['role'] not in {'institution','reference','recipient'} or i in cuts
                    or row.get('has_page_break') or row.get('has_field') or row.get('numbering')
                    or not row['tokens'] or any(t['kind']!='t' for t in row['tokens']) or len(c['regions'])!=1):return None
            r=c['regions'][0];b=r['bbox_px'];f=frames[page]
            if r['page_number']!=page or b==[0,0,f['width_px'],f['height_px']]:return None
            ys.extend([b[1],b[3]])
        return page,min(ys),max(ys)
    # Every raw pair crossed by actual DOM must have a strict same-page inversion.
    for i,seq in enumerate(sequences) if actual_ids != raw_ids else []:
        for j in range(i+1,len(sequences)):
            if positions[seq[0]]>positions[sequences[j][0]]:
                a,b=safe_unit(i),safe_unit(j)
                if not a or not b or a[0]!=b[0] or b[2]>=a[1]:model._fail('output_presentation_unsafe_inversion')
    deltas=[n for n in original_members if n not in {'word/document.xml','word/settings.xml'} and original_members[n]!=output_members[n]]
    if not deltas:return
    covered=set()
    for identifier,c in choices.items():
        row=rows[identifier];page=owners.get(identifier)
        if c['role']!='source_folio' or page is None or len(c['regions'])!=1 or identifier in cuts or any(t['kind']!='t' for t in (row['tokens'][:-1] if row['tokens'] and row['tokens'][-1]['kind']=='page_break' else row['tokens'])):continue
        r=c['regions'][0];b=r['bbox_px'];f=frames[page];text=row['text'].translate({ord(ch):None for ch in '\u200e\u200f\u2066\u2067\u2069'}).strip()
        if (r['page_number']==page and b[1]>=.85*f['height_px'] and b[3]-b[1]<=.12*f['height_px']
                and re.fullmatch(r'(?:(?:page|página|pagina|pág\.?|pag\.?|p\.?|صفحة|الصفحة)\s*)?[0-9\u0660-\u0669\u06f0-\u06f9]{1,4}(?:\s*(?:/|of|de|sur|من)\s*[0-9\u0660-\u0669\u06f0-\u06f9]{1,4})?',text,re.I)):covered.add(page)
    if covered!=set(context['selected_pages']):model._fail('output_footer_source_coverage')
    rels=model._xml(original_members['word/_rels/document.xml.rels']);targets={r.get('Id'):'word/'+r.get('Target','') for r in rels}
    doc=model._xml(original_members['word/document.xml']);referenced={targets.get(r.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')) for r in doc.iter(W+'footerReference')}
    font,halfpoints = ('Arial','22') if snapshot['target_lang']=='AR' else ('Times New Roman','21')
    for name in deltas:
        if name not in referenced:model._fail('output_footer_unauthorized_part')
        before=model._xml(original_members[name]);after=model._xml(output_members[name]);children=list(before)
        if len(children)!=1 or children[0].tag!=W+'p':model._fail('output_footer_not_generated_page')
        p=children[0]
        if p.attrib or [n.tag for n in p]!=[W+'pPr',W+'r']:model._fail('output_footer_not_generated_page')
        ppr,run=list(p)
        if (ppr.attrib or [n.tag for n in ppr]!=[W+'pStyle',W+'jc'] or ppr[0].attrib!={W+'val':'LegalPDFFooterText'} or ppr[1].attrib!={W+'val':'center'} or run.attrib
                or [n.tag for n in run]!=[W+'rPr',W+'fldChar',W+'instrText',W+'fldChar',W+'t',W+'fldChar']):model._fail('output_footer_not_generated_page')
        rp=run[0]
        if (rp.attrib or [n.tag for n in rp]!=[W+'rFonts',W+'color',W+'sz',W+'szCs']
                or rp[0].attrib!={W+k:font for k in ('ascii','hAnsi','eastAsia','cs')}
                or rp[1].attrib!={W+'val':'000000'} or any(n.attrib!={W+'val':halfpoints} for n in rp[2:])):model._fail('output_footer_not_generated_page')
        if ([dict(run[n].attrib) for n in (1,3,5)]!=[{W+'fldCharType':v} for v in ('begin','separate','end')]
                or run[2].text!=' PAGE ' or run[4].text!='1'
                or run[2].attrib!={'{http://www.w3.org/XML/1998/namespace}space':'preserve'} or run[4].attrib
                or any(len(n) for n in run[1:])):model._fail('output_footer_not_generated_page')
        expected=deepcopy(before);expected[0].remove(expected[0][1])
        if model._c14n(expected)!=model._c14n(after):model._fail('output_footer_suppression_changed')
