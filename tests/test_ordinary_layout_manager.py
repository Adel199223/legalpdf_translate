"""Real request/accounting boundary with fictional SDK responses; no network."""
import base64
from copy import deepcopy
from datetime import date
import json
from types import SimpleNamespace

import httpx
import pytest

from legalpdf_translate.accounting_policy import ordinary_accounting_policy
from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.openai_client import OpenAIResponsesClient, APIConnectionError, APITimeoutError
from legalpdf_translate.ordinary_layout_contracts import LayoutSuggestionPolicy, OrdinaryLayoutError
from legalpdf_translate.ordinary_layout_manager import OrdinaryLayoutManager
from legalpdf_translate.usage_accounting import DispatchAccounting
from tests.test_ordinary_layout_service import make_case, nonce
from tests.test_ordinary_layout_contracts import proposal


def enable_paid(case, *, response_kind="valid", cap="3"):
    calls, accountants = [], []
    policy = LayoutSuggestionPolicy("gpt-5.2", ".4", "1")
    budget = ReservationBudget(case.root.parent / "shared_budget.json", cap_usd=cap, identity={"fixture": "shared"})
    pricing = ordinary_accounting_policy().accounting_arguments(today=date(2026, 10, 9))["pricing_snapshot"]
    limits = {"requested_model": "gpt-5.2", "allowed_actual_models": ["gpt-5.2"],
        "allowed_actual_service_tiers": ["default"], "requested_service_tier": "default",
        "billing_scope": "openai_public_api", "currency": "USD", "allowed_base_urls": ["https://api.openai.com/v1"],
        "max_input_tokens": 100000, "max_output_tokens": 8000,
        "max_image_input_tokens": 4000, "max_image_count": 1, "image_bound_verified": True}
    def accountant(job, operation_nonce, operation_dir, selected_policy):
        assert selected_policy == policy and job.job_id == case.job.job_id
        result = DispatchAccounting(operation_dir / "accounting", run_identity={"fixture": operation_nonce},
            pricing_snapshot=pricing, budget_context=budget, dispatch_limits={"openai:layout_suggestion": limits})
        accountants.append(result)
        return result
    def create(**request):
        calls.append(request)
        assert len(accountants[-1].summary()["by_purpose"]) == 1
        if response_kind == "unknown":
            raise APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        value = proposal(case.view["review"])
        if response_kind == "invalid":
            value["paragraphs"][0]["text"] = "Forbidden replacement"
        if callable(response_kind):
            response_kind()
        return SimpleNamespace(id="fictional-response", model="gpt-5.2", status="completed", service_tier="default",
            output=[], output_text=json.dumps(value), usage={"input_tokens": 20, "output_tokens": 8, "total_tokens": 28,
                "input_tokens_details": {"cached_tokens": 0}, "output_tokens_details": {"reasoning_tokens": 0}})
    def provider(job, selected_policy):
        return OpenAIResponsesClient(model=selected_policy.model, max_transport_retries=0, pre_call_jitter_seconds=0,
            sdk_client=SimpleNamespace(base_url="https://api.openai.com/v1/", responses=SimpleNamespace(create=create)))
    case.manager = OrdinaryLayoutManager(case.root, mode="shadow", workspace_id="fixture", job_resolver=lambda _: case.state["job"],
        provider_factory=provider, accounting_factory=accountant, suggestion_policy=policy)
    return SimpleNamespace(calls=calls, accountants=accountants, budget=budget, policy=policy)


def suggest(case, operation_nonce=None):
    return case.manager.suggest(case.job.job_id, case.view["generation"], operation_nonce or nonce(), [1],
                                expected_baseline_id=case.view["baseline_id"])


