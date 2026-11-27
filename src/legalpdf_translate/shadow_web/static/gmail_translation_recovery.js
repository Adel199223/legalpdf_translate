// Recovery must identify a run, not merely a filename or a reused attachment ID.
export function matchesGmailTranslation(job, launch) {
  const config = job?.config;
  const expected = launch?.gmail_batch_context;
  const actual = config?.gmail_batch_context;
  if (!config || !expected || !actual) return false;
  for (const key of ["session_id", "message_id", "thread_id", "attachment_id"]) {
    const value = String(expected[key] || "").trim();
    if (!value || value !== String(actual[key] || "").trim()) return false;
  }
  const language = String(launch.target_lang || expected.selected_target_lang || "").trim().toUpperCase();
  const start = Number(launch.start_page || expected.selected_start_page);
  return Boolean(language && start > 0
    && language === String(config.target_lang || actual.selected_target_lang || "").trim().toUpperCase()
    && start === Number(config.start_page || actual.selected_start_page)
    && String(launch.source_path || "").trim()
    && String(launch.source_path).trim() === String(config.source_path || "").trim());
}

export async function fetchGmailTranslationForRecovery(launch, fetchJson, state) {
  if (!launch?.gmail_batch_context) throw new Error("The current Gmail attachment is unavailable. Reopen the Gmail session.");
  const history = await fetchJson("/api/translation/history", state);
  const jobs = history.normalized_payload?.active_jobs || [];
  // The server lists newest first, including the most recent explicit resume.
  const match = jobs.find((job) => job.job_kind === "translate" && matchesGmailTranslation(job, launch));
  if (!match) throw new Error("The retained run for this Gmail attachment is unavailable. Recovery did not prepare a new run.");
  const response = await fetchJson(`/api/translation/jobs/${encodeURIComponent(match.job_id)}`, state);
  const job = response.normalized_payload?.job;
  if (!job || job.job_id !== match.job_id || !matchesGmailTranslation(job, launch)) {
    throw new Error("The retained run no longer matches this Gmail attachment. Reopen the Gmail session.");
  }
  return job;
}
