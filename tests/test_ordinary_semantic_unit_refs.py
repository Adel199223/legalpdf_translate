"""Fictional compact protocol, exact derivation and historical replay boundaries."""
from copy import deepcopy
from dataclasses import replace
import json
import pytest
from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_unit_refs as refs
from legalpdf_translate.openai_client import ApiCallResult
from tests.test_ordinary_semantic_review import pack, recipe, PDF, Client as LegacyClient
from tests.test_ordinary_semantic_review import inventory, correction, verification


def response(stage, payload):
    index = review.STAGES.index(stage)
    result = (inventory, correction, verification)[index](payload)
    result["version"] = refs.VERSIONS[index]
    if index == 0:
        del result["unit_coverage"]
        for claim in result["claims"]:
            claim["context_unit_ids"] = []
            claim["source_image_evidence"] = [s for s in claim.pop("source_evidence") if s["kind"] == "image"]
    elif index == 2:
        lookup = {(u["page"], u["start"], u["end"], u["text"]): u["unit_id"] for u in payload["target_units"]}
        for row in result["claim_results"]:
            row["target_unit_ids"] = [lookup[(s["page"], s["start"], s["end"], s["quote"])] for s in row.pop("target_spans")]
        del result["target_unit_coverage"]
    return result


class Client:
    model = "fictional-model"
    def __init__(self, damage=None, after=None, usage=None):
        self.requests = []
        self.damage, self.after = damage, after
        self.usage = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30} if usage is None else usage
    def create_page_response(self, **request):
        self.requests.append(deepcopy(request))
        payload = json.loads(request["prompt_text"])
        result = response(payload["stage"], payload)
        if self.damage: result = self.damage(payload["stage"], result, payload)
        if self.after: self.after(payload["stage"])
        return ApiCallResult(json.dumps(result, ensure_ascii=False), self.usage, f"r{len(self.requests)}", effort="high")


def run(tmp_path, client=None, pages=None, settings=None, **kwargs):
    return review.run_semantic_review(pages=pages or pack(), recipe=settings or recipe(), pdf_sha256=PDF,
        evidence_dir=tmp_path / "audit", client=client, semantic_unit_reference_policy=refs.POLICY, **kwargs)


def test_three_calls_strict_hydration_and_zero_call_offline_replay(tmp_path):
    client = Client()
    result = run(tmp_path, client, pack(count=2))
    assert len(client.requests) == 3
    original = {p.relative_to(result.manifest_path.parent):p.read_bytes() for p in result.manifest_path.parent.rglob("*") if p.is_file()}
    loaded = review.load_semantic_review(pages=pack(count=2), recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=result.manifest_path.parent, semantic_unit_reference_policy=refs.POLICY)
    assert loaded.selected_text_by_page == result.selected_text_by_page and loaded.usage == result.usage
    assert result.usage["input_tokens"] == 30
    assert all((result.manifest_path.parent / p).read_bytes() == v for p,v in original.items())
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["version"] == refs.PROTOCOL
    assert manifest["binding"]["semantic_unit_reference_policy"]["semantic_unit_reference_policy"] == refs.POLICY
    for index, stage in enumerate(review.STAGES):
        directory = result.manifest_path.parent / stage
        raw = json.loads((directory / "raw_response.json").read_text())
        provider = json.loads(raw["raw_output"])
        derived = json.loads((directory / "derived_response.json").read_text())
        assert provider["version"] == refs.VERSIONS[index]
        assert derived["raw_output_sha256"] == review.audit._sha(raw["raw_output"])
        assert derived["request_sha256"] == review.audit._sha(review.audit._json(client.requests[index]))
        assert derived["canonical_response"]["version"] != provider["version"]
        assert json.loads((directory / "intent.json").read_text())["version"] == refs.PROTOCOL
        assert manifest["stages"][index]["derived_sha256"] == review.audit._sha((directory / "derived_response.json").read_bytes())


