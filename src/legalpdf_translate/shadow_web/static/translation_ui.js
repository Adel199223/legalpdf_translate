import {
  clearNode,
  createEmptyState,
  createTextElement,
  setNodeTitle,
  setText,
} from "./safe_rendering.js";

export function renderTranslationFieldValueInto(field, value = "") {
  if (!field) {
    return undefined;
  }

  field.value = value ?? "";
  return field;
}

export function renderTranslationSourcePathInto(nodes = {}, value = "") {
  const { pathField, summary } = nodes || {};
  if (!pathField && !summary) {
    return undefined;
  }

  if (pathField) {
    pathField.value = value ?? "";
  }
  if (summary) {
    setText(summary, String(value || "").trim() || "No source staged yet.");
  }
  return pathField || summary;
}

export function renderTranslationOutputSummaryInto(nodes = {}, summary = {}) {
  const { label, copy, path } = nodes || {};
  if (!label || !copy || !path) {
    return undefined;
  }

  setText(label, summary.label || "");
  setText(copy, summary.copy || "");
  setText(path, summary.path || "");
  return label;
}

export function renderTranslationRunStatusInto(nodes = {}, view = {}) {
  const {
    percent,
    chip,
    track,
    bar,
    task,
    pages,
    currentPage,
    imageRetry,
    alerts,
  } = nodes || {};
  if (!percent || !chip || !track || !bar || !task || !pages || !currentPage || !imageRetry || !alerts) {
    return undefined;
  }

  setText(percent, view.percentText || "");
  setText(chip, view.chipText || "");
  chip.className = `status-chip ${view.chipTone || ""}`;
  track.setAttribute("aria-valuenow", String(view.percentValue));
  bar.style.width = `${view.percentValue}%`;
  setText(task, view.currentTask || "");
  setText(pages, view.pagesText || "");
  setText(currentPage, view.currentPageText || "");
  setText(imageRetry, view.imageRetryText || "");
  setText(alerts, view.alertsText || "");
  return percent;
}

export function renderTranslationPrimaryActionsInto(nodes = {}, actionState = {}) {
  const {
    helper,
    startButton,
    analyzeButton,
    cancelButton,
    resumeButton,
    rebuildButton,
  } = nodes || {};

  if (helper) {
    setText(helper, actionState.helperText || "");
  }
  if (startButton) {
    startButton.disabled = !actionState.startEnabled;
  }
  if (analyzeButton) {
    analyzeButton.disabled = !actionState.analyzeEnabled;
  }
  if (cancelButton) {
    cancelButton.disabled = !actionState.cancelEnabled;
  }
  if (resumeButton) {
    resumeButton.disabled = !actionState.resumeEnabled;
  }
  if (rebuildButton) {
    rebuildButton.disabled = !actionState.rebuildEnabled;
  }
  return helper || undefined;
}

export function renderTranslationPreparedControlsInto(nodes = {}) {
  const {
    reportButton,
    reviewExport,
    cancelButton,
    resumeButton,
    rebuildButton,
  } = nodes || {};

  if (reportButton) {
    reportButton.disabled = true;
    reportButton.classList.add("hidden");
  }
  if (reviewExport) {
    reviewExport.disabled = true;
  }
  if (cancelButton) {
    cancelButton.disabled = true;
  }
  if (resumeButton) {
    resumeButton.disabled = true;
  }
  if (rebuildButton) {
    rebuildButton.disabled = true;
  }
  return reportButton || reviewExport || cancelButton || resumeButton || rebuildButton || undefined;
}

export function renderTranslationJobActionControlsInto(nodes = {}, controls = {}) {
  const { reportButton, reviewExport } = nodes || {};
  const reportAvailable = Boolean(controls.reportAvailable);
  const reportVisible = Boolean(controls.reportVisible);
  const reviewExportAvailable = Boolean(controls.reviewExportAvailable);

  if (reportButton) {
    reportButton.disabled = !reportAvailable;
    reportButton.classList.toggle("hidden", !reportVisible);
  }
  if (reviewExport) {
    reviewExport.disabled = !reviewExportAvailable;
  }
  return reportButton || reviewExport || undefined;
}

