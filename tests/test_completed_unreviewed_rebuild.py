"""Closed completed V5 renderer migration through ordinary browser Rebuild."""
from decimal import Decimal
from pathlib import Path
import json
import time
from copy import deepcopy

from fastapi.testclient import TestClient
import pytest

from legalpdf_translate import ordinary_auto_layout as automatic
from legalpdf_translate import ordinary_layout_contracts as c
from legalpdf_translate.ordinary_layout_service import _read
from tests import test_ordinary_auto_layout_workflow as flow
from tests.test_ordinary_auto_layout_recovery import offline
from tests.test_terminal_accounting_restore import gmail_fixture, restart_into_app

SCOPE = '?mode=shadow&workspace=fictional'


def wait(jobs, job_id):
    deadline = time.monotonic()+180
    while time.monotonic()<deadline:
        job=jobs.get_job(job_id)
        if job and job['status'] in {'completed','failed','cancelled'}:
            return job
        time.sleep(.05)
    pytest.fail(f'Bounded local rebuild did not settle: {jobs.get_job(job_id)}')


def seed(tmp_path, monkeypatch, *, source_hard=False):
    source, output = tmp_path/'fictional.pdf', tmp_path/'outputs'
    output.mkdir(); flow._source(source, ('digital',)*3)
    original = flow._proposal
    def proposal(view, page, columns=0):
        result = original(view, page, columns)
        for row in result['paragraphs']:
            row.update(role='body', heading_level=0, heading_size_pt=None, bold=False)
        ids = [row['paragraph_id'] for row in result['paragraphs']]
        result.update(version=c.PROPOSAL_VERSION_V3, paragraph_partitions=[], source_coverage_findings=[],
            source_layout_evidence=[{'kind':'source_footer','paragraph_ids':ids[-3:],'bbox':[.06,.935,.94,.995]}])
        result['bands']=[{'kind':'flow','groups':[{'paragraph_ids':ids,'panel':False}]}]
        for row, role in zip(result['paragraphs'][-3:], ['reference','source_folio','reference'] if page==3 else ['body','source_folio','body']):
            row['role']=role
        return result
    monkeypatch.setattr(flow, '_proposal', proposal)
    outputs = tuple(f'Fictional body {p}.\nFictional address.\nPage {p} of 3\nFictional contact.' for p in (1,2,3))
    app, jobs, sdk, requests = flow._app(tmp_path, monkeypatch, outputs, (1,2,3))
    if source_hard:
        from legalpdf_translate.accounting_policy import ordinary_accounting_policy
        from legalpdf_translate.budget_reservations import ReservationBudget
        from legalpdf_translate.usage_accounting import DispatchAccounting
        budget=ReservationBudget(tmp_path/'shared-hard-budget.json',cap_usd='10',identity={'fictional':'completed-rebuild'})
        # The ordinary public policy intentionally has no verified auto-tier
        # hard envelope. This fictional SDK always returns default tier; bind
        # that explicit finite fixture envelope before seeding its paid parent.
        policy=ordinary_accounting_policy().accounting_arguments()
        for limits in policy['dispatch_limits'].values():
            limits['allowed_actual_service_tiers']=['default']
        jobs._workflow_accounting['accounting_factory']=lambda **kwargs:DispatchAccounting(**kwargs,
            budget_context=budget,**policy)
    loaded, session, gmail = gmail_fixture(source, output)
    form = {'source_path':str(source),'output_dir':str(output),'target_lang':'EN','start_page':1,'end_page':3,
        'image_mode':'off','ocr_mode':'off','workers':1,'gmail_batch_context':gmail}
    client = TestClient(app)
    with monkeypatch.context() as old:
        old.setattr(automatic, 'frozen_automatic_layout_policy', automatic._heading_columns_v4_policy)
        response = client.post('/api/translation/jobs/translate', json={'mode':'shadow','workspace_id':'fictional','form_values':form})
        job_id = response.json()['normalized_payload']['job']['job_id']
        failed = wait(jobs, job_id)
        assert failed['status']=='completed',failed
        assert failed['result']['automatic_layout']['status']=='raw_fallback', failed
    with monkeypatch.context() as old:
        old.setattr(automatic, 'frozen_automatic_layout_policy', automatic._reference_footer_v5_policy)
        assert client.post(f'/api/translation/jobs/{job_id}/layout/recover'+SCOPE).status_code==200
        completed = wait(jobs, job_id)
        assert completed['result']['automatic_layout']['status']=='automatic_unreviewed', completed
    assert len(sdk.requests)==len(requests)==3
    return app, jobs, client, job_id, loaded, session, form, sdk, requests


