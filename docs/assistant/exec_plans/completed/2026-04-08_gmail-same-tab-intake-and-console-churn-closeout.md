# Gmail Same-Tab Intake and Deterministic Click Validation

## Goal and non-goals
1. Goal: replace Gmail's separate-tab/window launch with a same-tab redirect so the extension controls only one surface during intake.
2. Goal: preserve `launch_session_id` as cold-start/browser diagnostics while treating `handoff_session_id` as the per-click Gmail freshness key.
3. Goal: post the `/gmail-intake` bridge context immediately after the same-tab redirect commits, so browser-client hydration cannot strand the workspace with no Gmail payload.
4. Goal: add deterministic debug-triggered acceptance so we can validate the exact Gmail click handler without depending on toolbar-only manual clicks.
5. Goal: persist click-phase diagnostics, source Gmail URL, and return-to-Gmail state across the extension and browser app.
6. Non-goal: change Gmail translation semantics, prepared `New Job` behavior, Gmail-scoped run dirs, or OCR/page-4 recovery.

## Scope
- In scope:
  - same-tab redirect flow for `workspace=gmail-intake` in `extensions/gmail_intake/background.js`
  - a Gmail click-session model keyed by current browser tab id plus current `handoff_session_id`
  - capture and propagation of `source_gmail_url` through the extension, localhost bridge, and browser workspace state
  - a persistent `Return to Gmail` action in the browser app
  - extension-side click-phase diagnostics mirrored to browser-app diagnostics
  - a debug/test trigger that invokes the exact same Gmail click handler logic as the toolbar action
  - deterministic acceptance based on `tooling/automation_preflight.dart` plus a headed Gmail intake smoke
  - focused regression coverage for same-tab redirect, lock cleanup, and bridge-post ordering
- Out of scope:
  - changing unrelated Gmail translation/OCR behavior
  - changing non-Gmail browser launch UX beyond preserving existing fallback behavior
  - translation workflow logic

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `codex/gmail-same-tab-acceptance-closeout`
- base branch: `main`
- base SHA: `90a0936`
- target integration branch: `main`
- canonical build status: live validation accepted on the canonical primary repo, then closeout moved to a publish branch

## Interfaces/types/contracts affected
- Preserved browser-app cold-start success reason: `browser_server_ready` still means server ready, not browser-surface ready.
- Additive Gmail bridge/context fields:
  - `source_gmail_url`
- Additive click diagnostics fields:
  - `click_phase`
  - `click_failure_reason`
  - `bridge_context_posted`
  - `surface_visibility_status`
  - `source_gmail_url_present`
- Additive browser bootstrap/state fields:
  - `handoff_session_id`
  - `source_gmail_url`
  - `latest_extension_click_phase`
  - `latest_extension_click_failure_reason`
- Compatibility marker:
  - `extension_launch_session_schema_version` bumps to require same-tab handoff semantics
- Preserved ownership contract:
  - native host/runtime owns server readiness
  - extension owns Gmail click orchestration
  - the current Gmail tab becomes the browser surface during intake

## File-by-file implementation steps
1. Update `extensions/gmail_intake/background.js` to:
   - replace the Gmail-specific `openOrFocusBrowserApp` path with same-tab redirect on the current Gmail tab
   - persist a click-session record keyed by current tab id and current `handoff_session_id`
   - post the bridge payload immediately after same-tab redirect commit, then clear the click-session and navigate back to Gmail only if the post/workspace confirmation fails
   - post click-phase diagnostics into the correlated launch-session state
   - expose a debug/test entrypoint that routes into the same Gmail click handler logic as `chrome.action.onClicked`
2. Update `extensions/gmail_intake/content.js` to:
   - capture `source_gmail_url`
   - expose a page-level debug trigger for the Gmail click flow in local/test contexts
3. Update `src/legalpdf_translate/gmail_intake.py` and `src/legalpdf_translate/gmail_browser_service.py` to:
   - accept and persist `source_gmail_url`
   - preserve the latest `handoff_session_id` even when message content is reused
4. Update browser-app bootstrap and UI in:
   - `src/legalpdf_translate/shadow_web/app.py`
   - `src/legalpdf_translate/shadow_web/static/app.js`
   - `src/legalpdf_translate/shadow_web/static/gmail.js`
   - `src/legalpdf_translate/shadow_web/templates/index.html`
   so the page exposes `source_gmail_url`, latest click phase, and a `Return to Gmail` action.
