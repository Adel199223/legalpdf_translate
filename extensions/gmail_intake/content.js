(function () {
  if (window.__legalPdfGmailIntakeLoaded === true) {
    return;
  }
  window.__legalPdfGmailIntakeLoaded = true;

  const BANNER_ID = "legalpdf-gmail-intake-banner";
  const DEBUG_TRIGGER_EVENT = "legalpdf-gmail-intake-debug-trigger";
  const DEBUG_RESULT_EVENT = "legalpdf-gmail-intake-debug-result";

  function showBanner(message, kind) {
    const existing = document.getElementById(BANNER_ID);
    if (existing) {
      existing.remove();
    }

    const banner = document.createElement("div");
    banner.id = BANNER_ID;
    banner.textContent = message;
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
    if (kind === "success") {
      banner.style.background = "#D1FADF";
      banner.style.border = "1px solid #6CE9A6";
    } else if (kind === "info") {
      banner.style.background = "#D9F0FF";
      banner.style.border = "1px solid #84CAFF";
    } else {
      banner.style.background = "#FEE4E2";
      banner.style.border = "1px solid #FDA29B";
    }
    document.documentElement.appendChild(banner);
    window.setTimeout(() => banner.remove(), 4500);
  }

  function visibleElements(selector) {
    return Array.from(document.querySelectorAll(selector)).filter((node) => {
      return node instanceof HTMLElement && node.offsetParent !== null;
    });
  }

  function extractAccountEmail() {
    const candidates = [
      'a[aria-label*="@"][href*="SignOutOptions"]',
      'a[aria-label*="@"][role="button"]',
      'div[aria-label*="@"][role="button"]',
      'button[aria-label*="@"]'
    ];
    const emailPattern = /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/i;
    for (const selector of candidates) {
      const node = document.querySelector(selector);
      if (!(node instanceof HTMLElement)) {
        continue;
      }
      const label = String(node.getAttribute("aria-label") ?? "").trim();
      const match = label.match(emailPattern);
      if (match) {
        return match[0];
      }
    }
    return null;
  }

  function extractThreadId(candidate) {
    const nearest = candidate.closest("[data-legacy-thread-id]");
    const nearestThreadId = nearest?.getAttribute("data-legacy-thread-id")?.trim();
    if (nearestThreadId) {
      return nearestThreadId;
    }

    const visibleThreadIds = new Set(
      visibleElements("[data-legacy-thread-id]")
        .map((node) => node.getAttribute("data-legacy-thread-id")?.trim() ?? "")
        .filter((value) => value !== "")
    );
    if (visibleThreadIds.size === 1) {
      return Array.from(visibleThreadIds)[0];
    }
    throw new Error("The open Gmail thread is not identifiable exactly.");
  }

  function extractExactMailContext() {
    const candidates = visibleElements("[data-message-id][data-legacy-message-id]");
    if (candidates.length !== 1) {
      throw new Error("Open exactly one expanded Gmail message before sending intake.");
    }

    const candidate = candidates[0];
    const messageId = candidate.getAttribute("data-legacy-message-id")?.trim() ?? "";
    if (messageId === "") {
      throw new Error("The Gmail message id is unavailable for the open message.");
    }

    const threadId = extractThreadId(candidate);
    const subject = document.querySelector("h2.hP")?.textContent?.trim() ?? "";
    return {
      message_id: messageId,
      thread_id: threadId,
      subject,
      account_email: extractAccountEmail(),
      source_gmail_url: window.location.href
    };
  }

  function dispatchDebugResult(detail) {
    window.dispatchEvent(new CustomEvent(DEBUG_RESULT_EVENT, {
      detail: detail && typeof detail === "object" ? detail : {}
    }));
  }

  function triggerDebugClick(detail) {
    chrome.runtime.sendMessage({
      type: "gmail-intake-debug-click",
      detail: detail && typeof detail === "object" ? detail : {}
    }, (response) => {
      const runtimeError = chrome.runtime?.lastError;
      if (runtimeError) {
        dispatchDebugResult({
          ok: false,
          message: String(runtimeError.message || "debug_click_failed")
        });
        return;
      }
      dispatchDebugResult(response && typeof response === "object"
        ? response
        : { ok: true });
    });
  }

  window.addEventListener(DEBUG_TRIGGER_EVENT, (event) => {
    triggerDebugClick(event instanceof CustomEvent ? event.detail : {});
  });

  window.addEventListener("message", (event) => {
    if (event.source !== window) {
      return;
    }
    const payload = event.data;
    if (!payload || typeof payload !== "object") {
      return;
    }
    if (payload.type !== DEBUG_TRIGGER_EVENT) {
      return;
    }
    triggerDebugClick(payload.detail);
  });

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (!message || typeof message !== "object") {
      return false;
    }

    if (message.type === "gmail-intake-ping") {
      sendResponse({ ok: true, type: "gmail-intake-ready" });
      return false;
    }

    if (message.type === "gmail-intake-status") {
      const kind =
        message.kind === "success"
          ? "success"
          : message.kind === "info"
            ? "info"
            : "error";
      const text =
        typeof message.message === "string" && message.message.trim() !== ""
          ? message.message.trim()
          : kind === "success"
            ? "Gmail intake accepted."
            : kind === "info"
              ? "Gmail intake is still in progress."
            : "Gmail intake failed.";
      showBanner(text, kind);
      return false;
    }

    if (message.type === "gmail-intake-extract") {
      try {
        const context = extractExactMailContext();
        sendResponse({ ok: true, context });
      } catch (error) {
        const failure =
          error instanceof Error && error.message.trim() !== ""
            ? error.message.trim()
            : "The open Gmail message is not identifiable exactly.";
        showBanner(failure, "error");
        sendResponse({ ok: false, message: failure });
      }
      return false;
    }

    return false;
  });
})();
