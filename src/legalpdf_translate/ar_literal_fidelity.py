"""Source-bound wrapper regrouping and correction literal preservation."""
from collections import Counter
import re
import unicodedata
from itertools import product

from .output_normalize import LRI, PDI

TOKEN = re.compile(r"(?:\u2066)?\[\[([^\[\]]+)\]\](?:\u2069)?")
NUMERIC = re.compile(r"[0-9]+(?:[.,:/-][0-9]+)*")
SEPARATORS = re.compile(r"[\s=/€$£¥]*")
_MAX_GROUP_WORK = 200_000
_MAX_GROUP_STATES = 10_000
_MAX_SOURCE_LINE_WORK = 200_000
LITERAL_WRAPPER_POLICY = "lossless_source_components_v1"
LITERAL_WRAPPER_POLICY_V2 = "lossless_source_components_v2"
LITERAL_WRAPPER_POLICY_V3 = "lossless_source_components_v3"
_MAX_COMPONENT_CHARS = 120_000
_MAX_COMPONENT_WORK = 200_000
_MAX_COMPONENT_TOKENS = 512
_MAX_COMPONENT_BLOCKS = 32


def decompose_source_literal_components_with_stats(text, source_text, expected_tokens, *, literal_wrapper_policy=None):
    """Split only exact source-owned components in a complete postal witness.

    This changes internal wrappers, never a visible character or the expected
    inventory. Ambiguous, malformed or oversized proofs are a no-op. In
    particular, matching a short number somewhere inside an address is not
    ownership: split offsets come from exact source-row coordinate mappings.
    """
    from .ar_source_fields import _view, _occurrences, source_address_line_blocks

    if literal_wrapper_policy not in (None, LITERAL_WRAPPER_POLICY, LITERAL_WRAPPER_POLICY_V2, LITERAL_WRAPPER_POLICY_V3):
        raise ValueError("Unknown literal wrapper policy.")
    if (not isinstance(text, str) or not isinstance(source_text, str)
            or len(text) + len(source_text) > _MAX_COMPONENT_CHARS
            or not isinstance(expected_tokens, (tuple, list))
            or not 1 <= len(expected_tokens) <= _MAX_COMPONENT_TOKENS
            or any(not isinstance(v, str) or not v or len(v) > 256 for v in expected_tokens)):
        return text, 0

    work = len(source_text) + len(text)
    source = None

    def enclosed_span(value, token):
        # _view deliberately excludes a token's isolates when its regex sees
        # one printed enclosing [] pair. Recover coordinates locally, never
        # change the shared parser or accept a half/ambient/nested isolate.
        _, _, literal, start, end = token
        left, right = start - 1, end + 1
        if (left < 1 or right >= len(value)
                or value[left:right] != LRI + "[[" + literal + "]]" + PDI
                or value[left - 1] != "[" or value[right] != "]"
                or left > 1 and value[left - 2] in "([{"
                or right + 1 < len(value) and value[right + 1] in ")]}"):
            return None
        # Printed nesting may include whitespace or prose, not just an
        # immediately adjacent extra bracket. Token scaffolding is not printed
        # nesting and is removed only for this prefix-balance observation.
        printed_prefix = TOKEN.sub("", value[:left - 1])
        stack = []
        pairs = {")": "(", "]": "[", "}": "{"}
        for char in printed_prefix:
            if char in "([{":
                stack.append(char)
            elif char in pairs and stack and stack[-1] == pairs[char]:
                stack.pop()
        if stack or value[right + 1:].lstrip(" \t").startswith(("]", ")", "}")):
            return None
        return left, right

    def safe_view(value, *, canonical):
        nonlocal work
        # Normalization owns balanced LRI/PDI token wrappers and may place LRM
        # outside them. No other invisible format/control is proof material.
        if any((unicodedata.category(c) == "Cc" and c not in "\r\n")
               or (unicodedata.category(c) == "Cf" and c not in {LRI, PDI, "\u200e"})
               for c in value):
            return None
        view = _view(value)
        if view is None or len(view[2]) > _MAX_COMPONENT_TOKENS:
            return None
        cursor = 0
        outside = []
        tokens = []
        for token in view[2]:
            a, b, literal, start, end = token
            if (canonical and value[start:end] != LRI + "[[" + literal + "]]" + PDI
                    and literal_wrapper_policy == LITERAL_WRAPPER_POLICY_V3):
                expanded = enclosed_span(value, token)
                if expanded is None or source is None:
                    return None
                work += 3 * (len(source_text) + len(value)) + len(source[2]) + len(view[2])
                if work > _MAX_COMPONENT_WORK:
                    return None
                witnesses = [t for t in source[2] if t[2] == literal
                             and enclosed_span(source_text, t) is not None]
                printed = "[" + literal + "]"
                if (len(witnesses) != 1
                        or _occurrences(source[0], printed) != [(witnesses[0][0] - 1, witnesses[0][1] + 1)]
                        or _occurrences(view[0], printed) != [(a - 1, b + 1)]):
                    return None
                start, end = expanded
            outside.append(value[cursor:start])
            if canonical and (LRI in outside[-1] or PDI in outside[-1]):
                return None
            if canonical and value[start:end] != LRI + "[[" + literal + "]]" + PDI:
                return None
            tokens.append((a, b, literal, start, end))
            cursor = end
        outside.append(value[cursor:])
        if canonical:
            return None if LRI in outside[-1] or PDI in outside[-1] else (view[0], view[1], tokens)
        # Extraction may already isolate unrelated source runs. Require balanced,
        # unnested runs; proof rows below may contain only actual token controls.
        depth = 0
        for char in "".join(outside):
            if char == LRI:
                if depth:
                    return None
                depth = 1
            elif char == PDI:
                if not depth:
                    return None
                depth = 0
        return None if depth else view

    source = safe_view(source_text, canonical=False)
    target = safe_view(text, canonical=True)
    if source is None or target is None:
        return text, 0
    source_visible, target_visible = source[0], target[0]
    required = Counter(expected_tokens)
    source_counts = Counter(token[2] for token in source[2])
    before_counts = Counter(token[2] for token in target[2])
    blocks = source_address_line_blocks(source_visible)
    if literal_wrapper_policy in (LITERAL_WRAPPER_POLICY_V2, LITERAL_WRAPPER_POLICY_V3):
        from .ar_source_fields import source_required_prefixed_address_line_blocks
        blocks = sorted(set(blocks + source_required_prefixed_address_line_blocks(source_text, expected_tokens)), key=lambda field: field.start)
    if not blocks or len(blocks) > _MAX_COMPONENT_BLOCKS:
        return text, 0
    variants = {}
    for index, block in enumerate(blocks):
        work += len(source_visible) + len(source[2])
        if work > _MAX_COMPONENT_WORK:
            return text, 0
        if len(_occurrences(source_visible, block.value)) != 1:
            continue
        owned = [token for token in source[2] if token[0] < block.end and token[1] > block.start]
        raw_start, raw_end = source[1][block.start], source[1][block.end - 1] + 1
        raw_proof = source_text[raw_start:raw_end]
        for _, _, _, start, end in reversed(owned):
            left, right = max(start, raw_start) - raw_start, min(end, raw_end) - raw_start
            raw_proof = raw_proof[:left] + raw_proof[right:]
        if LRI in raw_proof or PDI in raw_proof:
            continue
        if (not 2 <= len(owned) <= 8 or any(a < block.start or b > block.end for a, b, *_ in owned)):
            continue
        rows = [(block.start + m.start(1), block.start + m.end(1), m[1])
                for m in re.finditer(r"([^\r\n]+)(?:\r\n|\r|\n|$)", block.value)]
        if not 2 <= len(rows) <= 3:
            continue
        parts = []
        for a, b, value, *_ in owned:
            work += len(source_visible) + len(target_visible)
            if work > _MAX_COMPONENT_WORK:
                return text, 0
            row_indexes = [n for n, (start, end, _) in enumerate(rows) if start <= a < b <= end]
            if (len(row_indexes) != 1 or required[value] != 1 or source_counts[value] != 1
                    or before_counts[value] != 0 or _occurrences(source_visible, value) != [(a, b)]
                    or len(_occurrences(target_visible, value)) != 1):
                parts = []
                break
            parts.append((row_indexes[0], a - rows[row_indexes[0]][0], b - rows[row_indexes[0]][0], value))
        if len(parts) != len(owned):
            continue
        # Only explicit horizontal address-row joins are recognized. Their
        # actual target bytes are retained, including all commas and spaces.
        for joins in product((" ", ", ", "، "), repeat=len(rows) - 1):
            offsets, literal = [], ""
            for n, (_, _, value) in enumerate(rows):
                offsets.append(len(literal))
                literal += value + (joins[n] if n < len(joins) else "")
            mapped = tuple((offsets[n] + start, offsets[n] + end, value) for n, start, end, value in parts)
            if any(literal[a:b] != value for a, b, value in mapped):
                continue
            variants.setdefault(literal, set()).add((index, mapped))

    allocations = []
    for token in target[2]:
        options = variants.get(token[2], set())
        if not options:
            continue
        if len(options) != 1:
            return text, 0
        index, parts = next(iter(options))
        if any(a[1] > b[0] for a, b in zip(parts, parts[1:])):
            return text, 0
        allocations.append((index, token, parts))
    if not allocations or [a[0] for a in allocations] != sorted({a[0] for a in allocations}):
        return text, 0

    def wrap(value):
        # Residual punctuation AND spaces remain protected together so Word's
        # literal-run rendering retains the contiguous LTR sequence.
        return LRI + "[[" + value + "]]" + PDI if value else ""

    result, cursor = [], 0
    for _, token, parts in allocations:
        _, _, literal, start, end = token
        result.append(text[cursor:start])
        prior = 0
        for a, b, value in parts:
            result.extend((wrap(literal[prior:a]), LRI + "[[" + value + "]]" + PDI))
            prior = b
        result.append(wrap(literal[prior:]))
        cursor = end
    result.append(text[cursor:])
    rebuilt = "".join(result)
    after = safe_view(rebuilt, canonical=True)
    if after is None or after[0] != target_visible:
        return text, 0
    after_counts = Counter(token[2] for token in after[2])
    if any(count > max(0, required[value] - before_counts[value])
           for value, count in (after_counts - before_counts).items() if value in required):
        return text, 0
    assert visible_text(rebuilt) == visible_text(text)
    return rebuilt, len(allocations)


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


