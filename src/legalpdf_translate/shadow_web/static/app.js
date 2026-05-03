import { describeLocalServerUnavailable, fetchJson, isLocalServerUnavailableError } from "./api.js";
import { runStagedBootstrap } from "./bootstrap_hydration.js";
import { runWithBusy } from "./busy_ui.js";
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
  deriveRecentWorkPresentation,
  deriveTranslationCompletionPresentation,
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
import { renderRecoveryResultInto } from "./recovery_result_ui.js";
import { closeSessionDrawer, initializeGmailUi, renderGmailBootstrap } from "./gmail.js";
import { initializePowerToolsUi, renderPowerToolsBootstrap } from "./power-tools.js";
import { deriveDashboardPresentation } from "./dashboard_presentation.js";
import {
  renderCapabilityCardsInto,
  renderDashboardCardsInto,
  renderDashboardSummaryInto,
  renderParityAuditInto,
  renderSummaryGridInto,
} from "./dashboard_ui.js";
import {
  renderInterpretationHistoryHeadingInto,
  renderInterpretationHistoryInto,
  renderRecentJobsInto,
} from "./recent_work_ui.js";
import {
  renderInterpretationCompletionCardInto,
  renderInterpretationExportPanelResultInto,
  renderInterpretationExportResultInto,
  renderInterpretationGmailResultInto,
  renderInterpretationLocationGuardInto,
  renderInterpretationReviewSummaryStateInto,
  renderInterpretationSeedCardStateInto,
  renderInterpretationSessionCardInto,
  resetInterpretationExportResultInto,
  syncInterpretationCompletionCardVisibilityInto,
} from "./interpretation_result_ui.js";
import {
  focusInterpretationFieldInto,
  renderInterpretationDisclosureSectionsInto,
  renderInterpretationReviewContextInto,
  renderInterpretationReviewSurfaceInto,
  renderInterpretationSessionShellInto,
  syncInterpretationReviewDrawerStateInto,
  syncInterpretationReviewDetailsShellInto,
  syncInterpretationSeedServiceSectionInto,
} from "./interpretation_review_ui.js";
import {
  renderCourtEmailEditorInto,
  renderCourtEmailOptionsInto,
  renderCourtEmailStatusInto,
  renderInterpretationActionButtonsInto,
  renderInterpretationCityDialogContentInto,
  renderInterpretationCityDialogFieldsInto,
  renderInterpretationFormFieldsInto,
  renderInterpretationFieldWarningInto,
  renderInterpretationCityAddButtonsInto,
  renderInterpretationCityOptionsInto,
  renderInterpretationDistanceHintInto,
  renderServiceEntityOptionsInto,
  renderServiceSameControlsInto,
  syncInterpretationCityDialogStateInto,
} from "./interpretation_reference_ui.js";
import {
  buildSettingsCapabilityCards,
  buildSettingsStatusPresentation,
  buildSettingsSummaryItems,
} from "./settings_presentation.js";
import {
  deriveProfilePresentation,
  formatProfileCountStatus,
  normalizeDistanceRows,
  parseDistanceRowsFromJson,
  removeDistanceRow,
  serializeDistanceRows,
  upsertDistanceRow,
} from "./profile_presentation.js";
import {
  renderProfileDistanceJsonInto,
  renderPrimaryProfileCardInto,
  renderProfileDistanceStatusInto,
  renderProfileDistanceRowsInto,
  renderProfileEditorChromeInto,
  renderProfileEditorFieldsInto,
  renderProfileListInto,
  renderProfileOptionsInto,
  renderProfileToolbarInto,
  syncProfileEditorDrawerStateInto,
} from "./profile_ui.js";
import {
  buildInterpretationReference,
  deriveInterpretationDisclosurePresentation,
  deriveInterpretationDrawerLayout,
  deriveInterpretationDistanceSync,
  deriveInterpretationGuardState,
  deriveInterpretationReviewPresentation,
  deriveInterpretationSeedServiceDefaults,
  deriveInterpretationWorkspaceMode,
  deriveCourtEmailSelection,
  normalizeCityName,
  resolveKnownCity,
  serviceEntityOptionsForSelection,
} from "./interpretation_review_state.js";
import {
  beginnerSurfaceTargetLabel as deriveBeginnerSurfaceTargetLabel,
  deriveBeginnerPrimarySurface,
  deriveRouteAwareTopbarStatus,
  isLiveRuntimeMode as deriveLiveRuntimeMode,
  isOperatorRoute,
  runtimeModeBannerText as deriveRuntimeModeBannerText,
  runtimeModeDisplayLabel,
  shouldShowDailyRuntimeModeBanner,
} from "./shell_presentation.js";
import {
  renderNavigationInto,
  renderClientHydrationMarkerInto,
  renderOperatorChromeInto,
  renderShellChromeInto,
  renderRuntimeModeBannerInto,
  renderRuntimeModeSelectorInto,
  renderShellRuntimeLabelsInto,
  renderShellVisibilityInto,
  renderTopbarInto,
} from "./shell_ui.js";
import { syncNewJobTaskControlsInto } from "./new_job_ui.js";
import {
  GOOGLE_PHOTOS_RECONNECT_GUIDANCE,
  buildGooglePhotosPickerDiagnostics,
  googlePhotosPickerBrowserUrl,
  googlePhotosUiState,
  renderGooglePhotosSummaryInto,
  renderGooglePhotosStatus,
  resetGooglePhotosPickerState,
  setGooglePhotosAuthFallback,
  setGooglePhotosPickerFallback,
  updateGooglePhotosPickerDiagnostics,
} from "./google_photos_ui.js";
import { buildExtensionLabCards } from "./extension_lab_presentation.js";
import {
  renderExtensionPrepareReasonCatalogInto,
  renderExtensionSimulatorDefaultsInto,
} from "./extension_lab_ui.js";
import {
  populateIdleDiagnostics,
  setDiagnostics,
  setPanelStatus,
  setTopbarStatus,
} from "./diagnostics_ui.js";

export {
  buildGooglePhotosPickerDiagnostics,
  googlePhotosPickerBrowserUrl,
  googlePhotosUiSafeSnapshot,
  renderGooglePhotosSummaryInto,
  renderGooglePhotosStatus,
  resetGooglePhotosPickerState,
  setGooglePhotosAuthFallback,
  setGooglePhotosPickerAutocloseDisabledForNextLaunch,
  setGooglePhotosPickerFallback,
} from "./google_photos_ui.js";

export {
  renderExtensionPrepareReasonCatalogInto,
  renderExtensionSimulatorDefaultsInto,
} from "./extension_lab_ui.js";
export { renderProfileDistanceRowsInto } from "./profile_ui.js";
export {
  renderCapabilityCardsInto,
  renderDashboardCardsInto,
  renderDashboardSummaryInto,
  renderParityAuditInto,
  renderSummaryGridInto,
} from "./dashboard_ui.js";
export {
  renderInterpretationHistoryHeadingInto,
  renderInterpretationHistoryInto,
  renderRecentJobsInto,
} from "./recent_work_ui.js";
export { renderNavigationInto } from "./shell_ui.js";
export { renderInterpretationExportResultInto } from "./interpretation_result_ui.js";
export { runWithBusy } from "./busy_ui.js";

function qs(id) {
  return document.getElementById(id);
}

function qsa(selector) {
  return Array.from(document.querySelectorAll(selector));
}

