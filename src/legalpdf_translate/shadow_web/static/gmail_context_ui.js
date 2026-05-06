function setFieldValueIfPresent(field, value) {
  if (field) {
    field.value = value ?? "";
  }
}

function fieldIsBlank(field) {
  return !String(field?.value ?? "").trim();
}

export function renderGmailContextDefaultsInto(nodes = {}, data = {}) {
  const defaults = data?.defaults || {};
  const messageContext = defaults.message_context || {};

  if (fieldIsBlank(nodes.messageId)) {
    setFieldValueIfPresent(nodes.messageId, messageContext.message_id || "");
  }
  if (fieldIsBlank(nodes.threadId)) {
    setFieldValueIfPresent(nodes.threadId, messageContext.thread_id || "");
  }
  if (fieldIsBlank(nodes.subject)) {
    setFieldValueIfPresent(nodes.subject, messageContext.subject || "");
  }
  if (fieldIsBlank(nodes.accountEmail)) {
    setFieldValueIfPresent(nodes.accountEmail, messageContext.account_email || "");
  }
  if (fieldIsBlank(nodes.outputDir)) {
    setFieldValueIfPresent(nodes.outputDir, defaults.default_output_dir || "");
  }
  if (fieldIsBlank(nodes.targetLang)) {
    setFieldValueIfPresent(nodes.targetLang, defaults.target_lang || "EN");
  }
  return nodes;
}

export function renderGmailSimulatorDefaultsInto(nodes = {}, defaults = {}) {
  setFieldValueIfPresent(nodes.messageId, defaults.message_id || "");
  setFieldValueIfPresent(nodes.threadId, defaults.thread_id || "");
  setFieldValueIfPresent(nodes.subject, defaults.subject || "");
  if (defaults.account_email) {
    setFieldValueIfPresent(nodes.accountEmail, defaults.account_email);
  }
  return nodes;
}
