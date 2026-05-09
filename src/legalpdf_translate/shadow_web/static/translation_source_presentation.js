function normalizeSourceTypeLabel(sourceType) {
  const normalized = String(sourceType || "").trim().toLowerCase();
  if (normalized === "pdf") {
    return "PDF";
  }
  if (normalized === "image") {
    return "Image";
  }
  return "PDF or image";
}

function normalizeTarget(value) {
  return String(value || "").trim().toUpperCase();
}

export function buildTranslationSourceCardPresentation({
  sourceState = {},
  preparedLaunch = null,
  selectedTarget = "",
  defaultTarget = "",
  hasManualSourceSelection = false,
} = {}) {
  const state = sourceState && typeof sourceState === "object" ? sourceState : {};
  const launch = preparedLaunch && typeof preparedLaunch === "object" ? preparedLaunch : {};
  const status = String(state.status || "empty").trim() || "empty";
  const isPrepared = status === "prepared-ready";
  const isUploading = status === "manual-uploading";
  const isError = status === "manual-error";
  const isCurrentJob = status === "current-job";
  const ready = Boolean(state.ready);
  const fromGmail = Boolean(state.fromGmail);

  let copy = "Drag and drop it here, or choose it from your computer.";
  if (isUploading) {
    copy = state.replacingPrepared
      ? "Checking the replacement document before it replaces the prepared attachment..."
      : "Uploading the file and checking the page count...";
  } else if (isCurrentJob) {
    copy = "This source is attached to the current translation job. Progress will update below while the run is active.";
  } else if (isPrepared) {
    copy = fromGmail
      ? "Review settings, then start translation. Choosing a local file will replace the prepared Gmail attachment for the next run."
      : "This document is already staged. Choosing a local file will replace it for the next run.";
  } else if (ready) {
    copy = "The document is staged and ready. Confirm the language and output folder, then start translation.";
  } else if (isError) {
    copy = state.message || "The file could not be staged. Choose another document to try again.";
  }

  const gmailTarget = normalizeTarget(launch.target_lang || launch.gmail_batch_context?.selected_target_lang);
  const selectedTargetLabel = normalizeTarget(selectedTarget);
  const fallbackTarget = normalizeTarget(defaultTarget);
  let stageStatus = "Choose a file to begin.";
  if (isUploading) {
    stageStatus = state.replacingPrepared
      ? "Checking the replacement document..."
      : "Uploading and checking the file...";
  } else if (isCurrentJob) {
    stageStatus = "Current job is using this source.";
  } else if (isPrepared) {
    stageStatus = fromGmail ? "Ready from Gmail." : "Prepared and ready.";
  } else if (ready) {
    stageStatus = "Uploaded and ready.";
  } else if (isError) {
    stageStatus = state.message || "Upload failed.";
  }

  let hint = "PDF and common image files are supported.";
  if (isCurrentJob) {
    hint = "Load another source only when you are ready to prepare the next run.";
  } else if (ready && isPrepared) {
    hint = fromGmail
      ? "The Gmail attachment stays staged until you explicitly choose a new local file."
      : "The prepared document stays staged until you explicitly choose a new local file.";
  } else if (ready) {
    hint = "The same local file will not be uploaded again unless it changes.";
  }

  const chipState = isError
    ? { text: "Needs attention", tone: "bad" }
    : isUploading
      ? { text: "Uploading", tone: "info" }
      : isCurrentJob
        ? { text: "In progress", tone: "info" }
        : isPrepared
          ? { text: "Ready", tone: "info" }
          : ready
            ? { text: "Ready", tone: "ok" }
            : { text: "", tone: "" };

  return {
    state: status,
    title: isPrepared && fromGmail
      ? "Gmail attachment is prepared"
      : state.filename || (isPrepared ? "Prepared source" : "Choose a PDF or image"),
    copy,
    filename: state.filename || "No file selected yet.",
    sourceType: normalizeSourceTypeLabel(state.sourceType || (isPrepared ? "pdf" : "")),
    pages: state.pageCount ?? "--",
    target: isPrepared && fromGmail && gmailTarget
      ? `Current Gmail job target: ${gmailTarget}`
      : `Target language: ${selectedTargetLabel || fallbackTarget || "EN"}`,
    defaultTarget: isPrepared && fromGmail && fallbackTarget && fallbackTarget !== gmailTarget
      ? `Default target for new jobs: ${fallbackTarget}`
      : "Using the current target language for this run.",
    stageStatus,
    hint,
    chipText: chipState.text,
    chipTone: chipState.tone,
    browseLabel: ready ? "Choose another document" : "Choose document",
    browseDisabled: isUploading,
    clearHidden: !Boolean(hasManualSourceSelection),
  };
}
