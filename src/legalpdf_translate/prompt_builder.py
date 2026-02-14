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
    if lang == TargetLang.EN:
        language_hint = " Keep the output strictly in English."
    elif lang == TargetLang.FR:
        language_hint = " Keep the output strictly in French."
    else:
        language_hint = ""
    header = (
        "COMPLIANCE FIX ONLY: Re-emit the SAME content, fix formatting only, "
        "as ONE plain-text code block and NOTHING ELSE."
        f"{language_hint}"
    )
    return "\n".join(
        [
            header,
            "<<<BEGIN PRIOR OUTPUT>>>",
            prior_output,
            "<<<END PRIOR OUTPUT>>>",
        ]
    )


def build_language_retry_prompt(lang: TargetLang, prior_output: str) -> str:
    if lang == TargetLang.EN:
        language_hint = " Re-emit in legal English only; remove Portuguese residual terms except verbatim-allowed fields."
    elif lang == TargetLang.FR:
        language_hint = " Re-emit in legal French only; remove Portuguese residual terms except verbatim-allowed fields."
    else:
        language_hint = " Re-emit in target language only."
    header = (
        "LANGUAGE CORRECTION ONLY: Re-emit the SAME content, fix language compliance only, "
        "as ONE plain-text code block and NOTHING ELSE."
        f"{language_hint}"
    )
    return "\n".join(
        [
            header,
            "<<<BEGIN PRIOR OUTPUT>>>",
            prior_output,
            "<<<END PRIOR OUTPUT>>>",
        ]
    )
