# APP User Guide

## Use This Guide When
- You need a plain-language explanation of what the app does.
- You are helping a non-coder run a translation safely.
- You need support steps for common run/setup questions.

## Do Not Use This Guide For
- Low-level architecture decisions.
- Source-code debugging details.
- CI/governance policy enforcement.

## For Agents: Support Interaction Contract
Use this sequence:
1. Plain explanation in everyday language.
2. Numbered action steps.
3. Canonical check against technical docs.
4. Uncertainty note if evidence is incomplete.

## Canonical Deference Rule
This guide is explanatory only. For architecture/status truth, defer to `APP_KNOWLEDGE.md`. If docs conflict with code, source code is final truth.

## Quick Start (No Technical Background)
1. Open the browser app in `live` mode. It opens to `New Job` by default.
2. Stay on `New Job` for normal translation work, or use the dedicated Gmail handoff screen when starting from Gmail.
3. Choose your PDF file or start from Gmail intake.
4. Pick output language (`EN`, `FR`, or `AR`) when you are translating.
5. Start the job and review the generated DOCX or honorários output when it finishes.

## What You See On Screen
- Left sidebar: the normal first-level buttons are `New Job`, `Recent Jobs`, and sometimes `Gmail`. Less-common areas stay under `More`.
- `New Job`: the main beginner-first work area. Translation is the default view, and `Interpretation` is available through the in-page task switch.
- `Gmail`: a dedicated Gmail handoff screen reached by same-tab redirect from Gmail. Exact-message review and attachment choice are shown first; `Return to Gmail` restores the original message, and deeper session/finalization work opens later in same-tab drawers.
- `More`: keeps `Dashboard`, `Settings`, `Profile`, `Power Tools`, and `Extension Lab` reachable without making the everyday shell feel crowded.
- `Dashboard`: an operator/status page under `More` that shows runtime mode, OCR, Word PDF export readiness, browser automation, Gmail bridge state, and other machine-level checks when you need machine-level visibility.
- `Recent Jobs`: the main secondary production page. It shows the latest saved rows first and keeps deeper translation and interpretation history tucked into collapsible sections until you ask for them.
- `Settings`: a bounded operator sheet for provider keys, Gmail bridge options, OCR checks, translation-auth tests, native-host checks, Word PDF export canary checks, and other machine-level settings. The screen is grouped so defaults stay visible first and lower-frequency diagnostics stay tucked away.
- `Profile`: your saved person/company details, addresses, distance defaults, and primary profile choice. The main page stays focused on the list and primary profile, while the full editor opens in a drawer.
- `Power Tools`: a bounded operator stack for glossary, calibration, and diagnostics workflows.
- `Extension Lab`: the browser-side diagnostics/simulator surface for Gmail handoff checks. The real browser extension stays canonical, and this lab remains an operator page rather than part of the normal daily flow.
- Workspace: the browser app still uses workspaces, but they are shown through the current browser tab or window instead of separate Qt windows by default.
- Theme: in `Settings > Appearance`, `dark_futuristic` is the brighter elevated default and `dark_simple` is the quieter darker variant. The change applies live without restarting the app.
- The browser app shell, Settings, Gmail review/preview, Save/Edit Job Log, and honorários export now share the same raised translucent panel style so the interface feels like one connected product surface.
- The Qt desktop shell still exists as a supported fallback, but it is no longer the normal day-to-day interface.

## Terms in Plain English
- PDF: The document you want translated.
- DOCX: The Word file created by the app.
- Run folder: A folder containing translation progress and diagnostics files.
- Resume: Continue from where a previous run stopped.
- Glossary: A preferred term list that keeps wording consistent.
- Budget cap: A spend limit you can set for a CLI run.
- Budget decision: What the app does when estimated cost is above cap (`warn` continues, `block` stops early).
- Review Queue: A short list of pages the app thinks deserve a human check.
- OCR Advisor: A recommendation shown after Analyze that suggests safer OCR or image settings.
- Safe OCR profile: A temporary one-click set of safer run settings for a scanned or OCR-heavy document.
- Queue Manifest: A small file that tells the app to run several PDFs one after another.
- Job Log: The place where you save finished work details like run ID, tokens, and estimated API cost.
- Live mode: the real browser app data path. It uses your real settings, job log, outputs, and Gmail workflow.
- Shadow mode: an isolated test copy of the browser app. It is useful for development and safe experiments, but it is not the normal place for real work.
- Extension Lab: the browser page that helps you verify Gmail bridge ownership, launch behavior, and handoff diagnostics.

