export const PRIMARY_NAV_ORDER = ["new-job", "gmail-intake", "recent-jobs"];
export const MORE_NAV_ORDER = ["dashboard", "settings", "profile", "power-tools", "extension-lab"];
export const OPERATOR_ROUTE_ORDER = ["power-tools", "extension-lab"];
export const DAILY_RUNTIME_MODE_BANNER_ROUTES = new Set(["dashboard", "new-job"]);

export const LIVE_MODE_BANNER_TEXT = "Live mode: using your real settings, Gmail drafts, and saved work.";
export const SHADOW_MODE_BANNER_TEXT = "Test mode: using isolated app data. Live Gmail and saved work may differ.";

const BEGINNER_PRIMARY_SURFACES = ["dashboard", "new-job", "recent-jobs", "profile", "settings"];

function findNavigationItem(items, id) {
  return items.find((item) => item.id === id) || null;
}

export function isLiveRuntimeMode(runtime = {}, runtimeMode = "shadow") {
  const safeRuntime = runtime || {};
  return safeRuntime.live_data === true || runtimeMode === "live";
}

export function isOperatorRoute(activeView = "") {
  return OPERATOR_ROUTE_ORDER.includes(activeView);
}

export function buildNavigationGroups(items = [], { showGmailNav = false } = {}) {
  const primary = [];
  for (const id of PRIMARY_NAV_ORDER) {
    if (id === "gmail-intake") {
      if (!showGmailNav) {
        continue;
      }
      const source = findNavigationItem(items, "gmail-intake");
      primary.push({
        id: "gmail-intake",
        label: source?.label || "Gmail",
        status: source?.status || "ready",
      });
      continue;
    }
    const item = findNavigationItem(items, id);
    if (item) {
      primary.push(item);
    }
  }

  const more = [];
  for (const id of MORE_NAV_ORDER) {
    const item = findNavigationItem(items, id);
    if (item) {
      more.push(item);
    }
  }
  return { primary, more };
}

export function deriveBeginnerPrimarySurface({
  uiVariant = "",
  activeView = "",
  operatorChromeActive = false,
} = {}) {
  return uiVariant === "qt"
    && BEGINNER_PRIMARY_SURFACES.includes(activeView)
    && !operatorChromeActive;
}

export function deriveRouteAwareTopbarStatus({
  runtime = {},
  activeView = "",
  uiVariant = "",
  operatorChromeActive = false,
  navLabel = "",
  runtimeMode = "shadow",
} = {}) {
  const liveMode = isLiveRuntimeMode(runtime, runtimeMode);
  if (uiVariant === "qt" && activeView === "dashboard" && !operatorChromeActive) {
    return {
      eyebrow: "Overview",
      title: "LegalPDF Translate",
      status: "Check what is ready and choose what you want to do next.",
      tone: liveMode ? "info" : "ok",
    };
  }
  if (uiVariant === "qt" && activeView === "new-job" && !operatorChromeActive) {
    return {
      eyebrow: "New Job",
      title: "LegalPDF Translate",
      status: "Choose a document, confirm the language, then start translation.",
      tone: liveMode ? "info" : "ok",
    };
  }
  if (uiVariant === "qt" && activeView === "recent-jobs" && !operatorChromeActive) {
    return {
      eyebrow: "Recent Work",
      title: "LegalPDF Translate",
      status: "Open saved cases or review recent translation runs.",
      tone: liveMode ? "info" : "ok",
    };
  }
  if (uiVariant === "qt" && activeView === "profile" && !operatorChromeActive) {
    return {
      eyebrow: "Profiles",
      title: "LegalPDF Translate",
      status: "Edit the details used in documents, travel distances, and Gmail replies.",
      tone: liveMode ? "info" : "ok",
    };
  }
  if (uiVariant === "qt" && activeView === "settings" && !operatorChromeActive) {
    return {
      eyebrow: "App Settings",
      title: "LegalPDF Translate",
      status: "Set defaults and check the tools used for translation, Gmail, and Word/PDF output.",
      tone: liveMode ? "info" : "ok",
    };
  }
  if (uiVariant === "qt" && activeView === "gmail-intake" && !operatorChromeActive) {
    return {
      eyebrow: "Gmail",
      title: "Review Gmail Attachments",
      status: "Choose the attachment you want to process, preview it if needed, then continue.",
      tone: liveMode ? "info" : "ok",
    };
  }
  if (uiVariant === "qt" && activeView === "power-tools") {
    return {
      eyebrow: "Advanced Tools",
      title: "LegalPDF Translate | Advanced Tools",
      status: "Use glossary, quality-check, and troubleshooting tools when you need more control.",
      tone: liveMode ? "info" : "ok",
    };
  }
  if (uiVariant === "qt" && activeView === "extension-lab") {
    return {
      eyebrow: "Browser Helper",
      title: "LegalPDF Translate | Browser Helper Checks",
      status: "Check the browser helper used for Gmail intake. Technical details stay below.",
      tone: liveMode ? "info" : "ok",
    };
  }

  const label = String(navLabel || "").trim();
  return {
    eyebrow: label === "Dashboard" ? "Overview" : label || "Workspace",
    title: label && label !== "Dashboard"
      ? `LegalPDF Translate | ${label}`
      : "LegalPDF Translate",
    status: liveMode ? LIVE_MODE_BANNER_TEXT : SHADOW_MODE_BANNER_TEXT,
    tone: liveMode ? "info" : "ok",
  };
}

export function runtimeModeBannerText(runtime = {}, runtimeMode = "shadow") {
  return isLiveRuntimeMode(runtime, runtimeMode) ? LIVE_MODE_BANNER_TEXT : SHADOW_MODE_BANNER_TEXT;
}

export function shouldShowDailyRuntimeModeBanner({
  uiVariant = "",
  activeView = "",
  operatorChromeActive = false,
} = {}) {
  return uiVariant === "qt"
    && DAILY_RUNTIME_MODE_BANNER_ROUTES.has(activeView)
    && !operatorChromeActive;
}

export function beginnerSurfaceTargetLabel(activeView = "") {
  if (activeView === "dashboard") {
    return "overview screen";
  }
  if (activeView === "recent-jobs") {
    return "recent work screen";
  }
  if (activeView === "profile") {
    return "profile setup screen";
  }
  if (activeView === "settings") {
    return "settings screen";
  }
  return "translation screen";
}

export function runtimeModeDisplayLabel(runtime = {}) {
  return runtime?.live_data ? "Live mode" : "Test mode";
}