5. Extend diagnostics in `src/legalpdf_translate/gmail_window_trace.py` so the latest launch state surfaces click-phase truth, but keep window tracing secondary.
6. Reset stale per-click launch diagnostics in `src/legalpdf_translate/gmail_focus_host.py` whenever a fresh `handoff_session_id` is minted, and keep server/native launch helpers on `python.exe` with no-window creation flags for reliable stdio without visible console churn.
7. Add or update deterministic validation tooling and focused regression coverage in:
   - `tests/test_gmail_intake.py`
   - `tests/test_shadow_web_api.py`
   - `tests/test_gmail_window_trace.py`
  - native-host source and launcher coverage

## Tests and acceptance criteria
1. Targeted tests pass for:
  - `tests/test_gmail_intake.py`
  - `tests/test_shadow_web_api.py`
  - `tests/test_gmail_window_trace.py`
  - `tests/test_gmail_focus_host.py`
  - relevant Gmail/translation non-regression slices already covering prepared-start defaults and Gmail-scoped run isolation
  - browser automation preflight checks from `tooling/automation_preflight.dart`
2. Acceptance:
   - Gmail click never opens or focuses a separate LegalPDF tab for `workspace=gmail-intake`
   - the current Gmail tab redirects to the LegalPDF Gmail workspace before the bridge POST
   - bridge POST happens immediately after redirect commit; hydration is bounded and cannot block delivery of the Gmail message context
   - bridge or workspace confirmation failures restore the original Gmail URL and clear the click-session immediately
   - second clicks do not show stale retry banners unless the same tab is genuinely mid-handoff for the same `handoff_session_id`
   - deterministic debug-triggered automation can exercise the same click handler and observe `bridge_context_posted=true`
   - the browser app exposes `Return to Gmail` and restores the original message URL

## Risks and mitigations
1. Risk: same-tab redirect can strand the user on the browser app if hydration fails.
   - Mitigation: restore the original Gmail URL immediately on pre-bridge or workspace-ready failure.
2. Risk: manual toolbar clicks remain noisy for acceptance.
   - Mitigation: add a debug trigger that drives the same handler and require deterministic automation acceptance first.
3. Risk: carrying Gmail source URLs through the browser app could drift or go missing.
   - Mitigation: treat the source URL as additive and fall back to inbox/thread-level navigation when absent.
4. Risk: stale click-session state survives across service-worker reloads.
   - Mitigation: key click-session state by current tab id plus current `handoff_session_id` and clear it whenever redirect/hydration evidence is absent.

## Assumptions/defaults
1. The current user-facing failure remains an extension click-orchestration bug, not a fresh host/runtime cold-start failure.
2. Reliability is more important than preserving the old separate-surface Gmail UX, so the chosen path is same-tab intake.
3. `Prepare selected` remains prepare-only and still opens `New Job`.
4. Existing stale Gmail tabs are ignored, not auto-closed, in this pass.

## Execution closeout
1. Implementation accepted on the live machine:
   - final normal Edge Profile 2 handoff: `20260419_125112_2d61fbb64f8e`
   - runtime: canonical `main`, AppData runtime root, native-host path kind `exe`
   - diagnostics: `click_phase=bridge_context_posted`, `bridge_context_posted=true`, `runtime_state_root_compatible=true`, `workspace_surface_confirmed=true`, `client_hydration_status=ready`, `source_gmail_url` present
   - Gmail bootstrap: `loaded` / `ready`, subject `Notificação de Tentativa de Conciliação`, message ID `19d433bf0ee61782`, one supported attachment
   - user-visible result: no `Pending load`, no unavailable message/thread IDs, no repeated LegalPDF/native-host CMD churn, and `Return to Gmail` restored the original Gmail URL
2. Focused implementation validation:
   - `.\.venv311\Scripts\python.exe -m pytest tests/test_gmail_intake.py tests/test_shadow_web_api.py tests/test_gmail_focus_host.py tests/test_launch_browser_app_live_detached.py tests/test_native_host_launcher_source.py tests/test_gmail_browser_service.py -q` -> `139 passed`
3. Assistant Docs Sync:
   - recorded same-tab Gmail intake, no-console native-host EXE registration, stale click-state fail-closed rules, deterministic acceptance, and automation-helper CMD cleanup in durable docs
   - added issue-memory entry `workflow-gmail-same-tab-console-churn-regression`
4. Status:
   - completed; no active ExecPlan remains for this bug family
