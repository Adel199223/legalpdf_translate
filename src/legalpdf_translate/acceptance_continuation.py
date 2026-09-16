"""Private, append-only continuation evidence for explicitly approved campaigns.

This is not an ordinary retry policy or an approval generator. The caller owns
the externally approved subset and authorizer; the transport must independently
verify the final bounded request and reserve against the original budget.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import re
import stat

from .formatting_support import fingerprint
from .structured_artifacts import (
    StructuredArtifactError, _decode, _json, _publish_file_exclusive, _read_file,
)

_HASH = re.compile(r"[a-f0-9]{64}\Z")


class AcceptanceContinuationError(StructuredArtifactError):
    """Content-free failure; uncertain attempts can never be automatically retried."""


@dataclass(frozen=True)
class AcceptanceContinuation:
    campaign_identity: str
    full_case_pages: tuple[int, ...]
    dispatch_pages: tuple[int, ...]
    authorize_request: Callable[[dict], str | None]
    source_review_json: str | None = None
    reviewed_source_evidence: object | None = None
    source_review_guard: Callable[[], None] | None = None

    def __post_init__(self):
        if not isinstance(self.campaign_identity, str) or not _HASH.fullmatch(self.campaign_identity):
            raise AcceptanceContinuationError("invalid_acceptance_campaign")
        for pages in (self.full_case_pages, self.dispatch_pages):
            if (type(pages) is not tuple or not pages or any(type(n) is not int or n < 1 for n in pages)
                    or tuple(sorted(set(pages))) != pages):
                raise AcceptanceContinuationError("invalid_acceptance_page_subset")
        if not set(self.dispatch_pages).issubset(self.full_case_pages) or not callable(self.authorize_request):
            raise AcceptanceContinuationError("invalid_acceptance_page_subset")
        if self.reviewed_source_evidence is not None and not callable(self.source_review_guard):
            raise AcceptanceContinuationError("reviewed_source_recheck_required")

    def validate_selection(self, selected_pages):
        if tuple(selected_pages) != self.full_case_pages:
            raise AcceptanceContinuationError("acceptance_requires_full_case_selection")

    def authorize(self, descriptor: dict, *, primary_approval: str | None = None) -> str | None:
        if descriptor["page_number"] not in self.dispatch_pages:
            raise AcceptanceContinuationError("acceptance_page_not_approved")
        approval = self.authorize_request(deepcopy(descriptor))
        if approval is None:
            return None
        if not isinstance(approval, str) or not _HASH.fullmatch(approval):
            raise AcceptanceContinuationError("invalid_acceptance_authorization")
        if descriptor["purpose"] == "correction" and approval == primary_approval:
            return None  # A primary amendment never silently authorizes correction.
        return approval


class AcceptancePageJournal:
    """Commit an intent before contact, then retain the paid response before use.

