function setFieldValueIfPresent(field, value) {
  if (field) {
    field.value = value ?? "";
  }
}

function fieldIsBlank(field) {
  return !String(field?.value ?? "").trim();
}

export function renderGmailContextDefaultsInto(nodes = {}, presentation = {}) {
  if (fieldIsBlank(nodes.messageId)) {
    setFieldValueIfPresent(nodes.messageId, presentation?.messageId);
  }
  if (fieldIsBlank(nodes.threadId)) {
    setFieldValueIfPresent(nodes.threadId, presentation?.threadId);
  }
  if (fieldIsBlank(nodes.subject)) {
    setFieldValueIfPresent(nodes.subject, presentation?.subject);
  }
  if (fieldIsBlank(nodes.accountEmail)) {
    setFieldValueIfPresent(nodes.accountEmail, presentation?.accountEmail);
  }
  if (fieldIsBlank(nodes.outputDir)) {
    setFieldValueIfPresent(nodes.outputDir, presentation?.outputDir);
  }
  if (fieldIsBlank(nodes.targetLang)) {
    setFieldValueIfPresent(nodes.targetLang, presentation?.targetLang);
  }
  return nodes;
}

export function renderGmailSimulatorDefaultsInto(nodes = {}, presentation = {}) {
  setFieldValueIfPresent(nodes.messageId, presentation?.messageId);
  setFieldValueIfPresent(nodes.threadId, presentation?.threadId);
  setFieldValueIfPresent(nodes.subject, presentation?.subject);
  if (presentation?.accountEmail) {
    setFieldValueIfPresent(nodes.accountEmail, presentation.accountEmail);
  }
  return nodes;
}
