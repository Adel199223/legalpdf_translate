# Gmail Preview Context Shaping

## Goal And Non-Goals
- Extract Gmail preview panel record/page/href context shaping from `gmail.js` into a pure `gmail_review_state.js` helper.
- Preserve the existing preview renderer, presentation builder, DOM IDs, event listeners, selectors, routes, backend payloads, Gmail/native-host contracts, and safe rendering.
- Do not change live Gmail/OAuth/native-host behavior or public API shapes.

## Scope
- In: pure preview panel context helper, `renderPreviewPanel()` delegation, ESM coverage, structural ownership tests, shadow Gmail smoke.
- Out: preview UI copy changes, renderer rewrites, backend route changes, live Gmail testing, extension/native-host changes.

## Worktree Provenance
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_preview_context_shaping`
- Branch: `codex/gmail-preview-context-shaping`
- Base branch: `main`
- Base SHA: `717da39d3f3a67b52ea888fa93f5e1a4c6b1fdac`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree for shadow-mode validation only.

## Interfaces And Contracts
- New pure export from `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`:
  - `buildGmailPreviewPanelContext({ attachments, previewState, workflowKind })`
- Return shape feeds `buildGmailPreviewPanelPresentation(...)`:
  - `{ attachment, href, page, pageCount, canApply, isPdf, isImage }`
- `gmail.js` must remain the owner of DOM lookup, PDF canvas rendering, drawer state, API calls, and side effects.
- No backend route, payload key, DOM selector, dataset, event listener, native-host, or live Gmail contract changes.

## Implementation Steps
- Add ESM tests in `tests/test_gmail_review_state.py` for closed preview, missing attachment, PDF href page resolution, image/fallback href resolution, inspect-only PDF, invalid page/page-count defaults, malicious href trimming, and null-safe defaults.
- Update `tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping` or a focused adjacent structural test to assert the export/import and that `renderPreviewPanel()` delegates preview context shaping instead of resolving attachment/page/href inline.
- Confirm targeted tests fail before implementation.
- Implement `buildGmailPreviewPanelContext(...)` in `gmail_review_state.js` using existing normalization helpers and MIME logic equivalent to current `gmail.js` behavior.
- Update `gmail.js` imports and `renderPreviewPanel()` to call the helper and pass the context into `buildGmailPreviewPanelPresentation(...)`.
- Remove now-unneeded local preview record/page/href helper functions from `gmail.js` if no callers remain.

## Tests And Acceptance
- Red test:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping tests/test_shadow_web_api.py::test_gmail_preview_ui_module_owns_preview_panel_renderer`
- Green targeted test: same command.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke from this worktree on port `8888`:
  - `.\.venv311\Scripts\python.exe tooling\launch_browser_app_live_detached.py --mode shadow --workspace gmail-review-demo --port 8888`
  - `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`
  - Verify page identity, nonblank content, no framework overlay, console health, screenshot evidence, load demo attachments, select demo PDF, open preview, visible canvas/status, and no live Gmail/native-host flow.

## Rollout And Fallback
- Stage only intended files.
- Commit: `Extract Gmail preview context shaping`.
- Push branch, create ready PR `[codex] Extract Gmail preview context shaping`, wait for green checks, merge normally, fast-forward local `main`, prune refs, and remove the feature worktree only after `main` contains the merge.
- Fallback is to abandon the feature branch before merge; no runtime data migration or route rollback is needed.

## Risks And Mitigations
- Risk: PDF preview links lose or duplicate page fragments. Mitigation: ESM tests cover page-fragment resolution.
- Risk: invalid preview state leaks `NaN` into presentation/hrefs. Mitigation: tests cover invalid page/page-count defaults.
- Risk: accidental selector or renderer change. Mitigation: structural tests pin safe renderer ownership and focused browser/Gmail suite runs before publish.

## Assumptions
- No live Gmail/OAuth/native-host testing is in scope.
- Browser smoke uses shadow mode and isolated demo workspace only.

## Completion Notes
- Added `buildGmailPreviewPanelContext(...)` to `gmail_review_state.js` and updated `gmail.js` preview rendering/event paths to consume that pure context instead of resolving preview attachment/page/href inline.
- Targeted red test failed before implementation because the new export was missing and the old inline helpers still existed.
- Targeted green tests passed: `4 passed in 4.98s`.
- Focused browser/Gmail suite passed: `200 passed in 183.39s`.
- Full validation passed. The docs/workspace hygiene wrapper hit the known Dart AOT launcher issue, and direct-Dart fallback succeeded.
- Browser shadow smoke on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake` verified page identity, nonblank UI, no framework overlay, clean console, demo review refresh, PDF preview controls/canvas, `Use current page`, attachment selection, and no live Gmail/OAuth/native-host flow.
