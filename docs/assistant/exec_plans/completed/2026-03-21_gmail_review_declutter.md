# Gmail Review Declutter

## Title
Declutter the browser Gmail attachment review UX so it tracks the Qt review dialog more closely while keeping the browser-native review and preview flow.

## Baseline
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch: `feat/gmail-review-parity-browser`
- HEAD: `e990ef3`
- Baseline note: existing dirty Gmail browser and bridge changes remain in place and must not be reverted during this pass.

## Goal
- Keep Gmail review auto-open and session preparation behavior intact.
- Reduce the Gmail review drawer to a compact Qt-like review surface.
- Move attachment preview into a separate on-demand browser surface.

## Non-goals
- No native-host, extension registration, bridge transport, or backend API changes.
- No changes to the Gmail review-event contract.

## Planned implementation
- Update the Gmail review drawer markup and copy in `shadow_web/templates/index.html`.
- Refactor Gmail review and preview state/behavior in `shadow_web/static/gmail.js`.
- Rework Gmail drawer and preview styling in `shadow_web/static/style.css`.
- Extend static/browser-state coverage in:
  - `tests/test_shadow_web_api.py`
  - `tests/test_gmail_review_state.py`

## Validation plan
- `node --check` for `gmail.js`
- Targeted pytest for Gmail review/static coverage
- `dart run tooling/automation_preflight.dart`
- Live Playwright verification against `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`

## Implemented
- Reworked the Gmail review drawer into a narrower Qt-like surface with one header close control, a compact summary banner, and a separate preview surface.
- Removed raw attachment ids and oversized file metadata from the visible review body; filenames now clamp compactly in the attachments table.
- Moved preview to an explicit on-demand modal with page navigation, `Open in new tab`, and `Use current page` start-page handoff.
- Reduced the review detail area to a compact current-attachment strip with filename, page-count status, start page, and preview action.
- Kept interpretation mode single-select and fixed a row-focus interaction bug so radio/checkbox clicks are no longer swallowed by row rerenders.

## Validation results
- `Get-Content src/legalpdf_translate/shadow_web/static/gmail.js -Raw | node --input-type=module --check -` -> PASS
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py` -> PASS (`1 passed`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py -k gmail` -> PASS (`3 passed, 13 deselected`)
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py` -> PASS (`3 passed`)
- `dart run tooling/automation_preflight.dart` -> PASS (`automation_host_selected: local`, `playwright_available: true`, system Edge binary selected)
- Live Playwright verification:
  - fresh Gmail review auto-opened after a real localhost bridge intake replay
  - preview stayed closed by default
  - raw attachment ids were no longer visible in the main review flow
  - clicking `Preview` opened the separate preview surface
  - `Use current page` updated the review start page
  - interpretation mode now keeps single-select behavior and enables `Prepare notice` after one notice is chosen
