export function normalizeGmailAttachmentList(value) {
  return Array.isArray(value) ? value : [];
}

export function gmailAttachmentId(attachment) {
  return String(attachment?.attachment_id || "");
}

export function gmailAttachmentFilename(attachment, fallback = "Attachment") {
  return String(attachment?.filename || fallback);
}

export function gmailAttachmentDisplayMime(attachment, fallback = "Unknown") {
  return String(attachment?.mime_type || fallback);
}

export function readGmailAttachmentValueById(source, id, fallback = undefined) {
  if (source instanceof Map) {
    return source.has(id) ? source.get(id) : fallback;
  }
  if (source && typeof source === "object" && Object.prototype.hasOwnProperty.call(source, id)) {
    return source[id];
  }
  return fallback;
}

export function formatGmailAttachmentSizeLabel(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(units.length - 1, Math.floor(Math.log(bytes) / Math.log(1024)));
  const scaled = bytes / (1024 ** index);
  const precision = scaled >= 10 || index === 0 ? 0 : 1;
  return `${scaled.toFixed(precision)} ${units[index]}`;
}

