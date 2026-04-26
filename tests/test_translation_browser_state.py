import functools

from .browser_esm_probe import run_browser_esm_json_probe


def _run_translation_browser_state_probe() -> dict[str, object]:
    script = r"""
const stateModuleUrl = __STATE_MODULE_URL__;
const translationModuleUrl = __TRANSLATION_MODULE_URL__;
const dashboardModuleUrl = __DASHBOARD_MODULE_URL__;

function tagNameForId(id) {
  if (
    id.startsWith("translation-source-file")
    || id.startsWith("translation-output-dir")
    || id.startsWith("translation-source-path")
    || id.startsWith("translation-job-id")
    || id.startsWith("translation-row-id")
    || id.startsWith("translation-context-text")
    || id.startsWith("translation-glossary-file")
    || id.startsWith("translation-context-file")
    || id.startsWith("translation-date")
    || id.startsWith("translation-case-")
    || id.startsWith("translation-court-email")
    || id.startsWith("translation-run-id")
    || id.startsWith("translation-pages")
    || id.startsWith("translation-word-count")
    || id.startsWith("translation-total-tokens")
    || id.startsWith("translation-rate-per-word")
    || id.startsWith("translation-expected-total")
    || id.startsWith("translation-amount-paid")
    || id.startsWith("translation-api-cost")
    || id.startsWith("translation-estimated-api-cost")
    || id.startsWith("translation-quality-risk-score")
    || id.startsWith("translation-profit")
  ) {
    return "INPUT";
  }
  if (
    id === "translation-target-lang"
    || id === "translation-effort"
    || id === "translation-effort-policy"
    || id === "translation-image-mode"
    || id === "translation-ocr-mode"
    || id === "translation-ocr-engine"
  ) {
    return "SELECT";
  }
  if (
    id.includes("browse")
    || id.includes("start")
    || id.includes("analyze")
    || id.includes("cancel")
    || id.includes("resume")
    || id.includes("rebuild")
    || id.includes("review-export")
    || id.includes("generate-report")
    || id.includes("save-row")
    || id.includes("open")
    || id.includes("continue")
    || id.includes("close")
    || id.includes("clear")
    || id.includes("refresh")
    || id.includes("new-save")
  ) {
    return "BUTTON";
  }
  if (id.includes("download-")) {
    return "A";
  }
  return "DIV";
}

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
    tagName: (initial.tagName || tagNameForId(id)).toUpperCase(),
    value: initial.value || "",
    textContent: initial.textContent || "",
    innerHTML: initial.innerHTML || "",
    checked: Boolean(initial.checked),
    href: initial.href || "",
    open: Boolean(initial.open),
    disabled: Boolean(initial.disabled),
    hidden: Boolean(initial.hidden),
    className: initial.className || "",
    dataset: { ...(initial.dataset || {}) },
    style: {},
    files: initial.files || [],
    children: [],
    attributes: {},
    clickCount: 0,
    setAttribute(name, value) {
      this.attributes[name] = String(value);
      if (name === "href") {
        this.href = String(value);
      }
    },
    removeAttribute(name) {
      delete this.attributes[name];
      if (name === "href") {
        this.href = "";
      }
    },
    appendChild(node) {
      this.children.push(node);
      return node;
    },
    replaceChildren(...nodes) {
      this.children = nodes;
    },
    addEventListener(type, handler) {
      if (!listeners.has(type)) {
        listeners.set(type, []);
      }
      listeners.get(type).push(handler);
    },
    removeEventListener(type, handler) {
      if (!listeners.has(type)) {
        return;
      }
      listeners.set(type, listeners.get(type).filter((item) => item !== handler));
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
    querySelector() {
      return null;
    },
    closest(selector) {
      const normalized = String(selector || "")
        .split(",")
        .map((part) => part.trim().toUpperCase())
        .filter(Boolean);
      return normalized.includes(this.tagName) ? this : null;
    },
    click() {
      this.clickCount += 1;
      return this.dispatch("click");
    },
  };
  element.classList = createClassList(element);
  return element;
}

function installEnvironment(url) {
  const elements = new Map();
  const documentListeners = new Map();
  const fetchCalls = [];
  const fetchQueue = [];

  function getElement(id) {
    if (!elements.has(id)) {
      elements.set(id, makeElement(id));
    }
    return elements.get(id);
  }

  globalThis.document = {
    body: makeElement("body", { tagName: "BODY", dataset: {} }),
    getElementById(id) {
      return getElement(id);
    },
    querySelectorAll() {
      return [];
    },
    createElement(tagName) {
      return makeElement("", { tagName });
    },
    addEventListener(type, handler) {
      if (!documentListeners.has(type)) {
        documentListeners.set(type, []);
      }
      documentListeners.get(type).push(handler);
    },
    async dispatch(type, event = {}) {
      for (const handler of documentListeners.get(type) || []) {
        await handler({ preventDefault() {}, stopPropagation() {}, ...event });
      }
    },
  };

  globalThis.window = {
    LEGALPDF_BROWSER_BOOTSTRAP: {
      defaultRuntimeMode: "live",
      defaultWorkspaceId: "workspace-1",
      defaultUiVariant: "qt",
      shadowHost: "127.0.0.1",
      shadowPort: 8877,
      buildSha: "f70d65c92df8",
      assetVersion: "test-assets",
      staticBasePath: "http://127.0.0.1:8877/static-build/test-assets/",
    },
    location: new URL(url),
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

  globalThis.DataTransfer = class DataTransfer {
    constructor() {
      this._files = [];
      this.items = {
        add: (file) => {
          this._files.push(file);
        },
      };
    }

    get files() {
      return this._files;
    }
  };

  globalThis.fetch = async (path, options = {}) => {
    const call = {
      path: String(path),
      method: String(options.method || "GET").toUpperCase(),
      body: options.body ?? null,
    };
    fetchCalls.push(call);
    const next = fetchQueue.shift();
    if (!next) {
      throw new Error(`Unexpected fetch: ${call.path}`);
    }
    return await next(call);
  };

  return {
    elements,
    fetchCalls,
    enqueueFetch(handler) {
      fetchQueue.push(handler);
    },
    countFetches(fragment) {
      return fetchCalls.filter((item) => item.path.includes(fragment)).length;
    },
    lastFetch(fragment) {
      const matches = fetchCalls.filter((item) => item.path.includes(fragment));
      return matches.length ? matches[matches.length - 1] : null;
    },
    element(id) {
      return getElement(id);
    },
    async dispatch(id, type, event = {}) {
      await getElement(id).dispatch(type, event);
    },
  };
}

function responseJson(payload, { status = 200 } = {}) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ "Content-Type": "application/json" }),
    async text() {
      return JSON.stringify(payload);
    },
  };
}

function failureJson(message, { status = 400 } = {}) {
  return responseJson({
    status: "failed",
    diagnostics: {
      error: message,
      message,
    },
  }, { status });
}

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function makeFile(name, { size = 512, lastModified = 1, type = "image/png" } = {}) {
  return { name, size, lastModified, type };
}

function preparedLaunch(overrides = {}) {
  return {
    source_path: "C:/tmp/gmail.pdf",
    source_filename: "gmail.pdf",
    page_count: 5,
    start_page: 2,
    output_dir: "C:/tmp/gmail",
    target_lang: "AR",
    image_mode: "auto",
    ocr_mode: "auto",
    ocr_engine: "local_then_api",
    resume: false,
    keep_intermediates: true,
    auto_start: false,
    workflow_source: "gmail_intake",
    gmail_batch_context: {
      source: "gmail_intake",
      session_id: "gmail_batch_1",
      message_id: "msg-1",
      thread_id: "thr-1",
      attachment_id: "att-1",
      selected_attachment_filename: "gmail.pdf",
      selected_attachment_count: 1,
      selected_target_lang: "AR",
      selected_start_page: 2,
      gmail_batch_session_report_path: "C:/tmp/gmail_session.json",
    },
    ...overrides,
  };
}

function historyResponse() {
  return responseJson({
    status: "ok",
    normalized_payload: {
      history: [],
      active_jobs: [],
    },
  });
}

function captureUi(env, translationModule) {
  return {
    snapshot: translationModule.getTranslationUiSnapshot(),
    sourceCardTitle: env.element("translation-source-card-title").textContent,
    sourceCardCopy: env.element("translation-source-card-copy").textContent,
    sourceCardFilename: env.element("translation-source-filename").textContent,
    sourceCardPages: env.element("translation-source-pages").textContent,
    sourceCardTarget: env.element("translation-source-target").textContent,
    sourceCardDefaultTarget: env.element("translation-source-default-target").textContent,
    sourceCardStatus: env.element("translation-source-stage-status").textContent,
    sourceCardHint: env.element("translation-source-card-hint").textContent,
    actionHelper: env.element("translation-action-helper").textContent,
    runTask: env.element("translation-current-task").textContent,
    resultHtml: env.element("translation-result").innerHTML,
    jobDiagnostics: env.element("translation-job-diagnostics").textContent,
    jobDetailsOpen: env.element("translation-job-details").open,
    numericWarning: env.element("translation-numeric-warning").textContent,
    completionNumericWarning: env.element("translation-completion-numeric-warning").textContent,
    saveNumericWarning: env.element("translation-save-numeric-warning").textContent,
    gmailStepNumericWarning: env.element("translation-gmail-step-numeric-warning").textContent,
    browseDisabled: env.element("translation-source-browse").disabled,
    sourceInputValue: env.element("translation-source-file").value,
    sourceInputClickCount: env.element("translation-source-file").clickCount,
  };
}

async function setupScenario(name, url = "http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job") {
  const env = installEnvironment(url);
  const stateModule = await import(stateModuleUrl);
  stateModule.initializeRouteState({
    defaultRuntimeMode: "live",
    defaultWorkspaceId: "workspace-1",
    defaultUiVariant: "qt",
  });
  stateModule.appState.bootstrap = {
    normalized_payload: {
      settings_summary: {
        default_outdir: "C:/tmp/default-output",
        default_lang: "AR",
      },
      gmail: {},
      runtime: {},
    },
  };
  const translationModule = await import(`${translationModuleUrl}?case=${encodeURIComponent(name)}`);
  translationModule.initializeTranslationUi();
  return { env, stateModule, translationModule };
}

function parseJsonBody(call) {
  return call && typeof call.body === "string" ? JSON.parse(call.body) : null;
}

function beginSourceInputChange(env, file) {
  env.element("translation-source-file").files = [file];
  env.element("translation-source-file").value = file.name;
  return env.dispatch("translation-source-file", "change");
}

async function waitForAsyncWork() {
  await Promise.resolve();
  await Promise.resolve();
}

const results = {};

{
  const scenario = await setupScenario("idle");
  await scenario.env.dispatch("translation-source-card", "click", {
    target: scenario.env.element("translation-source-card"),
  });
  const clicksAfterCard = scenario.env.element("translation-source-file").clickCount;
  await scenario.env.dispatch("translation-source-card", "click", {
    target: scenario.env.element("translation-source-browse"),
  });
  await scenario.env.dispatch("translation-cancel", "click");
  results.idle = {
    ...captureUi(scenario.env, scenario.translationModule),
    clicksAfterCard,
    clickCountAfterInteractiveTarget: scenario.env.element("translation-source-file").clickCount,
    fetchCount: scenario.env.fetchCalls.length,
  };
}

{
  const scenario = await setupScenario("prepared");
  scenario.translationModule.applyTranslationLaunch(preparedLaunch());
  results.prepared = captureUi(scenario.env, scenario.translationModule);
}

{
  const scenario = await setupScenario("prepared-target-mismatch");
  scenario.translationModule.applyTranslationLaunch(preparedLaunch({
    target_lang: "EN",
    gmail_batch_context: {
      ...preparedLaunch().gmail_batch_context,
      selected_target_lang: "EN",
    },
  }));
  results.preparedTargetMismatch = captureUi(scenario.env, scenario.translationModule);
}

{
  const scenario = await setupScenario("prepared-failed-replacement");
  scenario.translationModule.applyTranslationLaunch(preparedLaunch());
  const replacement = makeFile("replacement.png", { lastModified: 11 });
  scenario.env.element("translation-source-file").files = [replacement];
  scenario.env.element("translation-source-file").value = replacement.name;
  scenario.env.enqueueFetch(() => failureJson("Replacement upload failed."));
  await scenario.env.dispatch("translation-source-file", "change");
  const afterFailureCapture = captureUi(scenario.env, scenario.translationModule);

  scenario.env.enqueueFetch((call) => responseJson({
    status: "ok",
    normalized_payload: {
      job: {
        job_id: "tx-prepared-start",
        job_kind: "translate",
        status: "queued",
        status_text: "Queued from prepared Gmail source",
        config: {
          source_path: "C:/tmp/gmail.pdf",
          target_lang: "AR",
          start_page: 2,
          gmail_batch_context: preparedLaunch().gmail_batch_context,
        },
        actions: {
          cancel: true,
        },
      },
    },
  }));
  scenario.env.enqueueFetch(() => historyResponse());
  await scenario.env.dispatch("translation-start", "click");

  results.preparedFailedReplacement = {
    afterFailure: afterFailureCapture,
    uploadCallCount: scenario.env.countFetches("/api/translation/upload-source"),
    translateCallCount: scenario.env.countFetches("/api/translation/jobs/translate"),
    translateBody: parseJsonBody(scenario.env.lastFetch("/api/translation/jobs/translate")),
  };
}

{
  const scenario = await setupScenario("no-prepared-failed-local");
  const localFile = makeFile("local-image.png", { lastModified: 21 });
  scenario.env.enqueueFetch(() => failureJson("Upload failed for local image."));
  await beginSourceInputChange(scenario.env, localFile);
  results.noPreparedFailedLocal = captureUi(scenario.env, scenario.translationModule);
}

{
  const scenario = await setupScenario("local-success");
  scenario.translationModule.applyTranslationLaunch(preparedLaunch());
  const localFile = makeFile("local-image.png", { lastModified: 31 });
  scenario.env.enqueueFetch(() => responseJson({
    status: "ok",
    normalized_payload: {
      source_path: "C:/uploads/local-image.png",
      source_filename: "local-image.png",
      source_type: "image",
      page_count: 1,
    },
  }));
  await beginSourceInputChange(scenario.env, localFile);
  const firstCapture = captureUi(scenario.env, scenario.translationModule);
  const uploadCallsAfterSuccess = scenario.env.countFetches("/api/translation/upload-source");

  await beginSourceInputChange(scenario.env, localFile);

  results.localSuccess = {
    afterSuccess: firstCapture,
    finalSnapshot: scenario.translationModule.getTranslationUiSnapshot(),
    uploadCallsAfterSuccess,
    uploadCallsAfterReuse: scenario.env.countFetches("/api/translation/upload-source"),
  };
}

{
  const scenario = await setupScenario("pending-replacement");
  scenario.translationModule.applyTranslationLaunch(preparedLaunch());
  const localFile = makeFile("replacement-pending.png", { lastModified: 41 });
  const pendingUpload = deferred();
  scenario.env.enqueueFetch(() => pendingUpload.promise);
  const changePromise = beginSourceInputChange(scenario.env, localFile);
  await waitForAsyncWork();
  const duringCapture = captureUi(scenario.env, scenario.translationModule);
  const clickCountBeforeBlockedActions = scenario.env.element("translation-source-file").clickCount;
  const uploadCallsBeforeBlockedDrop = scenario.env.countFetches("/api/translation/upload-source");
  await scenario.env.dispatch("translation-source-card", "click", {
    target: scenario.env.element("translation-source-card"),
  });
  await scenario.env.dispatch("translation-source-browse", "click");
  await scenario.env.dispatch("translation-source-card", "drop", {
    dataTransfer: {
      files: [makeFile("blocked-during-pending.png", { lastModified: 42 })],
    },
  });
  pendingUpload.resolve(responseJson({
    status: "ok",
    normalized_payload: {
      source_path: "C:/uploads/replacement-pending.png",
      source_filename: "replacement-pending.png",
      source_type: "image",
      page_count: 1,
    },
  }));
  await changePromise;
  results.pendingReplacement = {
    during: duringCapture,
    blockedWhilePending: {
      clickCountBefore: clickCountBeforeBlockedActions,
      clickCountAfter: scenario.env.element("translation-source-file").clickCount,
      uploadCallsBeforeDrop: uploadCallsBeforeBlockedDrop,
      uploadCallsAfterDrop: scenario.env.countFetches("/api/translation/upload-source"),
    },
    after: captureUi(scenario.env, scenario.translationModule),
  };
}

{
  const scenario = await setupScenario("race-older-success-after-newer-success");
  const firstFile = makeFile("older-success.png", { lastModified: 51 });
  const secondFile = makeFile("newer-success.png", { lastModified: 52 });
  const firstUpload = deferred();
  const secondUpload = deferred();
  scenario.env.enqueueFetch(() => firstUpload.promise);
  const firstChange = beginSourceInputChange(scenario.env, firstFile);
  await waitForAsyncWork();
  scenario.env.enqueueFetch(() => secondUpload.promise);
  const secondChange = beginSourceInputChange(scenario.env, secondFile);
  await waitForAsyncWork();
  secondUpload.resolve(responseJson({
    status: "ok",
    normalized_payload: {
      source_path: "C:/uploads/newer-success.png",
      source_filename: "newer-success.png",
      source_type: "image",
      page_count: 1,
    },
  }));
  await secondChange;
  const afterNewer = captureUi(scenario.env, scenario.translationModule);
  firstUpload.resolve(responseJson({
    status: "ok",
    normalized_payload: {
      source_path: "C:/uploads/older-success.png",
      source_filename: "older-success.png",
      source_type: "image",
      page_count: 1,
    },
  }));
  await firstChange;
  results.raceOlderSuccessAfterNewerSuccess = {
    afterNewer,
    afterOlder: captureUi(scenario.env, scenario.translationModule),
    uploadCallCount: scenario.env.countFetches("/api/translation/upload-source"),
  };
}

{
  const scenario = await setupScenario("race-older-failure-after-newer-success");
  const firstFile = makeFile("older-failure.png", { lastModified: 61 });
  const secondFile = makeFile("newer-success-after-failure.png", { lastModified: 62 });
  const firstUpload = deferred();
  const secondUpload = deferred();
  scenario.env.enqueueFetch(() => firstUpload.promise);
  const firstChange = beginSourceInputChange(scenario.env, firstFile);
  await waitForAsyncWork();
  scenario.env.enqueueFetch(() => secondUpload.promise);
  const secondChange = beginSourceInputChange(scenario.env, secondFile);
  await waitForAsyncWork();
  secondUpload.resolve(responseJson({
    status: "ok",
    normalized_payload: {
      source_path: "C:/uploads/newer-success-after-failure.png",
      source_filename: "newer-success-after-failure.png",
      source_type: "image",
      page_count: 1,
    },
  }));
  await secondChange;
  const afterNewer = captureUi(scenario.env, scenario.translationModule);
  firstUpload.resolve(failureJson("Older upload failed after a newer success."));
  await firstChange;
  results.raceOlderFailureAfterNewerSuccess = {
    afterNewer,
    afterOlder: captureUi(scenario.env, scenario.translationModule),
    uploadCallCount: scenario.env.countFetches("/api/translation/upload-source"),
  };
}

{
  const scenario = await setupScenario("race-older-success-while-newer-pending");
  const firstFile = makeFile("older-pending.png", { lastModified: 71 });
  const secondFile = makeFile("newer-pending.png", { lastModified: 72 });
  const firstUpload = deferred();
  const secondUpload = deferred();
  scenario.env.enqueueFetch(() => firstUpload.promise);
  const firstChange = beginSourceInputChange(scenario.env, firstFile);
  await waitForAsyncWork();
  scenario.env.enqueueFetch(() => secondUpload.promise);
  const secondChange = beginSourceInputChange(scenario.env, secondFile);
  await waitForAsyncWork();
  firstUpload.resolve(responseJson({
    status: "ok",
    normalized_payload: {
      source_path: "C:/uploads/older-pending.png",
      source_filename: "older-pending.png",
      source_type: "image",
      page_count: 1,
    },
  }));
  await firstChange;
  const whileNewerPending = captureUi(scenario.env, scenario.translationModule);
  secondUpload.resolve(responseJson({
    status: "ok",
    normalized_payload: {
      source_path: "C:/uploads/newer-pending.png",
      source_filename: "newer-pending.png",
      source_type: "image",
      page_count: 1,
    },
  }));
  await secondChange;
  results.raceOlderSuccessWhileNewerPending = {
    whileNewerPending,
    afterNewer: captureUi(scenario.env, scenario.translationModule),
    uploadCallCount: scenario.env.countFetches("/api/translation/upload-source"),
  };
}

{
  const scenario = await setupScenario("prepared-stale-failure-ignored");
  scenario.translationModule.applyTranslationLaunch(preparedLaunch());
  const firstFile = makeFile("gmail-replacement-older.png", { lastModified: 81 });
  const secondFile = makeFile("gmail-replacement-newer.png", { lastModified: 82 });
  const firstUpload = deferred();
  const secondUpload = deferred();
  scenario.env.enqueueFetch(() => firstUpload.promise);
  const firstChange = beginSourceInputChange(scenario.env, firstFile);
  await waitForAsyncWork();
  scenario.env.enqueueFetch(() => secondUpload.promise);
  const secondChange = beginSourceInputChange(scenario.env, secondFile);
  await waitForAsyncWork();
  firstUpload.resolve(failureJson("Older Gmail replacement failed."));
  await firstChange;
  const whileNewerPending = captureUi(scenario.env, scenario.translationModule);
  secondUpload.resolve(responseJson({
    status: "ok",
    normalized_payload: {
      source_path: "C:/uploads/gmail-replacement-newer.png",
      source_filename: "gmail-replacement-newer.png",
      source_type: "image",
      page_count: 1,
    },
  }));
  await secondChange;
  results.preparedStaleFailureIgnored = {
    whileNewerPending,
    afterNewer: captureUi(scenario.env, scenario.translationModule),
    uploadCallCount: scenario.env.countFetches("/api/translation/upload-source"),
  };
}

{
  const scenario = await setupScenario("loaded-job-different-source");
  scenario.translationModule.applyTranslationLaunch(preparedLaunch({
    source_path: "C:/tmp/original-gmail.pdf",
    source_filename: "original-gmail.pdf",
  }));
  scenario.translationModule.renderTranslationJob({
    job_id: "tx-loaded-42",
    job_kind: "translate",
    status: "failed",
    status_text: "Loaded failed translation job",
    config: {
      source_path: "C:/jobs/loaded-source.pdf",
      target_lang: "FR",
      start_page: 1,
      gmail_batch_context: {
        source: "gmail_intake",
        session_id: "gmail_batch_loaded",
        message_id: "msg-loaded",
        thread_id: "thr-loaded",
        attachment_id: "att-loaded",
        selected_attachment_filename: "loaded-source.pdf",
        selected_attachment_count: 1,
        selected_target_lang: "FR",
        selected_start_page: 1,
        gmail_batch_session_report_path: "C:/tmp/loaded_session.json",
      },
    },
    progress: {
      selected_total: 7,
    },
    actions: {
      resume: true,
      rebuild: true,
    },
  });
  results.loadedJobDifferentSource = captureUi(scenario.env, scenario.translationModule);
}

{
  const scenario = await setupScenario("run-status");
  results.runStatusView = scenario.translationModule.deriveTranslationRunStatusView({
    job_id: "tx-running-1",
    job_kind: "translate",
    status: "running",
    status_text: "Page translation in progress",
    progress: {
      selected_index: 2,
      selected_total: 5,
      real_page: 4,
      retry_used: true,
      image_used: true,
      status_text: "Translating page 4",
    },
    result: {
      review_queue_count: 1,
    },
    logs: [
      "page=4 image_used=True retry_used=True status=finished",
      "Page 5 failed",
    ],
  });
}

{
  const scenario = await setupScenario("raw-status-and-numeric-warning");
  const rawStatus = '{"job_id":"tx-num","progress":{"phase":"completed"}}';
  scenario.translationModule.renderTranslationJob({
    job_id: "tx-num",
    job_kind: "translate",
    status: "completed",
    status_text: rawStatus,
    config: {
      source_path: "C:/tmp/gmail.pdf",
      source_filename: "gmail.pdf",
      target_lang: "EN",
      start_page: 2,
      gmail_batch_context: {
        ...preparedLaunch().gmail_batch_context,
        selected_target_lang: "EN",
      },
    },
    result: {
      completed_pages: 9,
      save_seed: {
        case_number: "CASE-NUM",
        target_lang: "EN",
      },
      translation_diagnostics: {
        validation_pages: [
          {
            page: 3,
            numeric_mismatches_count: 1,
            numeric_missing_sample: ["10.15"],
          },
          {
            page_number: 7,
            numeric_mismatches_count: 3,
            numeric_missing_sample: ["495,00", "5,50", "5,50"],
          },
        ],
      },
    },
  });
  results.rawStatusNumericWarning = captureUi(scenario.env, scenario.translationModule);
  results.numericWarningFromPreview = scenario.translationModule.deriveNumericMismatchWarning(null, {
    preview: [
      "## Numeric Mismatch Samples",
      "- Page 3: missing ['10.15']",
      "- Page 7: missing ['495,00', '5,50', '5,50']",
    ].join("\n"),
  });
}

{
  const scenario = await setupScenario("normal-running-diagnostics-collapsed");
  scenario.translationModule.renderTranslationJob({
    job_id: "tx-running-diagnostics",
    job_kind: "translate",
    status: "running",
    status_text: '{"job_id":"tx-running-diagnostics","phase":"page"}',
    config: {
      source_path: "C:/tmp/gmail.pdf",
      source_filename: "gmail.pdf",
      target_lang: "EN",
      start_page: 2,
    },
    progress: {
      selected_index: 2,
      selected_total: 8,
    },
    result: {
      completed_pages: 2,
    },
  });
  results.normalRunningDiagnostics = captureUi(scenario.env, scenario.translationModule);
}

{
  const scenario = await setupScenario("failed-diagnostics-open");
  scenario.translationModule.renderTranslationJob({
    job_id: "tx-failed-diagnostics",
    job_kind: "translate",
    status: "failed",
    status_text: "Translation failed on page 4.",
    config: {
      source_path: "C:/tmp/gmail.pdf",
      source_filename: "gmail.pdf",
      target_lang: "EN",
      start_page: 2,
    },
    result: {
      error: "Page translation failed.",
    },
  });
  results.failedDiagnostics = captureUi(scenario.env, scenario.translationModule);
}

{
  const scenario = await setupScenario("completion-presentation");
  results.completionPresentation = {
    idle: scenario.translationModule.deriveTranslationCompletionPresentation(),
    analyzeCompleted: scenario.translationModule.deriveTranslationCompletionPresentation({
      job: {
        job_id: "analyze-1",
        job_kind: "analyze",
        status: "completed",
        result: {
          analysis: {
            selected_pages_count: 4,
            pages_would_attach_images: 2,
          },
        },
      },
    }),
    translationCompleted: scenario.translationModule.deriveTranslationCompletionPresentation({
      job: {
        job_id: "translate-1",
        job_kind: "translate",
        status: "completed",
      },
      saveSeed: {
        case_number: "CASE-42",
        case_entity: "Tribunal",
        case_city: "Lisbon",
        translation_date: "2026-04-21",
        target_lang: "FR",
        output_docx: "C:/tmp/translated.docx",
      },
    }),
    loadedRow: scenario.translationModule.deriveTranslationCompletionPresentation({
      currentRowId: 17,
      saveSeed: {
        case_number: "CASE-17",
        case_entity: "Court",
        case_city: "Porto",
        translation_date: "2026-04-20",
      },
    }),
    arabicRequired: scenario.translationModule.deriveTranslationCompletionPresentation({
      job: {
        job_id: "translate-ar",
        job_kind: "translate",
        status: "completed",
      },
      saveSeed: {
        case_number: "CASE-AR",
        target_lang: "AR",
        output_docx: "C:/tmp/arabic.docx",
      },
      arabicReview: {
        required: true,
        resolved: false,
        status: "waiting_for_save",
        message: "Review the Arabic document in Word before you save the case record.",
        docx_path: "C:/tmp/arabic.docx",
      },
    }),
    arabicResolved: scenario.translationModule.deriveTranslationCompletionPresentation({
      job: {
        job_id: "translate-ar-done",
        job_kind: "translate",
        status: "completed",
      },
      saveSeed: {
        case_number: "CASE-AR-DONE",
        target_lang: "AR",
        output_docx: "C:/tmp/arabic-done.docx",
      },
      arabicReview: {
        required: true,
        resolved: true,
        status: "resolved",
        message: "Arabic review complete.",
        docx_path: "C:/tmp/arabic-done.docx",
      },
    }),
    gmailAttachmentReady: scenario.translationModule.deriveTranslationCompletionPresentation({
      arabicReview: {
        required: false,
        resolved: true,
      },
      gmailBatchContext: preparedLaunch().gmail_batch_context,
      gmailCurrentStep: {
        visible: true,
        filename: "gmail.pdf",
        batchLabel: "1/2",
        hasMoreItems: true,
      },
    }),
    gmailFinalizationReady: scenario.translationModule.deriveTranslationCompletionPresentation({
      gmailBatchContext: preparedLaunch().gmail_batch_context,
      gmailFinalizeReady: true,
    }),
  };
}

{
  const scenario = await setupScenario("recent-work-presentation", "http://127.0.0.1:8877/?mode=live&workspace=workspace-1#recent-jobs");
  results.recentWorkPresentation = {
    empty: scenario.translationModule.deriveRecentWorkPresentation(),
    loaded: scenario.translationModule.deriveRecentWorkPresentation({
      recentItemCount: 3,
      recordAvailable: false,
      jobType: "Interpretation",
    }),
    translationHistory: scenario.translationModule.deriveRecentWorkPresentation({
      jobType: "Translation",
    }),
    translationRun: scenario.translationModule.deriveRecentWorkPresentation({
      translationRunCount: 2,
      job: {
        job_id: "tx-run-7",
        job_kind: "translate",
        status: "running",
        config: {
          source_path: "C:/workspace/cases/notice.pdf",
          target_lang: "FR",
        },
      },
    }),
  };
}

{
  const dashboardModule = await import(dashboardModuleUrl);
  results.dashboardPresentation = {
    zero: dashboardModule.deriveDashboardPresentation({
      normalized_payload: {
        recent_job_counts: {
          total: 0,
          translation: 0,
          interpretation: 0,
        },
        runtime: {
          live_data: false,
        },
        parity_audit: {
          summary: "The browser app is ready for the daily workflows: translation, interpretation requests, Gmail attachments, and saved work.",
          ready_count: 5,
          total_count: 7,
          promotion_recommendation: {
            status: "not_ready_yet",
          },
        },
      },
      capability_flags: {
        gmail_bridge: {
          status: "warn",
        },
        word_pdf_export: {
          finalization_ready: false,
          preflight: {
            ok: false,
          },
          export_canary: {
            ok: false,
          },
        },
        translation: {
          credentials_configured: false,
        },
        ocr: {
          api_configured: false,
          local_available: false,
        },
      },
    }),
    nonzero: dashboardModule.deriveDashboardPresentation({
      normalized_payload: {
        recent_job_counts: {
          total: 5,
          translation: 3,
          interpretation: 2,
        },
        runtime: {
          live_data: true,
        },
        parity_audit: {
          summary: "The browser app is ready for the daily workflows: translation, interpretation requests, Gmail attachments, and saved work.",
          ready_count: 7,
          total_count: 7,
          promotion_recommendation: {
            status: "ready_for_daily_use",
          },
        },
      },
      capability_flags: {
        gmail_bridge: {
          status: "ok",
        },
        word_pdf_export: {
          finalization_ready: true,
        },
        translation: {
          credentials_configured: true,
        },
        ocr: {
          api_configured: true,
          local_available: false,
        },
      },
    }),
    summaryOnly: {
      zero: dashboardModule.formatDashboardSavedWorkSummary({
        total: 0,
        translation: 0,
        interpretation: 0,
      }),
      nonzero: dashboardModule.formatDashboardSavedWorkSummary({
        total: 4,
        translation: 3,
        interpretation: 1,
      }),
    },
  };
}

console.log(JSON.stringify(results));
"""
    return run_browser_esm_json_probe(
        script,
        {
            "__STATE_MODULE_URL__": "state.js",
            "__TRANSLATION_MODULE_URL__": "translation.js",
            "__DASHBOARD_MODULE_URL__": "dashboard_presentation.js",
        },
        timeout_seconds=30,
    )


