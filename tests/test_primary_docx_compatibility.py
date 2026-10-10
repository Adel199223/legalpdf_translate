from zipfile import ZipFile, ZipInfo
import xml.etree.ElementTree as ET

import pytest
from docx.oxml.ns import qn

from legalpdf_translate.docx_writer import _ensure_primary_compatibility_mode15


@pytest.mark.parametrize('values', [[], ['14'], ['15'], ['14', '15']])
def test_primary_mode15_preserves_namespace_package_and_other_settings(tmp_path, values):
    mode = ''.join(f'<w:compatSetting w:name="compatibilityMode" w:val="{v}"/>' for v in values)
    keep = '<w:compatSetting w:name="otherSetting" w:val="1"/>'
    xml = ('<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
           'xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml" '
           'xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" mc:Ignorable="w14">'
           '<w:zoom w:percent="100"/><w:compat>'+mode+keep+'</w:compat></w:settings>')
    path = tmp_path/'primary.docx'
    info = ZipInfo('word/settings.xml', (2020,1,2,3,4,6));info.external_attr=0o600<<16;info.comment=b'part'
    with ZipFile(path,'w') as archive:
        archive.comment=b'archive';archive.writestr(info,xml);archive.writestr('word/document.xml',b'<unchanged/>')
    _ensure_primary_compatibility_mode15(path)
    with ZipFile(path) as archive:
        data=archive.read('word/settings.xml');root=ET.fromstring(data)
        modes=[n for n in root.iter(qn('w:compatSetting')) if n.get(qn('w:name'))=='compatibilityMode']
        assert len(modes)==1 and modes[0].get(qn('w:val'))=='15'
        assert keep.encode() in data and b'mc:Ignorable="w14"' in data
        assert archive.read('word/document.xml')==b'<unchanged/>' and archive.comment==b'archive'
        actual=archive.getinfo('word/settings.xml')
        assert (actual.date_time,actual.external_attr,actual.comment)==(info.date_time,info.external_attr,info.comment)
    before=path.read_bytes();_ensure_primary_compatibility_mode15(path);assert path.read_bytes()==before


def test_primary_mode15_inserts_compat_when_missing(tmp_path):
    path=tmp_path/'primary.docx'
    with ZipFile(path,'w') as archive:
        archive.writestr('word/settings.xml','<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:zoom w:percent="100"/></w:settings>')
    _ensure_primary_compatibility_mode15(path)
    with ZipFile(path) as archive:
        assert b'w:val="15"' in archive.read('word/settings.xml')


def test_mode_placement_is_canonical_across_missing_old_and_current_modes(tmp_path):
    other='<w:compatSetting w:name="otherSetting" w:val="1"/>'
    base='<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:compat>{}</w:compat></w:settings>'
    outputs=[]
    for index, children in enumerate((other,
        '<w:compatSetting w:name="compatibilityMode" w:val="14"/>'+other,
        other+'<w:compatSetting w:name="compatibilityMode" w:val="15"/>')):
        path=tmp_path/f'position-{index}.docx'
        with ZipFile(path,'w') as archive:archive.writestr('word/settings.xml',base.format(children))
        _ensure_primary_compatibility_mode15(path)
        with ZipFile(path) as archive:outputs.append(archive.read('word/settings.xml'))
        before=path.read_bytes();_ensure_primary_compatibility_mode15(path);assert path.read_bytes()==before
    assert outputs[0]==outputs[1]==outputs[2]
    assert outputs[0].index(other.encode()) < outputs[0].index(b'w:name="compatibilityMode"')
