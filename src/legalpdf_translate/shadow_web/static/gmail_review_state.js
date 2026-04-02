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
    "translation_running",
    "translation_save",
    "translation_finalize",
    "interpretation_review",
    "interpretation_finalize",
  ]);
  return allowed.has(normalized) ? normalized : "idle";
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
    const currentJobStatus = String(translationUi.currentJobStatus || "").trim();
    if (translationUi.completionDrawerOpen || translationUi.hasCompletionSurface || currentJobStatus === "completed") {
      return "translation_save";
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

export function deriveGmailHomeCta({ stage, activeSession }) {
  switch (normalizeGmailStage(stage)) {
    case "translation_running":
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-translation-running",
        title: "Translation step is in progress.",
        description: activeSession?.current_attachment?.attachment?.filename
          ? `Continue the Gmail translation workspace for ${activeSession.current_attachment.attachment.filename}.`
          : `Continue attachment ${activeSession?.current_item_number || "?"}/${activeSession?.total_items || "?"} in the Gmail translation batch.`,
        tone: "info",
      };
    case "translation_save":
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-translation-save",
        title: "Finish Translation is ready.",
        description: "Return to the bounded finish surface to review and save the current Gmail translation row.",
        tone: "ok",
      };
    case "translation_finalize":
      if (activeSession?.finalization_state === "draft_ready") {
        return {
          visible: true,
          label: "Open Finalization Result",
          action: "resume-translation-finalize",
          title: "Batch finalization is complete.",
          description: "The Gmail draft is already ready. Open the finalization drawer to review the artifacts or generate a finalization report.",
          tone: "ok",
        };
      }
      if (activeSession?.finalization_state === "draft_failed") {
        return {
          visible: true,
          label: "Resume Current Step",
          action: "resume-translation-finalize",
          title: "Batch finalization needs attention.",
          description: "Honorários were created, but the Gmail draft step failed. Open the finalization drawer to retry or generate a finalization report.",
          tone: "info",
        };
      }
      if (activeSession?.finalization_state === "local_artifacts_ready") {
        return {
          visible: true,
          label: "Resume Current Step",
          action: "resume-translation-finalize",
          title: "Batch finalization is recoverable.",
          description: "Honorários were created locally, but the Gmail draft step is still pending. Open the finalization drawer to retry or generate a finalization report.",
          tone: "info",
        };
      }
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-translation-finalize",
        title: "Batch finalization is waiting.",
        description: "All selected Gmail attachments are confirmed. Resume the final reply step when you are ready.",
        tone: "ok",
      };
    case "interpretation_review":
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-interpretation-review",
        title: "Interpretation review is ready.",
        description: "Continue in the bounded interpretation review surface with the Gmail notice already staged.",
        tone: "info",
      };
    case "interpretation_finalize":
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-interpretation-finalize",
        title: "Interpretation finalization is ready.",
        description: "Return to the interpretation review surface to finish the Gmail reply without reopening the full workspace.",
        tone: "ok",
      };
    default:
      return {
        visible: false,
        label: "Resume Current Step",
        action: "review",
        title: "",
        description: "",
        tone: "info",
      };
  }
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
