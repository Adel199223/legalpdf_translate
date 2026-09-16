"""Synthetic legacy receipts only; no historical private text or executors."""
from copy import deepcopy
from dataclasses import replace
import json

import pytest

from legalpdf_translate import acceptance_legacy_recovery as legacy
from legalpdf_translate.acceptance_recovery import PinnedJSON
from legalpdf_translate.document_structure import PageStructure, StructureBlock
from legalpdf_translate.formatting_support import digest_text, fingerprint
from legalpdf_translate.structured_artifacts import StructuredArtifactError, validate_structured_page
from legalpdf_translate.types import TargetLang


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def write_pin(path, value):
    raw = encoded(value)
    path.write_bytes(raw)
    return PinnedJSON(path, digest_text(raw.decode()))


def signed(value):
    return {**value, 'fingerprint': fingerprint(value)}


@pytest.fixture
def case(tmp_path, monkeypatch, request):
    # Admit only synthetic instructions in synthetic tests. Real profile digests
    # remain literal constants in production, never derived from current prompts.
    monkeypatch.setattr(legacy, '_INSTRUCTIONS_SHA256', digest_text('Translate EN.'))
    monkeypatch.setattr(legacy, '_REVIEW_INSTRUCTIONS_SHA256', digest_text('Review EN.'))
    monkeypatch.setattr(legacy, '_REVIEW_PREFIX_SHA256', digest_text('Compare EN pairs.\n'))
    old = tmp_path / 'old'
    old.mkdir()
    source_rows = [{'id': 'p0002_b0001', 'text': 'Pedido admitido.'},
                   {'id': 'p0002_b0002', 'text': 'Data indicada.'}]
    target_rows = [{'id': source_rows[0]['id'], 'text': 'Request granted.'},
                   {'id': source_rows[1]['id'], 'text': 'Date indicated.'}]
    neighbor = getattr(request, 'param', 'Continuação')
    source1 = PageStructure(page_number=1, source_sha256=digest_text(neighbor),
        source_text_sha256=digest_text(neighbor), source_file_sha256='a' * 64,
        blocks=[StructureBlock('p0001_b0001', neighbor)]).to_dict()
    source2 = PageStructure(page_number=2, source_sha256=digest_text('Pedido admitido.\nData indicada.'),
        source_text_sha256=digest_text('Pedido admitido.\nData indicada.'), source_file_sha256='a' * 64,
        blocks=[StructureBlock(**row) for row in source_rows],
        metadata={'source_page_label': {'text': '2/2', 'source_page': 2, 'source_total_pages': 2}}).to_dict()
    pins = dict(legacy_sources=(write_pin(old / 'source1.json', source1), write_pin(old / 'source2.json', source2)))
    source_text = 'Pedido admitido.\n\nData indicada.\n2 / 2'
    source = PageStructure(page_number=2, source_sha256=digest_text(source_text),
        source_text_sha256=digest_text(source_text), source_file_sha256='a' * 64,
        uncertain=True, blocks=[StructureBlock('p0002_b100000001', source_text, uncertain=True)],
        metadata={'source_review': 'synthetic_current_review'})
    manifest = signed({'schema_version': 1, 'benchmark_id': 'synthetic', 'budget_cap_usd': '10',
        'cases': [signed({'case_id': 'en', 'language': 'EN', 'source_language': 'PT',
                         'source': {'sha256': 'a' * 64, 'page_count': 2}})]})
    pins['benchmark_manifest'] = write_pin(old / 'manifest.json', manifest)
    sources = [{'path': str(pin.path), 'sha256': pin.sha256} for pin in pins['legacy_sources']]
    job = dict(version=1, candidate_id='primary', case_id='en', page_number=2, purpose='translation',
        instructions='Translate EN.', input_text=encoded({'page': 2, 'total_pages': 2, 'blocks': source_rows,
            'context_only_not_to_translate': {'previous_tail': neighbor, 'next_head': ''}}).decode(),
        timeout_seconds=120, evidence_files=sources, prerequisites={'source_evidence_valid': True})
    pins['job'] = write_pin(old / 'job.json', job)
    reservations = {}

    def result_for(name, request, request_pin, raw, purpose, bound):
        request_sha = fingerprint(dict(model='gpt-5.6-terra', effort='high', instructions=request['instructions'],
            input_text=request['input_text'], max_output_tokens=bound, service_tier='default', store=False))
        usage = dict(accounting_version=2, call_id='benchmark:' + name, provider='openai',
            requested_model='gpt-5.6-terra', model='gpt-5.6-terra', effort='high', purpose=purpose,
            status='completed', attempt=1, cost_status='available', cost_usd=0.00014,
            usage_status='available', response_id='response_' + name,
            usage=dict(input_tokens=10, output_tokens=10, total_tokens=20, reasoning_tokens=2,
                cached_input_tokens=0, cache_write_tokens=0, usage_status='available', usage_missing=False))
        evidence = dict(dispatch_version=1, reservation_id=name, request_fingerprint=request_sha,
            usage_record=usage, output_sha256=digest_text(raw), output_chars=len(raw),
            status_code=None, error_code=None, block_reason=None, promotion_enabled=False)
        reservations[name] = dict(status='finalized', purpose=purpose, actual_usd='0.00014',
            reserved_usd='1', evidence=deepcopy(evidence), execution=dict(
                candidate_id='primary', case_id='en', page_number=2, purpose=purpose,
                model='gpt-5.6-terra', effort='high', max_output_tokens=bound, max_attempts=1,
                timeout_seconds=120, source_file_sha256='a' * 64, manifest_fingerprint=manifest['fingerprint'],
                request_fingerprint=request_sha, promotion_enabled=False,
                pricing=dict(input_per_1m=2, output_per_1m=12, cached_input_per_1m=0.2, cache_write_per_1m=2.5)))
        evidence['ledger_status'] = dict(reservation_id=name, status='finalized', actual_usd='0.00014', blocked_reason=None)
        return write_pin(old / (name + '.json'), dict(version=1, job_sha256=request_pin.sha256,
            raw_output=raw, usage_record=usage, evidence=evidence, status='completed'))

    raw = '```json\n' + encoded({'blocks': target_rows}).decode() + '\n```'
    pins['result'] = result_for('translation', job, pins['job'], raw, 'translation', 12000)
    assessment = dict(version=1, case_id='en', candidate_id='primary', page_number=2,
        source_file_sha256='a' * 64, source_text_sha256=source2['source_text_sha256'],
        format_ok=True, format_reason=None, translated_blocks=target_rows,
        result_file=str(pins['result'].path), request_file=str(pins['job'].path))
    pins['assessment'] = write_pin(old / 'assessment.json', assessment)
    review_job = {**job, 'purpose': 'fidelity_review', 'instructions': 'Review EN.',
        'input_text': 'Compare EN pairs.\n' + encoded({'source': source_rows, 'translation': target_rows}).decode(),
        'max_output_tokens': 1800, 'evidence_files': [*sources,
            {'path': str(pins['result'].path), 'sha256': pins['result'].sha256}]}
    pins['review_job'] = write_pin(old / 'review_job.json', review_job)
    pins['review_result'] = result_for('review', review_job, pins['review_job'], '{"findings":[]}', 'fidelity_review', 1800)
    ledger = signed(dict(schema_version=1, benchmark_id='synthetic', cap_usd='10',
        manifest_fingerprint=manifest['fingerprint'], manifest_path=str(pins['benchmark_manifest'].path),
        reservations=reservations))
    pins['ledger'] = write_pin(old / 'ledger.json', ledger)
    pins['preferences'] = write_pin(old / 'prefs.json', {})
    args = dict(**pins, source_structure=source, source_structure_sha256=source.fingerprint,
        source_guard=lambda: None, validator_binding='f' * 64, lang=TargetLang.EN, pages_dir=tmp_path / 'pages')
    mapping = dict(version=legacy.REMAP_VERSION, binding=legacy.legacy_recovery_binding(**{
        k: v for k, v in args.items() if k not in ('source_structure', 'source_guard', 'pages_dir')}),
        parent_id=source.blocks[0].id, previous_context_block_id='p0001_b0001', next_context_block_id=None,
        lines=[{'legacy_id': source_rows[0]['id']}, {'source_literal': ''},
               {'legacy_id': source_rows[1]['id']}, {'source_literal': '2 / 2'}],
        source_text_sha256=digest_text(source_text),
        target_text_sha256=digest_text('Request granted.\n\nDate indicated.\n2 / 2'))
    args['remapping_manifest'] = write_pin(old / 'remap.json', mapping)
    return args


