const DAILY_BROWSER_PORT = 8877;
const PREVIEW_BROWSER_PORT = 8888;
const DEFAULT_WORKSPACE = "workspace-1";

function extractErrorMessage(payload) {
  return String(
    payload?.diagnostics?.error ||
      payload?.diagnostics?.message ||
      payload?.message ||
      payload?.error ||
      "",
  ).trim();
}

function browserBootstrapConfig() {
  return globalThis.window?.LEGALPDF_BROWSER_BOOTSTRAP || {};
}

function currentLocationUrl() {
  const href = globalThis.window?.location?.href || "http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job";
  return new URL(href);
}

function currentUiVariant(url, config) {
  return new URLSearchParams(url.search).get("ui") === "legacy"
    ? "legacy"
    : String(config.defaultUiVariant || "qt");
}

function defaultViewForContext({ uiVariant, workspaceId }) {
  if (uiVariant === "legacy") {
    return "dashboard";
  }
  return workspaceId === "gmail-intake" ? "gmail-intake" : "new-job";
}

function buildBrowserUrl({ host, port, runtimeMode, workspaceId, uiVariant }) {
  const params = new URLSearchParams();
  params.set("mode", runtimeMode);
  params.set("workspace", workspaceId);
  if (uiVariant === "legacy") {
    params.set("ui", "legacy");
  }
  return `http://${host}:${intPort(port)}/?${params.toString()}#${defaultViewForContext({ uiVariant, workspaceId })}`;
}

function buildLaunchCommand({ port, runtimeMode, workspaceId, uiVariant }) {
  const args = [
    ".\\.venv311\\Scripts\\python.exe",
    "tooling\\launch_browser_app_live_detached.py",
  ];
  if (runtimeMode !== "live") {
    args.push("--mode", runtimeMode);
  }
  if (workspaceId !== DEFAULT_WORKSPACE) {
    args.push("--workspace", workspaceId);
  }
  if (intPort(port) !== DAILY_BROWSER_PORT) {
    args.push("--port", String(intPort(port)));
  }
  if (uiVariant === "legacy") {
    args.push("--ui", "legacy");
  }
  return args.join(" ");
}

function intPort(value) {
  const port = Number(value);
  return Number.isFinite(port) && port > 0 ? port : DAILY_BROWSER_PORT;
}

function resolveLocalServerContext(path, state) {
  const config = browserBootstrapConfig();
  const location = currentLocationUrl();
  const params = new URLSearchParams(location.search);
  const port = intPort(config.shadowPort || location.port || DAILY_BROWSER_PORT);
  const isPreviewPort = port === PREVIEW_BROWSER_PORT;
  const uiVariant = currentUiVariant(location, config);
  const runtimeMode = isPreviewPort
    ? "shadow"
    : (params.get("mode") === "live" ? "live" : String(state?.runtimeMode || config.defaultRuntimeMode || "shadow"));
  const workspaceId = isPreviewPort
    ? "workspace-preview"
    : String(state?.workspaceId || params.get("workspace") || config.defaultWorkspaceId || DEFAULT_WORKSPACE);
  const host = String(config.shadowHost || location.hostname || "127.0.0.1");
  return {
    host,
    port,
    runtimeMode,
    workspaceId,
    uiVariant,
    requestPath: String(path || ""),
    isPreviewPort,
  };
}

export function describeLocalServerUnavailable(value) {
  const context = value?.serverUnavailableContext || value || {};
  const host = String(context.host || "127.0.0.1");
  const port = intPort(context.port || DAILY_BROWSER_PORT);
  const runtimeMode = String(context.runtimeMode || (port === PREVIEW_BROWSER_PORT ? "shadow" : "live"));
  const workspaceId = String(
    context.workspaceId || (port === PREVIEW_BROWSER_PORT ? "workspace-preview" : DEFAULT_WORKSPACE),
  );
  const uiVariant = String(context.uiVariant || "qt");
  const isPreviewPort = Boolean(context.isPreviewPort || port === PREVIEW_BROWSER_PORT);
  const recommendedUrl = String(
    context.recommendedUrl || buildBrowserUrl({ host, port, runtimeMode, workspaceId, uiVariant }),
  );
  const launcherCommand = String(
    context.launcherCommand || buildLaunchCommand({ port, runtimeMode, workspaceId, uiVariant }),
  );
  if (isPreviewPort) {
    return {
      title: "Review preview unavailable",
      message: `The fixed review preview on ${host}:${port} is not responding. This tab may be a cached preview from an older review session.`,
      statusMessage: `Review preview unavailable on ${host}:${port}.`,
      diagnosticsHint: "The browser still has the old preview tab, but the local review server is no longer responding.",
      recoverySteps: [
        `Restart the fixed review preview with: ${launcherCommand}`,
        `Reopen the preview at: ${recommendedUrl}`,
        "Use port 8877 for the normal daily browser app and port 8888 only for branch review.",
      ],
      host,
      port,
      runtimeMode,
      workspaceId,
      recommendedUrl,
      launcherCommand,
    };
  }
  return {
    title: "Browser app unavailable",
    message: `The local browser app on ${host}:${port} is not responding. This tab may be cached, or the daily browser app may not be running right now.`,
    statusMessage: `Browser app unavailable on ${host}:${port}.`,
    diagnosticsHint: "The page loaded locally, but the active browser-app listener is not responding to API requests.",
    recoverySteps: [
      `Start the browser app again with: ${launcherCommand}`,
      `Open the current browser workspace again at: ${recommendedUrl}`,
      "If you meant to review the feature-preview shell instead, use the fixed preview on port 8888.",
    ],
    host,
    port,
    runtimeMode,
    workspaceId,
    recommendedUrl,
    launcherCommand,
  };
}

export function isLocalServerUnavailableError(error) {
  return Boolean(
    error?.isLocalServerUnavailable
    || error?.payload?.diagnostics?.error === "local_server_unavailable",
  );
}

export function buildLocalServerUnavailableError(path, state, cause) {
  const context = resolveLocalServerContext(path, state);
  const details = describeLocalServerUnavailable(context);
  const error = new Error(details.message);
  error.name = "LocalServerUnavailableError";
  error.status = 0;
  error.cause = cause;
  error.isLocalServerUnavailable = true;
  error.serverUnavailableContext = {
    ...context,
    recommendedUrl: details.recommendedUrl,
    launcherCommand: details.launcherCommand,
  };
  error.payload = {
    status: "failed",
    diagnostics: {
      error: "local_server_unavailable",
      message: details.message,
      host: details.host,
      port: details.port,
      runtime_mode: details.runtimeMode,
      workspace_id: details.workspaceId,
      request_path: context.requestPath,
      recommended_url: details.recommendedUrl,
      launcher_command: details.launcherCommand,
      cause: String(cause?.message || cause || ""),
    },
  };
  return error;
}

export async function fetchJson(path, state, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("X-LegalPDF-Runtime-Mode", state.runtimeMode);
  headers.set("X-LegalPDF-Workspace-Id", state.workspaceId);
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers,
    });
  } catch (error) {
    throw buildLocalServerUnavailableError(path, state, error);
  }
  const rawText = await response.text();
  let payload = {};
  if (rawText) {
    try {
      payload = JSON.parse(rawText);
    } catch {
      payload = {
        status: "failed",
        diagnostics: {
          error: rawText,
        },
      };
    }
  }
  if (!response.ok || payload.status === "failed") {
    const error = new Error(
      extractErrorMessage(payload) || rawText || `Request failed (${response.status}).`,
    );
    error.payload = payload;
    error.status = response.status;
    throw error;
  }
  return payload;
}
