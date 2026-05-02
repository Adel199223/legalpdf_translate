import { clearNode } from "./safe_rendering.js";

function appendOption(select, { value = "", text = "", selected = false } = {}) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = text;
  if (selected) {
    option.selected = true;
  }
  select.appendChild(option);
  return option;
}

export function renderInterpretationCityOptionsInto(select, cities = [], selectedValue = "") {
  if (!select) {
    return;
  }
  const currentValue = String(selectedValue || "");
  clearNode(select);
  appendOption(select, {
    value: "",
    text: "Select a city",
    selected: !currentValue,
  });
  for (const city of cities || []) {
    const value = String(city ?? "");
    appendOption(select, {
      value,
      text: value,
      selected: value === currentValue,
    });
  }
  select.value = currentValue;
}

export function renderCourtEmailOptionsInto(select, { options = [], selectedEmail = "" } = {}) {
  if (!select) {
    return;
  }
  const selectedValue = String(selectedEmail || "");
  const emailOptions = options || [];
  clearNode(select);
  appendOption(select, {
    value: "",
    text: emailOptions.length ? "Select a court email" : "No email saved for this city",
    selected: !selectedValue,
  });
  for (const email of emailOptions) {
    const value = String(email ?? "");
    appendOption(select, {
      value,
      text: value,
      selected: value === selectedValue,
    });
  }
  select.value = selectedValue;
}

export function renderCourtEmailStatusInto(status, { message = "", tone = "" } = {}) {
  if (!status) {
    return;
  }
  status.textContent = String(message ?? "");
  if (tone) {
    status.dataset.tone = String(tone);
  }
}

export function renderCourtEmailEditorInto(nodes = {}, editorState = {}) {
  const {
    editor = null,
    newEmailField = null,
    status = null,
  } = nodes || {};
  if (!editor) {
    return;
  }
  const open = Boolean(editorState.open);
  editor.classList.toggle("hidden", !open);
  if (!open) {
    return;
  }
  if (newEmailField) {
    newEmailField.value = "";
  }
  const cityLabel = String(editorState.cityLabel || "selected city");
  renderCourtEmailStatusInto(status, {
    message: `Add an email for ${cityLabel}.`,
  });
}

export function renderServiceEntityOptionsInto(select, options = [], selectedValue = "") {
  if (!select) {
    return;
  }
  const currentValue = String(selectedValue || "");
  clearNode(select);
  appendOption(select, {
    value: "",
    text: "Select service entity",
    selected: !currentValue,
  });
  for (const optionValue of options || []) {
    const value = String(optionValue ?? "");
    appendOption(select, {
      value,
      text: value,
      selected: value === currentValue,
    });
  }
  select.value = currentValue;
}

export function renderInterpretationFieldWarningInto(node, { message = "", tone = "warning" } = {}) {
  if (!node) {
    return;
  }
  const text = String(message || "").trim();
  node.textContent = text;
  node.classList.toggle("hidden", !text);
  node.classList.toggle("is-warning", Boolean(text) && tone === "warning");
  node.classList.toggle("is-danger", Boolean(text) && tone === "danger");
}

export function renderInterpretationDistanceHintInto(hint, text = "") {
  if (!hint) {
    return;
  }
  hint.textContent = String(text ?? "");
}

export function renderInterpretationActionButtonsInto(buttons = [], { blocked = false } = {}) {
  for (const button of buttons || []) {
    if (!button) {
      continue;
    }
    const keepHidden = button.classList.contains("hidden");
    button.disabled = Boolean(blocked) || button.getAttribute("aria-busy") === "true";
    if (keepHidden) {
      button.classList.add("hidden");
    }
  }
}

export function renderInterpretationCityAddButtonsInto(nodes = {}, state = {}) {
  const { caseButton = null, serviceButton = null } = nodes || {};
  const {
    provisionalCaseCity = "",
    provisionalServiceCity = "",
    serviceSame = false,
  } = state || {};
  if (caseButton) {
    caseButton.textContent = provisionalCaseCity ? `Add “${provisionalCaseCity}”` : "Add city...";
  }
  if (serviceButton) {
    serviceButton.textContent = provisionalServiceCity ? `Add “${provisionalServiceCity}”` : "Add city...";
    serviceButton.disabled = Boolean(serviceSame);
  }
}

export function renderServiceSameControlsInto(nodes = {}, { serviceSame = false } = {}) {
  const {
    serviceEntity = null,
    serviceCity = null,
    hint = null,
  } = nodes || {};
  const sameLocation = Boolean(serviceSame);
  if (serviceEntity) {
    serviceEntity.disabled = sameLocation;
  }
  if (serviceCity) {
    serviceCity.disabled = sameLocation;
  }
  if (hint) {
    hint.textContent = sameLocation
      ? "Service entity and city will mirror the case fields for save and export."
      : "Use different service fields when the service location differs from the case.";
  }
}

export function syncInterpretationCityDialogStateInto(backdrop, body, open) {
  if (!backdrop) {
    return;
  }
  const isOpen = Boolean(open);
  backdrop.classList.toggle("hidden", !isOpen);
  backdrop.setAttribute("aria-hidden", isOpen ? "false" : "true");
  if (body) {
    body.dataset.interpretationCityDialog = isOpen ? "open" : "closed";
  }
}

export function renderInterpretationCityDialogContentInto(nodes = {}, dialog = {}) {
  const {
    title = null,
    status = null,
    cityInput = null,
    distanceShell = null,
    distanceHint = null,
    confirmButton = null,
  } = nodes || {};
  if (title) {
    title.textContent = String(dialog.title ?? "");
  }
  if (status) {
    status.textContent = String(dialog.status ?? "");
  }
  if (cityInput) {
    cityInput.readOnly = Boolean(dialog.lockedCity);
  }
  if (distanceShell) {
    distanceShell.classList.toggle("hidden", !Boolean(dialog.showDistance));
  }
  if (distanceHint) {
    distanceHint.textContent = String(dialog.distanceHint ?? "");
  }
  if (confirmButton) {
    confirmButton.textContent = String(dialog.confirmLabel ?? "");
  }
}
