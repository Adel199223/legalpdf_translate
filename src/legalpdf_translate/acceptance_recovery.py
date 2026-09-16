"""Explicit offline derivatives of successful, immutable acceptance responses.

This is not checkpoint resume, paid authorization, or legal/layout certification.
Callers supply independently pinned historical evidence and a live source guard.
There is deliberately no provider, credential or accounting interface here.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

from .document_structure import validate_page_structure
from .formatting_support import digest_text, fingerprint, flatten_blocks
from .glossary import normalize_enabled_tiers_by_target_lang, normalize_glossaries
from .new_translation_blocks import validate_block
from .structured_arabic_literals import STRUCTURED_ARABIC_LITERALS_VERSION
from .structured_artifacts import (StructuredArtifactError, _decode, _json,
    _publish_file_exclusive, _read_file, publish_structured_page, validate_structured_page)
from .structured_glossary import build_structured_glossary
from .translation_structure import parse_structured_translation, structured_system_instructions
from .types import TargetLang

RECOVERY_VERSION = "legal_blocks_recovery_v1"
_HASH = re.compile(r"[a-f0-9]{64}\Z")
# Exact UTF-8 instruction digests from the preserved pre-pagination-clarification
# source. Never derive admitted historical profiles from today's prompt text.
_HISTORICAL_INSTRUCTIONS = {
    "EN": "58b7ae6f8e0ec7e156676596f7781bacad231c38d35c2014846ba2dc50733640",
    "FR": "600dfda29fd67fdb9f120f47eafbfa12194891a1d1ad3e47ef322ab3c360d37f",
    "AR": "9388c2a99d6da0f883a655d13e4f7d5998a335941e0c5215d6cca6f6e8021aee",
}


class AcceptanceRecoveryError(StructuredArtifactError):
    """Content-free failure; original journals are never changed."""


@dataclass(frozen=True)
class PinnedJSON:
    path: Path
    sha256: str

    def read(self):
        if not isinstance(self.sha256, str) or not _HASH.fullmatch(self.sha256):
            raise AcceptanceRecoveryError("invalid_recovery_pin")
        data = _read_file(Path(self.path))
        if hashlib.sha256(data).hexdigest() != self.sha256:
            raise AcceptanceRecoveryError("recovery_evidence_changed")
        return _decode(data)


def _envelope(record, identity):
    if (not isinstance(record, dict) or set(record) != {"version", "identity", "payload", "sha256"}
            or type(record["version"]) is not int or record["version"] != 1
            or record["identity"] != identity or not isinstance(record["payload"], dict)
            or fingerprint({k: v for k, v in record.items() if k != "sha256"}) != record["sha256"]):
        raise AcceptanceRecoveryError("invalid_historical_recovery_envelope")
    return record["payload"]


def _visible(text):
    return re.sub("[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text).replace("[[", "").replace("]]", "")


def recover_saved_page(*, intent: PinnedJSON, response: PinnedJSON, preferences: PinnedJSON,
                       historical_identity: dict, request_sha256: str, source_structure,
                       source_structure_sha256: str, source_guard, validator_binding: str,
                       lang: TargetLang, pages_dir: Path,
                       historical_instruction_binding: PinnedJSON | None = None) -> dict:
    """Strict packaging-only recovery; visible paid translation cannot change."""
    return _recover_page(**locals())


def recover_reviewed_page(*, intent: PinnedJSON, response: PinnedJSON, preferences: PinnedJSON,
                          historical_identity: dict, request_sha256: str, source_structure,
                          source_structure_sha256: str, source_guard, validator_binding: str,
                          lang: TargetLang, pages_dir: Path, review_manifest: PinnedJSON,
                          historical_instruction_binding: PinnedJSON | None = None) -> dict:
    """Publish a separately identified, explicitly AI-reviewed text derivative."""
    if type(review_manifest) is not PinnedJSON:
        raise AcceptanceRecoveryError('pinned_review_manifest_required')
    return _recover_page(**locals())


def _recover_page(*, intent: PinnedJSON, response: PinnedJSON, preferences: PinnedJSON,
                  historical_identity: dict, request_sha256: str, source_structure,
                  source_structure_sha256: str, source_guard, validator_binding: str,
                  lang: TargetLang, pages_dir: Path, review_manifest: PinnedJSON | None = None,
                  historical_instruction_binding: PinnedJSON | None = None) -> dict:
    """Validate old paid bytes with today's policy; publish a distinctly named bundle.

