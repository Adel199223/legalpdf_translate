import { deriveGmailAttachmentKindLabelForAttachment } from "./gmail_attachment_kind.js";
import {
  clampGmailAttachmentStartPage,
  deriveGmailAttachmentStartEditable,
  normalizeGmailAttachmentSelectionState,
} from "./gmail_review_state.js";

function normalizeAttachments(value) {
  return Array.isArray(value) ? value : [];
}

function attachmentId(attachment) {
  return String(attachment?.attachment_id || "");
}

function attachmentFilename(attachment) {
  return String(attachment?.filename || "Attachment");
}

function displayMimeText(attachment) {
  return String(attachment?.mime_type || "Unknown");
}

function normalizedWorkflowKind({ workflowKind = "", interpretationWorkflow = false } = {}) {
  if (String(workflowKind || "").trim() === "interpretation" || interpretationWorkflow === true) {
    return "interpretation";
  }
  return "translation";
}

function readByAttachmentId(source, id, fallback = undefined) {
  if (source instanceof Map) {
    return source.has(id) ? source.get(id) : fallback;
  }
  if (source && typeof source === "object" && Object.prototype.hasOwnProperty.call(source, id)) {
    return source[id];
  }
  return fallback;
}

function formatSizeLabel(value) {
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

function normalizeStartPage(value) {
  const parsed = Number.parseInt(String(value ?? "1").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

function pageCountText(pageCount) {
  const count = Number(pageCount || 0);
  return count > 0
    ? `${count} ${count === 1 ? "page" : "pages"}`
    : "Page count appears after preview";
}

function attachmentState(states, id) {
  const state = readByAttachmentId(states, id, {});
  return {
    selected: Boolean(state?.selected),
    startPage: normalizeStartPage(state?.startPage),
    pageCount: Math.max(0, Number(state?.pageCount || 0)),
  };
}

function resolveAdapterAttachmentState({ resolveState, selectionState, id }) {
  if (typeof resolveState === "function") {
    return normalizeGmailAttachmentSelectionState(resolveState(id));
  }
  return normalizeGmailAttachmentSelectionState(readByAttachmentId(selectionState, id, {}));
}

function resolveAdapterStartEditable({ resolveCanEditStart, workflowKind, attachment }) {
  if (typeof resolveCanEditStart === "function") {
    return resolveCanEditStart(attachment) === true;
  }
  return deriveGmailAttachmentStartEditable({ workflowKind, attachment });
}

function resolveAdapterKindLabel({ resolveKindLabel, attachment }) {
  if (typeof resolveKindLabel === "function") {
    return resolveKindLabel(attachment);
  }
  return deriveGmailAttachmentKindLabelForAttachment(attachment);
}

function resolveAdapterStartPage({ resolveStartPage, attachment, state, editable }) {
  if (typeof resolveStartPage === "function") {
    return resolveStartPage(attachment, state);
  }
  return clampGmailAttachmentStartPage({
    editable,
    rawValue: state.startPage,
    pageCount: state.pageCount,
  });
}

function buildAttachmentRow({
  attachment,
  selectedInputType,
  focusedAttachmentId,
  attachmentStates,
  canEditStartByAttachmentId,
  kindLabelsByAttachmentId,
  startPagesByAttachmentId,
  sizeLabelsByAttachmentId,
}) {
  const id = attachmentId(attachment);
  const state = attachmentState(attachmentStates, id);
  const selected = state.selected === true;
  const focused = focusedAttachmentId === id;
  const canEditStart = readByAttachmentId(canEditStartByAttachmentId, id, false) === true;
  const filename = attachmentFilename(attachment);
  const mime = displayMimeText(attachment);
  const kindLabel = String(readByAttachmentId(
    kindLabelsByAttachmentId,
    id,
    deriveGmailAttachmentKindLabelForAttachment(attachment),
  ));
  const sizeLabel = String(readByAttachmentId(sizeLabelsByAttachmentId, id, formatSizeLabel(attachment?.size_bytes || 0)));
  const startPage = normalizeStartPage(readByAttachmentId(startPagesByAttachmentId, id, state.startPage));

  return {
    attachmentId: id,
    rowClassName: [
      "gmail-review-row",
      selected ? "is-selected" : "",
      focused ? "is-focused" : "",
    ].filter(Boolean).join(" "),
    tabIndex: 0,
    select: {
      cellClassName: "",
      labelClassName: "checkbox-inline gmail-review-select",
      inputType: selectedInputType,
      inputName: "gmail-review-selection",
      inputDataset: { attachmentCheckbox: id },
      checked: selected,
      text: selected ? "Selected" : "Choose",
      textClassName: "gmail-review-row-label",
    },
    file: {
      cellClassName: "gmail-review-file-cell",
      text: filename,
      className: "gmail-review-file-name",
      title: filename,
    },
    kind: {
      cellClassName: "",
      text: kindLabel,
      title: mime,
    },
    size: {
      cellClassName: "",
      text: sizeLabel,
    },
    start: canEditStart
      ? {
        cellClassName: "",
        kind: "input",
        inputType: "number",
        className: "attachment-start-page",
        min: "1",
        step: "1",
        value: String(startPage),
        dataset: { attachmentStartPage: id },
      }
      : {
        cellClassName: "",
        kind: "static",
        text: "1",
        className: "gmail-review-start-static",
      },
  };
}

export function buildGmailAttachmentListPresentation({
  attachments = [],
  interpretationWorkflow = false,
  focusedAttachmentId = "",
  attachmentStates = {},
  canEditStartByAttachmentId = {},
  kindLabelsByAttachmentId = {},
  startPagesByAttachmentId = {},
  sizeLabelsByAttachmentId = {},
} = {}) {
  const normalizedAttachments = normalizeAttachments(attachments);
  const selectedInputType = interpretationWorkflow ? "radio" : "checkbox";
  return {
    startHeadingLabel: "Start page",
    selectedInputType,
    empty: {
      className: "empty-state",
      colSpan: 5,
      text: "No supported PDF or image attachments were found in this message.",
    },
    rows: normalizedAttachments.map((attachment) => buildAttachmentRow({
      attachment,
      selectedInputType,
      focusedAttachmentId,
      attachmentStates,
      canEditStartByAttachmentId,
      kindLabelsByAttachmentId,
      startPagesByAttachmentId,
      sizeLabelsByAttachmentId,
    })),
  };
}

export function buildGmailAttachmentListAdapterPresentation({
  attachments = [],
  selectionState = {},
  workflowKind = "",
  interpretationWorkflow = false,
  focusedAttachmentId = "",
  resolveState = null,
  resolveCanEditStart = null,
  resolveKindLabel = null,
  resolveStartPage = null,
  formatSizeLabel: customFormatSizeLabel = null,
} = {}) {
  const normalizedAttachments = normalizeAttachments(attachments);
  const normalizedWorkflow = normalizedWorkflowKind({ workflowKind, interpretationWorkflow });
  const attachmentStates = new Map();
  const canEditStartByAttachmentId = new Map();
  const kindLabelsByAttachmentId = new Map();
  const startPagesByAttachmentId = new Map();
  const sizeLabelsByAttachmentId = new Map();
  const sizeFormatter = typeof customFormatSizeLabel === "function" ? customFormatSizeLabel : formatSizeLabel;

  for (const attachment of normalizedAttachments) {
    const id = attachmentId(attachment);
    const state = resolveAdapterAttachmentState({ resolveState, selectionState, id });
    const editable = resolveAdapterStartEditable({
      resolveCanEditStart,
      workflowKind: normalizedWorkflow,
      attachment,
    });
    attachmentStates.set(id, state);
    canEditStartByAttachmentId.set(id, editable);
    kindLabelsByAttachmentId.set(id, resolveAdapterKindLabel({ resolveKindLabel, attachment }));
    startPagesByAttachmentId.set(id, resolveAdapterStartPage({
      resolveStartPage,
      attachment,
      state,
      editable,
    }));
    sizeLabelsByAttachmentId.set(id, sizeFormatter(attachment?.size_bytes || 0));
  }

  return buildGmailAttachmentListPresentation({
    attachments: normalizedAttachments,
    interpretationWorkflow: normalizedWorkflow === "interpretation",
    focusedAttachmentId,
    attachmentStates,
    canEditStartByAttachmentId,
    kindLabelsByAttachmentId,
    startPagesByAttachmentId,
    sizeLabelsByAttachmentId,
  });
}

function resolveReviewDetailStartEditable({
  canEditStart,
  resolveCanEditStart,
  workflowKind,
  attachment,
}) {
  if (typeof resolveCanEditStart === "function") {
    return resolveCanEditStart(attachment) === true;
  }
  if (typeof canEditStart === "boolean") {
    return canEditStart;
  }
  return deriveGmailAttachmentStartEditable({ workflowKind, attachment });
}

export function buildGmailReviewDetailAdapterPresentation(input = {}) {
  const source = input || {};
  const {
    attachment = null,
    state = {},
    workflowKind = "",
    interpretationWorkflow = false,
    previewLoaded = false,
    runtimeGuard = { blocked: false },
    kindLabel = "",
    resolveCanEditStart = null,
    resolveKindLabel = null,
    resolveStartPage = null,
  } = source;
  const normalizedState = normalizeGmailAttachmentSelectionState(state);
  const normalizedWorkflow = normalizedWorkflowKind({ workflowKind, interpretationWorkflow });
  const editable = resolveReviewDetailStartEditable({
    canEditStart: source.canEditStart,
    resolveCanEditStart,
    workflowKind: normalizedWorkflow,
    attachment,
  });
  const resolvedKindLabel = kindLabel
    ? String(kindLabel)
    : String(resolveAdapterKindLabel({ resolveKindLabel, attachment }));
  const startPage = Object.prototype.hasOwnProperty.call(source, "startPage")
    ? source.startPage
    : resolveAdapterStartPage({
      resolveStartPage,
      attachment,
      state: normalizedState,
      editable,
    });

  return buildGmailReviewDetailPresentation({
    attachment,
    state: normalizedState,
    canEditStart: editable,
    previewLoaded: previewLoaded === true,
    runtimeGuard: runtimeGuard || { blocked: false },
    kindLabel: resolvedKindLabel,
    startPage,
  });
}

export function buildGmailReviewDetailPresentation({
  attachment = null,
  state = {},
  canEditStart = false,
  previewLoaded = false,
  runtimeGuard = { blocked: false },
  kindLabel = "",
  startPage = 1,
} = {}) {
  if (!attachment) {
    return {
      className: "result-card empty-state",
      emptyText: "Choose an attachment row to see the document details, optional preview, and start page.",
    };
  }
  const id = attachmentId(attachment);
  const filename = attachmentFilename(attachment);
  const normalizedState = {
    selected: Boolean(state?.selected),
    pageCount: Math.max(0, Number(state?.pageCount || 0)),
  };
  const selectedStateText = normalizedState.selected ? "Selected" : "Not selected";
  const previewText = previewLoaded ? " · Preview ready" : "";

  return {
    className: "result-card",
    stripClassName: "gmail-review-detail-strip",
    primaryClassName: "gmail-review-detail-primary",
    actionsClassName: "gmail-review-detail-actions",
    title: {
      tagName: "strong",
      text: filename,
      className: "word-break",
      title: filename,
    },
    meta: {
      tagName: "p",
      text: `${kindLabel} · ${selectedStateText} · ${pageCountText(normalizedState.pageCount)}${previewText}`,
      className: "gmail-review-detail-meta",
    },
    hint: {
      tagName: "p",
      text: "Preview is optional. Use it if you want to check the document or choose a later start page.",
      className: "field-hint",
    },
    startField: canEditStart
      ? {
        className: "field gmail-review-start-field",
        label: {
          tagName: "label",
          text: "Start page",
          htmlFor: "gmail-review-detail-start",
        },
        input: {
          id: "gmail-review-detail-start",
          type: "number",
          min: "1",
          step: "1",
          value: String(normalizeStartPage(startPage)),
          dataset: { detailStartPage: id },
        },
      }
      : null,
    previewButton: {
      id: "gmail-preview-selected",
      type: "button",
      className: "ghost-button",
      dataset: { previewSelected: id },
      disabled: runtimeGuard?.blocked === true,
      text: "Preview",
    },
  };
}
