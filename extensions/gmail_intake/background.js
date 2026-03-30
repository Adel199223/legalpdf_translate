const DEFAULT_BRIDGE_PORT = 8765;
const NATIVE_FOCUS_HOST = "com.legalpdf.gmail_focus";
const COLD_START_TAB_WAIT_MS = 2200;
const COLD_START_TAB_POLL_MS = 150;
const WORKSPACE_READY_WAIT_MS = 3200;
const COLD_START_WORKSPACE_READY_WAIT_MS = 5200;
const WORKSPACE_READY_POLL_MS = 140;
const LAUNCH_READINESS_WAIT_MS = 35000;
const HANDOFF_LOCK_MAX_AGE_MS = (
  LAUNCH_READINESS_WAIT_MS
  + COLD_START_TAB_WAIT_MS
  + COLD_START_WORKSPACE_READY_WAIT_MS
  + WORKSPACE_READY_POLL_MS
);
const DEFAULT_BROWSER_APP_URL = "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake";
const WORKSPACE_PENDING_STATUSES = new Set(["warming", "delayed"]);
const BRIDGE_INTEGRITY_FAILURE_REASONS = new Set([
  "bridge_browser_mismatch",
  "split_brain_browser_owner",
]);
const EXTENSION_PROVENANCE_DRIFT_REASONS = new Set([
  "extension_source_drift",
]);
const IS_EXTENSION_TEST = Boolean(globalThis && globalThis.__LEGALPDF_TEST__ === true);
const CLIENT_HYDRATION_WAIT_MS = IS_EXTENSION_TEST ? 40 : 2600;
const CLIENT_HYDRATION_RELOAD_WAIT_MS = IS_EXTENSION_TEST ? 60 : 3600;
const CLIENT_HYDRATION_POLL_MS = IS_EXTENSION_TEST ? 1 : 140;

const handoffInFlight = new Map();
let handoffSequence = 0;

function normalizePort(value) {
  const parsed = Number.parseInt(String(value ?? DEFAULT_BRIDGE_PORT), 10);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    return DEFAULT_BRIDGE_PORT;
  }
  return parsed;
}

function normalizeToken(value) {
  return String(value ?? "").trim();
}

function normalizeUrl(value) {
  return String(value ?? "").trim();
}

function buildBridgeEndpoint(config) {
  return `http://127.0.0.1:${normalizePort(config && config.bridgePort)}/gmail-intake`;
}

function sleep(ms) {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms));
}

async function getStoredBridgeConfig() {
  const stored = await chrome.storage.local.get(["bridgePort", "bridgeToken"]);
  return {
    bridgePort: normalizePort(stored.bridgePort),
    bridgeToken: normalizeToken(stored.bridgeToken),
  };
}

async function setStoredBridgeConfig(config) {
  const bridgeToken = normalizeToken(config && config.bridgeToken);
  if (bridgeToken === "") {
    return;
  }
  await chrome.storage.local.set({
    bridgePort: normalizePort(config && config.bridgePort),
    bridgeToken,
  });
}

function buildHandoffKey(tabId, context) {
  const tabPart = Number.isInteger(tabId) ? String(tabId) : "tab";
  const messageId = normalizeToken(context && context.message_id);
  const threadId = normalizeToken(context && context.thread_id);
  return `${tabPart}:${messageId || threadId || "unknown"}`;
}

function claimHandoffLock(tabId, context) {
  const key = buildHandoffKey(tabId, context);
  const existing = handoffInFlight.get(key);
  const now = Date.now();
  if (existing && now - existing.startedAt <= HANDOFF_LOCK_MAX_AGE_MS) {
    return {
      ok: false,
      key,
      staleRecovered: false,
    };
  }
  const staleRecovered = Boolean(existing);
  if (staleRecovered) {
    handoffInFlight.delete(key);
  }
  const token = `handoff-${now}-${++handoffSequence}`;
  handoffInFlight.set(key, {
    token,
    startedAt: now,
  });
  return {
    ok: true,
    key,
    token,
    staleRecovered,
  };
}

function releaseHandoffLock(lock) {
  if (!lock || typeof lock !== "object") {
    return;
  }
  const existing = handoffInFlight.get(lock.key);
  if (!existing || existing.token !== lock.token) {
    return;
  }
  handoffInFlight.delete(lock.key);
}

function isHandoffLockCurrent(lock) {
  if (!lock || typeof lock !== "object") {
    return false;
  }
  const existing = handoffInFlight.get(lock.key);
  return Boolean(existing && existing.token === lock.token);
}

async function sendTabMessage(tabId, payload) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, payload);
    return { ok: true, response };
  } catch (error) {
    return { ok: false, error };
  }
}

async function showFallbackBanner(tabId, kind, message) {
  if (!Number.isInteger(tabId)) {
    return false;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: (bannerKind, bannerMessage) => {
        const bannerId = "legalpdf-gmail-intake-banner";
        const existing = document.getElementById(bannerId);
        if (existing) {
          existing.remove();
        }

        const banner = document.createElement("div");
        banner.id = bannerId;
        banner.textContent = bannerMessage;
        banner.style.position = "fixed";
        banner.style.top = "20px";
        banner.style.right = "20px";
        banner.style.zIndex = "2147483647";
        banner.style.maxWidth = "360px";
        banner.style.padding = "12px 16px";
        banner.style.borderRadius = "12px";
        banner.style.boxShadow = "0 10px 32px rgba(0, 0, 0, 0.25)";
        banner.style.font = "500 13px/1.4 Arial, sans-serif";
        banner.style.color = "#101828";
        if (bannerKind === "success") {
          banner.style.background = "#D1FADF";
          banner.style.border = "1px solid #6CE9A6";
        } else if (bannerKind === "info") {
          banner.style.background = "#D9F0FF";
          banner.style.border = "1px solid #84CAFF";
        } else {
          banner.style.background = "#FEE4E2";
          banner.style.border = "1px solid #FDA29B";
        }
        document.documentElement.appendChild(banner);
        window.setTimeout(() => banner.remove(), 4500);
      },
      args: [kind === "success" ? "success" : kind === "info" ? "info" : "error", message],
    });
    return true;
  } catch (_error) {
    return false;
  }
}

