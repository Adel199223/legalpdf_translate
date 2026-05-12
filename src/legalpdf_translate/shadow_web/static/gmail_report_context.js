import { browserPdfDiagnosticsFromError } from "./browser_pdf.js";
import { gmailAttachmentId } from "./gmail_attachment_metadata.js";
import { normalizeGmailAttachmentSelectionState } from "./gmail_review_state.js";

function objectOrNull(value) {
  return value && typeof value === "object" ? value : null;
}

function selectionStateFrom(source, id) {
  if (!id) {
    return normalizeGmailAttachmentSelectionState();
  }
  if (source instanceof Map) {
    return normalizeGmailAttachmentSelectionState(source.get(id));
  }
  if (source && typeof source === "object") {
    return normalizeGmailAttachmentSelectionState(source[id]);
  }
  return normalizeGmailAttachmentSelectionState();
}

function positiveNumber(value, fallback = 1) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function nonnegativeNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function previewReportState({ previewOpen = false, previewState = {} } = {}) {
  if (!previewOpen) {
    return {};
  }
  return {
    attachment_id: previewState.attachmentId || previewState.attachment_id || "",
    page: positiveNumber(previewState.page, 1),
    page_count: nonnegativeNumber(previewState.pageCount ?? previewState.page_count),
    preview_href: String(previewState.previewHref ?? previewState.preview_href ?? "").trim(),
  };
}

export function buildGmailAttachmentReportSnapshot({
  attachment = null,
  selectionState = new Map(),
} = {}) {
  const state = selectionStateFrom(selectionState, gmailAttachmentId(attachment));
  return {
    attachment_id: attachment?.attachment_id,
    filename: attachment?.filename || "",
    mime_type: attachment?.mime_type || "",
    size_bytes: Number(attachment?.size_bytes || 0),
    selected: state.selected,
    start_page: state.startPage,
    page_count: state.pageCount,
  };
}

export function buildGmailFailureReportContext({
  error = null,
  operation = "",
  attachment = null,
  capturedAt = "",
  runtimeMode = "",
  workspaceId = "",
  activeView = "",
  runtime = {},
  buildIdentity = {},
  workflowKind = "",
  focusedAttachmentId = "",
  message = {},
  attachments = [],
  selectionState = new Map(),
  previewOpen = false,
  previewState = {},
} = {}) {
  const diagnostics = {
    ...browserPdfDiagnosticsFromError(error),
    ...(objectOrNull(error?.payload?.diagnostics) || {}),
  };
  const messageContext = objectOrNull(message) || {};
  return {
    kind: "gmail_browser_failure",
    captured_at: String(capturedAt || "").trim(),
    operation: String(operation || "").trim(),
    runtime_mode: runtimeMode,
    workspace_id: workspaceId,
    active_view: activeView,
    build_sha: String(runtime?.build_sha || "").trim(),
    asset_version: String(runtime?.asset_version || "").trim(),
    build_identity: objectOrNull(buildIdentity) ? { ...buildIdentity } : {},
    workflow_kind: workflowKind,
    focused_attachment_id: attachment?.attachment_id || focusedAttachmentId || "",
    message: {
      message_id: messageContext.message_id || "",
      thread_id: messageContext.thread_id || "",
      subject: messageContext.subject || "",
      account_email: messageContext.account_email || "",
    },
    attachments: (Array.isArray(attachments) ? attachments : []).map((item) => (
      buildGmailAttachmentReportSnapshot({ attachment: item, selectionState })
    )),
    preview_state: previewReportState({ previewOpen, previewState }),
    error: {
      code: String(diagnostics.error || error?.name || "gmail_browser_failure").trim() || "gmail_browser_failure",
      message: String(error?.message || diagnostics.message || "Gmail browser failure.").trim(),
      diagnostics,
    },
  };
}

export function buildGmailFinalizationReportContext({
  batchFinalizeResult = null,
  displayedSession = null,
  runtimeMode = "",
  workspaceId = "",
  activeView = "",
  buildSha = "",
  assetVersion = "",
} = {}) {
  const normalized = objectOrNull(batchFinalizeResult?.normalized_payload) || {};
  const session = objectOrNull(displayedSession) || {};
  const rawContext = objectOrNull(normalized.finalization_report_context)
    || objectOrNull(session.finalization_report_context);
  if (!rawContext) {
    return null;
  }
  return {
    ...rawContext,
    runtime_mode: String(rawContext.runtime_mode || runtimeMode || "").trim(),
    workspace_id: String(rawContext.workspace_id || workspaceId || "").trim(),
    active_view: String(rawContext.active_view || activeView || "").trim(),
    build_sha: String(rawContext.build_sha || buildSha || "").trim(),
    asset_version: String(rawContext.asset_version || assetVersion || "").trim(),
  };
}
