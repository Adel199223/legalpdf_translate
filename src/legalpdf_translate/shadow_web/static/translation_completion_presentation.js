export function blankArabicReviewState() {
  return {
    required: false,
    resolved: true,
    resolution: "",
    status: "not_required",
    message: "",
    docx_path: "",
    fingerprint_changed: false,
    save_detected: false,
    fallback_used: false,
    job_id: "",
    completion_key: "",
    poll_interval_ms: 500,
    quiet_period_ms: 1500,
    auto_open_pending: false,
  };
}

export function normalizeArabicReviewState(value) {
  const base = blankArabicReviewState();
  if (!value || typeof value !== "object") {
    return base;
  }
  return {
    ...base,
    ...value,
    required: Boolean(value.required),
    resolved: Boolean(value.required ? value.resolved : true),
    resolution: String(value.resolution || "").trim(),
    fingerprint_changed: Boolean(value.fingerprint_changed),
    save_detected: Boolean(value.save_detected),
    fallback_used: Boolean(value.fallback_used),
    auto_open_pending: Boolean(value.auto_open_pending),
    poll_interval_ms: Number.isFinite(Number(value.poll_interval_ms)) ? Math.max(100, Number(value.poll_interval_ms)) : 500,
    quiet_period_ms: Number.isFinite(Number(value.quiet_period_ms)) ? Math.max(100, Number(value.quiet_period_ms)) : 1500,
    job_id: String(value.job_id || "").trim(),
    completion_key: String(value.completion_key || "").trim(),
    status: String(value.status || base.status).trim() || base.status,
    message: String(value.message || "").trim(),
    docx_path: String(value.docx_path || "").trim(),
  };
}

export function hasTranslationSaveSeedData(saveSeed = {}, { currentRowId = null, job = null } = {}) {
  const seed = saveSeed && typeof saveSeed === "object" ? saveSeed : {};
  return Boolean(
    currentRowId
    || job?.result?.save_seed
    || seed.run_id
    || seed.case_number
    || seed.court_email
    || seed.case_entity
    || seed.case_city,
  );
}