async function notifyTab(tabId, kind, message) {
  if (!Number.isInteger(tabId)) {
    return false;
  }

  const result = await sendTabMessage(tabId, {
    type: "gmail-intake-status",
    kind,
    message,
  });
  if (result.ok) {
    return true;
  }
  return await showFallbackBanner(tabId, kind, message);
}

async function ensureContentScriptReady(tabId) {
  const initial = await sendTabMessage(tabId, { type: "gmail-intake-ping" });
  if (initial.ok && initial.response && initial.response.ok === true) {
    return true;
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"],
    });
  } catch (_error) {
    return false;
  }

  const retry = await sendTabMessage(tabId, { type: "gmail-intake-ping" });
  return retry.ok && retry.response && retry.response.ok === true;
}

async function requestNativePreparation({ requestFocus = true, includeToken = true } = {}) {
  try {
    const response = await chrome.runtime.sendNativeMessage(NATIVE_FOCUS_HOST, {
      action: "prepare_gmail_intake",
      requestFocus,
      includeToken,
    });
    return { ok: true, response };
  } catch (error) {
    return { ok: false, error };
  }
}

function buildPrepareFailureMessage(response) {
  const reason = normalizeToken(response && response.reason);
  const bridgeProbeReason = normalizeToken(response?.bridge_probe_reason);
  const bridgeProbeTimedOut = response?.bridge_probe_timed_out === true;
  switch (reason) {
    case "bridge_disabled":
      return "Gmail bridge is disabled in LegalPDF Translate.";
    case "bridge_token_missing":
      return "Gmail bridge is not configured in LegalPDF Translate.";
    case "invalid_bridge_port":
      return "Gmail bridge port is invalid in LegalPDF Translate.";
    case "runtime_metadata_missing":
    case "bridge_not_running":
      return "LegalPDF Translate is not running the Gmail bridge right now.";
    case "bridge_owner_stale":
      return "LegalPDF Translate found stale Gmail bridge ownership metadata and needs to reclaim the bridge.";
    case "runtime_metadata_invalid":
      return "LegalPDF Translate has invalid Gmail bridge runtime metadata.";
    case "bridge_port_mismatch":
      return "LegalPDF Translate is listening on a different Gmail bridge port.";
    case "bridge_port_owner_unknown":
      return "LegalPDF Translate could not verify the Gmail bridge listener.";
    case "bridge_port_owner_mismatch":
      return "Another process is using the Gmail bridge port configured for LegalPDF Translate.";
    case "bridge_browser_mismatch":
      if (bridgeProbeTimedOut || bridgeProbeReason === "browser_probe_timeout") {
        return "LegalPDF Translate found a browser-owned Gmail bridge, but the browser app did not answer the live-runtime proof in time.";
      }
      return "LegalPDF Translate found a browser-owned Gmail bridge, but the visible browser workspace could not prove it owns the same live runtime.";
    case "split_brain_browser_owner":
      return "The Gmail bridge is owned by a different browser-app process than the visible browser workspace.";
    case "window_not_found":
      return "LegalPDF Translate is running without a visible main window.";
    case "launch_target_missing":
    case "launch_helper_missing":
    case "launch_python_missing":
      return "LegalPDF Translate auto-launch is not available from this checkout.";
    case "launch_runtime_broken":
      return "LegalPDF Translate found this checkout, but its local runtime is broken and could not be started safely.";
    case "launch_command_failed":
      return "LegalPDF Translate could not be started automatically.";
    case "launch_in_progress":
      return "LegalPDF Translate is already starting the browser app for this Gmail handoff.";
    case "launch_timeout":
      return "LegalPDF Translate was started, but the Gmail bridge did not become ready in time.";
    case "unsupported_platform":
      return "Foreground activation is only supported on Windows for this extension.";
    default:
      return "Gmail bridge is not ready in LegalPDF Translate.";
  }
}

function isLaunchStillInProgress(response) {
  return Boolean(response && response.launch_in_progress === true);
}

function buildLaunchInProgressMessage(response) {
  const remainingMs = Number.parseInt(String(response?.launch_lock_ttl_ms ?? 0), 10);
  const waitSeconds = Math.max(
    1,
    Math.ceil((Number.isFinite(remainingMs) && remainingMs > 0 ? remainingMs : LAUNCH_READINESS_WAIT_MS) / 1000),
  );
  return (
    "LegalPDF Translate is already starting the browser app for this Gmail handoff. "
    + `Please wait up to ${waitSeconds}s before clicking again; it will reuse the same launch instead of opening another window.`
  );
}

function buildNativeHostAutoLaunchRepairMessage() {
  return (
    "LegalPDF Translate native host is unavailable, so the extension cannot open the app automatically right now. "
    + "Open LegalPDF Translate once to repair the focus helper, then click the extension again."
  );
}

function extractExtensionProvenanceState(response) {
  return {
    syncStatus: normalizeToken(response?.extension_sync_status),
    syncApplied: response?.extension_sync_applied === true,
    reloadRequired: response?.extension_reload_required === true,
    provenanceReason: normalizeToken(response?.extension_provenance_reason),
    syncMessage: normalizeToken(response?.extension_sync_message),
  };
}

function hasExtensionProvenanceIssue(response) {
  const state = extractExtensionProvenanceState(response);
  return (
    state.reloadRequired
    || EXTENSION_PROVENANCE_DRIFT_REASONS.has(state.provenanceReason)
    || state.syncStatus === "sync_failed"
  );
}

function buildExtensionProvenanceNotice(response) {
  const state = extractExtensionProvenanceState(response);
  if (state.reloadRequired) {
    return {
      kind: "info",
      message: (
        "LegalPDF Translate updated the loaded Gmail extension files, but this running extension "
        + "instance is still using stale code. Reload the extension once, then reload Gmail if "
        + "needed, and click the extension again."
      ),
    };
  }
  if (state.syncStatus === "sync_failed") {
    const detail = state.syncMessage !== ""
      ? ` LegalPDF Translate could not sync the loaded extension copy automatically (${state.syncMessage}).`
      : " LegalPDF Translate could not sync the loaded extension copy automatically.";
    return {
      kind: "error",
      message: (
        "This Gmail extension copy is stale for the current LegalPDF Translate app."
        + detail
        + " Reload the extension once after the sync issue is fixed, then reload Gmail if needed, "
        + "and click the extension again."
      ),
    };
  }
  if (EXTENSION_PROVENANCE_DRIFT_REASONS.has(state.provenanceReason)) {
    return {
      kind: "error",
      message: (
        "This Gmail extension copy is stale for the current LegalPDF Translate app. Reload the "
        + "extension once, then reload Gmail if needed, and click the extension again."
      ),
    };
  }
  return null;
}

