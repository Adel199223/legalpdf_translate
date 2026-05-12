from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def test_translation_result_presentation_builds_translation_result_cards() -> None:
    script = r"""
const presentation = await import(__TRANSLATION_RESULT_PRESENTATION_MODULE_URL__);

const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";

const preparedLaunch = {
  source_filename: `notice ${malicious}.pdf`,
  target_lang: "FR",
  start_page: 2,
  image_mode: "always",
  ocr_mode: "auto",
  ocr_engine: "cloud",
  resume: false,
  keep_intermediates: false,
  gmail_batch_context: {
    selected_target_lang: "AR",
    selected_attachment_filename: `fallback ${malicious}.pdf`,
    selected_start_page: 3,
  },
};

const authFailureJob = {
  job_kind: "translate",
  status: "failed",
  status_text: `Auth failed ${malicious}`,
  result: {
    error: "authentication_failure",
    failure_context: {
      credential_source: { kind: "env", name: `OPENAI_${malicious}` },
      scope: "preflight",
      status_code: 401,
      exception_class: `AuthError ${malicious}`,
      message: `Bad key ${malicious}`,
    },
  },
};

const recoveryJob = {
  job_kind: "translate",
  status: "failed",
  status_text: '{"job_id":"unsafe"}',
  config: {
    target_lang: "AR",
    ocr_mode: "off",
    image_mode: "off",
  },
  result: {
    error: "compliance_failure",
    failed_page: 3,
    review_queue_count: 1,
    failure_context: {
      retry_reason: "ar_token_violation",
      validator_defect_reason: `Token mismatch ${malicious}`,
      page_number: 4,
      ar_violation_samples: [`342 ${malicious}`],
      ar_token_details: {
        missing_token_samples: [`342 ${malicious}`],
        unexpected_token_samples: [`Beja ${malicious}`, "Andreina Mateus"],
      },
    },
    advisor_recommendation: {
      recommended_ocr_mode: "auto",
      recommended_image_mode: "always",
      recommendation_reasons: ["ocr_helpful"],
      confidence: 0.82,
    },
  },
};

const cases = {
  nullSafe: presentation.buildTranslationResultCardPresentation(),
  empty: presentation.buildTranslationResultCardPresentation({
    job: null,
    preparedLaunch: null,
    hasReadySource: false,
    defaultTarget: "EN",
  }),
  prepared: presentation.buildTranslationResultCardPresentation({
    job: null,
    preparedLaunch,
    hasReadySource: false,
    defaultTarget: "EN",
  }),
  sourceReady: presentation.buildTranslationResultCardPresentation({
    job: null,
    preparedLaunch: null,
    hasReadySource: true,
    defaultTarget: "EN",
  }),
  analyze: presentation.buildTranslationResultCardPresentation({
    job: {
      job_kind: "analyze",
      status: "completed",
      status_text: `Analysis done ${malicious}`,
      result: {
        analysis: {
          selected_pages_count: 5,
          pages_would_attach_images: 2,
          advisor_recommendation: {
            recommended_ocr_mode: "auto",
            recommended_image_mode: "always",
          },
        },
      },
    },
  }),
  rebuild: presentation.buildTranslationResultCardPresentation({
    job: {
      job_kind: "rebuild",
      status: "completed",
      status_text: "",
      result: {
        rebuild: {
          docx_path: `C:/cases/rebuilt ${malicious}.docx`,
        },
      },
    },
  }),
  completedRawStatus: presentation.buildTranslationResultCardPresentation({
    job: {
      job_kind: "translate",
      status: "completed",
      status_text: '{"job_id":"raw","result":{}}',
      result: {
        completed_pages: 7,
        review_queue_count: 2,
        error: `Late warning ${malicious}`,
        metrics: {
          run_id: `run-${malicious}`,
        },
      },
    },
  }),
  authFailure: presentation.buildTranslationResultCardPresentation({
    job: authFailureJob,
  }),
  recovery: presentation.buildTranslationResultCardPresentation({
    job: recoveryJob,
  }),
  cancelledRecovery: presentation.buildTranslationResultCardPresentation({
    job: {
      ...recoveryJob,
      status: "cancelled",
      status_text: `Cancelled ${malicious}`,
      result: {
        ...recoveryJob.result,
        advisor_recommendation: {},
      },
    },
  }),
};

console.log(JSON.stringify({
  exportTypes: {
    card: typeof presentation.buildTranslationResultCardPresentation,
    recovery: typeof presentation.deriveTranslationRecoveryState,
  },
  recoveryState: presentation.deriveTranslationRecoveryState(recoveryJob),
  cases,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__TRANSLATION_RESULT_PRESENTATION_MODULE_URL__": "translation_result_presentation.js"},
        timeout_seconds=20,
    )

    assert results["exportTypes"] == {"card": "function", "recovery": "function"}
    assert results["cases"]["nullSafe"] == {
        "empty": True,
        "emptyText": "Choose a source file to see translation progress and results here.",
    }
    assert results["cases"]["empty"] == {
        "empty": True,
        "emptyText": "Choose a source file to see translation progress and results here.",
    }
    assert results["cases"]["prepared"] == {
        "title": "Prepared Gmail attachment is ready to start.",
        "summaryLines": [
            "Attachment: notice <img src=x onerror=alert(1)><script>bad()</script>.pdf",
            "Current Gmail job target: FR",
            "Default target for new jobs: EN",
            "Start page: 2",
            "Images: always",
            "OCR: auto / cloud",
            "Resume: off",
            "Keep intermediates: off",
        ],
        "footer": "Ready to start. Click Start Translate when you're ready.",
        "label": "ready",
        "tone": "info",
    }
    assert results["cases"]["sourceReady"] == {
        "title": "Source file is ready.",
        "summaryLines": [
            "Confirm the language and output folder, then click Start Translate when you're ready."
        ],
        "label": "ready",
        "tone": "ok",
    }
    assert results["cases"]["analyze"] == {
        "title": "Analysis done <img src=x onerror=alert(1)><script>bad()</script>",
        "summaryLines": [
            "Selected pages: 5",
            "Would attach images: 2",
            "Advisor: OCR auto / Images always",
        ],
        "label": "completed",
        "tone": "ok",
    }
    assert results["cases"]["rebuild"] == {
        "title": "Translation complete.",
        "summaryLines": [
            "DOCX: C:/cases/rebuilt <img src=x onerror=alert(1)><script>bad()</script>.docx"
        ],
        "label": "completed",
        "tone": "ok",
    }
    assert results["cases"]["completedRawStatus"] == {
        "title": "Translation complete.",
        "summaryLines": [
            "Completed pages: 7",
            "Run ID: run-<img src=x onerror=alert(1)><script>bad()</script>",
            "Flagged review pages: 2",
            "Error: Late warning <img src=x onerror=alert(1)><script>bad()</script>",
        ],
        "label": "completed",
        "tone": "ok",
    }
    assert results["cases"]["authFailure"] == {
        "title": "Auth failed <img src=x onerror=alert(1)><script>bad()</script>",
        "summaryLines": [
            "Recovery: open Browser Settings, save a valid translation key, and run Test Translation Auth.",
            "Credential source: env OPENAI_<img src=x onerror=alert(1)><script>bad()</script>",
            "Failure scope: preflight before page processing",
            "Status code: 401",
            "Failure class: AuthError <img src=x onerror=alert(1)><script>bad()</script>",
            "Bad key <img src=x onerror=alert(1)><script>bad()</script>",
        ],
        "label": "failed",
        "tone": "bad",
    }
    assert results["cases"]["recovery"]["title"] == "Translation progress is available."
    assert results["cases"]["recovery"]["label"] == "failed"
    assert results["cases"]["recovery"]["tone"] == "bad"
    assert results["cases"]["recovery"]["summaryLines"] == [
        "Failed page: 3",
        "Validator reason: Token mismatch <img src=x onerror=alert(1)><script>bad()</script>",
        "Retry reason: ar_token_violation",
        "Flagged review pages: 1",
        "Missing protected tokens after retry: 342 <img src=x onerror=alert(1)><script>bad()</script>",
        "Unexpected or altered protected tokens: Beja <img src=x onerror=alert(1)><script>bad()</script>, Andreina Mateus",
        "Recommended rerun settings: OCR auto / Images always. Change the setup, then use Start Translate for a new run.",
        "Resume Translation reruns the same config against the same source.",
        "Change OCR or image settings first, then use Start Translate for a new run.",
        "Rebuild DOCX only assembles completed pages and does not make this Gmail item confirmable.",
    ]
    assert results["cases"]["cancelledRecovery"]["title"] == (
        "Cancelled <img src=x onerror=alert(1)><script>bad()</script>"
    )
    assert results["cases"]["cancelledRecovery"]["tone"] == "warn"
    assert results["recoveryState"]["visible"] is True
    assert results["recoveryState"]["recommendedAction"] == "start_translate_with_advisor"
