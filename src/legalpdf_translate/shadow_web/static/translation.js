import { fetchJson } from "./api.js";
import { appState, setActiveView } from "./state.js";
import { ensureBrowserPdfBundleFromFile } from "./browser_pdf.js";
import {
  clearNode,
  createEmptyState,
  createTextElement,
  setNodeTitle,
} from "./safe_rendering.js";

const translationState = {
  currentSeed: null,
  currentRowId: null,
  currentJob: null,
  currentJobId: "",
  runtimeJobs: [],
  currentGmailBatchContext: null,
  currentPreparedLaunch: null,
  manualSourceFile: null,
  sourceCard: null,
  sourceUpload: null,
  uploadedSourcePath: "",
  uploadedSourceKey: "",
  pollTimer: null,
  arabicReviewPollTimer: null,
  completionDrawerOpen: false,
  lastAutoOpenedCompletionKey: "",
  arabicReview: null,
  numericMismatchWarningsByJobId: {},
  numericMismatchWarningFetches: {},
};

let lastTranslationUiSnapshotKey = "";
const PAGE_FLAG_LOG_RE = /page=(?<page>\d+)\s+image_used=(?<image>True|False)\s+retry_used=(?<retry>True|False)\s+status=(?<status>[a-z_]+)/;
const PAGE_STATUS_LOG_RE = /Page\s+(?<page>\d+)\s+(?<status>finished|failed)/i;
const NUMERIC_MISMATCH_WARNING_MESSAGE = "Review recommended: some numbers from the source may not appear exactly in the translation.";

function normalizeGmailBatchContext(value) {
  if (!value || typeof value !== "object") {
    return null;
  }
  const normalized = {
    source: String(value.source || "").trim(),
    session_id: String(value.session_id || "").trim(),
    message_id: String(value.message_id || "").trim(),
    thread_id: String(value.thread_id || "").trim(),
    attachment_id: String(value.attachment_id || "").trim(),
    selected_attachment_filename: String(value.selected_attachment_filename || "").trim(),
    selected_attachment_count: Number.parseInt(String(value.selected_attachment_count ?? "").trim(), 10) || 0,
    selected_target_lang: String(value.selected_target_lang || "").trim().toUpperCase(),
    selected_start_page: Number.parseInt(String(value.selected_start_page ?? "").trim(), 10) || 0,
    gmail_batch_session_report_path: String(value.gmail_batch_session_report_path || "").trim(),
  };
  return Object.values(normalized).some((item) => item)
    ? normalized
    : null;
}

function normalizePreparedTranslationLaunch(value) {
  if (!value || typeof value !== "object") {
    return null;
  }
  const pageCount = Number.parseInt(String(value.page_count ?? "").trim(), 10);
  const startPage = Number.parseInt(String(value.start_page ?? "").trim(), 10);
  const normalized = {
    source_path: String(value.source_path || "").trim(),
    source_filename: String(value.source_filename || "").trim(),
    page_count: Number.isFinite(pageCount) && pageCount > 0 ? pageCount : null,
    start_page: Number.isFinite(startPage) && startPage > 0 ? startPage : 1,
    output_dir: String(value.output_dir || "").trim(),
    target_lang: String(value.target_lang || "").trim().toUpperCase(),
    image_mode: String(value.image_mode || "").trim(),
    ocr_mode: String(value.ocr_mode || "").trim(),
    ocr_engine: String(value.ocr_engine || "").trim(),
    resume: typeof value.resume === "boolean" ? value.resume : null,
    keep_intermediates: typeof value.keep_intermediates === "boolean" ? value.keep_intermediates : null,
    auto_start: typeof value.auto_start === "boolean" ? value.auto_start : null,
    workflow_source: String(value.workflow_source || "").trim(),
    gmail_batch_context: normalizeGmailBatchContext(value.gmail_batch_context),
  };
  return Object.values(normalized).some((item) => item)
    ? normalized
    : null;
}

function currentPreparedTranslationLaunch() {
  return translationState.currentPreparedLaunch;
}

function clearPreparedTranslationLaunch() {
  translationState.currentPreparedLaunch = null;
}

function hasPreparedTranslationLaunch() {
  return Boolean(currentPreparedTranslationLaunch() && !translationState.currentJob && !hasTranslationCompletionSurface());
}

function isActiveTranslationJobStatus(status) {
  return ["queued", "running", "cancel_requested"].includes(String(status || "").trim());
}

// Fresh Gmail prepares should replace stale terminal workspace jobs instead of
// inheriting their failed/completed state into New Job.
function shouldResetWorkspaceForPreparedGmailLaunch(launch, { gmailBatchContext = null, workflowSource = "" } = {}) {
  if (!translationState.currentJob) {
    return false;
  }
  if (isActiveTranslationJobStatus(translationState.currentJob.status)) {
    return false;
  }
  return Boolean(gmailBatchContext || String(workflowSource || "").trim() === "gmail_intake");
}

function resetTranslationWorkspaceForPreparedLaunch() {
  translationState.currentSeed = null;
  translationState.currentRowId = null;
  translationState.lastAutoOpenedCompletionKey = "";
  translationState.currentGmailBatchContext = null;
  clearSourceUploadState();
  clearManualStagedSource();
  clearPreparedTranslationLaunch();
  setFieldValue("translation-job-id", "");
  setFieldValue("translation-row-id", "");
  closeTranslationCompletionDrawer();
  clearArabicReviewState();
  renderTranslationJob(null);
}

function preparedTranslationSummaryLines(launch = currentPreparedTranslationLaunch()) {
  if (!launch) {
    return [];
  }
  const gmailTarget = String(launch.target_lang || launch.gmail_batch_context?.selected_target_lang || "").trim().toUpperCase();
  const defaultTarget = defaultTranslationTargetLang();
  const targetLines = gmailTarget
    ? [`Current Gmail job target: ${gmailTarget}`]
    : ["Current Gmail job target: ?"];
  if (defaultTarget && defaultTarget !== gmailTarget) {
    targetLines.push(`Default target for new jobs: ${defaultTarget}`);
  }
  return [
    `Attachment: ${launch.source_filename || launch.gmail_batch_context?.selected_attachment_filename || "Prepared source"}`,
    ...targetLines,
    `Start page: ${launch.start_page ?? launch.gmail_batch_context?.selected_start_page ?? 1}`,
    `Images: ${launch.image_mode || "auto"}`,
    `OCR: ${launch.ocr_mode || "auto"} / ${launch.ocr_engine || "local_then_api"}`,
    `Resume: ${launch.resume === false ? "off" : "on"}`,
    `Keep intermediates: ${launch.keep_intermediates === false ? "off" : "on"}`,
  ];
}

function preparedTranslationStatusSummary(launch = currentPreparedTranslationLaunch()) {
  if (!launch) {
    return "";
  }
  return "Gmail attachment is prepared. Review settings, then start translation.";
}

function summarizeRuntimeJob(job) {
  if (!job || typeof job !== "object") {
    return null;
  }
  return {
    job_id: String(job.job_id || "").trim(),
    job_kind: String(job.job_kind || "").trim(),
    status: String(job.status || "").trim(),
    updated_at: String(job.updated_at || "").trim(),
    has_save_seed: Boolean(job.result?.save_seed),
    config: {
      source_path: String(job.config?.source_path || "").trim(),
      target_lang: String(job.config?.target_lang || "").trim(),
      start_page: Number.parseInt(String(job.config?.start_page ?? "").trim(), 10) || 0,
      gmail_batch_context: normalizeGmailBatchContext(job.config?.gmail_batch_context),
    },
  };
}