def _source_line_restoration_groups(primary_view, corrected_view, source, *, required=None, literal_wrapper_policy=None):
    """Allocate unique exact source CR/LF blocks flattened only to ASCII spaces."""
    if literal_wrapper_policy == LITERAL_WRAPPER_POLICY_V3:
        return _source_line_restoration_groups_v3(primary_view, corrected_view, source, required)
    from .ar_source_fields import _view, _occurrences, source_address_line_blocks
    source_view = _view(source) if source else None
    if source_view is None:
        return []
    source_visible = source_view[0]
    blocks = source_address_line_blocks(source_visible)
    if literal_wrapper_policy == LITERAL_WRAPPER_POLICY_V2:
        from .ar_source_fields import source_required_prefixed_address_line_blocks
        blocks = sorted(set(blocks + source_required_prefixed_address_line_blocks(source, required)), key=lambda field: field.start)
    flattened = [re.sub(r"\r\n|\r|\n", " ", field.value) for field in blocks]
    counts = Counter(flattened)
    result, associations = [], []
    # Each witness entails full exact-occurrence scans plus two token scans.
    # Charge their upper bounds before scanning; no unbounded quadratic proof.
    scan_work = len(source_visible)
    witness_work = len(source_visible) * 2 + sum(2 * len(view[0]) + len(view[2]) for view in (primary_view, corrected_view))

    def whole_group(view, start, end):
        visible, _, tokens = view
        owned = [(index, token) for index, token in enumerate(tokens)
                 if token[0] < end and token[1] > start]
        if (not owned or owned[0][1][0] != start or owned[-1][1][1] != end
                or any(token[0] < start or token[1] > end for _, token in owned)):
            return None
        for (_, left), (_, right) in zip(owned, owned[1:]):
            if not all(char.isspace() or unicodedata.category(char).startswith("P")
                       for char in visible[left[1]:right[0]]):
                return None
        return sum(1 << index for index, _ in owned)

    for field, flat in zip(blocks, flattened):
        scan_work += witness_work
        if scan_work > _MAX_SOURCE_LINE_WORK:
            return []
        if (counts[flat] != 1 or len(_occurrences(source_visible, field.value)) != 1
                or _occurrences(source_visible, flat)):
            continue
        before = _occurrences(primary_view[0], flat)
        after = _occurrences(corrected_view[0], field.value)
        prior_restored = _occurrences(primary_view[0], field.value)
        still_flat = _occurrences(corrected_view[0], flat)
        if len(before) + len(prior_restored) != 1 or len(after) + len(still_flat) != 1:
            continue
        associations.append(((before or prior_restored)[0][0], (after or still_flat)[0][0]))
        if not before or not after:
            continue
        left = whole_group(primary_view, *before[0])
        right = whole_group(corrected_view, *after[0])
        if left is not None and right is not None:
            result.append((left, right))
    # Restored blocks must keep their source association, including when several
    # otherwise unique addresses appear in the same correction.
    if any(a[0] >= b[0] or a[1] >= b[1] for a, b in zip(associations, associations[1:])):
        return []
    return result


