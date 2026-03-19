# Browser Parity Program for LegalPDF Translate

## Goal and non-goals
- Goal: evolve the current browser-hosted shadow surface into a parity-oriented local browser app that can eventually cover the latest desktop workflows.
- Goal: keep Qt/PySide6 as the stable canonical shell until browser parity is proven through staged acceptance.
- Goal: preserve a safe default by keeping browser state isolated unless the user explicitly switches to live mode.
- Goal: keep the real Gmail extension canonical while adding a browser-hosted Extension Lab for repeatable diagnostics and simulator-driven QA.
- Non-goal: replace the desktop app in one pass.
- Non-goal: commit this program to public or remote hosting.
- Non-goal: silently merge browser and desktop state models.

## Scope (in/out)
- In scope:
  - staged browser shell expansion under `src/legalpdf_translate/shadow_web/`
  - shared browser/backend service contracts for settings, job log, extension diagnostics, interpretation, and later translation/Gmail flows
  - runtime-mode selection (`shadow` vs `live`) with visible provenance
  - extension diagnostics and simulator surfaces alongside the real extension
  - parity checklisting against `APP_KNOWLEDGE.md`
- Out of scope:
  - remote deployment
  - deleting or downgrading the Qt desktop shell
  - replacing the real Gmail extension with a browser-only mock

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical worktree allowed by build policy; this worktree contains the approved in-progress browser/runtime fixes that the current parity program must extend.

## Interfaces/types/contracts affected
- Expanded local browser HTTP API groups:
  - `/api/bootstrap`, `/api/capabilities`, `/api/runtime-mode`, `/api/workspaces/*`
  - `/api/joblog/*`, `/api/settings/*`, `/api/profile/*`
  - `/api/extension/*`
  - later: `/api/translation/*`, `/api/gmail/*`
- Shared response envelope shape:
  - `status`
  - `normalized_payload`
  - `diagnostics`
  - `capability_flags`
- Runtime-mode/browser workspace contract:
  - isolated `shadow` mode by default
  - explicit `live` mode only when selected
  - workspace identity carried in the browser URL and echoed by APIs

## File-by-file implementation steps
1. Add a browser-parity foundation service layer that aggregates runtime-mode resolution, browser bootstrap data, recent-job summaries, settings/profile summaries, and extension diagnostics.
2. Extend `shadow_runtime.py` so the browser app can resolve both isolated shadow paths and explicit live-mode paths without silent fallback.
3. Refactor `shadow_web/app.py` to serve a browser shell rather than an interpretation-only page and to expose the new Stage 1 APIs.
4. Rebuild the browser UI into a routed multi-section shell with room for future parity stages while preserving the existing interpretation flow.
5. Add an Extension Lab that reuses native-host and extension-diagnostics helpers already used by the packaged extension.
6. Add tests and browser validation for each stage before advancing.

## Tests and acceptance criteria
- Each closed stage has:
  - targeted API/service tests
  - browser smoke validation
  - updated parity checklist evidence
- Browser responses always include runtime mode, workspace identity, and clear provenance.
- Live mode never activates implicitly.
- Extension Lab diagnostics reflect the actual host/runtime state without replacing the real extension.

## Rollout and fallback
- Roll out in strict stage order.
- Stop at each stage boundary and require the exact continuation token for the next stage.
- If a stage destabilizes a working browser or desktop flow, revert that stage’s browser-surface changes before proceeding.

## Risks and mitigations
- Risk: browser parity drift from the desktop app.
  - Mitigation: use `APP_KNOWLEDGE.md` as the parity checklist source and keep backend behavior in shared services.
- Risk: accidental live-data mutation.
  - Mitigation: isolated-by-default runtime mode, visible `LIVE DATA` banner, and no silent mode switching.
- Risk: extension/browser QA diverges from the real Gmail extension.
  - Mitigation: keep the real extension canonical and treat the Extension Lab as diagnostics plus simulation only.

## Assumptions/defaults
- This program is staged and stage-gated.
- Stage 1 is browser-shell foundation work, not translation/Gmail parity yet.
- Translation browser parity is planned for Stage 2, Gmail parity for Stage 3, admin/power tools for Stage 4, and final parity audit for Stage 5.
- The existing worktree remains the only implementation target until the parity program is accepted.
