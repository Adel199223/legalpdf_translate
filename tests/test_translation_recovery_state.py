from __future__ import annotations

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
        "Rebuild DOCX only assembles completed pages and does not make this Gmail item confirmable.",
    ]
    assert failed["advisorMessage"] == (
        "Recommended rerun settings: OCR auto / Images always. "
        "Change the setup, then use Start Translate for a new run."
    )
    assert results["rebuild"]["visible"] is False
    assert results["running"]["visible"] is False
