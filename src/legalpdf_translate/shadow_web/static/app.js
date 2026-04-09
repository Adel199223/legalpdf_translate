import { describeLocalServerUnavailable, fetchJson, isLocalServerUnavailableError } from "./api.js";
import { runStagedBootstrap } from "./bootstrap_hydration.js";
import {
  appState,
  initializeRouteState,
  routeShellMode,
  setActiveView,
  setOperatorMode,
  setRuntimeMode,
  syncActiveViewFromLocation,
} from "./state.js";
import {
  initializeTranslationUi,
  loadTranslationHistoryItem,
  openTranslationCompletionDrawer,
  refreshTranslationHistory,
  applyTranslationLaunch,
  closeTranslationCompletionDrawer,
  collectCurrentTranslationSaveValues,
  getTranslationUiSnapshot,
  getCurrentTranslationJobId,
  resetTranslationForGmailRedo,
  renderTranslationBootstrap,
  startTranslationLaunch,
} from "./translation.js";
import { closeSessionDrawer, initializeGmailUi, renderGmailBootstrap } from "./gmail.js";
import { initializePowerToolsUi, renderPowerToolsBootstrap } from "./power-tools.js";
import {
  buildInterpretationReference,
  deriveInterpretationDrawerLayout,
  deriveInterpretationGuardState,
  deriveInterpretationWorkspaceMode,
  normalizeCityName,
  resolveKnownCity,
} from "./interpretation_review_state.js";

function qs(id) {
  return document.getElementById(id);
}

function qsa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

function chipToneClass(status) {
  if (status === "ok") {
    return "ok";
  }
  if (status === "bad") {
    return "bad";
  }
  if (status === "info") {
    return "info";
  }
  return "warn";
}

const profileState = {
  currentProfileId: "",
};

const profileUiState = {
  editorDrawerOpen: false,
};

const interpretationUiState = {
  reviewDrawerOpen: false,
  validationField: "",
  completionPayload: null,
};

const interpretationCityState = {
  provisionalCities: {
    case_city: "",
    service_city: "",
  },
  dialogOpen: false,
  dialogResolver: null,
  activeDialog: {
    mode: "add",
    fieldName: "service_city",
    requireDistance: false,
  },
  autoDistanceCity: "",
  manualDistance: false,
};

const shellUiState = {
  gmailFocusActive: false,
};
const clientHydrationState = {
  status: "warming",
  bootstrappedAt: null,
  reason: "",
  message: "",
};

let lastInterpretationUiSnapshotKey = "";

function interpretationUiSnapshotKey() {
  return JSON.stringify(getInterpretationUiSnapshot());
}

function notifyInterpretationUiStateChanged({ force = false } = {}) {
  const nextKey = interpretationUiSnapshotKey();
  if (!force && nextKey === lastInterpretationUiSnapshotKey) {
    return;
  }
  lastInterpretationUiSnapshotKey = nextKey;
  window.dispatchEvent(new CustomEvent("legalpdf:interpretation-ui-state-changed"));
}

const PRIMARY_NAV_ORDER = ["new-job", "gmail-intake", "recent-jobs"];
const MORE_NAV_ORDER = ["dashboard", "settings", "profile", "power-tools", "extension-lab"];

