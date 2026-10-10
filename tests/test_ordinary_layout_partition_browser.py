"""Fresh fake-SDK partition response through normal browser delivery and Save."""
from decimal import Decimal
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile
from lxml import etree
from fastapi.testclient import TestClient
from legalpdf_translate.ordinary_layout_contracts import PROPOSAL_VERSION_V2
import tests.test_ordinary_auto_layout_workflow as fixture


def test_fresh_partition_response_normal_download_save_and_cost(tmp_path, monkeypatch):
    original = fixture._proposal
    def proposal(review, page, columns=0):
        value = original(review, page, columns)
        row = value['paragraphs'][0]
        row.update(role='body', heading_level=0, heading_size_pt=None, bold=False)
        value['version'] = PROPOSAL_VERSION_V2
        value['bands'] = [{'kind':'flow','groups':[{'paragraph_ids':[r['paragraph_id'] for r in value['paragraphs']], 'panel':False}]}]
        value['paragraph_partitions'] = [{'paragraph_id':row['paragraph_id'],'split_before':['Second phrase.']}]
        return value
    monkeypatch.setattr(fixture, '_proposal', proposal)
    source = tmp_path/'fictional.pdf';fixture._source(source, ('digital',))
    output = tmp_path/'output';output.mkdir()
    app, manager, sdk, layout_requests = fixture._app(tmp_path, monkeypatch, ('First phrase. Second phrase.',), (1,))
    with TestClient(app) as client:
        job_id = fixture._start(client, source, output, 'EN', start=1, end=1, image_mode='off', ocr_mode='off')
        job = fixture._wait(manager, job_id)
        assert job['status'] == 'completed' and job['result']['automatic_layout']['status'] == 'automatic_unreviewed'
        assert len(sdk.requests) == len(layout_requests) == 1
        scope='?mode=shadow&workspace=fictional'
        shown=client.get(f'/api/translation/jobs/{job_id}'+scope).json()['normalized_payload']['job']
        layout=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        review=layout.service.state(job_id)['review']
        candidate=layout.service.saved.verified_unreviewed_candidate(review['review_id'],job['result']['automatic_layout']['candidate_id'])
        parts=[row['parts'] for row in candidate.source_map['paragraphs'] if 'parts' in row]
        assert len(parts)==1 and [(p['start'],p['end']) for p in parts[0]] == [(0,14),(14,28)]
        download=client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        assert download.status_code==200 and download.content==candidate.docx_bytes
        assert download.headers["content-disposition"] == 'attachment; filename="fictional_EN.docx"'
        assert candidate.docx_bytes == download.content
        assert sha256(download.content).hexdigest()==shown['delivery']['sha256']
        with ZipFile(BytesIO(download.content)) as package:
            document=etree.fromstring(package.read('word/document.xml'))
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        texts=[''.join(p.xpath('.//w:t/text()',namespaces=ns)) for p in document.xpath('.//w:body//w:p',namespaces=ns)]
        assert [t for t in texts if t]==['First phrase. ','Second phrase.']
        seed=shown['result']['save_seed']
        assert Decimal(str(seed['api_cost']))==Decimal(str(job['result']['save_seed']['api_cost']))+Decimal(shown['layout_costs']['cost_usd'])
        saved=client.post('/api/translation/save-row',json={'mode':'shadow','workspace_id':'fictional','job_id':job_id,
          'baseline_id':shown['ordinary_layout']['baseline_id'],'expected_delivery_generation':shown['delivery']['generation'],
          'form_values':{**seed,'rate_per_word':'.027','expected_total_mode':'auto'}})
        assert saved.status_code==200 and saved.json()['saved_result']['row_id']
        assert Decimal(str(saved.json()['normalized_payload']['api_cost']))==Decimal(str(seed['api_cost']))
