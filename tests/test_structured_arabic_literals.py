"""Synthetic literals, not retained provider responses or private case content."""
from __future__ import annotations

import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens, pretokenize_arabic_source
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError,
    normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
)
from legalpdf_translate.validators import validate_ar


ADDRESS = 'Largo Eng. Álvaro Mendes - 1200-345 Lisboa'
NAME = 'João Guerreiro'


def visible(value):
    return value.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '')


def accepted(source, translation, **options):
    result = normalize(prepare(source, **options), translation)
    assert validate_ar(result).ok
    assert visible(result) == visible(translation)
    return result


@pytest.mark.parametrize('translation', [
    ADDRESS,
    f'[[{ADDRESS}]]',
    '[[Largo Eng. Álvaro Mendes - ]]\u2066[[1200-345]]\u2069[[ Lisboa]]',
    '[[Largo Eng. Álvaro]] [[Mendes - 1200-345 Lisboa]]',
])
def test_coherent_address_does_not_depend_on_model_token_segmentation(translation):
    result = accepted(ADDRESS, translation, role='footer')
    assert extract_locked_tokens(result) == [ADDRESS]
    assert result == f'\u2066[[{ADDRESS}]]\u2069'


def test_legacy_postcode_only_source_is_upgraded_from_exact_visible_address():
    old_source = pretokenize_arabic_source(ADDRESS)
    assert extract_locked_tokens(old_source) == ['1200-345']
    result = normalize(old_source, f'[[{ADDRESS}]]')
    assert extract_locked_tokens(result) == [ADDRESS]
    # No mutation to the legacy pre-tokenizer or legacy validator contract.
    assert not validate_ar(result, expected_tokens=['1200-345']).ok


@pytest.mark.parametrize('source,role,literal', [
    ('Morada: Rua das Flores 8', 'address', 'Rua das Flores 8'),
    ('Rua das Flores 8', 'address', 'Rua das Flores 8'),
    ('1200-345 Lisboa', 'body', '1200-345 Lisboa'),
    ('Nome: João Guerreiro', 'body', NAME),
    ('Élodie Müller', 'signature', 'Élodie Müller'),
    ('Łukasz Żak', 'signature', 'Łukasz Żak'),
    ('Jean-Luc Martin', 'signature', 'Jean-Luc Martin'),
    ('- 5 -', 'footer', '- 5 -'),
    ('5/11', 'footer', '5/11'),
    ('5', 'body', '5'),
])
def test_preparation_roundtrip_for_explicit_literal_categories(source, role, literal):
    prepared = prepare(source, role=role)
    assert visible(prepared) == source
    assert literal in extract_locked_tokens(prepared)
    assert accepted(source, f'[[{literal}]]', role=role)


@pytest.mark.parametrize('translation', [
    'الشاهد João Guerreiro حضر.',
    'الشاهد [[João]] [[Guerreiro]] حضر.',
    'الشاهد \u2066[[João Guerreiro]]\u2069 حضر.',
])
def test_exact_accented_name_gets_one_continuous_isolated_run(translation):
    result = accepted(f'Testemunha: {NAME} compareceu.', translation, protected_names=[NAME])
    assert extract_locked_tokens(result) == [NAME]


@pytest.mark.parametrize('changed', [
    'Joao Guerreiro', 'João Guerrelro', 'João Guerreir0', 'JOÃO GUERREIRO',
    'Guerreiro João', 'João  Guerreiro', 'João GuerreiroX',
])
def test_names_are_not_fuzzily_repaired(changed):
    prepared = prepare(f'Nome: {NAME}', protected_names=[NAME])
    with pytest.raises(StructuredArabicLiteralError, match='source_literal_coverage_mismatch'):
        normalize(prepared, f'الشاهد [[{changed}]]')


@pytest.mark.parametrize('changed', [
    ADDRESS.replace('1200-345', '1200-354'),
    ADDRESS.replace('Álvaro', 'Alvaro'),
    ADDRESS.replace('Lisboa', 'Porto'),
    ADDRESS.replace(' - ', ' '),
    ADDRESS.replace('Mendes', 'Mendes Mendes'),
])
def test_address_visible_text_must_be_exact(changed):
    with pytest.raises(StructuredArabicLiteralError, match='source_literal_coverage_mismatch'):
        accepted(ADDRESS, f'[[{changed}]]')


