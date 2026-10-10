"""Semantic section ownership shared by strict DOCX import/adoption guards."""
from lxml import etree
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

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
