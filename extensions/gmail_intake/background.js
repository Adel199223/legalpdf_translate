const DEFAULT_BRIDGE_PORT = 8765;
const NATIVE_FOCUS_HOST = "com.legalpdf.gmail_focus";
const COLD_START_TAB_WAIT_MS = 2200;
const COLD_START_TAB_POLL_MS = 150;

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
        banner.style.background = bannerKind === "success" ? "#D1FADF" : "#FEE4E2";
        banner.style.border = `1px solid ${bannerKind === "success" ? "#6CE9A6" : "#FDA29B"}`;
        document.documentElement.appendChild(banner);
        window.setTimeout(() => banner.remove(), 4500);
      },
      args: [kind === "success" ? "success" : "error", message],
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
    case "runtime_metadata_invalid":
      return "LegalPDF Translate has invalid Gmail bridge runtime metadata.";
    case "bridge_port_mismatch":
      return "LegalPDF Translate is listening on a different Gmail bridge port.";
    case "bridge_port_owner_unknown":
      return "LegalPDF Translate could not verify the Gmail bridge listener.";
    case "bridge_port_owner_mismatch":
      return "Another process is using the Gmail bridge port configured for LegalPDF Translate.";
    case "window_not_found":
      return "LegalPDF Translate is running without a visible main window.";
    case "launch_target_missing":
    case "launch_helper_missing":
    case "launch_python_missing":
      return "LegalPDF Translate auto-launch is not available from this checkout.";
    case "launch_command_failed":
      return "LegalPDF Translate could not be started automatically.";
    case "launch_timeout":
      return "LegalPDF Translate was started, but the Gmail bridge did not become ready in time.";
    case "unsupported_platform":
      return "Foreground activation is only supported on Windows for this extension.";
    default:
      return "Gmail bridge is not ready in LegalPDF Translate.";
  }
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

async function resolveBridgeConfigForClick() {
  const nativePreparation = await requestNativePreparation();
  if (nativePreparation.ok) {
    const response = nativePreparation.response;
    const bridgePort = normalizePort(response && response.bridgePort);
    const bridgeToken = normalizeToken(response && response.bridgeToken);
    if (response && response.ok === true && bridgeToken !== "") {
      return {
        ok: true,
        degradedMode: false,
        nativeResponse: response,
        config: { bridgePort, bridgeToken },
      };
    }
    return {
      ok: false,
      degradedMode: false,
      nativeResponse: response,
      message: buildPrepareFailureMessage(response),
    };
  }

  const storedConfig = await getStoredBridgeConfig();
  if (storedConfig.bridgeToken !== "") {
    return {
      ok: true,
      degradedMode: true,
      nativeResponse: null,
      config: storedConfig,
    };
  }

  return {
    ok: false,
    degradedMode: true,
    nativeResponse: null,
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
    resolved = await openOrFocusBrowserApp(targetUrl);
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
  const endpoint = `http://127.0.0.1:${config.bridgePort}/gmail-intake`;
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
    const resolvedBrowserOpen = await settleBrowserAppHandoff(browserUrl, browserAppOpened, waitForLaunchedTab);
    await notifyTab(
      tabId,
      "error",
      resolvedBrowserOpen
        ? `LegalPDF Translate is not listening on ${endpoint}.`
        : `LegalPDF Translate is not listening on ${endpoint}. The browser app may still need manual focus.`
    );
    return;
  }

  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }

  if (!response.ok) {
    const resolvedBrowserOpen = await settleBrowserAppHandoff(browserUrl, browserAppOpened, waitForLaunchedTab);
    const message =
      typeof payload.message === "string" && payload.message.trim() !== ""
        ? payload.message.trim()
        : `LegalPDF Translate rejected the request (${response.status}).`;
    await notifyTab(
      tabId,
      "error",
      resolvedBrowserOpen ? message : `${message} The browser app may still need manual focus.`,
    );
    return;
  }

  const resolvedBrowserOpen = await settleBrowserAppHandoff(browserUrl, browserAppOpened, waitForLaunchedTab);
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
  const message = suffix.length ? `${baseMessage} ${suffix.join(" ")}` : baseMessage;
  await notifyTab(tabId, "success", message);
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

  const bridgeResolution = await resolveBridgeConfigForClick();
  if (!bridgeResolution.ok) {
    await notifyTab(tab.id, "error", bridgeResolution.message);
    return;
  }

  const focusNotice = buildFocusNotice(bridgeResolution.nativeResponse, bridgeResolution.degradedMode);
  let browserAppOpened = false;
  const browserUrl = normalizeUrl(bridgeResolution.nativeResponse?.browser_url);
  const waitForLaunchedTab = Boolean(
    bridgeResolution.nativeResponse
    && bridgeResolution.nativeResponse.ui_owner === "browser_app"
    && bridgeResolution.nativeResponse.launched === true
    && browserUrl !== ""
  );
  if (
    bridgeResolution.nativeResponse
    && bridgeResolution.nativeResponse.ui_owner === "browser_app"
    && browserUrl !== ""
    && !waitForLaunchedTab
  ) {
    browserAppOpened = await openOrFocusBrowserApp(browserUrl);
  }
  await postContext(
    tab.id,
    extraction.context,
    bridgeResolution.config,
    bridgeResolution.nativeResponse,
    focusNotice,
    browserAppOpened,
    browserUrl,
    waitForLaunchedTab,
  );
});
