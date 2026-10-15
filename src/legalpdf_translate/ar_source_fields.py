"""Exact source address fields and wrapper-only equivalence for legacy Arabic.

No fuzzy matching or visible-character normalization. Saved source token shapes
may differ from a model's packaging; complete source fields, counts and order
provide the proof needed to compare those shapes without relaxing anti-loss.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
import unicodedata

_TOKEN = re.compile(r"(?<!\[)(?:\u2066)?\[\[([^\[\]]+)\]\](?:\u2069)?(?!\])")
_LRI, _PDI = "\u2066", "\u2069"
_HARD = "\v\f\x1c\x1d\x1e\x85\u2028\u2029"
_POSTAL = re.compile(r"[0-9]{4}-[0-9]{3}[ \t]+(?P<town>.+)\Z")
_LABEL = re.compile(r"(?i)^(?:Morada|Endereço|Endereco|Address|Domicílio|Domicilio)\s*[:\-]\s*")
_STREET = re.compile(r"(?i)^(?:Rua|R\.|Avenida|Av\.|Largo|Lg\.|Travessa|Tv\.|Praça|Praca|Estrada|Alameda|Quinta)\s+")
_PROSE = {"deve", "pagar", "comparecer", "enviar", "documentos", "obrigação", "obrigacao", "prazo", "tribunal"}
_LIMIT = 120_000
_INLINE_STREET = re.compile(
    r"(?<![\w./-])(?:Rua|Avenida|Av\.|Largo|Travessa|Praça|Praca|Estrada|Alameda)[ \t]+", re.I)
_INLINE_NUMBER = re.compile(
    r"(?:[ \t]*,[ \t]*|[ \t]+)(?:no[ \t]+)?n\.?[º°o]\.?[ \t]*[0-9]+(?:[A-Za-z])?"
    r"(?![\w/-]|[.,:][0-9])", re.I)
_INLINE_TOWN = re.compile(r",[ \t]+em[ \t]+(?P<town>[^,;!?\r\n]+)")


@dataclass(frozen=True)
class SourceAddressField:
    start: int
    end: int
    value: str


def _latin(char: str) -> bool:
    return unicodedata.name(char, "").startswith("LATIN ")


def _locality(value: str) -> bool:
    words = value.split()
    return bool(1 <= len(words) <= 6
        and not set(value.casefold().split()) & _PROSE
        and any(_latin(char) for char in value)
        and all(_latin(char) or unicodedata.category(char).startswith("M")
                or char in " '-.’" for char in value)
        and all(word[:1].isupper() or word in {"de", "da", "do", "das", "dos"} for word in words))


def source_address_fields(text: str) -> list[SourceAddressField]:
    """Return exact bounded lines: labelled addresses or proven postal chains."""
    lines = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        value = raw.rstrip("\r\n").strip(" \t")
        start = offset + len(raw) - len(raw.lstrip(" \t"))
        valid = len(value) <= 220 and not any(c in raw for c in _HARD) and "|" not in value
        lines.append((value if valid else "", start))
        offset += len(raw)
    fields = []
    for index, (value, start) in enumerate(lines):
        postal = _POSTAL.fullmatch(value)
        if postal and _locality(postal["town"]):
            fields.append(SourceAddressField(start, start + len(value), value))
        label = _LABEL.match(value)
        address = value[label.end():] if label else value
        if not _STREET.match(address) or not any(_latin(c) for c in address):
            continue
        if (set(re.findall(r"\w+", address.casefold())) & _PROSE
                or not all(_latin(c) or c.isdecimal() or unicodedata.category(c).startswith("M")
                           or c in " \t-–—.,/()ºª'’:" for c in address)):
            continue
        next_postal = _POSTAL.fullmatch(lines[index + 1][0]) if index + 1 < len(lines) else None
        if label or next_postal and _locality(next_postal["town"]):
            field_start = start + (label.end() if label else 0)
            fields.append(SourceAddressField(field_start, field_start + len(address), address))
    return sorted(set(fields), key=lambda field: field.start)


def _inline_address_fields(text: str, existing: list[SourceAddressField]):
    """Bound inline streets by an explicit house marker and optional locality.

    This affects wrapper equivalence only, not source pretokenization or saved
    protocol. Never claim generic numbers/prose, extend across a line boundary,
    or shorten an already proven complete address field.
    """
    fields = []
    for street in _INLINE_STREET.finditer(text):
        end = street.end()
        while end < len(text) and end - street.start() < 220 and text[end] not in "\r\n" + _HARD:
            end += 1
        fragment = text[street.end():end]
        number = _INLINE_NUMBER.search(fragment)
        if number is None or not _locality(fragment[:number.start()]):
            continue
        field_end = street.end() + number.end()
        town = _INLINE_TOWN.match(text, field_end)
        if town and _locality(town["town"].rstrip(" .")):
            field_end = town.end() - len(town["town"]) + len(town["town"].rstrip(" ."))
        field = SourceAddressField(street.start(), field_end, text[street.start():field_end])
        if field.end - field.start > 220:
            continue
        if any(prior.start < field.end and prior.end > field.start for prior in existing + fields):
            continue
        fields.append(field)
    return fields


def _view(text: str):
    """Visible exact text, source token intervals and original-coordinate map."""
    if not isinstance(text, str) or len(text) > _LIMIT:
        return None
    visible, positions, tokens = [], [], []
    cursor = 0
    for match in _TOKEN.finditer(text):
        if match[0].startswith(_LRI) != match[0].endswith(_PDI):
            return None
        before = text[cursor:match.start()]
        if "[[" in before or "]]" in before:
            return None
        for index, char in enumerate(before, cursor):
            if char not in {_LRI, _PDI}:
                visible.append(char); positions.append(index)
        start = len(visible)
        for index, char in enumerate(match[1], match.start(1)):
            if char in {_LRI, _PDI}:
                return None
            visible.append(char); positions.append(index)
        tokens.append((start, len(visible), match[1], match.start(), match.end()))
        cursor = match.end()
    tail = text[cursor:]
    if "[[" in tail or "]]" in tail:
        return None
    for index, char in enumerate(tail, cursor):
        if char not in {_LRI, _PDI}:
            visible.append(char); positions.append(index)
    return "".join(visible), positions, tokens


def _word(char: str) -> bool:
    return _latin(char) or char.isdecimal() or char == "_" or unicodedata.category(char).startswith("M")


def _occurrences(text: str, literal: str):
    result = []
    for match in re.finditer(re.escape(literal), text):
        start, end = match.span()
        if start and _word(text[start - 1]) or end < len(text) and _word(text[end]):
            continue
        if (start > 1 and text[start - 1] in "-/_" and _word(text[start - 2])
                or end + 1 < len(text) and text[end] in "-/_" and _word(text[end + 1])):
            continue
        result.append((start, end))
    return result


def _separate_inline_parts(field, owned):
    """Only a source-locked house number may leave the Portuguese connective."""
    marker = _INLINE_NUMBER.search(field.value)
    number = re.search(r"[0-9]+[A-Za-z]?\Z", field.value)
    if marker is None or number is None or marker.end() != len(field.value):
        return None
    if len(owned) != 1 or owned[0][:3] != (field.start + number.start(), field.end, number[0]):
        return None
    return field.value[:marker.start()], number[0]


def _separate_inline_occurrences(visible, target_tokens, source_visible, field, owned):
    """Prove exact street/house wrappers joined only by the Arabic number label.

    This does not regroup or rewrite the visible connective. A whole primary
    literal therefore remains subject to the independent correction loss guard.
    """
    parts = _separate_inline_parts(field, owned)
    if parts is None:
        return []
    street, number = parts
    streets = _occurrences(visible, street)
    if len(streets) != len(_occurrences(source_visible, street)):
        return []
    result = []
    for start, end in streets:
        if not any(token[:3] == (start, end, street) for token in target_tokens):
            continue
        following = next((token for token in target_tokens if token[0] >= end), None)
        if following is None or following[2] != number:
            continue
        a, b = following[:2]
        if not re.fullmatch(r"[ \t]*(?:[,،][ \t]*)?رقم[ \t]+", visible[end:a]):
            continue
        if (a, b) not in _occurrences(visible, number):
            continue
        if b + 1 < len(visible) and visible[b] in ".,:" and visible[b + 1].isdecimal():
            continue
        result.append((start, b, field.value))
    return result


def canonicalize_source_address_literals(text: str, source: str | None,
                                        expected: list[str] | None):
    """Return text/expectations/count/error; only exact source-proven wrappers change.

    Complete field occurrence counts and source order must agree. Wrappers that
    cross field boundaries never confer proof. Unrelated tokens remain intact.
    """
    if not source or expected is None:
        return text, expected, 0, None
    source_view, target_view = _view(source), _view(text)
    if source_view is None or target_view is None:
        return text, expected, 0, "source_address_malformed_tokens"
    source_visible, _, source_tokens = source_view
    visible, positions, target_tokens = target_view
    remaining = Counter(expected)
    owned_required = Counter()
    owned_by_field = {}
    inline_owned = Counter()
    fields = []
    source_fields = source_address_fields(source_visible)
    inline_fields = _inline_address_fields(source_visible, source_fields)
    source_fields = sorted(source_fields + inline_fields, key=lambda field: field.start)
    for field in source_fields:
        owned = [token for token in source_tokens if token[0] < field.end and token[1] > field.start]
        if not owned or any(token[0] < field.start or token[1] > field.end for token in owned):
            continue
        needed = Counter(token[2] for token in owned)
        if needed - remaining:
            continue
        remaining.subtract(needed)
        owned_required.update(needed)
        owned_by_field[field] = owned
        if field in inline_fields:
            inline_owned.update(needed)
        fields.append(field)
    if not fields:
        return text, expected, 0, None
    expected_fields = [field.value for field in fields]
    candidates = []
    for value in set(expected_fields):
        candidates.extend((start, end, value) for start, end in _occurrences(visible, value))
    separate = set()
    for field in fields:
        if field in inline_fields:
            separate.update(_separate_inline_occurrences(visible, target_tokens, source_visible,
                                                        field, owned_by_field[field]))
    candidates.extend(separate)
    # A locality inside a complete street address belongs to that larger field,
    # not to a second standalone occurrence elsewhere in the source. Own each
    # visible character at most once before checking exact counts and order.
    found = []
    for candidate in sorted(candidates, key=lambda item: (item[0], -item[1])):
        if found and candidate[0] < found[-1][1]:
            if candidate[1] <= found[-1][1]:
                continue
            return text, expected, 0, "source_address_association_mismatch"
        found.append(candidate)
    if Counter(value for _, _, value in found) != Counter(expected_fields):
        return text, expected, 0, "source_address_coverage_mismatch"
    if [value for _, _, value in found] != expected_fields:
        return text, expected, 0, "source_address_association_mismatch"
    if inline_owned:
        outside = Counter(token[2] for token in target_tokens
                          if not any(start <= token[0] and token[1] <= end for start, end, _ in found))
        if any(outside[value] != remaining[value] for value in inline_owned):
            return text, expected, 0, "source_address_token_multiplicity_mismatch"
    replacements = []
    separate_values = Counter(value for start, end, value in found if (start, end, value) in separate)
    for start, end, value in found:
        if (start, end, value) in separate:
            continue
        owned = [token for token in target_tokens if token[0] < end and token[1] > start]
        if any(token[0] < start or token[1] > end for token in owned):
            return text, expected, 0, "source_address_wrapper_crosses_field"
        raw_start, raw_end = positions[start], positions[end - 1] + 1
        if owned and owned[0][0] == start:
            raw_start = owned[0][3]
        if owned and owned[-1][1] == end:
            raw_end = owned[-1][4]
        replacements.append((raw_start, raw_end, _LRI + "[[" + value + "]]" + _PDI))
    result, cursor, changed = [], 0, 0
    for start, end, replacement in replacements:
        result.extend((text[cursor:start], replacement))
        changed += int(text[start:end] != replacement)
        cursor = end
    result.append(text[cursor:])
    result = "".join(result)
    assert _view(result)[0] == visible
    canonical_expected = []
    remove = owned_required.copy()
    keep_separate = separate_values.copy()
    canonical_fields = []
    for field in fields:
        if keep_separate[field.value]:
            keep_separate[field.value] -= 1
            remove.subtract(Counter(token[2] for token in owned_by_field[field]))
        else:
            canonical_fields.append(field.value)
    for value in expected:
        if remove[value]:
            remove[value] -= 1
        else:
            canonical_expected.append(value)
    canonical_expected.extend(canonical_fields)
    return result, canonical_expected, changed, None
