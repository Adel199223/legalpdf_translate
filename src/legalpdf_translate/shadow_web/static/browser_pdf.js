import { fetchJson } from "./api.js";

const DEFAULT_BUNDLE_SCALE = 2.0;
const MIN_PREVIEW_SCALE = 1.0;
const MAX_PREVIEW_SCALE = 2.4;

const pdfDocumentCache = new Map();
const pdfBundleCache = new Map();

let pdfjsModulePromise = null;

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

function extractAttemptedUrl(value) {
  const match = String(value || "").match(/https?:\/\/[^\s"')]+/i);
  return match ? match[0] : "";
}

function normalizeBrowserPdfError(error, context = {}) {
  const rawMessage = String(error?.message || error || "Browser PDF rendering failed.").trim();
  const { moduleUrl, workerUrl } = resolveBrowserPdfAssetUrls();
  const assetVersion = currentAssetVersion() || currentBuildSha();
  const attemptedUrl = extractAttemptedUrl(rawMessage);
  let code = "browser_pdf_render_failed";
  let message = rawMessage || "Browser PDF rendering failed.";
  if (
    rawMessage.includes("Setting up fake worker failed")
    || rawMessage.includes("Failed to fetch dynamically imported module")
  ) {
    code = "browser_pdf_worker_load_failed";
    message = "Browser PDF worker could not load, so Gmail preview and preparation could not continue.";
  } else if (rawMessage.startsWith("PDF fetch failed")) {
    code = "browser_pdf_source_fetch_failed";
  } else if (rawMessage.includes("canvas context")) {
    code = "browser_pdf_canvas_unavailable";
  }
  const diagnostics = {
    error: code,
    message,
    raw_message: rawMessage,
    phase: String(context.phase || "").trim(),
    asset_version: assetVersion,
    module_url: moduleUrl,
    expected_module_url: moduleUrl,
    worker_url: workerUrl,
    expected_worker_url: workerUrl,
    attempted_url: attemptedUrl,
    source_path: String(context.sourcePath || "").trim(),
    attachment_id: String(context.attachmentId || "").trim(),
    preview_url: String(context.url || "").trim(),
  };
  const wrapped = error instanceof Error ? error : new Error(rawMessage || message);
  wrapped.name = "BrowserPdfError";
  wrapped.message = message;
  wrapped.payload = {
    status: "failed",
    diagnostics,
  };
  wrapped.browserPdfDiagnostics = diagnostics;
  return wrapped;
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

async function loadPdfjsModule() {
  const { moduleUrl, workerUrl } = resolveBrowserPdfAssetUrls();
  if (!pdfjsModulePromise) {
    pdfjsModulePromise = import(moduleUrl).catch((error) => {
      pdfjsModulePromise = null;
      throw normalizeBrowserPdfError(error, { phase: "module_import" });
    });
  }
  const pdfjsModule = await pdfjsModulePromise;
  if (pdfjsModule.GlobalWorkerOptions.workerSrc !== workerUrl) {
    pdfjsModule.GlobalWorkerOptions.workerSrc = workerUrl;
  }
  return pdfjsModule;
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
    const pdfjs = await loadPdfjsModule();
    const data = file ? await bytesFromFile(file) : await bytesFromUrl(url);
    const loadingTask = pdfjs.getDocument({ data });
    const documentHandle = await loadingTask.promise;
    return {
      cacheKey,
      pdfjs,
      documentHandle,
      pageCount: Number(documentHandle.numPages || 0),
    };
  })();
  pdfDocumentCache.set(cacheKey, promise);
  try {
    return await promise;
  } catch (error) {
    pdfDocumentCache.delete(cacheKey);
    throw normalizeBrowserPdfError(error, {
      phase: "document_load",
      sourcePath,
      attachmentId,
      url,
    });
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
