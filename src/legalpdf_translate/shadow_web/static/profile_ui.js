import { clearNode, createEmptyState, createTextElement } from "./safe_rendering.js";

export function renderProfileOptionsInto(select, profiles = [], primaryProfileId = "") {
  if (!select) {
    return;
  }
  clearNode(select);
  if (!profiles.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No profiles available";
    option.selected = true;
    select.appendChild(option);
    select.disabled = true;
    return;
  }
  select.disabled = false;
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.document_name || profile.id;
    if (profile.id === primaryProfileId) {
      option.selected = true;
    }
    select.appendChild(option);
  }
}

export function renderProfileDistanceRowsInto(container, rows, { onRemove } = {}) {
  if (!container) {
    return;
  }
  clearNode(container);
  if (!rows.length) {
    container.appendChild(createEmptyState(
      "No city distances saved yet. Add the cities you use most often.",
      "result-card empty-state",
    ));
    return;
  }
  for (const row of rows) {
    const article = document.createElement("article");
    article.className = "distance-row";
    const details = document.createElement("div");
    details.appendChild(createTextElement("strong", row.city));
    details.appendChild(createTextElement("p", row.distanceLabel, "distance-row-meta"));
    article.appendChild(details);
    const actions = document.createElement("div");
    actions.className = "distance-row-actions";
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "ghost-button";
    removeButton.textContent = "Delete destination";
    removeButton.setAttribute("aria-label", `Delete destination ${row.city}`);
    removeButton.addEventListener("click", () => onRemove?.(row));
    actions.appendChild(removeButton);
    article.appendChild(actions);
    container.appendChild(article);
  }
}
