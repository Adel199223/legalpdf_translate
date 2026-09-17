"""Synthetic source-attributed fields, never private document excerpts."""
import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError, normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
)


PAIRS = [
    ('Assinado em 12-03-2027, por\nAna Maria Matos, Juiz de Direito\n\nLisboa, d.s.\n\nA Juiz de Direito\n\nAna Maria Matos',
     'تم التوقيع في 12-03-2027، من قبل\nAna Maria Matos، القاضي\n\nLisboa، التاريخ أعلاه\nالقاضي\nAna Maria Matos',
     ['12-03-2027', 'Ana Maria Matos', 'Lisboa', 'Ana Maria Matos']),
    ('Assinado em 12-03-2027, por\nAna Maria Matos, Procurador da República',
     'تم التوقيع في 12-03-2027، من قبل\nAna Maria Matos، وكيل الجمهورية', ['12-03-2027', 'Ana Maria Matos']),
    ('Lisboa, d.s\n\nA Magistrada do Ministério Público,\nAna Maria Matos',
     'Lisboa، التاريخ أعلاه\n\nقاضية النيابة العامة\nAna Maria Matos', ['Lisboa', 'Ana Maria Matos']),
    ('Indiciam suficientemente que João Guerreiro, filho de Luís Guerreiro e de Ana Matos, nascido em 12/03/1980.',
     'تشير أدلة كافية إلى أن João Guerreiro، ابن Luís Guerreiro وAna Matos، المولود في 12/03/1980.',
     ['João Guerreiro', 'Luís Guerreiro', 'Ana Matos', '12/03/1980']),
    ('residente na Rua das Flores, n.º 12, 4000-123 Porto, concelho de Porto,',
     'المقيم في Rua das Flores، رقم 12، 4000-123 Porto، بلدية Porto،',
     ['Rua das Flores', '12', '4000-123 Porto', 'Porto']),
    ('na Rua das Flores, Cedofeita, Porto, o arguido conduzia o veículo.',
     'في Rua das Flores, Cedofeita, Porto، كان المتهم يقود المركبة.', ['Rua das Flores, Cedofeita, Porto']),
    ('marca Opel, modelo Corsa 1.2.', 'من علامة Opel، طراز Corsa 1.2.', ['Opel', 'Corsa 1.2']),
    ('relatado pelo Senhor Desembargador Luís Matos,', 'أعده القاضي Luís Matos،', ['Luís Matos']),
    ('(Ana Matos, «Obra jurídica», in RMP nº 12, ...)', '(Ana Matos، «مؤلف قانوني»، في RMP رقم 12، ...)',
     ['Ana Matos', 'RMP', '12']),
    ('na página da internet www.example.org.', 'على صفحة الإنترنت www.example.org.', ['www.example.org']),
    ('Acórdão da Relação de Lisboa de 12 de Março de 2031,',
     'حكم محكمة الاستئناف في Lisboa بتاريخ 12 من مارس 2031،', ['Lisboa', '12', '2031']),
    ('artigo 45º, nº 3 al. x) e 48º, al. z)',
     'المادة 45، رقم 3 الفقرة x) و48، الفقرة z)', ['45', '3', 'x', '48', 'z']),
]


@pytest.mark.parametrize('source,target,expected', PAIRS)
def test_attributed_literals_keep_spelling_order_and_wrapper_idempotence(source, target, expected):
    prepared = prepare(source)
    assert extract_locked_tokens(prepared) == expected
    assert prepared.replace('[[', '').replace(']]', '') == source
    assert prepare(prepared) == prepared
    normalized = normalize(prepared, target)
    assert extract_locked_tokens(normalized) == expected
    assert normalized.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '') == target
    assert normalize(prepared, normalized) == normalized


@pytest.mark.parametrize('source,target,expected', PAIRS)
def test_missing_or_duplicated_source_fields_never_pass(source, target, expected):
    prepared = prepare(source)
    selected = expected[-1]
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepared, target + '\n' + selected)
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepared, target.replace(selected, '', 1))


