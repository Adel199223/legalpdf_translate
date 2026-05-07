export function renderGmailDemoReviewActionInto(button, { visible = false } = {}) {
  if (!button) {
    return undefined;
  }

  const show = Boolean(visible);
  button.classList.toggle("hidden", !show);
  button.disabled = !show;
  return button;
}

export function renderGmailReturnToSourceActionInto(button, { visible = false, sourceUrl = "" } = {}) {
  if (!button) {
    return undefined;
  }

  const show = Boolean(visible);
  button.classList.toggle("hidden", !show);
  button.disabled = !show;
  button.title = show ? String(sourceUrl || "") : "";
  return button;
}

export function renderGmailPrepareActionInto(button, { label = "", disabled = false, title = "" } = {}) {
  if (!button) {
    return undefined;
  }

  const nextLabel = String(label || "");
  button.textContent = nextLabel;
  button.dataset.defaultLabel = nextLabel;
  button.disabled = Boolean(disabled);
  button.title = String(title || "");
  return button;
}
