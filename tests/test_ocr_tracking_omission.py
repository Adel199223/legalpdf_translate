from copy import deepcopy
import hashlib

import pytest

from legalpdf_translate import ordinary_ocr_source_spans as spans
from legalpdf_translate import ordinary_ocr_tracking_omission as tracking
from legalpdf_translate import ordinary_ocr_visual_source as visual


DATE = "Data de expedição: 02-10-2026"
REF = "94-18235861"
FOLLOW = "À atenção da Secretaria"
CODE = "XY263450917DE"


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def fixture(code=CODE, index=6, *, newline="\n"):
    texts = [DATE, REF, code[:2] + " " + code[2:-2] + " " + code[-2:], FOLLOW]
    def scanned_rows(indices, scale):
        return [{"text": texts[i], "words": [{"text": texts[i],
                 "box": [40*scale, (50+20*i)*scale, 130*scale, 10*scale]}]} for i in indices]
    coarse = {"dpi": 144, "png_sha256": sha("coarse"), "lines": scanned_rows(range(4), 1)}
    regions = []
    groups = []
    for role, ids in [("mailing", [0, 1, 2]), ("mailing_follow", [3])]:
        regions.append({"role":role, "coarse_lines":ids, "detail":[], "scans":[
            {"dpi":d, "bounds":[0,0,1000,1200], "png_sha256":sha(f"{role}_{d}"),
             "lines":scanned_rows(ids,d/144)} for d in (288,432)]})
        groups.append((role,[texts[i] for i in ids]))
    damaged = code[:index] + code[index+1:]
    slot = "  ".join(damaged)
    raw = newline.join(["Uma carta", DATE, "", REF, " "+slot+" ", FOLLOW, "Órgão 49"])
    return raw, coarse, regions, groups, slot


@pytest.mark.parametrize("code,index,newline",[(CODE,6,"\n"),("RA841906357IT",8,"\r\n")])
def test_only_one_internal_digit_and_its_separator_are_inserted(code,index,newline):
    raw,coarse,regions,groups,slot=fixture(code,index,newline=newline)
    derived, proof = tracking.restore(raw,coarse,regions,groups)
    start,end = proof["raw_span"]
    at = proof["insert_at"]
    assert raw[start:end] == slot and proof["raw_spelling_sha256"] == sha(slot)
    assert derived == raw[:at]+code[index]+" "+raw[at:]
    assert proof["raw_sha256"] == sha(raw) and proof["derived_sha256"] == sha(derived)
    assert proof["serial_character_index"] == index and proof["printed_code"] == code
    assert proof["mailing_reference"] == REF and proof["coarse_lines"] == [0,1,2,3]
    assert proof["mailing_png_sha256"] == [scan["png_sha256"] for scan in regions[0]["scans"]]
    virtual,projection=spans.project(derived,groups)
    effective,obligations=visual._derive(virtual,groups)
    assert projection["raw_sha256"] == sha(derived)
    assert effective.count(code) == effective.count(REF) == 1 and [REF,code] in obligations["mailing_labels"]


@pytest.mark.parametrize("code,index",[(CODE,2),(CODE,10),("RE113456789PT",3),
                                       ("RE123456788PT",9),("RE111111111PT",6),
                                       ("RE123445678PT",6)])
def test_terminal_or_ambiguous_digit_is_never_attributed(code,index):
    raw,coarse,regions,groups,_=fixture(code,index)
    with pytest.raises(ValueError,match="requires_review"):
        tracking.restore(raw,coarse,regions,groups)


@pytest.mark.parametrize("damage",["transpose","wrong_digit","missing_early_word","source_country",
    "other_region","other_date","other_reference","other_follow","duplicate_follow","duplicate_raw",
    "duplicate_correct","other_compact","other_unicode_space","other_invisible","source_duplicate",
    "source_competitor","scan_disagreement","foreign_owner","nonconsecutive_owner","shifted_crop",
    "unbounded_padding","extra_words","coarse_disagreement"])
