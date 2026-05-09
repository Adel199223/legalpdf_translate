function normalizeReviewEventId(value) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function normalizeSignature(value) {
  return String(value ?? "").trim();
}

export function gmailReviewStorageKey({ runtimeMode, workspaceId }) {
  return `legalpdf:gmail-review:${String(runtimeMode || "live").trim()}:${String(workspaceId || "workspace-1").trim()}`;
}

export function readConsumedReviewState(storage, context) {
  if (!storage || typeof storage.getItem !== "function") {
    return { reviewEventId: 0, messageSignature: "" };
  }
  try {
    const raw = storage.getItem(gmailReviewStorageKey(context));
    if (!raw) {
      return { reviewEventId: 0, messageSignature: "" };
    }
    const parsed = JSON.parse(raw);
    return {
      reviewEventId: normalizeReviewEventId(parsed?.reviewEventId),
      messageSignature: normalizeSignature(parsed?.messageSignature),
    };
  } catch {
    return { reviewEventId: 0, messageSignature: "" };
  }
}

export function writeConsumedReviewState(storage, context, { reviewEventId, messageSignature }) {
  const payload = {
    reviewEventId: normalizeReviewEventId(reviewEventId),
    messageSignature: normalizeSignature(messageSignature),
  };
  if (!storage || typeof storage.setItem !== "function" || typeof storage.removeItem !== "function") {
    return payload;
  }
  try {
    if (payload.reviewEventId <= 0 && !payload.messageSignature) {
      storage.removeItem(gmailReviewStorageKey(context));
      return payload;
    }
    storage.setItem(gmailReviewStorageKey(context), JSON.stringify(payload));
  } catch {
    // Storage failures should not block Gmail review behavior.
  }
  return payload;
}

export function clearConsumedReviewState(storage, context) {
  if (!storage || typeof storage.removeItem !== "function") {
    return;
  }
  try {
    storage.removeItem(gmailReviewStorageKey(context));
  } catch {
    // Ignore storage clear failures.
  }
}

export function shouldAutoOpenReview({
  reviewEventId,
  messageSignature,
  consumedReviewEventId,
  consumedMessageSignature,
  loadResult,
  activeSession,
}) {
  const nextEventId = normalizeReviewEventId(reviewEventId);
  const lastConsumedEventId = normalizeReviewEventId(consumedReviewEventId);
  const nextSignature = normalizeSignature(messageSignature);
  const lastConsumedSignature = normalizeSignature(consumedMessageSignature);
  const hasLoadedMessage = Boolean(loadResult?.ok && loadResult?.message);

  if (!hasLoadedMessage || activeSession) {
    return false;
  }
  if (nextEventId <= 0) {
    return false;
  }
  if (lastConsumedEventId === 0 && !lastConsumedSignature) {
    return true;
  }
  if (nextEventId !== lastConsumedEventId) {
    return true;
  }
  if (nextSignature && nextSignature !== lastConsumedSignature) {
    return true;
  }
  return false;
}

function normalizeGmailStage(value) {
  const normalized = String(value || "").trim();
  const allowed = new Set([
    "idle",
    "review",
    "translation_recovery",
    "translation_prepared",
    "translation_running",
    "translation_save",
    "translation_finalize",
    "interpretation_review",
    "interpretation_finalize",
  ]);
  return allowed.has(normalized) ? normalized : "idle";
}

function normalizeGmailBatchContext(value) {
  if (!value || typeof value !== "object") {
    return null;
  }
  const normalized = {
    source: String(value.source || "").trim(),
    session_id: String(value.session_id || "").trim(),
    message_id: String(value.message_id || "").trim(),
    thread_id: String(value.thread_id || "").trim(),
    attachment_id: String(value.attachment_id || "").trim(),
    selected_attachment_filename: String(value.selected_attachment_filename || "").trim(),
    selected_attachment_count: Number.parseInt(String(value.selected_attachment_count ?? "").trim(), 10) || 0,
    selected_target_lang: String(value.selected_target_lang || "").trim().toUpperCase(),
    selected_start_page: Number.parseInt(String(value.selected_start_page ?? "").trim(), 10) || 0,
    gmail_batch_session_report_path: String(value.gmail_batch_session_report_path || "").trim(),
  };
  return Object.values(normalized).some((item) => item)
    ? normalized
    : null;
}

