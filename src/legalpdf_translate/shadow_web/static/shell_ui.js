import { MORE_NAV_ORDER, buildNavigationGroups, runtimeModeDisplayLabel } from "./shell_presentation.js";
import { clearNode, createTextElement, setText } from "./safe_rendering.js";

const LIVE_BANNER_TEXT = "Live mode: using your real settings, Gmail drafts, and saved work.";
const OPERATOR_VISIBLE_HINT = "Technical build, listener, and diagnostics panels stay visible across the shell until you turn them off.";
const OPERATOR_HIDDEN_HINT = "Build, listener, and diagnostics panels stay hidden until you ask for them or a failure occurs.";

function createNavigationButton(item, activeView = "") {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "nav-button";
  button.dataset.view = item.id;
  button.appendChild(createTextElement("span", String(item.label)));
  button.appendChild(createTextElement(
    "span",
    item.status === "ready" ? "Ready" : String(item.status),
    "nav-meta",
  ));
  if (item.id === activeView) {
    button.classList.add("active");
  }
  return button;
}

export function renderNavigationInto({
  primaryContainer,
  moreContainer,
  moreShell,
  items = [],
  activeView = "",
  showGmailNav = false,
} = {}) {
  const { primary, more } = buildNavigationGroups(items, { showGmailNav });

  clearNode(primaryContainer);
  clearNode(moreContainer);

  for (const collection of [
    { container: primaryContainer, items: primary },
    { container: moreContainer, items: more },
  ]) {
    for (const item of collection.items) {
      collection.container.appendChild(createNavigationButton(item, activeView));
    }
  }

  const moreActive = MORE_NAV_ORDER.includes(activeView);
  moreShell.open = moreActive;
  moreShell.classList.toggle("has-active-view", moreActive);
}

export function renderLiveBannerInto(banner, runtime = {}) {
  if (!banner) {
    return;
  }
  if (runtime.live_data) {
    setText(banner, LIVE_BANNER_TEXT);
    banner.classList.remove("hidden");
  } else {
    banner.classList.add("hidden");
    setText(banner, "");
  }
}

export function renderTopbarInto(
  { workspaceLabel = null, runtimeModeLabel = null, liveBanner = null } = {},
  runtime = {},
) {
  if (workspaceLabel) {
    setText(workspaceLabel, runtime?.workspace_id || "");
  }
  if (runtimeModeLabel) {
    setText(runtimeModeLabel, runtimeModeDisplayLabel(runtime));
  }
  renderLiveBannerInto(liveBanner, runtime);
}

export function renderShellRuntimeLabelsInto(
  { workspaceLabel = null, runtimeModeLabel = null, liveBanner = null } = {},
  { workspaceLabel: workspaceText = "", runtimeModeLabel: runtimeModeText = "", hideLiveBanner = false } = {},
) {
  if (workspaceLabel) {
    setText(workspaceLabel, workspaceText);
  }
  if (runtimeModeLabel) {
    setText(runtimeModeLabel, runtimeModeText);
  }
  if (hideLiveBanner && liveBanner) {
    liveBanner.classList.add("hidden");
    setText(liveBanner, "");
  }
}

export function renderClientHydrationMarkerInto(
  { body = null, targetWindow = null } = {},
  marker = {},
) {
  if (body?.dataset) {
    body.dataset.clientReady = String(marker.status ?? "");
    body.dataset.clientWorkspace = String(marker.workspaceId ?? "");
    body.dataset.clientRuntimeMode = String(marker.runtimeMode ?? "");
    body.dataset.clientActiveView = String(marker.activeView ?? "");
    body.dataset.clientBuildSha = String(marker.buildSha ?? "");
    body.dataset.clientAssetVersion = String(marker.assetVersion ?? "");
    body.dataset.clientLaunchSession = String(marker.launchSessionId || "");
    body.dataset.clientHandoffSession = String(marker.handoffSessionId || "");
    body.dataset.clientLaunchSessionSchemaVersion = String(marker.launchSessionSchemaVersion || 0);
  }
  if (targetWindow) {
    targetWindow.LEGALPDF_BROWSER_CLIENT_READY = marker;
  }
}

export function renderRuntimeModeSelectorInto(select, runtimeMode = {}) {
  if (!select) {
    return;
  }
  clearNode(select);
  for (const mode of runtimeMode.supported_modes || []) {
    const option = document.createElement("option");
    option.value = mode.id;
    option.textContent = mode.label;
    if (mode.id === runtimeMode.current_mode) {
      option.selected = true;
    }
    select.appendChild(option);
  }
}

export function renderRuntimeModeBannerInto(banner, { show = false, message = "", mode = "" } = {}) {
  if (!banner) {
    return;
  }
  if (!show) {
    banner.classList.add("hidden");
    setText(banner, "");
    delete banner.dataset.mode;
    return;
  }
  setText(banner, message);
  banner.dataset.mode = mode;
  banner.classList.remove("hidden");
}

export function renderOperatorChromeInto(
  { body = null, toggle = null, hint = null } = {},
  { active = false, operatorMode = false } = {},
) {
  if (body?.dataset) {
    body.dataset.operatorChrome = active ? "on" : "off";
  }
  if (!toggle) {
    return;
  }
  toggle.setAttribute("aria-pressed", operatorMode ? "true" : "false");
  setText(toggle, operatorMode ? "Hide Technical Details" : "Show Technical Details");
  if (hint) {
    setText(hint, operatorMode ? OPERATOR_VISIBLE_HINT : OPERATOR_HIDDEN_HINT);
  }
}

export function renderShellChromeInto(
  {
    body = null,
    eyebrow = null,
    title = null,
    workspaceLabel = null,
    runtimeModeLabel = null,
  } = {},
  {
    activeView = "",
    beginnerSurface = false,
    eyebrow: eyebrowText = "",
    title: titleText = "",
    workspaceLabel: workspaceText = "",
    runtimeModeLabel: runtimeModeText = "",
  } = {},
) {
  if (body?.dataset) {
    body.dataset.activeView = activeView;
    body.dataset.beginnerSurface = beginnerSurface ? "true" : "false";
  }
  if (eyebrow) {
    setText(eyebrow, eyebrowText);
  }
  if (title) {
    setText(title, titleText);
  }
  if (workspaceLabel && workspaceText) {
    setText(workspaceLabel, workspaceText);
  }
  if (runtimeModeLabel && runtimeModeText) {
    setText(runtimeModeLabel, runtimeModeText);
  }
}

export function renderShellVisibilityInto({
  views = [],
  navButtons = [],
  moreShell = null,
  activeView = "",
} = {}) {
  for (const node of views || []) {
    node.classList.toggle("hidden", node.dataset.view !== activeView);
  }
  for (const button of navButtons || []) {
    button.classList.toggle("active", button.dataset.view === activeView);
  }
  if (!moreShell) {
    return;
  }
  const moreActive = MORE_NAV_ORDER.includes(activeView);
  moreShell.open = moreActive || moreShell.open;
  moreShell.classList.toggle("has-active-view", moreActive);
}
