"""Deterministic post-output normalization (no semantic rewriting)."""

from __future__ import annotations

import re
from collections import Counter

from .types import TargetLang

LRI = "\u2066"
PDI = "\u2069"

TOKEN_RE = re.compile(r"\[\[.*?\]\]", re.DOTALL)
PT_MONTH_PATTERN = r"(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
PORTUGUESE_MONTH_DATE_PLAIN_RE = re.compile(
    r"(?<!\w)(?P<full>(?P<day>\d{1,2})\s+(?:de\s+)?(?P<month>[A-Za-zÀ-ÖØ-öø-ÿ]+)(?:\s+de)?\s+(?P<year>\d{4}))(?!\w)",
    re.IGNORECASE,
)
PORTUGUESE_MONTH_DATE_TOKEN_RE = re.compile(
    r"\[\[\s*(?P<full>(?P<day>\d{1,2})\s+(?:de\s+)?(?P<month>[A-Za-zÀ-ÖØ-öø-ÿ]+)(?:\s+de)?\s+(?P<year>\d{4}))\s*\]\]",
    re.IGNORECASE,
)
PORTUGUESE_MONTH_DATE_ENFR_RE = re.compile(
    rf"(?<!\w)(?P<full>(?P<day>\d{{1,2}})\s+(?:de\s+)?(?P<month>{PT_MONTH_PATTERN})(?:(?:\s+de)?\s+(?P<year>\d{{4}}))?)(?!\w)",
    re.IGNORECASE,
)
ADDRESS_CONTEXT_HINT_RE = re.compile(
    r"\b(?:rua|avenida|av\.?|travessa|largo|praça|praca|estrada|alameda|bairro)\b",
    re.IGNORECASE,
)
PT_MONTH_TO_AR = {
    "janeiro": "يناير",
    "fevereiro": "فبراير",
    "março": "مارس",
    "marco": "مارس",
    "abril": "أبريل",
    "maio": "مايو",
    "junho": "يونيو",
    "julho": "يوليو",
    "agosto": "أغسطس",
    "setembro": "سبتمبر",
    "outubro": "أكتوبر",
    "novembro": "نوفمبر",
    "dezembro": "ديسمبر",
}
PT_MONTH_TO_FR = {
    "janeiro": "janvier",
    "fevereiro": "février",
    "março": "mars",
    "marco": "mars",
    "abril": "avril",
    "maio": "mai",
    "junho": "juin",
    "julho": "juillet",
    "agosto": "août",
    "setembro": "septembre",
    "outubro": "octobre",
    "novembro": "novembre",
    "dezembro": "décembre",
}
PT_MONTH_TO_EN = {
    "janeiro": "January",
    "fevereiro": "February",
    "março": "March",
    "marco": "March",
    "abril": "April",
    "maio": "May",
    "junho": "June",
    "julho": "July",
    "agosto": "August",
    "setembro": "September",
    "outubro": "October",
    "novembro": "November",
    "dezembro": "December",
}


def normalize_output_text(
    text: str,
    *,
    lang: TargetLang,
    strip_trailing_spaces: bool = True,
    expected_ar_tokens: list[str] | None = None,
) -> str:
    normalized, _ = normalize_output_text_with_stats(
        text,
        lang=lang,
        strip_trailing_spaces=strip_trailing_spaces,
        expected_ar_tokens=expected_ar_tokens,
    )
    return normalized


def normalize_output_text_with_stats(
    text: str,
    *,
    lang: TargetLang,
    strip_trailing_spaces: bool = True,
    expected_ar_tokens: list[str] | None = None,
) -> tuple[str, int]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if strip_trailing_spaces:
        lines = [line.rstrip() for line in lines]
    lines = [line for line in lines if line.strip() != ""]
    normalized = "\n".join(lines)

    autofix_applied_count = 0
    if lang == TargetLang.AR:
        normalized = normalize_ar_portuguese_month_dates(normalized)
        normalized, autofix_applied_count = autofix_expected_ar_tokens(
            normalized,
            expected_tokens=expected_ar_tokens or [],
        )
        normalized = wrap_existing_tokens_with_isolates(normalized)
    elif lang in (TargetLang.EN, TargetLang.FR):
        normalized = normalize_enfr_portuguese_month_dates(normalized, lang=lang)
    return normalized, autofix_applied_count


def _is_boundary_safe(text: str, *, start: int, end: int, token: str) -> bool:
    if not token:
        return False
    if token[0].isalnum() and start > 0 and text[start - 1].isalnum():
        return False
    if token[-1].isalnum() and end < len(text) and text[end].isalnum():
        return False
    return True


def _wrap_literal_token(segment: str, token: str) -> tuple[str, int]:
    if not segment or not token:
        return segment, 0
    cursor = 0
    chunks: list[str] = []
    replaced = 0
    while cursor < len(segment):
        idx = segment.find(token, cursor)
        if idx < 0:
            chunks.append(segment[cursor:])
            break
        end = idx + len(token)
        if not _is_boundary_safe(segment, start=idx, end=end, token=token):
            chunks.append(segment[cursor:end])
            cursor = end
            continue
        chunks.append(segment[cursor:idx])
        chunks.append(f"[[{token}]]")
        replaced += 1
        cursor = end
    return "".join(chunks), replaced


