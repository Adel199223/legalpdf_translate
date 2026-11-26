"""Offline tests for the opt-in advisory Gemini Decisions API module."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legalpdf_translate import gemini_decisions
from legalpdf_translate.accounting_policy import gemini_accounting_policy
from legalpdf_translate.budget_reservations import ReservationBudget
from legalpdf_translate.usage_accounting import DispatchAccounting
from legalpdf_translate.workflow_components.ocr_advisor import build_ocr_image_advisor
from legalpdf_translate.workflow_components.quality_risk import build_quality_risk_summary


def _make_choice_response(choice: str, confidence: float, probabilities: dict[str, float], input_tokens: int = 150):
    return SimpleNamespace(
        answers=[SimpleNamespace(choice=choice, confidence=confidence, probabilities=probabilities)],
        usage=SimpleNamespace(
            total_input_tokens=input_tokens,
            total_output_tokens=0,
            total_thought_tokens=0,
            total_tokens=input_tokens,
        ),
    )


def _make_qa_response(noul: float, noul_conf: float, triage: str, triage_conf: float, input_tokens: int = 200):
    return SimpleNamespace(
        answers=[
            SimpleNamespace(noul=noul, confidence=noul_conf),
            SimpleNamespace(
                choice=triage,
                confidence=triage_conf,
                probabilities={"pass": 0.1, "spot_check": triage_conf, "priority_review": 0.05},
            ),
        ],
        usage=SimpleNamespace(
            total_input_tokens=input_tokens,
            total_tokens=input_tokens,
        ),
    )


def test_decisions_disabled_by_default_makes_zero_calls() -> None:
    calls: list[object] = []

    class _BoomDecisions:
        def create(self, **kwargs):
            calls.append(kwargs)
            raise AssertionError("Decisions API must not be called when disabled")

    res1 = evaluate = gemini_decisions.evaluate_page_routing_advisory(
        signal_summary={"pages": 2},
        enabled=False,
        sdk_client=SimpleNamespace(decisions=_BoomDecisions()),
    )
    res2 = gemini_decisions.evaluate_visual_qa_advisory(
        qa_summary={"quality_risk_score": 0.1},
        enabled=False,
        sdk_client=SimpleNamespace(decisions=_BoomDecisions()),
    )
    assert res1["status"] == "disabled" and res1["enabled"] is False
    assert res2["status"] == "disabled" and res2["enabled"] is False
    assert calls == []

    # Advisor and quality risk default hooks also make zero calls when disabled.
    advisor = build_ocr_image_advisor(
        rows=[{"extracted_text_chars": 500, "newline_to_char_ratio": 0.05}],
        target_lang="EN",
        current_ocr_mode="auto",
        current_image_mode="off",
        source="analyze_report",
    )
    risk = build_quality_risk_summary([(1, {"status": "done"})], target_lang="EN")
    assert "decisions_advisory" not in advisor
    assert "decisions_advisory" not in risk


def test_decisions_page_routing_advisory_and_confidence_abstention(tmp_path: Path) -> None:
    policy = gemini_accounting_policy()
    budget = ReservationBudget(tmp_path / "budget.json", cap_usd="1.00", identity={"run": "d1"})
    accountant = DispatchAccounting(
        tmp_path / "accounting",
        run_identity={"run": "d1"},
        budget_context=budget,
        **policy.accounting_arguments(),
    )

    sdk_ok = SimpleNamespace(
        decisions=SimpleNamespace(
            create=lambda **kw: _make_choice_response("attach_image", 0.88, {"attach_image": 0.88}, input_tokens=50000)
        )
    )
    advisory = gemini_decisions.evaluate_page_routing_advisory(
        signal_summary={"pages": 3, "image_candidate_ratio": 0.6},
        enabled=True,
        sdk_client=sdk_ok,
        accountant=accountant,
    )
    assert advisory["status"] == "ok"
    assert advisory["recommendation"] == "attach_image"
    assert advisory["advisory_only"] is True
    assert advisory["overrides_deterministic"] is False
    summary = accountant.summary()
    assert summary["coverage_status"] == "complete"
    assert float(summary["cost_usd"]) == pytest.approx(0.005)

    # Low confidence abstains cleanly
    sdk_low = SimpleNamespace(
        decisions=SimpleNamespace(
            create=lambda **kw: _make_choice_response("api_ocr_recommended", 0.42, {"api_ocr_recommended": 0.42})
        )
    )
    abstained = gemini_decisions.evaluate_page_routing_advisory(
        signal_summary={"pages": 1},
        enabled=True,
        sdk_client=sdk_low,
    )
    assert abstained["status"] == "abstained"
    assert abstained["recommendation"] is None
    assert abstained["raw_choice"] == "api_ocr_recommended"


def test_decisions_visual_qa_fail_open_on_error() -> None:
    class _BrokenDecisions:
        def create(self, **kwargs):
            raise RuntimeError("network down")

    res = gemini_decisions.evaluate_visual_qa_advisory(
        qa_summary={"quality_risk_score": 0.75},
        enabled=True,
        sdk_client=SimpleNamespace(decisions=_BrokenDecisions()),
    )
    assert res["status"] == "unavailable"
    assert res["triage"] is None
    assert res["overrides_deterministic"] is False


def test_decisions_visual_qa_attaches_additive_only_metadata() -> None:
    sdk = SimpleNamespace(
        decisions=SimpleNamespace(
            create=lambda **kw: _make_qa_response(0.81, 0.85, "spot_check", 0.82)
        )
    )
    risk = build_quality_risk_summary(
        [(1, {"status": "done", "fidelity_review_required": True})],
        target_lang="AR",
        decisions_advisory_enabled=True,
        decisions_sdk_client=sdk,
    )
    assert risk["review_queue_count"] == 1
    assert risk["decisions_advisory"]["status"] == "ok"
    assert risk["decisions_advisory"]["triage"] == "spot_check"
    assert risk["decisions_advisory"]["overrides_deterministic"] is False