## Common Tasks
1. Analyze first when a PDF looks messy or scanned, then decide whether to apply the OCR Advisor suggestion for the next run.
2. If a warning says `xhigh` can multiply cost and time, choose `Switch to fixed high` unless you intentionally want the slower, more expensive option.
3. If an OCR-heavy warning appears for a scanned document, choose `Apply safe OCR profile` to fix the current run without changing your saved defaults.
4. After a run finishes, open the Review Queue if pages were flagged for manual checking.
5. For Arabic runs, review the DOCX in Word when the app pauses for that step, then save it so the app can continue automatically.
6. Save the finished run to the Job Log so the case and cost details are stored together.
7. Use `Generate Run Report` from the translation completion area when you want the full Markdown run report next to the run folder. The app now downloads it immediately once and keeps `Download Run Report` available afterward. For Gmail-started runs, that report also keeps the `Gmail Intake / Batch Context` section and clearly labels `run tokens` versus `billed total (includes reasoning)`.
8. Use a queue manifest when you want the app to process several PDFs in sequence without starting each one manually.
9. Use Gmail intake when you want to start from one open Gmail message instead of choosing files manually.
10. Open another browser tab or browser window with a different workspace URL when you want a second independent workspace for another job.
11. After generating a `Requerimento de Honorários`, let the app create a Gmail draft when that flow supports it and `Court Email` is available.
12. Use the Job Log when you need an interpretation-only honorários document without a translation run, or start from Gmail intake when the court notice already arrived by email.

## Using the Job Log
1. Open `Tools > View Job Log` when you want to check or fix something you already saved.
2. Use the small pen button for the full edit form.
3. Double-click a visible row value for a quick inline change, then use `Save` or `Cancel` on that row.
4. Use the trash button only when you want to remove that saved row completely. The app asks before deleting it.
5. If the original PDF is gone, you can still edit the saved row.
6. Drag column borders wider when names or values are cut off. If the table gets wider than the window, scroll sideways.
7. The app remembers the widths you set for Job Log columns.
8. In the Save to Job Log form, scroll inside the window on smaller screens. The lower detail sections start collapsed so the main fields stay easier to reach.
9. Interpretation rows open a cleaner form: translation-only fields are hidden, the main date is the service date, and the visible KM field is one-way only.
10. For interpretation work, `Service same as Case` is usually the default. The service city is treated as the travel city unless you change it manually.
11. If a saved one-way distance already exists for that service city in the selected profile, the app fills it in automatically.
12. `Autofill from PDF header` also works for interpretation edit rows that were not created from a saved PDF. The app asks you to choose the PDF file when needed.
13. Fixed-choice fields such as `Job type`, `Lang`, and saved entity/city lists are chosen from dropdowns instead of typed manually. Use the small `+` button when you need a new saved entity or city.
14. Date fields can still be typed as `YYYY-MM-DD`, but you can now also pick them from a calendar popup. The calendar starts on Monday.

## Interpretation Honorarios
1. Use `Tools > New Interpretation Honorários...` for the direct save-first path, or open `Tools > View Job Log`.
2. In `Job Log`, use `Add...` and choose the interpretation path you need:
   - `Blank/manual interpretation entry`
   - `From notification PDF...`
   - `From photo/screenshot...`
   - `Choose from Google Photos` from the `New Job > Interpretation` panel when you want to import one selected Google Photos image
3. Review the case and service details before saving. Interpretation mode focuses on service date, service location, and distance instead of translation metrics.
4. If a photo, screenshot, or Google Photos import did not contain an explicit service entity or city, the form still opens normally and lets you fill those fields in manually.
5. Keep `Service same as Case` on when the hearing/service happened in the same place as the case. Turn it off only when the service entity or city is different.
6. The visible KM field is the one-way distance only. The app reuses the saved value for that service city when one already exists.
7. If you enter a new one-way distance for a service city and save the row, the app remembers it for future interpretation rows under the current profile.
8. If you used `Tools > New Interpretation Honorários...`, the export dialog opens right after save. Otherwise, use `Gerar Requerimento de Honorários...` from that row when you are ready.
9. The export dialog keeps the main case/profile fields visible first and tucks extra detail into `SERVICE`, `TEXT`, and `RECIPIENT` sections. `RECIPIENT` usually stays collapsed until you need to override the case-derived addressee.
10. The export saves the DOCX first and then attempts a sibling PDF with the same basename.
11. Leave `Include transport/distance sentence in honorários text` on in the normal case. Turn it off only when transport is being handled separately and you want that sentence omitted from the document.
12. The body still uses the service day, but the footer date before your signature always uses the day you generate the document.
13. If automatic PDF generation fails, the dialog keeps the DOCX, stays responsive, and lets you retry, choose an existing PDF, or continue local-only.
14. Manual/local interpretation exports can create a fresh Gmail draft when `Court Email`, Gmail draft prerequisites, and the honorários PDF are all available. Those drafts attach the honorários PDF only.