def test_explicit_paid_proposal_has_durable_purpose_and_never_review_flags(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    paid = enable_paid(case)
    assert case.manager.state(case.job.job_id)["suggestion_capability"]["available"]
    assert paid.calls == []
    operation = nonce(); result = suggest(case, operation)
    assert result["status"] == "applied_unreviewed", result
    assert result["accounting"]["complete"] is True
    assert len(paid.calls) == 1 and paid.calls[0]["max_output_tokens"] == 8000
    assert paid.calls[0]["input"][0]["content"][1]["type"] == "input_image"
    journal = paid.accountants[0].summary()
    assert journal["by_purpose"]["layout_suggestion"]["cost_usd"] > 0
    after = case.manager.state(case.job.job_id)
    assert after["generation"] == case.view["generation"] + 1
    assert after["review"]["decisions"]["review"]["document_reviewed"] is False
    assert suggest(case, operation) == result and len(paid.calls) == 1
    assert case.manager.layout_costs(case.job.job_id)["complete"]
    assert float(case.manager.layout_costs(case.job.job_id)["cost_usd"]) > 0


@pytest.mark.parametrize("language", ["EN", "FR", "AR"])
def test_layout_guidance_reaches_sdk_with_exact_language_text_and_source(tmp_path, monkeypatch, language):
    case = make_case(tmp_path, monkeypatch, language)
    paid = enable_paid(case)
    result = suggest(case)
    assert result["status"] == "applied_unreviewed"
    assert len(paid.calls) == 1
    request = paid.calls[0]
    instructions = request["instructions"]
    assert "For Arabic target text, normally use right paragraph alignment" in instructions
    assert "genuinely centered or justified source treatments" in instructions
    assert "do not mirror\ncolumn positions or change wording" in instructions
    assert "same source row, use matching\nspace_before_pt" in instructions
    content = request["input"][0]["content"]
    payload = json.loads(content[0]["text"])
    assert content[0]["type"] == "input_text"
    assert payload["target_lang"] == language and payload["page_number"] == 1
    assert payload["paragraphs"] == case.view["review"]["paragraphs"]
    source = case.manager.service.saved.image(case.view["review"]["review_id"], 1)
    assert content[1]["type"] == "input_image" and content[1]["detail"] == "high"
    assert content[1]["image_url"] == "data:image/png;base64," + base64.b64encode(source).decode("ascii")
    assert request["text"]["format"]["type"] == "json_schema"
    assert request["text"]["format"]["strict"] is True
    after = case.manager.state(case.job.job_id)
    assert after["review"]["paragraphs"] == case.view["review"]["paragraphs"]
    assert after["review"]["decisions"]["review"]["document_reviewed"] is False


@pytest.mark.parametrize("kind", ["invalid", "unknown"])
def test_invalid_or_unknown_outcome_does_not_apply_or_retry(tmp_path, monkeypatch, kind):
    case = make_case(tmp_path, monkeypatch); paid = enable_paid(case, response_kind=kind)
    operation = nonce(); result = suggest(case, operation)
    assert result["status"] == "failed" and len(paid.calls) == 1
    assert case.manager.state(case.job.job_id)["generation"] == case.view["generation"]
    assert suggest(case, operation) == result and len(paid.calls) == 1
    costs = case.manager.layout_costs(case.job.job_id)
    if kind == "unknown":
        assert costs["cost_usd"] is None and not costs["complete"]
        assert paid.budget.status()["held_usd"] != "0"
    else:
        assert costs["complete"] and float(costs["cost_usd"]) > 0


def test_budget_exhaustion_prevents_transport(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch); paid = enable_paid(case, cap=".00001")
    result = suggest(case)
    assert result["status"] == "failed" and paid.calls == []


def test_no_policy_no_mapping_and_unbounded_accountant_never_dispatch(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch, mapping=False)
    with pytest.raises(OrdinaryLayoutError, match="paid_policy_unavailable"):
        suggest(case)
    paid = enable_paid(case)
    with pytest.raises(OrdinaryLayoutError, match="page_mapping_required"):
        suggest(case)
    assert paid.calls == []


def test_concurrent_edit_is_preserved_and_paid_proposal_is_not_applied(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    def edit():
        view = case.manager.service.saved.read(case.view["review"]["review_id"])
        decisions = deepcopy(view["decisions"]); decisions["paragraphs"][1]["italic"] = True
        case.manager.service.saved.save_decisions(view["review_id"], view["generation"], nonce(), decisions)
    paid = enable_paid(case, response_kind=edit)
    result = suggest(case)
    assert result["status"] == "failed" and len(paid.calls) == 1
    after = case.manager.state(case.job.job_id)
    assert after["review"]["decisions"]["paragraphs"][1]["italic"] is True


def test_pending_operation_recovery_does_not_dispatch(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch); paid = enable_paid(case)
    operation = nonce()
    case.manager.service.begin_suggestion(case.job.job_id, case.view["generation"], operation, [1], paid.policy.public(),
                                         expected_baseline_id=case.view["baseline_id"])
    result = suggest(case, operation)
    assert result["status"] == "pending_or_interrupted" and not result["retry_dispatch_allowed"]
    assert paid.calls == []
    assert case.manager.layout_costs(case.job.job_id)["cost_usd"] is None
    with pytest.raises(OrdinaryLayoutError, match="suggestion_pending"):
        suggest(case, nonce())
    assert paid.calls == []


def test_completed_retry_survives_policy_expiry_new_baseline_and_retired_job(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch); paid = enable_paid(case)
    operation = nonce(); result = suggest(case, operation)
    assert result["status"] == "applied_unreviewed"
    case.manager.prepare(case.job.job_id, nonce())
    case.manager.suggestion_policy = None
    case.manager.job_resolver = lambda _: None
    assert suggest(case, operation) == result
    assert len(paid.calls) == 1
    with pytest.raises(OrdinaryLayoutError, match="nonce_conflict"):
        case.manager.suggest(case.job.job_id, case.view["generation"] + 1, operation, [1],
            expected_baseline_id=case.view["baseline_id"])


def test_new_baseline_during_response_never_applies_old_proposal(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    def change_baseline():
        case.manager.prepare(case.job.job_id, nonce())
    paid = enable_paid(case, response_kind=change_baseline)
    result = suggest(case)
    assert result["status"] == "failed" and result["error_code"] == "ordinary_layout_baseline_stale"
    assert len(paid.calls) == 1
    assert case.manager.state(case.job.job_id)["generation"] == case.view["generation"]


def test_memory_accounting_is_rejected_without_dispatch(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch); paid = enable_paid(case)
    case.manager.accounting_factory = lambda *_: object()
    result = suggest(case)
    assert result["error_code"] == "ordinary_layout_durable_accounting_required"
    assert paid.calls == []
    assert not case.manager.layout_costs(case.job.job_id)["complete"]


@pytest.mark.parametrize("kind", ["pending", "unknown", "valid"])
def test_delivery_mutations_require_settled_proposals(tmp_path, monkeypatch, kind):
    case = make_case(tmp_path, monkeypatch); paid = enable_paid(case, response_kind=kind)
    operation = nonce()
    if kind == "pending":
        case.manager.service.begin_suggestion(case.job.job_id, case.view["generation"], operation, [1], paid.policy.public(),
            expected_baseline_id=case.view["baseline_id"])
    else:
        suggest(case, operation)
    case.manager.select_delivery(case.job.job_id, 0, nonce(), "original", keep_ordinary_confirmed=True,
        expected_baseline_id=case.view["baseline_id"])
    assert case.manager.resolve_delivery(case.job.job_id, 1).path.is_file()
    if kind == "valid":
        assert case.manager.resolve_delivery(case.job.job_id, 1, nonce(), require_settled=True).frozen
    else:
        for options in ({"require_settled": True}, {"freeze_nonce": nonce()}):
            with pytest.raises(OrdinaryLayoutError, match="accounting_unsettled"):
                case.manager.resolve_delivery(case.job.job_id, 1, **options)
        assert case.manager.state(case.job.job_id)["frozen"] is None


def test_cancel_settles_current_page_retains_partial_proposal_and_stops_next(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch, pages=2)
    operation = nonce()
    def cancel():
        first = case.manager.cancel_suggestion(case.job.job_id, operation, case.view["generation"],
            expected_baseline_id=case.view["baseline_id"])
        assert first["status"] == "cancel_requested"
        assert case.manager.cancel_suggestion(case.job.job_id, operation, case.view["generation"],
            expected_baseline_id=case.view["baseline_id"]) == first
    paid = enable_paid(case, response_kind=cancel)
    result = case.manager.suggest(case.job.job_id, case.view["generation"], operation, [1, 2],
        expected_baseline_id=case.view["baseline_id"])
    assert result["status"] == "cancelled" and result["completed_pages"] == [1]
    assert result["applied_unreviewed"] and result["generation"] == case.view["generation"] + 1
    assert len(paid.calls) == 1 and result["accounting"]["complete"]
    assert case.manager.cancel_suggestion(case.job.job_id, operation, case.view["generation"],
        expected_baseline_id=case.view["baseline_id"]) == result
    with pytest.raises(OrdinaryLayoutError, match="nonce_conflict"):
        case.manager.cancel_suggestion(case.job.job_id, operation, case.view["generation"], expected_baseline_id=nonce())


def test_cancel_before_first_dispatch_has_zero_verified_cost(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch); paid = enable_paid(case)
    operation = nonce(); factory = case.manager.provider_factory
    def cancel_before_client(job, policy):
        case.manager.cancel_suggestion(job.job_id, operation, case.view["generation"],
            expected_baseline_id=case.view["baseline_id"])
        return factory(job, policy)
    case.manager.provider_factory = cancel_before_client
    result = suggest(case, operation)
    assert result["status"] == "cancelled" and result["completed_pages"] == []
    assert not result["applied_unreviewed"] and paid.calls == []
    assert result["accounting"]["cost_usd"] == 0 and result["accounting"]["complete"]


def test_layout_timeout_reaches_sdk_once_and_unknown_cost_remains_held(tmp_path, monkeypatch):
    case = make_case(tmp_path, monkeypatch)
    def timeout():
        raise APITimeoutError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    paid = enable_paid(case, response_kind=timeout)
    operation = nonce()
    result = suggest(case, operation)
    assert result["status"] == "failed" and result["completed_pages"] == []
    assert result["retry_dispatch_allowed"] is False
    assert len(paid.calls) == 1
    request = paid.calls[0]
    assert 470 < request["timeout"] <= 480
    assert request["max_output_tokens"] == 8000 and request["reasoning"] == {"effort": "high"}
    assert case.manager.state(case.job.job_id)["generation"] == case.view["generation"]
    before = paid.budget.status()
    assert before["held_usd"] != "0"
    assert result["accounting"]["cost_usd"] is None and not result["accounting"]["complete"]
    assert suggest(case, operation) == result
    assert len(paid.calls) == 1 and paid.budget.status() == before
