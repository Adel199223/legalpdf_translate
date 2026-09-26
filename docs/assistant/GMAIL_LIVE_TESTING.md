# Live Gmail Testing Guide

## Ground Rules
- Test live Gmail extension intake only from canonical `main` at `C:\Users\FA507\.codex\legalpdf_translate`.
- Do not live-test Gmail from feature branches or temporary worktrees.
- Do not switch the primary worktree branch while a LegalPDF server launched from that worktree is running.
- Do not delete app data or runtime metadata manually during a retest setup.
- Review generated DOCX/PDF files before sending any Gmail draft.

Feature branches should use browser `mode=shadow` and isolated workspaces for UI review.

## Shadow Review/Preview Demo
Use this path when you need to review Gmail attachment UI behavior from a feature branch without touching live Gmail:

```powershell
cd C:\Users\FA507\.codex\legalpdf_translate
.\.venv311\Scripts\python.exe -m legalpdf_translate.shadow_web.server --port 8888
```

Open `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`.

When no Gmail message is loaded, shadow mode shows `Load demo attachments`. Click it to seed one safe demo PDF, open Review Attachments, and test the real Review/Preview drawer behavior against isolated test data. This demo route is blocked in `live` mode and does not use the native host, real Gmail, drafts, or private attachments.

Expected persistence behavior:
- Review Attachments should not silently close when you click outside it.
- Preview should not silently disappear when you click outside it.
- Minimize/Close/Escape should preserve the selected attachment, start page, preview page, and show a restore chip.
- Restore chips should bring back the existing Review or Preview state instead of resetting it.

## Launch Canonical Main Runtime
From the primary repo on `main`:

```powershell
cd C:\Users\FA507\.codex\legalpdf_translate
git branch --show-current
git status --short
.\.venv311\Scripts\python.exe tooling\launch_browser_app_live_detached.py --mode live --workspace workspace-1 --no-open
```

The canonical browser app should use `127.0.0.1:8877`. The Gmail bridge should listen on `127.0.0.1:8765`.

## Listener Check
```powershell
Get-NetTCPConnection -LocalPort 8877,8765 -State Listen
```

If process inspection is needed, only stop a process when it is clearly:
- `python.exe` or `pythonw.exe`,
- running `-m legalpdf_translate.shadow_web.server`,
- using a LegalPDF browser-app port such as `8877` or `8888`.

Only stop a matching LegalPDF server when the current task permits it or the user has approved that process cleanup.
Never stop browsers, unrelated Python processes, or unknown processes.

## Manual Retest Steps
Before the click, verify the actual canonical build/served asset and check whether the configured Gmail helper has a connected account using its read-only account-status command. Do not print account details or tokens. Browser/assistant-connector authentication and app-helper authentication are separate. If a new connection is needed within an already explicitly authorized live Gmail check, initiate only the necessary scoped connection under that existing authorization; do not ask for the same permission again. Let the user complete Google's sign-in/consent and verify the resulting scopes without printing private details; do not automate authentication dialogs. An intake-only test needs no email-sending authority.

1. Open a real Gmail email with an attachment.
2. Click the LegalPDF extension once.
3. Confirm the current tab moves into the LegalPDF browser flow.
4. Confirm attachment review opens for the exact message.
5. Run translation or interpretation only if appropriate for the test.
6. Verify the observed behavior against the recorded current canonical build and served assets. A posted bridge context alone does not prove that the message or its attachments loaded.
7. Treat numeric mismatch warnings as a legal-review gate.
8. Review generated DOCX/PDF files before sending any Gmail draft.

Codex should click the extension or operate live Gmail only within explicit current user authorization. Existing authorization persists across interruption; an old failed or consumed extension operation must not be replayed merely to resume the task.

## Scoped intake and preparation checks

After an actual extension handoff failed solely because the app helper lacked a connection, a verified connection can be followed by **Advanced message details** / **Load this Gmail message** for the retained exact message. Record this as manual recovery; it does not establish a seamless extension-to-output pass. Keep read-only intake separate from translation, draft and send authority.

Before **Continue**, create or choose an existing writable output folder. A missing folder can return a setup refusal before a prepared session exists. Preserve that refusal; correct the folder once within the scoped test instead of restarting intake. When a Preview restore chip sits behind the open Review modal, minimize Review first, then restore Preview. Check selection and navigation state; hidden and visible drawer sizing can produce different canvas pixels without proving content loss.

