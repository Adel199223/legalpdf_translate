const SUPPORTED_VIEWS = new Set([
  "dashboard",
  "new-job",
  "gmail-intake",
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
  operatorMode: false,
  newJobTask: "translation",
  extensionDiagnostics: null,
};

export function routeShellMode(state = appState) {
  return state.uiVariant === "qt" && state.workspaceId === "gmail-intake" && state.activeView === "gmail-intake"
    ? "gmail-focus"
    : "standard";
}

function beginnerSurfaceActive(state = appState) {
  return state.uiVariant === "qt"
    && ["dashboard", "new-job", "recent-jobs", "profile", "settings"].includes(state.activeView)
    && !state.operatorMode;
}

function syncRouteDatasets() {
  if (!globalThis.document?.body?.dataset) {
    return;
  }
  document.body.dataset.uiVariant = appState.uiVariant;
  document.body.dataset.workspaceId = appState.workspaceId;
  document.body.dataset.activeView = appState.activeView;
  document.body.dataset.shellMode = routeShellMode();
  document.body.dataset.beginnerSurface = beginnerSurfaceActive() ? "true" : "false";
}

function emitRouteStateChanged() {
  if (typeof window === "undefined" || typeof window.dispatchEvent !== "function" || typeof CustomEvent !== "function") {
    return;
  }
  window.dispatchEvent(new CustomEvent("legalpdf:route-state-changed", {
    detail: {
      activeView: appState.activeView,
      runtimeMode: appState.runtimeMode,
      workspaceId: appState.workspaceId,
      uiVariant: appState.uiVariant,
      operatorMode: appState.operatorMode,
    },
  }));
}

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
  appState.operatorMode = ["1", "true", "on"].includes(String(params.get("operator") || "").trim().toLowerCase());
  syncActiveViewFromLocation();
  syncRouteDatasets();
  writeRouteState();
  return appState;
}

export function syncActiveViewFromLocation() {
  const hashView = window.location.hash.replace(/^#/, "").trim();
  appState.activeView = SUPPORTED_VIEWS.has(hashView) ? hashView : defaultViewForUiVariant(appState.uiVariant);
  syncRouteDatasets();
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
  if (appState.operatorMode) {
    url.searchParams.set("operator", "1");
  } else {
    url.searchParams.delete("operator");
  }
  url.hash = appState.activeView;
  window.history.replaceState({}, "", url);
}

export function setRuntimeMode(mode) {
  appState.runtimeMode = mode === "live" ? "live" : "shadow";
  writeRouteState();
  syncRouteDatasets();
}

export function setActiveView(view) {
  appState.activeView = SUPPORTED_VIEWS.has(view) ? view : defaultViewForUiVariant(appState.uiVariant);
  writeRouteState();
  syncRouteDatasets();
  emitRouteStateChanged();
}

export function setOperatorMode(enabled) {
  appState.operatorMode = Boolean(enabled);
  writeRouteState();
  syncRouteDatasets();
  emitRouteStateChanged();
}
