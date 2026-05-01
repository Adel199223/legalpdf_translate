import {
  appendMultilineText,
  clearNode,
  createTextElement,
} from "./safe_rendering.js";
import { createResultHeader } from "./result_card_ui.js";

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

function parityChecklistCard(item) {
  const status = String(item?.status || "");
  return {
    title: item?.title,
    text: item?.description,
    status: status === "ready" ? "ok" : status === "blocked" ? "bad" : "warn",
    label: status === "ready" ? "Ready" : status.replaceAll("_", " "),
  };
}

function appendListItems(list, items = [], emptyText) {
  if (items.length) {
    items.forEach((item) => list.appendChild(createTextElement("li", item)));
    return;
  }
  list.appendChild(createTextElement("li", emptyText));
}

export function renderParityAuditInto({
  statusNode = null,
  gridContainer = null,
  resultContainer = null,
  audit = {},
  presentation = {},
} = {}) {
  const checklist = audit.checklist || [];
  const cards = checklist.map((item) => parityChecklistCard(item));
  if (statusNode) {
    statusNode.textContent = presentation.parityStatus;
  }
  renderCapabilityCardsInto(gridContainer, cards);
  if (!resultContainer) {
    return;
  }
  const recommendation = audit.promotion_recommendation || {};
  const recommendationReady = recommendation.status === "ready_for_daily_use";
  resultContainer.classList.remove("empty-state");
  clearNode(resultContainer);
  resultContainer.appendChild(createResultHeader({
    title: recommendation.headline || "Promotion recommendation unavailable.",
    message: presentation.readyCountLine,
    label: presentation.resultChipLabel,
    tone: recommendationReady ? "ok" : "warn",
  }));
  const grid = document.createElement("div");
  grid.className = "result-grid";
  const nextBox = document.createElement("div");
  nextBox.appendChild(createTextElement("h3", presentation.resultNextTitle));
  const workflowList = document.createElement("ul");
  appendListItems(
    workflowList,
    recommendation.recommended_workflows || [],
    "No recommendation items available.",
  );
  nextBox.appendChild(workflowList);
  const limitsBox = document.createElement("div");
  limitsBox.appendChild(createTextElement("h3", presentation.resultLimitsTitle));
  const remainingList = document.createElement("ul");
  appendListItems(remainingList, audit.remaining_limitations || [], "No limitations recorded.");
  limitsBox.appendChild(remainingList);
  grid.appendChild(nextBox);
  grid.appendChild(limitsBox);
  resultContainer.appendChild(grid);
}
