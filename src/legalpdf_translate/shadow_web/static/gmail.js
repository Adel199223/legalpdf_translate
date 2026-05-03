import { fetchJson } from "./api.js";
import { appState, setActiveView } from "./state.js";
import {
  browserPdfDiagnosticsFromError,
  ensureBrowserPdfBundleFromUrl,
  renderBrowserPdfPreviewToCanvas,
} from "./browser_pdf.js";
import { deriveGmailLiveRuntimeGuard } from "./gmail_runtime_guard.js";
import {
  renderGmailAttachmentListInto,
  renderGmailBatchFinalizeSurfaceInto,
  renderGmailMessageResultInto,
  renderGmailNoncanonicalRuntimeGuardInto,
  renderGmailPreviewPanelInto,
  renderGmailReviewDetailInto,
  renderGmailReviewSummaryInto,
  renderGmailResumeCardInto,
  renderGmailSessionResultInto,
} from "./gmail_ui.js";
import {
  applyPreviewStateStartPage,
  clearConsumedReviewState,
  deriveGmailOverlayDismissalAction,
  deriveGmailAttachmentKindLabel,
  deriveGmailPreviewRestoreLabel,
  deriveGmailRedoAction,
  deriveGmailReviewRestoreLabel,
  deriveRecoveredFinalizationAction,
  createClosedPreviewState,
  deriveGmailHomeCta,
  deriveGmailStagePresentation,
  deriveGmailStage,
  deriveGmailWorkflowPresentation,
  isPreviewStateOpen,
  minimizePreviewState,
  openPreviewState,
  readConsumedReviewState,
  restorePreviewState,
  setPreviewStatePage,
  shouldTreatGmailWorkspaceAsStable,
  shouldAutoOpenReview,
  shouldIgnoreReviewRowFocusTarget,
  writeConsumedReviewState,
} from "./gmail_review_state.js";
const AUTO_REFRESH_DELAY_MS = 220;
const AUTO_REFRESH_THROTTLE_MS = 1400;
const PASSIVE_REFRESH_COOLDOWN_MS = 6000;
const WARMUP_POLL_INTERVAL_MS = 900;
const WARMUP_POLL_TIMEOUT_MS = 15000;

const gmailState = {
  bootstrap: null,
  loadResult: null,
  activeSession: null,
  restoredCompletedSession: null,
  interpretationSeed: null,
  suggestedTranslationLaunch: null,
  selectionState: new Map(),
  reviewDrawerOpen: false,
  reviewDrawerMinimized: false,
  reviewFocusedAttachmentId: "",
  previewDrawerOpen: false,
  previewDrawerMinimized: false,
  previewState: createClosedPreviewState(),
  sessionDrawerOpen: false,
  batchFinalizeDrawerOpen: false,
  batchFinalizePreflight: null,
  batchFinalizePreflightInFlight: false,
  batchFinalizeResult: null,
  batchFinalizeDrawerSource: "active",
  browserPdfState: new Map(),
  stage: "idle",
  refreshInFlight: false,
  refreshTimer: 0,
  lastRefreshAt: 0,
  lastPassiveRefreshAt: 0,
  warmupPollUntil: 0,
  lastRouteView: "",
  lastFailureReportContext: null,
  lastFailureReportPayload: null,
  lastFinalizationReportPayload: null,
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

function browserBootstrapConfig() {
  return globalThis.window?.LEGALPDF_BROWSER_BOOTSTRAP || {};
}

function currentGmailRuntimePayload() {
  const bootstrap = browserBootstrapConfig();
  const runtime = appState.bootstrap?.normalized_payload?.runtime || {};
  return {
    ...runtime,
    build_branch: String(runtime.build_branch || bootstrap.buildBranch || "").trim(),
    build_sha: String(runtime.build_sha || bootstrap.buildSha || "").trim(),
    asset_version: String(runtime.asset_version || bootstrap.assetVersion || "").trim(),
    live_data: runtime.live_data === true || appState.runtimeMode === "live",
  };
}

function currentGmailBuildIdentity() {
  const runtime = currentGmailRuntimePayload();
  const bootstrap = browserBootstrapConfig();
  const identity = (
    runtime.build_identity
    && typeof runtime.build_identity === "object"
    ? runtime.build_identity
    : appState.bootstrap?.normalized_payload?.shell?.build_identity
      && typeof appState.bootstrap.normalized_payload.shell.build_identity === "object"
      ? appState.bootstrap.normalized_payload.shell.build_identity
      : bootstrap.buildIdentity
        && typeof bootstrap.buildIdentity === "object"
        ? bootstrap.buildIdentity
        : {}
  );
  return {
    ...identity,
    branch: String(identity.branch || runtime.build_branch || "").trim(),
    head_sha: String(identity.head_sha || runtime.build_sha || "").trim(),
  };
}

function currentGmailBuildProvenance() {
  const runtime = currentGmailRuntimePayload();
  const buildIdentity = currentGmailBuildIdentity();
  const branch = String(buildIdentity.branch || runtime.build_branch || "").trim();
  const buildSha = String(buildIdentity.head_sha || runtime.build_sha || "").trim();
  const assetVersion = String(runtime.asset_version || "").trim();
  const pieces = [];
  if (branch && buildSha) {
    pieces.push(`${branch}@${buildSha}`);
  } else if (buildSha || branch) {
    pieces.push(buildSha || branch);
  }
  if (assetVersion) {
    pieces.push(`assets ${assetVersion}`);
  }
  return {
    branch,
    buildSha,
    assetVersion,
    label: pieces.join(" | ") || "Unavailable",
  };
}

function gmailRuntimeGuardSessionKey(buildIdentity = currentGmailBuildIdentity()) {
  const branch = String(buildIdentity.branch || "unknown-branch").trim() || "unknown-branch";
  const buildSha = String(buildIdentity.head_sha || "unknown-sha").trim() || "unknown-sha";
  return `legalpdf.gmail.noncanonical.${appState.runtimeMode}.${appState.workspaceId}.${branch}.${buildSha}`;
}

function gmailRuntimeGuardAcknowledged(buildIdentity = currentGmailBuildIdentity()) {
  const handle = sessionStorageHandle();
  if (!handle) {
    return false;
  }
  try {
    return handle.getItem(gmailRuntimeGuardSessionKey(buildIdentity)) === "1";
  } catch {
    return false;
  }
}

function setGmailRuntimeGuardAcknowledged(value, buildIdentity = currentGmailBuildIdentity()) {
  const handle = sessionStorageHandle();
  if (!handle) {
    return;
  }
  try {
    const key = gmailRuntimeGuardSessionKey(buildIdentity);
    if (value) {
      handle.setItem(key, "1");
    } else {
      handle.removeItem(key);
    }
  } catch {
    // Session storage is best effort only.
  }
}

function currentGmailRuntimeGuard() {
  const buildIdentity = currentGmailBuildIdentity();
  return deriveGmailLiveRuntimeGuard({
    runtime: currentGmailRuntimePayload(),
    buildIdentity,
    acknowledged: gmailRuntimeGuardAcknowledged(buildIdentity),
  });
}

function gmailRuntimeGuardDiagnostics(guard = currentGmailRuntimeGuard(), operation = "") {
  return {
    error: "noncanonical_live_runtime",
    message: guard.message,
    operation: String(operation || "").trim(),
    build_label: guard.buildLabel,
    build_identity: currentGmailBuildIdentity(),
    runtime: currentGmailRuntimePayload(),
    details: guard.details,
    acknowledged: Boolean(guard.acknowledged),
  };
}

function currentGmailFailureReportContext() {
  return gmailState.lastFailureReportContext && typeof gmailState.lastFailureReportContext === "object"
    ? { ...gmailState.lastFailureReportContext }
    : null;
}

function currentDisplayedBatchFinalizeSession() {
  if (gmailState.batchFinalizeDrawerSource === "restored") {
    return gmailState.restoredCompletedSession?.kind === "translation" && gmailState.restoredCompletedSession?.completed
      ? gmailState.restoredCompletedSession
      : null;
  }
  return gmailState.activeSession?.kind === "translation" && gmailState.activeSession?.completed
    ? gmailState.activeSession
    : null;
}

function currentBatchFinalizePreflight() {
  if (gmailState.batchFinalizeDrawerSource === "restored") {
    return null;
  }
  if (gmailState.batchFinalizePreflight && typeof gmailState.batchFinalizePreflight === "object") {
    return { ...gmailState.batchFinalizePreflight };
  }
  const session = currentDisplayedBatchFinalizeSession();
  if (session?.finalization_preflight && typeof session.finalization_preflight === "object") {
    return { ...session.finalization_preflight };
  }
  return null;
}

function currentBatchFinalizeState() {
  const payloadState = String(gmailState.batchFinalizeResult?.normalized_payload?.finalization_state || "").trim();
  if (payloadState) {
    return payloadState;
  }
  const sessionState = String(currentDisplayedBatchFinalizeSession()?.finalization_state || "").trim();
  if (sessionState) {
    return sessionState;
  }
  const preflight = currentBatchFinalizePreflight();
  if (preflight) {
    return preflight.finalization_ready ? "ready_to_finalize" : "blocked_word_pdf_export";
  }
  return "";
}

function currentGmailFinalizationReportContext() {
  const normalized = gmailState.batchFinalizeResult?.normalized_payload || {};
  const rawContext = (
    normalized.finalization_report_context
    && typeof normalized.finalization_report_context === "object"
  )
    ? normalized.finalization_report_context
    : (
      currentDisplayedBatchFinalizeSession()?.finalization_report_context
      && typeof currentDisplayedBatchFinalizeSession().finalization_report_context === "object"
    )
      ? currentDisplayedBatchFinalizeSession().finalization_report_context
      : null;
  if (!rawContext) {
    return null;
  }
  return {
    ...rawContext,
    runtime_mode: String(rawContext.runtime_mode || appState.runtimeMode || "").trim(),
    workspace_id: String(rawContext.workspace_id || appState.workspaceId || "").trim(),
    active_view: String(rawContext.active_view || appState.activeView || "").trim(),
    build_sha: String(rawContext.build_sha || browserBootstrapConfig().buildSha || "").trim(),
    asset_version: String(rawContext.asset_version || browserBootstrapConfig().assetVersion || "").trim(),
  };
}

function attachmentReportSnapshot(attachment) {
  const state = attachmentState(attachment.attachment_id);
  return {
    attachment_id: attachment.attachment_id,
    filename: attachment.filename || "",
    mime_type: attachment.mime_type || "",
    size_bytes: Number(attachment.size_bytes || 0),
    selected: state.selected,
    start_page: state.startPage,
    page_count: state.pageCount,
  };
}

function buildGmailFailureReportContext(error, { operation = "", attachment = null } = {}) {
  const runtime = currentGmailRuntimePayload();
  const diagnostics = {
    ...browserPdfDiagnosticsFromError(error),
    ...(error?.payload?.diagnostics && typeof error.payload.diagnostics === "object" ? error.payload.diagnostics : {}),
  };
  const message = gmailState.loadResult?.message || {};
  const previewState = isPreviewStateOpen(gmailState.previewState)
    ? {
      attachment_id: gmailState.previewState.attachmentId || "",
      page: previewPage(),
      page_count: previewPageCount(),
      preview_href: String(gmailState.previewState.previewHref || "").trim(),
    }
    : {};
  return {
    kind: "gmail_browser_failure",
    captured_at: new Date().toISOString(),
    operation: String(operation || "").trim(),
    runtime_mode: appState.runtimeMode,
    workspace_id: appState.workspaceId,
    active_view: appState.activeView,
    build_sha: String(runtime.build_sha || "").trim(),
    asset_version: String(runtime.asset_version || "").trim(),
    build_identity: currentGmailBuildIdentity(),
    workflow_kind: currentWorkflowKind(),
    focused_attachment_id: attachment?.attachment_id || gmailState.reviewFocusedAttachmentId || "",
    message: {
      message_id: message.message_id || "",
      thread_id: message.thread_id || "",
      subject: message.subject || "",
      account_email: message.account_email || "",
    },
    attachments: gmailAttachments().map(attachmentReportSnapshot),
    preview_state: previewState,
    error: {
      code: String(diagnostics.error || error?.name || "gmail_browser_failure").trim() || "gmail_browser_failure",
      message: String(error?.message || diagnostics.message || "Gmail browser failure.").trim(),
      diagnostics,
    },
  };
}

function clearGmailFailureReportContext() {
  gmailState.lastFailureReportContext = null;
  gmailState.lastFailureReportPayload = null;
}

function rememberGmailFailureReport(error, options = {}) {
  gmailState.lastFailureReportContext = buildGmailFailureReportContext(error, options);
  gmailState.lastFailureReportPayload = null;
}

function updateGmailFailureReportActionState() {
  const button = qs("gmail-generate-failure-report");
  if (!button) {
    return;
  }
  const available = Boolean(gmailState.lastFailureReportContext);
  button.classList.toggle("hidden", !available);
  button.disabled = !available;
  const defaultLabel = "Generate Failure Report";
  button.textContent = defaultLabel;
  button.dataset.defaultLabel = defaultLabel;
}

function updateGmailFinalizationReportActionState() {
  const button = qs("gmail-batch-finalize-report");
  if (!button) {
    return;
  }
  const available = Boolean(currentGmailFinalizationReportContext());
  button.classList.toggle("hidden", !available);
  button.disabled = !available;
  const defaultLabel = gmailState.lastFinalizationReportPayload
    ? "Generate Updated Finalization Report"
    : "Generate Finalization Report";
  button.textContent = defaultLabel;
  button.dataset.defaultLabel = defaultLabel;
}

function gmailFailureHint(error, fallbackMessage) {
  const diagnostics = browserPdfDiagnosticsFromError(error);
  if (
    diagnostics.error === "browser_pdf_worker_load_failed"
    || diagnostics.error === "browser_pdf_module_load_failed"
  ) {
    const phase = String(diagnostics.worker_boot_phase || diagnostics.phase || "worker_boot").trim().replaceAll("_", " ");
    const attemptedUrl = String(diagnostics.attempted_url || diagnostics.worker_url || diagnostics.module_url || "").trim();
    const rawBrowserError = String(diagnostics.raw_browser_error || diagnostics.raw_message || "").trim();
    const location = attemptedUrl ? ` at ${attemptedUrl}` : "";
    const rawDetail = rawBrowserError ? ` Browser error: ${rawBrowserError}` : "";
    return `Browser PDF ${phase} failed${location}.${rawDetail} Generate a failure report here or review the Gmail diagnostics below for the exact asset details.`;
  }
  return fallbackMessage;
}

function renderGmailNoncanonicalRuntimeGuard() {
  const card = qs("gmail-noncanonical-runtime-guard");
  const title = qs("gmail-noncanonical-runtime-title");
  const message = qs("gmail-noncanonical-runtime-message");
  const details = qs("gmail-noncanonical-runtime-details");
  const restartButton = qs("gmail-restart-canonical-runtime");
  const chip = card?.querySelector(".status-chip");
  const guard = currentGmailRuntimeGuard();
  renderGmailNoncanonicalRuntimeGuardInto({ card, title, message, details, restartButton, chip }, guard);
}

function maybeBlockGmailReviewAction(operation) {
  const guard = currentGmailRuntimeGuard();
  if (!guard.blocked) {
    return false;
  }
  setPanelStatus("gmail", "warn", guard.message);
  setDiagnostics("gmail", {
    status: "blocked",
    diagnostics: gmailRuntimeGuardDiagnostics(guard, operation),
  }, {
    hint: guard.message,
    open: true,
  });
  renderReviewSurface();
  return true;
}

async function restartCanonicalRuntimeGuidance() {
  const guard = currentGmailRuntimeGuard();
  setPanelStatus("gmail", "warn", "Restarting the live Gmail browser runtime...");
  setDiagnostics("gmail", {
    status: "restarting",
    diagnostics: gmailRuntimeGuardDiagnostics(guard, "gmail_restart_canonical_runtime"),
  }, {
    hint: "Restarting the browser runtime for live Gmail. This page will reconnect automatically.",
    open: true,
  });
  const payload = await fetchJson("/api/gmail/runtime/restart-canonical", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode: appState.runtimeMode,
      workspace_id: appState.workspaceId,
    }),
  });
  const browserUrl = String(payload.normalized_payload?.browser_url || window.location.href).trim() || window.location.href;
  const shellReadyUrl = String(payload.normalized_payload?.shell_ready_url || "").trim();
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    try {
      if (shellReadyUrl) {
        await fetch(shellReadyUrl, { cache: "no-store" });
      } else {
        await fetch(browserUrl, { cache: "no-store" });
      }
      window.location.replace(browserUrl);
      return;
    } catch {
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
  }
  throw new Error("Live Gmail runtime restart was started, but the browser listener did not become ready in time.");
}

