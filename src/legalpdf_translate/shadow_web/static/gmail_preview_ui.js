import { clearNode, createTextElement } from "./safe_rendering.js";
import { createResultHeader } from "./result_card_ui.js";

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

function renderGmailPreviewSummary(summary, previewSummary = {}) {
  if (previewSummary.kind !== "card") {
    summary.className = previewSummary.className || "result-card empty-state";
    summary.textContent = previewSummary.text || "";
    return;
  }
  summary.className = "result-card";
  clearNode(summary);
  summary.appendChild(createResultHeader({
    title: previewSummary.title || "Attachment preview",
    message: previewSummary.message || "",
    label: previewSummary.label || "",
    tone: previewSummary.tone || "ok",
  }));
}

function applyGmailPreviewControls(nodes, preview = {}) {
  const {
    openTab,
    applyButton,
    prevButton,
    nextButton,
    pageInput,
  } = nodes;
  const controls = preview.controls || {};
  const openTabPresentation = preview.openTab || {};

  openTab.classList.toggle("hidden", !openTabPresentation.visible);
  openTab.href = openTabPresentation.visible ? (openTabPresentation.href || "#") : "#";
  applyButton.disabled = controls.applyDisabled !== false;
  applyButton.textContent = controls.applyLabel || applyButton.dataset.defaultLabel;
  pageInput.disabled = controls.pageDisabled !== false;
  prevButton.disabled = controls.prevDisabled !== false;
  nextButton.disabled = controls.nextDisabled !== false;
  pageInput.min = controls.pageMin || "1";
  pageInput.max = controls.pageMax || "1";
  pageInput.value = controls.pageValue || "1";
}

function renderGmailPdfPreview(nodes, body = {}) {
  const { container } = nodes;

  container.className = body.className || "gmail-inline-preview";
  clearNode(container);
  const shell = document.createElement("div");
  shell.className = body.shellClassName || "gmail-inline-preview-canvas-shell";
  const canvas = document.createElement("canvas");
  canvas.id = body.canvasId || "gmail-preview-canvas";
  canvas.className = body.canvasClassName || "gmail-inline-preview-canvas";
  canvas.setAttribute("aria-label", body.canvasAriaLabel || "Preview for attachment");
  shell.appendChild(canvas);
  container.appendChild(shell);
}

function renderGmailImagePreview(nodes, body = {}) {
  const { container } = nodes;
  container.className = body.className || "gmail-inline-preview";
  clearNode(container);
  const shell = document.createElement("div");
  shell.className = body.shellClassName || "gmail-inline-preview-image-shell";
  const image = document.createElement("img");
  image.className = body.imageClassName || "gmail-inline-preview-image";
  image.src = body.src || "";
  image.alt = body.alt || "Attachment preview";
  shell.appendChild(image);
  container.appendChild(shell);
}

function renderGmailFallbackPreview(nodes, body = {}) {
  const { container } = nodes;
  container.className = body.className || "gmail-inline-preview empty-state";
  clearNode(container);
  container.appendChild(createTextElement("span", body.leadingText || ""));
  container.appendChild(createTextElement("strong", body.strongText || ""));
  container.appendChild(createTextElement("span", body.trailingText || ""));
}

function renderGmailEmptyPreview(nodes, body = {}) {
  const { container } = nodes;
  container.className = body.className || "gmail-inline-preview empty-state";
  container.textContent = body.text || "";
}

export function renderGmailPreviewPanelInto(nodes = {}, presentation = {}) {
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

  renderGmailPreviewSummary(summary, presentation.summary || {});
  applyGmailPreviewControls(nodes, presentation);
  status.textContent = presentation.statusText || "";

  const body = presentation.body || {};
  if (body.kind === "pdf") {
    renderGmailPdfPreview(nodes, body);
  } else if (body.kind === "image") {
    renderGmailImagePreview(nodes, body);
  } else if (body.kind === "fallback") {
    renderGmailFallbackPreview(nodes, body);
  } else {
    renderGmailEmptyPreview(nodes, body);
  }

  return gmailPreviewResult(presentation.shouldRenderPdfCanvas);
}

export function renderGmailPdfPreviewFallbackInto(nodes = {}, fallback = {}) {
  const { container, status } = nodes || {};
  if (!container || !status) {
    return undefined;
  }

  container.className = fallback.className || "gmail-inline-preview empty-state";
  container.textContent = fallback.containerMessage || "";
  status.textContent = fallback.statusMessage || "";
  return nodes;
}
