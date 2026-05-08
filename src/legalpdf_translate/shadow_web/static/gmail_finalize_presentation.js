function shortOutputFolderLabel(value) {
  const cleaned = String(value ?? "").trim();
  if (!cleaned) {
    return "Use default folder";
  }
  const normalized = cleaned.replace(/[\\/]+$/, "");
  const parts = normalized.split(/[\\/]/).filter(Boolean);
  return parts.at(-1) || cleaned;
}

function gmailBatchStateLabel(finalizationState, session) {
  return ({
    ready_to_finalize: "Ready",
    blocked_word_pdf_export: "Blocked",
    finalizing: "Finalizing",
    local_artifacts_ready: "Local only",
    draft_ready: "Draft ready",
    draft_failed: "Draft failed",
  })[finalizationState] || session?.status || "confirmed";
}

function gmailBatchSummaryCard({
  session,
  recoveredOnly,
  finalizationState,
  outputFolder,
  provenance,
  stateLabel,
}) {
  const confirmedItems = session.confirmed_items || [];
  return {
    title: session.message?.subject || "Gmail batch ready to finalize.",
    message: recoveredOnly
      ? "Recovered Gmail reply details from the last saved attachment set are available here."
      : `${confirmedItems.length} saved attachment(s) are ready for the Gmail reply.`,
    label: stateLabel,
    tone: finalizationState === "blocked_word_pdf_export" || finalizationState === "local_artifacts_ready"
      ? "warn"
      : finalizationState === "draft_failed"
        ? "bad"
        : "ok",
    gridItems: [
      { label: "Target Language", value: session.selected_target_lang || "?" },
      { label: "Confirmed Rows", value: confirmedItems.length },
      {
        label: "Output Folder",
        value: shortOutputFolderLabel(outputFolder),
        titleValue: outputFolder,
      },
      { label: "Build Provenance", value: provenance.label, className: "word-break" },
    ],
  };
}

