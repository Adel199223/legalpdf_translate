export function normalizeCityName(value) {
  return String(value ?? "").replace(/\s+/g, " ").trim();
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
    distanceHint = "Transport sentence disabled for this honorarios export.";
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
