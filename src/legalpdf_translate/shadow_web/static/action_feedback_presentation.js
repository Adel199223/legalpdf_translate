export function buildActionFailureFeedback(
  error = {},
  fallback = "",
  { panelSlot = "", diagnosticsSlot = "", tone = "bad" } = {},
) {
  const message = error?.message || fallback;
  return {
    panelSlot,
    diagnosticsSlot,
    tone,
    message,
    diagnosticsHint: message,
    diagnosticsOpen: true,
  };
}

export function applyActionFailureFeedbackToUi(
  error,
  {
    panelSlot = "",
    diagnosticsSlot = "",
    fallback = "",
    tone = "bad",
    diagnosticsHint = "",
    diagnosticsValue = undefined,
  } = {},
  {
    setPanelStatus = null,
    setDiagnostics = null,
  } = {},
) {
  const feedback = buildActionFailureFeedback(error, fallback, {
    panelSlot,
    diagnosticsSlot,
    tone,
  });
  const resolvedDiagnosticsHint = typeof diagnosticsHint === "function"
    ? diagnosticsHint(feedback.message)
    : (diagnosticsHint || feedback.diagnosticsHint);
  const resolvedDiagnosticsValue = typeof diagnosticsValue === "function"
    ? diagnosticsValue(feedback, error)
    : diagnosticsValue;
  if (typeof setPanelStatus === "function") {
    setPanelStatus(feedback.panelSlot, feedback.tone, feedback.message);
  }
  if (feedback.diagnosticsSlot && typeof setDiagnostics === "function") {
    setDiagnostics(feedback.diagnosticsSlot, resolvedDiagnosticsValue === undefined ? error : resolvedDiagnosticsValue, {
      hint: resolvedDiagnosticsHint,
      open: feedback.diagnosticsOpen,
    });
  }
  return feedback;
}

export function buildActionFailureClientMarker(error = {}, fallback = "") {
  const feedback = buildActionFailureFeedback(error, fallback);
  return {
    reason: error?.payload?.diagnostics?.error || error?.name || "bootstrap_failed",
    message: feedback.message,
  };
}
