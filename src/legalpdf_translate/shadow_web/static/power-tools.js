import { fetchJson } from "./api.js";
import { appState } from "./state.js";

function qs(id) {
  return document.getElementById(id);
}

function fieldValue(id) {
  return qs(id)?.value ?? "";
}

function setFieldValue(id, value) {
  const node = qs(id);
  if (node) {
    node.value = value ?? "";
  }
}

function setCheckbox(id, value) {
  const node = qs(id);
  if (node) {
    node.checked = Boolean(value);
  }
}

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

function renderProviderState(providerState, { preserveStatus = false } = {}) {
  if (!providerState) {
    return;
  }
  const ocr = providerState.ocr || {};
  const gmail = providerState.gmail_draft || {};
  const word = providerState.word_pdf_export || {};
  if (!preserveStatus) {
    const ocrReady = ocr.api_configured || ocr.local_available;
    const wordReady = word.ok;
    const tone = ocrReady && wordReady ? "ok" : "warn";
    const parts = [
      `OCR ${ocr.provider || "provider"} is ${ocrReady ? "usable" : "not ready"}.`,
      `Gmail drafts are ${gmail.ready ? "ready" : "not ready"}.`,
      `Word PDF export is ${wordReady ? "ready" : "degraded"}.`,
    ];
    setPanelStatus("settings", tone, parts.join(" "));
  }
  if (!preserveStatus) {
    setDiagnostics("settings-test", providerState, {
      hint: "Current OCR, Gmail draft, and Word host readiness.",
      open: false,
    });
  }
}

function renderSettingsAdminPayload(settingsAdmin, { preserveStatus = false } = {}) {
  if (!settingsAdmin) {
    return;
  }
  const values = settingsAdmin.form_values || {};
  currentSettingsFormValues = { ...currentSettingsFormValues, ...values };
  for (const [id, key] of Object.entries(settingsFieldMap)) {
    setFieldValue(id, values[key] ?? "");
  }
  for (const [id, key] of Object.entries(settingsCheckboxMap)) {
    setCheckbox(id, values[key]);
  }
  setFieldValue("settings-default-rate-json", prettyJson(values.default_rate_per_word || {}));
  renderProviderState(settingsAdmin.provider_state || {}, { preserveStatus });
}

function mergeLatestRunDirs(powerTools) {
  const diagnostics = powerTools?.diagnostics?.latest_run_dirs || [];
  const builder = powerTools?.glossary_builder?.latest_run_dirs || [];
  const seen = new Set();
  const output = [];
  for (const item of [...diagnostics, ...builder]) {
    const runDir = String(item?.run_dir || "").trim();
    if (!runDir || seen.has(runDir.toLowerCase())) {
      continue;
    }
    seen.add(runDir.toLowerCase());
    output.push(item);
  }
  return output;
}

function renderLatestRunDirs(items) {
  const container = qs("power-tools-latest-run-dirs");
  if (!container) {
    return;
  }
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = '<div class="empty-state">No recent run folders were discovered yet in this runtime mode.</div>';
    return;
  }
  for (const item of items) {
    const article = document.createElement("article");
    article.className = "history-item";

    const left = document.createElement("div");
    const title = document.createElement("strong");
    title.textContent = item.name || "run";
    const body = document.createElement("p");
    body.className = "word-break";
    body.textContent = item.run_dir || "";
    const meta = document.createElement("div");
    meta.className = "history-meta";
    for (const bit of [
      item.modified_at_iso || "",
      item.has_run_summary ? "summary" : "",
      item.has_run_state ? "state" : "",
      item.has_calibration_report ? "calibration" : "",
    ]) {
      if (!bit) {
        continue;
      }
      const small = document.createElement("small");
      small.textContent = bit;
      meta.appendChild(small);
    }
    left.appendChild(title);
    left.appendChild(body);
    left.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "panel-actions";
    const useForReport = document.createElement("button");
    useForReport.type = "button";
    useForReport.textContent = "Use For Report";
    useForReport.addEventListener("click", () => {
      setFieldValue("diagnostics-run-dir", item.run_dir || "");
      setPanelStatus("power-tools", "", `Selected ${item.name || "run"} for diagnostics output.`);
    });
    const addToBuilder = document.createElement("button");
    addToBuilder.type = "button";
    addToBuilder.textContent = "Add To Builder";
    addToBuilder.addEventListener("click", () => {
      appendUniqueLine("builder-run-dirs", item.run_dir || "");
      setFieldValue("builder-source-mode", "run_folders");
      syncBuilderSourceMode();
      setPanelStatus("power-tools", "", `Added ${item.name || "run"} to glossary builder input.`);
    });
    actions.appendChild(useForReport);
    actions.appendChild(addToBuilder);

    article.appendChild(left);
    article.appendChild(actions);
    container.appendChild(article);
  }
}