def test_request_boundaries_atomic_constraints_and_schema_enums(tmp_path):
    client = Client()
    pages = (replace(pack()[0], primary_text="عبارة أولية خاصة"),)
    settings = recipe(context_text="a unique preferred term")
    run(tmp_path, client, pages, settings)
    for index, request in enumerate(client.requests):
        payload = json.loads(request["prompt_text"])
        assert payload["semantic_unit_reference_policy"] == refs.POLICY
        assert payload["source_units"][0]["unit_id"] == "S001"
        assert request["effort"] == "high" and request["max_output_tokens"] == 32000
        schema = request["response_format"]["schema"]
        assert schema["$defs"]["source_id"]["enum"] == ["S001"]
        assert "context_text" in payload if index == 1 else "context_text" not in payload
        if index != 1: assert settings.context_text not in request["prompt_text"]
        if index == 0: assert pages[0].primary_text not in request["prompt_text"]
        if index == 2:
            assert schema["$defs"]["target_id"]["enum"] == ["T001"]
            assert "primary_pages" not in payload and "reason_codes" not in request["prompt_text"]
            assert "axis/proposition contradictions" in request["instructions"]
    assert "one subject/action-or-state/recipient" in client.requests[0]["instructions"]
    assert "original legal phrase" in client.requests[0]["instructions"]
    assert "every material fact WITHIN each owned unit" in client.requests[0]["instructions"]
    assert "multiple atomic claims with shared unit citations" in client.requests[0]["instructions"]
    assert "fact-level completeness" in client.requests[2]["instructions"]
    assert "already cited by another claim" in client.requests[2]["instructions"]


@pytest.mark.parametrize("defect", ["unknown", "duplicate", "context_unknown", "context_overlap", "context_duplicate",
    "missing_owner", "extra_inverse", "injected_text_evidence", "unresolved", "uncertain", "legacy_version", "wrong_top"])
def test_invalid_inventory_stops_without_selection(tmp_path, defect):
    def damage(stage, data, payload):
        if stage != review.STAGES[0]: return data
        claim = data["claims"][0]
        if defect == "unknown": claim["source_unit_ids"] = ["S999"]
        elif defect == "duplicate": claim["source_unit_ids"] *= 2
        elif defect == "context_unknown": claim["context_unit_ids"] = ["S999"]
        elif defect == "context_overlap": claim["context_unit_ids"] = claim["source_unit_ids"][:]
        elif defect == "context_duplicate": claim["context_unit_ids"] = ["S002", "S002"]
        elif defect == "missing_owner": claim["source_unit_ids"] = []
        elif defect == "extra_inverse": data["unit_coverage"] = []
        elif defect == "injected_text_evidence": claim["source_image_evidence"] = [{"kind":"text","page":1,"start":0,"end":1,"quote":"A"}]
        elif defect == "unresolved": claim["unresolved"] = True
        elif defect == "uncertain": claim["axes"]["temporal_state"] = "uncertain"
        elif defect == "legacy_version": data["version"] = review.INVENTORY_VERSION
        else: return []
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pack(count=2))
    assert len(client.requests) == 1
    assert not (tmp_path / "audit/manifest.json").exists()
    assert (tmp_path / "audit/source_inventory/raw_receipt.json").exists()


@pytest.mark.parametrize("defect", ["unknown_target", "source_as_target", "duplicate_target", "missing_target", "wrong_page",
    "contradiction", "inventory_challenge", "unsupported_addition", "unknown_error_ref"])
def test_verifier_remains_final_strict_authority(tmp_path, defect):
    def damage(stage, data, payload):
        if stage != review.STAGES[2]: return data
        row = data["claim_results"][0]
        if defect == "unknown_target": row["target_unit_ids"] = ["T999"]
        elif defect == "source_as_target": row["target_unit_ids"] = ["S001"]
        elif defect == "duplicate_target": row["target_unit_ids"] *= 2
        elif defect == "missing_target": row["target_unit_ids"] = []
        elif defect == "wrong_page": row["target_unit_ids"] = ["T002"]
        elif defect == "contradiction": row["status"] = "contradiction"
        elif defect == "inventory_challenge": data["inventory_errors"] = [{"source_unit_ids":["S001"],"reason":"Paraphrase temporal axis contradicts original completed act."}]
        elif defect == "unknown_error_ref": data["inventory_errors"] = [{"source_unit_ids":["S999"],"reason":"Missing fact"}]
        else: data["unsupported_additions"] = [{"target_unit_ids":["T001"],"reason":"Unsupported fact"}]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pack(count=2))
    assert len(client.requests) == 3 and not (tmp_path / "audit/manifest.json").exists()


