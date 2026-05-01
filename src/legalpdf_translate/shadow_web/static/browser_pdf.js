import { fetchJson } from "./api.js";

const DEFAULT_BUNDLE_SCALE = 2.0;
const MIN_PREVIEW_SCALE = 1.0;
const MAX_PREVIEW_SCALE = 2.4;
const WORKER_BOOTSTRAP_SETTLE_MS = 80;

const pdfDocumentCache = new Map();
const pdfBundleCache = new Map();

let pdfjsModuleState = { key: "", promise: null };
let pdfjsAssetPreflightState = { key: "", promise: null };
let pdfjsWorkerBootstrapState = {
  key: "",
  promise: null,
  workerPort: null,
  pdfjsModule: null,
};

function currentBuildSha() {
  return String(globalThis.window?.LEGALPDF_BROWSER_BOOTSTRAP?.buildSha || "").trim();
}

function currentAssetVersion() {
  return String(globalThis.window?.LEGALPDF_BROWSER_BOOTSTRAP?.assetVersion || "").trim();
}

function staticBasePath() {
  const configured = String(globalThis.window?.LEGALPDF_BROWSER_BOOTSTRAP?.staticBasePath || "/static/").trim();
  if (configured === "") {
    return "/static/";
  }
  if (/^[a-z][a-z0-9+.-]*:\/\//i.test(configured) || configured.startsWith("//")) {
    return configured.endsWith("/") ? configured : `${configured}/`;
  }
  const withLeadingSlash = configured.startsWith("/") ? configured : `/${configured}`;
  return withLeadingSlash.endsWith("/") ? withLeadingSlash : `${withLeadingSlash}/`;
}

function normalizeText(value) {
  return String(value ?? "").trim();
}

