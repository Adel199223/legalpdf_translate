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
    if lang in (TargetLang.EN, TargetLang.FR):
        header = (
            "COMPLIANCE FIX ONLY: Re-output the SAME translation content as below, without "
            "adding/removing any text, strictly as ONE plain-text code block and NOTHING ELSE. "
            "Do not insert blank lines. Content to reformat:"
        )
    else:
        header = (
            "COMPLIANCE FIX ONLY: Re-output the SAME Arabic translation content as below, "
            "without adding/removing any text, strictly as ONE plain-text code block and NOTHING "
            "ELSE. Do not insert blank lines. Ensure every Latin-script string and every "
            "number/identifier is inside [[...]] AND each token is wrapped as \u2066[[...]]\u2069. "
            "Do not reorder tokens except the list-marker rule. Content to reformat:"
        )
    return "\n".join(
        [
            header,
            "<<<BEGIN PRIOR OUTPUT>>>",
            prior_output,
            "<<<END PRIOR OUTPUT>>>",
        ]
    )