function isBridgeIntegrityFailureReason(reason) {
  return BRIDGE_INTEGRITY_FAILURE_REASONS.has(normalizeToken(reason));
}

function extractBridgeIntegrityState(payload) {
  const diagnosticsReason = normalizeToken(payload?.diagnostics?.gmail_bridge_sync?.reason);
  const capabilityFlagsBridge = payload?.capability_flags?.gmail_bridge;
  const capabilityReason = normalizeToken(capabilityFlagsBridge?.reason);
  const prepareResponse = (
    capabilityFlagsBridge?.current_mode?.prepare_response
    || payload?.normalized_payload?.extension_lab?.prepare_response
    || {}
  );
  return {
    reason: diagnosticsReason || capabilityReason,
    bridgeProbeReason: normalizeToken(prepareResponse?.bridge_probe_reason),
    bridgeProbeDetail: normalizeToken(prepareResponse?.bridge_probe_detail),
    bridgeProbeTimedOut: prepareResponse?.bridge_probe_timed_out === true,
  };
}

function buildBridgeIntegrityFailureMessage(source) {
  const reason = normalizeToken(source?.integrityFailureReason ?? source?.reason ?? source);
  const bridgeProbeReason = normalizeToken(
    source?.integrityFailureProbeReason ?? source?.bridge_probe_reason,
  );
  const bridgeProbeTimedOut = Boolean(
    source?.integrityFailureTimedOut ?? source?.bridge_probe_timed_out,
  );
  const baseMessage = buildPrepareFailureMessage({
    reason,
    bridge_probe_reason: bridgeProbeReason,
    bridge_probe_timed_out: bridgeProbeTimedOut,
  });
  if (!isBridgeIntegrityFailureReason(reason)) {
    return baseMessage;
  }
  if (bridgeProbeTimedOut || bridgeProbeReason === "browser_probe_timeout") {
    return `${baseMessage} Please wait a few seconds and click the extension again. If it keeps happening, restart the browser app.`;
  }
  return `${baseMessage} Close stale LegalPDF windows or restart the browser app, then click the extension again.`;
}

function messageContextMatches(expectedContext, candidateContext) {
  const expectedMessageId = normalizeToken(expectedContext && expectedContext.message_id);
  const expectedThreadId = normalizeToken(expectedContext && expectedContext.thread_id);
  const candidateMessageId = normalizeToken(
    candidateContext && (candidateContext.message_id ?? candidateContext.messageId),
  );
  const candidateThreadId = normalizeToken(
    candidateContext && (candidateContext.thread_id ?? candidateContext.threadId),
  );
  const comparisons = [];
  if (expectedMessageId !== "" && candidateMessageId !== "") {
    comparisons.push(expectedMessageId === candidateMessageId);
  }
  if (expectedThreadId !== "" && candidateThreadId !== "") {
    comparisons.push(expectedThreadId === candidateThreadId);
  }
  return comparisons.length > 0 && comparisons.every(Boolean);
}

function buildFocusNotice(nativeResponse, degradedMode) {
  if (degradedMode) {
    return "App focus helper unavailable; if the app did not come forward, check the taskbar.";
  }

  if (!nativeResponse || typeof nativeResponse !== "object") {
    return "App focus helper returned an invalid response; if the app did not come forward, check the taskbar.";
  }

  if (nativeResponse.ui_owner === "browser_app") {
    return "";
  }

  if (nativeResponse.ok === true && nativeResponse.focused === true) {
    return "";
  }
  if (nativeResponse.ok === true && nativeResponse.flashed === true) {
    return nativeResponse.launched === true
      ? "The app was started and flashed in the taskbar."
      : "The app was flashed in the taskbar.";
  }
  return `App focus helper could not foreground the app (${buildPrepareFailureMessage(nativeResponse)}).`;
}

function urlsMatchForFocus(candidateUrl, targetUrl) {
  try {
    const candidate = new URL(candidateUrl);
    const target = new URL(targetUrl);
    return candidate.origin === target.origin
      && candidate.pathname === target.pathname
      && candidate.search === target.search
      && candidate.hash === target.hash;
  } catch (_error) {
    return false;
  }
}

async function openOrFocusBrowserApp(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return false;
  }
  let url;
  try {
    url = new URL(targetUrl);
  } catch (_error) {
    return false;
  }
  const candidates = await chrome.tabs.query({ url: `${url.origin}/*` });
  const exactMatch = candidates.find((tab) => urlsMatchForFocus(tab.url, targetUrl));
  if (exactMatch && Number.isInteger(exactMatch.id)) {
    await chrome.tabs.update(exactMatch.id, { active: true });
    if (Number.isInteger(exactMatch.windowId)) {
      await chrome.windows.update(exactMatch.windowId, { focused: true });
    }
    return true;
  }
  const existing = candidates.find((tab) => Number.isInteger(tab.id));
  if (existing && Number.isInteger(existing.id)) {
    await chrome.tabs.update(existing.id, { active: true, url: targetUrl });
    if (Number.isInteger(existing.windowId)) {
      await chrome.windows.update(existing.windowId, { focused: true });
    }
    return true;
  }
  const created = await chrome.tabs.create({ url: targetUrl, active: true });
  if (created && Number.isInteger(created.windowId)) {
    await chrome.windows.update(created.windowId, { focused: true });
  }
  return true;
}

async function focusExistingBrowserAppWindow(browserUrl = DEFAULT_BROWSER_APP_URL) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return false;
  }
  let url;
  try {
    url = new URL(targetUrl);
  } catch (_error) {
    return false;
  }
  const candidates = await chrome.tabs.query({ url: `${url.origin}/*` });
  const exactMatch = candidates.find((tab) => urlsMatchForFocus(tab.url, targetUrl));
  if (exactMatch && Number.isInteger(exactMatch.id)) {
    await chrome.tabs.update(exactMatch.id, { active: true });
    if (Number.isInteger(exactMatch.windowId)) {
      await chrome.windows.update(exactMatch.windowId, { focused: true });
    }
    return true;
  }
  const existing = candidates.find((tab) => Number.isInteger(tab.id));
  if (existing && Number.isInteger(existing.id)) {
    await chrome.tabs.update(existing.id, { active: true });
    if (Number.isInteger(existing.windowId)) {
      await chrome.windows.update(existing.windowId, { focused: true });
    }
    return true;
  }
  return false;
}