function optionalStatus(value) {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number.parseInt(String(value), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function assetKey(assetUrls) {
  return `${normalizeText(assetUrls?.moduleUrl)}|${normalizeText(assetUrls?.workerUrl)}`;
}

function responseHeaderValue(response, name) {
  if (!response || !response.headers) {
    return "";
  }
  if (typeof response.headers.get === "function") {
    return normalizeText(response.headers.get(name));
  }
  return normalizeText(response.headers[name]);
}

function looksLikeJavaScriptContentType(contentType) {
  const normalized = normalizeText(contentType).toLowerCase();
  return normalized.includes("javascript") || normalized.includes("ecmascript");
}

function rawBrowserErrorText(error) {
  if (!error) {
    return "";
  }
  if (typeof error === "string") {
    return normalizeText(error);
  }
  const message = normalizeText(error.message);
  const name = normalizeText(error.name);
  const filename = normalizeText(error.filename || error.fileName);
  const line = optionalStatus(error.lineno || error.lineNumber);
  const column = optionalStatus(error.colno || error.columnNumber);
  const pieces = [];
  if (name && message) {
    pieces.push(message.startsWith(`${name}:`) ? message : `${name}: ${message}`);
  } else if (message || name) {
    pieces.push(message || name);
  }
  if (filename) {
    let location = filename;
    if (line !== null) {
      location += `:${line}`;
      if (column !== null) {
        location += `:${column}`;
      }
    }
    pieces.push(`at ${location}`);
  }
  const cause = error.cause ? rawBrowserErrorText(error.cause) : "";
  if (cause) {
    pieces.push(`cause: ${cause}`);
  }
  return pieces.filter(Boolean).join(" | ");
}

function extractAttemptedUrl(value) {
  const match = normalizeText(value).match(/https?:\/\/[^\s"')]+/i);
  return match ? match[0] : "";
}

function mergeString(preferred, fallback = "") {
  return normalizeText(preferred) || normalizeText(fallback);
}

function browserPdfErrorDescriptor({ rawMessage, phase, workerBootPhase, moduleFetchStatus, workerFetchStatus }) {
  if (rawMessage.startsWith("PDF fetch failed")) {
    return {
      code: "browser_pdf_source_fetch_failed",
      message: rawMessage || "Browser PDF source fetch failed.",
    };
  }
  if (rawMessage.includes("canvas context")) {
    return {
      code: "browser_pdf_canvas_unavailable",
      message: "Browser PDF preview could not acquire a canvas context.",
    };
  }
  if (
    phase === "worker_boot"
    || rawMessage.includes("Setting up fake worker failed")
    || rawMessage.includes("Cannot use more than one PDFWorker per port.")
    || workerBootPhase !== ""
    || (workerFetchStatus !== null && workerFetchStatus >= 400)
  ) {
    return {
      code: "browser_pdf_worker_load_failed",
      message: "Browser PDF worker could not load, so Gmail preview and preparation could not continue.",
    };
  }
  if (
    phase === "module_import"
    || rawMessage.includes("Failed to fetch dynamically imported module")
    || rawMessage.includes("Cannot find module")
  ) {
    const failedFetch = moduleFetchStatus !== null && moduleFetchStatus >= 400;
    return {
      code: "browser_pdf_module_load_failed",
      message: failedFetch
        ? "Browser PDF module could not be fetched, so Gmail preview and preparation could not continue."
        : "Browser PDF module could not load, so Gmail preview and preparation could not continue.",
    };
  }
  return {
    code: "browser_pdf_render_failed",
    message: rawMessage || "Browser PDF rendering failed.",
  };
}

export function resolveBrowserPdfAssetUrls({
  assetVersion = currentAssetVersion(),
  buildSha = currentBuildSha(),
  origin = String(globalThis.window?.location?.origin || "http://127.0.0.1:8877"),
  basePath = staticBasePath(),
} = {}) {
  const staticRoot = new URL(basePath, origin);
  const moduleUrl = new URL("vendor/pdfjs/pdf.mjs", staticRoot);
  const workerUrl = new URL("vendor/pdfjs/pdf.worker.mjs", staticRoot);
  const resolvedVersion = String(assetVersion || buildSha || "").trim();
  if (resolvedVersion) {
    moduleUrl.searchParams.set("v", resolvedVersion);
    workerUrl.searchParams.set("v", resolvedVersion);
  }
  return {
    moduleUrl: moduleUrl.href,
    workerUrl: workerUrl.href,
  };
}

export function browserPdfDiagnosticsFromError(error) {
  if (error?.browserPdfDiagnostics && typeof error.browserPdfDiagnostics === "object") {
    return { ...error.browserPdfDiagnostics };
  }
  if (error?.payload?.diagnostics && typeof error.payload.diagnostics === "object") {
    return { ...error.payload.diagnostics };
  }
  return {};
}

export function normalizeBrowserPdfError(error, context = {}) {
  const existing = browserPdfDiagnosticsFromError(error);
  const resolvedUrls = resolveBrowserPdfAssetUrls();
  const moduleUrl = mergeString(context.moduleUrl, existing.module_url || resolvedUrls.moduleUrl);
  const workerUrl = mergeString(context.workerUrl, existing.worker_url || resolvedUrls.workerUrl);
  const rawMessage = mergeString(existing.raw_message, error?.message || error || "Browser PDF rendering failed.");
  const rawBrowserError = mergeString(
    context.rawBrowserError,
    existing.raw_browser_error || rawBrowserErrorText(error) || rawMessage,
  );
  const phase = mergeString(context.phase, existing.phase);
  const workerBootPhase = mergeString(context.workerBootPhase, existing.worker_boot_phase);
  const moduleFetchStatus = optionalStatus(context.moduleFetchStatus ?? existing.module_fetch_status);
  const workerFetchStatus = optionalStatus(context.workerFetchStatus ?? existing.worker_fetch_status);
  const moduleContentType = mergeString(context.moduleContentType, existing.module_content_type);
  const workerContentType = mergeString(context.workerContentType, existing.worker_content_type);
  const attemptedUrl = mergeString(
    context.attemptedUrl,
    existing.attempted_url || extractAttemptedUrl(rawBrowserError) || extractAttemptedUrl(rawMessage),
  );
  const descriptor = browserPdfErrorDescriptor({
    rawMessage,
    phase,
    workerBootPhase,
    moduleFetchStatus,
    workerFetchStatus,
  });
  const diagnostics = {
    error: mergeString(existing.error, descriptor.code),
    message: mergeString(existing.message, descriptor.message),
    raw_message: rawMessage,
    raw_browser_error: rawBrowserError,
    phase,
    worker_boot_phase: workerBootPhase,
    asset_version: mergeString(existing.asset_version, currentAssetVersion() || currentBuildSha()),
    module_url: moduleUrl,
    expected_module_url: resolvedUrls.moduleUrl,
    worker_url: workerUrl,
    expected_worker_url: resolvedUrls.workerUrl,
    attempted_url: attemptedUrl,
    module_fetch_status: moduleFetchStatus,
    module_content_type: moduleContentType,
    worker_fetch_status: workerFetchStatus,
    worker_content_type: workerContentType,
    source_path: mergeString(context.sourcePath, existing.source_path),
    attachment_id: mergeString(context.attachmentId, existing.attachment_id),
    preview_url: mergeString(context.url, existing.preview_url),
  };
  const wrapped = error instanceof Error ? error : new Error(rawMessage || diagnostics.message);
  wrapped.name = "BrowserPdfError";
  wrapped.message = diagnostics.message;
  wrapped.payload = {
    status: "failed",
    diagnostics,
  };
  wrapped.browserPdfDiagnostics = diagnostics;
  return wrapped;
}

async function probeBrowserPdfAsset(url, { fetchImpl } = {}) {
  const resolvedFetch = fetchImpl || globalThis.fetch?.bind(globalThis);
  if (typeof resolvedFetch !== "function") {
    return {
      url,
      ok: false,
      jsContentTypeOk: false,
      fetchStatus: null,
      contentType: "",
      errorMessage: "Browser fetch is unavailable for PDF asset preflight.",
    };
  }
  try {
    const response = await resolvedFetch(url, {
      method: "GET",
      credentials: "same-origin",
      cache: "no-store",
    });
    const contentType = responseHeaderValue(response, "content-type");
    try {
      response.body?.cancel?.();
    } catch {
      // Best effort only.
    }
    return {
      url,
      ok: Boolean(response?.ok),
      jsContentTypeOk: looksLikeJavaScriptContentType(contentType),
      fetchStatus: optionalStatus(response?.status),
      contentType,
      errorMessage: "",
    };
  } catch (error) {
    return {
      url,
      ok: false,
      jsContentTypeOk: false,
      fetchStatus: null,
      contentType: "",
      errorMessage: rawBrowserErrorText(error) || normalizeText(error) || "Browser PDF asset preflight failed.",
    };
  }
}

export async function preflightBrowserPdfAssetUrls({
  assetUrls = resolveBrowserPdfAssetUrls(),
  fetchImpl = null,
} = {}) {
  const [moduleAsset, workerAsset] = await Promise.all([
    probeBrowserPdfAsset(assetUrls.moduleUrl, { fetchImpl }),
    probeBrowserPdfAsset(assetUrls.workerUrl, { fetchImpl }),
  ]);
  return {
    module: moduleAsset,
    worker: workerAsset,
  };
}

function ensureModuleAssetPreflight(preflight, assetUrls) {
  const moduleAsset = preflight?.module || {};
  if (!moduleAsset.ok) {
    const rawBrowserError = mergeString(
      moduleAsset.errorMessage,
      `Browser PDF module fetch failed (${moduleAsset.fetchStatus ?? "network"}).`,
    );
    throw normalizeBrowserPdfError(new Error(rawBrowserError), {
      phase: "module_import",
      rawBrowserError,
      attemptedUrl: moduleAsset.url || assetUrls.moduleUrl,
      moduleFetchStatus: moduleAsset.fetchStatus,
      moduleContentType: moduleAsset.contentType,
      workerFetchStatus: preflight?.worker?.fetchStatus,
      workerContentType: preflight?.worker?.contentType,
      moduleUrl: assetUrls.moduleUrl,
      workerUrl: assetUrls.workerUrl,
    });
  }
  if (!moduleAsset.jsContentTypeOk) {
    const rawBrowserError = `Browser PDF module returned unexpected content type: ${moduleAsset.contentType || "unknown"}.`;
    throw normalizeBrowserPdfError(new Error(rawBrowserError), {
      phase: "module_import",
      rawBrowserError,
      attemptedUrl: moduleAsset.url || assetUrls.moduleUrl,
      moduleFetchStatus: moduleAsset.fetchStatus,
      moduleContentType: moduleAsset.contentType,
      workerFetchStatus: preflight?.worker?.fetchStatus,
      workerContentType: preflight?.worker?.contentType,
      moduleUrl: assetUrls.moduleUrl,
      workerUrl: assetUrls.workerUrl,
    });
  }
}

function ensureWorkerAssetPreflight(preflight, assetUrls) {
  const workerAsset = preflight?.worker || {};
  if (!workerAsset.ok) {
    const rawBrowserError = mergeString(
      workerAsset.errorMessage,
      `Browser PDF worker fetch failed (${workerAsset.fetchStatus ?? "network"}).`,
    );
    throw normalizeBrowserPdfError(new Error(rawBrowserError), {
      phase: "worker_boot",
      workerBootPhase: "worker_fetch",
      rawBrowserError,
      attemptedUrl: workerAsset.url || assetUrls.workerUrl,
      moduleFetchStatus: preflight?.module?.fetchStatus,
      moduleContentType: preflight?.module?.contentType,
      workerFetchStatus: workerAsset.fetchStatus,
      workerContentType: workerAsset.contentType,
      moduleUrl: assetUrls.moduleUrl,
      workerUrl: assetUrls.workerUrl,
    });
  }
  if (!workerAsset.jsContentTypeOk) {
    const rawBrowserError = `Browser PDF worker returned unexpected content type: ${workerAsset.contentType || "unknown"}.`;
    throw normalizeBrowserPdfError(new Error(rawBrowserError), {
      phase: "worker_boot",
      workerBootPhase: "worker_content_type",
      rawBrowserError,
      attemptedUrl: workerAsset.url || assetUrls.workerUrl,
      moduleFetchStatus: preflight?.module?.fetchStatus,
      moduleContentType: preflight?.module?.contentType,
      workerFetchStatus: workerAsset.fetchStatus,
      workerContentType: workerAsset.contentType,
      moduleUrl: assetUrls.moduleUrl,
      workerUrl: assetUrls.workerUrl,
    });
  }
}

function workerEventError(event, fallbackMessage) {
  if (event?.error instanceof Error) {
    return event.error;
  }
  const error = new Error(
    normalizeText(event?.message)
    || rawBrowserErrorText(event)
    || normalizeText(fallbackMessage)
    || "Browser PDF worker bootstrap failed.",
  );
  if (event && typeof event === "object") {
    error.filename = event.filename || event.fileName || "";
    error.lineno = event.lineno || event.lineNumber || 0;
    error.colno = event.colno || event.columnNumber || 0;
  }
  return error;
}

async function attemptBrowserPdfWorkerBootstrap({
  workerUrl,
  attemptedUrl,
  workerBootPhase,
  workerFactory,
  setTimeoutImpl,
  clearTimeoutImpl,
  settleDelayMs,
}) {
  try {
    const worker = workerFactory(workerUrl, {
      type: "module",
      name: "legalpdf-browser-pdf-worker",
    });
    if (
      !worker
      || typeof worker.addEventListener !== "function"
      || typeof worker.removeEventListener !== "function"
      || typeof setTimeoutImpl !== "function"
      || typeof clearTimeoutImpl !== "function"
    ) {
      return {
        ok: true,
        workerPort: worker,
        attemptedUrl,
        workerBootPhase,
        rawBrowserError: "",
      };
    }
    return await new Promise((resolve) => {
      let settled = false;
      let timer = 0;
      const finalize = (result) => {
        if (settled) {
          return;
        }
        settled = true;
        clearTimeoutImpl(timer);
        worker.removeEventListener("error", onFailure);
        worker.removeEventListener("messageerror", onFailure);
        if (!result.ok) {
          try {
            worker.terminate?.();
          } catch {
            // Best effort only.
          }
        }
        resolve(result);
      };
      const onFailure = (event) => {
        const failure = workerEventError(event, `Browser PDF worker bootstrap failed at ${attemptedUrl}.`);
        finalize({
          ok: false,
          workerPort: null,
          attemptedUrl,
          workerBootPhase,
          rawBrowserError: rawBrowserErrorText(failure) || failure.message,
        });
      };
      timer = setTimeoutImpl(() => {
        finalize({
          ok: true,
          workerPort: worker,
          attemptedUrl,
          workerBootPhase,
          rawBrowserError: "",
        });
      }, settleDelayMs);
      worker.addEventListener("error", onFailure);
      worker.addEventListener("messageerror", onFailure);
    });
  } catch (error) {
    return {
      ok: false,
      workerPort: null,
      attemptedUrl,
      workerBootPhase,
      rawBrowserError: rawBrowserErrorText(error) || normalizeText(error),
    };
  }
}

export async function bootstrapBrowserPdfWorker({
  pdfjsModule,
  assetUrls = resolveBrowserPdfAssetUrls(),
  preflight = null,
  workerFactory = (url, options) => new Worker(url, options),
  blobFactory = (parts, options) => new Blob(parts, options),
  createObjectUrl = (blob) => URL.createObjectURL(blob),
  revokeObjectUrl = (url) => URL.revokeObjectURL(url),
  setTimeoutImpl = globalThis.setTimeout?.bind(globalThis),
  clearTimeoutImpl = globalThis.clearTimeout?.bind(globalThis),
  settleDelayMs = WORKER_BOOTSTRAP_SETTLE_MS,
} = {}) {
  if (!pdfjsModule?.GlobalWorkerOptions) {
    throw new Error("PDF.js module is required before bootstrapping the browser PDF worker.");
  }
  const resolvedPreflight = preflight || await preflightBrowserPdfAssetUrls({ assetUrls });
  ensureWorkerAssetPreflight(resolvedPreflight, assetUrls);

  const directAttempt = await attemptBrowserPdfWorkerBootstrap({
    workerUrl: assetUrls.workerUrl,
    attemptedUrl: assetUrls.workerUrl,
    workerBootPhase: "worker_bootstrap_direct",
    workerFactory,
    setTimeoutImpl,
    clearTimeoutImpl,
    settleDelayMs,
  });
  if (directAttempt.ok) {
    pdfjsModule.GlobalWorkerOptions.workerSrc = assetUrls.workerUrl;
    pdfjsModule.GlobalWorkerOptions.workerPort = directAttempt.workerPort;
    return {
      workerPort: directAttempt.workerPort,
      workerBootPhase: directAttempt.workerBootPhase,
      rawBrowserError: "",
      preflight: resolvedPreflight,
    };
  }

  let blobWrapperUrl = "";
  let blobAttempt = {
    ok: false,
    workerPort: null,
    attemptedUrl: assetUrls.workerUrl,
    workerBootPhase: "worker_bootstrap_blob_wrapper",
    rawBrowserError: "",
  };
  try {
    blobWrapperUrl = createObjectUrl(
      blobFactory([`await import(${JSON.stringify(assetUrls.workerUrl)});`], {
        type: "text/javascript",
      }),
    );
    blobAttempt = await attemptBrowserPdfWorkerBootstrap({
      workerUrl: blobWrapperUrl,
      attemptedUrl: assetUrls.workerUrl,
      workerBootPhase: "worker_bootstrap_blob_wrapper",
      workerFactory,
      setTimeoutImpl,
      clearTimeoutImpl,
      settleDelayMs,
    });
    if (blobAttempt.ok) {
      pdfjsModule.GlobalWorkerOptions.workerSrc = assetUrls.workerUrl;
      pdfjsModule.GlobalWorkerOptions.workerPort = blobAttempt.workerPort;
      return {
        workerPort: blobAttempt.workerPort,
        workerBootPhase: blobAttempt.workerBootPhase,
        rawBrowserError: directAttempt.rawBrowserError,
        preflight: resolvedPreflight,
      };
    }
  } finally {
    if (blobWrapperUrl) {
      try {
        revokeObjectUrl(blobWrapperUrl);
      } catch {
        // Best effort only.
      }
    }
  }

  const combinedRawError = [directAttempt.rawBrowserError, blobAttempt.rawBrowserError]
    .map((value) => normalizeText(value))
    .filter(Boolean)
    .join(" | ");
  throw normalizeBrowserPdfError(new Error(combinedRawError || "Browser PDF worker bootstrap failed."), {
    phase: "worker_boot",
    workerBootPhase: blobAttempt.workerBootPhase || directAttempt.workerBootPhase,
    rawBrowserError: combinedRawError,
    attemptedUrl: blobAttempt.attemptedUrl || directAttempt.attemptedUrl || assetUrls.workerUrl,
    moduleFetchStatus: resolvedPreflight.module.fetchStatus,
    moduleContentType: resolvedPreflight.module.contentType,
    workerFetchStatus: resolvedPreflight.worker.fetchStatus,
    workerContentType: resolvedPreflight.worker.contentType,
    moduleUrl: assetUrls.moduleUrl,
    workerUrl: assetUrls.workerUrl,
  });
}

function resetBrowserPdfWorkerBootstrap() {
  if (pdfjsWorkerBootstrapState.workerPort?.terminate) {
    try {
      pdfjsWorkerBootstrapState.workerPort.terminate();
    } catch {
      // Best effort only.
    }
  }
  if (pdfjsWorkerBootstrapState.pdfjsModule?.GlobalWorkerOptions) {
    pdfjsWorkerBootstrapState.pdfjsModule.GlobalWorkerOptions.workerPort = null;
  }
  pdfjsWorkerBootstrapState = {
    key: "",
    promise: null,
    workerPort: null,
    pdfjsModule: null,
  };
}

async function cachedBrowserPdfAssetPreflight(assetUrls) {
  const key = assetKey(assetUrls);
  if (!pdfjsAssetPreflightState.promise || pdfjsAssetPreflightState.key !== key) {
    pdfjsAssetPreflightState = {
      key,
      promise: preflightBrowserPdfAssetUrls({ assetUrls }).catch((error) => {
        pdfjsAssetPreflightState = { key: "", promise: null };
        throw error;
      }),
    };
  }
  return pdfjsAssetPreflightState.promise;
}

async function loadPdfjsState() {
  const assetUrls = resolveBrowserPdfAssetUrls();
  const preflight = await cachedBrowserPdfAssetPreflight(assetUrls);
  ensureModuleAssetPreflight(preflight, assetUrls);
  const moduleKey = assetUrls.moduleUrl;
  if (!pdfjsModuleState.promise || pdfjsModuleState.key !== moduleKey) {
    pdfjsModuleState = {
      key: moduleKey,
      promise: import(moduleKey).catch((error) => {
        pdfjsModuleState = { key: "", promise: null };
        throw normalizeBrowserPdfError(error, {
          phase: "module_import",
          rawBrowserError: rawBrowserErrorText(error),
          attemptedUrl: assetUrls.moduleUrl,
          moduleFetchStatus: preflight.module.fetchStatus,
          moduleContentType: preflight.module.contentType,
          workerFetchStatus: preflight.worker.fetchStatus,
          workerContentType: preflight.worker.contentType,
          moduleUrl: assetUrls.moduleUrl,
          workerUrl: assetUrls.workerUrl,
        });
      }),
    };
  }
  const pdfjsModule = await pdfjsModuleState.promise;
  return {
    pdfjsModule,
    assetUrls,
    preflight,
  };
}

async function ensurePdfjsWorkerBootstrap({ pdfjsModule, assetUrls, preflight }) {
  const workerKey = assetKey(assetUrls);
  if (pdfjsWorkerBootstrapState.key !== workerKey) {
    resetBrowserPdfWorkerBootstrap();
  }
  if (!pdfjsWorkerBootstrapState.promise) {
    pdfjsWorkerBootstrapState.key = workerKey;
    pdfjsWorkerBootstrapState.pdfjsModule = pdfjsModule;
    pdfjsWorkerBootstrapState.promise = bootstrapBrowserPdfWorker({
      pdfjsModule,
      assetUrls,
      preflight,
    }).then((result) => {
      pdfjsWorkerBootstrapState.workerPort = result.workerPort || null;
      return result;
    }).catch((error) => {
      resetBrowserPdfWorkerBootstrap();
      throw error;
    });
  }
  const result = await pdfjsWorkerBootstrapState.promise;
  pdfjsModule.GlobalWorkerOptions.workerSrc = assetUrls.workerUrl;
  pdfjsModule.GlobalWorkerOptions.workerPort = result.workerPort;
  return result;
}

function normalizePdfSourceKey({ sourcePath = "", attachmentId = "", url = "", file = null }) {
  const sourceKey = String(sourcePath || "").trim();
  if (sourceKey) {
    return sourceKey;
  }
  const attachmentKey = String(attachmentId || "").trim();
  if (attachmentKey) {
    return attachmentKey;
  }
  if (file) {
    return `${file.name}:${file.size}:${file.lastModified}`;
  }
  return String(url || "").trim();
}

async function bytesFromUrl(url) {
  const response = await fetch(url, { credentials: "same-origin" });
  if (!response.ok) {
    throw new Error(`PDF fetch failed (${response.status}).`);
  }
  return new Uint8Array(await response.arrayBuffer());
}

async function bytesFromFile(file) {
  return new Uint8Array(await file.arrayBuffer());
}

async function loadPdfDocument({
  sourcePath = "",
  attachmentId = "",
  url = "",
  file = null,
}) {
  const cacheKey = normalizePdfSourceKey({ sourcePath, attachmentId, url, file });
  if (pdfDocumentCache.has(cacheKey)) {
    return pdfDocumentCache.get(cacheKey);
  }
  const promise = (async () => {
    const pdfjsState = await loadPdfjsState();
    await ensurePdfjsWorkerBootstrap(pdfjsState);
    const data = file ? await bytesFromFile(file) : await bytesFromUrl(url);
    const loadingTask = pdfjsState.pdfjsModule.getDocument({ data });
    const documentHandle = await loadingTask.promise;
    return {
      cacheKey,
      pdfjs: pdfjsState.pdfjsModule,
      documentHandle,
      pageCount: Number(documentHandle.numPages || 0),
    };
  })();
  pdfDocumentCache.set(cacheKey, promise);
  try {
    return await promise;
  } catch (error) {
    pdfDocumentCache.delete(cacheKey);
    const normalized = normalizeBrowserPdfError(error, {
      phase: mergeString(error?.browserPdfDiagnostics?.phase, "document_load"),
      sourcePath,
      attachmentId,
      url,
    });
    if (
      normalized.browserPdfDiagnostics?.error === "browser_pdf_worker_load_failed"
      || normalized.browserPdfDiagnostics?.phase === "module_import"
      || normalized.browserPdfDiagnostics?.phase === "worker_boot"
    ) {
      resetBrowserPdfWorkerBootstrap();
    }
    throw normalized;
  }
}

function previewScaleForPage(page, preferredWidth = 0) {
  const baseViewport = page.getViewport({ scale: 1 });
  if (preferredWidth > 0 && baseViewport.width > 0) {
    const fittedScale = preferredWidth / baseViewport.width;
    return Math.min(MAX_PREVIEW_SCALE, Math.max(MIN_PREVIEW_SCALE, fittedScale));
  }
  return 1.35;
}

function renderViewportDimensions(viewport) {
  return {
    widthPx: Math.max(1, Math.ceil(viewport.width)),
    heightPx: Math.max(1, Math.ceil(viewport.height)),
  };
}

function canvasToBlob(canvas, mimeType = "image/png") {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) {
        resolve(blob);
        return;
      }
      reject(new Error("Browser PDF rendering could not create an image blob."));
    }, mimeType);
  });
}

