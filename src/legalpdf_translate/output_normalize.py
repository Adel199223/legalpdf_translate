"""Deterministic post-output normalization (no semantic rewriting)."""

from __future__ import annotations

import re

from .types import TargetLang

LRI = "\u2066"
PDI = "\u2069"

TOKEN_RE = re.compile(r"\[\[.*?\]\]", re.DOTALL)


def normalize_output_text(
    text: str,
    *,
    lang: TargetLang,
    strip_trailing_spaces: bool = True,
) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if strip_trailing_spaces:
        lines = [line.rstrip() for line in lines]
    lines = [line for line in lines if line.strip() != ""]
    normalized = "\n".join(lines)

    if lang == TargetLang.AR:
        normalized = wrap_existing_tokens_with_isolates(normalized)
    return normalized


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
