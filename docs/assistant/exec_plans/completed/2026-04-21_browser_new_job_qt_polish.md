# Browser New Job Qt Polish

## Goal and non-goals
- Goal: make the default browser `ui=qt` `#new-job` translation screen feel closer to the Qt dashboard's first-run experience without changing translation workflow semantics.
- Goal: de-technicalize the first-run browser surface, polish the source picker, improve destination/language presentation, add a richer run-status area, and anchor the primary action rail.
- Goal: preserve Gmail prepared translation launches and keep operator/runtime controls reachable without leaving them on the beginner surface by default.
- Non-goal: change Gmail routing/finalization behavior, interpretation workflows, live-vs-shadow semantics, or backend translation pipeline behavior.
- Non-goal: remove direct-route/operator surfaces or `ui=legacy`.

## Scope (in/out)
- In scope:
  - `src/legalpdf_translate/shadow_web/templates/index.html`
  - `src/legalpdf_translate/shadow_web/static/style.css`
  - `src/legalpdf_translate/shadow_web/static/app.js`
  - `src/legalpdf_translate/shadow_web/static/translation.js`
  - browser-focused tests for markup and translation UI state
- Out of scope:
  - Gmail intake route redesign
  - interpretation redesign
  - translation backend/job-manager changes
  - new browser runtime modes or route contracts

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
  - existing translation form field names and prepared Gmail launch payloads
- Add only additive browser-side view-model helpers for:
  - staged/manual source-card state
  - run-status presentation derived from existing job payloads

## File-by-file implementation steps
1. Update the `ui=qt` `#new-job` template:
   - de-technicalize topbar copy
   - hide beginner-facing runtime controls on the normal new-job surface
   - replace the visible raw source field with a polished source card/drop zone shell
   - convert output and language controls to beginner-friendly field presentation
   - add fixed run-status scaffold nodes and beginner helper copy
   - simplify the visible action rail heading/copy
2. Update browser shell behavior in `app.js`:
   - make topbar copy route-aware
   - gate runtime controls visibility by operator mode / secondary routes only
3. Update translation behavior in `translation.js`:
   - centralize manual source staging and reuse uploaded-source caching
   - preserve prepared Gmail source state until a user explicitly chooses a new local source
   - add derived source-card UI state and run-status UI state helpers
   - keep the run-status DOM stable during polling and job transitions
   - disable `Start Translate` until a source is ready, with friendly helper copy
4. Update styling in `style.css`:
   - add beginner-facing source-card/drop-zone styling
   - add output-summary and run-status metric styling
   - make the action rail feel footer-anchored in qt mode and stack cleanly on narrow widths
5. Update tests:
   - tighten markup assertions for qt new-job beginner copy and scaffolding
   - extend browser translation UI-state coverage for manual staging, Gmail prepared state preservation, and start-button readiness
   - add focused run-status helper coverage if a pure helper is introduced

## Tests and acceptance criteria
- Targeted validation:
  - `python -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
  - `python -m compileall src tests`
  - Node-backed JS syntax/state checks exercised through the existing pytest browser-state tests
  - `dart run tooling/validate_agent_docs.dart` if ExecPlan/docs are changed
  - `dart run tooling/validate_workspace_hygiene.dart` if available
- Acceptance:
  - qt `#new-job` reads like a guided app screen, not an operator console
  - source selection uploads immediately and shows feedback/page count when available
  - output destination defaults read cleanly without forcing raw path entry
  - target-language labels are user-friendly while keeping backend values unchanged
  - run status shows progress/metrics using existing job data
  - `Start Translate`, `Cancel`, and `...` preserve behavior
  - Gmail prepared translation launches still wait for explicit `Start Translate`

## Rollout and fallback
- Keep all changes scoped to the `ui=qt` browser shell.
- Preserve existing hidden/raw fields and operator details so regressions can fall back to current plumbing without backend changes.
- If a UI polish change conflicts with Gmail prepared state or route contracts, prefer preserving contract behavior and narrowing the polish.

## Risks and mitigations
- Risk: local-source staging could accidentally clear prepared Gmail state too aggressively.
  - Mitigation: only replace prepared state on explicit successful local selection and keep prepared summary on local staging failure.
- Risk: status-card refactor could regress polling behavior or completion drawer discovery.
  - Mitigation: keep completion drawer logic unchanged and add a pure helper for run-status derivation.
- Risk: hiding runtime controls could strand operator actions.
  - Mitigation: visibility-gate them only on beginner `#new-job`; keep them visible for operator mode and secondary routes.

## Assumptions/defaults
- Interpretation remains functionally unchanged in this pass.
- The current worktree is the active feature worktree for this task; no separate `git worktree` split is required because the repo was clean and no concurrent branch stream was already active here.
- Docs sync is deferred unless the final implementation creates an immediate touched-scope docs mismatch beyond this ExecPlan lifecycle update.

## Outcome
- Completed the `ui=qt` browser `#new-job` polish pass with route-aware beginner chrome, a staged source card, default-folder summary, Qt-like run status metrics, and an anchored action rail.
- Preserved prepared Gmail launches, operator/runtime controls on secondary or operator surfaces, existing translation field contracts, and the bounded completion/recovery surfaces.

## Validation
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
  - Result: `50 passed`
- `python -m compileall src tests`
  - Result: succeeded
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart`
  - Result: `PASS`
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart`
  - Result: `PASS`
