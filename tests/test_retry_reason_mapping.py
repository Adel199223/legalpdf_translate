from __future__ import annotations

from legalpdf_translate.types import TargetLang
from legalpdf_translate.workflow import TranslationWorkflow


def test_retry_reason_outside_text() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "prefix\n```\nvalid text\n```\n"
    evaluation = workflow._evaluate_output(raw, TargetLang.EN)  # type: ignore[attr-defined]
    reason = workflow._retry_reason_from_evaluation(  # type: ignore[attr-defined]
        evaluation,
        lang=TargetLang.EN,
        fallback_reason=evaluation.defect_reason,
    )
    assert evaluation.ok is False
    assert reason == "outside_text"


def test_retry_reason_multi_code_block() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "```\none\n```\n```\ntwo\n```"
    evaluation = workflow._evaluate_output(raw, TargetLang.EN)  # type: ignore[attr-defined]
    reason = workflow._retry_reason_from_evaluation(  # type: ignore[attr-defined]
        evaluation,
        lang=TargetLang.EN,
        fallback_reason=evaluation.defect_reason,
    )
    assert evaluation.ok is False
    assert reason == "multi_code_block"


def test_evaluate_output_enfr_convertible_month_date_passes_after_normalize() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "```\nBeja, 20 de Março às 11:30\n```"
    evaluation = workflow._evaluate_output(raw, TargetLang.FR)  # type: ignore[attr-defined]
    assert evaluation.ok is True
    assert evaluation.normalized_text == "Beja, 20 mars às 11:30"


def test_evaluate_output_enfr_unresolved_month_date_fails_validation() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "```\nBeja, 1.º de Março de 2026\n```"
    evaluation = workflow._evaluate_output(raw, TargetLang.FR)  # type: ignore[attr-defined]
    assert evaluation.ok is False
    assert evaluation.validator_failed is True
    assert evaluation.defect_reason == "Portuguese month-name date leaked after normalization."


def test_retry_reason_pt_language_leak_when_portuguese_legal_term_leaks() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "```\nMinistère public - Procuradoria da República da Comarca de Beja\n```"
    evaluation = workflow._evaluate_output(raw, TargetLang.FR)  # type: ignore[attr-defined]
    reason = workflow._retry_reason_from_evaluation(  # type: ignore[attr-defined]
        evaluation,
        lang=TargetLang.FR,
        fallback_reason=evaluation.defect_reason,
    )
    assert evaluation.ok is False
    assert evaluation.validator_failed is True
    assert evaluation.defect_reason == "Portuguese legal/institution terms leaked after normalization."
    assert reason == "pt_language_leak"


def test_retry_reason_ar_token_violation_when_expected_token_mismatch() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "```\nالاسم: [[Adel Belghaly]]\n```"
    evaluation = workflow._evaluate_output(  # type: ignore[attr-defined]
        raw,
        TargetLang.AR,
        expected_ar_tokens=["Adel Belghali"],
    )
    reason = workflow._retry_reason_from_evaluation(  # type: ignore[attr-defined]
        evaluation,
        lang=TargetLang.AR,
        fallback_reason=evaluation.defect_reason,
    )
    assert evaluation.ok is False
    assert evaluation.validator_failed is True
    assert evaluation.defect_reason == "Expected locked token mismatch."
    assert evaluation.ar_violation_kind == "expected_token_mismatch"
    assert evaluation.ar_violation_samples == ["Adel Belghali", "Adel Belghaly"]
    assert reason == "ar_token_violation"


def test_retry_reason_ar_pt_language_leak_after_token_strip() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "```\nالنص ãõç\n```"
    evaluation = workflow._evaluate_output(raw, TargetLang.AR)  # type: ignore[attr-defined]
    reason = workflow._retry_reason_from_evaluation(  # type: ignore[attr-defined]
        evaluation,
        lang=TargetLang.AR,
        fallback_reason=evaluation.defect_reason,
    )
    assert evaluation.ok is False
    assert evaluation.validator_failed is True
    assert evaluation.defect_reason is not None
    assert "Portuguese" in evaluation.defect_reason
    assert "leak" in evaluation.defect_reason
    assert reason == "pt_language_leak"


def test_ar_violation_kind_for_latin_digits_outside_wrapped_tokens() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "```\nالاسم: Adel Belghali\n```"
    evaluation = workflow._evaluate_output(  # type: ignore[attr-defined]
        raw,
        TargetLang.AR,
        expected_ar_tokens=[],
    )
    reason = workflow._retry_reason_from_evaluation(  # type: ignore[attr-defined]
        evaluation,
        lang=TargetLang.AR,
        fallback_reason=evaluation.defect_reason,
    )
    assert evaluation.ok is False
    assert evaluation.validator_failed is True
    assert evaluation.defect_reason == "Latin letters or digits found outside wrapped tokens."
    assert evaluation.ar_violation_kind == "latin_or_digits_outside_wrapped_tokens"
    assert evaluation.ar_violation_samples == ["الاسم: Adel Belghali"]
    assert reason == "ar_token_violation"


def test_ar_violation_kind_for_unwrapped_marker() -> None:
    workflow = TranslationWorkflow(client=object())
    raw = "```\nالاسم: [[Adel Belghali]\n```"
    evaluation = workflow._evaluate_output(  # type: ignore[attr-defined]
        raw,
        TargetLang.AR,
        expected_ar_tokens=[],
    )
    reason = workflow._retry_reason_from_evaluation(  # type: ignore[attr-defined]
        evaluation,
        lang=TargetLang.AR,
        fallback_reason=evaluation.defect_reason,
    )
    assert evaluation.ok is False
    assert evaluation.validator_failed is True
    assert evaluation.defect_reason == "Found unwrapped [[ token start."
    assert evaluation.ar_violation_kind == "unwrapped_token_marker"
    assert evaluation.ar_violation_samples is not None
    assert reason == "ar_token_violation"
