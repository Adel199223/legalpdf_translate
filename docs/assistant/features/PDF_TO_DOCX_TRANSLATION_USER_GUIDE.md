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
1. Open the LegalPDF browser app in `live` mode.
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
- Left sidebar: the calm first-level buttons are `New Job`, `Recent Jobs`, and sometimes `Gmail`. Less-common pages stay under `More`.
- `Dashboard`, `Settings`, `Profile`, `Power Tools`, and `Extension Lab` are still available, but they now behave as secondary/operator surfaces rather than the normal first screen.
- `New Job`: the default daily shell. It stays focused on source PDF, target language, output folder, bounded advanced settings, run status, and the bottom action rail.
- `Gmail`: a dedicated compact handoff screen for exact-message review and attachment selection. Deeper Gmail session/finalization work stays in same-tab drawers instead of appearing inline on the main shell.
- `Recent Jobs`: the main secondary production page, with the latest saved rows visible first and deeper translation/interpretation history kept behind collapsible sections.
- `Run Status`: progress bar, current task text, and page/image/error summary.
- Bottom action rail: `Start Translate`, `Cancel`, and `...`.
- `Settings > Appearance` now gives you two real live themes:
  - `dark_futuristic` for the brighter raised cyan-glass look
  - `dark_simple` for a quieter darker look with the same layout and controls
- `live` mode is the real-work browser surface. `shadow` mode is the isolated test copy that keeps separate settings, job log, and outputs.
- The browser app is now the preferred daily-use surface. The Qt shell remains a supported fallback, not the default starting point.
- `...` opens:
  - `Analyze Only`
  - `Resume Translation`
  - `Rebuild DOCX`

## Terms in Plain English
- Target language: The language you want the final document in.
- Analyze-only: A mode that inspects extraction quality without translating.
- Retry: The app making another attempt after a failed page response.
- OCR: Reading text from page images when normal extraction is poor.
- Run summary: A final report about what happened in the run.
- Live mode: The real browser-app path that uses your real settings, job log, outputs, and Gmail workflow.
- Shadow mode: The isolated browser-app path used for development, testing, or safe experiments.

## Multi-Window Workspaces
Use this when you want to work on more than one translation job at the same time.

### Open another workspace
1. Open another browser tab or browser window with a different workspace URL.
2. Or duplicate the current browser app tab and switch the `workspace=` value.
3. Use the Qt `New Window` path only if you are intentionally working in the fallback desktop shell.

### How it behaves
1. Each browser workspace is independent.
2. The current workspace stays visible in the URL, so separate tabs are easier to tell apart.
3. `New Run` still resets only the current workspace.
4. A busy workspace does not block another browser tab; you can open and prepare another job while the first one is running.
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
- The browser app live server now owns the normal Gmail intake bridge for all live browser workspaces when the bridge is enabled.
- The browser extension opens or focuses the fixed live browser workspace `gmail-intake`.
- Gmail-related settings stay global in `live` mode, but `shadow` mode stays isolated on purpose and does not own the real Gmail bridge.

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
6. On smaller screens, scroll inside the dialog instead of expecting the whole form to stay visible at once.
7. `Run Metrics` and `Amounts` start collapsed by default so the main case and service fields stay easier to reach first.

The prefill helps, but you still stay in control of the saved row.

For Arabic target runs, the app inserts an Arabic review step before `Save to Job Log` opens. That dialog tries to open the DOCX in Word automatically, offers `Align Right + Save`, and watches for a real save so the app can continue automatically. If Word automation or reopening fails, the supported fallback is manual: open or keep editing the DOCX in Word, save it, then use `Continue now` if detection misses, or `Continue without changes` if you want to skip the edit.

`Words` now means translated output words. The app uses this precedence:
1. final DOCX
2. partial DOCX
3. `pages/page_*.txt`
4. `0`

`Expected total` and `Profit` are recalculated from that translated-output word count.

