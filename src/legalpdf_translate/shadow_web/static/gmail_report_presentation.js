import { browserPdfDiagnosticsFromError } from "./browser_pdf.js";

export function buildGmailFailureReportActionPresentation({
  failureReportContext = null,
} = {}) {
  return {
    available: Boolean(failureReportContext),
    label: "Generate Failure Report",
  };
}

export function buildGmailFinalizationReportActionPresentation({
  finalizationReportContext = null,
  lastFinalizationReportPayload = null,
} = {}) {
  return {
    available: Boolean(finalizationReportContext),
    label: lastFinalizationReportPayload
      ? "Generate Updated Finalization Report"
      : "Generate Finalization Report",
  };
}

export function buildGmailBrowserFailureReportDiagnosticsPresentation({
  payload = null,
} = {}) {
  return {
    hint: payload?.normalized_payload?.report_path || "Gmail browser failure report generated.",
    open: true,
  };
}

export function buildGmailFinalizationReportDiagnosticsPresentation({
  payload = null,
} = {}) {
  return {
    hint: payload?.normalized_payload?.report_path || "Gmail finalization report generated.",
    open: true,
  };
}

export function buildGmailBrowserFailureHintPresentation({
  error = null,
  fallbackMessage = "",
} = {}) {
  const diagnostics = browserPdfDiagnosticsFromError(error);
  if (
    diagnostics.error === "browser_pdf_worker_load_failed"
    || diagnostics.error === "browser_pdf_module_load_failed"
  ) {
    const phase = String(diagnostics.worker_boot_phase || diagnostics.phase || "worker_boot").trim().replaceAll("_", " ");
    const attemptedUrl = String(diagnostics.attempted_url || diagnostics.worker_url || diagnostics.module_url || "").trim();
    const rawBrowserError = String(diagnostics.raw_browser_error || diagnostics.raw_message || "").trim();
    const location = attemptedUrl ? ` at ${attemptedUrl}` : "";
    const rawDetail = rawBrowserError ? ` Browser error: ${rawBrowserError}` : "";
    return `Browser PDF ${phase} failed${location}.${rawDetail} Generate a failure report here or review the Gmail diagnostics below for the exact asset details.`;
  }
  return String(fallbackMessage || "");
}