The guard must recheck the source review and all its physical dependencies.
Validator binding is the caller's exact current code-manifest digest. Neither
that digest nor the historical file pins purport to be a signed trust root.
Historical compatibility is explicit and pins a known prior language profile.
The caller's guard must still verify actual operation/model/response provenance.
"""
    if not callable(source_guard) or not _HASH.fullmatch(validator_binding):
        raise AcceptanceRecoveryError("recovery_source_guard_required")
    if historical_instruction_binding is not None and type(historical_instruction_binding) is not PinnedJSON:
        raise AcceptanceRecoveryError("pinned_historical_instruction_binding_required")
    identity = deepcopy(historical_identity)
    source = validate_page_structure(source_structure)
    if source.fingerprint != source_structure_sha256:
        raise AcceptanceRecoveryError("recovery_source_changed")
    full_pages = identity.get("full_case_pages")
    if (not isinstance(full_pages, list) or not full_pages
            or any(type(n) is not int or n < 1 for n in full_pages)
            or full_pages != sorted(set(full_pages)) or source.page_number not in full_pages
            or identity.get("page_number") != source.page_number):
        raise AcceptanceRecoveryError("recovery_page_selection_mismatch")

    def guard():
        source_guard()
        intent.read()
        response.read()
        preferences.read()
        if review_manifest is not None:
            review_manifest.read()
        if historical_instruction_binding is not None:
            historical_instruction_binding.read()

    guard()
    old_intent, old_response = intent.read(), response.read()
    request_payload = _envelope(old_intent, identity)
    saved = _envelope(old_response, identity)
    if (set(request_payload) != {"request", "approval_sha256"}
            or not isinstance(request_payload["request"], dict)
            or not isinstance(request_payload["approval_sha256"], str)
            or not _HASH.fullmatch(request_payload["approval_sha256"])
            or set(saved) != {"intent_sha256", "response", "usage", "metadata"}
            or saved["intent_sha256"] != old_intent["sha256"]
            or not all(isinstance(saved[k], dict) for k in ("response", "usage", "metadata"))):
        raise AcceptanceRecoveryError("recovery_response_binding_invalid")
    request = request_payload["request"]
    if fingerprint(request) != request_sha256:
        raise AcceptanceRecoveryError("recovery_request_changed")
    instruction_provenance = None
    if historical_instruction_binding is None:
        if request.get("instructions") != structured_system_instructions(lang):
            raise AcceptanceRecoveryError("recovery_language_or_instructions_mismatch")
    else:
        paid = saved["response"]
        instructions = request.get("instructions")
        if (not isinstance(lang, TargetLang) or not isinstance(instructions, str)
                or hashlib.sha256(instructions.encode("utf-8")).hexdigest() != _HISTORICAL_INSTRUCTIONS[lang.value]
                or paid.get("model") not in ("gpt-5.2", "gpt-5.6-terra", "gpt-5.6-sol")
                or paid.get("effort") not in ("high", "xhigh")
                or request.get("effort") != paid.get("effort")):
            raise AcceptanceRecoveryError("invalid_historical_instruction_binding")
        expected = {"version": "acceptance_historical_instruction_binding_v1",
            "profile": "legal_blocks_pre_pagination_clarification_v1", "target_lang": lang.value,
            "instructions_sha256": _HISTORICAL_INSTRUCTIONS[lang.value],
            "intent_sha256": intent.sha256, "response_sha256": response.sha256,
            "request_sha256": request_sha256, "preferences_sha256": preferences.sha256,
            "source_structure_sha256": source_structure_sha256,
            "historical_identity_sha256": fingerprint(identity),
            "expected_model": paid["model"], "expected_effort": paid["effort"]}
        record = historical_instruction_binding.read()
        if type(record) is not dict or record != expected:
            raise AcceptanceRecoveryError("invalid_historical_instruction_binding")
        instruction_provenance = {**record, "manifest_file_sha256": historical_instruction_binding.sha256}
    prompt_text = request.get("prompt_text")
    if not isinstance(prompt_text, str):
        raise AcceptanceRecoveryError("recovery_source_prompt_invalid")
    try:
        prompt, end = json.JSONDecoder().raw_decode(prompt_text)
        # Strict decoding rejects duplicate keys/nonfinite values in the prefix.
        prompt = _decode(prompt_text[:end].encode("utf-8"))
        rows = prompt["blocks"]
        source_rows = source.to_dict()["blocks"]
        if (prompt["page"] != source.page_number or prompt["total_pages"] < max(full_pages)
                or len(rows) != len(source_rows)
                or any(set(row) != {"id", "text"} or row["id"] != block["id"]
                    or _visible(row["text"]) != _visible(block["text"])
                    for row, block in zip(rows, source_rows))):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise AcceptanceRecoveryError("recovery_source_prompt_mismatch") from None
    prefs = preferences.read()
    code = lang.value
    entries = normalize_glossaries(prefs.get("personal_glossaries_by_lang", prefs.get("glossaries_by_lang")), [code])[code]
    tiers = normalize_enabled_tiers_by_target_lang(prefs.get("enabled_glossary_tiers_by_target_lang"), [code])[code]
    glossary = build_structured_glossary(rows, entries, target_lang=code, enabled_tiers=tiers)
    addendum = str((prefs.get("prompt_addendum_by_lang") or {}).get(code, "") or "").strip()
    tail = ("\n" + glossary.prompt_text if glossary.prompt_text else "") + ("\n" + addendum if addendum else "")
    if prompt_text[end:] != tail:
        raise AcceptanceRecoveryError("recovery_glossary_prompt_mismatch")
    paid = saved["response"]
    translated = parse_structured_translation(paid.get("raw_output"), rows, page_number=source.page_number,
        response_status=paid.get("response_status"), refused=paid.get("refused", True))
    review, version = None, RECOVERY_VERSION
    if review_manifest is not None:
        from .acceptance_review import apply_reviewed_edits, REVIEWED_RECOVERY_VERSION
        translated, review = apply_reviewed_edits(review_manifest.read(), rows, translated,
            expected_binding={'intent_sha256': intent.sha256, 'response_sha256': response.sha256,
                'preferences_sha256': preferences.sha256, 'source_structure_sha256': source_structure_sha256,
                'historical_identity_sha256': fingerprint(identity), 'target_lang': code})
        # Validate the reviewed derivative's complete block/marker structure too;
        # this is not a newly returned provider response or replacement receipt.
        translated = parse_structured_translation(_json({'blocks': translated}).decode('utf-8'), rows,
            page_number=source.page_number, response_status='completed', refused=False)
        review['manifest_file_sha256'] = review_manifest.sha256
        version = REVIEWED_RECOVERY_VERSION
    review_codes = {"legal_fidelity_not_evaluated"}
    normalized = [{"id": left["id"], "text": validate_block(left, right["text"], lang,
        glossary.for_block(left["id"]), review_codes)} for left, right in zip(rows, translated)]
    if any(_visible(before["text"]) != _visible(after["text"]) for before, after in zip(translated, normalized)):
        raise AcceptanceRecoveryError("recovery_changed_visible_translation")
    if review is not None and fingerprint({row['id']: _visible(row['text']) for row in normalized}) != review['reviewed_visible_sha256']:
        # Parsing trims outer whitespace. Even that must not silently alter an
        # explicitly reviewed edit or make its recorded hash describe other text.
        raise AcceptanceRecoveryError('recovery_changed_reviewed_translation')
    provenance = {
        "version": version, "historical_identity": identity,
        "historical_intent_file_sha256": intent.sha256, "historical_response_file_sha256": response.sha256,
        "historical_request_sha256": request_sha256, "preferences_sha256": preferences.sha256,
        "source_structure_sha256": source_structure_sha256, "validator_binding": validator_binding,
        "literal_policy": STRUCTURED_ARABIC_LITERALS_VERSION, "glossary_fingerprint": glossary.fingerprint,
        "lang": code, "historical_model": paid.get("model"), "historical_effort": paid.get("effort"),
        "historical_usage": deepcopy(saved["usage"]), "historical_response_usage": deepcopy(paid.get("usage")),
        "recovery_provider_dispatch_count": 0, "recovery_cost_usd": "0", "workflow_resumed": False,
        "full_case_complete": False, "visible_translation_unchanged": review is None,
        "fidelity_status": "not_evaluated", "layout_status": "not_evaluated",
        "review_codes": sorted(review_codes),
    }
    if review is not None:
        provenance['explicit_ai_review'] = review
    if instruction_provenance is not None:
        provenance['historical_instruction_binding'] = instruction_provenance
    recovery_identity = {"protocol": version, "fingerprint": fingerprint(provenance)}
    page_fingerprint = fingerprint({"recovery": recovery_identity, "page": source.page_number})
    text = flatten_blocks(normalized)
    target = source.to_dict()
    target["blocks"] = [{**block, "text": row["text"]} for block, row in zip(target["blocks"], normalized)]
    target["translation_sha256"] = digest_text(text)
    target["metadata"].update(recovery=provenance, protocol=version,
        translation_fingerprint=page_fingerprint,
        review={"fidelity_status": "not_evaluated", "human_review_required": True})
    commit = publish_structured_page(pages_dir, source_structure=source, translated_structure=target,
        translated_text=text, protocol_identity=recovery_identity, page_fingerprint=page_fingerprint,
        evidence_guard=guard, page_result=None)  # Not an orphan checkpoint/resume receipt.
    guard()
    return {"commit": commit, "provenance": provenance}


def assemble_recovered_page(pages_dir: Path, output_dir: Path, *, recovery: dict,
                            evidence_guard, writer=None) -> Path:
    """One partial review DOCX, with strict commit checks around the legacy writer.

