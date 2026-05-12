function normalizeText(value) {
  return String(value ?? "").trim();
}

function normalizePositiveInteger(value) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 0;
}

function defaultClientGmailHandoffState({ workspaceId = "" } = {}) {
  return normalizeText(workspaceId) === "gmail-intake" ? "warming" : "idle";
}

function selectGmailPayload(payload) {
  return payload?.gmail || payload || {};
}

export function deriveClientLaunchSessionUrlState({ href = "" } = {}) {
  try {
    const params = new URL(normalizeText(href)).searchParams;
    return {
      launchSessionId: normalizeText(params.get("launch_session_id")),
      handoffSessionId: normalizeText(params.get("handoff_session_id")),
      launchSessionSchemaVersion: normalizePositiveInteger(params.get("launch_session_schema_version")),
    };
  } catch (_error) {
    return {
      launchSessionId: "",
      handoffSessionId: "",
      launchSessionSchemaVersion: 0,
    };
  }
}

export function deriveClientGmailHandoffState({ payload = null, workspaceId = "" } = {}) {
  const gmailPayload = selectGmailPayload(payload);
  const loadResult = gmailPayload.load_result || {};
  const pendingStatus = deriveGmailPendingStatus({ bootstrap: gmailPayload });
  if (gmailPayload.pending_review_open && pendingStatus !== "") {
    return pendingStatus;
  }
  if (loadResult.ok === true) {
    return "loaded";
  }
  if (loadResult.ok === false) {
    return "load_failed";
  }
  return defaultClientGmailHandoffState({ workspaceId });
}

export function deriveClientLaunchSessionId({ payload = null, href = "", urlState = null } = {}) {
  const shellLaunchSession = payload?.shell?.launch_session || {};
  const runtimeLaunchSession = payload?.runtime?.launch_session || {};
  const nextUrlState = urlState || deriveClientLaunchSessionUrlState({ href });
  return normalizeText(
    nextUrlState.launchSessionId
    || shellLaunchSession.launch_session_id
    || runtimeLaunchSession.launch_session_id
    || "",
  );
}

export function deriveClientHandoffSessionId({ payload = null, href = "", urlState = null } = {}) {
  const gmailPayload = selectGmailPayload(payload);
  const shellLaunchSession = payload?.shell?.launch_session || {};
  const runtimeLaunchSession = payload?.runtime?.launch_session || {};
  const nextUrlState = urlState || deriveClientLaunchSessionUrlState({ href });
  return normalizeText(
    nextUrlState.handoffSessionId
    || gmailPayload.handoff_session_id
    || shellLaunchSession.handoff_session_id
    || runtimeLaunchSession.handoff_session_id
    || "",
  );
}

export function deriveClientLaunchSessionSchemaVersion({ payload = null, href = "", urlState = null } = {}) {
  const nextUrlState = urlState || deriveClientLaunchSessionUrlState({ href });
  if (nextUrlState.launchSessionSchemaVersion > 0) {
    return nextUrlState.launchSessionSchemaVersion;
  }
  return normalizePositiveInteger(payload?.shell?.extension_launch_session_schema_version);
}

export function deriveGmailBootstrapMessageContext({ bootstrap = null } = {}) {
  return bootstrap?.defaults?.message_context || {};
}

export function deriveGmailPendingIntakeContext({ bootstrap = null } = {}) {
  return bootstrap?.pending_intake_context || {};
}

export function deriveGmailClickDiagnostics({ bootstrap = null } = {}) {
  return bootstrap?.click_diagnostics || {};
}

export function deriveGmailPendingStatus({ bootstrap = null } = {}) {
  return normalizeText(bootstrap?.pending_status).toLowerCase();
}

export function deriveGmailPendingReviewOpen({ bootstrap = null } = {}) {
  return bootstrap?.pending_review_open === true;
}

export function deriveGmailSourceUrl({
  sourceUrl = "",
  currentHandoffContext = null,
  current_handoff_context = null,
  defaults = null,
  pendingIntakeContext = null,
  pending_intake_context = null,
  clickDiagnostics = null,
  click_diagnostics = null,
} = {}) {
  const handoffContext = currentHandoffContext || current_handoff_context;
  const pendingContext = pendingIntakeContext || pending_intake_context;
  const diagnostics = clickDiagnostics || click_diagnostics;
  return normalizeText(
    sourceUrl
    || handoffContext?.source_gmail_url
    || defaults?.message_context?.source_gmail_url
    || pendingContext?.source_gmail_url
    || diagnostics?.source_gmail_url
    || "",
  );
}