def test_context_refs_do_not_enlarge_owner_pages(tmp_path):
    def damage(stage, data, payload):
        if stage == review.STAGES[0]: data["claims"][0]["context_unit_ids"] = ["S002"]
        return data
    assert run(tmp_path, Client(damage), pack(count=2)).manifest_path.exists()


def test_valid_cross_page_atomic_claim_and_missing_owner_page(tmp_path):
    def cross(stage, data, payload):
        if stage == review.STAGES[0]:
            first, second = data["claims"]
            first["source_unit_ids"] += second["source_unit_ids"]
            data["claims"] = [first]
            data["boundaries"][0].update(relation="continuation", claim_ids=[first["claim_id"]])
        return data
    assert run(tmp_path / "valid", Client(cross), pack(count=2)).manifest_path.exists()
    def missing(stage, data, payload):
        data = cross(stage, data, payload)
        if stage == review.STAGES[2]: data["claim_results"][0]["target_unit_ids"] = ["T001"]
        return data
    with pytest.raises(review.SemanticAuditError, match="review_page_ownership"):
        run(tmp_path / "invalid", Client(missing), pack(count=2))


def test_unicode_whole_unit_hydration_keeps_exact_control_and_offsets(tmp_path):
    pages = (replace(pack()[0], original_source_text="Original 😀 \u2066literal\u2069.\r\nSecond line.",
        source_text="Original 😀 \u2066literal\u2069.\r\nSecond line.", primary_text="نص \u2066[[47]]\u2069\nسطر آخر"),)
    result = run(tmp_path, Client(), pages)
    derived = json.loads((result.manifest_path.parent / "source_inventory/derived_response.json").read_text())
    for claim in derived["canonical_response"]["claims"]:
        for span in claim["source_evidence"]:
            assert pages[0].original_source_text[span["start"]:span["end"]] == span["quote"]


@pytest.mark.parametrize("file", ["source_inventory/derived_response.json", "correction/derived_response.json", "verification/derived_response.json"])
def test_corrupt_derived_evidence_blocks_zero_call_replay(tmp_path, file):
    result = run(tmp_path, Client())
    path = result.manifest_path.parent / file
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(review.SemanticAuditError, match="evidence_corrupt"): run(tmp_path)


def test_missing_complete_derivation_and_changed_policy_cannot_replay(tmp_path):
    result = run(tmp_path, Client())
    (result.manifest_path.parent / "source_inventory/derived_response.json").unlink()
    with pytest.raises(review.SemanticAuditError, match="evidence_corrupt"): run(tmp_path)
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"):
        review.load_semantic_review(pages=pack(), recipe=recipe(), pdf_sha256=PDF,evidence_dir=result.manifest_path.parent)


def test_source_map_tampering_is_rejected_before_hydration(tmp_path):
    client = Client(); run(tmp_path, client)
    request = deepcopy(client.requests[0]); payload = json.loads(request["prompt_text"])
    payload["source_units"][0]["text"] += " changed"
    request["prompt_text"] = json.dumps(payload)
    raw = json.dumps(response(review.STAGES[0], json.loads(client.requests[0]["prompt_text"])))
    with pytest.raises(review.SemanticAuditError, match="review_reference_binding"):
        refs.hydrate(raw, review.STAGES[0], request, review.source_units(pack()))


