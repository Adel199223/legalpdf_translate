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

function activeAttachmentFilename(activeSession) {
  if (activeSession?.kind === "translation") {
    return String(activeSession.current_attachment?.attachment?.filename || "").trim();
  }
  if (activeSession?.kind === "interpretation") {
    return String(activeSession.attachment?.attachment?.filename || "").trim();
  }
  return "";
}

export function buildGmailStagePresentation({ stage, activeSession } = {}) {
  const normalizedStage = normalizeGmailStage(stage);
  const filename = activeAttachmentFilename(activeSession) || "this attachment";
  switch (normalizedStage) {
    case "translation_recovery":
      return {
        title: "Translation needs attention.",
        description: `${filename} needs recovery before the Gmail reply can continue.`,
        stripTitle: "Continue Gmail step",
        stripDescription: `${filename} needs recovery before you can keep going.`,
      };
    case "translation_prepared":
      return {
        title: "Translation is ready to start.",
        description: `${filename} is prepared in the translation screen. Review the settings there and start when you are ready.`,
        stripTitle: "Translation is ready to start",
        stripDescription: "Continue the Gmail step to review the seeded translation settings and start when you are ready.",
      };
    case "translation_running":
      return {
        title: "Translation is running.",
        description: `${filename} is already in progress. Continue the Gmail step when you want to review progress or the next action.`,
        stripTitle: "Translation is running",
        stripDescription: "Continue the Gmail step to review progress and the next action for this attachment.",
      };
    case "translation_save":
      return {
        title: "Review and save this attachment.",
        description: "Return to the finish step to confirm the translation details and save the current attachment.",
        stripTitle: "Review and save this attachment",
        stripDescription: "Continue the Gmail step to review and save the current attachment.",
      };
    case "translation_finalize":
      if (activeSession?.finalization_state === "draft_ready") {
        return {
          title: "Finalize Gmail reply.",
          description: "The Gmail reply is ready to review. Open the final step to check the final files or report.",
          stripTitle: "Finalize Gmail reply",
          stripDescription: "Continue the Gmail step to review the final Gmail reply and saved files.",
        };
      }
      if (activeSession?.finalization_state === "draft_failed") {
        return {
          title: "Finalize Gmail reply.",
          description: "The final Gmail reply still needs attention. Continue the final step to retry or review the report.",
          stripTitle: "Finalize Gmail reply",
          stripDescription: "Continue the Gmail step to finish the Gmail reply or review what still needs attention.",
        };
      }
      return {
        title: "Finalize Gmail reply.",
        description: "All selected attachments are ready. Continue the final step when you want to finish the Gmail reply.",
        stripTitle: "Finalize Gmail reply",
        stripDescription: "Continue the Gmail step to finish the Gmail reply when you are ready.",
      };
    case "interpretation_review":
      return {
        title: "Interpretation details are ready.",
        description: "Continue the interpretation review to check the notice details before you create the Gmail reply.",
        stripTitle: "Gmail interpretation ready",
        stripDescription: "Continue the Gmail step to review the notice details and create the Gmail reply.",
      };
    case "interpretation_finalize":
      return {
        title: "Create Gmail reply.",
        description: "The notice details and final files are ready for the Gmail reply step.",
        stripTitle: "Create Gmail reply",
        stripDescription: "Continue the Gmail step to create the interpretation reply.",
      };
    case "review":
      return {
        title: "Review Gmail attachments.",
        description: "Choose your workflow, pick the attachment you want, and continue when you are ready.",
        stripTitle: "Gmail attachment ready",
        stripDescription: "Review the Gmail message and attachments before you continue.",
      };
    default:
      return {
        title: "Review Gmail attachments.",
        description: "Open this from Gmail or load a message manually from details.",
        stripTitle: "Gmail attachment ready",
        stripDescription: "Review the Gmail message and attachments before you continue.",
      };
  }
}

export function buildGmailHomeCtaPresentation({
  stage,
  activeSession,
  stagePresentation = null,
} = {}) {
  const presentation = stagePresentation || buildGmailStagePresentation({ stage, activeSession });
  switch (normalizeGmailStage(stage)) {
    case "translation_recovery":
      return {
        visible: true,
        label: "Resume Recovery",
        action: "resume-translation-recovery",
        title: presentation.title,
        description: presentation.description,
        tone: "warn",
      };
    case "translation_prepared":
      return {
        visible: true,
        label: "Continue Current Step",
        action: "resume-translation-prepared",
        title: presentation.title,
        description: presentation.description,
        tone: "ok",
      };
    case "translation_running":
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-translation-running",
        title: presentation.title,
        description: presentation.description,
        tone: "info",
      };
    case "translation_save":
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-translation-save",
        title: presentation.title,
        description: presentation.description,
        tone: "ok",
      };
    case "translation_finalize":
      if (activeSession?.finalization_state === "draft_ready") {
        return {
          visible: true,
          label: "Continue Current Step",
          action: "resume-translation-finalize",
          title: presentation.title,
          description: presentation.description,
          tone: "ok",
        };
      }
      if (activeSession?.finalization_state === "draft_failed") {
        return {
          visible: true,
          label: "Resume Current Step",
          action: "resume-translation-finalize",
          title: presentation.title,
          description: presentation.description,
          tone: "info",
        };
      }
      if (activeSession?.finalization_state === "local_artifacts_ready") {
        return {
          visible: true,
          label: "Resume Current Step",
          action: "resume-translation-finalize",
          title: presentation.title,
          description: presentation.description,
          tone: "info",
        };
      }
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-translation-finalize",
        title: presentation.title,
        description: presentation.description,
        tone: "ok",
      };
    case "interpretation_review":
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-interpretation-review",
        title: presentation.title,
        description: presentation.description,
        tone: "info",
      };
    case "interpretation_finalize":
      return {
        visible: true,
        label: "Resume Current Step",
        action: "resume-interpretation-finalize",
        title: presentation.title,
        description: presentation.description,
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
