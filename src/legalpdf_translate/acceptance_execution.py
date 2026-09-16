"""Bind an existing external amendment to continuation; never mint authority.

There is deliberately no CLI, client construction, dispatch call or default
activation here. The separately authorized caller supplies a configured client,
an already verified budget and the workflow's actual accounting object.
"""
from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
import hashlib
from pathlib import Path

from .acceptance_budget import LegacyAcceptanceBudget
from .acceptance_continuation import AcceptanceContinuation, AcceptanceContinuationError
from .acceptance_provenance import request_fingerprint, _verified_file
from .source_document import source_page_identity, source_page_dimensions
from .source_readiness import verify_source_review
from .reviewed_source import REVIEWED_ACCEPTANCE_VERSION, ReviewedSourceEvidence
from .structured_artifacts import _decode
from .openai_client import OpenAIResponsesClient
from .usage_accounting import accounting_context


def _read_reviewed_entry(entry, *, max_bytes):
    """Bound actual reads as well as stat checks, including a growth race."""
    if not isinstance(entry, dict) or set(entry) != {"path", "sha256"}:
        raise ValueError
    path = Path(entry["path"])
    if not path.is_absolute() or not 0 < path.stat().st_size <= max_bytes:
        raise ValueError
    with path.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if not 0 < len(raw) <= max_bytes or hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError
    return raw


def build_acceptance_continuation(*, budget: LegacyAcceptanceBudget,
                                 client: OpenAIResponsesClient,
                                 accountant_supplier: Callable[[], object],
                                 source_review_file: dict | None = None) -> AcceptanceContinuation:
    if not isinstance(budget, LegacyAcceptanceBudget) or not budget.dispatch_enabled:
        raise AcceptanceContinuationError("acceptance_requires_verified_v2_budget")
    if not isinstance(client, OpenAIResponsesClient) or not callable(accountant_supplier):
        raise AcceptanceContinuationError("acceptance_requires_configured_request_builder")
    pages = set()
    for key, limit in budget.dispatch_limits.items():
        if key not in {"openai:translation", "openai:correction"}:
            raise AcceptanceContinuationError("acceptance_auxiliary_dispatch_not_allowed")
        if limit["max_attempts"] != 1 or limit["max_calls_per_page"] != 1:
            raise AcceptanceContinuationError("acceptance_requires_single_page_attempt")
        if client.model != budget.run_identity["model"] or client.model != limit["requested_model"]:
            raise AcceptanceContinuationError("acceptance_client_model_mismatch")
        pages.update(call["page_number"] for call in limit["approved_calls"])
    selection = budget.run_identity["selection"]
    full_pages = tuple(range(selection[0], selection[1] + 1))
    approval_digest = budget.expected_amendment_sha256
    campaign_identity = budget.continuation_identity
    review_entry = deepcopy(source_review_file)

    def checked_review(active):
        provenance = active.amendment["provenance"]
        manifest = _decode(_verified_file(provenance["config_manifest"], "config_manifest"))
        if review_entry is None or review_entry not in manifest["files"]:
            raise AcceptanceContinuationError("acceptance_source_review_not_approved")
        try:
            raw = _verified_file(review_entry, "source_review").decode("utf-8")
        except UnicodeError:
            raise AcceptanceContinuationError("acceptance_source_review_unreadable") from None
        source_path = Path(provenance["source"]["path"])
        identities = {n: source_page_identity(source_path, n)
                      for n in full_pages}
        envelope = _decode(raw.encode("utf-8"))
        evidence, sizes = None, None
        if isinstance(envelope, dict) and envelope.get("version") == REVIEWED_ACCEPTANCE_VERSION:
            try:
                entries = [envelope["candidate_file"], envelope["manifest_file"], *envelope["evidence_files"]]
                if len(entries) > 50_002 or any(entry not in manifest["files"] for entry in entries):
                    raise ValueError
                # Bound reads before allocation; no paths are discovered from document text.
                sizes_on_disk = [Path(entry["path"]).stat().st_size for entry in entries]
                if any(n < 1 or n > 64_000_000 for n in sizes_on_disk) or sum(sizes_on_disk) > 272_000_000:
                    raise ValueError
                contents, remaining = [], 272_000_000
                for i, entry in enumerate(entries):
                    content = _read_reviewed_entry(entry,
                        max_bytes=min(8_000_000 if i < 2 else 64_000_000, remaining))
                    contents.append(content)
                    remaining -= len(content)
                evidence = ReviewedSourceEvidence(contents[0], contents[1], tuple(
                    {entry["sha256"]: content for entry, content in zip(entries[2:], contents[2:])}.items()))
                sizes = {n: source_page_dimensions(source_path, n) for n in full_pages}
            except (ValueError, TypeError, KeyError, OSError):
                raise AcceptanceContinuationError("acceptance_reviewed_evidence_not_approved") from None
        verify_source_review(raw, page_identities=identities, source_hash=active.run_identity["source_sha256"],
            reviewed_evidence=evidence, page_sizes=sizes)
        return raw, evidence

    review_json, reviewed_evidence = checked_review(budget)

    def recheck_review():
        if checked_review(budget) != (review_json, reviewed_evidence):
            raise AcceptanceContinuationError("acceptance_source_review_changed")

    def authorize(descriptor):
        accountant = accountant_supplier()
        active = getattr(accountant, "budget_context", None)
        if (not isinstance(active, LegacyAcceptanceBudget)
                or active.expected_amendment_sha256 != approval_digest
                or active.continuation_identity != campaign_identity):
            raise AcceptanceContinuationError("acceptance_accounting_authority_changed")
        if checked_review(active) != (review_json, reviewed_evidence):
            raise AcceptanceContinuationError("acceptance_source_review_changed")
        purpose = descriptor["purpose"]
        if descriptor["attempt"] != {"translation": 1, "correction": 2}.get(purpose):
            raise AcceptanceContinuationError("acceptance_logical_attempt_invalid")
        limit = active.dispatch_limits.get(f"openai:{purpose}")
        if limit is None:
            return None
        if (client.model != active.run_identity["model"] or client.model != limit["requested_model"]
                or descriptor.get("model") != client.model
                or descriptor["request"].get("effort") != limit["required_effort"]):
            raise AcceptanceContinuationError("acceptance_client_model_or_effort_changed")
        with accounting_context(accountant, purpose=purpose, page_number=descriptor["page_number"]):
            request = client.prepare_page_request(**descriptor["request"])
        details = dict(request_hash=request_fingerprint(request), provider="openai", purpose=purpose,
            page_number=descriptor["page_number"], attempt=1, requested_model=request["model"],
            effort=request.get("reasoning", {}).get("effort", ""),
            requested_service_tier=request.get("service_tier", "auto"),
            billing_scope=limit["billing_scope"], currency=limit["currency"], route=limit["route"],
            base_url=str(getattr(client._client, "base_url", "")).rstrip("/"))
        if purpose == "correction":
            details["pending_correction_sha256"] = descriptor["pending_correction_sha256"]
        return approval_digest if active.permits_dispatch(**details) else None

    return AcceptanceContinuation(campaign_identity, full_pages, tuple(sorted(pages)), authorize,
        review_json, reviewed_evidence, recheck_review if reviewed_evidence is not None else None)
