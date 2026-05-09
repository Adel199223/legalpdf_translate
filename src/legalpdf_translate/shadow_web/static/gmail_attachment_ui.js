import {
  clearNode,
  createTextElement,
  setNodeTitle,
  setText,
} from "./safe_rendering.js";

function createCell(className = "") {
  const cell = document.createElement("td");
  if (className) {
    cell.className = className;
  }
  return cell;
}

function applyDataset(element, dataset = {}) {
  Object.entries(dataset || {}).forEach(([key, value]) => {
    element.dataset[key] = String(value ?? "");
  });
}

function safeTextTagName(value, fallback) {
  const tagName = String(value || "").trim().toLowerCase();
  return ["strong", "p", "span", "label"].includes(tagName) ? tagName : fallback;
}

export function renderGmailAttachmentListInto(
  container,
  presentation = {},
  { startHeading = null } = {},
) {
  if (!container) {
    return undefined;
  }
  clearNode(container);
  if (startHeading) {
    startHeading.textContent = presentation.startHeadingLabel || "";
  }
  const rows = Array.isArray(presentation.rows) ? presentation.rows : [];
  if (!rows.length) {
    const empty = presentation.empty || {};
    const row = document.createElement("tr");
    const cell = createCell(empty.className || "");
    cell.colSpan = Number(empty.colSpan || 1);
    cell.textContent = empty.text || "";
    row.appendChild(cell);
    container.appendChild(row);
    return container;
  }
  for (const rowPresentation of rows) {
    const row = document.createElement("tr");
    row.className = rowPresentation.rowClassName || "";
    row.dataset.attachmentRow = rowPresentation.attachmentId || "";
    row.tabIndex = Number(rowPresentation.tabIndex ?? 0);

    const select = rowPresentation.select || {};
    const selectCell = createCell(select.cellClassName || "");
    const label = document.createElement("label");
    label.className = select.labelClassName || "";
    const input = document.createElement("input");
    input.type = select.inputType || "";
    input.name = select.inputName || "";
    applyDataset(input, select.inputDataset);
    input.checked = select.checked === true;
    label.appendChild(input);
    label.appendChild(createTextElement("span", select.text || "", select.textClassName || ""));
    selectCell.appendChild(label);

    const file = rowPresentation.file || {};
    const fileCell = createCell(file.cellClassName || "");
    const filename = createTextElement("strong", file.text || "", file.className || "");
    setNodeTitle(filename, file.title || "");
    fileCell.appendChild(filename);

    const kind = rowPresentation.kind || {};
    const mimeCell = createCell(kind.cellClassName || "");
    setNodeTitle(mimeCell, kind.title || "");
    mimeCell.textContent = kind.text || "";

    const size = rowPresentation.size || {};
    const sizeCell = createCell(size.cellClassName || "");
    sizeCell.textContent = size.text || "";

    const start = rowPresentation.start || {};
    const startCell = createCell(start.cellClassName || "");
    if (start.kind === "input") {
      const startInput = document.createElement("input");
      startInput.type = start.inputType || "";
      startInput.className = start.className || "";
      startInput.min = start.min || "";
      startInput.step = start.step || "";
      startInput.value = start.value || "";
      applyDataset(startInput, start.dataset);
      startCell.appendChild(startInput);
    } else {
      startCell.appendChild(createTextElement("span", start.text || "", start.className || ""));
    }

    row.appendChild(selectCell);
    row.appendChild(fileCell);
    row.appendChild(mimeCell);
    row.appendChild(sizeCell);
    row.appendChild(startCell);
    container.appendChild(row);
  }
  return container;
}

export function renderGmailReviewDetailInto(
  container,
  presentation = {},
) {
  if (!container) {
    return undefined;
  }
  container.className = presentation.className || "";
  clearNode(container);
  if (presentation.emptyText) {
    setText(container, presentation.emptyText);
    return container;
  }
  const strip = document.createElement("div");
  strip.className = presentation.stripClassName || "";
  const primary = document.createElement("div");
  primary.className = presentation.primaryClassName || "";
  const titlePresentation = presentation.title || {};
  const title = createTextElement(
    safeTextTagName(titlePresentation.tagName, "strong"),
    titlePresentation.text || "",
    titlePresentation.className || "",
  );
  setNodeTitle(title, titlePresentation.title || "");
  primary.appendChild(title);
  const meta = presentation.meta || {};
  primary.appendChild(createTextElement(
    safeTextTagName(meta.tagName, "p"),
    meta.text || "",
    meta.className || "",
  ));
  const hint = presentation.hint || {};
  primary.appendChild(createTextElement(
    safeTextTagName(hint.tagName, "p"),
    hint.text || "",
    hint.className || "",
  ));
  strip.appendChild(primary);
  const actions = document.createElement("div");
  actions.className = presentation.actionsClassName || "";
  const startField = presentation.startField || null;
  if (startField) {
    const field = document.createElement("div");
    field.className = startField.className || "";
    const labelPresentation = startField.label || {};
    const label = createTextElement(
      safeTextTagName(labelPresentation.tagName, "label"),
      labelPresentation.text || "",
    );
    label.htmlFor = labelPresentation.htmlFor || "";
    const inputPresentation = startField.input || {};
    const input = document.createElement("input");
    input.id = inputPresentation.id || "";
    input.type = inputPresentation.type || "";
    input.min = inputPresentation.min || "";
    input.step = inputPresentation.step || "";
    input.value = inputPresentation.value || "";
    applyDataset(input, inputPresentation.dataset);
    field.appendChild(label);
    field.appendChild(input);
    actions.appendChild(field);
  }
  const previewButtonPresentation = presentation.previewButton || {};
  const previewButton = document.createElement("button");
  previewButton.type = previewButtonPresentation.type || "";
  previewButton.className = previewButtonPresentation.className || "";
  previewButton.id = previewButtonPresentation.id || "";
  applyDataset(previewButton, previewButtonPresentation.dataset);
  previewButton.disabled = previewButtonPresentation.disabled === true;
  previewButton.textContent = previewButtonPresentation.text || "";
  actions.appendChild(previewButton);
  strip.appendChild(actions);
  container.appendChild(strip);
  return container;
}
