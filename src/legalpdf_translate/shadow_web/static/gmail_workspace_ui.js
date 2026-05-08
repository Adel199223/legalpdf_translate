export function renderGmailWorkspaceStripInto(nodes = {}, card = {}) {
  if (!nodes) {
    return undefined;
  }

  const { strip, title, copy, action } = nodes;
  const visible = Boolean(card.visible);
  if (strip) {
    strip.classList.toggle("hidden", !visible);
  }
  if (!visible) {
    return nodes;
  }

  if (title) {
    title.textContent = card.title || "";
  }
  if (copy) {
    copy.textContent = card.copy || "";
  }
  if (action) {
    action.textContent = card.actionLabel || "";
    action.dataset.gmailStripAction = card.action || "";
  }

  return nodes;
}