@pytest.mark.parametrize('source,unproved', [
    ('Ana Matos, Juiz de Direito', 'Ana Matos'),
    ('Assinado em 12-03-2027, por\n\nAna Matos, Juiz de Direito', 'Ana Matos'),
    ('Lisboa, d.s.\nOutro assunto\nA Juiz de Direito\nAna Matos', 'Lisboa'),
    ('Lisboa, d.s.\n\n\nA Juiz de Direito\nAna Matos', 'Lisboa'),
    ('Lisboa, d.s.\fA Juiz de Direito\nAna Matos', 'Lisboa'),
    ('A Magistrada do Ministério Público,\n\n\nAna Matos', 'Ana Matos'),
    ('Indiciam suficientemente que Ana Matos, filha de João Matos e de Maria Alves, outra informação.', 'Ana Matos'),
    ('Indiciam suficientemente que Ana Matos, filha de João Matos | Outra Pessoa e de Maria Alves, nascida em 2000.', 'Ana Matos'),
    ('marca desconhecida, modelo Corsa 1.2.', 'Corsa 1.2'),
    ('marca Opel, modelo Enviar Documentos.', 'Opel'),
    ('modelo Corsa 1.2.', 'Corsa 1.2'),
    ('relatado pelo Senhor Desembargador Deve Pagar,', 'Deve Pagar'),
    ('(Ana Matos, outra informação)', 'Ana Matos'),
    ('www.example.org', 'www.example.org'),
    ('na página da internet www.example.org/path', 'www.example.org'),
])
def test_incomplete_context_does_not_bless_literal(source, unproved):
    assert unproved not in extract_locked_tokens(prepare(source))


@pytest.mark.parametrize('source,unproved', [
    ('Relação de Lisboa', 'Lisboa'),
    ('Acórdão da Relação de Lisboa sem data', 'Lisboa'),
    ('Acórdão da Relação de Deve Pagar de 12 de Março de 2031', 'Deve Pagar'),
    ('Acórdão da Relação de Lisboa | Coimbra de 12 de Março de 2031', 'Lisboa'),
    ('Acórdão da Relação de Lisboa\f de 12 de Março de 2031', 'Lisboa'),
    ('artigo 45º, al. xyz)', 'xyz'),
    ('artigo 45º, al. x palavra', 'x'),
    ('artigo 45º, festival. x)', 'x'),
])
def test_court_and_citation_fields_require_complete_source_attribution(source, unproved):
    assert unproved not in extract_locked_tokens(prepare(source))


@pytest.mark.parametrize('source,target', [
    ('artigo 45º, al. x)', 'المادة 45، الفقرة y)'),
    ('artigo 45º, al. x)', 'المادة 45، الفقرة x) وx)'),
    ('artigo 45º, al. x) e 48º, al. z)', 'المادة 45، الفقرة z) و48، الفقرة x)'),
    ('Acórdão da Relação de Lisboa de 12 de Março de 2031',
     'حكم محكمة الاستئناف في Coimbra بتاريخ 12 من مارس 2031'),
])
def test_changed_repeated_or_reordered_citation_components_are_rejected(source, target):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source), target)


def test_previous_numeric_only_wrappers_recover_without_visible_changes():
    source = 'Acórdão da Relação de Lisboa de [[12]] de Março de [[2031]], artigo [[45]]º, al. x)'
    target = 'حكم محكمة الاستئناف في Lisboa بتاريخ [[12]] من مارس [[2031]]، المادة [[45]]، الفقرة x)'
    normalized = normalize(source, target)
    assert extract_locked_tokens(normalized) == ['Lisboa', '12', '2031', '45', 'x']
    strip = lambda text: text.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '')
    assert strip(normalized) == strip(target)


@pytest.mark.parametrize('label', ['b)', 'ب)'])
def test_inline_clause_and_line_enumerator_keep_distinct_roles(label):
    source = 'b) Conferir o artigo 45º, al. b)'
    target = f'{label} راجع المادة 45، الفقرة b)'
    result = normalize(prepare(source), target)
    assert result.startswith(label if label == 'ب)' else '\u2066[[b)]]')
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source), target.replace('الفقرة b)', 'الفقرة c)'))


@pytest.mark.parametrize('label', ['al.', 'alínea'])
@pytest.mark.parametrize('boundary', ['\n', '\r\n', '\f', '\v', '|'])
def test_subparagraph_never_crosses_line_or_table_boundary(label, boundary):
    assert 'x' not in extract_locked_tokens(prepare(f'artigo 45º, {label}{boundary}x)'))


