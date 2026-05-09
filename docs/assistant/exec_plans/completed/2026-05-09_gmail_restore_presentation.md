# Gmail Restore Bar Presentation

## Goal and Non-Goals
- Goal: extract Gmail restore-bar presentation shaping from `gmail.js` into a pure static-browser presentation module.
- Non-goals: no backend route, payload, selector, Gmail/native-host, live Gmail, OAuth, or submitted value changes.

## Scope
- In: `gmail_restore_presentation.js`, the `renderGmailRestoreBar()` coordinator call-site, and focused browser static-module tests.
- Out: preview rendering behavior, review drawer behavior, live Gmail extension testing, and broader Gmail coordinator refactors.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_restore_presentation`
- Branch name: `codex/gmail-restore-presentation`
- Base branch: `main`
- Base SHA: `743364bd8febb8f0c9098f1bf3881d90a898ce22`
- Target integration branch: `main`
- Build status: noncanonical feature worktree; shadow-mode browser validation only.

## Interfaces and Contracts
- Add static ESM export `buildGmailRestoreBarPresentation(...)`.
- Preserve renderer input shape `{ review: { visible, label }, preview: { visible, label } }`.
- Preserve all DOM IDs, event listeners, dataset keys, route IDs, payload shapes, safe rendering, and Gmail/native-host contracts.

## Implementation Steps
1. Add failing coverage in `tests/test_shadow_web_api.py` for the new presentation module, coordinator delegation, and versioned static asset.
2. Run the targeted restore-bar test and confirm it fails because the module/export does not exist.
3. Create `src/legalpdf_translate/shadow_web/static/gmail_restore_presentation.js` as a pure builder using existing helpers from `gmail_review_state.js`.
4. Update `src/legalpdf_translate/shadow_web/static/gmail.js` so `renderGmailRestoreBar()` gathers state and delegates to the builder before calling `renderGmailRestoreBarInto(...)`.
5. Keep `gmail_restore_ui.js` unchanged unless tests reveal a renderer contract issue.

## Tests and Acceptance Criteria
- Targeted red/green:
  `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_restore_ui_module_owns_restore_bar_renderer`
- Focused browser/Gmail suite:
  `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Wrapper before handoff:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Shadow browser smoke on port `8888` verifies nonblank Gmail intake/review demo with no console errors or live Gmail access.

## Rollout and Fallback
- Roll out through a normal PR after local validation.
- Fallback is a simple revert of the new module import and `renderGmailRestoreBar()` delegation, because no external contracts change.

## Risks and Mitigations
- Risk: restore chip labels drift from existing behavior. Mitigation: reuse `deriveGmailReviewRestoreLabel`, `deriveGmailPreviewRestoreLabel`, and `isPreviewStateOpen`.
- Risk: static asset graph misses the new module. Mitigation: assert the versioned static asset endpoint serves `gmail_restore_presentation.js`.

## Assumptions
- The canonical worktree remains on `main` for live Gmail.
- Feature validation uses `mode=shadow`.
- The canonical `.venv311` Python executable is used while running tests from this worktree.

## Executed Validation
- RED confirmed: targeted restore-bar test failed before implementation because `gmail_restore_presentation.js` did not exist.
- Targeted restore-bar test passed after implementation:
  `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_restore_ui_module_owns_restore_bar_renderer`
- Versioned static asset test passed:
  `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite passed: 189 passed.
- `scripts/validate_dev.ps1 -Full` passed. The known `dartdev` AOT snapshot issue appeared for agent-docs and workspace-hygiene validation, and both direct-Dart fallbacks passed.
- Shadow Browser smoke passed at `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`: page loaded, console had no warnings/errors, demo attachments loaded, review drawer minimized to `Review Attachments — Restore`, and the restore button reopened the review drawer with the demo attachment table visible.
