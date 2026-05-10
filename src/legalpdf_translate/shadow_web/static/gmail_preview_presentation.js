function positiveNumber(value, fallback = 1) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

function nonnegativeNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0;
}

function attachmentFilename(attachment, fallback) {
  return String(attachment?.filename || fallback);
}

export function buildGmailPreviewLoadedDiagnosticsPresentation({
  payload = null,
  attachment = null,
} = {}) {
  const filename = attachmentFilename(
    payload?.normalized_payload?.attachment || attachment,
    "attachment",
  );
  return {
    hint: `Preview loaded for ${filename}.`,
    open: false,
  };
}

function resetControls() {
  return {
    applyDisabled: true,
    applyLabel: "",
    pageDisabled: true,
    prevDisabled: true,
    nextDisabled: true,
    pageMin: "1",
    pageMax: "1",
    pageValue: "1",
  };
}

function emptyPreviewPresentation() {
  return {
    summary: {
      kind: "empty",
      className: "result-card empty-state",
      text: "Preview is optional. Open it when you want to check the document more closely.",
    },
    openTab: { visible: false, href: "#" },
    controls: resetControls(),
    body: {
      kind: "empty",
      className: "gmail-inline-preview empty-state",
      text: "Preview opens here when requested.",
    },
    statusText: "Preview is optional. Use it if you want to check the document or choose a later start page.",
    shouldRenderPdfCanvas: false,
  };
}

function previewSummary({ attachment, page, pageCount, canApply }) {
  return {
    kind: "card",
    title: attachmentFilename(attachment, "Attachment preview"),
    message: pageCount > 0 ? `${pageCount} page(s) available` : "Preview ready",
    label: canApply ? `Page ${page}` : "Inspect only",
    tone: canApply ? "info" : "ok",
  };
}

function pdfControls({ page, pageCount, canApply }) {
  return {
    applyDisabled: !canApply,
    applyLabel: canApply ? "" : "Preview only",
    pageDisabled: false,
    prevDisabled: page <= 1,
    nextDisabled: pageCount > 0 ? page >= pageCount : false,
    pageMin: "1",
    pageMax: String(Math.max(1, pageCount || page)),
    pageValue: String(page),
  };
}

function previewOnlyControls() {
  return {
    ...resetControls(),
    applyLabel: "Preview only",
  };
}

function pdfStatusText({ page, pageCount, canApply }) {
  if (canApply) {
    return pageCount > 0
      ? `Previewing page ${page} of ${pageCount}. Use current page if you want the translation to start later in the document.`
      : `Previewing page ${page}. Use current page if you want the translation to start later in the document.`;
  }
  return pageCount > 0
    ? `Previewing page ${page} of ${pageCount}. This workflow still continues from page 1.`
    : `Previewing page ${page}. This workflow still continues from page 1.`;
}

export function buildGmailPreviewPanelPresentation({
  attachment = null,
  href = "",
  page = 1,
  pageCount = 0,
  canApply = false,
  isPdf = false,
  isImage = false,
} = {}) {
  const previewHref = String(href || "");
  if (!attachment || !previewHref) {
    return emptyPreviewPresentation();
  }

  const nextPage = positiveNumber(page, 1);
  const nextPageCount = nonnegativeNumber(pageCount);
  const applyAllowed = Boolean(canApply);
  const summary = previewSummary({
    attachment,
    page: nextPage,
    pageCount: nextPageCount,
    canApply: applyAllowed,
  });
  const openTab = { visible: true, href: previewHref };

  if (isPdf) {
    return {
      summary,
      openTab,
      controls: pdfControls({ page: nextPage, pageCount: nextPageCount, canApply: applyAllowed }),
      body: {
        kind: "pdf",
        className: "gmail-inline-preview",
        shellClassName: "gmail-inline-preview-canvas-shell",
        canvasId: "gmail-preview-canvas",
        canvasClassName: "gmail-inline-preview-canvas",
        canvasAriaLabel: `Preview for ${attachmentFilename(attachment, "attachment")}`,
      },
      statusText: pdfStatusText({ page: nextPage, pageCount: nextPageCount, canApply: applyAllowed }),
      shouldRenderPdfCanvas: true,
    };
  }

  if (isImage) {
    return {
      summary,
      openTab,
      controls: previewOnlyControls(),
      body: {
        kind: "image",
        className: "gmail-inline-preview",
        shellClassName: "gmail-inline-preview-image-shell",
        imageClassName: "gmail-inline-preview-image",
        src: previewHref,
        alt: attachmentFilename(attachment, "Attachment preview"),
      },
      statusText: "Image preview is shown inline. Start page stays fixed at 1 for this attachment.",
      shouldRenderPdfCanvas: false,
    };
  }

  return {
    summary,
    openTab,
    controls: previewOnlyControls(),
    body: {
      kind: "fallback",
      className: "gmail-inline-preview empty-state",
      leadingText: "Open ",
      strongText: attachmentFilename(attachment, "the preview"),
      trailingText: " in a new tab for a full attachment view.",
    },
    statusText: "This attachment type is available through the new-tab fallback.",
    shouldRenderPdfCanvas: false,
  };
}