async function renderPdfPageBlob(documentHandle, pageNumber, { scale = DEFAULT_BUNDLE_SCALE } = {}) {
  const page = await documentHandle.getPage(pageNumber);
  const viewport = page.getViewport({ scale });
  const canvas = document.createElement("canvas");
  const dimensions = renderViewportDimensions(viewport);
  canvas.width = dimensions.widthPx;
  canvas.height = dimensions.heightPx;
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) {
    throw new Error("Browser PDF rendering could not acquire a canvas context.");
  }
  await page.render({ canvasContext: context, viewport }).promise;
  const blob = await canvasToBlob(canvas, "image/png");
  return {
    pageNumber,
    fileName: `page_${String(pageNumber).padStart(4, "0")}.png`,
    mimeType: "image/png",
    widthPx: dimensions.widthPx,
    heightPx: dimensions.heightPx,
    blob,
  };
}

async function uploadBrowserPdfBundle({
  appState,
  sourcePath,
  attachmentId = "",
  pageCount,
  renderedPages,
}) {
  const manifest = {
    source_path: sourcePath,
    attachment_id: attachmentId,
    page_count: pageCount,
    pages: renderedPages.map((item) => ({
      page_number: item.pageNumber,
      file_name: item.fileName,
      mime_type: item.mimeType,
      width_px: item.widthPx,
      height_px: item.heightPx,
    })),
  };
  const form = new FormData();
  form.append("manifest", JSON.stringify(manifest));
  for (const page of renderedPages) {
    form.append("page_images", page.blob, page.fileName);
  }
  const payload = await fetchJson("/api/browser-pdf/bundle", appState, {
    method: "POST",
    body: form,
  });
  return payload.normalized_payload || {};
}

