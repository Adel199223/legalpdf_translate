import { fetchJson } from "./api.js";
import { appState } from "./state.js";
import { applyActionFailureFeedbackToUi } from "./action_feedback_presentation.js";
import { runWithBusy } from "./busy_ui.js";
import {
  buildSettingsActionFeedback,
  buildSettingsStatusPresentation,
} from "./settings_presentation.js";
import {
  buildPowerToolsArmWindowTracePresentation,
  buildPowerToolsBootstrapPresentation,
  buildPowerToolsBuilderApplyPresentation,
  buildPowerToolsBuilderRunPresentation,
  buildPowerToolsCalibrationRunPresentation,
  buildPowerToolsDebugBundlePresentation,
  buildPowerToolsGlossaryExportPresentation,
  buildPowerToolsGlossarySavePresentation,
  buildPowerToolsRunReportPresentation,
} from "./power_tools_presentation.js";
import {
  renderBuilderSourceModeInto,
  renderCredentialRecoveryStateInto,
  renderLatestRunDirsInto,
  renderPowerToolsBuilderDefaultsInto,
  renderPowerToolsCalibrationDefaultsInto,
  renderPowerToolsCheckboxInto,
  renderPowerToolsCredentialInputClearInto,
  renderPowerToolsFieldValueInto,
  renderPowerToolsGlossaryFormInto,
  renderPowerToolsResultFieldsInto,
  renderPowerToolsSettingsAdminFormInto,
  setDiagnostics,
  setPanelStatus,
} from "./power_tools_ui.js";

function qs(id) {
  return document.getElementById(id);
}

function fieldValue(id) {
  return qs(id)?.value ?? "";
}

function setFieldValue(id, value) {
  renderPowerToolsFieldValueInto(qs(id), value);
}

function setCheckbox(id, value) {
  renderPowerToolsCheckboxInto(qs(id), value);
}

function parseJsonObject(text, label) {
  const cleaned = String(text ?? "").trim();
  if (cleaned === "") {
    return {};
  }
  let parsed;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed;
}

