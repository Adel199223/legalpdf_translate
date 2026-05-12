function stringOrEmpty(value) {
  return String(value ?? "");
}

function objectOrEmpty(value) {
  return value && typeof value === "object" ? value : {};
}

export function buildGmailPrepareSessionRequestPayload({
  workflowKind = "",
  targetLang = "",
  outputDir = "",
  selections = [],
} = {}) {
  return {
    workflow_kind: stringOrEmpty(workflowKind),
    target_lang: stringOrEmpty(targetLang),
    output_dir: stringOrEmpty(outputDir),
    selections: Array.isArray(selections) ? selections : [],
  };
}

export function buildGmailBatchFinalizePreflightRequestPayload({ forceRefresh = false } = {}) {
  return {
    force_refresh: Boolean(forceRefresh),
  };
}

export function buildGmailConfirmCurrentTranslationRequestPayload({
  jobId = "",
  completionKey = "",
  formValues = {},
  rowId = null,
} = {}) {
  return {
    job_id: stringOrEmpty(jobId),
    completion_key: stringOrEmpty(completionKey),
    form_values: objectOrEmpty(formValues),
    row_id: rowId ?? null,
  };
}

export function buildGmailBatchFinalizeRequestPayload({
  profileId = "",
  outputFilename = "",
} = {}) {
  return {
    profile_id: stringOrEmpty(profileId),
    output_filename: stringOrEmpty(outputFilename),
  };
}

export function buildGmailInterpretationFinalizeRequestPayload({
  formValues = {},
  profileId = "",
  serviceSameChecked = false,
  outputFilename = "",
} = {}) {
  return {
    form_values: objectOrEmpty(formValues),
    profile_id: stringOrEmpty(profileId),
    service_same_checked: Boolean(serviceSameChecked),
    output_filename: stringOrEmpty(outputFilename),
  };
}