function formatDiagnosticValue(value) {
  if (value instanceof Error) {
    const payload = { status: "failed", message: value.message || "Unexpected error." };
    if (value.status) {
      payload.http_status = value.status;
    }
    if (value.payload && Object.keys(value.payload).length) {
      payload.payload = value.payload;
    }
    return JSON.stringify(payload, null, 2);
  }
  if (typeof value === "string") {
    return value;
  }
  if (value === undefined || value === null) {
    return "";
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function setDiagnostics(slot, value, { hint = "", open = false } = {}) {
  const pre = qs(`${slot}-diagnostics`);
  if (pre) {
    pre.textContent = formatDiagnosticValue(value);
  }
  const hintNode = qs(`${slot}-hint`);
  if (hintNode && hint) {
    hintNode.textContent = hint;
  }
  const details = qs(`${slot}-details`);
  if (details) {
    details.open = Boolean(open);
    if (open) {
      details.dataset.reveal = "true";
    } else {
      delete details.dataset.reveal;
    }
  }
}

function setPanelStatus(slot, tone, message) {
  const panel = qs(`${slot}-status`);
  if (!panel) {
    return;
  }
  panel.textContent = message;
  if (tone) {
    panel.dataset.tone = tone;
  } else {
    delete panel.dataset.tone;
  }
}

function setTopbarStatus(message, tone) {
  const panel = qs("topbar-status");
  if (!panel) {
    return;
  }
  panel.textContent = message;
  if (tone) {
    panel.dataset.tone = tone;
  } else {
    delete panel.dataset.tone;
  }
}

function currentBuildSha() {
  return String(globalThis.window?.LEGALPDF_BROWSER_BOOTSTRAP?.buildSha || "").trim();
}

function currentAssetVersion() {
  return String(globalThis.window?.LEGALPDF_BROWSER_BOOTSTRAP?.assetVersion || "").trim();
}

function serverAssetVersionFromPayload(payload) {
  return String(
    payload?.normalized_payload?.shell?.asset_version
    || payload?.normalized_payload?.runtime?.asset_version
    || "",
  ).trim();
}

function assertServerAssetVersionMatchesClient(payload) {
  const clientAssetVersion = currentAssetVersion();
  const serverAssetVersion = serverAssetVersionFromPayload(payload);
  if (clientAssetVersion === "" || serverAssetVersion === "" || clientAssetVersion === serverAssetVersion) {
    return;
  }
  const error = new Error(
    "This LegalPDF browser tab is using stale browser assets. Reload the tab once to pick up the current local build.",
  );
  error.name = "StaleBrowserAssetsError";
  error.payload = {
    status: "failed",
    diagnostics: {
      error: "stale_browser_assets",
      message: error.message,
      client_asset_version: clientAssetVersion,
      server_asset_version: serverAssetVersion,
      build_sha: currentBuildSha(),
    },
  };
  throw error;
}

function defaultClientGmailHandoffState() {
  return appState.workspaceId === "gmail-intake" ? "warming" : "idle";
}

function deriveClientGmailHandoffState(payload = appState.bootstrap?.normalized_payload) {
  const gmailPayload = payload?.gmail || {};
  const loadResult = gmailPayload.load_result || {};
  const pendingStatus = String(gmailPayload.pending_status || "").trim().toLowerCase();
  if (gmailPayload.pending_review_open && pendingStatus !== "") {
    return pendingStatus;
  }
  if (loadResult.ok === true) {
    return "loaded";
  }
  if (loadResult.ok === false) {
    return "load_failed";
  }
  return defaultClientGmailHandoffState();
}

function deriveClientLaunchSessionId(payload = appState.bootstrap?.normalized_payload) {
  const shellLaunchSession = payload?.shell?.launch_session || {};
  const runtimeLaunchSession = payload?.runtime?.launch_session || {};
  return String(
    shellLaunchSession.launch_session_id
    || runtimeLaunchSession.launch_session_id
    || "",
  ).trim();
}

function deriveClientHandoffSessionId(payload = appState.bootstrap?.normalized_payload) {
  const gmailPayload = payload?.gmail || payload || {};
  const shellLaunchSession = payload?.shell?.launch_session || {};
  const runtimeLaunchSession = payload?.runtime?.launch_session || {};
  return String(
    gmailPayload.handoff_session_id
    || shellLaunchSession.handoff_session_id
    || runtimeLaunchSession.handoff_session_id
    || "",
  ).trim();
}

function deriveClientLaunchSessionSchemaVersion(payload = appState.bootstrap?.normalized_payload) {
  const rawValue = payload?.shell?.extension_launch_session_schema_version;
  const parsed = Number.parseInt(String(rawValue ?? ""), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 0;
}

function setClientHydrationMarker(status, { payload = null, reason = "", message = "" } = {}) {
  const nextStatus = String(status || "warming").trim() || "warming";
  const nextBootstrappedAt = nextStatus === "ready"
    ? (clientHydrationState.status === "ready" && clientHydrationState.bootstrappedAt
      ? clientHydrationState.bootstrappedAt
      : new Date().toISOString())
    : null;
  const marker = {
    status: nextStatus,
    workspaceId: String(appState.workspaceId || "workspace-1"),
    runtimeMode: String(appState.runtimeMode || "shadow"),
    activeView: String(appState.activeView || ""),
    gmailHandoffState: deriveClientGmailHandoffState(payload || appState.bootstrap?.normalized_payload),
    buildSha: currentBuildSha(),
    assetVersion: currentAssetVersion(),
    launchSessionId: deriveClientLaunchSessionId(payload || appState.bootstrap?.normalized_payload),
    handoffSessionId: deriveClientHandoffSessionId(payload || appState.bootstrap?.normalized_payload),
    launchSessionSchemaVersion: deriveClientLaunchSessionSchemaVersion(payload || appState.bootstrap?.normalized_payload),
    bootstrappedAt: nextBootstrappedAt,
  };
  if (reason) {
    marker.reason = String(reason);
  }
  if (message) {
    marker.message = String(message);
  }
  clientHydrationState.status = marker.status;
  clientHydrationState.bootstrappedAt = marker.bootstrappedAt;
  clientHydrationState.reason = marker.reason || "";
  clientHydrationState.message = marker.message || "";
  if (globalThis.document?.body?.dataset) {
    document.body.dataset.clientReady = marker.status;
    document.body.dataset.clientWorkspace = marker.workspaceId;
    document.body.dataset.clientRuntimeMode = marker.runtimeMode;
    document.body.dataset.clientActiveView = marker.activeView;
    document.body.dataset.clientBuildSha = marker.buildSha;
    document.body.dataset.clientAssetVersion = marker.assetVersion;
    document.body.dataset.clientLaunchSession = marker.launchSessionId || "";
    document.body.dataset.clientHandoffSession = marker.handoffSessionId || "";
    document.body.dataset.clientLaunchSessionSchemaVersion = String(marker.launchSessionSchemaVersion || 0);
  }
  if (globalThis.window) {
    globalThis.window.LEGALPDF_BROWSER_CLIENT_READY = marker;
  }
  return marker;
}

function syncClientHydrationMarker({ payload = null } = {}) {
  return setClientHydrationMarker(clientHydrationState.status || "warming", {
    payload,
    reason: clientHydrationState.reason,
    message: clientHydrationState.message,
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderRecoveryResult(containerId, details) {
  const container = qs(containerId);
  if (!container) {
    return;
  }
  container.classList.remove("empty-state");
  const steps = details.recoverySteps
    .map((step) => `<li>${escapeHtml(step)}</li>`)
    .join("");
  container.innerHTML = `
    <div class="result-header">
      <div><strong>${escapeHtml(details.title)}</strong></div>
      <span class="status-chip bad">Unavailable</span>
    </div>
    <div class="result-grid">
      <div>
        <h3>Listener</h3>
        <p class="word-break">${escapeHtml(`${details.host}:${details.port}`)}</p>
      </div>
      <div>
        <h3>Recommended URL</h3>
        <p class="word-break">${escapeHtml(details.recommendedUrl)}</p>
      </div>
      <div>
        <h3>Launcher</h3>
        <p class="word-break">${escapeHtml(details.launcherCommand)}</p>
      </div>
    </div>
    <div>
      <h3>Recovery</h3>
      <ul>${steps}</ul>
    </div>
  `;
}

function applyBootstrapFailureState(error) {
  setClientHydrationMarker("client_boot_failed", {
    reason: error?.payload?.diagnostics?.error || error?.name || "bootstrap_failed",
    message: error?.message || "Browser app bootstrap failed.",
  });
  if (error?.payload?.diagnostics?.error === "stale_browser_assets") {
    setTopbarStatus(error.message || "This LegalPDF browser tab is using stale browser assets.", "bad");
    setPanelStatus(
      "runtime",
      "bad",
      error.message || "This LegalPDF browser tab is using stale browser assets.",
    );
    setDiagnostics("runtime", error, {
      hint: "The tab loaded an older browser asset version than the live server expects. Reload the LegalPDF tab once to pick up the current local build.",
      open: true,
    });
    return;
  }
  if (isLocalServerUnavailableError(error)) {
    const details = describeLocalServerUnavailable(error);
    qs("workspace-id-label").textContent = details.workspaceId;
    qs("runtime-mode-label").textContent = details.port === 8888
      ? "Fixed Review Preview"
      : (details.runtimeMode === "live" ? "Live App Data" : "Isolated Test Data");
    setTopbarStatus(details.statusMessage, "bad");
    const banner = qs("live-banner");
    banner.classList.add("hidden");
    banner.textContent = "";
    setPanelStatus("runtime", "bad", details.message);
    setPanelStatus("parity-audit", "bad", details.statusMessage);
    setPanelStatus("translation", "bad", details.message);
    setPanelStatus("gmail", "bad", details.message);
    setDiagnostics("runtime", error, { hint: details.diagnosticsHint, open: true });
    renderRecoveryResult("parity-audit-result", details);
    renderRecoveryResult("translation-result", details);
    renderRecoveryResult("gmail-message-result", details);
    renderRecoveryResult("gmail-session-result", details);
    return;
  }
  setTopbarStatus(error.message || "Browser app bootstrap failed.", "bad");
  setPanelStatus("runtime", "bad", error.message || "Browser app bootstrap failed.");
  setDiagnostics("runtime", error, { hint: error.message || "Browser app bootstrap failed.", open: true });
}

function fieldValue(id) {
  return qs(id).value.trim();
}

function setFieldValue(id, value) {
  qs(id).value = value ?? "";
}

function setCheckbox(id, value) {
  qs(id).checked = Boolean(value);
}

function profileSummaries() {
  return appState.bootstrap?.normalized_payload?.profiles || [];
}

function currentInterpretationReference() {
  return buildInterpretationReference(
    appState.bootstrap?.normalized_payload?.interpretation_reference || {},
    profileSummaries(),
    qs("profile-id")?.value || "",
  );
}

function interpretationFieldId(fieldName) {
  return fieldName === "service_city" ? "service-city" : "case-city";
}

function interpretationCityAddButtonId(fieldName) {
  return fieldName === "service_city" ? "service-city-add" : "case-city-add";
}

function interpretationCityWarningId(fieldName) {
  return fieldName === "service_city" ? "service-city-warning" : "case-city-warning";
}

function provisionalCityValue(fieldName) {
  return interpretationCityState.provisionalCities[fieldName] || "";
}

function setProvisionalCityValue(fieldName, value) {
  interpretationCityState.provisionalCities[fieldName] = normalizeCityName(value);
}

function displayedInterpretationCity(fieldName) {
  return fieldValue(interpretationFieldId(fieldName)) || provisionalCityValue(fieldName);
}

function populateInterpretationCitySelect(fieldName, selectedValue = "") {
  const select = qs(interpretationFieldId(fieldName));
  if (!select) {
    return;
  }
  const reference = currentInterpretationReference();
  const currentValue = resolveKnownCity(selectedValue || select.value, reference.availableCities);
  select.innerHTML = "";
  const placeholder = document.createElement("option");
  placeholder.value = "";
  placeholder.textContent = "Select a city";
  select.appendChild(placeholder);
  for (const city of reference.availableCities) {
    const option = document.createElement("option");
    option.value = city;
    option.textContent = city;
    select.appendChild(option);
  }
  select.value = currentValue || "";
}

function refreshInterpretationCitySelectors() {
  populateInterpretationCitySelect("case_city", fieldValue("case-city"));
  populateInterpretationCitySelect("service_city", fieldValue("service-city"));
}

function normalizedField(value) {
  return String(value ?? "").trim().toLocaleLowerCase();
}

function inferServiceSame(caseEntity, caseCity, serviceEntity, serviceCity) {
  const normalizedServiceEntity = normalizedField(serviceEntity);
  const normalizedServiceCity = normalizedField(serviceCity);
  if (!normalizedServiceEntity && !normalizedServiceCity) {
    return true;
  }
  return normalizedField(caseEntity) === normalizedServiceEntity && normalizedField(caseCity) === normalizedServiceCity;
}

function syncServiceFieldsFromCase() {
  if (!qs("service-same").checked) {
    return;
  }
  setFieldValue("service-entity", fieldValue("case-entity"));
  setFieldValue("service-city", fieldValue("case-city"));
  setProvisionalCityValue("service_city", provisionalCityValue("case_city"));
}

function setDisclosureState(id, expanded, summaryText = "") {
  const details = qs(id);
  if (details) {
    details.open = Boolean(expanded);
  }
  const summaryNode = qs(`${id}-summary`);
  if (summaryNode) {
    summaryNode.textContent = summaryText;
  }
}

function syncInterpretationDisclosureState() {
  const serviceSame = qs("service-same")?.checked ?? true;
  const drawerLayout = deriveInterpretationDrawerLayout({
    workspaceMode: interpretationWorkspaceMode(),
    activeSession: interpretationActiveSession(),
    serviceSame,
    validationField: interpretationUiState.validationField,
  });
  setDisclosureState(
    "interpretation-service-section",
    drawerLayout.sections.serviceOpen,
    serviceSame ? "Same as case" : "Custom service details",
  );
  const useServiceLocation = qs("use-service-location")?.checked ?? false;
  const includeTransport = qs("include-transport")?.checked ?? true;
  const travelDistance = fieldValue("travel-km-outbound");
  const outputFilename = fieldValue("output-filename");
  const textCustomized = Boolean(useServiceLocation || !includeTransport || travelDistance || outputFilename);
  setDisclosureState(
    "interpretation-text-section",
    drawerLayout.sections.textOpen,
    textCustomized ? "Custom wording or export detail ready" : "Review wording and filename before you finalize",
  );
  const recipientOverride = fieldValue("recipient-block");
  setDisclosureState(
    "interpretation-recipient-section",
    drawerLayout.sections.recipientOpen,
    recipientOverride ? "Custom recipient override ready" : "Auto-derived recipient",
  );
  const amountsTouched = Boolean(
    fieldValue("pages")
    || fieldValue("word-count")
    || fieldValue("rate-per-word")
    || fieldValue("expected-total")
    || fieldValue("amount-paid")
    || fieldValue("api-cost")
    || fieldValue("profit"),
  );
  const amountsSummary = amountsTouched
    ? "Metrics and pricing are ready for final review"
    : "Pages, words, rate, totals, API-cost, and profit stay tucked away until final review";
  const amountsSummaryNode = qs("interpretation-amounts-section-summary");
  if (amountsSummaryNode) {
    amountsSummaryNode.textContent = amountsSummary;
  }
  const amountsSection = qs("interpretation-amounts-section");
  if (amountsSection) {
    amountsSection.open = drawerLayout.sections.amountsOpen;
  }
}

function interpretationActiveSession() {
  return appState.bootstrap?.normalized_payload?.gmail?.active_session || null;
}

function interpretationNoticeFilename(activeSession = interpretationActiveSession()) {
  return String(
    activeSession?.attachment?.attachment?.filename
    || activeSession?.attachment?.filename
    || activeSession?.current_attachment?.attachment?.filename
    || ""
  ).trim();
}

function interpretationSnapshot() {
  return {
    rowId: String(appState.currentRowId || "").trim(),
    caseNumber: fieldValue("case-number"),
    courtEmail: fieldValue("court-email"),
    caseEntity: fieldValue("case-entity"),
    caseCity: displayedInterpretationCity("case_city"),
    serviceEntity: fieldValue("service-entity"),
    serviceCity: displayedInterpretationCity("service_city"),
    serviceSame: qs("service-same")?.checked ?? true,
    serviceDate: fieldValue("service-date"),
    travelKmOutbound: fieldValue("travel-km-outbound"),
    pages: fieldValue("pages"),
    wordCount: fieldValue("word-count"),
  };
}

function interpretationCaseLocation(snapshot = interpretationSnapshot()) {
  return [snapshot.caseEntity, snapshot.caseCity].filter(Boolean).join(" | ") || "Not set yet";
}

function interpretationServiceLocation(snapshot = interpretationSnapshot()) {
  if (snapshot.serviceSame) {
    return interpretationCaseLocation(snapshot);
  }
  return [snapshot.serviceEntity, snapshot.serviceCity].filter(Boolean).join(" | ") || "Not set yet";
}

function interpretationLocationSummary(snapshot = interpretationSnapshot()) {
  const caseLocation = interpretationCaseLocation(snapshot);
  if (!snapshot.serviceSame) {
    return interpretationServiceLocation(snapshot) || caseLocation || "Not set yet";
  }
  return caseLocation || "Not set yet";
}

function interpretationWorkspaceMode(snapshot = interpretationSnapshot(), activeSession = interpretationActiveSession()) {
  return deriveInterpretationWorkspaceMode({
    snapshot,
    activeSession,
    hasCompletionPayload: Boolean(interpretationUiState.completionPayload),
  });
}

function currentInterpretationGuardState() {
  return deriveInterpretationGuardState({
    reference: currentInterpretationReference(),
    caseCity: fieldValue("case-city"),
    serviceCity: fieldValue("service-city"),
    serviceSame: qs("service-same")?.checked ?? true,
    provisionalCaseCity: provisionalCityValue("case_city"),
    provisionalServiceCity: provisionalCityValue("service_city"),
    includeTransport: qs("include-transport")?.checked ?? true,
    travelKmOutbound: fieldValue("travel-km-outbound"),
  });
}

function hasMeaningfulInterpretationValue(value) {
  const normalized = String(value ?? "").trim();
  return Boolean(normalized && normalized !== "0" && normalized !== "0.0" && normalized !== "0.00");
}

function hasInterpretationReviewData(snapshot = interpretationSnapshot()) {
  return Boolean(
    snapshot.rowId
    || hasMeaningfulInterpretationValue(snapshot.caseNumber)
    || hasMeaningfulInterpretationValue(snapshot.courtEmail)
    || hasMeaningfulInterpretationValue(snapshot.caseEntity)
    || hasMeaningfulInterpretationValue(snapshot.caseCity)
    || hasMeaningfulInterpretationValue(snapshot.serviceDate)
    || hasMeaningfulInterpretationValue(snapshot.travelKmOutbound)
    || hasMeaningfulInterpretationValue(snapshot.pages)
    || hasMeaningfulInterpretationValue(snapshot.wordCount),
  );
}

function interpretationReviewButtonLabel(snapshot = interpretationSnapshot()) {
  if (snapshot.rowId) {
    return "Review Saved Row";
  }
  if (hasInterpretationReviewData(snapshot)) {
    return "Review Interpretation";
  }
  return "Start Blank Review";
}

function interpretationSessionChip(session, mode, completionPayload = interpretationUiState.completionPayload) {
  const status = String(session?.status || "").trim();
  if (mode === "gmail_completed") {
    const completionStatus = String(completionPayload?.status || "").trim();
    if (completionStatus === "ok") {
      return { tone: "ok", label: "Draft ready" };
    }
    if (completionStatus === "local_only") {
      return { tone: "warn", label: "Local only" };
    }
    if (completionStatus === "draft_unavailable") {
      return { tone: "warn", label: "Draft unavailable" };
    }
    if (completionStatus) {
      return { tone: "bad", label: "Needs review" };
    }
    if (session?.draft_created || status === "draft_ready") {
      return { tone: "ok", label: "Draft ready" };
    }
    if (String(session?.draft_failure_reason || "").trim() || status === "draft_failed") {
      return { tone: "bad", label: "Needs review" };
    }
    return { tone: "info", label: "Completed" };
  }
  if (status) {
    return { tone: "info", label: status.replaceAll("_", " ") };
  }
  return { tone: "info", label: "Prepared" };
}

function renderInterpretationSessionShell(snapshot = interpretationSnapshot()) {
  const shell = qs("interpretation-session-shell");
  const result = qs("interpretation-session-result");
  const statusNode = qs("interpretation-session-status");
  const primaryButton = qs("interpretation-session-primary");
  const activeSession = interpretationActiveSession();
  const mode = interpretationWorkspaceMode(snapshot, activeSession);
  const gmailModeActive = mode === "gmail_review" || mode === "gmail_completed";
  document.body.dataset.interpretationWorkspaceMode = mode;
  if (shell) {
    shell.classList.toggle("hidden", !gmailModeActive);
  }
  for (const id of ["interpretation-intake-panel", "interpretation-seed-panel", "interpretation-action-rail"]) {
    qs(id)?.classList.toggle("hidden", gmailModeActive);
  }
  if (!gmailModeActive || !result) {
    return;
  }
  const chip = interpretationSessionChip(activeSession, mode);
  const noticeFilename = interpretationNoticeFilename(activeSession) || "Notice PDF";
  const locationSummary = interpretationLocationSummary(snapshot);
  if (primaryButton) {
    primaryButton.textContent = mode === "gmail_completed" ? "View Final Result" : "Review Interpretation";
  }
  if (statusNode) {
    statusNode.textContent = mode === "gmail_completed"
      ? "The Gmail interpretation result is ready. Open the bounded review surface to inspect the draft and exported files."
      : "Keep this Gmail interpretation in one focused review surface. Resume the current step when you are ready.";
  }
  result.classList.remove("empty-state");
  result.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(mode === "gmail_completed" ? "Current interpretation result" : "Current interpretation step")}</strong>
        <p>${escapeHtml(noticeFilename)}</p>
      </div>
      <span class="status-chip ${chip.tone}">${escapeHtml(chip.label)}</span>
    </div>
    <div class="result-grid">
      <div><h3>Case Number</h3><p class="word-break">${escapeHtml(snapshot.caseNumber || "Not set yet")}</p></div>
      <div><h3>Court Email</h3><p class="word-break">${escapeHtml(snapshot.courtEmail || "Not set yet")}</p></div>
      <div><h3>Service Date</h3><p class="word-break">${escapeHtml(snapshot.serviceDate || "Not set yet")}</p></div>
      <div><h3>Location</h3><p class="word-break">${escapeHtml(locationSummary)}</p></div>
    </div>
  `;
}

function renderInterpretationSeedCard(containerId) {
  const container = qs(containerId);
  if (!container) {
    return;
  }
  const snapshot = interpretationSnapshot();
  const gmailSession = interpretationActiveSession();
  if (!hasInterpretationReviewData(snapshot)) {
    container.classList.add("empty-state");
    container.textContent = "Upload a notification PDF or screenshot to recover the case data, or start a blank review if you need to enter it manually.";
    return;
  }
  const title = snapshot.rowId
    ? `Saved interpretation row #${snapshot.rowId} is ready to review.`
    : "Recovered interpretation seed is ready to review.";
  const sessionLabel = gmailSession?.kind === "interpretation" ? "Gmail interpretation session active." : "Local interpretation review.";
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(title)}</strong>
        <p>${escapeHtml(sessionLabel)}</p>
      </div>
      <span class="status-chip ${snapshot.rowId ? "ok" : "info"}">${snapshot.rowId ? "Saved" : "Ready"}</span>
    </div>
    <div class="result-grid">
      <div><h3>Case</h3><p class="word-break">${escapeHtml(snapshot.caseNumber || "Not set yet")}</p></div>
      <div><h3>Court Email</h3><p class="word-break">${escapeHtml(snapshot.courtEmail || "Not set yet")}</p></div>
      <div><h3>Service Date</h3><p class="word-break">${escapeHtml(snapshot.serviceDate || "Not set yet")}</p></div>
      <div><h3>Location</h3><p class="word-break">${escapeHtml([snapshot.caseEntity, snapshot.caseCity].filter(Boolean).join(" | ") || "Not set yet")}</p></div>
    </div>
  `;
}

function renderInterpretationReviewSummary(snapshot = interpretationSnapshot()) {
  const container = qs("interpretation-review-summary-card");
  if (!container) {
    return;
  }
  const activeSession = interpretationActiveSession();
  const workspaceMode = interpretationWorkspaceMode(snapshot, activeSession);
  const noticeFilename = interpretationNoticeFilename(activeSession);
  if (!hasInterpretationReviewData(snapshot) && !noticeFilename) {
    container.classList.add("empty-state");
    container.textContent = "Recover the case data first, or start a blank review if you need to enter it manually.";
    return;
  }
  const chip = interpretationSessionChip(activeSession, workspaceMode);
  const title = activeSession?.kind === "interpretation"
    ? workspaceMode === "gmail_completed"
      ? "Gmail interpretation result is ready."
      : "Gmail interpretation notice is staged for review."
    : snapshot.rowId
      ? `Saved interpretation row #${snapshot.rowId} is ready to review.`
      : "Recovered interpretation seed is ready to review.";
  const subtitle = activeSession?.kind === "interpretation"
    ? workspaceMode === "gmail_completed"
      ? "The draft and exported files are ready to inspect from this same bounded surface."
      : noticeFilename || "Review the staged notice details and finish the Gmail step from this same surface."
    : noticeFilename || "Review the recovered interpretation details before you continue.";
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(title)}</strong>
        <p>${escapeHtml(subtitle)}</p>
      </div>
      <span class="status-chip ${chip.tone}">${escapeHtml(chip.label)}</span>
    </div>
    <div class="result-grid">
      <div><h3>Case Number</h3><p class="word-break">${escapeHtml(snapshot.caseNumber || "Not set yet")}</p></div>
      <div><h3>Court Email</h3><p class="word-break">${escapeHtml(snapshot.courtEmail || "Not set yet")}</p></div>
      <div><h3>Service Date</h3><p class="word-break">${escapeHtml(snapshot.serviceDate || "Not set yet")}</p></div>
      <div><h3>Location</h3><p class="word-break">${escapeHtml(interpretationLocationSummary(snapshot))}</p></div>
    </div>
  `;
}

function renderInterpretationReviewContext(snapshot = interpretationSnapshot()) {
  const container = qs("interpretation-review-context-card");
  const result = qs("interpretation-gmail-result");
  const titleNode = qs("interpretation-review-context-title");
  const copyNode = qs("interpretation-review-context-copy");
  const chipNode = qs("interpretation-review-context-chip");
  if (!container) {
    return;
  }
  const activeSession = interpretationActiveSession();
  const workspaceMode = interpretationWorkspaceMode(snapshot, activeSession);
  const reviewMode = workspaceMode === "gmail_review";
  container.classList.toggle("hidden", !reviewMode);
  if (!reviewMode) {
    return;
  }
  if (titleNode) {
    titleNode.textContent = "Keep the Gmail follow-up inside this review step.";
  }
  if (copyNode) {
    copyNode.textContent = "Review the notice details here, then finalize the Gmail reply from this same bounded surface.";
  }
  if (chipNode) {
    const chip = interpretationSessionChip(activeSession, workspaceMode);
    chipNode.className = `status-chip ${chip.tone}`;
    chipNode.textContent = chip.label;
  }
  if (result && result.classList.contains("empty-state")) {
    result.textContent = "Gmail draft and final attachment details appear here after finalization.";
  }
}

function syncInterpretationReviewDetailsShell(completed) {
  const details = qs("interpretation-review-details");
  if (!details) {
    return;
  }
  const summaryNode = qs("interpretation-review-details-summary");
  if (!completed) {
    details.open = true;
    delete details.dataset.autocollapsed;
    if (summaryNode) {
      summaryNode.textContent = "Case context and honorários controls are open";
    }
    return;
  }
  if (details.dataset.autocollapsed !== "done") {
    details.open = false;
    details.dataset.autocollapsed = "done";
  }
  if (summaryNode) {
    summaryNode.textContent = "Review details stay collapsed after finalization until you reopen them";
  }
}

function renderInterpretationCompletionCard(snapshot = interpretationSnapshot()) {
  const container = qs("interpretation-completion-card");
  if (!container) {
    return;
  }
  const activeSession = interpretationActiveSession();
  const workspaceMode = interpretationWorkspaceMode(snapshot, activeSession);
  const payload = interpretationUiState.completionPayload?.normalized_payload || {};
  const completed = workspaceMode === "gmail_completed";
  container.classList.toggle("hidden", !completed);
  syncInterpretationReviewDetailsShell(completed);
  if (!completed) {
    return;
  }
  const draftMessage = payload.gmail_draft_result?.message
    || payload.draft_prereqs?.message
    || activeSession?.draft_failure_reason
    || (activeSession?.draft_created ? "Gmail draft created successfully." : "Gmail finalization details are available.");
  const pdfPath = String(payload.pdf_path || payload.pdfPath || activeSession?.pdf_export?.pdf_path || activeSession?.pdf_export?.pdfPath || "").trim();
  const docxPath = String(payload.docx_path || payload.docxPath || "").trim();
  const chip = interpretationSessionChip(activeSession, workspaceMode);
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(draftMessage)}</strong>
        <p>${escapeHtml(interpretationNoticeFilename(activeSession) || "Notice PDF")}</p>
      </div>
      <span class="status-chip ${chip.tone}">${escapeHtml(chip.label)}</span>
    </div>
    <div class="result-grid">
      <div><h3>DOCX</h3><p class="word-break">${escapeHtml(docxPath || "Unavailable in this session view")}</p></div>
      <div><h3>PDF</h3><p class="word-break">${escapeHtml(pdfPath || "Unavailable")}</p></div>
      <div><h3>Case Location</h3><p class="word-break">${escapeHtml(interpretationCaseLocation(snapshot))}</p></div>
      <div><h3>Service Location</h3><p class="word-break">${escapeHtml(interpretationServiceLocation(snapshot))}</p></div>
    </div>
  `;
}

function setInterpretationFieldWarning(fieldName, message = "", tone = "warning") {
  const node = qs(interpretationCityWarningId(fieldName));
  if (!node) {
    return;
  }
  const text = String(message || "").trim();
  node.textContent = text;
  node.classList.toggle("hidden", !text);
  node.classList.toggle("is-warning", text && tone === "warning");
  node.classList.toggle("is-danger", text && tone === "danger");
}

function setInterpretationLocationGuard(message = "", tone = "warning") {
  const card = qs("interpretation-location-guard-card");
  if (!card) {
    return;
  }
  const text = String(message || "").trim();
  if (!text) {
    card.classList.add("hidden");
    card.classList.add("empty-state");
    card.textContent = "";
    return;
  }
  card.classList.remove("hidden", "empty-state");
  card.innerHTML = `
    <div class="result-header">
      <div><strong>${escapeHtml(text)}</strong></div>
      <span class="status-chip ${tone === "danger" ? "bad" : "warn"}">${tone === "danger" ? "Action blocked" : "Needs review"}</span>
    </div>
  `;
}

function applyInterpretationCityValue(fieldName, rawValue) {
  const fieldId = interpretationFieldId(fieldName);
  const reference = currentInterpretationReference();
  const resolved = resolveKnownCity(rawValue, reference.availableCities);
  setFieldValue(fieldId, resolved || "");
  setProvisionalCityValue(fieldName, resolved ? "" : rawValue);
}

function syncInterpretationDistanceFromReference() {
  const guard = currentInterpretationGuardState();
  const hint = qs("travel-km-hint");
  const travelField = qs("travel-km-outbound");
  if (!travelField || !hint) {
    return;
  }
  const serviceCity = guard.effectiveServiceCity || "";
  if (!guard.includeTransport) {
    hint.textContent = "Transport sentence disabled for this honorarios export.";
    return;
  }
  if (guard.parsedTravelDistanceState === "positive") {
    interpretationCityState.autoDistanceCity = "";
    interpretationCityState.manualDistance = true;
    hint.textContent = guard.distanceHint || "Using the current one-way distance.";
    return;
  }
  if (guard.knownDistance > 0 && serviceCity) {
    if (!fieldValue("travel-km-outbound") || !interpretationCityState.manualDistance || interpretationCityState.autoDistanceCity !== serviceCity) {
      setFieldValue("travel-km-outbound", String(guard.knownDistance));
      interpretationCityState.autoDistanceCity = serviceCity;
      interpretationCityState.manualDistance = false;
    }
    hint.textContent = guard.distanceHint || `Saved by city: ${guard.knownDistance} km one way.`;
    return;
  }
  if (!fieldValue("travel-km-outbound")) {
    interpretationCityState.autoDistanceCity = "";
    interpretationCityState.manualDistance = false;
  }
  hint.textContent = guard.distanceHint || "Distance saved by city will appear here when available.";
}

function updateInterpretationActionAvailability() {
  const guard = currentInterpretationGuardState();
  const blocked = guard.blocked && (
    guard.blockedCode === "unknown_case_city"
    || guard.blockedCode === "unknown_service_city"
    || guard.blockedCode === "distance_required"
    || guard.blockedCode === "distance_must_be_positive"
  );
  for (const id of ["save-row", "export-honorarios", "interpretation-finalize-gmail"]) {
    const button = qs(id);
    if (!button) {
      continue;
    }
    const keepHidden = button.classList.contains("hidden");
    button.disabled = blocked || button.getAttribute("aria-busy") === "true";
    if (keepHidden) {
      button.classList.add("hidden");
    }
  }
  const caseWarning = guard.provisionalCaseCity
    ? `Imported city "${guard.provisionalCaseCity}" is not confirmed yet. Select a known city or add it first.`
    : "";
  const serviceWarning = !qs("service-same")?.checked && guard.provisionalServiceCity
    ? `Imported city "${guard.provisionalServiceCity}" is not confirmed yet. Select a known city or add it first.`
    : "";
  setInterpretationFieldWarning("case_city", caseWarning, "warning");
  setInterpretationFieldWarning("service_city", serviceWarning, "warning");
  if (guard.blocked && (guard.blockedCode === "distance_required" || guard.blockedCode === "distance_must_be_positive")) {
    setInterpretationLocationGuard(guard.blockedMessage, "danger");
  } else if (guard.provisionalCaseCity || guard.provisionalServiceCity) {
    setInterpretationLocationGuard(guard.blockedMessage || "Choose a known city or add the imported city before saving or exporting.", "warning");
  } else {
    setInterpretationLocationGuard("");
  }
  const caseAddButton = qs(interpretationCityAddButtonId("case_city"));
  if (caseAddButton) {
    caseAddButton.textContent = guard.provisionalCaseCity ? `Add “${guard.provisionalCaseCity}”` : "Add city...";
  }
  const serviceAddButton = qs(interpretationCityAddButtonId("service_city"));
  if (serviceAddButton) {
    serviceAddButton.textContent = guard.provisionalServiceCity ? `Add “${guard.provisionalServiceCity}”` : "Add city...";
    serviceAddButton.disabled = qs("service-same")?.checked ?? false;
  }
}

function syncInterpretationCityControls() {
  syncInterpretationDistanceFromReference();
  updateInterpretationActionAvailability();
}

function resetInterpretationExportResult() {
  const panel = qs("interpretation-review-export-panel");
  const result = qs("export-result");
  interpretationUiState.completionPayload = null;
  if (panel) {
    panel.classList.add("hidden");
  }
  if (result) {
    result.classList.add("empty-state");
    result.textContent = "No export has been run yet.";
  }
  notifyInterpretationUiStateChanged();
}

function setInterpretationReviewDrawerOpen(open) {
  const backdrop = qs("interpretation-review-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  interpretationUiState.reviewDrawerOpen = Boolean(open);
  backdrop.classList.toggle("hidden", !interpretationUiState.reviewDrawerOpen);
  backdrop.setAttribute("aria-hidden", interpretationUiState.reviewDrawerOpen ? "false" : "true");
  document.body.dataset.interpretationReviewDrawer = interpretationUiState.reviewDrawerOpen ? "open" : "closed";
  notifyInterpretationUiStateChanged();
}

export function openInterpretationReviewDrawer() {
  setInterpretationReviewDrawerOpen(true);
}

function closeInterpretationReviewDrawer() {
  setInterpretationReviewDrawerOpen(false);
}

function syncInterpretationReviewSurface() {
  const snapshot = interpretationSnapshot();
  const button = qs("interpretation-open-review");
  const gmailButton = qs("interpretation-finalize-gmail");
  const gmailResult = qs("interpretation-gmail-result");
  const saveButton = qs("save-row");
  const exportButton = qs("export-honorarios");
  const clearButton = qs("interpretation-clear-review");
  const closeFooterButton = qs("interpretation-close-review-footer");
  if (button) {
    button.textContent = interpretationReviewButtonLabel(snapshot);
  }
  renderInterpretationSessionShell(snapshot);
  renderInterpretationSeedCard("interpretation-review-home-result");
  renderInterpretationReviewSummary(snapshot);
  renderInterpretationReviewContext(snapshot);
  renderInterpretationCompletionCard(snapshot);
  const hasGmailInterpretationSession = interpretationActiveSession()?.kind === "interpretation";
  const drawerLayout = deriveInterpretationDrawerLayout({
    workspaceMode: interpretationWorkspaceMode(snapshot, interpretationActiveSession()),
    activeSession: interpretationActiveSession(),
    serviceSame: qs("service-same")?.checked ?? true,
    validationField: interpretationUiState.validationField,
  });
  if (gmailButton) {
    gmailButton.classList.toggle("hidden", !drawerLayout.actions.showFinalizeGmail);
  }
  if (saveButton) {
    saveButton.classList.toggle("hidden", !drawerLayout.actions.showSaveRow);
  }
  if (exportButton) {
    exportButton.classList.toggle("hidden", !drawerLayout.actions.showGenerateDocxPdf);
  }
  if (clearButton) {
    clearButton.classList.toggle("hidden", !drawerLayout.actions.showNewBlank);
  }
  if (closeFooterButton) {
    closeFooterButton.classList.toggle("hidden", !drawerLayout.actions.showFooterClose);
  }
  if (gmailResult && !hasGmailInterpretationSession) {
    gmailResult.classList.add("empty-state");
    gmailResult.textContent = "Gmail draft and final attachment details appear here after finalization.";
  }
  const statusNode = qs("interpretation-review-status");
  if (statusNode) {
    if (interpretationWorkspaceMode(snapshot, interpretationActiveSession()) === "gmail_completed") {
      statusNode.textContent = "The Gmail interpretation draft and export are ready. Reopen Review details only if you need to inspect or adjust the completed form.";
    } else if (drawerLayout.actions.showFinalizeGmail) {
      statusNode.textContent = "Review the staged notice details here, then finish the Gmail reply from this same bounded surface.";
    } else {
      statusNode.textContent = hasInterpretationReviewData(snapshot)
        ? "Review the recovered case data here, then save the row or generate the honorários export when you are ready."
        : "Autofill a notification or open a blank review surface to prepare the interpretation row and honorários export.";
    }
  }
  syncInterpretationCityControls();
  syncInterpretationDisclosureState();
  notifyInterpretationUiStateChanged();
}

function focusInterpretationField(fieldName) {
  interpretationUiState.validationField = String(fieldName || "").trim();
  if (fieldName === "service_city" || fieldName === "service_entity" || fieldName === "service_date") {
    qs("interpretation-service-section")?.setAttribute("open", "open");
  }
  if (fieldName === "travel_km_outbound") {
    qs("interpretation-text-section")?.setAttribute("open", "open");
  }
  const targetId = fieldName === "case_city"
    ? "case-city"
    : fieldName === "service_city"
      ? "service-city"
      : fieldName === "travel_km_outbound"
        ? "travel-km-outbound"
        : fieldName;
  qs(targetId)?.focus();
}

function setInterpretationCityDialogOpen(open) {
  const backdrop = qs("interpretation-city-dialog-backdrop");
  if (!backdrop) {
    return;
  }
  interpretationCityState.dialogOpen = Boolean(open);
  backdrop.classList.toggle("hidden", !interpretationCityState.dialogOpen);
  backdrop.setAttribute("aria-hidden", interpretationCityState.dialogOpen ? "false" : "true");
  document.body.dataset.interpretationCityDialog = interpretationCityState.dialogOpen ? "open" : "closed";
}

function closeInterpretationCityDialog(result = null) {
  const resolver = interpretationCityState.dialogResolver;
  interpretationCityState.dialogResolver = null;
  setInterpretationCityDialogOpen(false);
  if (typeof resolver === "function") {
    resolver(result);
  }
}

function openInterpretationCityDialog({
  mode,
  fieldName,
  cityName = "",
  requireDistance = false,
  lockedCity = false,
  confirmLabel = "Save City",
} = {}) {
  interpretationCityState.activeDialog = {
    mode: mode || "add",
    fieldName: fieldName || "service_city",
    requireDistance: Boolean(requireDistance),
  };
  setFieldValue("interpretation-city-dialog-field-name", interpretationCityState.activeDialog.fieldName);
  setFieldValue("interpretation-city-dialog-mode", interpretationCityState.activeDialog.mode);
  setFieldValue("interpretation-city-dialog-name", cityName);
  setFieldValue("interpretation-city-dialog-distance", "");
  const title = qs("interpretation-city-dialog-title");
  const status = qs("interpretation-city-dialog-status");
  const cityInput = qs("interpretation-city-dialog-name");
  const distanceShell = qs("interpretation-city-dialog-distance-shell");
  const distanceHint = qs("interpretation-city-dialog-distance-hint");
  const confirmButton = qs("interpretation-city-dialog-confirm");
  const reference = currentInterpretationReference();
  if (title) {
    title.textContent = interpretationCityState.activeDialog.mode === "distance" ? "Confirm One-Way Distance" : "Add City";
  }
  if (status) {
    status.textContent = interpretationCityState.activeDialog.mode === "distance"
      ? `Enter the one-way distance from ${reference.travelOriginLabel || "your travel origin"} to ${cityName}.`
      : "Confirm the city details before continuing.";
  }
  if (cityInput) {
    cityInput.readOnly = Boolean(lockedCity);
  }
  if (distanceShell) {
    distanceShell.classList.toggle("hidden", !interpretationCityState.activeDialog.requireDistance);
  }
  if (distanceHint) {
    distanceHint.textContent = reference.travelOriginLabel
      ? `Use the one-way distance from ${reference.travelOriginLabel}.`
      : "Use the one-way distance from your profile travel origin.";
  }
  if (confirmButton) {
    confirmButton.textContent = confirmLabel;
  }
  setInterpretationCityDialogOpen(true);
  return new Promise((resolve) => {
    interpretationCityState.dialogResolver = resolve;
    window.setTimeout(() => {
      (lockedCity ? qs("interpretation-city-dialog-distance") : qs("interpretation-city-dialog-name"))?.focus();
    }, 0);
  });
}

function applyInterpretationReferenceUpdate(interpretationReference, profileDistanceSummary = null) {
  if (!appState.bootstrap?.normalized_payload) {
    return;
  }
  if (interpretationReference) {
    appState.bootstrap.normalized_payload.interpretation_reference = interpretationReference;
  }
  if (profileDistanceSummary?.profile_id) {
    appState.bootstrap.normalized_payload.profiles = profileSummaries().map((profile) => {
      if (String(profile.id || "") !== String(profileDistanceSummary.profile_id || "")) {
        return profile;
      }
      return {
        ...profile,
        travel_origin_label: profileDistanceSummary.travel_origin_label || profile.travel_origin_label,
        travel_distances_by_city: { ...(profileDistanceSummary.travel_distances_by_city || {}) },
        distance_city_count: Object.keys(profileDistanceSummary.travel_distances_by_city || {}).length,
      };
    });
  }
}

async function persistInterpretationCity({ fieldName, cityName, distanceValue = "" } = {}) {
  const payload = await fetchJson("/api/interpretation/cities/add", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      field_name: fieldName,
      city: cityName,
      profile_id: qs("profile-id")?.value || "",
      include_transport_sentence_in_honorarios: qs("include-transport")?.checked ?? true,
      travel_km_outbound: distanceValue,
    }),
  });
  applyInterpretationReferenceUpdate(
    payload.normalized_payload?.interpretation_reference || null,
    payload.normalized_payload?.profile_distance_summary || null,
  );
  refreshInterpretationCitySelectors();
  applyInterpretationCityValue(fieldName, payload.normalized_payload?.city || cityName);
  if ((qs("service-same")?.checked ?? false) && fieldName === "case_city") {
    applyInterpretationCityValue("service_city", payload.normalized_payload?.city || cityName);
  }
  if (String(distanceValue || "").trim()) {
    setFieldValue("travel-km-outbound", distanceValue);
    interpretationCityState.manualDistance = false;
    interpretationCityState.autoDistanceCity = payload.normalized_payload?.city || cityName;
  }
  syncInterpretationCityControls();
  setPanelStatus("form", "ok", payload.normalized_payload?.message || "City saved.");
  setDiagnostics("form", payload, {
    hint: payload.normalized_payload?.message || "City saved.",
    open: false,
  });
  return payload;
}

async function promptToAddInterpretationCity(fieldName) {
  const draftCity = provisionalCityValue(fieldName) || fieldValue(interpretationFieldId(fieldName));
  const result = await openInterpretationCityDialog({
    mode: "add",
    fieldName,
    cityName: draftCity,
    requireDistance: qs("include-transport")?.checked ?? true,
    confirmLabel: "Save City",
  });
  if (!result) {
    return false;
  }
  await persistInterpretationCity({
    fieldName,
    cityName: result.cityName,
    distanceValue: result.distanceValue,
  });
  return true;
}

export function recoverInterpretationValidationError(error) {
  const validation = error?.payload?.normalized_payload?.validation_error || error?.payload?.diagnostics?.validation_error;
  if (!validation || typeof validation !== "object") {
    return false;
  }
  openInterpretationReviewDrawer();
  const fieldName = String(validation.field || "").trim();
  const city = String(validation.city || "").trim();
  if (fieldName === "case_city") {
    setFieldValue("case-city", "");
    setProvisionalCityValue("case_city", city);
    if (qs("service-same")?.checked ?? false) {
      setFieldValue("service-city", "");
      setProvisionalCityValue("service_city", city);
    }
  } else if (fieldName === "service_city") {
    setFieldValue("service-city", "");
    setProvisionalCityValue("service_city", city);
    if (qs("service-same")?.checked ?? false) {
      setFieldValue("case-city", "");
      setProvisionalCityValue("case_city", city);
    }
  }
  syncInterpretationCityControls();
  setPanelStatus("form", "bad", error.message || "Interpretation validation failed.");
  setDiagnostics("form", error, {
    hint: error.message || "Interpretation validation failed.",
    open: true,
  });
  focusInterpretationField(fieldName || "case-city");
  return true;
}

export async function prepareInterpretationAction(actionName = "save") {
  const guard = currentInterpretationGuardState();
  if (guard.blocked) {
    const fallbackError = new Error(guard.blockedMessage || `Interpretation ${actionName} is blocked.`);
    fallbackError.payload = {
      status: "failed",
      normalized_payload: {
        validation_error: {
          code: guard.blockedCode,
          field: guard.blockedField,
          city: guard.blockedField === "case_city" ? guard.provisionalCaseCity : guard.provisionalServiceCity,
          travel_origin_label: guard.reference.travelOriginLabel,
          city_source: "current_selection",
        },
      },
      diagnostics: {
        error: guard.blockedMessage || `Interpretation ${actionName} is blocked.`,
      },
    };
    if (guard.blockedField === "travel_km_outbound") {
      qs("interpretation-text-section")?.setAttribute("open", "open");
      setPanelStatus("form", "bad", fallbackError.message || `Interpretation ${actionName} is blocked.`);
      setDiagnostics("form", fallbackError, {
        hint: fallbackError.message || `Interpretation ${actionName} is blocked.`,
        open: true,
      });
      focusInterpretationField("travel_km_outbound");
    } else {
      recoverInterpretationValidationError(fallbackError);
    }
    throw fallbackError;
  }
  if (guard.distancePromptNeeded) {
    const result = await openInterpretationCityDialog({
      mode: "distance",
      fieldName: "service_city",
      cityName: guard.effectiveServiceCity,
      requireDistance: true,
      lockedCity: true,
      confirmLabel: "Use Distance",
    });
    if (!result) {
      const message = guard.distanceHint || "A positive one-way distance is required before continuing.";
      setPanelStatus("form", "bad", message);
      setDiagnostics("form", { status: "failed", diagnostics: { error: message } }, { hint: message, open: true });
      qs("interpretation-text-section")?.setAttribute("open", "open");
      focusInterpretationField("travel_km_outbound");
      throw new Error(message);
    }
    await persistInterpretationCity({
      fieldName: "service_city",
      cityName: guard.effectiveServiceCity,
      distanceValue: result.distanceValue,
    });
  }
}

export function getInterpretationUiSnapshot() {
  const exportPanel = qs("interpretation-review-export-panel");
  const snapshot = interpretationSnapshot();
  const activeSession = interpretationActiveSession();
  return {
    reviewDrawerOpen: interpretationUiState.reviewDrawerOpen,
    hasSeedData: hasInterpretationReviewData(snapshot),
    exportReady: Boolean(exportPanel && !exportPanel.classList.contains("hidden")),
    rowId: String(appState.currentRowId || "").trim(),
    workspaceMode: interpretationWorkspaceMode(snapshot, activeSession),
    noticeFilename: interpretationNoticeFilename(activeSession),
    caseNumber: snapshot.caseNumber,
    courtEmail: snapshot.courtEmail,
    serviceDate: snapshot.serviceDate,
    locationSummary: interpretationLocationSummary(snapshot),
  };
}

function shouldShowGmailNav(payload = appState.bootstrap) {
  const gmail = payload?.normalized_payload?.gmail || {};
  return Boolean(
    appState.activeView === "gmail-intake"
    || appState.workspaceId === "gmail-intake"
    || gmail.load_result
    || gmail.active_session
    || gmail.interpretation_seed
    || gmail.suggested_translation_launch,
  );
}

function findNavigationItem(items, id) {
  return items.find((item) => item.id === id) || null;
}

function buildNavigationGroups(items) {
  const primary = [];
  for (const id of PRIMARY_NAV_ORDER) {
    if (id === "gmail-intake") {
      if (!shouldShowGmailNav()) {
        continue;
      }
      const source = findNavigationItem(items, "gmail-intake");
      primary.push({
        id: "gmail-intake",
        label: source?.label || "Gmail",
        status: source?.status || "ready",
      });
      continue;
    }
    const item = findNavigationItem(items, id);
    if (item) {
      primary.push(item);
    }
  }

  const more = [];
  for (const id of MORE_NAV_ORDER) {
    const item = findNavigationItem(items, id);
    if (item) {
      more.push(item);
    }
  }
  return { primary, more };
}

function setNewJobTask(task) {
  appState.newJobTask = task === "interpretation" ? "interpretation" : "translation";
  qsa("[data-task-panel]").forEach((panel) => {
    panel.classList.toggle("hidden", panel.dataset.taskPanel !== appState.newJobTask);
  });
  qsa(".task-switch").forEach((button) => {
    const selected = button.dataset.task === appState.newJobTask;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-selected", selected ? "true" : "false");
  });
  renderInterpretationSessionShell();
}

function syncShellChrome() {
  document.body.dataset.activeView = appState.activeView;
  const currentNav = document.querySelector(`.nav-button[data-view="${appState.activeView}"] span`);
  if (qs("topbar-title") && currentNav?.textContent?.trim()) {
    qs("topbar-title").textContent = currentNav.textContent.trim() === "Dashboard"
      ? "LegalPDF Translate"
      : `LegalPDF Translate | ${currentNav.textContent.trim()}`;
  }
}

function operatorChromeActive() {
  return appState.operatorMode || MORE_NAV_ORDER.includes(appState.activeView);
}

function syncOperatorChrome() {
  document.body.dataset.operatorChrome = operatorChromeActive() ? "on" : "off";
  const toggle = qs("operator-mode-toggle");
  if (!toggle) {
    return;
  }
  toggle.setAttribute("aria-pressed", appState.operatorMode ? "true" : "false");
  toggle.textContent = appState.operatorMode ? "Hide Technical Details" : "Show Technical Details";
  const hint = qs("operator-mode-hint");
  if (hint) {
    hint.textContent = appState.operatorMode
      ? "Technical build, listener, and diagnostics panels stay visible across the shell until you turn them off."
      : "Build, listener, and diagnostics panels stay hidden until you ask for them or a failure occurs.";
  }
}

function updateServiceFieldState() {
  interpretationUiState.validationField = "";
  const serviceSame = qs("service-same").checked;
  if (serviceSame) {
    syncServiceFieldsFromCase();
  } else if (!fieldValue("service-city") && provisionalCityValue("service_city") === provisionalCityValue("case_city")) {
    setProvisionalCityValue("service_city", "");
  }
  qs("service-entity").disabled = serviceSame;
  qs("service-city").disabled = serviceSame;
  qs("service-same-hint").textContent = serviceSame
    ? "Service entity and city will mirror the case fields for save and export."
    : "Use different service fields when the service location differs from the case.";
  syncInterpretationDisclosureState();
  syncInterpretationCityControls();
  renderInterpretationSeedCard("interpretation-review-home-result");
  renderInterpretationReviewSummary();
  renderInterpretationReviewContext();
  notifyInterpretationUiStateChanged();
}

function cloneJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function blankProfileDraft() {
  return {
    id: "",
    first_name: "",
    last_name: "",
    document_name_override: "",
    document_name: "",
    email: "",
    phone_number: "",
    postal_address: "",
    iban: "",
    iva_text: "23%",
    irs_text: "Sem retenção",
    travel_origin_label: "",
    travel_distances_by_city: {},
    distance_city_count: 0,
    is_primary: false,
  };
}

function setProfileEditorDrawerOpen(open) {
  const backdrop = qs("profile-editor-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  profileUiState.editorDrawerOpen = Boolean(open);
  backdrop.classList.toggle("hidden", !profileUiState.editorDrawerOpen);
  backdrop.setAttribute("aria-hidden", profileUiState.editorDrawerOpen ? "false" : "true");
  document.body.dataset.profileEditorDrawer = profileUiState.editorDrawerOpen ? "open" : "closed";
}

function openProfileEditorDrawer() {
  setProfileEditorDrawerOpen(true);
}

function closeProfileEditorDrawer() {
  setProfileEditorDrawerOpen(false);
}

function profileFieldIds() {
  return {
    id: "profile-editor-id",
    first_name: "profile-editor-first-name",
    last_name: "profile-editor-last-name",
    document_name_override: "profile-editor-document-name-override",
    email: "profile-editor-email",
    phone_number: "profile-editor-phone-number",
    postal_address: "profile-editor-postal-address",
    iban: "profile-editor-iban",
    iva_text: "profile-editor-iva-text",
    irs_text: "profile-editor-irs-text",
    travel_origin_label: "profile-editor-travel-origin-label",
  };
}

function formatDistanceJson(value) {
  const distances = value && typeof value === "object" ? value : {};
  return JSON.stringify(distances, null, 2);
}

function applyProfileEditor(profile, { openDrawer = false } = {}) {
  const resolved = { ...blankProfileDraft(), ...(profile || {}) };
  const fieldIds = profileFieldIds();
  for (const [key, id] of Object.entries(fieldIds)) {
    setFieldValue(id, resolved[key] ?? "");
  }
  setFieldValue("profile-editor-travel-distances-json", formatDistanceJson(resolved.travel_distances_by_city));
  setCheckbox("profile-editor-make-primary", Boolean(resolved.is_primary));
  profileState.currentProfileId = resolved.id || "";
  qs("profile-editor-status").textContent = resolved.id
    ? `Editing profile ${resolved.document_name || resolved.id}.`
    : "Editing a new profile draft.";
  qs("profile-set-primary").disabled = !resolved.id;
  qs("profile-delete").disabled = !resolved.id;
  if (openDrawer) {
    openProfileEditorDrawer();
  }
}

function collectProfileFormValues() {
  const fieldIds = profileFieldIds();
  const payload = {};
  for (const [key, id] of Object.entries(fieldIds)) {
    payload[key] = fieldValue(id);
  }
  let travelDistances = {};
  const rawJson = fieldValue("profile-editor-travel-distances-json");
  if (rawJson) {
    try {
      const parsed = JSON.parse(rawJson);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("Travel distances JSON must be an object mapping city names to one-way km values.");
      }
      travelDistances = parsed;
    } catch (error) {
      throw new Error(error.message || "Travel distances JSON is invalid.");
    }
  }
  payload.travel_distances_by_city = travelDistances;
  return payload;
}

export function collectInterpretationFormValues() {
  const serviceSame = qs("service-same").checked;
  const caseEntity = fieldValue("case-entity");
  const caseCity = fieldValue("case-city");
  return {
    case_number: fieldValue("case-number"),
    court_email: fieldValue("court-email"),
    case_entity: caseEntity,
    case_city: caseCity,
    service_entity: serviceSame ? caseEntity : fieldValue("service-entity"),
    service_city: serviceSame ? caseCity : fieldValue("service-city"),
    service_date: fieldValue("service-date"),
    travel_km_outbound: fieldValue("travel-km-outbound"),
    pages: fieldValue("pages"),
    word_count: fieldValue("word-count"),
    rate_per_word: fieldValue("rate-per-word"),
    expected_total: fieldValue("expected-total"),
    amount_paid: fieldValue("amount-paid"),
    api_cost: fieldValue("api-cost"),
    profit: fieldValue("profit"),
    recipient_block: qs("recipient-block").value.trim(),
    include_transport_sentence_in_honorarios: qs("include-transport").checked,
    use_service_location_in_honorarios: qs("use-service-location").checked,
  };
}

export function applyInterpretationSeed(seed, { activateTask = true, openReview = false } = {}) {
  if (activateTask) {
    setNewJobTask("interpretation");
  }
  appState.currentSeed = seed;
  appState.currentRowId = null;
  qs("row-id").value = "";
  setFieldValue("case-number", seed.case_number);
  setFieldValue("court-email", seed.court_email);
  setFieldValue("case-entity", seed.case_entity);
  applyInterpretationCityValue("case_city", seed.case_city);
  setFieldValue("service-entity", seed.service_entity || seed.case_entity || "");
  applyInterpretationCityValue("service_city", seed.service_city || seed.case_city || "");
  setFieldValue("service-date", seed.service_date);
  setFieldValue("travel-km-outbound", seed.travel_km_outbound ?? "");
  setFieldValue("pages", seed.pages ?? "");
  setFieldValue("word-count", seed.word_count ?? "");
  setFieldValue("rate-per-word", seed.rate_per_word ?? "");
  setFieldValue("expected-total", seed.expected_total ?? "");
  setFieldValue("amount-paid", seed.amount_paid ?? "");
  setFieldValue("api-cost", seed.api_cost ?? "");
  setFieldValue("profit", seed.profit ?? "");
  setCheckbox("service-same", inferServiceSame(seed.case_entity, seed.case_city, seed.service_entity, seed.service_city));
  setCheckbox("use-service-location", Boolean(seed.use_service_location_in_honorarios));
  setCheckbox("include-transport", seed.include_transport_sentence_in_honorarios !== false);
  qs("recipient-block").value = "";
  updateServiceFieldState();
  interpretationCityState.manualDistance = Boolean(fieldValue("travel-km-outbound"));
  interpretationCityState.autoDistanceCity = "";
  resetInterpretationExportResult();
  syncInterpretationReviewSurface();
  if (openReview) {
    openInterpretationReviewDrawer();
  }
}

function applyHistoryItem(item) {
  setNewJobTask("interpretation");
  appState.currentSeed = item.seed;
  appState.currentRowId = item.row.id;
  qs("row-id").value = item.row.id;
  setFieldValue("case-number", item.row.case_number || "");
  setFieldValue("court-email", item.row.court_email || "");
  setFieldValue("case-entity", item.row.case_entity || "");
  applyInterpretationCityValue("case_city", item.row.case_city || "");
  setFieldValue("service-entity", item.row.service_entity || "");
  applyInterpretationCityValue("service_city", item.row.service_city || "");
  setFieldValue("service-date", item.row.service_date || "");
  setFieldValue("travel-km-outbound", item.row.travel_km_outbound ?? "");
  setFieldValue("pages", item.row.pages ?? "");
  setFieldValue("word-count", item.row.word_count ?? "");
  setFieldValue("rate-per-word", item.row.rate_per_word ?? "");
  setFieldValue("expected-total", item.row.expected_total ?? "");
  setFieldValue("amount-paid", item.row.amount_paid ?? "");
  setFieldValue("api-cost", item.row.api_cost ?? "");
  setFieldValue("profit", item.row.profit ?? "");
  qs("recipient-block").value = "";
  setCheckbox("service-same", inferServiceSame(item.row.case_entity, item.row.case_city, item.row.service_entity, item.row.service_city));
  setCheckbox("use-service-location", Boolean(item.row.use_service_location_in_honorarios));
  setCheckbox("include-transport", item.row.include_transport_sentence_in_honorarios !== 0);
  updateServiceFieldState();
  interpretationCityState.manualDistance = Boolean(fieldValue("travel-km-outbound"));
  interpretationCityState.autoDistanceCity = "";
  resetInterpretationExportResult();
  syncInterpretationReviewSurface();
  setPanelStatus("form", "ok", `Loaded row #${item.row.id} from the active job log.`);
  setDiagnostics("form", { status: "ok", message: `Loaded row #${item.row.id}.` }, { hint: "Loaded from job-log history.", open: false });
  setActiveView("new-job");
  renderShellVisibility();
  openInterpretationReviewDrawer();
}

function renderProfiles(profiles, primaryProfileId) {
  const select = qs("profile-id");
  select.innerHTML = "";
  if (!profiles.length) {
    const option = document.createElement("option");
    option.value = "";
    option.textContent = "No profiles available";
    option.selected = true;
    select.appendChild(option);
    select.disabled = true;
    return;
  }
  select.disabled = false;
  for (const profile of profiles) {
    const option = document.createElement("option");
    option.value = profile.id;
    option.textContent = profile.document_name || profile.id;
    if (profile.id === primaryProfileId) {
      option.selected = true;
    }
    select.appendChild(option);
  }
}

function renderNavigation(items) {
  const primaryContainer = qs("section-nav");
  const moreContainer = qs("more-nav");
  const moreShell = qs("more-nav-shell");
  const { primary, more } = buildNavigationGroups(items);

  primaryContainer.innerHTML = "";
  moreContainer.innerHTML = "";

  for (const collection of [
    { container: primaryContainer, items: primary },
    { container: moreContainer, items: more },
  ]) {
    for (const item of collection.items) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "nav-button";
      button.dataset.view = item.id;
      button.innerHTML = `<span>${item.label}</span><span class="nav-meta">${item.status === "ready" ? "Ready" : item.status}</span>`;
      if (item.id === appState.activeView) {
        button.classList.add("active");
      }
      collection.container.appendChild(button);
    }
  }

  const moreActive = MORE_NAV_ORDER.includes(appState.activeView);
  moreShell.open = moreActive;
  moreShell.classList.toggle("has-active-view", moreActive);
}