def rewrite(case, key, change):
    value = case[key].read()
    change(value)
    if key in ('ledger', 'benchmark_manifest'):
        value['fingerprint'] = fingerprint({k: v for k, v in value.items() if k != 'fingerprint'})
    case[key] = write_pin(case[key].path, value)
    mapping = case['remapping_manifest'].read()
    if key != 'remapping_manifest':
        mapping['binding'][key + '_sha256'] = case[key].sha256
        case['remapping_manifest'] = write_pin(case['remapping_manifest'].path, mapping)


def test_exact_old_strings_remapped_current_source_and_tier_truth(case):
    before = {path: path.read_bytes() for path in case['job'].path.parent.iterdir()}
    result = legacy.recover_legacy_stage3_page(**case)
    assert result == legacy.recover_legacy_stage3_page(**case)
    text = (case['pages_dir'] / 'page_0002.txt').read_text(encoding='utf-8')
    assert text == 'Request granted.\n\nDate indicated.\n2 / 2'
    provenance = result['provenance']
    assert provenance['historical_model'] == 'gpt-5.6-terra'
    assert provenance['historical_effort'] == 'high'
    assert provenance['requested_service_tier'] == 'default'
    assert provenance['reported_service_tier'] is None
    assert provenance['historical_current_preferences_applied'] is False
    assert provenance['current_prompt_acceptance'] == 'not_evaluated'
    assert provenance['recovery_provider_dispatch_count'] == 0
    assert provenance['recovery_cost_usd'] == '0'
    assert provenance['fidelity_status'] == 'not_evaluated'
    assert provenance['layout_status'] == 'not_evaluated'
    assert provenance['workflow_resumed'] is False
    assert result['commit']['page_result'] is None
    target = json.loads((case['pages_dir'] / 'page_0002.structure.json').read_bytes())
    assert target['uncertain'] is True
    assert target['metadata']['source_review'] == 'synthetic_current_review'
    assert all(path.read_bytes() == raw for path, raw in before.items())


