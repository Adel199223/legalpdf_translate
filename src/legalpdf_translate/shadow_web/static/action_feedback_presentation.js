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
