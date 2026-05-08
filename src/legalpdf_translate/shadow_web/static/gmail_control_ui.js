export function renderGmailDrawerDatasetDefaultsInto(body) {
  if (!body) {
    return undefined;
  }

  body.dataset.gmailReviewDrawer = "closed";
  body.dataset.gmailPreviewDrawer = "closed";
  body.dataset.gmailSessionDrawer = "closed";
  body.dataset.gmailBatchFinalizeDrawer = "closed";
  return body;
}

export function renderGmailDrawerChromeInto(nodes = {}, drawer = {}) {
  const { backdrop, body } = nodes || {};
  if (!backdrop) {
    return undefined;
  }

  const open = Boolean(drawer.open);
  backdrop.classList.toggle("hidden", !open);
  backdrop.setAttribute("aria-hidden", open ? "false" : "true");
  const bodyDatasetKey = String(drawer.bodyDatasetKey || "").trim();
  if (body && bodyDatasetKey) {
    body.dataset[bodyDatasetKey] = open ? "open" : "closed";
  }
  return nodes;
}

export function renderGmailReviewChromeInto(nodes = {}, chrome = {}) {
  const { status, openButton } = nodes || {};
  if (!status || !openButton) {
    return undefined;
  }

  openButton.disabled = !Boolean(chrome.available);
  const buttonDataset = openButton.dataset || {};
  if (!buttonDataset.defaultLabel) {
    buttonDataset.defaultLabel = openButton.textContent;
  }
  openButton.textContent = buttonDataset.defaultLabel || "";
  status.textContent = chrome.statusText || "";
  return nodes;
}

export function renderGmailDetailsOpenInto(details, { open = false } = {}) {
  if (!details) {
    return undefined;
  }

  details.open = Boolean(open);
  return details;
}

export function renderGmailInputValueInto(input, value = "") {
  if (!input) {
    return undefined;
  }

  input.value = String(value ?? "");
  return input;
}
