import { fetchJson } from "./api.js";
import { applyActionFailureFeedbackToUi } from "./action_feedback_presentation.js";
import { appState, setActiveView } from "./state.js";
import {
  ensureBrowserPdfBundleFromUrl,
  renderBrowserPdfPreviewToCanvas,
} from "./browser_pdf.js";
import {
  setDiagnostics,
  setPanelStatus,
} from "./diagnostics_ui.js";
import { runGmailBusyAction } from "./gmail_action_runner.js";
import { deriveGmailLiveRuntimeGuard } from "./gmail_runtime_guard.js";
import {
  buildGmailRuntimeGuardBlockedDiagnosticsPresentation,
  buildGmailRuntimeGuardRestartDiagnosticsPresentation,
} from "./gmail_runtime_guard_presentation.js";
import {
  buildGmailBuildIdentity,
  buildGmailBuildProvenance,
  buildGmailRuntimeGuardDiagnostics,
  buildGmailRuntimeGuardSessionKey,
  buildGmailRuntimePayload,
} from "./gmail_runtime_presentation.js";
import {
  buildGmailAttachmentSavedDiagnosticsPresentation,
  buildGmailInitialDiagnosticsPresentations,
  buildGmailReviewRefreshDiagnosticsPresentation,
  buildGmailReviewResetDiagnosticsPresentation,
  buildGmailSessionPreparedDiagnosticsPresentation,
} from "./gmail_lifecycle_diagnostics_presentation.js";
import {
  buildGmailPassiveRefreshDecision,
  buildGmailWarmupPollingDecision,
  GMAIL_REFRESH_POLICY_DEFAULTS,
  isGmailWarmupPendingStatus,
} from "./gmail_refresh_policy.js";
import {
  renderGmailDemoReviewActionInto,
  renderGmailPrepareActionInto,
  renderGmailReturnToSourceActionInto,
} from "./gmail_action_ui.js";
import {
  buildGmailDemoReviewActionPresentation,
  buildGmailPrepareActionPresentation,
  buildGmailReturnToSourceActionPresentation,
  deriveGmailSourceUrl,
} from "./gmail_action_presentation.js";
import {
  renderAttachmentListInto,
  renderReviewDetailInto,
} from "./gmail_attachment_adapter.js";
import {
  deriveGmailAttachmentKindLabelForAttachment,
  isGmailPdfAttachment,
} from "./gmail_attachment_kind.js";
import {
  buildGmailBatchFinalizeDiagnosticsPresentation,
  buildGmailBatchFinalizePreflightDiagnosticsPresentation,
  buildGmailBatchFinalizeSurfacePresentation,
  buildGmailInterpretationFinalizeDiagnosticsPresentation,
  buildGmailNumericMismatchWarningPresentation,
} from "./gmail_finalize_presentation.js";
import {
  buildGmailBatchFinalizeSurfaceState,
  selectGmailBatchFinalizePreflight,
  selectGmailDisplayedBatchFinalizeSession,
} from "./gmail_batch_finalize_state.js";
import {
  buildGmailResumeCardPresentation,
  buildGmailSessionButtonRules,
  buildGmailSessionResultPresentation,
  buildGmailTranslationConfirmationGatePresentation,
  buildGmailTranslationStepCardPresentation,
  buildGmailTranslationStepContext,
  buildGmailWorkspaceStripAdapterPresentation,
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
  buildGmailBrowserFailureHintPresentation,
  buildGmailBrowserFailureReportDiagnosticsPresentation,
  buildGmailFailureReportActionPresentation,
  buildGmailFinalizationReportDiagnosticsPresentation,
  buildGmailFinalizationReportActionPresentation,
} from "./gmail_report_presentation.js";
import {
  buildGmailFailureReportContext,
  buildGmailFinalizationReportContext,
} from "./gmail_report_context.js";
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
import {
  buildGmailPreviewLoadedDiagnosticsPresentation,
  buildGmailPreviewPanelPresentation,
} from "./gmail_preview_presentation.js";
import {
  ensureGmailBrowserPdfBundleForAttachment,
  ensureGmailBrowserPdfBundlesForSelections,
  fetchGmailAttachmentPreviewPayload,
} from "./gmail_preview_bundle.js";
import {
  buildGmailBatchFinalizePreflightRequestPayload,
  buildGmailBatchFinalizeRequestPayload,
  buildGmailBrowserFailureReportRequestPayload,
  buildGmailConfirmCurrentTranslationRequestPayload,
  buildGmailEmptyRequestPayload,
  buildGmailFinalizationReportRequestPayload,
  buildGmailInterpretationFinalizeRequestPayload,
  buildGmailLoadMessageRequestPayload,
  buildGmailPrepareSessionRequestPayload,
  buildGmailRestartCanonicalRuntimeRequestPayload,
} from "./gmail_request_payloads.js";
import { buildGmailRestoreBarPresentation } from "./gmail_restore_presentation.js";
import { renderGmailRestoreBarInto } from "./gmail_restore_ui.js";
import {
  buildGmailHomeCtaPresentation,
  buildGmailPanelStatusPresentation,
  buildGmailStagePresentation,
} from "./gmail_stage_presentation.js";
import { buildGmailStageActionPlan } from "./gmail_stage_action_plan.js";
import {
  buildGmailContextDefaultsPresentation,
  buildGmailSimulatorDefaultsPresentation,
} from "./gmail_context_presentation.js";
import {
  buildGmailBatchFinalizeDrawerChromePresentation,
  buildGmailPreviewDrawerChromePresentation,
  buildGmailReviewDrawerChromePresentation,
  buildGmailReviewChromePresentation,
  buildGmailReviewLoadOutcomePresentation,
  buildGmailSessionDrawerChromePresentation,
} from "./gmail_control_presentation.js";
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
  applyGmailWorkflowSelectionDefaults,
  applyPreviewStateStartPage,
  buildGmailAttachmentPageCountUpdate,
  buildGmailAttachmentSelectionUpdate,
  buildGmailAttachmentStartPageUpdate,
  buildGmailPrepareSelectionsPayload,
  buildGmailPreviewPanelContext,
  buildGmailReviewLoadResetState,
  buildGmailSelectionStateMap,
  deriveGmailOverlayDismissalAction,
  deriveGmailAttachmentStartEditable,
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
  restorePreviewState,
  setPreviewStatePage,
  shouldTreatGmailWorkspaceAsStable,
  shouldIgnoreReviewRowFocusTarget,
} from "./gmail_review_state.js";
import {
  clearConsumedReviewState,
  readConsumedReviewState,
  shouldAutoOpenReview,
  writeConsumedReviewState,
} from "./gmail_review_persistence.js";
export { renderAttachmentListInto, renderReviewDetailInto } from "./gmail_attachment_adapter.js";
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

