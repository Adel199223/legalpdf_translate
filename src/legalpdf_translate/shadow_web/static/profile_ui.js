import {
  deriveProfilePresentation,
  normalizeDistanceRows,
} from "./profile_presentation.js";
import { clearNode, createEmptyState, createTextElement, setText } from "./safe_rendering.js";

export function renderProfileToolbarInto(nodes = {}, { liveData = false } = {}) {
  const { importButton = null, newButton = null } = nodes || {};
  if (importButton) {
    const usingLiveApp = liveData === true;
    importButton.disabled = usingLiveApp;
    setText(importButton, usingLiveApp ? "Using live app profiles" : "Copy profiles from live app");
  }
  if (newButton) {
    newButton.disabled = false;
  }
}

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

export function syncProfileEditorDrawerStateInto(backdrop, body, open) {
  if (!backdrop) {
    return;
  }
  const isOpen = Boolean(open);
  backdrop.classList.toggle("hidden", !isOpen);
  backdrop.setAttribute("aria-hidden", isOpen ? "false" : "true");
  if (body) {
    body.dataset.profileEditorDrawer = isOpen ? "open" : "closed";
  }
}

export function renderProfileDistanceStatusInto(node, { tone = "", message = "" } = {}) {
  if (!node) {
    return;
  }
  setText(node, message);
  if (tone) {
    node.dataset.tone = tone;
  } else {
    delete node.dataset.tone;
  }
}

export function renderProfileDistanceJsonInto(field, value = "") {
  if (!field) {
    return;
  }
  field.value = String(value ?? "");
}

function setControlValue(node, value) {
  if (!node) {
    return;
  }
  node.value = String(value ?? "");
}

export function renderProfileEditorFieldsInto(nodes = {}, values = {}) {
  const {
    fieldNodes = {},
    makePrimary = null,
    distanceCity = null,
    distanceKm = null,
  } = nodes || {};
  const {
    profileFields = {},
    isPrimary = false,
    clearDistanceDraft = false,
  } = values || {};
  if (!fieldNodes && !makePrimary && !distanceCity && !distanceKm) {
    return;
  }
  for (const [key, node] of Object.entries(fieldNodes || {})) {
    setControlValue(node, profileFields?.[key]);
  }
  if (makePrimary) {
    makePrimary.checked = Boolean(isPrimary);
  }
  if (clearDistanceDraft) {
    setControlValue(distanceCity, "");
    setControlValue(distanceKm, "");
  }
}

export function renderProfileEditorChromeInto(
  {
    status = null,
    setPrimaryButton = null,
    deleteButton = null,
    distanceAdvancedDetails = null,
  } = {},
  {
    statusMessage = "",
    hasProfile = false,
    useAsMainLabel = "",
    deleteLabel = "Delete profile",
    collapseDistanceAdvanced = false,
  } = {},
) {
  if (status) {
    setText(status, statusMessage);
  }
  if (setPrimaryButton) {
    setPrimaryButton.disabled = !hasProfile;
    setText(setPrimaryButton, useAsMainLabel);
  }
  if (deleteButton) {
    deleteButton.disabled = !hasProfile;
    setText(deleteButton, deleteLabel);
  }
  if (distanceAdvancedDetails && collapseDistanceAdvanced) {
    distanceAdvancedDetails.open = false;
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

export function renderPrimaryProfileCardInto(card, primaryProfile) {
  if (!card) {
    return;
  }
  clearNode(card);
  if (!primaryProfile) {
    card.classList.add("empty-state");
    setText(card, "No main profile is set yet. Add a profile or choose one from the list.");
    return;
  }
  const presentation = deriveProfilePresentation(primaryProfile);
  card.classList.remove("empty-state");

  const header = document.createElement("div");
  header.className = "result-header";
  const details = document.createElement("div");
  details.appendChild(createTextElement("p", "Main profile summary", "eyebrow"));
  details.appendChild(createTextElement("strong", presentation.displayName));
  details.appendChild(createTextElement("p", presentation.contactSummary));
  header.appendChild(details);
  header.appendChild(createTextElement("span", presentation.mainChipLabel, "status-chip ok"));
  card.appendChild(header);

  const meta = document.createElement("div");
  meta.className = "history-meta";
  meta.appendChild(createTextElement("small", presentation.travelOriginSummary));
  meta.appendChild(createTextElement("small", presentation.distanceSummary));
  card.appendChild(meta);
}

export function renderProfileListInto(
  container,
  profiles = [],
  { count = 0, onEdit, onSetPrimary, onDelete } = {},
) {
  if (!container) {
    return;
  }
  clearNode(container);
  if (!profiles.length) {
    container.appendChild(createEmptyState(
      "No profiles yet. Add a profile to get started.",
      "result-card empty-state",
    ));
    return;
  }
  for (const profile of profiles) {
    const presentation = deriveProfilePresentation(profile);
    const distanceCount = normalizeDistanceRows(profile.travel_distances_by_city || {}).length;
    const article = document.createElement("article");
    article.className = "profile-card";

    const header = document.createElement("div");
    header.className = "result-header";
    const details = document.createElement("div");
    details.appendChild(createTextElement("p", "Profile record", "eyebrow"));
    details.appendChild(createTextElement("h3", presentation.displayName));
    details.appendChild(createTextElement("p", presentation.contactSummary));
    header.appendChild(details);
    const chipLabel = profile.is_primary
      ? presentation.mainChipLabel
      : `${distanceCount} saved city distance${distanceCount === 1 ? "" : "s"}`;
    header.appendChild(createTextElement(
      "span",
      chipLabel,
      `status-chip ${profile.is_primary ? "ok" : "info"}`,
    ));
    article.appendChild(header);

    const meta = document.createElement("div");
    meta.className = "history-meta";
    meta.appendChild(createTextElement("small", presentation.travelOriginSummary));
    meta.appendChild(createTextElement("small", presentation.distanceSummary));
    article.appendChild(meta);
    article.appendChild(createTextElement(
      "p",
      "Edit this profile's contact, payment, and travel details.",
      "profile-card-helper",
    ));

    const actions = document.createElement("div");
    actions.className = "history-actions";
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => onEdit?.(profile));
    const primaryButton = document.createElement("button");
    primaryButton.type = "button";
    primaryButton.textContent = presentation.useAsMainLabel;
    primaryButton.disabled = Boolean(profile.is_primary);
    primaryButton.addEventListener("click", () => onSetPrimary?.(profile));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete profile";
    deleteButton.disabled = Boolean(count <= 1);
    deleteButton.addEventListener("click", () => onDelete?.(profile));
    actions.appendChild(editButton);
    actions.appendChild(primaryButton);
    actions.appendChild(deleteButton);
    article.appendChild(actions);
    container.appendChild(article);
  }
}
