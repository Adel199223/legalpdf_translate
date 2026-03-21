# Browser-to-Qt UX Alignment Stage 4

## Stage goal
- Convert interpretation from a long autofill-plus-admin page into a seeded-review flow.
- Keep autofill as a short intake step, then move save, export, and Gmail follow-up into one bounded same-tab review surface.
- Apply calmer Qt-style disclosure defaults so redundant detail stays tucked away until it becomes relevant.

## Completed implementation
- Renamed the top interpretation card to `Interpretation Intake` and reframed it as a short intake step instead of a full work surface.
- Replaced the old long inline interpretation form on `#new-job` with a compact `Seed Review` card that summarizes the recovered case context and offers one clear reopen action.
- Added a bounded `Review Interpretation` drawer that now owns the interpretation form, row save, honorarios export, Gmail session follow-up, and diagnostics.
- Made Gmail interpretation handoff open directly into the bounded review drawer after seed preparation so Gmail follow-up remains contextual instead of crowding the main shell.
- Kept `SERVICE`, `TEXT`, `RECIPIENT`, and `Amounts (EUR)` as the interpretation disclosure model while decluttering their defaults:
  - `SERVICE` stays collapsed when it mirrors the case
  - `TEXT` stays collapsed until wording/export detail is customized
  - `RECIPIENT` stays collapsed while it remains auto-derived
  - `Amounts` stays collapsed until final review
- Fixed the blank-seed interpretation summary so zero-valued defaults no longer look like a recovered interpretation row.

## Files changed in this stage
- `docs/assistant/SESSION_RESUME.md`
- `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage4.md`
- `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage3.md`
- `src/legalpdf_translate/shadow_web/templates/index.html`
- `src/legalpdf_translate/shadow_web/static/app.js`
- `src/legalpdf_translate/shadow_web/static/gmail.js`
- `src/legalpdf_translate/shadow_web/static/style.css`
- `tests/test_shadow_web_api.py`

## Validation plan for this stage
- `python -m pytest -q tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py tests/test_shadow_web_server.py`
- `python -m pytest -q tests/test_browser_gmail_bridge.py`
- `python -m compileall src tests`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- Playwright smoke on a temporary shadow preview:
  - interpretation home stays compact on first view
  - successful autofill or saved-row reopen leads into the bounded review drawer
  - Gmail interpretation session actions stay contextual and do not crowd the main shell

## Decision locks
- Interpretation save/export/finalization work stays in a bounded same-tab drawer, not as another stacked panel on `#new-job`.
- The calmer web shell intentionally keeps `TEXT` collapsed by default even though current Qt code/tests are slightly more permissive there; this is a deliberate web-native declutter choice under the approved Stage 4 plan.
- Gmail follow-up remains contextual to the review surface and must not re-expand into a full inline Gmail session stack on the main shell.
- Blank interpretation seeds must read as blank review starts, not as already-recovered records.

## Risks to watch before Stage 5
- The new review drawer must stay discoverable without becoming another always-open operator surface.
- Secondary routes such as review queue, job log, settings, and export/edit flows still need the same bounded-surface discipline applied across the rest of the app.
- Mobile and narrow-width behavior still needs the whole-app Stage 5 cleanup so these bounded surfaces remain calm under smaller layouts.

## Prompt pack for next stages
- Stage 5 (`NEXT_STAGE_5`): align remaining secondary routes with Qt-style dialog/table/preview behavior, complete wide/narrow whole-app cleanup, and finish the browser-to-Qt acceptance pass.
