"""Fictional occurrence-owned printed delimiters; no provider/private material."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_enclosure_authority as authority
from legalpdf_translate import ordinary_semantic_literal_authority as literal
from legalpdf_translate import ordinary_semantic_review as review
from tests.test_source_literal_authority import (RECIPE, INVENTORY, image, origins, correction, resolution, example)
from tests.test_ordinary_semantic_audit import page, token, PDF

VALUE = "2468013579"


def test_candidate_view_preserves_supported_whitespace_before_other_normalization():
    text = "  النص "+token("AB45")+".  "
    probe = review.audit.evaluate_output("```\n"+text+"\n```",review.audit.TargetLang.AR)
    assert probe.ok and probe.normalized_text != text
    assert authority._candidate_tokens(text) == authority._tokens(text)


def test_unsupported_square_view_cannot_normalize_visible_whitespace():
    text = "  النص [[[AB45]]].  "
    probe = review.audit.evaluate_output("```\n"+text+"\n```",review.audit.TargetLang.AR)
    assert probe.ok and not probe.normalized_text.endswith("  ")
    with pytest.raises(review.SemanticAuditError,match="wrapper_binding"):
        authority._candidate_tokens(text)


def carried(kind="round", *, extra=False):
    p,old,new = example("image")
    a,b = authority._PAIRS[kind]
    p = replace(p,primary_text="النص "+a+token(old)+b+".")
    if extra:
        p = replace(p,primary_text=p.primary_text+" "+token("AB45"))
    pages=[p]; registry=authority.freeze(pages,PDF,origins(pages))
    raw=correction(pages,[p.primary_text.replace(token(old),token(new))])
    eligible=authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    answer={"version":authority.RESPONSE,"literal_decisions":resolution(registry,eligible,[new])["decisions"],"enclosure_observations":[]}
    return pages,registry,raw,eligible,answer,old,new


@pytest.mark.parametrize("kind,a,b", [("square","[","]"),("round","(",")"),("curly","{","}")])
def test_unisolated_candidate_enclosure_uses_validated_view_without_rewriting_raw(kind,a,b):
    p = sample(1)
    pages = [p]
    registry = authority.freeze(pages,PDF,origins(pages))
    text = p.primary_text.replace(token(VALUE),a+token(VALUE)+b,1).replace("\u2066","").replace("\u2069","")
    raw = correction(pages,[text])
    before = deepcopy((pages,registry,raw))
    eligible = authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    assert len(eligible["enclosure_lookups"]) == 1
    assert eligible["canonical"] == json.loads(raw)
    assert eligible["rejected_proposal"]["pages"] == [{"page_number":1,"text":text}]
    answer = response(registry,eligible,[kind])
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    selected,_,_ = authority.validate(raw,pages,INVENTORY,RECIPE,context)
    assert selected[1] == context.projected_pages[0].primary_text
    assert context.enclosure_facts[0]["enclosure"] == kind
    assert (pages,registry,raw) == before


@pytest.mark.parametrize("damage", ["missing_pair","nested","migration","duplicate","changed_value","forbidden_control"])
def test_unisolated_candidate_view_cannot_relax_source_enclosure_or_sequence(damage):
    pages,registry,raw,eligible,answer,cert,context = prepared()
    text = context.projected_pages[0].primary_text.replace("\u2066","").replace("\u2069","")
    assert authority.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context)[0]
    if damage == "missing_pair": text = text.replace("[[["+VALUE+"]]]","[["+VALUE+"]]",1)
    elif damage == "nested": text = text.replace("[[["+VALUE+"]]]","[[[["+VALUE+"]]]]",1)
    elif damage == "migration":
        text = text.replace("[[["+VALUE+"]]]","[["+VALUE+"]]",1)
        index = text.rfind("[["+VALUE+"]]")
        text = text[:index]+"["+text[index:index+len(VALUE)+4]+"]"+text[index+len(VALUE)+4:]
    elif damage == "duplicate": text += " [[["+VALUE+"]]]"
    elif damage == "changed_value": text = text.replace("[[["+VALUE+"]]]","[[[OTHER9]]]",1)
    else: text += "\u202e"
    with pytest.raises(review.SemanticAuditError):
        authority.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context)


def test_unisolated_carried_square_pair_keeps_initial_sequence_transition_proof():
    pages,registry,raw,eligible,answer,old,new = carried("square",extra=True)
    text = json.loads(raw)["pages"][0]["corrected_text"].replace("\u2066","").replace("\u2069","")
    raw = correction(pages,[text])
    eligible = authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    assert authority.validate(raw,pages,INVENTORY,RECIPE,context)[0]
    answer["literal_decisions"][0]["exact_reading"] = "ZX1209"
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    authority.check_initial_sequence_replacement_eligibility(raw,pages,INVENTORY,registry,cert,context)
    with pytest.raises(review.SemanticAuditError,match="final_sequence_mismatch"):
        authority.validate(raw,pages,INVENTORY,RECIPE,context)


def certified_disagreement():
    pages,registry,raw,eligible,answer,old,new=carried(extra=True)
    answer["literal_decisions"][0]["exact_reading"]="ZX1209"
    cert=authority.certificate(review.audit._json(answer),pages,registry,eligible)
    return pages,registry,raw,cert,authority.project(pages,registry,cert),new


def test_initial_sequence_disagreement_only_routes_certified_slot_to_replacement():
    pages,registry,raw,cert,context,new=certified_disagreement()
    before=deepcopy((pages,registry,cert,context))
    with pytest.raises(review.SemanticAuditError,match="final_sequence_mismatch"):
        authority.validate(raw,pages,INVENTORY,RECIPE,context)
    authority.check_initial_sequence_replacement_eligibility(raw,pages,INVENTORY,registry,cert,context)
    authority.check_replacement_eligibility(raw,pages,INVENTORY,RECIPE,context)
    fixed=correction(pages,[context.projected_pages[0].primary_text])
    assert authority.validate(fixed,pages,INVENTORY,RECIPE,context)[0][1]==context.projected_pages[0].primary_text
    assert (pages,registry,cert,context)==before


@pytest.mark.parametrize("damage",["insert","drop","reorder","duplicate","uncertified","no_mismatch","no_change","context","certificate"])
def test_initial_sequence_transition_cannot_license_other_differences(damage):
    pages,registry,raw,cert,context,new=certified_disagreement()
    text=json.loads(raw)["pages"][0]["corrected_text"]
    if damage=="insert":text+=" "+token("EXTRA9")
    elif damage=="drop":text=text.replace(token("AB45"),"")
    elif damage=="reorder":text=token("AB45")+" "+text.replace(token("AB45"),"")
    elif damage=="duplicate":text=text.replace(token("AB45"),token(new))
    elif damage=="uncertified":text=text.replace(token("AB45"),token("CD67"))
    elif damage=="no_mismatch":text=context.projected_pages[0].primary_text
    elif damage=="context":context=replace(context,projected_pages=tuple(pages))
    elif damage=="certificate":cert["literal_certificate"]["changes"][0]["old_occurrence"]["primary_span"]["start"]+=1
    raw=correction(pages,[text],no_change=(1,) if damage=="no_change" else ())
    with pytest.raises(review.SemanticAuditError):
        authority.check_initial_sequence_replacement_eligibility(raw,pages,INVENTORY,registry,cert,context)


@pytest.mark.parametrize("kind", ["round","square","curly"])
def test_carried_original_whole_pair_certified_value_and_blind_request(kind):
    pages,registry,raw,eligible,answer,old,new=carried(kind)
    before=deepcopy((pages,registry))
    assert len(eligible["carried_original_pairs"])==1 and eligible["enclosure_lookups"]==[]
    request=authority.request(pages,RECIPE,registry,eligible)
    assert "carried_original_pairs" not in request["prompt_text"] and new not in request["prompt_text"]
    cert=authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context=authority.project(pages,registry,cert)
    assert context.enclosure_facts==() and len(context.source_facts)==1
    obligation=context.obligations[0]["occurrences"][0]
    assert obligation["basis"]=="unchanged_original_primary_pair_v1" and obligation["enclosure"]==kind
    assert authority.validate(raw,pages,INVENTORY,RECIPE,context)[0][1]==context.projected_pages[0].primary_text
    assert (pages,registry)==before


@pytest.mark.parametrize("damage", ["added","kind","insert","delete","repeat_old","repeat_new","reorder","control"])
def test_carried_pair_eligibility_never_authorizes_ambiguous_or_changed_pair(damage):
    pages,registry,raw,eligible,answer,old,new=carried(extra=True)
    p=pages[0];text=json.loads(raw)["pages"][0]["corrected_text"]
    if damage=="added":p=replace(p,primary_text=p.primary_text.replace("("+token(old)+")",token(old)))
    elif damage=="kind":text=text.replace("("+token(new)+")","["+token(new)+"]")
    elif damage=="insert":text+=" "+token("EXTRA1")
    elif damage=="delete":text=text.replace(token("AB45"),"")
    elif damage=="repeat_old":p=replace(p,primary_text=p.primary_text+" "+token(old));text+=" "+token(new)
    elif damage=="repeat_new":text=text.replace(token("AB45"),token(new))
    elif damage=="reorder":text=token("AB45")+" "+text.replace(token("AB45"),"")
    else:text+="\x00"
    pages=[p];registry=authority.freeze(pages,PDF,origins(pages))
    with pytest.raises(review.SemanticAuditError):authority.classify(correction(pages,[text]),pages,INVENTORY,RECIPE,registry)


@pytest.mark.parametrize("damage", ["missing_pair","wrong_pair","duplicate","migration","no_change","sequence"])
def test_carried_projected_occurrence_enforced_before_and_after_strict(damage):
    pages,registry,raw,eligible,answer,old,new=carried(extra=True)
    context=authority.project(pages,registry,authority.certificate(review.audit._json(answer),pages,registry,eligible))
    text=context.projected_pages[0].primary_text
    if damage=="missing_pair":text=text.replace("("+token(new)+")",token(new))
    elif damage=="wrong_pair":text=text.replace("("+token(new)+")","["+token(new)+"]")
    elif damage=="duplicate":text+=" ("+token(new)+")"
    elif damage=="migration":text=text.replace("("+token(new)+")",token(new)).replace(token("AB45"),"("+token("AB45")+")")
    elif damage=="sequence":text=text.replace(token("AB45"),token("DIFFERENT"))
    raw=correction(pages,[text],no_change=(1,) if damage=="no_change" else ())
    with pytest.raises(review.SemanticAuditError):authority.validate(raw,pages,INVENTORY,RECIPE,context)


@pytest.mark.parametrize("damage", ["missing","null","empty","extra","duplicate","kind","span","unknown"])
def test_carried_metadata_exact_binding(damage):
    pages,registry,raw,eligible,answer,old,new=carried()
    altered=deepcopy(eligible)
    if damage=="missing":altered.pop("carried_original_pairs")
    elif damage=="null":altered["carried_original_pairs"]=None
    elif damage=="empty":altered["carried_original_pairs"]=[]
    elif damage=="extra":altered["carried_original_pairs"][0]["source_image"]={}
    elif damage=="duplicate":altered["carried_original_pairs"]*=2
    elif damage=="kind":altered["carried_original_pairs"][0]["enclosure"]="square"
    elif damage=="span":altered["carried_original_pairs"][0]["old_occurrence"]["primary_span"]["start"]+=1
    else:altered["carried_original_pairs"][0]["old_occurrence"]["occurrence_id"]="UNKNOWN"
    with pytest.raises(review.SemanticAuditError):authority.certificate(review.audit._json(answer),pages,registry,altered)
    cert=authority.certificate(review.audit._json(answer),pages,registry,eligible)
    cert["carried_original_pairs"][0]["enclosure"]="square"
    with pytest.raises(review.SemanticAuditError):authority.project(pages,registry,cert)


def test_historical_unpaired_and_unsupported_original_pair_removal_has_no_carry_metadata():
    pages,registry,raw,eligible,answer,old,new=carried()
    text=json.loads(raw)["pages"][0]["corrected_text"].replace("("+token(new)+")",token(new))
    eligible=authority.classify(correction(pages,[text]),pages,INVENTORY,RECIPE,registry)
    assert "carried_original_pairs" not in eligible
    cert=authority.certificate(review.audit._json(answer),pages,registry,eligible)
    assert "carried_original_pairs" not in cert
    context=authority.project(pages,registry,cert)
    assert context.obligations==() and context.enclosure_facts==()
    assert authority.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context)[0][1]==text


@pytest.mark.parametrize("index", [0,1])
def test_genuine_prechange_larger_prose_and_pair_removal_success_bytes_exact(index):
    fixture=json.loads((Path(__file__).parent/"fixtures/carried_pair_prechange_success.json").read_bytes())
    assert fixture["fictional_only"] and fixture["baseline_runtime_sha256"]=="9f9bb3ce283c02e66c70c3a55bad9fcd5e8c16891ce1ee9e988b6d9b582e1210"
    case=fixture["cases"][index];pages=[review.SemanticAuditPage(**p) for p in case["pages"]]
    recipe=review.SemanticAuditRecipe(**case["recipe"])
    eligible=authority.classify(case["raw"],pages,INVENTORY,recipe,case["registry"])
    assert review.audit._json(eligible)==review.audit._json(case["eligibility"])
    assert review.audit._json(authority.request(pages,recipe,case["registry"],eligible))==review.audit._json(case["resolver_request"])
    cert=authority.certificate(review.audit._json(case["answer"]),pages,case["registry"],eligible)
    assert cert==case["certificate"] and "carried_original_pairs" not in cert
    context=authority.project(pages,case["registry"],cert)
    assert context.evidence==case["context"] and context.obligations==()
    selected=authority.validate(case["raw"],pages,INVENTORY,recipe,context)[0]
    assert {str(k):v for k,v in selected.items()}==case["selected"]


@pytest.mark.parametrize("kind", ["nested","larger","unmatched"])
def test_invalid_new_shape_never_acquires_a_carried_pair_license(kind):
    pages,registry,raw,eligible,answer,old,new=carried()
    text=json.loads(raw)["pages"][0]["corrected_text"]
    if kind=="nested":text="("+text+")"
    elif kind=="larger":text=text.replace("("+token(new)+")","(نص "+token(new)+")")
    else:text=text.replace("("+token(new)+")","("+token(new))
    eligible=authority.classify(correction(pages,[text]),pages,INVENTORY,RECIPE,registry)
    assert "carried_original_pairs" not in eligible
    cert=authority.certificate(review.audit._json(answer),pages,registry,eligible)
    assert authority.project(pages,registry,cert).obligations==()


def test_adjacent_certified_substitutions_project_carried_exact_old_span():
    p,old,new=example("image")
    p=replace(p,primary_text="النص "+token("AY99")+" ("+token(old)+").")
    pages=[p];registry=authority.freeze(pages,PDF,origins(pages))
    text=p.primary_text.replace(token("AY99"),token("BY12345")).replace(token(old),token(new))
    raw=correction(pages,[text]);eligible=authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    answer={"version":authority.RESPONSE,"literal_decisions":resolution(registry,eligible,["BY12345",new])["decisions"],"enclosure_observations":[]}
    cert=authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context=authority.project(pages,registry,cert)
    assert authority.validate(raw,pages,INVENTORY,RECIPE,context)[0][1]==text


def sample(repeats=2):
    text = "المرجع " + token(VALUE) + " ثم الرمز " + token("AB45")
    if repeats > 1:
        text += " ثم المرجع " + token(VALUE)
    for _ in range(repeats-2):
        text += " ثم " + token(VALUE)
    return page(1, source_text="Reference " + VALUE, original_source_text="Reference " + VALUE,
        primary_text=text+".", expected_ar_tokens=(VALUE,), image_data_url=image())


def prepared(p=None, kinds=None, extra_pages=()):
    p = p or sample()
    pages = [p,*extra_pages]
    registry = authority.freeze(pages, PDF, origins(pages))
    text = p.primary_text.replace(token(VALUE), "["+token(VALUE)+"]", 1)
    raw = correction(pages, [text]+[p.primary_text for p in extra_pages])
    eligible = authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    kinds = kinds or ["square"]+["none"]*(len(eligible["enclosure_lookups"])-1)
    answer = response(registry,eligible,kinds)
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    return pages,registry,raw,eligible,answer,cert,context


def response(registry, eligible, kinds):
    return {"version": authority.RESPONSE, "literal_decisions": [], "enclosure_observations": [
        {"occurrence_id": old["occurrence_id"], "exact_reading": old["value"], "ownership": "owned",
            "enclosure": kind, "source_image": {"page": old["page"],
                "image_sha256": next(p for p in registry["pages"] if p["page"] == old["page"])["image"]["sha256"],
                "bbox": [1+i*30,50,20+i*30,70]}}
        for i,(old,kind) in enumerate(zip(eligible["enclosure_lookups"],kinds))]}


def test_same_value_occurrences_independent_projection_and_required_source_unchanged():
    pages,registry,raw,eligible,answer,cert,context = prepared()
    before = deepcopy((pages,registry))
    selected,_,_ = authority.validate(raw,pages,INVENTORY,RECIPE,context)
    assert selected[1] == context.projected_pages[0].primary_text
    assert len(eligible["enclosure_lookups"]) == 2
    assert [o["enclosure"] for o in context.enclosure_facts] == ["square","none"]
    assert context.source_facts == ()
    effective = context.projected_pages[0]
    assert (effective.source_text,effective.original_source_text,effective.expected_ar_tokens) == (
        pages[0].source_text,pages[0].original_source_text,pages[0].expected_ar_tokens)
    assert (pages,registry) == before


@pytest.mark.parametrize("defect", ["migration","omission","duplicate","round","nested","prose","multiple","unmatched","reorder","unwrapped"])
def test_final_occurrence_obligations_reject_counter_credit_and_shape(defect):
    pages,registry,raw,eligible,answer,cert,context = prepared()
    text = json.loads(raw)["pages"][0]["corrected_text"]
    if defect == "migration":
        text = text.replace("["+token(VALUE)+"]",token(VALUE),1)
        index = text.rfind(token(VALUE)); text = text[:index]+"["+text[index:index+len(token(VALUE))]+"]"+text[index+len(token(VALUE)):]
    elif defect == "omission": text = text.replace("["+token(VALUE)+"]",token(VALUE),1)
    elif defect == "duplicate": text += " ["+token(VALUE)+"]"
    elif defect == "round": text = text.replace("["+token(VALUE)+"]","("+token(VALUE)+")")
    elif defect == "nested": text = text.replace("["+token(VALUE)+"]","[["+token(VALUE)+"]]")
    elif defect == "prose": text = text.replace("["+token(VALUE)+"]","[المرجع "+token(VALUE)+"]")
    elif defect == "multiple": text = text.replace("] ثم الرمز "," ثم الرمز ").replace(token("AB45"),token("AB45")+"]")
    elif defect == "unmatched": text = text.replace("["+token(VALUE)+"]","["+token(VALUE))
    elif defect == "reorder": text = text.replace(token("AB45"),token("DIFFERENT"))
    else: text = text.replace(token(VALUE),VALUE)
    with pytest.raises(review.SemanticAuditError):
        authority.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context)


def test_actual_original_no_change_cannot_inherit_projected_pair():
    pages,registry,raw,eligible,answer,cert,context = prepared()
    with pytest.raises(review.SemanticAuditError,match="enclosure_authority_final_enclosure_mismatch"):
        authority.validate(correction(pages,[""],no_change=(1,)),pages,INVENTORY,RECIPE,context)


@pytest.mark.parametrize("kinds", [("round","none"),("curly","none"),("none","square"),("none","none")])
def test_observation_supersedes_proposed_kind_and_preserves_none(kinds):
    pages,registry,raw,eligible,answer,cert,context = prepared(kinds=list(kinds))
    text = context.projected_pages[0].primary_text
    assert authority.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context)[0][1] == text


def test_resolver_blind_to_candidate_enclosure_kind_context_and_new_values():
    pages,registry,raw,eligible,answer,cert,context = prepared()
    request = authority.request(pages,replace(RECIPE,context_text="PRIVATE_PREF"),registry,eligible)
    data = json.loads(request["prompt_text"])
    assert len(data["old_enclosure_lookups"]) == 2
    assert "enclosure" not in review.audit._json(data["old_enclosure_lookups"])
    assert not set(data) & {"candidate_pages","primary_pages","rejected_proposal","source_inventory","context_text","prior_findings"}
    assert "PRIVATE_PREF" not in review.audit._json(request)
    assert all(set(row) == {"occurrence_id","page","value","primary_span"} for row in data["old_enclosure_lookups"])


@pytest.mark.parametrize("defect", ["reuse","wrong_page","wrong_hash","coordinates","reading","unresolved","missing","duplicate","extra_raw_span","lookup_span","lookup_omission"])
def test_closed_observations_ownership_coverage_and_projection_tamper(defect):
    pages,registry,raw,eligible,answer,cert,context = prepared()
    answer = deepcopy(answer); eligible = deepcopy(eligible)
    row = answer["enclosure_observations"][0]
    if defect == "reuse": answer["enclosure_observations"][1]["source_image"] = deepcopy(row["source_image"])
    elif defect == "wrong_page": row["source_image"]["page"] = 2
    elif defect == "wrong_hash": row["source_image"]["image_sha256"] = "0"*64
    elif defect == "coordinates": row["source_image"]["bbox"] = [0,0,1000,1000]
    elif defect == "reading": row["exact_reading"] += "1"
    elif defect == "unresolved": row["ownership"] = "unresolved"
    elif defect == "missing": answer["enclosure_observations"].pop()
    elif defect == "duplicate": answer["enclosure_observations"][1] = deepcopy(row)
    elif defect == "extra_raw_span": row["raw_span"] = None
    elif defect == "lookup_span": eligible["enclosure_lookups"][0]["primary_span"]["start"] += 1
    else:
        eligible["enclosure_lookups"].pop(); answer["enclosure_observations"].pop()
    with pytest.raises(review.SemanticAuditError):
        authority.certificate(review.audit._json(answer),pages,registry,eligible)
    bad = deepcopy(cert)
    bad["enclosure_observations"][0]["old_occurrence"]["primary_span"]["end"] -= 1
    with pytest.raises(review.SemanticAuditError): authority.project(pages,registry,bad)


def test_duplicate_neighbor_signatures_fail_before_candidate_acceptance():
    p = sample(5)
    registry = authority.freeze([p],PDF,origins([p]))
    raw = correction([p],[p.primary_text.replace(token(VALUE),"["+token(VALUE)+"]",1)])
    eligible = authority.classify(raw,[p],INVENTORY,RECIPE,registry)
    answer = response(registry,eligible,["square"]+["none"]*4)
    cert = authority.certificate(review.audit._json(answer),[p],registry,eligible)
    with pytest.raises(review.SemanticAuditError,match="ambiguous_neighborhood"):
        authority.project([p],registry,cert)


@pytest.mark.parametrize("defect", ["control","language","wrapper","coverage"])
def test_enclosure_failure_never_hides_later_hard_gate(defect):
    p,q = sample(),replace(sample(),page_number=2)
    registry = authority.freeze([p,q],PDF,origins([p,q]))
    raw = json.loads(correction([p,q],[p.primary_text.replace(token(VALUE),"["+token(VALUE)+"]",1),q.primary_text]))
    if defect == "control": raw["pages"][1]["corrected_text"] += "\x00"
    elif defect == "language": raw["pages"][1]["corrected_text"] = "A fictional English language document."
    elif defect == "wrapper": raw["pages"][1]["corrected_text"] += " [[broken[[x]]]]"
    else: raw["claim_coverage"] = []
    with pytest.raises(review.SemanticAuditError): authority.classify(review.audit._json(raw),[p,q],INVENTORY,RECIPE,registry)


@pytest.mark.parametrize("defect", ["off","no_image","no_origin","capacity"])
def test_pure_enclosure_requires_available_original_source_provenance(defect):
    p = sample(); recipe = RECIPE; source_origins = origins([p])
    if defect == "off": recipe = replace(recipe,configured_image_mode="off")
    elif defect == "no_image": p = replace(p,image_data_url=None)
    elif defect == "no_origin": source_origins[0]["kind"] = "unknown"
    registry = authority.freeze([p],PDF,source_origins)
    if defect == "capacity":
        # The real capacity state is covered by native long-value workflow tests.
        registry = {**registry,"availability":"ineligible_capacity"}
    raw = correction([p],[p.primary_text.replace(token(VALUE),"["+token(VALUE)+"]",1)])
    with pytest.raises(review.SemanticAuditError): authority.classify(raw,[p],INVENTORY,recipe,registry)


def test_mixed_value_and_enclosure_changes_leave_enclosure_source_and_required_unchanged():
    p = sample(); q,old,new = example("required",2)
    pages = [p,q]; registry = authority.freeze(pages,PDF,origins(pages))
    raw = correction(pages,[p.primary_text.replace(token(VALUE),"["+token(VALUE)+"]",1),q.primary_text.replace(old,new)])
    eligible = authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    answer = response(registry,eligible,["square","none"])
    answer["literal_decisions"] = resolution(registry,eligible,[new])["decisions"]
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    assert authority.validate(raw,pages,INVENTORY,RECIPE,context)[0][2] == context.projected_pages[1].primary_text
    assert context.projected_pages[0].source_text == p.source_text
    assert context.projected_pages[0].original_source_text == p.original_source_text
    assert context.projected_pages[0].expected_ar_tokens == p.expected_ar_tokens


def test_affected_page_unrelated_grouping_is_conservatively_rejected_but_v3_accepts():
    p = sample()
    p = replace(p,source_text=p.source_text+" 1 / 3",original_source_text=p.original_source_text+" 1 / 3",
        primary_text=p.primary_text+" "+token("1")+" / "+token("3"),expected_ar_tokens=(VALUE,"1","3"))
    pages,registry,raw,eligible,answer,cert,context = prepared(p)
    text = context.projected_pages[0].primary_text.replace(token("1")+" / "+token("3"),token("1 / 3"))
    with pytest.raises(review.SemanticAuditError,match="final_sequence_mismatch"):
        authority.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context)
    no_enclosure = text.replace("["+token(VALUE)+"]",token(VALUE))
    assert literal.validate(correction(pages,[no_enclosure]),pages,INVENTORY,RECIPE)[0]


def test_existing_same_value_pair_on_unchanged_page_does_not_activate_authority():
    p = sample()
    p = replace(p,primary_text=p.primary_text.replace(token(VALUE),"["+token(VALUE)+"]",1))
    registry = authority.freeze([p],PDF,origins([p]))
    raw = correction([p],[""],no_change=(1,))
    assert authority.classify(raw,[p],INVENTORY,RECIPE,registry) is None
    assert authority.validate(raw,[p],INVENTORY,RECIPE)[0][1] == p.primary_text


def test_same_occurrence_bare_value_replacement_and_new_enclosure_outside_scope():
    p,old,new = example("image")
    registry = authority.freeze([p],PDF,origins([p]))
    raw = correction([p],[p.primary_text.replace(token(old),"["+token(new)+"]")])
    with pytest.raises(review.SemanticAuditError,match="same_occurrence_value_and_enclosure"):
        authority.classify(raw,[p],INVENTORY,RECIPE,registry)


def test_ordinary_no_enclosure_conflict_keeps_v3_same_and_cross_page_grouping():
    # Existing V1 adapter remains unchanged; V4's no-enclosure layer must preserve
    # both accepted shapes through its own certificate/context too.
    first,old,new = example("image")
    ratio = "النسبة "+token("1")+" / "+token("3")
    second = page(2,source_text="[[1]] / [[3]]",source_text_kind="pretokenized",original_source_text="1 / 3",
        expected_ar_tokens=("1","3"),primary_text=ratio,image_data_url=image())
    pages = [first,second]; registry = authority.freeze(pages,PDF,origins(pages))
    raw = correction(pages,[first.primary_text.replace(old,new),"النسبة "+token("1 / 3")])
    eligible = authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    assert eligible["enclosure_lookups"] == []
    answer = response(registry,eligible,[])
    answer["literal_decisions"] = resolution(registry,eligible,[new])["decisions"]
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    assert authority.validate(raw,pages,INVENTORY,RECIPE,context)[0]


@pytest.mark.parametrize("outer", [("[","]"),("(",")"),("{","}")])
def test_preexisting_larger_prose_enclosure_cannot_own_new_immediate_pair(outer):
    a,b = outer
    p = sample(1)
    p = replace(p,primary_text=a+"السجل "+p.primary_text+" تابع"+b)
    registry = authority.freeze([p],PDF,origins([p]))
    raw = correction([p],[p.primary_text.replace(token(VALUE),"["+token(VALUE)+"]",1)])
    with pytest.raises(review.SemanticAuditError,match="nested_or_larger_enclosure"):
        authority.classify(raw,[p],INVENTORY,RECIPE,registry)


@pytest.mark.parametrize("outer", [("[","]"),("(",")"),("{","}")])
def test_larger_prose_enclosure_around_none_occurrence_cannot_use_other_pair_credit(outer):
    pages,registry,raw,eligible,answer,cert,context = prepared()
    text = context.projected_pages[0].primary_text
    last = text.rfind(token(VALUE)); a,b = outer
    text = text[:last]+a+"السجل "+token(VALUE)+" تابع"+b+text[last+len(token(VALUE)):]
    with pytest.raises(review.SemanticAuditError,match="final_enclosure_mismatch"):
        authority.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context)


def test_independent_adjacent_pairs_and_delimiters_inside_other_literal_are_not_nesting():
    p = sample()
    p = replace(p,primary_text=p.primary_text+" (بيان) "+token("A(B)C"))
    pages,registry,raw,eligible,answer,cert,context = prepared(p)
    assert authority.validate(raw,pages,INVENTORY,RECIPE,context)[0]
    text = context.projected_pages[0].primary_text.replace("["+token(VALUE)+"]", "(بيان) ["+token(VALUE)+"] (آخر)",1)
    # These unrelated prose pairs may independently fail strict quality; the
    # ownership parser itself must retain the exact same occurrence shapes.
    view,tokens = authority._tokens(text)
    assert authority._shapes(view,tokens)[0] == "square"


@pytest.mark.parametrize("outer", [("[","]"),("(",")")])
def test_unchanged_old_nested_enclosure_with_unrelated_prose_edit_keeps_strict_normal_path(outer):
    a,b = outer
    p = sample(1)
    text = a+"بيان ["+token(VALUE)+"] آخر"+b+" النص "+token("AB45")
    p = replace(p,primary_text=text)
    registry = authority.freeze([p],PDF,origins([p]))
    raw = correction([p],[text.replace("النص","المحتوى")])
    assert literal.validate(raw,[p],INVENTORY,RECIPE)[0]
    assert authority.classify(raw,[p],INVENTORY,RECIPE,registry) is None
    assert authority.validate(raw,[p],INVENTORY,RECIPE)[0]


def test_existing_valid_pair_migration_between_duplicate_neighborhoods_triggers_but_cannot_authorize():
    original = sample(5)
    matches = list(literal._TOKEN.finditer(original.primary_text))
    values = [m for m in matches if m[1] == VALUE]
    def wrap(index):
        match = values[index]
        return original.primary_text[:match.start()]+"["+match[0]+"]"+original.primary_text[match.end():]
    p = replace(original,primary_text=wrap(2))
    raw = correction([p],[wrap(3)])
    assert literal.validate(raw,[p],INVENTORY,RECIPE)[0]
    registry = authority.freeze([p],PDF,origins([p]))
    eligible = authority.classify(raw,[p],INVENTORY,RECIPE,registry)
    assert eligible is not None and len(eligible["enclosure_lookups"]) == 5
    answer = response(registry,eligible,["none","none","square","none","none"])
    cert = authority.certificate(review.audit._json(answer),[p],registry,eligible)
    with pytest.raises(review.SemanticAuditError,match="ambiguous_neighborhood"):
        authority.project([p],registry,cert)


@pytest.mark.parametrize("kind,a,b", [("square","[","]"),("round","(",")"),("curly","{","}")])
def test_existing_unambiguous_pair_source_ownership_blocks_migration_and_retains_actual_no_change(kind,a,b):
    p = sample()
    original = p.primary_text.replace(token(VALUE),a+token(VALUE)+b,1)
    moved = p.primary_text
    index = moved.rfind(token(VALUE))
    moved = moved[:index]+a+token(VALUE)+b+moved[index+len(token(VALUE)):]
    p = replace(p,primary_text=original)
    registry = authority.freeze([p],PDF,origins([p])); raw = correction([p],[moved])
    assert literal.validate(raw,[p],INVENTORY,RECIPE)[0]
    eligible = authority.classify(raw,[p],INVENTORY,RECIPE,registry)
    assert len(eligible["enclosure_lookups"]) == 2
    answer = response(registry,eligible,[kind,"none"])
    cert = authority.certificate(review.audit._json(answer),[p],registry,eligible)
    context = authority.project([p],registry,cert)
    assert context.projected_pages[0].primary_text == original
    with pytest.raises(review.SemanticAuditError,match="final_enclosure_mismatch"):
        authority.validate(raw,[p],INVENTORY,RECIPE,context)
    assert authority.validate(correction([p],[""],no_change=(1,)),[p],INVENTORY,RECIPE,context)[0][1] == original


def test_unchanged_existing_pair_in_ambiguous_repeats_with_unrelated_prose_edit_does_not_activate():
    p = sample(5)
    matches = [m for m in literal._TOKEN.finditer(p.primary_text) if m[1] == VALUE]
    match = matches[2]
    text = p.primary_text[:match.start()]+"["+match[0]+"]"+p.primary_text[match.end():]
    p = replace(p,primary_text=text)
    raw = correction([p],[text.replace("المرجع","الإشارة")])
    registry = authority.freeze([p],PDF,origins([p]))
    assert literal.validate(raw,[p],INVENTORY,RECIPE)[0]
    assert authority.classify(raw,[p],INVENTORY,RECIPE,registry) is None
    assert authority.validate(raw,[p],INVENTORY,RECIPE)[0]
