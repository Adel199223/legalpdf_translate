import { clearNode } from "./safe_rendering.js";

export {
  renderGmailBatchFinalizeSurfaceInto,
  renderGmailNumericMismatchWarningInto,
} from "./gmail_finalize_ui.js";
export {
  renderGmailDemoReviewActionInto,
  renderGmailPrepareActionInto,
  renderGmailReturnToSourceActionInto,
} from "./gmail_action_ui.js";
export { renderGmailReportActionInto } from "./gmail_report_ui.js";
export {
  renderGmailContextDefaultsInto,
  renderGmailSimulatorDefaultsInto,
} from "./gmail_context_ui.js";
export {
  renderGmailMessageResultInto,
  renderGmailReviewSummaryInto,
} from "./gmail_result_ui.js";
export {
  renderGmailAttachmentListInto,
  renderGmailReviewDetailInto,
} from "./gmail_attachment_ui.js";
export {
  renderGmailDrawerChromeInto,
  renderGmailReviewChromeInto,
  renderGmailDetailsOpenInto,
  renderGmailDrawerDatasetDefaultsInto,
  renderGmailInputValueInto,
} from "./gmail_control_ui.js";
export {
  renderGmailPdfPreviewFallbackInto,
  renderGmailPreviewPanelInto,
} from "./gmail_preview_ui.js";
export {
  renderGmailResumeCardInto,
  renderGmailResumeActionsInto,
  renderGmailSessionButtonsInto,
  renderGmailSessionResultInto,
  renderGmailTranslationStepCardInto,
} from "./gmail_session_ui.js";
export { renderGmailRestoreBarInto } from "./gmail_restore_ui.js";
export { renderGmailWorkspaceStripInto } from "./gmail_workspace_ui.js";

export function renderGmailNoncanonicalRuntimeGuardInto(nodes = {}, guard = {}) {
  const {
    card,
    title,
    message,
    details,
    restartButton,
    chip,
  } = nodes;
  if (!card || !title || !message || !details || !restartButton || !chip) {
    return;
  }

  card.classList.toggle("hidden", !guard.active);
  if (!guard.active) {
    clearNode(details);
    return;
  }

  title.textContent = guard.title || "";
  message.textContent = guard.message || "";
  clearNode(details);
  (Array.isArray(guard.details) ? guard.details : []).forEach((item) => {
    const detail = document.createElement("li");
    detail.textContent = String(item ?? "");
    details.appendChild(detail);
  });
  restartButton.textContent = guard.primaryLabel || "Restart from Canonical Main";
  chip.className = "status-chip warn";
  chip.textContent = "Review Paused";
}
