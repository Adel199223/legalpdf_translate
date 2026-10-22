"""Fictional source assertions and adversaries; no provider or private content."""
import base64
from copy import deepcopy
from dataclasses import replace
from io import BytesIO
import json

from PIL import Image
import pytest

from legalpdf_translate import ordinary_semantic_literal_authority as authority
from legalpdf_translate import ordinary_semantic_review as review
from tests.test_ordinary_semantic_audit import page, token, PDF

RECIPE = review.SemanticAuditRecipe("gpt-6-astra", "high")
INVENTORY = {"claims": [{"claim_id": "fictional"}]}


def image():
    buffer = BytesIO()
    Image.new("RGB", (200, 120), "white").save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()


def example(kind="required", number=1):
    old, new = {"required": ("https://portal-old.example/a", "https://authority-real.example/q"),
        "additional": ("Rua Ficcao, 4A", "Rua Ficcao, 4B"),
        "image": ("ZX1207", "ZX1208")}[kind]
    raw = "Portal: " + old if kind != "image" else "A fictional notice."
    p = page(number, source_text=("Portal: [["+old+"]]" if kind != "image" else raw),
        source_text_kind="pretokenized", original_source_text=raw,
        expected_ar_tokens=(old,) if kind == "required" else (), image_data_url=image(),
        primary_text="النص " + token(old) + ".")
    return p, old, new


def origins(pages, kind="ocr_v1"):
    return [{"version": "semantic_source_origin_v1", "page": p.page_number,
        "kind": kind, "provenance": {"source_route": "ocr"}} for p in pages]


def correction(pages, texts, *, no_change=()):
    return review.audit._json({"version": review.CORRECTION_VERSION,
        "pages": [{"page_number": p.page_number, "status": "no_change" if p.page_number in no_change else "corrected",
            "corrected_text": "" if p.page_number in no_change else text,
            "reason_codes": [] if p.page_number in no_change else ["material_meaning"]}
            for p,text in zip(pages,texts)],
        "claim_coverage": [{"claim_id": "fictional", "status": "preserved"}]})


def resolution(registry, eligibility, values):
    rows = []
    for i,(old,value) in enumerate(zip(eligibility["lookups"],values)):
        frozen = next(p for p in registry["pages"] if p["page"] == old["page"])
        raw = old["raw_candidates"][0] if old["raw_candidates"] else None
        rows.append({"occurrence_id": old["occurrence_id"], "status": "replace", "exact_reading": value,
            "ownership": "owned", "raw_span": {"start": raw["start"], "end": raw["end"]} if raw else None,
            "source_image": {"page": old["page"], "image_sha256": frozen["image"]["sha256"],
                "bbox": [1+i*30,1,20+i*30,20]}})
    return {"version": "source_literal_resolution_v1", "decisions": rows}


def prepared(kinds=("required",)):
    samples = [example(kind, i+1) for i,kind in enumerate(kinds)]
    pages = [row[0] for row in samples]
    registry = authority.freeze(pages, PDF, origins(pages))
    raw = correction(pages, [p.primary_text.replace(token(old),token(new)) for p,old,new in samples])
    eligible = authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    answer = resolution(registry,eligible,[r[2] for r in samples])
    return pages,registry,raw,eligible,answer


@pytest.mark.parametrize("kinds", [("required",),("additional",),("image",),("required","additional","image")])
def test_exact_three_conflict_classes_and_mixed_pages_keep_originals(kinds):
    pages,registry,raw,eligible,answer = prepared(kinds)
    before = deepcopy((pages,registry))
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    selected,_,_ = authority.validate(raw,pages,INVENTORY,RECIPE,context)
    assert (pages,registry) == before
    for p,projection,kind in zip(pages,context.projected_pages,kinds):
        old,new = example(kind)[1:]
        assert selected[p.page_number] == projection.primary_text
        assert token(new) in selected[p.page_number]
        assert new in projection.expected_ar_tokens
        if kind == "image":
            assert projection.source_text == p.source_text
            assert projection.original_source_text == p.original_source_text
            assert context.source_facts[-1]["qualification"] == "image_supported_literal_absent_from_raw_ocr"
        else:
            assert projection.original_source_text == p.original_source_text.replace(old,new)
            assert projection.source_text == p.source_text.replace(old,new)


