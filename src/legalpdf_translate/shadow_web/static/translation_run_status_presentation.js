import { looksLikeRawTechnicalStateText } from "./translation_result_presentation.js";

const PAGE_FLAG_LOG_RE = /page=(?<page>\d+)\s+image_used=(?<image>True|False)\s+retry_used=(?<retry>True|False)\s+status=(?<status>[a-z_]+)/;
const PAGE_STATUS_LOG_RE = /Page\s+(?<page>\d+)\s+(?<status>finished|failed)/i;

function objectOrEmpty(value) {
  return value && typeof value === "object" ? value : {};
}

function hasOwn(value, key) {
  return Object.prototype.hasOwnProperty.call(objectOrEmpty(value), key);
}

function coercePositiveInt(value) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
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

export function deriveTranslationRunStatusView(job = null, options = {}) {
  const normalizedOptions = objectOrEmpty(options);
  const preparedLaunch = objectOrEmpty(normalizedOptions.preparedLaunch);
  const sourceState = {
    status: "empty",
    ready: false,
    pageCount: null,
    message: "",
    replacingPrepared: false,
    ...objectOrEmpty(normalizedOptions.sourceState),
  };
  const sourceReady = hasOwn(normalizedOptions, "sourceReady")
    ? Boolean(normalizedOptions.sourceReady)
    : Boolean(sourceState.ready);
  const sourcePageCount = coercePositiveInt(
    hasOwn(normalizedOptions, "sourcePageCount")
      ? normalizedOptions.sourcePageCount
      : sourceState.pageCount,
  );
  const progress = job && typeof job.progress === "object" ? job.progress : {};
  const result = job && typeof job.result === "object" ? job.result : {};
  const logFlags = summarizeTranslationLogFlags(job?.logs || []);
  const completedPages = coercePositiveInt(result.completed_pages) ?? 0;
  const selectedIndex = coercePositiveInt(progress.selected_index) ?? completedPages;
  const selectedTotal = coercePositiveInt(progress.selected_total)
    ?? sourcePageCount
    ?? coercePositiveInt(preparedLaunch.page_count)
    ?? null;
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
    } else if (normalizedOptions.preparedLaunch) {
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
        : preparedLaunch.start_page && preparedLaunch.start_page > 1
          ? `Start at page ${preparedLaunch.start_page}`
          : "Not started",
    imageRetryText: imageRetryParts.join(" | ") || "No image or retry markers yet.",
    alertsText: alertParts.join(" | ") || "No flagged pages or errors.",
  };
}
