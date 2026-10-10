"""Source-bound wrapper regrouping and correction literal preservation."""
from collections import Counter
import re

from .output_normalize import LRI, PDI

TOKEN = re.compile(r"(?:\u2066)?\[\[([^\[\]]+)\]\](?:\u2069)?")
NUMERIC = re.compile(r"[0-9]+(?:[.,:/-][0-9]+)*")
SEPARATORS = re.compile(r"[\s=/€$£¥]*")


def visible_text(text):
    return TOKEN.sub(lambda match: match[1], text).replace(LRI, "").replace(PDI, "")


def regroup_source_numeric_tokens_with_stats(text, source):
    if not source:
        return text, 0
    changed_groups = 0
    pieces = []
    spans = []
    cursor = 0
    for match in TOKEN.finditer(source):
        pieces.append(source[cursor:match.start()].replace(LRI, "").replace(PDI, ""))
        start = sum(map(len, pieces))
        pieces.append(match[1])
        spans.append((start, start + len(match[1]), match[1]))
        cursor = match.end()
    pieces.append(source[cursor:].replace(LRI, "").replace(PDI, ""))
    visible = "".join(pieces)

    def replace(match):
        nonlocal changed_groups
        # Normalization supplies fully balanced isolate-wrapped tokens. Never
        # repair a half wrapper or a token embedded in malformed brackets.
        if match[0] != LRI + "[[" + match[1] + "]]" + PDI:
            return match[0]
        if (match.start() and text[match.start()-1] == "[") or (match.end() < len(text) and text[match.end()] == "]"):
            return match[0]
        literal = match[1]
        positions = [m.start() for m in re.finditer(re.escape(literal), visible)]
        if len(positions) != 1:
            return match[0]
        start = positions[0]; end = start + len(literal)
        owned = [(a, b, value) for a, b, value in spans if a < end and b > start]
        if len(owned) < 2 or any(a < start or b > end or not NUMERIC.fullmatch(value) for a, b, value in owned):
            return match[0]
        result = []; cursor = start
        for a, b, value in owned:
            separator = visible[cursor:a]
            if not SEPARATORS.fullmatch(separator):
                return match[0]
            result.extend((separator, LRI + "[[" + value + "]]" + PDI)); cursor = b
        if not SEPARATORS.fullmatch(visible[cursor:end]):
            return match[0]
        result.append(visible[cursor:end])
        replacement = "".join(result)
        changed_groups += int(replacement != match[0])
        return replacement
    result = TOKEN.sub(replace, text)
    assert visible_text(result) == visible_text(text)
    return result, changed_groups


def regroup_source_numeric_tokens(text, source):
    return regroup_source_numeric_tokens_with_stats(text, source)[0]


def _address_correction_exemptions(primary, corrected, required, source):
    if not source:
        return set()
    from .arabic_pre_tokenize import SENSITIVE_ADDRESS_LINE_RE
    source_visible = visible_text(source)
    fields = [m['value'].strip() for m in SENSITIVE_ADDRESS_LINE_RE.finditer(source_visible)]
    prior = Counter(m[1] for m in TOKEN.finditer(primary))
    after = Counter(m[1] for m in TOKEN.finditer(corrected))
    exemptions = set()
    skeleton = lambda value: re.sub(r'[0-9]+', '#', value)
    for expected in required or []:
        if fields.count(expected) != 1 or prior[expected] or not after[expected]:
            continue
        candidates = [value for value in prior if skeleton(value) == skeleton(expected)]
        if len(candidates) != 1 or sum(skeleton(value) == skeleton(expected) for value in fields) != 1:
            continue
        actual = candidates[0]
        numbers = re.findall(r'[0-9]+', actual)
        expected_numbers = re.findall(r'[0-9]+', expected)
        if prior[actual] != 1 or actual in source_visible or len(numbers) != len(expected_numbers):
            continue
        if sum(a != b for a, b in zip(numbers, expected_numbers)) == 1:
            exemptions.add(actual)
    return exemptions


def correction_preserves_additional_literals(primary, corrected, required, source=None):
    primary = regroup_source_numeric_tokens(primary, source)
    corrected = regroup_source_numeric_tokens(corrected, source)
    prior = Counter(match[1] for match in TOKEN.finditer(primary))
    after = Counter(match[1] for match in TOKEN.finditer(corrected))
    additional = prior - Counter(required or [])
    exemptions = _address_correction_exemptions(primary, corrected, required, source)
    return all(value in exemptions or after[value] >= prior[value] for value in additional)
