import {
  appendMultilineText,
  clearNode,
  createTextElement,
} from "./safe_rendering.js";

function chipToneClass(status) {
  if (status === "ok") {
    return "ok";
  }
  if (status === "bad") {
    return "bad";
  }
  if (status === "info") {
    return "info";
  }
  return "warn";
}

function createStatusChip(label, toneClass) {
  return createTextElement("span", label, `status-chip ${toneClass}`);
}

export function renderDashboardCardsInto(container, cards = []) {
  if (!container) {
    return;
  }
  clearNode(container);
  for (const card of cards) {
    const article = document.createElement("article");
    article.className = "launch-card";
    article.classList.add(card.status === "ready" ? "ready" : "planned");
    const chipTone = card.status === "ready" ? "ok" : "warn";
    const chipText = card.status === "ready" ? "Ready" : String(card.status || "").replaceAll("_", " ");
    article.appendChild(createTextElement("h3", card.title));
    article.appendChild(createTextElement("p", card.description));
    article.appendChild(createStatusChip(chipText, chipTone));
    container.appendChild(article);
  }
}

export function renderSummaryGridInto(container, items = []) {
  if (!container) {
    return;
  }
  clearNode(container);
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "summary-card";
    card.appendChild(createTextElement("h3", item.label));
    card.appendChild(createTextElement("p", item.value, "word-break"));
    container.appendChild(card);
  }
}

export function renderCapabilityCardsInto(container, cards = []) {
  if (!container) {
    return;
  }
  clearNode(container);
  for (const card of cards) {
    const article = document.createElement("article");
    article.className = "status-card";
    article.appendChild(createTextElement("h3", card.title));
    const paragraph = document.createElement("p");
    appendMultilineText(paragraph, card.text);
    article.appendChild(paragraph);
    article.appendChild(createStatusChip(card.label, chipToneClass(card.status)));
    container.appendChild(article);
  }
}
