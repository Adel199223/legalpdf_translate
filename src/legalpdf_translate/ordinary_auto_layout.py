"""Bounded source-image layout stage for fresh ordinary browser translations.

Translation remains the existing ordinary protocol. This stage keeps its raw
DOCX and writer map, makes one initial proposal per selected source page,
and permits only the explicitly saved fresh recipe's one global replacement.
It publishes only a separately verified unreviewed candidate.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from decimal import Decimal

from .ordinary_layout_contracts import encode, decode, fail
from .run_workspace_lock import run_workspace_slot
from . import saved_docx_layout_service as storage
from .translation_policy import ORDINARY_AUTO_LAYOUT_POLICY

_POLICY_RE = re.compile(r"source_image_unreviewed_v1:([a-f0-9]{64})\Z")


def frozen_automatic_layout_policy() -> str:
    """Freeze local price, request and validation versions before translation."""
    return _source_alignment_v20_policy()


def _body_columns_v3_policy() -> str:
    """Exact prior body-columns recipe; clock capability remains absent."""
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3", emphasis_normalization=True, metadata_normalization=True, primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True, metadata_normalization_version="ordinary_metadata_band_normalization_v3", source_folio_direction_version="numeric_run_ltr_v3")


def _optional_hint_policy(normalization_version: str, *, emphasis_normalization=False, metadata_normalization=False, primary_folio_version="terminal_labeled_folio_v1", source_folio_proof=False, metadata_normalization_version="ordinary_metadata_band_normalization_v1", source_folio_direction_version="numeric_run_ltr_v2", clock_direction_version=None, source_folio_inline_direction_version=None, emphasis_normalization_version="ordinary_optional_emphasis_normalization_v1", terminal_source_layout=False, closing_group=False, closing_group_version="bounded_terminal_signature_context_v1", proposal_repair_policy=None, source_in_flow_folio_direction_version=None, source_labeled_folio_direction_version=None, instruction_version=None) -> str:
    """Exact versioned capability identities; no arbitrary historical-policy admission."""
    from .ordinary_layout_accounting import layout_accounting_policy
    from .ordinary_layout_contracts import PROPOSAL_VERSION_V3
    from .ordinary_layout_manager import INSTRUCTIONS, INSTRUCTIONS_SOURCE_ALIGNMENT_V1

    if instruction_version is None:
        instructions = INSTRUCTIONS
    elif instruction_version == "source_alignment_v1":
        instructions = INSTRUCTIONS_SOURCE_ALIGNMENT_V1
    else:
        fail("source_alignment_instruction_version")
    accounting = layout_accounting_policy()
    identity = {"version": ORDINARY_AUTO_LAYOUT_POLICY,
        "proposal_version": PROPOSAL_VERSION_V3,
        "automatic_writer_version": "saved_docx_layout_writer_source_layout_v7",
        "source_folio_direction_version": source_folio_direction_version,
        "source_layout_normalization_version": normalization_version,
        "instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
        "pricing_catalog": json.loads(accounting._pricing_json),
        "dispatch_limits": json.loads(accounting._limits_json)}
    if instruction_version == "source_alignment_v1":
        from .ordinary_source_line_map import recipe_descriptor
        identity["native_source_line_map_policy"] = recipe_descriptor()
    if emphasis_normalization:
        if emphasis_normalization_version not in {"ordinary_optional_emphasis_normalization_v1", "ordinary_optional_emphasis_normalization_v2", "ordinary_optional_emphasis_normalization_v3"}:
            fail("invalid_emphasis_normalization_version")
        identity["optional_emphasis_normalization_version"] = emphasis_normalization_version
    if metadata_normalization:
        identity["metadata_band_normalization_version"] = metadata_normalization_version
        identity["primary_folio_version"] = primary_folio_version
    if source_folio_proof:
        from .ordinary_source_folio_proof import VERSION
        identity["local_source_folio_proof_version"] = VERSION
    if clock_direction_version is not None:
        if clock_direction_version != "clock_h_colon_ltr_v1":
            fail("source_clock_direction_version")
        identity["clock_direction_version"] = clock_direction_version
    if source_folio_inline_direction_version is not None:
        from .ordinary_source_layout import INLINE_FOLIO_DIRECTION_V1, INLINE_FOLIO_DIRECTION_V2, INLINE_FOLIO_DIRECTION_V3
        if source_folio_inline_direction_version not in (INLINE_FOLIO_DIRECTION_V1, INLINE_FOLIO_DIRECTION_V2, INLINE_FOLIO_DIRECTION_V3):
            fail("source_inline_folio_direction_version")
        identity["source_folio_inline_direction_version"] = source_folio_inline_direction_version
    if terminal_source_layout:
        identity["source_footer_placement_version"] = "terminal_body_flow_v1"
        identity["source_spacing_version"] = "baseline_metadata_heading_spacing_v1"
    if closing_group:
        if closing_group_version not in {"bounded_terminal_signature_context_v1", "bounded_terminal_signature_context_v2", "bounded_terminal_signature_context_v3", "bounded_terminal_signature_context_v4", "bounded_terminal_signature_context_v5"}:
            fail("source_closing_group_version")
        identity["source_closing_group_version"] = closing_group_version
    if proposal_repair_policy is not None:
        from .ordinary_layout_reproposal import descriptor
        identity["proposal_repair_policy"] = descriptor(proposal_repair_policy)
    if source_in_flow_folio_direction_version is not None:
        from .ordinary_in_flow_folio_bridges import KEY, VERSION
        if source_in_flow_folio_direction_version != VERSION:
            fail("source_in_flow_folio_direction_version", 409)
        identity[KEY] = VERSION
    if source_labeled_folio_direction_version is not None:
        from .ordinary_labeled_folio_direction import KEY, VERSION
        from .ordinary_labeled_folio_direction_v2 import VERSION as VERSION_V2
        if source_labeled_folio_direction_version not in {VERSION, VERSION_V2}:
            fail("source_labeled_folio_direction_version", 409)
        identity[KEY] = source_labeled_folio_direction_version
    return ORDINARY_AUTO_LAYOUT_POLICY + ":" + hashlib.sha256(encode(identity)).hexdigest()


def _clock_direction_policy():
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v3",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1")


def _heading_columns_v4_policy():
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v4",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1")


def _reference_footer_v5_policy():
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v5",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1")


def _inline_folio_direction_policy():
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v5",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1")


def _source_folio_inline_direction_version(policy_fingerprint):
    if policy_fingerprint in {_contact_folio_overlap_v19_policy().split(":",1)[1], _source_alignment_v20_policy().split(":",1)[1]}:
        from .ordinary_source_layout import INLINE_FOLIO_DIRECTION_V3
        return INLINE_FOLIO_DIRECTION_V3
    if policy_fingerprint == _contact_folio_v18_policy().split(":",1)[1]:
        from .ordinary_source_layout import INLINE_FOLIO_DIRECTION_V2
        return INLINE_FOLIO_DIRECTION_V2
    return ("source_bound_folio_separator_ltr_v1"
        if policy_fingerprint in {p.split(":",1)[1] for p in (_inline_folio_direction_policy(),_complete_lrm_emphasis_policy(),_terminal_source_layout_policy(),_terminal_closing_group_policy(),_plain_list_columns_v6_policy(),_terminal_footer_membership_v7_policy(),_in_body_terminal_closing_v8_policy(),_adjacent_lrm_emphasis_v9_policy(),_protected_folio_bridges_v10_policy(), _bounded_page_reproposal_v11_policy(), _per_page_reproposal_v12_policy(), _in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy())} else None)


def _complete_lrm_emphasis_policy():
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v5",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v2")


def _terminal_source_layout_policy():
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v5",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v2",
        terminal_source_layout=True)


def _terminal_closing_group_policy():
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v5",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v2",
        terminal_source_layout=True, closing_group=True)


def _plain_list_columns_v6_policy():
    """Fresh plain-list band proof; prior terminal-closing recipe stays exact."""
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v6",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v2",
        terminal_source_layout=True, closing_group=True)


def _terminal_footer_membership_v7_policy():
    """Fresh target-footer association and certified predecessor-table boundary."""
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v7",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v2",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v2")


def _in_body_terminal_closing_v8_policy():
    """Fresh positive in-body terminal association and exact carrier proof."""
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v2",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v3")

def _adjacent_lrm_emphasis_v9_policy():
    """Fresh adjacent canonical LRM owner hint omission; concrete V8 stays exact."""
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v3", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v3")


def _protected_folio_bridges_v10_policy():
    """Fresh protected folio bridge direction; concrete V9 stays exact."""
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v4", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v3")


def _bounded_page_reproposal_v11_policy():
    """Fresh one-slot page re-proposal; all concrete V10 capabilities stay exact."""
    from .ordinary_layout_reproposal import POLICY
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v4", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v3", proposal_repair_policy=POLICY)


def _proposal_repair_version(policy_fingerprint):
    from .ordinary_layout_reproposal import POLICY, POLICY_V2
    for policy, recipe in ((POLICY, _bounded_page_reproposal_v11_policy()),
                           (POLICY_V2, _per_page_reproposal_v12_policy()),
                           (POLICY_V2, _in_flow_folio_bridges_v13_policy()),
                           (POLICY_V2, _labeled_folio_direction_v14_policy()),
                           (POLICY_V2, _terminal_punctuation_folio_v15_policy()),
                           (POLICY_V2, _bounded_signature_label_v16_policy()),
                           (POLICY_V2, _local_footer_closing_v17_policy()),
                           (POLICY_V2, _contact_folio_v18_policy()), (POLICY_V2, _contact_folio_overlap_v19_policy()),
                           (POLICY_V2, _source_alignment_v20_policy())):
        if policy_fingerprint == recipe.split(":", 1)[1]:
            return policy
    return None


def _per_page_reproposal_v12_policy():
    """Fresh one replacement per selected page; concrete V11 stays immutable."""
    from .ordinary_layout_reproposal import POLICY_V2
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v4", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v3", proposal_repair_policy=POLICY_V2)


def _in_flow_folio_bridges_v13_policy():
    """Fresh local accepted-footer bridges, without changing V4 promotion."""
    from .ordinary_layout_reproposal import POLICY_V2
    from .ordinary_in_flow_folio_bridges import VERSION
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v4", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v3", proposal_repair_policy=POLICY_V2,
        source_in_flow_folio_direction_version=VERSION)


def _labeled_folio_direction_v14_policy():
    """Fresh whole labelled fraction direction, preserving V4 and in-flow V1."""
    from .ordinary_layout_reproposal import POLICY_V2
    from .ordinary_in_flow_folio_bridges import VERSION
    from .ordinary_labeled_folio_direction import VERSION as LABELED
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v4", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v3", proposal_repair_policy=POLICY_V2,
        source_in_flow_folio_direction_version=VERSION, source_labeled_folio_direction_version=LABELED)


def _terminal_punctuation_folio_v15_policy():
    """Fresh separately owned terminal-period proof; all concrete V14 contracts remain exact."""
    from .ordinary_layout_reproposal import POLICY_V2
    from .ordinary_in_flow_folio_bridges import VERSION
    from .ordinary_labeled_folio_direction_v2 import VERSION as LABELED
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v4", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v3", proposal_repair_policy=POLICY_V2,
        source_in_flow_folio_direction_version=VERSION, source_labeled_folio_direction_version=LABELED)


def _bounded_signature_label_v16_policy():
    """Fresh bounded signature-label pagination; all concrete V15 contracts remain exact."""
    from .ordinary_layout_reproposal import POLICY_V2
    from .ordinary_in_flow_folio_bridges import VERSION
    from .ordinary_labeled_folio_direction_v2 import VERSION as LABELED
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v4", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version="source_bound_folio_separator_ltr_v1",
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v4", proposal_repair_policy=POLICY_V2,
        source_in_flow_folio_direction_version=VERSION, source_labeled_folio_direction_version=LABELED)

def _local_footer_closing_v17_policy():
    from .ordinary_source_layout import INLINE_FOLIO_DIRECTION_V1
    return _local_footer_policy(INLINE_FOLIO_DIRECTION_V1)


def _contact_folio_v18_policy():
    from .ordinary_source_layout import INLINE_FOLIO_DIRECTION_V2
    return _local_footer_policy(INLINE_FOLIO_DIRECTION_V2)


def _contact_folio_overlap_v19_policy():
    from .ordinary_source_layout import INLINE_FOLIO_DIRECTION_V3
    return _local_footer_policy(INLINE_FOLIO_DIRECTION_V3)


def _source_alignment_v20_policy():
    """Source-line alignment guidance with the complete concrete V19 capabilities."""
    from .ordinary_source_layout import INLINE_FOLIO_DIRECTION_V3
    return _local_footer_policy(INLINE_FOLIO_DIRECTION_V3, instruction_version="source_alignment_v1")


def _local_footer_policy(inline_mode, *, instruction_version=None):
    """The contact-folio version changes local direction only, after proposal selection."""
    from .ordinary_layout_reproposal import POLICY_V2
    from .ordinary_in_flow_folio_bridges import VERSION
    from .ordinary_labeled_folio_direction_v2 import VERSION as LABELED
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v8",
        source_folio_direction_version="numeric_run_ltr_v4", clock_direction_version="clock_h_colon_ltr_v1",
        source_folio_inline_direction_version=inline_mode,
        emphasis_normalization_version="ordinary_optional_emphasis_normalization_v3",
        terminal_source_layout=True, closing_group=True,
        closing_group_version="bounded_terminal_signature_context_v5", proposal_repair_policy=POLICY_V2,
        source_in_flow_folio_direction_version=VERSION, source_labeled_folio_direction_version=LABELED,
        instruction_version=instruction_version)



def _proposal_render_profile(policy_fingerprint):
    """Only V13 supplies a new private renderer; absent still means saved V12."""
    return policy_fingerprint if policy_fingerprint in {p.split(":", 1)[1] for p in (_in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy())} else None


def manual_automatic_layout_policy():
    """Explicit recovery remains the concrete historical target, with no repair grant."""
    return _protected_folio_bridges_v10_policy()


def supports_manual_layout_recovery(policy):
    return not (type(policy) is str and _proposal_repair_version(policy.split(":", 1)[-1]) is not None)




def _source_folio_direction_version(policy_fingerprint):
    """Exact saved numeric identities shared by evidence and actual attachment."""
    if policy_fingerprint in {p.split(":",1)[1] for p in (_protected_folio_bridges_v10_policy(), _bounded_page_reproposal_v11_policy(), _per_page_reproposal_v12_policy(), _in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy())}:
        return "numeric_run_ltr_v4"
    if policy_fingerprint in {p.split(":",1)[1] for p in (
            _adjacent_lrm_emphasis_v9_policy(), _in_body_terminal_closing_v8_policy(),
            _terminal_footer_membership_v7_policy(), _plain_list_columns_v6_policy(),
            _terminal_closing_group_policy(), _terminal_source_layout_policy(),
            _complete_lrm_emphasis_policy(), _inline_folio_direction_policy(),
            _reference_footer_v5_policy(), _heading_columns_v4_policy(), _clock_direction_policy(),
            _body_columns_v3_policy(), _source_bound_v4_policy())}:
        return "numeric_run_ltr_v3"
    return None


def _terminal_source_layout_versions(policy_fingerprint):
    if policy_fingerprint in {_contact_folio_v18_policy().split(":",1)[1], _contact_folio_overlap_v19_policy().split(":",1)[1], _source_alignment_v20_policy().split(":",1)[1]}:
        return _terminal_source_layout_versions(_local_footer_closing_v17_policy().split(":",1)[1])
    if policy_fingerprint == _local_footer_closing_v17_policy().split(":", 1)[1]:
        return {**_terminal_source_layout_versions(_bounded_signature_label_v16_policy().split(":", 1)[1]),
            "source_closing_group_version":"bounded_terminal_signature_context_v5"}
    if policy_fingerprint == _bounded_signature_label_v16_policy().split(":", 1)[1]:
        return {**_terminal_source_layout_versions(_terminal_punctuation_folio_v15_policy().split(":", 1)[1]),
            "source_closing_group_version":"bounded_terminal_signature_context_v4"}
    if policy_fingerprint == _terminal_punctuation_folio_v15_policy().split(":", 1)[1]:
        from .ordinary_labeled_folio_direction_v2 import KEY, VERSION
        return {**_terminal_source_layout_versions(_labeled_folio_direction_v14_policy().split(":", 1)[1]), KEY: VERSION}
    if policy_fingerprint == _labeled_folio_direction_v14_policy().split(":", 1)[1]:
        from .ordinary_labeled_folio_direction import KEY, VERSION
        return {**_terminal_source_layout_versions(_in_flow_folio_bridges_v13_policy().split(":", 1)[1]), KEY: VERSION}
    if policy_fingerprint == _in_flow_folio_bridges_v13_policy().split(":", 1)[1]:
        from .ordinary_in_flow_folio_bridges import KEY, VERSION
        return {**_terminal_source_layout_versions(_per_page_reproposal_v12_policy().split(":", 1)[1]), KEY: VERSION}
    if policy_fingerprint in {p.split(":",1)[1] for p in (_in_body_terminal_closing_v8_policy(), _adjacent_lrm_emphasis_v9_policy(), _protected_folio_bridges_v10_policy(), _bounded_page_reproposal_v11_policy(), _per_page_reproposal_v12_policy(), _in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy())}:
        return {"source_footer_placement_version":"terminal_body_flow_v1",
                "source_spacing_version":"baseline_metadata_heading_spacing_v1",
                "source_closing_group_version":"bounded_terminal_signature_context_v3"}
    if policy_fingerprint == _terminal_footer_membership_v7_policy().split(":",1)[1]:
        return {"source_footer_placement_version":"terminal_body_flow_v1",
                "source_spacing_version":"baseline_metadata_heading_spacing_v1",
                "source_closing_group_version":"bounded_terminal_signature_context_v2"}
    if policy_fingerprint in {p.split(":",1)[1] for p in (_terminal_closing_group_policy(),_plain_list_columns_v6_policy())}:
        return {"source_footer_placement_version":"terminal_body_flow_v1",
                "source_spacing_version":"baseline_metadata_heading_spacing_v1",
                "source_closing_group_version":"bounded_terminal_signature_context_v1"}
    return ({"source_footer_placement_version":"terminal_body_flow_v1",
             "source_spacing_version":"baseline_metadata_heading_spacing_v1"}
        if policy_fingerprint == _terminal_source_layout_policy().split(":",1)[1] else {})


def _emphasis_normalization_version(policy_fingerprint):
    if policy_fingerprint in {p.split(":",1)[1] for p in (_adjacent_lrm_emphasis_v9_policy(), _protected_folio_bridges_v10_policy(), _bounded_page_reproposal_v11_policy(), _per_page_reproposal_v12_policy(), _in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy())}:
        return "ordinary_optional_emphasis_normalization_v3"
    if policy_fingerprint in {p.split(":",1)[1] for p in (_complete_lrm_emphasis_policy(),_terminal_source_layout_policy(),_terminal_closing_group_policy(),_plain_list_columns_v6_policy(),_terminal_footer_membership_v7_policy(),_in_body_terminal_closing_v8_policy())}:
        return "ordinary_optional_emphasis_normalization_v2"
    if policy_fingerprint in ({p.split(":",1)[1] for p in _metadata_normalization_policies()}
            | {_optional_hint_policy("ordinary_optional_layout_hint_normalization_v2",emphasis_normalization=True).split(":",1)[1]}):
        return "ordinary_optional_emphasis_normalization_v1"
    return None


def _verify_emphasis_version(record, version):
    key = "emphasis_normalization_version"
    expected = version in {"ordinary_optional_emphasis_normalization_v2", "ordinary_optional_emphasis_normalization_v3"}
    if (key in record) != expected or (expected and record[key] != version):
        fail("source_evidence_response_changed",409)


def _clock_direction_version(policy_fingerprint):
    """Only the exact old clock and fresh heading policies authorize clocks."""
    return "clock_h_colon_ltr_v1" if policy_fingerprint in {
        p.split(":", 1)[1] for p in (_clock_direction_policy(), _heading_columns_v4_policy(), _reference_footer_v5_policy(), _inline_folio_direction_policy(), _complete_lrm_emphasis_policy(), _terminal_source_layout_policy(),_terminal_closing_group_policy(),_plain_list_columns_v6_policy(),_terminal_footer_membership_v7_policy(),_in_body_terminal_closing_v8_policy(),_adjacent_lrm_emphasis_v9_policy(),_protected_folio_bridges_v10_policy(), _bounded_page_reproposal_v11_policy(), _per_page_reproposal_v12_policy(), _in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy())} else None


def _source_bound_v4_policy() -> str:
    """Exact former current recipe keeps V2 bands and numeric-run V3 evidence."""
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v4", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v2",
        source_folio_direction_version="numeric_run_ltr_v3")


def _source_bound_v3_policy() -> str:
    """Exact prior paid recipe, including its V2 band and direction behavior."""
    return _optional_hint_policy("ordinary_optional_layout_hint_normalization_v3",
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_source_bound_folio_v3", source_folio_proof=True,
        metadata_normalization_version="ordinary_metadata_band_normalization_v2")


def _metadata_normalization_policies() -> set[str]:
    """Exact old/new primary recipes share the same saved layout semantics."""
    return {_source_alignment_v20_policy(), _contact_folio_overlap_v19_policy(), _contact_folio_v18_policy(), _local_footer_closing_v17_policy(), _bounded_signature_label_v16_policy(), _terminal_punctuation_folio_v15_policy(), _labeled_folio_direction_v14_policy(), _in_flow_folio_bridges_v13_policy(), _per_page_reproposal_v12_policy(), _bounded_page_reproposal_v11_policy(), _protected_folio_bridges_v10_policy(), _adjacent_lrm_emphasis_v9_policy(), _in_body_terminal_closing_v8_policy(), _terminal_footer_membership_v7_policy(), _plain_list_columns_v6_policy(), _terminal_closing_group_policy(), _terminal_source_layout_policy(), _complete_lrm_emphasis_policy(), _inline_folio_direction_policy(), _reference_footer_v5_policy(), _heading_columns_v4_policy(), _clock_direction_policy(), _body_columns_v3_policy(), _source_bound_v4_policy(), _source_bound_v3_policy(), _optional_hint_policy(
        "ordinary_optional_layout_hint_normalization_v3", emphasis_normalization=True,
        metadata_normalization=True, primary_folio_version="terminal_labeled_folio_v2", source_folio_proof=True), _optional_hint_policy(
        "ordinary_optional_layout_hint_normalization_v3", emphasis_normalization=True,
        metadata_normalization=True, primary_folio_version="terminal_labeled_folio_v2"), _optional_hint_policy(
        "ordinary_optional_layout_hint_normalization_v2", emphasis_normalization=True,
        metadata_normalization=True), _optional_hint_policy(
        "ordinary_optional_layout_hint_normalization_v2", emphasis_normalization=True,
        metadata_normalization=True, primary_folio_version="terminal_labeled_folio_v2")}


def _source_normalization_version(policy_fingerprint):
    """Old paid operations must keep their original optional-hint recipe."""
    from .ordinary_layout_contracts import (OPTIONAL_HINT_NORMALIZATION_V1,
        OPTIONAL_HINT_NORMALIZATION_V2, OPTIONAL_HINT_NORMALIZATION_V3)
    current_recipe = _optional_hint_policy(OPTIONAL_HINT_NORMALIZATION_V3,
        emphasis_normalization=True, metadata_normalization=True,
        primary_folio_version="terminal_labeled_folio_v2")
    if policy_fingerprint in ({current_recipe.split(":", 1)[1]} | {p.split(":", 1)[1] for p in _source_folio_policies()}):
        return OPTIONAL_HINT_NORMALIZATION_V3
    if policy_fingerprint == _optional_hint_policy(OPTIONAL_HINT_NORMALIZATION_V1).split(":", 1)[1]:
        return OPTIONAL_HINT_NORMALIZATION_V1
    return OPTIONAL_HINT_NORMALIZATION_V2


def _source_folio_policies():
    return {_source_alignment_v20_policy(), _contact_folio_overlap_v19_policy(), _contact_folio_v18_policy(), _local_footer_closing_v17_policy(), _bounded_signature_label_v16_policy(), _terminal_punctuation_folio_v15_policy(), _labeled_folio_direction_v14_policy(), _in_flow_folio_bridges_v13_policy(), _per_page_reproposal_v12_policy(), _bounded_page_reproposal_v11_policy(), _protected_folio_bridges_v10_policy(), _adjacent_lrm_emphasis_v9_policy(), _in_body_terminal_closing_v8_policy(), _terminal_footer_membership_v7_policy(), _plain_list_columns_v6_policy(), _terminal_closing_group_policy(), _terminal_source_layout_policy(), _complete_lrm_emphasis_policy(), _inline_folio_direction_policy(), _reference_footer_v5_policy(), _heading_columns_v4_policy(), _clock_direction_policy(), _body_columns_v3_policy(), _source_bound_v4_policy(), _source_bound_v3_policy(), _optional_hint_policy(
        "ordinary_optional_layout_hint_normalization_v3", emphasis_normalization=True,
        metadata_normalization=True, primary_folio_version="terminal_labeled_folio_v2", source_folio_proof=True)}


def _band_normalization_version(policy_fingerprint):
    """Fresh flow repair is never silently applied to an older paid operation."""
    if policy_fingerprint in {p.split(":",1)[1] for p in (_in_body_terminal_closing_v8_policy(), _adjacent_lrm_emphasis_v9_policy(), _protected_folio_bridges_v10_policy(), _bounded_page_reproposal_v11_policy(), _per_page_reproposal_v12_policy(), _in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy())}:
        return "ordinary_metadata_band_normalization_v8"
    if policy_fingerprint == _terminal_footer_membership_v7_policy().split(":", 1)[1]:
        return "ordinary_metadata_band_normalization_v7"
    if policy_fingerprint == _plain_list_columns_v6_policy().split(":", 1)[1]:
        return "ordinary_metadata_band_normalization_v6"
    if policy_fingerprint in {p.split(":", 1)[1] for p in (_reference_footer_v5_policy(), _inline_folio_direction_policy(), _complete_lrm_emphasis_policy(), _terminal_source_layout_policy(),_terminal_closing_group_policy())}:
        return "ordinary_metadata_band_normalization_v5"
    if policy_fingerprint == _heading_columns_v4_policy().split(":", 1)[1]:
        return "ordinary_metadata_band_normalization_v4"
    if policy_fingerprint in {p.split(":", 1)[1] for p in (_clock_direction_policy(), _body_columns_v3_policy())}:
        return "ordinary_metadata_band_normalization_v3"
    if policy_fingerprint in {p.split(":", 1)[1] for p in
                             (_source_bound_v4_policy(), _source_bound_v3_policy())}:
        return "ordinary_metadata_band_normalization_v2"
    if policy_fingerprint in {p.split(":", 1)[1] for p in _metadata_normalization_policies()}:
        return "ordinary_metadata_band_normalization_v1"
    return None


def valid_automatic_layout_policy(value: str) -> bool:
    return type(value) is str and _POLICY_RE.fullmatch(value) is not None


def _nonce(kind: str, payload: dict) -> str:
    return hashlib.sha256(kind.encode("ascii") + b":" + encode(payload)).hexdigest()[:32]


def _durable_folder(identity: dict) -> Path:
    run_dir = Path(identity["run_dir"]).expanduser().resolve()
    return storage._mkdir(run_dir / "ordinary_auto_layout")


def _recovery_folder(root: Path) -> Path:
    """One explicit successor for this checkpoint, independent of job IDs."""
    return storage._mkdir(root / "recoveries" / "layout_capacity_v2")


def _direct_revalidation(root: Path, result: dict, policy: dict) -> bool:
    """Choose the durable lineage before admitting a fresh direct successor."""
    capacity = root / "recoveries" / "layout_capacity_v2"
    direct = root / "recoveries" / "layout_direct_revalidation_v1"
    markers = ("intent.json", "operation.json", "candidate.json")
    has_capacity = any((capacity / name).exists() for name in markers)
    has_direct = any((direct / name).exists() for name in markers)
    if has_capacity and has_direct:
        fail("automatic_recovery_predecessor_changed", 409)
    return has_direct or (not has_capacity
        and result.get("error_code") in {"ordinary_layout_page_break_requires_flow",
                                       "ordinary_layout_proposal_coverage",
                                       "ordinary_layout_invalid_proposal_decisions",
                                       "ordinary_layout_invalid_source_layout_evidence",
                                       "ordinary_layout_invalid_source_footer_evidence"}
        and policy.get("max_output_tokens") == 32000
        and policy.get("timeout_seconds") == 480.0)


def _failed_predecessor(manager, root: Path, identity: dict, old_policy: str, *, expected_identity=None, completed_marker=None) -> dict:
    """Prove the old dispatch is final and billed before a new paid operation."""
    if not valid_automatic_layout_policy(old_policy):
        fail("automatic_recovery_predecessor_invalid", 409)
    intent_path, pointer_path = root / "intent.json", root / "operation.json"
    if not intent_path.is_file() or not pointer_path.is_file() or (root / "candidate.json").exists():
        fail("automatic_recovery_predecessor_unavailable", 409)
    old_intent = _read_record(intent_path)
    expected = expected_identity or dict(identity, policy_fingerprint=old_policy.split(":", 1)[1])
    if old_intent != expected:
        fail("automatic_recovery_predecessor_changed", 409)
    pointer = _read_record(pointer_path)
    if (pointer.get("identity_sha256") != hashlib.sha256(encode(old_intent)).hexdigest()
            or pointer.get("selected_pages") != identity["selected_pages"]):
        fail("automatic_recovery_predecessor_changed", 409)
    from .ordinary_layout_contracts import identifier, nonce
    from .ordinary_layout_service import _read as verified_record
    origin = identifier(pointer.get("origin_job_id"))
    baseline_id = nonce(pointer.get("baseline_id"))
    operation_nonce = nonce(pointer.get("operation_nonce"))
    origin_folder = manager.service.root / origin
    operation = origin_folder / "baselines" / baseline_id / "suggestions" / operation_nonce
    result_path, summary_path = operation / "result.json", operation / "accounting_summary.json"
    completed_marker = completed_marker or root / "recoveries" / "layout_direct_revalidation_v1" / "candidate.json"
    if not completed_marker.is_file():
        completed_marker = root / "recoveries" / "layout_revalidation_v1" / "candidate.json"
    if not completed_marker.is_file():
        completed_marker = root / "recoveries" / "layout_capacity_v2" / "candidate.json"
    completed = _read_record(completed_marker) if completed_marker.is_file() else None
    if not result_path.is_file() or not summary_path.is_file():
        fail("automatic_recovery_predecessor_unsettled", 409)
    with manager.service.scope(origin) as scoped:
        selections = manager.service._selections(scoped)
        if completed is None and ((scoped / "automatic.json").exists()
                or (scoped / "frozen.json").exists() or selections):
            fail("automatic_recovery_predecessor_selected", 409)
        if completed is not None and ((scoped / "automatic.json").exists()
                or (scoped / "frozen.json").exists() or selections):
            if (completed.get("origin_job_id") != origin
                    or not (scoped / "automatic.json").exists()):
                fail("automatic_recovery_predecessor_selected", 409)
            automatic = verified_record(scoped / "automatic.json")
            if automatic.get("candidate_id") != completed.get("candidate_id"):
                fail("automatic_recovery_predecessor_selected", 409)
    operation_intent = verified_record(operation / "intent.json")
    result, summary = verified_record(result_path), verified_record(summary_path)
    from .ordinary_layout_contracts import decode
    from .usage_accounting import _state_fingerprint, _summarize
    journal_path = operation / "accounting" / "dispatch_accounting.json"
    journal = decode(storage._read(journal_path, 8 * 1024 * 1024))
    if (type(journal) is not dict or journal.get("fingerprint") != _state_fingerprint(journal)
            or journal.get("run_identity", {}).get("job_id") != origin
            or journal.get("run_identity", {}).get("operation_nonce") != operation_nonce
            or journal.get("run_identity", {}).get("binding", {}).get("source_sha256") != identity["source_pdf_sha256"]
            or journal.get("run_identity", {}).get("binding", {}).get("original_sha256") != identity["raw_docx_sha256"]
            or not isinstance(journal.get("events"), list)
            or _summarize(journal["events"], historical_incomplete=journal.get("historical_incomplete", False),
                pricing_snapshot=journal.get("pricing_snapshot")) != summary):
        fail("automatic_recovery_predecessor_unsettled", 409)
    binding = operation_intent.get("identity", {}).get("binding", {})
    if (operation_intent.get("operation_nonce") != operation_nonce
            or operation_intent.get("baseline_id") != baseline_id
            or operation_intent.get("review_id") != pointer.get("review_id")
            or operation_intent.get("request", {}).get("expected_generation") != pointer.get("initial_generation")
            or operation_intent.get("request", {}).get("page_numbers") != identity["selected_pages"]
            or operation_intent.get("identity", {}).get("run_id") != identity["run_id"]
            or operation_intent.get("identity", {}).get("mode") != identity["runtime_mode"]
            or operation_intent.get("identity", {}).get("workspace_id") != identity["workspace_id"]
            or binding.get("source_sha256") != identity["source_pdf_sha256"]
            or binding.get("original_sha256") != identity["raw_docx_sha256"]
            or (operation_intent.get("request", {}).get("policy", {}).get("max_output_tokens"),
                operation_intent.get("request", {}).get("policy", {}).get("timeout_seconds"))
                not in {(8000, 240.0), (32000, 480.0)}):
        fail("automatic_recovery_predecessor_changed", 409)
    if (result.get("status") != "failed" or result.get("applied_unreviewed")
            or result.get("retry_dispatch_allowed") is not False
            or result.get("accounting", {}).get("cost_usd") != summary.get("cost_usd")
            or result.get("accounting", {}).get("known_cost_usd") != summary.get("known_cost_usd")
            or summary.get("coverage_status") != "complete"
            or summary.get("cost_usd") is None or summary.get("unknown_cost_count") != 0
            or summary.get("in_flight_count") != 0
            or type(summary.get("provider_dispatch_count")) is not int
            or summary["provider_dispatch_count"] < 1):
        fail("automatic_recovery_predecessor_unsettled", 409)
    try:
        cost = Decimal(str(summary["cost_usd"]))
        if not cost.is_finite() or cost < 0 or cost != Decimal(str(summary["known_cost_usd"])):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        fail("automatic_recovery_predecessor_unsettled", 409)
    return {"intent_sha256": hashlib.sha256(storage._read(intent_path, 8 * 1024 * 1024)).hexdigest(),
        "pointer_sha256": hashlib.sha256(storage._read(pointer_path, 8 * 1024 * 1024)).hexdigest(),
        "result_sha256": hashlib.sha256(storage._read(result_path, 8 * 1024 * 1024)).hexdigest(),
        "accounting_summary_sha256": hashlib.sha256(storage._read(summary_path, 8 * 1024 * 1024)).hexdigest(),
        "accounting_journal_sha256": hashlib.sha256(storage._read(journal_path, 8 * 1024 * 1024)).hexdigest(),
        "known_cost_usd": str(cost), "origin_job_id": origin,
        "baseline_id": baseline_id, "operation_nonce": operation_nonce}


def _retained_continuation(manager, root: Path, identity: dict, predecessor: dict, *, direct=False,
                           parent_direct=False, inherited=None):
    """Admit a settled normalization failure; never reuse a partial SDK response."""
    prior_root = root if direct else root / "recoveries" / ("layout_direct_revalidation_v1" if parent_direct else "layout_capacity_v2")
    prior_identity = _read_record(prior_root / "intent.json")
    expected = dict(identity, policy_fingerprint=prior_identity.get("policy_fingerprint"))
    if not direct:
        expected["recovery_predecessor"] = predecessor
    if parent_direct:
        expected["retained_pages"] = {str(p): r["origin"] for p, r in inherited.items()}
    if prior_identity != expected:
        fail("automatic_recovery_predecessor_changed", 409)
    prior = _failed_predecessor(manager, prior_root, identity,
        ORDINARY_AUTO_LAYOUT_POLICY + ":" + prior_identity["policy_fingerprint"],
        expected_identity=expected,
        completed_marker=root / "recoveries" / ("layout_direct_revalidation_v1" if direct else "layout_revalidation_v1") / "candidate.json")
    if direct and prior != predecessor:
        fail("automatic_recovery_predecessor_changed", 409)
    from .ordinary_layout_service import _read as verified_record
    from .ordinary_layout_contracts import decode, normalize_proposals
    from .saved_docx_layout import inspect_docx
    operation = manager.service.root / prior["origin_job_id"] / "baselines" / prior["baseline_id"] / "suggestions" / prior["operation_nonce"]
    result = verified_record(operation / "result.json")
    policy = verified_record(operation / "intent.json")["request"]["policy"]
    if "proposal_repair_policy" in policy:
        fail("automatic_recovery_unsupported_policy", 409)
    allowed_errors = {"ordinary_layout_proposal_coverage", "ordinary_layout_invalid_proposal_decisions"} if parent_direct else {"ordinary_layout_page_break_requires_flow"}
    if direct:
        allowed_errors.add("ordinary_layout_proposal_coverage")
        allowed_errors.add("ordinary_layout_invalid_proposal_decisions")
        allowed_errors.add("ordinary_layout_invalid_source_layout_evidence")
        allowed_errors.add("ordinary_layout_invalid_source_footer_evidence")
    if (result.get("error_code") not in allowed_errors or policy.get("max_output_tokens") != 32000
            or direct and policy.get("timeout_seconds") != 480.0):
        fail("automatic_retained_response_unavailable", 409)
    journal = _read_record(operation / "accounting" / "dispatch_accounting.json")
    begins = [e for e in journal["events"] if e.get("event") == "begin"]
    finishes = [e for e in journal["events"] if e.get("event") == "finish"]
    if (not begins or len(begins) != len(finishes)
            or len({e.get("page_number") for e in begins}) != len(begins)):
        fail("automatic_retained_response_unsettled", 409)
    view = manager.service.state(prior["origin_job_id"])["review"]
    # The origin may have retired after Resume. Read its immutable reviewed
    # baseline, whose source/raw ownership was verified above.
    reviewed = storage._read(operation.parent.parent / "reviewed.docx", storage.DOCX_MAX_BYTES)
    snapshot = inspect_docx(reviewed, identity["target_lang"])
    retained = dict(inherited or {})
    if parent_direct:
        # Inherited pages are not new journal calls. Prove their exact copied
        # bytes and origin markers against the independently revalidated parent.
        for page, record in retained.items():
            if (storage._read(operation / f"page-{page:04d}.response.json", 2 * 1024 * 1024) != record["raw"]
                    or verified_record(operation / f"page-{page:04d}.retained.json") != record["origin"]):
                fail("automatic_retained_response_changed", 409)
    for begin in begins:
        page = begin.get("page_number")
        finish = next((e for e in finishes if e.get("call_id") == begin.get("call_id")), None)
        if (page in retained or page not in identity["selected_pages"] or begin.get("purpose") != "layout_suggestion"
                or begin.get("attempt") != 1 or begin.get("bounds", {}).get("max_output_tokens") != 32000
                or not finish or finish.get("outcome") != "succeeded"
                or finish.get("cost_status") != "available" or finish.get("cost_usd") is None
                or not finish.get("response_id") or finish.get("error_code") is not None):
            fail("automatic_retained_response_unsettled", 409)
        raw = storage._read(operation / f"page-{page:04d}.response.json", 2 * 1024 * 1024)
        proposal = decode(raw)
        if type(proposal) is not dict or proposal.get("page_number") != page:
            fail("automatic_retained_response_invalid", 409)
        # This is an explicit new successor, not replay of the predecessor's
        # failed result. Its own saved policy chooses the revalidation recipe.
        normalize_proposals(snapshot, view, [proposal],
                            band_normalization_version=_band_normalization_version(identity["policy_fingerprint"]),
                            **({"emphasis_normalization_version":_emphasis_normalization_version(identity["policy_fingerprint"])}
                                if _emphasis_normalization_version(identity["policy_fingerprint"]) in {"ordinary_optional_emphasis_normalization_v2", "ordinary_optional_emphasis_normalization_v3"} else {}))
        retained[page] = {"raw": raw, "origin": {"version": "ordinary_retained_proposal_v1",
            "source_page_number": page, "response_sha256": hashlib.sha256(raw).hexdigest(),
            "predecessor": prior, "original_policy_fingerprint": prior_identity["policy_fingerprint"],
            "provider_call_id": begin["call_id"], "locally_revalidated": True}}
    # Missing means genuinely never sent, not a lost or unusable response.
    if any((operation / f"page-{p:04d}.response.json").exists() for p in identity["selected_pages"] if p not in retained):
        fail("automatic_retained_response_changed", 409)
    return prior, retained


def _read_record(path: Path) -> dict:
    from .ordinary_layout_contracts import decode
    value = decode(storage._read(path, 8 * 1024 * 1024))
    if type(value) is not dict:
        fail("automatic_record_changed", 409)
    return value


def _operation_costs(manager, origin: str, identity: dict) -> dict:
    costs = manager.layout_costs(origin)
    if not costs["complete"]:
        fail("accounting_unsettled", 409)
    if "rebuild_predecessor" in identity:
        prior = identity["rebuild_predecessor"]["layout_costs"]
        if not prior["complete"] or Decimal(costs["known_cost_usd"]) != 0:
            fail("automatic_rebuild_accounting_unsettled", 409)
        return {"cost_usd": prior["cost_usd"], "known_cost_usd": prior["known_cost_usd"],
            "complete": True, "operations": prior["operations"] + costs["operations"]}
    predecessors = [identity[k] for k in ("recovery_predecessor", "revalidation_predecessor") if k in identity]
    inherited = [p for p in predecessors if p["origin_job_id"] != origin]
    if inherited:
        prior = sum((Decimal(p["known_cost_usd"]) for p in inherited), Decimal(0))
        new = Decimal(costs["known_cost_usd"])
        costs = {"cost_usd": str(prior + new), "known_cost_usd": str(prior + new),
            "complete": True, "operations": costs["operations"] + len(inherited),
            "predecessor_cost_usd": str(prior), "recovery_cost_usd": str(new)}
    return costs


def _source_layout_review(candidate) -> dict:
    """Expose rejected optional hints from the independently verified map."""
    from .ordinary_layout_contracts import source_evidence_review_fields
    return source_evidence_review_fields(candidate.source_map.get("source_evidence", {}).get("pages", []))


def _reused_candidate(manager, folder: Path, identity: dict, record: dict, job) -> dict:
    if identity.get("retained_pages"):
        pointer = _read_record(folder / "operation.json")
        if pointer.get("retained_pages") != identity["retained_pages"] or pointer.get("identity_sha256") != hashlib.sha256(encode(identity)).hexdigest():
            fail("automatic_retained_response_changed", 409)
        operation = manager.service.root / pointer["origin_job_id"] / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
        _verified_retained_pages(operation, identity["retained_pages"])
    if (record.get("identity") != identity or type(record.get("review_id")) is not str
            or type(record.get("candidate_id")) is not str
            or type(record.get("origin_job_id")) is not str):
        fail("automatic_candidate_changed", 409)
    if record.get("layout_costs") != _operation_costs(manager, record["origin_job_id"], identity):
        fail("automatic_candidate_changed", 409)
    candidate = manager.service.saved.verified_unreviewed_candidate(
        record["review_id"], record["candidate_id"])
    if (candidate.docx_sha256 != record.get("sha256")
            or candidate.source_map_sha256 != record.get("source_map_sha256")
            or hashlib.sha256(encode(candidate.receipt)).hexdigest() != record.get("receipt_sha256")
            or candidate.generation != record.get("generation")
            or candidate.current_generation != candidate.generation
            or candidate.source_pdf_sha256 != identity["source_pdf_sha256"]
            or candidate.raw_docx_sha256 != identity["raw_docx_sha256"]
            or candidate.raw_source_map_sha256 != identity["raw_source_map_sha256"]
            or list(candidate.selected_pages) != identity["selected_pages"]
            or candidate.policy_fingerprint != identity["policy_fingerprint"]
            or candidate.receipt.get("document_reviewed") is not False):
        fail("automatic_candidate_changed", 409)
    copy_path = folder / "output.docx"
    path = manager.service.root / record["origin_job_id"] / "automatic" / "output.docx"
    if (storage._read(copy_path, storage.DOCX_MAX_BYTES) != candidate.docx_bytes
            or storage._read(path, storage.DOCX_MAX_BYTES) != candidate.docx_bytes):
        fail("automatic_candidate_changed", 409)
    if job.job_id != record["origin_job_id"]:
        manager.service.adopt_automatic_alias(job, record["origin_job_id"], record["candidate_id"])
    from .joblog_flow import count_words_from_docx
    count = count_words_from_docx(path)
    return {"output_path": str(path),
        "review_copy_path": str(manager.service.automatic_review_copy(job.job_id)),
        "sha256": candidate.docx_sha256,
        "word_count": count, "candidate_id": candidate.candidate_id,
        "source_map_sha256": candidate.source_map_sha256,
        "policy_fingerprint": candidate.policy_fingerprint,
        "delivery_kind": "automatic_unreviewed", "reviewed": False,
        "reused_durable_candidate": True, "layout_costs": record["layout_costs"],
        **_source_layout_review(candidate),
        **({"recovery_predecessor": identity["recovery_predecessor"]}
           if "recovery_predecessor" in identity else {}),
        **({"revalidation_predecessor": identity["revalidation_predecessor"]}
           if "revalidation_predecessor" in identity else {})}


def _verified_retained_pages(operation: Path, expected: dict) -> None:
    from .ordinary_layout_service import _read
    policy = _read(operation / "intent.json").get("request", {}).get("policy", {})
    if "proposal_repair_policy" in policy:
        if expected:
            fail("automatic_recovery_unsupported_policy", 409)
        manifest = decode(storage._read(operation / "attempts/manifest.json", 8 * 1024 * 1024))
        _verified_reproposal_operation(operation, manifest.get("identity", {}).get("policy_fingerprint"))
    """Copied responses remain bound to their immutable prior operation."""
    from .ordinary_layout_service import _read as verified_record
    names = {f"page-{int(p):04d}.retained.json" for p in expected}
    if {p.name for p in operation.glob("*.retained.json")} != names:
        fail("automatic_retained_response_changed", 409)
    for page, origin in expected.items():
        if _proposal_repair_version(origin.get("original_policy_fingerprint")) is not None:
            fail("automatic_recovery_unsupported_policy", 409)
        if (verified_record(operation / f"page-{int(page):04d}.retained.json") != origin
                or hashlib.sha256(storage._read(operation / f"page-{int(page):04d}.response.json", 2 * 1024 * 1024)).hexdigest() != origin["response_sha256"]):
            fail("automatic_retained_response_changed", 409)


def _verified_reproposal_operation(operation, policy_fingerprint, *, restore=False):
    """Shared acceptance seam for new native attempts; historical bytes stay exact."""
    from .ordinary_layout_service import _read
    from .ordinary_layout_reproposal import KEY, operation_witness
    intent = _read(operation / "intent.json")
    policy = intent.get("request", {}).get("policy", {})
    required = _proposal_repair_version(policy_fingerprint)
    if required is None:
        if KEY in policy:
            fail("proposal_repair_policy_changed", 409)
        return None
    if policy.get(KEY) != required:
        fail("proposal_repair_ledger_missing", 409)
    initial = _read(operation / "proposal_initial_view.json")
    manifest = decode(storage._read(operation / "attempts/manifest.json", 8 * 1024 * 1024))
    if manifest.get("policy") != policy or manifest.get("initial_view") != initial.get("view"):
        fail("proposal_repair_context_changed", 409)
    identity = {**intent["identity"], "operation_nonce": intent["operation_nonce"],
        "baseline_id": intent["baseline_id"], "initial_generation": intent["request"]["expected_generation"],
        "policy_fingerprint": policy_fingerprint, "page_groups": manifest.get("identity", {}).get("page_groups")}
    from .saved_docx_layout import inspect_docx
    raw = storage._read(operation.parent.parent / "reviewed.docx", storage.DOCX_MAX_BYTES)
    source = storage._read(operation.parent.parent / "source.pdf", storage.PDF_MAX_BYTES)
    if (hashlib.sha256(raw).hexdigest() != identity.get("reviewed_sha256")
            or hashlib.sha256(source).hexdigest() != identity.get("source_sha256")):
        fail("proposal_repair_context_changed", 409)
    witness, proposals, summary = operation_witness(operation, snapshot=inspect_docx(raw, identity["target_lang"]),
        frames=initial["view"]["pages"], source_pdf=source, page_groups=dict(identity["page_groups"]),
        selected_pages=intent["request"]["page_numbers"], expected_identity=identity,
        restore_aliases=restore, seal=restore)
    if _read(operation / "accounting_summary.json") != summary:
        fail("proposal_repair_accounting_changed", 409)
    if (operation / "result.json").exists() and _read(operation / "result.json").get("proposal_repair_ledger_sha256") != hashlib.sha256(encode(witness)).hexdigest():
        fail("proposal_repair_ledger_changed", 409)
    return witness, proposals, summary


def _proposal_evidence(manager, job_id: str, baseline_id: str, review_id: str, operation_nonce: str,
                       selected_pages: tuple[int, ...], policy: str, *, retained_pages=None) -> dict:
    """Bind private selected proofs; V11 includes bounded untrusted attempt data."""
    from .saved_docx_layout_service import _read as bounded_read
    from .ordinary_layout_contracts import decode
    image_hashes = {page: hashlib.sha256(manager.service.saved.image(review_id, page)).hexdigest()
                    for page in selected_pages}
    pages, response_versions, source_evidence = [], set(), []
    with manager.service.scope(job_id) as folder:
        operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
        _verified_retained_pages(operation, retained_pages or {})
        intent = bounded_read(operation / "intent.json", 8 * 1024 * 1024)
        summary = bounded_read(operation / "accounting_summary.json", 8 * 1024 * 1024)
        from .ordinary_layout_service import _read as verified_record
        request_intent = verified_record(operation / "intent.json")
        request_policy = request_intent["request"]["policy"]
        repair_proof = _verified_reproposal_operation(operation, policy.split(":", 1)[1])
        emphasis_version = _emphasis_normalization_version(policy.split(":",1)[1])
        _verify_emphasis_version(request_policy,emphasis_version)
        band_version = _band_normalization_version(policy.split(":", 1)[1])
        if (band_version in {"ordinary_metadata_band_normalization_v2", "ordinary_metadata_band_normalization_v3", "ordinary_metadata_band_normalization_v4", "ordinary_metadata_band_normalization_v5", "ordinary_metadata_band_normalization_v6", "ordinary_metadata_band_normalization_v7", "ordinary_metadata_band_normalization_v8"}
                and request_policy.get("band_normalization_version") != band_version):
            fail("source_evidence_response_changed", 409)
        if (band_version in {"ordinary_metadata_band_normalization_v3", "ordinary_metadata_band_normalization_v4", "ordinary_metadata_band_normalization_v5", "ordinary_metadata_band_normalization_v6", "ordinary_metadata_band_normalization_v7", "ordinary_metadata_band_normalization_v8"}
                and not (operation / "proposal_initial_view.json").exists()):
            fail("source_evidence_initial_view_missing", 409)
        if band_version in {"ordinary_metadata_band_normalization_v3", "ordinary_metadata_band_normalization_v4", "ordinary_metadata_band_normalization_v5", "ordinary_metadata_band_normalization_v6", "ordinary_metadata_band_normalization_v7", "ordinary_metadata_band_normalization_v8"}:
            initial_record = verified_record(operation / "proposal_initial_view.json")
            _verify_emphasis_version(initial_record,emphasis_version)
            if (initial_record.get("band_normalization_version") != band_version
                    or initial_record.get("review_id") != review_id
                    or initial_record.get("generation") != request_intent["request"]["expected_generation"]):
                fail("source_evidence_initial_view_changed", 409)
        for page in selected_pages:
            response = bounded_read(operation / f"page-{page:04d}.response.json", 2 * 1024 * 1024)
            row = {"source_page_number": page,
                "source_image_sha256": image_hashes[page],
                "response_sha256": hashlib.sha256(response).hexdigest()}
            retained_path = operation / f"page-{page:04d}.retained.json"
            if retained_path.exists():
                row["retained_origin"] = verified_record(retained_path)
            proposal = decode(response)
            response_version = proposal.get("version")
            if response_version == "ordinary_layout_proposal_v3":
                # The hash-bound sidecar was validated against the immutable initial
                # generation, before uncertain proposed regions were applied.
                sidecar = verified_record(operation / "source_evidence.json")
                recorded_result = verified_record(operation / "result.json")
                if hashlib.sha256(encode(sidecar["pages"])).hexdigest() != recorded_result.get("source_layout_evidence_sha256"):
                    fail("source_evidence_response_changed", 409)
                records = [item for item in sidecar["pages"] if item.get("page_number") == page]
                if len(records) != 1 or records[0].get("response_sha256") != row["response_sha256"]:
                    fail("source_evidence_response_changed", 409)
                if (operation / "proposal_initial_view.json").exists():
                    from .ordinary_layout_contracts import proposal_source_evidence
                    from .saved_docx_layout import inspect_docx
                    initial_view = verified_record(operation / "proposal_initial_view.json")["view"]
                    _verify_emphasis_version(verified_record(operation / "proposal_initial_view.json"),emphasis_version)
                    if (band_version in {"ordinary_metadata_band_normalization_v2", "ordinary_metadata_band_normalization_v3", "ordinary_metadata_band_normalization_v4", "ordinary_metadata_band_normalization_v5", "ordinary_metadata_band_normalization_v6", "ordinary_metadata_band_normalization_v7", "ordinary_metadata_band_normalization_v8"}
                            and verified_record(operation / "proposal_initial_view.json").get("band_normalization_version") != band_version):
                        fail("source_evidence_response_changed", 409)
                    baseline_bytes = bounded_read(operation.parent.parent / "reviewed.docx", storage.DOCX_MAX_BYTES)
                    from .ordinary_layout_contracts import OPTIONAL_HINT_NORMALIZATION_V3
                    if (records[0].get("normalization", {}).get("version") == OPTIONAL_HINT_NORMALIZATION_V3
                            and _source_normalization_version(policy.split(":", 1)[1]) != OPTIONAL_HINT_NORMALIZATION_V3):
                        fail("source_evidence_response_changed", 409)
                    expected = proposal_source_evidence(inspect_docx(baseline_bytes, initial_view["target_lang"]), initial_view, proposal,
                        normalization_version=records[0].get("normalization", {}).get("version", _source_normalization_version(policy.split(":", 1)[1])),
                        band_normalization_version=_band_normalization_version(policy.split(":", 1)[1]),
                        emphasis_normalization_version=emphasis_version)
                    expected["response_sha256"] = row["response_sha256"]
                    if records[0] != expected:
                        fail("source_evidence_response_changed", 409)
                source_evidence.append(records[0])
            if response_version != "ordinary_layout_proposal_v1":
                row["proposal_schema_version"] = response_version
            response_versions.add(response_version)
            pages.append(row)
    schema_version = next(iter(response_versions)) if len(response_versions) == 1 else "mixed_retained_proposals"
    return {"version": "ordinary_auto_layout_evidence_v1", "document_reviewed": False,
        "rendered_layout_acceptance": "not_evaluated", "policy_fingerprint": policy.split(":", 1)[1],
        "operation_nonce": operation_nonce, "intent_sha256": hashlib.sha256(intent).hexdigest(),
        "accounting_summary_sha256": hashlib.sha256(summary).hexdigest(),
        "requested_model": request_policy["model"], "effort": request_policy["effort"],
        "proposal_schema_version": schema_version, "pages": pages,
        **({"proposal_repair_evidence": repair_proof[0]} if repair_proof is not None else {}),
        **({"local_source_folio_proof_version": "ordinary_source_folio_span_proof_v1"}
            if policy in _source_folio_policies() else {}),
        **({"source_folio_direction_version": _source_folio_direction_version(policy.split(":",1)[1])}
            if source_evidence and _source_folio_direction_version(policy.split(":",1)[1]) is not None else {}),
        **({"clock_direction_version": "clock_h_colon_ltr_v1"}
            if source_evidence and _clock_direction_version(policy.split(":", 1)[1]) is not None else {}),
        **({"source_folio_inline_direction_version": inline_mode}
            if source_evidence and (inline_mode := _source_folio_inline_direction_version(policy.split(":", 1)[1])) is not None else {}),
        **(_terminal_source_layout_versions(policy.split(":",1)[1]) if source_evidence else {}),
        **({"source_evidence": {"version": "ordinary_source_evidence_v1", "pages": source_evidence}} if source_evidence else {})}


def _recover_settled_result(manager, pointer: dict, selected_pages: list[int], *, policy_fingerprint=None) -> None:
    """Complete a saved, fully accounted operation locally after a crash."""
    from .ordinary_layout_contracts import decode, normalize_proposals, OrdinaryLayoutError
    from .ordinary_layout_service import _read as verified_record, _write as verified_write
    from .saved_docx_layout import inspect_docx
    origin, baseline_id = pointer["origin_job_id"], pointer["baseline_id"]
    operation_nonce, initial = pointer["operation_nonce"], pointer["initial_generation"]
    with manager.service.scope(origin) as folder:
        operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
        if (operation / "result.json").exists():
            return
        if (operation / "cancel.json").exists() or not (operation / "accounting_summary.json").exists():
            return
        intent = verified_record(operation / "intent.json")
        emphasis_version = _emphasis_normalization_version(policy_fingerprint)
        _verify_emphasis_version(intent.get("request",{}).get("policy",{}),emphasis_version)
        band_version = _band_normalization_version(policy_fingerprint)
        if (band_version in {"ordinary_metadata_band_normalization_v2", "ordinary_metadata_band_normalization_v3", "ordinary_metadata_band_normalization_v4", "ordinary_metadata_band_normalization_v5", "ordinary_metadata_band_normalization_v6", "ordinary_metadata_band_normalization_v7", "ordinary_metadata_band_normalization_v8"}
                and intent.get("request", {}).get("policy", {}).get("band_normalization_version") != band_version):
            fail("source_evidence_response_changed", 409)
        if band_version in {"ordinary_metadata_band_normalization_v3", "ordinary_metadata_band_normalization_v4", "ordinary_metadata_band_normalization_v5", "ordinary_metadata_band_normalization_v6", "ordinary_metadata_band_normalization_v7", "ordinary_metadata_band_normalization_v8"}:
            initial_path = operation / "proposal_initial_view.json"
            if not initial_path.exists():
                fail("source_evidence_initial_view_missing", 409)
            initial_record = verified_record(initial_path)
            _verify_emphasis_version(initial_record,emphasis_version)
            if (initial_record.get("band_normalization_version") != band_version
                    or initial_record.get("review_id") != pointer["review_id"]
                    or initial_record.get("generation") != initial):
                fail("source_evidence_initial_view_changed", 409)
        summary = verified_record(operation / "accounting_summary.json")
        repair_proof = _verified_reproposal_operation(operation, policy_fingerprint, restore=True)
        _verified_retained_pages(operation, pointer.get("retained_pages", {}))
        if (intent.get("baseline_id") != baseline_id or intent.get("review_id") != pointer["review_id"]
                or intent.get("operation_nonce") != operation_nonce
                or intent.get("request", {}).get("expected_generation") != initial
                or intent.get("request", {}).get("page_numbers") != selected_pages
                or summary.get("coverage_status") != "complete"
                or summary.get("cost_usd") is None
                or summary.get("unknown_cost_count") != 0
                or summary.get("in_flight_count") != 0
                or summary.get("provider_dispatch_count") != (len(repair_proof[0]["journal"]["events"]) // 2
                    if repair_proof is not None else len(selected_pages) - len(pointer.get("retained_pages", {})))
                or summary.get("attempt_count") != summary.get("provider_dispatch_count")):
            return
        proposals = []
        for page in selected_pages:
            path = operation / f"page-{page:04d}.response.json"
            if not path.exists():
                return
            raw = storage._read(path, 2 * 1024 * 1024)
            try:
                proposal = decode(raw)
            except ValueError:
                return
            if type(proposal) is not dict or proposal.get("page_number") != page:
                return
            proposals.append(proposal)
        reviewed = storage._read(folder / "baselines" / baseline_id / "reviewed.docx", storage.DOCX_MAX_BYTES)
        stored_decisions = (verified_record(operation / "proposed_decisions.json")
            if (operation / "proposed_decisions.json").exists() else None)
    current = manager.service.state(origin)
    if (current["baseline_id"] != baseline_id or current["review"]["review_id"] != pointer["review_id"]
            or current["generation"] not in {initial, initial + 1}):
        fail("automatic_generation_changed", 409)
    source_result_fields = {}
    with manager.service.scope(origin) as folder:
        sidecar_path = folder / "baselines" / baseline_id / "suggestions" / operation_nonce / "source_evidence.json"
        if sidecar_path.exists():
            records = verified_record(sidecar_path)["pages"]
            source_result_fields = {"source_coverage_findings": [f for page in records for f in page["findings"]],
                "source_layout_evidence_sha256": hashlib.sha256(encode(records)).hexdigest()}
    evidence_view = current["review"]
    normalization_version = _source_normalization_version(policy_fingerprint)
    if any(p.get("version") == "ordinary_layout_proposal_v3" for p in proposals):
        with manager.service.scope(origin) as folder:
            operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
            initial_path = operation / "proposal_initial_view.json"
            if not initial_path.exists():
                fail("source_evidence_initial_view_missing", 409)
            initial_record = verified_record(initial_path)
            _verify_emphasis_version(initial_record,emphasis_version)
            if initial_record.get("review_id") != pointer["review_id"] or initial_record.get("generation") != initial:
                fail("source_evidence_initial_view_changed", 409)
            if (band_version in {"ordinary_metadata_band_normalization_v2", "ordinary_metadata_band_normalization_v3", "ordinary_metadata_band_normalization_v4", "ordinary_metadata_band_normalization_v5", "ordinary_metadata_band_normalization_v6", "ordinary_metadata_band_normalization_v7", "ordinary_metadata_band_normalization_v8"}
                    and initial_record.get("band_normalization_version") != band_version):
                fail("source_evidence_initial_view_changed", 409)
            evidence_view = initial_record["view"]
            from .ordinary_layout_contracts import proposal_source_evidence
            source_records = [proposal_source_evidence(inspect_docx(reviewed, evidence_view["target_lang"]), evidence_view, p,
                normalization_version=normalization_version, band_normalization_version=_band_normalization_version(policy_fingerprint), emphasis_normalization_version=emphasis_version) for p in proposals]
            for record, proposal in zip(source_records, proposals):
                record["response_sha256"] = hashlib.sha256(storage._read(operation / f"page-{proposal['page_number']:04d}.response.json", 2 * 1024 * 1024)).hexdigest()
            expected_sidecar = {"version": "ordinary_source_evidence_v1", "pages": source_records}
            if (any(page.get("normalization", {}).get("review_required") for page in source_records)
                    and not (policy_fingerprint in {p.split(":", 1)[1] for p in _metadata_normalization_policies()}
                        or (policy_fingerprint == _optional_hint_policy("ordinary_optional_layout_hint_normalization_v1").split(":", 1)[1]
                            and all(page.get("normalization", {}).get("version") != "ordinary_optional_layout_hint_normalization_v2" for page in source_records))
                        or policy_fingerprint == _optional_hint_policy("ordinary_optional_layout_hint_normalization_v2").split(":", 1)[1]
                        or policy_fingerprint == _optional_hint_policy("ordinary_optional_layout_hint_normalization_v2", emphasis_normalization=True).split(":", 1)[1])):
                fail("optional_hint_recovery_requires_current_policy", 409)
            sidecar = operation / "source_evidence.json"
            if sidecar.exists() and verified_record(sidecar) != expected_sidecar:
                fail("source_evidence_response_changed", 409)
            if not sidecar.exists(): verified_write(sidecar, expected_sidecar)
            source_result_fields = {"source_coverage_findings": [f for page in source_records for f in page["findings"]],
                "source_layout_evidence_sha256": hashlib.sha256(encode(source_records)).hexdigest()}
    try:
        decisions = normalize_proposals(inspect_docx(reviewed, current["review"]["target_lang"]),
            evidence_view, proposals, normalization_version=normalization_version, band_normalization_version=_band_normalization_version(policy_fingerprint), emphasis_normalization_version=emphasis_version)
    except (OrdinaryLayoutError, ValueError):
        return
    if stored_decisions is not None and stored_decisions != decisions:
        return
    if current["generation"] == initial:
        with manager.service.scope(origin) as folder:
            operation = folder / "baselines" / baseline_id / "suggestions" / operation_nonce
            if not (operation / "proposed_decisions.json").exists():
                verified_write(operation / "proposed_decisions.json", decisions)
        applied = manager.service.apply_suggestion(origin, operation_nonce, initial, decisions,
            baseline_id=baseline_id)
        completed_generation = applied["generation"]
    else:
        if stored_decisions is None or current["review"]["decisions"] != decisions:
            return
        completed_generation = current["generation"]
    result = {"operation_nonce": operation_nonce, "baseline_id": baseline_id,
        "generation": completed_generation, "status": "applied_unreviewed",
        "completed_pages": selected_pages, "retry_dispatch_allowed": False,
        "applied_unreviewed": True,
        "accounting": {"cost_usd": summary.get("cost_usd"),
            "known_cost_usd": summary.get("known_cost_usd"),
            "unknown_cost_count": summary.get("unknown_cost_count"), "complete": True}}
    result.update(source_result_fields)
    if repair_proof is not None:
        result["proposal_repair_ledger_sha256"] = hashlib.sha256(encode(repair_proof[0])).hexdigest()
    if source_result_fields:
        from .ordinary_layout_contracts import source_evidence_review_fields
        result.update(source_evidence_review_fields(source_records if any(p.get("version") == "ordinary_layout_proposal_v3" for p in proposals) else records))
    manager.service.finish_suggestion(origin, operation_nonce, result, baseline_id=baseline_id)


def _finish_saved_proposals(manager, folder: Path, identity: dict, pointer: dict,
                            raw_map: dict, frozen_policy: str, job,
                            cancel_requested, begin_publication) -> dict:
    """Rebuild and verify only from an already-settled, saved operation."""
    origin = pointer["origin_job_id"]
    baseline_id = pointer["baseline_id"]
    operation_nonce = pointer["operation_nonce"]
    review_id = pointer["review_id"]
    policy_hash = identity["policy_fingerprint"]
    if (pointer.get("identity_sha256") != hashlib.sha256(encode(identity)).hexdigest()
            or pointer.get("selected_pages") != identity["selected_pages"]
            or pointer.get("retained_pages", {}) != identity.get("retained_pages", {})):
        fail("automatic_operation_identity_changed", 409)
    if cancel_requested(job.job_id):
        fail("automatic_layout_cancelled", 409)
    _recover_settled_result(manager, pointer, identity["selected_pages"], policy_fingerprint=policy_hash)
    outcome = manager.service.suggestion(origin, operation_nonce,
        expected_baseline_id=baseline_id, expected_generation=pointer["initial_generation"],
        page_numbers=identity["selected_pages"])
    if (outcome.get("status") != "applied_unreviewed"
            or outcome.get("completed_pages") != identity["selected_pages"]
            or not outcome.get("accounting", {}).get("complete")):
        fail("automatic_operation_pending_or_uncertain", 409)
    current = manager.service.state(origin)
    review = current["review"]
    if (current["baseline_id"] != baseline_id or review["review_id"] != review_id
            or review["generation"] != outcome["generation"]):
        fail("automatic_generation_changed", 409)
    evidence = _proposal_evidence(manager, origin, baseline_id, review_id, operation_nonce,
        tuple(identity["selected_pages"]), frozen_policy, retained_pages=identity.get("retained_pages", {}))
    manager.service.saved.attach_ordinary_binding(review_id, raw_map,
        tuple(identity["selected_pages"]), policy_hash, evidence,
        expected_generation=review["generation"])
    build_nonce = _nonce("automatic_build", {"operation_nonce": operation_nonce,
        "generation": review["generation"], "policy": policy_hash})
    built = manager.service.saved.build_unreviewed_candidate(review_id,
        review["generation"], build_nonce)
    if cancel_requested(job.job_id) or not begin_publication(job.job_id):
        fail("automatic_layout_cancelled", 409)
    manager.service.publish_automatic_candidate(origin, expected_baseline_id=baseline_id,
        operation_nonce=operation_nonce, candidate_id=built["candidate_id"],
        expected_generation=review["generation"], policy_fingerprint=policy_hash)
    artifact = manager.service.resolve_delivery(origin, 0)
    candidate = manager.service.saved.verified_unreviewed_candidate(review_id, built["candidate_id"])
    costs = _operation_costs(manager, origin, identity)
    with run_workspace_slot(folder):
        copy_path = folder / "output.docx"
        if copy_path.exists():
            if storage._read(copy_path, storage.DOCX_MAX_BYTES) != candidate.docx_bytes:
                fail("automatic_candidate_changed", 409)
        else:
            storage._atomic(copy_path, candidate.docx_bytes)
        record = {"identity": identity, "origin_job_id": origin,
            "review_id": review_id, "candidate_id": built["candidate_id"],
            "generation": candidate.generation, "sha256": candidate.docx_sha256,
            "source_map_sha256": candidate.source_map_sha256,
            "receipt_sha256": hashlib.sha256(encode(candidate.receipt)).hexdigest(),
            "layout_costs": costs}
        marker = folder / "candidate.json"
        if marker.exists():
            if _read_record(marker) != record:
                fail("automatic_candidate_changed", 409)
        else:
            storage._atomic(marker, encode(record))
    if job.job_id != origin:
        manager.service.adopt_automatic_alias(job, origin, built["candidate_id"])
    return {"output_path": str(artifact.path),
        "review_copy_path": str(manager.service.automatic_review_copy(job.job_id)),
        "sha256": artifact.sha256,
        "word_count": artifact.word_count, "candidate_id": built["candidate_id"],
        "source_map_sha256": built["source_map_sha256"], "policy_fingerprint": policy_hash,
        "delivery_kind": artifact.kind, "reviewed": False, "layout_costs": costs,
        **_source_layout_review(candidate),
        **({"recovery_predecessor": identity["recovery_predecessor"]}
           if "recovery_predecessor" in identity else {}),
        **({"revalidation_predecessor": identity["revalidation_predecessor"]}
           if "revalidation_predecessor" in identity else {})}


def run_automatic_layout(manager, accounting, job_id: str, frozen_policy: str,
                         *, cancel_requested=None, begin_publication=None,
                         recovery_old_policy: str | None = None) -> dict:
    """Run the included bounded layout stage against a pinned ordinary job."""
    if not valid_automatic_layout_policy(frozen_policy):
        fail("automatic_policy_invalid", 409)
    cancel_requested = cancel_requested or (lambda _job_id: False)
    begin_publication = begin_publication or (lambda _job_id: True)
    if cancel_requested(job_id):
        fail("automatic_layout_cancelled", 409)
    policy_hash = frozen_policy.split(":", 1)[1]
    job = manager._job(job_id)
    if not job.page_groups or tuple(sorted(job.page_groups)) != job.selected_pages:
        fail("page_mapping_required", 409)
    raw_map = accounting.jobs.trusted_ordinary_raw_map(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    from .ordinary_auto_layout_artifacts import bind_raw_page_map
    mapped = bind_raw_page_map(job.original_docx, raw_map,
        source_pdf_sha256=job.binding["source_sha256"],
        selected_pages=job.selected_pages, target_lang=job.target_lang)
    if mapped.page_ids != {p: tuple(ids) for p, ids in job.page_groups.items()}:
        fail("page_mapping_changed", 409)
    baseline = accounting.jobs.trusted_ordinary_baseline_identity(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    identity = {key: baseline[key] for key in ("run_id", "source_pdf_sha256", "raw_docx_sha256",
        "raw_source_map_bytes_sha256", "selected_pages", "target_lang", "runtime_mode", "workspace_id")}
    identity.update(raw_source_map_sha256=mapped.raw_source_map_sha256,
                    raw_snapshot_fingerprint=mapped.fingerprint, policy_fingerprint=policy_hash)
    root = _durable_folder(baseline)
    retained = {}
    direct = False
    if recovery_old_policy is not None:
        if not supports_manual_layout_recovery(recovery_old_policy):
            fail("automatic_recovery_unsupported_policy", 409)
        if frozen_policy != manual_automatic_layout_policy():
            fail("automatic_policy_changed", 409)
        predecessor = _failed_predecessor(manager, root, identity, recovery_old_policy)
        from .ordinary_layout_service import _read as verified_record
        predecessor_operation = manager.service.root / predecessor["origin_job_id"] / "baselines" / predecessor["baseline_id"] / "suggestions" / predecessor["operation_nonce"]
        predecessor_result = verified_record(predecessor_operation / "result.json")
        predecessor_policy = verified_record(predecessor_operation / "intent.json")["request"]["policy"]
        # Existing durable lineage wins over a newly eligible normalization
        # failure. Historical 8k operations retain their explicit capacity
        # recovery; they cannot be silently relabeled as 32k retained inputs.
        direct = _direct_revalidation(root, predecessor_result, predecessor_policy)
        if direct:
            _, retained = _retained_continuation(manager, root, identity, predecessor, direct=True)
            identity["retained_pages"] = {str(p): r["origin"] for p, r in retained.items()}
            folder = storage._mkdir(root / "recoveries" / "layout_direct_revalidation_v1")
        else:
            folder = _recovery_folder(root)
        if (folder / "operation.json").exists() and not (folder / "candidate.json").exists():
            pointer = _read_record(folder / "operation.json")
            old_operation = manager.service.root / pointer["origin_job_id"] / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
            if (old_operation / "result.json").exists():
                from .ordinary_layout_service import _read as verified_record
                failed = verified_record(old_operation / "result.json")
                errors = {"ordinary_layout_proposal_coverage", "ordinary_layout_invalid_proposal_decisions"} if direct else {"ordinary_layout_page_break_requires_flow"}
                if failed.get("status") == "failed" and failed.get("error_code") in errors:
                    # The existing second successor now also admits one failed
                    # direct child. Preserve original origins and charge each
                    # predecessor once; no recursive recovery chain is created.
                    original_retained = retained
                    parent_identity = dict(identity)
                    parent_identity.pop("retained_pages", None)
                    prior, retained = _retained_continuation(manager, root, parent_identity, predecessor,
                        parent_direct=direct, inherited=original_retained if direct else None)
                    identity["revalidation_predecessor"] = prior
                    identity["retained_pages"] = {str(p): r["origin"] for p, r in retained.items()}
                    folder = storage._mkdir(root / "recoveries" / "layout_revalidation_v1")
        identity["recovery_predecessor"] = predecessor
        if (not (folder / "candidate.json").is_file()
                and (manager.service.root / job_id).is_dir()):
            # A resumed job may have acquired its own delivery selection even
            # though the failed origin remains unselected. Never buy layout
            # pages for an output the operator has already selected.
            with manager.service.scope(job_id) as current_folder:
                if (manager.service._selections(current_folder)
                        or (current_folder / "frozen.json").exists()
                        or (current_folder / "automatic.json").exists()):
                    fail("automatic_recovery_predecessor_selected", 409)
    else:
        folder = root
    recover_pointer = None
    with run_workspace_slot(folder):
        intent_path = folder / "intent.json"
        if intent_path.exists():
            if _read_record(intent_path) != identity:
                fail("automatic_operation_identity_changed", 409)
            candidate_path = folder / "candidate.json"
            if candidate_path.exists():
                if cancel_requested(job_id) or not begin_publication(job_id):
                    fail("automatic_layout_cancelled", 409)
                return _reused_candidate(manager, folder, identity, _read_record(candidate_path), job)
            pointer_path = folder / "operation.json"
            if pointer_path.exists():
                recover_pointer = _read_record(pointer_path)
        else:
            storage._atomic(intent_path, encode(identity))
    if recover_pointer is not None:
        # Paid operation exists. Only local assembly of a settled saved result
        # may continue; pending/unknown results never trigger another request.
        return _finish_saved_proposals(manager, folder, identity, recover_pointer, raw_map, frozen_policy, job,
            cancel_requested, begin_publication)
    if cancel_requested(job_id):
        fail("automatic_layout_cancelled", 409)
    expected_dispatch_policy = manual_automatic_layout_policy() if recovery_old_policy is not None else frozen_automatic_layout_policy()
    if (recovery_old_policy is None and frozen_policy in {_local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy()}
            and expected_dispatch_policy == _source_alignment_v20_policy()):
        # An unfinished saved V17/V18/V19 Start still owns its original automatic stage.
        # Its selected source and checkpoint must authorize this exact policy.
        from .checkpoint import load_run_state
        state = load_run_state(Path(baseline["run_dir"]) / "run_state.json")
        if (state is not None and state.settings.get("ordinary_auto_layout_policy") == frozen_policy
                and state.pdf_fingerprint == identity["source_pdf_sha256"]
                and sorted(map(int, state.pages)) == list(job.selected_pages)):
            expected_dispatch_policy = frozen_policy
    if frozen_policy != expected_dispatch_policy:
        fail("automatic_policy_changed", 409)
    if recovery_old_policy is None:
        accounting.authorize_automatic(job, policy_hash,
            **({"proposal_repair_policy": _proposal_repair_version(policy_hash)} if _proposal_repair_version(policy_hash) is not None else {}))
    else:
        prior_cost = Decimal(identity["recovery_predecessor"]["known_cost_usd"])
        if "revalidation_predecessor" in identity:
            prior_cost += Decimal(identity["revalidation_predecessor"]["known_cost_usd"])
        accounting.authorize_recovery(job, policy_hash, str(prior_cost),
            missing_pages=[p for p in job.selected_pages if p not in retained] if retained else None,
            **({"direct_continuation_identity_sha256": hashlib.sha256(encode(identity)).hexdigest()}
               if direct and "revalidation_predecessor" in identity else {}))
    prepare_nonce = _nonce("automatic_revalidation_prepare" if retained else "automatic_recovery_prepare" if recovery_old_policy is not None else "automatic_prepare",
        {"job_id": job_id, "raw_snapshot": mapped.fingerprint, "policy": policy_hash,
         **({"direct_predecessor": identity["revalidation_predecessor"]["result_sha256"]}
            if direct and "revalidation_predecessor" in identity else {}),
         **({"predecessor": identity["recovery_predecessor"]["result_sha256"]}
            if recovery_old_policy is not None else {})})
    prepared = manager.prepare(job_id, prepare_nonce)
    if cancel_requested(job_id):
        fail("automatic_layout_cancelled", 409)
    baseline_id = prepared["baseline_id"]
    generation = prepared["generation"]
    operation_nonce = _nonce("automatic_revalidation_suggest" if retained else "automatic_recovery_suggest" if recovery_old_policy is not None else "automatic_suggest", {"job_id": job_id,
        "baseline_id": baseline_id, "generation": generation,
        "raw_snapshot": mapped.fingerprint, "policy": policy_hash,
        **({"direct_predecessor": identity["revalidation_predecessor"]["result_sha256"]}
           if direct and "revalidation_predecessor" in identity else {}),
        **({"predecessor": identity["recovery_predecessor"]["result_sha256"]}
           if recovery_old_policy is not None else {})})
    pointer = {"identity_sha256": hashlib.sha256(encode(identity)).hexdigest(),
        "origin_job_id": job_id, "baseline_id": baseline_id,
        "review_id": prepared["review"]["review_id"], "initial_generation": generation,
        "operation_nonce": operation_nonce, "selected_pages": list(job.selected_pages)}
    if retained:
        pointer["retained_pages"] = identity["retained_pages"]
    with run_workspace_slot(folder):
        pointer_path = folder / "operation.json"
        if pointer_path.exists():
            if _read_record(pointer_path) != pointer:
                fail("automatic_operation_identity_changed", 409)
        else:
            storage._atomic(pointer_path, encode(pointer))
    if cancel_requested(job_id):
        manager.service.cancel_suggestion(job_id, operation_nonce, generation,
            expected_baseline_id=baseline_id)
        fail("automatic_layout_cancelled", 409)
    outcome = manager.suggest(job_id, generation, operation_nonce, list(job.selected_pages),
        expected_baseline_id=baseline_id, external_cancel_requested=cancel_requested,
        retained_proposals=retained, band_normalization_version=_band_normalization_version(policy_hash),
        **({"emphasis_normalization_version":_emphasis_normalization_version(policy_hash)}
            if _emphasis_normalization_version(policy_hash) in {"ordinary_optional_emphasis_normalization_v2", "ordinary_optional_emphasis_normalization_v3"} else {}),
        **({"proposal_repair_policy": _proposal_repair_version(policy_hash)}
            if recovery_old_policy is None and _proposal_repair_version(policy_hash) is not None else {}),
        **({"proposal_render_policy_fingerprint": _proposal_render_profile(policy_hash)}
            if recovery_old_policy is None and _proposal_render_profile(policy_hash) is not None else {}))
    if (outcome.get("status") != "applied_unreviewed"
            or outcome.get("completed_pages") != list(job.selected_pages)
            or not outcome.get("accounting", {}).get("complete")):
        fail("automatic_proposal_incomplete", 409)
    return _finish_saved_proposals(manager, folder, identity, pointer, raw_map, frozen_policy, job,
        cancel_requested, begin_publication)


def _rebuild_inputs(manager, accounting, job_id):
    """Resolve immutable raw ownership, independently of the wrapper job ID."""
    job = manager._job(job_id)
    raw_map = accounting.jobs.trusted_ordinary_raw_map(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    baseline = accounting.jobs.trusted_ordinary_baseline_identity(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    from .ordinary_auto_layout_artifacts import bind_raw_page_map
    mapped = bind_raw_page_map(job.original_docx, raw_map,
        source_pdf_sha256=job.binding["source_sha256"], selected_pages=job.selected_pages,
        target_lang=job.target_lang)
    if mapped.page_ids != {p: tuple(ids) for p, ids in job.page_groups.items()}:
        fail("automatic_rebuild_parent_changed", 409)
    identity = {key: baseline[key] for key in ("run_id", "source_pdf_sha256", "raw_docx_sha256",
        "raw_source_map_bytes_sha256", "selected_pages", "target_lang", "runtime_mode", "workspace_id")}
    identity.update(raw_source_map_sha256=mapped.raw_source_map_sha256,
        raw_snapshot_fingerprint=mapped.fingerprint)
    return job, raw_map, baseline, identity


def _rebuild_roots(root):
    return [root, *(root / "recoveries" / name for name in (
        "layout_capacity_v2", "layout_direct_revalidation_v1", "layout_revalidation_v1"))]


def _settled_rebuild_operation(manager, root, base, pointer, *, expected=None, cost_only=False):
    """Read a native settled ledger; copied totals never authorize a rebuild."""
    from .ordinary_layout_contracts import identifier, nonce, decode
    from .ordinary_layout_service import _read
    from .usage_accounting import _state_fingerprint, _summarize
    origin = identifier(pointer.get("origin_job_id"))
    baseline = nonce(pointer.get("baseline_id")); operation_nonce = nonce(pointer.get("operation_nonce"))
    operation = manager.service.root / origin / "baselines" / baseline / "suggestions" / operation_nonce
    intent = _read(operation / "intent.json")
    journal_path = operation / "accounting" / "dispatch_accounting.json"
    journal = decode(storage._read(journal_path, 8 * 1024 * 1024))
    summary = _read(operation / "accounting_summary.json")
    result = _read(operation / "result.json")
    owner = intent.get("identity", {}); binding = owner.get("binding", {})
    request = intent.get("request", {})
    if (owner.get("job_id") != origin or owner.get("run_id") != base["run_id"]
            or owner.get("mode") != base["runtime_mode"] or owner.get("workspace_id") != base["workspace_id"]
            or owner.get("target_lang") != base["target_lang"] or owner.get("selected_pages") != base["selected_pages"]
            or binding.get("source_sha256") != base["source_pdf_sha256"]
            or binding.get("original_sha256") != base["raw_docx_sha256"]
            or binding.get("raw_source_map_sha256") != base["raw_source_map_sha256"]
            or intent.get("baseline_id") != baseline or intent.get("operation_nonce") != operation_nonce
            or request.get("page_numbers") != base["selected_pages"]
            or (request.get("policy", {}).get("max_output_tokens"),request.get("policy", {}).get("timeout_seconds"))
                not in ({(8000,240.0),(32000,480.0)} if cost_only else {(32000,480.0)})
            or journal.get("fingerprint") != _state_fingerprint(journal)
            or journal.get("run_identity") != {"job_id": origin, "run_id": base["run_id"],
                "operation_nonce": operation_nonce, "binding": binding}
            or type(journal.get("events")) is not list
            or _summarize(journal["events"], historical_incomplete=journal.get("historical_incomplete", False),
                pricing_snapshot=journal.get("pricing_snapshot")) != summary
            or summary.get("coverage_status") != "complete" or summary.get("cost_usd") is None
            or summary.get("cost_usd") != summary.get("known_cost_usd")
            or summary.get("unknown_cost_count") != 0 or summary.get("in_flight_count") != 0
            or result.get("retry_dispatch_allowed") is not False
            or result.get("status") not in {"failed", "applied_unreviewed"}
            or cost_only and result.get("status") != "failed"
            or not cost_only and (result.get("provider_refused") or result.get("provider_incomplete_reason")
                or result.get("provider_response_status") not in {None,"completed"})
            or any(result.get("accounting", {}).get(k) != summary.get(k) for k in ("cost_usd", "known_cost_usd", "unknown_cost_count"))):
        fail("automatic_rebuild_accounting_unsettled", 409)
    begins = [e for e in journal["events"] if e.get("event") == "begin"]
    finishes = [e for e in journal["events"] if e.get("event") == "finish"]
    repair_proof = None
    if "proposal_repair_policy" in request.get("policy", {}):
        if cost_only:
            fail("automatic_recovery_unsupported_policy", 409)
        manifest = decode(storage._read(operation / "attempts/manifest.json", 8 * 1024 * 1024))
        repair_proof = _verified_reproposal_operation(operation, manifest.get("identity", {}).get("policy_fingerprint"))
    if (len(journal["events"]) != len(begins) + len(finishes) or len(begins) != len(finishes)
            or len(begins) != summary.get("provider_dispatch_count")
            or summary.get("attempt_count") != len(begins)
            or repair_proof is None and len({e.get("page_number") for e in begins}) != len(begins)):
        fail("automatic_rebuild_accounting_unsettled", 409)
    for begin in begins:
        finish = [e for e in finishes if e.get("call_id") == begin.get("call_id")]
        if (begin.get("purpose") != "layout_suggestion" or begin.get("page_number") not in base["selected_pages"]
                or begin.get("attempt") != 1
                or begin.get("bounds", {}).get("max_output_tokens") != request["policy"]["max_output_tokens"]
                or len(finish) != 1
                or finish[0].get("cost_status") != "available" or finish[0].get("cost_usd") is None
                or cost_only and finish[0].get("outcome") not in {"succeeded","failed"}
                or not cost_only and (finish[0].get("outcome") != "succeeded"
                    or not finish[0].get("response_id") or finish[0].get("error_code") is not None)):
            fail("automatic_rebuild_accounting_unsettled", 409)
    cost = Decimal(str(summary["cost_usd"]))
    if not cost.is_finite() or cost < 0:
        fail("automatic_rebuild_accounting_unsettled", 409)
    roots = [p for p in _rebuild_roots(root) if (p / "operation.json").is_file()
        and _read_record(p / "operation.json").get("origin_job_id") == origin
        and _read_record(p / "operation.json").get("operation_nonce") == operation_nonce]
    if len(roots) != 1:
        fail("automatic_rebuild_origin_ambiguous", 409)
    global_intent = _read_record(roots[0] / "intent.json")
    global_pointer = _read_record(roots[0] / "operation.json")
    if (global_pointer.get("identity_sha256") != hashlib.sha256(encode(global_intent)).hexdigest()
            or global_pointer.get("review_id") != intent.get("review_id")
            or global_pointer.get("initial_generation") != request.get("expected_generation")
            or global_pointer.get("selected_pages") != base["selected_pages"]
            or global_pointer.get("retained_pages", {}) != global_intent.get("retained_pages", {})
            or hashlib.sha256(storage._read(operation.parent.parent / "reviewed.docx", storage.DOCX_MAX_BYTES)).hexdigest() != owner.get("reviewed_sha256")):
        fail("automatic_rebuild_origin_changed", 409)
    for key, value in base.items():
        if global_intent.get(key) != value:
            fail("automatic_rebuild_parent_changed", 409)
    descriptor = {"intent_sha256": hashlib.sha256(storage._read(roots[0] / "intent.json", 8 * 1024 * 1024)).hexdigest(),
        "pointer_sha256": hashlib.sha256(storage._read(roots[0] / "operation.json", 8 * 1024 * 1024)).hexdigest(),
        "result_sha256": hashlib.sha256(storage._read(operation / "result.json", 8 * 1024 * 1024)).hexdigest(),
        "accounting_summary_sha256": hashlib.sha256(storage._read(operation / "accounting_summary.json", 8 * 1024 * 1024)).hexdigest(),
        "accounting_journal_sha256": hashlib.sha256(storage._read(journal_path, 8 * 1024 * 1024)).hexdigest(),
        "known_cost_usd": str(cost), "origin_job_id": origin, "baseline_id": baseline,
        "operation_nonce": operation_nonce}
    if expected is not None and descriptor != expected:
        fail("automatic_rebuild_origin_changed", 409)
    return descriptor, operation, intent, result, begins, global_intent


def _completed_rebuild_proof(manager, accounting, job_id, *, check_invoking_state=True):
    """Verify the completed V5 parent without aliases, writes or provider setup."""
    job, raw_map, baseline, base = _rebuild_inputs(manager, accounting, job_id)
    root = Path(baseline["run_dir"]).resolve() / "ordinary_auto_layout"
    choices = []
    for folder in _rebuild_roots(root):
        if (folder / "candidate.json").is_file():
            marker = _read_record(folder / "candidate.json")
            if marker.get("identity") != _read_record(folder / "intent.json"):
                fail("automatic_rebuild_parent_changed", 409)
            if marker.get("identity", {}).get("policy_fingerprint") in {
                    _reference_footer_v5_policy().split(":", 1)[1], _bounded_page_reproposal_v11_policy().split(":", 1)[1],
                    _per_page_reproposal_v12_policy().split(":", 1)[1], _in_flow_folio_bridges_v13_policy().split(":", 1)[1], _labeled_folio_direction_v14_policy().split(":", 1)[1], _terminal_punctuation_folio_v15_policy().split(":", 1)[1], _bounded_signature_label_v16_policy().split(":", 1)[1], _local_footer_closing_v17_policy().split(":", 1)[1], _contact_folio_v18_policy().split(":", 1)[1], _contact_folio_overlap_v19_policy().split(":", 1)[1], _source_alignment_v20_policy().split(":", 1)[1]}:
                choices.append((folder, marker))
    if not choices:
        return None
    if len(choices) != 1:
        fail("automatic_rebuild_parent_ambiguous", 409)
    folder, marker = choices[0]
    identity = _read_record(folder / "intent.json")
    repair_version = _proposal_repair_version(identity.get("policy_fingerprint"))
    if repair_version is not None:
        from .ordinary_layout_reproposal import automatic_policy
        render_policy = automatic_policy(repair_version, _proposal_render_profile(identity.get("policy_fingerprint")))
    else:
        render_policy = _reference_footer_v5_policy()
    if marker.get("identity") != identity or any(identity.get(k) != v for k, v in base.items()):
        fail("automatic_rebuild_parent_changed", 409)
    pointer = _read_record(folder / "operation.json")
    if pointer.get("identity_sha256") != hashlib.sha256(encode(identity)).hexdigest():
        fail("automatic_rebuild_parent_changed", 409)
    native, operation, intent, result, begins, _ = _settled_rebuild_operation(manager, root, base, pointer)
    from .ordinary_layout_service import _read
    with manager.service.scope(native["origin_job_id"]) as scoped:
        _, manifest = manager.service._baseline(scoped)
        view = manager.service._view(scoped)
        if (manager.service._selections(scoped) or (scoped / "frozen.json").exists()
                or (scoped / "edited_revisions").exists() or not (scoped / "automatic.json").is_file()
                or view.get("baseline_id") != native["baseline_id"]):
            fail("automatic_rebuild_parent_selected", 409)
        automatic = _read(scoped / "automatic.json")
        candidate = manager.service._verified_automatic(scoped, manifest, automatic)
        if (automatic.get("candidate_id") != marker.get("candidate_id")
                or marker.get("origin_job_id") != native["origin_job_id"]
                or marker.get("review_id") != candidate.review_id
                or marker.get("generation") != candidate.generation
                or automatic.get("operation_nonce") != native["operation_nonce"]
                or candidate.generation != result.get("generation")
                or result.get("status") != "applied_unreviewed" or not result.get("applied_unreviewed")
                or result.get("completed_pages") != base["selected_pages"]
                or candidate.current_generation != candidate.generation
                or candidate.docx_sha256 != marker.get("sha256")
                or candidate.source_map_sha256 != marker.get("source_map_sha256")
                or hashlib.sha256(encode(candidate.receipt)).hexdigest() != marker.get("receipt_sha256")
                or candidate.policy_fingerprint != identity["policy_fingerprint"]
                or storage._read(folder / "output.docx", storage.DOCX_MAX_BYTES) != candidate.docx_bytes
                or view["review"]["decisions"] != _read(operation / "proposed_decisions.json")):
            fail("automatic_rebuild_parent_changed", 409)
        if intent["identity"] != manifest["identity"]:
            fail("automatic_rebuild_origin_changed", 409)
        # A later acceptance is a human decision, never a migration input.
        if view.get("output_reviews") or view.get("edited_revision"):
            fail("automatic_rebuild_parent_selected", 409)
    retained, ledgers = {}, {native["accounting_journal_sha256"]: native}
    expected_retained = identity.get("retained_pages", {})
    if pointer.get("retained_pages", {}) != expected_retained:
        fail("automatic_rebuild_origin_changed", 409)
    _verified_retained_pages(operation, expected_retained)
    for page in base["selected_pages"]:
        raw = storage._read(operation / f"page-{page:04d}.response.json", 2 * 1024 * 1024)
        if str(page) in expected_retained:
            origin = expected_retained[str(page)]
            prior = origin.get("predecessor", {})
            desc, origin_op, _, _, origin_begins, origin_identity = _settled_rebuild_operation(manager, root, base, prior, expected=prior)
            if (set(origin) != {"version", "source_page_number", "response_sha256", "predecessor", "original_policy_fingerprint", "provider_call_id", "locally_revalidated"}
                    or origin.get("version") != "ordinary_retained_proposal_v1" or origin.get("source_page_number") != page
                    or origin.get("response_sha256") != hashlib.sha256(raw).hexdigest()
                    or origin.get("locally_revalidated") is not True
                    or origin.get("original_policy_fingerprint") != origin_identity["policy_fingerprint"]
                    or storage._read(origin_op / f"page-{page:04d}.response.json", 2 * 1024 * 1024) != raw
                    or len([b for b in origin_begins if b.get("page_number") == page and b.get("call_id") == origin.get("provider_call_id")]) != 1):
                fail("automatic_rebuild_origin_changed", 409)
        else:
            calls = [b for b in begins if b.get("page_number") == page]
            if _proposal_repair_version(identity.get("policy_fingerprint")):
                witness, _, _ = _verified_reproposal_operation(operation, identity["policy_fingerprint"])
                selection = decode(witness["records"][f"page-{page:04d}/selection.json"])
                calls = [b for b in calls if b.get("call_id") == selection["call_id"]]
            if len(calls) != 1:
                fail("automatic_rebuild_origin_changed", 409)
            desc = native
            origin = {"version": "ordinary_retained_proposal_v1", "source_page_number": page,
                "response_sha256": hashlib.sha256(raw).hexdigest(), "predecessor": native,
                "original_policy_fingerprint": identity["policy_fingerprint"],
                "provider_call_id": calls[0]["call_id"], "locally_revalidated": True}
        ledgers[desc["accounting_journal_sha256"]] = desc
        retained[page] = {"raw": raw, "origin": origin}
    for name in ("recovery_predecessor", "revalidation_predecessor"):
        if name in identity:
            prior, *_ = _settled_rebuild_operation(manager, root, base, identity[name], expected=identity[name],cost_only=True)
            ledgers[prior["accounting_journal_sha256"]] = prior
    known = sum((Decimal(p["known_cost_usd"]) for p in ledgers.values()), Decimal(0))
    costs = _operation_costs(manager, native["origin_job_id"], identity)
    if (Decimal(costs["known_cost_usd"]) != known or costs != marker.get("layout_costs")):
        fail("automatic_rebuild_accounting_unsettled", 409)
    evidence = _proposal_evidence(manager, native["origin_job_id"], native["baseline_id"], marker["review_id"],
        native["operation_nonce"], job.selected_pages, render_policy, retained_pages=expected_retained)
    from .ordinary_source_folio_proof import KEY
    saved_folder = manager.service.saved._folder(marker["review_id"])
    saved_evidence = _read_record(saved_folder / "ordinary_proposals" / f"{candidate.generation:06d}.json")["proposal_evidence"]
    if {k: v for k, v in saved_evidence.items() if k != KEY} != evidence:
        fail("automatic_rebuild_parent_changed", 409)
    # The saved binding reader independently checks the evidence and source proof.
    if candidate.source_pdf_sha256 != base["source_pdf_sha256"] or candidate.raw_docx_sha256 != base["raw_docx_sha256"]:
        fail("automatic_rebuild_parent_changed", 409)
    with accounting.jobs._lock:
        record = accounting.jobs._jobs[job_id]
        config = record._config
        original_policy = record._ordinary_auto_layout_policy
        parent_id = record._rebuild_origin_job_id
    # Rebuild cannot evade a selection made on the invoking wrapper or alias.
    for current_id in ({job_id, parent_id} - {None, native["origin_job_id"]}) if check_invoking_state else ():
        if (manager.service.root / current_id).is_dir():
            with manager.service.scope(current_id) as current_folder:
                if (manager.service._selections(current_folder) or (current_folder / "frozen.json").exists()
                        or (current_folder / "edited_revisions").exists() or (current_folder / "alias_edits").exists()):
                    fail("automatic_rebuild_parent_selected", 409)
            current_view = manager.service.state(current_id)
            if (current_view.get("output_reviews") or current_view.get("edited_revision")
                    or (current_view.get("delivery") or {}).get("kind") in {"automatic_unreviewed_edited", "text_corrected", "reviewed"}):
                fail("automatic_rebuild_parent_selected", 409)
    if _read_record(root / "intent.json").get("policy_fingerprint") != (original_policy or "").split(":")[-1]:
        fail("automatic_rebuild_original_policy_changed", 409)
    from .checkpoint import load_run_state
    from .workflow_semantic_audit import select_pages
    state = load_run_state(Path(baseline["run_dir"]) / "run_state.json")
    _, selected = select_pages(state=state, config=config, run_dir=Path(baseline["run_dir"]), pages_dir=Path(baseline["run_dir"]) / "pages")
    if selected is not None:
        selected_hashes = {str(p): hashlib.sha256(t.encode("utf-8")).hexdigest() for p, t in selected.selected_text_by_page.items()}
    else:
        selected_hashes = {str(p): hashlib.sha256(storage._read(Path(baseline["run_dir"]) / "pages" / f"page_{p:04d}.txt", 8 * 1024 * 1024)).hexdigest()
            for p in job.selected_pages}
    source_accountant, _, source_cost = accounting._source(job)
    descriptor = {"version": "completed_unreviewed_rebuild_predecessor_v1",
        "owner_root": str(manager.service.root.resolve()), "run_root": str(Path(baseline["run_dir"]).resolve()),
        "parent_folder": str(folder.resolve()), "candidate_id": candidate.candidate_id,
        "review_id": candidate.review_id, "generation": candidate.generation,
        "sha256": candidate.docx_sha256, "source_map_sha256": candidate.source_map_sha256,
        "receipt_sha256": marker["receipt_sha256"], "candidate_marker_sha256": hashlib.sha256(encode(marker)).hexdigest(),
        "operation": native, "evidence_sha256": hashlib.sha256(encode(evidence)).hexdigest(),
        "selected_text_sha256": selected_hashes, "original_policy": original_policy,
        "render_policy": render_policy, "layout_costs": costs,
        "source_cost_usd": str(source_cost), "source_accounting_identity": source_accountant.run_identity,
        "source_budget_context": source_accountant.budget_identity,
        "source_accounting_sha256": hashlib.sha256(storage._read(source_accountant.journal_path, 8 * 1024 * 1024)).hexdigest()}
    return descriptor, retained, job, raw_map, baseline, base


def completed_unreviewed_rebuild_predecessor(manager, accounting, job_id):
    """Read-only product proof for the closed V5-to-inline renderer migration."""
    proof = _completed_rebuild_proof(manager, accounting, job_id)
    return proof[0] if proof is not None else None


def run_completed_unreviewed_rebuild(manager, accounting, job_id, *, cancel_requested=None, begin_publication=None):
    """One local immutable successor; missing input never falls back to a provider."""
    proof = _completed_rebuild_proof(manager, accounting, job_id)
    if proof is None:
        return None
    predecessor, retained, job, raw_map, baseline, base = proof
    cancel_requested = cancel_requested or (lambda _: False)
    begin_publication = begin_publication or (lambda _: True)
    if predecessor["render_policy"] in {_bounded_page_reproposal_v11_policy(), _per_page_reproposal_v12_policy(), _in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy()}:
        parent = Path(predecessor["parent_folder"])
        # Same-policy rebuild reuses the fully reverified selected artifact.
        # No retained successor, new application attempt or allowance is created.
        if cancel_requested(job_id) or not begin_publication(job_id):
            fail("automatic_layout_cancelled", 409)
        return _reused_candidate(manager, parent, _read_record(parent / "intent.json"),
            _read_record(parent / "candidate.json"), job)
    policy = _inline_folio_direction_policy()
    identity = dict(base, policy_fingerprint=policy.split(":", 1)[1],
        rebuild_predecessor=predecessor, retained_pages={str(p): r["origin"] for p, r in retained.items()},
        retained_only=True, missing_pages=[], max_new_calls=0)
    identity_sha = hashlib.sha256(encode(identity)).hexdigest()
    folder = storage._mkdir(Path(baseline["run_dir"]) / "ordinary_auto_layout" / "rebuilds" / "completed_unreviewed_v1" / identity["policy_fingerprint"])
    if cancel_requested(job_id):
        fail("automatic_layout_cancelled", 409)
    with run_workspace_slot(folder):
        if (folder / "intent.json").exists():
            if _read_record(folder / "intent.json") != identity:
                fail("automatic_rebuild_identity_changed", 409)
        else:
            storage._atomic(folder / "intent.json", encode(identity))
        pointer = _read_record(folder / "operation.json") if (folder / "operation.json").exists() else None
        if (folder / "candidate.json").exists():
            _verify_rebuild_zero(manager, pointer, identity)
            if cancel_requested(job_id) or not begin_publication(job_id):
                fail("automatic_layout_cancelled", 409)
            return _reused_candidate(manager, folder, identity, _read_record(folder / "candidate.json"), job)
    local_policy, local_accountant = accounting.completed_rebuild(job, folder, identity_sha,
        predecessor["layout_costs"]["known_cost_usd"])
    if pointer is None:
        # Pin the original operation owner BEFORE preparation, so a crash in
        # prepare cannot create a second namespace on the next wrapper job.
        with run_workspace_slot(folder):
            preparation_path = folder / "preparation.json"
            if preparation_path.exists():
                preparation = _read_record(preparation_path)
            else:
                preparation = {"identity_sha256": identity_sha, "origin_job_id": job_id,
                    "prepare_nonce": _nonce("completed_rebuild_prepare", {"job_id": job_id, "identity": identity_sha})}
                storage._atomic(preparation_path, encode(preparation))
        if (preparation.get("identity_sha256") != identity_sha
                or preparation.get("prepare_nonce") != _nonce("completed_rebuild_prepare", {"job_id": preparation.get("origin_job_id"), "identity": identity_sha})):
            fail("automatic_rebuild_identity_changed", 409)
        from dataclasses import replace
        from .ordinary_layout_contracts import identifier
        owner = identifier(preparation["origin_job_id"])
        binding = dict(job.binding); binding["job_id"] = owner
        prepared = manager.service.prepare(replace(job, job_id=owner, binding=binding), preparation["prepare_nonce"])
        pointer = {"identity_sha256": identity_sha, "origin_job_id": owner,
            "baseline_id": prepared["baseline_id"], "review_id": prepared["review"]["review_id"],
            "initial_generation": prepared["generation"], "selected_pages": list(job.selected_pages),
            "retained_pages": identity["retained_pages"],
            "operation_nonce": _nonce("completed_rebuild_suggest", {"identity": identity_sha, "job_id": owner})}
        with run_workspace_slot(folder):
            if (folder / "operation.json").exists() and _read_record(folder / "operation.json") != pointer:
                fail("automatic_rebuild_identity_changed", 409)
            if not (folder / "operation.json").exists():
                storage._atomic(folder / "operation.json", encode(pointer))
    if pointer.get("identity_sha256") != identity_sha or pointer.get("retained_pages") != identity["retained_pages"]:
        fail("automatic_rebuild_identity_changed", 409)
    # Recheck all durable inputs immediately before local work and publication.
    def recheck():
        if completed_unreviewed_rebuild_predecessor(manager, accounting, job_id) != predecessor:
            fail("automatic_rebuild_parent_changed", 409)
        return identity["retained_pages"]
    recheck()
    outcome = manager.suggest(pointer["origin_job_id"], pointer["initial_generation"], pointer["operation_nonce"],
        list(job.selected_pages), expected_baseline_id=pointer["baseline_id"],
        external_cancel_requested=lambda _: cancel_requested(job_id), retained_proposals=retained,
        band_normalization_version=_band_normalization_version(identity["policy_fingerprint"]),
        retained_only=True, retained_source_job=job, retained_identity_sha256=identity_sha,
        retained_policy=local_policy, retained_accounting_factory=local_accountant, retained_preflight=recheck)
    if outcome.get("status") != "applied_unreviewed":
        fail("automatic_proposal_incomplete", 409)
    _verify_rebuild_zero(manager, pointer, identity)
    recheck()
    def publish(current):
        recheck()
        _verify_rebuild_zero(manager, pointer, identity)
        return begin_publication(current)
    return _finish_saved_proposals(manager, folder, identity, pointer, raw_map, policy, job, cancel_requested, publish)


def _verify_rebuild_zero(manager, pointer, identity):
    if identity.get("rebuild_predecessor", {}).get("render_policy") in {_bounded_page_reproposal_v11_policy(), _per_page_reproposal_v12_policy(), _in_flow_folio_bridges_v13_policy(), _labeled_folio_direction_v14_policy(), _terminal_punctuation_folio_v15_policy(), _bounded_signature_label_v16_policy(), _local_footer_closing_v17_policy(), _contact_folio_v18_policy(), _contact_folio_overlap_v19_policy(), _source_alignment_v20_policy()}:
        fail("automatic_rebuild_unsupported_lineage", 409)
    from .ordinary_layout_service import _read
    from .usage_accounting import _state_fingerprint, _summarize
    operation = manager.service.root / pointer["origin_job_id"] / "baselines" / pointer["baseline_id"] / "suggestions" / pointer["operation_nonce"]
    intent = _read(operation / "intent.json")
    journal = _read_record(operation / "accounting" / "dispatch_accounting.json")
    summary = _read(operation / "accounting_summary.json")
    identity_sha = hashlib.sha256(encode(identity)).hexdigest()
    folder = Path(identity["rebuild_predecessor"]["run_root"]) / "ordinary_auto_layout" / "rebuilds" / "completed_unreviewed_v1" / identity["policy_fingerprint"]
    preparation = _read_record(folder / "preparation.json")
    owner = intent.get("identity", {})
    private = intent["request"]["policy"]
    from .ordinary_layout_accounting import MODEL, verified_page_ceiling
    from .ordinary_layout_contracts import LayoutSuggestionPolicy, VERSION
    ceiling = verified_page_ceiling()
    expected_policy = LayoutSuggestionPolicy(MODEL, str(ceiling), str(ceiling * len(identity["selected_pages"]))).public()
    expected_policy.update(retained_only=True, missing_pages=[], max_new_calls=0,
        completed_rebuild_identity_sha256=identity_sha,
        band_normalization_version=_band_normalization_version(identity["policy_fingerprint"]))
    native_baseline = _read(operation.parent.parent / "manifest.json")
    expected_intent = {"version": VERSION, "operation_nonce": pointer["operation_nonce"],
        "baseline_id": pointer["baseline_id"], "review_id": pointer["review_id"], "identity": native_baseline["identity"],
        "request": {"expected_generation": pointer["initial_generation"], "page_numbers": identity["selected_pages"], "policy": expected_policy}}
    if ({p.name for p in operation.glob("page-*.response.json")} != {f"page-{p:04d}.response.json" for p in identity["selected_pages"]}
            or {p.name for p in operation.glob("page-*.retained.json")} != {f"page-{p:04d}.retained.json" for p in identity["selected_pages"]}):
        fail("automatic_rebuild_origin_changed",409)
    if (pointer.get("identity_sha256") != identity_sha
            or preparation.get("identity_sha256") != identity_sha or preparation.get("origin_job_id") != pointer["origin_job_id"]
            or preparation.get("prepare_nonce") != pointer["baseline_id"]
            or pointer["operation_nonce"] != _nonce("completed_rebuild_suggest", {"identity": identity_sha, "job_id": pointer["origin_job_id"]})
            or intent.get("review_id") != pointer.get("review_id") or intent.get("baseline_id") != pointer["baseline_id"]
            or intent.get("operation_nonce") != pointer["operation_nonce"]
            or intent["request"].get("expected_generation") != pointer.get("initial_generation")
            or intent["request"].get("page_numbers") != identity["selected_pages"]
            or owner.get("job_id") != pointer["origin_job_id"] or owner.get("run_id") != identity["run_id"]
            or owner.get("mode") != identity["runtime_mode"] or owner.get("workspace_id") != identity["workspace_id"]
            or owner.get("source_sha256") != identity["source_pdf_sha256"] or owner.get("original_sha256") != identity["raw_docx_sha256"]
            or owner.get("selected_pages") != identity["selected_pages"] or owner.get("target_lang") != identity["target_lang"]
            or owner.get("reviewed_sha256") != hashlib.sha256(storage._read(operation.parent.parent / "reviewed.docx", storage.DOCX_MAX_BYTES)).hexdigest()
            or intent != expected_intent
            or private.get("completed_rebuild_identity_sha256") != identity_sha
            or private.get("retained_only") is not True or private.get("max_new_calls") != 0 or private.get("missing_pages") != []
            or journal.get("run_identity") != {"job_id": pointer["origin_job_id"], "run_id": intent["identity"]["run_id"],
                "operation_nonce": pointer["operation_nonce"], "binding": intent["identity"]["binding"]}
            or journal.get("fingerprint") != _state_fingerprint(journal) or journal.get("events") != []
            or _summarize([], historical_incomplete=journal.get("historical_incomplete", False), pricing_snapshot=journal.get("pricing_snapshot")) != summary
            or Decimal(str(summary.get("cost_usd"))) != 0 or summary.get("provider_dispatch_count") != 0
            or summary.get("attempt_count") != 0 or summary.get("unknown_cost_count") != 0 or summary.get("in_flight_count") != 0):
        fail("automatic_rebuild_accounting_unsettled", 409)
    predecessor = identity["rebuild_predecessor"]
    authorization = _read_record(folder / "authorization.json")
    expected_auth_identity = {"completed_rebuild_identity_sha256": identity_sha,
        "original_accounting_identity": predecessor["source_accounting_identity"], "missing_pages": [], "max_new_calls": 0}
    expected_authorization = {"authorization_kind": "server_owned_completed_unreviewed_rebuild_v1",
        "identity": expected_auth_identity, "translation_cost_usd": predecessor["source_cost_usd"],
        "prior_layout_cost_usd": str(Decimal(predecessor["layout_costs"]["known_cost_usd"])),
        "cap_usd": "0", "retained_only": True}
    if authorization != expected_authorization:
        fail("automatic_rebuild_accounting_unsettled", 409)
    expected_budget = predecessor["source_budget_context"]
    if expected_budget.get("hard") is False:
        from .budget_reservations import ReservationBudget, BudgetError
        from .usage_accounting import _budget_identity
        try:
            budget = ReservationBudget(folder / "budget.json", cap_usd="0", identity=expected_auth_identity, create=False)
            status = budget.status()
        except BudgetError:
            fail("automatic_rebuild_accounting_unsettled", 409)
        if status["blocked"] or status["attempts"] != 0 or Decimal(status["cap_usd"]) != 0:
            fail("automatic_rebuild_accounting_unsettled", 409)
        expected_budget = _budget_identity(budget)
    if journal.get("budget_context") != expected_budget:
        fail("automatic_rebuild_accounting_unsettled", 409)
    if (folder / "candidate.json").is_file():
        marker = _read_record(folder / "candidate.json")
        evidence = _read_record(manager.service.saved._folder(marker["review_id"]) / "ordinary_proposals" / f"{marker['generation']:06d}.json")["proposal_evidence"]
        if evidence.get("intent_sha256") != hashlib.sha256(storage._read(operation / "intent.json", 8 * 1024 * 1024)).hexdigest():
            fail("automatic_rebuild_identity_changed", 409)


def verified_completed_rebuild_layout_costs(manager, job, current):
    """Resolve internal successor lineage without adding fields to public results."""
    automatic = job.get("result", {}).get("automatic_layout", {})
    folder = Path(job.get("result", {}).get("run_dir", "")) / "ordinary_auto_layout" / "rebuilds" / "completed_unreviewed_v1" / _inline_folio_direction_policy().split(":", 1)[1]
    if not (folder / "candidate.json").is_file():
        return current
    marker = _read_record(folder / "candidate.json")
    if automatic.get("candidate_id") != marker.get("candidate_id"):
        return current
    accounting = getattr(manager, "_completed_rebuild_accounting", None)
    if accounting is None:
        fail("automatic_rebuild_accounting_unsettled", 409)
    proof = _completed_rebuild_proof(manager, accounting, job["job_id"], check_invoking_state=False)
    predecessor = proof[0] if proof else None
    identity = _read_record(folder / "intent.json")
    if (predecessor is None or identity.get("rebuild_predecessor") != predecessor
            or marker.get("identity") != identity or not current["complete"]):
        fail("automatic_rebuild_accounting_unsettled", 409)
    _verify_rebuild_zero(manager, _read_record(folder / "operation.json"), identity)
    prior=predecessor["layout_costs"]
    published={"cost_usd":prior["cost_usd"],"known_cost_usd":prior["known_cost_usd"],
        "complete":True,"operations":prior["operations"]+1}
    if published != marker.get("layout_costs"):
        fail("automatic_rebuild_accounting_unsettled", 409)
    known=Decimal(prior["known_cost_usd"])+Decimal(current["known_cost_usd"])
    return {"cost_usd":str(known),"known_cost_usd":str(known),"complete":True,
        "operations":prior["operations"]+current["operations"]}


def cancel_automatic_layout(manager, accounting, job_id: str, *, recovery: bool = False) -> None:
    """Bridge an active browser Cancel to the durable page-boundary marker."""
    baseline = accounting.jobs.trusted_ordinary_baseline_identity(job_id,
        runtime_mode=manager.mode, workspace_id=manager.workspace_id)
    root = _durable_folder(baseline)
    folder = _recovery_folder(root) if recovery else root
    if recovery and (root / "recoveries" / "layout_direct_revalidation_v1" / "operation.json").exists():
        folder = root / "recoveries" / "layout_direct_revalidation_v1"
    if recovery and (root / "recoveries" / "layout_revalidation_v1" / "operation.json").exists():
        folder = root / "recoveries" / "layout_revalidation_v1"
    pointer_path = folder / "operation.json"
    if not pointer_path.exists():
        return
    pointer = _read_record(pointer_path)
    if pointer.get("origin_job_id") != job_id:
        return  # A reused operation has no new page dispatch to cancel.
    manager.service.cancel_suggestion(job_id, pointer["operation_nonce"],
        pointer["initial_generation"], expected_baseline_id=pointer["baseline_id"])


def verified_recovery_layout_costs(manager, job: dict, current: dict) -> dict:
    """Add a failed predecessor's known charge once, from immutable files."""
    automatic = job.get("result", {}).get("automatic_layout", {})
    predecessor = automatic.get("recovery_predecessor")
    if type(predecessor) is not dict or not current.get("complete"):
        fail("automatic_recovery_accounting_unsettled", 409)
    from .ordinary_layout_contracts import identifier, nonce
    origin = identifier(predecessor.get("origin_job_id"))
    baseline_id = nonce(predecessor.get("baseline_id"))
    operation_nonce = nonce(predecessor.get("operation_nonce"))
    trusted = manager._job(job["job_id"])
    root = Path(job["result"]["run_dir"]).expanduser().resolve() / "ordinary_auto_layout"
    recovery = root / "recoveries" / "layout_capacity_v2"
    if (root / "recoveries" / "layout_direct_revalidation_v1" / "intent.json").exists():
        recovery = root / "recoveries" / "layout_direct_revalidation_v1"
    if automatic.get("revalidation_predecessor"):
        recovery = root / "recoveries" / "layout_revalidation_v1"
    marker = _read_record(recovery / "candidate.json")
    identity = marker.get("identity")
    if (type(identity) is not dict or identity.get("recovery_predecessor") != predecessor
            or identity.get("source_pdf_sha256") != trusted.binding["source_sha256"]
            or identity.get("raw_docx_sha256") != hashlib.sha256(trusted.original_docx).hexdigest()
            or identity.get("raw_source_map_sha256") != trusted.binding["raw_source_map_sha256"]
            or identity.get("run_id") != trusted.run_id
            or identity.get("target_lang") != trusted.target_lang
            or identity.get("selected_pages") != list(trusted.selected_pages)
            or identity.get("runtime_mode") != trusted.mode
            or identity.get("workspace_id") != trusted.workspace_id
            or (marker.get("origin_job_id") != job["job_id"]
                and not (manager.service.state(job["job_id"]).get("automatic_alias")
                    and manager.service.state(job["job_id"]).get("delivery", {}).get("artifact_id")
                        == marker.get("candidate_id")))):
        fail("automatic_recovery_identity_changed", 409)
    operation = manager.service.root / origin / "baselines" / baseline_id / "suggestions" / operation_nonce
    paths = {"intent_sha256": root / "intent.json", "pointer_sha256": root / "operation.json",
        "result_sha256": operation / "result.json",
        "accounting_summary_sha256": operation / "accounting_summary.json",
        "accounting_journal_sha256": operation / "accounting" / "dispatch_accounting.json"}
    if any(hashlib.sha256(storage._read(path, 8 * 1024 * 1024)).hexdigest() != predecessor[key]
           for key, path in paths.items()):
        fail("automatic_recovery_predecessor_changed", 409)
    from .ordinary_layout_service import _read as verified_record
    summary = verified_record(paths["accounting_summary_sha256"])
    if (summary.get("coverage_status") != "complete" or summary.get("unknown_cost_count") != 0
            or summary.get("in_flight_count") != 0
            or str(summary.get("cost_usd")) != predecessor.get("known_cost_usd")):
        fail("automatic_recovery_predecessor_unsettled", 409)
    try:
        prior = Decimal(predecessor["known_cost_usd"])
        present = Decimal(current["known_cost_usd"])
        if not prior.is_finite() or not present.is_finite() or prior < 0 or present < 0:
            raise ValueError
    except (ValueError, KeyError):
        fail("automatic_recovery_accounting_changed", 409)
    predecessors = [predecessor]
    extra = automatic.get("revalidation_predecessor")
    if extra:
        if identity.get("revalidation_predecessor") != extra:
            fail("automatic_recovery_identity_changed", 409)
        extra_origin = identifier(extra.get("origin_job_id"))
        extra_operation = manager.service.root / extra_origin / "baselines" / nonce(extra.get("baseline_id")) / "suggestions" / nonce(extra.get("operation_nonce"))
        extra_root = root / "recoveries" / "layout_capacity_v2"
        direct_root = root / "recoveries" / "layout_direct_revalidation_v1"
        if (direct_root / "intent.json").is_file() and hashlib.sha256(storage._read(direct_root / "intent.json", 8 * 1024 * 1024)).hexdigest() == extra["intent_sha256"]:
            extra_root = direct_root
        extra_paths = {"intent_sha256": extra_root / "intent.json", "pointer_sha256": extra_root / "operation.json",
            "result_sha256": extra_operation / "result.json",
            "accounting_summary_sha256": extra_operation / "accounting_summary.json",
            "accounting_journal_sha256": extra_operation / "accounting" / "dispatch_accounting.json"}
        if any(hashlib.sha256(storage._read(p, 8 * 1024 * 1024)).hexdigest() != extra[k] for k, p in extra_paths.items()):
            fail("automatic_recovery_predecessor_changed", 409)
        extra_summary = verified_record(extra_paths["accounting_summary_sha256"])
        if (extra_summary.get("coverage_status") != "complete" or extra_summary.get("unknown_cost_count") != 0
                or extra_summary.get("in_flight_count") != 0 or str(extra_summary.get("cost_usd")) != extra.get("known_cost_usd")):
            fail("automatic_recovery_predecessor_unsettled", 409)
        predecessors.append(extra)
    inherited = [p for p in predecessors if p["origin_job_id"] != marker["origin_job_id"]]
    inherited_cost = sum((Decimal(p["known_cost_usd"]) for p in inherited), Decimal(0))
    included_cost = sum((Decimal(p["known_cost_usd"]) for p in predecessors if p not in inherited), Decimal(0))
    if present < included_cost:
        fail("automatic_recovery_accounting_changed", 409)
    total = inherited_cost + present
    if marker.get("layout_costs", {}).get("cost_usd") != str(total):
        fail("automatic_recovery_accounting_changed", 409)
    return {"cost_usd": str(total), "known_cost_usd": str(total), "complete": True,
        "operations": current["operations"] + len(inherited),
        "predecessor_cost_usd": str(inherited_cost + included_cost),
        "recovery_cost_usd": str(present - included_cost)}
