import { fetchJson } from "./api.js";
import { applyActionFailureFeedbackToUi } from "./action_feedback_presentation.js";
import { appState, setActiveView } from "./state.js";
import { ensureBrowserPdfBundleFromFile } from "./browser_pdf.js";
import { runWithBusy } from "./busy_ui.js";
import { setDiagnostics, setPanelStatus } from "./diagnostics_ui.js";
import { renderShellVisibilityInto } from "./shell_ui.js";
import {
  buildTranslationResultCardPresentation,
  deriveTranslationRecoveryState,
  isAuthenticationFailure,
} from "./translation_result_presentation.js";
import { buildTranslationSourceCardPresentation } from "./translation_source_presentation.js";
import {
  deriveTranslationActionState as deriveTranslationActionStatePresentation,
} from "./translation_action_presentation.js";
import {
  deriveTranslationRunStatusView as deriveTranslationRunStatusViewPresentation,
} from "./translation_run_status_presentation.js";
import {
  blankArabicReviewState,
  deriveTranslationCompletionPresentation,
  hasTranslationSaveSeedData,
  normalizeArabicReviewState,
} from "./translation_completion_presentation.js";
import { deriveRecentWorkPresentation } from "./recent_work_presentation.js";
import {
  renderArabicReviewCardInto,
  renderResultHeaderCardInto,
  renderTranslationResultCardInto,
} from "./result_card_ui.js";
import {
  collapseTranslationCompletionSectionsInto,
  renderTranslationDownloadLinksInto,
  renderTranslationCheckboxInto,
  renderTranslationCompletionSurfaceInto,
  renderTranslationFieldValueInto,
  renderTranslationHistoryListInto,
  renderTranslationJobActionControlsInto,
  renderTranslationJobsListInto,
  renderTranslationNumericMismatchWarningInto,
  renderTranslationOutputSummaryInto,
  renderTranslationPrimaryActionsInto,
  renderTranslationPreparedControlsInto,
  renderTranslationRunStatusInto,
  renderTranslationSourcePathInto,
  renderTranslationSourceCardInto,
  renderTranslationSourceDragStateInto,
  renderTranslationSourceFileInputClearInto,
  syncTranslationCompletionDrawerStateInto,
} from "./translation_ui.js";

export { deriveTranslationRecoveryState } from "./translation_result_presentation.js";
export { deriveTranslationCompletionPresentation } from "./translation_completion_presentation.js";
export { deriveRecentWorkPresentation, formatRecentRunTitle } from "./recent_work_presentation.js";

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
const NUMERIC_MISMATCH_WARNING_MESSAGE = "Review recommended: some numbers from the source may not appear exactly in the translation.";

function applyActionFailureFeedback(
  error,
  { panelSlot = "", diagnosticsSlot = "", fallback = "", tone = "bad" } = {},
) {
  return applyActionFailureFeedbackToUi(
    error,
    { panelSlot, diagnosticsSlot, fallback, tone },
    { setPanelStatus, setDiagnostics },
  );
}

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

function rememberRuntimeJob(job) {
  const summarized = summarizeRuntimeJob(job);
  if (!summarized || !summarized.job_id) {
    return;
  }
  const remaining = translationState.runtimeJobs.filter((item) => item?.job_id !== summarized.job_id);
  translationState.runtimeJobs = [summarized, ...remaining];
}

function currentArabicReviewState() {
  return normalizeArabicReviewState(translationState.arabicReview);
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
  renderTranslationFieldValueInto(qs(id), value);
}

function setCheckbox(id, value) {
  renderTranslationCheckboxInto(qs(id), value);
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
  renderTranslationSourcePathInto(
    {
      pathField: qs("translation-source-path"),
      summary: qs("translation-source-path-summary"),
    },
    value,
  );
}

function currentManualSourceFile() {
  return translationState.manualSourceFile || qs("translation-source-file")?.files?.[0] || null;
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
    currentJobId = translationState.currentJobId,
  } = {},
) {
  return deriveTranslationActionStatePresentation(job, { sourceState, currentJobId });
}

