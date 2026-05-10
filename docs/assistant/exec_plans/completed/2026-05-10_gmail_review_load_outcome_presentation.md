# Gmail Review Load Outcome Presentation

## Goal And Non-Goals
- Extract pure presentation shaping for Gmail review load outcomes from `gmail.js`.
- Keep Gmail load routes, POST payloads, state reset contracts, diagnostics payloads, DOM IDs, datasets, event listeners, and safe renderer behavior unchanged.
- Do not touch live Gmail, OAuth, native-host, extension contracts, backend route shapes, or finalization flows.

## Scope
- In: `loadMessage()` and `loadDemoReview()` outcome tone/message/open-review decisions.
- In: pure ESM builder coverage and static asset export coverage.
- Out: renderer rewrites, backend payload changes, session/finalization state changes, live Gmail testing.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_review_load_outcome_presentation`
- Branch name: `codex/gmail-review-load-outcome-presentation`
- Base branch: `main`
- Base SHA: `962f766be4029cd8dfcd78084abb83b306168e92`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; shadow browser review only

## Interfaces, Types, And Contracts Affected
- Add `buildGmailReviewLoadOutcomePresentation(...)` to `gmail_control_presentation.js`.
- `gmail.js` gathers the existing load payload/state and applies the builder output.
- No public API, route, selector, dataset, submitted value, native-host, or extension contract changes.

## File-By-File Implementation Steps
- `tests/test_shadow_web_api.py`: add RED contract/ESM probes for message load ok, unavailable, error fallback, demo load, null-safe defaults, and malicious text preservation as plain data; assert static asset exports the builder.
- `src/legalpdf_translate/shadow_web/static/gmail_control_presentation.js`: add the pure builder with no DOM or rendering imports.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import the builder and replace inline load outcome shaping with calls to it.

## Tests And Acceptance Criteria
- RED first: targeted contract fails before implementation because the builder export/import is missing.
  - Result: failed as expected on missing `buildGmailReviewLoadOutcomePresentation` import/export.
- GREEN: targeted contract passes.
  - Result: passed.
- Focused suite passes:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: 203 passed.
- Full validation passes:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed. `dart run ...` hit the known Dart AOT snapshot issue; the wrapper's direct-Dart fallback succeeded for agent-docs and workspace hygiene.
- Shadow browser smoke on port `8888` confirms page identity, nonblank Gmail review demo, console health, and no live Gmail flow.
  - Result: passed on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-load-outcome-smoke#gmail-intake`.
  - Browser verified page identity, nonblank content, no framework overlay, clean console, and demo-load interaction.
  - Browser screenshot capture timed out; local Chromium CDP fallback captured post-demo screenshot evidence at `C:\Users\FA507\AppData\Local\Temp\gmail_review_load_outcome_after_demo.png`.

## Rollout And Fallback
- Publish through PR-first flow only after validation: commit, push branch, ready PR, wait for green checks, merge normally, fast-forward `main`, prune, and remove feature worktree after confirming merge.
- If GitHub auth, PR creation, CI, merge, or validation fails, stop and report the blocker.

## Risks And Mitigations
- Risk: changing status/diagnostics text. Mitigation: tests assert existing text and open/tone decisions.
- Risk: over-broad coordinator refactor. Mitigation: keep the extraction limited to pure presentation output consumed by existing load paths.

## Assumptions And Defaults
- No live Gmail/OAuth/native-host testing is in scope.
- Existing validation evidence must be rerun in this worktree before publish.
- Known Dart AOT launcher issue should be recorded only if the validation wrapper reports direct-Dart fallback success.