@pytest.mark.parametrize('case', ['Cabeçalho\nContinuação'], indirect=True)
def test_multiline_neighbor_context_preserved_without_rejecting_selected_page(case):
    before = {path: path.read_bytes() for path in case['job'].path.parent.iterdir()}
    result = legacy.recover_legacy_stage3_page(**case)
    assert result['provenance']['recovery_provider_dispatch_count'] == 0
    assert (case['pages_dir'] / 'page_0002.txt').read_text() == 'Request granted.\n\nDate indicated.\n2 / 2'
    assert all(path.read_bytes() == raw for path, raw in before.items())


def test_selected_page_multiline_legacy_row_still_rejected(case):
    page = case['legacy_sources'][1].read()
    page['blocks'][0]['text'] = 'Pedido\nadmitido.'
    page['source_sha256'] = page['source_text_sha256'] = digest_text('\n'.join(row['text'] for row in page['blocks']))
    new_pin = write_pin(case['legacy_sources'][1].path, page)
    case['legacy_sources'] = (case['legacy_sources'][0], new_pin)
    mapping = case['remapping_manifest'].read()
    mapping['binding']['legacy_sources_sha256'][1] = new_pin.sha256
    case['remapping_manifest'] = write_pin(case['remapping_manifest'].path, mapping)
    with pytest.raises(StructuredArtifactError, match='legacy_recovery_source_row_shape'):
        legacy.recover_legacy_stage3_page(**case)
    assert not case['pages_dir'].exists()


