"""PDF text extraction and deterministic block re-ordering."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable

from .config import BOTTOM_ZONE_RATIO, TOP_ZONE_RATIO


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
    "p.",
]

BARCODE_PATTERNS = [
    re.compile(r"%\*.+\*%"),
    re.compile(r"\b200460-[A-Za-z0-9/-]+\b"),
    re.compile(r"\b[A-Za-z0-9]{3,}[-/][A-Za-z0-9./-]{5,}\b"),
    re.compile(r"\b\d{6,}[-/][\dA-Za-z./-]{2,}\b"),
]


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
    compact = re.sub(r"\s+", "", text)
    if re.fullmatch(r"[A-Za-z0-9%*/\-]{12,}", compact or ""):
        return True
    return any(pattern.search(text) for pattern in BARCODE_PATTERNS)


def _line_text(line: dict) -> str:
    spans = line.get("spans", [])
    return "".join(str(span.get("text", "")) for span in spans)


def build_text_blocks_from_page_dict(page_dict: dict) -> list[TextBlock]:
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
        lines_data.sort(key=lambda item: (item[0], item[1]))
        text = "\n".join(item[2] for item in lines_data)
        blocks.append(
            TextBlock(
                x0=float(bbox[0]),
                y0=float(bbox[1]),
                x1=float(bbox[2]),
                y1=float(bbox[3]),
                text=text,
            )
        )
    return blocks


def _classify_blocks(blocks: list[TextBlock], page_width: float, page_height: float) -> None:
    top_zone = page_height * TOP_ZONE_RATIO
    bottom_zone_start = page_height * (1.0 - BOTTOM_ZONE_RATIO)
    near_top = page_height * 0.30
    for block in blocks:
        header_anchor = _text_has_anchor(block.text, HEADER_ANCHORS)
        footer_anchor = _text_has_anchor(block.text, FOOTER_ANCHORS)
        barcode_anchor = _is_barcode_like(block.text)
        if header_anchor and block.y0 <= top_zone:
            block.group = BlockGroup.HEADER
            continue
        if footer_anchor and block.y1 >= bottom_zone_start:
            block.group = BlockGroup.FOOTER
            continue
        if barcode_anchor and block.y0 <= near_top:
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
            },
        )
    _classify_blocks(blocks, page_width=page_width, page_height=page_height)
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
        },
    )


def _fragmented_heuristic(text: str) -> bool:
    lines = [line for line in text.split("\n") if line.strip() != ""]
    if len(lines) < 20:
        return False
    avg_len = sum(len(line) for line in lines) / len(lines)
    short_line_count = sum(1 for line in lines if len(line) <= 12)
    return avg_len < 18 and short_line_count / len(lines) > 0.6


def extract_ordered_page_text(pdf_path: Path, page_index: int) -> OrderedPageText:
    try:
        import fitz

        with fitz.open(pdf_path) as doc:
            page = doc.load_page(page_index)
            page_dict = page.get_text("dict")
            blocks = build_text_blocks_from_page_dict(page_dict)
            ordered_text, metadata = order_text_blocks_with_metadata(
                blocks,
                page_width=float(page.rect.width),
                page_height=float(page.rect.height),
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
    )