def autofix_expected_ar_tokens(text: str, *, expected_tokens: list[str]) -> tuple[str, int]:
    if not text or not expected_tokens:
        return text, 0

    cleaned_tokens = [token for token in expected_tokens if token and "[[" not in token and "]]" not in token]
    if not cleaned_tokens:
        return text, 0

    unique_tokens = list(Counter(cleaned_tokens).keys())
    unique_tokens.sort(key=len, reverse=True)

    pieces: list[str] = []
    cursor = 0
    applied = 0
    for match in TOKEN_RE.finditer(text):
        if match.start() > cursor:
            outside = text[cursor : match.start()]
            for token in unique_tokens:
                outside, token_applied = _wrap_literal_token(outside, token)
                applied += token_applied
            pieces.append(outside)
        pieces.append(match.group(0))
        cursor = match.end()

    if cursor < len(text):
        outside_tail = text[cursor:]
        for token in unique_tokens:
            outside_tail, token_applied = _wrap_literal_token(outside_tail, token)
            applied += token_applied
        pieces.append(outside_tail)

    return "".join(pieces), applied


def _normalize_month_key(month: str) -> str:
    cleaned = " ".join(month.replace("\xa0", " ").split()).strip().lower()
    if cleaned.endswith("."):
        cleaned = cleaned[:-1].strip()
    return cleaned


def _replace_portuguese_month_date(
    match: re.Match[str],
    *,
    month_map: dict[str, str],
    unknown_fallback: str,
) -> str:
    full = " ".join((match.group("full") or "").replace("\xa0", " ").split()).strip()
    day = (match.group("day") or "").strip()
    month = _normalize_month_key(match.group("month") or "")
    year = (match.group("year") or "").strip()
    if not full:
        return match.group(0)
    translated_month = month_map.get(month)
    if translated_month is None or day == "" or year == "":
        if unknown_fallback == "protected_token":
            # Fallback for uncertain month parsing: preserve as one protected LTR run.
            return f"[[{full}]]"
        return full
    if unknown_fallback == "protected_token":
        return f"[[{day}]] {translated_month} [[{year}]]"
    return f"{day} {translated_month} {year}"


def normalize_ar_portuguese_month_dates(text: str) -> str:
    if not text:
        return text

    converted = PORTUGUESE_MONTH_DATE_TOKEN_RE.sub(
        lambda match: _replace_portuguese_month_date(
            match,
            month_map=PT_MONTH_TO_AR,
            unknown_fallback="protected_token",
        ),
        text,
    )

    pieces: list[str] = []
    cursor = 0
    for token_match in TOKEN_RE.finditer(converted):
        if token_match.start() > cursor:
            outside = converted[cursor : token_match.start()]
            outside = PORTUGUESE_MONTH_DATE_PLAIN_RE.sub(
                lambda match: _replace_portuguese_month_date(
                    match,
                    month_map=PT_MONTH_TO_AR,
                    unknown_fallback="protected_token",
                ),
                outside,
            )
            pieces.append(outside)
        pieces.append(token_match.group(0))
        cursor = token_match.end()
    if cursor < len(converted):
        tail = converted[cursor:]
        tail = PORTUGUESE_MONTH_DATE_PLAIN_RE.sub(
            lambda match: _replace_portuguese_month_date(
                match,
                month_map=PT_MONTH_TO_AR,
                unknown_fallback="protected_token",
            ),
            tail,
        )
        pieces.append(tail)
    return "".join(pieces)


def normalize_enfr_portuguese_month_dates(text: str, *, lang: TargetLang) -> str:
    if not text:
        return text
    month_map = PT_MONTH_TO_FR if lang == TargetLang.FR else PT_MONTH_TO_EN

    def _replace_enfr(match: re.Match[str]) -> str:
        month = _normalize_month_key(match.group("month") or "")
        translated = month_map.get(month)
        if translated is None:
            return match.group("full") or match.group(0)
        day = (match.group("day") or "").strip()
        year = (match.group("year") or "").strip()
        if day == "":
            return match.group("full") or match.group(0)
        if year:
            return f"{day} {translated} {year}"
        return f"{day} {translated}"

    lines = text.split("\n")
    normalized_lines: list[str] = []
    for line in lines:
        if ADDRESS_CONTEXT_HINT_RE.search(line):
            normalized_lines.append(line)
            continue
        normalized_lines.append(PORTUGUESE_MONTH_DATE_ENFR_RE.sub(_replace_enfr, line))
    return "\n".join(normalized_lines)


def wrap_existing_tokens_with_isolates(text: str) -> str:
    """Wrap existing [[...]] with LRI/PDI when missing; never alter inside token."""
    if not text:
        return text
    result: list[str] = []
    cursor = 0
    for match in TOKEN_RE.finditer(text):
        start, end = match.span()
        token = match.group(0)
        has_prefix = start > 0 and text[start - 1] == LRI
        has_suffix = end < len(text) and text[end] == PDI

        copy_until = start - 1 if has_prefix else start
        result.append(text[cursor:copy_until])
        result.append(f"{LRI}{token}{PDI}")
        cursor = end + (1 if has_suffix else 0)
    result.append(text[cursor:])
    return "".join(result)
