import { clearNode } from "./safe_rendering.js";
import { appendResultGridItem, createResultHeader } from "./result_card_ui.js";

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
