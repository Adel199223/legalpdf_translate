"""Native exact-wire charging guards; installed SDK with fictional HTTP only."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from types import SimpleNamespace

import httpx
from openai import OpenAI
import pytest

from legalpdf_translate.openai_client import OpenAIResponsesClient, ApiCallError
from legalpdf_translate.accounting_policy import ordinary_accounting_policy, with_semantic_review_policy
from legalpdf_translate.usage_accounting import DispatchAccounting, DispatchAccountingError, accounting_context
from legalpdf_translate.semantic_review_model_policy import KEY, VERSION
from legalpdf_translate.semantic_review_billing import read_response, parse_response_bytes, validate_retained_responses

ROLE = {"version": VERSION, "model": "gpt-6-astra"}
IDENTITY = {"model": "gpt-5.2", KEY: ROLE}
USAGE = {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110,
    "input_tokens_details": {"cached_tokens": 20, "cache_write_tokens": 30},
    "output_tokens_details": {"reasoning_tokens": 4}}


def native(tmp_path, mutate=None, status=200, settings=None):
    requests, bodies = [], []
    def send(request):
        requests.append(json.loads(request.content))
        data = {"id": "fictional-billed-response", "model": "gpt-6-astra", "status": "completed",
                "service_tier": "default", "output_text": "fictional retained text", "usage": deepcopy(USAGE)}
        if mutate: data = mutate(data)
        raw = data if isinstance(data, bytes) else json.dumps(data).encode()
        bodies.append(raw)
        return httpx.Response(status, content=raw, headers={"content-type": "application/json"})
    sdk = OpenAI(api_key="fictional-test-key", http_client=httpx.Client(transport=httpx.MockTransport(send)))
    client = OpenAIResponsesClient(sdk_client=sdk, model="gpt-6-astra", max_transport_retries=0, pre_call_jitter_seconds=0)
    settings = settings or with_semantic_review_policy(ordinary_accounting_policy(), ROLE).accounting_arguments()
    accountant = DispatchAccounting(tmp_path / "journal", run_identity=IDENTITY, **settings)
    return client, accountant, requests, bodies


def call(client, accountant, purpose="semantic_audit"):
    with accounting_context(accountant, purpose=purpose, page_number=None):
        return client.create_page_response(instructions="Fictional instructions", prompt_text="Fictional source",
            effort="high", max_output_tokens=32000, timeout_seconds=480)


def test_exact_positive_write_formula_raw_body_and_immutable_catalog_restore(tmp_path):
    client, accountant, requests, bodies = native(tmp_path)
    assert call(client, accountant).raw_output == "fictional retained text"
    events = json.loads(accountant.journal_path.read_bytes())["events"]
    finish = events[-1]
    assert Decimal(finish["cost_usd"]) == Decimal("0.001395")
    proof = finish["semantic_review_billing_evidence"]["response"]
    assert (accountant.run_dir / proof["path"]).read_bytes() == bodies[0]
    assert proof["sha256"] == hashlib.sha256(bodies[0]).hexdigest()
    validate_retained_responses(accountant.run_dir, events)
    before = accountant.journal_path.read_bytes()
    restored = DispatchAccounting(accountant.run_dir, run_identity=IDENTITY,
        **ordinary_accounting_policy().accounting_arguments())
    assert restored.summary()["known_cost_usd"] == accountant.summary()["known_cost_usd"]
    assert accountant.journal_path.read_bytes() == before
    assert requests[0]["model"] == "gpt-6-astra" and requests[0]["max_output_tokens"] == 32000


@pytest.mark.parametrize("defect", ["missing_read", "missing_write", "null_read", "null_write", "bool_write", "string_write",
    "masked_null_read", "masked_null_write", "conflict_read", "conflict_write", "extra_charge", "band", "output_overflow",
    "tier", "model", "missing_id", "newline_id", "long_id", "duplicate_wire"])
def test_unsupported_bill_retains_exact_raw_and_blocks_after_process_restore(tmp_path, defect):
    def mutate(data):
        usage, details = data["usage"], data["usage"]["input_tokens_details"]
        if defect == "missing_read": details.pop("cached_tokens")
        elif defect == "missing_write": details.pop("cache_write_tokens")
        elif defect == "null_read": details["cached_tokens"] = None
        elif defect == "null_write": details["cache_write_tokens"] = None
        elif defect == "bool_write": details["cache_write_tokens"] = True
        elif defect == "string_write": details["cache_write_tokens"] = "30"
        elif defect == "masked_null_read": usage["cached_input_tokens"] = None
        elif defect == "masked_null_write": usage["cache_write_tokens"] = None
        elif defect == "conflict_read": usage["cached_input_tokens"] = 0
        elif defect == "conflict_write": usage["cache_write_tokens"] = 0
        elif defect == "extra_charge": details["unrecognized_paid_tokens"] = 1
        elif defect == "band": usage.update(input_tokens=272001, total_tokens=272011)
        elif defect == "output_overflow": usage.update(output_tokens=32001, total_tokens=32101)
        elif defect == "tier": data["service_tier"] = "priority"
        elif defect == "model": data["model"] = "gpt-6-astra-unverified"
        elif defect == "missing_id": data["id"] = None
        elif defect == "newline_id": data["id"] = "unsafe\nidentity"
        elif defect == "long_id": data["id"] = "x" * 513
        else: return json.dumps(data).replace('"model": "gpt-6-astra"', '"model": "gpt-6-astra", "model": "gpt-6-astra"').encode()
        return data
    client, accountant, requests, bodies = native(tmp_path, mutate)
    with pytest.raises(ApiCallError) as error: call(client, accountant)
    assert error.value.raw_output == "fictional retained text"
    state = json.loads(accountant.journal_path.read_bytes())
    assert len(state["events"]) == 2 and state["events"][-1]["cost_usd"] is None
    assert accountant.summary()["unknown_cost_count"] == 1
    proof = state["events"][-1]["semantic_review_billing_evidence"]["response"]
    assert (accountant.run_dir / proof["path"]).read_bytes() == bodies[0]
    before = accountant.journal_path.read_bytes()
    restored = DispatchAccounting(accountant.run_dir, run_identity=IDENTITY,
        **ordinary_accounting_policy().accounting_arguments())
    assert not restored.can_retry
    with pytest.raises(ApiCallError): call(client, restored)
    assert len(requests) == 1 and accountant.journal_path.read_bytes() == before


@pytest.mark.parametrize("input_tokens", [0, 272000])
def test_known_zero_and_exact_lower_band_edge_are_valid(tmp_path, input_tokens):
    def mutate(data):
        data["usage"] = {"input_tokens": input_tokens, "output_tokens": 0, "total_tokens": input_tokens,
            "cached_input_tokens": 0, "cache_write_tokens": 0}
        return data
    client, accountant, _, _ = native(tmp_path, mutate)
    call(client, accountant)
    assert Decimal(json.loads(accountant.journal_path.read_bytes())["events"][-1]["cost_usd"]) == Decimal(input_tokens) * 10 / 1000000


def test_wrong_purpose_has_zero_http_and_zero_journal_begin(tmp_path):
    client, accountant, requests, _ = native(tmp_path)
    with pytest.raises(ApiCallError): call(client, accountant, "translation")
    assert requests == [] and json.loads(accountant.journal_path.read_bytes())["events"] == []


@pytest.mark.parametrize("damage", ["missing", "changed"])
def test_retained_raw_body_damage_blocks_read_only_restore(tmp_path, damage):
    client, accountant, requests, _ = native(tmp_path)
    call(client, accountant)
    state = json.loads(accountant.journal_path.read_bytes())
    path = accountant.run_dir / state["events"][-1]["semantic_review_billing_evidence"]["response"]["path"]
    if damage == "missing": path.rename(path.with_suffix(".preserved"))
    else: path.write_bytes(path.read_bytes() + b" ")
    before = accountant.journal_path.read_bytes()
    with pytest.raises(DispatchAccountingError):
        DispatchAccounting(accountant.run_dir, run_identity=IDENTITY, **ordinary_accounting_policy().accounting_arguments())
    assert accountant.journal_path.read_bytes() == before and len(requests) == 1


def test_duplicate_usage_in_http_error_is_retained_unpriced(tmp_path):
    def mutate(data):
        return json.dumps(data).replace('"input_tokens": 100', '"input_tokens": 99, "input_tokens": 100').encode()
    client, accountant, requests, bodies = native(tmp_path, mutate, status=400)
    with pytest.raises(ApiCallError): call(client, accountant)
    state = json.loads(accountant.journal_path.read_bytes())
    assert state["events"][-1]["cost_usd"] is None and state["events"][-1]["cost_status"] == "duplicate_json_keys"
    assert len(requests) == 1
    assert read_response(accountant.run_dir, state["events"][-1]["semantic_review_billing_evidence"]["response"])["usage"]["input_tokens"] == 100