def test_unknown_policy_and_bounds_fail_before_dispatch(tmp_path):
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="review_reference_policy"):
        review.run_semantic_review(pages=pack(), recipe=recipe(), pdf_sha256=PDF,evidence_dir=tmp_path,client=client,semantic_unit_reference_policy="unknown")
    pages = (replace(pack()[0], original_source_text="\n".join(f"Line {i}" for i in range(refs.MAX_UNITS+1))),)
    with pytest.raises(review.SemanticAuditError, match="review_unit_bound"): run(tmp_path / "bound", client, pages)
    assert client.requests == []


def test_163_unit_case_schema_is_bounded_and_shared_defs():
    pages = (replace(pack()[0], original_source_text="\n".join(f"Line {i}" for i in range(163))),)
    units = review.source_units(pages); source = refs.unit_map(units,"S")
    schema = refs.response_format(review.STAGES[0],source)["schema"]
    assert len(schema["$defs"]["source_id"]["enum"]) == 163
    assert schema["properties"]["claims"]["items"]["properties"]["context_unit_ids"]["items"] == {"$ref":"#/$defs/source_id"}


def test_schema_aggregate_budget_fails_closed(monkeypatch):
    monkeypatch.setattr(refs,"MAX_ENUM_VALUES",1)
    with pytest.raises(review.SemanticAuditError, match="review_reference_schema_bound"):
        refs.descriptor(review.source_units(pack()))


def test_missing_usage_stops_after_one_settled_stage(tmp_path):
    client = Client(usage={})
    with pytest.raises(review.SemanticAuditError, match="usage_unknown_or_unsettled"): run(tmp_path, client)
    assert len(client.requests) == 1 and (tmp_path / "audit/source_inventory/raw_receipt.json").exists()
    assert not (tmp_path / "audit/correction").exists()


def test_cancel_after_first_settlement_no_later_dispatch_or_publication(tmp_path):
    cancelled = False
    def after(stage):
        nonlocal cancelled
        cancelled = True
    client = Client(after=after)
    with pytest.raises(review.SemanticAuditError, match="operation_cancelled"):
        run(tmp_path, client, cancel_check=lambda: cancelled)
    assert len(client.requests) == 1 and (tmp_path / "audit/source_inventory/raw_receipt.json").exists()
    assert not (tmp_path / "audit/manifest.json").exists()


def test_unsettled_intent_cannot_repurchase(tmp_path):
    class Interrupted(Client):
        def create_page_response(self, **request):
            self.requests.append(request)
            raise RuntimeError("connection interrupted")
    client = Interrupted()
    with pytest.raises(review.SemanticAuditError, match="provider_operation_unsettled"): run(tmp_path, client)
    second = Client()
    with pytest.raises(review.SemanticAuditError, match="review_unsettled_stage"): run(tmp_path, second)
    assert len(client.requests) == 1 and not second.requests


def test_initial_correction_anti_loss_remains_unchanged(tmp_path):
    pages = (replace(pack()[0],primary_text="نص \u2066[[47]]\u2069"),)
    def damage(stage,data,payload):
        if stage == review.STAGES[1]: data["pages"][0].update(status="corrected",corrected_text="نص",reason_codes=["omission"])
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path,client,pages)
    assert len(client.requests) == 2 and not (tmp_path / "audit/manifest.json").exists()


def test_image_only_and_text_only_coverage(tmp_path):
    pages = (replace(pack()[0],original_source_text="",source_text=""),)
    assert run(tmp_path / "image",Client(),pages).manifest_path.exists()
    assert run(tmp_path / "text",Client(),pack(off=True),recipe(configured_image_mode="off")).manifest_path.exists()


@pytest.mark.parametrize("count", [249,250,251,2400])
def test_unit_schema_threshold_and_existing_maximum(count):
    pages = (replace(pack()[0],original_source_text="\n".join(f"Line {n}" for n in range(count))),)
    source = refs.unit_map(review.source_units(pages),"S")
    schema = refs.response_format(review.STAGES[0],source)["schema"]
    definition = schema["$defs"]["source_id"]
    assert ("enum" in definition) == (count <= refs.ENUM_THRESHOLD)
    assert len(source) == count
    with pytest.raises(review.SemanticAuditError,match="review_reference_evidence"):
        refs._refs(["S99999"],source)


