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
