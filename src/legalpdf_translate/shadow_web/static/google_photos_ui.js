export const googlePhotosUiState = {
  status: null,
  sessionId: "",
  selectedItems: [],
  connectPollTimedOut: false,
  authUrl: "",
  pickerUrl: "",
  disablePickerAutocloseOnce: false,
  pickerDiagnostics: null,
};

export const GOOGLE_PHOTOS_RECONNECT_GUIDANCE = "Google Photos could not add the selected photo. Reconnect Google Photos, then choose the image again. Make sure the Picker tab uses the same Google account.";

const GOOGLE_PHOTOS_PICKER_FAILURE_CATEGORIES = new Set([
  "picker_account_mismatch_possible",
  "picker_stale_session_possible",
  "picker_uri_not_opened",
  "picker_user_did_not_click_done",
  "picker_done_but_media_items_set_false",
  "picker_reconnect_to_partner_app",
  "picker_timeout",
  "picker_unknown",
]);

function qs(id) {
  return globalThis.document?.getElementById(id) || null;
}

function safeGooglePhotosPickerFailureCategory(value = "") {
  const cleaned = String(value || "").trim();
  return GOOGLE_PHOTOS_PICKER_FAILURE_CATEGORIES.has(cleaned) ? cleaned : "picker_unknown";
}

function googlePhotosBlockerCategory(value = "") {
  const cleaned = String(value || "").trim();
  if (cleaned === "reconnect_to_partner_app") {
    return "picker_reconnect_to_partner_app";
  }
  if (cleaned === "could_not_add_photos") {
    return "picker_done_but_media_items_set_false";
  }
  return "picker_unknown";
}

export function buildGooglePhotosPickerDiagnostics(updates = {}) {
  const googleUiBlockerCategory = String(updates.google_ui_blocker_category || "").trim();
  const inferredCategory = googleUiBlockerCategory
    ? googlePhotosBlockerCategory(googleUiBlockerCategory)
    : updates.safe_failure_category;
  return {
    picker_session_created: Boolean(updates.picker_session_created),
    picker_fallback_visible: Boolean(updates.picker_fallback_visible),
    picker_fallback_clicked: Boolean(updates.picker_fallback_clicked),
    user_selected_one_photo: Boolean(updates.user_selected_one_photo),
    user_clicked_done: Boolean(updates.user_clicked_done),
    google_ui_blocker_seen: Boolean(updates.google_ui_blocker_seen),
    google_ui_blocker_category: googleUiBlockerCategory || "unknown",
    media_items_set_observed: Boolean(updates.media_items_set_observed),
    media_items_list_called: Boolean(updates.media_items_list_called),
    import_route_called: Boolean(updates.import_route_called),
    picker_session_deleted: Boolean(updates.picker_session_deleted),
    stale_picker_uri_possible: Boolean(updates.stale_picker_uri_possible),
    safe_failure_category: safeGooglePhotosPickerFailureCategory(inferredCategory),
  };
}

export function updateGooglePhotosPickerDiagnostics(updates = {}) {
  googlePhotosUiState.pickerDiagnostics = buildGooglePhotosPickerDiagnostics({
    ...(googlePhotosUiState.pickerDiagnostics || {}),
    ...updates,
  });
  return googlePhotosUiState.pickerDiagnostics;
}

export function resetGooglePhotosPickerState({ clearAuth = true, sessionDeleted = false } = {}) {
  googlePhotosUiState.sessionId = "";
  googlePhotosUiState.selectedItems = [];
  googlePhotosUiState.pickerUrl = "";
  googlePhotosUiState.disablePickerAutocloseOnce = false;
  googlePhotosUiState.pickerDiagnostics = buildGooglePhotosPickerDiagnostics({
    picker_session_deleted: sessionDeleted,
    stale_picker_uri_possible: false,
  });
  setGooglePhotosPickerFallback("", { visible: false });
  if (clearAuth) {
    googlePhotosUiState.authUrl = "";
    setGooglePhotosAuthFallback("", { visible: false });
  }
}

export function googlePhotosUiSafeSnapshot() {
  return {
    hasSessionId: Boolean(googlePhotosUiState.sessionId),
    selectedItemCount: googlePhotosUiState.selectedItems.length,
    hasAuthUrl: Boolean(googlePhotosUiState.authUrl),
    hasPickerUrl: Boolean(googlePhotosUiState.pickerUrl),
    pickerDiagnostics: googlePhotosUiState.pickerDiagnostics || buildGooglePhotosPickerDiagnostics(),
  };
}

