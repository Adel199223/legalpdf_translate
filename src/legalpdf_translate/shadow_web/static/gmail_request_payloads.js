function stringOrEmpty(value) {
  return String(value ?? "");
}

function objectOrEmpty(value) {
  return value && typeof value === "object" ? value : {};
}

export function buildGmailRestartCanonicalRuntimeRequestPayload({
  mode = "",
  workspaceId = "",
} = {}) {
  return {
    mode: stringOrEmpty(mode),
    workspace_id: stringOrEmpty(workspaceId),
  };
}

export function buildGmailLoadMessageRequestPayload({
  messageId = "",
  threadId = "",
  subject = "",
  accountEmail = "",
  sourceGmailUrl = "",
} = {}) {
  return {
    message_context: {
      message_id: stringOrEmpty(messageId),
      thread_id: stringOrEmpty(threadId),
      subject: stringOrEmpty(subject),
      account_email: stringOrEmpty(accountEmail),
      source_gmail_url: stringOrEmpty(sourceGmailUrl),
    },
  };
}

export function buildGmailEmptyRequestPayload() {
  return {};
}

export function buildGmailBrowserFailureReportRequestPayload({
  reportContext = {},
} = {}) {
  return {
    browser_failure_context: objectOrEmpty(reportContext),
  };
}

export function buildGmailFinalizationReportRequestPayload({
  reportContext = {},
} = {}) {
  return {
    gmail_finalization_context: objectOrEmpty(reportContext),
  };
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
  baselineId = null,
  expectedDeliveryGeneration = null,
} = {}) {
  return {
    job_id: stringOrEmpty(jobId),
    completion_key: stringOrEmpty(completionKey),
    form_values: objectOrEmpty(formValues),
    row_id: rowId ?? null,
    ...(baselineId ? {baseline_id:stringOrEmpty(baselineId),expected_delivery_generation:expectedDeliveryGeneration} : {}),
  };
}

export function buildGmailBatchFinalizeRequestPayload({
  profileId = "",
  outputFilename = "",
  recipientBlock = "",
  includeTranslatorDeclaration = false,
  translatorDeclarationText = "",
} = {}) {
  return {
    profile_id: stringOrEmpty(profileId),
    output_filename: stringOrEmpty(outputFilename),
    recipient_block: stringOrEmpty(recipientBlock),
    include_translator_declaration: Boolean(includeTranslatorDeclaration),
    translator_declaration_text: includeTranslatorDeclaration ? stringOrEmpty(translatorDeclarationText) : "",
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