function titleCaseWords(value) {
  return String(value || "")
    .trim()
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function recentWorkTypeLabel(value) {
  return String(value || "").trim().toLowerCase() === "interpretation"
    ? "Interpretation"
    : "Translation";
}

function recentRunKindLabel(value) {
  const kind = String(value || "").trim().toLowerCase();
  if (kind === "translate") {
    return "Translation";
  }
  if (kind === "analyze") {
    return "Analysis";
  }
  if (kind === "rebuild") {
    return "DOCX rebuild";
  }
  return titleCaseWords(kind) || "Translation";
}

function recentRunStatusLabel(value) {
  const status = String(value || "").trim().toLowerCase();
  if (status === "queued") {
    return "Queued";
  }
  if (status === "running") {
    return "Running";
  }
  if (status === "completed") {
    return "Complete";
  }
  if (status === "failed") {
    return "Needs attention";
  }
  if (status === "cancel_requested") {
    return "Cancel requested";
  }
  if (status === "canceled") {
    return "Canceled";
  }
  return titleCaseWords(status) || "Unknown";
}

export function formatRecentRunTitle(job = {}) {
  const sourcePath = String(job?.config?.source_path || "").trim();
  if (sourcePath) {
    const segments = sourcePath.split(/[\\/]/).filter(Boolean);
    return segments[segments.length - 1] || sourcePath;
  }
  return String(job?.job_id || "").trim() || "Translation run";
}

export function deriveRecentWorkPresentation({
  recentItemCount = 0,
  translationRunCount = 0,
  recordAvailable = true,
  jobType = "",
  job = null,
} = {}) {
  const typeLabel = recentWorkTypeLabel(jobType || job?.job_type || job?.row?.job_type);
  const targetLang = String(job?.config?.target_lang || "").trim().toUpperCase();
  const translationRunSubtitleBits = [
    recentRunKindLabel(job?.job_kind),
    targetLang ? `Target ${targetLang}` : "",
    recentRunStatusLabel(job?.status),
  ].filter(Boolean);
  const deleteConfirmMessage = typeLabel === "Interpretation"
    ? "Delete this saved interpretation record? This cannot be undone."
    : typeLabel === "Translation"
      ? "Delete this saved translation record? This cannot be undone."
      : "Delete this saved record? This cannot be undone.";

  return {
    typeLabel,
    recentWorkEmpty: "No saved work yet. Completed translations and interpretation requests will appear here.",
    recentCasesEmpty: "No saved cases yet.",
    recentWorkCount: `${recentItemCount} recent item(s) ready.`,
    recentOpenLabel: recordAvailable ? "Open" : "Open unavailable",
    recentDeleteLabel: "Delete record",
    interpretationHistoryEmpty: "No saved interpretation requests yet.",
    interpretationHistoryOpenLabel: "Open",
    interpretationHistoryDeleteLabel: "Delete record",
    translationHistoryEmpty: "No saved translation cases yet.",
    translationHistoryOpenLabel: "Open",
    translationHistoryDeleteLabel: "Delete record",
    translationRunsEmpty: "No translation runs have started yet.",
    translationRunsCount: `${translationRunCount} translation run(s) ready.`,
    translationRunOpenLabel: "Open run",
    translationRunResumeLabel: "Resume",
    translationRunRebuildLabel: "Rebuild DOCX",
    translationRunTitle: formatRecentRunTitle(job),
    translationRunSubtitle: translationRunSubtitleBits.join(" | "),
    deleteConfirmMessage,
    deleteStatus: "Saved record deleted.",
    refreshStatus: "Saved work refreshed.",
    loadedSavedCaseStatus: "Saved case record loaded. Review the details below.",
  };
}

function rememberRuntimeJob(job) {
  const summarized = summarizeRuntimeJob(job);
  if (!summarized || !summarized.job_id) {
    return;
  }
  const remaining = translationState.runtimeJobs.filter((item) => item?.job_id !== summarized.job_id);
  translationState.runtimeJobs = [summarized, ...remaining];
}

function blankArabicReviewState() {
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

function normalizeArabicReviewState(value) {
  const base = blankArabicReviewState();
  if (!value || typeof value !== "object") {
    return base;
  }
  return {
    ...base,
    ...value,
    required: Boolean(value.required),
    resolved: Boolean(value.required ? value.resolved : true),
    fingerprint_changed: Boolean(value.fingerprint_changed),
    save_detected: Boolean(value.save_detected),
    fallback_used: Boolean(value.fallback_used),
    auto_open_pending: Boolean(value.auto_open_pending),
    poll_interval_ms: Number.isFinite(Number(value.poll_interval_ms)) ? Math.max(100, Number(value.poll_interval_ms)) : 500,
    quiet_period_ms: Number.isFinite(Number(value.quiet_period_ms)) ? Math.max(100, Number(value.quiet_period_ms)) : 1500,
    job_id: String(value.job_id || "").trim(),
    completion_key: String(value.completion_key || "").trim(),
    status: String(value.status || base.status).trim() || base.status,
    resolution: String(value.resolution || "").trim(),
    message: String(value.message || "").trim(),
    docx_path: String(value.docx_path || "").trim(),
  };
}

function currentArabicReviewState() {
  return normalizeArabicReviewState(translationState.arabicReview);
}

function hasTranslationSaveSeedData(saveSeed = {}, { currentRowId = null, job = null } = {}) {
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

export function deriveTranslationCompletionPresentation({
  job = null,
  saveSeed = null,
  currentRowId = null,
  arabicReview = null,
  gmailBatchContext = null,
  gmailCurrentStep = null,
  gmailFinalizeReady = false,
} = {}) {
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

function translationUiSnapshotKey() {
  return JSON.stringify(getTranslationUiSnapshot());
}

function notifyTranslationUiStateChanged({ force = false } = {}) {
  const nextKey = translationUiSnapshotKey();
  if (!force && nextKey === lastTranslationUiSnapshotKey) {
    return;
  }
  lastTranslationUiSnapshotKey = nextKey;
  window.dispatchEvent(new CustomEvent("legalpdf:translation-ui-state-changed"));
}

function clearTranslationCompletionSeed() {
  translationState.currentSeed = null;
  translationState.currentRowId = null;
  setFieldValue("translation-row-id", "");
  clearArabicReviewState();
  syncTranslationCompletionSurface();
  notifyTranslationUiStateChanged();
}

function qs(id) {
  return document.getElementById(id);
}

function fieldValue(id) {
  return qs(id)?.value?.trim?.() ?? "";
}

function setFieldValue(id, value) {
  const node = qs(id);
  if (node) {
    node.value = value ?? "";
  }
}

function setCheckbox(id, value) {
  const node = qs(id);
  if (node) {
    node.checked = Boolean(value);
  }
}

function coercePositiveInt(value) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function blankSourceCardState() {
  return {
    kind: "empty",
    status: "idle",
    filename: "",
    sourceType: "",
    pageCount: null,
    sourcePath: "",
    message: "",
  };
}

function blankSourceUploadState() {
  return {
    token: 0,
    pending: false,
    fileKey: "",
    filename: "",
    sourceType: "",
    replacingPrepared: false,
    preservedPreparedLaunch: null,
    preservedGmailBatchContext: null,
    preservedSourcePath: "",
  };
}

function inferSourceType(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "";
  }
  if (normalized === "pdf" || normalized.endsWith(".pdf")) {
    return "pdf";
  }
  if (normalized === "image" || /\.(png|jpe?g|gif|webp|bmp|tiff?)$/i.test(normalized)) {
    return "image";
  }
  return "";
}

function buildPreparedSourceCardState(launch = currentPreparedTranslationLaunch()) {
  if (!launch) {
    return blankSourceCardState();
  }
  const filename = launch.source_filename || launch.gmail_batch_context?.selected_attachment_filename || "Prepared source";
  return {
    kind: "prepared",
    status: "ready",
    filename,
    sourceType: inferSourceType(filename || launch.source_path),
    pageCount: coercePositiveInt(launch.page_count),
    sourcePath: launch.source_path || "",
    message: "Prepared source is staged and ready to start.",
  };
}

function currentSourceCardState() {
  return {
    ...blankSourceCardState(),
    ...(translationState.sourceCard || {}),
  };
}

function setSourceCardState(value) {
  translationState.sourceCard = {
    ...blankSourceCardState(),
    ...(value || {}),
  };
}

function currentSourceUploadState() {
  return {
    ...blankSourceUploadState(),
    ...(translationState.sourceUpload || {}),
  };
}

function setSourceUploadState(value) {
  translationState.sourceUpload = {
    ...blankSourceUploadState(),
    ...(value || {}),
  };
}

function clearSourceUploadState() {
  translationState.sourceUpload = blankSourceUploadState();
}

function setSourcePathValue(value) {
  setFieldValue("translation-source-path", value ?? "");
  const pathNode = qs("translation-source-path-summary");
  if (pathNode) {
    pathNode.textContent = String(value || "").trim() || "No source staged yet.";
  }
}

function currentManualSourceFile() {
  return translationState.manualSourceFile || qs("translation-source-file")?.files?.[0] || null;
}

function normalizeSourceTypeLabel(sourceType) {
  const normalized = String(sourceType || "").trim().toLowerCase();
  if (normalized === "pdf") {
    return "PDF";
  }
  if (normalized === "image") {
    return "Image";
  }
  return "PDF or image";
}

function buildSourceCardStateFromJob(job) {
  const jobSourcePath = String(job?.config?.source_path || "").trim();
  const sourceName = jobSourcePath.split(/[\\/]/).pop() || jobSourcePath;
  return {
    kind: job?.config?.gmail_batch_context ? "prepared" : "manual",
    status: "ready",
    filename: sourceName,
    sourceType: inferSourceType(sourceName),
    pageCount: coercePositiveInt(job?.progress?.selected_total),
    sourcePath: jobSourcePath,
    message: isActiveTranslationJobStatus(job?.status)
      ? "This source is attached to the current translation job."
      : "Source is staged for the loaded job.",
  };
}

export function deriveTranslationSourceState({
  job = translationState.currentJob,
  preparedLaunch = currentPreparedTranslationLaunch(),
  sourceCard = currentSourceCardState(),
  sourceUpload = currentSourceUploadState(),
  sourcePathValue = fieldValue("translation-source-path"),
  uploadedSourcePath = translationState.uploadedSourcePath,
  currentGmailBatchContext = translationState.currentGmailBatchContext,
} = {}) {
  const normalizedCard = {
    ...blankSourceCardState(),
    ...(sourceCard || {}),
  };
  const normalizedUpload = {
    ...blankSourceUploadState(),
    ...(sourceUpload || {}),
  };
  const normalizedPreparedLaunch = normalizePreparedTranslationLaunch(preparedLaunch);
  const normalizedGmailContext = normalizeGmailBatchContext(currentGmailBatchContext);
  const jobSourcePath = String(job?.config?.source_path || "").trim();
  const preparedSourcePath = String(normalizedPreparedLaunch?.source_path || "").trim();
  const activeSourcePath = String(
    normalizedCard.sourcePath
    || (normalizedCard.kind === "manual" ? uploadedSourcePath : "")
    || sourcePathValue
    || "",
  ).trim();
  const sourceType = normalizedCard.sourceType
    || inferSourceType(normalizedCard.filename || activeSourcePath || preparedSourcePath || jobSourcePath);
  const fromGmail = Boolean(
    normalizedPreparedLaunch?.gmail_batch_context
    || normalizedGmailContext
    || job?.config?.gmail_batch_context,
  );
  const jobActive = isActiveTranslationJobStatus(job?.status);

  if (normalizedUpload.pending) {
    return {
      status: "manual-uploading",
      ready: false,
      filename: normalizedUpload.filename || normalizedCard.filename || "Document upload",
      sourceType: normalizedUpload.sourceType || sourceType,
      pageCount: null,
      sourcePath: "",
      fromGmail,
      replacingPrepared: Boolean(normalizedUpload.replacingPrepared),
      message: normalizedUpload.replacingPrepared
        ? "Checking the replacement document..."
        : "Uploading the document and checking it...",
    };
  }

  if (jobActive && jobSourcePath) {
    const jobCard = buildSourceCardStateFromJob(job);
    return {
      status: "current-job",
      ready: false,
      filename: jobCard.filename,
      sourceType: jobCard.sourceType,
      pageCount: jobCard.pageCount,
      sourcePath: jobCard.sourcePath,
      fromGmail: Boolean(job?.config?.gmail_batch_context),
      replacingPrepared: false,
      message: "This source is attached to the current translation job.",
    };
  }

  if (normalizedCard.kind === "manual" && normalizedCard.status === "error") {
    return {
      status: "manual-error",
      ready: false,
      filename: normalizedCard.filename,
      sourceType: normalizedCard.sourceType || sourceType,
      pageCount: normalizedCard.pageCount,
      sourcePath: "",
      fromGmail: false,
      replacingPrepared: false,
      message: normalizedCard.message || "The document could not be staged. Choose another file to continue.",
    };
  }

  if (normalizedCard.kind === "manual" && normalizedCard.status === "ready" && activeSourcePath) {
    return {
      status: "manual-ready",
      ready: true,
      filename: normalizedCard.filename || activeSourcePath.split(/[\\/]/).pop() || "",
      sourceType: normalizedCard.sourceType || sourceType,
      pageCount: normalizedCard.pageCount,
      sourcePath: activeSourcePath,
      fromGmail: false,
      replacingPrepared: false,
      message: normalizedCard.message || "The document is staged and ready.",
    };
  }

  if (normalizedPreparedLaunch && preparedSourcePath) {
    const preparedCard = buildPreparedSourceCardState(normalizedPreparedLaunch);
    return {
      status: "prepared-ready",
      ready: true,
      filename: preparedCard.filename,
      sourceType: preparedCard.sourceType || sourceType,
      pageCount: preparedCard.pageCount,
      sourcePath: preparedSourcePath,
      fromGmail: Boolean(normalizedPreparedLaunch.gmail_batch_context || normalizedGmailContext),
      replacingPrepared: false,
      message: preparedCard.message || "Prepared source is staged and ready to start.",
    };
  }

  if (normalizedCard.kind === "prepared" && normalizedCard.status === "ready" && activeSourcePath) {
    return {
      status: "prepared-ready",
      ready: true,
      filename: normalizedCard.filename || activeSourcePath.split(/[\\/]/).pop() || "",
      sourceType: normalizedCard.sourceType || sourceType,
      pageCount: normalizedCard.pageCount,
      sourcePath: activeSourcePath,
      fromGmail,
      replacingPrepared: false,
      message: normalizedCard.message || "Prepared source is staged and ready to start.",
    };
  }

  return {
    status: "empty",
    ready: false,
    filename: "",
    sourceType: "",
    pageCount: null,
    sourcePath: "",
    fromGmail: false,
    replacingPrepared: false,
    message: "Choose a PDF or image to begin.",
  };
}

function currentSourcePageCount() {
  const sourceState = deriveTranslationSourceState();
  if (sourceState.pageCount !== null) {
    return sourceState.pageCount;
  }
  return currentPreparedTranslationLaunch()?.page_count ?? null;
}

function hasReadyTranslationSource() {
  return Boolean(deriveTranslationSourceState().ready);
}

function hasManualSourceSelection() {
  return deriveTranslationSourceState().status === "manual-ready";
}

export function deriveTranslationActionState(
  job = translationState.currentJob,
  {
    sourceState = deriveTranslationSourceState({ job }),
  } = {},
) {
  const activeJob = isActiveTranslationJobStatus(job?.status);
  const jobId = String(job?.job_id || translationState.currentJobId || "").trim();
  const canStart = sourceState.ready && !activeJob;
  let helperText = "Choose a PDF or image to enable Start Translate.";
  if (sourceState.status === "manual-uploading") {
    helperText = sourceState.replacingPrepared
      ? "Checking the replacement document..."
      : "Checking the document before translation starts...";
  } else if (activeJob) {
    helperText = "A translation run is already in progress. Cancel it or wait for it to finish before starting another one.";
  } else if (sourceState.status === "prepared-ready") {
    helperText = sourceState.fromGmail
      ? "Gmail attachment is prepared. Review settings, then start translation."
      : "The prepared document is ready. Confirm the language and output folder, then start translation.";
  } else if (sourceState.status === "manual-ready") {
    helperText = "The document is ready. Confirm the language and output folder, then start translation.";
  } else if (sourceState.status === "manual-error") {
    helperText = sourceState.message || "The document could not be staged. Choose another file to continue.";
  }
  return {
    sourceState: sourceState.status,
    helperText,
    startEnabled: canStart,
    analyzeEnabled: canStart,
    cancelEnabled: Boolean(jobId && job?.actions?.cancel),
    resumeEnabled: Boolean(jobId && job?.actions?.resume),
    rebuildEnabled: Boolean(jobId && job?.actions?.rebuild),
  };
}

function renderTranslationSourceCard() {
  const card = qs("translation-source-card");
  if (!card) {
    return;
  }
  const title = qs("translation-source-card-title");
  const copy = qs("translation-source-card-copy");
  const filename = qs("translation-source-filename");
  const sourceType = qs("translation-source-type");
  const pages = qs("translation-source-pages");
  const target = qs("translation-source-target");
  const defaultTarget = qs("translation-source-default-target");
  const stageStatus = qs("translation-source-stage-status");
  const hint = qs("translation-source-card-hint");
  const chip = qs("translation-source-card-chip");
  const browseButton = qs("translation-source-browse");
  const clearButton = qs("translation-source-clear");
  const sourceState = deriveTranslationSourceState();
  const isPrepared = sourceState.status === "prepared-ready";
  const isUploading = sourceState.status === "manual-uploading";
  const isError = sourceState.status === "manual-error";
  const isCurrentJob = sourceState.status === "current-job";
  const ready = sourceState.ready;
  card.dataset.state = sourceState.status || "empty";

  if (title) {
    title.textContent = isPrepared && sourceState.fromGmail
      ? "Gmail attachment is prepared"
      : sourceState.filename || (isPrepared ? "Prepared source" : "Choose a PDF or image");
  }
  if (copy) {
    if (isUploading) {
      copy.textContent = sourceState.replacingPrepared
        ? "Checking the replacement document before it replaces the prepared attachment..."
        : "Uploading the file and checking the page count...";
    } else if (isCurrentJob) {
      copy.textContent = "This source is attached to the current translation job. Progress will update below while the run is active.";
    } else if (isPrepared) {
      copy.textContent = sourceState.fromGmail
        ? "Review settings, then start translation. Choosing a local file will replace the prepared Gmail attachment for the next run."
        : "This document is already staged. Choosing a local file will replace it for the next run.";
    } else if (ready) {
      copy.textContent = "The document is staged and ready. Confirm the language and output folder, then start translation.";
    } else if (isError) {
      copy.textContent = sourceState.message || "The file could not be staged. Choose another document to try again.";
    } else {
      copy.textContent = "Drag and drop it here, or choose it from your computer.";
    }
  }
  if (filename) {
    filename.textContent = sourceState.filename || "No file selected yet.";
  }
  if (sourceType) {
    sourceType.textContent = normalizeSourceTypeLabel(sourceState.sourceType || (isPrepared ? "pdf" : ""));
  }
  if (pages) {
    pages.textContent = sourceState.pageCount ?? "--";
  }
  if (target) {
    const launch = currentPreparedTranslationLaunch();
    const gmailTarget = String(launch?.target_lang || launch?.gmail_batch_context?.selected_target_lang || "").trim().toUpperCase();
    const selectedTarget = String(fieldValue("translation-target-lang") || "").trim().toUpperCase();
    target.textContent = isPrepared && sourceState.fromGmail && gmailTarget
      ? `Current Gmail job target: ${gmailTarget}`
      : `Target language: ${selectedTarget || defaultTranslationTargetLang() || "EN"}`;
  }
  if (defaultTarget) {
    const launch = currentPreparedTranslationLaunch();
    const gmailTarget = String(launch?.target_lang || launch?.gmail_batch_context?.selected_target_lang || "").trim().toUpperCase();
    const fallbackTarget = defaultTranslationTargetLang();
    defaultTarget.textContent = isPrepared && sourceState.fromGmail && fallbackTarget && fallbackTarget !== gmailTarget
      ? `Default target for new jobs: ${fallbackTarget}`
      : "Using the current target language for this run.";
  }
  if (stageStatus) {
    if (isUploading) {
      stageStatus.textContent = sourceState.replacingPrepared
        ? "Checking the replacement document..."
        : "Uploading and checking the file...";
    } else if (isCurrentJob) {
      stageStatus.textContent = "Current job is using this source.";
    } else if (isPrepared) {
      stageStatus.textContent = sourceState.fromGmail ? "Ready from Gmail." : "Prepared and ready.";
    } else if (ready) {
      stageStatus.textContent = "Uploaded and ready.";
    } else if (isError) {
      stageStatus.textContent = sourceState.message || "Upload failed.";
    } else {
      stageStatus.textContent = "Choose a file to begin.";
    }
  }
  if (hint) {
    if (isCurrentJob) {
      hint.textContent = "Load another source only when you are ready to prepare the next run.";
    } else if (ready && isPrepared) {
      hint.textContent = sourceState.fromGmail
        ? "The Gmail attachment stays staged until you explicitly choose a new local file."
        : "The prepared document stays staged until you explicitly choose a new local file.";
    } else if (ready) {
      hint.textContent = "The same local file will not be uploaded again unless it changes.";
    } else {
      hint.textContent = "PDF and common image files are supported.";
    }
  }
  if (chip) {
    const chipState = isError
      ? { text: "Needs attention", tone: "bad" }
      : isUploading
        ? { text: "Uploading", tone: "info" }
        : isCurrentJob
          ? { text: "In progress", tone: "info" }
        : isPrepared
          ? { text: "Ready", tone: "info" }
          : ready
            ? { text: "Ready", tone: "ok" }
            : { text: "", tone: "" };
    chip.textContent = chipState.text;
    chip.className = chipState.text ? `status-chip ${chipState.tone}` : "status-chip info hidden";
    chip.classList.toggle("hidden", chipState.text === "");
  }
  if (browseButton) {
    browseButton.textContent = ready ? "Choose another document" : "Choose document";
    browseButton.disabled = isUploading;
  }
  if (clearButton) {
    clearButton.classList.toggle("hidden", !hasManualSourceSelection());
  }
}

function browserDefaultOutputDir() {
  return String(appState.bootstrap?.normalized_payload?.settings_summary?.default_outdir || "").trim();
}

function defaultTranslationTargetLang() {
  return String(
    appState.bootstrap?.normalized_payload?.settings_summary?.default_lang
    || appState.bootstrap?.normalized_payload?.settings_summary?.target_lang
    || fieldValue("translation-target-lang")
    || "EN",
  ).trim().toUpperCase();
}

function renderTranslationOutputSummary() {
  const label = qs("translation-output-summary-label");
  const copy = qs("translation-output-summary-copy");
  const path = qs("translation-output-summary-path");
  if (!label || !copy || !path) {
    return;
  }
  const outputDir = fieldValue("translation-output-dir");
  const defaultOutdir = browserDefaultOutputDir();
  if (outputDir && defaultOutdir && outputDir === defaultOutdir) {
    label.textContent = "Using default output folder";
    copy.textContent = "Translated files will be saved in the default folder for this workspace.";
    path.textContent = outputDir;
    return;
  }
  if (outputDir) {
    label.textContent = "Save output in";
    copy.textContent = defaultOutdir
      ? "Using the folder shown below. Open Change folder/path if you want to save somewhere else."
      : "Using the folder shown below.";
    path.textContent = outputDir;
    return;
  }
  label.textContent = "Choose an output folder";
  copy.textContent = "Open Change folder/path to decide where translated files should be saved.";
  path.textContent = "No output folder selected yet.";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function blankNumericMismatchWarning({ checked = false } = {}) {
  return {
    visible: false,
    checked,
    message: NUMERIC_MISMATCH_WARNING_MESSAGE,
    lines: [],
    pages: [],
  };
}

function cleanNumericSample(value) {
  return String(value ?? "")
    .trim()
    .replace(/^['"`]+|['"`]+$/g, "")
    .trim();
}

function normalizeNumericSamples(value) {
  if (Array.isArray(value)) {
    return value.map(cleanNumericSample).filter(Boolean).slice(0, 6);
  }
  const text = String(value ?? "").trim();
  if (!text) {
    return [];
  }
  const trimmed = text.replace(/^\[/, "").replace(/\]$/, "");
  const quoted = Array.from(trimmed.matchAll(/["']([^"']+)["']/g))
    .map((match) => cleanNumericSample(match[1]))
    .filter(Boolean);
  if (quoted.length) {
    return quoted.slice(0, 6);
  }
  const separator = trimmed.includes(";") ? /\s*;\s*/ : /,\s+/;
  const parts = (trimmed.includes(";") || /,\s+/.test(trimmed))
    ? trimmed.split(separator)
    : [trimmed];
  return parts
    .map(cleanNumericSample)
    .filter(Boolean)
    .slice(0, 6);
}

function normalizeNumericWarningRows(rows = []) {
  const normalizedRows = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") {
      continue;
    }
    const samples = normalizeNumericSamples(row.samples ?? row.numeric_missing_sample ?? row.missing);
    const count = coercePositiveInt(row.count ?? row.numeric_mismatches_count) ?? samples.length;
    if (count <= 0 && samples.length === 0) {
      continue;
    }
    const page = coercePositiveInt(row.page ?? row.page_index ?? row.page_number);
    normalizedRows.push({
      page,
      count,
      samples,
    });
  }
  const lines = normalizedRows.map((row) => {
    const prefix = row.page ? `Page ${row.page}: ` : "";
    if (row.samples.length) {
      return `${prefix}${row.samples.join("; ")}`;
    }
    const countText = row.count === 1 ? "1 number needs review" : `${row.count} numbers need review`;
    return `${prefix}${countText}`;
  });
  return {
    visible: lines.length > 0,
    checked: true,
    message: NUMERIC_MISMATCH_WARNING_MESSAGE,
    lines,
    pages: normalizedRows,
  };
}

function collectNumericWarningRows(value, rows = [], seen = new Set(), depth = 0) {
  if (!value || typeof value !== "object" || seen.has(value) || depth > 7) {
    return rows;
  }
  seen.add(value);
  if (Array.isArray(value)) {
    value.forEach((item) => collectNumericWarningRows(item, rows, seen, depth + 1));
    return rows;
  }
  const samples = normalizeNumericSamples(value.numeric_missing_sample);
  const count = coercePositiveInt(value.numeric_mismatches_count) ?? 0;
  if (count > 0 || samples.length > 0) {
    rows.push({
      page: value.page_index ?? value.page ?? value.page_number,
      count,
      samples,
    });
  }
  for (const [key, nested] of Object.entries(value)) {
    if (
      key === "save_seed"
      || key === "logs"
      || key.endsWith("_path")
      || key.endsWith("_dir")
    ) {
      continue;
    }
    collectNumericWarningRows(nested, rows, seen, depth + 1);
  }
  return rows;
}

function extractNumericMismatchWarningFromText(text) {
  const source = String(text || "");
  if (!source) {
    return blankNumericMismatchWarning();
  }
  const rows = [];
  const lines = source.split(/\r?\n/);
  let inSamples = false;
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (/^#{1,6}\s+Numeric Mismatch Samples/i.test(line)) {
      inSamples = true;
      continue;
    }
    if (inSamples && /^#{1,6}\s+/.test(line)) {
      break;
    }
    const match = line.match(/^-?\s*Page\s+(?<page>\d+)\s*:\s*(?:missing\s*)?(?<samples>\[[^\]]*\]|.+)$/i);
    if (!match?.groups) {
      continue;
    }
    rows.push({
      page: match.groups.page,
      samples: normalizeNumericSamples(match.groups.samples),
    });
  }
  return normalizeNumericWarningRows(rows);
}

export function deriveNumericMismatchWarning(job = translationState.currentJob, extra = null) {
  const rows = collectNumericWarningRows(extra || job || []);
  const structured = normalizeNumericWarningRows(rows);
  if (structured.visible) {
    return structured;
  }
  const previewText = String(extra?.preview || extra?.normalized_payload?.preview || job?.result?.run_report_preview || "").trim();
  const previewWarning = extractNumericMismatchWarningFromText(previewText);
  if (previewWarning.visible) {
    return previewWarning;
  }
  const jobId = String(job?.job_id || "").trim();
  if (jobId && translationState.numericMismatchWarningsByJobId[jobId]) {
    return translationState.numericMismatchWarningsByJobId[jobId];
  }
  return blankNumericMismatchWarning();
}

export function renderNumericMismatchWarningInto(containerOrId, warning = blankNumericMismatchWarning()) {
  const container = typeof containerOrId === "string" ? qs(containerOrId) : containerOrId;
  if (!container) {
    return;
  }
  const normalized = warning?.visible ? warning : blankNumericMismatchWarning();
  container.classList.toggle("hidden", !normalized.visible);
  if (!normalized.visible) {
    container.textContent = "";
    return;
  }
  const detailLines = normalized.lines?.length ? `\n${normalized.lines.join("\n")}` : "";
  container.textContent = `${normalized.message}${detailLines}`;
  container.setAttribute("role", "note");
}

function currentNumericMismatchWarning(job = translationState.currentJob) {
  return deriveNumericMismatchWarning(job);
}

function renderTranslationNumericMismatchWarnings(job = translationState.currentJob) {
  const warning = currentNumericMismatchWarning(job);
  renderNumericMismatchWarningInto("translation-numeric-warning", warning);
  renderNumericMismatchWarningInto("translation-completion-numeric-warning", warning);
  renderNumericMismatchWarningInto("translation-save-numeric-warning", warning);
  renderNumericMismatchWarningInto("translation-gmail-step-numeric-warning", warning);
}

function cacheNumericMismatchWarning(jobId, warning) {
  const normalizedJobId = String(jobId || "").trim();
  if (!normalizedJobId) {
    return;
  }
  translationState.numericMismatchWarningsByJobId[normalizedJobId] = warning?.checked
    ? warning
    : { ...blankNumericMismatchWarning({ checked: true }), ...(warning || {}) };
}

function looksLikeRawTechnicalStateText(value) {
  const text = String(value || "").trim();
  return Boolean(
    text.startsWith("{")
    || text.startsWith("[")
    || /"job_id"|"normalized_payload"|"progress"|"result"/.test(text)
    || /^translation job state/i.test(text),
  );
}

function friendlyTranslationTaskText({ job, progress = {}, result = {}, fallback = "" } = {}) {
  const raw = String(progress.status_text || job?.status_text || fallback || "").trim();
  if (raw && !looksLikeRawTechnicalStateText(raw)) {
    return raw;
  }
  const completedPages = coercePositiveInt(result.completed_pages) ?? coercePositiveInt(progress.selected_index) ?? 0;
  if (job?.status === "completed") {
    return `Completed pages: ${completedPages}. Latest technical state is available in details.`;
  }
  if (["queued", "running", "cancel_requested"].includes(String(job?.status || ""))) {
    return completedPages > 0
      ? `Translating... Completed pages: ${completedPages}. Latest technical state is available in details.`
      : "Translating... Latest technical state is available in details.";
  }
  return "Latest technical state is available in details.";
}

function formatDiagnosticValue(value) {
  if (value instanceof Error) {
    const payload = { status: "failed", message: value.message || "Unexpected error." };
    if (value.status) {
      payload.http_status = value.status;
    }
    if (value.payload && Object.keys(value.payload).length) {
      payload.payload = value.payload;
    }
    return JSON.stringify(payload, null, 2);
  }
  if (typeof value === "string") {
    return value;
  }
  if (value === undefined || value === null) {
    return "";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function setDiagnostics(slot, value, { hint = "", open = false } = {}) {
  const pre = qs(`${slot}-diagnostics`);
  if (pre) {
    pre.textContent = formatDiagnosticValue(value);
  }
  const hintNode = qs(`${slot}-hint`);
  if (hintNode && hint) {
    hintNode.textContent = hint;
  }
  const details = qs(`${slot}-details`);
  if (details) {
    details.open = Boolean(open);
    if (open) {
      details.dataset.reveal = "true";
    } else {
      delete details.dataset.reveal;
    }
  }
}

function setPanelStatus(slot, tone, message) {
  const panel = qs(`${slot}-status`);
  if (!panel) {
    return;
  }
  panel.textContent = message;
  if (tone) {
    panel.dataset.tone = tone;
  } else {
    delete panel.dataset.tone;
  }
}

function setBusy(buttonIds, busy, busyLabels = {}) {
  for (const id of buttonIds) {
    const button = qs(id);
    if (!button) {
      continue;
    }
    if (!button.dataset.defaultLabel) {
      button.dataset.defaultLabel = button.textContent;
    }
    button.disabled = busy;
    button.setAttribute("aria-busy", busy ? "true" : "false");
    button.textContent = busy ? busyLabels[id] || button.dataset.defaultLabel : button.dataset.defaultLabel;
  }
}

async function runWithBusy(buttonIds, busyLabels, action) {
  if (buttonIds.some((id) => qs(id)?.disabled)) {
    return;
  }
  setBusy(buttonIds, true, busyLabels);
  try {
    return await action();
  } finally {
    setBusy(buttonIds, false);
  }
}

function stopPolling() {
  if (translationState.pollTimer !== null) {
    window.clearTimeout(translationState.pollTimer);
    translationState.pollTimer = null;
  }
}

function stopArabicReviewPolling() {
  if (translationState.arabicReviewPollTimer !== null) {
    window.clearTimeout(translationState.arabicReviewPollTimer);
    translationState.arabicReviewPollTimer = null;
  }
}

function setArabicReviewState(value, { forceNotify = false } = {}) {
  translationState.arabicReview = normalizeArabicReviewState(value);
  syncTranslationCompletionSurface();
  notifyTranslationUiStateChanged({ force: forceNotify });
}

function clearArabicReviewState({ forceNotify = false } = {}) {
  stopArabicReviewPolling();
  setArabicReviewState(blankArabicReviewState(), { forceNotify });
}

function sourceFileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
}

function syncNativeSourceInputFile(file) {
  const input = qs("translation-source-file");
  if (!input) {
    return;
  }
  if (!file) {
    input.value = "";
    try {
      input.files = [];
    } catch {
      // Ignore environments that do not allow programmatic FileList mutation.
    }
    return;
  }
  try {
    if (typeof DataTransfer === "function") {
      const transfer = new DataTransfer();
      transfer.items.add(file);
      input.files = transfer.files;
    }
  } catch {
    // Ignore environments that do not allow programmatic FileList mutation.
  }
}

function clearManualSourceSelection() {
  syncNativeSourceInputFile(null);
  translationState.manualSourceFile = null;
}

function clearUploadedSourceCache() {
  translationState.uploadedSourcePath = "";
  translationState.uploadedSourceKey = "";
}

function clearManualStagedSource() {
  clearManualSourceSelection();
  setSourcePathValue("");
  clearSourceUploadState();
  setSourceCardState(blankSourceCardState());
}

function isPdfFile(file) {
  if (!file) {
    return false;
  }
  return String(file.type || "").trim().toLowerCase() === "application/pdf"
    || String(file.name || "").trim().toLowerCase().endsWith(".pdf");
}

function sourceUploadToken() {
  return currentSourceUploadState().token + 1;
}

function isActiveSourceUploadTransaction(transaction) {
  if (!transaction) {
    return false;
  }
  const activeUpload = currentSourceUploadState();
  return Boolean(
    activeUpload.pending
      && Number(activeUpload.token) === Number(transaction.token)
      && String(activeUpload.fileKey || "") === String(transaction.fileKey || ""),
  );
}

function sourceUploadIsPending() {
  return Boolean(currentSourceUploadState().pending);
}

function beginSourceUploadTransaction(file) {
  const preparedLaunch = currentPreparedTranslationLaunch();
  const gmailBatchContext = normalizeGmailBatchContext(translationState.currentGmailBatchContext);
  const token = sourceUploadToken();
  setSourceUploadState({
    token,
    pending: true,
    fileKey: sourceFileKey(file),
    filename: file.name,
    sourceType: isPdfFile(file) ? "pdf" : "image",
    replacingPrepared: Boolean(preparedLaunch?.source_path),
    preservedPreparedLaunch: preparedLaunch ? normalizePreparedTranslationLaunch(preparedLaunch) : null,
    preservedGmailBatchContext: gmailBatchContext,
    preservedSourcePath: fieldValue("translation-source-path"),
  });
  return currentSourceUploadState();
}

function commitManualSourceState({
  file,
  sourcePath,
  sourceKey,
  filename = file?.name || "",
  sourceType = isPdfFile(file) ? "pdf" : "image",
  pageCount = null,
  message = "Source upload complete.",
} = {}) {
  clearSourceUploadState();
  clearPreparedTranslationLaunch();
  translationState.currentGmailBatchContext = null;
  translationState.manualSourceFile = file || null;
  syncNativeSourceInputFile(file || null);
  translationState.uploadedSourceKey = sourceKey || translationState.uploadedSourceKey || "";
  translationState.uploadedSourcePath = String(sourcePath || "").trim();
  setSourcePathValue(translationState.uploadedSourcePath);
  setSourceCardState({
    kind: "manual",
    status: "ready",
    filename,
    sourceType,
    pageCount: coercePositiveInt(pageCount),
    sourcePath: translationState.uploadedSourcePath,
    message,
  });
}

function restorePreparedSourceAfterFailedReplacement(transaction) {
  const restoredPrepared = normalizePreparedTranslationLaunch(transaction?.preservedPreparedLaunch);
  if (!restoredPrepared?.source_path) {
    return false;
  }
  translationState.currentPreparedLaunch = restoredPrepared;
  translationState.currentGmailBatchContext = normalizeGmailBatchContext(
    transaction?.preservedGmailBatchContext || restoredPrepared.gmail_batch_context,
  );
  setSourcePathValue(transaction?.preservedSourcePath || restoredPrepared.source_path || "");
  setSourceCardState(buildPreparedSourceCardState(restoredPrepared));
  return true;
}

function rollbackSourceUploadTransaction(file, error, transaction = currentSourceUploadState()) {
  clearSourceUploadState();
  clearManualSourceSelection();
  if (transaction?.replacingPrepared && restorePreparedSourceAfterFailedReplacement(transaction)) {
    return;
  }
  setSourcePathValue("");
  setSourceCardState({
    kind: "manual",
    status: "error",
    filename: file?.name || "",
    sourceType: isPdfFile(file) ? "pdf" : "image",
    pageCount: null,
    sourcePath: "",
    message: error?.message || "The file could not be staged.",
  });
}

async function stageTranslationSourceFile(file) {
  if (!file) {
    clearManualStagedSource();
    return "";
  }
  translationState.manualSourceFile = file;
  syncNativeSourceInputFile(file);
  const key = sourceFileKey(file);
  if (translationState.uploadedSourceKey === key && translationState.uploadedSourcePath) {
    commitManualSourceState({
      file,
      sourcePath: translationState.uploadedSourcePath,
      sourceKey: key,
      filename: file.name,
      sourceType: isPdfFile(file) ? "pdf" : "image",
      pageCount: currentSourceCardState().pageCount,
      message: "The document is staged and ready.",
    });
    renderTranslationSourceCard();
    syncTranslationPrimaryActionState();
    renderTranslationRunStatus(translationState.currentJob);
    if (!translationState.currentJob) {
      renderTranslationResultCard(null);
    }
    return translationState.uploadedSourcePath;
  }
  const transaction = beginSourceUploadTransaction(file);
  setSourceCardState({
    kind: "manual",
    status: "uploading",
    filename: file.name,
    sourceType: transaction.sourceType,
    pageCount: null,
    sourcePath: "",
    message: transaction.replacingPrepared
      ? "Checking the replacement document..."
      : "Uploading the file and checking the page count...",
  });
  renderTranslationSourceCard();
  syncTranslationPrimaryActionState();
  renderTranslationRunStatus(translationState.currentJob);
  try {
    const form = new FormData();
    form.append("file", file);
    const payload = await fetchJson("/api/translation/upload-source", appState, {
      method: "POST",
      body: form,
    });
    if (!isActiveSourceUploadTransaction(transaction)) {
      return "";
    }
    let resolvedPageCount = payload.normalized_payload.page_count ?? "?";
    let sourceUploadHint = "Source upload complete.";
    const resolvedSourcePath = String(payload.normalized_payload.source_path || "").trim();
    if (isPdfFile(file) && resolvedSourcePath) {
      const browserBundle = await ensureBrowserPdfBundleFromFile({
        appState,
        sourcePath: resolvedSourcePath,
        file,
      });
      if (!isActiveSourceUploadTransaction(transaction)) {
        return "";
      }
      resolvedPageCount = browserBundle.page_count ?? resolvedPageCount;
      sourceUploadHint = "Source upload complete. Browser PDF staging is ready.";
    }
    if (!isActiveSourceUploadTransaction(transaction)) {
      return "";
    }
    commitManualSourceState({
      file,
      sourcePath: resolvedSourcePath,
      sourceKey: key,
      filename: payload.normalized_payload.source_filename || file.name,
      sourceType: payload.normalized_payload.source_type || transaction.sourceType,
      pageCount: resolvedPageCount,
      message: sourceUploadHint,
    });
    setDiagnostics("translation", payload, {
      hint: sourceUploadHint,
      open: false,
    });
    renderTranslationSourceCard();
    syncTranslationPrimaryActionState();
    renderTranslationRunStatus(translationState.currentJob);
    if (!translationState.currentJob) {
      renderTranslationResultCard(null);
    }
    return translationState.uploadedSourcePath;
  } catch (error) {
    if (!isActiveSourceUploadTransaction(transaction)) {
      return "";
    }
    rollbackSourceUploadTransaction(file, error, transaction);
    throw error;
  }
}

async function ensureUploadedSource() {
  const sourceState = deriveTranslationSourceState();
  if (sourceState.status === "manual-ready" || sourceState.status === "prepared-ready") {
    return sourceState.sourcePath || "";
  }
  return "";
}

function collectTranslationSetupValues() {
  const values = {
    source_path: fieldValue("translation-source-path"),
    output_dir: fieldValue("translation-output-dir"),
    target_lang: fieldValue("translation-target-lang"),
    effort: fieldValue("translation-effort"),
    effort_policy: fieldValue("translation-effort-policy"),
    image_mode: fieldValue("translation-image-mode"),
    ocr_mode: fieldValue("translation-ocr-mode"),
    ocr_engine: fieldValue("translation-ocr-engine"),
    start_page: fieldValue("translation-start-page"),
    end_page: fieldValue("translation-end-page"),
    max_pages: fieldValue("translation-max-pages"),
    workers: fieldValue("translation-workers"),
    resume: qs("translation-resume").checked,
    page_breaks: qs("translation-page-breaks").checked,
    keep_intermediates: qs("translation-keep-intermediates").checked,
    context_file: fieldValue("translation-context-file"),
    glossary_file: fieldValue("translation-glossary-file"),
    context_text: qs("translation-context-text").value.trim(),
  };
  if (translationState.currentGmailBatchContext) {
    values.gmail_batch_context = { ...translationState.currentGmailBatchContext };
  }
  return values;
}

function collectTranslationSaveValues() {
  return {
    translation_date: fieldValue("translation-date"),
    case_number: fieldValue("translation-case-number"),
    court_email: fieldValue("translation-court-email"),
    case_entity: fieldValue("translation-case-entity"),
    case_city: fieldValue("translation-case-city"),
    run_id: fieldValue("translation-run-id"),
    lang: fieldValue("translation-target-lang-readonly"),
    target_lang: fieldValue("translation-target-lang-readonly"),
    pages: fieldValue("translation-pages"),
    word_count: fieldValue("translation-word-count"),
    total_tokens: fieldValue("translation-total-tokens"),
    rate_per_word: fieldValue("translation-rate-per-word"),
    expected_total: fieldValue("translation-expected-total"),
    amount_paid: fieldValue("translation-amount-paid"),
    api_cost: fieldValue("translation-api-cost"),
    estimated_api_cost: fieldValue("translation-estimated-api-cost"),
    quality_risk_score: fieldValue("translation-quality-risk-score"),
    profit: fieldValue("translation-profit"),
  };
}

function summarizeTranslationLogFlags(logs = []) {
  const imagePages = new Set();
  const retryPages = new Set();
  const failedPages = new Set();
  for (const entry of Array.isArray(logs) ? logs : []) {
    const line = String(entry || "").trim();
    const flagMatch = PAGE_FLAG_LOG_RE.exec(line);
    if (flagMatch) {
      const page = coercePositiveInt(flagMatch.groups?.page);
      if (page) {
        if (flagMatch.groups?.image === "True") {
          imagePages.add(page);
        }
        if (flagMatch.groups?.retry === "True") {
          retryPages.add(page);
        }
      }
    }
    const statusMatch = PAGE_STATUS_LOG_RE.exec(line);
    if (statusMatch?.groups?.status?.toLowerCase() === "failed") {
      const page = coercePositiveInt(statusMatch.groups.page);
      if (page) {
        failedPages.add(page);
      }
    }
  }
  return { imagePages, retryPages, failedPages };
}

function syncTranslationPrimaryActionState() {
  const startButton = qs("translation-start");
  const analyzeButton = qs("translation-analyze");
  const cancelButton = qs("translation-cancel");
  const resumeButton = qs("translation-resume-btn");
  const rebuildButton = qs("translation-rebuild");
  const helper = qs("translation-action-helper");
  const actionState = deriveTranslationActionState();
  if (helper) {
    helper.textContent = actionState.helperText;
  }
  if (startButton) {
    startButton.disabled = !actionState.startEnabled;
  }
  if (analyzeButton) {
    analyzeButton.disabled = !actionState.analyzeEnabled;
  }
  if (cancelButton) {
    cancelButton.disabled = !actionState.cancelEnabled;
  }
  if (resumeButton) {
    resumeButton.disabled = !actionState.resumeEnabled;
  }
  if (rebuildButton) {
    rebuildButton.disabled = !actionState.rebuildEnabled;
  }
}

export function deriveTranslationRunStatusView(
  job,
  {
    preparedLaunch = currentPreparedTranslationLaunch(),
    sourceState = deriveTranslationSourceState({ job, preparedLaunch }),
    sourceReady = sourceState.ready,
    sourcePageCount = sourceState.pageCount ?? currentSourcePageCount(),
  } = {},
) {
  const progress = job && typeof job.progress === "object" ? job.progress : {};
  const result = job && typeof job.result === "object" ? job.result : {};
  const logFlags = summarizeTranslationLogFlags(job?.logs || []);
  const completedPages = coercePositiveInt(result.completed_pages) ?? 0;
  const selectedIndex = coercePositiveInt(progress.selected_index) ?? completedPages;
  const selectedTotal = coercePositiveInt(progress.selected_total) ?? sourcePageCount ?? preparedLaunch?.page_count ?? null;
  const realPage = coercePositiveInt(progress.real_page);
  const flaggedCount = coercePositiveInt(result.review_queue_count) ?? 0;
  const failedPage = coercePositiveInt(result.failed_page);
  const errorCount = Math.max(logFlags.failedPages.size, failedPage ? 1 : 0, job?.status === "failed" ? 1 : 0);
  const percentValue = job
    ? (job.status === "completed"
      ? 100
      : selectedTotal
        ? Math.max(0, Math.min(100, Math.round((selectedIndex / selectedTotal) * 100)))
        : 0)
    : 0;
  let tone = "info";
  let chipText = "Ready";
  let currentTask = "Choose a source file to begin.";
  if (!job) {
    if (sourceState.status === "manual-uploading") {
      currentTask = sourceState.replacingPrepared
        ? "Checking the replacement document..."
        : "Checking the document before translation starts.";
      chipText = "Checking";
      tone = "info";
    } else if (sourceState.status === "manual-error") {
      currentTask = sourceState.message || "Choose another source file to continue.";
      chipText = "Needs attention";
      tone = "bad";
    } else if (preparedLaunch) {
      currentTask = "Prepared Gmail attachment is ready to start.";
      chipText = "Ready";
      tone = "info";
    } else if (sourceState.status === "current-job") {
      currentTask = "Current translation job is using this source.";
      chipText = "Running";
      tone = "info";
    } else if (sourceReady) {
      currentTask = "Source file is ready. Confirm the language and folder, then start translation.";
      chipText = "Ready";
      tone = "ok";
    } else {
      chipText = "Waiting";
      tone = "info";
    }
  } else {
    currentTask = friendlyTranslationTaskText({
      job,
      progress,
      result,
      fallback: "Translation job state is available.",
    });
    if (job.status === "completed") {
      chipText = "Complete";
      tone = "ok";
    } else if (job.status === "failed") {
      chipText = "Needs attention";
      tone = "bad";
    } else if (job.status === "cancel_requested" || job.status === "cancelled") {
      chipText = "Stopping";
      tone = "warn";
    } else {
      chipText = "Running";
      tone = "info";
    }
  }
  const imageRetryParts = [];
  if (logFlags.imagePages.size > 0) {
    imageRetryParts.push(`Images ${logFlags.imagePages.size}`);
  }
  if (logFlags.retryPages.size > 0) {
    imageRetryParts.push(`Retries ${logFlags.retryPages.size}`);
  }
  if (Boolean(progress.image_used) && realPage) {
    imageRetryParts.unshift(`Image on page ${realPage}`);
  }
  if (Boolean(progress.retry_used) && realPage) {
    imageRetryParts.unshift(`Retry on page ${realPage}`);
  }
  const alertParts = [];
  if (flaggedCount > 0) {
    alertParts.push(`Flagged ${flaggedCount}`);
  }
  if (errorCount > 0) {
    alertParts.push(`Errors ${errorCount}`);
  }
  return {
    percentValue,
    percentText: `${percentValue}%`,
    chipText,
    chipTone: tone,
    currentTask,
    pagesText: `${selectedIndex} / ${selectedTotal ?? "--"}`,
    currentPageText: realPage
      ? `Page ${realPage}`
      : job?.status === "completed"
        ? "Completed"
        : preparedLaunch?.start_page && preparedLaunch.start_page > 1
          ? `Start at page ${preparedLaunch.start_page}`
          : "Not started",
    imageRetryText: imageRetryParts.join(" | ") || "No image or retry markers yet.",
    alertsText: alertParts.join(" | ") || "No flagged pages or errors.",
  };
}

function renderTranslationRunStatus(job = translationState.currentJob) {
  const percentNode = qs("translation-progress-percent");
  const chipNode = qs("translation-run-status-chip");
  const trackNode = qs("translation-progress-track");
  const barNode = qs("translation-progress-bar");
  const taskNode = qs("translation-current-task");
  const pagesNode = qs("translation-run-pages");
  const currentPageNode = qs("translation-run-current-page");
  const imageRetryNode = qs("translation-run-image-retry");
  const alertsNode = qs("translation-run-alerts");
  if (!percentNode || !chipNode || !trackNode || !barNode || !taskNode || !pagesNode || !currentPageNode || !imageRetryNode || !alertsNode) {
    return;
  }
  const view = deriveTranslationRunStatusView(job);
  percentNode.textContent = view.percentText;
  chipNode.textContent = view.chipText;
  chipNode.className = `status-chip ${view.chipTone}`;
  trackNode.setAttribute("aria-valuenow", String(view.percentValue));
  barNode.style.width = `${view.percentValue}%`;
  taskNode.textContent = view.currentTask;
  pagesNode.textContent = view.pagesText;
  currentPageNode.textContent = view.currentPageText;
  imageRetryNode.textContent = view.imageRetryText;
  alertsNode.textContent = view.alertsText;
}

function clearDownloadLink(id) {
  const node = qs(id);
  if (!node) {
    return;
  }
  node.classList.add("hidden");
  node.removeAttribute("href");
}

function setDownloadLink(id, href) {
  const node = qs(id);
  if (!node) {
    return;
  }
  if (href) {
    node.href = href;
    node.classList.remove("hidden");
  } else {
    clearDownloadLink(id);
  }
}

function translationRunReportHref(job = translationState.currentJob) {
  if (!job?.actions?.download_run_report || !job?.job_id) {
    return "";
  }
  return `/api/translation/jobs/${job.job_id}/artifact/run_report?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}`;
}

function blankSaveSeed() {
  const today = new Date().toISOString().slice(0, 10);
  return {
    completed_at: `${today}T00:00:00`,
    translation_date: today,
    job_type: "Translation",
    case_number: "",
    court_email: "",
    case_entity: "",
    case_city: "",
    service_entity: "",
    service_city: "",
    service_date: today,
    lang: "",
    run_id: "",
    target_lang: fieldValue("translation-target-lang") || "EN",
    pages: 0,
    word_count: 0,
    total_tokens: "",
    rate_per_word: 0,
    expected_total: 0,
    amount_paid: 0,
    api_cost: 0,
    estimated_api_cost: "",
    quality_risk_score: "",
    profit: 0,
    pdf_path: null,
    output_docx: null,
    partial_docx: null,
  };
}

function dispatchNewJobTask(task) {
  window.dispatchEvent(new CustomEvent("legalpdf:set-new-job-task", { detail: { task } }));
}

function collapseTranslationCompletionSections() {
  qs("translation-save-metrics-section")?.removeAttribute("open");
  qs("translation-save-amounts-section")?.removeAttribute("open");
}

function hasTranslationSaveSeed() {
  return hasTranslationSaveSeedData(translationState.currentSeed || {}, {
    currentRowId: translationState.currentRowId,
    job: translationState.currentJob,
  });
}

function hasTranslationCompletionSurface() {
  return hasTranslationSaveSeed() || Boolean(translationState.currentJob?.status === "completed");
}

function currentTranslationCompletionKey() {
  if (translationState.currentJob?.status === "completed" && translationState.currentJobId) {
    return `job:${translationState.currentJobId}:${translationState.currentJob?.job_kind || "translate"}`;
  }
  if (translationState.currentRowId) {
    return `row:${translationState.currentRowId}`;
  }
  const seed = translationState.currentSeed || {};
  if (seed.run_id || seed.case_number) {
    return `seed:${seed.run_id || ""}:${seed.case_number || ""}`;
  }
  return "";
}

function currentTranslationSeed() {
  return translationState.currentSeed || {};
}

function currentCompletedTranslationJobRequiresArabicReview() {
  const job = translationState.currentJob;
  if (!job || job.job_kind !== "translate" || job.status !== "completed") {
    return false;
  }
  const seed = job.result?.save_seed || {};
  const targetLang = String(seed.target_lang || job.config?.target_lang || "").trim().toUpperCase();
  const outputDocx = String(seed.output_docx || "").trim();
  return targetLang === "AR" && Boolean(outputDocx);
}

function currentArabicReviewIsBlocking() {
  const review = currentArabicReviewState();
  return Boolean(review.required && !review.resolved);
}

function setTranslationCompletionDrawerOpen(open) {
  const backdrop = qs("translation-completion-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  translationState.completionDrawerOpen = Boolean(open) && hasTranslationCompletionSurface();
  backdrop.classList.toggle("hidden", !translationState.completionDrawerOpen);
  backdrop.setAttribute("aria-hidden", translationState.completionDrawerOpen ? "false" : "true");
  document.body.dataset.translationCompletionDrawer = translationState.completionDrawerOpen ? "open" : "closed";
  notifyTranslationUiStateChanged();
}

export function openTranslationCompletionDrawer({ auto = false } = {}) {
  if (!hasTranslationCompletionSurface()) {
    return;
  }
  setTranslationCompletionDrawerOpen(true);
  if (auto) {
    translationState.lastAutoOpenedCompletionKey = currentTranslationCompletionKey();
  }
}

export function closeTranslationCompletionDrawer() {
  setTranslationCompletionDrawerOpen(false);
}

export function getTranslationUiSnapshot() {
  const review = currentArabicReviewState();
  const recovery = deriveTranslationRecoveryState(translationState.currentJob);
  const sourceCard = currentSourceCardState();
  const sourceState = deriveTranslationSourceState();
  const actionState = deriveTranslationActionState(translationState.currentJob, { sourceState });
  const numericMismatchWarning = currentNumericMismatchWarning();
  return {
    currentJobKind: translationState.currentJob?.job_kind || "",
    currentJobStatus: translationState.currentJob?.status || "",
    currentJobId: translationState.currentJobId || "",
    currentJobHasSaveSeed: Boolean(translationState.currentJob?.result?.save_seed),
    hasCompletionSurface: hasTranslationCompletionSurface(),
    completionDrawerOpen: translationState.completionDrawerOpen,
    currentRowId: translationState.currentRowId || null,
    currentJobFailed: Boolean(translationState.currentJob?.status === "failed"),
    currentJobFailureReason: recovery.failureReason || "",
    currentJobFailurePage: recovery.failurePage ?? null,
    currentJobRecoveryRecommendedAction: recovery.recommendedAction || "",
    currentJobRecoveryRequired: Boolean(recovery.visible),
    requiresArabicReview: Boolean(review.required),
    arabicReviewResolved: !review.required || Boolean(review.resolved),
    arabicReviewState: review.status || "",
    arabicReviewMessage: review.message || "",
    arabicReviewCompletionKey: review.completion_key || currentTranslationCompletionKey(),
    runtimeJobs: translationState.runtimeJobs.map((job) => ({
      ...job,
      config: {
        ...job.config,
        gmail_batch_context: normalizeGmailBatchContext(job.config?.gmail_batch_context),
      },
    })),
    currentGmailBatchContext: normalizeGmailBatchContext(translationState.currentGmailBatchContext),
    numericMismatchWarning,
    hasPreparedLaunch: hasPreparedTranslationLaunch(),
    preparedLaunchSourcePath: currentPreparedTranslationLaunch()?.source_path || "",
    preparedLaunchAttachmentId: currentPreparedTranslationLaunch()?.gmail_batch_context?.attachment_id || "",
    preparedLaunchTargetLang: currentPreparedTranslationLaunch()?.target_lang || currentPreparedTranslationLaunch()?.gmail_batch_context?.selected_target_lang || "",
    defaultTargetLang: defaultTranslationTargetLang(),
    sourceReady: sourceState.ready,
    sourceState: sourceState.status,
    sourceCardKind: sourceCard.kind,
    sourceCardStatus: sourceCard.status,
    sourceCardFilename: sourceCard.filename,
    sourceCardPageCount: sourceCard.pageCount,
    sourceCardSourcePath: sourceCard.sourcePath || fieldValue("translation-source-path"),
    sourcePathValue: fieldValue("translation-source-path"),
    sourceUploadPending: currentSourceUploadState().pending,
    sourceUploadReplacingPrepared: currentSourceUploadState().replacingPrepared,
    manualSourceFileName: currentManualSourceFile()?.name || "",
    outputDirValue: fieldValue("translation-output-dir"),
    translationStartDisabled: Boolean(qs("translation-start")?.disabled),
    translationAnalyzeDisabled: Boolean(qs("translation-analyze")?.disabled),
    translationCancelDisabled: Boolean(qs("translation-cancel")?.disabled),
    translationResumeDisabled: Boolean(qs("translation-resume-btn")?.disabled),
    translationRebuildDisabled: Boolean(qs("translation-rebuild")?.disabled),
    translationActionHelper: qs("translation-action-helper")?.textContent?.trim?.() ?? "",
    derivedActionState: actionState,
    runStatusTask: qs("translation-current-task")?.textContent?.trim?.() ?? "",
  };
}

export async function startTranslationLaunch(launch, { auto = false } = {}) {
  if (!launch || typeof launch !== "object") {
    return;
  }
  applyTranslationLaunch(launch);
  setActiveView("new-job");
  setPanelStatus("translation", "", auto ? "Starting Gmail translation run..." : "Starting translation run...");
  await handleTranslate();
  closeTranslationCompletionDrawer();
}

function completionButtonLabel() {
  return deriveTranslationCompletionPresentation({
    job: translationState.currentJob,
    saveSeed: currentTranslationSeed(),
    currentRowId: translationState.currentRowId,
    arabicReview: currentArabicReviewState(),
    gmailBatchContext: translationState.currentGmailBatchContext,
  }).completionButtonLabel;
}

function completionSurfaceSummary() {
  return deriveTranslationCompletionPresentation({
    job: translationState.currentJob,
    saveSeed: currentTranslationSeed(),
    currentRowId: translationState.currentRowId,
    arabicReview: currentArabicReviewState(),
    gmailBatchContext: translationState.currentGmailBatchContext,
  }).drawerStatus;
}

function renderTranslationCompletionResultCard() {
  const container = qs("translation-completion-result");
  if (!container) {
    return;
  }
  const presentation = deriveTranslationCompletionPresentation({
    job: translationState.currentJob,
    saveSeed: currentTranslationSeed(),
    currentRowId: translationState.currentRowId,
    arabicReview: currentArabicReviewState(),
    gmailBatchContext: translationState.currentGmailBatchContext,
  });
  if (!presentation.available) {
    container.classList.add("empty-state");
    container.textContent = presentation.resultCopy;
    return;
  }
  const detailLines = presentation.resultDetailLines
    .filter(Boolean)
    .map((line) => escapeHtml(line))
    .join("<br>");
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(presentation.resultTitle)}</strong>
        <p>${escapeHtml(presentation.resultCopy)}${detailLines ? `<br><br>${detailLines}` : ""}</p>
      </div>
      <span class="status-chip ${escapeHtml(presentation.resultChipTone)}">${escapeHtml(presentation.resultChipLabel)}</span>
    </div>
  `;
}

function renderArabicReviewCard() {
  const card = qs("translation-arabic-review-card");
  const title = qs("translation-arabic-review-title");
  const copy = qs("translation-arabic-review-copy");
  const chip = qs("translation-arabic-review-chip");
  const docxLabel = qs("translation-arabic-review-docx-label");
  const docxPath = qs("translation-arabic-review-docx-path");
  const openButton = qs("translation-arabic-review-open");
  const continueNowButton = qs("translation-arabic-review-continue-now");
  const continueWithoutChangesButton = qs("translation-arabic-review-continue-without-changes");
  if (!card || !title || !copy || !chip || !docxLabel || !docxPath || !openButton || !continueNowButton || !continueWithoutChangesButton) {
    return;
  }
  const review = currentArabicReviewState();
  const presentation = deriveTranslationCompletionPresentation({
    job: translationState.currentJob,
    saveSeed: currentTranslationSeed(),
    currentRowId: translationState.currentRowId,
    arabicReview: review,
    gmailBatchContext: translationState.currentGmailBatchContext,
  });
  const show = Boolean(review.required || currentCompletedTranslationJobRequiresArabicReview());
  card.classList.toggle("hidden", !show);
  if (!show) {
    return;
  }
  docxLabel.textContent = presentation.arabicReview.docxLabel;
  title.textContent = presentation.arabicReview.title;
  copy.textContent = presentation.arabicReview.copy;
  docxPath.textContent = review.docx_path || String(currentTranslationSeed().output_docx || "").trim() || presentation.arabicReview.unavailableText;
  chip.textContent = presentation.arabicReview.chipLabel;
  chip.className = `status-chip ${presentation.arabicReview.chipTone}`;
  openButton.textContent = presentation.arabicReview.openLabel;
  continueNowButton.textContent = presentation.arabicReview.continueNowLabel;
  continueWithoutChangesButton.textContent = presentation.arabicReview.continueWithoutChangesLabel;
  openButton.disabled = !Boolean(review.docx_path || currentTranslationSeed().output_docx);
  continueNowButton.disabled = Boolean(review.required && review.resolved);
  continueWithoutChangesButton.disabled = Boolean(review.required && review.resolved);
}

function syncTranslationCompletionSurface() {
  const available = hasTranslationCompletionSurface();
  const openButton = qs("translation-open-completion");
  const formShell = qs("translation-completion-form-shell");
  const emptyShell = qs("translation-completion-empty");
  const statusNode = qs("translation-completion-status");
  const emptyTitleNode = qs("translation-completion-empty-title");
  const emptyCopyNode = qs("translation-completion-empty-copy");
  const saveTitleNode = qs("translation-save-form-title");
  const saveStatusNode = qs("translation-save-status");
  const reviewExportButton = qs("translation-review-export");
  const runReportButton = qs("translation-generate-report");
  const saveButton = qs("translation-save-row");
  const review = currentArabicReviewState();
  const presentation = deriveTranslationCompletionPresentation({
    job: translationState.currentJob,
    saveSeed: currentTranslationSeed(),
    currentRowId: translationState.currentRowId,
    arabicReview: review,
    gmailBatchContext: translationState.currentGmailBatchContext,
  });
  if (openButton) {
    openButton.classList.toggle("hidden", !available);
    openButton.textContent = completionButtonLabel();
  }
  if (emptyTitleNode) {
    emptyTitleNode.textContent = presentation.emptyTitle;
  }
  if (emptyCopyNode) {
    emptyCopyNode.textContent = presentation.emptyCopy;
  }
  if (saveTitleNode) {
    saveTitleNode.textContent = presentation.saveTitle;
  }
  if (saveStatusNode) {
    saveStatusNode.textContent = presentation.saveStatus;
  }
  if (!translationState.currentJob) {
    if (reviewExportButton) {
      reviewExportButton.disabled = true;
    }
    if (runReportButton) {
      runReportButton.disabled = true;
      runReportButton.classList.add("hidden");
    }
    clearDownloadLink("translation-download-report");
    clearDownloadLink("translation-download-docx");
    clearDownloadLink("translation-download-partial");
    clearDownloadLink("translation-download-summary");
    clearDownloadLink("translation-download-analyze");
  }
  if (!available) {
    formShell?.classList.add("hidden");
    emptyShell?.classList.add("hidden");
    if (statusNode) {
      statusNode.textContent = presentation.drawerStatus;
    }
    renderTranslationCompletionResultCard();
    renderArabicReviewCard();
    closeTranslationCompletionDrawer();
    return;
  }
  if (statusNode) {
    statusNode.textContent = presentation.drawerStatus;
  }
  const hasSaveSurface = hasTranslationSaveSeed();
  formShell?.classList.toggle("hidden", !hasSaveSurface);
  emptyShell?.classList.toggle("hidden", hasSaveSurface);
  if (saveButton) {
    saveButton.textContent = presentation.saveButtonLabel;
    saveButton.disabled = !hasSaveSurface || currentArabicReviewIsBlocking();
  }
  if (hasSaveSurface && !translationState.currentRowId && review.required) {
    setPanelStatus(
      "translation-save",
      review.resolved ? "" : "warn",
      presentation.saveStatus,
    );
  }
  renderTranslationCompletionResultCard();
  renderArabicReviewCard();
}

function maybeAutoOpenTranslationCompletion(job) {
  if (!job || job.status !== "completed") {
    return;
  }
  const key = currentTranslationCompletionKey();
  if (!key || translationState.lastAutoOpenedCompletionKey === key) {
    return;
  }
  openTranslationCompletionDrawer({ auto: true });
}

function translationFailureContext(job) {
  return job?.result?.failure_context || {};
}

function isAuthenticationFailure(job) {
  return String(job?.result?.error || "").trim() === "authentication_failure";
}

function currentTranslationRunDir(job = translationState.currentJob) {
  return String(
    job?.result?.artifacts?.run_dir
    || job?.artifacts?.run_dir
    || job?.artifacts?.run_dir_text
    || "",
  ).trim();
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

function translationStatusSummary(job) {
  if (!job) {
    return "";
  }
  if (job.job_kind === "analyze") {
    return job.status === "completed"
      ? "Analysis complete. Review the report, then start a full translation when you are ready."
      : job.status_text || "Analyze job is running.";
  }
  if (job.job_kind === "rebuild") {
    return job.status === "completed"
      ? "DOCX rebuild complete. Review the translated DOCX and download the refreshed file here."
      : job.status_text || "DOCX rebuild is running.";
  }
  if (job.status === "completed") {
    return "Translation complete. Review the translated document, then save the case record if everything looks right.";
  }
  if (job.status === "cancel_requested") {
    return "Cancellation requested. Waiting for the current page task to stop cleanly.";
  }
  if (job.status === "failed" && isAuthenticationFailure(job)) {
    return "OpenAI authentication failed. Open Browser Settings, save a valid translation key, run Test Translation Auth, then start the translation again.";
  }
  const recovery = deriveTranslationRecoveryState(job);
  if (recovery.visible) {
    return recovery.statusMessage;
  }
  return job.status_text || "Translation job is running.";
}

function applyTranslationSeed(seed, { rowId = null } = {}) {
  dispatchNewJobTask("translation");
  const resolved = seed || blankSaveSeed();
  translationState.currentSeed = resolved;
  translationState.currentRowId = rowId;
  setFieldValue("translation-row-id", rowId ?? "");
  setFieldValue("translation-date", resolved.translation_date || "");
  setFieldValue("translation-case-number", resolved.case_number || "");
  setFieldValue("translation-court-email", resolved.court_email || "");
  setFieldValue("translation-case-entity", resolved.case_entity || "");
  setFieldValue("translation-case-city", resolved.case_city || "");
  setFieldValue("translation-run-id", resolved.run_id || "");
  setFieldValue("translation-target-lang-readonly", resolved.target_lang || resolved.lang || "");
  setFieldValue("translation-pages", resolved.pages ?? "");
  setFieldValue("translation-word-count", resolved.word_count ?? "");
  setFieldValue("translation-total-tokens", resolved.total_tokens ?? "");
  setFieldValue("translation-rate-per-word", resolved.rate_per_word ?? "");
  setFieldValue("translation-expected-total", resolved.expected_total ?? "");
  setFieldValue("translation-amount-paid", resolved.amount_paid ?? "");
  setFieldValue("translation-api-cost", resolved.api_cost ?? "");
  setFieldValue("translation-estimated-api-cost", resolved.estimated_api_cost ?? "");
  setFieldValue("translation-quality-risk-score", resolved.quality_risk_score ?? "");
  setFieldValue("translation-profit", resolved.profit ?? "");
  collapseTranslationCompletionSections();
  syncTranslationCompletionSurface();
}

function currentArabicReviewRequestPayload(extra = {}) {
  const review = currentArabicReviewState();
  const completionKey = currentTranslationCompletionKey() || review.completion_key || "";
  return {
    job_id: translationState.currentJobId || review.job_id || "",
    completion_key: completionKey,
    ...extra,
  };
}

function scheduleArabicReviewPoll(delayMs = 500) {
  stopArabicReviewPolling();
  translationState.arabicReviewPollTimer = window.setTimeout(() => {
    refreshArabicReviewState().catch((error) => {
      setPanelStatus("translation-save", "bad", error.message || "Arabic DOCX review refresh failed.");
      setDiagnostics("translation-save", error, {
        hint: error.message || "Arabic DOCX review refresh failed.",
        open: true,
      });
    });
  }, Math.max(100, Number(delayMs) || 500));
}

async function refreshArabicReviewState({ allowRestore = false } = {}) {
  stopArabicReviewPolling();
  const reviewTargetKnown = currentCompletedTranslationJobRequiresArabicReview()
    || Boolean(currentArabicReviewState().completion_key)
    || allowRestore;
  if (!reviewTargetKnown) {
    clearArabicReviewState();
    return currentArabicReviewState();
  }
  const request = currentArabicReviewRequestPayload();
  const params = new URLSearchParams();
  if (request.job_id) {
    params.set("job_id", request.job_id);
  }
  if (request.completion_key) {
    params.set("completion_key", request.completion_key);
  }
  const url = params.size
    ? `/api/translation/arabic-review/state?${params.toString()}`
    : "/api/translation/arabic-review/state";
  const payload = await fetchJson(url, appState);
  const review = normalizeArabicReviewState(payload.normalized_payload?.arabic_review);
  if (allowRestore && !translationState.currentJobId && review.required && !review.resolved && review.job_id) {
    const restored = await fetchJson(`/api/translation/jobs/${review.job_id}`, appState);
    renderTranslationJob(restored.normalized_payload?.job || null);
    return currentArabicReviewState();
  }
  setArabicReviewState(review);
  if (review.required && !review.resolved) {
    if (review.auto_open_pending && review.job_id && review.job_id === translationState.currentJobId) {
      try {
        await openArabicReviewInWord({ auto: true });
        return currentArabicReviewState();
      } catch (error) {
        setPanelStatus("translation-save", "warn", error.message || "Arabic DOCX review open failed.");
        setDiagnostics("translation-save", error, {
          hint: error.message || "Arabic DOCX review open failed.",
          open: true,
        });
      }
    }
    scheduleArabicReviewPoll(review.poll_interval_ms || 500);
  }
  return review;
}

async function openArabicReviewInWord({ auto = false } = {}) {
  const payload = await fetchJson("/api/translation/arabic-review/open", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentArabicReviewRequestPayload()),
  });
  const review = normalizeArabicReviewState(payload.normalized_payload?.arabic_review);
  setArabicReviewState(review);
  setDiagnostics("translation-save", payload, {
    hint: review.message || (auto ? "Arabic DOCX review opened automatically." : "Arabic DOCX review opened in Word."),
    open: false,
  });
  if (review.required && !review.resolved) {
    scheduleArabicReviewPoll(review.poll_interval_ms || 500);
  }
  return review;
}

async function continueArabicReview(continuation) {
  const payload = await fetchJson("/api/translation/arabic-review/continue", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(currentArabicReviewRequestPayload({ continuation })),
  });
  const review = normalizeArabicReviewState(payload.normalized_payload?.arabic_review);
  setArabicReviewState(review);
  setDiagnostics("translation-save", payload, {
    hint: review.message || "Arabic DOCX review continuation recorded.",
    open: false,
  });
  return review;
}

async function restorePendingArabicReview() {
  try {
    await refreshArabicReviewState({ allowRestore: true });
  } catch (error) {
    clearArabicReviewState();
    setPanelStatus("translation-save", "bad", error.message || "Arabic DOCX review restore failed.");
    setDiagnostics("translation-save", error, {
      hint: error.message || "Arabic DOCX review restore failed.",
      open: true,
    });
  }
}

async function deleteTranslationJobLogRow(rowId) {
  const presentation = deriveRecentWorkPresentation({ jobType: "Translation" });
  if (!window.confirm(presentation.deleteConfirmMessage)) {
    return;
  }
  const payload = await fetchJson("/api/joblog/delete", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ row_id: rowId }),
  });
  if (Number(translationState.currentRowId) === Number(rowId)) {
    applyTranslationSeed(blankSaveSeed(), { rowId: null });
  }
  setPanelStatus("recent-jobs", "ok", presentation.deleteStatus);
  setPanelStatus("translation-save", "ok", presentation.deleteStatus);
  setDiagnostics("translation-save", payload, {
    hint: `Deleted translation record #${rowId}.`,
    open: false,
  });
  window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
}

function applyTranslationDefaults(defaults) {
  setFieldValue("translation-output-dir", defaults.output_dir || browserDefaultOutputDir() || "");
  setFieldValue("translation-target-lang", defaults.target_lang || "EN");
  setFieldValue("translation-effort", defaults.effort || "high");
  setFieldValue("translation-effort-policy", defaults.effort_policy || "adaptive");
  setFieldValue("translation-image-mode", defaults.image_mode || "off");
  setFieldValue("translation-ocr-mode", defaults.ocr_mode || "auto");
  setFieldValue("translation-ocr-engine", defaults.ocr_engine || "local_then_api");
  setFieldValue("translation-start-page", defaults.start_page ?? 1);
  setFieldValue("translation-end-page", defaults.end_page ?? "");
  setFieldValue("translation-max-pages", defaults.max_pages ?? "");
  setFieldValue("translation-workers", defaults.workers ?? 3);
  setCheckbox("translation-resume", defaults.resume !== false);
  setCheckbox("translation-page-breaks", defaults.page_breaks !== false);
  setCheckbox("translation-keep-intermediates", defaults.keep_intermediates !== false);
  setFieldValue("translation-context-file", defaults.context_file || "");
  setFieldValue("translation-glossary-file", defaults.glossary_file || "");
  setFieldValue("translation-context-text", defaults.context_text || "");
  renderTranslationOutputSummary();
}

export function applyTranslationLaunch(launch) {
  if (!launch || typeof launch !== "object") {
    return;
  }
  const preparedLaunch = normalizePreparedTranslationLaunch(launch);
  if (!preparedLaunch) {
    return;
  }
  const gmailBatchContext = normalizeGmailBatchContext(preparedLaunch.gmail_batch_context);
  const workflowSource = String(preparedLaunch.workflow_source || "").trim();
  dispatchNewJobTask("translation");
  if (shouldResetWorkspaceForPreparedGmailLaunch(preparedLaunch, { gmailBatchContext, workflowSource })) {
    resetTranslationWorkspaceForPreparedLaunch();
  }
  translationState.currentPreparedLaunch = preparedLaunch;
  clearSourceUploadState();
  if (gmailBatchContext || workflowSource === "gmail_intake") {
    clearManualSourceSelection();
  }
  translationState.currentGmailBatchContext = gmailBatchContext;
  setSourcePathValue(preparedLaunch.source_path || "");
  if (preparedLaunch.output_dir) {
    setFieldValue("translation-output-dir", preparedLaunch.output_dir);
  }
  if (preparedLaunch.target_lang) {
    setFieldValue("translation-target-lang", preparedLaunch.target_lang);
  }
  if (preparedLaunch.image_mode) {
    setFieldValue("translation-image-mode", preparedLaunch.image_mode);
  }
  if (preparedLaunch.ocr_mode) {
    setFieldValue("translation-ocr-mode", preparedLaunch.ocr_mode);
  }
  if (preparedLaunch.ocr_engine) {
    setFieldValue("translation-ocr-engine", preparedLaunch.ocr_engine);
  }
  if (typeof preparedLaunch.resume === "boolean") {
    setCheckbox("translation-resume", preparedLaunch.resume);
  }
  if (typeof preparedLaunch.keep_intermediates === "boolean") {
    setCheckbox("translation-keep-intermediates", preparedLaunch.keep_intermediates);
  }
  if (preparedLaunch.start_page !== undefined && preparedLaunch.start_page !== null) {
    setFieldValue("translation-start-page", preparedLaunch.start_page);
  }
  setSourceCardState(buildPreparedSourceCardState(preparedLaunch));
  renderTranslationSourceCard();
  renderTranslationOutputSummary();
  syncTranslationPrimaryActionState();
  renderTranslationRunStatus(null);
  setDiagnostics(
    "translation",
    {
      status: "prepared",
      action: "gmail_prepare_loaded",
      source_path: String(preparedLaunch.source_path || "").trim(),
      target_lang: String(preparedLaunch.target_lang || "").trim().toUpperCase(),
      start_page: preparedLaunch.start_page ?? 1,
      gmail_batch_context: gmailBatchContext,
    },
    {
      hint: "Gmail attachment loaded into the translation workspace. Review the settings, then start the translation run.",
      open: false,
    },
  );
  renderTranslationPreparedState();
}

export function maybeRestorePreparedTranslationLaunch(launch, { activeView = appState.activeView } = {}) {
  const normalizedLaunch = normalizePreparedTranslationLaunch(launch);
  if (!normalizedLaunch || String(activeView || "").trim() !== "new-job") {
    return false;
  }
  if (
    translationState.currentJob
    || translationState.currentJobId
    || translationState.currentRowId
    || hasTranslationCompletionSurface()
    || hasPreparedTranslationLaunch()
    || translationState.runtimeJobs.length > 0
  ) {
    return false;
  }
  applyTranslationLaunch(normalizedLaunch);
  return true;
}

export function resetTranslationForGmailRedo(launch) {
  stopPolling();
  stopArabicReviewPolling();
  resetTranslationWorkspaceForPreparedLaunch();
  applyTranslationLaunch(launch);
  setActiveView("new-job");
  setPanelStatus("translation", "", "Current Gmail attachment reloaded for a new run. Review the settings, then start translation again.");
  setDiagnostics(
    "translation",
    {
      status: "ready",
      action: "gmail_redo_prepared",
      source_path: String(launch?.source_path || "").trim(),
      attachment_id: String(launch?.gmail_batch_context?.attachment_id || "").trim(),
    },
    {
      hint: "Redo is prepared. The Gmail batch stayed intact; only the translation workspace was reset for this attachment.",
      open: false,
    },
  );
  notifyTranslationUiStateChanged({ force: true });
}

export function getCurrentTranslationJobId() {
  return translationState.currentJobId || "";
}

export function collectCurrentTranslationSaveValues() {
  return collectTranslationSaveValues();
}

function renderTranslationPreparedState() {
  if (!hasPreparedTranslationLaunch()) {
    return false;
  }
  setSourceCardState(buildPreparedSourceCardState(currentPreparedTranslationLaunch()));
  renderTranslationSourceCard();
  renderTranslationOutputSummary();
  renderTranslationResultCard(null);
  renderTranslationNumericMismatchWarnings(null);
  renderTranslationRunStatus(null);
  syncTranslationPrimaryActionState();
  setPanelStatus("translation", "", preparedTranslationStatusSummary());
  setDiagnostics("translation-job", {
    status: "prepared",
    message: "The Gmail attachment is staged in the translation workspace and ready to start.",
    source_path: currentPreparedTranslationLaunch()?.source_path || "",
    gmail_batch_context: normalizeGmailBatchContext(translationState.currentGmailBatchContext),
  }, {
    hint: "No translation job has started yet. This Gmail attachment is prepared and ready for Start Translate.",
    open: false,
  });
  setDownloadLink("translation-download-report", "");
  setDownloadLink("translation-download-docx", "");
  setDownloadLink("translation-download-partial", "");
  setDownloadLink("translation-download-summary", "");
  setDownloadLink("translation-download-analyze", "");
  const reportButton = qs("translation-generate-report");
  if (reportButton) {
    reportButton.disabled = true;
    reportButton.classList.add("hidden");
  }
  const reviewExport = qs("translation-review-export");
  if (reviewExport) {
    reviewExport.disabled = true;
  }
  const cancelButton = qs("translation-cancel");
  if (cancelButton) {
    cancelButton.disabled = true;
  }
  const resumeButton = qs("translation-resume-btn");
  if (resumeButton) {
    resumeButton.disabled = true;
  }
  const rebuildButton = qs("translation-rebuild");
  if (rebuildButton) {
    rebuildButton.disabled = true;
  }
  notifyTranslationUiStateChanged();
  return true;
}

function renderTranslationResultCard(job, { containerId = "translation-result" } = {}) {
  const container = qs(containerId);
  if (!container) {
    return;
  }
  if (!job) {
    const preparedLaunch = currentPreparedTranslationLaunch();
    if (preparedLaunch) {
      container.classList.remove("empty-state");
      container.innerHTML = `
        <div class="result-header">
          <div>
            <strong>Prepared Gmail attachment is ready to start.</strong>
            <p>${preparedTranslationSummaryLines(preparedLaunch).map((line) => escapeHtml(line)).join("<br>")}</p>
            <p>Ready to start. Click Start Translate when you're ready.</p>
          </div>
          <span class="status-chip info">ready</span>
        </div>
      `;
      return;
    }
    if (hasReadyTranslationSource()) {
      container.classList.remove("empty-state");
      container.innerHTML = `
        <div class="result-header">
          <div>
            <strong>Source file is ready.</strong>
            <p>Confirm the language and output folder, then click Start Translate when you're ready.</p>
          </div>
          <span class="status-chip ok">ready</span>
        </div>
      `;
      return;
    }
    container.classList.add("empty-state");
    container.textContent = "Choose a source file to see translation progress and results here.";
    return;
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
  container.classList.remove("empty-state");
  const primaryTitle = String(job.status_text || "").trim();
  const safeTitle = primaryTitle && !looksLikeRawTechnicalStateText(primaryTitle)
    ? primaryTitle
    : job.status === "completed"
      ? "Translation complete."
      : "Translation progress is available.";
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(safeTitle)}</strong>
        <p>${summaryLines.map((line) => escapeHtml(line)).join("<br>")}</p>
      </div>
      <span class="status-chip ${job.status === "completed" ? "ok" : job.status === "failed" ? "bad" : job.status === "cancelled" ? "warn" : "info"}">${escapeHtml(job.status)}</span>
    </div>
  `;
}

function maybeRefreshNumericMismatchWarning(job) {
  const jobId = String(job?.job_id || "").trim();
  if (
    !jobId
    || job?.job_kind !== "translate"
    || job?.status !== "completed"
    || !job?.actions?.download_run_report
    || !currentTranslationRunDir(job)
    || translationState.numericMismatchWarningsByJobId[jobId]?.checked
    || translationState.numericMismatchWarningFetches[jobId]
  ) {
    return;
  }
  translationState.numericMismatchWarningFetches[jobId] = true;
  fetchJson(`/api/translation/jobs/${jobId}/run-report`, appState, {
    method: "POST",
  }).then((payload) => {
    const warning = deriveNumericMismatchWarning(job, payload.normalized_payload || payload);
    cacheNumericMismatchWarning(jobId, warning.visible ? warning : blankNumericMismatchWarning({ checked: true }));
    if (translationState.currentJobId === jobId) {
      const refreshedJob = payload.normalized_payload?.job || translationState.currentJob || job;
      translationState.currentJob = refreshedJob;
      renderTranslationNumericMismatchWarnings(refreshedJob);
      notifyTranslationUiStateChanged({ force: true });
    }
  }).catch(() => {
    cacheNumericMismatchWarning(jobId, blankNumericMismatchWarning({ checked: true }));
  }).finally(() => {
    delete translationState.numericMismatchWarningFetches[jobId];
  });
}

function shouldOpenTranslationJobDiagnostics(job, recovery = deriveTranslationRecoveryState(job)) {
  if (!job) {
    return false;
  }
  if (isAuthenticationFailure(job)) {
    return true;
  }
  if (recovery?.visible) {
    return true;
  }
  return String(job.status || "").trim() === "failed";
}

function renderTranslationJob(job) {
  translationState.currentJob = job || null;
  translationState.currentJobId = job?.job_id || "";
  if (job) {
    clearSourceUploadState();
    clearPreparedTranslationLaunch();
  }
  const jobSourcePath = String(job?.config?.source_path || "").trim();
  if (jobSourcePath) {
    const currentSourcePath = String(deriveTranslationSourceState({ job: null }).sourcePath || "").trim();
    setSourcePathValue(jobSourcePath);
    if (
      isActiveTranslationJobStatus(job?.status)
      || currentSourceCardState().kind === "empty"
      || currentSourcePath !== jobSourcePath
    ) {
      setSourceCardState(buildSourceCardStateFromJob(job));
    }
  }
  if (job?.config?.gmail_batch_context) {
    translationState.currentGmailBatchContext = normalizeGmailBatchContext(job.config.gmail_batch_context);
  } else if (job) {
    translationState.currentGmailBatchContext = null;
  }
  rememberRuntimeJob(job);
  setFieldValue("translation-job-id", translationState.currentJobId);
  const runDir = currentTranslationRunDir(job);
  if (runDir && qs("diagnostics-run-dir")) {
    setFieldValue("diagnostics-run-dir", runDir);
  }
  const recovery = deriveTranslationRecoveryState(job);
  renderTranslationResultCard(job);
  renderTranslationNumericMismatchWarnings(job);
  maybeRefreshNumericMismatchWarning(job);
  const preparedSummary = !job
    ? (preparedTranslationStatusSummary()
      || (hasReadyTranslationSource()
        ? "Source file is ready. Confirm the language and output folder, then start translation."
        : "Choose a source file to begin."))
    : "";
  setPanelStatus(
    "translation",
    job
      ? (job.status === "failed" ? "bad" : job.status === "cancelled" ? "warn" : "")
      : "",
    translationStatusSummary(job) || preparedSummary || "Choose a source file to begin.",
  );
  const diagnosticsHint = isAuthenticationFailure(job)
    ? "OpenAI authentication failed. Open Browser Settings, save a valid translation key, run Test Translation Auth, then start the translation again."
    : recovery.visible
      ? recovery.diagnosticsHint
      : hasPreparedTranslationLaunch()
        ? "No translation job has started yet. This Gmail attachment is prepared and ready for Start Translate."
        : "Latest progress, log tail, review queue, and failure context appear here.";
  setDiagnostics("translation-job", job || (
    hasPreparedTranslationLaunch()
      ? {
        status: "prepared",
        message: "The Gmail attachment is staged in the translation workspace and ready to start.",
        source_path: currentPreparedTranslationLaunch()?.source_path || "",
        gmail_batch_context: normalizeGmailBatchContext(translationState.currentGmailBatchContext),
      }
      : { status: "idle", message: "No translation job loaded." }
  ), {
    hint: diagnosticsHint,
    open: shouldOpenTranslationJobDiagnostics(job, recovery),
  });
  setDownloadLink("translation-download-report", translationRunReportHref(job));
  setDownloadLink("translation-download-docx", job?.actions?.download_output_docx ? `/api/translation/jobs/${job.job_id}/artifact/output_docx?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "");
  setDownloadLink("translation-download-partial", job?.actions?.download_partial_docx ? `/api/translation/jobs/${job.job_id}/artifact/partial_docx?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "");
  setDownloadLink("translation-download-summary", job?.actions?.download_run_summary ? `/api/translation/jobs/${job.job_id}/artifact/run_summary?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "");
  setDownloadLink("translation-download-analyze", job?.actions?.download_analyze_report ? `/api/translation/jobs/${job.job_id}/artifact/analyze_report?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "");
  const reportButton = qs("translation-generate-report");
  if (reportButton) {
    const available = Boolean(job?.job_kind === "translate" && runDir);
    reportButton.disabled = !available;
    reportButton.classList.toggle("hidden", !job);
  }
  qs("translation-review-export").disabled = !job?.actions?.review_export;
  if (job?.result?.save_seed) {
    applyTranslationSeed(job.result.save_seed);
    setPanelStatus(
      "translation-save",
      "",
      deriveTranslationCompletionPresentation({
        job,
        saveSeed: job.result.save_seed,
        currentRowId: translationState.currentRowId,
        arabicReview: currentArabicReviewState(),
        gmailBatchContext: translationState.currentGmailBatchContext,
      }).saveStatus,
    );
  } else if (!job) {
    clearArabicReviewState();
  } else if (!currentCompletedTranslationJobRequiresArabicReview()) {
    clearArabicReviewState();
  }
  syncTranslationCompletionSurface();
  maybeAutoOpenTranslationCompletion(job);
  if (job && ["queued", "running", "cancel_requested"].includes(job.status)) {
    stopPolling();
    translationState.pollTimer = window.setTimeout(pollCurrentJob, 1500);
  } else {
    stopPolling();
  }
  if (currentCompletedTranslationJobRequiresArabicReview()) {
    refreshArabicReviewState().catch((error) => {
      clearArabicReviewState();
      setPanelStatus("translation-save", "bad", error.message || "Arabic DOCX review refresh failed.");
      setDiagnostics("translation-save", error, {
        hint: error.message || "Arabic DOCX review refresh failed.",
        open: true,
      });
    });
  }
  renderTranslationSourceCard();
  renderTranslationOutputSummary();
  renderTranslationRunStatus(job);
  syncTranslationPrimaryActionState();
  notifyTranslationUiStateChanged();
}

export function renderTranslationHistoryInto(container, history, { onOpen, onDelete } = {}) {
  if (!container) {
    return;
  }
  clearNode(container);
  if (!history.length) {
    container.appendChild(createEmptyState(deriveRecentWorkPresentation().translationHistoryEmpty));
    return;
  }
  for (const item of history) {
    const row = item.row || {};
    const presentation = deriveRecentWorkPresentation({ jobType: row.job_type || "Translation" });
    const card = document.createElement("article");
    card.className = "history-item";
    const details = document.createElement("div");
    details.appendChild(createTextElement("strong", row.case_number || "No case number"));
    details.appendChild(createTextElement(
      "p",
      [row.case_entity || "No case entity", row.case_city || "No case city", row.translation_date || "No date"].join(" | "),
    ));
    card.appendChild(details);
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = presentation.translationHistoryOpenLabel;
    button.addEventListener("click", () => onOpen?.(item));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = presentation.translationHistoryDeleteLabel;
    deleteButton.addEventListener("click", () => onDelete?.(item));
    actions.appendChild(button);
    actions.appendChild(deleteButton);
    card.appendChild(actions);
    container.appendChild(card);
  }
}

function renderTranslationHistory(history) {
  const container = qs("translation-history-list");
  if (!container) {
    return;
  }
  renderTranslationHistoryInto(container, history, {
    onOpen: (item) => loadTranslationHistoryItem(item),
    onDelete: async (item) => {
      try {
        await deleteTranslationJobLogRow(item.row?.id);
      } catch (error) {
        setPanelStatus("translation-save", "bad", error.message || "Translation row delete failed.");
        setDiagnostics("translation-save", error, {
          hint: error.message || "Translation row delete failed.",
          open: true,
        });
      }
    },
  });
}

function loadTranslationHistoryItem(item) {
  const row = item?.row || {};
  translationState.currentJob = null;
  translationState.currentJobId = "";
  translationState.currentGmailBatchContext = null;
  clearManualStagedSource();
  clearPreparedTranslationLaunch();
  clearArabicReviewState();
  applyTranslationSeed(item?.seed || blankSaveSeed(), { rowId: row.id || null });
  setActiveView("new-job");
  dispatchNewJobTask("translation");
  document.querySelectorAll(".page-view").forEach((node) => {
    node.classList.toggle("hidden", node.dataset.view !== "new-job");
  });
  document.querySelectorAll(".nav-button").forEach((buttonNode) => {
    buttonNode.classList.toggle("active", buttonNode.dataset.view === "new-job");
  });
  if (row.id) {
    setPanelStatus("translation-save", "ok", "Saved case record loaded. Review the fields below and save any edits.");
    setDiagnostics("translation-save", item, { hint: `Loaded case record #${row.id}.`, open: false });
  }
  renderTranslationSourceCard();
  renderTranslationOutputSummary();
  renderTranslationResultCard(null);
  renderTranslationRunStatus(null);
  syncTranslationPrimaryActionState();
  openTranslationCompletionDrawer();
}

