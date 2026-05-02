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

export function syncInterpretationReviewDetailsShellInto(details, summaryNode, shell = {}) {
  if (!details) {
    return;
  }
  if (!shell.completed) {
    details.open = true;
    delete details.dataset.autocollapsed;
    if (summaryNode) {
      summaryNode.textContent = shell.openSummary || "";
    }
    return;
  }
  if (details.dataset.autocollapsed !== "done") {
    details.open = false;
    details.dataset.autocollapsed = "done";
  }
  if (summaryNode) {
    summaryNode.textContent = shell.closedSummary || "";
  }
}

export function renderInterpretationReviewSurfaceInto(nodes = {}, surface = {}) {
  if (!nodes) {
    return;
  }
  const labels = surface.labels || {};
  const actions = surface.actions || {};
  const {
    openButton,
    drawerTitle,
    clearButton,
    clearTopButton,
    reloadHistoryButton,
    saveButton,
    exportButton,
    gmailButton,
    closeFooterButton,
    gmailResult,
    statusNode,
  } = nodes;

  if (openButton) {
    openButton.textContent = labels.openReview || "";
  }
  if (drawerTitle) {
    drawerTitle.textContent = labels.drawerTitle || "";
  }
  if (clearButton) {
    clearButton.textContent = labels.startBlank || "";
  }
  if (clearTopButton) {
    clearTopButton.textContent = labels.startBlank || "";
  }
  if (reloadHistoryButton) {
    reloadHistoryButton.textContent = labels.refreshHistory || "";
  }
  if (saveButton) {
    saveButton.textContent = labels.saveRow || "";
  }
  if (exportButton) {
    exportButton.textContent = labels.export || "";
  }
  if (gmailButton) {
    gmailButton.textContent = labels.finalizeGmail || "";
    gmailButton.classList.toggle("hidden", !actions.showFinalizeGmail);
  }
  if (saveButton) {
    saveButton.classList.toggle("hidden", !actions.showSaveRow);
  }
  if (exportButton) {
    exportButton.classList.toggle("hidden", !actions.showGenerateDocxPdf);
  }
  if (clearButton) {
    clearButton.classList.toggle("hidden", !actions.showNewBlank);
  }
  if (closeFooterButton) {
    closeFooterButton.classList.toggle("hidden", !actions.showFooterClose);
  }
  if (gmailResult && surface.resetGmailResult) {
    gmailResult.classList.add("empty-state");
    gmailResult.textContent = surface.gmailResultEmpty || "";
  }
  if (statusNode) {
    statusNode.textContent = labels.status || "";
  }
}
