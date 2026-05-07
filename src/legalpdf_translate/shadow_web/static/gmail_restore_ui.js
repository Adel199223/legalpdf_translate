export function renderGmailRestoreBarInto(nodes = {}, restore = {}) {
  const { bar, reviewButton, previewButton } = nodes || {};
  if (!bar || !reviewButton || !previewButton) {
    return undefined;
  }

  const review = restore.review || {};
  const preview = restore.preview || {};
  const reviewVisible = Boolean(review.visible);
  const previewVisible = Boolean(preview.visible);

  reviewButton.classList.toggle("hidden", !reviewVisible);
  reviewButton.disabled = !reviewVisible;
  if (reviewVisible) {
    reviewButton.textContent = review.label || "";
  }

  previewButton.classList.toggle("hidden", !previewVisible);
  previewButton.disabled = !previewVisible;
  if (previewVisible) {
    previewButton.textContent = preview.label || "";
  }

  bar.classList.toggle("hidden", !(reviewVisible || previewVisible));
  return nodes;
}