export function renderTranslationJobsInto(container, jobs, { onOpen, onResume, onRebuild } = {}) {
  if (!container) {
    return;
  }
  clearNode(container);
  if (!jobs.length) {
    container.appendChild(createEmptyState(deriveRecentWorkPresentation().translationRunsEmpty));
    return;
  }
  for (const job of jobs) {
    const presentation = deriveRecentWorkPresentation({ translationRunCount: jobs.length, job });
    const card = document.createElement("article");
    card.className = "history-item";
    const details = document.createElement("div");
    const title = createTextElement("strong", presentation.translationRunTitle);
    setNodeTitle(title, String(job?.config?.source_path || "").trim());
    details.appendChild(title);
    details.appendChild(createTextElement("p", presentation.translationRunSubtitle));
    const actions = document.createElement("div");
    actions.className = "history-meta";
    const loadButton = document.createElement("button");
    loadButton.type = "button";
    loadButton.textContent = presentation.translationRunOpenLabel;
    loadButton.addEventListener("click", () => onOpen?.(job));
    actions.appendChild(loadButton);
    if (job.actions?.resume) {
      const resume = document.createElement("button");
      resume.type = "button";
      resume.textContent = presentation.translationRunResumeLabel;
      resume.addEventListener("click", () => onResume?.(job));
      actions.appendChild(resume);
    }
    if (job.actions?.rebuild) {
      const rebuild = document.createElement("button");
      rebuild.type = "button";
      rebuild.textContent = presentation.translationRunRebuildLabel;
      rebuild.addEventListener("click", () => onRebuild?.(job));
      actions.appendChild(rebuild);
    }
    card.appendChild(details);
    card.appendChild(actions);
    container.appendChild(card);
  }
}