async function waitForLaunchedBrowserAppTab(browserUrl, timeoutMs = COLD_START_TAB_WAIT_MS) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return false;
  }
  let origin;
  try {
    origin = new URL(targetUrl).origin;
  } catch (_error) {
    return false;
  }
  const deadline = Date.now() + Math.max(0, Number(timeoutMs || 0));
  while (Date.now() <= deadline) {
    const candidates = await chrome.tabs.query({ url: `${origin}/*` });
    const exactMatch = candidates.find((tab) => urlsMatchForFocus(tab.url, targetUrl));
    if (exactMatch && Number.isInteger(exactMatch.id)) {
      await chrome.tabs.update(exactMatch.id, { active: true });
      if (Number.isInteger(exactMatch.windowId)) {
        await chrome.windows.update(exactMatch.windowId, { focused: true });
      }
      return true;
    }
    await sleep(COLD_START_TAB_POLL_MS);
  }
  return false;
}

function buildBrowserWorkspaceBootstrapUrl(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return "";
  }
  try {
    const parsed = new URL(targetUrl);
    const runtimeMode = normalizeToken(parsed.searchParams.get("mode")) || "live";
    const workspaceId = normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1";
    return `${parsed.origin}/api/gmail/bootstrap?mode=${encodeURIComponent(runtimeMode)}&workspace=${encodeURIComponent(workspaceId)}`;
  } catch (_error) {
    return "";
  }
}

function buildBrowserAppBootstrapUrl(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return "";
  }
  try {
    const parsed = new URL(targetUrl);
    const runtimeMode = normalizeToken(parsed.searchParams.get("mode")) || "live";
    const workspaceId = normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1";
    return `${parsed.origin}/api/bootstrap/shell?mode=${encodeURIComponent(runtimeMode)}&workspace=${encodeURIComponent(workspaceId)}`;
  } catch (_error) {
    return "";
  }
}

function defaultBrowserViewForWorkspace(workspaceId) {
  return workspaceId === "gmail-intake" ? "gmail-intake" : "new-job";
}

function parseBrowserClientExpectation(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return {
      runtimeMode: "live",
      workspaceId: "workspace-1",
      activeView: "new-job",
      assetVersion: "",
    };
  }
  try {
    const parsed = new URL(targetUrl);
    const workspaceId = normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1";
    return {
      runtimeMode: normalizeToken(parsed.searchParams.get("mode")) || "live",
      workspaceId,
      activeView: normalizeToken(parsed.hash.replace(/^#/, "")) || defaultBrowserViewForWorkspace(workspaceId),
      assetVersion: "",
    };
  } catch (_error) {
    return {
      runtimeMode: "live",
      workspaceId: "workspace-1",
      activeView: "new-job",
      assetVersion: "",
    };
  }
}

async function resolveBrowserAppTab(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return null;
  }
  let url;
  try {
    url = new URL(targetUrl);
  } catch (_error) {
    return null;
  }
  const candidates = await chrome.tabs.query({ url: `${url.origin}/*` });
  const exactMatch = candidates.find((tab) => urlsMatchForFocus(tab.url, targetUrl));
  if (exactMatch && Number.isInteger(exactMatch.id)) {
    return exactMatch;
  }
  const existing = candidates.find((tab) => Number.isInteger(tab.id));
  return existing || null;
}

async function readBrowserClientHydrationState(tabId) {
  if (!Number.isInteger(tabId)) {
    return {
      available: false,
      status: "",
      runtimeMode: "",
      workspaceId: "",
      activeView: "",
      gmailHandoffState: "",
      buildSha: "",
      assetVersion: "",
      bootstrappedAt: "",
      url: "",
    };
  }
  try {
    const execution = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        const marker = window.LEGALPDF_BROWSER_CLIENT_READY || null;
        const dataset = document.body?.dataset || {};
        return {
          marker,
          dataset: {
            clientReady: dataset.clientReady || "",
            clientWorkspace: dataset.clientWorkspace || "",
            clientRuntimeMode: dataset.clientRuntimeMode || "",
            clientActiveView: dataset.clientActiveView || "",
            clientBuildSha: dataset.clientBuildSha || "",
            clientAssetVersion: dataset.clientAssetVersion || "",
          },
          href: window.location.href,
        };
      },
    });
    const result = execution?.[0]?.result || {};
    const marker = result.marker || {};
    const dataset = result.dataset || {};
    const status = normalizeToken(marker.status || dataset.clientReady).toLowerCase();
    return {
      available: true,
      status,
      runtimeMode: normalizeToken(marker.runtimeMode || dataset.clientRuntimeMode).toLowerCase(),
      workspaceId: normalizeToken(marker.workspaceId || dataset.clientWorkspace),
      activeView: normalizeToken(marker.activeView || dataset.clientActiveView),
      gmailHandoffState: normalizeToken(marker.gmailHandoffState).toLowerCase(),
      buildSha: normalizeToken(marker.buildSha || dataset.clientBuildSha),
      assetVersion: normalizeToken(marker.assetVersion || dataset.clientAssetVersion),
      bootstrappedAt: normalizeToken(marker.bootstrappedAt),
      reason: normalizeToken(marker.reason),
      message: normalizeToken(marker.message),
      url: normalizeUrl(result.href),
    };
  } catch (_error) {
    return {
      available: false,
      status: "",
      runtimeMode: "",
      workspaceId: "",
      activeView: "",
      gmailHandoffState: "",
      buildSha: "",
      assetVersion: "",
      bootstrappedAt: "",
      url: "",
    };
  }
}

function doesBrowserClientAssetVersionMatch(clientState, expectedAssetVersion) {
  const expected = normalizeToken(expectedAssetVersion);
  if (expected === "") {
    return true;
  }
  return normalizeToken(clientState?.assetVersion) === expected;
}

function isBrowserClientReadyForExpectation(clientState, expected) {
  return (
    clientState.available === true
    && clientState.status === "ready"
    && clientState.runtimeMode === expected.runtimeMode
    && clientState.workspaceId === expected.workspaceId
    && clientState.activeView === expected.activeView
    && doesBrowserClientAssetVersionMatch(clientState, expected.assetVersion)
  );
}