def test_current_legacy_golden_requests_bindings_and_complete_raw_replay(tmp_path):
    from pathlib import Path
    fixture=json.loads((Path(__file__).parent/"fixtures/semantic_unit_refs/legacy_v3.json").read_text())
    assert fixture["engine_sha256"] == "89a8e76903d9ea3a4a5f5902028f509a3b5cad148e16ca95ce8930bc71ecbe09"
    pages=tuple(review.SemanticAuditPage(**p) for p in fixture["pages"])
    settings=review.SemanticAuditRecipe(**fixture["recipe"])
    client=LegacyClient()
    directory=tmp_path/"fresh"
    result=review.run_semantic_review(pages=pages,recipe=settings,pdf_sha256=PDF,evidence_dir=directory,client=client)
    assert review.audit._json(client.requests) == review.audit._json(fixture["requests"])
    assert {p.relative_to(directory).as_posix():p.read_text(encoding="utf8") for p in directory.rglob("*") if p.is_file()} == fixture["evidence"]
    saved=tmp_path/"saved"
    for rel,text in fixture["evidence"].items():
        path=saved/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(text.encode("utf8"))
    loaded=review.load_semantic_review(pages=pages,recipe=settings,pdf_sha256=PDF,evidence_dir=saved)
    assert loaded.reused and loaded.selected_text_by_page == result.selected_text_by_page
    assert {p.relative_to(saved).as_posix():p.read_text(encoding="utf8") for p in saved.rglob("*") if p.is_file()} == fixture["evidence"]
    assert review.semantic_review_source_fingerprint(pages,settings,PDF) == fixture["fingerprint"]
    assert review.semantic_review_source_fingerprint(pages,settings,PDF,semantic_unit_reference_policy=refs.POLICY) != fixture["fingerprint"]


@pytest.mark.parametrize("key,value", [("semantic_unit_reference_policy","other"),("protocol","other"),("stage","verification")])
def test_hydration_requires_exact_policy_and_stage_request(tmp_path,key,value):
    client=Client();run(tmp_path,client)
    request=deepcopy(client.requests[0]);payload=json.loads(request["prompt_text"])
    raw=json.dumps(response(review.STAGES[0],payload))
    payload[key]=value;request["prompt_text"]=json.dumps(payload)
    with pytest.raises(review.SemanticAuditError,match="review_reference_binding"):
        refs.hydrate(raw,review.STAGES[0],request,review.source_units(pack()))


def test_inventory_omitted_unit_fails_computed_coverage(tmp_path):
    def damage(stage,data,payload):
        if stage==review.STAGES[0]:data["claims"].pop()
        return data
    client=Client(damage)
    with pytest.raises(review.SemanticAuditError,match="review_coverage"):run(tmp_path,client,pack(count=2))
    assert len(client.requests)==1


def test_two_same_text_units_on_distinct_pages_cannot_alias(tmp_path):
    pages=(pack()[0],replace(pack()[0],page_number=2))
    def damage(stage,data,payload):
        if stage==review.STAGES[0]:data["claims"][1]["source_unit_ids"]=["S001"]
        return data
    with pytest.raises(review.SemanticAuditError,match="review_coverage"):
        run(tmp_path,Client(damage),pages)


@pytest.mark.parametrize("bad", [1,True,None,"s001"," S001","S001 ","S0001","sp1_0_madeup"])
def test_short_refs_have_no_alias_or_type_coercion(tmp_path,bad):
    def damage(stage,data,payload):
        if stage==review.STAGES[0]:data["claims"][0]["source_unit_ids"]=[bad]
        return data
    with pytest.raises(review.SemanticAuditError,match="review_reference_evidence"):
        run(tmp_path,Client(damage))


