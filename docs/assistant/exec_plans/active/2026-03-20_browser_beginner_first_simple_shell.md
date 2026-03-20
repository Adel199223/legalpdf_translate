# Browser Beginner-First Simple Shell

## Goal and non-goals
- Goal: simplify the default browser app into one understandable first screen for daily use while preserving the browser app as the preferred live surface.
- Goal: keep Gmail extension handoff focused by routing it to a dedicated Gmail intake screen instead of the general new-job shell.
- Goal: preserve the current browser capability breadth while removing novice-facing clutter from the primary navigation and first-run surface.
- Non-goal: add a permanent third runtime mode or a parallel long-term "lite" product.
- Non-goal: remove direct-route access to secondary views such as `Dashboard`, `Settings`, `Profile`, `Power Tools`, or `Extension Lab`.
- Non-goal: change `mode=live|shadow` semantics, Gmail bridge ownership, or existing browser APIs beyond additive shell metadata and routing.

## Scope (in/out)
- In scope:
  - browser shell routing and navigation under `src/legalpdf_translate/shadow_web/`
  - dedicated `#gmail-intake` browser route and Gmail handoff URL updates
  - simplified `#new-job` translation-first home with an in-page translation/interpretation task switch
  - hidden-by-default post-run translation save surfaces and compact Gmail session strip behavior
  - fixed preview-port operability on `127.0.0.1:8888` for branch review
  - browser bootstrap recovery UX for dead local listeners / stale cached preview tabs
  - focused browser/Gmail route and handoff regression tests
- Out of scope:
  - full visual restyling of all admin/secondary pages
  - changing backend workflow semantics for translation, interpretation, Gmail, or job-log persistence
  - removing the temporary `ui=legacy` fallback in this pass

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate_browser_qt_parity`
- branch name: `codex/browser-qt-parity-shell`
- base branch: `main`
- base SHA: `b6f75586fed51b3965c68bdc35a6e3d58c490a0d`
- target integration branch: `main`
- canonical build status: noncanonical feature worktree allowed by build policy; branch still contains the approved-base floor from `docs/assistant/runtime/CANONICAL_BUILD.json`

## Interfaces/types/contracts affected
- Preserve:
  - `?mode=live|shadow`
  - `?workspace=<id>`
- Add:
  - `#gmail-intake` dedicated browser view for Gmail extension handoff
- Preserve direct-route secondary hashes during rollout:
  - `#dashboard`
  - `#settings`
  - `#profile`
  - `#power-tools`
  - `#extension-lab`
- Preserve `ui=legacy` as the temporary internal fallback only.

## File-by-file implementation steps
1. Update worktree continuity docs:
   - move the completed parity-only ExecPlan to `completed/`
   - point `SESSION_RESUME.md` at the new simple-shell plan and the simplified browser entry URLs
2. Update browser routing and handoff contracts:
   - extend route-state support to include `gmail-intake`
   - change default browser-open URLs to `#new-job`
   - retarget browser Gmail bridge/focus-host URLs from `#new-job` to `#gmail-intake`
3. Simplify the browser shell template:
   - replace the primary sidebar with `New Job`, `Recent Jobs`, conditional `Gmail`, and `More`
   - split Gmail into its own `data-view="gmail-intake"` page
   - simplify `data-view="new-job"` into a translation-first shell with task switching and hidden-by-default advanced/post-run surfaces
4. Update browser static behavior:
   - render grouped primary vs secondary navigation and the `More` expander
   - manage new-job task switching, Gmail banner visibility, translation post-run visibility, and Gmail-route-specific continuation actions
   - keep direct secondary hashes fully routable
5. Refresh focused regression coverage for:
   - route defaults
   - Gmail bridge/focus-host URLs
   - simple-shell HTML presence/behavior
6. Add preview-operability hardening:
   - upgrade the detached browser launcher on this branch to the hardened arg-aware version with `--mode`, `--workspace`, `--port`, `--ui`, and `--no-open`
   - add a fixed review-preview wrapper targeting `127.0.0.1:8888/?mode=shadow&workspace=workspace-preview#new-job`
   - normalize dead-listener fetch failures into friendly local recovery copy instead of raw `Failed to fetch`
   - keep `8877` as the daily/live/Gmail contract and document `8888` as the fixed review-preview contract only

