---
name: legalpdf-browser-review
description: >-
  Inspect and verify the LegalPDF browser app in isolated shadow mode using
  Antigravity's browser subagent, Chrome DevTools MCP, or Playwright MCP. Use
  for browser UI reviews, Gmail preview demos, asset-version checks, and bridge safety.
---

# LegalPDF Browser Review

Defer to `docs/assistant/BROWSER_BRIDGE.md`, `docs/assistant/GMAIL_LIVE_TESTING.md`, `docs/assistant/LOCAL_ENV_PROFILE.local.md`, `docs/assistant/workflows/BROWSER_AUTOMATION_ENV_PROVENANCE_WORKFLOW.md`, and `docs/assistant/workflows/HARNESS_ISOLATION_AND_DIAGNOSTICS_WORKFLOW.md`.

## Safety & Tooling Boundaries

- **Never touch live Gmail**: Do not click the live Gmail extension, navigate to live Gmail via Antigravity's built-in `browser` subagent / `playwright` / `chrome-devtools` MCP, or invoke Antigravity's `gmail` plugin unless the user explicitly authorized live Gmail scope.
- **Keep live vs shadow separate**: Canonical `main` owns live daily mode on `127.0.0.1:8877` (Gmail bridge `8765`, launched via `tooling/launch_browser_app_live_detached.py`). Use port `8888` with `mode=shadow` for branch/UI review; `8888` must never own the live Gmail bridge.
- **Ignore legacy Codex browser scripts**: Do not import or run Codex's `browser-iab-safe-tabs` helpers; use Antigravity's built-in `browser` subagent, `chrome-devtools` MCP, or `playwright` MCP.
- **Shadow mode caveat**: `mode=shadow` isolates browser workspace state, not external/native endpoints if invoked directly; verify listener ownership and offline boundaries before assuming zero side effects.

## Steps

1. **Run browser preflight (direct Dart binary)**:
   ```powershell
   & 'C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe' tooling/automation_preflight.dart
   ```
   Capture `automation_browser_binary`, `automation_browser_version`, and `automation_browser_source`.
2. **Start isolated shadow preview server on `8888`**:
   ```powershell
   .\.venv311\Scripts\python.exe -m legalpdf_translate.shadow_web.server --port 8888
   ```
   Open one of:
   - Main UI: `http://127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job`
   - Gmail review demo: `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake` (click `Load demo attachments` for safe demo PDF staging)
3. **Inspect UI & runtime health** via the `browser` subagent, `chrome-devtools` MCP, or `playwright` MCP:
   - Check client/server `asset_version` agreement so cached assets are not masquerading as current code.
   - Verify safe dynamic text rendering and clean console/network state.
4. **Teardown**: Stop only the preview server you started (only `python.exe`/`pythonw.exe -m legalpdf_translate.shadow_web.server` on `8888`, never browsers or unknown processes).

## Verification

Report the build-under-test packet: repo/worktree path, branch, `HEAD` SHA, `mode=shadow` + workspace ID, `asset_version` match, preflight binary fields, and confirmation of clean preview shutdown.
