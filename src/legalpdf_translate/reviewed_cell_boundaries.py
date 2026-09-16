"""Conservative inline cuts for explicitly reviewed editable metadata cells.

These helpers do not partition, alter or approve text. A caller must separately
validate its ordinary whole-line boundaries, complete independent source/target
coverage and exact retained evidence. An extra cut is usable only at a returned
pipe boundary AND between an eligible immediate same-parent fragment pair.
"""
from __future__ import annotations

from collections.abc import Sequence
import json
import re
import unicodedata

from .reviewed_regions import (
    RegionFragmentInput, ReviewedRegionsError, validate_reviewed_regions,
)

MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_PIPE_BOUNDARIES = 5000
MAX_SCOPE_DEPTH = 128
_HORIZONTAL = frozenset(" \t")
_BIDI_OPEN = {"\u202a": "embedding", "\u202b": "embedding",
              "\u202d": "embedding", "\u202e": "embedding",
              "\u2066": "isolate", "\u2067": "isolate", "\u2068": "isolate"}
_LITERAL_ISOLATE = re.compile("\u2066\\[\\[([^\\[\\]|\\r\\n]+)\\]\\]\u2069")


class ReviewedCellBoundariesError(ValueError):
    """Only finite content-free categories leave this module."""


def _fail(code: str) -> None:
    raise ReviewedCellBoundariesError(code)


def _safe_field_edge(char: str, *, right: bool) -> bool:
    category = unicodedata.category(char)
    if char == "|" or category[0] in {"C", "Z"} or char.isspace():
        return False
    if right and (category[0] == "M" or 0x1F3FB <= ord(char) <= 0x1F3FF):
        return False
    return True


def _literal_isolate_edges(text: str) -> tuple[frozenset[int], frozenset[int]]:
    """Recognize complete LRI[[literal]]PDI units without opening a cut inside.

    Only this existing literal representation can supply a format-control edge.
    Nested controls, empty/padded fields and unsafe starting graphemes stay out.
    The ordinary full-text scope scan independently validates surrounding text.
    """
    left, right = set(), set()
    for match in _LITERAL_ISOLATE.finditer(text):
        content = match[1]
        if (any(unicodedata.category(char)[0] == "C" for char in content)
                or not _safe_field_edge(content[-1], right=False)
                or not _safe_field_edge(content[0], right=True)):
            continue
        left.add(match.end() - 1)
        right.add(match.start())
    return frozenset(left), frozenset(right)


def pipe_cell_boundaries(text: str) -> frozenset[int]:
    """Return interior cuts after a spaced ASCII pipe and its following space.

    At least one ASCII space/tab is required on each side of the pipe. The
    preceding cell owns the pipe and ALL following ASCII space/tabs. A cut is
    outside wrappers and bidi scopes and starts a nonempty field on the same
    line. Complete LRI[[literal]]PDI units may remain at either field edge;
    their controls and content belong to that cell together. No arbitrary
    whitespace, word/name/clock or grapheme cut is offered.
    This is a narrow reviewed-delimiter rule, not a general grapheme segmenter
    or a semantic assertion that an arbitrary pipe denotes a metadata field.

    The result excludes whole-line boundaries and parent endpoints; the caller
    validates those separately. All input, including text after the last pipe,
    is scanned so a malformed scope cannot hide behind an earlier safe cut.
    """
    if type(text) is not str or len(text) > MAX_TEXT_BYTES:
        _fail("cell_invalid_text")
    try:
        if len(text.encode("utf-8")) > MAX_TEXT_BYTES:
            _fail("cell_text_too_large")
    except UnicodeError:
        _fail("cell_invalid_unicode")
    safe: set[int] = set()
    literal_left, literal_right = _literal_isolate_edges(text)
    stack: list[str] = []
    placeholder = False
    index = 0
    while index < len(text):
        if text.startswith("[[", index):
            if placeholder:
                _fail("cell_nested_placeholder")
            placeholder = True
            index += 2
            continue
        if text.startswith("]]", index):
            if not placeholder:
                _fail("cell_unmatched_placeholder")
            placeholder = False
            index += 2
            continue
        char = text[index]
        if char in _BIDI_OPEN:
            if len(stack) >= MAX_SCOPE_DEPTH:
                _fail("cell_scope_depth_exceeded")
            stack.append(_BIDI_OPEN[char])
        elif char in {"\u202c", "\u2069"}:
            expected = "embedding" if char == "\u202c" else "isolate"
            if not stack or stack[-1] != expected:
                _fail("cell_unbalanced_bidi_scope")
            stack.pop()
        if (char == "\r" and (index + 1 == len(text) or text[index + 1] != "\n")
                or char in {"\u0085", "\u2028", "\u2029"}):
            _fail("cell_unsupported_line_separator")
        if (char == "|" and not stack and not placeholder and 0 < index < len(text) - 1
                and text[index - 1] in _HORIZONTAL and text[index + 1] in _HORIZONTAL):
            left, cut = index - 1, index + 1
            while left >= 0 and text[left] in _HORIZONTAL:
                left -= 1
            while cut < len(text) and text[cut] in _HORIZONTAL:
                cut += 1
            if (left >= 0 and cut < len(text)
                    and (_safe_field_edge(text[left], right=False) or left in literal_left)
                    and (_safe_field_edge(text[cut], right=True) or cut in literal_right)):
                if len(safe) >= MAX_PIPE_BOUNDARIES:
                    _fail("cell_too_many_boundaries")
                safe.add(cut)
        index += 1
    if stack or placeholder:
        _fail("cell_unclosed_text_scope")
    return frozenset(safe)


def validated_inline_cell_pairs(
    layout: dict, *, fragments: Sequence[RegionFragmentInput],
    page_number: int, image_size_px: tuple[int, int],
) -> frozenset[tuple[str, str]]:
    """Return increasing source-ID pairs in distinct one-fragment body cells.

    First independently validate the COMPLETE layout, including all owners,
    roles, boxes and ordering. Then return pairs belonging to the same table
    row. Only cells containing exactly one body fragment participate; headers,
    signatures, ordinary paragraphs, furniture and empty/multi-fragment cells
    cannot acquire inline-cut authority. Physical column order does not change
    immutable source order. The caller additionally requires immediate adjacent
    fragments of the same parent and checks each independent text offset.
    """
    try:
        canonical = validate_reviewed_regions(
            layout, fragments=fragments, page_number=page_number,
            image_size_px=image_size_px,
        )
        checked = json.loads(canonical)
        ranks = {fragment.rendering_id: rank for rank, fragment in enumerate(fragments)}
        roles = {fragment.rendering_id: fragment.role for fragment in fragments}
        pairs: set[tuple[str, str]] = set()
        for block in checked["body"]:
            if block["kind"] != "table":
                continue
            for row in block["rows"]:
                eligible = []
                for cell in row["cells"]:
                    identifiers = cell["fragment_ids"]
                    if len(identifiers) == 1 and roles[identifiers[0]] == "body":
                        eligible.append(identifiers[0])
                ordered = sorted(eligible, key=ranks.__getitem__)
                for index, first in enumerate(ordered):
                    pairs.update((first, second) for second in ordered[index + 1:])
        return frozenset(pairs)
    except (ReviewedRegionsError, ValueError, TypeError, KeyError, AttributeError, OverflowError):
        _fail("cell_invalid_region_layout")
