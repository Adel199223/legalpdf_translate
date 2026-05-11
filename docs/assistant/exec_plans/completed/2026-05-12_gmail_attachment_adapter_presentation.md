# Gmail Attachment Adapter Presentation ExecPlan

## Goal And Non-Goals
Move the Gmail attachment review adapter render helpers out of `gmail.js` into a focused static module while preserving the existing safe DOM renderer, pure presentation builders, exported compatibility surface, event listeners, selectors, dataset names, payloads, routes, and Gmail/native-host behavior.

Non-goals:
- Do not redesign the attachment review UI.
- Do not change row/detail DOM IDs, classes, datasets, routes, API payloads, or submitted values.
- Do not touch live Gmail, OAuth, native-host, or real drafts.

## Scope
In:
- Add a focused `gmail_attachment_adapter.js` module for adapter render helpers.
- Keep `gmail_attachment_presentation.js` as the pure data-shaping module.
- Keep `gmail_attachment_ui.js` as the safe DOM renderer.
- Re-export adapter helpers from `gmail.js` for compatibility while removing their implementation from the coordinator.
- Add contract/ESM/static asset coverage and validate in shadow mode.

Out:
- Backend changes, Gmail extension changes, selector changes, and live Gmail testing.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_attachment_adapter_presentation`
- Branch name: `codex/gmail-attachment-adapter-presentation`
- Base branch: `main`
- Base SHA: `3d3a051d0e7081abb1926e3c8d42336b492691e2`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use browser `mode=shadow` only.

## Interfaces/Types/Contracts Affected
- Internal browser static module interface only.
- Preserve public compatibility exports from `gmail.js`: `renderAttachmentListInto` and `renderReviewDetailInto`.
- New static module exports: `renderAttachmentListInto` and `renderReviewDetailInto`.
- Existing renderer contracts from `gmail_attachment_ui.js` and presentation shapes from `gmail_attachment_presentation.js` remain unchanged.

## File-By-File Implementation Steps
- `tests/test_shadow_web_api.py`: add failing contract coverage for the new adapter module, compatibility re-exports, purity boundaries, and static asset serving.
- `src/legalpdf_translate/shadow_web/static/gmail_attachment_adapter.js`: create adapter helpers that build presentation data and call safe renderers.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import adapter helpers for internal use and re-export them for compatibility; remove inline adapter helper implementations.
- `docs/assistant/exec_plans/...`: move this plan to `completed/` with validation evidence before commit.

## Tests And Acceptance Criteria
- RED first: targeted adapter contract test fails before implementation.
- GREEN targeted adapter test and static asset graph test.
- Focused browser/Gmail suite passes.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passes; record the known Dart AOT issue only if direct-Dart fallback succeeds.
- Browser shadow smoke verifies Gmail intake demo attachment load, review drawer row/detail rendering, preview interaction, console health, and screenshot evidence.

## Rollout And Fallback
- Publish as a ready PR after validation.
- Merge only after GitHub checks are green and PR is mergeable.
- If auth, CI, conflicts, or mergeability fail, stop at the highest clean point and report the blocker.
- Fallback is reverting the narrow PR; no public/backend contract migration is involved.

## Risks And Mitigations
- Risk: existing imports from `gmail.js` break. Mitigation: keep compatibility re-exports and contract tests.
- Risk: attachment safe rendering regresses. Mitigation: keep `gmail_attachment_ui.js` unchanged and test no `innerHTML` usage in adapter/presentation paths.
- Risk: Gmail row/detail behavior changes. Mitigation: preserve presentation builder inputs and smoke the shadow Gmail demo.

## Assumptions/Defaults
- No live Gmail/OAuth/native-host testing is in scope.
- No route, backend payload, submitted value, selector, dataset, Gmail/native-host, or extension contract changes are allowed.
- The user authorized the PR-first implementation, validation, publish, merge, and cleanup flow.

## Validation Log
- 2026-05-12 RED confirmed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_adapter_module_owns_review_attachment_adapters` failed because `gmail_attachment_adapter.js` did not exist.
- 2026-05-12 Targeted attachment/static contracts passed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_presentation_module_derives_list_and_detail_state tests/test_shadow_web_api.py::test_gmail_attachment_adapter_module_owns_review_attachment_adapters tests/test_shadow_web_api.py::test_gmail_attachment_ui_module_owns_review_attachment_renderers tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph` -> 4 passed.
- 2026-05-12 Focused browser/Gmail suite passed: `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py` -> 211 passed.
- 2026-05-12 Full validation passed: `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`. The wrapper reported the known `dart run` / `dartdev` AOT snapshot issue for agent docs and workspace hygiene validation, then direct-Dart fallback succeeded for both.
- 2026-05-12 Browser shadow smoke passed on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-attachment-adapter-smoke#gmail-intake`: page title `LegalPDF Translate`, nonblank content, no framework overlay, console had 0 warnings/errors, demo attachment loaded, review row/detail rendered safely, preview opened a PDF canvas (`gmail-preview-canvas` 827x1070), selecting the attachment updated row/detail state, and screenshot evidence was captured as `gmail-attachment-adapter-smoke.png`.

## Completion
- Completed 2026-05-12.
