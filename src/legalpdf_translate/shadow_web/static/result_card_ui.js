import {
  appendMultilineText,
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