Interpretation rows use the same Job Log window but a different editing mode:
- translation-only fields are hidden instead of shown as inactive
- the main visible date becomes the service date
- `Autofill from PDF header` can fall back to a manual PDF picker
- the visible distance input is one one-way KM field tied to `service_city`
- the saved one-way distance is reused automatically for that service city when the selected profile already has one recorded

## Job Log window
Use `Tools > View Job Log` when you want to review or correct saved rows later.

1. Use the pen button in `Actions` to open the full `Edit Job Log Entry` form for that row. That form now scrolls internally on smaller screens instead of opening off-screen.
2. Double-click a visible value when you want a quicker inline edit. That row switches to `Save` / `Cancel`, and the rest of the table waits until you finish that edit.
3. Use the trash button only when you want to remove a saved row completely. The app asks for confirmation first.
4. Historical rows can still open the full edit dialog even if the original source PDF is no longer available. Translation rows disable `Autofill from PDF header` in that case, while interpretation rows can still use that action through a manual PDF picker fallback. `Open translated DOCX` still works when the saved translated DOCX path still resolves.
5. Drag a column divider to resize it. Double-click the divider if you want that column auto-fitted again.
6. If the Job Log becomes wider than the window, use the horizontal scrollbar instead of squeezing the headers.
7. The app remembers your manual Job Log column widths.
8. In the full edit dialog, fixed-choice fields such as `Job type`, `Lang`, and saved entity/city lists are picked from dropdowns instead of being typed directly. Use the small `+` button when you need a new saved entity or city.
9. Editable dates still accept `YYYY-MM-DD`, but the app now also gives you a calendar popup. The calendar starts on Monday.

## Interpretation Honorarios
Use this flow when you need a `Requerimento de Honorários` for interpreting work rather than a translated document.

### Start the row
1. Use either `Tools > New Interpretation Honorários...` for the direct save-first path, or open `Tools > View Job Log`.
2. In `Job Log`, use `Add...` and choose one of these interpretation entry paths:
   - `Blank/manual interpretation entry`
   - `From notification PDF...`
   - `From photo/screenshot...`
3. Confirm the case, service, and date fields before saving the row.
4. If a photo or screenshot import did not contain an explicit service entity or city, the form still opens and lets you fill those fields in manually.

### Service city and distance rules
1. `Service same as Case` starts enabled for interpretation rows unless the imported data already proves a different service location.
2. While that option stays on, the service entity and service city mirror the case values, so the `SERVICE` section can stay collapsed until you actually need to change it.
3. The service city is the travel-distance city for interpretation honorários.
4. The visible KM field is the one-way distance only.
5. When the current profile already has a saved distance for that service city, the app fills it in automatically.
6. If you type a new one-way distance and save the row, the app remembers that value for that service city in the current profile.

### Generate the document
1. If you used `Tools > New Interpretation Honorários...`, save the row first and the export dialog opens automatically. Otherwise, open the saved interpretation row or keep the edit dialog open.
2. Click `Gerar Requerimento de Honorários...` when you are using the Job Log path.
3. Use the profile selector if needed.
4. The interpretation export dialog keeps the main case/profile controls visible first and groups secondary detail into `SERVICE`, `TEXT`, and `RECIPIENT` sections. `RECIPIENT` usually stays collapsed until you need to override the case-derived addressee.
5. On smaller screens, scroll inside the honorários dialog. The action buttons stay anchored at the bottom.
6. The export saves the honorários DOCX first and then attempts a sibling PDF with the same basename.
7. `Include transport/distance sentence in honorários text` starts enabled. Leave it on in the normal case, and turn it off only when the court is handling transport separately and that sentence should be omitted.
8. The addressee auto-completes the case city for generic court entities. The body keeps the saved `service_date`, but the footer date before the signature always uses the day you generate the document.
9. If automatic PDF export fails, the dialog keeps the saved DOCX usable locally and offers one recovery flow: retry PDF export, choose an existing PDF, open the DOCX/folder, or continue local-only.
10. Manual/local interpretation exports can offer a fresh Gmail draft when the saved row has `Court Email`, Gmail draft prerequisites are ready, and the honorários PDF was generated successfully.

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