export async function ensureBrowserPdfBundleFromFile({
  appState,
  sourcePath,
  file,
}) {
  const cacheKey = normalizePdfSourceKey({ sourcePath, file });
  if (pdfBundleCache.has(cacheKey)) {
    return pdfBundleCache.get(cacheKey);
  }
  const documentState = await loadPdfDocument({ sourcePath, file });
  const renderedPages = [];
  for (let pageNumber = 1; pageNumber <= documentState.pageCount; pageNumber += 1) {
    renderedPages.push(await renderPdfPageBlob(documentState.documentHandle, pageNumber));
  }
  const bundlePayload = await uploadBrowserPdfBundle({
    appState,
    sourcePath,
    pageCount: documentState.pageCount,
    renderedPages,
  });
  pdfBundleCache.set(cacheKey, bundlePayload);
  return bundlePayload;
}

export async function ensureBrowserPdfBundleFromUrl({
  appState,
  sourcePath,
  url,
  attachmentId = "",
}) {
  const cacheKey = normalizePdfSourceKey({ sourcePath, attachmentId, url });
  if (pdfBundleCache.has(cacheKey)) {
    return pdfBundleCache.get(cacheKey);
  }
  const documentState = await loadPdfDocument({ sourcePath, attachmentId, url });
  const renderedPages = [];
  for (let pageNumber = 1; pageNumber <= documentState.pageCount; pageNumber += 1) {
    renderedPages.push(await renderPdfPageBlob(documentState.documentHandle, pageNumber));
  }
  const bundlePayload = await uploadBrowserPdfBundle({
    appState,
    sourcePath,
    attachmentId,
    pageCount: documentState.pageCount,
    renderedPages,
  });
  pdfBundleCache.set(cacheKey, bundlePayload);
  return bundlePayload;
}