export function buildGmailBatchFinalizeSurfacePresentation({
  session = null,
  recoveredOnly = false,
  preflight = null,
  payload = null,
  finalizationState = "",
  preflightInFlight = false,
  outputFolder = "Use default folder",
  provenance = {},
} = {}) {
  const available = Boolean(session?.kind === "translation" && session?.completed);
  const normalized = payload?.normalized_payload || {};
  const retryAvailable = Boolean(normalized.retry_available);
  const provenancePayload = { label: "", ...provenance };
  const stateLabel = gmailBatchStateLabel(finalizationState, session);
  const retryLabel = "Try Gmail reply again";
  const defaultButtonLabel = payload?.status === "ok"
    ? "Finalized"
    : retryAvailable
      ? retryLabel
      : "Create Gmail reply";
  const defaultButton = {
    label: defaultButtonLabel,
    disabled: !available,
    hidden: false,
  };
  const surface = (card, options = {}) => ({
    button: defaultButton,
    ...card,
    closeDrawer: Boolean(options.closeDrawer),
  });

  if (!available) {
    return surface({
      statusText: "After every selected attachment is saved, create the Gmail reply with the final files.",
      summary: {
        empty: true,
        text: "Finish every Gmail attachment first to open the final reply step.",
      },
      result: {
        empty: true,
        text: "Gmail reply details will appear here after the final step.",
      },
    }, { closeDrawer: true });
  }

  const summaryCard = gmailBatchSummaryCard({
    session,
    recoveredOnly,
    finalizationState,
    outputFolder,
    provenance: provenancePayload,
    stateLabel,
  });

  if (recoveredOnly) {
    const recoveredStatusText = finalizationState === "draft_ready"
      ? "These recovered Gmail reply details are available to review. Start a new Gmail message normally if you need a fresh reply, or generate the finalization report here if you need the earlier files."
      : "These recovered Gmail reply details are available for review and report generation only.";
    return surface({
      button: {
        ...defaultButton,
        disabled: true,
        hidden: true,
      },
      statusText: recoveredStatusText,
      summary: summaryCard,
      result: {
        title: recoveredStatusText,
        message: session.actual_honorarios_path || session.actual_honorarios_pdf_path || session.session_report_path || "Recovered Gmail reply files are available.",
        label: stateLabel || "Recovered",
        tone: finalizationState === "draft_ready" ? "ok" : "info",
        gridItems: [
          { label: "DOCX", value: session.actual_honorarios_path || "Unavailable", className: "word-break" },
          { label: "PDF", value: session.actual_honorarios_pdf_path || "Unavailable", className: "word-break" },
          { label: "Session Report", value: session.session_report_path || "Unavailable", className: "word-break" },
          { label: "Recovery Source", value: session.restored_from_report ? "Recovered from an earlier Gmail reply step" : "Recovered" },
        ],
      },
    });
  }

  if (preflightInFlight && !payload) {
    return surface({
      button: {
        ...defaultButton,
        disabled: true,
      },
      statusText: "Checking the Word PDF export step before the Gmail reply is created.",
      summary: summaryCard,
      result: {
        empty: true,
        text: "Checking whether the final Word PDF step is ready...",
      },
    });
  }

  if (!payload && preflight && !preflight.finalization_ready) {
    return surface({
      button: {
        ...defaultButton,
        disabled: true,
      },
      statusText: "The final Word PDF step is blocked. Review the details here before you try again.",
      summary: summaryCard,
      result: {
        title: preflight.message || "Word PDF export is unavailable.",
        message: preflight.details || "The Word launch probe and export canary are shown below.",
        label: "Blocked",
        tone: "warn",
        gridItems: [
          { label: "Launch Preflight", value: preflight.launch_preflight?.message || "Unavailable" },
          { label: "Export Canary", value: preflight.export_canary?.message || "Unavailable" },
          { label: "Failure Phase", value: preflight.failure_phase || preflight.export_canary?.failure_phase || "Unknown" },
        ],
      },
    });
  }

  if (!payload && ["local_artifacts_ready", "draft_failed", "draft_ready"].includes(finalizationState)) {
    const draftCopy = finalizationState === "draft_ready"
      ? "The Gmail draft is ready for this saved attachment set."
      : session.draft_failure_reason || "The previous Gmail finalization attempt stayed recoverable in this workspace.";
    const draftStatusText = finalizationState === "draft_ready"
      ? "The Gmail reply is ready to review."
      : finalizationState === "draft_failed"
        ? "The final DOCX files were created, but the Gmail reply step failed. You can try again from here."
        : "The final DOCX files were created locally, but the Gmail reply step stayed unavailable. You can try again from here.";
    const showRetryAction = finalizationState !== "draft_ready";
    return surface({
      button: {
        ...defaultButton,
        label: showRetryAction ? retryLabel : defaultButtonLabel,
        disabled: !showRetryAction || (preflight && !preflight.finalization_ready),
        hidden: !showRetryAction,
      },
      statusText: draftStatusText,
      summary: summaryCard,
      result: {
        title: draftStatusText,
        message: session.actual_honorarios_path || session.actual_honorarios_pdf_path || draftCopy,
        label: stateLabel,
        tone: finalizationState === "draft_ready" ? "ok" : finalizationState === "draft_failed" ? "bad" : "warn",
        gridItems: [
          { label: "DOCX", value: session.actual_honorarios_path || "Unavailable", className: "word-break" },
          { label: "PDF", value: session.actual_honorarios_pdf_path || "Unavailable", className: "word-break" },
          { label: "Draft", value: draftCopy },
          { label: "Launch Preflight", value: preflight?.launch_preflight?.message || "Unavailable" },
          { label: "Export Canary", value: preflight?.export_canary?.message || "Unavailable" },
          { label: "Retry", value: showRetryAction ? "You can try again from this drawer." : "No retry required." },
          { label: "Build Provenance", value: provenancePayload.label, className: "word-break" },
        ],
      },
    });
  }

  if (!payload && preflight?.finalization_ready) {
    return surface({
      button: {
        ...defaultButton,
        disabled: false,
      },
      statusText: "Every selected Gmail attachment is saved. You can create the Gmail reply when you are ready.",
      summary: summaryCard,
      result: {
        title: "Word PDF export is ready.",
        message: "The same Word export path used for the Gmail reply passed a canary export on this machine.",
        label: "Ready",
        tone: "ok",
        gridItems: [
          { label: "Launch Preflight", value: preflight.launch_preflight?.message || "Ready" },
          { label: "Export Canary", value: preflight.export_canary?.message || "Ready" },
          { label: "Checked", value: preflight.last_checked_at || "Just now" },
        ],
      },
    });
  }

  if (!payload) {
    return surface({
      button: {
        ...defaultButton,
        disabled: true,
      },
      statusText: "The Gmail reply will unlock here after the Word PDF readiness check finishes.",
      summary: summaryCard,
      result: {
        empty: true,
        text: "Create the Gmail reply after the Word PDF readiness check finishes.",
      },
    });
  }

  const draftStatus = normalized.gmail_draft_result?.ok
    ? "Draft ready"
    : finalizationState === "local_artifacts_ready" || payload.status === "local_only"
      ? "Local only"
      : payload.status === "draft_unavailable"
        ? "Draft unavailable"
        : finalizationState === "draft_failed" || payload.status === "draft_failed"
          ? "Draft failed"
          : "Ready";
  const tone = payload.status === "ok" ? "ok" : finalizationState === "draft_failed" ? "bad" : "warn";
  const payloadStatusText = payload.status === "ok"
    ? "The Gmail reply is ready."
    : finalizationState === "blocked_word_pdf_export"
      ? "The final Word PDF step is blocked."
      : payload.status === "local_only"
        ? "The final DOCX files were created locally, but the Gmail reply step stayed unavailable."
        : finalizationState === "draft_failed"
          ? "The final DOCX files were created, but the Gmail reply step failed. You can try again from here."
          : "The Gmail reply step completed with warnings. Review the details here.";
  return surface({
    button: {
      ...defaultButton,
      disabled: preflightInFlight
        || payload.status === "ok"
        || (preflight && !preflight.finalization_ready),
      hidden: payload.status === "ok",
    },
    statusText: payloadStatusText,
    summary: summaryCard,
    result: {
      title: payloadStatusText,
      message: normalized.docx_path || normalized.pdf_path || "Finalization output is available.",
      label: draftStatus,
      tone: tone === "ok" ? "ok" : tone === "warn" ? "warn" : "bad",
      gridItems: [
        { label: "DOCX", value: normalized.docx_path || "Unavailable", className: "word-break" },
        { label: "PDF", value: normalized.pdf_path || "Unavailable", className: "word-break" },
        { label: "Draft", value: normalized.gmail_draft_result?.message || normalized.draft_prereqs?.message || draftStatus },
        { label: "Launch Preflight", value: preflight?.launch_preflight?.message || "Unavailable" },
        { label: "Export Canary", value: preflight?.export_canary?.message || "Unavailable" },
        { label: "Retry", value: retryAvailable ? "You can try again from this drawer." : "No retry required." },
        { label: "Build Provenance", value: provenancePayload.label, className: "word-break" },
      ],
    },
  });
}