@functools.lru_cache(maxsize=1)
def _probe_results() -> dict[str, object]:
    return _run_translation_browser_state_probe()


def test_translation_browser_idle_and_prepared_action_states() -> None:
    results = _probe_results()

    idle = results["idle"]
    assert idle["snapshot"]["sourceState"] == "empty"
    assert idle["snapshot"]["sourceReady"] is False
    assert idle["snapshot"]["translationStartDisabled"] is True
    assert idle["snapshot"]["translationAnalyzeDisabled"] is True
    assert idle["snapshot"]["translationCancelDisabled"] is True
    assert idle["snapshot"]["translationResumeDisabled"] is True
    assert idle["snapshot"]["translationRebuildDisabled"] is True
    assert idle["actionHelper"] == "Choose a PDF or image to enable Start Translate."
    assert idle["runTask"] == "Choose a source file to begin."
    assert idle["clicksAfterCard"] == 1
    assert idle["clickCountAfterInteractiveTarget"] == 1
    assert idle["fetchCount"] == 0

    prepared = results["prepared"]
    assert prepared["snapshot"]["sourceState"] == "prepared-ready"
    assert prepared["snapshot"]["sourceReady"] is True
    assert prepared["snapshot"]["translationStartDisabled"] is False
    assert prepared["snapshot"]["translationAnalyzeDisabled"] is False
    assert prepared["snapshot"]["translationCancelDisabled"] is True
    assert prepared["snapshot"]["translationResumeDisabled"] is True
    assert prepared["snapshot"]["translationRebuildDisabled"] is True
    assert prepared["sourceCardTitle"] == "Gmail attachment is prepared"
    assert "Review settings, then start translation" in prepared["sourceCardCopy"]
    assert prepared["sourceCardFilename"] == "gmail.pdf"
    assert prepared["sourceCardTarget"] == "Current Gmail job target: AR"
    assert "No file chosen" not in prepared["sourceCardCopy"]
    assert prepared["sourceCardStatus"] == "Ready from Gmail."
    assert prepared["actionHelper"] == "Gmail attachment is prepared. Review settings, then start translation."

    prepared_mismatch = results["preparedTargetMismatch"]
    assert prepared_mismatch["sourceCardTarget"] == "Current Gmail job target: EN"
    assert prepared_mismatch["sourceCardDefaultTarget"] == "Default target for new jobs: AR"


