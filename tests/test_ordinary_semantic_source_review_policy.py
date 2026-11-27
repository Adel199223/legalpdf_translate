"""Versioned request identity and strict failure/replay, never model quality."""
from dataclasses import replace, fields
from pathlib import Path
import hashlib
import json
import re

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_source_review as policy
from legalpdf_translate import ordinary_semantic_unit_refs as refs
from legalpdf_translate.openai_client import ApiCallError
from legalpdf_translate.output_normalize import LRI, PDI
from tests.test_ordinary_semantic_review import pack, recipe, PDF, Client as LegacyClient
from tests.test_ordinary_semantic_unit_refs import Client, response

KEY = "semantic_source_review_policy"
OPTIONS = {KEY: policy.POLICY, "semantic_unit_reference_policy": refs.POLICY,
           "source_inventory_max_output_tokens": 64000}


def snapshot(folder):
    return {p.relative_to(folder).as_posix(): p.read_bytes()
            for p in folder.rglob("*") if p.is_file()}


def run(folder, client=None, pages=None, settings=None, **kwargs):
    return review.run_semantic_review(pages=pages or pack(), recipe=settings or recipe(),
        pdf_sha256=PDF, evidence_dir=folder, client=client, **{**OPTIONS, **kwargs})


def test_three_stage_descriptor_bound_requests_and_local_replay(tmp_path):
    client = Client()
    settings = recipe(context_text="Fictional unique terminology preference.")
    result = run(tmp_path / "audit", client, pack(count=2), settings)
    binding = json.loads((tmp_path / "audit/intent.json").read_bytes())
    assert binding[KEY] == policy.descriptor()
    assert KEY not in {f.name for f in fields(review.SemanticAuditRecipe)}
    assert [r["max_output_tokens"] for r in client.requests] == [64000, 32000, 32000]
    for stage, request in zip(review.STAGES, client.requests):
        payload = json.loads(request["prompt_text"])
        assert payload[KEY] == policy.descriptor()
        assert payload["protocol"] == refs.PROTOCOL
        assert request["response_format"]["name"] == refs.VERSIONS[review.STAGES.index(stage)]
        assert request["instructions"].endswith(policy.SUFFIXES[stage])
        assert request["effort"] == "high" and request["timeout_seconds"] == 480
        assert request["image_data_urls"] == tuple(p.image_data_url for p in pack(count=2))
        assert ("context_text" in payload) is (stage == "correction")
        if stage != "correction":
            assert settings.context_text not in request["prompt_text"]
            assert "primary_pages" not in payload
        if stage == "verification":
            assert "reason_codes" not in request["prompt_text"] and "claim_coverage" not in payload
        intent = json.loads((tmp_path / "audit" / stage / "intent.json").read_bytes())
        derived = json.loads((tmp_path / "audit" / stage / "derived_response.json").read_bytes())
        digest = review.audit._sha(review.audit._json(request))
        assert intent["request_sha256"] == derived["request_sha256"] == digest
    before = snapshot(tmp_path / "audit")
    loaded = review.load_semantic_review(pages=pack(count=2), recipe=settings,
        pdf_sha256=PDF, evidence_dir=tmp_path / "audit", **OPTIONS)
    assert loaded.reused and loaded.usage == result.usage and len(client.requests) == 3
    assert snapshot(tmp_path / "audit") == before


@pytest.mark.parametrize("case", ["legacy_absent", "compact32", "compact64", "compact64_unresolved"])
def test_genuine_007_absence_none_requests_bindings_raw_derived_manifest_exact(tmp_path, case):
    fixture = json.loads((Path(__file__).parent / "fixtures/semantic_source_review_prechange_007.json").read_bytes())["cases"][case]
    pages = tuple(review.SemanticAuditPage(**p) for p in fixture["pages"])
    settings = review.SemanticAuditRecipe(**fixture["recipe"])
    def damage(stage, data, payload):
        if stage == "source_inventory": data["claims"][0]["axes"]["temporal_state"] = "uncertain"
        return data
    for explicit_none in (False, True):
        folder = tmp_path / str(explicit_none)
        options = dict(fixture["policy_options"])
        if explicit_none: options[KEY] = None
        client = LegacyClient() if case == "legacy_absent" else Client(damage if fixture["expected_error"] else None)
        client.model = "gpt-5.2"
        arguments = dict(pages=pages, recipe=settings, pdf_sha256=fixture["pdf_sha256"], evidence_dir=folder, **options)
        if fixture["expected_error"]:
            with pytest.raises(review.SemanticAuditError, match=re.escape(fixture["expected_error"])):
                review.run_semantic_review(**arguments, client=client)
        else:
            review.run_semantic_review(**arguments, client=client)
        assert review.audit._json(client.requests) == review.audit._json(fixture["requests"])
        assert snapshot(folder) == {n: text.encode() for n, text in fixture["evidence"].items()}
        assert review.semantic_review_source_fingerprint(pages, settings, fixture["pdf_sha256"], **options) == fixture["fingerprint"]
        before = snapshot(folder)
        if fixture["expected_error"]:
            with pytest.raises(review.SemanticAuditError, match=re.escape(fixture["expected_error"])): review.load_semantic_review(**arguments)
        else:
            assert review.load_semantic_review(**arguments).reused
        assert snapshot(folder) == before and len(client.requests) == fixture["fake_calls"]


