const DEFAULT_BRIDGE_PORT = 8765;
const NATIVE_FOCUS_HOST = "com.legalpdf.gmail_focus";
const COLD_START_TAB_WAIT_MS = 2200;
const COLD_START_TAB_POLL_MS = 150;
const WORKSPACE_READY_WAIT_MS = 3200;
const COLD_START_WORKSPACE_READY_WAIT_MS = 5200;
const WORKSPACE_READY_POLL_MS = 140;
const LAUNCH_READINESS_WAIT_MS = 35000;
const HANDOFF_LOCK_MAX_AGE_MS = (
  LAUNCH_READINESS_WAIT_MS
  + COLD_START_TAB_WAIT_MS
  + COLD_START_WORKSPACE_READY_WAIT_MS
  + WORKSPACE_READY_POLL_MS
);
const DEFAULT_BROWSER_APP_URL = "http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake";
const WORKSPACE_PENDING_STATUSES = new Set(["warming", "delayed"]);
const BRIDGE_INTEGRITY_FAILURE_REASONS = new Set([
  "bridge_browser_mismatch",
  "split_brain_browser_owner",
]);
const EXTENSION_PROVENANCE_DRIFT_REASONS = new Set([
  "extension_source_drift",
]);
const IS_EXTENSION_TEST = Boolean(globalThis && globalThis.__LEGALPDF_TEST__ === true);
const CLIENT_HYDRATION_WAIT_MS = IS_EXTENSION_TEST ? 40 : 2600;
const CLIENT_HYDRATION_RELOAD_WAIT_MS = IS_EXTENSION_TEST ? 60 : 3600;
const CLIENT_HYDRATION_POLL_MS = IS_EXTENSION_TEST ? 1 : 140;

const handoffInFlight = new Map();
const gmailClickSessions = new Map();
const pendingBrowserSurfaces = new Map();
const GMAIL_CLICK_SESSIONS_SESSION_KEY = "legalpdfGmailClickSessions";
const PENDING_BROWSER_SURFACES_SESSION_KEY = "legalpdfPendingBrowserSurfaces";
const activeBrowserLaunchSessions = new Map();
const ACTIVE_BROWSER_LAUNCH_SESSIONS_SESSION_KEY = "legalpdfActiveBrowserLaunchSessions";
const BROWSER_OPEN_OWNER_EXTENSION = "extension";
const BROWSER_OPEN_OWNER_SERVER_BOOT = "server_boot";
const STRICT_BROWSER_WORKSPACES = new Set(["gmail-intake"]);
const EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION = 4;
const GMAIL_CLICK_PHASE_CONTEXT_EXTRACTED = "context_extracted";
const GMAIL_CLICK_PHASE_NATIVE_PREPARE_OK = "native_prepare_ok";
const GMAIL_CLICK_PHASE_SAME_TAB_REDIRECT_STARTED = "same_tab_redirect_started";
const GMAIL_CLICK_PHASE_SAME_TAB_REDIRECT_COMMITTED = "same_tab_redirect_committed";
const GMAIL_CLICK_PHASE_WORKSPACE_CLIENT_READY = "workspace_client_ready";
const GMAIL_CLICK_PHASE_BRIDGE_CONTEXT_POSTED = "bridge_context_posted";
const GMAIL_CLICK_PHASE_RESTORED_TO_GMAIL = "restored_to_gmail";
const GMAIL_CLICK_PHASE_FAILED = "failed";
let pendingBrowserSurfacesLoaded = false;
let activeBrowserLaunchSessionsLoaded = false;
let gmailClickSessionsLoaded = false;
let handoffSequence = 0;

function normalizePort(value) {
  const parsed = Number.parseInt(String(value ?? DEFAULT_BRIDGE_PORT), 10);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    return DEFAULT_BRIDGE_PORT;
  }
  return parsed;
}

function normalizeToken(value) {
  return String(value ?? "").trim();
}

function normalizeSchemaVersion(value) {
  const parsed = Number.parseInt(String(value ?? "").trim(), 10);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : 0;
}

function normalizeUrl(value) {
  return String(value ?? "").trim();
}

async function withTimeout(promise, timeoutMs, fallbackValue) {
  const boundedTimeoutMs = Math.max(1, Number(timeoutMs || 0));
  let timeoutId = null;
  try {
    return await Promise.race([
      promise,
      new Promise((resolve) => {
        timeoutId = setTimeout(() => resolve(fallbackValue), boundedTimeoutMs);
      }),
    ]);
  } finally {
    if (timeoutId !== null) {
      clearTimeout(timeoutId);
    }
  }
}

function buildPendingBrowserSurfaceKey(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return "";
  }
  try {
    const parsed = new URL(targetUrl);
    const runtimeMode = normalizeToken(parsed.searchParams.get("mode")).toLowerCase() || "live";
    const workspaceId = normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1";
    return `${parsed.origin}${parsed.pathname}?mode=${runtimeMode}&workspace=${workspaceId}`;
  } catch (_error) {
    return targetUrl;
  }
}

function buildSameTabRedirectUrl(
  browserUrl,
  {
    launchSessionId = "",
    handoffSessionId = "",
    launchSessionSchemaVersion = EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION,
  } = {},
) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return "";
  }
  try {
    const parsed = new URL(targetUrl);
    const normalizedLaunchSessionId = normalizeToken(launchSessionId);
    const normalizedHandoffSessionId = normalizeToken(handoffSessionId);
    const normalizedSchemaVersion = normalizeSchemaVersion(launchSessionSchemaVersion);
    if (normalizedLaunchSessionId !== "") {
      parsed.searchParams.set("launch_session_id", normalizedLaunchSessionId);
    }
    if (normalizedHandoffSessionId !== "") {
      parsed.searchParams.set("handoff_session_id", normalizedHandoffSessionId);
    }
    if (normalizedSchemaVersion > 0) {
      parsed.searchParams.set("launch_session_schema_version", String(normalizedSchemaVersion));
    }
    return parsed.toString();
  } catch (_error) {
    return targetUrl;
  }
}

function pendingBrowserSurfaceStorage() {
  if (!chrome?.storage?.session) {
    return null;
  }
  if (typeof chrome.storage.session.get !== "function" || typeof chrome.storage.session.set !== "function") {
    return null;
  }
  return chrome.storage.session;
}

function normalizeGmailClickSessionRecord(record) {
  const tabId = Number.isInteger(record?.tabId) ? record.tabId : null;
  if (!Number.isInteger(tabId)) {
    return null;
  }
  return {
    tabId,
    sourceGmailUrl: normalizeUrl(record?.sourceGmailUrl),
    browserUrl: normalizeUrl(record?.browserUrl),
    launchSessionId: normalizeToken(record?.launchSessionId),
    handoffSessionId: normalizeToken(record?.handoffSessionId),
    phase: normalizeToken(record?.phase).toLowerCase(),
    failureReason: normalizeToken(record?.failureReason),
    bridgeContextPosted: record?.bridgeContextPosted === true,
    createdAt: Number.isInteger(record?.createdAt) ? record.createdAt : Date.now(),
    updatedAt: Number.isInteger(record?.updatedAt) ? record.updatedAt : Date.now(),
  };
}

function isActiveGmailClickPhase(phase) {
  return new Set([
    GMAIL_CLICK_PHASE_CONTEXT_EXTRACTED,
    GMAIL_CLICK_PHASE_NATIVE_PREPARE_OK,
    GMAIL_CLICK_PHASE_SAME_TAB_REDIRECT_STARTED,
    GMAIL_CLICK_PHASE_SAME_TAB_REDIRECT_COMMITTED,
    GMAIL_CLICK_PHASE_WORKSPACE_CLIENT_READY,
  ]).has(normalizeToken(phase).toLowerCase());
}

async function ensureGmailClickSessionsLoaded() {
  if (gmailClickSessionsLoaded) {
    return;
  }
  gmailClickSessionsLoaded = true;
  const storage = pendingBrowserSurfaceStorage();
  if (!storage) {
    return;
  }
  try {
    const stored = await storage.get([GMAIL_CLICK_SESSIONS_SESSION_KEY]);
    const rawRecords = stored?.[GMAIL_CLICK_SESSIONS_SESSION_KEY];
    if (!rawRecords || typeof rawRecords !== "object") {
      return;
    }
    gmailClickSessions.clear();
    for (const [key, record] of Object.entries(rawRecords)) {
      const normalized = normalizeGmailClickSessionRecord(record);
      if (normalized) {
        gmailClickSessions.set(String(key), normalized);
      }
    }
  } catch (_error) {
    // Fall back to the in-memory map when session storage is unavailable.
  }
}

async function persistGmailClickSessions() {
  const storage = pendingBrowserSurfaceStorage();
  if (!storage) {
    return;
  }
  const serialized = {};
  for (const [key, record] of gmailClickSessions.entries()) {
    const normalized = normalizeGmailClickSessionRecord(record);
    if (normalized) {
      serialized[key] = normalized;
    }
  }
  try {
    await storage.set({
      [GMAIL_CLICK_SESSIONS_SESSION_KEY]: serialized,
    });
  } catch (_error) {
    // Keep the in-memory registry if persistence fails.
  }
}

async function getGmailClickSession(tabId) {
  await ensureGmailClickSessionsLoaded();
  if (!Number.isInteger(tabId)) {
    return null;
  }
  const key = String(tabId);
  const normalized = normalizeGmailClickSessionRecord(gmailClickSessions.get(key));
  if (!normalized) {
    gmailClickSessions.delete(key);
    await persistGmailClickSessions();
    return null;
  }
  if (Date.now() - normalized.updatedAt > HANDOFF_LOCK_MAX_AGE_MS) {
    gmailClickSessions.delete(key);
    await persistGmailClickSessions();
    return null;
  }
  gmailClickSessions.set(key, normalized);
  return normalized;
}

async function rememberGmailClickSession(tabId, fields = {}) {
  await ensureGmailClickSessionsLoaded();
  if (!Number.isInteger(tabId)) {
    return null;
  }
  const key = String(tabId);
  const existing = normalizeGmailClickSessionRecord(gmailClickSessions.get(key));
  const now = Date.now();
  const next = normalizeGmailClickSessionRecord({
    tabId,
    sourceGmailUrl: normalizeUrl(fields?.sourceGmailUrl || existing?.sourceGmailUrl),
    browserUrl: normalizeUrl(fields?.browserUrl || existing?.browserUrl),
    launchSessionId: normalizeToken(fields?.launchSessionId || existing?.launchSessionId),
    handoffSessionId: normalizeToken(fields?.handoffSessionId || existing?.handoffSessionId),
    phase: normalizeToken(fields?.phase || existing?.phase),
    failureReason: normalizeToken(fields?.failureReason || existing?.failureReason),
    bridgeContextPosted: fields?.bridgeContextPosted === true || existing?.bridgeContextPosted === true,
    createdAt: existing?.createdAt || now,
    updatedAt: now,
  });
  if (!next) {
    return null;
  }
  gmailClickSessions.set(key, next);
  await persistGmailClickSessions();
  return next;
}

async function clearGmailClickSession(tabId) {
  await ensureGmailClickSessionsLoaded();
  if (!Number.isInteger(tabId)) {
    return;
  }
  gmailClickSessions.delete(String(tabId));
  await persistGmailClickSessions();
}

function normalizePendingBrowserSurfaceRecord(record) {
  const tabId = Number.isInteger(record?.tabId) ? record.tabId : null;
  if (!Number.isInteger(tabId)) {
    return null;
  }
  return {
    browserUrl: normalizeUrl(record?.browserUrl),
    tabId,
    windowId: Number.isInteger(record?.windowId) ? record.windowId : null,
    createdAt: Number.isInteger(record?.createdAt) ? record.createdAt : Date.now(),
    updatedAt: Number.isInteger(record?.updatedAt) ? record.updatedAt : Date.now(),
    launchSessionId: normalizeToken(record?.launchSessionId),
    handoffSessionId: normalizeToken(record?.handoffSessionId),
    browserOpenOwnedBy: normalizeToken(record?.browserOpenOwnedBy).toLowerCase(),
    resolutionStrategy: normalizeToken(record?.resolutionStrategy).toLowerCase(),
    surfaceCandidateSource: normalizeToken(record?.surfaceCandidateSource).toLowerCase(),
    surfaceCandidateValid: record?.surfaceCandidateValid !== false,
    surfaceInvalidationReason: normalizeToken(record?.surfaceInvalidationReason),
    freshTabCreatedAfterInvalidation: record?.freshTabCreatedAfterInvalidation === true,
  };
}

function normalizeActiveBrowserLaunchSessionRecord(record) {
  const launchSessionId = normalizeToken(record?.launchSessionId);
  const browserUrl = normalizeUrl(record?.browserUrl);
  if (launchSessionId === "" || browserUrl === "") {
    return null;
  }
  const createdAt = Number.isInteger(record?.createdAt) ? record.createdAt : Date.now();
  const updatedAt = Number.isInteger(record?.updatedAt) ? record.updatedAt : createdAt;
  const fallbackExpiresAt = updatedAt + LAUNCH_READINESS_WAIT_MS;
  const expiresAt = Number.isInteger(record?.expiresAt) ? record.expiresAt : fallbackExpiresAt;
  return {
    launchSessionId,
    handoffSessionId: normalizeToken(record?.handoffSessionId),
    browserUrl,
    owner: normalizeToken(record?.owner).toLowerCase() || BROWSER_OPEN_OWNER_SERVER_BOOT,
    createdAt,
    updatedAt,
    expiresAt: Math.max(updatedAt, expiresAt),
  };
}

async function ensurePendingBrowserSurfacesLoaded() {
  if (pendingBrowserSurfacesLoaded) {
    return;
  }
  pendingBrowserSurfacesLoaded = true;
  const storage = pendingBrowserSurfaceStorage();
  if (!storage) {
    return;
  }
  try {
    const stored = await storage.get([PENDING_BROWSER_SURFACES_SESSION_KEY]);
    const rawRecords = stored?.[PENDING_BROWSER_SURFACES_SESSION_KEY];
    if (!rawRecords || typeof rawRecords !== "object") {
      return;
    }
    pendingBrowserSurfaces.clear();
    for (const [key, record] of Object.entries(rawRecords)) {
      const normalized = normalizePendingBrowserSurfaceRecord(record);
      const normalizedKey = buildPendingBrowserSurfaceKey(key);
      if (normalized && normalizedKey !== "") {
        pendingBrowserSurfaces.set(normalizedKey, normalized);
      }
    }
  } catch (_error) {
    // Fall back to the in-memory map when session storage is unavailable.
  }
}

async function persistPendingBrowserSurfaces() {
  const storage = pendingBrowserSurfaceStorage();
  if (!storage) {
    return;
  }
  const serialized = {};
  for (const [key, record] of pendingBrowserSurfaces.entries()) {
    const normalized = normalizePendingBrowserSurfaceRecord(record);
    if (normalized) {
      serialized[key] = normalized;
    }
  }
  try {
    await storage.set({
      [PENDING_BROWSER_SURFACES_SESSION_KEY]: serialized,
    });
  } catch (_error) {
    // Keep the in-memory registry if persistence fails.
  }
}

async function ensureActiveBrowserLaunchSessionsLoaded() {
  if (activeBrowserLaunchSessionsLoaded) {
    return;
  }
  activeBrowserLaunchSessionsLoaded = true;
  const storage = pendingBrowserSurfaceStorage();
  if (!storage) {
    return;
  }
  try {
    const stored = await storage.get([ACTIVE_BROWSER_LAUNCH_SESSIONS_SESSION_KEY]);
    const rawRecords = stored?.[ACTIVE_BROWSER_LAUNCH_SESSIONS_SESSION_KEY];
    if (!rawRecords || typeof rawRecords !== "object") {
      return;
    }
    activeBrowserLaunchSessions.clear();
    for (const [key, record] of Object.entries(rawRecords)) {
      const normalized = normalizeActiveBrowserLaunchSessionRecord(record);
      const normalizedKey = buildPendingBrowserSurfaceKey(key);
      if (normalized && normalizedKey !== "") {
        activeBrowserLaunchSessions.set(normalizedKey, normalized);
      }
    }
  } catch (_error) {
    // Fall back to the in-memory map when session storage is unavailable.
  }
}

async function persistActiveBrowserLaunchSessions() {
  const storage = pendingBrowserSurfaceStorage();
  if (!storage) {
    return;
  }
  const serialized = {};
  for (const [key, record] of activeBrowserLaunchSessions.entries()) {
    const normalized = normalizeActiveBrowserLaunchSessionRecord(record);
    if (normalized) {
      serialized[key] = normalized;
    }
  }
  try {
    await storage.set({
      [ACTIVE_BROWSER_LAUNCH_SESSIONS_SESSION_KEY]: serialized,
    });
  } catch (_error) {
    // Keep the in-memory registry if persistence fails.
  }
}

async function rememberPendingBrowserSurface(browserUrl, tabLike, options = {}) {
  await ensurePendingBrowserSurfacesLoaded();
  const key = buildPendingBrowserSurfaceKey(browserUrl);
  if (key === "") {
    return null;
  }
  const tabId = Number.isInteger(tabLike?.id) ? tabLike.id : Number.isInteger(tabLike?.tabId) ? tabLike.tabId : null;
  if (!Number.isInteger(tabId)) {
    return null;
  }
  const existing = pendingBrowserSurfaces.get(key);
  const nextRecord = {
    browserUrl: normalizeUrl(browserUrl),
    tabId,
    windowId: Number.isInteger(tabLike?.windowId)
      ? tabLike.windowId
      : Number.isInteger(existing?.windowId)
        ? existing.windowId
        : null,
    createdAt: Number.isInteger(existing?.createdAt) ? existing.createdAt : Date.now(),
    updatedAt: Date.now(),
    launchSessionId: normalizeToken(options?.launchSessionId) || normalizeToken(existing?.launchSessionId),
    handoffSessionId: normalizeToken(options?.handoffSessionId) || normalizeToken(existing?.handoffSessionId),
    browserOpenOwnedBy: normalizeToken(options?.browserOpenOwnedBy || existing?.browserOpenOwnedBy).toLowerCase(),
    resolutionStrategy: normalizeToken(options?.resolutionStrategy || existing?.resolutionStrategy).toLowerCase(),
    surfaceCandidateSource: normalizeToken(options?.surfaceCandidateSource || existing?.surfaceCandidateSource).toLowerCase(),
    surfaceCandidateValid: options?.surfaceCandidateValid === undefined
      ? existing?.surfaceCandidateValid !== false
      : options.surfaceCandidateValid === true,
    surfaceInvalidationReason: normalizeToken(
      options?.surfaceInvalidationReason === undefined
        ? existing?.surfaceInvalidationReason
        : options?.surfaceInvalidationReason,
    ),
    freshTabCreatedAfterInvalidation: options?.freshTabCreatedAfterInvalidation === undefined
      ? existing?.freshTabCreatedAfterInvalidation === true
      : options.freshTabCreatedAfterInvalidation === true,
  };
  pendingBrowserSurfaces.set(key, nextRecord);
  await persistPendingBrowserSurfaces();
  return nextRecord;
}