async function waitForBrowserClientHydration(
  browserUrl,
  timeoutMs = CLIENT_HYDRATION_WAIT_MS,
  expectedAssetVersion = "",
) {
  const expectation = {
    ...parseBrowserClientExpectation(browserUrl),
    assetVersion: normalizeToken(expectedAssetVersion),
  };
  const deadline = Date.now() + Math.max(0, Number(timeoutMs || 0));
  let lastState = {
    available: false,
    status: "",
    runtimeMode: "",
    workspaceId: "",
    activeView: "",
    gmailHandoffState: "",
    buildSha: "",
    assetVersion: "",
    bootstrappedAt: "",
    url: "",
  };
  while (Date.now() <= deadline) {
    const tab = await resolveBrowserAppTab(browserUrl);
    if (tab && Number.isInteger(tab.id)) {
      const clientState = await readBrowserClientHydrationState(tab.id);
      lastState = {
        ...clientState,
        tabId: tab.id,
      };
      if (isBrowserClientReadyForExpectation(lastState, expectation)) {
        return {
          ready: true,
          tabId: tab.id,
          expected: expectation,
          clientState: lastState,
        };
      }
      if (lastState.status === "client_boot_failed") {
        return {
          ready: false,
          tabId: tab.id,
          expected: expectation,
          clientState: lastState,
        };
      }
    }
    await sleep(CLIENT_HYDRATION_POLL_MS);
  }
  return {
    ready: false,
    tabId: Number.isInteger(lastState.tabId) ? lastState.tabId : null,
    expected: expectation,
    clientState: lastState,
  };
}

async function reloadBrowserAppTab(browserUrl) {
  const tab = await resolveBrowserAppTab(browserUrl);
  if (!tab || !Number.isInteger(tab.id)) {
    return {
      ok: false,
      tabId: null,
    };
  }
  await chrome.tabs.reload(tab.id, { bypassCache: true });
  return {
    ok: true,
    tabId: tab.id,
  };
}

async function waitForBrowserWorkspaceState(
  browserUrl,
  expectedContext,
  timeoutMs = WORKSPACE_READY_WAIT_MS,
) {
  const workspaceEndpoint = buildBrowserWorkspaceBootstrapUrl(browserUrl);
  const appBootstrapEndpoint = buildBrowserAppBootstrapUrl(browserUrl);
  if (workspaceEndpoint === "" && appBootstrapEndpoint === "") {
    return {
      ready: false,
      pending: false,
      loaded: false,
      appBootstrapReady: false,
      workspaceRouteReachable: false,
      assetVersion: "",
    };
  }
  const deadline = Date.now() + Math.max(0, Number(timeoutMs || 0));
  let appBootstrapReady = false;
  let workspaceRouteReachable = false;
  let assetVersion = "";
  let integrityFailureReason = "";
  let integrityFailureProbeReason = "";
  let integrityFailureProbeDetail = "";
  let integrityFailureTimedOut = false;
  while (Date.now() <= deadline) {
    if (appBootstrapEndpoint !== "" && !appBootstrapReady) {
      try {
        const appBootstrapResponse = await fetch(appBootstrapEndpoint, { cache: "no-store" });
        if (appBootstrapResponse.ok) {
          appBootstrapReady = true;
          let appBootstrapPayload = {};
          try {
            appBootstrapPayload = await appBootstrapResponse.json();
          } catch (_error) {
            appBootstrapPayload = {};
          }
          const appIntegrity = extractBridgeIntegrityState(appBootstrapPayload);
          assetVersion = normalizeToken(
            appBootstrapPayload?.normalized_payload?.shell?.asset_version
            || appBootstrapPayload?.normalized_payload?.runtime?.asset_version,
          );
          const appIntegrityReason = appIntegrity.reason;
          if (isBridgeIntegrityFailureReason(appIntegrityReason)) {
            return {
              ready: false,
              pending: false,
              loaded: false,
              loadFailed: false,
              loadFailureMessage: "",
              warming: false,
              pendingStatus: "",
              integrityFailureReason: appIntegrityReason,
              integrityFailureProbeReason: appIntegrity.bridgeProbeReason,
              integrityFailureProbeDetail: appIntegrity.bridgeProbeDetail,
              integrityFailureTimedOut: appIntegrity.bridgeProbeTimedOut,
              appBootstrapReady,
              workspaceRouteReachable,
              assetVersion,
            };
          }
        }
      } catch (_error) {
        // The browser shell can still be warming; keep polling briefly.
      }
    }
    try {
      const response = await fetch(workspaceEndpoint, { cache: "no-store" });
      if (response.ok) {
        workspaceRouteReachable = true;
        let payload = {};
        try {
          payload = await response.json();
        } catch (_error) {
          payload = {};
        }
        const gmailPayload = payload?.normalized_payload || {};
        const integrityState = extractBridgeIntegrityState(payload);
        const integrityReason = integrityState.reason;
        const pendingContext = gmailPayload.pending_intake_context || {};
        const pendingStatus = normalizeToken(gmailPayload.pending_status).toLowerCase();
        const pendingReviewOpen = gmailPayload.pending_review_open === true;
        const pending = (
          messageContextMatches(expectedContext, pendingContext)
          && pendingReviewOpen
          && WORKSPACE_PENDING_STATUSES.has(pendingStatus)
        );
        const loadResult = gmailPayload.load_result || {};
        const loadMatches = messageContextMatches(expectedContext, loadResult.intake_context || {});
        const loaded = loadMatches && loadResult.ok === true;
        const loadFailed = loadMatches && loadResult.ok === false;
        const loadFailureMessage = (
          loadFailed
            ? normalizeToken(loadResult.status_message) || "LegalPDF Translate could not load the exact Gmail message."
            : ""
        );
        const warming = pending;
        if (isBridgeIntegrityFailureReason(integrityReason)) {
          return {
            ready: false,
            pending,
            loaded,
            loadFailed,
            loadFailureMessage,
            warming: false,
            pendingStatus,
            integrityFailureReason: integrityReason,
            integrityFailureProbeReason: integrityState.bridgeProbeReason,
            integrityFailureProbeDetail: integrityState.bridgeProbeDetail,
            integrityFailureTimedOut: integrityState.bridgeProbeTimedOut,
            appBootstrapReady,
            workspaceRouteReachable,
            assetVersion,
          };
        }
        if (loaded) {
          return {
            ready: true,
            pending,
            loaded,
            loadFailed,
            loadFailureMessage,
            warming,
            pendingStatus,
            integrityFailureReason,
            integrityFailureProbeReason: integrityState.bridgeProbeReason,
            integrityFailureProbeDetail: integrityState.bridgeProbeDetail,
            integrityFailureTimedOut: integrityState.bridgeProbeTimedOut,
            appBootstrapReady,
            workspaceRouteReachable,
            assetVersion,
          };
        }
        if (warming) {
          return {
            ready: true,
            pending,
            loaded,
            loadFailed,
            loadFailureMessage,
            warming,
            pendingStatus,
            integrityFailureReason,
            integrityFailureProbeReason: integrityState.bridgeProbeReason,
            integrityFailureProbeDetail: integrityState.bridgeProbeDetail,
            integrityFailureTimedOut: integrityState.bridgeProbeTimedOut,
            appBootstrapReady,
            workspaceRouteReachable,
            assetVersion,
          };
        }
        if (loadFailed) {
          return {
            ready: false,
            pending,
            loaded,
            loadFailed,
            loadFailureMessage,
            warming: false,
            pendingStatus,
            integrityFailureReason,
            integrityFailureProbeReason: integrityState.bridgeProbeReason,
            integrityFailureProbeDetail: integrityState.bridgeProbeDetail,
            integrityFailureTimedOut: integrityState.bridgeProbeTimedOut,
            appBootstrapReady,
            workspaceRouteReachable,
            assetVersion,
          };
        }
      }
    } catch (_error) {
      // The browser app can still be warming the route; keep polling briefly.
    }
    await sleep(WORKSPACE_READY_POLL_MS);
  }
  return {
    ready: false,
    pending: false,
    loaded: false,
    loadFailed: false,
    loadFailureMessage: "",
    warming: false,
    pendingStatus: "",
    integrityFailureReason,
    integrityFailureProbeReason,
    integrityFailureProbeDetail,
    integrityFailureTimedOut,
    appBootstrapReady,
    workspaceRouteReachable,
    assetVersion,
  };
}

