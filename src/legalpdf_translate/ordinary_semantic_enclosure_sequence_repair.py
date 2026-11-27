"""Opt-in rejection admission; never authority for a reordered final candidate."""
from collections import Counter
from dataclasses import asdict
import json

from . import ordinary_semantic_enclosure_authority as enclosure
from . import ordinary_semantic_enclosure_identity as identity
from . import ordinary_semantic_literal_authority as literal
from . import ordinary_semantic_review as review

KEY = "semantic_enclosure_sequence_repair_policy"
POLICY = "initial_enclosure_permutation_replacement_v1"


def _fail(code):
    review._fail("enclosure_sequence_repair_" + code)


def check_policy(policy):
    if policy is not None and (type(policy) is not str or policy != POLICY):
        _fail("policy")


def descriptor():
    return {"policy": POLICY, "admission": "initial_enclosure_only_old_multiset_permutation_v1",
        "result": "existing_single_replacement_only_v1", "final_order": "unchanged_projected_old_sequence_v1",
        "identity": identity.descriptor()}


def _encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")


def check_eligibility(raw, pages, inventory, recipe, registry, cert, context, *, identity_policy=None):
    """Permit only dispatch of the existing replacement, returning no text."""
    if identity_policy != identity.POLICY:
        _fail("dependency")
    data = literal.parse_correction(raw, pages, inventory)
    candidates = [p.primary_text if row["status"] == "no_change" else row["corrected_text"]
        for p, row in zip(pages, data["pages"])]
    if (type(cert) is not dict or cert.get("literal_certificate") is not None
            or not cert.get("enclosure_observations") or registry.get("availability") != "complete"):
        _fail("certificate")
    # Charge before new views, Counters or certificate reconstruction. The
    # projected baselines belong to the already-established authority context.
    identity.WorkBudget().charge([p.primary_text for p in pages],
        [p.primary_text for p in context.projected_pages], candidates)
    expected_context = enclosure.project(pages, registry, cert, identity_policy=identity_policy)
    if _encode(asdict(context)) != _encode(asdict(expected_context)):
        _fail("context")
    budget = identity.AdditionBudget()
    reordered = False
    for original, projected, text in zip(pages, expected_context.projected_pages, candidates):
        _, old = enclosure._tokens(original.primary_text)
        _, effective = enclosure._tokens(projected.primary_text)
        values = [t[2] for t in effective]
        if [t[2] for t in old] != values:
            _fail("baseline")
        _, tokens = enclosure._candidate_tokens(text)
        if len(tokens) > len(values) + identity.MAX_PAGE_OCCURRENCES:
            _fail("page_bound")
        forbidden = {t[2] for t in old} | set(values)
        proposed_old = [t[2] for t in tokens if t[2] in forbidden]
        if Counter(proposed_old) != Counter(values):
            _fail("old_multiset")
        reordered |= proposed_old != values
        # This private order is solely an addition filter/budget. It never
        # replaces the projected old sequence used by final validation.
        budget.mapping(tokens, proposed_old, [t[2] for t in old])
    # Reconstruct occurrence ownership from this exact rejected raw proposal,
    # not from mutable observation lookups or candidate positions supplied by it.
    eligibility = enclosure.classify(raw, pages, inventory, recipe, registry)
    if eligibility is None or eligibility["lookups"]:
        _fail("certificate")
    answer = {"version": enclosure.RESPONSE, "literal_decisions": [], "enclosure_observations": [
        {"occurrence_id": row["old_occurrence"]["occurrence_id"],
         "exact_reading": row["old_occurrence"]["value"], "ownership": "owned",
         "enclosure": row["enclosure"], "source_image": row["source_image"]}
        for row in cert["enclosure_observations"]]}
    expected_cert = enclosure.certificate(review.audit._json(answer), pages, registry, eligibility)
    # These producer commitments bind original resolver bytes/native dispatch,
    # which are verified by the existing stage loader, not recreated here.
    expected_cert["resolution_sha256"] = cert.get("resolution_sha256")
    if "native_resolution_binding" in cert:
        expected_cert["native_resolution_binding"] = cert["native_resolution_binding"]
    if _encode(expected_cert) != _encode(cert):
        _fail("certificate")
    if not reordered:
        _fail("no_permutation")
