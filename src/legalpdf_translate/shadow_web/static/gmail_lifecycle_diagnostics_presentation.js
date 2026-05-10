export function buildGmailInitialDiagnosticsPresentations() {
  return [
    {
      slot: "gmail",
      payload: {
        status: "idle",
        message: "No Gmail action has run yet.",
      },
      presentation: {
        hint: "Exact-message load, attachment preview, and session preparation details appear here.",
        open: false,
      },
    },
    {
      slot: "gmail-session",
      payload: {
        status: "idle",
        message: "No Gmail batch or interpretation finalization has run yet.",
      },
      presentation: {
        hint: "Batch progression, staged attachments, export status, and Gmail draft details appear here.",
        open: false,
      },
    },
    {
      slot: "gmail-batch-finalize",
      payload: {
        status: "idle",
        message: "No Gmail batch finalization has run yet.",
      },
      presentation: {
        hint: "Final draft request details and honorários export diagnostics appear here.",
        open: false,
      },
    },
  ];
}

export function buildGmailReviewRefreshDiagnosticsPresentation() {
  return {
    hint: "Gmail review refreshed.",
    open: false,
  };
}

export function buildGmailSessionPreparedDiagnosticsPresentation() {
  return {
    hint: "Gmail session prepared.",
    open: false,
  };
}

export function buildGmailAttachmentSavedDiagnosticsPresentation() {
  return {
    hint: "Current Gmail attachment saved as a case record.",
    open: false,
  };
}

export function buildGmailReviewResetDiagnosticsPresentation() {
  return {
    hint: "Gmail review reset.",
    open: false,
  };
}