@pytest.mark.parametrize('translation,code', [
    ('الاسم [[João Guerreiro]] [[João Guerreiro]]', 'source_literal_coverage_mismatch'),
    ('الاسم', 'source_literal_coverage_mismatch'),
    ('[[Élodie Müller]] ثم [[João Guerreiro]]', 'source_literal_association_mismatch'),
])
def test_name_coverage_and_association_are_not_only_a_set_comparison(translation, code):
    source = f'Nome: {NAME}'
    names = [NAME]
    if 'Müller' in translation:
        source += '\nNome: Élodie Müller'
        names += ['Élodie Müller']
    with pytest.raises(StructuredArabicLiteralError, match=code):
        normalize(prepare(source, protected_names=names), translation)


def test_independent_addresses_cannot_be_reassociated_by_reordering():
    other = 'Rua das Flores - 4000-123 Porto'
    source = prepare(f'{ADDRESS}\n{other}')
    with pytest.raises(StructuredArabicLiteralError, match='source_literal_association_mismatch'):
        normalize(source, f'[[{other}]]\n[[{ADDRESS}]]')


def test_names_remain_associated_with_their_addresses():
    other_name = 'Élodie Müller'
    other_address = 'Rua das Flores - 4000-123 Porto'
    source = prepare(f'Nome: {NAME}\n{ADDRESS}\nNome: {other_name}\n{other_address}')
    translation = f'[[{NAME}]]\n[[{other_address}]]\n[[{other_name}]]\n[[{ADDRESS}]]'
    with pytest.raises(StructuredArabicLiteralError, match='source_literal_association_mismatch'):
        normalize(source, translation)


@pytest.mark.parametrize('translation', [
    'جلسة [[16/03/2027]] والاستجواب [[12/03/2027]]',
    'جلسة [[12/03/2027]] والاستجواب [[17/03/2027]]',
    'جلسة [[12/03/2027]]',
    'جلسة [[12/03/2027]] والاستجواب [[16/03/2027]] [[16/03/2027]]',
])
def test_swapped_altered_missing_and_duplicated_dates_fail(translation):
    source = prepare('Audiência 12/03/2027; interrogatório 16/03/2027.')
    with pytest.raises(StructuredArabicLiteralError):
        normalize(source, translation)


def test_month_words_are_translated_but_digits_stay_exact():
    source = prepare('Prazo: [[12 de março de 2027]].')
    assert extract_locked_tokens(source) == ['12', '2027']
    result = normalize(source, 'الأجل [[12]] مارس [[2027]].')
    assert validate_ar(result).ok
    with pytest.raises(StructuredArabicLiteralError, match='unsupported_latin_or_digit_content'):
        normalize(source, 'الأجل [[12 de março de 2027]].')


def test_citations_numeric_values_and_identifier_order_stay_exact():
    source = 'Artigo 281 do CPP; processo 987/27.4ABCXY; total 12,50 EUR.'
    good = 'المادة [[281]] من [[CPP]]؛ القضية [[987/27.4ABCXY]]؛ المبلغ [[12,50]] [[EUR]].'
    assert accepted(source, good)
    for old, new in [('281', '282'), ('987/27.4ABCXY', '987/27.4ABCXZ'), ('12,50', '12.50')]:
        with pytest.raises(StructuredArabicLiteralError):
            normalize(prepare(source), good.replace(old, new))


def test_standalone_source_abbreviations_and_contact_literals_are_protected():
    source = 'GNR: 212345678; IMT; Email: exemplo@tribunais.example; https://example.org/1'
    translation = '[[GNR]]: [[212345678]]؛ [[IMT]]؛ البريد [[exemplo@tribunais.example]]؛ [[https://example.org/1]]'
    assert accepted(source, translation)


