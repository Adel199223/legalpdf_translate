const DEFAULT_BRIDGE_PORT = 8765;
const NATIVE_FOCUS_HOST = "com.legalpdf.gmail_focus";

function normalizePort(value) {
  const parsed = Number.parseInt(String(value ?? DEFAULT_BRIDGE_PORT), 10);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    return null;
  }
  return parsed;
}

function normalizeToken(value) {
  return String(value ?? "").trim();
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function setStatus(message, kind) {
  const node = document.getElementById("status");
  node.textContent = message;
  node.dataset.kind = kind;
}

function describeRuntimeReason(reason) {
  switch (normalizeToken(reason)) {
    case "bridge_owner_ready":
    case "legacy_bridge_owner_ready":
      return "Ready";
    case "bridge_disabled":
      return "Disabled in LegalPDF Translate";
    case "bridge_token_missing":
      return "Token missing in LegalPDF Translate";
    case "invalid_bridge_port":
      return "Configured port is invalid";
    case "runtime_metadata_missing":
    case "bridge_not_running":
      return "App is not running the Gmail bridge";
    case "runtime_metadata_invalid":
      return "App runtime metadata is invalid";
    case "bridge_port_mismatch":
      return "Configured app port does not match the running bridge";
    case "bridge_port_owner_unknown":
      return "Could not verify the bridge listener owner";
    case "bridge_port_owner_mismatch":
      return "Another process owns the configured bridge port";
    case "window_not_found":
      return "App window was not found";
    case "unsupported_platform":
      return "Foreground activation is Windows-only";
    default:
      return "Diagnostics unavailable";
  }
}

function describeUiOwner(response) {
  const owner = normalizeToken(response && response.ui_owner);
  if (owner === "browser_app") {
    return "Browser app live bridge";
  }
  if (owner === "qt_app") {
    return "Desktop app live bridge";
  }
  if (owner === "external") {
    return "External process";
  }
  return "Auto-configured from LegalPDF Translate";
}

function describeLaunchReason(reason) {
  switch (normalizeToken(reason)) {
    case "launch_target_ready":
      return "Ready from current checkout";
    case "launch_target_missing":
      return "Current checkout not found";
    case "launch_helper_missing":
      return "Launch helper missing";
    case "launch_python_missing":
      return "Checkout Python missing";
    default:
      return "Unavailable";
  }
}

async function loadDiagnostics() {
  setStatus("Refreshing diagnostics...", "info");
  setText("extensionId", chrome.runtime.id);

  const stored = await chrome.storage.local.get(["bridgePort", "bridgeToken"]);
  const fallbackPort = normalizePort(stored.bridgePort);
  const fallbackTokenPresent = normalizeToken(stored.bridgeToken) !== "";
  setText(
    "legacyFallback",
    fallbackTokenPresent
      ? `Stored fallback available${fallbackPort === null ? "" : ` on port ${fallbackPort}`}`
      : "No stored fallback"
  );

  try {
    const response = await chrome.runtime.sendNativeMessage(NATIVE_FOCUS_HOST, {
      action: "prepare_gmail_intake",
      requestFocus: false,
      includeToken: false,
    });
    const resolvedPort = normalizePort(response && response.bridgePort);
    const tokenPresent = response && response.bridgeTokenPresent === true;

    setText("mode", describeUiOwner(response));
    setText("nativeHostAvailability", "Available");
    setText("resolvedPort", resolvedPort === null ? "Unavailable" : String(resolvedPort));
    setText("tokenPresence", tokenPresent ? "Yes" : "No");
    setText(
      "runtimeStatus",
      response && response.ok === true && normalizeToken(response.ui_owner) === "browser_app"
        ? "Ready (browser app)"
        : describeRuntimeReason(response && response.reason)
    );
    setText(
      "autoLaunchReady",
      response && response.autoLaunchReady === true
        ? "Ready from current checkout"
        : describeLaunchReason(response && response.launchTargetReason)
    );
    setText(
      "launchTarget",
      response && typeof response.browser_url === "string" && response.browser_url.trim() !== ""
        ? response.browser_url.trim()
        : response && typeof response.launchTarget === "string" && response.launchTarget.trim() !== ""
          ? response.launchTarget.trim()
        : "Unavailable"
    );
    setStatus(
      response && response.ok === true
        ? normalizeToken(response.ui_owner) === "browser_app"
          ? "Browser-owned live Gmail bridge diagnostics loaded from LegalPDF Translate."
          : "Live Gmail bridge diagnostics loaded from LegalPDF Translate."
        : response && response.autoLaunchReady === true
          ? "LegalPDF Translate responded. The Gmail bridge is not running right now, but toolbar clicks can auto-start the app."
          : "LegalPDF Translate responded, but the Gmail bridge is not ready yet.",
      response && response.ok === true ? "success" : "warning"
    );
  } catch (_error) {
    setText("mode", fallbackTokenPresent ? "Legacy fallback only" : "Auto-config unavailable");
    setText("nativeHostAvailability", "Unavailable");
    setText("resolvedPort", fallbackPort === null ? "Unknown" : String(fallbackPort));
    setText("tokenPresence", fallbackTokenPresent ? "Yes (legacy fallback)" : "No");
    setText("runtimeStatus", "Native host unavailable");
    setText("autoLaunchReady", "Unavailable");
    setText("launchTarget", "Unavailable");
    setStatus(
      fallbackTokenPresent
        ? "Native messaging is unavailable, so only the stored legacy fallback can be used."
        : "Native messaging is unavailable and no legacy fallback is stored.",
      fallbackTokenPresent ? "warning" : "error"
    );
  }
}

document.addEventListener("DOMContentLoaded", () => {
  void loadDiagnostics();
  document.getElementById("refreshButton").addEventListener("click", () => {
    void loadDiagnostics();
  });
});
