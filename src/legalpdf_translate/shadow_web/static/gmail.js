import { fetchJson } from "./api.js";
import { appState, setActiveView } from "./state.js";
import {
  applyPreviewStateStartPage,
  clearConsumedReviewState,
  createClosedPreviewState,
  deriveGmailHomeCta,
  deriveGmailStage,
  isPreviewStateOpen,
  openPreviewState,
  readConsumedReviewState,
  setPreviewStatePage,
  shouldAutoOpenReview,
  shouldIgnoreReviewRowFocusTarget,
  writeConsumedReviewState,
} from "./gmail_review_state.js";

const AUTO_REFRESH_DELAY_MS = 220;
const AUTO_REFRESH_THROTTLE_MS = 1400;

const gmailState = {
  bootstrap: null,
  loadResult: null,
  activeSession: null,
  interpretationSeed: null,
  suggestedTranslationLaunch: null,
  selectionState: new Map(),
  reviewDrawerOpen: false,
  reviewFocusedAttachmentId: "",
  previewDrawerOpen: false,
  previewState: createClosedPreviewState(),
  sessionDrawerOpen: false,
  batchFinalizeDrawerOpen: false,
  batchFinalizeResult: null,
  stage: "idle",
  refreshInFlight: false,
  refreshTimer: 0,
  lastRefreshAt: 0,
  hooks: {},
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

function translationUiSnapshot() {
  return gmailState.hooks.getTranslationUiSnapshot?.() || {};
}

function interpretationUiSnapshot() {
  return gmailState.hooks.getInterpretationUiSnapshot?.() || {};
}

function maybeRestoreInterpretationSeedFromBootstrap() {
  if (gmailState.activeSession?.kind !== "interpretation" || !gmailState.interpretationSeed) {
    return;
  }
  const snapshot = interpretationUiSnapshot();
  if (snapshot.hasSeedData) {
    return;
  }
  gmailState.hooks.applyInterpretationSeed?.(gmailState.interpretationSeed, {
    activateTask: appState.activeView === "new-job",
    openReview: false,
  });
}

function currentGmailStage() {
  return deriveGmailStage({
    loadResult: gmailState.loadResult,
    activeSession: gmailState.activeSession,
    reviewDrawerOpen: gmailState.reviewDrawerOpen,
    translationUi: translationUiSnapshot(),
    interpretationUi: interpretationUiSnapshot(),
  });
}

function currentHomeCta() {
  return deriveGmailHomeCta({
    stage: gmailState.stage || currentGmailStage(),
    activeSession: gmailState.activeSession,
  });
}

function gmailHomeStatusMessage() {
  switch (gmailState.stage || currentGmailStage()) {
    case "translation_running":
    case "translation_save":
    case "translation_finalize":
    case "interpretation_review":
    case "interpretation_finalize":
      return "Gmail handoff is prepared. Resume Current Step when you are ready for the next bounded step.";
    default:
      return "Keep Gmail intake compact here. Open Attachment Review to choose files, preview the selected document, and decide where translation should start.";
  }
}

async function maybeAutoStartSuggestedTranslation(reason) {
  if (!gmailState.suggestedTranslationLaunch) {
    return false;
  }
  const launch = gmailState.suggestedTranslationLaunch;
  if (typeof gmailState.hooks.startTranslationLaunch === "function") {
    try {
      await gmailState.hooks.startTranslationLaunch(launch, { auto: true, reason });
      return true;
    } catch (error) {
      gmailState.hooks.applyTranslationLaunch?.(launch);
      setActiveView("new-job");
      throw error;
    }
  }
  gmailState.hooks.applyTranslationLaunch?.(launch);
  setActiveView("new-job");
  return false;
}

function runStageAction(action) {
  switch (action) {
    case "resume-translation-running":
      if (gmailState.suggestedTranslationLaunch) {
        gmailState.hooks.applyTranslationLaunch?.(gmailState.suggestedTranslationLaunch);
      }
      setActiveView("new-job");
      closeSessionDrawer();
      break;
    case "resume-translation-save":
      if (gmailState.suggestedTranslationLaunch) {
        gmailState.hooks.applyTranslationLaunch?.(gmailState.suggestedTranslationLaunch);
      }
      setActiveView("new-job");
      gmailState.hooks.openTranslationCompletionDrawer?.();
      closeSessionDrawer();
      break;
    case "resume-translation-finalize":
      openBatchFinalizeDrawer();
      break;
    case "resume-interpretation-review":
    case "resume-interpretation-finalize":
      if (gmailState.interpretationSeed) {
        gmailState.hooks.applyInterpretationSeed?.(gmailState.interpretationSeed, { openReview: true });
      } else {
        gmailState.hooks.openInterpretationReviewDrawer?.();
      }
      setActiveView("new-job");
      closeSessionDrawer();
      break;
    case "review":
      openReviewDrawer();
      break;
    case "open-intake":
    default:
      setActiveView("gmail-intake");
      break;
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

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const scaled = bytes / (1024 ** index);
  const precision = scaled >= 10 || index === 0 ? 0 : 1;
  return `${scaled.toFixed(precision)} ${units[index]}`;
}

function shortOutputFolderLabel(value) {
  const cleaned = String(value ?? "").trim();
  if (!cleaned) {
    return "Use workspace default";
  }
  const normalized = cleaned.replace(/[\\/]+$/, "");
  const parts = normalized.split(/[\\/]/).filter(Boolean);
  return parts.at(-1) || cleaned;
}

function currentWorkflowLabel() {
  return currentWorkflowKind() === "interpretation" ? "Interpretation notice" : "Translation batch";
}

function attachmentMime(attachment) {
  return String(attachment?.mime_type || "").trim().toLowerCase();
}

function isPdfAttachment(attachment) {
  return attachmentMime(attachment) === "application/pdf";
}

function isImageAttachment(attachment) {
  return attachmentMime(attachment).startsWith("image/");
}

function currentWorkflowKind() {
  return fieldValue("gmail-workflow-kind") === "interpretation" ? "interpretation" : "translation";
}

function bootstrapMessageContext() {
  return gmailState.bootstrap?.defaults?.message_context || {};
}

function gmailAttachments() {
  return gmailState.loadResult?.message?.attachments || [];
}

function getAttachmentById(attachmentId) {
  return gmailAttachments().find((item) => item.attachment_id === attachmentId) || null;
}

function currentReviewContext() {
  return {
    runtimeMode: appState.runtimeMode,
    workspaceId: appState.workspaceId,
  };
}

function sessionStorageHandle() {
  try {
    return window.sessionStorage || null;
  } catch {
    return null;
  }
}

function consumedReviewState() {
  return readConsumedReviewState(sessionStorageHandle(), currentReviewContext());
}

function rememberCurrentReviewEvent() {
  return writeConsumedReviewState(sessionStorageHandle(), currentReviewContext(), {
    reviewEventId: gmailState.bootstrap?.review_event_id,
    messageSignature: gmailState.bootstrap?.message_signature,
  });
}

function forgetConsumedReviewEvent() {
  clearConsumedReviewState(sessionStorageHandle(), currentReviewContext());
}

function applyBootstrapDefaults(data) {
  const defaults = data?.defaults || {};
  const messageContext = defaults.message_context || {};
  if (!fieldValue("gmail-message-id")) {
    setFieldValue("gmail-message-id", messageContext.message_id || "");
  }
  if (!fieldValue("gmail-thread-id")) {
    setFieldValue("gmail-thread-id", messageContext.thread_id || "");
  }
  if (!fieldValue("gmail-subject")) {
    setFieldValue("gmail-subject", messageContext.subject || "");
  }
  if (!fieldValue("gmail-account-email")) {
    setFieldValue("gmail-account-email", messageContext.account_email || "");
  }
  if (!fieldValue("gmail-output-dir")) {
    setFieldValue("gmail-output-dir", defaults.default_output_dir || "");
  }
  if (!fieldValue("gmail-target-lang")) {
    setFieldValue("gmail-target-lang", defaults.target_lang || "EN");
  }
}

function activeSessionAttachmentId(activeSession) {
  if (activeSession?.kind === "translation") {
    return activeSession.current_attachment?.attachment?.attachment_id || "";
  }
  if (activeSession?.kind === "interpretation") {
    return activeSession.attachment?.attachment?.attachment_id || "";
  }
  return "";
}

function resetPreviewState() {
  gmailState.previewState = createClosedPreviewState();
  setPreviewDrawerOpen(false);
}

function canEditStartPage(attachment) {
  return currentWorkflowKind() === "translation" && isPdfAttachment(attachment);
}

function clampStartPage(attachment, rawValue, pageCountOverride = null) {
  if (!attachment || !canEditStartPage(attachment)) {
    return 1;
  }
  const parsed = Number.parseInt(String(rawValue ?? "1").trim(), 10);
  let value = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  const pageCount = Number(pageCountOverride ?? (gmailState.selectionState.get(attachment.attachment_id)?.pageCount || 0));
  if (pageCount > 0) {
    value = Math.min(value, pageCount);
  }
  return Math.max(1, value);
}

function attachmentState(attachmentId) {
  const existing = gmailState.selectionState.get(attachmentId) || {};
  return {
    selected: Boolean(existing.selected),
    startPage: Number(existing.startPage || 1),
    pageCount: Number(existing.pageCount || 0),
  };
}

function setAttachmentState(attachmentId, nextValue) {
  gmailState.selectionState.set(attachmentId, {
    selected: Boolean(nextValue.selected),
    startPage: Math.max(1, Number(nextValue.startPage || 1)),
    pageCount: Math.max(0, Number(nextValue.pageCount || 0)),
  });
}

function ensureSelectionState(loadResult, activeSession) {
  const message = loadResult?.message || null;
  const next = new Map();
  for (const attachment of message?.attachments || []) {
    const existing = gmailState.selectionState.get(attachment.attachment_id) || {};
    next.set(attachment.attachment_id, {
      selected: Boolean(existing.selected),
      startPage: clampStartPage(attachment, existing.startPage || 1, existing.pageCount || 0),
      pageCount: Math.max(0, Number(existing.pageCount || 0)),
    });
  }
  if (activeSession?.kind === "translation") {
    for (const item of activeSession.attachments || []) {
      const attachment = item.attachment || {};
      next.set(attachment.attachment_id, {
        selected: true,
        startPage: clampStartPage(attachment, item.start_page || 1, item.page_count || 0),
        pageCount: Math.max(0, Number(item.page_count || 0)),
      });
    }
  }
  if (activeSession?.kind === "interpretation") {
    const attachmentId = activeSession.attachment?.attachment?.attachment_id || "";
    if (attachmentId) {
      next.set(attachmentId, {
        selected: true,
        startPage: 1,
        pageCount: Math.max(0, Number(activeSession.attachment?.page_count || 0)),
      });
    }
  }
  gmailState.selectionState = next;
  syncFocusedAttachment();
}

function syncFocusedAttachment() {
  const attachments = gmailAttachments();
  if (!attachments.length) {
    gmailState.reviewFocusedAttachmentId = "";
    resetPreviewState();
    return null;
  }
  const attachmentIds = new Set(attachments.map((attachment) => attachment.attachment_id));
  if (isPreviewStateOpen(gmailState.previewState) && !attachmentIds.has(gmailState.previewState.attachmentId)) {
    resetPreviewState();
  }
  let nextId = gmailState.reviewFocusedAttachmentId;
  if (!attachmentIds.has(nextId)) {
    nextId = "";
  }
  if (!nextId) {
    nextId = attachments.find((attachment) => attachmentState(attachment.attachment_id).selected)?.attachment_id || "";
  }
  if (!nextId) {
    nextId = activeSessionAttachmentId(gmailState.activeSession);
  }
  if (!attachmentIds.has(nextId)) {
    nextId = attachments[0]?.attachment_id || "";
  }
  gmailState.reviewFocusedAttachmentId = nextId;
  return getAttachmentById(nextId);
}

function focusAttachment(attachmentId) {
  const attachment = getAttachmentById(attachmentId);
  if (!attachment) {
    return null;
  }
  if (gmailState.reviewFocusedAttachmentId !== attachmentId) {
    gmailState.reviewFocusedAttachmentId = attachmentId;
  }
  return attachment;
}

function focusedAttachment() {
  return syncFocusedAttachment();
}

function previewAttachmentRecord() {
  if (!isPreviewStateOpen(gmailState.previewState)) {
    return null;
  }
  return getAttachmentById(gmailState.previewState.attachmentId);
}

function previewPageCount() {
  return Math.max(0, Number(gmailState.previewState.pageCount || 0));
}

function previewPage() {
  return Math.max(1, Number(gmailState.previewState.page || 1));
}

function resolvedPreviewHref() {
  const previewAttachment = previewAttachmentRecord();
  const previewHref = String(gmailState.previewState.previewHref || "").trim();
  if (!previewAttachment || !previewHref) {
    return "";
  }
  if (isPdfAttachment(previewAttachment)) {
    return `${previewHref}#page=${previewPage()}`;
  }
  return previewHref;
}

function setReviewDrawerOpen(open) {
  const backdrop = qs("gmail-review-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  const nextOpen = Boolean(open) && Boolean(gmailState.loadResult?.ok && gmailState.loadResult?.message);
  gmailState.reviewDrawerOpen = nextOpen;
  backdrop.classList.toggle("hidden", !nextOpen);
  backdrop.setAttribute("aria-hidden", nextOpen ? "false" : "true");
  document.body.dataset.gmailReviewDrawer = nextOpen ? "open" : "closed";
  if (nextOpen) {
    rememberCurrentReviewEvent();
  }
}

function openReviewDrawer() {
  if (!gmailState.loadResult?.ok || !gmailState.loadResult?.message) {
    return;
  }
  setReviewDrawerOpen(true);
}

function closeReviewDrawer() {
  setReviewDrawerOpen(false);
}

function setPreviewDrawerOpen(open) {
  const backdrop = qs("gmail-preview-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  const nextOpen = Boolean(open) && isPreviewStateOpen(gmailState.previewState);
  gmailState.previewDrawerOpen = nextOpen;
  backdrop.classList.toggle("hidden", !nextOpen);
  backdrop.setAttribute("aria-hidden", nextOpen ? "false" : "true");
  document.body.dataset.gmailPreviewDrawer = nextOpen ? "open" : "closed";
}

function openPreviewDrawer() {
  if (!isPreviewStateOpen(gmailState.previewState)) {
    return;
  }
  setPreviewDrawerOpen(true);
}

function closePreviewDrawer() {
  setPreviewDrawerOpen(false);
  resetPreviewState();
  renderReviewSurface();
}

function setSessionDrawerOpen(open) {
  const backdrop = qs("gmail-session-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  gmailState.sessionDrawerOpen = Boolean(open) && Boolean(gmailState.activeSession);
  backdrop.classList.toggle("hidden", !gmailState.sessionDrawerOpen);
  backdrop.setAttribute("aria-hidden", gmailState.sessionDrawerOpen ? "false" : "true");
  document.body.dataset.gmailSessionDrawer = gmailState.sessionDrawerOpen ? "open" : "closed";
}

function openSessionDrawer() {
  if (!gmailState.activeSession) {
    return;
  }
  setSessionDrawerOpen(true);
}

export function closeSessionDrawer() {
  setSessionDrawerOpen(false);
}

function setBatchFinalizeDrawerOpen(open) {
  const backdrop = qs("gmail-batch-finalize-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  const nextOpen = Boolean(open) && Boolean(gmailState.activeSession?.kind === "translation" && gmailState.activeSession?.completed);
  gmailState.batchFinalizeDrawerOpen = nextOpen;
  backdrop.classList.toggle("hidden", !nextOpen);
  backdrop.setAttribute("aria-hidden", nextOpen ? "false" : "true");
  document.body.dataset.gmailBatchFinalizeDrawer = nextOpen ? "open" : "closed";
}

function openBatchFinalizeDrawer() {
  if (!gmailState.activeSession?.kind || gmailState.activeSession.kind !== "translation" || !gmailState.activeSession.completed) {
    return;
  }
  renderBatchFinalizeSurface(gmailState.activeSession);
  setBatchFinalizeDrawerOpen(true);
}

function closeBatchFinalizeDrawer() {
  setBatchFinalizeDrawerOpen(false);
}

function renderBatchFinalizeSurface(activeSession) {
  const status = qs("gmail-batch-finalize-status");
  const summary = qs("gmail-batch-finalize-summary");
  const result = qs("gmail-batch-finalize-result");
  const button = qs("gmail-batch-finalize-run");
  if (!status || !summary || !result || !button) {
    return;
  }
  const available = Boolean(activeSession?.kind === "translation" && activeSession?.completed);
  button.disabled = !available;
  if (!available) {
    summary.className = "result-card empty-state";
    summary.textContent = "Finish every Gmail attachment first to open the final reply step.";
    result.className = "result-card empty-state";
    result.textContent = "Draft, honorários, and Gmail reply details appear here after finalization.";
    status.textContent = "Confirm every selected Gmail attachment before finalizing the batch reply.";
    closeBatchFinalizeDrawer();
    return;
  }
  const confirmedItems = activeSession.confirmed_items || [];
  const outputFolder = fieldValue("gmail-output-dir") || gmailState.bootstrap?.defaults?.default_output_dir || "Use workspace default";
  summary.className = "result-card";
  summary.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(activeSession.message?.subject || "Gmail batch ready to finalize.")}</strong>
        <p>${confirmedItems.length} confirmed attachment(s) are ready for the final Gmail reply.</p>
      </div>
      <span class="status-chip ok">${escapeHtml(activeSession.status || "confirmed")}</span>
    </div>
    <div class="result-grid">
      <div><h3>Target Language</h3><p>${escapeHtml(activeSession.selected_target_lang || "?")}</p></div>
      <div><h3>Confirmed Rows</h3><p>${confirmedItems.length}</p></div>
      <div><h3>Output Folder</h3><p title="${escapeHtml(outputFolder)}">${escapeHtml(shortOutputFolderLabel(outputFolder))}</p></div>
    </div>
  `;
  if (!gmailState.batchFinalizeResult) {
    result.className = "result-card empty-state";
    result.textContent = "Generate honorários and the Gmail reply draft when you are ready.";
    status.textContent = "All selected attachments are confirmed. Finalize the Gmail batch reply from this bounded surface.";
    return;
  }
  const payload = gmailState.batchFinalizeResult;
  const normalized = payload.normalized_payload || {};
  const draftStatus = normalized.gmail_draft_result?.ok
    ? "Draft ready"
    : payload.status === "local_only"
      ? "Local only"
      : payload.status === "draft_unavailable"
        ? "Draft unavailable"
        : payload.status === "draft_failed"
          ? "Draft failed"
          : "Ready";
  const tone = payload.status === "ok" ? "ok" : payload.status === "local_only" ? "warn" : "bad";
  status.textContent = payload.status === "ok"
    ? "Gmail batch reply draft is ready."
    : payload.status === "local_only"
      ? "Honorários were created locally, but the Gmail draft step stayed unavailable."
      : "Batch finalization completed with warnings. Review the result details here.";
  result.className = "result-card";
  result.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(status.textContent)}</strong>
        <p>${escapeHtml(normalized.docx_path || normalized.pdf_path || "Finalization output is available.")}</p>
      </div>
      <span class="status-chip ${tone === "ok" ? "ok" : tone === "warn" ? "warn" : "bad"}">${escapeHtml(draftStatus)}</span>
    </div>
    <div class="result-grid">
      <div><h3>DOCX</h3><p class="word-break">${escapeHtml(normalized.docx_path || "Unavailable")}</p></div>
      <div><h3>PDF</h3><p class="word-break">${escapeHtml(normalized.pdf_path || "Unavailable")}</p></div>
      <div><h3>Draft</h3><p>${escapeHtml(normalized.gmail_draft_result?.message || normalized.draft_prereqs?.message || draftStatus)}</p></div>
    </div>
  `;
}

function renderTranslationCompletionGmailStepCard(activeSession) {
  const card = qs("translation-gmail-step-card");
  const title = qs("translation-gmail-step-title");
  const copy = qs("translation-gmail-step-copy");
  const chip = qs("translation-gmail-step-chip");
  const button = qs("translation-gmail-confirm-current");
  if (!card || !title || !copy || !chip || !button) {
    return;
  }
  const translationUi = translationUiSnapshot();
  const show = Boolean(
    activeSession?.kind === "translation"
    && !activeSession?.completed
    && (translationUi.currentJobStatus === "completed" || translationUi.hasCompletionSurface),
  );
  card.classList.toggle("hidden", !show);
  button.disabled = !show;
  if (!show) {
    return;
  }
  const filename = activeSession.current_attachment?.attachment?.filename || "Current Gmail attachment";
  const batchLabel = activeSession.total_items
    ? `${activeSession.current_item_number || "?"}/${activeSession.total_items}`
    : "Batch step";
  title.textContent = `Gmail attachment ${batchLabel} is ready to confirm.`;
  copy.textContent = activeSession.current_item_number < activeSession.total_items
    ? `${filename} will be saved to the job log and the next attachment will start automatically.`
    : `${filename} will be saved to the job log and the final Gmail batch step will open next.`;
  chip.textContent = batchLabel;
}

function collectSelections() {
  const selections = [];
  for (const [attachmentId, item] of gmailState.selectionState.entries()) {
    if (!item.selected) {
      continue;
    }
    const attachment = getAttachmentById(attachmentId);
    if (!attachment) {
      continue;
    }
    selections.push({
      attachment_id: attachmentId,
      start_page: clampStartPage(attachment, item.startPage, item.pageCount),
    });
  }
  return selections;
}

function setWorkflowSelectionDefaults() {
  if (currentWorkflowKind() !== "interpretation") {
    return;
  }
  let kept = false;
  for (const attachment of gmailAttachments()) {
    const next = attachmentState(attachment.attachment_id);
    if (next.selected && !kept) {
      kept = true;
      next.startPage = 1;
    } else {
      next.selected = false;
      next.startPage = 1;
    }
    setAttachmentState(attachment.attachment_id, next);
  }
}

function updateAttachmentSelection(attachmentId, selected) {
  const attachment = getAttachmentById(attachmentId);
  if (!attachment) {
    return;
  }
  if (currentWorkflowKind() === "interpretation" && selected) {
    for (const other of gmailAttachments()) {
      const nextOther = attachmentState(other.attachment_id);
      nextOther.selected = false;
      nextOther.startPage = 1;
      setAttachmentState(other.attachment_id, nextOther);
    }
  }
  const next = attachmentState(attachmentId);
  next.selected = Boolean(selected);
  next.startPage = clampStartPage(attachment, next.startPage, next.pageCount);
  setAttachmentState(attachmentId, next);
  focusAttachment(attachmentId);
}

function updateAttachmentStartPage(attachmentId, value) {
  const attachment = getAttachmentById(attachmentId);
  if (!attachment) {
    return 1;
  }
  const next = attachmentState(attachmentId);
  next.startPage = clampStartPage(attachment, value, next.pageCount);
  setAttachmentState(attachmentId, next);
  return next.startPage;
}

function applyPreviewPageCount(attachmentId, pageCount) {
  const attachment = getAttachmentById(attachmentId);
  if (!attachment) {
    return;
  }
  const next = attachmentState(attachmentId);
  next.pageCount = Math.max(0, Number(pageCount || 0));
  next.startPage = clampStartPage(attachment, next.startPage, next.pageCount);
  setAttachmentState(attachmentId, next);
}

function renderMessageResult(loadResult) {
  const container = qs("gmail-message-result");
  const defaults = bootstrapMessageContext();
  const detailsHint = qs("gmail-intake-details-summary");
  if (!container) {
    return;
  }
  if (!loadResult) {
    const hasContext = Boolean(defaults.message_id || defaults.thread_id || defaults.subject || defaults.account_email);
    if (!hasContext) {
      container.classList.add("empty-state");
      container.textContent = "No Gmail message is loaded in this browser workspace yet.";
      if (detailsHint) {
        detailsHint.textContent = "Message and output overrides stay collapsed unless you need them.";
      }
      return;
    }
    container.classList.remove("empty-state");
    container.innerHTML = `
      <div class="result-header">
        <div>
          <strong>Extension handoff detected for this workspace.</strong>
          <p>${escapeHtml(defaults.subject || "Subject unavailable")}<br>${escapeHtml(defaults.account_email || "Account unavailable")}</p>
        </div>
        <span class="status-chip info">Pending load</span>
      </div>
      <div class="result-grid">
        <div><h3>Message ID</h3><p class="word-break">${escapeHtml(defaults.message_id || "Unavailable")}</p></div>
        <div><h3>Thread ID</h3><p class="word-break">${escapeHtml(defaults.thread_id || "Unavailable")}</p></div>
      </div>
    `;
    if (detailsHint) {
      detailsHint.textContent = "Extension defaults are ready; expand only if you need manual overrides.";
    }
    return;
  }
  const message = loadResult.message || {};
  const attachmentCount = (message.attachments || []).length;
  const outputFolder = fieldValue("gmail-output-dir") || gmailState.bootstrap?.defaults?.default_output_dir || "Use workspace default";
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(loadResult.status_message || "Gmail message state available.")}</strong>
        <p>${escapeHtml(message.subject || "No subject")}<br>${attachmentCount} supported attachment(s) from ${escapeHtml(message.account_email || "unknown account")}</p>
      </div>
      <span class="status-chip ${loadResult.ok ? "ok" : loadResult.classification === "unavailable" ? "warn" : "bad"}">${escapeHtml(loadResult.classification || (loadResult.ok ? "ready" : "failed"))}</span>
    </div>
    <div class="result-grid">
      <div><h3>Workflow</h3><p>${currentWorkflowKind() === "interpretation" ? "Interpretation notice" : "Translation batch"}</p></div>
      <div><h3>Attachments</h3><p>${attachmentCount}</p></div>
      <div><h3>Output Folder</h3><p class="word-break">${escapeHtml(outputFolder)}</p></div>
    </div>
  `;
  if (detailsHint) {
    detailsHint.textContent = "Message identifiers, account, and output overrides stay out of the way unless you need them.";
  }
}

function renderReviewSummary(loadResult) {
  const summary = qs("gmail-review-summary");
  const summaryGrid = qs("gmail-review-summary-grid");
  const summaryDetails = qs("gmail-review-summary-details");
  const reviewStatus = qs("gmail-review-status");
  const reviewOpenButton = qs("gmail-open-review");
  const attachments = loadResult?.message?.attachments || [];
  if (!summary || !summaryGrid || !reviewStatus || !reviewOpenButton) {
    return;
  }
  reviewOpenButton.disabled = !(loadResult?.ok && loadResult?.message);
  if (!reviewOpenButton.dataset.defaultLabel) {
    reviewOpenButton.dataset.defaultLabel = reviewOpenButton.textContent;
  }
  reviewOpenButton.textContent = reviewOpenButton.dataset.defaultLabel;
  if (!loadResult?.ok || !loadResult?.message) {
    summary.className = "result-card empty-state";
    summary.textContent = "Load the exact Gmail message to open attachment review.";
    summaryGrid.innerHTML = "";
    reviewStatus.textContent = "Choose the Gmail workflow, select the files you want, and open preview only when you need to inspect a document.";
    if (summaryDetails) {
      summaryDetails.open = false;
    }
    return;
  }
  const message = loadResult.message;
  const selectedCount = collectSelections().length;
  const outputFolder = fieldValue("gmail-output-dir") || gmailState.bootstrap?.defaults?.default_output_dir || "Use workspace default";
  const outputFolderLabel = shortOutputFolderLabel(outputFolder);
  summary.className = "result-card";
  summary.innerHTML = `
    <div class="gmail-review-summary-card">
      <div class="gmail-review-summary-copy">
        <strong>${escapeHtml(message.subject || "No subject")}</strong>
        <p>${attachments.length} supported attachment(s) ready for review</p>
      </div>
      <div class="gmail-review-summary-metrics">
        <div><h3>Workflow</h3><p>${currentWorkflowLabel()}</p></div>
        <div><h3>Folder</h3><p title="${escapeHtml(outputFolder)}">${escapeHtml(outputFolderLabel)}</p></div>
      </div>
      <span class="status-chip ${selectedCount ? "ok" : "info"}">${selectedCount ? `${selectedCount} selected` : "Review ready"}</span>
    </div>
  `;
  summaryGrid.innerHTML = `
    <div><h3>Sender</h3><p class="word-break">${escapeHtml(message.from_header || "Unavailable")}</p></div>
    <div><h3>Account</h3><p class="word-break">${escapeHtml(message.account_email || "Unavailable")}</p></div>
    <div><h3>Message ID</h3><p class="word-break">${escapeHtml(message.message_id || "Unavailable")}</p></div>
    <div><h3>Thread ID</h3><p class="word-break">${escapeHtml(message.thread_id || "Unavailable")}</p></div>
    <div><h3>Output Folder</h3><p class="word-break">${escapeHtml(outputFolder)}</p></div>
  `;
  reviewStatus.textContent = currentWorkflowKind() === "interpretation"
    ? "Choose the single notice you want to process. Preview stays optional and the handoff will still begin from page 1."
    : "Select the files you want. Open Preview only when you need to inspect a document or set the start page precisely.";
}

function renderAttachmentList(loadResult) {
  const container = qs("gmail-attachment-list");
  const startHeading = qs("gmail-review-start-heading");
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (startHeading) {
    startHeading.textContent = currentWorkflowKind() === "interpretation" ? "Notice" : "Start";
  }
  const attachments = loadResult?.message?.attachments || [];
  if (!attachments.length) {
    container.innerHTML = '<tr><td colspan="5" class="empty-state">No supported attachments are available for the loaded Gmail message.</td></tr>';
    return;
  }
  const interpretationWorkflow = currentWorkflowKind() === "interpretation";
  const selectedInputType = interpretationWorkflow ? "radio" : "checkbox";
  syncFocusedAttachment();
  for (const attachment of attachments) {
    const state = attachmentState(attachment.attachment_id);
    const selected = state.selected;
    const focused = gmailState.reviewFocusedAttachmentId === attachment.attachment_id;
    const canEditStart = canEditStartPage(attachment);
    const row = document.createElement("tr");
    row.className = [
      "gmail-review-row",
      selected ? "is-selected" : "",
      focused ? "is-focused" : "",
    ].filter(Boolean).join(" ");
    row.dataset.attachmentRow = attachment.attachment_id;
    row.tabIndex = 0;
    row.innerHTML = `
      <td>
        <label class="checkbox-inline gmail-review-select">
          <input
            type="${selectedInputType}"
            name="gmail-review-selection"
            data-attachment-checkbox="${escapeHtml(attachment.attachment_id)}"
            ${selected ? "checked" : ""}
          >
          <span class="gmail-review-row-label">${selected ? "Selected" : "Select"}</span>
        </label>
      </td>
      <td class="gmail-review-file-cell">
        <strong class="gmail-review-file-name" title="${escapeHtml(attachment.filename || "Attachment")}">${escapeHtml(attachment.filename || "Attachment")}</strong>
      </td>
      <td title="${escapeHtml(attachment.mime_type || "Unknown")}">${escapeHtml(attachment.mime_type || "Unknown")}</td>
      <td>${escapeHtml(formatBytes(attachment.size_bytes || 0))}</td>
      <td>
        ${canEditStart
          ? `<input type="number" class="attachment-start-page" min="1" step="1" value="${escapeHtml(String(clampStartPage(attachment, state.startPage, state.pageCount)))}" data-attachment-start-page="${escapeHtml(attachment.attachment_id)}">`
          : `<span class="gmail-review-start-static">${interpretationWorkflow ? "1" : "1"}</span>`}
      </td>
    `;
    container.appendChild(row);
  }
}

function renderReviewDetail() {
  const container = qs("gmail-review-detail");
  if (!container) {
    return;
  }
  const attachment = focusedAttachment();
  if (!attachment) {
    container.className = "result-card empty-state";
    container.textContent = "Select an attachment row to inspect it, preview it, and set the starting page.";
    return;
  }
  const state = attachmentState(attachment.attachment_id);
  const canEditStart = canEditStartPage(attachment);
  const previewLoaded = isPreviewStateOpen(gmailState.previewState) && gmailState.previewState.attachmentId === attachment.attachment_id;
  const pageCountText = state.pageCount > 0
    ? `${state.pageCount} ${state.pageCount === 1 ? "page" : "pages"}`
    : "Page count loads when you preview";
  container.className = "result-card";
  container.innerHTML = `
    <div class="gmail-review-detail-strip">
      <div class="gmail-review-detail-primary">
        <strong class="word-break" title="${escapeHtml(attachment.filename || "Attachment")}">${escapeHtml(attachment.filename || "Attachment")}</strong>
        <p class="gmail-review-detail-meta">${escapeHtml(pageCountText)}${previewLoaded ? " · Preview ready" : ""}</p>
      </div>
      <div class="gmail-review-detail-actions">
        ${canEditStart
          ? `<div class="field gmail-review-start-field">
              <label for="gmail-review-detail-start">Start Page</label>
              <input id="gmail-review-detail-start" type="number" min="1" step="1" value="${escapeHtml(String(clampStartPage(attachment, state.startPage, state.pageCount)))}" data-detail-start-page="${escapeHtml(attachment.attachment_id)}">
            </div>`
          : ""}
        <button type="button" class="ghost-button" id="gmail-preview-selected" data-preview-selected="${escapeHtml(attachment.attachment_id)}">Preview</button>
      </div>
    </div>
  `;
}

function renderPreviewPanel() {
  const container = qs("gmail-preview-frame");
  const summary = qs("gmail-preview-summary");
  const status = qs("gmail-preview-status");
  const openTab = qs("gmail-preview-open-tab");
  const applyButton = qs("gmail-preview-apply");
  const prevButton = qs("gmail-preview-prev");
  const nextButton = qs("gmail-preview-next");
  const pageInput = qs("gmail-preview-page");
  const attachment = focusedAttachment();
  const previewAttachment = previewAttachmentRecord();
  const previewHref = resolvedPreviewHref();
  if (!container || !summary || !status || !openTab || !applyButton || !prevButton || !nextButton || !pageInput) {
    return;
  }
  if (!applyButton.dataset.defaultLabel) {
    applyButton.dataset.defaultLabel = applyButton.textContent;
  }
  pageInput.disabled = true;
  prevButton.disabled = true;
  nextButton.disabled = true;
  pageInput.min = "1";
  pageInput.max = "1";
  pageInput.value = "1";
  openTab.classList.add("hidden");
  openTab.href = "#";
  applyButton.textContent = applyButton.dataset.defaultLabel;
  applyButton.disabled = true;
  if (!previewAttachment || !previewHref) {
    summary.className = "result-card empty-state";
    summary.textContent = "Choose Preview from the review drawer to inspect an attachment here.";
    container.className = "gmail-inline-preview empty-state";
    container.textContent = "Preview opens here when requested.";
    status.textContent = attachment
      ? `Preview ${attachment.filename || "the current attachment"} when you need to inspect it more closely.`
      : "Open preview when you need to inspect the current attachment more closely.";
    return;
  }
  const canApply = canEditStartPage(previewAttachment);
  summary.className = "result-card";
  summary.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(previewAttachment.filename || "Attachment preview")}</strong>
        <p>${previewPageCount() > 0 ? `${previewPageCount()} page(s) available` : "Preview ready"}</p>
      </div>
      <span class="status-chip ${canApply ? "info" : "ok"}">${canApply ? `Page ${previewPage()}` : "Inspect only"}</span>
    </div>
  `;
  openTab.classList.remove("hidden");
  openTab.href = previewHref;
  const pageCount = previewPageCount();
  const page = previewPage();
  if (isPdfAttachment(previewAttachment)) {
    pageInput.disabled = false;
    prevButton.disabled = page <= 1;
    nextButton.disabled = pageCount > 0 ? page >= pageCount : false;
    pageInput.max = String(Math.max(1, pageCount || page));
    pageInput.value = String(page);
    applyButton.disabled = !canApply;
    applyButton.textContent = canApply ? applyButton.dataset.defaultLabel : "Preview only";
    container.className = "gmail-inline-preview";
    container.innerHTML = `
      <iframe
        class="gmail-inline-preview-frame"
        src="${escapeHtml(previewHref)}"
        title="${escapeHtml(`Preview for ${previewAttachment.filename || "attachment"}`)}"
      ></iframe>
    `;
    status.textContent = canApply
      ? (pageCount > 0
        ? `Previewing page ${page} of ${pageCount}. Use current page when you want it to become the review start page.`
        : `Previewing page ${page}. Use current page when you want it to become the review start page.`)
      : (pageCount > 0
        ? `Previewing page ${page} of ${pageCount}. This workflow still prepares from page 1.`
        : `Previewing page ${page}. This workflow still prepares from page 1.`);
    return;
  }
  container.className = "gmail-inline-preview";
  if (isImageAttachment(previewAttachment)) {
    applyButton.disabled = true;
    applyButton.textContent = "Preview only";
    container.innerHTML = `
      <div class="gmail-inline-preview-image-shell">
        <img
          class="gmail-inline-preview-image"
          src="${escapeHtml(previewHref)}"
          alt="${escapeHtml(previewAttachment.filename || "Attachment preview")}"
        >
      </div>
    `;
    status.textContent = "Image preview is shown inline. Start page stays fixed at 1 for this attachment.";
    return;
  }
  applyButton.disabled = true;
  applyButton.textContent = "Preview only";
  container.className = "gmail-inline-preview empty-state";
  container.innerHTML = `Open <strong>${escapeHtml(previewAttachment.filename || "the preview")}</strong> in a new tab for a full attachment view.`;
  status.textContent = "This attachment type is available through the new-tab fallback.";
}

function renderResumeCard(activeSession) {
  const container = qs("gmail-resume-result");
  const button = qs("gmail-resume-step");
  gmailState.stage = currentGmailStage();
  const cta = currentHomeCta();
  if (button) {
    button.classList.toggle("hidden", !cta.visible);
    button.disabled = !cta.visible;
    button.textContent = cta.label || "Resume Current Step";
    button.dataset.gmailAction = cta.action || "";
  }
  if (!container) {
    return;
  }
  if (!cta.visible || !activeSession) {
    container.classList.add("hidden");
    container.classList.add("empty-state");
    container.textContent = "No Gmail step is waiting yet.";
    return;
  }
  let summaryGrid = "";
  if (activeSession.kind === "translation") {
    const currentAttachment = activeSession.current_attachment?.attachment?.filename || "Current attachment";
    const batchLabel = activeSession.total_items
      ? `${activeSession.current_item_number || "?"}/${activeSession.total_items}`
      : "Batch ready";
    summaryGrid = `
      <div class="result-grid">
        <div><h3>Stage</h3><p>${escapeHtml(gmailState.stage.replaceAll("_", " "))}</p></div>
        <div><h3>Batch</h3><p>${escapeHtml(batchLabel)}</p></div>
        <div><h3>Current File</h3><p class="word-break">${escapeHtml(currentAttachment)}</p></div>
      </div>
    `;
  } else if (activeSession.kind === "interpretation") {
    const noticeName = activeSession.attachment?.attachment?.filename || "Prepared notice";
    summaryGrid = `
      <div class="result-grid">
        <div><h3>Stage</h3><p>${escapeHtml(gmailState.stage.replaceAll("_", " "))}</p></div>
        <div><h3>Notice</h3><p class="word-break">${escapeHtml(noticeName)}</p></div>
      </div>
    `;
  }
  container.classList.remove("hidden");
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(cta.title || "Resume Current Step")}</strong>
        <p>${escapeHtml(cta.description || "Continue the active Gmail step when you are ready.")}</p>
      </div>
      <span class="status-chip ${cta.tone === "ok" ? "ok" : "info"}">${escapeHtml(activeSession.status || "ready")}</span>
    </div>
    ${summaryGrid}
  `;
}

function renderSessionResult(activeSession) {
  const container = qs("gmail-session-result");
  if (!container) {
    return;
  }
  if (!activeSession) {
    container.classList.add("empty-state");
    container.textContent = "Prepare a Gmail session to keep batch progression, interpretation notice state, and draft-finalization context in one browser workspace.";
    return;
  }
  container.classList.remove("empty-state");
  if (activeSession.kind === "translation") {
    const current = activeSession.current_attachment?.attachment || {};
    container.innerHTML = `
      <div class="result-header">
        <div>
          <strong>Gmail batch ${activeSession.current_item_number}/${activeSession.total_items}</strong>
          <p>${activeSession.completed ? "All attachments confirmed. Finalize the batch reply when ready." : `Current attachment: ${escapeHtml(current.filename || "Unavailable")}`}</p>
        </div>
        <span class="status-chip ${activeSession.completed ? "ok" : "info"}">${escapeHtml(activeSession.status || "prepared")}</span>
      </div>
      <div class="result-grid">
        <div><h3>Subject</h3><p>${escapeHtml(activeSession.message?.subject || "Unavailable")}</p></div>
        <div><h3>Target Language</h3><p>${escapeHtml(activeSession.selected_target_lang || "?")}</p></div>
        <div><h3>Confirmed Rows</h3><p>${(activeSession.confirmed_items || []).length}</p></div>
        <div><h3>Session Report</h3><p class="word-break">${escapeHtml(activeSession.session_report_path || "Unavailable")}</p></div>
      </div>
    `;
    return;
  }
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>Gmail interpretation notice ready</strong>
        <p>${escapeHtml(activeSession.attachment?.attachment?.filename || "No downloaded notice")} | ${escapeHtml(activeSession.message?.subject || "No subject")}</p>
      </div>
      <span class="status-chip info">${escapeHtml(activeSession.status || "prepared")}</span>
    </div>
    <div class="result-grid">
      <div><h3>Notice PDF</h3><p class="word-break">${escapeHtml(activeSession.attachment?.saved_path || "Unavailable")}</p></div>
      <div><h3>Session Report</h3><p class="word-break">${escapeHtml(activeSession.session_report_path || "Unavailable")}</p></div>
    </div>
  `;
}

function renderWorkspaceStrip() {
  const strip = qs("gmail-workspace-strip");
  if (!strip) {
    return;
  }
  const interpretationMode = String(interpretationUiSnapshot().workspaceMode || "").trim();
  const interpretationFocusedShell = appState.activeView === "new-job"
    && (interpretationMode === "gmail_review" || interpretationMode === "gmail_completed");
  const show = !interpretationFocusedShell && Boolean(gmailState.loadResult || gmailState.activeSession);
  strip.classList.toggle("hidden", !show);
  if (!show) {
    return;
  }
  const title = qs("gmail-workspace-strip-title");
  const copy = qs("gmail-workspace-strip-copy");
  const action = qs("gmail-workspace-strip-action");
  gmailState.stage = currentGmailStage();
  const cta = currentHomeCta();
  if (gmailState.activeSession && cta.visible) {
    title.textContent = cta.title || "A Gmail step is ready.";
    copy.textContent = cta.description || "Resume the current Gmail step when you are ready.";
    if (action) {
      action.textContent = cta.label || "Resume Current Step";
      action.dataset.gmailStripAction = cta.action || "";
    }
    return;
  }
  title.textContent = "A Gmail message is loaded for this workspace.";
  copy.textContent = "Open Gmail intake to review attachments and choose the right workflow before you continue.";
  if (action) {
    action.textContent = "Open Gmail Intake";
    action.dataset.gmailStripAction = "open-intake";
  }
}

function updatePrepareActionState() {
  const button = qs("gmail-prepare-session");
  if (!button) {
    return;
  }
  const selections = collectSelections();
  let label = currentWorkflowKind() === "interpretation"
    ? "Prepare notice"
    : "Prepare selected";
  let disabled = false;
  if (!gmailState.loadResult?.ok || !gmailState.loadResult?.message) {
    label = "Load Exact Gmail Message First";
    disabled = true;
  } else if (!selections.length) {
    label = currentWorkflowKind() === "interpretation"
      ? "Select One Notice To Continue"
      : "Select Attachments To Continue";
    disabled = true;
  }
  button.textContent = label;
  button.dataset.defaultLabel = label;
  button.disabled = disabled;
}

function syncShellState() {
  gmailState.stage = currentGmailStage();
  if (appState.bootstrap?.normalized_payload) {
    appState.bootstrap.normalized_payload.gmail = {
      ...(appState.bootstrap.normalized_payload.gmail || {}),
      ...gmailState.bootstrap,
      load_result: gmailState.loadResult,
      active_session: gmailState.activeSession,
      interpretation_seed: gmailState.interpretationSeed,
      suggested_translation_launch: gmailState.suggestedTranslationLaunch,
      stage: gmailState.stage,
    };
  }
  renderWorkspaceStrip();
  window.dispatchEvent(new CustomEvent("legalpdf:shell-state-updated"));
}

function updateSessionButtons() {
  const activeSession = gmailState.activeSession;
  const translationReady = Boolean(gmailState.suggestedTranslationLaunch);
  const interpretationReady = Boolean(gmailState.interpretationSeed);
  const sessionAvailable = Boolean(activeSession);
  const rules = [
    ["gmail-load-translation-launch", activeSession?.kind === "translation" && translationReady],
    ["gmail-confirm-translation", activeSession?.kind === "translation"],
    ["gmail-finalize-batch", activeSession?.kind === "translation" && activeSession.completed],
    ["gmail-load-interpretation-seed", activeSession?.kind === "interpretation" && interpretationReady],
    ["gmail-finalize-interpretation", activeSession?.kind === "interpretation"],
  ];
  for (const [id, enabled] of rules) {
    const button = qs(id);
    if (!button) {
      continue;
    }
    button.disabled = !enabled;
    button.classList.toggle("hidden", !enabled);
  }
  if (!sessionAvailable) {
    closeSessionDrawer();
  }
}

function renderReviewSurface() {
  renderReviewSummary(gmailState.loadResult);
  renderAttachmentList(gmailState.loadResult);
  renderReviewDetail();
  renderPreviewPanel();
  updatePrepareActionState();
}

function maybeAutoOpenReview() {
  if (gmailState.reviewDrawerOpen) {
    rememberCurrentReviewEvent();
    return false;
  }
  const consumed = consumedReviewState();
  const shouldOpen = shouldAutoOpenReview({
    reviewEventId: gmailState.bootstrap?.review_event_id,
    messageSignature: gmailState.bootstrap?.message_signature,
    consumedReviewEventId: consumed.reviewEventId,
    consumedMessageSignature: consumed.messageSignature,
    loadResult: gmailState.loadResult,
    activeSession: gmailState.activeSession,
  });
  if (shouldOpen) {
    openReviewDrawer();
  }
  return shouldOpen;
}

function mergeBootstrapPayload(gmailPayload) {
  gmailState.bootstrap = {
    ...(gmailState.bootstrap || {}),
    ...(gmailPayload || {}),
  };
}

export function renderGmailBootstrap(payload) {
  const gmailPayload = payload.normalized_payload.gmail || {};
  mergeBootstrapPayload(gmailPayload);
  gmailState.loadResult = gmailPayload.load_result || null;
  gmailState.activeSession = gmailPayload.active_session || null;
  gmailState.interpretationSeed = gmailPayload.interpretation_seed || null;
  gmailState.suggestedTranslationLaunch = gmailPayload.suggested_translation_launch || null;
  applyBootstrapDefaults(gmailPayload);
  maybeRestoreInterpretationSeedFromBootstrap();
  ensureSelectionState(gmailState.loadResult, gmailState.activeSession);
  renderMessageResult(gmailState.loadResult);
  renderReviewSurface();
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderTranslationCompletionGmailStepCard(gmailState.activeSession);
  renderBatchFinalizeSurface(gmailState.activeSession);
  updateSessionButtons();
  maybeAutoOpenReview();
  setPanelStatus(
    "gmail",
    gmailState.loadResult?.ok ? "ok" : "",
    gmailHomeStatusMessage(),
  );
  setPanelStatus(
    "gmail-session",
    gmailState.activeSession ? "ok" : "",
    gmailState.activeSession
      ? `Gmail ${gmailState.activeSession.kind} session is active in workspace ${appState.workspaceId}.`
      : "No Gmail translation batch or interpretation notice is active in this workspace yet.",
  );
  syncShellState();
}

async function refreshGmailState({ auto = false } = {}) {
  if (gmailState.refreshInFlight) {
    return null;
  }
  gmailState.refreshInFlight = true;
  try {
    const payload = await fetchJson("/api/gmail/bootstrap", appState);
    renderGmailBootstrap({ normalized_payload: { gmail: payload.normalized_payload } });
    gmailState.lastRefreshAt = Date.now();
    if (!auto) {
      setDiagnostics("gmail", payload, { hint: "Gmail workspace state refreshed.", open: false });
    }
    return payload;
  } finally {
    gmailState.refreshInFlight = false;
  }
}

async function loadMessage() {
  const payload = await fetchJson("/api/gmail/load-message", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message_context: {
        message_id: fieldValue("gmail-message-id"),
        thread_id: fieldValue("gmail-thread-id"),
        subject: fieldValue("gmail-subject"),
        account_email: fieldValue("gmail-account-email"),
      },
    }),
  });
  mergeBootstrapPayload({
    review_event_id: payload.normalized_payload.review_event_id,
    message_signature: payload.normalized_payload.message_signature,
  });
  gmailState.loadResult = payload.normalized_payload.load_result || null;
  gmailState.activeSession = null;
  gmailState.interpretationSeed = null;
  gmailState.suggestedTranslationLaunch = null;
  ensureSelectionState(gmailState.loadResult, null);
  resetPreviewState();
  gmailState.batchFinalizeResult = null;
  renderMessageResult(gmailState.loadResult);
  renderReviewSurface();
  renderResumeCard(null);
  renderSessionResult(null);
  renderTranslationCompletionGmailStepCard(null);
  renderBatchFinalizeSurface(null);
  updateSessionButtons();
  setPanelStatus("gmail", payload.status === "ok" ? "ok" : payload.status === "unavailable" ? "warn" : "bad", payload.normalized_payload.load_result?.status_message || "Gmail message load complete.");
  setDiagnostics("gmail", payload, { hint: payload.normalized_payload.load_result?.status_message || "Gmail message load complete.", open: payload.status !== "ok" });
  const details = qs("gmail-intake-details");
  if (details) {
    details.open = false;
  }
  if (gmailState.loadResult?.ok && gmailState.loadResult?.message) {
    openReviewDrawer();
  }
  syncShellState();
}

