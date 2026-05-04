import { clearNode, createEmptyState, createTextElement } from "./safe_rendering.js";

function appendRunDirMeta(container, item = {}) {
  const meta = document.createElement("div");
  meta.className = "history-meta";
  for (const bit of [
    item.modified_at_iso || "",
    item.has_run_summary ? "summary" : "",
    item.has_run_state ? "state" : "",
    item.has_calibration_report ? "calibration" : "",
  ]) {
    if (bit) {
      meta.appendChild(createTextElement("small", bit));
    }
  }
  container.appendChild(meta);
  return meta;
}

export function renderLatestRunDirsInto(
  container,
  items = [],
  { onUseForReport, onAddToBuilder } = {},
) {
  if (!container) {
    return undefined;
  }
  const runDirs = Array.isArray(items) ? items : [];
  clearNode(container);
  if (!runDirs.length) {
    container.appendChild(createEmptyState("No recent run folders are available yet."));
    return container;
  }
  for (const item of runDirs) {
    const article = document.createElement("article");
    article.className = "history-item";

    const left = document.createElement("div");
    left.appendChild(createTextElement("strong", item?.name || "run"));
    left.appendChild(createTextElement("p", item?.run_dir || "", "word-break"));
    appendRunDirMeta(left, item || {});

    const actions = document.createElement("div");
    actions.className = "panel-actions";
    const useForReport = document.createElement("button");
    useForReport.type = "button";
    useForReport.textContent = "Use for run report";
    useForReport.addEventListener("click", () => onUseForReport?.(item));
    const addToBuilder = document.createElement("button");
    addToBuilder.type = "button";
    addToBuilder.textContent = "Add to builder";
    addToBuilder.addEventListener("click", () => onAddToBuilder?.(item));
    actions.appendChild(useForReport);
    actions.appendChild(addToBuilder);

    article.appendChild(left);
    article.appendChild(actions);
    container.appendChild(article);
  }
  return container;
}