def test_large_fallback_map_still_enforces_application_membership():
    pages=(replace(pack()[0],original_source_text="\n".join(f"Line {n}" for n in range(2400))),)
    mapping=refs.unit_map(review.source_units(pages),"S")
    assert refs._refs(["S2400"],mapping)[0]["start"]>0
    for bad in (["S2401"],["S250","S250"]):
        with pytest.raises(review.SemanticAuditError,match="review_reference_evidence"):refs._refs(bad,mapping)


def test_image_only_claim_wrong_target_page_fails(tmp_path):
    pages=(replace(pack()[0],original_source_text="",source_text=""),replace(pack()[0],page_number=2,original_source_text="",source_text=""))
    def damage(stage,data,payload):
        if stage==review.STAGES[2]:data["claim_results"][0]["target_unit_ids"]=["T002"]
        return data
    with pytest.raises(review.SemanticAuditError,match="review_page_ownership"):run(tmp_path,Client(damage),pages)



def test_long_valid_claim_ids_use_membership_fallback_without_schema_rejection():
    source=refs.unit_map(review.source_units(pack()),"S")
    claims=[{"claim_id":"C"+str(n).zfill(3)+"x"*60} for n in range(200)]
    inventory={"claims":claims}
    fmt=refs.response_format(review.STAGES[1],source,inventory=inventory)
    assert "enum" not in fmt["schema"]["$defs"]["claim_id"]
    assert fmt["schema"]["$defs"]["source_id"]["enum"]==["S001"]
    refs._check_schema(fmt["schema"])


@pytest.mark.parametrize("budget", ["MAX_ENUM_VALUES","MAX_ENUM_CHARS","MAX_SCHEMA_CHARS"])
def test_dynamic_enums_fall_back_for_aggregate_budgets(monkeypatch,budget):
    source=refs.unit_map(review.source_units(pack()),"S")
    inventory={"claims":[{"claim_id":"c"+str(n).zfill(3)+"z"*60} for n in range(200)]}
    reference=refs.response_format(review.STAGES[1],source,inventory=inventory)
    if budget=="MAX_ENUM_VALUES": monkeypatch.setattr(refs,budget,100)
    elif budget=="MAX_ENUM_CHARS": monkeypatch.setattr(refs,budget,500)
    else: monkeypatch.setattr(refs,budget,len(review.audit._json(reference["schema"]))-10)
    fmt=refs.response_format(review.STAGES[1],source,inventory=inventory)
    refs._check_schema(fmt["schema"])
    assert any("enum" not in v for v in fmt["schema"]["$defs"].values())



def test_repeated_large_refs_fail_before_derived_publication(tmp_path,monkeypatch):
    # Provider raw is small enough, while exact repeated source spans alone
    # exceed the same legacy response bound. No source text is normalized.
    pages=(replace(pack()[0],original_source_text="X"*20000),)
    def repeat(stage,data,payload):
        if stage==review.STAGES[0]:
            first=data["claims"][0]
            data["claims"]=[{**deepcopy(first),"claim_id":f"C{n}"} for n in range(100)]
        return data
    monkeypatch.setattr(review.audit,"MAX_RESPONSE_CHARS",100000)
    client=Client(repeat)
    with pytest.raises(review.SemanticAuditError,match="review_response_bound"):run(tmp_path,client,pages)
    assert len(client.requests)==1
    assert (tmp_path/"audit/source_inventory/raw_receipt.json").exists()
    assert not (tmp_path/"audit/source_inventory/derived_response.json").exists()
    assert not (tmp_path/"audit/correction").exists()


def test_oversized_corrupt_derivation_is_checked_before_read(tmp_path,monkeypatch):
    from pathlib import Path
    result=run(tmp_path,Client())
    target=result.manifest_path.parent/"source_inventory/derived_response.json"
    target.write_bytes(target.read_bytes()+b" "*1000000)
    original=Path.read_bytes
    def checked(path):
        if path==target:pytest.fail("oversized corrupt derivation must fail stat-size check before read")
        return original(path)
    monkeypatch.setattr(Path,"read_bytes",checked)
    with pytest.raises(review.SemanticAuditError,match="evidence_corrupt"):run(tmp_path)