## Tests and acceptance criteria
- Focused tests:
  - `.\.venv311\Scripts\python.exe -m pytest -q tests/test_launch_browser_app_live_detached.py tests/test_shadow_web_runtime_recovery.py tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py tests/test_shadow_web_server.py tests/test_browser_gmail_bridge.py tests/test_gmail_focus.py tests/test_gmail_focus_host.py tests/test_windows_shortcut_scripts.py`
- Acceptance:
  - no-hash Qt/default browser route lands on `#new-job`
  - Gmail browser handoff lands on `#gmail-intake`
  - primary nav shows only `New Job`, `Recent Jobs`, conditional `Gmail`, and `More`
  - `Advanced Settings` starts collapsed
  - the visible translation action rail is limited to `Start Translate`, `Cancel`, and `...`
  - Gmail intake panels are absent from the normal home screen and replaced there by a compact Gmail session strip when relevant
  - translation save/log panels stay hidden until a run or saved row makes them relevant
  - interpretation disclosure defaults continue to match the Qt-derived `SERVICE` / `TEXT` / `RECIPIENT` / `Amounts` behavior
  - the daily browser app remains on `8877`, while the branch-review preview always uses `8888`
  - stale cached preview tabs surface a friendly local-server-unavailable recovery state instead of only `Failed to fetch`

## Rollout and fallback
- Keep `ui=legacy` as the temporary internal shell fallback during this branch pass.
- Keep direct secondary hash routes alive even though the default navigation becomes minimal.
- If a simplification change causes route or Gmail confusion, revert only the affected shell layer while preserving the `#gmail-intake` URL contract and the minimal-nav architecture.

## Risks and mitigations
- Risk: simplification hides real capabilities too aggressively.
  - Mitigation: keep direct routes and `More` access, and reveal advanced/post-run controls contextually instead of deleting them.
- Risk: Gmail handoff becomes disconnected from the main workflow.
  - Mitigation: dedicate `#gmail-intake` to Gmail state and provide explicit continue actions into translation or interpretation.
- Risk: mixed translation/interpretation state on `#new-job` remains confusing.
  - Mitigation: add an in-page task switch and keep only one task surface visible at a time.

## Assumptions/defaults
- Translation remains the default first task on `#new-job`.
- The browser shell should favor structural simplicity over exact Qt visual cloning in this pass.
- The repo’s Qt/browser knowledge is sufficient for this implementation without requiring new screenshots.

## Status snapshot
- Completed:
  - route-state and browser-open contracts now default Qt mode to `#new-job`
  - Gmail browser bridge and focus-host URLs now target `#gmail-intake`
  - the default browser shell now groups primary nav into `New Job`, `Recent Jobs`, conditional `Gmail`, and `More`
  - `#new-job` now uses a translation-first simple shell with an in-page translation/interpretation task switch
  - translation post-run save surfaces and interpretation export surfaces stay hidden until they become relevant
  - Gmail handoff is now isolated in its own `#gmail-intake` view, with only a compact Gmail strip shown on `#new-job`
- Validation:
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py tests/test_shadow_web_server.py tests/test_browser_gmail_bridge.py tests/test_gmail_focus.py tests/test_gmail_focus_host.py` -> `63 passed`
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_qt_app_state.py -k browser_app_owns_live_bridge` -> `1 passed`
  - `C:\Users\FA507\.codex\legalpdf_translate\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py` -> `18 passed` after the final route-chrome fix
  - `dart run tooling/validate_agent_docs.dart` -> `PASS`
  - `dart run tooling/validate_workspace_hygiene.dart` -> `PASS`
  - Playwright browser smoke on preview port `8892` confirmed:
    - default entry opens `#new-job` with `Translation` visible and `Interpretation` hidden
    - direct `#gmail-intake` entry keeps `gmail-intake` active, surfaces the conditional `Gmail` nav item, and updates the topbar to `LegalPDF Translate | Gmail`
- Remaining optional follow-up:
  - live visual acceptance in the browser app
  - targeted docs sync for touched browser-app user/ops references that still mention the older default URL
  - preview-port stabilization closeout on the open feature PR