def test_unsupported_ownership_adds_no_authority(damage):
    raw,coarse,regions,groups,slot=fixture()
    if damage=="transpose":
        short=slot.replace(" ","");raw=raw.replace(slot,"  ".join(short[:2]+short[3]+short[2]+short[4:]))
    elif damage=="wrong_digit":raw=raw.replace(slot,slot.replace("4","8"))
    elif damage=="missing_early_word":raw=raw.replace(slot,"  ".join(CODE[1:]))
    elif damage=="source_country":raw=raw.replace(slot,slot[:-1]+"F")
    elif damage=="other_region":raw=raw.replace(slot+"\u0020\n"+FOLLOW,slot+"\nnovo titular\n"+FOLLOW)
    elif damage=="other_date":raw=raw.replace(DATE,DATE.replace("02-10","03-10"))
    elif damage=="other_reference":raw=raw.replace(REF,REF[:-1]+"7")
    elif damage=="other_follow":raw=raw.replace(FOLLOW,"Outra secretaria")
    elif damage=="duplicate_follow":raw+="\n"+FOLLOW
    elif damage=="duplicate_raw":raw+="\n"+slot
    elif damage=="duplicate_correct":raw+="\n"+CODE
    elif damage=="other_compact":raw+="\nab23401985gb"
    elif damage=="other_unicode_space":raw+="\n"+"\u2009".join(CODE)
    elif damage=="other_invisible":raw+="\n"+"\u200b".join(CODE)
    elif damage=="source_duplicate":coarse["lines"].append(deepcopy(coarse["lines"][2]))
    elif damage=="source_competitor":coarse["lines"].append({"text":"RB301425678IT","words":[]})
    elif damage=="scan_disagreement":regions[0]["scans"][1]["lines"][2]["text"]=CODE.replace("9","8")
    elif damage=="foreign_owner":regions[0]["role"]="email"
    elif damage=="nonconsecutive_owner":regions[1]["coarse_lines"]=[0]
    elif damage=="shifted_crop":regions[0]["scans"][1]["bounds"][1]=300
    elif damage=="unbounded_padding":raw=raw.replace(slot,slot.replace("  "," "*30))
    elif damage=="extra_words":raw=raw.replace(slot,slot+" pessoa")
    elif damage=="coarse_disagreement":coarse["lines"][2]["text"]=coarse["lines"][2]["text"].replace("9","8")
    try:
        result, proof = tracking.restore(raw,coarse,regions,groups)
    except ValueError as error:
        assert str(error) == "ocr_visual_source_requires_review"
    else:
        assert proof is None and result == raw


def test_without_unique_positive_field_previous_route_retains_raw():
    raw,coarse,regions,groups,slot=fixture()
    for intact in (CODE," ".join(CODE)):
        actual=raw.replace(slot,intact)
        assert tracking.restore(actual,coarse,regions,groups)==(actual,None)
    assert tracking.restore(raw,coarse,[],[])==(raw,None)
    assert visual.POLICY=="local_source_slots_v1" and visual.FRESH_POLICY==visual.POLICY_V4


@pytest.mark.parametrize("sep",[""," ","  ","\t","\u2009","\u2066","\ufeff"])
def test_obsolete_value_is_still_rejected_beside_intact_source_token(sep):
    raw,coarse,regions,groups,slot=fixture();_,proof=tracking.restore(raw,coarse,regions,groups)
    source=f"[[{REF}]]\n[[{CODE}]]"
    obligations={"headers":[],"literals":[REF,CODE],"aliases":[[slot,CODE]],"tracking_omission_alias":slot}
    witness={"obligations":obligations}
    assert visual.violation(source,source,witness) is None
    wrong=sep.join(slot.replace(" ",""))
    assert visual.violation(source+"\n"+wrong,source,witness)=="ocr_visual_source_obsolete_literal"
    assert visual.violation(f"[[{REF}]]\n[[{wrong}]]",source,witness) in {
        "ocr_visual_source_literal", "ocr_visual_source_wrapper"}
    assert proof["printed_code"] == CODE


BEFORE = "A audiência prossegue na data marcada"
CENTER = "a decisão se mantém quando não for possível"
AFTER = "a outra pessoa comparecer ao tribunal"


def test_only_two_printed_condition_words_change_with_unique_neighbors():
    raw=BEFORE+"\r\n  a decisão e  mantém quando não há possível  \r\n"+AFTER
    a,b,replacement=visual._condition_gap([BEFORE,CENTER,AFTER],raw)
    assert raw[:a]+replacement+raw[b:]==raw.replace(" e "," se ").replace(" há "," for ")
    assert raw[:a].endswith("\r\n") and replacement.startswith("  ") and "  mantém" in replacement


