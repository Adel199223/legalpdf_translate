# Browser-to-Qt UX Alignment Stage 1

## Stage goal
- Lock the new staged roadmap on this worktree.
- Keep the daily browser shell calm by hiding routine operator chrome unless the user intentionally enters operator surfaces or a failure occurs.
- Preserve all direct routes and current live/shadow/Gmail contracts.

## Completed implementation
- Superseded the previous simple-shell plan with the new master ExecPlan and this stage packet.
- Kept primary navigation limited to `New Job`, conditional `Gmail`, `Recent Jobs`, and `More`.
- Hid build/workspace sidebar cards and primary-shell diagnostics panels by default.
- Added an explicit operator-details toggle under `More`.
- Kept operator chrome visible automatically on secondary/operator routes and auto-revealed diagnostics when failure paths request them.

## Files changed in this stage
- `docs/assistant/SESSION_RESUME.md`
- `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_master_plan.md`
- `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage1.md`
- `src/legalpdf_translate/shadow_web/templates/index.html`
- `src/legalpdf_translate/shadow_web/static/state.js`
- `src/legalpdf_translate/shadow_web/static/app.js`
- `src/legalpdf_translate/shadow_web/static/gmail.js`
- `src/legalpdf_translate/shadow_web/static/translation.js`
- `src/legalpdf_translate/shadow_web/static/style.css`
- `tests/test_shadow_web_route_state.py`
- `tests/test_shadow_web_api.py`

## Validation plan for this stage
- `python -m pytest -q tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py tests/test_shadow_web_server.py`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`

## Decision locks
- Operator chrome stays hidden by default on primary views.
- Operator chrome is reachable through `More` and an explicit toggle, not promoted into the main shell.
- Failure-driven diagnostics remain allowed to auto-reveal even when operator mode is off.
- Direct hashes such as `#dashboard`, `#settings`, `#profile`, `#power-tools`, and `#extension-lab` remain valid.

## Risks to watch before Stage 2
- Some advanced users may want routine technical panels always visible; the explicit operator toggle covers that, but Gmail/translation failure paths still need careful review.
- Stage 2 must avoid reintroducing overload by moving Gmail provenance and session state into bounded secondary surfaces instead of simply restyling the existing stacked layout.

## Prompt pack for next stages
- Stage 2 (`NEXT_STAGE_2`): convert `#gmail-intake` from a full workspace into a compact review-first handoff surface with deferred session/finalization drawers.
- Stage 3 (`NEXT_STAGE_3`): replace inline translation post-run/save stacking with one bounded completion surface that groups save/artifact/review actions together.
