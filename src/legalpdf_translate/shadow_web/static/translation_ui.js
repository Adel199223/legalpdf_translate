import { setText } from "./safe_rendering.js";

export function renderTranslationOutputSummaryInto(nodes = {}, summary = {}) {
  const { label, copy, path } = nodes || {};
  if (!label || !copy || !path) {
    return undefined;
  }

  setText(label, summary.label || "");
  setText(copy, summary.copy || "");
  setText(path, summary.path || "");
  return label;
}

export function renderTranslationRunStatusInto(nodes = {}, view = {}) {
  const {
    percent,
    chip,
    track,
    bar,
    task,
    pages,
    currentPage,
    imageRetry,
    alerts,
  } = nodes || {};
  if (!percent || !chip || !track || !bar || !task || !pages || !currentPage || !imageRetry || !alerts) {
    return undefined;
  }

  setText(percent, view.percentText || "");
  setText(chip, view.chipText || "");
  chip.className = `status-chip ${view.chipTone || ""}`;
  track.setAttribute("aria-valuenow", String(view.percentValue));
  bar.style.width = `${view.percentValue}%`;
  setText(task, view.currentTask || "");
  setText(pages, view.pagesText || "");
  setText(currentPage, view.currentPageText || "");
  setText(imageRetry, view.imageRetryText || "");
  setText(alerts, view.alertsText || "");
  return percent;
}

export function renderTranslationPrimaryActionsInto(nodes = {}, actionState = {}) {
  const {
    helper,
    startButton,
    analyzeButton,
    cancelButton,
    resumeButton,
    rebuildButton,
  } = nodes || {};

  if (helper) {
    setText(helper, actionState.helperText || "");
  }
  if (startButton) {
    startButton.disabled = !actionState.startEnabled;
  }
  if (analyzeButton) {
    analyzeButton.disabled = !actionState.analyzeEnabled;
  }
  if (cancelButton) {
    cancelButton.disabled = !actionState.cancelEnabled;
  }
  if (resumeButton) {
    resumeButton.disabled = !actionState.resumeEnabled;
  }
  if (rebuildButton) {
    rebuildButton.disabled = !actionState.rebuildEnabled;
  }
  return helper || undefined;
}

export function renderTranslationNumericMismatchWarningInto(container, warning = {}) {
  if (!container) {
    return undefined;
  }

  const visible = Boolean(warning?.visible);
  container.classList.toggle("hidden", !visible);
  if (!visible) {
    setText(container, "");
    return container;
  }

  const lines = Array.isArray(warning.lines) ? warning.lines : [];
  const detailLines = lines.length ? `\n${lines.join("\n")}` : "";
  setText(container, `${warning.message || ""}${detailLines}`);
  container.setAttribute("role", "note");
  return container;
}

export function renderTranslationDownloadLinkInto(node, href = "") {
  if (!node) {
    return undefined;
  }

  if (href) {
    node.href = href;
    node.classList.remove("hidden");
  } else {
    node.classList.add("hidden");
    node.removeAttribute("href");
  }
  return node;
}

export function syncTranslationCompletionDrawerStateInto(nodes = {}, open = false) {
  const { backdrop, body } = nodes || {};
  if (!backdrop) {
    return undefined;
  }

  const isOpen = Boolean(open);
  backdrop.classList.toggle("hidden", !isOpen);
  backdrop.setAttribute("aria-hidden", isOpen ? "false" : "true");
  if (body?.dataset) {
    body.dataset.translationCompletionDrawer = isOpen ? "open" : "closed";
  }
  return backdrop;
}

export function renderTranslationCompletionSurfaceInto(nodes = {}, surface = {}) {
  const {
    openButton,
    formShell,
    emptyShell,
    status,
    emptyTitle,
    emptyCopy,
    saveTitle,
    saveStatus,
    saveButton,
  } = nodes || {};

  const available = Boolean(surface.available);
  const hasSaveSurface = Boolean(surface.hasSaveSurface);

  if (openButton) {
    openButton.classList.toggle("hidden", !available);
    setText(openButton, surface.openButtonLabel || "");
  }
  if (emptyTitle) {
    setText(emptyTitle, surface.emptyTitle || "");
  }
  if (emptyCopy) {
    setText(emptyCopy, surface.emptyCopy || "");
  }
  if (saveTitle) {
    setText(saveTitle, surface.saveTitle || "");
  }
  if (saveStatus) {
    setText(saveStatus, surface.saveStatus || "");
  }
  if (status) {
    setText(status, surface.drawerStatus || "");
  }

  if (!available) {
    formShell?.classList.add("hidden");
    emptyShell?.classList.add("hidden");
    return openButton || status || undefined;
  }

  formShell?.classList.toggle("hidden", !hasSaveSurface);
  emptyShell?.classList.toggle("hidden", hasSaveSurface);
  if (saveButton) {
    setText(saveButton, surface.saveButtonLabel || "");
    saveButton.disabled = Boolean(surface.saveDisabled);
  }
  return openButton || status || undefined;
}
