const GOOGLE_PHOTOS_DISCONNECT_DIAGNOSTICS_MESSAGE =
  "Google Photos local connection was cleared. Connect again before choosing a photo.";
const GOOGLE_PHOTOS_DISCONNECT_PANEL_MESSAGE =
  "Google Photos local connection was cleared. Connect Google Photos again.";
const GOOGLE_PHOTOS_DISCONNECT_SUMMARY_MESSAGE =
  "Google Photos local connection was cleared. Connect Google Photos again before choosing a photo.";
const GOOGLE_PHOTOS_SIGN_IN_READY_MESSAGE =
  "Google sign-in is ready. If no Google tab opened, click Open Google sign-in.";
const GOOGLE_PHOTOS_CONNECTED_PANEL_MESSAGE =
  "Google Photos connected. Choose a photo to recover Interpretation metadata.";
const GOOGLE_PHOTOS_CONNECTED_SUMMARY_MESSAGE =
  "Google Photos connected. Choose a photo to continue.";
const GOOGLE_PHOTOS_PENDING_PANEL_MESSAGE =
  "Google Photos authorization is still pending. Use Open Google sign-in if no Google tab opened, or return after completing Google consent.";
const GOOGLE_PHOTOS_PENDING_SUMMARY_MESSAGE =
  "Still waiting for Google Photos authorization. Use Open Google sign-in if no Google tab opened.";
const GOOGLE_PHOTOS_PICKER_INSTRUCTION_MESSAGE =
  "A Google Photos tab should open. Select one photo, then click Done. If no tab opened, click Open Google Photos Picker. LegalPDF will continue waiting here until selection is completed.";
const GOOGLE_PHOTOS_SELECTION_FOUND_MESSAGE =
  "Selected photo found. Recovering Interpretation metadata...";
const GOOGLE_PHOTOS_IMPORT_EMPTY_MESSAGE =
  "Google Photos import completed, but no metadata fields were recovered automatically.";

function asObject(value) {
  return value && typeof value === "object" ? value : {};
}

function cleanText(value) {
  return String(value ?? "").trim();
}

function cleanTextList(values) {
  if (!Array.isArray(values)) {
    return [];
  }
  return values.map((value) => cleanText(value)).filter(Boolean);
}

function panel(tone, message) {
  return { tone, message };
}

function summary(message) {
  return { message };
}

function diagnostics(hint, open) {
  return { hint, open: Boolean(open) };
}

export function buildGooglePhotosConnectBusyPresentation(input = {}) {
  const options = asObject(input);
  return {
    "google-photos-connect": options.connected ? "Reconnecting..." : "Connecting...",
  };
}

export function buildGooglePhotosChooseBusyPresentation() {
  return { "google-photos-choose": "Choosing..." };
}

export function buildGooglePhotosDisconnectPresentation() {
  return {
    diagnostics: diagnostics(GOOGLE_PHOTOS_DISCONNECT_DIAGNOSTICS_MESSAGE, false),
    panel: panel("warn", GOOGLE_PHOTOS_DISCONNECT_PANEL_MESSAGE),
    summary: summary(GOOGLE_PHOTOS_DISCONNECT_SUMMARY_MESSAGE),
  };
}

export function buildGooglePhotosConnectionReadyPresentation() {
  return {
    panel: panel("info", GOOGLE_PHOTOS_SIGN_IN_READY_MESSAGE),
    summary: summary(GOOGLE_PHOTOS_SIGN_IN_READY_MESSAGE),
  };
}

export function buildGooglePhotosConnectionSucceededPresentation() {
  return {
    panel: panel("ok", GOOGLE_PHOTOS_CONNECTED_PANEL_MESSAGE),
    summary: summary(GOOGLE_PHOTOS_CONNECTED_SUMMARY_MESSAGE),
  };
}

export function buildGooglePhotosConnectionPendingPresentation() {
  return {
    panel: panel("warn", GOOGLE_PHOTOS_PENDING_PANEL_MESSAGE),
    summary: summary(GOOGLE_PHOTOS_PENDING_SUMMARY_MESSAGE),
  };
}

export function buildGooglePhotosPickerLaunchPresentation() {
  return {
    panel: panel("info", GOOGLE_PHOTOS_PICKER_INSTRUCTION_MESSAGE),
    summary: summary(GOOGLE_PHOTOS_PICKER_INSTRUCTION_MESSAGE),
  };
}

export function buildGooglePhotosPickerWaitingPresentation() {
  return {
    panel: panel("info", "Waiting for Google Photos selection..."),
    summary: summary(GOOGLE_PHOTOS_PICKER_INSTRUCTION_MESSAGE),
  };
}

export function buildGooglePhotosSelectionFoundPresentation(input = {}) {
  const options = asObject(input);
  return {
    summary: summary(cleanText(options.selectionWarning) || GOOGLE_PHOTOS_SELECTION_FOUND_MESSAGE),
  };
}

export function buildGooglePhotosImportPresentation(input = {}) {
  const options = asObject(input);
  const extractedFields = cleanTextList(options.extractedFields);
  const message = extractedFields.length
    ? `Recovered ${extractedFields.join(", ")} from the Google Photos selection.`
    : GOOGLE_PHOTOS_IMPORT_EMPTY_MESSAGE;
  const recovered = extractedFields.length > 0;
  return {
    diagnostics: diagnostics(message, !recovered),
    panel: panel(recovered ? "ok" : "warn", message),
    summary: summary(message),
  };
}
