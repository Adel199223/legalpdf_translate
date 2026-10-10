"""Conservative pre-tokenization helpers for Arabic mode input."""

from __future__ import annotations

import re
import unicodedata
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
POSTAL_TRACKING_CORE_RE = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2}\d{9}[A-Z]{2}(?![A-Za-z0-9])")
CASE_REF_RE = re.compile(
    r"(?<!\w)(?=[A-Za-z0-9./-]{5,})(?=[A-Za-z0-9./-]*\d)(?=[A-Za-z0-9./-]*(?:/|-|\.))[A-Za-z0-9./-]+(?!\w)"
)
STANDALONE_NUMBER_RE = re.compile(r"(?<![\w./-])\d+(?:[.,]\d+)?(?![\w./-])")
# Currency gives an unambiguous numeric boundary even before /unit or a
# sentence-ending dot, where the generic number matcher can backtrack to the
# integer prefix. Protect the complete value without consuming its currency.
CURRENCY_DECIMAL_RE = re.compile(
    r"[€$£¥][^\S\r\n]*(?P<amount>\d+(?:[.,]\d+)+)(?!\d|[.,]\d)"
)

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
PARTY_NAME_LINE_RE = re.compile(
    r"(?im)^[^\S\r\n]*(?:Arguid[oa]|Requerente|Requerid[oa]|Autor(?:a)?|Réu|Ré|Testemunha)"
    r"[^\S\r\n]*:[^\S\r\n]*(?P<value>[^\r\n]+)$"
)
NAME_ANCHOR_RE = re.compile(
    r"(?:Exm[oa]\.?(?:\(a\))?\s+Senhor(?:a|\(a\))?|"
    r"[OA]\s+Técnic[oa]\s+de\s+Justiça[.,]?|Juiz[.,]?|Juíza[.,]?)", re.IGNORECASE
)
STREET_ANCHOR_RE = re.compile(
    r"^(?:Rua|Avenida|Av\.|Largo|Praça|Travessa|Estrada)\s+|"
    r"^Palácio\s+da\s+Justiça\b.*\b(?:Praça|Rua)\s+", re.IGNORECASE
)


def _plausible_latin_name(value: str, *, minimum_words: int = 2) -> bool:
    """Field-bound names only; deliberately rejects institutions and prose."""
    words = value.strip().split()
    excluded = {"ministério", "tribunal", "procuradoria", "estado", "município", "câmara", "direção"}
    particles = {"de", "da", "do", "das", "dos", "e", "van", "von"}
    if not minimum_words <= len(words) <= 8 or words[0].casefold() in excluded:
        return False
    for word in words:
        if word.casefold() in particles:
            continue
        letters = word.replace("-", "").replace("'", "").replace("’", "")
        if not letters or not all((c.isalpha() and "LATIN" in unicodedata.name(c, ""))
                                  or unicodedata.category(c).startswith("M") for c in letters):
            return False
        if not word[0].isupper():
            return False
    return True


def _postal_locality_fragment(value: str) -> bool:
    """A short capitalized locality inside an already anchored postal block."""
    words = value.split()
    if not 1 <= len(words) <= 5:
        return False
    # Reuse the Latin spelling constraints without relaxing personal names.
    return _plausible_latin_name(value, minimum_words=1)


def _anchored_literal_spans(segment: str) -> list[_Span]:
    spans = []
    for match in PARTY_NAME_LINE_RE.finditer(segment):
        span = _trimmed_group_span(match, "value", segment)
        if span is not None and _plausible_latin_name(segment[span.start:span.end]):
            spans.append(span)
    lines = []
    offset = 0
    for raw in segment.splitlines(keepends=True):
        value = raw.strip()
        start = offset + len(raw) - len(raw.lstrip())
        lines.append((value, start, start + len(value)))
        offset += len(raw)
    for index, (value, _, _) in enumerate(lines):
        if NAME_ANCHOR_RE.fullmatch(value) and index + 1 < len(lines):
            name, start, end = lines[index + 1]
            if _plausible_latin_name(name):
                spans.append(_Span(start, end))
        if not STREET_ANCHOR_RE.search(value):
            continue
        block = []
        for address, start, end in lines[index:index + 4]:
            if not address or ":" in address or re.search(r"[!?;]", address):
                break
            # No unanchored intervening body paragraph: intermediate lines must
            # be short postal fragments, not sentence-like prose.
            if len(address) > 140 or (block and not POSTAL_CODE_RE.search(address)
                                      and not _postal_locality_fragment(address)):
                break
            block.append(_Span(start, end))
            if POSTAL_CODE_RE.search(address):
                spans.extend(block)
                break
    return spans
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
    spans: list[_Span] = _anchored_literal_spans(segment)
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
    currency_spans = [_Span(match.start("amount"), match.end("amount"))
                      for match in CURRENCY_DECIMAL_RE.finditer(segment)]
    spans.extend(currency_spans)
    for regex in (
        EMAIL_RE,
        URL_RE,
        IBAN_RE,
        POSTAL_CODE_RE,
        BARCODE_RE,
        POSTAL_TRACKING_CORE_RE,
        LONG_TRACK_RE,
        CASE_REF_RE,
        PORTUGUESE_MONTH_DATE_RE,
        STANDALONE_NUMBER_RE,
    ):
        for match in regex.finditer(segment):
            # A dot-decimal followed by /unit is a monetary value, not a case
            # identifier whose token should also consume the unit/punctuation.
            if regex is BARCODE_RE and POSTAL_TRACKING_CORE_RE.fullmatch(match.group(0)[2:-2]):
                continue
            if regex is CASE_REF_RE and any(match.start() == span.start for span in currency_spans):
                continue
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
        if (span.start > 0 and segment[span.start - 1] == "[") or (span.end < len(segment) and segment[span.end] == "]"):
            result.append(f"{LRI}[[{token}]]{PDI}")
        else:
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
