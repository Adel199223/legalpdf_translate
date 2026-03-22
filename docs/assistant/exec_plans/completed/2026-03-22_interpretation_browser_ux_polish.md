# Interpretation Browser UX Polish

## Title
Qt-style interpretation UX polish for the browser Gmail flow.

## Goal and non-goals
- Goal:
  - make the browser Gmail interpretation path feel like one focused Qt-style step instead of a page plus drawer plus duplicate summaries
  - keep the New Job interpretation shell minimal while an active Gmail interpretation session exists
- Non-goals:
  - no Gmail bridge, native-host, reply-address, validation, or document-generation logic changes
  - no backend endpoint or payload-shape changes

## Scope
- In:
  - client-side interpretation workspace-mode derivation
  - compact Gmail interpretation session shell on `#new-job`
  - suppression of duplicate intake/seed/action surfaces during active Gmail interpretation sessions
- Out:
  - interpretation drawer redesign beyond Stage 1
  - completion-state UX beyond Stage 1
  - Playwright/live verification beyond the staged boundary

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/gmail-review-parity-browser`
- Base branch: `feat/gmail-review-parity-browser`
- Base SHA: `e990ef3fca7aad1ed29d4f121bf05b405f37cf31`
- Target integration branch: `main`
- Canonical build status: noncanonical browser-shell worktree carrying the approved Gmail/browser parity floor from this branch baseline

## Interfaces/types/contracts affected
- `shadow_web/static/interpretation_review_state.js`
  - add interpretation workspace-mode derivation with `blank`, `manual_seed`, `gmail_review`, `gmail_completed`
- `shadow_web/static/app.js`
  - expose the new interpretation workspace mode through `getInterpretationUiSnapshot()`
  - replace the duplicated New Job interpretation shell with a compact Gmail interpretation session panel when a Gmail interpretation session is active
- `shadow_web/static/gmail.js`
  - suppress the top Gmail workspace strip on `#new-job` while the compact interpretation session shell is active
- No backend or API response contract changes in this pass

## File-by-file implementation steps
- `docs/assistant/exec_plans/active/2026-03-22_interpretation_browser_ux_polish.md`
  - create and maintain the staged plan record
- `src/legalpdf_translate/shadow_web/static/interpretation_review_state.js`
  - add `deriveInterpretationWorkspaceMode(...)`
- `src/legalpdf_translate/shadow_web/static/app.js`
  - derive/render the compact Gmail interpretation session shell
  - hide upload/seed/action shells while the Gmail interpretation workspace mode is active
  - include workspace-mode metadata in the interpretation UI snapshot
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - hide the generic Gmail strip on New Job when the compact interpretation session shell is active
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - add the compact `Current Interpretation Step` panel
- `src/legalpdf_translate/shadow_web/static/style.css`
  - style the compact interpretation session shell
- `tests/test_interpretation_review_state.py`
  - add workspace-mode coverage
- `tests/test_shadow_web_api.py`
  - assert the compact interpretation session shell markup exists

## Tests and acceptance criteria
- Stage 1 validation:
  - JS syntax checks for touched browser modules
  - `tests/test_interpretation_review_state.py`
  - `tests/test_shadow_web_api.py`
  - `tests/test_shadow_web_route_state.py`
- Acceptance for Stage 1:
  - a Gmail interpretation session on `#new-job` has one compact session panel instead of the upload + seed + action stack
  - the top Gmail strip is suppressed on `#new-job` during that focused interpretation mode
  - manual/local interpretation intake remains available when no Gmail interpretation session exists

## Rollout and fallback
- Roll out in staged browser-only increments.
- If Stage 1 causes regressions, revert the compact session-shell toggles while keeping the new workspace-mode helper for later stages.

## Risks and mitigations
- Risk: the new interpretation UI snapshot could create noisy shell updates.
  - Mitigation: keep snapshot fields narrow and continue using the existing change-key guard.
- Risk: hiding the New Job shell too aggressively could block manual/local interpretation intake.
  - Mitigation: only switch to the compact shell for `gmail_review` and `gmail_completed`.

## Assumptions/defaults
- The first focused Gmail handoff already works and should stay as-is.
- Same-window bounded flow remains the correct browser adaptation.
- The Gmail interpretation session summary should reflect live form edits, not stale imported values.

## Stage 1 implemented
- Added `deriveInterpretationWorkspaceMode(...)` to the browser interpretation state helper with `blank`, `manual_seed`, `gmail_review`, and `gmail_completed`.
- Added a compact `Current Interpretation Step` panel to the New Job interpretation task shell.
- Reworked the New Job interpretation shell so active Gmail interpretation sessions suppress:
  - the top Gmail strip on `#new-job`
  - the upload panel
  - the `Seed Review` panel
  - the interpretation action rail
- Kept the manual/local interpretation intake path intact whenever no Gmail interpretation session is active.

