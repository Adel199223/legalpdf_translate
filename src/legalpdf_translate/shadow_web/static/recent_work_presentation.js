function titleCaseWords(value) {
  return String(value || "")
    .trim()
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
    .join(" ");
}

function recentWorkTypeLabel(value) {
  return String(value || "").trim().toLowerCase() === "interpretation"
    ? "Interpretation"
    : "Translation";
}

function recentRunKindLabel(value) {
  const kind = String(value || "").trim().toLowerCase();
  if (kind === "translate") {
    return "Translation";
  }
  if (kind === "analyze") {
    return "Analysis";
  }
  if (kind === "rebuild") {
    return "DOCX rebuild";
  }
  return titleCaseWords(kind) || "Translation";
}

function recentRunStatusLabel(value) {
  const status = String(value || "").trim().toLowerCase();
  if (status === "queued") {
    return "Queued";
  }
  if (status === "running") {
    return "Running";
  }
  if (status === "completed") {
    return "Complete";
  }
  if (status === "failed") {
    return "Needs attention";
  }
  if (status === "cancel_requested") {
    return "Cancel requested";
  }
  if (status === "canceled") {
    return "Canceled";
  }
  return titleCaseWords(status) || "Unknown";
}

export function formatRecentRunTitle(job = {}) {
  const sourcePath = String(job?.config?.source_path || "").trim();
  if (sourcePath) {
    const segments = sourcePath.split(/[\\/]/).filter(Boolean);
    return segments[segments.length - 1] || sourcePath;
  }
  return String(job?.job_id || "").trim() || "Translation run";
}

export function deriveRecentWorkPresentation(options = {}) {
  const {
    recentItemCount = 0,
    translationRunCount = 0,
    recordAvailable = true,
    jobType = "",
    job = null,
  } = options || {};
  const typeLabel = recentWorkTypeLabel(jobType || job?.job_type || job?.row?.job_type);
  const targetLang = String(job?.config?.target_lang || "").trim().toUpperCase();
  const translationRunSubtitleBits = [
    recentRunKindLabel(job?.job_kind),
    targetLang ? `Target ${targetLang}` : "",
    recentRunStatusLabel(job?.status),
  ].filter(Boolean);
  const deleteConfirmMessage = typeLabel === "Interpretation"
    ? "Delete this saved interpretation record? This cannot be undone."
    : typeLabel === "Translation"
      ? "Delete this saved translation record? This cannot be undone."
      : "Delete this saved record? This cannot be undone.";

  return {
    typeLabel,
    recentWorkEmpty: "No saved work yet. Completed translations and interpretation requests will appear here.",
    recentCasesEmpty: "No saved cases yet.",
    recentWorkCount: `${recentItemCount} recent item(s) ready.`,
    recentOpenLabel: recordAvailable ? "Open" : "Open unavailable",
    recentDeleteLabel: "Delete record",
    interpretationHistoryEmpty: "No saved interpretation requests yet.",
    interpretationHistoryOpenLabel: "Open",
    interpretationHistoryDeleteLabel: "Delete record",
    translationHistoryEmpty: "No saved translation cases yet.",
    translationHistoryOpenLabel: "Open",
    translationHistoryDeleteLabel: "Delete record",
    translationRunsEmpty: "No translation runs have started yet.",
    translationRunsCount: `${translationRunCount} translation run(s) ready.`,
    translationRunOpenLabel: "Open run",
    translationRunResumeLabel: "Resume",
    translationRunRebuildLabel: "Rebuild DOCX",
    translationRunTitle: formatRecentRunTitle(job),
    translationRunSubtitle: translationRunSubtitleBits.join(" | "),
    deleteConfirmMessage,
    deleteStatus: "Saved record deleted.",
    refreshStatus: "Saved work refreshed.",
    loadedSavedCaseStatus: "Saved case record loaded. Review the details below.",
  };
}