async function previewAttachment(attachmentId) {
  const attachment = focusAttachment(attachmentId);
  if (!attachment) {
    return;
  }
  const currentState = attachmentState(attachmentId);
  const payload = await fetchJson("/api/gmail/preview-attachment", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ attachment_id: attachmentId }),
  });
  applyPreviewPageCount(attachmentId, payload.normalized_payload.page_count || 0);
  gmailState.previewState = openPreviewState({
    attachmentId,
    previewHref: payload.normalized_payload.preview_href || "",
    previewMimeType: payload.normalized_payload.attachment?.mime_type || attachment.mime_type || "",
    pageCount: attachmentState(attachmentId).pageCount,
    currentStartPage: currentState.startPage,
    editable: canEditStartPage(attachment),
  });
  renderAttachmentList(gmailState.loadResult);
  renderReviewDetail();
  renderPreviewPanel();
  openPreviewDrawer();
  setDiagnostics("gmail", payload, { hint: `Preview loaded for ${payload.normalized_payload.attachment?.filename || "attachment"}.`, open: false });
}

async function prepareSession() {
  const payload = await fetchJson("/api/gmail/prepare-session", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      workflow_kind: currentWorkflowKind(),
      target_lang: fieldValue("gmail-target-lang"),
      output_dir: fieldValue("gmail-output-dir"),
      selections: collectSelections(),
    }),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  gmailState.interpretationSeed = payload.normalized_payload.interpretation_seed || null;
  gmailState.suggestedTranslationLaunch = payload.normalized_payload.suggested_translation_launch || null;
  gmailState.batchFinalizeResult = null;
  ensureSelectionState(gmailState.loadResult, gmailState.activeSession);
  resetPreviewState();
  renderReviewSurface();
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderTranslationCompletionGmailStepCard(gmailState.activeSession);
  renderBatchFinalizeSurface(gmailState.activeSession);
  updateSessionButtons();
  setDiagnostics("gmail", payload, { hint: "Gmail session prepared.", open: false });
  closePreviewDrawer();
  closeReviewDrawer();
  closeSessionDrawer();
  closeBatchFinalizeDrawer();
  if (gmailState.suggestedTranslationLaunch) {
    await maybeAutoStartSuggestedTranslation("gmail-prepare");
  } else if (gmailState.interpretationSeed) {
    gmailState.hooks.applyInterpretationSeed?.(gmailState.interpretationSeed, { openReview: true });
    setActiveView("new-job");
  }
  gmailState.stage = currentGmailStage();
  setPanelStatus("gmail", "ok", gmailHomeStatusMessage());
  syncShellState();
}