def test_subparagraph_glossary_label_remains_translatable():
    from legalpdf_translate.glossary import GlossaryEntry
    from legalpdf_translate.structured_glossary import build_structured_glossary
    source, target = 'artigo 45º, al. x)', 'المادة 45، الفقرة x)'
    entry = GlossaryEntry('al.', 'الفقرة', 'exact', 'PT', 1)
    glossary = build_structured_glossary([{'id': 'p0001_b0001', 'text': source}], [entry], target_lang='AR')
    contract = glossary.for_block('p0001_b0001')
    assert normalize(prepare(source, glossary_contract=contract), target, glossary_contract=contract)
    assert contract.entries[0].preferred_translation == entry.preferred_translation


def test_proved_name_does_not_globally_allow_an_unattributed_longer_name():
    source = 'A Magistrada do Ministério Público,\nAna Matos\nOutro assunto: Ana Matos Pereira'
    assert extract_locked_tokens(prepare(source)) == ['Ana Matos']
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source), 'قاضية النيابة\nAna Matos\nموضوع آخر Ana Matos Pereira')


def test_explicit_abbreviations_do_not_create_a_general_uppercase_allowlist():
    approved = 'TIR PGR MP RMP CRC SPP SIMP'
    assert extract_locked_tokens(prepare(approved)) == approved.split()
    assert extract_locked_tokens(prepare('ABC UNKNOWN')) == []
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare('ABC UNKNOWN'), 'ABC UNKNOWN')


@pytest.mark.parametrize('boundary', ['\f', '\v', '\x85', '\u2028', '\u2029', '|'])
def test_citation_authority_cannot_cross_hard_or_table_boundary(boundary):
    source = f'(Ana Matos, «Título{boundary}outro trecho», in RMP nº 12)'
    assert 'Ana Matos' not in extract_locked_tokens(prepare(source))


@pytest.mark.parametrize('make', ['Citroën', 'Citroe\u0308n', 'Škoda'])
def test_source_vehicle_fields_preserve_accented_characters(make):
    source = f'marca {make}, modelo C3.'
    target = f'علامة {make}، الطراز C3.'
    assert extract_locked_tokens(prepare(source)) == [make, 'C3']
    assert extract_locked_tokens(normalize(prepare(source), target)) == [make, 'C3']
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source), target.replace(make, 'Citroen'))


def test_entity_protection_fails_closed_on_conflicting_saved_glossary_preference():
    from legalpdf_translate.glossary import GlossaryEntry
    from legalpdf_translate.structured_glossary import StructuredGlossaryError, build_structured_glossary
    source = 'marca Opel, modelo Corsa 1.2.'
    with pytest.raises(StructuredGlossaryError, match='incompatible_glossary_literal_contract'):
        build_structured_glossary([{'id': 'p0001_b0001', 'text': source}],
            [GlossaryEntry('marca Opel', 'علامة أوبل', 'exact', 'PT', 1)], target_lang='AR')


@pytest.mark.parametrize('source,unproved', [
    ('residente na Rua das Flores, Apresentar Documentos, concelho de Porto,',
     'Rua das Flores, Apresentar Documentos'),
    ('residente na Rua das Flores, n.º 12, Apresentar Documentos, 4000-123 Porto, concelho de Porto,',
     'Rua das Flores, n.º 12, Apresentar Documentos, 4000-123 Porto'),
    ('marca Opel, modelo 12 Entregar Multa.', 'Opel'),
    ('marca Opel, modelo Corsa Entregar Multa.', 'Opel'),
    ('A Juiz de Direito\nJuiz Substituto', 'Juiz Substituto'),
    ('A Juiz de Direito\nJuíza Substituta', 'Juíza Substituta'),
    ('O Procurador da República\nProcurador Adjunto', 'Procurador Adjunto'),
    ('A Magistrada do Ministério Público\nMagistrada Substituta', 'Magistrada Substituta'),
    ('A Juiz de Direito\nDesembargador Substituto', 'Desembargador Substituto'),
])
def test_entity_labels_do_not_protect_following_instructions_or_roles(source, unproved):
    assert unproved not in extract_locked_tokens(prepare(source))


@pytest.mark.parametrize('phrase,target', [
    ('Rua das Flores', 'شارع الزهور'),
    ('residente na Rua das Flores', 'المقيم في شارع الزهور'),
])
def test_partial_entity_overlap_cannot_silently_override_saved_preference(phrase, target):
    from legalpdf_translate.glossary import GlossaryEntry
    from legalpdf_translate.structured_glossary import StructuredGlossaryError, build_structured_glossary
    source = 'residente na Rua das Flores, n.º 12, 4000-123 Porto, concelho de Porto,'
    with pytest.raises(StructuredGlossaryError, match='incompatible_glossary_literal_contract'):
        build_structured_glossary([{'id': 'p0001_b0001', 'text': source}],
            [GlossaryEntry(phrase, target, 'exact', 'PT', 1)], target_lang='AR')


