"""Offline reuse of the historical English Stage 3 text-only receipt profile.

This is neither the modern provider envelope nor checkpoint resume. Historical
requests, settled costs and original strings remain independently identifiable.
Current preferences are recovery-time inputs, never invented past instructions.
No provider, credential, ledger constructor or native application is invoked.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from .acceptance_assembly import _directory
from .acceptance_recovery import PinnedJSON
from .acceptance_review import _visible, apply_reviewed_edits
from .document_structure import validate_page_structure
from .formatting_support import digest_text, fingerprint
from .glossary import normalize_enabled_tiers_by_target_lang, normalize_glossaries
from .new_translation_blocks import validate_block
from .structured_artifacts import (
    StructuredArtifactError, _decode, _hash_value, _json, publish_structured_page,
)
from .structured_glossary import build_structured_glossary
from .translation_structure import parse_structured_translation
from .types import TargetLang

VERSION = 'legal_blocks_legacy_reviewed_recovery_v1'
REMAP_VERSION = 'legacy_stage3_line_remap_v1'
# Known historical profiles, not today's prompt or caller-selected digests.
_INSTRUCTIONS_SHA256 = '046d1f4a62ac63c7fb079dc4b4dd7cbbe92db4c700416cc490533bdad870f052'
_REVIEW_INSTRUCTIONS_SHA256 = '9bbffd838c27435423a62234e73c31e76f1e95614b2e08e093e8b312c52fc1f4'
_REVIEW_PREFIX_SHA256 = '2c69afe41f5d09983a5c34f5e40c3e0822100ac5a766d06382808c6dd2061e73'
_PIN_NAMES = ('job', 'result', 'assessment', 'review_job', 'review_result',
              'ledger', 'benchmark_manifest', 'preferences')


class LegacyRecoveryError(StructuredArtifactError):
    """Content-free diagnostic; original evidence is never repaired in place."""


def _require(condition, code='legacy_recovery_invalid_evidence'):
    if not condition:
        raise LegacyRecoveryError(code)


def _review_projection(source_text, target_text):
    # Review offsets use the shared visible projection. This historical English
    # profile admits only identity-projected strings, so the line checks below
    # refer to exactly the same characters as the reviewed ranges.
    _require(_visible(source_text) == source_text and _visible(target_text) == target_text,
             'legacy_recovery_review_projection_not_identity')


def legacy_recovery_binding(*, job, result, assessment, review_job, review_result,
        ledger, benchmark_manifest, preferences, legacy_sources,
        source_structure_sha256, validator_binding, lang) -> dict:
    """Pins for an independently authored remap, not an execution authorization."""
    selected = locals()
    _require(lang is TargetLang.EN, 'legacy_recovery_profile_not_supported')
    _require(_hash_value(source_structure_sha256) and _hash_value(validator_binding))
    _require(type(legacy_sources) in (tuple, list) and 1 <= len(legacy_sources) <= 10000)
    _require(all(type(pin) is PinnedJSON and _hash_value(pin.sha256)
                 for pin in [*(selected[name] for name in _PIN_NAMES), *legacy_sources]))
    return {**{name + '_sha256': selected[name].sha256 for name in _PIN_NAMES},
        'legacy_sources_sha256': [pin.sha256 for pin in legacy_sources],
        'source_structure_sha256': source_structure_sha256,
        'validator_binding': validator_binding, 'target_lang': lang.value}


def _signed(value):
    _require(type(value) is dict and _hash_value(value.get('fingerprint'))
        and fingerprint({k: v for k, v in value.items() if k != 'fingerprint'}) == value['fingerprint'],
        'legacy_recovery_fingerprint_mismatch')


def _decimal(value):
    try:
        result = Decimal(str(value))
        _require(result.is_finite() and result >= 0)
        return result
    except (InvalidOperation, ValueError):
        raise LegacyRecoveryError('legacy_recovery_invalid_cost') from None


def _output_directory(path):
    _directory(path.parent)
    try:
        path.lstat()
    except FileNotFoundError:
        return
    _directory(path)  # Includes broken links/junctions; never follow a redirect.


def _evidence_files(job, pins):
    files = job.get('evidence_files')
    _require(type(files) is list and len(files) == len(pins))
    for row, pin in zip(files, pins):
        _require(type(row) is dict and set(row) == {'path', 'sha256'}
            and isinstance(row['path'], str) and Path(row['path']) == Path(pin.path)
            and row['sha256'] == pin.sha256, 'legacy_recovery_source_file_binding')


def _translation_rows(raw, source_rows):
    _require(isinstance(raw, str), 'legacy_recovery_invalid_response')
    if raw.startswith('```'):
        _require(raw.startswith('```json\n') and raw.endswith('\n```'), 'legacy_recovery_invalid_fence')
        raw = raw[8:-4]
    data = _decode(raw.encode('utf-8'))
    _require(type(data) is dict and set(data) == {'blocks'} and type(data['blocks']) is list)
    rows = data['blocks']
    _require(len(rows) == len(source_rows))
    for row, source in zip(rows, source_rows):
        _require(type(row) is dict and set(row) == {'id', 'text'} and row['id'] == source['id']
            and isinstance(row['text'], str) and row['text'].strip()
            and '\n' not in row['text'] and '\r' not in row['text'], 'legacy_recovery_block_mismatch')
    _require(len({row['id'] for row in rows}) == len(rows), 'legacy_recovery_duplicate_block')
    return rows


def _settled(job, job_pin, result, ledger, manifest, source_hash, purpose):
    """Cross-check stored request, response and settlement without dispatch code."""
    _require(type(job) is dict and type(job.get('version')) is int and job['version'] == 1
        and job.get('purpose') == purpose and isinstance(job.get('instructions'), str)
        and isinstance(job.get('input_text'), str))
    _require(type(result) is dict and set(result) == {
        'version', 'job_sha256', 'raw_output', 'usage_record', 'evidence', 'status'}
        and type(result['version']) is int and result['version'] == 1
        and result['job_sha256'] == job_pin.sha256 and result['status'] == 'completed'
        and isinstance(result['raw_output'], str))
    evidence, usage = result['evidence'], result['usage_record']
    _require(type(evidence) is dict and type(usage) is dict
        and evidence.get('dispatch_version') == 1 and evidence.get('usage_record') == usage
        and evidence.get('output_sha256') == digest_text(result['raw_output'])
        and type(evidence.get('output_chars')) is int and evidence['output_chars'] == len(result['raw_output'])
        and evidence.get('promotion_enabled') is False
        and all(evidence.get(key) is None for key in ('error_code', 'block_reason', 'status_code')))
    identifier = evidence.get('reservation_id')
    _require(isinstance(identifier, str) and identifier in ledger['reservations'])
    row = ledger['reservations'][identifier]
    _require(type(row) is dict and row.get('status') == 'finalized' and row.get('purpose') == purpose)
    execution = row.get('execution')
    _require(type(execution) is dict and row.get('evidence') == {
        k: v for k, v in evidence.items() if k != 'ledger_status'})
    _require(evidence.get('ledger_status') == {'reservation_id': identifier, 'status': 'finalized',
        'actual_usd': row.get('actual_usd'), 'blocked_reason': None})
    _require(all(execution.get(key) == job.get(key) for key in ('candidate_id', 'case_id', 'page_number', 'purpose'))
        and execution.get('source_file_sha256') == source_hash
        and execution.get('manifest_fingerprint') == manifest['fingerprint']
        and execution.get('promotion_enabled') is False
        and type(execution.get('max_attempts')) is int and execution['max_attempts'] == 1
        and execution.get('timeout_seconds') == job.get('timeout_seconds'))
    model, effort, limit = (execution.get(key) for key in ('model', 'effort', 'max_output_tokens'))
    _require(model == 'gpt-5.6-terra' and effort == 'high'
        and type(limit) is int and 0 < limit <= 24000
        and (job.get('max_output_tokens') is None or job['max_output_tokens'] == limit))
    request = dict(model=model, effort=effort, instructions=job['instructions'], input_text=job['input_text'],
                   max_output_tokens=limit, service_tier='default', store=False)
    request_hash = fingerprint(request)
    _require(execution.get('request_fingerprint') == evidence.get('request_fingerprint') == request_hash,
        'legacy_recovery_request_mismatch')
    _require(usage.get('provider') == 'openai' and usage.get('status') == 'completed'
        and usage.get('requested_model') == usage.get('model') == model and usage.get('effort') == effort
        and usage.get('purpose') == purpose and usage.get('call_id') == 'benchmark:' + identifier
        and type(usage.get('attempt')) is int and usage['attempt'] == 1
        and usage.get('cost_status') == usage.get('usage_status') == 'available'
        and isinstance(usage.get('response_id'), str) and usage['response_id'])
    tokens = usage.get('usage')
    keys = ('input_tokens', 'output_tokens', 'total_tokens', 'reasoning_tokens',
            'cached_input_tokens', 'cache_write_tokens')
    _require(type(tokens) is dict and all(type(tokens.get(key)) is int and tokens[key] >= 0 for key in keys)
        and tokens.get('usage_missing') is False and tokens.get('usage_status') == 'available'
        and tokens['input_tokens'] + tokens['output_tokens'] == tokens['total_tokens']
        and tokens['reasoning_tokens'] <= tokens['output_tokens'] <= limit
        and tokens['cached_input_tokens'] + tokens['cache_write_tokens'] <= tokens['input_tokens'])
    rates = execution.get('pricing')
    _require(type(rates) is dict)
    # Historical rates are evidence, not a current pricing decision. Reasoning
    # is included in output; it is deliberately never charged a second time.
    cost = sum(_decimal(rates.get(rate)) * count for rate, count in (
        ('input_per_1m', tokens['input_tokens'] - tokens['cached_input_tokens'] - tokens['cache_write_tokens']),
        ('cached_input_per_1m', tokens['cached_input_tokens']),
        ('cache_write_per_1m', tokens['cache_write_tokens']), ('output_per_1m', tokens['output_tokens']))) / 1000000
    _require(cost == _decimal(usage.get('cost_usd')) == _decimal(row.get('actual_usd'))
        and cost <= _decimal(row.get('reserved_usd')), 'legacy_recovery_settlement_mismatch')
    # This old profile did not retain the effective tier; do not guess one.
    _require(all('service_tier' not in item for item in (result, evidence, usage, execution)),
        'legacy_recovery_unrecognized_tier_evidence')
    return {'reservation_id': identifier, 'request_sha256': request_hash,
            'historical_cost_usd': str(cost), 'usage_record': deepcopy(usage)}


def recover_legacy_stage3_page(*, job: PinnedJSON, result: PinnedJSON,
        assessment: PinnedJSON, review_job: PinnedJSON, review_result: PinnedJSON,
        ledger: PinnedJSON, benchmark_manifest: PinnedJSON, legacy_sources,
        preferences: PinnedJSON, source_structure, source_structure_sha256: str,
        source_guard, validator_binding: str, lang: TargetLang, pages_dir: Path,
        remapping_manifest: PinnedJSON, review_manifest: PinnedJSON | None = None) -> dict:
    """Recover exact old text, optionally apply a separately pinned AI review.