The new output directory is exclusively created; failures retain their evidence.
Never call the writer on a pre-existing deliverable or label this a full case.
"""
    if not callable(evidence_guard):
        raise AcceptanceRecoveryError("recovery_source_guard_required")
    record, provenance = deepcopy(recovery["commit"]), deepcopy(recovery["provenance"])
    expected_identity = {"protocol": RECOVERY_VERSION, "fingerprint": fingerprint(provenance)}
    page = record["page_number"]
    page_fingerprint = fingerprint({"recovery": expected_identity, "page": page})
    if provenance.get("full_case_complete") is not False or provenance.get("workflow_resumed") is not False:
        raise AcceptanceRecoveryError("recovery_is_partial_only")
    def check():
        evidence_guard()
        # These optional, non-committed derivatives also influence the writer.
        # This recovery path has no accepted layout evidence; do not adopt them.
        for suffix in ("layout.json", "layout_eligibility.json"):
            extra = Path(pages_dir) / f"page_{page:04d}.{suffix}"
            if extra.exists() or extra.is_symlink():
                raise AcceptanceRecoveryError("recovery_unbound_layout_derivative")
        return validate_structured_page(pages_dir, page, protocol_identity=expected_identity,
            page_fingerprint=page_fingerprint, expected_commit=record)
    check()
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=False)
    total = max(provenance["historical_identity"]["full_case_pages"])
    output = output_dir / f"recovered_page_{page:04d}_of_{total:04d}_{provenance['lang']}.docx"
    if writer is None:
        from .docx_writer import assemble_docx
        writer = assemble_docx
    stats = {}
    writer(Path(pages_dir), output, lang=TargetLang(provenance["lang"]), page_breaks=False,
        page_numbers=[page], partial_output=True, derive_source_continuations=True, stats=stats)
    check()
    if stats.get("structured_page_count") != 1 or stats.get("structure_fallback_count") != 0:
        raise AcceptanceRecoveryError("recovery_writer_used_text_fallback")
    manifest = {"kind": "partial_recovered_page_review", "full_case_complete": False,
        "source_page_number": page, "full_case_pages": provenance["historical_identity"]["full_case_pages"],
        "bundle_sha256": record["bundle_sha256"], "docx_sha256": hashlib.sha256(_read_file(output)).hexdigest(),
        "recovery": provenance, "assembly_stats": stats, "rendered_layout_acceptance": "not_evaluated"}
    _publish_file_exclusive(output_dir / "recovery_review.json", _json(manifest))
    return output