async function clearPendingBrowserSurface(browserUrl) {
  await ensurePendingBrowserSurfacesLoaded();
  const key = buildPendingBrowserSurfaceKey(browserUrl);
  if (key === "") {
    return;
  }
  pendingBrowserSurfaces.delete(key);
  await persistPendingBrowserSurfaces();
}

async function clearPendingBrowserSurfaceByTabId(tabId) {
  await ensurePendingBrowserSurfacesLoaded();
  if (!Number.isInteger(tabId)) {
    return;
  }
  let changed = false;
  for (const [key, record] of pendingBrowserSurfaces.entries()) {
    if (record && record.tabId === tabId) {
      pendingBrowserSurfaces.delete(key);
      changed = true;
    }
  }
  if (changed) {
    await persistPendingBrowserSurfaces();
  }
}

async function rememberActiveBrowserLaunchSession(browserUrl, sessionLike) {
  await ensureActiveBrowserLaunchSessionsLoaded();
  const key = buildPendingBrowserSurfaceKey(browserUrl);
  if (key === "") {
    return null;
  }
  const launchSessionId = normalizeToken(sessionLike?.launchSessionId);
  if (launchSessionId === "") {
    return null;
  }
  const existing = activeBrowserLaunchSessions.get(key);
  const createdAt = Number.isInteger(existing?.createdAt) ? existing.createdAt : Date.now();
  const updatedAt = Date.now();
  const ttlMs = Math.max(
    1000,
    Number.isInteger(sessionLike?.ttlMs) ? sessionLike.ttlMs : LAUNCH_READINESS_WAIT_MS,
  );
  const nextRecord = {
    launchSessionId,
    handoffSessionId: normalizeToken(sessionLike?.handoffSessionId || existing?.handoffSessionId),
    browserUrl: normalizeUrl(browserUrl),
    owner: normalizeToken(sessionLike?.owner || existing?.owner).toLowerCase() || BROWSER_OPEN_OWNER_SERVER_BOOT,
    createdAt,
    updatedAt,
    expiresAt: updatedAt + ttlMs,
  };
  activeBrowserLaunchSessions.set(key, nextRecord);
  await persistActiveBrowserLaunchSessions();
  return nextRecord;
}

async function clearActiveBrowserLaunchSession(browserUrl) {
  await ensureActiveBrowserLaunchSessionsLoaded();
  const key = buildPendingBrowserSurfaceKey(browserUrl);
  if (key === "") {
    return;
  }
  activeBrowserLaunchSessions.delete(key);
  await persistActiveBrowserLaunchSessions();
}

async function getActiveBrowserLaunchSession(browserUrl) {
  await ensureActiveBrowserLaunchSessionsLoaded();
  const key = buildPendingBrowserSurfaceKey(browserUrl);
  if (key === "") {
    return null;
  }
  const record = normalizeActiveBrowserLaunchSessionRecord(activeBrowserLaunchSessions.get(key));
  if (!record) {
    activeBrowserLaunchSessions.delete(key);
    await persistActiveBrowserLaunchSessions();
    return null;
  }
  if (record.expiresAt <= Date.now()) {
    activeBrowserLaunchSessions.delete(key);
    await persistActiveBrowserLaunchSessions();
    return null;
  }
  return record;
}

async function focusPendingBrowserSurface(browserUrl, options = {}) {
  const resolved = await resolveBrowserAppTab(browserUrl, options);
  const tab = resolved?.tab || null;
  if (!tab || !Number.isInteger(tab.id)) {
    return false;
  }
  try {
    const updated = await chrome.tabs.update(tab.id, { active: true });
    const windowId = Number.isInteger(updated?.windowId) ? updated.windowId : tab.windowId;
    if (Number.isInteger(windowId)) {
      await chrome.windows.update(windowId, { focused: true });
    }
    await rememberPendingBrowserSurface(browserUrl, {
      tabId: tab.id,
      windowId,
    }, {
      launchSessionId: normalizeToken(resolved?.launchSessionId),
      handoffSessionId: normalizeToken(resolved?.handoffSessionId || options?.expectedHandoffSessionId || options?.handoffSessionId),
      browserOpenOwnedBy: normalizeToken(resolved?.browserOpenOwnedBy),
      resolutionStrategy: normalizeToken(resolved?.resolutionStrategy),
      surfaceCandidateSource: normalizeToken(resolved?.surfaceCandidateSource),
      surfaceCandidateValid: resolved?.surfaceCandidateValid === true,
      surfaceInvalidationReason: "",
      freshTabCreatedAfterInvalidation: resolved?.freshTabCreatedAfterInvalidation === true,
    });
    return true;
  } catch (_error) {
    await clearPendingBrowserSurfaceByTabId(tab.id);
    return false;
  }
}

function buildBridgeEndpoint(config) {
  return `http://127.0.0.1:${normalizePort(config && config.bridgePort)}/gmail-intake`;
}

function sleep(ms) {
  return new Promise((resolve) => globalThis.setTimeout(resolve, ms));
}

async function getStoredBridgeConfig() {
  const stored = await chrome.storage.local.get(["bridgePort", "bridgeToken"]);
  return {
    bridgePort: normalizePort(stored.bridgePort),
    bridgeToken: normalizeToken(stored.bridgeToken),
  };
}

async function setStoredBridgeConfig(config) {
  const bridgeToken = normalizeToken(config && config.bridgeToken);
  if (bridgeToken === "") {
    return;
  }
  await chrome.storage.local.set({
    bridgePort: normalizePort(config && config.bridgePort),
    bridgeToken,
  });
}

function buildHandoffKey(tabId, context) {
  const tabPart = Number.isInteger(tabId) ? String(tabId) : "tab";
  const messageId = normalizeToken(context && context.message_id);
  const threadId = normalizeToken(context && context.thread_id);
  return `${tabPart}:${messageId || threadId || "unknown"}`;
}

function claimHandoffLock(tabId, context) {
  const key = buildHandoffKey(tabId, context);
  const existing = handoffInFlight.get(key);
  const now = Date.now();
  if (existing && now - existing.startedAt <= HANDOFF_LOCK_MAX_AGE_MS) {
    return {
      ok: false,
      key,
      staleRecovered: false,
    };
  }
  const staleRecovered = Boolean(existing);
  if (staleRecovered) {
    handoffInFlight.delete(key);
  }
  const token = `handoff-${now}-${++handoffSequence}`;
  handoffInFlight.set(key, {
    token,
    startedAt: now,
  });
  return {
    ok: true,
    key,
    token,
    staleRecovered,
  };
}

async function claimOrRecoverHandoffLock(
  tabId,
  context,
  {
    browserUrl = DEFAULT_BROWSER_APP_URL,
    preferredWindowId = null,
  } = {},
) {
  let lock = claimHandoffLock(tabId, context);
  if (lock.ok) {
    return {
      ...lock,
      recoveredMissingSurfaceLock: false,
      existingSurfaceFocused: false,
    };
  }

  const focusedExistingSurface = await focusExistingBrowserAppWindow(browserUrl, {
    preferredWindowId,
  });
  if (focusedExistingSurface) {
    return {
      ...lock,
      recoveredMissingSurfaceLock: false,
      existingSurfaceFocused: true,
    };
  }

  handoffInFlight.delete(lock.key);
  lock = claimHandoffLock(tabId, context);
  return {
    ...lock,
    staleRecovered: true,
    recoveredMissingSurfaceLock: true,
    existingSurfaceFocused: false,
  };
}

function releaseHandoffLock(lock) {
  if (!lock || typeof lock !== "object") {
    return;
  }
  const existing = handoffInFlight.get(lock.key);
  if (!existing || existing.token !== lock.token) {
    return;
  }
  handoffInFlight.delete(lock.key);
}

function isHandoffLockCurrent(lock) {
  if (!lock || typeof lock !== "object") {
    return false;
  }
  const existing = handoffInFlight.get(lock.key);
  return Boolean(existing && existing.token === lock.token);
}

async function sendTabMessage(tabId, payload) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, payload);
    return { ok: true, response };
  } catch (error) {
    return { ok: false, error };
  }
}

async function showFallbackBanner(tabId, kind, message) {
  if (!Number.isInteger(tabId)) {
    return false;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      func: (bannerKind, bannerMessage) => {
        const bannerId = "legalpdf-gmail-intake-banner";
        const existing = document.getElementById(bannerId);
        if (existing) {
          existing.remove();
        }

        const banner = document.createElement("div");
        banner.id = bannerId;
        banner.textContent = bannerMessage;
        banner.style.position = "fixed";
        banner.style.top = "20px";
        banner.style.right = "20px";
        banner.style.zIndex = "2147483647";
        banner.style.maxWidth = "360px";
        banner.style.padding = "12px 16px";
        banner.style.borderRadius = "12px";
        banner.style.boxShadow = "0 10px 32px rgba(0, 0, 0, 0.25)";
        banner.style.font = "500 13px/1.4 Arial, sans-serif";
        banner.style.color = "#101828";
        if (bannerKind === "success") {
          banner.style.background = "#D1FADF";
          banner.style.border = "1px solid #6CE9A6";
        } else if (bannerKind === "info") {
          banner.style.background = "#D9F0FF";
          banner.style.border = "1px solid #84CAFF";
        } else {
          banner.style.background = "#FEE4E2";
          banner.style.border = "1px solid #FDA29B";
        }
        document.documentElement.appendChild(banner);
        window.setTimeout(() => banner.remove(), 4500);
      },
      args: [kind === "success" ? "success" : kind === "info" ? "info" : "error", message],
    });
    return true;
  } catch (_error) {
    return false;
  }
}

async function notifyTab(tabId, kind, message) {
  if (!Number.isInteger(tabId)) {
    return false;
  }

  const result = await sendTabMessage(tabId, {
    type: "gmail-intake-status",
    kind,
    message,
  });
  if (result.ok) {
    return true;
  }
  return await showFallbackBanner(tabId, kind, message);
}

async function ensureContentScriptReady(tabId) {
  const initial = await sendTabMessage(tabId, { type: "gmail-intake-ping" });
  if (initial.ok && initial.response && initial.response.ok === true) {
    return true;
  }

  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"],
    });
  } catch (_error) {
    return false;
  }

  const retry = await sendTabMessage(tabId, { type: "gmail-intake-ping" });
  return retry.ok && retry.response && retry.response.ok === true;
}

async function requestNativePreparation({ requestFocus = true, includeToken = true } = {}) {
  try {
    const response = await chrome.runtime.sendNativeMessage(NATIVE_FOCUS_HOST, {
      action: "prepare_gmail_intake",
      requestFocus,
      includeToken,
    });
    return { ok: true, response };
  } catch (error) {
    return { ok: false, error };
  }
}

function buildPrepareFailureMessage(response) {
  const reason = normalizeToken(response && response.reason);
  const bridgeProbeReason = normalizeToken(response?.bridge_probe_reason);
  const bridgeProbeTimedOut = response?.bridge_probe_timed_out === true;
  switch (reason) {
    case "bridge_disabled":
      return "Gmail bridge is disabled in LegalPDF Translate.";
    case "bridge_token_missing":
      return "Gmail bridge is not configured in LegalPDF Translate.";
    case "invalid_bridge_port":
      return "Gmail bridge port is invalid in LegalPDF Translate.";
    case "runtime_metadata_missing":
    case "bridge_not_running":
      return "LegalPDF Translate is not running the Gmail bridge right now.";
    case "bridge_owner_stale":
      return "LegalPDF Translate found stale Gmail bridge ownership metadata and needs to reclaim the bridge.";
    case "runtime_metadata_invalid":
      return "LegalPDF Translate has invalid Gmail bridge runtime metadata.";
    case "bridge_port_mismatch":
      return "LegalPDF Translate is listening on a different Gmail bridge port.";
    case "bridge_port_owner_unknown":
      return "LegalPDF Translate could not verify the Gmail bridge listener.";
    case "bridge_port_owner_mismatch":
      return "Another process is using the Gmail bridge port configured for LegalPDF Translate.";
    case "bridge_browser_mismatch":
      if (bridgeProbeTimedOut || bridgeProbeReason === "browser_probe_timeout") {
        return "LegalPDF Translate found a browser-owned Gmail bridge, but the browser app did not answer the live-runtime proof in time.";
      }
      return "LegalPDF Translate found a browser-owned Gmail bridge, but the visible browser workspace could not prove it owns the same live runtime.";
    case "split_brain_browser_owner":
      return "The Gmail bridge is owned by a different browser-app process than the visible browser workspace.";
    case "window_not_found":
      return "LegalPDF Translate is running without a visible main window.";
    case "launch_target_missing":
    case "launch_helper_missing":
    case "launch_python_missing":
      return "LegalPDF Translate auto-launch is not available from this checkout.";
    case "launch_runtime_broken":
      return "LegalPDF Translate found this checkout, but its local runtime is broken and could not be started safely.";
    case "launch_command_failed":
      return "LegalPDF Translate could not be started automatically.";
    case "launch_in_progress":
      return "LegalPDF Translate is already starting the browser app for this Gmail handoff.";
    case "browser_server_ready":
      return "LegalPDF Translate started the browser app server and is waiting for the Gmail workspace tab to finish opening.";
    case "launch_timeout":
      return "LegalPDF Translate was started, but the Gmail bridge did not become ready in time.";
    case "unsupported_platform":
      return "Foreground activation is only supported on Windows for this extension.";
    default:
      return "Gmail bridge is not ready in LegalPDF Translate.";
  }
}

function isLaunchStillInProgress(response) {
  return Boolean(response && response.launch_in_progress === true);
}

function buildLaunchInProgressMessage(response) {
  const remainingMs = Number.parseInt(String(response?.launch_lock_ttl_ms ?? 0), 10);
  const browserOpenOwnedBy = normalizeToken(response?.browser_open_owned_by).toLowerCase();
  const waitSeconds = Math.max(
    1,
    Math.ceil((Number.isFinite(remainingMs) && remainingMs > 0 ? remainingMs : LAUNCH_READINESS_WAIT_MS) / 1000),
  );
  if (browserOpenOwnedBy === BROWSER_OPEN_OWNER_EXTENSION) {
    return (
      "LegalPDF Translate already started this Gmail browser handoff. "
      + `Please wait up to ${waitSeconds}s or focus the existing LegalPDF tab instead of clicking again.`
    );
  }
  return (
    "LegalPDF Translate is already starting the browser app for this Gmail handoff. "
    + `Please wait up to ${waitSeconds}s before clicking again; it will reuse the same launch instead of opening another window.`
  );
}

function buildNativeHostAutoLaunchRepairMessage() {
  return (
    "LegalPDF Translate native host is unavailable, so the extension cannot open the app automatically right now. "
    + "Open LegalPDF Translate once to repair the focus helper, then click the extension again."
  );
}

function extractExtensionProvenanceState(response) {
  return {
    syncStatus: normalizeToken(response?.extension_sync_status),
    syncApplied: response?.extension_sync_applied === true,
    reloadRequired: response?.extension_reload_required === true,
    provenanceReason: normalizeToken(response?.extension_provenance_reason),
    syncMessage: normalizeToken(response?.extension_sync_message),
  };
}

function hasExtensionProvenanceIssue(response) {
  const state = extractExtensionProvenanceState(response);
  return (
    state.reloadRequired
    || EXTENSION_PROVENANCE_DRIFT_REASONS.has(state.provenanceReason)
    || state.syncStatus === "sync_failed"
  );
}

function buildExtensionProvenanceNotice(response) {
  const state = extractExtensionProvenanceState(response);
  if (state.reloadRequired) {
    return {
      kind: "info",
      message: (
        "LegalPDF Translate updated the loaded Gmail extension files, but this running extension "
        + "instance is still using stale code. Reload the extension once, then reload Gmail if "
        + "needed, and click the extension again."
      ),
    };
  }
  if (state.syncStatus === "sync_failed") {
    const detail = state.syncMessage !== ""
      ? ` LegalPDF Translate could not sync the loaded extension copy automatically (${state.syncMessage}).`
      : " LegalPDF Translate could not sync the loaded extension copy automatically.";
    return {
      kind: "error",
      message: (
        "This Gmail extension copy is stale for the current LegalPDF Translate app."
        + detail
        + " Reload the extension once after the sync issue is fixed, then reload Gmail if needed, "
        + "and click the extension again."
      ),
    };
  }
  if (EXTENSION_PROVENANCE_DRIFT_REASONS.has(state.provenanceReason)) {
    return {
      kind: "error",
      message: (
        "This Gmail extension copy is stale for the current LegalPDF Translate app. Reload the "
        + "extension once, then reload Gmail if needed, and click the extension again."
      ),
    };
  }
  return null;
}

function isBridgeIntegrityFailureReason(reason) {
  return BRIDGE_INTEGRITY_FAILURE_REASONS.has(normalizeToken(reason));
}

function extractBridgeIntegrityState(payload) {
  const diagnosticsReason = normalizeToken(payload?.diagnostics?.gmail_bridge_sync?.reason);
  const capabilityFlagsBridge = payload?.capability_flags?.gmail_bridge;
  const capabilityReason = normalizeToken(capabilityFlagsBridge?.reason);
  const prepareResponse = (
    capabilityFlagsBridge?.current_mode?.prepare_response
    || payload?.normalized_payload?.extension_lab?.prepare_response
    || {}
  );
  return {
    reason: diagnosticsReason || capabilityReason,
    bridgeProbeReason: normalizeToken(prepareResponse?.bridge_probe_reason),
    bridgeProbeDetail: normalizeToken(prepareResponse?.bridge_probe_detail),
    bridgeProbeTimedOut: prepareResponse?.bridge_probe_timed_out === true,
  };
}

