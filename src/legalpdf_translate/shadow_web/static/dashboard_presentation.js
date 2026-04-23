function clampCount(value) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function titleCaseStatus(value) {
  return String(value || "")
    .trim()
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ") || "Unknown";
}

function buildDashboardStatusSummary(cards = []) {
  const hasNeedsAttention = cards.some((card) => ["warn", "bad"].includes(card.status));
  return hasNeedsAttention
    ? "Some tools may need attention before every workflow is ready."
    : "App status looks ready for normal work.";
}

function buildAppDataCard(runtime = {}) {
  const liveData = runtime.live_data === true;
  return {
    title: "App data",
    text: liveData
      ? "Using your regular app data and saved work."
      : "Using an isolated test copy of app data.",
    status: liveData ? "ok" : "info",
    label: liveData ? "Ready" : "Test mode",
  };
}

function buildSavedWorkCard(counts = {}) {
  const total = clampCount(counts.total);
  return {
    title: "Saved work",
    text: formatDashboardSavedWorkSummary(counts),
    status: total > 0 ? "ok" : "info",
    label: total > 0 ? "Available" : "Empty",
  };
}

function buildGmailToolsCard(gmailBridge = {}) {
  const status = String(gmailBridge.status || "").trim() || "warn";
  const ready = status === "ok";
  return {
    title: "Gmail tools",
    text: ready
      ? "Gmail attachment review is ready when you need it."
      : "Gmail tools need attention before live Gmail work.",
    status: ready ? "ok" : "warn",
    label: ready ? "Ready" : "Needs attention",
  };
}

function buildWordPdfToolsCard(wordState = {}) {
  const launchPreflight = wordState.launch_preflight || wordState.preflight || {};
  const exportCanary = wordState.export_canary || {};
  const ready = wordState.finalization_ready === true || wordState.ok === true;
  const blocked = wordState.finalization_ready === false || launchPreflight.ok === false || exportCanary.ok === false;
  return {
    title: "Word/PDF tools",
    text: ready
      ? "Word and PDF tools are ready for export and reply steps."
      : "Word or PDF tools need attention before final export steps.",
    status: ready ? "ok" : blocked ? "warn" : "info",
    label: ready ? "Ready" : blocked ? "Needs attention" : "Checking",
  };
}

function buildTranslationProviderCard(translation = {}, ocr = {}) {
  const configured = translation.credentials_configured === true;
  const ocrReady = ocr.api_configured === true || ocr.local_available === true;
  return {
    title: "Translation provider",
    text: configured
      ? ocrReady
        ? "Translation and document-reading tools are ready."
        : "Translation is ready, but document-reading tools may need attention."
      : "Add translation credentials in Settings before live translation.",
    status: configured ? (ocrReady ? "ok" : "warn") : "warn",
    label: configured ? "Ready" : "Needs setup",
  };
}

export function formatDashboardSavedWorkSummary(counts = {}) {
  const total = clampCount(counts.total);
  const translation = clampCount(counts.translation);
  const interpretation = clampCount(counts.interpretation);
  if (total === 0) {
    return "No saved work yet. Completed translations and interpretation requests will appear here.";
  }
  return `${total} saved item(s) available. ${translation} translation case(s) and ${interpretation} interpretation request(s) are ready to reopen.`;
}

export function deriveDashboardPresentation(payload = {}) {
  const normalized = payload?.normalized_payload || {};
  const counts = normalized.recent_job_counts || {};
  const runtime = normalized.runtime || {};
  const audit = normalized.parity_audit || {};
  const recommendation = audit.promotion_recommendation || {};
  const capabilities = payload?.capability_flags || {};
  const cards = [
    buildAppDataCard(runtime),
    buildSavedWorkCard(counts),
    buildGmailToolsCard(capabilities.gmail_bridge || {}),
    buildWordPdfToolsCard(capabilities.word_pdf_export || {}),
    buildTranslationProviderCard(capabilities.translation || {}, capabilities.ocr || {}),
  ];
  const recommendationReady = recommendation.status === "ready_for_daily_use";
  return {
    savedWorkSummary: formatDashboardSavedWorkSummary(counts),
    statusCards: cards,
    statusSummary: buildDashboardStatusSummary(cards),
    parityStatus: String(audit.summary || "").trim() || "Checking available app features...",
    readyCountLine: `${clampCount(audit.ready_count)}/${clampCount(audit.total_count)} overview area(s) are ready.`,
    resultNextTitle: "Try next",
    resultLimitsTitle: "Keep in mind",
    resultChipLabel: recommendationReady
      ? "Ready"
      : titleCaseStatus(recommendation.status),
  };
}