function buildWorkspaceWarmupMessage({ baseMessage, focusNotice, resolvedBrowserOpen }) {
  const parts = [];
  if (baseMessage !== "") {
    parts.push(baseMessage);
  }
  parts.push("LegalPDF Translate received the Gmail handoff and is still loading the exact Gmail message.");
  parts.push("Please wait a few seconds, then click the extension again only if it stays stuck.");
  if (focusNotice !== "") {
    parts.push(focusNotice);
  } else if (!resolvedBrowserOpen) {
    parts.push("The browser app may still need manual focus.");
  }
  return parts.join(" ");
}

function buildWorkspaceNoHandoffMessage({ resolvedBrowserOpen, focusNotice }) {
  const parts = [];
  if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but no exact Gmail handoff reached the browser workspace.");
  } else {
    parts.push("LegalPDF Translate did not confirm an exact Gmail handoff in the browser workspace.");
  }
  parts.push("Please click the extension again.");
  if (focusNotice !== "") {
    parts.push(focusNotice);
  } else if (!resolvedBrowserOpen) {
    parts.push("The browser app may still need manual focus.");
  }
  return parts.join(" ");
}

function buildWorkspaceFailureMessage({ resolvedBrowserOpen, focusNotice }) {
  const parts = [];
  if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but the Gmail review surface did not become ready.");
    parts.push("Please focus the LegalPDF window and click the extension again.");
  } else {
    parts.push("LegalPDF Translate did not finish launching into the Gmail review surface.");
    parts.push("Please click the extension again.");
  }
  if (focusNotice !== "") {
    parts.push(focusNotice);
  } else if (!resolvedBrowserOpen) {
    parts.push("The browser app may still need manual focus.");
  }
  return parts.join(" ");
}

function buildClientShellNotHydratedMessage({ resolvedBrowserOpen, focusNotice, clientState }) {
  const parts = [];
  if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but the browser tab stayed on the plain shell instead of hydrating the Gmail review UI.");
  } else {
    parts.push("LegalPDF Translate could not confirm that the browser tab hydrated the Gmail review UI.");
  }
  parts.push("The extension reloaded the localhost tab once automatically, but the page still did not finish loading.");
  if (clientState?.status === "client_boot_failed" && clientState?.message) {
    parts.push(clientState.message);
  } else {
    parts.push("Refresh the LegalPDF tab once manually if it is still open. If this keeps happening, restart the browser app and click the extension again.");
  }
  if (focusNotice !== "") {
    parts.push(focusNotice);
  }
  return parts.join(" ");
}

function buildStaleBrowserAssetsMessage({
  resolvedBrowserOpen,
  focusNotice,
  clientState,
  expectedAssetVersion,
}) {
  const parts = [];
  if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but the browser tab is still running stale browser assets.");
  } else {
    parts.push("LegalPDF Translate could not confirm that the browser tab picked up the current browser assets.");
  }
  parts.push("The extension reloaded the localhost tab once automatically, but the tab still reported a different asset version than the live app expects.");
  if (expectedAssetVersion) {
    parts.push(`Expected asset version: ${expectedAssetVersion}.`);
  }
  if (clientState?.assetVersion) {
    parts.push(`Tab asset version: ${clientState.assetVersion}.`);
  }
  if (clientState?.message) {
    parts.push(clientState.message);
  } else {
    parts.push("Reload the LegalPDF tab once manually if it is still open. If this keeps happening, restart the browser app and click the extension again.");
  }
  if (focusNotice !== "") {
    parts.push(focusNotice);
  }
  return parts.join(" ");
}