def test_residence_number_alias_stays_translatable_without_changing_preferences():
    from legalpdf_translate.glossary import GlossaryEntry
    from legalpdf_translate.structured_glossary import build_structured_glossary
    source, target, expected = PAIRS[4]
    entry = GlossaryEntry('n.º', 'رقم', 'exact', 'PT', 1)
    glossary = build_structured_glossary([{'id': 'p0001_b0001', 'text': source}], [entry], target_lang='AR')
    contract = glossary.for_block('p0001_b0001')
    assert contract.entries[0].preferred_translation == entry.preferred_translation
    assert extract_locked_tokens(normalize(prepare(source, glossary_contract=contract), target,
                                          glossary_contract=contract)) == expected


@pytest.mark.parametrize('phrase,target', [('das Flores', 'الزهور'), ('Matos', 'ماتوس')])
def test_glossary_subphrase_inside_source_entity_fails_closed(phrase, target):
    from legalpdf_translate.glossary import GlossaryEntry
    from legalpdf_translate.structured_glossary import StructuredGlossaryError, build_structured_glossary
    source = PAIRS[4][0] + '\nA Juiz de Direito\nAna Matos'
    with pytest.raises(StructuredGlossaryError, match='incompatible_glossary_literal_contract'):
        build_structured_glossary([{'id': 'p0001_b0001', 'text': source}],
            [GlossaryEntry(phrase, target, 'exact', 'PT', 1)], target_lang='AR')


def test_compatible_partial_overlap_preserves_exact_configured_translation():
    from legalpdf_translate.glossary import GlossaryEntry
    from legalpdf_translate.structured_glossary import build_structured_glossary
    source = 'A Juiz de Direito\nAna Matos'
    entry = GlossaryEntry('Matos', 'Matos', 'exact', 'PT', 1)
    glossary = build_structured_glossary([{'id': 'p0001_b0001', 'text': source}], [entry], target_lang='AR')
    assert [item for item in glossary.for_block('p0001_b0001').entries
            if item.source_text == entry.source_text] == [entry]


@pytest.mark.parametrize('index', range(len(PAIRS)))
def test_real_structured_adapter_accepts_entities_once_without_correction(index, tmp_path, monkeypatch):
    from copy import deepcopy
    import json
    from types import SimpleNamespace
    import time
    from legalpdf_translate.document_structure import PageStructure, StructureBlock, text_sha256
    from legalpdf_translate.openai_client import ApiCallResult
    from legalpdf_translate.types import PageStatus
    from tests.test_structured_arabic_source_names import make_adapter
    source, target, expected = PAIRS[index]
    adapter = make_adapter(monkeypatch)
    page = PageStructure(page_number=1, source_sha256=text_sha256(source),
        source_text_sha256=text_sha256(source), source_file_sha256='1' * 64,
        blocks=[StructureBlock(id='p0001_b0001', text=source)])
    original, calls = deepcopy(page.to_dict()), []

    def create(**kwargs):
        calls.append(kwargs)
        assert len(calls) == 1
        payload, _ = json.JSONDecoder().raw_decode(kwargs['prompt_text'])
        assert extract_locked_tokens(payload['blocks'][0]['text']) == expected
        return ApiCallResult(raw_output=json.dumps({'blocks': [{'id': page.blocks[0].id, 'text': target}]}),
            usage={'input_tokens': 10, 'output_tokens': 15, 'total_tokens': 25},
            response_id='synthetic', response_status='completed', model='synthetic', effort='high')

    result = adapter.translate(client=SimpleNamespace(create_page_response=create), source=page,
        paths=SimpleNamespace(pages_dir=tmp_path / 'pages'), page_number=1, total_pages=1,
        context_text=None, image_data_url=None, image_detail='low', effort='high',
        metadata={'api_calls_count': 0, 'transport_retries_count': 0}, started=time.perf_counter())
    assert result.status == PageStatus.DONE and not result.retry_used and len(calls) == 1
    assert result.page_metadata['fidelity_review_status'] == 'not_evaluated'
    assert page.to_dict() == original
