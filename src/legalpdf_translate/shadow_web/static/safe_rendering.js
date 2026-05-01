export function clearNode(node) {
  if (!node) {
    return null;
  }
  if (typeof node.replaceChildren === "function") {
    node.replaceChildren();
  } else {
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }
  return node;
}

export function setText(node, value) {
  if (!node) {
    return null;
  }
  node.textContent = String(value ?? "");
  return node;
}

export function createTextElement(tagName, value, className = "") {
  const element = document.createElement(tagName);
  if (className) {
    element.className = className;
  }
  setText(element, value);
  return element;
}

export function appendTextElement(parent, tagName, value, className = "") {
  if (!parent) {
    return null;
  }
  const element = createTextElement(tagName, value, className);
  parent.appendChild(element);
  return element;
}

export function setNodeTitle(node, value) {
  if (!node) {
    return null;
  }
  node.title = String(value ?? "");
  return node;
}

export function appendMultilineText(parent, value) {
  if (!parent) {
    return null;
  }
  const text = String(value ?? "");
  const lines = text.split(/\r?\n/);
  lines.forEach((line, index) => {
    if (index > 0) {
      parent.appendChild(document.createElement("br"));
    }
    const span = document.createElement("span");
    span.textContent = line;
    parent.appendChild(span);
  });
  return parent;
}

export function createEmptyState(text, className = "empty-state") {
  const element = document.createElement("div");
  element.className = className;
  setText(element, text);
  return element;
}
