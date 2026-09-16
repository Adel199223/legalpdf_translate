"""Synthetic explicit review edits; never retained private provider content."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from legalpdf_translate import acceptance_recovery as recovery
from legalpdf_translate.acceptance_continuation import AcceptanceContinuation, AcceptancePageJournal
from legalpdf_translate.acceptance_review import (
    AcceptanceReviewError, REVIEW_VERSION, REVIEWED_RECOVERY_VERSION,
    VISIBLE_PROJECTION_VERSION, apply_reviewed_edits,
)
from legalpdf_translate.document_structure import PageStructure, StructureBlock
from legalpdf_translate.formatting_support import digest_text, fingerprint
from legalpdf_translate.structured_arabic_literals import _view
from legalpdf_translate.translation_structure import build_structured_page_prompt, structured_system_instructions
from legalpdf_translate.types import TargetLang
from tests.test_acceptance_recovery import pin


@pytest.fixture
def reviewed(tmp_path):
    texts = ['Data: d.s.', 'Montante: 150.']
    source = PageStructure(page_number=3, source_sha256=digest_text('\n'.join(texts)),
        source_text_sha256=digest_text('\n'.join(texts)), source_file_sha256='a' * 64,
        blocks=[StructureBlock(f'p0003_b{index:04d}', text) for index, text in enumerate(texts, 1)])
    rows = [{'id': block.id, 'text': block.text} for block in source.blocks]
    targets = [{'id': rows[0]['id'], 'text': 'التاريخ: d.s.'},
               {'id': rows[1]['id'], 'text': 'المبلغ: [[150]].'}]
    request = {'instructions': structured_system_instructions(TargetLang.AR),
        'prompt_text': build_structured_page_prompt(source_blocks=rows, page_number=3, total_pages=9), 'effort': 'high'}
    old = tmp_path / 'old'
    old.mkdir()
    journal = AcceptancePageJournal(old,
        policy=AcceptanceContinuation('b' * 64, tuple(range(1, 10)), (3,), lambda _: 'c' * 64),
        protocol_identity={'protocol': 'legal_blocks_v2', 'fingerprint': 'd' * 64},
        page_number=3, page_fingerprint='e' * 64)
    journal.begin(1, request, 'c' * 64)
    journal.save_response(1, result=SimpleNamespace(raw_output=json.dumps({'blocks': targets}),
        response_status='completed', refused=False, usage={'input_tokens': 30, 'output_tokens': 20},
        model='historical-model', effort='high'), usage={'attempt_1': {'input_tokens': 30, 'output_tokens': 20}},
        metadata={'api_calls_count': 1})
    prefs = tmp_path / 'preferences.json'
    prefs.write_text('{}', encoding='utf-8')
    args = dict(intent=pin(journal._path('primary.intent')), response=pin(journal._path('primary.response')),
        preferences=pin(prefs), historical_identity=journal.identity, request_sha256=fingerprint(request),
        source_structure=source, source_structure_sha256=source.fingerprint, source_guard=lambda: None,
        validator_binding='f' * 64, lang=TargetLang.AR, pages_dir=tmp_path / 'pages')
    binding = {'intent_sha256': args['intent'].sha256, 'response_sha256': args['response'].sha256,
        'preferences_sha256': args['preferences'].sha256, 'source_structure_sha256': source.fingerprint,
        'historical_identity_sha256': fingerprint(journal.identity), 'target_lang': 'AR'}
    manifest = {'version': REVIEW_VERSION, 'text_projection': VISIBLE_PROJECTION_VERSION,
        'reviewer_kind': 'codex_ai_test_review', 'binding': binding,
        'edits': [edit(rows[0], targets[0], 'd.s.', 'd.s.', 'التاريخ أعلاه')]}
    return args, manifest, rows, targets, tmp_path / 'review.json'


def edit(source, target, quote, before, after, *, target_start=None):
    left, right = _view(source['text'])[0], _view(target['text'])[0]
    start = right.index(before) if target_start is None else target_start
    return {'block_id': source['id'], 'source_text_sha256': digest_text(source['text']),
        'target_text_sha256': digest_text(target['text']), 'source_visible_sha256': digest_text(left),
        'target_visible_sha256': digest_text(right), 'source_start': left.index(quote),
        'source_end': left.index(quote) + len(quote), 'source_text': quote,
        'target_start': start, 'target_end': start + len(before), 'before': before, 'after': after,
        'reason_code': 'untranslated_source_abbreviation'}


def save_review(reviewed):
    args, manifest, _sources, _targets, path = reviewed
    path.write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    return {**args, 'review_manifest': pin(path)}


def test_reviewed_derivative_is_distinct_and_preserves_originals(reviewed):
    args = save_review(reviewed)
    originals = {key: args[key].path.read_bytes() for key in ('intent', 'response', 'preferences', 'review_manifest')}
    with pytest.raises(ValueError):
        recovery.recover_saved_page(**reviewed[0])
    result = recovery.recover_reviewed_page(**args)
    assert result['commit']['protocol_identity']['protocol'] == REVIEWED_RECOVERY_VERSION
    assert result['commit']['page_result'] is None
    provenance = result['provenance']
    assert provenance['visible_translation_unchanged'] is False
    assert provenance['recovery_provider_dispatch_count'] == 0 and provenance['recovery_cost_usd'] == '0'
    assert provenance['workflow_resumed'] is False and provenance['full_case_complete'] is False
    assert provenance['historical_usage'] == {'attempt_1': {'input_tokens': 30, 'output_tokens': 20}}
    assert provenance['explicit_ai_review']['manifest_file_sha256'] == args['review_manifest'].sha256
    assert provenance['explicit_ai_review']['human_certified'] is False
    visible = _view((args['pages_dir'] / 'page_0003.txt').read_text(encoding='utf-8'))[0]
    assert visible == 'التاريخ: التاريخ أعلاه\nالمبلغ: 150.'
    for key, before in originals.items():
        assert args[key].path.read_bytes() == before
    assert recovery.recover_reviewed_page(**args) == result


@pytest.mark.parametrize('field', ['intent_sha256', 'response_sha256', 'preferences_sha256',
    'source_structure_sha256', 'historical_identity_sha256', 'target_lang'])
def test_wrong_binding_rejected_before_publication(reviewed, field):
    reviewed[1]['binding'][field] = 'EN' if field == 'target_lang' else '0' * 64
    with pytest.raises(AcceptanceReviewError, match='review_evidence_binding_mismatch'):
        recovery.recover_reviewed_page(**save_review(reviewed))
    assert not reviewed[0]['pages_dir'].exists()


@pytest.mark.parametrize('field,value', [
    ('source_visible_sha256', '0' * 64), ('target_visible_sha256', '0' * 64),
    ('source_text_sha256', '0' * 64), ('target_text_sha256', '0' * 64),
    ('source_start', -1), ('source_end', 1000000), ('target_start', True), ('target_end', 1000000),
    ('source_text', 'different'), ('before', 'different'), ('after', ''), ('after', 'd.s.'),
    ('after', '[[text]]'), ('after', '\u2066text'), ('after', 'p0003_b0002'),
])
def test_invalid_edit_rejected(reviewed, field, value):
    reviewed[1]['edits'][0][field] = value
    with pytest.raises(AcceptanceReviewError):
        recovery.recover_reviewed_page(**save_review(reviewed))
    assert not reviewed[0]['pages_dir'].exists()


@pytest.mark.parametrize('field,value', [('reviewer_kind', 'human_certified'), ('version', 'v0'),
                                       ('text_projection', 'raw_bytes'), ('edits', [])])
def test_unbound_review_semantics_rejected(reviewed, field, value):
    reviewed[1][field] = value
    with pytest.raises(AcceptanceReviewError):
        recovery.recover_reviewed_page(**save_review(reviewed))


def test_overlap_and_noncanonical_order_rejected(reviewed):
    _args, manifest, source, target, _ = reviewed
    first = manifest['edits'][0]
    manifest['edits'].append(deepcopy(first))
    with pytest.raises(AcceptanceReviewError, match='overlapping_review_edits'):
        apply_reviewed_edits(manifest, source, target, expected_binding=manifest['binding'])
    manifest['edits'] = [edit(source[1], target[1], '150', '150', '151'), first]
    with pytest.raises(AcceptanceReviewError, match='noncanonical_review_edit_order'):
        apply_reviewed_edits(manifest, source, target, expected_binding=manifest['binding'])


def test_review_does_not_exempt_changed_protected_number(reviewed):
    _args, manifest, source, target, _ = reviewed
    manifest['edits'].append(edit(source[1], target[1], '150', '150', '151'))
    with pytest.raises(ValueError):
        recovery.recover_reviewed_page(**save_review(reviewed))
    assert not reviewed[0]['pages_dir'].exists()


def test_repeated_before_text_selects_only_exact_original_occurrence(reviewed):
    _args, manifest, source, target, _ = reviewed
    target[0]['text'] += ' d.s.'
    start = target[0]['text'].rindex('d.s.')
    manifest['edits'] = [edit(source[0], target[0], 'd.s.', 'd.s.', 'التاريخ أعلاه', target_start=start)]
    changed, _ = apply_reviewed_edits(manifest, source, target, expected_binding=manifest['binding'])
    assert changed[0]['text'] == 'التاريخ: d.s. التاريخ أعلاه'


def test_review_is_rechecked_during_publication(reviewed, monkeypatch):
    args = save_review(reviewed)
    publish = recovery.publish_structured_page
    def mutate(*pos, **kw):
        args['review_manifest'].path.write_text('{}', encoding='utf-8')
        return publish(*pos, **kw)
    monkeypatch.setattr(recovery, 'publish_structured_page', mutate)
    with pytest.raises(ValueError, match='recovery_evidence_changed'):
        recovery.recover_reviewed_page(**args)
    assert not (args['pages_dir'] / 'page_0003.commit.json').exists()


def test_normalizer_must_not_change_other_visible_text(reviewed, monkeypatch):
    args = save_review(reviewed)
    validate = recovery.validate_block
    monkeypatch.setattr(recovery, 'validate_block', lambda *a, **kw: validate(*a, **kw) + ' إضافة')
    with pytest.raises(ValueError, match='recovery_changed_visible_translation'):
        recovery.recover_reviewed_page(**args)
    assert not args['pages_dir'].exists()


def test_malformed_original_wrappers_cannot_be_hidden_by_review_projection(reviewed):
    _args, manifest, source, target, _ = reviewed
    target[1]['text'] += '[['
    with pytest.raises(AcceptanceReviewError, match='invalid_review_original_text'):
        apply_reviewed_edits(manifest, source, target, expected_binding=manifest['binding'])


def test_reviewed_name_change_still_fails_normal_literal_validator(reviewed):
    from legalpdf_translate.new_translation_blocks import validate_block
    _args, manifest, _source, _target, _ = reviewed
    source = [{'id': 'p0003_b0001', 'text': 'Nome: Ana Matos'}]
    target = [{'id': source[0]['id'], 'text': 'الاسم: [[Ana Matos]]'}]
    manifest['edits'] = [edit(source[0], target[0], 'Ana Matos', 'Ana Matos', 'Ana Alves')]
    changed, _ = apply_reviewed_edits(manifest, source, target, expected_binding=manifest['binding'])
    with pytest.raises(ValueError):
        validate_block(source[0], changed[0]['text'], TargetLang.AR, None, set())


def test_parser_trimming_cannot_silently_change_reviewed_boundary_space(reviewed):
    _args, manifest, source, target, _ = reviewed
    manifest['edits'].insert(0, edit(source[0], target[0], 'Data', 'التاريخ:', ' التاريخ:'))
    with pytest.raises(ValueError, match='recovery_changed_reviewed_translation'):
        recovery.recover_reviewed_page(**save_review(reviewed))
    assert not reviewed[0]['pages_dir'].exists()


def test_reviewed_entry_requires_pinned_manifest(reviewed):
    with pytest.raises(ValueError, match='pinned_review_manifest_required'):
        recovery.recover_reviewed_page(**reviewed[0], review_manifest=None)


def test_multiple_length_changing_edits_use_original_offsets(reviewed):
    _args, manifest, source, target, _ = reviewed
    target[0]['text'] += ' d.s.'
    manifest['edits'] = [edit(source[0], target[0], 'd.s.', 'd.s.', value, target_start=start)
                        for value, start in [('التاريخ أعلاه', 9), ('في التاريخ أعلاه', 14)]]
    changed, _ = apply_reviewed_edits(manifest, source, target, expected_binding=manifest['binding'])
    assert changed[0]['text'] == 'التاريخ: التاريخ أعلاه في التاريخ أعلاه'