This Gmail-draft branch always applies to translation honorários. Interpretation honorários can also produce Gmail drafts:
- manual/local interpretation exports create a fresh non-threaded draft and attach the honorários PDF only
- Gmail-intake interpretation notice exports create a threaded reply draft and attach the honorários PDF only

## Gmail Intake Batch Replies
Use this when the source files already arrived in Gmail and you want one reply draft back in the same thread.

### Setup
1. In `Settings > Keys & Providers > Gmail Drafts (Windows)`, enable the Gmail intake bridge.
2. Use the browser app in `live` mode for real Gmail work. `shadow` mode is only for isolated testing and diagnostics.
3. Normal use no longer requires copying the bridge token and port into the unpacked extension options page. Use the options page or `Extension Lab` for diagnostics only.
4. Keep LegalPDF Translate and Gmail on the same Windows host as Windows `gog`.

### Run the batch
1. Open Gmail in Edge or Chromium.
2. Expand exactly one message in the target thread.
3. Click the extension toolbar action. If the browser app is closed but the live Gmail bridge is configured, the native host can auto-start the current checkout and continue that same click.
4. Choose the Gmail intake mode in the review dialog:
   - `Translation` for the existing translation batch flow
   - `Interpretation notice` for one selected court-notice attachment that should not be translated
5. The review dialog starts with a compact summary banner. Use its info button when you need the sender, Gmail account, or output-folder details.
6. In `Translation` mode, review the supported attachments from that exact message, select one or more files, and set the Gmail batch target language before preparation starts.
7. In `Interpretation notice` mode, select exactly one supported PDF or image attachment. Translation-only controls stay hidden in that mode.
8. Open the attachment preview when you need to inspect a file before proceeding.
9. For translation PDFs, page `1` is the default. Scroll through the preview and click `Start from this page` only if translation should begin later. Interpretation notice imports do not use start-page semantics.
10. `Prepare selected attachments` stages the files, and already previewed files are reused when possible instead of being downloaded again.
11. Translation mode then translates the selected files one by one.
12. Interpretation-notice mode downloads the original notice, extracts the case and service metadata, opens the interpretation `Save to Job Log` confirmation, then opens interpretation honorários export.
13. After each successful translation, Arabic items first pause in the Word review gate. The dialog auto-opens the DOCX in Word, offers `Align Right + Save`, and auto-continues after a detected save; if automation fails, you can save manually and use `Continue now` or `Continue without changes`.
14. Translation mode then opens `Save to Job Log` and requires a confirmed save before continuing to the next item.
15. When all selected translation files are confirmed, the app can generate one honorários export using the combined translated word count for the batch.
16. The honorários export saves the DOCX first and then attempts a sibling PDF with the same basename.
17. If the translation honorários step succeeds and the PDF exists, the app creates one Gmail reply draft in the original thread with all translated DOCXs plus that single honorários PDF.
18. If the interpretation honorários step succeeds and the PDF exists, the app creates one Gmail reply draft in the original thread with the generated honorários PDF only.

