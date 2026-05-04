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
