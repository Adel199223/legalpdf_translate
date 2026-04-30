import { clearNode, createEmptyState, createTextElement } from "./safe_rendering.js";

export function renderExtensionPrepareReasonCatalogInto(container, items = []) {
  if (!container) {
    return;
  }
  clearNode(container);
  if (!items.length) {
    container.appendChild(createEmptyState("No prepare reasons are available."));
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "history-item";
    const body = document.createElement("div");
    body.appendChild(createTextElement("strong", item?.message || "No message available."));
    body.appendChild(createTextElement("p", `Code: ${item?.reason || "Unknown reason"}`));
    card.appendChild(body);
    container.appendChild(card);
  }
}
