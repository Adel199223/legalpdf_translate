"""Versioned ambiguity instructions; controlled responses are not quality proof."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_source_review as policy
from legalpdf_translate import ordinary_semantic_unit_refs as refs
from tests.test_ordinary_semantic_review import PDF, pack, recipe
from tests.test_ordinary_semantic_unit_refs import Client, response


@pytest.fixture
def requests(tmp_path):
    client = Client()
    review.run_semantic_review(
        pages=pack(count=2), recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=tmp_path / "compact", client=client,
        semantic_unit_reference_policy=refs.POLICY,
    )
    return client.requests


def adapt(request, stage, value=policy.POLICY_V2):
    return policy.adapt_request(
        request, stage, encode_payload=review._prompt_json, policy=value,
    )


def test_genuine_v1_descriptor_and_default_adapter_remain_exact(requests):
    golden = json.loads(
        (Path(__file__).parent / "fixtures/source_review_policy_v1_golden.json").read_bytes()
    )
    assert policy.descriptor() == policy.descriptor(policy.POLICY) == golden["descriptor"]
    for stage, original in zip(review.STAGES, requests):
        expected = deepcopy(original)
        payload = json.loads(original["prompt_text"])
        payload["semantic_source_review_policy"] = golden["descriptor"]
        expected["prompt_text"] = review._prompt_json(payload)
        expected["instructions"] += policy.SUFFIXES[stage]
        default = policy.adapt_request(original, stage, encode_payload=review._prompt_json)
        assert review.audit._json(default) == review.audit._json(expected)
        assert default == adapt(original, stage, policy.POLICY)
        assert hashlib.sha256(policy.SUFFIXES[stage].encode()).hexdigest() == (
            golden["descriptor"]["stage_instruction_sha256"][stage]
        )


def test_v2_changes_only_versioned_instructions_and_descriptor(requests):
    before = deepcopy(requests)
    descriptor = policy.descriptor(policy.POLICY_V2)
    assert descriptor["inventory_ambiguity_instruction"] == {
        "replaced_sha256": hashlib.sha256(policy._INVENTORY_OLD_AMBIGUITY.encode()).hexdigest(),
        "replacement_sha256": hashlib.sha256(policy._INVENTORY_NEW_AMBIGUITY.encode()).hexdigest(),
    }
    for stage, original in zip(review.STAGES, requests):
        result = adapt(original, stage)
        assert {k: v for k, v in result.items() if k not in ("instructions", "prompt_text")} == {
            k: v for k, v in original.items() if k not in ("instructions", "prompt_text")
        }
        payload = json.loads(result["prompt_text"])
        assert payload.pop("semantic_source_review_policy") == descriptor
        assert payload == json.loads(original["prompt_text"])
        suffix = policy.SUFFIXES[stage].replace(
            policy._SHARED_OLD_AMBIGUITY, policy._SHARED_NEW_AMBIGUITY,
        )
        inherited = original["instructions"]
        if stage == "source_inventory":
            inherited = inherited.replace(
                policy._INVENTORY_OLD_AMBIGUITY, policy._INVENTORY_NEW_AMBIGUITY,
            )
            assert result["instructions"].count(policy._INVENTORY_NEW_AMBIGUITY) == 1
            assert policy._INVENTORY_OLD_AMBIGUITY not in result["instructions"]
        else:
            assert policy._INVENTORY_NEW_AMBIGUITY not in result["instructions"]
        assert result["instructions"] == inherited + suffix
        assert policy._SHARED_OLD_AMBIGUITY not in result["instructions"]
        assert hashlib.sha256(suffix.encode()).hexdigest() == (
            descriptor["stage_instruction_sha256"][stage]
        )
    assert requests == before


@pytest.mark.parametrize("value", [None, "", "unknown", True, False, 0, [], {}])
def test_invalid_policy_never_adapts(requests, value):
    with pytest.raises(ValueError, match="Invalid source review policy"):
        adapt(requests[0], "source_inventory", value)
    with pytest.raises(ValueError):
        policy.descriptor(value)
    with pytest.raises(ValueError):
        policy.check_policy(value, refs.POLICY)


@pytest.mark.parametrize("dependency", [None, "", "unknown", True, [], {}])
def test_v2_requires_compact_reference_policy(dependency):
    with pytest.raises(ValueError):
        policy.check_policy(policy.POLICY_V2, dependency)
    policy.check_policy(policy.POLICY_V2, refs.POLICY)


@pytest.mark.parametrize("count", [0, 2])
def test_v2_fails_if_inherited_ambiguity_instruction_drifts(requests, count):
    request = deepcopy(requests[0])
    request["instructions"] = request["instructions"].replace(
        policy._INVENTORY_OLD_AMBIGUITY, policy._INVENTORY_OLD_AMBIGUITY * count,
    )
    with pytest.raises(ValueError, match="Unexpected inherited source ambiguity"):
        adapt(request, "source_inventory")


def test_v2_shared_instruction_drift_is_not_silently_accepted(requests, monkeypatch):
    monkeypatch.setitem(
        policy.SUFFIXES, "verification",
        policy.SUFFIXES["verification"].replace(policy._SHARED_OLD_AMBIGUITY, ""),
    )
    with pytest.raises(ValueError, match="Unexpected legacy source ambiguity"):
        adapt(requests[0], "source_inventory")


@pytest.mark.parametrize("defect", ["already_adapted", "wrong_stage", "missing_dependency"])
def test_malformed_request_is_rejected(requests, defect):
    request = deepcopy(requests[0])
    if defect == "already_adapted":
        request = adapt(request, "source_inventory")
    else:
        payload = json.loads(request["prompt_text"])
        if defect == "wrong_stage":
            payload["stage"] = "correction"
        else:
            del payload["semantic_unit_reference_policy"]
        request["prompt_text"] = review._prompt_json(payload)
    with pytest.raises(ValueError, match="Invalid source review policy request"):
        adapt(request, "source_inventory")


@pytest.mark.parametrize("defect", ["unresolved", "temporal", "number", "boundary"])
def test_v2_does_not_weaken_existing_unresolved_validators(requests, defect):
    request = adapt(requests[0], "source_inventory")
    payload = json.loads(request["prompt_text"])
    raw = response("source_inventory", payload)
    if defect == "unresolved":
        raw["claims"][0]["unresolved"] = True
    elif defect == "temporal":
        raw["claims"][0]["axes"]["temporal_state"] = "uncertain"
    elif defect == "number":
        raw["claims"][0]["axes"]["participant_number"] = "uncertain"
    else:
        raw["boundaries"][0]["relation"] = "uncertain"
    units = review.source_units(pack(count=2))
    canonical, _ = refs.hydrate(json.dumps(raw), "source_inventory", request, units)
    with pytest.raises(review.SemanticAuditError, match="review_source_unresolved"):
        review.validate_source_inventory(json.dumps(canonical), pack(count=2), units)
