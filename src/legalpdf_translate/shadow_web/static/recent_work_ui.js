import { deriveRecentWorkPresentation } from "./translation.js";
import { clearNode, createEmptyState, createTextElement, setText } from "./safe_rendering.js";

function appendHistoryMetaBits(container, bits) {
  const meta = document.createElement("div");
  meta.className = "history-meta";
  for (const bit of bits.filter(Boolean)) {
    meta.appendChild(createTextElement("small", bit));
  }
  container.appendChild(meta);
  return meta;
}

export function renderRecentJobsInto(
  container,
  items,
  historyById,
  translationHistoryById,
  { onOpenInterpretation, onOpenTranslation, onDelete } = {},
) {
  if (!container) {
    return;
  }
  clearNode(container);
  if (!items.length) {
    container.appendChild(createEmptyState(deriveRecentWorkPresentation().recentCasesEmpty));
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "history-item";
    const details = document.createElement("div");
    const interpretationItem = item.job_type === "Interpretation" ? historyById.get(Number(item.id)) : null;
    const translationItem = item.job_type !== "Interpretation" ? translationHistoryById.get(Number(item.id)) : null;
    const presentation = deriveRecentWorkPresentation({
      recentItemCount: items.length,
      recordAvailable: Boolean(interpretationItem || translationItem),
      jobType: item.job_type,
    });
    const summaryBits = [item.case_entity, item.case_city, item.service_date || item.completed_at].filter(Boolean);
    const chipBits = [presentation.typeLabel];
    if (item.target_lang) {
      chipBits.push(item.target_lang);
    }
    if (item.service_date || item.completed_at) {
      chipBits.push(item.service_date || item.completed_at);
    }
    details.appendChild(createTextElement("strong", item.case_number || "Saved case record"));
    details.appendChild(createTextElement("p", summaryBits.join(" | ") || "Saved case record"));
    appendHistoryMetaBits(details, chipBits);
    card.appendChild(details);
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const loadButton = document.createElement("button");
    loadButton.type = "button";
    loadButton.textContent = presentation.recentOpenLabel;
    loadButton.disabled = !(interpretationItem || translationItem);
    if (interpretationItem) {
      loadButton.addEventListener("click", () => onOpenInterpretation?.(interpretationItem));
    } else if (translationItem) {
      loadButton.addEventListener("click", () => onOpenTranslation?.(translationItem));
    }
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = presentation.recentDeleteLabel;
    deleteButton.addEventListener("click", () => onDelete?.(item));
    actions.appendChild(loadButton);
    actions.appendChild(deleteButton);
    card.appendChild(actions);
    container.appendChild(card);
  }
}

export function renderInterpretationHistoryHeadingInto(node, text = "Saved Interpretation Requests") {
  setText(node, text);
}

export function renderInterpretationHistoryInto(container, items, { onOpen, onDelete } = {}) {
  if (!container) {
    return;
  }
  clearNode(container);
  const presentation = deriveRecentWorkPresentation({ jobType: "Interpretation" });
  if (!items.length) {
    container.appendChild(createEmptyState(presentation.interpretationHistoryEmpty));
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "history-item";
    const left = document.createElement("div");
    const row = item.row || {};
    left.appendChild(createTextElement("strong", row.case_number || "Sem processo"));
    left.appendChild(createTextElement(
      "p",
      [row.case_entity || "No case entity", row.case_city || "No case city", row.service_date || "No service date"].join(" | "),
    ));
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = presentation.interpretationHistoryOpenLabel;
    button.addEventListener("click", () => onOpen?.(item));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = presentation.interpretationHistoryDeleteLabel;
    deleteButton.addEventListener("click", () => onDelete?.(item));
    actions.appendChild(button);
    actions.appendChild(deleteButton);
    card.appendChild(left);
    card.appendChild(actions);
    container.appendChild(card);
  }
}
