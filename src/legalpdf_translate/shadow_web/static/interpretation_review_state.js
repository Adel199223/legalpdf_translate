export function normalizeCityName(value) {
  return String(value ?? "").normalize("NFC").replace(/\s+/g, " ").trim();
}

function dedupeCities(values) {
  const seen = new Set();
  const ordered = [];
  for (const value of values || []) {
    const city = normalizeCityName(value);
    if (!city) {
      continue;
    }
    const key = city.toLocaleLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    ordered.push(city);
  }
  return ordered;
}

export function resolveKnownCity(value, availableCities = []) {
  const target = normalizeCityName(value);
  if (!target) {
    return "";
  }
  for (const city of availableCities || []) {
    const resolved = normalizeCityName(city);
    if (resolved && resolved.toLocaleLowerCase() === target.toLocaleLowerCase()) {
      return resolved;
    }
  }
  return "";
}

export function buildInterpretationReference(rawReference = {}, profiles = [], selectedProfileId = "") {
  const baseAvailableCities = dedupeCities(rawReference?.available_cities || rawReference?.availableCities || []);
  const baseDistances = { ...(rawReference?.travel_distances_by_city || rawReference?.travelDistancesByCity || {}) };
  const selectedProfile = (profiles || []).find((profile) => String(profile?.id || "") === String(selectedProfileId || ""))
    || (profiles || []).find((profile) => String(profile?.id || "") === String(rawReference?.profile_id || rawReference?.profileId || ""))
    || null;
  const profileDistances = selectedProfile?.travel_distances_by_city || {};
  const availableCities = dedupeCities([
    ...baseAvailableCities,
    ...Object.keys(baseDistances),
    ...Object.keys(profileDistances),
  ]);
  const knownDistances = {};
  for (const city of availableCities) {
    const profileValue = profileDistances[city];
    const baseValue = baseDistances[city];
    const directProfileKey = Object.keys(profileDistances).find((key) => normalizeCityName(key).toLocaleLowerCase() === city.toLocaleLowerCase());
    const directBaseKey = Object.keys(baseDistances).find((key) => normalizeCityName(key).toLocaleLowerCase() === city.toLocaleLowerCase());
    const resolvedValue = directProfileKey ? profileDistances[directProfileKey] : (directBaseKey ? baseDistances[directBaseKey] : (profileValue ?? baseValue));
    const numeric = Number(resolvedValue);
    if (Number.isFinite(numeric) && numeric > 0) {
      knownDistances[city] = numeric;
    }
  }
  return {
    profileId: String(selectedProfile?.id || rawReference?.profile_id || rawReference?.profileId || ""),
    travelOriginLabel: String(
      selectedProfile?.travel_origin_label
      || rawReference?.travel_origin_label
      || rawReference?.travelOriginLabel
      || ""
    ).trim(),
    availableCities,
    travelDistancesByCity: knownDistances,
  };
}

function parsePositiveDistance(rawValue) {
  const cleaned = String(rawValue ?? "").trim().replace(",", ".");
  if (!cleaned) {
    return { state: "blank", value: null };
  }
  const numeric = Number(cleaned);
  if (!Number.isFinite(numeric)) {
    return { state: "invalid", value: null };
  }
  if (numeric <= 0) {
    return { state: "non_positive", value: numeric };
  }
  return { state: "positive", value: numeric };
}

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

