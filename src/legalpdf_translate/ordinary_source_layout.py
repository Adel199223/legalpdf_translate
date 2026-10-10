"""Closed source-evidence transformations layered over immutable V6 candidates."""
from copy import deepcopy
from io import BytesIO
import re
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo
from lxml import etree
from . import saved_docx_layout as model

VERSION = "saved_docx_layout_writer_source_layout_v7"
W = model.W
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
CT = "{http://schemas.openxmlformats.org/package/2006/content-types}"
NS = {"w": W[1:-1]}

def _xml(raw):
    return model._xml(raw)

def _bytes(root):
    return etree.tostring(root,xml_declaration=True,encoding="UTF-8",standalone=True)

def _folio_ltr_span(paragraph, *, legacy_wrapper=False):
    """One closed Arabic folio expression; no text or font substitutions."""
    text=''.join(n.text or '' for n in paragraph.iter(W+'t'))
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

def transform(base, snapshot, pages, decisions, context, evidence, folio_direction_mode='numeric_run_ltr_v2'):
    """No side effects; only explicitly qualified decorative/footer rows may change."""
    from .saved_docx_layout_writer import SavedDocxLayoutArtifact
    from .ordinary_layout_contracts import proposal_source_evidence, PROPOSAL_VERSION_V3
    if folio_direction_mode not in {'legacy_none','direction_wrapper_v1','numeric_run_ltr_v2'}:model._fail('source_folio_direction_version')
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
    if folio_direction_mode=='numeric_run_ltr_v2':plan['folio_direction_version']=folio_direction_mode
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
                        span=_folio_ltr_span(node,legacy_wrapper=folio_direction_mode=='direction_wrapper_v1')
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
    members["word/document.xml"]=_bytes(root)
    raw=_pack(members);mapping=deepcopy(base.source_map)
    mapping.update(writer_version=VERSION,docx_sha256=model._sha(raw),base_source_map=deepcopy(base.source_map),source_layout_plan=plan,source_layout_plan_sha256=model._sha(model._canonical(plan)),exact_text_preserved=not bool(plan["decorative_rules"]),exact_meaningful_text_preserved=True)
    for row in mapping["paragraphs"]:
        identifier=row["paragraph_id"]
        if "part_uri" in mapped[identifier]:row.update({k:mapped[identifier][k] for k in ("part_uri","location")})
        else:
            row.update(part_uri="word/document.xml",location=root.getroottree().getpath(nodes[identifier]))
            for part,node in zip(row.get("parts",[]),part_nodes[identifier]):part["location"]=root.getroottree().getpath(node)
    mapping["structural_paragraphs"]=[root.getroottree().getpath(n) for n in structural if n.getroottree().getroot() is root]
    if plan['source_footers']:
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


def verify(actual, base, snapshot, pages, decisions, context, evidence):
    """Reconstruct the closed recipe, then independently inventory actual owned stories."""
    saved_plan=actual.source_map.get('source_layout_plan',{})
    mode=saved_plan.get('folio_direction_version','direction_wrapper_v1' if 'folio_ltr_spans' in saved_plan else 'legacy_none')
    expected=transform(base,snapshot,pages,decisions,context,evidence,mode)
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
    if plan['source_footers']:
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
                if part!=(item['part_uri'] if reference.get(W+'type')=='first' else plan['empty_continuation_footer_part']):model._fail('source_section_footer_references')
        empty=_xml(actual_parts[plan['empty_continuation_footer_part']])
        if len(empty)!=1 or empty[0].tag!=W+'p' or list(empty[0].findall(W+'r')) or list(empty.iter(W+'t')) or list(empty.iter(W+'instrText')):model._fail('source_section_continuation_footer')
        from .ordinary_presentation import suppress_footer
        expected_suppressed,_=suppress_footer(base_parts,base.docx_bytes,snapshot['target_lang'],True)
        for name in plan.get('suppressed_generated_footer_parts',[]):
            if actual_parts[name]!=expected_suppressed[name]:model._fail('source_section_generated_footer_delta')
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
            if owned['part_uri']!='word/document.xml':
                for br in list(baseline.iter(W+'br')):
                    if br.get(W+'type')!='page':model._fail('source_footer_control')
                    br.getparent().remove(br)
                span=next((item for item in plan.get('folio_ltr_spans',[]) if item['paragraph_id']==identifier),None)
                if span is not None:
                    expected_span=_folio_ltr_span(baseline,legacy_wrapper=mode=='direction_wrapper_v1')
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
            if model._c14n(node)!=model._c14n(baseline):model._fail('source_layout_run_semantics_changed')
            original="".join(t["text"] for t in rows[identifier]["tokens"] if t["kind"]=="t")
            if visible!=original:model._fail("source_layout_meaningful_text_changed")
    if seen!=set(rows):model._fail("source_layout_coverage_changed")


def owned_story_count_descriptor(source_map):
    """Call only after V7 candidate verification; no client-supplied map admission."""
    if source_map.get('writer_version')!=VERSION:raise ValueError('owned_story_count_version')
    rows=[]
    for row in source_map['paragraphs']:
        if row.get('parts'):
            rows.extend({'paragraph_id':part['part_id'],'part_uri':row['part_uri'],'location':part['location']} for part in row['parts'])
        else:rows.append({k:row[k] for k in ('paragraph_id','part_uri','location')})
    return {'version':'ordinary_owned_story_count_v1','docx_sha256':source_map['docx_sha256'],'paragraphs':rows}
