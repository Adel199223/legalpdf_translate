"""Code-block parser and language-specific validators."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .output_normalize import LRI, PDI


CODE_BLOCK_RE = re.compile(r"```(?:[^\n`]*)\n?(.*?)```", re.DOTALL)
AR_VALID_TOKEN_RE = re.compile(rf"{re.escape(LRI)}\[\[.*?\]\]{re.escape(PDI)}", re.DOTALL)


@dataclass(slots=True)
class CodeBlockParseResult:
    block_count: int
    inner_content: str | None
    outside_has_non_whitespace: bool


@dataclass(slots=True)
class ValidationResult:
    ok: bool
    reason: str | None = None


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


def validate_enfr(normalized_text: str) -> ValidationResult:
    if normalized_text.strip() == "":
        return ValidationResult(ok=False, reason="EN/FR output is empty.")
    if any(line.strip() == "" for line in normalized_text.split("\n")):
        return ValidationResult(ok=False, reason="EN/FR output contains blank lines.")
    return ValidationResult(ok=True)


def validate_ar(normalized_text: str) -> ValidationResult:
    if normalized_text.strip() == "":
        return ValidationResult(ok=False, reason="Arabic output is empty.")
    if re.search(rf"(?<!{re.escape(LRI)})\[\[", normalized_text):
        return ValidationResult(ok=False, reason="Found unwrapped [[ token start.")
    if re.search(rf"\]\](?!{re.escape(PDI)})", normalized_text):
        return ValidationResult(ok=False, reason="Found unwrapped ]] token end.")
    text_without_tokens = AR_VALID_TOKEN_RE.sub("", normalized_text)
    if re.search(r"[A-Za-z0-9]", text_without_tokens):
        return ValidationResult(ok=False, reason="Latin letters or digits found outside wrapped tokens.")
    return ValidationResult(ok=True)