def test_translation_browser_failed_local_replacement_restores_prepared_gmail_source() -> None:
    results = _probe_results()

    failed = results["preparedFailedReplacement"]
    snapshot = failed["afterFailure"]["snapshot"]
    assert snapshot["sourceState"] == "prepared-ready"
    assert snapshot["sourceReady"] is True
    assert snapshot["preparedLaunchSourcePath"] == "C:/tmp/gmail.pdf"
    assert snapshot["currentGmailBatchContext"]["attachment_id"] == "att-1"
    assert failed["afterFailure"]["sourceCardFilename"] == "gmail.pdf"
    assert failed["afterFailure"]["sourceCardStatus"] == "Ready from Gmail."
    assert failed["afterFailure"]["sourceInputValue"] == ""
    assert snapshot["manualSourceFileName"] == ""
    assert snapshot["translationStartDisabled"] is False
    assert snapshot["translationAnalyzeDisabled"] is False
    assert failed["uploadCallCount"] == 1
    assert failed["translateCallCount"] == 1
    assert failed["translateBody"]["form_values"]["source_path"] == "C:/tmp/gmail.pdf"
    assert failed["translateBody"]["form_values"]["gmail_batch_context"]["attachment_id"] == "att-1"


def test_translation_browser_local_staging_failure_success_and_pending_states() -> None:
    results = _probe_results()

    no_prepared = results["noPreparedFailedLocal"]
    assert no_prepared["snapshot"]["sourceState"] == "manual-error"
    assert no_prepared["snapshot"]["sourceReady"] is False
    assert no_prepared["snapshot"]["sourcePathValue"] == ""
    assert no_prepared["snapshot"]["translationStartDisabled"] is True
    assert no_prepared["snapshot"]["translationAnalyzeDisabled"] is True
    assert no_prepared["sourceCardStatus"] == "Upload failed for local image."
    assert no_prepared["actionHelper"] == "Upload failed for local image."

    pending = results["pendingReplacement"]
    assert pending["during"]["snapshot"]["sourceState"] == "manual-uploading"
    assert pending["during"]["snapshot"]["sourceReady"] is False
    assert pending["during"]["snapshot"]["sourceUploadPending"] is True
    assert pending["during"]["snapshot"]["sourceUploadReplacingPrepared"] is True
    assert pending["during"]["snapshot"]["translationStartDisabled"] is True
    assert pending["during"]["snapshot"]["translationAnalyzeDisabled"] is True
    assert pending["during"]["actionHelper"] == "Checking the replacement document..."
    assert pending["during"]["runTask"] == "Checking the replacement document..."
    assert pending["during"]["browseDisabled"] is True
    assert pending["blockedWhilePending"]["clickCountBefore"] == pending["blockedWhilePending"]["clickCountAfter"]
    assert pending["blockedWhilePending"]["uploadCallsBeforeDrop"] == pending["blockedWhilePending"]["uploadCallsAfterDrop"]
    assert pending["after"]["snapshot"]["sourceState"] == "manual-ready"
    assert pending["after"]["snapshot"]["sourceReady"] is True

    success = results["localSuccess"]
    success_snapshot = success["afterSuccess"]["snapshot"]
    assert success_snapshot["sourceState"] == "manual-ready"
    assert success_snapshot["sourceReady"] is True
    assert success_snapshot["hasPreparedLaunch"] is False
    assert success_snapshot["currentGmailBatchContext"] is None
    assert success_snapshot["sourcePathValue"] == "C:/uploads/local-image.png"
    assert success_snapshot["translationStartDisabled"] is False
    assert success_snapshot["translationAnalyzeDisabled"] is False
    assert success["afterSuccess"]["sourceCardFilename"] == "local-image.png"
    assert str(success["afterSuccess"]["sourceCardPages"]) == "1"
    assert success["uploadCallsAfterSuccess"] == 1
    assert success["uploadCallsAfterReuse"] == 1


