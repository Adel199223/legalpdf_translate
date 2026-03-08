const DEFAULT_BRIDGE_PORT = 8765;

async function getBridgeConfig() {
  const stored = await chrome.storage.local.get(["bridgePort", "bridgeToken"]);
  const parsedPort = Number.parseInt(String(stored.bridgePort ?? DEFAULT_BRIDGE_PORT), 10);
  const bridgePort =
    Number.isInteger(parsedPort) && parsedPort >= 1 && parsedPort <= 65535
      ? parsedPort
      : DEFAULT_BRIDGE_PORT;
  const bridgeToken = String(stored.bridgeToken ?? "").trim();
  return { bridgePort, bridgeToken };
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

async function postContext(tabId, context, config) {
  const endpoint = `http://127.0.0.1:${config.bridgePort}/gmail-intake`;
  let response;
  try {
    response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${config.bridgeToken}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message_id: context.message_id,
        thread_id: context.thread_id,
        subject: context.subject,
        account_email: context.account_email ?? undefined
      })
    });
  } catch (_error) {
    await notifyTab(
      tabId,
      "error",
      `LegalPDF Translate is not listening on ${endpoint}.`
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
    const message =
      typeof payload.message === "string" && payload.message.trim() !== ""
        ? payload.message.trim()
        : `LegalPDF Translate rejected the request (${response.status}).`;
    await notifyTab(tabId, "error", message);
    return;
  }

  const message =
    typeof payload.message === "string" && payload.message.trim() !== ""
      ? payload.message.trim()
      : "Gmail intake accepted.";
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

  const config = await getBridgeConfig();
  if (config.bridgeToken === "") {
    await notifyTab(tab.id, "error", "Bridge token is missing in extension options.");
    return;
  }

  let extraction;
  const extractionResult = await sendTabMessage(tab.id, { type: "gmail-intake-extract" });
  if (!extractionResult.ok) {
    await notifyTab(tab.id, "error", "Reload Gmail after installing or updating the extension.");
    return;
  }
  extraction = extractionResult.response;

  if (!extraction || extraction.ok !== true || typeof extraction.context !== "object" || extraction.context === null) {
    const message =
      extraction && typeof extraction.message === "string" && extraction.message.trim() !== ""
        ? extraction.message.trim()
        : "The open Gmail message is not identifiable exactly.";
    await notifyTab(tab.id, "error", message);
    return;
  }

  await postContext(tab.id, extraction.context, config);
});
