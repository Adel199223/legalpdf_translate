"""Prepare current reviewed-source requests without credentials or dispatch.

This is not approval, a workflow run, OCR, or recovery of an old operation.
The caller supplies pinned reviewed evidence and its physical recheck callback.
Outputs contain private prompts: retain them outside Git and general logs.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace
import time
from typing import Any

from legalpdf_translate.acceptance_continuation import AcceptanceContinuation, AcceptanceContinuationError
from legalpdf_translate.acceptance_provenance import canonical_run_config, request_fingerprint
from legalpdf_translate.budget_reservations import fingerprint
from legalpdf_translate.config import OPENAI_MODEL
from legalpdf_translate.new_translation_blocks import NewTranslationBlocks, MAX_OUTPUT_TOKENS
from legalpdf_translate.openai_client import (
    OpenAIResponsesClient, _request_accounting_details, _validate_dispatch_input_bound,
)
from legalpdf_translate.types import RunConfig
from legalpdf_translate.usage_accounting import accounting_context
from legalpdf_translate.workflow import TranslationWorkflow, get_page_count, resolve_page_selection


class PreparationOnly:
    """Immutable request limits; every dispatch-shaped method fails closed."""
    hard_budget = True
    max_retries = 0

    def __init__(self, limits, *, model=OPENAI_MODEL):
        self._limits = deepcopy(dict(limits))
        self._model = model
        self.responses = SimpleNamespace(create=self.deny)

    def request_limits(self, provider, purpose, model):
        if (provider, purpose, model) != ("openai", "translation", self._model):
            raise AcceptanceContinuationError("preparation_route_changed")
        return deepcopy(self._limits)

    def deny(self, *args, **kwargs):
        raise AcceptanceContinuationError("preparation_cannot_dispatch")

    begin = finish = verify_dispatch = deny


def prepare_reviewed_requests(
    *, config: RunConfig, preferences: Mapping[str, Any], campaign_id: str, case_id: str,
    eligible_pages: tuple[int, ...], source_review_json: str, reviewed_source_evidence: object,
    source_review_guard: Callable[[], None], dispatch_limits: Mapping[str, Any], directory: Path,
    model: str = OPENAI_MODEL, required_effort: str = "high",
) -> dict:
    """Exercise the same settings/source/prompt path as the eventual actual run.

    Only a fresh preparation directory may be written. No caller transport or
    accountant is accepted, and the capture authorizer can never grant authority.
    Config normalization must be explicit at the caller; never silently change
    an approved effective setting while calculating request fingerprints.
    """
    if not isinstance(preferences, Mapping) or reviewed_source_evidence is None or not callable(source_review_guard):
        raise AcceptanceContinuationError("preparation_requires_reviewed_source")
    if not campaign_id or not case_id or not isinstance(campaign_id, str) or not isinstance(case_id, str):
        raise AcceptanceContinuationError("preparation_identity_missing")
    limits = deepcopy(dict(dispatch_limits))
    if (required_effort not in {"high", "xhigh"}
            or limits.get("requested_model", model) != model
            or limits.get("required_effort", required_effort) != required_effort):
        raise AcceptanceContinuationError("preparation_model_or_effort_mismatch")
    if (limits.get("requested_service_tier") != "default"
            or limits.get("max_output_tokens") != MAX_OUTPUT_TOKENS
            or type(limits.get("max_input_tokens")) is not int or limits["max_input_tokens"] <= 0):
        raise AcceptanceContinuationError("preparation_bounds_changed")
    if (config.workers != 1 or not config.keep_intermediates or config.allow_xhigh_escalation
            or config.gmail_batch_context is not None or config.resume):
        raise AcceptanceContinuationError("preparation_config_not_supported")
    settings = deepcopy(dict(preferences))
    no_dispatch = PreparationOnly(limits, model=model)
    client = OpenAIResponsesClient(sdk_client=no_dispatch, model=model,
        max_transport_retries=0, pre_call_jitter_seconds=0)
    # No acceptance source or filesystem writes are needed to normalize settings.
    workflow = TranslationWorkflow(client=client, gui_settings=settings, environment_loader=lambda: None,
        ocr_engine_factory=no_dispatch.deny, translation_protocol="legal_blocks_v2")
    if canonical_run_config(workflow._normalize_config(config)) != canonical_run_config(config):
        raise AcceptanceContinuationError("preparation_requires_normalized_config")
    workflow._validate_config(config)
    page_count = get_page_count(config.pdf_path)
    pages = tuple(resolve_page_selection(total_pages=page_count, start_page=config.start_page,
        end_page=config.end_page, max_pages=config.max_pages))
    source_hash = hashlib.sha256(config.pdf_path.read_bytes()).hexdigest()
    campaign_identity = fingerprint({"campaign_id": campaign_id, "case_id": case_id,
        "source_sha256": source_hash, "full_case_pages": list(pages)})
    captured = {}

    def capture(descriptor):
        number = descriptor["page_number"]
        if descriptor["purpose"] != "translation" or number in captured:
            raise AcceptanceContinuationError("preparation_duplicate_or_correction")
        captured[number] = deepcopy(descriptor)
        return None

    policy = AcceptanceContinuation(campaign_identity, pages, eligible_pages, capture,
        source_review_json, reviewed_source_evidence, source_review_guard)
    workflow._acceptance_continuation = policy
    workflow._hydrate_request_settings(config=config, gui_settings=settings)
    context, context_hash = workflow._resolve_context(config)
    workflow._last_state = SimpleNamespace(pages={})
    workflow._last_config = config
    structured = NewTranslationBlocks(workflow, config, pages, source_hash=source_hash, context_hash=context_hash)
    workflow._structured_run = structured
    directory = Path(directory)
    directory.mkdir(exist_ok=False)
    paths = SimpleNamespace(run_dir=directory, pages_dir=directory / "pages")
    paths.pages_dir.mkdir()
    requests = {}
    for number in eligible_pages:
        result = structured.translate_reviewed(client=client, paths=paths, page_number=number,
            total_pages=page_count, context_text=context, started=time.perf_counter())
        if result.error != "acceptance_approval_required" or number not in captured:
            raise AcceptanceContinuationError("preparation_did_not_stop_at_authorization")
        logical = captured[number]["request"]
        if logical["effort"] != required_effort or logical.get("image_data_url") is not None:
            raise AcceptanceContinuationError("preparation_resolved_policy_changed")
        with accounting_context(no_dispatch, purpose="translation", page_number=number):
            exact = client.prepare_page_request(**logical)
        _, observed = _request_accounting_details(exact)
        _validate_dispatch_input_bound(no_dispatch, limits, observed)
        if (exact["model"] != model or exact.get("reasoning", {}).get("effort") != required_effort
                or exact.get("store") is not False
                or exact.get("max_output_tokens") != MAX_OUTPUT_TOKENS
                or exact.get("service_tier") != "default"):
            raise AcceptanceContinuationError("preparation_request_policy_changed")
        requests[number] = {"logical_request": logical, "request": exact,
            "request_sha256": request_fingerprint(exact), "descriptor": captured[number]}
    structured.check_source()
    if any(directory.rglob("*.json")):
        raise AcceptanceContinuationError("preparation_unexpected_journal")
    return {"version": "reviewed_request_preparation_v1", "campaign_identity": campaign_identity,
        "canonical_config": canonical_run_config(config), "preferences_sha256": fingerprint(settings),
        "run_identity": {"accounting_id": "preparation-only", "run_started_at": "not-dispatched",
            "source_sha256": source_hash, "context_hash": context_hash, "language": config.target_lang.value,
            "model": model, "protocol": "legal_blocks_v2", "protocol_identity": structured.identity,
            "selection": [pages[0], pages[-1]]}, "requests": requests, "sdk_calls_entered": 0}
