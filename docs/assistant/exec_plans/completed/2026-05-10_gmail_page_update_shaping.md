# Gmail Page Update Shaping

## Goal And Non-Goals
- Extract Gmail attachment start-page and preview page-count update shaping from `gmail.js` into pure helpers in `gmail_review_state.js`.
- Preserve the existing Gmail coordinator ownership of DOM events, side effects, rendering calls, focused attachment state, routes, payload keys, selectors, dataset names, Gmail/native-host behavior, and safe rendering.
- Do not change live Gmail/OAuth/native-host behavior or backend API contracts.

## Scope
- In: pure start-page/page-count update helpers, coordinator delegation, ESM coverage, structural ownership tests, shadow Gmail smoke.
- Out: renderer rewrites, copy changes, finalization behavior, backend routes, extension/native-host contracts, live Gmail testing.

## Worktree Provenance
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_page_update_shaping`
- Branch: `codex/gmail-page-update-shaping`
- Base branch: `main`
- Base SHA: `cd6265bb01e7028d0dae639e77c5459b0bf0ceb0`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree for shadow-mode validation only.

## Interfaces And Contracts
- New pure exports from `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`:
  - `buildGmailAttachmentStartPageUpdate({ attachment, state, value, workflowKind })`
  - `buildGmailAttachmentPageCountUpdate({ attachment, state, pageCount, workflowKind })`
- Both helpers return normalized attachment selection state objects compatible with `normalizeGmailAttachmentSelectionState(...)`.
- `gmail.js` keeps attachment lookup, state assignment, focus, rendering, API calls, PDF preview bundle handling, and UI events.
- No backend route, payload key, DOM selector, submitted value, dataset, native-host, or live Gmail contract changes.

## Tests And Acceptance
- Red test first:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping`
- Green targeted test: same command after implementation.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Browser smoke from this worktree on port `8888`:
  - `.\.venv311\Scripts\python.exe tooling\launch_browser_app_live_detached.py --mode shadow --workspace gmail-review-demo --port 8888`
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`: page identity, nonblank content, no framework overlay, clean console, demo PDF preview, start-page/page-count behavior, and no live Gmail/native-host flow.

## Rollout And Fallback
- Stage only intended code/tests and this ExecPlan after moving it to `completed/`.
- Commit: `Extract Gmail page update shaping`.
- Push branch, create ready PR `[codex] Extract Gmail page update shaping`, wait for green checks, merge normally, fast-forward local `main`, prune refs, and remove the feature worktree only after `main` contains the merge.
- Fallback is abandoning the feature branch before merge; no runtime data migration or route rollback is needed.

## Risks And Mitigations
- Risk: start page clamping changes translation scope. Mitigation: ESM tests cover PDF, image, interpretation, invalid value, and page-count clamp behavior.
- Risk: preview page-count updates preserve a stale out-of-range start page. Mitigation: tests cover high start pages clamped after page-count discovery.
- Risk: accidental selector/payload changes. Mitigation: structural tests pin coordinator delegation and focused browser/Gmail suite runs before publish.

## Execution Log
- Created the feature worktree and branch from `main@cd6265bb01e7028d0dae639e77c5459b0bf0ceb0`.
- Added failing contract coverage first:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping`
  - Expected failure: new pure builder exports were not implemented yet.
- Implemented `buildGmailAttachmentStartPageUpdate(...)` and `buildGmailAttachmentPageCountUpdate(...)` in `gmail_review_state.js`, then delegated `gmail.js` start-page and preview page-count state shaping to those helpers.
- Targeted green:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping` -> `2 passed`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py::test_gmail_review_state_storage_and_auto_open_rules tests/test_shadow_web_api.py::test_gmail_review_state_module_owns_selection_state_shaping tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_browser_safe_rendering.py::test_browser_dynamic_renderers_treat_external_values_as_text` -> `4 passed`
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py` -> `200 passed`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` -> completed successfully.
  - The validation wrapper encountered the known Dart AOT launcher issue and reported direct-Dart fallback success for the affected docs/workspace hygiene checks.
- Independent review:
  - Reviewer agent reported no implementation logic findings and `git diff --check` clean.
- Browser smoke:
  - Launched shadow server from the feature worktree on port `8888`.
  - Verified `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`.
  - Confirmed page identity, nonblank content, no framework overlay text, and empty warning/error console logs.
  - Seeded the shadow Gmail demo and verified review panel behavior without touching live Gmail/OAuth/native-host flows.
  - Entered a malicious/out-of-range start-page value through the Browser UI and verified the row/detail start-page state returned to `1` after preview page-count discovery.
  - Verified PDF preview drawer, `Open in new tab` control, page `1 of 1`, and `canvas#gmail-preview-canvas`; screenshot evidence saved at `C:\Users\FA507\AppData\Local\Temp\gmail-page-update-shaping-browser-smoke.png`.