function renderTranslationJobs(jobs) {
  const container = qs("translation-jobs-list");
  translationState.runtimeJobs = Array.isArray(jobs)
    ? jobs.map((job) => summarizeRuntimeJob(job)).filter(Boolean)
    : [];
  notifyTranslationUiStateChanged();
  if (!container) {
    return;
  }
  if (!jobs.length) {
    const presentation = deriveRecentWorkPresentation();
    setPanelStatus("translation-jobs", "", presentation.translationRunsEmpty);
  } else {
    setPanelStatus("translation-jobs", "", deriveRecentWorkPresentation({ translationRunCount: jobs.length }).translationRunsCount);
  }
  renderTranslationJobsInto(container, jobs, {
    onOpen: (job) => renderTranslationJob(job),
    onResume: (job) => handleResume(job.job_id),
    onRebuild: (job) => handleRebuild(job.job_id),
  });
}

function renderTranslationBootstrap(payload) {
  const translation = payload.normalized_payload.translation || {};
  applyTranslationDefaults(translation.defaults || {});
  renderTranslationHistory(translation.history || []);
  renderTranslationJobs(translation.active_jobs || []);
  maybeRestorePreparedTranslationLaunch(
    payload.normalized_payload?.gmail?.suggested_translation_launch
      || appState.bootstrap?.normalized_payload?.gmail?.suggested_translation_launch
      || null,
  );
  if (!translationState.currentSeed) {
    applyTranslationSeed(blankSaveSeed());
  }
  if (hasPreparedTranslationLaunch()) {
    setSourceCardState(buildPreparedSourceCardState(currentPreparedTranslationLaunch()));
  } else if (!hasReadyTranslationSource()) {
    setSourceCardState(blankSourceCardState());
  }
  if (!translationState.currentJob && hasPreparedTranslationLaunch()) {
    renderTranslationPreparedState();
  } else if (!translationState.currentJob) {
    renderTranslationSourceCard();
    renderTranslationResultCard(null);
    renderTranslationRunStatus(null);
    syncTranslationPrimaryActionState();
  }
  renderTranslationOutputSummary();
  syncTranslationCompletionSurface();
  restorePendingArabicReview();
}