def test_translation_browser_stale_upload_results_are_ignored() -> None:
    results = _probe_results()

    older_success = results["raceOlderSuccessAfterNewerSuccess"]
    assert older_success["uploadCallCount"] == 2
    assert older_success["afterNewer"]["snapshot"]["sourceState"] == "manual-ready"
    assert older_success["afterNewer"]["snapshot"]["sourcePathValue"] == "C:/uploads/newer-success.png"
    assert older_success["afterOlder"]["snapshot"]["sourceState"] == "manual-ready"
    assert older_success["afterOlder"]["snapshot"]["sourcePathValue"] == "C:/uploads/newer-success.png"
    assert older_success["afterOlder"]["sourceCardFilename"] == "newer-success.png"
    assert older_success["afterOlder"]["sourceCardStatus"] == "Uploaded and ready."

    older_failure = results["raceOlderFailureAfterNewerSuccess"]
    assert older_failure["uploadCallCount"] == 2
    assert older_failure["afterNewer"]["snapshot"]["sourceState"] == "manual-ready"
    assert older_failure["afterOlder"]["snapshot"]["sourceState"] == "manual-ready"
    assert older_failure["afterOlder"]["snapshot"]["sourcePathValue"] == "C:/uploads/newer-success-after-failure.png"
    assert older_failure["afterOlder"]["sourceCardFilename"] == "newer-success-after-failure.png"
    assert older_failure["afterOlder"]["actionHelper"] == "The document is ready. Confirm the language and output folder, then start translation."

    older_pending = results["raceOlderSuccessWhileNewerPending"]
    assert older_pending["uploadCallCount"] == 2
    assert older_pending["whileNewerPending"]["snapshot"]["sourceState"] == "manual-uploading"
    assert older_pending["whileNewerPending"]["snapshot"]["sourceReady"] is False
    assert older_pending["whileNewerPending"]["snapshot"]["sourcePathValue"] == ""
    assert older_pending["whileNewerPending"]["sourceCardFilename"] == "newer-pending.png"
    assert older_pending["whileNewerPending"]["actionHelper"] == "Checking the document before translation starts..."
    assert older_pending["afterNewer"]["snapshot"]["sourceState"] == "manual-ready"
    assert older_pending["afterNewer"]["snapshot"]["sourcePathValue"] == "C:/uploads/newer-pending.png"

    prepared_stale = results["preparedStaleFailureIgnored"]
    assert prepared_stale["uploadCallCount"] == 2
    assert prepared_stale["whileNewerPending"]["snapshot"]["sourceState"] == "manual-uploading"
    assert prepared_stale["whileNewerPending"]["snapshot"]["sourceUploadReplacingPrepared"] is True
    assert prepared_stale["whileNewerPending"]["snapshot"]["sourceReady"] is False
    assert prepared_stale["whileNewerPending"]["snapshot"]["hasPreparedLaunch"] is True
    assert prepared_stale["whileNewerPending"]["sourceCardFilename"] == "gmail-replacement-newer.png"
    assert prepared_stale["whileNewerPending"]["sourceCardStatus"] == "Checking the replacement document..."
    assert prepared_stale["afterNewer"]["snapshot"]["sourceState"] == "manual-ready"
    assert prepared_stale["afterNewer"]["snapshot"]["hasPreparedLaunch"] is False
    assert prepared_stale["afterNewer"]["snapshot"]["currentGmailBatchContext"] is None
    assert prepared_stale["afterNewer"]["snapshot"]["sourcePathValue"] == "C:/uploads/gmail-replacement-newer.png"


