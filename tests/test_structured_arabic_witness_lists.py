"""Synthetic witness-list regressions; no retained legal-document contents."""
from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace
import time
import unicodedata

import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError,
    normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
)
from legalpdf_translate.types import PageStatus
from tests.test_structured_arabic_source_names import make_adapter


SOURCE = 'Prova testemunhal:\na) Ana Matos, e,\nb) Luís Correia, ambos militares da GNR.'
TARGET = 'الأدلة الشهادية:\na) Ana Matos، و،\nb) Luís Correia، كلاهما من GNR.'
TOKENS = ['a)', 'Ana Matos', 'b)', 'Luís Correia', 'GNR']


@pytest.mark.parametrize('heading', ['Prova testemunhal:', 'PROVA TESTEMUNHAL:',
                                     'Rol de testemunhas:', 'Testemunhas:'])
@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_exact_witness_list_names_are_protected_in_source_order(heading, newline):
    source = SOURCE.replace('Prova testemunhal:', heading).replace('\n', newline)
    prepared = prepare(source)
    assert extract_locked_tokens(prepared) == TOKENS
    assert prepared.replace('[[', '').replace(']]', '') == source
    assert extract_locked_tokens(normalize(prepared, TARGET)) == TOKENS


@pytest.mark.parametrize('form', ['raw_source', 'old_prepared_source', 'new_prepared_source'])
def test_saved_unwrapped_target_is_locally_reusable_without_request_rewrite(form):
    source = SOURCE
    if form == 'old_prepared_source':
        source = source.replace('a)', '[[a)]]').replace('b)', '[[b)]]').replace('GNR', '[[GNR]]')
    elif form == 'new_prepared_source':
        source = prepare(source)
    before = source
    normalized = normalize(source, TARGET)
    assert extract_locked_tokens(normalized) == TOKENS
    assert source == before
    assert normalized.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '') == TARGET


@pytest.mark.parametrize('name', ['Ana Matos', 'Ana de Matos', 'Luís D’Avila', 'Ana-Maria Matos',
                                  'Lui\u0301s Correia', 'Ana Matos\u0327'])
@pytest.mark.parametrize('marker', ['a)', 'b.', '1)', '12.'])
def test_name_spelling_graphemes_and_whole_span_are_preserved(name, marker):
    source = f'Testemunhas:\n  {marker} {name};'
    prepared = prepare(source)
    assert name in extract_locked_tokens(prepared)
    assert name in extract_locked_tokens(normalize(prepared, f'الشهود:\n{marker} {name}؛'))


@pytest.mark.parametrize('target', [
    TARGET.replace('Luís Correia', 'Luis Correia'),
    TARGET.replace('Luís Correia', 'Luís CorreiaX'),
    TARGET.replace('Luís Correia', 'Luís Correia\u0301'),
    TARGET.replace('Luís Correia', ''),
    TARGET.replace('Luís Correia', 'Ana Matos'),
    TARGET.replace('Ana Matos', 'TEMP').replace('Luís Correia', 'Ana Matos').replace('TEMP', 'Luís Correia'),
    TARGET + '\nAna Matos',
    TARGET + '\nProva Documental',
])
def test_changed_missing_reordered_duplicated_names_and_prose_stay_rejected(target):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(SOURCE), target)


@pytest.mark.parametrize('source', [
    'Prova documental:\na) Ana Matos',
    'Foi oferecida prova testemunhal:\na) Ana Matos',
    'Prova testemunhal:\nDescrição:\na) Ana Matos',
    'Prova testemunhal:\n*\na) Ana Matos',
    'Prova testemunhal:\n\n\na) Ana Matos',
    'Prova testemunhal:\nAna Matos',
    'Prova testemunhal:\na) Deve Pagar',
    'Prova testemunhal:\na) Ministério Público',
    'Prova testemunhal:\na) Prova Documental',
    'Prova testemunhal:\na) Ana Matos deve pagar.',
    'Prova testemunhal:\na) Ana Matos | Luís Correia',
    'Prova testemunhal:\na) Ana Matos e Luís Correia',
])
def test_heading_does_not_bless_unattributed_prose_cross_cells_or_scope_gaps(source):
    prepared = prepare(source)
    assert not any(token in {'Ana Matos', 'Luís Correia', 'Deve Pagar',
                             'Ministério Público', 'Prova Documental'}
                   for token in extract_locked_tokens(prepared))
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepared, source)


def test_list_scope_ends_after_first_nonitem_and_does_not_cross_blocks():
    source = 'Testemunhas:\na) Ana Matos;\nOutro assunto:\nb) Luís Correia;'
    assert extract_locked_tokens(prepare(source)) == ['a)', 'Ana Matos', 'b)']
    assert 'Luís Correia' not in extract_locked_tokens(prepare('b) Luís Correia;'))
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare('Testemunhas:\na) Ana Matos;'), 'الشهود:\na) Luís Correia؛')


def test_decomposed_institution_is_not_a_name():
    source = 'Testemunhas:\na) ' + unicodedata.normalize('NFD', 'Ministério Público')
    assert extract_locked_tokens(prepare(source)) == ['a)']