function renderTranslationSourceCard() {
  const card = qs("translation-source-card");
  if (!card) {
    return;
  }
  const sourceState = deriveTranslationSourceState();
  const launch = currentPreparedTranslationLaunch();
  const presentation = buildTranslationSourceCardPresentation({
    sourceState,
    preparedLaunch: launch,
    selectedTarget: fieldValue("translation-target-lang"),
    defaultTarget: defaultTranslationTargetLang(),
    hasManualSourceSelection: hasManualSourceSelection(),
  });
  renderTranslationSourceCardInto({
    card,
    title: qs("translation-source-card-title"),
    copy: qs("translation-source-card-copy"),
    filename: qs("translation-source-filename"),
    sourceType: qs("translation-source-type"),
    pages: qs("translation-source-pages"),
    target: qs("translation-source-target"),
    defaultTarget: qs("translation-source-default-target"),
    stageStatus: qs("translation-source-stage-status"),
    hint: qs("translation-source-card-hint"),
    chip: qs("translation-source-card-chip"),
    browseButton: qs("translation-source-browse"),
    clearButton: qs("translation-source-clear"),
  }, presentation);
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
  const outputDir = fieldValue("translation-output-dir");
  const defaultOutdir = browserDefaultOutputDir();
  let summary = {
    label: "Choose an output folder",
    copy: "Open Change folder/path to decide where translated files should be saved.",
    path: "No output folder selected yet.",
  };
  if (outputDir && defaultOutdir && outputDir === defaultOutdir) {
    summary = {
      label: "Using default output folder",
      copy: "Translated files will be saved in the default folder for this workspace.",
      path: outputDir,
    };
  } else if (outputDir) {
    summary = {
      label: "Save output in",
      copy: defaultOutdir
        ? "Using the folder shown below. Open Change folder/path if you want to save somewhere else."
        : "Using the folder shown below.",
      path: outputDir,
    };
  }
  renderTranslationOutputSummaryInto({
    label: qs("translation-output-summary-label"),
    copy: qs("translation-output-summary-copy"),
    path: qs("translation-output-summary-path"),
  }, summary);
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
  renderTranslationNumericMismatchWarningInto(container, normalized);
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
    renderTranslationSourceFileInputClearInto(input);
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

function syncTranslationPrimaryActionState() {
  const actionState = deriveTranslationActionState();
  renderTranslationPrimaryActionsInto({
    helper: qs("translation-action-helper"),
    startButton: qs("translation-start"),
    analyzeButton: qs("translation-analyze"),
    cancelButton: qs("translation-cancel"),
    resumeButton: qs("translation-resume-btn"),
    rebuildButton: qs("translation-rebuild"),
  }, actionState);
}

export function deriveTranslationRunStatusView(
  job,
  options = {},
) {
  const normalizedOptions = options && typeof options === "object" ? options : {};
  const preparedLaunch = Object.prototype.hasOwnProperty.call(normalizedOptions, "preparedLaunch")
    ? normalizedOptions.preparedLaunch
    : currentPreparedTranslationLaunch();
  const sourceStateCandidate = Object.prototype.hasOwnProperty.call(normalizedOptions, "sourceState")
    ? normalizedOptions.sourceState
    : deriveTranslationSourceState({ job, preparedLaunch });
  const sourceState = sourceStateCandidate && typeof sourceStateCandidate === "object" ? sourceStateCandidate : {};
  const sourceReady = Object.prototype.hasOwnProperty.call(normalizedOptions, "sourceReady")
    ? normalizedOptions.sourceReady
    : sourceState.ready;
  const sourcePageCount = Object.prototype.hasOwnProperty.call(normalizedOptions, "sourcePageCount")
    ? normalizedOptions.sourcePageCount
    : sourceState.pageCount ?? currentSourcePageCount();
  return deriveTranslationRunStatusViewPresentation(job, {
    ...normalizedOptions,
    preparedLaunch,
    sourceState,
    sourceReady,
    sourcePageCount,
  });
}

function renderTranslationRunStatus(job = translationState.currentJob) {
  const nodes = {
    percent: qs("translation-progress-percent"),
    chip: qs("translation-run-status-chip"),
    track: qs("translation-progress-track"),
    bar: qs("translation-progress-bar"),
    task: qs("translation-current-task"),
    pages: qs("translation-run-pages"),
    currentPage: qs("translation-run-current-page"),
    imageRetry: qs("translation-run-image-retry"),
    alerts: qs("translation-run-alerts"),
  };
  if (!nodes.percent || !nodes.chip || !nodes.track || !nodes.bar || !nodes.task || !nodes.pages || !nodes.currentPage || !nodes.imageRetry || !nodes.alerts) {
    return;
  }
  const view = deriveTranslationRunStatusView(job);
  renderTranslationRunStatusInto(nodes, view);
}

function translationDownloadLinkNodes() {
  return {
    report: qs("translation-download-report"),
    docx: qs("translation-download-docx"),
    partial: qs("translation-download-partial"),
    summary: qs("translation-download-summary"),
    analyze: qs("translation-download-analyze"),
  };
}

function renderTranslationDownloadLinks(links = {}) {
  renderTranslationDownloadLinksInto(translationDownloadLinkNodes(), links);
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
  collapseTranslationCompletionSectionsInto({
    metrics: qs("translation-save-metrics-section"),
    amounts: qs("translation-save-amounts-section"),
  });
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
  syncTranslationCompletionDrawerStateInto({
    backdrop,
    body: document.body,
  }, translationState.completionDrawerOpen);
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
    renderResultHeaderCardInto(container, {
      available: false,
      emptyText: presentation.resultCopy,
    });
    return;
  }
  renderResultHeaderCardInto(container, {
    available: true,
    title: presentation.resultTitle,
    message: presentation.resultCopy,
    detailLines: presentation.resultDetailLines,
    label: presentation.resultChipLabel,
    tone: presentation.resultChipTone,
  });
}