function runGmailAction({
  buttonIds = [],
  busyLabel = "",
  busyLabels = null,
  guardIds = null,
  action = null,
  failureFeedback = {},
  onError = null,
  afterError = null,
} = {}) {
  return runGmailBusyAction({
    buttonIds,
    busyLabel,
    busyLabels,
    guardIds,
    action,
    failureFeedback,
    applyFailureFeedback: applyActionFailureFeedback,
    onError,
    afterError,
  });
}

function browserBootstrapConfig() {
  return globalThis.window?.LEGALPDF_BROWSER_BOOTSTRAP || {};
}

function currentGmailRuntimePayload() {
  return buildGmailRuntimePayload({
    runtime: appState.bootstrap?.normalized_payload?.runtime || {},
    bootstrap: browserBootstrapConfig(),
    runtimeMode: appState.runtimeMode,
  });
}

function currentGmailBuildIdentity() {
  return buildGmailBuildIdentity({
    runtime: currentGmailRuntimePayload(),
    shellBuildIdentity: appState.bootstrap?.normalized_payload?.shell?.build_identity || null,
    bootstrap: browserBootstrapConfig(),
  });
}

function currentGmailBuildProvenance() {
  return buildGmailBuildProvenance({
    runtime: currentGmailRuntimePayload(),
    buildIdentity: currentGmailBuildIdentity(),
  });
}

function gmailRuntimeGuardSessionKey(buildIdentity = currentGmailBuildIdentity()) {
  return buildGmailRuntimeGuardSessionKey({
    runtimeMode: appState.runtimeMode,
    workspaceId: appState.workspaceId,
    buildIdentity,
  });
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
  return buildGmailRuntimeGuardDiagnostics({
    guard,
    operation,
    buildIdentity: currentGmailBuildIdentity(),
    runtime: currentGmailRuntimePayload(),
  });
}

function currentGmailFailureReportContext() {
  return gmailState.lastFailureReportContext && typeof gmailState.lastFailureReportContext === "object"
    ? { ...gmailState.lastFailureReportContext }
    : null;
}

function currentGmailFinalizationReportContext() {
  return buildGmailFinalizationReportContext({
    batchFinalizeResult: gmailState.batchFinalizeResult,
    displayedSession: selectGmailDisplayedBatchFinalizeSession({
      drawerSource: gmailState.batchFinalizeDrawerSource,
      activeSession: gmailState.activeSession,
      restoredCompletedSession: gmailState.restoredCompletedSession,
    }),
    runtimeMode: appState.runtimeMode,
    workspaceId: appState.workspaceId,
    activeView: appState.activeView,
    buildSha: browserBootstrapConfig().buildSha,
    assetVersion: browserBootstrapConfig().assetVersion,
  });
}

function clearGmailFailureReportContext() {
  gmailState.lastFailureReportContext = null;
  gmailState.lastFailureReportPayload = null;
}

function rememberGmailFailureReport(error, options = {}) {
  const previewContext = currentPreviewPanelContext();
  gmailState.lastFailureReportContext = buildGmailFailureReportContext({
    error,
    operation: options.operation || "",
    attachment: options.attachment || null,
    capturedAt: new Date().toISOString(),
    runtimeMode: appState.runtimeMode,
    workspaceId: appState.workspaceId,
    activeView: appState.activeView,
    runtime: currentGmailRuntimePayload(),
    buildIdentity: currentGmailBuildIdentity(),
    workflowKind: currentWorkflowKind(),
    focusedAttachmentId: gmailState.reviewFocusedAttachmentId,
    message: gmailState.loadResult?.message || {},
    attachments: gmailAttachments(),
    selectionState: gmailState.selectionState,
    previewOpen: isPreviewStateOpen(gmailState.previewState),
    previewState: {
      ...gmailState.previewState,
      page: previewContext.page,
      pageCount: previewContext.pageCount,
    },
  });
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
  const diagnosticsPresentation = buildGmailRuntimeGuardBlockedDiagnosticsPresentation({
    guard,
    diagnostics: gmailRuntimeGuardDiagnostics(guard, operation),
  });
  setDiagnostics("gmail", diagnosticsPresentation.payload, diagnosticsPresentation.presentation);
  renderReviewSurface();
  return true;
}

