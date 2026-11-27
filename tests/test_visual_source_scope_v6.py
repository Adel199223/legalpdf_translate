"""Fresh shared visual scope: request/validation contracts, never model quality."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_source_review as policy
from legalpdf_translate import ordinary_semantic_repair as repair
from legalpdf_translate.checkpoint import ordinary_semantic_audit_recipe, SemanticAuditRecipeError
from tests.test_ordinary_semantic_review import pack, recipe, PDF
from tests.test_ordinary_semantic_unit_refs import Client
from tests.test_workflow_semantic_review_integration import saved_recipe

KEY = "semantic_source_review_policy"
V6 = "source_commitment_visual_v6"
OPTIONS = {"semantic_unit_reference_policy": "caller_unit_refs_v1",
    "source_inventory_max_output_tokens": 64000,
    "semantic_page_coverage_policy": "complete_selected_pages_v1"}
V5_HASHES = {
    "source_inventory": "5a6172505e7eedfe797c27fcaef17ae2f5f99ad32986401b2f9f7937565b5fb1",
    "correction": "7564fe2334d680c8d99772dbf8b37f483e1ff4a67a17cb1c4026a71b24718e3c",
    "verification": "af5cb1b9f89601fed05c9f8a171218099a347405f7ede321249b193612bf7e24"}


def files(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


def run(folder, client=None, selected=V6):
    return review.run_semantic_review(pages=pack(count=2), recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=folder, client=client, **OPTIONS, **{KEY: selected})


def test_v6_appends_one_identical_scope_to_all_three_exact_v5_stage_suffixes():
    assert policy.POLICY_V6 == V6
    assert policy.descriptor(policy.POLICY_V5)["stage_instruction_sha256"] == V5_HASHES
    before, after = policy._suffixes(policy.POLICY_V5), policy._suffixes(V6)
    for stage in review.STAGES:
        assert after[stage] == before[stage] + policy.V6_VISUAL_SCOPE
        assert after[stage].count(policy.V6_VISUAL_SCOPE) == 1
    old, new = policy.descriptor(policy.POLICY_V5), policy.descriptor(V6)
    assert {k:v for k,v in old.items() if k not in {"policy", "stage_instruction_sha256"}} == {
        k:v for k,v in new.items() if k not in {"policy", "stage_instruction_sha256"}}
    assert all(old["stage_instruction_sha256"][stage] != new["stage_instruction_sha256"][stage] for stage in review.STAGES)


@pytest.mark.parametrize("requirement", [
    "ALL readable text wherever it appears", "within a logo, crest, stamp or seal",
    "repeated headers/footers on each original page", "document-specific meaning",
    "stamps, signatures, selection, cancellation or association marks",
    "existing precise visual-description and association evidence",
    "without inferring authenticity, legal effect, identity or physical execution",
    "not a source proposition requiring invented prose or a neutral label",
    "This exception does not cover readable text or a document-specific meaning-bearing mark",
    "each page and region from its own supplied original evidence",
    "recurrence on another page is not evidence here",
    "retain unresolved and stop unapproved",
    "Do not suppress a real inventory error, target defect or unsupported addition",
])
def test_shared_scope_preserves_both_material_visual_content_and_page_local_limits(requirement):
    assert requirement in policy.V6_VISUAL_SCOPE


def test_all_request_changes_are_versioned_scope_and_descriptor_only(tmp_path):
    old_client, new_client = Client(), Client()
    old = run(tmp_path / "v5", old_client, policy.POLICY_V5)
    new = run(tmp_path / "v6", new_client)
    assert old.selected_text_by_page == new.selected_text_by_page
    assert len(old_client.requests) == len(new_client.requests) == 3
    for stage, old_request, new_request in zip(review.STAGES, old_client.requests, new_client.requests):
        old_payload, new_payload = json.loads(old_request["prompt_text"]), json.loads(new_request["prompt_text"])
        assert old_payload.pop(KEY) == policy.descriptor(policy.POLICY_V5)
        assert new_payload.pop(KEY) == policy.descriptor(V6)
        assert old_payload == new_payload
        assert new_request["instructions"] == old_request["instructions"] + policy.V6_VISUAL_SCOPE
        assert {k:v for k,v in old_request.items() if k not in {"prompt_text", "instructions"}} == {
            k:v for k,v in new_request.items() if k not in {"prompt_text", "instructions"}}
        assert new_request["image_data_urls"] == tuple(p.image_data_url for p in pack(count=2))
        assert new_request["response_format"] == old_request["response_format"]
    before = files(tmp_path / "v6")
    assert review.load_semantic_review(pages=pack(count=2), recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=tmp_path / "v6", **OPTIONS, **{KEY: V6}).reused
    assert files(tmp_path / "v6") == before and len(new_client.requests) == 3


@pytest.mark.parametrize("old", [None, policy.POLICY, policy.POLICY_V2, policy.POLICY_V3, policy.POLICY_V4, policy.POLICY_V5])
def test_old_saved_requests_cannot_be_retrospectively_reinterpreted_as_v6(tmp_path, old):
    client = Client()
    run(tmp_path / "audit", client, old)
    before = files(tmp_path / "audit")
    with pytest.raises(review.SemanticAuditError, match="binding"):
        run(tmp_path / "audit", client)
    assert len(client.requests) == 3 and files(tmp_path / "audit") == before


@pytest.mark.parametrize("reason", [
    "Generic institutional artwork is missing a neutral prose label.",
    "Readable text within a graphic was omitted.",
    "A document-specific signature mark was omitted.",
    "Page-local selection or cancellation meaning was omitted.",
])
def test_every_returned_inventory_error_remains_a_strict_rejection_without_keyword_filter(tmp_path, reason):
    def damage(stage, data, payload):
        if stage == "verification":
            data["inventory_errors"] = [{"source_unit_ids": [], "reason": reason}]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError, match="review_independent_verification_failed"):
        run(tmp_path / "audit", client)
    assert len(client.requests) == 3 and not (tmp_path / "audit/manifest.json").exists()
    before = files(tmp_path / "audit")
    with pytest.raises(review.SemanticAuditError):
        run(tmp_path / "audit", client)
    assert len(client.requests) == 3 and files(tmp_path / "audit") == before


@pytest.mark.parametrize("defect", ["source_unresolved", "candidate_missing", "candidate_unresolved", "unsupported", "wrong_owner", "literal_loss"])
def test_v6_never_waives_unresolved_ownership_target_or_literal_guards(tmp_path, defect):
    from legalpdf_translate.output_normalize import LRI, PDI
    protected = LRI + "[[ZX-206]]" + PDI
    pages = tuple(replace(p, source_text="Reference " + protected + ".", original_source_text="Reference ZX-206.",
        source_text_kind="pretokenized", expected_ar_tokens=("ZX-206",), primary_text="المرجع " + protected + ".") for p in pack(count=2))
    def damage(stage, data, payload):
        if stage == "source_inventory" and defect == "source_unresolved":
            data["claims"][0]["unresolved"] = True
        if stage == "correction" and defect == "literal_loss":
            data["pages"][0].update(status="corrected", corrected_text="المرجع.", reason_codes=["literal_fidelity"])
        if stage == "verification":
            if defect == "candidate_missing": data["claim_results"][0]["status"] = "missing"
            if defect == "candidate_unresolved": data["claim_results"][0]["status"] = "unresolved"
            if defect == "wrong_owner": data["claim_results"][0]["target_unit_ids"] = ["T002"]
            if defect == "unsupported": data["unsupported_additions"] = [{"target_unit_ids": ["T001"], "reason": "Unsupported generic label added."}]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError):
        review.run_semantic_review(pages=pages, recipe=recipe(), pdf_sha256=PDF, evidence_dir=tmp_path / "audit",
            client=client, **OPTIONS, **{KEY: V6})
    assert len(client.requests) == {"source_unresolved":1,"literal_loss":2}.get(defect,3)
    assert not (tmp_path / "audit/manifest.json").exists()


def test_fresh_saved_v6_roundtrips_and_saved_v5_never_upgrades(tmp_path):
    _, saved, settings = saved_recipe(tmp_path)
    # This historical oracle explicitly owns saved V6 as fresh advances.
    saved[KEY] = V6
    saved.pop("semantic_target_ambiguity_policy", None)
    saved.pop("semantic_enclosure_sequence_repair_policy", None)
    saved.pop("primary_page_evidence_policy", None)
    saved.pop("primary_literal_markup_policy", None)
    settings["ocr_engine"] = "api"
    assert saved[KEY] == V6
    assert saved["semantic_repair_policy"] == repair.POLICY_V4
    assert ordinary_semantic_audit_recipe(settings) == saved
    saved[KEY] = policy.POLICY_V5
    before = json.dumps(settings, sort_keys=True)
    assert ordinary_semantic_audit_recipe(settings)[KEY] == policy.POLICY_V5
    assert json.dumps(settings, sort_keys=True) == before


@pytest.mark.parametrize("saved_repair", [repair.POLICY, repair.POLICY_V2, repair.POLICY_V3])
def test_v6_cannot_be_combined_with_historical_repair_controllers(tmp_path, saved_repair):
    _, saved, settings = saved_recipe(tmp_path)
    # This historical oracle explicitly owns saved V6 as fresh advances.
    saved[KEY] = V6
    saved.pop("semantic_target_ambiguity_policy", None)
    saved.pop("semantic_enclosure_sequence_repair_policy", None)
    saved.pop("primary_page_evidence_policy", None)
    saved.pop("primary_literal_markup_policy", None)
    settings["ocr_engine"] = "api"
    saved["semantic_repair_policy"] = saved_repair
    with pytest.raises(SemanticAuditRecipeError, match="semantic_repair_policy"):
        ordinary_semantic_audit_recipe(settings)


@pytest.mark.parametrize("source_policy,repair_policy", [
    (policy.POLICY_V5, repair.POLICY), (policy.POLICY_V5, repair.POLICY_V2),
    (policy.POLICY_V5, repair.POLICY_V3), (policy.POLICY_V5, repair.POLICY_V4),
    (V6, repair.POLICY_V4),
])
def test_exact_saved_repair_options_admit_only_existing_v5_or_fresh_v6_v4_combinations(tmp_path, monkeypatch, source_policy, repair_policy):
    class Prepared(Exception): pass
    def prepared(*args, **kwargs): raise Prepared()
    monkeypatch.setattr(review, "_prepare", prepared)
    kwargs = {"semantic_repair_policy": repair_policy, "stage_guard": lambda **k: None}
    if repair_policy in (repair.POLICY_V3, repair.POLICY_V4):
        kwargs["semantic_literal_authority_policy"] = "source_literal_authority_v1"
    if repair_policy == repair.POLICY_V4:
        kwargs["semantic_enclosure_authority_policy"] = "source_enclosure_authority_v1"
    with pytest.raises(Prepared):
        repair.run_semantic_repair(pages=pack(), recipe=replace(recipe(), model="gpt-6-astra"), pdf_sha256=PDF,
            evidence_dir=tmp_path / "audit", **OPTIONS, **{KEY: source_policy}, **kwargs)
    assert not (tmp_path / "audit").exists()
    assert repair.descriptor(repair_policy)["max_cycles"] == 1


@pytest.mark.parametrize("saved_repair", [repair.POLICY, repair.POLICY_V2, repair.POLICY_V3])
def test_repair_controller_gate_rejects_unapproved_v6_historical_pair_before_evidence(tmp_path, saved_repair):
    kwargs = {"semantic_repair_policy": saved_repair, "stage_guard": lambda **k: None}
    if saved_repair == repair.POLICY_V3:
        kwargs["semantic_literal_authority_policy"] = "source_literal_authority_v1"
    with pytest.raises(review.SemanticAuditError, match="repair_policy_or_accounting"):
        repair.run_semantic_repair(pages=pack(), recipe=replace(recipe(), model="gpt-6-astra"), pdf_sha256=PDF,
            evidence_dir=tmp_path / "audit", **OPTIONS, **{KEY: V6}, **kwargs)
    assert not (tmp_path / "audit").exists()