export function setGooglePhotosPickerAutocloseDisabledForNextLaunch(disabled = true) {
  googlePhotosUiState.disablePickerAutocloseOnce = Boolean(disabled);
}

export function googlePhotosStatusMessage(status = {}) {
  if (status.connected) {
    return "Google Photos connected. Choose a photo to recover Interpretation metadata.";
  }
  if (googlePhotosUiState.authUrl && status.client_id_configured && status.client_secret_env_configured) {
    return "Google sign-in is ready. If no Google tab opened, click Open Google sign-in.";
  }
  if (status.reason === "token_expired_reconnect_required") {
    return "Google Photos authorization expired. Connect Google Photos again before choosing a photo.";
  }
  if (!status.client_id_configured) {
    return "Google Photos is not configured. Add a client ID setting or environment variable before connecting.";
  }
  if (!status.client_secret_env_configured) {
    return `Google Photos needs the ${status.client_secret_env_name || "client secret"} environment variable before connecting.`;
  }
  return "Google Photos is configured. Connect before choosing a photo.";
}

export function setGooglePhotosAuthFallback(authUrl = "", { visible = false } = {}) {
  const fallback = qs("google-photos-open-signin");
  const cleanedUrl = String(authUrl || "").trim();
  googlePhotosUiState.authUrl = visible && cleanedUrl ? cleanedUrl : "";
  if (!fallback) {
    return;
  }
  if (visible && cleanedUrl) {
    fallback.href = cleanedUrl;
    fallback.classList.remove("hidden");
    fallback.setAttribute("aria-hidden", "false");
    fallback.tabIndex = 0;
  } else {
    fallback.removeAttribute("href");
    fallback.classList.add("hidden");
    fallback.setAttribute("aria-hidden", "true");
    fallback.tabIndex = -1;
  }
}

export function googlePhotosPickerBrowserUrl(pickerUri = "", { autoclose = true } = {}) {
  const cleanedUrl = String(pickerUri || "").trim();
  if (!cleanedUrl) {
    return "";
  }
  if (!autoclose) {
    return cleanedUrl;
  }
  try {
    const parsed = new URL(cleanedUrl);
    const normalizedPath = parsed.pathname.replace(/\/+$/, "");
    if (!normalizedPath.endsWith("/autoclose")) {
      parsed.pathname = `${normalizedPath}/autoclose`;
    }
    return parsed.toString();
  } catch {
    return cleanedUrl.endsWith("/autoclose") ? cleanedUrl : `${cleanedUrl.replace(/\/+$/, "")}/autoclose`;
  }
}

export function setGooglePhotosPickerFallback(pickerUri = "", { visible = false } = {}) {
  const fallback = qs("google-photos-open-picker");
  const browserUrl = googlePhotosPickerBrowserUrl(pickerUri, { autoclose: !googlePhotosUiState.disablePickerAutocloseOnce });
  googlePhotosUiState.pickerUrl = visible && browserUrl ? browserUrl : "";
  updateGooglePhotosPickerDiagnostics({
    picker_fallback_visible: Boolean(visible && browserUrl),
    stale_picker_uri_possible: false,
  });
  if (visible && browserUrl) {
    googlePhotosUiState.disablePickerAutocloseOnce = false;
  }
  if (!fallback) {
    return;
  }
  if (visible && browserUrl) {
    fallback.href = browserUrl;
    fallback.classList.remove("hidden");
    fallback.setAttribute("aria-hidden", "false");
    fallback.tabIndex = 0;
  } else {
    fallback.removeAttribute("href");
    fallback.classList.add("hidden");
    fallback.setAttribute("aria-hidden", "true");
    fallback.tabIndex = -1;
  }
}

export function renderGooglePhotosStatus(status = {}) {
  googlePhotosUiState.status = status;
  if (status.connected || !status.client_id_configured || !status.client_secret_env_configured) {
    setGooglePhotosAuthFallback("", { visible: false });
  }
  if (!status.connected) {
    setGooglePhotosPickerFallback("", { visible: false });
  }
  const statusNode = qs("google-photos-status");
  if (statusNode) {
    statusNode.textContent = googlePhotosStatusMessage(status);
    statusNode.dataset.tone = status.connected ? "ok" : status.configured ? "warn" : "bad";
  }
  const connectButton = qs("google-photos-connect");
  if (connectButton) {
    connectButton.disabled = !status.client_id_configured || !status.client_secret_env_configured;
    connectButton.textContent = status.connected ? "Reconnect Google Photos" : "Connect Google Photos";
  }
  const chooseButton = qs("google-photos-choose");
  if (chooseButton) {
    chooseButton.disabled = !status.connected;
  }
}
