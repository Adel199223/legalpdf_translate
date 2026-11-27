"""Historical policy/byte identity and fresh saved clock context contracts."""
import base64
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from lxml import etree
import pytest

from legalpdf_translate import ordinary_auto_layout as auto
from legalpdf_translate import ordinary_auto_layout_artifacts as artifacts
from legalpdf_translate import ordinary_source_layout as source
from legalpdf_translate import saved_docx_layout as model
from legalpdf_translate import saved_docx_layout_writer as writer
from tests.clock_direction_fakes import split_inputs
from tests.test_saved_docx_layout import changed_part

OLD='source_image_unreviewed_v1:1e4a11e243d8a6a27dd7fa30c54e4475dfae4a3f74a68e789eef1be15362ab4b'
NEW='source_image_unreviewed_v1:d3c89ef63893696d339f350c00500a4cd865f594ce56ed9a45472bb350b5e0b7'
HISTORY=Path(__file__).parent/'fixtures/clock_direction_prechange_v3.json'


def writer_args():
    raw,_,snapshot,frames,decisions,evidence,_=split_inputs()
    context={'selected_pages':[1],'page_groups':[[p,list(ids)] for p,ids in snapshot.page_groups],
        'source_evidence':evidence['source_evidence'],'source_folio_direction_version':'numeric_run_ltr_v3'}
    return raw,snapshot.saved_snapshot,frames,decisions,context


def build(args):
    return writer.build_unreviewed_docx(*args[:4],ordinary_context=args[4])


def verify(candidate,args):
    writer.validate_built_docx(candidate.docx_bytes,candidate.source_map,original_docx=args[0],
        snapshot=args[1],pages=args[2],decisions=args[3],require_review=False,ordinary_context=args[4])


def test_ten_historical_maps_and_new_version_only_identity():
    history=json.loads(HISTORY.read_bytes())
    assert len(history['historical_ten_maps'])==10
    for row in history['historical_ten_maps']:
        policy=row['policy'];fp=policy.split(':',1)[1]
        assert auto._band_normalization_version(fp)==row['band_normalization_version']
        assert auto._source_normalization_version(fp)==row['source_hint_normalization_version']
        assert auto._clock_direction_version(fp) is None
        assert (policy in auto._metadata_normalization_policies())==row['metadata_and_emphasis_policy_member']
        assert (policy in auto._source_folio_policies())==row['source_folio_policy_member']
        assert (policy in {NEW,OLD,auto._source_bound_v4_policy()})==row['numeric_run_ltr_v3_evidence_emitted_when_source_evidence_present']
    assert auto._body_columns_v3_policy()==OLD and auto._clock_direction_policy()==NEW
    fp=NEW.split(':',1)[1]
    assert auto._clock_direction_version(fp)==source.CLOCK_DIRECTION_V1
    assert auto._band_normalization_version(fp)==auto._band_normalization_version(OLD.split(':',1)[1])
    assert auto._source_normalization_version(fp)==auto._source_normalization_version(OLD.split(':',1)[1])


