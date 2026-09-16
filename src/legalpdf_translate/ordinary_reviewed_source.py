"""Public, immutable source-review input for an ordinary structured run.

This consumes a separately completed review. It grants no provider authority,
creates no review decisions and imports no private acceptance integration.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import hashlib
import json
import re

from .reviewed_source import ReviewedSourceEvidence, REVIEWED_ACCEPTANCE_VERSION, REVIEWED_SOURCE_VERSION
from .source_readiness import verify_source_review
from .structured_artifacts import StructuredArtifactError, _decode

VERSION = "ordinary_reviewed_source_context_v1"
_MAX_JSON = 8_000_000
_MAX_ARTIFACTS = 256_000_000


class OrdinaryReviewedSourceError(StructuredArtifactError):
    """Content-free evidence or selection failure before ordinary dispatch."""


def _fail(code):
    raise OrdinaryReviewedSourceError(code) from None


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


@dataclass(frozen=True, slots=True)
class OrdinaryReviewedSourceContext:
    """An explicit selected revision, independent of budget/dispatch authority.

    The acquisition service supplies the original immutable evidence and a
    storage recheck hook. Hook return values confer no authority: every verify
    independently checks all evidence and the actual physical page identities.
    ``identity`` returns a new dictionary; no caller-owned mutable data is kept.
    """

    revision_id: str
    reviewer_kind: str
    source_review_json: bytes = field(repr=False)
    evidence: ReviewedSourceEvidence = field(repr=False)
    decision_evidence: bytes = field(repr=False)
    source_guard: Callable[[], None] = field(repr=False, compare=False)
    _identity_json: bytes = field(init=False, repr=False)

    def __post_init__(self):
        if (type(self.revision_id) is not str
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", self.revision_id) is None
                or type(self.reviewer_kind) is not str
                or self.reviewer_kind not in {"operator_review", "ai_test_review"}
                or not callable(self.source_guard)):
            _fail("ordinary_source_review_invalid_context")
        if (type(self.evidence) is not ReviewedSourceEvidence or type(self.evidence.artifacts) is not tuple
                or not 0 < len(self.evidence.artifacts) <= 50_000):
            _fail("ordinary_source_review_invalid_evidence")
        # Reject mutable containers/buffers and copy every container boundary.
        pairs = []
        for pair in self.evidence.artifacts:
            if (type(pair) is not tuple or len(pair) != 2
                    or type(pair[0]) is not str or type(pair[1]) is not bytes):
                _fail("ordinary_source_review_invalid_evidence")
            pairs.append((pair[0], pair[1]))
        object.__setattr__(self, "evidence", ReviewedSourceEvidence(
            self.evidence.candidate, self.evidence.manifest, tuple(pairs)))
        envelope = self._validate_bytes()
        identity = {"version": VERSION, "revision_id": self.revision_id,
            "reviewer_kind": self.reviewer_kind, "source_file_sha256": envelope["source_file_sha256"],
            "source_review_sha256": _sha(self.source_review_json),
            "candidate_file_sha256": _sha(self.evidence.candidate),
            "manifest_file_sha256": _sha(self.evidence.manifest),
            "decision_evidence_sha256": _sha(self.decision_evidence),
            "artifacts_sha256": _sha(_json(sorted(key for key, _ in self.evidence.artifacts)))}
        object.__setattr__(self, "_identity_json", _json(identity))

    @property
    def identity(self) -> dict:
        return json.loads(self._identity_json)

    def _validate_bytes(self):
        try:
            for raw in (self.source_review_json, self.decision_evidence,
                        self.evidence.candidate, self.evidence.manifest):
                if type(raw) is not bytes or not 0 < len(raw) <= _MAX_JSON:
                    _fail("ordinary_source_review_invalid_evidence")
            if not 0 < len(self.evidence.artifacts) <= 50_000:
                _fail("ordinary_source_review_invalid_evidence")
            seen, total = set(), 0
            for key, raw in self.evidence.artifacts:
                if key in seen or re.fullmatch(r"[a-f0-9]{64}", key) is None or _sha(raw) != key:
                    _fail("ordinary_source_review_evidence_changed")
                seen.add(key)
                total += len(raw)
                if not 0 < len(raw) <= 64_000_000 or total > _MAX_ARTIFACTS:
                    _fail("ordinary_source_review_evidence_too_large")
            envelope = _decode(self.source_review_json)
            if (type(envelope) is not dict or envelope.get("version") != REVIEWED_ACCEPTANCE_VERSION
                    or envelope.get("review_kind") != self.reviewer_kind
                    or envelope.get("review_evidence_sha256") != _sha(self.decision_evidence)
                    or envelope.get("candidate_file", {}).get("sha256") != _sha(self.evidence.candidate)
                    or envelope.get("manifest_file", {}).get("sha256") != _sha(self.evidence.manifest)
                    or type(envelope.get("source_file_sha256")) is not str
                    or envelope["source_file_sha256"] not in seen):
                _fail("ordinary_source_review_binding_changed")
            return envelope
        except OrdinaryReviewedSourceError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
            _fail("ordinary_source_review_invalid_evidence")

    def verify(self, *, source_hash: str, page_identities: dict, page_sizes: dict) -> dict[int, dict]:
        """Verify the complete browser-image source against actual caller reads."""
        try:
            self.source_guard()
        except Exception:
            _fail("ordinary_source_review_storage_changed")
        envelope = self._validate_bytes()
        try:
            if (source_hash != envelope["source_file_sha256"] or type(page_identities) is not dict
                    or not page_identities or set(page_identities) != set(range(1, len(page_identities) + 1))
                    or any(type(n) is not int or type(row) is not dict
                           or row.get("source_type") != "browser_pdf_image"
                           for n, row in page_identities.items())):
                _fail("ordinary_source_review_full_browser_source_required")
            rows = verify_source_review(self.source_review_json.decode("utf-8"),
                source_hash=source_hash, page_identities=page_identities, page_sizes=page_sizes,
                reviewed_evidence=self.evidence)
            for row in rows.values():
                source = row["source_structure"]
                if (source.get("provenance") != REVIEWED_SOURCE_VERSION
                        or source.get("metadata", {}).get("reviewed_source", {}).get("review_kind") != self.reviewer_kind):
                    _fail("ordinary_source_review_reviewer_changed")
            return rows
        except OrdinaryReviewedSourceError:
            raise
        except (ValueError, TypeError, KeyError, AttributeError, UnicodeError, RecursionError):
            _fail("ordinary_source_review_verification_failed")
