"""PDF text extraction and deterministic block re-ordering."""

from __future__ import annotations

import re
import math
import unicodedata
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Iterable

from .config import BOTTOM_ZONE_RATIO, TOP_ZONE_RATIO


NATIVE_EXTRACTION_VERSION = "ordered_structure_v5_new_runs"


class BlockGroup(str, Enum):
    HEADER = "header"
    BARCODE = "barcode"
    BODY = "body"
    FOOTER = "footer"


@dataclass(slots=True)
class TextBlock:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    group: BlockGroup = BlockGroup.BODY
    bold: bool = False
    italic: bool = False
    alignment: str | None = None


@dataclass(slots=True)
class OrderedPageText:
    text: str
    extraction_failed: bool
    newline_to_char_ratio: float
    fragmented: bool
    block_count: int
    header_blocks_count: int
    footer_blocks_count: int
    barcode_blocks_count: int
    body_blocks_count: int
    two_column_detected: bool
    page_width: float = 0.0
    page_height: float = 0.0
    body_blocks: tuple[TextBlock, ...] = field(default_factory=tuple)
    all_blocks: tuple[TextBlock, ...] = field(default_factory=tuple)
    tables: tuple[dict, ...] = field(default_factory=tuple)
    extraction_metadata: dict = field(default_factory=dict)


HEADER_ANCHORS = [
    "tribunal judicial",
    "juízo",
    "juizo",
    "comarca",
    "largo",
    "telef",
    "fax",
    "mail",
    "notificação por via postal simples",
    "notificacao por via postal simples",
    "processo",
    "referência deste documento",
    "referencia deste documento",
    "certificação citius",
    "certificacao citius",
]

FOOTER_ANCHORS = [
    "as férias judiciais",
    "as ferias judiciais",
    "indicar na resposta",
    "pág.",
    "pag.",
    "page",
]