function translationUiSnapshot() {
  return gmailState.hooks.getTranslationUiSnapshot?.() || {};
}

function renderGmailFinalizeNumericMismatchWarning(warning = translationUiSnapshot().numericMismatchWarning) {
  const container = qs("gmail-batch-finalize-numeric-warning");
  if (!container) {
    return;
  }
  const visible = Boolean(warning?.visible);
  container.classList.toggle("hidden", !visible);
  if (!visible) {
    container.textContent = "";
    return;
  }
  const lines = Array.isArray(warning.lines) ? warning.lines.filter(Boolean) : [];
  const detail = lines.length ? `\n${lines.join("\n")}` : "";
  container.textContent = `${warning.message || "Review recommended: some numbers from the source may not appear exactly in the translation."}${detail}`;
  container.setAttribute("role", "note");
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

function currentRedoAction() {
  return deriveGmailRedoAction({
    activeSession: gmailState.activeSession,
    translationUi: translationUiSnapshot(),
  });
}

function currentRecoveredFinalizationAction() {
  return deriveRecoveredFinalizationAction({
    restoredCompletedSession: gmailState.restoredCompletedSession,
  });
}

function gmailHomeStatusMessage() {
  const clickDiagnostics = currentClickDiagnostics();
  const recoveredAction = currentRecoveredFinalizationAction();
  const stage = gmailState.stage || currentGmailStage();
  const presentation = deriveGmailStagePresentation({
    stage,
    activeSession: gmailState.activeSession,
  });
  if (
    !gmailState.loadResult
    && !gmailState.activeSession
    && recoveredAction.visible
  ) {
    return "A previous Gmail result is still available here, but this page is waiting for a new Gmail message.";
  }
  switch (stage) {
    case "translation_recovery":
    case "translation_prepared":
    case "translation_running":
    case "translation_save":
    case "translation_finalize":
    case "interpretation_review":
    case "interpretation_finalize":
      return presentation.description;
    default:
      if (!gmailState.loadResult && !gmailState.activeSession && clickDiagnostics.click_phase && !clickDiagnostics.bridge_context_posted) {
        return `The last Gmail redirect stopped during ${clickDiagnostics.click_phase.replaceAll("_", " ")}. Use Back to Gmail or refresh this review before trying again.`;
      }
      return "Choose the attachment you want to process, preview it if needed, then continue.";
  }
}

function loadSuggestedTranslationLaunch({ closeCompletionDrawer = false } = {}) {
  if (!gmailState.suggestedTranslationLaunch) {
    return false;
  }
  gmailState.hooks.applyTranslationLaunch?.(gmailState.suggestedTranslationLaunch);
  if (closeCompletionDrawer) {
    gmailState.hooks.closeTranslationCompletionDrawer?.();
  }
  setActiveView("new-job");
  return true;
}

function runStageAction(action) {
  switch (action) {
    case "resume-translation-recovery":
    case "resume-translation-prepared":
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
    case "open-restored-translation-finalize":
      openBatchFinalizeDrawer({ source: "restored" });
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

async function runRedoCurrentTranslation() {
  if (!gmailState.suggestedTranslationLaunch) {
    throw new Error("No Gmail attachment is ready to redo here yet.");
  }
  const redo = currentRedoAction();
  if (!redo.visible) {
    throw new Error("Redo is not available for the current Gmail step.");
  }
  if (redo.blocked) {
    throw new Error(redo.description || "Cancel the active browser translation job before redoing this attachment.");
  }
  const confirmed = window.confirm(
    `Redo the current Gmail attachment?\n\n${redo.description || "This will clear only the translation state for the current attachment and keep the Gmail batch intact."}`,
  );
  if (!confirmed) {
    return;
  }
  gmailState.hooks.resetTranslationForGmailRedo?.(gmailState.suggestedTranslationLaunch);
  setActiveView("new-job");
  closeSessionDrawer();
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
    return "Use default folder";
  }
  const normalized = cleaned.replace(/[\\/]+$/, "");
  const parts = normalized.split(/[\\/]/).filter(Boolean);
  return parts.at(-1) || cleaned;
}

function currentWorkflowPresentation() {
  return deriveGmailWorkflowPresentation({ workflowKind: currentWorkflowKind() });
}

function currentWorkflowLabel() {
  return currentWorkflowPresentation().label;
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

function attachmentKindLabel(attachment) {
  return deriveGmailAttachmentKindLabel(attachmentMime(attachment));
}

function currentWorkflowKind() {
  return fieldValue("gmail-workflow-kind") === "interpretation" ? "interpretation" : "translation";
}

function bootstrapMessageContext() {
  return gmailState.bootstrap?.defaults?.message_context || {};
}

function pendingIntakeContext() {
  return gmailState.bootstrap?.pending_intake_context || {};
}

function currentClickDiagnostics() {
  return gmailState.bootstrap?.click_diagnostics || {};
}

function currentSourceGmailUrl() {
  const clickDiagnostics = currentClickDiagnostics();
  return String(
    gmailState.bootstrap?.current_handoff_context?.source_gmail_url
    || gmailState.bootstrap?.defaults?.message_context?.source_gmail_url
    || gmailState.bootstrap?.pending_intake_context?.source_gmail_url
    || clickDiagnostics.source_gmail_url
    || "",
  ).trim();
}

function updateReturnToGmailAction() {
  const button = qs("gmail-return-to-source");
  if (!button) {
    return;
  }
  const sourceUrl = currentSourceGmailUrl();
  const visible = sourceUrl !== "";
  button.classList.toggle("hidden", !visible);
  button.disabled = !visible;
  button.title = visible ? sourceUrl : "";
}

function pendingStatus() {
  return String(gmailState.bootstrap?.pending_status || "").trim().toLowerCase();
}

function pendingReviewOpen() {
  return gmailState.bootstrap?.pending_review_open === true;
}

function isWarmupPendingStatus(value) {
  return value === "warming" || value === "delayed";
}

function workspaceNeedsWarmupPolling() {
  return appState.activeView === "gmail-intake"
    && pendingReviewOpen()
    && isWarmupPendingStatus(pendingStatus());
}

function hasStableWorkspaceState() {
  return shouldTreatGmailWorkspaceAsStable({
    activeView: appState.activeView,
    loadResult: gmailState.loadResult,
    activeSession: gmailState.activeSession,
    restoredCompletedSession: gmailState.restoredCompletedSession,
    pendingStatus: pendingStatus(),
    pendingReviewOpen: pendingReviewOpen(),
  });
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
  gmailState.previewDrawerMinimized = false;
  setPreviewDrawerOpen(false);
  renderGmailRestoreBar();
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

function browserPdfAttachmentState(attachmentId) {
  return gmailState.browserPdfState.get(attachmentId) || {};
}

function setBrowserPdfAttachmentState(attachmentId, nextValue) {
  if (!attachmentId) {
    return;
  }
  const existing = browserPdfAttachmentState(attachmentId);
  gmailState.browserPdfState.set(attachmentId, {
    ...existing,
    ...nextValue,
    sourcePath: String(nextValue?.sourcePath ?? existing.sourcePath ?? "").trim(),
    previewHref: String(nextValue?.previewHref ?? existing.previewHref ?? "").trim(),
    pageCount: Math.max(0, Number(nextValue?.pageCount ?? existing.pageCount ?? 0)),
  });
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
  if (nextOpen) {
    gmailState.reviewDrawerMinimized = false;
  }
  backdrop.classList.toggle("hidden", !nextOpen);
  backdrop.setAttribute("aria-hidden", nextOpen ? "false" : "true");
  document.body.dataset.gmailReviewDrawer = nextOpen ? "open" : "closed";
  if (nextOpen) {
    rememberCurrentReviewEvent();
  }
  renderGmailRestoreBar();
}

function openReviewDrawer() {
  if (!gmailState.loadResult?.ok || !gmailState.loadResult?.message) {
    return;
  }
  gmailState.reviewDrawerMinimized = false;
  setReviewDrawerOpen(true);
}

function closeReviewDrawer({ restore = true } = {}) {
  gmailState.reviewDrawerMinimized = Boolean(restore && gmailState.loadResult?.ok && gmailState.loadResult?.message);
  setReviewDrawerOpen(false);
  renderGmailRestoreBar();
}

function setPreviewDrawerOpen(open) {
  const backdrop = qs("gmail-preview-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  const nextOpen = Boolean(open) && isPreviewStateOpen(gmailState.previewState);
  gmailState.previewDrawerOpen = nextOpen;
  if (nextOpen) {
    gmailState.previewDrawerMinimized = false;
    gmailState.previewState = restorePreviewState(gmailState.previewState);
  }
  backdrop.classList.toggle("hidden", !nextOpen);
  backdrop.setAttribute("aria-hidden", nextOpen ? "false" : "true");
  document.body.dataset.gmailPreviewDrawer = nextOpen ? "open" : "closed";
  renderGmailRestoreBar();
}

function openPreviewDrawer() {
  if (!isPreviewStateOpen(gmailState.previewState)) {
    return;
  }
  gmailState.previewDrawerMinimized = false;
  gmailState.previewState = restorePreviewState(gmailState.previewState);
  setPreviewDrawerOpen(true);
}

function closePreviewDrawer({ restore = true } = {}) {
  if (restore && isPreviewStateOpen(gmailState.previewState)) {
    gmailState.previewState = minimizePreviewState(gmailState.previewState);
    gmailState.previewDrawerMinimized = true;
  } else {
    gmailState.previewDrawerMinimized = false;
  }
  setPreviewDrawerOpen(false);
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

function setBatchFinalizeDrawerOpen(open, { source = "active" } = {}) {
  const backdrop = qs("gmail-batch-finalize-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  if (open) {
    gmailState.batchFinalizeDrawerSource = source === "restored" ? "restored" : "active";
  } else {
    gmailState.batchFinalizeDrawerSource = "active";
  }
  const activeOpen = Boolean(open) && Boolean(gmailState.activeSession?.kind === "translation" && gmailState.activeSession?.completed);
  const restoredOpen = Boolean(open)
    && gmailState.batchFinalizeDrawerSource === "restored"
    && Boolean(gmailState.restoredCompletedSession?.kind === "translation" && gmailState.restoredCompletedSession?.completed);
  gmailState.batchFinalizeDrawerOpen = activeOpen || restoredOpen;
  backdrop.classList.toggle("hidden", !gmailState.batchFinalizeDrawerOpen);
  backdrop.setAttribute("aria-hidden", gmailState.batchFinalizeDrawerOpen ? "false" : "true");
  document.body.dataset.gmailBatchFinalizeDrawer = gmailState.batchFinalizeDrawerOpen ? "open" : "closed";
}

function openBatchFinalizeDrawer({ source = "active" } = {}) {
  const useRestored = source === "restored";
  const session = useRestored ? gmailState.restoredCompletedSession : gmailState.activeSession;
  if (!session?.kind || session.kind !== "translation" || !session.completed) {
    return;
  }
  if (useRestored) {
    gmailState.batchFinalizePreflight = null;
    gmailState.batchFinalizeResult = null;
  }
  setBatchFinalizeDrawerOpen(true, { source });
  renderBatchFinalizeSurface(session);
  if (useRestored) {
    updateGmailFinalizationReportActionState();
    return;
  }
  void refreshBatchFinalizePreflight({ forceRefresh: false }).catch((error) => {
    setPanelStatus("gmail-batch-finalize", "bad", error.message || "Gmail batch finalization preflight failed.");
    setDiagnostics("gmail-batch-finalize", error, {
      hint: error.message || "Gmail batch finalization preflight failed.",
      open: true,
    });
  });
}

function closeBatchFinalizeDrawer() {
  setBatchFinalizeDrawerOpen(false);
}

function renderBatchFinalizeSurface(activeSession = currentDisplayedBatchFinalizeSession()) {
  const nodes = {
    status: qs("gmail-batch-finalize-status"),
    summary: qs("gmail-batch-finalize-summary"),
    result: qs("gmail-batch-finalize-result"),
    button: qs("gmail-batch-finalize-run"),
  };
  renderGmailFinalizeNumericMismatchWarning();
  if (!nodes.status || !nodes.summary || !nodes.result || !nodes.button) {
    return;
  }
  const session = activeSession || currentDisplayedBatchFinalizeSession();
  const recoveredOnly = gmailState.batchFinalizeDrawerSource === "restored";
  const available = Boolean(session?.kind === "translation" && session?.completed);
  const preflight = currentBatchFinalizePreflight();
  const payload = gmailState.batchFinalizeResult;
  const normalized = payload?.normalized_payload || {};
  const finalizationState = currentBatchFinalizeState();
  const retryAvailable = Boolean(normalized.retry_available);
  const provenance = currentGmailBuildProvenance();
  const stateLabel = ({
    ready_to_finalize: "Ready",
    blocked_word_pdf_export: "Blocked",
    finalizing: "Finalizing",
    local_artifacts_ready: "Local only",
    draft_ready: "Draft ready",
    draft_failed: "Draft failed",
  })[finalizationState] || session?.status || "confirmed";
  const retryLabel = "Try Gmail reply again";
  const defaultButtonLabel = payload?.status === "ok"
    ? "Finalized"
    : retryAvailable
      ? retryLabel
      : "Create Gmail reply";
  const defaultButton = {
    label: defaultButtonLabel,
    disabled: !available,
    hidden: false,
  };
  const renderSurface = (card) => renderGmailBatchFinalizeSurfaceInto(nodes, {
    button: defaultButton,
    ...card,
  });
  if (!available) {
    renderSurface({
      statusText: "After every selected attachment is saved, create the Gmail reply with the final files.",
      summary: {
        empty: true,
        text: "Finish every Gmail attachment first to open the final reply step.",
      },
      result: {
        empty: true,
        text: "Gmail reply details will appear here after the final step.",
      },
    });
    updateGmailFinalizationReportActionState();
    closeBatchFinalizeDrawer();
    return;
  }
  const confirmedItems = session.confirmed_items || [];
  const outputFolder = fieldValue("gmail-output-dir") || gmailState.bootstrap?.defaults?.default_output_dir || "Use default folder";
  const summaryCard = {
    title: session.message?.subject || "Gmail batch ready to finalize.",
    message: recoveredOnly
      ? "Recovered Gmail reply details from the last saved attachment set are available here."
      : `${confirmedItems.length} saved attachment(s) are ready for the Gmail reply.`,
    label: stateLabel,
    tone: finalizationState === "blocked_word_pdf_export" || finalizationState === "local_artifacts_ready"
      ? "warn"
      : finalizationState === "draft_failed"
        ? "bad"
        : "ok",
    gridItems: [
      { label: "Target Language", value: session.selected_target_lang || "?" },
      { label: "Confirmed Rows", value: confirmedItems.length },
      {
        label: "Output Folder",
        value: shortOutputFolderLabel(outputFolder),
        titleValue: outputFolder,
      },
      { label: "Build Provenance", value: provenance.label, className: "word-break" },
    ],
  };
  if (recoveredOnly) {
    const recoveredStatusText = finalizationState === "draft_ready"
      ? "These recovered Gmail reply details are available to review. Start a new Gmail message normally if you need a fresh reply, or generate the finalization report here if you need the earlier files."
      : "These recovered Gmail reply details are available for review and report generation only.";
    renderSurface({
      button: {
        ...defaultButton,
        disabled: true,
        hidden: true,
      },
      statusText: recoveredStatusText,
      summary: summaryCard,
      result: {
        title: recoveredStatusText,
        message: session.actual_honorarios_path || session.actual_honorarios_pdf_path || session.session_report_path || "Recovered Gmail reply files are available.",
        label: stateLabel || "Recovered",
        tone: finalizationState === "draft_ready" ? "ok" : "info",
        gridItems: [
          { label: "DOCX", value: session.actual_honorarios_path || "Unavailable", className: "word-break" },
          { label: "PDF", value: session.actual_honorarios_pdf_path || "Unavailable", className: "word-break" },
          { label: "Session Report", value: session.session_report_path || "Unavailable", className: "word-break" },
          { label: "Recovery Source", value: session.restored_from_report ? "Recovered from an earlier Gmail reply step" : "Recovered" },
        ],
      },
    });
    updateGmailFinalizationReportActionState();
    return;
  }
  if (gmailState.batchFinalizePreflightInFlight && !payload) {
    renderSurface({
      button: {
        ...defaultButton,
        disabled: true,
      },
      statusText: "Checking the Word PDF export step before the Gmail reply is created.",
      summary: summaryCard,
      result: {
        empty: true,
        text: "Checking whether the final Word PDF step is ready...",
      },
    });
    updateGmailFinalizationReportActionState();
    return;
  }
  if (!payload && preflight && !preflight.finalization_ready) {
    renderSurface({
      button: {
        ...defaultButton,
        disabled: true,
      },
      statusText: "The final Word PDF step is blocked. Review the details here before you try again.",
      summary: summaryCard,
      result: {
        title: preflight.message || "Word PDF export is unavailable.",
        message: preflight.details || "The Word launch probe and export canary are shown below.",
        label: "Blocked",
        tone: "warn",
        gridItems: [
          { label: "Launch Preflight", value: preflight.launch_preflight?.message || "Unavailable" },
          { label: "Export Canary", value: preflight.export_canary?.message || "Unavailable" },
          { label: "Failure Phase", value: preflight.failure_phase || preflight.export_canary?.failure_phase || "Unknown" },
        ],
      },
    });
    updateGmailFinalizationReportActionState();
    return;
  }
  if (!payload && ["local_artifacts_ready", "draft_failed", "draft_ready"].includes(finalizationState)) {
    const draftCopy = finalizationState === "draft_ready"
      ? "The Gmail draft is ready for this saved attachment set."
      : session.draft_failure_reason || "The previous Gmail finalization attempt stayed recoverable in this workspace.";
    const draftStatusText = finalizationState === "draft_ready"
      ? "The Gmail reply is ready to review."
      : finalizationState === "draft_failed"
        ? "The final DOCX files were created, but the Gmail reply step failed. You can try again from here."
        : "The final DOCX files were created locally, but the Gmail reply step stayed unavailable. You can try again from here.";
    const showRetryAction = finalizationState !== "draft_ready";
    renderSurface({
      button: {
        ...defaultButton,
        label: showRetryAction ? retryLabel : defaultButtonLabel,
        disabled: !showRetryAction || (preflight && !preflight.finalization_ready),
        hidden: !showRetryAction,
      },
      statusText: draftStatusText,
      summary: summaryCard,
      result: {
        title: draftStatusText,
        message: session.actual_honorarios_path || session.actual_honorarios_pdf_path || draftCopy,
        label: stateLabel,
        tone: finalizationState === "draft_ready" ? "ok" : finalizationState === "draft_failed" ? "bad" : "warn",
        gridItems: [
          { label: "DOCX", value: session.actual_honorarios_path || "Unavailable", className: "word-break" },
          { label: "PDF", value: session.actual_honorarios_pdf_path || "Unavailable", className: "word-break" },
          { label: "Draft", value: draftCopy },
          { label: "Launch Preflight", value: preflight?.launch_preflight?.message || "Unavailable" },
          { label: "Export Canary", value: preflight?.export_canary?.message || "Unavailable" },
          { label: "Retry", value: showRetryAction ? "You can try again from this drawer." : "No retry required." },
          { label: "Build Provenance", value: provenance.label, className: "word-break" },
        ],
      },
    });
    updateGmailFinalizationReportActionState();
    return;
  }
  if (!payload && preflight?.finalization_ready) {
    renderSurface({
      button: {
        ...defaultButton,
        disabled: false,
      },
      statusText: "Every selected Gmail attachment is saved. You can create the Gmail reply when you are ready.",
      summary: summaryCard,
      result: {
        title: "Word PDF export is ready.",
        message: "The same Word export path used for the Gmail reply passed a canary export on this machine.",
        label: "Ready",
        tone: "ok",
        gridItems: [
          { label: "Launch Preflight", value: preflight.launch_preflight?.message || "Ready" },
          { label: "Export Canary", value: preflight.export_canary?.message || "Ready" },
          { label: "Checked", value: preflight.last_checked_at || "Just now" },
        ],
      },
    });
    updateGmailFinalizationReportActionState();
    return;
  }
  if (!payload) {
    renderSurface({
      button: {
        ...defaultButton,
        disabled: true,
      },
      statusText: "The Gmail reply will unlock here after the Word PDF readiness check finishes.",
      summary: summaryCard,
      result: {
        empty: true,
        text: "Create the Gmail reply after the Word PDF readiness check finishes.",
      },
    });
    updateGmailFinalizationReportActionState();
    return;
  }
  const draftStatus = normalized.gmail_draft_result?.ok
    ? "Draft ready"
    : finalizationState === "local_artifacts_ready" || payload.status === "local_only"
      ? "Local only"
      : payload.status === "draft_unavailable"
        ? "Draft unavailable"
        : finalizationState === "draft_failed" || payload.status === "draft_failed"
          ? "Draft failed"
          : "Ready";
  const tone = payload.status === "ok" ? "ok" : finalizationState === "draft_failed" ? "bad" : "warn";
  const payloadStatusText = payload.status === "ok"
    ? "The Gmail reply is ready."
    : finalizationState === "blocked_word_pdf_export"
      ? "The final Word PDF step is blocked."
      : payload.status === "local_only"
      ? "The final DOCX files were created locally, but the Gmail reply step stayed unavailable."
      : finalizationState === "draft_failed"
        ? "The final DOCX files were created, but the Gmail reply step failed. You can try again from here."
        : "The Gmail reply step completed with warnings. Review the details here.";
  renderSurface({
    button: {
      ...defaultButton,
      disabled: gmailState.batchFinalizePreflightInFlight
        || payload.status === "ok"
        || (preflight && !preflight.finalization_ready),
      hidden: payload.status === "ok",
    },
    statusText: payloadStatusText,
    summary: summaryCard,
    result: {
      title: payloadStatusText,
      message: normalized.docx_path || normalized.pdf_path || "Finalization output is available.",
      label: draftStatus,
      tone: tone === "ok" ? "ok" : tone === "warn" ? "warn" : "bad",
      gridItems: [
        { label: "DOCX", value: normalized.docx_path || "Unavailable", className: "word-break" },
        { label: "PDF", value: normalized.pdf_path || "Unavailable", className: "word-break" },
        { label: "Draft", value: normalized.gmail_draft_result?.message || normalized.draft_prereqs?.message || draftStatus },
        { label: "Launch Preflight", value: preflight?.launch_preflight?.message || "Unavailable" },
        { label: "Export Canary", value: preflight?.export_canary?.message || "Unavailable" },
        { label: "Retry", value: retryAvailable ? "You can try again from this drawer." : "No retry required." },
        { label: "Build Provenance", value: provenance.label, className: "word-break" },
      ],
    },
  });
  updateGmailFinalizationReportActionState();
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
  const blockedOnArabicReview = Boolean(translationUi.requiresArabicReview && !translationUi.arabicReviewResolved);
  button.disabled = !show || blockedOnArabicReview;
  if (!show) {
    return;
  }
  const filename = activeSession.current_attachment?.attachment?.filename || "Current Gmail attachment";
  const batchLabel = activeSession.total_items
    ? `${activeSession.current_item_number || "?"}/${activeSession.total_items}`
    : "Batch step";
  const presentation = gmailState.hooks.deriveTranslationCompletionPresentation?.({
    currentRowId: translationUi.currentRowId,
    arabicReview: {
      required: translationUi.requiresArabicReview,
      resolved: translationUi.arabicReviewResolved,
      message: translationUi.arabicReviewMessage,
      completion_key: translationUi.arabicReviewCompletionKey,
      status: translationUi.arabicReviewResolved ? "resolved" : "required",
    },
    gmailBatchContext: translationUi.currentGmailBatchContext,
    gmailCurrentStep: {
      visible: show,
      filename,
      batchLabel,
      hasMoreItems: Number(activeSession.current_item_number || 0) < Number(activeSession.total_items || 0),
    },
  });
  title.textContent = presentation?.gmailCurrentAttachment?.title || (
    blockedOnArabicReview
      ? "Review the Arabic document in Word before you save this Gmail attachment."
      : "This Gmail attachment is ready to save."
  );
  copy.textContent = presentation?.gmailCurrentAttachment?.copy || (
    blockedOnArabicReview
      ? (translationUi.arabicReviewMessage || "Open the translated DOCX in Word, save it there, then return here to save this Gmail attachment.")
      : Number(activeSession.current_item_number || 0) < Number(activeSession.total_items || 0)
        ? "Save this translated attachment, then continue with the next Gmail step."
        : "Save this translated attachment, then continue to create the Gmail reply."
  );
  chip.textContent = presentation?.gmailCurrentAttachment?.chipLabel || batchLabel;
  button.textContent = presentation?.gmailCurrentAttachment?.buttonLabel || "Save this Gmail attachment";
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
      page_count: Math.max(0, Number(item.pageCount || 0)) || undefined,
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
  const pendingContext = pendingIntakeContext();
  const currentPendingStatus = pendingStatus();
  const pendingWarming = isWarmupPendingStatus(currentPendingStatus);
  const detailsHint = qs("gmail-intake-details-summary");
  const workflow = currentWorkflowPresentation();
  if (!container) {
    return;
  }
  if (!loadResult) {
    const resolvedContext = {
      message_id: defaults.message_id || pendingContext.message_id || "",
      thread_id: defaults.thread_id || pendingContext.thread_id || "",
      subject: defaults.subject || pendingContext.subject || "",
      account_email: defaults.account_email || pendingContext.account_email || "",
    };
    const hasContext = Boolean(
      resolvedContext.message_id
      || resolvedContext.thread_id
      || resolvedContext.subject
      || resolvedContext.account_email
    );
    if (!hasContext) {
      renderGmailMessageResultInto(container, detailsHint, {
        empty: true,
        emptyText: "Open this from Gmail or load a message manually from details.",
        detailsHint: "Manual message load and output overrides stay here unless Gmail needs help finding the message.",
      });
      return;
    }
    renderGmailMessageResultInto(container, detailsHint, {
      title: currentPendingStatus === "failed"
        ? "Gmail message could not finish loading."
        : pendingWarming
          ? "Gmail message is loading."
          : "Gmail message found.",
      message: resolvedContext.subject || "Subject unavailable",
      label: currentPendingStatus === "failed"
        ? "Needs attention"
        : pendingWarming
          ? "Loading"
          : "Ready soon",
      tone: currentPendingStatus === "failed" ? "bad" : "info",
      detailsHint: pendingWarming
        ? "The message is still loading; open these details only if Gmail needs manual help."
        : "Detected Gmail details are ready; open these details only if you need manual recovery.",
      gridItems: [
        {
          label: "Gmail account",
          value: resolvedContext.account_email || "Unavailable",
          className: "word-break",
        },
        {
          label: "Workflow",
          value: workflow.label,
        },
      ],
    });
    return;
  }
  const message = loadResult.message || {};
  const attachmentCount = (message.attachments || []).length;
  renderGmailMessageResultInto(container, detailsHint, {
    title: loadResult.ok ? "Gmail message ready to review." : "Gmail message needs attention.",
    message: message.subject || "No subject",
    label: loadResult.ok ? "Ready" : "Needs attention",
    tone: loadResult.ok ? "ok" : loadResult.classification === "unavailable" ? "warn" : "bad",
    detailsHint: "Exact IDs and output overrides stay here unless you need manual recovery or troubleshooting.",
    gridItems: [
      {
        label: "From",
        value: message.from_header || "Unavailable",
        className: "word-break",
      },
      {
        label: "Gmail account",
        value: message.account_email || "Unavailable",
        className: "word-break",
      },
      {
        label: "Supported attachments",
        value: attachmentCount,
      },
      {
        label: "Workflow",
        value: workflow.label,
      },
    ],
  });
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
  const workflow = currentWorkflowPresentation();
  reviewOpenButton.disabled = !(loadResult?.ok && loadResult?.message);
  if (!reviewOpenButton.dataset.defaultLabel) {
    reviewOpenButton.dataset.defaultLabel = reviewOpenButton.textContent;
  }
  reviewOpenButton.textContent = reviewOpenButton.dataset.defaultLabel;
  reviewStatus.textContent = "Step 1: Choose workflow. Step 2: Pick attachment(s). Step 3: Preview or set start page if needed. Step 4: Continue.";
  if (!loadResult?.ok || !loadResult?.message) {
    renderGmailReviewSummaryInto(
      { summary, summaryGrid, summaryDetails },
      {
        empty: true,
        emptyText: "Load this Gmail message to choose attachments.",
      },
    );
    return;
  }
  const message = loadResult.message;
  const selectedCount = collectSelections().length;
  const outputFolder = fieldValue("gmail-output-dir") || gmailState.bootstrap?.defaults?.default_output_dir || "Use default folder";
  renderGmailReviewSummaryInto(
    { summary, summaryGrid, summaryDetails },
    {
      subject: message.subject || "No subject",
      reviewStatus: workflow.reviewStatus,
      workflowLabel: workflow.label,
      attachmentCount: attachments.length,
      chipLabel: selectedCount ? `${selectedCount} selected` : "Review ready",
      chipTone: selectedCount ? "ok" : "info",
      gridItems: [
        {
          label: "From",
          value: message.from_header || "Unavailable",
          className: "word-break",
        },
        {
          label: "Gmail account",
          value: message.account_email || "Unavailable",
          className: "word-break",
        },
        {
          label: "Exact message ID",
          value: message.message_id || "Unavailable",
          className: "word-break",
        },
        {
          label: "Exact thread ID",
          value: message.thread_id || "Unavailable",
          className: "word-break",
        },
        {
          label: "Save output in",
          value: outputFolder,
          className: "word-break",
        },
      ],
    },
  );
}

export function renderAttachmentListInto(
  container,
  attachments,
  options = {},
) {
  renderGmailAttachmentListInto(container, attachments, {
    ...options,
    formatSizeLabel: options.formatSizeLabel || formatBytes,
    resolveKindLabel: options.resolveKindLabel || attachmentKindLabel,
    resolveStartPage: options.resolveStartPage || ((attachment, state = {}) => (
      clampStartPage(attachment, state.startPage, state.pageCount)
    )),
  });
}

function renderAttachmentList(loadResult) {
  const container = qs("gmail-attachment-list");
  const startHeading = qs("gmail-review-start-heading");
  if (!container) {
    return;
  }
  const attachments = loadResult?.message?.attachments || [];
  const interpretationWorkflow = currentWorkflowKind() === "interpretation";
  syncFocusedAttachment();
  renderAttachmentListInto(container, attachments, {
    startHeading,
    interpretationWorkflow,
    focusedAttachmentId: gmailState.reviewFocusedAttachmentId,
    resolveState: (attachmentId) => attachmentState(attachmentId),
    resolveCanEditStart: (attachment) => canEditStartPage(attachment),
  });
}

export function renderReviewDetailInto(
  container,
  attachment,
  options = {},
) {
  const state = options.state || {};
  renderGmailReviewDetailInto(container, attachment, {
    ...options,
    state,
    startPage: Object.prototype.hasOwnProperty.call(options, "startPage")
      ? options.startPage
      : clampStartPage(attachment, state.startPage, state.pageCount),
  });
}

function renderReviewDetail() {
  const container = qs("gmail-review-detail");
  if (!container) {
    return;
  }
  const attachment = focusedAttachment();
  const state = attachment ? attachmentState(attachment.attachment_id) : {};
  renderReviewDetailInto(container, attachment, {
    state,
    canEditStart: attachment ? canEditStartPage(attachment) : false,
    previewLoaded: attachment
      ? (isPreviewStateOpen(gmailState.previewState) && gmailState.previewState.attachmentId === attachment.attachment_id)
      : false,
    runtimeGuard: currentGmailRuntimeGuard(),
    kindLabel: attachment ? attachmentKindLabel(attachment) : "",
  });
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
  const previewAttachment = previewAttachmentRecord();
  const previewHref = resolvedPreviewHref();
  if (!container || !summary || !status || !openTab || !applyButton || !prevButton || !nextButton || !pageInput) {
    return;
  }

  const renderResult = renderGmailPreviewPanelInto({
    container,
    summary,
    status,
    openTab,
    applyButton,
    prevButton,
    nextButton,
    pageInput,
  }, {
    attachment: previewAttachment,
    href: previewHref,
    page: previewPage(),
    pageCount: previewPageCount(),
    canApply: previewAttachment ? canEditStartPage(previewAttachment) : false,
    isPdf: previewAttachment ? isPdfAttachment(previewAttachment) : false,
    isImage: previewAttachment ? isImageAttachment(previewAttachment) : false,
  });
  if (renderResult?.shouldRenderPdfCanvas) {
    void renderActivePdfPreviewCanvas(previewAttachment);
  }
}

function renderGmailRestoreBar() {
  const bar = qs("gmail-restore-bar");
  const reviewButton = qs("gmail-restore-review");
  const previewButton = qs("gmail-restore-preview");
  if (!bar || !reviewButton || !previewButton) {
    return;
  }
  const canRestoreReview = Boolean(
    gmailState.reviewDrawerMinimized
    && !gmailState.reviewDrawerOpen
    && gmailState.loadResult?.ok
    && gmailState.loadResult?.message,
  );
  reviewButton.classList.toggle("hidden", !canRestoreReview);
  reviewButton.disabled = !canRestoreReview;
  if (canRestoreReview) {
    reviewButton.textContent = deriveGmailReviewRestoreLabel({ selectedCount: collectSelections().length });
  }

  const canRestorePreview = Boolean(
    gmailState.previewDrawerMinimized
    && !gmailState.previewDrawerOpen
    && isPreviewStateOpen(gmailState.previewState),
  );
  previewButton.classList.toggle("hidden", !canRestorePreview);
  previewButton.disabled = !canRestorePreview;
  if (canRestorePreview) {
    previewButton.textContent = deriveGmailPreviewRestoreLabel(gmailState.previewState);
  }

  bar.classList.toggle("hidden", !(canRestoreReview || canRestorePreview));
}

function updateDemoReviewAction() {
  const button = qs("gmail-load-demo-review");
  if (!button) {
    return;
  }
  const visible = appState.runtimeMode === "shadow" && !(gmailState.loadResult?.ok && gmailState.loadResult?.message);
  button.classList.toggle("hidden", !visible);
  button.disabled = !visible;
}

function renderResumeCard(activeSession) {
  const container = qs("gmail-resume-result");
  const button = qs("gmail-resume-step");
  const redoButton = qs("gmail-redo-current");
  gmailState.stage = currentGmailStage();
  const cta = currentHomeCta();
  const redo = currentRedoAction();
  if (button) {
    button.classList.toggle("hidden", !cta.visible);
    button.disabled = !cta.visible;
    button.textContent = cta.label || "Resume Current Step";
    button.dataset.gmailAction = cta.action || "";
  }
  if (redoButton) {
    redoButton.classList.toggle("hidden", !redo.visible);
    redoButton.disabled = !redo.visible || !redo.enabled;
    redoButton.textContent = redo.label || "Redo Current Attachment";
    redoButton.dataset.gmailAction = redo.action || "";
    redoButton.title = redo.blocked ? (redo.description || "Cancel the active matching job before redoing this attachment.") : "";
  }
  if (!container) {
    return;
  }
  if (!cta.visible || !activeSession) {
    renderGmailResumeCardInto(container, {
      visible: false,
      emptyText: "No Gmail step is waiting yet.",
    });
    return;
  }
  let gridItems = [];
  const stagePresentation = deriveGmailStagePresentation({
    stage: gmailState.stage,
    activeSession,
  });
  if (activeSession.kind === "translation") {
    const currentAttachment = activeSession.current_attachment?.attachment?.filename || "Current attachment";
    const batchLabel = activeSession.total_items
      ? `${activeSession.current_item_number || "?"}/${activeSession.total_items}`
      : "Batch ready";
    gridItems = [
      { label: "Status", value: stagePresentation.title || "Ready" },
      { label: "Batch", value: batchLabel },
      { label: "Current File", value: currentAttachment, className: "word-break" },
    ];
  } else if (activeSession.kind === "interpretation") {
    const noticeName = activeSession.attachment?.attachment?.filename || "Prepared notice";
    gridItems = [
      { label: "Status", value: stagePresentation.title || "Ready" },
      { label: "Notice", value: noticeName, className: "word-break" },
    ];
  }
  renderGmailResumeCardInto(container, {
    visible: true,
    title: cta.title || "Resume Current Step",
    message: cta.description || "Continue the active Gmail step when you are ready.",
    extraMessages: redo.visible ? [redo.description || ""] : [],
    label: activeSession.status || "ready",
    tone: cta.tone === "ok" ? "ok" : "info",
    gridItems,
  });
}

function renderSessionResult(activeSession) {
  const container = qs("gmail-session-result");
  if (!container) {
    return;
  }
  if (!activeSession) {
    renderGmailSessionResultInto(container, {
      empty: true,
      emptyText: "Continue Gmail from here when a translation or interpretation step is ready.",
    });
    return;
  }
  const presentation = deriveGmailStagePresentation({
    stage: gmailState.stage || currentGmailStage(),
    activeSession,
  });
  if (activeSession.kind === "translation") {
    const current = activeSession.current_attachment?.attachment || {};
    renderGmailSessionResultInto(container, {
      title: presentation.title,
      message: presentation.description,
      label: activeSession.status || "prepared",
      tone: activeSession.completed ? "ok" : "info",
      gridItems: [
        { label: "Subject", value: activeSession.message?.subject || "Unavailable" },
        { label: "Language", value: activeSession.selected_target_lang || "?" },
        { label: "Current document", value: current.filename || "Unavailable", className: "word-break" },
        { label: "Completed attachments", value: (activeSession.confirmed_items || []).length },
      ],
    });
    return;
  }
  renderGmailSessionResultInto(container, {
    title: presentation.title,
    message: presentation.description,
    label: activeSession.status || "prepared",
    tone: "info",
    gridItems: [
      { label: "Notice", value: activeSession.attachment?.attachment?.filename || "Unavailable", className: "word-break" },
      { label: "Subject", value: activeSession.message?.subject || "Unavailable" },
    ],
  });
}

function renderWorkspaceStrip() {
  const strip = qs("gmail-workspace-strip");
  if (!strip) {
    return;
  }
  const interpretationMode = String(interpretationUiSnapshot().workspaceMode || "").trim();
  const interpretationFocusedShell = appState.activeView === "new-job"
    && (interpretationMode === "gmail_review" || interpretationMode === "gmail_completed");
  const show = !interpretationFocusedShell && Boolean(gmailState.loadResult || gmailState.activeSession || gmailState.restoredCompletedSession);
  strip.classList.toggle("hidden", !show);
  if (!show) {
    return;
  }
  const title = qs("gmail-workspace-strip-title");
  const copy = qs("gmail-workspace-strip-copy");
  const action = qs("gmail-workspace-strip-action");
  gmailState.stage = currentGmailStage();
  const cta = currentHomeCta();
  const recoveredAction = currentRecoveredFinalizationAction();
  if (gmailState.activeSession && cta.visible) {
    const presentation = deriveGmailStagePresentation({
      stage: gmailState.stage,
      activeSession: gmailState.activeSession,
    });
    title.textContent = presentation.stripTitle || cta.title || "Continue Gmail step";
    const redo = currentRedoAction();
    copy.textContent = redo.visible
      ? `${presentation.stripDescription || cta.description || "Continue the Gmail step when you are ready."} You can also redo only this attachment if needed.`
      : (presentation.stripDescription || cta.description || "Continue the Gmail step when you are ready.");
    if (action) {
      action.textContent = "Continue Gmail step";
      action.dataset.gmailStripAction = cta.action || "";
    }
    return;
  }
  if (!gmailState.loadResult && !gmailState.activeSession && recoveredAction.visible) {
    title.textContent = recoveredAction.title || "Last finalized batch is recoverable.";
    copy.textContent = recoveredAction.description || "Open the recovered result only if you need the previous Gmail finalization details or report.";
    if (action) {
      action.textContent = recoveredAction.label || "Open Last Finalization Result";
      action.dataset.gmailStripAction = recoveredAction.action || "";
    }
    return;
  }
  title.textContent = "Gmail attachment ready";
  copy.textContent = "Review the Gmail message and attachments before you continue.";
  if (action) {
    action.textContent = "Review Gmail message";
    action.dataset.gmailStripAction = "open-intake";
  }
}

function updatePrepareActionState() {
  const button = qs("gmail-prepare-session");
  if (!button) {
    return;
  }
  const workflow = currentWorkflowPresentation();
  const selections = collectSelections();
  const runtimeGuard = currentGmailRuntimeGuard();
  let label = workflow.prepareLabel;
  let disabled = false;
  if (!gmailState.loadResult?.ok || !gmailState.loadResult?.message) {
    label = "Load a Gmail message first";
    disabled = true;
  } else if (!selections.length) {
    label = workflow.emptySelectionLabel;
    disabled = true;
  } else if (runtimeGuard.blocked) {
    label = "Restart live Gmail runtime to continue";
    disabled = true;
  }
  button.textContent = label;
  button.dataset.defaultLabel = label;
  button.disabled = disabled;
  button.title = runtimeGuard.blocked ? runtimeGuard.message : "";
}

function syncShellState() {
  gmailState.stage = currentGmailStage();
  if (appState.bootstrap?.normalized_payload) {
    appState.bootstrap.normalized_payload.gmail = {
      ...(appState.bootstrap.normalized_payload.gmail || {}),
      ...gmailState.bootstrap,
      load_result: gmailState.loadResult,
      active_session: gmailState.activeSession,
      restored_completed_session: gmailState.restoredCompletedSession,
      interpretation_seed: gmailState.interpretationSeed,
      suggested_translation_launch: gmailState.suggestedTranslationLaunch,
      pending_status: gmailState.bootstrap?.pending_status || "",
      pending_intake_context: gmailState.bootstrap?.pending_intake_context || {},
      pending_review_open: gmailState.bootstrap?.pending_review_open === true,
      stage: gmailState.stage,
    };
  }
  renderWorkspaceStrip();
  syncRefreshSchedule();
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
  renderGmailNoncanonicalRuntimeGuard();
  renderAttachmentList(gmailState.loadResult);
  renderReviewDetail();
  renderPreviewPanel();
  renderGmailRestoreBar();
  updateDemoReviewAction();
  updatePrepareActionState();
  updateGmailFailureReportActionState();
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
  gmailState.restoredCompletedSession = gmailPayload.restored_completed_session || null;
  gmailState.batchFinalizePreflight = gmailState.activeSession?.finalization_preflight || null;
  if (gmailState.activeSession || gmailState.loadResult) {
    gmailState.batchFinalizeDrawerSource = "active";
  }
  if (!gmailState.loadResult && !gmailState.activeSession) {
    gmailState.browserPdfState = new Map();
  }
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
  updateReturnToGmailAction();
  updateGmailFailureReportActionState();
  updateGmailFinalizationReportActionState();
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
      ? deriveGmailStagePresentation({
        stage: gmailState.stage || currentGmailStage(),
        activeSession: gmailState.activeSession,
      }).description
      : "No Gmail translation or interpretation step is active yet.",
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
      setDiagnostics("gmail", payload, { hint: "Gmail review refreshed.", open: false });
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
        source_gmail_url: currentSourceGmailUrl(),
      },
    }),
  });
  mergeBootstrapPayload({
    review_event_id: payload.normalized_payload.review_event_id,
    message_signature: payload.normalized_payload.message_signature,
  });
  gmailState.browserPdfState = new Map();
  gmailState.loadResult = payload.normalized_payload.load_result || null;
  gmailState.activeSession = null;
  gmailState.restoredCompletedSession = null;
  gmailState.interpretationSeed = null;
  gmailState.suggestedTranslationLaunch = null;
  gmailState.batchFinalizePreflight = null;
  gmailState.batchFinalizeDrawerSource = "active";
  clearGmailFailureReportContext();
  ensureSelectionState(gmailState.loadResult, null);
  resetPreviewState();
  gmailState.batchFinalizeResult = null;
  gmailState.lastFinalizationReportPayload = null;
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

async function loadDemoReview() {
  const payload = await fetchJson("/api/gmail/demo-review", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  mergeBootstrapPayload({
    review_event_id: payload.normalized_payload.review_event_id,
    message_signature: payload.normalized_payload.message_signature,
  });
  gmailState.browserPdfState = new Map();
  gmailState.loadResult = payload.normalized_payload.load_result || null;
  gmailState.activeSession = null;
  gmailState.restoredCompletedSession = null;
  gmailState.interpretationSeed = null;
  gmailState.suggestedTranslationLaunch = null;
  gmailState.batchFinalizePreflight = null;
  gmailState.batchFinalizeDrawerSource = "active";
  clearGmailFailureReportContext();
  ensureSelectionState(gmailState.loadResult, null);
  resetPreviewState();
  gmailState.batchFinalizeResult = null;
  gmailState.lastFinalizationReportPayload = null;
  renderMessageResult(gmailState.loadResult);
  renderReviewSurface();
  renderResumeCard(null);
  renderSessionResult(null);
  renderTranslationCompletionGmailStepCard(null);
  renderBatchFinalizeSurface(null);
  updateSessionButtons();
  setPanelStatus("gmail", "ok", "Demo Gmail attachments loaded for shadow review.");
  setDiagnostics("gmail", payload, { hint: "Demo Gmail attachments loaded for shadow review.", open: false });
  if (gmailState.loadResult?.ok && gmailState.loadResult?.message) {
    openReviewDrawer();
  }
  syncShellState();
}

async function fetchAttachmentPreviewPayload(attachmentId) {
  const payload = await fetchJson("/api/gmail/preview-attachment", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ attachment_id: attachmentId }),
  });
  const normalized = payload.normalized_payload || {};
  setBrowserPdfAttachmentState(attachmentId, {
    sourcePath: normalized.preview_path || "",
    previewHref: normalized.preview_href || "",
    pageCount: normalized.page_count || 0,
  });
  if (normalized.page_count) {
    applyPreviewPageCount(attachmentId, normalized.page_count);
  }
  return payload;
}

