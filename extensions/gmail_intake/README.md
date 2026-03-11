# Gmail Intake Extension

Windows-only Gmail intake extension for the batch translation and threaded reply-draft workflow.

## Scope
- Manifest V3
- Gmail web only: `https://mail.google.com/*`
- Toolbar click only
- Sends exact message context only:
  - `message_id`
  - `thread_id`
  - `subject`
  - optional `account_email`
- No second Gmail OAuth stack
- No polling
- No auto-send

## Install
1. Open `edge://extensions` or `chrome://extensions`.
2. Enable Developer mode.
3. Choose `Load unpacked`.
4. Select `extensions/gmail_intake/`.

## Configure
1. In LegalPDF Translate, enable the Gmail intake bridge in `Settings > Keys & Providers > Gmail Drafts (Windows)`.
2. Keep Gmail and LegalPDF Translate on the same Windows host as Windows `gog`.
3. The extension can auto-start the current repo checkout when the app is closed, as long as the Gmail bridge is configured and the native host can resolve this checkout.
4. If you need diagnostics, open the extension options page and use `Refresh Diagnostics`.

## Use
1. Open Gmail in Edge or Chromium on the same Windows host as the app.
2. Open exactly one expanded message so the extension can identify it exactly.
3. Click the extension toolbar action. The extension asks the Edge native host for the live bridge port/token and, when needed, auto-starts the current checkout before posting to localhost.
4. If the handoff succeeds, the app fetches that exact message and opens the supported-attachment review dialog.
5. Select the attachments you want to translate and set the batch target language there if needed.
6. Save each translated file in `Save to Job Log` before the next file starts.
7. After the final file, optionally generate one honorários DOCX and one Gmail reply draft in the original thread.
8. The app creates a draft only. It does not send the email automatically.

The extension does not write its own report file. For durable diagnostics, use the app-owned `run_report.md` / `run_summary.json` for translation issues and `gmail_batch_session.json` for batch finalization or draft issues.

## Failure cases
- App not listening on `127.0.0.1:<port>`
- Invalid token
- Gmail bridge disabled or not configured in LegalPDF Translate
- Auto-launch target for the current checkout is missing or broken
- The app started, but the Gmail bridge did not become ready in time
- Edge native host unavailable; the extension may fall back to legacy stored config if one already exists
- The open Gmail message is not expanded enough to identify exactly
- More than one visible candidate message is open
- Content script on an older Gmail tab went stale; the extension now self-heals by reinjecting and should show a visible Gmail-page banner instead of doing nothing
- No supported attachments were found on the exact intake message
- Save to Job Log was cancelled during the batch, so remaining attachments were not processed
- Confirmed case/court metadata diverged, so the email must be split into separate reply batches
- Honorários generation was skipped or failed, so no Gmail draft was created
- The app showed `Gmail intake bridge unavailable`, so the localhost port/process state needs to be fixed before retrying