def test_translation_browser_loaded_job_source_replaces_stale_summary_and_run_status_view() -> None:
    results = _probe_results()

    loaded = results["loadedJobDifferentSource"]
    assert loaded["snapshot"]["sourcePathValue"] == "C:/jobs/loaded-source.pdf"
    assert loaded["snapshot"]["sourceCardFilename"] == "loaded-source.pdf"
    assert loaded["snapshot"]["currentGmailBatchContext"]["attachment_id"] == "att-loaded"
    assert loaded["sourceCardTitle"] == "Gmail attachment is prepared"
    assert loaded["sourceCardFilename"] == "loaded-source.pdf"
    assert loaded["sourceCardStatus"] == "Ready from Gmail."

    run_status = results["runStatusView"]
    assert run_status["percentValue"] == 40
    assert run_status["percentText"] == "40%"
    assert run_status["chipText"] == "Running"
    assert run_status["chipTone"] == "info"
    assert run_status["currentTask"] == "Translating page 4"
    assert run_status["pagesText"] == "2 / 5"
    assert run_status["currentPageText"] == "Page 4"
    assert "Image on page 4" in run_status["imageRetryText"]
    assert "Retry on page 4" in run_status["imageRetryText"]
    assert "Flagged 1" in run_status["alertsText"]
    assert "Errors 1" in run_status["alertsText"]

    raw_warning = results["rawStatusNumericWarning"]
    assert raw_warning["runTask"] == "Completed pages: 9. Latest technical state is available in details."
    assert '{"job_id"' not in raw_warning["runTask"]
    assert "Translation complete." in raw_warning["resultHtml"]
    assert '{"job_id"' not in raw_warning["resultHtml"]
    assert '"status_text"' in raw_warning["jobDiagnostics"]
    assert '\\"job_id\\"' in raw_warning["jobDiagnostics"]
    assert "Review recommended: some numbers from the source may not appear exactly in the translation." in raw_warning["numericWarning"]
    assert "Page 3: 10.15" in raw_warning["numericWarning"]
    assert "Page 7: 495,00; 5,50" in raw_warning["numericWarning"]
    assert raw_warning["numericWarning"] == raw_warning["completionNumericWarning"]
    assert raw_warning["numericWarning"] == raw_warning["saveNumericWarning"]
    assert raw_warning["numericWarning"] == raw_warning["gmailStepNumericWarning"]

    preview_warning = results["numericWarningFromPreview"]
    assert preview_warning["visible"] is True
    assert "Page 3: 10.15" in preview_warning["lines"]
    assert "Page 7: 495,00; 5,50; 5,50" in preview_warning["lines"]
    assert "Page 7: 495; 00; 5; 50" not in preview_warning["lines"]

    running_diagnostics = results["normalRunningDiagnostics"]
    assert running_diagnostics["jobDetailsOpen"] is False
    assert '"status_text"' in running_diagnostics["jobDiagnostics"]
    assert '\\"job_id\\"' in running_diagnostics["jobDiagnostics"]
    assert running_diagnostics["runTask"] == "Translating... Completed pages: 2. Latest technical state is available in details."

    failed_diagnostics = results["failedDiagnostics"]
    assert failed_diagnostics["jobDetailsOpen"] is True
    assert "Page translation failed." in failed_diagnostics["jobDiagnostics"]


