# Live Gmail Testing Guide

## Ground Rules
- Test live Gmail extension intake only from canonical `main` at `C:\Users\FA507\.codex\legalpdf_translate`.
- Do not live-test Gmail from feature branches or temporary worktrees.
- Do not switch the primary worktree branch while a LegalPDF server launched from that worktree is running.
- Do not delete app data or runtime metadata manually during a retest setup.
- Review generated DOCX/PDF files before sending any Gmail draft.

Feature branches should use browser `mode=shadow` and isolated workspaces for UI review.

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
1. Open a real Gmail email with an attachment.
2. Click the LegalPDF extension once.
3. Confirm the current tab moves into the LegalPDF browser flow.
4. Confirm attachment review opens for the exact message.
5. Run translation or interpretation only if appropriate for the test.
6. Confirm the live path shows the current UI polish from PR #46.
7. Treat numeric mismatch warnings as a legal-review gate.
8. Review generated DOCX/PDF files before sending any Gmail draft.

Codex should not click the extension or operate live Gmail unless a future task explicitly authorizes that scope.

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
