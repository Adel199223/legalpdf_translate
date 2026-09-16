"""Synthetic complete signature chains and optional exact date abbreviations."""
import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError, normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
)


def source(abbreviation='d.s.', blank=''):
    return f'Lisboa, {abbreviation}\n{blank}A Juiz de Direito\nAna Maria Matos'


def target(abbreviation='d.s.'):
    return f'Lisboa، {abbreviation}\nالقاضية\nAna Maria Matos'


def visible(value):
    return value.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '')


@pytest.mark.parametrize('abbreviation', ['d.s', 'd.s.'])
@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('blank', ['', '\n'])
def test_exact_retention_and_existing_translation_both_work(abbreviation, newline, blank):
    original = source(abbreviation, blank).replace('\n', newline)
    prepared = prepare(original)
    assert extract_locked_tokens(prepared) == ['Lisboa', 'Ana Maria Matos']
    raw = target(abbreviation)
    normalized = normalize(prepared, raw)
    assert extract_locked_tokens(normalized) == ['Lisboa', abbreviation, 'Ana Maria Matos']
    assert visible(normalized) == raw
    assert normalize(prepared, normalized) == normalized
    translated = target('التاريخ أعلاه')
    assert visible(normalize(prepared, translated)) == translated


@pytest.mark.parametrize('original', [
    'd.s.', 'Data: d.s.', 'Lisboa, d.s.',
    source().replace('A Juiz de Direito', 'Outro assunto'),
    source().replace('Ana Maria Matos', 'Deve Pagar'),
    source(blank='\n\n'), source().replace('\n', '\f', 1),
    source().replace('\n', '\u2029', 1), source().replace(', d.s.', ' | d.s.'),
    source().replace('d.s.', 'd.s.\nTexto adicional'),
])
def test_unproved_context_does_not_admit_retained_abbreviation(original):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(original), target())


@pytest.mark.parametrize('changed', [
    target('D.S.'), target('d.s'), target('d.s..'), target('d.s.X'),
    target('d.s.\u0301'), target('d.s. d.s.'),
    'd.s. Lisboa،\nالقاضية\nAna Maria Matos',
    target() + '\nEnviar documentos',
])
def test_changed_duplicate_reordered_or_unrelated_latin_stays_rejected(changed):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source()), changed)


def test_short_variant_is_not_a_prefix_for_different_punctuation():
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(source('d.s')), target('d.s.'))


def test_mixed_variants_use_whole_spelling_and_source_order():
    original = source('d.s') + '\n\n' + source('d.s.').replace('Lisboa', 'Porto').replace('Ana Maria Matos', 'Luís Manuel Matos')
    raw = target('d.s') + '\n\n' + target('d.s.').replace('Lisboa', 'Porto').replace('Ana Maria Matos', 'Luís Manuel Matos')
    assert visible(normalize(prepare(original), raw)) == raw
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(original), raw.replace('d.s\n', 'd.s.\n', 1))


def test_retention_requires_all_proved_occurrences_of_selected_spelling():
    original = source() + '\n\n' + source().replace('Lisboa', 'Porto').replace('Ana Maria Matos', 'Luís Manuel Matos')
    raw = target() + '\n\n' + target('التاريخ أعلاه').replace('Lisboa', 'Porto').replace('Ana Maria Matos', 'Luís Manuel Matos')
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(original), raw)
