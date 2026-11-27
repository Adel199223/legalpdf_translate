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
SOURCE_FIELD_POLICY = "baseline_label_value_v1"
SOURCE_INLINE_ADDRESS_JOIN_POLICY = "source_locative_house_join_v1"
SOURCE_INLINE_ADDRESS_JOIN_POLICY_V2 = "source_locative_house_join_v2"
SOURCE_INLINE_ADDRESS_JOIN_POLICY_V3 = "source_locative_house_join_v3"
_MAX_INLINE_COMPONENT_WORK = 200_000
_MAX_INLINE_COMPONENT_CARRIERS = 32
_LABELED_POSTAL = re.compile(
    r"(?i)^(?:C[oó]digo[ \t]+Postal|Postal[ \t]+Code|Postcode|Code[ \t]+Postal)[ \t]*:[ \t]*"
    r"(?P<value>[0-9]{4}(?:-|[ \t]+)[0-9]{3}[ \t]+(?P<town>.+))\Z")
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


def source_address_fields(text: str, *, source_field_policy: str | None = None) -> list[SourceAddressField]:
    """Return exact bounded lines: labelled addresses or proven postal chains."""
    if source_field_policy not in {None, SOURCE_FIELD_POLICY}:
        raise ValueError("Unknown source field policy.")
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
        if source_field_policy == SOURCE_FIELD_POLICY:
            labeled_postal = _LABELED_POSTAL.fullmatch(value)
            if labeled_postal and _locality(labeled_postal["town"]):
                fields.append(SourceAddressField(start + labeled_postal.start("value"),
                    start + labeled_postal.end("value"), labeled_postal["value"]))
        postal = _POSTAL.fullmatch(value)
        if postal and _locality(postal["town"]):
            fields.append(SourceAddressField(start, start + len(value), value))
        label = _LABEL.match(value)
        address = value[label.end():] if label else value
        field_start = start + (label.end() if label else 0)
        # A standalone address label may own only the immediately following
        # proven street line, never a subsequent generic label or postal label.
        if (source_field_policy == SOURCE_FIELD_POLICY and label and not address
                and index + 1 < len(lines)):
            address, field_start = lines[index + 1]
        if not _STREET.match(address) or not any(_latin(c) for c in address):
            continue
        if (set(re.findall(r"\w+", address.casefold())) & _PROSE
                or not all(_latin(c) or c.isdecimal() or unicodedata.category(c).startswith("M")
                           or c in " \t-–—.,/()ºª'’:" for c in address)):
            continue
        next_postal = _POSTAL.fullmatch(lines[index + 1][0]) if index + 1 < len(lines) else None
        if label or next_postal and _locality(next_postal["town"]):
            fields.append(SourceAddressField(field_start, field_start + len(address), address))
    return sorted(set(fields), key=lambda field: field.start)


def source_address_line_blocks(text: str) -> list[SourceAddressField]:
    """Exact two/three-line postal witnesses; no whitespace normalization.

    This narrower correction-only proof does not alter source tokenization or
    the existing single-field equivalence rules. Only CR/LF delimiters count as
    line boundaries; indentation and inline whitespace remain literal content.
    """
    if len(text) > _LIMIT:
        return []
    lines = list(re.finditer(r"([^\r\n]*)(\r\n|\r|\n|$)", text))
    blocks = []
    postal_pattern = re.compile(r"[0-9]{4}(?:-[0-9]{3})?[ \t]+(?P<town>.+)\Z")
    for index, line in enumerate(lines):
        street = line[1]
        if not _STREET.match(street) or len(street) > 140:
            continue
        if (set(re.findall(r"\w+", street.casefold())) & _PROSE
                or not all(_latin(c) or c.isdecimal() or unicodedata.category(c).startswith("M")
                           or c in " \t-–—.,/()ºª'’:" for c in street)):
            continue
        for size in (2, 3):
            group = lines[index:index + size]
            if len(group) != size or not all(item[2] for item in group[:-1]):
                continue
            values = [item[1] for item in group]
            if any(not value or len(value) > 140 or any(c in value for c in _HARD)
                   for value in values):
                continue
            postal = postal_pattern.fullmatch(values[-1])
            if not postal or not _locality(postal["town"]):
                continue
            if size == 3 and not _locality(values[1]):
                continue
            start, end = line.start(), group[-1].end(1)
            blocks.append(SourceAddressField(start, end, text[start:end]))
    return blocks


