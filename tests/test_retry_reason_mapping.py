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
