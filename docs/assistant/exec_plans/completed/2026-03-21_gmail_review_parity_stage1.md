# Gmail Review Parity Stage 1

## Title
Restore Qt-parity Gmail attachment review in the browser app, starting with the session review-event contract that will drive a bounded review surface in later stages.

## Goal and non-goals
- Goal: add durable browser Gmail review metadata so the UI can detect a fresh exact-message handoff and open the correct review surface automatically.
- Goal: record the current dirty Gmail browser baseline and stage the broader parity work safely.
- Non-goal: change native-host registration, extension transport, or the existing session/finalization flow in this stage.
- Non-goal: build the review drawer UI in this stage.

## Scope (in/out)
- In scope: ExecPlan setup, branch provenance, Gmail browser session review metadata, API/unit coverage for the new contract.
- Out of scope: Gmail review drawer markup/CSS/JS, inline preview UX, focus-refresh polling, native-host and bridge registration changes.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/gmail-review-parity-browser`
- Base branch: `feat/gmail-focus-shell-layout-fix`
- Base SHA: `e990ef3fca7aad1ed29d4f121bf05b405f37cf31`
- Target integration branch: `main`
- Canonical build status: canonical worktree, live browser app on port `8877`
- Baseline note: this branch intentionally carries forward dependent uncommitted Gmail browser/bridge fixes already present in the worktree; a separate worktree was not created because the required baseline is currently uncommitted.

## Interfaces/types/contracts affected
- `src/legalpdf_translate/gmail_browser_service.py`
  - Add workspace review metadata:
    - `review_event_id: int`
    - `message_signature: str`
- Browser Gmail bootstrap/load contract:
  - `build_bootstrap()` includes `review_event_id` and `message_signature`
  - `load_message()` includes `review_event_id` and `message_signature`
  - `accept_bridge_intake()` includes `review_event_id` and `message_signature`
- No endpoint paths, native-host payloads, or existing Gmail session payload shapes otherwise change.

## File-by-file implementation steps
- `src/legalpdf_translate/gmail_browser_service.py`
  - add message-signature helper and workspace review metadata fields
  - increment the event id every time a new load result is stored
  - expose the metadata in bootstrap/manual-load/bridge-ingest responses
- `tests/test_shadow_web_api.py`
  - assert the new Gmail review metadata exists in bootstrap and delegated load-message/session responses
- `tests/test_gmail_browser_service.py`
  - add direct service coverage for default review metadata and event increments across manual load + bridge intake

## Tests and acceptance criteria
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_browser_service.py tests/test_shadow_web_api.py`
- Acceptance:
  - new workspace bootstrap returns `review_event_id == 0` and `message_signature == ""`
  - first exact-message load returns event `1`
  - subsequent bridge/manual loads increment the event id monotonically within the workspace
  - bootstrap reflects the latest event/signature after load storage

## Rollout and fallback
- Stage 1 is backend-contract only; no live UI behavior is expected to change yet.
- If the new metadata contract proves unstable, revert only the review metadata additions and leave the current Gmail intake behavior untouched.

## Risks and mitigations
- Risk: review events reset unexpectedly when the workspace clears session state.
  - Mitigation: increment review metadata explicitly in `_store_loaded_result` after cleanup logic.
- Risk: later UI code depends on exact signature format.
  - Mitigation: treat `message_signature` as an opaque dedupe token and only test for presence/stability, not semantic parsing.

## Assumptions/defaults
- The current browser Gmail workspace already receives exact Gmail messages and supported attachments after extension handoff.
- Stage 2 will consume this metadata to auto-open a Qt-like review drawer without changing the bridge contract again.
- No docs sync is required yet because this stage does not change the user-facing Gmail flow by itself.

