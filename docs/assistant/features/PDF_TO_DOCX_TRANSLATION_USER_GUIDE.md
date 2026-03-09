# PDF to DOCX Translation User Guide

## Use This Guide When
- You need help with the app's main workflow: translating a PDF into DOCX.
- You are supporting users who are unfamiliar with technical tooling.
- You want plain-language troubleshooting for failed or partial runs.

## Do Not Use This Guide For
- Deep implementation details for OCR/model internals.
- Database schema migration procedures.
- CI pipeline maintenance.

## For Agents: Support Interaction Contract
Response shape:
1. Plain explanation.
2. Numbered steps.
3. Canonical check against `APP_KNOWLEDGE.md`.
4. Uncertainty note when needed.

Define unavoidable technical terms in one sentence.

## Canonical Deference Rule
This user guide is not canonical architecture truth. Defer to `APP_KNOWLEDGE.md`, and treat source code as final truth on conflict.

## Quick Start (No Technical Background)
1. Open LegalPDF Translate.
2. Select your PDF.
3. Choose target language.
4. Choose output folder.
5. Click `Start Translate`.
6. Open output DOCX when run completes.

## If Warnings Appear Before The Run Starts
Two warnings matter for OCR-heavy work.

### 1. xhigh cost/time warning
If the warning says `xhigh` can multiply cost and time, choose:
1. `Switch to fixed high`

Use `Proceed` only if you intentionally want the slower, more expensive `xhigh` setting.

### 2. OCR-heavy runtime warning
If the warning says local OCR is unavailable and the document appears OCR-heavy, choose:
1. `Apply safe OCR profile`

That applies this safer profile for the current run only:
- `OCR mode = always`
- `OCR engine = api`
- `Image mode = off`
- `Workers = 1`
- `Effort policy = fixed_high`
- `Resume = off`
- `Keep intermediates = on`

It does not silently overwrite your saved defaults.

## Main Screen Layout
- Left sidebar: navigation for `Dashboard`, `New Job`, `Recent Jobs`, `Settings`, and `Profile`.
- `Job Setup`: source PDF, target language, output folder, and `Advanced Settings`.
- `Conversion Output`: progress bar, current task text, and page/image/error summary.
- Bottom action rail: `Start Translate`, `Cancel`, and `...`.
- `...` opens:
  - `Open Output Folder`
  - `Export Partial DOCX`
  - `Rebuild DOCX`
  - `Generate Run Report`
  - `View Job Log`

## Terms in Plain English
- Target language: The language you want the final document in.
- Analyze-only: A mode that inspects extraction quality without translating.
- Retry: The app making another attempt after a failed page response.
- OCR: Reading text from page images when normal extraction is poor.
- Run summary: A final report about what happened in the run.

## Multi-Window Workspaces
Use this when you want to work on more than one translation job at the same time.

### Open another workspace
1. Use `File > New Window`.
2. Or press `Ctrl+Shift+N`.
3. Or open the bottom `...` menu and choose the blank-window action there.

### How it behaves
1. Each top-level window is its own workspace.
2. The title bar shows `Workspace N` and can also add the current source filename so you can tell windows apart quickly.
3. `New Run` still resets only the current workspace.
4. A busy workspace does not block `New Window`; you can open and prepare another job while the first one is running.
5. Unstarted form edits stay local to that workspace until you explicitly start a task.

### Run jobs in parallel
1. Start the first job in one workspace.
2. Open another workspace and set up the second job there.
3. Use a different effective output target if you want both jobs to run at once.
4. The app keeps workers, dialogs, progress, and summaries local to each workspace.

### Duplicate target protection
- The app blocks a second `translate`, `analyze`, `rebuild`, or `queue` start when it would reuse the same resolved run folder as an active workspace.
- In practice, the collision usually means the same source file, target language, and output folder would produce the same `<outdir>/<pdf_stem>_<LANG>_run/`.
- When this happens, use `Focus other workspace` or change the output folder / target language before retrying.

