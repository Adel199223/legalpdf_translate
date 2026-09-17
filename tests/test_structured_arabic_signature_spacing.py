"""Synthetic paragraph spacing in exact supported judicial signatures."""
import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError,
    normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
)


NAME = 'Ana Maria Matos'
TITLE = 'A Juiz de Direito'


def visible(text):
    return text.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '')


def duplicate_source(gap='\n\n', newline='\n'):
    return (f'Assinado em 12-03-2027, por{newline}{NAME}, Juiz de Direito'
            f'{newline}{newline}{TITLE}{gap}{NAME}')


def duplicate_target():
    return f'تم التوقيع في 12-03-2027\n{NAME}، القاضية\n\nالقاضية\n\n{NAME}'


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('blank', ['', ' \t'])
def test_single_blank_keeps_digital_and_standalone_name_occurrences(newline, blank):
    original = duplicate_source(newline + blank + newline, newline)
    prepared = prepare(original)
    assert extract_locked_tokens(prepared) == ['12-03-2027', NAME, NAME]
    assert visible(prepared) == original
    assert prepare(prepared) == prepared
    target = duplicate_target()
    normalized = normalize(prepared, target)
    assert extract_locked_tokens(normalized) == ['12-03-2027', NAME, NAME]
    assert visible(normalized) == target
    assert normalize(prepared, normalized) == normalized


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('blank', ['', ' \t'])
@pytest.mark.parametrize('abbreviation', ['d.s', 'd.s.'])
@pytest.mark.parametrize('retained', [False, True])
def test_complete_signature_chain_allows_one_blank_at_each_step(newline, blank, abbreviation, retained):
    gap = newline + blank + newline
    original = f'Lisboa, {abbreviation}{gap}{TITLE}{gap}{NAME}'
    prepared = prepare(original)
    assert visible(prepared) == original
    assert extract_locked_tokens(prepared) == ['Lisboa', NAME]
    date = abbreviation if retained else 'التاريخ أعلاه'
    target = f'Lisboa، {date}\n\nالقاضية\n\n{NAME}'
    normalized = normalize(prepared, target)
    assert extract_locked_tokens(normalized) == ['Lisboa', *([abbreviation] if retained else []), NAME]
    assert visible(normalized) == target
    assert normalize(prepared, normalized) == normalized


@pytest.mark.parametrize('gap', [
    '\n\n\n', '\r\n \t\r\n\t\r\n',
    '\nOutro assunto\n', '\n|\n', '\n \t| \t\n',
    *('\n' + boundary + '\n' for boundary in '\v\f\x1c\x1d\x1e\x85\u2028\u2029'),
])
def test_standalone_signature_does_not_cross_extra_blanks_or_other_content(gap):
    original = f'{TITLE}{gap}{NAME}'
    assert NAME not in extract_locked_tokens(prepare(original))
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(original), f'القاضية\n{NAME}')


@pytest.mark.parametrize('gap', ['\n\n\n', '\nOutro assunto\n', '\n|\n', '\n\f\n', '\n\u2029\n'])
@pytest.mark.parametrize('step', ['place_title', 'title_name'])
def test_incomplete_chain_cannot_prove_place_or_optional_date(gap, step):
    before, after = (gap, '\n\n') if step == 'place_title' else ('\n\n', gap)
    original = f'Lisboa, d.s.{before}{TITLE}{after}{NAME}'
    prepared = prepare(original)
    assert 'Lisboa' not in extract_locked_tokens(prepared)
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepared, f'Lisboa، d.s.\nالقاضية\n{NAME}')


@pytest.mark.parametrize('title', ['Juiz de Direito', 'A Juiz de Direito Adjunto', 'Pessoa responsável'])
def test_blank_does_not_expand_supported_title_allowlist(title):
    original = f'Lisboa, d.s.\n\n{title}\n\n{NAME}'
    assert NAME not in extract_locked_tokens(prepare(original))
    assert 'Lisboa' not in extract_locked_tokens(prepare(original))


@pytest.mark.parametrize('name', ['Deve Pagar', 'Juiz Substituto', 'Apresentar documentos amanhã.'])
def test_blank_does_not_prove_role_or_instruction_as_name(name):
    assert name not in extract_locked_tokens(prepare(f'{TITLE}\n\n{name}'))


@pytest.mark.parametrize('count', [0, 1, 3])
def test_duplicate_signature_name_still_requires_exact_target_count(count):
    prepared = prepare(duplicate_source())
    target = 'تم التوقيع في 12-03-2027\nالقاضية\n' + '\n'.join([NAME] * count)
    with pytest.raises(StructuredArabicLiteralError, match='source_literal_coverage_mismatch') as caught:
        normalize(prepared, target)
    assert caught.value.details == {
        'missing_literal_count': max(2 - count, 0),
        'duplicated_literal_count': max(count - 2, 0),
        'expected_literal_count': 3,
        'actual_literal_count': count + 1,
    }