async function confirmCurrentTranslation() {
  const jobId = gmailState.hooks.getCurrentTranslationJobId?.() || "";
  if (!jobId) {
    throw new Error("Run a translation job for the current Gmail attachment first.");
  }
  const payload = await fetchJson("/api/gmail/batch/confirm-current", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_id: jobId,
      form_values: gmailState.hooks.collectCurrentTranslationSaveValues?.() || {},
      row_id: qs("translation-row-id")?.value || null,
    }),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  gmailState.suggestedTranslationLaunch = payload.normalized_payload.suggested_translation_launch || null;
  ensureSelectionState(gmailState.loadResult, gmailState.activeSession);
  renderReviewSurface();
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderTranslationCompletionGmailStepCard(gmailState.activeSession);
  renderBatchFinalizeSurface(gmailState.activeSession);
  updateSessionButtons();
  setDiagnostics("gmail-session", payload, { hint: "Current Gmail attachment confirmed and saved to the job log.", open: false });
  if (gmailState.suggestedTranslationLaunch) {
    await maybeAutoStartSuggestedTranslation("gmail-confirm-next");
  } else if (gmailState.activeSession?.kind === "translation" && gmailState.activeSession.completed) {
    gmailState.hooks.closeTranslationCompletionDrawer?.();
    openBatchFinalizeDrawer();
  }
  syncShellState();
  window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
}