def test_resolver_is_blind_to_candidate_inventory_preference_and_new_value():
    pages,registry,raw,eligible,answer = prepared(("image",))
    req = authority.request(pages,replace(RECIPE,context_text="PRIVATE_PREFERENCE_SENTINEL"),registry,eligible)
    payload = json.loads(req["prompt_text"])
    assert set(payload) == {"stage","protocol","registry_sha256","pdf_sha256","source_pages","old_occurrence_lookups"}
    assert "ZX1207" in req["prompt_text"] and "ZX1208" not in req["prompt_text"]
    assert "PRIVATE_PREFERENCE_SENTINEL" not in review.audit._json(req)
    assert all(k not in payload for k in ("rejected_proposal","source_inventory","prior_findings","context_text","candidate_pages"))
    assert payload["old_occurrence_lookups"][0]["primary_span"]["context_before"]
    assert req["image_data_urls"] == tuple(p.image_data_url for p in pages)


@pytest.mark.parametrize("defect", ["wrapper","control","language","page_shape","claim_shape","unresolved"])
def test_first_literal_failure_cannot_hide_later_hard_failure(defect):
    pages,registry,raw,eligible,answer = prepared(("required","image"))
    data = json.loads(raw)
    row = data["pages"][1]
    if defect == "wrapper": row["corrected_text"] = "نص [[broken[[nested]]]]"
    elif defect == "control": row["corrected_text"] += "\x00"
    elif defect == "language": row["corrected_text"] = "O documento apresenta todos os factos do processo."
    elif defect == "page_shape": row["unknown"] = True
    elif defect == "claim_shape": data["claim_coverage"].append(data["claim_coverage"][0])
    else: row["status"] = "unresolved"
    with pytest.raises(review.SemanticAuditError):
        authority.classify(review.audit._json(data),pages,INVENTORY,RECIPE,registry)


@pytest.mark.parametrize("defect", ["no_image","image_off","no_origin","pdf_text","omission","extra","partial_duplicate"])
def test_ineligible_inputs_do_not_license_a_resolver(defect):
    p,old,new = example()
    recipe = RECIPE
    text = p.primary_text.replace(old,new)
    origin = "ocr_v1"
    if defect == "no_image": p = replace(p,image_data_url=None)
    elif defect == "image_off":
        p = replace(p,image_data_url=None,visual_coverage="text_only_configured_image_off")
        recipe = replace(recipe,configured_image_mode="off")
    elif defect == "no_origin": origin = "unknown"
    elif defect == "pdf_text": origin = "pdf_extraction_v1"
    elif defect == "omission": text = "النص."
    elif defect == "extra": text += token("UNOWNED")
    else:
        p = replace(p,primary_text=p.primary_text+token(old),expected_ar_tokens=(old,old))
        text = text+token(old)
    registry = authority.freeze([p],PDF,origins([p],origin))
    with pytest.raises(review.SemanticAuditError):
        authority.classify(correction([p],[text]),[p],INVENTORY,recipe,registry)


@pytest.mark.parametrize("defect", ["missing","extra","duplicate_id","cross_page","image_hash","bounds","overlap",
    "raw_offset","raw_bool","raw_null","ownership","unreadable","printed_typo","unknown_key","new_control","new_partial"])
def test_closed_certificate_schema_ownership_and_abstention(defect):
    pages,registry,raw,eligible,answer = prepared(("required","additional"))
    row = answer["decisions"][0]
    if defect == "missing": answer["decisions"].pop()
    elif defect == "extra": answer["decisions"].append(deepcopy(row))
    elif defect == "duplicate_id": answer["decisions"][1]["occurrence_id"] = row["occurrence_id"]
    elif defect == "cross_page": row["source_image"]["page"] = 2
    elif defect == "image_hash": row["source_image"]["image_sha256"] = "0"*64
    elif defect == "bounds": row["source_image"]["bbox"] = [0,0,201,120]
    elif defect == "overlap":
        # Both old values now claim one page and source region.
        answer["decisions"][1]["source_image"] = deepcopy(row["source_image"])
    elif defect == "raw_offset": row["raw_span"]["start"] += 1
    elif defect == "raw_bool": row["raw_span"]["start"] = True
    elif defect == "raw_null": row["raw_span"] = None
    elif defect == "ownership": row["ownership"] = "unresolved"
    elif defect == "unreadable": row["status"] = "unresolved"
    elif defect == "printed_typo":
        for item,old in zip(answer["decisions"],eligible["lookups"]):
            item["status"] = "unchanged"; item["exact_reading"] = old["value"]
    elif defect == "unknown_key": row["reason"] = "Never a certificate."
    elif defect == "new_control": row["exact_reading"] += "\u200b"
    else: row["exact_reading"] = ""
    with pytest.raises(review.SemanticAuditError):
        authority.certificate(review.audit._json(answer),pages,registry,eligible)


