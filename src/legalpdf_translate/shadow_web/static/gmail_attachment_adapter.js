import {
  buildGmailAttachmentListAdapterPresentation,
  buildGmailReviewDetailAdapterPresentation,
} from "./gmail_attachment_presentation.js";
import {
  renderGmailAttachmentListInto,
  renderGmailReviewDetailInto,
} from "./gmail_attachment_ui.js";
import { clampGmailAttachmentStartPage } from "./gmail_review_state.js";

function hasOwnOption(options, key) {
  return Object.prototype.hasOwnProperty.call(options || {}, key);
}

function clampReviewDetailStartPage(state, canEditStart) {
  return clampGmailAttachmentStartPage({
    editable: canEditStart,
    rawValue: state?.startPage,
    pageCount: state?.pageCount,
  });
}

export function renderAttachmentListInto(
  container,
  attachments,
  options = {},
) {
  const normalizedAttachments = Array.isArray(attachments) ? attachments : [];
  const presentation = buildGmailAttachmentListAdapterPresentation({
    attachments: normalizedAttachments,
    selectionState: options.selectionState || {},
    workflowKind: options.workflowKind || "",
    interpretationWorkflow: options.interpretationWorkflow === true,
    focusedAttachmentId: options.focusedAttachmentId || "",
    resolveState: options.resolveState || null,
    resolveCanEditStart: typeof options.resolveCanEditStart === "function"
      ? options.resolveCanEditStart
      : (() => false),
    resolveKindLabel: options.resolveKindLabel || null,
    resolveStartPage: options.resolveStartPage || null,
    formatSizeLabel: options.formatSizeLabel || null,
  });
  renderGmailAttachmentListInto(container, presentation, {
    startHeading: options.startHeading || null,
  });
}

export function renderReviewDetailInto(
  container,
  attachment,
  options = {},
) {
  const state = options.state || {};
  const canEditStart = options.canEditStart === true;
  const previewLoaded = options.previewLoaded === true;
  const presentation = buildGmailReviewDetailAdapterPresentation({
    attachment,
    state,
    canEditStart,
    previewLoaded,
    runtimeGuard: options.runtimeGuard || { blocked: false },
    kindLabel: options.kindLabel || "",
    resolveStartPage: () => clampReviewDetailStartPage(state, canEditStart),
    ...(hasOwnOption(options, "startPage") ? { startPage: options.startPage } : {}),
  });
  renderGmailReviewDetailInto(container, presentation);
}
