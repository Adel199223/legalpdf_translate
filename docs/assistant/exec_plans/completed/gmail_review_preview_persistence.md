# Gmail Review/Preview Persistence UX

## Goal and non-goals
- Improve Gmail intake Review Attachments and Preview UX so panels do not feel lost after outside clicks.
- Keep the change front-end focused.
- Do not change Gmail backend handoff behavior, extension route contracts, route paths, API payload shapes, safe rendering, app data, or draft sending behavior.

## Scope
- In scope: Gmail intake template controls, Gmail front-end state/handlers, styling, and focused browser-state tests.
- Out of scope: live Gmail testing, backend handoff changes, extension/native-host contracts, translation/finalization behavior, and unrelated UI redesign.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_persistence`
- Branch name: `codex/gmail-review-preview-persistence`
- Base branch: `origin/main`
- Base SHA: `77204f82e7992b00237fb218426c4ba0578cd8f3`
- Target integration branch: `main`
- Canonical runtime note: implementation is in an isolated worktree so the primary canonical-main live server can remain untouched.

## Interfaces/types/contracts affected
- Public backend/API/Gmail/native-host/extension contracts: none.
- Front-end-only state helpers are added for drawer dismissal and restore labels.

## File-by-file implementation steps
- `src/legalpdf_translate/shadow_web/templates/index.html`: add restore chips and explicit minimize/back controls for Gmail review and preview drawers.
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`: add pure helpers for restore labels, preview minimization/restoration, and dismissal actions.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: wire outside click to no-op, Escape to minimize, close/minimize to preserve state, and restore chips to reopen existing state.
- `src/legalpdf_translate/shadow_web/static/style.css`: style restore chips consistently with the Gmail workspace.
- Existing tests: add focused regression coverage for the new persistence behavior and template affordances.

## Tests and acceptance criteria
- Review Attachments outside click does not close silently.
- Review Attachments restores the existing selected/start-page state.
- Preview outside click does not close silently.
- Preview close/minimize preserves selected attachment and page.
- Restore chips expose selected count and preview page.
- Gmail route behavior remains unchanged.

## Rollout and fallback
- Validate with focused Gmail/browser route tests and `scripts/validate_dev.ps1`.
- If validation fails, keep the branch local and do not promote changes.
- Fallback is to revert only this front-end branch before merge.

## Risks and mitigations
- Risk: changing close semantics may keep more state than expected. Mitigation: only reset preview state on existing true reset flows.
- Risk: restore controls add clutter. Mitigation: show chips only when a drawer has been explicitly minimized/hidden with restorable state.

## Assumptions/defaults
- Backdrop clicks keep overlays open.
- Escape minimizes Review/Preview and shows a restore chip.
- Preview Close means hide/minimize while preserving state.

## Executed validation
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py tests/test_translation_browser_state.py tests/test_shadow_web_route_state.py` passed: 12 passed.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py` passed: 50 passed.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1` passed: 61 passed in wrapper pytest, compileall passed, agent docs validation passed via direct-Dart fallback, workspace hygiene validation passed via direct-Dart fallback.