@pytest.mark.parametrize('translation', [
    '[[Deve pagar o montante no prazo indicado.]]',
    'Deve pagar o montante no prazo indicado.',
    '[[deve]] دفع المبلغ في الأجل المحدد.',
])
def test_latin_legal_prose_cannot_hide_inside_output_tokens(translation):
    with pytest.raises(StructuredArabicLiteralError, match='unsupported_latin_or_digit_content'):
        normalize(prepare('Deve pagar o montante no prazo indicado.'), translation)


@pytest.mark.parametrize('role', ['body', 'address', 'signature', 'heading'])
def test_roles_do_not_turn_obligations_into_protected_prose(role):
    text = 'Deve pagar o montante de 25 EUR no prazo indicado.'
    prepared = prepare(text, role=role)
    assert extract_locked_tokens(prepared) == ['25', 'EUR']
    with pytest.raises(StructuredArabicLiteralError, match='unsupported_latin_or_digit_content'):
        normalize(prepared, f'[[{text}]]')


def test_heading_is_not_misidentified_as_a_person_or_whole_latin_literal():
    source = prepare('Prova Documental', role='heading')
    assert source == 'Prova Documental'
    assert accepted(source, 'الأدلة المستندية')
    with pytest.raises(StructuredArabicLiteralError):
        normalize(source, '[[Prova Documental]]')


def test_lists_and_punctuation_only_blocks_do_not_invent_content():
    prepared = prepare('  a) Prova\n  b) Testemunhas')
    assert extract_locked_tokens(prepared) == ['a)', 'b)']
    assert accepted('  a) Prova\n  b) Testemunhas', '  [[a)]] الدليل\n  [[b)]] الشهود')
    assert prepare('Foi chamado e. Depois saiu.') == 'Foi chamado e. Depois saiu.'
    assert accepted('*\n*', '*\n*')


def test_verified_arabic_enumeration_keeps_name_and_date_association():
    source = f'b) {NAME}, testemunha em 08.07.2026.'
    translation = f'ب) [[{NAME}]]، شاهد في [[08.07.2026]].'
    result = accepted(source, translation, protected_names=[NAME])
    assert result.startswith('ب) ')
    assert extract_locked_tokens(result) == [NAME, '08.07.2026']


@pytest.mark.parametrize('translation', [
    'أ) الدليل\nب) الشاهد', '[[أ)]] الدليل\n[[ب)]] الشاهد',
    '[[a)]] الدليل\nب) الشاهد',
])
def test_explicit_arabic_enumerator_mapping_is_not_ltr_packaged(translation):
    result = accepted('a) Prova\nb) Testemunha', translation)
    assert '[[أ)]]' not in result and '[[ب)]]' not in result


@pytest.mark.parametrize('translation', [
    'ب) الدليل\nأ) الشاهد', 'أ) الدليل\nج) الشاهد',
    'الدليل\nب) الشاهد', 'أ) الدليل\nب) الشاهد\nب) الشاهد',
    'الدليل أ)\nالشاهد ب)', 'أ. الدليل\nب) الشاهد',
    'أ) الدليل\nب)الشاهد',
    'أ) الدليل\nب) الشاهد\nج) الإضافة',
    'أ) الدليل\nب) الشاهد\nهـ) الإضافة',
    'الدليل [[a)]]\nالشاهد [[b)]]',
])
def test_enumerator_changes_drops_duplicates_reordering_or_movement_fail(translation):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare('a) Prova\nb) Testemunha'), translation)


def test_unapproved_enumerator_mapping_does_not_silently_drop_source_label():
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare('e) Prova'), 'هـ) الدليل')


def test_preparation_idempotence_for_names_addresses_contact_and_list_labels():
    source = f'b) {NAME}, testemunha em 08.07.2026.\n{ADDRESS}\n5\nCPP; 12,50 EUR.'
    prepared = prepare(source, protected_names=[NAME])
    assert prepare(prepared, protected_names=[NAME]) == prepared
    assert prepare(prepared) == prepared
    assert visible(prepared) == source


@pytest.mark.parametrize('source', ['[[Deve.pagar]]', '[[Deve Pagar]]'])
def test_source_wrapper_cannot_bless_obligation_prose(source):
    with pytest.raises(StructuredArabicLiteralError, match='unsupported_source_literal'):
        prepare(source)