Missing response after an intent is ambiguous even if the SDK was never reached.
Failing closed here prevents repurchase after a crash or failed journal write.
Files contain private source/request/response material and must not be logged.
"""

    def __init__(self, run_dir: Path, *, policy: AcceptanceContinuation,
                 protocol_identity: Mapping, page_number: int, page_fingerprint: str):
        self.policy = policy
        self.page_number = page_number
        self.folder = Path(run_dir) / "acceptance_private"
        self.folder.mkdir(exist_ok=True)
        info = self.folder.lstat()
        if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise AcceptanceContinuationError("unsafe_acceptance_evidence_directory")
        self.identity = {"campaign": policy.campaign_identity, "protocol": dict(protocol_identity),
                         "page_number": page_number, "page_fingerprint": page_fingerprint,
                         "full_case_pages": list(policy.full_case_pages)}

    def _path(self, name):
        return self.folder / f"page_{self.page_number:04d}.{name}.json"

    def _read(self, name):
        path = self._path(name)
        if not path.exists():
            return None
        record = _decode(_read_file(path))
        if (not isinstance(record, dict) or set(record) != {"version", "identity", "payload", "sha256"}
                or type(record["version"]) is not int or record["version"] != 1 or record["identity"] != self.identity
                or not isinstance(record["payload"], dict)
                or fingerprint({key: value for key, value in record.items() if key != "sha256"}) != record["sha256"]):
            raise AcceptanceContinuationError("acceptance_evidence_invalid")
        payload = record["payload"]
        if name.endswith(".intent"):
            if (set(payload) != {"request", "approval_sha256"} or not isinstance(payload["request"], dict)
                    or not isinstance(payload["approval_sha256"], str) or not _HASH.fullmatch(payload["approval_sha256"])):
                raise AcceptanceContinuationError("acceptance_intent_invalid")
        elif name.endswith(".response"):
            if (set(payload) != {"intent_sha256", "response", "usage", "metadata"}
                    or not all(isinstance(payload[key], dict) for key in ("response", "usage", "metadata"))
                    or not isinstance(payload["intent_sha256"], str) or not _HASH.fullmatch(payload["intent_sha256"])):
                raise AcceptanceContinuationError("acceptance_response_invalid")
            response = payload["response"]
            if (set(response) != {"raw_output", "usage", "response_id", "response_status", "refused",
                                 "transport_retries_count", "model", "effort", "attempt_usage"}
                    or not all(isinstance(response[key], str) for key in ("raw_output", "response_status", "model", "effort"))
                    or not isinstance(response["usage"], dict) or not isinstance(response["attempt_usage"], list)
                    or response["response_id"] is not None and not isinstance(response["response_id"], str)
                    or type(response["refused"]) is not bool
                    or type(response["transport_retries_count"]) is not int or response["transport_retries_count"] < 0):
                raise AcceptanceContinuationError("acceptance_response_invalid")
        elif name == "correction.pending":
            if (set(payload) != {"primary_response_sha256", "request"} or not isinstance(payload["request"], dict)
                    or not isinstance(payload["primary_response_sha256"], str)
                    or not _HASH.fullmatch(payload["primary_response_sha256"])):
                raise AcceptanceContinuationError("acceptance_pending_correction_invalid")
        return record

    def _write(self, name, payload):
        record = {"version": 1, "identity": self.identity, "payload": deepcopy(payload)}
        record["sha256"] = fingerprint(record)
        existing = self._read(name)
        if existing is not None:
            if existing != record:
                raise AcceptanceContinuationError("acceptance_evidence_conflict")
            return existing
        content = _json(record)
        if len(content) > 8 * 1024 * 1024:
            raise AcceptanceContinuationError("acceptance_evidence_too_large")
        _publish_file_exclusive(self._path(name), content)
        verified = self._read(name)
        if verified != record:
            raise AcceptanceContinuationError("acceptance_evidence_write_unverified")
        return verified

    def response(self, attempt: int, request: dict):
        stem = self._stem(attempt)
        intent, response = self._read(stem + ".intent"), self._read(stem + ".response")
        if attempt == 2 and (intent is not None or response is not None):
            pending = self._read("correction.pending")
            if pending is None or pending["payload"]["request"] != request:
                raise AcceptanceContinuationError("acceptance_pending_correction_invalid")
            primary = self._read("primary.response")
            if primary is None or primary["sha256"] != pending["payload"]["primary_response_sha256"]:
                raise AcceptanceContinuationError("acceptance_primary_response_changed")
        if intent is None:
            if response is not None or attempt == 1 and self._read("correction.pending") is not None:
                raise AcceptanceContinuationError("orphan_acceptance_evidence")
            return None
        if intent["payload"]["request"] != request:
            raise AcceptanceContinuationError("acceptance_request_changed")
        if response is None:
            raise AcceptanceContinuationError("acceptance_attempt_outcome_uncertain")
        if response["payload"].get("intent_sha256") != intent["sha256"]:
            raise AcceptanceContinuationError("acceptance_response_binding_invalid")
        return deepcopy(response["payload"])

    def begin(self, attempt: int, request: dict, approval: str):
        stem = self._stem(attempt)
        if self._read(stem + ".intent") is not None:
            raise AcceptanceContinuationError("acceptance_attempt_already_started")
        return self._write(stem + ".intent", {"request": request, "approval_sha256": approval})

    def save_response(self, attempt: int, *, result, usage: dict, metadata: dict):
        stem = self._stem(attempt)
        intent = self._read(stem + ".intent")
        if intent is None:
            raise AcceptanceContinuationError("acceptance_intent_missing")
        response = {name: deepcopy(getattr(result, name, default)) for name, default in (
            ("raw_output", ""), ("usage", {}), ("response_id", None), ("response_status", "unknown"),
            ("refused", False), ("transport_retries_count", 0), ("model", ""), ("effort", ""),
            ("attempt_usage", []))}
        return self._write(stem + ".response", {"intent_sha256": intent["sha256"],
            "response": response, "usage": usage, "metadata": metadata})

    def pending_correction(self, request: dict):
        primary = self._read("primary.response")
        if primary is None:
            raise AcceptanceContinuationError("acceptance_primary_response_missing")
        return self._write("correction.pending", {"primary_response_sha256": primary["sha256"],
                                                  "request": request})["sha256"]

    def primary_approval(self):
        intent = self._read("primary.intent")
        return intent["payload"]["approval_sha256"] if intent is not None else None

    def require_prior_attempt_evidence(self, prior_call_count: int, pending_digest: str | None = None):
        if prior_call_count > 0 and self._read("primary.intent") is None:
            raise AcceptanceContinuationError("acceptance_prior_attempt_evidence_missing")
        if pending_digest:
            pending = self._read("correction.pending")
            if pending is None or pending["sha256"] != pending_digest:
                raise AcceptanceContinuationError("acceptance_pending_correction_invalid")

    @staticmethod
    def _stem(attempt):
        if attempt not in (1, 2):
            raise AcceptanceContinuationError("acceptance_attempt_limit")
        return "primary" if attempt == 1 else "correction"
