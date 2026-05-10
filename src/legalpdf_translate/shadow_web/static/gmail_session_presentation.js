import { buildGmailStagePresentation } from "./gmail_stage_presentation.js";

const GMAIL_SESSION_BUTTON_IDS = [
  "gmail-load-translation-launch",
  "gmail-confirm-translation",
  "gmail-finalize-batch",
  "gmail-load-interpretation-seed",
  "gmail-finalize-interpretation",
];

export function buildGmailSessionButtonRules({
  activeSession = null,
  translationReady = false,
  interpretationReady = false,
} = {}) {
  const isTranslationSession = activeSession?.kind === "translation";
  const isInterpretationSession = activeSession?.kind === "interpretation";

  return {
    sessionAvailable: Boolean(activeSession),
    rules: [
      [GMAIL_SESSION_BUTTON_IDS[0], isTranslationSession && Boolean(translationReady)],
      [GMAIL_SESSION_BUTTON_IDS[1], isTranslationSession],
      [GMAIL_SESSION_BUTTON_IDS[2], isTranslationSession && Boolean(activeSession?.completed)],
      [GMAIL_SESSION_BUTTON_IDS[3], isInterpretationSession && Boolean(interpretationReady)],
      [GMAIL_SESSION_BUTTON_IDS[4], isInterpretationSession],
    ],
  };
}

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

export function buildGmailWorkspaceStripPresentation({
  show = false,
  loadResult = null,
  activeSession = null,
  cta = {},
  redo = {},
  recoveredAction = {},
  stagePresentation = {},
} = {}) {
  if (!show) {
    return {
      visible: false,
    };
  }

  if (activeSession && cta.visible) {
    const copy = stagePresentation.stripDescription
      || cta.description
      || "Continue the Gmail step when you are ready.";
    return {
      visible: true,
      title: stagePresentation.stripTitle || cta.title || "Continue Gmail step",
      copy: redo.visible ? `${copy} You can also redo only this attachment if needed.` : copy,
      actionLabel: "Continue Gmail step",
      action: cta.action || "",
    };
  }

  if (!loadResult && !activeSession && recoveredAction.visible) {
    return {
      visible: true,
      title: recoveredAction.title || "Last finalized batch is recoverable.",
      copy: recoveredAction.description
        || "Open the recovered result only if you need the previous Gmail finalization details or report.",
      actionLabel: recoveredAction.label || "Open Last Finalization Result",
      action: recoveredAction.action || "",
    };
  }

  return {
    visible: true,
    title: "Gmail attachment ready",
    copy: "Review the Gmail message and attachments before you continue.",
    actionLabel: "Review Gmail message",
    action: "open-intake",
  };
}

function isInterpretationFocusedShell({ activeView = "", interpretationWorkspaceMode = "" } = {}) {
  const normalizedMode = String(interpretationWorkspaceMode || "").trim();
  return activeView === "new-job"
    && (normalizedMode === "gmail_review" || normalizedMode === "gmail_completed");
}

export function buildGmailWorkspaceStripAdapterPresentation({
  activeView = "",
  interpretationWorkspaceMode = "",
  stage = "",
  loadResult = null,
  activeSession = null,
  restoredCompletedSession = null,
  cta = {},
  redo = {},
  recoveredAction = {},
  stagePresentation = null,
} = {}) {
  const show = !isInterpretationFocusedShell({ activeView, interpretationWorkspaceMode })
    && Boolean(loadResult || activeSession || restoredCompletedSession);
  const resolvedStagePresentation = activeSession && cta.visible
    ? (stagePresentation || buildGmailStagePresentation({ stage, activeSession }))
    : {};

  return buildGmailWorkspaceStripPresentation({
    show,
    loadResult,
    activeSession,
    cta,
    redo,
    recoveredAction,
    stagePresentation: resolvedStagePresentation,
  });
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
