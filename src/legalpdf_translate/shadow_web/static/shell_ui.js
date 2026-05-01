import { MORE_NAV_ORDER, buildNavigationGroups } from "./shell_presentation.js";
import { clearNode, createTextElement } from "./safe_rendering.js";

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