# A bare "p." also occurs in legal prose ("p. e p. pelo art."). Only
# recognize that abbreviation as furniture when it labels a page counter.
_ABBREVIATED_PAGE_COUNTER_RE = re.compile(
    r"^\s*p\.\s*\d+(?:\s*(?:/|de|of)\s*\d+)?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

BARCODE_PATTERNS = [
    re.compile(r"%\*.+\*%"),
    re.compile(r"\b200460-[A-Za-z0-9/-]+\b"),
    # Generic identifiers need a digit in the candidate itself. Ordinary
    # hyphenated words inside prose are not barcode furniture.
    re.compile(r"\b(?=[A-Za-z0-9./-]*[0-9])[A-Za-z0-9]{3,}[-/][A-Za-z0-9./-]{5,}\b"),
    re.compile(r"\b\d{6,}[-/][\dA-Za-z./-]{2,}\b"),
]

_REFERENCE_LABEL_RE = re.compile(
    r"^\s*(?:(?:processo|proc|refer[eê]ncia|ref)\b\.?|n(?:\.?\s*[º°]|\.))",
    re.IGNORECASE,
)


def get_page_count(pdf_path: Path) -> int:
    import fitz

    with fitz.open(pdf_path) as doc:
        return doc.page_count


def _sort_key(block: TextBlock) -> tuple[float, float]:
    return (block.y0, block.x0)


def _text_has_anchor(text: str, anchors: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(anchor in lowered for anchor in anchors)


def _is_barcode_like(text: str) -> bool:
    if "%*" in text:
        return True
    stripped = text.strip()
    compact = re.sub(r"\s+", "", stripped)
    # Removing spaces also joins ordinary ASCII prose, including sentences
    # with numbers. Only compact a single identifier or spaced numeric code.
    compact_identifier = not re.search(r"\s", stripped) or re.fullmatch(r"[0-9\s]+", stripped)
    if (compact_identifier and re.search(r"[0-9]", compact)
            and re.fullmatch(r"[A-Za-z0-9%*/\-]{12,}", compact)):
        return True
    return any(pattern.search(text) for pattern in BARCODE_PATTERNS)


def _is_labelled_reference_identifier(text: str) -> bool:
    """A labelled case/document number is prose, not standalone barcode text.

    Limit the exception to a single explicit label with a numeric identifier;
    court headings, multiline furniture and actual barcode markers retain their
    existing classification. Source text itself is never rewritten.
    """
    if "\n" in text.strip() or "%*" in text:
        return False
    label = _REFERENCE_LABEL_RE.match(text)
    return bool(label and re.search(r"\d", text[label.end():]))


def _line_text(line: dict) -> str:
    spans = line.get("spans", [])
    return "".join(str(span.get("text", "")) for span in spans)


SOURCE_FIELD_POLICY = "baseline_label_value_v1"
SOURCE_QUESTION_ROW_POLICY = "baseline_boolean_question_v1"
PRIMARY_PAGE_EVIDENCE_POLICY = "source_page_occurrences_v1"


def check_primary_page_evidence_policy(policy: str | None) -> None:
    from .ordinary_source_acronyms import POLICY as acronym_policy
    if policy is not None and (type(policy) is not str or policy not in {PRIMARY_PAGE_EVIDENCE_POLICY, acronym_policy}):
        raise ValueError("Unknown primary page evidence policy.")


def _field_label(text: str) -> bool:
    value = text.strip(" ")
    return (1 < len(value) <= 60 and value.endswith(":") and value[0].isalpha()
            and len(value[:-1].split()) <= 8
            and all(c.isalpha() or c.isdecimal() or c in " .()/-" for c in value[:-1]))


def _horizontal_baseline(line: dict) -> float | None:
    direction = line.get("dir")
    if (type(direction) not in {tuple, list} or len(direction) != 2
            or any(type(v) not in {int, float} or not math.isfinite(v) for v in direction)
            or abs(direction[0] - 1) > 1e-6 or abs(direction[1]) > 1e-6):
        return None
    origins = [span.get("origin") for span in line.get("spans", []) if str(span.get("text", "")).strip()]
    if not origins or any(type(p) not in {list, tuple} or len(p) != 2
                          or type(p[1]) not in {int, float} or not math.isfinite(p[1]) for p in origins):
        return None
    ys = [p[1] for p in origins]
    return sum(ys) / len(ys) if max(ys) - min(ys) <= .1 else None


_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_FIELD_CLOCK = re.compile(r"(?<![\w:])(?:[01][0-9]|2[0-3]):[0-5][0-9]h?(?![\w:])")


def _date_time_field(label: str, value: str) -> bool:
    """Only weak barcode matches that are entirely explained by source dates."""
    if not _field_label(label) or len(value) > 220 or not _FIELD_CLOCK.search(value):
        return False
    text = label + " " + value
    if ("%*" in text or any(unicodedata.category(c) in {"Cc", "Cf", "Zl", "Zp"} for c in text)
            or any(BARCODE_PATTERNS[index].search(text) for index in (0, 1, 3))):
        return False
    matches = [match.group() for match in BARCODE_PATTERNS[2].finditer(text)]
    if not matches or any(not _ISO_DATE.fullmatch(token) for token in matches):
        return False
    try:
        for token in matches:
            date.fromisoformat(token)
    except ValueError:
        return False
    remaining = _FIELD_CLOCK.sub("", _ISO_DATE.sub("", text))
    return not any(c.isdecimal() for c in remaining)


def _native_date_time_fields(page_dict: dict, page_width: float, page_height: float) -> set[tuple]:
    """Identify intact, horizontal label/value blocks to keep in geometric body flow."""
    fields = set()
    for raw in page_dict.get("blocks", []):
        lines = raw.get("lines", [])
        if raw.get("type") != 0 or len(lines) != 2:
            continue
        if any(type(line.get("wmode")) is not int or line["wmode"] != 0
               or not 1 <= len(line.get("spans", [])) <= 32 for line in lines):
            continue
        texts = [span.get("text") for line in lines for span in line["spans"]]
        if any(type(text) is not str for text in texts) or sum(map(len, texts)) > 320:
            continue
        label, value = (_line_text(line) for line in lines)
        if not _date_time_field(label, value):
            continue
        baselines = [_horizontal_baseline(line) for line in lines]
        if None in baselines or abs(baselines[0] - baselines[1]) > .1:
            continue
        left, right = (line.get("bbox") for line in lines)
        block = raw.get("bbox")
        if any(type(box) not in (list, tuple) or len(box) != 4
               or any(type(v) not in (int, float) or not math.isfinite(v) for v in box)
               or not (0 <= box[0] < box[2] <= page_width and 0 <= box[1] < box[3] <= page_height)
               for box in (left, right, block)):
            continue
        gap = right[0] - left[2]
        overlap = min(left[3], right[3]) - max(left[1], right[1])
        if (not 2 <= gap <= min(120, .25 * page_width) or abs(left[1] - right[1]) > .5
                or overlap < .8 * min(left[3] - left[1], right[3] - right[1])):
            continue
        union = (left[0], min(left[1], right[1]), right[2], max(left[3], right[3]))
        if any(abs(edge - bound) > .5 for edge, bound in zip(block, union)):
            continue
        fields.add((*block, label + "\n" + value))
    return fields


def _order_field_lines(lines: list[dict], page_width: float) -> list[tuple]:
    """Repair only a unique adjacent raw label/value pair in one PDF block.

    No global row rounding, joining, text rewriting or column flattening. The
    old geometric order of every unclaimed line stays exactly as it was.
    """
    records = [(float(line.get("bbox", [0, 0, 0, 0])[1]), float(line.get("bbox", [0, 0, 0, 0])[0]),
                _line_text(line), index) for index, line in enumerate(lines) if _line_text(line).strip()]
    ordered = sorted(records, key=lambda item: (item[0], item[1]))
    positions_by_index = {row[3]: position for position, row in enumerate(ordered)}
    baselines = [_horizontal_baseline(line) for line in lines]
    finite_baselines = sorted(value for value in baselines if value is not None)
    for index, left in enumerate(lines[:-1]):
        right = lines[index + 1]
        left_text, right_text = _line_text(left), _line_text(right)
        baseline = baselines[index]
        if (not _field_label(left_text) or _field_label(right_text) or not right_text.strip()
                or len(right_text) > 220 or baseline is None or baselines[index + 1] is None
                or abs(baseline - baselines[index + 1]) > .1
                or any(c in left_text + right_text for c in "\t\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029")):
            continue
        # A third same-baseline line makes a multi-cell/column row ambiguous.
        if bisect_right(finite_baselines, baseline + .1) - bisect_left(finite_baselines, baseline - .1) != 2:
            continue
        a, b = left.get("bbox"), right.get("bbox")
        if (type(a) not in {tuple, list} or type(b) not in {tuple, list} or len(a) != 4 or len(b) != 4
                or any(type(v) not in {int, float} or not math.isfinite(v) for v in (*a, *b))
                or not (a[0] < a[2] <= b[0] - 2 < b[2]) or abs(a[1] - b[1]) > .5
                or not 0 <= b[0] - a[2] <= min(120, .25 * page_width)
                or min(a[3], b[3]) - max(a[1], b[1]) < .8 * min(a[3] - a[1], b[3] - b[1])):
            continue
        positions = sorted(positions_by_index[row] for row in (index, index + 1) if row in positions_by_index)
        if len(positions) == 2 and positions[1] == positions[0] + 1 and ordered[positions[0]][3] == index + 1:
            ordered[positions[0]], ordered[positions[1]] = ordered[positions[1]], ordered[positions[0]]
            positions_by_index[index], positions_by_index[index + 1] = positions[0], positions[1]
    return ordered


def _question_label(text: str) -> bool:
    value = text.strip(" ")
    return (1 < len(text) <= 80 and value.endswith("?") and value[0].isalpha()
            and len(value[:-1].split()) <= 12
            and all(c.isalpha() or c.isdecimal() or c in " .()/-" for c in value[:-1]))


def _boolean_answer(text: str) -> bool:
    # Recognition only: the original line, spelling, accents and spacing are
    # never rewritten. Other languages and punctuated/expanded answers abstain.
    return unicodedata.normalize("NFC", text.strip(" ")).casefold() in {"sim", "não"}


def _order_question_lines(lines: list[dict], page_width: float, ordered: list[tuple]) -> list[tuple]:
    """Opt-in same-baseline question/boolean repair; leave colon-v1 untouched."""
    ordered = list(ordered)
    if not math.isfinite(page_width) or page_width <= 0:
        return ordered
    positions_by_index = {row[3]: position for position, row in enumerate(ordered)}
    baselines = [_horizontal_baseline(line) for line in lines]
    finite_baselines = sorted(value for value in baselines if value is not None)
    for index, left in enumerate(lines[:-1]):
        right = lines[index + 1]
        left_text, right_text = _line_text(left), _line_text(right)
        baseline = baselines[index]
        if (not _question_label(left_text) or not _boolean_answer(right_text)
                or baseline is None or baselines[index + 1] is None
                or abs(baseline - baselines[index + 1]) > .1
                or any(c in left_text + right_text for c in "\t\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029")):
            continue
        if bisect_right(finite_baselines, baseline + .1) - bisect_left(finite_baselines, baseline - .1) != 2:
            continue
        # A line with an unknown baseline cannot disprove a competing cell if
        # its box covers this row (or is itself malformed).
        unknown_row = False
        for other_index, other in enumerate(lines):
            if other_index in (index, index + 1) or not _line_text(other).strip() or baselines[other_index] is not None:
                continue
            box = other.get("bbox")
            if (type(box) not in {tuple, list} or len(box) != 4
                    or any(type(v) not in {int, float} or not math.isfinite(v) for v in box)
                    or box[1] - .1 <= baseline <= box[3] + .1):
                unknown_row = True
                break
        if unknown_row:
            continue
        a, b = left.get("bbox"), right.get("bbox")
        if (type(a) not in {tuple, list} or type(b) not in {tuple, list} or len(a) != 4 or len(b) != 4
                or any(type(v) not in {int, float} or not math.isfinite(v) for v in (*a, *b))
                or not (a[0] < a[2] <= b[0] - 2 < b[2]) or abs(a[1] - b[1]) > .5
                or not 0 <= b[0] - a[2] <= min(120, .25 * page_width)
                or min(a[3], b[3]) - max(a[1], b[1]) < .8 * min(a[3] - a[1], b[3] - b[1])):
            continue
        positions = sorted(positions_by_index[row] for row in (index, index + 1) if row in positions_by_index)
        if len(positions) == 2 and positions[1] == positions[0] + 1 and ordered[positions[0]][3] == index + 1:
            ordered[positions[0]], ordered[positions[1]] = ordered[positions[1]], ordered[positions[0]]
            positions_by_index[index], positions_by_index[index + 1] = positions[0], positions[1]
    return ordered


def build_text_blocks_from_page_dict(page_dict: dict, *, source_field_policy: str | None = None,
                                     source_question_row_policy: str | None = None) -> list[TextBlock]:
    if source_field_policy not in {None, SOURCE_FIELD_POLICY}:
        raise ValueError("Unknown source field policy.")
    if source_question_row_policy not in (None, SOURCE_QUESTION_ROW_POLICY):
        raise ValueError("Unknown source question row policy.")
    blocks: list[TextBlock] = []
    for block in page_dict.get("blocks", []):
        if int(block.get("type", -1)) != 0:
            continue
        bbox = block.get("bbox", [0.0, 0.0, 0.0, 0.0])
        lines_data = []
        for line in block.get("lines", []):
            line_bbox = line.get("bbox", [0.0, 0.0, 0.0, 0.0])
            text = _line_text(line)
            if text.strip() == "":
                continue
            lines_data.append((float(line_bbox[1]), float(line_bbox[0]), text))
        if not lines_data:
            continue
        if source_field_policy == SOURCE_FIELD_POLICY:
            lines_data = _order_field_lines(block.get("lines", []), float(page_dict.get("width", 0)))
        elif source_question_row_policy is not None:
            lines_data = sorted([(float(line.get("bbox", [0, 0, 0, 0])[1]), float(line.get("bbox", [0, 0, 0, 0])[0]),
                _line_text(line), index) for index, line in enumerate(block.get("lines", [])) if _line_text(line).strip()],
                key=lambda item: (item[0], item[1]))
        else:
            lines_data.sort(key=lambda item: (item[0], item[1]))
        if source_question_row_policy is not None:
            lines_data = _order_question_lines(block.get("lines", []), float(page_dict.get("width", 0)), lines_data)
        text = "\n".join(item[2] for item in lines_data)
        spans = [span for line in block.get("lines", []) for span in line.get("spans", [])
                 if str(span.get("text", "")).strip()]
        blocks.append(
            TextBlock(
                x0=float(bbox[0]),
                y0=float(bbox[1]),
                x1=float(bbox[2]),
                y1=float(bbox[3]),
                text=text,
                bold=bool(spans) and all(int(span.get("flags", 0)) & 16 for span in spans),
                italic=bool(spans) and all(int(span.get("flags", 0)) & 2 for span in spans),
            )
        )
    return blocks


def _classify_blocks(blocks: list[TextBlock], page_width: float, page_height: float,
                     *, preserve_structure: bool = False, date_time_fields: set[tuple] | None = None) -> None:
    top_zone = page_height * TOP_ZONE_RATIO
    bottom_zone_start = page_height * (1.0 - BOTTOM_ZONE_RATIO)
    near_top = page_height * 0.30
    for block in blocks:
        if preserve_structure and _is_labelled_reference_identifier(block.text):
            # Legacy extraction promotes identifier-like text before body text.
            # New structured sources must keep labelled references in their
            # own geometric flow, including when just inside the header zone.
            block.group = BlockGroup.BODY
            continue
        header_anchor = _text_has_anchor(block.text, HEADER_ANCHORS)
        footer_anchor = (_text_has_anchor(block.text, FOOTER_ANCHORS)
                         or _ABBREVIATED_PAGE_COUNTER_RE.search(block.text) is not None)
        barcode_anchor = _is_barcode_like(block.text)
        if header_anchor and block.y0 <= top_zone:
            block.group = BlockGroup.HEADER
            continue
        if footer_anchor and block.y1 >= bottom_zone_start:
            block.group = BlockGroup.FOOTER
            continue
        field_key = (block.x0, block.y0, block.x1, block.y1, block.text)
        if barcode_anchor and block.y0 <= near_top and not (date_time_fields and field_key in date_time_fields):
            block.group = BlockGroup.BARCODE
            continue
        block.group = BlockGroup.BODY


def _detect_two_columns(body_blocks: list[TextBlock], page_width: float) -> tuple[bool, list[TextBlock], list[TextBlock]]:
    if len(body_blocks) < 4:
        return (False, [], [])
    page_mid_x = page_width / 2.0
    left = [b for b in body_blocks if b.x0 < page_mid_x]
    right = [b for b in body_blocks if b.x0 >= page_mid_x]
    if len(left) < 2 or len(right) < 2:
        return (False, [], [])
    left_extent = max(block.x1 for block in left)
    right_start = min(block.x0 for block in right)
    if right_start - left_extent < page_width * 0.05:
        return (False, [], [])
    return (True, left, right)


def order_text_blocks(blocks: list[TextBlock], page_width: float, page_height: float) -> str:
    ordered, _ = order_text_blocks_with_metadata(blocks, page_width=page_width, page_height=page_height)
    return ordered


def order_text_blocks_with_metadata(
    blocks: list[TextBlock],
    page_width: float,
    page_height: float,
    *,
    preserve_structure: bool = False,
    date_time_fields: set[tuple] | None = None,
) -> tuple[str, dict[str, object]]:
    if not blocks:
        return (
            "",
            {
                "block_count": 0,
                "header_blocks_count": 0,
                "footer_blocks_count": 0,
                "barcode_blocks_count": 0,
                "body_blocks_count": 0,
                "two_column_detected": False,
                "ordered_body_blocks": tuple(),
            },
        )
    _classify_blocks(blocks, page_width=page_width, page_height=page_height,
                     preserve_structure=preserve_structure, date_time_fields=date_time_fields)
    header = sorted((b for b in blocks if b.group == BlockGroup.HEADER), key=_sort_key)
    barcode = sorted((b for b in blocks if b.group == BlockGroup.BARCODE), key=_sort_key)
    body = [b for b in blocks if b.group == BlockGroup.BODY]
    footer = sorted((b for b in blocks if b.group == BlockGroup.FOOTER), key=_sort_key)

    is_two_col, left, right = _detect_two_columns(body, page_width=page_width)
    if is_two_col:
        ordered_body = sorted(left, key=_sort_key) + sorted(right, key=_sort_key)
    else:
        ordered_body = sorted(body, key=_sort_key)

    ordered_blocks = header + barcode + ordered_body + footer
    lines: list[str] = []
    for block in ordered_blocks:
        if block.text.strip() == "":
            continue
        lines.append(block.text)
    return (
        "\n".join(lines),
        {
            "block_count": len(blocks),
            "header_blocks_count": len(header),
            "footer_blocks_count": len(footer),
            "barcode_blocks_count": len(barcode),
            "body_blocks_count": len(body),
            "two_column_detected": is_two_col,
            "ordered_body_blocks": tuple(ordered_body),
            "ordered_all_blocks": tuple(ordered_blocks),
        },
    )


def _fragmented_heuristic(text: str) -> bool:
    lines = [line for line in text.split("\n") if line.strip() != ""]
    if len(lines) < 20:
        return False
    avg_len = sum(len(line) for line in lines) / len(lines)
    short_line_count = sum(1 for line in lines if len(line) <= 12)
    return avg_len < 18 and short_line_count / len(lines) > 0.6


def _extract_tables(page, page_index: int) -> tuple[list[dict], list[str]]:
    """Keep only ordinary grids whose individual cell text matches spatial words.

    A page-global bag of tokens cannot detect swapped dates. Each extracted cell
    is checked against the words inside its own box; merged/overlapping cells
    remain original body text and require review.
    """
    tables, warnings = [], []
    if not hasattr(page, "find_tables"):
        return [], ["table_extraction_unavailable"]
    try:
        words = page.get_text("words")
        for number, table in enumerate(page.find_tables().tables, 1):
            texts = table.extract()
            cells = []
            valid = bool(table.rows)
            columns = None
            for row_index, row in enumerate(table.rows):
                columns = len(row.cells) if columns is None else columns
                valid = valid and len(row.cells) == columns
                for col_index, bbox in enumerate(row.cells):
                    if bbox is None:
                        valid = False
                        continue
                    own_words = [word for word in words if bbox[0] <= (word[0] + word[2]) / 2 < bbox[2]
                                 and bbox[1] <= (word[1] + word[3]) / 2 < bbox[3]]
                    own_words.sort(key=lambda word: (word[5], word[6], word[7]))
                    source_text = " ".join(str(word[4]) for word in own_words)
                    present = row_index < len(texts) and col_index < len(texts[row_index])
                    cell_text = (texts[row_index][col_index] or "") if present else ""
                    valid = valid and present and " ".join(cell_text.split()) == " ".join(source_text.split())
                    # A word crossing a boundary cannot be confidently assigned.
                    valid = valid and all(word[0] >= bbox[0] - 1 and word[1] >= bbox[1] - 1
                                          and word[2] <= bbox[2] + 1 and word[3] <= bbox[3] + 1 for word in own_words)
                    cells.append({"text": cell_text or "", "source_text": source_text, "bbox": list(bbox),
                                  "row": row_index, "col": col_index})
            for index, cell in enumerate(cells):
                a = cell["bbox"]
                for other in cells[index + 1:]:
                    b = other["bbox"]
                    if min(a[2], b[2]) - max(a[0], b[0]) > 1 and min(a[3], b[3]) - max(a[1], b[1]) > 1:
                        valid = False
            if not valid:
                warnings.append("table_cell_association_uncertain")
                continue
            tables.append({"table_id": f"p{page_index + 1:04d}_t{number:04d}",
                           "bbox": list(table.bbox), "cells": cells, "association_verified": True})
    except Exception:
        return [], ["table_extraction_unavailable"]
    return tables, sorted(set(warnings))


def extract_ordered_page_text(pdf_path: Path, page_index: int, *, preserve_structure: bool = False,
                              source_field_policy: str | None = None,
                              source_question_row_policy: str | None = None,
                              primary_page_evidence_policy: str | None = None) -> OrderedPageText:
    check_primary_page_evidence_policy(primary_page_evidence_policy)
    if source_field_policy not in {None, SOURCE_FIELD_POLICY}:
        raise ValueError("Unknown source field policy.")
    if source_question_row_policy not in (None, SOURCE_QUESTION_ROW_POLICY):
        raise ValueError("Unknown source question row policy.")
    page_width = 0.0
    page_height = 0.0
    tables: list[dict] = []
    extraction_metadata: dict = {}
    try:
        import fitz

        with fitz.open(pdf_path) as doc:
            page = doc.load_page(page_index)
            page_width = float(page.rect.width)
            page_height = float(page.rect.height)
            page_dict = page.get_text("dict")
            if preserve_structure:
                # Text coordinates are unrotated even when page.rect is rotated.
                page_width = float(page_dict.get("width", page_width))
                page_height = float(page_dict.get("height", page_height))
                extraction_metadata = {"extraction_version": NATIVE_EXTRACTION_VERSION,
                                       "coordinate_space": "pdf_points", "paper_size_basis": "source_pdf",
                                       "rotation_degrees": int(page.rotation), "native_backend_version": fitz.VersionBind,
                                       "warnings": ["rotated_source_requires_review"] if page.rotation else []}
                # A usable text layer can still omit a substantial scanned
                # region. Retain this source-only signal for full-page OCR.
                image_area = sum(max(0.0, float(raw["bbox"][2]) - float(raw["bbox"][0]))
                                 * max(0.0, float(raw["bbox"][3]) - float(raw["bbox"][1]))
                                 for raw in page_dict.get("blocks", [])
                                 if raw.get("type") == 1 and isinstance(raw.get("bbox"), (list, tuple)) and len(raw["bbox"]) == 4)
                extraction_metadata["raster_area_ratio"] = min(1.0, image_area / max(1.0, page_width * page_height))
                if extraction_metadata["raster_area_ratio"] >= 0.20:
                    extraction_metadata["warnings"].append("mixed_raster_source_requires_review")
                tables, warnings = _extract_tables(page, page_index)
                extraction_metadata["warnings"].extend(warnings)
            blocks = build_text_blocks_from_page_dict(page_dict,
                **({"source_field_policy": source_field_policy} if source_field_policy is not None and not page.rotation else {}),
                **({"source_question_row_policy": source_question_row_policy} if source_question_row_policy is not None and not page.rotation else {}))
            if source_field_policy is not None:
                extraction_metadata["source_field_policy"] = source_field_policy
            if source_question_row_policy is not None:
                extraction_metadata["source_question_row_policy"] = source_question_row_policy
                extraction_metadata["source_question_row_geometry_enabled"] = not bool(page.rotation)
            ordered_text, metadata = order_text_blocks_with_metadata(
                blocks,
                page_width=page_width,
                page_height=page_height,
                preserve_structure=preserve_structure,
                date_time_fields=(_native_date_time_fields(page_dict, page_width, page_height)
                                  if primary_page_evidence_policy and not page.rotation else None),
            )
    except Exception:
        return OrderedPageText(
            text="",
            extraction_failed=True,
            newline_to_char_ratio=1.0,
            fragmented=False,
            block_count=0,
            header_blocks_count=0,
            footer_blocks_count=0,
            barcode_blocks_count=0,
            body_blocks_count=0,
            two_column_detected=False,
            page_width=0.0,
            page_height=0.0,
            body_blocks=tuple(),
        )

    char_count = len(ordered_text)
    ratio = (ordered_text.count("\n") / char_count) if char_count else 1.0
    return OrderedPageText(
        text=ordered_text,
        extraction_failed=False,
        newline_to_char_ratio=ratio,
        fragmented=_fragmented_heuristic(ordered_text),
        block_count=int(metadata["block_count"]),
        header_blocks_count=int(metadata["header_blocks_count"]),
        footer_blocks_count=int(metadata["footer_blocks_count"]),
        barcode_blocks_count=int(metadata["barcode_blocks_count"]),
        body_blocks_count=int(metadata["body_blocks_count"]),
        two_column_detected=bool(metadata["two_column_detected"]),
        page_width=page_width,
        page_height=page_height,
        body_blocks=tuple(metadata.get("ordered_body_blocks", tuple())),
        all_blocks=tuple(metadata.get("ordered_all_blocks", tuple())) if preserve_structure else (),
        tables=tuple(tables),
        extraction_metadata=extraction_metadata,
    )
