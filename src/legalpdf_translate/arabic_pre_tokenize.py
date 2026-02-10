"""Conservative pre-tokenization helpers for Arabic mode input."""

from __future__ import annotations

import re
from dataclasses import dataclass


EXISTING_TOKEN_RE = re.compile(r"\[\[.*?\]\]", re.DOTALL)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE)
POSTAL_CODE_RE = re.compile(r"\b\d{4}-\d{3}\b")
BARCODE_RE = re.compile(r"%\*[^\s]*\*%")
LONG_TRACK_RE = re.compile(r"\b\d[\d-]{7,}\b")
CASE_REF_RE = re.compile(
    r"(?<!\w)(?=[A-Za-z0-9./-]{5,})(?=[A-Za-z0-9./-]*\d)(?=[A-Za-z0-9./-]*(?:/|-|\.))[A-Za-z0-9./-]+(?!\w)"
)
STANDALONE_NUMBER_RE = re.compile(r"(?<![\w./-])\d+(?:[.,]\d+)?(?![\w./-])")

PORTUGUESE_MONTH_DATE_RE = re.compile(
    r"\b\d{1,2}\s+(?:de\s+)?(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de)?\s+\d{4}\b",
    re.IGNORECASE,
)

LABEL_VALUE_RE = re.compile(
    r"(?im)\b(?:Telef|Telef\.|Tel\.|Fax|Mail|E-mail|Correio eletr[oó]nico|Processo|Proc\.|Refer[êe]ncia|Ref\.|ref\.ª|Assunto|Data|n[.ºoª]*)\b\s*[:\-]\s*(?P<value>[^\n]+)"
)

IDENTIFIER_VALUE_RE = re.compile(
    r"^(?:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|https?://\S+|\d{4}-\d{3}|(?=[A-Za-z0-9./%-]{3,}$)(?=.*(?:\d|[./%-]))[A-Za-z0-9./%-]+|\d{1,2}\s+(?:de\s+)?(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de)?\s+\d{4})$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _Span:
    start: int
    end: int


def _collect_spans(segment: str) -> list[_Span]:
    spans: list[_Span] = []
    for regex in (
        EMAIL_RE,
        URL_RE,
        POSTAL_CODE_RE,
        BARCODE_RE,
        LONG_TRACK_RE,
        CASE_REF_RE,
        PORTUGUESE_MONTH_DATE_RE,
        STANDALONE_NUMBER_RE,
    ):
        for match in regex.finditer(segment):
            spans.append(_Span(match.start(), match.end()))

    for match in LABEL_VALUE_RE.finditer(segment):
        value = match.group("value")
        if value is None:
            continue
        value_stripped = value.strip()
        if not value_stripped:
            continue
        if IDENTIFIER_VALUE_RE.match(value_stripped):
            value_start = match.start("value") + (len(value) - len(value.lstrip()))
            value_end = value_start + len(value_stripped)
            spans.append(_Span(value_start, value_end))
    return spans


def _merge_spans(spans: list[_Span]) -> list[_Span]:
    if not spans:
        return []
    spans_sorted = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    merged: list[_Span] = []
    for span in spans_sorted:
        if not merged:
            merged.append(span)
            continue
        last = merged[-1]
        if span.start < last.end:
            continue
        merged.append(span)
    return merged


def _wrap_plain_segment(segment: str) -> str:
    spans = _merge_spans(_collect_spans(segment))
    if not spans:
        return segment
    result: list[str] = []
    cursor = 0
    for span in spans:
        result.append(segment[cursor : span.start])
        token = segment[span.start : span.end]
        result.append(f"[[{token}]]")
        cursor = span.end
    result.append(segment[cursor:])
    return "".join(result)


def pretokenize_arabic_source(text: str) -> str:
    """Wrap conservative identifier-like spans in [[...]] without altering layout."""
    if not text:
        return text

    pieces: list[str] = []
    cursor = 0
    for token_match in EXISTING_TOKEN_RE.finditer(text):
        if token_match.start() > cursor:
            pieces.append(_wrap_plain_segment(text[cursor : token_match.start()]))
        pieces.append(token_match.group(0))
        cursor = token_match.end()
    if cursor < len(text):
        pieces.append(_wrap_plain_segment(text[cursor:]))
    return "".join(pieces)