@pytest.mark.parametrize('restart', [False, True])
def test_public_rebuild_completed_retained_successor_is_zero_provider_and_idempotent(tmp_path, monkeypatch, restart):
    app, jobs, client, parent, loaded, session, form, sdk, requests = seed(tmp_path, monkeypatch)
    immutable_owner=parent
    run = Path(jobs.get_job(parent)['result']['run_dir'])
    if restart:
        app, jobs = restart_into_app(tmp_path, app, jobs, parent, loaded, session)
        client = TestClient(app)
        response = client.post('/api/translation/jobs/translate', json={'mode':'shadow','workspace_id':'fictional',
            'form_values':{**form,'resume':True}})
        parent = response.json()['normalized_payload']['job']['job_id']
        resumed = wait(jobs, parent)
        assert resumed['result']['automatic_layout']['status']=='raw_fallback', resumed
    manager = app.state.ordinary_layouts.manager_for_context(app.state.shadow_context, 'shadow', 'fictional')
    accounting = app.state.ordinary_layouts._accounting
    proof = automatic.completed_unreviewed_rebuild_predecessor(manager, accounting, parent)
    assert proof['render_policy']==automatic._reference_footer_v5_policy()
    old_files = {p:p.read_bytes() for p in run.joinpath('ordinary_auto_layout').rglob('*') if p.is_file() and p.suffix!='.lock'}
    owner = manager.service.root / proof['operation']['origin_job_id']
    old_files.update({p:p.read_bytes() for p in owner.rglob('*') if p.is_file() and p.suffix!='.lock'})
    manager.provider_factory = lambda *args: pytest.fail('Rebuild constructed provider factory')
    manager.accounting_factory = lambda *args: pytest.fail('Rebuild constructed paid accountant')
    identities=[]; candidates=[]
    for iteration in range(3):
        origin=parent if iteration<2 else child
        response = client.post(f'/api/translation/jobs/{origin}/rebuild'+SCOPE)
        assert response.status_code==200,response.text
        child = response.json()['normalized_payload']['job']['job_id']
        final = wait(jobs, child)
        result = final['result']['automatic_layout']
        assert result['status']=='automatic_unreviewed', result
        # Completed Rebuild remains the closed5737-to-7c54 migration when
        # the ordinary fresh policy advances to optional emphasis V2.
        assert result['policy_fingerprint']==automatic._inline_folio_direction_policy().split(':',1)[1]
        assert automatic.frozen_automatic_layout_policy()!=automatic._inline_folio_direction_policy()
        assert result['reviewed'] is False and 'rebuild_predecessor' not in result
        assert result['source_layout_review_required']
        candidates.append(result['candidate_id'])
        folder = run/'ordinary_auto_layout/rebuilds/completed_unreviewed_v1'/result['policy_fingerprint']
        identity=json.loads((folder/'intent.json').read_bytes()); identities.append(identity)
        assert identity['retained_only'] and identity['missing_pages']==[] and identity['max_new_calls']==0
        pointer=json.loads((folder/'operation.json').read_bytes())
        op=manager.service.root/pointer['origin_job_id']/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
        assert json.loads((op/'accounting/dispatch_accounting.json').read_bytes())['events']==[]
        assert _read(op/'accounting_summary.json')['provider_dispatch_count']==0
        assert Decimal(result['layout_costs']['cost_usd'])==Decimal(proof['layout_costs']['cost_usd'])
        if iteration==0:
            downloaded=client.get(f'/api/translation/jobs/{child}/artifact/output_docx'+SCOPE)
            assert downloaded.status_code==200,downloaded.text
            assert flow._docx_text(downloaded.content)==flow._docx_text(manager._job(child).original_docx)
    assert len(set(candidates))==1 and identities[0]==identities[1]==identities[2]
    assert all(path.read_bytes()==raw for path,raw in old_files.items())
    assert len(sdk.requests)==len(requests)==3
    if restart:
        # Normal app restart uses the immutable run's saved recipe. The private
        # capsule bootstraps its original owner; Resume discovers the durable
        # successor through the unchanged raw-fallback wrapper shape again.
        second_restart=tmp_path/'second_restart';second_restart.mkdir()
        app,jobs=restart_into_app(second_restart,app,jobs,immutable_owner,loaded,session)
        client=TestClient(app)
        manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
        manager.provider_factory=lambda *args:pytest.fail('Restarted completed Rebuild constructed provider')
        response=client.post('/api/translation/jobs/translate',json={'mode':'shadow','workspace_id':'fictional',
            'form_values':{**form,'resume':True}})
        resumed_owner=response.json()['normalized_payload']['job']['job_id']
        assert wait(jobs,resumed_owner)['result']['automatic_layout']['status']=='raw_fallback'
        response=client.post(f'/api/translation/jobs/{resumed_owner}/rebuild'+SCOPE)
        child=response.json()['normalized_payload']['job']['job_id']
        final=wait(jobs,child)
        assert final['result']['automatic_layout']['candidate_id']==candidates[0],final['result']
    # Cost consumption remains valid after the ordinary Save freeze. Freeze is
    # not admission for a new migration, and must not erase settled charges.
    from legalpdf_translate.ordinary_layout_integration import delivery_job_snapshot
    final=jobs.get_job(child)
    snapshot,_=delivery_job_snapshot(manager,final)
    assert Decimal(snapshot['layout_costs']['cost_usd'])==Decimal(proof['layout_costs']['cost_usd'])
    assert Decimal(str(snapshot['result']['save_seed']['api_cost']))==Decimal(str(final['result']['save_seed']['api_cost']))+Decimal(proof['layout_costs']['cost_usd'])
    # A real qualified formatting edit on the alias remains a different
    # unreviewed delivery. It cannot become migration admission, while normal
    # cost consumption must still retain the original charge.
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from io import BytesIO
    working=manager.service.automatic_review_copy(child);working_before=working.read_bytes()
    document=Document(BytesIO(working_before));document.paragraphs[0].alignment=WD_ALIGN_PARAGRAPH.RIGHT
    edited=BytesIO();document.save(edited);working.write_bytes(edited.getvalue())
    original_generation=manager.service.state(child)['generation']
    edited_view=manager.service.adopt_automatic_word_edit(child)
    assert edited_view['delivery']['kind']=='automatic_unreviewed_edited'
    with pytest.raises(c.OrdinaryLayoutError,match='parent_selected'):
        automatic.completed_unreviewed_rebuild_predecessor(manager,app.state.ordinary_layouts._accounting,child)
    edited_snapshot,_=delivery_job_snapshot(manager,final)
    assert Decimal(edited_snapshot['layout_costs']['cost_usd'])==Decimal(proof['layout_costs']['cost_usd'])
    assert manager.service.state(child)['generation']==original_generation
    # Restore only this independent synthetic edit fixture for the Save case.
    edits=manager.service.root/child/'alias_edits'
    for path in sorted(edits.rglob('*'),reverse=True):
        if path.is_file():path.unlink()
        else:path.rmdir()
    edits.rmdir();working.write_bytes(working_before)
    state=manager.service.state(child)
    snapshot,artifact=delivery_job_snapshot(manager,jobs.get_job(child),mutation=True,
        baseline_id=state['baseline_id'],expected_delivery_generation=0,freeze_nonce='f'*32)
    assert artifact.frozen
    assert Decimal(snapshot['layout_costs']['cost_usd'])==Decimal(proof['layout_costs']['cost_usd'])
    with pytest.raises(c.OrdinaryLayoutError,match='parent_selected'):
        automatic.completed_unreviewed_rebuild_predecessor(manager,app.state.ordinary_layouts._accounting,child)


