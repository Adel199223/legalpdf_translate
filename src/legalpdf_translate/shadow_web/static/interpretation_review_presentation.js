import {
  deriveInterpretationWorkspaceMode,
} from "./interpretation_review_state.js";

const INTERPRETATION_DISCLOSURE_COPY = Object.freeze({
  serviceSame: "Using the case details",
  serviceCustom: "Custom service details ready",
  textDefault: "Optional wording and filename",
  textCustom: "Custom document options ready",
  recipientDefault: "Recipient is filled automatically",
  recipientCustom: "Custom recipient text ready",
  amountsDefault: "Optional amounts and internal totals",
  amountsTouched: "Amounts and totals ready",
  transportDisabledHint: "Transport sentence is turned off for this document.",
});

function hasMeaningfulInterpretationValue(value) {
  const normalized = String(value ?? "").trim();
  return Boolean(normalized && normalized !== "0" && normalized !== "0.0" && normalized !== "0.00");
}

function normalizeWorkspaceMode(value) {
  const normalized = String(value || "").trim();
  const allowed = new Set(["blank", "manual_seed", "gmail_review", "gmail_completed"]);
  return allowed.has(normalized) ? normalized : "blank";
}

function hasInterpretationSeedData(snapshot = {}) {
  return Boolean(
    hasMeaningfulInterpretationValue(snapshot?.rowId)
    || hasMeaningfulInterpretationValue(snapshot?.caseNumber)
    || hasMeaningfulInterpretationValue(snapshot?.courtEmail)
    || hasMeaningfulInterpretationValue(snapshot?.caseEntity)
    || hasMeaningfulInterpretationValue(snapshot?.caseCity)
    || hasMeaningfulInterpretationValue(snapshot?.serviceDate)
    || hasMeaningfulInterpretationValue(snapshot?.travelKmOutbound)
    || hasMeaningfulInterpretationValue(snapshot?.pages)
    || hasMeaningfulInterpretationValue(snapshot?.wordCount)
  );
}

function normalizedPayloadObject(value) {
  return value && typeof value === "object" ? value : {};
}

export function deriveInterpretationDisclosurePresentation({
  serviceSame = true,
  textCustomized = false,
  recipientOverride = "",
  amountsTouched = false,
  includeTransport = true,
} = {}) {
  const hasRecipientOverride = Boolean(String(recipientOverride ?? "").trim());
  return {
    serviceSummary: serviceSame
      ? INTERPRETATION_DISCLOSURE_COPY.serviceSame
      : INTERPRETATION_DISCLOSURE_COPY.serviceCustom,
    textSummary: textCustomized
      ? INTERPRETATION_DISCLOSURE_COPY.textCustom
      : INTERPRETATION_DISCLOSURE_COPY.textDefault,
    recipientSummary: hasRecipientOverride
      ? INTERPRETATION_DISCLOSURE_COPY.recipientCustom
      : INTERPRETATION_DISCLOSURE_COPY.recipientDefault,
    amountsSummary: amountsTouched
      ? INTERPRETATION_DISCLOSURE_COPY.amountsTouched
      : INTERPRETATION_DISCLOSURE_COPY.amountsDefault,
    transportDisabledHint: includeTransport
      ? ""
      : INTERPRETATION_DISCLOSURE_COPY.transportDisabledHint,
  };
}