async function ensureBrowserPdfBundleForAttachment(attachment, { previewPayload = null } = {}) {
  if (!attachment || !isPdfAttachment(attachment)) {
    return {
      pageCount: 1,
      sourcePath: "",
      previewHref: "",
    };
  }
  let payload = previewPayload;
  let browserState = browserPdfAttachmentState(attachment.attachment_id);
  if (!payload && (!browserState.sourcePath || !browserState.previewHref)) {
    payload = await fetchAttachmentPreviewPayload(attachment.attachment_id);
    browserState = browserPdfAttachmentState(attachment.attachment_id);
  }
  const sourcePath = String(browserState.sourcePath || payload?.normalized_payload?.preview_path || "").trim();
  const previewHref = String(browserState.previewHref || payload?.normalized_payload?.preview_href || "").trim();
  if (!sourcePath || !previewHref) {
    throw new Error(`Preview download for ${attachment.filename || "the PDF attachment"} is unavailable.`);
  }
  const bundlePayload = await ensureBrowserPdfBundleFromUrl({
    appState,
    sourcePath,
    url: previewHref,
    attachmentId: attachment.attachment_id,
  });
  const pageCount = Math.max(1, Number(bundlePayload.page_count || browserState.pageCount || 0));
  applyPreviewPageCount(attachment.attachment_id, pageCount);
  setBrowserPdfAttachmentState(attachment.attachment_id, {
    sourcePath,
    previewHref,
    pageCount,
  });
  return {
    pageCount,
    sourcePath,
    previewHref,
  };
}

