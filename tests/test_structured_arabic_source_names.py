"""Offline source-name regressions; no retained provider or private document data."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import threading
import time
import unicodedata
from types import SimpleNamespace

import pytest
from docx import Document

from legalpdf_translate import new_translation_blocks as adapter_module
from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.document_structure import structure_from_text
from legalpdf_translate.docx_writer import assemble_docx
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError,
    normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
    source_person_name_for_field,
)
from legalpdf_translate.types import OcrMode, PageStatus, TargetLang
from legalpdf_translate.translation_structure import BlockCoverageError, parse_structured_translation


NAME = 'João Guerreiro'
PAIRS = [
    ('Destinatário: João Guerreiro', 'المرسل إليه: João Guerreiro'),
    ('Documento de identificação | João Guerreiro', 'وثيقة الهوية | João Guerreiro'),
    ('O destinatário João Guerreiro deve apresentar os documentos.',
     'يجب على المرسل إليه João Guerreiro تقديم المستندات.'),
    ('João Guerreiro declarou que recebeu a notificação.',
     'صرّح João Guerreiro بأنه تسلّم الإخطار.'),
]


def make_adapter(monkeypatch):
    monkeypatch.setattr(adapter_module, 'source_page_identity',
                        lambda *_: {'source_file_sha256': '1' * 64})
    config = SimpleNamespace(pdf_path=Path('synthetic.pdf'), target_lang=TargetLang.AR,
                             ocr_mode=OcrMode.OFF, effort='high', effort_policy='fixed', page_breaks=False)
    def accumulate(metadata, usage):
        for key in ('input_tokens', 'output_tokens', 'reasoning_tokens', 'total_tokens'):
            metadata[key] = metadata.get(key, 0) + usage.get(key, 0)
    workflow = SimpleNamespace(_prompt_glossaries_by_lang={}, _enabled_glossary_tiers_by_lang={},
        _dispatch_accounting=None,
        _prompt_addendum_by_lang={}, _last_state=SimpleNamespace(pages={}), _cancel_event=threading.Event(),
        _translation_request_timeout_seconds=lambda **_: 30, _utc_now=lambda: 'synthetic-time',
        _accumulate_usage_totals=accumulate, _is_usable_source_text=lambda text: bool(text.strip()))
    return adapter_module.NewTranslationBlocks(workflow, config, (1,), source_hash='1' * 64, context_hash='context')


@pytest.mark.parametrize('source_text,translated', PAIRS)
def test_real_adapter_accepts_exact_names_once_and_writer_keeps_one_latin_run(
        tmp_path, monkeypatch, source_text, translated):
    run = make_adapter(monkeypatch)
    source = structure_from_text(source_text, page_number=1, source_file_sha256='1' * 64)
    original_source = deepcopy(source.to_dict())
    assert len(source.blocks) == 1
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        assert len(calls) == 1, 'Correct source-exact name must not consume a correction.'
        payload, _ = json.JSONDecoder().raw_decode(kwargs['prompt_text'])
        assert extract_locked_tokens(payload['blocks'][0]['text']) == [NAME]
        return ApiCallResult(raw_output=json.dumps({'blocks': [
            {'id': source.blocks[0].id, 'text': translated}]}),
            usage={'input_tokens': 8, 'output_tokens': 12, 'total_tokens': 20},
            response_id='synthetic', response_status='completed', model='synthetic', effort='high')
    pages = tmp_path / 'pages'
    result = run.translate(client=SimpleNamespace(create_page_response=create), source=source,
        paths=SimpleNamespace(pages_dir=pages), page_number=1, total_pages=1, context_text=None,
        image_data_url=None, image_detail='low', effort='high',
        metadata={'api_calls_count': 0, 'transport_retries_count': 0}, started=time.perf_counter())
    assert result.status == PageStatus.DONE and not result.retry_used and len(calls) == 1
    assert result.page_metadata['fidelity_review_status'] == 'not_evaluated'
    assert source.to_dict() == original_source
    committed = {path.name: path.read_bytes() for path in pages.iterdir() if path.is_file()}
    output = assemble_docx(pages, tmp_path / 'translated.docx', lang=TargetLang.AR,
                           page_breaks=False, page_numbers=[1])
    document = Document(output)
    name_runs = [run for paragraph in document.paragraphs for run in paragraph.runs if NAME in run.text]
    assert len(name_runs) == 1
    assert NAME in name_runs[0].text
    assert '[[' not in name_runs[0].text and ']]' not in name_runs[0].text
    assert all((pages / name).read_bytes() == data for name, data in committed.items())


@pytest.mark.parametrize('changed', ['Joao Guerreiro', 'Guerreiro João', 'João GuerreiroX',
                                     'Nuno Carrujo', 'João  Guerreiro', 'João Guerreir0'])
@pytest.mark.parametrize('source', [PAIRS[0][0], PAIRS[1][0], PAIRS[3][0]])
def test_detected_source_names_cannot_be_changed_or_replaced(source, changed):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source), f'المرسل إليه [[{changed}]]')


@pytest.mark.parametrize('source', [
    'Destinatário: Ministério Público',
    'Documento de identificação | Prova Documental',
    'O destinatário deve pagar o montante no prazo indicado.',
    'Destinatário: Deve Pagar',
    'Documento de identificação | Comprovativo de Pagamento',
    'Tribunal Judicial declarou que recebeu a notificação.',
])
def test_person_context_never_blesses_generic_legal_or_institutional_prose(source):
    prepared = prepare(source)
    assert extract_locked_tokens(prepared) == []
    with pytest.raises(StructuredArabicLiteralError, match='unsupported_latin_or_digit_content'):
        normalize(prepared, f'[[{source}]]')


def test_names_are_not_global_titlecase_whitelist_or_cross_block_evidence():
    assert prepare('Informações Complementares') == 'Informações Complementares'
    with pytest.raises(StructuredArabicLiteralError, match='unsupported_latin_or_digit_content'):
        normalize(prepare('Notificação ao destinatário.'), f'الإخطار إلى [[{NAME}]]')


def test_person_association_and_duplicate_counts_remain_strict():
    source = prepare('Destinatário: João Guerreiro; testemunha: Nuno Carrujo.')
    assert extract_locked_tokens(source) == [NAME, 'Nuno Carrujo']
    for target in ('المرسل إليه Nuno Carrujo؛ الشاهد João Guerreiro.',
                   'المرسل إليه João Guerreiro؛ الشاهد João Guerreiro؛ Nuno Carrujo.'):
        with pytest.raises(StructuredArabicLiteralError):
            normalize(source, target)


@pytest.mark.parametrize('source,literal,split', [
    ('Destinatário: João Guerreiro', NAME, ('João', ' ', 'Guerreiro')),
    ('Montante: 150', '150', ('1', '', '50')),
])
@pytest.mark.parametrize('mark', ['\u0301', '\u0327', '\u0332', '\u0903', '\u20dd'])
@pytest.mark.parametrize('form', ['plain', 'whole', 'split'])
def test_actual_block_validation_rejects_unsourced_literal_combining_suffix(
        source, literal, split, mark, form):
    if form == 'plain':
        value = literal + mark
    elif form == 'whole':
        value = f'[[{literal}{mark}]]'
    else:
        first, gap, last = split
        value = f'[[{first}]]{gap}[[{last}{mark}]]'
    row = {'id': 'p0001_b0001', 'text': prepare(source)}
    parsed = parse_structured_translation(
        json.dumps({'blocks': [{'id': row['id'], 'text': f'البيان: {value}'}]}),
        [row], page_number=1, response_status='completed', refused=False)
    with pytest.raises(BlockCoverageError) as caught:
        adapter_module.validate_block(row, parsed[0]['text'], TargetLang.AR, None, set())
    assert caught.value.detail_code == 'source_literal_coverage_mismatch'


@pytest.mark.parametrize('prefix,suffix', [
    ('المُرسَل إليه: ', ''),
    ('وَ', ''),
    ('فَ', ' وَالشاهد حاضر.'),
    ('المُرسَل إليه: ', 'وَالشاهد حاضر.'),
])
@pytest.mark.parametrize('form', ['plain', 'whole', 'split'])
def test_actual_block_validation_preserves_exact_name_and_arabic_diacritics(prefix, suffix, form):
    value = NAME if form == 'plain' else f'[[{NAME}]]' if form == 'whole' else '[[João]] [[Guerreiro]]'
    target = prefix + value + suffix
    row = {'id': 'p0001_b0001', 'text': prepare(f'Destinatário: {NAME}')}
    parsed = parse_structured_translation(
        json.dumps({'blocks': [{'id': row['id'], 'text': target}]}),
        [row], page_number=1, response_status='completed', refused=False)
    normalized = adapter_module.validate_block(row, parsed[0]['text'], TargetLang.AR, None, set())
    assert normalized == prefix + f'\u2066[[{NAME}]]\u2069' + suffix


@pytest.mark.parametrize('label,name', [
    ('Destinatário', 'João Andre\u0301'),
    ('Nome', 'João Andre\u0301'),
    ('Nome', 'João Andre\u0301 Silva'),
    ('Destinatário', 'Joa\u0303o Guerreiro'),
    ('Nome', 'Jose\u0301 D’Avila'),
    ('Destinatário', 'João Andre\u0301\u0327'),
])
@pytest.mark.parametrize('form', ['plain', 'whole', 'split'])
def test_real_adapter_preserves_complete_exact_source_name_graphemes(tmp_path, monkeypatch, label, name, form):
    run = make_adapter(monkeypatch)
    source = structure_from_text(f'{label}: {name}', page_number=1, source_file_sha256='1' * 64)
    original = deepcopy(source.to_dict())
    value = name if form == 'plain' else f'[[{name}]]' if form == 'whole' else ' '.join(
        f'[[{part}]]' for part in name.split(' '))
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        assert len(calls) == 1
        payload, _ = json.JSONDecoder().raw_decode(kwargs['prompt_text'])
        assert extract_locked_tokens(payload['blocks'][0]['text']) == [name]
        return ApiCallResult(raw_output=json.dumps({'blocks': [
            {'id': source.blocks[0].id, 'text': f'المُرسل إليه: {value}'}]}),
            usage={'input_tokens': 8, 'output_tokens': 12, 'total_tokens': 20},
            response_id='synthetic', response_status='completed', model='synthetic', effort='high')
    pages = tmp_path / 'pages'
    result = run.translate(client=SimpleNamespace(create_page_response=create), source=source,
        paths=SimpleNamespace(pages_dir=pages), page_number=1, total_pages=1, context_text=None,
        image_data_url=None, image_detail='low', effort='high',
        metadata={'api_calls_count': 0, 'transport_retries_count': 0}, started=time.perf_counter())
    assert result.status == PageStatus.DONE and not result.retry_used and len(calls) == 1
    assert source.to_dict() == original
    assert (pages / 'page_0001.txt').read_text('utf-8') == f'المُرسل إليه: \u2066[[{name}]]\u2069'
    assert source_person_name_for_field('Nome', name) == name


@pytest.mark.parametrize('source_text,literal', [
    ('Destinatário: João Andre\u0301', 'João Andre\u0301'),
    ('Montante: 150\u0332', '150\u0332'),
])
@pytest.mark.parametrize('change', ['unchanged', 'extra_mark', 'dropped_mark', 'latin_suffix'])
def test_source_mark_is_preserved_exactly_not_removed_or_extended(source_text, literal, change):
    value = {'unchanged': literal, 'extra_mark': literal + '\u0327',
             'dropped_mark': literal[:-1], 'latin_suffix': literal + 'X'}[change]
    row = {'id': 'p0001_b0001', 'text': prepare(source_text)}
    target = f'البيان: [[{value}]]'
    if change == 'unchanged':
        assert adapter_module.validate_block(row, target, TargetLang.AR, None, set()) == f'البيان: \u2066[[{literal}]]\u2069'
    else:
        with pytest.raises(BlockCoverageError):
            adapter_module.validate_block(row, target, TargetLang.AR, None, set())


def test_nfd_name_detection_does_not_bless_decomposed_institution_or_repair_spelling():
    institution = unicodedata.normalize('NFD', 'Ministério Público')
    assert extract_locked_tokens(prepare(f'Destinatário: {institution}')) == []
    assert source_person_name_for_field('Nome', institution) is None
    name = 'Joa\u0303o Guerreiro'
    row = {'id': 'p0001_b0001', 'text': prepare(f'Destinatário: {name}')}
    with pytest.raises(BlockCoverageError):
        adapter_module.validate_block(row, f'المرسل إليه: {unicodedata.normalize("NFC", name)}', TargetLang.AR, None, set())


def test_name_policy_version_changes_translation_identity(monkeypatch):
    first = make_adapter(monkeypatch).identity
    monkeypatch.setattr(adapter_module, 'STRUCTURED_ARABIC_LITERALS_VERSION', 'old-source-name-policy')
    assert make_adapter(monkeypatch).identity != first


@pytest.mark.parametrize('field', ['Nome', 'Destinatário', 'Documento de identificação', 'NAME:'])
def test_explicit_person_field_admits_only_exact_plausible_name(field):
    assert source_person_name_for_field(field, NAME) == NAME
    for prose in ('Deve Pagar', 'Prova Documental', 'Ministério Público', 'Comprovativo de Pagamento'):
        assert source_person_name_for_field(field, prose) is None
    assert source_person_name_for_field('Descrição', NAME) is None


def test_separate_source_table_cells_use_exact_header_column_association(tmp_path, monkeypatch):
    run = make_adapter(monkeypatch)
    source = structure_from_text(f'Nome\n\n{NAME}', page_number=1, source_file_sha256='1' * 64)
    assert len(source.blocks) == 2
    for row, block in enumerate(source.blocks):
        block.role, block.table_id, block.row, block.col = 'table_cell', 'people', row, 0
    calls = []
    def create(**kwargs):
        calls.append(kwargs)
        assert len(calls) == 1
        payload, _ = json.JSONDecoder().raw_decode(kwargs['prompt_text'])
        assert extract_locked_tokens(payload['blocks'][0]['text']) == []
        assert extract_locked_tokens(payload['blocks'][1]['text']) == [NAME]
        return ApiCallResult(raw_output=json.dumps({'blocks': [
            {'id': source.blocks[0].id, 'text': 'الاسم'},
            {'id': source.blocks[1].id, 'text': NAME}]}),
            usage={'input_tokens': 8, 'output_tokens': 12, 'total_tokens': 20},
            response_id='synthetic', response_status='completed', model='synthetic', effort='high')
    result = run.translate(client=SimpleNamespace(create_page_response=create), source=source,
        paths=SimpleNamespace(pages_dir=tmp_path / 'pages'), page_number=1, total_pages=1, context_text=None,
        image_data_url=None, image_detail='low', effort='high',
        metadata={'api_calls_count': 0, 'transport_retries_count': 0}, started=time.perf_counter())
    assert result.status == PageStatus.DONE and not result.retry_used and len(calls) == 1


@pytest.mark.parametrize('change', ['other_table', 'other_column', 'not_header', 'ambiguous_header', 'generic_field'])
def test_table_name_proof_never_crosses_or_guesses_field_association(change):
    source = structure_from_text(f'Nome\n\n{NAME}', page_number=1, source_file_sha256='1' * 64)
    for row, block in enumerate(source.blocks):
        block.role, block.table_id, block.row, block.col = 'table_cell', 'people', row, 0
    header, value = source.blocks
    if change == 'other_table':
        header.table_id = 'different'
    elif change == 'other_column':
        header.col = 1
    elif change == 'not_header':
        header.row = 2
    elif change == 'ambiguous_header':
        other = deepcopy(header)
        other.id = 'p0001_b0003'
        source.blocks.append(other)
    elif change == 'generic_field':
        header.text = 'Descrição'
    assert adapter_module._source_table_person_names(source).get(value.id) is None
