import { runWithBusy } from "./busy_ui.js";

function normalizeButtonIds(buttonIds) {
  if (typeof buttonIds === "string") {
    return buttonIds ? [buttonIds] : [];
  }
  return Array.isArray(buttonIds) ? buttonIds.filter((id) => typeof id === "string" && id) : [];
}

function normalizeBusyLabels(buttonIds, busyLabels, busyLabel) {
  if (busyLabels && typeof busyLabels === "object") {
    return busyLabels;
  }
  const label = String(busyLabel || "");
  if (!label) {
    return {};
  }
  return Object.fromEntries(buttonIds.map((id) => [id, label]));
}

function normalizeGuardIds(guardIds) {
  if (typeof guardIds === "string") {
    return guardIds ? [guardIds] : [];
  }
  return Array.isArray(guardIds) ? guardIds.filter((id) => typeof id === "string" && id) : null;
}

function resolveFailureFeedback(error, failureFeedback) {
  if (typeof failureFeedback === "function") {
    return failureFeedback(error) || {};
  }
  return failureFeedback || {};
}

export async function runGmailBusyAction({
  buttonIds = [],
  busyLabels = null,
  busyLabel = "",
  guardIds = null,
  action = null,
  failureFeedback = {},
  applyFailureFeedback = null,
  onError = null,
  afterError = null,
  runWithBusyImpl = runWithBusy,
} = {}) {
  const normalizedButtonIds = normalizeButtonIds(buttonIds);
  const normalizedBusyLabels = normalizeBusyLabels(normalizedButtonIds, busyLabels, busyLabel);
  const normalizedGuardIds = normalizeGuardIds(guardIds);
  const busyOptions = normalizedGuardIds ? { guardIds: normalizedGuardIds } : {};
  const busyRunner = typeof runWithBusyImpl === "function" ? runWithBusyImpl : runWithBusy;
  if (typeof onError !== "function") {
    onError = async () => {};
  }
  if (typeof afterError !== "function") {
    afterError = async () => {};
  }

  return await busyRunner(normalizedButtonIds, normalizedBusyLabels, async () => {
    try {
      return typeof action === "function" ? await action() : undefined;
    } catch (error) {
      await onError(error);
      if (typeof applyFailureFeedback === "function") {
        applyFailureFeedback(error, resolveFailureFeedback(error, failureFeedback));
      }
      await afterError(error);
      return undefined;
    }
  }, busyOptions);
}