function renderShellVisibility() {
  qsa(".page-view").forEach((node) => {
    node.classList.toggle("hidden", node.dataset.view !== appState.activeView);
  });
  qsa(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === appState.activeView);
  });
  const moreShell = qs("more-nav-shell");
  if (moreShell) {
    const moreActive = MORE_NAV_ORDER.includes(appState.activeView);
    moreShell.open = moreActive || moreShell.open;
    moreShell.classList.toggle("has-active-view", moreActive);
  }
  const gmailFocusActive = routeShellMode() === "gmail-focus";
  if (gmailFocusActive && !shellUiState.gmailFocusActive) {
    closeSessionDrawer();
    closeTranslationCompletionDrawer();
    closeInterpretationReviewDrawer();
    closeProfileEditorDrawer();
    qs("gmail-intake-details")?.removeAttribute("open");
  }
  shellUiState.gmailFocusActive = gmailFocusActive;
  setNewJobTask(appState.newJobTask);
  syncInterpretationReviewSurface();
  syncShellChrome();
  syncOperatorChrome();
}

function renderDashboardCards(cards) {
  const container = qs("dashboard-cards");
  container.innerHTML = "";
  for (const card of cards) {
    const article = document.createElement("article");
    article.className = "launch-card";
    article.classList.add(card.status === "ready" ? "ready" : "planned");
    const chipTone = card.status === "ready" ? "ok" : "warn";
    const chipText = card.status === "ready" ? "Ready now" : card.status.replaceAll("_", " ");
    article.innerHTML = `<h3>${card.title}</h3><p>${card.description}</p><span class="status-chip ${chipTone}">${chipText}</span>`;
    container.appendChild(article);
  }
}