export function renderTranslationNumericMismatchWarningInto(container, warning = {}) {
  if (!container) {
    return undefined;
  }

  const visible = Boolean(warning?.visible);
  container.classList.toggle("hidden", !visible);
  if (!visible) {
    setText(container, "");
    return container;
  }

  const lines = Array.isArray(warning.lines) ? warning.lines : [];
  const detailLines = lines.length ? `\n${lines.join("\n")}` : "";
  setText(container, `${warning.message || ""}${detailLines}`);
  container.setAttribute("role", "note");
  return container;
}

export function renderTranslationDownloadLinkInto(node, href = "") {
  if (!node) {
    return undefined;
  }

  if (href) {
    node.href = href;
    node.classList.remove("hidden");
  } else {
    node.classList.add("hidden");
    node.removeAttribute("href");
  }
  return node;
}

export function syncTranslationCompletionDrawerStateInto(nodes = {}, open = false) {
  const { backdrop, body } = nodes || {};
  if (!backdrop) {
    return undefined;
  }

  const isOpen = Boolean(open);
  backdrop.classList.toggle("hidden", !isOpen);
  backdrop.setAttribute("aria-hidden", isOpen ? "false" : "true");
  if (body?.dataset) {
    body.dataset.translationCompletionDrawer = isOpen ? "open" : "closed";
  }
  return backdrop;
}

export function renderTranslationCompletionSurfaceInto(nodes = {}, surface = {}) {
  const {
    openButton,
    formShell,
    emptyShell,
    status,
    emptyTitle,
    emptyCopy,
    saveTitle,
    saveStatus,
    saveButton,
  } = nodes || {};

  const available = Boolean(surface.available);
  const hasSaveSurface = Boolean(surface.hasSaveSurface);

  if (openButton) {
    openButton.classList.toggle("hidden", !available);
    setText(openButton, surface.openButtonLabel || "");
  }
  if (emptyTitle) {
    setText(emptyTitle, surface.emptyTitle || "");
  }
  if (emptyCopy) {
    setText(emptyCopy, surface.emptyCopy || "");
  }
  if (saveTitle) {
    setText(saveTitle, surface.saveTitle || "");
  }
  if (saveStatus) {
    setText(saveStatus, surface.saveStatus || "");
  }
  if (status) {
    setText(status, surface.drawerStatus || "");
  }

  if (!available) {
    formShell?.classList.add("hidden");
    emptyShell?.classList.add("hidden");
    return openButton || status || undefined;
  }

  formShell?.classList.toggle("hidden", !hasSaveSurface);
  emptyShell?.classList.toggle("hidden", hasSaveSurface);
  if (saveButton) {
    setText(saveButton, surface.saveButtonLabel || "");
    saveButton.disabled = Boolean(surface.saveDisabled);
  }
  return openButton || status || undefined;
}

export function renderTranslationSourceCardInto(nodes = {}, sourceCard = {}) {
  const {
    card,
    title,
    copy,
    filename,
    sourceType,
    pages,
    target,
    defaultTarget,
    stageStatus,
    hint,
    chip,
    browseButton,
    clearButton,
  } = nodes || {};

  if (!card) {
    return undefined;
  }

  card.dataset.state = sourceCard.state || "empty";
  setText(title, sourceCard.title || "");
  setText(copy, sourceCard.copy || "");
  setText(filename, sourceCard.filename || "");
  setText(sourceType, sourceCard.sourceType || "");
  setText(pages, sourceCard.pages ?? "");
  setText(target, sourceCard.target || "");
  setText(defaultTarget, sourceCard.defaultTarget || "");
  setText(stageStatus, sourceCard.stageStatus || "");
  setText(hint, sourceCard.hint || "");
  if (chip) {
    setText(chip, sourceCard.chipText || "");
    chip.className = sourceCard.chipText
      ? `status-chip ${sourceCard.chipTone || ""}`
      : "status-chip info hidden";
    chip.classList.toggle("hidden", !sourceCard.chipText);
  }
  if (browseButton) {
    setText(browseButton, sourceCard.browseLabel || "");
    browseButton.disabled = Boolean(sourceCard.browseDisabled);
  }
  clearButton?.classList.toggle("hidden", Boolean(sourceCard.clearHidden));
  return card;
}

