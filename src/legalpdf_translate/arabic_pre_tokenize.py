"""Conservative pre-tokenization helpers for Arabic mode input."""

from __future__ import annotations

import re
from dataclasses import dataclass

LRI = "\u2066"
PDI = "\u2069"

EXISTING_TOKEN_RE = re.compile(r"\[\[.*?\]\]", re.DOTALL)
TOKEN_CONTENT_RE = re.compile(r"(?<!\[)\[\[(?!\[)(.*?)\]\](?!\])", re.DOTALL)

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
URL_RE = re.compile(r"\bhttps?://[^\s]+", re.IGNORECASE)
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
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

SENSITIVE_NAME_LINE_RE = re.compile(
    r"(?im)^(?P<prefix>\s*(?:Nome|Name)\s*[:\-]\s*)(?P<value>[^\n]+)$",
)
SENSITIVE_ADDRESS_LINE_RE = re.compile(
    r"(?im)^(?P<prefix>\s*(?:Morada|Endere(?:ç|c)o|Address|Domic[ií]lio)\s*[:\-]\s*)(?P<value>[^\n]+)$",
)
SENSITIVE_CASE_LINE_RE = re.compile(
    r"(?im)^(?P<prefix>\s*(?:N[úu]mero\s+de\s+processo|Processo|Proc\.?|Refer[êe]ncia|Ref\.?|Ref\.ª)\s*[:\-]\s*)(?P<value>[^\n]+)$",
)
SENSITIVE_IBAN_LABEL_RE = re.compile(
    r"(?im)\b(?:IBAN)\b\s*[:\-]\s*(?P<value>[^\n]+)",
)
IDENTIFIER_VALUE_RE = re.compile(
    r"^(?:[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|https?://\S+|[A-Z]{2}\d{2}[A-Z0-9]{11,30}|\d{4}-\d{3}|(?=[A-Za-z0-9./%-]{3,}$)(?=.*(?:\d|[./%-]))[A-Za-z0-9./%-]+|\d{1,2}\s+(?:de\s+)?(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de)?\s+\d{4})$",
    re.IGNORECASE,
)


@dataclass(slots=True)
class _Span:
    start: int
    end: int


def _trimmed_group_span(match: re.Match[str], group: str, segment: str) -> _Span | None:
    raw_start = match.start(group)
    raw_end = match.end(group)
    if raw_start < 0 or raw_end <= raw_start:
        return None
    raw_value = segment[raw_start:raw_end]
    trimmed = raw_value.strip()
    if not trimmed:
        return None
    leading = len(raw_value) - len(raw_value.lstrip())
    trailing = len(raw_value) - len(raw_value.rstrip())
    start = raw_start + leading
    end = raw_end - trailing
    if end <= start:
        return None
    return _Span(start, end)


def _collect_full_value_spans(segment: str) -> list[_Span]:
    spans: list[_Span] = []
    for regex in (SENSITIVE_NAME_LINE_RE, SENSITIVE_ADDRESS_LINE_RE, SENSITIVE_CASE_LINE_RE):
        for match in regex.finditer(segment):
            span = _trimmed_group_span(match, "value", segment)
            if span is not None:
                spans.append(span)

    for match in SENSITIVE_IBAN_LABEL_RE.finditer(segment):
        span = _trimmed_group_span(match, "value", segment)
        if span is None:
            continue
        value = segment[span.start : span.end]
        if IDENTIFIER_VALUE_RE.match(value):
            spans.append(span)
    return spans


def _collect_spans(segment: str) -> list[_Span]:
    spans = _collect_full_value_spans(segment)
    for regex in (
        EMAIL_RE,
        URL_RE,
        IBAN_RE,
        POSTAL_CODE_RE,
        BARCODE_RE,
        LONG_TRACK_RE,
        CASE_REF_RE,
        PORTUGUESE_MONTH_DATE_RE,
        STANDALONE_NUMBER_RE,
    ):
        for match in regex.finditer(segment):
            spans.append(_Span(match.start(), match.end()))
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


def is_safe_ar_identifier_token_content(value: str) -> bool:
    normalized = " ".join(value.replace("\xa0", " ").split()).strip()
    if normalized == "":
        return False
    return IDENTIFIER_VALUE_RE.fullmatch(normalized) is not None


def _wrap_plain_segment(segment: str) -> str:
    spans = _merge_spans(_collect_spans(segment))
    if not spans:
        return segment
    result: list[str] = []
    cursor = 0
    for span in spans:
        token = segment[span.start : span.end]
        if span.start > 0 and span.end < len(segment) and segment[span.start - 1] == "[" and segment[span.end] == "]":
            result.append(segment[cursor : span.start - 1])
            result.append(f"[{LRI}[[{token}]]{PDI}]")
            cursor = span.end + 1
            continue
        result.append(segment[cursor : span.start])
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


def extract_locked_tokens(text: str) -> list[str]:
    if not text:
        return []
    tokens: list[str] = []
    for match in TOKEN_CONTENT_RE.finditer(text):
        token = match.group(1)
        if token is None:
            continue
        tokens.append(token)
    return tokens


def is_portuguese_month_date_token(token: str) -> bool:
    """True when token is exactly a Portuguese month-name date (e.g., 10 de fevereiro de 2026)."""
    if not token:
        return False
    normalized = " ".join(token.replace("\xa0", " ").split())
    if not normalized:
        return False
    return PORTUGUESE_MONTH_DATE_RE.fullmatch(normalized) is not None
