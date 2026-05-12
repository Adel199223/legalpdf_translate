function noop() {}

function attachmentMime(attachment) {
  return String(attachment?.mime_type || "").trim().toLowerCase();
}

function defaultIsPdfAttachment(attachment) {
  return attachmentMime(attachment) === "application/pdf";
}

function safeBrowserPdfState(getBrowserPdfAttachmentState, attachmentId) {
  if (typeof getBrowserPdfAttachmentState !== "function") {
    return {};
  }
  return getBrowserPdfAttachmentState(attachmentId) || {};
}

export function buildGmailAttachmentPreviewRequestPayload({ attachmentId } = {}) {
  return { attachment_id: attachmentId };
}

export function buildGmailBrowserPdfAttachmentStateFromPreviewPayload({ payload } = {}) {
  const normalized = payload?.normalized_payload || {};
  return {
    sourcePath: normalized.preview_path || "",
    previewHref: normalized.preview_href || "",
    pageCount: normalized.page_count || 0,
  };
}

export async function fetchGmailAttachmentPreviewPayload({
  attachmentId,
  fetchJson,
  appState,
  setBrowserPdfAttachmentState = noop,
  applyPreviewPageCount = noop,
} = {}) {
  if (typeof fetchJson !== "function") {
    throw new TypeError("fetchJson is required to load a Gmail attachment preview.");
  }
  const payload = await fetchJson("/api/gmail/preview-attachment", appState, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(buildGmailAttachmentPreviewRequestPayload({ attachmentId })),
  });
  const normalized = payload?.normalized_payload || {};
  setBrowserPdfAttachmentState(
    attachmentId,
    buildGmailBrowserPdfAttachmentStateFromPreviewPayload({ payload }),
  );
  if (normalized.page_count) {
    applyPreviewPageCount(attachmentId, normalized.page_count);
  }
  return payload;
}

export async function ensureGmailBrowserPdfBundleForAttachment({
  attachment,
  previewPayload = null,
  appState,
  isPdfAttachment = defaultIsPdfAttachment,
  getBrowserPdfAttachmentState,
  setBrowserPdfAttachmentState = noop,
  applyPreviewPageCount = noop,
  ensureBrowserPdfBundleFromUrl,
  fetchAttachmentPreviewPayload,
} = {}) {
  if (!attachment || !isPdfAttachment(attachment)) {
    return {
      pageCount: 1,
      sourcePath: "",
      previewHref: "",
    };
  }
  let payload = previewPayload;
  let browserState = safeBrowserPdfState(getBrowserPdfAttachmentState, attachment.attachment_id);
  if (!payload && (!browserState.sourcePath || !browserState.previewHref)) {
    if (typeof fetchAttachmentPreviewPayload !== "function") {
      throw new TypeError("fetchAttachmentPreviewPayload is required to prepare a Gmail PDF preview.");
    }
    payload = await fetchAttachmentPreviewPayload(attachment.attachment_id);
    browserState = safeBrowserPdfState(getBrowserPdfAttachmentState, attachment.attachment_id);
  }
  const sourcePath = String(
    browserState.sourcePath || payload?.normalized_payload?.preview_path || "",
  ).trim();
  const previewHref = String(
    browserState.previewHref || payload?.normalized_payload?.preview_href || "",
  ).trim();
  if (!sourcePath || !previewHref) {
    throw new Error(`Preview download for ${attachment.filename || "the PDF attachment"} is unavailable.`);
  }
  if (typeof ensureBrowserPdfBundleFromUrl !== "function") {
    throw new TypeError("ensureBrowserPdfBundleFromUrl is required to prepare a Gmail PDF preview.");
  }
  const bundlePayload = await ensureBrowserPdfBundleFromUrl({
    appState,
    sourcePath,
    url: previewHref,
    attachmentId: attachment.attachment_id,
  });
  const pageCount = Math.max(1, Number(bundlePayload?.page_count || browserState.pageCount || 0));
  applyPreviewPageCount(attachment.attachment_id, pageCount);
  setBrowserPdfAttachmentState(attachment.attachment_id, {
    sourcePath,
    previewHref,
    pageCount,
  });
  return {
    pageCount,
    sourcePath,
    previewHref,
  };
}

export async function ensureGmailBrowserPdfBundlesForSelections({
  attachments = [],
  getAttachmentState = () => ({}),
  ensureBrowserPdfBundleForAttachment,
  isPdfAttachment = defaultIsPdfAttachment,
} = {}) {
  const selectedAttachments = (attachments || []).filter((attachment) => (
    getAttachmentState(attachment?.attachment_id).selected
  ));
  for (const attachment of selectedAttachments) {
    if (!isPdfAttachment(attachment)) {
      continue;
    }
    if (typeof ensureBrowserPdfBundleForAttachment !== "function") {
      throw new TypeError("ensureBrowserPdfBundleForAttachment is required to prepare Gmail PDF previews.");
    }
    await ensureBrowserPdfBundleForAttachment(attachment);
  }
}