function buildBridgeIntegrityFailureMessage(source) {
  const reason = normalizeToken(source?.integrityFailureReason ?? source?.reason ?? source);
  const bridgeProbeReason = normalizeToken(
    source?.integrityFailureProbeReason ?? source?.bridge_probe_reason,
  );
  const bridgeProbeTimedOut = Boolean(
    source?.integrityFailureTimedOut ?? source?.bridge_probe_timed_out,
  );
  const baseMessage = buildPrepareFailureMessage({
    reason,
    bridge_probe_reason: bridgeProbeReason,
    bridge_probe_timed_out: bridgeProbeTimedOut,
  });
  if (!isBridgeIntegrityFailureReason(reason)) {
    return baseMessage;
  }
  if (bridgeProbeTimedOut || bridgeProbeReason === "browser_probe_timeout") {
    return `${baseMessage} Please wait a few seconds and click the extension again. If it keeps happening, restart the browser app.`;
  }
  return `${baseMessage} Close stale LegalPDF windows or restart the browser app, then click the extension again.`;
}

function messageContextMatches(expectedContext, candidateContext) {
  const expectedMessageId = normalizeToken(expectedContext && expectedContext.message_id);
  const expectedThreadId = normalizeToken(expectedContext && expectedContext.thread_id);
  const candidateMessageId = normalizeToken(
    candidateContext && (candidateContext.message_id ?? candidateContext.messageId),
  );
  const candidateThreadId = normalizeToken(
    candidateContext && (candidateContext.thread_id ?? candidateContext.threadId),
  );
  const comparisons = [];
  if (expectedMessageId !== "" && candidateMessageId !== "") {
    comparisons.push(expectedMessageId === candidateMessageId);
  }
  if (expectedThreadId !== "" && candidateThreadId !== "") {
    comparisons.push(expectedThreadId === candidateThreadId);
  }
  return comparisons.length > 0 && comparisons.every(Boolean);
}

function browserHandoffSessionIdFromPayload(payload) {
  const normalizedPayload = payload?.normalized_payload || {};
  const gmailPayload = normalizedPayload?.gmail || normalizedPayload || {};
  return normalizeToken(
    gmailPayload?.handoff_session_id
    || gmailPayload?.current_handoff_context?.handoff_session_id
    || gmailPayload?.pending_intake_context?.handoff_session_id,
  );
}

function buildFocusNotice(nativeResponse, degradedMode) {
  if (degradedMode) {
    return "App focus helper unavailable; if the app did not come forward, check the taskbar.";
  }

  if (!nativeResponse || typeof nativeResponse !== "object") {
    return "App focus helper returned an invalid response; if the app did not come forward, check the taskbar.";
  }

  if (nativeResponse.ui_owner === "browser_app") {
    return "";
  }

  if (nativeResponse.ok === true && nativeResponse.focused === true) {
    return "";
  }
  if (nativeResponse.ok === true && nativeResponse.flashed === true) {
    return nativeResponse.launched === true
      ? "The app was started and flashed in the taskbar."
      : "The app was flashed in the taskbar.";
  }
  return `App focus helper could not foreground the app (${buildPrepareFailureMessage(nativeResponse)}).`;
}

function parseBrowserWorkspaceIdentity(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return null;
  }
  try {
    const parsed = new URL(targetUrl);
    return {
      origin: parsed.origin,
      pathname: parsed.pathname,
      runtimeMode: normalizeToken(parsed.searchParams.get("mode")).toLowerCase() || "live",
      workspaceId: normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1",
    };
  } catch (_error) {
    return null;
  }
}

function browserWorkspaceRequiresExactSurface(browserUrl) {
  const identity = parseBrowserWorkspaceIdentity(browserUrl);
  return Boolean(identity && STRICT_BROWSER_WORKSPACES.has(identity.workspaceId));
}

function browserWorkspaceIdentityMatches(candidateUrl, targetUrl) {
  const candidate = parseBrowserWorkspaceIdentity(candidateUrl);
  const target = parseBrowserWorkspaceIdentity(targetUrl);
  return Boolean(
    candidate
    && target
    && candidate.origin === target.origin
    && candidate.pathname === target.pathname
    && candidate.runtimeMode === target.runtimeMode
    && candidate.workspaceId === target.workspaceId
  );
}

function urlsMatchForFocus(candidateUrl, targetUrl) {
  try {
    const candidate = new URL(candidateUrl);
    const target = new URL(targetUrl);
    return candidate.origin === target.origin
      && candidate.pathname === target.pathname
      && candidate.search === target.search
      && candidate.hash === target.hash;
  } catch (_error) {
    return false;
  }
}

async function getBrowserWindowState(windowId) {
  if (!Number.isInteger(windowId) || !chrome?.windows?.get) {
    return null;
  }
  try {
    return await chrome.windows.get(windowId);
  } catch (_error) {
    return null;
  }
}

async function ensureBrowserTabVisible(tabLike) {
  const tabId = Number.isInteger(tabLike?.id) ? tabLike.id : Number.isInteger(tabLike?.tabId) ? tabLike.tabId : null;
  const windowId = Number.isInteger(tabLike?.windowId) ? tabLike.windowId : null;
  if (!Number.isInteger(tabId)) {
    return { ok: false, surfaceVisibilityStatus: "not_visible", tabId: null };
  }
  let restored = false;
  const windowState = await getBrowserWindowState(windowId);
  const wasMinimized = normalizeToken(windowState?.state).toLowerCase() === "minimized";
  try {
    await chrome.tabs.update(tabId, { active: true });
    if (Number.isInteger(windowId)) {
      if (wasMinimized) {
        await chrome.windows.update(windowId, { state: "normal", focused: true });
        restored = true;
      } else {
        await chrome.windows.update(windowId, { focused: true });
      }
    }
  } catch (_error) {
    return {
      ok: false,
      surfaceVisibilityStatus: "focus_failed",
      tabId,
    };
  }
  const refreshedWindowState = await getBrowserWindowState(windowId);
  if (Number.isInteger(windowId) && refreshedWindowState && normalizeToken(refreshedWindowState.state).toLowerCase() === "minimized") {
    return {
      ok: false,
      surfaceVisibilityStatus: "not_visible",
      tabId,
    };
  }
  return {
    ok: true,
    surfaceVisibilityStatus: restored ? "restored" : "visible",
    tabId,
  };
}

async function primeBrowserClientHandoffSession(
  tabId,
  handoffSessionId,
  launchSessionId = "",
  schemaVersion = EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION,
) {
  const normalizedHandoffSessionId = normalizeToken(handoffSessionId);
  const normalizedLaunchSessionId = normalizeToken(launchSessionId);
  if (
    !Number.isInteger(tabId)
    || (normalizedHandoffSessionId === "" && normalizedLaunchSessionId === "")
  ) {
    return false;
  }
  try {
    const execution = await withTimeout(
      chrome.scripting.executeScript({
        target: { tabId },
        func: (nextHandoffSessionId, nextLaunchSessionId, nextSchemaVersion) => {
          const marker = window.LEGALPDF_BROWSER_CLIENT_READY;
          if (!marker || typeof marker !== "object") {
            return false;
          }
          const normalizedHandoff = String(nextHandoffSessionId || "").trim();
          const normalizedLaunch = String(nextLaunchSessionId || "").trim();
          if (normalizedHandoff !== "") {
            marker.handoffSessionId = normalizedHandoff;
          }
          if (normalizedLaunch !== "") {
            marker.launchSessionId = normalizedLaunch;
          }
          marker.launchSessionSchemaVersion = Number.parseInt(String(nextSchemaVersion || 0), 10) || 0;
          if (document.body?.dataset) {
            if (normalizedHandoff !== "") {
              document.body.dataset.clientHandoffSession = marker.handoffSessionId || "";
            }
            if (normalizedLaunch !== "") {
              document.body.dataset.clientLaunchSession = marker.launchSessionId || "";
            }
            document.body.dataset.clientLaunchSessionSchemaVersion = String(marker.launchSessionSchemaVersion || 0);
          }
          window.LEGALPDF_BROWSER_CLIENT_READY = marker;
          return true;
        },
        args: [
          normalizedHandoffSessionId,
          normalizedLaunchSessionId,
          normalizeSchemaVersion(schemaVersion) || EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION,
        ],
      }),
      CLIENT_HYDRATION_POLL_MS * 4,
      null,
    );
    return execution !== null;
  } catch (_error) {
    return false;
  }
}

function buildBrowserLaunchSessionDiagnosticsUrl(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return "";
  }
  try {
    const parsed = new URL(targetUrl);
    const runtimeMode = normalizeToken(parsed.searchParams.get("mode")) || "live";
    const workspaceId = normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1";
    return `${parsed.origin}/api/extension/launch-session-diagnostics?mode=${encodeURIComponent(runtimeMode)}&workspace=${encodeURIComponent(workspaceId)}`;
  } catch (_error) {
    return "";
  }
}

async function clearBrowserLaunchState(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return;
  }
  await clearPendingBrowserSurface(targetUrl);
  await clearActiveBrowserLaunchSession(targetUrl);
}

async function reportLaunchSessionDiagnostics(browserUrl, nativeResponse, diagnostics = {}) {
  const endpoint = buildBrowserLaunchSessionDiagnosticsUrl(browserUrl);
  if (endpoint === "") {
    return;
  }
  const launchSessionId = normalizeToken(diagnostics.launchSessionId || nativeResponse?.launch_session_id);
  if (launchSessionId === "") {
    return;
  }
  const payload = {
    launch_session_id: launchSessionId,
    handoff_session_id: normalizeToken(diagnostics.handoffSessionId),
    click_phase: normalizeToken(diagnostics.clickPhase).toLowerCase(),
    click_failure_reason: normalizeToken(diagnostics.clickFailureReason),
    source_gmail_url: normalizeUrl(diagnostics.sourceGmailUrl),
    browser_url: normalizeUrl(browserUrl || nativeResponse?.browser_url),
    tab_resolution_strategy: normalizeToken(diagnostics.tabResolutionStrategy).toLowerCase(),
    workspace_surface_confirmed: diagnostics.workspaceSurfaceConfirmed === true,
    client_hydration_status: normalizeToken(diagnostics.clientHydrationStatus).toLowerCase(),
    surface_candidate_source: normalizeToken(diagnostics.surfaceCandidateSource).toLowerCase(),
    surface_candidate_valid: diagnostics.surfaceCandidateValid === true,
    surface_invalidation_reason: normalizeToken(diagnostics.surfaceInvalidationReason),
    fresh_tab_created_after_invalidation: diagnostics.freshTabCreatedAfterInvalidation === true,
    bridge_context_posted: diagnostics.bridgeContextPosted === true,
    surface_visibility_status: normalizeToken(diagnostics.surfaceVisibilityStatus).toLowerCase(),
    outcome: normalizeToken(diagnostics.outcome).toLowerCase(),
    reason: normalizeToken(diagnostics.reason),
  };
  if (Object.prototype.hasOwnProperty.call(diagnostics, "runtimeStateRootCompatible")) {
    payload.runtime_state_root_compatible = diagnostics.runtimeStateRootCompatible === true;
  }
  if (Object.prototype.hasOwnProperty.call(diagnostics, "expectedRuntimeStateRoot")) {
    payload.expected_runtime_state_root = normalizeToken(diagnostics.expectedRuntimeStateRoot);
  }
  if (Object.prototype.hasOwnProperty.call(diagnostics, "observedRuntimeStateRoot")) {
    payload.observed_runtime_state_root = normalizeToken(diagnostics.observedRuntimeStateRoot);
  }
  if (Number.isInteger(diagnostics.tabId)) {
    payload.tab_id = diagnostics.tabId;
  }
  try {
    await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
  } catch (_error) {
    // Diagnostics must never break Gmail handoff flow.
  }
}

async function recordGmailClickPhase(tabId, nativeResponse, details = {}) {
  const handoffSessionId = normalizeToken(details.handoffSessionId || nativeResponse?.handoff_session_id);
  const launchSessionId = normalizeToken(details.launchSessionId || nativeResponse?.launch_session_id);
  const browserUrl = normalizeUrl(details.browserUrl || nativeResponse?.browser_url);
  const phase = normalizeToken(details.phase).toLowerCase();
  const failureReason = normalizeToken(details.failureReason);
  const sourceGmailUrl = normalizeUrl(details.sourceGmailUrl);
  await rememberGmailClickSession(tabId, {
    sourceGmailUrl,
    browserUrl,
    launchSessionId,
    handoffSessionId,
    phase,
    failureReason,
    bridgeContextPosted: details.bridgeContextPosted === true,
  });
  await reportLaunchSessionDiagnostics(browserUrl, nativeResponse, {
    launchSessionId,
    handoffSessionId,
    clickPhase: phase,
    clickFailureReason: failureReason,
    sourceGmailUrl,
    bridgeContextPosted: details.bridgeContextPosted === true,
    surfaceVisibilityStatus: normalizeToken(details.surfaceVisibilityStatus),
    workspaceSurfaceConfirmed: details.workspaceSurfaceConfirmed === true,
    clientHydrationStatus: normalizeToken(details.clientHydrationStatus),
    tabId: Number.isInteger(details.tabId) ? details.tabId : tabId,
    outcome: normalizeToken(details.outcome),
    reason: normalizeToken(details.reason || failureReason),
  });
}

async function openOrFocusBrowserApp(browserUrl, options = {}) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return false;
  }
  const activeLaunchSession = await getActiveBrowserLaunchSession(targetUrl);
  const preferredWindowId = Number.isInteger(options?.preferredWindowId) ? options.preferredWindowId : null;
  const allowCreate = options?.allowCreate !== false
    && (!activeLaunchSession || activeLaunchSession.owner === BROWSER_OPEN_OWNER_EXTENSION);
  const strictSurface = browserWorkspaceRequiresExactSurface(targetUrl);
  const resolvedSurface = await resolveBrowserAppTab(targetUrl, {
    expectedLaunchSessionId: normalizeToken(options?.launchSessionId || activeLaunchSession?.launchSessionId),
    expectedHandoffSessionId: normalizeToken(options?.handoffSessionId),
    preferredWindowId,
  });
  const resolvedTab = resolvedSurface?.tab || null;
  if (resolvedTab && Number.isInteger(resolvedTab.id)) {
    if (!strictSurface) {
      await chrome.tabs.update(resolvedTab.id, {
        active: true,
        url: targetUrl,
      });
    }
    const visibility = await ensureBrowserTabVisible(resolvedTab);
    if (visibility.ok) {
      if (activeLaunchSession) {
        await clearActiveBrowserLaunchSession(targetUrl);
      }
      return true;
    }
    if (!strictSurface || !allowCreate) {
      return false;
    }
    await clearPendingBrowserSurface(targetUrl);
  }
  if (!allowCreate) {
    return false;
  }
  const createArgs = { url: targetUrl, active: true };
  if (Number.isInteger(preferredWindowId)) {
    createArgs.windowId = preferredWindowId;
  }
  const created = await chrome.tabs.create(createArgs);
  const staleSurfaceInvalidated = normalizeToken(resolvedSurface?.surfaceInvalidationReason) !== "";
  const failedExistingFocus = resolvedTab && Number.isInteger(resolvedTab.id);
  const invalidationReason = failedExistingFocus
    ? "focus_failed"
    : strictSurface
      ? normalizeToken(resolvedSurface?.surfaceInvalidationReason)
      : "";
  await rememberPendingBrowserSurface(targetUrl, created, {
    launchSessionId: normalizeToken(options?.launchSessionId || activeLaunchSession?.launchSessionId),
    handoffSessionId: normalizeToken(options?.handoffSessionId),
    browserOpenOwnedBy: normalizeToken(options?.browserOpenOwnedBy || BROWSER_OPEN_OWNER_EXTENSION).toLowerCase(),
    resolutionStrategy: strictSurface ? "created_exact_tab" : "created_tab",
    surfaceCandidateSource: strictSurface ? "fresh_exact_tab" : "created_tab",
    surfaceCandidateValid: true,
    surfaceInvalidationReason: strictSurface ? invalidationReason : "",
    freshTabCreatedAfterInvalidation: strictSurface && (staleSurfaceInvalidated || failedExistingFocus),
  });
  if (!await ensureBrowserTabVisible(created)) {
    return false;
  }
  if (activeLaunchSession) {
    await clearActiveBrowserLaunchSession(targetUrl);
  }
  return true;
}

async function focusExistingBrowserAppWindow(browserUrl = DEFAULT_BROWSER_APP_URL, options = {}) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return false;
  }
  const activeLaunchSession = await getActiveBrowserLaunchSession(targetUrl);
  const preferredWindowId = Number.isInteger(options?.preferredWindowId) ? options.preferredWindowId : null;
  const resolvedSurface = await resolveBrowserAppTab(targetUrl, {
    expectedLaunchSessionId: normalizeToken(options?.launchSessionId || activeLaunchSession?.launchSessionId),
    expectedHandoffSessionId: normalizeToken(options?.handoffSessionId || activeLaunchSession?.handoffSessionId),
    preferredWindowId,
  });
  const resolvedTab = resolvedSurface?.tab || null;
  if (!resolvedTab || !Number.isInteger(resolvedTab.id)) {
    return false;
  }
  const visibility = await ensureBrowserTabVisible(resolvedTab);
  if (!visibility.ok) {
    return false;
  }
  await rememberPendingBrowserSurface(targetUrl, resolvedTab, {
    launchSessionId: normalizeToken(resolvedSurface?.launchSessionId || options?.launchSessionId || activeLaunchSession?.launchSessionId),
    handoffSessionId: normalizeToken(resolvedSurface?.handoffSessionId || options?.handoffSessionId || activeLaunchSession?.handoffSessionId),
    browserOpenOwnedBy: normalizeToken(resolvedSurface?.browserOpenOwnedBy || activeLaunchSession?.owner),
    resolutionStrategy: normalizeToken(resolvedSurface?.resolutionStrategy || "exact_workspace_match").toLowerCase(),
    surfaceCandidateSource: normalizeToken(resolvedSurface?.surfaceCandidateSource || "queried_exact_tab").toLowerCase(),
    surfaceCandidateValid: resolvedSurface?.surfaceCandidateValid !== false,
    surfaceInvalidationReason: "",
    freshTabCreatedAfterInvalidation: resolvedSurface?.freshTabCreatedAfterInvalidation === true,
  });
  if (activeLaunchSession) {
    await clearActiveBrowserLaunchSession(targetUrl);
  }
  return true;
}

