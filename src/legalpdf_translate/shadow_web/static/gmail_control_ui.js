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