async function resolveBridgeConfigForClick() {
  const nativePreparation = await requestNativePreparation();
  if (nativePreparation.ok) {
    const response = nativePreparation.response;
    const responseReason = normalizeToken(response && response.reason);
    const extensionProvenanceNotice = hasExtensionProvenanceIssue(response)
      ? buildExtensionProvenanceNotice(response)
      : null;
    const bridgePort = normalizePort(response && response.bridgePort);
    const bridgeToken = normalizeToken(response && response.bridgeToken);
    if (response && response.ok === true && bridgeToken !== "") {
      await setStoredBridgeConfig({ bridgePort, bridgeToken });
      if (extensionProvenanceNotice && !isBridgeIntegrityFailureReason(responseReason)) {
        return {
          ok: false,
          degradedMode: false,
          nativeResponse: response,
          messageKind: extensionProvenanceNotice.kind,
          message: extensionProvenanceNotice.message,
        };
      }
      return {
        ok: true,
        degradedMode: false,
        nativeResponse: response,
        config: { bridgePort, bridgeToken },
      };
    }
    if (isLaunchStillInProgress(response)) {
      return {
        ok: false,
        degradedMode: false,
        nativeResponse: response,
        launchInProgress: true,
        messageKind: "info",
        message: buildLaunchInProgressMessage(response),
      };
    }
    if (extensionProvenanceNotice && !isBridgeIntegrityFailureReason(responseReason)) {
      return {
        ok: false,
        degradedMode: false,
        nativeResponse: response,
        messageKind: extensionProvenanceNotice.kind,
        message: extensionProvenanceNotice.message,
      };
    }
    return {
      ok: false,
      degradedMode: false,
      nativeResponse: response,
      messageKind: "error",
      message: buildPrepareFailureMessage(response),
    };
  }

  const storedConfig = await getStoredBridgeConfig();
  if (storedConfig.bridgeToken !== "") {
    try {
      const probeResponse = await fetch(buildBridgeEndpoint(storedConfig), {
        method: "GET",
      });
      if (probeResponse && typeof probeResponse.status === "number") {
        return {
          ok: true,
          degradedMode: true,
          nativeResponse: null,
          config: storedConfig,
        };
      }
    } catch (_error) {
      // The native host is unavailable and the bridge is not already live.
    }
  }

  if (storedConfig.bridgeToken !== "") {
    return {
      ok: false,
      degradedMode: true,
      nativeResponse: null,
      messageKind: "error",
      message: buildNativeHostAutoLaunchRepairMessage(),
    };
  }

  return {
    ok: false,
    degradedMode: true,
    nativeResponse: null,
    messageKind: "error",
    message: "LegalPDF Translate native host is unavailable. Reload the extension or open the options page.",
  };
}

async function settleBrowserAppHandoff(browserUrl, browserAppOpened, waitForLaunchedTab) {
  let resolved = Boolean(browserAppOpened);
  const targetUrl = normalizeUrl(browserUrl);
  if (!resolved && waitForLaunchedTab && targetUrl !== "") {
    resolved = await waitForLaunchedBrowserAppTab(targetUrl);
  }
  if (!resolved && targetUrl !== "") {
    resolved = await focusExistingBrowserAppWindow(targetUrl);
  }
  return resolved;
}

async function postContext(
  tabId,
  context,
  config,
  nativeResponse,
  focusNotice,
  browserAppOpened = false,
  browserUrl = "",
  waitForLaunchedTab = false,
) {
  const endpoint = buildBridgeEndpoint(config);
  let response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${config.bridgeToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message_id: context.message_id,
        thread_id: context.thread_id,
        subject: context.subject,
        account_email: context.account_email ?? undefined,
      }),
    });
  } catch (_error) {
    await notifyTab(tabId, "error", `LegalPDF Translate is not listening on ${endpoint}.`);
    return { holdLock: false, outcome: "bridge_unreachable" };
  }

  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }

  if (!response.ok) {
    const message =
      typeof payload.message === "string" && payload.message.trim() !== ""
        ? payload.message.trim()
        : `LegalPDF Translate rejected the request (${response.status}).`;
    await notifyTab(tabId, "error", message);
    return { holdLock: false, outcome: "bridge_rejected" };
  }

  const resolvedBrowserOpen = await settleBrowserAppHandoff(browserUrl, browserAppOpened, waitForLaunchedTab);
  const workspaceState = await waitForBrowserWorkspaceState(
    browserUrl,
    context,
    waitForLaunchedTab ? COLD_START_WORKSPACE_READY_WAIT_MS : WORKSPACE_READY_WAIT_MS,
  );
  let clientHydrationState = null;
  let hydrationReloadAttempted = false;
  const baseMessage =
    typeof payload.message === "string" && payload.message.trim() !== ""
      ? payload.message.trim()
      : "Gmail intake accepted.";
  const suffix = [];
  if (focusNotice !== "") {
    suffix.push(focusNotice);
  }
  if (nativeResponse && nativeResponse.ui_owner === "browser_app" && !resolvedBrowserOpen) {
    suffix.push("The browser app may need manual focus.");
  }
  if (nativeResponse && nativeResponse.ui_owner === "browser_app") {
    if (isBridgeIntegrityFailureReason(workspaceState.integrityFailureReason)) {
      const parts = [buildBridgeIntegrityFailureMessage(workspaceState)];
      if (focusNotice !== "") {
        parts.push(focusNotice);
      }
      await notifyTab(tabId, "error", parts.join(" "));
      return { holdLock: false, outcome: "integrity_failure" };
    }
    if (workspaceState.loaded) {
      clientHydrationState = await waitForBrowserClientHydration(
        browserUrl,
        CLIENT_HYDRATION_WAIT_MS,
        workspaceState.assetVersion,
      );
      if (!clientHydrationState.ready && browserUrl !== "") {
        const canRetryHydration = (
          hydrationReloadAttempted === false
          && (
            clientHydrationState.clientState?.status !== "client_boot_failed"
            || clientHydrationState.clientState?.reason === "stale_browser_assets"
          )
        );
        if (canRetryHydration) {
          const reloadResult = await reloadBrowserAppTab(browserUrl);
          hydrationReloadAttempted = reloadResult.ok === true;
          if (hydrationReloadAttempted) {
            clientHydrationState = await waitForBrowserClientHydration(
              browserUrl,
              CLIENT_HYDRATION_RELOAD_WAIT_MS,
              workspaceState.assetVersion,
            );
          }
        }
      }
      if (!clientHydrationState.ready) {
        if (!doesBrowserClientAssetVersionMatch(clientHydrationState?.clientState || {}, workspaceState.assetVersion)) {
          await notifyTab(
            tabId,
            "error",
            buildStaleBrowserAssetsMessage({
              resolvedBrowserOpen,
              focusNotice,
              clientState: clientHydrationState?.clientState || {},
              expectedAssetVersion: workspaceState.assetVersion,
            }),
          );
          return { holdLock: false, outcome: "stale_browser_assets" };
        }
        await notifyTab(
          tabId,
          "error",
          buildClientShellNotHydratedMessage({
            resolvedBrowserOpen,
            focusNotice,
            clientState: clientHydrationState?.clientState || {},
          }),
        );
        return { holdLock: false, outcome: "client_shell_not_hydrated" };
      }
      const message = suffix.length ? `${baseMessage} ${suffix.join(" ")}` : baseMessage;
      await notifyTab(tabId, "success", message);
      return { holdLock: false, outcome: "loaded" };
    }
    if (workspaceState.loadFailed) {
      const parts = [workspaceState.loadFailureMessage || "LegalPDF Translate could not load the exact Gmail message."];
      if (focusNotice !== "") {
        parts.push(focusNotice);
      }
      await notifyTab(tabId, "error", parts.join(" "));
      return { holdLock: false, outcome: "load_failed" };
    }
    if (workspaceState.warming || workspaceState.pending) {
      await notifyTab(
        tabId,
        "info",
        buildWorkspaceWarmupMessage({
          baseMessage,
          focusNotice,
          resolvedBrowserOpen,
        }),
      );
      return { holdLock: true, outcome: "warming" };
    }
    if (workspaceState.workspaceRouteReachable || workspaceState.appBootstrapReady) {
      await notifyTab(
        tabId,
        "error",
        buildWorkspaceNoHandoffMessage({
          resolvedBrowserOpen,
          focusNotice,
        }),
      );
      return { holdLock: false, outcome: "workspace_no_handoff" };
    }
    await notifyTab(
      tabId,
      "error",
      buildWorkspaceFailureMessage({
        resolvedBrowserOpen,
        focusNotice,
      }),
    );
    return { holdLock: false, outcome: "workspace_failure" };
  }
  const message = suffix.length ? `${baseMessage} ${suffix.join(" ")}` : baseMessage;
  await notifyTab(tabId, "success", message);
  return { holdLock: false, outcome: "accepted" };
}

