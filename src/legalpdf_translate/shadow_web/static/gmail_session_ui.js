import { clearNode, createTextElement } from "./safe_rendering.js";
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
