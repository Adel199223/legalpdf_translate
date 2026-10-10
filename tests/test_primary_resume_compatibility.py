"""Only deterministic primary compatibility15 may bridge retained Resume bytes."""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

from docx import Document
from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import docx_writer, workflow
from legalpdf_translate.translation_service import TranslationJobManager
from tests.test_ordinary_auto_layout_workflow import _app, _source, _start, _wait
from tests.test_ordinary_auto_layout_recovery import _success_layout_provider


def _rewrite(path, member, transform):
    raw=path.read_bytes()
    with ZipFile(BytesIO(raw)) as source:
        out=BytesIO()
        with ZipFile(out,'w') as target:
            for item in source.infolist():
                value=source.read(item.filename)
                target.writestr(item,transform(value) if item.filename==member else value)
    path.write_bytes(out.getvalue())


def _bound(tmp_path):
    source=tmp_path/'source.pdf';source.write_bytes(b'fictional source')
    run=tmp_path/'run';origin='tx-123456789abc'
    retained=run/'ordinary_layout_originals'/origin;retained.mkdir(parents=True)
    old=retained/'provider.docx';document=Document();document.add_paragraph('Fictional retained text 42');document.save(old)
    docx_writer._remove_compatibility_mode(old)
    mapping={'docx_sha256':sha256(old.read_bytes()).hexdigest(),'pages':[{'source_page_number':1}]}
    old_map=retained/'provider.source_map.json';old_map.write_text(json.dumps(mapping))
    op=run/'ordinary_auto_layout';op.mkdir()
    intent={'run_id':'same-run','runtime_mode':'shadow','workspace_id':'fictional','target_lang':'EN',
            'policy_fingerprint':'same-policy','source_pdf_sha256':sha256(source.read_bytes()).hexdigest(),
            'raw_docx_sha256':sha256(old.read_bytes()).hexdigest(),
            'raw_source_map_bytes_sha256':sha256(old_map.read_bytes()).hexdigest(),'selected_pages':[1]}
    (op/'intent.json').write_text(json.dumps(intent));(op/'operation.json').write_text(json.dumps({'origin_job_id':origin}))
    fresh=tmp_path/'fresh.docx';fresh.write_bytes(old.read_bytes());docx_writer._ensure_primary_compatibility_mode15(fresh)
    mapping['docx_sha256']=sha256(fresh.read_bytes()).hexdigest();fresh.with_suffix('.source_map.json').write_text(json.dumps(mapping))
    job=SimpleNamespace(result_payload={'run_dir':str(run),'save_seed':{'run_id':'same-run'}},
        runtime_mode='shadow',workspace_id='fictional',config_payload={'target_lang':'EN'},
        _ordinary_auto_layout_policy='ordinary:same-policy',_ordinary_baseline=None)
    return job,fresh,source,old,old_map


def test_exact_settings_transform_reuses_original_bytes_and_map(tmp_path):
    job,fresh,source,old,old_map=_bound(tmp_path)
    before=(old.read_bytes(),old_map.read_bytes());assert fresh.read_bytes()!=before[0]
    assert TranslationJobManager._reuse_proven_ordinary_baseline(None,job,fresh,source)
    assert job._ordinary_baseline['original_sha256']==sha256(before[0]).hexdigest()
    assert job._ordinary_baseline['mapping_sha256']==sha256(before[1]).hexdigest()
    assert (old.read_bytes(),old_map.read_bytes())==before


