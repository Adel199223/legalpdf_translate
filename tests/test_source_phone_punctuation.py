from copy import deepcopy
import pytest

from legalpdf_translate import ordinary_ocr_visual_source as visual
from legalpdf_translate import ordinary_source_phone_punctuation as punctuation
from legalpdf_translate.ar_source_fields import _view
from legalpdf_translate.arabic_pre_tokenize import pretokenize_arabic_source

PHONE="333 112 233"
WEB="www.justica.pt"
PRINTED=PHONE+" /chamada para a rede móvel)"
AR="مكالمة إلى الشبكة المحمولة"


def fixture(monkeypatch, *, printed=PRINTED):
    rows=["Telefone",printed,WEB]
    coarse={"lines":[{"text":text,"words":[]} for text in rows]}
    scans=[{"dpi":dpi,"readings":rows[:]} for dpi in (288,432)]
    regions=[{"role":"side","coarse_lines":[0,1,2],"scans":scans,"detail":[]}]
    groups=[("side",rows[:])]
    monkeypatch.setattr(visual,"_read_line",lambda row,scan:scan['readings'][rows.index(row['text'])])
    effective="Telefone\n"+PHONE+" chamada para a rede móvel\n"+WEB
    obligations={"headers":[],"literals":[PHONE,WEB],"aliases":[],"conditions":[],
                 "uncertain_punctuation":[PHONE],"supplemented_column":True,"supplemented_contact":False,
                 "mailing_labels":[],"phone_slots":[]}
    return effective,obligations,coarse,regions,groups


def restored(monkeypatch):
    data=fixture(monkeypatch)
    effective,obligations=punctuation.restore(*data)
    source=pretokenize_arabic_source(visual.prepared_source(effective,{"obligations":obligations}),source_field_policy="baseline_label_value_v1")
    return effective,obligations,source


@pytest.mark.parametrize("tail", [" /"+AR+")"," ("+AR+")"," （"+AR+"）"])
def test_corroborated_source_is_restored_and_faithful_or_balanced_target_passes(monkeypatch,tail):
    effective,obligations,source=restored(monkeypatch)
    assert PRINTED in effective and not obligations['uncertain_punctuation']
    assert obligations[punctuation.KEY]==[{"phone":PHONE,"source_row":PRINTED,"region":0,"coarse_line":1,"left":None,"right":WEB}]
    candidate=f"هاتف\n[[{PHONE}]]"+tail+f"\n[[{WEB}]]"
    assert visual.violation(candidate,source,{"obligations":obligations}) is None
    assert candidate==f"هاتف\n[[{PHONE}]]"+tail+f"\n[[{WEB}]]"


@pytest.mark.parametrize("damage", ['moved_close','extra_close','foreign_open','balanced_with_foreign_close','duplicate_phone','deleted_phone','swapped_phone','wrong_phone','other_digit','other_token','moved_anchor_into_qualifier','nonadjacent_close','wrong_delimiter','moved_phone_field'])
def test_only_the_source_owned_phone_qualifier_can_use_the_unmatched_close(monkeypatch,damage):
    _,obligations,source=restored(monkeypatch)
    first=f"[[{PHONE}]] /{AR})";second=f"[[{WEB}]]";candidate=first+"\n"+second
    if damage=='moved_close':candidate=first[:-1]+"\n"+second+"\n)"
    elif damage=='extra_close':candidate+="\n)"
    elif damage=='foreign_open':candidate='(\n'+candidate
    elif damage=='balanced_with_foreign_close':candidate=candidate.replace('/','(')+"\n)"
    elif damage=='duplicate_phone':candidate+="\n"+first
    elif damage=='deleted_phone':candidate=candidate.replace(f"[[{PHONE}]]","")
    elif damage=='swapped_phone':candidate=candidate.replace(PHONE,WEB,1).rsplit(WEB,1)[0]+PHONE+"]]"
    elif damage=='wrong_phone':candidate=candidate.replace(PHONE,"333 112 234")
    elif damage=='other_digit':candidate=candidate.replace(AR,AR+" 5")
    elif damage=='other_token':candidate=candidate.replace(AR,AR+" [[77]]")
    elif damage=='moved_anchor_into_qualifier':candidate=first.replace(AR,AR+" "+second)
    elif damage=='nonadjacent_close':candidate=first[:-1]+"\n)\n"+second
    elif damage=='wrong_delimiter':candidate=candidate.replace("/",":")
    elif damage=='moved_phone_field':candidate=second+"\n"+first
    assert visual.violation(candidate,source,{"obligations":obligations}) is not None


