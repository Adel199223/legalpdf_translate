from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def _run_safe_rendering_probe() -> dict[str, object]:
    script = r"""
const safeRenderingModule = await import(__SAFE_RENDERING_MODULE_URL__);

function createClassList(element) {
  const classes = new Set(String(element.className || "").split(/\s+/).filter(Boolean));
  const sync = () => {
    element.className = Array.from(classes).join(" ");
  };
  return {
    add(...names) {
      names.forEach((name) => classes.add(name));
      sync();
    },
    remove(...names) {
      names.forEach((name) => classes.delete(name));
      sync();
    },
    toggle(name, force) {
      if (force === undefined) {
        if (classes.has(name)) {
          classes.delete(name);
        } else {
          classes.add(name);
        }
      } else if (force) {
        classes.add(name);
      } else {
        classes.delete(name);
      }
      sync();
      return classes.has(name);
    },
    contains(name) {
      return classes.has(name);
    },
  };
}

function makeElement(id = "", initial = {}) {
  const listeners = new Map();
  const element = {
    id,
    tagName: String(initial.tagName || "DIV").toUpperCase(),
    dataset: { ...(initial.dataset || {}) },
    style: {},
    attributes: {},
    className: initial.className || "",
    title: initial.title || "",
    href: initial.href || "",
    value: initial.value || "",
    checked: Boolean(initial.checked),
    disabled: Boolean(initial.disabled),
    hidden: Boolean(initial.hidden),
    open: Boolean(initial.open),
    tabIndex: initial.tabIndex || 0,
    colSpan: initial.colSpan || 1,
    children: [],
    parentNode: null,
    innerHTMLAssignments: [],
    _textContent: String(initial.textContent || ""),
    _innerHTML: String(initial.innerHTML || ""),
    setAttribute(name, value) {
      const next = String(value);
      this.attributes[name] = next;
      if (name === "href") {
        this.href = next;
      } else if (name === "title") {
        this.title = next;
      } else if (name === "class") {
        this.className = next;
      }
    },
    removeAttribute(name) {
      delete this.attributes[name];
      if (name === "href") {
        this.href = "";
      } else if (name === "title") {
        this.title = "";
      }
    },
    appendChild(node) {
      if (!node) {
        return node;
      }
      node.parentNode = this;
      this.children.push(node);
      return node;
    },
    replaceChildren(...nodes) {
      this.children = [];
      nodes.forEach((node) => {
        if (node) {
          node.parentNode = this;
          this.children.push(node);
        }
      });
      this._textContent = "";
      this._innerHTML = "";
    },
    removeChild(node) {
      this.children = this.children.filter((child) => child !== node);
      if (node) {
        node.parentNode = null;
      }
      return node;
    },
    addEventListener(type, handler) {
      if (!listeners.has(type)) {
        listeners.set(type, []);
      }
      listeners.get(type).push(handler);
    },
    async dispatch(type, event = {}) {
      const payload = {
        target: this,
        currentTarget: this,
        preventDefault() {},
        stopPropagation() {},
        ...event,
      };
      for (const handler of listeners.get(type) || []) {
        await handler(payload);
      }
    },
    click() {
      return this.dispatch("click");
    },
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    closest(selector) {
      const normalized = String(selector || "").split(",").map((part) => part.trim().toUpperCase()).filter(Boolean);
      return normalized.includes(this.tagName) ? this : null;
    },
  };
  Object.defineProperty(element, "firstChild", {
    get() {
      return this.children[0] || null;
    },
  });
  Object.defineProperty(element, "textContent", {
    get() {
      if (this.children.length) {
        return `${this._textContent}${this.children.map((child) => child.textContent || "").join("")}`;
      }
      return this._textContent;
    },
    set(value) {
      this._textContent = String(value ?? "");
      this.children = [];
      this._innerHTML = "";
    },
  });
  Object.defineProperty(element, "innerHTML", {
    get() {
      return this._innerHTML;
    },
    set(value) {
      const next = String(value ?? "");
      this._innerHTML = next;
      this._textContent = "";
      this.children = [];
      this.innerHTMLAssignments.push(next);
      const matches = Array.from(next.matchAll(/<\s*([a-zA-Z0-9-]+)/g));
      for (const match of matches) {
        const child = makeElement("", { tagName: match[1] });
        child.parentNode = this;
        this.children.push(child);
      }
    },
  });
  element.classList = createClassList(element);
  return element;
}

function installEnvironment() {
  const elements = new Map();
  function getElement(id) {
    if (!elements.has(id)) {
      elements.set(id, makeElement(id));
    }
    return elements.get(id);
  }

  globalThis.document = {
    body: makeElement("body", { tagName: "BODY", dataset: {} }),
    createElement(tagName) {
      return makeElement("", { tagName });
    },
    getElementById(id) {
      return getElement(id);
    },
    querySelectorAll() {
      return [];
    },
    querySelector() {
      return null;
    },
    addEventListener() {},
  };

  globalThis.window = {
    LEGALPDF_BROWSER_BOOTSTRAP: {
      defaultRuntimeMode: "live",
      defaultWorkspaceId: "workspace-1",
      defaultUiVariant: "qt",
      buildSha: "f70d65c92df8",
      assetVersion: "test-assets",
      staticBasePath: "http://127.0.0.1:8877/static-build/test-assets/",
    },
    location: new URL("http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job"),
    history: {
      replaceState(_state, _title, nextUrl) {
        window.location = new URL(nextUrl, window.location.href);
      },
    },
    dispatchEvent() {},
    addEventListener() {},
    removeEventListener() {},
    setTimeout() {
      return 1;
    },
    clearTimeout() {},
    confirm() {
      return true;
    },
  };

  globalThis.CustomEvent = class CustomEvent {
    constructor(type, init = {}) {
      this.type = type;
      this.detail = init.detail;
    }
  };

  globalThis.fetch = async () => {
    throw new Error("Unexpected fetch during renderer probe.");
  };
}

function walk(node, visit) {
  if (!node) {
    return;
  }
  visit(node);
  for (const child of node.children || []) {
    walk(child, visit);
  }
}

function countTag(node, tagName) {
  let count = 0;
  walk(node, (current) => {
    if (String(current.tagName || "").toUpperCase() === String(tagName).toUpperCase()) {
      count += 1;
    }
  });
  return count;
}

function countInnerHtmlWrites(node) {
  let count = 0;
  walk(node, (current) => {
    count += Array.isArray(current.innerHTMLAssignments) ? current.innerHTMLAssignments.length : 0;
  });
  return count;
}

function collectButtonLabels(node) {
  const labels = [];
  walk(node, (current) => {
    if (String(current.tagName || "").toUpperCase() === "BUTTON") {
      labels.push(current.textContent);
    }
  });
  return labels;
}

function collectTitles(node) {
  const titles = [];
  walk(node, (current) => {
    if (String(current.title || "").trim()) {
      titles.push(current.title);
    }
  });
  return titles;
}

function firstButton(node, label) {
  let found = null;
  walk(node, (current) => {
    if (!found && String(current.tagName || "").toUpperCase() === "BUTTON" && current.textContent === label) {
      found = current;
    }
  });
  return found;
}

installEnvironment();

const appModule = await import(__APP_MODULE_URL__);
const translationModule = await import(__TRANSLATION_MODULE_URL__);
const gmailModule = await import(__GMAIL_MODULE_URL__);

const malicious = '<img src=x onerror=alert(1)>';

const helperElement = safeRenderingModule.createTextElement("span", malicious);

let removedCity = "";
const profileContainer = document.createElement("div");
appModule.renderProfileDistanceRowsInto(profileContainer, [
  { city: malicious, distanceLabel: "12 km one way" },
], {
  onRemove(row) {
    removedCity = row.city;
  },
});
await firstButton(profileContainer, "Delete destination").click();

const recentContainer = document.createElement("div");
appModule.renderRecentJobsInto(
  recentContainer,
  [{
    id: 7,
    job_type: "Translation",
    case_number: malicious,
    case_entity: "Entity <b>unsafe</b>",
    case_city: "Beja<script>",
    service_date: "2026-04-21",
    completed_at: "",
    target_lang: "AR",
  }],
  new Map(),
  new Map([[7, { row: { id: 7 } }]]),
  {
    onOpenTranslation() {},
    onDelete() {},
  },
);

const interpretationHistoryContainer = document.createElement("div");
appModule.renderInterpretationHistoryInto(interpretationHistoryContainer, [{
  row: {
    id: 9,
    case_number: malicious,
    case_entity: "Tribunal <svg>",
    case_city: "Cuba<img>",
    service_date: "2026-05-01",
  },
}], {
  onOpen() {},
  onDelete() {},
});

const translationHistoryContainer = document.createElement("div");
translationModule.renderTranslationHistoryInto(translationHistoryContainer, [{
  row: {
    id: 11,
    job_type: "Translation",
    case_number: malicious,
    case_entity: "Court <b>unsafe</b>",
    case_city: "Beja<img>",
    translation_date: "2026-04-20",
  },
}], {
  onOpen() {},
  onDelete() {},
});

const translationJobsContainer = document.createElement("div");
translationModule.renderTranslationJobsInto(translationJobsContainer, [{
  job_id: "job-1",
  job_kind: "translate",
  status: "completed",
  config: {
    source_path: `C:/tmp/${malicious}.pdf`,
    target_lang: "AR",
  },
  actions: {
    resume: true,
    rebuild: true,
  },
}], {
  onOpen() {},
  onResume() {},
  onRebuild() {},
});

const attachmentTable = document.createElement("tbody");
const startHeading = document.createElement("div");
gmailModule.renderAttachmentListInto(attachmentTable, [{
  attachment_id: "att-1",
  filename: malicious,
  mime_type: "application/pdf",
  size_bytes: 512,
}], {
  startHeading,
  interpretationWorkflow: false,
  focusedAttachmentId: "att-1",
  resolveState() {
    return { selected: true, startPage: 1, pageCount: 4 };
  },
  resolveCanEditStart() {
    return true;
  },
});

const reviewDetailContainer = document.createElement("div");
gmailModule.renderReviewDetailInto(reviewDetailContainer, {
  attachment_id: "att-1",
  filename: malicious,
  mime_type: "application/pdf",
}, {
  state: { selected: true, startPage: 2, pageCount: 4 },
  canEditStart: true,
  previewLoaded: true,
  runtimeGuard: { blocked: false },
  kindLabel: "PDF",
});

const extensionReasonContainer = document.createElement("div");
appModule.renderExtensionPrepareReasonCatalogInto(extensionReasonContainer, [{
  reason: malicious,
  message: `Message ${malicious}`,
}]);
const extensionReasonEmptyContainer = document.createElement("div");
appModule.renderExtensionPrepareReasonCatalogInto(extensionReasonEmptyContainer, []);

console.log(JSON.stringify({
  safeHelperText: helperElement.textContent,
  profile: {
    text: profileContainer.textContent,
    imgCount: countTag(profileContainer, "IMG"),
    buttonLabels: collectButtonLabels(profileContainer),
    innerHTMLWrites: countInnerHtmlWrites(profileContainer),
    removedCity,
  },
  recentWork: {
    text: recentContainer.textContent,
    imgCount: countTag(recentContainer, "IMG"),
    buttonLabels: collectButtonLabels(recentContainer),
    innerHTMLWrites: countInnerHtmlWrites(recentContainer),
  },
  interpretationHistory: {
    text: interpretationHistoryContainer.textContent,
    imgCount: countTag(interpretationHistoryContainer, "IMG"),
    buttonLabels: collectButtonLabels(interpretationHistoryContainer),
    innerHTMLWrites: countInnerHtmlWrites(interpretationHistoryContainer),
  },
  translationHistory: {
    text: translationHistoryContainer.textContent,
    imgCount: countTag(translationHistoryContainer, "IMG"),
    buttonLabels: collectButtonLabels(translationHistoryContainer),
    innerHTMLWrites: countInnerHtmlWrites(translationHistoryContainer),
  },
  translationJobs: {
    text: translationJobsContainer.textContent,
    imgCount: countTag(translationJobsContainer, "IMG"),
    buttonLabels: collectButtonLabels(translationJobsContainer),
    titles: collectTitles(translationJobsContainer),
    innerHTMLWrites: countInnerHtmlWrites(translationJobsContainer),
  },
  gmailAttachments: {
    text: attachmentTable.textContent,
    imgCount: countTag(attachmentTable, "IMG"),
    innerHTMLWrites: countInnerHtmlWrites(attachmentTable),
    startHeading: startHeading.textContent,
  },
  gmailReviewDetail: {
    text: reviewDetailContainer.textContent,
    imgCount: countTag(reviewDetailContainer, "IMG"),
    buttonLabels: collectButtonLabels(reviewDetailContainer),
    innerHTMLWrites: countInnerHtmlWrites(reviewDetailContainer),
  },
  extensionReasonCatalog: {
    text: extensionReasonContainer.textContent,
    imgCount: countTag(extensionReasonContainer, "IMG"),
    scriptCount: countTag(extensionReasonContainer, "SCRIPT"),
    innerHTMLWrites: countInnerHtmlWrites(extensionReasonContainer),
  },
  extensionReasonCatalogEmpty: {
    text: extensionReasonEmptyContainer.textContent,
    imgCount: countTag(extensionReasonEmptyContainer, "IMG"),
    scriptCount: countTag(extensionReasonEmptyContainer, "SCRIPT"),
    innerHTMLWrites: countInnerHtmlWrites(extensionReasonEmptyContainer),
  },
}));
"""
    return run_browser_esm_json_probe(
        script,
        {
            "__SAFE_RENDERING_MODULE_URL__": "safe_rendering.js",
            "__APP_MODULE_URL__": "app.js",
            "__TRANSLATION_MODULE_URL__": "translation.js",
            "__GMAIL_MODULE_URL__": "gmail.js",
        },
        timeout_seconds=30,
    )