function delay(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

const profileState = {
  currentProfileId: "",
};

const profileUiState = {
  editorDrawerOpen: false,
  distanceRows: [],
  distanceJsonDirty: false,
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
  returnFocusId: "",
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

function isLiveRuntimeMode(runtime = {}) {
  return deriveLiveRuntimeMode(runtime, appState.runtimeMode);
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

function deriveClientLaunchSessionUrlState() {
  try {
    const params = new URL(globalThis.window?.location?.href || "").searchParams;
    const parsedSchemaVersion = Number.parseInt(
      String(params.get("launch_session_schema_version") ?? "").trim(),
      10,
    );
    return {
      launchSessionId: String(params.get("launch_session_id") || "").trim(),
      handoffSessionId: String(params.get("handoff_session_id") || "").trim(),
      launchSessionSchemaVersion: Number.isInteger(parsedSchemaVersion) && parsedSchemaVersion > 0
        ? parsedSchemaVersion
        : 0,
    };
  } catch (_error) {
    return {
      launchSessionId: "",
      handoffSessionId: "",
      launchSessionSchemaVersion: 0,
    };
  }
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
  const urlState = deriveClientLaunchSessionUrlState();
  return String(
    urlState.launchSessionId
    || shellLaunchSession.launch_session_id
    || runtimeLaunchSession.launch_session_id
    || "",
  ).trim();
}

function deriveClientHandoffSessionId(payload = appState.bootstrap?.normalized_payload) {
  const gmailPayload = payload?.gmail || payload || {};
  const shellLaunchSession = payload?.shell?.launch_session || {};
  const runtimeLaunchSession = payload?.runtime?.launch_session || {};
  const urlState = deriveClientLaunchSessionUrlState();
  return String(
    urlState.handoffSessionId
    || gmailPayload.handoff_session_id
    || shellLaunchSession.handoff_session_id
    || runtimeLaunchSession.handoff_session_id
    || "",
  ).trim();
}

function deriveClientLaunchSessionSchemaVersion(payload = appState.bootstrap?.normalized_payload) {
  const urlState = deriveClientLaunchSessionUrlState();
  if (urlState.launchSessionSchemaVersion > 0) {
    return urlState.launchSessionSchemaVersion;
  }
  const rawValue = payload?.shell?.extension_launch_session_schema_version;
  const parsed = Number.parseInt(String(rawValue ?? ""), 10);
  if (Number.isInteger(parsed) && parsed > 0) {
    return parsed;
  }
  return 0;
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
  renderClientHydrationMarkerInto({
    body: globalThis.document?.body,
    targetWindow: globalThis.window,
  }, marker);
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
    renderShellRuntimeLabelsInto({
      workspaceLabel: qs("workspace-id-label"),
      runtimeModeLabel: qs("runtime-mode-label"),
      liveBanner: qs("live-banner"),
    }, {
      workspaceLabel: details.workspaceId,
      runtimeModeLabel: details.port === 8888
        ? "Fixed Review Preview"
        : (details.runtimeMode === "live" ? "Live mode" : "Test mode"),
      hideLiveBanner: true,
    });
    setTopbarStatus(details.statusMessage, "bad");
    setPanelStatus("runtime", "bad", details.message);
    setPanelStatus("parity-audit", "bad", details.statusMessage);
    setPanelStatus("translation", "bad", details.message);
    setPanelStatus("gmail", "bad", details.message);
    setDiagnostics("runtime", error, { hint: details.diagnosticsHint, open: true });
    for (const containerId of [
      "parity-audit-result",
      "translation-result",
      "gmail-message-result",
      "gmail-session-result",
    ]) {
      renderRecoveryResultInto(qs(containerId), details);
    }
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
  renderInterpretationCityOptionsInto(select, reference.availableCities, currentValue);
}

function refreshInterpretationCitySelectors() {
  populateInterpretationCitySelect("case_city", fieldValue("case-city"));
  populateInterpretationCitySelect("service_city", fieldValue("service-city"));
}

function populateCourtEmailSelect({ currentEmail = "", seedEmail = "" } = {}) {
  const select = qs("court-email");
  if (!select) {
    return;
  }
  const reference = currentInterpretationReference();
  const selection = deriveCourtEmailSelection({
    reference,
    caseCity: displayedInterpretationCity("case_city"),
    currentEmail: currentEmail || select.value,
    seedEmail,
  });
  renderCourtEmailOptionsInto(select, {
    options: selection.options,
    selectedEmail: selection.email,
  });
}

function populateServiceEntitySelect(selectedValue = "") {
  const select = qs("service-entity");
  if (!select) {
    return;
  }
  const reference = currentInterpretationReference();
  const options = serviceEntityOptionsForSelection(reference, selectedValue || select.value);
  renderServiceEntityOptionsInto(select, options, selectedValue);
}

function refreshInterpretationReferenceBoundControls({ seedEmail = "" } = {}) {
  populateCourtEmailSelect({ currentEmail: fieldValue("court-email"), seedEmail });
  populateServiceEntitySelect(fieldValue("service-entity"));
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
  populateServiceEntitySelect(fieldValue("case-entity"));
  setFieldValue("service-entity", fieldValue("case-entity"));
  setFieldValue("service-city", fieldValue("case-city"));
  setProvisionalCityValue("service_city", provisionalCityValue("case_city"));
}

function syncInterpretationDisclosureState() {
  const serviceSame = qs("service-same")?.checked ?? true;
  const drawerLayout = deriveInterpretationDrawerLayout({
    workspaceMode: interpretationWorkspaceMode(),
    activeSession: interpretationActiveSession(),
    serviceSame,
    validationField: interpretationUiState.validationField,
  });
  const useServiceLocation = qs("use-service-location")?.checked ?? false;
  const includeTransport = qs("include-transport")?.checked ?? true;
  const travelDistance = fieldValue("travel-km-outbound");
  const outputFilename = fieldValue("output-filename");
  const textCustomized = Boolean(useServiceLocation || !includeTransport || travelDistance || outputFilename);
  const recipientOverride = fieldValue("recipient-block");
  const amountsTouched = Boolean(
    fieldValue("pages")
    || fieldValue("word-count")
    || fieldValue("rate-per-word")
    || fieldValue("expected-total")
    || fieldValue("amount-paid")
    || fieldValue("api-cost")
    || fieldValue("profit"),
  );
  const disclosurePresentation = deriveInterpretationDisclosurePresentation({
    serviceSame,
    textCustomized,
    recipientOverride,
    amountsTouched,
    includeTransport,
  });
  renderInterpretationDisclosureSectionsInto({
    serviceDetails: qs("interpretation-service-section"),
    serviceSummary: qs("interpretation-service-section-summary"),
    textDetails: qs("interpretation-text-section"),
    textSummary: qs("interpretation-text-section-summary"),
    recipientDetails: qs("interpretation-recipient-section"),
    recipientSummary: qs("interpretation-recipient-section-summary"),
    amountsDetails: qs("interpretation-amounts-section"),
    amountsSummary: qs("interpretation-amounts-section-summary"),
  }, {
    serviceOpen: drawerLayout.sections.serviceOpen,
    serviceSummary: disclosurePresentation.serviceSummary,
    textOpen: drawerLayout.sections.textOpen,
    textSummary: disclosurePresentation.textSummary,
    recipientOpen: drawerLayout.sections.recipientOpen,
    recipientSummary: disclosurePresentation.recipientSummary,
    amountsOpen: drawerLayout.sections.amountsOpen,
    amountsSummary: disclosurePresentation.amountsSummary,
  });
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

function currentInterpretationPresentation(snapshot = interpretationSnapshot()) {
  const activeSession = interpretationActiveSession();
  const workspaceMode = interpretationWorkspaceMode(snapshot, activeSession);
  return deriveInterpretationReviewPresentation({
    snapshot,
    activeSession,
    workspaceMode,
    hasReviewData: hasInterpretationReviewData(snapshot),
    completionPayload: interpretationUiState.completionPayload,
  });
}

function interpretationReviewButtonLabel(snapshot = interpretationSnapshot()) {
  return currentInterpretationPresentation(snapshot).actions.openReview;
}

function interpretationSessionChip(session, mode, completionPayload = interpretationUiState.completionPayload) {
  const presentation = deriveInterpretationReviewPresentation({
    snapshot: interpretationSnapshot(),
    activeSession: session,
    workspaceMode: mode,
    hasReviewData: hasInterpretationReviewData(interpretationSnapshot()),
    completionPayload,
  });
  const status = String(session?.status || "").trim();
  if (mode === "gmail_completed") {
    const completionStatus = String(completionPayload?.status || "").trim();
    if (completionStatus === "ok") {
      return { tone: "ok", label: presentation.gmailResult.createdLabel };
    }
    if (completionStatus === "local_only") {
      return { tone: "warn", label: presentation.gmailResult.localOnlyLabel };
    }
    if (completionStatus === "draft_unavailable") {
      return { tone: "warn", label: presentation.gmailResult.warningLabel };
    }
    if (completionStatus) {
      return { tone: "bad", label: presentation.gmailResult.warningLabel };
    }
    if (session?.draft_created || status === "draft_ready") {
      return { tone: "ok", label: presentation.gmailResult.createdLabel };
    }
    if (String(session?.draft_failure_reason || "").trim() || status === "draft_failed") {
      return { tone: "bad", label: presentation.gmailResult.warningLabel };
    }
    return { tone: "info", label: presentation.gmailResult.localOnlyLabel };
  }
  if (status) {
    return { tone: "info", label: status.replaceAll("_", " ") };
  }
  return { tone: "info", label: "Ready" };
}

function renderInterpretationSessionShell(snapshot = interpretationSnapshot()) {
  const shell = qs("interpretation-session-shell");
  const result = qs("interpretation-session-result");
  const statusNode = qs("interpretation-session-status");
  const primaryButton = qs("interpretation-session-primary");
  const activeSession = interpretationActiveSession();
  const mode = interpretationWorkspaceMode(snapshot, activeSession);
  const gmailModeActive = mode === "gmail_review" || mode === "gmail_completed";
  const sessionOpenButton = qs("interpretation-session-open-full-workspace");
  const chromeNodes = {
    body: document.body,
    shell,
    panels: [
      qs("interpretation-intake-panel"),
      qs("interpretation-seed-panel"),
      qs("interpretation-action-rail"),
    ],
    result,
    primaryButton,
    sessionOpenButton,
    statusNode,
  };
  if (!gmailModeActive || !result) {
    renderInterpretationSessionShellInto(chromeNodes, { mode, gmailModeActive });
    return;
  }
  const presentation = currentInterpretationPresentation(snapshot);
  const chip = interpretationSessionChip(activeSession, mode);
  const noticeFilename = interpretationNoticeFilename(activeSession) || "Notice PDF";
  const locationSummary = interpretationLocationSummary(snapshot);
  renderInterpretationSessionShellInto(chromeNodes, {
    mode,
    gmailModeActive,
    primaryLabel: presentation.actions.sessionPrimary,
    secondaryLabel: presentation.actions.sessionSecondary,
    status: presentation.home.status,
  });
  renderInterpretationSessionCardInto(result, {
    title: presentation.home.resultTitle,
    message: noticeFilename,
    chip,
    caseNumber: snapshot.caseNumber,
    courtEmail: snapshot.courtEmail,
    serviceDate: snapshot.serviceDate,
    location: locationSummary,
  });
}

function renderInterpretationSeedCard(containerId) {
  const container = qs(containerId);
  if (!container) {
    return;
  }
  const snapshot = interpretationSnapshot();
  const presentation = currentInterpretationPresentation(snapshot);
  renderInterpretationSeedCardStateInto(container, {
    empty: !hasInterpretationReviewData(snapshot),
    emptyText: presentation.reviewHome.emptyState,
    card: {
      title: presentation.reviewHome.title,
      message: presentation.reviewHome.subtitle,
      chip: {
        tone: snapshot.rowId ? "ok" : "info",
        label: snapshot.rowId ? "Saved" : "Ready",
      },
      caseValue: snapshot.caseNumber,
      courtEmail: snapshot.courtEmail,
      serviceDate: snapshot.serviceDate,
      location: [snapshot.caseEntity, snapshot.caseCity].filter(Boolean).join(" | "),
    },
  });
}

function renderInterpretationReviewSummary(snapshot = interpretationSnapshot()) {
  const container = qs("interpretation-review-summary-card");
  if (!container) {
    return;
  }
  const activeSession = interpretationActiveSession();
  const workspaceMode = interpretationWorkspaceMode(snapshot, activeSession);
  const presentation = currentInterpretationPresentation(snapshot);
  const noticeFilename = interpretationNoticeFilename(activeSession);
  const empty = !hasInterpretationReviewData(snapshot) && !noticeFilename;
  const chip = interpretationSessionChip(activeSession, workspaceMode);
  const subtitle = noticeFilename && workspaceMode !== "gmail_completed"
    ? noticeFilename
    : presentation.drawer.summarySubtitle;
  renderInterpretationReviewSummaryStateInto(container, {
    empty,
    emptyText: presentation.drawer.summaryEmpty,
    card: {
      title: presentation.drawer.summaryTitle,
      message: subtitle,
      chip,
      caseNumber: snapshot.caseNumber,
      courtEmail: snapshot.courtEmail,
      serviceDate: snapshot.serviceDate,
      location: interpretationLocationSummary(snapshot),
    },
  });
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
  const presentation = currentInterpretationPresentation(snapshot);
  const reviewMode = workspaceMode === "gmail_review";
  const gmailButton = qs("interpretation-finalize-gmail");
  const chip = reviewMode ? interpretationSessionChip(activeSession, workspaceMode) : {};
  renderInterpretationReviewContextInto({
    container,
    titleNode,
    copyNode,
    chipNode,
    gmailButton,
    result,
  }, {
    reviewMode,
    title: presentation.drawer.contextTitle,
    copy: presentation.drawer.contextCopy,
    chip,
    finalizeGmailLabel: presentation.actions.finalizeGmail,
    gmailResultEmpty: presentation.drawer.gmailResultEmpty,
  });
}

function syncInterpretationReviewDetailsShell(completed) {
  const details = qs("interpretation-review-details");
  if (!details) {
    return;
  }
  const summaryNode = qs("interpretation-review-details-summary");
  const presentation = currentInterpretationPresentation();
  syncInterpretationReviewDetailsShellInto(details, summaryNode, {
    completed,
    openSummary: presentation.drawer.detailsSummaryOpen,
    closedSummary: presentation.drawer.detailsSummaryClosed,
  });
}

function renderInterpretationCompletionCard(snapshot = interpretationSnapshot()) {
  const container = qs("interpretation-completion-card");
  if (!container) {
    return;
  }
  const activeSession = interpretationActiveSession();
  const workspaceMode = interpretationWorkspaceMode(snapshot, activeSession);
  const payload = interpretationUiState.completionPayload?.normalized_payload || {};
  const completionStatus = String(interpretationUiState.completionPayload?.status || "").trim();
  const presentation = currentInterpretationPresentation(snapshot);
  const completed = workspaceMode === "gmail_completed";
  syncInterpretationCompletionCardVisibilityInto(container, { completed });
  syncInterpretationReviewDetailsShell(completed);
  if (!completed) {
    return;
  }
  const draftMessage = payload.gmail_draft_result?.message
    || payload.draft_prereqs?.message
    || activeSession?.draft_failure_reason
    || ((completionStatus === "ok" || activeSession?.draft_created || activeSession?.status === "draft_ready")
      ? presentation.gmailResult.createdTitle
      : completionStatus === "local_only"
        ? presentation.gmailResult.localOnlyTitle
        : (completionStatus === "draft_unavailable" || activeSession?.draft_failure_reason || activeSession?.status === "draft_failed")
          ? presentation.gmailResult.warningTitle
          : presentation.gmailResult.localOnlyTitle);
  const pdfPath = String(payload.pdf_path || payload.pdfPath || activeSession?.pdf_export?.pdf_path || activeSession?.pdf_export?.pdfPath || "").trim();
  const docxPath = String(payload.docx_path || payload.docxPath || "").trim();
  const chip = interpretationSessionChip(activeSession, workspaceMode);
  const title = (completionStatus === "ok" || activeSession?.draft_created || activeSession?.status === "draft_ready")
    ? presentation.gmailResult.createdTitle
    : completionStatus === "local_only"
      ? presentation.gmailResult.localOnlyTitle
      : (completionStatus === "draft_unavailable" || activeSession?.draft_failure_reason || activeSession?.status === "draft_failed")
        ? presentation.gmailResult.warningTitle
        : presentation.gmailResult.localOnlyTitle;
  renderInterpretationCompletionCardInto(container, {
    title,
    message: draftMessage,
    chip,
    docxPath,
    pdfPath,
    caseLocation: interpretationCaseLocation(snapshot),
    serviceLocation: interpretationServiceLocation(snapshot),
  });
}

function setInterpretationFieldWarning(fieldName, message = "", tone = "warning") {
  const node = qs(interpretationCityWarningId(fieldName));
  if (!node) {
    return;
  }
  renderInterpretationFieldWarningInto(node, { message, tone });
}

function setInterpretationLocationGuard(rawMessage = "", tone = "warning") {
  const card = qs("interpretation-location-guard-card");
  if (!card) {
    return;
  }
  const message = String(rawMessage || "").trim();
  renderInterpretationLocationGuardInto(card, { message, tone });
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
  const syncState = deriveInterpretationDistanceSync({
    guard,
    travelKmOutbound: fieldValue("travel-km-outbound"),
    autoDistanceCity: interpretationCityState.autoDistanceCity,
    manualDistance: interpretationCityState.manualDistance,
  });
  if (fieldValue("travel-km-outbound") !== syncState.travelKmOutbound) {
    setFieldValue("travel-km-outbound", syncState.travelKmOutbound);
  }
  interpretationCityState.autoDistanceCity = syncState.autoDistanceCity;
  interpretationCityState.manualDistance = syncState.manualDistance;
  renderInterpretationDistanceHintInto(
    hint,
    syncState.hintText || guard.distanceHint || "Distance saved by city will appear here when available.",
  );
}

function updateInterpretationActionAvailability() {
  const guard = currentInterpretationGuardState();
  const blocked = guard.blocked && (
    guard.blockedCode === "unknown_case_city"
    || guard.blockedCode === "unknown_service_city"
    || guard.blockedCode === "distance_required"
    || guard.blockedCode === "distance_must_be_positive"
  );
  const actionButtons = ["save-row", "export-honorarios", "interpretation-finalize-gmail"]
    .map((id) => qs(id))
    .filter(Boolean);
  renderInterpretationActionButtonsInto(actionButtons, { blocked });
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
  const serviceAddButton = qs(interpretationCityAddButtonId("service_city"));
  renderInterpretationCityAddButtonsInto({
    caseButton: caseAddButton,
    serviceButton: serviceAddButton,
  }, {
    provisionalCaseCity: guard.provisionalCaseCity,
    provisionalServiceCity: guard.provisionalServiceCity,
    serviceSame: qs("service-same")?.checked ?? false,
  });
}

function syncInterpretationCityControls() {
  syncInterpretationDistanceFromReference();
  updateInterpretationActionAvailability();
}

function resetInterpretationExportResult() {
  const panel = qs("interpretation-review-export-panel");
  const result = qs("export-result");
  interpretationUiState.completionPayload = null;
  const presentation = currentInterpretationPresentation();
  resetInterpretationExportResultInto(panel, result, presentation.export.emptyState);
  notifyInterpretationUiStateChanged();
}

function setInterpretationReviewDrawerOpen(open) {
  const backdrop = qs("interpretation-review-drawer-backdrop");
  if (!backdrop) {
    return;
  }
  interpretationUiState.reviewDrawerOpen = Boolean(open);
  syncInterpretationReviewDrawerStateInto(backdrop, document.body, interpretationUiState.reviewDrawerOpen);
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
  const presentation = currentInterpretationPresentation(snapshot);
  const openButton = qs("interpretation-open-review");
  const gmailButton = qs("interpretation-finalize-gmail");
  const gmailResult = qs("interpretation-gmail-result");
  const saveButton = qs("save-row");
  const exportButton = qs("export-honorarios");
  const clearButton = qs("interpretation-clear-review");
  const closeFooterButton = qs("interpretation-close-review-footer");
  const drawerTitle = qs("interpretation-review-drawer-title");
  const clearTopButton = qs("clear-form");
  const reloadHistoryButton = qs("reload-history");
  const statusNode = qs("interpretation-review-status");
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
  renderInterpretationReviewSurfaceInto({
    openButton,
    drawerTitle,
    clearButton,
    clearTopButton,
    reloadHistoryButton,
    saveButton,
    exportButton,
    gmailButton,
    closeFooterButton,
    gmailResult,
    statusNode,
  }, {
    labels: {
      openReview: presentation.actions.openReview,
      drawerTitle: presentation.drawer.title,
      startBlank: presentation.actions.startBlank,
      refreshHistory: presentation.actions.refreshHistory,
      saveRow: presentation.actions.saveRow,
      export: presentation.actions.export,
      finalizeGmail: presentation.actions.finalizeGmail,
      status: presentation.drawer.status,
    },
    actions: drawerLayout.actions,
    resetGmailResult: !hasGmailInterpretationSession,
    gmailResultEmpty: presentation.drawer.gmailResultEmpty,
  });
  syncInterpretationCityControls();
  syncInterpretationDisclosureState();
  notifyInterpretationUiStateChanged();
}

function focusInterpretationField(fieldName) {
  interpretationUiState.validationField = String(fieldName || "").trim();
  const targetId = fieldName === "case_city"
    ? "case-city"
    : fieldName === "service_city"
      ? "service-city"
      : fieldName === "travel_km_outbound"
        ? "travel-km-outbound"
        : fieldName;
  focusInterpretationFieldInto({
    serviceSection: qs("interpretation-service-section"),
    textSection: qs("interpretation-text-section"),
    target: qs(targetId),
  }, fieldName);
}

function setInterpretationCityDialogOpen(open) {
  const backdrop = qs("interpretation-city-dialog-backdrop");
  if (!backdrop) {
    return;
  }
  interpretationCityState.dialogOpen = Boolean(open);
  syncInterpretationCityDialogStateInto(backdrop, document.body, interpretationCityState.dialogOpen);
}

function closeInterpretationCityDialog(result = null) {
  const resolver = interpretationCityState.dialogResolver;
  const returnFocusId = interpretationCityState.returnFocusId;
  interpretationCityState.dialogResolver = null;
  interpretationCityState.returnFocusId = "";
  setInterpretationCityDialogOpen(false);
  if (typeof resolver === "function") {
    resolver(result);
  }
  if (returnFocusId) {
    window.setTimeout(() => qs(returnFocusId)?.focus(), 0);
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
  renderInterpretationCityDialogFieldsInto({
    fieldName: qs("interpretation-city-dialog-field-name"),
    mode: qs("interpretation-city-dialog-mode"),
    cityName: qs("interpretation-city-dialog-name"),
    distance: qs("interpretation-city-dialog-distance"),
  }, {
    fieldName: interpretationCityState.activeDialog.fieldName,
    mode: interpretationCityState.activeDialog.mode,
    cityName,
  });
  const title = qs("interpretation-city-dialog-title");
  const status = qs("interpretation-city-dialog-status");
  const cityInput = qs("interpretation-city-dialog-name");
  const distanceShell = qs("interpretation-city-dialog-distance-shell");
  const distanceHint = qs("interpretation-city-dialog-distance-hint");
  const confirmButton = qs("interpretation-city-dialog-confirm");
  const reference = currentInterpretationReference();
  interpretationCityState.returnFocusId = document.activeElement?.id || interpretationCityAddButtonId(fieldName);
  const dialogTitle = interpretationCityState.activeDialog.mode === "distance"
    ? "Confirm One-Way Distance"
    : (fieldName === "case_city" ? "Add Case City" : "Add Service City");
  const dialogStatus = interpretationCityState.activeDialog.mode === "distance"
    ? `Enter the one-way distance from ${reference.travelOriginLabel || "your travel origin"} to ${cityName}.`
    : (
      interpretationCityState.activeDialog.requireDistance
        ? "Confirm the city details. Enter KM now to save a profile distance, or leave it blank."
        : "Confirm the city details before continuing."
    );
  const dialogDistanceHint = reference.travelOriginLabel
    ? `Optional one-way distance from ${reference.travelOriginLabel}.`
    : "Optional one-way distance from your profile travel origin.";
  renderInterpretationCityDialogContentInto({
    title,
    status,
    cityInput,
    distanceShell,
    distanceHint,
    confirmButton,
  }, {
    title: dialogTitle,
    status: dialogStatus,
    lockedCity,
    showDistance: interpretationCityState.activeDialog.requireDistance,
    distanceHint: dialogDistanceHint,
    confirmLabel,
  });
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
  refreshInterpretationReferenceBoundControls();
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
  const savedCity = payload.normalized_payload?.city || cityName;
  applyInterpretationCityValue(fieldName, savedCity);
  if ((qs("service-same")?.checked ?? false) && fieldName === "case_city") {
    applyInterpretationCityValue("service_city", savedCity);
  }
  if (String(distanceValue || "").trim()) {
    setFieldValue("travel-km-outbound", distanceValue);
    interpretationCityState.manualDistance = false;
    interpretationCityState.autoDistanceCity = savedCity;
  } else if (fieldName === "service_city" || ((qs("service-same")?.checked ?? false) && fieldName === "case_city")) {
    setFieldValue("travel-km-outbound", "");
    interpretationCityState.manualDistance = false;
    interpretationCityState.autoDistanceCity = "";
  }
  syncInterpretationCityControls();
  setPanelStatus("form", "ok", payload.normalized_payload?.message || "City saved.");
  setDiagnostics("form", payload, {
    hint: payload.normalized_payload?.message || "City saved.",
    open: false,
  });
  return payload;
}

function setCourtEmailEditorOpen(open) {
  const editor = qs("court-email-editor");
  if (!editor) {
    return;
  }
  const editorState = { open };
  if (open) {
    editorState.cityLabel = displayedInterpretationCity("case_city") || "selected city";
  }
  renderCourtEmailEditorInto({
    editor,
    newEmailField: qs("court-email-new"),
    status: qs("court-email-status"),
  }, editorState);
  if (open) {
    window.setTimeout(() => qs("court-email-new")?.focus(), 0);
  }
}

async function persistInterpretationCourtEmail() {
  const city = displayedInterpretationCity("case_city");
  const email = fieldValue("court-email-new");
  const payload = await fetchJson("/api/interpretation/court-emails/add", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      city,
      email,
    }),
  });
  applyInterpretationReferenceUpdate(
    payload.normalized_payload?.interpretation_reference || null,
    null,
  );
  populateCourtEmailSelect({ currentEmail: payload.normalized_payload?.email || email });
  setCourtEmailEditorOpen(false);
  setPanelStatus("form", "ok", payload.normalized_payload?.message || "Court email saved.");
  setDiagnostics("form", payload, {
    hint: payload.normalized_payload?.message || "Court email saved.",
    open: false,
  });
  syncInterpretationReviewSurface();
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

function setNewJobTask(task) {
  appState.newJobTask = task === "interpretation" ? "interpretation" : "translation";
  syncNewJobTaskControlsInto({
    panels: qsa("[data-task-panel]"),
    switches: qsa(".task-switch"),
    activeTask: appState.newJobTask,
  });
  renderInterpretationSessionShell();
}

function isBeginnerPrimarySurface() {
  return deriveBeginnerPrimarySurface({
    uiVariant: appState.uiVariant,
    activeView: appState.activeView,
    operatorChromeActive: operatorChromeActive(),
  });
}

function routeAwareTopbarStatus(runtime = {}) {
  const currentNav = document.querySelector(`.nav-button[data-view="${appState.activeView}"] span`);
  return deriveRouteAwareTopbarStatus({
    runtime,
    activeView: appState.activeView,
    uiVariant: appState.uiVariant,
    operatorChromeActive: operatorChromeActive(),
    navLabel: currentNav?.textContent?.trim() || "",
    runtimeMode: appState.runtimeMode,
  });
}

function runtimeModeBannerText(runtime = {}) {
  return deriveRuntimeModeBannerText(runtime, appState.runtimeMode);
}

function syncRuntimeModeBanner(runtime = {}) {
  const shouldShow = shouldShowDailyRuntimeModeBanner({
    uiVariant: appState.uiVariant,
    activeView: appState.activeView,
    operatorChromeActive: operatorChromeActive(),
  });
  renderRuntimeModeBannerInto(qs("runtime-mode-banner"), {
    show: shouldShow,
    message: runtimeModeBannerText(runtime),
    mode: isLiveRuntimeMode(runtime) ? "live" : "shadow",
  });
}

function syncShellChrome() {
  const runtime = appState.bootstrap?.normalized_payload?.runtime || {};
  const chrome = routeAwareTopbarStatus(runtime);
  syncRuntimeModeBanner(runtime);
  renderShellChromeInto(
    {
      body: document.body,
      eyebrow: qs("topbar-eyebrow"),
      title: qs("topbar-title"),
      workspaceLabel: qs("workspace-id-label"),
      runtimeModeLabel: qs("runtime-mode-label"),
    },
    {
      activeView: appState.activeView,
      beginnerSurface: isBeginnerPrimarySurface(),
      eyebrow: chrome.eyebrow,
      title: chrome.title,
      workspaceLabel: runtime.workspace_id || "",
      runtimeModeLabel: runtime.runtime_mode_label ? runtimeModeDisplayLabel(runtime) : "",
    },
  );
  setTopbarStatus(chrome.status, chrome.tone);
}

function beginnerSurfaceTargetLabel() {
  return deriveBeginnerSurfaceTargetLabel(appState.activeView);
}

function operatorChromeActive() {
  return appState.operatorMode || isOperatorRoute(appState.activeView);
}

function syncOperatorChrome() {
  renderOperatorChromeInto(
    {
      body: document.body,
      toggle: qs("operator-mode-toggle"),
      hint: qs("operator-mode-hint"),
    },
    {
      active: operatorChromeActive(),
      operatorMode: appState.operatorMode,
    },
  );
}

function updateServiceFieldState() {
  interpretationUiState.validationField = "";
  const serviceSame = qs("service-same").checked;
  if (serviceSame) {
    syncServiceFieldsFromCase();
  } else if (!fieldValue("service-city") && provisionalCityValue("service_city") === provisionalCityValue("case_city")) {
    setProvisionalCityValue("service_city", "");
  }
  renderServiceSameControlsInto({
    serviceEntity: qs("service-entity"),
    serviceCity: qs("service-city"),
    hint: qs("service-same-hint"),
  }, {
    serviceSame,
  });
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
  syncProfileEditorDrawerStateInto(backdrop, document.body, profileUiState.editorDrawerOpen);
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
  return JSON.stringify(serializeDistanceRows(value), null, 2);
}

function setProfileDistanceStatus(tone, message) {
  renderProfileDistanceStatusInto(qs("profile-distance-status"), { tone, message });
}

function syncProfileDistanceJsonField({ markClean = true } = {}) {
  const jsonField = qs("profile-editor-travel-distances-json");
  if (!jsonField) {
    return;
  }
  renderProfileDistanceJsonInto(jsonField, formatDistanceJson(profileUiState.distanceRows));
  if (markClean) {
    profileUiState.distanceJsonDirty = false;
  }
}

function renderProfileDistanceRows() {
  const container = qs("profile-distance-list");
  if (!container) {
    return;
  }
  renderProfileDistanceRowsInto(container, profileUiState.distanceRows, {
    onRemove: (row) => {
      profileUiState.distanceRows = removeDistanceRow(profileUiState.distanceRows, row.city);
      syncProfileDistanceJsonField();
      renderProfileDistanceRows();
      setProfileDistanceStatus("ok", `${row.city} deleted from interpretation distances. Save the profile to persist it.`);
    },
  });
}

function setProfileDistanceRows(rows, { markClean = true, statusTone = "", statusMessage = "" } = {}) {
  profileUiState.distanceRows = normalizeDistanceRows(rows);
  syncProfileDistanceJsonField({ markClean });
  renderProfileDistanceRows();
  setProfileDistanceStatus(
    statusTone,
    statusMessage || (
      profileUiState.distanceRows.length
        ? "Saved city distances are ready to use in interpretation requests."
        : "No city distances saved yet. Add the cities you use most often."
    ),
  );
}

function resyncProfileDistancesFromAdvancedJson({ setStatus = true } = {}) {
  const rows = parseDistanceRowsFromJson(qs("profile-editor-travel-distances-json")?.value || "");
  setProfileDistanceRows(rows, {
    markClean: true,
    statusTone: setStatus ? "ok" : "",
    statusMessage: setStatus ? "Distance list refreshed from the advanced data." : "",
  });
  return rows;
}

function applyProfileDistanceUpsert() {
  const cityField = qs("profile-distance-city");
  const kmField = qs("profile-distance-km");
  const nextRows = upsertDistanceRow(
    profileUiState.distanceRows,
    cityField?.value || "",
    kmField?.value || "",
  );
  const resolvedCity = String(cityField?.value || "").trim().replace(/\s+/g, " ");
  profileUiState.distanceRows = nextRows;
  syncProfileDistanceJsonField();
  renderProfileDistanceRows();
  setProfileDistanceStatus("ok", `${resolvedCity} is ready for interpretation travel details.`);
  if (cityField) {
    cityField.value = "";
  }
  if (kmField) {
    kmField.value = "";
  }
}

function applyProfileEditor(profile, { openDrawer = false } = {}) {
  const resolved = { ...blankProfileDraft(), ...(profile || {}) };
  const presentation = deriveProfilePresentation(resolved);
  const fieldIds = profileFieldIds();
  const fieldNodes = Object.fromEntries(
    Object.entries(fieldIds).map(([key, id]) => [key, qs(id)]),
  );
  renderProfileEditorFieldsInto({
    fieldNodes: fieldNodes,
    makePrimary: qs("profile-editor-make-primary"),
    distanceCity: qs("profile-distance-city"),
    distanceKm: qs("profile-distance-km"),
  }, {
    profileFields: resolved,
    isPrimary: Boolean(resolved.is_primary),
    clearDistanceDraft: true,
  });
  profileState.currentProfileId = resolved.id || "";
  renderProfileEditorChromeInto({
    status: qs("profile-editor-status"),
    setPrimaryButton: qs("profile-set-primary"),
    deleteButton: qs("profile-delete"),
    distanceAdvancedDetails: qs("profile-distance-advanced-details"),
  }, {
    statusMessage: presentation.editorStatus,
    hasProfile: Boolean(resolved.id),
    useAsMainLabel: presentation.useAsMainLabel,
    deleteLabel: "Delete profile",
    collapseDistanceAdvanced: true,
  });
  setProfileDistanceRows(resolved.travel_distances_by_city || {}, { markClean: true });
  if (openDrawer) {
    openProfileEditorDrawer();
  }
}

function collectProfileFormValues() {
  if (profileUiState.distanceJsonDirty) {
    resyncProfileDistancesFromAdvancedJson({ setStatus: false });
  }
  const fieldIds = profileFieldIds();
  const payload = {};
  for (const [key, id] of Object.entries(fieldIds)) {
    payload[key] = fieldValue(id);
  }
  payload.travel_distances_by_city = serializeDistanceRows(profileUiState.distanceRows);
  syncProfileDistanceJsonField();
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

export function applyInterpretationSeed(seed, { activateTask = true, openReview = false, sourceKind = "" } = {}) {
  if (activateTask) {
    setNewJobTask("interpretation");
  }
  appState.currentSeed = seed;
  appState.currentRowId = null;
  applyInterpretationCityValue("case_city", seed.case_city);
  populateCourtEmailSelect({ seedEmail: seed.court_email });
  const serviceDefaults = deriveInterpretationSeedServiceDefaults({ seed, sourceKind });
  populateServiceEntitySelect(serviceDefaults.serviceEntity);
  applyInterpretationCityValue("service_city", serviceDefaults.serviceCity);
  renderInterpretationFormFieldsInto({
    rowId: qs("row-id"),
    caseNumber: qs("case-number"),
    caseEntity: qs("case-entity"),
    serviceEntity: qs("service-entity"),
    serviceDate: qs("service-date"),
    travelKmOutbound: qs("travel-km-outbound"),
    pages: qs("pages"),
    wordCount: qs("word-count"),
    ratePerWord: qs("rate-per-word"),
    expectedTotal: qs("expected-total"),
    amountPaid: qs("amount-paid"),
    apiCost: qs("api-cost"),
    profit: qs("profit"),
    recipientBlock: qs("recipient-block"),
    serviceSame: qs("service-same"),
    useServiceLocation: qs("use-service-location"),
    includeTransport: qs("include-transport"),
  }, {
    rowId: "",
    caseNumber: seed.case_number,
    caseEntity: seed.case_entity,
    serviceEntity: serviceDefaults.serviceEntity,
    serviceDate: seed.service_date,
    travelKmOutbound: seed.travel_km_outbound ?? "",
    pages: seed.pages ?? "",
    wordCount: seed.word_count ?? "",
    ratePerWord: seed.rate_per_word ?? "",
    expectedTotal: seed.expected_total ?? "",
    amountPaid: seed.amount_paid ?? "",
    apiCost: seed.api_cost ?? "",
    profit: seed.profit ?? "",
    recipientBlock: "",
    serviceSame: serviceDefaults.serviceSame,
    useServiceLocation: Boolean(seed.use_service_location_in_honorarios),
    includeTransport: seed.include_transport_sentence_in_honorarios !== false,
  });
  interpretationCityState.manualDistance = Boolean(fieldValue("travel-km-outbound"));
  interpretationCityState.autoDistanceCity = "";
  updateServiceFieldState();
  syncInterpretationSeedServiceSectionInto(qs("interpretation-service-section"), {
    sourceKind,
    serviceSame: serviceDefaults.serviceSame,
  });
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
  applyInterpretationCityValue("case_city", item.row.case_city || "");
  populateCourtEmailSelect({ currentEmail: item.row.court_email || "" });
  populateServiceEntitySelect(item.row.service_entity || "");
  applyInterpretationCityValue("service_city", item.row.service_city || "");
  renderInterpretationFormFieldsInto({
    rowId: qs("row-id"),
    caseNumber: qs("case-number"),
    caseEntity: qs("case-entity"),
    serviceEntity: qs("service-entity"),
    serviceDate: qs("service-date"),
    travelKmOutbound: qs("travel-km-outbound"),
    pages: qs("pages"),
    wordCount: qs("word-count"),
    ratePerWord: qs("rate-per-word"),
    expectedTotal: qs("expected-total"),
    amountPaid: qs("amount-paid"),
    apiCost: qs("api-cost"),
    profit: qs("profit"),
    recipientBlock: qs("recipient-block"),
    serviceSame: qs("service-same"),
    useServiceLocation: qs("use-service-location"),
    includeTransport: qs("include-transport"),
  }, {
    rowId: item.row.id,
    caseNumber: item.row.case_number || "",
    caseEntity: item.row.case_entity || "",
    serviceEntity: item.row.service_entity || "",
    serviceDate: item.row.service_date || "",
    travelKmOutbound: item.row.travel_km_outbound ?? "",
    pages: item.row.pages ?? "",
    wordCount: item.row.word_count ?? "",
    ratePerWord: item.row.rate_per_word ?? "",
    expectedTotal: item.row.expected_total ?? "",
    amountPaid: item.row.amount_paid ?? "",
    apiCost: item.row.api_cost ?? "",
    profit: item.row.profit ?? "",
    recipientBlock: "",
    serviceSame: inferServiceSame(item.row.case_entity, item.row.case_city, item.row.service_entity, item.row.service_city),
    useServiceLocation: Boolean(item.row.use_service_location_in_honorarios),
    includeTransport: item.row.include_transport_sentence_in_honorarios !== 0,
  });
  updateServiceFieldState();
  interpretationCityState.manualDistance = Boolean(fieldValue("travel-km-outbound"));
  interpretationCityState.autoDistanceCity = "";
  resetInterpretationExportResult();
  syncInterpretationReviewSurface();
  setPanelStatus("form", "ok", deriveRecentWorkPresentation().loadedSavedCaseStatus);
  setDiagnostics("form", { status: "ok", message: `Loaded row #${item.row.id}.` }, { hint: `Loaded interpretation record #${item.row.id}.`, open: false });
  setActiveView("new-job");
  renderShellVisibility();
  openInterpretationReviewDrawer();
}

function renderProfiles(profiles, primaryProfileId) {
  renderProfileOptionsInto(qs("profile-id"), profiles, primaryProfileId);
}

function renderNavigation(items) {
  renderNavigationInto({
    primaryContainer: qs("section-nav"),
    moreContainer: qs("more-nav"),
    moreShell: qs("more-nav-shell"),
    items,
    activeView: appState.activeView,
    showGmailNav: shouldShowGmailNav(),
  });
}

function renderShellVisibility() {
  renderShellVisibilityInto({
    views: qsa(".page-view"),
    navButtons: qsa(".nav-button"),
    moreShell: qs("more-nav-shell"),
    activeView: appState.activeView,
  });
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
  renderDashboardCardsInto(qs("dashboard-cards"), cards);
}

function renderSummaryGrid(containerId, items) {
  renderSummaryGridInto(qs(containerId), items);
}

async function handleDeleteJobLogRow(rowId, { jobType = "job-log", source = "history" } = {}) {
  const presentation = deriveRecentWorkPresentation({ jobType });
  if (!window.confirm(presentation.deleteConfirmMessage)) {
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
  setPanelStatus("recent-jobs", "ok", presentation.deleteStatus);
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
  renderCapabilityCardsInto(qs(containerId), cards);
}

function renderRecentJobs(items, history, translationHistory = []) {
  const container = qs("recent-jobs-list");
  if (!container) {
    return;
  }
  if (!items.length) {
    const presentation = deriveRecentWorkPresentation();
    setPanelStatus("recent-jobs", "", presentation.recentWorkEmpty);
  } else {
    setPanelStatus("recent-jobs", "", deriveRecentWorkPresentation({ recentItemCount: items.length }).recentWorkCount);
  }
  const historyById = new Map(history.map((item) => [Number(item.row.id), item]));
  const translationHistoryById = new Map(translationHistory.map((item) => [Number(item.row.id), item]));
  renderRecentJobsInto(container, items, historyById, translationHistoryById, {
    onOpenInterpretation: (item) => applyHistoryItem(item),
    onOpenTranslation: (item) => loadTranslationHistoryItem(item),
    onDelete: async (item) => {
      try {
        await handleDeleteJobLogRow(item.id, { jobType: item.job_type, source: "recent jobs" });
      } catch (error) {
        setPanelStatus("recent-jobs", "bad", error.message || "Saved work delete failed.");
        setDiagnostics("form", error, { hint: error.message || "Saved work delete failed.", open: true });
      }
    },
  });
}

function renderHistory(items, modeLabel) {
  const container = qs("history-list");
  renderInterpretationHistoryHeadingInto(qs("history-heading"));
  renderInterpretationHistoryInto(container, items, {
    onOpen: (item) => applyHistoryItem(item),
    onDelete: async (item) => {
      try {
        await handleDeleteJobLogRow(item.row.id, { jobType: "Interpretation", source: "interpretation history" });
      } catch (error) {
        setPanelStatus("recent-jobs", "bad", error.message || "Saved work delete failed.");
        setDiagnostics("form", error, { hint: error.message || "Saved work delete failed.", open: true });
      }
    },
  });
}

function renderStatus(payload) {
  const runtime = payload.normalized_payload.runtime;
  const dashboardPresentation = deriveDashboardPresentation(payload);
  const settingsCards = buildSettingsCapabilityCards(payload);
  renderCapabilityCards("status-grid", dashboardPresentation.statusCards);
  renderCapabilityCards("settings-capability-grid", settingsCards);
  setPanelStatus("runtime", runtime.live_data ? "info" : "ok", dashboardPresentation.statusSummary);
  setDiagnostics("runtime", payload.diagnostics.runtime, {
    hint: "Build identity, listener ownership, and runtime-mode provenance.",
    open: false,
  });
}

export function renderInterpretationExportResult(payload) {
  const container = qs("export-result");
  renderInterpretationExportPanelResultInto(
    qs("interpretation-review-export-panel"),
    container,
    payload,
    currentInterpretationPresentation(),
  );
  openInterpretationReviewDrawer();
  syncInterpretationReviewSurface();
  notifyInterpretationUiStateChanged();
}

export function renderInterpretationGmailResult(payload) {
  const container = qs("interpretation-gmail-result");
  if (!container) {
    return;
  }
  interpretationUiState.completionPayload = payload;
  renderInterpretationGmailResultInto(container, payload, currentInterpretationPresentation());
  openInterpretationReviewDrawer();
  syncInterpretationReviewSurface();
  notifyInterpretationUiStateChanged();
}

function renderDashboard(payload) {
  const presentation = deriveDashboardPresentation(payload);
  renderDashboardSummaryInto(qs("dashboard-summary"), presentation.savedWorkSummary);
  renderDashboardCards(payload.normalized_payload.dashboard_cards || []);
  renderParityAudit(payload, presentation);
}

function renderParityAudit(payload, presentation = deriveDashboardPresentation(payload)) {
  renderParityAuditInto({
    statusNode: qs("parity-audit-status"),
    gridContainer: qs("parity-audit-grid"),
    resultContainer: qs("parity-audit-result"),
    audit: payload.normalized_payload.parity_audit || {},
    presentation,
  });
}

function renderSettings(payload) {
  const summary = payload.normalized_payload.settings_summary || {};
  const providerState = payload.normalized_payload.settings_admin?.provider_state || {};
  const items = buildSettingsSummaryItems(summary, providerState);
  const statusPresentation = buildSettingsStatusPresentation(providerState);
  renderSummaryGrid("settings-summary-grid", items);
  setPanelStatus("settings", statusPresentation.tone, statusPresentation.message);
}

function renderProfile(payload) {
  const summary = payload.normalized_payload.profile_summary || {};
  const primary = summary.primary_profile;
  const runtime = payload.normalized_payload.runtime || {};
  const primaryCard = qs("profile-primary-card");
  renderProfileToolbarInto({
    importButton: qs("import-live-profiles"),
    newButton: qs("new-profile"),
  }, {
    liveData: runtime.live_data === true,
  });
  renderPrimaryProfileCardInto(primaryCard, primary);
  const container = qs("profile-list");
  renderProfileListInto(container, summary.profiles || [], {
    count: summary.count || 0,
    onEdit(profile) {
      applyProfileEditor(cloneJson(profile), { openDrawer: true });
    },
    async onSetPrimary(profile) {
      try {
        await handleSetPrimaryProfile(profile.id);
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "Set-primary failed.");
        setDiagnostics("profile", error, { hint: error.message || "Set-primary failed.", open: true });
      }
    },
    async onDelete(profile) {
      try {
        await handleDeleteProfile(profile.id);
      } catch (error) {
        setPanelStatus("profile", "bad", error.message || "Profile delete failed.");
        setDiagnostics("profile", error, { hint: error.message || "Profile delete failed.", open: true });
      }
    },
  });
  setPanelStatus("profile", "", formatProfileCountStatus(summary.count || 0));
  setDiagnostics("profile", summary, {
    hint: "Profile summaries, required fields, and saved distance data appear here.",
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
  const runtime = payload.normalized_payload.runtime || {};
  const cards = buildExtensionLabCards({ prepare, extensionReport, bridgeSummary, runtime });
  renderCapabilityCards("extension-status-grid", cards);
  const extensionTone = bridgeSummary.status || (prepare.ok === true ? "ok" : "warn");
  setPanelStatus(
    "extension",
    extensionTone,
    prepare.ok === true
      ? "The browser helper is ready for Gmail intake in this mode."
      : "The browser helper needs attention. Open technical details below if you are troubleshooting.",
  );
  setDiagnostics("extension", { prepare_response: prepare, extension_report: extensionReport, bridge_summary: bridgeSummary, notes: data.notes || [] }, {
    hint: "Browser helper, extension, and readiness details.",
    open: false,
  });
  const defaults = data.simulator_defaults || {};
  renderExtensionSimulatorDefaultsInto({
    messageId: qs("sim-message-id"),
    threadId: qs("sim-thread-id"),
    subject: qs("sim-subject"),
    accountEmail: qs("sim-account-email"),
  }, defaults);
  const reasonCatalog = qs("extension-reason-catalog");
  if (reasonCatalog) {
    renderExtensionPrepareReasonCatalogInto(reasonCatalog, data.prepare_reason_catalog || []);
  }
}

function renderTopbar(payload) {
  const runtime = payload.normalized_payload.runtime;
  renderTopbarInto({
    workspaceLabel: qs("workspace-id-label"),
    runtimeModeLabel: qs("runtime-mode-label"),
    liveBanner: qs("live-banner"),
  }, runtime);
  syncShellChrome();
}

function renderRuntimeModeSelector(payload) {
  const runtimeMode = payload.normalized_payload.runtime_mode || {};
  renderRuntimeModeSelectorInto(qs("runtime-mode-select"), runtimeMode);
}

function renderBootstrap(payload) {
  appState.bootstrap = payload;
  const gmailBootstrap = payload.normalized_payload.gmail || {};
  renderNavigation(payload.normalized_payload.navigation || []);
  renderRuntimeModeSelector(payload);
  renderTopbar(payload);
  renderProfiles(payload.normalized_payload.profiles || [], payload.normalized_payload.primary_profile_id);
  refreshInterpretationCitySelectors();
  refreshInterpretationReferenceBoundControls();
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
  renderGooglePhotosStatus(payload.normalized_payload.google_photos || {});
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
    refreshInterpretationReferenceBoundControls();
  }
  syncInterpretationReviewSurface();
  syncClientHydrationMarker({ payload: payload.normalized_payload });
}

function applyShellBootstrapSnapshot(payload) {
  const shellPayload = payload?.normalized_payload?.shell || {};
  const runtimeMode = String(shellPayload.runtime_mode || appState.runtimeMode || "shadow").trim();
  const workspaceId = String(shellPayload.workspace_id || appState.workspaceId || "workspace-1").trim();
  const shellReady = shellPayload.ready === true;
  renderShellRuntimeLabelsInto({
    workspaceLabel: qs("workspace-id-label"),
    runtimeModeLabel: qs("runtime-mode-label"),
  }, {
    workspaceLabel: workspaceId || "workspace-1",
    runtimeModeLabel: runtimeMode === "live" ? "Live mode" : "Test mode",
  });
  if (workspaceId === "gmail-intake") {
    setTopbarStatus(
      shellReady
        ? "Browser shell is ready. Finishing Gmail workspace hydration..."
        : "Warming the browser shell and Gmail workspace...",
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
  if (isBeginnerPrimarySurface()) {
    const target = beginnerSurfaceTargetLabel();
    setTopbarStatus(
      shellReady
        ? `Opening the ${target}...`
        : `Preparing the ${target}...`,
      shellReady ? "info" : "warn",
    );
    setPanelStatus(
      "runtime",
      shellReady ? "info" : "warn",
      shellReady
        ? `Browser shell is responding. Loading the ${target}...`
        : "Browser shell is still warming.",
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
    : isBeginnerPrimarySurface()
      ? beginnerSurfaceTargetLabel()
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

async function handleUpload(formId, endpoint, { sourceKind = "" } = {}) {
  const form = qs(formId);
  const data = new FormData(form);
  const payload = await fetchJson(endpoint, appState, { method: "POST", body: data });
  if (payload.normalized_payload) {
    applyInterpretationSeed(payload.normalized_payload, { sourceKind });
  }
  const extractedFields = payload.diagnostics?.metadata_extraction?.extracted_fields || [];
  const message = extractedFields.length ? `Recovered ${extractedFields.join(", ")} from the uploaded file.` : "No metadata fields were recovered automatically.";
  setPanelStatus("autofill", extractedFields.length ? "ok" : "warn", message);
  setDiagnostics("autofill", payload.diagnostics, { hint: message, open: !extractedFields.length });
  openInterpretationReviewDrawer();
}

function renderGooglePhotosSummary({ selectedPhoto = null, diagnostics = null, message = "" } = {}) {
  renderGooglePhotosSummaryInto(qs("google-photos-summary"), {
    selectedPhoto,
    diagnostics,
    message,
  });
}

async function refreshGooglePhotosStatus() {
  const payload = await fetchJson("/api/interpretation/google-photos/status", appState);
  renderGooglePhotosStatus(payload.normalized_payload?.google_photos || {});
  return payload;
}

async function handleGooglePhotosDisconnectForReconnect() {
  const activeSessionId = googlePhotosUiState.sessionId;
  let sessionDeleted = false;
  if (activeSessionId) {
    try {
      await deleteGooglePhotosPickerSession(activeSessionId);
      sessionDeleted = true;
    } catch {
      updateGooglePhotosPickerDiagnostics({
        stale_picker_uri_possible: true,
        safe_failure_category: "picker_stale_session_possible",
      });
    }
  }
  resetGooglePhotosPickerState({ clearAuth: true, sessionDeleted });
  const payload = await fetchJson("/api/interpretation/google-photos/disconnect", appState, { method: "POST" });
  const status = payload.normalized_payload?.google_photos || {};
  renderGooglePhotosStatus(status);
  setDiagnostics("autofill", payload.diagnostics || {}, {
    hint: "Google Photos local connection was cleared. Connect again before choosing a photo.",
    open: false,
  });
  setPanelStatus("autofill", "warn", "Google Photos local connection was cleared. Connect Google Photos again.");
  renderGooglePhotosSummary({ message: "Google Photos local connection was cleared. Connect Google Photos again before choosing a photo." });
  return payload;
}

function clampGooglePhotosPollMilliseconds(value, fallback, minValue, maxValue) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return Math.max(minValue, Math.min(maxValue, parsed));
}

async function waitForGooglePhotosConnection() {
  const startedAt = Date.now();
  const timeoutMs = 90000;
  const pollIntervalMs = 2000;
  while (Date.now() - startedAt < timeoutMs) {
    await delay(pollIntervalMs);
    const payload = await refreshGooglePhotosStatus();
    const status = payload.normalized_payload?.google_photos || {};
    if (status.connected) {
      googlePhotosUiState.connectPollTimedOut = false;
      setPanelStatus("autofill", "ok", "Google Photos connected. Choose a photo to recover Interpretation metadata.");
      renderGooglePhotosSummary({ message: "Google Photos connected. Choose a photo to continue." });
      return true;
    }
  }
  googlePhotosUiState.connectPollTimedOut = true;
  setPanelStatus("autofill", "warn", "Google Photos authorization is still pending. Use Open Google sign-in if no Google tab opened, or return after completing Google consent.");
  renderGooglePhotosSummary({ message: "Still waiting for Google Photos authorization. Use Open Google sign-in if no Google tab opened." });
  await refreshGooglePhotosStatus().catch(() => {});
  return false;
}

async function handleGooglePhotosConnect() {
  const currentStatus = googlePhotosUiState.status || {};
  if (currentStatus.connected) {
    await handleGooglePhotosDisconnectForReconnect();
  } else {
    resetGooglePhotosPickerState({ clearAuth: true });
  }
  const payload = await fetchJson("/api/interpretation/google-photos/connect", appState, { method: "POST" });
  const authUrl = payload.normalized_payload?.google_photos?.auth_url || "";
  if (!authUrl) {
    throw new Error("Google Photos did not return an authorization URL.");
  }
  setGooglePhotosAuthFallback(authUrl, { visible: true });
  try {
    window.open(authUrl, "_blank", "noopener,noreferrer");
  } catch {
    // The visible fallback link remains available when the browser blocks programmatic opening.
  }
  const nextStatus = googlePhotosUiState.status || {};
  renderGooglePhotosStatus({
    ...nextStatus,
    configured: true,
    client_id_configured: true,
    client_secret_env_configured: true,
    connected: false,
  });
  setPanelStatus("autofill", "info", "Google sign-in is ready. If no Google tab opened, click Open Google sign-in.");
  renderGooglePhotosSummary({ message: "Google sign-in is ready. If no Google tab opened, click Open Google sign-in." });
  await waitForGooglePhotosConnection();
}

async function waitForGooglePhotosPickerSelection(sessionId, initialSession = {}) {
  const encodedSessionId = encodeURIComponent(sessionId);
  const pollIntervalMs = clampGooglePhotosPollMilliseconds(initialSession.poll_interval_ms, 2000, 1000, 10000);
  const timeoutMs = clampGooglePhotosPollMilliseconds(initialSession.timeout_ms, 120000, 30000, 600000);
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    const payload = await fetchJson(`/api/interpretation/google-photos/session/${encodedSessionId}`, appState);
    const session = payload.normalized_payload?.google_photos?.session || {};
    if (session.is_ready || session.media_items_set) {
      updateGooglePhotosPickerDiagnostics({
        media_items_set_observed: true,
        safe_failure_category: "picker_unknown",
      });
      setGooglePhotosPickerFallback("", { visible: false });
      return session;
    }
    setPanelStatus("autofill", "info", "Waiting for Google Photos selection...");
    renderGooglePhotosSummary({
      message: "A Google Photos tab should open. Select one photo, then click Done. If no tab opened, click Open Google Photos Picker. LegalPDF will continue waiting here until selection is completed.",
    });
    await delay(clampGooglePhotosPollMilliseconds(session.poll_interval_ms, pollIntervalMs, 1000, 10000));
  }
  updateGooglePhotosPickerDiagnostics({
    safe_failure_category: "picker_timeout",
    stale_picker_uri_possible: true,
  });
  setGooglePhotosPickerFallback("", { visible: false });
  throw new Error("Google Photos selection timed out before any media item was available.");
}

async function deleteGooglePhotosPickerSession(sessionId) {
  const cleaned = String(sessionId || "").trim();
  if (!cleaned) {
    return null;
  }
  return fetchJson(`/api/interpretation/google-photos/session/${encodeURIComponent(cleaned)}`, appState, {
    method: "DELETE",
  });
}

async function handleGooglePhotosChoose() {
  const pickerWindow = window.open("about:blank", "_blank", "noopener");
  let importedSelection = false;
  resetGooglePhotosPickerState({ clearAuth: false });
  try {
    const sessionPayload = await fetchJson("/api/interpretation/google-photos/session", appState, { method: "POST" });
    const session = sessionPayload.normalized_payload?.google_photos?.session || {};
    const pickerUri = session.picker_uri || "";
    if (!session.session_id || !pickerUri) {
      throw new Error("Google Photos Picker did not return a usable session.");
    }
    googlePhotosUiState.sessionId = session.session_id;
    updateGooglePhotosPickerDiagnostics({
      picker_session_created: true,
      media_items_set_observed: Boolean(session.is_ready || session.media_items_set),
      safe_failure_category: "picker_unknown",
    });
    const pickerBrowserUrl = googlePhotosPickerBrowserUrl(pickerUri, { autoclose: !googlePhotosUiState.disablePickerAutocloseOnce });
    setGooglePhotosPickerFallback(pickerUri, { visible: true });
    if (pickerWindow) {
      pickerWindow.location.href = pickerBrowserUrl;
    } else {
      window.open(pickerBrowserUrl, "_blank", "noopener");
    }
    const pickerMessage = "A Google Photos tab should open. Select one photo, then click Done. If no tab opened, click Open Google Photos Picker. LegalPDF will continue waiting here until selection is completed.";
    renderGooglePhotosSummary({ message: pickerMessage });
    setPanelStatus("autofill", "info", pickerMessage);
    await waitForGooglePhotosPickerSelection(session.session_id, session);
    updateGooglePhotosPickerDiagnostics({ media_items_list_called: true });
    const mediaPayload = await fetchJson(
      `/api/interpretation/google-photos/session/${encodeURIComponent(session.session_id)}/media-items`,
      appState,
    );
    const googlePhotosPayload = mediaPayload.normalized_payload?.google_photos || {};
    const mediaItems = googlePhotosPayload.media_items || [];
    googlePhotosUiState.selectedItems = mediaItems;
    if (!mediaItems.length) {
      updateGooglePhotosPickerDiagnostics({
        media_items_set_observed: false,
        safe_failure_category: "picker_done_but_media_items_set_false",
      });
      throw new Error("No Google Photos media item was selected.");
    }
    const selectionWarning = googlePhotosPayload.multiple_selection_warning || "";
    renderGooglePhotosSummary({
      selectedPhoto: mediaItems[0],
      message: selectionWarning || "Selected photo found. Recovering Interpretation metadata...",
    });
    updateGooglePhotosPickerDiagnostics({ import_route_called: true });
    const importPayload = await fetchJson("/api/interpretation/google-photos/import", appState, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: session.session_id,
        selection_key: mediaItems[0].selection_key || "",
        mode: appState.runtimeMode,
        workspace_id: appState.workspaceId,
      }),
    });
    importedSelection = true;
    googlePhotosUiState.sessionId = "";
    updateGooglePhotosPickerDiagnostics({
      media_items_set_observed: true,
      media_items_list_called: true,
      import_route_called: true,
      safe_failure_category: "picker_unknown",
    });
    setGooglePhotosPickerFallback("", { visible: false });
    if (importPayload.normalized_payload) {
      applyInterpretationSeed(importPayload.normalized_payload, { sourceKind: "google_photos" });
    }
    const extractedFields = importPayload.diagnostics?.metadata_extraction?.extracted_fields || [];
    const message = extractedFields.length
      ? `Recovered ${extractedFields.join(", ")} from the Google Photos selection.`
      : "Google Photos import completed, but no metadata fields were recovered automatically.";
    setPanelStatus("autofill", extractedFields.length ? "ok" : "warn", message);
    setDiagnostics("autofill", importPayload.diagnostics, { hint: message, open: !extractedFields.length });
    renderGooglePhotosSummary({
      selectedPhoto: importPayload.diagnostics?.google_photos?.selected_photo || mediaItems[0],
      diagnostics: importPayload.diagnostics?.google_photos || {},
      message: importPayload.diagnostics?.google_photos?.multiple_selection_warning || message,
    });
    openInterpretationReviewDrawer();
  } catch (error) {
    if (pickerWindow) {
      pickerWindow.close();
    }
    const currentCategory = googlePhotosUiState.pickerDiagnostics?.safe_failure_category || "";
    if (!currentCategory || currentCategory === "picker_unknown") {
      updateGooglePhotosPickerDiagnostics({
        safe_failure_category: String(error.message || "").includes("timed out") ? "picker_timeout" : "picker_unknown",
      });
    }
    setGooglePhotosPickerFallback("", { visible: false });
    throw error;
  } finally {
    if (googlePhotosUiState.sessionId && !importedSelection) {
      await deleteGooglePhotosPickerSession(googlePhotosUiState.sessionId)
        .then(() => {
          updateGooglePhotosPickerDiagnostics({
            picker_session_deleted: true,
            stale_picker_uri_possible: false,
          });
        })
        .catch(() => {
          updateGooglePhotosPickerDiagnostics({
            picker_session_deleted: false,
            stale_picker_uri_possible: true,
            safe_failure_category: "picker_stale_session_possible",
          });
        });
      googlePhotosUiState.sessionId = "";
    }
    if (!importedSelection) {
      setGooglePhotosPickerFallback("", { visible: false });
    }
    await refreshGooglePhotosStatus().catch(() => {});
  }
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
  setPanelStatus("form", "ok", `Saved case record #${payload.saved_result.row_id}.`);
  setDiagnostics("form", payload, { hint: `Saved case record #${payload.saved_result.row_id}.`, open: false });
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
  const message = payload.status === "ok"
    ? "Created the fee-request document successfully."
    : "The DOCX is ready, but the PDF export stayed local in this run.";
  setPanelStatus("form", payload.status === "ok" ? "ok" : "warn", message);
  setDiagnostics("form", payload, { hint: message, open: payload.status !== "ok" });
  renderInterpretationExportResult(payload);
}

async function handleImportLiveProfiles() {
  const payload = await fetchJson("/api/profiles/import-live", appState, { method: "POST" });
  const importedCount = payload.normalized_payload?.imported_profile_count ?? 0;
  const message = importedCount > 0
    ? `Copied ${importedCount} profile${importedCount === 1 ? "" : "s"} from the live app.`
    : "Using live app profiles in this mode.";
  await loadBootstrap();
  setPanelStatus("profile", "ok", message);
  setDiagnostics("profile", payload, {
    hint: importedCount > 0 ? `Copied ${importedCount} profile(s) from the live app.` : "Using live app profiles in this mode.",
    open: false,
  });
}

async function handleNewProfile() {
  const payload = await fetchJson("/api/profile/new", appState);
  applyProfileEditor(payload.normalized_payload?.profile || blankProfileDraft(), { openDrawer: true });
  setPanelStatus("profile", "", "New profile draft ready. Fill the required details, then save.");
  setDiagnostics("profile", payload, {
    hint: "New profile draft ready.",
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
  const message = "Profile saved.";
  await loadBootstrap();
  setPanelStatus("profile", "ok", message);
  setDiagnostics("profile", payload, {
    hint: message,
    open: false,
  });
}

async function handleDeleteProfile(profileId = fieldValue("profile-editor-id")) {
  const resolvedId = String(profileId || "").trim();
  if (!resolvedId) {
    throw new Error("Select a saved profile before deleting it.");
  }
  if (!window.confirm(deriveProfilePresentation({}).deleteConfirmMessage)) {
    return;
  }
  const payload = await fetchJson("/api/profile/delete", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ profile_id: resolvedId }),
  });
  profileState.currentProfileId = "";
  const message = "Profile deleted.";
  await loadBootstrap();
  closeProfileEditorDrawer();
  setPanelStatus("profile", "ok", message);
  setDiagnostics("profile", payload, {
    hint: "Profile deleted.",
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
  const primaryProfile = payload.normalized_payload?.profile_summary?.primary_profile || {};
  const message = `${deriveProfilePresentation(primaryProfile).displayName} is now the main profile.`;
  await loadBootstrap();
  setPanelStatus("profile", "ok", message);
  setDiagnostics("profile", payload, {
    hint: message,
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
    setPanelStatus("form", "", "Blank interpretation request loaded. Fill in the details manually or use autofill above.");
    setDiagnostics("form", { status: "ok", message: "Blank interpretation request loaded." }, { hint: "Blank interpretation request loaded.", open: false });
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
        await handleUpload("photo-upload-form", "/api/interpretation/autofill-photo", { sourceKind: "photo" });
      } catch (error) {
        setPanelStatus("autofill", "bad", error.message || "Photo autofill failed.");
        setDiagnostics("autofill", error, { hint: error.message || "Photo autofill failed.", open: true });
      }
    });
  });

  qs("google-photos-connect")?.addEventListener("click", async () => {
    const isReconnect = Boolean(googlePhotosUiState.status?.connected);
    await runWithBusy(["google-photos-connect", "google-photos-choose"], { "google-photos-connect": isReconnect ? "Reconnecting..." : "Connecting..." }, async () => {
      try {
        await handleGooglePhotosConnect();
      } catch (error) {
        setPanelStatus("autofill", "bad", error.message || "Google Photos connection failed.");
        setDiagnostics("autofill", error, { hint: error.message || "Google Photos connection failed.", open: true });
      }
    }, { guardIds: ["google-photos-connect"] });
    renderGooglePhotosStatus(googlePhotosUiState.status || {});
  });

  qs("google-photos-open-picker")?.addEventListener("click", () => {
    updateGooglePhotosPickerDiagnostics({
      picker_fallback_clicked: true,
      safe_failure_category: "picker_unknown",
    });
  });

  qs("google-photos-choose")?.addEventListener("click", async () => {
    await runWithBusy(["google-photos-connect", "google-photos-choose", "photo-submit"], { "google-photos-choose": "Choosing..." }, async () => {
      try {
        await handleGooglePhotosChoose();
      } catch (error) {
        const pickerDiagnostics = googlePhotosUiState.pickerDiagnostics || buildGooglePhotosPickerDiagnostics();
        const reconnectNeeded = [
          "picker_done_but_media_items_set_false",
          "picker_reconnect_to_partner_app",
          "picker_stale_session_possible",
          "picker_account_mismatch_possible",
        ].includes(pickerDiagnostics.safe_failure_category);
        const message = reconnectNeeded
          ? GOOGLE_PHOTOS_RECONNECT_GUIDANCE
          : (error.message || "Google Photos import failed.");
        setPanelStatus("autofill", "bad", message);
        setDiagnostics("autofill", {
          status: "failed",
          message,
          google_photos_picker: pickerDiagnostics,
          request_error: error.payload || {},
        }, { hint: message, open: true });
        renderGooglePhotosSummary({ diagnostics: { location_message: "Google Photos location: unavailable from Picker API" }, message });
      }
    }, { guardIds: ["google-photos-choose"] });
    renderGooglePhotosStatus(googlePhotosUiState.status || {});
  });

  qs("save-row").addEventListener("click", async () => {
    await runWithBusy(["save-row", "export-honorarios", "clear-form", "reload-history"], { "save-row": "Saving..." }, async () => {
      try {
        setPanelStatus("form", "", "Saving the case record...");
        await handleSave();
      } catch (error) {
        recoverInterpretationValidationError(error);
        setPanelStatus("form", "bad", error.message || "Save failed.");
        setDiagnostics("form", error, { hint: error.message || "Save failed.", open: true });
      }
    });
  });

  qs("export-honorarios").addEventListener("click", async () => {
    await runWithBusy(["save-row", "export-honorarios", "clear-form", "reload-history"], { "export-honorarios": "Creating..." }, async () => {
      try {
        setPanelStatus("form", "", "Creating the fee-request document...");
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
    }, { guardIds: ["import-live-profiles", "new-profile", "profile-save"] });
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

  qs("profile-distance-add")?.addEventListener("click", () => {
    try {
      applyProfileDistanceUpsert();
    } catch (error) {
      setProfileDistanceStatus("bad", error.message || "Unable to update the distance.");
    }
  });

  qs("profile-distance-sync-advanced")?.addEventListener("click", () => {
    try {
      resyncProfileDistancesFromAdvancedJson();
    } catch (error) {
      setProfileDistanceStatus("bad", error.message || "Unable to refresh the distance list.");
    }
  });

  qs("profile-editor-travel-distances-json")?.addEventListener("input", () => {
    profileUiState.distanceJsonDirty = true;
    setProfileDistanceStatus("info", "Advanced distance data changed. Save or refresh the visible list to apply it.");
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
        setPanelStatus("recent-jobs", "", deriveRecentWorkPresentation().refreshStatus);
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
  qs("case-entity").addEventListener("input", () => {
    updateServiceFieldState();
    populateCourtEmailSelect({ currentEmail: fieldValue("court-email") });
  });
  qs("service-entity").addEventListener("input", () => {
    interpretationUiState.validationField = "";
    syncInterpretationReviewSurface();
  });
  qs("service-entity").addEventListener("change", () => {
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
    populateCourtEmailSelect({ currentEmail: fieldValue("court-email") });
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
    refreshInterpretationReferenceBoundControls();
    syncInterpretationCityControls();
  });
  qs("court-email-add")?.addEventListener("click", () => setCourtEmailEditorOpen(true));
  qs("court-email-cancel")?.addEventListener("click", () => setCourtEmailEditorOpen(false));
  qs("court-email-save")?.addEventListener("click", async () => {
    try {
      await persistInterpretationCourtEmail();
    } catch (error) {
      setPanelStatus("form", "bad", error.message || "Unable to save the court email yet.");
      setDiagnostics("form", error, { hint: error.message || "Unable to save the court email yet.", open: true });
      renderCourtEmailStatusInto(qs("court-email-status"), {
        message: error.message || "Unable to save the court email yet.",
        tone: "bad",
      });
    }
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
    if (String(distanceValue || "").trim()) {
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
    deriveTranslationCompletionPresentation,
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
  setDiagnostics("power-tools-glossary", { status: "idle", message: "No glossary action has been run yet." }, { hint: "Glossary save and markdown export details appear here.", open: false });
  setDiagnostics("power-tools-builder", { status: "idle", message: "No glossary suggestion run has been executed yet." }, { hint: "Glossary suggestion results and apply responses appear here.", open: false });
  setDiagnostics("power-tools-calibration", { status: "idle", message: "No quality check has been run yet." }, { hint: "Quality-check report paths and suggestion details appear here.", open: false });
  setDiagnostics("power-tools-diagnostics", { status: "idle", message: "No troubleshooting bundle or run report has been generated yet." }, { hint: "Troubleshooting bundle and run report outputs appear here.", open: false });
  try {
    await loadBootstrap({ staged: true });
  } catch (error) {
    applyBootstrapFailureState(error);
  }
});