export function renderTranslationSourceFileInputClearInto(input) {
  if (!input) {
    return undefined;
  }
  input.value = "";
  return input;
}

export function renderTranslationSourceDragStateInto(card, { active = false } = {}) {
  if (!card?.dataset) {
    return undefined;
  }
  if (active) {
    card.dataset.dragActive = "true";
  } else {
    delete card.dataset.dragActive;
  }
  return card;
}

export function renderTranslationHistoryListInto(container, history = [], {
  emptyText = "",
  openLabel = "",
  deleteLabel = "",
  onOpen,
  onDelete,
} = {}) {
  if (!container) {
    return undefined;
  }

  const items = Array.isArray(history) ? history : [];
  clearNode(container);
  if (!items.length) {
    container.appendChild(createEmptyState(emptyText));
    return container;
  }

  for (const item of items) {
    const row = item?.row || {};
    const card = document.createElement("article");
    card.className = "history-item";
    const details = document.createElement("div");
    details.appendChild(createTextElement("strong", row.case_number || "No case number"));
    details.appendChild(createTextElement(
      "p",
      [row.case_entity || "No case entity", row.case_city || "No case city", row.translation_date || "No date"].join(" | "),
    ));
    card.appendChild(details);
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = openLabel;
    button.addEventListener("click", () => onOpen?.(item));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = deleteLabel;
    deleteButton.addEventListener("click", () => onDelete?.(item));
    actions.appendChild(button);
    actions.appendChild(deleteButton);
    card.appendChild(actions);
    container.appendChild(card);
  }
  return container;
}

export function renderTranslationJobsListInto(container, jobs = [], {
  emptyText = "",
  presentationForJob,
  onOpen,
  onResume,
  onRebuild,
} = {}) {
  if (!container) {
    return undefined;
  }

  const items = Array.isArray(jobs) ? jobs : [];
  clearNode(container);
  if (!items.length) {
    container.appendChild(createEmptyState(emptyText));
    return container;
  }

  for (const job of items) {
    const presentation = typeof presentationForJob === "function" ? presentationForJob(job) || {} : {};
    const card = document.createElement("article");
    card.className = "history-item";
    const details = document.createElement("div");
    const title = createTextElement("strong", presentation.translationRunTitle);
    setNodeTitle(title, String(job?.config?.source_path || "").trim());
    details.appendChild(title);
    details.appendChild(createTextElement("p", presentation.translationRunSubtitle));
    const actions = document.createElement("div");
    actions.className = "history-meta";
    const loadButton = document.createElement("button");
    loadButton.type = "button";
    loadButton.textContent = presentation.translationRunOpenLabel;
    loadButton.addEventListener("click", () => onOpen?.(job));
    actions.appendChild(loadButton);
    if (job?.actions?.resume) {
      const resume = document.createElement("button");
      resume.type = "button";
      resume.textContent = presentation.translationRunResumeLabel;
      resume.addEventListener("click", () => onResume?.(job));
      actions.appendChild(resume);
    }
    if (job?.actions?.rebuild) {
      const rebuild = document.createElement("button");
      rebuild.type = "button";
      rebuild.textContent = presentation.translationRunRebuildLabel;
      rebuild.addEventListener("click", () => onRebuild?.(job));
      actions.appendChild(rebuild);
    }
    card.appendChild(details);
    card.appendChild(actions);
    container.appendChild(card);
  }
  return container;
}
