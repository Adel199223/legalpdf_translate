import { isPreviewStateOpen } from "./gmail_review_state.js";

const GMAIL_REVIEW_CHROME_STATUS_TEXT = "Step 1: Choose workflow. Step 2: Pick attachment(s). Step 3: Preview or set start page if needed. Step 4: Continue.";
const GMAIL_REVIEW_LOAD_FALLBACK_MESSAGE = "Gmail message load complete.";
const GMAIL_DEMO_REVIEW_LOAD_MESSAGE = "Demo Gmail attachments loaded for shadow review.";

function isCompletedTranslationSession(session) {
  return Boolean(session?.kind === "translation" && session?.completed);
}

export function buildGmailReviewChromePresentation({ loadResult = null } = {}) {
  return {
    available: Boolean(loadResult?.ok && loadResult?.message),
    statusText: GMAIL_REVIEW_CHROME_STATUS_TEXT,
  };
}

export function buildGmailReviewDrawerChromePresentation({
  open = false,
  loadResult = null,
} = {}) {
  return {
    open: Boolean(open && loadResult?.ok && loadResult?.message),
    bodyDatasetKey: "gmailReviewDrawer",
  };
}

export function buildGmailPreviewDrawerChromePresentation({
  open = false,
  previewState = null,
} = {}) {
  return {
    open: Boolean(open && isPreviewStateOpen(previewState)),
    bodyDatasetKey: "gmailPreviewDrawer",
  };
}

export function buildGmailSessionDrawerChromePresentation({
  open = false,
  activeSession = null,
} = {}) {
  return {
    open: Boolean(open && activeSession),
    bodyDatasetKey: "gmailSessionDrawer",
  };
}

export function buildGmailBatchFinalizeDrawerChromePresentation({
  open = false,
  source = "active",
  activeSession = null,
  restoredCompletedSession = null,
} = {}) {
  const normalizedSource = String(source || "").trim() === "restored" ? "restored" : "active";
  const activeOpen = Boolean(open && isCompletedTranslationSession(activeSession));
  const restoredOpen = Boolean(
    open
    && normalizedSource === "restored"
    && isCompletedTranslationSession(restoredCompletedSession),
  );
  return {
    open: activeOpen || restoredOpen,
    bodyDatasetKey: "gmailBatchFinalizeDrawer",
  };
}

export function buildGmailReviewLoadOutcomePresentation({
  source = "message",
  payload = null,
  loadResult,
} = {}) {
  const normalizedSource = String(source || "message").trim() === "demo" ? "demo" : "message";
  const payloadLoadResult = payload?.normalized_payload?.load_result || null;
  const activeLoadResult = loadResult === undefined ? payloadLoadResult : loadResult;
  const shouldOpenReviewDrawer = Boolean(activeLoadResult?.ok && activeLoadResult?.message);

  if (normalizedSource === "demo") {
    return {
      panelStatus: {
        tone: "ok",
        message: GMAIL_DEMO_REVIEW_LOAD_MESSAGE,
      },
      diagnostics: {
        hint: GMAIL_DEMO_REVIEW_LOAD_MESSAGE,
        open: false,
      },
      reviewDrawer: {
        open: shouldOpenReviewDrawer,
      },
      intakeDetails: {
        close: false,
      },
    };
  }

  const payloadStatus = String(payload?.status || "").trim();
  const statusMessage = payloadLoadResult?.status_message || GMAIL_REVIEW_LOAD_FALLBACK_MESSAGE;
  return {
    panelStatus: {
      tone: payloadStatus === "ok" ? "ok" : payloadStatus === "unavailable" ? "warn" : "bad",
      message: statusMessage,
    },
    diagnostics: {
      hint: statusMessage,
      open: payloadStatus !== "ok",
    },
    reviewDrawer: {
      open: shouldOpenReviewDrawer,
    },
    intakeDetails: {
      close: true,
    },
  };
}
