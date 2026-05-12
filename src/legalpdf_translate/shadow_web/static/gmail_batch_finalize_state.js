function isCompletedTranslationSession(session) {
  return Boolean(
    session
    && typeof session === "object"
    && session.kind === "translation"
    && session.completed
  );
}

function cloneObjectOrNull(value) {
  return value && typeof value === "object" ? { ...value } : null;
}

export function selectGmailDisplayedBatchFinalizeSession({
  drawerSource = "",
  activeSession = null,
  restoredCompletedSession = null,
} = {}) {
  if (drawerSource === "restored") {
    return isCompletedTranslationSession(restoredCompletedSession) ? restoredCompletedSession : null;
  }
  return isCompletedTranslationSession(activeSession) ? activeSession : null;
}

export function selectGmailBatchFinalizePreflight({
  drawerSource = "",
  batchFinalizePreflight = null,
  displayedSession = null,
} = {}) {
  if (drawerSource === "restored") {
    return null;
  }
  const explicitPreflight = cloneObjectOrNull(batchFinalizePreflight);
  if (explicitPreflight) {
    return explicitPreflight;
  }
  return cloneObjectOrNull(displayedSession?.finalization_preflight);
}

export function deriveGmailBatchFinalizeState({
  payload = null,
  displayedSession = null,
  preflight = null,
} = {}) {
  const payloadState = String(payload?.normalized_payload?.finalization_state || "").trim();
  if (payloadState) {
    return payloadState;
  }
  const sessionState = String(displayedSession?.finalization_state || "").trim();
  if (sessionState) {
    return sessionState;
  }
  if (preflight && typeof preflight === "object") {
    return preflight.finalization_ready ? "ready_to_finalize" : "blocked_word_pdf_export";
  }
  return "";
}

export function buildGmailBatchFinalizeSurfaceState({
  activeSessionOverride = null,
  drawerSource = "",
  activeSession = null,
  restoredCompletedSession = null,
  batchFinalizePreflight = null,
  batchFinalizeResult = null,
  batchFinalizePreflightInFlight = false,
} = {}) {
  const displayedSession = selectGmailDisplayedBatchFinalizeSession({
    drawerSource,
    activeSession,
    restoredCompletedSession,
  });
  const preflight = selectGmailBatchFinalizePreflight({
    drawerSource,
    batchFinalizePreflight,
    displayedSession,
  });
  return {
    session: activeSessionOverride || displayedSession,
    recoveredOnly: drawerSource === "restored",
    preflight,
    payload: batchFinalizeResult || null,
    finalizationState: deriveGmailBatchFinalizeState({
      payload: batchFinalizeResult,
      displayedSession,
      preflight,
    }),
    preflightInFlight: Boolean(batchFinalizePreflightInFlight),
  };
}