async function waitForLaunchedBrowserAppTab(browserUrl, timeoutMs = COLD_START_TAB_WAIT_MS, options = {}) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return false;
  }
  const activeLaunchSession = await getActiveBrowserLaunchSession(targetUrl);
  if (await focusPendingBrowserSurface(targetUrl, {
    expectedLaunchSessionId: normalizeToken(options?.launchSessionId || activeLaunchSession?.launchSessionId),
    expectedHandoffSessionId: normalizeToken(options?.handoffSessionId || activeLaunchSession?.handoffSessionId),
  })) {
    return true;
  }
  let origin;
  try {
    origin = new URL(targetUrl).origin;
  } catch (_error) {
    return false;
  }
  const activeLaunchWaitMs = activeLaunchSession
    ? Math.max(0, activeLaunchSession.expiresAt - Date.now())
    : 0;
  const deadline = Date.now() + Math.max(0, Number(timeoutMs || 0), activeLaunchWaitMs);
  while (Date.now() <= deadline) {
    const candidates = await chrome.tabs.query({ url: `${origin}/*` });
    const workspaceMatch = candidates.find((tab) => browserWorkspaceIdentityMatches(tab.url, targetUrl));
    if (workspaceMatch && Number.isInteger(workspaceMatch.id)) {
      if (browserWorkspaceRequiresExactSurface(targetUrl)) {
        const validation = await validateStrictBrowserWorkspaceCandidate(targetUrl, workspaceMatch, {
          expectedLaunchSessionId: normalizeToken(options?.launchSessionId || activeLaunchSession?.launchSessionId),
          expectedHandoffSessionId: normalizeToken(options?.handoffSessionId || activeLaunchSession?.handoffSessionId),
          candidateSource: "queried_exact_tab",
        });
        if (!validation.valid) {
          await sleep(COLD_START_TAB_POLL_MS);
          continue;
        }
      }
      await rememberPendingBrowserSurface(targetUrl, workspaceMatch, {
        launchSessionId: normalizeToken(options?.launchSessionId || activeLaunchSession?.launchSessionId),
        handoffSessionId: normalizeToken(options?.handoffSessionId || activeLaunchSession?.handoffSessionId),
        browserOpenOwnedBy: activeLaunchSession?.owner,
        resolutionStrategy: "exact_workspace_match",
        surfaceCandidateSource: "queried_exact_tab",
        surfaceCandidateValid: true,
        surfaceInvalidationReason: "",
        freshTabCreatedAfterInvalidation: false,
      });
      const visibility = await ensureBrowserTabVisible(workspaceMatch);
      if (!visibility.ok) {
        await sleep(COLD_START_TAB_POLL_MS);
        continue;
      }
      if (activeLaunchSession) {
        await clearActiveBrowserLaunchSession(targetUrl);
      }
      return true;
    }
    await sleep(COLD_START_TAB_POLL_MS);
  }
  return false;
}

function shouldWaitForLaunchedBrowserTab({
  nativeResponse = null,
  browserUrl = "",
  launchSessionId = "",
  browserOpenOwnedBy = "",
} = {}) {
  const targetUrl = normalizeUrl(browserUrl || nativeResponse?.browser_url);
  const resolvedBrowserOpenOwner = normalizeToken(
    browserOpenOwnedBy || nativeResponse?.browser_open_owned_by,
  ).toLowerCase() || BROWSER_OPEN_OWNER_EXTENSION;
  const foreignLaunchOwner = resolvedBrowserOpenOwner !== BROWSER_OPEN_OWNER_EXTENSION;
  return Boolean(
    nativeResponse
    && nativeResponse.ui_owner === "browser_app"
    && targetUrl !== ""
    && foreignLaunchOwner
    && (
      nativeResponse.launched === true
      || normalizeToken(launchSessionId) !== ""
    )
  );
}

function buildBrowserWorkspaceBootstrapUrl(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return "";
  }
  try {
    const parsed = new URL(targetUrl);
    const runtimeMode = normalizeToken(parsed.searchParams.get("mode")) || "live";
    const workspaceId = normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1";
    return `${parsed.origin}/api/gmail/bootstrap?mode=${encodeURIComponent(runtimeMode)}&workspace=${encodeURIComponent(workspaceId)}`;
  } catch (_error) {
    return "";
  }
}

function buildBrowserAppBootstrapUrl(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return "";
  }
  try {
    const parsed = new URL(targetUrl);
    const runtimeMode = normalizeToken(parsed.searchParams.get("mode")) || "live";
    const workspaceId = normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1";
    return `${parsed.origin}/api/bootstrap/shell/ready?mode=${encodeURIComponent(runtimeMode)}&workspace=${encodeURIComponent(workspaceId)}`;
  } catch (_error) {
    return "";
  }
}

function defaultBrowserViewForWorkspace(workspaceId) {
  return workspaceId === "gmail-intake" ? "gmail-intake" : "new-job";
}