def test_decomposed_person_role_is_not_part_of_a_name():
    source = 'Testemunhas:\na) Signata\u0301rio Fulano'
    assert extract_locked_tokens(prepare(source)) == ['a)']
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source), 'الشهود:\na) Signata\u0301rio Fulano')


@pytest.mark.parametrize('separator', ['\v', '\f', '\x1c', '\x1d', '\x1e', '\x85', '\u2028', '\u2029'])
def test_paragraph_and_page_control_boundaries_end_heading_association(separator):
    assert 'Ana Matos' not in extract_locked_tokens(prepare(f'Testemunhas:{separator}a) Ana Matos'))


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('blank', ['', ' \t'])
def test_one_blank_after_heading_and_each_entry_preserves_exact_spans(newline, blank):
    source = SOURCE.replace('\n', newline + blank + newline)
    prepared = prepare(source)
    assert extract_locked_tokens(prepared) == TOKENS
    assert prepared.replace('[[', '').replace(']]', '') == source
    assert prepare(prepared) == prepared
    normalized = normalize(prepared, TARGET)
    assert extract_locked_tokens(normalized) == TOKENS
    assert normalize(prepared, normalized) == normalized


@pytest.mark.parametrize('prefix', ['Testemunhas:', 'Testemunhas:\na) Ana Matos;'])
@pytest.mark.parametrize('barrier', [
    '\n\n\n', '\r\n \t\r\n\t\r\n', '\n\nDescrição:\n',
    '\n\n|\n', '\n\na) Ana Matos, | outra célula\n',
    '\n\na) Deve Pagar;\n', '\n\nAna Matos\n',
    *('\n\n' + separator + '\n' for separator in '\v\f\x1c\x1d\x1e\x85\u2028\u2029'),
])
def test_blank_scope_cannot_cross_boundary_or_restart_without_heading(prefix, barrier):
    source = prefix + barrier + 'b) Luís Correia;\n\nc) Ana de Matos;'
    tokens = extract_locked_tokens(prepare(source))
    assert 'Luís Correia' not in tokens and 'Ana de Matos' not in tokens


@pytest.mark.parametrize('target', [
    TARGET.replace('Ana Matos', ''), TARGET + '\nAna Matos',
    TARGET.replace('Ana Matos', 'Luís Correia'),
    TARGET.replace('Ana Matos', 'TEMP').replace('Luís Correia', 'Ana Matos').replace('TEMP', 'Luís Correia'),
])
def test_blank_spacing_does_not_relax_literal_counts_or_associations(target):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(SOURCE.replace('\n', '\n\n')), target)


@pytest.mark.parametrize('target', [TARGET,
    TARGET.replace('Ana Matos', '[[Ana Matos]]').replace('Luís Correia', '[[Luís Correia]]'),
    TARGET.replace('Ana Matos', '[[Ana]] [[Matos]]').replace('Luís Correia', '[[Luís]] [[Correia]]')])
def test_wrapper_normalization_is_idempotent(target):
    prepared = prepare(SOURCE)
    assert prepare(prepared) == prepared
    normalized = normalize(prepared, target)
    assert normalize(prepared, normalized) == normalized
    assert extract_locked_tokens(normalized) == TOKENS


@pytest.mark.parametrize('gap', ['\n', '\n\n'])
def test_real_adapter_accepts_list_in_one_call_without_mutating_source(tmp_path, monkeypatch, gap):
    adapter = make_adapter(monkeypatch)
    # Reviewed-source blocks may contain a whole list. Ordinary extraction can
    # split this into three blocks; that is not same-block name attribution.
    text = SOURCE.replace('\n', gap)
    source = PageStructure(page_number=1, source_sha256=text_sha256(text),
        source_text_sha256=text_sha256(text), source_file_sha256='1' * 64,
        blocks=[StructureBlock(id='p0001_b0001', text=text)])
    original = deepcopy(source.to_dict())
    assert len(source.blocks) == 1
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        assert len(calls) == 1, 'Exact witness names must not cause a correction call.'
        payload, _ = json.JSONDecoder().raw_decode(kwargs['prompt_text'])
        assert extract_locked_tokens(payload['blocks'][0]['text']) == TOKENS
        assert 'exact occurrence counts and order within each block' in kwargs['instructions']
        assert 'borrowed words, quoted text' in kwargs['instructions']
        return ApiCallResult(raw_output=json.dumps({'blocks': [
            {'id': source.blocks[0].id, 'text': TARGET}]}),
            usage={'input_tokens': 10, 'output_tokens': 15, 'total_tokens': 25},
            response_id='synthetic', response_status='completed', model='synthetic', effort='high')

    result = adapter.translate(client=SimpleNamespace(create_page_response=create), source=source,
        paths=SimpleNamespace(pages_dir=tmp_path / 'pages'), page_number=1, total_pages=1,
        context_text=None, image_data_url=None, image_detail='low', effort='high',
        metadata={'api_calls_count': 0, 'transport_retries_count': 0}, started=time.perf_counter())
    assert result.status == PageStatus.DONE and not result.retry_used and len(calls) == 1
    assert result.page_metadata['fidelity_review_status'] == 'not_evaluated'
    assert source.to_dict() == original