@pytest.mark.parametrize('case_index',range(4))
def test_genuine_v3_docx_map_receipt_replay_and_fresh_empty_metadata(case_index):
    history=json.loads(HISTORY.read_bytes());case=history['cases'][case_index]
    raw=base64.b64decode(case['raw_base64']);pdf=base64.b64decode(case['source_pdf_base64'])
    snapshot=artifacts.bind_raw_page_map(raw,case['raw_source_map'],source_pdf_sha256=sha256(pdf).hexdigest(),
        selected_pages=(1,),target_lang=case['lang'])
    evidence=case['evidence'];before=deepcopy(evidence)
    old=artifacts.build_unreviewed_candidate(raw,snapshot,case['frames'],case['decisions'],proposal_evidence=evidence,source_pdf_bytes=pdf)
    assert (old.docx_sha256,old.source_map_sha256,old.receipt_sha256)==tuple(case[k] for k in
        ['candidate_docx_sha256','candidate_map_sha256','candidate_receipt_sha256'])
    assert 'clock_direction_version' not in old.source_map['source_layout_plan']
    assert 'clock_ltr_spans' not in old.source_map['source_layout_plan']
    fresh_evidence={**evidence,'policy_fingerprint':NEW.split(':',1)[1],'clock_direction_version':source.CLOCK_DIRECTION_V1}
    fresh=artifacts.build_unreviewed_candidate(raw,snapshot,case['frames'],case['decisions'],proposal_evidence=fresh_evidence,source_pdf_bytes=pdf)
    artifacts.verify_unreviewed_candidate(raw,snapshot,case['frames'],case['decisions'],fresh,proposal_evidence=fresh_evidence,source_pdf_bytes=pdf)
    assert fresh.source_map['source_layout_plan']['clock_direction_version']==source.CLOCK_DIRECTION_V1
    if case['kind']=='primary_whole':
        assert fresh.docx_bytes==old.docx_bytes
        assert fresh.source_map['source_layout_plan']['clock_ltr_spans']==[]
        old_map=deepcopy(old.source_map);new_map=deepcopy(fresh.source_map)
        for key in ['clock_direction_version','clock_ltr_spans']:del new_map['source_layout_plan'][key]
        for key in ['source_layout_plan_sha256','proposal_evidence_sha256']:
            del old_map[key];del new_map[key]
        assert old_map==new_map
    else:
        assert len(fresh.source_map['source_layout_plan']['clock_ltr_spans'])==2
        assert fresh.docx_bytes!=old.docx_bytes
    assert evidence==before
    assert fresh.receipt['document_reviewed'] is False
    assert fresh.receipt['rendered_layout_acceptance']=='not_evaluated'
    assert fresh.receipt['source_character_coverage']=='not_proven'


@pytest.mark.parametrize('fault',['missing','null','unknown','former','arbitrary','no_source'])
def test_build_and_verify_share_exact_fresh_evidence_pin(fault):
    raw,_,snapshot,frames,decisions,evidence,pdf=split_inputs()
    evidence.update(policy_fingerprint=NEW.split(':',1)[1],clock_direction_version=source.CLOCK_DIRECTION_V1)
    candidate=artifacts.build_unreviewed_candidate(raw,snapshot,frames,decisions,proposal_evidence=evidence,source_pdf_bytes=pdf)
    bad=deepcopy(evidence)
    if fault=='missing': del bad['clock_direction_version']
    elif fault=='null': bad['clock_direction_version']=None
    elif fault=='unknown': bad['clock_direction_version']='other'
    elif fault=='former': bad['policy_fingerprint']=OLD.split(':',1)[1]
    elif fault=='arbitrary': bad['policy_fingerprint']='f'*64
    elif fault=='no_source':
        del bad['source_evidence'];del bad['source_folio_direction_version']
    for call in [lambda:artifacts.build_unreviewed_candidate(raw,snapshot,frames,decisions,proposal_evidence=bad,source_pdf_bytes=pdf),
        lambda:artifacts.verify_unreviewed_candidate(raw,snapshot,frames,decisions,candidate,proposal_evidence=bad,source_pdf_bytes=pdf)]:
        with pytest.raises(ValueError,match='source_clock_direction_version'): call()


def test_unowned_public_writer_context_remains_supported_and_preserved():
    args=writer_args();args[4].update(page_groups=[[1,[]]],source_evidence={'version':'ordinary_source_evidence_v1','pages':[]})
    old=build(args);verify(old,args)
    args[4]['clock_direction_version']=source.CLOCK_DIRECTION_V1
    fresh=build(args);verify(fresh,args)
    assert fresh.docx_bytes==old.docx_bytes
    assert fresh.source_map['source_layout_plan']['clock_ltr_spans']==[]