function renderSummaryGrid(containerId, items) {
  const container = qs(containerId);
  container.innerHTML = "";
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "summary-card";
    card.innerHTML = `<h3>${item.label}</h3><p class="word-break">${item.value}</p>`;
    container.appendChild(card);
  }
}

async function handleDeleteJobLogRow(rowId, { jobType = "job-log", source = "history" } = {}) {
  if (!window.confirm(`Delete ${jobType} row #${rowId} from the active job log?`)) {
    return;
  }
  const payload = await fetchJson("/api/joblog/delete", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ row_id: rowId }),
  });
  if (Number(appState.currentRowId) === Number(rowId)) {
    appState.currentRowId = null;
    qs("row-id").value = "";
  }
  const message = payload.normalized_payload?.message || `Deleted row #${rowId}.`;
  setPanelStatus("recent-jobs", "ok", message);
  setDiagnostics("form", payload, { hint: `${source} deleted row #${rowId}.`, open: false });
  window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
}

function buildCapabilityCards(payload) {
  const runtime = payload.normalized_payload.runtime;
  const capabilities = payload.capability_flags;
  const automation = capabilities.browser_automation || payload.normalized_payload.automation_preflight || {};
  const gmailBridge = capabilities.gmail_bridge || {};
  const nativeHost = capabilities.native_host || {};
  const translation = capabilities.translation || {};
  const wordState = capabilities.word_pdf_export || {};
  const wordLaunch = wordState.launch_preflight || wordState.preflight || {};
  const wordCanary = wordState.export_canary || {};
  const wordReady = wordState.finalization_ready === true || wordState.ok === true;
  const wordText = wordReady
    ? "Launch preflight and export canary are passing for Gmail finalization PDF export."
    : [
        wordCanary.message ? `Export canary: ${wordCanary.message}` : "",
        wordLaunch.message ? `Launch preflight: ${wordLaunch.message}` : "",
      ].filter(Boolean).join("\n") || "Word PDF export readiness is unavailable.";
  const wordStatus = wordReady ? "ok" : (wordCanary.failure_code || wordLaunch.failure_code) ? "bad" : "warn";
  const wordLabel = wordReady ? "Ready" : wordState.finalization_ready === false ? "Blocked" : "Needs attention";
  const gmailBridgeText = [
    gmailBridge.message,
    gmailBridge.owner_kind ? `Owner: ${gmailBridge.owner_kind}` : "",
    ...(gmailBridge.detail_lines || []),
  ].filter(Boolean).join("\n");
  const translationReady = translation.credentials_configured === true;
  const translationSource = describeCredentialSource(translation.credential_source);
  return [
    {
      title: "Browser Runtime",
      text: `${runtime.runtime_mode_label}\nWorkspace: ${runtime.workspace_id}\nData root: ${runtime.app_data_dir}`,
      status: runtime.live_data ? "warn" : "ok",
      label: runtime.live_data ? "Live Data" : "Isolated",
    },
    {
      title: "Native Host",
      text: [
        nativeHost.message || "Native-host status is unavailable.",
        nativeHost.self_test_status ? `Self-test: ${nativeHost.self_test_status}` : "",
        nativeHost.wrapper_target_python ? `Wrapper target: ${nativeHost.wrapper_target_python}` : "",
      ].filter(Boolean).join("\n"),
      status: nativeHost.status || "warn",
      label: nativeHost.label || "Unknown",
    },
    {
      title: "OCR",
      text: `Provider: ${capabilities.ocr.provider}\nLocal OCR: ${capabilities.ocr.local_available ? "available" : "missing"}\nAPI OCR: ${capabilities.ocr.api_configured ? "configured" : "not configured"}`,
      status: capabilities.ocr.api_configured || capabilities.ocr.local_available ? "ok" : "warn",
      label: capabilities.ocr.api_configured || capabilities.ocr.local_available ? "Usable" : "Unavailable",
    },
    {
      title: "Translation Auth",
      text: `Credentials: ${translationReady ? "configured" : "not configured"}\nSource: ${translationSource}\nAuth test: ${translation.auth_test_supported ? "available" : "unavailable"}`,
      status: translationReady ? "ok" : "warn",
      label: translationReady ? "Configured" : "Needs auth",
    },
    {
      title: "Word PDF Export",
      text: wordText,
      status: wordStatus,
      label: wordLabel,
    },
    {
      title: "Browser Automation",
      text: `Preferred host: ${automation.preferred_host_status}\nPlaywright available: ${automation.toolchain?.playwright_available}`,
      status: automation.preferred_host_status === "available" ? "ok" : "warn",
      label: automation.preferred_host_status === "available" ? "Ready" : "Blocked",
    },
    {
      title: "Gmail Bridge",
      text: gmailBridgeText || "Gmail bridge status is unavailable.",
      status: gmailBridge.status || "warn",
      label: gmailBridge.label || "Unknown",
    },
  ];
}

