# Gmail Action Runner ExecPlan

## Goal And Non-Goals
Move repeated Gmail event-handler busy/failure wrapping out of `gmail.js` into a focused static helper while preserving every existing button ID, event listener, route, payload, diagnostics slot, Gmail/native-host behavior, and safe rendering path.

Non-goals:
- Do not change Gmail workflow behavior, routes, payload shapes, selectors, datasets, or submitted values.
- Do not touch live Gmail, OAuth, native-host, or real drafts.
- Do not redesign any UI.

## Scope
In:
- Add `gmail_action_runner.js` to centralize `runWithBusy` plus failure-feedback orchestration.
- Update `gmail.js` event handlers to call the action runner rather than repeating `runWithBusy`/`try`/`catch` blocks.
- Keep `busy_ui.js` as the shared button busy renderer.
- Add contract, ESM probe, and static asset coverage.

Out:
- Backend changes, extension changes, live Gmail testing, and renderer/presentation redesign.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_action_runner`
- Branch name: `codex/gmail-action-runner`
- Base branch: `main`
- Base SHA: `406ed831156f26985c64fb2dd48af4cacf2f52e6`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use browser `mode=shadow` only.

## Interfaces/Types/Contracts Affected
- New internal static module export: `runGmailBusyAction(...)`.
- Existing `busy_ui.js` exports remain unchanged.
- Existing Gmail event handlers, button IDs, diagnostics slots, and payloads remain unchanged.

## File-By-File Implementation Steps
- `tests/test_shadow_web_api.py`: add failing contract/probe coverage for `gmail_action_runner.js`, update Gmail busy ownership expectations, and add static asset graph coverage.
- `src/legalpdf_translate/shadow_web/static/gmail_action_runner.js`: implement the busy/failure wrapper around `runWithBusy`.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import the runner and replace repeated `runWithBusy` try/catch wrappers with `runGmailAction(...)` calls that preserve existing side effects and failure text.
- `docs/assistant/exec_plans/...`: move this plan to `completed/` with validation evidence before commit.

## Tests And Acceptance Criteria
- RED first: targeted action-runner contract fails before implementation.
- GREEN targeted action-runner and static asset graph tests.
- Focused browser/Gmail suite passes.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passes; record the known Dart AOT issue only if direct-Dart fallback succeeds.
- Browser shadow smoke verifies Gmail intake demo attachment load, review detail, preview interaction, console health, and screenshot evidence.

## Rollout And Fallback
- Publish as a ready PR after validation.
- Merge only after GitHub checks are green and PR is mergeable.
- If auth, CI, conflicts, or mergeability fail, stop at the highest clean point and report the blocker.
- Fallback is reverting the narrow PR; no public/backend contract migration is involved.

## Risks And Mitigations
- Risk: an error path loses a special side effect. Mitigation: support pre/post error hooks and assert the runner preserves call ordering.
- Risk: button busy labels change. Mitigation: keep IDs and labels at the `gmail.js` call sites.
- Risk: safe rendering regresses. Mitigation: action runner has no DOM writes and `busy_ui.js` remains the only busy renderer.

## Assumptions/Defaults
- No live Gmail/OAuth/native-host testing is in scope.
- No route, backend payload, submitted value, selector, dataset, Gmail/native-host, or extension contract changes are allowed.
- The user authorized the PR-first implementation, validation, publish, merge, and cleanup flow.

## Validation Log
- 2026-05-12 RED confirmed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_action_runner_module_centralizes_busy_failure_wrapping` failed because `gmail_action_runner.js` did not exist.
- 2026-05-12 Targeted action-runner/static contracts passed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_action_runner_module_centralizes_busy_failure_wrapping tests/test_shadow_web_api.py::test_gmail_js_uses_shared_busy_ui_for_button_state tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph` -> 3 passed.
- 2026-05-12 Focused browser/Gmail suite passed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py` -> 212 passed.
- 2026-05-12 Full validation passed: `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`. The wrapper reported the known `dart run` / `dartdev` AOT snapshot issue for agent docs and workspace hygiene validation, then direct-Dart fallback succeeded for both.
- 2026-05-12 Browser shadow smoke passed on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-action-runner-smoke#gmail-intake`: page title `LegalPDF Translate`, nonblank content, no framework overlay, console had 0 warnings/errors, `Load demo attachments` restored its label/`aria-busy=false`, demo attachment rendered, PDF preview opened with `gmail-preview-canvas` 827x1070, selecting the attachment updated row/detail state, no live Gmail/OAuth/native-host flow was touched, and screenshot evidence was captured as `gmail-action-runner-smoke.png`.

## Completion
- Completed 2026-05-12.
