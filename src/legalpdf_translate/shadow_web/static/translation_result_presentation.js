function objectOrEmpty(value) {
  return value && typeof value === "object" ? value : {};
}

function normalizeRecoverySamples(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((item) => String(item ?? "").trim())
    .filter(Boolean)
    .slice(0, 3);
}

function normalizeAdvisorRecommendation(value) {
  if (!value || typeof value !== "object") {
    return {
      recommended_ocr_mode: "",
      recommended_image_mode: "",
      recommendation_reasons: [],
      confidence: 0,
    };
  }
  return {
    recommended_ocr_mode: String(value.recommended_ocr_mode || "").trim().toLowerCase(),
    recommended_image_mode: String(value.recommended_image_mode || "").trim().toLowerCase(),
    recommendation_reasons: normalizeRecoverySamples(value.recommendation_reasons),
    confidence: Number(value.confidence || 0),
  };
}

function modeStrength(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (normalized === "always") {
    return 2;
  }
  if (normalized === "auto") {
    return 1;
  }
  return 0;
}

function advisorRerunHint(job) {
  const advisor = normalizeAdvisorRecommendation(job?.result?.advisor_recommendation);
  const retryReason = String(job?.result?.failure_context?.retry_reason || "").trim();
  const targetLang = String(job?.config?.target_lang || job?.result?.metrics?.target_lang || "").trim().toUpperCase();
  const currentOcrMode = String(job?.config?.ocr_mode || "").trim().toLowerCase();
  const currentImageMode = String(job?.config?.image_mode || "").trim().toLowerCase();
  const strongerOcr = modeStrength(advisor.recommended_ocr_mode) > modeStrength(currentOcrMode);
  const strongerImage = modeStrength(advisor.recommended_image_mode) > modeStrength(currentImageMode);
  const stronger = targetLang === "AR" && retryReason === "ar_token_violation" && (strongerOcr || strongerImage);
  if (!stronger) {
    return {
      stronger: false,
      message: "",
      recommendation: advisor,
    };
  }
  const settings = [];
  if (strongerOcr) {
    settings.push(`OCR ${advisor.recommended_ocr_mode}`);
  }
  if (strongerImage) {
    settings.push(`Images ${advisor.recommended_image_mode}`);
  }
  return {
    stronger: true,
    message: `Recommended rerun settings: ${settings.join(" / ")}. Change the setup, then use Start Translate for a new run.`,
    recommendation: advisor,
  };
}

function translationFailureContext(job) {
  return job?.result?.failure_context || {};
}

function describeCredentialSource(source) {
  const kind = String(source?.kind || "").trim();
  const name = String(source?.name || "").trim();
  if (kind === "stored") {
    return "stored app key";
  }
  if (kind === "env") {
    return name ? `env ${name}` : "environment variable";
  }
  if (kind === "inline") {
    return "inline key";
  }
  if (kind === "missing") {
    return "not configured";
  }
  return kind || "unknown";
}

function buildPreparedTranslationSummaryLines({ launch = null, defaultTarget = "" } = {}) {
  const preparedLaunch = objectOrEmpty(launch);
  if (!launch) {
    return [];
  }
  const gmailTarget = String(
    preparedLaunch.target_lang || preparedLaunch.gmail_batch_context?.selected_target_lang || "",
  ).trim().toUpperCase();
  const normalizedDefaultTarget = String(defaultTarget || "").trim().toUpperCase();
  const targetLines = gmailTarget
    ? [`Current Gmail job target: ${gmailTarget}`]
    : ["Current Gmail job target: ?"];
  if (normalizedDefaultTarget && normalizedDefaultTarget !== gmailTarget) {
    targetLines.push(`Default target for new jobs: ${normalizedDefaultTarget}`);
  }
  return [
    `Attachment: ${preparedLaunch.source_filename || preparedLaunch.gmail_batch_context?.selected_attachment_filename || "Prepared source"}`,
    ...targetLines,
    `Start page: ${preparedLaunch.start_page ?? preparedLaunch.gmail_batch_context?.selected_start_page ?? 1}`,
    `Images: ${preparedLaunch.image_mode || "auto"}`,
    `OCR: ${preparedLaunch.ocr_mode || "auto"} / ${preparedLaunch.ocr_engine || "local_then_api"}`,
    `Resume: ${preparedLaunch.resume === false ? "off" : "on"}`,
    `Keep intermediates: ${preparedLaunch.keep_intermediates === false ? "off" : "on"}`,
  ];
}

