const GMAIL_REVIEW_CHROME_STATUS_TEXT = "Step 1: Choose workflow. Step 2: Pick attachment(s). Step 3: Preview or set start page if needed. Step 4: Continue.";

export function buildGmailReviewChromePresentation({ loadResult = null } = {}) {
  return {
    available: Boolean(loadResult?.ok && loadResult?.message),
    statusText: GMAIL_REVIEW_CHROME_STATUS_TEXT,
  };
}
