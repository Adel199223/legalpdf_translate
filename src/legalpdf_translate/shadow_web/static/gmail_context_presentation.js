function stringFromFallback(value, fallback = "") {
  return String(value || fallback);
}

export function buildGmailContextDefaultsPresentation(options = {}) {
  const defaults = options?.defaults || {};
  const messageContext = defaults.message_context || {};

  return {
    messageId: stringFromFallback(messageContext.message_id),
    threadId: stringFromFallback(messageContext.thread_id),
    subject: stringFromFallback(messageContext.subject),
    accountEmail: stringFromFallback(messageContext.account_email),
    outputDir: stringFromFallback(defaults.default_output_dir),
    targetLang: stringFromFallback(defaults.target_lang, "EN"),
  };
}

export function buildGmailSimulatorDefaultsPresentation(options = {}) {
  const defaults = options?.defaults || {};

  return {
    messageId: stringFromFallback(defaults.message_id),
    threadId: stringFromFallback(defaults.thread_id),
    subject: stringFromFallback(defaults.subject),
    accountEmail: stringFromFallback(defaults.account_email),
  };
}