function describeCredentialSource(source) {
  const kind = String(source?.kind || "").trim();
  const name = String(source?.name || "").trim();
  if (kind === "stored" && name === "ocr_api_key_fallback") {
    return "stored OCR key fallback";
  }
  if (kind === "stored") {
    return "stored translation key";
  }
  if (kind === "env") {
    return name ? `env ${name}` : "environment variable";
  }
  if (kind === "inline") {
    return "inline key";
  }
  if (kind === "missing") {
    return "not configured";
  }
  return kind || "unknown";
}

function renderCapabilityCards(containerId, cards) {
  const container = qs(containerId);
  container.innerHTML = "";
  for (const card of cards) {
    const article = document.createElement("article");
    article.className = "status-card";
    article.innerHTML = `<h3>${card.title}</h3><p>${card.text.replaceAll("\n", "<br>")}</p><span class="status-chip ${chipToneClass(card.status)}">${card.label}</span>`;
    container.appendChild(article);
  }
}

function renderRecentJobs(items, history, translationHistory = []) {
  const container = qs("recent-jobs-list");
  container.innerHTML = "";
  if (!items.length) {
    setPanelStatus("recent-jobs", "", "No recent rows are available for this runtime mode yet.");
    container.innerHTML = '<div class="empty-state">No job-log rows exist for this runtime mode yet.</div>';
    return;
  }
  setPanelStatus("recent-jobs", "", `${items.length} recent row(s) loaded for this runtime mode.`);
  const historyById = new Map(history.map((item) => [Number(item.row.id), item]));
  const translationHistoryById = new Map(translationHistory.map((item) => [Number(item.row.id), item]));
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "history-item";
    const metaBits = [item.job_type];
    if (item.target_lang) {
      metaBits.push(item.target_lang);
    }
    if (item.service_date) {
      metaBits.push(item.service_date);
    }
    card.innerHTML = `<div><strong>${item.case_number}</strong><p>${item.case_entity} | ${item.case_city}</p><div class="history-meta">${metaBits.map((bit) => `<small>${bit}</small>`).join("")}</div></div>`;
    const interpretationItem = item.job_type === "Interpretation" ? historyById.get(Number(item.id)) : null;
    const translationItem = item.job_type !== "Interpretation" ? translationHistoryById.get(Number(item.id)) : null;
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const loadButton = document.createElement("button");
    loadButton.type = "button";
    loadButton.textContent = interpretationItem || translationItem ? "Load" : "View";
    loadButton.disabled = !(interpretationItem || translationItem);
    if (interpretationItem) {
      loadButton.addEventListener("click", () => applyHistoryItem(interpretationItem));
    } else if (translationItem) {
      loadButton.addEventListener("click", () => loadTranslationHistoryItem(translationItem));
    }
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", async () => {
      try {
        await handleDeleteJobLogRow(item.id, { jobType: item.job_type, source: "recent jobs" });
      } catch (error) {
        setPanelStatus("recent-jobs", "bad", error.message || "Recent-jobs delete failed.");
        setDiagnostics("form", error, { hint: error.message || "Recent-jobs delete failed.", open: true });
      }
    });
    actions.appendChild(loadButton);
    actions.appendChild(deleteButton);
    card.appendChild(actions);
    container.appendChild(card);
  }
}

function renderHistory(items, modeLabel) {
  const container = qs("history-list");
  qs("history-heading").textContent = `${modeLabel} Interpretation History`;
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = '<div class="empty-state">No interpretation rows saved yet for this runtime mode.</div>';
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "history-item";
    const left = document.createElement("div");
    left.innerHTML = `<strong>${item.row.case_number || "Sem processo"}</strong><p>${item.row.case_entity || "No case entity"} | ${item.row.case_city || "No case city"} | ${item.row.service_date || "No service date"}</p>`;
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Load";
    button.addEventListener("click", () => applyHistoryItem(item));
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";
    deleteButton.addEventListener("click", async () => {
      try {
        await handleDeleteJobLogRow(item.row.id, { jobType: "Interpretation", source: "interpretation history" });
      } catch (error) {
        setPanelStatus("recent-jobs", "bad", error.message || "Interpretation row delete failed.");
        setDiagnostics("form", error, { hint: error.message || "Interpretation row delete failed.", open: true });
      }
    });
    actions.appendChild(button);
    actions.appendChild(deleteButton);
    card.appendChild(left);
    card.appendChild(actions);
    container.appendChild(card);
  }
}

