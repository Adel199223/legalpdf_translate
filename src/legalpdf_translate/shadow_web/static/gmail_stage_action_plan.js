function emptyPlan() {
  return {
    activeView: "",
    applyTranslationLaunch: false,
    applyInterpretationSeed: false,
    openInterpretationReviewDrawer: false,
    openTranslationCompletionDrawer: false,
    openBatchFinalizeDrawer: false,
    batchFinalizeSource: "",
    openReviewDrawer: false,
    closeSessionDrawer: false,
  };
}

function normalizeAction(value) {
  return String(value || "").trim();
}

function translationResumePlan({ suggestedTranslationLaunch, openTranslationCompletionDrawer = false } = {}) {
  return {
    ...emptyPlan(),
    activeView: "new-job",
    applyTranslationLaunch: Boolean(suggestedTranslationLaunch),
    openTranslationCompletionDrawer: Boolean(openTranslationCompletionDrawer),
    closeSessionDrawer: true,
  };
}

function interpretationResumePlan({ interpretationSeed } = {}) {
  const hasSeed = Boolean(interpretationSeed);
  return {
    ...emptyPlan(),
    activeView: "new-job",
    applyInterpretationSeed: hasSeed,
    openInterpretationReviewDrawer: !hasSeed,
    closeSessionDrawer: true,
  };
}

export function buildGmailStageActionPlan({
  action = "",
  suggestedTranslationLaunch = null,
  interpretationSeed = null,
} = {}) {
  switch (normalizeAction(action)) {
    case "resume-translation-recovery":
    case "resume-translation-prepared":
    case "resume-translation-running":
      return translationResumePlan({ suggestedTranslationLaunch });
    case "resume-translation-save":
      return translationResumePlan({
        suggestedTranslationLaunch,
        openTranslationCompletionDrawer: true,
      });
    case "resume-translation-finalize":
      return {
        ...emptyPlan(),
        openBatchFinalizeDrawer: true,
      };
    case "open-restored-translation-finalize":
      return {
        ...emptyPlan(),
        openBatchFinalizeDrawer: true,
        batchFinalizeSource: "restored",
      };
    case "resume-interpretation-review":
    case "resume-interpretation-finalize":
      return interpretationResumePlan({ interpretationSeed });
    case "review":
      return {
        ...emptyPlan(),
        openReviewDrawer: true,
      };
    case "open-intake":
    default:
      return {
        ...emptyPlan(),
        activeView: "gmail-intake",
      };
  }
}