Normal full bootstrap, first PDF bundle responses and some generic error responses may assess Word readiness. An uncached assessment can launch a Word probe and a fictional-document PDF canary; the cache lasts 60 seconds. A failed preparation response can therefore have native effects even when no translation session was created. Scope and record the actual assessments, preserve the canonical readiness journal before/after, verify owned cleanup, and stop dependent actions if the observed bound is exceeded. Do not bypass readiness or call these routes native-free. The canonical app-data journal can differ from a historical isolated acceptance journal; verify exact paths and preserve both. Canary success does not establish legal-document translation or rendering quality.

The September24 qualified intake check loaded one message, previewed two PDFs and prepared one session without starting it. Its first setup refusal caused an unexpected fourth readiness pair beyond the original three-pair plan; all four reported cleanup and the corrected request succeeded without another assessment. The [completed check](exec_plans/completed/2026-09-24_live_gmail_connection_recovery.md) retains the failure, scope deviation, recovery and limitations.

## Translation saved versus later finalization

Ordinary **Save case record** and Gmail **Save this Gmail attachment** / Confirm are separate UI actions. A saved row does not by itself confirm the batch item; normal Gmail confirmation reuses the already saved row. Inspect the current genuine session and row/run/output join before repeating either action. Gmail05 demonstrated a single new row 91 followed by normal confirmation of that same row.

Normal **Save this Gmail attachment** / Confirm can save the job and output before a subsequent Word-readiness check fails. Inspect the genuine session report and exact job/run/output join before repeating a save or starting another translation. A saved translation is separate from honorários generation, Gmail draft creation and sending. The qualified Gmail03 check on merged PR303 saved one actual output as row 90; all 63 earlier rows remained unchanged. Its later readiness failure, separate owned cleanup and fresh preflight are preserved, not erased by the saved-job result. Current status belongs in [HANDOFF.md](HANDOFF.md).

Review scan output against the actual image: OCR or image input can still produce stray fragments, altered characters or omitted text. If a fresh rerun is justified, record explicit per-run OCR/image choices and choose a fresh existing output folder so the prior run remains intact. Do not promote those choices to defaults from one successful document. The ordinary image-only path is separate from reviewed-source mode, which requires local OCR evidence. Preserve any required original attachment bytes while the genuine intake is active; downloaded intake files can belong to a temporary directory removed when its owning session/runtime ends.

Gmail intake authorization does not prove draft-write permission. An actual Google 403 `insufficientPermissions` after successful honorários generation is a draft failure, not a missing translation or a successful draft. Preserve the finalization report and exact generated/staged artifacts; do not retry an uncertain draft or expand OAuth scope merely to obtain a green acceptance result. Gmail05 reached that permission-limited outcome once, without sending.

Keep the owning runtime alive through the normal browser download and inspect native browser permission prompts before shutdown. Verify the downloaded copy against the generated artifact. A successful local artifact route, a blocked browser transfer and a later successful download are distinct evidence. Native cleanup must also distinguish operation-owned Word processes from unrelated open or recovered user documents; never use global Word absence as a reason to close those documents.

Full bootstrap and some session/error responses may invoke native readiness; a GET is not automatically side-effect-free. A successful standalone preflight does not update another process's cached readiness. Preserve unknown cleanup and exact process ownership, use a fresh reviewed recovery scope where necessary, and never manually restore an older Word journal or replay a consumed helper to obtain a green status.

## If The Bridge Is Not Ready
- If `8877` is listening but `8765` is not, stop random fixes and run a focused live-bridge diagnosis.
- Check whether the canonical browser server is running from `main`.
- Check safe tails of:
  - `tmp/browser_app_8877.spawned.out.log`
  - `tmp/browser_app_8877.spawned.err.log`
- Capture the exact time, listener state, and visible browser/Gmail symptoms.
- Do not paste secrets, tokens, `.env` values, or private Gmail content into reports.

## Failure Evidence To Capture
If the extension click fails, capture:
- screenshot of the Gmail page after the click,
- screenshot of any LegalPDF browser page or error,
- exact time of click,
- whether attachment review opened, partially opened, or did nothing,
- safe listener state for `8877` and `8765`.