@pytest.mark.parametrize('change',['settings','body','footer','extra_member','source','policy','map','retained_map'])
def test_other_changes_cannot_use_compatibility_bridge(tmp_path,change):
    job,fresh,source,old,old_map=_bound(tmp_path);before=(old.read_bytes(),old_map.read_bytes())
    if change=='settings':
        _rewrite(fresh,'word/settings.xml',lambda v:v.replace(b'</w:settings>',b'<w:zoom w:percent="71"/></w:settings>'))
    elif change=='body':
        _rewrite(fresh,'word/document.xml',lambda v:v.replace(b'retained',b'CHANGED'))
    elif change=='footer':
        with ZipFile(fresh,'a') as z:z.writestr('word/footer99.xml',b'<changed/>')
    elif change=='extra_member':
        with ZipFile(fresh,'a') as z:z.writestr('unrelated.xml',b'<changed/>')
    elif change=='source':source.write_bytes(b'changed source')
    elif change=='policy':job._ordinary_auto_layout_policy='ordinary:changed-policy'
    elif change=='map':
        p=fresh.with_suffix('.source_map.json');v=json.loads(p.read_text());v['pages'][0]['extra']='changed';p.write_text(json.dumps(v))
    else:
        old_map.write_bytes(old_map.read_bytes()+b' ')
    if change in {'settings','body','footer','extra_member'}:
        p=fresh.with_suffix('.source_map.json');v=json.loads(p.read_text());v['docx_sha256']=sha256(fresh.read_bytes()).hexdigest();p.write_text(json.dumps(v))
    with pytest.raises(ValueError,match='ordinary_auto_layout_rebuild_'):
        TranslationJobManager._reuse_proven_ordinary_baseline(None,job,fresh,source)
    assert job._ordinary_baseline is None and old.read_bytes()==before[0]
    if change!='retained_map':assert old_map.read_bytes()==before[1]


def test_fresh_manager_normal_resume_keeps_old_raw_and_cost_once(tmp_path,monkeypatch):
    monkeypatch.delenv('LEGALPDF_TRANSLATION_PROTOCOL',raising=False)
    monkeypatch.setattr(workflow,'load_environment',lambda:None)
    monkeypatch.setattr(workflow,'run_translation_auth_test',lambda *a,**k:pytest.fail('unexpected auth'))
    monkeypatch.setattr(workflow,'resolve_openai_key_with_source',lambda *a,**k:pytest.fail('unexpected credentials'))
    source=tmp_path/'source.pdf';output=tmp_path/'output';output.mkdir();_source(source,('digital',))
    app,jobs,sdk,requests=_app(tmp_path,monkeypatch,('Fictional retained English text 42',),(1,),failed_page=1,failure='incomplete')
    with TestClient(app) as client:
        with monkeypatch.context() as old_writer:
            old_writer.setattr(docx_writer,'_ensure_primary_compatibility_mode15',docx_writer._remove_compatibility_mode)
            original_id=_start(client,source,output,'EN',start=1,end=1,image_mode='off')
            original=_wait(jobs,original_id)
        assert original['result']['automatic_layout']['status']=='raw_fallback'
        old_baseline=jobs._jobs[original_id]._ordinary_baseline
        old_raw=Path(old_baseline['original_path']);old_map=Path(old_baseline['mapping_path'])
        before=(old_raw.read_bytes(),old_map.read_bytes())
        assert len(sdk.requests)==len(requests)==1
    # Reconstruct through an actual new manager and normal checkpoint Resume.
    app2,jobs2,sdk2,requests2=_app(tmp_path,monkeypatch,(),(1,),failed_page=1,failure='incomplete')
    with TestClient(app2) as client:
        resumed_id=_start(client,source,output,'EN',start=1,end=1,image_mode='off',resume=True)
        resumed=_wait(jobs2,resumed_id)
        assert resumed['result']['automatic_layout']['status']=='raw_fallback',resumed
        baseline=jobs2._jobs[resumed_id]._ordinary_baseline
        assert baseline, resumed
        assert baseline['original_path']==str(old_raw) and baseline['mapping_path']==str(old_map)
        assert baseline['original_sha256']==sha256(before[0]).hexdigest()
        assert (old_raw.read_bytes(),old_map.read_bytes())==before
        assert len(sdk2.requests)==len(requests2)==0
        manager=app2.state.ordinary_layouts.manager_for_context(app2.state.shadow_context,'shadow','fictional')
        # Existing recovery fixture helper's indexing includes the failed call.
        recovery_requests=[requests[0]]
        manager.provider_factory=_success_layout_provider(app2,recovery_requests)
        response=client.post(f'/api/translation/jobs/{resumed_id}/layout/recover?mode=shadow&workspace=fictional')
        assert response.status_code==200,response.text
        completed=_wait(jobs2,resumed_id)
        assert completed['result']['automatic_layout']['status']=='automatic_unreviewed',completed
        assert len(sdk2.requests)==0 and len(recovery_requests)==2
        shown=client.get(f'/api/translation/jobs/{resumed_id}?mode=shadow&workspace=fictional').json()['normalized_payload']['job']
        assert shown['layout_costs']['operations']==2 and shown['layout_costs']['complete']
        assert (old_raw.read_bytes(),old_map.read_bytes())==before

