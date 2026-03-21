# Browser-to-Qt UX Alignment Stage 2

## Stage goal
- Convert `#gmail-intake` from a stacked workspace into a compact review-first handoff surface.
- Keep the Gmail route focused on message summary, attachment choice, workflow choice, target language, and one clear continue path.
- Move Gmail session state, downstream confirmation, and finalization actions into a bounded same-tab drawer that appears only when relevant.

## Completed implementation
- Rebuilt the Gmail intake page around one compact review panel instead of separate full-width context and session workspaces.
- Moved thread/message/account/output overrides into a collapsed `Message Details and Overrides` section.
- Added a summary-first Gmail handoff card that shows extension defaults before the exact message is loaded and message status after load.
- Removed the inline Gmail session panel from the page and replaced it with a global same-tab `Session Actions` drawer.
- Updated the new-job Gmail strip so it opens the Gmail intake when only a handoff exists, and opens the session drawer when a Gmail session is already active.
- Kept the live route contract unchanged: Gmail handoff still targets `#gmail-intake`.

## Files changed in this stage
- `docs/assistant/SESSION_RESUME.md`
- `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage2.md`
- `src/legalpdf_translate/shadow_web/templates/index.html`
- `src/legalpdf_translate/shadow_web/static/gmail.js`
- `src/legalpdf_translate/shadow_web/static/style.css`
- `tests/test_shadow_web_api.py`

## Validation plan for this stage
- `python -m pytest -q tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py tests/test_shadow_web_server.py`
- `python -m pytest -q tests/test_browser_gmail_bridge.py`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`

## Decision locks
- `#gmail-intake` stays the Gmail bridge destination.
- Message/thread/account/output overrides stay collapsed by default.
- Session confirmation/finalization actions stay in a drawer, not on the default intake page.
- The Gmail strip on `#new-job` must stay compact and must not re-embed the full Gmail intake/session stack into the main shell.

## Risks to watch before Stage 3
- The drawer must stay discoverable once users leave Gmail intake and start working in translation or interpretation.
- Translation completion still remains fragmented across status, overflow, and the inline save surface; Stage 3 must consolidate that without reintroducing page overload.

## Prompt pack for next stages
- Stage 3 (`NEXT_STAGE_3`): replace inline translation post-run/save stacking with one bounded completion surface that groups save/artifact/review actions together.
- Stage 4 (`NEXT_STAGE_4`): convert interpretation from autofill-plus-admin-form into a seeded-review flow with collapsed redundant sections and bounded export/finalization surfaces.
