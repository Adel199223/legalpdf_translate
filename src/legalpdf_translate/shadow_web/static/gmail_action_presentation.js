export function buildGmailPrepareActionPresentation({
  workflow = {},
  loadResult = null,
  selections = [],
  runtimeGuard = {},
} = {}) {
  let label = String(workflow.prepareLabel || "");
  let disabled = false;

  if (!loadResult?.ok || !loadResult?.message) {
    label = "Load a Gmail message first";
    disabled = true;
  } else if (!selections.length) {
    label = String(workflow.emptySelectionLabel || "");
    disabled = true;
  } else if (runtimeGuard.blocked) {
    label = "Restart live Gmail runtime to continue";
    disabled = true;
  }

  return {
    label,
    disabled,
    title: runtimeGuard.blocked ? String(runtimeGuard.message || "") : "",
  };
}