async function ensureBrowserPdfBundlesForSelections() {
  const selectedAttachments = gmailAttachments().filter((attachment) => attachmentState(attachment.attachment_id).selected);
  for (const attachment of selectedAttachments) {
    if (!isPdfAttachment(attachment)) {
      continue;
    }
    await ensureBrowserPdfBundleForAttachment(attachment);
  }
}

async function renderActivePdfPreviewCanvas(previewAttachment) {
  const container = qs("gmail-preview-frame");
  const canvas = qs("gmail-preview-canvas");
  const status = qs("gmail-preview-status");
  if (!previewAttachment || !container || !canvas || !status) {
    return;
  }
  const browserState = browserPdfAttachmentState(previewAttachment.attachment_id);
  const sourcePath = String(browserState.sourcePath || "").trim();
  const previewHref = String(browserState.previewHref || gmailState.previewState.previewHref || "").trim();
  if (!sourcePath || !previewHref) {
    container.className = "gmail-inline-preview empty-state";
    container.textContent = "Preview download is not ready for this PDF yet.";
    status.textContent = "Preview download is not ready yet. Try preview again.";
    return;
  }
  try {
    await renderBrowserPdfPreviewToCanvas({
      sourcePath,
      url: previewHref,
      attachmentId: previewAttachment.attachment_id,
      pageNumber: previewPage(),
      canvas,
      preferredWidth: Math.max(0, container.clientWidth - 32),
    });
  } catch (error) {
    rememberGmailFailureReport(error, {
      operation: "gmail_preview_render",
      attachment: previewAttachment,
    });
    container.className = "gmail-inline-preview empty-state";
    container.textContent = "Preview rendering failed for this PDF.";
    status.textContent = error.message || "Preview rendering failed.";
    setDiagnostics("gmail", error, { hint: gmailFailureHint(error, error.message || "Preview rendering failed."), open: true });
    updateGmailFailureReportActionState();
  }
}

