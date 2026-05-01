# Browser New Job Source/Action Hardening

## Goal and non-goals
- Goal: harden the browser `ui=qt` `#new-job` source card and action rail so the polished beginner flow stays correct during manual upload, prepared Gmail replacement, failure recovery, and loaded-job transitions.
- Goal: make source readiness and action enablement explicit, centralized, and testable.
- Goal: preserve the visible beginner-first surface while preventing invalid actions and stale source summaries.
- Non-goal: change backend translation APIs, Gmail intake/finalization routing, interpretation flows, completion drawers, or route/runtime contracts.
- Non-goal: redesign the broader browser shell beyond the low-risk pre-hydration operator-chrome hide.

## Scope (in/out)
- In scope:
  - `src/legalpdf_translate/shadow_web/templates/index.html`
  - `src/legalpdf_translate/shadow_web/static/translation.js`
  - browser-state and markup tests covering source/action edge cases
- Out of scope:
  - translation backend/job-manager changes
  - Gmail intake UI redesign
  - completion drawer redesign
  - interpretation redesign
  - `ui=legacy` changes

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-new-job-qt-polish`
- base branch: `main`
- base SHA: `f70d65c92df8`
- target integration branch: `main`
- canonical build status: canonical worktree on top of approved base floor `4e9d20e`

## Interfaces/types/contracts affected
- Preserve:
  - `?mode=live|shadow`
  - `?workspace=<id>`
  - `#new-job`
  - `#gmail-intake`
  - `ui=legacy`
  - `/api/translation/upload-source`
  - existing translation form field names
  - prepared Gmail launch payload shape
- Add only additive browser-side helpers for:
  - centralized source readiness/state derivation
  - centralized action-rail state derivation

## File-by-file implementation steps
1. Update `translation.js`:
   - add pure source/action derivation helpers
   - add transactional upload state for local staging and prepared Gmail rollback
   - refactor source card, action rail, and upload resolution to consume the helpers
   - make loaded jobs authoritative for visible source summaries
   - improve source-card click targeting without changing keyboard behavior
2. Update `index.html`:
   - set `data-operator-chrome` during inline bootstrap so operator-only details stay hidden on initial beginner loads
3. Update tests:
   - extend Node-backed browser-state coverage to drive real source upload success/failure paths
   - add assertions for idle, prepared, uploading, error, successful manual staging, and loaded-job source replacement
   - tighten markup/bootstrap assertions for pre-hydration operator-chrome state

## Tests and acceptance criteria
- Targeted validation:
  - `python -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
  - `python -m compileall src tests`
  - `dart run tooling/validate_agent_docs.dart` if ExecPlan/docs are changed
  - `dart run tooling/validate_workspace_hygiene.dart` if available
  - if `dart run` is broken, use the direct Dart executable and report that explicitly
- Acceptance:
  - the polished `ui=qt` `#new-job` screen stays visually consistent while invalid actions remain disabled
  - prepared Gmail sources survive failed local replacement attempts intact
  - non-Gmail local staging failures are recoverable without refresh
  - translation starts/analyzes only from the visible ready source
  - loaded jobs replace stale source summaries when their source differs

## Rollout and fallback
- Keep all changes browser-side and additive around the existing translation flow.
- If transactional upload handling conflicts with prepared Gmail behavior, prefer preserving the prepared Gmail source and narrowing the local staging behavior.
- If the pre-hydration operator-chrome tweak proves risky, keep the existing hydrated gating and drop only that polish.

## Risks and mitigations
- Risk: source rollback leaves manual cache or hidden fields stale.
  - Mitigation: centralize reset/commit helpers and assert rollback behavior in Node-backed tests.
- Risk: action gating drifts from job action flags.
  - Mitigation: funnel all button enablement through one pure helper that still respects existing `job.actions`.
- Risk: source-card click targeting breaks existing controls.
  - Mitigation: ignore interactive descendants and keep the explicit browse button as the primary keyboard entry point.

## Assumptions/defaults
- The current worktree remains the active implementation worktree; no extra `git worktree` split is needed for this scoped follow-up.
- The beginner UI should remain visually unchanged except for safer helper copy and button states.
- Docs sync remains deferred unless this pass creates an immediate user-facing docs mismatch beyond the ExecPlan lifecycle update.

## Outcome
- Added a centralized browser-side source state helper and action state helper for the qt `#new-job` flow.
- Made local source replacement transactional so prepared Gmail attachments survive failed local replacement attempts intact.
- Disabled invalid start/analyze/cancel/resume/rebuild states from one action-rail path and prevented empty-job cancel/rebuild/resume requests.
- Updated the source card to open the file picker on card clicks, ignore interactive descendants, and keep loaded-job source summaries authoritative.
- Added pre-hydration `data-operator-chrome` gating so operator-only chrome stays hidden on initial beginner loads.

## Validation
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
  - Result: `53 passed`
- `python -m compileall src tests`
  - Result: succeeded
- `dart run tooling/validate_agent_docs.dart`
  - Result: failed in this environment with `Unable to find AOT snapshot for dartdev`
- `dart run tooling/validate_workspace_hygiene.dart`
  - Result: failed in this environment with `Unable to find AOT snapshot for dartdev`
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart`
  - Result: `PASS`
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart`
  - Result: `PASS`