function renderArabicReviewCard() {
  const card = qs("translation-arabic-review-card");
  if (!card) {
    return;
  }
  const review = currentArabicReviewState();
  const saveSeed = currentTranslationSeed();
  const presentation = deriveTranslationCompletionPresentation({
    job: translationState.currentJob,
    saveSeed,
    currentRowId: translationState.currentRowId,
    arabicReview: review,
    gmailBatchContext: translationState.currentGmailBatchContext,
  });
  const show = Boolean(review.required || currentCompletedTranslationJobRequiresArabicReview());
  const docxSource = review.docx_path || String(saveSeed.output_docx || "").trim();
  renderArabicReviewCardInto({
    card,
    title: qs("translation-arabic-review-title"),
    copy: qs("translation-arabic-review-copy"),
    chip: qs("translation-arabic-review-chip"),
    docxLabel: qs("translation-arabic-review-docx-label"),
    docxPath: qs("translation-arabic-review-docx-path"),
    openButton: qs("translation-arabic-review-open"),
    continueNowButton: qs("translation-arabic-review-continue-now"),
    continueWithoutChangesButton: qs("translation-arabic-review-continue-without-changes"),
  }, {
    show,
    docxLabel: presentation.arabicReview.docxLabel,
    title: presentation.arabicReview.title,
    copy: presentation.arabicReview.copy,
    docxPath: docxSource || presentation.arabicReview.unavailableText,
    chipLabel: presentation.arabicReview.chipLabel,
    chipTone: presentation.arabicReview.chipTone,
    openLabel: presentation.arabicReview.openLabel,
    continueNowLabel: presentation.arabicReview.continueNowLabel,
    continueWithoutChangesLabel: presentation.arabicReview.continueWithoutChangesLabel,
    openDisabled: !Boolean(docxSource),
    continueNowDisabled: Boolean(review.required && review.resolved),
    continueWithoutChangesDisabled: Boolean(review.required && review.resolved),
  });
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
  const saveButton = qs("translation-save-row");
  const review = currentArabicReviewState();
  const hasSaveSurface = hasTranslationSaveSeed();
  const presentation = deriveTranslationCompletionPresentation({
    job: translationState.currentJob,
    saveSeed: currentTranslationSeed(),
    currentRowId: translationState.currentRowId,
    arabicReview: review,
    gmailBatchContext: translationState.currentGmailBatchContext,
  });
  renderTranslationCompletionSurfaceInto({
    openButton,
    formShell,
    emptyShell,
    status: statusNode,
    emptyTitle: emptyTitleNode,
    emptyCopy: emptyCopyNode,
    saveTitle: saveTitleNode,
    saveStatus: saveStatusNode,
    saveButton,
  }, {
    available,
    hasSaveSurface,
    openButtonLabel: completionButtonLabel(),
    drawerStatus: presentation.drawerStatus,
    emptyTitle: presentation.emptyTitle,
    emptyCopy: presentation.emptyCopy,
    saveTitle: presentation.saveTitle,
    saveStatus: presentation.saveStatus,
    saveButtonLabel: presentation.saveButtonLabel,
    saveDisabled: !hasSaveSurface || currentArabicReviewIsBlocking(),
  });
  if (!translationState.currentJob) {
    renderTranslationJobActionControlsInto({
      reportButton: qs("translation-generate-report"),
      reviewExport: qs("translation-review-export"),
    }, {
      reportAvailable: false,
      reportVisible: false,
      reviewExportAvailable: false,
    });
    renderTranslationDownloadLinks();
  }
  if (!available) {
    renderTranslationCompletionResultCard();
    renderArabicReviewCard();
    closeTranslationCompletionDrawer();
    return;
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

function currentTranslationRunDir(job = translationState.currentJob) {
  return String(
    job?.result?.artifacts?.run_dir
    || job?.artifacts?.run_dir
    || job?.artifacts?.run_dir_text
    || "",
  ).trim();
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
      applyActionFailureFeedback(error, {
        panelSlot: "translation-save",
        diagnosticsSlot: "translation-save",
        fallback: "Arabic DOCX review refresh failed.",
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
        applyActionFailureFeedback(error, {
          panelSlot: "translation-save",
          diagnosticsSlot: "translation-save",
          fallback: "Arabic DOCX review open failed.",
          tone: "warn",
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
    applyActionFailureFeedback(error, {
      panelSlot: "translation-save",
      diagnosticsSlot: "translation-save",
      fallback: "Arabic DOCX review restore failed.",
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
  renderTranslationDownloadLinks();
  renderTranslationPreparedControlsInto({
    reportButton: qs("translation-generate-report"),
    reviewExport: qs("translation-review-export"),
    cancelButton: qs("translation-cancel"),
    resumeButton: qs("translation-resume-btn"),
    rebuildButton: qs("translation-rebuild"),
  });
  notifyTranslationUiStateChanged();
  return true;
}

function renderTranslationResultCard(job, { containerId = "translation-result" } = {}) {
  const container = qs(containerId);
  if (!container) {
    return;
  }
  const card = buildTranslationResultCardPresentation({
    job,
    preparedLaunch: job ? null : currentPreparedTranslationLaunch(),
    hasReadySource: !job && hasReadyTranslationSource(),
    defaultTarget: defaultTranslationTargetLang(),
  });
  renderTranslationResultCardInto(container, card);
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
  renderTranslationDownloadLinks({
    report: translationRunReportHref(job),
    docx: job?.actions?.download_output_docx ? `/api/translation/jobs/${job.job_id}/artifact/output_docx?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "",
    partial: job?.actions?.download_partial_docx ? `/api/translation/jobs/${job.job_id}/artifact/partial_docx?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "",
    summary: job?.actions?.download_run_summary ? `/api/translation/jobs/${job.job_id}/artifact/run_summary?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "",
    analyze: job?.actions?.download_analyze_report ? `/api/translation/jobs/${job.job_id}/artifact/analyze_report?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "",
  });
  renderTranslationJobActionControlsInto({
    reportButton: qs("translation-generate-report"),
    reviewExport: qs("translation-review-export"),
  }, {
    reportAvailable: Boolean(job?.job_kind === "translate" && runDir),
    reportVisible: Boolean(job),
    reviewExportAvailable: Boolean(job?.actions?.review_export),
  });
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
      applyActionFailureFeedback(error, {
        panelSlot: "translation-save",
        diagnosticsSlot: "translation-save",
        fallback: "Arabic DOCX review refresh failed.",
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
  const presentation = deriveRecentWorkPresentation();
  renderTranslationHistoryListInto(container, history, {
    emptyText: presentation.translationHistoryEmpty,
    openLabel: presentation.translationHistoryOpenLabel,
    deleteLabel: presentation.translationHistoryDeleteLabel,
    onOpen,
    onDelete,
  });
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
        applyActionFailureFeedback(error, {
          panelSlot: "translation-save",
          diagnosticsSlot: "translation-save",
          fallback: "Translation row delete failed.",
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
  renderShellVisibilityInto({
    views: document.querySelectorAll(".page-view"),
    navButtons: document.querySelectorAll(".nav-button"),
    activeView: "new-job",
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
  const presentation = deriveRecentWorkPresentation();
  renderTranslationJobsListInto(container, jobs, {
    emptyText: presentation.translationRunsEmpty,
    presentationForJob: (job) => deriveRecentWorkPresentation({ translationRunCount: jobs.length, job }),
    onOpen,
    onResume,
    onRebuild,
  });
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
    applyActionFailureFeedback(error, {
      panelSlot: "translation",
      diagnosticsSlot: "translation-job",
      fallback: "Translation job polling failed.",
    });
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
  renderTranslationDownloadLinks();
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
    applyActionFailureFeedback(error, {
      panelSlot: "translation",
      diagnosticsSlot: "translation",
      fallback: "Source staging failed.",
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
      renderTranslationSourceDragStateInto(sourceCard, { active: false });
      return;
    }
    renderTranslationSourceDragStateInto(sourceCard, { active: true });
  });

  sourceCard?.addEventListener("dragleave", () => {
    renderTranslationSourceDragStateInto(sourceCard, { active: false });
  });

  sourceCard?.addEventListener("drop", async (event) => {
    event.preventDefault();
    renderTranslationSourceDragStateInto(sourceCard, { active: false });
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
        applyActionFailureFeedback(error, {
          panelSlot: "translation",
          diagnosticsSlot: "translation",
          fallback: "Translation refresh failed.",
        });
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
        applyActionFailureFeedback(error, {
          panelSlot: "translation",
          diagnosticsSlot: "translation",
          fallback: "Analyze failed.",
        });
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
        applyActionFailureFeedback(error, {
          panelSlot: "translation",
          diagnosticsSlot: "translation",
          fallback: "Translation start failed.",
        });
      }
    });
  });
  qs("translation-cancel")?.addEventListener("click", async () => {
    await runWithBusy(["translation-cancel"], { "translation-cancel": "Cancelling..." }, async () => {
      try {
        await handleCancel();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation",
          diagnosticsSlot: "translation",
          fallback: "Cancellation failed.",
        });
      }
    });
  });
  qs("translation-resume-btn")?.addEventListener("click", async () => {
    await runWithBusy(["translation-resume-btn"], { "translation-resume-btn": "Resuming..." }, async () => {
      try {
        closeTranslationCompletionDrawer();
        await handleResume();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation",
          diagnosticsSlot: "translation",
          fallback: "Resume failed.",
        });
      }
    });
  });
  qs("translation-rebuild")?.addEventListener("click", async () => {
    await runWithBusy(["translation-rebuild"], { "translation-rebuild": "Rebuilding..." }, async () => {
      try {
        closeTranslationCompletionDrawer();
        await handleRebuild();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation",
          diagnosticsSlot: "translation",
          fallback: "Rebuild failed.",
        });
      }
    });
  });
  qs("translation-review-export")?.addEventListener("click", async () => {
    await runWithBusy(["translation-review-export"], { "translation-review-export": "Exporting..." }, async () => {
      try {
        await handleReviewExport();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation",
          diagnosticsSlot: "translation-job",
          fallback: "Review queue export failed.",
        });
      }
    });
  });
  qs("translation-generate-report")?.addEventListener("click", async () => {
    await runWithBusy(["translation-generate-report"], { "translation-generate-report": "Generating..." }, async () => {
      try {
        await handleGenerateRunReport();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation",
          diagnosticsSlot: "translation-job",
          fallback: "Run report generation failed.",
        });
      }
    });
  });
  qs("translation-save-row")?.addEventListener("click", async () => {
    await runWithBusy(["translation-save-row"], { "translation-save-row": "Saving..." }, async () => {
      try {
        await handleTranslationSave();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation-save",
          diagnosticsSlot: "translation-save",
          fallback: "Translation save failed.",
        });
      }
    });
  });
  qs("translation-arabic-review-open")?.addEventListener("click", async () => {
    await runWithBusy(["translation-arabic-review-open"], { "translation-arabic-review-open": "Opening..." }, async () => {
      try {
        await openArabicReviewInWord();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation-save",
          diagnosticsSlot: "translation-save",
          fallback: "Arabic DOCX review open failed.",
        });
      }
    });
  });
  qs("translation-arabic-review-continue-now")?.addEventListener("click", async () => {
    await runWithBusy(["translation-arabic-review-continue-now"], { "translation-arabic-review-continue-now": "Continuing..." }, async () => {
      try {
        await continueArabicReview("continue_now");
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation-save",
          diagnosticsSlot: "translation-save",
          fallback: "Arabic DOCX review continuation failed.",
        });
      }
    });
  });
  qs("translation-arabic-review-continue-without-changes")?.addEventListener("click", async () => {
    await runWithBusy(["translation-arabic-review-continue-without-changes"], { "translation-arabic-review-continue-without-changes": "Continuing..." }, async () => {
      try {
        await continueArabicReview("continue_without_changes");
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "translation-save",
          diagnosticsSlot: "translation-save",
          fallback: "Arabic DOCX review continuation failed.",
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