### Gmail intake + workspaces
- The normal app launch now owns one shared Gmail intake bridge for all workspaces.
- If the last active workspace is idle and pristine, Gmail intake reuses it.
- If the last active workspace is busy or already has job context/draft state, Gmail intake opens a new blank workspace automatically.
- Gmail-related settings stay global, but another window's unstarted launch-form edits should not be overwritten by those updates.

## Analyze + OCR Advisor
Use Analyze when you want the app to inspect the PDF before spending translation time or money.

1. Open `Advanced Settings`.
2. Click `Analyze`.
3. Wait for the app to generate `analyze_report.json`.
4. If the app sees weak text extraction or layout risk, it can show an OCR Advisor recommendation.
5. The recommendation can suggest a different OCR mode and image mode.
6. In the GUI, `Apply` uses that recommendation for the next run only.
7. `Ignore` keeps your current settings and records that choice in the run metadata.

If no advisor appears, that usually means the app did not see enough evidence to recommend a change.

## Review Queue
After a run, the app can mark higher-risk pages for human review.

1. Open `Tools > Review Queue...`.
2. Check the flagged page numbers, scores, reasons, and suggested action.
3. Export the queue if you want review files outside the app.
4. The export creates both CSV and Markdown files for the same queue.

If the Review Queue opens empty, the app did not flag any pages for extra review in that run.

## Save to Job Log
After a successful run, the app can prefill the Job Log dialog using the latest run artifacts.

1. Finish a translation.
2. Open `Tools > Save to Job Log...`.
3. Confirm the prefilled values when available:
   - run ID
   - target language
   - total tokens
   - estimated API cost
   - quality risk score
   - translated output word count
4. Edit any field you want before saving.
5. Use `Open translated DOCX` if you want to reopen the current run's final or partial DOCX from inside the dialog.

The prefill helps, but you still stay in control of the saved row.

For Arabic target runs, the app inserts an Arabic review step before `Save to Job Log` opens. That dialog tries to open the DOCX in Word automatically, offers `Align Right + Save`, and watches for a real save so the app can continue automatically. If Word automation or reopening fails, the supported fallback is manual: open or keep editing the DOCX in Word, save it, then use `Continue now` if detection misses, or `Continue without changes` if you want to skip the edit.

`Words` now means translated output words. The app uses this precedence:
1. final DOCX
2. partial DOCX
3. `pages/page_*.txt`
4. `0`

`Expected total` and `Profit` are recalculated from that translated-output word count.

## Job Log window
Use `Tools > View Job Log` when you want to review or correct saved rows later.

1. Use the pen button in `Actions` to open the full `Edit Job Log Entry` form for that row.
2. Double-click a visible value when you want a quicker inline edit. That row switches to `Save` / `Cancel`, and the rest of the table waits until you finish that edit.
3. Use the trash button only when you want to remove a saved row completely. The app asks for confirmation first.
4. Historical rows can still open the full edit dialog even if the original source PDF is no longer available. In that case `Autofill from PDF header` stays disabled, but `Open translated DOCX` still works when the saved translated DOCX path still resolves.
5. Drag a column divider to resize it. Double-click the divider if you want that column auto-fitted again.
6. If the Job Log becomes wider than the window, use the horizontal scrollbar instead of squeezing the headers.
7. The app remembers your manual Job Log column widths.

## Honorarios + Gmail Drafts
If you generate a `Requerimento de Honorários`, the app can also prepare a Gmail draft to the row's `Court Email`.

### Current run
From `Save to Job Log`, the app already knows the translated DOCX from the current run. In the normal case, it should not ask you to pick that file again before creating the Gmail draft.

### Historical Job Log rows
From `Job Log`, the app now tries this order for the translated attachment:
1. stored final translated DOCX path
2. stored partial translated DOCX path
3. exact `run_id` recovery from normal output locations
4. manual `.docx` picker only if the row is legacy, stale, or ambiguous

If the app has to ask you once for a translated DOCX on a legacy row, it saves that path back into the row so the same row should not ask again next time.
You can use the pen action first if a historical row needs case/court corrections before exporting honorários or creating the Gmail draft.

