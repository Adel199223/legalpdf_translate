"""Delegated output-evaluation and retry-reason logic for the translation workflow."""

from __future__ import annotations

from typing import Any

from .contracts import OutputEvaluation
from ..glossary import detect_source_lang_for_glossary
from ..output_normalize import normalize_output_text_with_stats
from ..types import TargetLang
from ..validators import (
    parse_code_block_output,
    strip_ar_protected_spans_for_language_detection,
    validate_ar,
    validate_enfr,
)


def _ar_violation_samples(details: dict[str, Any] | None) -> list[str] | None:
    if not isinstance(details, dict):
        return None
    samples: list[str] = []
    for key in ("missing_token_samples", "unexpected_token_samples", "offending_snippets", "samples"):
        value = details.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            text = str(item or "").strip()
            if text != "":
                samples.append(text)
    if not samples:
        return None
    return samples[:3]


def _detect_arabic_language_leakage(normalized_text: str) -> tuple[bool, str]:
    stripped = strip_ar_protected_spans_for_language_detection(normalized_text)
    if stripped == "":
        return True, "AUTO"
    detected = detect_source_lang_for_glossary(stripped)
    if detected in {"AUTO", "AR"}:
        return True, detected
    return detected != "PT", detected


def evaluate_output(
    raw_output: str,
    lang: TargetLang,
    *,
    expected_ar_tokens: list[str] | None = None,
    ar_source_text: str | None = None,
    primary_normalized_text: str | None = None,
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
            ar_violation_kind=None,
            ar_violation_samples=None,
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
            ar_violation_kind=None,
            ar_violation_samples=None,
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
            ar_violation_kind=None,
            ar_violation_samples=None,
        )

    normalized, ar_autofix_applied_count = normalize_output_text_with_stats(
        parsed.inner_content,
        lang=lang,
        expected_ar_tokens=expected_ar_tokens,
    )
    if lang == TargetLang.AR:
        from ..output_normalize import regroup_source_bound_ar_numeric_tokens
        normalized, regroup_count = regroup_source_bound_ar_numeric_tokens(normalized, source_text=ar_source_text, expected_tokens=expected_ar_tokens)
        ar_autofix_applied_count += regroup_count
    if lang in (TargetLang.EN, TargetLang.FR):
        validation = validate_enfr(normalized, lang=lang)
    else:
        validation = validate_ar(normalized, expected_tokens=expected_ar_tokens)
    token_details = validation.details
    if lang == TargetLang.AR and primary_normalized_text is not None:
        from ..ar_literal_fidelity import correction_preserves_additional_literals
        if not correction_preserves_additional_literals(primary_normalized_text, normalized, expected_ar_tokens, ar_source_text):
            return OutputEvaluation(ok=False, normalized_text=normalized, defect_reason="Correction lost an additional primary literal.", parser_failed=False, validator_failed=True, outside_text=False, block_count=1, ar_autofix_applied_count=int(ar_autofix_applied_count), ar_token_details=None, ar_violation_kind="correction_literal_fidelity_loss", ar_violation_samples=None)
        from ..ar_literal_fidelity import _address_correction_exemptions
        exemptions = _address_correction_exemptions(primary_normalized_text, normalized, expected_ar_tokens, ar_source_text)
        if exemptions:
            import re
            token_details = dict(token_details or {})
            token_details["source_bound_address_replacements"] = [
                {"primary_literal": old, "required_literal": next(value for value in expected_ar_tokens or [] if re.sub(r"[0-9]+", "#", value) == re.sub(r"[0-9]+", "#", old))}
                for old in sorted(exemptions)
            ]
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
            ar_token_details=token_details,
            ar_violation_kind=validation.kind,
            ar_violation_samples=_ar_violation_samples(validation.details),
        )
    if lang == TargetLang.AR:
        language_ok, detected_lang = _detect_arabic_language_leakage(normalized)
        if not language_ok:
            return OutputEvaluation(
                ok=False,
                normalized_text=normalized,
                defect_reason=f"Portuguese language leak detected outside protected tokens (detected={detected_lang}).",
                parser_failed=False,
                validator_failed=True,
                outside_text=False,
                block_count=1,
                ar_autofix_applied_count=int(ar_autofix_applied_count),
                ar_token_details=token_details,
                ar_violation_kind=None,
                ar_violation_samples=None,
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
            ar_token_details=token_details,
            ar_violation_kind=None,
            ar_violation_samples=None,
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
        ar_token_details=token_details,
        ar_violation_kind=None,
        ar_violation_samples=None,
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
        if evaluation.ar_violation_kind in {
            "expected_token_mismatch",
            "unwrapped_token_marker",
            "latin_or_digits_outside_wrapped_tokens",
        }:
            return 'ar_token_violation'
        if 'latin' in reason or 'digit' in reason or 'token' in reason or 'wrapped' in reason:
            return 'ar_token_violation'
    return 'other'
