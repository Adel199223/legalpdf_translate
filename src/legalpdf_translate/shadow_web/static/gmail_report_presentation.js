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
