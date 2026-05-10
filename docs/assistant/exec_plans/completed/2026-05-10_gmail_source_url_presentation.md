# Gmail Source URL Presentation

## Goal And Non-Goals
- Extract Gmail source URL precedence and normalization from `gmail.js` into the existing pure Gmail action presentation module.
- Preserve the existing Return-to-Gmail renderer shape and the `load-message` payload contract.
- Do not change routes, IDs, datasets, submitted values, Gmail/native-host behavior, live Gmail flow, or safe text rendering.

## Scope
- In: deriving the current Gmail source URL from current handoff context, defaults message context, pending intake context, click diagnostics, and explicit source URL input.
- In: ESM contract tests for precedence, whitespace normalization, malicious string preservation as data, and null-safe defaults.
- Out: renderer changes, native-host changes, live Gmail/OAuth testing, finalization flows, and backend payload schema changes.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_source_url_presentation`
- Branch name: `codex/gmail-source-url-presentation`
- Base branch: `main`
- Base SHA: `fc13848b94af93551d7232c1bec9fff73c877c11`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; shadow browser review only

## Interfaces, Types, And Contracts Affected
- Add `deriveGmailSourceUrl(...)` to `gmail_action_presentation.js`.
- Keep `buildGmailReturnToSourceActionPresentation(...)` returning `{ visible, sourceUrl }`.
- `gmail.js` keeps `currentSourceGmailUrl()` as the coordinator-facing helper, but delegates pure precedence to the presentation module.

## File-By-File Implementation Steps
- `tests/test_shadow_web_api.py`: add RED assertions and ESM probes for `deriveGmailSourceUrl(...)`; update static asset export coverage.
- `src/legalpdf_translate/shadow_web/static/gmail_action_presentation.js`: add the pure derivation helper and reuse it from the return-to-source action builder.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import `deriveGmailSourceUrl(...)` and delegate `currentSourceGmailUrl()` to it.

## Tests And Acceptance Criteria
- RED first: targeted contract fails because `deriveGmailSourceUrl(...)` is not exported/imported yet.
  - Result: failed as expected on missing `deriveGmailSourceUrl(...)`.
- GREEN: targeted action presentation contract passes.
  - Result: passed with static asset coverage:
    `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_action_presentation_module_derives_prepare_action_state tests/test_shadow_web_api.py::test_gmail_action_ui_module_owns_return_to_source_action_renderer tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
- Focused browser/Gmail suite passes:
  `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: 203 passed.
- Full validation passes:
  `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Result: passed. `dart run ...` hit the known Dart AOT snapshot issue; the wrapper's direct-Dart fallback succeeded for agent-docs and workspace hygiene.
- Shadow browser smoke confirms Gmail review demo still loads without live Gmail/OAuth/native-host interaction.
  - Result: passed on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-source-url-smoke#gmail-intake`.
  - Browser verified page identity, nonblank content, no framework overlay, clean console, and demo-load interaction.
  - Browser screenshot capture timed out; local Chromium CDP fallback captured post-demo screenshot evidence at `C:\Users\FA507\AppData\Local\Temp\gmail_source_url_smoke_after_demo.png`.

## Rollout And Fallback
- Publish through PR-first flow only after validation: commit, push branch, ready PR, wait for green checks, merge normally, fast-forward `main`, prune, and remove feature worktree after confirming merge.
- Stop if GitHub auth, PR creation, checks, merge, or validation fails.

## Risks And Mitigations
- Risk: source URL precedence drift breaks Return-to-Gmail or `load-message` provenance. Mitigation: tests assert exact precedence and the existing payload helper delegates to the builder.
- Risk: accidental sanitization/HTML behavior change. Mitigation: preserve dynamic values as plain strings and keep safe DOM writes in the existing renderer.

## Assumptions And Defaults
- No live Gmail testing is in scope.
- The existing shadow Gmail demo is sufficient rendered smoke for this frontend-only refactor.
- Known Dart AOT launcher issue should be recorded only if the validation wrapper reports direct-Dart fallback success.