function parseJsonArray(text, label) {
  const cleaned = String(text ?? "").trim();
  if (cleaned === "") {
    return [];
  }
  let parsed;
  try {
    parsed = JSON.parse(cleaned);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON array.`);
  }
  return parsed;
}

function prettyJson(value) {
  return JSON.stringify(value ?? {}, null, 2);
}

function splitLines(text) {
  return String(text ?? "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function appendUniqueLine(id, value) {
  const lines = new Set(splitLines(fieldValue(id)));
  if (value) {
    lines.add(String(value));
  }
  setFieldValue(id, Array.from(lines).join("\n"));
}

async function fetchJsonAllowFailed(path, options = {}) {
  try {
    return await fetchJson(path, appState, options);
  } catch (error) {
    if (error?.isLocalServerUnavailable || Number(error?.status || 0) >= 500) {
      throw error;
    }
    if (error?.payload && typeof error.payload === "object") {
      return error.payload;
    }
    throw error;
  }
}

const settingsFieldMap = {
  "settings-default-lang": "default_lang",
  "settings-default-effort": "default_effort",
  "settings-default-effort-policy": "default_effort_policy",
  "settings-default-images-mode": "default_images_mode",
  "settings-default-outdir": "default_outdir",
  "settings-default-workers": "default_workers",
  "settings-ocr-provider": "ocr_api_provider",
  "settings-ocr-provider-default": "ocr_api_provider_default",
  "settings-ocr-mode-default": "ocr_mode_default",
  "settings-ocr-engine-default": "ocr_engine_default",
  "settings-ocr-api-base-url": "ocr_api_base_url",
  "settings-ocr-api-model": "ocr_api_model",
  "settings-ocr-api-env": "ocr_api_key_env_name",
  "settings-gmail-gog-path": "gmail_gog_path",
  "settings-gmail-account-email": "gmail_account_email",
  "settings-gmail-bridge-port": "gmail_intake_port",
  "settings-transport-retries": "perf_max_transport_retries",
  "settings-backoff-cap": "perf_backoff_cap_seconds",
  "settings-timeout-text": "perf_timeout_text_seconds",
  "settings-timeout-image": "perf_timeout_image_seconds",
};

const settingsCheckboxMap = {
  "settings-default-resume": "default_resume",
  "settings-default-keep": "default_keep_intermediates",
  "settings-default-breaks": "default_page_breaks",
  "settings-allow-xhigh": "allow_xhigh_escalation",
  "settings-gmail-bridge-enabled": "gmail_intake_bridge_enabled",
  "settings-diagnostics-admin-mode": "diagnostics_admin_mode",
  "settings-diagnostics-snippets": "diagnostics_include_sanitized_snippets",
  "settings-diagnostics-verbose": "diagnostics_verbose_metadata_logs",
  "settings-diagnostics-cost": "diagnostics_show_cost_summary",
  "settings-metadata-ai-enabled": "metadata_ai_enabled",
  "settings-metadata-photo-enabled": "metadata_photo_enabled",
  "settings-service-equals-case": "service_equals_case_by_default",
};

let currentSettingsFormValues = {};

function nodesForIds(ids) {
  const nodes = {};
  for (const id of ids) {
    nodes[id] = qs(id);
  }
  return nodes;
}

function renderProviderState(providerState, { preserveStatus = false } = {}) {
  if (!providerState) {
    return;
  }
  renderCredentialRecoveryStateInto({
    translation: qs("settings-translation-key-state"),
    ocr: qs("settings-ocr-key-state"),
    nativeHost: qs("settings-native-host-state"),
    word: qs("settings-word-pdf-export-state"),
  }, providerState);
  const readiness = buildSettingsReadinessSummary(providerState);
  if (!preserveStatus) {
    setPanelStatus("settings", readiness.tone, readiness.message);
  }
  if (!preserveStatus) {
    setDiagnostics("settings-test", providerState, {
      hint: readiness.hint,
      open: false,
    });
  }
}

function buildSettingsReadinessSummary(providerState) {
  return buildSettingsStatusPresentation(providerState);
}

function renderSettingsAdminPayload(settingsAdmin, { preserveStatus = false } = {}) {
  if (!settingsAdmin) {
    return;
  }
  const values = settingsAdmin.form_values || {};
  currentSettingsFormValues = { ...currentSettingsFormValues, ...values };
  const fieldValues = {};
  for (const [id, key] of Object.entries(settingsFieldMap)) {
    fieldValues[id] = values[key] ?? "";
  }
  const checkboxValues = {};
  for (const [id, key] of Object.entries(settingsCheckboxMap)) {
    checkboxValues[id] = values[key];
  }
  renderPowerToolsSettingsAdminFormInto({
    fields: nodesForIds(Object.keys(settingsFieldMap)),
    checkboxes: nodesForIds(Object.keys(settingsCheckboxMap)),
    defaultRateJson: qs("settings-default-rate-json"),
  }, {
    fieldValues,
    checkboxValues,
    defaultRateJson: prettyJson(values.default_rate_per_word || {}),
  });
  renderProviderState(settingsAdmin.provider_state || {}, { preserveStatus });
}

function renderLatestRunDirs(items) {
  renderLatestRunDirsInto(qs("power-tools-latest-run-dirs"), items, {
    onUseForReport(item) {
      setFieldValue("diagnostics-run-dir", item.run_dir || "");
      setPanelStatus("power-tools", "", `Selected ${item.name || "run"} for troubleshooting files.`);
    },
    onAddToBuilder(item) {
      appendUniqueLine("builder-run-dirs", item.run_dir || "");
      setFieldValue("builder-source-mode", "run_folders");
      syncBuilderSourceMode();
      setPanelStatus("power-tools", "", `Added ${item.name || "run"} to glossary suggestions input.`);
    },
  });
}

function renderPowerToolsPayload(powerTools, { preserveStatus = false } = {}) {
  if (!powerTools) {
    return;
  }
  const presentation = buildPowerToolsBootstrapPresentation(powerTools);
  renderPowerToolsGlossaryFormInto({
    projectPath: qs("glossary-project-path"),
    personalJson: qs("glossary-personal-json"),
    projectJson: qs("glossary-project-json"),
    enabledTiersJson: qs("glossary-enabled-tiers-json"),
    promptAddendumJson: qs("glossary-prompt-addendum-json"),
  }, presentation.glossaryForm);
  renderPowerToolsBuilderDefaultsInto({
    sourceMode: qs("builder-source-mode"),
    targetLang: qs("builder-target-lang"),
    mode: qs("builder-mode"),
    lemmaEffort: qs("builder-lemma-effort"),
    lemmaEnabled: qs("builder-lemma-enabled"),
    runDirs: qs("builder-run-dirs"),
    pdfPaths: qs("builder-pdf-paths"),
    approvedJson: qs("builder-approved-json"),
  }, presentation.builderDefaults);
  syncBuilderSourceMode();

  renderPowerToolsCalibrationDefaultsInto({
    pdfPath: qs("calibration-pdf-path"),
    outputDir: qs("calibration-output-dir"),
    targetLang: qs("calibration-target-lang"),
    samplePages: qs("calibration-sample-pages"),
    userSeed: qs("calibration-user-seed"),
    excerptMaxChars: qs("calibration-excerpt-max-chars"),
    includeExcerpts: qs("calibration-include-excerpts"),
  }, presentation.calibrationDefaults);

  if (!fieldValue("diagnostics-run-dir")) {
    setFieldValue("diagnostics-run-dir", "");
  }
  renderLatestRunDirs(presentation.latestRunDirs);
  if (!preserveStatus) {
    setPanelStatus(
      "power-tools",
      presentation.status.tone,
      presentation.status.message,
    );
  }
  if (!preserveStatus) {
    setDiagnostics(
      "power-tools-diagnostics",
      presentation.diagnostics.value,
      {
        hint: presentation.diagnostics.hint,
        open: presentation.diagnostics.open,
      },
    );
  }
}

export function renderPowerToolsBootstrap(payload, options = {}) {
  const normalized = payload?.normalized_payload || {};
  if (normalized.settings_admin) {
    renderSettingsAdminPayload(normalized.settings_admin, options);
  }
  if (normalized.power_tools) {
    renderPowerToolsPayload(normalized.power_tools, options);
  }
}

function collectSettingsFormValues() {
  const values = { ...currentSettingsFormValues };
  for (const [id, key] of Object.entries(settingsFieldMap)) {
    values[key] = fieldValue(id);
  }
  for (const [id, key] of Object.entries(settingsCheckboxMap)) {
    values[key] = qs(id)?.checked === true;
  }
  values.default_rate_per_word = parseJsonObject(fieldValue("settings-default-rate-json"), "Default rate JSON");
  return values;
}

function collectGlossaryPayload() {
  return {
    personal_glossaries_by_lang: parseJsonObject(fieldValue("glossary-personal-json"), "Personal glossaries JSON"),
    project_glossaries_by_lang: parseJsonObject(fieldValue("glossary-project-json"), "Project glossaries JSON"),
    enabled_tiers_by_target_lang: parseJsonObject(fieldValue("glossary-enabled-tiers-json"), "Enabled tiers JSON"),
    prompt_addendum_by_lang: parseJsonObject(fieldValue("glossary-prompt-addendum-json"), "Prompt addendum JSON"),
    project_glossary_path: fieldValue("glossary-project-path"),
  };
}

function collectBuilderPayload() {
  return {
    source_mode: fieldValue("builder-source-mode") || "run_folders",
    target_lang: fieldValue("builder-target-lang") || "EN",
    builder_mode: fieldValue("builder-mode") || "full_text",
    lemma_enabled: qs("builder-lemma-enabled")?.checked === true,
    lemma_effort: fieldValue("builder-lemma-effort") || "high",
    run_dirs: splitLines(fieldValue("builder-run-dirs")),
    pdf_paths: splitLines(fieldValue("builder-pdf-paths")),
  };
}

function collectCalibrationPayload() {
  return {
    pdf_path: fieldValue("calibration-pdf-path"),
    output_dir: fieldValue("calibration-output-dir"),
    target_lang: fieldValue("calibration-target-lang") || "EN",
    sample_pages: fieldValue("calibration-sample-pages"),
    user_seed: fieldValue("calibration-user-seed"),
    include_excerpts: qs("calibration-include-excerpts")?.checked === true,
    excerpt_max_chars: fieldValue("calibration-excerpt-max-chars"),
  };
}

function syncBuilderSourceMode() {
  const sourceMode = fieldValue("builder-source-mode") || "run_folders";
  renderBuilderSourceModeInto({
    runDirs: qs("builder-run-dirs"),
    pdfPaths: qs("builder-pdf-paths"),
  }, sourceMode);
}

async function refreshSettingsAdmin({ preserveStatus = true } = {}) {
  const payload = await fetchJson("/api/settings/admin", appState);
  renderSettingsAdminPayload(payload.normalized_payload, { preserveStatus });
  return payload;
}

async function refreshPowerTools({ preserveStatus = true } = {}) {
  const payload = await fetchJson("/api/power-tools/bootstrap", appState);
  renderPowerToolsPayload(payload.normalized_payload, { preserveStatus });
  return payload;
}

async function handleSettingsSave() {
  const payload = await fetchJson("/api/settings/save", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ form_values: collectSettingsFormValues() }),
  });
  renderSettingsAdminPayload(
    {
      form_values: payload.normalized_payload?.form_values || {},
      provider_state: payload.diagnostics?.provider_state || {},
    },
    { preserveStatus: true },
  );
  setPanelStatus("settings", "ok", "Settings saved for the active runtime mode.");
  setDiagnostics("settings-admin", payload, {
    hint: "Saved settings and refreshed provider state.",
    open: false,
  });
}

function applySettingsActionFeedback(
  payload,
  fallback,
  {
    diagnosticsSlot = "settings-test",
    clearFieldId = "",
    invalidateBootstrapOnOk = false,
  } = {},
) {
  const feedback = buildSettingsActionFeedback(payload, fallback);
  if (Object.keys(feedback.providerState || {}).length) {
    renderProviderState(feedback.providerState, { preserveStatus: true });
  }
  setPanelStatus("settings", feedback.tone, feedback.message);
  setDiagnostics(diagnosticsSlot, payload, {
    hint: feedback.diagnosticsHint,
    open: feedback.diagnosticsOpen,
  });
  if (feedback.ok && clearFieldId) {
    renderPowerToolsCredentialInputClearInto(qs(clearFieldId));
  }
  if (feedback.ok && invalidateBootstrapOnOk) {
    window.dispatchEvent(new CustomEvent("legalpdf:bootstrap-invalidated"));
  }
  return feedback;
}

function applyActionFailureFeedback(
  error,
  { panelSlot = "power-tools", diagnosticsSlot = "power-tools-diagnostics", fallback = "" } = {},
) {
  return applyActionFailureFeedbackToUi(
    error,
    { panelSlot, diagnosticsSlot, fallback },
    { setPanelStatus, setDiagnostics },
  );
}

function applyPowerToolsActionPresentation(presentation = {}) {
  if (Object.keys(presentation.resultFields || {}).length) {
    renderPowerToolsResultFieldsInto({
      approvedJson: qs("builder-approved-json"),
      diagnosticsRunDir: qs("diagnostics-run-dir"),
    }, presentation.resultFields);
  }
  const status = presentation.status || {};
  setPanelStatus(status.slot || "power-tools", status.tone || "", status.message || "");
  const diagnostics = presentation.diagnostics || {};
  setDiagnostics(diagnostics.slot || "power-tools-diagnostics", diagnostics.value || {}, {
    hint: diagnostics.hint || "",
    open: diagnostics.open === true,
  });
  return presentation;
}

async function handleTranslationKeySave() {
  const payload = await fetchJsonAllowFailed("/api/settings/translation-key/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: fieldValue("settings-translation-key-input") }),
  });
  applySettingsActionFeedback(payload, "Translation key save completed.", {
    diagnosticsSlot: "settings-admin",
    clearFieldId: "settings-translation-key-input",
    invalidateBootstrapOnOk: true,
  });
}

async function handleTranslationKeyClear() {
  const payload = await fetchJsonAllowFailed("/api/settings/translation-key/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  applySettingsActionFeedback(payload, "Translation key clear completed.", {
    diagnosticsSlot: "settings-admin",
    clearFieldId: "settings-translation-key-input",
    invalidateBootstrapOnOk: true,
  });
}

async function handleOcrKeySave() {
  const payload = await fetchJsonAllowFailed("/api/settings/ocr-key/save", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key: fieldValue("settings-ocr-key-input") }),
  });
  applySettingsActionFeedback(payload, "OCR key save completed.", {
    diagnosticsSlot: "settings-admin",
    clearFieldId: "settings-ocr-key-input",
    invalidateBootstrapOnOk: true,
  });
}

async function handleOcrKeyClear() {
  const payload = await fetchJsonAllowFailed("/api/settings/ocr-key/clear", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  applySettingsActionFeedback(payload, "OCR key clear completed.", {
    diagnosticsSlot: "settings-admin",
    clearFieldId: "settings-ocr-key-input",
    invalidateBootstrapOnOk: true,
  });
}

async function handleSettingsPreflight() {
  const payload = await fetchJson("/api/settings/preflight", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const providerState = payload.normalized_payload || {};
  renderProviderState(providerState, { preserveStatus: true });
  const readiness = buildSettingsReadinessSummary(providerState);
  setPanelStatus("settings", readiness.tone, `Provider and host preflight refreshed. ${readiness.message}`);
  setDiagnostics("settings-test", payload, {
    hint: readiness.hint,
    open: false,
  });
}

async function handleOcrTest() {
  const payload = await fetchJsonAllowFailed("/api/settings/ocr-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  applySettingsActionFeedback(payload, "OCR provider test completed.");
}

async function handleTranslationTest() {
  const payload = await fetchJsonAllowFailed("/api/settings/translation-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  applySettingsActionFeedback(payload, "Translation auth test completed.");
}

async function handleNativeHostTest() {
  const payload = await fetchJsonAllowFailed("/api/settings/native-host-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  applySettingsActionFeedback(payload, "Native-host diagnostics refreshed.");
}

async function handleNativeHostRepair() {
  const payload = await fetchJsonAllowFailed("/api/settings/native-host-repair", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  applySettingsActionFeedback(payload, "Native-host repair completed.", {
    diagnosticsSlot: "settings-admin",
    invalidateBootstrapOnOk: true,
  });
}

async function handleWordPdfExportTest() {
  const payload = await fetchJsonAllowFailed("/api/settings/word-pdf-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  applySettingsActionFeedback(payload, "Word PDF export test completed.");
}

async function handleGmailPrereqs() {
  const payload = await fetchJson("/api/settings/gmail-prereqs", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const tone = payload.normalized_payload?.ready ? "ok" : "warn";
  setPanelStatus("settings", tone, payload.normalized_payload?.message || "Gmail prereq check completed.");
  setDiagnostics("settings-test", payload, {
    hint: payload.normalized_payload?.message || "Gmail draft prerequisite check completed.",
    open: !payload.normalized_payload?.ready,
  });
}

async function handleGlossarySave() {
  const body = collectGlossaryPayload();
  const payload = await fetchJson("/api/power-tools/glossary/save", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  applyPowerToolsActionPresentation(buildPowerToolsGlossarySavePresentation(payload));
  await refreshPowerTools({ preserveStatus: true });
}

async function handleGlossaryExport() {
  const body = {
    ...collectGlossaryPayload(),
    title: fieldValue("glossary-markdown-title"),
  };
  const payload = await fetchJson("/api/power-tools/glossary/export-markdown", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  applyPowerToolsActionPresentation(buildPowerToolsGlossaryExportPresentation(payload));
}

async function handleBuilderRun() {
  const payload = await fetchJson("/api/power-tools/glossary-builder/run", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectBuilderPayload()),
  });
  applyPowerToolsActionPresentation(buildPowerToolsBuilderRunPresentation(payload));
}

async function handleBuilderApply() {
  const payload = await fetchJson("/api/power-tools/glossary-builder/apply", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      suggestions: parseJsonArray(fieldValue("builder-approved-json"), "Approved suggestions JSON"),
      project_glossary_path: fieldValue("glossary-project-path"),
    }),
  });
  applyPowerToolsActionPresentation(buildPowerToolsBuilderApplyPresentation(payload));
}

async function handleCalibrationRun() {
  const payload = await fetchJson("/api/power-tools/calibration/run", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectCalibrationPayload()),
  });
  applyPowerToolsActionPresentation(buildPowerToolsCalibrationRunPresentation(payload));
}

async function handleDebugBundle() {
  const payload = await fetchJson("/api/power-tools/diagnostics/debug-bundle", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_dir: fieldValue("diagnostics-run-dir") }),
  });
  applyPowerToolsActionPresentation(buildPowerToolsDebugBundlePresentation(payload));
}

async function handleRunReport() {
  const payload = await fetchJson("/api/power-tools/diagnostics/run-report", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_dir: fieldValue("diagnostics-run-dir") }),
  });
  applyPowerToolsActionPresentation(buildPowerToolsRunReportPresentation(payload));
}

async function handleArmWindowTrace() {
  const payload = await fetchJson("/api/power-tools/diagnostics/arm-window-trace", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  applyPowerToolsActionPresentation(buildPowerToolsArmWindowTracePresentation(payload));
}

export function initializePowerToolsUi() {
  const settingsActionButtons = [
    "settings-save",
    "settings-save-translation-key",
    "settings-clear-translation-key",
    "settings-save-ocr-key",
    "settings-clear-ocr-key",
    "settings-test-native-host",
    "settings-repair-native-host",
    "settings-test-translation",
    "settings-test-ocr",
    "settings-test-word-pdf",
    "settings-test-gmail",
  ];

  qs("builder-source-mode")?.addEventListener("change", syncBuilderSourceMode);

  qs("settings-refresh-admin")?.addEventListener("click", async () => {
    await runWithBusy(["settings-refresh-admin"], { "settings-refresh-admin": "Refreshing..." }, async () => {
      try {
        await refreshSettingsAdmin({ preserveStatus: false });
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "settings",
          diagnosticsSlot: "settings-admin",
          fallback: "Settings refresh failed.",
        });
      }
    });
  });

  qs("settings-run-preflight")?.addEventListener("click", async () => {
    await runWithBusy(["settings-run-preflight"], { "settings-run-preflight": "Checking..." }, async () => {
      try {
        await handleSettingsPreflight();
      } catch (error) {
        applyActionFailureFeedback(error, {
          panelSlot: "settings",
          diagnosticsSlot: "settings-test",
          fallback: "Settings preflight failed.",
        });
      }
    });
  });

  qs("settings-save")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-save": "Saving..." },
      async () => {
        try {
          await handleSettingsSave();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-admin",
            fallback: "Settings save failed.",
          });
        }
      },
    );
  });

  qs("settings-save-translation-key")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-save-translation-key": "Saving..." },
      async () => {
        try {
          await handleTranslationKeySave();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-admin",
            fallback: "Saving the translation key failed.",
          });
        }
      },
    );
  });

  qs("settings-clear-translation-key")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-clear-translation-key": "Clearing..." },
      async () => {
        try {
          await handleTranslationKeyClear();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-admin",
            fallback: "Clearing the translation key failed.",
          });
        }
      },
    );
  });

  qs("settings-save-ocr-key")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-save-ocr-key": "Saving..." },
      async () => {
        try {
          await handleOcrKeySave();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-admin",
            fallback: "Saving the OCR key failed.",
          });
        }
      },
    );
  });

  qs("settings-clear-ocr-key")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-clear-ocr-key": "Clearing..." },
      async () => {
        try {
          await handleOcrKeyClear();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-admin",
            fallback: "Clearing the OCR key failed.",
          });
        }
      },
    );
  });

  qs("settings-test-ocr")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-test-ocr": "Testing..." },
      async () => {
        try {
          await handleOcrTest();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-test",
            fallback: "OCR provider test failed.",
          });
        }
      },
    );
  });

  qs("settings-test-translation")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-test-translation": "Testing..." },
      async () => {
        try {
          await handleTranslationTest();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-test",
            fallback: "Translation auth test failed.",
          });
        }
      },
    );
  });

  qs("settings-test-native-host")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-test-native-host": "Testing..." },
      async () => {
        try {
          await handleNativeHostTest();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-test",
            fallback: "Native-host test failed.",
          });
        }
      },
    );
  });

  qs("settings-repair-native-host")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-repair-native-host": "Repairing..." },
      async () => {
        try {
          await handleNativeHostRepair();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-admin",
            fallback: "Native-host repair failed.",
          });
        }
      },
    );
  });

  qs("settings-test-word-pdf")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-test-word-pdf": "Testing..." },
      async () => {
        try {
          await handleWordPdfExportTest();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-test",
            fallback: "Word PDF export test failed.",
          });
        }
      },
    );
  });

  qs("settings-test-gmail")?.addEventListener("click", async () => {
    await runWithBusy(
      settingsActionButtons,
      { "settings-test-gmail": "Checking..." },
      async () => {
        try {
          await handleGmailPrereqs();
        } catch (error) {
          applyActionFailureFeedback(error, {
            panelSlot: "settings",
            diagnosticsSlot: "settings-test",
            fallback: "Gmail prerequisite check failed.",
          });
        }
      },
    );
  });

  qs("power-tools-refresh")?.addEventListener("click", async () => {
    await runWithBusy(["power-tools-refresh"], { "power-tools-refresh": "Refreshing..." }, async () => {
      try {
        await refreshPowerTools({ preserveStatus: false });
      } catch (error) {
        applyActionFailureFeedback(error, {
          fallback: "Advanced tools refresh failed.",
        });
      }
    });
  });

  qs("glossary-save")?.addEventListener("click", async () => {
    await runWithBusy(
      ["glossary-save", "glossary-export-markdown"],
      { "glossary-save": "Saving..." },
      async () => {
        try {
          await handleGlossarySave();
        } catch (error) {
          applyActionFailureFeedback(error, {
            diagnosticsSlot: "power-tools-glossary",
            fallback: "Glossary save failed.",
          });
        }
      },
    );
  });

  qs("glossary-export-markdown")?.addEventListener("click", async () => {
    await runWithBusy(
      ["glossary-save", "glossary-export-markdown"],
      { "glossary-export-markdown": "Exporting..." },
      async () => {
        try {
          await handleGlossaryExport();
        } catch (error) {
          applyActionFailureFeedback(error, {
            diagnosticsSlot: "power-tools-glossary",
            fallback: "Glossary markdown export failed.",
          });
        }
      },
    );
  });

  qs("builder-run")?.addEventListener("click", async () => {
    await runWithBusy(
      ["builder-run", "builder-apply"],
      { "builder-run": "Running..." },
      async () => {
        try {
          await handleBuilderRun();
        } catch (error) {
          applyActionFailureFeedback(error, {
            diagnosticsSlot: "power-tools-builder",
            fallback: "Build suggestions failed.",
          });
        }
      },
    );
  });

  qs("builder-apply")?.addEventListener("click", async () => {
    await runWithBusy(
      ["builder-run", "builder-apply"],
      { "builder-apply": "Applying..." },
      async () => {
        try {
          await handleBuilderApply();
        } catch (error) {
          applyActionFailureFeedback(error, {
            diagnosticsSlot: "power-tools-builder",
            fallback: "Apply selected suggestions failed.",
          });
        }
      },
    );
  });

  qs("calibration-run")?.addEventListener("click", async () => {
    await runWithBusy(["calibration-run"], { "calibration-run": "Running..." }, async () => {
      try {
        await handleCalibrationRun();
      } catch (error) {
        applyActionFailureFeedback(error, {
          diagnosticsSlot: "power-tools-calibration",
          fallback: "Quality check failed.",
        });
      }
    });
  });

  qs("diagnostics-create-bundle")?.addEventListener("click", async () => {
    await runWithBusy(
      ["diagnostics-arm-window-trace", "diagnostics-create-bundle", "diagnostics-generate-report"],
      { "diagnostics-create-bundle": "Bundling..." },
      async () => {
        try {
          await handleDebugBundle();
        } catch (error) {
          applyActionFailureFeedback(error, {
            fallback: "Create troubleshooting bundle failed.",
          });
        }
      },
    );
  });

  qs("diagnostics-arm-window-trace")?.addEventListener("click", async () => {
    await runWithBusy(
      ["diagnostics-arm-window-trace", "diagnostics-create-bundle", "diagnostics-generate-report"],
      { "diagnostics-arm-window-trace": "Arming..." },
      async () => {
        try {
          await handleArmWindowTrace();
        } catch (error) {
          applyActionFailureFeedback(error, {
            fallback: "Capture startup window trace failed.",
          });
        }
      },
    );
  });

  qs("diagnostics-generate-report")?.addEventListener("click", async () => {
    await runWithBusy(
      ["diagnostics-arm-window-trace", "diagnostics-create-bundle", "diagnostics-generate-report"],
      { "diagnostics-generate-report": "Generating..." },
      async () => {
        try {
          await handleRunReport();
        } catch (error) {
          applyActionFailureFeedback(error, {
            fallback: "Run report generation failed.",
          });
        }
      },
    );
  });
}
