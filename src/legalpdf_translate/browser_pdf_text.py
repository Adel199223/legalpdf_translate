"""Bounded PDF.js text evidence for browser-rendered PDF pages.

Coordinates are in the PDF.js scale-one, rotation-zero, top-left viewport.
They are ordering hints, not image-aligned or independently verified source
geometry or OCR evidence.
"""

from __future__ import annotations

import math
from typing import Any

from .pdf_text_order import OrderedPageText, TextBlock, order_text_blocks_with_metadata, _fragmented_heuristic

MAX_ITEMS = 20_000
MAX_ITEM_CHARS = 8_192
MAX_PAGE_CHARS = 200_000


def _number(value: Any, *, minimum: float, maximum: float, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f"Browser PDF text {label} must be a finite bounded number.")
    return float(value)


def validate_browser_page_text(value: Any, *, page_number: int) -> dict[str, Any]:
    if (type(page_number) is not int or type(value) is not dict
            or type(value.get("version")) is not int or value["version"] != 1
            or type(value.get("page_number")) is not int or value["page_number"] != page_number):
        raise ValueError("Browser PDF text page identity is invalid.")
    width = _number(value.get("page_width"), minimum=1, maximum=20_000, label="page width")
    height = _number(value.get("page_height"), minimum=1, maximum=20_000, label="page height")
    items = value.get("items")
    if type(items) is not list or len(items) > MAX_ITEMS:
        raise ValueError("Browser PDF text item count is invalid.")
    total_chars = 0
    normalized = []
    for item in items:
        if type(item) is not dict or type(item.get("text")) is not str:
            raise ValueError("Browser PDF text item is invalid.")
        content = item["text"]
        total_chars += len(content)
        if len(content) > MAX_ITEM_CHARS or total_chars > MAX_PAGE_CHARS or "\x00" in content:
            raise ValueError("Browser PDF text page exceeds bounded text limits.")
        direction = item.get("dir")
        if direction not in {"ltr", "rtl", "ttb"} or type(item.get("has_eol")) is not bool:
            raise ValueError("Browser PDF text item direction or line ending is invalid.")
        normalized.append({"text": content,
            "x": _number(item.get("x"), minimum=-20_000, maximum=20_000, label="x"),
            "y": _number(item.get("y"), minimum=-20_000, maximum=20_000, label="y"),
            "width": _number(item.get("width"), minimum=0, maximum=20_000, label="width"),
            "height": _number(item.get("height"), minimum=0, maximum=20_000, label="height"),
            "dir": direction, "has_eol": item["has_eol"]})
    return {"version": 1, "page_number": page_number, "page_width": width,
            "page_height": height, "items": normalized}


def _join_fragments(items: list[dict[str, Any]], *, direction: str) -> str:
    ordered = sorted(items, key=lambda item: item["x"], reverse=direction == "rtl")
    pieces: list[str] = []
    previous = None
    for item in ordered:
        text = item["text"]
        if not text:
            continue
        if previous is not None and pieces and not pieces[-1][-1:].isspace() and not text[:1].isspace():
            gap = ((item["x"] - (previous["x"] + previous["width"])) if direction != "rtl"
                   else (previous["x"] - (item["x"] + item["width"])))
            if gap > max(1.0, min(item["height"], previous["height"]) * 0.18):
                pieces.append(" ")
        pieces.append(text)
        previous = item
    return "".join(pieces)


def ordered_browser_page_text(value: dict[str, Any], *, preserve_structure: bool = False) -> OrderedPageText:
    evidence = validate_browser_page_text(value, page_number=value.get("page_number"))
    width, height = evidence["page_width"], evidence["page_height"]
    rows: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for item in evidence["items"]:
        if current and abs(item["y"] - current[0]["y"]) > max(2.0, min(item["height"], current[0]["height"]) * 0.45):
            rows.append(current)
            current = []
        current.append(item)
        if item["has_eol"]:
            rows.append(current)
            current = []
    if current:
        rows.append(current)

    blocks: list[TextBlock] = []
    for row in rows:
        text_items = [item for item in row if item["text"]]
        if not text_items:
            continue
        sorted_x = sorted(text_items, key=lambda item: item["x"])
        segments: list[list[dict[str, Any]]] = []
        segment: list[dict[str, Any]] = []
        prior = None
        for item in sorted_x:
            if prior is not None and item["x"] - (prior["x"] + prior["width"]) > width * 0.08:
                segments.append(segment)
                segment = []
            segment.append(item)
            prior = item
        if segment:
            segments.append(segment)
        for segment in segments:
            direction = "rtl" if sum(item["dir"] == "rtl" for item in segment) > len(segment) / 2 else "ltr"
            text = _join_fragments(segment, direction=direction)
            if not text.strip():
                continue
            blocks.append(TextBlock(x0=min(item["x"] for item in segment),
                y0=min(item["y"] for item in segment),
                x1=max(item["x"] + item["width"] for item in segment),
                y1=max(item["y"] + item["height"] for item in segment), text=text))

    text, metadata = order_text_blocks_with_metadata(blocks, page_width=width,
        page_height=height, preserve_structure=preserve_structure)
    return OrderedPageText(text=text, extraction_failed=not bool(text.strip()),
        newline_to_char_ratio=text.count("\n") / max(len(text), 1),
        fragmented=_fragmented_heuristic(text), block_count=metadata["block_count"],
        header_blocks_count=metadata["header_blocks_count"],
        footer_blocks_count=metadata["footer_blocks_count"],
        barcode_blocks_count=metadata["barcode_blocks_count"],
        body_blocks_count=metadata["body_blocks_count"],
        two_column_detected=metadata["two_column_detected"], page_width=width,
        page_height=height, body_blocks=(), all_blocks=(),
        extraction_metadata={"source": "browser_pdfjs_text", "geometry_basis": "pdfjs_unrotated_viewport_unverified"})
