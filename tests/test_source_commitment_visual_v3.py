"""Fresh V3 policy routing and guards; scripted replies are not semantic quality proof."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_source_review as policy
from tests.test_ordinary_semantic_review import PDF, pack, recipe
from tests.test_ordinary_semantic_unit_refs import Client


@pytest.mark.parametrize("case", ["absent", "explicit_none", "v1", "v2"])
def test_genuine_eca_requests_artifacts_fingerprint_and_local_replay_exact(tmp_path, case):
    fixture = json.loads((Path(__file__).parent / "fixtures/source_review_policy_prechange_eca.json").read_bytes())
    entry = fixture["cases"][case]
    pages = tuple(review.SemanticAuditPage(**p) for p in entry["pages"])
    settings = review.SemanticAuditRecipe(**entry["recipe"])
    args = dict(pages=pages, recipe=settings, pdf_sha256=entry["pdf_sha256"],
                evidence_dir=tmp_path / "audit", **entry["options"])
    client = Client()
    review.run_semantic_review(**args, client=client)
    assert review.audit._json(client.requests) == review.audit._json(entry["requests"])
    before = {p.relative_to(args["evidence_dir"]).as_posix(): p.read_bytes()
              for p in args["evidence_dir"].rglob("*") if p.is_file()}
    assert before == {name: value.encode() for name, value in entry["evidence"].items()}
    assert review.semantic_review_source_fingerprint(pages, settings, entry["pdf_sha256"], **entry["options"]) == entry["fingerprint"]
    assert review.load_semantic_review(**args).reused
    assert review.run_semantic_review(**args, client=client).reused
    assert len(client.requests) == 3
    assert {p.relative_to(args["evidence_dir"]).as_posix(): p.read_bytes()
            for p in args["evidence_dir"].rglob("*") if p.is_file()} == before


OPTIONS = {"semantic_unit_reference_policy": "caller_unit_refs_v1",
           "source_inventory_max_output_tokens": 64000,
           "semantic_page_coverage_policy": "complete_selected_pages_v1"}


def run(tmp_path, client, *, pages=None, version=None):
    return review.run_semantic_review(
        pages=pack(count=2) if pages is None else pages, recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=tmp_path / "audit", client=client, **OPTIONS,
        semantic_source_review_policy=version or policy.POLICY_V3,
    )


def test_v3_inherits_both_v2_reconciliations_and_changes_only_bound_stage_text(tmp_path):
    clients = [Client(), Client()]
    results = [run(tmp_path / str(i), client, version=version)
               for i, (client, version) in enumerate(zip(clients, (policy.POLICY_V2, policy.POLICY_V3)))]
    old_descriptor = policy.descriptor(policy.POLICY_V2)
    descriptor = policy.descriptor(policy.POLICY_V3)
    assert descriptor["inventory_ambiguity_instruction"] == old_descriptor["inventory_ambiguity_instruction"]
    assert results[0].selected_text_by_page == results[1].selected_text_by_page
    for stage, old, new in zip(review.STAGES, clients[0].requests, clients[1].requests):
        assert new["instructions"] == old["instructions"] + policy.V3_ADDITIONS[stage]
        assert policy._SHARED_OLD_AMBIGUITY not in new["instructions"]
        assert policy._SHARED_NEW_AMBIGUITY in new["instructions"]
        assert (policy._INVENTORY_NEW_AMBIGUITY in new["instructions"]) is (stage == "source_inventory")
        assert policy._INVENTORY_OLD_AMBIGUITY not in new["instructions"]
        assert {k: v for k, v in new.items() if k not in ("instructions", "prompt_text")} == {
            k: v for k, v in old.items() if k not in ("instructions", "prompt_text")}
        a, b = json.loads(old["prompt_text"]), json.loads(new["prompt_text"])
        assert a.pop("semantic_source_review_policy") == old_descriptor
        assert b.pop("semantic_source_review_policy") == descriptor
        assert a == b
        assert ("context_text" in b) is (stage == "correction")
        assert descriptor["stage_instruction_sha256"][stage] == hashlib.sha256(policy._suffixes(policy.POLICY_V3)[stage].encode()).hexdigest()
    manifest = json.loads(results[1].manifest_path.read_bytes())
    assert manifest["binding"]["semantic_source_review_policy"] == descriptor
    assert [r["max_output_tokens"] for r in clients[1].requests] == [64000, 32000, 32000]
    assert all(r["effort"] == "high" for r in clients[1].requests)


@pytest.mark.parametrize("previous", [None, policy.POLICY, policy.POLICY_V2])
def test_saved_attempt_cannot_be_upgraded_to_v3_or_rebilled(tmp_path, previous):
    client = Client()
    args = dict(pages=pack(count=2), recipe=recipe(), pdf_sha256=PDF,
                evidence_dir=tmp_path / "audit", **OPTIONS)
    review.run_semantic_review(**args, client=client, semantic_source_review_policy=previous)
    before = {p: p.read_bytes() for p in args["evidence_dir"].rglob("*") if p.is_file()}
    with pytest.raises(review.SemanticAuditError, match="binding"):
        review.run_semantic_review(**args, client=client, semantic_source_review_policy=policy.POLICY_V3)
    assert len(client.requests) == 3
    assert {p: p.read_bytes() for p in args["evidence_dir"].rglob("*") if p.is_file()} == before


def test_v3_stage_wording_tamper_invalidates_retained_binding_before_dispatch(tmp_path, monkeypatch):
    client = Client()
    run(tmp_path, client)
    monkeypatch.setitem(policy.V3_ADDITIONS, "verification", policy.V3_ADDITIONS["verification"] + " Changed rule.")
    with pytest.raises(review.SemanticAuditError, match="binding"):
        run(tmp_path, client)
    assert len(client.requests) == 3


@pytest.mark.parametrize("defect", ["source_unresolved", "temporal_uncertain", "inventory_omission", "partial_missing",
                                   "wrong_role", "candidate_unresolved", "wrong_owner", "literal_loss"])
def test_controlled_material_findings_still_block_publication(tmp_path, defect):
    pages = pack(count=2)
    if defect in {"inventory_omission", "partial_missing", "wrong_role"}:
        source, candidate = {
            "inventory_omission": ("The clerk reviewed and archived the entire file.", "راجع الموظف الملف كاملا وحفظه كاملا."),
            "partial_missing": ("The librarian recorded and indexed the collection.", "سجل أمين المكتبة المجموعة."),
            "wrong_role": ("The appointed mediator relayed the proposal.", "نقل المترجم المعيّن الاقتراح."),
        }[defect]
        pages = (replace(pages[0], source_text=source, original_source_text=source, primary_text=candidate),)
    if defect == "literal_loss":
        pages = (replace(pages[0], primary_text="نص عربي إضافي \u2066[[47]]\u2069"),)
    def damage(stage, data, payload):
        if stage == "source_inventory":
            if defect == "inventory_omission":
                data["claims"][0]["proposition"] = "The clerk reviewed and archived the file."
            if defect == "source_unresolved": data["claims"][0]["unresolved"] = True
            if defect == "temporal_uncertain": data["claims"][0]["axes"]["temporal_state"] = "uncertain"
        if stage == "correction" and defect == "literal_loss":
            data["pages"][0].update(status="corrected", corrected_text="نص عربي إضافي", reason_codes=["omission"])
        if stage == "verification":
            row = data["claim_results"][0]
            if defect == "inventory_omission":
                data["inventory_errors"] = [{"source_unit_ids": ["S001"], "reason": "A shared scope qualifier is absent from this source proposition, even though the candidate retains it."}]
            elif defect == "partial_missing": row["status"] = "missing"
            elif defect == "wrong_role": row["status"] = "contradiction"
            elif defect == "candidate_unresolved": row["status"] = "unresolved"
            elif defect == "wrong_owner": row["target_unit_ids"] = ["T002"]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pages=pages)
    assert len(client.requests) == (1 if defect in {"source_unresolved", "temporal_uncertain"} else 2 if defect == "literal_loss" else 3)
    assert not (tmp_path / "audit/manifest.json").exists()
    assert not list((tmp_path / "audit").glob("page_*.txt"))
    before = {p: p.read_bytes() for p in (tmp_path / "audit").rglob("*") if p.is_file()}
    sent = len(client.requests)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pages=pages)
    assert len(client.requests) == sent
    assert {p: p.read_bytes() for p in (tmp_path / "audit").rglob("*") if p.is_file()} == before


def test_equivalent_controlled_paraphrase_uses_actual_target_evidence_without_rewrite(tmp_path):
    pages = (replace(pack()[0], source_text="A witness may have heard a distant chime earlier.",
                     original_source_text="A witness may have heard a distant chime earlier.",
                     primary_text="قد يكون الشاهد قد سمع رنينا بعيدا في وقت سابق."),)
    client = Client()
    result = run(tmp_path, client, pages=pages)
    assert result.selected_text_by_page == {1: pages[0].primary_text}
    verified = json.loads(client.requests[-1]["prompt_text"])
    assert verified["target_units"][0]["text"] == pages[0].primary_text
    raw = json.loads((result.manifest_path.parent / "verification/raw_response.json").read_bytes())
    verdict = json.loads(raw["raw_output"])
    assert verdict["claim_results"][0] == {"claim_id": "claim_1", "status": "equivalent", "target_unit_ids": ["T001"]}
    assert verdict["inventory_errors"] == []


@pytest.mark.parametrize("value", [None, "", "unknown", True, 1, [], {}])
def test_v3_dependency_is_validated_before_evidence_or_dispatch(tmp_path, value):
    client = Client()
    with pytest.raises(review.SemanticAuditError):
        review.run_semantic_review(pages=pack(), recipe=recipe(), pdf_sha256=PDF,
            evidence_dir=tmp_path / "audit", client=client,
            semantic_source_review_policy=policy.POLICY_V3, semantic_unit_reference_policy=value)
    assert client.requests == [] and not (tmp_path / "audit").exists()


@pytest.mark.parametrize("saved_value", [None, policy.POLICY, policy.POLICY_V2])
def test_ordinary_saved_policy_resume_and_offline_never_consult_fresh_v3(tmp_path, monkeypatch, saved_value):
    from legalpdf_translate import workflow_semantic_audit as glue
    from legalpdf_translate.workflow import TranslationWorkflow
    from tests.test_semantic_review_model_integration import setup, immutable
    fresh = glue.fresh_recipe
    def historical(*args, **kwargs):
        result = fresh(*args, **kwargs)
        result.pop("semantic_repair_policy", None)
        result.pop("semantic_literal_authority_policy", None)
        result.pop("semantic_enclosure_authority_policy", None)
        if saved_value is None: result.pop("semantic_source_review_policy")
        else: result["semantic_source_review_policy"] = saved_value
        return result
    monkeypatch.setattr(glue, "fresh_recipe", historical)
    config, http, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    assert [r["model"] for r in http.requests] == ["gpt-5.2"] + ["gpt-6-astra"] * 3
    saved = flow._last_state.settings["ordinary_semantic_audit_recipe"]
    assert saved.get("semantic_source_review_policy") == saved_value
    before = immutable(result.run_dir)
    before[result.run_dir / "semantic_context.json"] = (result.run_dir / "semantic_context.json").read_bytes()
    monkeypatch.setattr(glue, "fresh_recipe", lambda *a, **k: pytest.fail("Saved replay recomputed fresh V3 recipe"))
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert len(http.requests) == 4
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert immutable(result.run_dir) == {path: raw for path, raw in before.items() if path.name != "semantic_context.json"}


@pytest.mark.parametrize("count", [0, 2])
def test_v3_inherited_inventory_instruction_drift_fails_closed(count):
    fixture = json.loads((Path(__file__).parent / "fixtures/source_review_policy_prechange_eca.json").read_bytes())
    request = deepcopy(fixture["cases"]["absent"]["requests"][0])
    request["instructions"] = request["instructions"].replace(
        policy._INVENTORY_OLD_AMBIGUITY, policy._INVENTORY_OLD_AMBIGUITY * count)
    before = deepcopy(request)
    with pytest.raises(ValueError, match="Unexpected inherited source ambiguity"):
        policy.adapt_request(request, "source_inventory", encode_payload=review._prompt_json, policy=policy.POLICY_V3)
    assert request == before