### Google Photos Interpretation Import
1. Use this only from `New Job > Interpretation`; it is not part of the Translation workflow.
2. Click `Connect Google Photos` if the app is not already connected.
3. If no Google sign-in tab opens, use the visible `Open Google sign-in` fallback.
4. After connection, click `Choose from Google Photos`.
5. If no Google Photos tab opens, use the visible `Open Google Photos Picker` fallback.
6. Select exactly one non-private photo first and finish the Google Photos selection flow.
7. Return to LegalPDF and wait for `Review Case Details`.
8. Treat Google Photos `createTime` and any downloaded EXIF date as provenance only. Confirm `service_date`, `service_city`, and `case_city` from OCR/document text or manual review before generating any honorários document.

## Multiple Windows
1. Open another browser tab or browser window with a different workspace URL when you want another independent workspace.
2. Each workspace stays separate. Starting, stopping, or resetting one workspace does not reset the others.
3. You can run different jobs in parallel as long as they do not resolve to the same run folder.
4. If the app says a translation is already active in another workspace, both workspaces would write to the same output run folder. Change the output folder or target language, or wait for the other workspace to finish.
5. Unstarted edits stay in that workspace only. A new blank workspace should not copy draft file/language/output changes from another one.
6. Gmail intake uses the fixed live workspace `gmail-intake` when the browser extension hands a message into the app.

## Gmail Intake Batch Replies
1. In `Settings > Keys & Providers > Gmail Drafts (Windows)`, turn on the Gmail intake bridge.
2. Load `extensions/gmail_intake/` as an unpacked extension in Edge or Chrome.
3. Normal use no longer requires manually copying the bridge token and port into the extension options page. Use that page only for diagnostics.
4. Open Gmail in that same Windows browser and expand exactly one message.
5. Click the extension toolbar button once. If the browser app is closed but the live Gmail bridge is configured, the native host can auto-start the canonical `main` checkout without opening CMD windows, and the same Gmail tab redirects into LegalPDF after preparation. If the handoff fails or is rejected before redirect, Gmail stays on the current page and shows the error banner there. If the browser says live Gmail is running from a noncanonical build, normal Gmail work stays blocked until `Restart from Canonical Main` succeeds.
6. The same browser tab opens the fixed live workspace `gmail-intake` and asks you to choose the Gmail intake mode. Use `Return to Gmail` when you want to go back to the original Gmail message:
   - `Translation` keeps the existing multi-attachment translation batch behavior and target-language review.
   - `Interpretation notice` is for one selected court-notice attachment that should not be translated.
