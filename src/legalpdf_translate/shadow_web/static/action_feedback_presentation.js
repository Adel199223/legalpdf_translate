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
  if (typeof setPanelStatus === "function") {
    setPanelStatus(feedback.panelSlot, feedback.tone, feedback.message);
  }
  if (feedback.diagnosticsSlot && typeof setDiagnostics === "function") {
    setDiagnostics(feedback.diagnosticsSlot, error, {
      hint: resolvedDiagnosticsHint,
      open: feedback.diagnosticsOpen,
    });
  }
  return feedback;
}
