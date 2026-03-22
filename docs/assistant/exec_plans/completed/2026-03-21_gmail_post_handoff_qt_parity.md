# Gmail Post-Handoff Qt Parity

## Title
Complete the browser Gmail post-handoff flow so it behaves like a bounded Qt-style sequence instead of a persistent session dashboard.

## Baseline
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch: `feat/gmail-review-parity-browser`
- HEAD: `e990ef3`
- Baseline note: existing dirty Gmail browser and bridge changes remain in place and must not be reverted during this staged pass.

## Goal
- Keep the first `Focused Intake Review` page as the browser landing step.
- Replace the generic post-prepare Gmail control center with stage-aware resume behavior.
- Move toward a same-window bounded-step flow that mirrors the Qt dialogs more closely.

## Non-goals
- No native-host, registration, or bridge transport changes.
- No backend API changes in this pass.
- No popup-window workflow.

## Stages
### Stage 1
- Add a client-side Gmail stage model.
- Rework Gmail intake home into a compact landing/resume screen.
- Remove the normal-path dependence on the generic Gmail session dashboard.

### Stage 2
- Auto-start the translation path after Gmail review.
- Auto-open the bounded translation finish surface and add batch-finalization flow.

### Stage 3
- Keep interpretation Gmail follow-up inside the interpretation review/finalization flow.
- Run full browser/live acceptance and record evidence.

## Planned implementation
- Extend Gmail state helpers in `shadow_web/static/gmail_review_state.js`.
- Rework Gmail shell/home orchestration in `shadow_web/static/gmail.js`.
- Expose the minimal translation/interpretation resume hooks from:
  - `shadow_web/static/translation.js`
  - `shadow_web/static/app.js`
- Update the Gmail intake home markup in `shadow_web/templates/index.html`.
- Extend focused Gmail browser/static coverage in:
  - `tests/test_gmail_review_state.py`
  - `tests/test_shadow_web_api.py`
  - `tests/test_shadow_web_route_state.py`

## Validation plan
- JS syntax check for touched browser modules
- Targeted pytest for Gmail review/static/route coverage
- Stop at Stage 1 boundary and require `NEXT_STAGE_2`

## Stage 1 implemented
- Added a client-side Gmail stage model and CTA derivation helpers in `shadow_web/static/gmail_review_state.js`.
- Reworked the Gmail intake home into a compact resume screen:
  - added `Resume Current Step`
  - removed home-page `Open Session Actions`
  - removed the home-page Gmail session banner
  - added a compact resume result card
- Kept the generic Gmail session drawer as a fallback surface, but removed the normal-path dependence on it from the Gmail home and workspace strip.
- Exposed minimal translation/interpretation UI snapshots so Gmail can derive the next bounded step without backend changes.

## Stage 1 validation results
- `Get-Content src/legalpdf_translate/shadow_web/static/gmail.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/translation.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/app.js -Raw | node --input-type=module --check -` -> PASS
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py` -> PASS (`1 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py -k gmail` -> PASS (`3 passed, 13 deselected`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> PASS (`3 passed`)

## Stage 2 implemented
- Wired Gmail translation prepare/confirm to auto-start the browser translation run instead of bouncing back to a generic Gmail session dashboard.
- Added a Gmail-aware step card inside the bounded `Finish Translation` drawer so the operator can confirm the current Gmail translation row directly from the save surface.
- Added a dedicated `Finalize Gmail Batch` drawer for the last-step Gmail reply flow after every selected attachment is confirmed.
- Kept the generic Gmail session drawer available as fallback, but removed it from the normal translation path.

## Stage 2 validation results
- `Get-Content src/legalpdf_translate/shadow_web/static/gmail.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/translation.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/app.js -Raw | node --input-type=module --check -` -> PASS
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py` -> PASS (`1 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py -k gmail` -> PASS (`3 passed, 13 deselected`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> PASS (`3 passed`)

## Stage 3 implemented
- Kept the Gmail interpretation follow-up inside the bounded interpretation review flow:
  - `Prepare notice` now opens the interpretation review surface directly in `#new-job`.
  - the interpretation review drawer now owns the Gmail finalization action via `Finalize Gmail Reply`.
  - Gmail draft/result feedback for interpretation now renders inside that same review drawer instead of sending the operator back to the generic Gmail session drawer.
- Added a frontend recursion guard in `shadow_web/static/app.js` so interpretation UI notifications only fire when the interpretation UI snapshot actually changes.
  - This fixed the live browser stack-overflow loop between `app.js` and `gmail.js` that was preventing the Gmail state from rendering reliably after a real load.
- Updated browser/static coverage in `tests/test_shadow_web_api.py` for the interpretation-bounded Gmail controls.

## Stage 3 validation results
- `Get-Content src/legalpdf_translate/shadow_web/static/gmail.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/app.js -Raw | node --input-type=module --check -` -> PASS
- `Get-Content src/legalpdf_translate/shadow_web/static/translation.js -Raw | node --input-type=module --check -` -> PASS
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py tests/test_shadow_web_api.py -k gmail tests/test_shadow_web_route_state.py` -> PASS (`5 passed, 15 deselected`)
- `dart run tooling/automation_preflight.dart` -> PASS
- Restored a real live Gmail workspace load using the exact message/thread for:
  - subject: `Remessa de peça processual // Pedido de tradução de sentença // P. 305/23.2GCBJA`
  - message/thread id: `19d0bf7e8dccffc0`
- Fresh Playwright live-browser verification against `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake` confirmed:
  - the focused intake page shows the real subject and 2 supported attachments
  - `Open Attachment Review` is enabled
  - switching to `Interpretation notice` enforces single-select radio behavior
  - selecting one notice enables `Prepare notice`
  - `Prepare notice` navigates to `#new-job`
  - the home CTA becomes `Resume Current Step`
  - the bounded `Review Interpretation` drawer auto-opens
  - the Gmail follow-up stays inside that drawer via `Finalize Gmail Reply`
  - no console errors occur in a fresh automation session after the recursion fix
  - the bounded interpretation flow remains readable at a narrower laptop viewport (`1180x900`)
- Live finalization execution confirmed:
  - invoking `Finalize Gmail Reply` in the bounded interpretation drawer moved the session to `draft_ready`
  - the UI rendered `Gmail draft created successfully` inside that same drawer
  - the live workspace exported:
    - `C:\Users\FA507\Downloads\Requerimento_Honorarios_Interpretacao_305_23.2GCBJA_20260322.docx`
    - `C:\Users\FA507\Downloads\Requerimento_Honorarios_Interpretacao_305_23.2GCBJA_20260322.pdf`
  - the live session record `C:\Users\FA507\Downloads\_gmail_interpretation_sessions\gmail_interpretation_08ff020efe0a\gmail_interpretation_session.json` records `draft_created: true`
- Evidence artifacts:
  - focused review: `.playwright-cli/page-2026-03-22T00-26-43-444Z.yml`
  - interpretation bounded flow: `.playwright-cli/page-2026-03-22T00-30-51-857Z.yml`
  - narrow-width screenshot: `.playwright-cli/page-2026-03-22T00-32-23-911Z.png`
  - post-finalization snapshot: `.playwright-cli/page-2026-03-22T00-38-20-769Z.yml`
  - post-finalization screenshot: `.playwright-cli/page-2026-03-22T00-38-36-370Z.png`