export function deriveInterpretationReviewPresentation({
  snapshot = {},
  activeSession = null,
  workspaceMode = "",
  hasReviewData,
  completionPayload = null,
} = {}) {
  const resolvedMode = normalizeWorkspaceMode(
    workspaceMode || deriveInterpretationWorkspaceMode({
      snapshot,
      activeSession,
      hasCompletionPayload: Boolean(completionPayload),
    })
  );
  const gmailMode = resolvedMode === "gmail_review" || resolvedMode === "gmail_completed";
  const reviewDataReady = typeof hasReviewData === "boolean" ? hasReviewData : hasInterpretationSeedData(snapshot);
  const rowLoaded = hasMeaningfulInterpretationValue(snapshot?.rowId);
  const disclosurePresentation = deriveInterpretationDisclosurePresentation();

  const sessionPrimaryLabel = resolvedMode === "gmail_completed" ? "View final result" : "Review details";
  const homeStatus = resolvedMode === "gmail_completed"
    ? "Final files are ready. Open the review to check the Gmail reply details."
    : "Review the notice details, then create the Gmail reply.";
  const homeResultTitle = resolvedMode === "gmail_completed"
    ? "Gmail reply ready"
    : "Gmail interpretation ready";

  let drawerStatus = "Upload a notification or start a blank request to begin.";
  let summaryTitle = "Upload a notification or start a blank request to begin.";
  let summarySubtitle = "Recover the case details first, or start a blank request if you need to enter them manually.";
  if (resolvedMode === "gmail_completed") {
    drawerStatus = "The Gmail reply and exported files are ready.";
    summaryTitle = "Gmail reply created.";
    summarySubtitle = "The Gmail reply and exported files are ready.";
  } else if (resolvedMode === "gmail_review") {
    drawerStatus = "Check the notice details, then create the Gmail reply.";
    summaryTitle = "Notice details are ready to review.";
    summarySubtitle = "Check the notice details, then create the Gmail reply.";
  } else if (reviewDataReady) {
    drawerStatus = "Check the recovered details, then save the case record or create the fee-request document.";
    summaryTitle = rowLoaded ? "Saved case record loaded." : "Recovered case details are ready.";
    summarySubtitle = rowLoaded
      ? "Review the fields below and save any edits."
      : "Check the recovered details, then save the case record or create the fee-request document.";
  }

  return {
    workspaceMode: resolvedMode,
    gmailMode,
    reviewDataReady,
    rowLoaded,
    home: {
      status: homeStatus,
      resultTitle: homeResultTitle,
      resultEmpty: "A Gmail interpretation summary appears here when the notice is ready.",
    },
    reviewHome: {
      emptyState: "Upload a notification PDF or screenshot to recover the case details, or start a blank request.",
      title: rowLoaded ? "Saved case record loaded." : "Recovered case details are ready.",
      subtitle: rowLoaded
        ? "Review the fields below and save any edits."
        : gmailMode
          ? "Check the notice details, then create the Gmail reply."
          : "Check the recovered details, then save the case record or create the fee-request document.",
    },
    drawer: {
      title: "Review Interpretation Request",
      status: drawerStatus,
      summaryEmpty: "Upload a notification or start a blank request to begin.",
      summaryTitle,
      summarySubtitle,
      contextTitle: "Create the Gmail reply after review.",
      contextCopy: "Check the notice details, then create the Gmail reply.",
      gmailResultEmpty: "Gmail reply details will appear here after the final step.",
      detailsSummaryOpen: "Case details and document options are open",
      detailsSummaryClosed: "Review details stay collapsed until you reopen them",
    },
    sections: {
      caseDetailsTitle: "Case details",
      serviceTitle: "Service details",
      serviceSummary: disclosurePresentation.serviceSummary,
      textTitle: "Document text",
      textSummary: disclosurePresentation.textSummary,
      recipientTitle: "Recipient",
      recipientSummary: disclosurePresentation.recipientSummary,
      amountsTitle: "Amounts (EUR)",
      amountsSummary: disclosurePresentation.amountsSummary,
      outputFilenameLabel: "Document filename",
      outputFilenamePlaceholder: "Optional filename for the fee-request DOCX",
      recipientBlockLabel: "Recipient text (optional override)",
      recipientBlockHint: "Used only for the current document. It is not saved to the case record.",
    },
    actions: {
      openReview: "Review details",
      startBlank: "Start blank request",
      refreshHistory: "Refresh history",
      sessionPrimary: sessionPrimaryLabel,
      sessionSecondary: "Review Gmail message",
      saveRow: "Save case record",
      export: "Create fee-request document",
      finalizeGmail: "Create Gmail reply",
    },
    export: {
      title: "Fee-request document",
      emptyState: "The generated DOCX/PDF will appear here after you create the document.",
      readyTitle: "The fee-request document is ready.",
      localOnlyTitle: "The DOCX is ready, but the PDF is only available locally.",
      failedTitle: "The fee-request document could not be created.",
      readyLabel: "Ready",
      localOnlyLabel: "Local only",
      failedLabel: "Needs review",
      pdfReadyLabel: "Ready",
    },
    gmailResult: {
      createdTitle: "Gmail reply created.",
      createdLabel: "Gmail reply created",
      localOnlyTitle: "Final files are ready.",
      localOnlyLabel: "Final files are ready",
      warningTitle: "Gmail reply needs review.",
      warningLabel: "Gmail reply needs review",
    },
  };
}

