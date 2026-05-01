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