def test_translation_completion_presentation_helper_uses_beginner_finish_copy() -> None:
    presentation = _probe_results()["completionPresentation"]

    idle = presentation["idle"]
    assert idle["available"] is False
    assert idle["drawerStatus"] == "When a translation finishes, you can review the result, download files, and save the case record here."
    assert idle["saveTitle"] == "Save Case Record"

    analyze = presentation["analyzeCompleted"]
    assert analyze["completionButtonLabel"] == "Review analysis"
    assert analyze["drawerStatus"] == "Analysis complete. Review the report, then start a full translation when you are ready."
    assert analyze["resultTitle"] == "Analysis complete."
    assert analyze["resultChipLabel"] == "Report ready"

    translation = presentation["translationCompleted"]
    assert translation["available"] is True
    assert translation["drawerStatus"] == "Translation complete. Review the translated document, then save the case record if everything looks right."
    assert translation["resultTitle"] == "Translation complete."
    assert translation["saveButtonLabel"] == "Save case record"
    assert translation["resultDetailLines"][0] == "CASE-42"

    loaded_row = presentation["loadedRow"]
    assert loaded_row["completionButtonLabel"] == "Open saved case record"
    assert loaded_row["drawerStatus"] == "Saved case record loaded. Review the fields below and save any edits."
    assert loaded_row["resultTitle"] == "Saved case record loaded."

    arabic_required = presentation["arabicRequired"]
    assert arabic_required["drawerStatus"] == "Review the Arabic document in Word before you save the case record."
    assert arabic_required["arabicReview"]["title"] == "Review Arabic document in Word"
    assert arabic_required["arabicReview"]["docxLabel"] == "Translated DOCX"
    assert arabic_required["arabicReview"]["continueNowLabel"] == "I saved the Word file"

    arabic_resolved = presentation["arabicResolved"]
    assert arabic_resolved["saveStatus"] == "Arabic document review is complete. Save the case record when you are ready."
    assert arabic_resolved["arabicReview"]["chipLabel"] == "Done"

    gmail_attachment = presentation["gmailAttachmentReady"]
    assert gmail_attachment["gmailCurrentAttachment"]["title"] == "This Gmail attachment is ready to save."
    assert gmail_attachment["gmailCurrentAttachment"]["copy"] == "Save this translated attachment, then continue with the next Gmail step."
    assert gmail_attachment["gmailCurrentAttachment"]["buttonLabel"] == "Save this Gmail attachment"

    gmail_finalization = presentation["gmailFinalizationReady"]
    assert gmail_finalization["gmailFinalization"]["title"] == "Create Gmail Reply"
    assert gmail_finalization["gmailFinalization"]["status"] == "Every selected Gmail attachment is saved. You can create the Gmail reply when you are ready."
    assert gmail_finalization["gmailFinalization"]["buttonLabel"] == "Create Gmail reply"


