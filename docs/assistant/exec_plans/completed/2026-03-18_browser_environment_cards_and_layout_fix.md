# Fix Browser Environment Cards and Layout Drift

## Goal and non-goals
- Goal: make the browser app dashboard environment cards truthful on first paint by using a fully hydrated capability snapshot in both `/api/bootstrap` and `/api/capabilities`.
- Goal: keep `shadow` mode isolated while reclassifying intentionally disabled shadow Gmail bridge state as informational instead of warning when live desktop bridge readiness is already present.
- Goal: harden the browser-shell card layout so long paths, IDs, and reasons wrap inside their boxes at the current desktop viewport.
- Non-goal: auto-enable or mirror live Gmail bridge settings into shadow mode.
- Non-goal: change the underlying Gmail bridge, OCR, or Word export host behavior beyond fixing browser-shell status reporting.

## Scope (in/out)
- In scope:
  - backend capability/bootstrap shaping for browser parity routes
  - Gmail bridge shadow-vs-live presentation semantics
  - dashboard/settings capability card rendering and wrap behavior
  - targeted regression tests and a live browser smoke on `127.0.0.1:8877`
- Out of scope:
  - changing canonical extension ownership
  - changing runtime-mode storage isolation rules
  - new browser-parity feature areas beyond the status/layout fixes

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_beginner_first_ux`
- Branch name: `codex/beginner-first-primary-flow-ux`
- Base branch: `main`
- Base SHA: `506dee686801d698c548ba34292ab28df4a3da02`
- Target integration branch: `main`
- Canonical build status: noncanonical parity worktree under active browser-app validation

## Interfaces/types/contracts affected
- `src/legalpdf_translate/browser_app_service.py`
- `src/legalpdf_translate/shadow_web/app.py`
- `src/legalpdf_translate/shadow_web/static/app.js`
- `src/legalpdf_translate/shadow_web/static/style.css`
- `tests/test_shadow_runtime_service.py`
- `tests/test_shadow_web_api.py`

## File-by-file implementation steps
1. Extend browser-app backend helpers so extension/bootstrap data includes additive Gmail bridge context for current mode and live desktop mode.
2. Add one shared browser capability snapshot helper used by both `/api/bootstrap` and `/api/capabilities`, including Word PDF preflight and browser automation state.
3. Reclassify Gmail bridge status into `ok` / `info` / `warn` / `bad` based on actual mode semantics instead of treating isolated shadow disablement as a warning.
4. Update browser card rendering to support the new `info` tone and consume the hydrated capability snapshot on first load.
5. Tighten card text wrapping and grid child sizing so long paths and reasons stay inside the layout.
6. Add targeted service/API regressions and revalidate via browser smoke on the main preview port.

## Tests and acceptance criteria
- `/api/bootstrap` includes `capability_flags.word_pdf_export.preflight` on first load.
- `/api/bootstrap` and `/api/capabilities` agree on Word/Gmail/browser automation capability flags.
- Shadow mode with bridge disabled locally but ready in live desktop mode yields informational Gmail bridge state, not warning.
- Dashboard environment card text wraps cleanly within the card bounds at the current desktop viewport.
- Targeted tests, JS syntax checks, Python compile checks, and a live browser smoke pass cleanly.

## Rollout and fallback
- Keep the main preview on `127.0.0.1:8877`.
- If the browser shell regresses during rollout, revert the card-classification helper and fall back to the last known Stage 5 preview while preserving the backend tests.

## Risks and mitigations
- Risk: capability snapshot hydration adds noticeable latency to bootstrap because Word preflight now runs on first paint.
  - Mitigation: reuse the same preflight shape already used by `/api/capabilities` and keep timeouts unchanged rather than adding a second probe path.
- Risk: Gmail bridge semantics become confusing if shadow and live states are mixed together.
  - Mitigation: return explicit current-mode and live-desktop context fields plus a plain-language summary.
- Risk: layout fixes unintentionally affect non-dashboard cards.
  - Mitigation: apply wrap and `min-width: 0` rules only to shared card classes and validate with a real dashboard smoke.

## Assumptions/defaults
- `shadow` mode remains isolated by default.
- A ready live desktop Gmail bridge should be visible as helpful context for shadow mode, not silently imported.
- The Word PDF warning shown in the dashboard screenshot is a bootstrap hydration bug rather than a true host failure.