export function deriveInterpretationGuardState({
  reference = {},
  caseCity = "",
  serviceCity = "",
  serviceSame = true,
  provisionalCaseCity = "",
  provisionalServiceCity = "",
  includeTransport = true,
  travelKmOutbound = "",
} = {}) {
  const resolvedReference = buildInterpretationReference(reference);
  const resolvedCaseCity = resolveKnownCity(caseCity, resolvedReference.availableCities);
  const resolvedServiceCity = serviceSame
    ? resolvedCaseCity
    : resolveKnownCity(serviceCity, resolvedReference.availableCities);
  const caseCityProvisional = resolvedCaseCity ? "" : normalizeCityName(provisionalCaseCity || caseCity);
  const serviceCityProvisional = resolvedServiceCity
    ? ""
    : normalizeCityName((serviceSame ? provisionalCaseCity : provisionalServiceCity) || serviceCity);

  let blocked = false;
  let blockedCode = "";
  let blockedField = "";
  let blockedMessage = "";
  if (!resolvedCaseCity) {
    blocked = true;
    blockedCode = "unknown_case_city";
    blockedField = "case_city";
    blockedMessage = caseCityProvisional
      ? `Case city "${caseCityProvisional}" must be selected from a known city or added first.`
      : "Case city is required.";
  } else if (!resolvedServiceCity) {
    blocked = true;
    blockedCode = "unknown_service_city";
    blockedField = "service_city";
    blockedMessage = serviceCityProvisional
      ? `Service city "${serviceCityProvisional}" must be selected from a known city or added first.`
      : "Service city is required.";
  }

  const effectiveServiceCity = resolvedServiceCity;
  const parsedDistance = parsePositiveDistance(travelKmOutbound);
  const knownDistance = effectiveServiceCity ? Number(resolvedReference.travelDistancesByCity[effectiveServiceCity] || 0) : 0;
  const hasKnownDistance = Number.isFinite(knownDistance) && knownDistance > 0;
  let distancePromptNeeded = false;
  let distanceHint = "";

  if (!blocked && includeTransport) {
    if (parsedDistance.state === "invalid") {
      blocked = true;
      blockedCode = "distance_required";
      blockedField = "travel_km_outbound";
      blockedMessage = "KM (one way) must be a number.";
    } else if (parsedDistance.state === "non_positive") {
      blocked = true;
      blockedCode = "distance_must_be_positive";
      blockedField = "travel_km_outbound";
      blockedMessage = "KM (one way) must be greater than 0.";
    } else if (parsedDistance.state === "positive") {
      distanceHint = `Using ${parsedDistance.value} km one way.`;
    } else if (effectiveServiceCity && hasKnownDistance) {
      distanceHint = `Saved by city: ${knownDistance} km one way.`;
    } else if (effectiveServiceCity) {
      distancePromptNeeded = true;
      distanceHint = resolvedReference.travelOriginLabel
        ? `No saved distance for ${effectiveServiceCity}. We'll ask for the one-way distance from ${resolvedReference.travelOriginLabel} before save or export.`
        : `No saved distance for ${effectiveServiceCity}.`;
    } else {
      distanceHint = "Select the service city before setting the transport distance.";
    }
  }

  if (!includeTransport) {
    distanceHint = INTERPRETATION_DISCLOSURE_COPY.transportDisabledHint;
  }

  return {
    reference: resolvedReference,
    blocked,
    blockedCode,
    blockedField,
    blockedMessage,
    caseCity: resolvedCaseCity,
    serviceCity: resolvedServiceCity,
    effectiveServiceCity,
    provisionalCaseCity: caseCityProvisional,
    provisionalServiceCity: serviceCityProvisional,
    includeTransport: Boolean(includeTransport),
    distancePromptNeeded,
    distanceHint,
    knownDistance: hasKnownDistance ? knownDistance : 0,
    parsedTravelDistance: parsedDistance.value,
    parsedTravelDistanceState: parsedDistance.state,
  };
}

function hasMeaningfulInterpretationValue(value) {
  const normalized = String(value ?? "").trim();
  return Boolean(normalized && normalized !== "0" && normalized !== "0.0" && normalized !== "0.00");
}

function hasCompletedInterpretationArtifacts(session) {
  const normalizedStatus = String(session?.status || "").trim();
  if (normalizedStatus === "draft_ready" || normalizedStatus === "draft_failed") {
    return true;
  }

  if (Boolean(session?.draft_created) || hasMeaningfulInterpretationValue(session?.draft_failure_reason)) {
    return true;
  }

  const pdfExport = session?.pdf_export;
  if (pdfExport && typeof pdfExport === "object") {
    return Boolean(
      hasMeaningfulInterpretationValue(pdfExport.pdf_path)
      || hasMeaningfulInterpretationValue(pdfExport.pdfPath)
      || hasMeaningfulInterpretationValue(pdfExport.docx_path)
      || hasMeaningfulInterpretationValue(pdfExport.docxPath)
      || hasMeaningfulInterpretationValue(pdfExport.failure_message)
      || hasMeaningfulInterpretationValue(pdfExport.failureMessage),
    );
  }

  return false;
}

export function deriveInterpretationWorkspaceMode({
  snapshot = {},
  activeSession = null,
  hasCompletionPayload = false,
} = {}) {
  const interpretationSession = activeSession?.kind === "interpretation" ? activeSession : null;
  if (interpretationSession) {
    const hasCompletedArtifacts = hasCompletedInterpretationArtifacts(interpretationSession);
    return (hasCompletedArtifacts || hasCompletionPayload) ? "gmail_completed" : "gmail_review";
  }

  const hasSeedData = Boolean(
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
  return hasSeedData ? "manual_seed" : "blank";
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