def test_recent_work_presentation_helper_uses_beginner_saved_work_copy() -> None:
    presentation = _probe_results()["recentWorkPresentation"]

    empty = presentation["empty"]
    assert empty["recentWorkEmpty"] == "No saved work yet. Completed translations and interpretation requests will appear here."
    assert empty["recentCasesEmpty"] == "No saved cases yet."
    assert empty["translationHistoryEmpty"] == "No saved translation cases yet."
    assert empty["translationRunsEmpty"] == "No translation runs have started yet."
    assert empty["recentOpenLabel"] == "Open"
    assert empty["recentDeleteLabel"] == "Delete record"

    loaded = presentation["loaded"]
    assert loaded["typeLabel"] == "Interpretation"
    assert loaded["recentWorkCount"] == "3 recent item(s) ready."
    assert loaded["recentOpenLabel"] == "Open unavailable"
    assert loaded["deleteConfirmMessage"] == "Delete this saved interpretation record? This cannot be undone."

    translation_history = presentation["translationHistory"]
    assert translation_history["translationHistoryOpenLabel"] == "Open"
    assert translation_history["translationHistoryDeleteLabel"] == "Delete record"
    assert translation_history["deleteConfirmMessage"] == "Delete this saved translation record? This cannot be undone."
    assert translation_history["refreshStatus"] == "Saved work refreshed."
    assert translation_history["loadedSavedCaseStatus"] == "Saved case record loaded. Review the details below."

    translation_run = presentation["translationRun"]
    assert translation_run["translationRunsCount"] == "2 translation run(s) ready."
    assert translation_run["translationRunTitle"] == "notice.pdf"
    assert translation_run["translationRunOpenLabel"] == "Open run"
    assert translation_run["translationRunResumeLabel"] == "Resume"
    assert translation_run["translationRunRebuildLabel"] == "Rebuild DOCX"
    assert translation_run["translationRunSubtitle"] == "Translation | Target FR | Running"

    helper_text = " ".join(
        str(value)
        for group in presentation.values()
        for value in group.values()
    )
    assert "job-log rows" not in helper_text
    assert "browser translation jobs" not in helper_text
    assert "row #" not in helper_text