def put_record(path,value):
    path.write_bytes(c.encode({'payload':value,'sha256':c.digest(c.encode(value))}))


def test_native_parent_pointer_marker_response_and_settlement_tampering_declines_before_new_operation(tmp_path,monkeypatch):
    app,jobs,client,parent,_,_,_,_,_=seed(tmp_path,monkeypatch)
    manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
    accounting=app.state.ordinary_layouts._accounting
    proof=automatic.completed_unreviewed_rebuild_predecessor(manager,accounting,parent)
    folder=Path(proof['parent_folder']);pointer=json.loads((folder/'operation.json').read_bytes())
    operation=manager.service.root/pointer['origin_job_id']/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
    ancestor=proof['operation']
    manager.provider_factory=lambda *args:pytest.fail('Invalid predecessor constructed provider')
    manager.accounting_factory=lambda *args:pytest.fail('Invalid predecessor constructed paid accountant')
    cases=[]
    for key,value in [('review_id','f'*32),('initial_generation',999),('selected_pages',[1,2])]:
        row=deepcopy(pointer);row[key]=value;cases.append((f'pointer_{key}',folder/'operation.json',c.encode(row)))
    marker=json.loads((folder/'candidate.json').read_bytes())
    for key,value in [('origin_job_id','tx-wrong'),('generation',999),('review_id','f'*32)]:
        row=deepcopy(marker);row[key]=value;cases.append((f'marker_{key}',folder/'candidate.json',c.encode(row)))
    row=deepcopy(marker);row['identity']['policy_fingerprint']='f'*64
    cases.append(('marker_policy',folder/'candidate.json',c.encode(row)))
    intent=_read(operation/'intent.json');row=deepcopy(intent);row['request']['page_numbers']=[1,2]
    cases.append(('native_page_selection',operation/'intent.json',c.encode({'payload':row,'sha256':c.digest(c.encode(row))})))
    raw=json.loads((operation/'page-0001.response.json').read_bytes());raw['page_number']=2
    cases.append(('response_page',operation/'page-0001.response.json',c.encode(raw)))
    cases.append(('published_output',manager.service.root/ancestor['origin_job_id']/'automatic/output.docx',b'changed'))
    cases.append(('durable_copy',folder/'output.docx',b'changed'))
    result=_read(operation/'result.json');row=deepcopy(result);row['completed_pages']=[1,2]
    cases.append(('incomplete_result',operation/'result.json',c.encode({'payload':row,'sha256':c.digest(c.encode(row))})))
    for label,path,changed in cases:
        before=path.read_bytes()
        try:
            path.write_bytes(changed)
            with pytest.raises(Exception) as error:
                automatic.completed_unreviewed_rebuild_predecessor(manager,accounting,parent)
            assert isinstance(error.value,(c.OrdinaryLayoutError,ValueError)),(label,error.value)
        finally:path.write_bytes(before)
    assert automatic.completed_unreviewed_rebuild_predecessor(manager,accounting,parent)==proof
    assert not (Path(proof['run_root'])/'ordinary_auto_layout/rebuilds').exists()