def source_required_prefixed_address_line_blocks(source: str, required) -> list[SourceAddressField]:
    """V2-only complete locked street/postal pairs, never substring evidence.

    This is wrapper-equivalence evidence, not a source tokenizer. Both adjacent
    lines must already be unique whole required tokens. No new field ownership
    is inferred for unprotected text or for numeric substrings in a postal row.
    """
    if not isinstance(source, str) or len(source) > _LIMIT:
        return []
    # Outside isolates may describe unrelated extraction runs, but must be
    # balanced and unnested and never enclose a token-owned isolate/line. Do
    # not derive proof from _view's removal of unowned formatting controls.
    depth, cursor, enclosed_tokens = 0, 0, set()
    for match in list(_TOKEN.finditer(source)) + [None]:
        boundary = match.start() if match else len(source)
        for char in source[cursor:boundary]:
            if char == _LRI:
                if depth:
                    return []
                depth = 1
            elif char == _PDI:
                if not depth:
                    return []
                depth = 0
            elif (unicodedata.category(char) == "Cf"
                  or unicodedata.category(char) == "Cc" and char not in "\t\r\n"):
                return []
        if depth and (match is None or match[0].startswith(_LRI)):
            return []
        if match:
            if depth:
                enclosed_tokens.add((match.start(), match.end()))
            if any(unicodedata.category(char) == "Cf"
                   or unicodedata.category(char) == "Cc" and char not in "\t\r\n"
                   for char in match[1]):
                return []
            cursor = match.end()
    view = _view(source)
    if (view is None or not isinstance(required, (list, tuple))
            or not 1 <= len(required) <= 512
            or any(not isinstance(value, str) or not value or len(value) > 256 for value in required)):
        return []
    visible, _, tokens = view
    if len(tokens) > 512:
        return []
    counts, source_counts = Counter(required), Counter(token[2] for token in tokens)
    lines = list(re.finditer(r"([^\r\n]*)(\r\n|\r|\n|$)", visible))
    marker = re.compile(r"(?<![\w.])" + _STREET.pattern.removeprefix("(?i)^"), re.I)
    postal_pattern = re.compile(r"[0-9]{4}(?:-[0-9]{3})?[ \t]+(?P<town>.+)\Z")
    result, work = [], len(source)
    for index, line in enumerate(lines[:-1]):
        street, postal = line[1], lines[index + 1][1]
        if not line[2] or not street or not postal or len(street) > 140 or len(postal) > 140:
            continue
        markers = list(marker.finditer(street))
        if len(markers) != 1:
            continue
        before = street[:markers[0].start()]
        prefix = re.fullmatch(r"(.+?)[ \t]+[-–—][ \t]+", before)
        if (prefix is None or len(prefix[1]) > 80 or not _locality(prefix[1])
                or not any(_latin(c) for c in street[markers[0].end():])
                or set(re.findall(r"\w+", street.casefold())) & _PROSE
                or not all(_latin(c) or c.isdecimal() or unicodedata.category(c).startswith("M")
                           or c in " \t-–—.,/()ºª'’" for c in street)):
            continue
        post = postal_pattern.fullmatch(postal)
        if post is None or not _locality(post["town"]):
            continue
        rows = ((line.start(1), line.end(1), street),
                (lines[index + 1].start(1), lines[index + 1].end(1), postal))
        valid = True
        for start, end, value in rows:
            work += len(visible) + len(tokens)
            if work > 200_000:
                return []
            owned = [token for token in tokens if token[0] < end and token[1] > start]
            if (len(owned) != 1 or owned[0][:3] != (start, end, value)
                    or counts[value] != 1 or source_counts[value] != 1
                    or _occurrences(visible, value) != [(start, end)]):
                valid = False
                break
        if valid:
            start, end = rows[0][0], rows[1][1]
            # Reject invisible source controls between the two complete tokens;
            # the original newline itself is the only restoration permission.
            left, right = next(t for t in tokens if t[:3] == rows[0]), next(t for t in tokens if t[:3] == rows[1])
            if (source[left[4]:right[3]] != line[2]
                    or (left[3], left[4]) in enclosed_tokens or (right[3], right[4]) in enclosed_tokens
                    or left[3] and source[left[3] - 1] not in "\r\n"
                    or right[4] < len(source) and source[right[4]] not in "\r\n"):
                continue
            result.append(SourceAddressField(start, end, visible[start:end]))
            if len(result) > 32:
                return []
    return result


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


