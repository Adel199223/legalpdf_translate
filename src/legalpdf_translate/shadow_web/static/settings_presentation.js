function cleanText(value, fallback = "Unavailable") {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function titleCaseToken(value, fallback = "Unknown") {
  const text = String(value ?? "").trim();
  if (!text) {
    return fallback;
  }
  return text
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function boolLabel(value, { ready = "ready", notReady = "not ready" } = {}) {
  return value ? ready : notReady;
}

function buildOcrDefaultsLabel(summary = {}) {
  const provider = titleCaseToken(summary.ocr_api_provider_default, "?");
  const mode = titleCaseToken(summary.ocr_mode_default, "?");
  const engine = titleCaseToken(summary.ocr_engine_default, "?");
  return `${provider} / ${mode} / ${engine}`;
}

function translationConfigured(providerState = {}) {
  return providerState.translation?.credentials_configured === true;
}

function ocrReady(providerState = {}) {
  const ocr = providerState.ocr || {};
  return ocr.api_configured === true || ocr.local_available === true;
}

function gmailReady(providerState = {}) {
  return providerState.gmail_draft?.ready === true;
}

function wordReady(providerState = {}) {
  const word = providerState.word_pdf_export || {};
  return word.finalization_ready === true || word.ok === true;
}

function browserHelperReady(providerState = {}) {
  return providerState.native_host?.ready === true;
}

function wordCapabilityText(providerState = {}) {
  const word = providerState.word_pdf_export || {};
  const launch = word.launch_preflight || word.preflight || {};
  const canary = word.export_canary || {};
  if (wordReady(providerState)) {
    return "Word and PDF output are ready for document finalization.";
  }
  return cleanText(
    canary.message || launch.message,
    "Word or PDF output needs attention before finalization.",
  );
}

export function buildSettingsSummaryItems(summary = {}, providerState = {}) {
  return [
    { label: "Theme", value: cleanText(summary.ui_theme, "Unknown") },
    { label: "Default language", value: cleanText(summary.default_lang, "Unknown") },
    { label: "Default output folder", value: cleanText(summary.default_outdir, "Not configured") },
    {
      label: "Translation provider",
      value: translationConfigured(providerState) ? "Configured" : "Not configured",
    },
    {
      label: "OCR defaults",
      value: buildOcrDefaultsLabel(summary),
    },
    {
      label: "Gmail intake",
      value: summary.gmail_intake_bridge_enabled
        ? `Enabled on ${cleanText(summary.gmail_intake_port, "unknown port")}`
        : "Disabled",
    },
    { label: "Settings file", value: cleanText(summary.settings_path) },
    { label: "Saved work database", value: cleanText(summary.job_log_db_path) },
    { label: "Output folder", value: cleanText(summary.outputs_dir) },
  ];
}

export function buildSettingsStatusPresentation(providerState = {}) {
  const translationReady = translationConfigured(providerState);
  const ocrIsReady = ocrReady(providerState);
  const gmailIsReady = gmailReady(providerState);
  const wordIsReady = wordReady(providerState);
  const helperReady = browserHelperReady(providerState);
  const tone = translationReady && ocrIsReady && gmailIsReady && wordIsReady && helperReady ? "ok" : "warn";
  return {
    tone,
    message: `Settings loaded. Translation provider is ${boolLabel(translationReady, { ready: "configured", notReady: "not configured" })}, OCR is ${boolLabel(ocrIsReady)}, Gmail replies are ${boolLabel(gmailIsReady)}, and Word/PDF output is ${boolLabel(wordIsReady, { ready: "ready", notReady: "degraded" })}.`,
    hint: "Provider tests, browser-helper checks, and detailed readiness payloads appear here.",
  };
}

export function buildSettingsCapabilityCards(payload = {}) {
  const providerState = payload?.normalized_payload?.settings_admin?.provider_state || {};
  const translationReady = translationConfigured(providerState);
  const ocrIsReady = ocrReady(providerState);
  const gmailIsReady = gmailReady(providerState);
  const helperReady = browserHelperReady(providerState);
  const wordIsReady = wordReady(providerState);
  return [
    {
      title: "Translation provider",
      text: translationReady
        ? "Translation credentials are ready for normal work."
        : "Add or test translation credentials before live translation.",
      status: translationReady ? "ok" : "warn",
      label: translationReady ? "Ready" : "Needs setup",
    },
    {
      title: "OCR tools",
      text: ocrIsReady
        ? "Document-reading tools are ready."
        : "OCR needs attention before image-heavy jobs.",
      status: ocrIsReady ? "ok" : "warn",
      label: ocrIsReady ? "Ready" : "Needs attention",
    },
    {
      title: "Gmail replies",
      text: gmailIsReady
        ? "Gmail reply preparation is ready when you need it."
        : "Gmail reply preparation needs attention before live use.",
      status: gmailIsReady ? "ok" : "warn",
      label: gmailIsReady ? "Ready" : "Needs attention",
    },
    {
      title: "Browser helper",
      text: helperReady
        ? "The browser helper is ready for Gmail and repair checks."
        : "The browser helper needs attention before Gmail intake or repair tasks.",
      status: helperReady ? "ok" : "warn",
      label: helperReady ? "Ready" : "Needs attention",
    },
    {
      title: "Word/PDF output",
      text: wordCapabilityText(providerState),
      status: wordIsReady ? "ok" : "warn",
      label: wordIsReady ? "Ready" : "Needs attention",
    },
  ];
}