def test_public_writer_only_changes_two_existing_colon_attributes_and_rejects_review_claim():
    args=writer_args();old=build(args);args[4]['clock_direction_version']=source.CLOCK_DIRECTION_V1
    fresh=build(args);verify(fresh,args)
    with ZipFile(BytesIO(old.docx_bytes)) as archive:before={name:archive.read(name) for name in archive.namelist()}
    with ZipFile(BytesIO(fresh.docx_bytes)) as archive:after={name:archive.read(name) for name in archive.namelist()}
    assert set(before)==set(after)
    assert all(before[name]==after[name] for name in before if name!='word/document.xml')
    old_xml=model._xml(before['word/document.xml']);new_xml=model._xml(after['word/document.xml'])
    plan=fresh.source_map['source_layout_plan'];assert len(plan['clock_ltr_spans'])==2
    p=next(new_xml.iter(model.W+'p'))
    for span in plan['clock_ltr_spans']:
        for change in span['colon_runs']:
            rtl=p.findall(model.W+'r')[change['run_index']].find(model.W+'rPr/'+model.W+'rtl')
            assert rtl.get(model.W+'val')=='0';rtl.set(model.W+'val','1')
    assert model._c14n(new_xml)==model._c14n(old_xml)
    with pytest.raises(ValueError):
        writer.validate_built_docx(fresh.docx_bytes,fresh.source_map,original_docx=args[0],snapshot=args[1],
            pages=args[2],decisions=args[3],require_review=True,ordinary_context=args[4])


@pytest.mark.parametrize('fault',['missing','extra','duplicate','moved','page','offset','run','hash','version','no_context','old_context',
    'text','font','digit_rtl','h_rtl','arabic_rtl','pPr','run_order','unlisted_colon'])
def test_public_verification_rejects_tampering_even_after_outer_hashes_are_repaired(fault):
    args=writer_args();args[4]['clock_direction_version']=source.CLOCK_DIRECTION_V1
    artifact=build(args);mapping=deepcopy(artifact.source_map);plan=mapping['source_layout_plan'];raw=artifact.docx_bytes
    span=plan['clock_ltr_spans'][0]
    if fault=='missing': plan['clock_ltr_spans'].pop()
    elif fault=='extra': plan['clock_ltr_spans'].append(deepcopy(span)|{'paragraph_id':'p000002'})
    elif fault=='duplicate': plan['clock_ltr_spans'].append(deepcopy(span))
    elif fault=='moved': plan['clock_ltr_spans'].reverse()
    elif fault=='page': span['source_page_number']=7
    elif fault=='offset': span['start']+=1
    elif fault=='run': span['colon_runs'][0]['run_index']+=1
    elif fault=='hash': span['clock_text_sha256']='f'*64
    elif fault=='version': plan['clock_direction_version']='other'
    elif fault=='no_context': del args[4]['clock_direction_version']
    elif fault=='old_context': args[4]['clock_direction_version']=None
    else:
        def patch(root):
            p=next(root.iter(model.W+'p'));runs=p.findall(model.W+'r')
            if fault=='text': runs[0].find(model.W+'t').text+='x'
            elif fault=='font': runs[2].find(model.W+'rPr/'+model.W+'rFonts').set(model.W+'ascii','Other')
            elif fault in {'digit_rtl','h_rtl','arabic_rtl'}:
                runs[0 if fault=='arabic_rtl' else 1 if fault=='digit_rtl' else 3].find(model.W+'rPr/'+model.W+'rtl').set(model.W+'val','0' if fault=='arabic_rtl' else '1')
            elif fault=='pPr': etree.SubElement(p.find(model.W+'pPr'),model.W+'jc').set(model.W+'val','left')
            elif fault=='run_order': p.append(runs[0])
            elif fault=='unlisted_colon': runs[2].find(model.W+'rPr/'+model.W+'rtl').set(model.W+'val','1')
        raw=changed_part(raw,'word/document.xml',patch)
    mapping['docx_sha256']=model._sha(raw)
    mapping['source_layout_plan_sha256']=model._sha(model._canonical(plan))
    with pytest.raises(ValueError): verify(writer.SavedDocxLayoutArtifact(raw,mapping),args)


def test_clock_context_requires_source_evidence_and_known_mode_before_any_build():
    args=writer_args();del args[4]['source_evidence'];args[4]['clock_direction_version']=source.CLOCK_DIRECTION_V1
    with pytest.raises(ValueError,match='source_clock_direction_version'): build(args)
