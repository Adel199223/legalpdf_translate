export function renderInterpretationReviewContextInto(nodes = {}, card = {}) {
  const {
    container,
    titleNode,
    copyNode,
    chipNode,
    gmailButton,
    result,
  } = nodes || {};
  if (!container) {
    return;
  }
  const reviewMode = Boolean(card.reviewMode);
  container.classList.toggle("hidden", !reviewMode);
  if (!reviewMode) {
    return;
  }
  if (titleNode) {
    titleNode.textContent = card.title || "";
  }
  if (copyNode) {
    copyNode.textContent = card.copy || "";
  }
  if (chipNode) {
    const chip = card.chip || {};
    chipNode.className = `status-chip ${chip.tone || ""}`.trim();
    chipNode.textContent = chip.label || "";
  }
  if (gmailButton) {
    gmailButton.textContent = card.finalizeGmailLabel || "";
  }
  if (result && result.classList.contains("empty-state")) {
    result.textContent = card.gmailResultEmpty || "";
  }
}
