"""Fictional old-occurrence identity, not authority for new source content."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from legalpdf_translate import ordinary_semantic_enclosure_authority as enclosure
from legalpdf_translate import ordinary_semantic_enclosure_identity as identity
from legalpdf_translate import ordinary_semantic_literal_authority as literal
from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate import ordinary_semantic_review as review
from tests.test_ordinary_semantic_audit import page, token, PDF
from tests.test_source_enclosure_authority import prepared, sample, carried, response, VALUE
from tests.test_source_literal_authority import RECIPE, INVENTORY, origins, correction, resolution, example, image


def case(extra_pages=()):
    pages,registry,raw,eligible,answer,cert,old=prepared(extra_pages=extra_pages)
    new=enclosure.project(pages,registry,cert,identity_policy=identity.POLICY)
    return pages,registry,cert,old,new


def validate(texts,args):
    pages,registry,cert,old,new=args
    return enclosure.validate(correction(pages,texts),pages,INVENTORY,RECIPE,new,identity_policy=identity.POLICY)[0]


@pytest.mark.parametrize('position',['before','between','after'])
def test_distinct_addition_preserves_all_old_positions_and_original_bytes(position):
    args=case();pages,registry,cert,old,new=args;before=deepcopy(args)
    text=new.projected_pages[0].primary_text
    if position=='before':text=token('NEWLABEL')+' '+text
    elif position=='between':text=text.replace(token('AB45'),token('NEWLABEL')+' '+token('AB45'))
    else:text+=' '+token('NEWLABEL')
    with pytest.raises(review.SemanticAuditError,match='final_sequence_mismatch'):
        enclosure.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,old)
    assert validate([text],args)[1]==text
    assert args==before and old.projected_pages==new.projected_pages


def test_repeated_new_values_and_value_old_only_on_another_page_are_identity_positive():
    second=replace(sample(1),page_number=2,primary_text=sample(1).primary_text+' '+token('NEWLABEL'))
    args=case((second,));text=args[-1].projected_pages[0].primary_text+' '+token('NEWLABEL')+' '+token('NEWLABEL')
    selected=validate([text,second.primary_text],args)
    assert selected[1]==text and selected[2]==second.primary_text


@pytest.mark.parametrize('damage',['duplicate','drop','change','reorder','composite','old_inside_new',
    'pair_contains_new','prose_pair','nested','moved','unmatched','control','malformed'])
def test_old_identity_full_actual_stack_and_controls_are_not_filtered_away(damage):
    args=case();text=args[-1].projected_pages[0].primary_text
    if damage=='duplicate':text+=' '+token(VALUE)
    elif damage=='drop':text=text.replace(token('AB45'),'')
    elif damage=='change':text=text.replace(token('AB45'),token('DIFFERENT'))
    elif damage=='reorder':text=token('AB45')+' '+text.replace(token('AB45'),'')
    elif damage=='composite':text=text.replace(token('AB45'),token('AB45 NEWLABEL'))
    elif damage=='old_inside_new':text=text.replace(token('AB45'),token('XAB45X'))
    elif damage=='pair_contains_new':text=text.replace('['+token(VALUE)+']','['+token(VALUE)+' '+token('NEWLABEL')+']',1)
    elif damage=='prose_pair':text='['+token('NEWLABEL')+' '+text+']'
    elif damage=='nested':text=text.replace('['+token(VALUE)+']','[['+token(VALUE)+']]',1)
    elif damage=='moved':text=text.replace('['+token(VALUE)+']',token(VALUE),1)+' ['+token('NEWLABEL')+']'
    elif damage=='unmatched':text='['+token('NEWLABEL')+' '+text
    elif damage=='control':text+=' '+token('NEW\u200eLABEL')
    else:text+=' [[broken[[x]]]]'
    with pytest.raises(review.SemanticAuditError):validate([text],args)


def test_additions_cannot_manufacture_old_neighborhood_uniqueness():
    p=sample(5);pages=[p];registry=enclosure.freeze(pages,PDF,origins(pages))
    raw=correction(pages,[p.primary_text.replace(token(VALUE),'['+token(VALUE)+']',1)])
    eligible=enclosure.classify(raw,pages,INVENTORY,RECIPE,registry)
    answer=response(registry,eligible,['square']+['none']*4)
    cert=enclosure.certificate(review.audit._json(answer),pages,registry,eligible)
    with pytest.raises(review.SemanticAuditError,match='ambiguous_neighborhood'):
        enclosure.project(pages,registry,cert,identity_policy=identity.POLICY)


def tokens(values):return [(0,0,v,0,0) for v in values]


@pytest.mark.parametrize('count,accepted',[(8,True),(9,False)])
def test_page_occurrences_charge_repeated_values(count,accepted):
    budget=identity.AdditionBudget()
    if accepted:assert budget.mapping(tokens(['NEW']*count+['OLD']),['OLD'],['OLD'])==[count]
    else:
        with pytest.raises(review.SemanticAuditError,match='page_bound'):budget.mapping(tokens(['NEW']*count+['OLD']),['OLD'],['OLD'])


@pytest.mark.parametrize('length,accepted',[(512,True),(513,False)])
def test_exact_value_character_bound(length,accepted):
    budget=identity.AdditionBudget()
    if accepted:budget.mapping(tokens(['N'*length,'OLD']),['OLD'],['OLD'])
    else:
        with pytest.raises(review.SemanticAuditError,match='addition_value'):budget.mapping(tokens(['N'*length,'OLD']),['OLD'],['OLD'])


def test_page_total_characters_and_document_occurrences_count_every_repetition():
    budget=identity.AdditionBudget()
    for _ in range(3):budget.mapping(tokens(['N']*8+['OLD']),['OLD'],['OLD'])
    with pytest.raises(review.SemanticAuditError,match='total_bound'):budget.mapping(tokens(['N','OLD']),['OLD'],['OLD'])
    budget=identity.AdditionBudget()
    for _ in range(4):budget.mapping(tokens(['N'*512]*4+['OLD']),['OLD'],['OLD'])
    with pytest.raises(review.SemanticAuditError,match='total_bound'):budget.mapping(tokens(['N','OLD']),['OLD'],['OLD'])
    with pytest.raises(review.SemanticAuditError,match='page_bound'):
        identity.AdditionBudget().mapping(tokens(['N'*512]*4+['N','OLD']),['OLD'],['OLD'])


def test_shared_work_budget_is_inclusive_and_exact_cases_use_no_additive_work():
    work=identity.WorkBudget();work.charge(['x'*200000],['y'*200000],['z'*200000]);work.charge(['x'*200000],['y'*200000],['z'*200000])
    assert work.charged==identity.MAX_WORK
    with pytest.raises(review.SemanticAuditError,match='work_bound'):work.charge(['x'],[],[])
    args=case();work=identity.WorkBudget();new=args[-1]
    enclosure._check({1:new.projected_pages[0].primary_text},new,identity_policy=identity.POLICY,pages=args[0],work=work)
    assert work.charged==0


def mixed():
    pages,registry,raw,eligible,answer,old,new=carried(extra=True)
    cert=enclosure.certificate(review.audit._json(answer),pages,registry,eligible)
    return pages,registry,raw,cert,enclosure.project(pages,registry,cert,identity_policy=identity.POLICY),old,new


def test_mixed_certified_final_addition_preserves_retired_alias_exclusion():
    pages,registry,raw,cert,context,old,new=mixed()
    text=context.projected_pages[0].primary_text+' '+token('NEWLABEL')
    assert enclosure.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context,identity_policy=identity.POLICY)[0][1]==text
    for bad in [text+' '+token(old),text+' '+token(new),text.replace(token(new),token('WRONG'))]:
        with pytest.raises(review.SemanticAuditError):enclosure.validate(correction(pages,[bad]),pages,INVENTORY,RECIPE,context,identity_policy=identity.POLICY)
    # Initial same-page lost/gained expansion remains outside the literalV1 classifier.
    with pytest.raises(review.SemanticAuditError):enclosure.classify(correction(pages,[text]),pages,INVENTORY,RECIPE,registry)


def test_existing_certified_initial_slot_with_addition_on_other_page_keeps_transition_proof(monkeypatch):
    first,old,new=example('image');first=replace(first,primary_text='النص ('+token(old)+') '+token('AB45')+'.')
    second=replace(sample(1),page_number=2);pages=[first,second];registry=enclosure.freeze(pages,PDF,origins(pages))
    text1=first.primary_text.replace(token(old),token(new));text2=second.primary_text+' '+token('NEWLABEL')
    raw=correction(pages,[text1,text2]);eligible=enclosure.classify(raw,pages,INVENTORY,RECIPE,registry)
    answer={'version':enclosure.RESPONSE,'literal_decisions':resolution(registry,eligible,['ZX1209'])['decisions'],'enclosure_observations':[]}
    cert=enclosure.certificate(review.audit._json(answer),pages,registry,eligible);context=enclosure.project(pages,registry,cert,identity_policy=identity.POLICY)
    events=[];view=enclosure._candidate_tokens;charge=identity.WorkBudget.charge;mapping=identity.AdditionBudget.mapping
    def observed_view(text):events.append('view');return view(text)
    def observed_charge(self,*args):events.append('charge');return charge(self,*args)
    def observed_mapping(self,*args):events.append('map');return mapping(self,*args)
    monkeypatch.setattr(enclosure,'_candidate_tokens',observed_view)
    monkeypatch.setattr(identity.WorkBudget,'charge',observed_charge)
    monkeypatch.setattr(identity.AdditionBudget,'mapping',observed_mapping)
    enclosure.check_initial_sequence_replacement_eligibility(raw,pages,INVENTORY,registry,cert,context,identity_policy=identity.POLICY)
    assert events.count('view')==2 and events.count('charge')==1
    assert events.index('charge')<events.index('map')
    # No inferred assignment of a wrong third value plus another new value to a slot.
    with pytest.raises(review.SemanticAuditError):enclosure.check_initial_sequence_replacement_eligibility(correction(pages,[text1+' '+token('NEWLABEL'),text2]),pages,INVENTORY,registry,cert,context,identity_policy=identity.POLICY)


@pytest.mark.parametrize('damage',['missing_policy','old_context','tag','unknown','descriptor'])
def test_saved_identity_context_mode_cannot_be_swapped_or_inferred(damage):
    args=case();pages,registry,cert,old,new=args;policy=identity.POLICY
    if damage=='missing_policy':policy=None
    elif damage=='old_context':new=old
    elif damage=='tag':new=replace(new,identity_policy=None)
    elif damage=='unknown':policy='unknown'
    else:
        new=deepcopy(new);new.evidence['source_enclosure_identity']['max_page_occurrences']=99
    with pytest.raises(review.SemanticAuditError):enclosure.validate(correction(pages,[new.projected_pages[0].primary_text]),pages,INVENTORY,RECIPE,new,identity_policy=policy)


def test_absence_descriptor_and_source_resolver_requests_remain_exact():
    pages,registry,raw,eligible,answer,cert,old=prepared();new=enclosure.project(pages,registry,cert,identity_policy=identity.POLICY)
    assert {k:v for k,v in new.evidence.items() if k!='source_enclosure_identity'}==old.evidence
    assert new.source_facts==old.source_facts and new.enclosure_facts==old.enclosure_facts
    assert repair.descriptor(repair.POLICY_V4)==repair.descriptor(repair.POLICY_V4,source_enclosure_identity_policy=None)
    descriptor=repair.descriptor(repair.POLICY_V4,source_enclosure_identity_policy=identity.POLICY)
    assert {k:v for k,v in descriptor.items() if k not in {'source_enclosure_identity','source_enclosure_replacement_instructions_sha256'}}==repair.descriptor(repair.POLICY_V4)
    assert enclosure.replacement_instructions()==enclosure.REPLACEMENT_INSTRUCTIONS
    assert 'SAME PAGE' in enclosure.replacement_instructions(identity.POLICY)
    assert 'may repeat within or across pages' in enclosure.replacement_instructions(identity.POLICY)
    before=deepcopy((pages,registry,eligible));request=enclosure.request(pages,RECIPE,registry,eligible)
    assert request==enclosure.request(pages,RECIPE,registry,eligible) and before==(pages,registry,eligible)


class AdditionScenario:
    def __init__(self,unsupported=False):
        from tests.test_source_enclosure_authority_workflow import EnclosureScenario
        self.base=EnclosureScenario();self.unsupported=unsupported
    def __call__(self,body,data):
        data=self.base(body,data)
        if 'text' in body:
            payload=json.loads(body['input'][0]['content'][0]['text']);value=json.loads(data['output'][0]['content'][0]['text'])
            if payload['stage']=='correction':
                for row in value['pages']:row['corrected_text']+=' '+token('NEWLABEL')
            elif payload['stage']=='verification' and self.unsupported:
                value['unsupported_additions']=[{'target_unit_ids':['T001'],'reason':'Fictional unsupported marker.'}]
            data['output'][0]['content'][0]['text']=json.dumps(value,ensure_ascii=False)
        return data


@pytest.mark.parametrize('unsupported',[False,True])
def test_native_new_value_is_identity_only_final_source_verifier_still_rules(tmp_path,unsupported):
    from tests.test_source_enclosure_authority_workflow import start
    from tests.test_semantic_review_model_integration import immutable
    scenario=AdditionScenario(unsupported);config,http,flow=start(tmp_path,scenario);result=flow.run(config)
    assert result.success is (not unsupported),result.error
    assert [p['stage'] for p in scenario.base.payloads]==['source_inventory','correction','source_literal_authority','verification']
    assert len(http.requests)==5
    saved=flow._last_state.settings['ordinary_semantic_audit_recipe'];assert saved['source_enclosure_identity_policy']==identity.POLICY
    before=immutable(result.run_dir);assert flow.run(replace(config,resume=True)).success is (not unsupported)
    assert len(http.requests)==5 and immutable(result.run_dir)==before
    if not unsupported:
        manifest=json.loads((result.run_dir/'semantic_audit/manifest.json').read_bytes());assert manifest['consumed_cycles']==1
        assert json.loads((result.run_dir/'semantic_audit/candidate_origin.json').read_bytes())['origin']=='initial_correction_revalidated'


@pytest.mark.parametrize('cross_page',[False,True])
def test_native_certified_disagreement_keeps_existing_replacement_route(tmp_path,cross_page):
    from tests.test_source_enclosure_authority_workflow import CertifiedDisagreementScenario, start
    from tests.test_workflow_semantic_audit_integration import CORRECTED
    base=CertifiedDisagreementScenario()
    def scenario(body,data):
        data=base(body,data)
        if cross_page and 'text' in body:
            payload=json.loads(body['input'][0]['content'][0]['text'])
            if payload['stage']=='correction':
                value=json.loads(data['output'][0]['content'][0]['text'])
                for row in value['pages']:
                    if row['page_number']==2:
                        row['corrected_text']=CORRECTED+base.tail(original=True)+' '+token('NEWLABEL')
                data['output'][0]['content'][0]['text']=json.dumps(value,ensure_ascii=False)
        return data
    config,http,flow=start(tmp_path,scenario)
    if cross_page:
        import fitz
        with fitz.open(config.pdf_path) as doc:
            doc.new_page().insert_text((50,80),'Fictional second original page.')
            doc.saveIncr()
    result=flow.run(config);assert result.success,result.error
    assert [p['stage'] for p in base.payloads]==['source_inventory','correction','source_literal_authority','correction','verification']
    assert len(http.requests)==(7 if cross_page else 6)
    directory=result.run_dir/'semantic_audit'
    assert json.loads((directory/'candidate_origin.json').read_bytes())['origin']=='single_full_replacement'
    assert json.loads((directory/'manifest.json').read_bytes())['consumed_cycles']==1


@pytest.mark.parametrize('damage',['unknown','null','repair','literal','enclosure','absent'])
def test_saved_capability_is_optional_but_strictly_bound_to_existing_pair(tmp_path,damage):
    from tests.test_semantic_review_model_integration import setup
    from legalpdf_translate import workflow_semantic_audit as glue,ordinary_auto_layout as auto
    from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe,SemanticAuditRecipeError,sha256_of_text
    config,http,flow=setup(tmp_path)
    saved=glue.fresh_recipe(config,'gpt-5.2',auto.frozen_automatic_layout_policy(),
        context_text=config.context_text,context_hash=sha256_of_text(config.context_text))
    settings={'ordinary_semantic_audit_recipe':saved,'image_mode':config.image_mode.value,
        'ordinary_auto_layout_policy':saved['ordinary_auto_layout_policy'],
        'ocr_engine':config.ocr_engine.value,'ocr_api_provider':config.ocr_api_provider.value,
        'strip_bidi_controls':config.strip_bidi_controls,
        'primary_assembly_recipe':{'version':'terminal_source_bound_folio_v4',
            'ordinary_auto_layout_policy':saved['ordinary_auto_layout_policy']}}
    assert ordinary_semantic_audit_recipe(settings)==saved
    assert saved['source_enclosure_identity_policy']==identity.POLICY
    if damage=='unknown':saved['source_enclosure_identity_policy']='unknown'
    elif damage=='null':saved['source_enclosure_identity_policy']=None
    elif damage=='repair':saved['semantic_repair_policy']=repair.POLICY_V3
    elif damage=='literal':saved.pop('semantic_literal_authority_policy')
    elif damage=='enclosure':saved.pop('semantic_enclosure_authority_policy')
    else:
        # Historical optional-identity absence predates its dependent markup proof.
        saved.pop('primary_literal_markup_policy',None)
        saved.pop('semantic_enclosure_sequence_repair_policy',None)
        saved.pop('primary_page_evidence_policy',None)
        saved.pop('source_enclosure_identity_policy')
    if damage=='absent':assert 'source_enclosure_identity_policy' not in ordinary_semantic_audit_recipe(settings)
    else:
        with pytest.raises(SemanticAuditRecipeError):ordinary_semantic_audit_recipe(settings)
    assert http.requests==[]
