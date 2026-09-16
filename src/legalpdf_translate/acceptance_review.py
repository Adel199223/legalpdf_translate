"""Explicit source-anchored AI test-review edits to immutable paid responses.

No automatic correction, provider, credential, accounting or settings access.
The caller pins the independently authored manifest and rechecks it during
publication. Hashes prove exact selection, not the reviewer's legal competence.
"""
from copy import deepcopy
import re

from .formatting_support import digest_text, fingerprint
from .structured_arabic_literals import _view
from .structured_artifacts import StructuredArtifactError


REVIEW_VERSION = 'acceptance_review_patch_v1'
REVIEWED_RECOVERY_VERSION = 'legal_blocks_reviewed_recovery_v1'
VISIBLE_PROJECTION_VERSION = 'structured_literal_visible_v1'
_REASON = re.compile(r'[a-z][a-z0-9_]{0,79}\Z')
_FORBIDDEN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u200e\u200f\u202a-\u202e\u2066-\u2069]|\[\[|\]\]|p[0-9]{4,}_b[0-9]{4,}')


class AcceptanceReviewError(StructuredArtifactError):
    """Content-free review-binding failure."""


def _require(condition, code='invalid_acceptance_review'):
    if not condition:
        raise AcceptanceReviewError(code)


def _visible(value):
    try:
        return _view(value)[0]
    except ValueError:
        raise AcceptanceReviewError('invalid_review_original_text') from None


def apply_reviewed_edits(manifest, source_rows, target_rows, *, expected_binding):
    """Apply exact reviewed ranges, leaving all other visible characters intact.

Offsets are into the original visible strings, not strings changed by a prior
edit. The caller must still run normal structural/language/literal validation.
"""
    _require(type(manifest) is dict and set(manifest) == {'version', 'text_projection', 'reviewer_kind', 'binding', 'edits'})
    _require(manifest['version'] == REVIEW_VERSION and manifest['reviewer_kind'] == 'codex_ai_test_review')
    _require(manifest['text_projection'] == VISIBLE_PROJECTION_VERSION)
    _require(type(manifest['binding']) is dict and manifest['binding'] == expected_binding,
             'review_evidence_binding_mismatch')
    edits = manifest['edits']
    _require(type(edits) is list and 1 <= len(edits) <= 64)
    _require(len(source_rows) == len(target_rows) and all(s['id'] == t['id'] for s, t in zip(source_rows, target_rows)))
    sources = {row['id']: _visible(row['text']) for row in source_rows}
    targets = {row['id']: _visible(row['text']) for row in target_rows}
    raw_sources = {row['id']: row['text'] for row in source_rows}
    raw_targets = {row['id']: row['text'] for row in target_rows}
    _require(len(sources) == len(source_rows) and len(targets) == len(target_rows))
    grouped = {}
    required = {'block_id', 'source_text_sha256', 'target_text_sha256', 'source_visible_sha256',
                'target_visible_sha256', 'source_start', 'source_end',
                'source_text', 'target_start', 'target_end', 'before', 'after', 'reason_code'}
    for edit in edits:
        _require(type(edit) is dict and set(edit) == required)
        block = edit['block_id']
        _require(isinstance(block, str) and block in sources)
        source, target = sources[block], targets[block]
        _require(edit['source_text_sha256'] == digest_text(raw_sources[block])
                 and edit['target_text_sha256'] == digest_text(raw_targets[block])
                 and edit['source_visible_sha256'] == digest_text(source)
                 and edit['target_visible_sha256'] == digest_text(target), 'review_text_binding_mismatch')
        _require(all(type(edit[key]) is int for key in ('source_start', 'source_end', 'target_start', 'target_end')))
        ss, se, ts, te = (edit[key] for key in ('source_start', 'source_end', 'target_start', 'target_end'))
        _require(0 <= ss < se <= len(source) and 0 <= ts < te <= len(target))
        _require(all(isinstance(edit[key], str) and 0 < len(edit[key]) <= 2048
                     for key in ('source_text', 'before', 'after')))
        _require(source[ss:se] == edit['source_text'] and target[ts:te] == edit['before'], 'review_span_mismatch')
        _require(edit['before'] != edit['after'] and not _FORBIDDEN.search(edit['after']))
        _require(isinstance(edit['reason_code'], str) and _REASON.fullmatch(edit['reason_code']))
        grouped.setdefault(block, []).append(edit)
    order = {row['id']: index for index, row in enumerate(source_rows)}
    _require(edits == sorted(edits, key=lambda edit: (order[edit['block_id']], edit['target_start'])),
             'noncanonical_review_edit_order')
    _require(sum(len(edit['before']) + len(edit['after']) for edit in edits) <= 16384)
    result = deepcopy(target_rows)
    for row in result:
        text = targets[row['id']]
        selected = sorted(grouped.get(row['id'], []), key=lambda edit: edit['target_start'])
        _require(all(a['target_end'] <= b['target_start'] for a, b in zip(selected, selected[1:])),
                 'overlapping_review_edits')
        for edit in reversed(selected):
            text = text[:edit['target_start']] + edit['after'] + text[edit['target_end']:]
        row['text'] = text
    _require(any(row['text'] != targets[row['id']] for row in result), 'review_has_no_visible_change')
    return result, {'version': REVIEW_VERSION, 'reviewer_kind': manifest['reviewer_kind'],
        'text_projection': VISIBLE_PROJECTION_VERSION,
        'manifest_fingerprint': fingerprint(manifest), 'edit_count': len(edits),
        'reason_codes': sorted({edit['reason_code'] for edit in edits}),
        'original_visible_sha256': fingerprint(targets),
        'reviewed_visible_sha256': fingerprint({row['id']: row['text'] for row in result}),
        'human_certified': False, 'legal_fidelity_status': 'not_evaluated', 'layout_status': 'not_evaluated'}
