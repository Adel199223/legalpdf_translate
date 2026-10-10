"""Semantic section ownership shared by strict DOCX import/adoption guards."""
from lxml import etree
import posixpath
import re
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

def _path(node, root):
    result=[]
    while node is not root:
        parent=node.getparent()
        if parent is None:
            raise ValueError("section_owner_missing")
        result.append(parent.index(node));node=parent
    return list(reversed(result))

def word_section_signature(members):
    """Semantic section topology for a package already validated by its caller.

    Word may renumber relationships and revision IDs. Source footer ownership,
    section boundaries, titlePg and every other section property stay exact.
    """
    raw = members.get("word/_rels/document.xml.rels")
    ids = {} if raw is None else {n.get("Id"): (n.get("Type"), n.get("Target"), n.get("TargetMode"))
        for n in etree.fromstring(raw)}
    def semantic(node):
        attrs = tuple(sorted((k,v) for k,v in node.attrib.items()
            if not etree.QName(k).localname.startswith("rsid") and etree.QName(k).localname != "id"))
        refs = []
        for k,v in node.attrib.items():
            if etree.QName(k).localname == "id":
                if v not in ids:
                    raise ValueError("section_reference_missing")
                refs.append(("relationship_target",ids[v]))
        return node.tag, attrs+tuple(refs), tuple(semantic(child) for child in node)
    root=etree.fromstring(members["word/document.xml"])
    def owner(node):
        parent = node.getparent()
        if parent is not None and parent.tag == W + "pPr":
            paragraph = parent.getparent()
            if paragraph is None or paragraph.tag != W + "p":
                raise ValueError("section_owner_missing")
            return "paragraph", tuple(_path(paragraph, root))
        return "terminal", tuple(_path(node, root))
    return tuple((owner(node),semantic(node)) for node in root.iter(W+"sectPr"))


def _empty_footer(raw):
    """Only a generated blank paragraph story can be continuation furniture."""
    root = etree.fromstring(raw)
    allowed = {W + n for n in ('ftr', 'p', 'pPr', 'r', 'rPr', 't', 'spacing',
        'jc', 'bidi', 'rFonts', 'sz', 'szCs', 'lang', 'rtl', 'pStyle')}
    return (root.tag == W+'ftr' and len(root) == 1 and root[0].tag == W+'p'
        and all(n.tag in allowed and not (n.text or '').strip() for n in root.iter()))


def verified_word_story_projection(before, after):
    """Map Word-renumbered stories by their section/reference owners, never text.

    This proves topology only. Callers must still compare every text/control
    inventory (or explicitly review imported wording) using this projection.
    """
    def describe(members):
        root = etree.fromstring(members['word/document.xml'])
        rels = {}
        for n in etree.fromstring(members.get('word/_rels/document.xml.rels', b'<Relationships/>')):
            key = n.get('Id')
            if key in rels:
                raise ValueError('section_relationship_duplicate')
            rels[key] = n
        stories = {p for p in members if re.fullmatch(r'word/(?:footer|header)\d+\.xml', p)}
        empty = {p for p in stories if p.startswith('word/footer') and _empty_footer(members[p])}
        inherited = {}; slots = {}; referenced = set(); sections = []
        def semantic(n):
            attrs = tuple(sorted((k,v) for k,v in n.attrib.items()
                if not etree.QName(k).localname.startswith('rsid')))
            if n.tag == W+'titlePg':
                if n.get(W+'val', 'true') not in {'true','1','on'}:
                    raise ValueError('section_first_page_value_invalid')
                attrs = ()
            return n.tag, attrs, tuple(semantic(c) for c in n)
        for index, section in enumerate(root.iter(W+'sectPr')):
            parent=section.getparent()
            owner=('paragraph', tuple(_path(parent.getparent(), root))) if parent.tag==W+'pPr' else ('terminal', tuple(_path(section, root)))
            properties=[]; seen=set()
            for child in section:
                if child.tag in {W+'footerReference', W+'headerReference'}:
                    kind = 'footer' if child.tag==W+'footerReference' else 'header'
                    slot=child.get(W+'type'); key=(kind,slot)
                    if slot not in {'first','default','even'} or key in seen or set(child.attrib)!={W+'type',R+'id'}:
                        raise ValueError('section_slot_invalid')
                    seen.add(key); rel=rels.get(child.get(R+'id'))
                    expected_type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/'+kind
                    if rel is None or rel.get('TargetMode') is not None or rel.get('Type')!=expected_type:
                        raise ValueError('section_reference_invalid')
                    target=rel.get('Target','')
                    if not target or '\\' in target or target.startswith('/') or '..' in target.split('/'):
                        raise ValueError('section_target_invalid')
                    target=posixpath.normpath('word/'+target)
                    if target not in stories or not re.fullmatch('word/'+kind+r'\d+\.xml',target):
                        raise ValueError('section_target_missing')
                    inherited[key]=target;referenced.add(target)
                elif child.tag==W+'titlePg' and child.get(W+'val') in {'false','0','off'}:
                    if set(child.attrib)!={W+'val'} or len(child):
                        raise ValueError('section_first_page_value_invalid')
                    continue  # Explicit false has the same meaning as no titlePg.
                elif child.tag==W+'type' and dict(child.attrib)=={W+'val':'nextPage'}:
                    continue  # Word omits the default next-page section type.
                else:
                    properties.append(semantic(child))
            sections.append((owner, tuple(properties)))
            for kind in ('header','footer'):
                for slot in ('first','default','even'):
                    slots[(index,kind,slot)]=inherited.get((kind,slot))
        if any(p not in referenced and p not in empty for p in stories):
            raise ValueError('section_story_orphan')
        return tuple(sections), slots, empty, stories
    a,slots_a,empty_a,stories_a=describe(before)
    b,slots_b,empty_b,stories_b=describe(after)
    if a!=b:
        raise ValueError('section_topology_changed')
    mapping={}; inverse={}
    for key, old in slots_a.items():
        new=slots_b[key]
        # Only footer continuation slots may split a proven blank story.
        if key[1]=='footer' and key[2] in {'default','even'} and (old is None or old in empty_a) and (new is None or new in empty_b):
            continue
        if old is None or new is None:
            if old!=new:raise ValueError('section_slot_changed')
            continue
        if old in mapping and mapping[old]!=new or new in inverse and inverse[new]!=old:
            raise ValueError('section_story_ownership_changed')
        mapping[old]=new;inverse[new]=old
    if any(p not in mapping and p not in empty_a for p in stories_a) or any(p not in inverse and p not in empty_b for p in stories_b):
        raise ValueError('section_story_unmapped')
    return {'part_map':mapping,'parent_empty_parts':sorted(empty_a),'edited_empty_parts':sorted(empty_b)}


def project_story_inventory(inventory, projection, *, edited=False):
    """Canonical logical story names, excluding proved blank continuation parts."""
    empty=set(projection['edited_empty_parts' if edited else 'parent_empty_parts'])
    inverse={v:k for k,v in projection['part_map'].items()} if edited else {}
    return tuple(sorted((inverse.get(name,name), rows) for name,rows in inventory if name not in empty))
