"""Fresh request representation only; the old evaluator and raw responses stay exact."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_source_review as policy
from legalpdf_translate.output_normalize import LRI, PDI
from tests.test_ordinary_semantic_unit_refs import Client
from tests.test_ordinary_semantic_review import PDF, pack, recipe


FIXTURE = Path(__file__).parent / "fixtures/semantic_serialization_prechange_3687.json"
OPTIONS = {"semantic_unit_reference_policy": "caller_unit_refs_v1",
           "source_inventory_max_output_tokens": 64000,
           "semantic_page_coverage_policy": "complete_selected_pages_v1"}


def wrapped(value): return LRI + "[[" + value + "]]" + PDI


def run(tmp_path, client, *, pages=None, version=None):
    return review.run_semantic_review(pages=pages or pack(), recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=tmp_path / "audit", client=client, **OPTIONS,
        semantic_source_review_policy=version or policy.POLICY_V4)


def files(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}


@pytest.mark.parametrize("name", ["absent", "explicit_none", "v1", "v2", "v3"])
def test_genuine_3687_requests_full_artifacts_fingerprint_and_replay_exact(tmp_path, name):
    entry = json.loads(FIXTURE.read_bytes())["cases"][name]
    pages = tuple(review.SemanticAuditPage(**p) for p in entry["pages"])
    settings = review.SemanticAuditRecipe(**entry["recipe"])
    args = dict(pages=pages, recipe=settings, pdf_sha256=entry["pdf_sha256"],
                evidence_dir=tmp_path / "audit", **entry["options"])
    client = Client()
    review.run_semantic_review(**args, client=client)
    assert review.audit._json(client.requests) == review.audit._json(entry["requests"])
    before = files(args["evidence_dir"])
    assert before == {name: value.encode() for name, value in entry["evidence"].items()}
    assert review.semantic_review_source_fingerprint(pages, settings, entry["pdf_sha256"], **entry["options"]) == entry["fingerprint"]
    assert review.run_semantic_review(**args, client=client).reused
    assert review.load_semantic_review(**args).reused
    assert len(client.requests) == 3 and files(args["evidence_dir"]) == before


@pytest.mark.parametrize("literal", ["ZX-204", "Évora", "الحقل", r"\u2066", r"\\u2066", 'A"B\\C',
                                    "A\t204", "A\n204", "A\r\n204", "A\r204", "[AB]", "A[B]C"])
def test_projection_preserves_exact_content_whitespace_and_delimiters(literal):
    value = "قبل " + wrapped(literal) + ", " + wrapped(literal) + " بعد"
    expected = "قبل [[" + literal + "]], [[" + literal + "]] بعد"
    assert policy.project_visible_literal_wrappers(value) == expected
    assert policy.project_visible_literal_wrappers(expected) == expected


@pytest.mark.parametrize("control", ["\x00", "\x07", "\u200c", "\u200d", "\u200e", "\u200f", "\u061c", "\u202e"])
def test_other_control_or_format_content_abstains_on_entire_wrapper(control):
    token = wrapped("A" + control + "B")
    value = token + "," + wrapped("C")
    assert policy.project_visible_literal_wrappers(value) == token + ",[[C]]"


@pytest.mark.parametrize("value", [LRI + "[[open", LRI + "[[A]]", wrapped("outer[[inner]]"),
                                  wrapped("A]]B"),
                                  "[[outer " + wrapped("inner") + "]]", wrapped("A" + PDI + "B")])
def test_ambiguous_protocol_candidates_never_expose_and_strip_inner_match(value):
    with pytest.raises(ValueError, match="projection"):
        policy.project_visible_literal_wrappers(value)


@pytest.mark.parametrize("text", ["raw [[ illustration", "raw ]] punctuation", "", "[[]]", "[[A]]", "\u200eArabic\u200f"])
def test_projection_is_not_a_generic_raw_bracket_or_control_validator(text):
    assert policy.project_visible_literal_wrappers(text) == text


def test_unrelated_directional_runs_remain_exact():
    unrelated = LRI + "unrelated text" + PDI + "\u200e"
    assert policy.project_visible_literal_wrappers(unrelated + wrapped("A") + unrelated) == unrelated + "[[A]]" + unrelated


@pytest.mark.parametrize("value", [None, False, [], {}, "x" * 300_001], ids=["none", "boolean", "list", "mapping", "over_bound"])
def test_projection_input_bounds(value):
    with pytest.raises(ValueError): policy.project_visible_literal_wrappers(value)


def test_v4_projects_only_two_correction_fields_and_binds_exact_replacement_metadata():
    entries = json.loads(FIXTURE.read_bytes())["cases"]["absent"]["requests"]
    for stage, request in zip(review.STAGES, entries):
        original = deepcopy(request)
        old = policy.adapt_request(request, stage, encode_payload=review._prompt_json, policy=policy.POLICY_V3)
        new = policy.adapt_request(request, stage, encode_payload=review._prompt_json, policy=policy.POLICY_V4)
        a, b = json.loads(old["prompt_text"]), json.loads(new["prompt_text"])
        old_meta = a.pop("semantic_source_review_policy")
        meta = b.pop("semantic_source_review_policy")
        assert old_meta == policy.descriptor(policy.POLICY_V3)
        assert meta == policy.descriptor(policy.POLICY_V4)
        assert meta["inventory_ambiguity_instruction"] == old_meta["inventory_ambiguity_instruction"]
        assert meta["correction_literal_instruction"] == {
            "replaced_sha256": hashlib.sha256(policy._CORRECTION_LITERAL_OLD.encode()).hexdigest(),
            "replacement_sha256": hashlib.sha256(policy._CORRECTION_LITERAL_NEW.encode()).hexdigest()}
        assert meta["correction_request_projection"] == {
            "version": "correction_visible_literal_wrappers_v1",
            "fields": ["primary_pages[].text", "literal_protocol[].source_text"],
            "semantics_sha256": hashlib.sha256(policy._LITERAL_PROJECTION_SEMANTICS.encode()).hexdigest()}
        if stage == "correction":
            expected = deepcopy(a)
            for collection, field in (("primary_pages", "text"), ("literal_protocol", "source_text")):
                for row in expected[collection]: row[field] = policy.project_visible_literal_wrappers(row[field])
            assert expected == b
            assert new["instructions"] == old["instructions"].replace(policy._CORRECTION_LITERAL_OLD, policy._CORRECTION_LITERAL_NEW) + policy.V4_CORRECTION_ADDITION
        else:
            assert a == b and old["instructions"] == new["instructions"]
        assert {k: v for k, v in old.items() if k not in {"instructions", "prompt_text"}} == {
            k: v for k, v in new.items() if k not in {"instructions", "prompt_text"}}
        assert request == original


@pytest.mark.parametrize("count", [0, 2])
def test_inherited_correction_instruction_drift_fails_closed(count):
    request = deepcopy(json.loads(FIXTURE.read_bytes())["cases"]["absent"]["requests"][1])
    request["instructions"] = request["instructions"].replace(policy._CORRECTION_LITERAL_OLD, policy._CORRECTION_LITERAL_OLD * count)
    with pytest.raises(ValueError, match="Unexpected inherited correction literal"):
        policy.adapt_request(request, "correction", encode_payload=review._prompt_json, policy=policy.POLICY_V4)


@pytest.mark.parametrize("literal", ["Évora", "حقل", r"\u2066", r"\\u2066", 'A"B\\C', "ZX-204"])
def test_visible_provider_response_passes_real_guards_and_verifier_sees_canonical_candidate(tmp_path, literal):
    source = "Source " + wrapped(literal) + "."
    primary = "النص " + wrapped(literal) + "."
    pages = (replace(pack()[0], source_text=source, original_source_text="Source " + literal + ".",
                     source_text_kind="pretokenized", expected_ar_tokens=(literal,), primary_text=primary),)
    visible = "النص [[" + literal + "]]."
    def change(stage, data, payload):
        if stage == "correction":
            assert payload["primary_pages"][0]["text"] == visible
            assert payload["literal_protocol"][0]["source_text"] == "Source [[" + literal + "]]."
            data["pages"][0].update(status="corrected", corrected_text=visible, reason_codes=["literal_fidelity"])
        return data
    client = Client(change)
    result = run(tmp_path, client, pages=pages)
    assert result.selected_text_by_page == {1: primary}
    final = json.loads(client.requests[-1]["prompt_text"])
    assert final["candidate_pages"][0]["text"] == primary
    assert final["target_units"][0]["text"] == primary
    envelope = json.loads((tmp_path / "audit/correction/raw_response.json").read_bytes())
    assert json.loads(envelope["raw_output"])["pages"][0]["corrected_text"] == visible
    before = files(tmp_path / "audit")
    assert run(tmp_path, client, pages=pages).reused
    assert len(client.requests) == 3 and files(tmp_path / "audit") == before


@pytest.mark.parametrize("defect", ["value", "literal_loss", "unresolved", "missing", "wrong_owner", "inventory_error"])
def test_existing_strict_failure_outcomes_remain_without_repurchase(tmp_path, defect):
    pages = tuple(replace(p, primary_text="النص " + wrapped("ZX-204") + ".", expected_ar_tokens=("ZX-204",),
                          source_text="Source " + wrapped("ZX-204") + ".", source_text_kind="pretokenized") for p in pack(count=2))
    def damage(stage, data, payload):
        if stage == "correction" and defect in {"value", "literal_loss"}:
            data["pages"][0].update(status="corrected", corrected_text="النص [[ZX-205]]." if defect == "value" else "النص.", reason_codes=["literal_fidelity"])
        if stage == "verification":
            if defect in {"unresolved", "missing"}: data["claim_results"][0]["status"] = defect
            if defect == "wrong_owner": data["claim_results"][0]["target_unit_ids"] = ["T002"]
            if defect == "inventory_error": data["inventory_errors"] = [{"source_unit_ids": ["S001"], "reason": "A source qualification is missing from the inventory."}]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pages=pages)
    sent = len(client.requests); before = files(tmp_path / "audit")
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client, pages=pages)
    assert len(client.requests) == sent and files(tmp_path / "audit") == before
    assert not (tmp_path / "audit/manifest.json").exists()


def test_malformed_projection_blocks_correction_dispatch_after_one_settled_inventory(tmp_path):
    pages = (replace(pack()[0], primary_text=LRI + "[[unterminated"),)
    client = Client()
    with pytest.raises(ValueError, match="projection"): run(tmp_path, client, pages=pages)
    assert len(client.requests) == 1
    assert (tmp_path / "audit/source_inventory/raw_response.json").is_file()
    assert not (tmp_path / "audit/correction").exists()
    before = files(tmp_path / "audit")
    with pytest.raises(ValueError, match="projection"): run(tmp_path, client, pages=pages)
    assert len(client.requests) == 1 and files(tmp_path / "audit") == before


@pytest.mark.parametrize("previous", [None, policy.POLICY, policy.POLICY_V2, policy.POLICY_V3])
def test_no_silent_saved_upgrade_to_v4(tmp_path, previous):
    client = Client(); args = dict(pages=pack(), recipe=recipe(), pdf_sha256=PDF, evidence_dir=tmp_path / "audit", **OPTIONS)
    review.run_semantic_review(**args, client=client, semantic_source_review_policy=previous)
    before = files(tmp_path / "audit")
    with pytest.raises(review.SemanticAuditError, match="binding"):
        review.run_semantic_review(**args, client=client, semantic_source_review_policy=policy.POLICY_V4)
    assert len(client.requests) == 3 and files(tmp_path / "audit") == before


def test_empty_unambiguous_wrapper_is_retained_not_claimed_valid():
    empty = wrapped("")
    assert policy.project_visible_literal_wrappers(empty + wrapped("A")) == empty + "[[A]]"
    # Request representation makes no assertion that an empty token validates.


def test_exact_resource_bound_and_adjacent_repeated_wrappers():
    assert policy.project_visible_literal_wrappers("x" * 300_000) == "x" * 300_000
    assert policy.project_visible_literal_wrappers(wrapped("A") * 3) == "[[A]]" * 3


def test_repeated_visible_literal_response_keeps_multiplicity_and_canonical_bytes(tmp_path):
    literal = "Á-24"
    primary = "النص " + wrapped(literal) + ", " + wrapped(literal) + "."
    pages = (replace(pack()[0], source_text="Source " + wrapped(literal) + ", " + wrapped(literal) + ".",
                     original_source_text="Source " + literal + ", " + literal + ".",
                     source_text_kind="pretokenized", expected_ar_tokens=(literal, literal), primary_text=primary),)
    def change(stage, data, payload):
        if stage == "correction":
            data["pages"][0].update(status="corrected", corrected_text=primary.replace(LRI, "").replace(PDI, ""), reason_codes=["literal_fidelity"])
        return data
    result = run(tmp_path, Client(change), pages=pages)
    assert result.selected_text_by_page[1] == primary


def test_saved_v3_ordinary_native_resume_and_offline_keep_old_request_bytes(tmp_path, monkeypatch):
    from legalpdf_translate import workflow_semantic_audit as glue
    from legalpdf_translate.workflow import TranslationWorkflow
    from tests.test_semantic_review_model_integration import setup, immutable
    fresh = glue.fresh_recipe
    def historical(*args, **kwargs):
        value = fresh(*args, **kwargs)
        value.pop("semantic_repair_policy", None)
        value.pop("semantic_literal_authority_policy", None)
        value.pop("semantic_enclosure_authority_policy", None)
        value["semantic_source_review_policy"] = policy.POLICY_V3
        return value
    monkeypatch.setattr(glue, "fresh_recipe", historical)
    config, http, flow = setup(tmp_path)
    result = flow.run(config)
    assert result.success, result.error
    assert [r["model"] for r in http.requests] == ["gpt-5.2"] + ["gpt-6-astra"] * 3
    before = immutable(result.run_dir)
    requests = deepcopy(http.requests)
    monkeypatch.setattr(glue, "fresh_recipe", lambda *a, **k: pytest.fail("Saved V3 consulted fresh V4 selection"))
    assert flow.run(replace(config, resume=True)).success
    assert TranslationWorkflow(gui_settings={}).rebuild_docx(config).is_file()
    assert http.requests == requests and immutable(result.run_dir) == before


@pytest.mark.parametrize("tamper", ["semantics", "projected_request"])
def test_projection_identity_or_effective_request_tamper_cannot_reuse_settlement(tmp_path, monkeypatch, tamper):
    client = Client()
    run(tmp_path, client)
    before = files(tmp_path / "audit")
    if tamper == "semantics":
        monkeypatch.setattr(policy, "_LITERAL_PROJECTION_SEMANTICS", policy._LITERAL_PROJECTION_SEMANTICS + " Changed projection.")
    else:
        original = policy.project_visible_literal_wrappers
        monkeypatch.setattr(policy, "project_visible_literal_wrappers", lambda text: original(text) + " ")
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
    assert len(client.requests) == 3 and files(tmp_path / "audit") == before


@pytest.mark.parametrize("opener", [LRI, "\u2067", "\u2068"])
@pytest.mark.parametrize("balanced", [False, True])
@pytest.mark.parametrize("prose", ["", "نص محيط "])
def test_ambient_isolation_only_causes_whole_token_abstention(opener, balanced, prose):
    prefix = opener + prose
    suffix = PDI if balanced else ""
    first, last = wrapped("A-47"), wrapped("B-58")
    value = prefix + first + suffix + "," + last
    expected = prefix + first + suffix + "," + ("[[B-58]]" if balanced else last)
    assert policy.project_visible_literal_wrappers(value) == expected