def test_retained_only_does_not_spend_available_shared_hard_capacity(tmp_path,monkeypatch):
    app,jobs,client,parent,_,_,_,sdk,requests=seed(tmp_path,monkeypatch,source_hard=True)
    manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
    source=jobs._jobs[parent]._completed_accountant
    before=source.budget_context.path.read_bytes()
    assert Decimal(source.budget_context.status()['remaining_usd'])>1
    manager.provider_factory=lambda *args:pytest.fail('Available hard capacity must not construct a provider')
    response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
    child=response.json()['normalized_payload']['job']['job_id']
    final=wait(jobs,child)
    assert final['result']['automatic_layout']['status']=='automatic_unreviewed',final['result']
    assert source.budget_context.path.read_bytes()==before
    assert len(sdk.requests)==len(requests)==3


def test_later_supported_paid_layout_charge_is_consumed_with_original_charge_once(tmp_path,monkeypatch):
    app,jobs,client,parent,_,_,_,_,requests=seed(tmp_path,monkeypatch)
    manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
    accounting=app.state.ordinary_layouts._accounting
    response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
    child=response.json()['normalized_payload']['job']['job_id'];final=wait(jobs,child)
    original=Decimal(final['result']['automatic_layout']['layout_costs']['known_cost_usd'])
    state=manager.service.state(child)
    # This separate ordinary authorization uses the existing fictional SDK. It
    # is deliberately outside the zero-call Rebuild, and its failed optional
    # manual hint still has an honest, fully settled native charge.
    accounting.authorize(manager._job(child),'a'*32,'5')
    later=manager.suggest(child,state['generation'],'b'*32,[3],expected_baseline_id=state['baseline_id'])
    assert later['accounting']['complete'] and len(requests)==4
    local=manager.layout_costs(child)
    assert Decimal(local['known_cost_usd'])>0
    from legalpdf_translate.ordinary_layout_integration import delivery_job_snapshot
    snapshot,_=delivery_job_snapshot(manager,jobs.get_job(child))
    assert Decimal(snapshot['layout_costs']['known_cost_usd'])==original+Decimal(local['known_cost_usd'])


