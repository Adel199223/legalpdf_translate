# Browser Gmail Intake Beginner Qt Polish

## Goal and non-goals
- Goal: make the browser `ui=qt` `#gmail-intake` flow feel beginner-friendly and Qt-like while preserving the current Gmail attachment intake/review behavior, routes, and backend contracts.
- Non-goals: Gmail extension/native-host contract changes, translation or interpretation workflow rewrites, completion/finalization redesign, `ui=legacy` changes, or `mode=live|shadow` / `workspace=...` / `#gmail-intake` / `#new-job` contract changes.

## Scope (in/out)
- In: Gmail intake hero/main panel copy, beginner home-card presentation, top Gmail action visibility, review drawer wording, attachment-table labels, current-attachment card wording, stage-specific beginner display labels, and the compact Gmail strip on `#new-job`.
- Out: backend API shape, runtime guard behavior, preview mechanics, prepared translation launch behavior, interpretation seed semantics, and operator diagnostics removal.

## Worktree provenance
- Worktree path: `C:\Users\FA507\.codex\legalpdf_translate`
- Branch name: `feat/browser-new-job-qt-polish`
- Base branch: `main`
- Base SHA: `f70d65c92df8d31e7a6f0b53c667aee5bad2cf2b`
- Target integration branch: `main`
- Canonical build status or intended noncanonical override: noncanonical feature branch used for browser UX iteration only; no runtime contract changes.

## Interfaces/types/contracts affected
- No backend or route contract changes.
- Additive browser-only display helpers may be added in `gmail_review_state.js` for beginner labels and stage-specific surface copy.
- Existing workflow values remain unchanged: `translation` / `interpretation`, target language `EN` / `FR` / `AR`, selected attachment state, start page state.

## File-by-file implementation steps
- `src/legalpdf_translate/shadow_web/templates/index.html`
  - Rewrite beginner-visible `#gmail-intake` hero, action row, details summary text, drawer labels, attachment-table headers, and compact Gmail strip copy.
  - Move refresh/open-full/reset actions into a collapsed advanced surface while keeping IDs and behavior intact.
- `src/legalpdf_translate/shadow_web/static/gmail_review_state.js`
  - Add pure display helpers for beginner workflow labels, prepare-button labels, stage-specific CTA/status text, and compact-strip wording.
- `src/legalpdf_translate/shadow_web/static/gmail.js`
  - Refactor beginner-visible renderers (`renderMessageResult`, `renderReviewSummary`, `renderAttachmentList`, `renderReviewDetail`, `renderResumeCard`, `renderWorkspaceStrip`, session/result copy) to use the new helper labels and hide technical fields from the beginner path.
- `src/legalpdf_translate/shadow_web/static/app.js`
  - Align route-aware shell chrome wording for Gmail intake contexts without changing shell-mode logic.
- `src/legalpdf_translate/shadow_web/static/style.css`
  - Tighten Gmail review row emphasis and support any low-risk layout adjustments needed for the renamed/collapsed beginner controls.
- Tests
  - Update `tests/test_shadow_web_api.py`, `tests/test_gmail_review_state.py`, and `tests/test_gmail_intake.py` to assert beginner-visible copy, helper outputs, and unchanged Gmail/runtime behavior.

## Tests and acceptance criteria
- `python -m pytest -q tests/test_gmail_review_state.py`
- `python -m pytest -q tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`
- `python -m pytest -q tests/test_shadow_web_route_state.py`
- `python -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
- `python -m compileall src tests`
- `dart run tooling/validate_agent_docs.dart` if docs are touched; fall back to direct Dart executable if `dartdev` AOT is broken.
- `dart run tooling/validate_workspace_hygiene.dart` if available; same fallback rule.
- Acceptance: Gmail intake reads like a guided review step, technical controls are tucked away, and prepared translation / interpretation / preview / runtime guard regressions do not occur.

## Rollout and fallback
- Keep the current DOM IDs, routes, and action handlers in place so the pass remains a copy/layout/state refactor only.
- If a copy/layout change risks breaking Gmail session progression, prefer preserving current behavior and moving only the technical wording/control visibility.

## Risks and mitigations
- Risk: beginner-copy changes accidentally hide required troubleshooting controls.
  - Mitigation: keep controls reachable through existing details/operator surfaces and preserve handler IDs.
- Risk: stage text drifts from actual Gmail session state.
  - Mitigation: centralize new beginner display labels in pure helpers layered on top of the existing stage helpers instead of re-deriving session logic in the renderer.
- Risk: markup assertions become brittle.
  - Mitigation: assert beginner-visible labels and required hidden/control presence separately, not by snapshotting whole sections.

## Assumptions/defaults
- The existing `gmail-focus` Qt shell remains the correct layout shell for the normal Gmail intake experience.
- Runtime guard details stay operator-facing except when a failure forces their surface open.
- APP_KNOWLEDGE and user guides are not updated unless the implementation introduces an immediate docs mismatch.

## Executed validations and outcomes
- `python -m pytest -q tests/test_gmail_review_state.py`
  - Result: failed in this environment because `C:\Python314\python.exe` does not have `pytest` installed.
- `python -m pytest -q tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`
  - Result: failed in this environment because `C:\Python314\python.exe` does not have `pytest` installed.
- `python -m pytest -q tests/test_shadow_web_route_state.py`
  - Result: failed in this environment because `C:\Python314\python.exe` does not have `pytest` installed.
- `python -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
  - Result: failed in this environment because `C:\Python314\python.exe` does not have `pytest` installed.
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_review_state.py`
  - Result: `1 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_gmail_intake.py -k "browser_pdf or runtime_guard or review"`
  - Result: `5 passed, 9 deselected`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_route_state.py`
  - Result: `3 passed`
- `.\.venv311\Scripts\python.exe -m pytest -q tests/test_shadow_web_api.py tests/test_shadow_web_route_state.py tests/test_translation_browser_state.py`
  - Result: `54 passed`
- `python -m compileall src tests`
  - Result: succeeded.
- `dart run tooling/validate_agent_docs.dart`
  - Result: failed with `Unable to find AOT snapshot for dartdev`.
- `dart run tooling/validate_workspace_hygiene.dart`
  - Result: failed with `Unable to find AOT snapshot for dartdev`.
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_agent_docs.dart`
  - Result: `PASS: agent docs validation succeeded.`
- `C:\dev\tools\flutter\bin\cache\dart-sdk\bin\dart.exe tooling/validate_workspace_hygiene.dart`
  - Result: `PASS: workspace hygiene validation succeeded.`