async function previewAttachment(attachmentId) {
  const attachment = focusAttachment(attachmentId);
  if (!attachment) {
    return;
  }
  const currentState = attachmentState(attachmentId);
  const payload = await fetchAttachmentPreviewPayload(attachmentId);
  if (isPdfAttachment(attachment)) {
    await ensureBrowserPdfBundleForAttachment(attachment, { previewPayload: payload });
  }
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
  clearGmailFailureReportContext();
  setDiagnostics("gmail", payload, { hint: `Preview loaded for ${payload.normalized_payload.attachment?.filename || "attachment"}.`, open: false });
  updateGmailFailureReportActionState();
}

async function prepareSession() {
  await ensureBrowserPdfBundlesForSelections();
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
  gmailState.restoredCompletedSession = payload.normalized_payload.restored_completed_session || null;
  gmailState.interpretationSeed = payload.normalized_payload.interpretation_seed || null;
  gmailState.suggestedTranslationLaunch = payload.normalized_payload.suggested_translation_launch || null;
  gmailState.batchFinalizePreflight = gmailState.activeSession?.finalization_preflight || null;
  gmailState.batchFinalizeResult = null;
  gmailState.lastFinalizationReportPayload = null;
  ensureSelectionState(gmailState.loadResult, gmailState.activeSession);
  resetPreviewState();
  renderReviewSurface();
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderTranslationCompletionGmailStepCard(gmailState.activeSession);
  renderBatchFinalizeSurface(gmailState.activeSession);
  updateSessionButtons();
  clearGmailFailureReportContext();
  updateGmailFinalizationReportActionState();
  setDiagnostics("gmail", payload, { hint: "Gmail session prepared.", open: false });
  closePreviewDrawer({ restore: false });
  closeReviewDrawer({ restore: false });
  closeSessionDrawer();
  closeBatchFinalizeDrawer();
  if (gmailState.suggestedTranslationLaunch) {
    loadSuggestedTranslationLaunch();
  } else if (gmailState.interpretationSeed) {
    gmailState.hooks.applyInterpretationSeed?.(gmailState.interpretationSeed, { openReview: true });
    setActiveView("new-job");
  }
  gmailState.stage = currentGmailStage();
  setPanelStatus("gmail", "ok", gmailHomeStatusMessage());
  updateGmailFailureReportActionState();
  syncShellState();
}

