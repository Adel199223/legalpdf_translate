import { fetchJson } from "./api.js";
import { applyActionFailureFeedbackToUi } from "./action_feedback_presentation.js";
import { appState, setActiveView } from "./state.js";
import {
  browserPdfDiagnosticsFromError,
  ensureBrowserPdfBundleFromUrl,
  renderBrowserPdfPreviewToCanvas,
} from "./browser_pdf.js";
import { runWithBusy } from "./busy_ui.js";
import {
  setDiagnostics,
  setPanelStatus,
} from "./diagnostics_ui.js";
import { deriveGmailLiveRuntimeGuard } from "./gmail_runtime_guard.js";
import {
  renderGmailDemoReviewActionInto,
  renderGmailPrepareActionInto,
  renderGmailReturnToSourceActionInto,
} from "./gmail_action_ui.js";
import {
  buildGmailDemoReviewActionPresentation,
  buildGmailPrepareActionPresentation,
  buildGmailReturnToSourceActionPresentation,
} from "./gmail_action_presentation.js";
import {
  renderGmailAttachmentListInto,
  renderGmailReviewDetailInto,
} from "./gmail_attachment_ui.js";
import {
  buildGmailAttachmentListPresentation,
  buildGmailReviewDetailPresentation,
} from "./gmail_attachment_presentation.js";
import {
  buildGmailBatchFinalizeSurfacePresentation,
  buildGmailNumericMismatchWarningPresentation,
} from "./gmail_finalize_presentation.js";
import {
  buildGmailResumeCardPresentation,
  buildGmailSessionButtonRules,
  buildGmailSessionResultPresentation,
  buildGmailTranslationStepCardPresentation,
  buildGmailTranslationStepContext,
  buildGmailWorkspaceStripPresentation,
} from "./gmail_session_presentation.js";
import {
  renderGmailDrawerChromeInto,
  renderGmailReviewChromeInto,
  renderGmailDetailsOpenInto,
  renderGmailDrawerDatasetDefaultsInto,
  renderGmailInputValueInto,
} from "./gmail_control_ui.js";
import { renderGmailBatchFinalizeSurfaceInto } from "./gmail_finalize_ui.js";
import { renderGmailReportActionInto } from "./gmail_report_ui.js";
import {
  buildGmailFailureReportActionPresentation,
  buildGmailFinalizationReportActionPresentation,
} from "./gmail_report_presentation.js";
import {
  buildGmailMessageResultPresentation,
  buildGmailReviewSummaryPresentation,
} from "./gmail_result_presentation.js";
import {
  renderGmailMessageResultInto,
  renderGmailReviewSummaryInto,
} from "./gmail_result_ui.js";
import { renderGmailNoncanonicalRuntimeGuardInto } from "./gmail_runtime_guard_ui.js";
import {
  renderGmailPdfPreviewFallbackInto,
  renderGmailPreviewPanelInto,
} from "./gmail_preview_ui.js";
import { buildGmailPreviewPanelPresentation } from "./gmail_preview_presentation.js";
import { buildGmailRestoreBarPresentation } from "./gmail_restore_presentation.js";
import { renderGmailRestoreBarInto } from "./gmail_restore_ui.js";
import {
  buildGmailHomeCtaPresentation,
  buildGmailPanelStatusPresentation,
  buildGmailStagePresentation,
} from "./gmail_stage_presentation.js";
import {
  buildGmailContextDefaultsPresentation,
  buildGmailSimulatorDefaultsPresentation,
} from "./gmail_context_presentation.js";
import { buildGmailReviewChromePresentation } from "./gmail_control_presentation.js";
import {
  renderGmailContextDefaultsInto,
  renderGmailNumericMismatchWarningInto,
  renderGmailResumeCardInto,
  renderGmailSessionButtonsInto,
  renderGmailSessionResultInto,
  renderGmailSimulatorDefaultsInto,
  renderGmailTranslationStepCardInto,
} from "./gmail_ui.js";
import { renderGmailResumeActionsInto } from "./gmail_session_ui.js";
import { renderGmailWorkspaceStripInto } from "./gmail_workspace_ui.js";
import {
  applyPreviewStateStartPage,
  buildGmailSelectionStateMap,
  clearConsumedReviewState,
  clampGmailAttachmentStartPage,
  deriveGmailOverlayDismissalAction,
  deriveGmailAttachmentStartEditable,
  deriveGmailAttachmentKindLabel,
  deriveGmailFocusedAttachmentId,
  deriveGmailRedoAction,
  deriveRecoveredFinalizationAction,
  createClosedPreviewState,
  deriveGmailStage,
  deriveGmailWorkflowPresentation,
  isPreviewStateOpen,
  minimizePreviewState,
  normalizeGmailAttachmentSelectionState,
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

function applyActionFailureFeedback(
  error,
  { panelSlot = "", diagnosticsSlot = "", fallback = "", diagnosticsHint = "" } = {},
) {
  return applyActionFailureFeedbackToUi(
    error,
    { panelSlot, diagnosticsSlot, fallback, diagnosticsHint },
    { setPanelStatus, setDiagnostics },
  );
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
  renderGmailReportActionInto(button, buildGmailFailureReportActionPresentation({
    failureReportContext: gmailState.lastFailureReportContext,
  }));
}

function updateGmailFinalizationReportActionState() {
  const button = qs("gmail-batch-finalize-report");
  renderGmailReportActionInto(button, buildGmailFinalizationReportActionPresentation({
    finalizationReportContext: currentGmailFinalizationReportContext(),
    lastFinalizationReportPayload: gmailState.lastFinalizationReportPayload,
  }));
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
  const presentation = buildGmailNumericMismatchWarningPresentation(warning);
  renderGmailNumericMismatchWarningInto(container, presentation);
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
  return buildGmailHomeCtaPresentation({
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
  return currentPanelStatusPresentation().gmail.message;
}

function currentPanelStatusPresentation() {
  const stage = gmailState.stage || currentGmailStage();
  return buildGmailPanelStatusPresentation({
    stage,
    activeSession: gmailState.activeSession,
    loadResult: gmailState.loadResult,
    recoveredAction: currentRecoveredFinalizationAction(),
    clickDiagnostics: currentClickDiagnostics(),
  });
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
  const presentation = buildGmailReturnToSourceActionPresentation({
    sourceUrl: currentSourceGmailUrl(),
  });
  renderGmailReturnToSourceActionInto(button, presentation);
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
  const presentation = buildGmailContextDefaultsPresentation({
    defaults: data?.defaults,
  });
  renderGmailContextDefaultsInto({
    messageId: qs("gmail-message-id"),
    threadId: qs("gmail-thread-id"),
    subject: qs("gmail-subject"),
    accountEmail: qs("gmail-account-email"),
    outputDir: qs("gmail-output-dir"),
    targetLang: qs("gmail-target-lang"),
  }, presentation);
}

function resetPreviewState() {
  gmailState.previewState = createClosedPreviewState();
  gmailState.previewDrawerMinimized = false;
  setPreviewDrawerOpen(false);
  renderGmailRestoreBar();
}

function canEditStartPage(attachment) {
  return deriveGmailAttachmentStartEditable({
    workflowKind: currentWorkflowKind(),
    attachment,
  });
}

function clampStartPage(attachment, rawValue, pageCountOverride = null) {
  return clampGmailAttachmentStartPage({
    editable: Boolean(attachment && canEditStartPage(attachment)),
    rawValue,
    pageCount: pageCountOverride ?? (gmailState.selectionState.get(attachment?.attachment_id)?.pageCount || 0),
  });
}

function attachmentState(attachmentId) {
  return normalizeGmailAttachmentSelectionState(gmailState.selectionState.get(attachmentId));
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
  gmailState.selectionState.set(attachmentId, normalizeGmailAttachmentSelectionState(nextValue));
}

function ensureSelectionState(loadResult, activeSession) {
  const message = loadResult?.message || null;
  gmailState.selectionState = buildGmailSelectionStateMap({
    attachments: message?.attachments || [],
    existingSelectionState: gmailState.selectionState,
    activeSession,
    workflowKind: currentWorkflowKind(),
  });
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
  const nextId = deriveGmailFocusedAttachmentId({
    attachments,
    selectionState: gmailState.selectionState,
    currentFocusedAttachmentId: gmailState.reviewFocusedAttachmentId,
    activeSession: gmailState.activeSession,
  });
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
  renderGmailDrawerChromeInto(
    { backdrop, body: document.body },
    { open: nextOpen, bodyDatasetKey: "gmailReviewDrawer" },
  );
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
  renderGmailDrawerChromeInto(
    { backdrop, body: document.body },
    { open: nextOpen, bodyDatasetKey: "gmailPreviewDrawer" },
  );
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
  renderGmailDrawerChromeInto(
    { backdrop, body: document.body },
    { open: gmailState.sessionDrawerOpen, bodyDatasetKey: "gmailSessionDrawer" },
  );
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
  renderGmailDrawerChromeInto(
    { backdrop, body: document.body },
    { open: gmailState.batchFinalizeDrawerOpen, bodyDatasetKey: "gmailBatchFinalizeDrawer" },
  );
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
    applyActionFailureFeedback(error, {
      panelSlot: "gmail-batch-finalize",
      diagnosticsSlot: "gmail-batch-finalize",
      fallback: "Gmail batch finalization preflight failed.",
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
  const preflight = currentBatchFinalizePreflight();
  const payload = gmailState.batchFinalizeResult;
  const finalizationState = currentBatchFinalizeState();
  const provenance = currentGmailBuildProvenance();
  const outputFolder = fieldValue("gmail-output-dir") || gmailState.bootstrap?.defaults?.default_output_dir || "Use default folder";
  const presentation = buildGmailBatchFinalizeSurfacePresentation({
    session,
    recoveredOnly,
    preflight,
    payload,
    finalizationState,
    preflightInFlight: gmailState.batchFinalizePreflightInFlight,
    outputFolder,
    provenance,
  });
  renderGmailBatchFinalizeSurfaceInto(nodes, presentation);
  updateGmailFinalizationReportActionState();
  if (presentation.closeDrawer) {
    closeBatchFinalizeDrawer();
  }
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
  const stepContext = buildGmailTranslationStepContext({ activeSession, translationUi });
  const presentation = stepContext.hookPayload
    ? gmailState.hooks.deriveTranslationCompletionPresentation?.(stepContext.hookPayload)
    : null;
  renderGmailTranslationStepCardInto({
    card,
    title,
    copy,
    chip,
    button,
  },
    buildGmailTranslationStepCardPresentation({
      stepContext,
      translationUi,
      hookPresentation: presentation,
    }),
  );
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
  renderGmailMessageResultInto(container, detailsHint, buildGmailMessageResultPresentation({
    loadResult,
    defaults,
    pendingContext,
    pendingStatus: currentPendingStatus,
    pendingWarming,
    workflow,
  }));
}

function renderReviewSummary(loadResult) {
  const summary = qs("gmail-review-summary");
  const summaryGrid = qs("gmail-review-summary-grid");
  const summaryDetails = qs("gmail-review-summary-details");
  const reviewStatus = qs("gmail-review-status");
  const reviewOpenButton = qs("gmail-open-review");
  if (!summary || !summaryGrid || !reviewStatus || !reviewOpenButton) {
    return;
  }
  const workflow = currentWorkflowPresentation();
  renderGmailReviewChromeInto({
    status: reviewStatus,
    openButton: reviewOpenButton,
  }, buildGmailReviewChromePresentation({ loadResult }));
  const selectedCount = collectSelections().length;
  const outputFolder = fieldValue("gmail-output-dir") || gmailState.bootstrap?.defaults?.default_output_dir || "Use default folder";
  renderGmailReviewSummaryInto(
    { summary, summaryGrid, summaryDetails },
    buildGmailReviewSummaryPresentation({
      loadResult,
      workflow,
      selectedCount,
      outputFolder,
    }),
  );
}

export function renderAttachmentListInto(
  container,
  attachments,
  options = {},
) {
  const normalizedAttachments = Array.isArray(attachments) ? attachments : [];
  const resolveState = options.resolveState || (() => ({ selected: false, startPage: 1, pageCount: 0 }));
  const resolveCanEditStart = options.resolveCanEditStart || (() => false);
  const resolveKindLabel = options.resolveKindLabel || attachmentKindLabel;
  const resolveStartPage = options.resolveStartPage || ((attachment, state = {}) => (
    clampStartPage(attachment, state.startPage, state.pageCount)
  ));
  const formatSizeLabel = options.formatSizeLabel || formatBytes;
  const attachmentStates = new Map();
  const canEditStartByAttachmentId = new Map();
  const kindLabelsByAttachmentId = new Map();
  const startPagesByAttachmentId = new Map();
  const sizeLabelsByAttachmentId = new Map();
  for (const attachment of normalizedAttachments) {
    const attachmentId = attachment?.attachment_id || "";
    const state = resolveState(attachmentId) || {};
    attachmentStates.set(attachmentId, state);
    canEditStartByAttachmentId.set(attachmentId, resolveCanEditStart(attachment) === true);
    kindLabelsByAttachmentId.set(attachmentId, resolveKindLabel(attachment));
    startPagesByAttachmentId.set(attachmentId, resolveStartPage(attachment, state));
    sizeLabelsByAttachmentId.set(attachmentId, formatSizeLabel(attachment?.size_bytes || 0));
  }
  const presentation = buildGmailAttachmentListPresentation({
    attachments: normalizedAttachments,
    interpretationWorkflow: options.interpretationWorkflow === true,
    focusedAttachmentId: options.focusedAttachmentId || "",
    attachmentStates,
    canEditStartByAttachmentId,
    kindLabelsByAttachmentId,
    startPagesByAttachmentId,
    sizeLabelsByAttachmentId,
  });
  renderGmailAttachmentListInto(container, presentation, { startHeading: options.startHeading || null });
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
  const presentation = buildGmailReviewDetailPresentation({
    attachment,
    state,
    canEditStart: options.canEditStart === true,
    previewLoaded: options.previewLoaded === true,
    runtimeGuard: options.runtimeGuard || { blocked: false },
    kindLabel: options.kindLabel || "",
    startPage: Object.prototype.hasOwnProperty.call(options, "startPage")
      ? options.startPage
      : clampStartPage(attachment, state.startPage, state.pageCount),
  });
  renderGmailReviewDetailInto(container, presentation);
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

  const presentation = buildGmailPreviewPanelPresentation({
    attachment: previewAttachment,
    href: previewHref,
    page: previewPage(),
    pageCount: previewPageCount(),
    canApply: previewAttachment ? canEditStartPage(previewAttachment) : false,
    isPdf: previewAttachment ? isPdfAttachment(previewAttachment) : false,
    isImage: previewAttachment ? isImageAttachment(previewAttachment) : false,
  });
  const renderResult = renderGmailPreviewPanelInto({
    container,
    summary,
    status,
    openTab,
    applyButton,
    prevButton,
    nextButton,
    pageInput,
  }, presentation);
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
  const presentation = buildGmailRestoreBarPresentation({
    reviewDrawerMinimized: gmailState.reviewDrawerMinimized,
    reviewDrawerOpen: gmailState.reviewDrawerOpen,
    loadResult: gmailState.loadResult,
    previewDrawerMinimized: gmailState.previewDrawerMinimized,
    previewDrawerOpen: gmailState.previewDrawerOpen,
    previewState: gmailState.previewState,
    selectedCount: collectSelections().length,
  });
  renderGmailRestoreBarInto({ bar, reviewButton, previewButton }, presentation);
}

function updateDemoReviewAction() {
  const button = qs("gmail-load-demo-review");
  if (!button) {
    return;
  }
  const presentation = buildGmailDemoReviewActionPresentation({
    runtimeMode: appState.runtimeMode,
    loadResult: gmailState.loadResult,
  });
  renderGmailDemoReviewActionInto(button, presentation);
}

function renderResumeCard(activeSession) {
  const container = qs("gmail-resume-result");
  const button = qs("gmail-resume-step");
  const redoButton = qs("gmail-redo-current");
  gmailState.stage = currentGmailStage();
  const cta = currentHomeCta();
  const redo = currentRedoAction();
  renderGmailResumeActionsInto({ resumeButton: button, redoButton }, { cta, redo });
  if (!container) {
    return;
  }
  const stagePresentation = buildGmailStagePresentation({
    stage: gmailState.stage,
    activeSession,
  });
  renderGmailResumeCardInto(container, buildGmailResumeCardPresentation({
    activeSession,
    cta,
    redo,
    stagePresentation,
  }));
}

function renderSessionResult(activeSession) {
  const container = qs("gmail-session-result");
  if (!container) {
    return;
  }
  const presentation = buildGmailStagePresentation({
    stage: gmailState.stage || currentGmailStage(),
    activeSession,
  });
  renderGmailSessionResultInto(container, buildGmailSessionResultPresentation({
    activeSession,
    stagePresentation: presentation,
  }));
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
  if (!show) {
    renderGmailWorkspaceStripInto({ strip }, { visible: false });
    return;
  }
  const title = qs("gmail-workspace-strip-title");
  const copy = qs("gmail-workspace-strip-copy");
  const action = qs("gmail-workspace-strip-action");
  gmailState.stage = currentGmailStage();
  const cta = currentHomeCta();
  const recoveredAction = currentRecoveredFinalizationAction();
  let stagePresentation = {};
  let redo = {};
  if (gmailState.activeSession && cta.visible) {
    stagePresentation = buildGmailStagePresentation({
      stage: gmailState.stage,
      activeSession: gmailState.activeSession,
    });
    redo = currentRedoAction();
  }
  renderGmailWorkspaceStripInto({ strip, title, copy, action }, buildGmailWorkspaceStripPresentation({
    show,
    loadResult: gmailState.loadResult,
    activeSession: gmailState.activeSession,
    cta,
    redo,
    recoveredAction,
    stagePresentation,
  }));
}

function updatePrepareActionState() {
  const button = qs("gmail-prepare-session");
  if (!button) {
    return;
  }
  const presentation = buildGmailPrepareActionPresentation({
    workflow: currentWorkflowPresentation(),
    loadResult: gmailState.loadResult,
    selections: collectSelections(),
    runtimeGuard: currentGmailRuntimeGuard(),
  });
  renderGmailPrepareActionInto(button, presentation);
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
  const presentation = buildGmailSessionButtonRules({
    activeSession,
    translationReady: Boolean(gmailState.suggestedTranslationLaunch),
    interpretationReady: Boolean(gmailState.interpretationSeed),
  });
  renderGmailSessionButtonsInto(presentation.rules.map(([id, enabled]) => [qs(id), enabled]));
  if (!presentation.sessionAvailable) {
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
  const panelStage = gmailState.stage || currentGmailStage();
  const panelStatus = buildGmailPanelStatusPresentation({
    stage: panelStage,
    activeSession: gmailState.activeSession,
    loadResult: gmailState.loadResult,
    recoveredAction: currentRecoveredFinalizationAction(),
    clickDiagnostics: currentClickDiagnostics(),
  });
  setPanelStatus(
    "gmail",
    panelStatus.gmail.tone,
    panelStatus.gmail.message,
  );
  setPanelStatus(
    "gmail-session",
    panelStatus.session.tone,
    panelStatus.session.message,
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
  renderGmailDetailsOpenInto(qs("gmail-intake-details"), { open: false });
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
    renderGmailPdfPreviewFallbackInto({ container, status }, {
      containerMessage: "Preview download is not ready for this PDF yet.",
      statusMessage: "Preview download is not ready yet. Try preview again.",
    });
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
    const feedback = applyActionFailureFeedback(error, {
      diagnosticsSlot: "gmail",
      fallback: "Preview rendering failed.",
      diagnosticsHint: (message) => gmailFailureHint(error, message),
    });
    renderGmailPdfPreviewFallbackInto({ container, status }, {
      containerMessage: "Preview rendering failed for this PDF.",
      statusMessage: feedback.message,
    });
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
    applyActionFailureFeedback(error, {
      panelSlot: "gmail-batch-finalize",
      diagnosticsSlot: "gmail-batch-finalize",
      fallback: "Gmail batch finalization preflight failed.",
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
  renderGmailDrawerDatasetDefaultsInto(document.body);

  qs("gmail-context-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusy(["gmail-load-message"], { "gmail-load-message": "Loading..." }, async () => {
      try {
        await loadMessage();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "gmail",
          diagnosticsSlot: "gmail",
          fallback: "Gmail message load failed.",
        });
      }
    });
  });

  qs("gmail-load-demo-review")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-load-demo-review"], { "gmail-load-demo-review": "Loading demo..." }, async () => {
      try {
        await loadDemoReview();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "gmail",
          diagnosticsSlot: "gmail",
          fallback: "Demo Gmail review load failed.",
        });
      }
    });
  });

  qs("gmail-use-simulator-defaults")?.addEventListener("click", () => {
    const defaults = appState.extensionDiagnostics?.simulator_defaults || {};
    const presentation = buildGmailSimulatorDefaultsPresentation({ defaults });
    renderGmailSimulatorDefaultsInto({
      messageId: qs("gmail-message-id"),
      threadId: qs("gmail-thread-id"),
      subject: qs("gmail-subject"),
      accountEmail: qs("gmail-account-email"),
    }, presentation);
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
      applyActionFailureFeedback(error, {
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Canonical runtime restart failed.",
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
        applyActionFailureFeedback(error, {
          panelSlot: "gmail",
          diagnosticsSlot: "gmail",
          fallback: "Attachment preview failed.",
        });
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
      renderGmailInputValueInto(startPage, clamped);
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
    renderGmailInputValueInto(startPage, clamped);
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
        applyActionFailureFeedback(error, {
          panelSlot: "gmail",
          diagnosticsSlot: "gmail",
          fallback: "Attachment preview failed.",
          diagnosticsHint: (message) => gmailFailureHint(error, message),
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
    renderGmailInputValueInto(input, clamped);
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
        applyActionFailureFeedback(error, {
          panelSlot: "gmail",
          diagnosticsSlot: "gmail",
          fallback: "Gmail session preparation failed.",
          diagnosticsHint: (message) => gmailFailureHint(error, message),
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
        applyActionFailureFeedback(error, {
          panelSlot: "gmail",
          diagnosticsSlot: "gmail",
          fallback: "Gmail browser failure report generation failed.",
        });
      }
    });
  });

  qs("gmail-batch-finalize-report")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-batch-finalize-report"], { "gmail-batch-finalize-report": "Generating..." }, async () => {
      try {
        await handleGmailFinalizationReport();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-batch-finalize",
          diagnosticsSlot: "gmail-batch-finalize",
          fallback: "Gmail finalization report generation failed.",
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
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-session",
          diagnosticsSlot: "gmail-session",
          fallback: "Redo current attachment failed.",
        });
      }
    });
  });

  qs("translation-gmail-confirm-current")?.addEventListener("click", async () => {
    await runWithBusy(["translation-gmail-confirm-current"], { "translation-gmail-confirm-current": "Confirming..." }, async () => {
      try {
        await confirmCurrentTranslation();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-session",
          diagnosticsSlot: "gmail-session",
          fallback: "Gmail attachment confirmation failed.",
        });
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
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-session",
          diagnosticsSlot: "gmail-session",
          fallback: "Gmail attachment confirmation failed.",
        });
      }
    });
  });

  qs("gmail-finalize-batch")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-finalize-batch"], { "gmail-finalize-batch": "Finalizing..." }, async () => {
      try {
        await finalizeBatch();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-session",
          diagnosticsSlot: "gmail-session",
          fallback: "Gmail batch finalization failed.",
        });
      }
    });
  });

  qs("gmail-finalize-interpretation")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-finalize-interpretation"], { "gmail-finalize-interpretation": "Creating..." }, async () => {
      try {
        await finalizeInterpretation();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-session",
          diagnosticsSlot: "gmail-session",
          fallback: "Creating the Gmail reply failed.",
        });
      }
    });
  });

  qs("interpretation-finalize-gmail")?.addEventListener("click", async () => {
    await runWithBusy(["interpretation-finalize-gmail"], { "interpretation-finalize-gmail": "Creating..." }, async () => {
      try {
        await finalizeInterpretation();
      } catch (error) {
        gmailState.hooks.recoverInterpretationValidationError?.(error);
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-session",
          diagnosticsSlot: "gmail-session",
          fallback: "Creating the Gmail reply failed.",
        });
      }
    });
  });

  qs("gmail-refresh")?.addEventListener("click", async () => {
    await runWithBusy(["gmail-refresh"], { "gmail-refresh": "Refreshing..." }, async () => {
      try {
        await refreshGmailState();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "gmail",
          diagnosticsSlot: "gmail",
          fallback: "Gmail refresh failed.",
        });
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
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-session",
          diagnosticsSlot: "gmail-session",
          fallback: "Gmail review reset failed.",
        });
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
        applyActionFailureFeedback(error, {
          panelSlot: "gmail-batch-finalize",
          diagnosticsSlot: "gmail-batch-finalize",
          fallback: "Gmail batch finalization failed.",
        });
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
