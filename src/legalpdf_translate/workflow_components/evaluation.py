"""Delegated output-evaluation and retry-reason logic for the translation workflow."""

from __future__ import annotations

from .contracts import OutputEvaluation
from ..output_normalize import normalize_output_text_with_stats
from ..types import TargetLang
from ..validators import parse_code_block_output, validate_ar, validate_enfr


def evaluate_output(
    raw_output: str,
    lang: TargetLang,
    *,
    expected_ar_tokens: list[str] | None = None,
) -> OutputEvaluation:
    parsed = parse_code_block_output(raw_output)
    if parsed.block_count == 0:
        return OutputEvaluation(
            ok=False,
            normalized_text=None,
            defect_reason='No code block in model output.',
            parser_failed=True,
            validator_failed=False,
            outside_text=False,
            block_count=0,
            ar_autofix_applied_count=0,
            ar_token_details=None,
        )
    if parsed.block_count > 1:
        return OutputEvaluation(
            ok=False,
            normalized_text=None,
            defect_reason='More than one code block in model output.',
            parser_failed=True,
            validator_failed=False,
            outside_text=False,
            block_count=parsed.block_count,
            ar_autofix_applied_count=0,
            ar_token_details=None,
        )
    if parsed.inner_content is None:
        return OutputEvaluation(
            ok=False,
            normalized_text=None,
            defect_reason='Missing inner code block content.',
            parser_failed=True,
            validator_failed=False,
            outside_text=False,
            block_count=1,
            ar_autofix_applied_count=0,
            ar_token_details=None,
        )

    normalized, ar_autofix_applied_count = normalize_output_text_with_stats(
        parsed.inner_content,
        lang=lang,
        expected_ar_tokens=expected_ar_tokens,
    )
    if lang in (TargetLang.EN, TargetLang.FR):
        validation = validate_enfr(normalized, lang=lang)
    else:
        validation = validate_ar(normalized, expected_tokens=expected_ar_tokens)
    if not validation.ok:
        return OutputEvaluation(
            ok=False,
            normalized_text=normalized,
            defect_reason=validation.reason,
            parser_failed=False,
            validator_failed=True,
            outside_text=False,
            block_count=1,
            ar_autofix_applied_count=int(ar_autofix_applied_count),
            ar_token_details=validation.details,
        )
    if parsed.outside_has_non_whitespace:
        return OutputEvaluation(
            ok=False,
            normalized_text=normalized,
            defect_reason='Non-whitespace text found outside code block.',
            parser_failed=False,
            validator_failed=False,
            outside_text=True,
            block_count=1,
            ar_autofix_applied_count=int(ar_autofix_applied_count),
            ar_token_details=validation.details,
        )
    return OutputEvaluation(
        ok=True,
        normalized_text=normalized,
        defect_reason=None,
        parser_failed=False,
        validator_failed=False,
        outside_text=False,
        block_count=1,
        ar_autofix_applied_count=int(ar_autofix_applied_count),
        ar_token_details=validation.details,
    )


def retry_reason_from_evaluation(
    evaluation: OutputEvaluation,
    *,
    lang: TargetLang,
    fallback_reason: str | None,
) -> str:
    if evaluation.outside_text:
        return 'outside_text'
    if evaluation.block_count == 0:
        return 'no_code_block'
    if evaluation.block_count > 1:
        return 'multi_code_block'
    reason = (fallback_reason or '').strip().lower()
    if 'blank line' in reason:
        return 'blank_lines'
    if 'portuguese' in reason and 'leak' in reason:
        return 'pt_language_leak'
    if lang == TargetLang.AR:
        if 'latin' in reason or 'digit' in reason or 'token' in reason or 'wrapped' in reason:
            return 'ar_token_violation'
    return 'other'
