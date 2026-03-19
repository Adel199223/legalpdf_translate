# Browser Parity Stage 1: Shell Foundation

## Goal and non-goals
- Goal: turn the interpretation-only shadow page into a real browser app shell with routed sections, runtime-mode switching, recent jobs, settings/profile summaries, and an Extension Lab.
- Goal: keep the existing interpretation workflow operational while the shell expands around it.
- Non-goal: ship translation browser workflows in this stage.
- Non-goal: ship Gmail batch/reply browser workflows in this stage.

## Scope (in/out)
- In scope:
  - master browser shell and route navigation
  - `shadow`/`live` runtime mode resolution
  - workspace identity in the URL and API payloads
  - `Dashboard`, `New Job`, `Recent Jobs`, `Settings`, `Profile`, and `Extension Lab`
  - browser APIs for runtime mode, workspaces, settings/profile summaries, recent jobs, and extension diagnostics/simulation
  - rebrand UI copy away from “shadow v1 only”
- Out of scope:
  - translation execution APIs
  - Gmail batch execution APIs
  - glossary/calibration/admin tool browser workflows

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical worktree approved for latest browser/runtime work.

## Interfaces/types/contracts affected
- New or expanded APIs:
  - `GET /api/runtime-mode`
  - `POST /api/runtime-mode`
  - `GET /api/workspaces/current`
  - `GET /api/joblog/recent`
  - `GET /api/settings/summary`
  - `GET /api/profile/summary`
  - `GET /api/extension/diagnostics`
  - `POST /api/extension/simulate-handoff`
- Browser shell route contract:
  - URL query contains workspace id and runtime mode
  - view routing stays client-side in Stage 1

## File-by-file implementation steps
1. Extend `src/legalpdf_translate/shadow_runtime.py` with browser-data target resolution for `shadow` and `live` modes.
2. Add a browser-shell aggregation service under `src/legalpdf_translate/` for bootstrap, recent-job, settings/profile, and extension-lab data.
3. Refactor `src/legalpdf_translate/shadow_web/app.py` to resolve runtime targets per request and serve the new Stage 1 APIs.
4. Replace the single interpretation page in `src/legalpdf_translate/shadow_web/templates/index.html` with a browser shell that contains all Stage 1 sections.
5. Split the browser JS into ES-module files and keep the existing interpretation functionality under the `New Job` section.
6. Add targeted API/runtime tests and shell smoke assertions.

## Tests and acceptance criteria
- Browser bootstrap succeeds in both `shadow` and `live` runtime modes.
- Runtime mode and workspace identity are echoed by shell APIs and visible in the UI.
- Existing interpretation upload/save/export behavior still works through the new shell.
- Recent jobs, settings/profile summaries, and extension diagnostics render without breaking the shell.

## Rollout and fallback
- Land Stage 1 only in this pass.
- Do not start Stage 2 implementation until the exact continuation token `NEXT_STAGE_2` is received.

## Risks and mitigations
- Risk: shell expansion breaks the existing interpretation page.
  - Mitigation: keep interpretation endpoints intact and preserve targeted tests for the existing flow.
- Risk: live mode writes to live data unexpectedly.
  - Mitigation: explicit runtime-mode toggle plus visible live banner and per-request mode resolution.

## Assumptions/defaults
- Client-side view routing is sufficient for Stage 1.
- Stage 1 may expose not-yet-implemented translation/Gmail browser cards as explicit upcoming surfaces rather than fake working flows.
