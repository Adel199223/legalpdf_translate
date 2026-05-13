function objectOrEmpty(value) {
  return value && typeof value === "object" ? value : {};
}

function isActiveTranslationJobStatus(status) {
  return ["queued", "running", "cancel_requested"].includes(String(status || "").trim());
}

export function deriveTranslationActionState(job = null, options = {}) {
  const normalizedOptions = objectOrEmpty(options);
  const sourceState = {
    status: "empty",
    ready: false,
    replacingPrepared: false,
    fromGmail: false,
    message: "",
    ...objectOrEmpty(normalizedOptions.sourceState),
  };
  const activeJob = isActiveTranslationJobStatus(job?.status);
  const jobId = String(job?.job_id || normalizedOptions.currentJobId || "").trim();
  const canStart = Boolean(sourceState.ready && !activeJob);
  let helperText = "Choose a PDF or image to enable Start Translate.";
  if (sourceState.status === "manual-uploading") {
    helperText = sourceState.replacingPrepared
      ? "Checking the replacement document..."
      : "Checking the document before translation starts...";
  } else if (activeJob) {
    helperText = "A translation run is already in progress. Cancel it or wait for it to finish before starting another one.";
  } else if (sourceState.status === "prepared-ready") {
    helperText = sourceState.fromGmail
      ? "Gmail attachment is prepared. Review settings, then start translation."
      : "The prepared document is ready. Confirm the language and output folder, then start translation.";
  } else if (sourceState.status === "manual-ready") {
    helperText = "The document is ready. Confirm the language and output folder, then start translation.";
  } else if (sourceState.status === "manual-error") {
    helperText = sourceState.message || "The document could not be staged. Choose another file to continue.";
  }
  return {
    sourceState: sourceState.status,
    helperText,
    startEnabled: canStart,
    analyzeEnabled: canStart,
    cancelEnabled: Boolean(jobId && job?.actions?.cancel),
    resumeEnabled: Boolean(jobId && job?.actions?.resume),
    rebuildEnabled: Boolean(jobId && job?.actions?.rebuild),
  };
}