async function refreshTranslationBootstrap() {
  const payload = await fetchJson("/api/translation/bootstrap", appState);
  renderTranslationBootstrap({
    normalized_payload: {
      translation: payload.normalized_payload,
      runtime: payload.normalized_payload.runtime || appState.bootstrap?.normalized_payload?.runtime || {},
      gmail: appState.bootstrap?.normalized_payload?.gmail || {},
    },
  });
}

async function refreshTranslationHistory() {
  const payload = await fetchJson("/api/translation/history", appState);
  renderTranslationHistory(payload.normalized_payload.history || []);
  renderTranslationJobs(payload.normalized_payload.active_jobs || []);
}

async function pollCurrentJob() {
  stopPolling();
  if (!translationState.currentJobId) {
    return;
  }
  try {
    const payload = await fetchJson(`/api/translation/jobs/${translationState.currentJobId}`, appState);
    renderTranslationJob(payload.normalized_payload.job || null);
    await refreshTranslationHistory();
  } catch (error) {
    setPanelStatus("translation", "bad", error.message || "Translation job polling failed.");
    setDiagnostics("translation-job", error, { hint: error.message || "Translation job polling failed.", open: true });
  }
}

async function handleGenerateRunReport() {
  const jobId = String(translationState.currentJobId || translationState.currentJob?.job_id || "").trim();
  if (!jobId) {
    throw new Error("No translation job is available for run report generation yet.");
  }
  const payload = await fetchJson(`/api/translation/jobs/${jobId}/run-report`, appState, {
    method: "POST",
  });
  cacheNumericMismatchWarning(
    jobId,
    deriveNumericMismatchWarning(payload.normalized_payload?.job || translationState.currentJob, payload.normalized_payload || payload),
  );
  renderTranslationJob(payload.normalized_payload?.job || translationState.currentJob);
  setPanelStatus("translation", "ok", "Run report generated.");
  setDiagnostics("translation-job", payload, {
    hint: payload.normalized_payload?.report_path || "Run report generated.",
    open: true,
  });
  const downloadLink = qs("translation-download-report");
  if (downloadLink?.href) {
    downloadLink.click();
  }
}

