"""Synthetic postal/addressee association; no retained document values."""
from copy import deepcopy
import json
from types import SimpleNamespace
import time

import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError, normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
)
from legalpdf_translate.types import PageStatus
from tests.test_structured_arabic_source_names import make_adapter


SENDER = 'Largo Eng. Álvaro Mendes\n1200-345 Lisboa'
RECIPIENT = 'Exmo(a) Senhor(a)\nJoão Guerreiro\nRua das Flores Nr.: 12\n4000-123 Porto'
SOURCE = SENDER + '\n\n' + RECIPIENT
TARGET = SENDER + '\n\nالسيد المحترم\nJoão Guerreiro\nRua das Flores Nr.: 12\n4000-123 Porto'
TOKENS = ['Largo Eng. Álvaro Mendes', '1200-345 Lisboa', 'João Guerreiro',
          'Rua das Flores Nr.: 12', '4000-123 Porto']


def visible(value):
    return value.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '')


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('salutation', ['Exmo(a) Senhor(a)', 'Exmo. Senhor', 'Exma. Senhora'])
def test_exact_postal_chains_prove_streets_and_addressee(newline, salutation):
    text = SOURCE.replace('Exmo(a) Senhor(a)', salutation).replace('\n', newline)
    prepared = prepare(text)
    assert extract_locked_tokens(prepared) == TOKENS
    assert visible(prepared) == text
    normalized = normalize(prepared, TARGET)
    assert visible(normalized) == TARGET
    assert prepare(prepared) == prepared
    assert normalize(prepared, normalized) == normalized


@pytest.mark.parametrize('form', ['raw', 'old_prepared'])
def test_saved_prompt_normalization_never_changes_visible_translation(form):
    text = SOURCE
    if form == 'old_prepared':
        text = text.replace('1200-345 Lisboa', '[[1200-345 Lisboa]]').replace(
            '4000-123 Porto', '[[4000-123 Porto]]').replace('Nr.: 12', 'Nr.: [[12]]')
    original = text
    assert visible(normalize(text, TARGET)) == TARGET
    assert text == original


@pytest.mark.parametrize('mutated', [
    RECIPIENT.replace('Senhor(a)\n', 'Senhor(a)\n\n'),
    RECIPIENT.replace('Guerreiro\n', 'Guerreiro\n\n'),
    RECIPIENT.replace('12\n', '12\n\n'),
    RECIPIENT.replace('12\n', '12\f'),
    RECIPIENT.replace('12\n', '12\u2029'),
    RECIPIENT.replace('12\n', '12\nOutro assunto\n'),
    RECIPIENT.replace('Exmo(a) Senhor(a)', 'Senhor'),
    RECIPIENT.replace('João Guerreiro', 'Deve Pagar'),
    RECIPIENT.replace('João Guerreiro', 'João Guerreiro | Ana Matos'),
    RECIPIENT.replace('4000-123', '4000'),
    RECIPIENT.replace('4000-123 Porto', '4000-123'),
    RECIPIENT.replace('4000-123 Porto', 'Texto sem código'),
    RECIPIENT.replace('Nr.: 12', 'Obrigação: 12'),
    RECIPIENT.replace('Nr.: 12', 'Nr.: texto'),
    RECIPIENT.replace('Nr.: 12', 'Nr.: 12 deve pagar'),
    RECIPIENT.replace('Nr.: 12', 'Nr.: 12 Enviar Documentos'),
    RECIPIENT.replace('Nr.: 12', 'Nr.: 12 Nr.: 13'),
])
def test_invalid_or_incomplete_chains_do_not_prove_addressee(mutated):
    assert 'João Guerreiro' not in extract_locked_tokens(prepare(mutated))
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(mutated), TARGET)


@pytest.mark.parametrize('mutated', [
    SENDER.replace('\n', '\n\n'), SENDER.replace('\n', '\f'),
    SENDER.replace('\n', '\nOutro assunto\n'), SENDER.replace('1200-345 Lisboa', '1200-345'),
    SENDER.replace('Largo Eng.', 'Obrigações:'),
])
def test_street_without_immediate_postal_city_is_not_whole_line_literal(mutated):
    assert 'Largo Eng. Álvaro Mendes' not in extract_locked_tokens(prepare(mutated))


@pytest.mark.parametrize('separator', ['\f', '\v', '\x85', '\u2028', '\u2029'])
def test_no_literal_crosses_hard_address_boundary(separator):
    text = SENDER.replace('\n', separator)
    assert all(separator not in literal for literal in extract_locked_tokens(prepare(text)))
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(text), SENDER)


@pytest.mark.parametrize('changed', [
    TARGET.replace('João Guerreiro', 'Joao Guerreiro'), TARGET.replace('João Guerreiro', ''),
    TARGET + '\nJoão Guerreiro', TARGET.replace('Álvaro', 'Alvaro'),
    TARGET.replace('Nr.: 12', 'Nr.: 13'), TARGET.replace('Nr.: 12', 'Nr. 12'),
    TARGET.replace('4000-123 Porto', '1200-345 Lisboa'),
    '\n'.join(reversed(TARGET.splitlines())),
])
def test_changed_missing_duplicate_or_reassociated_name_address_is_rejected(changed):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(SOURCE), changed)


def test_recipient_name_does_not_cross_source_blocks():
    assert 'João Guerreiro' not in extract_locked_tokens(prepare('João Guerreiro\nRua das Flores Nr.: 12\n4000-123 Porto'))
    assert 'João Guerreiro' not in extract_locked_tokens(prepare('Exmo(a) Senhor(a)\nJoão Guerreiro'))


def test_real_adapter_reuses_exact_names_addresses_in_one_call(tmp_path, monkeypatch):
    adapter = make_adapter(monkeypatch)
    page = PageStructure(page_number=1, source_sha256=text_sha256(SOURCE),
        source_text_sha256=text_sha256(SOURCE), source_file_sha256='1' * 64,
        blocks=[StructureBlock(id='p0001_b0001', text=SOURCE)])
    before = deepcopy(page.to_dict())
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        assert len(calls) == 1, 'Exact postal/name content must not cause correction.'
        payload, _ = json.JSONDecoder().raw_decode(kwargs['prompt_text'])
        assert extract_locked_tokens(payload['blocks'][0]['text']) == TOKENS
        return ApiCallResult(raw_output=json.dumps({'blocks': [{'id': page.blocks[0].id, 'text': TARGET}]}),
            usage={'input_tokens': 10, 'output_tokens': 15, 'total_tokens': 25},
            response_id='synthetic', response_status='completed', model='synthetic', effort='high')

    result = adapter.translate(client=SimpleNamespace(create_page_response=create), source=page,
        paths=SimpleNamespace(pages_dir=tmp_path / 'pages'), page_number=1, total_pages=1,
        context_text=None, image_data_url=None, image_detail='low', effort='high',
        metadata={'api_calls_count': 0, 'transport_retries_count': 0}, started=time.perf_counter())
    assert result.status == PageStatus.DONE and not result.retry_used and len(calls) == 1
    assert page.to_dict() == before