def test_image_only_no_synthetic_raw_ownership_and_false_no_change_rejected():
    pages,registry,raw,eligible,answer = prepared(("image",))
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    with pytest.raises(review.SemanticAuditError):
        authority.validate(correction(pages,[""],no_change=(1,)),pages,INVENTORY,RECIPE,context)
    answer["decisions"][0]["raw_span"] = {"start":0,"end":1}
    with pytest.raises(review.SemanticAuditError):
        authority.certificate(review.audit._json(answer),pages,registry,eligible)


@pytest.mark.parametrize("damage", ["omit","old","unlicensed_literal","bracket","required_count"])
def test_projection_preserves_all_unlicensed_guards(damage):
    pages,registry,raw,eligible,answer = prepared(("required",))
    p = pages[0]
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    text = context.projected_pages[0].primary_text
    new = answer["decisions"][0]["exact_reading"]
    if damage == "omit": text = "النص."
    elif damage == "old": text = p.primary_text
    elif damage == "unlicensed_literal":
        p = replace(p,primary_text=p.primary_text+token("EXTRA"))
        # The original extra occurrence remains an obligation in the projection.
        pages,registry,raw,eligible,answer = prepared(("required",))
        pages[0] = p
        registry = authority.freeze(pages,PDF,origins(pages))
        raw = correction(pages,[text+token("EXTRA")])
        eligible = authority.classify(raw,pages,INVENTORY,RECIPE,registry)
        answer = resolution(registry,eligible,[new])
        context = authority.project(pages,registry,authority.certificate(review.audit._json(answer),pages,registry,eligible))
    elif damage == "bracket": text = "("+text+")"
    else: text += token(new)
    with pytest.raises(review.SemanticAuditError):
        authority.validate(correction(pages,[text]),pages,INVENTORY,RECIPE,context)


def test_strict_valid_addition_and_unchanged_page_do_not_create_authority_lookups():
    p,_,_ = example("image")
    text = p.primary_text+" "+token("VISUAL")
    registry = authority.freeze([p],PDF,origins([p]))
    assert authority.classify(correction([p],[text]),[p],INVENTORY,RECIPE,registry) is None
    assert authority.validate(correction([p],[text]),[p],INVENTORY,RECIPE)[0][1] == text
    # A small ordinary repeated-token page must not build quadratic evidence.
    repeated = replace(p,original_source_text=" ".join(["12"]*40),source_text=" ".join(["[[12]]"]*40),
        primary_text=" ".join([token("12")]*40),expected_ar_tokens=tuple(["12"]*40))
    frozen = authority.freeze([repeated],PDF,origins([repeated]))
    assert len(frozen["pages"][0]["source_values"]) == 1
    assert len(review.audit._json(frozen)) < 80_000
    assert authority.classify(correction([repeated],[""],no_change=(1,)),[repeated],INVENTORY,RECIPE,frozen) is None


@pytest.mark.parametrize("kind", ["inside_wrapper","inside_field","raw_source_mismatch"])
def test_substrings_and_same_count_source_reordering_cannot_be_certified(kind):
    p = page(source_text="Código [[ABC123]]",source_text_kind="pretokenized",
        original_source_text="Código ABC123",expected_ar_tokens=("ABC123",),image_data_url=image(),
        primary_text="النص "+token("ABC123")+" "+token("ABC"))
    old,new = "ABC","ABD"
    if kind == "inside_field":
        old,new = "Ficcao","Modelo"
        p = replace(p,source_text="Morada: Rua Ficcao, 4",original_source_text="Morada: Rua Ficcao, 4",
            expected_ar_tokens=(),primary_text="العنوان "+token(old))
    elif kind == "raw_source_mismatch":
        old,new = "XYZ","NEW"
        p = replace(p,source_text="Other [[XYZ]]",original_source_text="XYZ Other",expected_ar_tokens=(),
            primary_text="نص "+token(old))
    registry = authority.freeze([p],PDF,origins([p]))
    raw = correction([p],[p.primary_text.replace(token(old),token(new))])
    eligible = authority.classify(raw,[p],INVENTORY,RECIPE,registry)
    answer = resolution(registry,eligible,[new])
    with pytest.raises(review.SemanticAuditError,match="raw_ownership"):
        authority.certificate(review.audit._json(answer),[p],registry,eligible)


