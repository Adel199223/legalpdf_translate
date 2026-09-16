"""Synthetic wrapped institutional headings; no retained case contents."""
from copy import deepcopy
import json
from types import SimpleNamespace
import time

import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
from legalpdf_translate.glossary import GlossaryEntry
from legalpdf_translate.openai_client import ApiCallResult
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError, normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
)
from legalpdf_translate.structured_glossary import build_structured_glossary
from legalpdf_translate.types import PageStatus
from tests.test_structured_arabic_source_names import make_adapter


PREFIX = 'Ministério Público - Procuradoria da República da Comarca de'


def source(place='Évora', heading=None):
    heading = heading or PREFIX.replace('da República', 'da\nRepública')
    return f'{heading} {place}\nInquéritos de {place}\n1200-345 {place}'


def target(place='Évora'):
    return f'النيابة العامة - نيابة الجمهورية لدائرة {place}\nوحدة التحقيقات في {place}\n1200-345 {place}'


def proof(text, entries=()):
    return build_structured_glossary([{'id': 'p0001_b0001', 'text': text}], list(entries),
        target_lang='AR').for_block('p0001_b0001')


def visible(text):
    return text.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '')


@pytest.mark.parametrize('place', ['Évora', 'Porto', 'Castelo Branco'])
@pytest.mark.parametrize('newline', ['\n', '\r\n'])
def test_verified_place_repeated_in_wrapped_header_is_counted_exactly(place, newline):
    text = source(place).replace('\n', newline)
    contract = proof(text)
    prepared = prepare(text, glossary_contract=contract)
    assert extract_locked_tokens(prepared) == [place, place, f'1200-345 {place}']
    normalized = normalize(prepared, target(place), glossary_contract=contract)
    assert visible(normalized) == target(place)
    assert prepare(prepared, glossary_contract=contract) == prepared
    assert normalize(prepared, normalized, glossary_contract=contract) == normalized


@pytest.mark.parametrize('target_form', [target(), target().replace('Évora', '[[Évora]]')])
def test_old_prepared_prompt_and_paid_visible_text_are_not_rewritten(target_form):
    text = source()
    contract = proof(text)
    old_prompt = text.replace('Inquéritos de Évora', 'Inquéritos de [[Évora]]').replace(
        '1200-345 Évora', '[[1200-345 Évora]]')
    original = old_prompt
    normalized = normalize(old_prompt, target_form, glossary_contract=contract)
    assert visible(normalized) == visible(target_form)
    assert old_prompt == original


@pytest.mark.parametrize('changed', [
    target().replace('Évora', 'Evora', 1), target().replace('Évora', 'ÉvoraX', 1),
    target().replace('Évora', 'Évora\u0301', 1), target().replace('Évora', '', 1),
    target() + '\nÉvora', target().replace('1200-345 Évora', '1200-345 Évora Évora'),
    '\n'.join(reversed(target().splitlines())),
])
def test_extra_missing_changed_or_reassociated_literals_remain_errors(changed):
    text = source()
    contract = proof(text)
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(text, glossary_contract=contract), changed, glossary_contract=contract)


@pytest.mark.parametrize('heading', [
    PREFIX.replace('da República', 'da\n\nRepública'),
    PREFIX.replace('da República', 'da\fRepública'),
    PREFIX.replace('da República', 'da\nOutro assunto\nRepública'),
    PREFIX.replace('da República', 'da\nRepública').replace('Comarca de', 'Comarca\nde'),
    'Referência a ' + PREFIX.replace('da República', 'da\nRepública'),
    'Évora deve pagar.\nCabeçalho sem associação:',
])
def test_place_proof_does_not_bless_arbitrary_prose_or_cross_paragraphs(heading):
    text = source(heading=heading)
    contract = proof(text)
    prepared = prepare(text, glossary_contract=contract)
    assert extract_locked_tokens(prepared).count('Évora') == 1
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepared, target(), glossary_contract=contract)


def test_heading_place_still_needs_independent_same_block_glossary_proof():
    text = PREFIX.replace('da República', 'da\nRepública') + ' Évora'
    contract = proof(text)
    assert contract.literal_spans == ()
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(text, glossary_contract=contract), 'النيابة في Évora', glossary_contract=contract)


def test_expansion_cannot_override_a_configured_translation_of_the_place():
    text = source()
    entry = GlossaryEntry('República da Comarca de Évora', 'نيابة الجمهورية لدائرة إيفورا', 'exact', 'PT', 1)
    contract = proof(text, [entry])
    with pytest.raises(StructuredArabicLiteralError, match='conflicting_source_place_literal'):
        prepare(text, glossary_contract=contract)


def test_real_adapter_finishes_in_one_call_and_preserves_source(tmp_path, monkeypatch):
    adapter = make_adapter(monkeypatch)
    text = source()
    page = PageStructure(page_number=1, source_sha256=text_sha256(text),
        source_text_sha256=text_sha256(text), source_file_sha256='1' * 64,
        blocks=[StructureBlock(id='p0001_b0001', text=text)])
    original = deepcopy(page.to_dict())
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        assert len(calls) == 1, 'An exact repeated source place must not cause a correction.'
        payload, _ = json.JSONDecoder().raw_decode(kwargs['prompt_text'])
        assert extract_locked_tokens(payload['blocks'][0]['text']) == ['Évora', 'Évora', '1200-345 Évora']
        return ApiCallResult(raw_output=json.dumps({'blocks': [{'id': page.blocks[0].id, 'text': target()}]}),
            usage={'input_tokens': 10, 'output_tokens': 15, 'total_tokens': 25},
            response_id='synthetic', response_status='completed', model='synthetic', effort='high')

    result = adapter.translate(client=SimpleNamespace(create_page_response=create), source=page,
        paths=SimpleNamespace(pages_dir=tmp_path / 'pages'), page_number=1, total_pages=1,
        context_text=None, image_data_url=None, image_detail='low', effort='high',
        metadata={'api_calls_count': 0, 'transport_retries_count': 0}, started=time.perf_counter())
    assert result.status == PageStatus.DONE and not result.retry_used and len(calls) == 1
    assert result.page_metadata['fidelity_review_status'] == 'not_evaluated'
    assert page.to_dict() == original
