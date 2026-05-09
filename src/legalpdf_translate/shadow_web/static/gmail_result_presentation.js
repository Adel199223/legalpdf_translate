export function buildGmailMessageResultPresentation({
  loadResult = null,
  defaults = {},
  pendingContext = {},
  pendingStatus = "",
  pendingWarming = false,
  workflow = {},
} = {}) {
  if (!loadResult) {
    const resolvedContext = {
      message_id: defaults.message_id || pendingContext.message_id || "",
      thread_id: defaults.thread_id || pendingContext.thread_id || "",
      subject: defaults.subject || pendingContext.subject || "",
      account_email: defaults.account_email || pendingContext.account_email || "",
    };
    const hasContext = Boolean(
      resolvedContext.message_id
      || resolvedContext.thread_id
      || resolvedContext.subject
      || resolvedContext.account_email,
    );
    if (!hasContext) {
      return {
        empty: true,
        emptyText: "Open this from Gmail or load a message manually from details.",
        detailsHint: "Manual message load and output overrides stay here unless Gmail needs help finding the message.",
      };
    }
    return {
      title: pendingStatus === "failed"
        ? "Gmail message could not finish loading."
        : pendingWarming
          ? "Gmail message is loading."
          : "Gmail message found.",
      message: resolvedContext.subject || "Subject unavailable",
      label: pendingStatus === "failed"
        ? "Needs attention"
        : pendingWarming
          ? "Loading"
          : "Ready soon",
      tone: pendingStatus === "failed" ? "bad" : "info",
      detailsHint: pendingWarming
        ? "The message is still loading; open these details only if Gmail needs manual help."
        : "Detected Gmail details are ready; open these details only if you need manual recovery.",
      gridItems: [
        {
          label: "Gmail account",
          value: resolvedContext.account_email || "Unavailable",
          className: "word-break",
        },
        {
          label: "Workflow",
          value: workflow.label,
        },
      ],
    };
  }

  const message = loadResult.message || {};
  const attachmentCount = (message.attachments || []).length;
  return {
    title: loadResult.ok ? "Gmail message ready to review." : "Gmail message needs attention.",
    message: message.subject || "No subject",
    label: loadResult.ok ? "Ready" : "Needs attention",
    tone: loadResult.ok
      ? "ok"
      : loadResult.classification === "unavailable"
        ? "warn"
        : "bad",
    detailsHint: "Exact IDs and output overrides stay here unless you need manual recovery or troubleshooting.",
    gridItems: [
      {
        label: "From",
        value: message.from_header || "Unavailable",
        className: "word-break",
      },
      {
        label: "Gmail account",
        value: message.account_email || "Unavailable",
        className: "word-break",
      },
      {
        label: "Supported attachments",
        value: attachmentCount,
      },
      {
        label: "Workflow",
        value: workflow.label,
      },
    ],
  };
}

export function buildGmailReviewSummaryPresentation({
  loadResult = null,
  workflow = {},
  selectedCount = 0,
  outputFolder = "",
} = {}) {
  if (!loadResult?.ok || !loadResult?.message) {
    return {
      empty: true,
      emptyText: "Load this Gmail message to choose attachments.",
    };
  }

  const message = loadResult.message;
  const attachments = Array.isArray(message.attachments) ? message.attachments : [];
  return {
    subject: message.subject || "No subject",
    reviewStatus: workflow.reviewStatus || "",
    workflowLabel: workflow.label || "",
    attachmentCount: attachments.length,
    chipLabel: selectedCount ? `${selectedCount} selected` : "Review ready",
    chipTone: selectedCount ? "ok" : "info",
    gridItems: [
      {
        label: "From",
        value: message.from_header || "Unavailable",
        className: "word-break",
      },
      {
        label: "Gmail account",
        value: message.account_email || "Unavailable",
        className: "word-break",
      },
      {
        label: "Exact message ID",
        value: message.message_id || "Unavailable",
        className: "word-break",
      },
      {
        label: "Exact thread ID",
        value: message.thread_id || "Unavailable",
        className: "word-break",
      },
      {
        label: "Save output in",
        value: outputFolder || "Use default folder",
        className: "word-break",
      },
    ],
  };
}