def test_duplicate_source_occurrence_requires_distinct_allocation_and_preserves_new_preexisting_counts():
    p,old,new = example("required")
    p = replace(p,source_text=p.source_text+" [["+old+"]]",original_source_text=p.original_source_text+" "+old,
        primary_text=p.primary_text+" "+token(old),expected_ar_tokens=(old,old))
    registry = authority.freeze([p],PDF,origins([p]))
    raw = correction([p],[p.primary_text.replace(old,new)])
    eligible = authority.classify(raw,[p],INVENTORY,RECIPE,registry)
    answer = resolution(registry,eligible,[new,new])
    with pytest.raises(review.SemanticAuditError,match="source_occurrence_reused"):
        authority.certificate(review.audit._json(answer),[p],registry,eligible)
    witness = eligible["lookups"][1]["raw_candidates"][1]
    answer["decisions"][1]["raw_span"] = {k:witness[k] for k in ("start","end")}
    cert = authority.certificate(review.audit._json(answer),[p],registry,eligible)
    context = authority.project([p],registry,cert)
    assert authority.validate(raw,[p],INVENTORY,RECIPE,context)[0][1].count(token(new)) == 2
    with pytest.raises(review.SemanticAuditError):
        authority.validate(correction([p],["نص "+token(new)]),[p],INVENTORY,RECIPE,context)
    # A replacement that equals an already-existing required occurrence owns two
    # distinct obligations after projection, not only the new certificate's one.
    p,old,new = example("required")
    p = replace(p,source_text=p.source_text+" [["+new+"]]",original_source_text=p.original_source_text+" "+new,
        primary_text=p.primary_text+" "+token(new),expected_ar_tokens=(old,new))
    registry = authority.freeze([p],PDF,origins([p]))
    raw = correction([p],[p.primary_text.replace(old,new)])
    eligible = authority.classify(raw,[p],INVENTORY,RECIPE,registry)
    cert = authority.certificate(review.audit._json(resolution(registry,eligible,[new])),[p],registry,eligible)
    context = authority.project([p],registry,cert)
    assert authority.validate(raw,[p],INVENTORY,RECIPE,context)[0][1].count(token(new)) == 2
    with pytest.raises(review.SemanticAuditError):
        authority.validate(correction([p],["نص "+token(new)]),[p],INVENTORY,RECIPE,context)


def test_mixed_unchanged_and_replacement_keeps_correct_printed_typo_and_never_changes_prose():
    pages,registry,raw,eligible,answer = prepared(("required","additional"))
    answer["decisions"][1].update(status="unchanged",exact_reading=eligible["lookups"][1]["value"])
    cert = authority.certificate(review.audit._json(answer),pages,registry,eligible)
    assert len(cert["changes"]) == 1
    context = authority.project(pages,registry,cert)
    assert context.projected_pages[1] == pages[1]
    tampered = deepcopy(cert)
    tampered["changes"][0]["old_occurrence"]["primary_span"].update(start=0,end=3,quote=pages[0].primary_text[:3])
    with pytest.raises(review.SemanticAuditError,match="projection_occurrence_binding"):
        authority.project(pages,registry,tampered)


def test_auto_correctable_old_url_cannot_manufacture_certified_candidate_compliance():
    p,_,_ = example("required")
    old,new = "https://tribuna1.example","https://tribunal.example"
    p = replace(p,source_text="Portal: [["+old+"]]",original_source_text="Portal: "+old,
        primary_text="البوابة "+token(old),expected_ar_tokens=(old,))
    registry = authority.freeze([p],PDF,origins([p]))
    automatic = authority.classify(correction([p],[p.primary_text.replace(old,new)]),[p],INVENTORY,RECIPE,registry)
    assert automatic is not None  # strict.ok auto-restoration cannot hide the authored conflict
    old_lookup = authority._lookup(registry["pages"][0],registry["pages"][0]["occurrences"][0])
    eligible = {"lookups":[old_lookup],"registry_sha256":review.audit._sha(review.audit._json(registry))}
    cert = authority.certificate(review.audit._json(resolution(registry,eligible,[new])),[p],registry,eligible)
    context = authority.project([p],registry,cert)
    # The unchanged historical evaluator is allowed to autocorrect this URL;
    # the fresh adapter must still reject its unauthored substituted compliance.
    assert review.audit.evaluate_output("```\n"+p.primary_text+"\n```",review.audit.TargetLang.AR,
        expected_ar_tokens=[new],ar_source_text=context.projected_pages[0].source_text,
        primary_normalized_text=context.projected_pages[0].primary_text).ok
    with pytest.raises(review.SemanticAuditError,match="final_occurrence_mismatch"):
        authority.validate(correction([p],[p.primary_text]),[p],INVENTORY,RECIPE,context)


