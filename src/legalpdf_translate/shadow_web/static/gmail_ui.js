import { clearNode, createTextElement } from "./safe_rendering.js";
import { appendResultGridItem, createResultHeader } from "./result_card_ui.js";

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