@pytest.mark.parametrize('key', ['job', 'result', 'assessment', 'review_job', 'review_result',
    'ledger', 'benchmark_manifest', 'preferences', 'remapping_manifest'])
@pytest.mark.parametrize('missing', [False, True])
def test_changed_missing_pin_never_publishes(case, key, missing):
    if missing:
        case[key].path.unlink()
    else:
        case[key].path.write_bytes(b'{"changed":true}')
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)
    assert not case['pages_dir'].exists()


@pytest.mark.parametrize('key,change', [
    ('job', lambda d: d.update(instructions='Another language')),
    ('result', lambda d: d.update(job_sha256='0' * 64)),
    ('result', lambda d: d.update(status='incomplete')),
    ('result', lambda d: d['evidence'].update(output_sha256='0' * 64)),
    ('result', lambda d: d['usage_record'].update(model='gpt-5.6-sol')),
    ('assessment', lambda d: d.update(source_file_sha256='0' * 64)),
    ('assessment', lambda d: d['translated_blocks'].reverse()),
    ('assessment', lambda d: d['translated_blocks'][0].update(text='Denied.')),
    ('review_job', lambda d: d.update(input_text=d['input_text'].replace('granted', 'denied'))),
    ('review_result', lambda d: d['evidence'].update(block_reason='failed')),
    ('ledger', lambda d: d['reservations']['translation'].update(status='uncertain')),
    ('ledger', lambda d: d['reservations']['translation'].update(actual_usd='0')),
    ('ledger', lambda d: d['reservations']['translation']['execution'].update(max_output_tokens=14000)),
    ('ledger', lambda d: d['reservations']['translation']['execution'].update(effort='xhigh')),
    ('ledger', lambda d: d['reservations']['translation']['execution'].update(case_id='wrong')),
    ('ledger', lambda d: d.update(cap_usd='20')),
    ('benchmark_manifest', lambda d: d['cases'][0].update(language='FR')),
    ('remapping_manifest', lambda d: d['lines'].reverse()),
    ('remapping_manifest', lambda d: d['lines'][1].update(source_literal='Invented')),
    ('remapping_manifest', lambda d: d['lines'][-1].update(source_literal='3 / 2')),
    ('remapping_manifest', lambda d: d.update(parent_id='p0002_b0001')),
    ('remapping_manifest', lambda d: d.update(previous_context_block_id='p0001_b9999')),
    ('remapping_manifest', lambda d: d.update(target_text_sha256='0' * 64)),
])
def test_rebound_but_inconsistent_historical_evidence_rejected(case, key, change):
    rewrite(case, key, change)
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)
    assert not case['pages_dir'].exists()


@pytest.mark.parametrize('raw', ['prefix\n```json\n{}\n```', '```JSON\n{}\n```',
    '```json\n{}\n```\nextra', '{"blocks":[],"blocks":[]}',
    '{"blocks":[{"id":"p0002_b0001","text":"a"},{"id":"p0002_b0001","text":"b"}]}',
    '{"blocks":[{"id":"p0002_b0002","text":"b"},{"id":"p0002_b0001","text":"a"}]}'])
def test_parser_strict_fence_keys_ids_and_source_order(raw):
    rows = [{'id': 'p0002_b0001', 'text': 'a'}, {'id': 'p0002_b0002', 'text': 'b'}]
    with pytest.raises(StructuredArtifactError):
        legacy._translation_rows(raw, rows)


def test_current_source_mutation_and_non_english_rejected(case):
    case['lang'] = TargetLang.FR
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)
    case['lang'] = TargetLang.EN
    case['source_structure'].blocks[0].text += ' Extra source.'
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)


