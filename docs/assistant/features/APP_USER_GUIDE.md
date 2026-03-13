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
1. Open the app.
2. Choose your PDF file.
3. Pick output language (`EN`, `FR`, or `AR`).
4. Start translation.
5. Wait for completion and open the generated DOCX file.

## What You See On Screen
- Left sidebar: quick buttons for `Dashboard`, `New Job`, `Recent Jobs`, `Settings`, and `Profile`.
- Window title: shows `Workspace N`; when a file is loaded it can also add that filename so parallel windows are easier to tell apart.
- Job Setup: where you choose the PDF, target language, and output folder.
- Run Status: where you watch progress, current task text, and page/image/error counts.
- Advanced Settings: a fold-open section for Analyze, OCR options, queue manifest, and other expert controls, with a small info button for the extra guidance.
- More menu (`...`): extra actions such as opening the output folder, rebuilding DOCX, or generating a run report.
- Theme: in `Settings > Appearance`, `dark_futuristic` is the brighter elevated default and `dark_simple` is the quieter darker variant. The change applies live without restarting the app.
- The main dashboard and the most-used dialogs now share the same raised translucent panel style, so Settings, Gmail review/preview, Save/Edit Job Log, and honorários export should feel like part of the same interface instead of separate utility windows.

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
- Tools menu: the top menu where you can open settings, the Review Queue, or the Job Log.
- More menu (`...`): the small button at the bottom that opens extra output/report actions.

## Common Tasks
1. Analyze first when a PDF looks messy or scanned, then decide whether to apply the OCR Advisor suggestion for the next run.
2. If a warning says `xhigh` can multiply cost and time, choose `Switch to fixed high` unless you intentionally want the slower, more expensive option.
3. If an OCR-heavy warning appears for a scanned document, choose `Apply safe OCR profile` to fix the current run without changing your saved defaults.
4. After a run finishes, open the Review Queue if pages were flagged for manual checking.
5. For Arabic runs, review the DOCX in Word when the app pauses for that step, then save it so the app can continue automatically.
6. Save the finished run to the Job Log so the case and cost details are stored together.
7. Use a queue manifest when you want the app to process several PDFs in sequence without starting each one manually.
8. Use Gmail intake when you want to start from one open Gmail message instead of choosing files manually.
9. Open `File > New Window` or press `Ctrl+Shift+N` when you want a second independent workspace for another job.
10. After generating a `Requerimento de Honorários`, let the app create a Gmail draft when that flow supports it and `Court Email` is available.
11. Use the Job Log when you need an interpretation-only honorários document without a translation run, or start from Gmail intake when the court notice already arrived by email.

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
3. Review the case and service details before saving. Interpretation mode focuses on service date, service location, and distance instead of translation metrics.
4. If a photo or screenshot import did not contain an explicit service entity or city, the form still opens normally and lets you fill those fields in manually.
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

## Multiple Windows
1. Open another workspace from `File > New Window`, `Ctrl+Shift+N`, or the bottom `...` menu.
2. Each window is a separate workspace. Starting, stopping, or resetting one window does not reset the others.
3. You can run different jobs in parallel as long as they do not resolve to the same run folder.
4. If the app says a translation is already active in another workspace, both windows would write to the same output run folder. Change the output folder or target language, or wait for the other workspace to finish.
5. Unstarted edits stay in that window only. A new blank workspace should not copy draft file/language/output changes from another workspace.
6. Gmail intake reuses the last active blank idle workspace when possible. If that workspace is already busy or has job context, the app opens a new workspace for the intake automatically.

## Gmail Intake Batch Replies
1. In `Settings > Keys & Providers > Gmail Drafts (Windows)`, turn on the Gmail intake bridge.
2. Load `extensions/gmail_intake/` as an unpacked extension in Edge or Chrome.
3. Normal use no longer requires manually copying the bridge token and port into the extension options page. Use that page only for diagnostics.
4. Open Gmail in that same Windows browser and expand exactly one message.
5. Click the extension toolbar button. If the app is closed but the Gmail bridge is configured, the extension can auto-start the current checkout and continue that same click. If Gmail still cannot identify one exact message, the batch does not start.
6. In the app, choose the Gmail intake mode first:
   - `Translation` keeps the existing multi-attachment translation batch behavior and target-language review.
   - `Interpretation notice` is for one selected court-notice attachment that should not be translated.