export function buildInterpretationSessionChip({
  session = null,
  workspaceMode = "",
  completionPayload = null,
  presentation = null,
} = {}) {
  const mode = normalizeWorkspaceMode(workspaceMode);
  const resolvedPresentation = presentation && typeof presentation === "object"
    ? presentation
    : deriveInterpretationReviewPresentation({
      activeSession: session,
      workspaceMode: mode,
      completionPayload,
    });
  const gmailResult = resolvedPresentation?.gmailResult
    || deriveInterpretationReviewPresentation().gmailResult;
  const status = String(session?.status || "").trim();
  if (mode === "gmail_completed") {
    const completionStatus = String(completionPayload?.status || "").trim();
    if (completionStatus === "ok") {
      return { tone: "ok", label: gmailResult.createdLabel };
    }
    if (completionStatus === "local_only") {
      return { tone: "warn", label: gmailResult.localOnlyLabel };
    }
    if (completionStatus === "draft_unavailable") {
      return { tone: "warn", label: gmailResult.warningLabel };
    }
    if (completionStatus) {
      return { tone: "bad", label: gmailResult.warningLabel };
    }
    if (session?.draft_created || status === "draft_ready") {
      return { tone: "ok", label: gmailResult.createdLabel };
    }
    if (String(session?.draft_failure_reason || "").trim() || status === "draft_failed") {
      return { tone: "bad", label: gmailResult.warningLabel };
    }
    return { tone: "info", label: gmailResult.localOnlyLabel };
  }
  if (status) {
    return { tone: "info", label: status.replaceAll("_", " ") };
  }
  return { tone: "info", label: "Ready" };
}

export function buildInterpretationCompletionCardPresentation({
  activeSession = null,
  workspaceMode = "",
  completionPayload = null,
  presentation = null,
} = {}) {
  const mode = normalizeWorkspaceMode(workspaceMode);
  const completed = mode === "gmail_completed";
  const chip = buildInterpretationSessionChip({
    session: activeSession,
    workspaceMode: mode,
    completionPayload,
    presentation,
  });
  if (!completed) {
    return {
      completed,
      title: "",
      message: "",
      chip,
      docxPath: "",
      pdfPath: "",
    };
  }

  const resolvedPresentation = presentation && typeof presentation === "object"
    ? presentation
    : deriveInterpretationReviewPresentation({
      activeSession,
      workspaceMode: mode,
      completionPayload,
    });
  const gmailResult = resolvedPresentation?.gmailResult
    || deriveInterpretationReviewPresentation().gmailResult;
  const payload = normalizedPayloadObject(completionPayload?.normalized_payload);
  const completionStatus = String(completionPayload?.status || "").trim();
  const sessionStatus = String(activeSession?.status || "").trim();
  const sessionFailureReason = String(activeSession?.draft_failure_reason || "").trim();
  const title = (completionStatus === "ok" || activeSession?.draft_created || sessionStatus === "draft_ready")
    ? gmailResult.createdTitle
    : completionStatus === "local_only"
      ? gmailResult.localOnlyTitle
      : (completionStatus === "draft_unavailable" || sessionFailureReason || sessionStatus === "draft_failed")
        ? gmailResult.warningTitle
        : gmailResult.localOnlyTitle;
  const message = payload.gmail_draft_result?.message
    || payload.draft_prereqs?.message
    || activeSession?.draft_failure_reason
    || title;
  const pdfPath = String(payload.pdf_path || payload.pdfPath || activeSession?.pdf_export?.pdf_path || activeSession?.pdf_export?.pdfPath || "").trim();
  const docxPath = String(payload.docx_path || payload.docxPath || "").trim();

  return {
    completed,
    title,
    message,
    chip,
    docxPath,
    pdfPath,
  };
}

export function deriveInterpretationDrawerLayout({
  workspaceMode = "blank",
  activeSession = null,
  serviceSame = true,
  validationField = "",
} = {}) {
  const normalizedMode = normalizeWorkspaceMode(workspaceMode);
  const gmailMode = normalizedMode === "gmail_review" || normalizedMode === "gmail_completed";
  const serviceValidation = ["service_entity", "service_city", "service_date"].includes(String(validationField || "").trim());
  return {
    workspaceMode: normalizedMode,
    gmailMode,
    sections: {
      serviceOpen: !serviceSame || serviceValidation,
      textOpen: true,
      recipientOpen: false,
      amountsOpen: false,
    },
    actions: {
      showFinalizeGmail: activeSession?.kind === "interpretation" && normalizedMode !== "gmail_completed",
      showGenerateDocxPdf: !gmailMode,
      showSaveRow: !gmailMode,
      showNewBlank: !gmailMode,
      showFooterClose: !gmailMode,
    },
  };
}
