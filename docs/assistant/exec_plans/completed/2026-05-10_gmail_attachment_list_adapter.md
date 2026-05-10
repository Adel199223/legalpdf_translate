# Gmail Attachment List Adapter Shaping

## Goal And Non-Goals
- Extract Gmail attachment-list adapter shaping from `gmail.js` into a pure presentation helper.
- Preserve the existing safe DOM renderer, Gmail coordinator side effects, route IDs, payload keys, selectors, dataset names, submitted values, native-host behavior, and live Gmail contracts.
- Do not touch backend routes, Gmail/OAuth/native-host flows, PDF rendering internals, or finalization behavior.

## Scope
- In: pure attachment-list adapter helper, coordinator delegation, ESM coverage, structural ownership tests, shadow Gmail smoke.
- Out: renderer rewrites, review-detail shaping, copy changes, backend routes, extension/native-host contracts, live Gmail testing.

## Worktree Provenance
- Worktree: `C:\Users\FA507\.codex\legalpdf_translate_gmail_attachment_list_adapter`
- Branch: `codex/gmail-attachment-list-adapter`
- Base branch: `main`
- Base SHA: `55fb1df804e2090df9b6da16a7cbec691df142de`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree for shadow-mode validation only.

## Interfaces And Contracts
- Add a pure export in `src/legalpdf_translate/shadow_web/static/gmail_attachment_presentation.js`:
  - `buildGmailAttachmentListAdapterPresentation({ attachments, selectionState, workflowKind, focusedAttachmentId, ...compatOptions })`
- The new helper returns the same renderer shape currently returned by `buildGmailAttachmentListPresentation(...)`.
- `gmail.js` keeps attachment lookup, state ownership, focus sync, rendering calls, event handling, API calls, and PDF preview behavior.
- `gmail_attachment_ui.js` remains the only attachment-list DOM renderer and continues using safe DOM writes.
- Existing `renderAttachmentListInto(...)` compatibility export remains available, but delegates adapter shaping to the new pure helper.

## Tests And Acceptance
- Red test first:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_presentation_module_derives_list_and_detail_state tests/test_shadow_web_api.py::test_gmail_attachment_ui_module_owns_review_attachment_renderers`
- Green targeted test: same command after implementation.
- Static asset assertion:
  - `/static-build/<asset_version>/gmail_attachment_presentation.js` serves JavaScript and exports the new adapter builder.
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - Record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.
- Browser smoke from this worktree on port `8888`:
  - `.\.venv311\Scripts\python.exe tooling\launch_browser_app_live_detached.py --mode shadow --workspace gmail-review-demo --port 8888`
  - Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`: page identity, nonblank content, no framework overlay, clean console, shadow demo attachment list, selection/start-page behavior, PDF preview path, and no live Gmail/native-host flow.

## Rollout And Fallback
- Move this ExecPlan to `completed/` after validation.
- Stage only intended code/tests and this completed ExecPlan.
- Commit: `Extract Gmail attachment list adapter shaping`.
- Push branch, create ready PR `[codex] Extract Gmail attachment list adapter shaping`, wait for green checks, merge normally, fast-forward local `main`, prune refs, and remove the feature worktree only after `main` contains the merge.
- Fallback is abandoning the feature branch before merge; no runtime data migration or route rollback is needed.

## Risks And Mitigations
- Risk: attachment selection rows drift from existing labels, datasets, or start-page values. Mitigation: ESM assertions cover PDF/image, interpretation radio mode, custom compatibility resolvers, malicious text, and null defaults.
- Risk: safe rendering weakens. Mitigation: DOM renderer remains untouched and safe-rendering/focused suites run before publish.
- Risk: coordinator still owns adapter loops. Mitigation: structural tests pin `gmail.js` to the new adapter builder and reject map/loop shaping in the exported attachment-list wrapper.

## Execution Log
- Created the feature worktree and branch from `main@55fb1df804e2090df9b6da16a7cbec691df142de`.
- Added failing contract coverage first:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_presentation_module_derives_list_and_detail_state tests/test_shadow_web_api.py::test_gmail_attachment_ui_module_owns_review_attachment_renderers`
  - Expected failure: missing `buildGmailAttachmentListAdapterPresentation(...)` export/import and missing `gmail.js` delegation.
- Implemented `buildGmailAttachmentListAdapterPresentation(...)` in `gmail_attachment_presentation.js`, using pure helpers from `gmail_review_state.js`, and updated `gmail.js` to delegate attachment-list adapter shaping to it.
- Reviewer found one compatibility issue: exported `renderAttachmentListInto(...)` defaulted PDF rows to editable without a supplied `resolveCanEditStart`. Fixed by preserving the old default `resolveCanEditStart: () => false` for wrapper callers while the internal Gmail render path explicitly supplies `canEditStartPage(...)`.
- Added regression coverage in the browser safe-rendering probe so wrapper default PDF rows remain static unless editability is explicitly supplied.
- Targeted green:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_presentation_module_derives_list_and_detail_state tests/test_shadow_web_api.py::test_gmail_attachment_ui_module_owns_review_attachment_renderers` -> `2 passed`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_presentation_module_derives_list_and_detail_state tests/test_shadow_web_api.py::test_gmail_attachment_ui_module_owns_review_attachment_renderers tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph tests/test_browser_safe_rendering.py::test_browser_dynamic_renderers_treat_external_values_as_text` -> `4 passed`
- Focused browser/Gmail suite:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py` -> `200 passed`
- Full validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` -> completed successfully.
  - The validation wrapper encountered the known Dart AOT launcher issue and reported direct-Dart fallback success for the affected docs/workspace hygiene checks.
- Independent review:
  - Initial reviewer finding was fixed; reviewer re-check reported no findings and `git diff --check` clean.
- Browser smoke:
  - Launched shadow server from the feature worktree on port `8888`.
  - Seeded the shadow Gmail review demo through `/api/gmail/demo-review`.
  - Verified `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`.
  - Confirmed page identity, nonblank content, no framework overlay text, and empty warning/error console logs.
  - Verified the attachment list row for `demo-gmail-review.pdf`, selected-state behavior, editable start-page field for translation PDF, enabled continue action after selection, and PDF preview drawer/canvas path.
  - Screenshot evidence saved at `C:\Users\FA507\AppData\Local\Temp\gmail-attachment-list-adapter-browser-smoke.png`.
  - No live Gmail/OAuth/native-host flow was touched.