chrome.action.onClicked.addListener(async (tab) => {
  if (!Number.isInteger(tab.id) || typeof tab.url !== "string" || !tab.url.startsWith("https://mail.google.com/")) {
    return;
  }

  const ready = await ensureContentScriptReady(tab.id);
  if (!ready) {
    await showFallbackBanner(
      tab.id,
      "error",
      "Reload Gmail after installing or updating the extension."
    );
    return;
  }

  const extractionResult = await sendTabMessage(tab.id, { type: "gmail-intake-extract" });
  if (!extractionResult.ok) {
    await notifyTab(tab.id, "error", "Reload Gmail after installing or updating the extension.");
    return;
  }

  const extraction = extractionResult.response;
  if (!extraction || extraction.ok !== true || typeof extraction.context !== "object" || extraction.context === null) {
    const message =
      extraction && typeof extraction.message === "string" && extraction.message.trim() !== ""
        ? extraction.message.trim()
        : "The open Gmail message is not identifiable exactly.";
    await notifyTab(tab.id, "error", message);
    return;
  }

  const handoffLock = claimHandoffLock(tab.id, extraction.context);
  if (!handoffLock.ok) {
    await focusExistingBrowserAppWindow();
    await notifyTab(
      tab.id,
      "info",
      "LegalPDF Translate is already preparing this Gmail handoff. Please wait a few seconds or focus the LegalPDF window.",
    );
    return;
  }
  if (handoffLock.staleRecovered) {
    await notifyTab(
      tab.id,
      "info",
      "A previous Gmail handoff stalled, so LegalPDF Translate is retrying with a fresh handoff now.",
    );
  }

  let shouldReleaseHandoffLock = true;
  try {
    const bridgeResolution = await resolveBridgeConfigForClick();
    if (!bridgeResolution.ok) {
      if (bridgeResolution.launchInProgress) {
        const pendingBrowserUrl = normalizeUrl(bridgeResolution.nativeResponse?.browser_url);
        await focusExistingBrowserAppWindow(pendingBrowserUrl || DEFAULT_BROWSER_APP_URL);
      }
      await notifyTab(tab.id, bridgeResolution.messageKind || "error", bridgeResolution.message);
      return;
    }
    if (!isHandoffLockCurrent(handoffLock)) {
      return;
    }

    const focusNotice = buildFocusNotice(bridgeResolution.nativeResponse, bridgeResolution.degradedMode);
    let browserAppOpened = false;
    const browserUrl = normalizeUrl(bridgeResolution.nativeResponse?.browser_url);
    const browserOpenOwnedBy = normalizeToken(bridgeResolution.nativeResponse?.browser_open_owned_by).toLowerCase();
    const waitForLaunchedTab = Boolean(
      bridgeResolution.nativeResponse
      && bridgeResolution.nativeResponse.ui_owner === "browser_app"
      && bridgeResolution.nativeResponse.launched === true
      && browserUrl !== ""
      && browserOpenOwnedBy !== "extension"
    );
    if (
      bridgeResolution.nativeResponse
      && bridgeResolution.nativeResponse.ui_owner === "browser_app"
      && browserUrl !== ""
      && !waitForLaunchedTab
    ) {
      browserAppOpened = await openOrFocusBrowserApp(browserUrl);
    }
    if (!isHandoffLockCurrent(handoffLock)) {
      return;
    }
    const handoffResult = await postContext(
      tab.id,
      extraction.context,
      bridgeResolution.config,
      bridgeResolution.nativeResponse,
      focusNotice,
      browserAppOpened,
      browserUrl,
      waitForLaunchedTab,
    );
    shouldReleaseHandoffLock = Boolean(handoffResult?.holdLock) === false;
  } finally {
    if (shouldReleaseHandoffLock) {
      releaseHandoffLock(handoffLock);
    }
  }
});

if (globalThis && globalThis.__LEGALPDF_TEST__ === true) {
  globalThis.__legalPdfGmailIntakeBackgroundTestHooks = {
    LAUNCH_READINESS_WAIT_MS,
    HANDOFF_LOCK_MAX_AGE_MS,
    CLIENT_HYDRATION_WAIT_MS,
    CLIENT_HYDRATION_RELOAD_WAIT_MS,
    buildHandoffKey,
    claimHandoffLock,
    releaseHandoffLock,
    isHandoffLockCurrent,
    handoffInFlight,
    resolveBridgeConfigForClick,
    postContext,
    settleBrowserAppHandoff,
    waitForBrowserClientHydration,
    reloadBrowserAppTab,
  };
}
