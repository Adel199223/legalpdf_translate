import {
  deriveGmailPreviewRestoreLabel,
  deriveGmailReviewRestoreLabel,
  isPreviewStateOpen,
} from "./gmail_review_state.js";

export function buildGmailRestoreBarPresentation({
  reviewDrawerMinimized = false,
  reviewDrawerOpen = false,
  loadResult = null,
  previewDrawerMinimized = false,
  previewDrawerOpen = false,
  previewState = null,
  selectedCount = 0,
} = {}) {
  const canRestoreReview = Boolean(
    reviewDrawerMinimized
    && !reviewDrawerOpen
    && loadResult?.ok
    && loadResult?.message,
  );
  const canRestorePreview = Boolean(
    previewDrawerMinimized
    && !previewDrawerOpen
    && isPreviewStateOpen(previewState),
  );
  return {
    review: {
      visible: canRestoreReview,
      label: canRestoreReview ? deriveGmailReviewRestoreLabel({ selectedCount }) : "",
    },
    preview: {
      visible: canRestorePreview,
      label: canRestorePreview ? deriveGmailPreviewRestoreLabel(previewState) : "",
    },
  };
}
