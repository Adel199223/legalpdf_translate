import { clearNode, createEmptyState, createTextElement } from "./safe_rendering.js";

function setValueWhenBlank(node, value) {
  if (!node) {
    return;
  }
  if (String(node.value || "").trim()) {
    return;
  }
  node.value = String(value ?? "");
}

export function renderExtensionSimulatorDefaultsInto(nodes = {}, defaults = {}) {
  const {
    messageId = null,
    threadId = null,
    subject = null,
    accountEmail = null,
  } = nodes || {};
  const source = defaults || {};
  setValueWhenBlank(messageId, source.message_id);
  setValueWhenBlank(threadId, source.thread_id);
  setValueWhenBlank(subject, source.subject);
  setValueWhenBlank(accountEmail, source.account_email);
}

export function renderExtensionPrepareReasonCatalogInto(container, items = []) {
  if (!container) {
    return;
  }
  clearNode(container);
  if (!items.length) {
    container.appendChild(createEmptyState("No prepare reasons are available."));
    return;
  }
  for (const item of items) {
    const card = document.createElement("article");
    card.className = "history-item";
    const body = document.createElement("div");
    body.appendChild(createTextElement("strong", item?.message || "No message available."));
    body.appendChild(createTextElement("p", `Code: ${item?.reason || "Unknown reason"}`));
    card.appendChild(body);
    container.appendChild(card);
  }
}