The physical source-evidence guard remains caller-owned and must recheck all
current source-review dependencies. Pin checks are not a signed trust root.
Outputs retain review requirements and cannot authorize paid resume/promotion.
"""
    args = locals()
    binding = legacy_recovery_binding(**{key: value for key, value in args.items() if key in {
        *_PIN_NAMES, 'legacy_sources', 'source_structure_sha256', 'validator_binding', 'lang'}})
    _require(callable(source_guard) and type(remapping_manifest) is PinnedJSON,
        'legacy_recovery_source_guard_required')
    _require(review_manifest is None or type(review_manifest) is PinnedJSON)
    pins = [*(args[name] for name in _PIN_NAMES), *legacy_sources, remapping_manifest]
    if review_manifest is not None:
        pins.append(review_manifest)
    pages_dir = Path(pages_dir)
    _require(pages_dir.is_absolute() and '..' not in pages_dir.parts)
    _output_directory(pages_dir)
    for pin in pins:
        _directory(Path(pin.path).parent)
        _require(not Path(pin.path).is_relative_to(pages_dir), 'legacy_recovery_output_overlaps_evidence')
    source = validate_page_structure(deepcopy(source_structure))
    _require(source.fingerprint == source_structure_sha256 and len(source.blocks) == 1
        and source.translation_sha256 is None, 'legacy_recovery_source_mismatch')

    def guard():
        source_guard()
        _output_directory(pages_dir)
        _require(validate_page_structure(source_structure).fingerprint == source_structure_sha256,
                 'legacy_recovery_source_changed')
        for pin in pins:
            _directory(Path(pin.path).parent)
            pin.read()

    guard()
    try:
        return _recover(args, binding, source, guard)
    except (KeyError, TypeError, AttributeError, IndexError, UnicodeError):
        raise LegacyRecoveryError('legacy_recovery_invalid_schema') from None


def _recover(args, binding, source, guard):
    values = {name: args[name].read() for name in _PIN_NAMES}
    job, paid, assessment, rjob, reviewed, ledger, manifest, prefs = (values[name] for name in _PIN_NAMES)
    _signed(manifest)
    _signed(ledger)
    _require(manifest.get('schema_version') == ledger.get('schema_version') == 1
        and ledger.get('benchmark_id') == manifest.get('benchmark_id')
        and ledger.get('manifest_fingerprint') == manifest['fingerprint']
        and Path(ledger['manifest_path']) == Path(args['benchmark_manifest'].path)
        and manifest.get('budget_cap_usd') == ledger.get('cap_usd') == '10'
        and type(ledger.get('reservations')) is dict)
    cases = [row for row in manifest['cases'] if row.get('case_id') == job.get('case_id')]
    _require(len(cases) == 1)
    case = cases[0]
    _signed(case)
    total = case['source']['page_count']
    _require(case.get('language') == 'EN' and case.get('source_language') == 'PT'
        and type(total) is int and total == len(args['legacy_sources'])
        and case['source']['sha256'] == source.source_file_sha256)
    old_sources = [pin.read() for pin in args['legacy_sources']]
    all_rows = []
    for n, page in enumerate(old_sources, 1):
        _require(page.get('page_number') == n and page.get('source_file_sha256') == source.source_file_sha256)
        rows = [{'id': block['id'], 'text': block['text']} for block in page['blocks']]
        # Only the page being remapped has one legacy row per output line.
        # Neighboring source blocks are exact context and may contain LF.
        _require(rows and len({row['id'] for row in rows}) == len(rows)
            and all(isinstance(row['id'], str) and re.fullmatch(fr'p{n:04d}_b[0-9]{{4,}}', row['id'])
                    and isinstance(row['text'], str) and row['text'].strip()
                    and (n != source.page_number or '\n' not in row['text'])
                    and '\r' not in row['text'] for row in rows), 'legacy_recovery_source_row_shape')
        _require(page['source_sha256'] == page['source_text_sha256'] == digest_text('\n'.join(r['text'] for r in rows)))
        all_rows.append(rows)
    number = source.page_number
    _require(1 <= number <= total and type(job.get('page_number')) is int and job['page_number'] == number)
    source_rows = all_rows[number - 1]
    _evidence_files(job, args['legacy_sources'])
    _evidence_files(rjob, [*args['legacy_sources'], args['result']])
    _require(all(job.get(key) == rjob.get(key) for key in ('candidate_id', 'case_id', 'page_number')))
    _require(digest_text(job['instructions']) == _INSTRUCTIONS_SHA256
        and digest_text(rjob['instructions']) == _REVIEW_INSTRUCTIONS_SHA256,
        'legacy_recovery_instructions_mismatch')
    primary = _settled(job, args['job'], paid, ledger, manifest, source.source_file_sha256, 'translation')
    review = _settled(rjob, args['review_job'], reviewed, ledger, manifest, source.source_file_sha256, 'fidelity_review')
    translated = _translation_rows(paid['raw_output'], source_rows)
    _require(assessment.get('version') == 1 and assessment.get('format_ok') is True
        and assessment.get('format_reason') is None and assessment.get('translated_blocks') == translated
        and all(assessment.get(key) == job[key] for key in ('candidate_id', 'case_id', 'page_number'))
        and assessment.get('source_file_sha256') == source.source_file_sha256
        and assessment.get('source_text_sha256') == old_sources[number - 1]['source_sha256']
        and Path(assessment['result_file']) == Path(args['result'].path)
        and Path(assessment['request_file']) == Path(args['job'].path), 'legacy_recovery_assessment_mismatch')
    prefix, sep, pairs_text = rjob['input_text'].partition('\n')
    _require(sep and digest_text(prefix + sep) == _REVIEW_PREFIX_SHA256
        and _decode(pairs_text.encode('utf-8')) == {'source': source_rows, 'translation': translated},
        'legacy_recovery_review_pairs_mismatch')
    _require(_decode(reviewed['raw_output'].encode('utf-8')) == {'findings': []},
        'legacy_recovery_historical_findings_require_review')
    mapping = args['remapping_manifest'].read()
    _require(type(mapping) is dict and set(mapping) == {'version', 'binding', 'parent_id', 'lines',
        'previous_context_block_id', 'next_context_block_id', 'source_text_sha256', 'target_text_sha256'}
        and mapping['version'] == REMAP_VERSION and mapping['binding'] == binding
        and mapping['parent_id'] == source.blocks[0].id, 'legacy_recovery_remapping_binding')
    contexts = {}
    for key, neighbor, slot in (('previous_context_block_id', number - 2, 'previous_tail'),
                                ('next_context_block_id', number, 'next_head')):
        context_id = mapping[key]
        if context_id is None:
            contexts[slot] = ''
        else:
            _require(isinstance(context_id, str) and 0 <= neighbor < total)
            matches = [row['text'] for row in all_rows[neighbor] if row['id'] == context_id]
            _require(len(matches) == 1, 'legacy_recovery_context_mismatch')
            contexts[slot] = matches[0]
    # No trailing glossary/addendum is admitted by this historical profile.
    _require(_decode(job['input_text'].encode('utf-8')) == {'page': number, 'total_pages': total,
        'blocks': source_rows, 'context_only_not_to_translate': contexts}, 'legacy_recovery_prompt_mismatch')
    source_lines, target_lines, selected = [], [], []
    target_by_id = {row['id']: row['text'] for row in translated}
    source_by_id = {row['id']: row['text'] for row in source_rows}
    lines = mapping['lines']
    _require(type(lines) is list and 1 <= len(lines) <= 10000)
    folio_count = 0
    for index, row in enumerate(lines):
        _require(type(row) is dict)
        if set(row) == {'legacy_id'}:
            identifier = row['legacy_id']
            _require(isinstance(identifier, str) and identifier in source_by_id)
            selected.append(identifier)
            source_lines.append(source_by_id[identifier])
            target_lines.append(target_by_id[identifier])
        else:
            _require(set(row) == {'source_literal'} and isinstance(row['source_literal'], str))
            literal = row['source_literal']
            if literal != '':
                folio = old_sources[number - 1]['metadata']['source_page_label']
                _require(index == len(lines) - 1 and re.fullmatch(r'[0-9]+ */ *[0-9]+', literal)
                    and re.sub(' ', '', literal) == folio['text'] == f'{number}/{total}'
                    and folio['source_page'] == number and folio['source_total_pages'] == total,
                    'legacy_recovery_unanchored_insertion')
                folio_count += 1
            source_lines.append(literal)
            target_lines.append(literal)
    source_text, remapped_text = '\n'.join(source_lines), '\n'.join(target_lines)
    _require(selected == [row['id'] for row in source_rows] and folio_count <= 1
        and source_text == source.blocks[0].text and mapping['source_text_sha256'] == digest_text(source_text)
        and mapping['target_text_sha256'] == digest_text(remapped_text), 'legacy_recovery_remapping_mismatch')
    rows = [{'id': source.blocks[0].id, 'text': source_text}]
    target_rows = [{'id': source.blocks[0].id, 'text': remapped_text}]
    explicit_review = None
    if args['review_manifest'] is not None:
        _review_projection(source_text, remapped_text)
        current_review = args['review_manifest'].read()
        target_rows, explicit_review = apply_reviewed_edits(current_review, rows, target_rows,
            expected_binding={'legacy_remapping_manifest_sha256': args['remapping_manifest'].sha256,
                'legacy_result_sha256': args['result'].sha256, 'preferences_sha256': args['preferences'].sha256,
                'source_structure_sha256': source.fingerprint, 'target_lang': 'EN'})
        for edit in current_review['edits']:
            ss, se, ts, te = (edit[key] for key in ('source_start', 'source_end', 'target_start', 'target_end'))
            _require('\n' not in source_text[ss:se] and '\n' not in remapped_text[ts:te]
                and '\n' not in edit['after']
                and source_text.count('\n', 0, ss) == remapped_text.count('\n', 0, ts),
                'legacy_recovery_review_line_association')
        explicit_review['manifest_file_sha256'] = args['review_manifest'].sha256
    parsed = parse_structured_translation(_json({'blocks': target_rows}).decode('utf-8'), rows,
        page_number=number, response_status='completed', refused=False)
    _require(parsed == target_rows, 'legacy_recovery_parser_changed_text')
    entries = normalize_glossaries(prefs.get('personal_glossaries_by_lang', prefs.get('glossaries_by_lang')), ['EN'])['EN']
    tiers = normalize_enabled_tiers_by_target_lang(prefs.get('enabled_glossary_tiers_by_target_lang'), ['EN'])['EN']
    glossary = build_structured_glossary(rows, entries, target_lang='EN', enabled_tiers=tiers)
    review_codes = {'legal_fidelity_not_evaluated', 'current_preference_compatibility_requires_review'}
    text = target_rows[0]['text']
    final_lines = text.split('\n')
    _require(len(final_lines) == len(source_lines) and all((left == '') == (right == '')
        for left, right in zip(source_lines, final_lines)), 'legacy_recovery_review_changed_line_partition')
    # The ordinary normalizer removes blank lines. They are explicit, reviewed
    # source spacing here, not model strings to rewrite. Validate a blank-only
    # projection and each associated line, preserving every published character.
    # No trimming, list merging, date repair or other change is silently adopted.
    compact = '\n'.join(line for line in final_lines if line != '')
    normalized = validate_block(rows[0], compact, TargetLang.EN, glossary.for_block(rows[0]['id']), review_codes)
    _require(normalized == compact, 'legacy_recovery_normalization_changed_text')
    for left, right in zip(source_lines, final_lines):
        checked = validate_block({'id': rows[0]['id'], 'text': left}, right,
            TargetLang.EN, glossary.for_block(rows[0]['id']), review_codes)
        _require(checked == right, 'legacy_recovery_normalization_changed_text')
    provenance = dict(version=VERSION, lang='EN', historical_model='gpt-5.6-terra', historical_effort='high',
        historical_identity={'case_id': job['case_id'], 'candidate_id': job['candidate_id'],
            'page_number': number, 'full_case_pages': list(range(1, total + 1))},
        binding=binding, source_structure_sha256=source.fingerprint,
        preferences_sha256=args['preferences'].sha256, preferences_role='recovery_time_only',
        historical_current_preferences_applied=False, historical_glossary_suffix_present=False,
        current_prompt_acceptance='not_evaluated', requested_service_tier='default', reported_service_tier=None,
        historical_translation=primary, historical_review=review,
        remapping_manifest_sha256=args['remapping_manifest'].sha256,
        remapped_target_sha256=digest_text(remapped_text), legacy_target_strings_preserved=explicit_review is None,
        validation_projection='remove_exact_source_bound_empty_lines_only_v1',
        recovery_provider_dispatch_count=0, recovery_cost_usd='0', workflow_resumed=False, full_case_complete=False,
        fidelity_status='not_evaluated', layout_status='not_evaluated', human_certified=False,
        review_codes=sorted(review_codes), glossary_fingerprint=glossary.fingerprint)
    if explicit_review is not None:
        provenance['explicit_ai_review'] = explicit_review
    identity = {'protocol': VERSION, 'fingerprint': fingerprint(provenance)}
    page_fingerprint = fingerprint({'recovery': identity, 'page': number})
    target = source.to_dict()
    target['blocks'][0]['text'] = text
    target['translation_sha256'] = digest_text(text)
    target['metadata'].update(recovery=provenance, protocol=VERSION, translation_fingerprint=page_fingerprint,
        review={'fidelity_status': 'not_evaluated', 'manual_review_required': True})
    guard()
    commit = publish_structured_page(args['pages_dir'], source_structure=source, translated_structure=target,
        translated_text=text, protocol_identity=identity, page_fingerprint=page_fingerprint,
        evidence_guard=guard, page_result=None)
    guard()
    return {'commit': commit, 'provenance': provenance}
