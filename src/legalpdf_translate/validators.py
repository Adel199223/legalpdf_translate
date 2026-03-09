"""Code-block parser and language-specific validators."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .output_normalize import LRI, PDI
from .types import TargetLang


CODE_BLOCK_RE = re.compile(r"```(?:[^\n`]*)\n?(.*?)```", re.DOTALL)
AR_VALID_TOKEN_RE = re.compile(rf"{re.escape(LRI)}\[\[.*?\]\]{re.escape(PDI)}", re.DOTALL)
PT_MONTH_PATTERN = r"(?:janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)"
PT_MONTH_DATE_LEAK_RE = re.compile(
    rf"(?<!\w)(?:\d{{1,2}}(?:\.\s*[ºo])?)\s+(?:de\s+)?{PT_MONTH_PATTERN}(?:(?:\s+de)?\s+\d{{4}})?(?!\w)",
    re.IGNORECASE,
)
ADDRESS_CONTEXT_HINT_RE = re.compile(
    r"\b(?:rua|avenida|av\.?|travessa|largo|praça|praca|estrada|alameda|bairro)\b",
    re.IGNORECASE,
)
ADDRESS_ONLY_LINE_RE = re.compile(
    r"^\s*(?:rua|avenida|av\.?|travessa|largo|praça|praca|estrada|alameda|bairro)\b",
    re.IGNORECASE,
)
EMAIL_OR_URL_RE = re.compile(
    r"(?:\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|https?://\S+|www\.\S+)",
    re.IGNORECASE,
)
PT_INSTITUTION_LEAK_RE = re.compile(
    r"\b(?:tribunal judicial|ju[íi]zo|procuradoria|comarca|minist[eé]rio p[úu]blico|inqu[eé]rito(?:s)?)\b",
    re.IGNORECASE,
)
PT_LEGAL_LEAK_RE = re.compile(
    r"\b(?:c\.\s*p\.\s*penal|c[oó]digo de processo penal|arguido|of[ií]cio(?:\s+de\s+notifica[cç][aã]o)?)\b",
    re.IGNORECASE,
)
PT_MIXED_ADDRESS_PREP_LEAK_RE = re.compile(
    r"\b(?:na|no)\s+(?:rua|avenida|av\.?|travessa|largo|praça|praca|estrada|alameda|bairro)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class CodeBlockParseResult:
    block_count: int
    inner_content: str | None
    outside_has_non_whitespace: bool


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    reason: str | None = None
    details: dict[str, Any] | None = None
    kind: str | None = None


def parse_code_block_output(raw_output: str) -> CodeBlockParseResult:
    matches = list(CODE_BLOCK_RE.finditer(raw_output))
    if len(matches) != 1:
        return CodeBlockParseResult(
            block_count=len(matches),
            inner_content=None,
            outside_has_non_whitespace=False,
        )
    match = matches[0]
    outside_text = raw_output[: match.start()] + raw_output[match.end() :]
    return CodeBlockParseResult(
        block_count=1,
        inner_content=match.group(1),
        outside_has_non_whitespace=outside_text.strip() != "",
    )


def _count_pt_month_date_leaks(text: str) -> int:
    leak_count = 0
    for line in text.split("\n"):
        if ADDRESS_CONTEXT_HINT_RE.search(line):
            continue
        leak_count += len(list(PT_MONTH_DATE_LEAK_RE.finditer(line)))
    return leak_count


def _sanitize_line_for_leak_checks(line: str) -> str:
    return EMAIL_OR_URL_RE.sub(" ", line)


def _count_pt_language_leaks(text: str) -> dict[str, int]:
    pt_month_leak_count = 0
    pt_legal_leak_count = 0
    pt_institution_leak_count = 0
    exempted_address_hits = 0
    for raw_line in text.split("\n"):
        line = _sanitize_line_for_leak_checks(raw_line)
        if line.strip() == "":
            continue
        has_address_hint = bool(ADDRESS_CONTEXT_HINT_RE.search(line))
        is_address_only = bool(ADDRESS_ONLY_LINE_RE.match(line))
        if has_address_hint:
            exempted_address_hits += 1
        if not has_address_hint:
            pt_month_leak_count += len(list(PT_MONTH_DATE_LEAK_RE.finditer(line)))
        # Address-only lines are intentionally preserved verbatim in EN/FR.
        if is_address_only:
            continue
        pt_institution_leak_count += len(list(PT_INSTITUTION_LEAK_RE.finditer(line)))
        pt_legal_leak_count += len(list(PT_LEGAL_LEAK_RE.finditer(line)))
        pt_legal_leak_count += len(list(PT_MIXED_ADDRESS_PREP_LEAK_RE.finditer(line)))
    return {
        "pt_month_leak_count": int(pt_month_leak_count),
        "pt_legal_leak_count": int(pt_legal_leak_count),
        "pt_institution_leak_count": int(pt_institution_leak_count),
        "exempted_address_hits": int(exempted_address_hits),
    }


def validate_enfr(normalized_text: str, *, lang: TargetLang | None = None) -> ValidationResult:
    if normalized_text.strip() == "":
        return ValidationResult(ok=False, reason="EN/FR output is empty.")
    if any(line.strip() == "" for line in normalized_text.split("\n")):
        return ValidationResult(ok=False, reason="EN/FR output contains blank lines.")
    if lang in (TargetLang.EN, TargetLang.FR):
        leak_counts = _count_pt_language_leaks(normalized_text)
        if leak_counts["pt_month_leak_count"] > 0:
            return ValidationResult(
                ok=False,
                reason="Portuguese month-name date leaked after normalization.",
                details=leak_counts,
            )
        if (leak_counts["pt_legal_leak_count"] + leak_counts["pt_institution_leak_count"]) > 0:
            return ValidationResult(
                ok=False,
                reason="Portuguese legal/institution terms leaked after normalization.",
                details=leak_counts,
            )
    return ValidationResult(ok=True)


def _extract_wrapped_token_contents(text: str) -> list[str]:
    values: list[str] = []
    for match in AR_VALID_TOKEN_RE.finditer(text):
        token = match.group(0)
        if not token.startswith(LRI) or not token.endswith(PDI):
            continue
        inner = token[len(LRI) : len(token) - len(PDI)]
        if not inner.startswith("[[") or not inner.endswith("]]"):
            continue
        values.append(inner[2:-2])
    return values


def _dedupe_samples(items: list[str], *, limit: int = 3) -> list[str]:
    samples: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = str(item or "").strip()
        if cleaned == "" or cleaned in seen:
            continue
        seen.add(cleaned)
        samples.append(cleaned)
        if len(samples) >= limit:
            break
    return samples


def _build_expected_token_details(expected_tokens: list[str], actual_tokens: list[str]) -> dict[str, Any]:
    expected_counts = Counter(expected_tokens)
    actual_counts = Counter(actual_tokens)
    missing_count = sum(
        max(0, expected_counts[token] - actual_counts.get(token, 0))
        for token in expected_counts
    )
    extra_count = sum(
        max(0, actual_counts[token] - expected_counts.get(token, 0))
        for token in actual_counts
    )

    remaining_expected = Counter(expected_tokens)
    unexpected_samples: list[str] = []
    for token in actual_tokens:
        if remaining_expected.get(token, 0) > 0:
            remaining_expected[token] -= 1
            if remaining_expected[token] <= 0:
                del remaining_expected[token]
        else:
            unexpected_samples.append(token)

    missing_samples: list[str] = []
    remaining_actual = Counter(actual_tokens)
    for token in expected_tokens:
        if remaining_actual.get(token, 0) > 0:
            remaining_actual[token] -= 1
            if remaining_actual[token] <= 0:
                del remaining_actual[token]
        else:
            missing_samples.append(token)

    return {
        "expected_total": int(sum(expected_counts.values())),
        "actual_total": int(sum(actual_counts.values())),
        "missing_count": int(missing_count),
        "altered_count": int(min(missing_count, extra_count)),
        "unexpected_count": int(extra_count),
        "missing_token_samples": _dedupe_samples(missing_samples),
        "unexpected_token_samples": _dedupe_samples(unexpected_samples),
    }


def _sample_unwrapped_marker_context(text: str, marker: str, *, limit: int = 3) -> list[str]:
    samples: list[str] = []
    for match in re.finditer(re.escape(marker), text):
        start = max(0, match.start() - 24)
        end = min(len(text), match.end() + 24)
        snippet = text[start:end].replace("\n", " ").strip()
        if snippet:
            samples.append(snippet)
        if len(samples) >= limit:
            break
    return _dedupe_samples(samples, limit=limit)


def _sample_outside_latin_digit_snippets(text: str, *, limit: int = 3) -> list[str]:
    stripped = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", text)
    samples: list[str] = []
    for line in stripped.split("\n"):
        if not re.search(r"[A-Za-z0-9]", line):
            continue
        candidate = " ".join(line.split()).strip()
        if candidate == "":
            continue
        if len(candidate) > 120:
            match = re.search(r"[A-Za-z0-9]", candidate)
            if match is not None:
                start = max(0, match.start() - 24)
                end = min(len(candidate), match.start() + 56)
                candidate = candidate[start:end].strip()
        samples.append(candidate)
        if len(samples) >= limit:
            break
    return _dedupe_samples(samples, limit=limit)


def strip_ar_protected_spans_for_language_detection(text: str) -> str:
    stripped = AR_VALID_TOKEN_RE.sub(" ", text)
    stripped = re.sub(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]", "", stripped)
    stripped = re.sub(r"[ \t]+", " ", stripped)
    stripped = re.sub(r"\n{3,}", "\n\n", stripped)
    return stripped.strip()


def validate_ar(normalized_text: str, expected_tokens: list[str] | None = None) -> ValidationResult:
    if normalized_text.strip() == "":
        return ValidationResult(ok=False, reason="Arabic output is empty.")
    if re.search(rf"(?<!{re.escape(LRI)})\[\[", normalized_text):
        return ValidationResult(
            ok=False,
            reason="Found unwrapped [[ token start.",
            kind="unwrapped_token_marker",
            details={"marker": "[[", "samples": _sample_unwrapped_marker_context(normalized_text, "[[")},
        )
    if re.search(rf"\]\](?!{re.escape(PDI)})", normalized_text):
        return ValidationResult(
            ok=False,
            reason="Found unwrapped ]] token end.",
            kind="unwrapped_token_marker",
            details={"marker": "]]", "samples": _sample_unwrapped_marker_context(normalized_text, "]]")},
        )
    token_details: dict[str, Any] | None = None
    if expected_tokens is not None:
        expected = [token for token in expected_tokens if isinstance(token, str) and token != ""]
        actual_tokens = _extract_wrapped_token_contents(normalized_text)
        token_details = _build_expected_token_details(expected, actual_tokens)
        if int(token_details.get("missing_count", 0) or 0) > 0:
            return ValidationResult(
                ok=False,
                reason="Expected locked token mismatch.",
                kind="expected_token_mismatch",
                details=token_details,
            )
    text_without_tokens = AR_VALID_TOKEN_RE.sub("", normalized_text)
    if re.search(r"[A-Za-z0-9]", text_without_tokens):
        return ValidationResult(
            ok=False,
            reason="Latin letters or digits found outside wrapped tokens.",
            kind="latin_or_digits_outside_wrapped_tokens",
            details={
                "offending_snippets": _sample_outside_latin_digit_snippets(text_without_tokens),
            },
        )
    if token_details is not None and token_details.get("unexpected_count", 0) > 0:
        return ValidationResult(ok=True, details=token_details)
    return ValidationResult(ok=True)
