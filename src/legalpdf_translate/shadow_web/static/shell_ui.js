import { MORE_NAV_ORDER, buildNavigationGroups } from "./shell_presentation.js";
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
