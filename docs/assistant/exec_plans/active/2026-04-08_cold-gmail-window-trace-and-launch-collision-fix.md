# Gmail Cold-Start Launch Recovery, Strict Workspace Ownership, and Stale Surface Invalidation

## Goal and non-goals
1. Goal: stop false-warming Gmail handoffs that leave no usable browser surface, then poison the next click with a stale-retry banner.
2. Goal: preserve the extension as the only visible browser-surface owner for Gmail cold start, while requiring exact `gmail-intake` tab confirmation before a handoff can remain active.
3. Goal: record extension-side tab resolution and hydration outcomes in the same correlated launch-session state already used by the browser app.
4. Non-goal: change Gmail translation semantics, prepared `New Job` behavior, Gmail-scoped run dirs, or OCR/page-4 recovery.

## Scope
- In scope:
  - exact workspace-tab ownership and no-hijack rules in `extensions/gmail_intake/background.js`
  - extension-side warmup/lock-hold semantics for browser-app Gmail handoffs
  - correlated launch-session diagnostics persisted through the browser app
  - stale exact `gmail-intake` tab invalidation tied to the active `launch_session_id`
  - browser-app/client compatibility markers so the extension can detect listener/schema drift
  - coherent-stack validation steps that require the unpacked extension and live listener to come from the same code revision under test
  - focused regression coverage for false-warming, stale assets, and no-surface Gmail clicks
- Out of scope:
  - blanket docs sync in this pass
  - changing non-Gmail browser launch UX beyond preserving existing fallback behavior
  - translation workflow logic

## Worktree provenance
- worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- branch name: `feat/gmail-handoff-surface-first`
- base branch: `main`
- base SHA: `f7d754dd8298a59e96e212855cd8278d67237606`
- target integration branch: `main`
- canonical build status: live listener under test is still the previously started canonical `main` process; this patch lives on a feature branch until promoted

## Interfaces/types/contracts affected
- Preserved browser-app cold-start success reason: `browser_server_ready` now explicitly means server ready, not browser-surface ready
- Additive launch diagnostics fields:
  - `handoff_session_id`
  - `tab_resolution_strategy`
  - `workspace_surface_confirmed`
  - `client_hydration_status`
  - `bridge_context_posted`
  - `surface_visibility_status`
  - `extension_surface_outcome`
  - `extension_surface_reason`
  - `extension_surface_tab_id`
  - `surface_candidate_source`
  - `surface_candidate_valid`
  - `surface_invalidation_reason`
  - `fresh_tab_created_after_invalidation`
- Additive browser-app compatibility marker:
  - `extension_launch_session_schema_version`
- Preserved Gmail cold-start ownership contract:
  - native host/runtime owns `server_boot`
  - extension owns `browser_surface`

## File-by-file implementation steps
1. Update `extensions/gmail_intake/background.js` to:
   - require exact `gmail-intake` workspace tab confirmation before keeping a handoff in `warming`
   - stop Gmail clicks from hijacking arbitrary `127.0.0.1:8877/*` tabs
   - clear pending browser surfaces and active launch sessions on no-surface/no-hydration failures
   - post extension-side tab-resolution and hydration diagnostics into the correlated launch-session state
   - treat remembered and queried exact `gmail-intake` tabs as provisional until they validate against the active launch session and current client state
   - create one fresh exact Gmail workspace tab after invalidating a stale surface, then reuse that fresh tab for the same launch session instead of creating duplicates
2. Update browser-app hydration markers and bootstrap payloads in:
   - `src/legalpdf_translate/shadow_web/static/app.js`
   - `src/legalpdf_translate/shadow_web/templates/index.html`
   - `src/legalpdf_translate/shadow_web/app.py`
   so the page exposes launch-session-aware client state and a schema-compatibility marker.
3. Update `src/legalpdf_translate/shadow_web/app.py` with a local-only extension diagnostics endpoint that persists launch-session fields into app-data launch-session state.
4. Extend `src/legalpdf_translate/gmail_window_trace.py` to surface the additive extension diagnostics fields through `latest_window_trace_status(...)`.
5. Update focused regression coverage in:
   - `tests/test_gmail_intake.py`
   - `tests/test_shadow_web_api.py`
   - `tests/test_gmail_window_trace.py`

## Tests and acceptance criteria
1. Targeted tests pass for:
   - `tests/test_gmail_intake.py`
   - `tests/test_shadow_web_api.py`
   - `tests/test_gmail_window_trace.py`
   - `tests/test_gmail_focus_host.py`
   - relevant Gmail/translation non-regression slices already covering prepared-start defaults and Gmail-scoped run isolation
2. Acceptance:
   - Gmail click never reuses an unrelated localhost tab for `workspace=gmail-intake`
   - server-side `warming` does not keep the handoff alive unless the exact browser surface is confirmed
   - no-surface/no-hydration first clicks fail closed instead of surviving into a stale-retry second click
   - stale exact `gmail-intake` tabs from an older launch session are invalidated before reuse and cause one fresh exact workspace tab to be created
   - the first Gmail click after extension reload must not silently no-op by focusing an unusable stale workspace tab
   - correlated launch-session state shows the extension-side tab-resolution and hydration outcome
   - extension still opens or focuses at most one LegalPDF browser surface

## Risks and mitigations
1. Risk: strict Gmail workspace matching can strand users if the exact workspace tab fails to appear quickly.
   - Mitigation: fail fast with a clear retry/manual-focus message instead of silently holding the handoff.
2. Risk: extension-side diagnostics drift from host-side launch state.
   - Mitigation: persist them into the same launch-session file already exposed by runtime diagnostics.
3. Risk: preserving origin-tab fallback for non-Gmail workspaces could reintroduce ambiguity elsewhere.
   - Mitigation: limit the strict no-hijack rule to `workspace=gmail-intake` only in this pass.
4. Risk: the unpacked Edge extension and live listener can drift to different revisions and make diagnostics misleading.
   - Mitigation: add an explicit compatibility marker and validate this bug only after syncing the unpacked extension copy and restarting the live listener from the same code revision under test.

## Assumptions/defaults
1. The current user-facing failure is primarily an extension state-machine bug, not a fresh host/runtime cold-start failure.
2. `browser_server_ready` must not be treated as proof that the visible Gmail workspace surface exists yet.
3. `Prepare selected` remains prepare-only and still opens `New Job`.
4. Relevant validations executed in this pass:
   - `132 passed` across `tests/test_gmail_focus_host.py`, `tests/test_gmail_browser_service.py`, `tests/test_shadow_web_api.py`, `tests/test_gmail_window_trace.py`, and `tests/test_gmail_intake.py`
   - `22 passed` across `tests/test_translation_browser_state.py`, `tests/test_translation_service_gmail_context.py`, `tests/test_output_handling.py`, and `tests/test_checkpoint_resume.py`
   - browser-app and extension now expose a fresh per-click `handoff_session_id`, and the Gmail extension confirms a visible exact `gmail-intake` surface before posting the Gmail bridge context
