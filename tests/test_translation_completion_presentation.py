from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def test_translation_completion_presentation_module_builds_finish_drawer_state() -> None:
    script = r"""
const presentation = await import(__TRANSLATION_COMPLETION_PRESENTATION_MODULE_URL__);

const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";

const cases = {
  idle: presentation.deriveTranslationCompletionPresentation(),
  analyzeCompleted: presentation.deriveTranslationCompletionPresentation({
    job: {
      job_id: "analyze-1",
      job_kind: "analyze",
      status: "completed",
      result: {
        analysis: {
          selected_pages_count: 4,
          pages_would_attach_images: 2,
        },
      },
    },
  }),
  rebuildCompleted: presentation.deriveTranslationCompletionPresentation({
    job: {
      job_id: "rebuild-1",
      job_kind: "rebuild",
      status: "completed",
      result: {
        rebuild: {
          docx_path: `C:/tmp/rebuilt ${malicious}.docx`,
        },
      },
    },
  }),
  translationCompleted: presentation.deriveTranslationCompletionPresentation({
    job: {
      job_id: "translate-1",
      job_kind: "translate",
      status: "completed",
    },
    saveSeed: {
      case_number: `CASE-${malicious}`,
      case_entity: `Tribunal ${malicious}`,
      case_city: "Lisbon",
      translation_date: "2026-04-21",
      target_lang: "FR",
      output_docx: "C:/tmp/translated.docx",
    },
  }),
  loadedRow: presentation.deriveTranslationCompletionPresentation({
    currentRowId: 17,
    saveSeed: {
      case_number: "CASE-17",
      case_entity: "Court",
      case_city: "Porto",
      translation_date: "2026-04-20",
    },
  }),
  arabicRequired: presentation.deriveTranslationCompletionPresentation({
    job: {
      job_id: "translate-ar",
      job_kind: "translate",
      status: "completed",
    },
    saveSeed: {
      case_number: "CASE-AR",
      target_lang: "AR",
      output_docx: "C:/tmp/arabic.docx",
    },
    arabicReview: {
      required: true,
      resolved: false,
      status: "waiting_for_save",
      message: `Review malicious ${malicious}`,
      docx_path: "C:/tmp/arabic.docx",
    },
  }),
  arabicMissing: presentation.deriveTranslationCompletionPresentation({
    job: {
      job_id: "translate-ar-missing",
      job_kind: "translate",
      status: "completed",
    },
    saveSeed: {
      case_number: "CASE-AR-MISSING",
      target_lang: "AR",
    },
    arabicReview: {
      required: true,
      resolved: false,
      status: "missing",
    },
  }),
  arabicResolved: presentation.deriveTranslationCompletionPresentation({
    job: {
      job_id: "translate-ar-done",
      job_kind: "translate",
      status: "completed",
    },
    saveSeed: {
      case_number: "CASE-AR-DONE",
      target_lang: "AR",
      output_docx: "C:/tmp/arabic-done.docx",
    },
    arabicReview: {
      required: true,
      resolved: true,
      status: "resolved",
      message: "Arabic review complete.",
      docx_path: "C:/tmp/arabic-done.docx",
    },
  }),
  gmailAttachmentReady: presentation.deriveTranslationCompletionPresentation({
    arabicReview: {
      required: false,
      resolved: true,
    },
    gmailBatchContext: {
      attachment_id: "att-1",
      selected_attachment_filename: "gmail.pdf",
    },
    gmailCurrentStep: {
      visible: true,
      filename: `gmail ${malicious}.pdf`,
      batchLabel: "1/2",
      hasMoreItems: true,
    },
  }),
  gmailFinalizationReady: presentation.deriveTranslationCompletionPresentation({
    gmailBatchContext: {
      attachment_id: "att-1",
    },
    gmailFinalizeReady: true,
  }),
  nullSafe: presentation.deriveTranslationCompletionPresentation(null),
};

console.log(JSON.stringify({
  exportTypes: {
    blankArabicReviewState: typeof presentation.blankArabicReviewState,
    deriveTranslationCompletionPresentation: typeof presentation.deriveTranslationCompletionPresentation,
    normalizeArabicReviewState: typeof presentation.normalizeArabicReviewState,
    hasTranslationSaveSeedData: typeof presentation.hasTranslationSaveSeedData,
  },
  blankReview: presentation.blankArabicReviewState(),
  normalizedReview: presentation.normalizeArabicReviewState({
    required: "yes",
    resolved: false,
    auto_open_pending: "true",
    poll_interval_ms: 1,
    quiet_period_ms: 2,
    status: `waiting_${malicious}`,
    message: `Message ${malicious}`,
  }),
  seedAvailability: {
    empty: presentation.hasTranslationSaveSeedData({}),
    fromRow: presentation.hasTranslationSaveSeedData({}, { currentRowId: 42 }),
    fromSeed: presentation.hasTranslationSaveSeedData({ case_number: "CASE-1" }),
    fromJob: presentation.hasTranslationSaveSeedData({}, {
      job: {
        result: {
          save_seed: {
            court_email: "court@example.test",
          },
        },
      },
    }),
  },
  cases,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__TRANSLATION_COMPLETION_PRESENTATION_MODULE_URL__": "translation_completion_presentation.js"},
        timeout_seconds=20,
    )

    assert results["exportTypes"] == {
        "blankArabicReviewState": "function",
        "deriveTranslationCompletionPresentation": "function",
        "normalizeArabicReviewState": "function",
        "hasTranslationSaveSeedData": "function",
    }
    assert results["blankReview"]["required"] is False
    assert results["blankReview"]["resolved"] is True
    assert results["blankReview"]["status"] == "not_required"
    assert results["normalizedReview"]["required"] is True
    assert results["normalizedReview"]["resolved"] is False
    assert results["normalizedReview"]["auto_open_pending"] is True
    assert results["normalizedReview"]["poll_interval_ms"] == 100
    assert results["normalizedReview"]["quiet_period_ms"] == 100
    assert results["normalizedReview"]["status"] == "waiting_<img src=x onerror=alert(1)><script>bad()</script>"
    assert results["normalizedReview"]["message"] == "Message <img src=x onerror=alert(1)><script>bad()</script>"
    assert results["seedAvailability"] == {
        "empty": False,
        "fromRow": True,
        "fromSeed": True,
        "fromJob": True,
    }

    idle = results["cases"]["idle"]
    assert idle["available"] is False
    assert idle["drawerStatus"] == (
        "When a translation finishes, you can review the result, download files, and save the case record here."
    )
    assert idle["saveTitle"] == "Save Case Record"
    assert idle["saveButtonLabel"] == "Save case record"
    assert idle["arabicReview"]["title"] == "Review Arabic document in Word"
    assert idle["gmailFinalization"]["buttonLabel"] == "Create Gmail reply"
    assert results["cases"]["nullSafe"] == idle

    analyze = results["cases"]["analyzeCompleted"]
    assert analyze["completionButtonLabel"] == "Review analysis"
    assert analyze["drawerStatus"] == "Analysis complete. Review the report, then start a full translation when you are ready."
    assert analyze["resultTitle"] == "Analysis complete."
    assert analyze["resultChipLabel"] == "Report ready"
    assert analyze["resultDetailLines"] == ["Selected pages: 4", "Pages that would use images: 2"]

    rebuild = results["cases"]["rebuildCompleted"]
    assert rebuild["drawerStatus"] == "DOCX rebuild complete. Review the translated DOCX and download the refreshed file here."
    assert rebuild["resultTitle"] == "Translated DOCX refreshed."
    assert rebuild["resultDetailLines"] == ["C:/tmp/rebuilt <img src=x onerror=alert(1)><script>bad()</script>.docx"]

    translation = results["cases"]["translationCompleted"]
    assert translation["available"] is True
    assert translation["drawerStatus"] == (
        "Translation complete. Review the translated document, then save the case record if everything looks right."
    )
    assert translation["resultTitle"] == "Translation complete."
    assert translation["resultDetailLines"] == [
        "CASE-<img src=x onerror=alert(1)><script>bad()</script>",
        "Tribunal <img src=x onerror=alert(1)><script>bad()</script> | Lisbon | 2026-04-21",
    ]

    loaded_row = results["cases"]["loadedRow"]
    assert loaded_row["completionButtonLabel"] == "Open saved case record"
    assert loaded_row["drawerStatus"] == "Saved case record loaded. Review the fields below and save any edits."
    assert loaded_row["resultTitle"] == "Saved case record loaded."

    arabic_required = results["cases"]["arabicRequired"]
    assert arabic_required["drawerStatus"] == "Review malicious <img src=x onerror=alert(1)><script>bad()</script>"
    assert arabic_required["saveStatus"] == "Review malicious <img src=x onerror=alert(1)><script>bad()</script>"
    assert arabic_required["arabicReview"]["chipLabel"] == "Waiting"
    assert arabic_required["arabicReview"]["chipTone"] == "info"
    assert arabic_required["gmailCurrentAttachment"]["title"] == (
        "Review the Arabic document in Word before you save this Gmail attachment."
    )

    arabic_missing = results["cases"]["arabicMissing"]
    assert arabic_missing["arabicReview"]["chipLabel"] == "Required"
    assert arabic_missing["arabicReview"]["chipTone"] == "warn"
    assert arabic_missing["drawerStatus"] == "Review the Arabic document in Word before you save the case record."

    arabic_resolved = results["cases"]["arabicResolved"]
    assert arabic_resolved["saveStatus"] == "Arabic document review is complete. Save the case record when you are ready."
    assert arabic_resolved["arabicReview"]["chipLabel"] == "Done"
    assert arabic_resolved["arabicReview"]["chipTone"] == "ok"

    gmail_attachment = results["cases"]["gmailAttachmentReady"]
    assert gmail_attachment["gmailCurrentAttachment"] == {
        "ready": True,
        "title": "This Gmail attachment is ready to save.",
        "copy": "Save this translated attachment, then continue with the next Gmail step.",
        "chipLabel": "1/2",
        "filename": "gmail <img src=x onerror=alert(1)><script>bad()</script>.pdf",
        "buttonLabel": "Save this Gmail attachment",
    }

    gmail_finalization = results["cases"]["gmailFinalizationReady"]
    assert gmail_finalization["gmailFinalization"]["ready"] is True
    assert gmail_finalization["gmailFinalization"]["title"] == "Create Gmail Reply"
    assert gmail_finalization["gmailFinalization"]["status"] == (
        "Every selected Gmail attachment is saved. You can create the Gmail reply when you are ready."
    )
