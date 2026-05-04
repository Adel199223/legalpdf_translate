import { clearNode, createTextElement, setNodeTitle, setText } from "./safe_rendering.js";
import { appendResultGridItem, createResultHeader } from "./result_card_ui.js";

export function renderGmailReportActionInto(button, { available = false, label = "" } = {}) {
  if (!button) {
    return undefined;
  }
  button.classList.toggle("hidden", !available);
  button.disabled = !available;
  button.textContent = label;
  button.dataset.defaultLabel = label;
  return button;
}

export function renderGmailNumericMismatchWarningInto(container, warning = {}) {
  if (!container) {
    return undefined;
  }
  const visible = Boolean(warning?.visible);
  container.classList.toggle("hidden", !visible);
  if (!visible) {
    container.textContent = "";
    return container;
  }
  const lines = Array.isArray(warning.lines) ? warning.lines.filter(Boolean) : [];
  const detail = lines.length ? `\n${lines.join("\n")}` : "";
  container.textContent = `${warning.message || "Review recommended: some numbers from the source may not appear exactly in the translation."}${detail}`;
  container.setAttribute("role", "note");
  return container;
}

export function renderGmailTranslationStepCardInto(nodes = {}, card = {}) {
  const {
    card: cardNode,
    title,
    copy,
    chip,
    button,
  } = nodes || {};
  if (!cardNode || !title || !copy || !chip || !button) {
    return undefined;
  }

  const visible = Boolean(card.visible);
  cardNode.classList.toggle("hidden", !visible);
  button.disabled = !visible || Boolean(card.blocked);
  if (!visible) {
    return nodes;
  }

  title.textContent = card.title || "";
  copy.textContent = card.copy || "";
  chip.textContent = card.chipLabel || "";
  button.textContent = card.buttonLabel || "";
  return nodes;
}

export function renderGmailRestoreBarInto(nodes = {}, restore = {}) {
  const { bar, reviewButton, previewButton } = nodes || {};
  if (!bar || !reviewButton || !previewButton) {
    return undefined;
  }

  const review = restore.review || {};
  const preview = restore.preview || {};
  const reviewVisible = Boolean(review.visible);
  const previewVisible = Boolean(preview.visible);

  reviewButton.classList.toggle("hidden", !reviewVisible);
  reviewButton.disabled = !reviewVisible;
  if (reviewVisible) {
    reviewButton.textContent = review.label || "";
  }

  previewButton.classList.toggle("hidden", !previewVisible);
  previewButton.disabled = !previewVisible;
  if (previewVisible) {
    previewButton.textContent = preview.label || "";
  }

  bar.classList.toggle("hidden", !(reviewVisible || previewVisible));
  return nodes;
}

export function renderGmailDemoReviewActionInto(button, { visible = false } = {}) {
  if (!button) {
    return undefined;
  }

  const show = Boolean(visible);
  button.classList.toggle("hidden", !show);
  button.disabled = !show;
  return button;
}

export function renderGmailReturnToSourceActionInto(button, { visible = false, sourceUrl = "" } = {}) {
  if (!button) {
    return undefined;
  }

  const show = Boolean(visible);
  button.classList.toggle("hidden", !show);
  button.disabled = !show;
  button.title = show ? String(sourceUrl || "") : "";
  return button;
}

export function renderGmailMessageResultInto(container, detailsHint, card = {}) {
  if (!container) {
    return;
  }

  if (card.empty) {
    container.classList.add("empty-state");
    container.textContent = card.emptyText || "";
    if (detailsHint) {
      detailsHint.textContent = card.detailsHint || "";
    }
    return;
  }

  container.classList.remove("empty-state");
  clearNode(container);
  container.appendChild(createResultHeader({
    title: card.title || "",
    message: card.message || "",
    label: card.label || "",
    tone: card.tone || "info",
  }));

  const grid = document.createElement("div");
  grid.className = "result-grid";
  (Array.isArray(card.gridItems) ? card.gridItems : []).forEach((item) => {
    appendResultGridItem(grid, item.label, item.value, {
      className: item.className || "",
    });
  });
  container.appendChild(grid);

  if (detailsHint) {
    detailsHint.textContent = card.detailsHint || "";
  }
}