def test_historical_eight_thousand_cost_only_ancestor_is_not_a_reused_response_origin(tmp_path,monkeypatch):
    from tests import test_ordinary_auto_layout_recovery as recovery_cases
    captured={};original_app=recovery_cases._app
    def capture(*args,**kwargs):
        values=original_app(*args,**kwargs);captured['values']=values;return values
    # Reuse the genuine existing native SDK/accounting fixture and its original
    # assertions, with the then-current V5 renderer made explicit.
    with monkeypatch.context() as historical:
        historical.setattr(recovery_cases,'_app',capture)
        historical.setattr(automatic,'frozen_automatic_layout_policy',automatic._reference_footer_v5_policy)
        recovery_cases.test_old_eight_thousand_token_checkpoint_resumes_then_recovers_at_current_bound(tmp_path,historical)
    app,jobs,sdk,requests=captured['values']
    parent=next(key for key in jobs._jobs if jobs.get_job(key)['result'].get('automatic_layout',{}).get('status')=='automatic_unreviewed')
    manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
    proof=automatic.completed_unreviewed_rebuild_predecessor(manager,app.state.ordinary_layouts._accounting,parent)
    manager.provider_factory=lambda *args:pytest.fail('Cost-only failed ancestor triggered a provider')
    with TestClient(app) as client:
        response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
        child=response.json()['normalized_payload']['job']['job_id'];final=wait(jobs,child)
    result=final['result']['automatic_layout'];assert result['status']=='automatic_unreviewed',result
    folder=Path(final['result']['run_dir'])/'ordinary_auto_layout/rebuilds/completed_unreviewed_v1'/result['policy_fingerprint']
    identity=json.loads((folder/'intent.json').read_bytes())
    assert {row['predecessor']['operation_nonce'] for row in identity['retained_pages'].values()}=={proof['operation']['operation_nonce']}
    assert requests[0]['max_output_tokens']==8000 and requests[1]['max_output_tokens']==32000
    assert len(sdk.requests)==1 and len(requests)==2
    assert Decimal(result['layout_costs']['known_cost_usd'])==Decimal(proof['layout_costs']['known_cost_usd'])