7. The review dialog starts with a short summary banner. Use its info button if you need the sender, Gmail account, or output-folder details.
8. In `Translation` mode, choose which files to translate and correct the target language if needed.
9. In `Interpretation notice` mode, select exactly one supported PDF or image attachment. The app hides translation-only review inputs in that mode.
10. Use `Preview selected attachment` when you need to inspect a file before preparing it.
11. In preview, page `1` is the default. Scroll the PDF and click `Start from this page` only for translation batches when the file should begin later, such as after a cover sheet.
12. When you click `Prepare selected attachments`, already previewed files are reused when possible instead of being downloaded again.
13. Translation mode then translates the selected files one by one.
14. Interpretation-notice mode stages the original notice, extracts the case and service metadata, opens the interpretation `Save to Job Log` confirmation, then opens interpretation honorários export.
15. Arabic translation files pause in a Word review step before `Save to Job Log`. Save the DOCX there and the app continues automatically; if save detection misses, use `Continue now` after saving.
16. Translation mode requires each file to be saved before the next one begins. If you cancel that dialog, the remaining files stop on purpose.
17. If one translation file resolves to a different case or court, stop and split the work into separate batches.
18. After the last translation file, or after the interpretation honorários export generates its PDF, the app can create one Gmail reply draft in the original thread.
19. Translation Gmail drafts attach the translated DOCX files plus the generated honorários PDF.
20. Interpretation Gmail drafts attach only the generated honorários PDF. They do not attach the original notice or any translated DOCX.
21. The app creates a draft only. It does not send the email automatically.

## If Gmail Intake Stops Early
1. If the page says the app is not listening, confirm the bridge is enabled. A normal toolbar click can auto-start the app, so a manual launch should only be needed after an auto-start failure.
2. If the app window says `Gmail intake bridge unavailable`, another process may already be using the bridge port.
3. If Gmail shows `accepted` but the app stays idle, check that the listener on `127.0.0.1:<port>` belongs to the LegalPDF app and not to `pytest` or another stray process.
4. If the page says auto-launch is unavailable from this checkout, open the extension options page and refresh diagnostics.
5. If the page says the token is invalid, treat that as a Settings/native-host mismatch and refresh diagnostics instead of editing the extension options page manually.
6. If the page says the message is ambiguous, collapse extra Gmail messages and leave only one expanded.
7. If the app shows no supported attachments, that email likely contains only inline or unsupported files.
8. If the batch stops after Save to Job Log, that is expected when you cancel the dialog or when the case/court details no longer match.
9. If you skip or fail honorários generation at the end of the translation batch, or cancel/fail the interpretation honorários export after Gmail intake, the app does not create the Gmail reply draft.
10. The extension does not create its own report file. Use the browser banner for handoff failures, then the app/run reports for everything after intake.
11. If the honorários PDF cannot be generated, the export still keeps the local DOCX but Gmail draft creation stays blocked for that export.

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
2. Double-click `Launch LegalPDF Translate.bat`.
3. That batch file uses the same canonical Qt launcher helper as the supported manual startup path.

Terminal option:
1. Open PowerShell in the project folder.
2. Run: `.\.venv311\Scripts\python.exe -m legalpdf_translate.qt_app`
3. If you want it detached from the terminal, run: `Start-Process .\.venv311\Scripts\pythonw.exe -ArgumentList '-m','legalpdf_translate.qt_app'`

## Common Help Paths
- Translation behavior basics: `docs/assistant/features/PDF_TO_DOCX_TRANSLATION_USER_GUIDE.md`
- Technical canonical check: `APP_KNOWLEDGE.md`

Queue mode and budget caps also exist in the CLI, but this guide stays focused on the desktop app in plain language.

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
