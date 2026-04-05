import { fetchJson } from "./api.js";
import { appState, setActiveView } from "./state.js";
import { ensureBrowserPdfBundleFromFile } from "./browser_pdf.js";

const translationState = {
  currentSeed: null,
  currentRowId: null,
  currentJob: null,
  currentJobId: "",
  runtimeJobs: [],
  currentGmailBatchContext: null,
  uploadedSourcePath: "",
  uploadedSourceKey: "",
  pollTimer: null,
  arabicReviewPollTimer: null,
  completionDrawerOpen: false,
  lastAutoOpenedCompletionKey: "",
  arabicReview: null,
};

let lastTranslationUiSnapshotKey = "";

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

function summarizeRuntimeJob(job) {
  if (!job || typeof job !== "object") {
    return null;
  }
  return {
    job_id: String(job.job_id || "").trim(),
    job_kind: String(job.job_kind || "").trim(),
    status: String(job.status || "").trim(),
    updated_at: String(job.updated_at || "").trim(),
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
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

function isPdfFile(file) {
  if (!file) {
    return false;
  }
  return String(file.type || "").trim().toLowerCase() === "application/pdf"
    || String(file.name || "").trim().toLowerCase().endsWith(".pdf");
}

async function ensureUploadedSource() {
  const input = qs("translation-source-file");
  const file = input?.files?.[0];
  if (!file) {
    return translationState.uploadedSourcePath || "";
  }
  const key = sourceFileKey(file);
  if (translationState.uploadedSourceKey === key && translationState.uploadedSourcePath) {
    return translationState.uploadedSourcePath;
  }
  const form = new FormData();
  form.append("file", file);
  const payload = await fetchJson("/api/translation/upload-source", appState, {
    method: "POST",
    body: form,
  });
  translationState.currentGmailBatchContext = null;
  translationState.uploadedSourceKey = key;
  translationState.uploadedSourcePath = payload.normalized_payload.source_path || "";
  let resolvedPageCount = payload.normalized_payload.page_count ?? "?";
  let sourceUploadHint = "Source upload complete.";
  if (isPdfFile(file) && translationState.uploadedSourcePath) {
    const browserBundle = await ensureBrowserPdfBundleFromFile({
      appState,
      sourcePath: translationState.uploadedSourcePath,
      file,
    });
    resolvedPageCount = browserBundle.page_count ?? resolvedPageCount;
    sourceUploadHint = "Source upload complete. Browser PDF staging is ready.";
  }
  setFieldValue("translation-source-summary", [
    `Filename: ${payload.normalized_payload.source_filename || file.name}`,
    `Type: ${payload.normalized_payload.source_type || "unknown"}`,
    `Pages: ${resolvedPageCount}`,
    `Saved path: ${payload.normalized_payload.source_path || ""}`,
  ].join("\n"));
  setDiagnostics("translation", payload, {
    hint: sourceUploadHint,
    open: false,
  });
  return translationState.uploadedSourcePath;
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
  const seed = translationState.currentSeed || {};
  return Boolean(
    translationState.currentRowId
    || translationState.currentJob?.result?.save_seed
    || seed.run_id
    || seed.case_number
    || seed.court_email
    || seed.case_entity
    || seed.case_city,
  );
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
  if (translationState.currentRowId) {
    return "Open Saved Row";
  }
  if (translationState.currentJob?.job_kind === "analyze") {
    return "Review Results";
  }
  return "Finish Translation";
}

function completionSurfaceSummary() {
  const review = currentArabicReviewState();
  const job = translationState.currentJob;
  if (job?.job_kind === "analyze" && job.status === "completed") {
    return "Analyze-only preflight is complete. Export the report or other artifacts here, or start the full translation when you are ready to create a job-log row.";
  }
  if (review.required && !review.resolved) {
    return review.message || "Arabic DOCX review is required before Save-to-Job-Log can continue.";
  }
  if (translationState.currentRowId) {
    return `Loaded translation row #${translationState.currentRowId}. Review the case fields first, then save any edits back to the active job log.`;
  }
  if (hasTranslationSaveSeed()) {
    return "Translation complete. Review the case fields first. Run metrics and amounts stay collapsed until you need them.";
  }
  return "Complete a translation run or load a saved translation row to review the case fields, artifacts, and finish-the-job actions here.";
}

function renderTranslationCompletionResultCard() {
  const container = qs("translation-completion-result");
  if (!container) {
    return;
  }
  if (translationState.currentJob) {
    renderTranslationResultCard(translationState.currentJob, { containerId: "translation-completion-result" });
    return;
  }
  if (!hasTranslationSaveSeed()) {
    container.classList.add("empty-state");
    container.textContent = "Complete a translation run or load a saved row to open the bounded translation finish surface.";
    return;
  }
  const seed = translationState.currentSeed || {};
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>Saved translation row is ready to review.</strong>
        <p>${seed.case_number || "No case number"}<br>${seed.case_entity || "No case entity"} | ${seed.case_city || "No case city"} | ${seed.translation_date || "No date"}</p>
      </div>
      <span class="status-chip info">Ready</span>
    </div>
  `;
}

function renderArabicReviewCard() {
  const card = qs("translation-arabic-review-card");
  const title = qs("translation-arabic-review-title");
  const copy = qs("translation-arabic-review-copy");
  const chip = qs("translation-arabic-review-chip");
  const docxPath = qs("translation-arabic-review-docx-path");
  const openButton = qs("translation-arabic-review-open");
  const continueNowButton = qs("translation-arabic-review-continue-now");
  const continueWithoutChangesButton = qs("translation-arabic-review-continue-without-changes");
  if (!card || !title || !copy || !chip || !docxPath || !openButton || !continueNowButton || !continueWithoutChangesButton) {
    return;
  }
  const review = currentArabicReviewState();
  const show = Boolean(review.required || currentCompletedTranslationJobRequiresArabicReview());
  card.classList.toggle("hidden", !show);
  if (!show) {
    return;
  }
  const resolved = Boolean(review.required && review.resolved);
  title.textContent = "Arabic DOCX Review";
  copy.textContent = review.message || (
    resolved
      ? "Arabic DOCX review is resolved. You can continue with Save-to-Job-Log or Gmail confirmation."
      : "Open the durable translated DOCX in Word, align or edit it manually, then save it to continue automatically."
  );
  docxPath.textContent = review.docx_path || String(currentTranslationSeed().output_docx || "").trim() || "Durable DOCX unavailable.";
  chip.textContent = resolved ? "Resolved" : review.status === "waiting_for_save" ? "Waiting" : "Required";
  chip.className = `status-chip ${resolved ? "ok" : review.status === "attention" || review.status === "missing" ? "warn" : "info"}`;
  openButton.disabled = !Boolean(review.docx_path || currentTranslationSeed().output_docx);
  continueNowButton.disabled = resolved;
  continueWithoutChangesButton.disabled = resolved;
}

function syncTranslationCompletionSurface() {
  const available = hasTranslationCompletionSurface();
  const openButton = qs("translation-open-completion");
  const formShell = qs("translation-completion-form-shell");
  const emptyShell = qs("translation-completion-empty");
  const statusNode = qs("translation-completion-status");
  const reviewExportButton = qs("translation-review-export");
  const runReportButton = qs("translation-generate-report");
  const saveButton = qs("translation-save-row");
  const review = currentArabicReviewState();
  if (openButton) {
    openButton.classList.toggle("hidden", !available);
    openButton.textContent = completionButtonLabel();
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
      statusNode.textContent = "Complete a translation run or load a saved translation row to review the case fields, artifacts, and finish-the-job actions here.";
    }
    renderTranslationCompletionResultCard();
    renderArabicReviewCard();
    closeTranslationCompletionDrawer();
    return;
  }
  if (statusNode) {
    statusNode.textContent = completionSurfaceSummary();
  }
  const hasSaveSurface = hasTranslationSaveSeed();
  formShell?.classList.toggle("hidden", !hasSaveSurface);
  emptyShell?.classList.toggle("hidden", hasSaveSurface);
  if (saveButton) {
    saveButton.disabled = !hasSaveSurface || currentArabicReviewIsBlocking();
  }
  if (hasSaveSurface && !translationState.currentRowId && review.required) {
    setPanelStatus(
      "translation-save",
      review.resolved ? "" : "warn",
      review.resolved
        ? "Arabic DOCX review resolved. Review the case fields before saving."
        : (review.message || "Arabic DOCX review is required before Save-to-Job-Log can continue."),
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
      ? "Analyze complete. Open the bounded results surface to export the report or start the full translation."
      : job.status_text || "Analyze job is running.";
  }
  if (job.job_kind === "rebuild") {
    return job.status === "completed"
      ? "DOCX rebuild complete. Open the bounded results surface to collect the refreshed artifact."
      : job.status_text || "DOCX rebuild is running.";
  }
  if (job.status === "completed") {
    return "Translation complete. Finish the job from the bounded results surface.";
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
  if (!window.confirm(`Delete translation row #${rowId} from the active job log?`)) {
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
  setPanelStatus("translation-save", "ok", payload.normalized_payload?.message || `Deleted translation row #${rowId}.`);
  setDiagnostics("translation-save", payload, {
    hint: payload.normalized_payload?.message || `Deleted translation row #${rowId}.`,
    open: false,
  });
  window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
}

function applyTranslationDefaults(defaults) {
  setFieldValue("translation-output-dir", defaults.output_dir || "");
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
}

export function applyTranslationLaunch(launch) {
  if (!launch || typeof launch !== "object") {
    return;
  }
  dispatchNewJobTask("translation");
  translationState.currentGmailBatchContext = normalizeGmailBatchContext(launch.gmail_batch_context);
  if (launch.source_path) {
    setFieldValue("translation-source-path", launch.source_path);
  }
  if (launch.output_dir) {
    setFieldValue("translation-output-dir", launch.output_dir);
  }
  if (launch.target_lang) {
    setFieldValue("translation-target-lang", launch.target_lang);
  }
  if (launch.start_page !== undefined && launch.start_page !== null) {
    setFieldValue("translation-start-page", launch.start_page);
  }
  setFieldValue(
    "translation-source-summary",
    [
      `Filename: ${launch.source_filename || "Unknown source"}`,
      `Pages: ${launch.page_count ?? "?"}`,
      `Start page: ${launch.start_page ?? 1}`,
      `Saved path: ${launch.source_path || ""}`,
    ].join("\n"),
  );
  setPanelStatus("translation", "", "Gmail attachment loaded into the translation workspace. Review the settings, then start the translation run.");
}

export function resetTranslationForGmailRedo(launch) {
  stopPolling();
  stopArabicReviewPolling();
  translationState.currentJob = null;
  translationState.currentJobId = "";
  translationState.currentSeed = null;
  translationState.currentRowId = null;
  translationState.lastAutoOpenedCompletionKey = "";
  translationState.uploadedSourcePath = "";
  translationState.uploadedSourceKey = "";
  setFieldValue("translation-job-id", "");
  setFieldValue("translation-row-id", "");
  const sourceInput = qs("translation-source-file");
  if (sourceInput) {
    sourceInput.value = "";
  }
  closeTranslationCompletionDrawer();
  clearArabicReviewState();
  renderTranslationJob(null);
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

function renderTranslationResultCard(job, { containerId = "translation-result" } = {}) {
  const container = qs(containerId);
  if (!container) {
    return;
  }
  if (!job) {
    container.classList.add("empty-state");
    container.textContent = "No translation job has run in this workspace yet.";
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
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(job.status_text || "Translation job state available.")}</strong>
        <p>${summaryLines.map((line) => escapeHtml(line)).join("<br>")}</p>
      </div>
      <span class="status-chip ${job.status === "completed" ? "ok" : job.status === "failed" ? "bad" : job.status === "cancelled" ? "warn" : "info"}">${escapeHtml(job.status)}</span>
    </div>
  `;
}

function renderTranslationJob(job) {
  translationState.currentJob = job || null;
  translationState.currentJobId = job?.job_id || "";
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
  setPanelStatus(
    "translation",
    job
      ? (job.status === "failed" ? "bad" : job.status === "cancelled" ? "warn" : "")
      : "",
    translationStatusSummary(job) || "Load a source file, then analyze or translate it in this browser workspace.",
  );
  const diagnosticsHint = isAuthenticationFailure(job)
    ? "OpenAI authentication failed. Open Browser Settings, save a valid translation key, run Test Translation Auth, then start the translation again."
    : recovery.visible
      ? recovery.diagnosticsHint
      : "Latest progress, log tail, review queue, and failure context appear here.";
  setDiagnostics("translation-job", job || { status: "idle", message: "No translation job loaded." }, {
    hint: diagnosticsHint,
    open: Boolean(job && job.status !== "completed"),
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
  qs("translation-cancel").disabled = !job?.actions?.cancel;
  qs("translation-resume-btn").disabled = !job?.actions?.resume;
  qs("translation-rebuild").disabled = !(job?.actions?.rebuild || false);
  if (job?.result?.save_seed) {
    applyTranslationSeed(job.result.save_seed);
    setPanelStatus("translation-save", "", "Translation seed loaded from the completed run. Review the fields before saving.");
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
  notifyTranslationUiStateChanged();
}

function renderTranslationHistory(history) {
  const container = qs("translation-history-list");
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (!history.length) {
    container.innerHTML = '<div class="empty-state">No translation rows have been saved yet for this runtime mode.</div>';
    return;
  }
  for (const item of history) {
    const row = item.row || {};
    const card = document.createElement("article");
    card.className = "history-item";
    card.innerHTML = `<div><strong>${row.case_number || "No case number"}</strong><p>${row.case_entity || "No case entity"} | ${row.case_city || "No case city"} | ${row.translation_date || "No date"}</p></div>`;
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Load";
    button.addEventListener("click", () => loadTranslationHistoryItem(item));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", async () => {
      try {
        await deleteTranslationJobLogRow(row.id);
      } catch (error) {
        setPanelStatus("translation-save", "bad", error.message || "Translation row delete failed.");
        setDiagnostics("translation-save", error, {
          hint: error.message || "Translation row delete failed.",
          open: true,
        });
      }
    });
    actions.appendChild(button);
    actions.appendChild(deleteButton);
    card.appendChild(actions);
    container.appendChild(card);
  }
}

function loadTranslationHistoryItem(item) {
  const row = item?.row || {};
  translationState.currentJob = null;
  translationState.currentJobId = "";
  translationState.currentGmailBatchContext = null;
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
    setPanelStatus("translation-save", "ok", `Loaded translation row #${row.id} from the active job log.`);
    setDiagnostics("translation-save", item, { hint: `Loaded row #${row.id}.`, open: false });
  }
  openTranslationCompletionDrawer();
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
  container.innerHTML = "";
  if (!jobs.length) {
    container.innerHTML = '<div class="empty-state">No browser translation jobs have been started in this runtime mode yet.</div>';
    setPanelStatus("translation-jobs", "", "No browser translation jobs are active for this runtime mode.");
    return;
  }
  setPanelStatus("translation-jobs", "", `${jobs.length} browser translation job(s) are available in this runtime mode.`);
  for (const job of jobs) {
    const card = document.createElement("article");
    card.className = "history-item";
    const details = document.createElement("div");
    const config = job.config || {};
    details.innerHTML = `<strong>${config.source_path || job.job_id}</strong><p>${job.job_kind} | ${config.target_lang || "?"} | ${job.status}</p>`;
    const actions = document.createElement("div");
    actions.className = "history-meta";
    const loadButton = document.createElement("button");
    loadButton.type = "button";
    loadButton.textContent = "Load";
    loadButton.addEventListener("click", () => renderTranslationJob(job));
    actions.appendChild(loadButton);
    if (job.actions?.resume) {
      const resume = document.createElement("button");
      resume.type = "button";
      resume.textContent = "Resume";
      resume.addEventListener("click", () => handleResume(job.job_id));
      actions.appendChild(resume);
    }
    if (job.actions?.rebuild) {
      const rebuild = document.createElement("button");
      rebuild.type = "button";
      rebuild.textContent = "Rebuild";
      rebuild.addEventListener("click", () => handleRebuild(job.job_id));
      actions.appendChild(rebuild);
    }
    card.appendChild(details);
    card.appendChild(actions);
    container.appendChild(card);
  }
}

function renderTranslationBootstrap(payload) {
  const translation = payload.normalized_payload.translation || {};
  applyTranslationDefaults(translation.defaults || {});
  renderTranslationHistory(translation.history || []);
  renderTranslationJobs(translation.active_jobs || []);
  if (!translationState.currentSeed) {
    applyTranslationSeed(blankSaveSeed());
  }
  syncTranslationCompletionSurface();
  restorePendingArabicReview();
}

async function refreshTranslationBootstrap() {
  const payload = await fetchJson("/api/translation/bootstrap", appState);
  renderTranslationBootstrap({
    normalized_payload: {
      translation: payload.normalized_payload,
      runtime: payload.normalized_payload.runtime || appState.bootstrap?.normalized_payload?.runtime || {},
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
  const payload = await fetchJson(`/api/translation/jobs/${translationState.currentJobId}/cancel`, appState, {
    method: "POST",
  });
  setDiagnostics("translation", payload, {
    hint: `Cancel request sent for ${translationState.currentJobId}.`,
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
    throw new Error(currentArabicReviewState().message || "Arabic DOCX review is still required before saving.");
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
  setPanelStatus("translation-save", "ok", `Saved translation row #${payload.saved_result.row_id} to the active job log.`);
  setDiagnostics("translation-save", payload, { hint: `Saved row #${payload.saved_result.row_id}.`, open: false });
  await refreshTranslationHistory();
  window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
}

function resetTranslationSaveForm() {
  applyTranslationSeed(translationState.currentJob?.result?.save_seed || blankSaveSeed(), { rowId: null });
  setPanelStatus("translation-save", "", "Translation save form reset.");
  collapseTranslationCompletionSections();
  syncTranslationCompletionSurface();
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
  syncTranslationCompletionSurface();

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
  renderTranslationBootstrap,
  resetTranslationForGmailRedo,
};
