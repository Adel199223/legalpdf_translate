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
