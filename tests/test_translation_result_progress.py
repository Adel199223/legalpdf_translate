from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def test_running_result_card_uses_done_count_instead_of_last_page_number() -> None:
    result = run_browser_esm_json_probe(r"""
const { buildTranslationResultCardPresentation } = await import(__RESULT_MODULE_URL__);
const { deriveTranslationRunStatusView } = await import(__STATUS_MODULE_URL__);
const jobs = [
  { status: "running", status_text: "Page 2 finished", progress: { selected_index: 1, selected_total: 2, real_page: 2, status_text: "Page 2 finished" } },
  { status: "running", status_text: "Page 2 failed", progress: { selected_index: 1, selected_total: 2, real_page: 2 } },
  { status: "running", status_text: "Resumed 2 page(s)", progress: { selected_index: 2, selected_total: 3, real_page: 0 } },
  { status: "queued", status_text: "Queued", progress: { selected_index: 0, selected_total: 2 } },
  { status: "cancel_requested", status_text: "Stopping", progress: { selected_index: 1, selected_total: 2 } },
  { status: "running", status_text: "Assembling DOCX", progress: { selected_index: 2, selected_total: 2 } },
];
console.log(JSON.stringify(jobs.map((job) => ({
  card: buildTranslationResultCardPresentation({ job: { job_kind: "translate", ...job } }),
  run: deriveTranslationRunStatusView({ job_kind: "translate", ...job }),
}))));
""", {
        "__RESULT_MODULE_URL__": "translation_result_presentation.js",
        "__STATUS_MODULE_URL__": "translation_run_status_presentation.js",
    })
    assert [item["card"]["summaryLines"] for item in result] == [
        ["Completed pages: 1 of 2"],
        ["Completed pages: 1 of 2"],
        ["Completed pages: 2 of 3"],
        ["Completed pages: 0 of 2"],
        ["Completed pages: 1 of 2"],
        ["Completed pages: 2 of 2"],
    ]
    assert result[0]["card"]["title"] == "Page 2 finished"
    assert result[0]["run"]["percentValue"] == 50
    assert result[-1]["card"]["label"] == "running"
    assert all(item["card"]["tone"] == "info" for item in result)


def test_active_result_card_does_not_invent_a_count_without_valid_progress() -> None:
    result = run_browser_esm_json_probe(r"""
const { buildTranslationResultCardPresentation } = await import(__RESULT_MODULE_URL__);
const malicious = "<img src=x onerror=alert(1)><script>bad()</script>";
const progressValues = [null, {}, { selected_total: 2 },
  { selected_index: null, selected_total: 2 },
  { selected_index: -1, selected_total: 2 },
  { selected_index: 3, selected_total: 2 },
  { selected_index: 0.5, selected_total: 2 },
  { selected_index: malicious, selected_total: 2 },
  { selected_index: 1, selected_total: malicious },
];
console.log(JSON.stringify(progressValues.map((progress) => buildTranslationResultCardPresentation({
  job: { job_kind: "translate", status: "running", status_text: malicious, progress },
}))));
""", {"__RESULT_MODULE_URL__": "translation_result_presentation.js"})
    for card in result:
        assert card["summaryLines"] == ["Waiting for page progress."]
        assert card["title"] == "<img src=x onerror=alert(1)><script>bad()</script>"


def test_result_card_preserves_terminal_and_explicit_result_summaries() -> None:
    result = run_browser_esm_json_probe(r"""
const { buildTranslationResultCardPresentation } = await import(__RESULT_MODULE_URL__);
console.log(JSON.stringify({
  completed: buildTranslationResultCardPresentation({ job: {
    job_kind: "translate", status: "completed", status_text: "Translation complete.",
    progress: { selected_index: 1, selected_total: 2 },
    result: { completed_pages: 2, metrics: { run_id: "fictional-run" } },
  } }),
  failed: buildTranslationResultCardPresentation({ job: {
    job_kind: "translate", status: "failed", status_text: "Page 2 failed",
    progress: { selected_index: 1, selected_total: 2 },
    result: { completed_pages: 1, failed_page: 2, error: "fictional_failure" },
  } }),
  explicitZero: buildTranslationResultCardPresentation({ job: {
    job_kind: "translate", status: "running",
    progress: { selected_index: 1, selected_total: 2 }, result: { completed_pages: 0 },
  } }),
}));
""", {"__RESULT_MODULE_URL__": "translation_result_presentation.js"})
    assert result["completed"]["summaryLines"] == ["Completed pages: 2", "Run ID: fictional-run"]
    assert result["completed"]["tone"] == "ok"
    assert result["failed"]["summaryLines"] == [
        "Failed page: 2",
        "Validator reason: fictional_failure",
        "Resume Translation reruns the same config against the same source.",
        "Change OCR or image settings first, then use Start Translate for a new run.",
        "Rebuild DOCX only assembles completed pages and does not complete a failed translation.",
    ]
    assert result["failed"]["tone"] == "bad"
    assert result["explicitZero"]["summaryLines"] == ["Completed pages: 0"]
