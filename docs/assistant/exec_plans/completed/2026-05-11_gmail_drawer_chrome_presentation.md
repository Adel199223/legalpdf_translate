# Gmail Drawer Chrome Presentation ExecPlan

## Goal And Non-Goals
Extract the remaining Gmail drawer chrome renderer payload shaping from `gmail.js` into a pure browser static presentation module while preserving drawer behavior, DOM IDs, dataset names, routes, Gmail/native-host behavior, and safe rendering.

Non-goals:
- Do not change drawer open/minimize semantics.
- Do not change `renderGmailDrawerChromeInto(...)`, backdrop IDs, body dataset names, routes, payloads, or selectors.
- Do not touch live Gmail, OAuth, native-host, or real drafts.

## Scope
In:
- Add pure drawer chrome presentation builders.
- Update Gmail drawer open flows to call builders before the existing safe renderer.
- Add contract/ESM/static asset coverage.
- Validate in shadow mode.

Out:
- UI redesign, animation, route changes, backend changes, and live Gmail testing.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_drawer_chrome_presentation`
- Branch name: `codex/gmail-drawer-chrome-presentation`
- Base branch: `main`
- Base SHA: `1e9e9cf2d7cde94fe6904ddc29a474b7aa977d4d`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use browser `mode=shadow` only.
- Completed: 2026-05-11

## Interfaces/Types/Contracts Affected
- Internal static-browser module interface only.
- Preserved renderer shape `{ open, bodyDatasetKey }`.
- Preserved dataset keys: `gmailReviewDrawer`, `gmailPreviewDrawer`, `gmailSessionDrawer`, `gmailBatchFinalizeDrawer`.

## File-By-File Implementation Steps
- `tests/test_shadow_web_api.py`: added failing contract/probe test for drawer chrome presentation builders and static asset coverage.
- `src/legalpdf_translate/shadow_web/static/gmail_control_presentation.js`: added pure exports for review, preview, session, and batch-finalize drawer chrome presentation.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: imported and called those builders before `renderGmailDrawerChromeInto(...)`.
- Moved this ExecPlan to `completed/` with validation evidence before commit.

## Tests And Acceptance Criteria
- RED first: targeted drawer chrome presentation test failed before implementation because the new exports did not exist.
- GREEN targeted test after implementation.
- Static asset route serves updated `gmail_control_presentation.js` JavaScript and includes the new exports.
- Focused browser/Gmail suite passes.
- `scripts/validate_dev.ps1 -Full` passes; record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.
- Browser shadow smoke verifies Gmail intake/demo review/preview drawer interaction with no live Gmail.

## Rollout And Fallback
- Publish as a normal ready PR after validation.
- Merge only after GitHub checks are green and PR is mergeable.
- If CI/auth/merge checks fail, stop at the highest clean point and report the blocker.
- Fallback is reverting the narrow PR; no backend or public contract migration is involved.

## Risks And Mitigations
- Risk: drawer open state changes. Mitigation: contract tests assert existing dataset keys and `gmail.js` call sites.
- Risk: accidental safe-rendering regression. Mitigation: kept renderer unchanged and asserted pure presentation module avoids DOM/renderer access.
- Risk: live Gmail side effects. Mitigation: used shadow demo only.

## Assumptions/Defaults
- No live Gmail/OAuth/native-host testing is in scope.
- No public backend API, route, payload, selector, submitted value, or extension contract changes are allowed.
- The user authorized the PR-first implementation, validation, publish, merge, and cleanup flow.

## Validation Log
- RED confirmed: `tests/test_shadow_web_api.py::test_gmail_control_presentation_module_builds_drawer_chrome_state` failed before implementation because `buildGmailReviewDrawerChromePresentation` and related exports were absent.
- Targeted drawer presentation test: `1 passed in 1.27s`.
- Static asset graph test: `1 passed in 4.00s`.
- Focused browser/Gmail suite: `210 passed in 180.12s`.
- Full validation: `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` completed successfully.
- Full validation recorded the known Dart AOT launcher issue for the docs and workspace hygiene launchers; the wrapper's direct-Dart fallback passed in both cases.
- Browser automation preflight selected local host, reported system Edge `148.0.3967.54`, found no stale-copy audit findings, and its Dart preflight tests passed.
- Browser shadow smoke on port `8888` verified page identity, nonblank content, no framework overlay, empty browser warning/error logs, demo attachment load, review drawer interaction, PDF preview drawer interaction, `gmail_control_presentation.js` asset serving, and screenshot evidence at `C:\Users\FA507\.codex\browser\gmail-drawer-chrome-smoke.png`.