async function handleAnalyze() {
  const uploadedSourcePath = await ensureUploadedSource();
  const formValues = collectTranslationSetupValues();
  if (!formValues.source_path && uploadedSourcePath) {
    formValues.source_path = uploadedSourcePath;
  }
  if (!String(formValues.source_path || "").trim()) {
    throw new Error("Choose a PDF or image and wait for it to finish checking before running Analyze Only.");
  }
  const payload = await fetchJson("/api/translation/jobs/analyze", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ form_values: formValues }),
  });
  setDiagnostics("translation", payload, {
    hint: "Analyze request completed.",
    open: false,
  });
  clearTranslationCompletionSeed();
  renderTranslationJob(payload.normalized_payload.job || null);
  await refreshTranslationHistory();
}

async function handleTranslate() {
  const uploadedSourcePath = await ensureUploadedSource();
  const formValues = collectTranslationSetupValues();
  if (!formValues.source_path && uploadedSourcePath) {
    formValues.source_path = uploadedSourcePath;
  }
  if (!String(formValues.source_path || "").trim()) {
    throw new Error("Choose a PDF or image and wait for it to finish checking before starting translation.");
  }
  const payload = await fetchJson("/api/translation/jobs/translate", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ form_values: formValues }),
  });
  setDiagnostics("translation", payload, {
    hint: "Translation run started.",
    open: false,
  });
  clearTranslationCompletionSeed();
  renderTranslationJob(payload.normalized_payload.job || null);
  await refreshTranslationHistory();
}

