from lxml import etree
import pytest
from legalpdf_translate.ordinary_section_ownership import word_section_signature

W="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
def members(reference="r1", target="footer1.xml", extra="", rsid="1111"):
    return {"word/document.xml": f'<w:document xmlns:w="{W}" xmlns:r="{R}"><w:body><w:p/><w:sectPr w:rsidR="{rsid}"><w:footerReference w:type="first" r:id="{reference}"/><w:titlePg/>{extra}</w:sectPr></w:body></w:document>'.encode(), "word/_rels/document.xml.rels":f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="{reference}" Type="{R}/footer" Target="{target}"/></Relationships>'.encode()}

def test_section_semantics_survive_word_revision_and_relationship_renumbering():
    assert word_section_signature(members()) == word_section_signature(members(reference="r999", rsid="9999"))

@pytest.mark.parametrize("changed", [members(target="other.xml"),members(extra='<w:type w:val="continuous"/>')])
def test_section_or_footer_ownership_changes_are_distinct(changed):
    assert word_section_signature(members()) != word_section_signature(changed)


def test_paragraph_section_owner_ignores_anchor_formatting_not_position():
    base=members();root=etree.fromstring(base["word/document.xml"])
    body=root[0];section=body[-1];body.remove(section)
    props=etree.SubElement(body[0],"{"+W+"}pPr");props.append(section)
    base["word/document.xml"]=etree.tostring(root)
    formatted=dict(base);etree.SubElement(props,"{"+W+"}bidi");props.insert(0,props[-1])
    formatted["word/document.xml"]=etree.tostring(root)
    assert word_section_signature(base)==word_section_signature(formatted)
    other=etree.SubElement(body,"{"+W+"}p");otherprops=etree.SubElement(other,"{"+W+"}pPr");otherprops.append(section)
    moved=dict(base);moved["word/document.xml"]=etree.tostring(root)
    assert word_section_signature(base)!=word_section_signature(moved)
