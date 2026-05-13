from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def test_recent_work_presentation_module_builds_saved_work_copy() -> None:
    script = r"""
const presentation = await import(__RECENT_WORK_PRESENTATION_MODULE_URL__);

const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";
const maliciousFilename = "<img src=x onerror=alert(1)><script>bad()<script>";

const cases = {
  empty: presentation.deriveRecentWorkPresentation(),
  loadedInterpretation: presentation.deriveRecentWorkPresentation({
    recentItemCount: 3,
    recordAvailable: false,
    jobType: "Interpretation",
  }),
  translationHistory: presentation.deriveRecentWorkPresentation({
    jobType: "Translation",
  }),
  unknownType: presentation.deriveRecentWorkPresentation({
    jobType: malicious,
  }),
  maliciousRun: presentation.deriveRecentWorkPresentation({
    translationRunCount: 2,
    job: {
      job_id: `tx-${malicious}`,
      job_kind: "translate",
      status: "running",
      config: {
        source_path: `C:/workspace/cases/notice ${maliciousFilename}.pdf`,
        target_lang: "fr",
      },
    },
  }),
  fallbackRun: presentation.deriveRecentWorkPresentation({
    job: {
      job_id: `job-${malicious}`,
      job_kind: "cancel_requested",
      status: "failed",
      config: {},
    },
  }),
  nullSafe: presentation.deriveRecentWorkPresentation(null),
};

console.log(JSON.stringify({
  exportTypes: {
    deriveRecentWorkPresentation: typeof presentation.deriveRecentWorkPresentation,
    formatRecentRunTitle: typeof presentation.formatRecentRunTitle,
  },
  titles: {
    fromPath: presentation.formatRecentRunTitle({
      config: {
        source_path: `C:/workspace/cases/notice ${maliciousFilename}.pdf`,
      },
    }),
    fromJobId: presentation.formatRecentRunTitle({ job_id: `job-${malicious}` }),
    fallback: presentation.formatRecentRunTitle(),
  },
  cases,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__RECENT_WORK_PRESENTATION_MODULE_URL__": "recent_work_presentation.js"},
        timeout_seconds=20,
    )

    assert results["exportTypes"] == {
        "deriveRecentWorkPresentation": "function",
        "formatRecentRunTitle": "function",
    }

    empty = results["cases"]["empty"]
    assert empty["recentWorkEmpty"] == "No saved work yet. Completed translations and interpretation requests will appear here."
    assert empty["recentCasesEmpty"] == "No saved cases yet."
    assert empty["translationHistoryEmpty"] == "No saved translation cases yet."
    assert empty["translationRunsEmpty"] == "No translation runs have started yet."
    assert empty["recentOpenLabel"] == "Open"
    assert empty["recentDeleteLabel"] == "Delete record"
    assert empty["translationRunTitle"] == "Translation run"
    assert empty["translationRunSubtitle"] == "Translation | Unknown"
    assert empty["deleteConfirmMessage"] == "Delete this saved translation record? This cannot be undone."

    loaded = results["cases"]["loadedInterpretation"]
    assert loaded["typeLabel"] == "Interpretation"
    assert loaded["recentWorkCount"] == "3 recent item(s) ready."
    assert loaded["recentOpenLabel"] == "Open unavailable"
    assert loaded["deleteConfirmMessage"] == "Delete this saved interpretation record? This cannot be undone."

    translation_history = results["cases"]["translationHistory"]
    assert translation_history["translationHistoryOpenLabel"] == "Open"
    assert translation_history["translationHistoryDeleteLabel"] == "Delete record"
    assert translation_history["refreshStatus"] == "Saved work refreshed."
    assert translation_history["loadedSavedCaseStatus"] == "Saved case record loaded. Review the details below."

    assert results["cases"]["unknownType"]["typeLabel"] == "Translation"
    assert results["cases"]["unknownType"]["deleteConfirmMessage"] == (
        "Delete this saved translation record? This cannot be undone."
    )

    malicious_run = results["cases"]["maliciousRun"]
    assert malicious_run["translationRunsCount"] == "2 translation run(s) ready."
    assert malicious_run["translationRunTitle"] == "notice <img src=x onerror=alert(1)><script>bad()<script>.pdf"
    assert malicious_run["translationRunSubtitle"] == "Translation | Target FR | Running"

    fallback_run = results["cases"]["fallbackRun"]
    assert fallback_run["translationRunTitle"] == "job-<img src=x onerror=alert(1)><script>bad()</script>"
    assert fallback_run["translationRunSubtitle"] == "Cancel Requested | Needs attention"

    assert results["cases"]["nullSafe"] == empty
    assert results["titles"] == {
        "fromPath": "notice <img src=x onerror=alert(1)><script>bad()<script>.pdf",
        "fromJobId": "job-<img src=x onerror=alert(1)><script>bad()</script>",
        "fallback": "Translation run",
    }

    helper_text = " ".join(
        str(value)
        for group in results["cases"].values()
        for value in group.values()
    )
    assert "job-log rows" not in helper_text
    assert "browser translation jobs" not in helper_text
    assert "row #" not in helper_text