async function handleGmailFailureReport() {
  const reportContext = currentGmailFailureReportContext();
  if (!reportContext) {
    throw new Error("No Gmail browser failure is available to report yet.");
  }
  const payload = await fetchJson("/api/power-tools/diagnostics/run-report", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      browser_failure_context: reportContext,
    }),
  });
  gmailState.lastFailureReportPayload = payload;
  setPanelStatus("gmail", "ok", "Gmail browser failure report generated for the current preview or prepare failure.");
  setDiagnostics("gmail", payload, {
    hint: payload.normalized_payload?.report_path || "Gmail browser failure report generated.",
    open: true,
  });
  updateGmailFailureReportActionState();
}

async function handleGmailFinalizationReport() {
  const reportContext = currentGmailFinalizationReportContext();
  if (!reportContext) {
    throw new Error("No Gmail finalization result is available to report yet.");
  }
  const payload = await fetchJson("/api/power-tools/diagnostics/run-report", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      gmail_finalization_context: reportContext,
    }),
  });
  gmailState.lastFinalizationReportPayload = payload;
  setPanelStatus("gmail-batch-finalize", "ok", "Gmail finalization report generated.");
  setDiagnostics("gmail-batch-finalize", payload, {
    hint: payload.normalized_payload?.report_path || "Gmail finalization report generated.",
    open: true,
  });
  updateGmailFinalizationReportActionState();
}