function currentTranslationAttachmentContext(activeSession) {
  if (!activeSession || activeSession.kind !== "translation" || activeSession.completed) {
    return null;
  }
  const currentAttachment = activeSession.current_attachment;
  const attachment = currentAttachment?.attachment;
  if (!currentAttachment || !attachment) {
    return null;
  }
  return {
    source: "gmail_intake",
    session_id: String(activeSession.session_id || "").trim(),
    message_id: String(activeSession.message?.message_id || "").trim(),
    thread_id: String(activeSession.message?.thread_id || "").trim(),
    attachment_id: String(attachment.attachment_id || "").trim(),
    selected_attachment_filename: String(attachment.filename || "").trim(),
    selected_attachment_count: Number.parseInt(String(activeSession.total_items ?? "").trim(), 10) || 0,
    selected_target_lang: String(activeSession.selected_target_lang || "").trim().toUpperCase(),
    selected_start_page: Number.parseInt(String(currentAttachment.start_page ?? "").trim(), 10) || 0,
    source_path: String(currentAttachment.saved_path || "").trim(),
  };
}

function translationJobMatchesCurrentAttachment(job, attachmentContext) {
  if (!job || typeof job !== "object" || !attachmentContext) {
    return false;
  }
  const jobContext = normalizeGmailBatchContext(job.config?.gmail_batch_context);
  if (jobContext && attachmentContext.attachment_id && jobContext.attachment_id === attachmentContext.attachment_id) {
    return true;
  }
  if (
    jobContext
    && attachmentContext.message_id
    && attachmentContext.thread_id
    && attachmentContext.selected_attachment_filename
    && jobContext.message_id === attachmentContext.message_id
    && jobContext.thread_id === attachmentContext.thread_id
    && jobContext.selected_attachment_filename === attachmentContext.selected_attachment_filename
    && Number(jobContext.selected_start_page || 0) === Number(attachmentContext.selected_start_page || 0)
  ) {
    return true;
  }
  const sourcePath = String(job.config?.source_path || "").trim();
  return Boolean(
    attachmentContext.source_path
    && sourcePath
    && sourcePath === attachmentContext.source_path
  );
}

function findMatchingTranslationJob(translationUi, attachmentContext) {
  const jobs = Array.isArray(translationUi.runtimeJobs) ? translationUi.runtimeJobs : [];
  return jobs.find((job) => translationJobMatchesCurrentAttachment(job, attachmentContext)) || null;
}

export function deriveGmailStage({
  loadResult,
  activeSession,
  reviewDrawerOpen = false,
  translationUi = {},
  interpretationUi = {},
}) {
  const hasLoadedMessage = Boolean(loadResult?.ok && loadResult?.message);
  if (activeSession?.kind === "translation") {
    if (activeSession.completed) {
      return "translation_finalize";
    }
    const attachmentContext = currentTranslationAttachmentContext(activeSession);
    const matchingJob = attachmentContext ? findMatchingTranslationJob(translationUi, attachmentContext) : null;
    const currentJobStatus = String(translationUi.currentJobStatus || "").trim();
    const currentJobKind = String(translationUi.currentJobKind || "").trim();
    const hasSaveSeed = Boolean(translationUi.currentJobHasSaveSeed);
    const matchingJobStatus = String(matchingJob?.status || "").trim();
    const matchingJobKind = String(matchingJob?.job_kind || "").trim();
    const matchingJobHasSaveSeed = Boolean(matchingJob?.has_save_seed);
    const preparedLaunchMatchesCurrentAttachment = Boolean(
      attachmentContext
      && translationUi.hasPreparedLaunch
      && translationJobMatchesCurrentAttachment({
        config: {
          source_path: String(translationUi.preparedLaunchSourcePath || "").trim(),
          gmail_batch_context: normalizeGmailBatchContext(translationUi.currentGmailBatchContext),
        },
      }, attachmentContext)
    );
    if (
      translationUi.currentJobRecoveryRequired
      || currentJobStatus === "failed"
      || currentJobStatus === "cancelled"
      || (currentJobKind === "rebuild" && !hasSaveSeed)
      || matchingJobStatus === "failed"
      || matchingJobStatus === "cancelled"
      || (matchingJobKind === "rebuild" && !matchingJobHasSaveSeed)
    ) {
      return "translation_recovery";
    }
    if (
      translationUi.completionDrawerOpen
      || translationUi.hasCompletionSurface
      || currentJobStatus === "completed"
      || matchingJobStatus === "completed"
    ) {
      return "translation_save";
    }
    if (preparedLaunchMatchesCurrentAttachment && !matchingJobStatus) {
      return "translation_prepared";
    }
    return "translation_running";
  }
  if (activeSession?.kind === "interpretation") {
    return interpretationUi.exportReady ? "interpretation_finalize" : "interpretation_review";
  }
  if (reviewDrawerOpen || hasLoadedMessage) {
    return "review";
  }
  return "idle";
}