## Gmail Intake Batch Replies
Use this when the source files already arrived in Gmail and you want one reply draft back in the same thread.

### Setup
1. In `Settings > Keys & Providers > Gmail Drafts (Windows)`, enable the Gmail intake bridge.
2. Copy the bridge token and port into the unpacked `extensions/gmail_intake/` extension options page.
3. Keep LegalPDF Translate running on the same Windows host as Gmail and Windows `gog`.

### Run the batch
1. Open Gmail in Edge or Chromium.
2. Expand exactly one message in the target thread.
3. Click the extension toolbar action.
4. Review the supported attachments from that exact message, select one or more files, and set the Gmail batch target language in that dialog before preparation starts.
5. Open the attachment preview when you need to inspect a file before translating it.
6. For PDFs, scroll through the preview and click `Use this page as start` if the first page should be skipped; image attachments stay fixed to page `1`.
7. `Prepare selected attachments` stages the files for the batch, and already previewed files are reused when possible instead of being downloaded again.
8. The app then translates those files one by one.
9. After each successful translation, Arabic items first pause in the Word review gate. The dialog auto-opens the DOCX in Word, offers `Align Right + Save`, and auto-continues after a detected save; if automation fails, you can save manually and use `Continue now` or `Continue without changes`.
10. The app then opens `Save to Job Log` and requires a confirmed save before continuing to the next item.
11. When all selected files are confirmed, the app can generate one honorários DOCX using the combined translated word count for the batch.
12. If that honorários step succeeds, the app creates one Gmail reply draft in the original thread with all translated DOCXs plus that single honorários DOCX.

### Batch rules
- Gmail intake is fail-closed. The batch does not start unless the extension can identify one exact open Gmail message and the app accepts the localhost handoff.
- The app fetches only the exact intake message, not the whole thread.
- The review list hides inline/signature/media junk and shows only supported source attachments from that exact message.
- PDF preview uses a lazy continuous-scroll viewer so large documents can be inspected before translation without rendering every page up front.
- If the current output folder is stale or missing, Gmail batch startup recovers automatically by preferring the current valid folder, then a valid default output folder, then `Downloads`.
- For Arabic Gmail items, the DOCX saved after the Word review gate is the reviewed artifact used downstream for that batch item.
- Every confirmed item in the batch must end with the same `case_number`, `case_entity`, `case_city`, and `court_email`.
- If any confirmed item differs, stop and split the email into separate reply batches.
- The final Gmail result is always a draft only. The app does not auto-send.
- If you accidentally choose an existing translated DOCX filename while saving honorários, the app auto-renames the honorários file instead of overwriting the translation.
- Gmail draft creation blocks duplicate attachment paths and translated artifacts that are actually honorários content.

## Queue Runs
Use queue mode when you want several PDFs to run in order.

### GUI queue flow
1. Open `Advanced Settings`.
2. Pick a queue manifest file (`.json` or `.jsonl`).
3. Click `Run Queue`.
4. Watch `Queue status` as jobs move through `pending`, `running`, `done`, `failed`, or `skipped`.
5. If you stop the queue, completed jobs stay completed and untouched jobs remain resumable.
6. Turn on `Rerun failed only` if you want the next queue run to retry only failed jobs from checkpoint state.

### CLI queue flow
Run queue mode from terminal like this:

```bash
legalpdf-translate --queue-manifest queue.jsonl --lang EN --outdir out
legalpdf-translate --queue-manifest queue.jsonl --rerun-failed-only true --lang EN --outdir out
```

Queue mode writes these sidecar files next to the manifest:
- `<manifest_stem>.queue_checkpoint.json`
- `<manifest_stem>.queue_summary.json`

