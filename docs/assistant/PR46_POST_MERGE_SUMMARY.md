# PR #46 Post-Merge Summary

## Merge Result
- PR: `https://github.com/Adel199223/legalpdf_translate/pull/46`.
- Source branch: `feat/browser-new-job-qt-polish`.
- Merge method: GitHub squash merge with expected-head protection.
- Merge commit on `main`: `dbca0ca536429f3c92edfb503f461da21b5909f8`.
- Merge date: 2026-04-26.
- Local primary worktree was switched back to `main` after merge.

## Scope
PR #46 polished the browser Qt-aligned workflows and safety presentation without changing Gmail/native-host/extension contracts or API payload shapes.

Major themes:
- beginner-first browser workflows across New Job, Dashboard, Recent Work, Profile, Settings, Gmail Intake, Power Tools, and Extension Lab,
- safer dynamic rendering protections,
- numeric mismatch warnings before save/finalization,
- clearer live vs shadow/test mode presentation,
- Gmail success follow-up safety UI,
- profile and Recent Work presentation cleanup,
- CI and Qt test stabilization required before merge.

## Late Presentation Cleanup
- Removed duplicate Recent Work empty-state sentence.
- Clarified Profile's main-profile summary versus editable profile records.
- Added clearer daily-screen shadow/test-mode visibility.
- Fixed New Job runtime-banner visibility before full bootstrap runtime payload was available.
- Captured automated shadow-mode screenshots for New Job, Dashboard, Recent Work, Profile, Settings, Power Tools, and Extension Lab during the review process.

## CI Encoding Fix
GitHub Windows CI failed in browser ESM probes because Python sent non-ASCII JavaScript probe source to Node without explicit UTF-8 encoding. The minimal fix set `encoding="utf-8"` in `tests/browser_esm_probe.py`. This preserved product behavior and stabilized tests containing strings such as `sentenca` with Portuguese accents in source fixtures.

## Qt Job Log Delete-Key Fix
Local full pytest exposed flaky Delete-key handling in `QtJobLogWindow`. The fix routed Delete key presses from the Job Log table/viewport through the existing `_confirm_delete_selected_rows()` path, preserving confirmation prompts, inline-edit blocking, and multi-row delete behavior.

## Validation Before Merge
Final pre-merge validation passed:
- targeted pytest: `66 passed`,
- full pytest: `1232 passed`,
- `scripts/validate_dev.ps1`: passed,
- `scripts/validate_dev.ps1 -Full`: passed,
- GitHub Actions checks: passed.

The known local Dart `dartdev` AOT wrapper issue appeared during validation and direct-Dart fallback succeeded.

## Post-Merge Gmail Retest Setup
After merge, canonical-main live setup reported:
- repo path: `C:\Users\FA507\.codex\legalpdf_translate`,
- branch: `main`,
- HEAD: `dbca0ca536429f3c92edfb503f461da21b5909f8`,
- `127.0.0.1:8877`: listening,
- `127.0.0.1:8765`: listening,
- server left running for manual user retest.

The remaining human step is one live Gmail extension retest from canonical `main` using a real Gmail email with an attachment.
