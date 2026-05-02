import {
  appendResultGridItem,
  createResultHeader,
} from "./result_card_ui.js";
import { clearNode } from "./safe_rendering.js";

function valueOrNotSet(value) {
  return value || "Not set yet";
}

function renderCardGridInto(container, { title = "", message = "", chip = {}, items = [] } = {}) {
  if (!container) {
    return;
  }
  clearNode(container);
  container.appendChild(createResultHeader({
    title,
    message,
    label: chip.label || "",
    tone: chip.tone || "info",
  }));
  const grid = document.createElement("div");
  grid.className = "result-grid";
  for (const item of items) {
    appendResultGridItem(grid, item.label, valueOrNotSet(item.value), { className: "word-break" });
  }
  container.appendChild(grid);
}

export function renderInterpretationSessionCardInto(container, card = {}) {
  renderCardGridInto(container, {
    title: card.title || "",
    message: card.message || "",
    chip: card.chip || {},
    items: [
      { label: "Case Number", value: card.caseNumber },
      { label: "Court Email", value: card.courtEmail },
      { label: "Service Date", value: card.serviceDate },
      { label: "Location", value: card.location },
    ],
  });
}

export function renderInterpretationSeedCardInto(container, card = {}) {
  renderCardGridInto(container, {
    title: card.title || "",
    message: card.message || "",
    chip: card.chip || {},
    items: [
      { label: "Case", value: card.caseValue },
      { label: "Court Email", value: card.courtEmail },
      { label: "Service Date", value: card.serviceDate },
      { label: "Location", value: card.location },
    ],
  });
}

export function renderInterpretationSeedCardStateInto(container, { empty = false, emptyText = "", card = {} } = {}) {
  if (!container) {
    return;
  }
  if (empty) {
    container.classList.add("empty-state");
    container.textContent = String(emptyText ?? "");
    return;
  }
  container.classList.remove("empty-state");
  renderInterpretationSeedCardInto(container, card || {});
}

export function renderInterpretationReviewSummaryCardInto(container, card = {}) {
  renderCardGridInto(container, {
    title: card.title || "",
    message: card.message || "",
    chip: card.chip || {},
    items: [
      { label: "Case Number", value: card.caseNumber },
      { label: "Court Email", value: card.courtEmail },
      { label: "Service Date", value: card.serviceDate },
      { label: "Location", value: card.location },
    ],
  });
}

export function renderInterpretationLocationGuardInto(card, { message = "", tone = "warning" } = {}) {
  if (!card) {
    return;
  }
  const text = String(message || "").trim();
  if (!text) {
    card.classList.add("hidden");
    card.classList.add("empty-state");
    card.textContent = "";
    return;
  }
  card.classList.remove("hidden", "empty-state");
  clearNode(card);
  const isDanger = tone === "danger";
  card.appendChild(createResultHeader({
    title: text,
    message: "",
    label: isDanger ? "Action blocked" : "Needs review",
    tone: isDanger ? "bad" : "warn",
  }));
}

export function renderInterpretationExportResultInto(container, payload, presentation) {
  const result = payload.normalized_payload || {};
  const pdf = payload.diagnostics?.pdf_export || {};
  const isOk = payload.status === "ok";
  const isLocalOnly = payload.status === "local_only";
  const tone = isOk ? "ok" : isLocalOnly ? "warn" : "bad";
  const label = isOk
    ? presentation.export.readyLabel
    : isLocalOnly
      ? presentation.export.localOnlyLabel
      : presentation.export.failedLabel;
  const message = isOk
    ? presentation.export.readyTitle
    : isLocalOnly
      ? pdf.failure_message || presentation.export.localOnlyTitle
      : presentation.export.failedTitle;
  container.classList.remove("empty-state");
  clearNode(container);
  container.appendChild(createResultHeader({
    title: message,
    message: "",
    label,
    tone: tone === "ok" ? "ok" : tone === "bad" ? "bad" : "warn",
  }));
  const grid = document.createElement("div");
  grid.className = "result-grid";
  appendResultGridItem(grid, "DOCX", result.docx_path || "Unavailable", { className: "word-break" });
  appendResultGridItem(grid, "PDF", result.pdf_path || "Unavailable", { className: "word-break" });
  appendResultGridItem(
    grid,
    "PDF Export",
    pdf.ok ? presentation.export.pdfReadyLabel : pdf.failure_message || "Unavailable",
  );
  container.appendChild(grid);
}

export function resetInterpretationExportResultInto(panel, result, emptyText = "") {
  if (panel) {
    panel.classList.add("hidden");
  }
  if (result) {
    result.classList.add("empty-state");
    result.textContent = String(emptyText ?? "");
  }
}

export function renderInterpretationGmailResultInto(container, payload, presentation) {
  if (!container) {
    return;
  }
  const result = payload.normalized_payload || {};
  const status = payload.status || "ok";
  const draftMessage = result.gmail_draft_result?.message
    || result.draft_prereqs?.message
    || result.pdf_path
    || result.docx_path
    || presentation.drawer.gmailResultEmpty;
  const title = status === "ok"
    ? presentation.gmailResult.createdTitle
    : status === "local_only"
      ? presentation.gmailResult.localOnlyTitle
      : presentation.gmailResult.warningTitle;
  const label = status === "ok"
    ? presentation.gmailResult.createdLabel
    : status === "local_only"
      ? presentation.gmailResult.localOnlyLabel
      : presentation.gmailResult.warningLabel;
  const tone = status === "ok" ? "ok" : status === "local_only" ? "warn" : "bad";
  container.classList.remove("empty-state");
  clearNode(container);
  container.appendChild(createResultHeader({
    title,
    message: draftMessage,
    label,
    tone,
  }));
  const grid = document.createElement("div");
  grid.className = "result-grid";
  appendResultGridItem(grid, "DOCX", result.docx_path || "Unavailable", { className: "word-break" });
  appendResultGridItem(grid, "PDF", result.pdf_path || "Unavailable", { className: "word-break" });
  appendResultGridItem(grid, "Reply status", label);
  container.appendChild(grid);
}

export function renderInterpretationCompletionCardInto(container, card = {}) {
  if (!container) {
    return;
  }
  const chip = card.chip || {};
  container.classList.remove("empty-state");
  clearNode(container);
  container.appendChild(createResultHeader({
    title: card.title || "",
    message: card.message || "",
    label: chip.label || "",
    tone: chip.tone || "info",
  }));
  const grid = document.createElement("div");
  grid.className = "result-grid";
  appendResultGridItem(
    grid,
    "DOCX",
    card.docxPath || "Unavailable in this session view",
    { className: "word-break" },
  );
  appendResultGridItem(grid, "PDF", card.pdfPath || "Unavailable", { className: "word-break" });
  appendResultGridItem(grid, "Case Location", card.caseLocation || "", { className: "word-break" });
  appendResultGridItem(grid, "Service Location", card.serviceLocation || "", { className: "word-break" });
  container.appendChild(grid);
}
