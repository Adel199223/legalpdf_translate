import { clearNode, createEmptyState, createTextElement } from "./safe_rendering.js";
import { formatDiagnosticValue } from "./diagnostics_presentation.js";

function describeTranslationCredentialSource(translation = {}) {
  const source = translation.effective_credential_source || translation.credential_source || {};
  const kind = String(source.kind || "").trim();
  const name = String(source.name || "").trim();
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
    return "missing credentials";
  }
  return kind || "unknown source";
}

function describeOcrCredentialSource(ocr = {}) {
  const source = ocr.effective_credential_source || {};
  const kind = String(source.kind || "").trim();
  const name = String(source.name || "").trim();
  if (kind === "stored" && name === "openai_api_key_fallback") {
    return "stored OpenAI translation key fallback";
  }
  if (kind === "stored") {
    return "stored OCR key";
  }
  if (kind === "env") {
    return name ? `env ${name}` : "environment variable";
  }
  if (kind === "missing") {
    return "missing credentials";
  }
  return kind || "unknown source";
}

function describeNativeHostState(nativeHost = {}) {
  if (nativeHost.ready === true) {
    return "ready";
  }
  if (nativeHost.repairable === true) {
    return "repairable from this browser runtime";
  }
  return "not repairable from this browser runtime";
}

export function renderCredentialRecoveryStateInto(nodes, providerState = {}) {
  if (!nodes) {
    return undefined;
  }

  const translation = providerState.translation || {};
  if (nodes.translation) {
    const storedState = translation.stored_credential_configured ? "yes" : "no";
    const fallbackState = translation.ocr_fallback_configured ? "available" : "not available";
    nodes.translation.textContent = [
      `Stored translation key: ${storedState}.`,
      `Stored OCR fallback: ${fallbackState}.`,
      `Effective source: ${describeTranslationCredentialSource(translation)}.`,
      "The browser never shows the stored key value.",
    ].join(" ");
  }

  const ocr = providerState.ocr || {};
  if (nodes.ocr) {
    const storedState = ocr.stored_credential_configured ? "yes" : "no";
    const fallbackState = ocr.translation_fallback_configured ? "available" : "not available";
    nodes.ocr.textContent = [
      `Stored OCR key: ${storedState}.`,
      `OpenAI translation fallback: ${fallbackState}.`,
      `Effective source: ${describeOcrCredentialSource(ocr)}.`,
      "The browser never shows the stored key value.",
    ].join(" ");
  }

  const nativeHost = providerState.native_host || {};
  if (nodes.nativeHost) {
    const wrapperTarget = String(nativeHost.wrapper_target_python || "").trim();
    nodes.nativeHost.textContent = [
      `Native host is ${describeNativeHostState(nativeHost)}.`,
      `Self-test: ${nativeHost.self_test_status || "not run"}.`,
      wrapperTarget ? `Wrapper target: ${wrapperTarget}.` : "",
      nativeHost.message ? nativeHost.message : "",
    ].filter(Boolean).join(" ");
  }

  const word = providerState.word_pdf_export || {};
  if (nodes.word) {
    const launchPreflight = word.launch_preflight || word.preflight || {};
    const exportCanary = word.export_canary || {};
    const lastCheckedAt = String(word.last_checked_at || "").trim();
    nodes.word.textContent = [
      `Launch preflight: ${launchPreflight.ok === true ? "passed" : launchPreflight.ok === false ? "failed" : "not run"}.`,
      `Export canary: ${exportCanary.ok === true ? "passed" : exportCanary.ok === false ? "failed" : "not run"}.`,
      `Finalization ready: ${word.finalization_ready === true ? "yes" : "no"}.`,
      lastCheckedAt ? `Checked at: ${lastCheckedAt}.` : "",
      word.used_cache === true ? "Current view reused a cached readiness result." : "Current view is showing a fresh readiness result or no cached result.",
      word.message ? String(word.message).trim() : "",
    ].filter(Boolean).join(" ");
  }

  return nodes;
}

function appendRunDirMeta(container, item = {}) {
  const meta = document.createElement("div");
  meta.className = "history-meta";
  for (const bit of [
    item.modified_at_iso || "",
    item.has_run_summary ? "summary" : "",
    item.has_run_state ? "state" : "",
    item.has_calibration_report ? "calibration" : "",
  ]) {
    if (bit) {
      meta.appendChild(createTextElement("small", bit));
    }
  }
  container.appendChild(meta);
  return meta;
}

export function renderLatestRunDirsInto(
  container,
  items = [],
  { onUseForReport, onAddToBuilder } = {},
) {
  if (!container) {
    return undefined;
  }
  const runDirs = Array.isArray(items) ? items : [];
  clearNode(container);
  if (!runDirs.length) {
    container.appendChild(createEmptyState("No recent run folders are available yet."));
    return container;
  }
  for (const item of runDirs) {
    const article = document.createElement("article");
    article.className = "history-item";

    const left = document.createElement("div");
    left.appendChild(createTextElement("strong", item?.name || "run"));
    left.appendChild(createTextElement("p", item?.run_dir || "", "word-break"));
    appendRunDirMeta(left, item || {});

    const actions = document.createElement("div");
    actions.className = "panel-actions";
    const useForReport = document.createElement("button");
    useForReport.type = "button";
    useForReport.textContent = "Use for run report";
    useForReport.addEventListener("click", () => onUseForReport?.(item));
    const addToBuilder = document.createElement("button");
    addToBuilder.type = "button";
    addToBuilder.textContent = "Add to builder";
    addToBuilder.addEventListener("click", () => onAddToBuilder?.(item));
    actions.appendChild(useForReport);
    actions.appendChild(addToBuilder);

    article.appendChild(left);
    article.appendChild(actions);
    container.appendChild(article);
  }
  return container;
}

export function renderPowerToolsFieldValueInto(field, value = "") {
  if (!field) {
    return undefined;
  }
  field.value = value ?? "";
  return field;
}

export function renderPowerToolsCheckboxInto(checkbox, value = false) {
  if (!checkbox) {
    return undefined;
  }
  checkbox.checked = Boolean(value);
  return checkbox;
}

function qs(id) {
  return document.getElementById(id);
}

export function setDiagnostics(slot, value, { hint = "", open = false } = {}) {
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

export function setPanelStatus(slot, tone, message) {
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
