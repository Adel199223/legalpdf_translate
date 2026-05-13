from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def test_translation_run_status_presentation_module_builds_run_status_state() -> None:
    script = r"""
const presentation = await import(__TRANSLATION_RUN_STATUS_PRESENTATION_MODULE_URL__);
const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";

const runningJob = {
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
};

const cases = {
  idle: presentation.deriveTranslationRunStatusView(),
  nullSafe: presentation.deriveTranslationRunStatusView(null, null),
  manualUploadingReplacement: presentation.deriveTranslationRunStatusView(null, {
    sourceState: {
      status: "manual-uploading",
      ready: false,
      replacingPrepared: true,
    },
  }),
  manualErrorMalicious: presentation.deriveTranslationRunStatusView(null, {
    sourceState: {
      status: "manual-error",
      ready: false,
      message: `Could not stage ${malicious}`,
    },
  }),
  preparedStartPage: presentation.deriveTranslationRunStatusView(null, {
    preparedLaunch: {
      page_count: 10,
      start_page: 3,
    },
    sourceState: {
      status: "prepared-ready",
      ready: true,
      pageCount: 10,
    },
    sourceReady: true,
    sourcePageCount: 10,
  }),
  sourceReady: presentation.deriveTranslationRunStatusView(null, {
    sourceState: {
      status: "manual-ready",
      ready: true,
      pageCount: 12,
    },
    sourceReady: true,
    sourcePageCount: 12,
  }),
  currentJobSource: presentation.deriveTranslationRunStatusView(null, {
    sourceState: {
      status: "current-job",
      ready: false,
      pageCount: 4,
    },
    sourcePageCount: 4,
  }),
  running: presentation.deriveTranslationRunStatusView(runningJob),
  completedRawStatus: presentation.deriveTranslationRunStatusView({
    job_id: "tx-complete",
    job_kind: "translate",
    status: "completed",
    status_text: '{"job_id":"tx-complete","progress":{"phase":"done"}}',
    result: {
      completed_pages: 9,
    },
  }),
  runningRawStatus: presentation.deriveTranslationRunStatusView({
    job_id: "tx-raw",
    job_kind: "translate",
    status: "running",
    status_text: '{"job_id":"tx-raw","progress":{"phase":"page"}}',
    result: {
      completed_pages: 2,
    },
  }),
  invalidInputs: presentation.deriveTranslationRunStatusView({
    job_id: "tx-invalid",
    job_kind: "translate",
    status: "running",
    progress: {
      selected_index: malicious,
      selected_total: "NaN",
      real_page: "-5",
      status_text: `Working ${malicious}`,
    },
    result: {
      review_queue_count: malicious,
      failed_page: "not-a-page",
    },
    logs: [
      `page=${malicious} image_used=True retry_used=True status=finished`,
      "Page nope failed",
    ],
  }),
  failed: presentation.deriveTranslationRunStatusView({
    job_id: "tx-failed",
    job_kind: "translate",
    status: "failed",
    result: {
      failed_page: 7,
    },
    logs: [
      "Page 7 failed",
    ],
  }),
  cancelRequested: presentation.deriveTranslationRunStatusView({
    job_id: "tx-cancel",
    job_kind: "translate",
    status: "cancel_requested",
    status_text: "Stopping after the current page.",
  }),
};

console.log(JSON.stringify({
  exportType: typeof presentation.deriveTranslationRunStatusView,
  cases,
}));
"""
    results = run_browser_esm_json_probe(
        script,
        {"__TRANSLATION_RUN_STATUS_PRESENTATION_MODULE_URL__": "translation_run_status_presentation.js"},
        timeout_seconds=20,
    )

    assert results["exportType"] == "function"

    idle = results["cases"]["idle"]
    assert idle == {
        "percentValue": 0,
        "percentText": "0%",
        "chipText": "Waiting",
        "chipTone": "info",
        "currentTask": "Choose a source file to begin.",
        "pagesText": "0 / --",
        "currentPageText": "Not started",
        "imageRetryText": "No image or retry markers yet.",
        "alertsText": "No flagged pages or errors.",
    }
    assert results["cases"]["nullSafe"] == idle

    uploading = results["cases"]["manualUploadingReplacement"]
    assert uploading["chipText"] == "Checking"
    assert uploading["chipTone"] == "info"
    assert uploading["currentTask"] == "Checking the replacement document..."

    manual_error = results["cases"]["manualErrorMalicious"]
    assert manual_error["chipText"] == "Needs attention"
    assert manual_error["chipTone"] == "bad"
    assert manual_error["currentTask"] == "Could not stage <img src=x onerror=alert(1)><script>bad()</script>"

    prepared = results["cases"]["preparedStartPage"]
    assert prepared["chipText"] == "Ready"
    assert prepared["chipTone"] == "info"
    assert prepared["currentTask"] == "Prepared Gmail attachment is ready to start."
    assert prepared["pagesText"] == "0 / 10"
    assert prepared["currentPageText"] == "Start at page 3"

    source_ready = results["cases"]["sourceReady"]
    assert source_ready["chipText"] == "Ready"
    assert source_ready["chipTone"] == "ok"
    assert source_ready["currentTask"] == (
        "Source file is ready. Confirm the language and folder, then start translation."
    )
    assert source_ready["pagesText"] == "0 / 12"

    current_job_source = results["cases"]["currentJobSource"]
    assert current_job_source["chipText"] == "Running"
    assert current_job_source["chipTone"] == "info"
    assert current_job_source["currentTask"] == "Current translation job is using this source."

    running = results["cases"]["running"]
    assert running["percentValue"] == 40
    assert running["percentText"] == "40%"
    assert running["chipText"] == "Running"
    assert running["chipTone"] == "info"
    assert running["currentTask"] == "Translating page 4"
    assert running["pagesText"] == "2 / 5"
    assert running["currentPageText"] == "Page 4"
    assert running["imageRetryText"] == "Retry on page 4 | Image on page 4 | Images 1 | Retries 1"
    assert running["alertsText"] == "Flagged 1 | Errors 1"

    completed = results["cases"]["completedRawStatus"]
    assert completed["percentValue"] == 100
    assert completed["percentText"] == "100%"
    assert completed["chipText"] == "Complete"
    assert completed["chipTone"] == "ok"
    assert completed["currentTask"] == "Completed pages: 9. Latest technical state is available in details."
    assert completed["currentPageText"] == "Completed"
    assert '{"job_id"' not in completed["currentTask"]

    raw_running = results["cases"]["runningRawStatus"]
    assert raw_running["currentTask"] == "Translating... Completed pages: 2. Latest technical state is available in details."
    assert '{"job_id"' not in raw_running["currentTask"]

    invalid = results["cases"]["invalidInputs"]
    assert invalid["percentValue"] == 0
    assert invalid["currentTask"] == "Working <img src=x onerror=alert(1)><script>bad()</script>"
    assert invalid["pagesText"] == "0 / --"
    assert invalid["currentPageText"] == "Not started"
    assert invalid["imageRetryText"] == "No image or retry markers yet."
    assert invalid["alertsText"] == "No flagged pages or errors."

    failed = results["cases"]["failed"]
    assert failed["chipText"] == "Needs attention"
    assert failed["chipTone"] == "bad"
    assert failed["currentTask"] == "Latest technical state is available in details."
    assert failed["alertsText"] == "Errors 1"

    cancel_requested = results["cases"]["cancelRequested"]
    assert cancel_requested["chipText"] == "Stopping"
    assert cancel_requested["chipTone"] == "warn"
    assert cancel_requested["currentTask"] == "Stopping after the current page."