function renderStatus(payload) {
  const runtime = payload.normalized_payload.runtime;
  const cards = buildCapabilityCards(payload);
  renderCapabilityCards("status-grid", cards);
  renderCapabilityCards("settings-capability-grid", cards);
  setPanelStatus("runtime", runtime.live_data ? "warn" : "ok", `Running on ${runtime.host}:${runtime.port} in ${runtime.runtime_mode_label}. Workspace ${runtime.workspace_id} is active.`);
  setDiagnostics("runtime", payload.diagnostics.runtime, {
    hint: "Build identity, listener ownership, and runtime-mode provenance.",
    open: false,
  });
}

export function renderInterpretationExportResult(payload) {
  const container = qs("export-result");
  qs("interpretation-review-export-panel")?.classList.remove("hidden");
  const result = payload.normalized_payload || {};
  const pdf = payload.diagnostics?.pdf_export || {};
  const isOk = payload.status === "ok";
  const isLocalOnly = payload.status === "local_only";
  const tone = isOk ? "ok" : isLocalOnly ? "warn" : "bad";
  const label = isOk ? "PDF ready" : isLocalOnly ? "Local-only" : "Export failed";
  const message = isOk ? "DOCX and sibling PDF are ready." : isLocalOnly ? pdf.failure_message || "DOCX is ready, but PDF export is unavailable." : "The export did not complete successfully.";
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div><strong>${message}</strong></div>
      <span class="status-chip ${tone === "ok" ? "ok" : tone === "bad" ? "bad" : "warn"}">${label}</span>
    </div>
    <div class="result-grid">
      <div><h3>DOCX</h3><p class="word-break">${result.docx_path || "Unavailable"}</p></div>
      <div><h3>PDF</h3><p class="word-break">${result.pdf_path || "Unavailable"}</p></div>
      <div><h3>PDF Export</h3><p>${pdf.ok ? "Ready" : pdf.failure_message || "Unavailable"}</p></div>
    </div>
  `;
  openInterpretationReviewDrawer();
  syncInterpretationReviewSurface();
  notifyInterpretationUiStateChanged();
}

export function renderInterpretationGmailResult(payload) {
  const container = qs("interpretation-gmail-result");
  if (!container) {
    return;
  }
  const result = payload.normalized_payload || {};
  const status = payload.status || "ok";
  const draftMessage = result.gmail_draft_result?.message || result.draft_prereqs?.message || "Gmail finalization details are available.";
  const label = status === "ok" ? "Draft ready" : status === "local_only" ? "Local only" : status === "draft_unavailable" ? "Draft unavailable" : "Draft warning";
  const tone = status === "ok" ? "ok" : status === "local_only" ? "warn" : "bad";
  interpretationUiState.completionPayload = payload;
  container.classList.remove("empty-state");
  container.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${escapeHtml(draftMessage)}</strong>
        <p>${escapeHtml(result.pdf_path || result.docx_path || "Final interpretation artifacts are available.")}</p>
      </div>
      <span class="status-chip ${tone === "ok" ? "ok" : tone === "warn" ? "warn" : "bad"}">${escapeHtml(label)}</span>
    </div>
    <div class="result-grid">
      <div><h3>DOCX</h3><p class="word-break">${escapeHtml(result.docx_path || "Unavailable")}</p></div>
      <div><h3>PDF</h3><p class="word-break">${escapeHtml(result.pdf_path || "Unavailable")}</p></div>
      <div><h3>Draft</h3><p>${escapeHtml(draftMessage)}</p></div>
    </div>
  `;
  openInterpretationReviewDrawer();
  syncInterpretationReviewSurface();
  notifyInterpretationUiStateChanged();
}

function renderDashboard(payload) {
  const counts = payload.normalized_payload.recent_job_counts || { total: 0, translation: 0, interpretation: 0 };
  const runtime = payload.normalized_payload.runtime;
  qs("dashboard-summary").textContent = `${counts.total} total job-log rows in ${runtime.runtime_mode_label}. ${counts.interpretation} interpretation row(s) and ${counts.translation} translation row(s) are available in this mode.`;
  renderDashboardCards(payload.normalized_payload.dashboard_cards || []);
  renderParityAudit(payload);
}

function renderParityAudit(payload) {
  const audit = payload.normalized_payload.parity_audit || {};
  const checklist = audit.checklist || [];
  const cards = checklist.map((item) => ({
    title: item.title,
    text: item.description,
    status: item.status === "ready" ? "ok" : item.status === "blocked" ? "bad" : "warn",
    label: item.status === "ready" ? "Ready" : item.status.replaceAll("_", " "),
  }));
  qs("parity-audit-status").textContent = audit.summary || "Browser-app readiness summary is unavailable.";
  renderCapabilityCards("parity-audit-grid", cards);
  const recommendation = audit.promotion_recommendation || {};
  const remaining = (audit.remaining_limitations || []).map((item) => `<li>${item}</li>`).join("");
  const workflows = (recommendation.recommended_workflows || []).map((item) => `<li>${item}</li>`).join("");
  const result = qs("parity-audit-result");
  const recommendationReady = recommendation.status === "ready_for_daily_use";
  result.classList.remove("empty-state");
  result.innerHTML = `
    <div class="result-header">
      <div>
        <strong>${recommendation.headline || "Promotion recommendation unavailable."}</strong>
        <p>${audit.ready_count || 0}/${audit.total_count || 0} audit areas are marked ready.</p>
      </div>
      <span class="status-chip ${recommendationReady ? "ok" : "warn"}">${recommendationReady ? "Ready now" : recommendation.status || "unknown"}</span>
    </div>
    <div class="result-grid">
      <div>
        <h3>Recommended Now</h3>
        <ul>${workflows || "<li>No recommendation items available.</li>"}</ul>
      </div>
      <div>
        <h3>Intentional Limits</h3>
        <ul>${remaining || "<li>No limitations recorded.</li>"}</ul>
      </div>
    </div>
  `;
}

function renderSettings(payload) {
  const summary = payload.normalized_payload.settings_summary || {};
  const providerState = payload.normalized_payload.settings_admin?.provider_state || {};
  const translation = providerState.translation || {};
  const ocr = providerState.ocr || {};
  const gmailDraft = providerState.gmail_draft || {};
  const wordPdf = providerState.word_pdf_export || {};
  const translationReady = translation.credentials_configured === true;
  const translationSource = describeCredentialSource(
    translation.effective_credential_source || translation.credential_source,
  );
  const items = [
    { label: "Theme", value: summary.ui_theme || "Unknown" },
    { label: "Default Language", value: summary.default_lang || "Unknown" },
    { label: "Default Output Directory", value: summary.default_outdir || "Not configured" },
    { label: "Translation Auth", value: translationReady ? `Configured via ${translationSource}` : "Not configured" },
    { label: "OCR Defaults", value: `${summary.ocr_mode_default || "?"} / ${summary.ocr_engine_default || "?"} / ${summary.ocr_api_provider_default || "?"}` },
    { label: "Gmail Bridge", value: summary.gmail_intake_bridge_enabled ? `Enabled on ${summary.gmail_intake_port}` : "Disabled" },
    { label: "Settings File", value: summary.settings_path || "Unavailable" },
    { label: "Job Log DB", value: summary.job_log_db_path || "Unavailable" },
    { label: "Outputs Root", value: summary.outputs_dir || "Unavailable" },
  ];
  renderSummaryGrid("settings-summary-grid", items);
  const settingsTone = translationReady && wordPdf.ok && (ocr.api_configured || ocr.local_available) && gmailDraft.ready ? "ok" : "warn";
  setPanelStatus(
    "settings",
    settingsTone,
    `Showing ${summary.runtime_label || "current"} settings with translation auth ${translationReady ? `configured via ${translationSource}` : "not configured"}, OCR ${ocr.provider || "provider"} ${ocr.api_configured || ocr.local_available ? "ready" : "not ready"}, Gmail drafts ${gmailDraft.ready ? "ready" : "not ready"}, and Word PDF export ${wordPdf.ok ? "ready" : "degraded"}.`,
  );
}

function renderProfile(payload) {
  const summary = payload.normalized_payload.profile_summary || {};
  const primary = summary.primary_profile;
  const importButton = qs("import-live-profiles");
  const newButton = qs("new-profile");
  importButton.disabled = appState.runtimeMode === "live";
  importButton.textContent = appState.runtimeMode === "live" ? "Live Profiles Active" : "Import Live Profiles";
  if (newButton) {
    newButton.disabled = false;
  }
  if (!primary) {
    qs("profile-primary-card").innerHTML = "No primary profile is configured for this runtime mode.";
  } else {
    qs("profile-primary-card").innerHTML = `
      <div class="result-header">
        <div>
          <strong>${primary.document_name || primary.id}</strong>
          <p>${primary.email || "No email saved"} | ${primary.travel_origin_label || "No travel origin label"}</p>
        </div>
        <span class="status-chip ok">Primary</span>
      </div>
      <div class="history-meta"><small>Travel city distances: ${primary.distance_city_count}</small></div>
    `;
  }
  const container = qs("profile-list");
  container.innerHTML = "";
  for (const profile of summary.profiles || []) {
    const article = document.createElement("article");
    article.className = "profile-card";
    article.innerHTML = `
      <div class="result-header">
        <div>
          <h3>${profile.document_name || profile.id}</h3>
          <p>${profile.email || "No email"} | ${profile.travel_origin_label || "No travel origin label"}</p>
        </div>
        <span class="status-chip ${profile.is_primary ? "ok" : "info"}">${profile.is_primary ? "Primary" : `${profile.distance_city_count} city distances`}</span>
      </div>
    `;
    const actions = document.createElement("div");
    actions.className = "history-actions";
    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.textContent = "Edit";
    editButton.addEventListener("click", () => applyProfileEditor(cloneJson(profile), { openDrawer: true }));
    const primaryButton = document.createElement("button");
    primaryButton.type = "button";
    primaryButton.textContent = profile.is_primary ? "Primary" : "Set Primary";
    primaryButton.disabled = Boolean(profile.is_primary);
    primaryButton.addEventListener("click", async () => {
      try {
        await handleSetPrimaryProfile(profile.id);
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "Set-primary failed.");
        setDiagnostics("profile", error, { hint: error.message || "Set-primary failed.", open: true });
      }
    });
    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.textContent = "Delete";
    deleteButton.disabled = Boolean(summary.count <= 1);
    deleteButton.addEventListener("click", async () => {
      try {
        await handleDeleteProfile(profile.id);
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "Profile delete failed.");
        setDiagnostics("profile", error, { hint: error.message || "Profile delete failed.", open: true });
      }
    });
    actions.appendChild(editButton);
    actions.appendChild(primaryButton);
    actions.appendChild(deleteButton);
    article.appendChild(actions);
    container.appendChild(article);
  }
  setPanelStatus("profile", "", `${summary.count || 0} profile(s) loaded for ${payload.normalized_payload.runtime.runtime_mode_label}.`);
  setDiagnostics("profile", summary, {
    hint: "Profile summaries, required fields, and travel-distance mappings for the active runtime mode.",
    open: false,
  });
  const selectedId = profileState.currentProfileId;
  const selectedProfile = (summary.profiles || []).find((profile) => profile.id === selectedId)
    || primary
    || summary.profiles?.[0]
    || blankProfileDraft();
  applyProfileEditor(cloneJson(selectedProfile), { openDrawer: false });
}

function renderExtensionLab(payload) {
  const data = payload.normalized_payload.extension_lab || {};
  appState.extensionDiagnostics = data;
  const prepare = data.prepare_response || {};
  const extensionReport = data.extension_report || {};
  const bridgeSummary = data.bridge_summary || {};
  const cards = [
    {
      title: "Native Host Prepare",
      text: `Reason: ${prepare.reason || "unknown"}\nUI owner: ${prepare.ui_owner || "none"}\nAuto-launch ready: ${prepare.autoLaunchReady === true ? "yes" : "no"}\nLaunch target: ${prepare.browser_url || prepare.launchTarget || "Unavailable"}`,
      status: bridgeSummary.status || (prepare.ok === true ? "ok" : "warn"),
      label: bridgeSummary.status === "info" ? "Informational" : prepare.ok === true ? "Ready" : "Needs attention",
    },
    {
      title: "Extension Discovery",
      text: `Stable ID: ${extensionReport.stable_extension_id || "unknown"}\nActive unpacked installs: ${(extensionReport.active_extension_ids || []).length}\nStale installs: ${(extensionReport.stale_extension_ids || []).length}`,
      status: "ok",
      label: "Reported",
    },
    {
      title: "Mode Context",
      text: (data.notes || []).join("\n") || "No extension-lab notes.",
      status: payload.normalized_payload.runtime.live_data ? "warn" : "ok",
      label: payload.normalized_payload.runtime.live_data ? "Live mode" : "Shadow mode",
    },
  ];
  renderCapabilityCards("extension-status-grid", cards);
  const extensionTone = bridgeSummary.status || (prepare.ok === true ? "ok" : "warn");
  setPanelStatus("extension", extensionTone, prepare.ok === true ? "The current runtime mode is ready for extension handoff." : bridgeSummary.message || "Extension diagnostics loaded. Review prepare status and simulator output below.");
  setDiagnostics("extension", { prepare_response: prepare, extension_report: extensionReport, bridge_summary: bridgeSummary, notes: data.notes || [] }, {
    hint: "Native host readiness, extension discovery, and bridge preparation details.",
    open: false,
  });
  const defaults = data.simulator_defaults || {};
  if (!fieldValue("sim-message-id")) {
    setFieldValue("sim-message-id", defaults.message_id || "");
  }
  if (!fieldValue("sim-thread-id")) {
    setFieldValue("sim-thread-id", defaults.thread_id || "");
  }
  if (!fieldValue("sim-subject")) {
    setFieldValue("sim-subject", defaults.subject || "");
  }
  if (!fieldValue("sim-account-email")) {
    setFieldValue("sim-account-email", defaults.account_email || "");
  }
  const reasonCatalog = qs("extension-reason-catalog");
  if (reasonCatalog) {
    reasonCatalog.innerHTML = "";
    for (const item of data.prepare_reason_catalog || []) {
      const card = document.createElement("article");
      card.className = "history-item";
      card.innerHTML = `<div><strong>${item.reason}</strong><p>${item.message}</p></div>`;
      reasonCatalog.appendChild(card);
    }
    if (!reasonCatalog.children.length) {
      reasonCatalog.innerHTML = '<div class="empty-state">No prepare reasons are available.</div>';
    }
  }
}

function showLiveBanner(runtime) {
  const banner = qs("live-banner");
  if (runtime.live_data) {
    banner.textContent = runtime.banner_text || "LIVE APP DATA is active.";
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
    banner.textContent = "";
  }
}

function renderTopbar(payload) {
  const runtime = payload.normalized_payload.runtime;
  qs("workspace-id-label").textContent = runtime.workspace_id;
  qs("runtime-mode-label").textContent = runtime.runtime_mode_label;
  setTopbarStatus(runtime.live_data
    ? `Live workspace ${runtime.workspace_id}: real settings, Gmail bridge, and job-log writes are active here.`
    : `Shadow workspace ${runtime.workspace_id}: isolated browser-app data stays separate from live mode.`, runtime.live_data ? "info" : "ok");
  showLiveBanner(runtime);
}

function renderRuntimeModeSelector(payload) {
  const runtimeMode = payload.normalized_payload.runtime_mode || {};
  const select = qs("runtime-mode-select");
  select.innerHTML = "";
  for (const mode of runtimeMode.supported_modes || []) {
    const option = document.createElement("option");
    option.value = mode.id;
    option.textContent = mode.label;
    if (mode.id === runtimeMode.current_mode) {
      option.selected = true;
    }
    select.appendChild(option);
  }
}

