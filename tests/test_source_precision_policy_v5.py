"""Fresh V5 request contract and unchanged guards; scripted replies prove no model quality."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_source_review as policy
from legalpdf_translate.output_normalize import LRI, PDI
from tests.test_ordinary_semantic_review import PDF, pack, recipe
from tests.test_ordinary_semantic_unit_refs import Client


FIXTURE = Path(__file__).parent / "fixtures/semantic_source_precision_prechange_d09d.json"
CASES = ("absent", "explicit_none", "v1", "v2", "v3", "v4")
OPTIONS = {"semantic_unit_reference_policy": "caller_unit_refs_v1",
           "source_inventory_max_output_tokens": 64000,
           "semantic_page_coverage_policy": "complete_selected_pages_v1"}
APPROVED_STAGE_HASHES = {
    "source_inventory": "5a6172505e7eedfe797c27fcaef17ae2f5f99ad32986401b2f9f7937565b5fb1",
    "correction": "7564fe2334d680c8d99772dbf8b37f483e1ff4a67a17cb1c4026a71b24718e3c",
    "verification": "af5cb1b9f89601fed05c9f8a171218099a347405f7ede321249b193612bf7e24",
}


def files(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob("*") if path.is_file()}


def run(tmp_path, client, *, pages=None):
    return review.run_semantic_review(pages=pack(count=2) if pages is None else pages,
        recipe=recipe(), pdf_sha256=PDF, evidence_dir=tmp_path / "audit", client=client,
        **OPTIONS, semantic_source_review_policy=policy.POLICY_V5)


@pytest.mark.parametrize("name", CASES)
def test_genuine_d09d_requests_full_artifacts_fingerprint_and_replay_exact(tmp_path, name):
    entry = json.loads(FIXTURE.read_bytes())["cases"][name]
    pages = tuple(review.SemanticAuditPage(**page) for page in entry["pages"])
    settings = review.SemanticAuditRecipe(**entry["recipe"])
    arguments = dict(pages=pages, recipe=settings, pdf_sha256=entry["pdf_sha256"],
                     evidence_dir=tmp_path / "audit", **entry["options"])
    client = Client()
    review.run_semantic_review(**arguments, client=client)
    assert review.audit._json(client.requests) == review.audit._json(entry["requests"])
    before = files(arguments["evidence_dir"])
    assert before == {path: value.encode("utf-8") for path, value in entry["evidence"].items()}
    assert review.semantic_review_source_fingerprint(pages, settings, entry["pdf_sha256"], **entry["options"]) == entry["fingerprint"]
    assert review.load_semantic_review(**arguments).reused
    assert review.run_semantic_review(**arguments, client=client).reused
    assert len(client.requests) == 3 and files(arguments["evidence_dir"]) == before


def test_approved_v5_delta_inherits_exact_v4_projection_and_verifier_bytes():
    previous = policy.descriptor(policy.POLICY_V4)
    descriptor = policy.descriptor(policy.POLICY_V5)
    assert descriptor["stage_instruction_sha256"] == APPROVED_STAGE_HASHES
    assert set(policy.V5_ADDITIONS) == {"source_inventory", "correction"}
    assert descriptor["stage_instruction_sha256"]["verification"] == previous["stage_instruction_sha256"]["verification"]
    assert {key: value for key, value in descriptor.items() if key not in ("policy", "stage_instruction_sha256")} == {
        key: value for key, value in previous.items() if key not in ("policy", "stage_instruction_sha256")}
    entries = json.loads(FIXTURE.read_bytes())["cases"]["absent"]["requests"]
    for stage, request in zip(review.STAGES, entries):
        original = deepcopy(request)
        old = policy.adapt_request(request, stage, encode_payload=review._prompt_json, policy=policy.POLICY_V4)
        new = policy.adapt_request(request, stage, encode_payload=review._prompt_json, policy=policy.POLICY_V5)
        assert new["instructions"] == old["instructions"] + policy.V5_ADDITIONS.get(stage, "")
        old_payload, new_payload = json.loads(old["prompt_text"]), json.loads(new["prompt_text"])
        assert old_payload.pop("semantic_source_review_policy") == previous
        assert new_payload.pop("semantic_source_review_policy") == descriptor
        assert old_payload == new_payload
        assert {key: value for key, value in old.items() if key not in ("instructions", "prompt_text")} == {
            key: value for key, value in new.items() if key not in ("instructions", "prompt_text")}
        if stage == "correction":
            incoming = json.loads(request["prompt_text"])
            expected = deepcopy(incoming)
            for collection, field in (("primary_pages", "text"), ("literal_protocol", "source_text")):
                for row in expected[collection]:
                    row[field] = policy.project_visible_literal_wrappers(row[field])
            assert new_payload == expected
        assert request == original


def test_approved_suffixes_bind_source_specificity_neutral_relations_and_equivalence():
    assert hashlib.sha256(policy.V5_ADDITIONS["source_inventory"].encode()).hexdigest() == "b76bed3237e320c667e74d4fe0670e60e835155716695bfba14e7052d42fad4c"
    assert hashlib.sha256(policy.V5_ADDITIONS["correction"].encode()).hexdigest() == "af56ef739fdc1d43f4f496b6de6aa32069352f58549b4e4015e9c747faf147f9"
    assert policy._suffixes(policy.POLICY_V5)["verification"] == policy._suffixes(policy.POLICY_V4)["verification"]


@pytest.mark.parametrize("name", CASES)
def test_genuine_history_cannot_be_upgraded_to_v5_or_repurchased(tmp_path, name):
    entry = json.loads(FIXTURE.read_bytes())["cases"][name]
    directory = tmp_path / "audit"
    for relative, text in entry["evidence"].items():
        path = directory / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf-8"))
    before = files(directory)
    arguments = dict(pages=tuple(review.SemanticAuditPage(**page) for page in entry["pages"]),
        recipe=review.SemanticAuditRecipe(**entry["recipe"]), pdf_sha256=entry["pdf_sha256"],
        evidence_dir=directory, **{**entry["options"], "semantic_source_review_policy": policy.POLICY_V5})
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="binding"):
        review.run_semantic_review(**arguments, client=client)
    assert client.requests == [] and files(directory) == before


@pytest.mark.parametrize("tamper", ["source_inventory", "correction", "projection_semantics"])
def test_v5_instruction_or_projection_identity_tamper_cannot_reuse_settlement(tmp_path, monkeypatch, tamper):
    client = Client()
    run(tmp_path, client)
    before = files(tmp_path / "audit")
    if tamper == "projection_semantics":
        monkeypatch.setattr(policy, "_LITERAL_PROJECTION_SEMANTICS", policy._LITERAL_PROJECTION_SEMANTICS + " Changed.")
    else:
        monkeypatch.setitem(policy.V5_ADDITIONS, tamper, policy.V5_ADDITIONS[tamper] + " Changed.")
    with pytest.raises(review.SemanticAuditError, match="binding"):
        run(tmp_path, client)
    assert len(client.requests) == 3 and files(tmp_path / "audit") == before


@pytest.mark.parametrize("defect,source,candidate,proposition,status", [
    ("inventory_type", "The inspector examined the thermal camera.", "فحص المفتش كاميرا التصوير الحراري.", "The inspector examined a camera.", None),
    ("inventory_relation", "The courier used a handheld scanner.", "استخدم الساعي ماسحا ضوئيا محمولا باليد.", "The courier used his handheld scanner.", None),
    ("candidate_type", "The technician checked the handheld scanner.", "فحص الفني أداة.", None, "missing"),
    ("candidate_relation", "The courier held the archive key for the afternoon.", "امتلك الساعي مفتاح الأرشيف طوال فترة بعد الظهر.", None, "contradiction"),
    ("candidate_qualifier", "The curator examined only the red folder.", "فحص أمين المجموعة المجلد.", None, "missing"),
], ids=["inventory_type", "inventory_relation", "candidate_type", "candidate_relation", "candidate_qualifier"])
def test_controlled_material_precision_findings_block_without_repurchase(tmp_path, defect, source, candidate, proposition, status):
    pages = (replace(pack()[0], source_text=source, original_source_text=source, primary_text=candidate),)
    def damage(stage, data, payload):
        if stage == "source_inventory" and proposition is not None:
            data["claims"][0]["proposition"] = proposition
        if stage == "verification":
            assert payload["target_units"][0]["text"] == candidate
            if proposition is not None:
                data["inventory_errors"] = [{"source_unit_ids": ["S001"], "reason": "The inventory generalizes an explicit source type or adds an unsupported relationship."}]
            else:
                data["claim_results"][0]["status"] = status
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError):
        run(tmp_path, client, pages=pages)
    assert len(client.requests) == 3
    before = files(tmp_path / "audit")
    assert "manifest.json" not in before and not list((tmp_path / "audit").glob("page_*.txt"))
    with pytest.raises(review.SemanticAuditError):
        run(tmp_path, client, pages=pages)
    assert len(client.requests) == 3 and files(tmp_path / "audit") == before


@pytest.mark.parametrize("source,candidate", [
    ("The inspector examined the thermal camera.", "فحص المفتش كاميرا التصوير الحراري."),
    ("A thermal camera arrived, and the inspector examined that device.", "وصلت كاميرا حرارية وفحص المفتش ذلك الجهاز."),
    ("The courier used a handheld scanner.", "استخدم الساعي ماسحا ضوئيا محمولا باليد."),
    ("The scanner belonged to the courier.", "كان الماسح الضوئي ملكا للساعي."),
    ("Levantou a mão.", "رفع يده."),
], ids=["accurate_type", "unambiguous_reference", "neutral_use", "expressed_ownership", "inalienable_possessive"])
def test_controlled_equivalent_terms_references_and_possessives_preserve_candidate(tmp_path, source, candidate):
    pages = (replace(pack()[0], source_text=source, original_source_text=source, primary_text=candidate),)
    client = Client()
    result = run(tmp_path, client, pages=pages)
    assert result.selected_text_by_page == {1: candidate}
    final = json.loads(client.requests[-1]["prompt_text"])
    assert "candidate_pages" in final and final["candidate_pages"][0]["text"] == candidate
    assert final["target_units"][0]["text"] == candidate
    before = files(tmp_path / "audit")
    assert run(tmp_path, client, pages=pages).reused
    assert len(client.requests) == 3 and files(tmp_path / "audit") == before


@pytest.mark.parametrize("defect", ["source_unresolved", "candidate_unresolved", "wrong_owner", "literal_loss"])
def test_existing_unresolved_ownership_and_literal_guards_still_block(tmp_path, defect):
    literal = "ZX-204"
    protected = LRI + "[[" + literal + "]]" + PDI
    pages = tuple(replace(page, source_text="Reference " + protected + ".",
        original_source_text="Reference " + literal + ".", source_text_kind="pretokenized",
        expected_ar_tokens=(literal,), primary_text="المرجع " + protected + ".") for page in pack(count=2))
    def damage(stage, data, payload):
        if stage == "source_inventory" and defect == "source_unresolved":
            data["claims"][0]["unresolved"] = True
        if stage == "correction" and defect == "literal_loss":
            data["pages"][0].update(status="corrected", corrected_text="المرجع.", reason_codes=["literal_fidelity"])
        if stage == "verification":
            if defect == "candidate_unresolved":
                data["claim_results"][0]["status"] = "unresolved"
            if defect == "wrong_owner":
                data["claim_results"][0]["target_unit_ids"] = ["T002"]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError):
        run(tmp_path, client, pages=pages)
    assert len(client.requests) == {"source_unresolved": 1, "literal_loss": 2}.get(defect, 3)
    before = files(tmp_path / "audit")
    assert "manifest.json" not in before
    sent = len(client.requests)
    with pytest.raises(review.SemanticAuditError):
        run(tmp_path, client, pages=pages)
    assert len(client.requests) == sent and files(tmp_path / "audit") == before


def test_v5_visible_correction_normalizes_before_verifier_and_preserves_raw_response(tmp_path):
    literal = "حقل-É24"
    protected = LRI + "[[" + literal + "]]" + PDI
    primary = "المرجع " + protected + ", " + protected + "."
    visible = primary.replace(LRI, "").replace(PDI, "")
    pages = (replace(pack()[0], source_text="Reference " + protected + ", " + protected + ".",
        original_source_text="Reference " + literal + ", " + literal + ".", source_text_kind="pretokenized",
        expected_ar_tokens=(literal, literal), primary_text=primary),)
    def correct(stage, data, payload):
        if stage == "correction":
            assert payload["primary_pages"][0]["text"] == visible
            data["pages"][0].update(status="corrected", corrected_text=visible, reason_codes=["literal_fidelity"])
        return data
    client = Client(correct)
    assert run(tmp_path, client, pages=pages).selected_text_by_page == {1: primary}
    final = json.loads(client.requests[-1]["prompt_text"])
    assert final["candidate_pages"][0]["text"] == final["target_units"][0]["text"] == primary
    envelope = json.loads((tmp_path / "audit/correction/raw_response.json").read_bytes())
    assert json.loads(envelope["raw_output"])["pages"][0]["corrected_text"] == visible


@pytest.mark.parametrize("value", [None, "", "unknown", True, 1, [], {}], ids=["none", "empty", "unknown", "bool", "integer", "list", "mapping"])
def test_v5_caller_unit_dependency_rejected_before_evidence_or_dispatch(tmp_path, value):
    client = Client()
    with pytest.raises(review.SemanticAuditError):
        review.run_semantic_review(pages=pack(), recipe=recipe(), pdf_sha256=PDF,
            evidence_dir=tmp_path / "audit", client=client,
            semantic_source_review_policy=policy.POLICY_V5, semantic_unit_reference_policy=value)
    assert client.requests == [] and not (tmp_path / "audit").exists()


def test_saved_v4_ordinary_resume_and_offline_ignore_fresh_v5_selection(tmp_path, monkeypatch):
    from legalpdf_translate import workflow_semantic_audit as glue
    from legalpdf_translate.workflow import TranslationWorkflow
    from tests.test_semantic_review_model_integration import setup, immutable
    fresh = glue.fresh_recipe
    def historical(*args, **kwargs):
        value = fresh(*args, **kwargs)
        value.pop("semantic_repair_policy", None)
        value.pop("semantic_literal_authority_policy", None)
        value.pop("semantic_enclosure_authority_policy", None)
        value["semantic_source_review_policy"] = policy.POLICY_V4
        return value
    monkeypatch.setattr(glue, "fresh_recipe", historical)
    config, http, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    requests, before = deepcopy(http.requests), immutable(result.run_dir)
    monkeypatch.setattr(glue, "fresh_recipe", lambda *args, **kwargs: pytest.fail("Saved V4 consulted fresh V5 selection"))
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert http.requests == requests and immutable(result.run_dir) == before