## Executed validations and outcomes
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_browser_service.py`
  - Passed: `2 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_browser_gmail_bridge.py`
  - Passed: `2 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py`
  - Passed: `16 passed`
- `git status --short --branch`
  - Confirmed active branch is `feat/gmail-review-parity-browser` and that dependent Gmail browser/bridge baseline changes remain present in the working tree.
- `dart run tooling/validate_agent_docs.dart`
  - Failed with pre-existing repo issue: `AD046: docs/assistant/SESSION_RESUME.md points to a branch that does not exist in this repo: codex/browser-qt-parity-shell`
  - Not addressed in this stage because it is unrelated to the Gmail review contract work.

## Stage 2 implementation delta
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
  - added browser-only review state helpers for consumed review events and auto-open gating
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - replaced the inline Gmail attachment flow with a bounded review drawer workflow
  - added workspace review auto-open behavior driven by `review_event_id` and `message_signature`
  - added inline preview rendering with PDF page binding and start-page controls
  - added focused refresh scheduling on browser focus/visibility while in `gmail-intake`
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - added the `Gmail Attachment Review` drawer shell and compact summary-first Gmail intake surface
  - normalized the attachment table to a five-column review layout with an explicit selection column
- `src/legalpdf_translate/shadow_web/static/style.css`
  - added Gmail review drawer, review table, inline preview, and drawer-body overflow rules
- `tests/test_gmail_review_state.py`
  - added Node-based coverage for consumed review-event storage and drawer auto-open semantics
- `tests/test_shadow_web_api.py`
  - extended static shell coverage to assert the new Gmail review drawer contract and summary-first UI

## Stage 2 validations and outcomes
- `Get-Content src/legalpdf_translate/shadow_web/static/gmail.js -Raw | node --check --input-type=module -`
  - Passed after fixing one JS parse error caused by mixed `??` and `||` precedence.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py`
  - Passed: `20 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_browser_service.py`
  - Passed: `2 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_browser_gmail_bridge.py`
  - Passed: `2 passed`

## Stage 3 validations and outcomes
- `dart run tooling/automation_preflight.dart`
  - Passed with local host selected, system Edge binary provenance, and `playwright_available=true`.
- `dart run test/tooling/automation_preflight_test.dart`
  - Passed: `4 cases`.
- Live server reconciliation:
  - Detected the stale detached browser-app process on `127.0.0.1:8877` was still serving branch `main` from global `pythonw.exe`, so the new Gmail review backend contract was not live yet.
  - Restarted the live browser app from the current workspace with:
    - old PID stopped: `34364`
    - new detached PID started: `3388`
    - runtime after restart: branch `feat/gmail-review-parity-browser`, interpreter `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\pythonw.exe`
- Live bridge replay:
  - Posted a real Gmail intake payload to `http://127.0.0.1:8765/gmail-intake` using the configured bearer token from the live settings file.
  - Bridge response: `{"status":"accepted","message":"Gmail intake accepted."}`
  - Follow-up bootstrap confirmed:
    - `review_event_id = 1`
    - non-empty `message_signature`
    - `attachment_count = 2`
    - no active Gmail session yet
- Playwright acceptance against `http://127.0.0.1:8877/?mode=live&workspace=gmail-intake#gmail-intake`
  - Fresh in-memory browser session auto-opened the review drawer from the new bridge event.
  - Verified:
    - `shellMode = "gmail-focus"`
    - `reviewDrawerOpen = true`
    - `attachmentRows = 2`
    - translation flow: selecting an attachment enables `Prepare selected`
    - cached PDF preview path updates review state and exposes the new-tab fallback
    - second attachment has `page_count = 5` via the live preview API
    - translation start-page state persisted at `2` in both the detail control and the row control for `sentença 305.pdf`
    - interpretation flow collapses back to a single selected file, resets start page to `1`, and enables `Prepare notice`
  - Screenshot artifact captured at `.playwright-cli/page-2026-03-21T13-37-46-260Z.png`
- Automation limitation note:
  - The Playwright CLI Chromium context downloaded PDF previews instead of rendering the built-in PDF viewer inline, so acceptance used the drawer state, preview status text, preview API page counts, and visible new-tab fallback rather than depending on Chromium's PDF plugin behavior.

## Stage status
- Stage 1 complete.
- Stage 2 complete.
- Stage 3 complete.
- Decision locks:
  - `review_event_id` is a monotonic per-workspace counter incremented on every stored exact-message load result.
  - `message_signature` is an opaque dedupe token derived from the loaded message context and attachment ids.
  - The browser Gmail intake now routes attachment review through a bounded drawer and preserves auto-open behavior through consumed review-event storage.
  - Inline preview is the browser-native replacement for the Qt review dialog preview; no standalone preview window is required by default.
  - The live browser app on `8877` must run from the current workspace/venv for Gmail review parity checks to be meaningful; stale detached `main` instances can make the UI look partially updated while backend review events remain missing.
