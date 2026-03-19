import { fetchJson } from "./api.js";
import { appState, setActiveView } from "./state.js";

const translationState = {
  currentSeed: null,
  currentRowId: null,
  currentJob: null,
  currentJobId: "",
  uploadedSourcePath: "",
  uploadedSourceKey: "",
  pollTimer: null,
};

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

function sourceFileKey(file) {
  return `${file.name}:${file.size}:${file.lastModified}`;
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
  translationState.uploadedSourceKey = key;
  translationState.uploadedSourcePath = payload.normalized_payload.source_path || "";
  setFieldValue("translation-source-summary", [
    `Filename: ${payload.normalized_payload.source_filename || file.name}`,
    `Type: ${payload.normalized_payload.source_type || "unknown"}`,
    `Pages: ${payload.normalized_payload.page_count ?? "?"}`,
    `Saved path: ${payload.normalized_payload.source_path || ""}`,
  ].join("\n"));
  setDiagnostics("translation", payload, {
    hint: "Source upload complete.",
    open: false,
  });
  return translationState.uploadedSourcePath;
}

function collectTranslationSetupValues() {
  return {
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

function translationStatusSummary(job) {
  if (!job) {
    return "";
  }
  if (job.job_kind === "analyze") {
    return job.status === "completed"
      ? "Analyze complete. Review the advisor output or start the full translation."
      : job.status_text || "Analyze job is running.";
  }
  if (job.job_kind === "rebuild") {
    return job.status === "completed"
      ? "DOCX rebuild complete."
      : job.status_text || "DOCX rebuild is running.";
  }
  if (job.status === "completed") {
    return "Translation complete. Review the save form, artifacts, and review queue.";
  }
  if (job.status === "cancel_requested") {
    return "Cancellation requested. Waiting for the current page task to stop cleanly.";
  }
  if (job.status === "cancelled") {
    return "Translation cancelled. You can resume or rebuild from the current run folder.";
  }
  if (job.status === "failed") {
    return job.status_text || "Translation failed.";
  }
  return job.status_text || "Translation job is running.";
}

function applyTranslationSeed(seed, { rowId = null } = {}) {
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

export function getCurrentTranslationJobId() {
  return translationState.currentJobId || "";
}

export function collectCurrentTranslationSaveValues() {
  return collectTranslationSaveValues();
}

function renderTranslationResultCard(job) {
  const container = qs("translation-result");
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
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${job.status_text || "Translation job state available."}</strong>
        <p>${summaryLines.join("<br>")}</p>
      </div>
      <span class="status-chip ${job.status === "completed" ? "ok" : job.status === "failed" ? "bad" : job.status === "cancelled" ? "warn" : "info"}">${job.status}</span>
    </div>
  `;
}

function renderTranslationJob(job) {
  translationState.currentJob = job || null;
  translationState.currentJobId = job?.job_id || "";
  setFieldValue("translation-job-id", translationState.currentJobId);
  renderTranslationResultCard(job);
  setPanelStatus("translation", job ? (job.status === "failed" ? "bad" : "") : "", translationStatusSummary(job) || "Load a source file, then analyze or translate it in this browser workspace.");
  setDiagnostics("translation-job", job || { status: "idle", message: "No translation job loaded." }, {
    hint: "Latest progress, log tail, review queue, and failure context appear here.",
    open: Boolean(job && job.status !== "completed"),
  });
  setDownloadLink("translation-download-docx", job?.actions?.download_output_docx ? `/api/translation/jobs/${job.job_id}/artifact/output_docx?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "");
  setDownloadLink("translation-download-partial", job?.actions?.download_partial_docx ? `/api/translation/jobs/${job.job_id}/artifact/partial_docx?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "");
  setDownloadLink("translation-download-summary", job?.actions?.download_run_summary ? `/api/translation/jobs/${job.job_id}/artifact/run_summary?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "");
  setDownloadLink("translation-download-analyze", job?.actions?.download_analyze_report ? `/api/translation/jobs/${job.job_id}/artifact/analyze_report?mode=${appState.runtimeMode}&workspace=${appState.workspaceId}` : "");
  qs("translation-review-export").disabled = !job?.actions?.review_export;
  qs("translation-cancel").disabled = !job?.actions?.cancel;
  qs("translation-resume-btn").disabled = !job?.actions?.resume;
  qs("translation-rebuild").disabled = !(job?.actions?.rebuild || false);
  if (job?.result?.save_seed) {
    applyTranslationSeed(job.result.save_seed);
    setPanelStatus("translation-save", "", "Translation seed loaded from the completed run. Review the fields before saving.");
  }
  if (job && ["queued", "running", "cancel_requested"].includes(job.status)) {
    stopPolling();
    translationState.pollTimer = window.setTimeout(pollCurrentJob, 1500);
  } else {
    stopPolling();
  }
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
  applyTranslationSeed(item?.seed || blankSaveSeed(), { rowId: row.id || null });
  setActiveView("new-job");
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
}

function renderTranslationJobs(jobs) {
  const container = qs("translation-jobs-list");
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
}

async function handleTranslationSave() {
  const payload = await fetchJson("/api/translation/save-row", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      form_values: collectTranslationSaveValues(),
      seed_payload: translationState.currentSeed,
      row_id: translationState.currentRowId,
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
  qs("translation-new-save")?.addEventListener("click", resetTranslationSaveForm);
}

export { loadTranslationHistoryItem, refreshTranslationBootstrap, refreshTranslationHistory, renderTranslationBootstrap };
