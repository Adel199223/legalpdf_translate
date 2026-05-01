# Gmail Bridge Host Fix

## Closeout Note
- Absorbed into the final Gmail/browser closeout branch instead of being published as a separate PR.
- Keep this file as the focused native-host repair packet that explains why local source-checkout registration now prefers the app-data wrapper host.

## Summary
- Repair the Gmail native host on the current `main` lineage so the Edge extension can prepare Gmail intake again.
- Keep the daily browser app contract unchanged on `127.0.0.1:8877`.
- Prefer a stable checkout-host wrapper when available, but preserve packaged-exe support for installed builds.

## Problem
- The live Edge native-messaging manifest now points at the canonical host path, but the packaged host executable crashes during the native handshake.
- Direct execution of `dist/legalpdf_translate/LegalPDFGmailFocusHost.exe` fails with `ModuleNotFoundError: No module named '_ctypes'`.
- The extension then falls back to the misleading toast `Gmail bridge is not configured in LegalPDF Translate.`

## Key Changes
- Harden native-host resolution so checkout/dev environments can prefer a stable `LegalPDFGmailFocusHost.cmd` wrapper when present.
- Restore the canonical-worktree preference for auto-launch target resolution so stale side worktrees do not become bridge owners.
- Update the PyInstaller host spec coverage for native runtime modules needed by the host.
- Add or restore focused tests covering wrapper preference, canonical worktree preference, and host packaging coverage.
- Re-register the live Edge native host against the repaired canonical host after code changes land locally.

## Test Plan
- `python -m pytest -q tests/test_gmail_focus_host.py tests/test_gmail_intake.py tests/test_pyinstaller_specs.py tests/test_browser_gmail_bridge.py`
- Direct native-host handshake against the registered host path.
- Manual extension retest after live host re-registration.

## Assumptions
- This pass should fix the misleading “not configured” toast without changing user-facing Gmail intake workflow semantics.
- A checkout-host wrapper is acceptable for the local dev environment because the user is running from source, not from a standalone installer-only deployment.
