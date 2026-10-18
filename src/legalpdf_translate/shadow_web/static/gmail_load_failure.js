const LOAD_FAILURE_MESSAGE = "Gmail message could not be loaded. Open Advanced message details to review the message and try again.";
const RECONNECT_MESSAGE = "Gmail access has expired or was revoked. Reconnect your Gmail account, then load this message again.";

export function gmailLoadFailureMessage(loadResult = null) {
  const reason = String(loadResult?.status_message || "").trim();
  if (/invalid_grant|token has been expired or revoked|token (?:has )?expired|token (?:has been )?revoked/i.test(reason)) {
    return RECONNECT_MESSAGE;
  }
  // Helper transport responses belong in technical diagnostics, not the main status.
  if (!reason || reason.length > 400 || /[\r\n]|^\s*[{[]|https?:\/\/|oauth2?:/i.test(reason)) {
    return LOAD_FAILURE_MESSAGE;
  }
  return reason;
}

export function gmailFailedLoadPayload(error) {
  const payload = error?.payload;
  // Recover only the known application load outcome. HTTP/transport failures still throw.
  return error?.status === 200 && payload?.status === "failed"
    && payload?.normalized_payload?.load_result?.ok === false
    ? payload
    : null;
}