function parseBrowserClientExpectation(browserUrl) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return {
      runtimeMode: "live",
      workspaceId: "workspace-1",
      activeView: "new-job",
      assetVersion: "",
    };
  }
  try {
    const parsed = new URL(targetUrl);
    const workspaceId = normalizeToken(parsed.searchParams.get("workspace")) || "workspace-1";
    return {
      runtimeMode: normalizeToken(parsed.searchParams.get("mode")) || "live",
      workspaceId,
      activeView: normalizeToken(parsed.hash.replace(/^#/, "")) || defaultBrowserViewForWorkspace(workspaceId),
      assetVersion: "",
    };
  } catch (_error) {
    return {
      runtimeMode: "live",
      workspaceId: "workspace-1",
      activeView: "new-job",
      assetVersion: "",
      };
  }
}

function doesBrowserClientMatchExpectation(clientState, expected) {
  return (
    clientState.available === true
    && clientState.runtimeMode === expected.runtimeMode
    && clientState.workspaceId === expected.workspaceId
    && clientState.activeView === expected.activeView
    && doesBrowserClientAssetVersionMatch(clientState, expected.assetVersion)
  );
}

function buildEmptyBrowserSurfaceResolution({
  launchSessionId = "",
  handoffSessionId = "",
  browserOpenOwnedBy = "",
  surfaceCandidateSource = "no_surface_confirmed",
  surfaceCandidateValid = false,
  surfaceInvalidationReason = "",
  freshTabCreatedAfterInvalidation = false,
  clientState = null,
} = {}) {
  return {
    tab: null,
    resolutionStrategy: "",
    launchSessionId: normalizeToken(launchSessionId),
    handoffSessionId: normalizeToken(handoffSessionId),
    browserOpenOwnedBy: normalizeToken(browserOpenOwnedBy).toLowerCase(),
    surfaceCandidateSource: normalizeToken(surfaceCandidateSource).toLowerCase() || "no_surface_confirmed",
    surfaceCandidateValid: surfaceCandidateValid === true,
    surfaceInvalidationReason: normalizeToken(surfaceInvalidationReason),
    freshTabCreatedAfterInvalidation: freshTabCreatedAfterInvalidation === true,
    clientState,
  };
}

function isFreshPendingSurfaceForActiveSession(pendingRecord, expectedLaunchSessionId) {
  const expected = normalizeToken(expectedLaunchSessionId);
  return Boolean(
    pendingRecord
    && normalizeToken(pendingRecord.resolutionStrategy).toLowerCase() === "created_exact_tab"
    && expected !== ""
    && normalizeToken(pendingRecord.launchSessionId) === expected
  );
}

async function validateStrictBrowserWorkspaceCandidate(
  browserUrl,
  tab,
  {
    expectedLaunchSessionId = "",
    expectedHandoffSessionId = "",
    expectedAssetVersion = "",
    candidateSource = "",
    pendingRecord = null,
    preferredWindowId = null,
  } = {},
) {
  const targetUrl = normalizeUrl(browserUrl);
  if (!tab || !Number.isInteger(tab.id) || !browserWorkspaceIdentityMatches(tab.url, targetUrl)) {
    return {
      valid: false,
      reason: "tab_missing",
      clientState: null,
    };
  }
  if (
    Number.isInteger(preferredWindowId)
    && Number.isInteger(tab.windowId)
    && tab.windowId !== preferredWindowId
  ) {
    return {
      valid: false,
      reason: "window_mismatch",
      clientState: null,
    };
  }

  const normalizedExpectedLaunchSessionId = normalizeToken(expectedLaunchSessionId);
  const normalizedExpectedHandoffSessionId = normalizeToken(expectedHandoffSessionId);
  const rememberedLaunchSessionId = normalizeToken(pendingRecord?.launchSessionId);
  const rememberedHandoffSessionId = normalizeToken(pendingRecord?.handoffSessionId);
  const normalizedCandidateSource = normalizeToken(candidateSource).toLowerCase();
  if (normalizedExpectedLaunchSessionId !== "" && rememberedLaunchSessionId !== "" && rememberedLaunchSessionId !== normalizedExpectedLaunchSessionId) {
    return {
      valid: false,
      reason: "launch_session_mismatch",
      clientState: null,
    };
  }
  if (normalizedExpectedHandoffSessionId !== "" && rememberedHandoffSessionId !== "" && rememberedHandoffSessionId !== normalizedExpectedHandoffSessionId) {
    return {
      valid: false,
      reason: "handoff_session_mismatch",
      clientState: null,
    };
  }
  if (
    normalizedCandidateSource === "fresh_exact_tab"
    && normalizedExpectedLaunchSessionId !== ""
    && rememberedLaunchSessionId === normalizedExpectedLaunchSessionId
    && (
      normalizedExpectedHandoffSessionId === ""
      || rememberedHandoffSessionId === ""
      || rememberedHandoffSessionId === normalizedExpectedHandoffSessionId
    )
  ) {
    return {
      valid: true,
      reason: "",
      clientState: null,
    };
  }

  const clientState = await readBrowserClientHydrationState(tab.id);
  const expectation = {
    ...parseBrowserClientExpectation(targetUrl),
    assetVersion: normalizeToken(expectedAssetVersion),
  };
  if (!doesBrowserClientMatchExpectation(clientState, expectation)) {
    return {
      valid: false,
      reason: clientState.available === true ? "client_state_mismatch" : "client_state_missing",
      clientState,
    };
  }

  if (normalizedExpectedLaunchSessionId === "") {
    return {
      valid: true,
      reason: "",
      clientState,
    };
  }

  const observedLaunchSessionId = normalizeToken(clientState.launchSessionId);
  const observedHandoffSessionId = normalizeToken(clientState.handoffSessionId);
  const requiresCurrentHandoffSession = (
    normalizedExpectedHandoffSessionId !== ""
    && normalizedCandidateSource !== "fresh_exact_tab"
  );
  if (rememberedLaunchSessionId !== "" && rememberedLaunchSessionId === normalizedExpectedLaunchSessionId) {
    if (observedLaunchSessionId !== "" && observedLaunchSessionId !== normalizedExpectedLaunchSessionId) {
      return {
        valid: false,
        reason: "launch_session_mismatch",
        clientState,
      };
    }
    if (requiresCurrentHandoffSession && observedHandoffSessionId !== normalizedExpectedHandoffSessionId) {
      return {
        valid: false,
        reason: observedHandoffSessionId === "" ? "handoff_session_missing" : "handoff_session_mismatch",
        clientState,
      };
    }
    return {
        valid: true,
      reason: "",
      clientState,
    };
  }

  if (observedLaunchSessionId !== normalizedExpectedLaunchSessionId) {
    return {
      valid: false,
      reason: observedLaunchSessionId === "" ? "client_state_missing" : "launch_session_mismatch",
      clientState,
    };
  }
  if (
    requiresCurrentHandoffSession
    && observedHandoffSessionId !== normalizedExpectedHandoffSessionId
  ) {
    return {
      valid: false,
      reason: observedHandoffSessionId === "" ? "handoff_session_missing" : "handoff_session_mismatch",
      clientState,
    };
  }

  return {
    valid: true,
    reason: "",
    clientState,
  };
}

async function resolveBrowserAppTab(browserUrl, options = {}) {
  const targetUrl = normalizeUrl(browserUrl);
  if (targetUrl === "") {
    return buildEmptyBrowserSurfaceResolution();
  }
  await ensurePendingBrowserSurfacesLoaded();
  const activeLaunchSession = await getActiveBrowserLaunchSession(targetUrl);
  const expectedLaunchSessionId = normalizeToken(
    options?.expectedLaunchSessionId
    || options?.launchSessionId
    || activeLaunchSession?.launchSessionId,
  );
  const expectedHandoffSessionId = normalizeToken(options?.expectedHandoffSessionId || options?.handoffSessionId);
  const expectedAssetVersion = normalizeToken(options?.expectedAssetVersion);
  const preferredWindowId = Number.isInteger(options?.preferredWindowId) ? options.preferredWindowId : null;
  let url;
  try {
    url = new URL(targetUrl);
  } catch (_error) {
    return buildEmptyBrowserSurfaceResolution({
      launchSessionId: expectedLaunchSessionId,
      browserOpenOwnedBy: activeLaunchSession?.owner,
    });
  }
  const key = buildPendingBrowserSurfaceKey(targetUrl);
  const strictSurface = browserWorkspaceRequiresExactSurface(targetUrl);
  const candidates = await chrome.tabs.query({ url: `${url.origin}/*` });
  let invalidResolution = buildEmptyBrowserSurfaceResolution({
    launchSessionId: expectedLaunchSessionId,
    handoffSessionId: expectedHandoffSessionId,
    browserOpenOwnedBy: activeLaunchSession?.owner,
  });
  const pending = pendingBrowserSurfaces.get(key);
  if (pending && Number.isInteger(pending.tabId)) {
    const pendingMatch = candidates.find((tab) => tab.id === pending.tabId);
    if (
      pendingMatch
      && (
        !strictSurface
        || browserWorkspaceIdentityMatches(pendingMatch.url, targetUrl)
      )
    ) {
      if (strictSurface) {
        const candidateSource = isFreshPendingSurfaceForActiveSession(pending, expectedLaunchSessionId)
          ? "fresh_exact_tab"
          : "pending_surface";
        const validation = await validateStrictBrowserWorkspaceCandidate(targetUrl, pendingMatch, {
          expectedLaunchSessionId,
          expectedHandoffSessionId,
          expectedAssetVersion,
          candidateSource,
          pendingRecord: pending,
          preferredWindowId,
        });
        if (!validation.valid) {
          pendingBrowserSurfaces.delete(key);
          await persistPendingBrowserSurfaces();
          invalidResolution = {
            ...invalidResolution,
            surfaceCandidateSource: candidateSource,
            surfaceInvalidationReason: validation.reason,
            clientState: validation.clientState,
          };
        } else {
          await rememberPendingBrowserSurface(targetUrl, pendingMatch, {
            launchSessionId: pending.launchSessionId || expectedLaunchSessionId,
            handoffSessionId: pending.handoffSessionId || expectedHandoffSessionId,
            browserOpenOwnedBy: pending.browserOpenOwnedBy || activeLaunchSession?.owner,
            resolutionStrategy: pending.resolutionStrategy || (candidateSource === "fresh_exact_tab" ? "created_exact_tab" : "pending_match"),
            surfaceCandidateSource: candidateSource,
            surfaceCandidateValid: true,
            surfaceInvalidationReason: "",
            freshTabCreatedAfterInvalidation: pending.freshTabCreatedAfterInvalidation === true,
          });
          return {
            tab: pendingMatch,
            resolutionStrategy: pending.resolutionStrategy || (candidateSource === "fresh_exact_tab" ? "created_exact_tab" : "pending_match"),
            launchSessionId: pending.launchSessionId || expectedLaunchSessionId,
            handoffSessionId: pending.handoffSessionId || expectedHandoffSessionId,
            browserOpenOwnedBy: pending.browserOpenOwnedBy || activeLaunchSession?.owner || "",
            surfaceCandidateSource: candidateSource,
            surfaceCandidateValid: true,
            surfaceInvalidationReason: "",
            freshTabCreatedAfterInvalidation: pending.freshTabCreatedAfterInvalidation === true,
            clientState: validation.clientState,
          };
        }
      } else {
        await rememberPendingBrowserSurface(targetUrl, pendingMatch, {
          launchSessionId: pending.launchSessionId,
          handoffSessionId: pending.handoffSessionId || expectedHandoffSessionId,
          browserOpenOwnedBy: pending.browserOpenOwnedBy,
          resolutionStrategy: pending.resolutionStrategy || "pending_match",
          surfaceCandidateSource: pending.surfaceCandidateSource || "pending_surface",
          surfaceCandidateValid: true,
          surfaceInvalidationReason: "",
          freshTabCreatedAfterInvalidation: pending.freshTabCreatedAfterInvalidation === true,
        });
        return {
          tab: pendingMatch,
          resolutionStrategy: pending.resolutionStrategy || "pending_match",
          launchSessionId: pending.launchSessionId,
          handoffSessionId: pending.handoffSessionId || expectedHandoffSessionId,
          browserOpenOwnedBy: pending.browserOpenOwnedBy || "",
          surfaceCandidateSource: pending.surfaceCandidateSource || "pending_surface",
          surfaceCandidateValid: true,
          surfaceInvalidationReason: "",
          freshTabCreatedAfterInvalidation: pending.freshTabCreatedAfterInvalidation === true,
          clientState: null,
        };
      }
    } else {
      pendingBrowserSurfaces.delete(key);
      await persistPendingBrowserSurfaces();
      invalidResolution = {
        ...invalidResolution,
        surfaceCandidateSource: normalizeToken(pending?.surfaceCandidateSource || "pending_surface").toLowerCase(),
        surfaceInvalidationReason: "tab_missing",
      };
    }
  }
  const workspaceMatch = candidates.find((tab) => browserWorkspaceIdentityMatches(tab.url, targetUrl));
  if (workspaceMatch && Number.isInteger(workspaceMatch.id)) {
    if (strictSurface) {
      const validation = await validateStrictBrowserWorkspaceCandidate(targetUrl, workspaceMatch, {
        expectedLaunchSessionId,
        expectedHandoffSessionId,
        expectedAssetVersion,
        candidateSource: "queried_exact_tab",
        preferredWindowId,
      });
      if (!validation.valid) {
        invalidResolution = {
          ...invalidResolution,
          surfaceCandidateSource: "queried_exact_tab",
          surfaceInvalidationReason: validation.reason,
          clientState: validation.clientState,
        };
      } else {
        await rememberPendingBrowserSurface(targetUrl, workspaceMatch, {
          launchSessionId: expectedLaunchSessionId,
          handoffSessionId: expectedHandoffSessionId,
          browserOpenOwnedBy: activeLaunchSession?.owner,
          resolutionStrategy: "exact_workspace_match",
          surfaceCandidateSource: "queried_exact_tab",
          surfaceCandidateValid: true,
          surfaceInvalidationReason: "",
          freshTabCreatedAfterInvalidation: false,
        });
        return {
          tab: workspaceMatch,
          resolutionStrategy: "exact_workspace_match",
          launchSessionId: expectedLaunchSessionId,
          handoffSessionId: expectedHandoffSessionId,
          browserOpenOwnedBy: activeLaunchSession?.owner || "",
          surfaceCandidateSource: "queried_exact_tab",
          surfaceCandidateValid: true,
          surfaceInvalidationReason: "",
          freshTabCreatedAfterInvalidation: false,
          clientState: validation.clientState,
        };
      }
    } else {
      await rememberPendingBrowserSurface(targetUrl, workspaceMatch, {
        launchSessionId: expectedLaunchSessionId,
        handoffSessionId: expectedHandoffSessionId,
        browserOpenOwnedBy: activeLaunchSession?.owner,
        resolutionStrategy: "exact_workspace_match",
        surfaceCandidateSource: "queried_exact_tab",
        surfaceCandidateValid: true,
        surfaceInvalidationReason: "",
        freshTabCreatedAfterInvalidation: false,
      });
      return {
        tab: workspaceMatch,
        resolutionStrategy: "exact_workspace_match",
        launchSessionId: expectedLaunchSessionId,
        handoffSessionId: expectedHandoffSessionId,
        browserOpenOwnedBy: activeLaunchSession?.owner || "",
        surfaceCandidateSource: "queried_exact_tab",
        surfaceCandidateValid: true,
        surfaceInvalidationReason: "",
        freshTabCreatedAfterInvalidation: false,
        clientState: null,
      };
    }
  }
  if (strictSurface) {
    return invalidResolution;
  }
  const existing = candidates.find((tab) => Number.isInteger(tab.id));
  if (existing && Number.isInteger(existing.id)) {
    await rememberPendingBrowserSurface(targetUrl, existing, {
      handoffSessionId: expectedHandoffSessionId,
      resolutionStrategy: "origin_tab_reused",
      surfaceCandidateSource: "origin_tab_reused",
      surfaceCandidateValid: true,
      surfaceInvalidationReason: "",
      freshTabCreatedAfterInvalidation: false,
    });
    return {
      tab: existing,
      resolutionStrategy: "origin_tab_reused",
      launchSessionId: expectedLaunchSessionId,
      handoffSessionId: expectedHandoffSessionId,
      browserOpenOwnedBy: activeLaunchSession?.owner || "",
      surfaceCandidateSource: "origin_tab_reused",
      surfaceCandidateValid: true,
      surfaceInvalidationReason: "",
      freshTabCreatedAfterInvalidation: false,
      clientState: null,
    };
  }
  return invalidResolution;
}

async function readBrowserClientHydrationState(tabId) {
  if (!Number.isInteger(tabId)) {
    return {
      available: false,
      status: "",
      runtimeMode: "",
      workspaceId: "",
      activeView: "",
      gmailHandoffState: "",
      buildSha: "",
      assetVersion: "",
      launchSessionId: "",
      handoffSessionId: "",
      launchSessionSchemaVersion: 0,
      bootstrappedAt: "",
      url: "",
    };
  }
  try {
    const execution = await withTimeout(
      chrome.scripting.executeScript({
        target: { tabId },
        func: () => {
          const marker = window.LEGALPDF_BROWSER_CLIENT_READY || null;
          const dataset = document.body?.dataset || {};
          return {
            marker,
            dataset: {
              clientReady: dataset.clientReady || "",
              clientWorkspace: dataset.clientWorkspace || "",
              clientRuntimeMode: dataset.clientRuntimeMode || "",
              clientActiveView: dataset.clientActiveView || "",
              clientBuildSha: dataset.clientBuildSha || "",
              clientAssetVersion: dataset.clientAssetVersion || "",
              clientLaunchSession: dataset.clientLaunchSession || "",
              clientHandoffSession: dataset.clientHandoffSession || "",
              clientLaunchSessionSchemaVersion: dataset.clientLaunchSessionSchemaVersion || "",
            },
            href: window.location.href,
          };
        },
      }),
      CLIENT_HYDRATION_POLL_MS * 4,
      null,
    );
    if (execution === null) {
      throw new Error("browser_client_hydration_probe_timeout");
    }
    const result = execution?.[0]?.result || {};
    const marker = result.marker || {};
    const dataset = result.dataset || {};
    const status = normalizeToken(marker.status || dataset.clientReady).toLowerCase();
    return {
      available: true,
      status,
      runtimeMode: normalizeToken(marker.runtimeMode || dataset.clientRuntimeMode).toLowerCase(),
      workspaceId: normalizeToken(marker.workspaceId || dataset.clientWorkspace),
      activeView: normalizeToken(marker.activeView || dataset.clientActiveView),
      gmailHandoffState: normalizeToken(marker.gmailHandoffState).toLowerCase(),
      buildSha: normalizeToken(marker.buildSha || dataset.clientBuildSha),
      assetVersion: normalizeToken(marker.assetVersion || dataset.clientAssetVersion),
      launchSessionId: normalizeToken(marker.launchSessionId || dataset.clientLaunchSession),
      handoffSessionId: normalizeToken(marker.handoffSessionId || dataset.clientHandoffSession),
      launchSessionSchemaVersion: normalizeSchemaVersion(
        marker.launchSessionSchemaVersion || dataset.clientLaunchSessionSchemaVersion,
      ),
      bootstrappedAt: normalizeToken(marker.bootstrappedAt),
      reason: normalizeToken(marker.reason),
      message: normalizeToken(marker.message),
      url: normalizeUrl(result.href),
    };
  } catch (_error) {
    return {
      available: false,
      status: "",
      runtimeMode: "",
      workspaceId: "",
      activeView: "",
      gmailHandoffState: "",
      buildSha: "",
      assetVersion: "",
      launchSessionId: "",
      handoffSessionId: "",
      launchSessionSchemaVersion: 0,
      bootstrappedAt: "",
      url: "",
    };
  }
}

function doesBrowserClientAssetVersionMatch(clientState, expectedAssetVersion) {
  const expected = normalizeToken(expectedAssetVersion);
  if (expected === "") {
    return true;
  }
  return normalizeToken(clientState?.assetVersion) === expected;
}

function isBrowserClientReadyForExpectation(clientState, expected) {
  return (
    clientState.available === true
    && clientState.status === "ready"
    && clientState.runtimeMode === expected.runtimeMode
    && clientState.workspaceId === expected.workspaceId
    && clientState.activeView === expected.activeView
    && doesBrowserClientAssetVersionMatch(clientState, expected.assetVersion)
  );
}

function isBrowserClientWarmingForSameTabExpectation(
  clientState,
  expected,
  expectedLaunchSessionId = "",
  expectedHandoffSessionId = "",
  expectedSchemaVersion = EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION,
) {
  return (
    clientState.available === true
    && normalizeToken(clientState.status).toLowerCase() === "warming"
    && clientState.runtimeMode === expected.runtimeMode
    && clientState.workspaceId === expected.workspaceId
    && clientState.activeView === expected.activeView
    && doesBrowserClientAssetVersionMatch(clientState, expected.assetVersion)
    && (
      normalizeToken(expectedLaunchSessionId) === ""
      || normalizeToken(clientState.launchSessionId) === normalizeToken(expectedLaunchSessionId)
    )
    && (
      normalizeToken(expectedHandoffSessionId) === ""
      || normalizeToken(clientState.handoffSessionId) === normalizeToken(expectedHandoffSessionId)
    )
    && normalizeSchemaVersion(clientState.launchSessionSchemaVersion) >= normalizeSchemaVersion(expectedSchemaVersion)
  );
}

async function waitForBrowserClientHydration(
  browserUrl,
  timeoutMs = CLIENT_HYDRATION_WAIT_MS,
  expectedAssetVersion = "",
  expectedLaunchSessionId = "",
  expectedHandoffSessionId = "",
  preferredWindowId = null,
) {
  const expectation = {
    ...parseBrowserClientExpectation(browserUrl),
    assetVersion: normalizeToken(expectedAssetVersion),
  };
  const deadline = Date.now() + Math.max(0, Number(timeoutMs || 0));
  let lastState = {
    available: false,
    status: "",
    runtimeMode: "",
    workspaceId: "",
    activeView: "",
    gmailHandoffState: "",
    buildSha: "",
    assetVersion: "",
    launchSessionId: "",
    launchSessionSchemaVersion: 0,
    bootstrappedAt: "",
    url: "",
  };
  while (Date.now() <= deadline) {
    const surface = await resolveBrowserAppTab(browserUrl, {
      expectedLaunchSessionId,
      expectedHandoffSessionId,
      expectedAssetVersion,
      preferredWindowId,
    });
    const tab = surface?.tab || null;
    if (tab && Number.isInteger(tab.id)) {
      const clientState = await readBrowserClientHydrationState(tab.id);
      lastState = {
        ...clientState,
        tabId: tab.id,
      };
      if (isBrowserClientReadyForExpectation(lastState, expectation)) {
        return {
          ready: true,
          tabId: tab.id,
          expected: expectation,
          clientState: lastState,
        };
      }
      if (lastState.status === "client_boot_failed") {
        return {
          ready: false,
          tabId: tab.id,
          expected: expectation,
          clientState: lastState,
        };
      }
    }
    await sleep(CLIENT_HYDRATION_POLL_MS);
  }
  return {
    ready: false,
    tabId: Number.isInteger(lastState.tabId) ? lastState.tabId : null,
    expected: expectation,
    clientState: lastState,
  };
}

function determineClientHydrationStatus(hydrationResult) {
  const clientState = hydrationResult?.clientState || {};
  const status = normalizeToken(clientState.status).toLowerCase();
  if (status === "ready") {
    return "ready";
  }
  if (status === "warming") {
    return "warming";
  }
  if (status === "client_boot_failed") {
    return "boot_failed";
  }
  if (hydrationResult?.ready) {
    return "ready";
  }
  return "not_found";
}

async function readTabById(tabId) {
  if (!Number.isInteger(tabId)) {
    return null;
  }
  if (typeof chrome?.tabs?.get === "function") {
    try {
      return await chrome.tabs.get(tabId);
    } catch (_error) {
      return null;
    }
  }
  if (typeof chrome?.tabs?.query === "function") {
    try {
      const tabs = await chrome.tabs.query({});
      return tabs.find((tab) => tab.id === tabId) || null;
    } catch (_error) {
      return null;
    }
  }
  return null;
}

async function waitForSameTabRedirectCommit(tabId, browserUrl, timeoutMs = CLIENT_HYDRATION_RELOAD_WAIT_MS) {
  const targetUrl = normalizeUrl(browserUrl);
  const deadline = Date.now() + Math.max(0, Number(timeoutMs || 0));
  let lastTab = await readTabById(tabId);
  while (Date.now() <= deadline) {
    if (lastTab && browserWorkspaceIdentityMatches(lastTab.url, targetUrl)) {
      return {
        ok: true,
        tab: lastTab,
      };
    }
    await sleep(CLIENT_HYDRATION_POLL_MS);
    lastTab = await readTabById(tabId);
  }
  return {
    ok: false,
    tab: lastTab,
  };
}

async function waitForSameTabWorkspaceHydration(
  tabId,
  browserUrl,
  expectedAssetVersion = "",
  expectedLaunchSessionId = "",
  expectedHandoffSessionId = "",
) {
  const expectation = {
    ...parseBrowserClientExpectation(browserUrl),
    assetVersion: normalizeToken(expectedAssetVersion),
  };
  const deadline = Date.now() + Math.max(0, CLIENT_HYDRATION_WAIT_MS + CLIENT_HYDRATION_RELOAD_WAIT_MS);
  const normalizedExpectedLaunchSessionId = normalizeToken(expectedLaunchSessionId);
  const normalizedExpectedHandoffSessionId = normalizeToken(expectedHandoffSessionId);
  let lastState = {
    available: false,
    status: "",
    runtimeMode: "",
    workspaceId: "",
    activeView: "",
    gmailHandoffState: "",
    buildSha: "",
    assetVersion: "",
    launchSessionId: "",
    handoffSessionId: "",
    launchSessionSchemaVersion: 0,
    bootstrappedAt: "",
    url: "",
  };
  while (Date.now() <= deadline) {
    const currentTab = await readTabById(tabId);
    if (!currentTab || !browserWorkspaceIdentityMatches(currentTab.url, browserUrl)) {
      await sleep(CLIENT_HYDRATION_POLL_MS);
      continue;
    }
    lastState = await readBrowserClientHydrationState(tabId);
    if (
      (normalizedExpectedLaunchSessionId !== "" || normalizedExpectedHandoffSessionId !== "")
      && (
        normalizeToken(lastState.launchSessionId) !== normalizedExpectedLaunchSessionId
        || normalizeToken(lastState.handoffSessionId) !== normalizedExpectedHandoffSessionId
        || normalizeSchemaVersion(lastState.launchSessionSchemaVersion) < EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION
      )
    ) {
      const primed = await primeBrowserClientHandoffSession(
        tabId,
        normalizedExpectedHandoffSessionId,
        normalizedExpectedLaunchSessionId,
        EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION,
      );
      if (primed) {
        lastState = await readBrowserClientHydrationState(tabId);
      }
    }
    if (
      isBrowserClientReadyForExpectation(lastState, expectation)
      && normalizeToken(lastState.launchSessionId) === normalizedExpectedLaunchSessionId
      && (
        normalizedExpectedHandoffSessionId === ""
        || normalizeToken(lastState.handoffSessionId) === normalizedExpectedHandoffSessionId
      )
    ) {
      return {
        ready: true,
        tabId,
        expected: expectation,
        clientState: lastState,
      };
    }
    if (
      isBrowserClientWarmingForSameTabExpectation(
        lastState,
        expectation,
        normalizedExpectedLaunchSessionId,
        normalizedExpectedHandoffSessionId,
      )
    ) {
      return {
        ready: true,
        tabId,
        expected: expectation,
        clientState: lastState,
      };
    }
    if (lastState.status === "client_boot_failed") {
      return {
        ready: false,
        tabId,
        expected: expectation,
        clientState: lastState,
      };
    }
    await sleep(CLIENT_HYDRATION_POLL_MS);
  }
  return {
    ready: false,
    tabId,
    expected: expectation,
    clientState: lastState,
  };
}

async function restoreTabToSourceGmail(tabId, sourceGmailUrl) {
  const targetUrl = normalizeUrl(sourceGmailUrl);
  if (!Number.isInteger(tabId) || targetUrl === "") {
    return false;
  }
  try {
    await chrome.tabs.update(tabId, {
      active: true,
      url: targetUrl,
    });
    return true;
  } catch (_error) {
    return false;
  }
}

async function inspectBrowserWorkspaceSurface(
  browserUrl,
  expectedAssetVersion = "",
  expectedLaunchSessionId = "",
  expectedHandoffSessionId = "",
  preferredWindowId = null,
) {
  const targetUrl = normalizeUrl(browserUrl);
  const resolvedSurface = await resolveBrowserAppTab(targetUrl, {
    expectedLaunchSessionId,
    expectedHandoffSessionId,
    expectedAssetVersion,
    preferredWindowId,
  });
  const resolvedTab = resolvedSurface?.tab || null;
  const workspaceSurfaceConfirmed = Boolean(
    resolvedTab
    && Number.isInteger(resolvedTab.id)
    && browserWorkspaceIdentityMatches(resolvedTab.url, targetUrl)
  );
  const visibility = workspaceSurfaceConfirmed
    ? await ensureBrowserTabVisible(resolvedTab)
    : { ok: false, surfaceVisibilityStatus: "not_visible" };
  if (workspaceSurfaceConfirmed && visibility.ok && normalizeToken(expectedHandoffSessionId) !== "") {
    await primeBrowserClientHandoffSession(
      resolvedTab.id,
      expectedHandoffSessionId,
      expectedLaunchSessionId,
      EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION,
    );
  }
  if (!workspaceSurfaceConfirmed) {
    const rejectedHydration = resolvedSurface?.clientState
      ? {
        ready: false,
        tabId: Number.isInteger(resolvedTab?.id) ? resolvedTab.id : null,
        clientState: resolvedSurface.clientState,
      }
      : null;
    return {
      tabId: Number.isInteger(resolvedTab?.id) ? resolvedTab.id : null,
      tabResolutionStrategy: normalizeToken(resolvedSurface?.resolutionStrategy).toLowerCase() || "no_surface_confirmed",
      surfaceCandidateSource: normalizeToken(resolvedSurface?.surfaceCandidateSource).toLowerCase() || "no_surface_confirmed",
      surfaceCandidateValid: resolvedSurface?.surfaceCandidateValid === true,
      surfaceInvalidationReason: normalizeToken(resolvedSurface?.surfaceInvalidationReason),
      freshTabCreatedAfterInvalidation: resolvedSurface?.freshTabCreatedAfterInvalidation === true,
      workspaceSurfaceConfirmed: false,
      surfaceVisibilityStatus: normalizeToken(visibility?.surfaceVisibilityStatus) || "not_visible",
      clientHydrationStatus: rejectedHydration ? determineClientHydrationStatus(rejectedHydration) : "not_found",
      clientHydration: rejectedHydration,
    };
  }
  if (!visibility.ok) {
    return {
      tabId: Number.isInteger(resolvedTab?.id) ? resolvedTab.id : null,
      tabResolutionStrategy: normalizeToken(resolvedSurface?.resolutionStrategy).toLowerCase() || "exact_workspace_match",
      surfaceCandidateSource: normalizeToken(resolvedSurface?.surfaceCandidateSource).toLowerCase() || "queried_exact_tab",
      surfaceCandidateValid: resolvedSurface?.surfaceCandidateValid === true,
      surfaceInvalidationReason: normalizeToken(resolvedSurface?.surfaceInvalidationReason) || normalizeToken(visibility?.surfaceVisibilityStatus),
      freshTabCreatedAfterInvalidation: resolvedSurface?.freshTabCreatedAfterInvalidation === true,
      workspaceSurfaceConfirmed: false,
      surfaceVisibilityStatus: normalizeToken(visibility?.surfaceVisibilityStatus) || "not_visible",
      clientHydrationStatus: "not_found",
      clientHydration: null,
    };
  }
  const clientHydration = await waitForBrowserClientHydration(
    targetUrl,
    CLIENT_HYDRATION_WAIT_MS,
    expectedAssetVersion,
    expectedLaunchSessionId,
    expectedHandoffSessionId,
    preferredWindowId,
  );
  return {
    tabId: Number.isInteger(clientHydration?.tabId) ? clientHydration.tabId : resolvedTab.id,
    tabResolutionStrategy: normalizeToken(resolvedSurface?.resolutionStrategy).toLowerCase() || "exact_workspace_match",
    surfaceCandidateSource: normalizeToken(resolvedSurface?.surfaceCandidateSource).toLowerCase() || "queried_exact_tab",
    surfaceCandidateValid: resolvedSurface?.surfaceCandidateValid === true,
    surfaceInvalidationReason: normalizeToken(resolvedSurface?.surfaceInvalidationReason),
    freshTabCreatedAfterInvalidation: resolvedSurface?.freshTabCreatedAfterInvalidation === true,
    workspaceSurfaceConfirmed: true,
    surfaceVisibilityStatus: normalizeToken(visibility?.surfaceVisibilityStatus) || "visible",
    clientHydrationStatus: determineClientHydrationStatus(clientHydration),
    clientHydration,
  };
}

async function reloadBrowserAppTab(browserUrl) {
  const surface = await resolveBrowserAppTab(browserUrl);
  const tab = surface?.tab || null;
  if (!tab || !Number.isInteger(tab.id)) {
    return {
      ok: false,
      tabId: null,
    };
  }
  await chrome.tabs.reload(tab.id, { bypassCache: true });
  return {
    ok: true,
    tabId: tab.id,
  };
}

async function waitForBrowserWorkspaceState(
  browserUrl,
  expectedContext,
  timeoutMs = WORKSPACE_READY_WAIT_MS,
  expectedRuntimeStateRoot = "",
) {
  const workspaceEndpoint = buildBrowserWorkspaceBootstrapUrl(browserUrl);
  const appBootstrapEndpoint = buildBrowserAppBootstrapUrl(browserUrl);
  if (workspaceEndpoint === "" && appBootstrapEndpoint === "") {
    return {
      ready: false,
      pending: false,
      loaded: false,
      appBootstrapReady: false,
      workspaceRouteReachable: false,
      assetVersion: "",
      launchSessionSchemaVersion: 0,
      launchSessionDiagnosticsCompatible: true,
      runtimeStateRootCompatible: true,
      expectedRuntimeStateRoot: normalizeToken(expectedRuntimeStateRoot),
      observedRuntimeStateRoot: "",
    };
  }
  const deadline = Date.now() + Math.max(0, Number(timeoutMs || 0));
  const normalizedExpectedRuntimeStateRoot = normalizeToken(expectedRuntimeStateRoot);
  let appBootstrapReady = false;
  let workspaceRouteReachable = false;
  let assetVersion = "";
  let observedHandoffSessionId = "";
  let observedRuntimeStateRoot = "";
  let launchSessionSchemaVersion = 0;
  let launchSessionDiagnosticsCompatible = true;
  let runtimeStateRootCompatible = normalizedExpectedRuntimeStateRoot === "";
  let integrityFailureReason = "";
  let integrityFailureProbeReason = "";
  let integrityFailureProbeDetail = "";
  let integrityFailureTimedOut = false;
  while (Date.now() <= deadline) {
    if (appBootstrapEndpoint !== "" && !appBootstrapReady) {
      try {
        const appBootstrapResponse = await fetch(appBootstrapEndpoint, { cache: "no-store" });
        if (appBootstrapResponse.ok) {
          appBootstrapReady = true;
          let appBootstrapPayload = {};
          try {
            appBootstrapPayload = await appBootstrapResponse.json();
          } catch (_error) {
            appBootstrapPayload = {};
          }
          const appIntegrity = extractBridgeIntegrityState(appBootstrapPayload);
          assetVersion = normalizeToken(
            appBootstrapPayload?.normalized_payload?.shell?.asset_version
            || appBootstrapPayload?.normalized_payload?.runtime?.asset_version,
          );
          observedRuntimeStateRoot = normalizeToken(
            appBootstrapPayload?.normalized_payload?.shell?.runtime_state_root
            || appBootstrapPayload?.normalized_payload?.runtime?.runtime_state_root
            || appBootstrapPayload?.normalized_payload?.runtime?.app_data_dir,
          );
          runtimeStateRootCompatible = (
            normalizedExpectedRuntimeStateRoot === ""
            || (
              observedRuntimeStateRoot !== ""
              && observedRuntimeStateRoot === normalizedExpectedRuntimeStateRoot
            )
          );
          launchSessionSchemaVersion = normalizeSchemaVersion(
            appBootstrapPayload?.normalized_payload?.shell?.extension_launch_session_schema_version,
          );
          launchSessionDiagnosticsCompatible = (
            launchSessionSchemaVersion >= EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION
            && runtimeStateRootCompatible
          );
          if (!runtimeStateRootCompatible) {
            return {
              ready: false,
              pending: false,
              loaded: false,
              loadFailed: false,
              loadFailureMessage: "",
              warming: false,
              pendingStatus: "",
              integrityFailureReason,
              integrityFailureProbeReason,
              integrityFailureProbeDetail,
              integrityFailureTimedOut,
              appBootstrapReady,
              workspaceRouteReachable,
              assetVersion,
              handoffSessionId: observedHandoffSessionId,
              launchSessionSchemaVersion,
              launchSessionDiagnosticsCompatible,
              runtimeStateRootCompatible,
              expectedRuntimeStateRoot: normalizedExpectedRuntimeStateRoot,
              observedRuntimeStateRoot,
            };
          }
          const appIntegrityReason = appIntegrity.reason;
          if (isBridgeIntegrityFailureReason(appIntegrityReason)) {
            return {
              ready: false,
              pending: false,
              loaded: false,
              loadFailed: false,
              loadFailureMessage: "",
              warming: false,
              pendingStatus: "",
              integrityFailureReason: appIntegrityReason,
              integrityFailureProbeReason: appIntegrity.bridgeProbeReason,
              integrityFailureProbeDetail: appIntegrity.bridgeProbeDetail,
              integrityFailureTimedOut: appIntegrity.bridgeProbeTimedOut,
              appBootstrapReady,
              workspaceRouteReachable,
              assetVersion,
              launchSessionSchemaVersion,
              launchSessionDiagnosticsCompatible,
              runtimeStateRootCompatible,
              expectedRuntimeStateRoot: normalizedExpectedRuntimeStateRoot,
              observedRuntimeStateRoot,
            };
          }
        }
      } catch (_error) {
        // The browser shell can still be warming; keep polling briefly.
      }
    }
    try {
      const response = await fetch(workspaceEndpoint, { cache: "no-store" });
      if (response.ok) {
        workspaceRouteReachable = true;
        let payload = {};
        try {
          payload = await response.json();
        } catch (_error) {
          payload = {};
        }
        const gmailPayload = payload?.normalized_payload || {};
        const integrityState = extractBridgeIntegrityState(payload);
        const integrityReason = integrityState.reason;
        const pendingContext = gmailPayload.pending_intake_context || {};
        observedHandoffSessionId = browserHandoffSessionIdFromPayload(payload);
        const expectedHandoffSessionId = normalizeToken(expectedContext?.handoff_session_id);
        const handoffMatches = expectedHandoffSessionId === "" || observedHandoffSessionId === expectedHandoffSessionId;
        const pendingStatus = normalizeToken(gmailPayload.pending_status).toLowerCase();
        const pendingReviewOpen = gmailPayload.pending_review_open === true;
        const pending = (
          messageContextMatches(expectedContext, pendingContext)
          && handoffMatches
          && pendingReviewOpen
          && WORKSPACE_PENDING_STATUSES.has(pendingStatus)
        );
        const loadResult = gmailPayload.load_result || {};
        const loadMatches = messageContextMatches(expectedContext, loadResult.intake_context || {});
        const loaded = loadMatches && handoffMatches && loadResult.ok === true;
        const loadFailed = loadMatches && handoffMatches && loadResult.ok === false;
        const loadFailureMessage = (
          loadFailed
            ? normalizeToken(loadResult.status_message) || "LegalPDF Translate could not load the exact Gmail message."
            : ""
        );
        const warming = pending;
        if (isBridgeIntegrityFailureReason(integrityReason)) {
          return {
            ready: false,
            pending,
            loaded,
            loadFailed,
            loadFailureMessage,
            warming: false,
            pendingStatus,
            integrityFailureReason: integrityReason,
            integrityFailureProbeReason: integrityState.bridgeProbeReason,
            integrityFailureProbeDetail: integrityState.bridgeProbeDetail,
            integrityFailureTimedOut: integrityState.bridgeProbeTimedOut,
            appBootstrapReady,
              workspaceRouteReachable,
              assetVersion,
              handoffSessionId: observedHandoffSessionId,
              launchSessionSchemaVersion,
              launchSessionDiagnosticsCompatible,
              runtimeStateRootCompatible,
              expectedRuntimeStateRoot: normalizedExpectedRuntimeStateRoot,
              observedRuntimeStateRoot,
            };
        }
        if (loaded) {
          return {
            ready: true,
            pending,
            loaded,
            loadFailed,
            loadFailureMessage,
            warming,
            pendingStatus,
            integrityFailureReason,
            integrityFailureProbeReason: integrityState.bridgeProbeReason,
            integrityFailureProbeDetail: integrityState.bridgeProbeDetail,
            integrityFailureTimedOut: integrityState.bridgeProbeTimedOut,
            appBootstrapReady,
            workspaceRouteReachable,
            assetVersion,
            handoffSessionId: observedHandoffSessionId,
            launchSessionSchemaVersion,
            launchSessionDiagnosticsCompatible,
            runtimeStateRootCompatible,
            expectedRuntimeStateRoot: normalizedExpectedRuntimeStateRoot,
            observedRuntimeStateRoot,
          };
        }
        if (warming) {
          return {
            ready: true,
            pending,
            loaded,
            loadFailed,
            loadFailureMessage,
            warming,
            pendingStatus,
            integrityFailureReason,
            integrityFailureProbeReason: integrityState.bridgeProbeReason,
            integrityFailureProbeDetail: integrityState.bridgeProbeDetail,
            integrityFailureTimedOut: integrityState.bridgeProbeTimedOut,
            appBootstrapReady,
            workspaceRouteReachable,
            assetVersion,
            handoffSessionId: observedHandoffSessionId,
            launchSessionSchemaVersion,
            launchSessionDiagnosticsCompatible,
            runtimeStateRootCompatible,
            expectedRuntimeStateRoot: normalizedExpectedRuntimeStateRoot,
            observedRuntimeStateRoot,
          };
        }
        if (loadFailed) {
          return {
            ready: false,
            pending,
            loaded,
            loadFailed,
            loadFailureMessage,
            warming: false,
            pendingStatus,
            integrityFailureReason,
            integrityFailureProbeReason: integrityState.bridgeProbeReason,
            integrityFailureProbeDetail: integrityState.bridgeProbeDetail,
            integrityFailureTimedOut: integrityState.bridgeProbeTimedOut,
            appBootstrapReady,
            workspaceRouteReachable,
            assetVersion,
            handoffSessionId: observedHandoffSessionId,
            launchSessionSchemaVersion,
            launchSessionDiagnosticsCompatible,
            runtimeStateRootCompatible,
            expectedRuntimeStateRoot: normalizedExpectedRuntimeStateRoot,
            observedRuntimeStateRoot,
          };
        }
      }
    } catch (_error) {
      // The browser app can still be warming the route; keep polling briefly.
    }
    await sleep(WORKSPACE_READY_POLL_MS);
  }
  return {
    ready: false,
    pending: false,
    loaded: false,
    loadFailed: false,
    loadFailureMessage: "",
    warming: false,
    pendingStatus: "",
    integrityFailureReason,
    integrityFailureProbeReason,
    integrityFailureProbeDetail,
    integrityFailureTimedOut,
    appBootstrapReady,
    workspaceRouteReachable,
    assetVersion,
    handoffSessionId: observedHandoffSessionId,
    launchSessionSchemaVersion,
    launchSessionDiagnosticsCompatible,
    runtimeStateRootCompatible,
    expectedRuntimeStateRoot: normalizedExpectedRuntimeStateRoot,
    observedRuntimeStateRoot,
  };
}

function buildWorkspaceWarmupMessage({ baseMessage, focusNotice, resolvedBrowserOpen }) {
  const parts = [];
  if (baseMessage !== "") {
    parts.push(baseMessage);
  }
  parts.push("LegalPDF Translate received the Gmail handoff and is still loading the exact Gmail message.");
  parts.push("Please wait a few seconds, then click the extension again only if it stays stuck.");
  if (focusNotice !== "") {
    parts.push(focusNotice);
  } else if (!resolvedBrowserOpen) {
    parts.push("The browser app may still need manual focus.");
  }
  return parts.join(" ");
}

function buildWorkspaceNoHandoffMessage({ resolvedBrowserOpen, focusNotice }) {
  const parts = [];
  if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but no exact Gmail handoff reached the browser workspace.");
  } else {
    parts.push("LegalPDF Translate did not confirm an exact Gmail handoff in the browser workspace.");
  }
  parts.push("Please click the extension again.");
  if (focusNotice !== "") {
    parts.push(focusNotice);
  } else if (!resolvedBrowserOpen) {
    parts.push("The browser app may still need manual focus.");
  }
  return parts.join(" ");
}

