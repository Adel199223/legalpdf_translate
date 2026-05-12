export function buildGmailShellSyncState({
  existingGmail = null,
  bootstrap = null,
  loadResult = null,
  activeSession = null,
  restoredCompletedSession = null,
  interpretationSeed = null,
  suggestedTranslationLaunch = null,
  pendingStatus = undefined,
  pendingIntakeContext = undefined,
  pendingReviewOpen = undefined,
  stage = "",
} = {}) {
  const bootstrapPayload = bootstrap && typeof bootstrap === "object" ? bootstrap : {};
  return {
    ...(existingGmail && typeof existingGmail === "object" ? existingGmail : {}),
    ...bootstrapPayload,
    load_result: loadResult,
    active_session: activeSession,
    restored_completed_session: restoredCompletedSession,
    interpretation_seed: interpretationSeed,
    suggested_translation_launch: suggestedTranslationLaunch,
    pending_status: pendingStatus === undefined ? (bootstrapPayload.pending_status || "") : pendingStatus,
    pending_intake_context: pendingIntakeContext === undefined
      ? (bootstrapPayload.pending_intake_context || {})
      : pendingIntakeContext,
    pending_review_open: pendingReviewOpen === undefined
      ? bootstrapPayload.pending_review_open === true
      : Boolean(pendingReviewOpen),
    stage,
  };
}
