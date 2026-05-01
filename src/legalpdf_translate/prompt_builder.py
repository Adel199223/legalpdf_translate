"""Prompt assembly helpers for page translation and compliance retry."""

from __future__ import annotations

from typing import Any, Mapping

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


def build_ar_token_retry_prompt(
    prior_output: str,
    expected_tokens: list[str],
    *,
    source_text: str | None = None,
    violation_kind: str | None = None,
    defect_reason: str | None = None,
    token_details: Mapping[str, Any] | None = None,
) -> str:
    tokens = [token for token in expected_tokens if isinstance(token, str) and token != ""]
    token_lines = [f"{index}. [[{token}]]" for index, token in enumerate(tokens, start=1)]
    header = (
        "ARABIC TOKEN CORRECTION ONLY: Re-emit the SAME content as ONE plain-text code block and NOTHING ELSE. "
        "Keep every listed [[...]] token exactly character-for-character. "
        "Do not translate, edit, split, remove, reorder, or add token contents. "
        "Every listed token must appear only inside [[...]]. "
        "If a listed token appears outside [[...]], wrap it instead of rewriting it. "
        "No Latin letters or digits may appear outside protected tokens. "
        "All non-token text must be Arabic."
    )
    defect_hint = ""
    if violation_kind == "latin_or_digits_outside_wrapped_tokens":
        defect_hint = (
            "CURRENT DEFECT TO FIX: Latin letters or digits still appear outside [[...]] tokens. "
            "Wrap every verbatim identifier span in [[...]] and keep the remaining text Arabic."
        )

    mismatch_lines: list[str] = []
    if defect_reason or violation_kind or isinstance(token_details, Mapping):
        mismatch_lines.extend(
            [
                "<<<BEGIN TOKEN MISMATCH SUMMARY>>>",
                f"Validator reason: {str(defect_reason or '').strip() or 'Arabic token mismatch.'}",
            ]
        )
        if violation_kind:
            mismatch_lines.append(f"Violation kind: {violation_kind}")
        if isinstance(token_details, Mapping):
            missing_count = int(token_details.get("missing_count", 0) or 0)
            altered_count = int(token_details.get("altered_count", 0) or 0)
            unexpected_count = int(token_details.get("unexpected_count", 0) or 0)
            mismatch_lines.extend(
                [
                    f"Missing protected tokens: {missing_count}",
                    f"Altered protected tokens: {altered_count}",
                    f"Unexpected protected tokens: {unexpected_count}",
                ]
            )
            missing_samples = [
                str(item).strip()
                for item in token_details.get("missing_token_samples", [])
                if str(item or "").strip() != ""
            ] if isinstance(token_details.get("missing_token_samples"), list) else []
            unexpected_samples = [
                str(item).strip()
                for item in token_details.get("unexpected_token_samples", [])
                if str(item or "").strip() != ""
            ] if isinstance(token_details.get("unexpected_token_samples"), list) else []
            if missing_samples:
                mismatch_lines.append("Missing token samples:")
                mismatch_lines.extend(f"- [[{item}]]" for item in missing_samples[:3])
            if unexpected_samples:
                mismatch_lines.append("Unexpected or altered token samples:")
                mismatch_lines.extend(f"- [[{item}]]" for item in unexpected_samples[:3])
        mismatch_lines.append("<<<END TOKEN MISMATCH SUMMARY>>>")

    lines = [
        header,
        "<<<BEGIN LOCKED TOKENS>>>",
        *token_lines,
        "<<<END LOCKED TOKENS>>>",
    ]
    if defect_hint:
        lines.insert(1, defect_hint)
    if mismatch_lines:
        lines.extend(mismatch_lines)
    if source_text:
        lines.extend(
            [
                "<<<BEGIN SOURCE PAGE>>>",
                source_text,
                "<<<END SOURCE PAGE>>>",
            ]
        )
    lines.extend(
        [
            "<<<BEGIN PRIOR OUTPUT>>>",
            prior_output,
            "<<<END PRIOR OUTPUT>>>",
        ]
    )
    return "\n".join(lines)


def build_language_retry_prompt(lang: TargetLang, prior_output: str) -> str:
    if lang == TargetLang.EN:
        language_hint = " Re-emit in legal English only; remove Portuguese residual terms except verbatim-allowed fields."
    elif lang == TargetLang.FR:
        language_hint = " Re-emit in legal French only; remove Portuguese residual terms except verbatim-allowed fields."
    else:
        language_hint = (
            " Re-emit in Arabic only; Portuguese is allowed only inside verbatim protected [[...]] tokens. "
            "Outside protected tokens, all remaining text must be Arabic."
        )
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