function buildRuntimeStateRootMismatchMessage({
  expectedRuntimeStateRoot,
  observedRuntimeStateRoot,
}) {
  const parts = [
    "LegalPDF Translate detected mismatched Gmail runtime state between the native host and the browser app.",
  ];
  if (expectedRuntimeStateRoot !== "") {
    parts.push(`Expected state root: ${expectedRuntimeStateRoot}.`);
  }
  if (observedRuntimeStateRoot !== "") {
    parts.push(`Browser app state root: ${observedRuntimeStateRoot}.`);
  }
  parts.push("Reload the extension once, then click the Gmail message again.");
  return parts.join(" ");
}

function buildWorkspaceFailureMessage({ resolvedBrowserOpen, focusNotice }) {
  const parts = [];
  if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but the Gmail review surface did not become ready.");
    parts.push("Please focus the LegalPDF window and click the extension again.");
  } else {
    parts.push("LegalPDF Translate did not finish launching into the Gmail review surface.");
    parts.push("Please click the extension again.");
  }
  if (focusNotice !== "") {
    parts.push(focusNotice);
  } else if (!resolvedBrowserOpen) {
    parts.push("The browser app may still need manual focus.");
  }
  return parts.join(" ");
}

function buildWorkspaceSurfaceConfirmationFailureMessage({
  resolvedBrowserOpen,
  focusNotice,
  hydrationStatus,
  hydrationResult,
  expectedAssetVersion = "",
  launchSessionDiagnosticsCompatible = true,
}) {
  const parts = [];
  const clientState = hydrationResult?.clientState || {};
  const expectedVersion = normalizeToken(expectedAssetVersion);
  const observedVersion = normalizeToken(clientState.assetVersion);
  const assetMismatch = expectedVersion !== "" && observedVersion !== "" && observedVersion !== expectedVersion;
  if (assetMismatch) {
    if (resolvedBrowserOpen) {
      parts.push("LegalPDF Translate opened, but the Gmail workspace tab is still running stale browser assets.");
    } else {
      parts.push("LegalPDF Translate could not confirm that the Gmail workspace tab picked up the current browser assets.");
    }
    parts.push(`Expected asset version: ${expectedVersion}.`);
    parts.push(`Tab asset version: ${observedVersion}.`);
  } else if (hydrationStatus === "boot_failed") {
    if (resolvedBrowserOpen) {
      parts.push("LegalPDF Translate opened, but the Gmail workspace tab failed to hydrate the review UI.");
    } else {
      parts.push("LegalPDF Translate could not confirm that the Gmail workspace tab hydrated the review UI.");
    }
    if (normalizeToken(clientState.message) !== "") {
      parts.push(normalizeToken(clientState.message));
    }
  } else if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but the exact Gmail workspace tab was not confirmed.");
  } else {
    parts.push("LegalPDF Translate did not confirm that the Gmail workspace tab opened correctly.");
  }
  if (!launchSessionDiagnosticsCompatible) {
    parts.push("The browser app is still running an older Gmail handoff schema than the extension expects.");
    parts.push("Reload or reopen LegalPDF Translate so the browser app and extension come from the same revision, then click the extension again.");
  }
  parts.push("Please focus the LegalPDF tab and click the extension again.");
  if (focusNotice !== "") {
    parts.push(focusNotice);
  } else if (!resolvedBrowserOpen) {
    parts.push("The browser app may still need manual focus.");
  }
  return parts.join(" ");
}

function buildClientShellNotHydratedMessage({ resolvedBrowserOpen, focusNotice, clientState }) {
  const parts = [];
  if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but the browser tab stayed on the plain shell instead of hydrating the Gmail review UI.");
  } else {
    parts.push("LegalPDF Translate could not confirm that the browser tab hydrated the Gmail review UI.");
  }
  parts.push("The extension reloaded the localhost tab once automatically, but the page still did not finish loading.");
  if (clientState?.status === "client_boot_failed" && clientState?.message) {
    parts.push(clientState.message);
  } else {
    parts.push("Refresh the LegalPDF tab once manually if it is still open. If this keeps happening, restart the browser app and click the extension again.");
  }
  if (focusNotice !== "") {
    parts.push(focusNotice);
  }
  return parts.join(" ");
}

function buildStaleBrowserAssetsMessage({
  resolvedBrowserOpen,
  focusNotice,
  clientState,
  expectedAssetVersion,
}) {
  const parts = [];
  if (resolvedBrowserOpen) {
    parts.push("LegalPDF Translate opened, but the browser tab is still running stale browser assets.");
  } else {
    parts.push("LegalPDF Translate could not confirm that the browser tab picked up the current browser assets.");
  }
  parts.push("The extension reloaded the localhost tab once automatically, but the tab still reported a different asset version than the live app expects.");
  if (expectedAssetVersion) {
    parts.push(`Expected asset version: ${expectedAssetVersion}.`);
  }
  if (clientState?.assetVersion) {
    parts.push(`Tab asset version: ${clientState.assetVersion}.`);
  }
  if (clientState?.message) {
    parts.push(clientState.message);
  } else {
    parts.push("Reload the LegalPDF tab once manually if it is still open. If this keeps happening, restart the browser app and click the extension again.");
  }
  if (focusNotice !== "") {
    parts.push(focusNotice);
  }
  return parts.join(" ");
}