@pytest.mark.parametrize("damage",["actor","negation","tense","new_verb","punctuation","wrong_neighbour",
    "duplicate_context","misplaced","other_connective","different_intervening_line"])
def test_ambiguous_or_substantive_condition_differences_abstain(damage):
    old=CENTER.replace(" se "," e ").replace(" for "," há ")
    raw=BEFORE+"\n"+old+"\n"+AFTER
    if damage=="actor":raw=raw.replace("a decisão","o arguido")
    elif damage=="negation":raw=raw.replace("não ","")
    elif damage=="tense":raw=raw.replace("mantém","manteve")
    elif damage=="new_verb":raw=raw.replace("mantém","reabre")
    elif damage=="punctuation":raw=raw.replace("mantém","mantém,")
    elif damage=="wrong_neighbour":raw=raw.replace("na data","a data")
    elif damage=="duplicate_context":raw+="\n"+BEFORE
    elif damage=="misplaced":raw=old+"\n"+BEFORE+"\n"+AFTER
    elif damage=="other_connective":raw=raw.replace(" e "," por ")
    elif damage=="different_intervening_line":raw=raw.replace(old,old+"\nMais contexto")
    assert visual._condition_gap([BEFORE,CENTER,AFTER],raw) is None

@pytest.mark.parametrize("duplicate",[None,0,1,2])
def test_condition_requires_each_printed_anchor_once(duplicate):
    old=CENTER.replace(" se "," e ").replace(" for "," há ")
    raw="\n".join([BEFORE,old,AFTER])
    rows=[{"text":text,"words":[{"text":text,"box":[20,20+i*15,125,12]}]}
          for i,text in enumerate([BEFORE,CENTER,AFTER])]
    if duplicate is not None:
        rows.append(deepcopy(rows[duplicate]))
    assert visual._condition_gap_plans(rows,[],raw)==(
        [("condition_gap",[0,1,2])] if duplicate is None else [])


@pytest.mark.parametrize("prior",["já","não será","sobre o pedido","nunca"])
def test_auxiliary_requires_the_same_directly_preceding_negation(prior):
    expected=CENTER.replace("não for",prior+" for")
    old=expected.replace(" se "," e ").replace(" for "," há ")
    assert visual._condition_gap([BEFORE,expected,AFTER],"\n".join([BEFORE,old,AFTER])) is None

def test_intact_mailing_field_does_not_claim_distant_short_identifier():
    raw,coarse,regions,groups,slot=fixture()
    untouched=raw.replace(slot," ".join(CODE))+"\n"+"Other record "*35+"\n"+" ".join("QD82710435US")
    assert tracking.restore(untouched,coarse,regions,groups)==(untouched,None)
    virtual,_=spans.project(untouched,groups)
    effective,_=visual._derive(virtual,groups)
    assert CODE in effective and " ".join("QD82710435US") in effective

@pytest.mark.parametrize("location",["source_split","source_format","raw_hidden","raw_beside_other_script"])
def test_competing_split_or_nonprinting_identifier_cannot_authorize_a_fix(location):
    raw,coarse,regions,groups,slot=fixture()
    damaged=slot.replace(" ","")
    if location=="source_split":
        coarse["lines"].extend({"text":part,"words":[]} for part in (damaged[:6],damaged[6:]))
    elif location=="source_format":
        coarse["lines"].append({"text":"\u00ad".join(damaged),"words":[]})
    elif location=="raw_hidden":
        raw+="\n"+"\u061c".join(damaged)
    else:
        raw+="\nرقم"+"\u00ad".join(damaged)+"ثان"
    with pytest.raises(ValueError,match="requires_review"):
        tracking.restore(raw,coarse,regions,groups)


def test_nonprinting_or_arabic_adjacency_cannot_hide_an_obsolete_target():
    _,_,_,_,slot=fixture()
    assert tracking.obsolete("رقم"+"\u061c".join(slot.replace(" ",""))+"ثان",slot)
    assert not tracking.obsolete("A"+slot.replace(" ","")+"B",slot)

def test_single_date_in_a_distant_column_cannot_supply_mailing_ownership():
    raw,coarse,regions,groups,_=fixture()
    coarse["lines"][0]["words"][0]["box"][0] += 125
    for scan in regions[0]["scans"]:
        scan["lines"][0]["words"][0]["box"][0] += 125*scan["dpi"]/144
    with pytest.raises(ValueError,match="requires_review"):
        tracking.restore(raw,coarse,regions,groups)
