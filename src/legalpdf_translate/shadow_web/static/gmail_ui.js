import { clearNode } from "./safe_rendering.js";
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
