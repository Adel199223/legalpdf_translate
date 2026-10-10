"""Word-added separator parts survive import; substantive notes stay unsupported."""
from io import BytesIO
from zipfile import ZipFile
from lxml import etree
import pytest
from legalpdf_translate.saved_docx_layout import inspect_docx, SavedDocxLayoutError, W
from tests.test_saved_docx_layout_service import docx_bytes

REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT = '{http://schemas.openxmlformats.org/package/2006/content-types}'
BASE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'


def with_system_notes(raw, mutation=None):
    with ZipFile(BytesIO(raw)) as archive:
        parts = {n: archive.read(n) for n in archive.namelist()}
    relations = etree.fromstring(parts['word/_rels/document.xml.rels'])
    types = etree.fromstring(parts['[Content_Types].xml'])
    for plural, singular in [('footnotes','footnote'),('endnotes','endnote')]:
        root = etree.Element(W+plural, nsmap={'w':W[1:-1]})
        for identifier, kind in [('-1','separator'),('0','continuationSeparator')]:
            note = etree.SubElement(root,W+singular,{W+'type':kind,W+'id':identifier})
            paragraph = etree.SubElement(note,W+'p',{W+'rsidR':'00ABCDEF'})
            properties = etree.SubElement(paragraph,W+'pPr')
            etree.SubElement(properties,W+'spacing',{W+'after':'0',W+'line':'240',W+'lineRule':'auto'})
            etree.SubElement(etree.SubElement(paragraph,W+'r'),W+kind)
        parts['word/'+plural+'.xml'] = etree.tostring(root)
        etree.SubElement(relations,REL+'Relationship',Id='rIdSystem'+plural,Type=BASE+plural,Target=plural+'.xml')
        etree.SubElement(types,CT+'Override',PartName='/word/'+plural+'.xml',ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.'+plural+'+xml')
    if mutation:
        root = etree.fromstring(parts['word/footnotes.xml'])
        binding = next(n for n in relations if n.get('Type') == BASE+'footnotes')
        override = next(n for n in types if n.get('PartName') == '/word/footnotes.xml')
        if mutation == 'real_note': root[0].set(W+'id','1');root[0].attrib.pop(W+'type')
        elif mutation == 'duplicate': root[1].set(W+'id','-1')
        elif mutation == 'text': etree.SubElement(root[0][0][-1],W+'t').text='Meaningful note'
        elif mutation == 'unknown': etree.SubElement(root[0][0],W+'bookmarkStart')
        elif mutation == 'attribute': root[0].set(W+'unknown','1')
        elif mutation == 'binding_child': etree.SubElement(binding,REL+'Unknown')
        elif mutation == 'binding_text': binding.text='unknown'
        elif mutation == 'override_child': etree.SubElement(override,CT+'Unknown')
        elif mutation == 'override_text': override.text='unknown'
        elif mutation == 'relations_root': relations.tag='{urn:unsupported}Relationships'
        elif mutation == 'types_root': types.tag='{urn:unsupported}Types'
        elif mutation == 'missing_binding': relations.remove(binding)
        elif mutation == 'duplicate_binding': relations.append(etree.fromstring(etree.tostring(binding))) ; relations[-1].set('Id','duplicate')
        elif mutation == 'wrong_binding': binding.set('Type',BASE+'styles')
        elif mutation == 'external': binding.set('TargetMode','External')
        elif mutation == 'missing_type': types.remove(override)
        elif mutation == 'duplicate_type': types.append(etree.fromstring(etree.tostring(override)))
        elif mutation == 'wrong_type': override.set('ContentType','application/xml')
        elif mutation == 'orphan': parts.pop('word/footnotes.xml')
        elif mutation == 'reference':
            doc=etree.fromstring(parts['word/document.xml']);etree.SubElement(doc.find('.//'+W+'r'),W+'footnoteReference',{W+'id':'1'});parts['word/document.xml']=etree.tostring(doc)
        elif mutation == 'note_rels': parts['word/_rels/footnotes.xml.rels']=b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
        if mutation != 'orphan': parts['word/footnotes.xml']=etree.tostring(root)
    parts['word/_rels/document.xml.rels']=etree.tostring(relations)
    parts['[Content_Types].xml']=etree.tostring(types)
    out=BytesIO()
    with ZipFile(out,'w') as archive:
        for name,data in parts.items(): archive.writestr(name,data)
    return out.getvalue()


@pytest.mark.parametrize('language',['EN','FR','AR'])
def test_system_notes_are_preserved_and_never_enter_paragraph_inventory(language):
    original=docx_bytes(language);saved=with_system_notes(original)
    a,b=inspect_docx(original,language),inspect_docx(saved,language)
    assert a['paragraphs']==b['paragraphs']
    assert {'word/footnotes.xml','word/endnotes.xml'} <= b['package_sha256'].keys()
    assert saved==with_system_notes(original)


@pytest.mark.parametrize('mutation',['real_note','duplicate','text','unknown','attribute','missing_binding','duplicate_binding','wrong_binding','external','missing_type','duplicate_type','wrong_type','orphan','reference','note_rels','binding_child','binding_text','override_child','override_text','relations_root','types_root'])
def test_notes_and_bad_bindings_remain_fatal(mutation):
    with pytest.raises(SavedDocxLayoutError): inspect_docx(with_system_notes(docx_bytes(),mutation),'EN')


@pytest.mark.parametrize('language',['EN','FR','AR'])
def test_real_import_api_build_keeps_system_note_bytes(tmp_path,monkeypatch,language):
    from fastapi.testclient import TestClient
    from tests.test_shadow_web_saved_docx_layout_api import actual_app,fictional_files,import_file,value,reviewed_decisions,HEADERS,api
    source,original=fictional_files(language);saved=with_system_notes(original)
    with TestClient(actual_app(tmp_path,monkeypatch)) as client:
        view=value(import_file(client,language,files=(source,saved)))
        base=api.PREFIX+'/reviews/'+view['review_id']
        updated=value(client.post(base+'/decisions',headers=HEADERS,json={'expected_generation':view['generation'],'save_nonce':'b'*32,'decisions':reviewed_decisions(view)}))
        built=value(client.post(base+'/builds',headers=HEADERS,json={'expected_generation':updated['generation'],'operation_nonce':'c'*32,'review_confirmed':True}))
        delivered=client.get(base+'/artifacts/'+built['artifacts'][0]['artifact_id']+'/docx',headers=HEADERS)
        assert delivered.status_code==200
        with ZipFile(BytesIO(saved)) as before,ZipFile(BytesIO(delivered.content)) as after:
            for name in ('word/footnotes.xml','word/endnotes.xml'):assert before.read(name)==after.read(name)


@pytest.mark.parametrize('mutation',['real_note','reference'])
def test_rejected_word_resolver_returns_fixed_safe_route_error(tmp_path,monkeypatch,mutation):
    from tests.test_ordinary_layout_service import make_case
    from tests.test_shadow_web_ordinary_layout_api import client_for,url
    case=make_case(tmp_path,monkeypatch)
    saved=with_system_notes(docx_bytes(),mutation)
    def resolver(_job):
        inspect_docx(saved,'EN')
        return case.job
    case.manager.job_resolver=resolver
    with client_for(case) as client:
        response=client.post(url(case,'/layout/prepare'),json={'prepare_nonce':'d'*32})
        assert response.status_code==422
        assert response.json()['diagnostics']['error']=='ordinary_layout_saved_word_unsupported'
        assert str(tmp_path) not in response.text and 'Meaningful note' not in response.text


def test_fixed_saved_word_message_is_safe_and_specific():
    from tests.test_ordinary_layout_browser_state import probe
    result=probe("console.log(JSON.stringify({message:ordinaryUi.ordinaryLayoutMessage('ordinary_layout_saved_word_unsupported')}));")
    assert result['message']=='The saved Word file contains unsupported content. Original files are preserved.'



def test_ordinary_prepare_rebases_word_serialization_without_changing_bytes(tmp_path,monkeypatch):
    from dataclasses import replace
    from tests.test_ordinary_layout_service import make_case
    from tests.test_shadow_web_ordinary_layout_api import client_for,url
    from legalpdf_translate.ordinary_layout_contracts import digest
    case=make_case(tmp_path,monkeypatch)
    saved=with_system_notes(case.job.reviewed_docx)
    case.state['job']=replace(case.job,reviewed_docx=saved,mapping_docx_sha256=digest(saved))
    with client_for(case) as client:
        response=client.post(url(case,'/layout/prepare'),json={'prepare_nonce':'e'*32})
        assert response.status_code==200,response.text
        view=response.json()['normalized_payload']['ordinary_layout']
        assert view['baseline_id']!=case.view['baseline_id']
        review=case.manager.service.saved.root/'reviews'/view['review']['review_id']
        assert (review/'original.docx').read_bytes()==saved



def test_resolver_absence_and_owner_mismatch_keep_distinct_statuses(tmp_path,monkeypatch):
    from dataclasses import replace
    from tests.test_ordinary_layout_service import make_case
    from tests.test_shadow_web_ordinary_layout_api import client_for,url
    case=make_case(tmp_path,monkeypatch)
    def absent(_):raise FileNotFoundError('private path must not leak')
    with client_for(case) as client:
        case.manager.job_resolver=absent
        response=client.post(url(case,'/layout/prepare'),json={'prepare_nonce':'f'*32})
        assert response.status_code==404
        assert response.json()['diagnostics']['error']=='ordinary_layout_job_unavailable'
        assert 'private path' not in response.text
        case.manager.job_resolver=lambda _:replace(case.job,workspace_id='wrong-owner')
        response=client.post(url(case,'/layout/prepare'),json={'prepare_nonce':'f'*32})
        assert response.status_code==409
        assert response.json()['diagnostics']['error']=='ordinary_layout_job_owner_mismatch'