export function renderGmailReviewSummaryInto(nodes = {}, card = {}) {
  const { summary, summaryGrid, summaryDetails } = nodes;
  if (!summary || !summaryGrid) {
    return;
  }

  if (card.empty) {
    summary.className = "result-card empty-state";
    summary.textContent = card.emptyText || "";
    clearNode(summaryGrid);
    if (summaryDetails) {
      summaryDetails.open = false;
    }
    return;
  }

  summary.className = "result-card";
  clearNode(summary);
  const summaryCard = document.createElement("div");
  summaryCard.className = "gmail-review-summary-card";

  const copy = document.createElement("div");
  copy.className = "gmail-review-summary-copy";
  const subject = document.createElement("strong");
  subject.textContent = card.subject || "No subject";
  copy.appendChild(subject);
  const status = document.createElement("p");
  status.textContent = card.reviewStatus || "";
  copy.appendChild(status);
  summaryCard.appendChild(copy);

  const metrics = document.createElement("div");
  metrics.className = "gmail-review-summary-metrics";
  appendResultGridItem(metrics, "Workflow", card.workflowLabel || "");
  appendResultGridItem(metrics, "Supported attachments", card.attachmentCount || 0);
  summaryCard.appendChild(metrics);

  const chip = document.createElement("span");
  chip.className = `status-chip ${card.chipTone || "info"}`;
  chip.textContent = card.chipLabel || "Review ready";
  summaryCard.appendChild(chip);
  summary.appendChild(summaryCard);

  clearNode(summaryGrid);
  (Array.isArray(card.gridItems) ? card.gridItems : []).forEach((item) => {
    appendResultGridItem(summaryGrid, item.label, item.value, {
      className: item.className || "",
    });
  });
}

function appendGmailResultGrid(container, gridItems = []) {
  const normalizedItems = Array.isArray(gridItems) ? gridItems : [];
  if (!normalizedItems.length) {
    return null;
  }
  const grid = document.createElement("div");
  grid.className = "result-grid";
  normalizedItems.forEach((item) => {
    appendResultGridItem(grid, item.label, item.value, {
      className: item.className || "",
      titleValue: item.titleValue ?? null,
    });
  });
  container.appendChild(grid);
  return grid;
}

function renderGmailResultCardInto(container, card = {}) {
  if (!container) {
    return undefined;
  }

  if (card.empty) {
    container.className = card.className || "result-card empty-state";
    container.textContent = card.text || "";
    return container;
  }

  container.className = card.className || "result-card";
  clearNode(container);
  container.appendChild(createResultHeader({
    title: card.title || "",
    message: card.message || "",
    label: card.label || "",
    tone: card.tone || "info",
  }));
  appendGmailResultGrid(container, card.gridItems);
  return container;
}

export function renderGmailBatchFinalizeSurfaceInto(nodes = {}, card = {}) {
  const { status, summary, result, button } = nodes;
  if (!status || !summary || !result || !button) {
    return undefined;
  }

  const buttonState = card.button || {};
  button.textContent = buttonState.label || "";
  button.disabled = Boolean(buttonState.disabled);
  button.classList.toggle("hidden", Boolean(buttonState.hidden));

  status.textContent = card.statusText || "";
  renderGmailResultCardInto(summary, card.summary || {});
  renderGmailResultCardInto(result, card.result || {});
  return nodes;
}

export function renderGmailResumeCardInto(container, card = {}) {
  if (!container) {
    return undefined;
  }

  if (!card.visible) {
    container.classList.add("hidden");
    container.classList.add("empty-state");
    container.textContent = card.emptyText || "No Gmail step is waiting yet.";
    return container;
  }

  container.classList.remove("hidden");
  container.classList.remove("empty-state");
  clearNode(container);
  const header = createResultHeader({
    title: card.title || "Resume Current Step",
    message: card.message || "Continue the active Gmail step when you are ready.",
    label: card.label || "ready",
    tone: card.tone === "ok" ? "ok" : "info",
  });
  const copy = header.children?.[0] || null;
  if (copy) {
    (Array.isArray(card.extraMessages) ? card.extraMessages : []).forEach((message) => {
      if (String(message ?? "")) {
        copy.appendChild(createTextElement("p", message));
      }
    });
  }
  container.appendChild(header);
  appendGmailResultGrid(container, card.gridItems);
  return container;
}