export async function renderBrowserPdfPreviewToCanvas({
  sourcePath,
  url,
  attachmentId = "",
  pageNumber,
  canvas,
  preferredWidth = 0,
}) {
  if (!(canvas instanceof HTMLCanvasElement)) {
    throw new Error("A preview canvas is required for browser PDF rendering.");
  }
  const documentState = await loadPdfDocument({ sourcePath, attachmentId, url });
  const safePageNumber = Math.min(
    Math.max(1, Number.parseInt(String(pageNumber || "1"), 10) || 1),
    Math.max(1, documentState.pageCount),
  );
  const page = await documentState.documentHandle.getPage(safePageNumber);
  const scale = previewScaleForPage(page, preferredWidth);
  const viewport = page.getViewport({ scale });
  const dimensions = renderViewportDimensions(viewport);
  canvas.width = dimensions.widthPx;
  canvas.height = dimensions.heightPx;
  const context = canvas.getContext("2d", { alpha: false });
  if (!context) {
    throw new Error("Browser PDF preview could not acquire a canvas context.");
  }
  await page.render({ canvasContext: context, viewport }).promise;
  return {
    pageCount: documentState.pageCount,
    pageNumber: safePageNumber,
    widthPx: dimensions.widthPx,
    heightPx: dimensions.heightPx,
  };
}