async function handleResume(jobId = translationState.currentJobId) {
  if (!String(jobId || "").trim()) {
    throw new Error("No translation job is available to resume.");
  }
  const payload = await fetchJson(`/api/translation/jobs/${jobId}/resume`, appState, {
    method: "POST",
  });
  setDiagnostics("translation", payload, {
    hint: `Resume request sent for ${jobId}.`,
    open: false,
  });
  renderTranslationJob(payload.normalized_payload.job || null);
  await refreshTranslationHistory();
}

async function handleRebuild(jobId = translationState.currentJobId) {
  if (!String(jobId || "").trim()) {
    throw new Error("No translation job is available to rebuild.");
  }
  const payload = await fetchJson(`/api/translation/jobs/${jobId}/rebuild`, appState, {
    method: "POST",
  });
  setDiagnostics("translation", payload, {
    hint: `Rebuild request sent for ${jobId}.`,
    open: false,
  });
  renderTranslationJob(payload.normalized_payload.job || null);
  await refreshTranslationHistory();
}

async function handleCancel() {
  const jobId = String(translationState.currentJobId || "").trim();
  if (!jobId) {
    throw new Error("No translation job is available to cancel.");
  }
  const payload = await fetchJson(`/api/translation/jobs/${jobId}/cancel`, appState, {
    method: "POST",
  });
  setDiagnostics("translation", payload, {
    hint: `Cancel request sent for ${jobId}.`,
    open: false,
  });
  renderTranslationJob(payload.normalized_payload.job || null);
  await refreshTranslationHistory();
}

