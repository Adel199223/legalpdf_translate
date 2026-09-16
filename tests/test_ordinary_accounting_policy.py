"""Ordinary policy and exact transport preparation, entirely offline."""
from datetime import date
from types import SimpleNamespace
import json
import socket

import pytest

from legalpdf_translate.accounting_policy import OrdinaryAccountingPolicy, ordinary_accounting_policy
from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.openai_client import OpenAIResponsesClient, _accounted_openai_create, _request_accounting_details
from legalpdf_translate.usage_accounting import DispatchAccounting, DispatchAccountingError, accounting_context


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*args, **kwargs):
        pytest.fail("Policy test attempted network access")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


def sdk_for(tier="default", *, endpoint="https://api.openai.com/v1/"):
    requests = []
    def create(**request):
        requests.append(request)
        return {"id": "fake-response", "model": "gpt-5.2", "service_tier": tier,
            "status": "completed", "output": [], "output_text": "synthetic output",
            "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}
    return SimpleNamespace(base_url=endpoint, responses=SimpleNamespace(create=create)), requests


def accountant(tmp_path, *, hard=False, arguments=None):
    budget = ReservationBudget(tmp_path / "budget.json", cap_usd="10", identity={"case": "test"}) if hard else None
    return DispatchAccounting(tmp_path / "accounting", run_identity={"case": "test"}, budget_context=budget,
        **(arguments or ordinary_accounting_policy().accounting_arguments(today=date(2026, 9, 10))))


@pytest.mark.parametrize("tier,known", [("default", True), ("priority", False), (None, False), ("flex", False)])
def test_public_reference_prices_only_actual_supported_tier_without_changing_request(tmp_path, tier, known):
    meter = accountant(tmp_path)
    sdk, requests = sdk_for(tier)
    _accounted_openai_create(client=sdk, accountant=meter, model="gpt-5.2", input="synthetic", store=False)
    assert len(requests) == 1
    assert "service_tier" not in requests[0] and "max_output_tokens" not in requests[0]
    summary = meter.summary()
    assert (summary["coverage_status"] == "complete") is known
    assert summary["cost_usd"] == (pytest.approx(.000875) if known else None)
    journal = json.loads(meter.journal_path.read_text(encoding="utf-8"))
    assert journal["events"][0]["requested_service_tier"] == "auto"
    assert journal["events"][1]["actual_service_tier"] == tier


@pytest.mark.parametrize("endpoint", ["https://example.invalid/v1", "https://api.openai.com/v1?secret=not-a-key",
                                    "https://not-a-key@api.openai.com/v1", ""])
def test_unknown_endpoint_never_inherits_public_pricing_or_logs_url_credentials(tmp_path, endpoint):
    meter = accountant(tmp_path)
    sdk, requests = sdk_for(endpoint=endpoint)
    _accounted_openai_create(client=sdk, accountant=meter, model="gpt-5.2", input="synthetic", store=False)
    assert len(requests) == 1 and meter.summary()["cost_usd"] is None
    assert "not-a-key" not in meter.journal_path.read_text(encoding="utf-8")


def test_auto_hard_cap_with_unverified_project_tiers_stops_before_reservation_or_sdk(tmp_path):
    meter = accountant(tmp_path, hard=True)
    sdk, requests = sdk_for()
    with pytest.raises(DispatchAccountingError, match="tier"):
        _accounted_openai_create(client=sdk, accountant=meter, model="gpt-5.2", input="synthetic")
    assert requests == []
    assert meter.summary()["call_count"] == 0
    assert float(meter.budget_context.status()["held_usd"]) == 0


def test_explicit_policy_preparation_equals_exact_dispatched_request(tmp_path):
    arguments = ordinary_accounting_policy().accounting_arguments(today=date(2026, 9, 10))
    limits = arguments["dispatch_limits"]["openai:*:gpt-5.2"]
    limits.update(requested_service_tier="default", max_input_tokens=5000, max_output_tokens=100,
                  apply_output_bound_only_when_hard=False)
    meter = accountant(tmp_path, hard=True, arguments=arguments)
    sdk, requests = sdk_for()
    client = OpenAIResponsesClient(sdk_client=sdk, pre_call_jitter_seconds=0, max_transport_retries=0)
    page = dict(instructions="synthetic", prompt_text="synthetic input", effort="high",
        response_format={"type": "json_schema", "strict": True, "name": "test", "schema": {}},
        max_output_tokens=200)
    with accounting_context(meter, purpose="translation", page_number=1):
        prepared = client.prepare_page_request(**page)
        assert requests == [] and meter.summary()["call_count"] == 0
        client.create_page_response(**page)
    actual = {k: v for k, v in requests[0].items() if k != "timeout"}
    assert prepared == actual
    assert actual["service_tier"] == "default" and actual["max_output_tokens"] == 100
    assert _request_accounting_details(actual)[0] == json.loads(meter.journal_path.read_text())["events"][0]["request_hash"]
    assert meter.summary()["coverage_status"] == "complete"


def test_policy_has_no_mutable_caller_aliases():
    arguments = ordinary_accounting_policy().accounting_arguments(today=date(2026, 9, 10))
    policy = OrdinaryAccountingPolicy.from_mapping(pricing=arguments["pricing_snapshot"], limits=arguments["dispatch_limits"])
    arguments["dispatch_limits"]["openai:*:gpt-5.2"]["allowed_base_urls"].append("https://example.invalid")
    copied = policy.accounting_arguments()
    copied["dispatch_limits"].clear()
    assert policy.accounting_arguments()["dispatch_limits"]["openai:*:gpt-5.2"]["allowed_base_urls"] == ["https://api.openai.com/v1"]


def test_endpoint_drift_after_begin_is_not_dispatched_and_not_charged(tmp_path):
    meter = accountant(tmp_path)
    sdk, requests = sdk_for()
    def change_endpoint():
        sdk.base_url = "https://example.invalid/v1"
        return 10.0
    with pytest.raises(ValueError, match="endpoint changed"):
        _accounted_openai_create(client=sdk, accountant=meter, model="gpt-5.2", input="synthetic",
            before_dispatch=change_endpoint)
    assert requests == []
    journal = json.loads(meter.journal_path.read_text(encoding="utf-8"))
    assert journal["events"][-1]["outcome"] == "not_dispatched"


@pytest.mark.parametrize("today", [date(2026, 9, 9), date(2026, 10, 11)])
def test_expired_or_future_reference_new_run_unknown_saved_run_keeps_frozen_prices(tmp_path, today):
    policy = ordinary_accounting_policy()
    old = accountant(tmp_path, arguments=policy.accounting_arguments(today=date(2026, 9, 10)))
    before = old.journal_path.read_bytes()
    expired = policy.accounting_arguments(today=today)
    assert expired["pricing_snapshot"] is None
    resumed = accountant(tmp_path, arguments=expired)
    assert resumed.pricing_snapshot is not None
    assert resumed.journal_path.read_bytes() == before
    fresh = accountant(tmp_path / "new", arguments=expired)
    assert fresh.pricing_snapshot is None