## Troubleshooting
1. If the desktop app does not open from terminal, use the real GUI entrypoint: `.\.venv311\Scripts\python.exe -m legalpdf_translate.qt_app`.
2. If setup commands fail with `html.entities` or `idna` import errors, run `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`, then activate `. .\.venv311\Scripts\Activate.ps1`.
3. If output is missing pages, check if run stopped early and use resume.
4. If run is slow, lower worker count and retry.
5. If text quality is poor, run Analyze first and inspect OCR routing or advisor recommendations before translating again.
6. If terminology is inconsistent, review glossary settings and rerun affected pages.
7. If no advisor appears after Analyze, the app may have found no strong signal for a better OCR/image setting.
8. If queue mode will not start, confirm the manifest file exists and each job has valid PDF/output information.
9. If a queue was interrupted, rerun it with the same manifest; completed jobs should be skipped automatically.
10. If the Review Queue is empty, that means no pages crossed the app's current risk threshold.
11. OCR can improve difficult scans, but it still depends on source quality and cannot fully repair a badly scanned page.
12. For OCR-heavy runs, start with pages `1-2`, then `3-4`, then `5-7`.
13. If you click `Cancel and wait`, the app now waits only for the active request deadline instead of appearing indefinitely frozen.
14. If a run stops partially, open `Generate Run Report` and the run folder before retrying. The stop dialog now includes suspected cause, halt reason, and request timing details when available.
15. If a historical honorários Gmail draft still asks you to pick the translated DOCX, that means the row has no stored artifact path and exact `run_id` recovery did not find one unique valid match. After one successful manual selection, the row should be healed and stop asking again.
16. If Gmail intake says the app is not listening, confirm the bridge is enabled in Settings and the app is still running on Windows with the same port shown in the extension.
17. If the app shows `Gmail intake bridge unavailable`, treat that as a port/process conflict first. The listener on `127.0.0.1:<port>` must belong to `python.exe -m legalpdf_translate.qt_app`, not `pytest`.
18. If Gmail intake says the token is invalid, re-copy the token from Settings into the extension options page.
19. If Gmail intake cannot identify the open Gmail message, collapse extra messages and leave exactly one expanded message visible.
20. If the Gmail review dialog shows no files, the email likely had no supported attachments or Gmail exposed only inline/signature/media parts.
21. If you cancel `Save to Job Log` during a Gmail batch, the remaining attachments stop by design.
22. If the Gmail batch warns that case/court metadata differ, split that email into separate batches instead of forcing one reply.
23. If you skip or fail honorários generation at the end of a Gmail batch, the app does not create the Gmail reply draft in V1.
24. A WSL-only `gog` smoke is not enough for final Gmail intake validation. The signed-in browser, Windows app, and Windows `gog` must be checked on the same host.
25. If translation itself fails, inspect `run_report.md` and `run_summary.json` first. Arabic failures now include `validator_defect_reason`, `ar_violation_kind`, and sample snippets.
26. If translation succeeded but finalization/draft behavior is wrong, inspect `_gmail_batch_sessions/<session_id>/gmail_batch_session.json` under the effective output folder before debugging Gmail transport or attachments again.
27. If the Arabic review dialog says Word automation failed, stay on Windows: use `Open in Word` or the default Windows handler, save manually, then use `Continue now` if save detection misses. WSL-only validation is not enough for this path.
28. If a second window is blocked before start, read the run-folder warning literally: another active workspace already owns that exact output target. Change output folder or language, or wait for the owner workspace to finish.

## Cost Guardrails (CLI)
Use this when you run from terminal and want cost protection.

1. Set a budget cap:
   - `legalpdf-translate --pdf <file> --lang EN --outdir <dir> --budget-cap-usd 3.50`
2. Choose behavior if estimate exceeds cap:
   - `--budget-on-exceed warn` (default): shows warning and continues.
   - `--budget-on-exceed block`: stops before page processing.
3. Optional profile label:
   - `--cost-profile-id default_local`
4. Check the run report and `run_summary.json` for:
   - `budget_decision`, `budget_decision_reason`, `budget_pre_run`, `budget_post_run`.

## Canonical Checkpoints for Agents
- Runtime behavior: `APP_KNOWLEDGE.md`
- Workflow specifics: `docs/assistant/workflows/TRANSLATION_WORKFLOW.md`
- Data/persistence behavior: `docs/assistant/workflows/PERSISTENCE_DATA_WORKFLOW.md`