@pytest.mark.parametrize('text', ['[[', ']]', '[[]]', '[[bad [[nested]]]]'])
def test_malformed_protocol_tokens_fail_safely(text):
    with pytest.raises(StructuredArabicLiteralError, match='malformed_structured_arabic_tokens'):
        prepare(text)
    with pytest.raises(StructuredArabicLiteralError, match='malformed_structured_arabic_tokens'):
        normalize('سلام', text)


@pytest.mark.parametrize('options', [
    {'protected_names': 'João Guerreiro'}, {'protected_names': None},
    {'protected_names': ['Someone Absent']}, {'protected_names': ['deve pagar']},
    {'role': None},
])
def test_invalid_source_options_fail_before_translation(options):
    with pytest.raises(StructuredArabicLiteralError):
        prepare('Nome: João Guerreiro', **options)


def test_errors_include_only_safe_codes_and_counters_not_private_text():
    with pytest.raises(StructuredArabicLiteralError) as caught:
        normalize(prepare(f'Nome: {NAME}'), '[[Wrong Person]]')
    error = caught.value
    assert error.code == str(error) == 'source_literal_coverage_mismatch'
    assert error.details == {'missing_literal_count': 1, 'duplicated_literal_count': 0,
                             'expected_literal_count': 1, 'actual_literal_count': 0}
    assert all(type(value) is int for value in error.details.values())
    assert NAME not in repr(error) and 'Wrong Person' not in repr(error)


def test_unknown_additional_digits_or_names_are_not_allowed():
    for translation in ('سلام [[8]]', 'سلام [[Unknown Person]]', 'سلام ٨'):
        with pytest.raises(StructuredArabicLiteralError, match='unsupported_latin_or_digit_content'):
            normalize('Saudação', translation)


def test_exact_name_substring_inside_a_different_larger_name_does_not_pass():
    with pytest.raises(StructuredArabicLiteralError, match='source_literal_coverage_mismatch'):
        normalize(prepare(f'Nome: {NAME}'), f'X{NAME}')


def test_normalization_is_idempotent_and_does_not_rewrite_punctuation():
    source = prepare(f'Nome: {NAME}\n{ADDRESS}')
    translation = f'الاسم: [[{NAME}]]؛\nالعنوان: [[{ADDRESS}]].'
    normalized = normalize(source, translation)
    assert normalize(source, normalized) == normalized
    assert visible(normalized) == visible(translation)


@pytest.mark.parametrize('source,translation', [
    ('Destinatário: João Guerreiro', 'المرسل إليه: João Guerreiro'),
    ('DESTINATÁRIA: Élodie Müller', 'المرسل إليها: Élodie Müller'),
    ('Documento de identificação | João Guerreiro', 'وثيقة الهوية | João Guerreiro'),
    ('O destinatário João Guerreiro deve apresentar os documentos.',
     'يجب على المرسل إليه João Guerreiro تقديم المستندات.'),
    ('A testemunha indicada neste exemplo é Nuno Carrujo.',
     'الشاهد المذكور في هذا المثال هو Nuno Carrujo.'),
    ('João Guerreiro declarou que recebeu a notificação.',
     'صرّح João Guerreiro بأنه تسلّم الإخطار.'),
    ('Foi ouvido João Guerreiro como testemunha.', 'سُمعت أقوال João Guerreiro بصفته شاهداً.'),
    ('João Guerreiro, arguido neste processo, compareceu.',
     'حضر João Guerreiro، المتهم في هذه القضية.'),
])
@pytest.mark.parametrize('wrapped', [False, True])
def test_person_context_protects_exact_source_names_without_caller_hints(source, translation, wrapped):
    name = 'Élodie Müller' if 'Élodie' in source else 'Nuno Carrujo' if 'Nuno' in source else NAME
    prepared = prepare(source)
    assert visible(prepared) == source
    assert extract_locked_tokens(prepared) == [name]
    output = translation.replace(name, f'[[{name}]]') if wrapped else translation
    normalized = normalize(prepared, output)
    assert validate_ar(normalized).ok
    assert visible(normalized) == translation
    assert extract_locked_tokens(normalized) == [name]
    assert normalized.count(f'\u2066[[{name}]]\u2069') == 1
