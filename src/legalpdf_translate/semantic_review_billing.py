"""Bounded actual-usage admission for the semantic-only public Astra policy.

This does not establish an input/image reservation envelope. Strict BLOCK remains
unsupported. Lower-band attribution admits actual input<=272000, not larger input.
"""
from __future__ import annotations

from collections.abc import Mapping
import hashlib
import json
from pathlib import Path
import re

# Historical callers and journals keep the original evidence/status contract.
POLICY = "astra_public_standard_lower_band_v1"
FRESH_POLICY = "astra_public_standard_lower_band_30m_v2"
MODEL = "gpt-6-astra"
MAX_INPUT_TOKENS = 272000
_KEY = "semantic_review_billing_policy"


def strict_limits(limits):
    return limits.get(_KEY) in (POLICY, FRESH_POLICY)


def _mapping(value):
    if isinstance(value, Mapping):
        return dict(value)
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dump(mode="json", exclude_none=True)
    return vars(value) if hasattr(value, "__dict__") else value


def _tree(value, depth=0):
    if depth > 3:
        raise ValueError
    if isinstance(value, Mapping) or hasattr(value, "__dict__"):
        value = _mapping(value)
        if type(value) is not dict or len(value) > 32:
            raise ValueError
        if any(type(k) is not str or len(k) > 64 or not k.replace("_", "").isalnum()
               or k.lower() in {"prompt", "source_text", "document_text", "api_key", "secret", "content"}
               for k in value):
            raise ValueError
        return {k: _tree(v, depth + 1) for k, v in value.items()}
    if value is not None and type(value) not in (int, float, bool):
        raise ValueError
    return value


def usage_evidence(usage, *, max_output_tokens, policy=POLICY):
    """Retain bounded dimensions under the caller's frozen billing policy."""
    raw, digest, status = None, None, "unsupported_usage_shape"
    try:
        raw = _tree(_mapping(usage))
        encoded = json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        if len(encoded) > 16000:
            raise ValueError
        digest = hashlib.sha256(encoded).hexdigest()
        status = (_admit(raw, max_output_tokens, policy) if policy in (POLICY, FRESH_POLICY)
                  else "unsupported_billing_policy")
    except (ValueError, TypeError, AttributeError, RecursionError, OverflowError):
        raw = None
    return {"policy": policy, "raw_usage": raw, "raw_usage_sha256": digest, "status": status}


def _admit(raw, maximum, policy):
    if type(raw) is not dict:
        return "missing_usage"
    scalar = {"input_tokens", "output_tokens", "total_tokens", "reasoning_tokens", "cached_input_tokens", "cache_write_tokens"}
    if set(raw) - scalar - {"input_tokens_details", "output_tokens_details"}:
        return "unsupported_usage_dimensions"
    for key in scalar:
        if key in raw and (type(raw[key]) is not int or raw[key] < 0):
            return "invalid_usage_counts"
    for key, allowed in (("input_tokens_details", {"cached_tokens", "cache_write_tokens"}),
                         ("output_tokens_details", {"reasoning_tokens"})):
        details = raw.get(key)
        if details is None:
            continue
        if key == "input_tokens_details" and policy == FRESH_POLICY:
            allowed = allowed | {"cache_write_tokens_details"}
        if type(details) is not dict or set(details) - allowed:
            return "unsupported_usage_dimensions"
        if any(type(v) is not int or v < 0 for k, v in details.items()
               if k != "cache_write_tokens_details"):
            return "invalid_usage_counts"
    for flat, nested, field in (("cached_input_tokens", "input_tokens_details", "cached_tokens"),
                                ("cache_write_tokens", "input_tokens_details", "cache_write_tokens"),
                                ("reasoning_tokens", "output_tokens_details", "reasoning_tokens")):
        other = (raw.get(nested) or {}).get(field)
        if raw.get(flat) is not None and other is not None and raw[flat] != other:
            return "conflicting_usage_dimensions"
    for flat, field in (("cached_input_tokens", "cached_tokens"), ("cache_write_tokens", "cache_write_tokens")):
        value = raw.get(flat)
        if value is None:
            value = (raw.get("input_tokens_details") or {}).get(field)
        if type(value) is not int or value < 0:
            return "missing_explicit_cache_dimensions"
    details = raw.get("input_tokens_details") or {}
    if policy == FRESH_POLICY and "cache_write_tokens_details" in details:
        ttl = details["cache_write_tokens_details"]
        if type(ttl) is not dict or set(ttl) != {"ttl_30m_tokens", "ttl_12h_tokens"}:
            return "unsupported_usage_dimensions"
        if any(type(v) is not int or v < 0 for v in ttl.values()):
            return "invalid_usage_counts"
        aggregate = raw.get("cache_write_tokens", details.get("cache_write_tokens"))
        if sum(ttl.values()) != aggregate:
            return "conflicting_usage_dimensions"
        if ttl["ttl_12h_tokens"] != 0:
            return "unsupported_cache_write_ttl"
    from .usage_accounting import normalize_usage
    normalized = normalize_usage(raw)
    if normalized["usage_status"] != "available":
        return "invalid_or_missing_usage"
    if normalized["input_tokens"] > MAX_INPUT_TOKENS:
        return "input_price_band_unsupported"
    if type(maximum) is not int or normalized["output_tokens"] > maximum:
        return "output_bound_exceeded"
    return "available"