function renderPowerToolsPayload(powerTools, { preserveStatus = false } = {}) {
  if (!powerTools) {
    return;
  }
  const glossary = powerTools.glossary || {};
  setFieldValue("glossary-project-path", glossary.project_glossary_path || "");
  setFieldValue("glossary-personal-json", prettyJson(glossary.personal_glossaries_by_lang || {}));
  setFieldValue("glossary-project-json", prettyJson(glossary.project_glossaries_by_lang || {}));
  setFieldValue("glossary-enabled-tiers-json", prettyJson(glossary.enabled_tiers_by_target_lang || {}));
  setFieldValue("glossary-prompt-addendum-json", prettyJson(glossary.prompt_addendum_by_lang || {}));

  const builder = powerTools.glossary_builder || {};
  const builderDefaults = builder.defaults || {};
  setFieldValue("builder-source-mode", builderDefaults.source_mode || "run_folders");
  setFieldValue("builder-target-lang", builderDefaults.target_lang || "EN");
  setFieldValue("builder-mode", builderDefaults.mode || "full_text");
  setFieldValue("builder-lemma-effort", builderDefaults.lemma_effort || "high");
  setCheckbox("builder-lemma-enabled", builderDefaults.lemma_enabled);
  setFieldValue("builder-run-dirs", (builderDefaults.run_dirs || []).join("\n"));
  setFieldValue("builder-pdf-paths", (builderDefaults.pdf_paths || []).join("\n"));
  if (builder.last_result?.suggestions) {
    setFieldValue("builder-approved-json", prettyJson(builder.last_result.suggestions));
  }
  syncBuilderSourceMode();

  const calibration = powerTools.calibration || {};
  const calibrationDefaults = calibration.defaults || {};
  setFieldValue("calibration-pdf-path", calibrationDefaults.pdf_path || "");
  setFieldValue("calibration-output-dir", calibrationDefaults.output_dir || "");
  setFieldValue("calibration-target-lang", calibrationDefaults.target_lang || "EN");
  setFieldValue("calibration-sample-pages", calibrationDefaults.sample_pages ?? 5);
  setFieldValue("calibration-user-seed", calibrationDefaults.user_seed || "");
  setFieldValue("calibration-excerpt-max-chars", calibrationDefaults.excerpt_max_chars ?? 200);
  setCheckbox("calibration-include-excerpts", calibrationDefaults.include_excerpts);

  const diagnostics = powerTools.diagnostics || {};
  if (!fieldValue("diagnostics-run-dir")) {
    setFieldValue("diagnostics-run-dir", "");
  }
  renderLatestRunDirs(mergeLatestRunDirs(powerTools));
  if (!preserveStatus) {
    const latestCount = mergeLatestRunDirs(powerTools).length;
    setPanelStatus(
      "power-tools",
      latestCount > 0 ? "ok" : "",
      latestCount > 0
        ? `Glossary, calibration, and diagnostics tools are ready. ${latestCount} recent run folder(s) are available.`
        : "Glossary, calibration, and diagnostics tools are ready for this runtime mode.",
    );
  }
  if (!preserveStatus) {
    setDiagnostics(
      "power-tools-diagnostics",
      {
        outputs_root: diagnostics.outputs_root || "",
        runtime_metadata_path: diagnostics.runtime_metadata_path || "",
        latest_run_dirs: mergeLatestRunDirs(powerTools),
      },
      {
        hint: "Debug-bundle and run-report defaults for this runtime mode.",
        open: false,
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
  const useRunDirs = sourceMode === "run_folders";
  qs("builder-run-dirs").disabled = !useRunDirs;
  qs("builder-pdf-paths").disabled = useRunDirs;
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

async function handleSettingsPreflight() {
  const payload = await fetchJson("/api/settings/preflight", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  renderProviderState(payload.normalized_payload || {}, { preserveStatus: true });
  setPanelStatus(
    "settings",
    payload.normalized_payload?.word_pdf_export?.ok ? "ok" : "warn",
    "Provider and host preflight refreshed for the active runtime mode.",
  );
  setDiagnostics("settings-test", payload, {
    hint: "OCR, Gmail draft, and Word export host status.",
    open: false,
  });
}

async function handleOcrTest() {
  const payload = await fetchJson("/api/settings/ocr-test", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  const tone = payload.status === "ok" ? "ok" : "warn";
  setPanelStatus("settings", tone, payload.normalized_payload?.message || "OCR provider test completed.");
  setDiagnostics("settings-test", payload, {
    hint: payload.normalized_payload?.message || "OCR provider test completed.",
    open: payload.status !== "ok",
  });
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
  setPanelStatus("power-tools", "ok", "Glossary workspace saved for the active runtime mode.");
  setDiagnostics("power-tools-glossary", payload, {
    hint: "Glossary JSON persisted to browser settings and project glossary storage.",
    open: false,
  });
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
  setPanelStatus("power-tools", "ok", "Consistency glossary markdown exported.");
  setDiagnostics("power-tools-glossary", payload, {
    hint: payload.normalized_payload?.markdown_path || "Glossary markdown export completed.",
    open: false,
  });
}

async function handleBuilderRun() {
  const payload = await fetchJson("/api/power-tools/glossary-builder/run", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectBuilderPayload()),
  });
  if (payload.normalized_payload?.suggestions) {
    setFieldValue("builder-approved-json", prettyJson(payload.normalized_payload.suggestions));
  }
  setPanelStatus(
    "power-tools",
    "ok",
    `Glossary builder scanned ${payload.normalized_payload?.pages_scanned ?? 0} page(s) across ${payload.normalized_payload?.sources_processed ?? 0} source(s).`,
  );
  setDiagnostics("power-tools-builder", payload, {
    hint: payload.normalized_payload?.artifact_dir || "Glossary builder run completed.",
    open: false,
  });
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
  setPanelStatus("power-tools", "ok", "Approved glossary suggestions were applied.");
  setDiagnostics("power-tools-builder", payload, {
    hint: "Builder suggestions were merged into personal and project glossaries.",
    open: false,
  });
}

async function handleCalibrationRun() {
  const payload = await fetchJson("/api/power-tools/calibration/run", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectCalibrationPayload()),
  });
  setPanelStatus("power-tools", "ok", "Calibration audit completed.");
  setDiagnostics("power-tools-calibration", payload, {
    hint: payload.normalized_payload?.report_md_path || "Calibration audit artifacts were generated.",
    open: false,
  });
  const reportPath = String(payload.normalized_payload?.report_json_path || "").trim();
  if (reportPath) {
    setFieldValue("diagnostics-run-dir", reportPath.replace(/[\\/][^\\/]+$/, ""));
  }
}

async function handleDebugBundle() {
  const payload = await fetchJson("/api/power-tools/diagnostics/debug-bundle", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_dir: fieldValue("diagnostics-run-dir") }),
  });
  setPanelStatus("power-tools", "ok", "Browser debug bundle created.");
  setDiagnostics("power-tools-diagnostics", payload, {
    hint: payload.normalized_payload?.bundle_path || "Debug bundle created.",
    open: false,
  });
}

