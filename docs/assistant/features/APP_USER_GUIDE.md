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
- Job Setup: where you choose the PDF, target language, and output folder.
- Conversion Output: where you watch progress, current task text, and page/image/error counts.
- Advanced Settings: a fold-open section for Analyze, OCR options, queue manifest, and other expert controls.
- More menu (`...`): extra actions such as opening the output folder, rebuilding DOCX, or generating a run report.

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
9. After generating a `Requerimento de Honorários`, let the app create a Gmail draft when `Court Email` is available.

## Gmail Intake Batch Replies
1. In `Settings > Keys & Providers > Gmail Drafts (Windows)`, turn on the Gmail intake bridge and keep the app running on Windows.
2. Load `extensions/gmail_intake/` as an unpacked extension in Edge or Chrome.
3. Copy the bridge token and port from the app into the extension options page.
4. Open Gmail in that same Windows browser and expand exactly one message.
5. Click the extension toolbar button. If Gmail cannot identify one exact message, the batch does not start.
6. In the app, review the supported attachments from that email, choose which ones to translate, and correct the target language there if needed.
7. Use `Preview selected attachment` when you need to inspect a file before preparing it.
8. In preview, scroll the PDF and click `Use this page as start` if the first page is only a cover sheet or otherwise should not be translated.
9. When you click `Prepare selected attachments`, already previewed files are reused when possible instead of being downloaded again.
10. The app translates the selected files one by one.
11. Arabic files pause in a Word review step before `Save to Job Log`. Save the DOCX there and the app continues automatically; if save detection misses, use `Continue now` after saving.
12. Save each file before the next one begins. If you cancel that dialog, the remaining files stop on purpose.
13. If one file resolves to a different case or court, stop and split the work into separate batches.
14. After the last file, you can generate one honorários DOCX and one Gmail reply draft in the original thread.
15. The app creates a draft only. It does not send the email automatically.

## If Gmail Intake Stops Early
1. If the page says the app is not listening, confirm the bridge is enabled and the Windows app is still running.
2. If the app window says `Gmail intake bridge unavailable`, another process may already be using the bridge port.
3. If Gmail shows `accepted` but the app stays idle, check that the listener on `127.0.0.1:<port>` belongs to the LegalPDF app and not to `pytest` or another stray process.
4. If the page says the token is invalid, copy the token from Settings into the extension options again.
5. If the page says the message is ambiguous, collapse extra Gmail messages and leave only one expanded.
6. If the app shows no supported attachments, that email likely contains only inline or unsupported files.
7. If the batch stops after Save to Job Log, that is expected when you cancel the dialog or when the case/court details no longer match.
8. If you skip or fail honorários generation at the end of the batch, the app does not create the Gmail reply draft in this version.
9. The extension does not create its own report file. Use the browser banner for handoff failures, then the app/run reports for everything after intake.

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
Use the real GUI module entrypoint:
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
5. When Gmail draft creation is offered after generating honorários, the app should usually reuse the translated DOCX automatically. Historical Job Log rows only ask you to pick a translation file when the row has no stored path and exact `run_id` recovery is not possible.
6. Gmail intake live testing must happen on the same Windows host as the signed-in browser and Windows `gog`. A WSL-only smoke is not enough for the final check.
7. In Gmail batches, if you accidentally choose the translated DOCX filename while saving honorários, the app now auto-renames the honorários file instead of overwriting the translation.
8. If a Gmail batch reply draft still fails after translation finished, look for `gmail_batch_session.json` under your output folder’s `_gmail_batch_sessions` directory before retrying blindly.
