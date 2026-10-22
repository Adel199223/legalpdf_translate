"""Fictional SDK workflow/recovery proves fresh clock bytes and honest review gates."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from fastapi.testclient import TestClient
from lxml import etree
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import workflow
from legalpdf_translate.ordinary_layout_service import _read
from tests.test_ordinary_auto_layout_recovery import offline
from tests import test_ordinary_auto_layout_workflow as flow
from tests.test_ordinary_body_columns_workflow import install_body_proposal, operation, protected
from tests.test_ordinary_layout_service import nonce
from tests.test_saved_docx_layout import changed_part


LINES='موعد خيالي [[09:30h]]\nجواب خيالي أول\nبيان خيالي ثان\nجواب خيالي ثان\nبيان خيالي أخير'


def install_fictional_split_assembly(monkeypatch):
    """Provide a former plain split-run input through the primary assembly seam."""
    original=workflow.assemble_docx
    def assemble(*args,**kwargs):
        path=original(*args,**kwargs)
        def split(root):
            for run in list(root.iter(model.W+'r')):
                nodes=run.findall(model.W+'t')
                if len(nodes)!=1 or ':' not in (nodes[0].text or ''): continue
                text=nodes[0].text
                if '09:30h' not in text: continue
                # Input and mapping retain every exact character; only input run
                # segmentation/direction simulates the older primary presentation.
                left,right=text.split(':',1);parent=run.getparent();index=parent.index(run)
                for offset,(value,rtl) in enumerate([(left,'0'),(':','1'),(right,'0')]):
                    new=deepcopy(run);new.find(model.W+'t').text=value
                    props=new.find(model.W+'rPr')
                    if props is None: props=etree.Element(model.W+'rPr');new.insert(0,props)
                    for prior in list(props.findall(model.W+'rtl')):props.remove(prior)
                    etree.SubElement(props,model.W+'rtl').set(model.W+'val',rtl)
                    parent.insert(index+offset,new)
                parent.remove(run)
        raw=changed_part(path.read_bytes(),'word/document.xml',split)
        path.write_bytes(raw)
        mapping_path=path.with_suffix('.source_map.json');mapping=json.loads(mapping_path.read_bytes())
        mapping['docx_sha256']=sha256(raw).hexdigest()
        mapping_path.write_text(json.dumps(mapping,ensure_ascii=False),encoding='utf-8')
        return path
    monkeypatch.setattr(workflow,'assemble_docx',assemble)


def candidate(layout,root,pointer):
    marker=json.loads((root/'candidate.json').read_bytes())
    value=layout.service.saved.verified_unreviewed_candidate(pointer['review_id'],marker['candidate_id'])
    assert value.source_map['source_layout_plan']['clock_direction_version']=='clock_h_colon_ltr_v1'
    assert value.source_map['source_layout_plan']['clock_ltr_spans']
    assert value.receipt['document_reviewed'] is False
    assert value.receipt['rendered_layout_acceptance']=='not_evaluated'
    assert value.receipt['source_character_coverage']=='not_proven'
    assert all(page['source_coverage_verified'] is False for page in value.source_map['source_evidence']['pages'])
    return marker,value


def test_fresh_automatic_clock_download_and_binding_keep_warning_and_review_gates(tmp_path,monkeypatch):
    install_body_proposal(monkeypatch);install_fictional_split_assembly(monkeypatch)
    source,output=tmp_path/'source.pdf',tmp_path/'output';output.mkdir();flow._source(source,('digital',))
    app,jobs,sdk,requests=flow._app(tmp_path,monkeypatch,(LINES,),(1,));scope='?mode=shadow&workspace=fictional'
    with TestClient(app) as client:
        job_id=flow._start(client,source,output,'AR',start=1,end=1,image_mode='off')
        job=flow._wait(jobs,job_id)
        assert job['result']['automatic_layout']['status']=='automatic_unreviewed',job
        assert len(sdk.requests)==len(requests)==1 and len(sdk.semantic_requests)==3
        root=Path(job['result']['run_dir'])/'ordinary_auto_layout';pointer=json.loads((root/'operation.json').read_bytes())
        layout=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        marker,value=candidate(layout,root,pointer)
        response=client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        assert response.status_code==200 and response.content==value.docx_bytes
        raw=jobs.trusted_ordinary_layout_job(job_id,runtime_mode='shadow',workspace_id='fictional')
        assert flow._docx_text(response.content)==flow._docx_text(raw.original_docx)
        assert _read(operation(layout,pointer)/'result.json')['source_layout_review_required'] is True
        view=layout.service.state(job_id)['review']
        assert view['decisions']['review']['document_reviewed'] is False
        with pytest.raises(c.OrdinaryLayoutError,match='output_review_required'):
            layout.service.accept_output(job_id,marker['candidate_id'],view['generation'],nonce(),False,expected_baseline_id=pointer['baseline_id'])
        from legalpdf_translate.saved_docx_layout_service import SavedDocxLayoutServiceError
        with pytest.raises(SavedDocxLayoutServiceError):
            layout.service.saved.build(view['review_id'],view['generation'],nonce(),True)
        evidence=auto._proposal_evidence(layout,job_id,pointer['baseline_id'],pointer['review_id'],pointer['operation_nonce'],(1,),auto.frozen_automatic_layout_policy())
        assert evidence['clock_direction_version']=='clock_h_colon_ltr_v1'
        raw_map=json.loads(next(Path(job['result']['run_dir']).rglob('provider.source_map.json')).read_bytes())
        before=protected(operation(layout,pointer))
        fp=auto.frozen_automatic_layout_policy().split(':',1)[1]
        for bad_fp,bad in [(fp,{k:v for k,v in evidence.items() if k!='clock_direction_version'}),
            (fp,{**evidence,'clock_direction_version':None}),(fp,{**evidence,'clock_direction_version':'other'}),
            (auto._body_columns_v3_policy().split(':',1)[1],evidence),('f'*64,evidence)]:
            with pytest.raises(SavedDocxLayoutServiceError,match='ordinary_source_(clock|folio)_direction_changed'):
                layout.service.saved.attach_ordinary_binding(view['review_id'],raw_map,(1,),bad_fp,bad,expected_generation=view['generation'])
        assert protected(operation(layout,pointer))==before and len(requests)==1 and len(sdk.semantic_requests)==3


def test_direct_successor_reuses_strict_semantics_and_two_raw_responses_with_clock_plan(tmp_path,monkeypatch):
    install_body_proposal(monkeypatch);install_fictional_split_assembly(monkeypatch)
    source,output=tmp_path/'source.pdf',tmp_path/'output';output.mkdir();flow._source(source,('digital',)*3)
    app,jobs,sdk,requests=flow._app(tmp_path,monkeypatch,(LINES,)*3,(1,2,3));scope='?mode=shadow&workspace=fictional'
    old=auto._source_bound_v4_policy();mapper=auto._band_normalization_version
    with TestClient(app) as client:
        with monkeypatch.context() as previous:
            previous.setattr(auto,'frozen_automatic_layout_policy',lambda:old)
            previous.setattr(auto,'_band_normalization_version',lambda fp:c.BAND_NORMALIZATION_V2 if fp==old.split(':',1)[1] else mapper(fp))
            job_id=flow._start(client,source,output,'AR',start=1,end=3,image_mode='off',page_breaks=True)
            initial=flow._wait(jobs,job_id)
        assert initial['result']['automatic_layout']['status']=='raw_fallback'
        assert len(sdk.requests)==3 and len(sdk.semantic_requests)==3 and len(requests)==2
        run=Path(initial['result']['run_dir']);root=run/'ordinary_auto_layout'
        pointer=json.loads((root/'operation.json').read_bytes())
        layout=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        op=operation(layout,pointer);before=protected(op);semantic=protected(run/'semantic_audit')
        baseline_paths=[op.parent.parent/name for name in ['provider.docx','reviewed.docx','source.pdf']]
        assert all(path.is_file() for path in baseline_paths)
        baseline={path:path.read_bytes() for path in baseline_paths}
        assert (run/'semantic_audit/manifest.json').is_file()
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
        recovered=flow._wait(jobs,job_id)
        assert recovered['result']['automatic_layout']['status']=='automatic_unreviewed',recovered
        assert len(sdk.requests)==len(sdk.semantic_requests)==len(requests)==3
        assert json.loads(requests[-1]['input'][0]['content'][0]['text'])['page_number']==3
        child=root/'recoveries/layout_direct_revalidation_v1';identity=json.loads((child/'intent.json').read_bytes())
        assert set(identity['retained_pages'])=={'1','2'}
        child_pointer=json.loads((child/'operation.json').read_bytes());nextop=operation(layout,child_pointer)
        _,value=candidate(layout,child,child_pointer)
        assert _read(nextop/'result.json')['source_layout_review_required'] is True
        for page in [1,2]:assert (nextop/f'page-{page:04d}.response.json').read_bytes()==(op/f'page-{page:04d}.response.json').read_bytes()
        assert all(path.read_bytes()==data for path,data in (before|baseline).items())
        assert protected(run/'semantic_audit')==semantic
        download=client.get(f'/api/translation/jobs/{job_id}/artifact/output_docx'+scope)
        assert download.status_code==200 and download.content==value.docx_bytes
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+scope).status_code==200
        resumed_id=flow._start(client,source,output,'AR',start=1,end=3,image_mode='off',page_breaks=True,resume=True)
        flow._wait(jobs,resumed_id)
        assert client.post(f'/api/translation/jobs/{resumed_id}/layout/recover'+scope).status_code==200
        assert flow._wait(jobs,resumed_id)['result']['automatic_layout']['status']=='automatic_unreviewed'
        assert len(sdk.requests)==len(sdk.semantic_requests)==len(requests)==3
        assert all(path.read_bytes()==data for path,data in (before|baseline).items())
        assert protected(run/'semantic_audit')==semantic


def test_former_body_v3_policy_actual_saved_binding_stays_clock_absent(tmp_path,monkeypatch):
    from tests.test_ordinary_body_columns_workflow import test_actual_binding_preserves_old_and_new_numeric_run_identity_and_rejects_other_claims
    old=auto._body_columns_v3_policy()
    monkeypatch.setattr(auto,'frozen_automatic_layout_policy',lambda:old)
    test_actual_binding_preserves_old_and_new_numeric_run_identity_and_rejects_other_claims(tmp_path,monkeypatch,'fresh')
