"""Opt-in advisory Gemini Decisions API helpers (v1beta, fail-open).

These helpers never override deterministic validators, budget reservations, or
unreviewed-status flags. When disabled (the default) or when credentials/service
are unavailable, they make zero paid calls or abstain without failing the run.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from google import genai

from .config import GEMINI_DECISIONS_MODEL
from .gemini_client import (
    _extract_gemini_base_url,
    _extract_gemini_usage,
    _parse_data_url_image,
    _trusted_gemini_billing_scope,
    resolve_gemini_key_with_source,
)
from .openai_client import _active_accountant, _dispatch_limits, _field
from .usage_accounting import MemoryDispatchAccounting

DEFAULT_DECISIONS_ABSTAIN_THRESHOLD = 0.70
_DECISIONS_DEFAULT_ACCOUNTING = MemoryDispatchAccounting()


def _decisions_request_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _create_decisions_client(api_key: str) -> Any:
    return genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1beta", "retry_options": {"attempts": 1}},
    )


def _accounted_decision_create(
    *,
    client: Any,
    accountant: Any,
    input_items: Any,
    questions: Sequence[Mapping[str, Any]],
    model: str = GEMINI_DECISIONS_MODEL,
) -> Any:
    active = _active_accountant(accountant or _DECISIONS_DEFAULT_ACCOUNTING)
    purpose, limits = _dispatch_limits(active, provider="gemini", purpose="decisions", model=model)
    billing_scope = _trusted_gemini_billing_scope(client, limits)
    currency = limits.get("currency", "USD")
    if active.hard_budget and billing_scope is None:
        raise ValueError("Hard-budget dispatch requires a verified Gemini Decisions endpoint and scope.")
    base_url = _extract_gemini_base_url(client)
    request_hash = _decisions_request_hash(
        {
            "model": model,
            "questions": list(questions),
            "input_count": len(input_items) if isinstance(input_items, list) else 1,
        }
    )
    bounds = {**limits, "image_count": 0}
    ticket = active.begin(
        provider="gemini",
        requested_model=model,
        effort="decisions",
        purpose=purpose,
        request_hash=request_hash,
        bounds=bounds,
        attempt=1,
        requested_service_tier="default",
        billing_scope=billing_scope,
        currency=currency,
        route="decisions.create",
        base_url=base_url,
    )
    try:
        response = client.decisions.create(
            model=model,
            input=input_items,
            questions=list(questions),
        )
    except Exception as exc:  # noqa: BLE001
        active.finish(
            ticket,
            outcome="failed",
            usage={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            response_id=None,
            actual_model=model,
            error_code=type(exc).__name__,
            actual_service_tier="default",
            actual_billing_scope=billing_scope,
            currency=currency,
        )
        raise

    usage = _extract_gemini_usage(response)
    if "output_tokens" not in usage and "input_tokens" in usage:
        usage = {**usage, "output_tokens": 0}
    active.finish(
        ticket,
        outcome="succeeded",
        usage=usage,
        response_id=None,
        actual_model=model,
        actual_service_tier="default",
        actual_billing_scope=billing_scope,
        currency=currency,
    )
    return response


def _build_decision_input(
    summary_text: str,
    *,
    image_data_url: str | None = None,
) -> list[dict[str, Any]]:
    content: list[dict[str, Any]] = [{"type": "text", "text": str(summary_text or "").strip() or "No summary provided."}]
    if isinstance(image_data_url, str) and image_data_url.strip():
        content.append(_parse_data_url_image(image_data_url.strip()))
    return content


def evaluate_page_routing_advisory(
    *,
    signal_summary: Mapping[str, Any],
    enabled: bool = False,
    api_key: str | None = None,
    sdk_client: Any | None = None,
    accountant: Any | None = None,
    abstain_threshold: float = DEFAULT_DECISIONS_ABSTAIN_THRESHOLD,
    model: str = GEMINI_DECISIONS_MODEL,
) -> dict[str, Any]:
    """Optional advisory routing hint over deterministic OCR/image advisor signals."""
    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "model": model,
            "advisory_only": True,
            "overrides_deterministic": False,
            "recommendation": None,
        }
    if sdk_client is None:
        resolved_key, _ = resolve_gemini_key_with_source(api_key, allow_ocr_fallback=True)
        if not resolved_key:
            return {
                "enabled": True,
                "status": "unavailable",
                "reason": "missing_gemini_credentials",
                "model": model,
                "advisory_only": True,
                "overrides_deterministic": False,
                "recommendation": None,
            }
        client = _create_decisions_client(resolved_key)
    else:
        client = sdk_client

    questions = [
        {
            "type": "choice",
            "instructions": (
                "Based on the document signal metrics, choose the safest visual/OCR routing mode for legal translation."
            ),
            "criteria": {
                "text_only": "Clean digital text coverage with low fragmentation; text-only translation is sufficient.",
                "attach_image": "Mixed or complex visual layout where attaching source page images helps layout/context.",
                "api_ocr_recommended": "Low embedded text or scanned content where API OCR fallback should be used.",
            },
        }
    ]
    input_items = _build_decision_input(
        f"Deterministic advisor signal summary:\n{json.dumps(dict(signal_summary), sort_keys=True)}"
    )
    try:
        response = _accounted_decision_create(
            client=client,
            accountant=accountant,
            input_items=input_items,
            questions=questions,
            model=model,
        )
        answers = list(_field(response, "answers") or [])
        if not answers:
            raise ValueError("Decisions API returned no answers.")
        first = answers[0]
        choice = str(_field(first, "choice") or "").strip() or None
        confidence = float(_field(first, "confidence") or 0.0)
        probabilities = dict(_field(first, "probabilities") or {})
        abstained = confidence < float(abstain_threshold) or choice is None
        return {
            "enabled": True,
            "status": "abstained" if abstained else "ok",
            "model": model,
            "advisory_only": True,
            "overrides_deterministic": False,
            "abstain_threshold": float(abstain_threshold),
            "confidence": round(confidence, 4),
            "raw_choice": choice,
            "recommendation": None if abstained else choice,
            "probabilities": probabilities,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "enabled": True,
            "status": "unavailable",
            "reason": type(exc).__name__,
            "model": model,
            "advisory_only": True,
            "overrides_deterministic": False,
            "recommendation": None,
        }


def evaluate_visual_qa_advisory(
    *,
    qa_summary: Mapping[str, Any],
    image_data_url: str | None = None,
    enabled: bool = False,
    api_key: str | None = None,
    sdk_client: Any | None = None,
    accountant: Any | None = None,
    abstain_threshold: float = DEFAULT_DECISIONS_ABSTAIN_THRESHOLD,
    model: str = GEMINI_DECISIONS_MODEL,
) -> dict[str, Any]:
    """Optional advisory visual QA & review-queue triage using Gemini Decisions API."""
    if not enabled:
        return {
            "enabled": False,
            "status": "disabled",
            "model": model,
            "advisory_only": True,
            "overrides_deterministic": False,
            "triage": None,
        }
    if sdk_client is None:
        resolved_key, _ = resolve_gemini_key_with_source(api_key, allow_ocr_fallback=True)
        if not resolved_key:
            return {
                "enabled": True,
                "status": "unavailable",
                "reason": "missing_gemini_credentials",
                "model": model,
                "advisory_only": True,
                "overrides_deterministic": False,
                "triage": None,
            }
        client = _create_decisions_client(resolved_key)
    else:
        client = sdk_client

    questions = [
        {
            "type": "noul",
            "instructions": (
                "Evaluate whether the translated legal document metrics indicate complete, faithful legal parity "
                "without unresolved omissions or structural corruption."
            ),
            "criteria": {
                "true_description": "Consistent translation telemetry without unresolved numeric, citation, or validator anomalies.",
                "false_description": "Telemetry or image indicators show potential omissions, mismatches, or review-worthy defects.",
            },
        },
        {
            "type": "choice",
            "instructions": "Select the additive operator QA triage recommendation.",
            "criteria": {
                "pass": "Low risk; routine operator review.",
                "spot_check": "Moderate risk; recommend spot-checking flagged sections.",
                "priority_review": "Elevated risk; prioritize operator inspection before delivery.",
            },
        },
    ]
    input_items = _build_decision_input(
        f"Visual & deterministic QA telemetry:\n{json.dumps(dict(qa_summary), sort_keys=True)}",
        image_data_url=image_data_url,
    )
    try:
        response = _accounted_decision_create(
            client=client,
            accountant=accountant,
            input_items=input_items,
            questions=questions,
            model=model,
        )
        answers = list(_field(response, "answers") or [])
        noul_ans = answers[0] if len(answers) >= 1 else None
        choice_ans = answers[1] if len(answers) >= 2 else (answers[0] if len(answers) == 1 else None)
        noul_val = float(_field(noul_ans, "noul") or 0.0) if noul_ans is not None else None
        noul_conf = float(_field(noul_ans, "confidence") or 0.0) if noul_ans is not None else 0.0
        choice = str(_field(choice_ans, "choice") or "").strip() or None if choice_ans is not None else None
        choice_conf = float(_field(choice_ans, "confidence") or 0.0) if choice_ans is not None else 0.0
        probabilities = dict(_field(choice_ans, "probabilities") or {}) if choice_ans is not None else {}
        best_conf = max(noul_conf, choice_conf)
        abstained = best_conf < float(abstain_threshold) or choice is None
        return {
            "enabled": True,
            "status": "abstained" if abstained else "ok",
            "model": model,
            "advisory_only": True,
            "overrides_deterministic": False,
            "abstain_threshold": float(abstain_threshold),
            "confidence": round(best_conf, 4),
            "noul": round(noul_val, 4) if noul_val is not None else None,
            "noul_confidence": round(noul_conf, 4),
            "raw_choice": choice,
            "triage": None if abstained else choice,
            "probabilities": probabilities,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "enabled": True,
            "status": "unavailable",
            "reason": type(exc).__name__,
            "model": model,
            "advisory_only": True,
            "overrides_deterministic": False,
            "triage": None,
        }
