import { fetchJson } from "./api.js";
import { appState, setActiveView } from "./state.js";

const gmailState = {
  bootstrap: null,
  loadResult: null,
  activeSession: null,
  interpretationSeed: null,
  suggestedTranslationLaunch: null,
  selectionState: new Map(),
  sessionDrawerOpen: false,
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

function ensureSelectionState(loadResult, activeSession) {
  const message = loadResult?.message || null;
  const next = new Map();
  for (const attachment of message?.attachments || []) {
    const existing = gmailState.selectionState.get(attachment.attachment_id) || {};
    next.set(attachment.attachment_id, {
      selected: Boolean(existing.selected),
      startPage: Number(existing.startPage || 1),
      pageCount: Number(existing.pageCount || 0),
    });
  }
  if (activeSession?.kind === "translation") {
    for (const item of activeSession.attachments || []) {
      const attachment = item.attachment || {};
      next.set(attachment.attachment_id, {
        selected: true,
        startPage: Number(item.start_page || 1),
        pageCount: Number(item.page_count || 0),
      });
    }
  }
  if (activeSession?.kind === "interpretation") {
    const attachmentId = activeSession.attachment?.attachment?.attachment_id || "";
    if (attachmentId) {
      next.set(attachmentId, {
        selected: true,
        startPage: 1,
        pageCount: Number(activeSession.attachment?.page_count || 0),
      });
    }
  }
  gmailState.selectionState = next;
}

function currentWorkflowKind() {
  return fieldValue("gmail-workflow-kind") === "interpretation" ? "interpretation" : "translation";
}

function bootstrapMessageContext() {
  return gmailState.bootstrap?.defaults?.message_context || {};
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

function closeSessionDrawer() {
  setSessionDrawerOpen(false);
}

function collectSelections() {
  const selections = [];
  for (const [attachmentId, item] of gmailState.selectionState.entries()) {
    if (!item.selected) {
      continue;
    }
    selections.push({
      attachment_id: attachmentId,
      start_page: currentWorkflowKind() === "interpretation" ? 1 : Math.max(1, Number(item.startPage || 1)),
    });
  }
  return selections;
}

function renderMessageResult(loadResult) {
  const container = qs("gmail-message-result");
  const defaults = bootstrapMessageContext();
  const detailsHint = qs("gmail-intake-details-summary");
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
          <p>${defaults.subject || "Subject unavailable"}<br>${defaults.account_email || "Account unavailable"}</p>
        </div>
        <span class="status-chip info">Pending load</span>
      </div>
      <div class="result-grid">
        <div><h3>Message ID</h3><p class="word-break">${defaults.message_id || "Unavailable"}</p></div>
        <div><h3>Thread ID</h3><p class="word-break">${defaults.thread_id || "Unavailable"}</p></div>
      </div>
    `;
    if (detailsHint) {
      detailsHint.textContent = "Extension defaults are ready; expand only if you need manual overrides.";
    }
    return;
  }
  const message = loadResult.message || {};
  const attachmentCount = (message.attachments || []).length;
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${loadResult.status_message || "Gmail message state available."}</strong>
        <p>${message.subject || "No subject"}<br>${attachmentCount} supported attachment(s) from ${message.account_email || "unknown account"}</p>
      </div>
      <span class="status-chip ${loadResult.ok ? "ok" : loadResult.classification === "unavailable" ? "warn" : "bad"}">${loadResult.classification || (loadResult.ok ? "ready" : "failed")}</span>
    </div>
    <div class="result-grid">
      <div><h3>Workflow</h3><p>${currentWorkflowKind() === "interpretation" ? "Interpretation notice" : "Translation batch"}</p></div>
      <div><h3>Attachments</h3><p>${attachmentCount}</p></div>
    </div>
  `;
  if (detailsHint) {
    detailsHint.textContent = "Message identifiers, account, and output overrides stay out of the way unless you need them.";
  }
}

function renderAttachmentList(loadResult) {
  const container = qs("gmail-attachment-list");
  container.innerHTML = "";
  const attachments = loadResult?.message?.attachments || [];
  if (!attachments.length) {
    container.innerHTML = '<div class="empty-state">No supported attachments are available for the loaded Gmail message.</div>';
    return;
  }
  const interpretationWorkflow = currentWorkflowKind() === "interpretation";
  for (const attachment of attachments) {
    const state = gmailState.selectionState.get(attachment.attachment_id) || { selected: false, startPage: 1, pageCount: 0 };
    const row = document.createElement("article");
    row.className = "history-item";
    row.innerHTML = `
      <div class="gmail-attachment-card">
        <label class="checkbox-inline">
          <input type="checkbox" data-attachment-checkbox="${attachment.attachment_id}" ${state.selected ? "checked" : ""}>
          <strong>${attachment.filename}</strong>
        </label>
        <p>${attachment.mime_type} | ${attachment.size_bytes} bytes | ${state.pageCount > 0 ? `${state.pageCount} page(s)` : "Preview for page count"}</p>
      </div>
    `;
    const controls = document.createElement("div");
    controls.className = "history-meta gmail-attachment-actions";
    if (!interpretationWorkflow) {
      const input = document.createElement("input");
      input.type = "number";
      input.min = "1";
      input.step = "1";
      input.value = String(Math.max(1, Number(state.startPage || 1)));
      input.dataset.attachmentStartPage = attachment.attachment_id;
      input.className = "attachment-start-page";
      controls.appendChild(input);
    }
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Preview";
    button.dataset.previewAttachment = attachment.attachment_id;
    controls.appendChild(button);
    row.appendChild(controls);
    container.appendChild(row);
  }
}

function renderSessionBanner(activeSession) {
  const container = qs("gmail-session-banner");
  if (!container) {
    return;
  }
  if (!activeSession) {
    container.classList.add("hidden");
    container.classList.add("empty-state");
    container.textContent = "No Gmail session is active yet.";
    return;
  }
  container.classList.remove("hidden");
  container.classList.remove("empty-state");
  if (activeSession.kind === "translation") {
    container.innerHTML = `
      <div class="result-header">
        <div>
          <strong>Translation batch prepared.</strong>
          <p>${activeSession.completed ? "All selected attachments are confirmed and ready to finalize." : `Attachment ${activeSession.current_item_number}/${activeSession.total_items} is ready for the next translation step.`}</p>
        </div>
        <span class="status-chip ${activeSession.completed ? "ok" : "info"}">${activeSession.status || "prepared"}</span>
      </div>
    `;
    return;
  }
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>Interpretation notice prepared.</strong>
        <p>Open session actions when you are ready to continue into interpretation or finalize the Gmail reply.</p>
      </div>
      <span class="status-chip info">${activeSession.status || "prepared"}</span>
    </div>
  `;
}

function renderSessionResult(activeSession) {
  const container = qs("gmail-session-result");
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
          <p>${activeSession.completed ? "All attachments confirmed. Finalize the batch reply when ready." : `Current attachment: ${current.filename || "Unavailable"}`}</p>
        </div>
        <span class="status-chip ${activeSession.completed ? "ok" : "info"}">${activeSession.status || "prepared"}</span>
      </div>
      <div class="result-grid">
        <div><h3>Subject</h3><p>${activeSession.message?.subject || "Unavailable"}</p></div>
        <div><h3>Target Language</h3><p>${activeSession.selected_target_lang || "?"}</p></div>
        <div><h3>Confirmed Rows</h3><p>${(activeSession.confirmed_items || []).length}</p></div>
        <div><h3>Session Report</h3><p class="word-break">${activeSession.session_report_path || "Unavailable"}</p></div>
      </div>
    `;
    return;
  }
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>Gmail interpretation notice ready</strong>
        <p>${activeSession.attachment?.attachment?.filename || "No downloaded notice"} | ${activeSession.message?.subject || "No subject"}</p>
      </div>
      <span class="status-chip info">${activeSession.status || "prepared"}</span>
    </div>
    <div class="result-grid">
      <div><h3>Notice PDF</h3><p class="word-break">${activeSession.attachment?.saved_path || "Unavailable"}</p></div>
      <div><h3>Session Report</h3><p class="word-break">${activeSession.session_report_path || "Unavailable"}</p></div>
    </div>
  `;
}

function renderWorkspaceStrip() {
  const strip = qs("gmail-workspace-strip");
  if (!strip) {
    return;
  }
  const show = Boolean(gmailState.loadResult || gmailState.activeSession);
  strip.classList.toggle("hidden", !show);
  if (!show) {
    return;
  }
  const title = qs("gmail-workspace-strip-title");
  const copy = qs("gmail-workspace-strip-copy");
  const action = qs("gmail-workspace-strip-action");
  if (gmailState.activeSession?.kind === "translation") {
    title.textContent = "A Gmail translation batch is active.";
    copy.textContent = "Open session actions when you need to confirm the current row or finalize the reply draft.";
    if (action) {
      action.textContent = "Open Session Actions";
      action.dataset.gmailStripAction = "session";
    }
    return;
  }
  if (gmailState.activeSession?.kind === "interpretation") {
    title.textContent = "A Gmail interpretation handoff is active.";
    copy.textContent = "Open session actions when you need to continue into interpretation or finalize the Gmail reply.";
    if (action) {
      action.textContent = "Open Session Actions";
      action.dataset.gmailStripAction = "session";
    }
    return;
  }
  title.textContent = "A Gmail message is loaded for this workspace.";
  copy.textContent = "Open Gmail intake to review attachments and choose the right workflow before you continue.";
  if (action) {
    action.textContent = "Open Gmail Intake";
    action.dataset.gmailStripAction = "intake";
  }
}

function updatePrepareActionState() {
  const button = qs("gmail-prepare-session");
  if (!button) {
    return;
  }
  const selections = collectSelections();
  let label = currentWorkflowKind() === "interpretation"
    ? "Continue To Interpretation"
    : "Continue To Translation";
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
  if (appState.bootstrap?.normalized_payload) {
    appState.bootstrap.normalized_payload.gmail = {
      ...(appState.bootstrap.normalized_payload.gmail || {}),
      ...gmailState.bootstrap,
      load_result: gmailState.loadResult,
      active_session: gmailState.activeSession,
      interpretation_seed: gmailState.interpretationSeed,
      suggested_translation_launch: gmailState.suggestedTranslationLaunch,
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
  for (const id of ["gmail-open-session", "gmail-preview-session"]) {
    const button = qs(id);
    if (!button) {
      continue;
    }
    button.disabled = !sessionAvailable;
    button.classList.toggle("hidden", !sessionAvailable);
  }
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

export function renderGmailBootstrap(payload) {
  const gmailPayload = payload.normalized_payload.gmail || {};
  gmailState.bootstrap = gmailPayload;
  gmailState.loadResult = gmailPayload.load_result || null;
  gmailState.activeSession = gmailPayload.active_session || null;
  gmailState.interpretationSeed = gmailPayload.interpretation_seed || null;
  gmailState.suggestedTranslationLaunch = gmailPayload.suggested_translation_launch || null;
  applyBootstrapDefaults(gmailPayload);
  ensureSelectionState(gmailState.loadResult, gmailState.activeSession);
  renderMessageResult(gmailState.loadResult);
  renderAttachmentList(gmailState.loadResult);
  renderSessionBanner(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  updatePrepareActionState();
  updateSessionButtons();
  setPanelStatus(
    "gmail",
    gmailState.loadResult?.ok ? "ok" : "",
    gmailState.activeSession
      ? "Gmail handoff is staged and ready. Open session actions only when you need the next downstream step."
      : "Review the exact message, choose the attachment flow, and continue only when the handoff is ready.",
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

async function refreshGmailState() {
  const payload = await fetchJson("/api/gmail/bootstrap", appState);
  renderGmailBootstrap({ normalized_payload: { gmail: payload.normalized_payload } });
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
  gmailState.loadResult = payload.normalized_payload.load_result || null;
  gmailState.activeSession = null;
  gmailState.interpretationSeed = null;
  gmailState.suggestedTranslationLaunch = null;
  ensureSelectionState(gmailState.loadResult, null);
  renderMessageResult(gmailState.loadResult);
  renderAttachmentList(gmailState.loadResult);
  renderSessionBanner(null);
  renderSessionResult(null);
  updatePrepareActionState();
  updateSessionButtons();
  setPanelStatus("gmail", payload.status === "ok" ? "ok" : payload.status === "unavailable" ? "warn" : "bad", payload.normalized_payload.load_result?.status_message || "Gmail message load complete.");
  setDiagnostics("gmail", payload, { hint: payload.normalized_payload.load_result?.status_message || "Gmail message load complete.", open: payload.status !== "ok" });
  const details = qs("gmail-intake-details");
  if (details) {
    details.open = false;
  }
}

async function previewAttachment(attachmentId) {
  const payload = await fetchJson("/api/gmail/preview-attachment", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ attachment_id: attachmentId }),
  });
  const item = gmailState.selectionState.get(attachmentId) || { selected: false, startPage: 1, pageCount: 0 };
  item.pageCount = Number(payload.normalized_payload.page_count || 0);
  gmailState.selectionState.set(attachmentId, item);
  renderAttachmentList(gmailState.loadResult);
  if (payload.normalized_payload.preview_href) {
    window.open(payload.normalized_payload.preview_href, "_blank", "noopener,noreferrer");
  }
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
  renderSessionBanner(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  updatePrepareActionState();
  updateSessionButtons();
  setDiagnostics("gmail", payload, { hint: "Gmail session prepared.", open: false });
  if (gmailState.suggestedTranslationLaunch) {
    gmailState.hooks.applyTranslationLaunch?.(gmailState.suggestedTranslationLaunch);
  }
  if (gmailState.interpretationSeed) {
    gmailState.hooks.applyInterpretationSeed?.(gmailState.interpretationSeed, { openReview: true });
  }
  setPanelStatus("gmail", "ok", "Gmail handoff is prepared. Open session actions when you are ready to continue into the working shell.");
  openSessionDrawer();
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
  renderSessionBanner(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  updateSessionButtons();
  setDiagnostics("gmail-session", payload, { hint: "Current Gmail attachment confirmed and saved to the job log.", open: false });
  if (gmailState.suggestedTranslationLaunch) {
    gmailState.hooks.applyTranslationLaunch?.(gmailState.suggestedTranslationLaunch);
  }
  window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
}

async function finalizeBatch() {
  const payload = await fetchJson("/api/gmail/batch/finalize", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile_id: qs("profile-id")?.value || "",
      output_filename: fieldValue("gmail-final-output-filename"),
    }),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  renderSessionBanner(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  updateSessionButtons();
  setDiagnostics("gmail-session", payload, { hint: payload.status === "ok" ? "Gmail batch reply draft is ready." : "Gmail batch finalization completed with warnings.", open: payload.status !== "ok" });
}

async function finalizeInterpretation() {
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
  renderSessionBanner(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  updateSessionButtons();
  gmailState.hooks.renderInterpretationExportResult?.(payload);
  setDiagnostics("gmail-session", payload, { hint: payload.status === "ok" ? "Gmail interpretation reply draft is ready." : "Interpretation Gmail finalization completed with warnings.", open: payload.status !== "ok" });
}

export function initializeGmailUi(hooks) {
  gmailState.hooks = hooks || {};
  setDiagnostics("gmail", { status: "idle", message: "No Gmail action has run yet." }, { hint: "Exact-message load, attachment preview, and session preparation details appear here.", open: false });
  setDiagnostics("gmail-session", { status: "idle", message: "No Gmail batch or interpretation finalization has run yet." }, { hint: "Batch progression, staged attachments, export status, and Gmail draft details appear here.", open: false });

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
    if (currentWorkflowKind() === "interpretation") {
      let kept = false;
      for (const item of gmailState.selectionState.values()) {
        if (item.selected && !kept) {
          kept = true;
        } else {
          item.selected = false;
        }
      }
    }
    renderAttachmentList(gmailState.loadResult);
    renderMessageResult(gmailState.loadResult);
    updatePrepareActionState();
  });
  qs("gmail-attachment-list")?.addEventListener("change", (event) => {
    const checkbox = event.target.closest("[data-attachment-checkbox]");
    if (checkbox) {
      const attachmentId = checkbox.dataset.attachmentCheckbox;
      const next = gmailState.selectionState.get(attachmentId) || { selected: false, startPage: 1, pageCount: 0 };
      if (currentWorkflowKind() === "interpretation" && checkbox.checked) {
        for (const item of gmailState.selectionState.values()) {
          item.selected = false;
        }
      }
      next.selected = Boolean(checkbox.checked);
      gmailState.selectionState.set(attachmentId, next);
      if (currentWorkflowKind() === "interpretation") {
        renderAttachmentList(gmailState.loadResult);
      }
      updatePrepareActionState();
      return;
    }
    const startPage = event.target.closest("[data-attachment-start-page]");
    if (startPage) {
      const attachmentId = startPage.dataset.attachmentStartPage;
      const next = gmailState.selectionState.get(attachmentId) || { selected: false, startPage: 1, pageCount: 0 };
      next.startPage = Math.max(1, Number(startPage.value || 1));
      gmailState.selectionState.set(attachmentId, next);
    }
  });
  qs("gmail-attachment-list")?.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-preview-attachment]");
    if (!button) {
      return;
    }
    button.disabled = true;
    try {
      try {
        await previewAttachment(button.dataset.previewAttachment);
      } catch (error) {
        setPanelStatus("gmail", "bad", error.message || "Attachment preview failed.");
        setDiagnostics("gmail", error, { hint: error.message || "Attachment preview failed.", open: true });
      }
    } finally {
      button.disabled = false;
    }
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
        const payload = await fetchJson("/api/gmail/reset", appState, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
        renderGmailBootstrap({ normalized_payload: { gmail: payload.normalized_payload } });
        setDiagnostics("gmail-session", payload, { hint: "Gmail workspace reset.", open: false });
        closeSessionDrawer();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Gmail workspace reset failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Gmail workspace reset failed.", open: true });
      }
    });
  });
  qs("gmail-open-session")?.addEventListener("click", openSessionDrawer);
  qs("gmail-preview-session")?.addEventListener("click", openSessionDrawer);
  qs("gmail-workspace-strip-action")?.addEventListener("click", () => {
    if (gmailState.activeSession) {
      openSessionDrawer();
      return;
    }
    setActiveView("gmail-intake");
  });
  qs("gmail-close-session-drawer")?.addEventListener("click", closeSessionDrawer);
  qs("gmail-session-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("gmail-session-drawer-backdrop")) {
      closeSessionDrawer();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && gmailState.sessionDrawerOpen) {
      closeSessionDrawer();
    }
  });
}