async function restartCanonicalRuntimeGuidance() {
  const guard = currentGmailRuntimeGuard();
  setPanelStatus("gmail", "warn", "Restarting the live Gmail browser runtime...");
  const diagnosticsPresentation = buildGmailRuntimeGuardRestartDiagnosticsPresentation({
    guard,
    diagnostics: gmailRuntimeGuardDiagnostics(guard, "gmail_restart_canonical_runtime"),
  });
  setDiagnostics("gmail", diagnosticsPresentation.payload, diagnosticsPresentation.presentation);
  const payload = await fetchJson("/api/gmail/runtime/restart-canonical", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildGmailRestartCanonicalRuntimeRequestPayload({
      mode: appState.runtimeMode,
      workspaceId: appState.workspaceId,
    })),
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

function applyGmailStageActionPlan(plan) {
  if (plan.applyTranslationLaunch && gmailState.suggestedTranslationLaunch) {
    gmailState.hooks.applyTranslationLaunch?.(gmailState.suggestedTranslationLaunch);
  }
  if (plan.applyInterpretationSeed && gmailState.interpretationSeed) {
    gmailState.hooks.applyInterpretationSeed?.(gmailState.interpretationSeed, { openReview: true });
  }
  if (plan.openInterpretationReviewDrawer) {
    gmailState.hooks.openInterpretationReviewDrawer?.();
  }
  if (plan.activeView) {
    setActiveView(plan.activeView);
  }
  if (plan.openTranslationCompletionDrawer) {
    gmailState.hooks.openTranslationCompletionDrawer?.();
  }
  if (plan.closeSessionDrawer) {
    closeSessionDrawer();
  }
  if (plan.openBatchFinalizeDrawer) {
    if (plan.batchFinalizeSource === "restored") {
      openBatchFinalizeDrawer({ source: "restored" });
    } else {
      openBatchFinalizeDrawer();
    }
  }
  if (plan.openReviewDrawer) {
    openReviewDrawer();
  }
}

function runStageAction(action) {
  const plan = buildGmailStageActionPlan({
    action,
    suggestedTranslationLaunch: gmailState.suggestedTranslationLaunch,
    interpretationSeed: gmailState.interpretationSeed,
  });
  applyGmailStageActionPlan(plan);
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

function currentWorkflowPresentation() {
  return deriveGmailWorkflowPresentation({ workflowKind: currentWorkflowKind() });
}

function currentWorkflowLabel() {
  return currentWorkflowPresentation().label;
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
  return deriveGmailSourceUrl({
    currentHandoffContext: gmailState.bootstrap?.current_handoff_context,
    defaults: gmailState.bootstrap?.defaults,
    pendingIntakeContext: gmailState.bootstrap?.pending_intake_context,
    clickDiagnostics: currentClickDiagnostics(),
  });
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
  return isGmailWarmupPendingStatus(value);
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

function currentPreviewPanelContext() {
  return buildGmailPreviewPanelContext({
    attachments: gmailAttachments(),
    previewState: gmailState.previewState,
    workflowKind: currentWorkflowKind(),
  });
}

function setReviewDrawerOpen(open) {
  const backdrop = qs("gmail-review-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  const drawerPresentation = buildGmailReviewDrawerChromePresentation({
    open,
    loadResult: gmailState.loadResult,
  });
  gmailState.reviewDrawerOpen = drawerPresentation.open;
  if (drawerPresentation.open) {
    gmailState.reviewDrawerMinimized = false;
  }
  renderGmailDrawerChromeInto(
    { backdrop, body: document.body },
    drawerPresentation,
  );
  if (drawerPresentation.open) {
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
  const drawerPresentation = buildGmailPreviewDrawerChromePresentation({
    open,
    previewState: gmailState.previewState,
  });
  gmailState.previewDrawerOpen = drawerPresentation.open;
  if (drawerPresentation.open) {
    gmailState.previewDrawerMinimized = false;
    gmailState.previewState = restorePreviewState(gmailState.previewState);
  }
  renderGmailDrawerChromeInto(
    { backdrop, body: document.body },
    drawerPresentation,
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
  const drawerPresentation = buildGmailSessionDrawerChromePresentation({
    open,
    activeSession: gmailState.activeSession,
  });
  gmailState.sessionDrawerOpen = drawerPresentation.open;
  renderGmailDrawerChromeInto(
    { backdrop, body: document.body },
    drawerPresentation,
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
  const drawerPresentation = buildGmailBatchFinalizeDrawerChromePresentation({
    open,
    source: gmailState.batchFinalizeDrawerSource,
    activeSession: gmailState.activeSession,
    restoredCompletedSession: gmailState.restoredCompletedSession,
  });
  gmailState.batchFinalizeDrawerOpen = drawerPresentation.open;
  renderGmailDrawerChromeInto(
    { backdrop, body: document.body },
    drawerPresentation,
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

function renderBatchFinalizeSurface(activeSession = null) {
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
  const surfaceState = buildGmailBatchFinalizeSurfaceState({
    activeSessionOverride: activeSession,
    drawerSource: gmailState.batchFinalizeDrawerSource,
    activeSession: gmailState.activeSession,
    restoredCompletedSession: gmailState.restoredCompletedSession,
    batchFinalizePreflight: gmailState.batchFinalizePreflight,
    batchFinalizeResult: gmailState.batchFinalizeResult,
    batchFinalizePreflightInFlight: gmailState.batchFinalizePreflightInFlight,
  });
  const provenance = currentGmailBuildProvenance();
  const outputFolder = fieldValue("gmail-output-dir") || gmailState.bootstrap?.defaults?.default_output_dir || "Use default folder";
  const presentation = buildGmailBatchFinalizeSurfacePresentation({
    ...surfaceState,
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
  return buildGmailPrepareSelectionsPayload({
    attachments: gmailAttachments(),
    selectionState: gmailState.selectionState,
    workflowKind: currentWorkflowKind(),
  });
}

function setWorkflowSelectionDefaults() {
  const workflowKind = currentWorkflowKind();
  if (workflowKind !== "interpretation") {
    return;
  }
  gmailState.selectionState = applyGmailWorkflowSelectionDefaults({
    attachments: gmailAttachments(),
    selectionState: gmailState.selectionState,
    workflowKind,
  });
}

function updateAttachmentSelection(attachmentId, selected) {
  const attachment = getAttachmentById(attachmentId);
  if (!attachment) {
    return;
  }
  gmailState.selectionState = buildGmailAttachmentSelectionUpdate({
    attachments: gmailAttachments(),
    selectionState: gmailState.selectionState,
    attachmentId,
    selected,
    workflowKind: currentWorkflowKind(),
  });
  focusAttachment(attachmentId);
}

function updateAttachmentStartPage(attachmentId, value) {
  const attachment = getAttachmentById(attachmentId);
  if (!attachment) {
    return 1;
  }
  const next = buildGmailAttachmentStartPageUpdate({
    attachment,
    state: attachmentState(attachmentId),
    value,
    workflowKind: currentWorkflowKind(),
  });
  setAttachmentState(attachmentId, next);
  return next.startPage;
}

function applyPreviewPageCount(attachmentId, pageCount) {
  const attachment = getAttachmentById(attachmentId);
  if (!attachment) {
    return;
  }
  const next = buildGmailAttachmentPageCountUpdate({
    attachment,
    state: attachmentState(attachmentId),
    pageCount,
    workflowKind: currentWorkflowKind(),
  });
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
    workflowKind: currentWorkflowKind(),
    interpretationWorkflow,
    focusedAttachmentId: gmailState.reviewFocusedAttachmentId,
    selectionState: gmailState.selectionState,
    resolveCanEditStart: (attachment) => canEditStartPage(attachment),
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
    kindLabel: attachment ? deriveGmailAttachmentKindLabelForAttachment(attachment) : "",
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
  const previewContext = buildGmailPreviewPanelContext({
    attachments: gmailAttachments(),
    previewState: gmailState.previewState,
    workflowKind: currentWorkflowKind(),
  });
  if (!container || !summary || !status || !openTab || !applyButton || !prevButton || !nextButton || !pageInput) {
    return;
  }

  const presentation = buildGmailPreviewPanelPresentation({
    attachment: previewContext.attachment,
    href: previewContext.href,
    page: previewContext.page,
    pageCount: previewContext.pageCount,
    canApply: previewContext.canApply,
    isPdf: previewContext.isPdf,
    isImage: previewContext.isImage,
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
    void renderActivePdfPreviewCanvas(previewContext.attachment);
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
  const title = qs("gmail-workspace-strip-title");
  const copy = qs("gmail-workspace-strip-copy");
  const action = qs("gmail-workspace-strip-action");
  gmailState.stage = currentGmailStage();
  const cta = currentHomeCta();
  const redo = currentRedoAction();
  const recoveredAction = currentRecoveredFinalizationAction();
  renderGmailWorkspaceStripInto({ strip, title, copy, action }, buildGmailWorkspaceStripAdapterPresentation({
    activeView: appState.activeView,
    interpretationWorkspaceMode: interpretationUiSnapshot().workspaceMode,
    stage: gmailState.stage,
    loadResult: gmailState.loadResult,
    activeSession: gmailState.activeSession,
    restoredCompletedSession: gmailState.restoredCompletedSession,
    cta,
    redo,
    recoveredAction,
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

function applyGmailReviewLoadResetState(reviewLoadState = {}) {
  mergeBootstrapPayload(reviewLoadState.bootstrapPatch);
  gmailState.browserPdfState = reviewLoadState.browserPdfState;
  gmailState.loadResult = reviewLoadState.loadResult;
  gmailState.activeSession = reviewLoadState.activeSession;
  gmailState.restoredCompletedSession = reviewLoadState.restoredCompletedSession;
  gmailState.interpretationSeed = reviewLoadState.interpretationSeed;
  gmailState.suggestedTranslationLaunch = reviewLoadState.suggestedTranslationLaunch;
  gmailState.batchFinalizePreflight = reviewLoadState.batchFinalizePreflight;
  gmailState.batchFinalizeDrawerSource = reviewLoadState.batchFinalizeDrawerSource;
  gmailState.batchFinalizeResult = reviewLoadState.batchFinalizeResult;
  gmailState.lastFinalizationReportPayload = reviewLoadState.lastFinalizationReportPayload;
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
      const diagnosticsPresentation = buildGmailReviewRefreshDiagnosticsPresentation({ payload });
      setDiagnostics("gmail", payload, diagnosticsPresentation);
    }
    return payload;
  } finally {
    gmailState.refreshInFlight = false;
  }
}

function applyGmailReviewLoadOutcomePresentation({ payload, presentation }) {
  setPanelStatus(
    "gmail",
    presentation.panelStatus.tone,
    presentation.panelStatus.message,
  );
  setDiagnostics("gmail", payload, presentation.diagnostics);
  if (presentation.intakeDetails.close) {
    renderGmailDetailsOpenInto(qs("gmail-intake-details"), { open: false });
  }
  if (presentation.reviewDrawer.open) {
    openReviewDrawer();
  }
}

async function loadMessage() {
  const payload = await fetchJson("/api/gmail/load-message", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildGmailLoadMessageRequestPayload({
      messageId: fieldValue("gmail-message-id"),
      threadId: fieldValue("gmail-thread-id"),
      subject: fieldValue("gmail-subject"),
      accountEmail: fieldValue("gmail-account-email"),
      sourceGmailUrl: currentSourceGmailUrl(),
    })),
  });
  const reviewLoadState = buildGmailReviewLoadResetState({ payload });
  applyGmailReviewLoadResetState(reviewLoadState);
  clearGmailFailureReportContext();
  ensureSelectionState(gmailState.loadResult, null);
  resetPreviewState();
  renderMessageResult(gmailState.loadResult);
  renderReviewSurface();
  renderResumeCard(null);
  renderSessionResult(null);
  renderTranslationCompletionGmailStepCard(null);
  renderBatchFinalizeSurface(null);
  updateSessionButtons();
  const outcomePresentation = buildGmailReviewLoadOutcomePresentation({
    source: "message",
    payload,
    loadResult: gmailState.loadResult,
  });
  applyGmailReviewLoadOutcomePresentation({ payload, presentation: outcomePresentation });
  syncShellState();
}

async function loadDemoReview() {
  const payload = await fetchJson("/api/gmail/demo-review", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildGmailEmptyRequestPayload()),
  });
  const reviewLoadState = buildGmailReviewLoadResetState({ payload });
  applyGmailReviewLoadResetState(reviewLoadState);
  clearGmailFailureReportContext();
  ensureSelectionState(gmailState.loadResult, null);
  resetPreviewState();
  renderMessageResult(gmailState.loadResult);
  renderReviewSurface();
  renderResumeCard(null);
  renderSessionResult(null);
  renderTranslationCompletionGmailStepCard(null);
  renderBatchFinalizeSurface(null);
  updateSessionButtons();
  const outcomePresentation = buildGmailReviewLoadOutcomePresentation({
    source: "demo",
    payload,
    loadResult: gmailState.loadResult,
  });
  applyGmailReviewLoadOutcomePresentation({ payload, presentation: outcomePresentation });
  syncShellState();
}

function gmailPreviewBundleOptions() {
  return {
    appState,
    fetchJson,
    ensureBrowserPdfBundleFromUrl,
    isPdfAttachment: isGmailPdfAttachment,
    getBrowserPdfAttachmentState: browserPdfAttachmentState,
    setBrowserPdfAttachmentState,
    applyPreviewPageCount,
  };
}

async function fetchAttachmentPreviewPayload(attachmentId) {
  return fetchGmailAttachmentPreviewPayload({
    ...gmailPreviewBundleOptions(),
    attachmentId,
  });
}

async function ensureBrowserPdfBundleForAttachment(attachment, { previewPayload = null } = {}) {
  return ensureGmailBrowserPdfBundleForAttachment({
    ...gmailPreviewBundleOptions(),
    attachment,
    previewPayload,
    fetchAttachmentPreviewPayload,
  });
}

async function ensureBrowserPdfBundlesForSelections() {
  return ensureGmailBrowserPdfBundlesForSelections({
    attachments: gmailAttachments(),
    getAttachmentState: attachmentState,
    ensureBrowserPdfBundleForAttachment,
    isPdfAttachment: isGmailPdfAttachment,
  });
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
      pageNumber: currentPreviewPanelContext().page,
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
      diagnosticsHint: (message) => buildGmailBrowserFailureHintPresentation({
        error,
        fallbackMessage: message,
      }),
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
  if (isGmailPdfAttachment(attachment)) {
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
  const diagnosticsPresentation = buildGmailPreviewLoadedDiagnosticsPresentation({
    payload,
    attachment,
  });
  setDiagnostics("gmail", payload, diagnosticsPresentation);
  updateGmailFailureReportActionState();
}

async function prepareSession() {
  await ensureBrowserPdfBundlesForSelections();
  const payload = await fetchJson("/api/gmail/prepare-session", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildGmailPrepareSessionRequestPayload({
      workflowKind: currentWorkflowKind(),
      targetLang: fieldValue("gmail-target-lang"),
      outputDir: fieldValue("gmail-output-dir"),
      selections: collectSelections(),
    })),
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
  const diagnosticsPresentation = buildGmailSessionPreparedDiagnosticsPresentation({ payload });
  setDiagnostics("gmail", payload, diagnosticsPresentation);
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
    body: JSON.stringify(buildGmailBrowserFailureReportRequestPayload({
      reportContext,
    })),
  });
  gmailState.lastFailureReportPayload = payload;
  setPanelStatus("gmail", "ok", "Gmail browser failure report generated for the current preview or prepare failure.");
  const diagnosticsPresentation = buildGmailBrowserFailureReportDiagnosticsPresentation({
    payload,
  });
  setDiagnostics("gmail", payload, diagnosticsPresentation);
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
    body: JSON.stringify(buildGmailFinalizationReportRequestPayload({
      reportContext,
    })),
  });
  gmailState.lastFinalizationReportPayload = payload;
  setPanelStatus("gmail-batch-finalize", "ok", "Gmail finalization report generated.");
  const diagnosticsPresentation = buildGmailFinalizationReportDiagnosticsPresentation({
    payload,
  });
  setDiagnostics("gmail-batch-finalize", payload, diagnosticsPresentation);
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
      body: JSON.stringify(buildGmailBatchFinalizePreflightRequestPayload({
        forceRefresh,
      })),
    });
  gmailState.activeSession = payload.normalized_payload.active_session || gmailState.activeSession;
  gmailState.restoredCompletedSession = payload.normalized_payload.restored_completed_session || gmailState.restoredCompletedSession;
  gmailState.batchFinalizePreflight = payload.normalized_payload.finalization_preflight || null;
    renderResumeCard(gmailState.activeSession);
    renderSessionResult(gmailState.activeSession);
    renderBatchFinalizeSurface(gmailState.activeSession);
    updateSessionButtons();
    const preflightDiagnosticsPresentation = buildGmailBatchFinalizePreflightDiagnosticsPresentation({
      payload,
    });
    setDiagnostics("gmail-batch-finalize", payload, preflightDiagnosticsPresentation);
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
  const confirmationGate = buildGmailTranslationConfirmationGatePresentation({
    translationUi,
    jobId: gmailState.hooks.getCurrentTranslationJobId?.() || "",
  });
  if (confirmationGate.blocked) {
    throw new Error(confirmationGate.message);
  }
  const jobId = confirmationGate.jobId;
  const payload = await fetchJson("/api/gmail/batch/confirm-current", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildGmailConfirmCurrentTranslationRequestPayload({
      jobId,
      completionKey: translationUi.arabicReviewCompletionKey || "",
      formValues: gmailState.hooks.collectCurrentTranslationSaveValues?.() || {},
      rowId: qs("translation-row-id")?.value || null,
    })),
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
  const diagnosticsPresentation = buildGmailAttachmentSavedDiagnosticsPresentation({ payload });
  setDiagnostics("gmail-session", payload, diagnosticsPresentation);
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
  const preflight = preflightPayload?.normalized_payload?.finalization_preflight || selectGmailBatchFinalizePreflight({
    drawerSource: gmailState.batchFinalizeDrawerSource,
    batchFinalizePreflight: gmailState.batchFinalizePreflight,
    displayedSession: selectGmailDisplayedBatchFinalizeSession({
      drawerSource: gmailState.batchFinalizeDrawerSource,
      activeSession: gmailState.activeSession,
      restoredCompletedSession: gmailState.restoredCompletedSession,
    }),
  });
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
    body: JSON.stringify(buildGmailBatchFinalizeRequestPayload({
      profileId: qs("profile-id")?.value || "",
      outputFilename: fieldValue("gmail-batch-final-output-filename") || fieldValue("gmail-final-output-filename"),
    })),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  gmailState.restoredCompletedSession = payload.normalized_payload.restored_completed_session || null;
  gmailState.batchFinalizePreflight = payload.normalized_payload.finalization_preflight || gmailState.batchFinalizePreflight;
  gmailState.batchFinalizeResult = payload;
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderBatchFinalizeSurface(gmailState.activeSession);
  updateSessionButtons();
  const batchDiagnosticsPresentation = buildGmailBatchFinalizeDiagnosticsPresentation({
    payload,
  });
  setDiagnostics("gmail-batch-finalize", payload, batchDiagnosticsPresentation);
  updateGmailFinalizationReportActionState();
  syncShellState();
}

async function finalizeInterpretation() {
  await gmailState.hooks.prepareInterpretationAction?.("gmail-finalize");
  const payload = await fetchJson("/api/gmail/interpretation/finalize", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildGmailInterpretationFinalizeRequestPayload({
      formValues: gmailState.hooks.collectInterpretationFormValues?.() || {},
      profileId: qs("profile-id")?.value || "",
      serviceSameChecked: Boolean(qs("service-same")?.checked),
      outputFilename: fieldValue("gmail-final-output-filename"),
    })),
  });
  gmailState.activeSession = payload.normalized_payload.active_session || null;
  gmailState.restoredCompletedSession = payload.normalized_payload.restored_completed_session || null;
  renderResumeCard(gmailState.activeSession);
  renderSessionResult(gmailState.activeSession);
  renderTranslationCompletionGmailStepCard(gmailState.activeSession);
  updateSessionButtons();
  gmailState.hooks.renderInterpretationExportResult?.(payload);
  gmailState.hooks.renderInterpretationGmailResult?.(payload);
  const interpretationDiagnosticsPresentation = buildGmailInterpretationFinalizeDiagnosticsPresentation({
    payload,
  });
  setDiagnostics("gmail-session", payload, interpretationDiagnosticsPresentation);
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
  const now = Date.now();
  const decision = buildGmailWarmupPollingDecision({
    activeView: appState.activeView,
    needsWarmupPolling: workspaceNeedsWarmupPolling(),
    warmupPollUntil: gmailState.warmupPollUntil,
    lastRefreshAt: gmailState.lastRefreshAt,
    now,
    timings: GMAIL_REFRESH_POLICY_DEFAULTS,
  });
  if (decision.action === "stop") {
    stopWarmupPolling();
    return;
  }
  gmailState.warmupPollUntil = decision.warmupPollUntil;
  scheduleAutoRefresh(decision.delayMs);
}

function maybeSchedulePassiveRefresh() {
  const now = Date.now();
  const decision = buildGmailPassiveRefreshDecision({
    activeView: appState.activeView,
    needsWarmupPolling: workspaceNeedsWarmupPolling(),
    stableWorkspaceState: hasStableWorkspaceState(),
    lastPassiveRefreshAt: gmailState.lastPassiveRefreshAt,
    lastRefreshAt: gmailState.lastRefreshAt,
    now,
    timings: GMAIL_REFRESH_POLICY_DEFAULTS,
  });
  if (decision.action === "warmup") {
    syncRefreshSchedule();
    return;
  }
  if (decision.action === "stop") {
    stopWarmupPolling();
    return;
  }
  if (decision.action === "skip") {
    return;
  }
  gmailState.lastPassiveRefreshAt = decision.lastPassiveRefreshAt;
  scheduleAutoRefresh(decision.delayMs, { replace: decision.replace });
}

export function initializeGmailUi(hooks) {
  gmailState.hooks = hooks || {};
  gmailState.lastRouteView = appState.activeView;
  for (const diagnosticsPresentation of buildGmailInitialDiagnosticsPresentations()) {
    setDiagnostics(
      diagnosticsPresentation.slot,
      diagnosticsPresentation.payload,
      diagnosticsPresentation.presentation,
    );
  }
  renderGmailDrawerDatasetDefaultsInto(document.body);

  qs("gmail-context-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runGmailAction({
      buttonIds: ["gmail-load-message"],
      busyLabel: "Loading...",
      action: () => loadMessage(),
      failureFeedback: {
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Gmail message load failed.",
      },
    });
  });

  qs("gmail-load-demo-review")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-load-demo-review"],
      busyLabel: "Loading demo...",
      action: () => loadDemoReview(),
      failureFeedback: {
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Demo Gmail review load failed.",
      },
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
    void runGmailAction({
      buttonIds: ["gmail-restart-canonical-runtime"],
      busyLabel: "Restarting...",
      action: () => restartCanonicalRuntimeGuidance(),
      failureFeedback: {
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Canonical runtime restart failed.",
      },
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
    await runGmailAction({
      buttonIds: ["gmail-preview-selected"],
      busyLabel: "Loading...",
      action: () => previewAttachment(attachmentId),
      failureFeedback: {
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Attachment preview failed.",
      },
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
    await runGmailAction({
      buttonIds: ["gmail-preview-selected"],
      busyLabel: "Loading...",
      action: () => previewAttachment(attachment.attachment_id),
      onError: (error) => {
        rememberGmailFailureReport(error, {
          operation: "gmail_preview_attachment",
          attachment,
        });
      },
      failureFeedback: (error) => ({
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Attachment preview failed.",
        diagnosticsHint: (message) => buildGmailBrowserFailureHintPresentation({
          error,
          fallbackMessage: message,
        }),
      }),
      afterError: () => {
        updateGmailFailureReportActionState();
      },
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
    gmailState.previewState = setPreviewStatePage(gmailState.previewState, currentPreviewPanelContext().page - 1);
    renderPreviewPanel();
  });

  qs("gmail-preview-next")?.addEventListener("click", () => {
    if (!isPreviewStateOpen(gmailState.previewState)) {
      return;
    }
    const previewContext = currentPreviewPanelContext();
    const upperBound = previewContext.pageCount > 0 ? previewContext.pageCount : previewContext.page + 1;
    const next = Math.min(upperBound, previewContext.page + 1);
    gmailState.previewState = setPreviewStatePage(gmailState.previewState, next);
    renderPreviewPanel();
  });

  qs("gmail-preview-page")?.addEventListener("change", (event) => {
    if (!isPreviewStateOpen(gmailState.previewState)) {
      return;
    }
    const input = event.target;
    gmailState.previewState = setPreviewStatePage(gmailState.previewState, input.value);
    const clamped = currentPreviewPanelContext().page;
    renderGmailInputValueInto(input, clamped);
    renderPreviewPanel();
  });

  qs("gmail-preview-apply")?.addEventListener("click", () => {
    const attachment = currentPreviewPanelContext().attachment;
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
    await runGmailAction({
      buttonIds: ["gmail-prepare-session"],
      busyLabel: "Preparing...",
      action: () => prepareSession(),
      onError: (error) => {
        rememberGmailFailureReport(error, {
          operation: "gmail_prepare_session",
          attachment: focusedAttachment(),
        });
      },
      failureFeedback: (error) => ({
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Gmail session preparation failed.",
        diagnosticsHint: (message) => buildGmailBrowserFailureHintPresentation({
          error,
          fallbackMessage: message,
        }),
      }),
      afterError: () => {
        updateGmailFailureReportActionState();
      },
    });
  });

  qs("gmail-generate-failure-report")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-generate-failure-report"],
      busyLabel: "Generating...",
      action: () => handleGmailFailureReport(),
      failureFeedback: {
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Gmail browser failure report generation failed.",
      },
    });
  });

  qs("gmail-batch-finalize-report")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-batch-finalize-report"],
      busyLabel: "Generating...",
      action: () => handleGmailFinalizationReport(),
      failureFeedback: {
        panelSlot: "gmail-batch-finalize",
        diagnosticsSlot: "gmail-batch-finalize",
        fallback: "Gmail finalization report generation failed.",
      },
    });
  });

  qs("gmail-resume-step")?.addEventListener("click", (event) => {
    runStageAction(event.currentTarget?.dataset.gmailAction || "");
  });

  qs("gmail-redo-current")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-redo-current"],
      busyLabel: "Preparing...",
      action: () => runRedoCurrentTranslation(),
      failureFeedback: {
        panelSlot: "gmail-session",
        diagnosticsSlot: "gmail-session",
        fallback: "Redo current attachment failed.",
      },
    });
  });

  qs("translation-gmail-confirm-current")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["translation-gmail-confirm-current"],
      busyLabel: "Confirming...",
      action: () => confirmCurrentTranslation(),
      failureFeedback: {
        panelSlot: "gmail-session",
        diagnosticsSlot: "gmail-session",
        fallback: "Gmail attachment confirmation failed.",
      },
    });
  });

  qs("gmail-load-translation-launch")?.addEventListener("click", () => {
    if (gmailState.suggestedTranslationLaunch) {
      runStageAction("resume-translation-running");
    }
  });

  qs("gmail-load-interpretation-seed")?.addEventListener("click", () => {
    if (gmailState.interpretationSeed) {
      runStageAction("resume-interpretation-review");
    }
  });

  window.addEventListener("legalpdf:open-gmail-session-drawer", () => {
    if (gmailState.activeSession) {
      openSessionDrawer();
    }
  });

  qs("gmail-confirm-translation")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-confirm-translation"],
      busyLabel: "Confirming...",
      action: () => confirmCurrentTranslation(),
      failureFeedback: {
        panelSlot: "gmail-session",
        diagnosticsSlot: "gmail-session",
        fallback: "Gmail attachment confirmation failed.",
      },
    });
  });

  qs("gmail-finalize-batch")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-finalize-batch"],
      busyLabel: "Finalizing...",
      action: () => finalizeBatch(),
      failureFeedback: {
        panelSlot: "gmail-session",
        diagnosticsSlot: "gmail-session",
        fallback: "Gmail batch finalization failed.",
      },
    });
  });

  qs("gmail-finalize-interpretation")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-finalize-interpretation"],
      busyLabel: "Creating...",
      action: () => finalizeInterpretation(),
      failureFeedback: {
        panelSlot: "gmail-session",
        diagnosticsSlot: "gmail-session",
        fallback: "Creating the Gmail reply failed.",
      },
    });
  });

  qs("interpretation-finalize-gmail")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["interpretation-finalize-gmail"],
      busyLabel: "Creating...",
      action: () => finalizeInterpretation(),
      onError: (error) => {
        gmailState.hooks.recoverInterpretationValidationError?.(error);
      },
      failureFeedback: {
        panelSlot: "gmail-session",
        diagnosticsSlot: "gmail-session",
        fallback: "Creating the Gmail reply failed.",
      },
    });
  });

  qs("gmail-refresh")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-refresh"],
      busyLabel: "Refreshing...",
      action: () => refreshGmailState(),
      failureFeedback: {
        panelSlot: "gmail",
        diagnosticsSlot: "gmail",
        fallback: "Gmail refresh failed.",
      },
    });
  });

  qs("gmail-reset")?.addEventListener("click", async () => {
    await runGmailAction({
      buttonIds: ["gmail-reset"],
      busyLabel: "Resetting...",
      action: async () => {
        const payload = await fetchJson("/api/gmail/reset", appState, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildGmailEmptyRequestPayload()),
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
        const diagnosticsPresentation = buildGmailReviewResetDiagnosticsPresentation({ payload });
        setDiagnostics("gmail-session", payload, diagnosticsPresentation);
        setDiagnostics("gmail-batch-finalize", payload, diagnosticsPresentation);
        closeSessionDrawer();
      },
      failureFeedback: {
        panelSlot: "gmail-session",
        diagnosticsSlot: "gmail-session",
        fallback: "Gmail review reset failed.",
      },
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
    await runGmailAction({
      buttonIds: ["gmail-batch-finalize-run"],
      busyLabel: "Finalizing...",
      action: () => finalizeBatch(),
      failureFeedback: {
        panelSlot: "gmail-batch-finalize",
        diagnosticsSlot: "gmail-batch-finalize",
        fallback: "Gmail batch finalization failed.",
      },
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