def test_dashboard_presentation_helper_uses_beginner_overview_copy() -> None:
    presentation = _probe_results()["dashboardPresentation"]

    zero = presentation["zero"]
    assert zero["savedWorkSummary"] == "No saved work yet. Completed translations and interpretation requests will appear here."
    assert zero["statusSummary"] == "Some tools may need attention before every workflow is ready."
    assert zero["parityStatus"] == (
        "The browser app is ready for the daily workflows: translation, interpretation requests, Gmail attachments, and saved work."
    )
    assert zero["readyCountLine"] == "5/7 overview area(s) are ready."
    assert zero["resultNextTitle"] == "Try next"
    assert zero["resultLimitsTitle"] == "Keep in mind"
    assert zero["resultChipLabel"] == "Not Ready Yet"
    assert [card["title"] for card in zero["statusCards"]] == [
        "App data",
        "Saved work",
        "Gmail tools",
        "Word/PDF tools",
        "Translation provider",
    ]
    assert zero["statusCards"][2]["text"] == "Optional setup for live Gmail intake."
    assert zero["statusCards"][2]["label"] == "Setup needed"

    nonzero = presentation["nonzero"]
    assert nonzero["savedWorkSummary"] == "5 saved item(s) available. 3 translation case(s) and 2 interpretation request(s) are ready to reopen."
    assert nonzero["statusSummary"] == "App status looks ready for normal work."
    assert nonzero["readyCountLine"] == "7/7 overview area(s) are ready."
    assert nonzero["resultChipLabel"] == "Ready"
    assert nonzero["statusCards"][2]["text"] == "Live Gmail attachments are ready when you need them."

    summary_only = presentation["summaryOnly"]
    assert summary_only["zero"] == "No saved work yet. Completed translations and interpretation requests will appear here."
    assert summary_only["nonzero"] == "4 saved item(s) available. 3 translation case(s) and 1 interpretation request(s) are ready to reopen."

    helper_text = " ".join(
        str(value)
        for group in presentation.values()
        for value in (group.values() if isinstance(group, dict) else [group])
    )
    assert "job-log rows" not in helper_text
    assert "Gmail bridge" not in helper_text
    assert "workspace" not in helper_text
    assert "artifacts" not in helper_text
    assert "Save to Job Log" not in helper_text