async function refreshBatchFinalizePreflight({ forceRefresh = false } = {}) {
  if (!(gmailState.activeSession?.kind === "translation" && gmailState.activeSession?.completed)) {
    gmailState.batchFinalizePreflight = null;
    renderBatchFinalizeSurface(gmailState.activeSession);
    return null;
  }
  gmailState.batchFinalizePreflightInFlight = true;
  renderBatchFinalizeSurface(gmailState.activeSession);
  try {
    const payload = await fetchJson("/api/gmail/batch/finalize-preflight", appState, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ force_refresh: forceRefresh }),
    });
  gmailState.activeSession = payload.normalized_payload.active_session || gmailState.activeSession;
  gmailState.restoredCompletedSession = payload.normalized_payload.restored_completed_session || gmailState.restoredCompletedSession;
  gmailState.batchFinalizePreflight = payload.normalized_payload.finalization_preflight || null;
    renderResumeCard(gmailState.activeSession);
    renderSessionResult(gmailState.activeSession);
    renderBatchFinalizeSurface(gmailState.activeSession);
    updateSessionButtons();
    setDiagnostics("gmail-batch-finalize", payload, {
      hint: payload.status === "ok"
        ? "Word PDF export canary passed for Gmail finalization."
        : payload.normalized_payload?.finalization_preflight?.message || "Word PDF export is blocked before Gmail finalization.",
      open: payload.status !== "ok",
    });
    return payload;
  } catch (error) {
    setPanelStatus("gmail-batch-finalize", "bad", error.message || "Gmail batch finalization preflight failed.");
    setDiagnostics("gmail-batch-finalize", error, {
      hint: error.message || "Gmail batch finalization preflight failed.",
      open: true,
    });
    throw error;
  } finally {
    gmailState.batchFinalizePreflightInFlight = false;
    renderBatchFinalizeSurface(gmailState.activeSession);
  }
}

async function confirmCurrentTranslation() {
  const translationUi = translationUiSnapshot();
  if (translationUi.requiresArabicReview && !translationUi.arabicReviewResolved) {
    throw new Error(translationUi.arabicReviewMessage || "Arabic DOCX review is still required before Gmail confirmation can continue.");
  }
  if (translationUi.currentJobRecoveryRequired || translationUi.currentJobStatus === "failed" || translationUi.currentJobStatus === "cancelled") {
    const failurePage = Number.isFinite(Number(translationUi.currentJobFailurePage))
      ? ` on page ${Number(translationUi.currentJobFailurePage)}`
      : "";
    const failureReason = String(translationUi.currentJobFailureReason || "").trim();
    throw new Error(
      failureReason
        ? `This Gmail attachment still needs translation recovery${failurePage}: ${failureReason}`
        : `This Gmail attachment still needs translation recovery${failurePage} before Gmail confirmation can continue.`,
    );
  }
  if (translationUi.currentJobKind === "rebuild" || !translationUi.currentJobHasSaveSeed) {
    throw new Error(
      "Only a completed translation with a durable reviewed DOCX can be confirmed for Gmail. Rebuild DOCX does not make this attachment confirmable.",
    );
  }
  const jobId = gmailState.hooks.getCurrentTranslationJobId?.() || "";
  if (!jobId) {
    throw new Error("Run a translation job for the current Gmail attachment first.");
  }
  const payload = await fetchJson("/api/gmail/batch/confirm-current", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_id: jobId,
      completion_key: translationUi.arabicReviewCompletionKey || "",
      form_values: gmailState.hooks.collectCurrentTranslationSaveValues?.() || {},
      row_id: qs("translation-row-id")?.value || null,
    }),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  gmailState.restoredCompletedSession = payload.normalized_payload.restored_completed_session || null;
  gmailState.suggestedTranslationLaunch = payload.normalized_payload.suggested_translation_launch || null;
  gmailState.batchFinalizePreflight = gmailState.activeSession?.finalization_preflight || null;
  ensureSelectionState(gmailState.loadResult, gmailState.activeSession);
  renderReviewSurface();
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderTranslationCompletionGmailStepCard(gmailState.activeSession);
  renderBatchFinalizeSurface(gmailState.activeSession);
  updateSessionButtons();
  setDiagnostics("gmail-session", payload, { hint: "Current Gmail attachment saved as a case record.", open: false });
  if (gmailState.suggestedTranslationLaunch) {
    loadSuggestedTranslationLaunch({ closeCompletionDrawer: true });
  } else if (gmailState.activeSession?.kind === "translation" && gmailState.activeSession.completed) {
    gmailState.hooks.closeTranslationCompletionDrawer?.();
    openBatchFinalizeDrawer();
  }
  syncShellState();
  window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
}

async function finalizeBatch() {
  const preflightPayload = await refreshBatchFinalizePreflight({ forceRefresh: false });
  const preflight = preflightPayload?.normalized_payload?.finalization_preflight || currentBatchFinalizePreflight();
  if (!preflight?.finalization_ready) {
    setPanelStatus(
      "gmail-batch-finalize",
      "warn",
      preflight?.message || "Word PDF export is blocked before Gmail finalization.",
    );
    updateGmailFinalizationReportActionState();
    return;
  }
  const payload = await fetchJson("/api/gmail/batch/finalize", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile_id: qs("profile-id")?.value || "",
      output_filename: fieldValue("gmail-batch-final-output-filename") || fieldValue("gmail-final-output-filename"),
    }),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  gmailState.restoredCompletedSession = payload.normalized_payload.restored_completed_session || null;
  gmailState.batchFinalizePreflight = payload.normalized_payload.finalization_preflight || gmailState.batchFinalizePreflight;
  gmailState.batchFinalizeResult = payload;
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderBatchFinalizeSurface(gmailState.activeSession);
  updateSessionButtons();
  setDiagnostics("gmail-batch-finalize", payload, { hint: payload.status === "ok" ? "The Gmail reply is ready." : "The Gmail reply step completed with warnings.", open: payload.status !== "ok" });
  updateGmailFinalizationReportActionState();
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
  gmailState.restoredCompletedSession = payload.normalized_payload.restored_completed_session || null;
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

function stopWarmupPolling() {
  gmailState.warmupPollUntil = 0;
  clearScheduledRefresh();
}

