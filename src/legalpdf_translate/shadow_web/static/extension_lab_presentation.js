export function extensionReadinessCardText(prepare = {}, bridgeSummary = {}) {
  if (prepare.ok === true) {
    return "Ready for Gmail intake in this mode.";
  }
  if (bridgeSummary.status === "info") {
    return "This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting.";
  }
  return "Needs attention before Gmail intake can start here. Open technical details below when troubleshooting.";
}

export function extensionInstallCardText(extensionReport = {}) {
  const activeCount = Array.isArray(extensionReport.active_extension_ids)
    ? extensionReport.active_extension_ids.length
    : 0;
  const staleCount = Array.isArray(extensionReport.stale_extension_ids)
    ? extensionReport.stale_extension_ids.length
    : 0;
  if (activeCount > 0) {
    return "Browser helper details were found. Open technical details below for installation IDs.";
  }
  if (staleCount > 0) {
    return "Older browser helper details were found. Open technical details below when troubleshooting.";
  }
  return "No browser helper installation details were reported.";
}

export function extensionModeCardText(runtime = {}, bridgeSummary = {}) {
  const lines = [
    runtime.live_data === true
      ? "Using live app settings and saved work."
      : "Using isolated test settings and saved work.",
  ];
  if (runtime.live_data === true) {
    lines.push("Use this page when Gmail intake needs a deeper technical check.");
  } else if (bridgeSummary.status === "info") {
    lines.push("This test mode is isolated from live Gmail intake. Open technical details below when troubleshooting.");
  } else {
    lines.push("Live Gmail readiness can differ from this isolated test mode.");
  }
  return lines.join("\n");
}

export function buildExtensionLabCards({
  prepare = {},
  extensionReport = {},
  bridgeSummary = {},
  runtime = {},
} = {}) {
  const activeInstallCount = Array.isArray(extensionReport.active_extension_ids)
    ? extensionReport.active_extension_ids.length
    : 0;

  return [
    {
      title: "Gmail helper readiness",
      text: extensionReadinessCardText(prepare, bridgeSummary),
      status: bridgeSummary.status || (prepare.ok === true ? "ok" : "warn"),
      label: prepare.ok === true ? "Ready" : bridgeSummary.label || "Needs attention",
    },
    {
      title: "Installed browser helper",
      text: extensionInstallCardText(extensionReport),
      status: activeInstallCount > 0 ? "ok" : "warn",
      label: activeInstallCount > 0 ? "Detected" : "Needs attention",
    },
    {
      title: "Current mode",
      text: extensionModeCardText(runtime, bridgeSummary),
      status: bridgeSummary.status === "info" ? "info" : runtime.live_data ? "warn" : "ok",
      label: runtime.live_data ? "Live mode" : "Test mode",
    },
  ];
}
