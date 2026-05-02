function buttonById(id) {
  return document.getElementById(id);
}

export function setBusy(buttonIds, busy, busyLabels = {}) {
  for (const id of buttonIds || []) {
    const button = buttonById(id);
    if (!button) {
      continue;
    }
    if (!button.dataset.defaultLabel) {
      button.dataset.defaultLabel = button.textContent;
    }
    button.disabled = busy;
    button.setAttribute("aria-busy", busy ? "true" : "false");
    button.textContent = busy ? busyLabels[id] || button.dataset.defaultLabel : button.dataset.defaultLabel;
  }
}

export async function runWithBusy(buttonIds, busyLabels, action, options = {}) {
  const guardIds = options.guardIds || buttonIds;
  if ((guardIds || []).some((id) => buttonById(id)?.disabled)) {
    return;
  }
  setBusy(buttonIds, true, busyLabels);
  try {
    return await action();
  } finally {
    setBusy(buttonIds, false);
  }
}
