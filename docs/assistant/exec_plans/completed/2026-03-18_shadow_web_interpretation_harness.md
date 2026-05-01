# Local Browser-Hosted Shadow App for Interpretation Flow

## Goal and non-goals
- Goal: add a local-only browser-hosted shadow surface for the interpretation workflow so UI/flow work can be validated in a browser without replacing the Qt desktop app.
- Goal: extract interpretation-specific business logic from Qt orchestration into a shared backend service used by both Qt and the new shadow surface.
- Goal: keep the shadow surface isolated from live desktop settings, job log state, Gmail bridge runtime, and default ports.
- Non-goal: replace the Qt app as the canonical product.
- Non-goal: ship a full web product or broad translation workflow in this pass.
- Non-goal: include Gmail intake, Gmail draft creation, or browser extension flows in the shadow surface v1.

## Scope (in/out)
- In scope:
  - shared interpretation service extraction
  - local shadow runtime state and server entrypoint
  - FastAPI + server-rendered browser UI for interpretation-only flows
  - interpretation autofill from notification PDF and photo/screenshot
  - interpretation job-log save/history in isolated shadow storage
  - interpretation honorarios DOCX/PDF generation with calm local-only fallback
  - browser automation preflight visibility in the shadow UI and runtime metadata
- Out of scope:
  - translation workflow browser UI
  - Gmail bridge reuse or live extension automation
  - replacing Qt dialogs with browser-first code paths
  - remote hosting or deployment

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical worktree allowed by build policy; implementation targets the active latest-feature worktree because canonical `main` is currently dirty and missing core source files.

## Interfaces/types/contracts affected
- New server entrypoint: `legalpdf_translate.shadow_web.server`
- New shared interpretation service module for:
  - autofill
  - seed building
  - payload normalization
  - isolated job-log persistence
  - honorarios export orchestration
- New shadow runtime/state helpers for isolated app-data root and runtime metadata
- New local HTTP API contract:
  - `GET /api/bootstrap`
  - `GET /api/capabilities`
  - `POST /api/interpretation/autofill-notification`
  - `POST /api/interpretation/autofill-photo`
  - `POST /api/interpretation/save-row`
  - `POST /api/interpretation/export-honorarios`
  - `GET /api/interpretation/history`

## File-by-file implementation steps
1. Add a shared interpretation service module under `src/legalpdf_translate/` and move/duplicate-free the Qt-trapped interpretation business logic into it.
2. Refactor Qt dialogs/app-window interpretation code to call the shared service instead of owning the business rules directly.
3. Add isolated shadow runtime state helpers for settings path, job-log DB path, output root, runtime metadata, and listener ownership checks.
4. Add a new `shadow_web` package with:
   - FastAPI app factory
   - server entrypoint
   - templates/static assets
   - API response shaping and capability gating
5. Add dependency and packaging updates for FastAPI/Jinja/uvicorn/python-multipart and include the new package in local execution.
6. Add targeted tests for:
   - shared interpretation service
   - Qt regression through the shared service
   - isolated shadow state
   - shadow API behavior
   - browser automation preflight rendering

## Tests and acceptance criteria
- Shared interpretation service returns the same interpretation seed and payload shapes previously used by Qt.
- Qt interpretation autofill/save/export paths continue to pass targeted tests after the extraction.
- Shadow runtime never writes to the live desktop app settings path or default Gmail bridge port.
- Shadow server reports browser automation preflight as unavailable on the current machine until Playwright is repaired.
- Shadow interpretation browser flow supports upload -> autofill -> edit -> save -> export.
- Honorarios PDF failure keeps DOCX success and returns a clear local-only recovery state.

## Rollout and fallback
- Roll out as a separate local entrypoint only; do not wire it into the Qt app menus in this pass.
- If browser automation remains unavailable, the server/UI still ships with visible preflight diagnostics and manual browser testing remains possible.
- If the shared service extraction causes regressions, Qt remains the reference behavior and the extraction is corrected before expanding the browser surface.

## Risks and mitigations
- Risk: duplicated business rules between Qt and browser layers.
  - Mitigation: centralize interpretation rules in one shared backend service and keep browser JS presentation-only.
- Risk: shadow runtime pollutes live user state.
  - Mitigation: separate namespace and worktree-keyed state root; no live-path defaults.
- Risk: Word/PDF and OCR host dependencies behave differently in browser-triggered flows.
  - Mitigation: keep those capabilities backend-owned and return explicit capability/failure states.
- Risk: Playwright is not healthy on the current machine.
  - Mitigation: surface preflight as first-class status and keep smoke validation blocked until repaired.

## Assumptions/defaults
- The browser-hosted version is a testing harness first.
- V1 covers interpretation flow only.
- Shadow state is isolated by default.
- FastAPI plus server-rendered templates is the v1 stack.
- Future web ambitions may reuse the shared backend contract, but this pass does not commit the repo to a full web rewrite.
