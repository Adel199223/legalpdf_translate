export function renderGmailReportActionInto(button, { available = false, label = "" } = {}) {
  if (!button) {
    return undefined;
  }
  button.classList.toggle("hidden", !available);
  button.disabled = !available;
  button.textContent = label;
  button.dataset.defaultLabel = label;
  return button;
}
