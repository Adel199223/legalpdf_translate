// Per-document wording is scoped to the active Gmail batch, never saved defaults.
export function renderGmailFeeOptions(nodes, { ownerKey = "", editable = false } = {}) {
  if (!nodes.group) return;
  if (nodes.group.dataset.ownerKey !== ownerKey) {
    nodes.group.dataset.ownerKey = ownerKey;
    nodes.recipient.value = "";
    nodes.include.checked = false;
    nodes.declaration.value = nodes.declaration.defaultValue;
  }
  nodes.group.disabled = !editable;
  nodes.declaration.disabled = !editable || !nodes.include.checked;
  nodes.declarationField.hidden = !nodes.include.checked;
}

export function readGmailFeeOptions(nodes) {
  return {
    recipientBlock: nodes.recipient?.value || "",
    includeTranslatorDeclaration: Boolean(nodes.include?.checked),
    translatorDeclarationText: nodes.include?.checked ? (nodes.declaration?.value || "") : "",
  };
}
