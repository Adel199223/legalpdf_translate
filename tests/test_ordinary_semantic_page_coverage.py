"""Complete selected-page requests retain strict proof and historical replay."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_page_coverage as policy
from tests.test_ordinary_semantic_review import pack, recipe, PDF, Client as LegacyClient
from tests.test_ordinary_semantic_unit_refs import Client

KEY = policy.KEY
OPTIONS = {KEY: policy.POLICY, "semantic_unit_reference_policy": "caller_unit_refs_v1",
           "semantic_source_review_policy": "source_commitment_visual_v1",
           "source_inventory_max_output_tokens": 64000}


def pages():
    return tuple(replace(page, page_number=n) for page, n in zip(pack(count=3), (2, 5, 8)))


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in folder.rglob("*") if p.is_file()}


def run(folder, client=None, **kwargs):
    return review.run_semantic_review(pages=pages(), recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=folder, client=client, **{**OPTIONS, **kwargs})


def test_request_exact_selected_count_enum_wording_binding_and_zero_call_replay(tmp_path):
    tmp_path = tmp_path / "audit"
    client = Client()
    result = run(tmp_path, client)
    binding = json.loads((tmp_path / "intent.json").read_bytes())
    assert binding[KEY] == policy.descriptor([2, 5, 8])
    assert [r["max_output_tokens"] for r in client.requests] == [64000, 32000, 32000]
    for stage, request in zip(review.STAGES, client.requests):
        assert json.loads(request["prompt_text"])[KEY] == binding[KEY]
        assert request["effort"] == "high" and request["timeout_seconds"] == 480
        if stage == "correction":
            schema = request["response_format"]["schema"]["properties"]["pages"]
            assert schema["minItems"] == schema["maxItems"] == 3
            assert schema["items"]["properties"]["page_number"] == {"type": "integer", "enum": [2, 5, 8]}
            assert policy.OLD_SENTENCE not in request["instructions"]
            assert request["instructions"].count(policy.NEW_SENTENCE) == 1
        else:
            assert policy.NEW_SENTENCE not in request["instructions"]
    assert policy.OLD_SENTENCE in review._CORRECTION
    assert result.selected_text_by_page == {p.page_number: p.primary_text for p in pages()}
    before = snapshot(tmp_path)
    loaded = review.load_semantic_review(pages=pages(), recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=tmp_path, **OPTIONS)
    assert loaded.reused and loaded.usage == result.usage
    assert snapshot(tmp_path) == before and len(client.requests) == 3


@pytest.mark.parametrize("count", [1, 12])
def test_dynamic_schema_uses_actual_selection_boundaries(tmp_path, count):
    tmp_path = tmp_path / "audit"
    client = Client()
    selected = pack(count=count)
    review.run_semantic_review(pages=selected, recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=tmp_path, client=client, **OPTIONS)
    schema = client.requests[1]["response_format"]["schema"]["properties"]["pages"]
    assert schema["minItems"] == schema["maxItems"] == count
    assert schema["items"]["properties"]["page_number"]["enum"] == list(range(1, count + 1))


@pytest.mark.parametrize("defect", ["empty", "sparse", "duplicate", "unselected", "out_of_order", "boolean_identity"])
def test_unchanged_deterministic_validator_rejects_bad_page_coverage_without_verifier(tmp_path, defect):
    tmp_path = tmp_path / "audit"
    def damage(stage, data, payload):
        if stage == "correction":
            rows = data["pages"]
            if defect == "empty": data["pages"] = []
            elif defect == "sparse": data["pages"] = rows[:1]
            elif defect == "duplicate": rows[1] = deepcopy(rows[0])
            elif defect == "unselected": rows[1]["page_number"] = 7
            elif defect == "boolean_identity": rows[0]["page_number"] = True
            else: data["pages"] = rows[::-1]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
    assert len(client.requests) == 2
    assert (tmp_path / "correction/raw_response.json").is_file()
    assert (tmp_path / "correction/raw_receipt.json").is_file()
    assert not (tmp_path / "verification").exists()
    assert not (tmp_path / "manifest.json").exists()
    before = snapshot(tmp_path)
    with pytest.raises(review.SemanticAuditError): run(tmp_path, client)
    assert snapshot(tmp_path) == before and len(client.requests) == 2


@pytest.mark.parametrize("value", ["unknown", "", True, 0, [], {}])
def test_invalid_policy_fails_before_evidence_or_dispatch(tmp_path, value):
    tmp_path = tmp_path / "audit"
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="review_page_coverage_policy"):
        run(tmp_path / "audit", client, **{KEY: value})
    with pytest.raises(review.SemanticAuditError, match="review_page_coverage_policy"):
        review.semantic_review_source_fingerprint(pages(), recipe(), PDF, **{**OPTIONS, KEY: value})
    assert not client.requests and not (tmp_path / "audit").exists()


@pytest.mark.parametrize("dependency", [None, "unknown"])
def test_caller_refs_required_before_dispatch(tmp_path, dependency):
    tmp_path = tmp_path / "audit"
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="review_page_coverage_policy"):
        run(tmp_path, client, semantic_unit_reference_policy=dependency,
            semantic_source_review_policy=None, source_inventory_max_output_tokens=None)
    assert not client.requests and not tmp_path.joinpath("intent.json").exists()


@pytest.mark.parametrize("case", ["legacy_absent", "compact32", "compact64", "source_commitment_v1"])
def test_genuine_365_requests_artifacts_and_replay_exact_for_absence_and_none(tmp_path, case):
    tmp_path = tmp_path / "audit"
    golden = json.loads((Path(__file__).parent / "fixtures/semantic_page_coverage_prechange_365.json").read_bytes())["cases"][case]
    selected = tuple(review.SemanticAuditPage(**p) for p in golden["pages"])
    settings = review.SemanticAuditRecipe(**golden["recipe"])
    for explicit_none in (False, True):
        options = dict(golden["policy_options"])
        if explicit_none: options[KEY] = None
        folder = tmp_path / str(explicit_none)
        client = LegacyClient() if case == "legacy_absent" else Client()
        client.model = settings.model
        args = dict(pages=selected, recipe=settings, pdf_sha256=golden["pdf_sha256"], evidence_dir=folder, **options)
        review.run_semantic_review(**args, client=client)
        assert review.audit._json(client.requests) == review.audit._json(golden["requests"])
        assert snapshot(folder) == {n: value.encode() for n, value in golden["evidence"].items()}
        assert review.semantic_review_source_fingerprint(selected, settings, golden["pdf_sha256"], **options) == golden["fingerprint"]
        before = snapshot(folder)
        assert review.load_semantic_review(**args).reused
        assert snapshot(folder) == before and len(client.requests) == 3


def test_saved_policy_or_exact_wording_cannot_silently_upgrade_evidence(tmp_path, monkeypatch):
    tmp_path = tmp_path / "audit"
    client = Client()
    run(tmp_path / "old", client, **{KEY: None})
    before = snapshot(tmp_path / "old")
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"):
        run(tmp_path / "old", client)
    assert snapshot(tmp_path / "old") == before and len(client.requests) == 3
    run(tmp_path / "new", client)
    before = snapshot(tmp_path / "new")
    monkeypatch.setattr(policy, "NEW_SENTENCE", policy.NEW_SENTENCE + " A changed instruction.")
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"):
        run(tmp_path / "new", client)
    assert snapshot(tmp_path / "new") == before and len(client.requests) == 6


@pytest.mark.parametrize("defect", ["missing_sentence", "duplicated_sentence", "unexpected_schema", "wrong_selection"])
def test_adapter_refuses_unexpected_old_instruction_or_schema_without_mutation(defect):
    # Build an authentic compact correction request with the same immutable map.
    selected = pages(); units = review.source_units(selected)
    from legalpdf_translate import ordinary_semantic_unit_refs as refs
    inv_request = refs.adapt_request(review._request("source_inventory", selected, recipe(), PDF, units), "source_inventory", units)
    from tests.test_ordinary_semantic_unit_refs import response
    canonical, _ = refs.hydrate(json.dumps(response("source_inventory", json.loads(inv_request["prompt_text"]))), "source_inventory", inv_request, units)
    request = refs.adapt_request(review._request("correction", selected, recipe(), PDF, units, inventory=canonical), "correction", units)
    if defect == "missing_sentence": request["instructions"] = request["instructions"].replace(policy.OLD_SENTENCE, "Changed")
    elif defect == "duplicated_sentence": request["instructions"] += policy.OLD_SENTENCE
    elif defect == "unexpected_schema": request["response_format"]["schema"]["properties"]["pages"]["maxItems"] = 2
    original = deepcopy(request)
    with pytest.raises(ValueError):
        policy.adapt_request(request, "correction", [2, 5, 9] if defect == "wrong_selection" else [2, 5, 8], encode_payload=review._prompt_json)
    assert request == original


def test_only_intended_correction_instruction_and_schema_change(tmp_path):
    old, new = Client(), Client()
    run(tmp_path / "old", old, **{KEY: None})
    run(tmp_path / "new", new)
    for stage, before, after in zip(review.STAGES, old.requests, new.requests):
        old_payload, new_payload = json.loads(before["prompt_text"]), json.loads(after["prompt_text"])
        assert new_payload.pop(KEY) == policy.descriptor([2, 5, 8])
        assert new_payload == old_payload
        expected = deepcopy(before)
        expected["prompt_text"] = after["prompt_text"]
        if stage == "correction":
            expected["instructions"] = expected["instructions"].replace(policy.OLD_SENTENCE, policy.NEW_SENTENCE)
            array = expected["response_format"]["schema"]["properties"]["pages"]
            array.update({"minItems": 3, "maxItems": 3})
            array["items"]["properties"]["page_number"]["enum"] = [2, 5, 8]
        assert expected == after
