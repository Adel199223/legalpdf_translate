import {
  appendResultGridItem,
  createResultHeader,
} from "./result_card_ui.js";
import { clearNode } from "./safe_rendering.js";

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