function renderBootstrap(payload) {
  appState.bootstrap = payload;
  const gmailBootstrap = payload.normalized_payload.gmail || {};
  renderNavigation(payload.normalized_payload.navigation || []);
  renderRuntimeModeSelector(payload);
  renderTopbar(payload);
  renderProfiles(payload.normalized_payload.profiles || [], payload.normalized_payload.primary_profile_id);
  refreshInterpretationCitySelectors();
  renderHistory(payload.normalized_payload.history || [], payload.normalized_payload.runtime.runtime_mode_label);
  renderRecentJobs(
    payload.normalized_payload.recent_jobs || [],
    payload.normalized_payload.history || [],
    payload.normalized_payload.translation?.history || [],
  );
  renderDashboard(payload);
  renderSettings(payload);
  renderPowerToolsBootstrap(payload);
  renderProfile(payload);
  renderExtensionLab(payload);
  renderGmailBootstrap(payload);
  renderStatus(payload);
  renderTranslationBootstrap(payload);
  renderShellVisibility();
  if (
    !appState.currentSeed
    && gmailBootstrap.active_session?.kind === "interpretation"
    && gmailBootstrap.interpretation_seed
  ) {
    applyInterpretationSeed(gmailBootstrap.interpretation_seed, { activateTask: appState.activeView === "new-job" });
  } else if (!appState.currentSeed && payload.normalized_payload.blank_seed) {
    applyInterpretationSeed(payload.normalized_payload.blank_seed, { activateTask: false });
  } else {
    refreshInterpretationCitySelectors();
  }
  syncInterpretationReviewSurface();
  syncClientHydrationMarker({ payload: payload.normalized_payload });
}

function applyShellBootstrapSnapshot(payload) {
  const shellPayload = payload?.normalized_payload?.shell || {};
  const runtimeMode = String(shellPayload.runtime_mode || appState.runtimeMode || "shadow").trim();
  const workspaceId = String(shellPayload.workspace_id || appState.workspaceId || "workspace-1").trim();
  const shellReady = shellPayload.ready === true;
  qs("workspace-id-label").textContent = workspaceId || "workspace-1";
  qs("runtime-mode-label").textContent = runtimeMode === "live" ? "Live App Data" : "Isolated Test Data";
  if (workspaceId === "gmail-intake") {
    setTopbarStatus(
      shellReady
        ? "Browser shell is ready. Finishing Gmail workspace hydration..."
        : "Warming the browser shell, Gmail bridge, and workspace...",
      shellReady ? "info" : "warn",
    );
    setPanelStatus(
      "runtime",
      shellReady ? "info" : "warn",
      shellReady
        ? "Browser shell is responding. Loading the Gmail workspace UI..."
        : "Browser shell is still warming for the Gmail workspace.",
    );
    return;
  }
  setTopbarStatus(
    shellReady
      ? "Browser shell is ready. Finishing browser workspace hydration..."
      : "Warming the browser shell and app capabilities...",
    shellReady ? "info" : "warn",
  );
  setPanelStatus(
    "runtime",
    shellReady ? "info" : "warn",
    shellReady
      ? "Browser shell is responding. Loading the full workspace UI..."
      : "Browser shell is still warming.",
  );
}

function applyStagedBootstrapRetryStatus({ attempt, maxAttempts, error }) {
  const target = appState.workspaceId === "gmail-intake" || appState.activeView === "gmail-intake"
    ? "Gmail workspace"
    : "browser workspace";
  const detail = error?.message ? ` ${error.message}` : "";
  setTopbarStatus(
    `Finishing ${target} hydration (attempt ${attempt} of ${maxAttempts})...`,
    "warn",
  );
  setPanelStatus(
    "runtime",
    "warn",
    `The ${target} is still warming after the shell became ready.${detail}`,
  );
}

function populateIdleDiagnostics() {
  if (!qs("autofill-diagnostics").textContent.trim()) {
    setDiagnostics("autofill", { status: "idle", message: "No upload has been run yet." }, { hint: "Metadata extraction details appear here after an upload.", open: false });
  }
  if (!qs("form-diagnostics").textContent.trim()) {
    setDiagnostics("form", { status: "idle", message: "No save or export has been run yet." }, { hint: "Save/export responses and validation details appear here.", open: false });
  }
  if (!qs("profile-diagnostics").textContent.trim()) {
    setDiagnostics("profile", { status: "idle", message: "No profile save, delete, or import has been run yet." }, { hint: "Profile saves, deletes, and import details appear here.", open: false });
  }
  if (!qs("simulator-diagnostics").textContent.trim()) {
    setDiagnostics("simulator", { status: "idle", message: "No simulator run has been executed yet." }, { hint: "Preview request payload, bridge endpoint, and readiness.", open: false });
  }
}

async function loadBootstrap({ staged = false } = {}) {
  setClientHydrationMarker("warming", {
    payload: appState.bootstrap?.normalized_payload,
  });
  try {
    let payload;
    if (staged) {
      const stagedResult = await runStagedBootstrap({
        routeContext: {
          workspaceId: appState.workspaceId,
          activeView: appState.activeView,
        },
        fetchShell: async () => {
          const shellPayload = await fetchJson("/api/bootstrap/shell/ready", appState);
          assertServerAssetVersionMatchesClient(shellPayload);
          applyShellBootstrapSnapshot(shellPayload);
          return shellPayload;
        },
        fetchFull: () => fetchJson("/api/bootstrap", appState),
        onRetry: applyStagedBootstrapRetryStatus,
      });
      payload = stagedResult.fullPayload;
    } else {
      payload = await fetchJson("/api/bootstrap", appState);
    }
    assertServerAssetVersionMatchesClient(payload);
    renderBootstrap(payload);
    populateIdleDiagnostics();
    setClientHydrationMarker("ready", {
      payload: payload.normalized_payload,
    });
    return payload;
  } catch (error) {
    setClientHydrationMarker("client_boot_failed", {
      payload: appState.bootstrap?.normalized_payload,
      reason: error?.payload?.diagnostics?.error || error?.name || "bootstrap_failed",
      message: error?.message || "Browser app bootstrap failed.",
    });
    throw error;
  }
}

async function reloadHistory() {
  const payload = await fetchJson("/api/interpretation/history", appState);
  renderHistory(payload.normalized_payload.history || [], appState.bootstrap?.normalized_payload?.runtime?.runtime_mode_label || "Current");
  renderRecentJobs(
    appState.bootstrap?.normalized_payload?.recent_jobs || [],
    payload.normalized_payload.history || [],
    appState.bootstrap?.normalized_payload?.translation?.history || [],
  );
  await refreshTranslationHistory();
}

async function refreshExtensionLab() {
  const payload = await fetchJson("/api/extension/diagnostics", appState);
  renderExtensionLab({
    ...appState.bootstrap,
    normalized_payload: {
      ...appState.bootstrap.normalized_payload,
      extension_lab: payload.normalized_payload,
      runtime: payload.normalized_payload.runtime || appState.bootstrap.normalized_payload.runtime,
    },
    diagnostics: { ...appState.bootstrap.diagnostics, runtime: payload.diagnostics.runtime },
    capability_flags: payload.capability_flags,
  });
}

async function handleUpload(formId, endpoint) {
  const form = qs(formId);
  const data = new FormData(form);
  const payload = await fetchJson(endpoint, appState, { method: "POST", body: data });
  if (payload.normalized_payload) {
    applyInterpretationSeed(payload.normalized_payload);
  }
  const extractedFields = payload.diagnostics?.metadata_extraction?.extracted_fields || [];
  const message = extractedFields.length ? `Recovered ${extractedFields.join(", ")} from the uploaded file.` : "No metadata fields were recovered automatically.";
  setPanelStatus("autofill", extractedFields.length ? "ok" : "warn", message);
  setDiagnostics("autofill", payload.diagnostics, { hint: message, open: !extractedFields.length });
  openInterpretationReviewDrawer();
}

async function handleSave() {
  await prepareInterpretationAction("save");
  const payload = await fetchJson("/api/interpretation/save-row", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      form_values: collectInterpretationFormValues(),
      seed_payload: appState.currentSeed,
      row_id: appState.currentRowId,
      profile_id: qs("profile-id").value,
      service_same_checked: qs("service-same").checked,
      use_service_location_in_honorarios_checked: qs("use-service-location").checked,
      include_transport_sentence_in_honorarios_checked: qs("include-transport").checked,
    }),
  });
  appState.currentRowId = payload.saved_result.row_id;
  qs("row-id").value = payload.saved_result.row_id;
  setPanelStatus("form", "ok", `Saved row #${payload.saved_result.row_id} to the active job log.`);
  setDiagnostics("form", payload, { hint: `Saved row #${payload.saved_result.row_id}.`, open: false });
  await loadBootstrap();
  syncInterpretationReviewSurface();
  openInterpretationReviewDrawer();
}

async function handleExport() {
  await prepareInterpretationAction("export");
  const payload = await fetchJson("/api/interpretation/export-honorarios", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      form_values: collectInterpretationFormValues(),
      profile_id: qs("profile-id").value,
      output_filename: fieldValue("output-filename"),
      service_same_checked: qs("service-same").checked,
      use_service_location_in_honorarios_checked: qs("use-service-location").checked,
      include_transport_sentence_in_honorarios_checked: qs("include-transport").checked,
    }),
  });
  const message = payload.status === "ok" ? "Generated DOCX and PDF successfully." : "DOCX is ready, but PDF export stayed in local-only mode.";
  setPanelStatus("form", payload.status === "ok" ? "ok" : "warn", message);
  setDiagnostics("form", payload, { hint: message, open: payload.status !== "ok" });
  renderInterpretationExportResult(payload);
}

async function handleImportLiveProfiles() {
  const payload = await fetchJson("/api/profiles/import-live", appState, { method: "POST" });
  const importedCount = payload.normalized_payload?.imported_profile_count ?? 0;
  const message = importedCount > 0 ? `Imported ${importedCount} live profile${importedCount === 1 ? "" : "s"} into the isolated browser workspace.` : payload.normalized_payload?.message || "Live profiles are already active in this mode.";
  await loadBootstrap();
  setPanelStatus("profile", "ok", message);
  setDiagnostics("profile", payload, {
    hint: importedCount > 0 ? `Imported ${importedCount} profile(s).` : payload.normalized_payload?.message || "Live profiles already active.",
    open: false,
  });
}

async function handleNewProfile() {
  const payload = await fetchJson("/api/profile/new", appState);
  applyProfileEditor(payload.normalized_payload?.profile || blankProfileDraft(), { openDrawer: true });
  setPanelStatus("profile", "", "New profile draft loaded. Fill the required fields, then save it.");
  setDiagnostics("profile", payload, {
    hint: "New profile draft loaded.",
    open: false,
  });
  setActiveView("profile");
  renderShellVisibility();
}

async function handleSaveProfile() {
  const makePrimary = qs("profile-editor-make-primary").checked;
  const payload = await fetchJson("/api/profile/save", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      profile: collectProfileFormValues(),
      make_primary: makePrimary,
    }),
  });
  const savedProfile = payload.normalized_payload?.saved_profile || {};
  profileState.currentProfileId = savedProfile.id || "";
  const message = payload.normalized_payload?.message || `Saved profile ${savedProfile.document_name || savedProfile.id || ""}.`;
  await loadBootstrap();
  setPanelStatus("profile", "ok", message);
  setDiagnostics("profile", payload, {
    hint: payload.normalized_payload?.message || "Profile saved.",
    open: false,
  });
}

async function handleDeleteProfile(profileId = fieldValue("profile-editor-id")) {
  const resolvedId = String(profileId || "").trim();
  if (!resolvedId) {
    throw new Error("Select a saved profile before deleting it.");
  }
  if (!window.confirm(`Delete profile ${resolvedId} from the active runtime mode?`)) {
    return;
  }
  const payload = await fetchJson("/api/profile/delete", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: resolvedId }),
  });
  profileState.currentProfileId = "";
  const message = payload.normalized_payload?.message || `Deleted profile ${resolvedId}.`;
  await loadBootstrap();
  closeProfileEditorDrawer();
  setPanelStatus("profile", "ok", message);
  setDiagnostics("profile", payload, {
    hint: payload.normalized_payload?.message || `Deleted profile ${resolvedId}.`,
    open: false,
  });
}

async function handleSetPrimaryProfile(profileId = fieldValue("profile-editor-id")) {
  const resolvedId = String(profileId || "").trim();
  if (!resolvedId) {
    throw new Error("Select a saved profile before setting it as primary.");
  }
  const payload = await fetchJson("/api/profile/set-primary", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: resolvedId }),
  });
  profileState.currentProfileId = resolvedId;
  const message = payload.normalized_payload?.message || `Set profile ${resolvedId} as primary.`;
  await loadBootstrap();
  setPanelStatus("profile", "ok", message);
  setDiagnostics("profile", payload, {
    hint: payload.normalized_payload?.message || `Set profile ${resolvedId} as primary.`,
    open: false,
  });
}

function resetFormToBlank() {
  if (appState.bootstrap?.normalized_payload?.blank_seed) {
    applyInterpretationSeed(appState.bootstrap.normalized_payload.blank_seed);
    setCheckbox("service-same", true);
    setCheckbox("use-service-location", false);
    setCheckbox("include-transport", true);
    updateServiceFieldState();
    setPanelStatus("form", "", "Blank interpretation entry loaded. Fill fields manually or use autofill above.");
    setDiagnostics("form", { status: "ok", message: "Blank interpretation seed loaded." }, { hint: "Blank interpretation seed loaded.", open: false });
    openInterpretationReviewDrawer();
  }
}

async function handleRuntimeModeChange() {
  const requestedMode = qs("runtime-mode-select").value;
  const payload = await fetchJson("/api/runtime-mode", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mode: requestedMode, workspace_id: appState.workspaceId }),
  });
  setRuntimeMode(payload.normalized_payload.current_mode);
  await loadBootstrap();
}

async function handleExtensionSimulation() {
  const payload = await fetchJson("/api/extension/simulate-handoff", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message_context: {
        message_id: fieldValue("sim-message-id"),
        thread_id: fieldValue("sim-thread-id"),
        subject: fieldValue("sim-subject"),
        account_email: fieldValue("sim-account-email"),
      },
      mode: appState.runtimeMode,
      workspace_id: appState.workspaceId,
    }),
  });
  const message = payload.status === "ok" ? "Handoff simulation is ready to POST to the localhost bridge." : "Handoff simulation completed, but the bridge is not currently ready.";
  setPanelStatus("simulator", payload.status === "ok" ? "ok" : "warn", message);
  setDiagnostics("simulator", payload, { hint: message, open: true });
}

function setBusy(buttonIds, busy, busyLabels = {}) {
  for (const id of buttonIds) {
    const button = qs(id);
    if (!button) {
      continue;
    }
    if (!button.dataset.defaultLabel) {
      button.dataset.defaultLabel = button.textContent;
    }
    button.disabled = busy;
    button.setAttribute("aria-busy", busy ? "true" : "false");
    button.textContent = busy ? busyLabels[id] || button.dataset.defaultLabel : button.dataset.defaultLabel;
  }
}

async function runWithBusy(buttonIds, busyLabels, action) {
  if (buttonIds.some((id) => qs(id)?.disabled)) {
    return;
  }
  setBusy(buttonIds, true, busyLabels);
  try {
    return await action();
  } finally {
    setBusy(buttonIds, false);
  }
}