def blocked(events):
    """A settled unknown strict bill remains blocked after a new process starts."""
    strict = {e["call_id"] for e in events if e.get("event") == "begin"
              and strict_limits(e.get("bounds", {}))}
    finishes = {e["call_id"]: e for e in events if e.get("event") == "finish"}
    return any(key not in finishes or finishes[key].get("cost_status") != "available" for key in strict)


MAX_RESPONSE_BYTES = 8_000_000


def parse_response_bytes(raw):
    """One raw SDK envelope; detect duplicate keys before any lossy SDK parse."""
    if type(raw) is not bytes or len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Unsupported semantic response byte bound.")
    duplicate = False
    def pairs(rows):
        nonlocal duplicate
        result = {}
        for key, value in rows:
            if key in result:
                duplicate = True
            result[key] = value
        return result
    status, data = "available", {}
    try:
        data = json.loads(raw, object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
        if type(data) is not dict:
            data, status = {}, "invalid_json_envelope"
        elif duplicate:
            status = "duplicate_json_keys"
    except (ValueError, TypeError, UnicodeError, RecursionError):
        status = "invalid_json_envelope"
    return data, {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw), "json_status": status}


def read_response(journal_dir, evidence):
    if (type(evidence) is not dict or set(evidence) != {"path", "sha256", "bytes", "json_status"}
            or type(evidence["path"]) is not str
            or re.fullmatch(r"provider_responses/[a-f0-9]{32}\.json", evidence["path"]) is None):
        raise ValueError("Invalid semantic response evidence.")
    base = Path(journal_dir)
    folder, path = base / "provider_responses", base / evidence["path"]
    if base.is_symlink() or folder.is_symlink() or path.is_symlink() or not path.is_file():
        raise ValueError("Missing semantic response evidence.")
    if type(evidence["bytes"]) is not int or not 0 <= evidence["bytes"] <= MAX_RESPONSE_BYTES:
        raise ValueError("Invalid semantic response evidence size.")
    if path.stat().st_size != evidence["bytes"]:
        raise ValueError("Semantic response evidence size changed.")
    data, metadata = parse_response_bytes(path.read_bytes())
    if {"path": evidence["path"], **metadata} != evidence:
        raise ValueError("Semantic response evidence changed.")
    return data


def response_billing_evidence(journal_dir, evidence, *, max_output_tokens,
                              response_id, actual_model, actual_service_tier, policy=POLICY):
    response = read_response(journal_dir, evidence)
    result = usage_evidence(response.get("usage"), max_output_tokens=max_output_tokens, policy=policy)
    result["response"] = dict(evidence)
    if evidence["json_status"] != "available":
        result["status"] = evidence["json_status"]
    elif (type(response.get("id")) is not str or not response["id"].strip()
          or len(response["id"]) > 512 or response["id"].strip() != response["id"]
          or "\n" in response["id"] or "\r" in response["id"]):
        result["status"] = "missing_response_identity"
    elif any(response.get(key) != value for key, value in
             (("id", response_id), ("model", actual_model), ("service_tier", actual_service_tier))):
        result["status"] = "response_identity_mismatch"
    return response, result


def validate_retained_responses(journal_dir, events):
    begins = {e["call_id"]: e for e in events if e.get("event") == "begin"}
    for finish in (e for e in events if e.get("event") == "finish"):
        begin = begins.get(finish["call_id"], {})
        if not strict_limits(begin.get("bounds", {})) or finish["outcome"] == "not_dispatched":
            continue
        evidence = finish.get("semantic_review_billing_evidence")
        if type(evidence) is not dict or "response" not in evidence:
            raise ValueError("Missing native semantic response proof.")
        response, expected = response_billing_evidence(journal_dir, evidence["response"],
            max_output_tokens=begin["bounds"].get("max_output_tokens"), response_id=finish.get("response_id"),
            actual_model=finish.get("actual_model"), actual_service_tier=finish.get("actual_service_tier"),
            policy=begin["bounds"][_KEY])
        from .usage_accounting import normalize_usage
        if expected != evidence or normalize_usage(response.get("usage"), provider=begin["provider"]) != finish["usage"]:
            raise ValueError("Native semantic response proof changed.")