7. The Gmail page starts compactly. The first screen shows the message summary, supported attachments, workflow choice, target language when needed, and one main continue action. Use the small info button only when you need sender, Gmail account, bridge owner, or output-folder details.
8. In `Translation` mode, choose which files to translate and correct the target language if needed.
9. In `Interpretation notice` mode, select exactly one supported PDF or image attachment. The app hides translation-only review inputs in that mode.
10. Use `Preview selected attachment` when you need to inspect a file before preparing it.
11. In preview, page `1` is the default. Scroll the PDF and click `Start from this page` only for translation batches when the file should begin later, such as after a cover sheet.
12. When you click `Prepare selected`, already previewed files are reused when possible instead of being downloaded again.
13. Translation mode now keeps the Gmail and translation flow calmer than before: `Prepare selected` opens `New Job` in a prepared state, shows the seeded attachment/settings summary, and waits for you to click `Start Translate`. Fresh Gmail prepares start as new runs by default with `Resume` off and `Keep intermediates` on unless you intentionally change them before starting.
14. Interpretation-notice mode stages the original notice, then moves into one compact `Current Interpretation Step` view plus a bounded `Review Interpretation` drawer instead of a long mixed admin page.
15. If the interpretation city or distance is invalid, the browser now blocks finalization and asks you to correct the city/distance before saving, exporting, or finalizing the Gmail reply.
16. Arabic translation files pause in a Word review step before `Save to Job Log`. The app opens the durable DOCX in Word for you; align or edit it manually, save it, and the app continues automatically. If save detection misses, use `Continue now` after saving.
17. If you want to rerun the same current Gmail attachment without closing Edge or resetting the whole Gmail workspace, use `Redo Current Attachment`. It reloads the same attachment into translation, keeps prior files on disk, reseeds the prepared run settings, and waits for you to start the rerun manually. If you instead click the extension again for a new Gmail handoff, the new handoff should win by default. Use `Open Last Finalization Result` only when you intentionally want the previous finalized batch details.
18. Translation mode requires each file to be saved before the next one begins. If you cancel that dialog, the remaining files stop on purpose.
19. If a translation file fails, the current attachment moves into a recovery state. `Resume Translation` reruns the same config; if you want different OCR or image settings, start a fresh translation from the current form instead.
20. If one translation file resolves to a different case or court, stop and split the work into separate batches.
21. After the last translation file, or after the interpretation honorários export generates its PDF, the app can create one Gmail reply draft in the original thread.
22. Translation Gmail drafts attach the translated DOCX files plus the generated honorários PDF.
23. Interpretation Gmail drafts attach only the generated honorários PDF. They do not attach the original notice or any translated DOCX.
24. When the original Gmail message explicitly names a reply email, the app now prefers that reply address for the Gmail draft instead of a weaker derived guess.
25. The app creates a draft only. It does not send the email automatically.
26. If preview or `Prepare selected` fails before translation starts, the Gmail diagnostics area now keeps your selection and offers `Generate Failure Report`.
27. If `Finalize Gmail Batch Reply` is blocked, treat that as a Word PDF export readiness issue first. The app now checks the real export path before finalization and offers `Generate Finalization Report` whenever the last-step Gmail finalization state is blocked or completed, including a successful draft-ready finish.

## If Gmail Intake Stops Early
1. If the page says the app is not listening, confirm the bridge is enabled in `Settings` and that you are using the browser app in `live` mode. A normal toolbar click can auto-start the app, so a manual launch should only be needed after an auto-start failure.
2. If the dashboard or Extension Lab says `Gmail intake bridge unavailable`, another process may already be using the bridge port or the live browser server may not own it yet.
3. If Gmail shows `accepted` but the browser app stays idle, check that the listener on `127.0.0.1:<port>` belongs to the LegalPDF browser app live server and not to `pytest` or another stray process.
4. If Gmail says the handoff is already in progress, that should only mean the same tab is still redirecting or hydrating for the current click. If the workspace is not visible or the message repeats after a retry, treat it as stale state and refresh diagnostics instead of clicking repeatedly.
5. If the page says the browser app is running from a noncanonical build, choose `Restart from Canonical Main`. Preview and `Prepare selected` stay blocked for normal live Gmail work until the canonical runtime is restored.
6. If the extension says the native host is unavailable, reload the extension or open the extension options page and refresh diagnostics. Normal use should not require manually copying bridge tokens.
7. If the page says auto-launch is unavailable from this checkout, open the extension options page and refresh diagnostics.
8. If the page says the token is invalid, treat that as a Settings/native-host mismatch and refresh diagnostics instead of editing the extension options page manually.
9. If the page says the message is ambiguous, collapse extra Gmail messages and leave only one expanded.
10. If the app shows no supported attachments, that email likely contains only inline or unsupported files.
11. If the batch stops after Save to Job Log, that is expected when you cancel the dialog or when the case/court details no longer match.
12. If you skip or fail honorários generation at the end of the translation batch, or cancel/fail the interpretation honorários export after Gmail intake, the app does not create the Gmail reply draft.
13. The extension does not create its own report file. Use the browser banner for handoff failures, then the app/run reports for everything after intake.
14. If the honorários PDF cannot be generated, the export still keeps the local DOCX but Gmail draft creation stays blocked for that export.
15. If the same tab reaches LegalPDF but shows `Pending load`, unavailable message/thread IDs, or no attachment-ready text, treat the click diagnostics as the source of truth: `bridge_context_posted` should be `true`, `source_gmail_url` should be present, and the native-host path should be the EXE target rather than the old `.cmd` wrapper.
16. If Gmail/browser preparation fails before a run exists, use `Generate Failure Report` from the Gmail diagnostics area instead of searching for a run report that does not exist yet. That report now includes the raw browser PDF worker/module failure details.
17. If Gmail finalization is blocked or completes and you still want a full last-step artifact, use `Generate Finalization Report` from the finalization drawer. That report now stays available for blocked states and completed states, including successful draft creation.
18. If the current Gmail attachment was already run and you want to do it again from the same live workspace, use `Redo Current Attachment` instead of `Reset Gmail Workspace`. `Redo` keeps the Gmail batch session and only resets the translation side for that attachment.
19. If `Generate Run Report` appears to do nothing, it should now download the detailed `run_report.md` immediately and leave `Download Run Report` available afterward. Look for that file in the run folder next to `run_summary.json`.

