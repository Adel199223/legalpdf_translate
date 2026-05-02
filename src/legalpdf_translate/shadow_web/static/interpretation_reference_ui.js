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
