export function renderInterpretationSessionShellInto(nodes = {}, shell = {}) {
  if (!nodes) {
    return;
  }
  const {
    body = null,
    shell: sessionShell = null,
    panels = [],
    result = null,
    primaryButton = null,
    sessionOpenButton = null,
    statusNode = null,
  } = nodes;
  const gmailModeActive = Boolean(shell.gmailModeActive);
  if (body?.dataset) {
    body.dataset.interpretationWorkspaceMode = String(shell.mode ?? "");
  }
  if (sessionShell) {
    sessionShell.classList.toggle("hidden", !gmailModeActive);
  }
  for (const panel of panels || []) {
    panel?.classList?.toggle("hidden", gmailModeActive);
  }
  if (!gmailModeActive) {
    return;
  }
  if (primaryButton) {
    primaryButton.textContent = String(shell.primaryLabel ?? "");
  }
  if (sessionOpenButton) {
    sessionOpenButton.textContent = String(shell.secondaryLabel ?? "");
  }
  if (statusNode) {
    statusNode.textContent = String(shell.status ?? "");
  }
  result?.classList?.remove("empty-state");
}

export function renderInterpretationDisclosureSectionsInto(nodes = {}, disclosure = {}) {
  if (!nodes) {
    return;
  }
  const pairs = [
    {
      details: nodes.serviceDetails,
      summary: nodes.serviceSummary,
      open: disclosure.serviceOpen,
      summaryText: disclosure.serviceSummary,
    },
    {
      details: nodes.textDetails,
      summary: nodes.textSummary,
      open: disclosure.textOpen,
      summaryText: disclosure.textSummary,
    },
    {
      details: nodes.recipientDetails,
      summary: nodes.recipientSummary,
      open: disclosure.recipientOpen,
      summaryText: disclosure.recipientSummary,
    },
    {
      details: nodes.amountsDetails,
      summary: nodes.amountsSummary,
      open: disclosure.amountsOpen,
      summaryText: disclosure.amountsSummary,
    },
  ];
  for (const pair of pairs) {
    if (pair.details) {
      pair.details.open = Boolean(pair.open);
    }
    if (pair.summary) {
      pair.summary.textContent = String(pair.summaryText ?? "");
    }
  }
}

export function focusInterpretationFieldInto(nodes = {}, fieldName = "") {
  if (!nodes) {
    return;
  }
  const {
    serviceSection = null,
    textSection = null,
    target = null,
  } = nodes;
  const normalizedField = String(fieldName || "").trim();
  if (
    normalizedField === "service_city"
    || normalizedField === "service_entity"
    || normalizedField === "service_date"
  ) {
    serviceSection?.setAttribute?.("open", "open");
  }
  if (normalizedField === "travel_km_outbound") {
    textSection?.setAttribute?.("open", "open");
  }
  target?.focus?.();
}

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

export function syncInterpretationReviewDrawerStateInto(backdrop, body, open) {
  if (!backdrop) {
    return;
  }
  const isOpen = Boolean(open);
  backdrop.classList.toggle("hidden", !isOpen);
  backdrop.setAttribute("aria-hidden", isOpen ? "false" : "true");
  if (body) {
    body.dataset.interpretationReviewDrawer = isOpen ? "open" : "closed";
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
