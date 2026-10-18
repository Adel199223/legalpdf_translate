"""Source-bound wrapper regrouping and correction literal preservation."""
from collections import Counter
import re
import unicodedata

from .output_normalize import LRI, PDI

TOKEN = re.compile(r"(?:\u2066)?\[\[([^\[\]]+)\]\](?:\u2069)?")
NUMERIC = re.compile(r"[0-9]+(?:[.,:/-][0-9]+)*")
SEPARATORS = re.compile(r"[\s=/€$£¥]*")
_MAX_GROUP_WORK = 200_000
_MAX_GROUP_STATES = 10_000


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


def _adjacent_groups_preserve(primary_view, corrected_view, protected_values):
    """Allocate exact whole-token groups once on each side of a correction.

    Group boundaries are always token boundaries, never substring boundaries.
    Unprotected words/numbers cannot bridge a group; visible separators remain
    exact. This permits wrapper splits/merges without reusing a nested occurrence.
    """
    before, _, prior = primary_view
    after, _, corrected = corrected_view
    needed = sum(1 << index for index, token in enumerate(prior)
                 if token[2] in protected_values)
    if not needed:
        return True

    def can_extend(visible, tokens, index):
        return index + 1 < len(tokens) and all(
            char.isspace() or unicodedata.category(char).startswith("P")
            for char in visible[tokens[index][1]:tokens[index + 1][0]])

    candidates = {index: set() for index in range(len(prior)) if needed & (1 << index)}
    comparisons = 0
    for start in range(len(prior)):
        for target in range(len(corrected)):
            end, target_end = start, target
            while True:
                comparisons += 1
                if comparisons > _MAX_GROUP_WORK:
                    return False  # Ambiguous regrouping never weakens fidelity.
                left = before[prior[start][0]:prior[end][1]]
                right = after[corrected[target][0]:corrected[target_end][1]]
                if left == right:
                    owned = ((1 << (end + 1)) - (1 << start))
                    used = ((1 << (target_end + 1)) - (1 << target))
                    covered = owned & needed
                    comparisons += covered.bit_count()
                    if comparisons > _MAX_GROUP_WORK:
                        return False
                    while covered:
                        bit = covered & -covered
                        candidates[bit.bit_length() - 1].add((owned, used))
                        covered ^= bit
                    if not (can_extend(before, prior, end)
                            and can_extend(after, corrected, target_end)):
                        break
                    end += 1
                    target_end += 1
                elif left.startswith(right) and can_extend(after, corrected, target_end):
                    target_end += 1
                elif right.startswith(left) and can_extend(before, prior, end):
                    end += 1
                else:
                    break

    pending, seen = [(0, 0)], set()
    while pending:
        owned, used = pending.pop()
        if needed & ~owned == 0:
            return True
        if (owned, used) in seen:
            continue
        seen.add((owned, used))
        if len(seen) > _MAX_GROUP_STATES:
            return False
        options = []
        for index, matches in candidates.items():
            if owned & (1 << index):
                continue
            available = []
            for left, right in matches:
                comparisons += 1
                if comparisons > _MAX_GROUP_WORK:
                    return False
                if not left & owned and not right & used:
                    available.append((left, right))
            if not available:
                options = []
                break
            if not options or len(available) < len(options):
                options = available
        for left, right in options:
            if len(pending) + len(seen) >= _MAX_GROUP_STATES:
                return False
            pending.append((owned | left, used | right))
    return False


def correction_preserves_additional_literals(primary, corrected, required, source=None):
    from .ar_source_fields import canonicalize_source_address_literals, _view
    if _view(primary) is None or _view(corrected) is None:
        return False
    primary_canonical, canonical_required, _, primary_error = canonicalize_source_address_literals(primary, source, required)
    corrected_canonical, corrected_required, _, corrected_error = canonicalize_source_address_literals(corrected, source, required)
    if corrected_error:
        return False
    if not primary_error and Counter(canonical_required or []) == Counter(corrected_required or []):
        primary = primary_canonical
        corrected = corrected_canonical
        required = canonical_required
    primary = regroup_source_numeric_tokens(primary, source)
    corrected = regroup_source_numeric_tokens(corrected, source)
    prior = Counter(match[1] for match in TOKEN.finditer(primary))
    after = Counter(match[1] for match in TOKEN.finditer(corrected))
    additional = prior - Counter(required or [])
    exemptions = _address_correction_exemptions(primary, corrected, required, source)
    protected = set(additional) - exemptions
    if all(after[value] >= prior[value] for value in protected):
        return True
    # Required occurrences also reserve their own span during regrouping. A
    # number inside a preserved street must not replace a second required number.
    return _adjacent_groups_preserve(_view(primary), _view(corrected), set(prior) - exemptions)
