const DEFAULT_EXPORT_PRESENTATION = Object.freeze({
  readyTitle: "The fee-request document is ready.",
  localOnlyTitle: "The DOCX is ready, but the PDF is only available locally.",
  failedTitle: "The fee-request document could not be created.",
  readyLabel: "Ready",
  localOnlyLabel: "Local only",
  failedLabel: "Needs review",
  pdfReadyLabel: "Ready",
});

const DEFAULT_GMAIL_RESULT_PRESENTATION = Object.freeze({
  createdTitle: "Gmail reply created.",
  createdLabel: "Gmail reply created",
  localOnlyTitle: "Final files are ready.",
  localOnlyLabel: "Final files are ready",
  warningTitle: "Gmail reply needs review.",
  warningLabel: "Gmail reply needs review",
});

const DEFAULT_DRAWER_PRESENTATION = Object.freeze({
  gmailResultEmpty: "Gmail reply details will appear here after the final step.",
});

function objectOrEmpty(value) {
  return value && typeof value === "object" ? value : {};
}

function exportCopy(presentation = {}) {
  return {
    ...DEFAULT_EXPORT_PRESENTATION,
    ...objectOrEmpty(presentation?.export),
  };
}

function gmailResultCopy(presentation = {}) {
  return {
    ...DEFAULT_GMAIL_RESULT_PRESENTATION,
    ...objectOrEmpty(presentation?.gmailResult),
  };
}

function drawerCopy(presentation = {}) {
  return {
    ...DEFAULT_DRAWER_PRESENTATION,
    ...objectOrEmpty(presentation?.drawer),
  };
}

function wordBreakItem(label, value) {
  return { label, value, className: "word-break" };
}

function plainItem(label, value) {
  return { label, value, className: "" };
}

export function buildInterpretationExportResultPresentation({
  payload = {},
  presentation = {},
} = {}) {
  const result = objectOrEmpty(payload?.normalized_payload);
  const pdf = objectOrEmpty(payload?.diagnostics?.pdf_export);
  const copy = exportCopy(presentation);
  const isOk = payload?.status === "ok";
  const isLocalOnly = payload?.status === "local_only";
  const label = isOk
    ? copy.readyLabel
    : isLocalOnly
      ? copy.localOnlyLabel
      : copy.failedLabel;
  const title = isOk
    ? copy.readyTitle
    : isLocalOnly
      ? pdf.failure_message || copy.localOnlyTitle
      : copy.failedTitle;
  const tone = isOk ? "ok" : isLocalOnly ? "warn" : "bad";

  return {
    title,
    message: "",
    chip: { label, tone },
    items: [
      wordBreakItem("DOCX", result.docx_path || "Unavailable"),
      wordBreakItem("PDF", result.pdf_path || "Unavailable"),
      plainItem("PDF Export", pdf.ok ? copy.pdfReadyLabel : pdf.failure_message || "Unavailable"),
    ],
  };
}

export function buildInterpretationGmailResultPresentation({
  payload = {},
  presentation = {},
} = {}) {
  const result = objectOrEmpty(payload?.normalized_payload);
  const status = payload?.status || "ok";
  const gmailCopy = gmailResultCopy(presentation);
  const drawer = drawerCopy(presentation);
  const message = result.gmail_draft_result?.message
    || result.draft_prereqs?.message
    || result.pdf_path
    || result.docx_path
    || drawer.gmailResultEmpty;
  const title = status === "ok"
    ? gmailCopy.createdTitle
    : status === "local_only"
      ? gmailCopy.localOnlyTitle
      : gmailCopy.warningTitle;
  const label = status === "ok"
    ? gmailCopy.createdLabel
    : status === "local_only"
      ? gmailCopy.localOnlyLabel
      : gmailCopy.warningLabel;
  const tone = status === "ok" ? "ok" : status === "local_only" ? "warn" : "bad";

  return {
    title,
    message,
    chip: { label, tone },
    items: [
      wordBreakItem("DOCX", result.docx_path || "Unavailable"),
      wordBreakItem("PDF", result.pdf_path || "Unavailable"),
      plainItem("Reply status", label),
    ],
  };
}