export function renderGmailSessionResultInto(container, card = {}) {
  if (!container) {
    return undefined;
  }

  if (card.empty) {
    container.classList.add("empty-state");
    container.textContent = card.emptyText || "Continue Gmail from here when a translation or interpretation step is ready.";
    return container;
  }

  container.classList.remove("empty-state");
  clearNode(container);
  container.appendChild(createResultHeader({
    title: card.title || "",
    message: card.message || "",
    label: card.label || "prepared",
    tone: card.tone || "info",
  }));
  appendGmailResultGrid(container, card.gridItems);
  return container;
}

function createCell(className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  return cell;
}

function defaultFormatSizeLabel(value) {
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

function defaultAttachmentKindLabel(attachment) {
  const normalized = String(attachment?.mime_type || "").trim().toLowerCase();
  if (normalized === "application/pdf") {
    return "PDF";
  }
  if (normalized.startsWith("image/")) {
    return "Image";
  }
  return "Unknown";
}

function defaultStartPage(_attachment, state = {}) {
  const parsed = Number.parseInt(String(state.startPage ?? "1").trim(), 10);
  let value = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  const pageCount = Number(state.pageCount || 0);
  if (pageCount > 0) {
    value = Math.min(value, pageCount);
  }
  return Math.max(1, value);
}

export function renderGmailAttachmentListInto(
  container,
  attachments = [],
  {
    startHeading = null,
    interpretationWorkflow = false,
    focusedAttachmentId = "",
    resolveState = () => ({ selected: false, startPage: 1, pageCount: 0 }),
    resolveCanEditStart = () => false,
    resolveKindLabel = defaultAttachmentKindLabel,
    resolveStartPage = defaultStartPage,
    formatSizeLabel = defaultFormatSizeLabel,
  } = {},
) {
  if (!container) {
    return undefined;
  }
  const normalizedAttachments = Array.isArray(attachments) ? attachments : [];
  clearNode(container);
  if (startHeading) {
    startHeading.textContent = "Start page";
  }
  if (!normalizedAttachments.length) {
    const row = document.createElement("tr");
    const cell = createCell("empty-state");
    cell.colSpan = 5;
    cell.textContent = "No supported PDF or image attachments were found in this message.";
    row.appendChild(cell);
    container.appendChild(row);
    return container;
  }
  const selectedInputType = interpretationWorkflow ? "radio" : "checkbox";
  for (const attachment of normalizedAttachments) {
    const attachmentId = attachment?.attachment_id || "";
    const state = resolveState(attachmentId) || {};
    const selected = state.selected === true;
    const focused = focusedAttachmentId === attachmentId;
    const canEditStart = resolveCanEditStart(attachment) === true;
    const row = document.createElement("tr");
    row.className = [
      "gmail-review-row",
      selected ? "is-selected" : "",
      focused ? "is-focused" : "",
    ].filter(Boolean).join(" ");
    row.dataset.attachmentRow = attachmentId;
    row.tabIndex = 0;

    const selectCell = createCell();
    const label = document.createElement("label");
    label.className = "checkbox-inline gmail-review-select";
    const input = document.createElement("input");
    input.type = selectedInputType;
    input.name = "gmail-review-selection";
    input.dataset.attachmentCheckbox = attachmentId;
    input.checked = selected;
    label.appendChild(input);
    label.appendChild(createTextElement("span", selected ? "Selected" : "Choose", "gmail-review-row-label"));
    selectCell.appendChild(label);

    const fileCell = createCell("gmail-review-file-cell");
    const filename = createTextElement("strong", attachment?.filename || "Attachment", "gmail-review-file-name");
    setNodeTitle(filename, attachment?.filename || "Attachment");
    fileCell.appendChild(filename);

    const mimeCell = createCell();
    setNodeTitle(mimeCell, attachment?.mime_type || "Unknown");
    mimeCell.textContent = resolveKindLabel(attachment);

    const sizeCell = createCell();
    sizeCell.textContent = formatSizeLabel(attachment?.size_bytes || 0);

    const startCell = createCell();
    if (canEditStart) {
      const startInput = document.createElement("input");
      startInput.type = "number";
      startInput.className = "attachment-start-page";
      startInput.min = "1";
      startInput.step = "1";
      startInput.value = String(resolveStartPage(attachment, state));
      startInput.dataset.attachmentStartPage = attachmentId;
      startCell.appendChild(startInput);
    } else {
      startCell.appendChild(createTextElement("span", "1", "gmail-review-start-static"));
    }

    row.appendChild(selectCell);
    row.appendChild(fileCell);
    row.appendChild(mimeCell);
    row.appendChild(sizeCell);
    row.appendChild(startCell);
    container.appendChild(row);
  }
  return container;
}

export function renderGmailReviewDetailInto(
  container,
  attachment,
  {
    state = {},
    canEditStart = false,
    previewLoaded = false,
    runtimeGuard = { blocked: false },
    kindLabel = "",
    startPage = defaultStartPage(attachment, state),
  } = {},
) {
  if (!container) {
    return undefined;
  }
  if (!attachment) {
    container.className = "result-card empty-state";
    clearNode(container);
    setText(container, "Choose an attachment row to see the document details, optional preview, and start page.");
    return container;
  }
  const pageCountText = state.pageCount > 0
    ? `${state.pageCount} ${state.pageCount === 1 ? "page" : "pages"}`
    : "Page count appears after preview";
  const selectedStateText = state.selected ? "Selected" : "Not selected";
  container.className = "result-card";
  clearNode(container);
  const strip = document.createElement("div");
  strip.className = "gmail-review-detail-strip";
  const primary = document.createElement("div");
  primary.className = "gmail-review-detail-primary";
  const title = createTextElement("strong", attachment.filename || "Attachment", "word-break");
  setNodeTitle(title, attachment.filename || "Attachment");
  primary.appendChild(title);
  primary.appendChild(createTextElement(
    "p",
    `${kindLabel} · ${selectedStateText} · ${pageCountText}${previewLoaded ? " · Preview ready" : ""}`,
    "gmail-review-detail-meta",
  ));
  primary.appendChild(createTextElement(
    "p",
    "Preview is optional. Use it if you want to check the document or choose a later start page.",
    "field-hint",
  ));
  strip.appendChild(primary);
  const actions = document.createElement("div");
  actions.className = "gmail-review-detail-actions";
  if (canEditStart) {
    const field = document.createElement("div");
    field.className = "field gmail-review-start-field";
    const label = createTextElement("label", "Start page");
    label.htmlFor = "gmail-review-detail-start";
    const input = document.createElement("input");
    input.id = "gmail-review-detail-start";
    input.type = "number";
    input.min = "1";
    input.step = "1";
    input.value = String(startPage);
    input.dataset.detailStartPage = attachment.attachment_id || "";
    field.appendChild(label);
    field.appendChild(input);
    actions.appendChild(field);
  }
  const previewButton = document.createElement("button");
  previewButton.type = "button";
  previewButton.className = "ghost-button";
  previewButton.id = "gmail-preview-selected";
  previewButton.dataset.previewSelected = attachment.attachment_id || "";
  previewButton.disabled = runtimeGuard.blocked === true;
  previewButton.textContent = "Preview";
  actions.appendChild(previewButton);
  strip.appendChild(actions);
  container.appendChild(strip);
  return container;
}

function resetGmailPreviewControls(nodes) {
  const {
    openTab,
    applyButton,
    prevButton,
    nextButton,
    pageInput,
  } = nodes;
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
}

function gmailPreviewResult(shouldRenderPdfCanvas) {
  return { shouldRenderPdfCanvas: Boolean(shouldRenderPdfCanvas) };
}

function renderGmailPreviewSummary(summary, attachment, { page, pageCount, canApply }) {
  summary.className = "result-card";
  clearNode(summary);
  summary.appendChild(createResultHeader({
    title: attachment.filename || "Attachment preview",
    message: pageCount > 0 ? `${pageCount} page(s) available` : "Preview ready",
    label: canApply ? `Page ${page}` : "Inspect only",
    tone: canApply ? "info" : "ok",
  }));
}

function renderGmailPdfPreview(nodes, attachment, preview) {
  const {
    container,
    status,
    applyButton,
    prevButton,
    nextButton,
    pageInput,
  } = nodes;
  const page = Number(preview.page) || 1;
  const pageCount = Number(preview.pageCount) || 0;
  const canApply = Boolean(preview.canApply);

  pageInput.disabled = false;
  prevButton.disabled = page <= 1;
  nextButton.disabled = pageCount > 0 ? page >= pageCount : false;
  pageInput.max = String(Math.max(1, pageCount || page));
  pageInput.value = String(page);
  applyButton.disabled = !canApply;
  applyButton.textContent = canApply ? applyButton.dataset.defaultLabel : "Preview only";

  container.className = "gmail-inline-preview";
  clearNode(container);
  const shell = document.createElement("div");
  shell.className = "gmail-inline-preview-canvas-shell";
  const canvas = document.createElement("canvas");
  canvas.id = "gmail-preview-canvas";
  canvas.className = "gmail-inline-preview-canvas";
  canvas.setAttribute("aria-label", `Preview for ${attachment.filename || "attachment"}`);
  shell.appendChild(canvas);
  container.appendChild(shell);

  status.textContent = canApply
    ? (pageCount > 0
      ? `Previewing page ${page} of ${pageCount}. Use current page if you want the translation to start later in the document.`
      : `Previewing page ${page}. Use current page if you want the translation to start later in the document.`)
    : (pageCount > 0
      ? `Previewing page ${page} of ${pageCount}. This workflow still continues from page 1.`
      : `Previewing page ${page}. This workflow still continues from page 1.`);
}

function renderGmailImagePreview(nodes, attachment, preview) {
  const {
    container,
    status,
    applyButton,
  } = nodes;
  applyButton.disabled = true;
  applyButton.textContent = "Preview only";
  container.className = "gmail-inline-preview";
  clearNode(container);
  const shell = document.createElement("div");
  shell.className = "gmail-inline-preview-image-shell";
  const image = document.createElement("img");
  image.className = "gmail-inline-preview-image";
  image.src = preview.href || "";
  image.alt = attachment.filename || "Attachment preview";
  shell.appendChild(image);
  container.appendChild(shell);
  status.textContent = "Image preview is shown inline. Start page stays fixed at 1 for this attachment.";
}

function renderGmailFallbackPreview(nodes, attachment) {
  const {
    container,
    status,
    applyButton,
  } = nodes;
  applyButton.disabled = true;
  applyButton.textContent = "Preview only";
  container.className = "gmail-inline-preview empty-state";
  clearNode(container);
  container.appendChild(createTextElement("span", "Open "));
  container.appendChild(createTextElement("strong", attachment.filename || "the preview"));
  container.appendChild(createTextElement("span", " in a new tab for a full attachment view."));
  status.textContent = "This attachment type is available through the new-tab fallback.";
}

export function renderGmailPreviewPanelInto(nodes = {}, preview = {}) {
  const {
    container,
    summary,
    status,
    openTab,
    applyButton,
    prevButton,
    nextButton,
    pageInput,
  } = nodes;
  if (!container || !summary || !status || !openTab || !applyButton || !prevButton || !nextButton || !pageInput) {
    return undefined;
  }

  resetGmailPreviewControls({
    openTab,
    applyButton,
    prevButton,
    nextButton,
    pageInput,
  });

  const attachment = preview.attachment || null;
  if (!attachment || !preview.href) {
    summary.className = "result-card empty-state";
    summary.textContent = "Preview is optional. Open it when you want to check the document more closely.";
    container.className = "gmail-inline-preview empty-state";
    container.textContent = "Preview opens here when requested.";
    status.textContent = "Preview is optional. Use it if you want to check the document or choose a later start page.";
    return gmailPreviewResult(false);
  }

  const page = Number(preview.page) || 1;
  const pageCount = Number(preview.pageCount) || 0;
  const canApply = Boolean(preview.canApply);
  renderGmailPreviewSummary(summary, attachment, { page, pageCount, canApply });
  openTab.classList.remove("hidden");
  openTab.href = preview.href;

  if (preview.isPdf) {
    renderGmailPdfPreview(nodes, attachment, { ...preview, page, pageCount, canApply });
    return gmailPreviewResult(true);
  }

  if (preview.isImage) {
    renderGmailImagePreview(nodes, attachment, preview);
    return gmailPreviewResult(false);
  }

  renderGmailFallbackPreview(nodes, attachment);
  return gmailPreviewResult(false);
}

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