def test_normalizer_cannot_silently_change_legacy_text(case, monkeypatch):
    monkeypatch.setattr(legacy, 'validate_block', lambda *a: a[1] + ' Changed.')
    with pytest.raises(StructuredArtifactError, match='normalization_changed'):
        legacy.recover_legacy_stage3_page(**case)
    assert not case['pages_dir'].exists()


def test_drift_during_publication_never_yields_valid_commit(case):
    calls = []
    def guard():
        calls.append(1)
        if len(calls) == 3:
            case['job'].path.write_bytes(b'{}')
    case['source_guard'] = guard
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)
    with pytest.raises(StructuredArtifactError):
        validate_structured_page(case['pages_dir'], 2)


def test_existing_output_never_overwritten(case):
    case['pages_dir'].mkdir()
    path = case['pages_dir'] / 'page_0002.txt'
    path.write_bytes(b'keep')
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)
    assert path.read_bytes() == b'keep'


@pytest.mark.parametrize('when', ['before', 'during'])
def test_output_directory_redirect_cannot_write_into_old_evidence(case, when):
    destination = case['job'].path.parent
    before = {path: path.read_bytes() for path in destination.iterdir()}
    def redirect():
        try:
            case['pages_dir'].symlink_to(destination, target_is_directory=True)
        except OSError as exc:
            pytest.skip('Directory symlink creation unavailable: ' + type(exc).__name__)
    if when == 'before':
        redirect()
    else:
        calls = []
        def guard():
            calls.append(1)
            if len(calls) == 2:
                redirect()
        case['source_guard'] = guard
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)
    assert {path: path.read_bytes() for path in destination.iterdir()} == before


@pytest.mark.parametrize('pin_index', [0, 1])
def test_legacy_source_byte_drift_rejected(case, pin_index):
    case['legacy_sources'][pin_index].path.write_bytes(b'{}')
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)
    assert not case['pages_dir'].exists()


def test_exact_new_bundle_works_in_full_case_assembly(case, tmp_path):
    from legalpdf_translate.acceptance_assembly import PageBundleRef, assembly_binding, assemble_mixed_case
    from legalpdf_translate.structured_artifacts import publish_structured_page
    result = legacy.recover_legacy_stage3_page(**case)
    first_source = case['legacy_sources'][0].read()
    first_target = deepcopy(first_source)
    first_target['blocks'][0]['text'] = 'Continuation'
    first_target['translation_sha256'] = digest_text('Continuation')
    first_folder = tmp_path / 'first_page'
    first = publish_structured_page(first_folder, source_structure=first_source, translated_structure=first_target,
        translated_text='Continuation', protocol_identity={'protocol': 'legal_blocks_v2', 'fingerprint': 'b' * 64},
        page_fingerprint='c' * 64, page_result=None)
    refs = [PageBundleRef(folder, commit,
        digest_text((folder / f"page_{commit['page_number']:04d}.commit.json").read_text(encoding='utf-8')), 'd' * 64)
        for folder, commit in ((first_folder, first), (case['pages_dir'], result['commit']))]
    kwargs = dict(page_bundles=refs, full_case_pages=[1, 2], source_file_sha256='a' * 64,
        lang=TargetLang.EN, preferences_sha256=case['preferences'].sha256)
    binding = assembly_binding(**kwargs)
    output = assemble_mixed_case(**kwargs, output_dir=tmp_path / 'assembly', evidence_guard=lambda: binding)
    receipt = json.loads((output.parent / 'assembly.json').read_bytes())
    assert receipt['original_commits'][1] == result['commit']
    assert receipt['provider_dispatch_count'] == 0
    assert receipt['fidelity_acceptance'] == 'not_evaluated'