@pytest.mark.parametrize("damage", ['scan_disagreement','duplicate_source_phone','duplicate_compact_source','duplicate_digit_spaced_source','duplicate_split_source','duplicate_effective_phone','duplicate_compact_phone','wrong_effective_row','extra_source_id','wrong_digits','foreign_region','no_neighbour','unsupported_shape'])
def test_source_admission_never_generalizes_an_uncertain_or_unowned_row(monkeypatch,damage):
    effective,obligations,coarse,regions,groups=fixture(monkeypatch)
    if damage=='scan_disagreement':regions[0]['scans'][1]['readings'][1]=PRINTED.replace('/', '(')
    elif damage=='duplicate_source_phone':coarse['lines'].append({'text':PRINTED,'words':[]})
    elif damage=='duplicate_compact_source':coarse['lines'].append({'text':PHONE.replace(' ',''),'words':[]})
    elif damage=='duplicate_digit_spaced_source':coarse['lines'].append({'text':' '.join(PHONE.replace(' ','')),'words':[]})
    elif damage=='duplicate_split_source':coarse['lines'].extend({'text':part,'words':[]} for part in PHONE.split())
    elif damage=='duplicate_effective_phone':effective+='\n'+PHONE
    elif damage=='duplicate_compact_phone':effective+='\n'+PHONE.replace(' ','')
    elif damage=='wrong_effective_row':effective=effective.replace('móvel','fixa')
    elif damage=='extra_source_id':effective=effective.replace('rede','rede 777/26')
    elif damage=='wrong_digits':effective=effective.replace(PHONE,'333 112 234')
    elif damage=='foreign_region':regions[0]['coarse_lines'][1]=2
    elif damage=='no_neighbour':obligations['literals']=[PHONE]
    elif damage=='unsupported_shape':groups[0][1][1]=PRINTED.replace('móvel','móvel (local)')
    if damage in {'no_neighbour','unsupported_shape'}:
        result,proof=punctuation.restore(effective,obligations,coarse,regions,groups)
        assert result==effective and not proof[punctuation.KEY] and proof['uncertain_punctuation']==[PHONE]
    else:
        with pytest.raises(ValueError,match='requires_review'):
            punctuation.restore(effective,obligations,coarse,regions,groups)


def test_absent_capability_keeps_original_guard_behavior(monkeypatch):
    _,obligations,source=restored(monkeypatch)
    prior=deepcopy(obligations);prior.pop(punctuation.KEY)
    candidate=f"[[{PHONE}]] {AR}\n[[{WEB}]]\n)"
    assert visual.violation(candidate,source,{"obligations":prior}) is None
    assert visual.violation(candidate,source,{"obligations":obligations})=='ocr_visual_source_phone_punctuation'


def test_source_slots_and_target_characters_are_not_mutated(monkeypatch):
    _,obligations,source=restored(monkeypatch)
    candidate=f"[[{PHONE}]] /{AR})\n[[{WEB}]]"
    before=(source,candidate,deepcopy(obligations))
    assert punctuation.violation(_view(source),_view(candidate),obligations) is None
    assert before==(source,candidate,obligations)


def test_fresh_and_canonical_reloaded_guidance_have_exact_bytes(monkeypatch):
    import json
    _,obligations,_=restored(monkeypatch)
    witness={'sha256':'c'*64,'obligations':obligations}
    saved=json.loads(visual._encode(witness))
    assert list(witness['obligations'][punctuation.KEY][0])!=list(saved['obligations'][punctuation.KEY][0])
    assert visual.guidance(witness).encode('utf8')==visual.guidance(saved).encode('utf8')


@pytest.mark.parametrize("form", ["bare","balanced","printed","wrapped","compact"])
def test_already_present_sidebar_uses_the_same_measured_source_slot(monkeypatch,form):
    effective,obligations,coarse,regions,groups=fixture(monkeypatch)
    obligations['uncertain_punctuation']=[]
    groups[0]=('phone_qualifier',groups[0][1])
    regions[0]['role']='phone_qualifier'
    if form=='balanced':effective=effective.replace(PHONE+' chamada',PHONE+' (chamada').replace('móvel','móvel)')
    elif form=='printed':effective=effective.replace(PHONE+' chamada',PHONE+' /chamada').replace('móvel','móvel)')
    elif form=='wrapped':effective=effective.replace(PHONE,PHONE.replace(' ','\n')).replace(' chamada para a rede móvel','\nchamada\npara\na\nrede\nmóvel')
    elif form=='compact':effective=effective.replace(PHONE,PHONE.replace(' ',''))
    effective=effective.replace('\n', ' ') if form!='wrapped' else effective
    final,evidence=punctuation.restore(effective,obligations,coarse,regions,groups)
    assert final.splitlines().count(PRINTED)==1 and len(evidence[punctuation.KEY])==1
    assert not evidence['uncertain_punctuation']


def test_plans_cover_present_field_without_duplicating_missing_sidebar(monkeypatch):
    _,_,coarse,_,_=fixture(monkeypatch)
    assert punctuation.plans(coarse['lines'],[])==[('phone_qualifier',[1])]
    assert punctuation.plans(coarse['lines'],[('side',[0,1,2])])==[('side',[0,1,2])]
    coarse['lines'][1]['text']=PRINTED.replace('/','(')
    # Planning may inspect normalized coarse punctuation; only two agreeing
    # high-resolution source observations can create actual authority.
    assert punctuation.plans(coarse['lines'],[])==[('phone_qualifier',[1])]


@pytest.mark.parametrize('policy',[visual.POLICY,visual.POLICY_V2])
def test_historical_builds_never_enter_new_punctuation_policy(monkeypatch,policy):
    import fitz
    def denied(*a,**k):pytest.fail('historical build used V3')
    monkeypatch.setattr(punctuation,'restore',denied)
    monkeypatch.setattr(punctuation,'plans',denied)
    scan={'dpi':144,'bounds':[0,0,100,100],'png_sha256':'a'*64,'lines':[]}
    monkeypatch.setattr(visual,'_scan',lambda *a,**k:deepcopy(scan))
    with fitz.open() as doc:
        page=doc.new_page()
        effective,saved=visual._build(page,'Original source',1,'b'*64,None,policy=policy)
        assert punctuation.KEY not in saved['obligations']
        assert visual._build(page,'Original source',1,'b'*64,None,saved,policy=policy)==(effective,saved)