export function looksLikeRawTechnicalStateText(value) {
  const text = String(value || "").trim();
  return Boolean(
    text.startsWith("{")
    || text.startsWith("[")
    || /"job_id"|"normalized_payload"|"progress"|"result"/.test(text)
    || /^translation job state/i.test(text),
  );
}

export function isAuthenticationFailure(job) {
  return String(job?.result?.error || "").trim() === "authentication_failure";
}

export function deriveTranslationRecoveryState(job) {
  const base = {
    visible: false,
    statusMessage: "",
    diagnosticsHint: "",
    summaryLines: [],
    guidanceLines: [],
    advisorMessage: "",
    failureReason: "",
    failurePage: null,
    recommendedAction: "",
  };
  if (!job || job.job_kind !== "translate" || !["failed", "cancelled"].includes(String(job.status || "").trim())) {
    return base;
  }
  const result = job.result && typeof job.result === "object" ? job.result : {};
  const failure = result.failure_context && typeof result.failure_context === "object" ? result.failure_context : {};
  const tokenDetails = failure.ar_token_details && typeof failure.ar_token_details === "object"
    ? failure.ar_token_details
    : {};
  const missingSamples = normalizeRecoverySamples(tokenDetails.missing_token_samples);
  const unexpectedSamples = normalizeRecoverySamples(tokenDetails.unexpected_token_samples);
  const violationSamples = normalizeRecoverySamples(failure.ar_violation_samples);
  const retryReason = String(failure.retry_reason || "").trim();
  const validatorReason = String(failure.validator_defect_reason || "").trim();
  const failureReason = validatorReason || String(result.error || job.status_text || "").trim();
  const failurePageRaw = Number.parseInt(String(result.failed_page ?? failure.page_number ?? ""), 10);
  const failurePage = Number.isFinite(failurePageRaw) && failurePageRaw > 0 ? failurePageRaw : null;
  const reviewQueueCountRaw = Number.parseInt(String(result.review_queue_count ?? 0), 10);
  const reviewQueueCount = Number.isFinite(reviewQueueCountRaw) && reviewQueueCountRaw > 0 ? reviewQueueCountRaw : 0;
  const advisor = advisorRerunHint(job);
  const summaryLines = [];
  if (failurePage !== null) {
    summaryLines.push(`Failed page: ${failurePage}`);
  }
  if (failureReason) {
    summaryLines.push(`Validator reason: ${failureReason}`);
  }
  if (retryReason) {
    summaryLines.push(`Retry reason: ${retryReason}`);
  }
  if (reviewQueueCount > 0) {
    summaryLines.push(`Flagged review pages: ${reviewQueueCount}`);
  }
  if (missingSamples.length) {
    summaryLines.push(`Missing protected tokens after retry: ${missingSamples.join(", ")}`);
  }
  if (unexpectedSamples.length) {
    summaryLines.push(`Unexpected or altered protected tokens: ${unexpectedSamples.join(", ")}`);
  } else if (violationSamples.length) {
    summaryLines.push(`Arabic token samples: ${violationSamples.join(", ")}`);
  }
  const guidanceLines = [
    "Resume Translation reruns the same config against the same source.",
    "Change OCR or image settings first, then use Start Translate for a new run.",
    "Rebuild DOCX only assembles completed pages and does not make this Gmail item confirmable.",
  ];
  const statusMessage = job.status === "cancelled"
    ? "Translation stopped before this Gmail attachment could be confirmed. Resume reruns the same config, and Start Translate is the path for changed OCR/image settings."
    : "Translation needs recovery before this Gmail attachment can continue. Resume reruns the same config, and Start Translate is the path for changed OCR/image settings.";
  const diagnosticsHint = advisor.message || `${guidanceLines[0]} ${guidanceLines[1]} ${guidanceLines[2]}`;
  return {
    visible: true,
    statusMessage,
    diagnosticsHint,
    summaryLines,
    guidanceLines,
    advisorMessage: advisor.message,
    failureReason,
    failurePage,
    recommendedAction: advisor.stronger ? "start_translate_with_advisor" : "resume_translation",
  };
}

