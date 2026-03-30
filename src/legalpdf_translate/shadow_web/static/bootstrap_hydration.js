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

const STANDARD_BOOTSTRAP_RETRY_DELAYS_MS = [200, 350, 550];
const GMAIL_BOOTSTRAP_RETRY_DELAYS_MS = [200, 350, 550, 850, 1200];

function safeToken(value, fallback) {
  const cleaned = String(value ?? "")
    .trim()
    .replace(/[^A-Za-z0-9._-]+/g, "-")
    .replace(/^[._-]+|[._-]+$/g, "");
  return cleaned || fallback;
}

function normalizeRuntimeMode(value, fallback = "shadow") {
  const candidate = String(value ?? "").trim().toLowerCase();
  if (candidate === "live") {
    return "live";
  }
  if (candidate === "shadow") {
    return "shadow";
  }
  return fallback === "live" ? "live" : "shadow";
}

function normalizeUiVariant(value, fallback = "qt") {
  return String(value ?? "").trim().toLowerCase() === "legacy" ? "legacy" : fallback;
}

function defaultViewForContext({ uiVariant, workspaceId }) {
  if (uiVariant === "legacy") {
    return "dashboard";
  }
  return workspaceId === "gmail-intake" ? "gmail-intake" : "new-job";
}

function normalizeActiveView(value, fallback) {
  const candidate = String(value ?? "").trim();
  return SUPPORTED_VIEWS.has(candidate) ? candidate : fallback;
}

export function resolveBootstrapRouteContext({
  href = "http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job",
  defaultRuntimeMode = "shadow",
  defaultWorkspaceId = "workspace-1",
  defaultUiVariant = "qt",
} = {}) {
  const url = new URL(href);
  const params = new URLSearchParams(url.search);
  const uiVariant = normalizeUiVariant(params.get("ui"), normalizeUiVariant(defaultUiVariant, "qt"));
  const workspaceId = safeToken(params.get("workspace") || defaultWorkspaceId, "workspace-1");
  const runtimeMode = normalizeRuntimeMode(params.get("mode"), normalizeRuntimeMode(defaultRuntimeMode, "shadow"));
  const activeView = normalizeActiveView(
    url.hash.replace(/^#/, ""),
    defaultViewForContext({ uiVariant, workspaceId }),
  );
  return {
    runtimeMode,
    workspaceId,
    activeView,
    uiVariant,
  };
}

export function buildInitialClientReadyState({
  href,
  defaultRuntimeMode,
  defaultWorkspaceId,
  defaultUiVariant,
  assetVersion = "",
  buildSha = "",
} = {}) {
  const route = resolveBootstrapRouteContext({
    href,
    defaultRuntimeMode,
    defaultWorkspaceId,
    defaultUiVariant,
  });
  return {
    status: "warming",
    runtimeMode: route.runtimeMode,
    workspaceId: route.workspaceId,
    activeView: route.activeView,
    gmailHandoffState: route.workspaceId === "gmail-intake" ? "warming" : "idle",
    buildSha: String(buildSha || ""),
    assetVersion: String(assetVersion || ""),
    bootstrappedAt: null,
  };
}

export async function runStagedBootstrap({
  routeContext,
  fetchShell,
  fetchFull,
  sleep = (ms) => new Promise((resolve) => globalThis.setTimeout(resolve, ms)),
  onShell = null,
  onRetry = null,
} = {}) {
  if (typeof fetchShell !== "function") {
    throw new Error("fetchShell is required.");
  }
  if (typeof fetchFull !== "function") {
    throw new Error("fetchFull is required.");
  }

  const resolvedRouteContext = routeContext || {};
  const retryDelays = (
    resolvedRouteContext.workspaceId === "gmail-intake"
    || resolvedRouteContext.activeView === "gmail-intake"
  )
    ? GMAIL_BOOTSTRAP_RETRY_DELAYS_MS
    : STANDARD_BOOTSTRAP_RETRY_DELAYS_MS;

  const shellPayload = await fetchShell();
  if (typeof onShell === "function") {
    onShell(shellPayload);
  }

  for (let attemptIndex = 0; attemptIndex <= retryDelays.length; attemptIndex += 1) {
    try {
      const fullPayload = await fetchFull();
      return {
        shellPayload,
        fullPayload,
        attempts: attemptIndex + 1,
        retries: attemptIndex,
      };
    } catch (error) {
      if (attemptIndex >= retryDelays.length) {
        throw error;
      }
      const delayMs = retryDelays[attemptIndex];
      if (typeof onRetry === "function") {
        onRetry({
          attempt: attemptIndex + 1,
          maxAttempts: retryDelays.length + 1,
          delayMs,
          error,
        });
      }
      await sleep(delayMs);
    }
  }

  throw new Error("Browser bootstrap retry budget exhausted.");
}
