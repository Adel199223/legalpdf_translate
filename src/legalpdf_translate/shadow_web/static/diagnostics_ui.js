import { formatDiagnosticValue } from "./diagnostics_presentation.js";

function qs(id) {
  return document.getElementById(id);
}

export function setDiagnostics(slot, value, { hint = "", open = false } = {}) {
  const pre = qs(`${slot}-diagnostics`);
  if (pre) {
    pre.textContent = formatDiagnosticValue(value);
  }
  const hintNode = qs(`${slot}-hint`);
  if (hintNode && hint) {
    hintNode.textContent = hint;
  }
  const details = qs(`${slot}-details`);
  if (details) {
    details.open = Boolean(open);
    if (open) {
      details.dataset.reveal = "true";
    } else {
      delete details.dataset.reveal;
    }
  }
}

export function setPanelStatus(slot, tone, message) {
  const panel = qs(`${slot}-status`);
  if (!panel) {
    return;
  }
  panel.textContent = message;
  if (tone) {
    panel.dataset.tone = tone;
  } else {
    delete panel.dataset.tone;
  }
}

export function setTopbarStatus(message, tone) {
  const panel = qs("topbar-status");
  if (!panel) {
    return;
  }
  panel.textContent = message;
  if (tone) {
    panel.dataset.tone = tone;
  } else {
    delete panel.dataset.tone;
  }
}

function diagnosticIsEmpty(slot) {
  const node = qs(`${slot}-diagnostics`);
  return Boolean(node && !node.textContent.trim());
}

export function populateIdleDiagnostics() {
  if (diagnosticIsEmpty("autofill")) {
    setDiagnostics(
      "autofill",
      { status: "idle", message: "No upload has been run yet." },
      { hint: "Metadata extraction details appear here after an upload.", open: false },
    );
  }
  if (diagnosticIsEmpty("form")) {
    setDiagnostics(
      "form",
      { status: "idle", message: "No save or export has been run yet." },
      { hint: "Save/export responses and validation details appear here.", open: false },
    );
  }
  if (diagnosticIsEmpty("profile")) {
    setDiagnostics(
      "profile",
      { status: "idle", message: "No profile save, delete, or import has been run yet." },
      { hint: "Profile saves, deletes, and import details appear here.", open: false },
    );
  }
  if (diagnosticIsEmpty("simulator")) {
    setDiagnostics(
      "simulator",
      { status: "idle", message: "No simulator run has been executed yet." },
      { hint: "Preview request payload, bridge endpoint, and readiness.", open: false },
    );
  }
}