export function buildTranslationResultCardPresentation({
  job = null,
  preparedLaunch = null,
  hasReadySource = false,
  defaultTarget = "",
} = {}) {
  if (!job) {
    if (preparedLaunch) {
      return {
        title: "Prepared Gmail attachment is ready to start.",
        summaryLines: buildPreparedTranslationSummaryLines({ launch: preparedLaunch, defaultTarget }),
        footer: "Ready to start. Click Start Translate when you're ready.",
        label: "ready",
        tone: "info",
      };
    }
    if (hasReadySource) {
      return {
        title: "Source file is ready.",
        summaryLines: ["Confirm the language and output folder, then click Start Translate when you're ready."],
        label: "ready",
        tone: "ok",
      };
    }
    return {
      empty: true,
      emptyText: "Choose a source file to see translation progress and results here.",
    };
  }

  const summaryLines = [];
  if (job.job_kind === "analyze") {
    const analysis = job.result?.analysis || {};
    summaryLines.push(`Selected pages: ${analysis.selected_pages_count ?? 0}`);
    summaryLines.push(`Would attach images: ${analysis.pages_would_attach_images ?? 0}`);
    const advisor = analysis.advisor_recommendation || {};
    if (advisor.recommended_ocr_mode || advisor.recommended_image_mode) {
      summaryLines.push(`Advisor: OCR ${advisor.recommended_ocr_mode || "?"} / Images ${advisor.recommended_image_mode || "?"}`);
    }
  } else if (job.job_kind === "rebuild") {
    summaryLines.push(`DOCX: ${job.result?.rebuild?.docx_path || "Unavailable"}`);
  } else {
    const result = job.result || {};
    const metrics = result.metrics || {};
    if (isAuthenticationFailure(job)) {
      const failureContext = translationFailureContext(job);
      const credentialSource = describeCredentialSource(failureContext.credential_source);
      summaryLines.push("Recovery: open Browser Settings, save a valid translation key, and run Test Translation Auth.");
      summaryLines.push(`Credential source: ${credentialSource}`);
      summaryLines.push(
        `Failure scope: ${failureContext.scope === "preflight" ? "preflight before page processing" : "page translation"}`,
      );
      if (failureContext.status_code) {
        summaryLines.push(`Status code: ${failureContext.status_code}`);
      }
      if (failureContext.exception_class) {
        summaryLines.push(`Failure class: ${failureContext.exception_class}`);
      }
      if (failureContext.message) {
        summaryLines.push(failureContext.message);
      }
    } else if (deriveTranslationRecoveryState(job).visible) {
      const recovery = deriveTranslationRecoveryState(job);
      summaryLines.push(...recovery.summaryLines);
      if (recovery.advisorMessage) {
        summaryLines.push(recovery.advisorMessage);
      }
      summaryLines.push(...recovery.guidanceLines);
    } else {
      summaryLines.push(`Completed pages: ${result.completed_pages ?? 0}`);
      if (metrics.run_id) {
        summaryLines.push(`Run ID: ${metrics.run_id}`);
      }
      if (result.review_queue_count) {
        summaryLines.push(`Flagged review pages: ${result.review_queue_count}`);
      }
      if (result.error) {
        summaryLines.push(`Error: ${result.error}`);
      }
    }
  }

  const primaryTitle = String(job.status_text || "").trim();
  const safeTitle = primaryTitle && !looksLikeRawTechnicalStateText(primaryTitle)
    ? primaryTitle
    : job.status === "completed"
      ? "Translation complete."
      : "Translation progress is available.";
  return {
    title: safeTitle,
    summaryLines,
    label: job.status,
    tone: job.status === "completed" ? "ok" : job.status === "failed" ? "bad" : job.status === "cancelled" ? "warn" : "info",
  };
}
