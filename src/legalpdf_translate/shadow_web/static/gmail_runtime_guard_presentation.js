const BLOCKED_HINT = "Review actions are paused until the live Gmail runtime is canonical.";
const RESTART_HINT = "Restarting the browser runtime for live Gmail. This page will reconnect automatically.";

function normalizeDiagnostics(diagnostics) {
  return diagnostics && typeof diagnostics === "object"
    ? { ...diagnostics }
    : {};
}

function guardMessage(guard) {
  return String(guard?.message || "").trim();
}

export function buildGmailRuntimeGuardBlockedDiagnosticsPresentation({
  guard = null,
  diagnostics = null,
} = {}) {
  return {
    payload: {
      status: "blocked",
      diagnostics: normalizeDiagnostics(diagnostics),
    },
    presentation: {
      hint: guardMessage(guard) || BLOCKED_HINT,
      open: true,
    },
  };
}

export function buildGmailRuntimeGuardRestartDiagnosticsPresentation({
  diagnostics = null,
} = {}) {
  return {
    payload: {
      status: "restarting",
      diagnostics: normalizeDiagnostics(diagnostics),
    },
    presentation: {
      hint: RESTART_HINT,
      open: true,
    },
  };
}