async function resolveBridgeConfigForClick() {
  const nativePreparation = await requestNativePreparation();
  if (nativePreparation.ok) {
    const response = nativePreparation.response;
    const responseReason = normalizeToken(response && response.reason);
    const extensionProvenanceNotice = hasExtensionProvenanceIssue(response)
      ? buildExtensionProvenanceNotice(response)
      : null;
    const bridgePort = normalizePort(response && response.bridgePort);
    const bridgeToken = normalizeToken(response && response.bridgeToken);
    if (response && response.ok === true && bridgeToken !== "") {
      await setStoredBridgeConfig({ bridgePort, bridgeToken });
      if (extensionProvenanceNotice && !isBridgeIntegrityFailureReason(responseReason)) {
        return {
          ok: false,
          degradedMode: false,
          nativeResponse: response,
          messageKind: extensionProvenanceNotice.kind,
          message: extensionProvenanceNotice.message,
        };
      }
      return {
        ok: true,
        degradedMode: false,
        nativeResponse: response,
        config: { bridgePort, bridgeToken },
      };
    }
    if (isLaunchStillInProgress(response)) {
      return {
        ok: false,
        degradedMode: false,
        nativeResponse: response,
        launchInProgress: true,
        messageKind: "info",
        message: buildLaunchInProgressMessage(response),
      };
    }
    if (extensionProvenanceNotice && !isBridgeIntegrityFailureReason(responseReason)) {
      return {
        ok: false,
        degradedMode: false,
        nativeResponse: response,
        messageKind: extensionProvenanceNotice.kind,
        message: extensionProvenanceNotice.message,
      };
    }
    return {
      ok: false,
      degradedMode: false,
      nativeResponse: response,
      messageKind: "error",
      message: buildPrepareFailureMessage(response),
    };
  }

  const storedConfig = await getStoredBridgeConfig();
  if (storedConfig.bridgeToken !== "") {
    try {
      const probeResponse = await fetch(buildBridgeEndpoint(storedConfig), {
        method: "GET",
      });
      if (probeResponse && typeof probeResponse.status === "number") {
        return {
          ok: true,
          degradedMode: true,
          nativeResponse: null,
          config: storedConfig,
        };
      }
    } catch (_error) {
      // The native host is unavailable and the bridge is not already live.
    }
  }

  if (storedConfig.bridgeToken !== "") {
    return {
      ok: false,
      degradedMode: true,
      nativeResponse: null,
      messageKind: "error",
      message: buildNativeHostAutoLaunchRepairMessage(),
    };
  }

  return {
    ok: false,
    degradedMode: true,
    nativeResponse: null,
    messageKind: "error",
    message: "LegalPDF Translate native host is unavailable. Reload the extension or open the options page.",
  };
}

async function waitForPreparedBridgeConfigForClick() {
  const deadline = Date.now() + LAUNCH_READINESS_WAIT_MS;
  let lastResult = null;
  while (Date.now() <= deadline) {
    const result = await resolveBridgeConfigForClick();
    lastResult = result;
    if (result.ok) {
      return result;
    }
    if (!result.launchInProgress) {
      return result;
    }
    await sleep(COLD_START_TAB_POLL_MS);
  }
  return lastResult || {
    ok: false,
    degradedMode: false,
    nativeResponse: null,
    messageKind: "error",
    message: "LegalPDF Translate did not finish preparing the Gmail bridge in time.",
  };
}

async function settleBrowserAppHandoff(browserUrl, browserAppOpened, waitForLaunchedTab, options = {}) {
  let resolved = Boolean(browserAppOpened);
  const targetUrl = normalizeUrl(browserUrl);
  const activeLaunchSession = targetUrl === "" ? null : await getActiveBrowserLaunchSession(targetUrl);
  const expectedLaunchSessionId = normalizeToken(options?.launchSessionId || activeLaunchSession?.launchSessionId);
  const expectedHandoffSessionId = normalizeToken(options?.handoffSessionId || activeLaunchSession?.handoffSessionId);
  if (
    !resolved
    && targetUrl !== ""
    && (waitForLaunchedTab || (activeLaunchSession && activeLaunchSession.owner !== BROWSER_OPEN_OWNER_EXTENSION))
  ) {
    resolved = await waitForLaunchedBrowserAppTab(
      targetUrl,
      activeLaunchSession
        ? Math.max(COLD_START_TAB_WAIT_MS, activeLaunchSession.expiresAt - Date.now())
        : COLD_START_TAB_WAIT_MS,
      {
        launchSessionId: expectedLaunchSessionId,
        handoffSessionId: expectedHandoffSessionId,
      },
    );
  }
  if (!resolved && targetUrl !== "") {
    resolved = await focusExistingBrowserAppWindow(targetUrl, {
      launchSessionId: expectedLaunchSessionId,
      handoffSessionId: expectedHandoffSessionId,
    });
  }
  return resolved;
}

async function confirmBrowserWorkspaceSurfaceBeforeBridgePost(
  tabId,
  context,
  nativeResponse,
  focusNotice,
  browserAppOpened = false,
  browserUrl = "",
  waitForLaunchedTab = false,
  preferredWindowId = null,
) {
  const targetUrl = normalizeUrl(browserUrl);
  if (!nativeResponse || nativeResponse.ui_owner !== "browser_app" || targetUrl === "") {
    return {
      ok: true,
      resolvedBrowserOpen: Boolean(browserAppOpened),
      surfaceState: null,
    };
  }
  const launchSessionId = normalizeToken(nativeResponse?.launch_session_id);
  const handoffSessionId = normalizeToken(context?.handoff_session_id);
  const resolvedBrowserOpen = await settleBrowserAppHandoff(
    targetUrl,
    browserAppOpened,
    waitForLaunchedTab,
    {
      launchSessionId,
      handoffSessionId,
    },
  );
  const surfaceState = await inspectBrowserWorkspaceSurface(
    targetUrl,
    "",
    launchSessionId,
    handoffSessionId,
    preferredWindowId,
  );
  const clientHydrationStatus = normalizeToken(surfaceState?.clientHydrationStatus).toLowerCase() || "not_found";
  const workspaceSurfaceConfirmed = surfaceState?.workspaceSurfaceConfirmed === true;
  const hydratedSurfaceConfirmed = workspaceSurfaceConfirmed
    && (clientHydrationStatus === "ready" || clientHydrationStatus === "warming");
  if (hydratedSurfaceConfirmed) {
    return {
      ok: true,
      resolvedBrowserOpen,
      surfaceState,
    };
  }

  await clearBrowserLaunchState(targetUrl);
  await reportLaunchSessionDiagnostics(targetUrl, nativeResponse, {
    launchSessionId,
    handoffSessionId,
    tabResolutionStrategy: surfaceState?.tabResolutionStrategy,
    workspaceSurfaceConfirmed,
    clientHydrationStatus,
    surfaceCandidateSource: surfaceState?.surfaceCandidateSource,
    surfaceCandidateValid: surfaceState?.surfaceCandidateValid === true,
    surfaceInvalidationReason: surfaceState?.surfaceInvalidationReason,
    freshTabCreatedAfterInvalidation: surfaceState?.freshTabCreatedAfterInvalidation === true,
    bridgeContextPosted: false,
    surfaceVisibilityStatus: normalizeToken(surfaceState?.surfaceVisibilityStatus),
    tabId: surfaceState?.tabId,
    outcome: "workspace_surface_unconfirmed",
    reason: "pre_bridge_surface_unconfirmed",
  });
  await notifyTab(
    tabId,
    "error",
    buildWorkspaceSurfaceConfirmationFailureMessage({
      resolvedBrowserOpen,
      focusNotice,
      hydrationStatus: clientHydrationStatus,
      hydrationResult: surfaceState?.clientHydration || null,
      expectedAssetVersion: "",
      launchSessionDiagnosticsCompatible: true,
    }),
  );
  return {
    ok: false,
    resolvedBrowserOpen,
    surfaceState,
  };
}

async function postContext(
  tabId,
  context,
  config,
  nativeResponse,
  focusNotice,
  browserAppOpened = false,
  browserUrl = "",
  waitForLaunchedTab = false,
  preferredWindowId = null,
) {
  const endpoint = buildBridgeEndpoint(config);
  let response;
  try {
    response = await withTimeout(
      fetch(endpoint, {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${config.bridgeToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message_id: context.message_id,
          thread_id: context.thread_id,
          subject: context.subject,
          account_email: context.account_email ?? undefined,
          handoff_session_id: context.handoff_session_id ?? undefined,
          source_gmail_url: context.source_gmail_url ?? undefined,
        }),
      }),
      WORKSPACE_READY_WAIT_MS,
      null,
    );
    if (response === null) {
      throw new Error("bridge_post_timeout");
    }
  } catch (_error) {
    await notifyTab(tabId, "error", `LegalPDF Translate is not listening on ${endpoint}.`);
    return { holdLock: false, outcome: "bridge_unreachable" };
  }

  let payload = {};
  try {
    payload = await response.json();
  } catch (_error) {
    payload = {};
  }

  if (!response.ok) {
    const message =
      typeof payload.message === "string" && payload.message.trim() !== ""
        ? payload.message.trim()
        : `LegalPDF Translate rejected the request (${response.status}).`;
    await notifyTab(tabId, "error", message);
    return { holdLock: false, outcome: "bridge_rejected" };
  }

  await recordGmailClickPhase(tabId, nativeResponse, {
    phase: GMAIL_CLICK_PHASE_BRIDGE_CONTEXT_POSTED,
    sourceGmailUrl: normalizeUrl(context?.source_gmail_url),
    browserUrl,
    launchSessionId: normalizeToken(nativeResponse?.launch_session_id),
    handoffSessionId: normalizeToken(context?.handoff_session_id || nativeResponse?.handoff_session_id),
    bridgeContextPosted: true,
    surfaceVisibilityStatus: browserAppOpened ? "visible" : "",
    workspaceSurfaceConfirmed: browserAppOpened === true,
    tabId,
    outcome: "bridge_accepted",
    reason: "bridge_accepted",
  });

  const resolvedBrowserOpen = await settleBrowserAppHandoff(browserUrl, browserAppOpened, waitForLaunchedTab);
  const workspaceState = await waitForBrowserWorkspaceState(
    browserUrl,
    context,
    waitForLaunchedTab ? COLD_START_WORKSPACE_READY_WAIT_MS : WORKSPACE_READY_WAIT_MS,
    normalizeToken(nativeResponse?.runtime_state_root),
  );
  if (workspaceState.runtimeStateRootCompatible === false) {
    await clearBrowserLaunchState(browserUrl);
    await reportLaunchSessionDiagnostics(browserUrl, nativeResponse, {
      launchSessionId: normalizeToken(nativeResponse?.launch_session_id),
      handoffSessionId: normalizeToken(context?.handoff_session_id),
      runtimeStateRootCompatible: false,
      expectedRuntimeStateRoot: normalizeToken(workspaceState.expectedRuntimeStateRoot),
      observedRuntimeStateRoot: normalizeToken(workspaceState.observedRuntimeStateRoot),
      bridgeContextPosted: true,
      outcome: "runtime_state_root_mismatch",
      reason: "runtime_state_root_mismatch",
    });
    await notifyTab(
      tabId,
      "error",
      buildRuntimeStateRootMismatchMessage({
        expectedRuntimeStateRoot: normalizeToken(workspaceState.expectedRuntimeStateRoot),
        observedRuntimeStateRoot: normalizeToken(workspaceState.observedRuntimeStateRoot),
      }),
    );
    return {
      holdLock: false,
      outcome: "runtime_state_root_mismatch",
      runtimeStateRootCompatible: false,
      expectedRuntimeStateRoot: normalizeToken(workspaceState.expectedRuntimeStateRoot),
      observedRuntimeStateRoot: normalizeToken(workspaceState.observedRuntimeStateRoot),
    };
  }
  const surfaceState = nativeResponse && nativeResponse.ui_owner === "browser_app"
    ? await inspectBrowserWorkspaceSurface(
      browserUrl,
      workspaceState.assetVersion,
      normalizeToken(nativeResponse?.launch_session_id),
      normalizeToken(context?.handoff_session_id),
      preferredWindowId,
    )
    : null;
  const clientHydrationStatus = normalizeToken(surfaceState?.clientHydrationStatus).toLowerCase() || "not_found";
  const exactWorkspaceSurfaceConfirmed = surfaceState?.workspaceSurfaceConfirmed === true;
  const clientHydrationResult = surfaceState?.clientHydration || null;
  const reportBrowserOutcome = async (outcome, reason = "") => {
    if (!surfaceState) {
      return;
    }
    await reportLaunchSessionDiagnostics(browserUrl, nativeResponse, {
      launchSessionId: normalizeToken(nativeResponse?.launch_session_id),
      handoffSessionId: normalizeToken(context?.handoff_session_id),
      sourceGmailUrl: normalizeUrl(context?.source_gmail_url),
      tabResolutionStrategy: surfaceState.tabResolutionStrategy,
      workspaceSurfaceConfirmed: surfaceState.workspaceSurfaceConfirmed,
      clientHydrationStatus,
      surfaceCandidateSource: surfaceState.surfaceCandidateSource,
      surfaceCandidateValid: surfaceState.surfaceCandidateValid,
      surfaceInvalidationReason: surfaceState.surfaceInvalidationReason,
      freshTabCreatedAfterInvalidation: surfaceState.freshTabCreatedAfterInvalidation,
      bridgeContextPosted: true,
      surfaceVisibilityStatus: normalizeToken(surfaceState.surfaceVisibilityStatus),
      runtimeStateRootCompatible: workspaceState.runtimeStateRootCompatible !== false,
      expectedRuntimeStateRoot: normalizeToken(workspaceState.expectedRuntimeStateRoot),
      observedRuntimeStateRoot: normalizeToken(workspaceState.observedRuntimeStateRoot),
      tabId: surfaceState.tabId,
      outcome,
      reason,
    });
  };
  const includeRuntimeStateRootCompatibility = browserAppOpened === true;
  const withRuntimeStateRootCompatibility = (result) => (
    includeRuntimeStateRootCompatibility
      ? {
        ...result,
        runtimeStateRootCompatible: workspaceState.runtimeStateRootCompatible !== false,
        expectedRuntimeStateRoot: normalizeToken(workspaceState.expectedRuntimeStateRoot),
        observedRuntimeStateRoot: normalizeToken(workspaceState.observedRuntimeStateRoot),
      }
      : result
  );
  const baseMessage =
    typeof payload.message === "string" && payload.message.trim() !== ""
      ? payload.message.trim()
      : "Gmail intake accepted.";
  const suffix = [];
  if (focusNotice !== "") {
    suffix.push(focusNotice);
  }
  if (nativeResponse && nativeResponse.ui_owner === "browser_app" && !resolvedBrowserOpen) {
    suffix.push("The browser app may need manual focus.");
  }
  if (nativeResponse && nativeResponse.ui_owner === "browser_app") {
    if (isBridgeIntegrityFailureReason(workspaceState.integrityFailureReason)) {
      const parts = [buildBridgeIntegrityFailureMessage(workspaceState)];
      if (focusNotice !== "") {
        parts.push(focusNotice);
      }
      await clearBrowserLaunchState(browserUrl);
      await reportBrowserOutcome("integrity_failure", workspaceState.integrityFailureReason);
      await notifyTab(tabId, "error", parts.join(" "));
      return { holdLock: false, outcome: "integrity_failure" };
    }
    if (workspaceState.loaded) {
      if (exactWorkspaceSurfaceConfirmed && clientHydrationStatus === "ready") {
        await clearActiveBrowserLaunchSession(browserUrl);
        await reportBrowserOutcome("loaded", "workspace_loaded");
        const message = suffix.length ? `${baseMessage} ${suffix.join(" ")}` : baseMessage;
        await notifyTab(tabId, "success", message);
        return withRuntimeStateRootCompatibility({ holdLock: false, outcome: "loaded" });
      }
      if (exactWorkspaceSurfaceConfirmed && clientHydrationStatus === "warming") {
        await clearActiveBrowserLaunchSession(browserUrl);
        await reportBrowserOutcome("warming", "workspace_loaded_client_warming");
        await notifyTab(
          tabId,
          "info",
          buildWorkspaceWarmupMessage({
            baseMessage,
            focusNotice,
            resolvedBrowserOpen,
          }),
        );
        return withRuntimeStateRootCompatibility({ holdLock: true, outcome: "warming" });
      }
      await clearBrowserLaunchState(browserUrl);
      await reportBrowserOutcome("workspace_surface_unconfirmed", "workspace_loaded_without_confirmed_surface");
      await notifyTab(
        tabId,
        "error",
        buildWorkspaceSurfaceConfirmationFailureMessage({
          resolvedBrowserOpen,
          focusNotice,
          hydrationStatus: clientHydrationStatus,
          hydrationResult: clientHydrationResult,
          expectedAssetVersion: workspaceState.assetVersion,
          launchSessionDiagnosticsCompatible: workspaceState.launchSessionDiagnosticsCompatible,
        }),
      );
      return withRuntimeStateRootCompatibility({ holdLock: false, outcome: "workspace_surface_unconfirmed" });
    }
    if (workspaceState.loadFailed) {
      const parts = [workspaceState.loadFailureMessage || "LegalPDF Translate could not load the exact Gmail message."];
      if (focusNotice !== "") {
        parts.push(focusNotice);
      }
      await clearBrowserLaunchState(browserUrl);
      await reportBrowserOutcome("load_failed", "workspace_load_failed");
      await notifyTab(tabId, "error", parts.join(" "));
      return withRuntimeStateRootCompatibility({ holdLock: false, outcome: "load_failed" });
    }
    if (workspaceState.warming || workspaceState.pending) {
      if (exactWorkspaceSurfaceConfirmed && (clientHydrationStatus === "ready" || clientHydrationStatus === "warming")) {
        await clearActiveBrowserLaunchSession(browserUrl);
        await reportBrowserOutcome("warming", "workspace_pending_with_confirmed_surface");
        await notifyTab(
          tabId,
          "info",
          buildWorkspaceWarmupMessage({
            baseMessage,
            focusNotice,
            resolvedBrowserOpen,
          }),
        );
        return withRuntimeStateRootCompatibility({ holdLock: true, outcome: "warming" });
      }
      await clearBrowserLaunchState(browserUrl);
      await reportBrowserOutcome("workspace_surface_unconfirmed", "workspace_pending_without_confirmed_surface");
      await notifyTab(
        tabId,
        "error",
        buildWorkspaceSurfaceConfirmationFailureMessage({
          resolvedBrowserOpen,
          focusNotice,
          hydrationStatus: clientHydrationStatus,
          hydrationResult: clientHydrationResult,
          expectedAssetVersion: workspaceState.assetVersion,
          launchSessionDiagnosticsCompatible: workspaceState.launchSessionDiagnosticsCompatible,
        }),
      );
      return withRuntimeStateRootCompatibility({ holdLock: false, outcome: "workspace_surface_unconfirmed" });
    }
    if (workspaceState.workspaceRouteReachable || workspaceState.appBootstrapReady) {
      await clearBrowserLaunchState(browserUrl);
      await reportBrowserOutcome("workspace_no_handoff", "workspace_route_reachable_without_exact_handoff");
      await notifyTab(
        tabId,
        "error",
        buildWorkspaceNoHandoffMessage({
          resolvedBrowserOpen,
          focusNotice,
        }),
      );
      return withRuntimeStateRootCompatibility({ holdLock: false, outcome: "workspace_no_handoff" });
    }
    await clearBrowserLaunchState(browserUrl);
    await reportBrowserOutcome("workspace_failure", "workspace_surface_not_ready");
    await notifyTab(
      tabId,
      "error",
      buildWorkspaceFailureMessage({
        resolvedBrowserOpen,
        focusNotice,
      }),
    );
    return withRuntimeStateRootCompatibility({ holdLock: false, outcome: "workspace_failure" });
  }
  const message = suffix.length ? `${baseMessage} ${suffix.join(" ")}` : baseMessage;
  await notifyTab(tabId, "success", message);
  return { holdLock: false, outcome: "accepted" };
}