def test_late_source_field_failure_stays_ineligible_behind_earlier_literal_failure():
    from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
    from tests.test_ar_field_label_boundaries import prepared as field_prepared
    first,old,new = example("image")
    source = field_prepared("Morada:\nAvenida Clara, 10, 1.º Andar\nCódigo Postal:1234 567 Cidade")
    primary = "العنوان: "+token("Avenida Clara, 10, 1.º Andar")+"\nالرمز البريدي: "+token("1234 567 Cidade")
    second = page(2,source_text=source,source_text_kind="pretokenized",image_data_url=image(),
        original_source_text=authority._view(source)[0],
        expected_ar_tokens=tuple(extract_locked_tokens(source)),primary_text=primary)
    pages = [first,second]
    registry = authority.freeze(pages,PDF,origins(pages))
    with pytest.raises(review.SemanticAuditError,match="ineligible_strict_failure"):
        authority.classify(correction(pages,[first.primary_text.replace(old,new),primary.replace("10","11")]),
            pages,INVENTORY,replace(RECIPE,source_field_policy="baseline_label_value_v1"),registry)


@pytest.mark.parametrize("image_off", [False,True])
def test_bounded_registry_unavailable_keeps_long_no_conflict_ordinary_pages_valid(image_off):
    value = "https://fictional.example/"+"segment"*80
    p = page(source_text="[["+value+"]]",source_text_kind="pretokenized",original_source_text=value,
        expected_ar_tokens=(value,),primary_text="البوابة "+token(value),image_data_url=image())
    recipe = RECIPE
    if image_off:
        p = replace(p,image_data_url=None,visual_coverage="text_only_configured_image_off")
        recipe = replace(recipe,configured_image_mode="off")
    review.audit._validate_inputs([p],recipe,PDF)
    raw = correction([p],[""],no_change=(1,))
    assert review.validate_source_correction(raw,[p],INVENTORY,recipe)[0][1] == p.primary_text
    registry = authority.freeze([p],PDF,origins([p]))
    assert registry["availability"] == "ineligible_capacity"
    assert authority.classify(raw,[p],INVENTORY,recipe,registry) is None
    assert authority.validate(raw,[p],INVENTORY,recipe)[0][1] == p.primary_text
    with pytest.raises(review.SemanticAuditError,match="registry_unavailable"):
        authority.classify(correction([p],["البوابة "+token("NEW")]),[p],INVENTORY,recipe,registry)


@pytest.mark.parametrize("same_page", [False,True])
def test_certified_identity_counts_preserve_unrelated_source_bound_wrapper_grouping(same_page):
    first,old,new = example("image")
    ratio = "النسبة "+token("1")+" / "+token("3")
    second = page(2,source_text="[[1]] / [[3]]",source_text_kind="pretokenized",original_source_text="1 / 3",
        expected_ar_tokens=("1","3"),primary_text=ratio,image_data_url=image())
    if same_page:
        first = replace(first,source_text=second.source_text,original_source_text=second.original_source_text,
            expected_ar_tokens=second.expected_ar_tokens,primary_text=first.primary_text+" "+ratio)
        pages = [first]
        texts = [first.primary_text.replace(old,new).replace(token("1")+" / "+token("3"),token("1 / 3"))]
    else:
        pages = [first,second]
        texts = [first.primary_text.replace(old,new),"النسبة "+token("1 / 3")]
        assert review.validate_source_correction(correction([second],[texts[1]]),[second],INVENTORY,RECIPE)[0]
    registry = authority.freeze(pages,PDF,origins(pages))
    raw = correction(pages,texts)
    eligible = authority.classify(raw,pages,INVENTORY,RECIPE,registry)
    assert len(eligible["lookups"]) == 1
    cert = authority.certificate(review.audit._json(resolution(registry,eligible,[new])),pages,registry,eligible)
    context = authority.project(pages,registry,cert)
    selected,_,_ = authority.validate(raw,pages,INVENTORY,RECIPE,context)
    assert all(authority._view(selected[p.page_number])[0] == authority._view(t)[0] for p,t in zip(pages,texts))


def test_capacity_cannot_hide_an_unrelated_invalid_later_origin():
    p,_,_ = example("image")
    p = replace(p,primary_text="نص "+token("x"*600))
    pages = [p,replace(p,page_number=2)]
    records = origins(pages); records[1]["kind"] = []
    with pytest.raises(review.SemanticAuditError,match="source_origin_binding"):
        authority.freeze(pages,PDF,records)
