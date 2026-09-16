"""Bounded source-attributed reference fields for Arabic structured translation.

No target text, I/O, case repair, institution lookup or general uppercase rule.
The caller supplies its existing exact name/address/place predicates. Titles,
quoted substantive text and the surrounding legal clauses stay translatable.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Callable


@dataclass(frozen=True)
class SourceEntitySpans:
    literals: tuple[tuple[int, int], ...] = ()
    persons: tuple[tuple[int, int], ...] = ()
    signature_abbreviations: tuple[tuple[int, int], ...] = ()


_HARD = '\v\f\x1c\x1d\x1e\x85\u2028\u2029'
_DIGITAL_DATE = re.compile(r'Assinado em[ \t]+[0-9]{2}-[0-9]{2}-[0-9]{4},[ \t]+por\Z', re.I)
_DIGITAL_NAME = re.compile(r'(?P<name>[^,\r\n]{1,160}),[ \t]*(?:Juiz de Direito|Procurador da República)\Z', re.I)
_SIGNATURE_TITLE = re.compile(
    r'(?:A Juiz de Direito|O Juiz de Direito|A Juíza de Direito|'
    r'A Magistrada do Ministério Público|O Magistrado do Ministério Público|'
    r'O Procurador da República|A Procuradora da República),?\Z', re.I)
_SIGNATURE_PLACE = re.compile(r'(?P<place>[^,\r\n]{1,120}),[ \t]*(?P<abbreviation>d\.s\.?)\Z')
_PARENTAGE = re.compile(
    r'(?i:Indiciam[ \t]+suficientemente[ \t]+que)[ \t]+'
    r'(?P<person>[^,\r\n]{1,160}),[ \t]*(?i:filh[oa][ \t]+de)[ \t]+'
    r'(?P<parent1>[^,\r\n;]{1,160}?)[ \t]+(?i:e[ \t]+de)[ \t]+'
    r'(?P<parent2>[^,\r\n;]{1,160}),[ \t]*(?i:nascid[oa][ \t]+em)(?=[ \t])')
_RESIDENCE = re.compile(
    r'(?i:(?<!\w)residente[ \t]+n[ao])[ \t]+(?P<address>[^\r\n;]{1,220}?),'
    r'[ \t]*(?i:concelho[ \t]+de)[ \t]+(?P<place>[^,;\r\n]{1,120})(?=,)')
_NUMBERED_ADDRESS = re.compile(
    r'(?P<street>[^,;\r\n]{1,120}),[ \t]*'
    r'(?i:n[ \t]*\.?[ºo°])[ \t]*[0-9]+(?:[A-Za-z])?,[ \t]*'
    r'(?P<postal>[0-9]{4}-[0-9]{3}[ \t]+(?P<city>[^,;\r\n]{1,80}))\Z')
_JUDICIAL_ROLE_WORD = re.compile(r'(?:juiz|juíza|desembargador[ae]?|desembargadora|'
    r'procurador[ae]?|procuradora|magistrad[oa])\Z', re.I)
_INCIDENT = re.compile(
    r'(?i:(?<!\w)na)[ \t]+(?P<address>[^\r\n;]{1,220}?),'
    r'[ \t]*(?i:o[ \t]+arguido[ \t]+conduzia)(?=[ \t,])')
_VEHICLE = re.compile(
    r'(?i:(?<!\w)marca)[ \t]+(?P<make>[^,\r\n;]{1,60}),[ \t]*'
    r'(?i:modelo)[ \t]+(?P<model>[^\r\n;]{1,80}?)(?=\.(?:[ \t]|$)|;|\r?$)', re.M)
_REPORTING_JUDGE = re.compile(
    r'(?i:(?<!\w)relatado[ \t]+pelo[ \t]+Senhor[ \t]+Desembargador)[ \t]+'
    r'(?P<name>[^,;:\r\n]{1,160})(?=,)')
_CITATION_AUTHOR = re.compile(
    r'\((?P<name>[^,;()\r\n]{1,160}),[ \t]*«[^»\r\n]{1,300}»,[ \t]*(?i:in)[ \t]+')
_WEBSITE = re.compile(
    r'(?i:(?<!\w)na[ \t]+página[ \t]+da[ \t]+internet)[ \t]+'
    r'(?P<domain>(?i:www\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}))'
    r'(?=[ \t\r\n,;)]|\.(?:[ \t\r\n]|$)|$)')
_COURT_CITATION = re.compile(
    r'(?i:(?<!\w)Acórdão[ \t]+d[ao][ \t]+(?:Tribunal[ \t]+d[ao][ \t]+)?'
    r'Relação[ \t]+d[aoe])[ \t]+(?P<place>[^,;:\r\n]{1,120}?)[ \t]+'
    r'(?i:de)[ \t]+(?:0?[1-9]|[12][0-9]|3[01])[ \t]+(?i:de)[ \t]+'
    r'(?i:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)'
    r'[ \t]+(?i:de)[ \t]+[0-9]{4}(?!\w)')
_SUBPARAGRAPH = re.compile(
    r'(?i:(?<!\w)(?:al\.|alínea))[ \t]+(?P<letter>[a-z])(?=\))')


def _lines(text):
    result, offset = [], 0
    for raw in text.splitlines(keepends=True):
        value = raw.rstrip('\r\n').strip(' \t')
        start = offset + len(raw) - len(raw.lstrip(' \t'))
        # None distinguishes a hard/table boundary from a permitted blank line.
        result.append((None if any(char in raw for char in _HARD) or '|' in value else value, start))
        offset += len(raw)
    return result


def _field(text, match, group):
    start, end = match.span(group)
    raw = text[start:end]
    start += len(raw) - len(raw.lstrip(' \t'))
    end -= len(raw) - len(raw.rstrip(' \t'))
    return text[start:end], (start, end)


def _vehicle_field(value, *, model=False):
    # The supported form is one proper name/code, optionally followed by a
    # bounded numeric/alphanumeric model code. Never arbitrary title-case prose.
    words = value.split(' ')
    if not 1 <= len(words) <= (2 if model else 1):
        return False
    if len(words) == 2 and not re.fullmatch(r'(?=[A-Za-z0-9./-]*[0-9])[A-Za-z0-9]+(?:[./-][A-Za-z0-9]+)*', words[1]):
        return False
    return bool(value and all(word and (word[0].isupper() or word[0].isdigit())
        and all(unicodedata.name(char, '').startswith('LATIN ') or char.isdecimal()
                or unicodedata.category(char).startswith('M') or char in '-./' for char in word)
        for word in words) and not set(unicodedata.normalize('NFC', value).casefold().split()) & {
            'desconhecido', 'desconhecida', 'não', 'apurado', 'apurada', 'enviar', 'documentos',
            'deve', 'pagar', 'obrigação', 'prova', 'marca', 'modelo'})


def _matches(regex, text):
    for match in regex.finditer(text):
        if not any(char in match[0] for char in _HARD) and '|' not in match[0]:
            yield match


def extract_source_entities(text: str, *, valid_name: Callable[[str], bool],
                            valid_address: Callable[[str], bool],
                            valid_place: Callable[[str], bool]) -> SourceEntitySpans:
    """Return exact ranges only after complete local source attribution."""
    supplied_name_check = valid_name
    valid_name = lambda value: supplied_name_check(value) and not any(
        _JUDICIAL_ROLE_WORD.fullmatch(unicodedata.normalize('NFC', word)) for word in value.split())
    literals, persons, abbreviations = [], [], []
    lines = _lines(text)
    for index, (line, offset) in enumerate(lines):
        if line is None:
            continue
        digital = _DIGITAL_NAME.fullmatch(line)
        if (digital and index and lines[index - 1][0] is not None
                and _DIGITAL_DATE.fullmatch(lines[index - 1][0])):
            name = digital['name'].strip(' \t')
            if valid_name(name):
                start = offset + digital.start('name')
                persons.append((start, start + len(name)))
        if _SIGNATURE_TITLE.fullmatch(line) and index + 1 < len(lines):
            name, start = lines[index + 1]
            if name is not None and valid_name(name):
                persons.append((start, start + len(name)))
        place_match = _SIGNATURE_PLACE.fullmatch(line)
        if place_match and valid_place(place_match['place']):
            following = index + 1
            if following < len(lines) and lines[following][0] == '':
                following += 1  # Only one explicit blank before the heading.
            if (following + 1 < len(lines) and lines[following][0] is not None
                    and _SIGNATURE_TITLE.fullmatch(lines[following][0])
                    and lines[following + 1][0] is not None and valid_name(lines[following + 1][0])):
                start = offset + place_match.start('place')
                literals.append((start, start + len(place_match['place'])))
                abbreviations.append((offset + place_match.start('abbreviation'),
                                      offset + place_match.end('abbreviation')))

    for match in _matches(_PARENTAGE, text):
        fields = [_field(text, match, key) for key in ('person', 'parent1', 'parent2')]
        if all(valid_name(value) for value, _ in fields):
            persons.extend(span for _, span in fields)
    for regex in (_REPORTING_JUDGE, _CITATION_AUTHOR):
        for match in _matches(regex, text):
            name, span = _field(text, match, 'name')
            if valid_name(name):
                persons.append(span)
    for match in _matches(_RESIDENCE, text):
        address, address_span = _field(text, match, 'address')
        place, place_span = _field(text, match, 'place')
        parts = _NUMBERED_ADDRESS.fullmatch(address)
        if parts and valid_address(parts['street']) and valid_place(parts['city']) and valid_place(place):
            # Keep labels and punctuation translatable (including configured
            # n.º aliases), not an opaque literal for the entire residence.
            literals.extend((address_span[0] + parts.start(key), address_span[0] + parts.end(key))
                            for key in ('street', 'postal'))
            literals.append(place_span)
    for match in _matches(_INCIDENT, text):
        address, span = _field(text, match, 'address')
        if valid_address(address):
            literals.append(span)
    for match in _matches(_VEHICLE, text):
        fields = [_field(text, match, key) for key in ('make', 'model')]
        if _vehicle_field(fields[0][0]) and _vehicle_field(fields[1][0], model=True):
            literals.extend(span for _, span in fields)
    for match in _matches(_WEBSITE, text):
        literals.append(match.span('domain'))
    for match in _matches(_COURT_CITATION, text):
        place, span = _field(text, match, 'place')
        if valid_place(place):
            literals.append(span)
    for match in _matches(_SUBPARAGRAPH, text):
        # Translate the label; retain only the exact source reference letter.
        # This cannot admit an arbitrary Latin word, digit or cross-line label.
        literals.append(match.span('letter'))
    return SourceEntitySpans(tuple(sorted(set(literals))), tuple(sorted(set(persons))),
                             tuple(sorted(set(abbreviations))))