async function handleReviewExport() {
  const payload = await fetchJson(`/api/translation/jobs/${translationState.currentJobId}/review-export`, appState, {
    method: "POST",
  });
  setDiagnostics("translation-job", payload, { hint: "Review queue export created.", open: true });
  openTranslationCompletionDrawer();
}

async function handleTranslationSave() {
  if (currentArabicReviewIsBlocking()) {
    throw new Error(currentArabicReviewState().message || "Review the Arabic document in Word before you save the case record.");
  }
  const payload = await fetchJson("/api/translation/save-row", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      form_values: collectTranslationSaveValues(),
      seed_payload: translationState.currentSeed,
      row_id: translationState.currentRowId,
      job_id: translationState.currentJobId || "",
      completion_key: currentTranslationCompletionKey(),
    }),
  });
  translationState.currentRowId = payload.saved_result.row_id;
  setFieldValue("translation-row-id", payload.saved_result.row_id);
  setPanelStatus("translation-save", "ok", `Saved case record #${payload.saved_result.row_id}.`);
  setDiagnostics("translation-save", payload, { hint: `Saved case record #${payload.saved_result.row_id}.`, open: false });
  await refreshTranslationHistory();
  window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
}

function resetTranslationSaveForm() {
  applyTranslationSeed(translationState.currentJob?.result?.save_seed || blankSaveSeed(), { rowId: null });
  setPanelStatus("translation-save", "", "Case record form reset.");
  collapseTranslationCompletionSections();
  syncTranslationCompletionSurface();
}

function sourceCardClickIsInteractive(target) {
  if (!target || typeof target.closest !== "function") {
    return false;
  }
  return Boolean(target.closest("button, a, input, select, textarea, summary, details, label"));
}

export function initializeTranslationUi() {
  setDiagnostics("translation", { status: "idle", message: "No translation request has been sent yet." }, {
    hint: "Run requests, source-upload details, and backend validation appear here.",
    open: false,
  });
  setDiagnostics("translation-job", { status: "idle", message: "No translation job loaded yet." }, {
    hint: "Latest progress, log tail, review queue, and failure context appear here.",
    open: false,
  });
  setDiagnostics("translation-save", { status: "idle", message: "No translation save has been run yet." }, {
    hint: "Row-save validation and payload details appear here.",
    open: false,
  });
  clearDownloadLink("translation-download-docx");
  clearDownloadLink("translation-download-partial");
  clearDownloadLink("translation-download-summary");
  clearDownloadLink("translation-download-analyze");
  clearDownloadLink("translation-download-report");
  clearArabicReviewState();
  renderTranslationSourceCard();
  renderTranslationOutputSummary();
  renderTranslationResultCard(null);
  renderTranslationRunStatus(null);
  syncTranslationPrimaryActionState();
  syncTranslationCompletionSurface();

  const sourceInput = qs("translation-source-file");
  const sourceCard = qs("translation-source-card");
  const outputDirInput = qs("translation-output-dir");
  const handleSourceStagingError = (error) => {
    renderTranslationSourceCard();
    renderTranslationResultCard(translationState.currentJob);
    renderTranslationRunStatus(translationState.currentJob);
    syncTranslationPrimaryActionState();
    setPanelStatus("translation", "bad", error.message || "Source staging failed.");
    setDiagnostics("translation", error, {
      hint: error.message || "Source staging failed.",
      open: true,
    });
  };

  qs("translation-source-browse")?.addEventListener("click", () => {
    if (sourceUploadIsPending()) {
      return;
    }
    sourceInput?.click();
  });

  sourceCard?.addEventListener("click", (event) => {
    if (sourceUploadIsPending()) {
      return;
    }
    if (sourceCardClickIsInteractive(event.target)) {
      return;
    }
    sourceInput?.click();
  });

  qs("translation-source-clear")?.addEventListener("click", () => {
    clearManualStagedSource();
    renderTranslationSourceCard();
    renderTranslationResultCard(translationState.currentJob);
    renderTranslationRunStatus(translationState.currentJob);
    syncTranslationPrimaryActionState();
    setDiagnostics("translation", { status: "idle", message: "Local source cleared." }, {
      hint: "Choose another PDF or image to continue.",
      open: false,
    });
  });

  sourceInput?.addEventListener("change", async () => {
    const file = sourceInput.files?.[0] || null;
    if (!file) {
      renderTranslationSourceCard();
      renderTranslationRunStatus(translationState.currentJob);
      syncTranslationPrimaryActionState();
      return;
    }
    try {
      await stageTranslationSourceFile(file);
    } catch (error) {
      handleSourceStagingError(error);
    }
  });

  sourceCard?.addEventListener("dragover", (event) => {
    event.preventDefault();
    if (sourceUploadIsPending()) {
      delete sourceCard.dataset.dragActive;
      return;
    }
    sourceCard.dataset.dragActive = "true";
  });

  sourceCard?.addEventListener("dragleave", () => {
    delete sourceCard.dataset.dragActive;
  });

  sourceCard?.addEventListener("drop", async (event) => {
    event.preventDefault();
    delete sourceCard.dataset.dragActive;
    if (sourceUploadIsPending()) {
      return;
    }
    const file = event.dataTransfer?.files?.[0] || null;
    if (!file) {
      return;
    }
    try {
      await stageTranslationSourceFile(file);
    } catch (error) {
      handleSourceStagingError(error);
    }
  });

  for (const eventName of ["input", "change"]) {
    outputDirInput?.addEventListener(eventName, () => {
      renderTranslationOutputSummary();
      syncTranslationPrimaryActionState();
    });
  }

  qs("translation-refresh")?.addEventListener("click", async () => {
    await runWithBusy(["translation-refresh"], { "translation-refresh": "Refreshing..." }, async () => {
      try {
        await refreshTranslationBootstrap();
      } catch (error) {
        setPanelStatus("translation", "bad", error.message || "Translation refresh failed.");
        setDiagnostics("translation", error, { hint: error.message || "Translation refresh failed.", open: true });
      }
    });
  });
  qs("translation-analyze")?.addEventListener("click", async () => {
    await runWithBusy(["translation-analyze", "translation-start"], { "translation-analyze": "Analyzing..." }, async () => {
      try {
        closeTranslationCompletionDrawer();
        setPanelStatus("translation", "", "Running analyze-only preflight...");
        await handleAnalyze();
      } catch (error) {
        setPanelStatus("translation", "bad", error.message || "Analyze failed.");
        setDiagnostics("translation", error, { hint: error.message || "Analyze failed.", open: true });
      }
    });
  });
  qs("translation-start")?.addEventListener("click", async () => {
    await runWithBusy(["translation-analyze", "translation-start"], { "translation-start": "Starting..." }, async () => {
      try {
        closeTranslationCompletionDrawer();
        setPanelStatus("translation", "", "Starting translation run...");
        await handleTranslate();
      } catch (error) {
        setPanelStatus("translation", "bad", error.message || "Translation start failed.");
        setDiagnostics("translation", error, { hint: error.message || "Translation start failed.", open: true });
      }
    });
  });
  qs("translation-cancel")?.addEventListener("click", async () => {
    await runWithBusy(["translation-cancel"], { "translation-cancel": "Cancelling..." }, async () => {
      try {
        await handleCancel();
      } catch (error) {
        setPanelStatus("translation", "bad", error.message || "Cancellation failed.");
        setDiagnostics("translation", error, { hint: error.message || "Cancellation failed.", open: true });
      }
    });
  });
  qs("translation-resume-btn")?.addEventListener("click", async () => {
    await runWithBusy(["translation-resume-btn"], { "translation-resume-btn": "Resuming..." }, async () => {
      try {
        closeTranslationCompletionDrawer();
        await handleResume();
      } catch (error) {
        setPanelStatus("translation", "bad", error.message || "Resume failed.");
        setDiagnostics("translation", error, { hint: error.message || "Resume failed.", open: true });
      }
    });
  });
  qs("translation-rebuild")?.addEventListener("click", async () => {
    await runWithBusy(["translation-rebuild"], { "translation-rebuild": "Rebuilding..." }, async () => {
      try {
        closeTranslationCompletionDrawer();
        await handleRebuild();
      } catch (error) {
        setPanelStatus("translation", "bad", error.message || "Rebuild failed.");
        setDiagnostics("translation", error, { hint: error.message || "Rebuild failed.", open: true });
      }
    });
  });
  qs("translation-review-export")?.addEventListener("click", async () => {
    await runWithBusy(["translation-review-export"], { "translation-review-export": "Exporting..." }, async () => {
      try {
        await handleReviewExport();
      } catch (error) {
        setPanelStatus("translation", "bad", error.message || "Review queue export failed.");
        setDiagnostics("translation-job", error, { hint: error.message || "Review queue export failed.", open: true });
      }
    });
  });
  qs("translation-generate-report")?.addEventListener("click", async () => {
    await runWithBusy(["translation-generate-report"], { "translation-generate-report": "Generating..." }, async () => {
      try {
        await handleGenerateRunReport();
      } catch (error) {
        setPanelStatus("translation", "bad", error.message || "Run report generation failed.");
        setDiagnostics("translation-job", error, {
          hint: error.message || "Run report generation failed.",
          open: true,
        });
      }
    });
  });
  qs("translation-save-row")?.addEventListener("click", async () => {
    await runWithBusy(["translation-save-row"], { "translation-save-row": "Saving..." }, async () => {
      try {
        await handleTranslationSave();
      } catch (error) {
        setPanelStatus("translation-save", "bad", error.message || "Translation save failed.");
        setDiagnostics("translation-save", error, { hint: error.message || "Translation save failed.", open: true });
      }
    });
  });
  qs("translation-arabic-review-open")?.addEventListener("click", async () => {
    await runWithBusy(["translation-arabic-review-open"], { "translation-arabic-review-open": "Opening..." }, async () => {
      try {
        await openArabicReviewInWord();
      } catch (error) {
        setPanelStatus("translation-save", "bad", error.message || "Arabic DOCX review open failed.");
        setDiagnostics("translation-save", error, {
          hint: error.message || "Arabic DOCX review open failed.",
          open: true,
        });
      }
    });
  });
  qs("translation-arabic-review-continue-now")?.addEventListener("click", async () => {
    await runWithBusy(["translation-arabic-review-continue-now"], { "translation-arabic-review-continue-now": "Continuing..." }, async () => {
      try {
        await continueArabicReview("continue_now");
      } catch (error) {
        setPanelStatus("translation-save", "bad", error.message || "Arabic DOCX review continuation failed.");
        setDiagnostics("translation-save", error, {
          hint: error.message || "Arabic DOCX review continuation failed.",
          open: true,
        });
      }
    });
  });
  qs("translation-arabic-review-continue-without-changes")?.addEventListener("click", async () => {
    await runWithBusy(["translation-arabic-review-continue-without-changes"], { "translation-arabic-review-continue-without-changes": "Continuing..." }, async () => {
      try {
        await continueArabicReview("continue_without_changes");
      } catch (error) {
        setPanelStatus("translation-save", "bad", error.message || "Arabic DOCX review continuation failed.");
        setDiagnostics("translation-save", error, {
          hint: error.message || "Arabic DOCX review continuation failed.",
          open: true,
        });
      }
    });
  });
  qs("translation-new-save")?.addEventListener("click", resetTranslationSaveForm);
  qs("translation-open-completion")?.addEventListener("click", () => openTranslationCompletionDrawer());
  qs("translation-close-completion")?.addEventListener("click", closeTranslationCompletionDrawer);
  qs("translation-close-completion-form")?.addEventListener("click", closeTranslationCompletionDrawer);
  qs("translation-completion-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("translation-completion-drawer-backdrop")) {
      closeTranslationCompletionDrawer();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && translationState.completionDrawerOpen) {
      closeTranslationCompletionDrawer();
    }
  });
}

export {
  loadTranslationHistoryItem,
  refreshTranslationBootstrap,
  refreshTranslationHistory,
  renderTranslationJob,
  renderTranslationBootstrap,
};
