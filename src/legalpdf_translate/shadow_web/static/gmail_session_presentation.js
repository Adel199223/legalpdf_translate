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
