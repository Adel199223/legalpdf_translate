"""Strict source-associated Arabic literal packaging for the block protocol.

This is deliberately separate from the legacy Arabic normalizer/validator.
Only source-proven literal characters may survive in Latin/digit spans; token
boundaries are presentation, not evidence of a translation defect. No fuzzy
matching, accent repair, number substitution, provider call or file I/O occurs.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable

from .arabic_pre_tokenize import (
    BARCODE_RE, CASE_REF_RE, EMAIL_RE, IBAN_RE, LONG_TRACK_RE, POSTAL_CODE_RE,
    URL_RE, is_portuguese_month_date_token,
)

STRUCTURED_ARABIC_LITERALS_VERSION = 'structured_arabic_literals_v15_bounded_review_spacing'
_LIMIT = 120_000
_LRI, _PDI = '\u2066', '\u2069'
_BIDI = re.compile('[\u200e\u200f\u202a-\u202e\u2066-\u2069]')
_TOKEN = re.compile(r'\[\[([^\[\]]+)\]\]')
_NUMBER = re.compile(r'[0-9]+(?:[.,][0-9]+)*')
_FOLIO = re.compile(r'(?:[-–—]\s*)?[0-9]{1,4}(?:\s*/\s*[0-9]{1,4})?(?:\s*[-–—])?\Z')
_ENUM = re.compile(r'(?m)^\s*(?P<label>[a-z][)]|[a-z][.])(?=\s)')
# Bounded, explicit list-label translation. This is not a general transliterator.
_ARABIC_ENUM = {'a': 'أ', 'b': 'ب', 'c': 'ج', 'd': 'د'}
_ARABIC_ENUM_RE = re.compile(r'(?m)^[ \t]*(?P<label>[\u0621-\u064a]\u0640?[).])(?=\s|$)')
_MIXED_IDENTIFIER = re.compile(r'(?<!\w)(?=[A-Za-z0-9./%\-]*[A-Za-z])(?=[A-Za-z0-9./%\-]*[0-9])[A-Za-z0-9./%\-]+(?!\w)')
_NON_NAME_WORDS = {
    'ministério', 'público', 'tribunal', 'judicial', 'juízo', 'justiça', 'código',
    'processo', 'penal', 'sumário', 'república', 'comarca', 'polícia', 'guarda',
    'nacional', 'exmo', 'senhor', 'largo', 'rua', 'avenida', 'notificação',
    'decisão', 'prova', 'documental', 'testemunhal', 'pagamento', 'sentença',
    'deve', 'pagar', 'obrigação', 'prazo', 'deverá', 'condenado', 'comparecer',
    'o', 'a', 'os', 'as', 'um', 'uma', 'documento', 'identificação',
    'comprovativo', 'direito', 'defesa', 'informações', 'complementares',
}
_STREET = re.compile(
    r'(?i)^(?:Rua|R\.|Avenida|Av\.|Largo|Lg\.|Travessa|Tv\.|Praceta|Praça|Praca|'
    r'Alameda|Estrada|Urbanização|Urbanizacao|Beco|Calçada|Calcada)\s+')
_ADDRESS_LABEL = re.compile(r'(?i)^(?:Morada|Endereço|Endereco|Address|Domicílio|Domicilio)\s*[:\-]\s*')
_NAME_LABEL = re.compile(r'(?i)^(?:Nome|Name)\s*[:\-]\s*')
_POSTAL_SALUTATION = re.compile(r'(?:Exmo\(a\)[ \t]+Senhor\(a\)|Exmo\.[ \t]+Senhor|Exma\.[ \t]+Senhora)\Z', re.I)
_HOUSE_NUMBER_COLON = re.compile(r'(?<!\w)Nr\.:[ \t]*[0-9]+[ \t]*\Z', re.I)
_HARD_LINE_BREAKS = '\v\f\x1c\x1d\x1e\x85\u2028\u2029'
_OFFICIAL_SIGNATURE_TITLE = re.compile(r'(?:O/A|O|A)[ \t]+Oficial[ \t]+de[ \t]+Justiça,\Z', re.I)
_OFFICIAL_SIGNATURE_RANK = re.compile(r'Técnico[ \t]+de[ \t]+Justiça\Z', re.I)
# A capitalized phrase alone is not evidence of a person. New detections need
# a person field/attribution in this exact source block; no target text is used.
_PERSON_ROLE = (r'nome|name|destinat[áa]ri[oa]|arguid[oa]|testemunha|signat[áa]ri[oa]|'
                r'ofendid[oa]|requerente|requerid[oa]|int[ée]rprete|advogad[oa]|defensor[ae]?')
_PERSON_ROLE_WORD = re.compile(rf'(?:{_PERSON_ROLE})\Z', re.I)
_PERSON_PREFIX = re.compile(
    rf'(?<!\w)(?:{_PERSON_ROLE})(?:[ \t]+completo)?[ \t]*'
    r'(?:(?:[:\-]|é|de nome|chamad[oa]|identificad[oa] como|'
    r'indicad[oa](?: n[eo]st[ea] (?:exemplo|processo|documento))? é)[ \t]*)?\Z', re.I)
_PERSON_BEFORE_ACTION = re.compile(
    r'(?i)(?<!\w)foi[ \t]+(?:ouvid[oa]|notificad[oa]|identificad[oa])[ \t]+\Z')
_PERSON_AFTER_ACTION = re.compile(
    r'(?i)^[ \t]+(?:declarou|compareceu|assinou|prestou declarações|'
    r'foi[ \t]+(?:ouvid[oa]|notificad[oa]|identificad[oa]))\b')
_PERSON_AFTER_ROLE = re.compile(rf'^[ \t]*,[ \t]*(?:[oa][ \t]+)?(?:{_PERSON_ROLE})\b', re.I)
_PERSON_FIELD = re.compile(rf'(?:{_PERSON_ROLE}|nome completo|documento de identifica[çc][ãa]o)\Z', re.I)
_PERSON_TABLE_PREFIX = re.compile(
    rf'(?:^|[|\r\n])[ \t]*(?:{_PERSON_ROLE}|nome completo|documento de identifica[çc][ãa]o)[ \t]*\|[ \t]*\Z', re.I)
_NAME_CONNECTORS = {'da', 'de', 'do', 'dos', 'das'}
_WITNESS_HEADING = re.compile(r'(?:prova testemunhal|rol de testemunhas|testemunhas)[ \t]*:', re.I)
_WITNESS_ITEM = re.compile(r'[ \t]*(?:[a-z][.)]|[0-9]{1,3}[.)])[ \t]+')
_PROSE_WORDS = {'deve', 'deverá', 'devera', 'obrigado', 'obrigação', 'obrigacao',
    'notifica', 'notificado', 'comparecer', 'pagamento', 'pagar', 'condenado',
    'declara', 'requer', 'decide', 'determina', 'sentença', 'sentenca'}
# These are source-associated abbreviations, not a blanket uppercase-word rule.
_ABBREVIATIONS = re.compile(r'(?<!\w)(?:CPP|CPC|CP|GNR|IMT|PSP|SEF|AIMA|DIAP|IBAN|'
    r'RGCO|RGIT|CIVA|TJUE|UE|NIF|NISS|NIPC|EUR|USD|TIR|PGR|MP|RMP|CRC|SPP|SIMP|citius|Citius)(?!\w)')
# The ordinary glossary recognizes one line at a time. A source district heading
# may wrap once without losing its place attribution. This is not a general
# paragraph joiner: the complete prefix and independently verified place are
# required, and the total matched heading may contain at most one line break.
_HEADER_SPACE = r'(?:[ \t]+|[ \t]*\r?\n[ \t]*)'
_DISTRICT_PREFIX = (
    rf'(?m)^[ \t]*(?i:Minist[ée]rio{_HEADER_SPACE}P[úu]blico[ \t]*[-–][ \t]*'
    rf'Procuradoria{_HEADER_SPACE}da{_HEADER_SPACE}Rep[úu]blica{_HEADER_SPACE}'
    rf'da{_HEADER_SPACE}Comarca{_HEADER_SPACE}de){_HEADER_SPACE}')


class StructuredArabicLiteralError(ValueError):
    """Safe code and counters only; no source/response snippets or names."""
    def __init__(self, code: str, **counts: int):
        self.code = code
        self.details = dict(counts)
        super().__init__(code)


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


def _require(value: bool, code: str) -> None:
    if not value:
        raise StructuredArabicLiteralError(code)


def _text(value: str) -> str:
    _require(isinstance(value, str) and len(value) <= _LIMIT, 'invalid_structured_arabic_text')
    return value


def _latin(char: str) -> bool:
    return bool(char) and unicodedata.name(char, '').startswith('LATIN ')


def _word_character(char: str) -> bool:
    # Arabic conjunctions may touch an isolated Latin name. Latin/digit suffixes
    # cannot turn an exact name/identifier into a different larger one.
    return _latin(char) or char.isdecimal() or char == '_'


def _unmarked_end(value: str) -> int:
    end = len(value)
    while end and unicodedata.category(value[end - 1]).startswith('M'):
        end -= 1
    return end


def _source_grapheme_span(text: str, span: _Span) -> _Span:
    """Include only marks actually attached to an already proven source span."""
    end = span.end
    base_end = _unmarked_end(text[span.start:end])
    base = text[span.start + base_end - 1] if base_end else ''
    if _latin(base) or base.isdecimal():
        while end < len(text) and unicodedata.category(text[end]).startswith('M'):
            end += 1
    return _Span(span.start, end)


def _occurrences(text: str, literal: str) -> list[_Span]:
    result, cursor = [], 0
    base_end = _unmarked_end(literal)
    last = literal[base_end - 1] if base_end else ''
    while literal and (start := text.find(literal, cursor)) >= 0:
        end = start + len(literal)
        cursor = end
        if (start and _word_character(literal[0]) and _word_character(text[start - 1])
                or end < len(text) and _word_character(last) and _word_character(text[end])):
            continue
        # A following mark modifies the literal's final Latin/digit grapheme,
        # even when supplied outside its token wrapper. It is not ordinary
        # Arabic prose. Marks on a preceding Arabic conjunction remain valid.
        if (end < len(text) and (_latin(last) or last.isdecimal())
                and unicodedata.category(text[end]).startswith('M')):
            continue
        result.append(_Span(start, end))
    return result


def _view(value: str) -> tuple[str, list[_Span]]:
    """Remove only protocol wrappers/bidi; keep every visible character exact."""
    value = _BIDI.sub('', _text(value))
    pieces, spans, cursor, size = [], [], 0, 0
    for match in _TOKEN.finditer(value):
        before = value[cursor:match.start()]
        _require('[[' not in before and ']]' not in before, 'malformed_structured_arabic_tokens')
        pieces.extend((before, match[1]))
        size += len(before)
        spans.append(_Span(size, size + len(match[1])))
        size += len(match[1])
        cursor = match.end()
    tail = value[cursor:]
    _require('[[' not in tail and ']]' not in tail, 'malformed_structured_arabic_tokens')
    pieces.append(tail)
    return ''.join(pieces), spans


def _name(value: str) -> bool:
    words = value.split(' ')
    # Canonical comparison is only for the denylist; returned/source text is
    # never normalized. NFD must not turn an institution into a person name.
    if not 2 <= len(words) <= 10 or set(unicodedata.normalize('NFC', value).casefold().split()) & _NON_NAME_WORDS:
        return False
    named = 0
    for index, word in enumerate(words):
        if word in {'da', 'de', 'do', 'dos', 'das', 'e'} and 0 < index < len(words) - 1:
            continue
        parts = re.split("[-'’]", word)
        if not all(part and _latin(part[0]) and part[0].isupper()
                   and all(_latin(char) or unicodedata.category(char).startswith('M') for char in part)
                   for part in parts):
            return False
        named += 1
    return named >= 2


def _name_word_spans(text: str) -> list[_Span]:
    """Exact Latin words including their marks; no accent repair or guessing."""
    words, cursor = [], 0
    while cursor < len(text):
        if not _latin(text[cursor]):
            cursor += 1
            continue
        start = cursor
        cursor += 1
        while cursor < len(text):
            char = text[cursor]
            if (_latin(char) or unicodedata.category(char).startswith('M')
                    or char in "-'’" and cursor + 1 < len(text) and _latin(text[cursor + 1])):
                cursor += 1
            else:
                break
        words.append(_Span(start, cursor))
    return words


def source_person_name_for_field(field_text: str, value_text: str) -> str | None:
    """Exact name in an explicitly associated source table field, never a guess.

    The caller must prove the field/value relationship from the same source
    table. An arbitrary table-cell role or a target-supplied name is insufficient.
    """
    field = _text(field_text).strip().rstrip(':').strip()
    value = _text(value_text).strip()
    return value if _PERSON_FIELD.fullmatch(field) and _name(value) else None


def _witness_list_name_spans(text: str) -> list[_Span]:
    """Attribute marked source entries under an explicit witness heading.

    A list marker alone is not evidence of a person. At most one empty line
    may separate the heading and valid entries. Other boundaries end the
    heading's scope; names cannot cross lines/cells or consume trailing prose.
    The target never contributes attribution or spelling evidence.
    """
    spans, offset, active, blank_seen = [], 0, False, False
    for raw in text.splitlines(keepends=True):
        if '|' in raw or any(char in raw for char in _HARD_LINE_BREAKS):
            active = False  # Hard and table boundaries do not prove adjacency.
            offset += len(raw)
            continue
        line = raw.rstrip('\r\n')
        if _WITNESS_HEADING.fullmatch(line.strip()):
            active, blank_seen = True, False
        elif active and not line.strip(' \t'):
            active, blank_seen = not blank_seen, True
        elif active:
            marker = _WITNESS_ITEM.match(line)
            words = _name_word_spans(line[marker.end():]) if marker else []
            if not words or words[0].start != 0:
                active = False
            else:
                value = line[marker.end():]
                end = words[0].end
                for following in words[1:10]:
                    if (value[end:following.start] != ' '
                            or value[following.start:following.end] not in _NAME_CONNECTORS
                            and not value[following.start].isupper()):
                        break
                    end = following.end
                name, tail = value[:end], value[end:]
                # A comma introduces descriptive text, never part of the name.
                # An unpunctuated obligation/conjunction or table cell is not
                # an independently bounded name entry.
                if (not _name(name) or any(_PERSON_ROLE_WORD.fullmatch(unicodedata.normalize('NFC', word))
                                          for word in name.split())
                        or tail.strip() and not re.match(r'^[ \t]*[,;.]', tail)):
                    active = False
                else:
                    start = offset + marker.end()
                    spans.append(_Span(start, start + end))
                    blank_seen = False
        offset += len(raw)
    return spans


def _contextual_name_spans(text: str) -> list[_Span]:
    """Bounded source-only person attribution; never cross a line or table cell.

    Preserve the exact visible substring. Connectors are admitted only between
    name words. In particular, do not merge two people through Portuguese `e`.
    Unknown/unattributed capitalized prose remains unprotected and reviewable.
    """
    words = _name_word_spans(text)
    spans = _witness_list_name_spans(text)
    for index, first in enumerate(words):
        if not text[first.start].isupper():
            continue
        end = first.end
        for following in words[index + 1:index + 10]:
            gap = text[end:following.start]
            if not gap or any(char != ' ' for char in gap):
                break
            if text[following.start:following.end] not in _NAME_CONNECTORS and not text[following.start].isupper():
                break
            end = following.end
        # A trailing connector belongs to the surrounding prose, not the name.
        candidate = text[first.start:end]
        while candidate.rsplit(' ', 1)[-1] in _NAME_CONNECTORS:
            candidate = candidate.rsplit(' ', 1)[0]
            end = first.start + len(candidate)
        if (not _name(candidate) or any(_PERSON_ROLE_WORD.fullmatch(unicodedata.normalize('NFC', word))
                                        for word in candidate.split())):
            continue
        before = text[max(0, first.start - 160):first.start]
        after = text[end:end + 100]
        table_value = (_PERSON_TABLE_PREFIX.search(before)
                       and re.match(r'^[ \t]*(?:[|;\r\n]|\.?[ \t]*$)', after))
        if (_PERSON_PREFIX.search(before) or _PERSON_BEFORE_ACTION.search(before)
                or _PERSON_AFTER_ACTION.match(after) or _PERSON_AFTER_ROLE.match(after) or table_value):
            spans.append(_Span(first.start, end))
    return spans


def _address(value: str, *, role: str = '') -> bool:
    # Validation view only: preserve the original source punctuation in spans.
    # A colon belongs to an address only in this explicit numbered-house label.
    checked = _HOUSE_NUMBER_COLON.sub(lambda match: match[0].replace(':', ''), value)
    if (not value or len(value) > 220 or any(char in value for char in '\r\n' + _HARD_LINE_BREAKS)
            or any(not (_latin(char) or char.isdecimal() or char.isspace()
                        or char in "-–—.,/()ºª'’") for char in checked)):
        return False
    if set(re.findall(r'\w+', value.casefold())) & _PROSE_WORDS:
        return False
    postal = POSTAL_CODE_RE.search(value)
    starts_street = bool(_STREET.match(value))
    postal_line = bool(postal and postal.start() == 0 and value[postal.end():].strip()
                       and all(_latin(char) or char in " '-.’" for char in value[postal.end():]))
    return bool(starts_street and (postal or role == 'address') or postal_line)


def _source_lines(text: str) -> list[tuple[str, _Span]]:
    """Keep blank/hard/table boundaries and exact visible line offsets."""
    lines, offset = [], 0
    for raw in text.splitlines(keepends=True):
        value = raw.rstrip('\r\n').strip(' \t')
        start = offset + len(raw) - len(raw.lstrip(' \t'))
        valid = not any(char in raw for char in _HARD_LINE_BREAKS) and '|' not in value
        lines.append((value if valid else '', _Span(start, start + len(value))))
        offset += len(raw)
    return lines


def _official_signature_spans(text: str) -> list[_Span]:
    """Require the complete source title/name/rank judicial-officer signature."""
    lines, names = _source_lines(text), []
    for index in range(1, len(lines) - 1):
        name, span = lines[index]
        if (_OFFICIAL_SIGNATURE_TITLE.fullmatch(lines[index - 1][0])
                and _OFFICIAL_SIGNATURE_RANK.fullmatch(lines[index + 1][0]) and _name(name)
                and not any(_PERSON_ROLE_WORD.fullmatch(unicodedata.normalize('NFC', word))
                            for word in name.split())):
            names.append(span)
    return names


def _postal_block_spans(text: str) -> tuple[list[_Span], list[_Span]]:
    """Attribute adjacent street/postcode and salutation/name/street/postcode.

    A whole-page body role is not address evidence. These complete chains are
    source-only and may not cross empty lines, hard separators or table cells.
    Every returned range retains the exact original visible text.
    """
    lines = _source_lines(text)
    addresses, names = [], []
    for index, (value, span) in enumerate(lines[:-1]):
        postal = lines[index + 1][0]
        if (not value or not _STREET.match(value) or not _address(value, role='address')
                or not POSTAL_CODE_RE.match(postal) or not _address(postal)):
            continue
        addresses.append(span)
        if index >= 2:
            salutation, (name, name_span) = lines[index - 2][0], lines[index - 1]
            if (_POSTAL_SALUTATION.fullmatch(salutation) and _name(name)
                    and not any(_PERSON_ROLE_WORD.fullmatch(unicodedata.normalize('NFC', word))
                                for word in name.split())):
                names.append(name_span)
    return addresses, names


def _safe_literal(value: str) -> bool:
    core = value[:_unmarked_end(value)]
    identifier = any(regex.fullmatch(core) for regex in (
        EMAIL_RE, URL_RE, IBAN_RE, POSTAL_CODE_RE, BARCODE_RE,
        LONG_TRACK_RE, CASE_REF_RE, _MIXED_IDENTIFIER,
    ))
    return bool(value and (identifier
        or _name(value) or _address(core, role='address') or _FOLIO.fullmatch(core)
        or _NUMBER.fullmatch(core)
        or _ABBREVIATIONS.fullmatch(core) or re.fullmatch(r'[a-z][).]', value)))


def _choose(spans: Iterable[_Span]) -> list[_Span]:
    """Prefer the longest enclosing source literal, then source order."""
    result = []
    for span in sorted(set(spans), key=lambda item: (-(item.end - item.start), item.start)):
        if not any(span.start < other.end and other.start < span.end for other in result):
            result.append(span)
    return sorted(result, key=lambda item: item.start)


def _source_entities(text: str):
    from .structured_arabic_entities import extract_source_entities
    from .structured_glossary import _place_name
    return extract_source_entities(text,
        valid_name=lambda value: _name(value) and not any(
            _PERSON_ROLE_WORD.fullmatch(unicodedata.normalize('NFC', word)) for word in value.split()),
        valid_address=lambda value: bool(_STREET.match(value)) and _address(value, role='address'),
        valid_place=_place_name)


def _source_spans(text: str, tokens: list[_Span], *, role: str = '',
                  names: Iterable[str] = (), glossary_spans: Iterable[_Span] = ()) -> list[_Span]:
    entities = _source_entities(text)
    entity_spans = [_Span(*span) for span in (*entities.literals, *entities.persons)]
    approved = tuple(glossary_spans)
    source_addresses, addressee_names = _postal_block_spans(text)
    source_names = [*_contextual_name_spans(text), *_official_signature_spans(text), *addressee_names]
    spans = [*approved, *source_names, *source_addresses, *entity_spans]
    for token in tokens:
        literal = text[token.start:token.end]
        if is_portuguese_month_date_token(literal):
            # Portuguese month words must be translated, not hidden as Latin.
            continue
        _require(_safe_literal(literal) or any(span.start <= token.start and token.end <= span.end
                                              for span in (*approved, *entity_spans)), 'unsupported_source_literal')
        spans.append(token)
    for name in names:
        _require(isinstance(name, str) and _name(name), 'invalid_source_name_literal')
        found = _occurrences(text, name)
        if not found:
            # The older caller regex can stop immediately before a source
            # accent. Ignore that redundant prefix only when a complete name
            # is independently proven by this block's person attribution.
            found = [span for span in source_names if text[span.start:span.end].startswith(name)
                     and span.start + len(name) < span.end
                     and unicodedata.category(text[span.start + len(name)]).startswith('M')]
        _require(bool(found), 'source_name_literal_not_found')
        spans.extend(found)
    for match in re.finditer(r'[^\r\n]+', text):
        line = match[0]
        start = match.start() + len(line) - len(line.lstrip())
        value = line.strip()
        label = _ADDRESS_LABEL.match(value)
        if label:
            start += label.end()
            value = value[label.end():]
        if _address(value, role=role) or _FOLIO.fullmatch(value):
            spans.append(_Span(start, start + len(value)))
        name_label = _NAME_LABEL.match(line.strip())
        if name_label:
            value = line.strip()[name_label.end():]
            if _name(value):
                name_start = match.start() + len(line) - len(line.lstrip()) + name_label.end()
                spans.append(_Span(name_start, name_start + len(value)))
        elif role in {'signature', 'address'} and _name(line.strip()):
            name_start = match.start() + len(line) - len(line.lstrip())
            spans.append(_Span(name_start, name_start + len(line.strip())))
    for regex in (EMAIL_RE, URL_RE, IBAN_RE, POSTAL_CODE_RE, BARCODE_RE,
                  LONG_TRACK_RE, CASE_REF_RE, _MIXED_IDENTIFIER, _NUMBER, _ABBREVIATIONS, _ENUM):
        for match in regex.finditer(text):
            # Sentence punctuation is not an identifier. Decimal/date internal
            # punctuation and the source's punctuation outside the span stay put.
            start, end = match.span('label') if regex is _ENUM else match.span()
            if regex in (CASE_REF_RE, _MIXED_IDENTIFIER):
                while end > start and text[end - 1] in '.,':
                    end -= 1
            if end > start:
                spans.append(_Span(start, end))
    return _choose(_source_grapheme_span(text, span) for span in spans)


def _wrap(text: str, spans: list[_Span], *, isolates: bool) -> str:
    pieces, cursor = [], 0
    for span in spans:
        pieces.append(text[cursor:span.start])
        token = '[[' + text[span.start:span.end] + ']]'
        pieces.append(_LRI + token + _PDI if isolates else token)
        cursor = span.end
    pieces.append(text[cursor:])
    return ''.join(pieces)


def _line_start(text: str, span: _Span) -> bool:
    return not text[text.rfind('\n', 0, span.start) + 1:span.start].strip()


def _glossary_spans(text: str, contract) -> list[_Span]:
    if contract is None:
        return []
    # Lazy import avoids a cycle: the pure contract builder uses the same strict
    # span/count checks to reject inconsistent glossary pairs before dispatch.
    from .structured_glossary import verified_glossary_literal_spans
    approved = [_Span(start, end) for start, end in verified_glossary_literal_spans(text, contract)]
    result = list(approved)
    for literal in {text[span.start:span.end] for span in approved}:
        pattern = _DISTRICT_PREFIX + r'(?P<place>' + re.escape(literal) + r')[ \t]*(?=\r?$)'
        for match in re.finditer(pattern, text):
            if match[0].count('\n') > 1:
                continue
            span = _Span(*match.span('place'))
            if span in approved:
                continue
            # Do not override a configured phrase translating/transliterating
            # this occurrence. Source proof and preferences are both required;
            # target output never supplies authority or a spelling repair.
            for entry in contract.entries:
                if any(found.start <= span.start and span.end <= found.end
                       for found in _occurrences(text, entry.source_text)):
                    _require(bool(_occurrences(_view(entry.preferred_translation)[0], literal)),
                             'conflicting_source_place_literal')
            result.append(span)
    return result


def prepare_structured_arabic_source(text: str, *, role: str = '',
                                      protected_names: Iterable[str] = (), glossary_contract=None) -> str:
    """Protect source literals before digit tokenization; do not edit text.

    ``protected_names`` is a caller's conservative source-name detection, not
    model output. Every supplied name must be an exact plausible source span.
    Roles may strengthen address/signature detection, never bless legal prose.
    A glossary contract must independently bind this exact source block and
    matched approved pairs; a caller-supplied list of extra literals is not accepted.
    """
    visible, existing = _view(text)
    _require(isinstance(role, str) and isinstance(protected_names, Iterable)
             and not isinstance(protected_names, (str, bytes)),
             'invalid_structured_literal_options')
    spans = _source_spans(visible, existing, role=role, names=protected_names,
                          glossary_spans=_glossary_spans(visible, glossary_contract))
    return _wrap(visible, spans, isolates=False)


def _signature_abbreviation_occurrences(text: str, literal: str) -> list[_Span]:
    return [_Span(*match.span()) for match in re.finditer(r'(?<![\w.])d\.s\.?(?![\w.])', text)
            if match[0] == literal and (match.end() == len(text)
            or not unicodedata.category(text[match.end()]).startswith('M'))]


def normalize_structured_arabic_translation(prepared_source: str, translated: str, *, glossary_contract=None) -> str:
    """Validate exact literal counts/associations and canonicalize wrappers only.

    Equivalent one-token, split-token and unwrapped spellings are accepted only
    when their visible characters exactly match source-proven spans. All such
    spans remain in their source order. Numeric/citation/event checks must still
    run on the returned text; this helper is not a legal-equivalence reviewer.
    """
    source, supplied = _view(prepared_source)
    source_spans = _source_spans(source, supplied, glossary_spans=_glossary_spans(source, glossary_contract))
    # A complete source signature independently proves this date abbreviation.
    # Preserve an exact retained spelling, or leave the existing translated
    # Arabic-date-formula path alone. The target never supplies source authority.
    visible, _ = _view(translated)
    optional = [_Span(*span) for span in _source_entities(source).signature_abbreviations
                if _signature_abbreviation_occurrences(visible, source[span[0]:span[1]])]
    # Selecting a spelling requires every proved source occurrence, with the
    # same count and order as the other literals; unrelated source prose is not
    # promoted. Whole variants prevent d.s from matching a d.s. prefix.
    source_spans = _choose([*source_spans, *optional])
    return _normalize_with_source_spans(source, source_spans, translated,
        exact_signature_abbreviations=frozenset(source[span.start:span.end] for span in optional))


def _normalize_with_source_spans(source: str, source_spans: list[_Span], translated: str, *,
                                 exact_signature_abbreviations: frozenset[str] = frozenset()) -> str:
    """Shared pure validator; glossary preflight supplies only verified source spans."""
    expected = [source[span.start:span.end] for span in source_spans]
    visible, _ = _view(translated)
    source_enumerators = {literal for span, literal in zip(source_spans, expected)
                          if re.fullmatch(r'[a-z][).]', literal) and _line_start(source, span)}
    candidates = [span for literal in set(expected) for span in (
                  _signature_abbreviation_occurrences(visible, literal)
                  if literal in exact_signature_abbreviations else _occurrences(visible, literal))
                  if literal not in source_enumerators
                  or (_line_start(visible, span)
                      and (span.end == len(visible) or visible[span.end].isspace()))]
    translated_enumerators = {}
    for source_span, literal in zip(source_spans, expected):
        if (len(literal) == 2 and literal[0] in _ARABIC_ENUM and literal[1] in ').'
                and _line_start(source, source_span)):
            alternative = _ARABIC_ENUM[literal[0]] + literal[1]
            for span in _occurrences(visible, alternative):
                if (_line_start(visible, span)
                        and (span.end == len(visible) or visible[span.end].isspace())):
                    candidates.append(span)
                    translated_enumerators[span] = literal
    if source_enumerators:
        # Extra Arabic list markers cannot disappear into ordinary Arabic prose.
        # Even an unsupported mapping remains evidence of excess list coverage.
        reverse = {value: key for key, value in _ARABIC_ENUM.items()}
        for match in _ARABIC_ENUM_RE.finditer(visible):
            span = _Span(*match.span('label'))
            label = match['label']
            candidates.append(span)
            translated_enumerators[span] = reverse.get(label[:-1], label[:-1]) + label[-1]
    spans = _choose(candidates)
    actual = [translated_enumerators.get(span, visible[span.start:span.end]) for span in spans]
    wanted, observed = Counter(expected), Counter(actual)
    missing = sum((wanted - observed).values())
    duplicated = sum((observed - wanted).values())
    if missing or duplicated:
        raise StructuredArabicLiteralError('source_literal_coverage_mismatch',
            missing_literal_count=missing, duplicated_literal_count=duplicated,
            expected_literal_count=len(expected), actual_literal_count=len(actual))
    if actual != expected:
        raise StructuredArabicLiteralError('source_literal_association_mismatch',
            reassociated_literal_count=sum(a != b for a, b in zip(actual, expected)))
    residual, cursor = [], 0
    for span in spans:
        residual.append(visible[cursor:span.start])
        cursor = span.end
    residual.append(visible[cursor:])
    unsupported = sum(_latin(char) or char.isdecimal() for char in ''.join(residual))
    if unsupported:
        raise StructuredArabicLiteralError('unsupported_latin_or_digit_content',
                                          unsupported_character_count=unsupported)
    return _wrap(visible, [span for span in spans if span not in translated_enumerators], isolates=True)
