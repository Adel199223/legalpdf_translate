from __future__ import annotations

import json

import pytest

from .browser_esm_probe import run_browser_esm_json_probe


def _run_translation_recovery_probe() -> dict[str, object]:
    script = """
const translationModule = await import(__TRANSLATION_MODULE_URL__);

const failedJob = {{
  job_kind: "translate",
  status: "failed",
  status_text: "Translation failed (compliance_failure)",
  config: {{
    target_lang: "AR",
    ocr_mode: "off",
    image_mode: "off",
  }},
  result: {{
    error: "compliance_failure",
    failed_page: 3,
    review_queue_count: 1,
    failure_context: {{
      retry_reason: "ar_token_violation",
      validator_defect_reason: "Expected locked token mismatch.",
      page_number: 3,
      ar_violation_samples: ["342", "Beja"],
      ar_token_details: {{
        missing_token_samples: ["342"],
        unexpected_token_samples: ["Beja", "Andreina Mateus"],
      }},
    }},
    advisor_recommendation: {{
      recommended_ocr_mode: "auto",
      recommended_image_mode: "always",
      recommendation_reasons: ["ocr_helpful", "image_helpful"],
      confidence: 0.82,
    }},
  }},
}};

const rebuildJob = {{
  job_kind: "rebuild",
  status: "completed",
  result: {{}},
}};

const runningJob = {{
  job_kind: "translate",
  status: "running",
  result: {{}},
}};

const results = {{
  failed: translationModule.deriveTranslationRecoveryState(failedJob),
  rebuild: translationModule.deriveTranslationRecoveryState(rebuildJob),
  running: translationModule.deriveTranslationRecoveryState(runningJob),
}};

console.log(JSON.stringify(results));
""".replace("{{", "{").replace("}}", "}")
    return run_browser_esm_json_probe(
        script,
        {"__TRANSLATION_MODULE_URL__": "translation.js"},
        timeout_seconds=20,
    )


def test_translation_recovery_state_surfaces_failed_arabic_guidance() -> None:
    results = _run_translation_recovery_probe()

    failed = results["failed"]
    assert failed["visible"] is True
    assert failed["failureReason"] == "Expected locked token mismatch."
    assert failed["failurePage"] == 3
    assert failed["recommendedAction"] == "start_translate_with_advisor"
    assert "Failed page: 3" in failed["summaryLines"]
    assert "Validator reason: Expected locked token mismatch." in failed["summaryLines"]
    assert "Retry reason: ar_token_violation" in failed["summaryLines"]
    assert "Flagged review pages: 1" in failed["summaryLines"]
    assert "Missing protected tokens after retry: 342" in failed["summaryLines"]
    assert "Unexpected or altered protected tokens: Beja, Andreina Mateus" in failed["summaryLines"]
    assert failed["guidanceLines"] == [
        "Resume Translation reruns the same config against the same source.",
        "Change OCR or image settings first, then use Start Translate for a new run.",
        "Rebuild DOCX only assembles completed pages and does not complete a failed translation.",
    ]
    assert failed["advisorMessage"] == (
        "Recommended rerun settings: OCR auto / Images always. "
        "Change the setup, then use Start Translate for a new run."
    )
    assert results["rebuild"]["visible"] is False
    assert results["running"]["visible"] is False


@pytest.mark.parametrize(
    ("failure", "progress", "image_recommendation_expected"),
    [
        ({"page_number": 1, "request_type": "image_backed"}, {"real_page": 1, "image_used": True}, False),
        ({"page_number": 1, "request_type": "image_backed"}, {}, False),
        ({"page_number": 1}, {"real_page": 1, "image_used": True}, False),
        ({"page_number": 1, "request_type": "text_only"}, {"real_page": 1, "image_used": False}, True),
        ({"page_number": 1}, {}, True),
        ({"request_type": "image_backed"}, {}, True),
        ({"page_number": 2, "request_type": "image_backed"}, {"real_page": 2, "image_used": True}, True),
        ({"page_number": 1, "request_type": "image_backed"}, {"real_page": 1, "image_used": False}, True),
        ({"page_number": 1, "request_type": "text_only"}, {"real_page": 1, "image_used": True}, True),
        ({"page_number": 2, "request_type": "image_backed"}, {"real_page": 1, "image_used": True}, True),
        ({"page_number": 1}, {"real_page": 1, "image_used": "true"}, True),
        ({"page_number": 1, "request_type": "image_backed"}, {"real_page": 2, "image_used": False}, False),
    ],
)
def test_image_rerun_hint_uses_actual_failed_page_evidence(
    failure: dict[str, object], progress: dict[str, object], image_recommendation_expected: bool,
) -> None:
    script = """
const translation = await import(__TRANSLATION_MODULE_URL__);
const presentation = await import(__PRESENTATION_MODULE_URL__);
const job = {
  job_kind: "translate", status: "failed",
  config: { target_lang: "AR", ocr_mode: "auto", image_mode: "auto" },
  progress: __PROGRESS__,
  result: {
    failed_page: 1, error: "compliance_failure", review_queue_count: 1,
    failure_context: {
      retry_reason: "ar_token_violation", validator_defect_reason: "Fictional token mismatch",
      ar_token_details: { missing_token_samples: ["TOKEN_A"] }, ...__FAILURE__,
    },
    advisor_recommendation: { recommended_ocr_mode: "off", recommended_image_mode: "always" },
  },
};
console.log(JSON.stringify({
  recovery: translation.deriveTranslationRecoveryState(job),
  card: presentation.buildTranslationResultCardPresentation({ job }),
  ocr: translation.deriveTranslationRecoveryState({
    ...job, config: { ...job.config, ocr_mode: "off" },
    result: { ...job.result, advisor_recommendation: { ...job.result.advisor_recommendation, recommended_ocr_mode: "auto" } },
  }),
}));
""".replace("__PROGRESS__", json.dumps(progress)).replace("__FAILURE__", json.dumps(failure))
    results = run_browser_esm_json_probe(
        script,
        {"__TRANSLATION_MODULE_URL__": "translation.js", "__PRESENTATION_MODULE_URL__": "translation_result_presentation.js"},
        timeout_seconds=20,
    )
    recovery = results["recovery"]
    assert ("Images always" in recovery["advisorMessage"]) is image_recommendation_expected
    assert any("Images always" in line for line in results["card"]["summaryLines"]) is image_recommendation_expected
    assert recovery["visible"] is True
    assert recovery["failurePage"] == 1
    assert "Validator reason: Fictional token mismatch" in recovery["summaryLines"]
    assert "Missing protected tokens after retry: TOKEN_A" in recovery["summaryLines"]
    assert any("already used an image" in line for line in recovery["guidanceLines"]) is not image_recommendation_expected
    assert "OCR auto" in results["ocr"]["advisorMessage"]
    assert ("Images always" in results["ocr"]["advisorMessage"]) is image_recommendation_expected
