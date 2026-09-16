"""Synthetic judicial-officer signature attribution, never private names."""
import pytest

from legalpdf_translate.arabic_pre_tokenize import extract_locked_tokens
from legalpdf_translate.structured_arabic_literals import (
    StructuredArabicLiteralError, normalize_structured_arabic_translation as normalize,
    prepare_structured_arabic_source as prepare,
)


SOURCE = 'O/A Oficial de Justiça,\nAna Maria Alves Correia\nTécnico de Justiça'
TARGET = 'مأمور قضائي،\nAna Maria Alves Correia\nفني العدالة'
NAME = 'Ana Maria Alves Correia'


@pytest.mark.parametrize('newline', ['\n', '\r\n'])
@pytest.mark.parametrize('article', ['O/A', 'O', 'A'])
def test_complete_official_signature_proves_exact_source_name(newline, article):
    source = SOURCE.replace('O/A', article).replace('\n', newline)
    prepared = prepare(source)
    assert extract_locked_tokens(prepared) == [NAME]
    assert extract_locked_tokens(normalize(prepared, TARGET)) == [NAME]
    assert prepare(prepared) == prepared
    assert normalize(prepared, normalize(prepared, TARGET)) == normalize(prepared, TARGET)
    assert prepared.replace('[[', '').replace(']]', '') == source


def test_old_saved_prompt_recovery_preserves_every_visible_character():
    normalized = normalize(SOURCE, TARGET)
    assert normalized.replace('[[', '').replace(']]', '').replace('\u2066', '').replace('\u2069', '') == TARGET


@pytest.mark.parametrize('source', [
    SOURCE.replace('Justiça,\n', 'Justiça,\n\n'),
    SOURCE.replace('Correia\n', 'Correia\n\n'),
    SOURCE.replace('Justiça,\n', 'Justiça,\f'),
    SOURCE.replace('Correia\n', 'Correia\u2029'),
    SOURCE.replace('Correia\n', 'Correia\nOutro assunto\n'),
    SOURCE.replace('O/A Oficial', 'Uma referência ao Oficial'),
    SOURCE.replace('Técnico de Justiça', 'Informação adicional'),
    SOURCE.replace(NAME, NAME + ' | Luís Correia'),
    SOURCE.replace(NAME, 'Deve Pagar'),
    SOURCE.replace(NAME, NAME + ' Enviar Documentos'),
])
def test_incomplete_or_cross_boundary_signature_is_not_name_proof(source):
    assert NAME not in extract_locked_tokens(prepare(source))


@pytest.mark.parametrize('changed', [
    TARGET.replace(NAME, 'Ana Maria Alves Coreia'), TARGET.replace(NAME, ''), TARGET + '\n' + NAME,
    TARGET.replace(NAME, NAME + '\u0301'), TARGET.replace(NAME, 'Correia Ana Maria Alves'),
])
def test_name_misspelling_missing_duplicate_or_reordering_stays_rejected(changed):
    with pytest.raises(StructuredArabicLiteralError):
        normalize(prepare(SOURCE), changed)


def test_signature_does_not_cross_blocks():
    assert NAME not in extract_locked_tokens(prepare('O/A Oficial de Justiça,\n' + NAME))
    assert NAME not in extract_locked_tokens(prepare(NAME + '\nTécnico de Justiça'))
