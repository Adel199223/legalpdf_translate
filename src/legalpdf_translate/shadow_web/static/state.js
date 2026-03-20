const SUPPORTED_VIEWS = new Set([
  "dashboard",
  "new-job",
  "recent-jobs",
  "settings",
  "profile",
  "power-tools",
  "extension-lab",
]);

function safeToken(value, fallback) {
  const cleaned = String(value ?? "")
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^[._-]+|[._-]+$/g, "");
  return cleaned || fallback;
}

function nextWorkspaceId() {
  if (globalThis.crypto?.randomUUID) {
    return `workspace-${crypto.randomUUID().slice(0, 8)}`;
  }
  return `workspace-${Math.random().toString(16).slice(2, 10)}`;
}

export const appState = {
  bootstrap: null,
  currentSeed: null,
  currentRowId: null,
  runtimeMode: "live",
  workspaceId: "workspace-1",
  activeView: "dashboard",
  uiVariant: "qt",
  extensionDiagnostics: null,
};

function defaultViewForUiVariant(uiVariant) {
  return uiVariant === "legacy" ? "dashboard" : "new-job";
}

export function initializeRouteState(config) {
  const params = new URLSearchParams(window.location.search);
  appState.runtimeMode = params.get("mode") === "live" ? "live" : String(config.defaultRuntimeMode || "shadow");
  appState.workspaceId = safeToken(
    params.get("workspace") || config.defaultWorkspaceId || nextWorkspaceId(),
    "workspace-1",
  );
  appState.uiVariant = params.get("ui") === "legacy" ? "legacy" : String(config.defaultUiVariant || "qt");
  syncActiveViewFromLocation();
  document.body.dataset.uiVariant = appState.uiVariant;
  writeRouteState();
  return appState;
}

export function syncActiveViewFromLocation() {
  const hashView = window.location.hash.replace(/^#/, "").trim();
  appState.activeView = SUPPORTED_VIEWS.has(hashView) ? hashView : defaultViewForUiVariant(appState.uiVariant);
  return appState.activeView;
}

export function writeRouteState() {
  const url = new URL(window.location.href);
  url.searchParams.set("mode", appState.runtimeMode);
  url.searchParams.set("workspace", appState.workspaceId);
  if (appState.uiVariant === "legacy") {
    url.searchParams.set("ui", "legacy");
  } else {
    url.searchParams.delete("ui");
  }
  url.hash = appState.activeView;
  window.history.replaceState({}, "", url);
}

export function setRuntimeMode(mode) {
  appState.runtimeMode = mode === "live" ? "live" : "shadow";
  writeRouteState();
}

export function setActiveView(view) {
  appState.activeView = SUPPORTED_VIEWS.has(view) ? view : defaultViewForUiVariant(appState.uiVariant);
  writeRouteState();
}