export function deriveGmailWorkflowPresentation({ workflowKind } = {}) {
  const normalized = String(workflowKind || "").trim() === "interpretation"
    ? "interpretation"
    : "translation";
  if (normalized === "interpretation") {
    return {
      kind: "interpretation",
      label: "Interpretation",
      selectionLabel: "selected notice",
      emptySelectionLabel: "Choose a notice to continue",
      prepareLabel: "Continue with selected notice",
      reviewStatus: "Choose the notice you want to process. Preview is optional and the notice will continue from page 1.",
      currentItemLabel: "Current notice",
    };
  }
  return {
    kind: "translation",
    label: "Translation",
    selectionLabel: "selected attachments",
    emptySelectionLabel: "Choose attachments to continue",
    prepareLabel: "Continue with selected attachments",
    reviewStatus: "Choose the attachments you want to process. Preview is optional and helps when you want to confirm the document or choose a later start page.",
    currentItemLabel: "Current document",
  };
}

export function deriveGmailAttachmentKindLabel(mimeType) {
  const normalized = String(mimeType || "").trim().toLowerCase();
  if (normalized === "application/pdf") {
    return "PDF";
  }
  if (normalized.startsWith("image/")) {
    return "Image";
  }
  return "Unknown";
}

export function deriveRecoveredFinalizationAction({ restoredCompletedSession }) {
  if (
    restoredCompletedSession?.kind !== "translation"
    || restoredCompletedSession?.completed !== true
    || restoredCompletedSession?.restored_from_report !== true
  ) {
    return {
      visible: false,
      enabled: false,
      label: "Open Last Finalization Result",
      action: "",
      title: "",
      description: "",
      tone: "info",
    };
  }
  const subject = String(restoredCompletedSession?.message?.subject || "").trim();
  const draftReady = String(restoredCompletedSession?.finalization_state || "").trim() === "draft_ready";
  return {
    visible: true,
    enabled: true,
    label: "Open Last Finalization Result",
    action: "open-restored-translation-finalize",
    title: "Last Gmail reply is still available.",
    description: subject
      ? `${subject} was recovered from the previous Gmail reply. Open it only if you need the earlier final files or report; a fresh Gmail message should continue normally.`
      : "Open the previous Gmail reply only if you need the earlier final files or report; a fresh Gmail message should continue normally.",
    tone: draftReady ? "ok" : "info",
  };
}

export function shouldTreatGmailWorkspaceAsStable({
  activeView,
  loadResult,
  activeSession,
  restoredCompletedSession,
  pendingStatus = "",
  pendingReviewOpen = false,
}) {
  if (String(activeView || "").trim() !== "gmail-intake") {
    return false;
  }
  const normalizedPendingStatus = String(pendingStatus || "").trim().toLowerCase();
  if (pendingReviewOpen === true && (normalizedPendingStatus === "warming" || normalizedPendingStatus === "delayed")) {
    return false;
  }
  if (activeSession) {
    return true;
  }
  if (loadResult?.ok && loadResult?.message) {
    return true;
  }
  if (restoredCompletedSession) {
    return false;
  }
  return false;
}

export function deriveGmailRedoAction({ activeSession, translationUi = {} }) {
  const attachmentContext = currentTranslationAttachmentContext(activeSession);
  if (!attachmentContext) {
    return {
      visible: false,
      enabled: false,
      blocked: false,
      label: "Redo Current Attachment",
      action: "",
      title: "",
      description: "",
      warning: "",
      matchingJob: null,
    };
  }
  const matchingJob = findMatchingTranslationJob(translationUi, attachmentContext);
  const status = String(matchingJob?.status || "").trim();
  const blocked = ["queued", "running", "cancel_requested"].includes(status);
  const filename = attachmentContext.selected_attachment_filename || "the current attachment";
  if (!matchingJob) {
    return {
      visible: true,
      enabled: true,
      blocked: false,
      label: "Redo Current Attachment",
      action: "redo-current-translation",
      title: "Redo this attachment.",
      description: `Prepare a fresh translation for ${filename} while keeping the Gmail reply on the same message.`,
      warning: "",
      matchingJob: null,
    };
  }
  if (blocked) {
    return {
      visible: true,
      enabled: false,
      blocked: true,
      label: "Redo Current Attachment",
      action: "redo-current-translation",
      title: "This attachment is already running.",
      description: `${filename} already has an active ${matchingJob.job_kind || "translation"} run. Cancel it first if you want to run this file again.`,
      warning: `Matching job: ${matchingJob.job_id || "unknown"}`,
      matchingJob,
    };
  }
  return {
    visible: true,
    enabled: true,
    blocked: false,
    label: "Redo Current Attachment",
    action: "redo-current-translation",
    title: "Redo this attachment.",
    description: `${filename} already has an earlier ${matchingJob.job_kind || "translation"} run in this app. Redo keeps the earlier files and prepares a fresh run for you to start manually.`,
    warning: `Matching job: ${matchingJob.job_id || "unknown"}`,
    matchingJob,
  };
}