def _supported_component_controls(value):
    """No invisible override or half/nested isolate can supply fresh proof."""
    if not isinstance(value, str):
        return False
    depth = 0
    for char in value:
        if (unicodedata.category(char) == "Cc" and char not in "\r\n"
                or unicodedata.category(char) == "Cf" and char not in {LRI, PDI, "\u200e"}):
            return False
        if char == LRI:
            if depth:
                return False
            depth = 1
        elif char == PDI:
            if not depth:
                return False
            depth = 0
    return depth == 0


def _source_line_restoration_groups_v3(primary_view, corrected_view, source, required):
    """Restore exact CR/LF source rows from the closed per-boundary join set.

    Commas inside a row never change. Every supported join variant and the
    original block share one occurrence/ownership budget on each side.
    """
    from .ar_source_fields import (_view, _occurrences, source_address_line_blocks,
                                   source_required_prefixed_address_line_blocks)
    if not _supported_component_controls(source):
        return []
    source_view = _view(source)
    if source_view is None:
        return []
    visible = source_view[0]
    blocks = sorted(set(source_address_line_blocks(visible)
        + source_required_prefixed_address_line_blocks(source, required)), key=lambda field: field.start)
    if not blocks or len(blocks) > _MAX_COMPONENT_BLOCKS:
        return []
    free_isolates = []
    for match in re.finditer(LRI + "[^" + LRI + PDI + "]*" + PDI, source):
        owned = TOKEN.fullmatch(match[0])
        if owned is None or match[0] != LRI + "[[" + owned[1] + "]]" + PDI:
            free_isolates.append(match.span())
    variants = []
    scan_work = len(source) * 2
    for field in blocks:
        rows = re.split(r"\r\n|\r|\n", field.value)
        if not 2 <= len(rows) <= 3:
            return []
        joined = set()
        for joins in product((" ", ", ", "، "), repeat=len(rows) - 1):
            flat = "".join(row + (joins[i] if i < len(joins) else "") for i, row in enumerate(rows))
            scan_work += len(flat)
            if scan_work > _MAX_SOURCE_LINE_WORK:
                return []
            joined.add(flat)
        variants.append(joined)
    counts = Counter(flat for joined in variants for flat in joined)
    result, associations = [], []

    def whole_group(view, start, end):
        text, _, tokens = view
        owned = [(i, token) for i, token in enumerate(tokens) if token[0] < end and token[1] > start]
        if (not owned or owned[0][1][0] != start or owned[-1][1][1] != end
                or any(token[0] < start or token[1] > end for _, token in owned)):
            return None
        if any(not all(c.isspace() or unicodedata.category(c).startswith("P")
                       for c in text[a[1]:b[0]]) for (_, a), (_, b) in zip(owned, owned[1:])):
            return None
        return sum(1 << i for i, _ in owned)

    witness_work = len(visible) * 2 + sum(2 * len(v[0]) + len(v[2]) for v in (primary_view, corrected_view))
    for field, joined in zip(blocks, variants):
        scan_work += witness_work * len(joined) + len(free_isolates)
        if scan_work > _MAX_SOURCE_LINE_WORK:
            return []
        raw_start, raw_end = source_view[1][field.start], source_view[1][field.end - 1] + 1
        before = [span for flat in joined for span in _occurrences(primary_view[0], flat)]
        after_flat = [span for flat in joined for span in _occurrences(corrected_view[0], flat)]
        prior_restored = _occurrences(primary_view[0], field.value)
        after = _occurrences(corrected_view[0], field.value)
        if not (before or after_flat or prior_restored or after):
            continue
        if (any(a < raw_end and b > raw_start for a, b in free_isolates)
                or any(counts[flat] != 1 for flat in joined)
                or len(_occurrences(visible, field.value)) != 1
                or any(_occurrences(visible, flat) for flat in joined)
                or len(before) + len(prior_restored) > 1 or len(after) + len(after_flat) > 1):
            return []  # Ambiguity cannot remove an unchanged block's association.
        if len(before) + len(prior_restored) != 1 or len(after) + len(after_flat) != 1:
            continue
        associations.append(((before or prior_restored)[0][0], (after or after_flat)[0][0]))
        if before and after:
            left = whole_group(primary_view, *before[0])
            right = whole_group(corrected_view, *after[0])
            if left is not None and right is not None:
                result.append((left, right))
    if any(a[0] >= b[0] or a[1] >= b[1] for a, b in zip(associations, associations[1:])):
        return []
    return result