if (chrome?.tabs?.onRemoved?.addListener) {
  chrome.tabs.onRemoved.addListener((tabId) => {
    void clearPendingBrowserSurfaceByTabId(tabId);
    void clearGmailClickSession(tabId);
  });
}

async function failSameTabHandoff(
  tabId,
  sourceGmailUrl,
  message,
  nativeResponse = null,
  details = {},
) {
  const browserUrl = normalizeUrl(details.browserUrl || nativeResponse?.browser_url);
  if (browserUrl !== "") {
    await clearBrowserLaunchState(browserUrl);
  }
  await recordGmailClickPhase(tabId, nativeResponse, {
    phase: GMAIL_CLICK_PHASE_FAILED,
    failureReason: normalizeToken(details.failureReason),
    sourceGmailUrl,
    browserUrl,
    surfaceVisibilityStatus: normalizeToken(details.surfaceVisibilityStatus),
    workspaceSurfaceConfirmed: details.workspaceSurfaceConfirmed === true,
    clientHydrationStatus: normalizeToken(details.clientHydrationStatus),
    outcome: normalizeToken(details.outcome || "failed"),
    reason: normalizeToken(details.reason || details.failureReason || "same_tab_handoff_failed"),
  });
  await clearGmailClickSession(tabId);
  if (await restoreTabToSourceGmail(tabId, sourceGmailUrl)) {
    await sleep(CLIENT_HYDRATION_POLL_MS * 2);
  }
  await notifyTab(tabId, "error", message);
}

async function handleGmailIntakeClick(tab, { trigger = "toolbar" } = {}) {
  if (!Number.isInteger(tab.id) || typeof tab.url !== "string" || !tab.url.startsWith("https://mail.google.com/")) {
    return;
  }

  const existingClickSession = await getGmailClickSession(tab.id);
  if (existingClickSession && isActiveGmailClickPhase(existingClickSession.phase)) {
    await notifyTab(
      tab.id,
      "info",
      "LegalPDF Translate is already preparing this Gmail handoff in the current tab. Please wait a few seconds.",
    );
    return;
  }
  await clearGmailClickSession(tab.id);

  const ready = await ensureContentScriptReady(tab.id);
  if (!ready) {
    await showFallbackBanner(
      tab.id,
      "error",
      "Reload Gmail after installing or updating the extension."
    );
    return;
  }

  const extractionResult = await sendTabMessage(tab.id, { type: "gmail-intake-extract" });
  if (!extractionResult.ok) {
    await notifyTab(tab.id, "error", "Reload Gmail after installing or updating the extension.");
    return;
  }

  const extraction = extractionResult.response;
  if (!extraction || extraction.ok !== true || typeof extraction.context !== "object" || extraction.context === null) {
    const message =
      extraction && typeof extraction.message === "string" && extraction.message.trim() !== ""
        ? extraction.message.trim()
        : "The open Gmail message is not identifiable exactly.";
    await notifyTab(tab.id, "error", message);
    return;
  }

  let handoffLock = claimHandoffLock(tab.id, extraction.context);
  if (!handoffLock.ok) {
    handoffInFlight.delete(handoffLock.key);
    handoffLock = claimHandoffLock(tab.id, extraction.context);
    if (!handoffLock.ok) {
      await notifyTab(
        tab.id,
        "info",
        "LegalPDF Translate is already preparing this Gmail handoff in the current tab. Please wait a few seconds.",
      );
      return;
    }
  }

  const sourceGmailUrl = normalizeUrl(extraction.context.source_gmail_url || tab.url);
  await rememberGmailClickSession(tab.id, {
    sourceGmailUrl,
    browserUrl: "",
    launchSessionId: "",
    handoffSessionId: "",
    phase: GMAIL_CLICK_PHASE_CONTEXT_EXTRACTED,
    failureReason: "",
    bridgeContextPosted: false,
  });

  let shouldReleaseHandoffLock = true;
  try {
    const bridgeResolution = await waitForPreparedBridgeConfigForClick();
    if (!bridgeResolution.ok) {
      await failSameTabHandoff(
        tab.id,
        sourceGmailUrl,
        bridgeResolution.message,
        bridgeResolution.nativeResponse,
        {
          failureReason: bridgeResolution.launchInProgress ? "launch_in_progress_timeout" : "native_prepare_failed",
          outcome: "prepare_failed",
          reason: normalizeToken(bridgeResolution.nativeResponse?.reason) || "native_prepare_failed",
        },
      );
      return;
    }
    if (!isHandoffLockCurrent(handoffLock)) {
      await clearGmailClickSession(tab.id);
      return;
    }

    const browserUrl = normalizeUrl(bridgeResolution.nativeResponse?.browser_url);
    const launchSessionId = normalizeToken(bridgeResolution.nativeResponse?.launch_session_id);
    const handoffSessionId = normalizeToken(bridgeResolution.nativeResponse?.handoff_session_id);
    const handoffContext = {
      ...extraction.context,
      handoff_session_id: handoffSessionId || undefined,
      source_gmail_url: sourceGmailUrl || undefined,
    };
    if (bridgeResolution.nativeResponse?.ui_owner !== "browser_app" || browserUrl === "") {
      await failSameTabHandoff(
        tab.id,
        sourceGmailUrl,
        "LegalPDF Translate did not return a browser-app Gmail workspace URL for this handoff.",
        bridgeResolution.nativeResponse,
        {
          failureReason: "browser_url_missing",
          outcome: "prepare_failed",
          reason: "browser_url_missing",
        },
      );
      return;
    }

    await recordGmailClickPhase(tab.id, bridgeResolution.nativeResponse, {
      phase: GMAIL_CLICK_PHASE_NATIVE_PREPARE_OK,
      sourceGmailUrl,
      browserUrl,
      launchSessionId,
      handoffSessionId,
      outcome: "prepare_ready",
      reason: trigger,
    });
    await rememberActiveBrowserLaunchSession(browserUrl, {
      launchSessionId,
      handoffSessionId,
      owner: BROWSER_OPEN_OWNER_EXTENSION,
      ttlMs: Number.isInteger(bridgeResolution.nativeResponse?.launch_lock_ttl_ms)
        ? bridgeResolution.nativeResponse.launch_lock_ttl_ms
        : LAUNCH_READINESS_WAIT_MS,
    });

    const redirectBrowserUrl = buildSameTabRedirectUrl(browserUrl, {
      launchSessionId,
      handoffSessionId,
      launchSessionSchemaVersion: EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION,
    });

    let redirectedTab;
    try {
      redirectedTab = await chrome.tabs.update(tab.id, {
        active: true,
        url: redirectBrowserUrl,
      });
    } catch (_error) {
      await failSameTabHandoff(
        tab.id,
        sourceGmailUrl,
        "LegalPDF Translate could not redirect the current Gmail tab into the intake workspace.",
        bridgeResolution.nativeResponse,
        {
          failureReason: "redirect_update_failed",
          outcome: "redirect_failed",
          reason: "redirect_update_failed",
        },
      );
      return;
    }

    await rememberPendingBrowserSurface(redirectBrowserUrl, {
      tabId: tab.id,
      windowId: Number.isInteger(redirectedTab?.windowId) ? redirectedTab.windowId : tab.windowId,
    }, {
      launchSessionId,
      handoffSessionId,
      browserOpenOwnedBy: BROWSER_OPEN_OWNER_EXTENSION,
      resolutionStrategy: "same_tab_redirect",
      surfaceCandidateSource: "same_tab_redirect",
      surfaceCandidateValid: true,
      surfaceInvalidationReason: "",
      freshTabCreatedAfterInvalidation: false,
    });
    await recordGmailClickPhase(tab.id, bridgeResolution.nativeResponse, {
      phase: GMAIL_CLICK_PHASE_SAME_TAB_REDIRECT_STARTED,
      sourceGmailUrl,
      browserUrl,
      launchSessionId,
      handoffSessionId,
      surfaceVisibilityStatus: "visible",
      tabId: tab.id,
      outcome: "redirect_started",
      reason: trigger,
    });

    const redirectCommit = await waitForSameTabRedirectCommit(tab.id, browserUrl);
    if (!redirectCommit.ok) {
      await failSameTabHandoff(
        tab.id,
        sourceGmailUrl,
        "LegalPDF Translate did not finish redirecting the current Gmail tab into the intake workspace.",
        bridgeResolution.nativeResponse,
        {
          browserUrl,
          launchSessionId,
          handoffSessionId,
          failureReason: "redirect_not_committed",
          surfaceVisibilityStatus: "not_visible",
          outcome: "redirect_failed",
          reason: "redirect_not_committed",
        },
      );
      return;
    }

    await recordGmailClickPhase(tab.id, bridgeResolution.nativeResponse, {
      phase: GMAIL_CLICK_PHASE_SAME_TAB_REDIRECT_COMMITTED,
      sourceGmailUrl,
      browserUrl,
      launchSessionId,
      handoffSessionId,
      surfaceVisibilityStatus: "visible",
      tabId: tab.id,
      workspaceSurfaceConfirmed: true,
      outcome: "redirect_committed",
      reason: trigger,
    });

    await primeBrowserClientHandoffSession(
      tab.id,
      handoffSessionId,
      launchSessionId,
      EXTENSION_LAUNCH_SESSION_SCHEMA_VERSION,
    );

    // Do not gate the real Gmail payload on content-script hydration. If the
    // service worker is interrupted here, the browser app would otherwise be
    // left open forever with only a shell and no message context.
    const handoffResult = await postContext(
      tab.id,
      handoffContext,
      bridgeResolution.config,
      bridgeResolution.nativeResponse,
      "",
      true,
      browserUrl,
      false,
      tab.windowId,
    );
    const handoffOutcome = normalizeToken(handoffResult?.outcome).toLowerCase();
    const bridgeContextPosted = !["bridge_unreachable", "bridge_rejected"].includes(handoffOutcome);
    const runtimeStateRoot = normalizeToken(
      handoffResult?.observedRuntimeStateRoot
      || handoffResult?.expectedRuntimeStateRoot
      || bridgeResolution.nativeResponse?.runtime_state_root,
    );
    const runtimeStateRootKnownCompatible =
      bridgeContextPosted && handoffResult?.runtimeStateRootCompatible === true && runtimeStateRoot !== "";
    const clientHydrationStatus = handoffOutcome === "loaded"
      ? "ready"
      : handoffOutcome === "warming"
        ? "warming"
        : "not_found";
    await recordGmailClickPhase(tab.id, bridgeResolution.nativeResponse, {
      phase: bridgeContextPosted ? GMAIL_CLICK_PHASE_BRIDGE_CONTEXT_POSTED : GMAIL_CLICK_PHASE_FAILED,
      sourceGmailUrl,
      browserUrl,
      launchSessionId,
      handoffSessionId,
      bridgeContextPosted,
      clientHydrationStatus,
      surfaceVisibilityStatus: "visible",
      workspaceSurfaceConfirmed: true,
      tabId: tab.id,
      outcome: normalizeToken(handoffResult?.outcome || (bridgeContextPosted ? "bridge_context_posted" : "bridge_failed")),
      reason: normalizeToken(handoffResult?.outcome || "bridge_failed"),
      failureReason: bridgeContextPosted ? "" : normalizeToken(handoffResult?.outcome || "bridge_failed"),
      ...(runtimeStateRootKnownCompatible
        ? {
          runtimeStateRootCompatible: true,
          expectedRuntimeStateRoot: normalizeToken(handoffResult?.expectedRuntimeStateRoot) || runtimeStateRoot,
          observedRuntimeStateRoot: normalizeToken(handoffResult?.observedRuntimeStateRoot) || runtimeStateRoot,
        }
        : {}),
    });
    if (
      bridgeContextPosted
      && !["accepted", "loaded", "warming"].includes(normalizeToken(handoffResult?.outcome))
    ) {
      if (await restoreTabToSourceGmail(tab.id, sourceGmailUrl)) {
        await sleep(CLIENT_HYDRATION_POLL_MS * 2);
      }
      await notifyTab(
        tab.id,
        "error",
        "LegalPDF Translate could not complete the Gmail handoff in this tab, so Gmail was restored. Please try again.",
      );
    }
    await clearGmailClickSession(tab.id);
    shouldReleaseHandoffLock = Boolean(handoffResult?.holdLock) === false;
  } finally {
    if (shouldReleaseHandoffLock) {
      releaseHandoffLock(handoffLock);
    }
  }
}

chrome.action.onClicked.addListener(async (tab) => {
  await handleGmailIntakeClick(tab, { trigger: "toolbar" });
});

async function resolveDebugGmailTab(detail = {}) {
  const requestedTabId = Number.parseInt(String(detail?.tab_id ?? detail?.tabId ?? ""), 10);
  if (Number.isInteger(requestedTabId)) {
    const requestedTab = await readTabById(requestedTabId);
    if (
      requestedTab
      && Number.isInteger(requestedTab.id)
      && typeof requestedTab.url === "string"
      && requestedTab.url.startsWith("https://mail.google.com/")
    ) {
      return requestedTab;
    }
  }

  const sourceGmailUrl = normalizeUrl(detail?.source_gmail_url || detail?.sourceGmailUrl);
  let tabs = [];
  try {
    tabs = await chrome.tabs.query({ url: "https://mail.google.com/*" });
  } catch (_error) {
    tabs = [];
  }
  if (!Array.isArray(tabs) || tabs.length === 0) {
    return null;
  }
  if (sourceGmailUrl !== "") {
    const exactSourceTab = tabs.find((tab) => normalizeUrl(tab?.url) === sourceGmailUrl);
    if (exactSourceTab && Number.isInteger(exactSourceTab.id)) {
      return exactSourceTab;
    }
  }
  const activeCurrentWindowTab = tabs.find((tab) => tab?.active === true && tab?.highlighted === true);
  if (activeCurrentWindowTab && Number.isInteger(activeCurrentWindowTab.id)) {
    return activeCurrentWindowTab;
  }
  const activeTab = tabs.find((tab) => tab?.active === true);
  if (activeTab && Number.isInteger(activeTab.id)) {
    return activeTab;
  }
  return tabs.find((tab) => Number.isInteger(tab?.id)) || null;
}

if (chrome?.runtime?.onMessage?.addListener) {
  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (!message || typeof message !== "object") {
      return false;
    }

    if (message.type === "gmail-intake-debug-click-active-gmail") {
      const detail = message.detail && typeof message.detail === "object" ? message.detail : {};
      void resolveDebugGmailTab(detail)
        .then(async (tab) => {
          if (!tab || !Number.isInteger(tab.id)) {
            sendResponse({ ok: false, message: "gmail_tab_unavailable" });
            return;
          }
          await handleGmailIntakeClick(tab, { trigger: "debug-active-gmail" });
          sendResponse({
            ok: true,
            tab: {
              id: tab.id,
              url: normalizeUrl(tab.url),
              active: tab.active === true,
              windowId: Number.isInteger(tab.windowId) ? tab.windowId : null,
            },
          });
        })
        .catch((error) => sendResponse({
          ok: false,
          message: error instanceof Error && error.message ? error.message : "gmail_intake_debug_failed",
        }));
      return true;
    }

    if (message.type === "gmail-intake-debug-click") {
      const tab = sender?.tab;
      if (!tab || !Number.isInteger(tab.id)) {
        sendResponse({ ok: false, message: "gmail_tab_unavailable" });
        return false;
      }
      void handleGmailIntakeClick(tab, { trigger: "debug" })
        .then(() => sendResponse({ ok: true }))
        .catch((error) => sendResponse({
          ok: false,
          message: error instanceof Error && error.message ? error.message : "gmail_intake_debug_failed",
        }));
      return true;
    }

    return false;
  });
}

if (globalThis && globalThis.__LEGALPDF_TEST__ === true) {
  globalThis.__legalPdfGmailIntakeBackgroundTestHooks = {
    LAUNCH_READINESS_WAIT_MS,
    HANDOFF_LOCK_MAX_AGE_MS,
    CLIENT_HYDRATION_WAIT_MS,
    CLIENT_HYDRATION_RELOAD_WAIT_MS,
    buildHandoffKey,
    claimHandoffLock,
    releaseHandoffLock,
    isHandoffLockCurrent,
    handoffInFlight,
    resolveBridgeConfigForClick,
    postContext,
    settleBrowserAppHandoff,
    shouldWaitForLaunchedBrowserTab,
    openOrFocusBrowserApp,
    claimOrRecoverHandoffLock,
    rememberPendingBrowserSurface,
    rememberActiveBrowserLaunchSession,
    getActiveBrowserLaunchSession,
    clearActiveBrowserLaunchSession,
    focusExistingBrowserAppWindow,
    resolveBrowserAppTab,
    waitForBrowserClientHydration,
    reloadBrowserAppTab,
    waitForPreparedBridgeConfigForClick,
    waitForSameTabRedirectCommit,
    waitForSameTabWorkspaceHydration,
    handleGmailIntakeClick,
    resolveDebugGmailTab,
    gmailClickSessions,
    pendingBrowserSurfaces,
    activeBrowserLaunchSessions,
  };
}