async function finalizeBatch() {
  const payload = await fetchJson("/api/gmail/batch/finalize", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile_id: qs("profile-id")?.value || "",
      output_filename: fieldValue("gmail-batch-final-output-filename") || fieldValue("gmail-final-output-filename"),
    }),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  gmailState.batchFinalizeResult = payload;
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderBatchFinalizeSurface(gmailState.activeSession);
  updateSessionButtons();
  setDiagnostics("gmail-batch-finalize", payload, { hint: payload.status === "ok" ? "Gmail batch reply draft is ready." : "Gmail batch finalization completed with warnings.", open: payload.status !== "ok" });
  syncShellState();
}

async function finalizeInterpretation() {
  await gmailState.hooks.prepareInterpretationAction?.("gmail-finalize");
  const payload = await fetchJson("/api/gmail/interpretation/finalize", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      form_values: gmailState.hooks.collectInterpretationFormValues?.() || {},
      profile_id: qs("profile-id")?.value || "",
      service_same_checked: Boolean(qs("service-same")?.checked),
      output_filename: fieldValue("gmail-final-output-filename"),
    }),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderTranslationCompletionGmailStepCard(gmailState.activeSession);
  updateSessionButtons();
  gmailState.hooks.renderInterpretationExportResult?.(payload);
  gmailState.hooks.renderInterpretationGmailResult?.(payload);
  setDiagnostics("gmail-session", payload, { hint: payload.status === "ok" ? "Gmail interpretation reply draft is ready." : "Interpretation Gmail finalization completed with warnings.", open: payload.status !== "ok" });
  syncShellState();
}