async function handleRunReport() {
  const payload = await fetchJson("/api/power-tools/diagnostics/run-report", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_dir: fieldValue("diagnostics-run-dir") }),
  });
  setPanelStatus("power-tools", "ok", "Run report generated.");
  setDiagnostics("power-tools-diagnostics", payload, {
    hint: payload.normalized_payload?.report_path || "Run report generated.",
    open: false,
  });
}

export function initializePowerToolsUi() {
  qs("builder-source-mode")?.addEventListener("change", syncBuilderSourceMode);

  qs("settings-refresh-admin")?.addEventListener("click", async () => {
    await runWithBusy(["settings-refresh-admin"], { "settings-refresh-admin": "Refreshing..." }, async () => {
      try {
        await refreshSettingsAdmin({ preserveStatus: false });
      } catch (error) {
        setPanelStatus("settings", "bad", error.message || "Settings refresh failed.");
        setDiagnostics("settings-admin", error, { hint: error.message || "Settings refresh failed.", open: true });
      }
    });
  });

  qs("settings-run-preflight")?.addEventListener("click", async () => {
    await runWithBusy(["settings-run-preflight"], { "settings-run-preflight": "Refreshing..." }, async () => {
      try {
        await handleSettingsPreflight();
      } catch (error) {
        setPanelStatus("settings", "bad", error.message || "Settings preflight failed.");
        setDiagnostics("settings-test", error, { hint: error.message || "Settings preflight failed.", open: true });
      }
    });
  });

  qs("settings-save")?.addEventListener("click", async () => {
    await runWithBusy(
      ["settings-save", "settings-test-ocr", "settings-test-gmail"],
      { "settings-save": "Saving..." },
      async () => {
        try {
          await handleSettingsSave();
        } catch (error) {
          setPanelStatus("settings", "bad", error.message || "Settings save failed.");
          setDiagnostics("settings-admin", error, { hint: error.message || "Settings save failed.", open: true });
        }
      },
    );
  });

  qs("settings-test-ocr")?.addEventListener("click", async () => {
    await runWithBusy(
      ["settings-save", "settings-test-ocr", "settings-test-gmail"],
      { "settings-test-ocr": "Testing..." },
      async () => {
        try {
          await handleOcrTest();
        } catch (error) {
          setPanelStatus("settings", "bad", error.message || "OCR provider test failed.");
          setDiagnostics("settings-test", error, { hint: error.message || "OCR provider test failed.", open: true });
        }
      },
    );
  });

  qs("settings-test-gmail")?.addEventListener("click", async () => {
    await runWithBusy(
      ["settings-save", "settings-test-ocr", "settings-test-gmail"],
      { "settings-test-gmail": "Checking..." },
      async () => {
        try {
          await handleGmailPrereqs();
        } catch (error) {
          setPanelStatus("settings", "bad", error.message || "Gmail prerequisite check failed.");
          setDiagnostics("settings-test", error, { hint: error.message || "Gmail prerequisite check failed.", open: true });
        }
      },
    );
  });

  qs("power-tools-refresh")?.addEventListener("click", async () => {
    await runWithBusy(["power-tools-refresh"], { "power-tools-refresh": "Refreshing..." }, async () => {
      try {
        await refreshPowerTools({ preserveStatus: false });
      } catch (error) {
        setPanelStatus("power-tools", "bad", error.message || "Power tools refresh failed.");
        setDiagnostics("power-tools-diagnostics", error, { hint: error.message || "Power tools refresh failed.", open: true });
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
          setPanelStatus("power-tools", "bad", error.message || "Glossary save failed.");
          setDiagnostics("power-tools-glossary", error, { hint: error.message || "Glossary save failed.", open: true });
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
          setPanelStatus("power-tools", "bad", error.message || "Glossary markdown export failed.");
          setDiagnostics("power-tools-glossary", error, { hint: error.message || "Glossary markdown export failed.", open: true });
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
          setPanelStatus("power-tools", "bad", error.message || "Glossary builder failed.");
          setDiagnostics("power-tools-builder", error, { hint: error.message || "Glossary builder failed.", open: true });
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
          setPanelStatus("power-tools", "bad", error.message || "Applying builder suggestions failed.");
          setDiagnostics("power-tools-builder", error, { hint: error.message || "Applying builder suggestions failed.", open: true });
        }
      },
    );
  });

  qs("calibration-run")?.addEventListener("click", async () => {
    await runWithBusy(["calibration-run"], { "calibration-run": "Running..." }, async () => {
      try {
        await handleCalibrationRun();
      } catch (error) {
        setPanelStatus("power-tools", "bad", error.message || "Calibration audit failed.");
        setDiagnostics("power-tools-calibration", error, { hint: error.message || "Calibration audit failed.", open: true });
      }
    });
  });

  qs("diagnostics-create-bundle")?.addEventListener("click", async () => {
    await runWithBusy(
      ["diagnostics-create-bundle", "diagnostics-generate-report"],
      { "diagnostics-create-bundle": "Bundling..." },
      async () => {
        try {
          await handleDebugBundle();
        } catch (error) {
          setPanelStatus("power-tools", "bad", error.message || "Debug bundle creation failed.");
          setDiagnostics("power-tools-diagnostics", error, { hint: error.message || "Debug bundle creation failed.", open: true });
        }
      },
    );
  });

  qs("diagnostics-generate-report")?.addEventListener("click", async () => {
    await runWithBusy(
      ["diagnostics-create-bundle", "diagnostics-generate-report"],
      { "diagnostics-generate-report": "Generating..." },
      async () => {
        try {
          await handleRunReport();
        } catch (error) {
          setPanelStatus("power-tools", "bad", error.message || "Run report generation failed.");
          setDiagnostics("power-tools-diagnostics", error, { hint: error.message || "Run report generation failed.", open: true });
        }
      },
    );
  });
}