export function deriveTranslationCompletionPresentation(options = {}) {
  const {
    job = null,
    saveSeed = null,
    currentRowId = null,
    arabicReview = null,
    gmailBatchContext = null,
    gmailCurrentStep = null,
    gmailFinalizeReady = false,
  } = options || {};
  const seed = saveSeed && typeof saveSeed === "object"
    ? saveSeed
    : (job?.result?.save_seed || {});
  const review = normalizeArabicReviewState(arabicReview);
  const hasSaveSeed = hasTranslationSaveSeedData(seed, { currentRowId, job });
  const available = hasSaveSeed || Boolean(job?.status === "completed");
  const rowLoaded = Boolean(currentRowId);
  const analyzeCompleted = Boolean(job?.job_kind === "analyze" && job?.status === "completed");
  const rebuildCompleted = Boolean(job?.job_kind === "rebuild" && job?.status === "completed");
  const translationCompleted = Boolean(job?.job_kind === "translate" && job?.status === "completed");
  const blockedOnArabicReview = Boolean(review.required && !review.resolved);
  const gmailStep = gmailCurrentStep && typeof gmailCurrentStep === "object" ? gmailCurrentStep : {};
  const gmailStepFilename = String(gmailStep.filename || "").trim();
  const gmailStepBatchLabel = String(gmailStep.batchLabel || "").trim() || "Gmail";
  const gmailStepHasMoreItems = Boolean(gmailStep.hasMoreItems);
  const resultDetailLines = [];

  if (rowLoaded || hasSaveSeed || translationCompleted) {
    if (seed.case_number || seed.case_entity || seed.case_city || seed.translation_date) {
      resultDetailLines.push(seed.case_number || "No case number");
      resultDetailLines.push([
        seed.case_entity || "No case entity",
        seed.case_city || "No case city",
        seed.translation_date || "No date",
      ].join(" | "));
    }
  } else if (analyzeCompleted) {
    const analysis = job?.result?.analysis || {};
    resultDetailLines.push(`Selected pages: ${analysis.selected_pages_count ?? 0}`);
    if (analysis.pages_would_attach_images != null) {
      resultDetailLines.push(`Pages that would use images: ${analysis.pages_would_attach_images}`);
    }
  } else if (rebuildCompleted) {
    resultDetailLines.push(job?.result?.rebuild?.docx_path || "Updated DOCX is ready.");
  }

  let completionButtonLabel = "Finish Translation";
  let drawerStatus = "When a translation finishes, you can review the result, download files, and save the case record here.";
  let emptyTitle = "Review Results";
  let emptyCopy = "When a translation finishes, you can review the result, download files, and save the case record here.";
  let resultTitle = "Finish Translation";
  let resultCopy = "When a translation finishes, you can review the result, download files, and save the case record here.";
  let resultChipLabel = "Waiting";
  let resultChipTone = "info";
  let saveTitle = "Save Case Record";
  let saveStatus = "When a translation finishes, you can review the result, download files, and save the case record here.";

  if (rowLoaded) {
    completionButtonLabel = "Open saved case record";
    drawerStatus = "Saved case record loaded. Review the fields below and save any edits.";
    resultTitle = "Saved case record loaded.";
    resultCopy = "Review the fields below and save any edits.";
    resultChipLabel = "Loaded";
    resultChipTone = "info";
    saveStatus = "Saved case record loaded. Review the fields below and save any edits.";
  } else if (analyzeCompleted) {
    completionButtonLabel = "Review analysis";
    drawerStatus = "Analysis complete. Review the report, then start a full translation when you are ready.";
    emptyCopy = drawerStatus;
    resultTitle = "Analysis complete.";
    resultCopy = "Review the report, then start a full translation when you are ready.";
    resultChipLabel = "Report ready";
    resultChipTone = "ok";
    saveStatus = drawerStatus;
  } else if (rebuildCompleted) {
    drawerStatus = "DOCX rebuild complete. Review the translated DOCX and download the refreshed file here.";
    resultTitle = "Translated DOCX refreshed.";
    resultCopy = "Review the refreshed translated DOCX and download it when you are ready.";
    resultChipLabel = "Ready";
    resultChipTone = "ok";
    saveStatus = "The translated DOCX was rebuilt. Review it here before you save the case record.";
  } else if (translationCompleted || hasSaveSeed) {
    drawerStatus = "Translation complete. Review the translated document, then save the case record if everything looks right.";
    resultTitle = "Translation complete.";
    resultCopy = "Review the translated document, then save the case record if everything looks right.";
    resultChipLabel = "Ready";
    resultChipTone = "ok";
    saveStatus = "Translation complete. Review the translated document, then save the case record if everything looks right.";
  }

  if (blockedOnArabicReview) {
    drawerStatus = review.message || "Review the Arabic document in Word before you save the case record.";
    saveStatus = review.message || "Review the Arabic document in Word before you save the case record.";
  } else if (review.required && review.resolved && (translationCompleted || hasSaveSeed)) {
    saveStatus = "Arabic document review is complete. Save the case record when you are ready.";
  }

  const gmailAttachmentReady = Boolean(gmailBatchContext || gmailStep.visible);
  const gmailCurrentAttachment = {
    ready: gmailAttachmentReady,
    title: blockedOnArabicReview
      ? "Review the Arabic document in Word before you save this Gmail attachment."
      : "This Gmail attachment is ready to save.",
    copy: blockedOnArabicReview
      ? (review.message || "Open the translated DOCX in Word, save it there, then return here to save this Gmail attachment.")
      : gmailStepHasMoreItems
        ? "Save this translated attachment, then continue with the next Gmail step."
        : "Save this translated attachment, then continue to create the Gmail reply.",
    chipLabel: gmailStepBatchLabel,
    filename: gmailStepFilename,
    buttonLabel: "Save this Gmail attachment",
  };

  return {
    available,
    hasSaveSeed,
    completionButtonLabel,
    drawerStatus,
    emptyTitle,
    emptyCopy,
    resultTitle,
    resultCopy,
    resultChipLabel,
    resultChipTone,
    resultDetailLines,
    saveTitle,
    saveStatus,
    saveButtonLabel: "Save case record",
    arabicReview: {
      title: "Review Arabic document in Word",
      copy: blockedOnArabicReview
        ? (review.message || "Open the translated DOCX in Word, make any alignment or formatting fixes, save it, then return here.")
        : review.required && review.resolved
          ? "The Arabic document review is complete. Save the case record or continue with the Gmail step when you are ready."
          : "Open the translated DOCX in Word, make any alignment or formatting fixes, save it, then return here.",
      chipLabel: review.required && review.resolved
        ? "Done"
        : review.status === "waiting_for_save"
          ? "Waiting"
          : "Required",
      chipTone: review.required && review.resolved
        ? "ok"
        : review.status === "attention" || review.status === "missing"
          ? "warn"
          : "info",
      docxLabel: "Translated DOCX",
      unavailableText: "Translated DOCX unavailable.",
      openLabel: "Open in Word",
      continueNowLabel: "I saved the Word file",
      continueWithoutChangesLabel: "Continue without changes",
    },
    gmailCurrentAttachment,
    gmailFinalization: {
      ready: Boolean(gmailFinalizeReady),
      title: "Create Gmail Reply",
      status: gmailFinalizeReady
        ? "Every selected Gmail attachment is saved. You can create the Gmail reply when you are ready."
        : "After every selected attachment is saved, create the Gmail reply with the final files.",
      summary: gmailFinalizeReady
        ? "The final Gmail reply step is ready."
        : "Finish saving every Gmail attachment to unlock the final reply step.",
      resultEmpty: "Gmail reply details will appear here after the final step.",
      filenameLabel: "Final DOCX filename",
      filenamePlaceholder: "Optional filename for the final Gmail DOCX",
      buttonLabel: "Create Gmail reply",
    },
  };
}