def _adjacent_groups_preserve(primary_view, corrected_view, protected_values, source=None, *, required=None, literal_wrapper_policy=None, source_line_proof_safe=True):
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

    source_groups = (_source_line_restoration_groups(primary_view, corrected_view, source, required=required,
        literal_wrapper_policy=literal_wrapper_policy) if source_line_proof_safe else [])
    for owned, used in source_groups:
        covered = owned & needed
        comparisons += covered.bit_count()
        if comparisons > _MAX_GROUP_WORK:
            return False
        while covered:
            bit = covered & -covered
            candidates[bit.bit_length() - 1].add((owned, used))
            covered ^= bit

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


def correction_preserves_additional_literals(primary, corrected, required, source=None, *, source_field_policy=None, literal_wrapper_policy=None, source_inline_address_join_policy=None):
    from .ar_source_fields import canonicalize_source_address_literals, _view
    if literal_wrapper_policy not in (None, LITERAL_WRAPPER_POLICY, LITERAL_WRAPPER_POLICY_V2, LITERAL_WRAPPER_POLICY_V3):
        raise ValueError("Unknown literal wrapper policy.")
    if _view(primary) is None or _view(corrected) is None:
        return False
    field_options = {"source_field_policy": source_field_policy} if source_field_policy is not None else {}
    if source_inline_address_join_policy is not None:
        field_options["source_inline_address_join_policy"] = source_inline_address_join_policy
    primary_canonical, canonical_required, _, primary_error = canonicalize_source_address_literals(primary, source, required, **field_options)
    corrected_canonical, corrected_required, _, corrected_error = canonicalize_source_address_literals(corrected, source, required, **field_options)
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
    proof_safe = (literal_wrapper_policy != LITERAL_WRAPPER_POLICY_V3
                  or _supported_component_controls(primary) and _supported_component_controls(corrected))
    return _adjacent_groups_preserve(_view(primary), _view(corrected), set(prior) - exemptions, source,
        required=required, literal_wrapper_policy=literal_wrapper_policy, source_line_proof_safe=proof_safe)
