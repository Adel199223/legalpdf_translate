"""New caller wiring only; synthetic authority/source and fake provider."""
from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path

import pytest

from legalpdf_translate.budget_reservations import BudgetError
from tests.test_acceptance_campaign_integration import (
    _approve, _campaign, _forbid_source_acquisition,
)
from tests.test_acceptance_continuation import offline
from tooling.structured_acceptance_run import run_approved_acceptance


def invoke(case, approval, *, resume=False, **overrides):
    arguments = dict(
        config=replace(case.config, resume=resume), preferences={}, client=case.client,
        ledger_path=case.ledger, amendment_path=approval[0],
        expected_amendment_sha256=approval[1], run_identity=case.identity,
        execution_identity=case.execution, pricing_snapshot=case.prices,
        source_review_file=case.review_entry,
    )
    arguments.update(overrides)
    return run_approved_acceptance(**arguments)


def prepared(tmp_path, monkeypatch, *, pages=1):
    _forbid_source_acquisition(monkeypatch)
    case = _campaign(tmp_path, pages=pages, reviewed=True)
    case.sdk.max_retries = 0  # Explicit fake transport contract, not a live SDK.
    return case, _approve(case, tuple(range(1, pages + 1)))


def test_new_caller_preserves_paid_evidence_and_resume_does_not_contact_again(tmp_path, monkeypatch):
    case, approval = prepared(tmp_path, monkeypatch)
    result = invoke(case, approval)
    assert result.success, result.error
    assert len(case.sdk.requests) == 1
    ledger_before = case.ledger.read_bytes()
    evidence = {path: path.read_bytes() for path in (result.run_dir / "acceptance_private").glob("*.json")}
    resumed = invoke(case, approval, resume=True)
    assert resumed.success and len(case.sdk.requests) == 1
    assert case.ledger.read_bytes() == ledger_before
    assert evidence and all(path.read_bytes() == raw for path, raw in evidence.items())


@pytest.mark.parametrize("drift", ["preferences", "config", "output", "review"])
def test_new_caller_drift_blocks_before_contact(tmp_path, monkeypatch, drift):
    case, approval = prepared(tmp_path, monkeypatch)
    before = case.ledger.read_bytes()
    changes = {}
    if drift == "preferences":
        changes["preferences"] = {"prompt_addendum_by_lang": {"AR": "changed"}}
    elif drift == "config":
        changes["config"] = replace(case.config, page_breaks=not case.config.page_breaks)
    elif drift == "output":
        changes["config"] = replace(case.config, output_dir=tmp_path / "unapproved-output")
    else:
        path = Path(case.review_entry["path"])
        path.write_bytes(path.read_bytes() + b"\n")  # Isolated synthetic fixture.
    with pytest.raises((BudgetError, ValueError)):
        invoke(case, approval, **changes)
    assert not case.sdk.requests
    assert case.ledger.read_bytes() == before
    assert not (tmp_path / "unapproved-output").exists()


def test_new_caller_unknown_usage_is_held_and_not_rebought(tmp_path, monkeypatch):
    case, approval = prepared(tmp_path, monkeypatch, pages=2)
    case.sdk.missing_usage = True
    result = invoke(case, approval)
    assert not result.success and len(case.sdk.requests) == 1
    state = json.loads(case.ledger.read_bytes())
    new_rows = [row for row in state["reservations"].values() if "execution" in row]
    assert len(new_rows) == 1 and new_rows[0]["status"] == "uncertain"
    assert Decimal(new_rows[0]["reserved_usd"]) > 0
    assert state["blocked_reason"]
    before = case.ledger.read_bytes()
    try:
        resumed = invoke(case, approval, resume=True)
    except BudgetError:
        pass
    else:
        assert not resumed.success
    assert len(case.sdk.requests) == 1 and case.ledger.read_bytes() == before


@pytest.mark.parametrize("layer", ["wrapper", "sdk", "unknown_sdk"])
def test_new_caller_rejects_retry_policy_before_loading_authority(tmp_path, monkeypatch, layer):
    case, approval = prepared(tmp_path, monkeypatch)
    if layer == "wrapper":
        case.client._max_transport_retries = 1
    elif layer == "sdk":
        case.sdk.max_retries = 1
    else:
        del case.sdk.max_retries
    before = case.ledger.read_bytes()
    with pytest.raises(ValueError, match="zero retries"):
        invoke(case, approval)
    assert not case.sdk.requests and case.ledger.read_bytes() == before