function clearScheduledRefresh() {
  if (gmailState.refreshTimer) {
    window.clearTimeout(gmailState.refreshTimer);
    gmailState.refreshTimer = 0;
  }
}

function scheduleFocusedRefresh() {
  if (appState.activeView !== "gmail-intake") {
    clearScheduledRefresh();
    return;
  }
  clearScheduledRefresh();
  const elapsed = Date.now() - gmailState.lastRefreshAt;
  const delay = Math.max(AUTO_REFRESH_DELAY_MS, AUTO_REFRESH_THROTTLE_MS - elapsed);
  gmailState.refreshTimer = window.setTimeout(async () => {
    gmailState.refreshTimer = 0;
    try {
      await refreshGmailState({ auto: true });
    } catch {
      // Silent auto-refresh failures should not steal focus from the operator.
    }
  }, delay);
}

export function initializeGmailUi(hooks) {
  gmailState.hooks = hooks || {};
  setDiagnostics("gmail", { status: "idle", message: "No Gmail action has run yet." }, { hint: "Exact-message load, attachment preview, and session preparation details appear here.", open: false });
  setDiagnostics("gmail-session", { status: "idle", message: "No Gmail batch or interpretation finalization has run yet." }, { hint: "Batch progression, staged attachments, export status, and Gmail draft details appear here.", open: false });
  setDiagnostics("gmail-batch-finalize", { status: "idle", message: "No Gmail batch finalization has run yet." }, { hint: "Final draft request details and honorários export diagnostics appear here.", open: false });
  document.body.dataset.gmailReviewDrawer = "closed";
  document.body.dataset.gmailPreviewDrawer = "closed";
  document.body.dataset.gmailSessionDrawer = "closed";
  document.body.dataset.gmailBatchFinalizeDrawer = "closed";

  qs("gmail-context-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusy(["gmail-load-message"], { "gmail-load-message": "Loading..." }, async () => {
      try {
        await loadMessage();
      } catch (error) {
        setPanelStatus("gmail", "bad", error.message || "Gmail message load failed.");
        setDiagnostics("gmail", error, { hint: error.message || "Gmail message load failed.", open: true });
      }
    });
  });

  qs("gmail-use-simulator-defaults")?.addEventListener("click", () => {
    const defaults = appState.extensionDiagnostics?.simulator_defaults || {};
    setFieldValue("gmail-message-id", defaults.message_id || "");
    setFieldValue("gmail-thread-id", defaults.thread_id || "");
    setFieldValue("gmail-subject", defaults.subject || "");
    if (defaults.account_email) {
      setFieldValue("gmail-account-email", defaults.account_email);
    }
  });

  qs("gmail-workflow-kind")?.addEventListener("change", () => {
    setWorkflowSelectionDefaults();
    renderMessageResult(gmailState.loadResult);
    renderReviewSurface();
  });

  qs("gmail-open-review")?.addEventListener("click", () => {
    openReviewDrawer();
  });

  qs("gmail-close-review-drawer")?.addEventListener("click", closeReviewDrawer);
  qs("gmail-review-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("gmail-review-drawer-backdrop")) {
      closeReviewDrawer();
    }
  });

  qs("gmail-attachment-list")?.addEventListener("click", (event) => {
    if (shouldIgnoreReviewRowFocusTarget(event.target)) {
      return;
    }
    const row = event.target.closest("[data-attachment-row]");
    if (!row) {
      return;
    }
    focusAttachment(row.dataset.attachmentRow || "");
    renderAttachmentList(gmailState.loadResult);
    renderReviewDetail();
    renderPreviewPanel();
  });

  qs("gmail-attachment-list")?.addEventListener("keydown", (event) => {
    if (shouldIgnoreReviewRowFocusTarget(event.target)) {
      return;
    }
    const row = event.target.closest("[data-attachment-row]");
    if (!row || !["Enter", " "].includes(event.key)) {
      return;
    }
    event.preventDefault();
    focusAttachment(row.dataset.attachmentRow || "");
    renderAttachmentList(gmailState.loadResult);
    renderReviewDetail();
    renderPreviewPanel();
  });

  qs("gmail-attachment-list")?.addEventListener("dblclick", async (event) => {
    if (shouldIgnoreReviewRowFocusTarget(event.target)) {
      return;
    }
    const row = event.target.closest("[data-attachment-row]");
    if (!row) {
      return;
    }
    const attachmentId = row.dataset.attachmentRow || "";
    if (!attachmentId) {
      return;
    }
    await runWithBusy(["gmail-preview-selected"], { "gmail-preview-selected": "Loading..." }, async () => {
      try {
        await previewAttachment(attachmentId);
      } catch (error) {
        setPanelStatus("gmail", "bad", error.message || "Attachment preview failed.");
        setDiagnostics("gmail", error, { hint: error.message || "Attachment preview failed.", open: true });
      }
    });
  });

  qs("gmail-attachment-list")?.addEventListener("change", (event) => {
    const checkbox = event.target.closest("[data-attachment-checkbox]");
    if (checkbox) {
      const attachmentId = checkbox.dataset.attachmentCheckbox;
      updateAttachmentSelection(attachmentId, Boolean(checkbox.checked));
      renderReviewSurface();
      return;
    }
    const startPage = event.target.closest("[data-attachment-start-page]");
    if (startPage) {
      const attachmentId = startPage.dataset.attachmentStartPage;
      const clamped = updateAttachmentStartPage(attachmentId, startPage.value);
      startPage.value = String(clamped);
      renderReviewDetail();
      renderPreviewPanel();
    }
  });

  qs("gmail-review-detail")?.addEventListener("change", (event) => {
    const startPage = event.target.closest("[data-detail-start-page]");
    if (!startPage) {
      return;
    }
    const attachmentId = startPage.dataset.detailStartPage;
    const clamped = updateAttachmentStartPage(attachmentId, startPage.value);
    startPage.value = String(clamped);
    renderAttachmentList(gmailState.loadResult);
    renderPreviewPanel();
  });

  qs("gmail-review-detail")?.addEventListener("click", async (event) => {
    const trigger = event.target.closest("[data-preview-selected]");
    if (!trigger) {
      return;
    }
    const attachment = focusedAttachment();
    if (!attachment) {
      return;
    }
    await runWithBusy(["gmail-preview-selected"], { "gmail-preview-selected": "Loading..." }, async () => {
      try {
        await previewAttachment(attachment.attachment_id);
      } catch (error) {
        setPanelStatus("gmail", "bad", error.message || "Attachment preview failed.");
        setDiagnostics("gmail", error, { hint: error.message || "Attachment preview failed.", open: true });
      }
    });
  });

  qs("gmail-close-preview-drawer")?.addEventListener("click", closePreviewDrawer);
  qs("gmail-preview-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("gmail-preview-drawer-backdrop")) {
      closePreviewDrawer();
    }
  });

  qs("gmail-preview-prev")?.addEventListener("click", () => {
    if (!isPreviewStateOpen(gmailState.previewState)) {
      return;
    }
    gmailState.previewState = setPreviewStatePage(gmailState.previewState, previewPage() - 1);
    renderPreviewPanel();
  });

  qs("gmail-preview-next")?.addEventListener("click", () => {
    if (!isPreviewStateOpen(gmailState.previewState)) {
      return;
    }
    const upperBound = previewPageCount() > 0 ? previewPageCount() : previewPage() + 1;
    const next = Math.min(upperBound, previewPage() + 1);
    gmailState.previewState = setPreviewStatePage(gmailState.previewState, next);
    renderPreviewPanel();
  });

  qs("gmail-preview-page")?.addEventListener("change", (event) => {
    if (!isPreviewStateOpen(gmailState.previewState)) {
      return;
    }
    const input = event.target;
    gmailState.previewState = setPreviewStatePage(gmailState.previewState, input.value);
    const clamped = previewPage();
    input.value = String(clamped);
    renderPreviewPanel();
  });

  qs("gmail-preview-apply")?.addEventListener("click", () => {
    const attachment = previewAttachmentRecord();
    if (!attachment || !isPreviewStateOpen(gmailState.previewState)) {
      return;
    }
    const nextStartPage = applyPreviewStateStartPage(
      gmailState.previewState,
      attachmentState(attachment.attachment_id).startPage,
    );
    updateAttachmentStartPage(attachment.attachment_id, nextStartPage);
    focusAttachment(attachment.attachment_id);
    closePreviewDrawer();
    renderAttachmentList(gmailState.loadResult);
    renderReviewDetail();
  });

  qs("gmail-prepare-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusy(["gmail-prepare-session"], { "gmail-prepare-session": "Preparing..." }, async () => {
      try {
        await prepareSession();
      } catch (error) {
        setPanelStatus("gmail", "bad", error.message || "Gmail session preparation failed.");
        setDiagnostics("gmail", error, { hint: error.message || "Gmail session preparation failed.", open: true });
      }
    });
  });

  qs("gmail-resume-step")?.addEventListener("click", (event) => {
    runStageAction(event.currentTarget?.dataset.gmailAction || "");
  });

  qs("translation-gmail-confirm-current")?.addEventListener("click", async () => {
    await runWithBusy(["translation-gmail-confirm-current"], { "translation-gmail-confirm-current": "Confirming..." }, async () => {
      try {
        await confirmCurrentTranslation();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Gmail attachment confirmation failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Gmail attachment confirmation failed.", open: true });
      }
    });
  });

  qs("gmail-load-translation-launch")?.addEventListener("click", () => {
    if (gmailState.suggestedTranslationLaunch) {
      gmailState.hooks.applyTranslationLaunch?.(gmailState.suggestedTranslationLaunch);
      setActiveView("new-job");
      closeSessionDrawer();
    }
  });

  qs("gmail-load-interpretation-seed")?.addEventListener("click", () => {
    if (gmailState.interpretationSeed) {
      gmailState.hooks.applyInterpretationSeed?.(gmailState.interpretationSeed, { openReview: true });
      setActiveView("new-job");
      closeSessionDrawer();
    }
  });

  window.addEventListener("legalpdf:open-gmail-session-drawer", () => {
    if (gmailState.activeSession) {
      openSessionDrawer();
    }
  });

  qs("gmail-confirm-translation")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-confirm-translation"], { "gmail-confirm-translation": "Confirming..." }, async () => {
      try {
        await confirmCurrentTranslation();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Gmail attachment confirmation failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Gmail attachment confirmation failed.", open: true });
      }
    });
  });

  qs("gmail-finalize-batch")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-finalize-batch"], { "gmail-finalize-batch": "Finalizing..." }, async () => {
      try {
        await finalizeBatch();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Gmail batch finalization failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Gmail batch finalization failed.", open: true });
      }
    });
  });

  qs("gmail-finalize-interpretation")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-finalize-interpretation"], { "gmail-finalize-interpretation": "Finalizing..." }, async () => {
      try {
        await finalizeInterpretation();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Interpretation Gmail finalization failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Interpretation Gmail finalization failed.", open: true });
      }
    });
  });

  qs("interpretation-finalize-gmail")?.addEventListener("click", async () => {
    await runWithBusy(["interpretation-finalize-gmail"], { "interpretation-finalize-gmail": "Finalizing..." }, async () => {
      try {
        await finalizeInterpretation();
      } catch (error) {
        gmailState.hooks.recoverInterpretationValidationError?.(error);
        setPanelStatus("gmail-session", "bad", error.message || "Interpretation Gmail finalization failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Interpretation Gmail finalization failed.", open: true });
      }
    });
  });

  qs("gmail-refresh")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-refresh"], { "gmail-refresh": "Refreshing..." }, async () => {
      try {
        await refreshGmailState();
      } catch (error) {
        setPanelStatus("gmail", "bad", error.message || "Gmail refresh failed.");
        setDiagnostics("gmail", error, { hint: error.message || "Gmail refresh failed.", open: true });
      }
    });
  });

  qs("gmail-reset")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-reset"], { "gmail-reset": "Resetting..." }, async () => {
      try {
        const payload = await fetchJson("/api/gmail/reset", appState, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        });
        forgetConsumedReviewEvent();
        resetPreviewState();
        gmailState.batchFinalizeResult = null;
        closeReviewDrawer();
        closeBatchFinalizeDrawer();
        renderGmailBootstrap({ normalized_payload: { gmail: payload.normalized_payload } });
        setDiagnostics("gmail-session", payload, { hint: "Gmail workspace reset.", open: false });
        setDiagnostics("gmail-batch-finalize", payload, { hint: "Gmail workspace reset.", open: false });
        closeSessionDrawer();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Gmail workspace reset failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Gmail workspace reset failed.", open: true });
      }
    });
  });

  qs("gmail-workspace-strip-action")?.addEventListener("click", () => {
    runStageAction(qs("gmail-workspace-strip-action")?.dataset.gmailStripAction || "open-intake");
  });
  qs("gmail-open-full-workspace")?.addEventListener("click", () => {
    setActiveView("new-job");
  });
  qs("gmail-close-session-drawer")?.addEventListener("click", closeSessionDrawer);
  qs("gmail-session-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("gmail-session-drawer-backdrop")) {
      closeSessionDrawer();
    }
  });
  qs("gmail-batch-finalize-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusy(["gmail-batch-finalize-run"], { "gmail-batch-finalize-run": "Finalizing..." }, async () => {
      try {
        await finalizeBatch();
      } catch (error) {
        setPanelStatus("gmail-batch-finalize", "bad", error.message || "Gmail batch finalization failed.");
        setDiagnostics("gmail-batch-finalize", error, { hint: error.message || "Gmail batch finalization failed.", open: true });
      }
    });
  });
  qs("gmail-close-batch-finalize-drawer")?.addEventListener("click", closeBatchFinalizeDrawer);
  qs("gmail-batch-finalize-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("gmail-batch-finalize-drawer-backdrop")) {
      closeBatchFinalizeDrawer();
    }
  });

  window.addEventListener("focus", scheduleFocusedRefresh);
  window.addEventListener("legalpdf:translation-ui-state-changed", () => {
    renderResumeCard(gmailState.activeSession);
    renderTranslationCompletionGmailStepCard(gmailState.activeSession);
    renderBatchFinalizeSurface(gmailState.activeSession);
    syncShellState();
  });
  window.addEventListener("legalpdf:interpretation-ui-state-changed", () => {
    renderResumeCard(gmailState.activeSession);
    syncShellState();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      scheduleFocusedRefresh();
    }
  });
  window.addEventListener("legalpdf:route-state-changed", () => {
    if (appState.activeView === "gmail-intake") {
      renderResumeCard(gmailState.activeSession);
      renderTranslationCompletionGmailStepCard(gmailState.activeSession);
      renderBatchFinalizeSurface(gmailState.activeSession);
      renderWorkspaceStrip();
      scheduleFocusedRefresh();
      return;
    }
    closePreviewDrawer();
    closeReviewDrawer();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && gmailState.previewDrawerOpen) {
      closePreviewDrawer();
      return;
    }
    if (event.key === "Escape" && gmailState.reviewDrawerOpen) {
      closeReviewDrawer();
      return;
    }
    if (event.key === "Escape" && gmailState.sessionDrawerOpen) {
      closeSessionDrawer();
      return;
    }
    if (event.key === "Escape" && gmailState.batchFinalizeDrawerOpen) {
      closeBatchFinalizeDrawer();
    }
  });
}
