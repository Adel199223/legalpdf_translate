"""Saved inventory-only output bounds; entirely fictional and provider-free."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from legalpdf_translate import ordinary_semantic_review as review
from legalpdf_translate import ordinary_semantic_unit_refs as refs
from legalpdf_translate.openai_client import ApiCallError
from tests.test_ordinary_semantic_review import pack, recipe, PDF
from tests.test_ordinary_semantic_unit_refs import Client, run, response


def snapshot(directory):
    return {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()}


def test_inventory_only_cap_bound_to_source_stage_request_and_derivation(tmp_path):
    client = Client()
    result = run(tmp_path, client, source_inventory_max_output_tokens=64000)
    assert [r["max_output_tokens"] for r in client.requests] == [64000, 32000, 32000]
    assert all(r["timeout_seconds"] == 480 for r in client.requests)
    assert recipe().max_output_tokens == 32000
    directory = result.manifest_path.parent
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["binding"]["source_inventory_max_output_tokens"] == 64000
    assert manifest["binding"]["recipe_sha256"] == review._prepare(pack(), recipe(), PDF, refs.POLICY)[2]["recipe_sha256"]
    fingerprint = review.semantic_review_source_fingerprint(pack(), recipe(), PDF,
        semantic_unit_reference_policy=refs.POLICY, source_inventory_max_output_tokens=64000)
    assert result.binding_sha256 == fingerprint
    assert fingerprint != review.semantic_review_source_fingerprint(pack(), recipe(), PDF,
        semantic_unit_reference_policy=refs.POLICY)
    for stage, request in zip(review.STAGES, client.requests):
        intent = json.loads((directory / stage / "intent.json").read_text())
        derived = json.loads((directory / stage / "derived_response.json").read_text())
        assert intent["review_binding_sha256"] == fingerprint
        assert intent["request_sha256"] == derived["request_sha256"] == review.audit._sha(review.audit._json(request))
    before = snapshot(directory)
    loaded = review.load_semantic_review(pages=pack(), recipe=recipe(), pdf_sha256=PDF,
        evidence_dir=directory, semantic_unit_reference_policy=refs.POLICY,
        source_inventory_max_output_tokens=64000)
    assert loaded.reused and loaded.selected_text_by_page == result.selected_text_by_page
    assert snapshot(directory) == before and len(client.requests) == 3


@pytest.mark.parametrize("budget", [True, False, 64000.0, "64000", 32000, 63999, 64001, 128000, 0, -1])
def test_invalid_budget_fails_before_evidence_or_dispatch(tmp_path, budget):
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="review_inventory_output_budget"):
        run(tmp_path, client, source_inventory_max_output_tokens=budget)
    assert not client.requests and not (tmp_path / "audit").exists()
    with pytest.raises(review.SemanticAuditError, match="review_inventory_output_budget"):
        review.semantic_review_source_fingerprint(pack(), recipe(), PDF,
            semantic_unit_reference_policy=refs.POLICY, source_inventory_max_output_tokens=budget)


@pytest.mark.parametrize("policy", [None, "other", True])
def test_override_requires_compact_policy(tmp_path, policy):
    client = Client()
    with pytest.raises(review.SemanticAuditError, match="review_inventory_output_budget"):
        review.run_semantic_review(pages=pack(), recipe=recipe(), pdf_sha256=PDF,
            evidence_dir=tmp_path / "audit", client=client,
            semantic_unit_reference_policy=policy, source_inventory_max_output_tokens=64000)
    assert not client.requests and not (tmp_path / "audit").exists()


def test_genuine_prechange_compact_32k_identity_fresh_bytes_and_offline_replay(tmp_path):
    fixture = json.loads((Path(__file__).parent / "fixtures/semantic_unit_refs/compact_32k_b4b1.json").read_text())
    assert fixture["engine_sha256"] == "b4b13398b5bd5660ba3c327aec65c29a49537c0882566bf0d6365ff328a57efe"
    pages = tuple(review.SemanticAuditPage(**p) for p in fixture["pages"])
    settings = review.SemanticAuditRecipe(**fixture["recipe"])
    client = Client()
    result = run(tmp_path, client, pages, settings)
    assert review.audit._json(client.requests) == review.audit._json(fixture["requests"])
    assert {k: v.decode("utf8") for k, v in snapshot(result.manifest_path.parent).items()} == fixture["evidence"]
    assert review.semantic_review_source_fingerprint(pages, settings, PDF,
        semantic_unit_reference_policy=refs.POLICY, source_inventory_max_output_tokens=None) == fixture["fingerprint"]
    saved = tmp_path / "saved"
    for rel, text in fixture["evidence"].items():
        path = saved / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode("utf8"))
    before = snapshot(saved)
    loaded = review.load_semantic_review(pages=pages, recipe=settings, pdf_sha256=PDF,
        evidence_dir=saved, semantic_unit_reference_policy=refs.POLICY)
    assert loaded.reused and loaded.selected_text_by_page == result.selected_text_by_page
    assert snapshot(saved) == before


@pytest.mark.parametrize("saved_budget", [None, 64000])
def test_saved_budget_never_silently_upgrades_or_downgrades(tmp_path, saved_budget):
    client = Client()
    run(tmp_path, client, source_inventory_max_output_tokens=saved_budget)
    before = snapshot(tmp_path / "audit")
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"):
        run(tmp_path, client, source_inventory_max_output_tokens=64000 if saved_budget is None else None)
    assert len(client.requests) == 3 and snapshot(tmp_path / "audit") == before


class Incomplete(Client):
    def create_page_response(self, **request):
        self.requests.append(deepcopy(request))
        raise ApiCallError("fictional cap reached", None, "IncompleteResponseError", 0, 0, 0, False,
            usage={"input_tokens": 10, "output_tokens": request["max_output_tokens"],
                   "total_tokens": 10 + request["max_output_tokens"]}, response_id="settled-incomplete",
            response_status="incomplete", incomplete_reason="max_output_tokens", refused=False,
            raw_output='{"version":"ordinary_source_inventory_unit_refs_v1","claims":["truncated')


@pytest.mark.parametrize("budget", [None, 64000])
def test_incomplete_raw_retained_rejected_replay_never_repurchases(tmp_path, budget):
    client = Incomplete()
    with pytest.raises(review.SemanticAuditError, match="provider_incomplete"):
        run(tmp_path, client, source_inventory_max_output_tokens=budget)
    before = snapshot(tmp_path / "audit")
    raw = json.loads(before["source_inventory/raw_response.json"])
    assert raw["incomplete_reason"] == "max_output_tokens"
    assert "source_inventory/raw_receipt.json" in before
    assert "source_inventory/derived_response.json" not in before
    assert not (tmp_path / "audit/correction").exists()
    for available_client in (None, client):
        with pytest.raises(review.SemanticAuditError, match="provider_incomplete"):
            run(tmp_path, available_client, source_inventory_max_output_tokens=budget)
    with pytest.raises(review.SemanticAuditError, match="source_binding_mismatch"):
        run(tmp_path, client, source_inventory_max_output_tokens=64000 if budget is None else None)
    assert len(client.requests) == 1 and snapshot(tmp_path / "audit") == before


def test_64k_pending_staging_blocks_uncertain_repurchase(tmp_path, monkeypatch):
    client = Client()
    original = review.audit.os.link
    def interrupted(src, dst):
        if Path(dst).parent.name == review.STAGES[0] and Path(dst).name == "raw_response.json":
            raise OSError("fictional interruption after fsync")
        return original(src, dst)
    with monkeypatch.context() as patch:
        patch.setattr(review.audit.os, "link", interrupted)
        with pytest.raises(review.SemanticAuditError, match="evidence_write_failure"):
            run(tmp_path, client, source_inventory_max_output_tokens=64000)
    assert list((tmp_path / "audit/source_inventory").glob("*.pending"))
    before = snapshot(tmp_path / "audit")
    for available_client in (None, client):
        with pytest.raises(review.SemanticAuditError, match="review_unsettled_stage"):
            run(tmp_path, available_client, source_inventory_max_output_tokens=64000)
    assert len(client.requests) == 1 and snapshot(tmp_path / "audit") == before


@pytest.mark.parametrize("cancel_stage", review.STAGES)
def test_64k_cancelled_settlement_reuses_each_stage_once(tmp_path, cancel_stage):
    state = {"cancel": False}
    client = Client(after=lambda stage: state.update(cancel=stage == cancel_stage))
    with pytest.raises(review.SemanticAuditError, match="operation_cancelled"):
        run(tmp_path, client, cancel_check=lambda: state["cancel"], source_inventory_max_output_tokens=64000)
    assert (tmp_path / "audit" / cancel_stage / "raw_receipt.json").exists()
    assert not (tmp_path / "audit/manifest.json").exists()
    client.after = None
    state["cancel"] = False
    result = run(tmp_path, client, source_inventory_max_output_tokens=64000)
    assert result.manifest_path.exists() and len(client.requests) == 3
    assert [r["max_output_tokens"] for r in client.requests] == [64000, 32000, 32000]


@pytest.mark.parametrize("hard", [False, True])
def test_actual_transport_accounting_and_reservation_use_effective_cap(tmp_path, hard):
    from decimal import Decimal
    from types import SimpleNamespace
    from legalpdf_translate.budget_reservations import ReservationBudget
    from legalpdf_translate.cost_guardrails import PricingSnapshot
    from legalpdf_translate.openai_client import OpenAIResponsesClient, _request_accounting_details
    from legalpdf_translate.usage_accounting import DispatchAccounting, accounting_context
    # Synthetic rates verify the accounting path, not current provider pricing.
    prices = PricingSnapshot.from_mapping({
        "snapshot_id": "inventory-cap-fictional", "verified_at": "2026-10-20", "source": "offline fixture",
        "models": {"openai:gpt-5.2|default|fixture|USD": {"input_per_1m": 2, "output_per_1m": 8,
            "cached_input_per_1m": 1, "service_tier": "default", "billing_scope": "fixture", "currency": "USD"}}})
    budget = ReservationBudget(tmp_path / "budget.json", cap_usd="3", identity={"case": "fictional"}) if hard else None
    accountant = DispatchAccounting(tmp_path / "journal", run_identity={"case": "fictional"},
        pricing_snapshot=prices, budget_context=budget, dispatch_limits={"openai:semantic_audit": {
            "requested_model": "gpt-5.2", "max_input_tokens": 30000, "max_output_tokens": 128000,
            "apply_output_bound_only_when_hard": True, "requested_service_tier": "default",
            "billing_scope": "fixture", "currency": "USD", "allowed_base_urls": ["https://api.openai.com/v1"]}})
    actual = []
    def create(**request):
        actual.append(deepcopy(request))
        event = json.loads(accountant.journal_path.read_text())["events"][-1]
        cap = [64000, 32000, 32000][len(actual) - 1]
        assert event["event"] == "begin" and request["max_output_tokens"] == cap
        assert event["bounds"]["max_output_tokens"] == cap
        assert event["request_hash"] == _request_accounting_details(request)[0]
        ceiling = (Decimal(30000) * 2 + Decimal(cap) * 8) / Decimal(1000000)
        assert Decimal(event["ceiling_usd"]) == ceiling
        if hard:
            assert Decimal(budget.status()["held_usd"]) == ceiling
        payload = json.loads(request["input"][0]["content"][0]["text"])
        return {"id": f"fictional-{len(actual)}", "model": "gpt-5.2", "service_tier": "default",
            "status": "completed", "output": [], "output_text": json.dumps(response(payload["stage"], payload)),
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}}
    sdk = SimpleNamespace(base_url="https://api.openai.com/v1", responses=SimpleNamespace(create=create))
    client = OpenAIResponsesClient(sdk_client=sdk, model="gpt-5.2", pre_call_jitter_seconds=0, max_transport_retries=0)
    with accounting_context(accountant, purpose="semantic_audit"):
        result = run(tmp_path, client, pack(off=True), replace(recipe(configured_image_mode="off"), model="gpt-5.2"),
            source_inventory_max_output_tokens=64000)
    assert len(actual) == 3 and result.usage["output_tokens"] == 60
    assert accountant.summary()["coverage_status"] == "complete"
    assert accountant.summary()["call_count"] == 3
    if hard:
        assert Decimal(budget.status()["held_usd"]) == 0


@pytest.mark.parametrize("bound", ["raw", "hydrated"])
def test_64k_does_not_raise_existing_response_or_hydration_bounds(tmp_path, bound):
    assert review.audit.MAX_RESPONSE_CHARS == 600000
    pages = pack()
    def damage(stage, data, payload):
        if stage != review.STAGES[0]: return data
        if bound == "raw":
            data["claims"][0]["proposition"] = "X" * 600001
        else:
            first = data["claims"][0]
            data["claims"] = [{**deepcopy(first), "claim_id": f"C{n}"} for n in range(40)]
        return data
    if bound == "hydrated":
        pages = (replace(pack()[0], original_source_text="X" * 20000),)
    client = Client(damage)
    with pytest.raises(review.SemanticAuditError, match="review_response_bound"):
        run(tmp_path, client, pages, source_inventory_max_output_tokens=64000)
    assert len(client.requests) == 1 and (tmp_path / "audit/source_inventory/raw_receipt.json").exists()
    assert not (tmp_path / "audit/source_inventory/derived_response.json").exists()
    assert not (tmp_path / "audit/manifest.json").exists()
