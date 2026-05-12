export function normalizeGmailAttachmentMime(mimeType) {
  return String(mimeType || "").trim().toLowerCase();
}

export function gmailAttachmentMime(attachment) {
  return normalizeGmailAttachmentMime(attachment?.mime_type);
}

export function isGmailPdfMime(mimeType) {
  return normalizeGmailAttachmentMime(mimeType) === "application/pdf";
}

export function isGmailImageMime(mimeType) {
  return normalizeGmailAttachmentMime(mimeType).startsWith("image/");
}

export function isGmailPdfAttachment(attachment) {
  return isGmailPdfMime(gmailAttachmentMime(attachment));
}

export function isGmailImageAttachment(attachment) {
  return isGmailImageMime(gmailAttachmentMime(attachment));
}

export function deriveGmailAttachmentKindLabel(mimeType) {
  if (isGmailPdfMime(mimeType)) {
    return "PDF";
  }
  if (isGmailImageMime(mimeType)) {
    return "Image";
  }
  return "Unknown";
}

export function deriveGmailAttachmentKindLabelForAttachment(attachment) {
  return deriveGmailAttachmentKindLabel(gmailAttachmentMime(attachment));
}

