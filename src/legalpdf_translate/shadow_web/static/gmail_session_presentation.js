export function buildGmailResumeCardPresentation({
  activeSession = null,
  cta = {},
  redo = {},
  stagePresentation = {},
} = {}) {
  if (!cta.visible || !activeSession) {
    return {
      visible: false,
      emptyText: "No Gmail step is waiting yet.",
    };
  }

  let gridItems = [];
  if (activeSession.kind === "translation") {
    const currentAttachment = activeSession.current_attachment?.attachment?.filename || "Current attachment";
    const batchLabel = activeSession.total_items
      ? `${activeSession.current_item_number || "?"}/${activeSession.total_items}`
      : "Batch ready";
    gridItems = [
      { label: "Status", value: stagePresentation.title || "Ready" },
      { label: "Batch", value: batchLabel },
      { label: "Current File", value: currentAttachment, className: "word-break" },
    ];
  } else if (activeSession.kind === "interpretation") {
    const noticeName = activeSession.attachment?.attachment?.filename || "Prepared notice";
    gridItems = [
      { label: "Status", value: stagePresentation.title || "Ready" },
      { label: "Notice", value: noticeName, className: "word-break" },
    ];
  }

  return {
    visible: true,
    title: cta.title || "Resume Current Step",
    message: cta.description || "Continue the active Gmail step when you are ready.",
    extraMessages: redo.visible ? [redo.description || ""] : [],
    label: activeSession.status || "ready",
    tone: cta.tone === "ok" ? "ok" : "info",
    gridItems,
  };
}

export function buildGmailTranslationStepContext({
  activeSession = null,
  translationUi = {},
} = {}) {
  const visible = Boolean(
    activeSession?.kind === "translation"
    && !activeSession?.completed
    && (translationUi.currentJobStatus === "completed" || translationUi.hasCompletionSurface),
  );
  const blocked = Boolean(translationUi.requiresArabicReview && !translationUi.arabicReviewResolved);
  const filename = activeSession?.current_attachment?.attachment?.filename || "Current Gmail attachment";
  const batchLabel = activeSession?.total_items
    ? `${activeSession.current_item_number || "?"}/${activeSession.total_items}`
    : "Batch step";
  const hasMoreItems = Number(activeSession?.current_item_number || 0) < Number(activeSession?.total_items || 0);

  return {
    visible,
    blocked,
    filename,
    batchLabel,
    hasMoreItems,
    hookPayload: visible ? {
      currentRowId: translationUi.currentRowId,
      arabicReview: {
        required: translationUi.requiresArabicReview,
        resolved: translationUi.arabicReviewResolved,
        message: translationUi.arabicReviewMessage,
        completion_key: translationUi.arabicReviewCompletionKey,
        status: translationUi.arabicReviewResolved ? "resolved" : "required",
      },
      gmailBatchContext: translationUi.currentGmailBatchContext,
      gmailCurrentStep: {
        visible,
        filename,
        batchLabel,
        hasMoreItems,
      },
    } : null,
  };
}

export function buildGmailTranslationStepCardPresentation({
  stepContext = null,
  activeSession = null,
  translationUi = {},
  hookPresentation = null,
} = {}) {
  const context = stepContext || buildGmailTranslationStepContext({ activeSession, translationUi });
  if (!context.visible) {
    return {
      visible: false,
      blocked: context.blocked,
    };
  }

  const hookCard = hookPresentation?.gmailCurrentAttachment || {};
  return {
    visible: true,
    blocked: context.blocked,
    title: hookCard.title || (
      context.blocked
        ? "Review the Arabic document in Word before you save this Gmail attachment."
        : "This Gmail attachment is ready to save."
    ),
    copy: hookCard.copy || (
      context.blocked
        ? (translationUi.arabicReviewMessage || "Open the translated DOCX in Word, save it there, then return here to save this Gmail attachment.")
        : context.hasMoreItems
          ? "Save this translated attachment, then continue with the next Gmail step."
          : "Save this translated attachment, then continue to create the Gmail reply."
    ),
    chipLabel: hookCard.chipLabel || context.batchLabel,
    buttonLabel: hookCard.buttonLabel || "Save this Gmail attachment",
  };
}

export function buildGmailSessionResultPresentation({
  activeSession = null,
  stagePresentation = {},
} = {}) {
  if (!activeSession) {
    return {
      empty: true,
      emptyText: "Continue Gmail from here when a translation or interpretation step is ready.",
    };
  }

  if (activeSession.kind === "translation") {
    const current = activeSession.current_attachment?.attachment || {};
    return {
      title: stagePresentation.title,
      message: stagePresentation.description,
      label: activeSession.status || "prepared",
      tone: activeSession.completed ? "ok" : "info",
      gridItems: [
        { label: "Subject", value: activeSession.message?.subject || "Unavailable" },
        { label: "Language", value: activeSession.selected_target_lang || "?" },
        { label: "Current document", value: current.filename || "Unavailable", className: "word-break" },
        { label: "Completed attachments", value: (activeSession.confirmed_items || []).length },
      ],
    };
  }

  return {
    title: stagePresentation.title,
    message: stagePresentation.description,
    label: activeSession.status || "prepared",
    tone: "info",
    gridItems: [
      { label: "Notice", value: activeSession.attachment?.attachment?.filename || "Unavailable", className: "word-break" },
      { label: "Subject", value: activeSession.message?.subject || "Unavailable" },
    ],
  };
}