function normalizePreviewPageValue(value, { editable, pageCount }) {
  if (!editable) {
    return 1;
  }
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  let nextValue = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
  const upperBound = Number.parseInt(String(pageCount ?? 0).trim(), 10);
  if (Number.isFinite(upperBound) && upperBound > 0) {
    nextValue = Math.min(nextValue, upperBound);
  }
  return Math.max(1, nextValue);
}

export function createClosedPreviewState() {
  return {
    open: false,
    minimized: false,
    attachmentId: "",
    previewHref: "",
    previewMimeType: "",
    page: 1,
    pageCount: 0,
    editable: false,
  };
}

export function openPreviewState({
  attachmentId,
  previewHref,
  previewMimeType,
  pageCount,
  currentStartPage,
  editable,
}) {
  const normalizedAttachmentId = normalizeSignature(attachmentId);
  const nextEditable = Boolean(editable);
  const nextPageCount = Math.max(0, Number.parseInt(String(pageCount ?? 0).trim(), 10) || 0);
  return {
    open: Boolean(normalizedAttachmentId),
    minimized: false,
    attachmentId: normalizedAttachmentId,
    previewHref: normalizeSignature(previewHref),
    previewMimeType: normalizeSignature(previewMimeType),
    page: normalizePreviewPageValue(currentStartPage, {
      editable: nextEditable,
      pageCount: nextPageCount,
    }),
    pageCount: nextPageCount,
    editable: nextEditable,
  };
}

export function setPreviewStatePage(previewState, value) {
  if (!previewState?.open || !normalizeSignature(previewState.attachmentId)) {
    return createClosedPreviewState();
  }
  return {
    ...previewState,
    page: normalizePreviewPageValue(value, {
      editable: Boolean(previewState.editable),
      pageCount: Math.max(0, Number.parseInt(String(previewState.pageCount ?? 0).trim(), 10) || 0),
    }),
  };
}

export function applyPreviewStateStartPage(previewState, currentStartPage) {
  if (!previewState?.open || !normalizeSignature(previewState.attachmentId)) {
    return normalizePreviewPageValue(currentStartPage, { editable: true, pageCount: 0 });
  }
  return normalizePreviewPageValue(previewState.page, {
    editable: Boolean(previewState.editable),
    pageCount: Math.max(0, Number.parseInt(String(previewState.pageCount ?? 0).trim(), 10) || 0),
  });
}

export function isPreviewStateOpen(previewState) {
  return Boolean(previewState?.open && normalizeSignature(previewState.attachmentId));
}

export function minimizePreviewState(previewState) {
  if (!isPreviewStateOpen(previewState)) {
    return createClosedPreviewState();
  }
  return {
    ...previewState,
    minimized: true,
  };
}

export function restorePreviewState(previewState) {
  if (!isPreviewStateOpen(previewState)) {
    return createClosedPreviewState();
  }
  return {
    ...previewState,
    minimized: false,
  };
}

export function deriveGmailReviewRestoreLabel({ selectedCount } = {}) {
  const count = Math.max(0, Number.parseInt(String(selectedCount ?? 0).trim(), 10) || 0);
  if (count === 1) {
    return "Review Attachments — 1 selected";
  }
  if (count > 1) {
    return `Review Attachments — ${count} selected`;
  }
  return "Review Attachments — Restore";
}

export function deriveGmailPreviewRestoreLabel(previewState) {
  if (!isPreviewStateOpen(previewState)) {
    return "PDF Preview — Restore";
  }
  const page = Math.max(1, Number.parseInt(String(previewState.page ?? 1).trim(), 10) || 1);
  return `PDF Preview — page ${page}`;
}

export function deriveGmailOverlayDismissalAction(trigger) {
  const normalizedTrigger = normalizeSignature(trigger).toLowerCase();
  if (normalizedTrigger === "backdrop" || normalizedTrigger === "outside") {
    return "keep-open";
  }
  if (["back", "close", "escape", "minimize"].includes(normalizedTrigger)) {
    return "minimize";
  }
  return "keep-open";
}

export function shouldIgnoreReviewRowFocusTarget(target) {
  if (!target || typeof target.closest !== "function") {
    return false;
  }
  const selectors = [
    ".gmail-review-select",
    ".attachment-start-page",
    "button",
    "a",
    "select",
    "textarea",
    "input",
  ];
  return selectors.some((selector) => {
    try {
      return Boolean(target.closest(selector));
    } catch {
      return false;
    }
  });
}
