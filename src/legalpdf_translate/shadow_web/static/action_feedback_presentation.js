export function buildActionFailureFeedback(
  error = {},
  fallback = "",
  { panelSlot = "", diagnosticsSlot = "" } = {},
) {
  const message = error?.message || fallback;
  return {
    panelSlot,
    diagnosticsSlot,
    tone: "bad",
    message,
    diagnosticsHint: message,
    diagnosticsOpen: true,
  };
}