def test_browser_dynamic_renderers_treat_external_values_as_text() -> None:
    results = _run_safe_rendering_probe()

    assert results["safeHelperText"] == '<img src=x onerror=alert(1)>'

    assert '<img src=x onerror=alert(1)>' in results["profile"]["text"]
    assert results["profile"]["imgCount"] == 0
    assert results["profile"]["innerHTMLWrites"] == 0
    assert "Delete destination" in results["profile"]["buttonLabels"]
    assert results["profile"]["removedCity"] == '<img src=x onerror=alert(1)>'

    assert '<img src=x onerror=alert(1)>' in results["recentWork"]["text"]
    assert "Entity <b>unsafe</b>" in results["recentWork"]["text"]
    assert results["recentWork"]["imgCount"] == 0
    assert results["recentWork"]["innerHTMLWrites"] == 0
    assert results["recentWork"]["buttonLabels"] == ["Open", "Delete record"]

    assert '<img src=x onerror=alert(1)>' in results["interpretationHistory"]["text"]
    assert "Tribunal <svg>" in results["interpretationHistory"]["text"]
    assert results["interpretationHistory"]["imgCount"] == 0
    assert results["interpretationHistory"]["innerHTMLWrites"] == 0
    assert results["interpretationHistory"]["buttonLabels"] == ["Open", "Delete record"]

    assert '<img src=x onerror=alert(1)>' in results["translationHistory"]["text"]
    assert "Court <b>unsafe</b>" in results["translationHistory"]["text"]
    assert results["translationHistory"]["imgCount"] == 0
    assert results["translationHistory"]["innerHTMLWrites"] == 0
    assert results["translationHistory"]["buttonLabels"] == ["Open", "Delete record"]

    assert '<img src=x onerror=alert(1)>.pdf' in results["translationJobs"]["text"]
    assert results["translationJobs"]["imgCount"] == 0
    assert results["translationJobs"]["innerHTMLWrites"] == 0
    assert results["translationJobs"]["buttonLabels"] == ["Open run", "Resume", "Rebuild DOCX"]
    assert results["translationJobs"]["titles"] == ['C:/tmp/<img src=x onerror=alert(1)>.pdf']

    assert '<img src=x onerror=alert(1)>' in results["gmailAttachments"]["text"]
    assert results["gmailAttachments"]["imgCount"] == 0
    assert results["gmailAttachments"]["innerHTMLWrites"] == 0
    assert results["gmailAttachments"]["startHeading"] == "Start page"

    assert '<img src=x onerror=alert(1)>' in results["gmailReviewDetail"]["text"]
    assert results["gmailReviewDetail"]["imgCount"] == 0
    assert results["gmailReviewDetail"]["innerHTMLWrites"] == 0
    assert results["gmailReviewDetail"]["buttonLabels"] == ["Preview"]

    assert '<img src=x onerror=alert(1)>' in results["extensionReasonCatalog"]["text"]
    assert "Message <img src=x onerror=alert(1)>" in results["extensionReasonCatalog"]["text"]
    assert "Code: <img src=x onerror=alert(1)>" in results["extensionReasonCatalog"]["text"]
    assert results["extensionReasonCatalog"]["imgCount"] == 0
    assert results["extensionReasonCatalog"]["scriptCount"] == 0
    assert results["extensionReasonCatalog"]["innerHTMLWrites"] == 0

    assert results["extensionReasonCatalogEmpty"]["text"] == "No prepare reasons are available."
    assert results["extensionReasonCatalogEmpty"]["imgCount"] == 0
    assert results["extensionReasonCatalogEmpty"]["scriptCount"] == 0
    assert results["extensionReasonCatalogEmpty"]["innerHTMLWrites"] == 0
