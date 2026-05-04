import {
  appendMultilineText,
  clearNode,
  createTextElement,
  setNodeTitle,
  setText,
} from "./safe_rendering.js";

export function createStatusChip(label, toneClass) {
  return createTextElement("span", label, `status-chip ${toneClass}`);
}

export function createResultHeader({ title = "", message = "", label = "", tone = "info" }) {
  const header = document.createElement("div");
  header.className = "result-header";
  const copy = document.createElement("div");
  copy.appendChild(createTextElement("strong", title));
  if (String(message ?? "")) {
    copy.appendChild(createTextElement("p", message));
  }
  header.appendChild(copy);
  header.appendChild(createStatusChip(label, tone));
  return header;
}

export function appendResultGridItem(container, title, value, { className = "", multiline = false, titleValue = null } = {}) {
  const item = document.createElement("div");
  item.appendChild(createTextElement("h3", title));
  const paragraph = document.createElement("p");
  if (className) {
    paragraph.className = className;
  }
  if (titleValue !== null && titleValue !== undefined) {
    setNodeTitle(paragraph, titleValue);
  }
  if (multiline) {
    appendMultilineText(paragraph, value);
  } else {
    setText(paragraph, value);
  }
  item.appendChild(paragraph);
  container.appendChild(item);
  return item;
}

export function renderResultHeaderCardInto(container, card = {}) {
  if (!container) {
    return undefined;
  }

  if (!card.available) {
    container.classList.add("empty-state");
    container.textContent = card.emptyText || "";
    return container;
  }

  container.classList.remove("empty-state");
  clearNode(container);

  const header = document.createElement("div");
  header.className = "result-header";
  const copy = document.createElement("div");
  copy.appendChild(createTextElement("strong", card.title || ""));

  const message = createTextElement("p", card.message || "");
  const detailLines = (Array.isArray(card.detailLines) ? card.detailLines : []).filter(Boolean);
  if (detailLines.length) {
    message.appendChild(document.createElement("br"));
    message.appendChild(document.createElement("br"));
    appendMultilineText(message, detailLines.join("\n"));
  }
  copy.appendChild(message);

  header.appendChild(copy);
  header.appendChild(createStatusChip(card.label || "", card.tone || "info"));
  container.appendChild(header);
  return container;
}

export function renderTranslationResultCardInto(container, card = {}) {
  if (!container) {
    return undefined;
  }

  if (card.empty) {
    container.classList.add("empty-state");
    container.textContent = card.emptyText || "";
    return container;
  }

  container.classList.remove("empty-state");
  clearNode(container);

  const header = document.createElement("div");
  header.className = "result-header";

  const copy = document.createElement("div");
  copy.appendChild(createTextElement("strong", card.title || ""));

  const summary = document.createElement("p");
  const summaryLines = (Array.isArray(card.summaryLines) ? card.summaryLines : []).map((line) => String(line ?? ""));
  appendMultilineText(summary, summaryLines.join("\n"));
  copy.appendChild(summary);

  const footer = String(card.footer || "");
  if (footer) {
    copy.appendChild(createTextElement("p", footer));
  }

  header.appendChild(copy);
  header.appendChild(createStatusChip(card.label || "", card.tone || "info"));
  container.appendChild(header);
  return container;
}
