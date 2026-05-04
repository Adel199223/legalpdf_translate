import { setText } from "./safe_rendering.js";

export function renderTranslationOutputSummaryInto(nodes = {}, summary = {}) {
  const { label, copy, path } = nodes || {};
  if (!label || !copy || !path) {
    return undefined;
  }

  setText(label, summary.label || "");
  setText(copy, summary.copy || "");
  setText(path, summary.path || "");
  return label;
}
