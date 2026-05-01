import {
  appendResultGridItem,
  createResultHeader,
} from "./result_card_ui.js";
import {
  clearNode,
  createTextElement,
} from "./safe_rendering.js";

export function renderRecoveryResultInto(container, details = {}) {
  if (!container) {
    return;
  }
  container.classList.remove("empty-state");
  clearNode(container);
  container.appendChild(createResultHeader({
    title: details.title,
    label: "Unavailable",
    tone: "bad",
  }));
  const grid = document.createElement("div");
  grid.className = "result-grid";
  appendResultGridItem(grid, "Listener", `${details.host}:${details.port}`, { className: "word-break" });
  appendResultGridItem(grid, "Recommended URL", details.recommendedUrl, { className: "word-break" });
  appendResultGridItem(grid, "Launcher", details.launcherCommand, { className: "word-break" });
  container.appendChild(grid);

  const recovery = document.createElement("div");
  recovery.appendChild(createTextElement("h3", "Recovery"));
  const list = document.createElement("ul");
  for (const step of details.recoverySteps || []) {
    list.appendChild(createTextElement("li", step));
  }
  recovery.appendChild(list);
  container.appendChild(recovery);
}
