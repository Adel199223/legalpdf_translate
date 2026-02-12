"""Prompt assembly helpers for page translation and compliance retry."""

from __future__ import annotations

from .types import TargetLang


def build_page_prompt(
    lang: TargetLang,
    page_number: int,
    total_pages: int,
    source_text: str,
    context_text: str | None = None,
) -> str:
    lines: list[str] = []
    if lang == TargetLang.EN:
        lines.append("EN")
    elif lang == TargetLang.FR:
        lines.append("FR")

    lines.append(f"<<<PAGE {page_number} OF {total_pages}>>>")
    if context_text:
        lines.append("<<<BEGIN CONTEXT>>>")
        lines.append(context_text)
        lines.append("<<<END CONTEXT>>>")
    lines.append("<<<BEGIN SOURCE>>>")
    lines.append(source_text)
    lines.append("<<<END SOURCE>>>")
    return "\n".join(lines)


def build_retry_prompt(lang: TargetLang, prior_output: str) -> str:
    _ = lang
    header = (
        "COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, "
        "as ONE plain-text code block and NOTHING ELSE."
    )
    return "\n".join(
        [
            header,
            "<<<BEGIN PRIOR OUTPUT>>>",
            prior_output,
            "<<<END PRIOR OUTPUT>>>",
        ]
    )
