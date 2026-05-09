function normalizeAttachments(value) {
  return Array.isArray(value) ? value : [];
}

function attachmentId(attachment) {
  return String(attachment?.attachment_id || "");
}

function attachmentFilename(attachment) {
  return String(attachment?.filename || "Attachment");
}

function attachmentMime(attachment) {
  return String(attachment?.mime_type || "Unknown");
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

function defaultKindLabel(attachment) {
  const normalized = String(attachment?.mime_type || "").trim().toLowerCase();
  if (normalized === "application/pdf") {
    return "PDF";
  }
  if (normalized.startsWith("image/")) {
    return "Image";
  }
  return "Unknown";
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
  const mime = attachmentMime(attachment);
  const kindLabel = String(readByAttachmentId(kindLabelsByAttachmentId, id, defaultKindLabel(attachment)));
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