def _separate_inline_occurrences(visible, target_tokens, source_visible, field, owned, *,
                                 source_inline_address_join_policy=None, text=None,
                                 source=None, source_positions=None):
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
        if not re.fullmatch(r"[ \t]*(?:[,،][ \t]*)?(?:رقم|بالرقم)[ \t]+", visible[end:a]):
            # A new permission is source-qualified, local and raw-coordinate
            # checked. _view deliberately retains its historical behavior;
            # erased stray isolates must never manufacture this new proof.
            marker = _INLINE_NUMBER.search(field.value)
            locative = (marker is not None and re.fullmatch(
                r"(?:[ \t]*,[ \t]*|[ \t]+)no[ \t]+n\.?[º°o]\.?[ \t]*[0-9]+[A-Za-z]?",
                marker[0], re.I))
            street_token = next(t for t in target_tokens if t[:3] == (start, end, street))
            if (source_inline_address_join_policy not in (SOURCE_INLINE_ADDRESS_JOIN_POLICY, SOURCE_INLINE_ADDRESS_JOIN_POLICY_V2, SOURCE_INLINE_ADDRESS_JOIN_POLICY_V3)
                    or not locative or text is None or source is None or source_positions is None
                    or not (re.fullmatch(r"[ \t]*(?:[,،][ \t]*)?عند[ \t]+رقم[ \t]+",
                                        text[street_token[4]:following[3]])
                        or source_inline_address_join_policy == SOURCE_INLINE_ADDRESS_JOIN_POLICY_V3
                        and re.fullmatch(r"[ \t]*(?:[,،][ \t]*)?في[ \t]+رقم[ \t]+",
                                        text[street_token[4]:following[3]]))):
                continue
            number_start = len(field.value) - len(number)
            raw_marker_start = source_positions[field.start]
            if source[raw_marker_start:owned[0][3]] != field.value[:number_start]:
                continue
        if (a, b) not in _occurrences(visible, number):
            continue
        if b + 1 < len(visible) and visible[b] in ".,:" and visible[b + 1].isdecimal():
            continue
        result.append((start, b, field.value))
    return result


def _source_inline_locative_alternative(field, owned, source, source_view):
    """Delete only one unprotected grammatical locative from a proven field."""
    parts = _separate_inline_parts(field, owned)
    if parts is None:
        return None
    street, number = parts
    marker = _INLINE_NUMBER.search(field.value)
    locative = re.fullmatch(
        r"(?P<prefix>[ \t]*,[ \t]*|[ \t]+)(?P<locative>no[ \t]+)n\.?[º°o]\.?[ \t]*[0-9]+[A-Za-z]?",
        marker[0], re.I) if marker else None
    if locative is None:
        return None
    visible, positions, _ = source_view
    if (_occurrences(visible, field.value) != [(field.start, field.end)]
            or len(_occurrences(visible, street)) != 1):
        return None
    # The only source-owned token is the exact house. In particular `no` and
    # the ordinal marker cannot be discarded from a protected source token.
    number_start = len(field.value) - len(number)
    if source[positions[field.start]:owned[0][3]] != field.value[:number_start]:
        return None
    left = marker.start() + locative.start("locative")
    right = marker.start() + locative.end("locative")
    return field.value[:left] + field.value[right:], street


def _complete_inline_component_carriers(text, view, start, end, literal):
    """Only complete existing carriers may prove semantic-character ownership.

    Strip known wrapper spans only. Unowned isolates/controls cannot disappear
    through _view, and no carrier may claim prose outside the complete field.
    """
    visible, positions, tokens = view
    owned = [token for token in tokens if token[0] < end and token[1] > start]
    if (not 1 <= len(owned) <= _MAX_INLINE_COMPONENT_CARRIERS
            or any(a < start or b > end for a, b, *_ in owned)):
        return False
    def semantic(char):
        return char not in " \t" and not unicodedata.category(char).startswith("P")
    for offset in range(start, end):
        if semantic(visible[offset]) and not any(a <= offset < b for a, b, *_ in owned):
            return False
    if any(not any(semantic(c) for c in token[2]) for token in owned):
        return False
    raw_start = owned[0][3] if owned[0][0] == start else positions[start]
    raw_end = owned[-1][4] if owned[-1][1] == end else positions[end - 1] + 1
    if (raw_start and unicodedata.category(text[raw_start - 1]) == "Cf"
            or raw_end < len(text) and unicodedata.category(text[raw_end]) == "Cf"):
        return False
    pieces, cursor = [], raw_start
    for a, b, value, begin, finish in owned:
        if text[begin:finish] not in ("[[" + value + "]]", _LRI + "[[" + value + "]]" + _PDI):
            return False
        pieces.extend((text[cursor:begin], value))
        cursor = finish
    pieces.append(text[cursor:raw_end])
    return "".join(pieces) == literal


