# Gmail Workspace Strip Adapter Presentation

## Goal And Non-Goals

Extract Gmail workspace-strip visibility and adapter shaping from `gmail.js` into a pure session presentation helper while preserving the existing safe DOM renderer and Gmail contracts.

Non-goals: no backend routes, payloads, submitted values, DOM IDs, dataset names, Gmail/native-host behavior, live Gmail/OAuth flow, or text-rendering changes.

## Scope

In scope:
- Add `buildGmailWorkspaceStripAdapterPresentation(...)` in `gmail_session_presentation.js`.
- Keep `buildGmailWorkspaceStripPresentation(...)` as the final pure card builder.
- Update `renderWorkspaceStrip()` in `gmail.js` so it gathers coordinator state and delegates visibility/card shaping to the adapter.
- Add red-first ESM/contract/static asset coverage.
- Validate with focused tests, full validation, and shadow Browser smoke.
- Publish through a ready PR and merge after green checks.

Out of scope:
- Live Gmail testing, OAuth testing, native-host testing, API route changes, and unrelated UI refactors.

## Worktree Provenance

- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate_gmail_workspace_strip_adapter`
- Branch name: `codex/gmail-workspace-strip-adapter`
- Base branch: `main`
- Base SHA: `ddc628919b1abebd2b1d1120191c571b2d42fc86`
- Target integration branch: `main`
- Canonical build status: noncanonical feature worktree; shadow-mode browser validation only.

## Interfaces, Types, And Contracts Affected

- `renderWorkspaceStrip()` remains an internal Gmail coordinator renderer.
- `renderGmailWorkspaceStripInto(...)` remains the safe DOM-only renderer.
- Existing strip IDs and action dataset contracts remain unchanged, including `gmail-workspace-strip`, `gmail-workspace-strip-title`, `gmail-workspace-strip-copy`, `gmail-workspace-strip-action`, and the `data-gmail-strip-action` behavior.
- Dynamic text continues flowing through presentation objects and safe DOM writes.

## File-By-File Implementation Steps

- `src/legalpdf_translate/shadow_web/static/gmail_session_presentation.js`: export `buildGmailWorkspaceStripAdapterPresentation(...)` and delegate to the existing card builder.
- `src/legalpdf_translate/shadow_web/static/gmail.js`: import the adapter helper and simplify `renderWorkspaceStrip()` to gather state/nodes and render the returned presentation.
- `tests/test_shadow_web_api.py`: add failing adapter export, ESM behavior, ownership, and static asset assertions first.
- `docs/assistant/exec_plans/active/2026-05-10_gmail_workspace_strip_adapter.md`: record progress, validation, review, and move to `completed/` before commit.

## Tests And Acceptance Criteria

Red first:
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py::test_gmail_session_presentation_module_builds_workspace_strip_card tests/test_shadow_web_api.py::test_gmail_workspace_ui_module_owns_workspace_strip_renderer`
- Result: failed before implementation because the new adapter export/use did not exist yet.

After implementation:
- Same targeted tests pass.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_browser_safe_rendering.py tests/test_translation_browser_state.py tests/test_gmail_review_state.py tests/test_profile_browser_state.py`
- `powershell -ExecutionPolicy Bypass -File scripts/validate_dev.ps1 -Full`
- Result: targeted adapter/ownership/stage tests passed, focused browser/Gmail suite passed with `200 passed`, and full validation passed. The full validation wrapper hit the known `dart run` AOT launcher issue, then the direct-Dart fallback passed for agent-doc and workspace-hygiene validation.

Browser smoke:
- Launch shadow app on port `8888`.
- Verify `http://127.0.0.1:8888/?mode=shadow&workspace=gmail-review-demo#gmail-intake`.
- Confirm page identity, nonblank content, no framework overlay, console health, screenshot evidence where possible, workspace strip behavior, review detail/preview smoke, and no live Gmail/OAuth/native-host flow.
- Result: shadow app was launched from this feature worktree on port `8888` with isolated workspace `gmail-workspace-strip-smoke`. Browser verified page identity (`LegalPDF Translate`), meaningful Gmail intake content, no framework overlay, no console warnings/errors, and the workspace strip card/action from `#new-job` after closing the seeded review drawer overlay. The strip rendered `Gmail attachment ready`, kept `data-gmail-strip-action="open-intake"`, and returned to `#gmail-intake`. Browser screenshot capture timed out through the in-app CDP path; fallback headless capture produced app-shell screenshot evidence, while DOM/console/interaction checks covered the strip behavior itself.

## Rollout And Fallback

Publish flow after validation:
- Stage only intended files.
- Commit `Extract Gmail workspace strip adapter presentation`.
- Push `codex/gmail-workspace-strip-adapter`.
- Create ready PR `[codex] Extract Gmail workspace strip adapter presentation`.
- Wait for green CI, merge normally, fast-forward canonical `main`, prune refs, and remove the feature worktree only after `main` contains the merge.

Fallback: stop before merge if auth fails, PR creation fails, CI is red, conflicts appear, or required checks remain unexpectedly pending.

## Risks And Mitigations

- Risk: workspace strip visibility changes on interpretation-focused shells. Mitigation: ESM adapter probes for hidden interpretation shell and visible non-focused states.
- Risk: recovered finalized batch CTA changes. Mitigation: ESM adapter probes for recovered-only and default Gmail-message states.
- Risk: unsafe text rendering regressions. Mitigation: keep DOM writes in `gmail_workspace_ui.js` and run existing safe-rendering/browser regression tests.

## Assumptions And Defaults

- No live Gmail/OAuth/native-host testing is in scope.
- The adapter receives already-derived coordinator facts and must not read global runtime state.
- The feature PR should be ready for review/merge after validations pass.