## Stage 1 validation results
- `Get-Content src/legalpdf_translate/shadow_web/static/interpretation_review_state.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/app.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/gmail.js -Raw | node --input-type=module --check -` -> PASS
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py` -> PASS (`23 passed`)

## Stage 2 implemented
- Added a pure drawer-layout helper in `shadow_web/static/interpretation_review_state.js` so the browser can enforce:
  - Gmail-mode footer actions
  - Qt-like section defaults
  - service-section auto-open when a service validation target is active
- Reworked the interpretation review drawer in `shadow_web/templates/index.html` and `shadow_web/static/app.js`:
  - narrowed the drawer to the dedicated interpretation width
  - replaced the old duplicate Gmail summary/action card with:
    - one compact review summary block
    - one contextual Gmail CTA/result block
  - hid `New Blank Entry`, `Close`, `Save Interpretation Row`, and `Generate DOCX + PDF` from the normal Gmail interpretation path, leaving `Finalize Gmail Reply` as the only footer CTA in that mode
- Updated the drawer section defaults to the Qt-style profile:
  - `SERVICE` collapsed when service matches case
  - `TEXT` expanded by default
  - `RECIPIENT` collapsed by default
  - `Amounts (EUR)` collapsed by default
- Extended browser-state/static coverage for the new drawer rules and shell markup.

## Stage 2 validation results
- `Get-Content src/legalpdf_translate/shadow_web/static/interpretation_review_state.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/app.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/gmail.js -Raw | node --input-type=module --check -` -> PASS
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py` -> PASS (`23 passed`)

## Stage 3 implemented
- Added compact completion-mode behavior to the browser interpretation review flow:
  - once a Gmail finalization result exists in the browser UI, the interpretation workspace now switches from `gmail_review` to `gmail_completed` immediately instead of waiting for a refreshed backend session payload
  - the compact New Job session shell now changes its primary CTA to `View Final Result`
  - the drawer summary now switches from "notice is staged for review" copy to "result is ready" copy
  - the completion card becomes the primary result surface, while `Review details` auto-collapses after completion
- Fixed a live Stage 3 state gap discovered during verification:
  - empty `pdf_export: {}` on a prepared Gmail interpretation session no longer misclassifies the browser as completed
  - restored prepared Gmail interpretation sessions now reapply the staged interpretation seed into the browser form on reload
  - bootstrap no longer overwrites a restored Gmail interpretation seed with the blank local seed
  - client-side completion payloads now count as completion for workspace-mode derivation so the browser shell reflects the just-finished result immediately
- Kept all of this browser-only:
  - no Gmail bridge changes
  - no reply-address or validation changes
  - no document-generation contract changes

## Stage 3 validation results
- Syntax checks:
  - `Get-Content src/legalpdf_translate/shadow_web/static/interpretation_review_state.js -Raw | node --input-type=module --check -` -> PASS
  - `Get-Content src/legalpdf_translate/shadow_web/static/app.js -Raw | node --input-type=module --check -` -> PASS
  - `Get-Content src/legalpdf_translate/shadow_web/static/gmail.js -Raw | node --input-type=module --check -` -> PASS
  - `Get-Content src/legalpdf_translate/shadow_web/static/translation.js -Raw | node --input-type=module --check -` -> PASS
- Targeted automated coverage:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_interpretation_review_state.py tests/test_shadow_web_route_state.py` -> PASS (`4 passed`)
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py -k "index_contains_beginner_first_shell_sections or bootstrap_includes_gmail_workspace_payload"` -> PASS (`2 passed, 17 deselected`)
  - `dart run tooling/automation_preflight.dart` -> PASS
- Live browser verification:
  - verified against `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#new-job` on the live Gmail interpretation workspace
  - confirmed the compact `Current Interpretation Step` shell restores the prepared Gmail seed values after reload:
    - case number `363141111`
    - court email `beja.judicial@tribunais.org.pt`
    - service date `2026-03-20`
    - location `Ministério Público | Beja`
  - confirmed `Review Interpretation` opens the dedicated 720px interpretation drawer
  - confirmed Gmail interpretation mode shows the Qt-style defaults:
    - `Finalize Gmail Reply` visible
    - `Generate DOCX + PDF` hidden
    - `New Blank Entry` hidden
    - `SERVICE` collapsed
    - `TEXT` expanded
    - `RECIPIENT` collapsed
    - `Amounts (EUR)` collapsed
  - confirmed live form edits propagate through the focused shell and drawer summary without stale imported values:
    - changing the case city in the browser updated both the home summary and the drawer summary immediately
  - confirmed completion-mode behavior in the live-loaded browser surface using a simulated finalization result to avoid generating another real Gmail draft:
    - home CTA changed to `View Final Result`
    - summary copy changed to the completed-state messaging
    - completion card became visible
    - `Finalize Gmail Reply` hid
    - `Review details` auto-collapsed
    - completion summary reflected the live-edited location values
  - console check after the final verification session: `0` errors, `0` warnings
- Evidence artifact:
  - completion-state screenshot copied to `output/playwright/interpretation_stage3_completion.png`