def canonicalize_source_address_literals(text: str, source: str | None,
                                        expected: list[str] | None, *, source_field_policy: str | None = None,
                                        source_inline_address_join_policy: str | None = None):
    """Return text/expectations/count/error; only exact source-proven wrappers change.

    Complete field occurrence counts and source order must agree. Wrappers that
    cross field boundaries never confer proof. Unrelated tokens remain intact.
    """
    if source_inline_address_join_policy not in (None, SOURCE_INLINE_ADDRESS_JOIN_POLICY, SOURCE_INLINE_ADDRESS_JOIN_POLICY_V2, SOURCE_INLINE_ADDRESS_JOIN_POLICY_V3):
        raise ValueError("Unknown source inline address join policy.")
    if not source or expected is None:
        return text, expected, 0, None
    source_view, target_view = _view(source), _view(text)
    if source_view is None or target_view is None:
        return text, expected, 0, "source_address_malformed_tokens"
    source_visible, source_positions, source_tokens = source_view
    visible, positions, target_tokens = target_view
    remaining = Counter(expected)
    owned_required = Counter()
    owned_by_field = {}
    inline_owned = Counter()
    fields = []
    source_fields = source_address_fields(source_visible,
        **({"source_field_policy": source_field_policy} if source_field_policy is not None else {}))
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
    canonical_alternatives = {}
    component_work = 0
    if source_inline_address_join_policy in (SOURCE_INLINE_ADDRESS_JOIN_POLICY_V2, SOURCE_INLINE_ADDRESS_JOIN_POLICY_V3):
        for field in fields:
            if field not in inline_fields:
                continue
            component_work += 2 * len(source_visible) + 4 * len(visible) + len(source_tokens) + len(target_tokens)
            if component_work > _MAX_INLINE_COMPONENT_WORK:
                return text, expected, 0, "source_address_component_bound"
            alternative = _source_inline_locative_alternative(field, owned_by_field[field], source, source_view)
            if alternative is None:
                continue
            literal, street = alternative
            # The source house must not become a prefix of a changed compound
            # number, including when punctuation and the suffix use separate
            # wrappers. Check original and alternate representations jointly,
            # before declining an absent alternate or allocating any carrier.
            for representation in (field.value, literal):
                for match in re.finditer(re.escape(representation), visible):
                    start, end = match.span()
                    if (start and _word(visible[start - 1])
                            or start > 1 and visible[start - 1] in "-/_" and _word(visible[start - 2])):
                        continue
                    if (end < len(visible) and _word(visible[end])
                            or end + 1 < len(visible) and (
                                visible[end] in ".,:" and visible[end + 1].isdecimal()
                                or visible[end] in "-/_" and _word(visible[end + 1]))):
                        return text, expected, 0, "source_address_association_mismatch"
            hits = _occurrences(visible, literal)
            if not hits:
                continue
            # These are aliases of one source identity, not unrelated extras.
            # Do not decline the new proof and fall back to an original-only
            # success when competing original/short representations coexist.
            if (_occurrences(visible, field.value) or len(hits) != 1
                    or len(_occurrences(visible, street)) != 1):
                return text, expected, 0, "source_address_association_mismatch"
            start, end = hits[0]
            if not _complete_inline_component_carriers(text, target_view, start, end, literal):
                return text, expected, 0, "source_address_component_carrier_mismatch"
            key = (start, end, field.value)
            if key in canonical_alternatives:
                return text, expected, 0, "source_address_association_mismatch"
            canonical_alternatives[key] = literal
            candidates.append(key)
    separate = set()
    for field in fields:
        if field in inline_fields:
            separate.update(_separate_inline_occurrences(visible, target_tokens, source_visible,
                                                        field, owned_by_field[field],
                source_inline_address_join_policy=source_inline_address_join_policy,
                text=text, source=source, source_positions=source_positions))
    candidates.extend(separate)
    # A locality inside a complete street address belongs to that larger field,
    # not to a second standalone occurrence elsewhere in the source. Own each
    # visible character at most once before checking exact counts and order.
    found = []
    for candidate in sorted(candidates, key=lambda item: (item[0], -item[1])):
        if found and candidate[0] < found[-1][1]:
            if candidate in canonical_alternatives or found[-1] in canonical_alternatives:
                return text, expected, 0, "source_address_association_mismatch"
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
        canonical_value = canonical_alternatives.get((start, end, value), value)
        replacements.append((raw_start, raw_end, _LRI + "[[" + canonical_value + "]]" + _PDI))
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
    observed_alternatives = {value: canonical_alternatives[(start, end, value)]
        for start, end, value in found if (start, end, value) in canonical_alternatives}
    for field in fields:
        if keep_separate[field.value]:
            keep_separate[field.value] -= 1
            remove.subtract(Counter(token[2] for token in owned_by_field[field]))
        else:
            canonical_fields.append(observed_alternatives.get(field.value, field.value))
    for value in expected:
        if remove[value]:
            remove[value] -= 1
        else:
            canonical_expected.append(value)
    canonical_expected.extend(canonical_fields)
    return result, canonical_expected, changed, None
