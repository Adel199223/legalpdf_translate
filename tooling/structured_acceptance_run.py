"""Execute separately authorized reviewed-source acceptance through the app.

No CLI, credential discovery, client construction or authority generation.
This is an execution entry, not a read-only preflight or security sandbox.
The caller owns the configured transport, process deadline and fresh-operation
authorization. Historical consumed private callers are not reopened here.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from typing import Any

from legalpdf_translate.acceptance_budget import LegacyAcceptanceBudget
from legalpdf_translate.acceptance_continuation import AcceptanceContinuationError
from legalpdf_translate.acceptance_execution import build_acceptance_continuation
from legalpdf_translate.acceptance_provenance import canonical_run_config
from legalpdf_translate.cost_guardrails import PricingSnapshot
from legalpdf_translate.openai_client import OpenAIResponsesClient
from legalpdf_translate.types import RunConfig, RunSummary
from legalpdf_translate.usage_accounting import DispatchAccounting
from legalpdf_translate.workflow import TranslationWorkflow
from tooling.structured_acceptance_preflight import build_acceptance_accounting


def run_approved_acceptance(
    *,
    config: RunConfig,
    preferences: Mapping[str, Any],
    client: OpenAIResponsesClient,
    ledger_path: Path,
    amendment_path: Path,
    expected_amendment_sha256: str,
    run_identity: Mapping[str, Any],
    execution_identity: Mapping[str, Any],
    pricing_snapshot: PricingSnapshot | Mapping[str, Any],
    source_review_file: Mapping[str, str],
    successor_scope_file: Mapping[str, str] | None = None,
) -> RunSummary:
    """Use explicit inputs without changing their approved effective values.

    An initial budget verifies the supplied authority; the workflow's actual
    accountant is constructed by the same factory and exposed to continuation.
    Every dispatch is still subject to runtime/source/request/cost checks.
    Resume uses existing journals; this function never resets them or retries
    an uncertain operation. Successful export alone is not acceptance approval.
    """
    if not isinstance(config, RunConfig) or not isinstance(preferences, Mapping):
        raise ValueError("Acceptance requires explicit configuration and preferences.")
    if (not isinstance(client, OpenAIResponsesClient)
            or client._max_transport_retries != 0
            or getattr(client._client, "max_retries", None) != 0):
        raise ValueError("Acceptance requires a configured transport with zero retries at both layers.")
    if config.workers != 1 or not config.keep_intermediates or config.allow_xhigh_escalation:
        raise ValueError("Acceptance requires serial execution, retained evidence and no xhigh escalation.")
    if config.gmail_batch_context is not None:
        raise ValueError("Acceptance does not authorize Gmail intake.")

    # Copy caller-owned containers, not credentials or the supplied transport.
    settings = deepcopy(dict(preferences))
    identity = deepcopy(dict(run_identity))
    if client.model != identity.get("model"):
        raise AcceptanceContinuationError("acceptance_client_model_mismatch")
    execution = deepcopy(dict(execution_identity))
    review = deepcopy(dict(source_review_file))
    prices = (pricing_snapshot if isinstance(pricing_snapshot, PricingSnapshot)
              else PricingSnapshot.from_mapping(pricing_snapshot))
    budget = LegacyAcceptanceBudget(
        ledger_path, amendment_path=amendment_path,
        expected_amendment_sha256=expected_amendment_sha256,
        run_identity=identity, execution_identity=execution, pricing_snapshot=prices,
    )
    # Reject drift before workflow setup can create output/run-state artifacts.
    # The actual accountant still rechecks the effective normalized config.
    budget.bind_runtime_context(config=lambda: canonical_run_config(config),
                                preferences=lambda: settings)
    if successor_scope_file is not None:
        from legalpdf_translate.acceptance_successor import validate_successor_scope
        validate_successor_scope(budget, deepcopy(dict(successor_scope_file)))
    if set(budget.dispatch_limits) != {"openai:translation"}:
        raise AcceptanceContinuationError("acceptance_caller_primary_only")
    holder: dict[str, DispatchAccounting] = {}
    continuation = build_acceptance_continuation(
        budget=budget, client=client,
        accountant_supplier=lambda: holder["accountant"], source_review_file=review,
    )
    if continuation.reviewed_source_evidence is None:
        raise AcceptanceContinuationError("acceptance_caller_requires_saved_reviewed_source")

    def factory(**arguments):
        accountant = build_acceptance_accounting(
            **arguments, ledger_path=ledger_path, amendment_path=amendment_path,
            expected_amendment_sha256=expected_amendment_sha256,
            execution_identity=execution, pricing_snapshot=prices,
        )
        holder["accountant"] = accountant
        return accountant

    def no_ocr(*args, **kwargs):
        raise AcceptanceContinuationError("acceptance_caller_ocr_not_authorized")

    workflow = TranslationWorkflow(
        client=client, gui_settings=settings, environment_loader=lambda: None,
        ocr_engine_factory=no_ocr, translation_protocol="legal_blocks_v2",
        accounting_factory=factory, acceptance_continuation=continuation,
    )
    return workflow.run(config)