function scheduleAutoRefresh(delayMs, { replace = false } = {}) {
  if (appState.activeView !== "gmail-intake") {
    stopWarmupPolling();
    return;
  }
  if (replace) {
    clearScheduledRefresh();
  }
  if (gmailState.refreshTimer || gmailState.refreshInFlight) {
    return;
  }
  const nextDelay = Math.max(0, Number(delayMs || 0));
  gmailState.refreshTimer = window.setTimeout(async () => {
    gmailState.refreshTimer = 0;
    try {
      await refreshGmailState({ auto: true });
    } catch {
      // Silent auto-refresh failures should not steal focus from the operator.
    }
  }, nextDelay);
}

function syncRefreshSchedule() {
  if (appState.activeView !== "gmail-intake") {
    stopWarmupPolling();
    return;
  }
  if (!workspaceNeedsWarmupPolling()) {
    stopWarmupPolling();
    return;
  }
  const now = Date.now();
  if (!gmailState.warmupPollUntil || gmailState.warmupPollUntil < now) {
    gmailState.warmupPollUntil = now + WARMUP_POLL_TIMEOUT_MS;
  }
  if (now >= gmailState.warmupPollUntil) {
    stopWarmupPolling();
    return;
  }
  const elapsed = now - gmailState.lastRefreshAt;
  const delay = Math.max(AUTO_REFRESH_DELAY_MS, WARMUP_POLL_INTERVAL_MS - Math.max(0, elapsed));
  scheduleAutoRefresh(delay);
}

function maybeSchedulePassiveRefresh() {
  if (appState.activeView !== "gmail-intake") {
    stopWarmupPolling();
    return;
  }
  if (workspaceNeedsWarmupPolling()) {
    syncRefreshSchedule();
    return;
  }
  if (hasStableWorkspaceState()) {
    stopWarmupPolling();
    return;
  }
  const now = Date.now();
  if (now - gmailState.lastPassiveRefreshAt < PASSIVE_REFRESH_COOLDOWN_MS) {
    return;
  }
  gmailState.lastPassiveRefreshAt = now;
  const elapsed = Date.now() - gmailState.lastRefreshAt;
  const delay = Math.max(AUTO_REFRESH_DELAY_MS, AUTO_REFRESH_THROTTLE_MS - elapsed);
  scheduleAutoRefresh(delay, { replace: true });
}

export function initializeGmailUi(hooks) {
  gmailState.hooks = hooks || {};
  gmailState.lastRouteView = appState.activeView;
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

  qs("gmail-load-demo-review")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-load-demo-review"], { "gmail-load-demo-review": "Loading demo..." }, async () => {
      try {
        await loadDemoReview();
      } catch (error) {
        setPanelStatus("gmail", "bad", error.message || "Demo Gmail review load failed.");
        setDiagnostics("gmail", error, { hint: error.message || "Demo Gmail review load failed.", open: true });
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

  qs("gmail-return-to-source")?.addEventListener("click", () => {
    const sourceUrl = currentSourceGmailUrl();
    if (sourceUrl) {
      window.location.assign(sourceUrl);
    }
  });

  qs("gmail-restart-canonical-runtime")?.addEventListener("click", () => {
    runWithBusy(["gmail-restart-canonical-runtime"], { "gmail-restart-canonical-runtime": "Restarting..." }, async () => {
      await restartCanonicalRuntimeGuidance();
    }).catch((error) => {
      setPanelStatus("gmail", "bad", error.message || "Canonical runtime restart failed.");
      setDiagnostics("gmail", error, {
        hint: error.message || "Canonical runtime restart failed.",
        open: true,
      });
    });
  });

  qs("gmail-close-review-drawer")?.addEventListener("click", closeReviewDrawer);
  qs("gmail-minimize-review-drawer")?.addEventListener("click", closeReviewDrawer);
  qs("gmail-restore-review")?.addEventListener("click", openReviewDrawer);
  qs("gmail-review-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("gmail-review-drawer-backdrop")) {
      if (deriveGmailOverlayDismissalAction("backdrop") === "keep-open") {
        event.preventDefault();
        event.stopPropagation();
        renderGmailRestoreBar();
      }
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
    if (maybeBlockGmailReviewAction("gmail_preview_attachment")) {
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
    if (maybeBlockGmailReviewAction("gmail_preview_attachment")) {
      return;
    }
    await runWithBusy(["gmail-preview-selected"], { "gmail-preview-selected": "Loading..." }, async () => {
      try {
        await previewAttachment(attachment.attachment_id);
      } catch (error) {
        rememberGmailFailureReport(error, {
          operation: "gmail_preview_attachment",
          attachment,
        });
        setPanelStatus("gmail", "bad", error.message || "Attachment preview failed.");
        setDiagnostics("gmail", error, {
          hint: gmailFailureHint(error, error.message || "Attachment preview failed."),
          open: true,
        });
        updateGmailFailureReportActionState();
      }
    });
  });

  qs("gmail-close-preview-drawer")?.addEventListener("click", closePreviewDrawer);
  qs("gmail-minimize-preview-drawer")?.addEventListener("click", closePreviewDrawer);
  qs("gmail-restore-preview")?.addEventListener("click", openPreviewDrawer);
  qs("gmail-back-to-review-drawer")?.addEventListener("click", () => {
    closePreviewDrawer();
    openReviewDrawer();
  });
  qs("gmail-preview-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("gmail-preview-drawer-backdrop")) {
      if (deriveGmailOverlayDismissalAction("backdrop") === "keep-open") {
        event.preventDefault();
        event.stopPropagation();
        renderGmailRestoreBar();
      }
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
    if (maybeBlockGmailReviewAction("gmail_prepare_session")) {
      return;
    }
    await runWithBusy(["gmail-prepare-session"], { "gmail-prepare-session": "Preparing..." }, async () => {
      try {
        await prepareSession();
      } catch (error) {
        rememberGmailFailureReport(error, {
          operation: "gmail_prepare_session",
          attachment: focusedAttachment(),
        });
        setPanelStatus("gmail", "bad", error.message || "Gmail session preparation failed.");
        setDiagnostics("gmail", error, {
          hint: gmailFailureHint(error, error.message || "Gmail session preparation failed."),
          open: true,
        });
        updateGmailFailureReportActionState();
      }
    });
  });

  qs("gmail-generate-failure-report")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-generate-failure-report"], { "gmail-generate-failure-report": "Generating..." }, async () => {
      try {
        await handleGmailFailureReport();
      } catch (error) {
        setPanelStatus("gmail", "bad", error.message || "Gmail browser failure report generation failed.");
        setDiagnostics("gmail", error, {
          hint: error.message || "Gmail browser failure report generation failed.",
          open: true,
        });
      }
    });
  });

  qs("gmail-batch-finalize-report")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-batch-finalize-report"], { "gmail-batch-finalize-report": "Generating..." }, async () => {
      try {
        await handleGmailFinalizationReport();
      } catch (error) {
        setPanelStatus("gmail-batch-finalize", "bad", error.message || "Gmail finalization report generation failed.");
        setDiagnostics("gmail-batch-finalize", error, {
          hint: error.message || "Gmail finalization report generation failed.",
          open: true,
        });
      }
    });
  });

  qs("gmail-resume-step")?.addEventListener("click", (event) => {
    runStageAction(event.currentTarget?.dataset.gmailAction || "");
  });

  qs("gmail-redo-current")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-redo-current"], { "gmail-redo-current": "Preparing..." }, async () => {
      try {
        await runRedoCurrentTranslation();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Redo current attachment failed.");
        setDiagnostics("gmail-session", error, {
          hint: error.message || "Redo current attachment failed.",
          open: true,
        });
      }
    });
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
    await runWithBusy(["gmail-finalize-interpretation"], { "gmail-finalize-interpretation": "Creating..." }, async () => {
      try {
        await finalizeInterpretation();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Creating the Gmail reply failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Creating the Gmail reply failed.", open: true });
      }
    });
  });

  qs("interpretation-finalize-gmail")?.addEventListener("click", async () => {
    await runWithBusy(["interpretation-finalize-gmail"], { "interpretation-finalize-gmail": "Creating..." }, async () => {
      try {
        await finalizeInterpretation();
      } catch (error) {
        gmailState.hooks.recoverInterpretationValidationError?.(error);
        setPanelStatus("gmail-session", "bad", error.message || "Creating the Gmail reply failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Creating the Gmail reply failed.", open: true });
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
        gmailState.batchFinalizePreflight = null;
        gmailState.batchFinalizeResult = null;
        clearGmailFailureReportContext();
        gmailState.lastFinalizationReportPayload = null;
        closeReviewDrawer({ restore: false });
        closeBatchFinalizeDrawer();
        renderGmailBootstrap({ normalized_payload: { gmail: payload.normalized_payload } });
        setDiagnostics("gmail-session", payload, { hint: "Gmail review reset.", open: false });
        setDiagnostics("gmail-batch-finalize", payload, { hint: "Gmail review reset.", open: false });
        closeSessionDrawer();
      } catch (error) {
        setPanelStatus("gmail-session", "bad", error.message || "Gmail review reset failed.");
        setDiagnostics("gmail-session", error, { hint: error.message || "Gmail review reset failed.", open: true });
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

  window.addEventListener("focus", maybeSchedulePassiveRefresh);
  window.addEventListener("legalpdf:translation-ui-state-changed", () => {
    renderResumeCard(gmailState.activeSession);
    renderTranslationCompletionGmailStepCard(gmailState.activeSession);
    renderBatchFinalizeSurface(gmailState.activeSession);
    setPanelStatus(
      "gmail",
      gmailState.loadResult?.ok ? "ok" : "",
      gmailHomeStatusMessage(),
    );
    syncShellState();
  });
  window.addEventListener("legalpdf:interpretation-ui-state-changed", () => {
    renderResumeCard(gmailState.activeSession);
    syncShellState();
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      maybeSchedulePassiveRefresh();
    }
  });
  window.addEventListener("legalpdf:route-state-changed", () => {
    const previousView = gmailState.lastRouteView;
    gmailState.lastRouteView = appState.activeView;
    if (appState.activeView === "gmail-intake") {
      renderResumeCard(gmailState.activeSession);
      renderTranslationCompletionGmailStepCard(gmailState.activeSession);
      renderBatchFinalizeSurface(gmailState.activeSession);
      renderWorkspaceStrip();
      if (previousView !== "gmail-intake") {
        maybeSchedulePassiveRefresh();
      } else {
        syncRefreshSchedule();
      }
      return;
    }
    stopWarmupPolling();
    resetPreviewState();
    closeReviewDrawer({ restore: false });
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && gmailState.previewDrawerOpen) {
      if (deriveGmailOverlayDismissalAction("escape") === "minimize") {
        event.preventDefault();
        closePreviewDrawer();
      }
      return;
    }
    if (event.key === "Escape" && gmailState.reviewDrawerOpen) {
      if (deriveGmailOverlayDismissalAction("escape") === "minimize") {
        event.preventDefault();
        closeReviewDrawer();
      }
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
