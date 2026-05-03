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