function wireEvents() {
  window.addEventListener("hashchange", () => {
    syncActiveViewFromLocation();
    if (appState.bootstrap?.normalized_payload) {
      renderNavigation(appState.bootstrap.normalized_payload.navigation || []);
    }
    renderShellVisibility();
    syncClientHydrationMarker();
  });

  window.addEventListener("legalpdf:route-state-changed", () => {
    if (appState.bootstrap?.normalized_payload) {
      renderNavigation(appState.bootstrap.normalized_payload.navigation || []);
    }
    renderShellVisibility();
    syncClientHydrationMarker();
  });

  window.addEventListener("legalpdf:set-new-job-task", (event) => {
    setNewJobTask(event.detail?.task);
  });

  window.addEventListener("legalpdf:bootstrap-invalidated", async () => {
    try {
      await loadBootstrap();
    } catch (error) {
      setPanelStatus("runtime", "bad", error.message || "Browser shell refresh failed.");
      setDiagnostics("runtime", error, { hint: error.message || "Browser shell refresh failed.", open: true });
    }
  });

  window.addEventListener("legalpdf:shell-state-updated", () => {
    if (!appState.bootstrap?.normalized_payload) {
      return;
    }
    renderNavigation(appState.bootstrap.normalized_payload.navigation || []);
    renderShellVisibility();
    syncClientHydrationMarker();
  });

  document.addEventListener("click", (event) => {
    const navButton = event.target.closest(".nav-button");
    if (navButton) {
      setActiveView(navButton.dataset.view);
      return;
    }
    const taskButton = event.target.closest(".task-switch");
    if (taskButton) {
      setNewJobTask(taskButton.dataset.task);
      return;
    }
    const target = event.target.closest("[data-target-view]");
    if (!target) {
      return;
    }
    setActiveView(target.dataset.targetView);
  });

  qs("operator-mode-toggle")?.addEventListener("click", () => {
    setOperatorMode(!appState.operatorMode);
  });

  qs("notification-upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusy(["notification-submit"], { "notification-submit": "Autofilling..." }, async () => {
      try {
        setPanelStatus("autofill", "", "Running notification OCR and metadata recovery...");
        await handleUpload("notification-upload-form", "/api/interpretation/autofill-notification");
      } catch (error) {
        setPanelStatus("autofill", "bad", error.message || "Notification autofill failed.");
        setDiagnostics("autofill", error, { hint: error.message || "Notification autofill failed.", open: true });
      }
    });
  });

  qs("photo-upload-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusy(["photo-submit"], { "photo-submit": "Autofilling..." }, async () => {
      try {
        setPanelStatus("autofill", "", "Running photo/screenshot metadata recovery...");
        await handleUpload("photo-upload-form", "/api/interpretation/autofill-photo");
      } catch (error) {
        setPanelStatus("autofill", "bad", error.message || "Photo autofill failed.");
        setDiagnostics("autofill", error, { hint: error.message || "Photo autofill failed.", open: true });
      }
    });
  });

  qs("save-row").addEventListener("click", async () => {
    await runWithBusy(["save-row", "export-honorarios", "clear-form", "reload-history"], { "save-row": "Saving..." }, async () => {
      try {
        setPanelStatus("form", "", "Saving the interpretation row...");
        await handleSave();
      } catch (error) {
        recoverInterpretationValidationError(error);
        setPanelStatus("form", "bad", error.message || "Save failed.");
        setDiagnostics("form", error, { hint: error.message || "Save failed.", open: true });
      }
    });
  });

  qs("export-honorarios").addEventListener("click", async () => {
    await runWithBusy(["save-row", "export-honorarios", "clear-form", "reload-history"], { "export-honorarios": "Generating..." }, async () => {
      try {
        setPanelStatus("form", "", "Generating honorários DOCX and PDF...");
        await handleExport();
      } catch (error) {
        recoverInterpretationValidationError(error);
        setPanelStatus("form", "bad", error.message || "Export failed.");
        setDiagnostics("form", error, { hint: error.message || "Export failed.", open: true });
      }
    });
  });
  qs("interpretation-open-review")?.addEventListener("click", openInterpretationReviewDrawer);
  qs("interpretation-session-primary")?.addEventListener("click", openInterpretationReviewDrawer);
  qs("interpretation-close-review")?.addEventListener("click", closeInterpretationReviewDrawer);
  qs("interpretation-close-review-footer")?.addEventListener("click", closeInterpretationReviewDrawer);
  qs("interpretation-clear-review")?.addEventListener("click", resetFormToBlank);
  qs("interpretation-review-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("interpretation-review-drawer-backdrop")) {
      closeInterpretationReviewDrawer();
    }
  });
  qs("profile-close-editor")?.addEventListener("click", closeProfileEditorDrawer);
  qs("profile-close-editor-footer")?.addEventListener("click", closeProfileEditorDrawer);
  qs("profile-editor-drawer-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("profile-editor-drawer-backdrop")) {
      closeProfileEditorDrawer();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && interpretationCityState.dialogOpen) {
      closeInterpretationCityDialog(null);
      return;
    }
    if (event.key === "Escape" && interpretationUiState.reviewDrawerOpen) {
      closeInterpretationReviewDrawer();
      return;
    }
    if (event.key === "Escape" && profileUiState.editorDrawerOpen) {
      closeProfileEditorDrawer();
    }
  });

  qs("use-service-location")?.addEventListener("change", syncInterpretationDisclosureState);
  qs("include-transport")?.addEventListener("change", () => {
    syncInterpretationDisclosureState();
    syncInterpretationCityControls();
  });
  qs("recipient-block")?.addEventListener("input", syncInterpretationDisclosureState);

  qs("import-live-profiles").addEventListener("click", async () => {
    await runWithBusy(["import-live-profiles", "new-profile", "profile-save", "profile-set-primary", "profile-delete"], { "import-live-profiles": "Importing..." }, async () => {
      try {
        await handleImportLiveProfiles();
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "Profile import failed.");
        setDiagnostics("profile", error, { hint: error.message || "Profile import failed.", open: true });
      }
    });
  });

  qs("new-profile").addEventListener("click", async () => {
    await runWithBusy(["import-live-profiles", "new-profile", "profile-save", "profile-set-primary", "profile-delete"], { "new-profile": "Preparing..." }, async () => {
      try {
        await handleNewProfile();
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "New profile failed.");
        setDiagnostics("profile", error, { hint: error.message || "New profile failed.", open: true });
      }
    });
  });

  qs("profile-save").addEventListener("click", async () => {
    await runWithBusy(["import-live-profiles", "new-profile", "profile-save", "profile-set-primary", "profile-delete"], { "profile-save": "Saving..." }, async () => {
      try {
        await handleSaveProfile();
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "Profile save failed.");
        setDiagnostics("profile", error, { hint: error.message || "Profile save failed.", open: true });
      }
    });
  });

  qs("profile-set-primary").addEventListener("click", async () => {
    await runWithBusy(["import-live-profiles", "new-profile", "profile-save", "profile-set-primary", "profile-delete"], { "profile-set-primary": "Updating..." }, async () => {
      try {
        await handleSetPrimaryProfile();
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "Set-primary failed.");
        setDiagnostics("profile", error, { hint: error.message || "Set-primary failed.", open: true });
      }
    });
  });

  qs("profile-delete").addEventListener("click", async () => {
    await runWithBusy(["import-live-profiles", "new-profile", "profile-save", "profile-set-primary", "profile-delete"], { "profile-delete": "Deleting..." }, async () => {
      try {
        await handleDeleteProfile();
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "Profile delete failed.");
        setDiagnostics("profile", error, { hint: error.message || "Profile delete failed.", open: true });
      }
    });
  });

  qs("refresh-bootstrap").addEventListener("click", async () => {
    await runWithBusy(["refresh-bootstrap"], { "refresh-bootstrap": "Refreshing..." }, async () => {
      try {
        await loadBootstrap();
      } catch (error) {
        setPanelStatus("runtime", "bad", error.message || "Runtime refresh failed.");
        setDiagnostics("runtime", error, { hint: error.message || "Runtime refresh failed.", open: true });
      }
    });
  });

  qs("reload-history").addEventListener("click", async () => {
    await runWithBusy(["reload-history"], { "reload-history": "Reloading..." }, async () => {
      try {
        await reloadHistory();
        setPanelStatus("recent-jobs", "", "Job-log history refreshed.");
      } catch (error) {
        setPanelStatus("recent-jobs", "bad", error.message || "History reload failed.");
        setDiagnostics("form", error, { hint: error.message || "History reload failed.", open: true });
      }
    });
  });

  qs("refresh-extension").addEventListener("click", async () => {
    await runWithBusy(["refresh-extension"], { "refresh-extension": "Refreshing..." }, async () => {
      try {
        await refreshExtensionLab();
      } catch (error) {
        setPanelStatus("extension", "bad", error.message || "Extension diagnostics refresh failed.");
        setDiagnostics("extension", error, { hint: error.message || "Extension diagnostics refresh failed.", open: true });
      }
    });
  });

  qs("extension-simulator-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusy(["simulate-handoff"], { "simulate-handoff": "Simulating..." }, async () => {
      try {
        await handleExtensionSimulation();
      } catch (error) {
        setPanelStatus("simulator", "bad", error.message || "Simulator request failed.");
        setDiagnostics("simulator", error, { hint: error.message || "Simulator request failed.", open: true });
      }
    });
  });

  qs("runtime-mode-select").addEventListener("change", async () => {
    await runWithBusy(["refresh-bootstrap"], { "refresh-bootstrap": "Switching..." }, async () => {
      try {
        await handleRuntimeModeChange();
      } catch (error) {
        setPanelStatus("runtime", "bad", error.message || "Runtime mode change failed.");
        setDiagnostics("runtime", error, { hint: error.message || "Runtime mode change failed.", open: true });
      }
    });
  });

  qs("clear-form").addEventListener("click", resetFormToBlank);
  qs("service-same").addEventListener("change", updateServiceFieldState);
  qs("case-entity").addEventListener("input", updateServiceFieldState);
  qs("service-entity").addEventListener("input", () => {
    interpretationUiState.validationField = "";
    syncInterpretationReviewSurface();
  });
  for (const id of ["case-number", "court-email", "service-date"]) {
    qs(id).addEventListener("input", () => {
      interpretationUiState.validationField = "";
      syncInterpretationReviewSurface();
    });
  }
  qs("case-city").addEventListener("change", () => {
    interpretationUiState.validationField = "";
    setProvisionalCityValue("case_city", "");
    updateServiceFieldState();
  });
  qs("service-city").addEventListener("change", () => {
    interpretationUiState.validationField = "";
    setProvisionalCityValue("service_city", "");
    syncInterpretationCityControls();
    syncInterpretationReviewSurface();
  });
  qs("travel-km-outbound").addEventListener("input", () => {
    interpretationUiState.validationField = "";
    interpretationCityState.manualDistance = Boolean(fieldValue("travel-km-outbound"));
    if (!interpretationCityState.manualDistance) {
      interpretationCityState.autoDistanceCity = "";
    }
    syncInterpretationCityControls();
    syncInterpretationReviewSurface();
  });
  qs("profile-id").addEventListener("change", () => {
    refreshInterpretationCitySelectors();
    applyInterpretationCityValue("case_city", displayedInterpretationCity("case_city"));
    applyInterpretationCityValue("service_city", displayedInterpretationCity("service_city"));
    syncInterpretationCityControls();
  });
  qs("case-city-add").addEventListener("click", async () => {
    try {
      await promptToAddInterpretationCity("case_city");
    } catch (error) {
      recoverInterpretationValidationError(error);
      setPanelStatus("form", "bad", error.message || "Unable to save the city yet.");
      setDiagnostics("form", error, { hint: error.message || "Unable to save the city yet.", open: true });
    }
  });
  qs("service-city-add").addEventListener("click", async () => {
    try {
      await promptToAddInterpretationCity("service_city");
    } catch (error) {
      recoverInterpretationValidationError(error);
      setPanelStatus("form", "bad", error.message || "Unable to save the city yet.");
      setDiagnostics("form", error, { hint: error.message || "Unable to save the city yet.", open: true });
    }
  });
  qs("interpretation-city-dialog-close")?.addEventListener("click", () => closeInterpretationCityDialog(null));
  qs("interpretation-city-dialog-cancel")?.addEventListener("click", () => closeInterpretationCityDialog(null));
  qs("interpretation-city-dialog-backdrop")?.addEventListener("click", (event) => {
    if (event.target === qs("interpretation-city-dialog-backdrop")) {
      closeInterpretationCityDialog(null);
    }
  });
  qs("interpretation-city-dialog-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const requireDistance = interpretationCityState.activeDialog.requireDistance;
    const cityName = normalizeCityName(fieldValue("interpretation-city-dialog-name"));
    const distanceValue = fieldValue("interpretation-city-dialog-distance");
    if (!cityName) {
      qs("interpretation-city-dialog-name")?.focus();
      return;
    }
    if (requireDistance) {
      const numeric = Number(String(distanceValue || "").trim().replace(",", "."));
      if (!Number.isFinite(numeric) || numeric <= 0) {
        qs("interpretation-city-dialog-distance")?.focus();
        return;
      }
    }
    closeInterpretationCityDialog({ cityName, distanceValue });
  });
  qs("recipient-block").addEventListener("input", syncInterpretationDisclosureState);
}

document.addEventListener("DOMContentLoaded", async () => {
  initializeRouteState(window.LEGALPDF_BROWSER_BOOTSTRAP || {});
  setClientHydrationMarker("warming");
  renderShellVisibility();
  wireEvents();
  initializeTranslationUi();
  initializeGmailUi({
    applyInterpretationSeed,
    collectInterpretationFormValues,
    prepareInterpretationAction,
    recoverInterpretationValidationError,
    getInterpretationUiSnapshot,
    renderInterpretationExportResult,
    renderInterpretationGmailResult,
    applyTranslationLaunch,
    startTranslationLaunch,
    resetTranslationForGmailRedo,
    closeTranslationCompletionDrawer,
    collectCurrentTranslationSaveValues,
    getTranslationUiSnapshot,
    getCurrentTranslationJobId,
    openInterpretationReviewDrawer,
    openTranslationCompletionDrawer,
  });
  initializePowerToolsUi();
  setDiagnostics("runtime", { status: "pending", message: "Loading runtime metadata..." }, { hint: "Build identity, listener ownership, and runtime-mode provenance.", open: false });
  setDiagnostics("autofill", { status: "idle", message: "No upload has been run yet." }, { hint: "Metadata extraction details appear here after an upload.", open: false });
  setDiagnostics("form", { status: "idle", message: "No save or export has been run yet." }, { hint: "Save/export responses and validation details appear here.", open: false });
  setDiagnostics("simulator", { status: "idle", message: "No simulator run has been executed yet." }, { hint: "Preview request payload, bridge endpoint, and readiness.", open: false });
  setDiagnostics("settings-admin", { status: "idle", message: "No settings save has been run yet." }, { hint: "Save responses and provider-state refresh details appear here.", open: false });
  setDiagnostics("settings-test", { status: "idle", message: "No provider preflight has been run yet." }, { hint: "Translation auth, OCR, Gmail, and Word preflight checks appear here.", open: false });
  setDiagnostics("power-tools-glossary", { status: "idle", message: "No glossary action has been run yet." }, { hint: "Glossary saves and markdown export details appear here.", open: false });
  setDiagnostics("power-tools-builder", { status: "idle", message: "No glossary builder run has been executed yet." }, { hint: "Glossary builder results and apply responses appear here.", open: false });
  setDiagnostics("power-tools-calibration", { status: "idle", message: "No calibration audit has been run yet." }, { hint: "Calibration audit report paths and suggestion details appear here.", open: false });
  setDiagnostics("power-tools-diagnostics", { status: "idle", message: "No debug bundle or run report has been generated yet." }, { hint: "Debug bundle and run report outputs appear here.", open: false });
  try {
    await loadBootstrap({ staged: true });
  } catch (error) {
    applyBootstrapFailureState(error);
  }
});
