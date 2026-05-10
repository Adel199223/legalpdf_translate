# Gmail Review Detail Adapter Presentation

## Goal And Non-Goals

Extract the remaining Gmail review-detail state shaping from `gmail.js` into a pure attachment presentation adapter, keeping the existing safe DOM renderer and Gmail contracts unchanged.

Non-goals: no backend routes, payloads, submitted values, selector IDs, dataset names, Gmail/native-host behavior, live Gmail/OAuth flow, or renderer text-safety changes.

## Scope

In scope:
- Add a pure `buildGmailReviewDetailAdapterPresentation(...)` helper in `gmail_attachment_presentation.js`.
- Update `gmail.js` so `renderReviewDetailInto(...)` delegates presentation shaping to that helper, then calls `renderGmailReviewDetailInto(...)`.
- Add ESM/contract coverage for the adapter and static asset export.
- Run focused and full validation plus shadow Browser smoke.
- Publish through a ready PR and merge after green checks.

Out of scope:
- Live Gmail testing, OAuth testing, native-host testing, route/API changes, and unrelated cleanup.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_review_detail_adapter`
- Branch name: `codex/gmail-review-detail-adapter`
- Base branch: `main`
- Base SHA: `dced666ddb7e5b78770ede81436df4817766cd7a`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; shadow-mode browser validation only.

## Interfaces, Types, And Contracts Affected

- `renderReviewDetailInto(container, attachment, options)` remains exported from `gmail.js`.
- `renderGmailReviewDetailInto(container, presentation)` remains the safe DOM-only renderer.
- Existing IDs/datasets/routes/listeners/payloads remain unchanged, including `gmail-review-detail-start`, `data-detail-start-page`, `gmail-preview-selected`, and `data-preview-selected`.
- Dynamic text continues flowing through presentation data and safe DOM writes.

## File-By-File Implementation Steps

- `src/legalpdf_translate/shadow_web/static/gmail_attachment_presentation.js`: export `buildGmailReviewDetailAdapterPresentation(...)` and delegate to the existing `buildGmailReviewDetailPresentation(...)`.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import the adapter helper and simplify `renderReviewDetailInto(...)` to gather options/state and hand off shaping.
- `tests/test_shadow_web_api.py`: add failing contract/ESM/static route expectations first, then update after implementation only if needed.
- `docs/assistant/exec_plans/active/2026-05-10_gmail_review_detail_adapter.md`: record progress, validations, and move to `completed/` before commit.

## Tests And Acceptance Criteria

Red first:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_presentation_module_derives_list_and_detail_state tests/test_shadow_web_api.py::test_gmail_attachment_ui_module_owns_review_attachment_renderers`

After implementation:
- Same targeted tests pass.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`

Browser smoke:
- Launch shadow app on port `8888`.
- Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`.
- Confirm page identity, nonblank content, no framework overlay, console health, screenshot evidence, and shadow Gmail review-detail behavior without touching live Gmail.

## Rollout And Fallback

Publish flow after validation:
- Stage only intended files.
- Commit `Extract Gmail review detail adapter presentation`.
- Push `codex/gmail-review-detail-adapter`.
- Create ready PR `[codex] Extract Gmail review detail adapter presentation`.
- Wait for green CI, merge normally, fast-forward canonical `main`, prune refs, and remove the feature worktree only after `main` contains the merge.

Fallback: stop before merge if auth fails, PR creation fails, CI is red, conflicts appear, or required checks remain unexpectedly pending.

## Risks And Mitigations

- Risk: wrapper compatibility drift for explicit `startPage`, `canEditStart`, `previewLoaded`, or malicious filenames. Mitigation: ESM adapter probes and existing safe-rendering browser tests.
- Risk: hidden DOM contract changes. Mitigation: ownership tests assert renderer location and static asset export; no selector/dataset edits.
- Risk: broad refactor creep. Mitigation: only touch the adapter module, `gmail.js`, tests, and this ExecPlan.

## Assumptions And Defaults

- No live Gmail/OAuth/native-host testing is in scope.
- The pure adapter receives already-derived coordinator facts and must not read global runtime state.
- The feature PR should be ready for review/merge after validations pass.

## Progress And Validation

- Created the isolated worktree at `C:\Users\FA507\.codex\legalpdf_translate_gmail_review_detail_adapter` on `codex/gmail-review-detail-adapter`.
- Added failing contract tests first. Initial targeted run failed because `buildGmailReviewDetailAdapterPresentation` did not exist in the presentation module or `gmail.js`.
- Implemented the pure adapter helper and delegated `renderReviewDetailInto(...)` through it.
- Targeted tests passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_attachment_presentation_module_derives_list_and_detail_state tests/test_shadow_web_api.py::test_gmail_attachment_ui_module_owns_review_attachment_renderers`
- Focused browser/Gmail suite passed:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
  - Result: `200 passed`.
- Full validation passed:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - The wrapper hit the known Dart AOT launcher issue for agent-docs and workspace-hygiene validation, then reported direct-Dart fallback success for both.
- Browser smoke:
  - Launched the shadow server from this feature worktree on port `8888`.
  - Verified `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake` for page identity, nonblank Gmail demo content, clean console, and no framework overlay.
  - Verified shadow Gmail review-detail content for `demo-gmail-review.pdf`.
  - Verified PDF preview controls and `gmail-preview-canvas`; a fresh shadow workspace confirmed preview href `/api/gmail/attachment/demo-gmail-review-pdf?mode=shadow&workspace=gmail-review-detail-smoke#page=1`.
  - No live Gmail/OAuth/native-host flow was touched.
  - The final canvas screenshot call timed out, but Browser emitted earlier screenshot evidence of the preview state during the same smoke run.
- Independent review:
  - Reviewer reported no findings.
  - Reviewer noted a residual test gap for the adapter's default translation-PDF derivation path; added `adapterDefaultPdfDetail` ESM coverage and reran the targeted presentation/ownership tests plus safe-rendering test successfully.
