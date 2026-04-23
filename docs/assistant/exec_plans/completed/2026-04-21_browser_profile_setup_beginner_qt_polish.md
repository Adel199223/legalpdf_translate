# Browser Profile Setup Beginner Qt Polish

## 1. Title
Browser Profile Setup Beginner Qt Polish

## 2. Goal and non-goals
Goal:
- Make the `ui=qt` `#profile` route read like a normal setup screen for document, Gmail, and interpretation travel details.
- Add a beginner-friendly interpretation distance editor that syncs with the existing `travel_distances_by_city` JSON contract.

Non-goals:
- No backend API, profile persistence, Gmail, translation, interpretation, route-id, or `ui=legacy` behavior changes.
- No redesign of Settings, Power Tools, or Extension Lab.

## 3. Scope (in/out)
In:
- Profile shell/nav/topbar copy for `ui=qt`
- Profile main panel, help card, editor drawer copy
- Browser-only profile presentation helper(s)
- Visible distance list/add/update/remove UX plus advanced JSON recovery area
- Tests and Downloads deliverables for this pass

Out:
- Backend serialization changes
- New profile APIs
- Broader operator-surface wording cleanup

## 4. Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/browser-new-job-qt-polish`
- base branch: `main`
- base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- target integration branch: `main`
- canonical build status or intended noncanonical override: canonical browser-shell UX pass on the current approved feature floor; validation pending after implementation

## 5. Interfaces/types/contracts affected
- Browser-shell presentation only:
  - `#profile` remains unchanged
  - existing profile endpoints remain unchanged
  - existing `travel_distances_by_city` payload shape remains unchanged
- Add browser-only helper module for profile presentation and distance-row normalization/serialization

## 6. File-by-file implementation steps
- `src/legalpdf_translate/browser_app_service.py`
  - Update profile nav label/description for the beginner setup framing.
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - Rewrite beginner-visible profile page and drawer copy.
  - Add visible interpretation distance editor UI and advanced JSON recovery area.
- `src/legalpdf_translate/shadow_web/static/state.js`
  - Treat `profile` as a beginner surface for `ui=qt` operator-off sessions.
- `src/legalpdf_translate/shadow_web/static/profile_presentation.js`
  - Add pure helpers for profile copy, status text, and distance row normalization/serialization.
- `src/legalpdf_translate/shadow_web/static/app.js`
  - Remove profile from operator-route-only chrome behavior.
  - Add profile topbar state.
  - Use profile presentation helpers for main-card/list rendering, button copy, and distance editor sync.
- `src/legalpdf_translate/shadow_web/static/style.css`
  - Add any light styles needed for the distance editor list/inputs and advanced area.
- `tests/test_shadow_web_api.py`
  - Assert beginner-friendly profile copy and absence of old bounded/runtime/JSON-first wording.
- `tests/test_shadow_web_route_state.py`
  - Assert `#profile` remains routable and behaves like a beginner/setup surface in qt/operator-off mode.
- `tests/test_profile_browser_state.py`
  - Add focused ESM helper coverage for profile presentation and distance-row behavior.

## 7. Tests and acceptance criteria
- Validation:
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1`
  - `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_shadow_web_index_contains_beginner_first_shell_sections`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_runtime_service.py::test_browser_profile_management_and_joblog_delete_helpers`
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_profile_browser_state.py`
  - `powershell -ExecutionPolicy Bypass -File scripts/create_review_bundle.ps1`
- Acceptance:
  - Profile route reads like setup, not an operator/runtime surface.
  - Main profile is obvious.
  - City distances are manageable without editing raw JSON.
  - Raw JSON remains available only as advanced recovery.

## 8. Rollout and fallback
- Roll out as browser-only copy/presentation changes plus additive helper module.
- If distance-editor sync proves fragile, keep the advanced JSON fallback visible in the same drawer rather than changing the backend contract.

## 9. Risks and mitigations
- Risk: profile route loses operator access to technical details.
  - Mitigation: keep diagnostics/details and operator mode behavior intact; only remove beginner-visible prominence.
- Risk: visible distance editor drifts from saved JSON.
  - Mitigation: make helper-based normalization/serialization the single source of truth and test JSON resync.
- Risk: profile route topbar/beginner-surface change regresses shell behavior.
  - Mitigation: extend existing route-state tests rather than introducing route-specific ad hoc logic.

## 10. Assumptions/defaults
- Visible shell/page label stays `Profiles`.
- Beginner-visible copy uses `main profile` while backend/internal state keeps `primary_profile_id`.
- Visible distance editor rejects blank city and non-positive km values even though backend normalization is more permissive.
- No docs sync beyond the ExecPlan is required unless implementation reveals a direct user-guide mismatch.