@pytest.mark.parametrize("value", ["unknown", "", True, False, 0, [], {}])
def test_invalid_policy_stops_before_dispatch_or_evidence(tmp_path, value):
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="review_source_policy"):
        run(tmp_path / "audit", client, **{KEY: value})
    with pytest.raises(review.SemanticAuditError, match="review_source_policy"):
        review.semantic_review_source_fingerprint(pack(), recipe(), PDF, **{**OPTIONS, KEY: value})
    assert not client.requests and not (tmp_path / "audit").exists()


@pytest.mark.parametrize("dependency", [None, "unknown"])
def test_policy_requires_caller_unit_refs_before_any_call(tmp_path, dependency):
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="review_source_policy"):
        run(tmp_path / "audit", client, semantic_unit_reference_policy=dependency,
            source_inventory_max_output_tokens=None)
    assert not client.requests and not (tmp_path / "audit").exists()


def test_policy_or_any_stage_suffix_change_cannot_upgrade_saved_evidence(tmp_path, monkeypatch):
    client = Client()
    run(tmp_path / "old", client, **{KEY: None})
    before = snapshot(tmp_path / "old")
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"):
        run(tmp_path / "old", client)
    assert len(client.requests) == 3 and snapshot(tmp_path / "old") == before
    run(tmp_path / "new", client)
    before = snapshot(tmp_path / "new")
    monkeypatch.setitem(policy.SUFFIXES, "verification", policy.VERIFICATION + "\nChanged generic instruction.")
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"):
        run(tmp_path / "new", client)
    assert len(client.requests) == 6 and snapshot(tmp_path / "new") == before


@pytest.mark.parametrize("uncertain", [False, True])
def test_reported_past_can_preserve_epistemic_status_but_real_uncertainty_still_blocks(tmp_path, uncertain):
    source = "An unnamed worker reported that a delivery had occurred; its truth is disputed."
    pages = (replace(pack()[0], source_text=source, original_source_text=source,
                     primary_text="أفاد عامل بأن التسليم كان قد تم، مع بقاء صحة الإفادة محل خلاف."),)
    def damage(stage, data, payload):
        if stage == "source_inventory":
            claim = data["claims"][0]
            claim["axes"]["temporal_state"] = "uncertain" if uncertain else "completed"
            claim["axes"]["polarity_modality"] = "reported allegation; truth disputed"
            claim["axes"]["actor_recipient"] = "unnamed reporting worker; delivery actor unspecified"
        return data
    client = Client(damage)
    if uncertain:
        with pytest.raises(review.SemanticAuditError, match="review_source_unresolved"):
            run(tmp_path / "audit", client, pages)
        assert len(client.requests) == 1 and not (tmp_path / "audit/correction").exists()
    else:
        assert run(tmp_path / "audit", client, pages).selected_text_by_page[1] == pages[0].primary_text
    # These controlled responses exercise unchanged validators, not inference.


@pytest.mark.parametrize("reason", ["A condition was omitted.", "A generic role acquired an unsupported identity.",
    "A prospective act became a completed act.", "A documentary resultative state became future action."])
def test_independent_semantic_challenges_still_stop_final_selection(tmp_path, reason):
    def damage(stage, data, payload):
        if stage == "verification": data["inventory_errors"] = [{"source_unit_ids": ["S001"], "reason": reason}]
        return data
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError, match="review_independent_verification_failed"):
        run(tmp_path / "audit", client)
    assert len(client.requests) == 3 and not (tmp_path / "audit/manifest.json").exists()


@pytest.mark.parametrize("kind", ["pending", "usage_unknown", "incomplete", "cancelled"])
def test_enabled_policy_preserves_settlement_stop_no_repeat(tmp_path, kind):
    stopped = False
    class StopClient(Client):
        def create_page_response(self, **request):
            nonlocal stopped
            if kind == "pending":
                self.requests.append(request)
                raise RuntimeError("fictional uncertain transport")
            value = super().create_page_response(**request)
            if kind == "usage_unknown": return replace(value, usage={})
            if kind == "incomplete":
                return replace(value, response_status="incomplete", incomplete_reason="max_output_tokens")
            stopped = True
            return value
    client = StopClient()
    expected = {"pending": "provider_operation_unsettled", "usage_unknown": "usage_unknown_or_unsettled",
                "incomplete": "provider_incomplete", "cancelled": "operation_cancelled"}[kind]
    with pytest.raises(review.SemanticAuditError, match=expected):
        run(tmp_path / "audit", client, cancel_check=(lambda: stopped) if kind == "cancelled" else None)
    before = snapshot(tmp_path / "audit")
    assert not (tmp_path / "audit/correction").exists() and not (tmp_path / "audit/manifest.json").exists()
    if kind != "cancelled":
        with pytest.raises(review.SemanticAuditError): run(tmp_path / "audit", client)
        assert len(client.requests) == 1 and snapshot(tmp_path / "audit") == before
    else:
        # A settled cancelled stage may validate locally, but cannot dispatch
        # a missing next stage without a client or publish a final selection.
        with pytest.raises(review.SemanticAuditError): run(tmp_path / "audit")
        assert len(client.requests) == 1


@pytest.mark.parametrize("name", ["source_inventory/derived_response.json", "source_inventory/raw_response.json", "source_inventory/intent.json"])
def test_new_policy_retained_tampering_is_rejected_without_another_send(tmp_path, name):
    client = Client()
    run(tmp_path / "audit", client)
    path = tmp_path / "audit" / name
    data = json.loads(path.read_bytes())
    data["tampered"] = True
    path.write_bytes(json.dumps(data).encode())
    with pytest.raises(review.SemanticAuditError): run(tmp_path / "audit", client)
    assert len(client.requests) == 3
