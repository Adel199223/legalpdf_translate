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
