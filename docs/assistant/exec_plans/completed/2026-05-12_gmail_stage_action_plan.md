# Gmail Stage Action Plan ExecPlan

## Goal And Non-Goals
Move Gmail stage action decision shaping out of `gmail.js` into a pure static planner while preserving the exact stage action strings, route IDs, hook calls, drawer behavior, dataset values, Gmail/native-host behavior, and safe rendering paths.

Non-goals:
- Do not change backend routes, payloads, submitted values, selectors, DOM IDs, datasets, or Gmail/native-host contracts.
- Do not touch live Gmail, OAuth, native-host, or real drafts.
- Do not redesign the Gmail UI or broaden event wiring beyond the stage-action paths.

## Scope
In:
- Add a focused static module that turns a stage action plus available Gmail state into a pure action plan.
- Update `gmail.js` so stage action handlers gather coordinator state, ask the planner what effects are needed, then execute the existing side effects.
- Reuse the same action execution path for the direct translation-launch and interpretation-seed buttons where behavior currently overlaps.
- Add contract, ESM probe, and static asset coverage.

Out:
- Backend changes, extension changes, live Gmail testing, and unrelated event-handler refactors.

## Worktree Provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_stage_action_plan`
- Branch name: `codex/gmail-stage-action-plan`
- Base branch: `main`
- Base SHA: `68fca9fcee02cb4f974e59d51563c6abf2c571a2`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; use browser `mode=shadow` only.

## Interfaces/Types/Contracts Affected
- New internal static module export: `buildGmailStageActionPlan(...)`.
- Existing stage action strings remain unchanged:
  - `resume-translation-recovery`
  - `resume-translation-prepared`
  - `resume-translation-running`
  - `resume-translation-save`
  - `resume-translation-finalize`
  - `open-restored-translation-finalize`
  - `resume-interpretation-review`
  - `resume-interpretation-finalize`
  - `review`
  - `open-intake`
- Existing Gmail route IDs remain unchanged: `new-job` and `gmail-intake`.

## File-By-File Implementation Steps
- `tests/test_shadow_web_api.py`: add RED contract/probe coverage for `gmail_stage_action_plan.js`, assert `gmail.js` imports/calls the planner, and add static asset graph coverage.
- `src/legalpdf_translate/shadow_web/static/gmail_stage_action_plan.js`: implement the pure planner with null-safe defaults and no DOM/render/API access.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: replace the inline `runStageAction()` switch with planner-driven side-effect execution, preserving all hook calls and drawer opens/closes.
- `docs/assistant/exec_plans/...`: move this plan to `completed/` with validation evidence before commit.

## Tests And Acceptance Criteria
- RED first: targeted stage-action planner contract fails before implementation.
- GREEN targeted stage-action and static asset tests.
- Focused browser/Gmail suite passes.
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full` passes; record the known Dart AOT launcher issue only if direct-Dart fallback succeeds.
- Browser shadow smoke verifies Gmail intake loads, demo attachments can be loaded, stage/review/preview interaction still works, console is healthy, screenshot evidence is captured, and no live Gmail/OAuth/native-host flow is touched.

## Rollout And Fallback
- Publish as a ready PR after validation.
- Merge only after GitHub checks are green and PR is mergeable.
- If auth, CI, conflicts, or mergeability fail, stop at the highest clean point and report the blocker.
- Fallback is reverting the narrow PR; no public/backend contract migration is involved.

## Risks And Mitigations
- Risk: a stage action loses a side effect. Mitigation: probe every known action string and keep side effects executed only in `gmail.js`.
- Risk: unknown action behavior changes. Mitigation: assert malformed/unknown actions fall back to `gmail-intake`.
- Risk: direct launch buttons diverge from stage actions. Mitigation: route them through the same planner/executor.

## Assumptions/Defaults
- No live Gmail/OAuth/native-host testing is in scope.
- The new export is an internal static-browser module interface only.
- The user authorized the implementation, validation, publish, merge, and cleanup flow.

## Validation Log
- 2026-05-12 Baseline targeted checks passed before edits: `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py tests/test_shadow_web_api.py::test_gmail_stage_presentation_module_derives_stage_and_home_cta_state` -> 3 passed.
- 2026-05-12 RED confirmed: `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_stage_action_plan_module_builds_stage_action_effects tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph` failed because `gmail_stage_action_plan.js` did not exist and the static asset returned 404.
- 2026-05-12 Targeted stage-action/static contracts passed: `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_stage_action_plan_module_builds_stage_action_effects tests/test_shadow_web_api.py::test_shadow_web_versioned_static_route_serves_current_browser_asset_graph` -> 2 passed.
- 2026-05-12 Focused browser/Gmail suite passed: `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py` -> 213 passed.
- 2026-05-12 Full validation passed: `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`. The wrapper reported the known `dart run` / `dartdev` AOT snapshot issue for agent docs and workspace hygiene validation, then direct-Dart fallback succeeded for both.
- 2026-05-12 Browser shadow smoke passed on `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-stage-action-smoke#gmail-intake`: page title `LegalPDF Translate`, nonblank Gmail intake content, no framework overlay, console had 0 warnings/errors, `Load demo attachments` succeeded via Browser DOM-CUA click, selecting the demo attachment revealed detail/preview controls, PDF preview opened with `gmail-preview-canvas` width 827 height 1070, open-tab href stayed `/api/gmail/attachment/demo-gmail-review-pdf?mode=shadow&workspace=gmail-stage-action-smoke#page=1`, and no live Gmail/OAuth/native-host flow was touched. In-app Browser Playwright screenshot/click paths timed out on the local page; Browser DOM/console/DOM-CUA interaction proof was used, and screenshot evidence was captured with the loopback Edge fallback at `C:\Users\FA507\AppData\Local\Temp\iab-screenshot-fallback-1778582009869.png`.

## Completion
- Completed 2026-05-12.