### Batch rules
- Gmail intake is fail-closed. The batch does not start unless the extension can identify one exact open Gmail message and the app accepts the localhost handoff.
- In normal browser-first use, the live bridge owner should be the LegalPDF browser app server. Qt ownership is fallback/coexistence only.
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
- Interpretation honorários keep the saved `service_date` in the body, but the footer date before the signature always uses the day you generate the document.

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
1. Easiest manual launch on Windows: double-click `LegalPDF Browser App (Live).cmd` on the Desktop if it exists, or run `.\.venv311\Scripts\python.exe -m legalpdf_translate.shadow_web.server --open`.
2. If you want the live browser app without keeping a terminal attached, run `.\.venv311\Scripts\python.exe tooling/launch_browser_app_live_detached.py`.
3. If setup commands fail with `html.entities` or `idna` import errors, run `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`, then activate `. .\.venv311\Scripts\Activate.ps1`.
4. If output is missing pages, check if run stopped early and use resume.
5. If run is slow, lower worker count and retry.
6. If text quality is poor, run Analyze first and inspect OCR routing or advisor recommendations before translating again.
7. If terminology is inconsistent, review glossary settings and rerun affected pages. Recurring Portuguese court/prosecution headers are now matched as phrase-level institutional entries, so if a header is still wrong, capture the exact header lines instead of only the case-specific body text.
8. If no advisor appears after Analyze, the app may have found no strong signal for a better OCR/image setting.
9. If queue mode will not start, confirm the manifest file exists and each job has valid PDF/output information.
10. If a queue was interrupted, rerun it with the same manifest; completed jobs should be skipped automatically.
11. If the Review Queue is empty, that means no pages crossed the app's current risk threshold.
12. OCR can improve difficult scans, but it still depends on source quality and cannot fully repair a badly scanned page.
13. For OCR-heavy runs, start with pages `1-2`, then `3-4`, then `5-7`.
14. If you click `Cancel and wait`, the app now waits only for the active request deadline instead of appearing indefinitely frozen.
15. If a run stops partially, open `Generate Run Report` and the run folder before retrying. The stop dialog now includes suspected cause, halt reason, and request timing details when available.
16. If a historical honorários Gmail draft still asks you to pick the translated DOCX, that means the row has no stored artifact path and exact `run_id` recovery did not find one unique valid match. After one successful manual selection, the row should be healed and stop asking again.
17. If `Autofill from PDF header` is available on an interpretation row without an attached source PDF, that is expected. The app now asks you to choose the PDF manually for that autofill pass.
18. If an interpretation row shows the wrong travel distance, check the `Service city` first. The saved KM value is keyed to that service city.
19. If Gmail intake says the app is not listening, confirm the bridge is enabled in `live` mode. A normal toolbar click can auto-start the browser app, so repeated listener errors usually mean a bridge or launch-target problem instead of “app closed”.
20. If the app shows `Gmail intake bridge unavailable`, treat that as a port/process conflict first. The listener on `127.0.0.1:<port>` should normally belong to the LegalPDF browser app live server, not `pytest`.
21. If Gmail intake says auto-launch is unavailable from this checkout, refresh the extension diagnostics and verify the native host can still see this repo worktree.
22. If Gmail intake says the token is invalid, treat that as a Settings/native-host mismatch and refresh diagnostics instead of editing the extension options page manually.
23. If Gmail intake cannot identify the open Gmail message, collapse extra messages and leave exactly one expanded message visible.
24. If the Gmail review dialog shows no files, the email likely had no supported attachments or Gmail exposed only inline/signature/media parts.
25. If you cancel `Save to Job Log` during a Gmail batch, the remaining attachments stop by design.
26. If the Gmail batch warns that case/court metadata differ, split that email into separate batches instead of forcing one reply.
27. If you skip or fail honorários generation at the end of a Gmail batch, the app does not create the Gmail reply draft in V1.
28. A WSL-only `gog` smoke is not enough for final Gmail intake validation. The signed-in browser, Windows app, and Windows `gog` must be checked on the same host.
29. If translation itself fails, inspect `run_report.md` and `run_summary.json` first. Arabic failures now include `validator_defect_reason`, `ar_violation_kind`, and sample snippets.
30. If translation succeeded but finalization/draft behavior is wrong, inspect `_gmail_batch_sessions/<session_id>/gmail_batch_session.json` under the effective output folder before debugging Gmail transport or attachments again.
31. If the Arabic review dialog says Word automation failed, stay on Windows: use `Open in Word` or the default Windows handler, save manually, then use `Continue now` if save detection misses. WSL-only validation is not enough for this path.
32. If a second window is blocked before start, read the run-folder warning literally: another active workspace already owns that exact output target. Change output folder or language, or wait for the owner workspace to finish.

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
