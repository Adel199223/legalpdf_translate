# Browser-to-Qt UX Alignment Stage 3

## Stage goal
- Keep the default translation shell limited to `Job Setup`, `Run Status`, and `Action Rail`.
- Move translation completion, artifacts, and job-log save work off the main page and into one bounded same-tab finish surface.
- Keep `Advanced Settings` collapsed by default and reserve the action overflow for low-frequency utilities only.

## Completed implementation
- Removed the inline translation post-run panel from `#new-job`.
- Added a bounded `Finish Translation` drawer that opens automatically when analyze or translation completion becomes actionable.
- Kept the main translation shell calm: the overflow now keeps only `Analyze Only`, `Resume Translation`, and `Rebuild DOCX`.
- Moved review export and download artifacts into the completion drawer instead of leaving them in the main action rail.
- Kept `Run Metrics` and `Amounts` collapsed by default inside the bounded save surface.
- Added a contextual `Finish Translation` / `Review Results` reopen button on the `Run Status` card so users can return to the bounded surface without reloading a crowded page.
- Ensured analyze-only completion shows artifacts without forcing an empty save form, while saved translation rows still reopen directly into the bounded edit/save surface.

## Files changed in this stage
- `docs/assistant/SESSION_RESUME.md`
- `docs/assistant/exec_plans/active/2026-03-21_browser_qt_alignment_stage3.md`
- `docs/assistant/exec_plans/completed/2026-03-21_browser_qt_alignment_stage2.md`
- `src/legalpdf_translate/shadow_web/templates/index.html`
- `src/legalpdf_translate/shadow_web/static/translation.js`
- `src/legalpdf_translate/shadow_web/static/style.css`
- `tests/test_shadow_web_api.py`

## Validation plan for this stage
- `python -m pytest -q tests/test_shadow_web_route_state.py tests/test_shadow_web_api.py tests/test_shadow_web_server.py`
- `python -m pytest -q tests/test_browser_gmail_bridge.py`
- `dart run tooling/validate_agent_docs.dart`
- `dart run tooling/validate_workspace_hygiene.dart`
- Playwright smoke on a temporary shadow preview:
  - default `#new-job` remains limited to setup/status/action rail
  - analyze completion opens the bounded finish surface instead of rendering an inline save stack

## Decision locks
- Translation completion stays in a bounded same-tab drawer, not as another permanent panel on `#new-job`.
- The action overflow remains limited to low-frequency utilities.
- Artifact download and review-export actions stay grouped with completion/save work, not in the main shell.
- Analyze-only completion may open the drawer, but it must not show an empty save form.

## Risks to watch before Stage 4
- The completion drawer must stay discoverable without becoming another always-open operator surface.
- Interpretation still uses a longer seeded-admin layout, so Stage 4 must apply the same bounded-surface discipline there without losing autofill momentum.

## Prompt pack for next stages
- Stage 4 (`NEXT_STAGE_4`): convert interpretation from autofill-plus-admin-form into a seeded-review flow with collapsed redundant sections and bounded export/finalization surfaces.
- Stage 5 (`NEXT_STAGE_5`): align remaining secondary routes with Qt-style dialog/table/preview behavior and complete whole-app cleanup across wide/narrow layouts.
