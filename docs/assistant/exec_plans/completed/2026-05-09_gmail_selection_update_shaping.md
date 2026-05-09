# Gmail Selection Update Shaping

## Goal And Non-Goals
- Extract Gmail attachment selection default/update state transitions out of `gmail.js` into pure `gmail_review_state.js` helpers.
- Preserve existing Gmail review behavior, safe rendering, payloads, selectors, routes, native-host contracts, and browser/live mode behavior.
- Do not touch live Gmail, OAuth, native-host setup, backend routes, or submitted payload shapes.

## Scope
- In: pure selection-state transition helpers, coordinator delegation in `gmail.js`, ESM/state contract tests, structural ownership tests, shadow browser smoke.
- Out: renderer changes, UI copy changes, route/API changes, live Gmail testing, extension/native-host behavior changes.

## Worktree Provenance
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_selection_update_shaping`
- Branch: `codex/gmail-selection-update-shaping`
- Base branch: `main`
- Base SHA: `a8b805532dfc1554c45e7f727adc56ec8b4edaf6`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree for shadow-mode validation only.

## Interfaces And Contracts
- New pure exports from `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`:
  - `applyGmailWorkflowSelectionDefaults({ attachments, selectionState, workflowKind })`
  - `buildGmailAttachmentSelectionUpdate({ attachments, selectionState, attachmentId, selected, workflowKind })`
- `gmail.js` must continue to own coordinator state writes, focus changes, rendering, and browser/Gmail side effects.
- No backend route, DOM ID, dataset, event listener, payload key, selector, or native-host contract changes.

## Implementation Steps
- Add ESM coverage in `tests/test_gmail_review_state.py` for translation no-op defaults, interpretation single-selection defaults, translation update clamping, interpretation update exclusivity, missing attachment no-op, object/null-safe state inputs, and malicious page input.
- Update `tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping` to assert the new exports/imports and to pin `gmail.js` delegation for `setWorkflowSelectionDefaults()` and `updateAttachmentSelection()`.
- Confirm the targeted tests fail before implementation.
- Implement the pure helpers in `gmail_review_state.js`, reusing `normalizeGmailAttachmentSelectionState`, `clampGmailAttachmentStartPage`, `deriveGmailAttachmentStartEditable`, `selectionStateFrom`, and `selectionStateEntries`.
- Update `gmail.js` imports and delegate only the state-map shaping while preserving existing early return/focus behavior.

## Tests And Acceptance
- Red test:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping`
- Green targeted test: same command.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation before publish:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke from this worktree on port `8888`:
  - `.\.venv311\Scripts\python.exe tooling\launch_browser_app_live_detached.py --mode shadow --workspace gmail-review-demo --port 8888`
  - `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`
  - Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, load demo attachments, selection workflow behavior, and no live Gmail/native-host access.

## Completion Notes
- Red confirmed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping`
  - Failed on missing `applyGmailWorkflowSelectionDefaults` export/delegation as expected.
- Targeted green:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph`
  - `3 passed in 4.93s`.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - `200 passed in 175.17s`.
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Passed. Known `dart run` AOT launcher issue appeared for agent-docs and workspace-hygiene validators; direct-Dart fallback succeeded for both.
- Code review:
  - Reviewer found no behavioral issues; residual note was to include this ExecPlan in staging.
- Browser smoke:
  - Browser on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake` confirmed page identity, nonblank content, no framework overlay, console health, screenshot evidence, demo attachment load, selected demo PDF state, and no live Gmail/native-host flow.
  - Browser Playwright-backed click/screenshot paths had CDP timeouts; Browser DOM/CUA succeeded for interaction/screenshot.
  - Standalone Playwright fallback verified selected checkbox, preview drawer, visible `gmail-preview-canvas`, and preview status `Previewing page 1 of 1...`; screenshot: `C:\Users\FA507\AppData\Local\Temp\gmail-selection-update-playwright-smoke.png`.

## Rollout And Fallback
- Stage only intended files.
- Commit: `Extract Gmail selection update shaping`.
- Push branch, create ready PR `[codex] Extract Gmail selection update shaping`, wait for green checks, merge normally, fast-forward local `main`, prune refs, and remove the feature worktree only after `main` contains the merge.
- Fallback is to abandon the feature branch before merge; no runtime data migration or route rollback is needed.

## Risks And Mitigations
- Risk: interpretation workflow accidentally allows multiple selected attachments. Mitigation: dedicated ESM tests for defaulting and update exclusivity.
- Risk: page values are clamped differently. Mitigation: tests cover PDF page-count clamping and malicious/invalid page inputs.
- Risk: accidental contract change. Mitigation: structural tests pin delegation only and focused browser/Gmail suite runs before publish.

## Assumptions
- No live Gmail/OAuth/native-host testing is in scope.
- The next roadmap step remains a small Gmail/browser modernization PR.
- Browser smoke uses shadow mode and an isolated demo workspace.