def test_apply_boundary_restores_only_summary_and_never_recreates_lost_native_journal(tmp_path,monkeypatch):
    app,jobs,client,parent,_,_,_,sdk,requests=seed(tmp_path,monkeypatch)
    manager=app.state.ordinary_layouts.manager_for_context(app.state.shadow_context,'shadow','fictional')
    manager.provider_factory=lambda *args:pytest.fail('Interrupted local Rebuild constructed provider')
    response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
    child=response.json()['normalized_payload']['job']['job_id'];final=wait(jobs,child)
    result=final['result']['automatic_layout'];assert result['status']=='automatic_unreviewed',result
    run=Path(final['result']['run_dir'])
    folder=run/'ordinary_auto_layout/rebuilds/completed_unreviewed_v1'/result['policy_fingerprint']
    pointer=json.loads((folder/'operation.json').read_bytes())
    owner=manager.service.root/pointer['origin_job_id']
    operation=owner/'baselines'/pointer['baseline_id']/'suggestions'/pointer['operation_nonce']
    # Fictional crash image: decisions were applied; no operation result or
    # publication yet. Cached saved build is harmless and must reuse its bytes.
    remove=[folder/'candidate.json',folder/'output.docx',owner/'automatic.json',
        *(owner/'automatic').iterdir(),operation/'result.json',operation/'accounting_summary.json',
        operation.parent.parent/'suggestion_results'/(pointer['operation_nonce']+'.json')]
    removed={p:p.read_bytes() for p in remove}
    for path in removed:path.unlink()
    response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
    resumed=response.json()['normalized_payload']['job']['job_id'];recovered=wait(jobs,resumed)
    assert recovered['result']['automatic_layout']['candidate_id']==result['candidate_id'],recovered['result']
    assert _read(operation/'accounting_summary.json')['provider_dispatch_count']==0
    assert all(p.read_bytes()==raw for p,raw in removed.items())
    identity=json.loads((folder/'intent.json').read_bytes())
    # Fast reuse must retain the entire native authorization, request identity
    # and journal owner. These are not recreated from copied aggregate totals.
    auth=folder/'authorization.json';budget=folder/'budget.json'
    intent_path=operation/'intent.json'
    mutations=[]
    for key,value in [('cap_usd','1'),('retained_only',False)]:
        row=json.loads(auth.read_bytes());row[key]=value
        mutations.append((auth,c.encode(row)))
    native=_read(intent_path)
    for key,value in [('model','unapproved'),('effort','low'),('max_new_calls',1),('band_normalization_version',c.BAND_NORMALIZATION_V4)]:
        row=deepcopy(native);row['request']['policy'][key]=value
        mutations.append((intent_path,c.encode({'payload':row,'sha256':c.digest(c.encode(row))})))
    for path,replacement in mutations+[(auth,None),(budget,None)]:
        before=path.read_bytes()
        try:
            if replacement is None:path.unlink()
            else:path.write_bytes(replacement)
            with pytest.raises(Exception):automatic._verify_rebuild_zero(manager,pointer,identity)
            if replacement is None:assert not path.exists()
        finally:path.write_bytes(before)
    # Independent earlier crash image: only page1 was copied, generation is
    # still initial, and no sidecar/application/publication exists. Restore
    # this synthetic image between fault cases; no actual run is edited.
    saved=manager.service.saved._folder(pointer['review_id'])
    early_paths=[*removed,saved/'generations'/f"{pointer['initial_generation']+1:06d}.json",
        saved/'ordinary_binding.json',saved/'ordinary_raw_source_map.json',
        saved/'ordinary_proposals'/f"{pointer['initial_generation']+1:06d}.json",
        operation/'source_evidence.json',operation/'proposed_decisions.json',
        *(operation/f'page-{p:04d}.{kind}.json' for p in (2,3) for kind in ('response','retained'))]
    early={p:p.read_bytes() for p in early_paths}
    for path in early:path.unlink()
    real_authorize=app.state.ordinary_layouts._accounting.completed_rebuild;constructed=[]
    def count_accountant(*args,**kwargs):
        policy,factory=real_authorize(*args,**kwargs)
        def counted(*values):constructed.append(True);return factory(*values)
        return policy,counted
    monkeypatch.setattr(app.state.ordinary_layouts._accounting,'completed_rebuild',count_accountant)
    first=operation/'page-0001.response.json';first_before=first.read_bytes();first.write_bytes(first_before+b'\n')
    response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
    bad=response.json()['normalized_payload']['job']['job_id'];assert wait(jobs,bad)['result']['automatic_layout']['status']=='raw_fallback'
    assert constructed==[]
    terminal_result=_read(operation/'result.json')
    terminal_index=operation.parent.parent/'suggestion_results'/(pointer['operation_nonce']+'.json')
    for status in ('failed','cancelled'):
        terminal=deepcopy(terminal_result);terminal['status']=status
        put_record(operation/'result.json',terminal);put_record(terminal_index,terminal)
        before_result=(operation/'result.json').read_bytes()
        response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
        repeated=response.json()['normalized_payload']['job']['job_id']
        assert wait(jobs,repeated)['result']['automatic_layout']['status']=='raw_fallback'
        assert (operation/'result.json').read_bytes()==before_result
        assert manager.service.state(pointer['origin_job_id'])['generation']==pointer['initial_generation']
        assert constructed==[]
    first.write_bytes(first_before)
    # Reset the fictional pre-failure crash image for its independent positive
    # replay, rather than asking product code to reinterpret a terminal failure.
    for path in (operation/'result.json',operation.parent.parent/'suggestion_results'/(pointer['operation_nonce']+'.json')):
        if path.exists():path.unlink()
    response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
    partial=response.json()['normalized_payload']['job']['job_id'];completed=wait(jobs,partial)
    assert completed['result']['automatic_layout']['candidate_id']==result['candidate_id'],completed['result']
    assert constructed==[True] and all(p.read_bytes()==raw for p,raw in early.items())
    # The same crash with a LOST journal is a provenance failure, never a new
    # empty ledger. This fixture touches only the synthetic successor namespace.
    for path in removed:path.unlink()
    journal=operation/'accounting/dispatch_accounting.json';journal.unlink()
    response=client.post(f'/api/translation/jobs/{parent}/rebuild'+SCOPE)
    declined=response.json()['normalized_payload']['job']['job_id'];halted=wait(jobs,declined)
    assert halted['result']['automatic_layout']['status']=='raw_fallback'
    assert not journal.exists() and not (folder/'candidate.json').exists()
    assert len(sdk.requests)==len(requests)==3