@pytest.fixture
def reviewed_case(case):
    source = case['source_structure'].blocks[0]
    target = 'Request granted.\n\nDate indicated.\n2 / 2'
    binding = {'legacy_remapping_manifest_sha256': case['remapping_manifest'].sha256,
        'legacy_result_sha256': case['result'].sha256, 'preferences_sha256': case['preferences'].sha256,
        'source_structure_sha256': case['source_structure_sha256'], 'target_lang': 'EN'}
    edit = dict(block_id=source.id, source_text_sha256=digest_text(source.text),
        target_text_sha256=digest_text(target), source_visible_sha256=digest_text(source.text),
        target_visible_sha256=digest_text(target), source_start=17, source_end=30,
        source_text='Data indicada', target_start=18, target_end=32, before='Date indicated',
        after='Specified date', reason_code='terminology_review')
    # Build exact spans without embedding private source content in this fixture.
    edit.update(source_start=source.text.index('Data indicada'), source_end=source.text.index('Data indicada') + 13,
        target_start=target.index('Date indicated'), target_end=target.index('Date indicated') + 14)
    manifest = dict(version='acceptance_review_patch_v1', text_projection='structured_literal_visible_v1',
        reviewer_kind='codex_ai_test_review', binding=binding, edits=[edit])
    case['review_manifest'] = write_pin(case['job'].path.parent / 'current_review.json', manifest)
    return case


def test_explicit_post_mapping_review_is_distinct_and_bound(reviewed_case):
    case = reviewed_case
    target = 'Request granted.\n\nDate indicated.\n2 / 2'
    result = legacy.recover_legacy_stage3_page(**case)
    assert 'Specified date' in (case['pages_dir'] / 'page_0002.txt').read_text()
    assert result['provenance']['explicit_ai_review']['edit_count'] == 1
    assert result['provenance']['remapped_target_sha256'] == digest_text(target)
    assert result['provenance']['legacy_target_strings_preserved'] is False
    assert result['provenance']['fidelity_status'] == 'not_evaluated'
    case['review_manifest'] = replace(case['review_manifest'], sha256='0' * 64)
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)


def test_review_cannot_use_other_source_line_as_anchor(reviewed_case):
    case = reviewed_case
    manifest = case['review_manifest'].read()
    manifest['edits'][0].update(target_start=0, target_end=15, before='Request granted', after='Request refused')
    case['review_manifest'] = write_pin(case['review_manifest'].path, manifest)
    with pytest.raises(StructuredArtifactError, match='review_line_association'):
        legacy.recover_legacy_stage3_page(**case)
    assert not case['pages_dir'].exists()


def test_review_cannot_modify_source_bound_blank_partition(reviewed_case):
    case = reviewed_case
    manifest = case['review_manifest'].read()
    manifest['edits'][0]['after'] = 'Specified\ndate'
    case['review_manifest'] = write_pin(case['review_manifest'].path, manifest)
    with pytest.raises(StructuredArtifactError):
        legacy.recover_legacy_stage3_page(**case)
    assert not case['pages_dir'].exists()


@pytest.mark.parametrize('side', ['source', 'target'])
@pytest.mark.parametrize('marked', ['[[Text]]\n\nDate.', '\u200eText\n\nDate.', '\u2066Text\u2069\n\nDate.'])
def test_review_projection_cannot_shift_line_offsets(side, marked):
    source, target = ('Text\n\nDate.', 'Text\n\nDate.')
    if side == 'source':
        source = marked
    else:
        target = marked
    with pytest.raises(StructuredArtifactError, match='review_projection_not_identity'):
        legacy._review_projection(source, target)


def test_review_projection_guard_runs_before_applying_edits(reviewed_case, monkeypatch):
    def reject(source_text, target_text):
        raise legacy.LegacyRecoveryError('legacy_recovery_review_projection_not_identity')
    monkeypatch.setattr(legacy, '_review_projection', reject)
    monkeypatch.setattr(legacy, 'apply_reviewed_edits', lambda *a, **k: pytest.fail('Review ran before projection guard'))
    with pytest.raises(StructuredArtifactError, match='review_projection_not_identity'):
        legacy.recover_legacy_stage3_page(**reviewed_case)
    assert not reviewed_case['pages_dir'].exists()