## Warning Dialogs
- `Switch to fixed high`: Use this when the app warns that `xhigh` can multiply cost and time. It changes the current run away from the risky `xhigh` mode.
- `Apply safe OCR profile`: Use this when the app warns that the document appears OCR-heavy and local OCR is unavailable. It changes only the current run to:
  - OCR mode `always`
  - OCR engine `api`
  - Image mode `off`
  - Workers `1`
  - Effort policy `fixed_high`
  - Resume `off`
  - Keep intermediates `on`
- These warning actions are temporary for the current run only. They do not silently overwrite your saved defaults.

## If The App Does Not Open
Quickest beginner option:
1. Open the repo folder in File Explorer.
2. If you already have a browser-app launcher shortcut, use that first.
3. Or open `http://127.0.0.1:8877/?mode=live&workspace=workspace-1#new-job` directly after launching the browser app.

Terminal option:
1. Open PowerShell in the project folder.
2. Run: `.\.venv311\Scripts\python.exe -m legalpdf_translate.shadow_web.server --open`
3. If you want the real-work browser session without keeping the terminal attached, run: `.\.venv311\Scripts\python.exe tooling/launch_browser_app_live_detached.py`
4. Use the Qt shell only as a fallback when the browser app itself needs recovery: `.\.venv311\Scripts\python.exe -m legalpdf_translate.qt_app`

## Common Help Paths
- Translation behavior basics: `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- Technical canonical check: `APP_KNOWLEDGE.md`

Queue mode and budget caps also exist in the CLI, but this guide stays focused on the browser app in plain language.

## If Setup Fails (Beginner Recovery)
If `pip` or `pytest` shows errors about `html.entities` or `idna`, your Python install is broken on the machine, not in your project.

Use this fix:
1. Run: `powershell -ExecutionPolicy Bypass -File scripts/setup_python311_env.ps1 -Recreate`
2. Activate: `. .\.venv311\Scripts\Activate.ps1`
3. Retry your command.

## OCR-Heavy Safety Notes
1. For scanned court documents, start with pages `1-2`, then `3-4`, then `5-7` instead of running the whole document immediately.
2. If you choose `Cancel and wait`, the app now waits only until the current request finishes or hits its deadline. It should no longer look indefinitely stuck.
3. If a run stops partway through, open the run report and the run folder before trying again.
4. In Save to Job Log, `Words` now means translated output words from the DOCX, not raw OCR/source page text.
5. In the Job Log window, use the pen button for the full form, double-click visible cells for quick inline edits, and expect a confirmation before any delete.
6. When Gmail draft creation is offered after generating honorários, the app should usually reuse the translated DOCX automatically. Historical Job Log rows only ask you to pick a translation file when the row has no stored path and exact `run_id` recovery is not possible.
7. Gmail intake live testing must happen on the same Windows host as the signed-in browser and Windows `gog`. A WSL-only smoke is not enough for the final check.
8. In Gmail batches, if you accidentally choose the translated DOCX filename while saving honorários, the app now auto-renames the honorários file instead of overwriting the translation.
9. If a Gmail batch reply draft still fails after translation finished, look for `gmail_batch_session.json` under your output folder’s `_gmail_batch_sessions` directory before retrying blindly.
10. For interpretation rows, the saved distance is tied to the service city. If the KM value looks wrong, confirm the row's service city before saving or exporting honorários.
